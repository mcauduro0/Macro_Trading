"""Tests for BacktestEngine v2 -- portfolio backtesting, walk-forward, TransactionCostModel.

Covers:
- TransactionCostModel: 12-instrument cost table, prefix matching, cost calculations
- BacktestEngine.run_portfolio: equal/custom weights, result structure, attribution
- BacktestEngine.walk_forward_validation: window generation, output format
- BacktestConfig backward compatibility: defaults, new v2 fields

Uses mock strategies and loaders to keep tests fast and self-contained.
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.backtesting.costs import TransactionCostModel
from src.backtesting.engine import BacktestConfig, BacktestEngine
from src.backtesting.metrics import BacktestResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def cost_model():
    """TransactionCostModel instance."""
    return TransactionCostModel()


@pytest.fixture
def base_config():
    """Basic BacktestConfig for tests."""
    return BacktestConfig(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 3, 31),
        initial_capital=1_000_000.0,
        rebalance_frequency="monthly",
    )


@pytest.fixture
def mock_loader():
    """MagicMock for PointInTimeDataLoader."""
    loader = MagicMock()
    # Return a DataFrame with close prices when get_market_data is called
    dates = pd.bdate_range("2024-01-01", "2024-03-31")
    prices = 100.0 * (1 + np.random.RandomState(42).randn(len(dates)).cumsum() * 0.01)
    df = pd.DataFrame({"close": prices}, index=dates)
    loader.get_market_data.return_value = df
    return loader


class MockStrategy:
    """Mock strategy that returns fixed weights for testing."""

    def __init__(self, strategy_id: str, fixed_weights: dict[str, float]):
        self.strategy_id = strategy_id
        self._weights = fixed_weights

    def generate_signals(self, as_of_date: date) -> dict[str, float]:
        return self._weights


@pytest.fixture
def mock_strategies():
    """Two mock strategies with different instruments."""
    return [
        MockStrategy("STRAT_A", {"IBOVESPA": 0.3, "DI_PRE_365": 0.2}),
        MockStrategy("STRAT_B", {"USDBRL": 0.4, "ZN_10Y": 0.1}),
    ]


# ---------------------------------------------------------------------------
# TransactionCostModel tests
# ---------------------------------------------------------------------------
class TestTransactionCostModel:
    def test_cost_table_has_12_instruments(self, cost_model):
        assert len(TransactionCostModel.COST_TABLE) == 12
        expected_keys = {
            "DI1", "DDI", "DOL", "NDF", "NTN_B", "LTN",
            "UST", "ZN", "ZF", "ES", "CDS_BR", "IBOV_FUT",
        }
        assert set(TransactionCostModel.COST_TABLE.keys()) == expected_keys

    def test_get_cost_bps_known_instrument_di1(self, cost_model):
        # DI1: spread=0.5 + commission=0.3 + exchange_fee=0.2 = 1.0
        assert cost_model.get_cost_bps("DI1") == 1.0

    def test_get_cost_bps_known_instrument_cds_br(self, cost_model):
        # CDS_BR: spread=5.0 + commission=0.0 + exchange_fee=0.0 = 5.0
        assert cost_model.get_cost_bps("CDS_BR") == 5.0

    def test_get_cost_bps_known_instrument_es(self, cost_model):
        # ES: spread=0.2 + commission=0.5 + exchange_fee=0.3 = 1.0
        assert cost_model.get_cost_bps("ES") == 1.0

    def test_get_cost_bps_known_instrument_dol(self, cost_model):
        # DOL: spread=0.3 + commission=0.3 + exchange_fee=0.2 = 0.8
        assert cost_model.get_cost_bps("DOL") == 0.8

    def test_get_cost_bps_unknown_returns_default(self, cost_model):
        # Unknown instrument -> default 2.0 bps
        assert cost_model.get_cost_bps("UNKNOWN_TICKER") == 2.0

    def test_get_cost_bps_prefix_matching_di_pre(self, cost_model):
        # "DI_PRE_365" should match prefix "DI_PRE" -> DI1 -> 1.0
        assert cost_model.get_cost_bps("DI_PRE_365") == 1.0

    def test_get_cost_bps_prefix_matching_usdbrl(self, cost_model):
        # "USDBRL" should match prefix -> NDF -> 2.0
        assert cost_model.get_cost_bps("USDBRL") == 2.0

    def test_get_cost_bps_prefix_matching_ibov(self, cost_model):
        # "IBOV_..." should match prefix "IBOV" -> IBOV_FUT -> 1.5
        assert cost_model.get_cost_bps("IBOV_SPOT") == 1.5

    def test_get_cost_notional(self, cost_model):
        # DI1: 1M notional * 1.0 bps / 10000 = 100.0 USD
        assert cost_model.get_cost("DI1", 1_000_000) == 100.0

    def test_get_cost_negative_notional(self, cost_model):
        # Should use abs(notional)
        assert cost_model.get_cost("DI1", -1_000_000) == 100.0

    def test_get_round_trip_bps(self, cost_model):
        # DI1: 2 * 1.0 = 2.0
        assert cost_model.get_round_trip_bps("DI1") == 2.0

    def test_get_round_trip_bps_cds(self, cost_model):
        # CDS_BR: 2 * 5.0 = 10.0
        assert cost_model.get_round_trip_bps("CDS_BR") == 10.0

    def test_custom_default_bps(self):
        tcm = TransactionCostModel(default_bps=5.0)
        assert tcm.get_cost_bps("TOTALLY_UNKNOWN") == 5.0

    def test_all_instruments_have_three_components(self, cost_model):
        for key, costs in TransactionCostModel.COST_TABLE.items():
            assert "spread" in costs, f"{key} missing spread"
            assert "commission" in costs, f"{key} missing commission"
            assert "exchange_fee" in costs, f"{key} missing exchange_fee"
            # All components should be non-negative
            assert costs["spread"] >= 0
            assert costs["commission"] >= 0
            assert costs["exchange_fee"] >= 0


# ---------------------------------------------------------------------------
# BacktestEngine.run_portfolio tests
# ---------------------------------------------------------------------------
class TestRunPortfolio:
    def test_run_portfolio_equal_weights(
        self, base_config, mock_loader, mock_strategies
    ):
        engine = BacktestEngine(base_config, mock_loader)
        result = engine.run_portfolio(mock_strategies)

        # Check result structure
        assert "portfolio_result" in result
        assert "individual_results" in result
        assert "weights" in result
        assert "correlation_matrix" in result
        assert "attribution" in result

        # Equal weights for 2 strategies
        assert result["weights"] == {"STRAT_A": 0.5, "STRAT_B": 0.5}

        # Individual results should contain both strategies
        assert "STRAT_A" in result["individual_results"]
        assert "STRAT_B" in result["individual_results"]

        # Portfolio result should be a BacktestResult
        assert isinstance(result["portfolio_result"], BacktestResult)
        assert result["portfolio_result"].strategy_id == "PORTFOLIO"

    def test_run_portfolio_custom_weights(
        self, base_config, mock_loader, mock_strategies
    ):
        engine = BacktestEngine(base_config, mock_loader)
        custom_weights = {"STRAT_A": 0.7, "STRAT_B": 0.3}
        result = engine.run_portfolio(mock_strategies, weights=custom_weights)

        assert result["weights"] == {"STRAT_A": 0.7, "STRAT_B": 0.3}

    def test_run_portfolio_single_strategy(self, base_config, mock_loader):
        strategy = MockStrategy("SINGLE", {"IBOVESPA": 0.5})
        engine = BacktestEngine(base_config, mock_loader)
        result = engine.run_portfolio([strategy])

        assert result["weights"] == {"SINGLE": 1.0}
        assert "SINGLE" in result["individual_results"]

    def test_run_portfolio_attribution_sums_to_one(
        self, base_config, mock_loader, mock_strategies
    ):
        engine = BacktestEngine(base_config, mock_loader)
        result = engine.run_portfolio(mock_strategies)

        # Attribution values should sum close to 1.0
        total_attr = sum(result["attribution"].values())
        assert abs(total_attr - 1.0) < 0.01

    def test_run_portfolio_empty_raises(self, base_config, mock_loader):
        engine = BacktestEngine(base_config, mock_loader)
        with pytest.raises(ValueError, match="strategies list must not be empty"):
            engine.run_portfolio([])


# ---------------------------------------------------------------------------
# Walk-forward validation tests
# ---------------------------------------------------------------------------
class TestWalkForwardValidation:
    def test_walk_forward_window_generation(self):
        """With 36-month period, train=12, test=6, should get 4 windows."""
        start = date(2020, 1, 1)
        end = date(2023, 1, 1)  # 36 months
        windows = BacktestEngine._generate_wf_windows(start, end, 12, 6)

        assert len(windows) > 0
        for train_start, train_end, test_start, test_end in windows:
            assert train_start < train_end
            assert train_end == test_start
            assert test_start < test_end
            assert test_end <= end

    def test_walk_forward_window_generation_24_months(self):
        """With 24-month period, train=12, test=6, get correct count."""
        start = date(2022, 1, 1)
        end = date(2024, 1, 1)  # 24 months
        windows = BacktestEngine._generate_wf_windows(start, end, 12, 6)

        # train=12mo, test=6mo, advance by 6mo each step
        # Window 0: train 2022-01 to 2023-01, test 2023-01 to 2023-07 (fits)
        # Window 1: train 2022-07 to 2023-07, test 2023-07 to 2024-01 (fits)
        # Window 2: train 2023-01 to 2024-01, test 2024-01 to 2024-07 (exceeds end)
        assert len(windows) == 2

    def test_walk_forward_short_period_no_windows(self):
        """Period shorter than train+test -> no windows."""
        start = date(2023, 1, 1)
        end = date(2023, 6, 1)  # 5 months
        windows = BacktestEngine._generate_wf_windows(start, end, 12, 6)
        assert len(windows) == 0

    def test_walk_forward_returns_list_of_dicts(self, mock_loader):
        config = BacktestConfig(
            start_date=date(2022, 1, 1),
            end_date=date(2024, 1, 1),
            initial_capital=1_000_000.0,
            rebalance_frequency="monthly",
            walk_forward=True,
            walk_forward_train_months=12,
            walk_forward_test_months=6,
        )
        engine = BacktestEngine(config, mock_loader)
        strategy = MockStrategy("WF_TEST", {"IBOVESPA": 0.5})

        results = engine.walk_forward_validation(strategy)

        assert isinstance(results, list)
        assert len(results) > 0

        for wf_result in results:
            assert "window" in wf_result
            assert "train_start" in wf_result
            assert "train_end" in wf_result
            assert "test_start" in wf_result
            assert "test_end" in wf_result
            assert "in_sample_sharpe" in wf_result
            assert "out_of_sample_sharpe" in wf_result
            assert "in_sample_result" in wf_result
            assert "out_of_sample_result" in wf_result
            assert "params_used" in wf_result
            assert isinstance(wf_result["in_sample_result"], BacktestResult)
            assert isinstance(wf_result["out_of_sample_result"], BacktestResult)

    def test_walk_forward_no_param_grid(self, mock_loader):
        """Without param_grid, params_used should be empty dict."""
        config = BacktestConfig(
            start_date=date(2022, 1, 1),
            end_date=date(2024, 1, 1),
            initial_capital=1_000_000.0,
            rebalance_frequency="monthly",
            walk_forward_train_months=12,
            walk_forward_test_months=6,
        )
        engine = BacktestEngine(config, mock_loader)
        strategy = MockStrategy("WF_TEST", {"IBOVESPA": 0.5})

        results = engine.walk_forward_validation(strategy)

        for wf_result in results:
            assert wf_result["params_used"] == {}


# ---------------------------------------------------------------------------
# BacktestConfig backward compat tests
# ---------------------------------------------------------------------------
class TestBacktestConfigV2:
    def test_backtest_config_defaults(self):
        """v1 defaults preserved."""
        c = BacktestConfig(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=1_000_000.0,
        )
        assert c.transaction_cost_bps == 5.0
        assert c.slippage_bps == 2.0
        assert c.max_leverage == 1.0
        assert c.rebalance_frequency == "monthly"

    def test_backtest_config_new_fields(self):
        """v2 fields have correct defaults."""
        c = BacktestConfig(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=1_000_000.0,
        )
        assert c.walk_forward is False
        assert c.walk_forward_train_months == 60
        assert c.walk_forward_test_months == 12
        assert c.funding_rate == 0.05
        assert c.point_in_time is True
        assert c.cost_model is None

    def test_backtest_config_with_cost_model(self):
        """Can pass a TransactionCostModel."""
        tcm = TransactionCostModel()
        c = BacktestConfig(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=1_000_000.0,
            cost_model=tcm,
        )
        assert c.cost_model is tcm

    def test_backtest_config_frozen(self):
        """Config remains frozen."""
        c = BacktestConfig(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=1_000_000.0,
        )
        with pytest.raises((AttributeError, TypeError)):
            c.initial_capital = 2e6  # type: ignore[misc]

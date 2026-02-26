"""Tests for BacktestEngine signal adapter and non-zero-trade backtesting.

Covers:
- _adapt_signals_to_weights: dict passthrough, list[StrategyPosition],
  list[StrategySignal] (LONG/SHORT/NEUTRAL/multi-instrument), empty list, None
- Integration: v3 strategy backtest produces non-zero trades + valid metrics
- Integration: v2 strategy backtest produces non-zero trades
- Integration: mixed v2/v3 portfolio backtest via run_portfolio

Uses mock strategies and loaders to keep tests fast and self-contained.
"""
from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock

import numpy as np
import pandas as pd

from src.backtesting.engine import BacktestConfig, BacktestEngine
from src.backtesting.metrics import BacktestResult
from src.core.enums import AssetClass, SignalDirection, SignalStrength
from src.strategies.base import StrategyPosition, StrategySignal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_engine(
    start: date = date(2024, 1, 1),
    end: date = date(2024, 6, 30),
    freq: str = "monthly",
) -> BacktestEngine:
    """Create a BacktestEngine with a mock loader returning synthetic prices."""
    loader = MagicMock()
    dates = pd.bdate_range(start=start, end=end)
    # Deterministic but varying price series
    rng = np.random.RandomState(42)
    prices = 100.0 + rng.randn(len(dates)).cumsum() * 0.5
    prices = np.maximum(prices, 10.0)  # ensure positive
    df = pd.DataFrame({"close": prices}, index=dates)
    loader.get_market_data.return_value = df

    config = BacktestConfig(
        start_date=start,
        end_date=end,
        initial_capital=1_000_000.0,
        rebalance_frequency=freq,
    )
    return BacktestEngine(config, loader)


def _make_signal(
    direction: SignalDirection = SignalDirection.LONG,
    instruments: list[str] | None = None,
    size: float = 0.3,
    strategy_id: str = "TEST_V3",
) -> StrategySignal:
    """Create a StrategySignal with sensible defaults."""
    return StrategySignal(
        strategy_id=strategy_id,
        timestamp=datetime(2024, 1, 31),
        direction=direction,
        strength=SignalStrength.MODERATE,
        confidence=0.7,
        z_score=1.2,
        raw_value=1.2,
        suggested_size=size,
        asset_class=AssetClass.FX,
        instruments=instruments or ["USDBRL"],
        entry_level=5.0,
        stop_loss=4.8,
        take_profit=5.3,
    )


def _make_position(
    instrument: str = "DI_PRE_365",
    weight: float = 0.25,
    strategy_id: str = "TEST_V2",
) -> StrategyPosition:
    """Create a StrategyPosition with sensible defaults."""
    return StrategyPosition(
        strategy_id=strategy_id,
        instrument=instrument,
        weight=weight,
        confidence=0.8,
        direction=SignalDirection.LONG,
        entry_signal="test_signal",
    )


# ---------------------------------------------------------------------------
# Unit tests for _adapt_signals_to_weights
# ---------------------------------------------------------------------------
class TestAdaptSignalsToWeights:
    """Unit tests for BacktestEngine._adapt_signals_to_weights."""

    def _get_adapter(self) -> BacktestEngine:
        return _make_engine()

    def test_adapt_dict_passthrough(self):
        """dict[str, float] input returns unchanged."""
        engine = self._get_adapter()
        weights = {"USDBRL": 0.3, "DI_PRE_365": -0.2}
        result = engine._adapt_signals_to_weights(weights)
        assert result is weights  # exact same object
        assert result == {"USDBRL": 0.3, "DI_PRE_365": -0.2}

    def test_adapt_strategy_position_list(self):
        """list[StrategyPosition] converts to {instrument: weight}."""
        engine = self._get_adapter()
        positions = [
            _make_position("DI_PRE_365", 0.25),
            _make_position("DI_PRE_730", 0.15),
        ]
        result = engine._adapt_signals_to_weights(positions)
        assert result == {"DI_PRE_365": 0.25, "DI_PRE_730": 0.15}

    def test_adapt_strategy_signal_list_long(self):
        """list[StrategySignal] with LONG direction -> +suggested_size."""
        engine = self._get_adapter()
        signals = [_make_signal(SignalDirection.LONG, ["USDBRL"], 0.3)]
        result = engine._adapt_signals_to_weights(signals)
        assert result == {"USDBRL": 0.3}

    def test_adapt_strategy_signal_list_short(self):
        """list[StrategySignal] with SHORT direction -> -suggested_size."""
        engine = self._get_adapter()
        signals = [_make_signal(SignalDirection.SHORT, ["USDBRL"], 0.3)]
        result = engine._adapt_signals_to_weights(signals)
        assert result == {"USDBRL": -0.3}

    def test_adapt_strategy_signal_list_neutral(self):
        """NEUTRAL signal produces weight 0.0."""
        engine = self._get_adapter()
        signals = [_make_signal(SignalDirection.NEUTRAL, ["USDBRL"], 0.3)]
        result = engine._adapt_signals_to_weights(signals)
        assert result == {"USDBRL": 0.0}

    def test_adapt_strategy_signal_multi_instrument(self):
        """A signal with instruments=["DI_PRE_365", "DI_PRE_730"] produces entries for both."""
        engine = self._get_adapter()
        signals = [
            _make_signal(
                SignalDirection.LONG,
                ["DI_PRE_365", "DI_PRE_730"],
                0.2,
            )
        ]
        result = engine._adapt_signals_to_weights(signals)
        assert result == {"DI_PRE_365": 0.2, "DI_PRE_730": 0.2}

    def test_adapt_strategy_signal_sum_same_instrument(self):
        """Multiple signals targeting the same instrument are summed."""
        engine = self._get_adapter()
        signals = [
            _make_signal(SignalDirection.LONG, ["USDBRL"], 0.2),
            _make_signal(SignalDirection.LONG, ["USDBRL"], 0.1),
        ]
        result = engine._adapt_signals_to_weights(signals)
        assert abs(result["USDBRL"] - 0.3) < 1e-9

    def test_adapt_empty_list(self):
        """Empty list returns {}."""
        engine = self._get_adapter()
        result = engine._adapt_signals_to_weights([])
        assert result == {}

    def test_adapt_none_returns_empty(self):
        """If generate_signals returns None, adapter returns {}."""
        engine = self._get_adapter()
        result = engine._adapt_signals_to_weights(None)
        assert result == {}


# ---------------------------------------------------------------------------
# Mock strategies for integration tests
# ---------------------------------------------------------------------------
class MockV3Strategy:
    """Mock v3 strategy returning list[StrategySignal] with alternating direction."""

    def __init__(self, strategy_id: str = "MOCK_V3"):
        self.strategy_id = strategy_id
        self._call_count = 0

    def generate_signals(self, as_of_date: date) -> list[StrategySignal]:
        self._call_count += 1
        # Alternate LONG/SHORT each month
        direction = (
            SignalDirection.LONG
            if self._call_count % 2 == 1
            else SignalDirection.SHORT
        )
        return [
            StrategySignal(
                strategy_id=self.strategy_id,
                timestamp=datetime.combine(as_of_date, datetime.min.time()),
                direction=direction,
                strength=SignalStrength.MODERATE,
                confidence=0.7,
                z_score=1.5,
                raw_value=1.5,
                suggested_size=0.3,
                asset_class=AssetClass.FX,
                instruments=["USDBRL"],
                entry_level=5.0,
                stop_loss=4.8,
                take_profit=5.3,
            )
        ]


class MockV2Strategy:
    """Mock v2 strategy returning list[StrategyPosition]."""

    def __init__(self, strategy_id: str = "MOCK_V2"):
        self.strategy_id = strategy_id
        self._call_count = 0

    def generate_signals(self, as_of_date: date) -> list[StrategyPosition]:
        self._call_count += 1
        # Alternate weight sign
        sign = 1.0 if self._call_count % 2 == 1 else -1.0
        return [
            StrategyPosition(
                strategy_id=self.strategy_id,
                instrument="DI_PRE_365",
                weight=sign * 0.25,
                confidence=0.8,
                direction=(
                    SignalDirection.LONG if sign > 0 else SignalDirection.SHORT
                ),
                entry_signal="test",
            )
        ]


class MockDictStrategy:
    """Mock strategy returning dict[str, float] (classic contract)."""

    def __init__(self, strategy_id: str = "MOCK_DICT"):
        self.strategy_id = strategy_id

    def generate_signals(self, as_of_date: date) -> dict[str, float]:
        return {"IBOVESPA": 0.4}


# ---------------------------------------------------------------------------
# Integration tests: non-zero trades
# ---------------------------------------------------------------------------
class TestV3StrategyBacktest:
    """Integration tests proving v3 strategies produce non-zero trades."""

    def test_v3_strategy_backtest_produces_trades(self):
        """BacktestEngine.run() with v3 list[StrategySignal] strategy produces trades."""
        engine = _make_engine(
            start=date(2024, 1, 1),
            end=date(2024, 6, 30),
            freq="monthly",
        )
        strategy = MockV3Strategy()
        result = engine.run(strategy)

        assert isinstance(result, BacktestResult)
        assert result.total_trades > 0, (
            f"Expected non-zero trades, got {result.total_trades}"
        )
        assert result.strategy_id == "MOCK_V3"

    def test_v2_strategy_backtest_produces_trades(self):
        """BacktestEngine.run() with v2 list[StrategyPosition] strategy produces trades."""
        engine = _make_engine(
            start=date(2024, 1, 1),
            end=date(2024, 6, 30),
            freq="monthly",
        )
        strategy = MockV2Strategy()
        result = engine.run(strategy)

        assert isinstance(result, BacktestResult)
        assert result.total_trades > 0, (
            f"Expected non-zero trades, got {result.total_trades}"
        )
        assert result.strategy_id == "MOCK_V2"

    def test_v3_strategy_tearsheet_has_valid_metrics(self):
        """BacktestResult from v3 strategy has finite Sharpe and negative/zero max_drawdown."""
        engine = _make_engine(
            start=date(2024, 1, 1),
            end=date(2024, 6, 30),
            freq="monthly",
        )
        strategy = MockV3Strategy()
        result = engine.run(strategy)

        # Sharpe must be a finite float
        assert np.isfinite(result.sharpe_ratio), (
            f"Sharpe not finite: {result.sharpe_ratio}"
        )
        # max_drawdown must be <= 0 (negative % or zero)
        assert result.max_drawdown <= 0, (
            f"max_drawdown should be <= 0, got {result.max_drawdown}"
        )
        # Equity curve should have entries (at least 2 for meaningful metrics)
        assert len(result.equity_curve) >= 2, (
            f"Expected >= 2 equity points, got {len(result.equity_curve)}"
        )
        # Final equity should be positive
        assert result.final_equity > 0

    def test_portfolio_backtest_mixed_v2_v3(self):
        """run_portfolio with one v2 and one v3 mock strategy produces trades."""
        engine = _make_engine(
            start=date(2024, 1, 1),
            end=date(2024, 6, 30),
            freq="monthly",
        )
        v2 = MockV2Strategy("MIX_V2")
        v3 = MockV3Strategy("MIX_V3")

        portfolio = engine.run_portfolio([v2, v3])

        assert "portfolio_result" in portfolio
        assert "individual_results" in portfolio
        pr = portfolio["portfolio_result"]

        assert isinstance(pr, BacktestResult)
        assert pr.strategy_id == "PORTFOLIO"

        # Individual results should both be present
        assert "MIX_V2" in portfolio["individual_results"]
        assert "MIX_V3" in portfolio["individual_results"]

        # Both individual strategies should have trades (this is the key assertion:
        # v2 and v3 return types are properly adapted, producing actual trades)
        v2_trades = portfolio["individual_results"]["MIX_V2"].total_trades
        v3_trades = portfolio["individual_results"]["MIX_V3"].total_trades
        assert v2_trades > 0, f"Expected v2 trades > 0, got {v2_trades}"
        assert v3_trades > 0, f"Expected v3 trades > 0, got {v3_trades}"

        # Portfolio-level total_trades is the aggregate across individual strategies
        aggregate_trades = v2_trades + v3_trades
        assert aggregate_trades > 0, (
            f"Expected non-zero aggregate trades, got {aggregate_trades}"
        )

        # Portfolio equity curve should exist
        assert len(pr.equity_curve) >= 2

        # Attribution and weights should exist
        assert "attribution" in portfolio
        assert "weights" in portfolio
        assert len(portfolio["weights"]) == 2

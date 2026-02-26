"""Unit tests for backtesting engine -- TESTV2-03.

Tests cover:
- Portfolio: mark-to-market, rebalance with costs, total_equity
- BacktestConfig: frozen dataclass, defaults
- compute_metrics: Sharpe, Sortino, Calmar, max drawdown, win rate, profit factor
- Edge cases: empty equity curve, single month, no trades
"""
from __future__ import annotations

from datetime import date

import pytest

from src.backtesting.engine import BacktestConfig
from src.backtesting.metrics import compute_metrics
from src.backtesting.portfolio import Portfolio

AS_OF = date(2024, 1, 31)
CONFIG = BacktestConfig(
    start_date=date(2024, 1, 1),
    end_date=date(2024, 12, 31),
    initial_capital=1_000_000.0,
    rebalance_frequency="monthly",
    transaction_cost_bps=5.0,
    slippage_bps=2.0,
)


def make_equity_curve(
    n_months: int = 12, monthly_return: float = 0.01, start: date = date(2024, 1, 31)
) -> list[tuple[date, float]]:
    """Build a synthetic equity curve with constant monthly returns."""
    curve = []
    equity = 1_000_000.0
    for i in range(n_months):
        equity *= (1 + monthly_return)
        d = date(start.year, start.month, 28) if i == 0 else date(
            start.year + (start.month + i - 1) // 12,
            (start.month + i - 1) % 12 + 1,
            28,
        )
        curve.append((d, equity))
    return curve


# ---------------------------------------------------------------------------
# Portfolio tests
# ---------------------------------------------------------------------------
class TestPortfolio:
    def test_initial_equity_equals_capital(self):
        p = Portfolio(1_000_000.0)
        assert abs(p.total_equity - 1_000_000.0) < 0.01

    def test_positions_empty_on_init(self):
        p = Portfolio(500_000.0)
        assert p.positions == {}
        assert p.equity_curve == []
        assert p.trade_log == []

    def test_total_equity_is_cash_plus_positions(self):
        p = Portfolio(1_000_000.0)
        p.cash = 600_000.0
        p.positions = {"IBOVESPA": 400_000.0}
        assert abs(p.total_equity - 1_000_000.0) < 0.01

    def test_rebalance_deducts_transaction_costs(self):
        p = Portfolio(1_000_000.0)
        p._rebalance_date = AS_OF
        prices = {"IBOVESPA": 100_000.0}
        p.rebalance({"IBOVESPA": 0.5}, prices, CONFIG)
        expected_notional = 500_000.0
        expected_cost = expected_notional * (5.0 + 2.0) / 10_000  # 7bps = 350
        assert abs(p.positions["IBOVESPA"] - expected_notional) < 1.0
        assert abs(p.cash - (1_000_000.0 - expected_notional - expected_cost)) < 1.0

    def test_rebalance_logs_to_trade_log(self):
        p = Portfolio(1_000_000.0)
        p._rebalance_date = AS_OF
        p.rebalance({"IBOVESPA": 0.5}, {"IBOVESPA": 100_000.0}, CONFIG)
        assert len(p.trade_log) == 1
        assert p.trade_log[0]["ticker"] == "IBOVESPA"
        assert p.trade_log[0]["direction"] == "BUY"
        assert p.trade_log[0]["cost"] > 0

    def test_rebalance_enforces_max_leverage(self):
        """Total weight 2.0 with max_leverage=1.0 -> weights scaled to 0.5 each."""
        p = Portfolio(1_000_000.0)
        p._rebalance_date = AS_OF
        config_2x = BacktestConfig(
            start_date=date(2024, 1, 1), end_date=date(2024, 12, 31),
            initial_capital=1_000_000.0, max_leverage=1.0
        )
        # weights sum to 2.0 -- should be scaled to 1.0
        p.rebalance({"A": 1.0, "B": 1.0}, {"A": 1.0, "B": 1.0}, config_2x)
        total_notional = sum(abs(v) for v in p.positions.values())
        assert total_notional <= 1_000_000.0 * 1.01  # within 1% of max_leverage * equity

    def test_rebalance_exits_removed_tickers(self):
        """Ticker in positions but not in target_weights -> position zeroed."""
        p = Portfolio(1_000_000.0)
        p.positions = {"OLD_TICKER": 200_000.0}
        p.cash = 800_000.0
        p._rebalance_date = AS_OF
        # New rebalance doesn't include OLD_TICKER
        p.rebalance({"IBOVESPA": 0.3}, {"IBOVESPA": 100_000.0, "OLD_TICKER": 100_000.0}, CONFIG)
        assert p.positions.get("OLD_TICKER", 0.0) == 0.0

    def test_mark_to_market_updates_position_value(self):
        """Position doubles when price doubles."""
        p = Portfolio(1_000_000.0)
        p.cash = 500_000.0
        p.positions = {"IBOVESPA": 500_000.0}
        p._entry_prices = {"IBOVESPA": 100_000.0}
        p.mark_to_market({"IBOVESPA": 200_000.0})  # price doubled
        # Position notional should double
        assert abs(p.positions["IBOVESPA"] - 1_000_000.0) < 1.0


# ---------------------------------------------------------------------------
# BacktestConfig tests
# ---------------------------------------------------------------------------
class TestBacktestConfig:
    def test_default_costs(self):
        c = BacktestConfig(date(2024, 1, 1), date(2024, 12, 31), 1e6)
        assert c.transaction_cost_bps == 5.0
        assert c.slippage_bps == 2.0
        assert c.max_leverage == 1.0
        assert c.rebalance_frequency == "monthly"

    def test_frozen_dataclass(self):
        c = BacktestConfig(date(2024, 1, 1), date(2024, 12, 31), 1e6)
        with pytest.raises((AttributeError, TypeError)):
            c.initial_capital = 2e6  # type: ignore[misc]


# ---------------------------------------------------------------------------
# compute_metrics tests
# ---------------------------------------------------------------------------
class TestComputeMetrics:
    def _make_portfolio_with_curve(self, n: int = 12, ret: float = 0.01) -> Portfolio:
        p = Portfolio(1_000_000.0)
        p.equity_curve = make_equity_curve(n, ret)
        return p

    def test_positive_sharpe_for_positive_returns(self):
        p = self._make_portfolio_with_curve(12, 0.01)
        result = compute_metrics(p, CONFIG, "TEST")
        assert result.sharpe_ratio > 0, f"Sharpe={result.sharpe_ratio}"

    def test_zero_drawdown_for_monotonic_equity(self):
        p = self._make_portfolio_with_curve(12, 0.01)
        result = compute_metrics(p, CONFIG, "TEST")
        assert result.max_drawdown == 0.0, f"Max DD={result.max_drawdown}"

    def test_negative_drawdown_for_declining_equity(self):
        p = Portfolio(1_000_000.0)
        # Equity peaks then drops
        p.equity_curve = [
            (date(2024, 1, 31), 1_100_000.0),
            (date(2024, 2, 29), 1_000_000.0),  # -9.1% drawdown
            (date(2024, 3, 31), 1_050_000.0),
        ]
        result = compute_metrics(p, CONFIG, "TEST")
        assert result.max_drawdown < 0, f"Expected negative max_dd, got {result.max_drawdown}"

    def test_total_return_positive_for_positive_curve(self):
        p = self._make_portfolio_with_curve(12, 0.02)
        result = compute_metrics(p, CONFIG, "TEST")
        assert result.total_return > 0

    def test_empty_equity_curve_returns_zeros(self):
        p = Portfolio(1_000_000.0)
        result = compute_metrics(p, CONFIG, "TEST")
        assert result.sharpe_ratio == 0.0
        assert result.total_return == 0.0

    def test_monthly_returns_dict_keys_format(self):
        p = self._make_portfolio_with_curve(12, 0.01)
        result = compute_metrics(p, CONFIG, "TEST")
        for k in result.monthly_returns:
            assert len(k) == 7 and "-" in k, f"Bad key format: {k}"

    def test_short_backtest_empty_monthly_returns(self):
        """Single equity point -> empty monthly_returns."""
        p = Portfolio(1_000_000.0)
        p.equity_curve = [(date(2024, 1, 31), 1_010_000.0)]
        result = compute_metrics(p, CONFIG, "TEST")
        assert result.monthly_returns == {}

    def test_win_rate_from_trade_log(self):
        p = Portfolio(1_000_000.0)
        p.equity_curve = make_equity_curve(12, 0.005)
        p.trade_log = [
            {"pnl": 1000.0},
            {"pnl": 2000.0},
            {"pnl": -500.0},
            {"pnl": 1500.0},
        ]
        result = compute_metrics(p, CONFIG, "TEST")
        assert abs(result.win_rate - 0.75) < 0.01  # 3 wins out of 4

    def test_profit_factor_from_trade_log(self):
        p = Portfolio(1_000_000.0)
        p.equity_curve = make_equity_curve(12, 0.005)
        p.trade_log = [{"pnl": 4500.0}, {"pnl": -1500.0}]  # PF = 4500/1500 = 3.0
        result = compute_metrics(p, CONFIG, "TEST")
        assert abs(result.profit_factor - 3.0) < 0.01

    def test_zero_profit_factor_when_no_losses(self):
        p = Portfolio(1_000_000.0)
        p.equity_curve = make_equity_curve(12, 0.01)
        p.trade_log = [{"pnl": 1000.0}, {"pnl": 2000.0}]  # no losses
        result = compute_metrics(p, CONFIG, "TEST")
        assert result.profit_factor == 0.0  # no gross_loss -> 0.0

    def test_backtest_result_strategy_id(self):
        p = self._make_portfolio_with_curve()
        result = compute_metrics(p, CONFIG, "MY_STRATEGY")
        assert result.strategy_id == "MY_STRATEGY"

    def test_annualized_return_reasonable(self):
        """12 months at 1%/month -> ~12.7% annualized."""
        p = self._make_portfolio_with_curve(12, 0.01)
        result = compute_metrics(p, CONFIG, "TEST")
        assert 10.0 < result.annualized_return < 16.0, f"Ann return: {result.annualized_return}"

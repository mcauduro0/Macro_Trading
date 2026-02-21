"""BacktestEngine and BacktestConfig for event-driven backtesting.

Point-in-time correctness is enforced by PointInTimeDataLoader:
strategy.generate_signals(as_of_date) calls loader.get_*() methods
which filter by release_time <= as_of_date. BacktestEngine passes
as_of_date to strategy -- no future data can leak in.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

import pandas as pd

from src.backtesting.portfolio import Portfolio
from src.agents.data_loader import PointInTimeDataLoader

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BacktestConfig:
    """Immutable configuration for a backtest run."""
    start_date: date
    end_date: date
    initial_capital: float
    rebalance_frequency: str = "monthly"    # "daily", "weekly", "monthly"
    transaction_cost_bps: float = 5.0       # bps round-trip per trade
    slippage_bps: float = 2.0               # bps per trade
    max_leverage: float = 1.0               # max sum(abs(weights))


class StrategyProtocol(Protocol):
    """Protocol that all strategies must satisfy for BacktestEngine."""
    strategy_id: str

    def generate_signals(self, as_of_date: date) -> dict[str, float]:
        """Return {ticker: target_weight} for the given as_of_date.

        Only data with release_time <= as_of_date may be accessed.
        """
        ...


class BacktestEngine:
    """Event-driven backtesting engine with PIT enforcement.

    Iterates business-day rebalance dates from config.start_date to
    config.end_date, calling strategy.generate_signals(as_of_date) at
    each step. PIT correctness is guaranteed by PointInTimeDataLoader
    enforcing release_time <= as_of_date in all database queries.

    Usage:
        config = BacktestConfig(start_date=..., end_date=..., initial_capital=1_000_000.0)
        engine = BacktestEngine(config, loader)
        result = engine.run(strategy)
    """

    def __init__(self, config: BacktestConfig, loader: PointInTimeDataLoader) -> None:
        self.config = config
        self.loader = loader
        self._last_known_prices: dict[str, float] = {}  # price cache for gap filling

    def run(self, strategy: StrategyProtocol) -> Any:
        """Execute the full backtest for a strategy.

        Returns BacktestRawResult with equity curve. Metrics are computed
        by calling compute_metrics() from src.backtesting.metrics -- but
        BacktestEngine.run() returns a BacktestRawResult with equity_curve and
        trade_log populated; metrics are computed in Plan 10-03.

        For Plan 10-02, return a namedtuple containing portfolio and config so
        Plan 10-03 can add compute_metrics(). Defines a simple BacktestRawResult
        namedtuple here:

        BacktestRawResult(strategy_id, config, portfolio, rebalance_dates)

        Plan 10-03 replaces this with the full BacktestResult dataclass.
        """
        from collections import namedtuple
        BacktestRawResult = namedtuple(
            "BacktestRawResult", ["strategy_id", "config", "portfolio", "rebalance_dates"]
        )

        portfolio = Portfolio(initial_capital=self.config.initial_capital)
        rebalance_dates = self._get_rebalance_dates()

        logger.info(
            "backtest_starting strategy_id=%s start=%s end=%s n_rebalance_dates=%d",
            strategy.strategy_id,
            str(self.config.start_date),
            str(self.config.end_date),
            len(rebalance_dates),
        )

        for as_of_date in rebalance_dates:
            try:
                # PIT: strategy sees only data with release_time <= as_of_date
                # (enforced inside strategy.generate_signals via PointInTimeDataLoader)
                target_weights = strategy.generate_signals(as_of_date)

                # Get current prices (PIT enforced by loader)
                prices = self._get_prices(as_of_date, list(target_weights.keys()))

                # Mark-to-market at current prices
                if prices:
                    portfolio.mark_to_market(prices)

                # Apply rebalance with costs (sets _rebalance_date on portfolio)
                portfolio._rebalance_date = as_of_date
                portfolio.rebalance(target_weights, prices, self.config)

                # Record equity
                portfolio.equity_curve.append((as_of_date, portfolio.total_equity))

            except Exception as exc:
                logger.warning(
                    "backtest_step_failed as_of_date=%s error=%s",
                    str(as_of_date),
                    str(exc),
                )

        logger.info(
            "backtest_complete strategy_id=%s n_equity_points=%d final_equity=%.2f",
            strategy.strategy_id,
            len(portfolio.equity_curve),
            portfolio.equity_curve[-1][1] if portfolio.equity_curve else 0.0,
        )

        return BacktestRawResult(
            strategy_id=strategy.strategy_id,
            config=self.config,
            portfolio=portfolio,
            rebalance_dates=rebalance_dates,
        )

    def _get_rebalance_dates(self) -> list[date]:
        """Generate rebalance dates based on config.rebalance_frequency."""
        all_bdays = pd.bdate_range(
            start=self.config.start_date, end=self.config.end_date, freq="B"
        )
        if self.config.rebalance_frequency == "daily":
            return [d.date() for d in all_bdays]
        elif self.config.rebalance_frequency == "weekly":
            weekly = all_bdays.to_frame().resample("W").last()
            return [d.date() for d in weekly.index]
        elif self.config.rebalance_frequency == "monthly":
            monthly = all_bdays.to_frame().resample("ME").last()
            return [d.date() for d in monthly.index]
        else:
            raise ValueError(
                f"Unknown rebalance_frequency: {self.config.rebalance_frequency!r}. "
                "Use 'daily', 'weekly', or 'monthly'."
            )

    def _get_prices(self, as_of_date: date, tickers: list[str]) -> dict[str, float]:
        """Fetch PIT prices for tickers, falling back to last known price on gaps.

        Args:
            as_of_date: Reference date (PIT enforced by loader).
            tickers: List of ticker strings.

        Returns:
            {ticker: price} dict. Missing tickers use last known price if available.
        """
        prices: dict[str, float] = {}
        for ticker in tickers:
            try:
                df = self.loader.get_market_data(ticker, as_of_date, lookback_days=5)
                if df is not None and not df.empty and "close" in df.columns:
                    last_price = float(df["close"].dropna().iloc[-1])
                    if last_price > 0:
                        prices[ticker] = last_price
                        self._last_known_prices[ticker] = last_price
                elif ticker in self._last_known_prices:
                    prices[ticker] = self._last_known_prices[ticker]
            except Exception:
                if ticker in self._last_known_prices:
                    prices[ticker] = self._last_known_prices[ticker]
        return prices

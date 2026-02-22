"""BacktestEngine and BacktestConfig for event-driven backtesting.

Point-in-time correctness is enforced by PointInTimeDataLoader:
strategy.generate_signals(as_of_date) calls loader.get_*() methods
which filter by release_time <= as_of_date. BacktestEngine passes
as_of_date to strategy -- no future data can leak in.

v2 additions (BTST-01, BTST-02):
- run_portfolio: Multi-strategy portfolio backtesting with weights and attribution
- walk_forward_validation: Train/test window splitting with overfit detection
- BacktestConfig: New optional fields for walk-forward and cost model
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional, Protocol

import numpy as np
import pandas as pd

from src.backtesting.portfolio import Portfolio
from src.backtesting.metrics import BacktestResult, compute_metrics
from src.backtesting.costs import TransactionCostModel
from src.agents.data_loader import PointInTimeDataLoader
from src.strategies.base import StrategySignal, StrategyPosition
from src.core.enums import SignalDirection

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BacktestConfig:
    """Immutable configuration for a backtest run.

    v2 additions: walk_forward, walk_forward_train_months,
    walk_forward_test_months, funding_rate, point_in_time, cost_model.
    All new fields have defaults that preserve backward compatibility.
    """
    start_date: date
    end_date: date
    initial_capital: float
    rebalance_frequency: str = "monthly"    # "daily", "weekly", "monthly"
    transaction_cost_bps: float = 5.0       # bps round-trip per trade
    slippage_bps: float = 2.0               # bps per trade
    max_leverage: float = 1.0               # max sum(abs(weights))
    # v2 additions
    walk_forward: bool = False
    walk_forward_train_months: int = 60
    walk_forward_test_months: int = 12
    funding_rate: float = 0.05
    point_in_time: bool = True
    cost_model: Optional[TransactionCostModel] = None


class StrategyProtocol(Protocol):
    """Protocol that all strategies must satisfy for BacktestEngine.

    The canonical return type of ``generate_signals`` is ``dict[str, float]``,
    but BacktestEngine also accepts ``list[StrategyPosition]`` (v2 strategies)
    and ``list[StrategySignal]`` (v3 strategies) via its internal
    ``_adapt_signals_to_weights`` adapter.  The Protocol signature is kept as
    ``dict[str, float]`` for backward compatibility.
    """
    strategy_id: str

    def generate_signals(self, as_of_date: date) -> dict[str, float]:
        """Return {ticker: target_weight} for the given as_of_date.

        Only data with release_time <= as_of_date may be accessed.

        v3 note: Strategies may also return ``list[StrategySignal]`` or
        ``list[StrategyPosition]``; BacktestEngine converts them internally.
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

        Iterates rebalance dates, calling strategy.generate_signals() at each
        step. After the loop, computes all financial metrics via compute_metrics()
        and returns a BacktestResult dataclass with 10 metrics populated.

        Returns:
            BacktestResult with equity curve, trade statistics, and risk metrics.
        """
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
                raw_signals = strategy.generate_signals(as_of_date)
                target_weights = self._adapt_signals_to_weights(raw_signals)

                if not target_weights:
                    # No signal for this date -- record equity and continue
                    portfolio.equity_curve.append((as_of_date, portfolio.total_equity))
                    continue

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

        return compute_metrics(portfolio, self.config, strategy.strategy_id)

    def _adapt_signals_to_weights(self, raw: Any) -> dict[str, float]:
        """Convert strategy output to ``{ticker: target_weight}`` dict.

        Handles three return types from ``generate_signals()``:

        1. ``dict[str, float]``: Returned as-is (existing StrategyProtocol).
        2. ``list[StrategyPosition]``: Extracts ``{pos.instrument: pos.weight}``.
        3. ``list[StrategySignal]``: Extracts signed size per instrument.
           LONG -> +suggested_size, SHORT -> -suggested_size, NEUTRAL -> 0.0.
           Multiple signals targeting the same instrument are summed.
        4. ``None`` or empty list: Returns ``{}``.

        Args:
            raw: Return value of ``strategy.generate_signals()``.

        Returns:
            Target weights dict suitable for ``Portfolio.rebalance()``.
        """
        if raw is None:
            return {}

        if isinstance(raw, dict):
            return raw

        if isinstance(raw, list):
            if len(raw) == 0:
                return {}

            first = raw[0]

            # list[StrategySignal] detection: has .instruments and .suggested_size
            if hasattr(first, "instruments") and hasattr(first, "suggested_size"):
                weights: dict[str, float] = {}
                for signal in raw:
                    size = signal.suggested_size
                    if signal.direction == SignalDirection.SHORT:
                        size = -size
                    elif signal.direction == SignalDirection.NEUTRAL:
                        size = 0.0
                    for instrument in signal.instruments:
                        weights[instrument] = weights.get(instrument, 0.0) + size
                return weights

            # list[StrategyPosition] detection: has .instrument and .weight
            if hasattr(first, "instrument") and hasattr(first, "weight"):
                return {pos.instrument: pos.weight for pos in raw}

        # Fallback: attempt to use as-is (will fail at .keys() if invalid,
        # caught by the outer try/except in run())
        return raw

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

    # ------------------------------------------------------------------
    # v2: Portfolio-level backtesting (BTST-01)
    # ------------------------------------------------------------------
    def run_portfolio(
        self,
        strategies: list[StrategyProtocol],
        weights: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Run multi-strategy portfolio backtest with attribution.

        Executes ``self.run()`` for each strategy, combines equity curves
        using the given weights, computes correlation and attribution.

        Args:
            strategies: List of strategy instances (must satisfy StrategyProtocol).
            weights: Optional {strategy_id: weight} dict.  If ``None``,
                strategies are equally weighted (1/N).

        Returns:
            Dict with keys:
            - ``portfolio_result``: Combined BacktestResult.
            - ``individual_results``: {strategy_id: BacktestResult}.
            - ``weights``: The weights used.
            - ``correlation_matrix``: {(id_a, id_b): correlation}.
            - ``attribution``: {strategy_id: contribution_pct}.
        """
        if not strategies:
            raise ValueError("strategies list must not be empty")

        # Default: equal weight
        if weights is None:
            n = len(strategies)
            weights = {s.strategy_id: 1.0 / n for s in strategies}

        # Run individual backtests
        individual_results: dict[str, BacktestResult] = {}
        for strategy in strategies:
            result = self.run(strategy)
            individual_results[strategy.strategy_id] = result

        # Build daily returns per strategy from equity curves
        strategy_returns: dict[str, pd.Series] = {}
        for sid, result in individual_results.items():
            if len(result.equity_curve) < 2:
                continue
            dates = [pd.Timestamp(d) for d, _ in result.equity_curve]
            equities = pd.Series(
                [e for _, e in result.equity_curve], index=dates
            )
            strategy_returns[sid] = equities.pct_change().dropna()

        # Combine equity curves: weighted sum of individual equity series
        equity_series_dict: dict[str, pd.Series] = {}
        for sid, result in individual_results.items():
            if len(result.equity_curve) >= 2:
                dates = [pd.Timestamp(d) for d, _ in result.equity_curve]
                equity_series_dict[sid] = pd.Series(
                    [e for _, e in result.equity_curve], index=dates
                )

        if equity_series_dict:
            # Align all equity series to a common date index
            equity_df = pd.DataFrame(equity_series_dict)
            equity_df = equity_df.ffill().bfill()

            # Portfolio equity = sum of weighted individual equities
            portfolio_equity = pd.Series(0.0, index=equity_df.index)
            for sid in equity_df.columns:
                w = weights.get(sid, 0.0)
                portfolio_equity += equity_df[sid] * w

            # Combined equity curve as list of (date, equity)
            combined_curve = [
                (d.date(), float(e))
                for d, e in portfolio_equity.items()
            ]

            # Compute combined metrics via Portfolio + compute_metrics
            combined_portfolio = Portfolio(
                initial_capital=self.config.initial_capital
            )
            combined_portfolio.equity_curve = combined_curve

            # Aggregate trade statistics
            total_trades = sum(
                r.total_trades for r in individual_results.values()
            )
            combined_portfolio.trade_log = []
            for r in individual_results.values():
                # Add synthetic trade log entries for aggregate stats
                if r.total_trades > 0 and r.win_rate > 0:
                    wins = int(r.total_trades * r.win_rate)
                    for _ in range(wins):
                        combined_portfolio.trade_log.append({"pnl": 1.0})
                    for _ in range(r.total_trades - wins):
                        combined_portfolio.trade_log.append({"pnl": -1.0})

            portfolio_result = compute_metrics(
                combined_portfolio, self.config, "PORTFOLIO"
            )
        else:
            # No valid equity curves
            portfolio_result = BacktestResult(
                strategy_id="PORTFOLIO",
                start_date=self.config.start_date,
                end_date=self.config.end_date,
                initial_capital=self.config.initial_capital,
                final_equity=self.config.initial_capital,
                total_return=0.0,
                annualized_return=0.0,
                annualized_volatility=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                calmar_ratio=0.0,
                max_drawdown=0.0,
                win_rate=0.0,
                profit_factor=0.0,
                total_trades=0,
                monthly_returns={},
                equity_curve=[],
            )
            combined_curve = []

        # Correlation matrix
        correlation_matrix: dict[tuple[str, str], float] = {}
        if len(strategy_returns) >= 2:
            returns_df = pd.DataFrame(strategy_returns)
            returns_df = returns_df.dropna()
            if len(returns_df) > 1:
                corr = returns_df.corr()
                for id_a in corr.columns:
                    for id_b in corr.columns:
                        correlation_matrix[(id_a, id_b)] = float(
                            corr.loc[id_a, id_b]
                        )

        # Attribution: each strategy's weighted contribution to total return
        attribution: dict[str, float] = {}
        total_weighted_return = sum(
            individual_results[sid].total_return * weights.get(sid, 0.0)
            for sid in individual_results
        )
        for sid, result in individual_results.items():
            w = weights.get(sid, 0.0)
            if abs(total_weighted_return) > 1e-8:
                attribution[sid] = (
                    result.total_return * w / total_weighted_return
                )
            else:
                attribution[sid] = w  # fallback: just the weight

        logger.info(
            "portfolio_backtest_complete n_strategies=%d total_return=%.2f%%",
            len(strategies),
            portfolio_result.total_return,
        )

        return {
            "portfolio_result": portfolio_result,
            "individual_results": individual_results,
            "weights": weights,
            "correlation_matrix": correlation_matrix,
            "attribution": attribution,
        }

    # ------------------------------------------------------------------
    # v2: Walk-forward validation (BTST-02)
    # ------------------------------------------------------------------
    def walk_forward_validation(
        self,
        strategy: StrategyProtocol,
        param_grid: dict[str, list] | None = None,
    ) -> list[dict[str, Any]]:
        """Walk-forward validation with train/test window splitting.

        Slides a rolling window across the backtest period to evaluate
        in-sample vs out-of-sample performance.  Useful for detecting
        overfitting (overfit ratio = mean OOS Sharpe / mean IS Sharpe;
        ratio < 0.5 suggests overfitting).

        Args:
            strategy: Strategy instance to validate.
            param_grid: Optional parameter grid for optimization.
                Each key is a strategy attribute, each value a list of
                candidates.  If provided, the best Sharpe params on the
                training window are used for the test window.

        Returns:
            List of dicts, one per window, with keys:
            window, train_start, train_end, test_start, test_end,
            in_sample_sharpe, out_of_sample_sharpe, in_sample_result,
            out_of_sample_result, params_used.
        """
        train_months = self.config.walk_forward_train_months
        test_months = self.config.walk_forward_test_months

        # Generate windows
        windows = self._generate_wf_windows(
            self.config.start_date,
            self.config.end_date,
            train_months,
            test_months,
        )

        if not windows:
            logger.warning(
                "walk_forward_no_windows period too short for "
                "train=%d test=%d months",
                train_months,
                test_months,
            )
            return []

        results: list[dict[str, Any]] = []
        is_sharpes: list[float] = []
        oos_sharpes: list[float] = []

        for i, (train_start, train_end, test_start, test_end) in enumerate(
            windows
        ):
            params_used: dict[str, Any] = {}

            if param_grid:
                # Grid search on training window
                best_sharpe = -float("inf")
                best_params: dict[str, Any] = {}

                import itertools

                param_names = list(param_grid.keys())
                param_values = list(param_grid.values())

                for combo in itertools.product(*param_values):
                    trial_params = dict(zip(param_names, combo))
                    # Apply params to strategy
                    for k, v in trial_params.items():
                        setattr(strategy, k, v)

                    train_config = BacktestConfig(
                        start_date=train_start,
                        end_date=train_end,
                        initial_capital=self.config.initial_capital,
                        rebalance_frequency=self.config.rebalance_frequency,
                        transaction_cost_bps=self.config.transaction_cost_bps,
                        slippage_bps=self.config.slippage_bps,
                        max_leverage=self.config.max_leverage,
                    )
                    train_engine = BacktestEngine(train_config, self.loader)
                    train_result = train_engine.run(strategy)

                    if train_result.sharpe_ratio > best_sharpe:
                        best_sharpe = train_result.sharpe_ratio
                        best_params = trial_params.copy()

                # Apply best params for test
                for k, v in best_params.items():
                    setattr(strategy, k, v)
                params_used = best_params
            else:
                # No param grid: run with current params
                train_config = BacktestConfig(
                    start_date=train_start,
                    end_date=train_end,
                    initial_capital=self.config.initial_capital,
                    rebalance_frequency=self.config.rebalance_frequency,
                    transaction_cost_bps=self.config.transaction_cost_bps,
                    slippage_bps=self.config.slippage_bps,
                    max_leverage=self.config.max_leverage,
                )
                train_engine = BacktestEngine(train_config, self.loader)

            # Run train (in-sample)
            train_config = BacktestConfig(
                start_date=train_start,
                end_date=train_end,
                initial_capital=self.config.initial_capital,
                rebalance_frequency=self.config.rebalance_frequency,
                transaction_cost_bps=self.config.transaction_cost_bps,
                slippage_bps=self.config.slippage_bps,
                max_leverage=self.config.max_leverage,
            )
            train_engine = BacktestEngine(train_config, self.loader)
            in_sample_result = train_engine.run(strategy)

            # Run test (out-of-sample)
            test_config = BacktestConfig(
                start_date=test_start,
                end_date=test_end,
                initial_capital=self.config.initial_capital,
                rebalance_frequency=self.config.rebalance_frequency,
                transaction_cost_bps=self.config.transaction_cost_bps,
                slippage_bps=self.config.slippage_bps,
                max_leverage=self.config.max_leverage,
            )
            test_engine = BacktestEngine(test_config, self.loader)
            oos_result = test_engine.run(strategy)

            is_sharpes.append(in_sample_result.sharpe_ratio)
            oos_sharpes.append(oos_result.sharpe_ratio)

            results.append({
                "window": i,
                "train_start": train_start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
                "in_sample_sharpe": in_sample_result.sharpe_ratio,
                "out_of_sample_sharpe": oos_result.sharpe_ratio,
                "in_sample_result": in_sample_result,
                "out_of_sample_result": oos_result,
                "params_used": params_used,
            })

            logger.info(
                "walk_forward_window window=%d is_sharpe=%.2f oos_sharpe=%.2f",
                i,
                in_sample_result.sharpe_ratio,
                oos_result.sharpe_ratio,
            )

        # Log overfit ratio
        mean_is = np.mean(is_sharpes) if is_sharpes else 0.0
        mean_oos = np.mean(oos_sharpes) if oos_sharpes else 0.0
        if abs(mean_is) > 1e-8:
            overfit_ratio = mean_oos / mean_is
        else:
            overfit_ratio = 0.0

        logger.info(
            "walk_forward_complete n_windows=%d mean_is_sharpe=%.2f "
            "mean_oos_sharpe=%.2f overfit_ratio=%.2f%s",
            len(results),
            float(mean_is),
            float(mean_oos),
            float(overfit_ratio),
            " WARNING:OVERFITTING" if overfit_ratio < 0.5 else "",
        )

        return results

    @staticmethod
    def _generate_wf_windows(
        start: date,
        end: date,
        train_months: int,
        test_months: int,
    ) -> list[tuple[date, date, date, date]]:
        """Generate walk-forward train/test windows.

        Slides by test_months each step.  Returns list of
        (train_start, train_end, test_start, test_end) tuples.

        Args:
            start: Overall backtest start date.
            end: Overall backtest end date.
            train_months: Training window length in months.
            test_months: Test window length in months.

        Returns:
            List of (train_start, train_end, test_start, test_end) tuples.
        """
        windows: list[tuple[date, date, date, date]] = []
        current_train_start = start

        while True:
            # Compute window boundaries using pd.DateOffset
            train_end_ts = pd.Timestamp(current_train_start) + pd.DateOffset(
                months=train_months
            )
            test_start_ts = train_end_ts
            test_end_ts = test_start_ts + pd.DateOffset(months=test_months)

            train_end = train_end_ts.date()
            test_start = test_start_ts.date()
            test_end = test_end_ts.date()

            # Stop if test window exceeds overall end
            if test_end > end:
                break

            windows.append((current_train_start, train_end, test_start, test_end))

            # Advance by test_months
            next_start_ts = pd.Timestamp(current_train_start) + pd.DateOffset(
                months=test_months
            )
            current_train_start = next_start_ts.date()

        return windows

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

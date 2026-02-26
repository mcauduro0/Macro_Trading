"""Metrics computation for backtest results.

All metrics computed using numpy and pandas only -- no external library.
BacktestResult is a dataclass (NOT frozen -- allows optional field population).
Persistence uses the same sync session pattern as AgentReportRecord.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """Complete backtest result with all financial metrics.

    All percentage values stored as % (e.g., 12.5 means 12.5%, not 0.125).
    max_drawdown is a negative % (e.g., -15.3 means -15.3% drawdown).
    """
    strategy_id: str
    start_date: date
    end_date: date
    initial_capital: float
    final_equity: float

    # Return metrics
    total_return: float          # %
    annualized_return: float     # %
    annualized_volatility: float # %

    # Risk-adjusted metrics
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float

    # Drawdown
    max_drawdown: float          # negative % (e.g., -15.3)

    # Trade statistics
    win_rate: float              # fraction [0, 1]
    profit_factor: float         # gross_profit / abs(gross_loss); 0.0 if no losses
    total_trades: int

    # Time series
    monthly_returns: dict        # {"YYYY-MM": return_pct}
    equity_curve: list[tuple[date, float]]  # [(date, equity)]


def compute_metrics(portfolio: Any, config: Any, strategy_id: str) -> BacktestResult:
    """Compute all financial metrics from portfolio equity curve and trade log.

    Args:
        portfolio: Portfolio instance from Plan 10-02 (has equity_curve, trade_log).
        config: BacktestConfig instance (has start_date, end_date, initial_capital).
        strategy_id: Identifier string for the strategy.

    Returns:
        BacktestResult with all 10 metrics populated.
    """
    equity_data = portfolio.equity_curve  # list of (date, float)

    if len(equity_data) < 2:
        # Degenerate case: no meaningful run
        return BacktestResult(
            strategy_id=strategy_id,
            start_date=config.start_date,
            end_date=config.end_date,
            initial_capital=config.initial_capital,
            final_equity=config.initial_capital,
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
            equity_curve=equity_data,
        )

    # Build equity Series with DatetimeIndex
    dates = [pd.Timestamp(d) for d, _ in equity_data]
    equities = [e for _, e in equity_data]
    equity = pd.Series(equities, index=dates)
    equity = equity[equity > 0]  # guard against zero/negative equity

    if len(equity) < 2:
        return _empty_result(strategy_id, config, equity_data)

    # --- Core return metrics ---
    n_years = max(
        (config.end_date - config.start_date).days / 365.25, 1 / 365.25
    )
    total_return_pct = (equity.iloc[-1] / equity.iloc[0] - 1) * 100
    ann_return_pct = ((1 + total_return_pct / 100) ** (1 / n_years) - 1) * 100

    # Daily/periodic returns
    returns = equity.pct_change().dropna()
    # Infer annualization factor from rebalance frequency
    if config.rebalance_frequency == "daily":
        ann_factor = 252
    elif config.rebalance_frequency == "weekly":
        ann_factor = 52
    else:  # monthly
        ann_factor = 12

    ann_vol_pct = float(returns.std() * np.sqrt(ann_factor) * 100) if len(returns) > 1 else 0.0

    # --- Sharpe (risk-free = 0 for simplicity) ---
    # When volatility is zero: positive returns -> large positive Sharpe (capped);
    # zero returns -> 0.0
    if ann_vol_pct > 1e-8:
        sharpe = ann_return_pct / ann_vol_pct
    elif ann_return_pct > 1e-8:
        sharpe = 99.99  # zero-vol positive returns -> effectively infinite Sharpe
    else:
        sharpe = 0.0

    # --- Sortino (downside deviation only) ---
    downside = returns[returns < 0]
    if len(downside) > 1:
        sortino_denom = float(downside.std() * np.sqrt(ann_factor) * 100)
        sortino = (ann_return_pct / sortino_denom) if sortino_denom > 1e-8 else 0.0
    else:
        # No downside returns: positive returns -> use Sharpe as proxy
        sortino = sharpe

    # --- Max drawdown ---
    rolling_max = equity.expanding().max()
    drawdown_series = equity / rolling_max - 1
    max_dd_pct = float(drawdown_series.min()) * 100  # negative number
    # Guard: monotonically increasing equity -> drawdown = 0
    if max_dd_pct > 0:
        max_dd_pct = 0.0

    # --- Calmar ---
    calmar = (ann_return_pct / abs(max_dd_pct)) if max_dd_pct < -1e-8 else 0.0

    # --- Monthly returns ---
    try:
        monthly = equity.resample("ME").last().pct_change().dropna()
        if len(monthly) < 2:
            monthly_dict: dict = {}
        else:
            monthly_dict = {
                str(d.date())[:7]: round(float(v) * 100, 4)
                for d, v in monthly.items()
            }
    except Exception:
        monthly_dict = {}

    # --- Trade statistics from trade_log ---
    trade_pnls = [t.get("pnl", 0.0) for t in portfolio.trade_log if "pnl" in t]
    wins = [p for p in trade_pnls if p > 0]
    losses = [p for p in trade_pnls if p <= 0]
    total_trades = len(trade_pnls)
    win_rate = len(wins) / total_trades if total_trades > 0 else 0.0
    gross_loss = abs(sum(losses))
    profit_factor = (sum(wins) / gross_loss) if gross_loss > 1e-8 else 0.0

    return BacktestResult(
        strategy_id=strategy_id,
        start_date=config.start_date,
        end_date=config.end_date,
        initial_capital=config.initial_capital,
        final_equity=float(equity.iloc[-1]),
        total_return=round(float(total_return_pct), 4),
        annualized_return=round(float(ann_return_pct), 4),
        annualized_volatility=round(float(ann_vol_pct), 4),
        sharpe_ratio=round(float(sharpe), 4),
        sortino_ratio=round(float(sortino), 4),
        calmar_ratio=round(float(calmar), 4),
        max_drawdown=round(float(max_dd_pct), 4),
        win_rate=round(float(win_rate), 4),
        profit_factor=round(float(profit_factor), 4),
        total_trades=total_trades,
        monthly_returns=monthly_dict,
        equity_curve=equity_data,
    )


def _empty_result(strategy_id: str, config: Any, equity_data: list) -> BacktestResult:
    return BacktestResult(
        strategy_id=strategy_id,
        start_date=config.start_date,
        end_date=config.end_date,
        initial_capital=config.initial_capital,
        final_equity=config.initial_capital,
        total_return=0.0, annualized_return=0.0, annualized_volatility=0.0,
        sharpe_ratio=0.0, sortino_ratio=0.0, calmar_ratio=0.0,
        max_drawdown=0.0, win_rate=0.0, profit_factor=0.0,
        total_trades=0, monthly_returns={}, equity_curve=equity_data,
    )


def persist_result(result: BacktestResult, sync_session_factory: Any) -> None:
    """Persist a BacktestResult to the backtest_results table.

    Uses the same sync session pattern as AgentReportRecord persistence.
    ON CONFLICT DO NOTHING not applicable here (no unique constraint);
    each call inserts a new row.

    Args:
        result: Computed BacktestResult from compute_metrics().
        sync_session_factory: SQLAlchemy sync sessionmaker factory.
    """
    from src.core.models.backtest_results import BacktestResultRecord

    # Serialize equity curve to JSON-safe list of [date_str, equity] pairs
    equity_curve_json = [
        [str(d), round(e, 2)] for d, e in result.equity_curve
    ]
    config_json = {
        "start_date": str(result.start_date),
        "end_date": str(result.end_date),
        "initial_capital": result.initial_capital,
    }

    record = BacktestResultRecord(
        strategy_id=result.strategy_id,
        start_date=result.start_date,
        end_date=result.end_date,
        initial_capital=result.initial_capital,
        final_equity=result.final_equity,
        total_return=result.total_return,
        annualized_return=result.annualized_return,
        annualized_volatility=result.annualized_volatility,
        sharpe_ratio=result.sharpe_ratio,
        sortino_ratio=result.sortino_ratio,
        calmar_ratio=result.calmar_ratio,
        max_drawdown=result.max_drawdown,
        win_rate=result.win_rate,
        profit_factor=result.profit_factor,
        total_trades=result.total_trades,
        equity_curve=equity_curve_json,
        monthly_returns=result.monthly_returns,
        config_json=config_json,
    )

    with sync_session_factory() as session:
        try:
            session.add(record)
            session.commit()
            logger.info(
                "backtest_result_persisted",
                strategy_id=result.strategy_id,
                sharpe=result.sharpe_ratio,
            )
        except Exception as exc:
            session.rollback()
            logger.error("backtest_result_persist_failed", error=str(exc))
            raise

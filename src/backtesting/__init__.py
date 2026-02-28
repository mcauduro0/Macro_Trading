"""Backtesting engine for strategy validation with point-in-time correctness."""

from src.backtesting.analytics import (
    compute_information_ratio,
    compute_rolling_sharpe,
    compute_sortino,
    compute_tail_ratio,
    compute_turnover,
    deflated_sharpe,
    generate_tearsheet,
)
from src.backtesting.costs import TransactionCostModel
from src.backtesting.engine import BacktestConfig, BacktestEngine
from src.backtesting.metrics import BacktestResult, compute_metrics, persist_result
from src.backtesting.portfolio import Portfolio

__all__ = [
    "BacktestConfig",
    "BacktestEngine",
    "Portfolio",
    "BacktestResult",
    "TransactionCostModel",
    "compute_metrics",
    "persist_result",
    # Analytics (BTST-03, BTST-05, BTST-06)
    "compute_sortino",
    "compute_information_ratio",
    "compute_tail_ratio",
    "compute_turnover",
    "compute_rolling_sharpe",
    "deflated_sharpe",
    "generate_tearsheet",
]

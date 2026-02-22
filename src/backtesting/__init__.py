"""Backtesting engine for strategy validation with point-in-time correctness."""
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
]

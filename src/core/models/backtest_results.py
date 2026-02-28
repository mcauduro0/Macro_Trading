"""Backtest results table -- stores full backtest run results.

Regular PostgreSQL table (NOT a hypertable -- low volume: one row per backtest run).
Equity curve and monthly returns stored as JSONB for flexible querying.

v3.0 additions (SFWK-04):
- run_timestamp: When the backtest was executed
- params_json: Strategy parameters used in this run
- daily_returns_json: Array of daily returns for distribution analysis
- avg_holding_days: Average trade holding period in days
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class BacktestResultRecord(Base):
    """ORM model for the backtest_results table.

    Named BacktestResultRecord (not BacktestResult) to avoid collision
    with the BacktestResult dataclass in src.backtesting.metrics.
    """

    __tablename__ = "backtest_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    initial_capital: Mapped[float] = mapped_column(Float, nullable=False)
    final_equity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_return: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    annualized_return: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    annualized_volatility: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sharpe_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sortino_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    calmar_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    win_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    profit_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_trades: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    equity_curve: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    monthly_returns: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    config_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # v3.0 additions (SFWK-04)
    run_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    params_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    daily_returns_json: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    avg_holding_days: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<BacktestResultRecord("
            f"strategy_id={self.strategy_id!r}, "
            f"start_date={self.start_date}, "
            f"sharpe_ratio={self.sharpe_ratio})>"
        )

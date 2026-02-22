"""Strategy state table -- persists strategy signal snapshots (SFWK-03).

Regular PostgreSQL table (NOT a hypertable) storing one row per strategy
signal evaluation.  Used by the BacktestEngine v2 to track signal history
and by the daily pipeline to persist current strategy states.

Composite index on (strategy_id, timestamp DESC) for efficient
time-series queries per strategy.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class StrategyStateRecord(Base):
    """ORM model for the strategy_state table.

    Stores a snapshot of a strategy's signal output at a given timestamp,
    including direction, strength, confidence, z-score, suggested sizing,
    and optional entry/stop/take-profit levels.
    """

    __tablename__ = "strategy_state"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    strength: Mapped[str] = mapped_column(String(10), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    z_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raw_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    suggested_size: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    instruments: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    entry_level: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    take_profit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    holding_period_days: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_strategy_state_strat_ts",
            "strategy_id",
            timestamp.desc(),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<StrategyStateRecord("
            f"strategy_id={self.strategy_id!r}, "
            f"timestamp={self.timestamp}, "
            f"direction={self.direction!r})>"
        )

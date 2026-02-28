"""Portfolio state table -- persists portfolio positions with strategy attribution.

TimescaleDB hypertable storing one row per (timestamp, instrument) with
notional weight, direction, P&L, and JSON-encoded strategy attribution
for tracing which strategies contributed to each position.

Created by Alembic migration 008.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class PortfolioStateRecord(Base):
    """ORM model for the portfolio_state hypertable.

    Stores a snapshot of a portfolio position at a given timestamp,
    including direction, notional size, weight, P&L, and which
    strategies contributed via strategy_attribution JSON.

    Composite primary key on (id, timestamp) for hypertable compatibility.
    Unique constraint on (timestamp, instrument) as natural key.
    """

    __tablename__ = "portfolio_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    instrument: Mapped[str] = mapped_column(String(50), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    notional: Mapped[float] = mapped_column(Float, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    entry_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unrealized_pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    strategy_attribution: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "timestamp", "instrument", name="uq_portfolio_state_natural_key"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PortfolioStateRecord("
            f"instrument={self.instrument!r}, "
            f"timestamp={self.timestamp}, "
            f"direction={self.direction!r}, "
            f"weight={self.weight})>"
        )

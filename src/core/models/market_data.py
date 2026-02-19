"""Market data hypertable -- OHLCV price/rate time series.

TimescaleDB hypertable partitioned on 'timestamp' with 1-month chunk intervals.
Composite primary key (id, timestamp) as required by TimescaleDB.
Natural key: (instrument_id, timestamp, frequency) for idempotent writes.
Compression: segmentby=instrument_id, orderby=timestamp DESC.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MarketData(Base):
    __tablename__ = "market_data"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    frequency: Mapped[str] = mapped_column(String(20), nullable=False, default="daily")
    open: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    high: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    low: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    close: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    adjusted_close: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "timestamp", "frequency",
            name="uq_market_data_natural_key",
        ),
        Index("ix_market_data_instrument_id", "instrument_id"),
        {"comment": "TimescaleDB hypertable partitioned on timestamp"},
    )

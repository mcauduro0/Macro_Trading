"""Signals hypertable -- trading signal output time series.

TimescaleDB hypertable partitioned on 'signal_date' with 1-year chunk intervals.
Composite primary key (id, signal_date) as required by TimescaleDB.
Natural key: (signal_type, signal_date, instrument_id) for idempotent writes.
Compression: segmentby=signal_type, orderby=signal_date DESC.
"""

from datetime import date
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Date,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    signal_date: Mapped[date] = mapped_column(
        Date, primary_key=True, nullable=False
    )
    instrument_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("instruments.id"), nullable=True
    )
    series_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("series_metadata.id"), nullable=True
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "signal_type", "signal_date", "instrument_id",
            name="uq_signals_natural_key",
        ),
        Index("ix_signals_signal_type", "signal_type"),
        {"comment": "TimescaleDB hypertable partitioned on signal_date"},
    )

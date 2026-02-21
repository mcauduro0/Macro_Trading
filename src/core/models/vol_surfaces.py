"""Vol surface hypertable -- implied volatility surface data.

TimescaleDB hypertable partitioned on 'surface_date' with 1-year chunk intervals.
Composite primary key (id, surface_date) as required by TimescaleDB.
Natural key: (instrument_id, surface_date, delta, tenor_days) for idempotent writes.
Compression: segmentby=instrument_id, orderby=surface_date DESC.
"""

from datetime import date
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class VolSurface(Base):
    __tablename__ = "vol_surfaces"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id"), nullable=False
    )
    surface_date: Mapped[date] = mapped_column(
        Date, primary_key=True, nullable=False
    )
    delta: Mapped[float] = mapped_column(Float, nullable=False)
    tenor_days: Mapped[int] = mapped_column(Integer, nullable=False)
    implied_vol: Mapped[float] = mapped_column(Float, nullable=False)
    call_put: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "surface_date", "delta", "tenor_days",
            name="uq_vol_surfaces_natural_key",
        ),
        Index("ix_vol_surfaces_instrument_id", "instrument_id"),
        {"comment": "TimescaleDB hypertable partitioned on surface_date"},
    )

"""Curves hypertable -- yield curve, swap curve, and breakeven curve data.

TimescaleDB hypertable partitioned on 'curve_date' with 3-month chunk intervals.
Composite primary key (id, curve_date) as required by TimescaleDB.
Natural key: (curve_id, curve_date, tenor_days) for idempotent writes.
Compression: segmentby=curve_id, orderby=curve_date DESC.
"""

from datetime import date
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Date,
    Float,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CurveData(Base):
    __tablename__ = "curves"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    curve_id: Mapped[str] = mapped_column(String(50), nullable=False)
    curve_date: Mapped[date] = mapped_column(
        Date, primary_key=True, nullable=False
    )
    tenor_days: Mapped[int] = mapped_column(Integer, nullable=False)
    tenor_label: Mapped[str] = mapped_column(String(20), nullable=False)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    curve_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "curve_id", "curve_date", "tenor_days",
            name="uq_curves_natural_key",
        ),
        Index("ix_curves_curve_id", "curve_id"),
        {"comment": "TimescaleDB hypertable partitioned on curve_date"},
    )

"""Fiscal data hypertable -- government fiscal metrics time series.

TimescaleDB hypertable partitioned on 'observation_date' with 1-year chunk intervals.
Composite primary key (id, observation_date) as required by TimescaleDB.
Natural key: (series_id, observation_date, fiscal_metric) for idempotent writes.
Compression: segmentby=series_id, orderby=observation_date DESC.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class FiscalData(Base):
    __tablename__ = "fiscal_data"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    series_id: Mapped[int] = mapped_column(
        ForeignKey("series_metadata.id"), nullable=False
    )
    observation_date: Mapped[date] = mapped_column(
        Date, primary_key=True, nullable=False
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    fiscal_metric: Mapped[str] = mapped_column(String(50), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="BRL_MM")
    release_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "series_id", "observation_date", "fiscal_metric",
            name="uq_fiscal_data_natural_key",
        ),
        Index("ix_fiscal_data_series_id", "series_id"),
        {"comment": "TimescaleDB hypertable partitioned on observation_date"},
    )

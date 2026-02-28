"""Macro series hypertable -- economic/macro data with point-in-time correctness.

TimescaleDB hypertable partitioned on 'observation_date' with 1-year chunk intervals.
Composite primary key (id, observation_date) as required by TimescaleDB.
Natural key: (series_id, observation_date, revision_number) for idempotent writes.
Compression: segmentby=series_id, orderby=observation_date DESC.

The release_time column (TIMESTAMPTZ) records when this data point became publicly
available, enabling point-in-time correct backtesting.
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
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MacroSeries(Base):
    __tablename__ = "macro_series"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    series_id: Mapped[int] = mapped_column(
        ForeignKey("series_metadata.id"), nullable=False
    )
    observation_date: Mapped[date] = mapped_column(
        Date, primary_key=True, nullable=False
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    release_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="When this value became known (TIMESTAMPTZ)",
    )
    revision_number: Mapped[int] = mapped_column(SmallInteger, default=0)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "series_id",
            "observation_date",
            "revision_number",
            name="uq_macro_series_natural_key",
        ),
        Index("ix_macro_series_series_id", "series_id"),
        {"comment": "TimescaleDB hypertable partitioned on observation_date"},
    )

"""Flow data hypertable -- FX and capital flow time series.

TimescaleDB hypertable partitioned on 'observation_date' with 1-year chunk intervals.
Composite primary key (id, observation_date) as required by TimescaleDB.
Natural key: (series_id, observation_date, flow_type) for idempotent writes.
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


class FlowData(Base):
    __tablename__ = "flow_data"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    series_id: Mapped[int] = mapped_column(
        ForeignKey("series_metadata.id"), nullable=False
    )
    observation_date: Mapped[date] = mapped_column(
        Date, primary_key=True, nullable=False
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    flow_type: Mapped[str] = mapped_column(String(50), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="USD_MM")
    release_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "series_id",
            "observation_date",
            "flow_type",
            name="uq_flow_data_natural_key",
        ),
        Index("ix_flow_data_series_id", "series_id"),
        {"comment": "TimescaleDB hypertable partitioned on observation_date"},
    )

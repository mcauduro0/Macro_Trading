"""Series metadata table -- registry of all data series with source info.

Regular PostgreSQL table (not a hypertable). Referenced by macro_series,
flow_data, fiscal_data, and signals via foreign keys.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SeriesMetadata(Base):
    __tablename__ = "series_metadata"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("data_sources.id"), nullable=False
    )
    series_code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    country: Mapped[str] = mapped_column(String(10), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    decimal_separator: Mapped[str] = mapped_column(String(5), default=".")
    date_format: Mapped[str] = mapped_column(String(20), default="YYYY-MM-DD")
    is_revisable: Mapped[bool] = mapped_column(default=False)
    release_lag_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    release_timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("source_id", "series_code", name="uq_series_metadata_source_series"),
    )

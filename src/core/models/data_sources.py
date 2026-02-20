"""Data source registry table -- tracks external data providers.

Regular PostgreSQL table (not a hypertable). Referenced by series_metadata
via foreign key. Normalizes provider information (base_url, auth_type,
rate limits, locale) so changes update in one place.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    auth_type: Mapped[str] = mapped_column(String(50), nullable=False)
    rate_limit_per_minute: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    default_locale: Mapped[str] = mapped_column(String(10), default="en-US")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

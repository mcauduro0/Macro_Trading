"""Instrument metadata table -- registry of tradeable instruments.

Regular PostgreSQL table (not a hypertable). Referenced by market_data,
vol_surfaces, and signals via foreign keys.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(50), nullable=False)
    instrument_type: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="FUTURE, BOND, SWAP, OPTION, CDS, NDF, SPOT, INDEX, ETF, FRA",
    )
    country: Mapped[str] = mapped_column(String(10), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    exchange: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    maturity_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    contract_specs: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True,
        comment="multiplier, tick_size, margin, settlement_type",
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

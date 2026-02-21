"""Market-data (OHLCV) endpoints for instruments."""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.core.models.instruments import Instrument
from src.core.models.market_data import MarketData

router = APIRouter(prefix="/market-data", tags=["Market Data"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------
class OHLCVRecord(BaseModel):
    timestamp: datetime
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None


class LatestPrice(BaseModel):
    close: Optional[float] = None
    timestamp: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _resolve_instrument_id(
    session: AsyncSession, ticker: str
) -> int:
    """Map a ticker string to the instruments.id, or raise 404."""
    stmt = select(Instrument.id).where(Instrument.ticker == ticker)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Instrument '{ticker}' not found")
    return row


# ---------------------------------------------------------------------------
# GET /api/v1/market-data/latest  (before parameterised route)
# ---------------------------------------------------------------------------
@router.get("/latest", response_model=dict[str, LatestPrice])
async def latest_prices(
    tickers: str = Query(
        ..., description="Comma-separated tickers, e.g. USDBRL,IBOVESPA,VIX"
    ),
    session: AsyncSession = Depends(get_db),
) -> dict[str, LatestPrice]:
    """Return the most recent close price for each requested ticker."""
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
    result: dict[str, LatestPrice] = {}

    for ticker in ticker_list:
        stmt = (
            select(MarketData.close, MarketData.timestamp)
            .join(Instrument, MarketData.instrument_id == Instrument.id)
            .where(Instrument.ticker == ticker)
            .order_by(MarketData.timestamp.desc())
            .limit(1)
        )
        row = (await session.execute(stmt)).first()
        if row is not None:
            result[ticker] = LatestPrice(close=row.close, timestamp=row.timestamp)
        else:
            result[ticker] = LatestPrice()

    return result


# ---------------------------------------------------------------------------
# GET /api/v1/market-data/{ticker}
# ---------------------------------------------------------------------------
@router.get("/{ticker}", response_model=list[OHLCVRecord])
async def get_market_data(
    ticker: str,
    start: Optional[date] = Query(None, description="Start date"),
    end: Optional[date] = Query(None, description="End date"),
    session: AsyncSession = Depends(get_db),
) -> list[OHLCVRecord]:
    """Return OHLCV history for a single instrument."""
    instrument_id = await _resolve_instrument_id(session, ticker)

    stmt = (
        select(
            MarketData.timestamp,
            MarketData.open,
            MarketData.high,
            MarketData.low,
            MarketData.close,
            MarketData.volume,
        )
        .where(MarketData.instrument_id == instrument_id)
    )

    if start:
        stmt = stmt.where(MarketData.timestamp >= datetime.combine(start, datetime.min.time()))
    if end:
        stmt = stmt.where(MarketData.timestamp <= datetime.combine(end, datetime.max.time()))

    stmt = stmt.order_by(MarketData.timestamp.asc())
    rows = (await session.execute(stmt)).all()

    return [
        OHLCVRecord(
            timestamp=r.timestamp,
            open=r.open,
            high=r.high,
            low=r.low,
            close=r.close,
            volume=r.volume,
        )
        for r in rows
    ]

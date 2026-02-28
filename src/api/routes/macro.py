"""Macro-economic data series endpoints.

Provides access to macro_series observations, a dashboard of key
indicators, and metadata search.
"""

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.core.models.instruments import Instrument
from src.core.models.macro_series import MacroSeries
from src.core.models.market_data import MarketData
from src.core.models.series_metadata import SeriesMetadata

router = APIRouter(prefix="/macro", tags=["Macro"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------
class MacroObservation(BaseModel):
    observation_date: date
    value: float
    release_time: Optional[datetime] = None
    revision_number: int = 0


class IndicatorValue(BaseModel):
    value: Optional[float] = None
    date: Optional[str] = None


class DashboardResponse(BaseModel):
    brazil: dict[str, IndicatorValue]
    us: dict[str, IndicatorValue]
    market: dict[str, IndicatorValue]


class SeriesSearchResult(BaseModel):
    id: int
    series_code: str
    name: str
    frequency: str
    country: str
    unit: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _latest_macro_value(
    session: AsyncSession,
    series_code: str,
) -> IndicatorValue:
    """Return the most recent macro_series value for a given series_code."""
    stmt = (
        select(MacroSeries.value, MacroSeries.observation_date)
        .join(SeriesMetadata, MacroSeries.series_id == SeriesMetadata.id)
        .where(SeriesMetadata.series_code == series_code)
        .order_by(MacroSeries.observation_date.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        return IndicatorValue()
    return IndicatorValue(value=row.value, date=str(row.observation_date))


async def _latest_market_value(
    session: AsyncSession,
    ticker: str,
) -> IndicatorValue:
    """Return the most recent market_data close for a given instrument ticker."""
    stmt = (
        select(MarketData.close, MarketData.timestamp)
        .join(Instrument, MarketData.instrument_id == Instrument.id)
        .where(Instrument.ticker == ticker)
        .order_by(MarketData.timestamp.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        return IndicatorValue()
    return IndicatorValue(
        value=row.close,
        date=str(row.timestamp.date()) if row.timestamp else None,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/macro/dashboard  (must come before the {series_code} route)
# ---------------------------------------------------------------------------
@router.get("/dashboard", response_model=DashboardResponse)
async def macro_dashboard(session: AsyncSession = Depends(get_db)) -> DashboardResponse:
    """Key macro indicators organised into brazil / us / market blocks."""

    # Brazil indicators -- looked up by series_code in series_metadata
    brazil_codes = {
        "selic_target": "BR_SELIC_TARGET",
        "ipca_yoy": "BR_IPCA_YOY",
        "ipca_mom": "BR_IPCA_MOM",
        "ibc_br": "BR_IBC_BR",
        "unemployment": "BR_UNEMPLOYMENT",
        "trade_balance": "BR_TRADE_BALANCE",
        "reserves": "BR_RESERVES",
        "net_debt_gdp": "BR_NET_DEBT_GDP",
        "gross_debt_gdp": "BR_GROSS_DEBT_GDP",
    }
    brazil: dict[str, IndicatorValue] = {}
    for key, code in brazil_codes.items():
        brazil[key] = await _latest_macro_value(session, code)

    # US indicators
    us_codes = {
        "fed_funds": "US_FED_FUNDS",
        "cpi_yoy": "US_CPI_ALL_SA",
        "pce_core_yoy": "US_PCE_CORE",
        "nfp": "US_NFP_TOTAL",
        "unemployment": "US_UNEMP_U3",
        "ust_10y": "US_UST_10Y",
        "debt_gdp": "US_DEBT_GDP",
    }
    us: dict[str, IndicatorValue] = {}
    for key, code in us_codes.items():
        us[key] = await _latest_macro_value(session, code)

    # Market indicators -- pulled from market_data by ticker
    market_tickers = {
        "usdbrl": "USDBRL",
        "dxy": "DXY",
        "vix": "VIX",
        "ibovespa": "IBOVESPA",
        "sp500": "SP500",
        "gold": "GOLD",
        "oil_wti": "OIL_WTI",
    }
    market: dict[str, IndicatorValue] = {}
    for key, ticker in market_tickers.items():
        market[key] = await _latest_market_value(session, ticker)

    return DashboardResponse(brazil=brazil, us=us, market=market)


# ---------------------------------------------------------------------------
# GET /api/v1/macro/search
# ---------------------------------------------------------------------------
@router.get("/search", response_model=list[SeriesSearchResult])
async def search_series(
    q: str = Query(..., min_length=1, description="Search keyword"),
    country: Optional[str] = Query(
        None, description="ISO country filter (e.g. BR, US)"
    ),
    session: AsyncSession = Depends(get_db),
) -> list[SeriesSearchResult]:
    """Search series_metadata by name (case-insensitive), optionally filtered by country."""
    stmt = select(
        SeriesMetadata.id,
        SeriesMetadata.series_code,
        SeriesMetadata.name,
        SeriesMetadata.frequency,
        SeriesMetadata.country,
        SeriesMetadata.unit,
    ).where(SeriesMetadata.name.ilike(f"%{q}%"))

    if country:
        stmt = stmt.where(SeriesMetadata.country == country.upper())

    stmt = stmt.order_by(SeriesMetadata.name).limit(50)
    rows = (await session.execute(stmt)).all()

    return [
        SeriesSearchResult(
            id=r.id,
            series_code=r.series_code,
            name=r.name,
            frequency=r.frequency,
            country=r.country,
            unit=r.unit,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# GET /api/v1/macro/{series_code}
# ---------------------------------------------------------------------------
@router.get("/{series_code}", response_model=list[MacroObservation])
async def get_macro_series(
    series_code: str,
    start: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    pit: bool = Query(False, description="Point-in-time filter (release_time <= end)"),
    session: AsyncSession = Depends(get_db),
) -> list[MacroObservation]:
    """Return observation history for a given series_code.

    When *pit=true* only observations whose release_time is on or before the
    *end* date are returned, enabling point-in-time correct queries.
    """
    # Resolve series_code -> series_metadata.id
    meta_stmt = select(SeriesMetadata.id).where(
        SeriesMetadata.series_code == series_code
    )
    meta_row = (await session.execute(meta_stmt)).first()
    if meta_row is None:
        raise HTTPException(status_code=404, detail=f"Series '{series_code}' not found")
    sm_id: int = meta_row.id

    # Build query
    stmt = select(
        MacroSeries.observation_date,
        MacroSeries.value,
        MacroSeries.release_time,
        MacroSeries.revision_number,
    ).where(MacroSeries.series_id == sm_id)

    if start:
        stmt = stmt.where(MacroSeries.observation_date >= start)
    if end:
        stmt = stmt.where(MacroSeries.observation_date <= end)
    if pit and end:
        stmt = stmt.where(
            MacroSeries.release_time
            <= datetime.combine(end, datetime.max.time(), tzinfo=timezone.utc)
        )

    stmt = stmt.order_by(MacroSeries.observation_date.asc())
    rows = (await session.execute(stmt)).all()

    return [
        MacroObservation(
            observation_date=r.observation_date,
            value=r.value,
            release_time=r.release_time,
            revision_number=r.revision_number,
        )
        for r in rows
    ]

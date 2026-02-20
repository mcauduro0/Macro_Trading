"""Capital-flow and positioning endpoints.

Exposes FX-flow and CFTC positioning data from the flow_data table.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.core.models.flow_data import FlowData
from src.core.models.series_metadata import SeriesMetadata

router = APIRouter(prefix="/flows", tags=["Flows"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------
class FlowRecord(BaseModel):
    observation_date: date
    value: float
    flow_type: str


class PositioningSummaryItem(BaseModel):
    series_code: str
    name: str
    latest_date: Optional[date] = None
    latest_value: Optional[float] = None
    flow_type: Optional[str] = None


# ---------------------------------------------------------------------------
# GET /api/v1/flows/positioning-summary  (before parameterised route)
# ---------------------------------------------------------------------------
@router.get("/positioning-summary", response_model=list[PositioningSummaryItem])
async def positioning_summary(
    session: AsyncSession = Depends(get_db),
) -> list[PositioningSummaryItem]:
    """Return latest CFTC positioning values for all CFTC-related series.

    Identifies CFTC series by matching series_code LIKE 'CFTC_%' in
    series_metadata.
    """
    # Find all CFTC series
    meta_stmt = (
        select(SeriesMetadata.id, SeriesMetadata.series_code, SeriesMetadata.name)
        .where(SeriesMetadata.series_code.like("CFTC_%"))
        .order_by(SeriesMetadata.series_code)
    )
    meta_rows = (await session.execute(meta_stmt)).all()

    results: list[PositioningSummaryItem] = []
    for meta in meta_rows:
        latest_stmt = (
            select(
                FlowData.observation_date,
                FlowData.value,
                FlowData.flow_type,
            )
            .where(FlowData.series_id == meta.id)
            .order_by(FlowData.observation_date.desc())
            .limit(1)
        )
        row = (await session.execute(latest_stmt)).first()
        results.append(
            PositioningSummaryItem(
                series_code=meta.series_code,
                name=meta.name,
                latest_date=row.observation_date if row else None,
                latest_value=row.value if row else None,
                flow_type=row.flow_type if row else None,
            )
        )

    return results


# ---------------------------------------------------------------------------
# GET /api/v1/flows/{series_code}
# ---------------------------------------------------------------------------
@router.get("/{series_code}", response_model=list[FlowRecord])
async def get_flow_data(
    series_code: str,
    start: Optional[date] = Query(None, description="Start date"),
    session: AsyncSession = Depends(get_db),
) -> list[FlowRecord]:
    """Return flow-data observations for a given series_code."""
    # Resolve series_code to series_metadata.id
    meta_stmt = select(SeriesMetadata.id).where(
        SeriesMetadata.series_code == series_code
    )
    meta_row = (await session.execute(meta_stmt)).scalar_one_or_none()
    if meta_row is None:
        raise HTTPException(
            status_code=404, detail=f"Flow series '{series_code}' not found"
        )

    stmt = (
        select(
            FlowData.observation_date,
            FlowData.value,
            FlowData.flow_type,
        )
        .where(FlowData.series_id == meta_row)
    )

    if start:
        stmt = stmt.where(FlowData.observation_date >= start)

    stmt = stmt.order_by(FlowData.observation_date.asc())
    rows = (await session.execute(stmt)).all()

    return [
        FlowRecord(
            observation_date=r.observation_date,
            value=r.value,
            flow_type=r.flow_type,
        )
        for r in rows
    ]

"""Yield-curve and rate-curve endpoints.

Exposes curve snapshots by date, tenor-level history, and a list of
available curve identifiers.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.core.models.curves import CurveData

router = APIRouter(prefix="/curves", tags=["Curves"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------
class CurvePoint(BaseModel):
    tenor_label: str
    tenor_days: int
    rate: float


class CurveSnapshot(BaseModel):
    curve_id: str
    date: date
    points: list[CurvePoint]


class CurveHistoryPoint(BaseModel):
    date: date
    rate: float


# ---------------------------------------------------------------------------
# GET /api/v1/curves/available  (before parameterised route)
# ---------------------------------------------------------------------------
@router.get("/available", response_model=list[str])
async def available_curves(session: AsyncSession = Depends(get_db)) -> list[str]:
    """Return distinct curve_id values present in the curves table."""
    stmt = select(CurveData.curve_id).distinct().order_by(CurveData.curve_id)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)


# ---------------------------------------------------------------------------
# GET /api/v1/curves/{curve_id}
# ---------------------------------------------------------------------------
@router.get("/{curve_id}", response_model=CurveSnapshot)
async def get_curve_snapshot(
    curve_id: str,
    date: Optional[date] = Query(
        None, alias="date", description="Snapshot date (defaults to latest)"
    ),
    session: AsyncSession = Depends(get_db),
) -> CurveSnapshot:
    """Return all tenor points for a curve on a given date.

    If *date* is omitted the most recent available date is used.
    """
    # Determine the target date
    target_date = date
    if target_date is None:
        latest_stmt = (
            select(func.max(CurveData.curve_date))
            .where(CurveData.curve_id == curve_id)
        )
        latest_row = (await session.execute(latest_stmt)).scalar_one_or_none()
        if latest_row is None:
            raise HTTPException(
                status_code=404, detail=f"No data for curve '{curve_id}'"
            )
        target_date = latest_row

    # Fetch points
    stmt = (
        select(
            CurveData.tenor_label,
            CurveData.tenor_days,
            CurveData.rate,
        )
        .where(CurveData.curve_id == curve_id, CurveData.curve_date == target_date)
        .order_by(CurveData.tenor_days.asc())
    )
    rows = (await session.execute(stmt)).all()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No data for curve '{curve_id}' on {target_date}",
        )

    return CurveSnapshot(
        curve_id=curve_id,
        date=target_date,
        points=[
            CurvePoint(tenor_label=r.tenor_label, tenor_days=r.tenor_days, rate=r.rate)
            for r in rows
        ],
    )


# ---------------------------------------------------------------------------
# GET /api/v1/curves/{curve_id}/history
# ---------------------------------------------------------------------------
@router.get("/{curve_id}/history", response_model=list[CurveHistoryPoint])
async def get_curve_history(
    curve_id: str,
    tenor: str = Query(..., description="Tenor label, e.g. 5Y"),
    start: Optional[date] = Query(None, description="Start date"),
    end: Optional[date] = Query(None, description="End date"),
    session: AsyncSession = Depends(get_db),
) -> list[CurveHistoryPoint]:
    """Return the rate time-series for a single tenor of a curve."""
    stmt = (
        select(CurveData.curve_date, CurveData.rate)
        .where(CurveData.curve_id == curve_id, CurveData.tenor_label == tenor)
    )

    if start:
        stmt = stmt.where(CurveData.curve_date >= start)
    if end:
        stmt = stmt.where(CurveData.curve_date <= end)

    stmt = stmt.order_by(CurveData.curve_date.asc())
    rows = (await session.execute(stmt)).all()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No history for curve '{curve_id}' tenor '{tenor}'",
        )

    return [CurveHistoryPoint(date=r.curve_date, rate=r.rate) for r in rows]

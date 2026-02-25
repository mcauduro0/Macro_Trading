"""PMS Morning Pack endpoints.

Provides:
- GET  /pms/morning-pack/latest          -- most recent daily briefing
- GET  /pms/morning-pack/{briefing_date} -- briefing by date
- POST /pms/morning-pack/generate        -- generate new briefing
- GET  /pms/morning-pack/history         -- briefing summaries for last N days
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas.pms_schemas import (
    GenerateMorningPackRequest,
    MorningPackResponse,
    MorningPackSummaryResponse,
)

router = APIRouter(prefix="/pms/morning-pack", tags=["PMS - Morning Pack"])

# ---------------------------------------------------------------------------
# Lazy singleton for MorningPackService (duplicated per plan specification)
# ---------------------------------------------------------------------------
_service = None


def _get_service():
    """Return (or create) the module-level MorningPackService singleton."""
    global _service
    if _service is None:
        from src.pms.morning_pack import MorningPackService
        from src.pms import TradeWorkflowService, PositionManager

        pm = PositionManager()
        tw = TradeWorkflowService(position_manager=pm)
        _service = MorningPackService(position_manager=pm, trade_workflow=tw)
    return _service


# ---------------------------------------------------------------------------
# 1. GET /pms/morning-pack/latest
# ---------------------------------------------------------------------------
@router.get("/latest", response_model=MorningPackResponse)
async def get_latest_briefing():
    """Return the most recent daily briefing."""
    try:
        svc = _get_service()
        briefing = svc.get_latest()
        if briefing is None:
            raise HTTPException(
                status_code=404, detail="No briefing available"
            )
        return MorningPackResponse(**briefing)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# 2. POST /pms/morning-pack/generate
# ---------------------------------------------------------------------------
@router.post("/generate", response_model=MorningPackResponse)
async def generate_briefing(body: GenerateMorningPackRequest):
    """Generate a new daily briefing."""
    try:
        svc = _get_service()
        briefing_date = body.briefing_date or date.today()
        briefing = svc.generate(briefing_date=briefing_date, force=body.force)
        return MorningPackResponse(**briefing)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# 3. GET /pms/morning-pack/history (before /{briefing_date} to avoid path conflict)
# ---------------------------------------------------------------------------
@router.get("/history", response_model=list[MorningPackSummaryResponse])
async def get_briefing_history(
    days: int = Query(30, ge=1, le=365, description="Number of recent briefings"),
):
    """Return briefing summaries for the last N briefings."""
    try:
        svc = _get_service()
        summaries = svc.get_history(days=days)
        return [MorningPackSummaryResponse(**s) for s in summaries]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# 4. GET /pms/morning-pack/{briefing_date}
# ---------------------------------------------------------------------------
@router.get("/{briefing_date}", response_model=MorningPackResponse)
async def get_briefing_by_date(briefing_date: str):
    """Return the briefing for a specific date."""
    try:
        parsed_date = _parse_date(briefing_date)
        if parsed_date is None:
            raise HTTPException(
                status_code=400, detail=f"Invalid date format: {briefing_date}"
            )
        svc = _get_service()
        briefing = svc.get_by_date(parsed_date)
        if briefing is None:
            raise HTTPException(
                status_code=404,
                detail=f"No briefing found for {briefing_date}",
            )
        return MorningPackResponse(**briefing)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
def _parse_date(value: str | None) -> date | None:
    """Parse an optional ISO date string."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {value}")

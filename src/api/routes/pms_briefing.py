"""PMS Morning Pack endpoints.

Provides:
- GET  /pms/morning-pack/latest          -- most recent daily briefing
- GET  /pms/morning-pack/{briefing_date} -- briefing by date
- POST /pms/morning-pack/generate        -- generate new briefing
- GET  /pms/morning-pack/history         -- briefing summaries for last N days
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.schemas.pms_schemas import (
    GenerateMorningPackRequest,
    MorningPackResponse,
    MorningPackSummaryResponse,
)
from src.cache import PMSCache, get_pms_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pms/morning-pack", tags=["PMS - Morning Pack"])

# ---------------------------------------------------------------------------
# Lazy singleton for MorningPackService (duplicated per plan specification)
# ---------------------------------------------------------------------------
_service = None


def _get_service():
    """Return (or create) the module-level MorningPackService singleton."""
    global _service
    if _service is None:
        from src.pms import PositionManager, TradeWorkflowService
        from src.pms.morning_pack import MorningPackService

        pm = PositionManager()
        tw = TradeWorkflowService(position_manager=pm)
        _service = MorningPackService(position_manager=pm, trade_workflow=tw)
        # Hydrate from DB so in-memory stores have real data
        try:
            from src.pms.db_loader import hydrate_morning_pack_service, hydrate_trade_workflow
            hydrate_trade_workflow(tw)
            hydrate_morning_pack_service(_service)
            logger.info("MorningPackService hydrated from DB")
        except Exception as exc:
            logger.warning("Failed to hydrate MorningPackService: %s", exc)
    return _service


# ---------------------------------------------------------------------------
# 1. GET /pms/morning-pack/latest
# ---------------------------------------------------------------------------
@router.get("/latest", response_model=MorningPackResponse)
async def get_latest_briefing(
    cache: PMSCache = Depends(get_pms_cache),
):
    """Return the most recent daily briefing."""
    try:
        # Cache-first read using today's date as key
        date_key = date.today().isoformat()
        try:
            cached = await cache.get_morning_pack(date_key)
            if cached is not None:
                logger.debug("GET /morning-pack/latest: cache HIT (%s)", date_key)
                cached["cached"] = True
                return cached
        except Exception:
            logger.warning("GET /morning-pack/latest: cache read failed")

        svc = _get_service()
        briefing = svc.get_latest()
        if briefing is None:
            raise HTTPException(
                status_code=404, detail="No briefing available"
            )

        # Cache the result
        try:
            await cache.set_morning_pack(date_key, briefing)
            logger.debug("GET /morning-pack/latest: cache SET (%s)", date_key)
        except Exception:
            logger.warning("GET /morning-pack/latest: cache write failed")

        return MorningPackResponse(**briefing)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 2. POST /pms/morning-pack/generate
# ---------------------------------------------------------------------------
@router.post("/generate", response_model=MorningPackResponse)
async def generate_briefing(
    body: GenerateMorningPackRequest,
    cache: PMSCache = Depends(get_pms_cache),
):
    """Generate a new daily briefing."""
    try:
        svc = _get_service()
        briefing_date = body.briefing_date or date.today()
        briefing = svc.generate(briefing_date=briefing_date, force=body.force)

        # Write-through: cache the freshly generated briefing
        try:
            date_key = briefing_date.isoformat()
            await cache.set_morning_pack(date_key, briefing)
            logger.debug("POST /generate: cache SET (%s)", date_key)
        except Exception:
            logger.warning("POST /generate: cache write failed")

        return MorningPackResponse(**briefing)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 4. GET /pms/morning-pack/{briefing_date}
# ---------------------------------------------------------------------------
@router.get("/{briefing_date}", response_model=MorningPackResponse)
async def get_briefing_by_date(
    briefing_date: str,
    cache: PMSCache = Depends(get_pms_cache),
):
    """Return the briefing for a specific date."""
    try:
        parsed_date = _parse_date(briefing_date)
        if parsed_date is None:
            raise HTTPException(
                status_code=400, detail=f"Invalid date format: {briefing_date}"
            )

        # Cache-first read
        date_key = briefing_date
        try:
            cached = await cache.get_morning_pack(date_key)
            if cached is not None:
                logger.debug("GET /morning-pack/%s: cache HIT", date_key)
                cached["cached"] = True
                return cached
        except Exception:
            logger.warning("GET /morning-pack/%s: cache read failed", date_key)

        svc = _get_service()
        briefing = svc.get_by_date(parsed_date)
        if briefing is None:
            raise HTTPException(
                status_code=404,
                detail=f"No briefing found for {briefing_date}",
            )

        # Cache the result
        try:
            await cache.set_morning_pack(date_key, briefing)
            logger.debug("GET /morning-pack/%s: cache SET", date_key)
        except Exception:
            logger.warning("GET /morning-pack/%s: cache write failed", date_key)

        return MorningPackResponse(**briefing)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


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

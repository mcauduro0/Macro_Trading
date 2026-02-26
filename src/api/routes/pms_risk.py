"""PMS Risk Monitor endpoints.

Provides:
- GET  /pms/risk/live    -- complete live risk snapshot
- GET  /pms/risk/trend   -- 30-day risk trend data
- GET  /pms/risk/limits  -- current risk limits configuration
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.schemas.pms_schemas import (
    LiveRiskResponse,
    RiskTrendPointResponse,
)
from src.cache import PMSCache, get_pms_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pms/risk", tags=["PMS - Risk Monitor"])

# ---------------------------------------------------------------------------
# Lazy singleton for RiskMonitorService (duplicated per plan specification)
# ---------------------------------------------------------------------------
_service = None


def _get_service():
    """Return (or create) the module-level RiskMonitorService singleton."""
    global _service
    if _service is None:
        from src.pms.risk_monitor import RiskMonitorService
        from src.pms import PositionManager

        _service = RiskMonitorService(position_manager=PositionManager())
    return _service


# ---------------------------------------------------------------------------
# 1. GET /pms/risk/live
# ---------------------------------------------------------------------------
@router.get("/live", response_model=LiveRiskResponse)
async def get_live_risk(
    as_of_date: Optional[str] = Query(
        None, description="Reference date YYYY-MM-DD (defaults to today)"
    ),
    cache: PMSCache = Depends(get_pms_cache),
):
    """Return a complete live risk snapshot."""
    try:
        # Cache-first read (only for default date)
        if as_of_date is None:
            try:
                cached = await cache.get_risk_metrics()
                if cached is not None:
                    logger.debug("GET /risk/live: cache HIT")
                    cached["cached"] = True
                    return cached
            except Exception:
                logger.warning("GET /risk/live: cache read failed")

        svc = _get_service()
        ref_date = _parse_date(as_of_date)
        risk_data = svc.compute_live_risk(as_of_date=ref_date)

        # Cache the result for default (current) date
        if as_of_date is None:
            try:
                await cache.set_risk_metrics(risk_data)
                logger.debug("GET /risk/live: cache SET")
            except Exception:
                logger.warning("GET /risk/live: cache write failed")

        return LiveRiskResponse(**risk_data)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# 2. GET /pms/risk/trend
# ---------------------------------------------------------------------------
@router.get("/trend", response_model=list[RiskTrendPointResponse])
async def get_risk_trend(
    days: int = Query(30, ge=1, le=365, description="Number of days of trend data"),
):
    """Return risk trend data for the last N snapshots."""
    try:
        svc = _get_service()
        trend = svc.get_risk_trend(days=days)
        return [RiskTrendPointResponse(**point) for point in trend]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# 3. GET /pms/risk/limits
# ---------------------------------------------------------------------------
@router.get("/limits")
async def get_risk_limits():
    """Return current risk limits configuration and latest limits summary."""
    try:
        svc = _get_service()

        # PMSRiskLimits as dict
        from dataclasses import asdict

        limits_config = asdict(svc.pms_limits)

        # Get latest limits_summary from a fresh risk computation
        risk_data = svc.compute_live_risk()
        limits_summary = risk_data.get("limits_summary", {})

        return {
            "config": limits_config,
            "limits_summary": limits_summary,
        }
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

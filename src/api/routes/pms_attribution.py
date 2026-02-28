"""PMS Performance Attribution endpoints.

Provides:
- GET  /pms/attribution              -- multi-dimensional P&L attribution
- GET  /pms/attribution/equity-curve -- equity curve with daily returns and drawdown
- GET  /pms/attribution/best-worst   -- top N and bottom N positions by P&L
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.schemas.pms_schemas import (
    AttributionResponse,
    EquityCurvePointResponse,
)
from src.cache import PMSCache, get_pms_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pms/attribution", tags=["PMS - Attribution"])

# ---------------------------------------------------------------------------
# Lazy singleton for PerformanceAttributionEngine (duplicated per plan spec)
# ---------------------------------------------------------------------------
_service = None


def _get_service():
    """Return (or create) the module-level PerformanceAttributionEngine singleton."""
    global _service
    if _service is None:
        from src.pms import PositionManager
        from src.pms.attribution import PerformanceAttributionEngine

        pm = PositionManager()
        _service = PerformanceAttributionEngine(position_manager=pm)
        # Hydrate from DB so in-memory stores have real data
        try:
            from src.pms.db_loader import hydrate_position_manager

            hydrate_position_manager(pm)
            logger.info("PerformanceAttributionEngine hydrated from DB")
        except Exception as exc:
            logger.warning("Failed to hydrate PerformanceAttributionEngine: %s", exc)
    return _service


# ---------------------------------------------------------------------------
# 1. GET /pms/attribution
# ---------------------------------------------------------------------------
@router.get("", response_model=AttributionResponse)
async def get_attribution(
    period: str = Query(
        "MTD", description="Period: daily, WTD, MTD, QTD, YTD, inception, custom"
    ),
    start_date: Optional[str] = Query(
        None, description="Start date YYYY-MM-DD (for custom period)"
    ),
    end_date: Optional[str] = Query(
        None, description="End date YYYY-MM-DD (for custom period)"
    ),
    cache: PMSCache = Depends(get_pms_cache),
):
    """Return multi-dimensional P&L attribution for the specified period."""
    try:
        # Derive period_key for cache lookup
        if period == "custom" and start_date and end_date:
            period_key = f"custom_{start_date}_{end_date}"
        else:
            today_str = date.today().isoformat()
            period_key = f"{period.lower()}_{today_str}"

        # Cache-first read
        try:
            cached = await cache.get_attribution(period_key)
            if cached is not None:
                logger.debug("GET /attribution: cache HIT (%s)", period_key)
                cached["cached"] = True
                return cached
        except Exception:
            logger.warning("GET /attribution: cache read failed")

        svc = _get_service()

        if period == "custom":
            sd = _parse_date(start_date)
            ed = _parse_date(end_date)
            if sd is None or ed is None:
                raise HTTPException(
                    status_code=400,
                    detail="start_date and end_date are required for custom period",
                )
            result = svc.compute_custom_range(start_date=sd, end_date=ed)
        else:
            result = svc.compute_for_period(period=period)

        # Ensure period dates are serializable (convert date objects to str)
        period_data = result.get("period", {})
        if "start" in period_data and isinstance(period_data["start"], date):
            period_data["start"] = period_data["start"].isoformat()
        if "end" in period_data and isinstance(period_data["end"], date):
            period_data["end"] = period_data["end"].isoformat()

        # Convert date objects in by_time_period entries
        for entry in result.get("by_time_period", []):
            if "period_start" in entry and isinstance(entry["period_start"], date):
                entry["period_start"] = entry["period_start"].isoformat()
            if "period_end" in entry and isinstance(entry["period_end"], date):
                entry["period_end"] = entry["period_end"].isoformat()

        # Cache the result
        try:
            await cache.set_attribution(period_key, result)
            logger.debug("GET /attribution: cache SET (%s)", period_key)
        except Exception:
            logger.warning("GET /attribution: cache write failed")

        return AttributionResponse(**result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 2. GET /pms/attribution/equity-curve
# ---------------------------------------------------------------------------
@router.get("/equity-curve", response_model=list[EquityCurvePointResponse])
async def get_equity_curve(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
):
    """Return equity curve data with daily returns and drawdown."""
    try:
        svc = _get_service()
        sd = _parse_date(start_date)
        ed = _parse_date(end_date)

        # Default to last 30 days if not specified
        if sd is None:
            sd = date.today() - timedelta(days=30)
        if ed is None:
            ed = date.today()

        curve = svc.compute_equity_curve(start_date=sd, end_date=ed)
        return [EquityCurvePointResponse(**point) for point in curve]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 3. GET /pms/attribution/best-worst
# ---------------------------------------------------------------------------
@router.get("/best-worst")
async def get_best_worst(
    n: int = Query(10, ge=1, le=100, description="Number of top/bottom positions"),
):
    """Return top N and bottom N positions by P&L from latest attribution."""
    try:
        svc = _get_service()

        # Use inception-to-date for full picture
        result = svc.compute_for_period("inception")
        by_instrument = result.get("by_instrument", [])

        # Sort by pnl_brl
        sorted_positions = sorted(
            by_instrument, key=lambda x: x.get("pnl_brl", 0.0), reverse=True
        )

        best = sorted_positions[:n]
        worst = (
            sorted_positions[-n:] if len(sorted_positions) >= n else sorted_positions
        )
        worst = sorted(worst, key=lambda x: x.get("pnl_brl", 0.0))

        return {
            "best": best,
            "worst": worst,
            "total_positions": len(by_instrument),
        }
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

"""Risk endpoint (portfolio risk report).

Provides:
- GET /risk/report — portfolio risk report
    (Delegates to portfolio_api.portfolio_risk for the same data)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/risk", tags=["Risk"])


# ---------------------------------------------------------------------------
# Response envelope
# ---------------------------------------------------------------------------
def _envelope(data: Any) -> dict:
    return {
        "status": "ok",
        "data": data,
        "meta": {"timestamp": datetime.now(timezone.utc).isoformat()},
    }


# ---------------------------------------------------------------------------
# GET /api/v1/risk/report
# ---------------------------------------------------------------------------
@router.get("/report")
async def risk_report(
    date: Optional[str] = Query(None, description="Date YYYY-MM-DD"),
):
    """Return portfolio risk report (VaR, stress tests, limits)."""
    try:
        from src.api.routes.portfolio_api import _build_risk_report
        import asyncio

        risk_data = await asyncio.to_thread(_build_risk_report)
        return _envelope(risk_data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

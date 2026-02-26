"""Monitoring API endpoints for alerts, pipeline status, and system health.

Provides:
- GET  /api/v1/monitoring/alerts          -- Active alerts from AlertManager
- GET  /api/v1/monitoring/pipeline-status -- Per-connector pipeline health
- GET  /api/v1/monitoring/system-health   -- Aggregate system health status
- POST /api/v1/monitoring/test-alert      -- Trigger test notification
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from src.monitoring.alert_manager import AlertManager

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])

# Shared AlertManager instance (singleton for the API lifetime)
_alert_manager: AlertManager | None = None


def _get_alert_manager() -> AlertManager:
    """Lazy-initialize and return the shared AlertManager."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


# ---------------------------------------------------------------------------
# Response envelope (consistent with Phase 13 pattern)
# ---------------------------------------------------------------------------

def _envelope(data: Any) -> dict:
    return {
        "status": "ok",
        "data": data,
        "meta": {"timestamp": datetime.now(timezone.utc).isoformat()},
    }


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class TestAlertRequest(BaseModel):
    channel: str = "both"  # "slack" | "email" | "both"


class RuleConfigRequest(BaseModel):
    rule_id: str
    enabled: Optional[bool] = None
    threshold: Optional[float] = None


# ---------------------------------------------------------------------------
# GET /api/v1/monitoring/alerts
# ---------------------------------------------------------------------------

@router.get("/alerts")
async def get_active_alerts():
    """Return active alerts from the AlertManager (fired within cooldown window)."""
    am = _get_alert_manager()
    alerts = am.get_active_alerts()
    return _envelope({
        "alerts": alerts,
        "total": len(alerts),
    })


# ---------------------------------------------------------------------------
# GET /api/v1/monitoring/pipeline-status
# ---------------------------------------------------------------------------

@router.get("/pipeline-status")
async def get_pipeline_status():
    """Return pipeline health summary per connector.

    Uses sample data for now (matching Phase 17 API pattern).
    """
    connectors = [
        {
            "connector": "bcb_sgs",
            "status": "OK",
            "last_run": "2026-02-23T06:00:00Z",
            "last_run_age": 1200,
            "duration_seconds": 45,
            "records_fetched": 1250,
        },
        {
            "connector": "fred",
            "status": "OK",
            "last_run": "2026-02-23T06:01:00Z",
            "last_run_age": 1140,
            "duration_seconds": 32,
            "records_fetched": 890,
        },
        {
            "connector": "yahoo",
            "status": "OK",
            "last_run": "2026-02-23T06:02:00Z",
            "last_run_age": 1080,
            "duration_seconds": 28,
            "records_fetched": 650,
        },
        {
            "connector": "bcb_ptax",
            "status": "OK",
            "last_run": "2026-02-23T06:00:30Z",
            "last_run_age": 1170,
            "duration_seconds": 12,
            "records_fetched": 30,
        },
        {
            "connector": "b3_market_data",
            "status": "OK",
            "last_run": "2026-02-23T06:03:00Z",
            "last_run_age": 1020,
            "duration_seconds": 55,
            "records_fetched": 2100,
        },
        {
            "connector": "treasury_gov",
            "status": "OK",
            "last_run": "2026-02-23T06:01:30Z",
            "last_run_age": 1110,
            "duration_seconds": 18,
            "records_fetched": 420,
        },
    ]

    # Overall pipeline status
    all_ok = all(c["status"] == "OK" for c in connectors)
    return _envelope({
        "overall_status": "healthy" if all_ok else "degraded",
        "connectors": connectors,
        "total_connectors": len(connectors),
    })


# ---------------------------------------------------------------------------
# GET /api/v1/monitoring/system-health
# ---------------------------------------------------------------------------

@router.get("/system-health")
async def get_system_health():
    """Return aggregate system health: DB, Redis, pipeline, agents, risk."""
    # Sample health status (matching Phase 17 deterministic pattern)
    components = {
        "database": {"status": "healthy", "latency_ms": 2.3},
        "redis": {"status": "healthy", "latency_ms": 0.8},
        "pipeline": {
            "status": "healthy",
            "last_run": "2026-02-23T06:03:00Z",
            "connectors_ok": 6,
            "connectors_total": 6,
        },
        "agents": {
            "status": "healthy",
            "agents_fresh": 5,
            "agents_total": 5,
            "oldest_report_age_hours": 18.5,
        },
        "risk": {
            "status": "healthy",
            "var_95": 0.032,
            "drawdown": 0.018,
            "limits_breached": 0,
        },
    }

    # Determine overall status
    statuses = [c["status"] for c in components.values()]
    if all(s == "healthy" for s in statuses):
        overall = "healthy"
    elif any(s == "unhealthy" for s in statuses):
        overall = "unhealthy"
    else:
        overall = "degraded"

    return _envelope({
        "overall_status": overall,
        "components": components,
    })


# ---------------------------------------------------------------------------
# POST /api/v1/monitoring/test-alert
# ---------------------------------------------------------------------------

@router.post("/test-alert")
async def test_alert(body: TestAlertRequest | None = None):
    """Trigger a test alert notification to specified channel(s).

    Accepts optional ``{"channel": "slack|email|both"}``.
    """
    channel = (body.channel if body else "both").lower()
    am = _get_alert_manager()

    test_alert = {
        "rule_id": "TEST",
        "name": "Test Alert",
        "description": "This is a test alert to verify notification channels",
        "severity": "warning",
        "threshold": 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    results = {}
    if channel in ("slack", "both"):
        results["slack"] = am.send_slack(test_alert)
    if channel in ("email", "both"):
        results["email"] = am.send_email(test_alert)

    return _envelope({
        "test_alert": test_alert,
        "delivery": results,
        "channel": channel,
    })

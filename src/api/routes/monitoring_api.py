"""Monitoring API endpoints for alerts, pipeline status, and system health.

Provides:
- GET  /api/v1/monitoring/alerts          -- Active alerts from AlertManager
- GET  /api/v1/monitoring/pipeline-status -- Per-connector pipeline health
- GET  /api/v1/monitoring/system-health   -- Aggregate system health status
- POST /api/v1/monitoring/test-alert      -- Trigger test notification
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from src.monitoring.alert_manager import AlertManager

logger = logging.getLogger(__name__)

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
    return _envelope(
        {
            "alerts": alerts,
            "total": len(alerts),
        }
    )


# ---------------------------------------------------------------------------
# GET /api/v1/monitoring/pipeline-status
# ---------------------------------------------------------------------------


@router.get("/pipeline-status")
async def get_pipeline_status():
    """Return pipeline health summary per connector from real database records."""
    connectors: list[dict] = []

    try:
        from sqlalchemy import text

        from src.core.database import async_session_factory

        async with async_session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT connector_name, status, last_run_at, "
                    "duration_seconds, records_fetched "
                    "FROM pipeline_runs "
                    "WHERE last_run_at = ("
                    "  SELECT MAX(last_run_at) FROM pipeline_runs pr2 "
                    "  WHERE pr2.connector_name = pipeline_runs.connector_name"
                    ") "
                    "ORDER BY connector_name"
                )
            )
            rows = result.fetchall()
            for row in rows:
                age_seconds = 0
                if row.last_run_at:
                    age_seconds = int(
                        (datetime.now(timezone.utc) - row.last_run_at).total_seconds()
                    )
                connectors.append(
                    {
                        "connector": row.connector_name,
                        "status": row.status or "UNKNOWN",
                        "last_run": (
                            row.last_run_at.isoformat() if row.last_run_at else None
                        ),
                        "last_run_age": age_seconds,
                        "duration_seconds": row.duration_seconds,
                        "records_fetched": row.records_fetched,
                    }
                )
    except Exception as exc:
        logger.warning("pipeline_status_db_unavailable: %s", exc)
        # Return honest status instead of fake data

        known_connectors = [
            "bcb_sgs",
            "fred",
            "yahoo",
            "bcb_ptax",
            "b3_market_data",
            "treasury_gov",
            "ibge_sidra",
            "oecd_sdmx",
            "cftc_cot",
            "anbima",
            "bcb_focus",
            "bcb_fx_flow",
            "stn_fiscal",
            "fmp_treasury",
            "te_di_curve",
        ]
        for name in known_connectors:
            connectors.append(
                {
                    "connector": name,
                    "status": "UNKNOWN",
                    "last_run": None,
                    "last_run_age": None,
                    "duration_seconds": None,
                    "records_fetched": None,
                    "note": "Database unavailable - no pipeline run history",
                }
            )

    all_ok = all(c.get("status") == "OK" for c in connectors) if connectors else False
    has_unknown = any(c.get("status") == "UNKNOWN" for c in connectors)

    if has_unknown:
        overall = "unknown"
    elif all_ok:
        overall = "healthy"
    else:
        overall = "degraded"

    return _envelope(
        {
            "overall_status": overall,
            "connectors": connectors,
            "total_connectors": len(connectors),
        }
    )


# ---------------------------------------------------------------------------
# GET /api/v1/monitoring/system-health
# ---------------------------------------------------------------------------


@router.get("/system-health")
async def get_system_health():
    """Return aggregate system health: DB, Redis, pipeline, agents, risk.

    Performs real health checks against each component.
    """
    components: dict[str, dict] = {}

    # Database health check
    try:
        import time

        from sqlalchemy import text

        from src.core.database import async_session_factory

        t0 = time.monotonic()
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        latency = (time.monotonic() - t0) * 1000
        components["database"] = {"status": "healthy", "latency_ms": round(latency, 1)}
    except Exception as exc:
        components["database"] = {"status": "unhealthy", "error": str(exc)}

    # Redis health check
    try:
        import time

        from src.core.redis import get_redis

        t0 = time.monotonic()
        r = get_redis()
        r.ping()
        latency = (time.monotonic() - t0) * 1000
        components["redis"] = {"status": "healthy", "latency_ms": round(latency, 1)}
    except Exception as exc:
        components["redis"] = {"status": "unhealthy", "error": str(exc)}

    # Pipeline status (count recent runs from DB)
    try:
        from sqlalchemy import text

        from src.core.database import async_session_factory

        async with async_session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT COUNT(DISTINCT connector_name) as total, "
                    "COUNT(DISTINCT CASE WHEN status = 'OK' THEN connector_name END) as ok_count, "
                    "MAX(last_run_at) as last_run "
                    "FROM pipeline_runs "
                    "WHERE last_run_at > NOW() - INTERVAL '24 hours'"
                )
            )
            row = result.first()
            if row and row.total > 0:
                components["pipeline"] = {
                    "status": "healthy" if row.ok_count == row.total else "degraded",
                    "last_run": row.last_run.isoformat() if row.last_run else None,
                    "connectors_ok": row.ok_count,
                    "connectors_total": row.total,
                }
            else:
                components["pipeline"] = {
                    "status": "unknown",
                    "note": "No pipeline runs in last 24 hours",
                }
    except Exception as exc:
        components["pipeline"] = {"status": "unknown", "error": str(exc)}

    # Agent freshness (check agent_reports table)
    try:
        from sqlalchemy import text

        from src.core.database import async_session_factory

        async with async_session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT COUNT(DISTINCT agent_id) as total, "
                    "COUNT(DISTINCT CASE WHEN created_at > NOW() - INTERVAL '24 hours' "
                    "  THEN agent_id END) as fresh, "
                    "EXTRACT(EPOCH FROM (NOW() - MIN(created_at))) / 3600 as oldest_hours "
                    "FROM agent_reports "
                    "WHERE created_at > NOW() - INTERVAL '7 days'"
                )
            )
            row = result.first()
            if row and row.total > 0:
                components["agents"] = {
                    "status": "healthy" if row.fresh >= 3 else "degraded",
                    "agents_fresh": row.fresh or 0,
                    "agents_total": row.total or 0,
                    "oldest_report_age_hours": (
                        round(row.oldest_hours, 1) if row.oldest_hours else None
                    ),
                }
            else:
                components["agents"] = {
                    "status": "unknown",
                    "note": "No agent reports found in last 7 days",
                }
    except Exception as exc:
        components["agents"] = {"status": "unknown", "error": str(exc)}

    # Risk status (quick VaR check)
    try:
        from src.api.routes.risk_api import _load_portfolio_returns

        returns = _load_portfolio_returns()
        from src.risk.var_calculator import VaRCalculator

        calc = VaRCalculator()
        vr = calc.calculate(returns, "historical")
        components["risk"] = {
            "status": "healthy",
            "var_95": round(vr.var_95, 6),
            "n_observations": vr.n_observations,
        }
    except Exception as exc:
        components["risk"] = {"status": "unknown", "error": str(exc)}

    # Determine overall status
    statuses = [c["status"] for c in components.values()]
    if all(s == "healthy" for s in statuses):
        overall = "healthy"
    elif any(s == "unhealthy" for s in statuses):
        overall = "unhealthy"
    else:
        overall = "degraded"

    return _envelope(
        {
            "overall_status": overall,
            "components": components,
        }
    )


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

    return _envelope(
        {
            "test_alert": test_alert,
            "delivery": results,
            "channel": channel,
        }
    )

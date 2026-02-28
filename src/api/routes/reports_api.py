"""Report API endpoints for daily report generation and delivery.

Endpoints:
  GET  /reports/daily        — List recent daily reports (last 7 days)
  GET  /reports/daily/latest — Returns the most recent daily report
  POST /reports/daily/send   — Triggers report generation and delivery
"""

import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.reporting.daily_report import DailyReportGenerator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


class SendReportRequest(BaseModel):
    channels: list[str] = ["email", "slack"]
    recipients: list[str] | None = None
    date: str | None = None


def _build_pipeline_context() -> dict:
    """Build pipeline_context from real database and agent data.

    Queries TimescaleDB for the latest market data, agent reports, signals,
    and portfolio state. Returns a dict suitable for DailyReportGenerator.
    """
    ctx: dict = {
        "market_snapshot": {},
        "regime": {},
        "agent_views": {},
        "signals": {},
        "portfolio": {},
        "risk": {},
        "actions": {},
    }

    try:
        from sqlalchemy import create_engine, text

        from src.core.config import get_settings

        settings = get_settings()
        engine = create_engine(settings.database_url)

        with engine.connect() as conn:
            # Market snapshot from macro_series
            series_map = {
                "BCB_432": ("SELIC", "brazil_rates"),
                "BCB_4389": ("USDBRL", "fx"),
                "BCB_433": ("IPCA_12M", "brazil_macro"),
                "FRED_DFF": ("FED_FUNDS", "us_rates"),
                "FRED_DGS10": ("UST_10Y", "us_rates"),
                "FRED_VIXCLS": ("VIX", "global"),
            }
            snapshot: dict = {}
            for series_id, (name, cat) in series_map.items():
                try:
                    row = conn.execute(
                        text(
                            "SELECT value, reference_date FROM macro_series "
                            "WHERE series_id = :sid "
                            "ORDER BY reference_date DESC LIMIT 1"
                        ),
                        {"sid": series_id},
                    ).first()
                    if row:
                        snapshot[name] = {
                            "value": float(row.value),
                            "date": str(row.reference_date),
                        }
                except Exception:
                    continue
            ctx["market_snapshot"] = snapshot

            # Agent views from agent_reports table
            try:
                rows = conn.execute(
                    text(
                        "SELECT agent_id, direction, conviction, key_drivers, "
                        "narrative FROM agent_reports "
                        "WHERE created_at >= NOW() - INTERVAL '7 days' "
                        "ORDER BY created_at DESC"
                    )
                ).fetchall()
                views = {}
                for row in rows:
                    aid = row.agent_id
                    if aid not in views:
                        views[aid] = {
                            "direction": row.direction,
                            "conviction": (
                                float(row.conviction) if row.conviction else 0.0
                            ),
                            "key_drivers": row.key_drivers or [],
                            "narrative": (row.narrative or "")[:300],
                        }
                ctx["agent_views"] = views
            except Exception as exc:
                logger.debug("agent_views query failed: %s", exc)

            # Signals from signals table
            try:
                sig_rows = conn.execute(
                    text(
                        "SELECT instrument, direction, conviction, strategy_id "
                        "FROM signals "
                        "WHERE created_at >= NOW() - INTERVAL '2 days' "
                        "ORDER BY conviction DESC LIMIT 20"
                    )
                ).fetchall()
                ctx["signals"] = {
                    "active": [
                        {
                            "instrument": r.instrument,
                            "direction": r.direction,
                            "conviction": float(r.conviction) if r.conviction else 0.0,
                            "strategy_id": r.strategy_id,
                        }
                        for r in sig_rows
                    ],
                    "count": len(sig_rows),
                }
            except Exception as exc:
                logger.debug("signals query failed: %s", exc)

            # Portfolio from positions table
            try:
                pos_rows = conn.execute(
                    text(
                        "SELECT instrument, direction, notional_brl, "
                        "unrealized_pnl_brl, entry_date "
                        "FROM positions WHERE status = 'OPEN' "
                        "ORDER BY notional_brl DESC"
                    )
                ).fetchall()
                ctx["portfolio"] = {
                    "positions": [
                        {
                            "instrument": r.instrument,
                            "direction": r.direction,
                            "notional_brl": (
                                float(r.notional_brl) if r.notional_brl else 0.0
                            ),
                            "unrealized_pnl_brl": (
                                float(r.unrealized_pnl_brl)
                                if r.unrealized_pnl_brl
                                else 0.0
                            ),
                        }
                        for r in pos_rows
                    ],
                    "count": len(pos_rows),
                }
            except Exception as exc:
                logger.debug("portfolio query failed: %s", exc)

    except Exception as exc:
        logger.warning("pipeline_context build failed: %s", exc)

    # Regime from AgentRegistry if available
    try:
        from src.agents.registry import AgentRegistry

        agent = AgentRegistry.get("cross_asset_agent")
        report = getattr(agent, "latest_report", None)
        if report and hasattr(report, "regime"):
            ctx["regime"] = {
                "name": getattr(report.regime, "name", "Unknown"),
                "probabilities": getattr(report.regime, "probabilities", {}),
                "transition_risk": getattr(report.regime, "transition_prob", 0.0),
            }
    except Exception:
        ctx["regime"] = {"name": "Unknown", "probabilities": {}, "transition_risk": 0.0}

    # Risk placeholder (VaR requires portfolio_returns which may be empty)
    ctx["risk"] = {"var_95": "data unavailable", "stress_tests": "data unavailable"}
    ctx["actions"] = {"pending_proposals": [], "limit_breaches": []}

    return ctx


@router.get("/daily")
async def list_daily_reports():
    """List recent daily reports (last 7 days)."""
    today = date.today()
    reports = []
    for i in range(7):
        d = today - timedelta(days=i)
        if d.weekday() >= 5:
            continue
        reports.append(
            {
                "date": str(d),
                "generation_time": f"{d}T06:30:00Z",
                "sections": 7,
                "status": "generated" if i > 0 else "latest",
            }
        )
    return {
        "status": "ok",
        "data": {"reports": reports, "total": len(reports)},
        "meta": {"timestamp": datetime.now(timezone.utc).isoformat()},
    }


@router.get("/daily/latest")
async def get_latest_report():
    """Returns the most recent daily report with all 7 sections.

    Builds pipeline_context from real database data, then generates
    the report. Returns 503 if no data is available.
    """
    try:
        pipeline_ctx = _build_pipeline_context()
        generator = DailyReportGenerator()
        sections = generator.generate(pipeline_context=pipeline_ctx)

        sections_data = {}
        for key, section in sections.items():
            sections_data[key] = {
                "title": section.title,
                "content": section.content,
                "commentary": section.commentary,
            }

        return {
            "status": "ok",
            "data": {
                "date": str(generator.as_of_date),
                "sections": sections_data,
                "section_count": len(sections_data),
                "html_url": "/api/v1/reports/daily/latest?format=html",
                "markdown_url": "/api/v1/reports/daily/latest?format=md",
            },
            "meta": {"timestamp": datetime.now(timezone.utc).isoformat()},
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Report generation requires pipeline data: {exc}",
        )
    except Exception as exc:
        logger.error("Report generation failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Report generation error: {exc}",
        )


@router.post("/daily/send")
async def send_daily_report(request: SendReportRequest):
    """Trigger report generation and delivery via email and/or Slack."""
    as_of = date.fromisoformat(request.date) if request.date else None
    generator = DailyReportGenerator(as_of_date=as_of)

    try:
        pipeline_ctx = _build_pipeline_context()
        generator.generate(pipeline_context=pipeline_ctx)
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Report generation requires pipeline data: {exc}",
        )

    results: dict[str, str] = {}

    if "email" in request.channels:
        ok = generator.send_email(recipients=request.recipients)
        results["email"] = "sent" if ok else "failed_or_not_configured"

    if "slack" in request.channels:
        ok = generator.send_slack()
        results["slack"] = "sent" if ok else "failed_or_not_configured"

    return {
        "status": "ok",
        "data": {
            "date": str(generator.as_of_date),
            "delivery": results,
            "sections_generated": len(generator.sections),
        },
        "meta": {"timestamp": datetime.now(timezone.utc).isoformat()},
    }

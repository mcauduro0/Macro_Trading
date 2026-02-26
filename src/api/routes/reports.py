"""Reports endpoint — daily macro brief.

Provides:
- GET /reports/daily-brief — generate daily macro narrative via NarrativeGenerator
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["Reports"])


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
# GET /api/v1/reports/daily-brief
# ---------------------------------------------------------------------------
@router.get("/daily-brief")
async def daily_brief(
    date: Optional[str] = Query(None, description="Date YYYY-MM-DD"),
):
    """Generate daily macro brief via NarrativeGenerator."""
    from datetime import date as date_type

    as_of = date_type.today()
    if date:
        try:
            as_of = date_type.fromisoformat(date)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {date}")

    try:
        brief = await asyncio.to_thread(_generate_brief, as_of)
        return _envelope({
            "content": brief.content,
            "source": brief.source,
            "word_count": brief.word_count,
            "generated_at": brief.generated_at.isoformat(),
            "as_of_date": str(brief.as_of_date),
        })
    except Exception as exc:
        logger.error("reports error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


def _generate_brief(as_of: date):
    """Run agents and generate narrative brief."""
    from src.api.routes.agents import AGENT_DEFINITIONS, _get_agent_instance
    from src.narrative.generator import NarrativeGenerator

    # Collect agent reports
    agent_reports = {}
    for defn in AGENT_DEFINITIONS:
        agent_id = defn["agent_id"]
        try:
            agent = _get_agent_instance(agent_id)
            if agent is not None:
                report = agent.backtest_run(as_of)
                agent_reports[agent_id] = report
        except Exception:
            pass

    # Generate narrative (reads ANTHROPIC_API_KEY from settings; template fallback if empty)
    generator = NarrativeGenerator()
    brief = generator.generate(agent_reports, as_of_date=as_of)
    return brief

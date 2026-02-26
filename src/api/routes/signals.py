"""Signal aggregation endpoint.

Provides:
- GET /signals/latest — latest signals from all agents with consensus
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/signals", tags=["Signals"])


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
# GET /api/v1/signals/latest
# ---------------------------------------------------------------------------
@router.get("/latest")
async def signals_latest(
    date: Optional[str] = Query(None, description="Date YYYY-MM-DD"),
):
    """Run all agents and return aggregated signals with consensus."""
    from datetime import date as date_type

    as_of = date_type.today()
    if date:
        try:
            as_of = date_type.fromisoformat(date)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {date}")

    try:
        all_signals = await _collect_all_signals(as_of)

        # Compute consensus per asset class
        consensus = _compute_consensus(all_signals)

        return _envelope({
            "signals": all_signals,
            "consensus": consensus,
            "as_of_date": str(as_of),
        })
    except Exception as exc:
        logger.error("signals error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


async def _collect_all_signals(as_of: date) -> list[dict]:
    """Run all agents and collect their signals as dicts."""
    from src.api.routes.agents import AGENT_DEFINITIONS, _get_agent_instance

    all_signals: list[dict] = []
    for defn in AGENT_DEFINITIONS:
        agent_id = defn["agent_id"]
        try:
            agent = _get_agent_instance(agent_id)
            if agent is None:
                continue
            report = await asyncio.to_thread(agent.backtest_run, as_of)
            for sig in report.signals:
                direction = sig.direction.value if hasattr(sig.direction, "value") else str(sig.direction)
                strength = sig.strength.value if hasattr(sig.strength, "value") else str(sig.strength)
                all_signals.append({
                    "signal_id": sig.signal_id,
                    "agent_id": sig.agent_id,
                    "direction": direction,
                    "strength": strength,
                    "confidence": sig.confidence,
                    "value": sig.value,
                    "horizon_days": sig.horizon_days,
                    "metadata": sig.metadata,
                })
        except Exception:
            # Skip agents that fail
            pass

    return all_signals


def _compute_consensus(signals: list[dict]) -> dict:
    """Compute consensus per direction from all signals."""
    # Group by direction
    direction_groups: dict[str, list[dict]] = defaultdict(list)
    for sig in signals:
        direction_groups[sig["direction"]].append(sig)

    total = len(signals) if signals else 1
    consensus = {}
    for direction, group in direction_groups.items():
        avg_confidence = sum(s["confidence"] for s in group) / len(group) if group else 0.0
        agreement_ratio = len(group) / total
        consensus[direction] = {
            "direction": direction,
            "avg_confidence": round(avg_confidence, 4),
            "agreement_ratio": round(agreement_ratio, 4),
            "count": len(group),
        }

    return consensus

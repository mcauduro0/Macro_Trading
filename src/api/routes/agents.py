"""Agent management endpoints.

Provides:
- GET  /agents              — list all registered agents
- GET  /agents/{id}/latest  — get latest report for an agent
- POST /agents/{id}/run     — trigger agent execution
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["Agents"])


# ---------------------------------------------------------------------------
# Response envelope
# ---------------------------------------------------------------------------
def _envelope(data: Any) -> dict:
    return {
        "status": "ok",
        "data": data,
        "meta": {"timestamp": datetime.now(timezone.utc).isoformat()},
    }


def _error_envelope(message: str, status_code: int = 500) -> dict:
    return {
        "status": "error",
        "error": message,
        "meta": {"timestamp": datetime.now(timezone.utc).isoformat()},
    }


# ---------------------------------------------------------------------------
# Agent metadata (static — reflects the 5 registered agents)
# ---------------------------------------------------------------------------
AGENT_DEFINITIONS = [
    {
        "agent_id": "inflation_agent",
        "agent_name": "Inflation Agent",
        "description": (
            "Analyzes Brazilian and US inflation dynamics via Phillips Curve,"
            " bottom-up IPCA, surprise, and persistence models."
        ),
        "execution_order_index": 0,
    },
    {
        "agent_id": "monetary_agent",
        "agent_name": "Monetary Policy Agent",
        "description": (
            "Models monetary policy via Taylor Rule, Selic path,"
            " term premium, and Kalman r-star estimation."
        ),
        "execution_order_index": 1,
    },
    {
        "agent_id": "fiscal_agent",
        "agent_name": "Fiscal Agent",
        "description": (
            "Assesses fiscal outlook via debt sustainability analysis,"
            " fiscal impulse, and fiscal dominance risk."
        ),
        "execution_order_index": 2,
    },
    {
        "agent_id": "fx_agent",
        "agent_name": "FX Equilibrium Agent",
        "description": "Evaluates FX fair value via BEER model, carry-to-risk, capital flows, and CIP basis analysis.",
        "execution_order_index": 3,
    },
    {
        "agent_id": "cross_asset_agent",
        "agent_name": "Cross-Asset Agent",
        "description": "Detects macro regimes, cross-asset correlations, and risk sentiment across asset classes.",
        "execution_order_index": 4,
    },
]

AGENT_LOOKUP = {a["agent_id"]: a for a in AGENT_DEFINITIONS}


# ---------------------------------------------------------------------------
# Request body
# ---------------------------------------------------------------------------
class AgentRunRequest(BaseModel):
    date: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_agent_instance(agent_id: str):
    """Instantiate an agent by ID with a PointInTimeDataLoader."""
    from src.agents.data_loader import PointInTimeDataLoader

    loader = PointInTimeDataLoader()

    agent_map = {}
    try:
        from src.agents.inflation_agent import InflationAgent
        agent_map["inflation_agent"] = lambda: InflationAgent(loader)
    except ImportError:
        pass
    try:
        from src.agents.monetary_agent import MonetaryPolicyAgent
        agent_map["monetary_agent"] = lambda: MonetaryPolicyAgent(loader)
    except ImportError:
        pass
    try:
        from src.agents.fiscal_agent import FiscalAgent
        agent_map["fiscal_agent"] = lambda: FiscalAgent(loader)
    except ImportError:
        pass
    try:
        from src.agents.fx_agent import FxEquilibriumAgent
        agent_map["fx_agent"] = lambda: FxEquilibriumAgent(loader)
    except ImportError:
        pass
    try:
        from src.agents.cross_asset_agent import CrossAssetAgent
        agent_map["cross_asset_agent"] = lambda: CrossAssetAgent(loader)
    except ImportError:
        pass

    if agent_id not in agent_map:
        return None
    return agent_map[agent_id]()


def _report_to_dict(report) -> dict:
    """Serialize an AgentReport to JSON-safe dict."""
    signals = []
    for sig in report.signals:
        signals.append({
            "signal_id": sig.signal_id,
            "direction": sig.direction.value if hasattr(sig.direction, "value") else str(sig.direction),
            "strength": sig.strength.value if hasattr(sig.strength, "value") else str(sig.strength),
            "confidence": sig.confidence,
            "value": sig.value,
            "horizon_days": sig.horizon_days,
            "metadata": sig.metadata,
        })
    return {
        "agent_id": report.agent_id,
        "as_of_date": str(report.as_of_date),
        "narrative": report.narrative,
        "signals": signals,
    }


# ---------------------------------------------------------------------------
# GET /api/v1/agents
# ---------------------------------------------------------------------------
@router.get("")
async def list_agents():
    """Return list of all 5 registered agents with metadata."""
    agents_data = []
    for defn in AGENT_DEFINITIONS:
        agents_data.append({
            **defn,
            "last_run": None,
            "signal_count": 0,
        })
    return _envelope(agents_data)


# ---------------------------------------------------------------------------
# GET /api/v1/agents/{agent_id}/latest
# ---------------------------------------------------------------------------
@router.get("/{agent_id}/latest")
async def agent_latest(
    agent_id: str,
    date: Optional[str] = Query(None, description="Date YYYY-MM-DD"),
):
    """Run agent for the given date and return its report."""
    if agent_id not in AGENT_LOOKUP:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    import asyncio
    from datetime import date as date_type

    as_of = date_type.today()
    if date:
        try:
            as_of = date_type.fromisoformat(date)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {date}")

    try:
        agent = _get_agent_instance(agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        report = await asyncio.to_thread(agent.backtest_run, as_of)
        return _envelope(_report_to_dict(report))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# POST /api/v1/agents/{agent_id}/run
# ---------------------------------------------------------------------------
@router.post("/{agent_id}/run")
async def agent_run(
    agent_id: str,
    body: AgentRunRequest | None = None,
):
    """Trigger agent execution and return the report."""
    if agent_id not in AGENT_LOOKUP:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    import asyncio
    from datetime import date as date_type

    as_of = date_type.today()
    if body and body.date:
        try:
            as_of = date_type.fromisoformat(body.date)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {body.date}")

    try:
        agent = _get_agent_instance(agent_id)
        if agent is None:
            raise HTTPException(status_code=500, detail=f"Agent '{agent_id}' could not be instantiated")
        report = await asyncio.to_thread(agent.run, as_of)
        return _envelope(_report_to_dict(report))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")

"""PMS Decision Journal endpoints.

Provides:
- GET  /pms/journal/                       -- list journal entries with filtering and pagination
- GET  /pms/journal/{entry_id}             -- single journal entry detail with context snapshots
- POST /pms/journal/{entry_id}/outcome     -- record outcome assessment as linked NOTE entry
- GET  /pms/journal/stats/decision-analysis -- decision statistics and analysis
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas.pms_schemas import JournalEntryResponse, OutcomeRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pms/journal", tags=["PMS - Decision Journal"])

# ---------------------------------------------------------------------------
# Lazy singleton for TradeWorkflowService (duplicated per plan specification)
# ---------------------------------------------------------------------------
_workflow = None


def _get_workflow():
    """Return (or create) the module-level TradeWorkflowService singleton."""
    global _workflow
    if _workflow is None:
        from src.pms import TradeWorkflowService

        _workflow = TradeWorkflowService()
        # Hydrate from DB so in-memory stores have real data
        try:
            from src.pms.db_loader import hydrate_trade_workflow

            hydrate_trade_workflow(_workflow)
            logger.info("TradeWorkflowService hydrated from DB (journal route)")
        except Exception as exc:
            logger.warning("Failed to hydrate TradeWorkflowService (journal): %s", exc)
    return _workflow


# ---------------------------------------------------------------------------
# 1. GET /pms/journal/ -- list journal entries with filtering and pagination
# ---------------------------------------------------------------------------
@router.get("/", response_model=list[JournalEntryResponse])
async def list_journal_entries(
    entry_type: Optional[str] = Query(
        None,
        description="Filter by entry type: OPEN, CLOSE, REJECT, MODIFY, NOTE, SYSTEM_EVENT",
    ),
    position_id: Optional[int] = Query(None, description="Filter by position ID"),
    instrument: Optional[str] = Query(None, description="Filter by instrument"),
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    limit: int = Query(50, ge=1, le=500, description="Max entries to return"),
    offset: int = Query(0, ge=0, description="Number of entries to skip"),
):
    """Return filtered and paginated journal entries, sorted by created_at descending."""
    try:
        wf = _get_workflow()
        journal = list(wf.position_manager._journal)

        # Apply filters
        if entry_type:
            journal = [
                e
                for e in journal
                if e.get("entry_type", "").upper() == entry_type.upper()
            ]

        if position_id is not None:
            journal = [e for e in journal if e.get("position_id") == position_id]

        if instrument:
            journal = [
                e
                for e in journal
                if (e.get("instrument") or "").upper() == instrument.upper()
            ]

        if start_date:
            sd = _parse_date(start_date)
            if sd:
                journal = [
                    e
                    for e in journal
                    if e.get("created_at")
                    and (
                        e["created_at"].date()
                        if isinstance(e["created_at"], datetime)
                        else e["created_at"]
                    )
                    >= sd
                ]

        if end_date:
            ed = _parse_date(end_date)
            if ed:
                journal = [
                    e
                    for e in journal
                    if e.get("created_at")
                    and (
                        e["created_at"].date()
                        if isinstance(e["created_at"], datetime)
                        else e["created_at"]
                    )
                    <= ed
                ]

        # Sort by created_at descending
        journal.sort(key=lambda e: e.get("created_at") or datetime.min, reverse=True)

        # Pagination
        journal = journal[offset : offset + limit]

        return [JournalEntryResponse(**e) for e in journal]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 2. GET /pms/journal/stats/decision-analysis -- decision statistics
# ---------------------------------------------------------------------------
@router.get("/stats/decision-analysis")
async def decision_analysis():
    """Compute decision statistics from all journal entries."""
    try:
        wf = _get_workflow()
        journal = wf.position_manager._journal

        total_entries = len(journal)

        # Count by type
        by_type: dict[str, int] = {}
        for entry in journal:
            et = entry.get("entry_type", "UNKNOWN")
            by_type[et] = by_type.get(et, 0) + 1

        total_opened = by_type.get("OPEN", 0)
        total_closed = by_type.get("CLOSE", 0)
        total_rejections = by_type.get("REJECT", 0)

        # Approval rate: OPEN / (OPEN + REJECT)
        approved_plus_rejected = total_opened + total_rejections
        approval_rate = (
            total_opened / approved_plus_rejected if approved_plus_rejected > 0 else 0.0
        )

        # Average holding days: time between OPEN and CLOSE for same position_id
        open_dates: dict[int, datetime] = {}
        holding_days_list: list[float] = []

        for entry in journal:
            pos_id = entry.get("position_id")
            if pos_id is None:
                continue
            created = entry.get("created_at")
            if created is None:
                continue

            if entry.get("entry_type") == "OPEN":
                open_dates[pos_id] = created
            elif entry.get("entry_type") == "CLOSE" and pos_id in open_dates:
                delta = created - open_dates[pos_id]
                holding_days_list.append(delta.total_seconds() / 86400.0)

        avg_holding_days = (
            sum(holding_days_list) / len(holding_days_list)
            if holding_days_list
            else 0.0
        )

        return {
            "total_entries": total_entries,
            "by_type": by_type,
            "approval_rate": round(approval_rate, 4),
            "avg_holding_days": round(avg_holding_days, 2),
            "total_positions_opened": total_opened,
            "total_positions_closed": total_closed,
            "total_rejections": total_rejections,
        }
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 3. GET /pms/journal/{entry_id} -- single journal entry detail
# ---------------------------------------------------------------------------
@router.get("/{entry_id}", response_model=JournalEntryResponse)
async def get_journal_entry(entry_id: int):
    """Return a single journal entry by ID with full context snapshots."""
    try:
        wf = _get_workflow()
        for entry in wf.position_manager._journal:
            if entry.get("id") == entry_id:
                return JournalEntryResponse(**entry)
        raise HTTPException(
            status_code=404, detail=f"Journal entry {entry_id} not found"
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 4. POST /pms/journal/{entry_id}/outcome -- record outcome as linked NOTE
# ---------------------------------------------------------------------------
@router.post("/{entry_id}/outcome", response_model=JournalEntryResponse)
async def record_outcome(entry_id: int, body: OutcomeRequest):
    """Create a new NOTE journal entry linked to the same position as the original entry.

    Does NOT modify the original locked entry -- creates a new linked NOTE instead.
    """
    try:
        wf = _get_workflow()
        pm = wf.position_manager

        # Find original entry
        original = None
        for entry in pm._journal:
            if entry.get("id") == entry_id:
                original = entry
                break

        if original is None:
            raise HTTPException(
                status_code=404, detail=f"Journal entry {entry_id} not found"
            )

        now = datetime.utcnow()

        # Build content for hash
        system_notes = (
            f"Outcome assessment for entry #{entry_id}: "
            f"{body.realized_pnl_assessment or 'N/A'}"
        )
        journal_content = {
            "entry_type": "NOTE",
            "instrument": original.get("instrument", ""),
            "direction": original.get("direction", ""),
            "notional_brl": original.get("notional_brl", 0.0),
            "entry_price": 0.0,
            "manager_notes": body.outcome_notes,
            "system_notes": system_notes,
        }
        content_hash = pm._compute_content_hash(**journal_content)

        # Create new NOTE entry linked to same position_id
        new_entry = {
            "id": len(pm._journal) + 1,
            "created_at": now,
            "entry_type": "NOTE",
            "position_id": original.get("position_id"),
            "proposal_id": original.get("proposal_id"),
            "instrument": original.get("instrument"),
            "direction": original.get("direction"),
            "notional_brl": original.get("notional_brl"),
            "manager_notes": body.outcome_notes,
            "system_notes": system_notes,
            "market_snapshot": {},
            "portfolio_snapshot": {},
            "content_hash": content_hash,
            "is_locked": True,
        }

        pm._journal.append(new_entry)

        return JournalEntryResponse(**new_entry)
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

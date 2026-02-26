"""PMS Trade Blotter endpoints.

Provides:
- GET  /pms/trades/proposals                        -- list trade proposals
- GET  /pms/trades/proposals/{id}                   -- single proposal detail
- POST /pms/trades/proposals/{id}/approve           -- approve a pending proposal
- POST /pms/trades/proposals/{id}/reject            -- reject a pending proposal
- POST /pms/trades/proposals/{id}/modify-approve    -- modify and approve
- POST /pms/trades/proposals/generate               -- generate proposals from signals
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.schemas.pms_schemas import (
    ApproveProposalRequest,
    GenerateProposalsRequest,
    ModifyApproveRequest,
    RejectProposalRequest,
    TradeProposalResponse,
)
from src.cache import PMSCache, get_pms_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pms/trades", tags=["PMS - Trade Blotter"])

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
    return _workflow


# ---------------------------------------------------------------------------
# 1. GET /pms/trades/proposals
# ---------------------------------------------------------------------------
@router.get("/proposals", response_model=list[TradeProposalResponse])
async def list_proposals(
    status: Optional[str] = Query(
        None, description="Filter by status: PENDING, APPROVED, REJECTED, MODIFIED"
    ),
    date: Optional[str] = Query(None, description="Filter by as_of_date YYYY-MM-DD"),
):
    """Return filtered list of trade proposals."""
    try:
        wf = _get_workflow()
        proposals = list(wf._proposals)

        if status:
            proposals = [
                p for p in proposals if p.get("status", "").upper() == status.upper()
            ]

        if date:
            try:
                filter_date = _parse_date(date)
            except HTTPException:
                raise
            if filter_date:
                proposals = [
                    p
                    for p in proposals
                    if p.get("as_of_date") == filter_date
                ]

        return [TradeProposalResponse(**p) for p in proposals]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 2. GET /pms/trades/proposals/{proposal_id}
# ---------------------------------------------------------------------------
@router.get("/proposals/{proposal_id}", response_model=TradeProposalResponse)
async def get_proposal(proposal_id: int):
    """Return a single trade proposal by ID."""
    try:
        wf = _get_workflow()
        proposal = wf._find_proposal(proposal_id)
        if proposal is None:
            raise HTTPException(
                status_code=404, detail=f"Proposal {proposal_id} not found"
            )
        return TradeProposalResponse(**proposal)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 3. POST /pms/trades/proposals/{proposal_id}/approve
# ---------------------------------------------------------------------------
@router.post(
    "/proposals/{proposal_id}/approve", response_model=TradeProposalResponse
)
async def approve_proposal(
    proposal_id: int,
    body: ApproveProposalRequest,
    cache: PMSCache = Depends(get_pms_cache),
):
    """Approve a pending trade proposal and open a position."""
    try:
        wf = _get_workflow()
        updated = wf.approve_proposal(
            proposal_id=proposal_id,
            execution_price=body.execution_price,
            execution_notional_brl=body.execution_notional_brl,
            manager_notes=body.manager_notes,
            manager_thesis=body.manager_thesis,
            target_price=body.target_price,
            stop_loss=body.stop_loss,
            time_horizon=body.time_horizon,
        )

        # Approving a trade changes the book -- invalidate portfolio cache
        try:
            await cache.invalidate_portfolio_data()
            logger.debug("POST /approve: cache invalidated")
        except Exception:
            logger.warning("POST /approve: cache invalidation failed")

        return TradeProposalResponse(**updated)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 4. POST /pms/trades/proposals/{proposal_id}/reject
# ---------------------------------------------------------------------------
@router.post(
    "/proposals/{proposal_id}/reject", response_model=TradeProposalResponse
)
async def reject_proposal(
    proposal_id: int,
    body: RejectProposalRequest,
    cache: PMSCache = Depends(get_pms_cache),
):
    """Reject a pending trade proposal with mandatory notes."""
    try:
        wf = _get_workflow()
        updated = wf.reject_proposal(
            proposal_id=proposal_id,
            manager_notes=body.manager_notes,
        )

        # Rejecting a trade may affect pending book views -- invalidate
        try:
            await cache.invalidate_portfolio_data()
            logger.debug("POST /reject: cache invalidated")
        except Exception:
            logger.warning("POST /reject: cache invalidation failed")

        return TradeProposalResponse(**updated)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 5. POST /pms/trades/proposals/{proposal_id}/modify-approve
# ---------------------------------------------------------------------------
@router.post(
    "/proposals/{proposal_id}/modify-approve",
    response_model=TradeProposalResponse,
)
async def modify_approve_proposal(
    proposal_id: int,
    body: ModifyApproveRequest,
    cache: PMSCache = Depends(get_pms_cache),
):
    """Modify a pending proposal and approve it, opening a position."""
    try:
        wf = _get_workflow()
        updated = wf.modify_and_approve_proposal(
            proposal_id=proposal_id,
            modified_direction=body.modified_direction,
            modified_notional_brl=body.modified_notional_brl,
            execution_price=body.execution_price,
            manager_notes=body.manager_notes,
        )

        # Modify-approve changes the book -- invalidate portfolio cache
        try:
            await cache.invalidate_portfolio_data()
            logger.debug("POST /modify-approve: cache invalidated")
        except Exception:
            logger.warning("POST /modify-approve: cache invalidation failed")

        return TradeProposalResponse(**updated)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 6. POST /pms/trades/proposals/generate
# ---------------------------------------------------------------------------
@router.post("/proposals/generate", response_model=list[TradeProposalResponse])
async def generate_proposals(body: GenerateProposalsRequest):
    """Generate trade proposals from aggregated signals.

    If no signals are provided, returns an empty list.
    """
    try:
        wf = _get_workflow()

        if not body.signals:
            return []

        created = wf.generate_proposals_from_signals(
            signals=body.signals,
            as_of_date=body.as_of_date,
        )
        return [TradeProposalResponse(**p) for p in created]
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

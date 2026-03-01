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

from src.api.auth import Role, require_role
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
        # Hydrate from DB so in-memory stores have real data
        try:
            from src.pms.db_loader import hydrate_trade_workflow

            hydrate_trade_workflow(_workflow)
            logger.info("TradeWorkflowService hydrated from DB (trades route)")
        except Exception as exc:
            logger.warning("Failed to hydrate TradeWorkflowService: %s", exc)
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
                proposals = [p for p in proposals if p.get("as_of_date") == filter_date]

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
@router.post("/proposals/{proposal_id}/approve", response_model=TradeProposalResponse)
async def approve_proposal(
    proposal_id: int,
    body: ApproveProposalRequest,
    cache: PMSCache = Depends(get_pms_cache),
    user: dict = Depends(require_role(Role.MANAGER)),
):
    """Approve a pending trade proposal and open a position (MANAGER only)."""
    try:
        wf = _get_workflow()

        # Pre-trade risk validation via compliance module
        proposal = wf._find_proposal(proposal_id)
        if proposal is None:
            raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
        try:
            from src.compliance.risk_controls import PreTradeRiskControls

            controls = PreTradeRiskControls()
            notional = body.execution_notional_brl or proposal.get("suggested_notional_brl", 0)
            book = wf.position_manager.get_book()
            check = controls.validate_trade(
                instrument=proposal.get("instrument", ""),
                asset_class=proposal.get("asset_class", ""),
                direction=proposal.get("direction", ""),
                notional_brl=notional,
                portfolio_nav=book["summary"].get("total_nav_brl", 10_000_000.0),
                current_leverage=book["summary"].get("gross_leverage", 0.0),
                current_var_pct=0.0,
                current_drawdown_pct=book["summary"].get("max_drawdown_pct", 0.0),
                asset_class_weights=book.get("by_asset_class", {}),
            )
            if not check["approved"]:
                hard = [c for c in check.get("checks", []) if c.get("hard_block")]
                if hard:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Pre-trade risk check failed: {hard[0].get('reason', 'blocked')}",
                    )
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Pre-trade risk check skipped: %s", exc)

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

        # Audit log
        try:
            from src.compliance.audit import AuditLogger

            AuditLogger().log_event(
                event_type="TRADE_APPROVED",
                details={
                    "proposal_id": proposal_id,
                    "instrument": updated.get("instrument"),
                    "direction": updated.get("direction"),
                    "notional_brl": updated.get("execution_notional_brl"),
                    "user": user.get("sub", "unknown"),
                },
            )
        except Exception:
            logger.warning("Audit log failed for trade approval")

        # Approving a trade changes the book -- invalidate portfolio cache
        try:
            await cache.invalidate_portfolio_data()
            logger.debug("POST /approve: cache invalidated")
        except Exception:
            logger.warning("POST /approve: cache invalidation failed")

        return TradeProposalResponse(**updated)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 4. POST /pms/trades/proposals/{proposal_id}/reject
# ---------------------------------------------------------------------------
@router.post("/proposals/{proposal_id}/reject", response_model=TradeProposalResponse)
async def reject_proposal(
    proposal_id: int,
    body: RejectProposalRequest,
    cache: PMSCache = Depends(get_pms_cache),
    user: dict = Depends(require_role(Role.MANAGER)),
):
    """Reject a pending trade proposal with mandatory notes (MANAGER only)."""
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
    user: dict = Depends(require_role(Role.MANAGER)),
):
    """Modify a pending proposal and approve it (MANAGER only)."""
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

"""PMS Portfolio endpoints.

Provides:
- GET  /pms/book                              -- full portfolio book
- GET  /pms/book/positions                    -- filtered positions list
- POST /pms/book/positions/open               -- open discretionary position
- POST /pms/book/positions/{id}/close         -- close position
- POST /pms/book/positions/{id}/update-price  -- update current price
- POST /pms/mtm                               -- mark all positions to market
- GET  /pms/pnl/summary                       -- P&L summary
- GET  /pms/pnl/equity-curve                  -- P&L timeseries
- GET  /pms/pnl/attribution                   -- P&L attribution by strategy/asset
- GET  /pms/pnl/monthly-heatmap              -- monthly P&L heatmap
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.schemas.pms_schemas import (
    BookResponse,
    BookSummaryResponse,
    ClosePositionRequest,
    MTMRequest,
    OpenPositionRequest,
    PnLPointResponse,
    PositionResponse,
    UpdatePriceRequest,
)
from src.api.auth import Role, require_role
from src.cache import PMSCache, get_pms_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pms", tags=["PMS - Portfolio"])

# ---------------------------------------------------------------------------
# Lazy singleton for TradeWorkflowService
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
            logger.info("TradeWorkflowService hydrated from DB (portfolio route)")
        except Exception as exc:
            logger.warning("Failed to hydrate TradeWorkflowService: %s", exc)
    return _workflow


# ---------------------------------------------------------------------------
# 1. GET /pms/book
# ---------------------------------------------------------------------------
@router.get("/book", response_model=BookResponse)
async def get_book(
    as_of_date: Optional[str] = Query(None, description="Date YYYY-MM-DD"),
    cache: PMSCache = Depends(get_pms_cache),
):
    """Return full portfolio book with summary, positions, and breakdowns."""
    try:
        # Cache-first read (only for default date -- no cache for historical)
        if as_of_date is None:
            try:
                cached = await cache.get_book()
                if cached is not None:
                    logger.debug("GET /book: cache HIT")
                    cached["cached"] = True
                    return cached
            except Exception:
                logger.warning("GET /book: cache read failed, computing fresh")

        wf = _get_workflow()
        ref_date = _parse_date(as_of_date)
        book = wf.position_manager.get_book(as_of_date=ref_date)

        result = BookResponse(
            summary=BookSummaryResponse(**book["summary"]),
            positions=[PositionResponse(**p) for p in book["positions"]],
            by_asset_class=book.get("by_asset_class", {}),
            closed_today=[PositionResponse(**p) for p in book.get("closed_today", [])],
        )

        # Cache the result for default (current) date
        if as_of_date is None:
            try:
                await cache.set_book(result.model_dump(mode="json"))
                logger.debug("GET /book: cache SET")
            except Exception:
                logger.warning("GET /book: cache write failed")

        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 2. GET /pms/book/positions
# ---------------------------------------------------------------------------
@router.get("/book/positions", response_model=list[PositionResponse])
async def get_positions(
    asset_class: Optional[str] = Query(None, description="Filter by asset class"),
    is_open: bool = Query(True, description="Filter by open/closed status"),
):
    """Return filtered list of positions."""
    try:
        wf = _get_workflow()
        positions = wf.position_manager._positions

        filtered = [p for p in positions if p["is_open"] == is_open]
        if asset_class:
            filtered = [
                p
                for p in filtered
                if p.get("asset_class", "").upper() == asset_class.upper()
            ]

        return [PositionResponse(**p) for p in filtered]
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 3. POST /pms/book/positions/open
# ---------------------------------------------------------------------------
@router.post("/book/positions/open", response_model=PositionResponse, status_code=201)
async def open_position(
    body: OpenPositionRequest,
    cache: PMSCache = Depends(get_pms_cache),
    user: dict = Depends(require_role(Role.MANAGER)),
):
    """Open a new discretionary position (MANAGER only)."""
    try:
        wf = _get_workflow()
        result = wf.open_discretionary_trade(
            instrument=body.instrument,
            asset_class=body.asset_class,
            direction=body.direction,
            notional_brl=body.notional_brl,
            execution_price=body.execution_price,
            entry_date=body.entry_date or date.today(),
            manager_thesis=body.manager_thesis,
            target_price=body.target_price,
            stop_loss=body.stop_loss,
            time_horizon=body.time_horizon,
            strategy_ids=body.strategy_ids or None,
        )
        position = result["position"]

        # Write-through: invalidate + refresh book cache
        try:
            await cache.invalidate_portfolio_data()
            new_book = wf.position_manager.get_book()
            await cache.refresh_book(new_book)
            logger.debug("POST /open: cache invalidated and refreshed")
        except Exception:
            logger.warning("POST /open: cache refresh failed")

        return PositionResponse(**position)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 4. POST /pms/book/positions/{position_id}/close
# ---------------------------------------------------------------------------
@router.post("/book/positions/{position_id}/close", response_model=PositionResponse)
async def close_position(
    position_id: int,
    body: ClosePositionRequest,
    cache: PMSCache = Depends(get_pms_cache),
    user: dict = Depends(require_role(Role.MANAGER)),
):
    """Close an open position (MANAGER only)."""
    try:
        wf = _get_workflow()
        closed = wf.close_position(
            position_id=position_id,
            close_price=body.close_price,
            close_date=body.close_date,
            manager_notes=body.manager_notes,
            outcome_notes=body.outcome_notes,
        )

        # Write-through: invalidate + refresh book cache
        try:
            await cache.invalidate_portfolio_data()
            new_book = wf.position_manager.get_book()
            await cache.refresh_book(new_book)
            logger.debug("POST /close: cache invalidated and refreshed")
        except Exception:
            logger.warning("POST /close: cache refresh failed")

        return PositionResponse(**closed)
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 5. POST /pms/book/positions/{position_id}/update-price
# ---------------------------------------------------------------------------
@router.post(
    "/book/positions/{position_id}/update-price", response_model=PositionResponse
)
async def update_price(
    position_id: int,
    body: UpdatePriceRequest,
    cache: PMSCache = Depends(get_pms_cache),
):
    """Manually update the current price of a position."""
    try:
        wf = _get_workflow()
        position = wf.position_manager._find_position(position_id)
        if position is None:
            raise HTTPException(
                status_code=404, detail=f"Position {position_id} not found"
            )

        position["current_price"] = body.price
        position["updated_at"] = datetime.now(tz=timezone.utc)

        # Write-through: invalidate + refresh book cache
        try:
            await cache.invalidate_portfolio_data()
            new_book = wf.position_manager.get_book()
            await cache.refresh_book(new_book)
            logger.debug("POST /update-price: cache invalidated and refreshed")
        except Exception:
            logger.warning("POST /update-price: cache refresh failed")

        return PositionResponse(**position)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 6. POST /pms/mtm
# ---------------------------------------------------------------------------
@router.post("/mtm")
async def run_mark_to_market(
    body: MTMRequest,
    cache: PMSCache = Depends(get_pms_cache),
    user: dict = Depends(require_role(Role.MANAGER)),
):
    """Mark all open positions to market (MANAGER only)."""
    try:
        wf = _get_workflow()
        updated = wf.position_manager.mark_to_market(
            price_overrides=body.price_overrides or None,
            current_fx_rate=body.fx_rate,
        )

        # Write-through: invalidate + refresh book cache after MTM
        try:
            await cache.invalidate_portfolio_data()
            new_book = wf.position_manager.get_book()
            await cache.refresh_book(new_book)
            logger.debug("POST /mtm: cache invalidated and refreshed")
        except Exception:
            logger.warning("POST /mtm: cache refresh failed")

        return {
            "status": "ok",
            "updated_count": len(updated),
            "positions": [PositionResponse(**p) for p in updated],
        }
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 7. GET /pms/pnl/summary
# ---------------------------------------------------------------------------
@router.get("/pnl/summary")
async def pnl_summary(
    as_of_date: Optional[str] = Query(None, description="Date YYYY-MM-DD"),
):
    """Return P&L summary from the portfolio book."""
    try:
        wf = _get_workflow()
        ref_date = _parse_date(as_of_date)
        book = wf.position_manager.get_book(as_of_date=ref_date)
        return {"status": "ok", "data": book["summary"]}
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 8. GET /pms/pnl/equity-curve
# ---------------------------------------------------------------------------
@router.get("/pnl/equity-curve", response_model=list[PnLPointResponse])
async def pnl_equity_curve(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
):
    """Return P&L timeseries for equity curve plotting."""
    try:
        wf = _get_workflow()
        sd = _parse_date(start_date)
        ed = _parse_date(end_date)
        timeseries = wf.position_manager.get_pnl_timeseries(start_date=sd, end_date=ed)
        return [PnLPointResponse(**point) for point in timeseries]
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 9. GET /pms/pnl/attribution
# ---------------------------------------------------------------------------
@router.get("/pnl/attribution")
async def pnl_attribution():
    """Return P&L attribution grouped by strategy, asset class, and instrument."""
    try:
        wf = _get_workflow()
        pm = wf.position_manager

        all_positions = pm._positions
        by_strategy: dict[str, float] = defaultdict(float)
        by_asset_class: dict[str, float] = defaultdict(float)
        by_instrument: dict[str, float] = defaultdict(float)

        for pos in all_positions:
            pnl = (pos.get("unrealized_pnl_brl") or 0.0) + (
                pos.get("realized_pnl_brl") or 0.0
            )
            instrument = pos.get("instrument", "UNKNOWN")
            asset_class = pos.get("asset_class", "UNKNOWN")

            by_instrument[instrument] += pnl
            by_asset_class[asset_class] += pnl

            strategy_ids = pos.get("strategy_ids") or []
            if strategy_ids:
                per_strategy_pnl = pnl / len(strategy_ids)
                for sid in strategy_ids:
                    by_strategy[sid] += per_strategy_pnl
            else:
                by_strategy["unattributed"] += pnl

        return {
            "status": "ok",
            "data": {
                "by_strategy": {k: round(v, 2) for k, v in by_strategy.items()},
                "by_asset_class": {k: round(v, 2) for k, v in by_asset_class.items()},
                "by_instrument": {k: round(v, 2) for k, v in by_instrument.items()},
            },
        }
    except Exception as exc:
        logger.error("%s error: %s", __name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 10. GET /pms/pnl/monthly-heatmap
# ---------------------------------------------------------------------------
@router.get("/pnl/monthly-heatmap")
async def pnl_monthly_heatmap():
    """Return aggregated monthly P&L for heatmap display."""
    try:
        wf = _get_workflow()
        pm = wf.position_manager

        monthly: dict[tuple[int, int], float] = defaultdict(float)
        for snap in pm._pnl_history:
            snap_date = snap.get("snapshot_date")
            if not snap_date or not isinstance(snap_date, date):
                continue
            key = (snap_date.year, snap_date.month)
            monthly[key] += snap.get("daily_pnl_brl") or 0.0

        months = sorted(
            [
                {"year": year, "month": month, "pnl_brl": round(pnl, 2)}
                for (year, month), pnl in monthly.items()
            ],
            key=lambda m: (m["year"], m["month"]),
        )

        return {"status": "ok", "data": {"months": months}}
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

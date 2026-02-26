"""FastAPI TestClient integration tests for the PMS API.

20 tests verifying the full PMS workflow end-to-end:
  - Portfolio book (empty, open, close, MTM, P&L)
  - Trade proposals (generate, approve, reject)
  - Decision journal (listing, statistics)
  - Morning Pack (generate, latest, history)
  - Risk Monitor (live, trend, limits)
  - Attribution (period, equity curve)

All tests use an in-memory TradeWorkflowService with no DB dependency.
A fresh singleton is injected per test via the ``client`` fixture.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.pms_attribution import router as pms_attribution_router
from src.api.routes.pms_briefing import router as pms_briefing_router
from src.api.routes.pms_journal import router as pms_journal_router
from src.api.routes.pms_portfolio import router as pms_portfolio_router
from src.api.routes.pms_risk import router as pms_risk_router
from src.api.routes.pms_trades import router as pms_trades_router

# -------------------------------------------------------------------------
# Sample data
# -------------------------------------------------------------------------
SAMPLE_SIGNALS = [
    {
        "instrument": "DI1_F27",
        "asset_class": "RATES",
        "direction": "LONG",
        "conviction": 0.75,
        "strategy_ids": ["RATES-01"],
        "signal_source": "aggregator",
    },
    {
        "instrument": "USDBRL",
        "asset_class": "FX",
        "direction": "SHORT",
        "conviction": 0.60,
        "strategy_ids": ["FX-01"],
        "signal_source": "aggregator",
    },
]


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
def _create_test_app() -> FastAPI:
    """Create minimal FastAPI app with PMS routers only (no DB)."""
    app = FastAPI(title="PMS Test")
    app.include_router(pms_portfolio_router, prefix="/api/v1")
    app.include_router(pms_trades_router, prefix="/api/v1")
    app.include_router(pms_journal_router, prefix="/api/v1")
    app.include_router(pms_briefing_router, prefix="/api/v1")
    app.include_router(pms_risk_router, prefix="/api/v1")
    app.include_router(pms_attribution_router, prefix="/api/v1")
    return app


# -------------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------------
@pytest.fixture
def client():
    """Fresh TestClient with reset PMS state for each test."""
    import src.api.routes.pms_attribution as attribution_mod
    import src.api.routes.pms_briefing as briefing_mod
    import src.api.routes.pms_journal as journal_mod
    import src.api.routes.pms_portfolio as pms_mod
    import src.api.routes.pms_risk as risk_mod
    import src.api.routes.pms_trades as trades_mod

    # Create fresh workflow for test isolation
    from src.pms import PositionManager, TradeWorkflowService
    from src.pms.attribution import PerformanceAttributionEngine
    from src.pms.morning_pack import MorningPackService
    from src.pms.risk_monitor import RiskMonitorService

    pm = PositionManager()
    fresh_workflow = TradeWorkflowService(position_manager=pm)

    pms_mod._workflow = fresh_workflow
    trades_mod._workflow = fresh_workflow
    journal_mod._workflow = fresh_workflow

    # Inject fresh services sharing the same PositionManager
    briefing_mod._service = MorningPackService(
        position_manager=pm, trade_workflow=fresh_workflow
    )
    risk_mod._service = RiskMonitorService(position_manager=pm)
    attribution_mod._service = PerformanceAttributionEngine(position_manager=pm)

    app = _create_test_app()
    with TestClient(app) as c:
        yield c

    # Cleanup: reset singletons so other tests are unaffected
    pms_mod._workflow = None
    trades_mod._workflow = None
    journal_mod._workflow = None
    briefing_mod._service = None
    risk_mod._service = None
    attribution_mod._service = None


# =========================================================================
# 1. Portfolio — empty book
# =========================================================================
def test_get_book_empty(client: TestClient):
    """GET /api/v1/pms/book returns an empty book with 0 positions."""
    resp = client.get("/api/v1/pms/book")
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]["open_positions"] == 0
    assert data["positions"] == []


# =========================================================================
# 2. Portfolio — open discretionary position
# =========================================================================
def test_open_discretionary_position(client: TestClient):
    """POST /api/v1/pms/book/positions/open returns 201 with the new position."""
    body = {
        "instrument": "DI1_F27",
        "asset_class": "RATES",
        "direction": "LONG",
        "notional_brl": 10_000_000,
        "execution_price": 85.5,
        "manager_thesis": "Expect rate cuts in 2027 cycle",
    }
    resp = client.post("/api/v1/pms/book/positions/open", json=body)
    assert resp.status_code == 201
    pos = resp.json()
    assert pos["instrument"] == "DI1_F27"
    assert pos["direction"] == "LONG"
    assert pos["is_open"] is True
    assert pos["id"] >= 1


# =========================================================================
# 3. Portfolio — validation error (missing manager_thesis)
# =========================================================================
def test_open_position_validation_error(client: TestClient):
    """POST without required manager_thesis returns 422."""
    body = {
        "instrument": "DI1_F27",
        "asset_class": "RATES",
        "direction": "LONG",
        "notional_brl": 10_000_000,
        "execution_price": 85.5,
        # manager_thesis omitted intentionally
    }
    resp = client.post("/api/v1/pms/book/positions/open", json=body)
    assert resp.status_code == 422


# =========================================================================
# 4. Trade Blotter — generate and list proposals
# =========================================================================
def test_generate_and_list_proposals(client: TestClient):
    """POST generate + GET proposals returns the generated proposals."""
    gen_resp = client.post(
        "/api/v1/pms/trades/proposals/generate",
        json={"signals": SAMPLE_SIGNALS},
    )
    assert gen_resp.status_code == 200
    proposals = gen_resp.json()
    assert len(proposals) == 2

    list_resp = client.get("/api/v1/pms/trades/proposals")
    assert list_resp.status_code == 200
    all_proposals = list_resp.json()
    assert len(all_proposals) == 2


# =========================================================================
# 5. Trade Blotter — approve proposal flow
# =========================================================================
def test_approve_proposal_flow(client: TestClient):
    """Generate a proposal, approve it, and verify position is created."""
    # Generate
    client.post(
        "/api/v1/pms/trades/proposals/generate",
        json={"signals": SAMPLE_SIGNALS},
    )

    # Approve first proposal (DI1_F27, highest conviction)
    approve_resp = client.post(
        "/api/v1/pms/trades/proposals/1/approve",
        json={
            "execution_price": 86.0,
            "execution_notional_brl": 10_000_000,
            "manager_notes": "Aligned with macro view",
        },
    )
    assert approve_resp.status_code == 200
    approved = approve_resp.json()
    assert approved["status"] == "APPROVED"
    assert approved["position_id"] is not None

    # Verify position shows up in book
    book_resp = client.get("/api/v1/pms/book")
    assert book_resp.status_code == 200
    book = book_resp.json()
    assert book["summary"]["open_positions"] >= 1


# =========================================================================
# 6. Trade Blotter — reject proposal flow
# =========================================================================
def test_reject_proposal_flow(client: TestClient):
    """Generate a proposal, reject it with notes, and verify REJECTED status."""
    client.post(
        "/api/v1/pms/trades/proposals/generate",
        json={"signals": SAMPLE_SIGNALS},
    )

    reject_resp = client.post(
        "/api/v1/pms/trades/proposals/1/reject",
        json={"manager_notes": "Risk budget exceeded for RATES positions"},
    )
    assert reject_resp.status_code == 200
    rejected = reject_resp.json()
    assert rejected["status"] == "REJECTED"


# =========================================================================
# 7. Trade Blotter — reject without notes fails
# =========================================================================
def test_reject_without_notes_fails(client: TestClient):
    """Reject with notes shorter than min_length returns 422."""
    client.post(
        "/api/v1/pms/trades/proposals/generate",
        json={"signals": SAMPLE_SIGNALS},
    )

    # RejectProposalRequest has min_length=3; send only 2 characters
    reject_resp = client.post(
        "/api/v1/pms/trades/proposals/1/reject",
        json={"manager_notes": "No"},
    )
    assert reject_resp.status_code == 422


# =========================================================================
# 8. Portfolio — close position flow
# =========================================================================
def test_close_position_flow(client: TestClient):
    """Open then close a position, verifying realized P&L is present."""
    # Open
    open_resp = client.post(
        "/api/v1/pms/book/positions/open",
        json={
            "instrument": "USDBRL",
            "asset_class": "FX",
            "direction": "LONG",
            "notional_brl": 5_000_000,
            "execution_price": 5.10,
            "manager_thesis": "USD strengthening thesis",
        },
    )
    assert open_resp.status_code == 201
    pos_id = open_resp.json()["id"]

    # Close
    close_resp = client.post(
        f"/api/v1/pms/book/positions/{pos_id}/close",
        json={"close_price": 5.20},
    )
    assert close_resp.status_code == 200
    closed = close_resp.json()
    assert closed["is_open"] is False
    assert closed["realized_pnl_brl"] is not None


# =========================================================================
# 9. Decision Journal — entries from open + close
# =========================================================================
def test_journal_entries(client: TestClient):
    """Open then close a position; GET /pms/journal/ shows OPEN and CLOSE entries."""
    # Open
    open_resp = client.post(
        "/api/v1/pms/book/positions/open",
        json={
            "instrument": "DI1_F27",
            "asset_class": "RATES",
            "direction": "LONG",
            "notional_brl": 10_000_000,
            "execution_price": 85.5,
            "manager_thesis": "Rate-cut expectation",
        },
    )
    assert open_resp.status_code == 201
    pos_id = open_resp.json()["id"]

    # Close
    close_resp = client.post(
        f"/api/v1/pms/book/positions/{pos_id}/close",
        json={"close_price": 86.0},
    )
    assert close_resp.status_code == 200

    # Query journal
    journal_resp = client.get("/api/v1/pms/journal/")
    assert journal_resp.status_code == 200
    entries = journal_resp.json()

    entry_types = {e["entry_type"] for e in entries}
    assert "OPEN" in entry_types
    assert "CLOSE" in entry_types
    assert len(entries) >= 2


# =========================================================================
# 10. Decision Journal — statistics
# =========================================================================
def test_journal_stats(client: TestClient):
    """After open, close, and reject operations, stats reflect correct counts."""
    # Open a position
    client.post(
        "/api/v1/pms/book/positions/open",
        json={
            "instrument": "DI1_F27",
            "asset_class": "RATES",
            "direction": "LONG",
            "notional_brl": 10_000_000,
            "execution_price": 85.5,
            "manager_thesis": "Rate view thesis",
        },
    )

    # Close the position
    client.post(
        "/api/v1/pms/book/positions/1/close",
        json={"close_price": 86.0},
    )

    # Generate proposals (IDs start at 2 since discretionary trade created proposal 1)
    gen_resp = client.post(
        "/api/v1/pms/trades/proposals/generate",
        json={"signals": SAMPLE_SIGNALS},
    )
    proposals = gen_resp.json()
    # Reject the first generated proposal (highest conviction)
    reject_id = proposals[0]["id"]
    client.post(
        f"/api/v1/pms/trades/proposals/{reject_id}/reject",
        json={"manager_notes": "Exceeds risk budget for the week"},
    )

    # Query stats
    stats_resp = client.get("/api/v1/pms/journal/stats/decision-analysis")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_entries"] >= 3  # OPEN + CLOSE + REJECT at minimum
    assert stats["total_positions_opened"] >= 1
    assert stats["total_positions_closed"] >= 1
    assert stats["total_rejections"] >= 1
    assert 0.0 <= stats["approval_rate"] <= 1.0


# =========================================================================
# 11. Portfolio — P&L summary
# =========================================================================
def test_pnl_summary(client: TestClient):
    """GET /api/v1/pms/pnl/summary returns a summary dict."""
    resp = client.get("/api/v1/pms/pnl/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "data" in data
    assert "aum" in data["data"]


# =========================================================================
# 12. Portfolio — mark-to-market endpoint
# =========================================================================
def test_mtm_endpoint(client: TestClient):
    """POST /api/v1/pms/book/mtm updates open positions."""
    # Open a position first
    client.post(
        "/api/v1/pms/book/positions/open",
        json={
            "instrument": "USDBRL",
            "asset_class": "FX",
            "direction": "LONG",
            "notional_brl": 5_000_000,
            "execution_price": 5.10,
            "manager_thesis": "FX exposure thesis",
        },
    )

    # Run MTM with price override (endpoint is /pms/mtm, not /pms/book/mtm)
    mtm_resp = client.post(
        "/api/v1/pms/mtm",
        json={"price_overrides": {"USDBRL": 5.20}, "fx_rate": 5.20},
    )
    assert mtm_resp.status_code == 200
    mtm = mtm_resp.json()
    assert mtm["status"] == "ok"
    assert mtm["updated_count"] >= 1


# =========================================================================
# 13. Morning Pack — generate
# =========================================================================
def test_morning_pack_generate(client: TestClient):
    """POST /api/v1/pms/morning-pack/generate creates and returns a briefing."""
    resp = client.post(
        "/api/v1/pms/morning-pack/generate",
        json={},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert "briefing_date" in data
    assert "created_at" in data
    assert "action_items" in data
    assert "trade_proposals" in data
    assert "market_snapshot" in data
    assert "agent_views" in data
    assert "regime" in data
    assert "top_signals" in data
    assert "signal_changes" in data
    assert "portfolio_state" in data
    assert "macro_narrative" in data


# =========================================================================
# 14. Morning Pack — latest
# =========================================================================
def test_morning_pack_latest(client: TestClient):
    """Generate a briefing, then GET /api/v1/pms/morning-pack/latest."""
    # First generate
    gen_resp = client.post(
        "/api/v1/pms/morning-pack/generate",
        json={},
    )
    assert gen_resp.status_code == 200

    # Then get latest
    resp = client.get("/api/v1/pms/morning-pack/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert "briefing_date" in data
    assert "action_items" in data


# =========================================================================
# 15. Morning Pack — history
# =========================================================================
def test_morning_pack_history(client: TestClient):
    """GET /api/v1/pms/morning-pack/history returns a list."""
    resp = client.get("/api/v1/pms/morning-pack/history?days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


# =========================================================================
# 16. Risk Monitor — live
# =========================================================================
def test_risk_live(client: TestClient):
    """GET /api/v1/pms/risk/live returns a complete risk snapshot."""
    resp = client.get("/api/v1/pms/risk/live")
    assert resp.status_code == 200
    data = resp.json()
    assert "as_of_date" in data
    assert "var" in data
    assert "leverage" in data
    assert "drawdown" in data
    assert "concentration" in data
    assert "alerts" in data


# =========================================================================
# 17. Risk Monitor — trend
# =========================================================================
def test_risk_trend(client: TestClient):
    """GET /api/v1/pms/risk/trend returns a list of trend points."""
    resp = client.get("/api/v1/pms/risk/trend?days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


# =========================================================================
# 18. Risk Monitor — limits
# =========================================================================
def test_risk_limits(client: TestClient):
    """GET /api/v1/pms/risk/limits returns limits configuration."""
    resp = client.get("/api/v1/pms/risk/limits")
    assert resp.status_code == 200
    data = resp.json()
    assert "config" in data
    assert "limits_summary" in data
    assert "var_95_limit_pct" in data["config"]
    assert "gross_leverage_limit" in data["config"]


# =========================================================================
# 19. Attribution — period
# =========================================================================
def test_attribution(client: TestClient):
    """GET /api/v1/pms/attribution?period=MTD returns attribution data."""
    resp = client.get("/api/v1/pms/attribution?period=MTD")
    assert resp.status_code == 200
    data = resp.json()
    assert "period" in data
    assert "total_pnl_brl" in data
    assert "by_strategy" in data
    assert "by_asset_class" in data


# =========================================================================
# 20. Attribution — equity curve
# =========================================================================
def test_attribution_equity_curve(client: TestClient):
    """GET /api/v1/pms/attribution/equity-curve returns a list."""
    resp = client.get("/api/v1/pms/attribution/equity-curve")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)

"""Tests for MorningPackService daily briefing generation.

Verifies:
- Complete briefing generation with all 9 sections
- Action-first ordering (action_items is first section key)
- Graceful degradation when all components are None
- Auto-persistence across multiple briefings
- Action item prioritization (CRITICAL before LOW)
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from src.pms.morning_pack import MorningPackService
from src.pms.position_manager import PositionManager
from src.pms.trade_workflow import TradeWorkflowService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def position_manager() -> PositionManager:
    """Create a PositionManager with a sample position."""
    pm = PositionManager()
    pm.open_position(
        instrument="DI1_F27",
        asset_class="RATES",
        direction="LONG",
        notional_brl=10_000_000.0,
        entry_price=11.50,
        entry_date=date(2026, 2, 20),
        strategy_ids=["RATES_BR_01"],
    )
    return pm


@pytest.fixture
def trade_workflow(position_manager: PositionManager) -> TradeWorkflowService:
    """Create a TradeWorkflowService with a pending proposal."""
    tw = TradeWorkflowService(position_manager=position_manager)
    tw.generate_proposals_from_signals(
        signals=[
            {
                "instrument": "USDBRL",
                "asset_class": "FX",
                "direction": "SHORT",
                "conviction": 0.72,
                "strategy_ids": ["FX_BR_01"],
                "signal_source": "aggregator",
            }
        ],
        as_of_date=date(2026, 2, 24),
    )
    return tw


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMorningPackGeneration:
    """Test MorningPackService.generate() produces complete briefings."""

    def test_generate_morning_pack(
        self,
        position_manager: PositionManager,
        trade_workflow: TradeWorkflowService,
    ) -> None:
        """Generate a briefing with real components and verify all 9 sections."""
        service = MorningPackService(
            position_manager=position_manager,
            trade_workflow=trade_workflow,
        )

        briefing = service.generate(briefing_date=date(2026, 2, 24))

        # All 9 content sections must be present
        expected_sections = [
            "action_items",
            "trade_proposals",
            "market_snapshot",
            "agent_views",
            "regime",
            "top_signals",
            "signal_changes",
            "portfolio_state",
            "macro_narrative",
        ]
        for section in expected_sections:
            assert section in briefing, f"Missing section: {section}"

        # Metadata fields
        assert "id" in briefing
        assert "briefing_date" in briefing
        assert briefing["briefing_date"] == date(2026, 2, 24)
        assert "created_at" in briefing

        # Action-first ordering: action_items should be the first content key
        # (after id, briefing_date, created_at which are metadata)
        content_keys = [
            k for k in briefing.keys()
            if k not in ("id", "briefing_date", "created_at")
        ]
        assert content_keys[0] == "action_items", (
            f"Expected action_items as first content key, got {content_keys[0]}"
        )
        assert content_keys[1] == "trade_proposals", (
            f"Expected trade_proposals as second content key, got {content_keys[1]}"
        )

        # Trade proposals should contain our pending proposal
        proposals = briefing["trade_proposals"]
        assert isinstance(proposals, list)
        assert len(proposals) >= 1
        assert proposals[0]["instrument"] == "USDBRL"

        # Portfolio state should have the position
        pstate = briefing["portfolio_state"]
        assert isinstance(pstate, dict)
        assert "summary" in pstate
        assert pstate["summary"]["open_positions"] >= 1

        # Market snapshot should have the placeholder structure
        snapshot = briefing["market_snapshot"]
        assert isinstance(snapshot, dict)
        for group in ["brazil_rates", "brazil_macro", "fx", "us_rates", "us_macro", "global_", "credit"]:
            assert group in snapshot

        # Macro narrative should be a non-empty string
        narrative = briefing["macro_narrative"]
        assert isinstance(narrative, str)
        assert len(narrative) > 100  # Should be a multi-paragraph narrative

    def test_graceful_degradation(self) -> None:
        """Generate a briefing with None for all optional components."""
        service = MorningPackService()  # All None

        briefing = service.generate(briefing_date=date(2026, 2, 24))

        # All 9 sections still present
        expected_sections = [
            "action_items",
            "trade_proposals",
            "market_snapshot",
            "agent_views",
            "regime",
            "top_signals",
            "signal_changes",
            "portfolio_state",
            "macro_narrative",
        ]
        for section in expected_sections:
            assert section in briefing, f"Missing section: {section}"

        # Unavailable sections should be dicts with "status": "unavailable"
        proposals = briefing["trade_proposals"]
        assert isinstance(proposals, dict)
        assert proposals["status"] == "unavailable"

        pstate = briefing["portfolio_state"]
        assert isinstance(pstate, dict)
        assert pstate["status"] == "unavailable"

        top_signals = briefing["top_signals"]
        assert isinstance(top_signals, dict)
        assert top_signals["status"] == "unavailable"

        signal_changes = briefing["signal_changes"]
        assert isinstance(signal_changes, dict)
        assert signal_changes["status"] == "unavailable"

        # Market snapshot is always a dict structure (no dependency)
        snapshot = briefing["market_snapshot"]
        assert isinstance(snapshot, dict)
        assert "brazil_rates" in snapshot

        # Narrative should still be generated (template fallback)
        narrative = briefing["macro_narrative"]
        assert isinstance(narrative, str)
        assert len(narrative) > 50

        # Action items should include stale data warnings
        action_items = briefing["action_items"]
        assert isinstance(action_items, list)
        stale_items = [
            ai for ai in action_items if ai["category"] == "stale_data"
        ]
        assert len(stale_items) >= 1, "Expected stale data warnings for unavailable sections"

    def test_auto_persist(
        self,
        position_manager: PositionManager,
        trade_workflow: TradeWorkflowService,
    ) -> None:
        """Generate two briefings and verify auto-persistence."""
        service = MorningPackService(
            position_manager=position_manager,
            trade_workflow=trade_workflow,
        )

        b1 = service.generate(briefing_date=date(2026, 2, 23))
        b2 = service.generate(briefing_date=date(2026, 2, 24))

        assert len(service._briefings) == 2
        assert service._briefings[0]["briefing_date"] == date(2026, 2, 23)
        assert service._briefings[1]["briefing_date"] == date(2026, 2, 24)

        # get_latest returns the most recent
        latest = service.get_latest()
        assert latest is not None
        assert latest["briefing_date"] == date(2026, 2, 24)

        # get_by_date returns the correct one
        found = service.get_by_date(date(2026, 2, 23))
        assert found is not None
        assert found["briefing_date"] == date(2026, 2, 23)

        # Generating again for same date without force returns existing
        b2_again = service.generate(briefing_date=date(2026, 2, 24))
        assert len(service._briefings) == 2  # No new entry
        assert b2_again["id"] == b2["id"]

        # get_history returns summaries
        history = service.get_history(days=10)
        assert len(history) == 2
        assert all("briefing_date" in h for h in history)
        assert all("action_items_count" in h for h in history)

    def test_action_items_prioritization(
        self,
        position_manager: PositionManager,
    ) -> None:
        """Set up a scenario with trade proposals and risk warnings, verify sorting."""
        tw = TradeWorkflowService(position_manager=position_manager)

        # Create a flip proposal (CRITICAL priority) -- position is LONG RATES
        # so a SHORT on the same instrument with high conviction is a flip
        tw.generate_proposals_from_signals(
            signals=[
                {
                    "instrument": "DI1_F27",
                    "asset_class": "RATES",
                    "direction": "SHORT",
                    "conviction": 0.85,
                    "strategy_ids": ["RATES_BR_02"],
                    "signal_source": "aggregator",
                },
                {
                    "instrument": "USDBRL",
                    "asset_class": "FX",
                    "direction": "SHORT",
                    "conviction": 0.60,
                    "strategy_ids": ["FX_BR_01"],
                    "signal_source": "aggregator",
                },
            ],
            as_of_date=date(2026, 2, 24),
        )

        service = MorningPackService(
            position_manager=position_manager,
            trade_workflow=tw,
        )

        briefing = service.generate(briefing_date=date(2026, 2, 24))

        action_items = briefing["action_items"]
        assert isinstance(action_items, list)
        assert len(action_items) >= 2

        # Verify sorting: CRITICAL should come before MEDIUM/LOW
        priorities = [ai["priority"] for ai in action_items]
        # Check that the first item is CRITICAL (flip proposal)
        assert priorities[0] == "CRITICAL", (
            f"Expected CRITICAL as first priority, got {priorities[0]}"
        )

        # Verify priority ordering is non-decreasing
        priority_values = [
            {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(p, 99)
            for p in priorities
        ]
        for i in range(len(priority_values) - 1):
            assert priority_values[i] <= priority_values[i + 1], (
                f"Action items not sorted by priority at index {i}: "
                f"{priorities[i]} > {priorities[i+1]}"
            )

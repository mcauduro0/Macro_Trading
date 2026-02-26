"""Comprehensive tests for TradeWorkflowService.

All tests use pure in-memory TradeWorkflowService (no DB dependency).
14 tests covering signal-to-proposal pipeline, approval/reject/modify workflow,
discretionary trades, position closing, and flip signal detection.
"""

from datetime import date

import pytest

from src.pms.position_manager import PositionManager
from src.pms.trade_workflow import TradeWorkflowService

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def pm() -> PositionManager:
    """Fresh PositionManager with 100M BRL AUM."""
    return PositionManager(aum=100_000_000.0)


@pytest.fixture
def tws(pm: PositionManager) -> TradeWorkflowService:
    """Fresh TradeWorkflowService backed by a 100M AUM PositionManager."""
    return TradeWorkflowService(position_manager=pm)


@pytest.fixture
def sample_signals() -> list[dict]:
    """Sample aggregated signals for testing."""
    return [
        {
            "instrument": "DI1_F26",
            "asset_class": "RATES",
            "direction": "LONG",
            "conviction": 0.85,
            "strategy_ids": ["RATES-01", "RATES-02"],
            "signal_source": "aggregator",
            "suggested_notional_brl": 20_000_000.0,
        },
        {
            "instrument": "USDBRL",
            "asset_class": "FX",
            "direction": "SHORT",
            "conviction": 0.70,
            "strategy_ids": ["FX-01"],
            "signal_source": "aggregator",
            "suggested_notional_brl": 15_000_000.0,
        },
        {
            "instrument": "CDS_BR_5Y",
            "asset_class": "CREDIT",
            "direction": "LONG",
            "conviction": 0.60,
            "strategy_ids": ["CROSS-01"],
            "signal_source": "aggregator",
            "suggested_notional_brl": 10_000_000.0,
        },
    ]


@pytest.fixture
def low_conviction_signals() -> list[dict]:
    """Signals with conviction below threshold."""
    return [
        {
            "instrument": "IBOV_FUT",
            "asset_class": "EQUITY",
            "direction": "LONG",
            "conviction": 0.30,
            "strategy_ids": ["EQ-01"],
            "signal_source": "aggregator",
        },
        {
            "instrument": "NTN-B_2030",
            "asset_class": "SOVEREIGN",
            "direction": "SHORT",
            "conviction": 0.50,
            "strategy_ids": ["SOV-01"],
            "signal_source": "aggregator",
        },
    ]


# =============================================================================
# generate_proposals_from_signals tests
# =============================================================================


class TestGenerateProposals:
    """Tests for TradeWorkflowService.generate_proposals_from_signals."""

    def test_generate_proposals_filters_low_conviction(
        self, tws: TradeWorkflowService, low_conviction_signals: list[dict]
    ):
        """Signals with conviction < 0.55 are excluded."""
        proposals = tws.generate_proposals_from_signals(low_conviction_signals)
        assert len(proposals) == 0
        assert len(tws._proposals) == 0

    def test_generate_proposals_respects_max_limit(self, tws: TradeWorkflowService):
        """Max 5 proposals even with 8 qualifying signals."""
        signals = [
            {
                "instrument": f"INST_{i}",
                "asset_class": "EQUITY",
                "direction": "LONG",
                "conviction": 0.60 + i * 0.01,
                "strategy_ids": [f"STR-{i}"],
                "signal_source": "aggregator",
            }
            for i in range(8)
        ]
        proposals = tws.generate_proposals_from_signals(signals)
        assert len(proposals) == 5
        assert len(tws._proposals) == 5

    def test_generate_proposals_sorts_by_conviction(
        self, tws: TradeWorkflowService, sample_signals: list[dict]
    ):
        """Highest conviction first."""
        proposals = tws.generate_proposals_from_signals(sample_signals)
        convictions = [p["conviction"] for p in proposals]
        assert convictions == sorted(convictions, reverse=True)
        assert proposals[0]["conviction"] == 0.85

    def test_generate_proposals_creates_rationale_and_risk_impact(
        self, tws: TradeWorkflowService, sample_signals: list[dict]
    ):
        """Each proposal has non-empty rationale and risk_impact dict."""
        proposals = tws.generate_proposals_from_signals(sample_signals)
        for p in proposals:
            assert p["rationale"]
            assert isinstance(p["rationale"], str)
            assert len(p["rationale"]) > 0
            assert isinstance(p["risk_impact"], dict)
            assert "estimated_leverage_delta" in p["risk_impact"]
            assert "current_open_positions" in p["risk_impact"]
            assert "same_instrument_exposure" in p["risk_impact"]
            assert "asset_class_concentration" in p["risk_impact"]


# =============================================================================
# approve_proposal tests
# =============================================================================


class TestApproveProposal:
    """Tests for TradeWorkflowService.approve_proposal."""

    def test_approve_proposal_creates_position(
        self, tws: TradeWorkflowService, sample_signals: list[dict]
    ):
        """Approve returns proposal with position_id set, and position exists in PM."""
        tws.generate_proposals_from_signals(sample_signals)
        proposal = tws.approve_proposal(
            proposal_id=1,
            execution_price=90000.0,
            execution_notional_brl=20_000_000.0,
            manager_notes="Confirmed by PM",
        )
        assert proposal["status"] == "APPROVED"
        assert proposal["position_id"] is not None
        assert proposal["position_id"] == 1

        # Verify position exists in position_manager
        pos = tws.position_manager._find_position(proposal["position_id"])
        assert pos is not None
        assert pos["instrument"] == "DI1_F26"
        assert pos["is_open"] is True

        # Verify journal entry has proposal_id linked
        journal_entries = [
            j for j in tws.position_manager._journal if j.get("proposal_id") == 1
        ]
        assert len(journal_entries) == 1

    def test_approve_proposal_not_pending_raises(
        self, tws: TradeWorkflowService, sample_signals: list[dict]
    ):
        """Approving already-approved proposal raises ValueError."""
        tws.generate_proposals_from_signals(sample_signals)
        tws.approve_proposal(
            proposal_id=1,
            execution_price=90000.0,
            execution_notional_brl=20_000_000.0,
        )
        with pytest.raises(ValueError, match="not PENDING"):
            tws.approve_proposal(
                proposal_id=1,
                execution_price=90000.0,
                execution_notional_brl=20_000_000.0,
            )


# =============================================================================
# reject_proposal tests
# =============================================================================


class TestRejectProposal:
    """Tests for TradeWorkflowService.reject_proposal."""

    def test_reject_proposal_requires_notes(
        self, tws: TradeWorkflowService, sample_signals: list[dict]
    ):
        """Reject with empty notes raises ValueError."""
        tws.generate_proposals_from_signals(sample_signals)

        with pytest.raises(ValueError, match="manager_notes is mandatory"):
            tws.reject_proposal(proposal_id=1, manager_notes="")

        with pytest.raises(ValueError, match="manager_notes is mandatory"):
            tws.reject_proposal(proposal_id=1, manager_notes="   ")

    def test_reject_proposal_creates_journal_entry(
        self, tws: TradeWorkflowService, sample_signals: list[dict]
    ):
        """Reject creates REJECT journal entry with content_hash."""
        tws.generate_proposals_from_signals(sample_signals)
        proposal = tws.reject_proposal(
            proposal_id=1,
            manager_notes="Risk too high given current positioning",
        )

        assert proposal["status"] == "REJECTED"
        assert proposal["notes"] == "Risk too high given current positioning"

        # Verify REJECT journal entry
        reject_entries = [
            j for j in tws.position_manager._journal if j["entry_type"] == "REJECT"
        ]
        assert len(reject_entries) == 1
        entry = reject_entries[0]
        assert entry["proposal_id"] == 1
        assert entry["instrument"] == "DI1_F26"
        assert entry["content_hash"] is not None
        assert len(entry["content_hash"]) == 64  # SHA256 hex
        assert entry["is_locked"] is True


# =============================================================================
# modify_and_approve tests
# =============================================================================


class TestModifyAndApprove:
    """Tests for TradeWorkflowService.modify_and_approve_proposal."""

    def test_modify_and_approve_overrides_direction(
        self, tws: TradeWorkflowService, sample_signals: list[dict]
    ):
        """Modify changes direction before opening position."""
        tws.generate_proposals_from_signals(sample_signals)
        # Original direction for proposal 1 is LONG (DI1_F26)
        proposal = tws.modify_and_approve_proposal(
            proposal_id=1,
            modified_direction="SHORT",
            execution_price=90500.0,
        )

        assert proposal["status"] == "MODIFIED"
        assert proposal["direction"] == "SHORT"
        assert proposal["position_id"] is not None

        # Verify position has modified direction
        pos = tws.position_manager._find_position(proposal["position_id"])
        assert pos is not None
        assert pos["direction"] == "SHORT"


# =============================================================================
# open_discretionary_trade tests
# =============================================================================


class TestDiscretionaryTrade:
    """Tests for TradeWorkflowService.open_discretionary_trade."""

    def test_open_discretionary_trade_requires_thesis(
        self, tws: TradeWorkflowService
    ):
        """Empty thesis raises ValueError."""
        with pytest.raises(ValueError, match="manager_thesis is mandatory"):
            tws.open_discretionary_trade(
                instrument="IBOV_FUT",
                asset_class="EQUITY",
                direction="LONG",
                notional_brl=5_000_000.0,
                execution_price=130000.0,
                entry_date=date(2026, 2, 24),
                manager_thesis="",
            )

        with pytest.raises(ValueError, match="manager_thesis is mandatory"):
            tws.open_discretionary_trade(
                instrument="IBOV_FUT",
                asset_class="EQUITY",
                direction="LONG",
                notional_brl=5_000_000.0,
                execution_price=130000.0,
                entry_date=date(2026, 2, 24),
                manager_thesis="   ",
            )

    def test_open_discretionary_trade_creates_position_and_proposal(
        self, tws: TradeWorkflowService
    ):
        """Creates both proposal and position with DISCRETIONARY source."""
        result = tws.open_discretionary_trade(
            instrument="IBOV_FUT",
            asset_class="EQUITY",
            direction="LONG",
            notional_brl=5_000_000.0,
            execution_price=130000.0,
            entry_date=date(2026, 2, 24),
            manager_thesis="Expect strong earnings season for blue chips",
            target_price=140000.0,
            stop_loss=125000.0,
        )

        assert "proposal" in result
        assert "position" in result

        proposal = result["proposal"]
        position = result["position"]

        # Verify proposal
        assert proposal["status"] == "APPROVED"
        assert proposal["signal_source"] == "DISCRETIONARY"
        assert proposal["rationale"] == "Expect strong earnings season for blue chips"
        assert proposal["position_id"] == position["id"]
        assert proposal["metadata_json"]["target_price"] == 140000.0
        assert proposal["metadata_json"]["stop_loss"] == 125000.0

        # Verify position
        assert position["is_open"] is True
        assert position["instrument"] == "IBOV_FUT"
        assert position["direction"] == "LONG"
        assert position["notional_brl"] == 5_000_000.0

        # Verify journal entry has proposal_id
        journal_entries = [
            j
            for j in tws.position_manager._journal
            if j.get("proposal_id") == proposal["id"]
        ]
        assert len(journal_entries) == 1

        # Verify in proposals list
        assert len(tws._proposals) == 1
        assert tws._proposals[0]["signal_source"] == "DISCRETIONARY"


# =============================================================================
# close_position tests
# =============================================================================


class TestClosePosition:
    """Tests for TradeWorkflowService.close_position."""

    def test_close_position_delegates_to_pm(
        self, tws: TradeWorkflowService, sample_signals: list[dict]
    ):
        """Close returns position with realized P&L."""
        tws.generate_proposals_from_signals(sample_signals)
        tws.approve_proposal(
            proposal_id=1,
            execution_price=90000.0,
            execution_notional_brl=20_000_000.0,
        )

        closed = tws.close_position(
            position_id=1,
            close_price=91000.0,
            manager_notes="Taking profit",
        )

        assert closed["is_open"] is False
        assert closed["close_price"] == 91000.0
        assert closed["realized_pnl_brl"] != 0.0

    def test_close_position_with_outcome_notes(
        self, tws: TradeWorkflowService, sample_signals: list[dict]
    ):
        """Outcome notes creates additional NOTE journal entry."""
        tws.generate_proposals_from_signals(sample_signals)
        tws.approve_proposal(
            proposal_id=1,
            execution_price=90000.0,
            execution_notional_brl=20_000_000.0,
        )

        journal_count_before = len(tws.position_manager._journal)

        tws.close_position(
            position_id=1,
            close_price=91000.0,
            manager_notes="Taking profit",
            outcome_notes="Trade performed well, thesis confirmed by BCB rate decision",
        )

        # CLOSE + NOTE = 2 additional entries
        journal_count_after = len(tws.position_manager._journal)
        # close_position creates 1 CLOSE entry + 1 NOTE entry
        assert journal_count_after == journal_count_before + 2

        note_entries = [
            j for j in tws.position_manager._journal if j["entry_type"] == "NOTE"
        ]
        assert len(note_entries) == 1
        assert "thesis confirmed" in note_entries[0]["manager_notes"]
        assert note_entries[0]["content_hash"] is not None
        assert len(note_entries[0]["content_hash"]) == 64


# =============================================================================
# flip signal detection tests
# =============================================================================


class TestFlipDetection:
    """Tests for flip signal detection in generate_proposals_from_signals."""

    def test_flip_signal_detection(self, tws: TradeWorkflowService):
        """Signal with conviction >= 0.60 against existing opposite position is detected."""
        # Open a SHORT position on USDBRL
        tws.position_manager.open_position(
            instrument="USDBRL",
            asset_class="FX",
            direction="SHORT",
            notional_brl=10_000_000.0,
            entry_price=5.0,
        )

        # Generate a LONG signal on USDBRL with conviction >= 0.60
        signals = [
            {
                "instrument": "USDBRL",
                "asset_class": "FX",
                "direction": "LONG",
                "conviction": 0.65,
                "strategy_ids": ["FX-02"],
                "signal_source": "aggregator",
            },
        ]

        proposals = tws.generate_proposals_from_signals(signals)
        assert len(proposals) == 1
        assert proposals[0]["is_flip"] is True

        # Non-flip: same direction as existing position
        signals_same_dir = [
            {
                "instrument": "USDBRL",
                "asset_class": "FX",
                "direction": "SHORT",
                "conviction": 0.65,
                "strategy_ids": ["FX-03"],
                "signal_source": "aggregator",
            },
        ]
        proposals_same = tws.generate_proposals_from_signals(signals_same_dir)
        assert len(proposals_same) == 1
        assert proposals_same[0]["is_flip"] is False

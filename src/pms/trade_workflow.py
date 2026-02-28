"""Trade workflow service for the Portfolio Management System.

Converts aggregated signals into trade proposals, provides a human-in-the-loop
approval/reject/modify workflow, supports manager-initiated discretionary trades,
and logs all decisions immutably in the DecisionJournal.

This is the core decision engine of the PMS -- it bridges the automated signal
generation pipeline with human portfolio management, ensuring every trade
decision is captured with full context for audit and performance review.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any

import structlog

from .position_manager import PositionManager

logger = structlog.get_logger(__name__)


class TradeWorkflowService:
    """Orchestrates the trade proposal lifecycle on top of PositionManager.

    Workflow:
        1. Aggregated signals -> generate_proposals_from_signals() -> PENDING proposals
        2. Manager reviews via get_pending_proposals()
        3. Manager acts: approve_proposal(), reject_proposal(), modify_and_approve_proposal()
        4. Manager can also open_discretionary_trade() or close_position()
        5. Every action is journaled immutably with content hashes
    """

    # Configuration constants
    CONVICTION_MIN: float = 0.55
    FLIP_THRESHOLD: float = 0.60
    MAX_PROPOSALS_PER_DAY: int = 5

    def __init__(self, position_manager: PositionManager | None = None) -> None:
        """Initialize TradeWorkflowService.

        Args:
            position_manager: Optional PositionManager instance. Creates a new
                one with default 100M BRL AUM if not provided.
        """
        self.position_manager = position_manager or PositionManager()
        self._proposals: list[dict] = []

    # -------------------------------------------------------------------------
    # Method 1: Generate proposals from signals
    # -------------------------------------------------------------------------

    def generate_proposals_from_signals(
        self,
        signals: list[dict],
        as_of_date: date | None = None,
    ) -> list[dict]:
        """Convert aggregated signals into trade proposals.

        Filters by conviction >= 0.55, detects flips at >= 0.60, limits to
        max 5 proposals per call, sorted by conviction descending.

        Args:
            signals: List of aggregated signal dicts, each with keys:
                instrument, asset_class, direction, conviction, strategy_ids,
                signal_source, and optional suggested_notional_brl.
            as_of_date: Reference date for proposals (defaults to today).

        Returns:
            List of created proposal dicts with status PENDING.
        """
        ref_date = as_of_date or date.today()

        # Filter: only signals with conviction >= threshold
        qualifying = [
            s for s in signals if s.get("conviction", 0) >= self.CONVICTION_MIN
        ]

        # Sort by conviction descending, take top N
        qualifying.sort(key=lambda s: s.get("conviction", 0), reverse=True)
        qualifying = qualifying[: self.MAX_PROPOSALS_PER_DAY]

        created_proposals: list[dict] = []
        for signal in qualifying:
            # Detect flip: conviction >= FLIP_THRESHOLD and opposite open position
            is_flip = False
            if signal.get("conviction", 0) >= self.FLIP_THRESHOLD:
                opposite_dir = (
                    "SHORT" if signal.get("direction", "").upper() == "LONG" else "LONG"
                )
                for pos in self.position_manager._positions:
                    if (
                        pos["is_open"]
                        and pos["instrument"] == signal["instrument"]
                        and pos["direction"] == opposite_dir
                    ):
                        is_flip = True
                        break

            next_id = len(self._proposals) + 1
            now = datetime.utcnow()

            proposal = {
                "id": next_id,
                "created_at": now,
                "updated_at": now,
                "as_of_date": ref_date,
                "instrument": signal["instrument"],
                "asset_class": signal["asset_class"],
                "direction": signal["direction"].upper(),
                "suggested_notional_brl": signal.get(
                    "suggested_notional_brl", 10_000_000.0
                ),
                "conviction": signal["conviction"],
                "signal_source": signal.get("signal_source", "aggregator"),
                "strategy_ids": signal.get("strategy_ids", []),
                "rationale": self._generate_trade_rationale(signal),
                "risk_impact": self._estimate_portfolio_impact(signal),
                "status": "PENDING",
                "is_flip": is_flip,
                "reviewed_by": None,
                "reviewed_at": None,
                "execution_price": None,
                "execution_notional_brl": None,
                "position_id": None,
                "notes": None,
                "metadata_json": {},
            }

            self._proposals.append(proposal)
            created_proposals.append(proposal)

            logger.info(
                "proposal_created",
                proposal_id=next_id,
                instrument=signal["instrument"],
                direction=signal["direction"],
                conviction=signal["conviction"],
                is_flip=is_flip,
            )

        return created_proposals

    # -------------------------------------------------------------------------
    # Method 2: Get pending proposals
    # -------------------------------------------------------------------------

    def get_pending_proposals(self, as_of_date: date | None = None) -> list[dict]:
        """Return all PENDING proposals sorted by conviction descending.

        Args:
            as_of_date: Optional date filter (matches proposal's as_of_date).

        Returns:
            List of PENDING proposal dicts sorted by conviction descending.
        """
        pending = [p for p in self._proposals if p["status"] == "PENDING"]

        if as_of_date is not None:
            pending = [p for p in pending if p.get("as_of_date") == as_of_date]

        pending.sort(key=lambda p: p.get("conviction", 0), reverse=True)
        return pending

    # -------------------------------------------------------------------------
    # Method 3: Approve proposal
    # -------------------------------------------------------------------------

    def approve_proposal(
        self,
        proposal_id: int,
        execution_price: float,
        execution_notional_brl: float,
        manager_notes: str | None = None,
        manager_thesis: str | None = None,
        target_price: float | None = None,
        stop_loss: float | None = None,
        time_horizon: str | None = None,
    ) -> dict:
        """Approve a PENDING proposal and open a position.

        Args:
            proposal_id: ID of the proposal to approve.
            execution_price: Actual execution price.
            execution_notional_brl: Actual notional in BRL.
            manager_notes: Optional manager notes.
            manager_thesis: Optional thesis for the trade.
            target_price: Optional target price.
            stop_loss: Optional stop loss level.
            time_horizon: Optional time horizon string.

        Returns:
            Updated proposal dict with position_id set.

        Raises:
            ValueError: If proposal not found or not PENDING.
        """
        proposal = self._find_proposal(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal["status"] != "PENDING":
            raise ValueError(
                f"Proposal {proposal_id} is not PENDING (current status: {proposal['status']})"
            )

        now = datetime.utcnow()

        # Update proposal
        proposal["status"] = "APPROVED"
        proposal["execution_price"] = execution_price
        proposal["execution_notional_brl"] = execution_notional_brl
        proposal["reviewed_at"] = now
        proposal["updated_at"] = now
        proposal["notes"] = manager_notes

        # Store optional metadata
        if target_price is not None:
            proposal["metadata_json"]["target_price"] = target_price
        if stop_loss is not None:
            proposal["metadata_json"]["stop_loss"] = stop_loss
        if time_horizon is not None:
            proposal["metadata_json"]["time_horizon"] = time_horizon

        # Open position via PositionManager
        position = self.position_manager.open_position(
            instrument=proposal["instrument"],
            asset_class=proposal["asset_class"],
            direction=proposal["direction"],
            notional_brl=execution_notional_brl,
            entry_price=execution_price,
            entry_date=date.today(),
            strategy_ids=proposal.get("strategy_ids"),
            notes=manager_notes or manager_thesis,
        )

        proposal["position_id"] = position["id"]

        # Link proposal_id to the journal entry created by open_position
        if self.position_manager._journal:
            last_journal = self.position_manager._journal[-1]
            last_journal["proposal_id"] = proposal_id

        logger.info(
            "proposal_approved",
            proposal_id=proposal_id,
            position_id=position["id"],
            instrument=proposal["instrument"],
        )

        return proposal

    # -------------------------------------------------------------------------
    # Method 4: Reject proposal
    # -------------------------------------------------------------------------

    def reject_proposal(
        self,
        proposal_id: int,
        manager_notes: str,
    ) -> dict:
        """Reject a PENDING proposal with mandatory notes.

        Args:
            proposal_id: ID of the proposal to reject.
            manager_notes: Mandatory rejection notes explaining the decision.

        Returns:
            Updated proposal dict with status REJECTED.

        Raises:
            ValueError: If proposal not found, not PENDING, or notes empty.
        """
        if not manager_notes or not manager_notes.strip():
            raise ValueError("manager_notes is mandatory for rejection")

        proposal = self._find_proposal(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal["status"] != "PENDING":
            raise ValueError(
                f"Proposal {proposal_id} is not PENDING (current status: {proposal['status']})"
            )

        now = datetime.utcnow()

        # Update proposal
        proposal["status"] = "REJECTED"
        proposal["reviewed_at"] = now
        proposal["updated_at"] = now
        proposal["notes"] = manager_notes

        # Create REJECT journal entry
        journal_content = {
            "entry_type": "REJECT",
            "instrument": proposal["instrument"],
            "direction": proposal["direction"],
            "notional_brl": proposal["suggested_notional_brl"],
            "entry_price": 0.0,
            "manager_notes": manager_notes,
            "system_notes": f"Proposal #{proposal_id} rejected. Conviction: {proposal['conviction']:.2%}",
        }
        content_hash = self.position_manager._compute_content_hash(**journal_content)

        journal_entry = {
            "id": len(self.position_manager._journal) + 1,
            "created_at": now,
            "entry_type": "REJECT",
            "position_id": None,
            "proposal_id": proposal_id,
            "instrument": proposal["instrument"],
            "direction": proposal["direction"],
            "notional_brl": proposal["suggested_notional_brl"],
            "entry_price": 0.0,
            "manager_notes": manager_notes,
            "system_notes": journal_content["system_notes"],
            "market_snapshot": {},
            "portfolio_snapshot": {},
            "content_hash": content_hash,
            "is_locked": True,
        }

        self.position_manager._journal.append(journal_entry)

        logger.info(
            "proposal_rejected",
            proposal_id=proposal_id,
            instrument=proposal["instrument"],
        )

        return proposal

    # -------------------------------------------------------------------------
    # Method 5: Modify and approve proposal
    # -------------------------------------------------------------------------

    def modify_and_approve_proposal(
        self,
        proposal_id: int,
        modified_direction: str | None = None,
        modified_notional_brl: float | None = None,
        execution_price: float | None = None,
        manager_notes: str | None = None,
        **kwargs: Any,
    ) -> dict:
        """Modify a PENDING proposal and approve it, opening a position.

        Args:
            proposal_id: ID of the proposal to modify.
            modified_direction: Override direction (LONG/SHORT).
            modified_notional_brl: Override notional in BRL.
            execution_price: Execution price (required if not already set).
            manager_notes: Optional manager notes.
            **kwargs: Additional fields to store in metadata_json.

        Returns:
            Updated proposal dict with status MODIFIED and position_id set.

        Raises:
            ValueError: If proposal not found or not PENDING.
        """
        proposal = self._find_proposal(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal["status"] != "PENDING":
            raise ValueError(
                f"Proposal {proposal_id} is not PENDING (current status: {proposal['status']})"
            )

        now = datetime.utcnow()

        # Apply modifications
        if modified_direction is not None:
            proposal["direction"] = modified_direction.upper()
        if modified_notional_brl is not None:
            proposal["execution_notional_brl"] = modified_notional_brl
        else:
            proposal["execution_notional_brl"] = proposal["suggested_notional_brl"]

        if execution_price is not None:
            proposal["execution_price"] = execution_price

        effective_notional = modified_notional_brl or proposal["suggested_notional_brl"]
        effective_price = execution_price or proposal.get("execution_price", 0.0)

        # Update proposal status
        proposal["status"] = "MODIFIED"
        proposal["reviewed_at"] = now
        proposal["updated_at"] = now
        proposal["notes"] = manager_notes

        # Store kwargs in metadata
        for key, value in kwargs.items():
            proposal["metadata_json"][key] = value

        # Open position via PositionManager with modified values
        position = self.position_manager.open_position(
            instrument=proposal["instrument"],
            asset_class=proposal["asset_class"],
            direction=proposal["direction"],
            notional_brl=effective_notional,
            entry_price=effective_price,
            entry_date=date.today(),
            strategy_ids=proposal.get("strategy_ids"),
            notes=manager_notes,
        )

        proposal["position_id"] = position["id"]

        # Link proposal_id to the journal entry created by open_position
        if self.position_manager._journal:
            last_journal = self.position_manager._journal[-1]
            last_journal["proposal_id"] = proposal_id

        logger.info(
            "proposal_modified_and_approved",
            proposal_id=proposal_id,
            position_id=position["id"],
            instrument=proposal["instrument"],
            direction=proposal["direction"],
        )

        return proposal

    # -------------------------------------------------------------------------
    # Method 6: Open discretionary trade
    # -------------------------------------------------------------------------

    def open_discretionary_trade(
        self,
        instrument: str,
        asset_class: str,
        direction: str,
        notional_brl: float,
        execution_price: float,
        entry_date: date,
        manager_thesis: str,
        target_price: float | None = None,
        stop_loss: float | None = None,
        time_horizon: str | None = None,
        strategy_ids: list[str] | None = None,
    ) -> dict:
        """Open a manager-initiated discretionary trade.

        Creates both a proposal (with status APPROVED and source DISCRETIONARY)
        and a position, linked together.

        Args:
            instrument: Instrument ticker.
            asset_class: Asset class.
            direction: LONG or SHORT.
            notional_brl: Notional in BRL.
            execution_price: Execution price.
            entry_date: Entry date.
            manager_thesis: Mandatory thesis explaining the trade rationale.
            target_price: Optional target price.
            stop_loss: Optional stop loss.
            time_horizon: Optional time horizon.
            strategy_ids: Optional strategy IDs.

        Returns:
            Dict with both proposal and position data.

        Raises:
            ValueError: If manager_thesis is empty or None.
        """
        if not manager_thesis or not manager_thesis.strip():
            raise ValueError("manager_thesis is mandatory for discretionary trades")

        now = datetime.utcnow()
        next_id = len(self._proposals) + 1

        # Build metadata
        metadata: dict[str, Any] = {}
        if target_price is not None:
            metadata["target_price"] = target_price
        if stop_loss is not None:
            metadata["stop_loss"] = stop_loss
        if time_horizon is not None:
            metadata["time_horizon"] = time_horizon

        # Create proposal (already APPROVED)
        proposal = {
            "id": next_id,
            "created_at": now,
            "updated_at": now,
            "as_of_date": entry_date,
            "instrument": instrument,
            "asset_class": asset_class.upper(),
            "direction": direction.upper(),
            "suggested_notional_brl": notional_brl,
            "conviction": 1.0,  # Manager discretionary: full conviction
            "signal_source": "DISCRETIONARY",
            "strategy_ids": strategy_ids or [],
            "rationale": manager_thesis,
            "risk_impact": self._estimate_portfolio_impact(
                {
                    "instrument": instrument,
                    "asset_class": asset_class,
                    "suggested_notional_brl": notional_brl,
                }
            ),
            "status": "APPROVED",
            "is_flip": False,
            "reviewed_by": "manager",
            "reviewed_at": now,
            "execution_price": execution_price,
            "execution_notional_brl": notional_brl,
            "position_id": None,
            "notes": manager_thesis,
            "metadata_json": metadata,
        }

        self._proposals.append(proposal)

        # Open position via PositionManager
        position = self.position_manager.open_position(
            instrument=instrument,
            asset_class=asset_class,
            direction=direction,
            notional_brl=notional_brl,
            entry_price=execution_price,
            entry_date=entry_date,
            strategy_ids=strategy_ids,
            notes=manager_thesis,
        )

        proposal["position_id"] = position["id"]

        # Link proposal_id to the journal entry
        if self.position_manager._journal:
            last_journal = self.position_manager._journal[-1]
            last_journal["proposal_id"] = next_id

        logger.info(
            "discretionary_trade_opened",
            proposal_id=next_id,
            position_id=position["id"],
            instrument=instrument,
            direction=direction,
        )

        return {
            "proposal": proposal,
            "position": position,
        }

    # -------------------------------------------------------------------------
    # Method 7: Close position
    # -------------------------------------------------------------------------

    def close_position(
        self,
        position_id: int,
        close_price: float,
        close_date: date | datetime | None = None,
        manager_notes: str | None = None,
        outcome_notes: str | None = None,
    ) -> dict:
        """Close a position with optional outcome assessment.

        Delegates to PositionManager.close_position() and optionally creates
        an additional NOTE journal entry recording the outcome assessment.

        Args:
            position_id: ID of the position to close.
            close_price: Closing price.
            close_date: Close date (defaults to now).
            manager_notes: Notes on the close decision.
            outcome_notes: Optional outcome assessment for the journal.

        Returns:
            Closed position dict with realized P&L.
        """
        closed_position = self.position_manager.close_position(
            position_id=position_id,
            close_price=close_price,
            close_date=close_date,
            notes=manager_notes,
        )

        # If outcome notes provided, create additional NOTE journal entry
        if outcome_notes and outcome_notes.strip():
            now = datetime.utcnow()
            journal_content = {
                "entry_type": "NOTE",
                "instrument": closed_position["instrument"],
                "direction": closed_position["direction"],
                "notional_brl": closed_position["notional_brl"],
                "entry_price": close_price,
                "manager_notes": outcome_notes,
                "system_notes": (
                    f"Outcome assessment for position #{position_id}. "
                    f"Realized P&L: {closed_position['realized_pnl_brl']:.2f} BRL"
                ),
            }
            content_hash = self.position_manager._compute_content_hash(
                **journal_content
            )

            journal_entry = {
                "id": len(self.position_manager._journal) + 1,
                "created_at": now,
                "entry_type": "NOTE",
                "position_id": position_id,
                "proposal_id": None,
                "instrument": closed_position["instrument"],
                "direction": closed_position["direction"],
                "notional_brl": closed_position["notional_brl"],
                "entry_price": close_price,
                "manager_notes": outcome_notes,
                "system_notes": journal_content["system_notes"],
                "market_snapshot": {},
                "portfolio_snapshot": {},
                "content_hash": content_hash,
                "is_locked": True,
            }

            self.position_manager._journal.append(journal_entry)

            logger.info(
                "outcome_notes_recorded",
                position_id=position_id,
                instrument=closed_position["instrument"],
            )

        return closed_position

    # -------------------------------------------------------------------------
    # Method 8: Estimate portfolio impact (private)
    # -------------------------------------------------------------------------

    def _estimate_portfolio_impact(self, signal: dict) -> dict:
        """Compute simple pre-trade portfolio impact analytics.

        Args:
            signal: Signal dict with instrument, asset_class, suggested_notional_brl.

        Returns:
            Dict with leverage_delta, open_positions count, same-instrument
            exposure, and asset class concentration.
        """
        aum = self.position_manager.aum
        suggested_notional = signal.get("suggested_notional_brl", 10_000_000.0)

        open_positions = [p for p in self.position_manager._positions if p["is_open"]]

        same_instrument_exposure = sum(
            p["notional_brl"]
            for p in open_positions
            if p["instrument"] == signal.get("instrument")
        )

        asset_class_notional = sum(
            p["notional_brl"]
            for p in open_positions
            if p["asset_class"] == signal.get("asset_class", "").upper()
        )

        return {
            "estimated_leverage_delta": suggested_notional / aum if aum > 0 else 0.0,
            "current_open_positions": len(open_positions),
            "same_instrument_exposure": same_instrument_exposure,
            "asset_class_concentration": asset_class_notional / aum if aum > 0 else 0.0,
        }

    # -------------------------------------------------------------------------
    # Method 9: Generate trade rationale (private)
    # -------------------------------------------------------------------------

    def _generate_trade_rationale(self, signal: dict) -> str:
        """Generate trade rationale from signal data.

        Uses a template-based approach as primary method. If ANTHROPIC_API_KEY
        is available, attempts LLM enhancement via Claude API (falls back to
        template on any failure).

        Args:
            signal: Signal dict with instrument, asset_class, direction,
                conviction, signal_source, strategy_ids.

        Returns:
            Rationale string (always non-empty).
        """
        # Template-based rationale (always available)
        strategy_names = ", ".join(signal.get("strategy_ids", [])) or "N/A"
        template = (
            f"Signal-generated {signal.get('direction', 'UNKNOWN')} proposal for "
            f"{signal.get('instrument', 'UNKNOWN')} ({signal.get('asset_class', 'UNKNOWN')}) "
            f"with {signal.get('conviction', 0):.0%} conviction from "
            f"{signal.get('signal_source', 'aggregator')}. "
            f"Strategies: {strategy_names}."
        )

        # Optional LLM enhancement
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            try:
                import httpx

                prompt = (
                    f"Write a concise 2-sentence trade rationale for a "
                    f"{signal.get('direction', 'UNKNOWN')} position in "
                    f"{signal.get('instrument', 'UNKNOWN')} ({signal.get('asset_class', 'UNKNOWN')}) "
                    f"with {signal.get('conviction', 0):.0%} conviction. "
                    f"Strategies: {strategy_names}."
                )

                response = httpx.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 256,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()
                llm_text = data.get("content", [{}])[0].get("text", "")
                if llm_text.strip():
                    return f"{llm_text.strip()} [Source: {template}]"
            except Exception:
                logger.debug(
                    "llm_rationale_fallback",
                    instrument=signal.get("instrument"),
                    reason="LLM call failed, using template",
                )

        return template

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _find_proposal(self, proposal_id: int) -> dict | None:
        """Find proposal by ID."""
        for p in self._proposals:
            if p["id"] == proposal_id:
                return p
        return None

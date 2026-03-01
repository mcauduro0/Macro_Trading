"""Emergency stop procedure with human-in-the-loop design.

Provides a structured procedure for halting all trading activity in a crisis.
The system MARKS positions for urgent close and FREEZES new proposal
generation, but does NOT automatically close positions. A human must review
the position report and execute each close manually.

This separation is deliberate: in a genuine crisis, automatic liquidation
can amplify losses (bad fills, liquidity shocks). The emergency stop ensures
the human has full visibility and control.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class PositionCloseItem:
    """A single position flagged for urgent close during emergency stop.

    Attributes:
        position_id: Unique identifier of the position.
        instrument: Instrument name (e.g. ``"USDBRL"``).
        asset_class: Asset class (e.g. ``"fx"``, ``"rates"``).
        direction: ``"long"`` or ``"short"``.
        notional: Current notional exposure in BRL.
        unrealized_pnl: Current unrealized P&L in BRL.
        priority: Suggested close priority (1 = highest).
        notes: Additional context for the human operator.
    """

    position_id: str
    instrument: str
    asset_class: str
    direction: str
    notional: float
    unrealized_pnl: float
    priority: int = 1
    notes: str = ""


@dataclass
class EmergencyStopResult:
    """Outcome of an emergency stop initiation.

    Attributes:
        activated: True if the procedure was successfully activated.
        timestamp: UTC time of activation.
        reason: Human-readable reason for the stop.
        manager_confirmation: Identifier of the confirming manager.
        positions_flagged: Number of positions marked for urgent close.
        position_report: List of :class:`PositionCloseItem` dicts.
        proposals_frozen: True if proposal generation was frozen.
        checklist: Ordered list of follow-up actions for the human operator.
        audit_record: The audit event dict (if an AuditLogger was provided).
    """

    activated: bool
    timestamp: str
    reason: str
    manager_confirmation: str
    positions_flagged: int
    position_report: list[dict[str, Any]]
    proposals_frozen: bool
    checklist: list[str]
    audit_record: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# EmergencyStopProcedure
# ---------------------------------------------------------------------------


class EmergencyStopProcedure:
    """Orchestrates the emergency stop sequence.

    The procedure:
        1. Validates manager confirmation.
        2. Marks all open positions with ``needs_urgent_close = True``.
        3. Freezes new proposal generation.
        4. Generates a prioritized position report for human review.
        5. Logs a CRITICAL audit event (if AuditLogger provided).
        6. Returns a structured result with a follow-up checklist.

    Args:
        audit_logger: Optional :class:`~src.compliance.audit.AuditLogger`.
            If provided, a ``CRITICAL`` event is logged on activation.
    """

    def __init__(self, audit_logger: Any = None) -> None:
        self._audit_logger = audit_logger
        self._frozen = False
        self._stop_active = False
        self._stop_timestamp: str | None = None

    @property
    def is_frozen(self) -> bool:
        """True if proposal generation is currently frozen."""
        return self._frozen

    @property
    def is_active(self) -> bool:
        """True if an emergency stop is currently active."""
        return self._stop_active

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def initiate(
        self,
        reason: str,
        manager_confirmation: str,
        positions: list[dict[str, Any]] | None = None,
    ) -> EmergencyStopResult:
        """Initiate the emergency stop procedure.

        Args:
            reason: Human-readable explanation for triggering the stop
                (e.g. ``"Unexpected BRL move > 5% in 30 minutes"``).
            manager_confirmation: Identifier of the approving manager
                (e.g. ``"john.doe@fund.com"``). Required to activate.
            positions: Optional list of current open positions as dicts.
                Each dict should contain at minimum: ``position_id``,
                ``instrument``, ``asset_class``, ``direction``,
                ``notional``, ``unrealized_pnl``.
                If not provided, the result will contain an empty report
                and the operator must source position data separately.

        Returns:
            :class:`EmergencyStopResult` with full context for the
            human operator.

        Raises:
            ValueError: If ``reason`` or ``manager_confirmation`` is empty.
        """
        # --- Validation ---
        if not reason or not reason.strip():
            raise ValueError("Emergency stop reason must not be empty.")
        if not manager_confirmation or not manager_confirmation.strip():
            raise ValueError(
                "Manager confirmation (identifier) is required to activate "
                "emergency stop."
            )

        now = datetime.now(timezone.utc)
        self._stop_timestamp = now.isoformat()
        self._stop_active = True

        logger.critical(
            "emergency_stop.initiated",
            reason=reason,
            manager=manager_confirmation,
            timestamp=self._stop_timestamp,
        )

        # --- Freeze proposal generation ---
        self._frozen = True
        logger.warning("emergency_stop.proposals_frozen")

        # --- Flag positions for urgent close ---
        position_report = self._build_position_report(positions or [])

        # --- Audit event ---
        audit_record = self._log_audit_event(
            reason=reason,
            manager=manager_confirmation,
            positions_flagged=len(position_report),
        )

        # --- Build checklist ---
        checklist = self._build_checklist(
            reason=reason,
            n_positions=len(position_report),
        )

        result = EmergencyStopResult(
            activated=True,
            timestamp=self._stop_timestamp,
            reason=reason,
            manager_confirmation=manager_confirmation,
            positions_flagged=len(position_report),
            position_report=position_report,
            proposals_frozen=True,
            checklist=checklist,
            audit_record=audit_record,
        )

        logger.critical(
            "emergency_stop.result",
            positions_flagged=result.positions_flagged,
            checklist_items=len(checklist),
        )
        return result

    def reset(self, manager_confirmation: str) -> dict[str, Any]:
        """Reset the emergency stop, unfreezing proposal generation.

        Only call this after all flagged positions have been manually
        reviewed and either closed or explicitly retained.

        Args:
            manager_confirmation: Identifier of the manager authorizing
                the reset.

        Returns:
            dict with reset confirmation details.

        Raises:
            ValueError: If ``manager_confirmation`` is empty.
        """
        if not manager_confirmation or not manager_confirmation.strip():
            raise ValueError("Manager confirmation required to reset.")

        self._frozen = False
        self._stop_active = False

        logger.info(
            "emergency_stop.reset",
            manager=manager_confirmation,
        )

        if self._audit_logger is not None:
            try:
                self._audit_logger.log_event(
                    event_type="EMERGENCY_STOP",
                    entity_type="system",
                    entity_id="emergency_stop",
                    user=manager_confirmation,
                    action="Emergency stop reset -- proposals unfrozen",
                    before_state={"frozen": True, "stop_active": True},
                    after_state={"frozen": False, "stop_active": False},
                    metadata={"sub_action": "reset"},
                    severity="WARNING",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("emergency_stop.audit_reset_error", error=str(exc))

        return {
            "reset": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "manager": manager_confirmation,
            "proposals_frozen": False,
            "stop_active": False,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_position_report(
        self,
        positions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Mark each position for urgent close and produce a sorted report.

        Positions are sorted by absolute notional descending (largest
        exposures first) so the operator can prioritize unwinding.
        """
        report: list[dict[str, Any]] = []
        for idx, pos in enumerate(positions):
            item = PositionCloseItem(
                position_id=str(pos.get("position_id", f"unknown_{idx}")),
                instrument=str(pos.get("instrument", "UNKNOWN")),
                asset_class=str(pos.get("asset_class", "unknown")),
                direction=str(pos.get("direction", "unknown")),
                notional=float(pos.get("notional", 0.0)),
                unrealized_pnl=float(pos.get("unrealized_pnl", 0.0)),
                priority=idx + 1,  # Will be re-sorted below
                notes="",
            )
            report.append(
                {
                    "position_id": item.position_id,
                    "instrument": item.instrument,
                    "asset_class": item.asset_class,
                    "direction": item.direction,
                    "notional": item.notional,
                    "unrealized_pnl": item.unrealized_pnl,
                    "needs_urgent_close": True,
                    "priority": item.priority,
                    "notes": item.notes,
                }
            )

        # Sort by absolute notional descending -- largest exposure first
        report.sort(key=lambda p: abs(p["notional"]), reverse=True)
        # Re-number priorities after sort
        for idx, item in enumerate(report):
            item["priority"] = idx + 1

        return report

    def _log_audit_event(
        self,
        reason: str,
        manager: str,
        positions_flagged: int,
    ) -> dict[str, Any] | None:
        """Log a CRITICAL audit event for the emergency stop."""
        if self._audit_logger is None:
            logger.warning(
                "emergency_stop.no_audit_logger",
                msg="AuditLogger not configured; skipping audit event",
            )
            return None

        try:
            record = self._audit_logger.log_event(
                event_type="EMERGENCY_STOP",
                entity_type="system",
                entity_id="emergency_stop",
                user=manager,
                action=f"Emergency stop initiated: {reason}",
                before_state={"frozen": False, "stop_active": False},
                after_state={
                    "frozen": True,
                    "stop_active": True,
                    "positions_flagged": positions_flagged,
                },
                metadata={
                    "reason": reason,
                    "positions_flagged": positions_flagged,
                    "sub_action": "initiate",
                },
                severity="CRITICAL",
            )
            return record
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "emergency_stop.audit_error",
                error=str(exc),
            )
            return None

    @staticmethod
    def _build_checklist(reason: str, n_positions: int) -> list[str]:
        """Generate a follow-up checklist for the human operator."""
        checklist = [
            "1. Review the position report -- verify all flagged positions.",
            f"2. Manually close/unwind {n_positions} flagged position(s), "
            "starting with highest priority (largest notional).",
            "3. Verify each close in the order management system.",
            "4. Confirm no open limit orders remain on the book.",
            "5. Notify risk management and senior portfolio manager.",
            f"6. Document the incident: reason = '{reason}'.",
            "7. Once all positions are handled, call reset() to unfreeze "
            "proposal generation.",
            "8. Conduct a post-mortem within 24 hours.",
        ]
        return checklist

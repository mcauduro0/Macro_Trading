"""Audit logging with dual-write: JSONL file + optional database insert.

Provides immutable, tamper-evident audit trail for all PMS events.
Each record includes a SHA-256 checksum covering the canonical fields
so downstream consumers can verify integrity.

All functions tolerate database unavailability -- file logging is the
primary store; DB insert is best-effort.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_AUDIT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "logs",
)
DEFAULT_AUDIT_FILE = "audit.jsonl"


class EventType(str, Enum):
    """Canonical event types captured by the audit log."""

    POSITION_OPEN = "POSITION_OPEN"
    POSITION_CLOSE = "POSITION_CLOSE"
    TRADE_APPROVED = "TRADE_APPROVED"
    TRADE_REJECTED = "TRADE_REJECTED"
    RISK_BREACH = "RISK_BREACH"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    MTM_UPDATE = "MTM_UPDATE"
    MORNING_PACK_GENERATED = "MORNING_PACK_GENERATED"
    SYSTEM_STARTUP = "SYSTEM_STARTUP"


class Severity(str, Enum):
    """Severity levels for audit events."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_checksum(record: dict[str, Any]) -> str:
    """Compute SHA-256 over the canonical fields of an audit record.

    The checksum covers: event_timestamp, event_type, entity_type,
    entity_id, user, action, before_state, after_state, severity.
    Metadata is intentionally excluded so enrichment does not
    invalidate the checksum.
    """
    canonical_fields = [
        str(record.get("event_timestamp", "")),
        str(record.get("event_type", "")),
        str(record.get("entity_type", "")),
        str(record.get("entity_id", "")),
        str(record.get("user", "")),
        str(record.get("action", "")),
        json.dumps(record.get("before_state"), sort_keys=True, default=str),
        json.dumps(record.get("after_state"), sort_keys=True, default=str),
        str(record.get("severity", "")),
    ]
    payload = "|".join(canonical_fields).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# ---------------------------------------------------------------------------
# AuditLogger
# ---------------------------------------------------------------------------


class AuditLogger:
    """Immutable audit logger with dual-write (JSONL file + optional DB).

    Args:
        audit_dir: Directory for the JSONL file. Defaults to ``logs/``
            at the project root.
        audit_file: Filename within *audit_dir*. Defaults to ``audit.jsonl``.
        db_session_factory: Optional callable that returns a DB session.
            If provided, each event is *also* inserted into an
            ``audit_events`` table. DB failures are logged but never
            propagated.
    """

    def __init__(
        self,
        audit_dir: str | None = None,
        audit_file: str = DEFAULT_AUDIT_FILE,
        db_session_factory: Any = None,
    ) -> None:
        self._audit_dir = audit_dir or DEFAULT_AUDIT_DIR
        self._audit_path = os.path.join(self._audit_dir, audit_file)
        self._db_session_factory = db_session_factory

        # Ensure the audit directory exists
        Path(self._audit_dir).mkdir(parents=True, exist_ok=True)

        logger.info(
            "audit_logger.init",
            audit_path=self._audit_path,
            db_enabled=db_session_factory is not None,
        )

    # ------------------------------------------------------------------
    # Core logging
    # ------------------------------------------------------------------

    def log_event(
        self,
        event_type: EventType | str,
        entity_type: str,
        entity_id: str,
        user: str,
        action: str,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        severity: Severity | str = Severity.INFO,
    ) -> dict[str, Any]:
        """Write a single audit event to JSONL (and optionally DB).

        Args:
            event_type: One of :class:`EventType` or a custom string.
            entity_type: E.g. ``"position"``, ``"proposal"``, ``"portfolio"``.
            entity_id: Unique identifier of the affected entity.
            user: Who or what triggered the event (user ID or ``"system"``).
            action: Human-readable verb, e.g. ``"opened long USDBRL"``.
            before_state: State snapshot before the change (optional).
            after_state: State snapshot after the change (optional).
            metadata: Arbitrary extra context (not covered by checksum).
            severity: ``INFO``, ``WARNING``, or ``CRITICAL``.

        Returns:
            The fully-constructed audit record dict (including checksum).
        """
        now = datetime.now(timezone.utc)
        record: dict[str, Any] = {
            "event_timestamp": now.isoformat(),
            "event_type": str(event_type.value if isinstance(event_type, EventType) else event_type),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "user": user,
            "action": action,
            "before_state": before_state,
            "after_state": after_state,
            "metadata": metadata or {},
            "severity": str(severity.value if isinstance(severity, Severity) else severity),
        }
        record["checksum"] = _compute_checksum(record)

        # --- File write (primary) ---
        self._write_jsonl(record)

        # --- DB write (best-effort) ---
        self._write_db(record)

        logger.info(
            "audit_logger.event",
            event_type=record["event_type"],
            entity_id=entity_id,
            severity=record["severity"],
            checksum=record["checksum"][:12],
        )
        return record

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def log_risk_breach(
        self,
        limit_name: str,
        current_value: float,
        limit_value: float,
        entity_id: str = "portfolio",
        user: str = "system",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Shorthand for logging a risk limit breach.

        Always logged at CRITICAL severity.
        """
        breach_meta = {
            "limit_name": limit_name,
            "current_value": current_value,
            "limit_value": limit_value,
            "utilization_pct": round(
                (current_value / limit_value * 100) if limit_value else 0.0, 2
            ),
            **(metadata or {}),
        }
        return self.log_event(
            event_type=EventType.RISK_BREACH,
            entity_type="risk_limit",
            entity_id=entity_id,
            user=user,
            action=f"Risk breach on {limit_name}: {current_value:.4f} exceeds {limit_value:.4f}",
            before_state={"value": current_value},
            after_state={"limit": limit_value, "breached": True},
            metadata=breach_meta,
            severity=Severity.CRITICAL,
        )

    # ------------------------------------------------------------------
    # Query / retrieval
    # ------------------------------------------------------------------

    def get_audit_trail(
        self,
        event_type: EventType | str | None = None,
        entity_id: str | None = None,
        severity: Severity | str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Read audit trail from the JSONL file with optional filters.

        This scans the file sequentially -- suitable for operational queries
        and compliance review, not for high-frequency analytics. For heavy
        queries, use the DB copy.

        Args:
            event_type: Filter by event type.
            entity_id: Filter by entity ID.
            severity: Filter by severity.
            start_time: Earliest event timestamp (inclusive).
            end_time: Latest event timestamp (inclusive).
            limit: Maximum number of records to return (most recent first).

        Returns:
            List of matching audit records, most recent first.
        """
        if not os.path.exists(self._audit_path):
            return []

        records: list[dict[str, Any]] = []
        et_str = str(
            event_type.value if isinstance(event_type, EventType) else event_type
        ) if event_type else None
        sev_str = str(
            severity.value if isinstance(severity, Severity) else severity
        ) if severity else None

        try:
            with open(self._audit_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Apply filters
                    if et_str and rec.get("event_type") != et_str:
                        continue
                    if entity_id and rec.get("entity_id") != entity_id:
                        continue
                    if sev_str and rec.get("severity") != sev_str:
                        continue
                    if start_time:
                        rec_ts = datetime.fromisoformat(rec["event_timestamp"])
                        if rec_ts < start_time:
                            continue
                    if end_time:
                        rec_ts = datetime.fromisoformat(rec["event_timestamp"])
                        if rec_ts > end_time:
                            continue

                    records.append(rec)
        except OSError as exc:
            logger.error("audit_logger.read_error", error=str(exc))
            return []

        # Most recent first, apply limit
        records.reverse()
        return records[:limit]

    # ------------------------------------------------------------------
    # Internal write methods
    # ------------------------------------------------------------------

    def _write_jsonl(self, record: dict[str, Any]) -> None:
        """Append a single JSON line to the audit file."""
        try:
            with open(self._audit_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
        except OSError as exc:
            logger.error(
                "audit_logger.file_write_error",
                error=str(exc),
                event_type=record.get("event_type"),
            )

    def _write_db(self, record: dict[str, Any]) -> None:
        """Best-effort insert into the audit_events DB table.

        Swallows all exceptions so that DB unavailability never blocks
        the primary JSONL write path.
        """
        if self._db_session_factory is None:
            return
        try:
            session = self._db_session_factory()
            # Expects an ``audit_events`` table accessible via raw SQL or ORM.
            # Using raw insert for minimal coupling.
            session.execute(
                """
                INSERT INTO audit_events
                    (event_timestamp, event_type, entity_type, entity_id,
                     "user", action, before_state, after_state, metadata,
                     severity, checksum)
                VALUES
                    (:event_timestamp, :event_type, :entity_type, :entity_id,
                     :user, :action, :before_state, :after_state, :metadata,
                     :severity, :checksum)
                """,
                {
                    "event_timestamp": record["event_timestamp"],
                    "event_type": record["event_type"],
                    "entity_type": record["entity_type"],
                    "entity_id": record["entity_id"],
                    "user": record["user"],
                    "action": record["action"],
                    "before_state": json.dumps(record.get("before_state"), default=str),
                    "after_state": json.dumps(record.get("after_state"), default=str),
                    "metadata": json.dumps(record.get("metadata"), default=str),
                    "severity": record["severity"],
                    "checksum": record["checksum"],
                },
            )
            session.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "audit_logger.db_write_error",
                error=str(exc),
                event_type=record.get("event_type"),
            )

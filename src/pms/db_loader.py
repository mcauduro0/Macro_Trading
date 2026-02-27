"""Database loader for PMS in-memory stores.

Loads positions, trade proposals, and briefings from TimescaleDB
into the in-memory stores used by PositionManager, TradeWorkflowService,
and MorningPackService.

This bridges the gap between the DB-persisted data (written by the Dagster
pipeline) and the in-memory singletons used by the FastAPI routes.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime

logger = logging.getLogger(__name__)


def _get_connection():
    """Create a psycopg2 connection using environment variables.

    Prioritizes individual POSTGRES_* env vars over DATABASE_URL
    because DATABASE_URL may have incorrect host (e.g. 127.0.0.1
    instead of the Docker service name).
    """
    import psycopg2
    import psycopg2.extras

    host = os.environ.get("POSTGRES_HOST", "timescaledb")
    port = int(os.environ.get("POSTGRES_PORT", "5432"))
    dbname = os.environ.get("POSTGRES_DB", "macro_trading")
    user = os.environ.get("POSTGRES_USER", "macro_user")
    password = os.environ.get("POSTGRES_PASSWORD", "macro_pass")

    return psycopg2.connect(
        host=host, port=port, dbname=dbname,
        user=user, password=password,
    )


def load_positions() -> list[dict]:
    """Load all portfolio positions from the database.

    Returns:
        List of position dicts compatible with PositionManager._positions.
    """
    try:
        import psycopg2.extras
        conn = _get_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, instrument, asset_class, direction, quantity,
                       notional_brl, notional_usd, entry_price, entry_date,
                       entry_fx_rate, current_price, unrealized_pnl_brl,
                       unrealized_pnl_usd, realized_pnl_brl, realized_pnl_usd,
                       transaction_cost_brl, is_open, closed_at, close_price,
                       entry_dv01, entry_delta, entry_convexity,
                       entry_var_contribution, entry_spread_duration,
                       strategy_ids, strategy_weights, notes, metadata_json,
                       created_at, updated_at
                FROM portfolio_positions
                ORDER BY id
            """)
            rows = cur.fetchall()
        conn.close()

        positions = []
        for row in rows:
            pos = dict(row)
            # Parse JSON fields
            if isinstance(pos.get("strategy_ids"), str):
                try:
                    pos["strategy_ids"] = json.loads(pos["strategy_ids"])
                except Exception:
                    pass
            if isinstance(pos.get("strategy_weights"), str):
                try:
                    pos["strategy_weights"] = json.loads(pos["strategy_weights"])
                except Exception:
                    pass
            if isinstance(pos.get("metadata_json"), str):
                try:
                    pos["metadata_json"] = json.loads(pos["metadata_json"])
                except Exception:
                    pass
            positions.append(pos)

        logger.info("Loaded %d positions from DB", len(positions))
        return positions

    except Exception as exc:
        logger.warning("Failed to load positions from DB: %s", exc)
        return []


def load_trade_proposals() -> list[dict]:
    """Load all trade proposals from the database.

    Returns:
        List of proposal dicts compatible with TradeWorkflowService._proposals.
    """
    try:
        import psycopg2.extras
        conn = _get_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, created_at, updated_at, instrument, asset_class,
                       direction, suggested_notional_brl, suggested_quantity,
                       conviction, signal_source, strategy_ids, rationale,
                       risk_impact, status, reviewed_by, reviewed_at,
                       execution_price, execution_notional_brl, position_id,
                       notes, metadata_json
                FROM trade_proposals
                ORDER BY id
            """)
            rows = cur.fetchall()
        conn.close()

        proposals = []
        for row in rows:
            prop = dict(row)
            # Parse JSON fields
            for field in ("strategy_ids", "risk_impact", "metadata_json"):
                if isinstance(prop.get(field), str):
                    try:
                        prop[field] = json.loads(prop[field])
                    except Exception:
                        pass
            # Ensure compatibility with TradeWorkflowService expected fields
            prop.setdefault("as_of_date", prop.get("created_at", datetime.utcnow()).date()
                            if isinstance(prop.get("created_at"), datetime)
                            else date.today())
            # Add agent_id and agent fields for frontend compatibility
            if prop.get("signal_source") and not prop.get("agent_id"):
                prop["agent_id"] = prop["signal_source"]
                prop["agent"] = prop["signal_source"].replace("_agent", "")
            proposals.append(prop)

        logger.info("Loaded %d trade proposals from DB", len(proposals))
        return proposals

    except Exception as exc:
        logger.warning("Failed to load trade proposals from DB: %s", exc)
        return []


def load_daily_briefing(briefing_date: date | None = None) -> dict | None:
    """Load the latest daily briefing from the database.

    Args:
        briefing_date: Specific date to load. If None, loads the latest.

    Returns:
        Briefing dict compatible with MorningPackService, or None.
    """
    try:
        import psycopg2.extras
        conn = _get_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if briefing_date:
                cur.execute("""
                    SELECT * FROM daily_briefings
                    WHERE briefing_date = %s
                    LIMIT 1
                """, (briefing_date,))
            else:
                cur.execute("""
                    SELECT * FROM daily_briefings
                    ORDER BY briefing_date DESC
                    LIMIT 1
                """)
            row = cur.fetchone()
        conn.close()

        if row is None:
            return None

        briefing = dict(row)
        # Parse JSONB fields
        for field in ("market_snapshot", "regime_assessment", "agent_views",
                      "top_signals", "signal_changes", "portfolio_state",
                      "trade_proposals", "action_items", "metadata_json"):
            val = briefing.get(field)
            if isinstance(val, str):
                try:
                    briefing[field] = json.loads(val)
                except Exception:
                    pass

        # Map to MorningPackService expected format
        result = {
            "id": str(briefing.get("id", "")),
            "briefing_date": briefing["briefing_date"],
            "created_at": briefing["created_at"],
            "action_items": briefing.get("action_items", []),
            "trade_proposals": briefing.get("trade_proposals", []),
            "market_snapshot": briefing.get("market_snapshot", {}),
            "agent_views": briefing.get("agent_views", []),
            "regime": briefing.get("regime_assessment", {}),
            "top_signals": briefing.get("top_signals", []),
            "signal_changes": briefing.get("signal_changes", {}),
            "portfolio_state": briefing.get("portfolio_state", {}),
            "macro_narrative": briefing.get("macro_narrative", ""),
        }

        logger.info("Loaded daily briefing for %s from DB", briefing["briefing_date"])
        return result

    except Exception as exc:
        logger.warning("Failed to load daily briefing from DB: %s", exc)
        return None


def hydrate_position_manager(pm) -> None:
    """Load positions from DB into a PositionManager instance.

    Args:
        pm: PositionManager instance to hydrate.
    """
    positions = load_positions()
    if positions:
        pm._positions = positions
        logger.info("Hydrated PositionManager with %d positions", len(positions))


def hydrate_trade_workflow(wf) -> None:
    """Load proposals from DB into a TradeWorkflowService instance.

    Also hydrates the underlying PositionManager.

    Args:
        wf: TradeWorkflowService instance to hydrate.
    """
    # Hydrate position manager first
    hydrate_position_manager(wf.position_manager)

    # Load proposals
    proposals = load_trade_proposals()
    if proposals:
        wf._proposals = proposals
        logger.info("Hydrated TradeWorkflowService with %d proposals", len(proposals))


def hydrate_morning_pack_service(mps) -> None:
    """Load briefings from DB into a MorningPackService instance.

    Args:
        mps: MorningPackService instance to hydrate.
    """
    briefing = load_daily_briefing()
    if briefing:
        mps._briefings = [briefing]
        logger.info("Hydrated MorningPackService with latest briefing")

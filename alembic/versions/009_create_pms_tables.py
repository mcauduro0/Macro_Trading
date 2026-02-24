"""create PMS tables: portfolio_positions, trade_proposals, decision_journal,
daily_briefings, position_pnl_history (hypertable) + immutability trigger

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-02-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "i9j0k1l2m3n4"
down_revision: Union[str, None] = "h8i9j0k1l2m3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. portfolio_positions ───────────────────────────────────────────
    op.create_table(
        "portfolio_positions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("instrument", sa.String(50), nullable=False),
        sa.Column("asset_class", sa.String(30), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column("notional_brl", sa.Float(), nullable=False),
        sa.Column("notional_usd", sa.Float(), nullable=True),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("entry_fx_rate", sa.Float(), nullable=True),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("unrealized_pnl_brl", sa.Float(), nullable=True),
        sa.Column("unrealized_pnl_usd", sa.Float(), nullable=True),
        sa.Column("realized_pnl_brl", sa.Float(), nullable=True),
        sa.Column("realized_pnl_usd", sa.Float(), nullable=True),
        sa.Column("transaction_cost_brl", sa.Float(), nullable=True),
        sa.Column("is_open", sa.Boolean(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_price", sa.Float(), nullable=True),
        # Risk snapshot at entry
        sa.Column("entry_dv01", sa.Float(), nullable=True),
        sa.Column("entry_delta", sa.Float(), nullable=True),
        sa.Column("entry_convexity", sa.Float(), nullable=True),
        sa.Column("entry_var_contribution", sa.Float(), nullable=True),
        sa.Column("entry_spread_duration", sa.Float(), nullable=True),
        # Strategy linkage
        sa.Column("strategy_ids", JSONB(), nullable=True),
        sa.Column("strategy_weights", JSONB(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_portfolio_positions"),
    )

    op.create_index(
        "ix_portfolio_positions_instrument",
        "portfolio_positions",
        ["instrument"],
    )
    op.create_index(
        "ix_portfolio_positions_is_open",
        "portfolio_positions",
        ["is_open"],
    )
    op.create_index(
        "ix_portfolio_positions_is_open_asset_class",
        "portfolio_positions",
        ["is_open", "asset_class"],
    )

    # ── 2. trade_proposals ───────────────────────────────────────────────
    op.create_table(
        "trade_proposals",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("instrument", sa.String(50), nullable=False),
        sa.Column("asset_class", sa.String(30), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("suggested_notional_brl", sa.Float(), nullable=False),
        sa.Column("suggested_quantity", sa.Float(), nullable=True),
        sa.Column("conviction", sa.Float(), nullable=False),
        sa.Column("signal_source", sa.String(100), nullable=True),
        sa.Column("strategy_ids", JSONB(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("risk_impact", JSONB(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reviewed_by", sa.String(100), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_price", sa.Float(), nullable=True),
        sa.Column("execution_notional_brl", sa.Float(), nullable=True),
        sa.Column(
            "position_id",
            sa.BigInteger(),
            sa.ForeignKey("portfolio_positions.id"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_trade_proposals"),
    )

    op.create_index(
        "ix_trade_proposals_status",
        "trade_proposals",
        ["status"],
    )

    # ── 3. decision_journal ──────────────────────────────────────────────
    op.create_table(
        "decision_journal",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("entry_type", sa.String(30), nullable=False),
        sa.Column(
            "position_id",
            sa.BigInteger(),
            sa.ForeignKey("portfolio_positions.id"),
            nullable=True,
        ),
        sa.Column(
            "proposal_id",
            sa.BigInteger(),
            sa.ForeignKey("trade_proposals.id"),
            nullable=True,
        ),
        sa.Column("instrument", sa.String(50), nullable=True),
        sa.Column("direction", sa.String(10), nullable=True),
        sa.Column("notional_brl", sa.Float(), nullable=True),
        sa.Column("entry_price", sa.Float(), nullable=True),
        sa.Column("manager_notes", sa.Text(), nullable=True),
        sa.Column("system_notes", sa.Text(), nullable=True),
        sa.Column("market_snapshot", JSONB(), nullable=True),
        sa.Column("portfolio_snapshot", JSONB(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("is_locked", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_decision_journal"),
    )

    op.create_index(
        "ix_decision_journal_entry_type",
        "decision_journal",
        ["entry_type"],
    )
    op.create_index(
        "ix_decision_journal_position_id",
        "decision_journal",
        ["position_id"],
    )
    op.create_index(
        "ix_decision_journal_created_at",
        "decision_journal",
        ["created_at"],
    )

    # ── 4. daily_briefings ───────────────────────────────────────────────
    op.create_table(
        "daily_briefings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("briefing_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("market_snapshot", JSONB(), nullable=True),
        sa.Column("regime_assessment", JSONB(), nullable=True),
        sa.Column("agent_views", JSONB(), nullable=True),
        sa.Column("top_signals", JSONB(), nullable=True),
        sa.Column("signal_changes", JSONB(), nullable=True),
        sa.Column("portfolio_state", JSONB(), nullable=True),
        sa.Column("trade_proposals", JSONB(), nullable=True),
        sa.Column("risk_summary", JSONB(), nullable=True),
        sa.Column("macro_narrative", sa.Text(), nullable=True),
        sa.Column("action_items", JSONB(), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_daily_briefings"),
        sa.UniqueConstraint("briefing_date", name="uq_daily_briefings_briefing_date"),
    )

    # ── 5. position_pnl_history (TimescaleDB hypertable) ─────────────────
    op.create_table(
        "position_pnl_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("position_id", sa.BigInteger(), nullable=False),
        sa.Column("instrument", sa.String(50), nullable=False),
        sa.Column("mark_price", sa.Float(), nullable=False),
        sa.Column("unrealized_pnl_brl", sa.Float(), nullable=False),
        sa.Column("unrealized_pnl_usd", sa.Float(), nullable=True),
        sa.Column("daily_pnl_brl", sa.Float(), nullable=True),
        sa.Column("daily_pnl_usd", sa.Float(), nullable=True),
        sa.Column("cumulative_pnl_brl", sa.Float(), nullable=True),
        sa.Column("dv01", sa.Float(), nullable=True),
        sa.Column("delta", sa.Float(), nullable=True),
        sa.Column("var_contribution", sa.Float(), nullable=True),
        sa.Column("fx_rate", sa.Float(), nullable=True),
        sa.Column("is_manual_override", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.PrimaryKeyConstraint(
            "id", "snapshot_date", name="pk_position_pnl_history"
        ),
        sa.UniqueConstraint(
            "snapshot_date",
            "position_id",
            name="uq_position_pnl_history_natural_key",
        ),
    )

    # Convert to TimescaleDB hypertable with 90-day chunks
    op.execute(
        "SELECT create_hypertable('position_pnl_history', 'snapshot_date', "
        "migrate_data => true, chunk_time_interval => INTERVAL '90 days')"
    )

    # Enable compression with segmentby = position_id
    op.execute(
        "ALTER TABLE position_pnl_history SET ("
        "  timescaledb.compress,"
        "  timescaledb.compress_segmentby = 'position_id'"
        ")"
    )

    # Compress chunks older than 60 days
    op.execute(
        "SELECT add_compression_policy('position_pnl_history', INTERVAL '60 days')"
    )

    # ── 6. DecisionJournal immutability trigger ──────────────────────────
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_journal_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.is_locked = TRUE THEN
                RAISE EXCEPTION 'Cannot modify or delete locked decision journal entry (id=%)', OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_decision_journal_immutable
        BEFORE UPDATE OR DELETE ON decision_journal
        FOR EACH ROW
        EXECUTE FUNCTION prevent_journal_modification();
        """
    )


def downgrade() -> None:
    # Drop trigger and function first
    op.execute("DROP TRIGGER IF EXISTS trg_decision_journal_immutable ON decision_journal")
    op.execute("DROP FUNCTION IF EXISTS prevent_journal_modification()")

    # Remove compression policy before dropping hypertable
    op.execute(
        "SELECT remove_compression_policy('position_pnl_history', if_exists => true)"
    )

    # Drop tables in reverse dependency order
    op.drop_table("position_pnl_history")
    op.drop_table("daily_briefings")
    op.drop_table("decision_journal")
    op.drop_table("trade_proposals")
    op.drop_table("portfolio_positions")

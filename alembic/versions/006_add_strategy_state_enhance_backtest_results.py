"""add strategy_state table and enhance backtest_results with v2 columns

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-02-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6g7h8i9j0k1"
down_revision: Union[str, None] = "e5f6g7h8i9j0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------------------------------------------------------------
    # 1. Create strategy_state table (SFWK-03)
    # ---------------------------------------------------------------
    op.create_table(
        "strategy_state",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("strategy_id", sa.String(50), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("strength", sa.String(10), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("z_score", sa.Float(), nullable=True),
        sa.Column("raw_value", sa.Float(), nullable=True),
        sa.Column("suggested_size", sa.Float(), nullable=True),
        sa.Column("instruments", JSONB(), nullable=True),
        sa.Column("entry_level", sa.Float(), nullable=True),
        sa.Column("stop_loss", sa.Float(), nullable=True),
        sa.Column("take_profit", sa.Float(), nullable=True),
        sa.Column("holding_period_days", sa.Integer(), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_strategy_state"),
    )
    # Single-column index on strategy_id
    op.create_index(
        "ix_strategy_state_strategy_id",
        "strategy_state",
        ["strategy_id"],
    )
    # Composite index on (strategy_id, timestamp DESC) for time-series queries
    op.create_index(
        "ix_strategy_state_strat_ts",
        "strategy_state",
        ["strategy_id", sa.text("timestamp DESC")],
    )

    # ---------------------------------------------------------------
    # 2. Add v2 columns to backtest_results (SFWK-04)
    # ---------------------------------------------------------------
    op.add_column(
        "backtest_results",
        sa.Column("run_timestamp", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "backtest_results",
        sa.Column("params_json", JSONB(), nullable=True),
    )
    op.add_column(
        "backtest_results",
        sa.Column("daily_returns_json", JSONB(), nullable=True),
    )
    op.add_column(
        "backtest_results",
        sa.Column("avg_holding_days", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    # Remove v2 columns from backtest_results
    op.drop_column("backtest_results", "avg_holding_days")
    op.drop_column("backtest_results", "daily_returns_json")
    op.drop_column("backtest_results", "params_json")
    op.drop_column("backtest_results", "run_timestamp")

    # Drop strategy_state table
    op.drop_index("ix_strategy_state_strat_ts", table_name="strategy_state")
    op.drop_index("ix_strategy_state_strategy_id", table_name="strategy_state")
    op.drop_table("strategy_state")

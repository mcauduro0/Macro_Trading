"""add strategy_signals hypertable and backtest_results table

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-02-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6g7h8i9"
down_revision: Union[str, None] = "c3d4e5f6g7h8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- strategy_signals: hypertable for per-strategy signal persistence --
    # (Schema only; signal writes added in Phase 11 when strategies are built)
    op.create_table(
        "strategy_signals",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("strategy_id", sa.String(50), nullable=False),
        sa.Column("signal_date", sa.Date(), nullable=False),
        sa.Column("ticker", sa.String(50), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", "signal_date", name="pk_strategy_signals"),
    )
    op.execute(
        "SELECT create_hypertable('strategy_signals', 'signal_date', "
        "chunk_time_interval => INTERVAL '1 year', if_not_exists => TRUE);"
    )
    op.create_index(
        "ix_strategy_signals_strategy_date",
        "strategy_signals",
        ["strategy_id", "signal_date"],
    )

    # -- backtest_results: regular table (low volume, one row per backtest run) --
    op.create_table(
        "backtest_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("strategy_id", sa.String(50), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("initial_capital", sa.Float(), nullable=False),
        sa.Column("final_equity", sa.Float(), nullable=True),
        sa.Column("total_return", sa.Float(), nullable=True),
        sa.Column("annualized_return", sa.Float(), nullable=True),
        sa.Column("annualized_volatility", sa.Float(), nullable=True),
        sa.Column("sharpe_ratio", sa.Float(), nullable=True),
        sa.Column("sortino_ratio", sa.Float(), nullable=True),
        sa.Column("calmar_ratio", sa.Float(), nullable=True),
        sa.Column("max_drawdown", sa.Float(), nullable=True),
        sa.Column("win_rate", sa.Float(), nullable=True),
        sa.Column("profit_factor", sa.Float(), nullable=True),
        sa.Column("total_trades", sa.Integer(), nullable=True),
        sa.Column("equity_curve", JSONB(), nullable=True),
        sa.Column("monthly_returns", JSONB(), nullable=True),
        sa.Column("config_json", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_backtest_results"),
    )
    op.create_index(
        "ix_backtest_results_strategy_id",
        "backtest_results",
        ["strategy_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_backtest_results_strategy_id")
    op.drop_table("backtest_results")
    op.drop_index("ix_strategy_signals_strategy_date")
    op.drop_table("strategy_signals")

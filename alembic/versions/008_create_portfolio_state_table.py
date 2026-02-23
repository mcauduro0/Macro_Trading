"""create portfolio_state hypertable for position persistence

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-02-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h8i9j0k1l2m3"
down_revision: Union[str, None] = "g7h8i9j0k1l2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_state",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("instrument", sa.String(50), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("notional", sa.Float(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=True),
        sa.Column("unrealized_pnl", sa.Float(), nullable=True),
        sa.Column("strategy_attribution", JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id", "timestamp", name="pk_portfolio_state"),
    )

    # Natural key uniqueness
    op.create_unique_constraint(
        "uq_portfolio_state_natural_key",
        "portfolio_state",
        ["timestamp", "instrument"],
    )

    # Convert to TimescaleDB hypertable
    op.execute(
        "SELECT create_hypertable('portfolio_state', 'timestamp', "
        "migrate_data => true)"
    )

    # Compression policy: compress chunks older than 30 days
    op.execute(
        "ALTER TABLE portfolio_state SET ("
        "  timescaledb.compress,"
        "  timescaledb.compress_segmentby = 'instrument'"
        ")"
    )
    op.execute(
        "SELECT add_compression_policy('portfolio_state', INTERVAL '30 days')"
    )


def downgrade() -> None:
    # Remove compression policy first
    op.execute(
        "SELECT remove_compression_policy('portfolio_state', if_exists => true)"
    )
    op.drop_constraint(
        "uq_portfolio_state_natural_key", "portfolio_state", type_="unique"
    )
    op.drop_table("portfolio_state")

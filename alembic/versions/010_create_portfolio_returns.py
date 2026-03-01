"""create portfolio_returns hypertable for daily portfolio-level returns

Used by risk endpoints (VaR, stress, limits, dashboard) and portfolio
attribution to compute historical risk metrics.

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-03-01

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "j0k1l2m3n4o5"
down_revision: Union[str, None] = "i9j0k1l2m3n4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_returns",
        sa.Column("return_date", sa.Date(), nullable=False),
        sa.Column("daily_return", sa.Float(), nullable=False),
        sa.Column("cumulative_return", sa.Float(), nullable=True),
        sa.Column("portfolio_nav", sa.Float(), nullable=True),
        sa.Column("n_instruments", sa.Integer(), nullable=True),
        sa.Column("weighting_method", sa.String(30), server_default="equal_weight"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("return_date", name="pk_portfolio_returns"),
    )

    # Convert to TimescaleDB hypertable with 90-day chunks
    op.execute(
        "SELECT create_hypertable('portfolio_returns', 'return_date', "
        "migrate_data => true, chunk_time_interval => INTERVAL '90 days')"
    )

    op.create_index(
        "ix_portfolio_returns_date",
        "portfolio_returns",
        ["return_date"],
    )


def downgrade() -> None:
    op.drop_table("portfolio_returns")

"""create pipeline_runs table

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-02-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6g7h8i9j0"
down_revision: Union[str, None] = "d4e5f6g7h8i9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pipeline_runs: regular table (low volume -- one row per daily run)
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("step_timings", JSONB(), nullable=True),
        sa.Column("signal_count", sa.Integer(), nullable=True),
        sa.Column("position_count", sa.Integer(), nullable=True),
        sa.Column("regime", sa.String(30), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pipeline_runs"),
    )
    op.create_index(
        "ix_pipeline_runs_run_date",
        "pipeline_runs",
        ["run_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_pipeline_runs_run_date")
    op.drop_table("pipeline_runs")

"""add agent_reports table

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6g7h8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_id", sa.String(50), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("signals_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("narrative", sa.Text(), nullable=True),
        sa.Column("model_diagnostics", JSONB(), nullable=True),
        sa.Column("data_quality_flags", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agent_reports"),
    )
    op.create_index(
        "ix_agent_reports_agent_id_date",
        "agent_reports",
        ["agent_id", "as_of_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_reports_agent_id_date")
    op.drop_table("agent_reports")

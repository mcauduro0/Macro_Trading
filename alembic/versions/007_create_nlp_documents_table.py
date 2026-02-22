"""create nlp_documents table for central bank document storage

Revision ID: g7h8i9j0k1l2
Revises: f6g7h8i9j0k1
Create Date: 2026-02-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g7h8i9j0k1l2"
down_revision: Union[str, None] = "f6g7h8i9j0k1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nlp_documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("doc_type", sa.String(30), nullable=False),
        sa.Column("doc_date", sa.Date(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("hawk_score", sa.Float(), nullable=True),
        sa.Column("dove_score", sa.Float(), nullable=True),
        sa.Column("change_score", sa.String(30), nullable=True),
        sa.Column("key_phrases", JSONB(), nullable=True),
        sa.Column("url", sa.String(500), nullable=True),
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
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_nlp_documents"),
    )

    # Natural key uniqueness: one document per (source, doc_type, doc_date)
    op.create_unique_constraint(
        "uq_nlp_documents_natural_key",
        "nlp_documents",
        ["source", "doc_type", "doc_date"],
    )

    # Composite index for efficient lookups by source and date
    op.create_index(
        "ix_nlp_documents_source_doc_date",
        "nlp_documents",
        ["source", "doc_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_nlp_documents_source_doc_date", table_name="nlp_documents")
    op.drop_constraint(
        "uq_nlp_documents_natural_key", "nlp_documents", type_="unique"
    )
    op.drop_table("nlp_documents")

"""Add instrument_type, maturity_date, and contract_specs to instruments table.

These columns are required by the GUIA Etapa 2 specification:
- instrument_type: FUTURE, BOND, SWAP, OPTION, CDS, NDF, SPOT, INDEX, ETF, FRA
- maturity_date: nullable date for futures/bonds
- contract_specs: JSONB with multiplier, tick_size, margin, settlement_type

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "instruments",
        sa.Column(
            "instrument_type",
            sa.String(20),
            nullable=True,
            comment="FUTURE, BOND, SWAP, OPTION, CDS, NDF, SPOT, INDEX, ETF, FRA",
        ),
    )
    op.add_column(
        "instruments",
        sa.Column("maturity_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "instruments",
        sa.Column(
            "contract_specs",
            JSONB,
            nullable=True,
            comment="multiplier, tick_size, margin, settlement_type",
        ),
    )


def downgrade() -> None:
    op.drop_column("instruments", "contract_specs")
    op.drop_column("instruments", "maturity_date")
    op.drop_column("instruments", "instrument_type")

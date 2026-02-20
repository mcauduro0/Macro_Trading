"""Initial schema with 10 tables, 7 hypertables, and compression policies.

Creates the complete database schema for the Macro Trading system:
- 3 metadata tables: data_sources, instruments, series_metadata
- 7 TimescaleDB hypertables: market_data, macro_series, curves,
  flow_data, fiscal_data, vol_surfaces, signals
- Compression policies on all 7 hypertables

Revision ID: a1b2c3d4e5f6
Revises: None
Create Date: 2026-02-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # Step 1: Enable TimescaleDB extension
    # -----------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")

    # -----------------------------------------------------------------------
    # Step 2: Create metadata tables (referenced by hypertables via FK)
    # -----------------------------------------------------------------------

    # data_sources -- provider registry
    op.create_table(
        "data_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("auth_type", sa.String(50), nullable=False),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=True),
        sa.Column("default_locale", sa.String(10), nullable=False, server_default="en-US"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_data_sources"),
        sa.UniqueConstraint("name", name="uq_data_sources_name"),
    )

    # instruments -- tradeable instrument registry
    op.create_table(
        "instruments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("asset_class", sa.String(50), nullable=False),
        sa.Column("country", sa.String(10), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("exchange", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_instruments"),
        sa.UniqueConstraint("ticker", name="uq_instruments_ticker"),
    )

    # series_metadata -- data series registry
    op.create_table(
        "series_metadata",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("series_code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("country", sa.String(10), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("decimal_separator", sa.String(5), nullable=False, server_default="."),
        sa.Column("date_format", sa.String(20), nullable=False, server_default="YYYY-MM-DD"),
        sa.Column("is_revisable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("release_lag_days", sa.Integer(), nullable=True),
        sa.Column("release_timezone", sa.String(50), nullable=False, server_default="UTC"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_series_metadata"),
        sa.ForeignKeyConstraint(
            ["source_id"], ["data_sources.id"],
            name="fk_series_metadata_source_id_data_sources",
        ),
        sa.UniqueConstraint("source_id", "series_code", name="uq_series_metadata_source_series"),
    )

    # -----------------------------------------------------------------------
    # Step 2b: Create hypertable tables (with composite PKs including time)
    # -----------------------------------------------------------------------

    # market_data -- OHLCV price/rate time series
    op.create_table(
        "market_data",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("frequency", sa.String(20), nullable=False, server_default="daily"),
        sa.Column("open", sa.Float(), nullable=True),
        sa.Column("high", sa.Float(), nullable=True),
        sa.Column("low", sa.Float(), nullable=True),
        sa.Column("close", sa.Float(), nullable=True),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("adjusted_close", sa.Float(), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint("id", "timestamp", name="pk_market_data"),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"],
            name="fk_market_data_instrument_id_instruments",
        ),
        sa.UniqueConstraint(
            "instrument_id", "timestamp", "frequency",
            name="uq_market_data_natural_key",
        ),
    )
    op.create_index("ix_market_data_instrument_id", "market_data", ["instrument_id"])

    # macro_series -- economic/macro data with point-in-time correctness
    op.create_table(
        "macro_series",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("series_id", sa.Integer(), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column(
            "release_time", sa.DateTime(timezone=True), nullable=False,
            comment="When this value became known (TIMESTAMPTZ)",
        ),
        sa.Column("revision_number", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint("id", "observation_date", name="pk_macro_series"),
        sa.ForeignKeyConstraint(
            ["series_id"], ["series_metadata.id"],
            name="fk_macro_series_series_id_series_metadata",
        ),
        sa.UniqueConstraint(
            "series_id", "observation_date", "revision_number",
            name="uq_macro_series_natural_key",
        ),
    )
    op.create_index("ix_macro_series_series_id", "macro_series", ["series_id"])

    # curves -- yield curve, swap curve, breakeven curve data
    op.create_table(
        "curves",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("curve_id", sa.String(50), nullable=False),
        sa.Column("curve_date", sa.Date(), nullable=False),
        sa.Column("tenor_days", sa.Integer(), nullable=False),
        sa.Column("tenor_label", sa.String(20), nullable=False),
        sa.Column("rate", sa.Float(), nullable=False),
        sa.Column("curve_type", sa.String(20), nullable=False),
        sa.Column("source", sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint("id", "curve_date", name="pk_curves"),
        sa.UniqueConstraint(
            "curve_id", "curve_date", "tenor_days",
            name="uq_curves_natural_key",
        ),
    )
    op.create_index("ix_curves_curve_id", "curves", ["curve_id"])

    # flow_data -- FX and capital flow time series
    op.create_table(
        "flow_data",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("series_id", sa.Integer(), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("flow_type", sa.String(50), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False, server_default="USD_MM"),
        sa.Column("release_time", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", "observation_date", name="pk_flow_data"),
        sa.ForeignKeyConstraint(
            ["series_id"], ["series_metadata.id"],
            name="fk_flow_data_series_id_series_metadata",
        ),
        sa.UniqueConstraint(
            "series_id", "observation_date", "flow_type",
            name="uq_flow_data_natural_key",
        ),
    )
    op.create_index("ix_flow_data_series_id", "flow_data", ["series_id"])

    # fiscal_data -- government fiscal metrics time series
    op.create_table(
        "fiscal_data",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("series_id", sa.Integer(), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("fiscal_metric", sa.String(50), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False, server_default="BRL_MM"),
        sa.Column("release_time", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", "observation_date", name="pk_fiscal_data"),
        sa.ForeignKeyConstraint(
            ["series_id"], ["series_metadata.id"],
            name="fk_fiscal_data_series_id_series_metadata",
        ),
        sa.UniqueConstraint(
            "series_id", "observation_date", "fiscal_metric",
            name="uq_fiscal_data_natural_key",
        ),
    )
    op.create_index("ix_fiscal_data_series_id", "fiscal_data", ["series_id"])

    # vol_surfaces -- implied volatility surface data
    op.create_table(
        "vol_surfaces",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("surface_date", sa.Date(), nullable=False),
        sa.Column("delta", sa.Float(), nullable=False),
        sa.Column("tenor_days", sa.Integer(), nullable=False),
        sa.Column("implied_vol", sa.Float(), nullable=False),
        sa.Column("call_put", sa.String(4), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint("id", "surface_date", name="pk_vol_surfaces"),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"],
            name="fk_vol_surfaces_instrument_id_instruments",
        ),
        sa.UniqueConstraint(
            "instrument_id", "surface_date", "delta", "tenor_days",
            name="uq_vol_surfaces_natural_key",
        ),
    )
    op.create_index("ix_vol_surfaces_instrument_id", "vol_surfaces", ["instrument_id"])

    # signals -- trading signal output time series
    op.create_table(
        "signals",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("signal_type", sa.String(50), nullable=False),
        sa.Column("signal_date", sa.Date(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=True),
        sa.Column("series_id", sa.Integer(), nullable=True),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", "signal_date", name="pk_signals"),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"],
            name="fk_signals_instrument_id_instruments",
        ),
        sa.ForeignKeyConstraint(
            ["series_id"], ["series_metadata.id"],
            name="fk_signals_series_id_series_metadata",
        ),
        sa.UniqueConstraint(
            "signal_type", "signal_date", "instrument_id",
            name="uq_signals_natural_key",
        ),
    )
    op.create_index("ix_signals_signal_type", "signals", ["signal_type"])

    # -----------------------------------------------------------------------
    # Step 3: Convert 7 tables to TimescaleDB hypertables
    # -----------------------------------------------------------------------

    # Market data: daily frequency, 1-month chunks
    op.execute("""
        SELECT create_hypertable(
            'market_data', 'timestamp',
            chunk_time_interval => INTERVAL '1 month',
            if_not_exists => TRUE
        );
    """)

    # Macro series: sparse data, 1-year chunks
    op.execute("""
        SELECT create_hypertable(
            'macro_series', 'observation_date',
            chunk_time_interval => INTERVAL '1 year',
            if_not_exists => TRUE
        );
    """)

    # Curves: daily frequency, 3-month chunks
    op.execute("""
        SELECT create_hypertable(
            'curves', 'curve_date',
            chunk_time_interval => INTERVAL '3 months',
            if_not_exists => TRUE
        );
    """)

    # Flow data, fiscal data, vol surfaces, signals: 1-year chunks
    for table, time_col in [
        ("flow_data", "observation_date"),
        ("fiscal_data", "observation_date"),
        ("vol_surfaces", "surface_date"),
        ("signals", "signal_date"),
    ]:
        op.execute(f"""
            SELECT create_hypertable(
                '{table}', '{time_col}',
                chunk_time_interval => INTERVAL '1 year',
                if_not_exists => TRUE
            );
        """)

    # -----------------------------------------------------------------------
    # Step 4: Enable compression on all 7 hypertables
    # -----------------------------------------------------------------------
    hypertable_compression = [
        ("market_data", "instrument_id", "timestamp DESC"),
        ("macro_series", "series_id", "observation_date DESC"),
        ("curves", "curve_id", "curve_date DESC"),
        ("flow_data", "series_id", "observation_date DESC"),
        ("fiscal_data", "series_id", "observation_date DESC"),
        ("vol_surfaces", "instrument_id", "surface_date DESC"),
        ("signals", "signal_type", "signal_date DESC"),
    ]

    for table, segmentby, orderby in hypertable_compression:
        op.execute(f"""
            ALTER TABLE {table} SET (
                timescaledb.compress,
                timescaledb.compress_segmentby = '{segmentby}',
                timescaledb.compress_orderby = '{orderby}'
            );
        """)

    # -----------------------------------------------------------------------
    # Step 5: Add compression policies (generous delays)
    # Policies are configured but only compress chunks older than the
    # specified interval. After backfill in Phase 4, these activate
    # automatically on historical data.
    # -----------------------------------------------------------------------
    compression_policies = [
        ("market_data", "30 days"),
        ("macro_series", "90 days"),
        ("curves", "90 days"),
        ("flow_data", "90 days"),
        ("fiscal_data", "180 days"),
        ("vol_surfaces", "90 days"),
        ("signals", "90 days"),
    ]

    for table, delay in compression_policies:
        op.execute(f"""
            SELECT add_compression_policy('{table}', INTERVAL '{delay}');
        """)


def downgrade() -> None:
    # -----------------------------------------------------------------------
    # Step 1: Remove compression policies
    # -----------------------------------------------------------------------
    for table in [
        "signals", "vol_surfaces", "fiscal_data",
        "flow_data", "curves", "macro_series", "market_data",
    ]:
        op.execute(f"SELECT remove_compression_policy('{table}', if_exists => true);")
        op.execute(f"ALTER TABLE {table} SET (timescaledb.compress = false);")

    # -----------------------------------------------------------------------
    # Step 2: Drop tables in reverse dependency order
    # (hypertables first, then metadata tables)
    # -----------------------------------------------------------------------
    op.drop_index("ix_signals_signal_type", table_name="signals")
    op.drop_table("signals")

    op.drop_index("ix_vol_surfaces_instrument_id", table_name="vol_surfaces")
    op.drop_table("vol_surfaces")

    op.drop_index("ix_fiscal_data_series_id", table_name="fiscal_data")
    op.drop_table("fiscal_data")

    op.drop_index("ix_flow_data_series_id", table_name="flow_data")
    op.drop_table("flow_data")

    op.drop_index("ix_curves_curve_id", table_name="curves")
    op.drop_table("curves")

    op.drop_index("ix_macro_series_series_id", table_name="macro_series")
    op.drop_table("macro_series")

    op.drop_index("ix_market_data_instrument_id", table_name="market_data")
    op.drop_table("market_data")

    op.drop_table("series_metadata")
    op.drop_table("instruments")
    op.drop_table("data_sources")

    # -----------------------------------------------------------------------
    # Step 3: Drop TimescaleDB extension
    # -----------------------------------------------------------------------
    op.execute("DROP EXTENSION IF EXISTS timescaledb CASCADE;")

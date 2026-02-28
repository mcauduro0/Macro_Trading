"""PMS (Portfolio Management System) v4.0 models.

5 SQLAlchemy 2.0 ORM models for the Portfolio Management System:
  - PortfolioPosition: live and closed positions with dual notional and risk snapshot
  - TradeProposal: pending/approved/rejected trade proposals
  - DecisionJournal: immutable audit log with SHA256 content hashes
  - DailyBriefing: daily morning-pack briefings (market + portfolio state)
  - PositionPnLHistory: TimescaleDB hypertable for daily P&L snapshots

Created by Alembic migration 009.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class PortfolioPosition(Base):
    """Live and closed portfolio positions.

    Stores BRL-primary notional with optional USD conversion, full risk
    snapshot at entry (DV01, delta, convexity, VaR contribution, spread
    duration), and strategy attribution via JSONB fields.

    Non-hypertable: single BigInteger PK with standard indexes.
    """

    __tablename__ = "portfolio_positions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    instrument: Mapped[str] = mapped_column(String(50), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(30), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notional_brl: Mapped[float] = mapped_column(Float, nullable=False)
    notional_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    entry_fx_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unrealized_pnl_brl: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, default=0.0
    )
    unrealized_pnl_usd: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, default=0.0
    )
    realized_pnl_brl: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, default=0.0
    )
    realized_pnl_usd: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, default=0.0
    )
    transaction_cost_brl: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, default=0.0
    )
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    close_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Risk snapshot at entry
    entry_dv01: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    entry_delta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    entry_convexity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    entry_var_contribution: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    entry_spread_duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Strategy linkage
    strategy_ids: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    strategy_weights: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_portfolio_positions_instrument", "instrument"),
        Index("ix_portfolio_positions_is_open", "is_open"),
        Index("ix_portfolio_positions_is_open_asset_class", "is_open", "asset_class"),
    )

    def __repr__(self) -> str:
        return (
            f"<PortfolioPosition("
            f"id={self.id}, "
            f"instrument={self.instrument!r}, "
            f"direction={self.direction!r}, "
            f"notional_brl={self.notional_brl}, "
            f"is_open={self.is_open})>"
        )


class TradeProposal(Base):
    """Pending, approved, or rejected trade proposals.

    Captures signal-generated or discretionary trade ideas with conviction
    scoring, pre-trade risk impact, and eventual execution linkage back
    to a PortfolioPosition.
    """

    __tablename__ = "trade_proposals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    instrument: Mapped[str] = mapped_column(String(50), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(30), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    suggested_notional_brl: Mapped[float] = mapped_column(Float, nullable=False)
    suggested_quantity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    conviction: Mapped[float] = mapped_column(Float, nullable=False)
    signal_source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    strategy_ids: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_impact: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    execution_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    execution_notional_brl: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    position_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("portfolio_positions.id"),
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (Index("ix_trade_proposals_status", "status"),)

    def __repr__(self) -> str:
        return (
            f"<TradeProposal("
            f"id={self.id}, "
            f"instrument={self.instrument!r}, "
            f"status={self.status!r})>"
        )


class DecisionJournal(Base):
    """Immutable audit log of all portfolio decisions.

    Each entry captures the decision context: trade parameters, manager/system
    notes, market snapshot (SELIC, USDBRL, VIX, DI rates), and portfolio
    snapshot (AUM, leverage, VaR). A SHA256 content_hash provides integrity
    verification. A PostgreSQL trigger enforces DB-level immutability on
    locked rows.
    """

    __tablename__ = "decision_journal"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    entry_type: Mapped[str] = mapped_column(String(30), nullable=False)
    position_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("portfolio_positions.id"),
        nullable=True,
    )
    proposal_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("trade_proposals.id"),
        nullable=True,
    )
    instrument: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    direction: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    notional_brl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    entry_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    manager_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    system_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    market_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    portfolio_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_decision_journal_entry_type", "entry_type"),
        Index("ix_decision_journal_position_id", "position_id"),
        Index("ix_decision_journal_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<DecisionJournal("
            f"id={self.id}, "
            f"entry_type={self.entry_type!r}, "
            f"instrument={self.instrument!r})>"
        )


class DailyBriefing(Base):
    """Daily morning-pack briefing snapshot.

    One row per trading day capturing market conditions, regime assessment,
    agent views, top signals, portfolio state, trade proposals, risk summary,
    and a macro narrative. Consumed by the MorningPack UI (Phase 22).
    """

    __tablename__ = "daily_briefings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    briefing_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    market_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    regime_assessment: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    agent_views: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    top_signals: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    signal_changes: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    portfolio_state: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    trade_proposals: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    risk_summary: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    macro_narrative: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_items: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<DailyBriefing(" f"id={self.id}, " f"briefing_date={self.briefing_date})>"
        )


class PositionPnLHistory(Base):
    """Daily P&L snapshots per position -- TimescaleDB hypertable.

    Composite PK on (id, snapshot_date) for hypertable compatibility.
    Natural key: (snapshot_date, position_id).
    Compression: segmentby=position_id, 90-day chunks, compress after 60 days.

    NOTE: position_id references portfolio_positions.id conceptually but
    has NO FK constraint for TimescaleDB hypertable compatibility.
    """

    __tablename__ = "position_pnl_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_date: Mapped[date] = mapped_column(Date, primary_key=True, nullable=False)
    position_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    instrument: Mapped[str] = mapped_column(String(50), nullable=False)
    mark_price: Mapped[float] = mapped_column(Float, nullable=False)
    unrealized_pnl_brl: Mapped[float] = mapped_column(Float, nullable=False)
    unrealized_pnl_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    daily_pnl_brl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    daily_pnl_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cumulative_pnl_brl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dv01: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    delta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    var_contribution: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fx_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_manual_override: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "snapshot_date",
            "position_id",
            name="uq_position_pnl_history_natural_key",
        ),
        {"comment": "TimescaleDB hypertable partitioned on snapshot_date"},
    )

    def __repr__(self) -> str:
        return (
            f"<PositionPnLHistory("
            f"position_id={self.position_id}, "
            f"snapshot_date={self.snapshot_date}, "
            f"instrument={self.instrument!r})>"
        )

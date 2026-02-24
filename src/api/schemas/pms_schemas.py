"""Pydantic v2 request/response schemas for the PMS (Portfolio Management System) API.

Covers all request bodies for position/proposal operations and typed response
models for portfolio book, trade proposals, journal entries, and P&L analytics.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Generic API envelope
# ---------------------------------------------------------------------------
T = TypeVar("T")


class APIEnvelope(BaseModel, Generic[T]):
    """Standard API response wrapper."""

    status: str = "ok"
    data: T
    meta: dict[str, Any] = Field(default_factory=dict)


# =====================================================================
# REQUEST MODELS
# =====================================================================


class OpenPositionRequest(BaseModel):
    """Request body for POST /book/positions/open."""

    instrument: str
    asset_class: str
    direction: str = Field(..., description="LONG or SHORT")
    notional_brl: float = Field(..., gt=0)
    execution_price: float = Field(..., gt=0)
    entry_date: Optional[date] = None
    manager_thesis: str = Field(..., min_length=5)
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    time_horizon: Optional[str] = None
    strategy_ids: list[str] = Field(default_factory=list)


class ClosePositionRequest(BaseModel):
    """Request body for POST /book/positions/{id}/close."""

    close_price: float = Field(..., gt=0)
    close_date: Optional[date] = None
    manager_notes: Optional[str] = None
    outcome_notes: Optional[str] = None


class UpdatePriceRequest(BaseModel):
    """Request body for POST /book/positions/{id}/update-price."""

    price: float = Field(..., gt=0)


class MTMRequest(BaseModel):
    """Request body for POST /book/mtm."""

    price_overrides: dict[str, float] = Field(default_factory=dict)
    fx_rate: float = 5.0


class ApproveProposalRequest(BaseModel):
    """Request body for POST /proposals/{id}/approve."""

    execution_price: float = Field(..., gt=0)
    execution_notional_brl: float = Field(..., gt=0)
    manager_notes: Optional[str] = None
    manager_thesis: Optional[str] = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    time_horizon: Optional[str] = None


class RejectProposalRequest(BaseModel):
    """Request body for POST /proposals/{id}/reject."""

    manager_notes: str = Field(..., min_length=3)


class ModifyApproveRequest(BaseModel):
    """Request body for POST /proposals/{id}/modify-approve."""

    modified_direction: Optional[str] = None
    modified_notional_brl: Optional[float] = Field(default=None, gt=0)
    execution_price: Optional[float] = Field(default=None, gt=0)
    manager_notes: Optional[str] = None


class GenerateProposalsRequest(BaseModel):
    """Request body for POST /proposals/generate."""

    signals: Optional[list[dict[str, Any]]] = None
    as_of_date: Optional[date] = None


class OutcomeRequest(BaseModel):
    """Request body for recording trade outcome notes."""

    outcome_notes: str = Field(..., min_length=5)
    realized_pnl_assessment: Optional[str] = Field(
        default=None, description="GOOD, BAD, or NEUTRAL"
    )


# =====================================================================
# RESPONSE MODELS
# =====================================================================


class PositionResponse(BaseModel):
    """Single position detail."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    instrument: str
    asset_class: str
    direction: str
    notional_brl: float
    entry_price: float
    entry_date: Optional[date] = None
    current_price: Optional[float] = None
    unrealized_pnl_brl: Optional[float] = None
    unrealized_pnl_usd: Optional[float] = None
    realized_pnl_brl: Optional[float] = None
    realized_pnl_usd: Optional[float] = None
    transaction_cost_brl: Optional[float] = None
    is_open: bool = True
    closed_at: Optional[datetime] = None
    close_price: Optional[float] = None
    quantity: Optional[float] = None
    notional_usd: Optional[float] = None
    entry_fx_rate: Optional[float] = None
    entry_dv01: Optional[float] = None
    entry_delta: Optional[float] = None
    entry_convexity: Optional[float] = None
    entry_var_contribution: Optional[float] = None
    entry_spread_duration: Optional[float] = None
    strategy_ids: Optional[list[str]] = None
    strategy_weights: Optional[dict[str, float]] = None
    notes: Optional[str] = None
    rate_pct: Optional[float] = None
    business_days: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BookSummaryResponse(BaseModel):
    """Portfolio book summary metrics."""

    model_config = ConfigDict(from_attributes=True)

    aum: float = 0.0
    total_notional_brl: float = 0.0
    leverage: float = 0.0
    open_positions: int = 0
    pnl_today_brl: float = 0.0
    pnl_mtd_brl: float = 0.0
    pnl_ytd_brl: float = 0.0
    total_unrealized_pnl_brl: float = 0.0
    total_realized_pnl_brl: float = 0.0


class BookResponse(BaseModel):
    """Full portfolio book with summary, positions, and breakdowns."""

    model_config = ConfigDict(from_attributes=True)

    summary: BookSummaryResponse
    positions: list[PositionResponse]
    by_asset_class: dict[str, dict[str, Any]] = Field(default_factory=dict)
    closed_today: list[PositionResponse] = Field(default_factory=list)


class TradeProposalResponse(BaseModel):
    """Single trade proposal detail."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    instrument: str
    asset_class: str
    direction: str
    suggested_notional_brl: float = 0.0
    conviction: float = 0.0
    signal_source: Optional[str] = None
    strategy_ids: Optional[list[str]] = None
    rationale: Optional[str] = None
    risk_impact: Optional[dict[str, Any]] = None
    status: str = "PENDING"
    execution_price: Optional[float] = None
    execution_notional_brl: Optional[float] = None
    position_id: Optional[int] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None


class JournalEntryResponse(BaseModel):
    """Decision journal entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None
    entry_type: str
    position_id: Optional[int] = None
    proposal_id: Optional[int] = None
    instrument: Optional[str] = None
    direction: Optional[str] = None
    notional_brl: Optional[float] = None
    manager_notes: Optional[str] = None
    system_notes: Optional[str] = None
    content_hash: Optional[str] = None
    is_locked: bool = True


class PnLPointResponse(BaseModel):
    """Single point on the P&L equity curve."""

    model_config = ConfigDict(from_attributes=True)

    snapshot_date: date
    daily_pnl_brl: float = 0.0
    cumulative_pnl_brl: float = 0.0


# =====================================================================
# MORNING PACK SCHEMAS
# =====================================================================


class ActionItemResponse(BaseModel):
    """Single action item from the morning briefing."""

    priority: str  # CRITICAL, HIGH, MEDIUM, LOW
    category: str
    description: str
    urgency: str


class MorningPackResponse(BaseModel):
    """Full morning pack briefing response."""

    model_config = ConfigDict(from_attributes=True)

    id: Any
    briefing_date: date
    created_at: datetime
    action_items: Any  # list[ActionItemResponse] or unavailable marker
    trade_proposals: Any
    market_snapshot: Any
    agent_views: Any
    regime: Any
    top_signals: Any
    signal_changes: Any
    portfolio_state: Any
    macro_narrative: Any


class MorningPackSummaryResponse(BaseModel):
    """Compact morning pack summary for history listing."""

    briefing_date: date
    action_items_count: int
    narrative_excerpt: Optional[str] = None


class GenerateMorningPackRequest(BaseModel):
    """Request body for POST /pms/morning-pack/generate."""

    briefing_date: Optional[date] = None
    force: bool = False


# =====================================================================
# RISK MONITOR SCHEMAS
# =====================================================================


class VaRSnapshotResponse(BaseModel):
    """VaR snapshot with parametric and Monte Carlo estimates."""

    parametric_95: float = 0.0
    parametric_99: float = 0.0
    monte_carlo_95: Optional[float] = None
    monte_carlo_99: Optional[float] = None
    limit_95_pct: float = 2.0
    limit_99_pct: float = 3.0
    utilization_95_pct: float = 0.0
    utilization_99_pct: float = 0.0


class RiskAlertResponse(BaseModel):
    """Single risk alert."""

    type: str
    severity: str  # WARNING or BREACH
    message: str
    value: float
    limit: float


class LiveRiskResponse(BaseModel):
    """Complete live risk snapshot."""

    as_of_date: date
    var: Any
    leverage: Any
    drawdown: Any
    concentration: Any
    stress_tests: list[Any] = Field(default_factory=list)
    limits_summary: Any
    alerts: list[RiskAlertResponse] = Field(default_factory=list)


class RiskTrendPointResponse(BaseModel):
    """Single point on the risk trend chart."""

    date: date
    var_95: float = 0.0
    leverage_gross: float = 0.0
    drawdown_pct: float = 0.0
    alert_count: int = 0


# =====================================================================
# ATTRIBUTION SCHEMAS
# =====================================================================


class AttributionByStrategyResponse(BaseModel):
    """Strategy-level P&L attribution."""

    strategy_id: str
    pnl_brl: float
    return_contribution_pct: float
    trades_count: int = 0
    win_rate_pct: float = 0.0


class AttributionByAssetClassResponse(BaseModel):
    """Asset-class-level P&L attribution."""

    asset_class: str
    pnl_brl: float
    return_contribution_pct: float
    avg_notional_brl: float = 0.0


class AttributionResponse(BaseModel):
    """Complete multi-dimensional P&L attribution response."""

    period: dict
    total_pnl_brl: float
    total_return_pct: float
    by_strategy: list[Any] = Field(default_factory=list)
    by_asset_class: list[Any] = Field(default_factory=list)
    by_instrument: list[Any] = Field(default_factory=list)
    by_factor: list[Any] = Field(default_factory=list)
    by_time_period: list[Any] = Field(default_factory=list)
    by_trade_type: Any = Field(default_factory=dict)
    performance_stats: Any = Field(default_factory=dict)


class EquityCurvePointResponse(BaseModel):
    """Single point on the equity curve."""

    date: date
    equity_brl: float
    return_pct_daily: float = 0.0
    return_pct_cumulative: float = 0.0
    drawdown_pct: float = 0.0

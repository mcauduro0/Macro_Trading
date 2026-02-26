"""CrossAssetView frozen dataclass and builder pattern.

CrossAssetView is the structured output from the enhanced CrossAssetAgent v2,
providing regime classification, per-asset-class views, risk metrics, key trades,
narrative, and consistency issue tracking.

All dataclasses are frozen (immutable after creation). CrossAssetViewBuilder
collects data incrementally and produces a frozen CrossAssetView via .build().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


# ---------------------------------------------------------------------------
# Supporting frozen dataclasses
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AssetClassView:
    """Directional view for a single asset class.

    Attributes:
        asset_class: Name of asset class (e.g., "FX", "rates", "equities").
        direction: Directional view ("LONG", "SHORT", "NEUTRAL").
        conviction: Conviction score 0.0 to 1.0.
        key_driver: Primary driver of the view.
        instruments: List of relevant instruments.
    """

    asset_class: str
    direction: str
    conviction: float
    key_driver: str
    instruments: tuple[str, ...] = ()


@dataclass(frozen=True)
class TailRiskAssessment:
    """Composite tail risk assessment.

    Attributes:
        composite_score: Overall tail risk score 0-100.
        regime_transition_prob: Probability of transitioning to adverse regime.
        market_indicators: Dict of market stress indicators.
        assessment: Human-readable level ("low", "moderate", "elevated", "critical").
    """

    composite_score: float
    regime_transition_prob: float
    market_indicators: tuple[tuple[str, float], ...] = ()
    assessment: str = "low"


@dataclass(frozen=True)
class KeyTrade:
    """Top-conviction trade recommendation.

    Attributes:
        instrument: Instrument identifier.
        direction: Trade direction ("LONG" or "SHORT").
        conviction: Conviction score 0.0 to 1.0.
        rationale: Brief explanation for the trade.
        strategy_id: Originating strategy identifier.
    """

    instrument: str
    direction: str
    conviction: float
    rationale: str
    strategy_id: str = ""


@dataclass(frozen=True)
class ConsistencyIssue:
    """Flagged contradiction between signals.

    Attributes:
        rule_id: Identifier for the consistency rule that fired.
        description: Human-readable description of the contradiction.
        affected_instruments: Instruments affected by the contradiction.
        severity: "warning" or "critical".
        sizing_penalty: Sizing multiplier penalty (default 0.5).
    """

    rule_id: str
    description: str
    affected_instruments: tuple[str, ...] = ()
    severity: str = "warning"
    sizing_penalty: float = 0.5


# ---------------------------------------------------------------------------
# CrossAssetView frozen dataclass
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CrossAssetView:
    """Frozen cross-asset view produced by CrossAssetAgent v2.

    Contains regime classification, per-asset-class views, risk metrics,
    key trades, narrative, and consistency issue tracking.

    Attributes:
        regime: One of "Goldilocks", "Reflation", "Stagflation", "Deflation".
        regime_probabilities: Dict mapping regime name to probability (sums to ~1.0).
        asset_class_views: Per-asset-class directional views.
        risk_appetite: Composite risk appetite score 0-100.
        tail_risk: Tail risk assessment dataclass.
        key_trades: Top-3 trades by conviction.
        narrative: 3-5 sentence regime narrative.
        risk_warnings: Human-readable risk warnings.
        consistency_issues: Flagged contradictions from consistency checker.
        as_of_date: Point-in-time reference date.
        generated_at: UTC datetime when view was generated.
    """

    regime: str
    regime_probabilities: dict[str, float]
    asset_class_views: dict[str, AssetClassView] = field(default_factory=dict)
    risk_appetite: float = 50.0
    tail_risk: TailRiskAssessment | None = None
    key_trades: tuple[KeyTrade, ...] = ()
    narrative: str = ""
    risk_warnings: tuple[str, ...] = ()
    consistency_issues: tuple[ConsistencyIssue, ...] = ()
    as_of_date: date = field(default_factory=date.today)
    generated_at: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# CrossAssetViewBuilder
# ---------------------------------------------------------------------------
class CrossAssetViewBuilder:
    """Builder for incrementally constructing a CrossAssetView.

    Usage::

        builder = CrossAssetViewBuilder()
        builder.set_regime("Goldilocks")
        builder.set_regime_probabilities({"Goldilocks": 0.7, ...})
        builder.set_as_of_date(date.today())
        view = builder.build()
    """

    _VALID_REGIMES = {"Goldilocks", "Reflation", "Stagflation", "Deflation"}

    def __init__(self) -> None:
        self._regime: str | None = None
        self._regime_probabilities: dict[str, float] | None = None
        self._asset_class_views: dict[str, AssetClassView] = {}
        self._risk_appetite: float = 50.0
        self._tail_risk: TailRiskAssessment | None = None
        self._key_trades: list[KeyTrade] = []
        self._narrative: str = ""
        self._risk_warnings: list[str] = []
        self._consistency_issues: list[ConsistencyIssue] = []
        self._as_of_date: date | None = None

    def set_regime(self, regime: str) -> CrossAssetViewBuilder:
        """Set the regime classification.

        Args:
            regime: One of "Goldilocks", "Reflation", "Stagflation", "Deflation".

        Returns:
            Self for chaining.
        """
        self._regime = regime
        return self

    def set_regime_probabilities(
        self, probabilities: dict[str, float]
    ) -> CrossAssetViewBuilder:
        """Set regime probability vector.

        Args:
            probabilities: Dict mapping regime names to probabilities.

        Returns:
            Self for chaining.
        """
        self._regime_probabilities = dict(probabilities)
        return self

    def add_asset_class_view(self, view: AssetClassView) -> CrossAssetViewBuilder:
        """Add a per-asset-class directional view.

        Args:
            view: AssetClassView instance.

        Returns:
            Self for chaining.
        """
        self._asset_class_views[view.asset_class] = view
        return self

    def set_risk_appetite(self, score: float) -> CrossAssetViewBuilder:
        """Set composite risk appetite score.

        Args:
            score: Score in [0, 100].

        Returns:
            Self for chaining.
        """
        self._risk_appetite = max(0.0, min(100.0, score))
        return self

    def set_tail_risk(self, tail_risk: TailRiskAssessment) -> CrossAssetViewBuilder:
        """Set tail risk assessment.

        Args:
            tail_risk: TailRiskAssessment instance.

        Returns:
            Self for chaining.
        """
        self._tail_risk = tail_risk
        return self

    def add_key_trade(self, trade: KeyTrade) -> CrossAssetViewBuilder:
        """Add a key trade recommendation.

        Args:
            trade: KeyTrade instance.

        Returns:
            Self for chaining.
        """
        self._key_trades.append(trade)
        return self

    def set_narrative(self, narrative: str) -> CrossAssetViewBuilder:
        """Set the regime narrative.

        Args:
            narrative: 3-5 sentence regime narrative text.

        Returns:
            Self for chaining.
        """
        self._narrative = narrative
        return self

    def add_risk_warning(self, warning: str) -> CrossAssetViewBuilder:
        """Add a human-readable risk warning.

        Args:
            warning: Warning text.

        Returns:
            Self for chaining.
        """
        self._risk_warnings.append(warning)
        return self

    def add_consistency_issue(self, issue: ConsistencyIssue) -> CrossAssetViewBuilder:
        """Add a flagged consistency issue.

        Args:
            issue: ConsistencyIssue instance.

        Returns:
            Self for chaining.
        """
        self._consistency_issues.append(issue)
        return self

    def set_as_of_date(self, as_of_date: date) -> CrossAssetViewBuilder:
        """Set the point-in-time reference date.

        Args:
            as_of_date: Reference date.

        Returns:
            Self for chaining.
        """
        self._as_of_date = as_of_date
        return self

    def build(self) -> CrossAssetView:
        """Build and return a frozen CrossAssetView.

        Validates:
        - regime is set
        - regime_probabilities is set and sums to ~1.0

        Returns:
            Frozen CrossAssetView instance.

        Raises:
            ValueError: If required fields are missing or probabilities invalid.
        """
        if self._regime is None:
            raise ValueError("regime must be set before building CrossAssetView")

        if self._regime_probabilities is None:
            raise ValueError(
                "regime_probabilities must be set before building CrossAssetView"
            )

        prob_sum = sum(self._regime_probabilities.values())
        if abs(prob_sum - 1.0) > 0.01:
            raise ValueError(
                f"regime_probabilities must sum to ~1.0, got {prob_sum:.4f}"
            )

        if self._as_of_date is None:
            self._as_of_date = date.today()

        return CrossAssetView(
            regime=self._regime,
            regime_probabilities=dict(self._regime_probabilities),
            asset_class_views=dict(self._asset_class_views),
            risk_appetite=self._risk_appetite,
            tail_risk=self._tail_risk,
            key_trades=tuple(self._key_trades),
            narrative=self._narrative,
            risk_warnings=tuple(self._risk_warnings),
            consistency_issues=tuple(self._consistency_issues),
            as_of_date=self._as_of_date,
            generated_at=datetime.utcnow(),
        )

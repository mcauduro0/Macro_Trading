"""Cross-Asset Agent v2 -- regime detection, correlation breaks, risk sentiment,
HMM regime classification, consistency checking, and structured CrossAssetView.

Implements CrossAssetAgent with three quantitative models plus v2 enhancements:

1. **RegimeDetectionModel** -- Composite risk-on/risk-off regime score from
   6 macro z-scores. Positive composite = risk-off factors elevated.
   Score in [-1, +1]; SHORT above +0.2, LONG below -0.2.

2. **CorrelationAnalysis** -- Rolling 63-day correlation break detector across
   5 asset pairs. Fires NEUTRAL alert when any pair shows |z| > 2.0
   (regime-neutral signal, not directional).

3. **RiskSentimentIndex** -- Weighted 0-100 fear/greed composite from 6
   subscores. Below 30 = fear (SHORT risk assets); above 70 = greed (LONG).

v2 Enhancements:
- **HMMRegimeClassifier** -- 4-state HMM with rule-based fallback producing
  full probability vector.
- **CrossAssetConsistencyChecker** -- 7 rules detecting signal contradictions
  with 0.5x sizing penalty on affected instruments.
- **CrossAssetView** -- Frozen dataclass output with regime, probabilities,
  asset class views, risk metrics, key trades, narrative, and consistency issues.

CrossAssetAgent is the 5th and final agent in the pipeline, registered last
in AgentRegistry.EXECUTION_ORDER. It provides the global risk regime context
that all strategies use to scale positions.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

from src.agents.base import AgentSignal, BaseAgent, classify_strength
from src.agents.consistency_checker import CrossAssetConsistencyChecker
from src.agents.cross_asset_view import (
    AssetClassView,
    CrossAssetView,
    CrossAssetViewBuilder,
    KeyTrade,
    TailRiskAssessment,
)
from src.agents.data_loader import PointInTimeDataLoader
from src.agents.features.cross_asset_features import CrossAssetFeatureEngine
from src.agents.hmm_regime import HMMRegimeClassifier
from src.core.enums import SignalDirection, SignalStrength

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RegimeDetectionModel
# ---------------------------------------------------------------------------
class RegimeDetectionModel:
    """Risk-on/risk-off regime detector from macro z-score composite.

    Reads ``_regime_components`` -- dict of 6 direction-corrected z-scores
    (positive = risk-off). Composite = nanmean, clipped to [-1, +1].

    Direction mapping:
    - composite > +0.2 --> SHORT (risk-off, reduce risk asset exposure)
    - composite < -0.2 --> LONG  (risk-on, increase risk asset exposure)
    - else              --> NEUTRAL
    """

    SIGNAL_ID = "CROSSASSET_REGIME"

    def run(self, features: dict, as_of_date: date) -> AgentSignal:
        """Compute regime detection signal.

        Args:
            features: Feature dict from CrossAssetFeatureEngine.compute().
            as_of_date: Point-in-time reference date.

        Returns:
            AgentSignal with CROSSASSET_REGIME signal_id.
        """

        def _no_signal(reason: str = "") -> AgentSignal:
            logger.debug("regime_model_no_signal: %s", reason)
            return AgentSignal(
                signal_id=self.SIGNAL_ID,
                agent_id="cross_asset_agent",
                timestamp=datetime.utcnow(),
                as_of_date=as_of_date,
                direction=SignalDirection.NEUTRAL,
                strength=SignalStrength.NO_SIGNAL,
                confidence=0.0,
                value=0.0,
                horizon_days=63,
                metadata={"reason": reason},
            )

        raw = features.get("_regime_components")
        if raw is None or not isinstance(raw, dict):
            return _no_signal("no_regime_components")

        values = [v for v in raw.values() if not (isinstance(v, float) and np.isnan(v))]
        if not values:
            return _no_signal("all_nan_components")

        composite = float(np.nanmean(values))
        score = float(np.clip(composite / 2.0, -1.0, 1.0))

        # Direction thresholds
        if score > 0.2:
            direction = SignalDirection.SHORT  # risk-off
        elif score < -0.2:
            direction = SignalDirection.LONG  # risk-on
        else:
            direction = SignalDirection.NEUTRAL

        confidence = min(1.0, abs(score) * 2.0)
        strength = classify_strength(confidence)

        return AgentSignal(
            signal_id=self.SIGNAL_ID,
            agent_id="cross_asset_agent",
            timestamp=datetime.utcnow(),
            as_of_date=as_of_date,
            direction=direction,
            strength=strength,
            confidence=confidence,
            value=round(score, 4),
            horizon_days=63,
            metadata={
                "regime_score": round(score, 4),
                "n_factors": len(values),
                "components": {
                    k: round(v, 4)
                    for k, v in raw.items()
                    if not (isinstance(v, float) and np.isnan(v))
                },
            },
        )


# ---------------------------------------------------------------------------
# CorrelationAnalysis
# ---------------------------------------------------------------------------
class CorrelationAnalysis:
    """Rolling correlation break detector across asset pairs.

    Uses 63-day rolling windows to compute cross-asset correlations,
    then z-scores the current correlation against recent history.
    Fires a NEUTRAL alert when |z| > 2.0 (correlation break is a
    regime-neutral signal, not directional).
    """

    SIGNAL_ID = "CROSSASSET_CORRELATION"
    WINDOW = 63
    BREAK_Z = 2.0
    MIN_OBS = 130

    def run(self, features: dict, as_of_date: date) -> AgentSignal:
        """Compute correlation break signal.

        Args:
            features: Feature dict from CrossAssetFeatureEngine.compute().
            as_of_date: Point-in-time reference date.

        Returns:
            AgentSignal with CROSSASSET_CORRELATION signal_id.
        """

        def _no_signal(reason: str = "") -> AgentSignal:
            logger.debug("correlation_no_signal: %s", reason)
            return AgentSignal(
                signal_id=self.SIGNAL_ID,
                agent_id="cross_asset_agent",
                timestamp=datetime.utcnow(),
                as_of_date=as_of_date,
                direction=SignalDirection.NEUTRAL,
                strength=SignalStrength.NO_SIGNAL,
                confidence=0.0,
                value=0.0,
                horizon_days=63,
                metadata={"reason": reason},
            )

        raw_pairs = features.get("_correlation_pairs")
        if raw_pairs is None or not isinstance(raw_pairs, dict) or len(raw_pairs) == 0:
            return _no_signal("no_correlation_pairs")

        correlations: dict[str, float] = {}
        z_scores: dict[str, float] = {}
        breaks_detected: list[str] = []
        pairs_checked = 0

        for pair_name, pair_data in raw_pairs.items():
            if pair_data is None:
                continue

            sx, sy = pair_data
            current, z, is_break = self._compute_corr_break(sx, sy)

            if np.isnan(current):
                continue

            pairs_checked += 1
            correlations[pair_name] = round(current, 4)
            z_scores[pair_name] = round(z, 4) if not np.isnan(z) else 0.0

            if is_break:
                breaks_detected.append(pair_name)

        if pairs_checked == 0:
            return _no_signal("no_pairs_with_sufficient_data")

        max_z = max(abs(z) for z in z_scores.values()) if z_scores else 0.0

        # Direction: always NEUTRAL (correlation breaks are regime-neutral alerts)
        direction = SignalDirection.NEUTRAL

        # Strength based on max_z
        if max_z > 3.0:
            strength = SignalStrength.STRONG
        elif max_z > self.BREAK_Z:
            strength = SignalStrength.MODERATE
        elif max_z > 1.5:
            strength = SignalStrength.WEAK
        else:
            strength = SignalStrength.NO_SIGNAL

        confidence = min(1.0, max_z / 4.0)

        return AgentSignal(
            signal_id=self.SIGNAL_ID,
            agent_id="cross_asset_agent",
            timestamp=datetime.utcnow(),
            as_of_date=as_of_date,
            direction=direction,
            strength=strength,
            confidence=confidence,
            value=round(float(max_z), 4),
            horizon_days=63,
            metadata={
                "pairs_checked": pairs_checked,
                "breaks_detected": breaks_detected,
                "max_z": round(max_z, 4),
                "correlations": correlations,
            },
        )

    def _compute_corr_break(
        self, sx: pd.Series, sy: pd.Series
    ) -> tuple[float, float, bool]:
        """Compute correlation and z-score for a single pair.

        Args:
            sx: First time series.
            sy: Second time series.

        Returns:
            (current_corr, z_score, is_break)
        """
        try:
            aligned = pd.concat([sx, sy], axis=1).dropna()
            if len(aligned) < self.MIN_OBS:
                return float("nan"), float("nan"), False

            x, y = aligned.iloc[:, 0], aligned.iloc[:, 1]
            roll_corr = x.rolling(self.WINDOW).corr(y).dropna()

            if len(roll_corr) < self.WINDOW:
                return float("nan"), float("nan"), False

            current = float(roll_corr.iloc[-1])
            hist = roll_corr.iloc[-self.WINDOW - 1 : -1]
            hist_mean = float(hist.mean())
            hist_std = float(hist.std())
            z = (current - hist_mean) / hist_std if hist_std > 1e-8 else 0.0

            return current, z, abs(z) > self.BREAK_Z
        except Exception:
            return float("nan"), float("nan"), False


# ---------------------------------------------------------------------------
# RiskSentimentIndex
# ---------------------------------------------------------------------------
class RiskSentimentIndex:
    """Weighted fear/greed composite from 6 market subscores.

    Each subscore is in [0, 100] (100 = maximum greed/risk-on).
    Composite is a weighted mean (renormalized over available components).

    Direction mapping:
    - score < 30  --> SHORT (fear = risk-off = short risk assets)
    - score > 70  --> LONG  (greed = risk-on = long risk assets)
    - else        --> NEUTRAL
    """

    SIGNAL_ID = "CROSSASSET_SENTIMENT"
    WEIGHTS: dict[str, float] = {
        "vix": 0.25,
        "hy_oas": 0.20,
        "dxy": 0.15,
        "cftc_brl": 0.15,
        "em_flows": 0.15,
        "credit_proxy": 0.10,
    }

    def run(self, features: dict, as_of_date: date) -> AgentSignal:
        """Compute risk sentiment composite signal.

        Args:
            features: Feature dict from CrossAssetFeatureEngine.compute().
            as_of_date: Point-in-time reference date.

        Returns:
            AgentSignal with CROSSASSET_SENTIMENT signal_id.
        """

        def _no_signal(reason: str = "") -> AgentSignal:
            logger.debug("sentiment_no_signal: %s", reason)
            return AgentSignal(
                signal_id=self.SIGNAL_ID,
                agent_id="cross_asset_agent",
                timestamp=datetime.utcnow(),
                as_of_date=as_of_date,
                direction=SignalDirection.NEUTRAL,
                strength=SignalStrength.NO_SIGNAL,
                confidence=0.0,
                value=0.0,
                horizon_days=21,
                metadata={"reason": reason},
            )

        components = features.get("_sentiment_components")
        if components is None or not isinstance(components, dict):
            return _no_signal("no_sentiment_components")

        # Filter to non-NaN components
        available: dict[str, float] = {}
        for k, v in components.items():
            try:
                if v is not None and not (isinstance(v, float) and np.isnan(v)):
                    available[k] = float(v)
            except (TypeError, ValueError):
                continue

        if not available:
            return _no_signal("all_nan_components")

        # Compute weighted mean, renormalizing weights over available components
        total_weight = sum(self.WEIGHTS.get(k, 0.0) for k in available)
        if total_weight < 1e-8:
            return _no_signal("zero_weight")

        composite_score = sum(
            available[k] * self.WEIGHTS.get(k, 0.0) / total_weight for k in available
        )

        # Direction
        if composite_score < 30:
            direction = SignalDirection.SHORT  # fear
        elif composite_score > 70:
            direction = SignalDirection.LONG  # greed
        else:
            direction = SignalDirection.NEUTRAL

        confidence = abs(composite_score - 50) / 50
        strength = classify_strength(confidence)

        return AgentSignal(
            signal_id=self.SIGNAL_ID,
            agent_id="cross_asset_agent",
            timestamp=datetime.utcnow(),
            as_of_date=as_of_date,
            direction=direction,
            strength=strength,
            confidence=confidence,
            value=round(composite_score, 2),
            horizon_days=21,
            metadata={
                "composite_score": round(composite_score, 2),
                "components": {
                    k: round(v, 2)
                    for k, v in components.items()
                    if not (isinstance(v, float) and np.isnan(v))
                },
                "n_components": len(available),
            },
        )


# ---------------------------------------------------------------------------
# CrossAssetAgent
# ---------------------------------------------------------------------------
class CrossAssetAgent(BaseAgent):
    """Cross-asset agent producing 3 signals: regime, correlation, sentiment.

    Signals produced:
    1. CROSSASSET_REGIME       -- Risk-on/off regime composite [-1, +1]
    2. CROSSASSET_CORRELATION  -- Correlation break alerts (|z| > 2.0)
    3. CROSSASSET_SENTIMENT    -- Fear/greed index [0, 100]

    This is the 5th and final agent in AgentRegistry.EXECUTION_ORDER.
    """

    AGENT_ID = "cross_asset_agent"
    AGENT_NAME = "Cross-Asset Agent"

    def __init__(self, loader: PointInTimeDataLoader) -> None:
        super().__init__(self.AGENT_ID, self.AGENT_NAME)
        self.loader = loader
        self.feature_engine = CrossAssetFeatureEngine()
        self.regime_model = RegimeDetectionModel()
        self.correlation_model = CorrelationAnalysis()
        self.sentiment_model = RiskSentimentIndex()
        # v2 enhancements
        self.hmm_classifier = HMMRegimeClassifier()
        self.consistency_checker = CrossAssetConsistencyChecker()
        self._last_view: CrossAssetView | None = None

    # ------------------------------------------------------------------
    # BaseAgent abstract method implementations
    # ------------------------------------------------------------------
    def load_data(self, as_of_date: date) -> dict[str, Any]:
        """Load all cross-asset data using PointInTimeDataLoader.

        All data loads are individually guarded -- a failure for one series
        returns None for that key and lets the pipeline continue.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            Dictionary mapping series names to DataFrames (or None).
        """
        data: dict[str, Any] = {}

        def _safe_load(key: str, loader_fn, *args, **kwargs) -> None:
            try:
                data[key] = loader_fn(*args, **kwargs)
            except Exception as exc:
                self.log.warning("data_load_failed", key=key, error=str(exc))
                data[key] = None

        _safe_load(
            "vix", self.loader.get_market_data, "VIX", as_of_date, lookback_days=756
        )
        _safe_load(
            "dxy", self.loader.get_market_data, "DXY", as_of_date, lookback_days=756
        )
        _safe_load(
            "ibovespa",
            self.loader.get_market_data,
            "IBOVESPA",
            as_of_date,
            lookback_days=756,
        )
        _safe_load(
            "sp500", self.loader.get_market_data, "SP500", as_of_date, lookback_days=756
        )
        _safe_load(
            "oil_wti",
            self.loader.get_market_data,
            "OIL_WTI",
            as_of_date,
            lookback_days=756,
        )
        _safe_load(
            "usdbrl_ptax",
            self.loader.get_market_data,
            "USDBRL_PTAX",
            as_of_date,
            lookback_days=756,
        )
        _safe_load(
            "hy_oas",
            self.loader.get_macro_series,
            "FRED-BAMLH0A0HYM2",
            as_of_date,
            lookback_days=756,
        )
        _safe_load(
            "ust_2y",
            self.loader.get_macro_series,
            "FRED-DGS2",
            as_of_date,
            lookback_days=756,
        )
        _safe_load(
            "ust_10y",
            self.loader.get_macro_series,
            "FRED-DGS10",
            as_of_date,
            lookback_days=756,
        )
        _safe_load(
            "ust_5y",
            self.loader.get_macro_series,
            "FRED-DGS5",
            as_of_date,
            lookback_days=756,
        )
        _safe_load(
            "cftc_brl",
            self.loader.get_flow_data,
            "CFTC_6L_LEVERAGED_NET",
            as_of_date,
            lookback_days=756,
        )
        _safe_load(
            "bcb_flow",
            self.loader.get_flow_data,
            "BR_FX_FLOW_COMMERCIAL",
            as_of_date,
            lookback_days=365,
        )

        # v2: Growth and inflation z-score series for HMM features
        _safe_load(
            "growth_proxy",
            self.loader.get_macro_series,
            "BR_IBC_BR_YOY",
            as_of_date,
            lookback_days=756,
        )
        _safe_load(
            "ipca_12m",
            self.loader.get_macro_series,
            "BR_IPCA_12M",
            as_of_date,
            lookback_days=756,
        )

        # DI curve for credit proxy
        try:
            data["di_curve"] = self.loader.get_curve("DI", as_of_date)
        except Exception as exc:
            self.log.warning("di_curve_load_failed", error=str(exc))
            data["di_curve"] = {}

        data["_as_of_date"] = as_of_date
        return data

    def compute_features(self, data: dict) -> dict[str, Any]:
        """Compute cross-asset features from raw data.

        Args:
            data: Output of ``load_data()``.

        Returns:
            Feature dictionary with scalar values and private model keys.
        """
        as_of_date = data.get("_as_of_date")
        if as_of_date is None:
            as_of_date = date.today()
        return self.feature_engine.compute(data, as_of_date)

    def run_models(self, features: dict) -> list[AgentSignal]:
        """Execute all 3 cross-asset models and build CrossAssetView.

        Order: Regime -> Correlation -> Sentiment -> build CrossAssetView.

        Args:
            features: Output of ``compute_features()``.

        Returns:
            List of exactly 3 AgentSignal objects.
        """
        as_of_date = features["_as_of_date"]
        signals = []
        signals.append(self.regime_model.run(features, as_of_date))
        signals.append(self.correlation_model.run(features, as_of_date))
        signals.append(self.sentiment_model.run(features, as_of_date))

        # v2: Build CrossAssetView from signals and features
        try:
            self._last_view = self.build_cross_asset_view(signals, features)
        except Exception as exc:
            logger.warning("CrossAssetView build failed: %s", exc)
            self._last_view = None

        return signals

    # ------------------------------------------------------------------
    # v2: CrossAssetView builder
    # ------------------------------------------------------------------
    def build_cross_asset_view(
        self, signals: list[AgentSignal], features: dict
    ) -> CrossAssetView:
        """Build a CrossAssetView from agent signals and features.

        Uses HMMRegimeClassifier for regime probabilities and
        CrossAssetConsistencyChecker for contradiction detection.

        Args:
            signals: List of 3 AgentSignal objects from run_models().
            features: Feature dict from compute_features().

        Returns:
            Frozen CrossAssetView dataclass.
        """
        as_of_date = features.get("_as_of_date", date.today())
        builder = CrossAssetViewBuilder()

        # --- HMM regime classification ---
        feature_df = self._build_hmm_features(features)
        hmm_result = self.hmm_classifier.classify(feature_df, as_of_date)

        builder.set_regime(hmm_result.regime)
        builder.set_regime_probabilities(hmm_result.regime_probabilities)

        if hmm_result.warning:
            builder.add_risk_warning(hmm_result.warning)

        # --- Per-asset-class views from signals ---
        regime_sig = signals[0] if len(signals) > 0 else None
        sentiment_sig = signals[2] if len(signals) > 2 else None

        # FX view
        builder.add_asset_class_view(
            AssetClassView(
                asset_class="FX",
                direction=regime_sig.direction.value if regime_sig else "NEUTRAL",
                conviction=regime_sig.confidence if regime_sig else 0.0,
                key_driver="regime_risk_off_on",
                instruments=("USDBRL",),
            )
        )

        # Rates view
        builder.add_asset_class_view(
            AssetClassView(
                asset_class="rates",
                direction=regime_sig.direction.value if regime_sig else "NEUTRAL",
                conviction=regime_sig.confidence if regime_sig else 0.0,
                key_driver="regime_composite",
                instruments=("DI_PRE", "NTN_B_REAL"),
            )
        )

        # Equities view
        builder.add_asset_class_view(
            AssetClassView(
                asset_class="equities",
                direction=sentiment_sig.direction.value if sentiment_sig else "NEUTRAL",
                conviction=sentiment_sig.confidence if sentiment_sig else 0.0,
                key_driver="risk_sentiment_index",
                instruments=("IBOV_FUT",),
            )
        )

        # --- Risk appetite ---
        if sentiment_sig:
            builder.set_risk_appetite(sentiment_sig.value)

        # --- Tail risk ---
        regime_probs = hmm_result.regime_probabilities
        regime_transition_prob = regime_probs.get(
            "Stagflation", 0.0
        ) + regime_probs.get("Deflation", 0.0)

        vix_z = features.get("vix_zscore_252d", 0.0)
        if isinstance(vix_z, float) and np.isnan(vix_z):
            vix_z = 0.0
        credit_z = features.get("hy_oas_zscore_252d", 0.0)
        if isinstance(credit_z, float) and np.isnan(credit_z):
            credit_z = 0.0

        tail_composite = min(
            100.0,
            max(
                0.0,
                30.0 * abs(vix_z)
                + 30.0 * abs(credit_z)
                + 40.0 * regime_transition_prob,
            ),
        )

        if tail_composite >= 70:
            assessment = "critical"
        elif tail_composite >= 50:
            assessment = "elevated"
        elif tail_composite >= 30:
            assessment = "moderate"
        else:
            assessment = "low"

        builder.set_tail_risk(
            TailRiskAssessment(
                composite_score=round(tail_composite, 2),
                regime_transition_prob=round(regime_transition_prob, 4),
                market_indicators=(
                    ("VIX_z", round(vix_z, 4)),
                    ("credit_spread_z", round(credit_z, 4)),
                ),
                assessment=assessment,
            )
        )

        # --- Key trades: top-3 by confidence ---
        trade_candidates = []
        for sig in signals:
            if sig.direction != SignalDirection.NEUTRAL and sig.confidence > 0:
                instrument = sig.signal_id.replace("CROSSASSET_", "")
                trade_candidates.append(
                    KeyTrade(
                        instrument=instrument,
                        direction=sig.direction.value,
                        conviction=sig.confidence,
                        rationale=f"{sig.signal_id} signal ({sig.strength.value})",
                        strategy_id="cross_asset_agent",
                    )
                )

        trade_candidates.sort(key=lambda t: t.conviction, reverse=True)
        for trade in trade_candidates[:3]:
            builder.add_key_trade(trade)

        # --- Narrative ---
        narrative = self._build_view_narrative(
            hmm_result, sentiment_sig, regime_transition_prob, trade_candidates[:3]
        )
        builder.set_narrative(narrative)

        # --- Consistency checking ---
        agent_sigs_dict: dict[str, Any] = {}
        for sig in signals:
            agent_sigs_dict[sig.signal_id] = sig

        strategy_sigs_dict: dict[str, Any] = {}  # populated externally if available

        issues = self.consistency_checker.check(
            agent_sigs_dict, strategy_sigs_dict, hmm_result.regime
        )
        for issue in issues:
            builder.add_consistency_issue(issue)

        builder.set_as_of_date(as_of_date)
        return builder.build()

    def _build_hmm_features(self, features: dict) -> pd.DataFrame:
        """Build 6-column HMM feature DataFrame from feature dict.

        Columns: growth_z, inflation_z, VIX_z, credit_spread_z, FX_vol_z,
                 equity_momentum_z.

        Uses available z-scores from the feature engine, mapping them to
        HMM-expected column names. Returns a single-row DataFrame suitable
        for rule-based fallback (HMM needs >= 60 rows for full path).

        Args:
            features: Feature dict from compute_features().

        Returns:
            DataFrame with HMM feature columns.
        """
        # Map feature engine keys to HMM columns
        vix_z = features.get("vix_zscore_252d", 0.0)
        credit_z = features.get("hy_oas_zscore_252d", 0.0)
        dxy_z = features.get("dxy_zscore_252d", 0.0)
        bcb_z = features.get("bcb_flow_zscore", 0.0)

        # Use regime components for growth proxy
        regime_comps = features.get("_regime_components", {})
        # Growth: negative of ust_slope (inverted curve = low growth)
        growth_z = -regime_comps.get("ust_slope", 0.0) if regime_comps else 0.0

        # Inflation: use credit proxy or dxy as inflation proxy
        inflation_z = (
            credit_z * 0.5
        )  # credit spread partially reflects inflation expectations

        # Replace NaN with 0
        def _safe(v: float) -> float:
            if isinstance(v, float) and np.isnan(v):
                return 0.0
            return float(v)

        row = {
            "growth_z": _safe(growth_z),
            "inflation_z": _safe(inflation_z),
            "VIX_z": _safe(vix_z),
            "credit_spread_z": _safe(credit_z),
            "FX_vol_z": _safe(dxy_z),
            "equity_momentum_z": _safe(bcb_z),
        }

        return pd.DataFrame([row])

    @staticmethod
    def _build_view_narrative(
        hmm_result: Any,
        sentiment_sig: AgentSignal | None,
        regime_transition_prob: float,
        key_trades: list,
    ) -> str:
        """Build a 3-5 sentence regime narrative for CrossAssetView.

        Uses template-based generation (LLM narrative is in NarrativeGenerator).

        Args:
            hmm_result: HMMResult from classifier.
            sentiment_sig: Sentiment signal (or None).
            regime_transition_prob: Probability of adverse regime.
            key_trades: Top key trades.

        Returns:
            Narrative text string.
        """
        regime = hmm_result.regime
        prob = hmm_result.regime_probabilities.get(regime, 0.0)
        method = hmm_result.method

        sentences = []
        sentences.append(
            f"Current regime is {regime} ({prob:.0%} confidence via {method})."
        )

        if sentiment_sig:
            sent_val = sentiment_sig.value
            sent_dir = sentiment_sig.direction.value
            sentences.append(f"Risk sentiment at {sent_val:.0f}/100 ({sent_dir}).")

        if regime_transition_prob > 0.3:
            sentences.append(
                f"Elevated regime transition risk at {regime_transition_prob:.0%} "
                f"probability of moving to Stagflation/Deflation."
            )

        if key_trades:
            trade_strs = [f"{t.direction} {t.instrument}" for t in key_trades[:3]]
            sentences.append(f"Key trades: {', '.join(trade_strs)}.")

        if hmm_result.warning:
            sentences.append(f"Note: {hmm_result.warning}")

        return " ".join(sentences)

    def generate_narrative(self, signals: list[AgentSignal], features: dict) -> str:
        """Generate a human-readable cross-asset analysis summary.

        Uses CrossAssetView narrative when available (v2), falling back to
        the original format.

        Args:
            signals: List of 3 AgentSignal objects from run_models().
            features: Feature dict from compute_features().

        Returns:
            Formatted analysis text summarizing all signals.
        """
        # v2: Use CrossAssetView narrative if available
        if self._last_view and self._last_view.narrative:
            return self._last_view.narrative

        # Fallback to original format
        as_of = features.get("_as_of_date", "unknown")

        regime_sig = signals[0] if len(signals) > 0 else None
        corr_sig = signals[1] if len(signals) > 1 else None
        sentiment_sig = signals[2] if len(signals) > 2 else None

        regime_dir = regime_sig.direction.value if regime_sig else "N/A"
        regime_score = regime_sig.value if regime_sig else 0.0

        sentiment_score = sentiment_sig.value if sentiment_sig else 50.0
        sentiment_dir = sentiment_sig.direction.value if sentiment_sig else "N/A"

        n_breaks = len(corr_sig.metadata.get("breaks_detected", [])) if corr_sig else 0

        return (
            f"Cross-Asset Assessment ({as_of}): "
            f"Regime={regime_dir} ({regime_score:.2f}). "
            f"Sentiment={sentiment_score:.0f}/100 ({sentiment_dir}). "
            f"Correlation breaks={n_breaks}."
        )

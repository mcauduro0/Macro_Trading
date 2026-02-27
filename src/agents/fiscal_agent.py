"""Fiscal Agent — Brazil debt sustainability, fiscal impulse, and dominance risk.

Implements FiscalAgent with three quantitative models:

1. **DebtSustainabilityModel** — IMF-style 4-scenario, 5Y DSA using
   d_{t+1} = d_t*(1+r)/(1+g) - pb. Signals when baseline 5Y debt path
   rises or falls more than 5pp.

2. **FiscalImpulseModel** — 12M change in primary balance/GDP, z-scored.
   Positive z (improving pb) = fiscal contraction = SHORT. Negative z
   (deteriorating pb) = fiscal expansion = LONG.

3. **FiscalDominanceRisk** — Composite 0-100 score from 4 weighted
   components (debt level, r-g spread, pb trend, CB credibility).
   Maps to LONG/NEUTRAL/SHORT via locked thresholds (33, 66).

FiscalAgent aggregates into FISCAL_BR_COMPOSITE using equal weights
(1/3 each) with 0.70 conflict dampening.

Architecture decisions:
- Baseline-as-primary approach for DSA direction (baseline scenario drives signal).
- Confidence from scenario consensus (how many of 4 scenarios show stabilizing).
- FiscalDominanceRisk substitutes 50 (neutral) for NaN subscores.
- Equal weights for composite (all 3 signals are independent fiscal indicators).
- Conflict dampening: 0.70 when any active signal disagrees with plurality.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

from src.agents.base import AgentSignal, BaseAgent, classify_strength
from src.agents.data_loader import PointInTimeDataLoader
from src.agents.features.fiscal_features import FiscalFeatureEngine
from src.core.enums import SignalDirection, SignalStrength

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DebtSustainabilityModel
# ---------------------------------------------------------------------------
class DebtSustainabilityModel:
    """IMF-style Debt Sustainability Analysis — 4-scenario, 5Y projection.

    Formula: d_{t+1} = d_t * (1 + r) / (1 + g) - pb
    Scenarios: baseline, stress (+200bps r, -1pp g, -0.5pp pb),
               adjustment (+1.5pp pb), tailwind (-100bps r, +1pp g).

    Signal direction uses baseline-as-primary approach:
    - baseline_delta > THRESHOLD → LONG (rising debt = BRL bearish fiscal stress)
    - baseline_delta < -THRESHOLD → SHORT (declining debt = BRL positive)
    - else → NEUTRAL

    Confidence from scenario consensus: how many of 4 scenarios show stabilizing
    (delta <= 0). 4/4 → 1.0, 3/4 → 0.70, 2/4 → 0.40, 1/4 → 0.20, 0/4 → 0.05.
    """

    SIGNAL_ID = "FISCAL_BR_DSA"
    HORIZON = 5       # 5-year projection
    MIN_OBS = 12      # months of data required (graceful degradation for early backtest)
    THRESHOLD = 5.0   # pp change in terminal debt/GDP to trigger signal

    SCENARIOS: dict[str, dict[str, float]] = {
        "baseline":   {"r_adj": 0.0,  "g_adj": 0.0,  "pb_adj":  0.0},
        "stress":     {"r_adj": 2.0,  "g_adj": -1.0, "pb_adj": -0.5},
        "adjustment": {"r_adj": 0.0,  "g_adj": 0.0,  "pb_adj":  1.5},
        "tailwind":   {"r_adj": -1.0, "g_adj": 1.0,  "pb_adj":  0.0},
    }

    # Confidence mapping: stabilizing_count -> confidence
    _CONFIDENCE_MAP: dict[int, float] = {
        4: 1.0,
        3: 0.70,
        2: 0.40,
        1: 0.20,
        0: 0.05,
    }

    def run(self, features: dict, as_of_date: date) -> AgentSignal:
        """Compute DSA signal from feature dict.

        Args:
            features: Feature dict from FiscalFeatureEngine.compute().
            as_of_date: Point-in-time reference date.

        Returns:
            AgentSignal with FISCAL_BR_DSA signal_id.
        """

        def _no_signal(reason: str = "") -> AgentSignal:
            logger.debug("dsa_no_signal: %s", reason)
            return AgentSignal(
                signal_id=self.SIGNAL_ID,
                agent_id="fiscal_agent",
                timestamp=datetime.utcnow(),
                as_of_date=as_of_date,
                direction=SignalDirection.NEUTRAL,
                strength=SignalStrength.NO_SIGNAL,
                confidence=0.0,
                value=0.0,
                horizon_days=252 * self.HORIZON,
                metadata={"reason": reason},
            )

        # Validate _dsa_raw_data
        dsa_raw = features.get("_dsa_raw_data")
        if dsa_raw is None:
            return _no_signal("missing_dsa_raw_data")

        required_keys = ("debt_gdp", "r_nominal", "g_real", "pb_gdp")
        for k in required_keys:
            val = dsa_raw.get(k)
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return _no_signal(f"missing_data:{k}")

        # Check pb_history length >= MIN_OBS
        pb_history = features.get("_pb_history")
        if pb_history is None or not isinstance(pb_history, pd.Series) or len(pb_history) < self.MIN_OBS:
            return _no_signal("insufficient_history")

        # Extract DSA inputs
        d0: float = dsa_raw["debt_gdp"]
        pb: float = dsa_raw["pb_gdp"]
        focus_ipca_12m: float = dsa_raw.get("focus_ipca_12m", np.nan)

        # Baseline real interest rate: prefer DI 5Y stripped of inflation
        di_curve: dict = features.get("_di_curve", {})
        r_baseline_real: float = self._get_r_baseline_real(
            di_curve, focus_ipca_12m, dsa_raw
        )

        # Growth: prefer g_focus if available, else g_real
        g_baseline: float = dsa_raw.get("g_focus") or dsa_raw.get("g_real", np.nan)
        if g_baseline is None or (isinstance(g_baseline, float) and np.isnan(g_baseline)):
            g_baseline = dsa_raw.get("g_real", np.nan)
        if isinstance(g_baseline, float) and np.isnan(g_baseline):
            return _no_signal("missing_data:g_real")

        # Run 4 scenarios
        all_paths: dict[str, list[float]] = {}
        for name, params in self.SCENARIOS.items():
            r_adj: float = params["r_adj"]
            g_adj: float = params["g_adj"]
            pb_adj: float = params["pb_adj"]
            path = self._project_debt_path(
                d0,
                r_baseline_real + r_adj,
                g_baseline + g_adj,
                pb + pb_adj,
            )
            all_paths[name] = path

        baseline_path = all_paths["baseline"]
        baseline_delta = baseline_path[-1] - d0

        # Signal direction: baseline-as-primary
        if baseline_delta > self.THRESHOLD:
            direction = SignalDirection.LONG
        elif baseline_delta < -self.THRESHOLD:
            direction = SignalDirection.SHORT
        else:
            direction = SignalDirection.NEUTRAL

        # Confidence from scenario consensus (stabilizing = delta <= 0)
        stabilizing_count = sum(
            1 for path in all_paths.values() if (path[-1] - d0) <= 0
        )
        confidence = self._CONFIDENCE_MAP.get(stabilizing_count, 0.05)

        strength = classify_strength(confidence)
        value = round(baseline_delta, 4)

        scenario_metadata = {
            name: {
                "terminal": round(path[-1], 4),
                "delta": round(path[-1] - d0, 4),
            }
            for name, path in all_paths.items()
        }

        return AgentSignal(
            signal_id=self.SIGNAL_ID,
            agent_id="fiscal_agent",
            timestamp=datetime.utcnow(),
            as_of_date=as_of_date,
            direction=direction,
            strength=strength,
            confidence=confidence,
            value=value,
            horizon_days=252 * self.HORIZON,
            metadata={
                "d0": d0,
                "baseline_terminal": round(baseline_path[-1], 4),
                "scenarios": scenario_metadata,
                "r_baseline_real": round(r_baseline_real, 4),
                "g_baseline": round(g_baseline, 4),
                "pb": pb,
            },
        )

    def _project_debt_path(
        self, d0: float, r: float, g: float, pb: float, horizon: int | None = None
    ) -> list[float]:
        """Project debt/GDP ratio for horizon years.

        d_{t+1} = d_t * (1+r/100) / (1+g/100) - pb/100

        Args:
            d0: Initial debt/GDP ratio (%).
            r: Real interest rate (%).
            g: Real GDP growth rate (%).
            pb: Primary balance/GDP (%).
            horizon: Number of years to project (default: self.HORIZON).

        Returns:
            List of length horizon+1 starting from d0.
        """
        if horizon is None:
            horizon = self.HORIZON
        path = [d0]
        for _ in range(horizon):
            d_next = path[-1] * (1 + r / 100) / (1 + g / 100) - pb / 100
            path.append(d_next)
        return path

    def _get_r_baseline_real(
        self,
        di_curve: dict,
        focus_ipca_12m: float,
        dsa_raw: dict,
    ) -> float:
        """Get real baseline interest rate from DI 5Y if available.

        Falls back to r_real from dsa_raw if DI curve is missing.

        Args:
            di_curve: Dict of {tenor_days: rate}.
            focus_ipca_12m: Inflation expectations (%).
            dsa_raw: Raw DSA data dict with r_real fallback.

        Returns:
            Real interest rate in %.
        """
        fallback = dsa_raw.get("r_real", np.nan)
        if not di_curve:
            return float(fallback) if not isinstance(fallback, float) or not np.isnan(fallback) else 3.0

        # Find closest tenor to 1825 days (5Y)
        target_tenor = 1825
        try:
            closest_tenor = min(di_curve.keys(), key=lambda t: abs(t - target_tenor))
            di_5y = di_curve[closest_tenor]
            if not np.isnan(focus_ipca_12m):
                return float(di_5y) - float(focus_ipca_12m)
            return float(di_5y) - 4.0  # rough inflation assumption if focus missing
        except Exception as exc:
            logger.debug("di_5y_lookup_failed: %s", exc)
            return float(fallback) if not isinstance(fallback, float) or not np.isnan(fallback) else 3.0


# ---------------------------------------------------------------------------
# FiscalImpulseModel
# ---------------------------------------------------------------------------
class FiscalImpulseModel:
    """Fiscal impulse as 12M change in primary balance/GDP, z-scored.

    Direction: positive z (pb improving over 12M) = fiscal contraction = SHORT USDBRL.
    Negative z (pb deteriorating over 12M) = fiscal expansion = LONG USDBRL.

    Fires when |z| >= Z_FIRE (1.0).
    """

    SIGNAL_ID = "FISCAL_BR_IMPULSE"
    Z_FIRE = 1.0      # |z| threshold to fire signal
    ROLL_WINDOW = 36  # months for z-score mean/std
    MIN_OBS = 24      # minimum pb_history length

    def run(self, features: dict, as_of_date: date) -> AgentSignal:
        """Generate fiscal impulse signal from pb history.

        Args:
            features: Feature dict from FiscalFeatureEngine.compute().
            as_of_date: Point-in-time reference date.

        Returns:
            AgentSignal with FISCAL_BR_IMPULSE signal_id.
        """

        def _no_signal(reason: str = "") -> AgentSignal:
            logger.debug("fiscal_impulse_no_signal: %s", reason)
            return AgentSignal(
                signal_id=self.SIGNAL_ID,
                agent_id="fiscal_agent",
                timestamp=datetime.utcnow(),
                as_of_date=as_of_date,
                direction=SignalDirection.NEUTRAL,
                strength=SignalStrength.NO_SIGNAL,
                confidence=0.0,
                value=0.0,
                horizon_days=126,
                metadata={"reason": reason},
            )

        pb_history = features.get("_pb_history")
        if pb_history is None or not isinstance(pb_history, pd.Series) or len(pb_history) < self.MIN_OBS:
            return _no_signal("insufficient_data")

        # Compute 12M diff
        pb_12m_change = pb_history.diff(12).dropna()
        if pb_12m_change.empty:
            return _no_signal("insufficient_diff_data")

        # Z-score over rolling window
        rolling_mean = pb_12m_change.rolling(self.ROLL_WINDOW).mean()
        rolling_std = pb_12m_change.rolling(self.ROLL_WINDOW).std()

        latest_mean = rolling_mean.iloc[-1]
        latest_std = rolling_std.iloc[-1]

        if np.isnan(latest_std) or latest_std < 1e-8:
            return _no_signal("zero_variance")

        z = (pb_12m_change.iloc[-1] - latest_mean) / latest_std

        if z > self.Z_FIRE:
            direction = SignalDirection.SHORT  # pb improving = fiscal contraction = BRL positive
        elif z < -self.Z_FIRE:
            direction = SignalDirection.LONG   # pb deteriorating = fiscal expansion = BRL bearish
        else:
            direction = SignalDirection.NEUTRAL

        if direction == SignalDirection.NEUTRAL:
            confidence = 0.0
        else:
            confidence = min(1.0, abs(z) / 2.0)

        strength = classify_strength(confidence)

        return AgentSignal(
            signal_id=self.SIGNAL_ID,
            agent_id="fiscal_agent",
            timestamp=datetime.utcnow(),
            as_of_date=as_of_date,
            direction=direction,
            strength=strength,
            confidence=confidence,
            value=round(float(z), 4),
            horizon_days=126,
            metadata={
                "pb_12m_change": float(pb_12m_change.iloc[-1]),
                "z_score": float(z),
                "roll_window": self.ROLL_WINDOW,
            },
        )


# ---------------------------------------------------------------------------
# FiscalDominanceRisk
# ---------------------------------------------------------------------------
class FiscalDominanceRisk:
    """Composite fiscal dominance risk score (0-100) from 4 components.

    Components and weights (locked):
      debt_level    0.35  — gross debt/GDP absolute level
      r_g_spread    0.30  — r-g: positive and high = destabilizing
      pb_trend      0.20  — 12M trend in primary balance (deteriorating = bad)
      cb_credibility 0.15 — |Focus 12M - 3.0%| deviation from target

    Sub-score normalization anchors:
      debt_level:    60% GDP -> 50pts; 90% GDP -> 100pts; 30% GDP -> 0pts
      r_g_spread:    r-g=0 -> 50pts; r-g=+5 -> 100pts; r-g=-5 -> 0pts
      pb_trend:      12M pb change of +1pp GDP -> 0pts; -1pp -> 100pts
      cb_credibility: |focus-3.0|=0 -> 0pts; |deviation|=3pp -> 100pts

    Thresholds (locked):
      0-33  → LOW risk   → SHORT USDBRL (BRL-positive fiscal conditions)
      33-66 → MODERATE   → NEUTRAL
      66-100 → HIGH risk  → LONG USDBRL (fiscal stress = BRL weakness)
    """

    SIGNAL_ID = "FISCAL_BR_DOMINANCE_RISK"

    WEIGHTS: dict[str, float] = {
        "debt_level":     0.35,
        "r_g_spread":     0.30,
        "pb_trend":       0.20,
        "cb_credibility": 0.15,
    }

    THRESHOLD_LOW = 33.0
    THRESHOLD_HIGH = 66.0

    def run(self, features: dict, as_of_date: date) -> AgentSignal:
        """Generate fiscal dominance risk signal.

        Args:
            features: Feature dict from FiscalFeatureEngine.compute().
            as_of_date: Point-in-time reference date.

        Returns:
            AgentSignal with FISCAL_BR_DOMINANCE_RISK signal_id.
        """

        def _no_signal(reason: str = "") -> AgentSignal:
            logger.debug("dominance_risk_no_signal: %s", reason)
            return AgentSignal(
                signal_id=self.SIGNAL_ID,
                agent_id="fiscal_agent",
                timestamp=datetime.utcnow(),
                as_of_date=as_of_date,
                direction=SignalDirection.NEUTRAL,
                strength=SignalStrength.NO_SIGNAL,
                confidence=0.0,
                value=0.0,
                horizon_days=252,
                metadata={"reason": reason},
            )

        def _clamp(val: float, lo: float, hi: float) -> float:
            return max(lo, min(hi, val))

        # Compute subscores
        gross_debt_gdp = features.get("gross_debt_gdp", np.nan)
        r_g_spread = features.get("r_g_spread", np.nan)
        pb_12m_change = features.get("pb_12m_change", np.nan)
        focus_abs_dev = features.get("focus_ipca_12m_abs_dev", np.nan)

        try:
            debt_score = (
                _clamp((gross_debt_gdp - 30) / (90 - 30) * 100, 0, 100)
                if not np.isnan(gross_debt_gdp)
                else np.nan
            )
        except Exception:
            debt_score = np.nan

        try:
            rg_score = _clamp((r_g_spread + 5) / 10 * 100, 0, 100) if not np.isnan(r_g_spread) else np.nan
        except Exception:
            rg_score = np.nan

        try:
            pb_score = _clamp((-pb_12m_change + 1) / 2 * 100, 0, 100) if not np.isnan(pb_12m_change) else np.nan
        except Exception:
            pb_score = np.nan

        try:
            cred_score = _clamp(focus_abs_dev / 3.0 * 100, 0, 100) if not np.isnan(focus_abs_dev) else np.nan
        except Exception:
            cred_score = np.nan

        subscores = {
            "debt_level":     debt_score,
            "r_g_spread":     rg_score,
            "pb_trend":       pb_score,
            "cb_credibility": cred_score,
        }

        nan_count = sum(1 for v in subscores.values() if isinstance(v, float) and np.isnan(v))
        if nan_count >= 3:
            return _no_signal("insufficient_features")

        # Substitute 50 for NaN subscores
        filled_scores = {
            k: (50.0 if isinstance(v, float) and np.isnan(v) else float(v))
            for k, v in subscores.items()
        }

        # Weighted composite (renormalize by available weights)
        total_weight = sum(
            w
            for k, w in self.WEIGHTS.items()
            if not (isinstance(subscores[k], float) and np.isnan(subscores[k]))
        )
        if total_weight < 1e-8:
            return _no_signal("zero_total_weight")

        composite = sum(
            filled_scores[k] * w
            for k, w in self.WEIGHTS.items()
        )
        # Since we substituted 50 for NaN rather than excluding, use full weight sum = 1.0
        # No renormalization needed when filling with neutral value

        # Map to direction
        if composite < self.THRESHOLD_LOW:
            direction = SignalDirection.SHORT
        elif composite > self.THRESHOLD_HIGH:
            direction = SignalDirection.LONG
        else:
            direction = SignalDirection.NEUTRAL

        # Confidence: distance from midpoint (50)
        raw_conf = abs(composite - 50) / 50
        if direction == SignalDirection.NEUTRAL:
            confidence = 0.2  # low but not zero
        else:
            confidence = raw_conf

        strength = classify_strength(confidence)

        return AgentSignal(
            signal_id=self.SIGNAL_ID,
            agent_id="fiscal_agent",
            timestamp=datetime.utcnow(),
            as_of_date=as_of_date,
            direction=direction,
            strength=strength,
            confidence=confidence,
            value=round(composite, 2),
            horizon_days=252,
            metadata={
                "composite_score": round(composite, 2),
                "subscores": {
                    "debt_level": round(debt_score, 2) if not np.isnan(debt_score) else None,
                    "r_g_spread": round(rg_score, 2) if not np.isnan(rg_score) else None,
                    "pb_trend": round(pb_score, 2) if not np.isnan(pb_score) else None,
                    "cb_credibility": round(cred_score, 2) if not np.isnan(cred_score) else None,
                },
                "thresholds": {"low": self.THRESHOLD_LOW, "high": self.THRESHOLD_HIGH},
            },
        )


# ---------------------------------------------------------------------------
# FiscalAgent
# ---------------------------------------------------------------------------
class FiscalAgent(BaseAgent):
    """Fiscal agent producing 4 signals from BR debt sustainability analysis.

    Signals produced:
    1. FISCAL_BR_DSA           — IMF-style 4-scenario debt sustainability
    2. FISCAL_BR_IMPULSE       — Fiscal impulse (12M pb change z-score)
    3. FISCAL_BR_DOMINANCE_RISK — Composite fiscal dominance risk (0-100)
    4. FISCAL_BR_COMPOSITE     — Equal-weight aggregate of 3 BR signals
    """

    AGENT_ID = "fiscal_agent"
    AGENT_NAME = "Fiscal Agent"

    def __init__(self, loader: PointInTimeDataLoader) -> None:
        super().__init__(self.AGENT_ID, self.AGENT_NAME)
        self.loader = loader
        self.feature_engine = FiscalFeatureEngine()
        self.dsa_model = DebtSustainabilityModel()
        self.impulse_model = FiscalImpulseModel()
        self.dominance_model = FiscalDominanceRisk()

    # ------------------------------------------------------------------
    # BaseAgent abstract method implementations
    # ------------------------------------------------------------------
    def load_data(self, as_of_date: date) -> dict[str, Any]:
        """Load all fiscal series using PointInTimeDataLoader.

        All data loads are individually guarded — a failure for one series
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

        # 15Y lookback for DSA history (5475 days)
        _safe_load(
            "gross_debt",
            self.loader.get_macro_series,
            "BR_GROSS_DEBT_GDP",
            as_of_date,
            lookback_days=5475,
        )
        _safe_load(
            "net_debt",
            self.loader.get_macro_series,
            "BR_NET_DEBT_GDP",
            as_of_date,
            lookback_days=5475,
        )
        _safe_load(
            "primary_balance",
            self.loader.get_macro_series,
            "BR_PRIMARY_BALANCE",
            as_of_date,
            lookback_days=5475,
        )
        _safe_load(
            "gdp_qoq",
            self.loader.get_macro_series,
            "BR_GDP_QOQ",
            as_of_date,
            lookback_days=5475,
        )
        _safe_load(
            "selic",
            self.loader.get_macro_series,
            "BCB-432",
            as_of_date,
            lookback_days=5475,
        )
        # Focus PIB: current year and next year
        cy = as_of_date.year
        ny = cy + 1

        # Focus IPCA — year-specific code
        _safe_load(
            "focus",
            self.loader.get_macro_series,
            f"BR_FOCUS_IPCA_{cy}_MEDIAN",
            as_of_date,
            lookback_days=5475,
        )
        _safe_load(
            "focus_pib_cy",
            self.loader.get_macro_series,
            f"BR_FOCUS_PIB_{cy}_MEDIAN",
            as_of_date,
            lookback_days=5475,
        )
        _safe_load(
            "focus_pib_ny",
            self.loader.get_macro_series,
            f"BR_FOCUS_PIB_{ny}_MEDIAN",
            as_of_date,
            lookback_days=5475,
        )

        # DI curve (raw dict)
        try:
            data["di_curve"] = self.loader.get_curve("DI", as_of_date)
        except Exception as exc:
            self.log.warning("di_curve_load_failed", error=str(exc))
            data["di_curve"] = {}

        # Store as_of_date for compute_features
        data["_as_of_date"] = as_of_date

        return data

    def compute_features(self, data: dict) -> dict[str, Any]:
        """Compute fiscal features from raw data.

        Args:
            data: Output of ``load_data()``.

        Returns:
            Feature dictionary with scalar values and private time series keys.
        """
        as_of_date = data.get("_as_of_date")
        if as_of_date is None:
            as_of_date = date.today()

        features = self.feature_engine.compute(data, as_of_date)
        features["_as_of_date"] = as_of_date
        return features

    def run_models(self, features: dict) -> list[AgentSignal]:
        """Execute all 3 fiscal models and build composite.

        Order: DSA → Impulse → DominanceRisk → Composite.

        Args:
            features: Output of ``compute_features()``.

        Returns:
            List of exactly 4 AgentSignal objects.
        """
        as_of_date = features["_as_of_date"]
        signals = []

        dsa_sig = self.dsa_model.run(features, as_of_date)
        signals.append(dsa_sig)

        impulse_sig = self.impulse_model.run(features, as_of_date)
        signals.append(impulse_sig)

        dominance_sig = self.dominance_model.run(features, as_of_date)
        signals.append(dominance_sig)

        # Composite (all 3 BR signals, equal-weight with conflict dampening)
        signals.append(self._build_composite(signals, as_of_date))

        return signals

    def generate_narrative(self, signals: list[AgentSignal], features: dict) -> str:
        """Generate a human-readable fiscal analysis summary.

        Args:
            signals: List of 4 AgentSignal objects from run_models().
            features: Feature dict from compute_features().

        Returns:
            Formatted analysis text summarizing all signals.
        """
        as_of_date = features.get("_as_of_date", "unknown")

        # Extract metadata for each signal
        dsa_sig = signals[0] if len(signals) > 0 else None
        impulse_sig = signals[1] if len(signals) > 1 else None
        dominance_sig = signals[2] if len(signals) > 2 else None
        composite_sig = signals[3] if len(signals) > 3 else None

        parts = [f"Fiscal Assessment ({as_of_date}):"]

        if dsa_sig:
            baseline_delta = dsa_sig.metadata.get("baseline_terminal", "N/A")
            d0 = dsa_sig.metadata.get("d0", "N/A")
            if isinstance(baseline_delta, (int, float)) and isinstance(d0, (int, float)):
                delta = baseline_delta - d0
                parts.append(
                    f"DSA: {dsa_sig.direction.value} (5Y debt path {delta:+.1f}pp from {d0:.1f}% GDP)."
                )
            else:
                parts.append(f"DSA: {dsa_sig.direction.value}.")

        if impulse_sig:
            z = impulse_sig.metadata.get("z_score", impulse_sig.value)
            parts.append(f"Impulse: {impulse_sig.direction.value} (z={z:.2f}).")

        if dominance_sig:
            score = dominance_sig.metadata.get("composite_score", dominance_sig.value)
            parts.append(f"Dominance Risk: {dominance_sig.direction.value} (score={score:.0f}/100).")

        if composite_sig:
            parts.append(f"Composite: {composite_sig.direction.value}.")

        return " ".join(parts)

    # ------------------------------------------------------------------
    # Composite signal builder
    # ------------------------------------------------------------------
    def _build_composite(
        self, sub_signals: list[AgentSignal], as_of_date: date
    ) -> AgentSignal:
        """Build FISCAL_BR_COMPOSITE from the 3 fiscal sub-signals.

        Equal weights (1/3 each) since all 3 signals are independent fiscal
        indicators. Conflict dampening: 0.70 when any active signal disagrees
        with plurality direction.

        Args:
            sub_signals: List of [dsa_sig, impulse_sig, dominance_sig].
            as_of_date: Point-in-time reference date.

        Returns:
            AgentSignal with FISCAL_BR_COMPOSITE signal_id.
        """
        # Equal base weights
        base_weight = 1.0 / 3.0
        base_weights = [base_weight] * len(sub_signals)

        # Filter to active signals (non-NO_SIGNAL and non-NEUTRAL direction)
        active = [
            (sig, w)
            for sig, w in zip(sub_signals, base_weights)
            if sig.strength != SignalStrength.NO_SIGNAL
            and sig.direction != SignalDirection.NEUTRAL
        ]

        if not active:
            return AgentSignal(
                signal_id="FISCAL_BR_COMPOSITE",
                agent_id="fiscal_agent",
                timestamp=datetime.utcnow(),
                as_of_date=as_of_date,
                direction=SignalDirection.NEUTRAL,
                strength=SignalStrength.NO_SIGNAL,
                confidence=0.0,
                value=0.0,
                horizon_days=252,
                metadata={"reason": "no_active_sub_signals"},
            )

        # Renormalize weights to active signals
        total_w = sum(w for _, w in active)
        norm_weights = [w / total_w for _, w in active]
        active_sigs = [sig for sig, _ in active]

        # Plurality vote for direction
        long_w = sum(w for sig, w in zip(active_sigs, norm_weights) if sig.direction == SignalDirection.LONG)
        short_w = sum(w for sig, w in zip(active_sigs, norm_weights) if sig.direction == SignalDirection.SHORT)
        plurality_direction = SignalDirection.LONG if long_w >= short_w else SignalDirection.SHORT

        # Conflict detection: dampening if any active signal disagrees
        disagreements = sum(
            1 for sig in active_sigs if sig.direction != plurality_direction
        )
        dampening = 0.70 if disagreements >= 1 else 1.0

        # Weighted confidence with dampening
        weighted_conf = sum(sig.confidence * w for sig, w in zip(active_sigs, norm_weights))
        composite_confidence = weighted_conf * dampening
        composite_strength = classify_strength(composite_confidence)

        # Weighted value
        composite_value = sum(sig.value * w for sig, w in zip(active_sigs, norm_weights))

        return AgentSignal(
            signal_id="FISCAL_BR_COMPOSITE",
            agent_id="fiscal_agent",
            timestamp=datetime.utcnow(),
            as_of_date=as_of_date,
            direction=plurality_direction,
            strength=composite_strength,
            confidence=round(composite_confidence, 4),
            value=round(composite_value, 4),
            horizon_days=252,
            metadata={
                "weights": "equal_1/3",
                "dampening": dampening,
                "n_active": len(active),
                "long_weight": round(long_w, 4),
                "short_weight": round(short_w, 4),
            },
        )

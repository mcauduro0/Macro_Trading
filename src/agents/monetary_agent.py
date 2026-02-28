"""Monetary Policy Agent — BR and US central bank analysis.

Implements MonetaryPolicyAgent with five quantitative models:

1. **TaylorRuleModel** — BCB-modified Taylor Rule measuring policy gap.
2. **KalmanFilterRStar** — State-space estimation of time-varying natural rate r*.
3. **SelicPathModel** — Market-implied Selic path vs Taylor model path.
4. **TermPremiumModel** — DI term premium z-score signal.
5. **UsFedAnalysis** — US Fed Taylor gap and financial conditions.

MonetaryPolicyAgent aggregates into MONETARY_BR_COMPOSITE (BR signals only).
MONETARY_US_FED_STANCE remains a standalone signal — not fed into BR composite.

Architecture decisions:
- Composite weights: Taylor 50%, SelicPath 30%, TermPremium 20%.
- US Fed excluded from BR composite (separate market, avoid double-counting).
- Conflict dampening: 0.70 applied when >= 1 BR sub-signal disagrees with plurality.
- TaylorRuleModel.GAP_FLOOR = 1.0 (100bps — locked per CONTEXT.md).
- MODERATE_BAND = 1.5 (150bps): gap in [1.0, 1.5) → MODERATE, >= 1.5 → STRONG.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

from src.agents.base import AgentSignal, BaseAgent, classify_strength
from src.agents.data_loader import PointInTimeDataLoader
from src.agents.features.monetary_features import MonetaryFeatureEngine
from src.core.enums import SignalDirection, SignalStrength

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TaylorRuleModel
# ---------------------------------------------------------------------------
class TaylorRuleModel:
    """BCB-modified Taylor Rule: i* = r* + π_e + α(π_e - π*) + β(y_gap) + γ(inertia).

    Signals when |policy_gap| >= GAP_FLOOR (100bps, locked).
    Positive gap (Selic above Taylor) → SHORT (rate-cut bias).
    Negative gap (Selic below Taylor) → LONG (hike risk).

    Strength bands:
    - |gap| in [GAP_FLOOR, MODERATE_BAND) → MODERATE (confidence=0.60)
    - |gap| >= MODERATE_BAND             → STRONG (confidence=0.85)
    """

    SIGNAL_ID = "MONETARY_BR_TAYLOR"
    ALPHA = 1.5  # Inflation gap coefficient (BCB empirical estimate)
    BETA = 0.5  # Output gap coefficient
    GAMMA = 0.5  # Inertia coefficient
    PI_STAR = 3.0  # BCB inflation target (%)
    GAP_FLOOR = 1.0  # 100bps floor — locked per CONTEXT.md
    MODERATE_BAND = 1.5  # 150bps — above this → STRONG

    @staticmethod
    def _classify_gap_source(composite_gap: Any, ibc_gap: Any) -> str:
        """Return a label for which gap measure was used."""
        _is_valid_composite = composite_gap is not None and not (
            isinstance(composite_gap, float) and np.isnan(composite_gap)
        )
        _is_valid_ibc = ibc_gap is not None and not (
            isinstance(ibc_gap, float) and np.isnan(ibc_gap)
        )
        if _is_valid_composite:
            return "composite"
        if _is_valid_ibc:
            return "ibc_br"
        return "neutral"

    def run(self, features: dict, r_star: float, as_of_date: date) -> AgentSignal:
        """Compute Taylor Rule implied rate and generate policy gap signal.

        Args:
            features: Feature dict from MonetaryFeatureEngine.compute().
            r_star: Natural rate estimate from KalmanFilterRStar (%).
            as_of_date: Point-in-time reference date.

        Returns:
            AgentSignal with MONETARY_BR_TAYLOR signal_id.
        """

        def _no_signal(reason: str = "") -> AgentSignal:
            logger.debug("taylor_no_signal: %s", reason)
            return AgentSignal(
                signal_id=self.SIGNAL_ID,
                agent_id="monetary_agent",
                timestamp=datetime.utcnow(),
                as_of_date=as_of_date,
                direction=SignalDirection.NEUTRAL,
                strength=SignalStrength.NO_SIGNAL,
                confidence=0.0,
                value=0.0,
                horizon_days=252,
                metadata={"reason": reason},
            )

        # Validate hard-required features (output gap has neutral fallback)
        hard_required = ("focus_ipca_12m", "selic_target")
        for key in hard_required:
            val = features.get(key)
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return _no_signal(f"missing_feature:{key}")
        if np.isnan(r_star):
            return _no_signal("r_star_nan")

        focus_ipca = features["focus_ipca_12m"]
        selic = features["selic_target"]

        # Output gap: prefer composite_activity_gap (blends IBC-Br + unemployment + NUCI)
        # Fall back to IBC-Br output_gap alone, then 0.0 (neutral)
        composite_gap = features.get("composite_activity_gap")
        ibc_gap = features.get("ibc_br_output_gap")
        if composite_gap is not None and not (
            isinstance(composite_gap, float) and np.isnan(composite_gap)
        ):
            output_gap = composite_gap
        elif ibc_gap is not None and not (
            isinstance(ibc_gap, float) and np.isnan(ibc_gap)
        ):
            output_gap = ibc_gap
        else:
            output_gap = 0.0
            logger.info("taylor_using_neutral_output_gap")

        # Policy inertia: default 0.0 when unavailable
        raw_inertia = features.get("policy_inertia")
        is_valid = raw_inertia is not None and not (
            isinstance(raw_inertia, float) and np.isnan(raw_inertia)
        )
        inertia = raw_inertia if is_valid else 0.0

        # Taylor Rule: i* = r* + π_e + α(π_e − π*) + β(y_gap) + γ(inertia)
        i_star = (
            r_star
            + focus_ipca
            + self.ALPHA * (focus_ipca - self.PI_STAR)
            + self.BETA * output_gap
            + self.GAMMA * inertia
        )

        # Policy gap: positive → Selic above Taylor (restrictive)
        policy_gap = selic - i_star

        if abs(policy_gap) < self.GAP_FLOOR:
            return _no_signal(f"gap_below_floor:{policy_gap:.2f}")

        # Direction
        direction = SignalDirection.SHORT if policy_gap > 0 else SignalDirection.LONG

        # Strength and confidence
        abs_gap = abs(policy_gap)
        if abs_gap >= self.MODERATE_BAND:
            strength = SignalStrength.STRONG
            confidence = 0.85
        else:
            strength = SignalStrength.MODERATE
            confidence = 0.60

        return AgentSignal(
            signal_id=self.SIGNAL_ID,
            agent_id="monetary_agent",
            timestamp=datetime.utcnow(),
            as_of_date=as_of_date,
            direction=direction,
            strength=strength,
            confidence=confidence,
            value=round(policy_gap, 4),
            horizon_days=252,
            metadata={
                "i_star": round(i_star, 4),
                "selic": selic,
                "r_star": r_star,
                "output_gap": round(output_gap, 4),
                "gap_source": self._classify_gap_source(
                    composite_gap,
                    ibc_gap,
                ),
                "policy_gap_bps": round(policy_gap * 100, 1),
            },
        )


# ---------------------------------------------------------------------------
# KalmanFilterRStar
# ---------------------------------------------------------------------------
class KalmanFilterRStar:
    """Laubach-Williams inspired estimation of time-varying natural rate r*.

    Two-state Kalman filter:
    - State 1: r* (natural real interest rate, slow-moving)
    - State 2: g* (trend real GDP growth, slow-moving)

    Observation equation (IS curve inspired):
    - y_t = r*_t + g*_t/2 + v_t

    where y_t = selic_t - expectations_t (ex-ante real rate proxy).

    The g* component is informed by the IBC-Br output gap series: when a
    persistent negative gap exists, g* should be lower (and r* falls).

    Falls back to simple random-walk if gap_series is unavailable.

    Implemented directly with numpy — no external Kalman library required.
    """

    MIN_OBS = 24  # Minimum observations before running filter
    DEFAULT_R_STAR = 3.0  # % — returned when insufficient data

    def estimate(
        self,
        selic_series: pd.Series,
        expectations_series: pd.Series,
        gap_series: pd.Series,
    ) -> tuple[float, float]:
        """Estimate the natural rate r* via Laubach-Williams Kalman filter.

        Args:
            selic_series: Monthly Selic target series (%).
            expectations_series: Monthly Focus IPCA 12M median series (%).
            gap_series: Monthly IBC-Br output gap series (%). Used to inform
                the trend growth component g*.

        Returns:
            Tuple of ``(r_star_estimate, uncertainty)`` where uncertainty is
            the final filter variance ``P[0,0]``. If insufficient data, returns
            ``(DEFAULT_R_STAR, inf)``.
        """
        # Build observation series (ex-ante real rate)
        try:
            obs_series = (selic_series - expectations_series).dropna()
        except Exception as exc:
            logger.warning("kalman_obs_series_failed: %s", exc)
            return self.DEFAULT_R_STAR, float("inf")

        n_obs = len(obs_series)
        if n_obs < self.MIN_OBS:
            logger.warning(
                "kalman_insufficient_data: got %d observations, need %d",
                n_obs,
                self.MIN_OBS,
            )
            return self.DEFAULT_R_STAR, float("inf")

        # Check if we have gap data for the enhanced 2-state model
        has_gap = isinstance(gap_series, pd.Series) and len(gap_series) >= self.MIN_OBS

        if has_gap:
            return self._estimate_lw(obs_series, gap_series)
        else:
            return self._estimate_simple(obs_series)

    def _estimate_simple(self, obs_series: pd.Series) -> tuple[float, float]:
        """Simple random-walk Kalman (fallback when gap data unavailable)."""
        Q = 0.01  # State noise (r* changes slowly)
        R = 1.0  # Observation noise

        x = 3.0  # Initial r* estimate
        P = 1.0  # Initial uncertainty

        for y in obs_series:
            if np.isnan(y):
                continue
            P_pred = P + Q
            K = P_pred / (P_pred + R)
            x = x + K * (y - x)
            P = (1 - K) * P_pred

        return float(x), float(P)

    def _estimate_lw(
        self,
        obs_series: pd.Series,
        gap_series: pd.Series,
    ) -> tuple[float, float]:
        """Laubach-Williams 2-state Kalman filter.

        State vector: [r*, g*]
        Transition: x_t = F * x_{t-1} + w_t
            r*_t = r*_{t-1} + w1_t     (random walk)
            g*_t = g*_{t-1} + w2_t     (random walk)

        Observation: y_t = H * x_t + v_t
            y_t = r*_t + 0.5 * g*_t + v_t

        When output gap is available, add a second observation:
            gap_t = c * (y_{t-real} - r*_t) + noise
        This constrains r* to be consistent with observed economic slack.
        """
        # Align series by common index
        common_idx = obs_series.index.intersection(gap_series.index)
        if len(common_idx) < self.MIN_OBS:
            # Fall back: use obs_series alone with simple 2-state
            common_idx = obs_series.index
            gap_aligned = None
        else:
            gap_aligned = gap_series.reindex(common_idx)

        obs_aligned = obs_series.reindex(common_idx)

        # State: [r*, g*]
        n_states = 2
        F = np.eye(n_states)  # Random walk transition

        # Observation matrix: y = [1, 0.5] * [r*, g*]
        H = np.array([[1.0, 0.5]])

        # Noise covariances
        Q = np.diag([0.01, 0.005])  # r* varies more than g*
        R = np.array([[1.0]])  # Observation noise

        # Initial state
        x = np.array([3.0, 2.0])  # r*=3%, g*=2% (historical BR priors)
        P = np.eye(n_states) * 2.0  # Moderate initial uncertainty

        for i, idx in enumerate(common_idx):
            y = obs_aligned.get(idx, np.nan)
            if np.isnan(y):
                continue

            # Predict
            x_pred = F @ x
            P_pred = F @ P @ F.T + Q

            # Update with real rate observation
            innovation = y - H @ x_pred
            S = H @ P_pred @ H.T + R
            K = P_pred @ H.T @ np.linalg.inv(S)
            x = x_pred + (K @ innovation).flatten()
            P = (np.eye(n_states) - K @ H) @ P_pred

            # If gap data available, use it as soft constraint on r*:
            # Large negative gap → r* should be lower (economy below potential)
            if gap_aligned is not None:
                gap_val = gap_aligned.get(idx, np.nan)
                if not np.isnan(gap_val):
                    # Soft observation: gap ~ -0.3 * (real_rate - r*)
                    # This nudges r* toward consistency with output gap
                    H_gap = np.array([[-0.3, 0.0]])
                    R_gap = np.array([[4.0]])  # High noise (soft constraint)
                    innov_gap = gap_val - H_gap @ x
                    S_gap = H_gap @ P @ H_gap.T + R_gap
                    K_gap = P @ H_gap.T @ np.linalg.inv(S_gap)
                    x = x + (K_gap @ innov_gap).flatten()
                    P = (np.eye(n_states) - K_gap @ H_gap) @ P

        r_star = float(x[0])
        g_star = float(x[1])
        uncertainty = float(P[0, 0])

        logger.debug(
            "lw_rstar_estimate",
            r_star=round(r_star, 3),
            g_star=round(g_star, 3),
            uncertainty=round(uncertainty, 4),
        )

        return r_star, uncertainty


# ---------------------------------------------------------------------------
# SelicPathModel
# ---------------------------------------------------------------------------
class SelicPathModel:
    """Market-implied Selic path vs Taylor Rule model path signal.

    Market path proxy: di_1y (1Y DI rate, forward-looking market pricing).
    Model path: i_star from TaylorRuleModel.

    Direction convention (standard rates strategy):
    - market > model → SHORT (market is pricing more tightening than fundamentals
      justify — fade the hike pricing, rates should come down)
    - market < model → LONG (market underpricing tightening risk)

    Fires when |market_vs_model| >= 50bps.
    """

    SIGNAL_ID = "MONETARY_BR_SELIC_PATH"
    FIRE_THRESHOLD = 0.5  # 50bps minimum deviation

    def run(self, features: dict, i_star: float, as_of_date: date) -> AgentSignal:
        """Generate Selic path divergence signal.

        Args:
            features: Feature dict from MonetaryFeatureEngine.compute().
            i_star: Taylor-implied rate from TaylorRuleModel (%).
            as_of_date: Point-in-time reference date.

        Returns:
            AgentSignal with MONETARY_BR_SELIC_PATH signal_id.
        """

        def _no_signal(reason: str = "") -> AgentSignal:
            logger.debug("selic_path_no_signal: %s", reason)
            return AgentSignal(
                signal_id=self.SIGNAL_ID,
                agent_id="monetary_agent",
                timestamp=datetime.utcnow(),
                as_of_date=as_of_date,
                direction=SignalDirection.NEUTRAL,
                strength=SignalStrength.NO_SIGNAL,
                confidence=0.0,
                value=0.0,
                horizon_days=126,
                metadata={"reason": reason},
            )

        di_1y = features.get("di_1y")
        if di_1y is None or (isinstance(di_1y, float) and np.isnan(di_1y)):
            return _no_signal("di_1y_nan")
        if np.isnan(i_star):
            return _no_signal("i_star_nan")

        market_vs_model = di_1y - i_star

        if abs(market_vs_model) < self.FIRE_THRESHOLD:
            return _no_signal(f"deviation_below_threshold:{market_vs_model:.2f}")

        # Direction: market above model → SHORT (fade hike pricing)
        direction = (
            SignalDirection.SHORT if market_vs_model > 0 else SignalDirection.LONG
        )

        confidence = min(1.0, abs(market_vs_model) / 2.0)
        strength = classify_strength(confidence)

        return AgentSignal(
            signal_id=self.SIGNAL_ID,
            agent_id="monetary_agent",
            timestamp=datetime.utcnow(),
            as_of_date=as_of_date,
            direction=direction,
            strength=strength,
            confidence=confidence,
            value=round(market_vs_model, 4),
            horizon_days=126,
            metadata={
                "di_1y": di_1y,
                "taylor_implied": round(i_star, 4),
                "deviation_bps": round(market_vs_model * 100, 1),
            },
        )


# ---------------------------------------------------------------------------
# TermPremiumModel
# ---------------------------------------------------------------------------
class TermPremiumModel:
    """DI term premium estimate and z-score signal.

    Term premium proxy: di_10y − (focus_ipca_12m + r*)
    Z-score: (current_tp − trailing_mean) / trailing_std

    Direction:
    - z > Z_HIGH → LONG (TP attractive, rates above fair value, long duration)
    - z < Z_LOW  → SHORT (TP compressed, expensive to own duration)
    """

    SIGNAL_ID = "MONETARY_BR_TERM_PREMIUM"
    Z_HIGH = 1.5  # z > 1.5 → LONG
    Z_LOW = -1.5  # z < -1.5 → SHORT
    MIN_HISTORY = 12  # months minimum for z-score

    def run(self, features: dict, as_of_date: date) -> AgentSignal:
        """Generate term premium z-score signal.

        Args:
            features: Feature dict including ``_r_star_estimate`` (set by
                MonetaryPolicyAgent after Kalman run) and ``_tp_history``.
            as_of_date: Point-in-time reference date.

        Returns:
            AgentSignal with MONETARY_BR_TERM_PREMIUM signal_id.
        """

        def _no_signal(reason: str = "") -> AgentSignal:
            logger.debug("term_premium_no_signal: %s", reason)
            return AgentSignal(
                signal_id=self.SIGNAL_ID,
                agent_id="monetary_agent",
                timestamp=datetime.utcnow(),
                as_of_date=as_of_date,
                direction=SignalDirection.NEUTRAL,
                strength=SignalStrength.NO_SIGNAL,
                confidence=0.0,
                value=0.0,
                horizon_days=252,
                metadata={"reason": reason},
            )

        di_10y = features.get("di_10y")
        focus_ipca = features.get("focus_ipca_12m")
        r_star = features.get("_r_star_estimate")
        tp_history = features.get("_tp_history")

        # Validate inputs
        for val, name in (
            (di_10y, "di_10y"),
            (focus_ipca, "focus_ipca_12m"),
            (r_star, "_r_star_estimate"),
        ):
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return _no_signal(f"missing:{name}")

        if (
            tp_history is None
            or not isinstance(tp_history, pd.Series)
            or len(tp_history) < self.MIN_HISTORY
        ):
            return _no_signal("insufficient_tp_history")

        # Current term premium
        current_tp = di_10y - (focus_ipca + r_star)

        hist_mean = tp_history.mean()
        hist_std = tp_history.std()

        if np.isnan(hist_std) or hist_std < 1e-8:
            return _no_signal("tp_history_zero_std")

        z = (current_tp - hist_mean) / hist_std

        if abs(z) < 0.5:
            return AgentSignal(
                signal_id=self.SIGNAL_ID,
                agent_id="monetary_agent",
                timestamp=datetime.utcnow(),
                as_of_date=as_of_date,
                direction=SignalDirection.NEUTRAL,
                strength=SignalStrength.NO_SIGNAL,
                confidence=0.0,
                value=round(z, 4),
                horizon_days=252,
                metadata={"z_score": round(z, 4), "reason": "z_below_threshold"},
            )

        if z > self.Z_HIGH:
            direction = SignalDirection.LONG
        elif z < self.Z_LOW:
            direction = SignalDirection.SHORT
        else:
            direction = SignalDirection.NEUTRAL

        confidence = min(1.0, abs(z) / 3.0)
        strength = classify_strength(confidence)

        return AgentSignal(
            signal_id=self.SIGNAL_ID,
            agent_id="monetary_agent",
            timestamp=datetime.utcnow(),
            as_of_date=as_of_date,
            direction=direction,
            strength=strength,
            confidence=confidence,
            value=round(z, 4),
            horizon_days=252,
            metadata={
                "current_tp": round(current_tp, 4),
                "z_score": round(z, 4),
                "tp_mean": round(hist_mean, 4),
                "tp_std": round(hist_std, 4),
            },
        )


# ---------------------------------------------------------------------------
# UsFedAnalysis
# ---------------------------------------------------------------------------
class UsFedAnalysis:
    """US Fed policy gap and financial conditions signal.

    US Taylor Rule: i* = 2.5 + 1.5*(PCE_core − 2.0) + 0.5*output_gap_proxy

    US output gap proxy: ust_slope * 0.5 (inverted curve ≈ negative output gap).

    Signal interpretation:
    - gap > 0 (Fed above Taylor = restrictive) → SHORT (tight global = BRL bearish)
    - gap < 0 (Fed below Taylor = accommodative) → LONG (easy global = BRL supportive)

    Fires when |gap| >= GAP_FLOOR (50bps). US conditions signal is standalone.
    """

    SIGNAL_ID = "MONETARY_US_FED_STANCE"
    NEUTRAL_RATE = 2.5
    ALPHA = 1.5
    BETA = 0.5
    GAP_FLOOR = 0.5  # 50bps — tighter for US where markets are more efficient

    def run(self, features: dict, as_of_date: date) -> AgentSignal:
        """Generate US Fed policy gap signal.

        Args:
            features: Feature dict from MonetaryFeatureEngine.compute().
            as_of_date: Point-in-time reference date.

        Returns:
            AgentSignal with MONETARY_US_FED_STANCE signal_id.
        """

        def _no_signal(reason: str = "") -> AgentSignal:
            logger.debug("us_fed_no_signal: %s", reason)
            return AgentSignal(
                signal_id=self.SIGNAL_ID,
                agent_id="monetary_agent",
                timestamp=datetime.utcnow(),
                as_of_date=as_of_date,
                direction=SignalDirection.NEUTRAL,
                strength=SignalStrength.NO_SIGNAL,
                confidence=0.0,
                value=0.0,
                horizon_days=252,
                metadata={"reason": reason},
            )

        pce_core = features.get("us_pce_core_yoy")
        fed_funds = features.get("fed_funds_rate")
        ust_slope = features.get("ust_slope")

        for val, name in ((pce_core, "us_pce_core_yoy"), (fed_funds, "fed_funds_rate")):
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return _no_signal(f"missing:{name}")

        # US output gap proxy from yield curve slope
        us_output_gap_proxy = (
            ust_slope * 0.5
            if (ust_slope is not None and not np.isnan(ust_slope))
            else 0.0
        )

        us_i_star = (
            self.NEUTRAL_RATE
            + self.ALPHA * (pce_core - 2.0)
            + self.BETA * us_output_gap_proxy
        )

        gap = fed_funds - us_i_star

        if abs(gap) < self.GAP_FLOOR:
            return _no_signal(f"gap_below_floor:{gap:.2f}")

        # Direction: hawkish Fed = tight global = bearish BRL context
        direction = SignalDirection.SHORT if gap > 0 else SignalDirection.LONG

        confidence = min(1.0, abs(gap) / 2.0)
        strength = classify_strength(confidence)

        return AgentSignal(
            signal_id=self.SIGNAL_ID,
            agent_id="monetary_agent",
            timestamp=datetime.utcnow(),
            as_of_date=as_of_date,
            direction=direction,
            strength=strength,
            confidence=confidence,
            value=round(gap, 4),
            horizon_days=252,
            metadata={
                "us_i_star": round(us_i_star, 4),
                "fed_funds": fed_funds,
                "policy_gap_bps": round(gap * 100, 1),
                "nfci": features.get("nfci", float("nan")),
            },
        )


# ---------------------------------------------------------------------------
# MonetaryPolicyAgent
# ---------------------------------------------------------------------------
class MonetaryPolicyAgent(BaseAgent):
    """Monetary policy agent producing 5 signals from BR and US central bank analysis.

    Signals produced:
    1. MONETARY_BR_TAYLOR     — BCB policy gap vs Taylor Rule
    2. MONETARY_BR_SELIC_PATH — Market DI path vs model path
    3. MONETARY_BR_TERM_PREMIUM — DI long-end term premium z-score
    4. MONETARY_US_FED_STANCE  — US Fed policy gap (standalone)
    5. MONETARY_BR_COMPOSITE   — Weighted aggregate of BR signals (1-3)
    """

    AGENT_ID = "monetary_agent"
    AGENT_NAME = "Monetary Policy Agent"

    def __init__(self, loader: PointInTimeDataLoader) -> None:
        super().__init__(self.AGENT_ID, self.AGENT_NAME)
        self.loader = loader
        self.feature_engine = MonetaryFeatureEngine()
        self.kalman = KalmanFilterRStar()
        self.taylor = TaylorRuleModel()
        self.selic_path = SelicPathModel()
        self.term_premium = TermPremiumModel()
        self.us_fed = UsFedAnalysis()

    # ------------------------------------------------------------------
    # BaseAgent abstract method implementations
    # ------------------------------------------------------------------
    def load_data(self, as_of_date: date) -> dict[str, Any]:
        """Load all monetary series using PointInTimeDataLoader.

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

        # BR monetary series
        _safe_load(
            "selic",
            self.loader.get_macro_series,
            "BCB-432",
            as_of_date,
            lookback_days=3650,
        )
        # Focus IPCA — year-specific code matching connector output
        cy = as_of_date.year
        _safe_load(
            "focus",
            self.loader.get_macro_series,
            f"BR_FOCUS_IPCA_{cy}_MEDIAN",
            as_of_date,
            lookback_days=3650,
        )
        _safe_load(
            "ibc_br",
            self.loader.get_macro_series,
            "BCB-24363",
            as_of_date,
            lookback_days=5475,
        )

        # DI 10Y history (for term premium z-score)
        try:
            di_10y_hist = self.loader.get_curve_history(
                "DI",
                tenor_days=2520,
                as_of_date=as_of_date,
                lookback_days=756,
            )
            data["di_10y_history"] = di_10y_hist
        except Exception as exc:
            self.log.warning("di_10y_history_load_failed", error=str(exc))
            data["di_10y_history"] = None

        # BR labor market / activity for enhanced gap estimation
        _safe_load(
            "br_unemployment",
            self.loader.get_macro_series,
            "BCB-24369",
            as_of_date,
            lookback_days=3650,
        )
        _safe_load(
            "br_capacity_util",
            self.loader.get_macro_series,
            "BCB-1344",
            as_of_date,
            lookback_days=3650,
        )

        # DI curve (raw dict of tenor_days → rate; convert to DataFrame)
        try:
            di_raw = self.loader.get_curve("DI", as_of_date)
            if di_raw:
                # Map tenor_days to named columns (approx: 252=1Y, 504=2Y, 1260=5Y, 2520=10Y)
                tenor_map = {
                    252: "tenor_1y",
                    504: "tenor_2y",
                    1260: "tenor_5y",
                    2520: "tenor_10y",
                }
                row_data = {}
                for tenor_days, rate in di_raw.items():
                    col = tenor_map.get(tenor_days)
                    if col:
                        row_data[col] = rate
                    else:
                        # Closest mapping — tolerance scales with tenor
                        for t_days, col_name in sorted(tenor_map.items()):
                            tolerance = max(30, int(t_days * 0.15))
                            if abs(tenor_days - t_days) < tolerance:
                                if col_name not in row_data:
                                    row_data[col_name] = rate
                                break

                # Synthetic long-end DI from NTN-B real + Focus IPCA (Fisher eq.)
                # B3 DI swap curve only covers up to 12M; for 2Y/5Y/10Y we use:
                #   nominal_rate ≈ real_rate(NTN-B) + inflation_expectation(Focus)
                if "tenor_10y" not in row_data or "tenor_5y" not in row_data:
                    try:
                        ntnb_raw = self.loader.get_curve("NTN_B_REAL", as_of_date)
                        if ntnb_raw:
                            # Get Focus IPCA 12M for inflation add-on
                            focus_df = data.get("focus")
                            focus_ipca = np.nan
                            if focus_df is not None and not focus_df.empty:
                                if "focus_ipca_12m" in focus_df.columns:
                                    focus_ipca = float(
                                        focus_df["focus_ipca_12m"].dropna().iloc[-1]
                                    )
                                elif "value" in focus_df.columns:
                                    focus_ipca = float(
                                        focus_df["value"].dropna().iloc[-1]
                                    )

                            if not np.isnan(focus_ipca):
                                ipca_decimal = focus_ipca / 100.0
                                ntnb_tenor_map = {1825: "tenor_5y", 2520: "tenor_10y"}
                                for target_days, col_name in ntnb_tenor_map.items():
                                    if col_name not in row_data:
                                        # Find closest NTN-B tenor
                                        closest_tenor = min(
                                            ntnb_raw.keys(),
                                            key=lambda t: abs(t - target_days),
                                        )
                                        if (
                                            abs(closest_tenor - target_days)
                                            < target_days * 0.30
                                        ):
                                            real_rate = ntnb_raw[closest_tenor]
                                            # Fisher: (1+nom) = (1+real)*(1+infl)
                                            nominal = (1 + real_rate) * (
                                                1 + ipca_decimal
                                            ) - 1
                                            row_data[col_name] = nominal
                                            self.log.info(
                                                "synthetic_di_from_ntnb",
                                                tenor=col_name,
                                                real_rate=round(real_rate, 4),
                                                focus_ipca=round(focus_ipca, 2),
                                                nominal=round(nominal, 4),
                                            )
                    except Exception as ntnb_exc:
                        self.log.warning("ntnb_fallback_failed", error=str(ntnb_exc))

                data["di_curve"] = (
                    pd.DataFrame([row_data]) if row_data else pd.DataFrame()
                )
            else:
                data["di_curve"] = pd.DataFrame()
        except Exception as exc:
            self.log.warning("di_curve_load_failed", error=str(exc))
            data["di_curve"] = pd.DataFrame()

        # US series
        _safe_load(
            "fed_funds",
            self.loader.get_macro_series,
            "FRED-DFF",
            as_of_date,
            lookback_days=3650,
        )
        _safe_load(
            "nfci",
            self.loader.get_macro_series,
            "FRED-NFCI",
            as_of_date,
            lookback_days=1825,
        )
        _safe_load(
            "pce_core",
            self.loader.get_macro_series,
            "FRED-PCEPILFE",
            as_of_date,
            lookback_days=1825,
        )
        _safe_load(
            "us_breakeven",
            self.loader.get_macro_series,
            "FRED-T10YIE",
            as_of_date,
            lookback_days=1825,
        )

        # UST curve — primary: Treasury.gov curve data
        try:
            ust_raw = self.loader.get_curve("UST", as_of_date)
            if ust_raw:
                ust_map = {504: "ust_2y", 1260: "ust_5y", 2520: "ust_10y"}
                ust_row = {}
                for tenor_days, rate in ust_raw.items():
                    col = ust_map.get(tenor_days)
                    if col:
                        ust_row[col] = rate
                    else:
                        for t_days, col_name in sorted(ust_map.items()):
                            if abs(tenor_days - t_days) < 30:
                                ust_row[col_name] = rate
                                break
                data["ust_curve"] = (
                    pd.DataFrame([ust_row]) if ust_row else pd.DataFrame()
                )
            else:
                data["ust_curve"] = pd.DataFrame()
        except Exception as exc:
            self.log.warning("ust_curve_load_failed", error=str(exc))
            data["ust_curve"] = pd.DataFrame()

        # UST curve — fallback: FRED DGS series when Treasury.gov is empty
        ust_df = data.get("ust_curve")
        if ust_df is None or ust_df.empty:
            self.log.info("ust_curve_empty_using_fred_fallback")
            fred_map = {
                "ust_2y": "FRED-DGS2",
                "ust_5y": "FRED-DGS5",
                "ust_10y": "FRED-DGS10",
            }
            ust_row = {}
            for col_name, fred_code in fred_map.items():
                try:
                    fred_df = self.loader.get_macro_series(
                        fred_code, as_of_date, lookback_days=30
                    )
                    if (
                        fred_df is not None
                        and not fred_df.empty
                        and "value" in fred_df.columns
                    ):
                        # FRED DGS series are in percentage (e.g. 4.35);
                        # store as-is — feature engine normalizes to pct
                        ust_row[col_name] = float(fred_df["value"].dropna().iloc[-1])
                except Exception:
                    pass
            if ust_row:
                data["ust_curve"] = pd.DataFrame([ust_row])

        return data

    def compute_features(self, data: dict) -> dict[str, Any]:
        """Compute monetary policy features from raw data.

        Args:
            data: Output of ``load_data()``.

        Returns:
            Feature dictionary with scalar values and private time series keys.
        """
        as_of_date = data.get("_as_of_date")
        if as_of_date is None:
            # Reconstruct from context — use today as fallback
            as_of_date = date.today()

        features = self.feature_engine.compute(data, as_of_date)
        features["_as_of_date"] = as_of_date
        return features

    def run_models(self, features: dict) -> list[AgentSignal]:
        """Execute all 5 monetary models in dependency order.

        Order: Kalman (provides r*) → Taylor (uses r*) → SelicPath (uses i*)
               → TermPremium (uses r_star_estimate) → UsFed (standalone)
               → Composite (aggregates BR signals).

        Args:
            features: Output of ``compute_features()``.

        Returns:
            List of exactly 5 AgentSignal objects.
        """
        as_of_date = features["_as_of_date"]

        # Step 1: Run Kalman to get r*
        r_star, r_star_uncertainty = self.kalman.estimate(
            features.get("_selic_history_series", pd.Series(dtype=float)),
            features.get("_focus_history_series", pd.Series(dtype=float)),
            features.get("_ibc_gap_series", pd.Series(dtype=float)),
        )
        features["_r_star_estimate"] = r_star
        features["_r_star_uncertainty"] = r_star_uncertainty

        self.log.debug(
            "kalman_rstar",
            r_star=round(r_star, 3),
            uncertainty=round(r_star_uncertainty, 4),
        )

        signals = []

        # Step 2: Taylor Rule (needs r*)
        taylor_sig = self.taylor.run(features, r_star, as_of_date)
        signals.append(taylor_sig)

        # Step 3: Selic Path (needs Taylor i*)
        # Derive i_star: selic - policy_gap = i_star
        if taylor_sig.strength != SignalStrength.NO_SIGNAL and taylor_sig.value != 0.0:
            selic_target = features.get("selic_target", float("nan"))
            i_star = selic_target - taylor_sig.value  # selic - gap = i_star
        else:
            i_star = features.get("selic_target", float("nan"))

        selic_path_sig = self.selic_path.run(features, i_star, as_of_date)
        signals.append(selic_path_sig)

        # Step 4: Term Premium (needs _r_star_estimate in features)
        term_premium_sig = self.term_premium.run(features, as_of_date)
        signals.append(term_premium_sig)

        # Step 5: US Fed (standalone)
        us_fed_sig = self.us_fed.run(features, as_of_date)
        signals.append(us_fed_sig)

        # Step 6: BR Composite (Taylor + SelicPath + TermPremium only)
        composite_sig = self._build_composite(signals[:3], as_of_date)
        signals.append(composite_sig)

        return signals

    def generate_narrative(self, signals: list[AgentSignal], features: dict) -> str:
        """Generate a human-readable monetary policy analysis summary.

        Args:
            signals: List of 5 AgentSignal objects from run_models().
            features: Feature dict from compute_features().

        Returns:
            Multi-line analysis text summarizing all signals.
        """
        lines = [
            f"=== Monetary Policy Agent Report ({features.get('_as_of_date', 'unknown')}) ===",
            "",
            "--- Brazilian Monetary Policy ---",
        ]

        for sig in signals:
            direction_str = sig.direction.value
            strength_str = sig.strength.value
            lines.append(
                f"  [{sig.signal_id}] {direction_str} | {strength_str} "
                f"| conf={sig.confidence:.2f} | val={sig.value:.4f}"
            )
            if sig.metadata and "reason" not in sig.metadata:
                meta_str = ", ".join(
                    f"{k}={v}" for k, v in list(sig.metadata.items())[:3]
                )
                lines.append(f"    -> {meta_str}")

        # Macro context
        selic = features.get("selic_target", float("nan"))
        focus = features.get("focus_ipca_12m", float("nan"))
        r_star = features.get("_r_star_estimate", float("nan"))
        real_rate = features.get("real_rate_gap", float("nan"))
        fed_funds = features.get("fed_funds_rate", float("nan"))

        lines.extend(
            [
                "",
                "--- Key Indicators ---",
                f"  Selic Target: {selic:.2f}% | Focus IPCA 12M: {focus:.2f}% | "
                f"Real Rate Gap: {real_rate:.2f}%",
                f"  Kalman r*: {r_star:.2f}% | Fed Funds: {fed_funds:.2f}%",
            ]
        )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Composite signal builder
    # ------------------------------------------------------------------
    def _build_composite(
        self, br_signals: list[AgentSignal], as_of_date: date
    ) -> AgentSignal:
        """Build MONETARY_BR_COMPOSITE from the 3 BR sub-signals.

        Weights:
        - TaylorRuleModel:  50% (fundamental model, highest quality)
        - SelicPathModel:   30% (market-derived path)
        - TermPremiumModel: 20% (duration valuation)

        US Fed stance is NOT included — separate market, no double-counting.

        Conflict dampening: If any BR signal disagrees with the plurality
        direction, apply 0.70 dampening to composite confidence.

        Args:
            br_signals: List of [taylor_sig, selic_path_sig, term_premium_sig].
            as_of_date: Point-in-time reference date.

        Returns:
            AgentSignal with MONETARY_BR_COMPOSITE signal_id.
        """
        # Base weights aligned with signal order: [Taylor, SelicPath, TermPremium]
        base_weights = [0.50, 0.30, 0.20]
        signal_ids = [
            "MONETARY_BR_TAYLOR",
            "MONETARY_BR_SELIC_PATH",
            "MONETARY_BR_TERM_PREMIUM",
        ]

        # Filter to active signals
        active = [
            (sig, w, sid)
            for sig, w, sid in zip(br_signals, base_weights, signal_ids)
            if sig.strength != SignalStrength.NO_SIGNAL
            and sig.direction != SignalDirection.NEUTRAL
        ]

        if not active:
            return AgentSignal(
                signal_id="MONETARY_BR_COMPOSITE",
                agent_id="monetary_agent",
                timestamp=datetime.utcnow(),
                as_of_date=as_of_date,
                direction=SignalDirection.NEUTRAL,
                strength=SignalStrength.NO_SIGNAL,
                confidence=0.0,
                value=0.0,
                horizon_days=252,
                metadata={"reason": "no_active_sub_signals"},
            )

        # Renormalize weights
        total_w = sum(w for _, w, _ in active)
        norm_weights = [w / total_w for _, w, _ in active]
        active_sigs = [sig for sig, _, _ in active]

        # Plurality vote for direction
        long_w = sum(
            w
            for sig, w in zip(active_sigs, norm_weights)
            if sig.direction == SignalDirection.LONG
        )
        short_w = sum(
            w
            for sig, w in zip(active_sigs, norm_weights)
            if sig.direction == SignalDirection.SHORT
        )
        plurality_direction = (
            SignalDirection.LONG if long_w >= short_w else SignalDirection.SHORT
        )

        # Conflict detection: if any signal disagrees with plurality → dampen
        disagreements = sum(
            1 for sig in active_sigs if sig.direction != plurality_direction
        )
        dampening = 0.70 if disagreements >= 1 else 1.0

        # Weighted confidence
        weighted_conf = sum(
            sig.confidence * w for sig, w in zip(active_sigs, norm_weights)
        )
        composite_confidence = weighted_conf * dampening
        composite_strength = classify_strength(composite_confidence)

        # Weighted value
        composite_value = sum(
            sig.value * w for sig, w in zip(active_sigs, norm_weights)
        )

        effective_weights = {
            sig.signal_id: round(w, 4) for sig, w in zip(active_sigs, norm_weights)
        }

        return AgentSignal(
            signal_id="MONETARY_BR_COMPOSITE",
            agent_id="monetary_agent",
            timestamp=datetime.utcnow(),
            as_of_date=as_of_date,
            direction=plurality_direction,
            strength=composite_strength,
            confidence=round(composite_confidence, 4),
            value=round(composite_value, 4),
            horizon_days=252,
            metadata={
                "weights": effective_weights,
                "dampening": dampening,
                "long_weight": round(long_w, 4),
                "short_weight": round(short_w, 4),
            },
        )

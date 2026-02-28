"""FX Equilibrium Agent — BEER, carry-to-risk, FX flows, CIP basis.

Implements FxEquilibriumAgent with four quantitative models:

1. **BeerModel** — Behavioral Equilibrium Exchange Rate via OLS.
   log(USDBRL) = α + β1*tot_proxy + β2*real_rate_diff + β3*nfa_proxy
   Fires when misalignment exceeds ±5% (locked in CONTEXT.md).

2. **CarryToRiskModel** — z-score of 12M rolling carry/vol ratio.
   Carry-to-risk z > 1.0 → SHORT; z < -1.0 → LONG.

3. **FlowModel** — Equal-weight BCB FX flow + CFTC 6L positioning z-scores.
   Positive composite (net BRL inflows) → SHORT USDBRL.

4. **CipBasisModel** — CIP deviation: DI 1Y − (USD offshore + expected dep).
   Positive basis (funding friction) → LONG USDBRL (locked in CONTEXT.md).

FxEquilibriumAgent aggregates into FX_BR_COMPOSITE with locked weights:
BEER 40% + Carry 30% + Flow 20% + CIP 10%; 0.70 conflict dampening.

Architecture decisions:
- BeerModel.THRESHOLD = 5.0 (locked symmetric misalignment threshold).
- CarryToRiskModel uses 30D realized PTAX vol denominator (locked).
- CipBasisModel direction: positive basis → LONG USDBRL (locked).
- Composite weights fixed; conflict dampening when any active signal disagrees.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm

from src.agents.base import AgentSignal, BaseAgent, classify_strength
from src.agents.data_loader import PointInTimeDataLoader
from src.agents.features.fx_features import FxFeatureEngine
from src.core.enums import SignalDirection, SignalStrength

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# BeerModel
# ---------------------------------------------------------------------------
class BeerModel:
    """Behavioral Equilibrium Exchange Rate via OLS.

    log(USDBRL) = α + β1*tot_proxy + β2*real_rate_diff + β3*nfa_proxy + ε
    Refit with available predictors. NO_SIGNAL if fewer than 2 predictors survive.
    Misalignment threshold: ±5% (locked in CONTEXT.md).

    Direction convention:
    - Misalignment > +5%  (USDBRL above fair, BRL undervalued) → SHORT USDBRL
    - Misalignment < -5%  (USDBRL below fair, BRL overvalued)  → LONG USDBRL
    """

    SIGNAL_ID = "FX_BR_BEER"
    MIN_OBS = 24       # minimum monthly observations to fit
    THRESHOLD = 5.0    # % misalignment to fire signal (locked)
    PREDICTOR_COLS = ["tot_proxy", "real_rate_diff", "nfa_proxy"]

    def run(self, features: dict, as_of_date: date) -> AgentSignal:  # noqa: C901
        """Compute BEER OLS misalignment signal.

        Args:
            features: Feature dict from FxFeatureEngine.compute().
            as_of_date: Point-in-time reference date.

        Returns:
            AgentSignal with FX_BR_BEER signal_id.
        """

        def _no_signal(reason: str = "") -> AgentSignal:
            logger.debug("beer_model_no_signal: %s", reason)
            return AgentSignal(
                signal_id=self.SIGNAL_ID,
                agent_id="fx_agent",
                timestamp=datetime.utcnow(),
                as_of_date=as_of_date,
                direction=SignalDirection.NEUTRAL,
                strength=SignalStrength.NO_SIGNAL,
                confidence=0.0,
                value=0.0,
                horizon_days=252,
                metadata={"reason": reason},
            )

        df = features.get("_beer_ols_data")
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return _no_signal("no_data")

        # Determine available predictors (>= MIN_OBS non-NaN values)
        available_preds = [
            c
            for c in self.PREDICTOR_COLS
            if c in df.columns and df[c].notna().sum() >= self.MIN_OBS
        ]
        if len(available_preds) < 2:
            return _no_signal("insufficient_predictors")

        # Drop rows where any of the selected cols is NaN
        df_fit = df[["log_usdbrl"] + available_preds].dropna()
        if len(df_fit) < self.MIN_OBS:
            return _no_signal("insufficient_data")

        try:
            X = sm.add_constant(df_fit[available_preds])
            model = sm.OLS(df_fit["log_usdbrl"], X).fit()

            # Reconstruct latest_X using the same add_constant as training
            # so column count always matches model.params (handles edge case
            # where sm.add_constant skips constant when predictors are constant)
            latest_X = sm.add_constant(
                df_fit[available_preds].iloc[[-1]], has_constant="skip"
            )
            # Ensure column count matches model params
            if latest_X.shape[1] != len(model.params):
                latest_X = sm.add_constant(
                    df_fit[available_preds].iloc[[-1]], has_constant="add"
                )
            predicted_log = model.predict(latest_X).iloc[0]
            fair_value = float(np.exp(predicted_log))
            actual_usdbrl = float(np.exp(df_fit["log_usdbrl"].iloc[-1]))

            misalignment_pct = (actual_usdbrl / fair_value - 1) * 100

            if misalignment_pct > self.THRESHOLD:
                direction = SignalDirection.SHORT   # BRL undervalued → mean reversion → sell USD
            elif misalignment_pct < -self.THRESHOLD:
                direction = SignalDirection.LONG    # BRL overvalued → mean reversion → buy USD
            else:
                direction = SignalDirection.NEUTRAL

            confidence = min(1.0, abs(misalignment_pct) / (self.THRESHOLD * 3))
            strength = classify_strength(confidence)

            return AgentSignal(
                signal_id=self.SIGNAL_ID,
                agent_id="fx_agent",
                timestamp=datetime.utcnow(),
                as_of_date=as_of_date,
                direction=direction,
                strength=strength,
                confidence=confidence,
                value=round(misalignment_pct, 4),
                horizon_days=252,
                metadata={
                    "fair_value": round(fair_value, 4),
                    "actual_usdbrl": round(actual_usdbrl, 4),
                    "misalignment_pct": round(misalignment_pct, 4),
                    "n_obs": len(df_fit),
                    "r_squared": round(model.rsquared, 4),
                    "n_predictors": len(available_preds),
                    "predictors_used": available_preds,
                },
            )
        except Exception as exc:
            logger.warning("beer_model_ols_failed: %s", exc)
            return _no_signal(f"ols_error:{exc!s}")


# ---------------------------------------------------------------------------
# CarryToRiskModel
# ---------------------------------------------------------------------------
class CarryToRiskModel:
    """Carry-to-risk model: z-score of 12M rolling carry/vol ratio.

    carry_ratio = (selic - fed_funds) / vol_30d_realized
    Z-score of carry_ratio over 12M history. |z| > 1.0 fires signal.
    Positive z (unusually attractive carry) → SHORT USDBRL.
    Negative z (carry unwind risk) → LONG USDBRL.
    Denominator: 30D realized USDBRL vol from daily PTAX (locked in CONTEXT.md).
    """

    SIGNAL_ID = "FX_BR_CARRY_RISK"
    Z_FIRE = 1.0      # |z| threshold to fire
    ROLL_WINDOW = 12  # months for z-score
    MIN_OBS = 13      # need 12M of history plus current

    def run(self, features: dict, as_of_date: date) -> AgentSignal:
        """Generate carry-to-risk z-score signal.

        Args:
            features: Feature dict from FxFeatureEngine.compute().
            as_of_date: Point-in-time reference date.

        Returns:
            AgentSignal with FX_BR_CARRY_RISK signal_id.
        """

        def _no_signal(reason: str = "") -> AgentSignal:
            logger.debug("carry_to_risk_no_signal: %s", reason)
            return AgentSignal(
                signal_id=self.SIGNAL_ID,
                agent_id="fx_agent",
                timestamp=datetime.utcnow(),
                as_of_date=as_of_date,
                direction=SignalDirection.NEUTRAL,
                strength=SignalStrength.NO_SIGNAL,
                confidence=0.0,
                value=0.0,
                horizon_days=63,
                metadata={"reason": reason},
            )

        carry_history = features.get("_carry_ratio_history")
        if (
            carry_history is None
            or not isinstance(carry_history, pd.Series)
            or len(carry_history) < self.MIN_OBS
        ):
            return _no_signal("insufficient_data")

        current = carry_history.iloc[-1]
        if np.isnan(current):
            return _no_signal("nan_carry_ratio")

        roll_mean = carry_history.rolling(self.ROLL_WINDOW).mean().iloc[-1]
        roll_std = carry_history.rolling(self.ROLL_WINDOW).std().iloc[-1]

        if np.isnan(roll_std) or roll_std == 0:
            return _no_signal("zero_variance")

        z = (current - roll_mean) / roll_std

        if z > self.Z_FIRE:
            direction = SignalDirection.SHORT   # attractive carry = BRL inflows expected
        elif z < -self.Z_FIRE:
            direction = SignalDirection.LONG    # carry unwind risk = BRL outflows
        else:
            direction = SignalDirection.NEUTRAL

        confidence = min(1.0, abs(z) / 2.0)
        strength = classify_strength(confidence)

        return AgentSignal(
            signal_id=self.SIGNAL_ID,
            agent_id="fx_agent",
            timestamp=datetime.utcnow(),
            as_of_date=as_of_date,
            direction=direction,
            strength=strength,
            confidence=confidence,
            value=round(float(z), 4),
            horizon_days=63,
            metadata={
                "carry_ratio": round(float(current), 4),
                "z_score": round(float(z), 4),
                "roll_mean": round(float(roll_mean), 4),
                "carry_raw_pct": features.get("carry_raw", float("nan")),
                "vol_30d": features.get("vol_30d_realized", float("nan")),
            },
        )


# ---------------------------------------------------------------------------
# FlowModel
# ---------------------------------------------------------------------------
class FlowModel:
    """FX flow composite from BCB FX flows and CFTC BRL positioning.

    Equal-weight z-scores: BCB commercial + financial flow net (BCB FX flow)
    and CFTC 6L (BRL/USD futures) non-commercial leveraged net position.
    Positive composite (net inflows + long BRL positioning) → SHORT USDBRL.
    Negative composite → LONG USDBRL.
    """

    SIGNAL_ID = "FX_BR_FLOW"
    Z_FIRE = 0.5     # composite z-score threshold to fire
    MIN_OBS = 4      # minimum non-null observations per component

    def run(self, features: dict, as_of_date: date) -> AgentSignal:
        """Generate FX flow composite signal.

        Args:
            features: Feature dict from FxFeatureEngine.compute().
            as_of_date: Point-in-time reference date.

        Returns:
            AgentSignal with FX_BR_FLOW signal_id.
        """

        def _no_signal(reason: str = "") -> AgentSignal:
            logger.debug("flow_model_no_signal: %s", reason)
            return AgentSignal(
                signal_id=self.SIGNAL_ID,
                agent_id="fx_agent",
                timestamp=datetime.utcnow(),
                as_of_date=as_of_date,
                direction=SignalDirection.NEUTRAL,
                strength=SignalStrength.NO_SIGNAL,
                confidence=0.0,
                value=0.0,
                horizon_days=21,
                metadata={"reason": reason},
            )

        flow_df = features.get("_flow_combined")
        if flow_df is None or not isinstance(flow_df, pd.DataFrame) or flow_df.empty:
            return _no_signal("no_flow_data")

        if "bcb_flow_zscore" not in flow_df.columns or "cftc_zscore" not in flow_df.columns:
            return _no_signal("missing_columns")

        bcb_z = flow_df["bcb_flow_zscore"].iloc[-1]
        cftc_z = flow_df["cftc_zscore"].iloc[-1]

        # Handle NaN components
        bcb_nan = np.isnan(bcb_z)
        cftc_nan = np.isnan(cftc_z)

        if bcb_nan and cftc_nan:
            return _no_signal("all_nan")

        if bcb_nan:
            composite_z = float(cftc_z)
        elif cftc_nan:
            composite_z = float(bcb_z)
        else:
            composite_z = (float(bcb_z) + float(cftc_z)) / 2.0

        if composite_z > self.Z_FIRE:
            direction = SignalDirection.SHORT    # net BRL inflows = BRL demand = sell USD
        elif composite_z < -self.Z_FIRE:
            direction = SignalDirection.LONG     # net BRL outflows = buy USD
        else:
            direction = SignalDirection.NEUTRAL

        confidence = min(1.0, abs(composite_z) / 2.0)
        strength = classify_strength(confidence)

        return AgentSignal(
            signal_id=self.SIGNAL_ID,
            agent_id="fx_agent",
            timestamp=datetime.utcnow(),
            as_of_date=as_of_date,
            direction=direction,
            strength=strength,
            confidence=confidence,
            value=round(float(composite_z), 4),
            horizon_days=21,
            metadata={
                "composite_z": round(float(composite_z), 4),
                "bcb_flow_z": float(bcb_z) if not bcb_nan else None,
                "cftc_z": float(cftc_z) if not cftc_nan else None,
            },
        )


# ---------------------------------------------------------------------------
# CipBasisModel
# ---------------------------------------------------------------------------
class CipBasisModel:
    """CIP deviation: DI 1Y minus (USD offshore rate + expected depreciation).

    Proxy: cip_basis = di_1y - (fed_funds + expected_usdbrl_depreciation_12m)
    where expected_dep comes from Focus Câmbio 12M series.
    Positive basis (DDI > offshore USD cost) = capital flow friction = BRL less attractive.
    Direction (locked in CONTEXT.md): positive basis → LONG USDBRL.
    """

    SIGNAL_ID = "FX_BR_CIP_BASIS"
    Z_FIRE = 0.75     # z-score of basis history to fire signal
    ROLL_WINDOW = 24  # months for z-score baseline
    SIMPLE_THRESHOLD = 1.0  # % — fire on simple basis when no history

    def run(self, features: dict, as_of_date: date) -> AgentSignal:
        """Generate CIP basis signal.

        Args:
            features: Feature dict from FxFeatureEngine.compute().
            as_of_date: Point-in-time reference date.

        Returns:
            AgentSignal with FX_BR_CIP_BASIS signal_id.
        """

        def _no_signal(reason: str = "") -> AgentSignal:
            logger.debug("cip_basis_no_signal: %s", reason)
            return AgentSignal(
                signal_id=self.SIGNAL_ID,
                agent_id="fx_agent",
                timestamp=datetime.utcnow(),
                as_of_date=as_of_date,
                direction=SignalDirection.NEUTRAL,
                strength=SignalStrength.NO_SIGNAL,
                confidence=0.0,
                value=0.0,
                horizon_days=21,
                metadata={"reason": reason},
            )

        cip_basis = features.get("cip_basis")
        di_1y = features.get("_di_1y_rate", np.nan)
        sofr = features.get("_sofr_rate", np.nan)

        # Primary: use pre-computed cip_basis
        basis_value: float
        if cip_basis is not None and not (isinstance(cip_basis, float) and np.isnan(cip_basis)):
            basis_value = float(cip_basis)
        elif not (isinstance(di_1y, float) and np.isnan(di_1y)) and not (
            isinstance(sofr, float) and np.isnan(sofr)
        ):
            # Simplified fallback: di_1y - sofr
            basis_simple = float(di_1y) - float(sofr)
            if abs(basis_simple) < self.SIMPLE_THRESHOLD:
                return _no_signal(f"basis_below_threshold:{basis_simple:.2f}")
            basis_value = basis_simple
        else:
            return _no_signal("no_cip_data")

        # Z-score approach when history available
        cip_history = features.get("_cip_basis_history")
        if (
            cip_history is not None
            and isinstance(cip_history, pd.Series)
            and len(cip_history) >= self.ROLL_WINDOW
        ):
            hist_mean = float(cip_history.mean())
            hist_std = float(cip_history.std())
            if hist_std > 1e-8:
                z = (basis_value - hist_mean) / hist_std
                if abs(z) < self.Z_FIRE:
                    direction = SignalDirection.NEUTRAL
                else:
                    direction = (
                        SignalDirection.LONG if basis_value > 0 else SignalDirection.SHORT
                    )
            else:
                direction = SignalDirection.LONG if basis_value > 0 else SignalDirection.SHORT
        else:
            # Threshold-based when no history
            direction = SignalDirection.LONG if basis_value > 0 else SignalDirection.SHORT

        confidence = min(1.0, abs(basis_value) / 5.0)
        strength = classify_strength(confidence)

        return AgentSignal(
            signal_id=self.SIGNAL_ID,
            agent_id="fx_agent",
            timestamp=datetime.utcnow(),
            as_of_date=as_of_date,
            direction=direction,
            strength=strength,
            confidence=confidence,
            value=round(float(basis_value), 4),
            horizon_days=21,
            metadata={
                "basis_pct": round(float(basis_value), 4),
                "di_1y": features.get("_di_1y_rate", float("nan")),
                "sofr": features.get("_sofr_rate", float("nan")),
                "interpretation": "positive_basis_means_brl_less_attractive",
            },
        )


# ---------------------------------------------------------------------------
# FxEquilibriumAgent
# ---------------------------------------------------------------------------
class FxEquilibriumAgent(BaseAgent):
    """FX equilibrium agent producing 5 signals from BEER, carry, flow, CIP.

    Signals produced:
    1. FX_BR_BEER        — BEER OLS misalignment (±5% threshold, locked)
    2. FX_BR_CARRY_RISK  — Carry-to-risk z-score (|z| > 1.0)
    3. FX_BR_FLOW        — BCB + CFTC FX flow composite z-score
    4. FX_BR_CIP_BASIS   — CIP basis: positive → LONG USDBRL (locked)
    5. FX_BR_COMPOSITE   — Weighted aggregate: BEER 40% + Carry 30% + Flow 20% + CIP 10%
    """

    AGENT_ID = "fx_agent"
    AGENT_NAME = "FX Equilibrium Agent"

    def __init__(self, loader: PointInTimeDataLoader) -> None:
        super().__init__(self.AGENT_ID, self.AGENT_NAME)
        self.loader = loader
        self.feature_engine = FxFeatureEngine()
        self.beer_model = BeerModel()
        self.carry_model = CarryToRiskModel()
        self.flow_model = FlowModel()
        self.cip_model = CipBasisModel()

    # ------------------------------------------------------------------
    # BaseAgent abstract method implementations
    # ------------------------------------------------------------------
    def load_data(self, as_of_date: date) -> dict[str, Any]:
        """Load all FX data using PointInTimeDataLoader.

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

        # USDBRL daily — 15Y for BEER monthly + vol history
        _safe_load(
            "ptax",
            self.loader.get_market_data,
            "USDBRL_PTAX",
            as_of_date,
            lookback_days=5475,
        )
        # BR Selic target
        _safe_load(
            "selic",
            self.loader.get_macro_series,
            "BCB-432",
            as_of_date,
            lookback_days=5475,
        )
        # US Fed Funds
        _safe_load(
            "fed_funds",
            self.loader.get_macro_series,
            "FRED-DFF",
            as_of_date,
            lookback_days=5475,
        )
        # SOFR (may be None pre-2018)
        _safe_load(
            "sofr",
            self.loader.get_macro_series,
            "FRED-SOFR",
            as_of_date,
            lookback_days=1825,
        )
        # FX reserves (NFA proxy)
        _safe_load(
            "fx_reserves",
            self.loader.get_macro_series,
            "BR_RESERVES",
            as_of_date,
            lookback_days=5475,
        )
        # Trade balance (ToT proxy)
        _safe_load(
            "trade_balance",
            self.loader.get_macro_series,
            "BR_TRADE_BALANCE",
            as_of_date,
            lookback_days=5475,
        )
        # Focus Câmbio (expected depreciation) — year-specific code
        cy = as_of_date.year
        _safe_load(
            "focus_cambio",
            self.loader.get_macro_series,
            f"BR_FOCUS_CAMBIO_{cy}_MEDIAN",
            as_of_date,
            lookback_days=1825,
        )
        # Focus IPCA (inflation expectations) — year-specific code
        _safe_load(
            "focus_ipca",
            self.loader.get_macro_series,
            f"BR_FOCUS_IPCA_{cy}_MEDIAN",
            as_of_date,
            lookback_days=5475,
        )
        # DI curve spot (for CIP basis DI 1Y)
        try:
            data["di_curve"] = self.loader.get_curve("DI", as_of_date)
        except Exception as exc:
            self.log.warning("di_curve_load_failed", error=str(exc))
            data["di_curve"] = {}

        # DI curve history at 5Y tenor (for BEER real rate diff)
        # DI_PRE 5Y = 1260 trading days (5 * 252)
        _safe_load(
            "di_curve_history",
            self.loader.get_curve_history,
            "DI",
            1260,
            as_of_date,
            lookback_days=5475,
        )
        # UST 5Y history (for BEER real rate diff)
        # Primary: curve_data from Treasury.gov connector
        _safe_load(
            "ust_5y_history",
            self.loader.get_curve_history,
            "UST",
            1825,
            as_of_date,
            lookback_days=5475,
        )
        # Fallback: FRED DGS5 when Treasury.gov curve data is unavailable
        ust_5y = data.get("ust_5y_history")
        if ust_5y is None or ust_5y.empty:
            self.log.info("ust_curve_empty_using_fred_fallback")
            _safe_load(
                "_fred_ust_5y",
                self.loader.get_macro_series,
                "FRED-DGS5",
                as_of_date,
                lookback_days=5475,
            )
            fred_ust = data.get("_fred_ust_5y")
            if fred_ust is not None and not fred_ust.empty and "value" in fred_ust.columns:
                # Reshape FRED macro series to match curve_history format (date, rate)
                data["ust_5y_history"] = fred_ust[["value"]].rename(columns={"value": "rate"})
        # BCB FX flow commercial + financial
        _safe_load(
            "bcb_flow",
            self.loader.get_flow_data,
            "BR_FX_FLOW_COMMERCIAL",
            as_of_date,
            lookback_days=1825,
        )
        # CFTC 6L BRL leveraged positioning
        _safe_load(
            "cftc_brl",
            self.loader.get_flow_data,
            "CFTC_6L_LEVERAGED_NET",
            as_of_date,
            lookback_days=1825,
        )

        data["_as_of_date"] = as_of_date
        return data

    def compute_features(self, data: dict) -> dict[str, Any]:
        """Compute FX features from raw data.

        Args:
            data: Output of ``load_data()``.

        Returns:
            Feature dictionary with scalar values and private time series keys.
        """
        as_of_date = data.get("_as_of_date")
        if as_of_date is None:
            as_of_date = date.today()
        return self.feature_engine.compute(data, as_of_date)

    def run_models(self, features: dict) -> list[AgentSignal]:
        """Execute all 4 FX models and build composite.

        Order: BEER → Carry → Flow → CIP → Composite.

        Args:
            features: Output of ``compute_features()``.

        Returns:
            List of exactly 5 AgentSignal objects.
        """
        as_of_date = features["_as_of_date"]
        signals = []

        beer_sig = self.beer_model.run(features, as_of_date)
        signals.append(beer_sig)

        carry_sig = self.carry_model.run(features, as_of_date)
        signals.append(carry_sig)

        flow_sig = self.flow_model.run(features, as_of_date)
        signals.append(flow_sig)

        cip_sig = self.cip_model.run(features, as_of_date)
        signals.append(cip_sig)

        # Composite (locked weights per CONTEXT.md)
        signals.append(self._build_composite(signals, as_of_date))
        return signals

    def generate_narrative(self, signals: list[AgentSignal], features: dict) -> str:
        """Generate a human-readable FX equilibrium analysis summary.

        Args:
            signals: List of 5 AgentSignal objects from run_models().
            features: Feature dict from compute_features().

        Returns:
            Formatted analysis text summarizing all signals.
        """
        as_of = features.get("_as_of_date", "unknown")

        # Extract signal metadata safely
        beer_sig = signals[0] if len(signals) > 0 else None
        carry_sig = signals[1] if len(signals) > 1 else None
        flow_sig = signals[2] if len(signals) > 2 else None
        cip_sig = signals[3] if len(signals) > 3 else None
        composite_sig = signals[4] if len(signals) > 4 else None

        beer_dir = beer_sig.direction.value if beer_sig else "N/A"
        misalign = beer_sig.metadata.get("misalignment_pct", 0.0) if beer_sig else 0.0

        carry_dir = carry_sig.direction.value if carry_sig else "N/A"
        z_carry = carry_sig.metadata.get("z_score", carry_sig.value if carry_sig else 0.0)

        flow_dir = flow_sig.direction.value if flow_sig else "N/A"
        z_flow = flow_sig.metadata.get("composite_z", flow_sig.value if flow_sig else 0.0)

        cip_dir = cip_sig.direction.value if cip_sig else "N/A"
        basis = cip_sig.metadata.get("basis_pct", cip_sig.value if cip_sig else 0.0)

        composite_dir = composite_sig.direction.value if composite_sig else "N/A"

        return (
            f"FX Equilibrium Assessment ({as_of}): "
            f"BEER={beer_dir} ({misalign:+.1f}% misalignment). "
            f"Carry-to-Risk={carry_dir} (z={z_carry:.2f}). "
            f"Flow={flow_dir} (composite_z={z_flow:.2f}). "
            f"CIP Basis={cip_dir} ({basis:.2f}%). "
            f"Composite={composite_dir}."
        )

    # ------------------------------------------------------------------
    # Composite signal builder
    # ------------------------------------------------------------------
    def _build_composite(
        self, sub_signals: list[AgentSignal], as_of_date: date
    ) -> AgentSignal:
        """Build FX_BR_COMPOSITE from the 4 FX sub-signals.

        Locked weights (CONTEXT.md):
        - BeerModel:       40% (fundamental valuation, longest horizon)
        - CarryToRiskModel: 30% (risk-adjusted carry)
        - FlowModel:       20% (flow imbalances)
        - CipBasisModel:   10% (funding friction indicator)

        Conflict dampening: 0.70 when any active signal disagrees with
        the plurality direction.

        Args:
            sub_signals: List of [beer_sig, carry_sig, flow_sig, cip_sig].
            as_of_date: Point-in-time reference date.

        Returns:
            AgentSignal with FX_BR_COMPOSITE signal_id.
        """
        base_weights = {
            "FX_BR_BEER":       0.40,
            "FX_BR_CARRY_RISK": 0.30,
            "FX_BR_FLOW":       0.20,
            "FX_BR_CIP_BASIS":  0.10,
        }

        # Filter to active signals (non-NO_SIGNAL and non-NEUTRAL direction)
        active = [
            (sig, base_weights.get(sig.signal_id, 0.0))
            for sig in sub_signals
            if sig.strength != SignalStrength.NO_SIGNAL
            and sig.direction != SignalDirection.NEUTRAL
        ]

        if not active:
            return AgentSignal(
                signal_id="FX_BR_COMPOSITE",
                agent_id="fx_agent",
                timestamp=datetime.utcnow(),
                as_of_date=as_of_date,
                direction=SignalDirection.NEUTRAL,
                strength=SignalStrength.NO_SIGNAL,
                confidence=0.0,
                value=0.0,
                horizon_days=63,
                metadata={"reason": "no_active_sub_signals"},
            )

        # Renormalize weights to active signals
        total_w = sum(w for _, w in active)
        norm_weights = [w / total_w for _, w in active]
        active_sigs = [sig for sig, _ in active]

        # Plurality vote
        long_w = sum(
            w for sig, w in zip(active_sigs, norm_weights)
            if sig.direction == SignalDirection.LONG
        )
        short_w = sum(
            w for sig, w in zip(active_sigs, norm_weights)
            if sig.direction == SignalDirection.SHORT
        )
        plurality_direction = SignalDirection.LONG if long_w >= short_w else SignalDirection.SHORT

        # Conflict dampening
        disagreements = sum(
            1 for sig in active_sigs if sig.direction != plurality_direction
        )
        dampening = 0.70 if disagreements >= 1 else 1.0

        # Weighted confidence with dampening
        weighted_conf = sum(
            sig.confidence * w for sig, w in zip(active_sigs, norm_weights)
        )
        composite_confidence = weighted_conf * dampening
        composite_strength = classify_strength(composite_confidence)

        # Weighted value
        composite_value = sum(
            sig.value * w for sig, w in zip(active_sigs, norm_weights)
        )

        return AgentSignal(
            signal_id="FX_BR_COMPOSITE",
            agent_id="fx_agent",
            timestamp=datetime.utcnow(),
            as_of_date=as_of_date,
            direction=plurality_direction,
            strength=composite_strength,
            confidence=round(composite_confidence, 4),
            value=round(composite_value, 4),
            horizon_days=63,
            metadata={
                "weights": "BEER40_Carry30_Flow20_CIP10",
                "dampening": dampening,
                "n_active": len(active),
                "long_weight": round(long_w, 4),
                "short_weight": round(short_w, 4),
            },
        )

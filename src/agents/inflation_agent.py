"""Inflation agent and sub-models for macro signal generation.

Implements:
- InflationAgent: Template Method agent orchestrating feature computation
  and model execution.  load_data(), compute_features(), run_models(), and
  generate_narrative() are all fully implemented here.
- PhillipsCurveModel: Expectations-augmented OLS Phillips Curve on a
  rolling 120-month (10-year) window.
- IpcaBottomUpModel: 9-component seasonal IBGE-weighted 12M IPCA forecast.
- InflationSurpriseModel: IPCA actual vs Focus MoM consensus z-score signal.
- InflationPersistenceModel: Composite 0-100 inflation persistence score.
- UsInflationTrendModel: US PCE core trend analysis vs Fed 2% target.
"""

from __future__ import annotations

import logging
import warnings
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm

from src.agents.base import AgentSignal, BaseAgent, classify_strength
from src.agents.data_loader import PointInTimeDataLoader
from src.agents.features.inflation_features import InflationFeatureEngine
from src.core.enums import SignalDirection, SignalStrength

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# InflationAgent
# ---------------------------------------------------------------------------
class InflationAgent(BaseAgent):
    """Analytical agent for Brazilian and US inflation signals.

    Implements the BaseAgent Template Method pattern.  All pipeline steps are
    fully implemented: load_data(), compute_features(), run_models(), and
    generate_narrative().  The agent produces exactly 6 AgentSignal objects:
    5 sub-model signals + 1 INFLATION_BR_COMPOSITE.
    """

    AGENT_ID = "inflation_agent"
    AGENT_NAME = "Inflation Agent"

    # BCB SGS series codes
    _IPCA_HEADLINE = "BCB-433"
    _IPCA_CORE_SMOOTHED = "BCB-4466"
    _IPCA_CORE_TRIMMED = "BCB-11427"
    _IPCA_CORE_EX_FE = "BCB-16122"
    _IPCA_SERVICES = "BCB-10841"
    _IPCA_INDUSTRIAL = "BCB-10844"
    _IPCA_DIFFUSION = "BCB-21379"
    _IBC_BR = "BCB-24363"

    _COMPONENTS = {
        "food_home": "BCB-1637",
        "food_away": "BCB-7170",
        "housing": "BCB-1638",
        "clothing": "BCB-1639",
        "health": "BCB-7485",
        "personal_care": "BCB-1640",
        "education": "BCB-1641",
        "transport": "BCB-1642",
        "communication": "BCB-1643",
    }

    _FOCUS_12M = "FOCUS-IPCA-12M"
    _FOCUS_EOY = "FOCUS-IPCA-EOY"

    # FRED series codes
    _US_CPI_CORE = "FRED-CPILFESL"
    _US_PCE_CORE = "FRED-PCEPILFE"
    _US_PCE_SUPERCORE = "FRED-PCESV"
    _US_BREAKEVEN_5Y = "FRED-T5YIE"
    _US_BREAKEVEN_10Y = "FRED-T10YIE"
    _US_MICHIGAN_1Y = "FRED-MICH"
    _US_MICHIGAN_5Y = "FRED-MICH5YR"

    # Market data instruments
    _USDBRL = "USDBRL"
    _CRB = "CRB"

    def __init__(self, loader: PointInTimeDataLoader) -> None:
        super().__init__(self.AGENT_ID, self.AGENT_NAME)
        self.loader = loader
        self.feature_engine = InflationFeatureEngine()
        self.phillips = PhillipsCurveModel()
        self.bottom_up = IpcaBottomUpModel()
        self.surprise = InflationSurpriseModel()
        self.persistence = InflationPersistenceModel()
        self.us_trend = UsInflationTrendModel()

    # ------------------------------------------------------------------
    # load_data — fully implemented
    # ------------------------------------------------------------------
    def load_data(self, as_of_date: date) -> dict[str, Any]:
        """Load all inflation-relevant series from PointInTimeDataLoader.

        Each loader call is wrapped in try/except so a single series
        failure does not abort the whole data load.  Missing series
        return None, which InflationFeatureEngine handles gracefully.

        Args:
            as_of_date: PIT reference date.

        Returns:
            Dict matching InflationFeatureEngine data key expectations.
        """
        lookback_5y = 1825
        lookback_10y = 3650

        def _safe_macro(code: str, lookback: int = lookback_5y) -> pd.DataFrame | None:
            try:
                return self.loader.get_macro_series(code, as_of_date, lookback_days=lookback)
            except Exception as exc:
                self.log.warning("load_macro_failed", code=code, error=str(exc))
                return None

        def _safe_market(ticker: str) -> pd.DataFrame | None:
            try:
                return self.loader.get_market_data(ticker, as_of_date, lookback_days=lookback_5y)
            except Exception as exc:
                self.log.warning("load_market_failed", ticker=ticker, error=str(exc))
                return None

        # IPCA headline (MoM series)
        ipca = _safe_macro(self._IPCA_HEADLINE)

        # IPCA cores
        ipca_cores = {
            "smoothed": _safe_macro(self._IPCA_CORE_SMOOTHED),
            "trimmed": _safe_macro(self._IPCA_CORE_TRIMMED),
            "ex_fe": _safe_macro(self._IPCA_CORE_EX_FE),
        }

        # IPCA 9 components
        ipca_components = {
            key: _safe_macro(code) for key, code in self._COMPONENTS.items()
        }

        # Sub-indices and diffusion
        ipca_services = _safe_macro(self._IPCA_SERVICES)
        ipca_industrial = _safe_macro(self._IPCA_INDUSTRIAL)
        ipca_diffusion = _safe_macro(self._IPCA_DIFFUSION)

        # Focus expectations
        focus_12m = _safe_macro(self._FOCUS_12M)
        focus_eoy = _safe_macro(self._FOCUS_EOY)

        # Combine focus into a single DataFrame with two columns when available
        focus: pd.DataFrame | None = None
        if focus_12m is not None and not focus_12m.empty:
            focus = focus_12m[["value"]].rename(columns={"value": "ipca_12m"})
            if focus_eoy is not None and not focus_eoy.empty:
                eoy = focus_eoy[["value"]].rename(columns={"value": "ipca_eoy"})
                focus = focus.join(eoy, how="outer")
        elif focus_eoy is not None and not focus_eoy.empty:
            focus = focus_eoy[["value"]].rename(columns={"value": "ipca_eoy"})

        # IBC-Br (10Y lookback for HP filter and OLS)
        ibc_br = _safe_macro(self._IBC_BR, lookback=lookback_10y)

        # Market data
        usdbrl = _safe_market(self._USDBRL)
        crb = _safe_market(self._CRB)

        # US macro series (FRED)
        us_cpi = _safe_macro(self._US_CPI_CORE)
        us_pce = _safe_macro(self._US_PCE_CORE)
        us_pce_supercore = _safe_macro(self._US_PCE_SUPERCORE)

        # US breakevens — combine into single DataFrame
        be_5y = _safe_macro(self._US_BREAKEVEN_5Y)
        be_10y = _safe_macro(self._US_BREAKEVEN_10Y)
        us_breakevens: pd.DataFrame | None = None
        if be_5y is not None and not be_5y.empty:
            us_breakevens = be_5y[["value"]].rename(columns={"value": "be_5y"})
            if be_10y is not None and not be_10y.empty:
                b10 = be_10y[["value"]].rename(columns={"value": "be_10y"})
                us_breakevens = us_breakevens.join(b10, how="outer")
        elif be_10y is not None and not be_10y.empty:
            us_breakevens = be_10y[["value"]].rename(columns={"value": "be_10y"})

        # US Michigan survey — combine into single DataFrame
        mich_1y = _safe_macro(self._US_MICHIGAN_1Y)
        mich_5y = _safe_macro(self._US_MICHIGAN_5Y)
        us_michigan: pd.DataFrame | None = None
        if mich_1y is not None and not mich_1y.empty:
            us_michigan = mich_1y[["value"]].rename(columns={"value": "mich_1y"})
            if mich_5y is not None and not mich_5y.empty:
                m5 = mich_5y[["value"]].rename(columns={"value": "mich_5y"})
                us_michigan = us_michigan.join(m5, how="outer")
        elif mich_5y is not None and not mich_5y.empty:
            us_michigan = mich_5y[["value"]].rename(columns={"value": "mich_5y"})

        return {
            "ipca": ipca,
            "ipca_cores": ipca_cores,
            "ipca_components": ipca_components,
            "ipca_services": ipca_services,
            "ipca_industrial": ipca_industrial,
            "ipca_diffusion": ipca_diffusion,
            "focus": focus,
            "ibc_br": ibc_br,
            "usdbrl": usdbrl,
            "crb": crb,
            "us_cpi": us_cpi,
            "us_pce": us_pce,
            "us_pce_supercore": us_pce_supercore,
            "us_breakevens": us_breakevens,
            "us_michigan": us_michigan,
        }

    # ------------------------------------------------------------------
    # compute_features — fully implemented
    # ------------------------------------------------------------------
    def compute_features(self, data: dict) -> dict[str, Any]:
        """Delegate to InflationFeatureEngine.compute() and add private keys.

        Stores ``features["_as_of_date"]`` (required by run_models),
        ``features["_surprise_series"]`` (DataFrame for InflationSurpriseModel),
        and ``features["_services_3m_saar"]`` (float for InflationPersistenceModel).

        Args:
            data: Output of load_data().

        Returns:
            Flat feature dict including private _raw_ols_data,
            _raw_components, _surprise_series, and _services_3m_saar keys.
        """
        # as_of_date stored in data by load_data caller (run/backtest_run)
        as_of_date = data.get("_as_of_date", date.today())
        features = self.feature_engine.compute(data, as_of_date)
        features["_as_of_date"] = as_of_date

        # Build _surprise_series for InflationSurpriseModel
        features["_surprise_series"] = self._build_surprise_series(data)

        # Build _services_3m_saar for InflationPersistenceModel
        features["_services_3m_saar"] = self._compute_services_3m_saar(data)

        return features

    # ------------------------------------------------------------------
    # run_models — fully implemented
    # ------------------------------------------------------------------
    def run_models(self, features: dict) -> list[AgentSignal]:
        """Execute all 5 inflation models and build composite.

        Runs: PhillipsCurve, BottomUp, Surprise, Persistence, UsTrend.
        Then builds INFLATION_BR_COMPOSITE from the 4 BR signals.

        Args:
            features: Output of compute_features(), must include _as_of_date.

        Returns:
            List of exactly 6 AgentSignal objects.
        """
        as_of_date = features["_as_of_date"]
        signals = []

        for model in [self.phillips, self.bottom_up, self.surprise, self.persistence, self.us_trend]:
            try:
                sig = model.run(features, as_of_date)
                signals.append(sig)
            except Exception as exc:
                self.log.warning("model_failed", model=model.SIGNAL_ID, error=str(exc))

        composite = self._build_composite(signals, as_of_date)
        signals.append(composite)
        return signals

    # ------------------------------------------------------------------
    # generate_narrative — fully implemented
    # ------------------------------------------------------------------
    def generate_narrative(self, signals: list[AgentSignal], features: dict) -> str:
        """Generate a human-readable inflation analysis summary.

        Args:
            signals: List of AgentSignal objects from run_models().
            features: Feature dict from compute_features().

        Returns:
            Multi-line analysis text summarizing all signals.
        """
        as_of_date = features.get("_as_of_date", "unknown")
        composite_direction = "NEUTRAL"
        for sig in signals:
            if sig.signal_id == "INFLATION_BR_COMPOSITE":
                composite_direction = sig.direction.value
                break

        lines = ["# Inflation Agent Analysis", ""]
        for sig in signals:
            lines.append(
                f"- {sig.signal_id}: {sig.direction.value} ({sig.strength.value}, conf={sig.confidence:.2f})"
            )
        lines.append(f"\nComposite inflation view: {composite_direction} as of {as_of_date}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Composite signal builder
    # ------------------------------------------------------------------
    def _build_composite(self, signals: list[AgentSignal], as_of_date: date) -> AgentSignal:
        """Weighted composite of BR inflation sub-signals.

        Weights: Phillips 35%, BottomUp 30%, Surprise 20%, Persistence 15%.
        US trend (INFLATION_US_TREND) is excluded from the BR composite.
        Conflict dampening: if >= 2 signals disagree with plurality, reduce
        confidence by 30% (multiply by 0.70).

        Args:
            signals: List of sub-model signals (5 total, US excluded from BR).
            as_of_date: Point-in-time reference date.

        Returns:
            AgentSignal with signal_id="INFLATION_BR_COMPOSITE".
        """
        no_signal_composite = AgentSignal(
            signal_id="INFLATION_BR_COMPOSITE",
            agent_id=self.AGENT_ID,
            timestamp=datetime.utcnow(),
            as_of_date=as_of_date,
            direction=SignalDirection.NEUTRAL,
            strength=SignalStrength.NO_SIGNAL,
            confidence=0.0,
            value=0.0,
            horizon_days=252,
            metadata={"reason": "no_active_br_sub_signals"},
        )

        # Weights only for BR sub-signals (US trend excluded)
        base_weights = {
            "INFLATION_BR_PHILLIPS": 0.35,
            "INFLATION_BR_BOTTOMUP": 0.30,
            "INFLATION_BR_SURPRISE": 0.20,
            "INFLATION_BR_PERSISTENCE": 0.15,
        }

        # Filter to non-NO_SIGNAL BR signals
        active_signals = [
            sig
            for sig in signals
            if sig.signal_id in base_weights and sig.strength != SignalStrength.NO_SIGNAL
        ]

        if not active_signals:
            return no_signal_composite

        # Renormalize weights for available signals
        available_weight = sum(base_weights[sig.signal_id] for sig in active_signals)
        norm_weights = {
            sig.signal_id: base_weights[sig.signal_id] / available_weight
            for sig in active_signals
        }

        # Majority vote for direction (count votes by weight)
        long_w = sum(
            norm_weights[sig.signal_id] for sig in active_signals if sig.direction == SignalDirection.LONG
        )
        short_w = sum(
            norm_weights[sig.signal_id] for sig in active_signals if sig.direction == SignalDirection.SHORT
        )
        neutral_w = sum(
            norm_weights[sig.signal_id] for sig in active_signals if sig.direction == SignalDirection.NEUTRAL
        )

        if long_w >= short_w and long_w >= neutral_w:
            plurality_direction = SignalDirection.LONG
        elif short_w >= long_w and short_w >= neutral_w:
            plurality_direction = SignalDirection.SHORT
        else:
            plurality_direction = SignalDirection.NEUTRAL

        # Conflict detection: >= 2 signals disagree with plurality
        disagreements = sum(1 for sig in active_signals if sig.direction != plurality_direction)
        dampening = 0.70 if disagreements >= 2 else 1.0

        # Weighted confidence with dampening
        composite_confidence = sum(
            norm_weights[sig.signal_id] * sig.confidence for sig in active_signals
        ) * dampening
        composite_confidence = round(min(1.0, composite_confidence), 4)
        strength = classify_strength(composite_confidence)

        effective_weights = {sig.signal_id: round(norm_weights[sig.signal_id], 4) for sig in active_signals}
        sub_directions = {sig.signal_id: sig.direction.value for sig in active_signals}

        return AgentSignal(
            signal_id="INFLATION_BR_COMPOSITE",
            agent_id=self.AGENT_ID,
            timestamp=datetime.utcnow(),
            as_of_date=as_of_date,
            direction=plurality_direction,
            strength=strength,
            confidence=composite_confidence,
            value=composite_confidence,
            horizon_days=252,
            metadata={
                "weights": effective_weights,
                "dampening": dampening,
                "sub_directions": sub_directions,
            },
        )

    # ------------------------------------------------------------------
    # Private helpers for compute_features
    # ------------------------------------------------------------------
    def _build_surprise_series(self, data: dict) -> pd.DataFrame:
        """Build the surprise_series DataFrame for InflationSurpriseModel.

        Returns a DataFrame with columns: actual_mom, focus_mom_median,
        indexed monthly.  Returns empty DataFrame if data unavailable.
        """
        try:
            ipca_df = data.get("ipca")
            focus_df = data.get("focus")

            if ipca_df is None or not isinstance(ipca_df, pd.DataFrame) or ipca_df.empty:
                return pd.DataFrame(columns=["actual_mom", "focus_mom_median"])

            # Get IPCA MoM (actual)
            val_col = "value" if "value" in ipca_df.columns else ipca_df.columns[0]
            actual = ipca_df[[val_col]].rename(columns={val_col: "actual_mom"}).copy()
            actual.index = pd.to_datetime(actual.index)
            actual = actual.resample("ME").last()

            # Get Focus 12M median (used as MoM consensus proxy)
            if focus_df is None or not isinstance(focus_df, pd.DataFrame) or focus_df.empty:
                return pd.DataFrame(columns=["actual_mom", "focus_mom_median"])

            # Focus 12M expectations as MoM proxy (divide YoY by 12)
            focus_val_col = "ipca_12m" if "ipca_12m" in focus_df.columns else focus_df.columns[0]
            focus_series = focus_df[[focus_val_col]].copy()
            focus_series.index = pd.to_datetime(focus_series.index)
            focus_monthly = focus_series.resample("ME").last()
            # Convert 12M YoY expectation to approximate MoM
            focus_monthly["focus_mom_median"] = focus_monthly[focus_val_col] / 12.0
            focus_monthly = focus_monthly[["focus_mom_median"]]

            # Align and join
            surprise = actual.join(focus_monthly, how="inner")
            return surprise.dropna()

        except Exception as exc:
            self.log.warning("surprise_series_build_failed", error=str(exc))
            return pd.DataFrame(columns=["actual_mom", "focus_mom_median"])

    def _compute_services_3m_saar(self, data: dict) -> float:
        """Compute services MoM 3-month SAAR for InflationPersistenceModel.

        Returns:
            SAAR value in %, or np.nan if insufficient data.
        """
        try:
            df = data.get("ipca_services")
            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                return float(np.nan)

            val_col = "value" if "value" in df.columns else df.columns[0]
            series = df[val_col].dropna()
            if len(series) < 4:
                return float(np.nan)

            # Last 3 MoM values, annualized (SAAR)
            last3 = series.iloc[-3:]
            compounded_3m = np.prod(1.0 + last3.values / 100.0)
            saar = (compounded_3m**4 - 1.0) * 100.0
            return float(saar)
        except Exception:
            return float(np.nan)


# ---------------------------------------------------------------------------
# PhillipsCurveModel
# ---------------------------------------------------------------------------
class PhillipsCurveModel:
    """Expectations-augmented OLS Phillips Curve on a rolling 10-year window.

    Fits:
        core_inflation = α + β1*expectations_12m + β2*output_gap
                       + β3*usdbrl_yoy + β4*crb_yoy

    on the trailing WINDOW monthly observations.  Predicts 12M core
    inflation and generates a LONG/SHORT signal vs the BCB target.
    """

    SIGNAL_ID = "INFLATION_BR_PHILLIPS"
    AGENT_ID = "inflation_agent"
    MIN_OBS = 36   # minimum observations to fit
    WINDOW = 120   # 10-year rolling window (months)
    TARGET = 3.0   # BCB inflation target %

    def run(self, features: dict, as_of_date: date) -> AgentSignal:
        """Fit OLS on trailing window, predict, and return signal.

        Args:
            features: Output of InflationAgent.compute_features(), which
                must contain a ``_raw_ols_data`` DataFrame.
            as_of_date: PIT reference date used in the returned signal.

        Returns:
            AgentSignal with direction based on predicted core vs target.
        """
        no_signal = self._no_signal(as_of_date, "insufficient_data")

        try:
            ols_df: pd.DataFrame = features.get("_raw_ols_data", pd.DataFrame())

            if not isinstance(ols_df, pd.DataFrame) or ols_df.empty:
                return no_signal

            # Drop rows missing the dependent variable
            ols_df = ols_df.dropna(subset=["core_yoy"])
            if len(ols_df) < self.MIN_OBS:
                return no_signal

            # Use trailing WINDOW rows
            window_df = ols_df.iloc[-self.WINDOW :]
            y = window_df["core_yoy"]
            x_cols = ["expectations_12m", "output_gap", "usdbrl_yoy", "crb_yoy"]

            # Fill missing regressors with column means (allow partial obs)
            X = window_df[x_cols].copy()
            for col in x_cols:
                X[col] = X[col].fillna(X[col].mean())

            # Drop any remaining NaN rows (all regressors missing)
            mask = X.notna().all(axis=1) & y.notna()
            X_clean = X[mask]
            y_clean = y[mask]

            if len(y_clean) < self.MIN_OBS:
                return self._no_signal(as_of_date, "insufficient_clean_obs")

            X_const = sm.add_constant(X_clean, has_constant="add")
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = sm.OLS(y_clean, X_const).fit()

            # Predict using latest available feature values
            latest_x = {}
            for col in x_cols:
                # Use the last non-NaN value from the full ols_df
                col_series = ols_df[col].dropna()
                latest_x[col] = float(col_series.iloc[-1]) if not col_series.empty else float(X_clean[col].mean())

            latest_df = pd.DataFrame([latest_x])[x_cols]
            latest_const = sm.add_constant(latest_df, has_constant="add")
            predicted_core = float(model.predict(latest_const).iloc[0])

            gap = predicted_core - self.TARGET
            confidence = min(1.0, abs(gap) / 3.0)
            strength = classify_strength(confidence)

            if gap > 0.5:
                direction = SignalDirection.LONG
            elif gap < -0.5:
                direction = SignalDirection.SHORT
            else:
                direction = SignalDirection.NEUTRAL

            coefs = dict(zip(model.model.exog_names, model.params.tolist()))

            return AgentSignal(
                signal_id=self.SIGNAL_ID,
                agent_id=self.AGENT_ID,
                timestamp=datetime.utcnow(),
                as_of_date=as_of_date,
                direction=direction,
                strength=strength,
                confidence=confidence,
                value=predicted_core,
                horizon_days=252,
                metadata={
                    "r_squared": float(model.rsquared),
                    "n_obs": int(model.nobs),
                    "coefficients": coefs,
                    "prediction": predicted_core,
                    "gap_vs_target": gap,
                    "target": self.TARGET,
                },
            )

        except Exception as exc:
            log.warning("phillips_curve_failed", error=str(exc))
            return self._no_signal(as_of_date, f"exception: {exc}")

    def _no_signal(self, as_of_date: date, reason: str) -> AgentSignal:
        return AgentSignal(
            signal_id=self.SIGNAL_ID,
            agent_id=self.AGENT_ID,
            timestamp=datetime.utcnow(),
            as_of_date=as_of_date,
            direction=SignalDirection.NEUTRAL,
            strength=SignalStrength.NO_SIGNAL,
            confidence=0.0,
            value=0.0,
            horizon_days=252,
            metadata={"reason": reason},
        )


# ---------------------------------------------------------------------------
# IpcaBottomUpModel
# ---------------------------------------------------------------------------
class IpcaBottomUpModel:
    """Component-level IPCA forecast using seasonal patterns + IBGE weights.

    For each of the 9 IPCA sub-components, computes the trailing 5-year
    seasonal factor per calendar month, projects 12 months of factors
    from the current month, and aggregates using official IBGE weights.
    """

    SIGNAL_ID = "INFLATION_BR_BOTTOMUP"
    AGENT_ID = "inflation_agent"
    TARGET = 3.0    # BCB inflation target %
    BAND = 1.5      # tolerance band (±1.5pp from target)

    IBGE_WEIGHTS: dict[str, float] = {
        "food_home": 0.21,
        "food_away": 0.11,
        "housing": 0.16,
        "clothing": 0.04,
        "health": 0.14,
        "personal_care": 0.09,
        "education": 0.06,
        "transport": 0.12,
        "communication": 0.05,
    }

    # Number of months of history to use for seasonal calculation
    SEASONAL_WINDOW = 60  # 5 years

    def run(self, features: dict, as_of_date: date) -> AgentSignal:
        """Aggregate 9-component seasonal forecast to 12M IPCA projection.

        Args:
            features: Output of InflationAgent.compute_features(), which
                must contain a ``_raw_components`` dict of DataFrames.
            as_of_date: PIT reference date.

        Returns:
            AgentSignal based on forecast vs BCB target+band.
        """
        no_signal = self._no_signal(as_of_date, "insufficient_data")

        try:
            raw_components: dict[str, pd.DataFrame] = features.get("_raw_components", {})
            if not raw_components:
                return no_signal

            component_forecasts: dict[str, float] = {}
            components_used: dict[str, dict] = {}

            current_month = as_of_date.month

            for component, weight in self.IBGE_WEIGHTS.items():
                df = raw_components.get(component)
                if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                    continue

                series = df["value"].dropna()
                if len(series) < 12:
                    continue

                # Use trailing SEASONAL_WINDOW months
                trailing = series.iloc[-self.SEASONAL_WINDOW :]
                trailing.index = pd.to_datetime(trailing.index)

                # Compute seasonal factor per calendar month (mean MoM for that month)
                seasonal_by_month: dict[int, float] = {}
                for m in range(1, 13):
                    month_vals = trailing[trailing.index.month == m]
                    if not month_vals.empty:
                        seasonal_by_month[m] = float(month_vals.mean())

                if not seasonal_by_month:
                    continue

                # Project 12 months starting from next month (current_month + 1)
                projected_moms: list[float] = []
                monthly_details: list[dict] = []
                for i in range(1, 13):
                    proj_month = ((current_month - 1 + i) % 12) + 1
                    # Use seasonal average, or overall mean as fallback
                    mom = seasonal_by_month.get(
                        proj_month,
                        float(np.mean(list(seasonal_by_month.values()))),
                    )
                    projected_moms.append(mom)
                    monthly_details.append({"month": proj_month, "seasonal_mom": mom})

                # 12M compounded cumulative from 12 MoM values
                annual_forecast = (np.prod([1.0 + m / 100.0 for m in projected_moms]) - 1.0) * 100.0
                component_forecasts[component] = annual_forecast
                components_used[component] = {
                    "forecast_12m": annual_forecast,
                    "seasonal_months": len(seasonal_by_month),
                    "monthly": monthly_details,
                }

            if len(component_forecasts) < 3:
                return self._no_signal(as_of_date, f"only {len(component_forecasts)} components available")

            # Weighted aggregate
            # Re-normalize weights to available components
            available_weight = sum(
                self.IBGE_WEIGHTS[c] for c in component_forecasts
            )
            if available_weight <= 0:
                return no_signal

            forecast_12m = sum(
                component_forecasts[c] * self.IBGE_WEIGHTS[c]
                for c in component_forecasts
            ) / available_weight

            # Signal generation
            gap = forecast_12m - self.TARGET
            confidence = min(1.0, abs(gap) / (self.BAND * 2.0))
            strength = classify_strength(confidence)

            if forecast_12m > self.TARGET + self.BAND:
                direction = SignalDirection.LONG
            elif forecast_12m < self.TARGET - self.BAND:
                direction = SignalDirection.SHORT
            else:
                direction = SignalDirection.NEUTRAL

            return AgentSignal(
                signal_id=self.SIGNAL_ID,
                agent_id=self.AGENT_ID,
                timestamp=datetime.utcnow(),
                as_of_date=as_of_date,
                direction=direction,
                strength=strength,
                confidence=confidence,
                value=forecast_12m,
                horizon_days=252,
                metadata={
                    "forecast_12m": forecast_12m,
                    "target": self.TARGET,
                    "band": self.BAND,
                    "gap_vs_target": gap,
                    "components_used": len(component_forecasts),
                    "normalized_weight": available_weight,
                    "component_forecasts": components_used,
                },
            )

        except Exception as exc:
            log.warning("ipca_bottomup_failed", error=str(exc))
            return self._no_signal(as_of_date, f"exception: {exc}")

    def _no_signal(self, as_of_date: date, reason: str) -> AgentSignal:
        return AgentSignal(
            signal_id=self.SIGNAL_ID,
            agent_id=self.AGENT_ID,
            timestamp=datetime.utcnow(),
            as_of_date=as_of_date,
            direction=SignalDirection.NEUTRAL,
            strength=SignalStrength.NO_SIGNAL,
            confidence=0.0,
            value=0.0,
            horizon_days=252,
            metadata={"reason": reason},
        )


# ---------------------------------------------------------------------------
# InflationSurpriseModel
# ---------------------------------------------------------------------------
class InflationSurpriseModel:
    """IPCA actual vs Focus MoM consensus z-score signal.

    Computes the rolling 3-month average surprise (actual - consensus MoM),
    normalizes it against trailing 12-month history, and fires a signal when
    the absolute z-score exceeds Z_FIRE.

    Direction conventions (locked per CONTEXT.md):
    - Upside surprise (actual > consensus, z > 0) → LONG (hawkish signal)
    - Downside surprise (z < 0) → SHORT
    """

    SIGNAL_ID = "INFLATION_BR_SURPRISE"
    AGENT_ID = "inflation_agent"
    Z_FIRE = 1.0    # |z| > 1.0 → signal fires
    Z_STRONG = 2.0  # |z| > 2.0 → STRONG

    def run(self, features: dict, as_of_date: date) -> AgentSignal:
        """Compute surprise z-score and return directional signal.

        Args:
            features: Must contain ``_surprise_series`` — a DataFrame with
                columns ``actual_mom`` and ``focus_mom_median``, monthly
                DatetimeIndex, at least 12 rows.
            as_of_date: PIT reference date.

        Returns:
            AgentSignal with direction LONG (upside) or SHORT (downside),
            or NO_SIGNAL if insufficient data or |z| < Z_FIRE.
        """
        try:
            surprise_df: pd.DataFrame = features.get("_surprise_series", pd.DataFrame())

            if surprise_df is None or not isinstance(surprise_df, pd.DataFrame) or surprise_df.empty:
                return self._no_signal(as_of_date, "no_surprise_series")

            if len(surprise_df) < 12:
                return self._no_signal(as_of_date, "insufficient_data_lt_12m")

            # Ensure required columns exist
            if "actual_mom" not in surprise_df.columns or "focus_mom_median" not in surprise_df.columns:
                return self._no_signal(as_of_date, "missing_columns")

            # Monthly surprise = actual - consensus (in pp)
            monthly_surprise = surprise_df["actual_mom"] - surprise_df["focus_mom_median"]

            # Rolling 3M average
            rolling_3m = monthly_surprise.rolling(3).mean()
            if rolling_3m.empty or pd.isna(rolling_3m.iloc[-1]):
                return self._no_signal(as_of_date, "rolling_3m_nan")
            rolling_3m_avg = float(rolling_3m.iloc[-1])

            # Trailing 12M statistics for normalization
            trailing_12m = monthly_surprise.tail(12)
            mean_12m = float(trailing_12m.mean())
            std_12m = float(trailing_12m.std())

            # Handle zero std (no variation)
            if std_12m == 0.0 or pd.isna(std_12m):
                return self._no_signal(as_of_date, "zero_std_no_variation")

            z_score = (rolling_3m_avg - mean_12m) / std_12m

            # Signal fires only when |z| >= Z_FIRE
            if abs(z_score) < self.Z_FIRE:
                return AgentSignal(
                    signal_id=self.SIGNAL_ID,
                    agent_id=self.AGENT_ID,
                    timestamp=datetime.utcnow(),
                    as_of_date=as_of_date,
                    direction=SignalDirection.NEUTRAL,
                    strength=SignalStrength.NO_SIGNAL,
                    confidence=0.0,
                    value=round(z_score, 4),
                    horizon_days=63,
                    metadata={
                        "z_score": z_score,
                        "rolling_3m_avg_pp": rolling_3m_avg,
                        "trailing_12m_std": std_12m,
                        "reason": "z_below_fire_threshold",
                    },
                )

            # Direction: upside surprise → LONG (hawkish), downside → SHORT
            direction = SignalDirection.LONG if z_score > 0 else SignalDirection.SHORT

            # Strength and confidence
            if abs(z_score) >= self.Z_STRONG:
                confidence = max(0.85, min(1.0, 0.85 + (abs(z_score) - self.Z_STRONG) * 0.05))
                strength = SignalStrength.STRONG
            else:
                confidence = min(abs(z_score) / 2.0, 1.0)
                strength = classify_strength(confidence)

            return AgentSignal(
                signal_id=self.SIGNAL_ID,
                agent_id=self.AGENT_ID,
                timestamp=datetime.utcnow(),
                as_of_date=as_of_date,
                direction=direction,
                strength=strength,
                confidence=round(confidence, 4),
                value=round(z_score, 4),
                horizon_days=63,
                metadata={
                    "z_score": z_score,
                    "rolling_3m_avg_pp": rolling_3m_avg,
                    "trailing_12m_std": std_12m,
                },
            )

        except Exception as exc:
            log.warning("inflation_surprise_failed", error=str(exc))
            return self._no_signal(as_of_date, f"exception: {exc}")

    def _no_signal(self, as_of_date: date, reason: str) -> AgentSignal:
        return AgentSignal(
            signal_id=self.SIGNAL_ID,
            agent_id=self.AGENT_ID,
            timestamp=datetime.utcnow(),
            as_of_date=as_of_date,
            direction=SignalDirection.NEUTRAL,
            strength=SignalStrength.NO_SIGNAL,
            confidence=0.0,
            value=0.0,
            horizon_days=63,
            metadata={"reason": reason},
        )


# ---------------------------------------------------------------------------
# InflationPersistenceModel
# ---------------------------------------------------------------------------
class InflationPersistenceModel:
    """Composite 0-100 inflation persistence score from 4 components.

    Components (equal weight 25% each):
    1. Diffusion index (already 0-100)
    2. Core acceleration (3M vs 6M momentum)
    3. Services momentum (3M SAAR)
    4. Expectations anchoring (inverted distance from BCB target)

    Missing components are skipped and weights are renormalized.
    """

    SIGNAL_ID = "INFLATION_BR_PERSISTENCE"
    AGENT_ID = "inflation_agent"
    WEIGHTS = {"diffusion": 0.25, "core_accel": 0.25, "services_mom": 0.25, "expectations": 0.25}
    HIGH_THRESHOLD = 60.0  # score > 60 → LONG (sticky inflation)
    LOW_THRESHOLD = 40.0   # score < 40 → SHORT (falling)

    def run(self, features: dict, as_of_date: date) -> AgentSignal:
        """Compute persistence composite score and return directional signal.

        Args:
            features: Must contain ``ipca_diffusion``, ``ipca_core_smoothed``
                (or a DataFrame), ``_services_3m_saar``, and ``focus_ipca_12m``.
            as_of_date: PIT reference date.

        Returns:
            AgentSignal with direction based on composite 0-100 score.
        """
        try:
            sub_scores: dict[str, float] = {}

            # 1. Diffusion sub-score (0-100 normalized, already in that range)
            ipca_diffusion = features.get("ipca_diffusion", np.nan)
            if not pd.isna(ipca_diffusion):
                sub_scores["diffusion"] = float(min(100.0, max(0.0, ipca_diffusion)))

            # 2. Core acceleration (3M vs 6M momentum of core YoY)
            ipca_core_raw = features.get("ipca_core_smoothed", np.nan)
            # Try to get DataFrame-based core series for momentum computation
            raw_ols = features.get("_raw_ols_data")
            if raw_ols is not None and isinstance(raw_ols, pd.DataFrame) and not raw_ols.empty:
                core_series = raw_ols["core_yoy"].dropna()
                if len(core_series) >= 6:
                    avg_3m = float(core_series.iloc[-3:].mean())
                    avg_6m = float(core_series.iloc[-6:].mean())
                    diff = avg_3m - avg_6m
                    # Normalize: 50 + (diff * 10) clamped to [0, 100]
                    core_accel_sub = float(min(100.0, max(0.0, 50.0 + diff * 10.0)))
                    sub_scores["core_accel"] = core_accel_sub
            elif not pd.isna(ipca_core_raw):
                # Fallback: use scalar — treat as neutral (50)
                sub_scores["core_accel"] = 50.0

            # 3. Services momentum (3M SAAR)
            services_saar = features.get("_services_3m_saar", np.nan)
            if not pd.isna(services_saar):
                # SAAR in [0, 15] range → normalize to [0, 100]
                services_sub = float(min(100.0, max(0.0, services_saar / 15.0 * 100.0)))
                sub_scores["services_mom"] = services_sub

            # 4. Expectations anchoring (inverted: closer to target = higher score)
            focus_12m = features.get("focus_ipca_12m", np.nan)
            if not pd.isna(focus_12m):
                bcb_target = 3.0
                # anchoring_sub = max(0, 100 - |focus - target| * 20)
                anchoring_sub = float(max(0.0, 100.0 - abs(focus_12m - bcb_target) * 20.0))
                sub_scores["expectations"] = anchoring_sub

            # If all 4 components are NaN → NO_SIGNAL
            if not sub_scores:
                return self._no_signal(as_of_date, "all_sub_scores_nan")

            # Renormalize weights among available components
            available_weight = sum(self.WEIGHTS[k] for k in sub_scores)
            norm_weights = {k: self.WEIGHTS[k] / available_weight for k in sub_scores}

            # Composite score
            score = sum(sub_scores[k] * norm_weights[k] for k in sub_scores)
            score = round(score, 2)

            # Direction
            if score > self.HIGH_THRESHOLD:
                direction = SignalDirection.LONG
            elif score < self.LOW_THRESHOLD:
                direction = SignalDirection.SHORT
            else:
                direction = SignalDirection.NEUTRAL

            # Confidence: distance from neutral midpoint (50)
            confidence = round(abs(score - 50.0) / 50.0, 4)
            strength = classify_strength(confidence)

            return AgentSignal(
                signal_id=self.SIGNAL_ID,
                agent_id=self.AGENT_ID,
                timestamp=datetime.utcnow(),
                as_of_date=as_of_date,
                direction=direction,
                strength=strength,
                confidence=confidence,
                value=score,
                horizon_days=63,
                metadata={
                    "score": score,
                    "diffusion_sub": sub_scores.get("diffusion", float("nan")),
                    "core_accel_sub": sub_scores.get("core_accel", float("nan")),
                    "services_sub": sub_scores.get("services_mom", float("nan")),
                    "expectations_sub": sub_scores.get("expectations", float("nan")),
                },
            )

        except Exception as exc:
            log.warning("inflation_persistence_failed", error=str(exc))
            return self._no_signal(as_of_date, f"exception: {exc}")

    def _no_signal(self, as_of_date: date, reason: str) -> AgentSignal:
        return AgentSignal(
            signal_id=self.SIGNAL_ID,
            agent_id=self.AGENT_ID,
            timestamp=datetime.utcnow(),
            as_of_date=as_of_date,
            direction=SignalDirection.NEUTRAL,
            strength=SignalStrength.NO_SIGNAL,
            confidence=0.0,
            value=0.0,
            horizon_days=63,
            metadata={"reason": reason},
        )


# ---------------------------------------------------------------------------
# UsInflationTrendModel
# ---------------------------------------------------------------------------
class UsInflationTrendModel:
    """US PCE core trend analysis vs Fed 2% target.

    Compares PCE core 3M SAAR and YoY against the Fed's 2% target.
    Secondary confirmation via PCE supercore momentum.
    """

    SIGNAL_ID = "INFLATION_US_TREND"
    AGENT_ID = "inflation_agent"
    FED_TARGET = 2.0

    def run(self, features: dict, as_of_date: date) -> AgentSignal:
        """Analyze US PCE trend relative to Fed target.

        Args:
            features: Must contain ``us_pce_core_3m_saar``, ``us_pce_core_yoy``,
                and ``us_pce_supercore_mom_3m``.
            as_of_date: PIT reference date.

        Returns:
            AgentSignal with direction and confidence based on PCE gap.
        """
        try:
            pce_3m_saar = features.get("us_pce_core_3m_saar", np.nan)
            pce_yoy = features.get("us_pce_core_yoy", np.nan)
            supercore_mom = features.get("us_pce_supercore_mom_3m", np.nan)

            # If all inputs are NaN → NO_SIGNAL
            pce_3m_valid = not pd.isna(pce_3m_saar)
            pce_yoy_valid = not pd.isna(pce_yoy)
            supercore_valid = not pd.isna(supercore_mom)

            if not pce_3m_valid and not pce_yoy_valid:
                return self._no_signal(as_of_date, "all_inputs_nan")

            # Target gap using YoY (most reliable)
            if pce_yoy_valid:
                target_gap = float(pce_yoy) - self.FED_TARGET
            else:
                target_gap = float(pce_3m_saar) - self.FED_TARGET  # type: ignore[arg-type]

            # Primary direction signal
            if pce_3m_valid and pce_yoy_valid:
                if float(pce_3m_saar) > self.FED_TARGET and target_gap > 0:  # type: ignore[arg-type]
                    direction = SignalDirection.LONG
                elif float(pce_3m_saar) < self.FED_TARGET and target_gap < 0:  # type: ignore[arg-type]
                    direction = SignalDirection.SHORT
                else:
                    direction = SignalDirection.NEUTRAL
            elif pce_yoy_valid:
                direction = SignalDirection.LONG if target_gap > 0 else (
                    SignalDirection.SHORT if target_gap < 0 else SignalDirection.NEUTRAL
                )
            else:
                gap_3m = float(pce_3m_saar) - self.FED_TARGET  # type: ignore[arg-type]
                direction = SignalDirection.LONG if gap_3m > 0 else (
                    SignalDirection.SHORT if gap_3m < 0 else SignalDirection.NEUTRAL
                )

            # Base confidence: 2pp above target = full confidence
            confidence = min(1.0, abs(target_gap) / 2.0)

            # Secondary confirmation: supercore momentum
            if supercore_valid:
                supercore_val = float(supercore_mom)  # type: ignore[arg-type]
                if direction == SignalDirection.LONG and supercore_val > 0:
                    confidence = min(1.0, confidence + 0.10)
                elif direction == SignalDirection.SHORT and supercore_val < 0:
                    confidence = min(1.0, confidence + 0.10)
                elif direction != SignalDirection.NEUTRAL:
                    # Opposing supercore → dampen
                    confidence = max(0.0, confidence - 0.10)

            confidence = round(confidence, 4)
            strength = classify_strength(confidence)

            # Primary value: 3M SAAR if available, else YoY
            value = round(float(pce_3m_saar), 4) if pce_3m_valid else round(float(pce_yoy), 4)  # type: ignore[arg-type]

            return AgentSignal(
                signal_id=self.SIGNAL_ID,
                agent_id=self.AGENT_ID,
                timestamp=datetime.utcnow(),
                as_of_date=as_of_date,
                direction=direction,
                strength=strength,
                confidence=confidence,
                value=value,
                horizon_days=252,
                metadata={
                    "pce_3m_saar": float(pce_3m_saar) if pce_3m_valid else None,
                    "target_gap_pp": target_gap,
                    "supercore_momentum": float(supercore_mom) if supercore_valid else None,
                },
            )

        except Exception as exc:
            log.warning("us_inflation_trend_failed", error=str(exc))
            return self._no_signal(as_of_date, f"exception: {exc}")

    def _no_signal(self, as_of_date: date, reason: str) -> AgentSignal:
        return AgentSignal(
            signal_id=self.SIGNAL_ID,
            agent_id=self.AGENT_ID,
            timestamp=datetime.utcnow(),
            as_of_date=as_of_date,
            direction=SignalDirection.NEUTRAL,
            strength=SignalStrength.NO_SIGNAL,
            confidence=0.0,
            value=0.0,
            horizon_days=252,
            metadata={"reason": reason},
        )

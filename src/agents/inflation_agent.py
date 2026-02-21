"""Inflation agent and sub-models for macro signal generation.

Implements:
- InflationAgent: Template Method agent orchestrating feature computation
  and model execution.  load_data() and compute_features() are fully
  implemented here; run_models() will be expanded in Plan 08-02.
- PhillipsCurveModel: Expectations-augmented OLS Phillips Curve on a
  rolling 120-month (10-year) window.
- IpcaBottomUpModel: 9-component seasonal forecast aggregated with
  official IBGE weights.
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

    Implements the BaseAgent Template Method pattern.  Data loading and
    feature computation are fully implemented; model execution is stubbed
    for Plan 08-02 completion.
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
        """Delegate to InflationFeatureEngine.compute().

        Args:
            data: Output of load_data().

        Returns:
            Flat feature dict including private _raw_ols_data and
            _raw_components keys for downstream models.
        """
        # as_of_date is not stored on data; pass today as placeholder.
        # PhillipsCurveModel and IpcaBottomUpModel receive as_of_date
        # explicitly via run().
        return self.feature_engine.compute(data, date.today())

    # ------------------------------------------------------------------
    # run_models — stub (completed in Plan 08-02)
    # ------------------------------------------------------------------
    def run_models(self, features: dict) -> list[AgentSignal]:
        """Execute quantitative models (stub — completed in Plan 08-02).

        Returns empty list until Plan 08-02 wires in all models.
        """
        return []

    # ------------------------------------------------------------------
    # generate_narrative — stub (completed in Plan 08-02)
    # ------------------------------------------------------------------
    def generate_narrative(self, signals: list[AgentSignal], features: dict) -> str:
        """Generate analysis narrative (stub — completed in Plan 08-02)."""
        return ""


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

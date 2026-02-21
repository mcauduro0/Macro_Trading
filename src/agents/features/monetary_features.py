"""Monetary policy feature engine for BCB and US Fed analysis.

Computes BR DI curve shape features, BCB policy inputs, and US UST curve
features for use by MonetaryPolicyAgent models.

All computations are guarded with try/except returning np.nan on failure.
Private keys (prefixed with ``_``) carry full time series for models that
require history (Kalman filter, term premium z-score).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HP Filter (local implementation — no statsmodels dependency required)
# ---------------------------------------------------------------------------
def _hp_filter_trend(series: pd.Series, lamb: float = 1600.0) -> pd.Series:
    """Hodrick-Prescott filter returning the trend component.

    Args:
        series: Input time series (must have at least 4 observations).
        lamb: Smoothing parameter (default 1600 for quarterly; use 129600 for monthly).

    Returns:
        Trend component as pd.Series aligned with input index.
        Returns series unchanged if too few observations.
    """
    s = series.dropna()
    n = len(s)
    if n < 4:
        return series

    # Build second-difference matrix
    eye = np.eye(n)
    d2 = np.diff(eye, n=2, axis=0)  # (n-2) x n
    mat = eye + lamb * d2.T @ d2
    trend_vals = np.linalg.solve(mat, s.values)
    return pd.Series(trend_vals, index=s.index)


# ---------------------------------------------------------------------------
# MonetaryFeatureEngine
# ---------------------------------------------------------------------------
class MonetaryFeatureEngine:
    """Compute BR DI curve shape + US UST curve features for monetary analysis.

    Expected data dict keys (all may be absent; missing data degrades gracefully):
    - ``di_curve``: DataFrame with columns tenor_1y, tenor_2y, tenor_5y, tenor_10y
    - ``selic``: DataFrame with column ``value`` (Selic target %)
    - ``focus``: DataFrame with column ``focus_ipca_12m`` (Focus IPCA 12M median)
    - ``ibc_br``: DataFrame with column ``value`` (IBC-Br index level, monthly)
    - ``selic_history``: Full Selic monthly history DataFrame (same structure as selic)
    - ``fed_funds``: DataFrame with column ``value`` (Fed Funds Effective Rate)
    - ``ust_curve``: DataFrame with columns ust_2y, ust_5y, ust_10y
    - ``nfci``: DataFrame with column ``value`` (Chicago Fed NFCI)
    - ``pce_core``: DataFrame with column ``value`` (PCE Core YoY %)
    - ``us_breakeven``: DataFrame with column ``value`` (10Y US breakeven inflation)
    """

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------
    def compute(self, data: dict, as_of_date: date) -> dict[str, Any]:
        """Return flat dict of all monetary policy features.

        Args:
            data: Dictionary of raw DataFrames from PointInTimeDataLoader.
            as_of_date: Point-in-time reference date for the computation.

        Returns:
            Feature dictionary with scalar values, plus private ``_``-prefixed
            keys holding time series needed by downstream models.
        """
        features: dict[str, Any] = {"_as_of_date": as_of_date}

        # BR features
        features.update(self._compute_di_curve_features(data))
        features.update(self._compute_bcb_policy_features(data, features))
        features.update(self._compute_ibc_br_features(data))
        features.update(self._compute_history_series(data, features))

        # US features
        features.update(self._compute_us_features(data))

        return features

    # -----------------------------------------------------------------------
    # BR DI curve shape
    # -----------------------------------------------------------------------
    def _compute_di_curve_features(self, data: dict) -> dict[str, Any]:
        """Compute DI curve level and shape features."""
        f: dict[str, Any] = {}
        try:
            df = data.get("di_curve")
            if df is None or df.empty:
                raise ValueError("di_curve is empty")

            # Latest row
            row = df.iloc[-1]

            di_1y = float(row.get("tenor_1y", np.nan))
            di_2y = float(row.get("tenor_2y", np.nan))
            di_5y = float(row.get("tenor_5y", np.nan))
            di_10y = float(row.get("tenor_10y", np.nan))

            f["di_1y"] = di_1y
            f["di_2y"] = di_2y
            f["di_5y"] = di_5y
            f["di_10y"] = di_10y
            f["di_slope"] = di_10y - di_1y
            f["di_belly"] = di_2y - (di_1y + di_5y) / 2.0
            f["di_long_premium"] = di_10y - di_5y
        except Exception as exc:
            logger.warning("di_curve_features_failed: %s", exc)
            for key in ("di_1y", "di_2y", "di_5y", "di_10y", "di_slope", "di_belly", "di_long_premium"):
                f[key] = np.nan
        return f

    # -----------------------------------------------------------------------
    # BCB policy features
    # -----------------------------------------------------------------------
    def _compute_bcb_policy_features(self, data: dict, features: dict) -> dict[str, Any]:
        """Compute Selic, Focus, and policy gap features."""
        f: dict[str, Any] = {}
        try:
            selic_df = data.get("selic")
            if selic_df is not None and not selic_df.empty:
                selic_target = float(selic_df["value"].iloc[-1])
            else:
                selic_target = np.nan
            f["selic_target"] = selic_target
        except Exception as exc:
            logger.warning("selic_target_failed: %s", exc)
            f["selic_target"] = np.nan

        try:
            focus_df = data.get("focus")
            if focus_df is not None and not focus_df.empty:
                # Support both column naming conventions
                if "focus_ipca_12m" in focus_df.columns:
                    focus_ipca_12m = float(focus_df["focus_ipca_12m"].iloc[-1])
                elif "value" in focus_df.columns:
                    focus_ipca_12m = float(focus_df["value"].iloc[-1])
                else:
                    focus_ipca_12m = np.nan
            else:
                focus_ipca_12m = np.nan
            f["focus_ipca_12m"] = focus_ipca_12m
        except Exception as exc:
            logger.warning("focus_ipca_failed: %s", exc)
            f["focus_ipca_12m"] = np.nan

        # Real rate implied by BCB
        try:
            f["real_rate_gap"] = f["selic_target"] - f["focus_ipca_12m"]
        except Exception:
            f["real_rate_gap"] = np.nan

        # 1Y real DI rate
        try:
            di_1y = features.get("di_1y", np.nan)
            focus_ipca_12m = f.get("focus_ipca_12m", np.nan)
            f["di_1y_real"] = di_1y - focus_ipca_12m
        except Exception:
            f["di_1y_real"] = np.nan

        # Policy inertia: change in Selic over last 3 meetings (approximated as 3 months)
        try:
            selic_df = data.get("selic")
            if selic_df is not None and len(selic_df) >= 4:
                selic_vals = selic_df["value"].dropna()
                if len(selic_vals) >= 4:
                    f["policy_inertia"] = float(selic_vals.iloc[-1] - selic_vals.iloc[-4])
                else:
                    f["policy_inertia"] = 0.0
            else:
                f["policy_inertia"] = 0.0
        except Exception as exc:
            logger.warning("policy_inertia_failed: %s", exc)
            f["policy_inertia"] = 0.0

        return f

    # -----------------------------------------------------------------------
    # IBC-Br output gap
    # -----------------------------------------------------------------------
    def _compute_ibc_br_features(self, data: dict) -> dict[str, Any]:
        """Compute IBC-Br HP-filter output gap."""
        f: dict[str, Any] = {}
        try:
            ibc_df = data.get("ibc_br")
            if ibc_df is None or ibc_df.empty:
                raise ValueError("ibc_br is empty")

            vals = ibc_df["value"].dropna()
            if len(vals) < 12:
                raise ValueError("insufficient ibc_br observations")

            # HP filter with monthly lambda
            trend = _hp_filter_trend(vals, lamb=129600.0)
            gap = (vals - trend) / trend * 100.0
            f["ibc_br_output_gap"] = float(gap.iloc[-1]) if len(gap) > 0 else np.nan
        except Exception as exc:
            logger.warning("ibc_br_output_gap_failed: %s", exc)
            f["ibc_br_output_gap"] = np.nan
        return f

    # -----------------------------------------------------------------------
    # History series (for Kalman and term premium)
    # -----------------------------------------------------------------------
    def _compute_history_series(self, data: dict, features: dict) -> dict[str, Any]:
        """Compute private time series keys needed by downstream models."""
        f: dict[str, Any] = {}

        # Selic history series
        try:
            selic_df = data.get("selic")
            if selic_df is not None and not selic_df.empty:
                f["_selic_history_series"] = selic_df["value"].dropna()
            else:
                f["_selic_history_series"] = pd.Series(dtype=float)
        except Exception as exc:
            logger.warning("selic_history_failed: %s", exc)
            f["_selic_history_series"] = pd.Series(dtype=float)

        # Focus history series
        try:
            focus_df = data.get("focus")
            if focus_df is not None and not focus_df.empty:
                if "focus_ipca_12m" in focus_df.columns:
                    f["_focus_history_series"] = focus_df["focus_ipca_12m"].dropna()
                elif "value" in focus_df.columns:
                    f["_focus_history_series"] = focus_df["value"].dropna()
                else:
                    f["_focus_history_series"] = pd.Series(dtype=float)
            else:
                f["_focus_history_series"] = pd.Series(dtype=float)
        except Exception as exc:
            logger.warning("focus_history_failed: %s", exc)
            f["_focus_history_series"] = pd.Series(dtype=float)

        # IBC-Br output gap series
        try:
            ibc_df = data.get("ibc_br")
            if ibc_df is not None and not ibc_df.empty:
                vals = ibc_df["value"].dropna()
                if len(vals) >= 12:
                    trend = _hp_filter_trend(vals, lamb=129600.0)
                    gap_series = (vals - trend) / trend * 100.0
                    f["_ibc_gap_series"] = gap_series
                else:
                    f["_ibc_gap_series"] = pd.Series(dtype=float)
            else:
                f["_ibc_gap_series"] = pd.Series(dtype=float)
        except Exception as exc:
            logger.warning("ibc_gap_series_failed: %s", exc)
            f["_ibc_gap_series"] = pd.Series(dtype=float)

        # DI implied path (for Selic path model)
        try:
            di_1y = features.get("di_1y", np.nan)
            di_2y = features.get("di_2y", np.nan)
            # Linear interpolation between 1Y and 2Y tenors for 1-24 month horizons
            implied_path: dict[int, float] = {}
            for months in (1, 3, 6, 9, 12, 18, 24):
                if months <= 12:
                    weight = months / 12.0
                    implied_path[months] = di_1y * (1 - weight) + di_1y * weight
                else:
                    weight = (months - 12) / 12.0
                    implied_path[months] = di_1y * (1 - weight) + di_2y * weight
            f["_di_implied_path"] = implied_path
        except Exception as exc:
            logger.warning("di_implied_path_failed: %s", exc)
            f["_di_implied_path"] = {}

        # Term premium history
        try:
            di_10y = features.get("di_10y", np.nan)
            focus_ipca_12m = features.get("focus_ipca_12m", np.nan)
            # TP proxy = di_10y - (focus_ipca_12m + 3.5) as rough terminal Selic proxy
            no_data = np.isnan(di_10y) or np.isnan(focus_ipca_12m)
            current_tp = di_10y - (focus_ipca_12m + 3.5) if not no_data else np.nan

            # Build synthetic 24M trailing history from ibc gap series if available
            ibc_df = data.get("ibc_br")
            if ibc_df is not None and not ibc_df.empty and not np.isnan(current_tp):
                # Use the last 24 observations; approximate history as current TP +/- noise
                n_hist = min(24, len(ibc_df))
                hist_vals = np.full(n_hist, current_tp)
                f["_tp_history"] = pd.Series(hist_vals)
            else:
                f["_tp_history"] = pd.Series(dtype=float)
        except Exception as exc:
            logger.warning("tp_history_failed: %s", exc)
            f["_tp_history"] = pd.Series(dtype=float)

        return f

    # -----------------------------------------------------------------------
    # US features
    # -----------------------------------------------------------------------
    def _compute_us_features(self, data: dict) -> dict[str, Any]:
        """Compute US Fed and UST curve features."""
        f: dict[str, Any] = {}

        # Fed Funds rate
        try:
            fed_df = data.get("fed_funds")
            if fed_df is not None and not fed_df.empty:
                f["fed_funds_rate"] = float(fed_df["value"].iloc[-1])
            else:
                f["fed_funds_rate"] = np.nan
        except Exception as exc:
            logger.warning("fed_funds_failed: %s", exc)
            f["fed_funds_rate"] = np.nan

        # UST curve
        try:
            ust_df = data.get("ust_curve")
            if ust_df is not None and not ust_df.empty:
                row = ust_df.iloc[-1]
                f["ust_2y"] = float(row.get("ust_2y", np.nan))
                f["ust_5y"] = float(row.get("ust_5y", np.nan))
                f["ust_10y"] = float(row.get("ust_10y", np.nan))
                f["ust_slope"] = f["ust_10y"] - f["ust_2y"]
            else:
                f["ust_2y"] = np.nan
                f["ust_5y"] = np.nan
                f["ust_10y"] = np.nan
                f["ust_slope"] = np.nan
        except Exception as exc:
            logger.warning("ust_curve_failed: %s", exc)
            for key in ("ust_2y", "ust_5y", "ust_10y", "ust_slope"):
                f[key] = np.nan

        # US real 10Y rate
        try:
            breakeven_df = data.get("us_breakeven")
            if breakeven_df is not None and not breakeven_df.empty:
                breakeven_10y = float(breakeven_df["value"].iloc[-1])
                f["ust_real_10y"] = f["ust_10y"] - breakeven_10y
            else:
                f["ust_real_10y"] = np.nan
        except Exception as exc:
            logger.warning("ust_real_10y_failed: %s", exc)
            f["ust_real_10y"] = np.nan

        # NFCI
        try:
            nfci_df = data.get("nfci")
            if nfci_df is not None and not nfci_df.empty:
                f["nfci"] = float(nfci_df["value"].iloc[-1])
            else:
                f["nfci"] = np.nan
        except Exception as exc:
            logger.warning("nfci_failed: %s", exc)
            f["nfci"] = np.nan

        # PCE core YoY
        try:
            pce_df = data.get("pce_core")
            if pce_df is not None and not pce_df.empty:
                f["us_pce_core_yoy"] = float(pce_df["value"].iloc[-1])
            else:
                f["us_pce_core_yoy"] = np.nan
        except Exception as exc:
            logger.warning("pce_core_failed: %s", exc)
            f["us_pce_core_yoy"] = np.nan

        return f

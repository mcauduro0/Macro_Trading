"""Fiscal feature engine for Brazil macro fiscal analysis.

FiscalFeatureEngine computes debt sustainability metrics, primary balance
dynamics, r-g spread, and CB credibility proxy from point-in-time data.

All computations are guarded with try/except returning np.nan on failure.
Private keys (_dsa_raw_data, _pb_history, _focus_history, _as_of_date)
are written into the output dict for consumption by fiscal model classes.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class FiscalFeatureEngine:
    """Compute Brazil fiscal features from raw point-in-time data.

    Designed to be stateless — instantiate once, call compute() repeatedly
    with different as_of_date values for backtesting.
    """

    # BCB inflation target (%)
    INFLATION_TARGET = 3.0

    def compute(self, data: dict, as_of_date: date) -> dict[str, Any]:
        """Return a flat dict of all fiscal features plus private model keys.

        Args:
            data: Dict of DataFrames keyed by gross_debt, net_debt,
                  primary_balance, gdp_qoq, selic, focus, focus_pib_cy,
                  focus_pib_ny, di_curve.
            as_of_date: Point-in-time reference date.

        Returns:
            Flat feature dict with scalar values and private series keys.
        """
        features: dict[str, Any] = {}

        # ----------------------------------------------------------------
        # Gross debt/GDP
        # ----------------------------------------------------------------
        gross_debt_df = data.get("gross_debt")
        try:
            if gross_debt_df is not None and not gross_debt_df.empty:
                features["gross_debt_gdp"] = float(gross_debt_df["value"].iloc[-1])
            else:
                features["gross_debt_gdp"] = np.nan
        except Exception as exc:
            logger.debug("gross_debt_gdp_failed: %s", exc)
            features["gross_debt_gdp"] = np.nan

        # 12M change in gross debt/GDP
        try:
            if (
                gross_debt_df is not None
                and not gross_debt_df.empty
                and len(gross_debt_df) >= 13
            ):
                series = gross_debt_df["value"].dropna()
                features["debt_gdp_12m_change"] = float(
                    series.iloc[-1] - series.iloc[-13]
                )
            else:
                features["debt_gdp_12m_change"] = np.nan
        except Exception as exc:
            logger.debug("debt_gdp_12m_change_failed: %s", exc)
            features["debt_gdp_12m_change"] = np.nan

        # 12M rolling mean of gross debt/GDP (smoothed level)
        try:
            if gross_debt_df is not None and not gross_debt_df.empty:
                series = gross_debt_df["value"].dropna()
                rolling = series.rolling(12).mean()
                val = rolling.iloc[-1]
                features["debt_gdp_trend"] = float(val) if not np.isnan(val) else np.nan
            else:
                features["debt_gdp_trend"] = np.nan
        except Exception as exc:
            logger.debug("debt_gdp_trend_failed: %s", exc)
            features["debt_gdp_trend"] = np.nan

        # ----------------------------------------------------------------
        # Net debt/GDP
        # ----------------------------------------------------------------
        net_debt_df = data.get("net_debt")
        try:
            if net_debt_df is not None and not net_debt_df.empty:
                features["net_debt_gdp"] = float(net_debt_df["value"].iloc[-1])
            else:
                features["net_debt_gdp"] = np.nan
        except Exception as exc:
            logger.debug("net_debt_gdp_failed: %s", exc)
            features["net_debt_gdp"] = np.nan

        # ----------------------------------------------------------------
        # Primary balance/GDP and history
        # ----------------------------------------------------------------
        primary_balance_df = data.get("primary_balance")
        gdp_qoq_df = data.get("gdp_qoq")

        # Build primary_balance_gdp series (monthly, if possible)
        pb_gdp_series = self._build_pb_gdp_series(primary_balance_df, gdp_qoq_df)

        try:
            if pb_gdp_series is not None and not pb_gdp_series.empty:
                features["primary_balance_gdp"] = float(pb_gdp_series.iloc[-1])
            else:
                features["primary_balance_gdp"] = np.nan
        except Exception as exc:
            logger.debug("primary_balance_gdp_failed: %s", exc)
            features["primary_balance_gdp"] = np.nan

        # 12M change in primary_balance_gdp
        try:
            if pb_gdp_series is not None and len(pb_gdp_series) >= 13:
                features["pb_12m_change"] = float(
                    pb_gdp_series.iloc[-1] - pb_gdp_series.iloc[-13]
                )
            else:
                features["pb_12m_change"] = np.nan
        except Exception as exc:
            logger.debug("pb_12m_change_failed: %s", exc)
            features["pb_12m_change"] = np.nan

        # ----------------------------------------------------------------
        # R-G dynamics
        # ----------------------------------------------------------------
        selic_df = data.get("selic")
        try:
            if selic_df is not None and not selic_df.empty:
                features["r_nominal"] = float(selic_df["value"].iloc[-1])
            else:
                features["r_nominal"] = np.nan
        except Exception as exc:
            logger.debug("r_nominal_failed: %s", exc)
            features["r_nominal"] = np.nan

        # Focus IPCA 12M
        focus_df = data.get("focus")
        try:
            if focus_df is not None and not focus_df.empty:
                features["focus_ipca_12m"] = float(focus_df["value"].iloc[-1])
            else:
                features["focus_ipca_12m"] = np.nan
        except Exception as exc:
            logger.debug("focus_ipca_12m_failed: %s", exc)
            features["focus_ipca_12m"] = np.nan

        # Real Selic: r_nominal - focus_ipca_12m
        try:
            r_nom = features.get("r_nominal", np.nan)
            f_ipca = features.get("focus_ipca_12m", np.nan)
            if not np.isnan(r_nom) and not np.isnan(f_ipca):
                features["r_real"] = r_nom - f_ipca
            else:
                features["r_real"] = np.nan
        except Exception as exc:
            logger.debug("r_real_failed: %s", exc)
            features["r_real"] = np.nan

        # Annualized real GDP growth from trailing 4Q average
        features["g_real"] = self._compute_g_real(gdp_qoq_df)

        # R-G spread
        try:
            r_real = features.get("r_real", np.nan)
            g_real = features.get("g_real", np.nan)
            if not np.isnan(r_real) and not np.isnan(g_real):
                features["r_g_spread"] = r_real - g_real
            else:
                features["r_g_spread"] = np.nan
        except Exception as exc:
            logger.debug("r_g_spread_failed: %s", exc)
            features["r_g_spread"] = np.nan

        # ----------------------------------------------------------------
        # CB credibility proxy
        # ----------------------------------------------------------------
        try:
            f_ipca = features.get("focus_ipca_12m", np.nan)
            if not np.isnan(f_ipca):
                features["focus_ipca_12m_abs_dev"] = abs(f_ipca - self.INFLATION_TARGET)
            else:
                features["focus_ipca_12m_abs_dev"] = np.nan
        except Exception as exc:
            logger.debug("focus_ipca_12m_abs_dev_failed: %s", exc)
            features["focus_ipca_12m_abs_dev"] = np.nan

        # Z-score of deviation over 36M history
        try:
            focus_history = self._build_focus_series(focus_df)
            if focus_history is not None and len(focus_history) >= 12:
                abs_dev_series = (focus_history - self.INFLATION_TARGET).abs()
                rolling_mean = abs_dev_series.rolling(36).mean()
                rolling_std = abs_dev_series.rolling(36).std()
                last_mean = rolling_mean.iloc[-1]
                last_std = rolling_std.iloc[-1]
                last_dev = abs_dev_series.iloc[-1]
                if not np.isnan(last_std) and last_std > 1e-8:
                    features["cb_credibility_zscore"] = float(
                        (last_dev - last_mean) / last_std
                    )
                else:
                    features["cb_credibility_zscore"] = np.nan
            else:
                features["cb_credibility_zscore"] = np.nan
        except Exception as exc:
            logger.debug("cb_credibility_zscore_failed: %s", exc)
            features["cb_credibility_zscore"] = np.nan

        # ----------------------------------------------------------------
        # Focus PIB (GDP growth forecasts)
        # ----------------------------------------------------------------
        g_focus = self._compute_g_focus(data, features.get("g_real", np.nan))
        features["g_focus"] = g_focus

        # ----------------------------------------------------------------
        # Private model keys
        # ----------------------------------------------------------------
        # _dsa_raw_data for DebtSustainabilityModel
        dsa_raw: dict[str, Any] = {
            "debt_gdp": features.get("gross_debt_gdp", np.nan),
            "r_nominal": features.get("r_nominal", np.nan),
            "g_real": features.get("g_real", np.nan),
            "pb_gdp": features.get("primary_balance_gdp", np.nan),
            "r_real": features.get("r_real", np.nan),
            "focus_ipca_12m": features.get("focus_ipca_12m", np.nan),
            "g_focus": g_focus,
        }
        features["_dsa_raw_data"] = dsa_raw

        # _pb_history: pd.Series of monthly pb/GDP values
        features["_pb_history"] = (
            pb_gdp_series if pb_gdp_series is not None else pd.Series(dtype=float)
        )

        # _focus_history: pd.Series of monthly focus_ipca_12m values
        focus_history_series = self._build_focus_series(focus_df)
        features["_focus_history"] = (
            focus_history_series
            if focus_history_series is not None
            else pd.Series(dtype=float)
        )

        # _di_curve: raw dict {tenor_days: rate}
        di_curve = data.get("di_curve")
        if isinstance(di_curve, dict):
            features["_di_curve"] = di_curve
        else:
            features["_di_curve"] = {}

        # _as_of_date
        features["_as_of_date"] = as_of_date

        return features

    # ----------------------------------------------------------------
    # Private helpers
    # ----------------------------------------------------------------
    def _build_pb_gdp_series(
        self,
        primary_balance_df: pd.DataFrame | None,
        gdp_qoq_df: pd.DataFrame | None,
    ) -> pd.Series | None:
        """Build monthly primary balance/GDP series.

        primary_balance_gdp = primary_balance_brl_bn / (gdp_quarterly_brl_bn * 4) * 100

        Returns:
            pd.Series with DatetimeIndex, or None if insufficient data.
        """
        try:
            if primary_balance_df is None or primary_balance_df.empty:
                return None
            if gdp_qoq_df is None or gdp_qoq_df.empty:
                return None

            pb_series = primary_balance_df["value"].dropna()
            gdp_series = gdp_qoq_df["value"].dropna()

            # GDP quarterly QoQ to annualized level estimate:
            # Use the last available quarterly value, annualized = quarterly_value * 4
            # For simplicity, use the latest GDP quarterly value as annualized GDP
            # We forward-fill quarterly GDP to monthly frequency for alignment
            gdp_quarterly = gdp_series.copy()
            # Resample to monthly freq, forward fill
            gdp_monthly = gdp_quarterly.resample("ME").last().ffill()

            # Align on common monthly index
            common_idx = pb_series.index.intersection(gdp_monthly.index)
            if len(common_idx) == 0:
                # Try reindexing
                pb_reindexed = pb_series.resample("ME").last()
                gdp_reindexed = gdp_monthly.reindex(pb_reindexed.index, method="ffill")
                common_idx = pb_reindexed.index
                pb_aligned = pb_reindexed
                gdp_aligned = gdp_reindexed
            else:
                pb_aligned = pb_series.loc[common_idx]
                gdp_aligned = gdp_monthly.loc[common_idx]

            # annualized GDP estimate = quarterly GDP * 4
            gdp_annualized = gdp_aligned * 4

            # Primary balance as % of GDP
            pb_gdp = (pb_aligned / gdp_annualized) * 100

            return pb_gdp.dropna()
        except Exception as exc:
            logger.debug("_build_pb_gdp_series_failed: %s", exc)
            return None

    def _compute_g_real(self, gdp_qoq_df: pd.DataFrame | None) -> float:
        """Compute annualized real GDP growth from trailing 4Q average.

        Formula: trailing 4Q average of (1 + qoq/100)^4 - 1) * 100

        Returns:
            Float annualized growth rate in %, or np.nan.
        """
        try:
            if gdp_qoq_df is None or gdp_qoq_df.empty:
                return np.nan
            series = gdp_qoq_df["value"].dropna()
            if len(series) < 4:
                return np.nan

            last4 = series.iloc[-4:]
            annualized = last4.apply(lambda q: ((1 + q / 100) ** 4 - 1) * 100)
            return float(annualized.mean())
        except Exception as exc:
            logger.debug("_compute_g_real_failed: %s", exc)
            return np.nan

    def _build_focus_series(self, focus_df: pd.DataFrame | None) -> pd.Series | None:
        """Build monthly Focus IPCA 12M series."""
        try:
            if focus_df is None or focus_df.empty:
                return None
            series = focus_df["value"].dropna()
            if series.empty:
                return None
            return series
        except Exception as exc:
            logger.debug("_build_focus_series_failed: %s", exc)
            return None

    def _compute_g_focus(self, data: dict, g_real_fallback: float) -> float:
        """Compute Focus PIB growth forecast average (current year + next year).

        Falls back to g_real if Focus PIB series unavailable.

        Returns:
            Float growth forecast in %, or g_real_fallback.
        """
        try:
            pib_cy_df = data.get("focus_pib_cy")
            pib_ny_df = data.get("focus_pib_ny")

            cy_val: float | None = None
            ny_val: float | None = None

            if pib_cy_df is not None and not isinstance(pib_cy_df, type(None)):
                if hasattr(pib_cy_df, "empty") and not pib_cy_df.empty:
                    cy_val = float(pib_cy_df["value"].iloc[-1])

            if pib_ny_df is not None and not isinstance(pib_ny_df, type(None)):
                if hasattr(pib_ny_df, "empty") and not pib_ny_df.empty:
                    ny_val = float(pib_ny_df["value"].iloc[-1])

            if cy_val is not None and ny_val is not None:
                return (cy_val + ny_val) / 2.0
            if cy_val is not None:
                return cy_val
            if ny_val is not None:
                return ny_val

            return g_real_fallback
        except Exception as exc:
            logger.debug("_compute_g_focus_failed: %s", exc)
            return g_real_fallback

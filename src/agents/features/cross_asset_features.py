"""Cross-asset feature engine -- regime, correlation, and sentiment inputs.

CrossAssetFeatureEngine.compute() produces scalar features and three private
model-level keys (_regime_components, _correlation_pairs, _sentiment_components)
consumed by RegimeDetectionModel, CorrelationAnalysis, and RiskSentimentIndex.

All computations guard with try/except returning np.nan on failure -- never raise.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd


class CrossAssetFeatureEngine:
    """Compute cross-asset features from raw point-in-time data.

    Designed to be called once per agent run.  All private keys are
    prefixed with ``_`` so model classes can distinguish them from
    scalar feature values.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def compute(self, data: dict, as_of_date: date) -> dict[str, Any]:  # noqa: C901
        """Return a flat dict of all cross-asset features plus private model keys.

        Args:
            data: Raw data dict from CrossAssetAgent.load_data().
            as_of_date: Point-in-time reference date.

        Returns:
            Feature dict with scalar keys and private ``_``-prefixed keys.
        """
        features: dict[str, Any] = {}
        features["_as_of_date"] = as_of_date

        # ------------------------------------------------------------------
        # Scalar features
        # ------------------------------------------------------------------
        features["vix_level"] = self._latest_close(data.get("vix"))
        features["vix_zscore_252d"] = self._zscore_252d(data.get("vix"), col="close")

        features["hy_oas_bps"] = self._latest_value(data.get("hy_oas"))
        features["hy_oas_zscore_252d"] = self._zscore_252d(data.get("hy_oas"), col="value")

        features["dxy_level"] = self._latest_close(data.get("dxy"))
        features["dxy_zscore_252d"] = self._zscore_252d(data.get("dxy"), col="close")

        features["ust_slope_bps"] = self._compute_ust_slope(data)
        features["ust_slope_zscore_252d"] = self._compute_ust_slope_zscore(data)

        features["cftc_brl_net"] = self._latest_value(data.get("cftc_brl"))
        features["cftc_brl_zscore"] = self._zscore_52w(data.get("cftc_brl"), col="value")

        features["bcb_flow_net"] = self._latest_value(data.get("bcb_flow"))
        features["bcb_flow_zscore"] = self._zscore_52w(data.get("bcb_flow"), col="value")

        features["di_5y_rate"] = self._extract_di_5y(data.get("di_curve"))
        features["ust_5y_rate"] = self._latest_value(data.get("ust_5y"))

        features["credit_proxy_bps"] = self._compute_credit_proxy(
            features["di_5y_rate"], features["ust_5y_rate"]
        )

        # ------------------------------------------------------------------
        # Private key: _regime_components
        # ------------------------------------------------------------------
        features["_regime_components"] = self._build_regime_components(features)

        # ------------------------------------------------------------------
        # Private key: _correlation_pairs
        # ------------------------------------------------------------------
        features["_correlation_pairs"] = self._build_correlation_pairs(data)

        # ------------------------------------------------------------------
        # Private key: _sentiment_components
        # ------------------------------------------------------------------
        features["_sentiment_components"] = self._build_sentiment_components(features)

        return features

    # ------------------------------------------------------------------
    # Scalar helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _latest_close(df: pd.DataFrame | None) -> float:
        """Extract latest ``close`` value from DataFrame."""
        try:
            if df is not None and not df.empty and "close" in df.columns:
                series = df["close"].dropna()
                if len(series) > 0:
                    return float(series.iloc[-1])
        except Exception:
            pass
        return np.nan

    @staticmethod
    def _latest_value(df: pd.DataFrame | None) -> float:
        """Extract latest ``value`` value from DataFrame."""
        try:
            if df is not None and not df.empty and "value" in df.columns:
                series = df["value"].dropna()
                if len(series) > 0:
                    return float(series.iloc[-1])
        except Exception:
            pass
        return np.nan

    @staticmethod
    def _zscore_252d(df: pd.DataFrame | None, col: str) -> float:
        """Compute z-score of latest value vs trailing 252-day history."""
        try:
            if df is not None and not df.empty and col in df.columns:
                series = df[col].dropna()
                if len(series) >= 252:
                    window = series.iloc[-252:]
                    current = float(window.iloc[-1])
                    hist = window.iloc[:-1]
                    mean = float(hist.mean())
                    std = float(hist.std())
                    if std > 1e-8:
                        return float((current - mean) / std)
        except Exception:
            pass
        return np.nan

    @staticmethod
    def _zscore_52w(df: pd.DataFrame | None, col: str) -> float:
        """Compute z-score of latest value vs trailing 52-week (~252 day) history."""
        try:
            if df is not None and not df.empty and col in df.columns:
                series = df[col].dropna()
                if len(series) >= 52:
                    window = series.iloc[-52:]
                    current = float(window.iloc[-1])
                    hist = window.iloc[:-1]
                    mean = float(hist.mean())
                    std = float(hist.std())
                    if std > 1e-8:
                        return float((current - mean) / std)
        except Exception:
            pass
        return np.nan

    def _compute_ust_slope(self, data: dict) -> float:
        """Compute UST 10Y - 2Y slope in basis points."""
        try:
            ust_10y = self._latest_value(data.get("ust_10y"))
            ust_2y = self._latest_value(data.get("ust_2y"))
            if not np.isnan(ust_10y) and not np.isnan(ust_2y):
                return float((ust_10y - ust_2y) * 100)
        except Exception:
            pass
        return np.nan

    def _compute_ust_slope_zscore(self, data: dict) -> float:
        """Compute z-score of UST slope vs trailing 252-day history."""
        try:
            ust_10y_df = data.get("ust_10y")
            ust_2y_df = data.get("ust_2y")
            if (
                ust_10y_df is not None
                and not ust_10y_df.empty
                and "value" in ust_10y_df.columns
                and ust_2y_df is not None
                and not ust_2y_df.empty
                and "value" in ust_2y_df.columns
            ):
                slope = (ust_10y_df["value"] - ust_2y_df["value"]).dropna() * 100
                if len(slope) >= 252:
                    window = slope.iloc[-252:]
                    current = float(window.iloc[-1])
                    hist = window.iloc[:-1]
                    mean = float(hist.mean())
                    std = float(hist.std())
                    if std > 1e-8:
                        return float((current - mean) / std)
        except Exception:
            pass
        return np.nan

    @staticmethod
    def _extract_di_5y(di_curve: dict | None) -> float:
        """Extract 5Y tenor from DI curve dict (key 1825 or nearest)."""
        try:
            if di_curve and isinstance(di_curve, dict) and len(di_curve) > 0:
                target = 1825
                # Ensure keys are numeric
                numeric_keys = [k for k in di_curve.keys() if isinstance(k, (int, float))]
                if numeric_keys:
                    closest = min(numeric_keys, key=lambda t: abs(t - target))
                    return float(di_curve[closest])
        except Exception:
            pass
        return np.nan

    @staticmethod
    def _compute_credit_proxy(di_5y_rate: float, ust_5y_rate: float) -> float:
        """Credit proxy = (DI 5Y - UST 5Y) * 100 in bps."""
        try:
            if not np.isnan(di_5y_rate) and not np.isnan(ust_5y_rate):
                return float((di_5y_rate - ust_5y_rate) * 100)
        except Exception:
            pass
        return np.nan

    # ------------------------------------------------------------------
    # Private key builders
    # ------------------------------------------------------------------
    def _build_regime_components(self, features: dict) -> dict[str, float]:
        """Build regime component dict (z-scores, direction-corrected for risk-off)."""
        components: dict[str, float] = {}

        # vix: already risk-off when high
        components["vix"] = features.get("vix_zscore_252d", np.nan)

        # hy_oas: risk-off when high
        components["hy_oas"] = features.get("hy_oas_zscore_252d", np.nan)

        # dxy: risk-off when high (strong USD)
        components["dxy"] = features.get("dxy_zscore_252d", np.nan)

        # em_flows: negative of bcb_flow_zscore (outflows = risk-off = positive z)
        bcb_z = features.get("bcb_flow_zscore", np.nan)
        try:
            components["em_flows"] = -bcb_z if not np.isnan(bcb_z) else np.nan
        except Exception:
            components["em_flows"] = np.nan

        # ust_slope: negative of slope zscore (inversion = risk-off = positive z)
        slope_z = features.get("ust_slope_zscore_252d", np.nan)
        try:
            components["ust_slope"] = -slope_z if not np.isnan(slope_z) else np.nan
        except Exception:
            components["ust_slope"] = np.nan

        # br_fiscal: hy_oas_zscore_252d * 0.3 as proxy
        hy_z = features.get("hy_oas_zscore_252d", np.nan)
        try:
            components["br_fiscal"] = hy_z * 0.3 if not np.isnan(hy_z) else np.nan
        except Exception:
            components["br_fiscal"] = np.nan

        return components

    def _build_correlation_pairs(
        self, data: dict
    ) -> dict[str, tuple[pd.Series, pd.Series] | None]:
        """Build correlation pair dict for CorrelationAnalysis."""
        pairs: dict[str, tuple[pd.Series, pd.Series] | None] = {}

        usdbrl_ptax = data.get("usdbrl_ptax")
        dxy = data.get("dxy")
        ibovespa = data.get("ibovespa")
        sp500 = data.get("sp500")
        vix = data.get("vix")
        oil_wti = data.get("oil_wti")
        ust_2y = data.get("ust_2y")

        def _extract_series(
            df: pd.DataFrame | None, col: str
        ) -> pd.Series | None:
            try:
                if df is not None and not df.empty and col in df.columns:
                    s = df[col].dropna()
                    if len(s) > 0:
                        return s
            except Exception:
                pass
            return None

        usdbrl_s = _extract_series(usdbrl_ptax, "close")
        dxy_s = _extract_series(dxy, "close")
        ibov_s = _extract_series(ibovespa, "close")
        sp500_s = _extract_series(sp500, "close")
        vix_s = _extract_series(vix, "close")
        oil_s = _extract_series(oil_wti, "close")
        ust_2y_s = _extract_series(ust_2y, "value")

        # USDBRL_DXY
        if usdbrl_s is not None and dxy_s is not None:
            pairs["USDBRL_DXY"] = (usdbrl_s, dxy_s)
        else:
            pairs["USDBRL_DXY"] = None

        # DI_UST — use ust_2y value as proxy for DI/UST co-movement
        # For DI, try to build a daily series from di_curve if available
        # Otherwise use ust_2y alone (will be None)
        if ust_2y_s is not None and ibov_s is not None:
            # Use IBOV as proxy for DI since DI daily history may not be available
            # This gives us a BR rate proxy correlation
            pairs["DI_UST"] = (ibov_s, ust_2y_s)
        else:
            pairs["DI_UST"] = None

        # IBOV_SP500
        if ibov_s is not None and sp500_s is not None:
            pairs["IBOV_SP500"] = (ibov_s, sp500_s)
        else:
            pairs["IBOV_SP500"] = None

        # USDBRL_VIX
        if usdbrl_s is not None and vix_s is not None:
            pairs["USDBRL_VIX"] = (usdbrl_s, vix_s)
        else:
            pairs["USDBRL_VIX"] = None

        # OIL_BRL (inverted pair)
        if oil_s is not None and usdbrl_s is not None:
            pairs["OIL_BRL"] = (oil_s, usdbrl_s)
        else:
            pairs["OIL_BRL"] = None

        return pairs

    def _build_sentiment_components(self, features: dict) -> dict[str, float]:
        """Build sentiment subscore dict, each mapped to [0, 100]."""
        components: dict[str, float] = {}

        components["vix"] = self._linear_scale(
            features.get("vix_level", np.nan), lo=10, hi=40, invert=True
        )
        components["hy_oas"] = self._linear_scale(
            features.get("hy_oas_bps", np.nan), lo=300, hi=1000, invert=True
        )
        components["dxy"] = self._linear_scale(
            features.get("dxy_level", np.nan), lo=90, hi=115, invert=True
        )
        components["cftc_brl"] = self._linear_scale(
            features.get("cftc_brl_zscore", np.nan), lo=-2, hi=2
        )
        components["em_flows"] = self._linear_scale(
            features.get("bcb_flow_zscore", np.nan), lo=-2, hi=2
        )
        components["credit_proxy"] = self._linear_scale(
            features.get("credit_proxy_bps", np.nan), lo=100, hi=600, invert=True
        )

        return components

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    @staticmethod
    def _linear_scale(
        val: float, lo: float, hi: float, invert: bool = False
    ) -> float:
        """Clamp val to [lo, hi], map to [0, 100], optionally invert.

        Args:
            val: Input value.
            lo: Lower bound.
            hi: Upper bound.
            invert: If True, lo maps to 100 and hi maps to 0.

        Returns:
            Scaled value in [0, 100] or np.nan if input is NaN.
        """
        try:
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return np.nan
            clamped = max(lo, min(hi, float(val)))
            ratio = (clamped - lo) / (hi - lo) if hi != lo else 0.5
            if invert:
                ratio = 1.0 - ratio
            return round(ratio * 100, 4)
        except Exception:
            return np.nan

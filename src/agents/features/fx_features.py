"""FX Equilibrium feature engine — BEER, carry-to-risk, FX flows, CIP basis.

FxFeatureEngine.compute() produces scalar features and private model-level
keys (_beer_ols_data, _ptax_daily, _carry_ratio_history, _flow_combined)
consumed by BeerModel, CarryToRiskModel, FlowModel, and CipBasisModel.

All computations guard with try/except returning np.nan on failure — never raise.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd


class FxFeatureEngine:
    """Compute FX equilibrium features from raw point-in-time data.

    Designed to be called once per agent run.  All private keys are
    prefixed with ``_`` so model classes can distinguish them from
    scalar feature values.
    """

    def compute(self, data: dict, as_of_date: date) -> dict[str, Any]:  # noqa: C901
        """Return a flat dict of all FX features plus private model keys.

        Args:
            data: Raw data dict from FxEquilibriumAgent.load_data().
            as_of_date: Point-in-time reference date.

        Returns:
            Feature dict with scalar keys and private ``_``-prefixed keys.
        """
        features: dict[str, Any] = {}
        features["_as_of_date"] = as_of_date

        # ------------------------------------------------------------------
        # Spot level
        # ------------------------------------------------------------------
        ptax_df = data.get("ptax")
        ptax_close: pd.Series | None = None

        try:
            if ptax_df is not None and not ptax_df.empty and "close" in ptax_df.columns:
                ptax_close = ptax_df["close"].dropna()
                usdbrl_spot = float(ptax_close.iloc[-1])
                features["usdbrl_spot"] = usdbrl_spot
                # YoY
                if len(ptax_close) >= 252:
                    prev_year = float(ptax_close.iloc[-252])
                    if prev_year != 0:
                        features["usdbrl_yoy"] = (usdbrl_spot / prev_year - 1) * 100
                    else:
                        features["usdbrl_yoy"] = np.nan
                else:
                    features["usdbrl_yoy"] = np.nan
            else:
                features["usdbrl_spot"] = np.nan
                features["usdbrl_yoy"] = np.nan
        except Exception:
            features["usdbrl_spot"] = np.nan
            features["usdbrl_yoy"] = np.nan

        # ------------------------------------------------------------------
        # Carry fundamentals
        # ------------------------------------------------------------------
        try:
            selic_df = data.get("selic")
            selic_rate = np.nan
            if (
                selic_df is not None
                and not selic_df.empty
                and "value" in selic_df.columns
            ):
                selic_rate = float(selic_df["value"].dropna().iloc[-1])
            features["selic_rate"] = selic_rate
        except Exception:
            features["selic_rate"] = np.nan

        try:
            ff_df = data.get("fed_funds")
            fed_funds_rate = np.nan
            if ff_df is not None and not ff_df.empty and "value" in ff_df.columns:
                fed_funds_rate = float(ff_df["value"].dropna().iloc[-1])
            features["fed_funds_rate"] = fed_funds_rate
        except Exception:
            features["fed_funds_rate"] = np.nan

        # Raw carry differential
        try:
            if not np.isnan(features["selic_rate"]) and not np.isnan(
                features["fed_funds_rate"]
            ):
                features["carry_raw"] = (
                    features["selic_rate"] - features["fed_funds_rate"]
                )
            else:
                features["carry_raw"] = np.nan
        except Exception:
            features["carry_raw"] = np.nan

        # 30-day realized USDBRL vol (annualized %)
        try:
            vol_30d = np.nan
            if ptax_close is not None and len(ptax_close) >= 31:
                daily_returns = ptax_close.pct_change().dropna()
                vol_30d = float(
                    daily_returns.rolling(30).std().iloc[-1] * np.sqrt(252) * 100
                )
            features["vol_30d_realized"] = vol_30d
        except Exception:
            features["vol_30d_realized"] = np.nan

        # Carry-to-risk ratio
        try:
            if (
                not np.isnan(features["carry_raw"])
                and not np.isnan(features["vol_30d_realized"])
                and features["vol_30d_realized"] != 0
            ):
                features["carry_to_risk_ratio"] = (
                    features["carry_raw"] / features["vol_30d_realized"]
                )
            else:
                features["carry_to_risk_ratio"] = np.nan
        except Exception:
            features["carry_to_risk_ratio"] = np.nan

        # ------------------------------------------------------------------
        # BEER inputs (monthly, 2010-present)
        # ------------------------------------------------------------------
        try:
            # real_rate_diff: DI 5Y real − UST 5Y real
            di_curve_hist = data.get("di_curve_history")
            ust_5y_hist = data.get("ust_5y_history")
            focus_ipca_df = data.get("focus_ipca")

            di_5y_series: pd.Series | None = None
            if (
                di_curve_hist is not None
                and not di_curve_hist.empty
                and "rate" in di_curve_hist.columns
            ):
                _s = di_curve_hist["rate"].copy()
                _s.index = self._tz_naive(_s.index)
                raw = _s.resample("ME").last()
                # Curve rates may be decimal (0.135) — convert to pct if needed
                di_5y_series = (
                    raw * 100.0 if (len(raw) > 0 and raw.max() < 1.0) else raw
                )

            ust_5y_series: pd.Series | None = None
            if (
                ust_5y_hist is not None
                and not ust_5y_hist.empty
                and "rate" in ust_5y_hist.columns
            ):
                _s = ust_5y_hist["rate"].copy()
                _s.index = self._tz_naive(_s.index)
                raw = _s.resample("ME").last()
                ust_5y_series = (
                    raw * 100.0 if (len(raw) > 0 and raw.max() < 1.0) else raw
                )

            focus_ipca_series: pd.Series | None = None
            if (
                focus_ipca_df is not None
                and not focus_ipca_df.empty
                and "value" in focus_ipca_df.columns
            ):
                _s = focus_ipca_df["value"].copy()
                _s.index = self._tz_naive(_s.index)
                focus_ipca_series = _s.resample("ME").last()

            if (
                di_5y_series is not None
                and ust_5y_series is not None
                and focus_ipca_series is not None
            ):
                real_br = di_5y_series - focus_ipca_series
                real_us = ust_5y_series - focus_ipca_series * 0.4  # rough US PCE proxy
                real_rate_diff = (real_br - real_us).dropna()
                features["real_rate_diff"] = (
                    float(real_rate_diff.iloc[-1]) if len(real_rate_diff) else np.nan
                )
            else:
                features["real_rate_diff"] = np.nan
        except Exception:
            features["real_rate_diff"] = np.nan

        try:
            fx_res_df = data.get("fx_reserves")
            nfa_proxy = np.nan
            if (
                fx_res_df is not None
                and not fx_res_df.empty
                and "value" in fx_res_df.columns
            ):
                latest_res = float(fx_res_df["value"].dropna().iloc[-1])
                if latest_res > 0:
                    nfa_proxy = float(np.log(latest_res))
            features["nfa_proxy"] = nfa_proxy
        except Exception:
            features["nfa_proxy"] = np.nan

        try:
            tb_df = data.get("trade_balance")
            tot_proxy = np.nan
            if tb_df is not None and not tb_df.empty and "value" in tb_df.columns:
                tb_series = tb_df["value"].dropna()
                if len(tb_series) >= 12:
                    tot_proxy = float(
                        (tb_series.iloc[-1] / tb_series.iloc[-12] - 1) * 100
                    )
            features["tot_proxy"] = tot_proxy
        except Exception:
            features["tot_proxy"] = np.nan

        try:
            focus_cambio_df = data.get("focus_cambio")
            usdbrl_spot = features.get("usdbrl_spot", np.nan)
            usdbrl_yoy = features.get("usdbrl_yoy", np.nan)
            di_curve_dict = data.get("di_curve") or {}

            # DI 1Y from curve dict — convert decimal to percentage if needed
            di_1y = np.nan
            if di_curve_dict:
                target = 252
                try:
                    closest = min(di_curve_dict.keys(), key=lambda t: abs(t - target))
                    raw_rate = float(di_curve_dict[closest])
                    # Curve rates are decimal (0.135 = 13.5%); other rates are pct
                    di_1y = raw_rate * 100.0 if raw_rate < 1.0 else raw_rate
                except Exception:
                    di_1y = np.nan
            features["_di_1y_rate"] = di_1y

            # Expected depreciation from Focus Câmbio 12M
            expected_dep = np.nan
            if (
                focus_cambio_df is not None
                and not focus_cambio_df.empty
                and "value" in focus_cambio_df.columns
                and not np.isnan(usdbrl_spot)
                and usdbrl_spot != 0
            ):
                focus_cambio_val = float(focus_cambio_df["value"].dropna().iloc[-1])
                expected_dep = (focus_cambio_val - usdbrl_spot) / usdbrl_spot * 100
            else:
                # Fallback: use trailing realized depreciation
                if not np.isnan(usdbrl_yoy):
                    expected_dep = usdbrl_yoy

            # CIP basis: di_1y - (fed_funds + expected_dep)
            fed_funds_rate = features.get("fed_funds_rate", np.nan)
            if (
                not np.isnan(di_1y)
                and not np.isnan(fed_funds_rate)
                and not np.isnan(expected_dep)
            ):
                features["cip_basis"] = di_1y - (fed_funds_rate + expected_dep)
            else:
                features["cip_basis"] = np.nan
        except Exception:
            features["cip_basis"] = np.nan
            features["_di_1y_rate"] = np.nan

        # SOFR rate
        try:
            sofr_df = data.get("sofr")
            sofr_rate = np.nan
            if sofr_df is not None and not sofr_df.empty and "value" in sofr_df.columns:
                sofr_rate = float(sofr_df["value"].dropna().iloc[-1])
            if np.isnan(sofr_rate):
                sofr_rate = features.get("fed_funds_rate", np.nan)
            features["_sofr_rate"] = sofr_rate
        except Exception:
            features["_sofr_rate"] = features.get("fed_funds_rate", np.nan)

        # ------------------------------------------------------------------
        # Private key: _ptax_daily
        # ------------------------------------------------------------------
        try:
            if ptax_close is not None and len(ptax_close) > 0:
                features["_ptax_daily"] = ptax_close.copy()
            else:
                features["_ptax_daily"] = pd.Series(dtype=float)
        except Exception:
            features["_ptax_daily"] = pd.Series(dtype=float)

        # ------------------------------------------------------------------
        # Private key: _beer_ols_data (monthly DataFrame)
        # ------------------------------------------------------------------
        try:
            features["_beer_ols_data"] = self._build_beer_ols_data(data, features)
        except Exception:
            features["_beer_ols_data"] = pd.DataFrame()

        # ------------------------------------------------------------------
        # Private key: _carry_ratio_history (monthly pd.Series)
        # ------------------------------------------------------------------
        try:
            features["_carry_ratio_history"] = self._build_carry_ratio_history(data)
        except Exception:
            features["_carry_ratio_history"] = pd.Series(dtype=float)

        # ------------------------------------------------------------------
        # Private key: _flow_combined (DataFrame)
        # ------------------------------------------------------------------
        try:
            features["_flow_combined"] = self._build_flow_combined(data)
        except Exception:
            features["_flow_combined"] = pd.DataFrame(
                columns=["bcb_flow_zscore", "cftc_zscore"]
            )

        return features

    # ------------------------------------------------------------------
    # Private builders
    # ------------------------------------------------------------------

    def _build_beer_ols_data(self, data: dict, features: dict) -> pd.DataFrame:
        """Build monthly OLS input DataFrame for BeerModel."""
        ptax_df = data.get("ptax")
        if ptax_df is None or ptax_df.empty or "close" not in ptax_df.columns:
            return pd.DataFrame()

        # Monthly USDBRL close (normalize tz)
        ptax_close = ptax_df["close"].copy()
        ptax_close.index = self._tz_naive(ptax_close.index)
        monthly_usdbrl = ptax_close.resample("ME").last().dropna()
        if monthly_usdbrl.empty:
            return pd.DataFrame()

        df = pd.DataFrame({"log_usdbrl": np.log(monthly_usdbrl)})

        # tot_proxy: monthly TB values (already computed above, rebuild as series)
        tb_df = data.get("trade_balance")
        if tb_df is not None and not tb_df.empty and "value" in tb_df.columns:
            tb_val = tb_df["value"].copy()
            tb_val.index = self._tz_naive(tb_val.index)
            tb_monthly = tb_val.resample("ME").last()
            tb_pct = tb_monthly.pct_change(12) * 100
            df = df.join(tb_pct.rename("tot_proxy"), how="left")

        # real_rate_diff: monthly
        di_hist = data.get("di_curve_history")
        ust_hist = data.get("ust_5y_history")
        focus_ipca_df = data.get("focus_ipca")
        if (
            di_hist is not None
            and not di_hist.empty
            and "rate" in di_hist.columns
            and ust_hist is not None
            and not ust_hist.empty
            and "rate" in ust_hist.columns
            and focus_ipca_df is not None
            and not focus_ipca_df.empty
            and "value" in focus_ipca_df.columns
        ):
            di_s = di_hist["rate"].copy()
            di_s.index = self._tz_naive(di_s.index)
            di_m = di_s.resample("ME").last()
            ust_s = ust_hist["rate"].copy()
            ust_s.index = self._tz_naive(ust_s.index)
            ust_m = ust_s.resample("ME").last()
            ipca_s = focus_ipca_df["value"].copy()
            ipca_s.index = self._tz_naive(ipca_s.index)
            ipca_m = ipca_s.resample("ME").last()
            rrd = (di_m - ipca_m) - (ust_m - ipca_m * 0.4)
            df = df.join(rrd.rename("real_rate_diff"), how="left")

        # nfa_proxy: log(fx_reserves)
        fx_res_df = data.get("fx_reserves")
        if (
            fx_res_df is not None
            and not fx_res_df.empty
            and "value" in fx_res_df.columns
        ):
            res_val = fx_res_df["value"].copy()
            res_val.index = self._tz_naive(res_val.index)
            res_m = res_val.resample("ME").last()
            nfa = res_m[res_m > 0].apply(np.log)
            df = df.join(nfa.rename("nfa_proxy"), how="left")

        # Filter to 2010-present (restrict start date for BEER)
        df = df[df.index >= "2010-01-01"]
        # Drop rows where log_usdbrl is NaN
        df = df[df["log_usdbrl"].notna()]

        return df

    @staticmethod
    def _tz_naive(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
        """Strip timezone info so all indices align."""
        return idx.tz_localize(None) if idx.tz is not None else idx

    def _build_carry_ratio_history(self, data: dict) -> pd.Series:
        """Build monthly carry-to-risk ratio series for CarryToRiskModel."""
        ptax_df = data.get("ptax")
        selic_df = data.get("selic")
        ff_df = data.get("fed_funds")

        if ptax_df is None or ptax_df.empty or "close" not in ptax_df.columns:
            return pd.Series(dtype=float)

        ptax_close = ptax_df["close"].dropna()
        ptax_close.index = self._tz_naive(ptax_close.index)
        if len(ptax_close) < 31:
            return pd.Series(dtype=float)

        # Daily vol, resampled to monthly
        daily_returns = ptax_close.pct_change().dropna()
        rolling_vol = daily_returns.rolling(30).std() * np.sqrt(252) * 100
        monthly_vol = rolling_vol.resample("ME").last().dropna()

        # Monthly selic and fed_funds (normalize tz)
        selic_m: pd.Series | None = None
        if selic_df is not None and not selic_df.empty and "value" in selic_df.columns:
            s = selic_df["value"].copy()
            s.index = self._tz_naive(s.index)
            selic_m = s.resample("ME").last()

        ff_m: pd.Series | None = None
        if ff_df is not None and not ff_df.empty and "value" in ff_df.columns:
            f = ff_df["value"].copy()
            f.index = self._tz_naive(f.index)
            ff_m = f.resample("ME").last()

        if selic_m is None or ff_m is None:
            return pd.Series(dtype=float)

        carry_m = (selic_m - ff_m).dropna()
        ratio = carry_m / monthly_vol
        ratio = ratio.dropna()
        return ratio

    def _build_flow_combined(self, data: dict) -> pd.DataFrame:
        """Build combined FX flow DataFrame for FlowModel."""
        bcb_df = data.get("bcb_flow")
        cftc_df = data.get("cftc_brl")
        # BCB flow z-score (24M)
        bcb_z: pd.Series
        if bcb_df is not None and not bcb_df.empty and "value" in bcb_df.columns:
            _v = bcb_df["value"].copy()
            _v.index = self._tz_naive(_v.index)
            bcb_val = _v.resample("ME").sum()
            roll_mean = bcb_val.rolling(24).mean()
            roll_std = bcb_val.rolling(24).std()
            std_safe = roll_std.replace(0, np.nan)
            bcb_z = ((bcb_val - roll_mean) / std_safe).fillna(0.0)
        else:
            # No data — use 0.0 placeholder with single row
            idx = pd.DatetimeIndex([pd.Timestamp.now().normalize()])
            bcb_z = pd.Series([np.nan], index=idx)
        # CFTC z-score (24M)
        cftc_z: pd.Series
        if cftc_df is not None and not cftc_df.empty and "value" in cftc_df.columns:
            _v = cftc_df["value"].copy()
            _v.index = self._tz_naive(_v.index)
            cftc_val = _v.resample("ME").last()
            roll_mean_c = cftc_val.rolling(24).mean()
            roll_std_c = cftc_val.rolling(24).std()
            std_safe_c = roll_std_c.replace(0, np.nan)
            cftc_z = ((cftc_val - roll_mean_c) / std_safe_c).fillna(0.0)
        else:
            idx = pd.DatetimeIndex([pd.Timestamp.now().normalize()])
            cftc_z = pd.Series([np.nan], index=idx)
        combined = pd.DataFrame({"bcb_flow_zscore": bcb_z, "cftc_zscore": cftc_z})
        return combined

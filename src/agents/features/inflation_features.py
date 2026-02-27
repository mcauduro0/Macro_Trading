"""Inflation feature engine for the InflationAgent.

InflationFeatureEngine.compute() takes a pre-loaded data dict and an
as_of_date, then returns a flat dict of 30+ Brazilian and 15+ US
inflation features.  Every computation is guarded: missing or empty
series produce np.nan rather than raising exceptions.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from statsmodels.tsa.filters.hp_filter import hpfilter


class InflationFeatureEngine:
    """Compute inflation features from raw point-in-time data.

    All methods are stateless; no DB access happens here.  The caller
    (InflationAgent.compute_features) is responsible for passing a fully
    populated ``data`` dict.

    Data dict expected keys
    -----------------------
    data["ipca"]              DataFrame: IPCA headline MoM monthly
    data["ipca_cores"]        dict: {"smoothed": df, "trimmed": df, "ex_fe": df}
    data["ipca_components"]   dict of 9 component DataFrames (MoM)
    data["focus"]             DataFrame: Focus expectations
    data["ibc_br"]            DataFrame: IBC-Br monthly activity index
    data["usdbrl"]            DataFrame: USDBRL daily from market_data
    data["crb"]               DataFrame: CRB commodity index from market_data
    data["us_cpi"]            DataFrame: US CPI core
    data["us_pce"]            DataFrame: US PCE core
    data["us_breakevens"]     DataFrame: breakeven inflation (5Y, 10Y)
    data["us_michigan"]       DataFrame: Michigan survey (1Y, 5Y)
    data["us_pce_supercore"]  DataFrame or None: PCE services ex-housing
    data["ipca_services"]     DataFrame: services IPCA sub-index
    data["ipca_industrial"]   DataFrame: industrial goods IPCA sub-index
    data["ipca_diffusion"]    DataFrame or None: diffusion index
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def compute(self, data: dict, as_of_date: date) -> dict[str, Any]:
        """Return a flat dict of all inflation features.

        Args:
            data: Dict of DataFrames/sub-dicts keyed by series type.
            as_of_date: Point-in-time reference date (for documentation).

        Returns:
            Flat dict mapping feature name -> scalar (float or np.nan).
        """
        features: dict[str, Any] = {}

        features.update(self._br_ipca_headline(data))
        features.update(self._br_ipca_cores(data))
        features.update(self._br_ipca_components(data))
        features.update(self._br_ipca_sub_indices(data))
        features.update(self._br_ipca_diffusion(data))
        features.update(self._br_focus(data))
        features.update(self._br_activity(data))
        features.update(self._br_fx_passthrough(data))
        features.update(self._br_commodity(data))
        features.update(self._us_cpi_pce(data))
        features.update(self._us_breakevens(data))
        features.update(self._us_michigan(data))
        features.update(self._us_supercore(data))
        features.update(self._us_pce_target_gap(features))

        # Private keys used by model classes (prepared aggregates)
        features["_raw_ols_data"] = self._build_ols_data(data, features)
        features["_raw_components"] = self._build_component_data(data)

        return features

    # ------------------------------------------------------------------
    # BR — IPCA headline
    # ------------------------------------------------------------------
    def _br_ipca_headline(self, data: dict) -> dict[str, Any]:
        out: dict[str, Any] = {"ipca_yoy": np.nan, "ipca_mom": np.nan}
        df = data.get("ipca")
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return out

        val_col = self._value_col(df)
        series = df[val_col].dropna()
        if series.empty:
            return out

        out["ipca_mom"] = float(series.iloc[-1])
        # YoY: compounded 12M cumulative  ((1+r1/100)*...*(1+r12/100) - 1)*100
        if len(series) >= 12:
            last12 = series.iloc[-12:]
            yoy = (np.prod(1.0 + last12.values / 100.0) - 1.0) * 100.0
            out["ipca_yoy"] = float(yoy)

        return out

    # ------------------------------------------------------------------
    # BR — IPCA cores
    # ------------------------------------------------------------------
    def _br_ipca_cores(self, data: dict) -> dict[str, Any]:
        out: dict[str, Any] = {
            "ipca_core_smoothed": np.nan,
            "ipca_core_trimmed_mean": np.nan,
            "ipca_core_ex_food_energy": np.nan,
        }
        cores = data.get("ipca_cores")
        if not isinstance(cores, dict):
            return out

        mapping = {
            "smoothed": "ipca_core_smoothed",
            "trimmed": "ipca_core_trimmed_mean",
            "ex_fe": "ipca_core_ex_food_energy",
        }
        for key, feat in mapping.items():
            df = cores.get(key)
            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                continue
            val_col = self._value_col(df)
            series = df[val_col].dropna()
            if series.empty:
                continue
            # YoY: compounded 12M
            if len(series) >= 12:
                last12 = series.iloc[-12:]
                yoy = (np.prod(1.0 + last12.values / 100.0) - 1.0) * 100.0
                out[feat] = float(yoy)
            else:
                out[feat] = float(series.iloc[-1])

        return out

    # ------------------------------------------------------------------
    # BR — IPCA 9 components (MoM)
    # ------------------------------------------------------------------
    _COMPONENT_KEYS = [
        "food_home",
        "food_away",
        "housing",
        "clothing",
        "health",
        "personal_care",
        "education",
        "transport",
        "communication",
    ]

    def _br_ipca_components(self, data: dict) -> dict[str, Any]:
        out: dict[str, Any] = {f"ipca_{k}_mom": np.nan for k in self._COMPONENT_KEYS}
        components = data.get("ipca_components")
        if not isinstance(components, dict):
            return out

        for key in self._COMPONENT_KEYS:
            df = components.get(key)
            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                continue
            val_col = self._value_col(df)
            series = df[val_col].dropna()
            if not series.empty:
                out[f"ipca_{key}_mom"] = float(series.iloc[-1])

        return out

    # ------------------------------------------------------------------
    # BR — Services and industrial sub-indices (YoY)
    # ------------------------------------------------------------------
    def _br_ipca_sub_indices(self, data: dict) -> dict[str, Any]:
        out: dict[str, Any] = {
            "ipca_services_yoy": np.nan,
            "ipca_industrial_yoy": np.nan,
        }
        for feat, key in [
            ("ipca_services_yoy", "ipca_services"),
            ("ipca_industrial_yoy", "ipca_industrial"),
        ]:
            df = data.get(key)
            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                continue
            val_col = self._value_col(df)
            series = df[val_col].dropna()
            if len(series) >= 12:
                last12 = series.iloc[-12:]
                yoy = (np.prod(1.0 + last12.values / 100.0) - 1.0) * 100.0
                out[feat] = float(yoy)
            elif not series.empty:
                out[feat] = float(series.iloc[-1])

        return out

    # ------------------------------------------------------------------
    # BR — Diffusion index
    # ------------------------------------------------------------------
    def _br_ipca_diffusion(self, data: dict) -> dict[str, Any]:
        out: dict[str, Any] = {"ipca_diffusion": np.nan}
        df = data.get("ipca_diffusion")
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            # Proxy: % of 9 components with positive latest MoM
            comps = data.get("ipca_components")
            if isinstance(comps, dict) and comps:
                positives = 0
                total = 0
                for key in self._COMPONENT_KEYS:
                    cdf = comps.get(key)
                    if cdf is None or not isinstance(cdf, pd.DataFrame) or cdf.empty:
                        continue
                    val_col = self._value_col(cdf)
                    series = cdf[val_col].dropna()
                    if not series.empty:
                        total += 1
                        if series.iloc[-1] > 0:
                            positives += 1
                if total > 0:
                    out["ipca_diffusion"] = float(positives / total * 100.0)
            return out

        val_col = self._value_col(df)
        series = df[val_col].dropna()
        if not series.empty:
            out["ipca_diffusion"] = float(series.iloc[-1])

        return out

    # ------------------------------------------------------------------
    # BR — Focus survey expectations
    # ------------------------------------------------------------------
    def _br_focus(self, data: dict) -> dict[str, Any]:
        out: dict[str, Any] = {
            "focus_ipca_12m": np.nan,
            "focus_ipca_eoy": np.nan,
        }
        df = data.get("focus")
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return out

        # Focus DataFrame may have multiple columns (12m, eoy); handle both
        cols = list(df.columns)
        val_col = self._value_col(df)
        series = df[val_col].dropna()
        if not series.empty:
            out["focus_ipca_12m"] = float(series.iloc[-1])

        # If there's a second column, use it for eoy
        other_cols = [c for c in cols if c != val_col and c not in ("date", "release_time", "revision_number")]
        if other_cols:
            eoy_series = df[other_cols[0]].dropna()
            if not eoy_series.empty:
                out["focus_ipca_eoy"] = float(eoy_series.iloc[-1])

        return out

    # ------------------------------------------------------------------
    # BR — Activity / output gap
    # ------------------------------------------------------------------
    def _br_activity(self, data: dict) -> dict[str, Any]:
        out: dict[str, Any] = {
            "ibc_br_level": np.nan,
            "ibc_br_trend": np.nan,
            "ibc_br_output_gap": np.nan,
        }
        df = data.get("ibc_br")
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return out

        val_col = self._value_col(df)
        series = df[val_col].dropna()
        if series.empty:
            return out

        out["ibc_br_level"] = float(series.iloc[-1])

        # HP filter requires at least 13 observations for lambda=1600 (monthly)
        if len(series) >= 13:
            try:
                _cycle, trend = hpfilter(series, lamb=1600)
                trend_val = float(trend.iloc[-1])
                level_val = out["ibc_br_level"]
                out["ibc_br_trend"] = trend_val
                if trend_val != 0:
                    out["ibc_br_output_gap"] = (level_val - trend_val) / trend_val * 100.0
            except Exception:
                pass

        return out

    # ------------------------------------------------------------------
    # BR — FX passthrough
    # ------------------------------------------------------------------
    def _br_fx_passthrough(self, data: dict) -> dict[str, Any]:
        out: dict[str, Any] = {"usdbrl_yoy": np.nan, "usdbrl_3m": np.nan}
        df = data.get("usdbrl")
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return out

        # Use 'close' or 'adjusted_close' column if from market_data
        price_col = None
        for col in ("adjusted_close", "close", "value"):
            if col in df.columns:
                price_col = col
                break
        if price_col is None:
            return out

        series = df[price_col].dropna()
        if series.empty:
            return out

        latest = float(series.iloc[-1])

        # YoY: ~252 trading days back
        if len(series) >= 252:
            past_yoy = float(series.iloc[-252])
            if past_yoy != 0:
                out["usdbrl_yoy"] = (latest / past_yoy - 1.0) * 100.0

        # 3M: ~63 trading days back
        if len(series) >= 63:
            past_3m = float(series.iloc[-63])
            if past_3m != 0:
                out["usdbrl_3m"] = (latest / past_3m - 1.0) * 100.0

        return out

    # ------------------------------------------------------------------
    # BR — Commodity driver
    # ------------------------------------------------------------------
    def _br_commodity(self, data: dict) -> dict[str, Any]:
        out: dict[str, Any] = {"crb_yoy": np.nan}
        df = data.get("crb")
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return out

        price_col = None
        for col in ("adjusted_close", "close", "value"):
            if col in df.columns:
                price_col = col
                break
        if price_col is None:
            return out

        series = df[price_col].dropna()
        if len(series) >= 252:
            latest = float(series.iloc[-1])
            past = float(series.iloc[-252])
            if past != 0:
                out["crb_yoy"] = (latest / past - 1.0) * 100.0

        return out

    # ------------------------------------------------------------------
    # US — CPI and PCE
    # ------------------------------------------------------------------
    def _us_cpi_pce(self, data: dict) -> dict[str, Any]:
        out: dict[str, Any] = {
            "us_cpi_core_yoy": np.nan,
            "us_pce_core_yoy": np.nan,
            "us_pce_core_3m_saar": np.nan,
        }

        # CPI core YoY (index-based series from FRED)
        cpi_df = data.get("us_cpi")
        if cpi_df is not None and isinstance(cpi_df, pd.DataFrame) and not cpi_df.empty:
            val_col = self._value_col(cpi_df)
            series = cpi_df[val_col].dropna()
            if len(series) >= 13:
                latest = float(series.iloc[-1])
                past = float(series.iloc[-13])  # 12 months ago (index value)
                if past != 0:
                    out["us_cpi_core_yoy"] = (latest / past - 1.0) * 100.0
            elif len(series) >= 12:
                # Treat as MoM series
                last12 = series.iloc[-12:]
                yoy = (np.prod(1.0 + last12.values / 100.0) - 1.0) * 100.0
                out["us_cpi_core_yoy"] = float(yoy)

        # PCE core YoY and 3M SAAR
        pce_df = data.get("us_pce")
        if pce_df is not None and isinstance(pce_df, pd.DataFrame) and not pce_df.empty:
            val_col = self._value_col(pce_df)
            series = pce_df[val_col].dropna()
            if len(series) >= 13:
                latest = float(series.iloc[-1])
                past = float(series.iloc[-13])
                if past != 0:
                    out["us_pce_core_yoy"] = (latest / past - 1.0) * 100.0

            # 3M SAAR: annualize the 3M compounded return
            # Use MoM changes (% change month-over-month)
            if len(series) >= 4:
                mom_series = series.pct_change().dropna()
                if len(mom_series) >= 3:
                    last3 = mom_series.iloc[-3:]
                    compounded_3m = np.prod(1.0 + last3.values)
                    saar = (compounded_3m**4 - 1.0) * 100.0
                    out["us_pce_core_3m_saar"] = float(saar)

        return out

    # ------------------------------------------------------------------
    # US — Breakevens
    # ------------------------------------------------------------------
    def _us_breakevens(self, data: dict) -> dict[str, Any]:
        out: dict[str, Any] = {
            "us_breakeven_5y": np.nan,
            "us_breakeven_10y": np.nan,
        }
        df = data.get("us_breakevens")
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return out

        cols = list(df.columns)
        # Expect columns named by tenor, or use first two numeric columns
        col_5y = next((c for c in cols if "5" in str(c)), None)
        col_10y = next((c for c in cols if "10" in str(c)), None)

        # Fallback: use positional columns
        numeric_cols = [c for c in cols if c not in ("date", "release_time", "revision_number")]
        if col_5y is None and len(numeric_cols) >= 1:
            col_5y = numeric_cols[0]
        if col_10y is None and len(numeric_cols) >= 2:
            col_10y = numeric_cols[1]

        if col_5y is not None:
            series = df[col_5y].dropna()
            if not series.empty:
                out["us_breakeven_5y"] = float(series.iloc[-1])

        if col_10y is not None:
            series = df[col_10y].dropna()
            if not series.empty:
                out["us_breakeven_10y"] = float(series.iloc[-1])

        return out

    # ------------------------------------------------------------------
    # US — Michigan survey
    # ------------------------------------------------------------------
    def _us_michigan(self, data: dict) -> dict[str, Any]:
        out: dict[str, Any] = {
            "us_michigan_1y": np.nan,
            "us_michigan_5y": np.nan,
        }
        df = data.get("us_michigan")
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return out

        cols = [c for c in df.columns if c not in ("date", "release_time", "revision_number")]
        col_1y = next((c for c in cols if "1" in str(c) or "1y" in str(c).lower()), None)
        col_5y = next((c for c in cols if "5" in str(c) or "5y" in str(c).lower()), None)

        if col_1y is None and len(cols) >= 1:
            col_1y = cols[0]
        if col_5y is None and len(cols) >= 2:
            col_5y = cols[1]

        if col_1y is not None:
            s = df[col_1y].dropna()
            if not s.empty:
                out["us_michigan_1y"] = float(s.iloc[-1])

        if col_5y is not None:
            s = df[col_5y].dropna()
            if not s.empty:
                out["us_michigan_5y"] = float(s.iloc[-1])

        return out

    # ------------------------------------------------------------------
    # US — Supercore PCE
    # ------------------------------------------------------------------
    def _us_supercore(self, data: dict) -> dict[str, Any]:
        out: dict[str, Any] = {
            "us_pce_supercore_yoy": np.nan,
            "us_pce_supercore_mom_3m": np.nan,
        }
        df = data.get("us_pce_supercore")
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return out

        val_col = self._value_col(df)
        series = df[val_col].dropna()
        if series.empty:
            return out

        # YoY
        if len(series) >= 13:
            latest = float(series.iloc[-1])
            past = float(series.iloc[-13])
            if past != 0:
                out["us_pce_supercore_yoy"] = (latest / past - 1.0) * 100.0

        # 3M average MoM
        if len(series) >= 4:
            mom = series.pct_change().dropna() * 100.0
            if len(mom) >= 3:
                out["us_pce_supercore_mom_3m"] = float(mom.iloc[-3:].mean())

        return out

    # ------------------------------------------------------------------
    # US — PCE target gap
    # ------------------------------------------------------------------
    def _us_pce_target_gap(self, features: dict) -> dict[str, Any]:
        pce_yoy = features.get("us_pce_core_yoy", np.nan)
        if pd.isna(pce_yoy):
            return {"us_pce_target_gap": np.nan}
        return {"us_pce_target_gap": float(pce_yoy) - 2.0}

    # ------------------------------------------------------------------
    # Private key: OLS data for PhillipsCurveModel
    # ------------------------------------------------------------------
    def _build_ols_data(self, data: dict, features: dict) -> pd.DataFrame:
        """Assemble a monthly DataFrame for the OLS Phillips Curve model.

        Columns: core_yoy, expectations_12m, output_gap, usdbrl_yoy, crb_yoy.
        Uses the IPCA core smoothed series as the dependent variable.
        """
        try:
            # Build a monthly date-indexed DataFrame
            records: dict[pd.Timestamp, dict] = {}

            # Dependent: core inflation MoM -> compute rolling 12M YoY
            # Priority: smoothed P55 (BCB-4466) > trimmed mean (BCB-11427) > ex-F&E (BCB-16122)
            cores = data.get("ipca_cores")
            core_series: pd.Series | None = None
            if isinstance(cores, dict):
                for core_key in ("smoothed", "trimmed", "ex_fe"):
                    core_df = cores.get(core_key)
                    if core_df is not None and isinstance(core_df, pd.DataFrame) and not core_df.empty:
                        val_col = self._value_col(core_df)
                        candidate = core_df[val_col].dropna()
                        if len(candidate) >= 12:
                            core_series = candidate
                            break

            if core_series is not None:
                s = core_series
                for i in range(12, len(s) + 1):
                    window = s.iloc[i - 12 : i]
                    yoy = (np.prod(1.0 + window.values / 100.0) - 1.0) * 100.0
                    ts = s.index[i - 1]
                    if ts not in records:
                        records[ts] = {}
                    records[ts]["core_yoy"] = float(yoy)

            # Focus 12M expectations
            focus_df = data.get("focus")
            if focus_df is not None and isinstance(focus_df, pd.DataFrame) and not focus_df.empty:
                val_col = self._value_col(focus_df)
                for ts, row in focus_df.iterrows():
                    val = row.get(val_col, np.nan)
                    if pd.notna(val):
                        if ts not in records:
                            records[ts] = {}
                        records[ts]["expectations_12m"] = float(val)

            # IBC-Br output gap
            ibc_df = data.get("ibc_br")
            if ibc_df is not None and isinstance(ibc_df, pd.DataFrame) and not ibc_df.empty:
                val_col = self._value_col(ibc_df)
                series = ibc_df[val_col].dropna()
                if len(series) >= 13:
                    try:
                        _cycle, trend = hpfilter(series, lamb=1600)
                        for i in range(len(series)):
                            ts = series.index[i]
                            lev = float(series.iloc[i])
                            tr = float(trend.iloc[i])
                            gap = (lev - tr) / tr * 100.0 if tr != 0 else 0.0
                            if ts not in records:
                                records[ts] = {}
                            records[ts]["output_gap"] = gap
                    except Exception:
                        pass

            # USDBRL YoY (rolling, from market_data)
            usdbrl_df = data.get("usdbrl")
            if usdbrl_df is not None and isinstance(usdbrl_df, pd.DataFrame) and not usdbrl_df.empty:
                price_col = next(
                    (c for c in ("adjusted_close", "close", "value") if c in usdbrl_df.columns),
                    None,
                )
                if price_col is not None:
                    # Resample to monthly (last observation)
                    monthly = usdbrl_df[price_col].dropna().resample("ME").last()
                    if len(monthly) >= 13:
                        yoy_series = monthly.pct_change(12) * 100.0
                        for ts, val in yoy_series.items():
                            if pd.notna(val):
                                if ts not in records:
                                    records[ts] = {}
                                records[ts]["usdbrl_yoy"] = float(val)

            # CRB YoY (monthly)
            crb_df = data.get("crb")
            if crb_df is not None and isinstance(crb_df, pd.DataFrame) and not crb_df.empty:
                price_col = next(
                    (c for c in ("adjusted_close", "close", "value") if c in crb_df.columns),
                    None,
                )
                if price_col is not None:
                    monthly = crb_df[price_col].dropna().resample("ME").last()
                    if len(monthly) >= 13:
                        yoy_series = monthly.pct_change(12) * 100.0
                        for ts, val in yoy_series.items():
                            if pd.notna(val):
                                if ts not in records:
                                    records[ts] = {}
                                records[ts]["crb_yoy"] = float(val)

            if not records:
                return pd.DataFrame(
                    columns=["core_yoy", "expectations_12m", "output_gap", "usdbrl_yoy", "crb_yoy"]
                )

            df = pd.DataFrame.from_dict(records, orient="index")
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            for col in ["core_yoy", "expectations_12m", "output_gap", "usdbrl_yoy", "crb_yoy"]:
                if col not in df.columns:
                    df[col] = np.nan

            # If output_gap is entirely NaN (IBC-Br unavailable or HP filter failed),
            # fill with 0.0 (neutral gap) so OLS can still run with the other 3 regressors.
            if df["output_gap"].isna().all():
                df["output_gap"] = 0.0

            return df[["core_yoy", "expectations_12m", "output_gap", "usdbrl_yoy", "crb_yoy"]]

        except Exception:
            return pd.DataFrame(
                columns=["core_yoy", "expectations_12m", "output_gap", "usdbrl_yoy", "crb_yoy"]
            )

    # ------------------------------------------------------------------
    # Private key: component data for IpcaBottomUpModel
    # ------------------------------------------------------------------
    def _build_component_data(self, data: dict) -> dict[str, pd.DataFrame]:
        """Return per-component DataFrames with a 'value' column.

        Keys match IpcaBottomUpModel.IBGE_WEIGHTS keys.
        """
        result: dict[str, pd.DataFrame] = {}
        components = data.get("ipca_components")
        if not isinstance(components, dict):
            return result

        for key in self._COMPONENT_KEYS:
            df = components.get(key)
            if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                result[key] = pd.DataFrame(columns=["value"])
                continue
            val_col = self._value_col(df)
            out = df[[val_col]].rename(columns={val_col: "value"}).copy()
            out.index = pd.to_datetime(out.index)

            # Sanity check: if values look like price indices (median > 50)
            # rather than MoM percentages, convert to pct_change.
            if not out["value"].dropna().empty and out["value"].dropna().abs().median() > 50.0:
                out["value"] = out["value"].pct_change() * 100.0
                out = out.dropna()

            result[key] = out

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _value_col(df: pd.DataFrame) -> str:
        """Return the primary value column name from a DataFrame.

        Prefers 'value', then 'close', then first non-date column.
        """
        for col in ("value", "close", "adjusted_close"):
            if col in df.columns:
                return col
        # Fallback: first column that isn't an index-related name
        for col in df.columns:
            if col not in ("date", "release_time", "revision_number"):
                return col
        return df.columns[0]

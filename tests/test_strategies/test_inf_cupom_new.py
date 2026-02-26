"""Tests for INF-02 (IPCA Surprise), INF-03 (Inflation Carry), and CUPOM-02
(Onshore-Offshore Spread) strategies.

Uses mock PointInTimeDataLoader (MagicMock) following the established pattern
from test_inf_br_01.py and test_cupom_01.py.
"""

from datetime import date
from unittest.mock import MagicMock

import pandas as pd

from src.core.enums import AssetClass, SignalDirection
from src.strategies.cupom_02_onshore_offshore import Cupom02OnshoreOffshoreStrategy
from src.strategies.inf_02_ipca_surprise import Inf02IpcaSurpriseStrategy
from src.strategies.inf_03_inflation_carry import Inf03InflationCarryStrategy
from src.strategies.registry import StrategyRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_macro_df(values: list[float], base_date: str = "2020-01-15") -> pd.DataFrame:
    """Create a mock macro series DataFrame.

    Args:
        values: List of observation values.
        base_date: Starting date for the index.

    Returns:
        DataFrame with 'value', 'release_time', 'revision_number' columns.
    """
    dates = pd.date_range(base_date, periods=len(values), freq="MS")
    df = pd.DataFrame({
        "value": values,
        "release_time": dates,
        "revision_number": [1] * len(values),
    }, index=dates)
    df.index.name = "date"
    return df


def _make_curve_history(
    rates: list[float],
    base_date: str = "2023-01-02",
) -> pd.DataFrame:
    """Create a mock curve history DataFrame.

    Args:
        rates: List of rate values.
        base_date: Starting date for the index.

    Returns:
        DataFrame with 'rate' column and date index.
    """
    dates = pd.date_range(base_date, periods=len(rates), freq="B")
    df = pd.DataFrame({"rate": rates}, index=dates)
    df.index.name = "date"
    return df


# ============================================================================
# INF-02: IPCA Surprise Trade
# ============================================================================
def _make_inf02_loader(
    ipca15_value: float | None = 0.52,
    ipca_mom_values: list[float] | None = None,
    focus_ipca_values: list[float] | None = None,
) -> MagicMock:
    """Create a mock loader for INF-02 tests.

    Args:
        ipca15_value: IPCA-15 preview value (None = missing).
        ipca_mom_values: Monthly IPCA values (60 months default).
        focus_ipca_values: Focus IPCA median values (60 months default).
    """
    loader = MagicMock()

    if ipca_mom_values is None:
        # 60 months of realistic IPCA MoM data with seasonal pattern
        ipca_mom_values = [
            0.40 + 0.10 * (i % 12 - 6) / 6.0 for i in range(60)
        ]
    if focus_ipca_values is None:
        # Focus forecasts that are close to actuals but not identical
        focus_ipca_values = [v + 0.02 for v in ipca_mom_values]

    # get_latest_macro_value
    def macro_value_side_effect(series_code, as_of_date):
        if series_code == "BR_IPCA15_MOM":
            return ipca15_value
        return None

    loader.get_latest_macro_value.side_effect = macro_value_side_effect

    # get_macro_series: returns IPCA MoM history
    ipca_df = _make_macro_df(ipca_mom_values)

    def macro_series_side_effect(series_code, as_of_date, lookback_days=3650):
        if series_code == "BR_IPCA_MOM":
            return ipca_df
        if series_code == "BR_FOCUS_IPCA_CY_MEDIAN":
            return _make_macro_df(focus_ipca_values)
        return pd.DataFrame(columns=["date", "value", "release_time", "revision_number"])

    loader.get_macro_series.side_effect = macro_series_side_effect

    # get_focus_expectations: wraps get_macro_series for IPCA
    focus_df = _make_macro_df(focus_ipca_values)

    def focus_side_effect(indicator, as_of_date, lookback_days=365):
        if indicator == "IPCA":
            return focus_df
        return pd.DataFrame(columns=["date", "value", "release_time", "revision_number"])

    loader.get_focus_expectations.side_effect = focus_side_effect

    return loader


class TestInf02Registration:
    """INF-02 is registered with correct asset class."""

    def test_registered_in_strategy_registry(self) -> None:
        assert "INF_02" in StrategyRegistry.list_all()

    def test_registered_with_inflation_br_asset_class(self) -> None:
        strategies = StrategyRegistry.list_by_asset_class(AssetClass.INFLATION_BR)
        assert "INF_02" in strategies


class TestInf02SignalGeneration:
    """INF-02 generates signals when model diverges from Focus."""

    def test_signal_when_model_diverges_high(self) -> None:
        """IPCA-15 = 0.80, Focus ~0.42 => large positive surprise => SHORT."""
        loader = _make_inf02_loader(ipca15_value=0.80)
        strategy = Inf02IpcaSurpriseStrategy(data_loader=loader)
        # Use a date near the 10th for IPCA release window
        signals = strategy.generate_signals(date(2025, 6, 10))

        assert len(signals) == 1
        sig = signals[0]
        assert sig.direction == SignalDirection.SHORT
        assert sig.z_score > 0
        assert sig.strategy_id == "INF_02"
        assert 0.0 <= sig.confidence <= 1.0

    def test_signal_when_model_diverges_low(self) -> None:
        """IPCA-15 = 0.10, Focus ~0.42 => negative surprise => LONG."""
        loader = _make_inf02_loader(ipca15_value=0.10)
        strategy = Inf02IpcaSurpriseStrategy(data_loader=loader)
        signals = strategy.generate_signals(date(2025, 6, 10))

        assert len(signals) == 1
        sig = signals[0]
        assert sig.direction == SignalDirection.LONG
        assert sig.z_score < 0


class TestInf02Ipca15Preference:
    """INF-02 uses IPCA-15 as model forecast when available."""

    def test_ipca15_used_when_available(self) -> None:
        """When IPCA-15 is available, it should be used as the model forecast."""
        loader = _make_inf02_loader(ipca15_value=0.90)
        strategy = Inf02IpcaSurpriseStrategy(data_loader=loader)
        signals = strategy.generate_signals(date(2025, 6, 10))

        assert len(signals) >= 1
        # Verify the model_forecast in metadata is the IPCA-15 value
        assert signals[0].metadata["model_forecast"] == 0.90

    def test_seasonal_fallback_when_ipca15_missing(self) -> None:
        """When IPCA-15 is None, seasonal average should be used."""
        loader = _make_inf02_loader(ipca15_value=None)
        strategy = Inf02IpcaSurpriseStrategy(data_loader=loader)
        signals = strategy.generate_signals(date(2025, 6, 10))

        # Should still work (using seasonal average)
        # Model forecast should not be None (it uses seasonal)
        if signals:
            assert signals[0].metadata["model_forecast"] is not None
            assert signals[0].metadata["model_forecast"] != 0.90


class TestInf02MissingData:
    """INF-02 returns empty list when data is missing."""

    def test_missing_ipca_data_returns_empty(self) -> None:
        """Both IPCA-15 and IPCA MoM missing => empty."""
        loader = MagicMock()
        loader.get_latest_macro_value.return_value = None
        loader.get_macro_series.return_value = pd.DataFrame(
            columns=["date", "value", "release_time", "revision_number"],
        )
        loader.get_focus_expectations.return_value = pd.DataFrame(
            columns=["date", "value", "release_time", "revision_number"],
        )

        strategy = Inf02IpcaSurpriseStrategy(data_loader=loader)
        signals = strategy.generate_signals(date(2025, 6, 10))
        assert signals == []

    def test_missing_focus_returns_empty(self) -> None:
        """Focus expectations missing => empty."""
        loader = _make_inf02_loader()
        empty_df = pd.DataFrame(
            columns=["date", "value", "release_time", "revision_number"],
        )
        # Override both get_focus_expectations and get_macro_series to return
        # empty for Focus data (the strategy calls both internally)
        loader.get_focus_expectations.side_effect = lambda *a, **kw: empty_df
        loader.get_macro_series.side_effect = lambda *a, **kw: empty_df

        strategy = Inf02IpcaSurpriseStrategy(data_loader=loader)
        signals = strategy.generate_signals(date(2025, 6, 10))
        assert signals == []


# ============================================================================
# INF-03: Inflation Carry
# ============================================================================
def _make_inf03_loader(
    di_curve: dict[int, float] | None = None,
    ntnb_curve: dict[int, float] | None = None,
    ipca_12m: float | None = 4.5,
    focus_ipca: float | None = 4.0,
    di_history_rates: list[float] | None = None,
    ntnb_history_rates: list[float] | None = None,
) -> MagicMock:
    """Create a mock loader for INF-03 tests.

    Args:
        di_curve: DI_PRE curve. Defaults to curve with 504 tenor.
        ntnb_curve: NTN_B_REAL curve. Defaults to curve with 504 tenor.
        ipca_12m: Trailing 12M IPCA value.
        focus_ipca: Focus IPCA expectation.
        di_history_rates: Historical DI rates for z-score.
        ntnb_history_rates: Historical NTN-B rates for z-score.
    """
    loader = MagicMock()

    if di_curve is None:
        di_curve = {126: 12.0, 504: 13.0, 756: 13.5}
    if ntnb_curve is None:
        ntnb_curve = {504: 6.0, 756: 6.5}

    def curve_side_effect(curve_id, as_of_date):
        if curve_id == "DI_PRE":
            return di_curve
        if curve_id == "NTN_B_REAL":
            return ntnb_curve
        return {}

    loader.get_curve.side_effect = curve_side_effect

    # Macro values
    def macro_value_side_effect(series_code, as_of_date):
        if series_code == "BR_IPCA_12M":
            return ipca_12m
        return None

    loader.get_latest_macro_value.side_effect = macro_value_side_effect

    # Focus expectations
    if focus_ipca is not None:
        focus_df = _make_macro_df([focus_ipca] * 30)
    else:
        focus_df = pd.DataFrame(
            columns=["date", "value", "release_time", "revision_number"],
        )

    def focus_side_effect(indicator, as_of_date, lookback_days=365):
        if indicator == "IPCA":
            return focus_df
        return pd.DataFrame(columns=["date", "value", "release_time", "revision_number"])

    loader.get_focus_expectations.side_effect = focus_side_effect

    # Curve histories
    if di_history_rates is None:
        di_history_rates = [13.0 + 0.05 * (i % 10 - 5) for i in range(300)]
    if ntnb_history_rates is None:
        ntnb_history_rates = [6.0 + 0.03 * (i % 10 - 5) for i in range(300)]

    def history_side_effect(curve_id, tenor, as_of, lookback_days=756):
        if curve_id == "DI_PRE":
            return _make_curve_history(di_history_rates)
        if curve_id == "NTN_B_REAL":
            return _make_curve_history(ntnb_history_rates)
        return pd.DataFrame(columns=["date", "rate"])

    loader.get_curve_history.side_effect = history_side_effect

    return loader


class TestInf03Registration:
    """INF-03 registration tests."""

    def test_registered_in_strategy_registry(self) -> None:
        assert "INF_03" in StrategyRegistry.list_all()

    def test_registered_with_inflation_br_asset_class(self) -> None:
        strategies = StrategyRegistry.list_by_asset_class(AssetClass.INFLATION_BR)
        assert "INF_03" in strategies


class TestInf03ShortBreakeven:
    """Breakeven above target+band => composite > 0 => SHORT breakeven."""

    def test_high_breakeven_triggers_short(self) -> None:
        """DI=15 - NTN-B=4 = breakeven 11% >> target 3% => SHORT."""
        loader = _make_inf03_loader(
            di_curve={504: 15.0},
            ntnb_curve={504: 4.0},
            ipca_12m=4.5,
            focus_ipca=4.0,
        )
        strategy = Inf03InflationCarryStrategy(data_loader=loader)
        signals = strategy.generate_signals(date(2025, 6, 15))

        assert len(signals) == 1
        sig = signals[0]
        assert sig.direction == SignalDirection.SHORT
        assert sig.z_score > 0
        assert sig.strategy_id == "INF_03"

    def test_short_metadata_contains_benchmarks(self) -> None:
        """Metadata should contain all 3 benchmark comparisons."""
        loader = _make_inf03_loader(
            di_curve={504: 15.0},
            ntnb_curve={504: 4.0},
        )
        strategy = Inf03InflationCarryStrategy(data_loader=loader)
        signals = strategy.generate_signals(date(2025, 6, 15))

        assert len(signals) == 1
        meta = signals[0].metadata
        assert "bcb_target" in meta
        assert "ipca_12m" in meta
        assert "focus_ipca" in meta
        assert "composite_z" in meta


class TestInf03LongBreakeven:
    """Breakeven below all benchmarks => LONG breakeven."""

    def test_low_breakeven_triggers_long(self) -> None:
        """DI=8 - NTN-B=7 = breakeven 1% << target 3% => LONG."""
        loader = _make_inf03_loader(
            di_curve={504: 8.0},
            ntnb_curve={504: 7.0},
            ipca_12m=4.5,
            focus_ipca=4.0,
            # History centered around breakeven=7 so current=1 is well below
            di_history_rates=[13.0 + 0.05 * (i % 10 - 5) for i in range(300)],
            ntnb_history_rates=[6.0 + 0.03 * (i % 10 - 5) for i in range(300)],
        )
        strategy = Inf03InflationCarryStrategy(data_loader=loader)
        signals = strategy.generate_signals(date(2025, 6, 15))

        assert len(signals) == 1
        sig = signals[0]
        assert sig.direction == SignalDirection.LONG
        assert sig.z_score < 0


class TestInf03MissingData:
    """INF-03 returns empty when data is missing."""

    def test_missing_di_curve_returns_empty(self) -> None:
        loader = _make_inf03_loader(di_curve={})
        strategy = Inf03InflationCarryStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_missing_ntnb_curve_returns_empty(self) -> None:
        loader = _make_inf03_loader(ntnb_curve={})
        strategy = Inf03InflationCarryStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_missing_ipca_12m_returns_empty(self) -> None:
        loader = _make_inf03_loader(ipca_12m=None)
        strategy = Inf03InflationCarryStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_missing_focus_returns_empty(self) -> None:
        loader = _make_inf03_loader(focus_ipca=None)
        strategy = Inf03InflationCarryStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []


# ============================================================================
# CUPOM-02: Onshore-Offshore Spread
# ============================================================================
def _make_cupom02_loader(
    di_curve: dict[int, float] | None = None,
    ust_curve: dict[int, float] | None = None,
    di_history_rates: list[float] | None = None,
    ust_history_rates: list[float] | None = None,
) -> MagicMock:
    """Create a mock loader for CUPOM-02 tests.

    Args:
        di_curve: DI_PRE curve. Defaults to curve with 126 tenor.
        ust_curve: UST_NOM curve. Defaults to curve with 126 tenor.
        di_history_rates: Historical DI rates for z-score.
        ust_history_rates: Historical UST rates for z-score.
    """
    loader = MagicMock()

    if di_curve is None:
        di_curve = {63: 12.0, 126: 13.0, 252: 13.5, 504: 14.0}
    if ust_curve is None:
        ust_curve = {126: 4.50, 252: 4.60, 365: 4.75}

    def curve_side_effect(curve_id, as_of_date):
        if curve_id == "DI_PRE":
            return di_curve
        if curve_id == "UST_NOM":
            return ust_curve
        return {}

    loader.get_curve.side_effect = curve_side_effect

    # Curve histories
    if di_history_rates is None:
        di_history_rates = [13.0 + 0.05 * (i % 10 - 5) for i in range(300)]
    if ust_history_rates is None:
        ust_history_rates = [4.50 + 0.02 * (i % 10 - 5) for i in range(300)]

    def history_side_effect(curve_id, tenor, as_of, lookback_days=756):
        if curve_id == "DI_PRE":
            return _make_curve_history(di_history_rates)
        if curve_id == "UST_NOM":
            return _make_curve_history(ust_history_rates)
        return pd.DataFrame(columns=["date", "rate"])

    loader.get_curve_history.side_effect = history_side_effect

    return loader


class TestCupom02Registration:
    """CUPOM-02 registration tests."""

    def test_registered_in_strategy_registry(self) -> None:
        assert "CUPOM_02" in StrategyRegistry.list_all()

    def test_registered_with_cupom_cambial_asset_class(self) -> None:
        strategies = StrategyRegistry.list_by_asset_class(AssetClass.CUPOM_CAMBIAL)
        assert "CUPOM_02" in strategies


class TestCupom02SignalGeneration:
    """CUPOM-02 generates signals on elevated onshore premium."""

    def test_elevated_onshore_premium_produces_signal(self) -> None:
        """DI=18 - UST=4.5 = spread 13.5 >> historical ~8.5 => SHORT."""
        loader = _make_cupom02_loader(
            di_curve={126: 18.0},
            ust_curve={126: 4.50},
        )
        strategy = Cupom02OnshoreOffshoreStrategy(data_loader=loader)
        signals = strategy.generate_signals(date(2025, 6, 15))

        assert len(signals) == 1
        sig = signals[0]
        assert sig.strategy_id == "CUPOM_02"
        assert 0.0 <= sig.confidence <= 1.0
        assert sig.z_score != 0

    def test_positive_z_triggers_short_spread(self) -> None:
        """Positive z-score (elevated onshore premium) => SHORT spread."""
        loader = _make_cupom02_loader(
            di_curve={126: 18.0},
            ust_curve={126: 4.50},
        )
        strategy = Cupom02OnshoreOffshoreStrategy(data_loader=loader)
        signals = strategy.generate_signals(date(2025, 6, 15))

        assert len(signals) == 1
        assert signals[0].direction == SignalDirection.SHORT
        assert signals[0].z_score > 0

    def test_compressed_spread_triggers_long(self) -> None:
        """DI=7 - UST=4.5 = spread 2.5 << historical ~8.5 => LONG."""
        loader = _make_cupom02_loader(
            di_curve={126: 7.0},
            ust_curve={126: 4.50},
        )
        strategy = Cupom02OnshoreOffshoreStrategy(data_loader=loader)
        signals = strategy.generate_signals(date(2025, 6, 15))

        assert len(signals) == 1
        assert signals[0].direction == SignalDirection.LONG
        assert signals[0].z_score < 0


class TestCupom02MissingData:
    """CUPOM-02 returns empty list when data is missing."""

    def test_missing_di_curve_returns_empty(self) -> None:
        loader = _make_cupom02_loader(di_curve={})
        strategy = Cupom02OnshoreOffshoreStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_missing_ust_curve_returns_empty(self) -> None:
        loader = _make_cupom02_loader(ust_curve={})
        strategy = Cupom02OnshoreOffshoreStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_insufficient_history_returns_empty(self) -> None:
        """Less than 60 history points => empty list."""
        loader = _make_cupom02_loader(
            di_history_rates=[13.0] * 20,
            ust_history_rates=[4.50] * 20,
        )
        strategy = Cupom02OnshoreOffshoreStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_no_matching_tenor_returns_empty(self) -> None:
        """Curves with no tenor near 63 or 126 => empty."""
        loader = _make_cupom02_loader(
            di_curve={1000: 13.0},
            ust_curve={1000: 4.50},
        )
        strategy = Cupom02OnshoreOffshoreStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

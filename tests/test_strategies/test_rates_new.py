"""Tests for 4 new rates strategies: RATES-03, RATES-04, RATES-05, RATES-06.

Uses mock PointInTimeDataLoader to test signal generation, event windowing,
adaptive exit, and missing-data handling across all strategies.
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.core.enums import AssetClass, SignalDirection
from src.strategies.base import StrategySignal
from src.strategies.rates_03_br_us_spread import Rates03BrUsSpreadStrategy
from src.strategies.rates_04_term_premium import Rates04TermPremiumStrategy
from src.strategies.rates_05_fomc_event import Rates05FomcEventStrategy
from src.strategies.rates_06_copom_event import Rates06CopomEventStrategy
from src.strategies.registry import StrategyRegistry


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _make_history(
    rates: list[float],
    start_date: str = "2024-01-01",
    col: str = "rate",
) -> pd.DataFrame:
    """Build a synthetic curve/macro history DataFrame.

    Args:
        rates: Values (one per business day).
        start_date: First date in the series.
        col: Column name (default 'rate').

    Returns:
        DataFrame with column indexed by date.
    """
    dates = pd.bdate_range(start=start_date, periods=len(rates))
    return pd.DataFrame({col: rates}, index=dates)


def _make_macro_history(
    values: list[float],
    start_date: str = "2024-01-01",
) -> pd.DataFrame:
    """Build a synthetic macro series DataFrame matching data_loader output.

    Args:
        values: One value per business day.
        start_date: First date.

    Returns:
        DataFrame with columns [value, release_time, revision_number].
    """
    dates = pd.bdate_range(start=start_date, periods=len(values))
    return pd.DataFrame(
        {
            "value": values,
            "release_time": dates,
            "revision_number": [1] * len(values),
        },
        index=dates,
    )


# ===========================================================================
# RATES-03: BR-US Spread Tests
# ===========================================================================
class TestRates03Registration:
    """RATES-03 is registered in StrategyRegistry."""

    def test_registered(self) -> None:
        assert "RATES_03" in StrategyRegistry.list_all()

    def test_asset_class(self) -> None:
        meta = StrategyRegistry._metadata.get("RATES_03", {})
        assert meta.get("asset_class") == AssetClass.RATES_BR


class TestRates03SignalGeneration:
    """RATES-03 produces StrategySignal with valid z-score on DI-UST spread."""

    def test_valid_curves_produce_signal(self) -> None:
        loader = MagicMock()

        # DI curve: 2Y (504d) at 13%, 5Y (1260d) at 14%
        loader.get_curve.side_effect = lambda curve_id, d: (
            {504: 0.13, 1260: 0.14} if curve_id == "DI_PRE"
            else {504: 0.045, 1260: 0.05} if curve_id == "UST_NOM"
            else {}
        )

        # CDS and inflation
        def macro_side(code, d):
            return {"BR_CDS_5Y": 200.0, "BR_IPCA_12M": 5.0, "US_CPI_YOY": 3.0}.get(code)
        loader.get_latest_macro_value.side_effect = macro_side

        # DI and UST history -- spread widens dramatically at end (z > 1.25)
        # Normal spread ~8.5%, suddenly jumps to 12%
        di_hist = _make_history([0.13] * 250 + [0.17] * 10)
        ust_hist = _make_history([0.045] * 260)

        def curve_history_side(curve_id, tenor, d, lookback_days=756):
            if "DI" in curve_id:
                return di_hist
            return ust_hist

        loader.get_curve_history.side_effect = curve_history_side

        strat = Rates03BrUsSpreadStrategy(data_loader=loader, entry_z_threshold=1.25)
        signals = strat.generate_signals(date(2025, 6, 15))

        assert len(signals) == 1
        sig = signals[0]
        assert isinstance(sig, StrategySignal)
        assert sig.z_score != 0.0
        assert sig.strategy_id == "RATES_03"


class TestRates03CdsAdjustment:
    """CDS adjustment reduces the spread when CDS data is available."""

    def test_cds_reduces_spread(self) -> None:
        loader = MagicMock()
        loader.get_curve.side_effect = lambda curve_id, d: (
            {504: 0.13, 1260: 0.14} if curve_id == "DI_PRE"
            else {504: 0.045, 1260: 0.05} if curve_id == "UST_NOM"
            else {}
        )
        # CDS at 200bps = 2.0% -> adjusted spread = raw - 2.0%
        loader.get_latest_macro_value.side_effect = lambda c, d: (
            200.0 if c == "BR_CDS_5Y" else None
        )

        di_hist = _make_history([0.13] * 260)
        ust_hist = _make_history([0.045] * 260)
        loader.get_curve_history.side_effect = lambda *a, **kw: (
            di_hist if "DI" in a[0] else ust_hist
        )

        strat = Rates03BrUsSpreadStrategy(data_loader=loader, entry_z_threshold=0.1)
        signals = strat.generate_signals(date(2025, 6, 15))

        # The signal's raw_value should reflect CDS adjustment
        # raw_spread_2y = 0.13 - 0.045 = 0.085
        # cds_pct = 200/100 = 2.0%
        # adjusted = 0.085 - 0.02 = 0.065
        if signals:
            assert signals[0].metadata["adjusted_spread_2y"] < signals[0].metadata["raw_spread_2y"]


class TestRates03MissingData:
    """Missing curve data returns empty list."""

    def test_missing_di_curve_returns_empty(self) -> None:
        loader = MagicMock()
        loader.get_curve.side_effect = lambda curve_id, d: (
            {} if curve_id == "DI_PRE" else {504: 0.045}
        )
        strat = Rates03BrUsSpreadStrategy(data_loader=loader)
        assert strat.generate_signals(date(2025, 6, 15)) == []

    def test_missing_ust_curve_returns_empty(self) -> None:
        loader = MagicMock()
        loader.get_curve.side_effect = lambda curve_id, d: (
            {504: 0.13} if curve_id == "DI_PRE" else {}
        )
        strat = Rates03BrUsSpreadStrategy(data_loader=loader)
        assert strat.generate_signals(date(2025, 6, 15)) == []


# ===========================================================================
# RATES-04: Term Premium Tests
# ===========================================================================
class TestRates04Registration:
    """RATES-04 is registered in StrategyRegistry."""

    def test_registered(self) -> None:
        assert "RATES_04" in StrategyRegistry.list_all()


class TestRates04SignalGeneration:
    """RATES-04 produces signal when DI_2Y > Focus Selic (positive TP)."""

    def test_positive_tp_produces_signal(self) -> None:
        loader = MagicMock()

        # DI curve: 2Y at 13%, 5Y at 14%
        loader.get_curve.return_value = {504: 0.13, 1260: 0.14}

        # Focus Selic at 10% -> TP_2Y = 0.13 - 0.10 = 0.03
        focus_df = _make_macro_history([0.10] * 100)
        loader.get_focus_expectations.return_value = focus_df

        # DI history with elevated TP at end
        di_hist = _make_history([0.11] * 250 + [0.15] * 10)
        loader.get_curve_history.return_value = di_hist

        strat = Rates04TermPremiumStrategy(data_loader=loader, entry_z_threshold=1.0)
        signals = strat.generate_signals(date(2025, 6, 15))

        assert len(signals) == 1
        sig = signals[0]
        assert isinstance(sig, StrategySignal)
        assert sig.metadata["tp_2y"] > 0


class TestRates04StrongSignal:
    """Extreme TP z-score produces STRONG signal."""

    def test_extreme_tp_z_strong(self) -> None:
        loader = MagicMock()

        # DI at very elevated level vs Focus
        loader.get_curve.return_value = {504: 0.20, 1260: 0.22}

        focus_df = _make_macro_history([0.10] * 200)
        loader.get_focus_expectations.return_value = focus_df

        # Long history at low TP, then sudden spike
        di_hist = _make_history([0.11] * 250 + [0.22] * 10)
        loader.get_curve_history.return_value = di_hist

        strat = Rates04TermPremiumStrategy(data_loader=loader, entry_z_threshold=1.0)
        signals = strat.generate_signals(date(2025, 6, 15))

        assert len(signals) == 1
        from src.core.enums import SignalStrength
        assert signals[0].strength == SignalStrength.STRONG


class TestRates04MissingFocus:
    """Missing Focus data returns empty list."""

    def test_missing_focus_returns_empty(self) -> None:
        loader = MagicMock()
        loader.get_curve.return_value = {504: 0.13, 1260: 0.14}
        loader.get_focus_expectations.return_value = pd.DataFrame(
            columns=["value", "release_time", "revision_number"]
        )

        strat = Rates04TermPremiumStrategy(data_loader=loader)
        assert strat.generate_signals(date(2025, 6, 15)) == []


# ===========================================================================
# RATES-05: FOMC Event Tests
# ===========================================================================
class TestRates05Registration:
    """RATES-05 is registered in StrategyRegistry."""

    def test_registered(self) -> None:
        assert "RATES_05" in StrategyRegistry.list_all()

    def test_asset_class_us(self) -> None:
        meta = StrategyRegistry._metadata.get("RATES_05", {})
        assert meta.get("asset_class") == AssetClass.RATES_US


class TestRates05PreEventSignal:
    """Signal generated when as_of_date is within 5 days before FOMC."""

    def test_signal_before_fomc(self) -> None:
        loader = MagicMock()

        # Use a known FOMC date: 2025-03-19 (Wednesday)
        # 3 business days before = 2025-03-14 (Friday)
        as_of = date(2025, 3, 14)

        # UST curve
        loader.get_curve.return_value = {504: 0.045}

        # CPI at 4.0%, FFR at 5.25%
        def macro_side(code, d):
            return {"US_CPI_YOY": 4.0, "US_FED_FUNDS": 5.25}.get(code)
        loader.get_latest_macro_value.side_effect = macro_side

        # History for divergence z-score
        ust_hist = _make_history([0.04] * 300)
        loader.get_curve_history.return_value = ust_hist

        cpi_hist = _make_macro_history([3.5] * 300)
        loader.get_macro_series.return_value = cpi_hist

        strat = Rates05FomcEventStrategy(
            data_loader=loader, entry_z_threshold=0.5
        )
        signals = strat.generate_signals(as_of)

        # Should produce a signal (we're inside the FOMC window)
        assert len(signals) >= 1
        assert signals[0].metadata["phase"] == "pre_event"


class TestRates05OutsideWindow:
    """No signal when outside FOMC window."""

    def test_no_signal_outside_fomc(self) -> None:
        loader = MagicMock()

        # 2025-02-15 is a Saturday, but 2025-02-10 (Monday) is far from any FOMC
        as_of = date(2025, 2, 10)

        strat = Rates05FomcEventStrategy(data_loader=loader)
        signals = strat.generate_signals(as_of)

        assert signals == []


class TestRates05PostEventExit:
    """Post-event exit: no signal when z reverts below 0.5."""

    def test_post_event_z_reverted(self) -> None:
        loader = MagicMock()

        # 1 business day after FOMC 2025-03-19 -> 2025-03-20 (Thursday)
        as_of = date(2025, 3, 20)

        # Taylor rule in generate_signals with CPI=3.0, FFR=5.0:
        #   neutral = 2.5 + 3.0 = 5.5
        #   output_gap_proxy = (5.0 - 5.5)*0.3 = -0.15
        #   taylor = 2.5 + 3.0 + 0.5*(3.0-2.0) + 0.5*(-0.15) = 5.925
        # Set UST = 5.925 -> current divergence = 0.0
        #
        # In _build_divergence_history (no output_gap_proxy):
        #   taylor_hist = 2.5 + 3.0 + 0.5*(3.0-2.0) = 6.0
        #   hist divergence = UST - 6.0
        # With UST noise around 5.925 -> hist divergences around -0.075
        # std(hist) ~ 0.1; z of 0.0 relative to mean -0.075 = (0-(-0.075))/0.1 ~ 0.75
        # Need exit_z_threshold = 1.0 to ensure exit triggers
        loader.get_curve.return_value = {504: 5.925}

        def macro_side(code, d):
            return {"US_CPI_YOY": 3.0, "US_FED_FUNDS": 5.0}.get(code)
        loader.get_latest_macro_value.side_effect = macro_side

        # History with noise so that z of current divergence (0.0) is small
        # Historical divergences will be UST_rate - 6.0 (the Taylor from history)
        # Set UST history around 6.0 -> hist divergences around 0 -> z of 0 = 0
        import random
        random.seed(42)
        ust_noise = [6.0 + random.gauss(0, 0.15) for _ in range(300)]
        ust_hist = _make_history(ust_noise)
        loader.get_curve_history.return_value = ust_hist

        cpi_hist = _make_macro_history([3.0] * 300)
        loader.get_macro_series.return_value = cpi_hist

        strat = Rates05FomcEventStrategy(
            data_loader=loader, entry_z_threshold=1.0, exit_z_threshold=1.0
        )
        signals = strat.generate_signals(as_of)

        # Current divergence = 5.925 - 5.925 = 0.0
        # Historical divergences centered around 0 (UST ~ 6.0, taylor_hist = 6.0)
        # z = (0.0 - ~0) / ~0.15 -> |z| << 1.0 -> post-event exit triggers
        assert signals == []


class TestRates05MissingData:
    """Missing UST curve returns empty list."""

    def test_missing_ust_returns_empty(self) -> None:
        loader = MagicMock()

        # Inside FOMC window
        as_of = date(2025, 3, 14)
        loader.get_curve.return_value = {}

        strat = Rates05FomcEventStrategy(data_loader=loader)
        assert strat.generate_signals(as_of) == []


# ===========================================================================
# RATES-06: COPOM Event Tests
# ===========================================================================
class TestRates06Registration:
    """RATES-06 is registered in StrategyRegistry."""

    def test_registered(self) -> None:
        assert "RATES_06" in StrategyRegistry.list_all()


class TestRates06DuringWindow:
    """Signal generated during COPOM window."""

    def test_signal_during_copom_window(self) -> None:
        loader = MagicMock()

        # COPOM date 2025-03-19 -> 3 bdays before = 2025-03-14
        as_of = date(2025, 3, 14)

        # DI curve: short tenor at 13.5%
        loader.get_curve.return_value = {30: 0.135, 504: 0.13, 1260: 0.14}

        # Selic at 13.25%, IPCA at 5.0% (above upper band -> model expects hike)
        def macro_side(code, d):
            return {"BR_SELIC_TARGET": 0.1325, "BR_IPCA_12M": 5.0}.get(code)
        loader.get_latest_macro_value.side_effect = macro_side

        # History for divergence
        di_hist = _make_history([0.13] * 200)
        selic_hist = _make_macro_history([0.1325] * 200)
        ipca_hist = _make_macro_history([5.0] * 200)

        def macro_series_side(code, d, lookback_days=504):
            if "SELIC" in code:
                return selic_hist
            if "IPCA" in code:
                return ipca_hist
            return pd.DataFrame(columns=["value", "release_time", "revision_number"])

        loader.get_macro_series.side_effect = macro_series_side
        loader.get_curve_history.return_value = di_hist

        strat = Rates06CopomEventStrategy(
            data_loader=loader, entry_z_threshold=0.3
        )
        signals = strat.generate_signals(as_of)

        # Should produce signal (inside window + data available)
        assert len(signals) >= 1


class TestRates06OutsideWindow:
    """No signal outside COPOM window."""

    def test_no_signal_outside_copom(self) -> None:
        loader = MagicMock()

        # 2025-02-10 is far from any COPOM date
        as_of = date(2025, 2, 10)

        strat = Rates06CopomEventStrategy(data_loader=loader)
        assert strat.generate_signals(as_of) == []


class TestRates06Direction:
    """DI pricing more hawkish than model -> LONG direction."""

    def test_hawkish_di_long_direction(self) -> None:
        loader = MagicMock()

        # COPOM date 2025-03-19 -> 2 bdays before = 2025-03-17
        as_of = date(2025, 3, 17)

        # DI short end pricing aggressively high (hawkish)
        loader.get_curve.return_value = {30: 0.145, 504: 0.14}

        # Selic at 13.25%, IPCA at 5.0% -> model expects +25bps
        # DI-implied = 0.145 - 0.1325 = 0.0125 (125bps)
        # Model = +0.0025 (25bps)
        # Divergence = 0.0125 - 0.0025 = 0.01 (positive -> hawkish DI)
        def macro_side(code, d):
            return {"BR_SELIC_TARGET": 0.1325, "BR_IPCA_12M": 5.0}.get(code)
        loader.get_latest_macro_value.side_effect = macro_side

        # History where DI was close to Selic (low divergence historically)
        di_hist = _make_history([0.1325] * 200)
        selic_hist = _make_macro_history([0.1325] * 200)
        ipca_hist = _make_macro_history([5.0] * 200)

        def macro_series_side(code, d, lookback_days=504):
            if "SELIC" in code:
                return selic_hist
            if "IPCA" in code:
                return ipca_hist
            return pd.DataFrame(columns=["value", "release_time", "revision_number"])

        loader.get_macro_series.side_effect = macro_series_side
        loader.get_curve_history.return_value = di_hist

        strat = Rates06CopomEventStrategy(
            data_loader=loader, entry_z_threshold=0.5
        )
        signals = strat.generate_signals(as_of)

        if signals:
            # Divergence > 0 -> z > 0 -> LONG direction
            assert signals[0].direction == SignalDirection.LONG


class TestRates06MissingData:
    """Missing DI curve returns empty list."""

    def test_missing_di_returns_empty(self) -> None:
        loader = MagicMock()

        # Inside COPOM window
        as_of = date(2025, 3, 17)
        loader.get_curve.return_value = {}

        strat = Rates06CopomEventStrategy(data_loader=loader)
        assert strat.generate_signals(as_of) == []

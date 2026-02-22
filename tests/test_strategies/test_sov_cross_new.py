"""Tests for SOV-01, SOV-02, SOV-03, CROSS-01, and CROSS-02 strategies.

Uses mock PointInTimeDataLoader (MagicMock) following the established pattern
from test_inf_cupom_new.py and test_fx_new.py.
"""

from datetime import date
from unittest.mock import MagicMock

import pandas as pd

from src.core.enums import AssetClass, SignalDirection
from src.strategies.cross_01_regime_allocation import (
    Cross01RegimeAllocationStrategy,
    MacroRegime,
)
from src.strategies.cross_02_risk_appetite import Cross02RiskAppetiteStrategy
from src.strategies.registry import StrategyRegistry
from src.strategies.sov_01_cds_curve import Sov01CdsCurveStrategy
from src.strategies.sov_02_em_relative_value import Sov02EmRelativeValueStrategy
from src.strategies.sov_03_rating_migration import Sov03RatingMigrationStrategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_macro_df(
    values: list[float], base_date: str = "2020-01-15",
) -> pd.DataFrame:
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


def _make_market_df(
    closes: list[float], base_date: str = "2023-01-02",
) -> pd.DataFrame:
    """Create a mock market data DataFrame.

    Args:
        closes: List of close prices.
        base_date: Starting date for the index.

    Returns:
        DataFrame with OHLCV columns and date index.
    """
    dates = pd.date_range(base_date, periods=len(closes), freq="B")
    df = pd.DataFrame({
        "open": closes,
        "high": [c * 1.01 for c in closes],
        "low": [c * 0.99 for c in closes],
        "close": closes,
        "volume": [1e6] * len(closes),
        "adjusted_close": closes,
    }, index=dates)
    df.index.name = "date"
    return df


def _make_curve_history(
    rates: list[float], base_date: str = "2023-01-02",
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
# SOV-01: CDS Curve Trading
# ============================================================================
def _make_sov01_loader(
    cds_5y_values: list[float] | None = None,
    cds_1y_values: list[float] | None = None,
    debt_pct: float | None = 80.0,
) -> MagicMock:
    """Create a mock loader for SOV-01 tests.

    Args:
        cds_5y_values: CDS 5Y history values. Defaults to 300 values around 180.
        cds_1y_values: CDS 1Y history values. None means unavailable.
        debt_pct: Debt-to-GDP value.
    """
    loader = MagicMock()

    if cds_5y_values is None:
        cds_5y_values = [180.0 + 5.0 * (i % 20 - 10) for i in range(300)]

    cds_5y_df = _make_macro_df(cds_5y_values)

    def macro_series_side_effect(series_code, as_of_date, lookback_days=3650):
        if series_code == "BR_CDS_5Y":
            return cds_5y_df
        if series_code == "BR_CDS_1Y" and cds_1y_values is not None:
            return _make_macro_df(cds_1y_values)
        return pd.DataFrame(columns=["date", "value", "release_time", "revision_number"])

    loader.get_macro_series.side_effect = macro_series_side_effect

    def macro_value_side_effect(series_code, as_of_date):
        if series_code == "BR_CDS_5Y":
            return cds_5y_values[-1] if cds_5y_values else None
        if series_code in ("BR_GROSS_DEBT_PCT_GDP", "BR_GROSS_DEBT_GDP"):
            return debt_pct
        return None

    loader.get_latest_macro_value.side_effect = macro_value_side_effect

    return loader


class TestSov01Registration:
    """SOV-01 registration tests."""

    def test_registered_in_strategy_registry(self) -> None:
        assert "SOV_01" in StrategyRegistry.list_all()

    def test_registered_with_sovereign_credit_asset_class(self) -> None:
        strategies = StrategyRegistry.list_by_asset_class(AssetClass.SOVEREIGN_CREDIT)
        assert "SOV_01" in strategies


class TestSov01SignalGeneration:
    """SOV-01 generates signals based on CDS curve."""

    def test_elevated_cds_produces_signal(self) -> None:
        """CDS at 280 vs history around 180 => high level z => signal."""
        # History around 180, but current value pushed to 280
        cds_values = [180.0 + 5.0 * (i % 20 - 10) for i in range(299)]
        cds_values.append(280.0)  # Elevated current

        loader = _make_sov01_loader(cds_5y_values=cds_values)
        strategy = Sov01CdsCurveStrategy(data_loader=loader)
        signals = strategy.generate_signals(date(2025, 6, 15))

        assert len(signals) == 1
        sig = signals[0]
        assert sig.strategy_id == "SOV_01"
        assert sig.z_score != 0
        assert 0.0 <= sig.confidence <= 1.0
        assert sig.asset_class == AssetClass.SOVEREIGN_CREDIT

    def test_cds_level_z_direction(self) -> None:
        """High level z (stress) => SHORT CDS (sell protection, mean reversion)."""
        cds_values = [180.0 + 3.0 * (i % 10 - 5) for i in range(299)]
        cds_values.append(220.0)  # Above mean but not extreme

        loader = _make_sov01_loader(cds_5y_values=cds_values)
        strategy = Sov01CdsCurveStrategy(data_loader=loader)
        signals = strategy.generate_signals(date(2025, 6, 15))

        if signals:
            # When composite > 0 and < 3, direction should be SHORT (mean reversion)
            assert signals[0].direction == SignalDirection.SHORT


class TestSov01MissingData:
    """SOV-01 returns empty list when data is missing."""

    def test_missing_cds_data_returns_empty(self) -> None:
        loader = MagicMock()
        loader.get_macro_series.return_value = pd.DataFrame(
            columns=["date", "value", "release_time", "revision_number"],
        )
        loader.get_latest_macro_value.return_value = None

        strategy = Sov01CdsCurveStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []


# ============================================================================
# SOV-02: EM Sovereign Relative Value
# ============================================================================
def _make_sov02_loader(
    br_cds_value: float | None = 250.0,
    cds_history: list[float] | None = None,
) -> MagicMock:
    """Create a mock loader for SOV-02 tests.

    Args:
        br_cds_value: Current Brazil CDS 5Y value. None = missing.
        cds_history: Historical CDS values for residual z-score.
    """
    loader = MagicMock()

    if cds_history is None:
        cds_history = [180.0 + 5.0 * (i % 20 - 10) for i in range(300)]

    cds_df = _make_macro_df(cds_history)

    def macro_value_side_effect(series_code, as_of_date):
        if series_code == "BR_CDS_5Y":
            return br_cds_value
        return None

    loader.get_latest_macro_value.side_effect = macro_value_side_effect

    def macro_series_side_effect(series_code, as_of_date, lookback_days=3650):
        if series_code == "BR_CDS_5Y":
            return cds_df
        return pd.DataFrame(columns=["date", "value", "release_time", "revision_number"])

    loader.get_macro_series.side_effect = macro_series_side_effect

    return loader


class TestSov02Registration:
    """SOV-02 registration tests."""

    def test_registered_in_strategy_registry(self) -> None:
        assert "SOV_02" in StrategyRegistry.list_all()


class TestSov02SignalGeneration:
    """SOV-02 signal tests."""

    def test_positive_residual_triggers_short(self) -> None:
        """CDS expensive (250 vs predicted ~180) => positive residual => SHORT."""
        loader = _make_sov02_loader(br_cds_value=250.0)
        strategy = Sov02EmRelativeValueStrategy(data_loader=loader)
        signals = strategy.generate_signals(date(2025, 6, 15))

        assert len(signals) == 1
        sig = signals[0]
        assert sig.direction == SignalDirection.SHORT
        assert sig.z_score > 0
        assert sig.strategy_id == "SOV_02"

    def test_negative_residual_triggers_long(self) -> None:
        """CDS cheap (80 vs predicted ~180) => negative residual => LONG."""
        # History around 180, with last value = 80 (matching br_cds_value)
        cds_history = [180.0 + 5.0 * (i % 20 - 10) for i in range(299)]
        cds_history.append(80.0)  # Current value must match br_cds_value
        loader = _make_sov02_loader(br_cds_value=80.0, cds_history=cds_history)
        strategy = Sov02EmRelativeValueStrategy(data_loader=loader)
        signals = strategy.generate_signals(date(2025, 6, 15))

        assert len(signals) == 1
        assert signals[0].direction == SignalDirection.LONG


class TestSov02MissingData:
    """SOV-02 returns empty list when data is missing."""

    def test_missing_br_cds_returns_empty(self) -> None:
        loader = _make_sov02_loader(br_cds_value=None)
        strategy = Sov02EmRelativeValueStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []


# ============================================================================
# SOV-03: Rating Migration Anticipation
# ============================================================================
def _make_sov03_loader(
    debt_pct: float | None = 85.0,
    gdp_growth: float | None = 1.0,
    trade_balance: float | None = 3.0,
    cds_values: list[float] | None = None,
) -> MagicMock:
    """Create a mock loader for SOV-03 tests.

    Args:
        debt_pct: Debt-to-GDP %. None = missing.
        gdp_growth: GDP growth YOY %. None = missing.
        trade_balance: Trade balance in USD bn. None = missing.
        cds_values: CDS 5Y history for political factor.
    """
    loader = MagicMock()

    if cds_values is None:
        # Rising CDS trend for elevated political risk
        cds_values = [160.0 + 0.5 * i for i in range(200)]

    cds_df = _make_macro_df(cds_values)

    def macro_value_side_effect(series_code, as_of_date):
        if series_code in ("BR_GROSS_DEBT_PCT_GDP", "BR_GROSS_DEBT_GDP"):
            return debt_pct
        if series_code == "BR_GDP_GROWTH_YOY":
            return gdp_growth
        if series_code == "BR_TRADE_BALANCE":
            return trade_balance
        if series_code == "BR_CDS_5Y":
            return cds_values[-1] if cds_values else None
        return None

    loader.get_latest_macro_value.side_effect = macro_value_side_effect

    def macro_series_side_effect(series_code, as_of_date, lookback_days=3650):
        if series_code == "BR_CDS_5Y":
            return cds_df
        return pd.DataFrame(columns=["date", "value", "release_time", "revision_number"])

    loader.get_macro_series.side_effect = macro_series_side_effect

    return loader


class TestSov03Registration:
    """SOV-03 registration tests."""

    def test_registered_in_strategy_registry(self) -> None:
        assert "SOV_03" in StrategyRegistry.list_all()


class TestSov03SignalGeneration:
    """SOV-03 signal generation tests."""

    def test_high_fiscal_stress_triggers_long_cds(self) -> None:
        """High debt (100%) + low growth (-0.5%) => p_downgrade > 0.65 => LONG CDS."""
        loader = _make_sov03_loader(
            debt_pct=100.0,
            gdp_growth=-0.5,
            trade_balance=-8.0,  # large deficit
        )
        strategy = Sov03RatingMigrationStrategy(data_loader=loader)
        signals = strategy.generate_signals(date(2025, 6, 15))

        assert len(signals) == 1
        sig = signals[0]
        assert sig.direction == SignalDirection.LONG  # buy protection
        assert sig.metadata["p_downgrade"] > 0.65

    def test_favorable_conditions_triggers_short_cds(self) -> None:
        """Low debt (60%) + high growth (4%) => p_downgrade < 0.35 => SHORT CDS."""
        # Flat/declining CDS trend for low political risk
        cds_values = [200.0 - 0.3 * i for i in range(200)]
        loader = _make_sov03_loader(
            debt_pct=60.0,
            gdp_growth=4.0,
            trade_balance=10.0,  # surplus
            cds_values=cds_values,
        )
        strategy = Sov03RatingMigrationStrategy(data_loader=loader)
        signals = strategy.generate_signals(date(2025, 6, 15))

        assert len(signals) == 1
        sig = signals[0]
        assert sig.direction == SignalDirection.SHORT  # sell protection
        assert sig.metadata["p_downgrade"] < 0.35


class TestSov03MissingData:
    """SOV-03 returns empty list when data is missing."""

    def test_missing_debt_returns_empty(self) -> None:
        loader = _make_sov03_loader(debt_pct=None)
        strategy = Sov03RatingMigrationStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []


# ============================================================================
# CROSS-01: Macro Regime Allocation
# ============================================================================
def _make_cross01_loader(
    gdp_growth: float | None = 3.0,
    ipca_12m: float | None = 3.0,
    growth_history: list[float] | None = None,
    inflation_history: list[float] | None = None,
) -> MagicMock:
    """Create a mock loader for CROSS-01 tests.

    Args:
        gdp_growth: Current GDP growth YOY %.
        ipca_12m: Current trailing 12M IPCA %.
        growth_history: Historical GDP values for z-score.
        inflation_history: Historical IPCA values for z-score.
    """
    loader = MagicMock()

    if growth_history is None:
        growth_history = [2.0 + 0.3 * (i % 10 - 5) for i in range(60)]
    if inflation_history is None:
        inflation_history = [4.5 + 0.5 * (i % 10 - 5) for i in range(60)]

    growth_df = _make_macro_df(growth_history)
    infl_df = _make_macro_df(inflation_history)

    def macro_value_side_effect(series_code, as_of_date):
        if series_code == "BR_GDP_GROWTH_YOY":
            return gdp_growth
        if series_code == "BR_IPCA_12M":
            return ipca_12m
        return None

    loader.get_latest_macro_value.side_effect = macro_value_side_effect

    def macro_series_side_effect(series_code, as_of_date, lookback_days=3650):
        if series_code == "BR_GDP_GROWTH_YOY":
            return growth_df
        if series_code == "BR_IPCA_12M":
            return infl_df
        return pd.DataFrame(columns=["date", "value", "release_time", "revision_number"])

    loader.get_macro_series.side_effect = macro_series_side_effect

    return loader


class TestCross01Registration:
    """CROSS-01 registration tests."""

    def test_registered_in_strategy_registry(self) -> None:
        assert "CROSS_01" in StrategyRegistry.list_all()

    def test_registered_with_cross_asset_class(self) -> None:
        strategies = StrategyRegistry.list_by_asset_class(AssetClass.CROSS_ASSET)
        assert "CROSS_01" in strategies


class TestCross01GoldilocksRegime:
    """CROSS-01 classifies Goldilocks regime correctly."""

    def test_goldilocks_regime_classification(self) -> None:
        """Growth up (4%) + inflation low (3%) => Goldilocks."""
        loader = _make_cross01_loader(
            gdp_growth=4.0,  # above history mean ~2.0
            ipca_12m=3.0,    # below history mean ~4.5
        )
        strategy = Cross01RegimeAllocationStrategy(data_loader=loader)
        signals = strategy.generate_signals(date(2025, 6, 15))

        assert len(signals) >= 1
        # Goldilocks: LONG equities, LONG DI, SHORT USDBRL, LONG NTN-B
        instruments_traded = [s.instruments[0] for s in signals]
        assert "IBOV_FUT" in instruments_traded

        # Check metadata contains regime
        for sig in signals:
            assert sig.metadata["regime"] == "Goldilocks"


class TestCross01StagflationRegime:
    """CROSS-01 classifies Stagflation regime correctly."""

    def test_stagflation_triggers_short_equities(self) -> None:
        """Growth down (0.5%) + inflation high (8%) => Stagflation => SHORT equities."""
        loader = _make_cross01_loader(
            gdp_growth=0.5,  # below mean
            ipca_12m=8.0,    # well above mean
        )
        strategy = Cross01RegimeAllocationStrategy(data_loader=loader)
        signals = strategy.generate_signals(date(2025, 6, 15))

        assert len(signals) >= 1
        # Find equity signal
        equity_signals = [
            s for s in signals if "IBOV_FUT" in s.instruments
        ]
        assert len(equity_signals) == 1
        assert equity_signals[0].direction == SignalDirection.SHORT

        # Verify regime metadata
        for sig in signals:
            assert sig.metadata["regime"] == "Stagflation"


class TestCross01RegimeMetadata:
    """CROSS-01 stores regime metadata in signals."""

    def test_metadata_contains_regime_info(self) -> None:
        """All signals should have growth_z, inflation_z, regime, regime_confidence."""
        loader = _make_cross01_loader(gdp_growth=3.5, ipca_12m=3.0)
        strategy = Cross01RegimeAllocationStrategy(data_loader=loader)
        signals = strategy.generate_signals(date(2025, 6, 15))

        if signals:
            meta = signals[0].metadata
            assert "regime" in meta
            assert "growth_z" in meta
            assert "inflation_z" in meta
            assert "regime_confidence" in meta
            assert meta["regime"] in [
                "Goldilocks", "Reflation", "Stagflation", "Deflation",
            ]


class TestCross01MissingData:
    """CROSS-01 returns empty list when data is missing."""

    def test_missing_growth_returns_empty(self) -> None:
        loader = _make_cross01_loader(gdp_growth=None)
        strategy = Cross01RegimeAllocationStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_missing_inflation_returns_empty(self) -> None:
        loader = _make_cross01_loader(ipca_12m=None)
        strategy = Cross01RegimeAllocationStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []


# ============================================================================
# CROSS-02: Global Risk Appetite
# ============================================================================
def _make_cross02_loader(
    vix_closes: list[float] | None = None,
    cds_values: list[float] | None = None,
    usdbrl_closes: list[float] | None = None,
    ibov_closes: list[float] | None = None,
    di_curve: dict[int, float] | None = None,
    selic: float | None = 13.75,
    di_history_rates: list[float] | None = None,
) -> MagicMock:
    """Create a mock loader for CROSS-02 tests.

    Args:
        vix_closes: VIX close price history.
        cds_values: CDS 5Y history values.
        usdbrl_closes: USDBRL close prices.
        ibov_closes: IBOVESPA close prices.
        di_curve: DI_PRE curve dict.
        selic: Selic target rate.
        di_history_rates: DI curve history rates.
    """
    loader = MagicMock()

    if vix_closes is None:
        vix_closes = [18.0 + 2.0 * (i % 10 - 5) for i in range(300)]
    if cds_values is None:
        cds_values = [180.0 + 5.0 * (i % 20 - 10) for i in range(300)]
    if usdbrl_closes is None:
        usdbrl_closes = [5.0 + 0.1 * (i % 20 - 10) for i in range(300)]
    if ibov_closes is None:
        ibov_closes = [120000.0 + 1000.0 * (i % 20 - 10) for i in range(300)]
    if di_curve is None:
        di_curve = {63: 13.80, 126: 14.00, 252: 14.20}
    if di_history_rates is None:
        di_history_rates = [14.0 + 0.1 * (i % 10 - 5) for i in range(300)]

    vix_df = _make_market_df(vix_closes)
    usdbrl_df = _make_market_df(usdbrl_closes)
    ibov_df = _make_market_df(ibov_closes)
    cds_df = _make_macro_df(cds_values)

    def market_data_side_effect(ticker, as_of_date, lookback_days=756):
        if ticker == "^VIX":
            return vix_df
        if ticker == "USDBRL":
            return usdbrl_df
        if ticker == "IBOVESPA":
            return ibov_df
        return pd.DataFrame(
            columns=["date", "open", "high", "low", "close", "volume", "adjusted_close"],
        )

    loader.get_market_data.side_effect = market_data_side_effect

    def macro_series_side_effect(series_code, as_of_date, lookback_days=3650):
        if series_code == "BR_CDS_5Y":
            return cds_df
        return pd.DataFrame(columns=["date", "value", "release_time", "revision_number"])

    loader.get_macro_series.side_effect = macro_series_side_effect

    def macro_value_side_effect(series_code, as_of_date):
        if series_code == "BR_SELIC_TARGET":
            return selic
        return None

    loader.get_latest_macro_value.side_effect = macro_value_side_effect

    def curve_side_effect(curve_id, as_of_date):
        if curve_id == "DI_PRE":
            return di_curve
        return {}

    loader.get_curve.side_effect = curve_side_effect

    di_hist_df = _make_curve_history(di_history_rates)

    def curve_history_side_effect(curve_id, tenor, as_of, lookback_days=756):
        if curve_id == "DI_PRE":
            return di_hist_df
        return pd.DataFrame(columns=["date", "rate"])

    loader.get_curve_history.side_effect = curve_history_side_effect

    return loader


class TestCross02Registration:
    """CROSS-02 registration tests."""

    def test_registered_in_strategy_registry(self) -> None:
        assert "CROSS_02" in StrategyRegistry.list_all()

    def test_registered_with_cross_asset_class(self) -> None:
        strategies = StrategyRegistry.list_by_asset_class(AssetClass.CROSS_ASSET)
        assert "CROSS_02" in strategies


class TestCross02RiskOn:
    """CROSS-02 risk-on scenario tests."""

    def test_low_vix_low_cds_strong_momentum_risk_on(self) -> None:
        """Low VIX + low CDS + strong equity momentum => risk-on trades."""
        # VIX at historic lows => -vix_z strongly positive (risk-on)
        vix_closes = [30.0] * 280 + [28.0, 26.0, 24.0, 22.0, 20.0, 18.0, 16.0, 14.0, 12.0, 10.0,
                                      10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 8.0]

        # CDS declining sharply => -cds_z strongly positive
        cds_values = [250.0] * 280
        cds_values += [240.0, 230.0, 220.0, 210.0, 200.0, 190.0, 180.0, 170.0, 160.0, 150.0,
                       140.0, 130.0, 120.0, 110.0, 105.0, 100.0, 95.0, 90.0, 85.0, 80.0]

        # Strong equity momentum (sharply rising after flat base)
        ibov_closes = [100000.0] * 230 + [100000.0 + 1500.0 * i for i in range(70)]

        # Declining FX vol (declining USDBRL = stable BRL)
        usdbrl_closes = [5.50] * 230 + [5.50 - 0.01 * i for i in range(70)]

        # Tight funding spread: DI close to Selic
        di_curve_tight = {63: 13.76, 126: 13.80, 252: 13.85}

        loader = _make_cross02_loader(
            vix_closes=vix_closes,
            cds_values=cds_values,
            ibov_closes=ibov_closes,
            usdbrl_closes=usdbrl_closes,
            di_curve=di_curve_tight,
            selic=13.75,
        )
        strategy = Cross02RiskAppetiteStrategy(data_loader=loader)
        signals = strategy.generate_signals(date(2025, 6, 15))

        assert len(signals) >= 1
        # Risk-on: LONG equities, SHORT USDBRL, LONG DI
        instruments = [s.instruments[0] for s in signals]
        directions = {s.instruments[0]: s.direction for s in signals}

        if "IBOV_FUT" in instruments:
            assert directions["IBOV_FUT"] == SignalDirection.LONG

        # All signals should have risk_appetite in metadata
        for sig in signals:
            assert "risk_appetite" in sig.metadata
            assert sig.metadata["risk_appetite"] > 0


class TestCross02RiskOff:
    """CROSS-02 risk-off scenario tests."""

    def test_high_vix_high_cds_risk_off(self) -> None:
        """High VIX + high CDS + weak equity => risk-off trades."""
        # VIX at historic highs => vix_z positive => -vix_z negative
        vix_closes = [18.0 + 2.0 * (i % 10 - 5) for i in range(299)]
        vix_closes.append(40.0)  # Very high current VIX

        # CDS at historic highs
        cds_values = [180.0 + 5.0 * (i % 10 - 5) for i in range(299)]
        cds_values.append(350.0)  # Very high current CDS

        # Weak equity momentum (falling)
        ibov_closes = [150000.0 - 500.0 * i for i in range(300)]

        # High FX vol (rising USDBRL with jumps)
        usdbrl_closes = [4.5 + 0.02 * i + 0.1 * (i % 5) for i in range(300)]

        loader = _make_cross02_loader(
            vix_closes=vix_closes,
            cds_values=cds_values,
            ibov_closes=ibov_closes,
            usdbrl_closes=usdbrl_closes,
        )
        strategy = Cross02RiskAppetiteStrategy(data_loader=loader)
        signals = strategy.generate_signals(date(2025, 6, 15))

        assert len(signals) >= 1
        # Risk-off: SHORT equities, LONG USDBRL, SHORT DI
        instruments = [s.instruments[0] for s in signals]
        directions = {s.instruments[0]: s.direction for s in signals}

        if "IBOV_FUT" in instruments:
            assert directions["IBOV_FUT"] == SignalDirection.SHORT

        for sig in signals:
            assert sig.metadata["risk_appetite"] < 0


class TestCross02Neutral:
    """CROSS-02 neutral zone tests."""

    def test_neutral_when_risk_appetite_between_thresholds(self) -> None:
        """When indicators are mixed => neutral risk appetite => no signals."""
        # All indicators near their mean => z-scores near 0 => neutral
        vix_closes = [18.0] * 300
        cds_values = [180.0] * 300
        usdbrl_closes = [5.0] * 300
        ibov_closes = [120000.0] * 300

        loader = _make_cross02_loader(
            vix_closes=vix_closes,
            cds_values=cds_values,
            usdbrl_closes=usdbrl_closes,
            ibov_closes=ibov_closes,
        )
        strategy = Cross02RiskAppetiteStrategy(data_loader=loader)
        signals = strategy.generate_signals(date(2025, 6, 15))

        # With all values constant, z-scores should be 0 => neutral
        assert signals == []


class TestCross02MissingData:
    """CROSS-02 returns empty list when all data is missing."""

    def test_all_missing_returns_empty(self) -> None:
        loader = MagicMock()
        loader.get_market_data.return_value = pd.DataFrame(
            columns=["date", "open", "high", "low", "close", "volume", "adjusted_close"],
        )
        loader.get_macro_series.return_value = pd.DataFrame(
            columns=["date", "value", "release_time", "revision_number"],
        )
        loader.get_latest_macro_value.return_value = None
        loader.get_curve.return_value = {}
        loader.get_curve_history.return_value = pd.DataFrame(columns=["date", "rate"])

        strategy = Cross02RiskAppetiteStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

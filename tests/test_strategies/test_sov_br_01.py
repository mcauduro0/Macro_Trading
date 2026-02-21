"""Tests for SOV_BR_01 BR Fiscal Risk Premium strategy.

Uses mock PointInTimeDataLoader to test signal generation under various
fiscal risk and spread z-score scenarios.
"""

from datetime import date
from unittest.mock import MagicMock

import pandas as pd

from src.core.enums import SignalDirection
from src.strategies.sov_br_01_fiscal_risk import SovBR01FiscalRiskStrategy


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
def _make_curve_history(
    rates: list[float],
    base_date: str = "2023-01-02",
) -> pd.DataFrame:
    """Create a mock curve history DataFrame."""
    dates = pd.date_range(base_date, periods=len(rates), freq="B")
    df = pd.DataFrame({"rate": rates}, index=dates)
    df.index.name = "date"
    return df


def _make_mock_loader(
    debt_gdp: float | None = 78.0,
    primary_balance: float | None = -1.5,
    di_curve: dict[int, float] | None = None,
    cds_5y: float | None = None,
    ust_curve: dict[int, float] | None = None,
    di_history_rates: list[float] | None = None,
) -> MagicMock:
    """Create a mock PointInTimeDataLoader for SOV_BR_01 tests.

    Args:
        debt_gdp: BR gross debt-to-GDP ratio (None = missing).
        primary_balance: BR primary balance as % GDP (negative = deficit).
        di_curve: DI_PRE curve. Defaults to curve with long tenors.
        cds_5y: BR CDS 5Y in bps (None = use DI-UST fallback).
        ust_curve: UST_NOM curve for spread fallback.
        di_history_rates: DI curve history. Defaults to 300 points.
    """
    loader = MagicMock()

    if di_curve is None:
        di_curve = {126: 12.0, 365: 13.0, 756: 14.0, 1260: 14.5}

    def curve_side_effect(curve_id, as_of_date):
        if curve_id == "DI_PRE":
            return di_curve
        if curve_id == "UST_NOM":
            if ust_curve is not None:
                return ust_curve
            return {365: 4.50, 1260: 4.80}
        return {}

    loader.get_curve.side_effect = curve_side_effect

    # Macro values
    def macro_side_effect(series_code, as_of_date):
        if series_code == "BR_GROSS_DEBT_GDP":
            return debt_gdp
        if series_code == "BR_NET_DEBT_GDP":
            return debt_gdp
        if series_code == "BR_PRIMARY_BALANCE_GDP":
            return primary_balance
        if series_code == "BR_CDS_5Y":
            return cds_5y
        return None

    loader.get_latest_macro_value.side_effect = macro_side_effect

    # Market data (USDBRL)
    loader.get_market_data.return_value = pd.DataFrame(
        {"close": [5.0]},
        index=pd.to_datetime(["2025-06-15"]),
    )

    # Curve history for spread z-score
    if di_history_rates is None:
        di_history_rates = [14.0 + 0.1 * (i % 10 - 5) for i in range(300)]

    def history_side_effect(curve_id, tenor, as_of, lookback_days=756):
        if curve_id == "DI_PRE":
            return _make_curve_history(di_history_rates)
        return pd.DataFrame(columns=["date", "rate"])

    loader.get_curve_history.side_effect = history_side_effect

    return loader


# ---------------------------------------------------------------------------
# High fiscal risk + underpriced spread -> SHORT DI, LONG USDBRL
# ---------------------------------------------------------------------------
class TestSovBR01HighRiskUnderpriced:
    """High fiscal risk + spread below average -> fiscal dominance trade."""

    def test_short_di_long_usdbrl(self) -> None:
        """fiscal_risk > 0.6, spread_z < -1.5 -> SHORT DI + LONG USDBRL."""
        # Debt 90% GDP, deficit -3.0 -> high fiscal risk
        # DI long-end at 11.0 (below historical mean ~14.0) -> negative z-score
        loader = _make_mock_loader(
            debt_gdp=90.0,
            primary_balance=-3.0,
            di_curve={1260: 11.0},  # well below history mean
        )
        strategy = SovBR01FiscalRiskStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert len(positions) == 2
        # First position: SHORT DI
        di_pos = next(p for p in positions if "DI_PRE" in p.instrument)
        assert di_pos.direction == SignalDirection.SHORT
        assert di_pos.weight < 0

        # Second position: LONG USDBRL
        fx_pos = next(p for p in positions if p.instrument == "USDBRL")
        assert fx_pos.direction == SignalDirection.LONG
        assert fx_pos.weight > 0

    def test_metadata_contains_fiscal_info(self) -> None:
        """Positions should include fiscal risk metadata."""
        loader = _make_mock_loader(
            debt_gdp=90.0,
            primary_balance=-3.0,
            di_curve={1260: 11.0},
        )
        strategy = SovBR01FiscalRiskStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))

        if positions:
            meta = positions[0].metadata
            assert "fiscal_risk" in meta
            assert "spread_z" in meta
            assert "debt_gdp" in meta


# ---------------------------------------------------------------------------
# Low fiscal risk + overpriced spread -> LONG DI, SHORT USDBRL
# ---------------------------------------------------------------------------
class TestSovBR01LowRiskOverpriced:
    """Low fiscal risk + spread above average -> compression trade."""

    def test_long_di_short_usdbrl(self) -> None:
        """fiscal_risk < 0.3, spread_z > 1.5 -> LONG DI + SHORT USDBRL."""
        # Debt 55% GDP, surplus +2.0 -> low fiscal risk
        # DI long-end at 18.0 (above historical mean ~14.0) -> positive z-score
        loader = _make_mock_loader(
            debt_gdp=55.0,
            primary_balance=2.0,
            di_curve={1260: 18.0},  # well above history mean
        )
        strategy = SovBR01FiscalRiskStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert len(positions) == 2
        # First position: LONG DI
        di_pos = next(p for p in positions if "DI_PRE" in p.instrument)
        assert di_pos.direction == SignalDirection.LONG
        assert di_pos.weight > 0

        # Second position: SHORT USDBRL
        fx_pos = next(p for p in positions if p.instrument == "USDBRL")
        assert fx_pos.direction == SignalDirection.SHORT
        assert fx_pos.weight < 0


# ---------------------------------------------------------------------------
# Moderate fiscal risk or normal spread -> no position
# ---------------------------------------------------------------------------
class TestSovBR01Neutral:
    """Moderate conditions -> no position."""

    def test_moderate_risk_normal_spread_no_position(self) -> None:
        """fiscal_risk in [0.3, 0.6] or spread_z in [-1.5, 1.5] -> empty."""
        # Debt 75% GDP, small deficit -> moderate risk (~0.47)
        # DI at 14.0 (near mean) -> z-score ~0
        loader = _make_mock_loader(
            debt_gdp=75.0,
            primary_balance=-0.5,
            di_curve={1260: 14.0},
        )
        strategy = SovBR01FiscalRiskStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert positions == []

    def test_high_risk_but_spread_normal(self) -> None:
        """High fiscal risk but spread near average -> no trade."""
        loader = _make_mock_loader(
            debt_gdp=95.0,
            primary_balance=-3.0,
            di_curve={1260: 14.0},  # near mean
        )
        strategy = SovBR01FiscalRiskStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert positions == []

    def test_low_risk_but_spread_normal(self) -> None:
        """Low fiscal risk but spread near average -> no trade."""
        loader = _make_mock_loader(
            debt_gdp=50.0,
            primary_balance=3.0,
            di_curve={1260: 14.0},  # near mean
        )
        strategy = SovBR01FiscalRiskStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert positions == []


# ---------------------------------------------------------------------------
# Missing data edge cases
# ---------------------------------------------------------------------------
class TestSovBR01MissingData:
    """Missing data should return empty list."""

    def test_missing_debt_gdp_returns_empty(self) -> None:
        loader = _make_mock_loader(debt_gdp=None)
        strategy = SovBR01FiscalRiskStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_missing_primary_balance_returns_empty(self) -> None:
        loader = _make_mock_loader(primary_balance=None)
        strategy = SovBR01FiscalRiskStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_missing_di_curve_returns_empty(self) -> None:
        loader = _make_mock_loader(di_curve={})
        strategy = SovBR01FiscalRiskStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_insufficient_history_returns_empty(self) -> None:
        """Less than 60 history points -> empty list."""
        loader = _make_mock_loader(di_history_rates=[14.0] * 20)
        strategy = SovBR01FiscalRiskStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []


# ---------------------------------------------------------------------------
# Fiscal risk score computation
# ---------------------------------------------------------------------------
class TestSovBR01FiscalRisk:
    """Test fiscal risk score computation."""

    def test_high_debt_high_deficit_high_risk(self) -> None:
        """90% GDP debt, -3% deficit -> high fiscal risk."""
        loader = _make_mock_loader()
        strategy = SovBR01FiscalRiskStrategy(data_loader=loader)
        risk = strategy._compute_fiscal_risk(90.0, -3.0)
        assert risk > 0.6

    def test_low_debt_surplus_low_risk(self) -> None:
        """50% GDP debt, +2% surplus -> low fiscal risk."""
        loader = _make_mock_loader()
        strategy = SovBR01FiscalRiskStrategy(data_loader=loader)
        risk = strategy._compute_fiscal_risk(50.0, 2.0)
        assert risk < 0.3

    def test_risk_bounded_zero_one(self) -> None:
        """Fiscal risk must be in [0, 1]."""
        loader = _make_mock_loader()
        strategy = SovBR01FiscalRiskStrategy(data_loader=loader)

        # Extreme high
        risk_high = strategy._compute_fiscal_risk(120.0, -10.0)
        assert 0.0 <= risk_high <= 1.0

        # Extreme low
        risk_low = strategy._compute_fiscal_risk(30.0, 5.0)
        assert 0.0 <= risk_low <= 1.0


# ---------------------------------------------------------------------------
# Weight and confidence bounds
# ---------------------------------------------------------------------------
class TestSovBR01Bounds:
    """Output weight and confidence must be in valid ranges."""

    def test_weight_in_bounds(self) -> None:
        """Weight must be in [-1, 1]."""
        loader = _make_mock_loader(
            debt_gdp=95.0,
            primary_balance=-5.0,
            di_curve={1260: 11.0},
        )
        strategy = SovBR01FiscalRiskStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))

        for pos in positions:
            assert -1.0 <= pos.weight <= 1.0
            assert 0.0 <= pos.confidence <= 1.0


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
class TestSovBR01Config:
    """Test strategy configuration."""

    def test_strategy_id(self) -> None:
        loader = _make_mock_loader()
        strategy = SovBR01FiscalRiskStrategy(data_loader=loader)
        assert strategy.strategy_id == "SOV_BR_01"

    def test_config_values(self) -> None:
        loader = _make_mock_loader()
        strategy = SovBR01FiscalRiskStrategy(data_loader=loader)
        assert strategy.config.stop_loss_pct == 0.05
        assert strategy.config.take_profit_pct == 0.12
        assert strategy.config.instruments == ["DI_PRE", "USDBRL"]

"""Tests for CUPOM_01 CIP Basis Mean Reversion strategy.

Uses mock PointInTimeDataLoader to test signal generation under various
CIP basis z-score scenarios.
"""

from datetime import date
from unittest.mock import MagicMock

import pandas as pd

from src.core.enums import SignalDirection
from src.strategies.cupom_01_cip_basis import Cupom01CipBasisStrategy


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
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


def _make_mock_loader(
    di_curve: dict[int, float] | None = None,
    ust_curve: dict[int, float] | None = None,
    sofr_rate: float | None = 5.30,
    di_history_rates: list[float] | None = None,
    ust_history_rates: list[float] | None = None,
) -> MagicMock:
    """Create a mock PointInTimeDataLoader for CUPOM_01 tests.

    Args:
        di_curve: DI_PRE curve. Defaults to curve with ~1Y tenor.
        ust_curve: UST_NOM curve. Defaults to curve with ~1Y tenor.
        sofr_rate: SOFR rate (None = missing).
        di_history_rates: DI curve history for 1Y tenor. Defaults to 300 points.
        ust_history_rates: UST curve history for 1Y tenor. Defaults to 300 points.
    """
    loader = MagicMock()

    if di_curve is None:
        di_curve = {126: 12.0, 365: 13.0, 504: 13.5}
    if ust_curve is None:
        ust_curve = {365: 4.50, 730: 4.75}

    def curve_side_effect(curve_id, as_of_date):
        if curve_id == "DI_PRE":
            return di_curve
        if curve_id == "UST_NOM":
            return ust_curve
        return {}

    loader.get_curve.side_effect = curve_side_effect

    # Macro values (SOFR)
    def macro_side_effect(series_code, as_of_date):
        if series_code in ("US_SOFR", "US_FED_FUNDS"):
            return sofr_rate
        return None

    loader.get_latest_macro_value.side_effect = macro_side_effect

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


# ---------------------------------------------------------------------------
# Short basis (z-score > threshold -> basis extremely wide)
# ---------------------------------------------------------------------------
class TestCupom01ShortBasis:
    """Basis z-score > threshold -> SHORT basis position."""

    def test_short_when_basis_extremely_wide(self) -> None:
        """Extremely wide basis (high z-score) -> SHORT basis."""
        # DI_1Y=16.0, UST_1Y=4.50, SOFR=5.30
        # cupom = 16.0 - 4.50 = 11.50
        # basis = 11.50 - 5.30 = 6.20
        # Historical basis: DI ~13.0 - UST ~4.50 - SOFR 5.30 = ~3.20
        # Z-score should be positive and large
        loader = _make_mock_loader(
            di_curve={365: 16.0},
            ust_curve={365: 4.50},
            sofr_rate=5.30,
        )
        strategy = Cupom01CipBasisStrategy(data_loader=loader, basis_z_threshold=2.0)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert len(positions) == 1
        pos = positions[0]
        assert pos.direction == SignalDirection.SHORT
        assert pos.weight < 0  # SHORT => negative weight
        assert 0.0 <= pos.confidence <= 1.0
        assert pos.strategy_id == "CUPOM_01"


# ---------------------------------------------------------------------------
# Long basis (z-score < -threshold -> basis extremely narrow)
# ---------------------------------------------------------------------------
class TestCupom01LongBasis:
    """Basis z-score < -threshold -> LONG basis position."""

    def test_long_when_basis_extremely_narrow(self) -> None:
        """Extremely narrow basis (low z-score) -> LONG basis."""
        # DI_1Y=10.0, UST_1Y=4.50, SOFR=5.30
        # cupom = 10.0 - 4.50 = 5.50
        # basis = 5.50 - 5.30 = 0.20
        # Historical basis: ~3.20
        # Z-score should be negative and large
        loader = _make_mock_loader(
            di_curve={365: 10.0},
            ust_curve={365: 4.50},
            sofr_rate=5.30,
        )
        strategy = Cupom01CipBasisStrategy(data_loader=loader, basis_z_threshold=2.0)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert len(positions) == 1
        pos = positions[0]
        assert pos.direction == SignalDirection.LONG
        assert pos.weight > 0  # LONG => positive weight


# ---------------------------------------------------------------------------
# Neutral (within threshold)
# ---------------------------------------------------------------------------
class TestCupom01Neutral:
    """Basis within threshold -> no position."""

    def test_within_threshold_no_position(self) -> None:
        """Basis z-score within threshold -> empty list."""
        # DI_1Y=13.0 (same as history mean), so z-score ~ 0
        loader = _make_mock_loader(
            di_curve={365: 13.0},
            ust_curve={365: 4.50},
            sofr_rate=5.30,
        )
        strategy = Cupom01CipBasisStrategy(data_loader=loader, basis_z_threshold=2.0)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert positions == []


# ---------------------------------------------------------------------------
# Missing data edge cases
# ---------------------------------------------------------------------------
class TestCupom01MissingData:
    """Missing data should return empty list."""

    def test_missing_di_curve_returns_empty(self) -> None:
        loader = _make_mock_loader(di_curve={})
        strategy = Cupom01CipBasisStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_missing_ust_curve_returns_empty(self) -> None:
        loader = _make_mock_loader(ust_curve={})
        strategy = Cupom01CipBasisStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_missing_sofr_returns_empty(self) -> None:
        loader = _make_mock_loader(sofr_rate=None)
        strategy = Cupom01CipBasisStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_no_matching_1y_tenor_returns_empty(self) -> None:
        """Curves with no tenor near 365 days."""
        loader = _make_mock_loader(
            di_curve={21: 10.0, 42: 10.5},
            ust_curve={365: 4.50},
        )
        strategy = Cupom01CipBasisStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_insufficient_history_returns_empty(self) -> None:
        """Less than 60 history points -> empty list."""
        loader = _make_mock_loader(
            di_history_rates=[13.0] * 20,
            ust_history_rates=[4.50] * 20,
        )
        strategy = Cupom01CipBasisStrategy(data_loader=loader)
        assert strategy.generate_signals(date(2025, 6, 15)) == []


# ---------------------------------------------------------------------------
# Weight and confidence bounds
# ---------------------------------------------------------------------------
class TestCupom01Bounds:
    """Output weight and confidence must be in valid ranges."""

    def test_weight_in_bounds(self) -> None:
        """Weight must be in [-1, 1]."""
        loader = _make_mock_loader(di_curve={365: 20.0})
        strategy = Cupom01CipBasisStrategy(data_loader=loader, basis_z_threshold=1.0)
        positions = strategy.generate_signals(date(2025, 6, 15))

        if positions:
            pos = positions[0]
            assert -1.0 <= pos.weight <= 1.0
            assert 0.0 <= pos.confidence <= 1.0

    def test_custom_threshold(self) -> None:
        """Custom z-score threshold should be respected."""
        # With threshold=1.0, normal z-score ~2 would trigger
        loader = _make_mock_loader(di_curve={365: 16.0})
        strategy = Cupom01CipBasisStrategy(
            data_loader=loader,
            basis_z_threshold=1.0,
        )
        positions = strategy.generate_signals(date(2025, 6, 15))
        # Should trigger since z-score > 1.0
        assert len(positions) >= 1


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
class TestCupom01Config:
    """Test strategy configuration."""

    def test_strategy_id(self) -> None:
        loader = _make_mock_loader()
        strategy = Cupom01CipBasisStrategy(data_loader=loader)
        assert strategy.strategy_id == "CUPOM_01"

    def test_config_values(self) -> None:
        loader = _make_mock_loader()
        strategy = Cupom01CipBasisStrategy(data_loader=loader)
        assert strategy.config.stop_loss_pct == 0.03
        assert strategy.config.take_profit_pct == 0.06
        assert strategy.config.instruments == ["DI_PRE", "USDBRL"]

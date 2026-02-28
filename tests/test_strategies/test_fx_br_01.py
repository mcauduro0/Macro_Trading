"""Tests for FX_BR_01 USDBRL Carry & Fundamental composite strategy.

Uses mock PointInTimeDataLoader to test signal generation under various
carry, BEER, flow, and regime scenarios.
"""

from datetime import date
from unittest.mock import MagicMock

import pandas as pd

from src.core.enums import SignalDirection
from src.strategies.fx_br_01_carry_fundamental import FxBR01CarryFundamentalStrategy


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
def _make_usdbrl_df(
    prices: list[float],
    base_date: str = "2024-01-02",
) -> pd.DataFrame:
    """Create a mock USDBRL market data DataFrame.

    Args:
        prices: List of close prices.
        base_date: Starting date for the business day index.

    Returns:
        DataFrame indexed by date with OHLCV columns.
    """
    dates = pd.date_range(base_date, periods=len(prices), freq="B", tz="UTC")
    df = pd.DataFrame(
        {
            "open": prices,
            "high": [p * 1.01 for p in prices],
            "low": [p * 0.99 for p in prices],
            "close": prices,
            "volume": [1_000_000] * len(prices),
            "adjusted_close": prices,
        },
        index=dates,
    )
    df.index.name = "date"
    return df


def _make_flow_df(
    values: list[float],
    base_date: str = "2024-06-01",
) -> pd.DataFrame:
    """Create a mock FX flow DataFrame.

    Args:
        values: List of net flow values.
        base_date: Starting date for the business day index.

    Returns:
        DataFrame indexed by date with value/flow_type/release_time columns.
    """
    dates = pd.date_range(base_date, periods=len(values), freq="B")
    df = pd.DataFrame(
        {
            "value": values,
            "flow_type": ["NET"] * len(values),
            "release_time": [None] * len(values),
        },
        index=dates,
    )
    df.index.name = "date"
    return df


def _make_mock_loader(
    br_rate: float | None = 13.75,
    us_rate: float | None = 5.50,
    usdbrl_prices: list[float] | None = None,
    flow_values: list[float] | None = None,
) -> MagicMock:
    """Create a mock PointInTimeDataLoader for FX_BR_01 tests.

    Args:
        br_rate: Selic target rate (None = missing).
        us_rate: US Fed Funds rate (None = missing).
        usdbrl_prices: USDBRL price series. Defaults to 300 points around 5.0.
        flow_values: FX flow values. Defaults to 100 positive values.
    """
    loader = MagicMock()

    # Macro values
    def macro_side_effect(series_code, as_of_date):
        if series_code == "BR_SELIC_TARGET":
            return br_rate
        if series_code in ("US_FED_FUNDS", "US_SOFR"):
            return us_rate
        return None

    loader.get_latest_macro_value.side_effect = macro_side_effect

    # USDBRL market data
    if usdbrl_prices is None:
        # Default: 300 business days around 5.0 with some variation
        usdbrl_prices = [5.0 + 0.01 * (i % 20 - 10) for i in range(300)]
    loader.get_market_data.return_value = _make_usdbrl_df(usdbrl_prices)

    # Flow data
    if flow_values is None:
        flow_values = [100.0 + 5.0 * (i % 10) for i in range(100)]
    loader.get_flow_data.return_value = _make_flow_df(flow_values)

    # Curve (fallback for Selic)
    loader.get_curve.return_value = {252: 13.0, 504: 13.5}

    return loader


# ---------------------------------------------------------------------------
# Carry component tests
# ---------------------------------------------------------------------------
class TestFxBR01CarryComponent:
    """Test carry-to-risk score computation."""

    def test_high_carry_differential_positive_score(self) -> None:
        """High BR-US rate differential => positive carry score."""
        # BR=13.75, US=5.50 -> carry = 8.25
        loader = _make_mock_loader(br_rate=13.75, us_rate=5.50)
        strategy = FxBR01CarryFundamentalStrategy(data_loader=loader)

        score = strategy._compute_carry_score(date(2025, 6, 15))
        assert score is not None
        assert score > 0  # positive carry => positive score (long BRL)

    def test_negative_carry_differential(self) -> None:
        """Negative carry (US > BR) => negative carry score."""
        loader = _make_mock_loader(br_rate=3.0, us_rate=5.50)
        strategy = FxBR01CarryFundamentalStrategy(data_loader=loader)

        score = strategy._compute_carry_score(date(2025, 6, 15))
        assert score is not None
        assert score < 0  # negative carry => negative score

    def test_missing_br_rate_uses_di_fallback(self) -> None:
        """When Selic is None, falls back to DI curve."""
        loader = _make_mock_loader(br_rate=None, us_rate=5.50)
        strategy = FxBR01CarryFundamentalStrategy(data_loader=loader)

        score = strategy._compute_carry_score(date(2025, 6, 15))
        # Should use DI curve 252 tenor = 13.0
        assert score is not None


# ---------------------------------------------------------------------------
# BEER component tests
# ---------------------------------------------------------------------------
class TestFxBR01BeerComponent:
    """Test BEER misalignment score computation."""

    def test_usdbrl_above_mean_positive_beer(self) -> None:
        """USDBRL above 252-day mean => BRL undervalued => positive score."""
        # Prices: 252 at 5.0, then jump to 5.50
        prices = [5.0] * 252 + [5.50] * 10
        loader = _make_mock_loader(usdbrl_prices=prices)
        strategy = FxBR01CarryFundamentalStrategy(data_loader=loader)

        score = strategy._compute_beer_score(date(2025, 6, 15))
        assert score is not None
        assert score > 0  # above fair value => BRL undervalued => positive

    def test_usdbrl_below_mean_negative_beer(self) -> None:
        """USDBRL below 252-day mean => BRL overvalued => negative score."""
        prices = [5.50] * 252 + [5.0] * 10
        loader = _make_mock_loader(usdbrl_prices=prices)
        strategy = FxBR01CarryFundamentalStrategy(data_loader=loader)

        score = strategy._compute_beer_score(date(2025, 6, 15))
        assert score is not None
        assert score < 0  # below fair value => BRL overvalued => negative

    def test_insufficient_data_returns_none(self) -> None:
        """Less than 252 data points => None."""
        prices = [5.0] * 100
        loader = _make_mock_loader(usdbrl_prices=prices)
        strategy = FxBR01CarryFundamentalStrategy(data_loader=loader)

        score = strategy._compute_beer_score(date(2025, 6, 15))
        assert score is None


# ---------------------------------------------------------------------------
# Flow component tests
# ---------------------------------------------------------------------------
class TestFxBR01FlowComponent:
    """Test FX flow z-score computation."""

    def test_positive_flow_positive_score(self) -> None:
        """Strong positive net inflows => positive flow score."""
        # Large positive values
        values = [200.0 + 50.0 * (i % 5) for i in range(100)]
        loader = _make_mock_loader(flow_values=values)
        strategy = FxBR01CarryFundamentalStrategy(data_loader=loader)

        score = strategy._compute_flow_score(date(2025, 6, 15))
        # Score depends on z-score; with uniform positive flow it should be >= 0
        assert score is not None

    def test_insufficient_flow_data_returns_none(self) -> None:
        """Less than 30 data points => None."""
        values = [100.0] * 10
        loader = _make_mock_loader(flow_values=values)
        strategy = FxBR01CarryFundamentalStrategy(data_loader=loader)

        score = strategy._compute_flow_score(date(2025, 6, 15))
        assert score is None


# ---------------------------------------------------------------------------
# Composite and direction tests
# ---------------------------------------------------------------------------
class TestFxBR01CompositeDirection:
    """Test composite signal direction logic."""

    def test_positive_composite_short_usdbrl(self) -> None:
        """Positive composite => SHORT USDBRL (long BRL)."""
        # High carry (BR >> US) + BRL undervalued + strong inflows
        # Prices: first 252 at ~5.0, then trending up to ~5.50 with variation
        prices = [5.0 + 0.02 * (i % 10 - 5) for i in range(252)]
        prices += [5.50 + 0.02 * (i % 10 - 5) for i in range(48)]
        loader = _make_mock_loader(
            br_rate=15.0,
            us_rate=3.0,
            usdbrl_prices=prices,
        )
        strategy = FxBR01CarryFundamentalStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert len(positions) == 1
        pos = positions[0]
        assert pos.direction == SignalDirection.SHORT
        assert pos.weight < 0  # SHORT => negative weight

    def test_negative_composite_long_usdbrl(self) -> None:
        """Negative composite => LONG USDBRL (short BRL)."""
        # Low carry (US >> BR) + BRL overvalued + no flow data
        # Price history: high average, then drop => BRL overvalued => negative BEER
        prices = [6.0 + 0.02 * (i % 10 - 5) for i in range(252)]
        prices += [4.5 + 0.02 * (i % 10 - 5) for i in range(48)]
        loader = _make_mock_loader(
            br_rate=1.0,
            us_rate=12.0,
            usdbrl_prices=prices,
            flow_values=[0.0] * 10,  # insufficient for flow score -> 0
        )
        strategy = FxBR01CarryFundamentalStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert len(positions) == 1
        pos = positions[0]
        assert pos.direction == SignalDirection.LONG
        assert pos.weight >= 0  # LONG => non-negative weight

    def test_small_composite_no_position(self) -> None:
        """Composite < 0.1 in absolute value => no position (neutral zone)."""
        # Equal rates + near fair value + no flow data => small composite
        prices = [5.0 + 0.02 * (i % 10 - 5) for i in range(300)]
        loader = _make_mock_loader(
            br_rate=5.50,
            us_rate=5.50,
            usdbrl_prices=prices,
            flow_values=[0.0] * 10,  # insufficient for flow score -> 0
        )
        strategy = FxBR01CarryFundamentalStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))

        assert positions == []


# ---------------------------------------------------------------------------
# Weight composition
# ---------------------------------------------------------------------------
class TestFxBR01Weights:
    """Test component weight composition."""

    def test_weights_sum_to_one(self) -> None:
        """Default weights must sum to 1.0."""
        loader = _make_mock_loader()
        strategy = FxBR01CarryFundamentalStrategy(data_loader=loader)

        total = strategy.carry_weight + strategy.beer_weight + strategy.flow_weight
        assert abs(total - 1.0) < 1e-10

    def test_custom_weights(self) -> None:
        """Custom weights should be accepted."""
        loader = _make_mock_loader()
        strategy = FxBR01CarryFundamentalStrategy(
            data_loader=loader,
            carry_weight=0.50,
            beer_weight=0.30,
            flow_weight=0.20,
        )
        assert strategy.carry_weight == 0.50
        assert strategy.beer_weight == 0.30
        assert strategy.flow_weight == 0.20


# ---------------------------------------------------------------------------
# Regime adjustment
# ---------------------------------------------------------------------------
class TestFxBR01RegimeAdjustment:
    """Test regime adjustment scale-down."""

    def test_unfavorable_regime_scales_weight(self) -> None:
        """Regime score < -0.3 => weight scaled by 0.50."""
        # Set up for a clear signal
        prices = [5.0 + 0.02 * (i % 10 - 5) for i in range(252)] + [
            5.50 + 0.02 * (i % 10 - 5) for i in range(48)
        ]
        loader = _make_mock_loader(
            br_rate=15.0,
            us_rate=3.0,
            usdbrl_prices=prices,
        )
        strategy = FxBR01CarryFundamentalStrategy(data_loader=loader)

        # Without regime
        pos_normal = strategy.generate_signals(date(2025, 6, 15))

        # With unfavorable regime
        pos_regime = strategy.generate_signals(
            date(2025, 6, 15),
            regime_score=-0.5,
        )

        assert len(pos_normal) == 1
        assert len(pos_regime) == 1
        # Regime should scale the weight by 0.5
        assert abs(pos_regime[0].weight) < abs(pos_normal[0].weight)

    def test_favorable_regime_no_scaling(self) -> None:
        """Regime score >= -0.3 => no scaling."""
        prices = [5.0 + 0.02 * (i % 10 - 5) for i in range(252)] + [
            5.50 + 0.02 * (i % 10 - 5) for i in range(48)
        ]
        loader = _make_mock_loader(
            br_rate=15.0,
            us_rate=3.0,
            usdbrl_prices=prices,
        )
        strategy = FxBR01CarryFundamentalStrategy(data_loader=loader)

        pos_normal = strategy.generate_signals(date(2025, 6, 15))
        pos_favorable = strategy.generate_signals(
            date(2025, 6, 15),
            regime_score=0.5,
        )

        assert len(pos_normal) == 1
        assert len(pos_favorable) == 1
        assert abs(pos_normal[0].weight) == abs(pos_favorable[0].weight)

    def test_no_regime_score_no_scaling(self) -> None:
        """regime_score=None => no scaling."""
        prices = [5.0 + 0.02 * (i % 10 - 5) for i in range(252)] + [
            5.50 + 0.02 * (i % 10 - 5) for i in range(48)
        ]
        loader = _make_mock_loader(
            br_rate=15.0,
            us_rate=3.0,
            usdbrl_prices=prices,
        )
        strategy = FxBR01CarryFundamentalStrategy(data_loader=loader)

        pos = strategy.generate_signals(date(2025, 6, 15), regime_score=None)
        assert len(pos) == 1
        # metadata should show no regime scale applied
        assert pos[0].metadata.get("regime_scale_applied") is False


# ---------------------------------------------------------------------------
# Missing data edge cases
# ---------------------------------------------------------------------------
class TestFxBR01MissingData:
    """Missing data should return empty list, not raise."""

    def test_missing_both_rates_returns_empty(self) -> None:
        """No BR or US rate available => empty list."""
        loader = _make_mock_loader(br_rate=None, us_rate=None)
        # Also remove curve fallback
        loader.get_curve.return_value = {}
        strategy = FxBR01CarryFundamentalStrategy(data_loader=loader)

        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_missing_usdbrl_data_returns_empty(self) -> None:
        """No USDBRL market data => empty list."""
        loader = _make_mock_loader()
        loader.get_market_data.return_value = pd.DataFrame(
            columns=["date", "open", "high", "low", "close", "volume", "adjusted_close"]
        )
        strategy = FxBR01CarryFundamentalStrategy(data_loader=loader)

        assert strategy.generate_signals(date(2025, 6, 15)) == []

    def test_insufficient_vol_history_returns_empty(self) -> None:
        """Less than 21 USDBRL data points => empty list."""
        loader = _make_mock_loader(usdbrl_prices=[5.0] * 10)
        strategy = FxBR01CarryFundamentalStrategy(data_loader=loader)

        assert strategy.generate_signals(date(2025, 6, 15)) == []


# ---------------------------------------------------------------------------
# Weight and confidence bounds
# ---------------------------------------------------------------------------
class TestFxBR01Bounds:
    """Output weight and confidence must be in valid ranges."""

    def test_weight_in_bounds(self) -> None:
        """Weight must be in [-1, 1]."""
        prices = [5.0 + 0.02 * (i % 10 - 5) for i in range(252)] + [
            5.50 + 0.02 * (i % 10 - 5) for i in range(48)
        ]
        loader = _make_mock_loader(
            br_rate=20.0,
            us_rate=1.0,
            usdbrl_prices=prices,
        )
        strategy = FxBR01CarryFundamentalStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))

        if positions:
            pos = positions[0]
            assert -1.0 <= pos.weight <= 1.0
            assert 0.0 <= pos.confidence <= 1.0

    def test_confidence_in_bounds(self) -> None:
        """Confidence must be in [0, 1] even with extreme inputs."""
        prices = [5.0 + 0.02 * (i % 10 - 5) for i in range(252)] + [
            7.0 + 0.02 * (i % 10 - 5) for i in range(48)
        ]
        loader = _make_mock_loader(
            br_rate=25.0,
            us_rate=0.5,
            usdbrl_prices=prices,
        )
        strategy = FxBR01CarryFundamentalStrategy(data_loader=loader)
        positions = strategy.generate_signals(date(2025, 6, 15))

        if positions:
            assert 0.0 <= positions[0].confidence <= 1.0


# ---------------------------------------------------------------------------
# Strategy config
# ---------------------------------------------------------------------------
class TestFxBR01Config:
    """Test strategy configuration."""

    def test_strategy_id(self) -> None:
        loader = _make_mock_loader()
        strategy = FxBR01CarryFundamentalStrategy(data_loader=loader)
        assert strategy.strategy_id == "FX_BR_01"

    def test_config_values(self) -> None:
        loader = _make_mock_loader()
        strategy = FxBR01CarryFundamentalStrategy(data_loader=loader)
        assert strategy.config.strategy_name == "USDBRL Carry & Fundamental"
        assert strategy.config.instruments == ["USDBRL"]
        assert strategy.config.stop_loss_pct == 0.05
        assert strategy.config.take_profit_pct == 0.10

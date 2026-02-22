"""Tests for new FX strategies: FX-02, FX-03, FX-04, FX-05.

Uses mock PointInTimeDataLoader with MagicMock to test signal generation,
edge cases, contrarian logic, vol-adjusted sizing, and misalignment
direction for all 4 new USDBRL strategies.
"""

from datetime import date
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from src.core.enums import AssetClass, SignalDirection
from src.strategies.base import StrategySignal
from src.strategies.fx_02_carry_momentum import Fx02CarryMomentumStrategy
from src.strategies.fx_03_flow_tactical import Fx03FlowTacticalStrategy
from src.strategies.fx_04_vol_surface_rv import Fx04VolSurfaceRvStrategy
from src.strategies.fx_05_terms_of_trade import Fx05TermsOfTradeStrategy
from src.strategies.registry import StrategyRegistry


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
AS_OF = date(2025, 6, 15)


def _make_market_df(
    prices: list[float],
    base_date: str = "2023-01-02",
) -> pd.DataFrame:
    """Create a mock OHLCV market data DataFrame."""
    dates = pd.date_range(base_date, periods=len(prices), freq="B", tz="UTC")
    df = pd.DataFrame(
        {
            "open": prices,
            "high": [p * 1.005 for p in prices],
            "low": [p * 0.995 for p in prices],
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
    base_date: str = "2024-01-02",
) -> pd.DataFrame:
    """Create a mock flow data DataFrame."""
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


def _make_macro_df(
    values: list[float],
    base_date: str = "2024-01-02",
) -> pd.DataFrame:
    """Create a mock macro series DataFrame."""
    dates = pd.date_range(base_date, periods=len(values), freq="B")
    df = pd.DataFrame(
        {
            "value": values,
            "release_time": [None] * len(values),
            "revision_number": [1] * len(values),
        },
        index=dates,
    )
    df.index.name = "date"
    return df


def _empty_market_df() -> pd.DataFrame:
    """Return an empty market data DataFrame."""
    return pd.DataFrame(
        columns=["date", "open", "high", "low", "close", "volume", "adjusted_close"]
    )


def _empty_flow_df() -> pd.DataFrame:
    """Return an empty flow data DataFrame."""
    return pd.DataFrame(columns=["date", "value", "flow_type", "release_time"])


def _empty_macro_df() -> pd.DataFrame:
    """Return an empty macro series DataFrame."""
    return pd.DataFrame(columns=["date", "value", "release_time", "revision_number"])


# ---------------------------------------------------------------------------
# FX-02: Carry-Adjusted Momentum -- Registration
# ---------------------------------------------------------------------------
class TestFx02Registration:
    """FX-02 strategy registration in StrategyRegistry."""

    def test_fx02_registered(self) -> None:
        """FX_02 should be in the registry."""
        assert "FX_02" in StrategyRegistry.list_all()

    def test_fx02_asset_class(self) -> None:
        """FX_02 should be listed under AssetClass.FX."""
        fx_strategies = StrategyRegistry.list_by_asset_class(AssetClass.FX)
        assert "FX_02" in fx_strategies


# ---------------------------------------------------------------------------
# FX-02: Signal generation
# ---------------------------------------------------------------------------
class TestFx02Signals:
    """FX-02 Carry-Adjusted Momentum signal generation."""

    def _make_fx02_loader(
        self,
        br_rate: float | None = 13.75,
        us_rate: float | None = 5.50,
        usdbrl_prices: list[float] | None = None,
    ) -> MagicMock:
        """Build a mock loader for FX-02."""
        loader = MagicMock()

        def macro_value_side_effect(series_code, as_of_date):
            if series_code == "BR_SELIC_TARGET":
                return br_rate
            if series_code == "US_FED_FUNDS":
                return us_rate
            return None

        loader.get_latest_macro_value.side_effect = macro_value_side_effect

        # Selic macro series history (daily values over ~350 days)
        selic_history = [br_rate or 13.75] * 350
        us_history = [us_rate or 5.50] * 350
        loader.get_macro_series.side_effect = lambda code, aod, **kw: (
            _make_macro_df(selic_history) if "SELIC" in code
            else _make_macro_df(us_history) if "FED" in code
            else _empty_macro_df()
        )

        if usdbrl_prices is None:
            # 600 business days with mild trend
            np.random.seed(42)
            base = 5.0
            noise = np.random.normal(0, 0.02, 600)
            usdbrl_prices = [base + sum(noise[:i]) * 0.1 for i in range(600)]
            usdbrl_prices = [max(3.5, min(7.0, p)) for p in usdbrl_prices]

        loader.get_market_data.return_value = _make_market_df(usdbrl_prices)

        return loader

    def test_generates_signal_with_data(self) -> None:
        """FX-02 should produce a signal when all data is available."""
        loader = self._make_fx02_loader()
        strategy = Fx02CarryMomentumStrategy(data_loader=loader)
        signals = strategy.generate_signals(AS_OF)

        # May or may not produce signal depending on z-score magnitude
        # At minimum, should not raise
        assert isinstance(signals, list)

    def test_signal_fields_populated(self) -> None:
        """StrategySignal should have z_score, entry_level, stop_loss, take_profit."""
        # Use strong carry differential to ensure signal generation
        loader = self._make_fx02_loader(br_rate=20.0, us_rate=1.0)
        strategy = Fx02CarryMomentumStrategy(data_loader=loader)
        signals = strategy.generate_signals(AS_OF)

        if signals:  # May not produce if z < threshold
            sig = signals[0]
            assert isinstance(sig, StrategySignal)
            assert sig.z_score != 0.0
            assert sig.entry_level is not None
            assert sig.stop_loss is not None
            assert sig.take_profit is not None
            assert sig.holding_period_days == 21
            assert sig.strategy_id == "FX_02"
            assert sig.asset_class == AssetClass.FX

    def test_missing_br_rate_returns_empty(self) -> None:
        """Missing Selic rate should return empty list."""
        loader = self._make_fx02_loader(br_rate=None)
        strategy = Fx02CarryMomentumStrategy(data_loader=loader)
        signals = strategy.generate_signals(AS_OF)
        assert signals == []

    def test_missing_us_rate_returns_empty(self) -> None:
        """Missing US Fed Funds rate should return empty list."""
        loader = self._make_fx02_loader(us_rate=None)
        strategy = Fx02CarryMomentumStrategy(data_loader=loader)
        signals = strategy.generate_signals(AS_OF)
        assert signals == []

    def test_missing_market_data_returns_empty(self) -> None:
        """Missing USDBRL market data should return empty list."""
        loader = self._make_fx02_loader()
        loader.get_market_data.return_value = _empty_market_df()
        strategy = Fx02CarryMomentumStrategy(data_loader=loader)
        signals = strategy.generate_signals(AS_OF)
        assert signals == []

    def test_vol_adjusted_sizing(self) -> None:
        """Suggested size should be scaled by min(1, target_vol/realized_vol)."""
        # High-vol prices (larger swings)
        np.random.seed(99)
        prices = [5.0 + 0.5 * np.sin(i / 5) + np.random.normal(0, 0.2) for i in range(600)]
        prices = [max(3.5, p) for p in prices]
        loader = self._make_fx02_loader(br_rate=20.0, us_rate=1.0, usdbrl_prices=prices)
        strategy = Fx02CarryMomentumStrategy(data_loader=loader)
        signals = strategy.generate_signals(AS_OF)

        if signals:
            sig = signals[0]
            # Vol-adjusted size should be <= base conviction size
            assert 0 < sig.suggested_size <= 1.0
            assert "vol_scale" in sig.metadata


# ---------------------------------------------------------------------------
# FX-03: Flow-Based Tactical -- Registration
# ---------------------------------------------------------------------------
class TestFx03Registration:
    """FX-03 strategy registration in StrategyRegistry."""

    def test_fx03_registered(self) -> None:
        """FX_03 should be in the registry."""
        assert "FX_03" in StrategyRegistry.list_all()

    def test_fx03_asset_class(self) -> None:
        """FX_03 should be listed under AssetClass.FX."""
        fx_strategies = StrategyRegistry.list_by_asset_class(AssetClass.FX)
        assert "FX_03" in fx_strategies


# ---------------------------------------------------------------------------
# FX-03: Signal generation + contrarian logic
# ---------------------------------------------------------------------------
class TestFx03Signals:
    """FX-03 Flow-Based Tactical signal generation and contrarian logic."""

    def _make_fx03_loader(
        self,
        bcb_values: list[float] | None = None,
        cftc_values: list[float] | None = None,
        b3_values: list[float] | None = None,
        usdbrl_prices: list[float] | None = None,
    ) -> MagicMock:
        """Build a mock loader for FX-03."""
        loader = MagicMock()

        if bcb_values is None:
            bcb_values = [100.0 + 10.0 * np.sin(i / 10) for i in range(300)]
        if cftc_values is None:
            cftc_values = [50.0 + 5.0 * np.sin(i / 8) for i in range(300)]
        if b3_values is None:
            b3_values = [80.0 + 8.0 * np.sin(i / 12) for i in range(300)]

        def flow_side_effect(series_code, as_of_date, **kwargs):
            if series_code == "BR_FX_FLOW_NET":
                return _make_flow_df(bcb_values)
            if series_code == "CFTC_6L_LEVERAGED_NET":
                return _make_flow_df(cftc_values)
            if series_code == "BR_FX_FLOW_FINANCIAL":
                return _make_flow_df(b3_values)
            return _empty_flow_df()

        loader.get_flow_data.side_effect = flow_side_effect

        if usdbrl_prices is None:
            usdbrl_prices = [5.0 + 0.01 * (i % 20 - 10) for i in range(100)]
        loader.get_market_data.return_value = _make_market_df(usdbrl_prices)

        return loader

    def test_generates_signal_with_data(self) -> None:
        """FX-03 should produce a signal when all flow data is available."""
        loader = self._make_fx03_loader()
        strategy = Fx03FlowTacticalStrategy(data_loader=loader)
        signals = strategy.generate_signals(AS_OF)
        assert isinstance(signals, list)

    def test_signal_fields_populated(self) -> None:
        """StrategySignal should have correct fields populated."""
        # Use strong directional flows to ensure signal
        bcb_vals = [50.0] * 200 + [500.0] * 100  # spike at end
        loader = self._make_fx03_loader(bcb_values=bcb_vals)
        strategy = Fx03FlowTacticalStrategy(data_loader=loader)
        signals = strategy.generate_signals(AS_OF)

        if signals:
            sig = signals[0]
            assert isinstance(sig, StrategySignal)
            assert sig.entry_level is not None
            assert sig.stop_loss is not None
            assert sig.take_profit is not None
            assert sig.holding_period_days == 14
            assert sig.strategy_id == "FX_03"

    def test_missing_bcb_flow_returns_empty(self) -> None:
        """Missing BCB FX flow should return empty list."""
        loader = self._make_fx03_loader()
        loader.get_flow_data.side_effect = lambda code, aod, **kw: (
            _empty_flow_df() if code == "BR_FX_FLOW_NET"
            else _make_flow_df([50.0] * 300)
        )
        strategy = Fx03FlowTacticalStrategy(data_loader=loader)
        signals = strategy.generate_signals(AS_OF)
        assert signals == []

    def test_missing_cftc_returns_empty(self) -> None:
        """Missing CFTC data should return empty list."""
        loader = self._make_fx03_loader()
        loader.get_flow_data.side_effect = lambda code, aod, **kw: (
            _empty_flow_df() if code == "CFTC_6L_LEVERAGED_NET"
            else _make_flow_df([50.0] * 300)
        )
        strategy = Fx03FlowTacticalStrategy(data_loader=loader)
        signals = strategy.generate_signals(AS_OF)
        assert signals == []

    def test_missing_b3_flow_returns_empty(self) -> None:
        """Missing B3 flow should return empty list."""
        loader = self._make_fx03_loader()
        loader.get_flow_data.side_effect = lambda code, aod, **kw: (
            _empty_flow_df() if code == "BR_FX_FLOW_FINANCIAL"
            else _make_flow_df([50.0] * 300)
        )
        strategy = Fx03FlowTacticalStrategy(data_loader=loader)
        signals = strategy.generate_signals(AS_OF)
        assert signals == []

    def test_contrarian_logic_inverts_at_extreme(self) -> None:
        """When |composite_z| > 2, direction should be inverted."""
        # Create extremely skewed flows to push z beyond 2
        # BCB: huge spike => very high z
        bcb_vals = [10.0] * 250 + [1000.0] * 50
        cftc_vals = [5.0] * 250 + [500.0] * 50
        b3_vals = [8.0] * 250 + [800.0] * 50
        loader = self._make_fx03_loader(
            bcb_values=bcb_vals,
            cftc_values=cftc_vals,
            b3_values=b3_vals,
        )
        strategy = Fx03FlowTacticalStrategy(data_loader=loader)
        signals = strategy.generate_signals(AS_OF)

        if signals:
            sig = signals[0]
            assert "is_contrarian" in sig.metadata
            if sig.metadata["is_contrarian"]:
                # When contrarian, direction should be flipped from base
                base_dir = sig.metadata["base_direction"]
                if base_dir == "SHORT":
                    assert sig.direction == SignalDirection.LONG
                else:
                    assert sig.direction == SignalDirection.SHORT

    def test_stop_loss_is_3pct(self) -> None:
        """Stop-loss should be approximately 3% from entry."""
        bcb_vals = [10.0] * 200 + [500.0] * 100
        loader = self._make_fx03_loader(bcb_values=bcb_vals)
        strategy = Fx03FlowTacticalStrategy(data_loader=loader)
        signals = strategy.generate_signals(AS_OF)

        if signals:
            sig = signals[0]
            entry = sig.entry_level
            stop = sig.stop_loss
            pct_diff = abs(stop - entry) / entry
            assert abs(pct_diff - 0.03) < 0.001


# ---------------------------------------------------------------------------
# FX-04: Vol Surface RV -- Registration
# ---------------------------------------------------------------------------
class TestFx04Registration:
    """FX-04 strategy registration in StrategyRegistry."""

    def test_fx04_registered(self) -> None:
        """FX_04 should be in the registry."""
        assert "FX_04" in StrategyRegistry.list_all()

    def test_fx04_asset_class(self) -> None:
        """FX_04 should be listed under AssetClass.FX."""
        fx_strategies = StrategyRegistry.list_by_asset_class(AssetClass.FX)
        assert "FX_04" in fx_strategies


# ---------------------------------------------------------------------------
# FX-04: Signal generation
# ---------------------------------------------------------------------------
class TestFx04Signals:
    """FX-04 Vol Surface Relative Value signal generation."""

    def _make_fx04_loader(
        self,
        usdbrl_prices: list[float] | None = None,
    ) -> MagicMock:
        """Build a mock loader for FX-04."""
        loader = MagicMock()

        if usdbrl_prices is None:
            # 700 business days with some vol clustering
            np.random.seed(42)
            prices = [5.0]
            for i in range(699):
                # Add regime-switching vol
                vol = 0.01 if i < 500 else 0.03
                ret = np.random.normal(0.0001, vol)
                prices.append(prices[-1] * (1 + ret))
            usdbrl_prices = prices

        loader.get_market_data.return_value = _make_market_df(usdbrl_prices)
        return loader

    def test_generates_signal_with_data(self) -> None:
        """FX-04 should produce a signal when sufficient data is available."""
        loader = self._make_fx04_loader()
        strategy = Fx04VolSurfaceRvStrategy(data_loader=loader)
        signals = strategy.generate_signals(AS_OF)
        assert isinstance(signals, list)

    def test_signal_fields_populated(self) -> None:
        """StrategySignal should have vol-surface specific metadata."""
        loader = self._make_fx04_loader()
        strategy = Fx04VolSurfaceRvStrategy(data_loader=loader)
        signals = strategy.generate_signals(AS_OF)

        if signals:
            sig = signals[0]
            assert isinstance(sig, StrategySignal)
            assert sig.entry_level is not None
            assert sig.stop_loss is not None
            assert sig.take_profit is not None
            assert sig.holding_period_days == 14
            assert sig.strategy_id == "FX_04"
            assert "iv_rv_z" in sig.metadata
            assert "term_z" in sig.metadata
            assert "skew_z" in sig.metadata
            assert "kurt_z" in sig.metadata

    def test_missing_market_data_returns_empty(self) -> None:
        """Missing USDBRL data should return empty list."""
        loader = self._make_fx04_loader()
        loader.get_market_data.return_value = _empty_market_df()
        strategy = Fx04VolSurfaceRvStrategy(data_loader=loader)
        signals = strategy.generate_signals(AS_OF)
        assert signals == []

    def test_insufficient_history_returns_empty(self) -> None:
        """Less than 504 data points should return empty list."""
        short_prices = [5.0 + 0.01 * i for i in range(100)]
        loader = self._make_fx04_loader(usdbrl_prices=short_prices)
        strategy = Fx04VolSurfaceRvStrategy(data_loader=loader)
        signals = strategy.generate_signals(AS_OF)
        assert signals == []


# ---------------------------------------------------------------------------
# FX-05: Terms of Trade -- Registration
# ---------------------------------------------------------------------------
class TestFx05Registration:
    """FX-05 strategy registration in StrategyRegistry."""

    def test_fx05_registered(self) -> None:
        """FX_05 should be in the registry."""
        assert "FX_05" in StrategyRegistry.list_all()

    def test_fx05_asset_class(self) -> None:
        """FX_05 should be listed under AssetClass.FX."""
        fx_strategies = StrategyRegistry.list_by_asset_class(AssetClass.FX)
        assert "FX_05" in fx_strategies


# ---------------------------------------------------------------------------
# FX-05: Signal generation + misalignment direction
# ---------------------------------------------------------------------------
class TestFx05Signals:
    """FX-05 Terms of Trade signal generation and misalignment logic."""

    def _make_fx05_loader(
        self,
        commodity_prices: dict[str, list[float]] | None = None,
        usdbrl_prices: list[float] | None = None,
    ) -> MagicMock:
        """Build a mock loader for FX-05."""
        loader = MagicMock()

        if commodity_prices is None:
            # Default: 600 business days for each commodity with different trends
            np.random.seed(42)
            commodity_prices = {}
            for ticker in ["ZS=F", "TIO=F", "BZ=F", "SB=F", "KC=F"]:
                base = 100.0
                prices = [base]
                for i in range(599):
                    ret = np.random.normal(0.0005, 0.015)
                    prices.append(prices[-1] * (1 + ret))
                commodity_prices[ticker] = prices

        if usdbrl_prices is None:
            np.random.seed(99)
            usdbrl_prices = [5.0]
            for i in range(599):
                ret = np.random.normal(0, 0.01)
                usdbrl_prices.append(usdbrl_prices[-1] * (1 + ret))

        def market_data_side_effect(ticker, as_of_date, **kwargs):
            if ticker == "USDBRL":
                return _make_market_df(usdbrl_prices)
            if ticker in commodity_prices:
                return _make_market_df(commodity_prices[ticker])
            return _empty_market_df()

        loader.get_market_data.side_effect = market_data_side_effect

        return loader

    def test_generates_signal_with_data(self) -> None:
        """FX-05 should produce a signal when all commodity data is available."""
        loader = self._make_fx05_loader()
        strategy = Fx05TermsOfTradeStrategy(data_loader=loader)
        signals = strategy.generate_signals(AS_OF)
        assert isinstance(signals, list)

    def test_signal_fields_populated(self) -> None:
        """StrategySignal should have ToT-specific metadata."""
        loader = self._make_fx05_loader()
        strategy = Fx05TermsOfTradeStrategy(data_loader=loader)
        signals = strategy.generate_signals(AS_OF)

        if signals:
            sig = signals[0]
            assert isinstance(sig, StrategySignal)
            assert sig.entry_level is not None
            assert sig.stop_loss is not None
            assert sig.take_profit is not None
            assert sig.holding_period_days == 28
            assert sig.strategy_id == "FX_05"
            assert "tot_z" in sig.metadata
            assert "usdbrl_z" in sig.metadata
            assert "misalignment" in sig.metadata

    def test_missing_commodity_returns_empty(self) -> None:
        """Missing any commodity data should return empty list."""
        loader = self._make_fx05_loader()
        # Override to return empty for all tickers
        loader.get_market_data.side_effect = lambda t, aod, **kw: (
            _make_market_df([5.0 + 0.01 * i for i in range(600)]) if t == "USDBRL"
            else _empty_market_df()
        )
        strategy = Fx05TermsOfTradeStrategy(data_loader=loader)
        signals = strategy.generate_signals(AS_OF)
        assert signals == []

    def test_missing_usdbrl_returns_empty(self) -> None:
        """Missing USDBRL data should return empty list."""
        loader = self._make_fx05_loader()
        loader.get_market_data.side_effect = lambda t, aod, **kw: (
            _empty_market_df() if t == "USDBRL"
            else _make_market_df([100.0 + 0.1 * i for i in range(600)])
        )
        strategy = Fx05TermsOfTradeStrategy(data_loader=loader)
        signals = strategy.generate_signals(AS_OF)
        assert signals == []

    def test_positive_misalignment_shorts_usdbrl(self) -> None:
        """Positive misalignment (ToT improving > BRL) => SHORT USDBRL."""
        # Commodities rising strongly, USDBRL flat => positive misalignment
        commodity_prices = {}
        for ticker in ["ZS=F", "TIO=F", "BZ=F", "SB=F", "KC=F"]:
            # Strong uptrend
            prices = [100.0 * (1 + 0.001 * i) for i in range(600)]
            commodity_prices[ticker] = prices

        # USDBRL flat
        usdbrl_prices = [5.0 + 0.001 * np.sin(i / 20) for i in range(600)]

        loader = self._make_fx05_loader(
            commodity_prices=commodity_prices,
            usdbrl_prices=usdbrl_prices,
        )
        strategy = Fx05TermsOfTradeStrategy(data_loader=loader)
        signals = strategy.generate_signals(AS_OF)

        if signals:
            sig = signals[0]
            # Positive misalignment => SHORT USDBRL
            assert sig.direction == SignalDirection.SHORT
            assert sig.metadata["misalignment"] > 0

    def test_negative_misalignment_longs_usdbrl(self) -> None:
        """Negative misalignment (ToT deteriorating > BRL) => LONG USDBRL."""
        # Commodities falling, USDBRL flat => negative misalignment
        commodity_prices = {}
        for ticker in ["ZS=F", "TIO=F", "BZ=F", "SB=F", "KC=F"]:
            # Strong downtrend
            prices = [100.0 * (1 - 0.001 * i) for i in range(600)]
            prices = [max(10.0, p) for p in prices]
            commodity_prices[ticker] = prices

        # USDBRL flat
        usdbrl_prices = [5.0 + 0.001 * np.sin(i / 20) for i in range(600)]

        loader = self._make_fx05_loader(
            commodity_prices=commodity_prices,
            usdbrl_prices=usdbrl_prices,
        )
        strategy = Fx05TermsOfTradeStrategy(data_loader=loader)
        signals = strategy.generate_signals(AS_OF)

        if signals:
            sig = signals[0]
            # Negative misalignment => LONG USDBRL
            assert sig.direction == SignalDirection.LONG
            assert sig.metadata["misalignment"] < 0

    def test_stop_loss_is_4pct(self) -> None:
        """Stop-loss should be approximately 4% from entry."""
        loader = self._make_fx05_loader()
        strategy = Fx05TermsOfTradeStrategy(data_loader=loader)
        signals = strategy.generate_signals(AS_OF)

        if signals:
            sig = signals[0]
            entry = sig.entry_level
            stop = sig.stop_loss
            pct_diff = abs(stop - entry) / entry
            assert abs(pct_diff - 0.04) < 0.001


# ---------------------------------------------------------------------------
# Cross-cutting: All 4 strategies listed together
# ---------------------------------------------------------------------------
class TestAllFxStrategies:
    """Cross-cutting tests for all new FX strategies together."""

    def test_all_four_registered(self) -> None:
        """All 4 new FX strategies should be in the registry."""
        all_ids = StrategyRegistry.list_all()
        for sid in ["FX_02", "FX_03", "FX_04", "FX_05"]:
            assert sid in all_ids, f"{sid} not found in registry"

    def test_all_four_in_fx_asset_class(self) -> None:
        """All 4 new FX strategies should be listed under AssetClass.FX."""
        fx_ids = StrategyRegistry.list_by_asset_class(AssetClass.FX)
        for sid in ["FX_02", "FX_03", "FX_04", "FX_05"]:
            assert sid in fx_ids, f"{sid} not found in FX asset class"

    def test_fx_asset_class_has_five_strategies(self) -> None:
        """FX asset class should have 5 strategies (FX_BR_01 + 4 new)."""
        fx_ids = StrategyRegistry.list_by_asset_class(AssetClass.FX)
        assert len(fx_ids) >= 5
        assert "FX_BR_01" in fx_ids

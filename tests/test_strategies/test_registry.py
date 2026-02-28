"""Tests for StrategyRegistry -- decorator-based strategy registration (SFWK-02).

Validates registration, lookup, asset-class filtering, and instantiation.
Uses a fixture to save/restore registry state to avoid pollution between tests.
"""

from datetime import date

import pytest

from src.core.enums import AssetClass, Frequency
from src.strategies.base import BaseStrategy, StrategyConfig, StrategyPosition
from src.strategies.registry import StrategyRegistry


# ---------------------------------------------------------------------------
# Fixture: save/restore registry state between tests
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _clean_registry():
    """Save and restore StrategyRegistry state around each test."""
    saved_strategies = dict(StrategyRegistry._strategies)
    saved_metadata = dict(StrategyRegistry._metadata)
    yield
    StrategyRegistry._strategies = saved_strategies
    StrategyRegistry._metadata = saved_metadata


# ---------------------------------------------------------------------------
# Dummy strategy for registration tests
# ---------------------------------------------------------------------------
_DUMMY_CONFIG = StrategyConfig(
    strategy_id="DUMMY_REG",
    strategy_name="Dummy Registry Strategy",
    asset_class=AssetClass.FX,
    instruments=["USDBRL"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
)


class DummyRegistryStrategy(BaseStrategy):
    """Minimal concrete strategy for registry tests."""

    def __init__(self, config: StrategyConfig | None = None) -> None:
        super().__init__(config=config or _DUMMY_CONFIG)

    def generate_signals(self, as_of_date: date) -> list[StrategyPosition]:
        return []


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestRegistryRegisterDecorator:
    def test_register_decorator(self) -> None:
        """@StrategyRegistry.register should register a strategy class by ID."""

        @StrategyRegistry.register(
            "TEST_01", asset_class=AssetClass.FX, instruments=["USDBRL"]
        )
        class _TestStrategy(DummyRegistryStrategy):
            pass

        assert "TEST_01" in StrategyRegistry.list_all()
        assert StrategyRegistry.get("TEST_01") is _TestStrategy

    def test_register_decorator_returns_class_unchanged(self) -> None:
        """The decorator should return the original class unmodified."""

        @StrategyRegistry.register("TEST_02", asset_class=AssetClass.EQUITY_INDEX)
        class _TestStrategy2(DummyRegistryStrategy):
            pass

        # Class should be the same object (not wrapped)
        assert _TestStrategy2.__name__ == "_TestStrategy2"
        assert issubclass(_TestStrategy2, BaseStrategy)


class TestRegistryGet:
    def test_get_existing(self) -> None:
        """get() should return the registered class."""
        StrategyRegistry._strategies["TEST_GET"] = DummyRegistryStrategy
        StrategyRegistry._metadata["TEST_GET"] = {
            "asset_class": AssetClass.FX,
            "instruments": [],
        }
        cls = StrategyRegistry.get("TEST_GET")
        assert cls is DummyRegistryStrategy

    def test_get_missing_raises(self) -> None:
        """get() should raise KeyError for unregistered strategy."""
        with pytest.raises(KeyError, match="NONEXISTENT"):
            StrategyRegistry.get("NONEXISTENT")


class TestRegistryListAll:
    def test_list_all_includes_existing_8(self) -> None:
        """list_all() should include all 8 existing strategies from __init__.py."""
        all_ids = StrategyRegistry.list_all()
        assert len(all_ids) >= 8
        assert "RATES_BR_01" in all_ids
        assert "RATES_BR_02" in all_ids
        assert "RATES_BR_03" in all_ids
        assert "RATES_BR_04" in all_ids
        assert "INF_BR_01" in all_ids
        assert "FX_BR_01" in all_ids
        assert "CUPOM_01" in all_ids
        assert "SOV_BR_01" in all_ids

    def test_list_all_sorted(self) -> None:
        """list_all() should return a sorted list."""
        all_ids = StrategyRegistry.list_all()
        assert all_ids == sorted(all_ids)


class TestRegistryListByAssetClass:
    def test_list_by_asset_class_fixed_income(self) -> None:
        """list_by_asset_class(FIXED_INCOME) should return at least 4 BR rates strategies."""
        fi_ids = StrategyRegistry.list_by_asset_class(AssetClass.FIXED_INCOME)
        expected = ["RATES_BR_01", "RATES_BR_02", "RATES_BR_03", "RATES_BR_04"]
        for sid in expected:
            assert (
                sid in fi_ids
            ), f"Expected {sid} in FIXED_INCOME strategies, got {fi_ids}"

    def test_list_by_asset_class_fx(self) -> None:
        """list_by_asset_class(FX) should return at least FX_BR_01."""
        fx_ids = StrategyRegistry.list_by_asset_class(AssetClass.FX)
        assert "FX_BR_01" in fx_ids

    def test_list_by_asset_class_empty(self) -> None:
        """list_by_asset_class for unused class should return empty list."""
        ids = StrategyRegistry.list_by_asset_class(AssetClass.CRYPTO)
        assert ids == []


class TestRegistryInstantiate:
    def test_instantiate_returns_instance(self) -> None:
        """instantiate() with required args should return a BaseStrategy instance."""
        # Register a dummy that doesn't need data_loader
        StrategyRegistry._strategies["DUMMY_INST"] = DummyRegistryStrategy
        StrategyRegistry._metadata["DUMMY_INST"] = {
            "asset_class": AssetClass.FX,
            "instruments": ["USDBRL"],
        }
        instance = StrategyRegistry.instantiate("DUMMY_INST")
        assert isinstance(instance, BaseStrategy)
        assert instance.strategy_id == "DUMMY_REG"

    def test_instantiate_passes_kwargs(self) -> None:
        """instantiate() should pass kwargs to the constructor."""
        custom_config = StrategyConfig(
            strategy_id="CUSTOM_ID",
            strategy_name="Custom",
            asset_class=AssetClass.FX,
            instruments=["EURUSD"],
            rebalance_frequency=Frequency.WEEKLY,
            max_position_size=0.5,
        )
        StrategyRegistry._strategies["DUMMY_KW"] = DummyRegistryStrategy
        StrategyRegistry._metadata["DUMMY_KW"] = {
            "asset_class": AssetClass.FX,
            "instruments": [],
        }
        instance = StrategyRegistry.instantiate("DUMMY_KW", config=custom_config)
        assert instance.strategy_id == "CUSTOM_ID"

    def test_instantiate_missing_raises(self) -> None:
        """instantiate() should raise KeyError for unregistered strategy."""
        with pytest.raises(KeyError):
            StrategyRegistry.instantiate("MISSING_STRATEGY")

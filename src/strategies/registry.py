"""Strategy Registry -- decorator-based strategy registration (SFWK-02).

Replaces the manual ALL_STRATEGIES dict with a class-level registry that
supports decorator-based registration, lookup by asset class, and
bulk instantiation.

Usage::

    @StrategyRegistry.register("MY_STRAT_01", asset_class=AssetClass.FX, instruments=["USDBRL"])
    class MyStrategy(BaseStrategy):
        ...

    # Later:
    cls = StrategyRegistry.get("MY_STRAT_01")
    instance = StrategyRegistry.instantiate("MY_STRAT_01", config=my_config)
    all_fx = StrategyRegistry.list_by_asset_class(AssetClass.FX)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.enums import AssetClass

if TYPE_CHECKING:
    from src.strategies.base import BaseStrategy


class StrategyRegistry:
    """Central registry for all trading strategies.

    Stores strategy classes and metadata (asset_class, instruments) at the
    class level.  The ``register`` decorator adds strategies at import time.
    """

    _strategies: dict[str, type[BaseStrategy]] = {}
    _metadata: dict[str, dict] = {}

    @classmethod
    def register(
        cls,
        strategy_id: str,
        asset_class: AssetClass | None = None,
        instruments: list[str] | None = None,
    ):
        """Decorator that registers a strategy class in the registry.

        Args:
            strategy_id: Unique strategy identifier.
            asset_class: Optional asset class for filtering.
            instruments: Optional list of instrument tickers.

        Returns:
            The original class, unmodified.
        """

        def decorator(strategy_cls: type[BaseStrategy]) -> type[BaseStrategy]:
            cls._strategies[strategy_id] = strategy_cls
            cls._metadata[strategy_id] = {
                "asset_class": asset_class,
                "instruments": instruments or [],
            }
            return strategy_cls

        return decorator

    @classmethod
    def get(cls, strategy_id: str) -> type[BaseStrategy]:
        """Get a strategy class by ID.

        Args:
            strategy_id: Strategy identifier.

        Returns:
            The strategy class.

        Raises:
            KeyError: If strategy_id is not registered.
        """
        if strategy_id not in cls._strategies:
            available = ", ".join(sorted(cls._strategies.keys()))
            raise KeyError(
                f"Strategy '{strategy_id}' not found in registry. "
                f"Available strategies: [{available}]"
            )
        return cls._strategies[strategy_id]

    @classmethod
    def list_all(cls) -> list[str]:
        """Return a sorted list of all registered strategy IDs."""
        return sorted(cls._strategies.keys())

    @classmethod
    def list_by_asset_class(cls, asset_class: AssetClass) -> list[str]:
        """Return strategy IDs matching the given asset class.

        First checks the registry metadata.  Falls back to inspecting
        the strategy class's config.asset_class if metadata is missing.

        Args:
            asset_class: Asset class to filter by.

        Returns:
            Sorted list of matching strategy IDs.
        """
        matches: list[str] = []
        for sid, meta in cls._metadata.items():
            if meta.get("asset_class") == asset_class:
                matches.append(sid)
                continue
            # Fallback: check class-level config if metadata is missing
            if meta.get("asset_class") is None:
                strategy_cls = cls._strategies.get(sid)
                if strategy_cls is not None:
                    # Some strategies define a module-level config constant
                    # Try to find asset_class from the class itself
                    try:
                        # Check for a class attribute or default config
                        if hasattr(strategy_cls, "DEFAULT_CONFIG"):
                            if strategy_cls.DEFAULT_CONFIG.asset_class == asset_class:
                                matches.append(sid)
                    except Exception:
                        pass
        return sorted(matches)

    @classmethod
    def instantiate(cls, strategy_id: str, **kwargs) -> BaseStrategy:
        """Instantiate a strategy by ID with optional keyword arguments.

        Args:
            strategy_id: Strategy identifier.
            **kwargs: Arguments passed to the strategy constructor.

        Returns:
            An instance of the strategy.
        """
        strategy_cls = cls.get(strategy_id)
        return strategy_cls(**kwargs)

    @classmethod
    def instantiate_all(cls) -> list[BaseStrategy]:
        """Instantiate all registered strategies with default parameters.

        Strategies that require constructor arguments will raise errors.
        This is intended for strategies with no-arg or all-default constructors.

        Returns:
            List of strategy instances.
        """
        instances = []
        for sid in sorted(cls._strategies.keys()):
            strategy_cls = cls._strategies[sid]
            instances.append(strategy_cls())
        return instances

"""Trading strategy framework for the Macro Trading system.

Re-exports the core strategy infrastructure:
- BaseStrategy: Abstract base class for all trading strategies
- StrategyConfig: Immutable strategy configuration dataclass
- StrategyPosition: Target position output dataclass
"""

from src.strategies.base import BaseStrategy, StrategyConfig, StrategyPosition

__all__ = [
    "BaseStrategy",
    "StrategyConfig",
    "StrategyPosition",
]

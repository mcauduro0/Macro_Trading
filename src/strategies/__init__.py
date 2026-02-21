"""Trading strategy framework for the Macro Trading system.

Re-exports the core strategy infrastructure and concrete strategies:
- BaseStrategy: Abstract base class for all trading strategies
- StrategyConfig: Immutable strategy configuration dataclass
- StrategyPosition: Target position output dataclass
- RatesBR01CarryStrategy: BR DI Carry & Roll-Down strategy
- RatesBR02TaylorStrategy: BR Taylor Rule Misalignment strategy
"""

from src.strategies.base import BaseStrategy, StrategyConfig, StrategyPosition
from src.strategies.rates_br_01_carry import RatesBR01CarryStrategy
from src.strategies.rates_br_02_taylor import RatesBR02TaylorStrategy

__all__ = [
    "BaseStrategy",
    "RatesBR01CarryStrategy",
    "RatesBR02TaylorStrategy",
    "StrategyConfig",
    "StrategyPosition",
]

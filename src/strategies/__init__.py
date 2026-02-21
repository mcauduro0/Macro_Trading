"""Trading strategy framework for the Macro Trading system.

Re-exports the core strategy infrastructure and concrete strategies:
- BaseStrategy: Abstract base class for all trading strategies
- StrategyConfig: Immutable strategy configuration dataclass
- StrategyPosition: Target position output dataclass
- RatesBR01CarryStrategy: BR DI Carry & Roll-Down strategy
- RatesBR02TaylorStrategy: BR Taylor Rule Misalignment strategy
- RatesBR03SlopeStrategy: BR DI Curve Slope (Flattener/Steepener) strategy
- RatesBR04SpilloverStrategy: US Rates Spillover to BR DI strategy
- InfBR01BreakevenStrategy: BR Breakeven Inflation Trade strategy
- FxBR01CarryFundamentalStrategy: USDBRL Carry & Fundamental composite strategy
"""

from src.strategies.base import BaseStrategy, StrategyConfig, StrategyPosition
from src.strategies.fx_br_01_carry_fundamental import FxBR01CarryFundamentalStrategy
from src.strategies.inf_br_01_breakeven import InfBR01BreakevenStrategy
from src.strategies.rates_br_01_carry import RatesBR01CarryStrategy
from src.strategies.rates_br_02_taylor import RatesBR02TaylorStrategy
from src.strategies.rates_br_03_slope import RatesBR03SlopeStrategy
from src.strategies.rates_br_04_spillover import RatesBR04SpilloverStrategy

__all__ = [
    "BaseStrategy",
    "FxBR01CarryFundamentalStrategy",
    "InfBR01BreakevenStrategy",
    "RatesBR01CarryStrategy",
    "RatesBR02TaylorStrategy",
    "RatesBR03SlopeStrategy",
    "RatesBR04SpilloverStrategy",
    "StrategyConfig",
    "StrategyPosition",
]

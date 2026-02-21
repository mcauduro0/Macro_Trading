"""Trading strategy framework for the Macro Trading system.

Re-exports the core strategy infrastructure and all 8 concrete strategies:
- BaseStrategy: Abstract base class for all trading strategies
- StrategyConfig: Immutable strategy configuration dataclass
- StrategyPosition: Target position output dataclass
- RatesBR01CarryStrategy: BR DI Carry & Roll-Down strategy
- RatesBR02TaylorStrategy: BR Taylor Rule Misalignment strategy
- RatesBR03SlopeStrategy: BR DI Curve Slope (Flattener/Steepener) strategy
- RatesBR04SpilloverStrategy: US Rates Spillover to BR DI strategy
- InfBR01BreakevenStrategy: BR Breakeven Inflation Trade strategy
- FxBR01CarryFundamentalStrategy: USDBRL Carry & Fundamental composite strategy
- Cupom01CipBasisStrategy: Cupom Cambial CIP Basis Mean Reversion strategy
- SovBR01FiscalRiskStrategy: BR Fiscal Risk Premium strategy

ALL_STRATEGIES: dict mapping strategy_id to strategy class for programmatic
discovery by the backtesting engine (Phase 10) and daily pipeline (Phase 13).
"""

from src.strategies.base import BaseStrategy, StrategyConfig, StrategyPosition
from src.strategies.cupom_01_cip_basis import Cupom01CipBasisStrategy
from src.strategies.fx_br_01_carry_fundamental import FxBR01CarryFundamentalStrategy
from src.strategies.inf_br_01_breakeven import InfBR01BreakevenStrategy
from src.strategies.rates_br_01_carry import RatesBR01CarryStrategy
from src.strategies.rates_br_02_taylor import RatesBR02TaylorStrategy
from src.strategies.rates_br_03_slope import RatesBR03SlopeStrategy
from src.strategies.rates_br_04_spillover import RatesBR04SpilloverStrategy
from src.strategies.sov_br_01_fiscal_risk import SovBR01FiscalRiskStrategy

# ---------------------------------------------------------------------------
# ALL_STRATEGIES registry: strategy_id -> strategy class
# ---------------------------------------------------------------------------
ALL_STRATEGIES: dict[str, type[BaseStrategy]] = {
    "RATES_BR_01": RatesBR01CarryStrategy,
    "RATES_BR_02": RatesBR02TaylorStrategy,
    "RATES_BR_03": RatesBR03SlopeStrategy,
    "RATES_BR_04": RatesBR04SpilloverStrategy,
    "INF_BR_01": InfBR01BreakevenStrategy,
    "FX_BR_01": FxBR01CarryFundamentalStrategy,
    "CUPOM_01": Cupom01CipBasisStrategy,
    "SOV_BR_01": SovBR01FiscalRiskStrategy,
}

__all__ = [
    "ALL_STRATEGIES",
    "BaseStrategy",
    "Cupom01CipBasisStrategy",
    "FxBR01CarryFundamentalStrategy",
    "InfBR01BreakevenStrategy",
    "RatesBR01CarryStrategy",
    "RatesBR02TaylorStrategy",
    "RatesBR03SlopeStrategy",
    "RatesBR04SpilloverStrategy",
    "SovBR01FiscalRiskStrategy",
    "StrategyConfig",
    "StrategyPosition",
]

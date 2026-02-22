"""Trading strategy framework for the Macro Trading system.

Re-exports the core strategy infrastructure and all 16 concrete strategies:
- BaseStrategy: Abstract base class for all trading strategies
- StrategyConfig: Immutable strategy configuration dataclass
- StrategyPosition: Target position output dataclass
- StrategySignal: Rich signal dataclass with z_score, entry/stop/take-profit (v3.0)
- StrategyRegistry: Decorator-based strategy registration (v3.0)
- RatesBR01CarryStrategy: BR DI Carry & Roll-Down strategy
- RatesBR02TaylorStrategy: BR Taylor Rule Misalignment strategy
- RatesBR03SlopeStrategy: BR DI Curve Slope (Flattener/Steepener) strategy
- RatesBR04SpilloverStrategy: US Rates Spillover to BR DI strategy
- Rates03BrUsSpreadStrategy: BR-US Rate Spread mean reversion (v3.0)
- Rates04TermPremiumStrategy: Term Premium Extraction (v3.0)
- Rates05FomcEventStrategy: FOMC Event Strategy (v3.0)
- Rates06CopomEventStrategy: COPOM Event Strategy (v3.0)
- InfBR01BreakevenStrategy: BR Breakeven Inflation Trade strategy
- FxBR01CarryFundamentalStrategy: USDBRL Carry & Fundamental composite strategy
- Fx02CarryMomentumStrategy: USDBRL Carry-Adjusted Momentum strategy (v3.0)
- Fx03FlowTacticalStrategy: USDBRL Flow-Based Tactical strategy (v3.0)
- Fx04VolSurfaceRvStrategy: USDBRL Vol Surface Relative Value strategy (v3.0)
- Fx05TermsOfTradeStrategy: USDBRL Terms of Trade Misalignment strategy (v3.0)
- Cupom01CipBasisStrategy: Cupom Cambial CIP Basis Mean Reversion strategy
- SovBR01FiscalRiskStrategy: BR Fiscal Risk Premium strategy

ALL_STRATEGIES: dict mapping strategy_id to strategy class for programmatic
discovery by the backtesting engine (Phase 10) and daily pipeline (Phase 13).

StrategyRegistry: Class-level registry that provides the same mapping plus
decorator-based registration, asset-class filtering, and instantiation helpers.
Both ALL_STRATEGIES and StrategyRegistry are populated at import time.
"""

from src.strategies.base import (
    BaseStrategy,
    StrategyConfig,
    StrategyPosition,
    StrategySignal,
)
from src.strategies.cupom_01_cip_basis import Cupom01CipBasisStrategy
from src.strategies.fx_02_carry_momentum import Fx02CarryMomentumStrategy
from src.strategies.fx_03_flow_tactical import Fx03FlowTacticalStrategy
from src.strategies.fx_04_vol_surface_rv import Fx04VolSurfaceRvStrategy
from src.strategies.fx_05_terms_of_trade import Fx05TermsOfTradeStrategy
from src.strategies.fx_br_01_carry_fundamental import FxBR01CarryFundamentalStrategy
from src.strategies.inf_br_01_breakeven import InfBR01BreakevenStrategy
from src.strategies.rates_03_br_us_spread import Rates03BrUsSpreadStrategy
from src.strategies.rates_04_term_premium import Rates04TermPremiumStrategy
from src.strategies.rates_05_fomc_event import Rates05FomcEventStrategy
from src.strategies.rates_06_copom_event import Rates06CopomEventStrategy
from src.strategies.rates_br_01_carry import RatesBR01CarryStrategy
from src.strategies.rates_br_02_taylor import RatesBR02TaylorStrategy
from src.strategies.rates_br_03_slope import RatesBR03SlopeStrategy
from src.strategies.rates_br_04_spillover import RatesBR04SpilloverStrategy
from src.strategies.registry import StrategyRegistry
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

# ---------------------------------------------------------------------------
# Auto-register existing 8 strategies in StrategyRegistry (v3.0)
# ---------------------------------------------------------------------------
# This bridges the legacy ALL_STRATEGIES dict with the new StrategyRegistry
# so both access patterns work.  New strategies (Phase 15+) should use the
# @StrategyRegistry.register decorator directly.
for _sid, _cls in ALL_STRATEGIES.items():
    StrategyRegistry._strategies[_sid] = _cls
    # Extract asset_class and instruments from the strategy's default config
    # Each strategy module defines a module-level config constant
    _asset_class = None
    _instruments: list[str] = []
    try:
        # Convention: each strategy class has a module-level *_CONFIG constant
        # but we can also check if they have a default config attribute.
        # Safest: instantiation without data_loader may fail, so inspect module.
        import importlib
        _mod = importlib.import_module(_cls.__module__)
        for _attr_name in dir(_mod):
            _attr = getattr(_mod, _attr_name)
            if isinstance(_attr, StrategyConfig) and _attr.strategy_id == _sid:
                _asset_class = _attr.asset_class
                _instruments = list(_attr.instruments)
                break
    except Exception:
        pass
    StrategyRegistry._metadata[_sid] = {
        "asset_class": _asset_class,
        "instruments": _instruments,
    }

# Clean up loop variables from module namespace
del _sid, _cls, _asset_class, _instruments

__all__ = [
    "ALL_STRATEGIES",
    "BaseStrategy",
    "Cupom01CipBasisStrategy",
    "Fx02CarryMomentumStrategy",
    "Fx03FlowTacticalStrategy",
    "Fx04VolSurfaceRvStrategy",
    "Fx05TermsOfTradeStrategy",
    "FxBR01CarryFundamentalStrategy",
    "InfBR01BreakevenStrategy",
    "Rates03BrUsSpreadStrategy",
    "Rates04TermPremiumStrategy",
    "Rates05FomcEventStrategy",
    "Rates06CopomEventStrategy",
    "RatesBR01CarryStrategy",
    "RatesBR02TaylorStrategy",
    "RatesBR03SlopeStrategy",
    "RatesBR04SpilloverStrategy",
    "SovBR01FiscalRiskStrategy",
    "StrategyConfig",
    "StrategyPosition",
    "StrategyRegistry",
    "StrategySignal",
]

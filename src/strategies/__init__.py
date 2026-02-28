"""Trading strategy framework for the Macro Trading system.

Re-exports the core strategy infrastructure and all 24 concrete strategies:
- BaseStrategy: Abstract base class for all trading strategies
- StrategyConfig: Immutable strategy configuration dataclass
- StrategyPosition: Target position output dataclass
- StrategySignal: Rich signal dataclass with z_score, entry/stop/take-profit (v3.0)
- StrategyRegistry: Decorator-based strategy registration (v3.0)

Original 8 strategies (v2.0):
- RatesBR01CarryStrategy: BR DI Carry & Roll-Down strategy
- RatesBR02TaylorStrategy: BR Taylor Rule Misalignment strategy
- RatesBR03SlopeStrategy: BR DI Curve Slope (Flattener/Steepener) strategy
- RatesBR04SpilloverStrategy: US Rates Spillover to BR DI strategy
- InfBR01BreakevenStrategy: BR Breakeven Inflation Trade strategy
- FxBR01CarryFundamentalStrategy: USDBRL Carry & Fundamental composite strategy
- Cupom01CipBasisStrategy: Cupom Cambial CIP Basis Mean Reversion strategy
- SovBR01FiscalRiskStrategy: BR Fiscal Risk Premium strategy

16 new strategies (v3.0 Phase 15):
- Fx02CarryMomentumStrategy: USDBRL Carry-Adjusted Momentum (Plan 01)
- Fx03FlowTacticalStrategy: USDBRL Flow-Based Tactical (Plan 01)
- Fx04VolSurfaceRvStrategy: USDBRL Vol Surface Relative Value (Plan 01)
- Fx05TermsOfTradeStrategy: USDBRL Terms of Trade Misalignment (Plan 01)
- Rates03BrUsSpreadStrategy: BR-US Rate Spread mean reversion (Plan 02)
- Rates04TermPremiumStrategy: Term Premium Extraction (Plan 02)
- Rates05FomcEventStrategy: FOMC Event Strategy (Plan 02)
- Rates06CopomEventStrategy: COPOM Event Strategy (Plan 02)
- Inf02IpcaSurpriseStrategy: IPCA Surprise Trade (Plan 03)
- Inf03InflationCarryStrategy: Inflation Carry (Plan 03)
- Cupom02OnshoreOffshoreStrategy: Onshore-Offshore Spread (Plan 03)
- Sov01CdsCurveStrategy: CDS Curve Trading (Plan 04)
- Sov02EmRelativeValueStrategy: EM Sovereign Relative Value (Plan 04)
- Sov03RatingMigrationStrategy: Rating Migration Anticipation (Plan 04)
- Cross01RegimeAllocationStrategy: Macro Regime Allocation (Plan 04)
- Cross02RiskAppetiteStrategy: Global Risk Appetite (Plan 04)

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
from src.strategies.cross_01_regime_allocation import Cross01RegimeAllocationStrategy
from src.strategies.cross_02_risk_appetite import Cross02RiskAppetiteStrategy

# Original 8 strategies (v2.0)
from src.strategies.cupom_01_cip_basis import Cupom01CipBasisStrategy
from src.strategies.cupom_02_onshore_offshore import Cupom02OnshoreOffshoreStrategy

# Plan 01: FX strategies (v3.0)
from src.strategies.fx_02_carry_momentum import Fx02CarryMomentumStrategy
from src.strategies.fx_03_flow_tactical import Fx03FlowTacticalStrategy
from src.strategies.fx_04_vol_surface_rv import Fx04VolSurfaceRvStrategy
from src.strategies.fx_05_terms_of_trade import Fx05TermsOfTradeStrategy
from src.strategies.fx_br_01_carry_fundamental import FxBR01CarryFundamentalStrategy

# Plan 03: Inflation / Cupom strategies (v3.0)
from src.strategies.inf_02_ipca_surprise import Inf02IpcaSurpriseStrategy
from src.strategies.inf_03_inflation_carry import Inf03InflationCarryStrategy
from src.strategies.inf_br_01_breakeven import InfBR01BreakevenStrategy

# Plan 02: Rates strategies (v3.0)
from src.strategies.rates_03_br_us_spread import Rates03BrUsSpreadStrategy
from src.strategies.rates_04_term_premium import Rates04TermPremiumStrategy
from src.strategies.rates_05_fomc_event import Rates05FomcEventStrategy
from src.strategies.rates_06_copom_event import Rates06CopomEventStrategy
from src.strategies.rates_br_01_carry import RatesBR01CarryStrategy
from src.strategies.rates_br_02_taylor import RatesBR02TaylorStrategy
from src.strategies.rates_br_03_slope import RatesBR03SlopeStrategy
from src.strategies.rates_br_04_spillover import RatesBR04SpilloverStrategy
from src.strategies.registry import StrategyRegistry

# Plan 04: Sovereign / Cross-asset strategies (v3.0)
from src.strategies.sov_01_cds_curve import Sov01CdsCurveStrategy
from src.strategies.sov_02_em_relative_value import Sov02EmRelativeValueStrategy
from src.strategies.sov_03_rating_migration import Sov03RatingMigrationStrategy
from src.strategies.sov_br_01_fiscal_risk import SovBR01FiscalRiskStrategy

# ---------------------------------------------------------------------------
# ALL_STRATEGIES registry: strategy_id -> strategy class
# ---------------------------------------------------------------------------
ALL_STRATEGIES: dict[str, type[BaseStrategy]] = {
    # Original 8 (v2.0)
    "RATES_BR_01": RatesBR01CarryStrategy,
    "RATES_BR_02": RatesBR02TaylorStrategy,
    "RATES_BR_03": RatesBR03SlopeStrategy,
    "RATES_BR_04": RatesBR04SpilloverStrategy,
    "INF_BR_01": InfBR01BreakevenStrategy,
    "FX_BR_01": FxBR01CarryFundamentalStrategy,
    "CUPOM_01": Cupom01CipBasisStrategy,
    "SOV_BR_01": SovBR01FiscalRiskStrategy,
    # Plan 01: FX (v3.0)
    "FX_02": Fx02CarryMomentumStrategy,
    "FX_03": Fx03FlowTacticalStrategy,
    "FX_04": Fx04VolSurfaceRvStrategy,
    "FX_05": Fx05TermsOfTradeStrategy,
    # Plan 02: Rates (v3.0)
    "RATES_03": Rates03BrUsSpreadStrategy,
    "RATES_04": Rates04TermPremiumStrategy,
    "RATES_05": Rates05FomcEventStrategy,
    "RATES_06": Rates06CopomEventStrategy,
    # Plan 03: Inflation / Cupom (v3.0)
    "INF_02": Inf02IpcaSurpriseStrategy,
    "INF_03": Inf03InflationCarryStrategy,
    "CUPOM_02": Cupom02OnshoreOffshoreStrategy,
    # Plan 04: Sovereign / Cross-asset (v3.0)
    "SOV_01": Sov01CdsCurveStrategy,
    "SOV_02": Sov02EmRelativeValueStrategy,
    "SOV_03": Sov03RatingMigrationStrategy,
    "CROSS_01": Cross01RegimeAllocationStrategy,
    "CROSS_02": Cross02RiskAppetiteStrategy,
}

# ---------------------------------------------------------------------------
# Auto-register existing 8 strategies in StrategyRegistry (v3.0)
# ---------------------------------------------------------------------------
# This bridges the legacy ALL_STRATEGIES dict with the new StrategyRegistry
# so both access patterns work.  New strategies (Phase 15+) use the
# @StrategyRegistry.register decorator directly; the original 8 are registered
# here manually since they predate the decorator pattern.
_ORIGINAL_8 = {
    "RATES_BR_01",
    "RATES_BR_02",
    "RATES_BR_03",
    "RATES_BR_04",
    "INF_BR_01",
    "FX_BR_01",
    "CUPOM_01",
    "SOV_BR_01",
}
for _sid, _cls in ALL_STRATEGIES.items():
    if _sid not in _ORIGINAL_8:
        continue  # v3.0 strategies use @StrategyRegistry.register
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
del _sid, _cls, _asset_class, _instruments, _ORIGINAL_8

__all__ = [
    "ALL_STRATEGIES",
    "BaseStrategy",
    # Plan 04: Cross-asset
    "Cross01RegimeAllocationStrategy",
    "Cross02RiskAppetiteStrategy",
    # Original 8
    "Cupom01CipBasisStrategy",
    # Plan 03
    "Cupom02OnshoreOffshoreStrategy",
    # Plan 01: FX
    "Fx02CarryMomentumStrategy",
    "Fx03FlowTacticalStrategy",
    "Fx04VolSurfaceRvStrategy",
    "Fx05TermsOfTradeStrategy",
    "FxBR01CarryFundamentalStrategy",
    # Plan 03
    "Inf02IpcaSurpriseStrategy",
    "Inf03InflationCarryStrategy",
    "InfBR01BreakevenStrategy",
    # Plan 02: Rates
    "Rates03BrUsSpreadStrategy",
    "Rates04TermPremiumStrategy",
    "Rates05FomcEventStrategy",
    "Rates06CopomEventStrategy",
    "RatesBR01CarryStrategy",
    "RatesBR02TaylorStrategy",
    "RatesBR03SlopeStrategy",
    "RatesBR04SpilloverStrategy",
    # Plan 04: Sovereign
    "Sov01CdsCurveStrategy",
    "Sov02EmRelativeValueStrategy",
    "Sov03RatingMigrationStrategy",
    "SovBR01FiscalRiskStrategy",
    "StrategyConfig",
    "StrategyPosition",
    "StrategyRegistry",
    "StrategySignal",
]

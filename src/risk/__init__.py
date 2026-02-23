"""Risk computation package -- VaR, CVaR, stress testing, limits, and monitoring."""

from src.risk.drawdown_manager import (
    AlertDispatcher,
    AssetClassLossTracker,
    CircuitBreakerConfig,
    CircuitBreakerEvent,
    CircuitBreakerState,
    DrawdownManager,
    StrategyLossTracker,
)
from src.risk.risk_limits import (
    LimitCheckResult,
    RiskLimitChecker,
    RiskLimitsConfig,
)
from src.risk.risk_limits_v2 import (
    LossRecord,
    RiskBudgetReport,
    RiskLimitsManager,
    RiskLimitsManagerConfig,
)
from src.risk.risk_monitor import RiskMonitor, RiskReport
from src.risk.stress_tester import (
    DEFAULT_SCENARIOS,
    StressResult,
    StressScenario,
    StressTester,
)
from src.risk.var_calculator import VaRCalculator, VaRDecomposition, VaRResult

__all__ = [
    "AlertDispatcher",
    "AssetClassLossTracker",
    "CircuitBreakerConfig",
    "CircuitBreakerEvent",
    "CircuitBreakerState",
    "DEFAULT_SCENARIOS",
    "DrawdownManager",
    "LimitCheckResult",
    "LossRecord",
    "RiskBudgetReport",
    "RiskLimitChecker",
    "RiskLimitsConfig",
    "RiskLimitsManager",
    "RiskLimitsManagerConfig",
    "RiskMonitor",
    "RiskReport",
    "StressResult",
    "StressScenario",
    "StressTester",
    "StrategyLossTracker",
    "VaRCalculator",
    "VaRDecomposition",
    "VaRResult",
]

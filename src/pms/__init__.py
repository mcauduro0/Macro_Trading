"""PMS (Portfolio Management System) v4.0 core package.

Provides position lifecycle management and analytics:
  - PositionManager: open/close/MTM/book operations
  - MarkToMarketService: instrument-aware pricing and risk metrics
  - TradeWorkflowService: signal-to-proposal pipeline with approval workflow
  - MorningPackService: daily briefing generation with action-first ordering
  - PerformanceAttributionEngine: multi-dimensional P&L decomposition
  - RiskMonitorService: daily risk snapshots with alerts and trend history
  - PMSRiskLimits: configurable risk limit thresholds
  - Pricing functions: B3 DI PU convention, NTN-B, CDS, FX

Usage:
    from src.pms import PositionManager, MarkToMarketService, TradeWorkflowService
    from src.pms import MorningPackService, PerformanceAttributionEngine
    from src.pms import RiskMonitorService, PMSRiskLimits
    from src.pms.pricing import rate_to_pu, compute_dv01_from_pu
"""

from src.pms.attribution import PerformanceAttributionEngine
from src.pms.morning_pack import MorningPackService
from src.pms.mtm_service import MarkToMarketService
from src.pms.position_manager import PositionManager
from src.pms.risk_limits_config import PMSRiskLimits
from src.pms.risk_monitor import RiskMonitorService
from src.pms.trade_workflow import TradeWorkflowService

__all__ = [
    "PositionManager",
    "MarkToMarketService",
    "TradeWorkflowService",
    "MorningPackService",
    "PerformanceAttributionEngine",
    "RiskMonitorService",
    "PMSRiskLimits",
]

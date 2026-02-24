"""PMS (Portfolio Management System) v4.0 core package.

Provides position lifecycle management:
  - PositionManager: open/close/MTM/book operations
  - MarkToMarketService: instrument-aware pricing and risk metrics
  - Pricing functions: B3 DI PU convention, NTN-B, CDS, FX

Usage:
    from src.pms import PositionManager, MarkToMarketService
    from src.pms.pricing import rate_to_pu, compute_dv01_from_pu
"""

from src.pms.mtm_service import MarkToMarketService
from src.pms.position_manager import PositionManager

__all__ = [
    "PositionManager",
    "MarkToMarketService",
]

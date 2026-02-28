"""Data source connectors package.

Re-exports the BaseConnector ABC, exception hierarchy, and all concrete
connector classes for convenient imports.

Phase 2 connectors (4):
    BcbPtaxConnector, BcbSgsConnector, FredConnector, YahooFinanceConnector

Phase 3 connectors (7):
    BcbFocusConnector, BcbFxFlowConnector, B3MarketDataConnector,
    CftcCotConnector, IbgeSidraConnector, StnFiscalConnector,
    TreasuryGovConnector

Phase 4 connectors (2):
    FmpTreasuryConnector, TradingEconDiCurveConnector

Global macro connectors (1):
    OecdSdmxConnector (OECD Economic Outlook structural estimates)

Placeholder connectors (1):
    AnbimaConnector (pending API access)
"""

# Placeholder connectors (pending API access)
from .anbima import AnbimaConnector

# Phase 3 connectors
from .b3_market_data import B3MarketDataConnector
from .base import (
    BaseConnector,
    ConnectorError,
    DataParsingError,
    FetchError,
    RateLimitError,
)
from .bcb_focus import BcbFocusConnector
from .bcb_fx_flow import BcbFxFlowConnector

# Phase 2 connectors
from .bcb_ptax import BcbPtaxConnector
from .bcb_sgs import BcbSgsConnector
from .cftc_cot import CftcCotConnector

# Phase 4 connectors
from .fmp_treasury import FmpTreasuryConnector
from .fred import FredConnector
from .ibge_sidra import IbgeSidraConnector
from .oecd_sdmx import OecdSdmxConnector
from .stn_fiscal import StnFiscalConnector
from .te_di_curve import TradingEconDiCurveConnector
from .treasury_gov import TreasuryGovConnector
from .yahoo_finance import YahooFinanceConnector

__all__ = [
    # Base
    "BaseConnector",
    "ConnectorError",
    "DataParsingError",
    "FetchError",
    "RateLimitError",
    # Phase 2 connectors
    "BcbPtaxConnector",
    "BcbSgsConnector",
    "FredConnector",
    "YahooFinanceConnector",
    # Phase 3 connectors
    "B3MarketDataConnector",
    "BcbFocusConnector",
    "BcbFxFlowConnector",
    "CftcCotConnector",
    "IbgeSidraConnector",
    "StnFiscalConnector",
    "TreasuryGovConnector",
    # Phase 4 connectors
    "FmpTreasuryConnector",
    "TradingEconDiCurveConnector",
    # Global macro connectors
    "OecdSdmxConnector",
    # Placeholder connectors
    "AnbimaConnector",
]

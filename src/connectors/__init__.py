"""Data source connectors package.

Re-exports the BaseConnector ABC, exception hierarchy, and all concrete
connector classes for convenient imports.

Phase 2 connectors (4):
    BcbPtaxConnector, BcbSgsConnector, FredConnector, YahooFinanceConnector

Phase 3 connectors (7):
    BcbFocusConnector, BcbFxFlowConnector, B3MarketDataConnector,
    CftcCotConnector, IbgeSidraConnector, StnFiscalConnector,
    TreasuryGovConnector

Placeholder connectors (1):
    AnbimaConnector (pending API access)
"""

from .base import (
    BaseConnector,
    ConnectorError,
    DataParsingError,
    FetchError,
    RateLimitError,
)

# Phase 2 connectors
from .bcb_ptax import BcbPtaxConnector
from .bcb_sgs import BcbSgsConnector
from .fred import FredConnector
from .yahoo_finance import YahooFinanceConnector

# Phase 3 connectors
from .b3_market_data import B3MarketDataConnector
from .bcb_focus import BcbFocusConnector
from .bcb_fx_flow import BcbFxFlowConnector
from .cftc_cot import CftcCotConnector
from .ibge_sidra import IbgeSidraConnector
from .stn_fiscal import StnFiscalConnector
from .treasury_gov import TreasuryGovConnector

# Placeholder connectors (pending API access)
from .anbima import AnbimaConnector

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
    # Placeholder connectors
    "AnbimaConnector",
]

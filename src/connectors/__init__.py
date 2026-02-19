"""Data source connectors package.

Re-exports the BaseConnector ABC, exception hierarchy, and all concrete
connector classes for convenient imports.
"""

from .base import (
    BaseConnector,
    ConnectorError,
    DataParsingError,
    FetchError,
    RateLimitError,
)
from .bcb_ptax import BcbPtaxConnector
from .bcb_sgs import BcbSgsConnector
from .fred import FredConnector
from .yahoo_finance import YahooFinanceConnector

__all__ = [
    "BaseConnector",
    "ConnectorError",
    "DataParsingError",
    "FetchError",
    "RateLimitError",
    "BcbPtaxConnector",
    "BcbSgsConnector",
    "FredConnector",
    "YahooFinanceConnector",
]

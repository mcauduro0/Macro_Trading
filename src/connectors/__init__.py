"""Data source connectors package.

Re-exports the BaseConnector ABC and exception hierarchy for convenient imports.
"""

from .base import (
    BaseConnector,
    ConnectorError,
    DataParsingError,
    FetchError,
    RateLimitError,
)

__all__ = [
    "BaseConnector",
    "ConnectorError",
    "DataParsingError",
    "FetchError",
    "RateLimitError",
]

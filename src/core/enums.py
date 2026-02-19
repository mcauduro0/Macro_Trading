"""Shared enumerations used across all models and modules.

All enums use the (str, Enum) mixin pattern so their values are
serializable strings, compatible with database storage and JSON output.
"""

from enum import Enum


class AssetClass(str, Enum):
    """Classification of tradeable instruments."""

    FX = "FX"
    EQUITY_INDEX = "EQUITY_INDEX"
    COMMODITY = "COMMODITY"
    FIXED_INCOME = "FIXED_INCOME"
    CRYPTO = "CRYPTO"


class Frequency(str, Enum):
    """Data observation frequency."""

    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    ANNUAL = "ANNUAL"


class Country(str, Enum):
    """Country codes (ISO 3166-1 alpha-2)."""

    BR = "BR"
    US = "US"


class CurveType(str, Enum):
    """Yield curve classification."""

    NOMINAL = "NOMINAL"
    REAL = "REAL"
    BREAKEVEN = "BREAKEVEN"
    SWAP = "SWAP"


class FlowType(str, Enum):
    """Capital/FX flow classification."""

    COMMERCIAL = "COMMERCIAL"
    FINANCIAL = "FINANCIAL"
    SWAP_STOCK = "SWAP_STOCK"
    NET = "NET"


class FiscalMetric(str, Enum):
    """Government fiscal metric types."""

    PRIMARY_BALANCE = "PRIMARY_BALANCE"
    NOMINAL_BALANCE = "NOMINAL_BALANCE"
    GROSS_DEBT = "GROSS_DEBT"
    NET_DEBT = "NET_DEBT"
    REVENUE = "REVENUE"
    EXPENDITURE = "EXPENDITURE"

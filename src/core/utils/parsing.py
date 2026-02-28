"""Numeric value parsing utilities for multi-format data sources.

Handles both period-decimal (international) and comma-decimal (Brazilian)
number formats, as encountered in BCB SGS, FRED, and other API responses.

Examples::

    >>> parse_numeric_value("0.16", ".")
    0.16
    >>> parse_numeric_value("1.234,56", ",")
    1234.56
    >>> parse_numeric_value("", ".")  # returns None
    >>> parse_numeric_value("-", ".")  # returns None
"""

from __future__ import annotations


def parse_numeric_value(raw: str, decimal_sep: str = ".") -> float | None:
    """Parse a numeric string into a float, handling various formats.

    Supports both period-decimal (international: 1,234.56) and comma-decimal
    (Brazilian: 1.234,56) conventions.

    Args:
        raw: The raw string value to parse.
        decimal_sep: The decimal separator character. Use "." for international
            format (e.g., "1,234.56") or "," for Brazilian format (e.g., "1.234,56").

    Returns:
        The parsed float value, or None for empty/placeholder values.

    Raises:
        ValueError: If the string cannot be parsed as a number.

    Examples:
        >>> parse_numeric_value("0.16", ".")
        0.16
        >>> parse_numeric_value("1.234,56", ",")
        1234.56
        >>> parse_numeric_value("1,234.56", ".")
        1234.56
        >>> parse_numeric_value("", ".")  # returns None
        >>> parse_numeric_value("-", ".")  # returns None
        >>> parse_numeric_value(".", ".")  # returns None
    """
    if raw is None:
        return None

    if not isinstance(raw, str):
        raw = str(raw)

    stripped = raw.strip()

    # Return None for empty, dash-only, or lone-separator placeholders
    if stripped in ("", "-", ".", ","):
        return None

    if decimal_sep == ",":
        # Brazilian format: periods are thousands separators, comma is decimal
        # e.g., "1.234,56" -> "1234.56"
        cleaned = stripped.replace(".", "").replace(",", ".")
    else:
        # International format: commas are thousands separators, period is decimal
        # e.g., "1,234.56" -> "1234.56"
        cleaned = stripped.replace(",", "")

    try:
        return float(cleaned)
    except ValueError:
        raise ValueError(
            f"Cannot parse '{raw}' as a numeric value " f"(decimal_sep='{decimal_sep}')"
        )

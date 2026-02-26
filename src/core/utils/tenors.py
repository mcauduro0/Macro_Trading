"""Tenor parsing and conversion utilities.

Provides functions for parsing financial tenor strings (e.g., "3M", "1Y", "21D")
and converting them to calendar days, dates, and business days.

Examples::

    >>> parse_tenor("3M")
    (3, 'M')
    >>> tenor_to_calendar_days("1Y")
    365
    >>> tenor_to_date("1M", date(2025, 1, 15))
    datetime.date(2025, 2, 15)
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

TENOR_PATTERN = re.compile(r"^(\d+)([DWMY])$", re.IGNORECASE)

# Approximate day counts per unit (for quick estimates)
_UNIT_DAYS = {
    "D": 1,
    "W": 7,
    "M": 30,
    "Y": 365,
}


def parse_tenor(tenor: str) -> tuple[int, str]:
    """Parse a tenor string into its numeric count and unit letter.

    Args:
        tenor: A tenor string like "3M", "1Y", "21D", "2W".

    Returns:
        A tuple of (count, unit) where unit is one of D, W, M, Y (uppercase).

    Raises:
        ValueError: If the tenor string does not match the expected pattern.

    Examples:
        >>> parse_tenor("3M")
        (3, 'M')
        >>> parse_tenor("21D")
        (21, 'D')
        >>> parse_tenor("1y")  # case-insensitive
        (1, 'Y')
    """
    match = TENOR_PATTERN.match(tenor.strip())
    if not match:
        raise ValueError(
            f"Invalid tenor format: '{tenor}'. "
            "Expected pattern like '3M', '1Y', '21D', '2W'."
        )
    count = int(match.group(1))
    unit = match.group(2).upper()
    return count, unit


def tenor_to_calendar_days(tenor: str) -> int:
    """Convert a tenor string to an approximate number of calendar days.

    Uses standard approximations: D=1, W=7, M=30, Y=365.

    Args:
        tenor: A tenor string like "3M", "1Y".

    Returns:
        Approximate number of calendar days.

    Examples:
        >>> tenor_to_calendar_days("3M")
        90
        >>> tenor_to_calendar_days("1Y")
        365
        >>> tenor_to_calendar_days("2W")
        14
    """
    count, unit = parse_tenor(tenor)
    return count * _UNIT_DAYS[unit]


def tenor_to_date(
    tenor: str,
    reference_date: date,
    calendar: object | None = None,
) -> date:
    """Convert a tenor string to an actual target date.

    For D units with a calendar, uses the calendar's offset method.
    For W, M, Y units, uses dateutil.relativedelta for exact math.
    If a calendar is provided and the result is not a business day,
    rolls forward to the next business day (Following convention).

    Args:
        tenor: A tenor string like "1M", "1Y", "21D".
        reference_date: The starting date.
        calendar: Optional bizdays Calendar object for business day adjustment.
            If provided, the result is adjusted to the next business day
            when it falls on a non-business day.

    Returns:
        The target date corresponding to the tenor offset.

    Examples:
        >>> tenor_to_date("1M", date(2025, 1, 15))
        datetime.date(2025, 2, 15)
        >>> tenor_to_date("1Y", date(2025, 1, 15))
        datetime.date(2026, 1, 15)
    """
    count, unit = parse_tenor(tenor)

    if unit == "D":
        if calendar is not None and hasattr(calendar, "offset"):
            result = calendar.offset(reference_date, count)
            # bizdays.offset may return a date or datetime-like
            if hasattr(result, "date") and callable(result.date):
                return result.date()
            return result
        result = reference_date + timedelta(days=count)
    elif unit == "W":
        result = reference_date + timedelta(weeks=count)
    elif unit == "M":
        result = reference_date + relativedelta(months=count)
    elif unit == "Y":
        result = reference_date + relativedelta(years=count)
    else:
        raise ValueError(f"Unknown tenor unit: {unit}")  # pragma: no cover

    # Business day adjustment (Following convention)
    if calendar is not None and hasattr(calendar, "isbizday"):
        if not calendar.isbizday(result):
            result = calendar.following(result)

    return result


def tenor_to_business_days(
    tenor: str,
    reference_date: date,
    calendar: object,
) -> int:
    """Convert a tenor to the number of business days from the reference date.

    Computes the target date using tenor_to_date (with business day adjustment)
    and then counts the business days between the reference and target dates.

    Args:
        tenor: A tenor string like "3M", "1Y".
        reference_date: The starting date.
        calendar: A bizdays Calendar object with bizdays() method.

    Returns:
        Number of business days between reference_date and the tenor target date.
    """
    target = tenor_to_date(tenor, reference_date, calendar=calendar)
    return calendar.bizdays(reference_date, target)


def find_closest_tenor(
    curve: dict[int, float],
    target: int,
    tolerance: int,
) -> int | None:
    """Find the closest available tenor to the target within tolerance.

    Common utility used by multiple strategies that operate on curve data
    (DI, NTN-B, Cupom Cambial, etc.).

    Args:
        curve: Tenor-to-rate mapping (tenor in days -> rate).
        target: Target tenor in days.
        tolerance: Maximum allowed distance from target in days.

    Returns:
        Closest tenor key, or None if nothing within tolerance.
    """
    best_tenor = None
    best_dist = float("inf")
    for tenor in curve:
        dist = abs(tenor - target)
        if dist < best_dist and dist <= tolerance:
            best_dist = dist
            best_tenor = tenor
    return best_tenor

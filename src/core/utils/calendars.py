"""Business day calendar utilities for Brazilian and US markets.

Uses bizdays (ANBIMA calendar) for Brazilian business days and
exchange_calendars (XNYS) for US/NYSE business days. Calendars
are lazily loaded on first access.

Examples::

    >>> from datetime import date
    >>> is_business_day_br(date(2025, 1, 1))  # New Year
    False
    >>> is_business_day_us(date(2025, 7, 4))  # Independence Day
    False
    >>> count_business_days_br(date(2025, 1, 2), date(2025, 1, 10))
    6
"""

from __future__ import annotations

from datetime import date

import exchange_calendars as xcals
import pandas as pd
from bizdays import Calendar

# ---------------------------------------------------------------------------
# Lazy calendar singletons
# ---------------------------------------------------------------------------
_anbima_cal: Calendar | None = None
_nyse_cal = None  # exchange_calendars.ExchangeCalendar


def _get_anbima() -> Calendar:
    """Return the ANBIMA business day calendar, loading on first call."""
    global _anbima_cal
    if _anbima_cal is None:
        _anbima_cal = Calendar.load("ANBIMA")
    return _anbima_cal


def _get_nyse():  # -> exchange_calendars.ExchangeCalendar
    """Return the NYSE exchange calendar, loading on first call."""
    global _nyse_cal
    if _nyse_cal is None:
        _nyse_cal = xcals.get_calendar("XNYS")
    return _nyse_cal


# ---------------------------------------------------------------------------
# Brazilian (ANBIMA) calendar functions
# ---------------------------------------------------------------------------
def is_business_day_br(d: date) -> bool:
    """Check if a date is a business day on the ANBIMA calendar.

    Args:
        d: The date to check.

    Returns:
        True if the date is a business day in Brazil.
    """
    cal = _get_anbima()
    return cal.isbizday(d)


def count_business_days_br(start: date, end: date) -> int:
    """Count business days between two dates on the ANBIMA calendar.

    The count is exclusive of the start date and inclusive of the end date,
    following the ANBIMA convention (e.g., for DI futures day-count).

    Args:
        start: Start date (exclusive).
        end: End date (inclusive).

    Returns:
        Number of business days between start and end.
    """
    cal = _get_anbima()
    return cal.bizdays(start, end)


def add_business_days_br(d: date, n: int) -> date:
    """Add n business days to a date using the ANBIMA calendar.

    Args:
        d: Reference date.
        n: Number of business days to add (can be negative).

    Returns:
        The resulting date after offsetting by n business days.
    """
    cal = _get_anbima()
    return cal.offset(d, n)


def next_business_day_br(d: date) -> date:
    """Return d if it is a business day, otherwise the next business day.

    Args:
        d: The reference date.

    Returns:
        The same date if it is a business day, or the next one.
    """
    cal = _get_anbima()
    if cal.isbizday(d):
        return d
    return cal.following(d)


def previous_business_day_br(d: date) -> date:
    """Return d if it is a business day, otherwise the previous business day.

    Args:
        d: The reference date.

    Returns:
        The same date if it is a business day, or the previous one.
    """
    cal = _get_anbima()
    if cal.isbizday(d):
        return d
    return cal.preceding(d)


# ---------------------------------------------------------------------------
# US (NYSE) calendar functions
# ---------------------------------------------------------------------------
def is_business_day_us(d: date) -> bool:
    """Check if a date is a trading session on the NYSE.

    Args:
        d: The date to check.

    Returns:
        True if the NYSE is open on that date.
    """
    cal = _get_nyse()
    ts = pd.Timestamp(d)
    return cal.is_session(ts)


def count_business_days_us(start: date, end: date) -> int:
    """Count NYSE trading sessions between two dates.

    Both start and end are inclusive in the session count, but we return
    the count excluding the start date to match the BR convention.

    Args:
        start: Start date (exclusive).
        end: End date (inclusive).

    Returns:
        Number of NYSE trading sessions in the range (start, end].
    """
    cal = _get_nyse()
    ts_start = pd.Timestamp(start)
    ts_end = pd.Timestamp(end)

    # Clamp to calendar bounds
    if ts_start < cal.first_session:
        ts_start = cal.first_session
    if ts_end > cal.last_session:
        ts_end = cal.last_session

    if ts_start >= ts_end:
        return 0

    sessions = cal.sessions_in_range(ts_start, ts_end)
    # Exclude start date from count if it is a session
    count = len(sessions)
    if cal.is_session(ts_start):
        count -= 1
    return count


def next_business_day_us(d: date) -> date:
    """Return d if it is a NYSE session, otherwise the next session.

    Args:
        d: The reference date.

    Returns:
        The same date if the NYSE is open, or the next trading date.
    """
    cal = _get_nyse()
    ts = pd.Timestamp(d)

    # Clamp if before calendar start
    if ts < cal.first_session:
        return cal.first_session.date()

    if cal.is_session(ts):
        return d

    # Find next valid session
    next_ts = cal.date_to_session(ts, direction="next")
    return next_ts.date()


def previous_business_day_us(d: date) -> date:
    """Return d if it is a NYSE session, otherwise the previous session.

    Args:
        d: The reference date.

    Returns:
        The same date if the NYSE is open, or the previous trading date.
    """
    cal = _get_nyse()
    ts = pd.Timestamp(d)

    # Clamp if after calendar end
    if ts > cal.last_session:
        return cal.last_session.date()

    if cal.is_session(ts):
        return d

    # Find previous valid session
    prev_ts = cal.date_to_session(ts, direction="previous")
    return prev_ts.date()

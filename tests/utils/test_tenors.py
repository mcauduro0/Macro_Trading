"""Tests for src.core.utils.tenors module."""

from __future__ import annotations

from datetime import date

import pytest

from src.core.utils.tenors import (
    parse_tenor,
    tenor_to_business_days,
    tenor_to_calendar_days,
    tenor_to_date,
)


class TestParseTenor:
    """Tests for parse_tenor function."""

    def test_months(self) -> None:
        assert parse_tenor("3M") == (3, "M")

    def test_years(self) -> None:
        assert parse_tenor("1Y") == (1, "Y")

    def test_days(self) -> None:
        assert parse_tenor("21D") == (21, "D")

    def test_weeks(self) -> None:
        assert parse_tenor("2W") == (2, "W")

    def test_case_insensitive(self) -> None:
        assert parse_tenor("3m") == (3, "M")
        assert parse_tenor("1y") == (1, "Y")

    def test_invalid_tenor_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid tenor format"):
            parse_tenor("XYZ")

    def test_empty_tenor_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid tenor format"):
            parse_tenor("")

    def test_no_number_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid tenor format"):
            parse_tenor("M")


class TestTenorToCalendarDays:
    """Tests for tenor_to_calendar_days function."""

    def test_three_months(self) -> None:
        assert tenor_to_calendar_days("3M") == 90

    def test_one_year(self) -> None:
        assert tenor_to_calendar_days("1Y") == 365

    def test_one_day(self) -> None:
        assert tenor_to_calendar_days("1D") == 1

    def test_two_weeks(self) -> None:
        assert tenor_to_calendar_days("2W") == 14

    def test_six_months(self) -> None:
        assert tenor_to_calendar_days("6M") == 180

    def test_two_years(self) -> None:
        assert tenor_to_calendar_days("2Y") == 730


class TestTenorToDate:
    """Tests for tenor_to_date function."""

    def test_one_month(self) -> None:
        result = tenor_to_date("1M", date(2025, 1, 15))
        assert result == date(2025, 2, 15)

    def test_one_year(self) -> None:
        result = tenor_to_date("1Y", date(2025, 1, 15))
        assert result == date(2026, 1, 15)

    def test_seven_days(self) -> None:
        result = tenor_to_date("7D", date(2025, 1, 15))
        assert result == date(2025, 1, 22)

    def test_two_weeks(self) -> None:
        result = tenor_to_date("2W", date(2025, 1, 15))
        assert result == date(2025, 1, 29)

    def test_month_end_rollover(self) -> None:
        # 1M from Jan 31 -> Feb 28
        result = tenor_to_date("1M", date(2025, 1, 31))
        assert result == date(2025, 2, 28)

    def test_with_calendar_business_day_adjustment(self) -> None:
        """When a calendar is provided, non-business days roll to next BD."""
        from bizdays import Calendar
        cal = Calendar.load("ANBIMA")

        # 1M from Dec 31, 2024 -> Jan 31, 2025 is a Friday (business day)
        result = tenor_to_date("1M", date(2024, 12, 31), calendar=cal)
        assert result == date(2025, 1, 31)
        assert cal.isbizday(result)

    def test_with_calendar_rolls_to_next_bd(self) -> None:
        """When target falls on holiday, roll forward."""
        from bizdays import Calendar
        cal = Calendar.load("ANBIMA")

        # Find a case where the result lands on a non-BD
        # 1M from Feb 1, 2025 -> Mar 1, 2025 (Saturday) -> rolls to Mar 3 (but Carnaval)
        # -> Mar 5, 2025 (Ash Wednesday, which is a BD per ANBIMA)
        result = tenor_to_date("1M", date(2025, 2, 1), calendar=cal)
        assert cal.isbizday(result)


class TestTenorToBusinessDays:
    """Tests for tenor_to_business_days function."""

    def test_counts_business_days_for_tenor(self) -> None:
        from bizdays import Calendar
        cal = Calendar.load("ANBIMA")

        # 1M from Jan 2, 2025 -> Feb 2, 2025 (Sunday, rolls to Feb 3)
        bd_count = tenor_to_business_days("1M", date(2025, 1, 2), calendar=cal)
        assert bd_count > 0
        # Should be approximately 21-22 business days
        assert 19 <= bd_count <= 23

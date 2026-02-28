"""Tests for src.core.utils.calendars module."""

from __future__ import annotations

from datetime import date

from src.core.utils.calendars import (
    add_business_days_br,
    count_business_days_br,
    count_business_days_us,
    is_business_day_br,
    is_business_day_us,
    next_business_day_br,
    next_business_day_us,
    previous_business_day_br,
    previous_business_day_us,
)


class TestBrazilianCalendar:
    """Tests for ANBIMA calendar functions."""

    def test_carnaval_monday_is_not_business_day(self) -> None:
        # Carnaval Monday 2025
        assert is_business_day_br(date(2025, 3, 3)) is False

    def test_carnaval_tuesday_is_not_business_day(self) -> None:
        # Carnaval Tuesday 2025
        assert is_business_day_br(date(2025, 3, 4)) is False

    def test_ash_wednesday_is_business_day(self) -> None:
        # ANBIMA treats Ash Wednesday (March 5, 2025) as a business day
        assert is_business_day_br(date(2025, 3, 5)) is True

    def test_new_year_is_not_business_day(self) -> None:
        assert is_business_day_br(date(2025, 1, 1)) is False

    def test_normal_thursday_is_business_day(self) -> None:
        # January 2, 2025 is a normal Thursday
        assert is_business_day_br(date(2025, 1, 2)) is True

    def test_saturday_is_not_business_day(self) -> None:
        assert is_business_day_br(date(2025, 1, 4)) is False

    def test_count_business_days_br_known_range(self) -> None:
        # Jan 2 to Jan 10, 2025: expect 6 business days
        # (Jan 3, 6, 7, 8, 9, 10 -- excluding start Jan 2)
        result = count_business_days_br(date(2025, 1, 2), date(2025, 1, 10))
        assert result == 6

    def test_add_business_days_br(self) -> None:
        # Jan 2, 2025 + 3 BD = Jan 7, 2025 (skips weekend Jan 4-5)
        result = add_business_days_br(date(2025, 1, 2), 3)
        assert result == date(2025, 1, 7)

    def test_next_business_day_br_on_business_day(self) -> None:
        # Already a business day -- returns same date
        assert next_business_day_br(date(2025, 1, 2)) == date(2025, 1, 2)

    def test_next_business_day_br_on_weekend(self) -> None:
        # Saturday Jan 4 -> Monday Jan 6
        assert next_business_day_br(date(2025, 1, 4)) == date(2025, 1, 6)

    def test_previous_business_day_br_on_business_day(self) -> None:
        assert previous_business_day_br(date(2025, 1, 2)) == date(2025, 1, 2)

    def test_previous_business_day_br_on_weekend(self) -> None:
        # Sunday Jan 5 -> Friday Jan 3
        assert previous_business_day_br(date(2025, 1, 5)) == date(2025, 1, 3)


class TestUSCalendar:
    """Tests for NYSE calendar functions."""

    def test_new_year_is_not_business_day(self) -> None:
        assert is_business_day_us(date(2025, 1, 1)) is False

    def test_independence_day_is_not_business_day(self) -> None:
        assert is_business_day_us(date(2025, 7, 4)) is False

    def test_normal_thursday_is_business_day(self) -> None:
        assert is_business_day_us(date(2025, 1, 2)) is True

    def test_saturday_is_not_business_day(self) -> None:
        assert is_business_day_us(date(2025, 1, 4)) is False

    def test_count_business_days_us_known_range(self) -> None:
        # Jan 13 to Jan 17, 2025: expect 4 NYSE sessions (excluding start)
        # Sessions: Jan 14, 15, 16, 17 (Jan 20 is MLK Day, outside range)
        result = count_business_days_us(date(2025, 1, 13), date(2025, 1, 17))
        assert result == 4

    def test_next_business_day_us_on_holiday(self) -> None:
        # Jan 1, 2025 (Wed, New Year) -> Jan 2 (Thu)
        assert next_business_day_us(date(2025, 1, 1)) == date(2025, 1, 2)

    def test_next_business_day_us_on_session(self) -> None:
        assert next_business_day_us(date(2025, 1, 2)) == date(2025, 1, 2)

    def test_previous_business_day_us_on_holiday(self) -> None:
        # Jan 1, 2025 (Wed, New Year) -> Dec 31, 2024 (Tue)
        assert previous_business_day_us(date(2025, 1, 1)) == date(2024, 12, 31)

    def test_previous_business_day_us_on_session(self) -> None:
        assert previous_business_day_us(date(2025, 1, 2)) == date(2025, 1, 2)

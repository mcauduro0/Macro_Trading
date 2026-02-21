"""Tests for src.core.utils.parsing module."""

from __future__ import annotations

import pytest

from src.core.utils.parsing import parse_numeric_value


class TestParseNumericValue:
    """Tests for parse_numeric_value function."""

    # -- Period-decimal (international format) --

    def test_simple_period_decimal(self) -> None:
        assert parse_numeric_value("0.16", ".") == 0.16

    def test_period_decimal_with_comma_thousands(self) -> None:
        assert parse_numeric_value("1,234.56", ".") == 1234.56

    def test_period_decimal_integer(self) -> None:
        assert parse_numeric_value("42", ".") == 42.0

    def test_period_decimal_negative(self) -> None:
        assert parse_numeric_value("-3.14", ".") == -3.14

    # -- Comma-decimal (Brazilian format) --

    def test_comma_decimal_with_period_thousands(self) -> None:
        assert parse_numeric_value("1.234,56", ",") == 1234.56

    def test_simple_comma_decimal(self) -> None:
        assert parse_numeric_value("0,16", ",") == 0.16

    def test_comma_decimal_large_number(self) -> None:
        assert parse_numeric_value("1.000.000,99", ",") == 1000000.99

    # -- None returns for empty/placeholder values --

    def test_empty_string_returns_none(self) -> None:
        assert parse_numeric_value("", ".") is None

    def test_dash_returns_none(self) -> None:
        assert parse_numeric_value("-", ".") is None

    def test_period_only_returns_none(self) -> None:
        assert parse_numeric_value(".", ".") is None

    def test_comma_only_returns_none(self) -> None:
        assert parse_numeric_value(",", ",") is None

    def test_whitespace_only_returns_none(self) -> None:
        assert parse_numeric_value("   ", ".") is None

    # -- Error cases --

    def test_unparseable_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse"):
            parse_numeric_value("abc", ".")

    def test_mixed_separators_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse"):
            parse_numeric_value("12.34.56", ".")

    # -- Edge cases --

    def test_leading_trailing_whitespace_stripped(self) -> None:
        assert parse_numeric_value("  308.417  ", ".") == 308.417

    def test_zero(self) -> None:
        assert parse_numeric_value("0", ".") == 0.0

    def test_default_decimal_sep_is_period(self) -> None:
        assert parse_numeric_value("3.14") == 3.14

"""Tests for PointInTimeDataLoader PIT-correct queries.

These tests require a running database with seeded data from v1.0.
Tests are marked with ``@skip_no_db`` and will be skipped if the database
is not available.
"""

from datetime import date

import pytest
import sqlalchemy as sa

from src.agents.data_loader import PointInTimeDataLoader


def _db_available() -> bool:
    """Check if the PostgreSQL database is reachable."""
    try:
        from src.core.database import sync_engine

        with sync_engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
        return True
    except Exception:
        return False


skip_no_db = pytest.mark.skipif(not _db_available(), reason="Database not available")


# ---------------------------------------------------------------------------
# Instantiation and interface
# ---------------------------------------------------------------------------
class TestLoaderInterface:
    def test_instantiation(self) -> None:
        loader = PointInTimeDataLoader()
        assert loader is not None

    def test_has_all_methods(self) -> None:
        loader = PointInTimeDataLoader()
        expected_methods = [
            "get_macro_series",
            "get_latest_macro_value",
            "get_curve",
            "get_curve_history",
            "get_market_data",
            "get_flow_data",
            "get_focus_expectations",
        ]
        for method_name in expected_methods:
            assert hasattr(loader, method_name), f"Missing method: {method_name}"
            assert callable(getattr(loader, method_name))


# ---------------------------------------------------------------------------
# Database-dependent tests (skipped without DB)
# ---------------------------------------------------------------------------
@skip_no_db
class TestLoaderMacroSeries:
    def test_returns_dataframe(self) -> None:
        import pandas as pd

        loader = PointInTimeDataLoader()
        df = loader.get_macro_series("BR_SELIC_TARGET", date(2024, 6, 15))
        assert isinstance(df, pd.DataFrame)
        assert "value" in df.columns
        assert len(df) > 0

    def test_pit_correctness(self) -> None:
        """Later as_of_date should return more or equal rows."""
        loader = PointInTimeDataLoader()
        df_early = loader.get_macro_series("BR_SELIC_TARGET", date(2020, 1, 1))
        df_late = loader.get_macro_series("BR_SELIC_TARGET", date(2024, 1, 1))
        assert len(df_late) >= len(df_early)

    def test_dates_not_after_as_of(self) -> None:
        loader = PointInTimeDataLoader()
        df = loader.get_macro_series("BR_SELIC_TARGET", date(2024, 6, 15))
        if not df.empty:
            # Index is datetime -- compare date part
            max_date = df.index.max().date()
            assert max_date <= date(2024, 6, 15)

    def test_empty_for_nonexistent_series(self) -> None:
        loader = PointInTimeDataLoader()
        df = loader.get_macro_series("NONEXISTENT_SERIES", date(2024, 6, 15))
        assert df.empty


@skip_no_db
class TestLoaderLatestValue:
    def test_returns_float(self) -> None:
        loader = PointInTimeDataLoader()
        val = loader.get_latest_macro_value("BR_SELIC_TARGET", date(2024, 6, 15))
        assert val is not None
        assert isinstance(val, float)

    def test_none_for_nonexistent(self) -> None:
        loader = PointInTimeDataLoader()
        val = loader.get_latest_macro_value("NONEXISTENT_SERIES", date(2024, 6, 15))
        assert val is None


@skip_no_db
class TestLoaderCurve:
    def test_returns_dict(self) -> None:
        loader = PointInTimeDataLoader()
        curve = loader.get_curve("DI_PRE", date(2024, 6, 15))
        assert isinstance(curve, dict)
        if curve:
            # Keys are tenor_days (int), values are rates (float)
            for k, v in curve.items():
                assert isinstance(k, int)
                assert isinstance(v, float)

    def test_empty_for_nonexistent_curve(self) -> None:
        loader = PointInTimeDataLoader()
        curve = loader.get_curve("NONEXISTENT_CURVE", date(2024, 6, 15))
        assert curve == {}


@skip_no_db
class TestLoaderMarketData:
    def test_returns_dataframe(self) -> None:
        import pandas as pd

        loader = PointInTimeDataLoader()
        df = loader.get_market_data("USDBRL", date(2024, 6, 15))
        assert isinstance(df, pd.DataFrame)
        if not df.empty:
            assert "close" in df.columns

    def test_empty_for_nonexistent_ticker(self) -> None:
        loader = PointInTimeDataLoader()
        df = loader.get_market_data("NONEXISTENT_TICKER", date(2024, 6, 15))
        assert df.empty

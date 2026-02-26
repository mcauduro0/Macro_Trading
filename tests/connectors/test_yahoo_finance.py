"""Tests for YahooFinanceConnector.

Verifies ticker registry, batching, record parsing, NaN handling,
and UTC timestamp generation. Mocks yfinance.download() to avoid
real network calls.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from src.connectors.yahoo_finance import YahooFinanceConnector

# ---------------------------------------------------------------------------
# Ticker registry tests
# ---------------------------------------------------------------------------


class TestTickerRegistry:
    """Tests for the TICKERS class-level constant."""

    def test_tickers_registry_has_25_plus(self):
        """Registry must contain at least 25 tickers per requirement."""
        assert len(YahooFinanceConnector.TICKERS) >= 25

    def test_tickers_registry_has_key_tickers(self):
        """Essential tickers from the Fase0 guide must be present."""
        required = ["USDBRL", "SP500", "GOLD", "EWZ", "VIX", "IBOVESPA", "DXY"]
        for ticker in required:
            assert ticker in YahooFinanceConnector.TICKERS, (
                f"Missing required ticker: {ticker}"
            )

    def test_tickers_registry_fx_symbols(self):
        """FX tickers must map to correct Yahoo symbols."""
        assert YahooFinanceConnector.TICKERS["USDBRL"] == "BRL=X"
        assert YahooFinanceConnector.TICKERS["EURUSD"] == "EURUSD=X"
        assert YahooFinanceConnector.TICKERS["DXY"] == "DX-Y.NYB"

    def test_tickers_registry_index_symbols(self):
        """Equity index tickers must map to correct Yahoo symbols."""
        assert YahooFinanceConnector.TICKERS["IBOVESPA"] == "^BVSP"
        assert YahooFinanceConnector.TICKERS["SP500"] == "^GSPC"
        assert YahooFinanceConnector.TICKERS["VIX"] == "^VIX"

    def test_tickers_registry_commodity_symbols(self):
        """Commodity tickers must map to correct Yahoo symbols."""
        assert YahooFinanceConnector.TICKERS["GOLD"] == "GC=F"
        assert YahooFinanceConnector.TICKERS["OIL_WTI"] == "CL=F"
        assert YahooFinanceConnector.TICKERS["IRON_ORE_PROXY"] == "VALE3.SA"


# ---------------------------------------------------------------------------
# Batching tests
# ---------------------------------------------------------------------------


class TestBatching:
    """Tests for the _batch_tickers() method."""

    def test_batch_tickers_creates_correct_batches(self):
        """Tickers should be split into batches of BATCH_SIZE."""
        connector = YahooFinanceConnector()
        batches = connector._batch_tickers()
        # Each batch should have at most BATCH_SIZE tickers
        for batch in batches:
            assert len(batch) <= connector.BATCH_SIZE
        # Total tickers across all batches should equal registry size
        total = sum(len(b) for b in batches)
        assert total == len(connector.TICKERS)

    def test_batch_tickers_with_custom_list(self):
        """Custom ticker list should also be batched correctly."""
        connector = YahooFinanceConnector()
        custom = ["BRL=X", "^GSPC", "GC=F"]
        batches = connector._batch_tickers(custom)
        total = sum(len(b) for b in batches)
        assert total == 3

    def test_batch_tickers_with_exact_batch_size(self):
        """A list exactly matching batch size should produce one batch."""
        connector = YahooFinanceConnector()
        custom = ["A", "B", "C", "D", "E"]  # 5 == BATCH_SIZE
        batches = connector._batch_tickers(custom)
        assert len(batches) == 1
        assert len(batches[0]) == 5


# ---------------------------------------------------------------------------
# Helpers -- mock DataFrame builders
# ---------------------------------------------------------------------------


def _make_single_ticker_df() -> pd.DataFrame:
    """Create a DataFrame mimicking single-ticker yf.download() output."""
    dates = pd.to_datetime(["2025-01-02", "2025-01-03"])
    data = {
        "Open": [6.18, 6.19],
        "High": [6.21, 6.22],
        "Low": [6.15, 6.17],
        "Close": [6.19, 6.20],
        "Volume": [0, 0],
    }
    return pd.DataFrame(data, index=dates)


def _make_multi_ticker_df() -> pd.DataFrame:
    """Create a DataFrame mimicking multi-ticker yf.download() output."""
    dates = pd.to_datetime(["2025-01-02", "2025-01-03"])
    arrays = [
        ["BRL=X", "BRL=X", "BRL=X", "BRL=X", "BRL=X",
         "^GSPC", "^GSPC", "^GSPC", "^GSPC", "^GSPC"],
        ["Open", "High", "Low", "Close", "Volume",
         "Open", "High", "Low", "Close", "Volume"],
    ]
    tuples = list(zip(*arrays))
    index = pd.MultiIndex.from_tuples(tuples, names=["Ticker", "Price"])
    data = [
        [6.18, 6.21, 6.15, 6.19, 0,
         5881.63, 5906.47, 5867.08, 5881.63, 3544500000],
        [6.19, 6.22, 6.17, 6.20, 0,
         5900.12, 5920.87, 5880.56, 5906.47, 3628100000],
    ]
    return pd.DataFrame(data, index=dates, columns=index)


def _make_df_with_nans() -> pd.DataFrame:
    """Create a DataFrame with NaN values for testing None conversion."""
    dates = pd.to_datetime(["2025-01-02"])
    data = {
        "Open": [6.18],
        "High": [np.nan],
        "Low": [6.15],
        "Close": [np.nan],
        "Volume": [np.nan],
    }
    return pd.DataFrame(data, index=dates)


# ---------------------------------------------------------------------------
# Record parsing tests
# ---------------------------------------------------------------------------


class TestRecordParsing:
    """Tests for DataFrame-to-record conversion."""

    def test_fetch_creates_records_with_correct_fields(self):
        """Records must have all required OHLCV fields plus metadata."""
        connector = YahooFinanceConnector()
        reverse_map = {"BRL=X": "USDBRL"}
        df = _make_single_ticker_df()

        records = connector._parse_dataframe(df, ["BRL=X"], reverse_map)

        assert len(records) == 2
        rec = records[0]
        assert rec["_ticker"] == "USDBRL"
        assert rec["frequency"] == "daily"
        assert rec["source"] == "YAHOO_FINANCE"
        assert rec["open"] == pytest.approx(6.18)
        assert rec["high"] == pytest.approx(6.21)
        assert rec["low"] == pytest.approx(6.15)
        assert rec["close"] == pytest.approx(6.19)
        assert rec["volume"] == pytest.approx(0.0)
        assert rec["adjusted_close"] == rec["close"]

    def test_multi_ticker_parsing(self):
        """Multi-ticker DataFrame should produce records for all tickers."""
        connector = YahooFinanceConnector()
        reverse_map = {"BRL=X": "USDBRL", "^GSPC": "SP500"}
        df = _make_multi_ticker_df()

        records = connector._parse_dataframe(
            df, ["BRL=X", "^GSPC"], reverse_map
        )

        tickers = {r["_ticker"] for r in records}
        assert tickers == {"USDBRL", "SP500"}
        assert len(records) == 4  # 2 dates x 2 tickers

    def test_nan_values_converted_to_none(self):
        """NaN values in the DataFrame should become None in records."""
        connector = YahooFinanceConnector()
        reverse_map = {"BRL=X": "USDBRL"}
        df = _make_df_with_nans()

        records = connector._parse_dataframe(df, ["BRL=X"], reverse_map)

        assert len(records) == 1
        rec = records[0]
        assert rec["open"] == pytest.approx(6.18)
        assert rec["high"] is None
        assert rec["close"] is None
        assert rec["volume"] is None

    def test_record_has_utc_timestamp(self):
        """Record timestamps must be timezone-aware (UTC)."""
        connector = YahooFinanceConnector()
        reverse_map = {"BRL=X": "USDBRL"}
        df = _make_single_ticker_df()

        records = connector._parse_dataframe(df, ["BRL=X"], reverse_map)

        ts = records[0]["timestamp"]
        assert isinstance(ts, datetime)
        assert ts.tzinfo is not None
        assert ts.tzinfo == timezone.utc
        assert ts.year == 2025
        assert ts.month == 1
        assert ts.day == 2

    def test_empty_dataframe_returns_no_records(self):
        """An empty DataFrame should return an empty list."""
        connector = YahooFinanceConnector()
        reverse_map = {"BRL=X": "USDBRL"}
        df = pd.DataFrame()

        records = connector._parse_dataframe(df, ["BRL=X"], reverse_map)
        assert records == []

    def test_none_dataframe_returns_no_records(self):
        """A None DataFrame should return an empty list."""
        connector = YahooFinanceConnector()
        reverse_map = {"BRL=X": "USDBRL"}

        records = connector._parse_dataframe(None, ["BRL=X"], reverse_map)
        assert records == []


# ---------------------------------------------------------------------------
# Async fetch test with mocked yfinance
# ---------------------------------------------------------------------------


class TestFetchAsync:
    """Tests for the async fetch() method with mocked yfinance."""

    @pytest.mark.asyncio
    async def test_fetch_calls_yfinance_download(self):
        """fetch() should call yf.download() via asyncio.to_thread()."""
        mock_df = _make_single_ticker_df()

        with patch("src.connectors.yahoo_finance.yf.download", return_value=mock_df):
            async with YahooFinanceConnector() as connector:
                records = await connector.fetch(
                    start_date=date(2025, 1, 1),
                    end_date=date(2025, 1, 5),
                    tickers=["USDBRL"],
                )

        assert len(records) == 2
        assert all(r["_ticker"] == "USDBRL" for r in records)

    @pytest.mark.asyncio
    async def test_fetch_handles_download_failure(self):
        """fetch() should handle yfinance exceptions gracefully."""
        with patch(
            "src.connectors.yahoo_finance.yf.download",
            side_effect=Exception("Network error"),
        ):
            async with YahooFinanceConnector() as connector:
                records = await connector.fetch(
                    start_date=date(2025, 1, 1),
                    end_date=date(2025, 1, 5),
                    tickers=["USDBRL"],
                )

        assert records == []

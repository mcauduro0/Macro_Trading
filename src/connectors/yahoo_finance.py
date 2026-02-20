"""Yahoo Finance connector -- daily OHLCV for 25+ global tickers.

Uses the yfinance library for data retrieval, wrapped with asyncio.to_thread()
to avoid blocking the event loop. Downloads in batches with random delays
to mitigate rate limiting.

Ticker universe covers:
- FX: USDBRL, EURUSD, USDJPY, GBPUSD, USDCHF, DXY, USDMXN, USDCNY, USDCLP
- Equity Indices: IBOVESPA, SP500, VIX, NASDAQ, RUSSELL2000
- Commodities: GOLD, OIL_WTI, OIL_BRENT, SOYBEAN, CORN, COPPER, IRON_ORE_PROXY
- ETFs: EWZ, TIP, TLT, HYG, EMB, LQD
"""

from __future__ import annotations

import asyncio
import math
import random
from datetime import date, datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
import structlog
import yfinance as yf
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.connectors.base import BaseConnector, ConnectorError, DataParsingError
from src.core.database import async_session_factory
from src.core.models.instruments import Instrument
from src.core.models.market_data import MarketData

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Ticker registry -- mirrors Fase0 guide Etapa 9 with extensions to 27
# ---------------------------------------------------------------------------
TICKERS: dict[str, str] = {
    # FX
    "USDBRL": "BRL=X",
    "EURUSD": "EURUSD=X",
    "USDJPY": "JPY=X",
    "GBPUSD": "GBPUSD=X",
    "USDCHF": "CHF=X",
    "DXY": "DX-Y.NYB",
    # Equity Indices
    "IBOVESPA": "^BVSP",
    "SP500": "^GSPC",
    "VIX": "^VIX",
    # Commodities
    "GOLD": "GC=F",
    "OIL_WTI": "CL=F",
    "OIL_BRENT": "BZ=F",
    "SOYBEAN": "ZS=F",
    "CORN": "ZC=F",
    "COPPER": "HG=F",
    "IRON_ORE_PROXY": "VALE3.SA",
    # ETFs (flow proxies)
    "EWZ": "EWZ",
    "TIP_ETF": "TIP",
    "TLT_ETF": "TLT",
    "HYG_ETF": "HYG",
    "EMB_ETF": "EMB",
    "LQD_ETF": "LQD",
    # Additional tickers to reach 27
    "USDMXN": "MXN=X",       # Mexico peso (EM peer)
    "USDCNY": "CNY=X",       # China yuan
    "USDCLP": "CLP=X",       # Chile peso (EM peer)
    "NASDAQ": "^IXIC",       # Nasdaq Composite
    "RUSSELL2000": "^RUT",   # Russell 2000 small cap
}

# Mapping from ticker prefix to reasonable instrument metadata defaults
_ASSET_CLASS_MAP: dict[str, tuple[str, str, str]] = {
    # ticker_prefix -> (asset_class, country, currency)
    "USDBRL": ("FX", "BR", "BRL"),
    "EURUSD": ("FX", "US", "USD"),
    "USDJPY": ("FX", "JP", "JPY"),
    "GBPUSD": ("FX", "GB", "GBP"),
    "USDCHF": ("FX", "CH", "CHF"),
    "DXY": ("FX", "US", "USD"),
    "USDMXN": ("FX", "MX", "MXN"),
    "USDCNY": ("FX", "CN", "CNY"),
    "USDCLP": ("FX", "CL", "CLP"),
    "IBOVESPA": ("EQUITY_INDEX", "BR", "BRL"),
    "SP500": ("EQUITY_INDEX", "US", "USD"),
    "VIX": ("VOLATILITY", "US", "USD"),
    "NASDAQ": ("EQUITY_INDEX", "US", "USD"),
    "RUSSELL2000": ("EQUITY_INDEX", "US", "USD"),
    "GOLD": ("COMMODITY", "US", "USD"),
    "OIL_WTI": ("COMMODITY", "US", "USD"),
    "OIL_BRENT": ("COMMODITY", "GB", "USD"),
    "SOYBEAN": ("COMMODITY", "US", "USD"),
    "CORN": ("COMMODITY", "US", "USD"),
    "COPPER": ("COMMODITY", "US", "USD"),
    "IRON_ORE_PROXY": ("EQUITY", "BR", "BRL"),
    "EWZ": ("ETF", "US", "USD"),
    "TIP_ETF": ("ETF", "US", "USD"),
    "TLT_ETF": ("ETF", "US", "USD"),
    "HYG_ETF": ("ETF", "US", "USD"),
    "EMB_ETF": ("ETF", "US", "USD"),
    "LQD_ETF": ("ETF", "US", "USD"),
}


class YahooFinanceConnector(BaseConnector):
    """Connector for Yahoo Finance daily OHLCV data via yfinance.

    Uses asyncio.to_thread() to wrap synchronous yfinance calls.
    Downloads in batches of BATCH_SIZE with random delays between batches.
    """

    SOURCE_NAME: str = "YAHOO_FINANCE"
    BASE_URL: str = "https://finance.yahoo.com"
    BATCH_SIZE: int = 5
    BATCH_DELAY_SECONDS: float = 2.0

    # Class-level reference to the ticker registry
    TICKERS: dict[str, str] = TICKERS

    def _batch_tickers(
        self, tickers: list[str] | None = None
    ) -> list[list[str]]:
        """Split ticker symbols into batches of BATCH_SIZE.

        Args:
            tickers: Optional list of Yahoo ticker symbols. If None, uses all
                     tickers from the TICKERS registry.

        Returns:
            List of batches, each a list of Yahoo ticker symbols.
        """
        yahoo_symbols = tickers or list(self.TICKERS.values())
        n_batches = math.ceil(len(yahoo_symbols) / self.BATCH_SIZE)
        return [
            yahoo_symbols[i * self.BATCH_SIZE : (i + 1) * self.BATCH_SIZE]
            for i in range(n_batches)
        ]

    async def _download_batch(
        self,
        yahoo_tickers: list[str],
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame | None:
        """Download OHLCV data for a batch of tickers via yfinance.

        Wraps the synchronous yf.download() call with asyncio.to_thread()
        to avoid blocking the event loop.

        Args:
            yahoo_tickers: List of Yahoo Finance ticker symbols.
            start_date: Inclusive start date.
            end_date: Inclusive end date.

        Returns:
            DataFrame with OHLCV data, or None on failure.
        """

        def _download() -> pd.DataFrame:
            return yf.download(
                tickers=yahoo_tickers,
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                group_by="ticker",
                auto_adjust=True,
                threads=False,
                progress=False,
            )

        try:
            df = await asyncio.to_thread(_download)
            return df
        except Exception as exc:
            self.log.warning(
                "batch_download_failed",
                tickers=yahoo_tickers,
                error=str(exc),
            )
            return None

    def _parse_dataframe(
        self,
        df: pd.DataFrame,
        yahoo_tickers: list[str],
        reverse_map: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Parse a yfinance DataFrame into a list of record dicts.

        Handles both single-ticker and multi-ticker DataFrames, which have
        different column structures (flat vs MultiIndex).

        Args:
            df: DataFrame returned by yf.download().
            yahoo_tickers: The Yahoo ticker symbols that were requested.
            reverse_map: Mapping from Yahoo symbol to internal ticker name.

        Returns:
            List of record dicts ready for store().
        """
        records: list[dict[str, Any]] = []

        if df is None or df.empty:
            return records

        is_multi_ticker = len(yahoo_tickers) > 1

        if is_multi_ticker and isinstance(df.columns, pd.MultiIndex):
            # Multi-ticker: columns are MultiIndex (Ticker, Price)
            available_tickers = df.columns.get_level_values(0).unique()
            for yahoo_sym in yahoo_tickers:
                if yahoo_sym not in available_tickers:
                    self.log.debug(
                        "ticker_not_in_response",
                        yahoo_symbol=yahoo_sym,
                    )
                    continue

                our_ticker = reverse_map.get(yahoo_sym)
                if our_ticker is None:
                    continue

                ticker_df = df[yahoo_sym]
                records.extend(
                    self._rows_to_records(ticker_df, our_ticker)
                )
        else:
            # Single ticker: flat columns (Open, High, Low, Close, Volume)
            yahoo_sym = yahoo_tickers[0]
            our_ticker = reverse_map.get(yahoo_sym)
            if our_ticker is not None:
                # For single ticker with MultiIndex, flatten
                if isinstance(df.columns, pd.MultiIndex):
                    df = df.droplevel("Ticker", axis=1)
                records.extend(self._rows_to_records(df, our_ticker))

        return records

    def _rows_to_records(
        self, df: pd.DataFrame, ticker: str
    ) -> list[dict[str, Any]]:
        """Convert DataFrame rows to record dicts for a single ticker.

        Args:
            df: DataFrame with OHLCV columns and DatetimeIndex.
            ticker: Our internal ticker name.

        Returns:
            List of record dicts.
        """
        records: list[dict[str, Any]] = []

        for idx, row in df.iterrows():
            ts = pd.Timestamp(idx)
            timestamp = datetime(
                ts.year, ts.month, ts.day, tzinfo=timezone.utc
            )

            def _clean(val: Any) -> float | None:
                """Convert NaN/inf to None, otherwise return float."""
                if val is None:
                    return None
                if isinstance(val, float) and (np.isnan(val) or np.isinf(val)):
                    return None
                try:
                    fval = float(val)
                    if np.isnan(fval) or np.isinf(fval):
                        return None
                    return fval
                except (TypeError, ValueError):
                    return None

            open_val = _clean(row.get("Open"))
            high_val = _clean(row.get("High"))
            low_val = _clean(row.get("Low"))
            close_val = _clean(row.get("Close"))
            volume_val = _clean(row.get("Volume"))

            records.append(
                {
                    "_ticker": ticker,
                    "timestamp": timestamp,
                    "frequency": "daily",
                    "open": open_val,
                    "high": high_val,
                    "low": low_val,
                    "close": close_val,
                    "volume": volume_val,
                    "adjusted_close": close_val,
                    "source": self.SOURCE_NAME,
                }
            )

        return records

    async def fetch(
        self,
        start_date: date,
        end_date: date,
        tickers: list[str] | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Fetch daily OHLCV data from Yahoo Finance.

        Args:
            start_date: Inclusive start date.
            end_date: Inclusive end date.
            tickers: Optional list of internal ticker names to fetch.
                     If None, fetches all tickers in the TICKERS registry.
            **kwargs: Additional arguments (unused).

        Returns:
            List of record dicts with _ticker, timestamp, OHLCV fields.
        """
        # Determine which tickers to fetch
        if tickers is not None:
            selected = {k: v for k, v in self.TICKERS.items() if k in tickers}
        else:
            selected = dict(self.TICKERS)

        if not selected:
            self.log.warning("no_tickers_selected")
            return []

        # Reverse map: Yahoo symbol -> our ticker name
        reverse_map: dict[str, str] = {v: k for k, v in selected.items()}
        yahoo_symbols = list(selected.values())

        batches = self._batch_tickers(yahoo_symbols)
        all_records: list[dict[str, Any]] = []

        for batch_num, batch in enumerate(batches, start=1):
            self.log.info(
                "batch_downloading",
                batch=batch_num,
                total_batches=len(batches),
                tickers=batch,
            )

            df = await self._download_batch(batch, start_date, end_date)
            if df is not None and not df.empty:
                records = self._parse_dataframe(df, batch, reverse_map)
                all_records.extend(records)
                self.log.info(
                    "batch_downloaded",
                    batch=batch_num,
                    records=len(records),
                )

            # Random delay between batches (skip after last batch)
            if batch_num < len(batches):
                delay = random.uniform(1.0, self.BATCH_DELAY_SECONDS)
                await asyncio.sleep(delay)

        self.log.info(
            "fetch_complete",
            total_records=len(all_records),
            tickers_requested=len(selected),
        )
        return all_records

    async def _ensure_instrument(
        self, ticker: str, yahoo_symbol: str
    ) -> int:
        """Ensure an Instrument row exists for the given ticker.

        Uses INSERT ... ON CONFLICT DO NOTHING on the ticker unique constraint,
        then returns the instrument id via SELECT.

        Args:
            ticker: Internal ticker name (e.g., "USDBRL").
            yahoo_symbol: Yahoo Finance symbol (e.g., "BRL=X").

        Returns:
            The instrument.id integer.

        Raises:
            ConnectorError: If the instrument cannot be found after upsert.
        """
        asset_class, country, currency = _ASSET_CLASS_MAP.get(
            ticker, ("OTHER", "US", "USD")
        )

        async with async_session_factory() as session:
            async with session.begin():
                stmt = pg_insert(Instrument).values(
                    ticker=ticker,
                    name=f"{ticker} ({yahoo_symbol})",
                    asset_class=asset_class,
                    country=country,
                    currency=currency,
                ).on_conflict_do_nothing(index_elements=["ticker"])
                await session.execute(stmt)

            # Fetch the instrument id (separate query after commit)
            result = await session.execute(
                select(Instrument.id).where(Instrument.ticker == ticker)
            )
            instrument_id = result.scalar_one_or_none()

        if instrument_id is None:
            raise ConnectorError(
                f"Failed to find instrument for ticker {ticker}"
            )
        return instrument_id

    async def store(self, records: list[dict[str, Any]]) -> int:
        """Persist fetched records to the market_data table.

        Groups records by _ticker, ensures each Instrument exists, replaces
        _ticker with instrument_id, then performs a bulk insert with
        ON CONFLICT DO NOTHING.

        Args:
            records: List of record dicts from fetch().

        Returns:
            Number of records inserted (excluding conflicts).
        """
        if not records:
            return 0

        # Group records by _ticker
        by_ticker: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            ticker = record["_ticker"]
            by_ticker.setdefault(ticker, []).append(record)

        # Resolve instrument IDs and prepare records for insert
        insert_records: list[dict[str, Any]] = []
        for ticker, ticker_records in by_ticker.items():
            yahoo_symbol = self.TICKERS.get(ticker, ticker)
            instrument_id = await self._ensure_instrument(ticker, yahoo_symbol)

            for record in ticker_records:
                rec = {k: v for k, v in record.items() if k != "_ticker"}
                rec["instrument_id"] = instrument_id
                insert_records.append(rec)

        inserted = await self._bulk_insert(
            MarketData, insert_records, "uq_market_data_natural_key"
        )
        self.log.info(
            "store_complete",
            total=len(insert_records),
            inserted=inserted,
        )
        return inserted

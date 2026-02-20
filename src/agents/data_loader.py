"""Point-in-time data loader for analytical agents.

PointInTimeDataLoader is the **single data access layer** used by all agents
for both live execution and backtesting.  Every method enforces point-in-time
(PIT) correctness so that backtests never look ahead:

- ``macro_series``: has ``release_time`` (NOT NULL) -- direct PIT filtering.
- ``curves``: no ``release_time`` -- uses ``curve_date <= as_of_date`` proxy
  (curves are published same day).
- ``market_data``: no ``release_time`` -- uses ``timestamp <= as_of_date``
  proxy (prices available in real time).
- ``flow_data``: ``release_time`` is nullable -- uses it when present,
  falls back to ``observation_date``.

All queries use **sync sessions** (psycopg2) because agent runs are batch
processes, not concurrent web requests.  Each method opens and closes its
own session to avoid long-lived connections.
"""

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

import pandas as pd
import structlog
from sqlalchemy import Date, and_, cast, func, select

from src.core.database import sync_session_factory
from src.core.models.curves import CurveData
from src.core.models.flow_data import FlowData
from src.core.models.instruments import Instrument
from src.core.models.macro_series import MacroSeries
from src.core.models.market_data import MarketData
from src.core.models.series_metadata import SeriesMetadata


class PointInTimeDataLoader:
    """Load data respecting point-in-time constraints for backtesting.

    All methods take an ``as_of_date`` parameter that defines the "present"
    for PIT filtering.  Only data that was publicly available on or before
    that date is returned.

    Usage::

        loader = PointInTimeDataLoader()
        df = loader.get_macro_series("BR_SELIC_TARGET", date(2024, 6, 15))
    """

    def __init__(self) -> None:
        self.log = structlog.get_logger().bind(component="pit_data_loader")

    # ------------------------------------------------------------------
    # macro_series (PIT via release_time)
    # ------------------------------------------------------------------
    def get_macro_series(
        self,
        series_code: str,
        as_of_date: date,
        lookback_days: int = 3650,
    ) -> pd.DataFrame:
        """Load macro series with point-in-time filtering on release_time.

        For revised series, only the latest revision available at
        ``as_of_date`` is returned per observation date.

        Args:
            series_code: Series code in series_metadata (e.g. ``"BR_SELIC_TARGET"``).
            as_of_date: Only data with ``release_time <= as_of_date`` is returned.
            lookback_days: How far back to load (default 10 years).

        Returns:
            DataFrame with columns ``["date", "value", "release_time",
            "revision_number"]`` indexed on ``date``.  Empty if no data.
        """
        start = as_of_date - timedelta(days=lookback_days)

        stmt = (
            select(
                MacroSeries.observation_date.label("date"),
                MacroSeries.value,
                MacroSeries.release_time,
                MacroSeries.revision_number,
            )
            .join(SeriesMetadata, MacroSeries.series_id == SeriesMetadata.id)
            .where(
                and_(
                    SeriesMetadata.series_code == series_code,
                    cast(MacroSeries.release_time, Date) <= as_of_date,
                    MacroSeries.observation_date >= start,
                )
            )
            .order_by(MacroSeries.observation_date, MacroSeries.revision_number.desc())
        )

        session = sync_session_factory()
        try:
            rows = session.execute(stmt).all()
        finally:
            session.close()

        if not rows:
            self.log.debug(
                "macro_series_loaded",
                series=series_code,
                rows=0,
                as_of=str(as_of_date),
            )
            return pd.DataFrame(columns=["date", "value", "release_time", "revision_number"])

        df = pd.DataFrame(rows, columns=["date", "value", "release_time", "revision_number"])

        # Keep only the highest revision per observation_date
        df = df.drop_duplicates(subset=["date"], keep="first")
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()

        self.log.debug(
            "macro_series_loaded",
            series=series_code,
            rows=len(df),
            as_of=str(as_of_date),
        )
        return df

    def get_latest_macro_value(
        self,
        series_code: str,
        as_of_date: date,
    ) -> Optional[float]:
        """Return the most recent value for a series available at as_of_date.

        Uses the same PIT filtering as ``get_macro_series`` but returns
        only the single latest value.

        Args:
            series_code: Series code in series_metadata.
            as_of_date: PIT reference date.

        Returns:
            Float value, or ``None`` if no data is available.
        """
        stmt = (
            select(MacroSeries.value)
            .join(SeriesMetadata, MacroSeries.series_id == SeriesMetadata.id)
            .where(
                and_(
                    SeriesMetadata.series_code == series_code,
                    cast(MacroSeries.release_time, Date) <= as_of_date,
                )
            )
            .order_by(MacroSeries.observation_date.desc(), MacroSeries.revision_number.desc())
            .limit(1)
        )

        session = sync_session_factory()
        try:
            row = session.execute(stmt).first()
        finally:
            session.close()

        if row is None:
            return None
        return float(row[0])

    # ------------------------------------------------------------------
    # curves (PIT via curve_date)
    # ------------------------------------------------------------------
    def get_curve(
        self,
        curve_id: str,
        as_of_date: date,
    ) -> dict[int, float]:
        """Load the most recent curve snapshot available at as_of_date.

        Curves have no ``release_time`` column; ``curve_date <= as_of_date``
        serves as the PIT proxy (curves are published same-day).

        Args:
            curve_id: Curve identifier (e.g. ``"DI_PRE"``, ``"UST_NOM"``).
            as_of_date: PIT reference date.

        Returns:
            ``{tenor_days: rate}`` dict.  Empty dict if no data.
        """
        # Step 1: Find the most recent curve_date for this curve
        max_date_stmt = (
            select(func.max(CurveData.curve_date))
            .where(
                and_(
                    CurveData.curve_id == curve_id,
                    CurveData.curve_date <= as_of_date,
                )
            )
        )

        session = sync_session_factory()
        try:
            found_date = session.execute(max_date_stmt).scalar()

            if found_date is None:
                self.log.debug(
                    "curve_loaded",
                    curve_id=curve_id,
                    tenors=0,
                    curve_date=None,
                    as_of=str(as_of_date),
                )
                return {}

            # Step 2: Load all tenor points for that date
            points_stmt = (
                select(CurveData.tenor_days, CurveData.rate)
                .where(
                    and_(
                        CurveData.curve_id == curve_id,
                        CurveData.curve_date == found_date,
                    )
                )
                .order_by(CurveData.tenor_days)
            )
            rows = session.execute(points_stmt).all()
        finally:
            session.close()

        result = {int(r[0]): float(r[1]) for r in rows}

        self.log.debug(
            "curve_loaded",
            curve_id=curve_id,
            tenors=len(result),
            curve_date=str(found_date),
            as_of=str(as_of_date),
        )
        return result

    def get_curve_history(
        self,
        curve_id: str,
        tenor_days: int,
        as_of_date: date,
        lookback_days: int = 756,
    ) -> pd.DataFrame:
        """Load the history of a single curve tenor point.

        Args:
            curve_id: Curve identifier.
            tenor_days: Target tenor in days (e.g. ``365`` for 1Y).
            as_of_date: PIT reference date.
            lookback_days: How far back to load (default ~3 years).

        Returns:
            DataFrame with columns ``["date", "rate"]`` indexed on ``date``.
        """
        start = as_of_date - timedelta(days=lookback_days)

        stmt = (
            select(
                CurveData.curve_date.label("date"),
                CurveData.rate,
            )
            .where(
                and_(
                    CurveData.curve_id == curve_id,
                    CurveData.tenor_days == tenor_days,
                    CurveData.curve_date <= as_of_date,
                    CurveData.curve_date >= start,
                )
            )
            .order_by(CurveData.curve_date)
        )

        session = sync_session_factory()
        try:
            rows = session.execute(stmt).all()
        finally:
            session.close()

        if not rows:
            return pd.DataFrame(columns=["date", "rate"])

        df = pd.DataFrame(rows, columns=["date", "rate"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        return df

    # ------------------------------------------------------------------
    # market_data (PIT via timestamp)
    # ------------------------------------------------------------------
    def get_market_data(
        self,
        ticker: str,
        as_of_date: date,
        lookback_days: int = 756,
    ) -> pd.DataFrame:
        """Load OHLCV market data for an instrument.

        Market data has no ``release_time``; ``timestamp <= as_of_date``
        serves as the PIT proxy (prices are available in real time).

        Args:
            ticker: Instrument ticker (e.g. ``"USDBRL"``, ``"IBOVESPA"``).
            as_of_date: PIT reference date.
            lookback_days: How far back to load (default ~3 years).

        Returns:
            DataFrame with columns ``["date", "open", "high", "low",
            "close", "volume", "adjusted_close"]`` indexed on ``date``.
        """
        start_dt = datetime.combine(
            as_of_date - timedelta(days=lookback_days),
            time.min,
            tzinfo=timezone.utc,
        )
        end_dt = datetime.combine(as_of_date, time.max, tzinfo=timezone.utc)

        stmt = (
            select(
                MarketData.timestamp.label("date"),
                MarketData.open,
                MarketData.high,
                MarketData.low,
                MarketData.close,
                MarketData.volume,
                MarketData.adjusted_close,
            )
            .join(Instrument, MarketData.instrument_id == Instrument.id)
            .where(
                and_(
                    Instrument.ticker == ticker,
                    MarketData.timestamp >= start_dt,
                    MarketData.timestamp <= end_dt,
                )
            )
            .order_by(MarketData.timestamp)
        )

        session = sync_session_factory()
        try:
            rows = session.execute(stmt).all()
        finally:
            session.close()

        if not rows:
            return pd.DataFrame(
                columns=["date", "open", "high", "low", "close", "volume", "adjusted_close"]
            )

        df = pd.DataFrame(
            rows,
            columns=["date", "open", "high", "low", "close", "volume", "adjusted_close"],
        )
        df["date"] = pd.to_datetime(df["date"], utc=True)
        df = df.set_index("date").sort_index()
        return df

    # ------------------------------------------------------------------
    # flow_data (PIT via release_time when available, else observation_date)
    # ------------------------------------------------------------------
    def get_flow_data(
        self,
        series_code: str,
        as_of_date: date,
        lookback_days: int = 365,
    ) -> pd.DataFrame:
        """Load flow data with PIT filtering.

        Uses ``release_time`` when available, falls back to
        ``observation_date`` for rows where ``release_time`` is NULL.

        Args:
            series_code: Series code in series_metadata.
            as_of_date: PIT reference date.
            lookback_days: How far back to load (default 1 year).

        Returns:
            DataFrame with columns ``["date", "value", "flow_type",
            "release_time"]`` indexed on ``date``.
        """
        start = as_of_date - timedelta(days=lookback_days)

        stmt = (
            select(
                FlowData.observation_date.label("date"),
                FlowData.value,
                FlowData.flow_type,
                FlowData.release_time,
            )
            .join(SeriesMetadata, FlowData.series_id == SeriesMetadata.id)
            .where(
                and_(
                    SeriesMetadata.series_code == series_code,
                    FlowData.observation_date >= start,
                    # PIT: use release_time if available, else observation_date
                    func.coalesce(
                        cast(FlowData.release_time, Date),
                        FlowData.observation_date,
                    )
                    <= as_of_date,
                )
            )
            .order_by(FlowData.observation_date)
        )

        session = sync_session_factory()
        try:
            rows = session.execute(stmt).all()
        finally:
            session.close()

        if not rows:
            return pd.DataFrame(columns=["date", "value", "flow_type", "release_time"])

        df = pd.DataFrame(rows, columns=["date", "value", "flow_type", "release_time"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        return df

    # ------------------------------------------------------------------
    # Focus expectations (convenience wrapper)
    # ------------------------------------------------------------------
    def get_focus_expectations(
        self,
        indicator: str,
        as_of_date: date,
        lookback_days: int = 365,
    ) -> pd.DataFrame:
        """Load Focus survey expectations for a given indicator.

        Convenience wrapper that calls ``get_macro_series`` with the
        standard Focus series code pattern.

        Args:
            indicator: Indicator name (e.g. ``"IPCA"``, ``"SELIC"``).
            as_of_date: PIT reference date.
            lookback_days: How far back to load.

        Returns:
            DataFrame from ``get_macro_series``.
        """
        series_code = f"BR_FOCUS_{indicator}_CY_MEDIAN"
        return self.get_macro_series(series_code, as_of_date, lookback_days)

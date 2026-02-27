"""Base connector infrastructure for all data source connectors.

Provides the BaseConnector abstract class with:
- Async HTTP client via httpx with connection pooling
- Retry with exponential backoff + jitter via tenacity
- Rate limiting via asyncio.Semaphore
- Structured logging via structlog
- Reusable _bulk_insert with ON CONFLICT DO NOTHING for idempotent ingestion

Exception hierarchy:
- ConnectorError: base for all connector errors
- RateLimitError: API rate limit hit (HTTP 429)
- DataParsingError: response data parse failure
- FetchError: HTTP fetch failure after retries exhausted
"""

import abc
import asyncio
import inspect
from datetime import date, timedelta
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from src.core.database import async_session_factory
from src.core.models.data_sources import DataSource


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------
class ConnectorError(Exception):
    """Base exception for all connector errors."""


class RateLimitError(ConnectorError):
    """Raised when the API returns a 429 rate limit response."""


class DataParsingError(ConnectorError):
    """Raised when response data cannot be parsed into the expected format."""


class FetchError(ConnectorError):
    """Raised when an HTTP request fails after all retry attempts."""


# ---------------------------------------------------------------------------
# BaseConnector ABC
# ---------------------------------------------------------------------------
class BaseConnector(abc.ABC):
    """Abstract base class for all data source connectors.

    Subclasses MUST override:
        SOURCE_NAME: str - identifier (e.g., "BCB_SGS", "FRED")
        BASE_URL: str - base API URL

    Subclasses MAY override:
        RATE_LIMIT_PER_SECOND: float - max concurrent requests (default 5.0)
        MAX_RETRIES: int - retry attempts on failure (default 3)
        TIMEOUT_SECONDS: float - HTTP timeout per request (default 30.0)

    Usage::

        async with MyConnector() as conn:
            count = await conn.run(start_date, end_date)
    """

    # Subclasses MUST override
    SOURCE_NAME: str = ""
    BASE_URL: str = ""

    # Subclasses MAY override
    RATE_LIMIT_PER_SECOND: float = 5.0
    MAX_RETRIES: int = 3
    TIMEOUT_SECONDS: float = 30.0

    # Metadata for _ensure_data_source (subclasses MAY override)
    AUTH_TYPE: str = "none"
    DEFAULT_LOCALE: str = "en-US"
    SOURCE_NOTES: str = ""

    # Date chunking (subclasses MAY override; used by _chunk_date_range)
    MAX_DATE_RANGE_YEARS: int = 10

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._semaphore = asyncio.Semaphore(int(self.RATE_LIMIT_PER_SECOND))
        self.log = structlog.get_logger().bind(connector=self.SOURCE_NAME)

    async def __aenter__(self) -> "BaseConnector":
        """Create and configure the httpx async client."""
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=httpx.Timeout(self.TIMEOUT_SECONDS),
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
            ),
        )
        return self

    async def __aexit__(self, *exc: Any) -> None:
        """Close the httpx async client if open."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Return the active httpx client.

        Raises:
            ConnectorError: If the client has not been initialized via __aenter__.
        """
        if self._client is None:
            raise ConnectorError(
                f"{self.SOURCE_NAME}: HTTP client not initialized. "
                "Use 'async with connector:' context manager."
            )
        return self._client

    async def _request(
        self, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        """Rate-limited HTTP request with retry.

        Acquires a semaphore slot before delegating to _request_with_retry
        to enforce the per-second concurrency limit.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: URL path (relative to BASE_URL) or absolute URL.
            **kwargs: Additional arguments passed to httpx.AsyncClient.request.

        Returns:
            The httpx.Response object.

        Raises:
            RateLimitError: If the API returns HTTP 429.
            FetchError: If all retry attempts are exhausted.
        """
        async with self._semaphore:
            return await self._request_with_retry(method, url, **kwargs)

    async def _request_with_retry(
        self, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        """Execute an HTTP request with tenacity retry logic.

        Uses AsyncRetrying so that instance attributes (MAX_RETRIES) are
        accessible at runtime rather than decoration time.

        Retries on: httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException.
        Backoff: exponential with jitter (initial=1s, max=30s, jitter=5s).
        """
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(
                (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException)
            ),
            stop=stop_after_attempt(self.MAX_RETRIES),
            wait=wait_exponential_jitter(initial=1, max=30, jitter=5),
            reraise=True,
        ):
            with attempt:
                self.log.debug(
                    "http_request",
                    method=method,
                    url=url,
                    attempt=attempt.retry_state.attempt_number,
                )
                response = self.client.request(method, url, **kwargs)
                if inspect.isawaitable(response):
                    response = await response
                if response.status_code == 429:
                    raise RateLimitError(
                        f"{self.SOURCE_NAME}: Rate limit exceeded (HTTP 429)"
                    )
                response.raise_for_status()
                return response

        # Should not be reached, but satisfies type checker
        raise FetchError(f"{self.SOURCE_NAME}: Request failed after retries")  # pragma: no cover

    # ---------------------------------------------------------------------------
    # Abstract interface
    # ---------------------------------------------------------------------------
    @abc.abstractmethod
    async def fetch(
        self, start_date: date, end_date: date, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Fetch data from the external source for the given date range.

        Args:
            start_date: Inclusive start date.
            end_date: Inclusive end date.
            **kwargs: Connector-specific parameters.

        Returns:
            List of record dicts ready for storage.
        """
        ...

    @abc.abstractmethod
    async def store(self, records: list[dict[str, Any]]) -> int:
        """Persist fetched records to the database.

        Args:
            records: List of record dicts from fetch().

        Returns:
            Number of records inserted (excluding conflicts).
        """
        ...

    # ---------------------------------------------------------------------------
    # Concrete methods
    # ---------------------------------------------------------------------------
    async def run(
        self, start_date: date, end_date: date, **kwargs: Any
    ) -> int:
        """Execute the full fetch-then-store pipeline.

        Args:
            start_date: Inclusive start date.
            end_date: Inclusive end date.
            **kwargs: Passed through to fetch().

        Returns:
            Number of records inserted.
        """
        records = await self.fetch(start_date, end_date, **kwargs)

        if not records:
            self.log.warning(
                "no_records_fetched",
                start_date=str(start_date),
                end_date=str(end_date),
            )
            return 0

        inserted = await self.store(records)
        self.log.info(
            "ingestion_complete",
            fetched=len(records),
            inserted=inserted,
            start_date=str(start_date),
            end_date=str(end_date),
        )
        return inserted

    def _chunk_date_range(
        self, start_date: date, end_date: date
    ) -> list[tuple[date, date]]:
        """Split a date range into chunks of MAX_DATE_RANGE_YEARS.

        Useful for APIs that reject queries spanning too many years.

        Args:
            start_date: Inclusive start date.
            end_date: Inclusive end date.

        Returns:
            List of (chunk_start, chunk_end) tuples covering the full range.
        """
        chunks: list[tuple[date, date]] = []
        chunk_start = start_date

        while chunk_start <= end_date:
            chunk_end_year = chunk_start.year + self.MAX_DATE_RANGE_YEARS
            try:
                chunk_end = date(
                    chunk_end_year, chunk_start.month, chunk_start.day
                ) - timedelta(days=1)
            except ValueError:
                # Handle leap year edge case (Feb 29)
                chunk_end = date(chunk_end_year, chunk_start.month, 28)

            if chunk_end >= end_date:
                chunk_end = end_date

            chunks.append((chunk_start, chunk_end))
            chunk_start = chunk_end + timedelta(days=1)

        return chunks

    async def _ensure_data_source(self) -> int:
        """Ensure a data_sources row exists for this connector. Returns its id.

        Uses SOURCE_NAME, BASE_URL, AUTH_TYPE, RATE_LIMIT_PER_SECOND,
        DEFAULT_LOCALE, and SOURCE_NOTES class attributes to populate the row.
        """
        async with async_session_factory() as session:
            async with session.begin():
                stmt = pg_insert(DataSource).values(
                    name=self.SOURCE_NAME,
                    base_url=self.BASE_URL,
                    auth_type=self.AUTH_TYPE,
                    rate_limit_per_minute=int(self.RATE_LIMIT_PER_SECOND * 60),
                    default_locale=self.DEFAULT_LOCALE,
                    notes=self.SOURCE_NOTES or self.SOURCE_NAME,
                    is_active=True,
                ).on_conflict_do_nothing(index_elements=["name"])
                await session.execute(stmt)

            result = await session.execute(
                select(DataSource.id).where(DataSource.name == self.SOURCE_NAME)
            )
            row = result.scalar_one()
            return row

    async def _bulk_insert(
        self,
        model_class: type,
        records: list[dict[str, Any]],
        constraint_name: str,
        batch_size: int = 2000,
    ) -> int:
        """Bulk insert records using INSERT ... ON CONFLICT DO NOTHING.

        Records are inserted in batches to avoid exceeding the asyncpg
        limit of 32767 query parameters.

        Args:
            model_class: SQLAlchemy ORM model class (the table).
            records: List of dicts whose keys match model columns.
            constraint_name: Name of the unique/primary key constraint
                for ON CONFLICT DO NOTHING.
            batch_size: Maximum number of records per INSERT statement.

        Returns:
            Number of rows actually inserted (excludes conflicts).
        """
        if not records:
            return 0

        total_inserted = 0
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            async with async_session_factory() as session:
                async with session.begin():
                    stmt = pg_insert(model_class).values(batch)
                    stmt = stmt.on_conflict_do_nothing(constraint=constraint_name)
                    result = await session.execute(stmt)
                    total_inserted += result.rowcount
        return total_inserted

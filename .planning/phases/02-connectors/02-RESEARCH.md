# Phase 2: Core Connectors - Research

**Researched:** 2026-02-19
**Domain:** Async data connectors, API integration, business day utilities, test infrastructure
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
No locked decisions -- all implementation decisions deferred to Claude's discretion.

### Claude's Discretion

All implementation decisions for Phase 2 are at Claude's discretion. The user trusts the builder's technical judgment for this connector phase. Key areas where Claude will decide:

**BaseConnector Pattern:**
- Abstract class design (methods, properties, lifecycle hooks)
- HTTP client management (httpx async, connection pooling)
- Retry and backoff strategy (tenacity vs custom)
- Rate limiting approach
- Structured logging integration (structlog)
- Error handling and exception hierarchy

**Connector Implementation:**
- Method signatures and return types for each connector
- API response parsing strategy per source
- Brazilian number format handling (1.234,56 -> 1234.56)
- Date format handling per API (YYYY-MM-DD, DD/MM/YYYY, MM-DD-YYYY)
- How connectors map API responses to ORM model instances
- Batch vs single-record insert strategy

**Data Integrity Utilities:**
- Business day calendar implementation (ANBIMA BR + NYSE US)
- Holiday data storage approach (hardcoded, file-based, or package)
- Tenor-to-days and tenor-to-date conversion logic

**Test Infrastructure:**
- pytest conftest structure and fixture design
- respx mock patterns for each API
- Sample data fixtures and test data strategy
- Integration vs unit test boundaries

### Deferred Ideas (OUT OF SCOPE)
None -- all connector-related work stays within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CONN-01 | Base connector abstract class with async HTTP (httpx), retry with backoff, rate limiting, structured logging | httpx 0.28.1 async client, tenacity 9.1.4 for retry/backoff, structlog contextvars for async logging, asyncio.Semaphore for rate limiting |
| CONN-02 | BCB SGS connector fetches ~50 Brazilian macro series with comma-decimal parsing | BCB SGS API at api.bcb.gov.br, JSON format returns `valor` as string with **period decimal** (not comma), dates in DD/MM/YYYY, 10-year max range per request |
| CONN-03 | FRED connector fetches ~50 US macro series with missing-value handling | FRED API at api.stlouisfed.org, `value` field returns `"."` for missing data, `realtime_start`/`realtime_end` for vintages, requires API key |
| CONN-10 | Yahoo Finance connector fetches daily OHLCV for 25+ tickers via yfinance | yfinance 1.2.0, synchronous library (run in executor for async context), rate limiting via delays between batches |
| CONN-11 | BCB PTAX connector fetches official FX fixing from OData API with MM-DD-YYYY date handling | PTAX OData API at olinda.bcb.gov.br, date params use MM-DD-YYYY format, response has cotacaoCompra/cotacaoVenda with period decimals |
| DATA-01 | All macro_series records store release_time for point-in-time correctness | MacroSeries model has release_time (TIMESTAMPTZ, NOT NULL), BCB/FRED provide release context, approximate with fetch timestamp when unavailable |
| DATA-02 | Revision tracking via revision_number field | MacroSeries model has revision_number (SmallInteger, default 0), FRED vintages via realtime_start/realtime_end, BCB SGS not revisable |
| DATA-03 | All database inserts use ON CONFLICT DO NOTHING for idempotent re-runs | SQLAlchemy `postgresql.insert().on_conflict_do_nothing(index_elements=[...])` targeting natural key unique constraints |
| DATA-04 | Business day calendar utilities for ANBIMA (BR) and NYSE (US) holidays | bizdays 1.0.2 with built-in ANBIMA calendar (2000-2078), exchange_calendars 4.11.3 with XNYS for NYSE |
| DATA-05 | Tenor-to-days and tenor-to-date conversion with business day conventions | bizdays for DU/252 counting, custom tenor parser for 1M/3M/6M/1Y/2Y labels, BUS/252 convention for Brazil |
| TEST-02 | Pytest test suite for connectors with respx HTTP mocking | respx 0.22.0 with respx_mock fixture, route patterns for each API endpoint, side effects for error scenarios |
| TEST-03 | Pytest conftest with database session fixture and sample date fixtures | async session fixture using async_session_factory, sample API response fixtures as JSON files, date fixtures for business day testing |
</phase_requirements>

## Summary

Phase 2 builds the data ingestion layer: a BaseConnector abstract class and four concrete connectors (BCB SGS, FRED, Yahoo Finance, BCB PTAX) that fetch external data and write it to the existing TimescaleDB schema. The connectors module also needs business day calendar utilities and a pytest test infrastructure with HTTP mocking.

The existing Phase 1 codebase provides all necessary ORM models (MacroSeries, MarketData, Instrument, SeriesMetadata, DataSource), async/sync database engines with session factories, a Pydantic settings singleton (with `fred_api_key`), and Redis. The connectors will use the async engine (asyncpg) for all database writes and httpx for all HTTP requests (except yfinance which wraps its own HTTP layer).

**Critical research finding:** The BCB SGS API JSON format returns `valor` as a string with **period decimal separator** (e.g., `"0.16"`, `"1.31"`), NOT comma-decimal format. The requirement for "comma-decimal parsing" (1.234,56 -> 1234.56) is still worth implementing as a utility since the CSV/SOAP endpoints and other BCB data sources DO use Brazilian formatting, and the series_metadata model already has a `decimal_separator` field. However, the primary JSON endpoint uses standard period notation. The connector should be defensive: parse based on the `decimal_separator` metadata field, defaulting to handling both formats.

**Primary recommendation:** Use httpx 0.28.1 as the async HTTP client, tenacity 9.1.4 for retry with exponential backoff + jitter, respx 0.22.0 for test mocking, bizdays 1.0.2 for ANBIMA business day calendar, and exchange_calendars 4.11.3 for NYSE calendar. Use yfinance 1.2.0 directly (it handles its own HTTP) but wrap calls with asyncio.to_thread() and add delays between batches for rate limiting.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.28.1 | Async HTTP client | Native async/await, connection pooling, timeout control, transport-level retry |
| tenacity | 9.1.4 | Retry with backoff | Production-grade retry: exponential backoff + jitter, async-native, exception filtering |
| structlog | >=24.4.0 | Structured logging | Already in pyproject.toml; contextvars for async-safe context binding |
| yfinance | 1.2.0 | Yahoo Finance data | Standard Python library for Yahoo Finance; handles auth/cookies/rate-limit headers |
| bizdays | 1.0.2 | Business day calendar | Built-in ANBIMA calendar (2000-2078), pure Python, no heavy dependencies |
| exchange_calendars | 4.11.3 | NYSE trading calendar | 50+ exchange calendars including XNYS (NYSE), actively maintained |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| respx | 0.22.0 | HTTPX mocking for tests | All connector unit tests that mock HTTP calls |
| pytest | >=8.0.0 | Test framework | Already in pyproject.toml dev dependencies |
| pytest-asyncio | >=0.24.0 | Async test support | Already in pyproject.toml; `asyncio_mode = "auto"` configured |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tenacity | backoff | backoff is simpler but tenacity has richer async support, more stop/wait strategies, and wider adoption |
| tenacity | httpx-retries | httpx-retries is transport-level only (no response code retry by default); tenacity works at application level |
| bizdays | anbima_calendar | anbima_calendar (0.1.1) is less mature; bizdays is established, covers 2000-2078, actively maintained |
| exchange_calendars | pandas_market_calendars | exchange_calendars is the successor to trading_calendars, lighter weight, no pandas dependency for calendar ops |
| yfinance | yahooquery | yahooquery has async support but yfinance 1.2.0 is more widely adopted and has better documentation |

**Installation:**
```bash
pip install httpx tenacity respx yfinance bizdays exchange_calendars
```

## Architecture Patterns

### Recommended Project Structure
```
src/
  connectors/
    __init__.py
    base.py              # BaseConnector ABC + exception hierarchy
    bcb_sgs.py           # BCB SGS connector
    fred.py              # FRED connector
    yahoo_finance.py     # Yahoo Finance connector
    bcb_ptax.py          # BCB PTAX connector
  core/
    (existing Phase 1 modules)
  utils/
    __init__.py
    calendars.py         # Business day calendar utilities (ANBIMA + NYSE)
    tenors.py            # Tenor-to-days and tenor-to-date conversion
    parsing.py           # Number format parsing (Brazilian comma-decimal, etc.)
tests/
  conftest.py            # Global fixtures: async session, sample dates
  connectors/
    __init__.py
    conftest.py          # Connector-specific fixtures: respx mocks, sample API data
    test_bcb_sgs.py
    test_fred.py
    test_yahoo_finance.py
    test_bcb_ptax.py
  utils/
    __init__.py
    test_calendars.py
    test_tenors.py
    test_parsing.py
  fixtures/
    bcb_sgs_sample.json   # Sample BCB SGS API response
    fred_sample.json      # Sample FRED API response
    ptax_sample.json      # Sample BCB PTAX API response
```

### Pattern 1: BaseConnector Abstract Class
**What:** Abstract base class establishing the connector lifecycle and shared infrastructure.
**When to use:** All data connectors inherit from this.
**Recommendation:**

```python
# src/connectors/base.py
import abc
from datetime import date
from typing import Any

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from src.core.config import settings
from src.core.database import async_session_factory

logger = structlog.get_logger()


class ConnectorError(Exception):
    """Base exception for all connector errors."""
    pass


class RateLimitError(ConnectorError):
    """Raised when API rate limit is hit."""
    pass


class DataParsingError(ConnectorError):
    """Raised when response data cannot be parsed."""
    pass


class BaseConnector(abc.ABC):
    """Abstract base for all data connectors.

    Provides:
    - Long-lived httpx.AsyncClient with connection pooling
    - Retry with exponential backoff + jitter (via tenacity)
    - Rate limiting via asyncio.Semaphore
    - Structured logging with source context
    - Idempotent bulk insert with ON CONFLICT DO NOTHING
    """

    # Subclasses MUST override these
    SOURCE_NAME: str  # e.g., "BCB_SGS", "FRED"
    BASE_URL: str

    # Subclasses MAY override these
    RATE_LIMIT_PER_SECOND: float = 5.0
    MAX_RETRIES: int = 3
    TIMEOUT_SECONDS: float = 30.0

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._semaphore = asyncio.Semaphore(int(self.RATE_LIMIT_PER_SECOND))
        self.log = logger.bind(connector=self.SOURCE_NAME)

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=httpx.Timeout(self.TIMEOUT_SECONDS),
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
            ),
        )
        return self

    async def __aexit__(self, *exc):
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise ConnectorError("Connector not entered as context manager")
        return self._client

    @abc.abstractmethod
    async def fetch(
        self,
        start_date: date,
        end_date: date,
        **kwargs,
    ) -> list[dict[str, Any]]:
        """Fetch data from the external API.
        Returns list of dicts ready for ORM insert."""
        ...

    @abc.abstractmethod
    async def store(self, records: list[dict[str, Any]]) -> int:
        """Store records using ON CONFLICT DO NOTHING.
        Returns count of new rows inserted."""
        ...

    async def run(
        self,
        start_date: date,
        end_date: date,
        **kwargs,
    ) -> int:
        """Full fetch-then-store pipeline."""
        records = await self.fetch(start_date, end_date, **kwargs)
        if not records:
            self.log.info("no_records_fetched", start=str(start_date), end=str(end_date))
            return 0
        count = await self.store(records)
        self.log.info(
            "ingestion_complete",
            fetched=len(records),
            inserted=count,
            start=str(start_date),
            end=str(end_date),
        )
        return count
```

### Pattern 2: Idempotent Bulk Insert with ON CONFLICT DO NOTHING
**What:** Core insert pattern using SQLAlchemy's PostgreSQL dialect for conflict-free upserts.
**When to use:** Every connector's `store()` method.
**Example:**

```python
# Source: SQLAlchemy 2.0 PostgreSQL Dialect Docs
from sqlalchemy.dialects.postgresql import insert as pg_insert
from src.core.database import async_session_factory
from src.core.models import MacroSeries

async def store(self, records: list[dict]) -> int:
    """Insert records with ON CONFLICT DO NOTHING on natural key."""
    if not records:
        return 0

    async with async_session_factory() as session:
        async with session.begin():
            stmt = pg_insert(MacroSeries).values(records)
            stmt = stmt.on_conflict_do_nothing(
                constraint="uq_macro_series_natural_key"
            )
            result = await session.execute(stmt)
            return result.rowcount
```

**Important:** Use `constraint="uq_macro_series_natural_key"` (the named constraint) rather than `index_elements=` for clarity and correctness with composite unique constraints.

### Pattern 3: Tenacity Retry with Rate Limiting
**What:** Combining tenacity's retry decorator with asyncio.Semaphore for rate limiting.
**When to use:** All HTTP calls to external APIs.
**Example:**

```python
import asyncio
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)
import httpx

class BaseConnector:
    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Rate-limited HTTP request with retry."""
        async with self._semaphore:
            return await self._request_with_retry(method, url, **kwargs)

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=30, jitter=5),
        reraise=True,
    )
    async def _request_with_retry(self, method: str, url: str, **kwargs) -> httpx.Response:
        response = await self.client.request(method, url, **kwargs)
        if response.status_code == 429:
            raise RateLimitError(f"Rate limited by {self.SOURCE_NAME}")
        response.raise_for_status()
        return response
```

### Pattern 4: Structlog Async Context Binding
**What:** Using structlog's contextvars for request-scoped logging in async connectors.
**When to use:** All connector operations for traceability.
**Example:**

```python
import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars

# Configure once at app startup
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,  # MUST be first
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),  # or JSONRenderer for production
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)

# In connector run():
async def run(self, start_date, end_date, **kwargs):
    bind_contextvars(
        connector=self.SOURCE_NAME,
        start_date=str(start_date),
        end_date=str(end_date),
    )
    try:
        records = await self.fetch(start_date, end_date, **kwargs)
        # ... structlog automatically includes context vars
    finally:
        clear_contextvars()
```

### Anti-Patterns to Avoid
- **Creating httpx.AsyncClient per request:** Kills connection pooling and TLS session reuse. Use one long-lived client via context manager.
- **Using `session.add_all()` with ON CONFLICT:** Causes flush errors with NULL identity keys when rows are skipped. Use Core `insert().values()` instead.
- **Blocking calls in async context:** yfinance is synchronous -- always wrap with `asyncio.to_thread()`.
- **Unbounded retry:** Always use `stop_after_attempt()` to prevent infinite retry loops.
- **Ignoring BCB SGS 10-year limit:** Since March 2025, BCB SGS rejects queries spanning >10 years. Split date ranges.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP retry with backoff | Custom retry loops with sleep() | tenacity 9.1.4 | Handles jitter, async sleep, exception filtering, stop conditions, call statistics |
| Brazilian business day calendar | Holiday list maintenance | bizdays 1.0.2 with ANBIMA | 948 holidays from 2000-2078, maintained by author of python-bcb |
| NYSE trading calendar | US holiday list | exchange_calendars 4.11.3 XNYS | Community-maintained, covers 2025-2026+, handles early closes |
| Yahoo Finance API client | Raw HTTP to Yahoo endpoints | yfinance 1.2.0 | Handles cookies, crumb tokens, rate limit headers, data cleaning |
| HTTPX test mocking | Custom mock transport | respx 0.22.0 | Route patterns, side effects, call statistics, pytest fixture |
| Number format parsing | Regex for comma/period | Standard approach with str.replace() | Simple enough that a utility function is correct, but must handle edge cases (thousands separator) |

**Key insight:** The BCB API ecosystem (SGS, PTAX, Focus) and the FRED API are stable, well-documented JSON APIs. The main complexity is not in the HTTP layer but in data integrity: correct date/number parsing, release_time tracking, revision storage, and idempotent writes. Libraries handle the former; careful ORM mapping handles the latter.

## Common Pitfalls

### Pitfall 1: BCB SGS 10-Year Query Limit
**What goes wrong:** Queries to BCB SGS API spanning more than 10 years return an error since March 2025.
**Why it happens:** BCB imposed volume limits on their API.
**How to avoid:** Split date ranges into 10-year (or smaller) windows. The connector should automatically chunk requests.
**Warning signs:** Empty responses or HTTP errors from api.bcb.gov.br.

### Pitfall 2: BCB SGS `valor` Field is String with Period Decimal
**What goes wrong:** The requirement mentions "comma-decimal parsing" but the BCB SGS JSON API actually returns `valor` as a string with **period** decimal separator (e.g., `"0.16"`, `"1.31"`).
**Why it happens:** The JSON format uses international notation, not Brazilian locale. The series_metadata model has a `decimal_separator` field that could be used to handle either format.
**How to avoid:** Implement a generic `parse_value(raw: str, decimal_sep: str = ".")` utility that handles both formats. Default to period for JSON API. Test with both comma and period inputs.
**Warning signs:** ValueError when converting strings to float.

### Pitfall 3: FRED Missing Values as "."
**What goes wrong:** FRED API returns `"."` (a single period) for missing observation values. Naive `float()` conversion raises ValueError.
**Why it happens:** FRED convention for null/missing data.
**How to avoid:** Always check `if value == "."` before parsing. Skip or store as NULL depending on business logic (for this project: skip, don't insert missing observations).
**Warning signs:** ValueError exceptions during FRED data parsing.

### Pitfall 4: BCB PTAX Date Format is MM-DD-YYYY
**What goes wrong:** PTAX OData API uses `MM-DD-YYYY` format for date parameters (e.g., `'01-15-2025'`), not DD/MM/YYYY or ISO format. Wrong format silently returns empty results.
**Why it happens:** The OData endpoint uses a non-standard American date format unlike other BCB endpoints.
**How to avoid:** Use `date.strftime("%m-%d-%Y")` when building PTAX query URLs. Add a test that verifies the date format produces correct API responses.
**Warning signs:** Empty `"value": []` arrays in PTAX responses.

### Pitfall 5: yfinance Rate Limiting and Blocking
**What goes wrong:** Yahoo Finance aggressively rate-limits requests, returning 429 errors. Can lead to temporary IP bans.
**Why it happens:** yfinance scrapes Yahoo Finance endpoints; Yahoo treats rapid automated access as abuse.
**How to avoid:** Batch tickers using `yf.download(tickers=[...])` for bulk requests. Add random delays (1-3 seconds) between batches. Limit concurrent requests. Use yfinance's built-in `YfRateLimitError` exception handling.
**Warning signs:** `YfRateLimitError` or 429 HTTP status codes.

### Pitfall 6: SQLAlchemy Async + session.add_all() with Conflicts
**What goes wrong:** Using `session.add_all()` with ON CONFLICT DO NOTHING causes flush errors because SQLAlchemy cannot determine the identity of skipped rows.
**Why it happens:** The ORM unit-of-work expects all added objects to receive primary keys on flush, but skipped rows get no PKs.
**How to avoid:** Use Core `insert().values(list_of_dicts).on_conflict_do_nothing()` instead of ORM add_all(). Execute via `session.execute(stmt)`.
**Warning signs:** IntegrityError or NULL primary key errors after insert.

### Pitfall 7: Forgetting release_time for Point-in-Time Correctness
**What goes wrong:** Macro series observations are inserted without meaningful release_time, making point-in-time queries useless.
**Why it happens:** Not all APIs provide explicit publication timestamps.
**How to avoid:** For FRED: use `realtime_start` from the API response. For BCB SGS: use `datetime.now(tz=ZoneInfo("America/Sao_Paulo"))` as approximate release time (data becomes available when we fetch it). Document the approximation. For PTAX: use `dataHoraCotacao` from the response.
**Warning signs:** All release_time values being identical across different observation dates.

### Pitfall 8: FRED Revision Tracking with realtime_start/realtime_end
**What goes wrong:** Fetching FRED data without specifying real-time periods returns only the latest vintage, losing revision history.
**Why it happens:** Default FRED API behavior returns "FRED mode" (today's view), not "ALFRED mode" (historical vintages).
**How to avoid:** For revisable series (like GDP, NFP), use `realtime_start` and `realtime_end` parameters to fetch vintages. Store each vintage as a separate row with incrementing `revision_number`. For non-revisable series (like interest rates), default behavior is fine.
**Warning signs:** Only one row per observation date for series known to be revised (e.g., GDP).

## Code Examples

Verified patterns from official sources:

### BCB SGS Connector - Fetch and Parse
```python
# Source: BCB Open Data Portal API documentation
# URL: https://dadosabertos.bcb.gov.br/

import httpx
from datetime import date, datetime
from zoneinfo import ZoneInfo

BCB_SGS_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"

async def fetch_bcb_sgs(
    client: httpx.AsyncClient,
    series_code: int,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Fetch BCB SGS series data.

    BCB SGS JSON response format:
    [{"data": "01/01/2025", "valor": "0.16"}, ...]

    - "data" is DD/MM/YYYY format
    - "valor" is a string with PERIOD decimal (NOT comma)
    - Since March 2025: max 10-year span per request
    """
    url = BCB_SGS_URL.format(code=series_code)
    params = {
        "formato": "json",
        "dataInicial": start_date.strftime("%d/%m/%Y"),
        "dataFinal": end_date.strftime("%d/%m/%Y"),
    }
    response = await client.get(url, params=params)
    response.raise_for_status()
    raw_data = response.json()

    records = []
    for item in raw_data:
        # Parse DD/MM/YYYY date
        obs_date = datetime.strptime(item["data"], "%d/%m/%Y").date()
        # Parse value -- BCB SGS JSON uses period decimal
        raw_value = item["valor"]
        if not raw_value or raw_value.strip() == "":
            continue  # Skip missing values
        value = float(raw_value)

        records.append({
            "observation_date": obs_date,
            "value": value,
            "release_time": datetime.now(tz=ZoneInfo("America/Sao_Paulo")),
            "revision_number": 0,
            "source": "BCB_SGS",
        })

    return records
```

### FRED Connector - Fetch with Vintage Support
```python
# Source: FRED API documentation
# URL: https://fred.stlouisfed.org/docs/api/fred/series_observations.html

FRED_BASE_URL = "https://api.stlouisfed.org/fred"

async def fetch_fred_observations(
    client: httpx.AsyncClient,
    series_id: str,
    api_key: str,
    start_date: date,
    end_date: date,
    realtime_start: date | None = None,
    realtime_end: date | None = None,
) -> list[dict]:
    """Fetch FRED series observations.

    FRED JSON response format:
    {"observations": [
        {"realtime_start": "2025-01-01", "realtime_end": "2025-01-01",
         "date": "2024-01-01", "value": "21427.2"},
        ...
    ]}

    - "value" is a string; missing values are "." (a single period)
    - "date" is YYYY-MM-DD
    - realtime_start/end control vintage access (ALFRED mode)
    """
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start_date.strftime("%Y-%m-%d"),
        "observation_end": end_date.strftime("%Y-%m-%d"),
    }
    if realtime_start:
        params["realtime_start"] = realtime_start.strftime("%Y-%m-%d")
    if realtime_end:
        params["realtime_end"] = realtime_end.strftime("%Y-%m-%d")

    response = await client.get(f"{FRED_BASE_URL}/series/observations", params=params)
    response.raise_for_status()
    data = response.json()

    records = []
    for obs in data.get("observations", []):
        # Skip missing values (FRED uses "." for missing)
        if obs["value"] == ".":
            continue

        obs_date = datetime.strptime(obs["date"], "%Y-%m-%d").date()
        value = float(obs["value"])

        # Use realtime_start as release_time (when this vintage was known)
        release_time = datetime.strptime(
            obs["realtime_start"], "%Y-%m-%d"
        ).replace(tzinfo=ZoneInfo("America/New_York"))

        records.append({
            "observation_date": obs_date,
            "value": value,
            "release_time": release_time,
            "revision_number": 0,  # Increment for each vintage
            "source": "FRED",
        })

    return records
```

### BCB PTAX Connector - Fetch FX Fixing
```python
# Source: BCB Open Data Portal - PTAX OData API
# URL: https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/swagger-ui3

PTAX_BASE_URL = "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata"

async def fetch_ptax_period(
    client: httpx.AsyncClient,
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Fetch PTAX dollar rates for a period.

    PTAX OData response format:
    {"value": [
        {"cotacaoCompra": 5.7036, "cotacaoVenda": 5.7042,
         "dataHoraCotacao": "2021-03-26 13:02:36.682"},
        ...
    ]}

    - Date params use MM-DD-YYYY format (NOT DD/MM or ISO)
    - cotacaoCompra/Venda are numbers (period decimal)
    - dataHoraCotacao is "YYYY-MM-DD HH:mm:ss.SSS"
    - Multiple quotes per day (opening, intermediate, closing)
    """
    url = (
        f"{PTAX_BASE_URL}/CotacaoDolarPeriodo("
        f"dataInicial=@di,dataFinalCotacao=@df)"
    )
    params = {
        "@di": f"'{start_date.strftime('%m-%d-%Y')}'",
        "@df": f"'{end_date.strftime('%m-%d-%Y')}'",
        "$format": "json",
    }
    response = await client.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    records = []
    for item in data.get("value", []):
        # Parse dataHoraCotacao (YYYY-MM-DD HH:mm:ss.SSS)
        dt_str = item["dataHoraCotacao"]
        release_time = datetime.strptime(
            dt_str, "%Y-%m-%d %H:%M:%S.%f"
        ).replace(tzinfo=ZoneInfo("America/Sao_Paulo"))

        records.append({
            "observation_date": release_time.date(),
            "buy_rate": item["cotacaoCompra"],
            "sell_rate": item["cotacaoVenda"],
            "release_time": release_time,
            "source": "BCB_PTAX",
        })

    return records
```

### Yahoo Finance Connector - Async Wrapper
```python
# Source: yfinance documentation
# URL: https://ranaroussi.github.io/yfinance/

import asyncio
import yfinance as yf
from datetime import date

async def fetch_yahoo_ohlcv(
    tickers: list[str],
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Fetch Yahoo Finance OHLCV data.

    yfinance is synchronous -- wrap in asyncio.to_thread().
    Use yf.download() for bulk fetching (fewer HTTP requests).
    """
    def _download():
        df = yf.download(
            tickers=tickers,
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            group_by="ticker",
            auto_adjust=True,  # Use adjusted prices
            threads=False,  # Avoid threading issues in async context
        )
        return df

    df = await asyncio.to_thread(_download)
    # Transform DataFrame to list of dicts for ORM insert...
    return records
```

### Respx Test Mocking Pattern
```python
# Source: RESPX documentation
# URL: https://lundberg.github.io/respx/

import httpx
import pytest
import respx
from httpx import Response

@pytest.fixture
def bcb_sgs_mock():
    """Mock BCB SGS API responses."""
    with respx.mock(base_url="https://api.bcb.gov.br") as mock:
        # Mock IPCA series (code 433)
        mock.get(
            url__startswith="/dados/serie/bcdata.sgs.433/dados",
        ).mock(return_value=Response(
            200,
            json=[
                {"data": "01/01/2025", "valor": "0.16"},
                {"data": "01/02/2025", "valor": "1.31"},
            ],
        ))
        yield mock


@pytest.mark.asyncio
async def test_bcb_sgs_fetch(bcb_sgs_mock):
    """Test BCB SGS connector parses response correctly."""
    async with httpx.AsyncClient(base_url="https://api.bcb.gov.br") as client:
        # ... test connector logic
        pass
    assert bcb_sgs_mock.calls.call_count == 1
```

### Idempotent Insert Pattern
```python
# Source: SQLAlchemy 2.0 PostgreSQL Dialect Documentation
# URL: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html

from sqlalchemy.dialects.postgresql import insert as pg_insert
from src.core.database import async_session_factory
from src.core.models import MacroSeries

async def store_macro_observations(records: list[dict]) -> int:
    """Insert macro series observations idempotently.

    Uses ON CONFLICT DO NOTHING on the natural key
    (series_id, observation_date, revision_number).
    Returns count of newly inserted rows.
    """
    if not records:
        return 0

    async with async_session_factory() as session:
        async with session.begin():
            stmt = pg_insert(MacroSeries).values(records)
            stmt = stmt.on_conflict_do_nothing(
                constraint="uq_macro_series_natural_key"
            )
            result = await session.execute(stmt)
            return result.rowcount
```

### Business Day Calendar Utilities
```python
# Source: bizdays documentation + exchange_calendars documentation
# bizdays: https://wilsonfreitas.github.io/python-bizdays/
# exchange_calendars: https://github.com/gerrymanoim/exchange_calendars

from bizdays import Calendar
import exchange_calendars as xcals
from datetime import date

# Load ANBIMA calendar (covers 2000-01-01 to 2078-12-25)
anbima_cal = Calendar.load("ANBIMA")

# Load NYSE calendar
nyse_cal = xcals.get_calendar("XNYS")

def is_business_day_br(d: date) -> bool:
    """Check if date is a Brazilian business day (ANBIMA)."""
    return anbima_cal.isbizday(d)

def count_business_days_br(start: date, end: date) -> int:
    """Count business days between two dates (ANBIMA, exclusive of start)."""
    return anbima_cal.bizdays(start, end)

def is_business_day_us(d: date) -> bool:
    """Check if date is a US business day (NYSE)."""
    return nyse_cal.is_session(d.isoformat())

def add_business_days_br(d: date, n: int) -> date:
    """Add n business days to a date using ANBIMA calendar."""
    return anbima_cal.offset(d, n)
```

### Tenor Conversion Utility
```python
# Tenor parsing and conversion for fixed income conventions

import re
from datetime import date
from bizdays import Calendar

TENOR_PATTERN = re.compile(r"^(\d+)([DWMY])$", re.IGNORECASE)

MONTH_DAYS = {
    "D": 1,
    "W": 7,
    "M": 30,     # Approximate
    "Y": 365,    # Approximate
}

def parse_tenor(tenor: str) -> tuple[int, str]:
    """Parse tenor string like '3M', '1Y', '21D' into (count, unit)."""
    match = TENOR_PATTERN.match(tenor.upper())
    if not match:
        raise ValueError(f"Invalid tenor format: {tenor}")
    return int(match.group(1)), match.group(2)

def tenor_to_calendar_days(tenor: str) -> int:
    """Convert tenor to approximate calendar days."""
    count, unit = parse_tenor(tenor)
    return count * MONTH_DAYS[unit]

def tenor_to_date(
    tenor: str,
    reference_date: date,
    calendar: Calendar | None = None,
) -> date:
    """Convert tenor to target date from reference_date.

    If calendar provided, adjusts to next business day (Following convention).
    """
    from dateutil.relativedelta import relativedelta

    count, unit = parse_tenor(tenor)

    if unit == "D":
        if calendar:
            return calendar.offset(reference_date, count)
        target = reference_date + timedelta(days=count)
    elif unit == "W":
        target = reference_date + timedelta(weeks=count)
    elif unit == "M":
        target = reference_date + relativedelta(months=count)
    elif unit == "Y":
        target = reference_date + relativedelta(years=count)

    if calendar and not calendar.isbizday(target):
        target = calendar.following(target)

    return target

def tenor_to_business_days(
    tenor: str,
    reference_date: date,
    calendar: Calendar,
) -> int:
    """Convert tenor to business days (DU/252 convention).

    Standard for Brazilian fixed income: count business days
    from reference_date to tenor maturity.
    """
    target = tenor_to_date(tenor, reference_date, calendar)
    return calendar.bizdays(reference_date, target)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| requests + custom retry | httpx + tenacity | httpx 0.20+ (2022) | Native async, connection pooling, better timeout control |
| BCB SGS unlimited queries | BCB SGS 10-year max per request | March 2025 | Must chunk date ranges for backfill |
| yfinance 0.2.x | yfinance 1.2.0 | December 2025 | New Calendars module, rate limit error handling, `auto_adjust` warning |
| FRED manual HTTP | FRED API unchanged | Stable | JSON response format consistent for years |
| trading_calendars (Quantopian) | exchange_calendars 4.x | 2021 fork | Community-maintained, more exchanges, regular holiday updates |
| Custom holiday lists | bizdays with ANBIMA calendar | bizdays 1.0 (2024) | Pre-loaded 948 holidays from 2000-2078, no maintenance needed |

**Deprecated/outdated:**
- **trading_calendars:** Replaced by exchange_calendars (2021 fork). Do not use.
- **requests library for async:** Use httpx instead. requests has no native async support.
- **yfinance < 1.0:** Missing rate limit error handling (YfRateLimitError), deprecation warnings for `auto_adjust`.
- **BCB SGS queries without date filters:** No longer supported as of March 2025.

## Open Questions

1. **BCB SGS comma-decimal vs period-decimal discrepancy**
   - What we know: The JSON API returns period-decimal (e.g., `"0.16"`). The requirement mentions "comma-decimal parsing (1.234,56 -> 1234.56)."
   - What's unclear: Whether some BCB SGS series return comma-decimal in JSON, or if this requirement only applies to CSV/other formats.
   - Recommendation: Implement a `parse_numeric_value(raw: str, decimal_sep: str)` utility that handles both. Use the `decimal_separator` field from `series_metadata` to drive parsing. Default to period for JSON API but keep comma handling as a safety net. Test both.

2. **FRED revision tracking granularity**
   - What we know: FRED provides `realtime_start`/`realtime_end` per observation and a `vintagedates` endpoint. The MacroSeries model has `revision_number` (SmallInteger).
   - What's unclear: How many vintages to store for each revisable series (GDP, NFP). Storing all vintages could mean many rows per observation date.
   - Recommendation: For Phase 2 (proving the pattern), fetch only the latest vintage (default FRED mode) and store with `revision_number=0`. Add a `fetch_vintages()` method that can be called for specific series in Phase 4 backfill. This avoids premature complexity while proving the revision storage pattern.

3. **yfinance thread safety in async context**
   - What we know: yfinance is synchronous and internally uses requests. Wrapping in `asyncio.to_thread()` moves execution to a thread pool.
   - What's unclear: Whether yfinance's internal state (cookies, session) is thread-safe for concurrent `to_thread()` calls.
   - Recommendation: Use `threads=False` in `yf.download()` and serialize yfinance calls (don't run multiple `to_thread()` concurrently). Process tickers in batches with delays.

4. **PTAX multiple quotes per day**
   - What we know: PTAX API returns 5 quotes per day (opening, 3 intermediate, closing). The closing PTAX rate is the official fixing.
   - What's unclear: Which quote to store, or whether to store all.
   - Recommendation: Filter for the closing bulletin (`tipoBoletim = "Fechamento"`) which is the official PTAX rate used in settlements.

## Sources

### Primary (HIGH confidence)
- BCB SGS API documentation - https://dadosabertos.bcb.gov.br/ (endpoint format, date parameters, 10-year limit)
- BCB PTAX OData API documentation - https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/swagger-ui3 (endpoint format, MM-DD-YYYY dates)
- FRED API series/observations - https://fred.stlouisfed.org/docs/api/fred/series_observations.html (response format, missing values, real-time periods)
- FRED Real-Time Periods - https://fred.stlouisfed.org/docs/api/fred/realtime_period.html (vintage/revision tracking)
- SQLAlchemy 2.0 PostgreSQL Dialect - https://docs.sqlalchemy.org/en/20/dialects/postgresql.html (insert on_conflict_do_nothing)
- SQLAlchemy 2.0 ORM DML - https://docs.sqlalchemy.org/en/20/orm/queryguide/dml.html (bulk insert patterns)
- httpx documentation - https://www.python-httpx.org/ (async client, transports, timeouts)
- structlog contextvars - https://www.structlog.org/en/stable/contextvars.html (async-safe context binding)
- tenacity PyPI - https://pypi.org/project/tenacity/ (version 9.1.4, API reference)
- respx documentation - https://lundberg.github.io/respx/ (mocking patterns, pytest fixture)
- yfinance documentation - https://ranaroussi.github.io/yfinance/ (version 1.2.0, download function)
- bizdays documentation - https://wilsonfreitas.github.io/python-bizdays/ (ANBIMA calendar, 2000-2078)
- exchange_calendars PyPI - https://pypi.org/project/exchange_calendars/ (version 4.11.3, XNYS)

### Secondary (MEDIUM confidence)
- BCB SGS JSON `valor` field format verified via multiple sources (dadosabertos portal data browser, python-bcb library usage, live API examples in blog posts) - period decimal confirmed
- yfinance rate limiting discussed in GitHub issues #2125, #2422 and multiple blog posts
- SQLAlchemy async bulk insert patterns from GitHub discussions #6935, #7651

### Tertiary (LOW confidence)
- PTAX `tipoBoletim = "Fechamento"` filter for closing rate -- needs validation against actual API response to confirm field name and value

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries verified on PyPI with current versions, documentation checked
- Architecture: HIGH - patterns derived from official documentation and existing Phase 1 codebase conventions
- Pitfalls: HIGH - BCB 10-year limit confirmed via multiple sources; FRED missing values documented officially; yfinance rate limiting widely reported
- API response formats: MEDIUM - BCB SGS period-decimal verified via multiple secondary sources but could not make live API call to confirm directly
- PTAX closing rate filter: LOW - needs validation during implementation

**Research date:** 2026-02-19
**Valid until:** 2026-03-19 (30 days - stable APIs and libraries)

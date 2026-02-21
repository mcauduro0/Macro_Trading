"""Tests for BCB SGS connector.

Uses respx to mock BCB SGS API HTTP responses and verify:
- DD/MM/YYYY date parsing
- Period-decimal value parsing
- Empty/missing value handling
- 10-year date range chunking
- Series registry completeness
"""

from __future__ import annotations

from datetime import date

import httpx
import pytest
import respx

from src.connectors.bcb_sgs import BcbSgsConnector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def bcb_connector() -> BcbSgsConnector:
    """Create a BcbSgsConnector instance without entering the async context."""
    return BcbSgsConnector()


# ---------------------------------------------------------------------------
# Date parsing and value parsing tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fetch_series_parses_dates_and_values():
    """Verify BCB SGS connector correctly parses DD/MM/YYYY dates and period-decimal values."""
    mock_data = [
        {"data": "02/01/2025", "valor": "0.16"},
        {"data": "03/01/2025", "valor": "1.31"},
    ]

    with respx.mock(base_url="https://api.bcb.gov.br") as mock:
        mock.get("/dados/serie/bcdata.sgs.433/dados").respond(
            200, json=mock_data
        )

        async with BcbSgsConnector() as conn:
            records = await conn.fetch_series(
                series_code=433,
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 31),
            )

    assert len(records) == 2

    # First record: 02/01/2025 -> 2025-01-02, value 0.16
    assert records[0]["observation_date"] == date(2025, 1, 2)
    assert records[0]["value"] == pytest.approx(0.16)
    assert records[0]["revision_number"] == 0
    assert records[0]["source"] == "BCB_SGS"
    assert records[0]["release_time"] is not None

    # Second record: 03/01/2025 -> 2025-01-03, value 1.31
    assert records[1]["observation_date"] == date(2025, 1, 3)
    assert records[1]["value"] == pytest.approx(1.31)


@pytest.mark.asyncio
async def test_fetch_series_skips_empty_values():
    """Verify BCB SGS connector skips records with empty or dash values."""
    mock_data = [
        {"data": "01/01/2025", "valor": ""},
        {"data": "02/01/2025", "valor": "-"},
        {"data": "03/01/2025", "valor": "0.16"},
    ]

    with respx.mock(base_url="https://api.bcb.gov.br") as mock:
        mock.get("/dados/serie/bcdata.sgs.433/dados").respond(
            200, json=mock_data
        )

        async with BcbSgsConnector() as conn:
            records = await conn.fetch_series(
                series_code=433,
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 31),
            )

    # Only the third record (value "0.16") should be returned
    assert len(records) == 1
    assert records[0]["observation_date"] == date(2025, 1, 3)
    assert records[0]["value"] == pytest.approx(0.16)


# ---------------------------------------------------------------------------
# Date chunking tests
# ---------------------------------------------------------------------------
def test_date_chunking_splits_long_ranges(bcb_connector):
    """Verify date ranges > 10 years are split into multiple chunks."""
    chunks = bcb_connector._chunk_date_range(
        date(2010, 1, 1), date(2025, 12, 31)
    )

    # 16-year range should produce 2 chunks
    assert len(chunks) == 2

    # First chunk: 2010-01-01 to ~2019-12-31
    assert chunks[0][0] == date(2010, 1, 1)
    assert chunks[0][1].year == 2019

    # Second chunk: starts after first chunk ends, goes to 2025-12-31
    assert chunks[1][1] == date(2025, 12, 31)


def test_date_chunking_short_range_no_split(bcb_connector):
    """Verify date ranges <= 10 years return a single chunk."""
    chunks = bcb_connector._chunk_date_range(
        date(2020, 1, 1), date(2025, 12, 31)
    )

    assert len(chunks) == 1
    assert chunks[0] == (date(2020, 1, 1), date(2025, 12, 31))


def test_date_chunking_exact_10_years(bcb_connector):
    """Verify date range of exactly 10 years returns a single chunk."""
    chunks = bcb_connector._chunk_date_range(
        date(2015, 1, 1), date(2024, 12, 31)
    )

    assert len(chunks) == 1
    assert chunks[0] == (date(2015, 1, 1), date(2024, 12, 31))


# ---------------------------------------------------------------------------
# Series registry tests
# ---------------------------------------------------------------------------
def test_series_registry_has_expected_count():
    """Verify the series registry contains at least 48 series (~50 from Fase0 guide)."""
    assert len(BcbSgsConnector.SERIES_REGISTRY) >= 48


def test_series_registry_has_key_series():
    """Verify the registry includes critical series for each category."""
    registry = BcbSgsConnector.SERIES_REGISTRY

    # Inflation
    assert "BR_IPCA_MOM" in registry
    assert registry["BR_IPCA_MOM"] == 433

    # Monetary
    assert "BR_SELIC_TARGET" in registry
    assert registry["BR_SELIC_TARGET"] == 432

    # External
    assert "BR_RESERVES" in registry
    assert registry["BR_RESERVES"] == 13621

    # Fiscal
    assert "BR_GROSS_DEBT_GDP" in registry
    assert registry["BR_GROSS_DEBT_GDP"] == 13762

    # Activity
    assert "BR_GDP_QOQ" in registry
    assert registry["BR_GDP_QOQ"] == 22099


def test_series_registry_values_are_integers():
    """Verify all BCB SGS codes are positive integers."""
    for key, code in BcbSgsConnector.SERIES_REGISTRY.items():
        assert isinstance(code, int), f"{key} code is not int: {type(code)}"
        assert code > 0, f"{key} code is not positive: {code}"


# ---------------------------------------------------------------------------
# Connector constants tests
# ---------------------------------------------------------------------------
def test_connector_constants():
    """Verify connector class-level constants are set correctly."""
    assert BcbSgsConnector.SOURCE_NAME == "BCB_SGS"
    assert BcbSgsConnector.BASE_URL == "https://api.bcb.gov.br"
    assert BcbSgsConnector.RATE_LIMIT_PER_SECOND == 3.0
    assert BcbSgsConnector.MAX_DATE_RANGE_YEARS == 10


@pytest.mark.asyncio
async def test_fetch_series_handles_non_list_response():
    """Verify connector handles unexpected non-list API responses gracefully."""
    with respx.mock(base_url="https://api.bcb.gov.br") as mock:
        # BCB sometimes returns an error object instead of a list
        mock.get("/dados/serie/bcdata.sgs.433/dados").respond(
            200, json={"error": "series not found"}
        )

        async with BcbSgsConnector() as conn:
            records = await conn.fetch_series(
                series_code=433,
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 31),
            )

    assert len(records) == 0

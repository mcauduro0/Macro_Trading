"""Tests for BCB FX Flow connector.

Uses respx to mock BCB SGS API HTTP responses and verify:
- DD/MM/YYYY date parsing
- Period-decimal value parsing (including negative values)
- Empty/missing value handling
- Flow type mapping per series
- 10-year date range chunking
- Series registry completeness
"""

from __future__ import annotations

from datetime import date

import pytest
import respx

from src.connectors.bcb_fx_flow import BcbFxFlowConnector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def connector() -> BcbFxFlowConnector:
    """Create a BcbFxFlowConnector instance without entering the async context."""
    return BcbFxFlowConnector()


# ---------------------------------------------------------------------------
# Fetch parsing tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fetch_parses_dates_and_values():
    """Verify connector correctly parses DD/MM/YYYY dates and period-decimal values."""
    mock_data = [
        {"data": "06/01/2025", "valor": "1234.5"},
        {"data": "07/01/2025", "valor": "-567.8"},
        {"data": "08/01/2025", "valor": "890.1"},
    ]

    with respx.mock(base_url="https://api.bcb.gov.br") as mock:
        mock.get("/dados/serie/bcdata.sgs.22704/dados").respond(200, json=mock_data)

        async with BcbFxFlowConnector() as conn:
            records = await conn._fetch_series(
                series_key="BR_FX_FLOW_COMMERCIAL",
                series_code=22704,
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 31),
            )

    assert len(records) == 3

    # First record: 06/01/2025 -> 2025-01-06, value 1234.5
    assert records[0]["observation_date"] == date(2025, 1, 6)
    assert records[0]["value"] == pytest.approx(1234.5)
    assert records[0]["flow_type"] == "FX_COMMERCIAL"
    assert records[0]["unit"] == "USD_MM"
    assert records[0]["_series_key"] == "BR_FX_FLOW_COMMERCIAL"
    assert records[0]["release_time"] is not None

    # Second record: negative value
    assert records[1]["observation_date"] == date(2025, 1, 7)
    assert records[1]["value"] == pytest.approx(-567.8)

    # Third record
    assert records[2]["observation_date"] == date(2025, 1, 8)
    assert records[2]["value"] == pytest.approx(890.1)


@pytest.mark.asyncio
async def test_fetch_with_empty_response():
    """Verify connector returns empty list for empty API response."""
    with respx.mock(base_url="https://api.bcb.gov.br") as mock:
        mock.get("/dados/serie/bcdata.sgs.22704/dados").respond(200, json=[])

        async with BcbFxFlowConnector() as conn:
            records = await conn._fetch_series(
                series_key="BR_FX_FLOW_COMMERCIAL",
                series_code=22704,
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 31),
            )

    assert len(records) == 0


@pytest.mark.asyncio
async def test_fetch_skips_invalid_entries():
    """Verify connector skips records with empty, dash, or invalid date values."""
    mock_data = [
        {"data": "06/01/2025", "valor": "1234.5"},
        {"data": "07/01/2025", "valor": ""},
        {"data": "08/01/2025", "valor": "-"},
        {"data": "invalid-date", "valor": "100.0"},
        {"data": "09/01/2025", "valor": "500.0"},
    ]

    with respx.mock(base_url="https://api.bcb.gov.br") as mock:
        mock.get("/dados/serie/bcdata.sgs.22705/dados").respond(200, json=mock_data)

        async with BcbFxFlowConnector() as conn:
            records = await conn._fetch_series(
                series_key="BR_FX_FLOW_FINANCIAL",
                series_code=22705,
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 31),
            )

    # Only records with valid date AND value should be returned
    assert len(records) == 2
    assert records[0]["observation_date"] == date(2025, 1, 6)
    assert records[0]["flow_type"] == "FX_FINANCIAL"
    assert records[1]["observation_date"] == date(2025, 1, 9)


@pytest.mark.asyncio
async def test_fetch_handles_non_list_response():
    """Verify connector handles unexpected non-list API responses gracefully."""
    with respx.mock(base_url="https://api.bcb.gov.br") as mock:
        mock.get("/dados/serie/bcdata.sgs.22706/dados").respond(
            200, json={"error": "series not found"}
        )

        async with BcbFxFlowConnector() as conn:
            records = await conn._fetch_series(
                series_key="BR_FX_FLOW_TOTAL",
                series_code=22706,
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 31),
            )

    assert len(records) == 0


# ---------------------------------------------------------------------------
# Flow type mapping tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_flow_type_mapping_commercial():
    """Verify BR_FX_FLOW_COMMERCIAL maps to FX_COMMERCIAL flow_type."""
    mock_data = [{"data": "06/01/2025", "valor": "100.0"}]

    with respx.mock(base_url="https://api.bcb.gov.br") as mock:
        mock.get("/dados/serie/bcdata.sgs.22704/dados").respond(200, json=mock_data)

        async with BcbFxFlowConnector() as conn:
            records = await conn._fetch_series(
                "BR_FX_FLOW_COMMERCIAL", 22704, date(2025, 1, 1), date(2025, 1, 31)
            )

    assert records[0]["flow_type"] == "FX_COMMERCIAL"


@pytest.mark.asyncio
async def test_flow_type_mapping_swap_stock():
    """Verify BR_BCB_SWAP_STOCK maps to BCB_SWAP_STOCK flow_type."""
    mock_data = [{"data": "06/01/2025", "valor": "75000.0"}]

    with respx.mock(base_url="https://api.bcb.gov.br") as mock:
        mock.get("/dados/serie/bcdata.sgs.12070/dados").respond(200, json=mock_data)

        async with BcbFxFlowConnector() as conn:
            records = await conn._fetch_series(
                "BR_BCB_SWAP_STOCK", 12070, date(2025, 1, 1), date(2025, 1, 31)
            )

    assert records[0]["flow_type"] == "BCB_SWAP_STOCK"


# ---------------------------------------------------------------------------
# Fetch all series tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fetch_all_series():
    """Verify fetch() iterates over all 4 series in the registry."""
    mock_data = [{"data": "06/01/2025", "valor": "100.0"}]

    with respx.mock(base_url="https://api.bcb.gov.br") as mock:
        mock.get("/dados/serie/bcdata.sgs.22704/dados").respond(200, json=mock_data)
        mock.get("/dados/serie/bcdata.sgs.22705/dados").respond(200, json=mock_data)
        mock.get("/dados/serie/bcdata.sgs.22706/dados").respond(200, json=mock_data)
        mock.get("/dados/serie/bcdata.sgs.12070/dados").respond(200, json=mock_data)

        async with BcbFxFlowConnector() as conn:
            records = await conn.fetch(date(2025, 1, 1), date(2025, 1, 31))

    # 4 series x 1 record each = 4 records
    assert len(records) == 4

    # Verify each record has a _series_key
    series_keys = {r["_series_key"] for r in records}
    assert series_keys == {
        "BR_FX_FLOW_COMMERCIAL",
        "BR_FX_FLOW_FINANCIAL",
        "BR_FX_FLOW_TOTAL",
        "BR_BCB_SWAP_STOCK",
    }


@pytest.mark.asyncio
async def test_fetch_subset_of_series():
    """Verify fetch() can fetch a subset of series via series_ids param."""
    mock_data = [{"data": "06/01/2025", "valor": "100.0"}]

    with respx.mock(base_url="https://api.bcb.gov.br") as mock:
        mock.get("/dados/serie/bcdata.sgs.22704/dados").respond(200, json=mock_data)

        async with BcbFxFlowConnector() as conn:
            records = await conn.fetch(
                date(2025, 1, 1),
                date(2025, 1, 31),
                series_ids=["BR_FX_FLOW_COMMERCIAL"],
            )

    assert len(records) == 1
    assert records[0]["_series_key"] == "BR_FX_FLOW_COMMERCIAL"


@pytest.mark.asyncio
async def test_fetch_skips_unknown_series_key():
    """Verify fetch() skips unknown series keys without error."""
    with respx.mock(base_url="https://api.bcb.gov.br"):
        async with BcbFxFlowConnector() as conn:
            records = await conn.fetch(
                date(2025, 1, 1),
                date(2025, 1, 31),
                series_ids=["NONEXISTENT_KEY"],
            )

    assert len(records) == 0


# ---------------------------------------------------------------------------
# Date chunking tests
# ---------------------------------------------------------------------------
def test_date_chunking_splits_long_ranges(connector):
    """Verify date ranges > 10 years are split into multiple chunks."""
    chunks = connector._chunk_date_range(date(2010, 1, 1), date(2025, 12, 31))

    # 16-year range should produce 2 chunks
    assert len(chunks) == 2
    assert chunks[0][0] == date(2010, 1, 1)
    assert chunks[0][1].year == 2019
    assert chunks[1][1] == date(2025, 12, 31)


def test_date_chunking_short_range_no_split(connector):
    """Verify date ranges <= 10 years return a single chunk."""
    chunks = connector._chunk_date_range(date(2020, 1, 1), date(2025, 12, 31))

    assert len(chunks) == 1
    assert chunks[0] == (date(2020, 1, 1), date(2025, 12, 31))


# ---------------------------------------------------------------------------
# Registry and constants tests
# ---------------------------------------------------------------------------
def test_series_registry_has_4_series():
    """Verify the series registry contains exactly 4 series."""
    assert len(BcbFxFlowConnector.SERIES_REGISTRY) == 4


def test_series_registry_keys():
    """Verify the registry includes the expected series keys."""
    registry = BcbFxFlowConnector.SERIES_REGISTRY
    assert "BR_FX_FLOW_COMMERCIAL" in registry
    assert registry["BR_FX_FLOW_COMMERCIAL"] == 22704
    assert "BR_FX_FLOW_FINANCIAL" in registry
    assert registry["BR_FX_FLOW_FINANCIAL"] == 22705
    assert "BR_FX_FLOW_TOTAL" in registry
    assert registry["BR_FX_FLOW_TOTAL"] == 22706
    assert "BR_BCB_SWAP_STOCK" in registry
    assert registry["BR_BCB_SWAP_STOCK"] == 12070


def test_flow_type_map_covers_all_series():
    """Verify every series key has a corresponding flow_type mapping."""
    for key in BcbFxFlowConnector.SERIES_REGISTRY:
        assert (
            key in BcbFxFlowConnector.FLOW_TYPE_MAP
        ), f"Missing FLOW_TYPE_MAP entry for {key}"


def test_connector_constants():
    """Verify connector class-level constants are set correctly."""
    assert BcbFxFlowConnector.SOURCE_NAME == "BCB_FX_FLOW"
    assert BcbFxFlowConnector.BASE_URL == "https://api.bcb.gov.br"
    assert BcbFxFlowConnector.RATE_LIMIT_PER_SECOND == 3.0

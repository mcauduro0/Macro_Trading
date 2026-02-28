"""Tests for STN Fiscal connector.

Uses respx to mock BCB SGS API HTTP responses and verify:
- DD/MM/YYYY date parsing
- Period-decimal value parsing (including negative values)
- Empty/missing value handling
- Fiscal metric and unit mapping per series
- 10-year date range chunking
- Series registry completeness
"""

from __future__ import annotations

from datetime import date

import pytest
import respx

from src.connectors.stn_fiscal import StnFiscalConnector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def connector() -> StnFiscalConnector:
    """Create a StnFiscalConnector instance without entering the async context."""
    return StnFiscalConnector()


# ---------------------------------------------------------------------------
# Fetch parsing tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fetch_parses_dates_and_values():
    """Verify connector correctly parses DD/MM/YYYY dates and period-decimal values."""
    mock_data = [
        {"data": "01/01/2025", "valor": "15432.7"},
        {"data": "01/02/2025", "valor": "-8765.4"},
        {"data": "01/03/2025", "valor": "73.2"},
    ]

    with respx.mock(base_url="https://api.bcb.gov.br") as mock:
        mock.get("/dados/serie/bcdata.sgs.5364/dados").respond(200, json=mock_data)

        async with StnFiscalConnector() as conn:
            records = await conn._fetch_series(
                series_key="BR_PRIMARY_BALANCE_MONTHLY",
                series_code=5364,
                fiscal_metric="PRIMARY_BALANCE",
                unit="BRL_MM",
                start_date=date(2025, 1, 1),
                end_date=date(2025, 3, 31),
            )

    assert len(records) == 3

    # First record: 01/01/2025 -> 2025-01-01, value 15432.7
    assert records[0]["observation_date"] == date(2025, 1, 1)
    assert records[0]["value"] == pytest.approx(15432.7)
    assert records[0]["fiscal_metric"] == "PRIMARY_BALANCE"
    assert records[0]["unit"] == "BRL_MM"
    assert records[0]["_series_key"] == "BR_PRIMARY_BALANCE_MONTHLY"
    assert records[0]["release_time"] is not None

    # Second record: negative value
    assert records[1]["observation_date"] == date(2025, 2, 1)
    assert records[1]["value"] == pytest.approx(-8765.4)

    # Third record
    assert records[2]["observation_date"] == date(2025, 3, 1)
    assert records[2]["value"] == pytest.approx(73.2)


@pytest.mark.asyncio
async def test_fetch_with_empty_response():
    """Verify connector returns empty list for empty API response."""
    with respx.mock(base_url="https://api.bcb.gov.br") as mock:
        mock.get("/dados/serie/bcdata.sgs.5364/dados").respond(200, json=[])

        async with StnFiscalConnector() as conn:
            records = await conn._fetch_series(
                series_key="BR_PRIMARY_BALANCE_MONTHLY",
                series_code=5364,
                fiscal_metric="PRIMARY_BALANCE",
                unit="BRL_MM",
                start_date=date(2025, 1, 1),
                end_date=date(2025, 3, 31),
            )

    assert len(records) == 0


@pytest.mark.asyncio
async def test_fetch_skips_invalid_entries():
    """Verify connector skips records with empty, dash, or invalid date values."""
    mock_data = [
        {"data": "01/01/2025", "valor": "15432.7"},
        {"data": "01/02/2025", "valor": ""},
        {"data": "01/03/2025", "valor": "-"},
        {"data": "bad-date", "valor": "100.0"},
        {"data": "01/04/2025", "valor": "500.0"},
    ]

    with respx.mock(base_url="https://api.bcb.gov.br") as mock:
        mock.get("/dados/serie/bcdata.sgs.13762/dados").respond(200, json=mock_data)

        async with StnFiscalConnector() as conn:
            records = await conn._fetch_series(
                series_key="BR_GROSS_DEBT_GDP",
                series_code=13762,
                fiscal_metric="GROSS_DEBT_GDP",
                unit="PERCENT",
                start_date=date(2025, 1, 1),
                end_date=date(2025, 6, 30),
            )

    # Only records with valid date AND value should be returned
    assert len(records) == 2
    assert records[0]["observation_date"] == date(2025, 1, 1)
    assert records[0]["fiscal_metric"] == "GROSS_DEBT_GDP"
    assert records[0]["unit"] == "PERCENT"
    assert records[1]["observation_date"] == date(2025, 4, 1)


@pytest.mark.asyncio
async def test_fetch_handles_non_list_response():
    """Verify connector handles unexpected non-list API responses gracefully."""
    with respx.mock(base_url="https://api.bcb.gov.br") as mock:
        mock.get("/dados/serie/bcdata.sgs.5364/dados").respond(
            200, json={"error": "series not found"}
        )

        async with StnFiscalConnector() as conn:
            records = await conn._fetch_series(
                series_key="BR_PRIMARY_BALANCE_MONTHLY",
                series_code=5364,
                fiscal_metric="PRIMARY_BALANCE",
                unit="BRL_MM",
                start_date=date(2025, 1, 1),
                end_date=date(2025, 3, 31),
            )

    assert len(records) == 0


# ---------------------------------------------------------------------------
# Fiscal metric and unit mapping tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fiscal_metric_mapping_primary_balance():
    """Verify BR_PRIMARY_BALANCE_MONTHLY maps to PRIMARY_BALANCE metric and BRL_MM unit."""
    mock_data = [{"data": "01/01/2025", "valor": "100.0"}]

    with respx.mock(base_url="https://api.bcb.gov.br") as mock:
        mock.get("/dados/serie/bcdata.sgs.5364/dados").respond(200, json=mock_data)

        async with StnFiscalConnector() as conn:
            records = await conn._fetch_series(
                "BR_PRIMARY_BALANCE_MONTHLY",
                5364,
                "PRIMARY_BALANCE",
                "BRL_MM",
                date(2025, 1, 1),
                date(2025, 1, 31),
            )

    assert records[0]["fiscal_metric"] == "PRIMARY_BALANCE"
    assert records[0]["unit"] == "BRL_MM"


@pytest.mark.asyncio
async def test_fiscal_metric_mapping_gross_debt():
    """Verify BR_GROSS_DEBT_GDP maps to GROSS_DEBT_GDP metric and PERCENT unit."""
    mock_data = [{"data": "01/01/2025", "valor": "73.5"}]

    with respx.mock(base_url="https://api.bcb.gov.br") as mock:
        mock.get("/dados/serie/bcdata.sgs.13762/dados").respond(200, json=mock_data)

        async with StnFiscalConnector() as conn:
            records = await conn._fetch_series(
                "BR_GROSS_DEBT_GDP",
                13762,
                "GROSS_DEBT_GDP",
                "PERCENT",
                date(2025, 1, 1),
                date(2025, 1, 31),
            )

    assert records[0]["fiscal_metric"] == "GROSS_DEBT_GDP"
    assert records[0]["unit"] == "PERCENT"


# ---------------------------------------------------------------------------
# Fetch all series tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fetch_all_series():
    """Verify fetch() iterates over all 6 series in the registry."""
    mock_data = [{"data": "01/01/2025", "valor": "100.0"}]

    with respx.mock(base_url="https://api.bcb.gov.br") as mock:
        mock.get("/dados/serie/bcdata.sgs.5364/dados").respond(200, json=mock_data)
        mock.get("/dados/serie/bcdata.sgs.4513/dados").respond(200, json=mock_data)
        mock.get("/dados/serie/bcdata.sgs.13762/dados").respond(200, json=mock_data)
        mock.get("/dados/serie/bcdata.sgs.21864/dados").respond(200, json=mock_data)
        mock.get("/dados/serie/bcdata.sgs.21865/dados").respond(200, json=mock_data)
        mock.get("/dados/serie/bcdata.sgs.7620/dados").respond(200, json=mock_data)

        async with StnFiscalConnector() as conn:
            records = await conn.fetch(date(2025, 1, 1), date(2025, 1, 31))

    # 6 series x 1 record each = 6 records
    assert len(records) == 6

    # Verify all series keys are present
    series_keys = {r["_series_key"] for r in records}
    assert series_keys == {
        "BR_PRIMARY_BALANCE_MONTHLY",
        "BR_NET_DEBT_GDP_CENTRAL",
        "BR_GROSS_DEBT_GDP",
        "BR_TOTAL_REVENUE",
        "BR_TOTAL_EXPENDITURE",
        "BR_SOCIAL_SEC_DEFICIT",
    }

    # Verify fiscal_metric varies across series
    metrics = {r["fiscal_metric"] for r in records}
    assert "PRIMARY_BALANCE" in metrics
    assert "GROSS_DEBT_GDP" in metrics
    assert "TOTAL_REVENUE" in metrics


@pytest.mark.asyncio
async def test_fetch_subset_of_series():
    """Verify fetch() can fetch a subset of series via series_ids param."""
    mock_data = [{"data": "01/01/2025", "valor": "100.0"}]

    with respx.mock(base_url="https://api.bcb.gov.br") as mock:
        mock.get("/dados/serie/bcdata.sgs.5364/dados").respond(200, json=mock_data)

        async with StnFiscalConnector() as conn:
            records = await conn.fetch(
                date(2025, 1, 1),
                date(2025, 1, 31),
                series_ids=["BR_PRIMARY_BALANCE_MONTHLY"],
            )

    assert len(records) == 1
    assert records[0]["_series_key"] == "BR_PRIMARY_BALANCE_MONTHLY"


@pytest.mark.asyncio
async def test_fetch_skips_unknown_series_key():
    """Verify fetch() skips unknown series keys without error."""
    with respx.mock(base_url="https://api.bcb.gov.br"):
        async with StnFiscalConnector() as conn:
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
def test_series_registry_has_6_series():
    """Verify the series registry contains exactly 6 series."""
    assert len(StnFiscalConnector.SERIES_REGISTRY) == 6


def test_series_registry_keys_and_codes():
    """Verify the registry includes the expected series keys and BCB codes."""
    registry = StnFiscalConnector.SERIES_REGISTRY

    assert "BR_PRIMARY_BALANCE_MONTHLY" in registry
    assert registry["BR_PRIMARY_BALANCE_MONTHLY"][0] == 5364

    assert "BR_NET_DEBT_GDP_CENTRAL" in registry
    assert registry["BR_NET_DEBT_GDP_CENTRAL"][0] == 4513

    assert "BR_GROSS_DEBT_GDP" in registry
    assert registry["BR_GROSS_DEBT_GDP"][0] == 13762

    assert "BR_TOTAL_REVENUE" in registry
    assert registry["BR_TOTAL_REVENUE"][0] == 21864

    assert "BR_TOTAL_EXPENDITURE" in registry
    assert registry["BR_TOTAL_EXPENDITURE"][0] == 21865

    assert "BR_SOCIAL_SEC_DEFICIT" in registry
    assert registry["BR_SOCIAL_SEC_DEFICIT"][0] == 7620


def test_series_registry_tuples_have_3_elements():
    """Verify each registry entry is a tuple of (code, fiscal_metric, unit)."""
    for key, entry in StnFiscalConnector.SERIES_REGISTRY.items():
        assert isinstance(entry, tuple), f"{key} is not a tuple"
        assert len(entry) == 3, f"{key} tuple has {len(entry)} elements, expected 3"
        code, metric, unit = entry
        assert isinstance(code, int) and code > 0, f"{key} code invalid: {code}"
        assert isinstance(metric, str) and len(metric) > 0, f"{key} metric empty"
        assert isinstance(unit, str) and len(unit) > 0, f"{key} unit empty"


def test_connector_constants():
    """Verify connector class-level constants are set correctly."""
    assert StnFiscalConnector.SOURCE_NAME == "STN_FISCAL"
    assert StnFiscalConnector.BASE_URL == "https://api.bcb.gov.br"
    assert StnFiscalConnector.RATE_LIMIT_PER_SECOND == 3.0


def test_connector_inherits_from_base_connector():
    """Verify StnFiscalConnector inherits from BaseConnector."""
    from src.connectors.base import BaseConnector

    assert issubclass(StnFiscalConnector, BaseConnector)

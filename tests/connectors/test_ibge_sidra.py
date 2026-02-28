"""Tests for IBGE SIDRA connector.

Uses respx to mock IBGE SIDRA API HTTP responses and verify:
- Header row (index 0) is skipped
- YYYYMM period parsing to first-of-month dates
- Invalid values ("", "-", "...") are skipped
- Series keys correctly incorporate group name
- All 9 IPCA groups are in the registry
- Both MoM change and weight variables are fetched
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from src.connectors.ibge_sidra import IbgeSidraConnector

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def ibge_sidra_sample() -> list[dict]:
    """Load the IBGE SIDRA sample fixture."""
    with (FIXTURES_DIR / "ibge_sidra_sample.json").open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def connector() -> IbgeSidraConnector:
    """Create an IbgeSidraConnector instance."""
    return IbgeSidraConnector()


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------
def test_ipca_groups_has_9_entries():
    """Verify IPCA_GROUPS contains exactly 9 consumption groups."""
    assert len(IbgeSidraConnector.IPCA_GROUPS) == 9


def test_ipca_groups_has_expected_groups():
    """Verify all 9 expected IPCA groups are present."""
    expected = {
        "FOOD",
        "HOUSING",
        "HOUSEHOLD",
        "CLOTHING",
        "TRANSPORT",
        "HEALTH",
        "PERSONAL",
        "EDUCATION",
        "COMMUNICATION",
    }
    assert set(IbgeSidraConnector.IPCA_GROUPS.keys()) == expected


def test_code_to_name_reverse_map():
    """Verify the reverse map correctly maps codes back to group names."""
    for name, code in IbgeSidraConnector.IPCA_GROUPS.items():
        assert IbgeSidraConnector._CODE_TO_NAME[str(code)] == name


def test_connector_constants():
    """Verify connector class-level constants are set correctly."""
    assert IbgeSidraConnector.SOURCE_NAME == "IBGE_SIDRA"
    assert IbgeSidraConnector.BASE_URL == "https://apisidra.ibge.gov.br"
    assert IbgeSidraConnector.RATE_LIMIT_PER_SECOND == 1.0
    assert IbgeSidraConnector.TIMEOUT_SECONDS == 60.0


# ---------------------------------------------------------------------------
# Period parsing tests
# ---------------------------------------------------------------------------
def test_period_to_date_valid():
    """Verify YYYYMM is parsed to first-of-month date."""
    assert IbgeSidraConnector._period_to_date("202401") == date(2024, 1, 1)
    assert IbgeSidraConnector._period_to_date("202312") == date(2023, 12, 1)
    assert IbgeSidraConnector._period_to_date("202006") == date(2020, 6, 1)


def test_period_to_date_invalid():
    """Verify invalid periods return None."""
    assert IbgeSidraConnector._period_to_date("") is None
    assert IbgeSidraConnector._period_to_date("2024") is None
    assert IbgeSidraConnector._period_to_date("20241301") is None  # too long


def test_date_to_period():
    """Verify date to YYYYMM conversion."""
    assert IbgeSidraConnector._date_to_period(date(2024, 1, 15)) == "202401"
    assert IbgeSidraConnector._date_to_period(date(2023, 12, 31)) == "202312"


# ---------------------------------------------------------------------------
# Fetch tests with respx mocking
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fetch_variable_skips_header_row(ibge_sidra_sample):
    """Verify the first element (header metadata) is always skipped."""
    with respx.mock(base_url="https://apisidra.ibge.gov.br") as mock:
        # Mock the MoM change variable request
        mock.get(url__regex=r"/values/t/7060/.*").respond(200, json=ibge_sidra_sample)

        async with IbgeSidraConnector() as conn:
            records = await conn._fetch_variable(63, "202401", "202402")

    # The fixture has 7 items: 1 header + 6 data rows
    # Of the 6 data rows: 3 have valid values, 3 have invalid ("", "-", "...")
    assert len(records) == 3

    # Verify no record has the header metadata (header has no valid V value
    # and non-numeric NC/NN fields that would be in data items)
    for rec in records:
        assert rec["_series_key"].startswith("BR_IPCA_")
        assert rec["observation_date"] is not None


@pytest.mark.asyncio
async def test_fetch_variable_parses_dates_correctly(ibge_sidra_sample):
    """Verify YYYYMM periods are converted to first-of-month dates."""
    with respx.mock(base_url="https://apisidra.ibge.gov.br") as mock:
        mock.get(url__regex=r"/values/t/7060/.*").respond(200, json=ibge_sidra_sample)

        async with IbgeSidraConnector() as conn:
            records = await conn._fetch_variable(63, "202401", "202402")

    # Valid records: 202401/FOOD (1.53), 202401/HOUSING (0.25), 202402/FOOD (-0.37)
    dates = {rec["observation_date"] for rec in records}
    assert date(2024, 1, 1) in dates
    assert date(2024, 2, 1) in dates


@pytest.mark.asyncio
async def test_fetch_variable_skips_invalid_values(ibge_sidra_sample):
    """Verify records with empty, dash, or ellipsis values are skipped."""
    with respx.mock(base_url="https://apisidra.ibge.gov.br") as mock:
        mock.get(url__regex=r"/values/t/7060/.*").respond(200, json=ibge_sidra_sample)

        async with IbgeSidraConnector() as conn:
            records = await conn._fetch_variable(63, "202401", "202402")

    # Only 3 valid records should remain (1.53, 0.25, -0.37)
    values = [rec["value"] for rec in records]
    assert pytest.approx(1.53) in values
    assert pytest.approx(0.25) in values
    assert pytest.approx(-0.37) in values
    assert len(values) == 3


@pytest.mark.asyncio
async def test_series_keys_incorporate_group_name(ibge_sidra_sample):
    """Verify series keys follow BR_IPCA_{GROUP}_MOM pattern."""
    with respx.mock(base_url="https://apisidra.ibge.gov.br") as mock:
        mock.get(url__regex=r"/values/t/7060/.*").respond(200, json=ibge_sidra_sample)

        async with IbgeSidraConnector() as conn:
            records = await conn._fetch_variable(63, "202401", "202402")

    keys = {rec["_series_key"] for rec in records}
    assert "BR_IPCA_FOOD_MOM" in keys
    assert "BR_IPCA_HOUSING_MOM" in keys


@pytest.mark.asyncio
async def test_fetch_variable_weight_produces_weight_keys():
    """Verify variable 2265 (weight) produces _WEIGHT series keys."""
    sample_data = [
        {  # Header row
            "NC": "header",
            "NN": "header",
            "V": "Valor",
            "D3C": "202401",
            "D4C": "7169",
        },
        {  # Data row
            "NC": "1",
            "NN": "Brasil",
            "V": "21.15",
            "D3C": "202401",
            "D4C": "7169",
        },
    ]

    with respx.mock(base_url="https://apisidra.ibge.gov.br") as mock:
        mock.get(url__regex=r"/values/t/7060/.*").respond(200, json=sample_data)

        async with IbgeSidraConnector() as conn:
            records = await conn._fetch_variable(2265, "202401", "202401")

    assert len(records) == 1
    assert records[0]["_series_key"] == "BR_IPCA_FOOD_WEIGHT"
    assert records[0]["value"] == pytest.approx(21.15)


@pytest.mark.asyncio
async def test_fetch_handles_empty_response():
    """Verify empty response returns empty list."""
    with respx.mock(base_url="https://apisidra.ibge.gov.br") as mock:
        mock.get(url__regex=r"/values/t/7060/.*").respond(200, json=[])

        async with IbgeSidraConnector() as conn:
            records = await conn._fetch_variable(63, "202401", "202401")

    assert records == []


@pytest.mark.asyncio
async def test_fetch_handles_non_list_response():
    """Verify non-list response is handled gracefully."""
    with respx.mock(base_url="https://apisidra.ibge.gov.br") as mock:
        mock.get(url__regex=r"/values/t/7060/.*").respond(
            200, json={"error": "service unavailable"}
        )

        async with IbgeSidraConnector() as conn:
            records = await conn._fetch_variable(63, "202401", "202401")

    assert records == []


@pytest.mark.asyncio
async def test_fetch_calls_both_variables():
    """Verify fetch() calls both MoM change (63) and weight (2265) endpoints."""
    mom_data = [
        {"NC": "header", "V": "V", "D3C": "202401", "D4C": "7169"},
        {"NC": "1", "V": "0.50", "D3C": "202401", "D4C": "7169"},
    ]
    weight_data = [
        {"NC": "header", "V": "V", "D3C": "202401", "D4C": "7169"},
        {"NC": "1", "V": "21.00", "D3C": "202401", "D4C": "7169"},
    ]

    with respx.mock(base_url="https://apisidra.ibge.gov.br") as mock:
        # Two sequential requests for different variables
        route = mock.get(url__regex=r"/values/t/7060/.*")
        route.side_effect = [
            httpx.Response(200, json=mom_data),
            httpx.Response(200, json=weight_data),
        ]

        async with IbgeSidraConnector() as conn:
            records = await conn.fetch(date(2024, 1, 1), date(2024, 1, 31))

    assert len(records) == 2
    keys = {rec["_series_key"] for rec in records}
    assert "BR_IPCA_FOOD_MOM" in keys
    assert "BR_IPCA_FOOD_WEIGHT" in keys


@pytest.mark.asyncio
async def test_records_have_required_fields(ibge_sidra_sample):
    """Verify each record has all required fields for macro_series table."""
    with respx.mock(base_url="https://apisidra.ibge.gov.br") as mock:
        mock.get(url__regex=r"/values/t/7060/.*").respond(200, json=ibge_sidra_sample)

        async with IbgeSidraConnector() as conn:
            records = await conn._fetch_variable(63, "202401", "202402")

    for rec in records:
        assert "_series_key" in rec
        assert "observation_date" in rec
        assert "value" in rec
        assert "release_time" in rec
        assert "revision_number" in rec
        assert rec["revision_number"] == 0
        assert "source" in rec
        assert rec["source"] == "IBGE_SIDRA"

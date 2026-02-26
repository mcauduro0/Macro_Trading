"""Tests for BCB Focus connector.

Uses respx to mock BCB OData API responses and verify:
- OData pagination with $top/$skip terminates correctly
- Series key encodes reference year (e.g., BR_FOCUS_IPCA_2026_MEDIAN)
- observation_date is the survey date (not the reference year)
- MAX_PAGES safety limit stops infinite loops
- Empty response handling
- Indicator name normalization (accents, hyphens removed)
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from src.connectors.bcb_focus import BcbFocusConnector, _normalize_indicator_name

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def bcb_focus_sample() -> dict:
    """Load the BCB Focus sample fixture."""
    with (FIXTURES_DIR / "bcb_focus_sample.json").open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def connector() -> BcbFocusConnector:
    """Create a BcbFocusConnector instance."""
    return BcbFocusConnector()


# ---------------------------------------------------------------------------
# Indicator name normalization tests
# ---------------------------------------------------------------------------
def test_normalize_indicator_removes_accents():
    """Verify accented characters are normalized."""
    assert _normalize_indicator_name("Câmbio") == "CAMBIO"


def test_normalize_indicator_removes_hyphens():
    """Verify hyphens are removed."""
    assert _normalize_indicator_name("IGP-M") == "IGPM"


def test_normalize_indicator_uppercases():
    """Verify result is uppercase."""
    assert _normalize_indicator_name("Selic") == "SELIC"
    assert _normalize_indicator_name("PIB") == "PIB"


# ---------------------------------------------------------------------------
# Connector constants tests
# ---------------------------------------------------------------------------
def test_connector_constants():
    """Verify connector class-level constants."""
    assert BcbFocusConnector.SOURCE_NAME == "BCB_FOCUS"
    assert BcbFocusConnector.BASE_URL == "https://olinda.bcb.gov.br"
    assert BcbFocusConnector.ODATA_PAGE_SIZE == 1000
    assert BcbFocusConnector.MAX_PAGES == 100
    assert BcbFocusConnector.RATE_LIMIT_PER_SECOND == 2.0


def test_indicators_have_5_entries():
    """Verify 5 indicators are configured."""
    assert len(BcbFocusConnector.INDICATORS) == 5


def test_indicators_have_expected_keys():
    """Verify all expected indicators are present."""
    expected = {"IPCA", "IGP-M", "Selic", "PIB", "Câmbio"}
    assert set(BcbFocusConnector.INDICATORS.keys()) == expected


# ---------------------------------------------------------------------------
# OData pagination tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pagination_terminates_on_partial_page():
    """Verify pagination stops when a page has fewer items than page size."""
    # Page 1: 3 items (< ODATA_PAGE_SIZE=1000) -> terminate after first page
    page_data = {
        "value": [
            {"Indicador": "IPCA", "Data": "2025-02-14",
             "DataReferencia": "2025", "Mediana": 5.60},
            {"Indicador": "IPCA", "Data": "2025-02-07",
             "DataReferencia": "2025", "Mediana": 5.57},
            {"Indicador": "IPCA", "Data": "2025-01-31",
             "DataReferencia": "2025", "Mediana": 5.55},
        ]
    }

    with respx.mock(base_url="https://olinda.bcb.gov.br") as mock:
        mock.get(url__regex=r"/olinda/servico/Expectativas/.*").respond(
            200, json=page_data
        )

        async with BcbFocusConnector() as conn:
            items = await conn._fetch_odata_paginated(
                "ExpectativasMercadoAnuais",
                "Indicador eq 'IPCA'"
            )

    assert len(items) == 3


@pytest.mark.asyncio
async def test_pagination_multi_page():
    """Verify pagination fetches multiple pages when first is full."""
    # Create a connector with a small page size for testing
    connector = BcbFocusConnector()
    connector.ODATA_PAGE_SIZE = 2  # Small page size to test pagination

    # Page 1: 2 items (== page_size) -> fetch next page
    page1 = {
        "value": [
            {"Indicador": "IPCA", "Data": "2025-02-14",
             "DataReferencia": "2025", "Mediana": 5.60},
            {"Indicador": "IPCA", "Data": "2025-02-07",
             "DataReferencia": "2025", "Mediana": 5.57},
        ]
    }
    # Page 2: 1 item (< page_size) -> terminate
    page2 = {
        "value": [
            {"Indicador": "IPCA", "Data": "2025-01-31",
             "DataReferencia": "2025", "Mediana": 5.55},
        ]
    }

    with respx.mock(base_url="https://olinda.bcb.gov.br") as mock:
        route = mock.get(url__regex=r"/olinda/servico/Expectativas/.*")
        route.side_effect = [
            httpx.Response(200, json=page1),
            httpx.Response(200, json=page2),
        ]

        async with connector:
            items = await connector._fetch_odata_paginated(
                "ExpectativasMercadoAnuais",
                "Indicador eq 'IPCA'"
            )

    assert len(items) == 3


@pytest.mark.asyncio
async def test_pagination_max_pages_safety_limit():
    """Verify pagination stops after MAX_PAGES even if pages are always full."""
    connector = BcbFocusConnector()
    connector.ODATA_PAGE_SIZE = 2
    connector.MAX_PAGES = 3  # Small limit for testing

    # Always return full pages (2 items each)
    full_page = {
        "value": [
            {"Indicador": "IPCA", "Data": "2025-02-14",
             "DataReferencia": "2025", "Mediana": 5.60},
            {"Indicador": "IPCA", "Data": "2025-02-07",
             "DataReferencia": "2025", "Mediana": 5.57},
        ]
    }

    with respx.mock(base_url="https://olinda.bcb.gov.br") as mock:
        # Return full pages indefinitely
        mock.get(url__regex=r"/olinda/servico/Expectativas/.*").respond(
            200, json=full_page
        )

        async with connector:
            items = await connector._fetch_odata_paginated(
                "ExpectativasMercadoAnuais",
                "Indicador eq 'IPCA'"
            )

    # MAX_PAGES=3, page_size=2 -> 3*2 = 6 items max
    assert len(items) == 6


@pytest.mark.asyncio
async def test_pagination_empty_response():
    """Verify empty response (0 items) terminates immediately."""
    with respx.mock(base_url="https://olinda.bcb.gov.br") as mock:
        mock.get(url__regex=r"/olinda/servico/Expectativas/.*").respond(
            200, json={"value": []}
        )

        async with BcbFocusConnector() as conn:
            items = await conn._fetch_odata_paginated(
                "ExpectativasMercadoAnuais",
                "Indicador eq 'IPCA'"
            )

    assert items == []


# ---------------------------------------------------------------------------
# Fetch tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_series_key_encodes_reference_year(bcb_focus_sample):
    """Verify series keys contain the reference year for horizon disambiguation."""
    with respx.mock(base_url="https://olinda.bcb.gov.br") as mock:
        # All indicators return the same sample data
        mock.get(url__regex=r"/olinda/servico/Expectativas/.*").respond(
            200, json=bcb_focus_sample
        )

        async with BcbFocusConnector() as conn:
            records = await conn.fetch(date(2025, 2, 1), date(2025, 2, 28))

    # Check that reference year is encoded in keys
    keys = {rec["_series_key"] for rec in records}
    # IPCA has both 2025 and 2026 reference years in sample
    assert "BR_FOCUS_IPCA_2025_MEDIAN" in keys
    assert "BR_FOCUS_IPCA_2026_MEDIAN" in keys


@pytest.mark.asyncio
async def test_observation_date_is_survey_date(bcb_focus_sample):
    """Verify observation_date is the survey publication date, not reference year."""
    with respx.mock(base_url="https://olinda.bcb.gov.br") as mock:
        mock.get(url__regex=r"/olinda/servico/Expectativas/.*").respond(
            200, json=bcb_focus_sample
        )

        async with BcbFocusConnector() as conn:
            records = await conn.fetch(date(2025, 2, 1), date(2025, 2, 28))

    # All records should have survey dates (Feb 2025), not reference years
    for rec in records:
        assert rec["observation_date"].year == 2025
        assert rec["observation_date"].month == 2


@pytest.mark.asyncio
async def test_cambio_normalized_to_cambio():
    """Verify Cambio indicator produces CAMBIO in series key (accent removed)."""
    cambio_data = {
        "value": [
            {
                "Indicador": "Câmbio",
                "Data": "2025-02-14",
                "DataReferencia": "2025",
                "Mediana": 5.82,
            }
        ]
    }

    with respx.mock(base_url="https://olinda.bcb.gov.br") as mock:
        mock.get(url__regex=r"/olinda/servico/Expectativas/.*").respond(
            200, json=cambio_data
        )

        async with BcbFocusConnector() as conn:
            records = await conn.fetch(date(2025, 2, 1), date(2025, 2, 28))

    # Check that CAMBIO appears in keys (from Câmbio indicator)
    keys = {rec["_series_key"] for rec in records}
    cambio_keys = [k for k in keys if "CAMBIO" in k]
    assert len(cambio_keys) > 0
    assert "BR_FOCUS_CAMBIO_2025_MEDIAN" in keys


@pytest.mark.asyncio
async def test_igpm_normalized_to_igpm():
    """Verify IGP-M indicator produces IGPM in series key (hyphen removed)."""
    igpm_data = {
        "value": [
            {
                "Indicador": "IGP-M",
                "Data": "2025-02-14",
                "DataReferencia": "2025",
                "Mediana": 4.50,
            }
        ]
    }

    with respx.mock(base_url="https://olinda.bcb.gov.br") as mock:
        mock.get(url__regex=r"/olinda/servico/Expectativas/.*").respond(
            200, json=igpm_data
        )

        async with BcbFocusConnector() as conn:
            records = await conn.fetch(date(2025, 2, 1), date(2025, 2, 28))

    # Check IGPM keys exist (from IGP-M indicator)
    keys = {rec["_series_key"] for rec in records}
    igpm_keys = [k for k in keys if "IGPM" in k]
    assert len(igpm_keys) > 0
    # Verify the key pattern
    assert "BR_FOCUS_IGPM_2025_MEDIAN" in keys


@pytest.mark.asyncio
async def test_records_have_required_fields(bcb_focus_sample):
    """Verify each record has all required fields for macro_series table."""
    with respx.mock(base_url="https://olinda.bcb.gov.br") as mock:
        mock.get(url__regex=r"/olinda/servico/Expectativas/.*").respond(
            200, json=bcb_focus_sample
        )

        async with BcbFocusConnector() as conn:
            records = await conn.fetch(date(2025, 2, 1), date(2025, 2, 28))

    assert len(records) > 0
    for rec in records:
        assert "_series_key" in rec
        assert "observation_date" in rec
        assert "value" in rec
        assert "release_time" in rec
        assert "revision_number" in rec
        assert rec["revision_number"] == 0
        assert "source" in rec
        assert rec["source"] == "BCB_FOCUS"


@pytest.mark.asyncio
async def test_mediana_value_is_extracted(bcb_focus_sample):
    """Verify the Mediana (consensus median) is extracted as the value."""
    with respx.mock(base_url="https://olinda.bcb.gov.br") as mock:
        mock.get(url__regex=r"/olinda/servico/Expectativas/.*").respond(
            200, json=bcb_focus_sample
        )

        async with BcbFocusConnector() as conn:
            records = await conn.fetch(date(2025, 2, 1), date(2025, 2, 28))

    # Sample has Mediana values: 5.60, 4.20, 5.57 for IPCA
    values = [rec["value"] for rec in records if "IPCA" in rec["_series_key"]]
    assert pytest.approx(5.60) in values
    assert pytest.approx(4.20) in values
    assert pytest.approx(5.57) in values


@pytest.mark.asyncio
async def test_missing_mediana_skipped():
    """Verify records with None Mediana are skipped."""
    data = {
        "value": [
            {
                "Indicador": "IPCA",
                "Data": "2025-02-14",
                "DataReferencia": "2025",
                "Mediana": None,
            },
            {
                "Indicador": "IPCA",
                "Data": "2025-02-14",
                "DataReferencia": "2026",
                "Mediana": 4.20,
            },
        ]
    }

    with respx.mock(base_url="https://olinda.bcb.gov.br") as mock:
        mock.get(url__regex=r"/olinda/servico/Expectativas/.*").respond(
            200, json=data
        )

        async with BcbFocusConnector() as conn:
            records = await conn.fetch(date(2025, 2, 1), date(2025, 2, 28))

    # Only the record with Mediana=4.20 should be kept (times 5 indicators)
    ipca_records = [r for r in records if "IPCA" in r["_series_key"]]
    assert len(ipca_records) == 1
    assert ipca_records[0]["value"] == pytest.approx(4.20)


@pytest.mark.asyncio
async def test_release_time_has_sp_timezone(bcb_focus_sample):
    """Verify release_time uses America/Sao_Paulo timezone."""
    with respx.mock(base_url="https://olinda.bcb.gov.br") as mock:
        mock.get(url__regex=r"/olinda/servico/Expectativas/.*").respond(
            200, json=bcb_focus_sample
        )

        async with BcbFocusConnector() as conn:
            records = await conn.fetch(date(2025, 2, 1), date(2025, 2, 28))

    for rec in records:
        assert rec["release_time"].tzinfo is not None
        assert str(rec["release_time"].tzinfo) == "America/Sao_Paulo"

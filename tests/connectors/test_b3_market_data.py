"""Tests for B3/Tesouro Direto connector.

Uses respx to mock BCB SGS and Tesouro Direto HTTP responses and verify:
- DI swap curve: rate is divided by 100 (percentage to decimal)
- DI swap curve: curve_id='DI_PRE', correct tenor_label and tenor_days
- NTN-B: parses Tesouro Direto JSON correctly, curve_id='NTN_B_REAL'
- NTN-B: graceful fallback on 404 (returns empty list, no crash)
- Empty BCB SGS response handling
- Registry completeness (12 tenors)
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from src.connectors.b3_market_data import B3MarketDataConnector

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def tesouro_direto_response() -> dict:
    """Load sample Tesouro Direto JSON response."""
    filepath = FIXTURES_DIR / "tesouro_direto_sample.json"
    with filepath.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# DI Swap Curve Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_di_curve_rate_division_by_100():
    """Verify DI swap rates are converted from percentage to decimal (13.50 -> 0.1350)."""
    mock_data = [
        {"data": "02/01/2025", "valor": "13.50"},
        {"data": "03/01/2025", "valor": "14.25"},
    ]

    with respx.mock(base_url="https://api.bcb.gov.br") as mock:
        # Mock only the first tenor (7805 = 1M/30D) to keep test focused
        mock.get("/dados/serie/bcdata.sgs.7805/dados").respond(200, json=mock_data)
        # Mock remaining tenors with empty responses
        for code in range(7806, 7817):
            mock.get(f"/dados/serie/bcdata.sgs.{code}/dados").respond(200, json=[])

        async with B3MarketDataConnector() as conn:
            records = await conn.fetch_di_curve(date(2025, 1, 1), date(2025, 1, 31))

    # Should have 2 records from the 1M tenor
    di_records = [r for r in records if r["tenor_label"] == "1M"]
    assert len(di_records) == 2

    # Rate should be divided by 100: 13.50 -> 0.1350
    assert di_records[0]["rate"] == pytest.approx(0.1350)
    assert di_records[1]["rate"] == pytest.approx(0.1425)


@pytest.mark.asyncio
async def test_di_curve_has_correct_curve_id_and_tenors():
    """Verify DI records have curve_id='DI_PRE' with correct tenor metadata."""
    mock_data_1m = [{"data": "02/01/2025", "valor": "13.50"}]
    mock_data_6m = [{"data": "02/01/2025", "valor": "14.20"}]

    with respx.mock(base_url="https://api.bcb.gov.br") as mock:
        mock.get("/dados/serie/bcdata.sgs.7805/dados").respond(200, json=mock_data_1m)
        mock.get("/dados/serie/bcdata.sgs.7810/dados").respond(200, json=mock_data_6m)
        # Mock remaining tenors with empty responses
        for code in [7806, 7807, 7808, 7809, 7811, 7812, 7813, 7814, 7815, 7816]:
            mock.get(f"/dados/serie/bcdata.sgs.{code}/dados").respond(200, json=[])

        async with B3MarketDataConnector() as conn:
            records = await conn.fetch_di_curve(date(2025, 1, 1), date(2025, 1, 31))

    assert len(records) == 2

    # Check 1M tenor
    rec_1m = [r for r in records if r["tenor_label"] == "1M"][0]
    assert rec_1m["curve_id"] == "DI_PRE"
    assert rec_1m["tenor_days"] == 30
    assert rec_1m["curve_type"] == "swap"
    assert rec_1m["source"] == "BCB_SGS"

    # Check 6M tenor
    rec_6m = [r for r in records if r["tenor_label"] == "6M"][0]
    assert rec_6m["curve_id"] == "DI_PRE"
    assert rec_6m["tenor_days"] == 180
    assert rec_6m["rate"] == pytest.approx(0.1420)


@pytest.mark.asyncio
async def test_di_curve_skips_empty_and_invalid_values():
    """Verify DI curve skips empty, dash, and invalid date values."""
    mock_data = [
        {"data": "02/01/2025", "valor": ""},
        {"data": "invalid_date", "valor": "13.50"},
        {"data": "03/01/2025", "valor": "-"},
        {"data": "04/01/2025", "valor": "14.00"},
    ]

    with respx.mock(base_url="https://api.bcb.gov.br") as mock:
        mock.get("/dados/serie/bcdata.sgs.7805/dados").respond(200, json=mock_data)
        for code in range(7806, 7817):
            mock.get(f"/dados/serie/bcdata.sgs.{code}/dados").respond(200, json=[])

        async with B3MarketDataConnector() as conn:
            records = await conn.fetch_di_curve(date(2025, 1, 1), date(2025, 1, 31))

    # Only the last record should be parsed (value "14.00")
    assert len(records) == 1
    assert records[0]["rate"] == pytest.approx(0.14)


@pytest.mark.asyncio
async def test_di_curve_handles_empty_api_response():
    """Verify DI curve handles empty list from BCB SGS gracefully."""
    with respx.mock(base_url="https://api.bcb.gov.br") as mock:
        for code in range(7805, 7817):
            mock.get(f"/dados/serie/bcdata.sgs.{code}/dados").respond(200, json=[])

        async with B3MarketDataConnector() as conn:
            records = await conn.fetch_di_curve(date(2025, 1, 1), date(2025, 1, 31))

    assert records == []


# ---------------------------------------------------------------------------
# NTN-B Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ntnb_parses_tesouro_direto_json(tesouro_direto_response):
    """Verify NTN-B correctly parses Tesouro Direto JSON with curve_id='NTN_B_REAL'."""
    td_url = B3MarketDataConnector.TESOURO_DIRETO_URL

    with respx.mock:
        respx.get(td_url).respond(200, json=tesouro_direto_response)

        async with B3MarketDataConnector() as conn:
            records = await conn.fetch_ntnb_rates(as_of_date=date(2026, 1, 15))

    # Sample fixture has 3 NTN-B (IPCA+) bonds and 1 IPCA+ com Juros
    # (Prefixado and Selic are excluded)
    assert len(records) >= 3

    for rec in records:
        assert rec["curve_id"] == "NTN_B_REAL"
        assert rec["curve_type"] == "sovereign_real"
        assert rec["source"] == "TESOURO_DIRETO"
        assert rec["tenor_days"] > 0
        # Rate should be divided by 100 (e.g., 6.85 -> 0.0685)
        assert rec["rate"] < 1.0


@pytest.mark.asyncio
async def test_ntnb_rate_division(tesouro_direto_response):
    """Verify NTN-B rates are converted from percentage to decimal."""
    td_url = B3MarketDataConnector.TESOURO_DIRETO_URL

    with respx.mock:
        respx.get(td_url).respond(200, json=tesouro_direto_response)

        async with B3MarketDataConnector() as conn:
            records = await conn.fetch_ntnb_rates(as_of_date=date(2026, 1, 15))

    # First NTN-B in fixture has rate 6.85% -> 0.0685
    ntnb_2029 = [r for r in records if r["tenor_days"] < 1500]
    assert len(ntnb_2029) >= 1
    assert ntnb_2029[0]["rate"] == pytest.approx(0.0685)


@pytest.mark.asyncio
async def test_ntnb_fallback_on_404():
    """Verify NTN-B returns empty list on 404 (no crash)."""
    td_url = B3MarketDataConnector.TESOURO_DIRETO_URL

    with respx.mock:
        respx.get(td_url).respond(404)

        async with B3MarketDataConnector() as conn:
            records = await conn.fetch_ntnb_rates(as_of_date=date(2026, 1, 15))

    assert records == []


@pytest.mark.asyncio
async def test_ntnb_fallback_on_timeout():
    """Verify NTN-B returns empty list on timeout (no crash)."""
    td_url = B3MarketDataConnector.TESOURO_DIRETO_URL

    with respx.mock:
        respx.get(td_url).mock(side_effect=httpx.TimeoutException("timeout"))

        async with B3MarketDataConnector() as conn:
            # Override retries to avoid slow test
            conn.MAX_RETRIES = 1
            records = await conn.fetch_ntnb_rates(as_of_date=date(2026, 1, 15))

    assert records == []


@pytest.mark.asyncio
async def test_ntnb_skips_non_ipca_bonds(tesouro_direto_response):
    """Verify NTN-B skips Prefixado and Selic bonds."""
    td_url = B3MarketDataConnector.TESOURO_DIRETO_URL

    with respx.mock:
        respx.get(td_url).respond(200, json=tesouro_direto_response)

        async with B3MarketDataConnector() as conn:
            records = await conn.fetch_ntnb_rates(as_of_date=date(2026, 1, 15))

    # Verify no Prefixado or Selic bonds
    for rec in records:
        assert rec["curve_id"] == "NTN_B_REAL"


# ---------------------------------------------------------------------------
# Registry Tests
# ---------------------------------------------------------------------------
def test_di_registry_has_12_tenors():
    """Verify DI swap registry has exactly 12 tenors (30d to 360d)."""
    assert len(B3MarketDataConnector.DI_SWAP_REGISTRY) == 12


def test_di_registry_sgs_codes():
    """Verify DI swap SGS codes are #7805 through #7816."""
    registry = B3MarketDataConnector.DI_SWAP_REGISTRY
    codes = sorted(entry[0] for entry in registry.values())
    assert codes == list(range(7805, 7817))


def test_di_registry_tenor_days_ascending():
    """Verify tenor_days are ascending from 30 to 360."""
    registry = B3MarketDataConnector.DI_SWAP_REGISTRY
    days = [entry[2] for entry in registry.values()]
    assert days == sorted(days)
    assert days[0] == 30
    assert days[-1] == 360


# ---------------------------------------------------------------------------
# Connector Constants
# ---------------------------------------------------------------------------
def test_connector_constants():
    """Verify connector class-level constants."""
    assert B3MarketDataConnector.SOURCE_NAME == "B3_MARKET_DATA"
    assert B3MarketDataConnector.BASE_URL == "https://api.bcb.gov.br"
    assert B3MarketDataConnector.RATE_LIMIT_PER_SECOND == 3.0


# ---------------------------------------------------------------------------
# Fetch (combined) Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fetch_combines_di_and_ntnb():
    """Verify fetch() combines DI_PRE and NTN_B_REAL records."""
    di_data = [{"data": "02/01/2025", "valor": "13.50"}]
    td_data = {
        "response": {
            "TrsrBdTradgList": [{
                "TrsrBd": {
                    "nm": "Tesouro IPCA+ 2029",
                    "mtrtyDt": "2029-05-15T00:00:00",
                    "anulInvstmtRate": 6.85,
                }
            }]
        }
    }

    td_url = B3MarketDataConnector.TESOURO_DIRETO_URL

    with respx.mock:
        respx.get(url__regex=r".*api\.bcb\.gov\.br.*7805.*").respond(200, json=di_data)
        for code in range(7806, 7817):
            respx.get(url__regex=rf".*api\.bcb\.gov\.br.*{code}.*").respond(
                200, json=[]
            )
        respx.get(td_url).respond(200, json=td_data)

        async with B3MarketDataConnector() as conn:
            records = await conn.fetch(date(2025, 1, 1), date(2025, 1, 31))

    di_recs = [r for r in records if r["curve_id"] == "DI_PRE"]
    ntnb_recs = [r for r in records if r["curve_id"] == "NTN_B_REAL"]

    assert len(di_recs) >= 1
    assert len(ntnb_recs) >= 1

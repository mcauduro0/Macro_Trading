"""Tests for US Treasury yield curve connector.

Uses respx to mock Treasury.gov CSV responses and verify:
- Nominal curve parsing: correct number of records, rates divided by 100
- N/A and empty values are skipped (not parsed as float)
- Breakeven computation: UST_BEI rate = nominal - real at matching tenors
- Date filtering: records outside start/end range are excluded
- Unknown columns (e.g., '1.5 Mo') are skipped without error
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import respx

from src.connectors.treasury_gov import TreasuryGovConnector

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def treasury_csv_nominal() -> str:
    """Load sample Treasury nominal yield CSV."""
    filepath = FIXTURES_DIR / "treasury_yield_sample.csv"
    return filepath.read_text(encoding="utf-8")


@pytest.fixture
def treasury_csv_real() -> str:
    """Sample Treasury real (TIPS) yield CSV with fewer tenors."""
    return (
        "Date,5 Yr,7 Yr,10 Yr,20 Yr,30 Yr\n"
        "01/02/2025,1.92,2.05,2.12,2.28,2.25\n"
        "01/03/2025,1.90,2.03,2.10,N/A,2.23\n"
        "01/06/2025,1.94,2.07,2.14,2.30,2.27\n"
    )


# ---------------------------------------------------------------------------
# Helper: build the actual URL paths the connector will request
# ---------------------------------------------------------------------------
def _nominal_path(year: int) -> str:
    return TreasuryGovConnector.NOMINAL_URL.format(year=year)


def _real_path(year: int) -> str:
    return TreasuryGovConnector.REAL_URL.format(year=year)


# ---------------------------------------------------------------------------
# Nominal Curve Parsing
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_nominal_curve_parsing(treasury_csv_nominal):
    """Verify nominal curve records are parsed correctly with rates / 100."""
    with respx.mock(base_url="https://home.treasury.gov") as mock:
        mock.get(_nominal_path(2025)).respond(200, text=treasury_csv_nominal)

        async with TreasuryGovConnector() as conn:
            records = await conn._fetch_curve_csv(
                TreasuryGovConnector.NOMINAL_URL, 2025, "UST_NOM", "sovereign_nominal"
            )

    # Should have records from 3 dates
    dates = {r["curve_date"] for r in records}
    assert len(dates) == 3

    # All records should have curve_id UST_NOM
    for rec in records:
        assert rec["curve_id"] == "UST_NOM"
        assert rec["curve_type"] == "sovereign_nominal"
        assert rec["source"] == "TREASURY_GOV"

    # Check rate division: 4.35 -> 0.0435
    rec_1mo_d1 = [
        r for r in records
        if r["tenor_label"] == "1M" and r["curve_date"] == date(2025, 1, 2)
    ]
    assert len(rec_1mo_d1) == 1
    assert rec_1mo_d1[0]["rate"] == pytest.approx(0.0435)
    assert rec_1mo_d1[0]["tenor_days"] == 30


@pytest.mark.asyncio
async def test_nominal_skips_na_and_empty(treasury_csv_nominal):
    """Verify N/A and empty values are skipped (not parsed as float)."""
    with respx.mock(base_url="https://home.treasury.gov") as mock:
        mock.get(_nominal_path(2025)).respond(200, text=treasury_csv_nominal)

        async with TreasuryGovConnector() as conn:
            records = await conn._fetch_curve_csv(
                TreasuryGovConnector.NOMINAL_URL, 2025, "UST_NOM", "sovereign_nominal"
            )

    # Row 1 (01/02/2025): 4 Mo is empty, so no 4M record for that date
    d1_4m = [
        r for r in records
        if r["curve_date"] == date(2025, 1, 2) and r["tenor_label"] == "4M"
    ]
    assert len(d1_4m) == 0

    # Row 2 (01/03/2025): 20 Yr is "N/A", so no 20Y record for that date
    d2_20y = [
        r for r in records
        if r["curve_date"] == date(2025, 1, 3) and r["tenor_label"] == "20Y"
    ]
    assert len(d2_20y) == 0


@pytest.mark.asyncio
async def test_unknown_columns_skipped(treasury_csv_nominal):
    """Verify unknown columns like '1.5 Mo' are skipped without error."""
    with respx.mock(base_url="https://home.treasury.gov") as mock:
        mock.get(_nominal_path(2025)).respond(200, text=treasury_csv_nominal)

        async with TreasuryGovConnector() as conn:
            records = await conn._fetch_curve_csv(
                TreasuryGovConnector.NOMINAL_URL, 2025, "UST_NOM", "sovereign_nominal"
            )

    # No records should have a tenor from the unknown "1.5 Mo" column
    tenor_labels = {r["tenor_label"] for r in records}
    assert "1.5M" not in tenor_labels
    # But should have valid tenors
    assert "1M" in tenor_labels
    assert "10Y" in tenor_labels


# ---------------------------------------------------------------------------
# Breakeven Computation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_breakeven_computation(treasury_csv_nominal, treasury_csv_real):
    """Verify UST_BEI = nominal - real at matching tenors."""
    with respx.mock(base_url="https://home.treasury.gov") as mock:
        mock.get(_nominal_path(2025)).respond(200, text=treasury_csv_nominal)
        mock.get(_real_path(2025)).respond(200, text=treasury_csv_real)

        async with TreasuryGovConnector() as conn:
            records = await conn.fetch(date(2025, 1, 1), date(2025, 1, 31))

    bei_records = [r for r in records if r["curve_id"] == "UST_BEI"]
    assert len(bei_records) > 0

    # Check breakeven for 10Y on 01/02/2025:
    # nominal 10Y = 4.60% = 0.0460, real 10Y = 2.12% = 0.0212
    # BEI = 0.0460 - 0.0212 = 0.0248
    bei_10y_d1 = [
        r for r in bei_records
        if r["curve_date"] == date(2025, 1, 2) and r["tenor_label"] == "10Y"
    ]
    assert len(bei_10y_d1) == 1
    assert bei_10y_d1[0]["rate"] == pytest.approx(0.0248)
    assert bei_10y_d1[0]["curve_type"] == "breakeven"
    assert bei_10y_d1[0]["source"] == "TREASURY_GOV"
    assert bei_10y_d1[0]["tenor_days"] == 3650


@pytest.mark.asyncio
async def test_breakeven_skips_unmatched_tenors(treasury_csv_nominal, treasury_csv_real):
    """Verify breakeven only computed where both nominal and real exist."""
    with respx.mock(base_url="https://home.treasury.gov") as mock:
        mock.get(_nominal_path(2025)).respond(200, text=treasury_csv_nominal)
        mock.get(_real_path(2025)).respond(200, text=treasury_csv_real)

        async with TreasuryGovConnector() as conn:
            records = await conn.fetch(date(2025, 1, 1), date(2025, 1, 31))

    bei_records = [r for r in records if r["curve_id"] == "UST_BEI"]

    # No BEI for 1M, 2M, 3M etc. since real curve only has 5Y+ tenors
    bei_1m = [r for r in bei_records if r["tenor_label"] == "1M"]
    assert len(bei_1m) == 0


# ---------------------------------------------------------------------------
# Date Filtering
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_date_filtering(treasury_csv_nominal, treasury_csv_real):
    """Verify records outside start/end range are excluded."""
    with respx.mock(base_url="https://home.treasury.gov") as mock:
        mock.get(_nominal_path(2025)).respond(200, text=treasury_csv_nominal)
        mock.get(_real_path(2025)).respond(200, text=treasury_csv_real)

        async with TreasuryGovConnector() as conn:
            # Only request Jan 2-3, excluding Jan 6
            records = await conn.fetch(date(2025, 1, 2), date(2025, 1, 3))

    # Should not have Jan 6 records
    dates = {r["curve_date"] for r in records}
    assert date(2025, 1, 6) not in dates
    assert date(2025, 1, 2) in dates
    assert date(2025, 1, 3) in dates


# ---------------------------------------------------------------------------
# Static Breakeven Computation
# ---------------------------------------------------------------------------
def test_compute_breakeven_static():
    """Verify _compute_breakeven with known inputs."""
    nominal = [
        {"curve_id": "UST_NOM", "curve_date": date(2025, 1, 2),
         "tenor_days": 1825, "tenor_label": "5Y", "rate": 0.0442,
         "curve_type": "sovereign_nominal", "source": "TREASURY_GOV"},
        {"curve_id": "UST_NOM", "curve_date": date(2025, 1, 2),
         "tenor_days": 3650, "tenor_label": "10Y", "rate": 0.0460,
         "curve_type": "sovereign_nominal", "source": "TREASURY_GOV"},
    ]
    real = [
        {"curve_id": "UST_REAL", "curve_date": date(2025, 1, 2),
         "tenor_days": 1825, "tenor_label": "5Y", "rate": 0.0192,
         "curve_type": "sovereign_real", "source": "TREASURY_GOV"},
        {"curve_id": "UST_REAL", "curve_date": date(2025, 1, 2),
         "tenor_days": 3650, "tenor_label": "10Y", "rate": 0.0212,
         "curve_type": "sovereign_real", "source": "TREASURY_GOV"},
    ]

    bei = TreasuryGovConnector._compute_breakeven(nominal, real)

    assert len(bei) == 2
    assert bei[0]["curve_id"] == "UST_BEI"
    assert bei[0]["tenor_label"] == "5Y"
    assert bei[0]["rate"] == pytest.approx(0.0250)  # 0.0442 - 0.0192
    assert bei[1]["tenor_label"] == "10Y"
    assert bei[1]["rate"] == pytest.approx(0.0248)  # 0.0460 - 0.0212


# ---------------------------------------------------------------------------
# Tenor Map Tests
# ---------------------------------------------------------------------------
def test_tenor_map_has_13_tenors():
    """Verify TENOR_MAP has exactly 13 tenors."""
    assert len(TreasuryGovConnector.TENOR_MAP) == 13


def test_tenor_map_days_ascending():
    """Verify tenor_days are ascending."""
    days = [entry[1] for entry in TreasuryGovConnector.TENOR_MAP.values()]
    assert days == sorted(days)
    assert days[0] == 30
    assert days[-1] == 10950


# ---------------------------------------------------------------------------
# Connector Constants
# ---------------------------------------------------------------------------
def test_connector_constants():
    """Verify connector class-level constants."""
    assert TreasuryGovConnector.SOURCE_NAME == "TREASURY_GOV"
    assert TreasuryGovConnector.BASE_URL == "https://home.treasury.gov"
    assert TreasuryGovConnector.RATE_LIMIT_PER_SECOND == 2.0
    assert TreasuryGovConnector.TIMEOUT_SECONDS == 60.0


# ---------------------------------------------------------------------------
# CSV fetch error handling
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_csv_fetch_error_returns_empty():
    """Verify graceful handling of CSV fetch errors."""
    with respx.mock(base_url="https://home.treasury.gov") as mock:
        mock.get(_nominal_path(2025)).respond(500)

        async with TreasuryGovConnector() as conn:
            conn.MAX_RETRIES = 1
            records = await conn._fetch_curve_csv(
                TreasuryGovConnector.NOMINAL_URL, 2025, "UST_NOM", "sovereign_nominal"
            )

    assert records == []


@pytest.mark.asyncio
async def test_empty_csv_returns_empty():
    """Verify empty CSV returns empty list."""
    with respx.mock(base_url="https://home.treasury.gov") as mock:
        mock.get(_nominal_path(2025)).respond(200, text="")

        async with TreasuryGovConnector() as conn:
            records = await conn._fetch_curve_csv(
                TreasuryGovConnector.NOMINAL_URL, 2025, "UST_NOM", "sovereign_nominal"
            )

    assert records == []

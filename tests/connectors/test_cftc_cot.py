"""Tests for CFTC COT disaggregated connector.

Uses respx to mock CFTC ZIP downloads and Socrata CSV responses, plus
in-memory CSV fixtures for net position computation.

Verifies:
- Net position computation: long - short for each of 4 categories
- Contract filtering: only tracked contracts appear in output
- Series key format: CFTC_{CONTRACT}_{CATEGORY}_NET
- ZIP extraction: mock ZIP download with real ZIP bytes
- Socrata fallback: mock Socrata endpoint returning CSV data
- Column validation: missing columns log warning, do not crash
- Empty DataFrame produces empty record list
"""

from __future__ import annotations

import io
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
import respx

from src.connectors.cftc_cot import CftcCotConnector

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def connector() -> CftcCotConnector:
    """Create a CftcCotConnector instance without entering async context."""
    return CftcCotConnector()


@pytest.fixture
def sample_csv_text() -> str:
    """Load the sample disaggregated CSV fixture."""
    filepath = FIXTURES_DIR / "cftc_disagg_sample.csv"
    return filepath.read_text(encoding="utf-8")


@pytest.fixture
def sample_df(sample_csv_text: str) -> pd.DataFrame:
    """Parse sample CSV fixture into a DataFrame."""
    return pd.read_csv(io.StringIO(sample_csv_text))


@pytest.fixture
def sample_zip_bytes(sample_csv_text: str) -> bytes:
    """Create a ZIP archive in-memory containing the sample CSV."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("fut_disagg_txt_2025.csv", sample_csv_text)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Net Position Computation
# ---------------------------------------------------------------------------
def test_compute_net_positions_basic(
    connector: CftcCotConnector, sample_df: pd.DataFrame
):
    """Verify net = long - short for each category and contract."""
    records = connector.compute_net_positions(sample_df)

    # 2 tracked contracts (ES=13874A, TY=043602) x 4 categories x 2 dates = 16
    # Row 5 (contract 999999) should be skipped
    assert len(records) == 16

    # ES DEALER_NET on 2025-01-07: 120000 - 95000 = 25000
    es_dealer = [
        r
        for r in records
        if r["_series_key"] == "CFTC_ES_DEALER_NET"
        and r["observation_date"] == date(2025, 1, 7)
    ]
    assert len(es_dealer) == 1
    assert es_dealer[0]["value"] == pytest.approx(25000.0)
    assert es_dealer[0]["flow_type"] == "CFTC_DEALER_NET"
    assert es_dealer[0]["unit"] == "contracts"

    # TY LEVERAGED_NET on 2025-01-07: 350000 - 420000 = -70000
    ty_lev = [
        r
        for r in records
        if r["_series_key"] == "CFTC_TY_LEVERAGED_NET"
        and r["observation_date"] == date(2025, 1, 7)
    ]
    assert len(ty_lev) == 1
    assert ty_lev[0]["value"] == pytest.approx(-70000.0)

    # ES ASSETMGR_NET on 2025-01-14: 460000 - 390000 = 70000
    es_am = [
        r
        for r in records
        if r["_series_key"] == "CFTC_ES_ASSETMGR_NET"
        and r["observation_date"] == date(2025, 1, 14)
    ]
    assert len(es_am) == 1
    assert es_am[0]["value"] == pytest.approx(70000.0)


def test_compute_net_positions_all_categories(
    connector: CftcCotConnector, sample_df: pd.DataFrame
):
    """Verify all 4 categories are computed for each contract."""
    records = connector.compute_net_positions(sample_df)

    # Check we get all 4 categories for ES on 2025-01-07
    es_d1 = [
        r
        for r in records
        if r["_series_key"].startswith("CFTC_ES_")
        and r["observation_date"] == date(2025, 1, 7)
    ]
    categories = {r["_series_key"].split("_")[2] for r in es_d1}
    assert categories == {"DEALER", "ASSETMGR", "LEVERAGED", "OTHER"}


def test_compute_net_positions_contract_filtering(
    connector: CftcCotConnector, sample_df: pd.DataFrame
):
    """Verify untracked contracts (code 999999) are filtered out."""
    records = connector.compute_net_positions(sample_df)

    # No records should contain '999999' or 'UNTRACKED'
    series_keys = {r["_series_key"] for r in records}
    for key in series_keys:
        assert "999999" not in key
        assert "UNTRACKED" not in key


def test_compute_net_positions_series_key_format(
    connector: CftcCotConnector, sample_df: pd.DataFrame
):
    """Verify series_key follows CFTC_{CONTRACT}_{CATEGORY}_NET pattern."""
    records = connector.compute_net_positions(sample_df)

    for rec in records:
        key = rec["_series_key"]
        parts = key.split("_")
        assert parts[0] == "CFTC"
        assert parts[-1] == "NET"
        # Contract name should be in CONTRACT_CODES
        contract_name = parts[1]
        assert contract_name in CftcCotConnector.CONTRACT_CODES


def test_compute_net_positions_empty_df(connector: CftcCotConnector):
    """Verify empty DataFrame returns empty record list."""
    records = connector.compute_net_positions(pd.DataFrame())
    assert records == []


def test_compute_net_positions_missing_columns(connector: CftcCotConnector):
    """Verify missing category columns log warning but do not crash."""
    # DataFrame with correct structure but missing DEALER columns
    df = pd.DataFrame(
        {
            "Report_Date_as_YYYY-MM-DD": ["2025-01-07"],
            "CFTC_Contract_Market_Code": ["13874A"],
            "Asset_Mgr_Positions_Long_All": [100],
            "Asset_Mgr_Positions_Short_All": [50],
            "Lev_Money_Positions_Long_All": [200],
            "Lev_Money_Positions_Short_All": [150],
            "Other_Rept_Positions_Long_All": [30],
            "Other_Rept_Positions_Short_All": [20],
        }
    )

    records = connector.compute_net_positions(df)

    # Should have 3 categories (ASSETMGR, LEVERAGED, OTHER) but no DEALER
    assert len(records) == 3
    keys = {r["_series_key"] for r in records}
    assert "CFTC_ES_DEALER_NET" not in keys
    assert "CFTC_ES_ASSETMGR_NET" in keys
    assert "CFTC_ES_LEVERAGED_NET" in keys
    assert "CFTC_ES_OTHER_NET" in keys


def test_compute_net_positions_missing_date_column(connector: CftcCotConnector):
    """Verify missing date column returns empty records."""
    df = pd.DataFrame(
        {
            "CFTC_Contract_Market_Code": ["13874A"],
            "Dealer_Positions_Long_All": [100],
            "Dealer_Positions_Short_All": [50],
        }
    )

    records = connector.compute_net_positions(df)
    assert records == []


# ---------------------------------------------------------------------------
# ZIP Extraction
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_download_historical_year_extracts_zip(sample_zip_bytes: bytes):
    """Verify ZIP download extracts CSV and filters to tracked contracts."""
    with respx.mock(base_url="https://www.cftc.gov") as mock:
        mock.get("/files/dea/history/fut_disagg_txt_2025.zip").respond(
            200, content=sample_zip_bytes
        )

        async with CftcCotConnector() as conn:
            df = await conn._download_historical_year(2025)

    # Should only contain tracked contracts (ES and TY), not 999999
    assert len(df) == 4  # 2 contracts x 2 dates
    codes = set(df["CFTC_Contract_Market_Code"].astype(str).str.strip())
    assert codes == {"13874A", "043602"}


@pytest.mark.asyncio
async def test_download_historical_year_error_returns_empty():
    """Verify download error returns empty DataFrame."""
    with respx.mock(base_url="https://www.cftc.gov") as mock:
        mock.get("/files/dea/history/fut_disagg_txt_2020.zip").respond(500)

        async with CftcCotConnector() as conn:
            conn.MAX_RETRIES = 1
            df = await conn._download_historical_year(2020)

    assert df.empty


@pytest.mark.asyncio
async def test_download_historical_year_invalid_zip():
    """Verify corrupted ZIP returns empty DataFrame."""
    with respx.mock(base_url="https://www.cftc.gov") as mock:
        mock.get("/files/dea/history/fut_disagg_txt_2020.zip").respond(
            200, content=b"not a zip file"
        )

        async with CftcCotConnector() as conn:
            df = await conn._download_historical_year(2020)

    assert df.empty


# ---------------------------------------------------------------------------
# Socrata Fallback
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fetch_current_week_socrata(sample_csv_text: str):
    """Verify Socrata CSV fetch returns filtered DataFrame."""
    with respx.mock(base_url="https://publicreporting.cftc.gov") as mock:
        mock.get("/resource/72hh-3qpy.csv").respond(200, text=sample_csv_text)

        conn = CftcCotConnector()
        df = await conn._fetch_current_week()

    # Should only contain tracked contracts
    assert not df.empty
    codes = set(df["CFTC_Contract_Market_Code"].astype(str).str.strip())
    assert "999999" not in codes


@pytest.mark.asyncio
async def test_fetch_current_week_socrata_error():
    """Verify Socrata error returns empty DataFrame."""
    with respx.mock(base_url="https://publicreporting.cftc.gov") as mock:
        mock.get("/resource/72hh-3qpy.csv").respond(500)

        conn = CftcCotConnector()
        df = await conn._fetch_current_week()

    assert df.empty


@pytest.mark.asyncio
async def test_fetch_current_week_socrata_empty():
    """Verify empty Socrata response returns empty DataFrame."""
    with respx.mock(base_url="https://publicreporting.cftc.gov") as mock:
        mock.get("/resource/72hh-3qpy.csv").respond(200, text="")

        conn = CftcCotConnector()
        df = await conn._fetch_current_week()

    assert df.empty


# ---------------------------------------------------------------------------
# Fetch Integration (ZIP + Socrata combined)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fetch_combines_historical_and_current(
    sample_zip_bytes: bytes, sample_csv_text: str
):
    """Verify fetch() combines ZIP historical data with Socrata current data."""
    with respx.mock(base_url="https://www.cftc.gov") as cftc_mock:
        cftc_mock.get("/files/dea/history/fut_disagg_txt_2024.zip").respond(
            200, content=sample_zip_bytes
        )

        with respx.mock(base_url="https://publicreporting.cftc.gov") as socrata_mock:
            socrata_mock.get("/resource/72hh-3qpy.csv").respond(
                200, text=sample_csv_text
            )

            async with CftcCotConnector() as conn:
                records = await conn.fetch(date(2024, 1, 1), date(2026, 12, 31))

    # Should have records from both sources (all have 2025-01 dates)
    assert len(records) > 0


@pytest.mark.asyncio
async def test_fetch_date_filtering(sample_zip_bytes: bytes):
    """Verify fetch() filters records to the requested date range."""
    with respx.mock(base_url="https://www.cftc.gov") as mock:
        mock.get("/files/dea/history/fut_disagg_txt_2024.zip").respond(
            200, content=sample_zip_bytes
        )

        async with CftcCotConnector() as conn:
            # Request range that should only match first date (2025-01-07)
            records = await conn.fetch(date(2024, 1, 1), date(2025, 1, 10))

    # Only records from 2025-01-07 (not 2025-01-14)
    dates = {r["observation_date"] for r in records}
    assert date(2025, 1, 7) in dates
    assert date(2025, 1, 14) not in dates


# ---------------------------------------------------------------------------
# Registry and Constants
# ---------------------------------------------------------------------------
def test_contract_codes_has_12_entries():
    """Verify CONTRACT_CODES has exactly 13 contracts."""
    assert len(CftcCotConnector.CONTRACT_CODES) == 13


def test_categories_has_4_entries():
    """Verify CATEGORIES has exactly 4 trader categories."""
    assert len(CftcCotConnector.CATEGORIES) == 4


def test_reverse_contract_map_matches():
    """Verify reverse map is consistent with forward map."""
    for name, code in CftcCotConnector.CONTRACT_CODES.items():
        assert CftcCotConnector._reverse_contract_map[code] == name


def test_connector_constants():
    """Verify connector class-level constants."""
    assert CftcCotConnector.SOURCE_NAME == "CFTC_COT"
    assert CftcCotConnector.BASE_URL == "https://www.cftc.gov"
    assert CftcCotConnector.RATE_LIMIT_PER_SECOND == 1.0
    assert CftcCotConnector.TIMEOUT_SECONDS == 120.0
    assert CftcCotConnector.SOCRATA_BASE_URL == "https://publicreporting.cftc.gov"


def test_max_possible_series():
    """Verify 13 contracts x 4 categories = 52 possible series."""
    total = len(CftcCotConnector.CONTRACT_CODES) * len(CftcCotConnector.CATEGORIES)
    assert total == 52

"""Tests for FRED connector.

Uses respx to mock FRED API HTTP responses and verify:
- Observation parsing (dates, values)
- Missing value "." handling
- release_time from realtime_start
- API key inclusion in requests
- Series registry completeness
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import httpx
import pytest
import respx

from src.connectors.fred import FredConnector


# ---------------------------------------------------------------------------
# Sample FRED API response data
# ---------------------------------------------------------------------------
SAMPLE_OBSERVATIONS = {
    "realtime_start": "2025-01-01",
    "realtime_end": "2025-12-31",
    "observation_start": "2025-01-01",
    "observation_end": "2025-06-30",
    "observations": [
        {
            "realtime_start": "2025-02-14",
            "realtime_end": "2025-03-14",
            "date": "2025-01-01",
            "value": "308.417",
        },
        {
            "realtime_start": "2025-03-15",
            "realtime_end": "9999-12-31",
            "date": "2025-01-01",
            "value": "308.620",
        },
        {
            "realtime_start": "2025-03-15",
            "realtime_end": "9999-12-31",
            "date": "2025-02-01",
            "value": "309.685",
        },
    ],
}

SAMPLE_WITH_MISSING = {
    "realtime_start": "2025-01-01",
    "realtime_end": "2025-12-31",
    "observation_start": "2025-01-01",
    "observation_end": "2025-06-30",
    "observations": [
        {
            "realtime_start": "2025-02-14",
            "realtime_end": "2025-03-14",
            "date": "2025-01-01",
            "value": "308.417",
        },
        {
            "realtime_start": "2025-03-15",
            "realtime_end": "9999-12-31",
            "date": "2025-02-01",
            "value": ".",
        },
        {
            "realtime_start": "2025-04-10",
            "realtime_end": "9999-12-31",
            "date": "2025-03-01",
            "value": "309.100",
        },
    ],
}


# ---------------------------------------------------------------------------
# Observation parsing tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fetch_series_parses_observations():
    """Verify FRED connector correctly parses observation dates and values."""
    with respx.mock(base_url="https://api.stlouisfed.org") as mock:
        mock.get("/fred/series/observations").respond(
            200, json=SAMPLE_OBSERVATIONS
        )

        with patch("src.connectors.fred.settings") as mock_settings:
            mock_settings.fred_api_key = "test_api_key_123"

            async with FredConnector() as conn:
                records = await conn.fetch_series(
                    series_code="CPIAUCSL",
                    start_date=date(2025, 1, 1),
                    end_date=date(2025, 6, 30),
                )

    assert len(records) == 3

    # First observation
    assert records[0]["observation_date"] == date(2025, 1, 1)
    assert records[0]["value"] == pytest.approx(308.417)
    assert records[0]["revision_number"] == 0
    assert records[0]["source"] == "FRED"

    # Second observation (same date, different realtime)
    assert records[1]["observation_date"] == date(2025, 1, 1)
    assert records[1]["value"] == pytest.approx(308.620)

    # Third observation
    assert records[2]["observation_date"] == date(2025, 2, 1)
    assert records[2]["value"] == pytest.approx(309.685)


@pytest.mark.asyncio
async def test_fetch_series_skips_missing_values():
    """Verify FRED connector skips observations where value is '.' (FRED missing convention)."""
    with respx.mock(base_url="https://api.stlouisfed.org") as mock:
        mock.get("/fred/series/observations").respond(
            200, json=SAMPLE_WITH_MISSING
        )

        with patch("src.connectors.fred.settings") as mock_settings:
            mock_settings.fred_api_key = "test_api_key_123"

            async with FredConnector() as conn:
                records = await conn.fetch_series(
                    series_code="CPIAUCSL",
                    start_date=date(2025, 1, 1),
                    end_date=date(2025, 6, 30),
                )

    # Missing value "." should be skipped, so only 2 of 3 observations returned
    assert len(records) == 2
    assert records[0]["value"] == pytest.approx(308.417)
    assert records[1]["value"] == pytest.approx(309.100)


@pytest.mark.asyncio
async def test_fetch_series_includes_realtime_start_as_release_time():
    """Verify release_time is set from the realtime_start field of each observation."""
    with respx.mock(base_url="https://api.stlouisfed.org") as mock:
        mock.get("/fred/series/observations").respond(
            200, json=SAMPLE_OBSERVATIONS
        )

        with patch("src.connectors.fred.settings") as mock_settings:
            mock_settings.fred_api_key = "test_api_key_123"

            async with FredConnector() as conn:
                records = await conn.fetch_series(
                    series_code="CPIAUCSL",
                    start_date=date(2025, 1, 1),
                    end_date=date(2025, 6, 30),
                )

    # First observation: realtime_start is 2025-02-14
    assert records[0]["release_time"].year == 2025
    assert records[0]["release_time"].month == 2
    assert records[0]["release_time"].day == 14
    assert records[0]["release_time"].tzinfo is not None

    # Second observation: realtime_start is 2025-03-15
    assert records[1]["release_time"].month == 3
    assert records[1]["release_time"].day == 15


# ---------------------------------------------------------------------------
# API key tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fetch_requires_api_key():
    """Verify the FRED API request includes the api_key parameter."""
    with respx.mock(base_url="https://api.stlouisfed.org") as mock:
        route = mock.get("/fred/series/observations").respond(
            200, json={"observations": []}
        )

        with patch("src.connectors.fred.settings") as mock_settings:
            mock_settings.fred_api_key = "my_secret_key_456"

            async with FredConnector() as conn:
                records = await conn.fetch_series(
                    series_code="DFF",
                    start_date=date(2025, 1, 1),
                    end_date=date(2025, 1, 31),
                )

    # Verify request was made with api_key parameter
    assert route.called
    request = route.calls[0].request
    assert "api_key=my_secret_key_456" in str(request.url)


@pytest.mark.asyncio
async def test_fetch_raises_without_api_key():
    """Verify FRED connector raises ConnectorError when no API key is set."""
    with patch("src.connectors.fred.settings") as mock_settings:
        mock_settings.fred_api_key = ""

        async with FredConnector() as conn:
            with pytest.raises(Exception, match="FRED API key not configured"):
                await conn.fetch_series(
                    series_code="DFF",
                    start_date=date(2025, 1, 1),
                    end_date=date(2025, 1, 31),
                )


# ---------------------------------------------------------------------------
# Series registry tests
# ---------------------------------------------------------------------------
def test_series_registry_has_expected_count():
    """Verify the series registry contains at least 48 series (~50 from Fase0 guide)."""
    assert len(FredConnector.SERIES_REGISTRY) >= 48


def test_series_registry_has_key_series():
    """Verify the registry includes critical series for each category."""
    registry = FredConnector.SERIES_REGISTRY

    # Inflation
    assert "US_CPI_ALL_SA" in registry
    assert registry["US_CPI_ALL_SA"] == "CPIAUCSL"

    # Rates
    assert "US_FED_FUNDS" in registry
    assert registry["US_FED_FUNDS"] == "DFF"

    # Treasury
    assert "US_UST_10Y" in registry
    assert registry["US_UST_10Y"] == "DGS10"

    # Labor
    assert "US_NFP_TOTAL" in registry
    assert registry["US_NFP_TOTAL"] == "PAYEMS"

    # Credit
    assert "US_HY_OAS" in registry
    assert registry["US_HY_OAS"] == "BAMLH0A0HYM2"


def test_series_registry_values_are_strings():
    """Verify all FRED series codes are non-empty strings."""
    for key, code in FredConnector.SERIES_REGISTRY.items():
        assert isinstance(code, str), f"{key} code is not str: {type(code)}"
        assert len(code) > 0, f"{key} code is empty"


def test_revisable_series_subset_of_registry():
    """Verify all REVISABLE_SERIES keys exist in SERIES_REGISTRY."""
    for key in FredConnector.REVISABLE_SERIES:
        assert key in FredConnector.SERIES_REGISTRY, (
            f"REVISABLE_SERIES key '{key}' not found in SERIES_REGISTRY"
        )


# ---------------------------------------------------------------------------
# Connector constants tests
# ---------------------------------------------------------------------------
def test_connector_constants():
    """Verify connector class-level constants are set correctly."""
    assert FredConnector.SOURCE_NAME == "FRED"
    assert FredConnector.BASE_URL == "https://api.stlouisfed.org"
    assert FredConnector.RATE_LIMIT_PER_SECOND == 2.0
    assert FredConnector.TIMEOUT_SECONDS == 60.0


@pytest.mark.asyncio
async def test_fetch_series_handles_empty_observations():
    """Verify connector handles empty observations list gracefully."""
    with respx.mock(base_url="https://api.stlouisfed.org") as mock:
        mock.get("/fred/series/observations").respond(
            200, json={"observations": []}
        )

        with patch("src.connectors.fred.settings") as mock_settings:
            mock_settings.fred_api_key = "test_key"

            async with FredConnector() as conn:
                records = await conn.fetch_series(
                    series_code="DFF",
                    start_date=date(2025, 1, 1),
                    end_date=date(2025, 1, 31),
                )

    assert len(records) == 0

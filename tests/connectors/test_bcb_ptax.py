"""Tests for BcbPtaxConnector.

Verifies MM-DD-YYYY date formatting, closing bulletin filtering,
buy/sell rate mapping, timezone handling, and empty response handling.
Uses respx for HTTP mocking of the BCB OData API.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx
import pytest
import respx

from src.connectors.bcb_ptax import BcbPtaxConnector

SP_TZ = ZoneInfo("America/Sao_Paulo")

# ---------------------------------------------------------------------------
# Sample PTAX API responses
# ---------------------------------------------------------------------------

PTAX_CLOSING_AND_OPENING = {
    "value": [
        {
            "cotacaoCompra": 5.7036,
            "cotacaoVenda": 5.7042,
            "dataHoraCotacao": "2025-01-15 13:07:03.490",
            "tipoBoletim": "Fechamento",
        },
        {
            "cotacaoCompra": 5.6900,
            "cotacaoVenda": 5.6910,
            "dataHoraCotacao": "2025-01-15 10:05:12.123",
            "tipoBoletim": "Abertura",
        },
        {
            "cotacaoCompra": 5.7150,
            "cotacaoVenda": 5.7160,
            "dataHoraCotacao": "2025-01-16 13:08:45.567",
            "tipoBoletim": "Fechamento",
        },
    ]
}

PTAX_EMPTY_RESPONSE = {"value": []}


# ---------------------------------------------------------------------------
# Date format tests
# ---------------------------------------------------------------------------


class TestDateFormat:
    """Tests for the critical MM-DD-YYYY date format."""

    def test_date_format_produces_correct_api_params(self):
        """strftime('%m-%d-%Y') must produce MM-DD-YYYY format."""
        d = date(2025, 1, 15)
        formatted = d.strftime("%m-%d-%Y")
        assert formatted == "01-15-2025"

    def test_date_format_not_dd_mm_yyyy(self):
        """PTAX API requires MM-DD-YYYY, not DD-MM-YYYY."""
        d = date(2025, 3, 15)
        formatted = d.strftime("%m-%d-%Y")
        # MM-DD-YYYY: 03-15-2025 (not 15-03-2025)
        assert formatted == "03-15-2025"
        assert formatted != "15-03-2025"

    def test_date_format_not_iso(self):
        """PTAX API requires MM-DD-YYYY, not YYYY-MM-DD."""
        d = date(2025, 6, 30)
        formatted = d.strftime("%m-%d-%Y")
        assert formatted == "06-30-2025"
        assert formatted != "2025-06-30"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_period_uses_mm_dd_yyyy_format(self):
        """The request URL params must contain dates in MM-DD-YYYY format."""
        route = respx.get(
            url__startswith="https://olinda.bcb.gov.br/olinda/servico/PTAX/"
        ).mock(return_value=httpx.Response(200, json=PTAX_EMPTY_RESPONSE))

        async with BcbPtaxConnector() as connector:
            await connector.fetch_period(date(2025, 1, 15), date(2025, 1, 31))

        assert route.called
        request = route.calls.last.request
        url_str = str(request.url)
        # Verify MM-DD-YYYY format in params
        assert "01-15-2025" in url_str
        assert "01-31-2025" in url_str


# ---------------------------------------------------------------------------
# Closing bulletin filter tests
# ---------------------------------------------------------------------------


class TestClosingBulletinFilter:
    """Tests for tipoBoletim='Fechamento' filtering."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_period_filters_closing_bulletin(self, ptax_response):
        """Only closing bulletins should be returned."""
        respx.get(
            url__startswith="https://olinda.bcb.gov.br/olinda/servico/PTAX/"
        ).mock(return_value=httpx.Response(200, json=ptax_response))

        async with BcbPtaxConnector() as connector:
            records = await connector.fetch_period(date(2025, 1, 15), date(2025, 1, 16))

        # ptax_sample.json has 3 entries: 2 Fechamento + 1 Abertura
        assert len(records) == 2
        assert all(r["source"] == "BCB_PTAX" for r in records)

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_period_filters_closing_bulletin_inline_data(self):
        """Only 'Fechamento' bulletins should be kept from mixed response."""
        respx.get(
            url__startswith="https://olinda.bcb.gov.br/olinda/servico/PTAX/"
        ).mock(return_value=httpx.Response(200, json=PTAX_CLOSING_AND_OPENING))

        async with BcbPtaxConnector() as connector:
            records = await connector.fetch_period(date(2025, 1, 15), date(2025, 1, 16))

        # 3 entries: 2 Fechamento + 1 Abertura -> 2 records
        assert len(records) == 2


# ---------------------------------------------------------------------------
# Rate mapping tests
# ---------------------------------------------------------------------------


class TestRateMapping:
    """Tests for cotacaoCompra -> open, cotacaoVenda -> close mapping."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_period_parses_buy_sell_rates(self):
        """open must be cotacaoCompra (buy), close must be cotacaoVenda (sell)."""
        respx.get(
            url__startswith="https://olinda.bcb.gov.br/olinda/servico/PTAX/"
        ).mock(return_value=httpx.Response(200, json=PTAX_CLOSING_AND_OPENING))

        async with BcbPtaxConnector() as connector:
            records = await connector.fetch_period(date(2025, 1, 15), date(2025, 1, 16))

        # First closing bulletin
        rec0 = records[0]
        assert rec0["open"] == pytest.approx(5.7036)  # cotacaoCompra
        assert rec0["close"] == pytest.approx(5.7042)  # cotacaoVenda
        assert rec0["adjusted_close"] == pytest.approx(5.7042)

        # Second closing bulletin
        rec1 = records[1]
        assert rec1["open"] == pytest.approx(5.7150)
        assert rec1["close"] == pytest.approx(5.7160)

    @pytest.mark.asyncio
    @respx.mock
    async def test_high_low_volume_are_none(self):
        """PTAX only has buy/sell rates; high, low, volume must be None."""
        respx.get(
            url__startswith="https://olinda.bcb.gov.br/olinda/servico/PTAX/"
        ).mock(return_value=httpx.Response(200, json=PTAX_CLOSING_AND_OPENING))

        async with BcbPtaxConnector() as connector:
            records = await connector.fetch_period(date(2025, 1, 15), date(2025, 1, 16))

        for rec in records:
            assert rec["high"] is None
            assert rec["low"] is None
            assert rec["volume"] is None


# ---------------------------------------------------------------------------
# Timezone / release time tests
# ---------------------------------------------------------------------------


class TestTimezone:
    """Tests for dataHoraCotacao parsing with Sao Paulo timezone."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_period_sets_release_time_from_dataHoraCotacao(self):
        """timestamp must be parsed from dataHoraCotacao with SP timezone."""
        respx.get(
            url__startswith="https://olinda.bcb.gov.br/olinda/servico/PTAX/"
        ).mock(return_value=httpx.Response(200, json=PTAX_CLOSING_AND_OPENING))

        async with BcbPtaxConnector() as connector:
            records = await connector.fetch_period(date(2025, 1, 15), date(2025, 1, 16))

        ts = records[0]["timestamp"]
        assert isinstance(ts, datetime)
        assert ts.tzinfo is not None
        # Verify it's in Sao Paulo timezone
        assert str(ts.tzinfo) == "America/Sao_Paulo"
        assert ts.year == 2025
        assert ts.month == 1
        assert ts.day == 15
        assert ts.hour == 13
        assert ts.minute == 7


# ---------------------------------------------------------------------------
# Empty / edge case tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for empty responses and edge cases."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_period_handles_empty_response(self):
        """Empty response should return empty list, not raise."""
        respx.get(
            url__startswith="https://olinda.bcb.gov.br/olinda/servico/PTAX/"
        ).mock(return_value=httpx.Response(200, json=PTAX_EMPTY_RESPONSE))

        async with BcbPtaxConnector() as connector:
            records = await connector.fetch_period(date(2025, 1, 15), date(2025, 1, 16))

        assert records == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_chunks_multi_year_range(self):
        """fetch() should split multi-year ranges into chunks."""
        route = respx.get(
            url__startswith="https://olinda.bcb.gov.br/olinda/servico/PTAX/"
        ).mock(return_value=httpx.Response(200, json=PTAX_EMPTY_RESPONSE))

        async with BcbPtaxConnector() as connector:
            await connector.fetch(date(2023, 1, 1), date(2025, 6, 30))

        # 2023-01-01 to 2025-06-30 = ~2.5 years -> at least 3 API calls
        assert route.call_count >= 3

    def test_ticker_name_is_usdbrl_ptax(self):
        """The instrument ticker must be USDBRL_PTAX."""
        assert BcbPtaxConnector.TICKER_NAME == "USDBRL_PTAX"

    def test_source_name_is_bcb_ptax(self):
        """The source name must be BCB_PTAX."""
        assert BcbPtaxConnector.SOURCE_NAME == "BCB_PTAX"

    @pytest.mark.asyncio
    @respx.mock
    async def test_record_has_correct_metadata(self):
        """Each record must have correct _ticker, frequency, source."""
        respx.get(
            url__startswith="https://olinda.bcb.gov.br/olinda/servico/PTAX/"
        ).mock(return_value=httpx.Response(200, json=PTAX_CLOSING_AND_OPENING))

        async with BcbPtaxConnector() as connector:
            records = await connector.fetch_period(date(2025, 1, 15), date(2025, 1, 16))

        for rec in records:
            assert rec["_ticker"] == "USDBRL_PTAX"
            assert rec["frequency"] == "daily"
            assert rec["source"] == "BCB_PTAX"

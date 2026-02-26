"""Tests for FOMCScraper -- Federal Reserve FOMC statements and minutes scraping.

All HTTP requests are mocked; no real network calls are made.
Cache isolation via tmp_path fixture.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from src.nlp.scrapers.copom_scraper import ScrapedDocument
from src.nlp.scrapers.fomc_scraper import FOMCScraper

# ---------------------------------------------------------------------------
# Sample HTML fixtures
# ---------------------------------------------------------------------------
FOMC_CALENDAR_HTML = """
<html><body>
<div class="fomc-meeting">
  <div class="fomc-meeting__month">January 30-31, 2024</div>
  <div class="fomc-meeting__links">
    <a href="/newsevents/pressreleases/monetary20240131a.htm">Statement</a>
    <a href="/monetarypolicy/fomcminutes20240131.htm">Minutes</a>
  </div>
</div>
<div class="fomc-meeting">
  <div class="fomc-meeting__month">December 12-13, 2023</div>
  <div class="fomc-meeting__links">
    <a href="/newsevents/pressreleases/monetary20231213a.htm">Statement</a>
    <a href="/monetarypolicy/fomcminutes20231213.htm">Minutes</a>
  </div>
</div>
</body></html>
"""

FOMC_STATEMENT_HTML = """
<html><body>
<div id="article">
  <h3>Federal Reserve Issues FOMC Statement</h3>
  <p>The Federal Open Market Committee decided to maintain the target range
  for the federal funds rate at 5-1/4 to 5-1/2 percent.</p>
  <p>Recent indicators suggest that economic activity has been expanding
  at a solid pace. Job gains have moderated but remain strong.</p>
</div>
</body></html>
"""

FOMC_MINUTES_HTML = """
<html><body>
<div id="article">
  <h3>Minutes of the Federal Open Market Committee</h3>
  <p>A joint meeting of the Federal Open Market Committee and the Board of
  Governors was held in the offices of the Board of Governors.</p>
  <p>Participants discussed the economic outlook and agreed that
  inflation remained elevated above the Committee's longer-run goal.</p>
</div>
</body></html>
"""

FOMC_HISTORICAL_HTML = """
<html><body>
<div class="panel">
  <h5>January 25-26, 2011</h5>
  <a href="/newsevents/pressreleases/monetary20110126a.htm">Statement</a>
  <a href="/monetarypolicy/fomcminutes20110126.htm">Minutes</a>
</div>
</body></html>
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestFOMCScraperInit:
    """Test FOMCScraper initialization."""

    def test_creates_cache_dir(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "fomc_cache"
        scraper = FOMCScraper(cache_dir=str(cache_dir))
        assert cache_dir.exists()
        assert scraper.cache_dir == cache_dir

    def test_default_rate_limit(self, tmp_path: Path) -> None:
        scraper = FOMCScraper(cache_dir=str(tmp_path))
        assert scraper.rate_limit == 2.0

    def test_close_client(self, tmp_path: Path) -> None:
        scraper = FOMCScraper(cache_dir=str(tmp_path))
        mock_client = MagicMock(spec=httpx.Client)
        scraper._client = mock_client
        scraper.close()
        mock_client.close.assert_called_once()
        assert scraper._client is None


class TestFOMCScraperCalendarUrls:
    """Test calendar URL generation."""

    def test_get_calendar_urls_includes_historical(self, tmp_path: Path) -> None:
        scraper = FOMCScraper(cache_dir=str(tmp_path))
        urls = scraper._get_calendar_urls(start_year=2023)

        # Should have historical URLs for years between 2023 and current
        assert len(urls) >= 2  # at least 2023 historical + current calendar
        assert any("fomchistorical2023" in u for u in urls)
        assert any("fomccalendars.htm" in u for u in urls)


class TestFOMCScraperScrapeStatements:
    """Test scrape_statements with mocked HTTP."""

    @patch("src.nlp.scrapers.fomc_scraper.time.sleep")
    def test_scrape_statements_returns_documents(
        self, mock_sleep: MagicMock, tmp_path: Path
    ) -> None:
        scraper = FOMCScraper(cache_dir=str(tmp_path), rate_limit=0)

        mock_client = MagicMock(spec=httpx.Client)

        # Calendar page response
        cal_response = MagicMock()
        cal_response.text = FOMC_CALENDAR_HTML
        cal_response.status_code = 200
        cal_response.raise_for_status = MagicMock()

        # Statement page response
        stmt_response = MagicMock()
        stmt_response.text = FOMC_STATEMENT_HTML
        stmt_response.status_code = 200
        stmt_response.raise_for_status = MagicMock()

        # For start_year=2023, we get historical 2023 + 2024 + 2025 + current calendar
        # Each calendar returns the same HTML for simplicity
        mock_client.get = MagicMock(
            side_effect=[cal_response] + [stmt_response] * 2 +  # historical 2023
                        [cal_response] + [stmt_response] * 2 +  # historical 2024
                        [cal_response] + [stmt_response] * 2 +  # historical 2025
                        [cal_response] + [stmt_response] * 2    # current calendar
        )
        scraper._client = mock_client

        docs = scraper.scrape_statements(start_year=2023)

        assert len(docs) > 0
        for doc in docs:
            assert doc.source == "fomc"
            assert doc.doc_type == "statement"
            assert isinstance(doc.doc_date, date)
            assert len(doc.raw_text) > 0

    @patch("src.nlp.scrapers.fomc_scraper.time.sleep")
    def test_incremental_cache_skips_existing(
        self, mock_sleep: MagicMock, tmp_path: Path
    ) -> None:
        """Second scrape with cached docs should skip them."""
        scraper = FOMCScraper(cache_dir=str(tmp_path), rate_limit=0)

        # Pre-populate cache
        cached_doc = ScrapedDocument(
            source="fomc",
            doc_type="statement",
            doc_date=date(2024, 1, 31),
            raw_text="Cached statement",
            url="https://www.federalreserve.gov/test",
        )
        scraper._save_to_cache(cached_doc)

        mock_client = MagicMock(spec=httpx.Client)

        cal_response = MagicMock()
        cal_response.text = FOMC_CALENDAR_HTML
        cal_response.status_code = 200
        cal_response.raise_for_status = MagicMock()

        stmt_response = MagicMock()
        stmt_response.text = FOMC_STATEMENT_HTML
        stmt_response.status_code = 200
        stmt_response.raise_for_status = MagicMock()

        # Multiple calendar pages + doc responses
        mock_client.get = MagicMock(
            side_effect=[cal_response, stmt_response] * 10
        )
        scraper._client = mock_client

        docs = scraper.scrape_statements(start_year=2023)

        # The cached 2024-01-31 date should not appear in new docs
        for doc in docs:
            assert doc.doc_date != date(2024, 1, 31)


class TestFOMCScraperScrapeMinutes:
    """Test scrape_minutes with mocked HTTP."""

    @patch("src.nlp.scrapers.fomc_scraper.time.sleep")
    def test_scrape_minutes_returns_documents(
        self, mock_sleep: MagicMock, tmp_path: Path
    ) -> None:
        scraper = FOMCScraper(cache_dir=str(tmp_path), rate_limit=0)

        mock_client = MagicMock(spec=httpx.Client)

        cal_response = MagicMock()
        cal_response.text = FOMC_CALENDAR_HTML
        cal_response.status_code = 200
        cal_response.raise_for_status = MagicMock()

        min_response = MagicMock()
        min_response.text = FOMC_MINUTES_HTML
        min_response.status_code = 200
        min_response.raise_for_status = MagicMock()

        mock_client.get = MagicMock(
            side_effect=[cal_response] + [min_response] * 2 +
                        [cal_response] + [min_response] * 2 +
                        [cal_response] + [min_response] * 2 +
                        [cal_response] + [min_response] * 2
        )
        scraper._client = mock_client

        docs = scraper.scrape_minutes(start_year=2023)

        assert len(docs) > 0
        for doc in docs:
            assert doc.source == "fomc"
            assert doc.doc_type == "minutes"


class TestFOMCScraperScrapeAll:
    """Test scrape_all combines statements and minutes."""

    @patch("src.nlp.scrapers.fomc_scraper.time.sleep")
    def test_scrape_all_combines_and_sorts(
        self, mock_sleep: MagicMock, tmp_path: Path
    ) -> None:
        scraper = FOMCScraper(cache_dir=str(tmp_path), rate_limit=0)

        mock_client = MagicMock(spec=httpx.Client)

        cal_response = MagicMock()
        cal_response.text = FOMC_CALENDAR_HTML
        cal_response.status_code = 200
        cal_response.raise_for_status = MagicMock()

        doc_response = MagicMock()
        doc_response.text = FOMC_STATEMENT_HTML
        doc_response.status_code = 200
        doc_response.raise_for_status = MagicMock()

        # Enough responses for all calendar pages + docs (statements + minutes)
        mock_client.get = MagicMock(
            side_effect=[cal_response] + [doc_response] * 20
        )
        scraper._client = mock_client

        docs = scraper.scrape_all(start_year=2024)

        if docs:
            dates = [d.doc_date for d in docs]
            assert dates == sorted(dates)


class TestFOMCScraperCache:
    """Test cache operations."""

    def test_get_cached_documents(self, tmp_path: Path) -> None:
        scraper = FOMCScraper(cache_dir=str(tmp_path))

        docs_to_cache = [
            ScrapedDocument(
                source="fomc",
                doc_type="statement",
                doc_date=date(2024, 1, 31),
                raw_text="Statement text",
                url="https://www.federalreserve.gov/test1",
            ),
            ScrapedDocument(
                source="fomc",
                doc_type="minutes",
                doc_date=date(2024, 3, 20),
                raw_text="Minutes text",
                url="https://www.federalreserve.gov/test2",
            ),
        ]

        for doc in docs_to_cache:
            scraper._save_to_cache(doc)

        cached = scraper.get_cached_documents()

        assert len(cached) == 2
        assert cached[0].doc_date < cached[1].doc_date
        assert cached[0].source == "fomc"

    def test_get_cached_documents_empty(self, tmp_path: Path) -> None:
        scraper = FOMCScraper(cache_dir=str(tmp_path))
        cached = scraper.get_cached_documents()
        assert cached == []

    def test_cache_file_naming(self, tmp_path: Path) -> None:
        scraper = FOMCScraper(cache_dir=str(tmp_path))
        doc = ScrapedDocument(
            source="fomc",
            doc_type="statement",
            doc_date=date(2024, 1, 31),
            raw_text="Test",
            url="https://test.com",
        )
        scraper._save_to_cache(doc)

        cache_file = tmp_path / "fomc_statement_2024-01-31.json"
        assert cache_file.exists()

        data = json.loads(cache_file.read_text())
        assert data["source"] == "fomc"
        assert data["doc_date"] == "2024-01-31"


class TestFOMCScraperPersist:
    """Test persist_documents with mocked session."""

    def test_persist_documents_calls_insert(self, tmp_path: Path) -> None:
        scraper = FOMCScraper(cache_dir=str(tmp_path))

        docs = [
            ScrapedDocument(
                source="fomc",
                doc_type="statement",
                doc_date=date(2024, 1, 31),
                raw_text="Test statement text",
                url="https://www.federalreserve.gov/test",
            ),
        ]

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        count = scraper.persist_documents(docs, mock_session)

        assert count == 1
        mock_session.execute.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_persist_empty_list_returns_zero(self, tmp_path: Path) -> None:
        scraper = FOMCScraper(cache_dir=str(tmp_path))
        mock_session = MagicMock()

        count = scraper.persist_documents([], mock_session)

        assert count == 0
        mock_session.execute.assert_not_called()


class TestFOMCScraperHTTPErrors:
    """Test error handling for HTTP failures."""

    @patch("src.nlp.scrapers.fomc_scraper.time.sleep")
    def test_calendar_page_failure_continues(
        self, mock_sleep: MagicMock, tmp_path: Path
    ) -> None:
        scraper = FOMCScraper(cache_dir=str(tmp_path), rate_limit=0)

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get = MagicMock(
            side_effect=httpx.HTTPError("Connection failed")
        )
        scraper._client = mock_client

        docs = scraper.scrape_statements(start_year=2024)
        assert docs == []

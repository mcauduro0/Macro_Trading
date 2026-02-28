"""Tests for COPOMScraper -- BCB COPOM atas and comunicados scraping.

All HTTP requests are mocked; no real network calls are made.
Cache isolation via tmp_path fixture.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from src.nlp.scrapers.copom_scraper import (
    COPOMScraper,
    ScrapedDocument,
    _extract_text_from_html,
)

# ---------------------------------------------------------------------------
# Sample HTML fixtures
# ---------------------------------------------------------------------------
COPOM_INDEX_HTML = """
<html><body>
<div class="conteudo">
  <ul>
    <li><a href="/publicacoes/atascopom/20240131">Ata 265 - 31/01/2024</a></li>
    <li><a href="/publicacoes/atascopom/20231213">Ata 264 - 13/12/2023</a></li>
    <li><a href="/publicacoes/atascopom/20231101">Ata 263 - 01/11/2023</a></li>
  </ul>
</div>
</body></html>
"""

COPOM_DOC_HTML = """
<html><body>
<nav>Navigation should be stripped</nav>
<div id="conteudo">
  <h2>Ata da 265a Reuniao do Copom</h2>
  <p>O Comite de Politica Monetaria decidiu, por unanimidade, elevar a taxa Selic
  em 0,25 ponto percentual, para 11,25% a.a.</p>
  <p>A inflacao corrente permanece acima da meta e as expectativas seguem
  desancoradas para os proximos anos.</p>
</div>
<footer>Footer should be stripped</footer>
</body></html>
"""

COPOM_COMUNICADO_INDEX_HTML = """
<html><body>
<div class="conteudo">
  <ul>
    <li><a href="/publicacoes/comunicadoscopom/20240131">Comunicado 265 - 31/01/2024</a></li>
    <li><a href="/publicacoes/comunicadoscopom/20231213">Comunicado 264 - 13/12/2023</a></li>
  </ul>
</div>
</body></html>
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestExtractTextFromHtml:
    """Test the HTML text extraction utility."""

    def test_strips_html_tags(self) -> None:
        html = "<p>Hello <b>world</b></p>"
        assert _extract_text_from_html(html) == "Hello world"

    def test_strips_nav_and_footer(self) -> None:
        html = "<nav>Menu</nav><p>Content</p><footer>Footer</footer>"
        text = _extract_text_from_html(html)
        assert "Menu" not in text
        assert "Footer" not in text
        assert "Content" in text

    def test_normalizes_whitespace(self) -> None:
        html = "<p>Hello    \n\n   world</p>"
        assert _extract_text_from_html(html) == "Hello world"


class TestScrapedDocument:
    """Test the ScrapedDocument dataclass."""

    def test_to_dict(self) -> None:
        doc = ScrapedDocument(
            source="copom",
            doc_type="ata",
            doc_date=date(2024, 1, 31),
            raw_text="Test text",
            url="https://example.com/test",
        )
        d = doc.to_dict()
        assert d["source"] == "copom"
        assert d["doc_type"] == "ata"
        assert d["doc_date"] == date(2024, 1, 31)
        assert d["raw_text"] == "Test text"
        assert d["url"] == "https://example.com/test"


class TestCOPOMScraperInit:
    """Test COPOMScraper initialization."""

    def test_creates_cache_dir(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "test_cache"
        scraper = COPOMScraper(cache_dir=str(cache_dir))
        assert cache_dir.exists()
        assert scraper.cache_dir == cache_dir

    def test_default_rate_limit(self, tmp_path: Path) -> None:
        scraper = COPOMScraper(cache_dir=str(tmp_path))
        assert scraper.rate_limit == 2.0


class TestCOPOMScraperScrapeAtas:
    """Test scrape_atas with mocked HTTP."""

    @patch("src.nlp.scrapers.copom_scraper.time.sleep")
    def test_scrape_atas_returns_documents(
        self, mock_sleep: MagicMock, tmp_path: Path
    ) -> None:
        scraper = COPOMScraper(cache_dir=str(tmp_path), rate_limit=0)

        # Mock HTTP responses
        mock_client = MagicMock(spec=httpx.Client)

        # Index page response
        index_response = MagicMock()
        index_response.text = COPOM_INDEX_HTML
        index_response.status_code = 200
        index_response.raise_for_status = MagicMock()

        # Document page response
        doc_response = MagicMock()
        doc_response.text = COPOM_DOC_HTML
        doc_response.status_code = 200
        doc_response.raise_for_status = MagicMock()

        mock_client.get = MagicMock(
            side_effect=[index_response, doc_response, doc_response, doc_response]
        )

        scraper._client = mock_client

        docs = scraper.scrape_atas(start_year=2023)

        assert len(docs) > 0
        for doc in docs:
            assert doc.source == "copom"
            assert doc.doc_type == "ata"
            assert isinstance(doc.doc_date, date)
            assert doc.doc_date.year >= 2023
            assert len(doc.raw_text) > 0
            assert doc.url.startswith("https://")

    @patch("src.nlp.scrapers.copom_scraper.time.sleep")
    def test_incremental_cache_skips_existing(
        self, mock_sleep: MagicMock, tmp_path: Path
    ) -> None:
        """Second scrape with same cache should not re-fetch cached documents."""
        scraper = COPOMScraper(cache_dir=str(tmp_path), rate_limit=0)

        # Pre-populate cache with one document
        cached_doc = ScrapedDocument(
            source="copom",
            doc_type="ata",
            doc_date=date(2024, 1, 31),
            raw_text="Cached ata text",
            url="https://www.bcb.gov.br/publicacoes/atascopom/20240131",
        )
        scraper._save_to_cache(cached_doc)

        # Mock HTTP -- only index page should be fetched
        mock_client = MagicMock(spec=httpx.Client)
        index_response = MagicMock()
        index_response.text = COPOM_INDEX_HTML
        index_response.status_code = 200
        index_response.raise_for_status = MagicMock()

        doc_response = MagicMock()
        doc_response.text = COPOM_DOC_HTML
        doc_response.status_code = 200
        doc_response.raise_for_status = MagicMock()

        mock_client.get = MagicMock(
            side_effect=[index_response, doc_response, doc_response]
        )
        scraper._client = mock_client

        docs = scraper.scrape_atas(start_year=2023)

        # The cached doc (2024-01-31) should be skipped
        for doc in docs:
            assert doc.doc_date != date(2024, 1, 31)


class TestCOPOMScraperScrapeAll:
    """Test scrape_all combines atas and comunicados."""

    @patch("src.nlp.scrapers.copom_scraper.time.sleep")
    def test_scrape_all_combines_and_sorts(
        self, mock_sleep: MagicMock, tmp_path: Path
    ) -> None:
        scraper = COPOMScraper(cache_dir=str(tmp_path), rate_limit=0)

        mock_client = MagicMock(spec=httpx.Client)

        # Two index page responses (atas + comunicados) + doc pages
        ata_index = MagicMock()
        ata_index.text = COPOM_INDEX_HTML
        ata_index.status_code = 200
        ata_index.raise_for_status = MagicMock()

        com_index = MagicMock()
        com_index.text = COPOM_COMUNICADO_INDEX_HTML
        com_index.status_code = 200
        com_index.raise_for_status = MagicMock()

        doc_resp = MagicMock()
        doc_resp.text = COPOM_DOC_HTML
        doc_resp.status_code = 200
        doc_resp.raise_for_status = MagicMock()

        # Index for atas + 3 doc pages + index for comunicados + 2 doc pages
        mock_client.get = MagicMock(
            side_effect=[ata_index] + [doc_resp] * 3 + [com_index] + [doc_resp] * 2
        )
        scraper._client = mock_client

        docs = scraper.scrape_all(start_year=2023)

        # Should have docs from both atas and comunicados
        assert len(docs) > 0
        # Verify sorted by date
        dates = [d.doc_date for d in docs]
        assert dates == sorted(dates)


class TestCOPOMScraperCache:
    """Test cache loading functionality."""

    def test_get_cached_documents(self, tmp_path: Path) -> None:
        scraper = COPOMScraper(cache_dir=str(tmp_path))

        # Save some documents to cache
        docs_to_cache = [
            ScrapedDocument(
                source="copom",
                doc_type="ata",
                doc_date=date(2024, 1, 31),
                raw_text="Ata text 1",
                url="https://www.bcb.gov.br/test1",
            ),
            ScrapedDocument(
                source="copom",
                doc_type="comunicado",
                doc_date=date(2024, 3, 20),
                raw_text="Comunicado text 1",
                url="https://www.bcb.gov.br/test2",
            ),
        ]

        for doc in docs_to_cache:
            scraper._save_to_cache(doc)

        # Load from cache
        cached = scraper.get_cached_documents()

        assert len(cached) == 2
        assert cached[0].doc_date < cached[1].doc_date  # sorted
        assert cached[0].source == "copom"
        assert cached[0].raw_text == "Ata text 1"

    def test_get_cached_documents_empty_cache(self, tmp_path: Path) -> None:
        scraper = COPOMScraper(cache_dir=str(tmp_path))
        cached = scraper.get_cached_documents()
        assert cached == []

    def test_cache_file_format(self, tmp_path: Path) -> None:
        scraper = COPOMScraper(cache_dir=str(tmp_path))
        doc = ScrapedDocument(
            source="copom",
            doc_type="ata",
            doc_date=date(2024, 1, 31),
            raw_text="Test",
            url="https://test.com",
        )
        scraper._save_to_cache(doc)

        cache_file = tmp_path / "copom_ata_2024-01-31.json"
        assert cache_file.exists()

        data = json.loads(cache_file.read_text())
        assert data["source"] == "copom"
        assert data["doc_date"] == "2024-01-31"


class TestCOPOMScraperPersist:
    """Test persist_documents with mocked session."""

    def test_persist_documents_calls_insert(self, tmp_path: Path) -> None:
        scraper = COPOMScraper(cache_dir=str(tmp_path))

        docs = [
            ScrapedDocument(
                source="copom",
                doc_type="ata",
                doc_date=date(2024, 1, 31),
                raw_text="Test ata text",
                url="https://www.bcb.gov.br/test",
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
        scraper = COPOMScraper(cache_dir=str(tmp_path))
        mock_session = MagicMock()

        count = scraper.persist_documents([], mock_session)

        assert count == 0
        mock_session.execute.assert_not_called()


class TestCOPOMScraperHTTPErrors:
    """Test error handling for HTTP failures."""

    @patch("src.nlp.scrapers.copom_scraper.time.sleep")
    def test_index_page_failure_returns_empty(
        self, mock_sleep: MagicMock, tmp_path: Path
    ) -> None:
        scraper = COPOMScraper(cache_dir=str(tmp_path), rate_limit=0)

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get = MagicMock(side_effect=httpx.HTTPError("Connection failed"))
        scraper._client = mock_client

        docs = scraper.scrape_atas(start_year=2023)
        assert docs == []

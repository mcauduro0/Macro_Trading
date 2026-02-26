"""COPOMScraper for Brazilian Central Bank (BCB) communications.

Retrieves COPOM atas (minutes) and comunicados (post-meeting statements)
from bcb.gov.br with incremental caching. First run scrapes all documents
from start_year onwards; subsequent runs only fetch new documents.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.core.models.nlp_documents import NlpDocumentRecord

logger = logging.getLogger(__name__)


@dataclass
class ScrapedDocument:
    """Represents a scraped central bank document."""

    source: str
    doc_type: str
    doc_date: date
    raw_text: str
    url: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict suitable for DB insertion."""
        return {
            "source": self.source,
            "doc_type": self.doc_type,
            "doc_date": self.doc_date,
            "raw_text": self.raw_text,
            "url": self.url,
        }


class _TextExtractor(HTMLParser):
    """Simple HTML-to-text extractor using stdlib html.parser."""

    def __init__(self) -> None:
        super().__init__()
        self._text_parts: list[str] = []
        self._skip = False
        self._skip_tags = {"script", "style", "nav", "header", "footer"}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self._skip_tags:
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._skip_tags:
            self._skip = False

    def handle_data(self, data: str) -> None:
        if not self._skip:
            stripped = data.strip()
            if stripped:
                self._text_parts.append(stripped)

    def get_text(self) -> str:
        return " ".join(self._text_parts)


def _extract_text_from_html(html: str) -> str:
    """Extract readable text from HTML, stripping tags and normalizing whitespace."""
    parser = _TextExtractor()
    parser.feed(html)
    text = parser.get_text()
    # Normalize multiple spaces/newlines
    text = re.sub(r"\s+", " ", text).strip()
    return text


class COPOMScraper:
    """Scraper for BCB COPOM atas and comunicados.

    Uses httpx for HTTP requests with incremental caching:
    - First run scrapes all documents from start_year onwards
    - Subsequent runs check cache and only fetch new documents

    Args:
        cache_dir: Directory for cached document JSON files.
        rate_limit: Seconds to wait between HTTP requests.
    """

    BASE_URL = "https://www.bcb.gov.br"
    ATAS_PATH = "/publicacoes/atascopom"
    COMUNICADOS_PATH = "/publicacoes/comunicadoscopom"
    USER_AGENT = "MacroTradingSystem/1.0"

    def __init__(
        self,
        cache_dir: str = ".cache/nlp/copom",
        rate_limit: float = 2.0,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.rate_limit = rate_limit
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                headers={"User-Agent": self.USER_AGENT},
                timeout=httpx.Timeout(30.0),
                follow_redirects=True,
            )
        return self._client

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def _cache_key(self, source: str, doc_type: str, doc_date: date) -> str:
        """Generate cache filename."""
        return f"{source}_{doc_type}_{doc_date.isoformat()}.json"

    def _is_cached(self, source: str, doc_type: str, doc_date: date) -> bool:
        """Check if a document is already cached."""
        cache_file = self.cache_dir / self._cache_key(source, doc_type, doc_date)
        return cache_file.exists()

    def _save_to_cache(self, doc: ScrapedDocument) -> None:
        """Save a scraped document to the local cache."""
        cache_file = self.cache_dir / self._cache_key(
            doc.source, doc.doc_type, doc.doc_date
        )
        data = asdict(doc)
        data["doc_date"] = doc.doc_date.isoformat()
        cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def _load_from_cache(self, filepath: Path) -> ScrapedDocument:
        """Load a ScrapedDocument from a cache file."""
        data = json.loads(filepath.read_text(encoding="utf-8"))
        data["doc_date"] = date.fromisoformat(data["doc_date"])
        return ScrapedDocument(**data)

    def _get_cached_dates(self, doc_type: str) -> set[date]:
        """Get the set of dates already cached for a doc_type."""
        dates: set[date] = set()
        pattern = f"copom_{doc_type}_*.json"
        for filepath in self.cache_dir.glob(pattern):
            try:
                # Extract date from filename: copom_{doc_type}_{YYYY-MM-DD}.json
                date_str = filepath.stem.split("_", 2)[-1]
                dates.add(date.fromisoformat(date_str))
            except (ValueError, IndexError):
                continue
        return dates

    def _parse_index_page(
        self, html: str, doc_type: str, start_year: int
    ) -> list[dict[str, Any]]:
        """Parse BCB index page to extract document links and dates.

        Returns list of dicts with keys: url, date, doc_type.
        BCB pages list documents with links containing dates.
        """
        documents: list[dict[str, Any]] = []

        # BCB pages use links like /publicacoes/atascopom/NNNN
        # and display dates in various formats
        # Pattern: look for links with year-based URLs
        link_pattern = re.compile(
            r'href="([^"]*(?:ata|comunicado|copom)[^"]*)"',
            re.IGNORECASE,
        )
        date_pattern = re.compile(
            r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})"
        )

        # Also try ISO date pattern
        iso_date_pattern = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

        links_found = link_pattern.findall(html)
        dates_found = date_pattern.findall(html)
        iso_dates_found = iso_date_pattern.findall(html)

        # Parse dates from page content
        parsed_dates: list[date] = []
        for day, month, year in dates_found:
            try:
                d = date(int(year), int(month), int(day))
                if d.year >= start_year:
                    parsed_dates.append(d)
            except ValueError:
                continue

        for year, month, day in iso_dates_found:
            try:
                d = date(int(year), int(month), int(day))
                if d.year >= start_year:
                    parsed_dates.append(d)
            except ValueError:
                continue

        # Build document list from links and associate with nearest date
        for link in links_found:
            full_url = link if link.startswith("http") else f"{self.BASE_URL}{link}"
            # Try to extract date from URL
            url_date_match = re.search(r"(\d{4})[-/]?(\d{2})[-/]?(\d{2})", link)
            if url_date_match:
                try:
                    d = date(
                        int(url_date_match.group(1)),
                        int(url_date_match.group(2)),
                        int(url_date_match.group(3)),
                    )
                    if d.year >= start_year:
                        documents.append({
                            "url": full_url,
                            "date": d,
                            "doc_type": doc_type,
                        })
                except ValueError:
                    continue

        # If no date-embedded links, match links with parsed dates
        if not documents and links_found and parsed_dates:
            for i, link in enumerate(links_found):
                if i < len(parsed_dates):
                    full_url = (
                        link if link.startswith("http") else f"{self.BASE_URL}{link}"
                    )
                    documents.append({
                        "url": full_url,
                        "date": parsed_dates[i],
                        "doc_type": doc_type,
                    })

        return documents

    def scrape_atas(self, start_year: int = 2010) -> list[ScrapedDocument]:
        """Scrape COPOM atas (minutes) from BCB.

        Args:
            start_year: Earliest year to scrape from.

        Returns:
            List of newly scraped documents (excludes already-cached ones).
        """
        return self._scrape_doc_type("ata", self.ATAS_PATH, start_year)

    def scrape_comunicados(self, start_year: int = 2010) -> list[ScrapedDocument]:
        """Scrape COPOM comunicados (post-meeting statements) from BCB.

        Args:
            start_year: Earliest year to scrape from.

        Returns:
            List of newly scraped documents (excludes already-cached ones).
        """
        return self._scrape_doc_type("comunicado", self.COMUNICADOS_PATH, start_year)

    def _scrape_doc_type(
        self, doc_type: str, path: str, start_year: int
    ) -> list[ScrapedDocument]:
        """Common scraping logic for a document type.

        Args:
            doc_type: Type identifier ("ata" or "comunicado").
            path: URL path on BCB site.
            start_year: Earliest year to include.

        Returns:
            List of newly scraped documents.
        """
        client = self._get_client()
        cached_dates = self._get_cached_dates(doc_type)
        new_docs: list[ScrapedDocument] = []

        try:
            # Fetch index page
            index_url = f"{self.BASE_URL}{path}"
            response = client.get(index_url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "Failed to fetch COPOM %s index: %s", doc_type, exc
            )
            return new_docs

        # Parse document links
        doc_entries = self._parse_index_page(response.text, doc_type, start_year)

        for entry in doc_entries:
            doc_date = entry["date"]

            # Skip if already cached (incremental)
            if doc_date in cached_dates:
                logger.debug("Skipping cached %s %s", doc_type, doc_date)
                continue

            # Rate limit
            time.sleep(self.rate_limit)

            try:
                doc_response = client.get(entry["url"])
                doc_response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning(
                    "Failed to fetch %s %s: %s",
                    doc_type,
                    doc_date,
                    exc,
                )
                continue

            raw_text = _extract_text_from_html(doc_response.text)
            if not raw_text:
                logger.warning(
                    "Empty text extracted for %s %s, skipping",
                    doc_type,
                    doc_date,
                )
                continue

            doc = ScrapedDocument(
                source="copom",
                doc_type=doc_type,
                doc_date=doc_date,
                raw_text=raw_text,
                url=entry["url"],
            )
            self._save_to_cache(doc)
            new_docs.append(doc)

        return new_docs

    def scrape_all(self, start_year: int = 2010) -> list[ScrapedDocument]:
        """Scrape all COPOM documents (atas + comunicados).

        Args:
            start_year: Earliest year to scrape from.

        Returns:
            Combined list sorted by date.
        """
        atas = self.scrape_atas(start_year)
        comunicados = self.scrape_comunicados(start_year)
        combined = atas + comunicados
        combined.sort(key=lambda d: d.doc_date)
        return combined

    def get_cached_documents(self) -> list[ScrapedDocument]:
        """Load all cached documents without making HTTP requests.

        Returns:
            List of all cached ScrapedDocument objects sorted by date.
        """
        docs: list[ScrapedDocument] = []
        for filepath in self.cache_dir.glob("copom_*.json"):
            try:
                doc = self._load_from_cache(filepath)
                docs.append(doc)
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                logger.warning("Failed to load cache file %s: %s", filepath, exc)
                continue
        docs.sort(key=lambda d: d.doc_date)
        return docs

    def persist_documents(
        self,
        documents: list[ScrapedDocument],
        session: Any,
    ) -> int:
        """Persist scraped documents to the nlp_documents table.

        Uses ON CONFLICT DO NOTHING for idempotent insertion.

        Args:
            documents: List of scraped documents to persist.
            session: SQLAlchemy session (sync or async).

        Returns:
            Number of new documents inserted.
        """
        if not documents:
            return 0

        records = [doc.to_dict() for doc in documents]
        stmt = pg_insert(NlpDocumentRecord).values(records)
        stmt = stmt.on_conflict_do_nothing(
            constraint="uq_nlp_documents_natural_key"
        )
        result = session.execute(stmt)
        session.flush()
        return result.rowcount

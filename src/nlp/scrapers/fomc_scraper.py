"""FOMCScraper for Federal Reserve communications.

Retrieves FOMC statements and minutes from federalreserve.gov with
incremental caching. First run scrapes all documents from start_year
onwards; subsequent runs only fetch new documents.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.core.models.nlp_documents import NlpDocumentRecord
from src.nlp.scrapers.copom_scraper import (
    ScrapedDocument,
    _extract_text_from_html,
)

logger = logging.getLogger(__name__)


class FOMCScraper:
    """Scraper for Federal Reserve FOMC statements and minutes.

    Uses httpx for HTTP requests with incremental caching:
    - First run scrapes all documents from start_year onwards
    - Subsequent runs check cache and only fetch new documents

    Args:
        cache_dir: Directory for cached document JSON files.
        rate_limit: Seconds to wait between HTTP requests.
    """

    BASE_URL = "https://www.federalreserve.gov"
    CALENDAR_PATH = "/monetarypolicy/fomccalendars.htm"
    HISTORICAL_PATH_TEMPLATE = "/monetarypolicy/fomchistorical{year}.htm"
    USER_AGENT = "MacroTradingSystem/1.0"

    def __init__(
        self,
        cache_dir: str = ".cache/nlp/fomc",
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
        pattern = f"fomc_{doc_type}_*.json"
        for filepath in self.cache_dir.glob(pattern):
            try:
                date_str = filepath.stem.split("_", 2)[-1]
                dates.add(date.fromisoformat(date_str))
            except (ValueError, IndexError):
                continue
        return dates

    def _get_calendar_urls(self, start_year: int) -> list[str]:
        """Get all calendar page URLs to scrape.

        Current year uses the main calendar page; historical years use
        year-specific URLs.
        """
        current_year = date.today().year
        urls: list[str] = []

        # Historical pages for past years
        for year in range(start_year, current_year):
            urls.append(
                f"{self.BASE_URL}"
                f"{self.HISTORICAL_PATH_TEMPLATE.format(year=year)}"
            )

        # Current year calendar
        urls.append(f"{self.BASE_URL}{self.CALENDAR_PATH}")

        return urls

    def _parse_calendar_page(
        self, html: str, doc_type: str, start_year: int
    ) -> list[dict[str, Any]]:
        """Parse FOMC calendar/historical page to extract document links.

        Returns list of dicts with keys: url, date, doc_type.
        """
        documents: list[dict[str, Any]] = []

        # FOMC pages link to statements and minutes with patterns like:
        # /newsevents/pressreleases/monetary20240131a.htm (statement)
        # /monetarypolicy/fomcminutes20240131.htm (minutes)
        if doc_type == "statement":
            link_pattern = re.compile(
                r'href="([^"]*(?:monetary\d{8}|pressreleases/monetary)[^"]*\.htm)"',
                re.IGNORECASE,
            )
        else:  # minutes
            link_pattern = re.compile(
                r'href="([^"]*fomcminutes\d{8}[^"]*\.htm)"',
                re.IGNORECASE,
            )

        # Date pattern in FOMC URLs: YYYYMMDD
        url_date_pattern = re.compile(r"(\d{4})(\d{2})(\d{2})")

        links_found = link_pattern.findall(html)

        for link in links_found:
            url_date_match = url_date_pattern.search(link)
            if url_date_match:
                try:
                    d = date(
                        int(url_date_match.group(1)),
                        int(url_date_match.group(2)),
                        int(url_date_match.group(3)),
                    )
                    if d.year >= start_year:
                        full_url = (
                            link
                            if link.startswith("http")
                            else f"{self.BASE_URL}{link}"
                        )
                        documents.append({
                            "url": full_url,
                            "date": d,
                            "doc_type": doc_type,
                        })
                except ValueError:
                    continue

        # Deduplicate by date (some pages list same meeting multiple times)
        seen_dates: set[date] = set()
        unique_docs: list[dict[str, Any]] = []
        for doc in documents:
            if doc["date"] not in seen_dates:
                seen_dates.add(doc["date"])
                unique_docs.append(doc)

        return unique_docs

    def scrape_statements(self, start_year: int = 2010) -> list[ScrapedDocument]:
        """Scrape FOMC statements from the Federal Reserve.

        Args:
            start_year: Earliest year to scrape from.

        Returns:
            List of newly scraped statement documents.
        """
        return self._scrape_doc_type("statement", start_year)

    def scrape_minutes(self, start_year: int = 2010) -> list[ScrapedDocument]:
        """Scrape FOMC minutes from the Federal Reserve.

        Args:
            start_year: Earliest year to scrape from.

        Returns:
            List of newly scraped minutes documents.
        """
        return self._scrape_doc_type("minutes", start_year)

    def _scrape_doc_type(
        self, doc_type: str, start_year: int
    ) -> list[ScrapedDocument]:
        """Common scraping logic for a document type.

        Args:
            doc_type: Type identifier ("statement" or "minutes").
            start_year: Earliest year to include.

        Returns:
            List of newly scraped documents.
        """
        client = self._get_client()
        cached_dates = self._get_cached_dates(doc_type)
        new_docs: list[ScrapedDocument] = []

        calendar_urls = self._get_calendar_urls(start_year)

        for calendar_url in calendar_urls:
            try:
                response = client.get(calendar_url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning(
                    "Failed to fetch FOMC calendar %s: %s",
                    calendar_url,
                    exc,
                )
                continue

            # Rate limit between calendar pages
            time.sleep(self.rate_limit)

            doc_entries = self._parse_calendar_page(
                response.text, doc_type, start_year
            )

            for entry in doc_entries:
                doc_date = entry["date"]

                # Skip if already cached (incremental)
                if doc_date in cached_dates:
                    logger.debug("Skipping cached %s %s", doc_type, doc_date)
                    continue

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
                    source="fomc",
                    doc_type=doc_type,
                    doc_date=doc_date,
                    raw_text=raw_text,
                    url=entry["url"],
                )
                self._save_to_cache(doc)
                new_docs.append(doc)

        return new_docs

    def scrape_all(self, start_year: int = 2010) -> list[ScrapedDocument]:
        """Scrape all FOMC documents (statements + minutes).

        Args:
            start_year: Earliest year to scrape from.

        Returns:
            Combined list sorted by date.
        """
        statements = self.scrape_statements(start_year)
        minutes = self.scrape_minutes(start_year)
        combined = statements + minutes
        combined.sort(key=lambda d: d.doc_date)
        return combined

    def get_cached_documents(self) -> list[ScrapedDocument]:
        """Load all cached documents without making HTTP requests.

        Returns:
            List of all cached ScrapedDocument objects sorted by date.
        """
        docs: list[ScrapedDocument] = []
        for filepath in self.cache_dir.glob("fomc_*.json"):
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

"""NLPProcessor pipeline for central bank document analysis.

Orchestrates the full NLP workflow: clean -> score -> extract key phrases ->
compare vs previous -> persist results. Works with ScrapedDocument input
from COPOM and FOMC scrapers.
"""

from __future__ import annotations

import html
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import update

from src.core.models.nlp_documents import NlpDocumentRecord
from src.nlp.scrapers.copom_scraper import ScrapedDocument
from src.nlp.sentiment_analyzer import CentralBankSentimentAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class ProcessedDocument:
    """Result of processing a single central bank document.

    Attributes:
        source: Institution identifier ("copom" or "fomc").
        doc_type: Document type ("ata", "comunicado", "statement", "minutes").
        doc_date: Meeting or release date.
        cleaned_text: Normalized document text.
        hawk_score: Hawkish sentiment score [0, 1].
        dove_score: Dovish sentiment score [0, 1].
        net_score: Net sentiment [-1, +1], positive = hawkish.
        change_score: Categorical shift label vs previous document.
        key_phrases: Extracted key phrases with context.
        method: Scoring method ("dictionary" or "dictionary+llm").
    """

    source: str
    doc_type: str
    doc_date: date
    cleaned_text: str
    hawk_score: float
    dove_score: float
    net_score: float
    change_score: str
    key_phrases: list[str] = field(default_factory=list)
    method: str = "dictionary"


@dataclass
class PipelineResult:
    """Summary result of running the full NLP pipeline on a batch.

    Attributes:
        documents_processed: Number of documents successfully processed.
        documents_persisted: Number of documents persisted to database.
        errors: List of error messages for failed documents.
    """

    documents_processed: int = 0
    documents_persisted: int = 0
    errors: list[str] = field(default_factory=list)


class NLPProcessor:
    """Orchestrates the central bank document NLP pipeline.

    Pipeline steps per document:
    1. Clean: normalize text (strip HTML, normalize whitespace/encoding)
    2. Score: run CentralBankSentimentAnalyzer for hawk/dove scores
    3. Extract: pull key phrases from scored document
    4. Compare: compute change_score vs previous document
    5. Persist: update nlp_documents table with results

    Args:
        analyzer: Sentiment analyzer instance. Created if not provided.
        session_factory: Optional SQLAlchemy session factory for persistence.
    """

    # Source to language mapping
    _LANGUAGE_MAP: dict[str, str] = {
        "copom": "pt",
        "fomc": "en",
    }

    def __init__(
        self,
        analyzer: CentralBankSentimentAnalyzer | None = None,
        session_factory: Any = None,
    ) -> None:
        self.analyzer = analyzer or CentralBankSentimentAnalyzer()
        self.session_factory = session_factory

    def process_document(
        self,
        doc: ScrapedDocument,
        previous_doc_score: float | None = None,
    ) -> ProcessedDocument:
        """Process a single scraped document through the full pipeline.

        Args:
            doc: Scraped document to process.
            previous_doc_score: Net score of previous document for change detection.

        Returns:
            ProcessedDocument with all fields populated.
        """
        # Step 1: Clean
        cleaned_text = self._clean_text(doc.raw_text)

        # Step 2: Score
        language = self._detect_language(doc.source)
        result = self.analyzer.score(cleaned_text, language)

        # Step 3: Extract (already done in score, but we can re-extract if needed)
        key_phrases = result.key_phrases

        # Step 4: Compare
        if previous_doc_score is not None:
            change_score = self.analyzer.compute_change_score(
                result.net_score, previous_doc_score
            )
        else:
            change_score = "neutral"

        return ProcessedDocument(
            source=doc.source,
            doc_type=doc.doc_type,
            doc_date=doc.doc_date,
            cleaned_text=cleaned_text,
            hawk_score=result.hawk_score,
            dove_score=result.dove_score,
            net_score=result.net_score,
            change_score=change_score,
            key_phrases=key_phrases,
            method=result.method,
        )

    def process_batch(
        self,
        documents: list[ScrapedDocument],
        source: str,
    ) -> list[ProcessedDocument]:
        """Process a batch of documents with sequential change detection.

        Documents are sorted by date ascending. Each document's change_score
        is computed relative to the previous document's net_score.

        Args:
            documents: List of scraped documents to process.
            source: Source identifier for language detection.

        Returns:
            List of ProcessedDocument in date order.
        """
        # Sort by date ascending for sequential comparison
        sorted_docs = sorted(documents, key=lambda d: d.doc_date)
        processed: list[ProcessedDocument] = []
        previous_score: float | None = None

        for doc in sorted_docs:
            try:
                result = self.process_document(doc, previous_score)
                processed.append(result)
                previous_score = result.net_score
            except Exception as exc:
                logger.error(
                    "Failed to process document %s %s %s: %s",
                    doc.source,
                    doc.doc_type,
                    doc.doc_date,
                    exc,
                )

        return processed

    def persist_results(
        self,
        processed_docs: list[ProcessedDocument],
        session: Any,
    ) -> int:
        """Persist processed document results to the nlp_documents table.

        Updates existing rows matching (source, doc_type, doc_date) with
        hawk_score, dove_score, change_score, and key_phrases.

        Args:
            processed_docs: List of processed documents to persist.
            session: SQLAlchemy session for database operations.

        Returns:
            Count of updated records.
        """
        updated_count = 0

        for doc in processed_docs:
            try:
                stmt = (
                    update(NlpDocumentRecord)
                    .where(
                        NlpDocumentRecord.source == doc.source,
                        NlpDocumentRecord.doc_type == doc.doc_type,
                        NlpDocumentRecord.doc_date == doc.doc_date,
                    )
                    .values(
                        hawk_score=doc.hawk_score,
                        dove_score=doc.dove_score,
                        change_score=doc.change_score,
                        key_phrases=doc.key_phrases,
                    )
                )
                result = session.execute(stmt)
                if result.rowcount > 0:
                    updated_count += result.rowcount
            except Exception as exc:
                logger.error(
                    "Failed to persist results for %s %s %s: %s",
                    doc.source,
                    doc.doc_type,
                    doc.doc_date,
                    exc,
                )

        session.flush()
        return updated_count

    def run_pipeline(
        self,
        scraped_documents: list[ScrapedDocument],
        source: str,
        session: Any = None,
    ) -> PipelineResult:
        """Run the full NLP pipeline: process batch then persist.

        Args:
            scraped_documents: Documents to process.
            source: Source identifier for language detection.
            session: Optional SQLAlchemy session. If None, skips persistence.

        Returns:
            PipelineResult with counts and any errors.
        """
        result = PipelineResult()

        # Process batch
        try:
            processed = self.process_batch(scraped_documents, source)
            result.documents_processed = len(processed)
        except Exception as exc:
            result.errors.append(f"Batch processing failed: {exc}")
            return result

        # Persist if session provided
        if session is not None:
            try:
                result.documents_persisted = self.persist_results(
                    processed, session
                )
            except Exception as exc:
                result.errors.append(f"Persistence failed: {exc}")

        return result

    @staticmethod
    def _clean_text(raw_text: str) -> str:
        """Clean raw text for analysis.

        Steps:
        1. Strip HTML tags
        2. Decode HTML entities
        3. Normalize Unicode to NFC
        4. Collapse multiple whitespace to single space
        5. Strip leading/trailing whitespace

        Args:
            raw_text: Raw document text, possibly containing HTML.

        Returns:
            Cleaned, normalized text.
        """
        if not raw_text:
            return ""

        # Strip HTML tags
        text = re.sub(r"<[^>]+>", " ", raw_text)

        # Decode HTML entities (&amp; -> &, &lt; -> <, etc.)
        text = html.unescape(text)

        # Normalize Unicode
        text = unicodedata.normalize("NFC", text)

        # Collapse multiple whitespace to single space
        text = re.sub(r"\s+", " ", text)

        # Strip leading/trailing whitespace
        text = text.strip()

        return text

    @staticmethod
    def _detect_language(source: str) -> str:
        """Detect language from document source.

        Args:
            source: Source identifier ("copom" or "fomc").

        Returns:
            Language code ("pt" or "en").
        """
        return NLPProcessor._LANGUAGE_MAP.get(source.lower(), "en")

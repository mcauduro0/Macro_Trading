"""Unit tests for NLPProcessor pipeline.

Tests the full pipeline: clean -> score -> extract -> compare -> persist,
using ScrapedDocument fixtures with sample text.
All tests are self-contained with no real HTTP or database calls.
"""

from datetime import date

import pytest

from src.nlp.nlp_processor import NLPProcessor, PipelineResult, ProcessedDocument
from src.nlp.scrapers.copom_scraper import ScrapedDocument


@pytest.fixture
def processor():
    """Create NLPProcessor without database."""
    return NLPProcessor()


@pytest.fixture
def copom_hawk_doc():
    """Hawkish COPOM document fixture."""
    return ScrapedDocument(
        source="copom",
        doc_type="comunicado",
        doc_date=date(2024, 1, 31),
        raw_text=(
            "O Copom decidiu por unanimidade elevar a taxa Selic em 50 pontos base. "
            "A pressao inflacionaria persistente e a inflacao acima da meta exigem "
            "aperto monetario. A deterioracao do cenario requer vigilancia."
        ),
        url="https://www.bcb.gov.br/comunicado/2024-01",
    )


@pytest.fixture
def copom_dove_doc():
    """Dovish COPOM document fixture."""
    return ScrapedDocument(
        source="copom",
        doc_type="comunicado",
        doc_date=date(2024, 3, 20),
        raw_text=(
            "O Copom decidiu por unanimidade reduzir a taxa Selic. "
            "A inflacao controlada e as expectativas ancoradas permitem "
            "flexibilizacao monetaria. A atividade economica fraca e o "
            "hiato do produto negativo justificam o corte da selic."
        ),
        url="https://www.bcb.gov.br/comunicado/2024-03",
    )


@pytest.fixture
def fomc_doc():
    """FOMC statement fixture."""
    return ScrapedDocument(
        source="fomc",
        doc_type="statement",
        doc_date=date(2024, 6, 12),
        raw_text=(
            "The Committee decided to maintain the target range for the "
            "federal funds rate. Inflation remains elevated. The Committee "
            "anticipates further firming may be appropriate."
        ),
        url="https://www.federalreserve.gov/statement/2024-06",
    )


class TestProcessDocument:
    """Tests for single document processing."""

    def test_process_document_returns_processed_document(self, processor, copom_hawk_doc):
        """Processing a document should return ProcessedDocument with all fields."""
        result = processor.process_document(copom_hawk_doc)
        assert isinstance(result, ProcessedDocument)
        assert result.source == "copom"
        assert result.doc_type == "comunicado"
        assert result.doc_date == date(2024, 1, 31)
        assert result.cleaned_text  # non-empty
        assert isinstance(result.hawk_score, float)
        assert isinstance(result.dove_score, float)
        assert isinstance(result.net_score, float)
        assert isinstance(result.change_score, str)
        assert isinstance(result.key_phrases, list)
        assert result.method in ("dictionary", "dictionary+llm")

    def test_process_document_without_previous_has_neutral_change(
        self, processor, copom_hawk_doc
    ):
        """Without previous_doc_score, change_score should be neutral."""
        result = processor.process_document(copom_hawk_doc, previous_doc_score=None)
        assert result.change_score == "neutral"

    def test_process_document_with_previous_computes_change(
        self, processor, copom_hawk_doc
    ):
        """With previous_doc_score, change_score should reflect the delta."""
        # Hawk doc should score positive; previous was very negative -> major shift
        result = processor.process_document(copom_hawk_doc, previous_doc_score=-0.5)
        assert result.change_score in (
            "hawkish_shift",
            "major_hawkish_shift",
        )


class TestProcessBatch:
    """Tests for batch document processing."""

    def test_process_batch_computes_sequential_change_scores(
        self, processor, copom_hawk_doc, copom_dove_doc
    ):
        """Batch processing should compute change_score relative to previous doc."""
        results = processor.process_batch(
            [copom_hawk_doc, copom_dove_doc], source="copom"
        )
        assert len(results) == 2
        # First doc: no previous -> neutral
        assert results[0].change_score == "neutral"
        # Second doc: has previous -> some shift (dovish relative to hawkish)
        assert results[1].change_score in (
            "dovish_shift",
            "major_dovish_shift",
        )

    def test_process_batch_sorts_by_date(self, processor, copom_hawk_doc, copom_dove_doc):
        """Batch processing should sort documents by date ascending."""
        # Pass in reverse order
        results = processor.process_batch(
            [copom_dove_doc, copom_hawk_doc], source="copom"
        )
        assert results[0].doc_date <= results[1].doc_date

    def test_process_batch_first_doc_neutral(self, processor, copom_hawk_doc):
        """First document in batch should always have change_score='neutral'."""
        results = processor.process_batch([copom_hawk_doc], source="copom")
        assert len(results) == 1
        assert results[0].change_score == "neutral"


class TestCleanText:
    """Tests for text cleaning."""

    def test_clean_text_strips_html_tags(self, processor):
        """HTML tags should be removed."""
        raw = "<p>Hello <b>world</b></p>"
        cleaned = processor._clean_text(raw)
        assert "<p>" not in cleaned
        assert "<b>" not in cleaned
        assert "Hello" in cleaned
        assert "world" in cleaned

    def test_clean_text_normalizes_whitespace(self, processor):
        """Multiple spaces/newlines should collapse to single space."""
        raw = "Hello    world\n\n\nfoo   bar"
        cleaned = processor._clean_text(raw)
        assert "  " not in cleaned
        assert cleaned == "Hello world foo bar"

    def test_clean_text_decodes_html_entities(self, processor):
        """HTML entities should be decoded."""
        raw = "rates &amp; bonds &lt; stocks"
        cleaned = processor._clean_text(raw)
        assert "&amp;" not in cleaned
        assert "rates & bonds < stocks" == cleaned

    def test_clean_text_empty_input(self, processor):
        """Empty input should return empty string."""
        assert processor._clean_text("") == ""


class TestDetectLanguage:
    """Tests for language detection from source."""

    def test_copom_returns_pt(self, processor):
        """Source 'copom' should return 'pt'."""
        assert processor._detect_language("copom") == "pt"

    def test_fomc_returns_en(self, processor):
        """Source 'fomc' should return 'en'."""
        assert processor._detect_language("fomc") == "en"

    def test_unknown_source_defaults_to_en(self, processor):
        """Unknown source should default to 'en'."""
        assert processor._detect_language("ecb") == "en"


class TestRunPipeline:
    """Tests for the full run_pipeline method."""

    def test_run_pipeline_without_session(
        self, processor, copom_hawk_doc, copom_dove_doc
    ):
        """Pipeline without session should process but not persist."""
        result = processor.run_pipeline(
            [copom_hawk_doc, copom_dove_doc],
            source="copom",
            session=None,
        )
        assert isinstance(result, PipelineResult)
        assert result.documents_processed == 2
        assert result.documents_persisted == 0
        assert result.errors == []

    def test_run_pipeline_processes_multiple_docs(
        self, processor, copom_hawk_doc, copom_dove_doc, fomc_doc
    ):
        """Pipeline should handle documents from different sources."""
        result = processor.run_pipeline(
            [copom_hawk_doc, copom_dove_doc, fomc_doc],
            source="mixed",
            session=None,
        )
        assert result.documents_processed == 3

    def test_pipeline_result_dataclass(self):
        """PipelineResult should have expected default values."""
        result = PipelineResult()
        assert result.documents_processed == 0
        assert result.documents_persisted == 0
        assert result.errors == []

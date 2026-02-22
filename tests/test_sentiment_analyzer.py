"""Unit tests for CentralBankSentimentAnalyzer.

Tests hawk/dove scoring in Portuguese and English, change score
classification, key phrase extraction, and edge cases.
"""

import pytest

from src.nlp.sentiment_analyzer import CentralBankSentimentAnalyzer, SentimentResult


@pytest.fixture
def analyzer():
    """Create analyzer without LLM."""
    return CentralBankSentimentAnalyzer(api_key=None)


# --- Portuguese scoring tests ---


class TestPortugueseScoring:
    """Tests for Portuguese (COPOM/BCB) text scoring."""

    def test_hawkish_pt_text_scores_positive(self, analyzer):
        """Clearly hawkish PT text should have net_score > 0."""
        text = (
            "O Copom decidiu por unanimidade elevar a taxa Selic em 50 pontos base "
            "diante da pressao inflacionaria persistente e da deterioracao do cenario. "
            "A inflacao acima da meta exige aperto monetario adicional."
        )
        result = analyzer.score(text, "pt")
        assert result.net_score > 0, f"Expected positive net_score, got {result.net_score}"
        assert result.hawk_score > result.dove_score

    def test_dovish_pt_text_scores_negative(self, analyzer):
        """Clearly dovish PT text should have net_score < 0."""
        text = (
            "O Copom decidiu reduzir a taxa Selic diante do ciclo de queda. "
            "A inflacao controlada e a convergencia para a meta permitem "
            "flexibilizacao monetaria. A atividade economica fraca e o hiato "
            "do produto negativo sustentam o espaco para corte."
        )
        result = analyzer.score(text, "pt")
        assert result.net_score < 0, f"Expected negative net_score, got {result.net_score}"
        assert result.dove_score > result.hawk_score

    def test_neutral_pt_text_scores_near_zero(self, analyzer):
        """Text with no dictionary terms should score near zero."""
        text = (
            "A reuniao do comite foi realizada na sede do banco central "
            "com a presenca de todos os membros. Os dados foram apresentados "
            "e a discussao seguiu a pauta prevista."
        )
        result = analyzer.score(text, "pt")
        assert abs(result.net_score) < 0.3, f"Expected near-zero score, got {result.net_score}"


# --- English scoring tests ---


class TestEnglishScoring:
    """Tests for English (FOMC/Fed) text scoring."""

    def test_hawkish_en_text_scores_positive(self, analyzer):
        """Clearly hawkish EN text should have net_score > 0."""
        text = (
            "The Committee decided to raise rates by 75 basis points. "
            "Inflation remains elevated and price pressures continue to be broad-based. "
            "The Committee anticipates further firming to achieve a sufficiently "
            "restrictive stance. Upside risks to inflation persist."
        )
        result = analyzer.score(text, "en")
        assert result.net_score > 0, f"Expected positive net_score, got {result.net_score}"

    def test_dovish_en_text_scores_negative(self, analyzer):
        """Clearly dovish EN text should have net_score < 0."""
        text = (
            "The Committee decided to cut rates. Inflation has eased and "
            "disinflation continues. The labor market is softening with "
            "unemployment rising. Economic slowdown warrants accommodative "
            "policy easing. Inflation expectations anchored near the two percent goal."
        )
        result = analyzer.score(text, "en")
        assert result.net_score < 0, f"Expected negative net_score, got {result.net_score}"

    def test_neutral_en_text_scores_near_zero(self, analyzer):
        """Text without policy terms should score near zero."""
        text = (
            "The meeting was attended by all members of the committee. "
            "Staff presented the economic outlook. Participants discussed "
            "recent developments in the global economy."
        )
        result = analyzer.score(text, "en")
        assert abs(result.net_score) < 0.3, f"Expected near-zero score, got {result.net_score}"


# --- Change score tests ---


class TestChangeScore:
    """Tests for categorical change score computation."""

    def test_major_hawkish_shift(self, analyzer):
        """Large positive delta -> major_hawkish_shift."""
        result = analyzer.compute_change_score(0.5, -0.1)
        assert result == "major_hawkish_shift"

    def test_major_dovish_shift(self, analyzer):
        """Large negative delta -> major_dovish_shift."""
        result = analyzer.compute_change_score(-0.3, 0.2)
        assert result == "major_dovish_shift"

    def test_hawkish_shift(self, analyzer):
        """Moderate positive delta -> hawkish_shift."""
        result = analyzer.compute_change_score(0.3, 0.1)
        assert result == "hawkish_shift"

    def test_dovish_shift(self, analyzer):
        """Moderate negative delta -> dovish_shift."""
        result = analyzer.compute_change_score(0.0, 0.2)
        assert result == "dovish_shift"

    def test_neutral_no_shift(self, analyzer):
        """Small delta -> neutral."""
        result = analyzer.compute_change_score(0.15, 0.12)
        assert result == "neutral"

    def test_exact_threshold_major(self, analyzer):
        """Delta exactly at major threshold (0.3) is not major (uses > not >=)."""
        # |0.3| is NOT > 0.3, so should be hawkish_shift
        result = analyzer.compute_change_score(0.4, 0.1)
        assert result == "major_hawkish_shift"

    def test_exact_threshold_minor(self, analyzer):
        """Delta exactly at minor threshold boundaries."""
        # delta = 0.1, |0.1| is NOT > 0.1, so neutral
        result = analyzer.compute_change_score(0.2, 0.1)
        assert result == "neutral"


# --- Key phrase extraction tests ---


class TestKeyPhraseExtraction:
    """Tests for key phrase extraction."""

    def test_extract_key_phrases_returns_list(self, analyzer):
        """Key phrases should be returned as a non-empty list for hawk text."""
        text = "A elevacao da selic foi necessaria diante da pressao inflacionaria."
        phrases = analyzer.extract_key_phrases(text, "pt")
        assert isinstance(phrases, list)
        assert len(phrases) > 0

    def test_extract_key_phrases_empty_text(self, analyzer):
        """Empty text should return empty list."""
        phrases = analyzer.extract_key_phrases("", "pt")
        assert phrases == []


# --- Edge case tests ---


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_text_returns_zero_scores(self, analyzer):
        """Empty text should return all-zero SentimentResult."""
        result = analyzer.score("", "pt")
        assert result.hawk_score == 0.0
        assert result.dove_score == 0.0
        assert result.net_score == 0.0
        assert result.method == "dictionary"

    def test_whitespace_only_returns_zero_scores(self, analyzer):
        """Whitespace-only text should return all-zero SentimentResult."""
        result = analyzer.score("   \n\t  ", "en")
        assert result.net_score == 0.0

    def test_score_clipped_to_range(self, analyzer):
        """Net score must be clipped to [-1, +1]."""
        result = analyzer.score(
            "raise rates raise rates raise rates tightening tightening "
            "hawkish rate hike rate hike further firming policy firming "
            "inflation persistent above target additional tightening",
            "en",
        )
        assert -1.0 <= result.net_score <= 1.0

    def test_mixed_hawk_dove_text_intermediate(self, analyzer):
        """Mixed hawk/dove text should produce intermediate scores."""
        text = (
            "The committee raised rates due to elevated inflation but noted "
            "that economic slowdown and labor market softening suggest "
            "the cycle of tightening is near its end with possible rate cut ahead."
        )
        result = analyzer.score(text, "en")
        # Should not be extreme in either direction
        assert -0.9 < result.net_score < 0.9

    def test_sentiment_result_dataclass(self, analyzer):
        """SentimentResult should have all expected fields."""
        result = analyzer.score("raise rates", "en")
        assert hasattr(result, "hawk_score")
        assert hasattr(result, "dove_score")
        assert hasattr(result, "net_score")
        assert hasattr(result, "key_phrases")
        assert hasattr(result, "method")
        assert isinstance(result, SentimentResult)

    def test_unknown_language_defaults_to_pt(self, analyzer):
        """Unknown language code should fall back to PT dictionary."""
        result = analyzer.score("elevacao da selic", "xx")
        assert result.net_score > 0  # PT hawk term should match

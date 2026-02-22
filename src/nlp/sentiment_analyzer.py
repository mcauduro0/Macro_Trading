"""CentralBankSentimentAnalyzer for hawk/dove scoring of central bank communications.

Provides dictionary-based term matching with optional LLM refinement.
Produces hawk/dove scores in [-1, +1] range with categorical change detection
and key phrase extraction.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field

from src.nlp.dictionaries.hawk_dove_en import DOVE_TERMS_EN, HAWK_TERMS_EN
from src.nlp.dictionaries.hawk_dove_pt import DOVE_TERMS_PT, HAWK_TERMS_PT

logger = logging.getLogger(__name__)


@dataclass
class SentimentResult:
    """Result of sentiment analysis on a central bank document.

    Attributes:
        hawk_score: Normalized hawkish score [0, 1].
        dove_score: Normalized dovish score [0, 1].
        net_score: Net sentiment score [-1, +1], positive = hawkish.
        key_phrases: Top extracted phrases with context.
        method: Scoring method used ("dictionary" or "dictionary+llm").
    """

    hawk_score: float
    dove_score: float
    net_score: float
    key_phrases: list[str] = field(default_factory=list)
    method: str = "dictionary"


class CentralBankSentimentAnalyzer:
    """Hawk/dove sentiment analyzer for central bank communications.

    Uses dictionary-based term matching as the primary scoring method
    with optional LLM refinement when an API key is available.

    Args:
        api_key: Optional Anthropic API key for LLM refinement.
    """

    # Change score thresholds (locked decision)
    MAJOR_SHIFT_THRESHOLD = 0.3
    MINOR_SHIFT_THRESHOLD = 0.1

    def __init__(self, api_key: str | None = None) -> None:
        # Load dictionaries for both languages
        self._dictionaries = {
            "pt": {
                "hawk": HAWK_TERMS_PT,
                "dove": DOVE_TERMS_PT,
            },
            "en": {
                "hawk": HAWK_TERMS_EN,
                "dove": DOVE_TERMS_EN,
            },
        }

        # Check if LLM refinement is available
        self._llm_available = False
        self._api_key = api_key
        if api_key:
            try:
                import anthropic  # noqa: F401

                self._llm_available = True
                logger.info("LLM refinement enabled via Anthropic API")
            except ImportError:
                logger.warning(
                    "Anthropic package not installed; LLM refinement disabled"
                )

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize text for dictionary matching.

        Lowercases, decomposes accents (NFD -> strip combining marks -> NFC),
        strips non-alphanumeric characters except spaces.
        """
        text = text.lower()
        # Decompose unicode, remove combining diacritical marks, recompose
        text = unicodedata.normalize("NFD", text)
        text = "".join(
            ch for ch in text if unicodedata.category(ch) != "Mn"
        )
        text = unicodedata.normalize("NFC", text)
        # Replace punctuation with spaces (keep alphanumeric and spaces)
        text = re.sub(r"[^\w\s]", " ", text)
        # Collapse multiple whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def score(self, text: str, language: str = "pt") -> SentimentResult:
        """Score a document for hawk/dove sentiment.

        Args:
            text: Document text to analyze.
            language: Language code ("pt" for Portuguese, "en" for English).

        Returns:
            SentimentResult with hawk/dove scores and key phrases.
        """
        if not text or not text.strip():
            return SentimentResult(
                hawk_score=0.0,
                dove_score=0.0,
                net_score=0.0,
                key_phrases=[],
                method="dictionary",
            )

        cleaned = self._normalize_text(text)
        lang_key = language if language in self._dictionaries else "pt"
        hawk_dict = self._dictionaries[lang_key]["hawk"]
        dove_dict = self._dictionaries[lang_key]["dove"]

        # Count weighted term occurrences
        hawk_weights: list[float] = []
        dove_weights: list[float] = []

        # Sort by term length descending so longer phrases match first
        for term, weight in sorted(
            hawk_dict.items(), key=lambda x: len(x[0]), reverse=True
        ):
            count = cleaned.count(term)
            if count > 0:
                hawk_weights.extend([weight] * count)

        for term, weight in sorted(
            dove_dict.items(), key=lambda x: len(x[0]), reverse=True
        ):
            count = cleaned.count(term)
            if count > 0:
                dove_weights.extend([weight] * count)

        total_terms_found = max(1, len(hawk_weights) + len(dove_weights))
        hawk_score = sum(hawk_weights) / total_terms_found
        dove_score = sum(dove_weights) / total_terms_found

        net_score = hawk_score - dove_score
        # Clip to [-1, +1]
        net_score = max(-1.0, min(1.0, net_score))

        # Extract key phrases
        key_phrases = self.extract_key_phrases(text, language)

        method = "dictionary"

        # Optional LLM refinement
        if self._llm_available:
            try:
                refined = self._refine_with_llm(text, net_score, language)
                net_score = max(-1.0, min(1.0, refined))
                method = "dictionary+llm"
            except Exception as exc:
                logger.warning("LLM refinement failed, using dictionary score: %s", exc)

        return SentimentResult(
            hawk_score=round(hawk_score, 4),
            dove_score=round(dove_score, 4),
            net_score=round(net_score, 4),
            key_phrases=key_phrases,
            method=method,
        )

    def compute_change_score(
        self, current_score: float, previous_score: float
    ) -> str:
        """Compute categorical change score vs previous document.

        Per locked decision: categorical + magnitude classification.

        Args:
            current_score: Current document net_score.
            previous_score: Previous document net_score.

        Returns:
            One of: "major_hawkish_shift", "major_dovish_shift",
                    "hawkish_shift", "dovish_shift", "neutral".
        """
        delta = current_score - previous_score

        if abs(delta) > self.MAJOR_SHIFT_THRESHOLD:
            return "major_hawkish_shift" if delta > 0 else "major_dovish_shift"
        elif abs(delta) > self.MINOR_SHIFT_THRESHOLD:
            return "hawkish_shift" if delta > 0 else "dovish_shift"
        else:
            return "neutral"

    def extract_key_phrases(
        self, text: str, language: str = "pt", top_n: int = 10
    ) -> list[str]:
        """Extract top key phrases from text based on dictionary matches.

        Finds all dictionary term matches and returns the top_n by weight,
        preserving surrounding context (approximately 5 words on each side).

        Args:
            text: Original document text.
            language: Language code ("pt" or "en").
            top_n: Maximum number of phrases to return.

        Returns:
            List of key phrases with surrounding context.
        """
        if not text or not text.strip():
            return []

        cleaned = self._normalize_text(text)
        lang_key = language if language in self._dictionaries else "pt"
        hawk_dict = self._dictionaries[lang_key]["hawk"]
        dove_dict = self._dictionaries[lang_key]["dove"]

        # Combine all terms with their weights and direction
        all_terms: list[tuple[str, float]] = []
        for term, weight in hawk_dict.items():
            if term in cleaned:
                all_terms.append((term, weight))
        for term, weight in dove_dict.items():
            if term in cleaned:
                all_terms.append((term, weight))

        # Sort by weight descending, take top_n
        all_terms.sort(key=lambda x: x[1], reverse=True)
        top_terms = all_terms[:top_n]

        # Extract phrases with context from normalized text
        words = cleaned.split()
        phrases: list[str] = []

        for term, _weight in top_terms:
            # Find the term position in the word list
            term_words = term.split()
            term_len = len(term_words)
            for i in range(len(words) - term_len + 1):
                candidate = " ".join(words[i : i + term_len])
                if candidate == term:
                    # Get surrounding context (5 words each side)
                    start = max(0, i - 5)
                    end = min(len(words), i + term_len + 5)
                    context = " ".join(words[start:end])
                    if context not in phrases:
                        phrases.append(context)
                    break  # Only first occurrence per term

        return phrases

    def _refine_with_llm(
        self, text: str, dict_score: float, language: str
    ) -> float:
        """Refine dictionary score using LLM analysis.

        Sends the text to Claude for hawk/dove rating and blends
        the result with the dictionary score (70% dict + 30% LLM).

        Args:
            text: Original document text.
            dict_score: Dictionary-based net score.
            language: Language code.

        Returns:
            Blended score. On any error, returns dict_score unchanged.
        """
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self._api_key)

            lang_label = "Portuguese" if language == "pt" else "English"
            prompt = (
                f"Analyze this {lang_label} central bank communication for "
                f"monetary policy stance. Rate it on a scale from -1.0 (very "
                f"dovish/easing) to +1.0 (very hawkish/tightening). "
                f"Reply with ONLY a single float number.\n\n"
                f"Text: {text[:3000]}"  # Truncate to avoid token limits
            )

            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=50,
                messages=[{"role": "user", "content": prompt}],
            )

            llm_text = message.content[0].text.strip()
            llm_score = float(llm_text)
            llm_score = max(-1.0, min(1.0, llm_score))

            # Blend: 70% dictionary + 30% LLM
            blended = 0.7 * dict_score + 0.3 * llm_score
            logger.info(
                "LLM refinement: dict=%.3f, llm=%.3f, blended=%.3f",
                dict_score,
                llm_score,
                blended,
            )
            return blended

        except Exception as exc:
            logger.warning("LLM refinement error: %s", exc)
            return dict_score

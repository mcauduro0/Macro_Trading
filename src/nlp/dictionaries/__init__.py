"""Hawk/dove term dictionaries for central bank sentiment analysis.

Provides Portuguese (COPOM/BCB) and English (FOMC/Fed) dictionaries
with weighted terms for hawk/dove classification.
"""

from src.nlp.dictionaries.hawk_dove_en import (
    DOVE_TERMS_EN,
    HAWK_TERMS_EN,
)
from src.nlp.dictionaries.hawk_dove_pt import (
    DOVE_TERMS_PT,
    HAWK_TERMS_PT,
)

__all__ = [
    "HAWK_TERMS_PT",
    "DOVE_TERMS_PT",
    "HAWK_TERMS_EN",
    "DOVE_TERMS_EN",
]

"""NlpDocumentRecord ORM model for central bank document storage.

Stores raw text and sentiment scores for COPOM and FOMC documents.
Single table design with unique constraint on (source, doc_type, doc_date)
to prevent duplicate scrapes.
"""

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from .base import Base


class NlpDocumentRecord(Base):
    """ORM model for the nlp_documents table.

    Attributes:
        source: Institution identifier ("copom" or "fomc").
        doc_type: Document type ("ata", "comunicado", "statement", "minutes").
        doc_date: Meeting or release date.
        raw_text: Full document text (null until scraped).
        hawk_score: Hawkish sentiment score [-1, +1] (null until scored).
        dove_score: Dovish sentiment score [-1, +1] (null until scored).
        change_score: Categorical shift label (null until scored).
        key_phrases: JSON list of extracted phrases (null until scored).
        url: Source URL for the document.
    """

    __tablename__ = "nlp_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(20), nullable=False)
    doc_type = Column(String(30), nullable=False)
    doc_date = Column(Date, nullable=False)
    raw_text = Column(Text, nullable=True)
    hawk_score = Column(Float, nullable=True)
    dove_score = Column(Float, nullable=True)
    change_score = Column(String(30), nullable=True)
    key_phrases = Column(JSONB, nullable=True)
    url = Column(String(500), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "source",
            "doc_type",
            "doc_date",
            name="uq_nlp_documents_natural_key",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<NlpDocumentRecord(source={self.source!r}, "
            f"doc_type={self.doc_type!r}, doc_date={self.doc_date})>"
        )

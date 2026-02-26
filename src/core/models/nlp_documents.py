"""NlpDocumentRecord ORM model for central bank document storage.

Stores raw text and sentiment scores for COPOM and FOMC documents.
Single table design with unique constraint on (source, doc_type, doc_date)
to prevent duplicate scrapes.
"""

from datetime import date as date_type
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

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

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(30), nullable=False)
    doc_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hawk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dove_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    change_score: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    key_phrases: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
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

"""Agent reports table -- audit trail for agent execution results.

Regular PostgreSQL table (NOT a hypertable -- low volume: ~5 records/day).
Stores the narrative, diagnostics, and metadata from each agent run.
Individual signal values are persisted separately to the signals hypertable.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AgentReportRecord(Base):
    """ORM model for the ``agent_reports`` table.

    Named ``AgentReportRecord`` (not ``AgentReport``) to avoid confusion
    with the dataclass in ``src.agents.base``.
    """

    __tablename__ = "agent_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(50), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    signals_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    narrative: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_diagnostics: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    data_quality_flags: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_agent_reports_agent_id_date", "agent_id", "as_of_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentReportRecord("
            f"agent_id={self.agent_id!r}, "
            f"as_of_date={self.as_of_date}, "
            f"signals_count={self.signals_count})>"
        )

"""Agent framework core -- BaseAgent ABC, AgentSignal, and AgentReport.

Implements the Template Method pattern: BaseAgent.run() orchestrates the
pipeline load_data -> compute_features -> run_models -> generate_narrative,
while subclasses supply the domain-specific implementations.

AgentSignal is the typed output for a single signal produced by a model.
AgentReport bundles all signals from a single agent run with metadata.
"""

import abc
import asyncio
import concurrent.futures
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.core.database import async_session_factory, sync_session_factory
from src.core.enums import SignalDirection, SignalStrength
from src.core.models.signals import Signal

# Shared thread pool for async-to-sync bridging (avoids per-call instantiation)
_SHARED_THREAD_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=2)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def classify_strength(confidence: float) -> SignalStrength:
    """Map a numeric confidence value to a SignalStrength bucket.

    Args:
        confidence: Value between 0.0 and 1.0.

    Returns:
        STRONG if >= 0.75, MODERATE if >= 0.50, WEAK if >= 0.25,
        otherwise NO_SIGNAL.
    """
    if confidence >= 0.75:
        return SignalStrength.STRONG
    if confidence >= 0.50:
        return SignalStrength.MODERATE
    if confidence >= 0.25:
        return SignalStrength.WEAK
    return SignalStrength.NO_SIGNAL


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class AgentSignal:
    """Typed output for a single signal produced by an analytical model.

    Attributes:
        signal_id: Unique identifier, e.g. ``"INFLATION_BR_PHILLIPS"``.
        agent_id: Producing agent, e.g. ``"inflation_agent"``.
        timestamp: UTC datetime when the signal was generated.
        as_of_date: Point-in-time reference date.
        direction: LONG, SHORT, or NEUTRAL.
        strength: Bucketed confidence (STRONG/MODERATE/WEAK/NO_SIGNAL).
        confidence: Raw confidence value in ``[0.0, 1.0]``.
        value: Numerical signal value (z-score, model output, etc.).
        horizon_days: Signal horizon in trading days (21=1M, 63=1Q, 252=1Y).
        metadata: Arbitrary model-specific details.
    """

    signal_id: str
    agent_id: str
    timestamp: datetime
    as_of_date: date
    direction: SignalDirection
    strength: SignalStrength
    confidence: float
    value: float
    horizon_days: int
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentReport:
    """Complete output from a single agent run.

    Bundles all signals with a human-readable narrative and diagnostics.

    Attributes:
        agent_id: Producing agent identifier.
        as_of_date: Point-in-time reference date.
        generated_at: UTC datetime when the report was assembled.
        signals: List of AgentSignal objects.
        narrative: Human-readable analysis summary.
        model_diagnostics: Model fit statistics, feature importances, etc.
        data_quality_flags: Issues encountered during data loading.
    """

    agent_id: str
    as_of_date: date
    generated_at: datetime
    signals: list[AgentSignal]
    narrative: str
    model_diagnostics: dict = field(default_factory=dict)
    data_quality_flags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# BaseAgent ABC
# ---------------------------------------------------------------------------
class BaseAgent(abc.ABC):
    """Abstract base class for all analytical agents.

    Subclasses implement the four abstract methods to provide domain logic.
    The concrete ``run()`` and ``backtest_run()`` methods orchestrate the
    full pipeline using the Template Method pattern.
    """

    def __init__(self, agent_id: str, agent_name: str) -> None:
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.log = structlog.get_logger().bind(agent=agent_id)

    # ------------------------------------------------------------------
    # Abstract interface (subclasses MUST implement)
    # ------------------------------------------------------------------
    @abc.abstractmethod
    def load_data(self, as_of_date: date) -> dict[str, Any]:
        """Load all required data for analysis, respecting point-in-time.

        Implementations must only use data with ``release_time <= as_of_date``.

        Args:
            as_of_date: The reference date for point-in-time filtering.

        Returns:
            Dictionary mapping descriptive keys to DataFrames or scalars.
        """
        ...

    @abc.abstractmethod
    def compute_features(self, data: dict) -> dict[str, Any]:
        """Transform raw data into model features.

        Args:
            data: Output of ``load_data()``.

        Returns:
            Dictionary mapping feature names to computed values.
        """
        ...

    @abc.abstractmethod
    def run_models(self, features: dict) -> list[AgentSignal]:
        """Execute quantitative models and generate signals.

        Args:
            features: Output of ``compute_features()``.

        Returns:
            List of AgentSignal objects (one per sub-model).
        """
        ...

    @abc.abstractmethod
    def generate_narrative(self, signals: list[AgentSignal], features: dict) -> str:
        """Generate a human-readable analysis summary.

        Args:
            signals: Output of ``run_models()``.
            features: Output of ``compute_features()``.

        Returns:
            Multi-paragraph analysis text.
        """
        ...

    # ------------------------------------------------------------------
    # Concrete pipeline methods
    # ------------------------------------------------------------------
    def run(self, as_of_date: date) -> AgentReport:
        """Execute the full agent pipeline and persist signals.

        Orchestrates: load_data -> compute_features -> run_models ->
        generate_narrative -> _persist_signals.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            Complete AgentReport with all signals and narrative.
        """
        self.log.info("agent_run_start", as_of_date=str(as_of_date))
        start = datetime.utcnow()

        data = self.load_data(as_of_date)
        data_flags = self._check_data_quality(data)
        features = self.compute_features(data)
        signals = self.run_models(features)
        narrative = self.generate_narrative(signals, features)
        self._persist_signals(signals)

        elapsed = (datetime.utcnow() - start).total_seconds()
        self.log.info(
            "agent_run_complete",
            signals=len(signals),
            elapsed=round(elapsed, 2),
        )
        report = AgentReport(
            agent_id=self.agent_id,
            as_of_date=as_of_date,
            generated_at=datetime.utcnow(),
            signals=signals,
            narrative=narrative,
            model_diagnostics={},
            data_quality_flags=data_flags,
        )
        self._persist_report(report)
        return report

    def backtest_run(self, as_of_date: date) -> AgentReport:
        """Execute the pipeline without persisting signals.

        Identical to ``run()`` but skips ``_persist_signals()`` and data
        quality flagging. Intended for use by the backtesting engine.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            AgentReport with signals but no side-effects.
        """
        data = self.load_data(as_of_date)
        features = self.compute_features(data)
        signals = self.run_models(features)
        narrative = self.generate_narrative(signals, features)
        return AgentReport(
            agent_id=self.agent_id,
            as_of_date=as_of_date,
            generated_at=datetime.utcnow(),
            signals=signals,
            narrative=narrative,
            model_diagnostics={},
            data_quality_flags=[],
        )

    # ------------------------------------------------------------------
    # Concrete helper methods
    # ------------------------------------------------------------------
    def _check_data_quality(self, data: dict) -> list[str]:
        """Scan loaded data for quality issues.

        Checks for:
        - None values (missing data entirely)
        - NaN values within pandas DataFrames

        Args:
            data: Dictionary from ``load_data()``.

        Returns:
            List of human-readable flag strings.
        """
        import pandas as pd

        flags: list[str] = []
        for key, value in data.items():
            if value is None:
                flags.append(f"{key}: data is None")
            elif isinstance(value, pd.DataFrame):
                na_count = int(value.isna().sum().sum())
                if na_count > 0:
                    flags.append(f"{key}: contains {na_count} missing values")
            elif isinstance(value, dict):
                # Recurse one level for nested dicts of DataFrames
                for sub_key, sub_val in value.items():
                    if sub_val is None:
                        flags.append(f"{key}.{sub_key}: data is None")
                    elif isinstance(sub_val, pd.DataFrame):
                        na_sub = int(sub_val.isna().sum().sum())
                        if na_sub > 0:
                            flags.append(
                                f"{key}.{sub_key}: contains {na_sub} missing values"
                            )
        return flags

    def _persist_report(self, report: AgentReport) -> None:
        """Persist agent report to the ``agent_reports`` table for audit trail.

        Args:
            report: The AgentReport to persist.
        """
        from src.core.models.agent_reports import AgentReportRecord

        session = sync_session_factory()
        try:
            record = AgentReportRecord(
                agent_id=report.agent_id,
                as_of_date=report.as_of_date,
                signals_count=len(report.signals),
                narrative=report.narrative,
                model_diagnostics=report.model_diagnostics or None,
                data_quality_flags=report.data_quality_flags or None,
            )
            session.add(record)
            session.commit()
            self.log.info(
                "report_persisted",
                agent_id=report.agent_id,
                as_of_date=str(report.as_of_date),
            )
        except Exception as exc:
            session.rollback()
            self.log.error("report_persist_failed", error=str(exc))
        finally:
            session.close()

    def _persist_signals(self, signals: list[AgentSignal]) -> int:
        """Persist signals to the signals hypertable.

        Bridges sync calling context to the async database session by
        running ``_persist_signals_async`` in a thread pool if an event
        loop is already running, or via ``asyncio.run()`` otherwise.

        Args:
            signals: List of AgentSignal objects to persist.

        Returns:
            Number of rows inserted (conflicts excluded).
        """
        try:
            asyncio.get_running_loop()
            # Already in async context -- run in shared thread pool
            future = _SHARED_THREAD_POOL.submit(asyncio.run, self._persist_signals_async(signals))
            inserted = future.result()
        except RuntimeError:
            # No running loop -- safe to use asyncio.run
            inserted = asyncio.run(self._persist_signals_async(signals))

        self.log.info("signals_persisted", count=inserted)
        return inserted

    async def _persist_signals_async(self, signals: list[AgentSignal]) -> int:
        """Async implementation of signal persistence.

        Uses INSERT ... ON CONFLICT DO NOTHING on the
        ``uq_signals_natural_key`` constraint for idempotency.

        Args:
            signals: List of AgentSignal objects.

        Returns:
            Number of rows inserted.
        """
        records = [
            {
                "signal_type": sig.signal_id,
                "signal_date": sig.as_of_date,
                "instrument_id": None,
                "series_id": None,
                "value": sig.value,
                "confidence": sig.confidence,
                "metadata_json": json.dumps(
                    {
                        "direction": sig.direction.value,
                        "strength": sig.strength.value,
                        "horizon_days": sig.horizon_days,
                        "agent_id": sig.agent_id,
                        **sig.metadata,
                    }
                ),
            }
            for sig in signals
        ]
        if not records:
            return 0

        async with async_session_factory() as session:
            async with session.begin():
                stmt = pg_insert(Signal).values(records)
                stmt = stmt.on_conflict_do_nothing(
                    constraint="uq_signals_natural_key"
                )
                result = await session.execute(stmt)
                return result.rowcount

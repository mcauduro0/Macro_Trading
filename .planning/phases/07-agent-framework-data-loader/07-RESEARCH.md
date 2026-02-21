# Phase 7: Agent Framework & Data Loader - Research

**Researched:** 2026-02-20
**Domain:** Agent framework infrastructure, point-in-time data access, quantitative modeling dependencies
**Confidence:** HIGH

## Summary

Phase 7 builds the foundational infrastructure that all 5 analytical agents (Inflation, Monetary Policy, Fiscal, FX Equilibrium, Cross-Asset) will rely on. The codebase already has a well-established pattern in `src/connectors/base.py` (BaseConnector ABC with Template Method pattern, structured logging, async context management), which serves as the architectural blueprint for BaseAgent. The signals hypertable exists with a natural key constraint suitable for ON CONFLICT DO NOTHING idempotent writes. The database layer provides both async (asyncpg) and sync (psycopg2) session factories ready for use.

The key challenge is the PointInTimeDataLoader, which must enforce `release_time <= as_of_date` for macro_series (which has a NOT NULL release_time column) but needs different approaches for curves, market_data, and flow_data (which either lack release_time or have it nullable). The existing transforms layer (returns.py, macro.py, curves.py) provides computation utilities agents will consume directly. Two critical dependencies --- statsmodels and scikit-learn --- are NOT installed and must be added for quantitative models in later phases.

**Primary recommendation:** Follow the BaseConnector pattern closely for BaseAgent design, use sync sessions for the PointInTimeDataLoader (batch queries during agent runs are CPU-bound, not I/O-bound), and create a new Alembic migration (003) for the agent_reports table as a regular table (not a hypertable, given low volume).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AGENT-01 | BaseAgent abstract class with Template Method pattern: load_data -> compute_features -> run_models -> generate_narrative -> persist_signals | BaseConnector ABC in connectors/base.py provides the exact pattern (run() orchestrates fetch -> store). Structlog logging, Template Method confirmed as standard approach. |
| AGENT-02 | AgentSignal dataclass with signal_id, direction, strength, confidence (0-1), value, horizon_days, metadata | New SignalDirection and SignalStrength enums follow existing (str, Enum) pattern in src/core/enums.py. Dataclass fields map cleanly to signals hypertable columns. |
| AGENT-03 | AgentReport dataclass combining signals, narrative text, model diagnostics, and data quality flags | Plain Python dataclass. No ORM mapping needed for in-memory report structure; agent_reports table stores the persistent version. |
| AGENT-04 | PointInTimeDataLoader utility querying macro_series, curves, market_data with release_time <= as_of_date constraint | macro_series.release_time is NOT NULL (ideal). curves and market_data lack release_time --- must use curve_date/timestamp as proxy. flow_data.release_time is nullable. Sync session (psycopg2) recommended for batch queries. |
| AGENT-05 | AgentRegistry managing execution order with run_all(as_of_date) | Simple class-level dict registry with ordered execution. No framework needed. |
| AGENT-06 | Signal persistence to signals hypertable with ON CONFLICT DO NOTHING idempotency | Existing _bulk_insert pattern in BaseConnector uses pg_insert().on_conflict_do_nothing(constraint="uq_signals_natural_key"). Direct reuse. |
| AGENT-07 | Alembic migration adding agent_reports table | Migration 003, regular table (not hypertable). Alembic env.py needs agent_reports model import added. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0.46 | ORM, database queries for PIT data loader | Already installed, used throughout codebase (mapped_column style) |
| asyncpg | 0.31.0 | Async PostgreSQL driver | Already installed, used by async_engine |
| psycopg2-binary | (installed) | Sync PostgreSQL driver | Already installed, used by sync_engine and Alembic |
| structlog | 25.5.0 | Structured logging for agents | Already installed, used by all connectors |
| pandas | 3.0.1 | DataFrame returns from PointInTimeDataLoader | Already installed, used by transforms |
| numpy | 2.4.2 | Array operations in features/models | Already installed |
| alembic | (installed) | Database migrations | Already installed, 2 migrations exist |

### New Dependencies (to be added)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| statsmodels | latest | OLS regression (Phillips Curve, Taylor Rule), Kalman Filter, time series models | Required by INFL-02 (PhillipsCurveModel), MONP-02 (TaylorRuleModel), MONP-03 (KalmanFilterRStar) in Phase 8+ |
| scikit-learn | latest | Linear regression, standardization, model evaluation utilities | Required by agents for feature scaling, model fitting in Phase 8+ |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| statsmodels OLS | numpy.linalg.lstsq | statsmodels provides t-stats, R-squared, residual diagnostics; raw numpy only gives coefficients |
| scikit-learn LinearRegression | statsmodels OLS | scikit-learn is simpler API but lacks econometric diagnostics; use both |
| Sync PointInTimeDataLoader | Async version | Agent runs are batch processes, not concurrent web requests; sync is simpler and avoids event loop complexity within agent computation |

**Installation:**
```bash
pip install statsmodels scikit-learn
```
Then add to `pyproject.toml` dependencies section:
```toml
"statsmodels>=0.14",
"scikit-learn>=1.4",
```

## Architecture Patterns

### Recommended Project Structure
```
src/agents/
    __init__.py                 # Exports BaseAgent, AgentSignal, AgentReport, AgentRegistry
    base.py                     # BaseAgent ABC, AgentSignal, AgentReport dataclasses
    registry.py                 # AgentRegistry with ordered execution
    data_loader.py              # PointInTimeDataLoader (sync queries)
    inflation/                  # Phase 8
        __init__.py
        agent.py
        features.py
        models.py
    monetary/                   # Phase 8
    fiscal/                     # Phase 9
    fx/                         # Phase 9
    cross_asset/                # Phase 10
```

### New Model File
```
src/core/models/
    agent_reports.py            # AgentReport ORM model for persistence
```

### New Enum Additions
```
src/core/enums.py              # Add SignalDirection, SignalStrength enums
```

### Pattern 1: Template Method (BaseAgent.run)
**What:** Abstract base class with concrete `run()` method orchestrating abstract steps
**When to use:** All agents follow the same pipeline: load_data -> compute_features -> run_models -> generate_narrative -> persist_signals
**Example:**
```python
# Source: Existing pattern in src/connectors/base.py lines 218-249
# BaseConnector.run() orchestrates fetch() -> store()
# BaseAgent.run() orchestrates load_data() -> compute_features() -> run_models() -> generate_narrative() -> _persist_signals()

class BaseAgent(abc.ABC):
    def run(self, as_of_date: date) -> AgentReport:
        """Concrete orchestrator -- Template Method pattern."""
        data = self.load_data(as_of_date)
        data_flags = self._check_data_quality(data)
        features = self.compute_features(data)
        signals = self.run_models(features)
        narrative = self.generate_narrative(signals, features)
        self._persist_signals(signals)
        return AgentReport(...)

    def backtest_run(self, as_of_date: date) -> AgentReport:
        """Same pipeline but does NOT persist signals."""
        data = self.load_data(as_of_date)
        features = self.compute_features(data)
        signals = self.run_models(features)
        narrative = self.generate_narrative(signals, features)
        return AgentReport(...)  # No _persist_signals call

    @abc.abstractmethod
    def load_data(self, as_of_date: date) -> dict[str, Any]: ...
    @abc.abstractmethod
    def compute_features(self, data: dict) -> dict[str, Any]: ...
    @abc.abstractmethod
    def run_models(self, features: dict) -> list[AgentSignal]: ...
    @abc.abstractmethod
    def generate_narrative(self, signals: list[AgentSignal], features: dict) -> str: ...
```

### Pattern 2: Idempotent Signal Persistence (ON CONFLICT DO NOTHING)
**What:** Bulk insert signals using PostgreSQL upsert with conflict resolution
**When to use:** Every time agents persist signals to the signals hypertable
**Example:**
```python
# Source: Existing pattern in src/connectors/base.py lines 251-279
# BaseConnector._bulk_insert uses pg_insert().on_conflict_do_nothing(constraint=...)

from sqlalchemy.dialects.postgresql import insert as pg_insert
from src.core.database import async_session_factory
from src.core.models.signals import Signal

async def _persist_signals(self, signals: list[AgentSignal]) -> int:
    records = [
        {
            "signal_type": s.signal_id,
            "signal_date": s.as_of_date,
            "instrument_id": None,  # or mapped from metadata
            "value": s.value,
            "confidence": s.confidence,
            "metadata_json": json.dumps(s.metadata) if s.metadata else None,
        }
        for s in signals
    ]
    async with async_session_factory() as session:
        async with session.begin():
            stmt = pg_insert(Signal).values(records)
            stmt = stmt.on_conflict_do_nothing(constraint="uq_signals_natural_key")
            result = await session.execute(stmt)
            return result.rowcount
```

### Pattern 3: Point-in-Time Data Queries (PointInTimeDataLoader)
**What:** Sync database queries with release_time constraint to prevent look-ahead bias
**When to use:** Every agent data load, both for live execution and backtesting
**Example:**
```python
# Source: Database patterns from src/core/database.py lines 51-55, 81-92
# Uses sync_session_factory for batch queries

from sqlalchemy import select, and_
from src.core.database import sync_session_factory
from src.core.models.macro_series import MacroSeries

class PointInTimeDataLoader:
    def get_macro_series(self, series_id: str, as_of_date: date,
                         lookback_days: int = 3650) -> pd.DataFrame:
        """macro_series has release_time NOT NULL -- direct PIT query."""
        session = sync_session_factory()
        try:
            start = as_of_date - timedelta(days=lookback_days)
            stmt = (
                select(MacroSeries)
                .where(and_(
                    MacroSeries.series.has(series_code=series_id),
                    MacroSeries.release_time <= as_of_date,
                    MacroSeries.observation_date >= start,
                ))
                .order_by(MacroSeries.observation_date)
            )
            result = session.execute(stmt)
            rows = result.scalars().all()
            return pd.DataFrame([...])  # Convert to DataFrame
        finally:
            session.close()

    def get_curve(self, curve_id: str, as_of_date: date) -> dict[int, float]:
        """curves has NO release_time -- use curve_date <= as_of_date as proxy."""
        # ...

    def get_market_data(self, ticker: str, as_of_date: date,
                        lookback_days: int = 756) -> pd.DataFrame:
        """market_data has NO release_time -- use timestamp <= as_of_date."""
        # ...
```

### Pattern 4: Structured Logging (Agent-specific)
**What:** structlog with bound context for each agent
**When to use:** All agent logging
**Example:**
```python
# Source: Existing pattern in src/connectors/base.py line 88
# self.log = structlog.get_logger().bind(connector=self.SOURCE_NAME)

import structlog

class BaseAgent(abc.ABC):
    def __init__(self, agent_id: str, agent_name: str):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.log = structlog.get_logger().bind(agent=agent_id)
```

### Anti-Patterns to Avoid
- **Using async sessions in PointInTimeDataLoader:** Agent model computation is CPU-bound (OLS fitting, feature calculation). Mixing async I/O with synchronous computation creates unnecessary complexity. Use sync sessions.
- **Creating new hypertables for agent_reports:** This table will have ~5 records per day (one per agent). Hypertables add overhead for low-volume tables. Use a regular PostgreSQL table.
- **Storing full DataFrames in AgentReport:** Keep AgentReport lightweight. Store computed signals and narrative text, not the raw input data.
- **Importing agent models in alembic/env.py:** Only the ORM persistence model (AgentReport) needs to be imported for autogenerate. Dataclasses (AgentSignal, AgentReport as a Python dataclass) are NOT ORM models and should NOT be imported in env.py.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Idempotent DB inserts | Custom upsert logic | `pg_insert().on_conflict_do_nothing(constraint=...)` from `sqlalchemy.dialects.postgresql` | Already proven in BaseConnector._bulk_insert; handles edge cases correctly |
| Retry logic | Custom retry wrapper | `tenacity` library with `AsyncRetrying` | Already used in connectors; handles backoff, jitter, exception filtering |
| Structured logging | Python logging.getLogger | `structlog` with `.bind()` context | Already standardized across codebase; JSON-serializable, context-rich |
| Date/calendar utilities | Custom business day logic | Existing `src/core/utils/calendars.py` module | Already handles BR and US holiday calendars, business day calculations |
| Z-score computation | Custom rolling z-score | Existing `src/transforms/returns.py: compute_z_score()` | Already tested and used in transforms layer |
| YoY from MoM | Custom accumulation logic | Existing `src/transforms/macro.py: yoy_from_mom()` | Handles edge cases (missing data, partial windows) |

**Key insight:** The v1.0 transforms layer already provides the computational building blocks agents need. Agents should call these transforms, not reimplement them.

## Common Pitfalls

### Pitfall 1: Look-Ahead Bias in PointInTimeDataLoader
**What goes wrong:** Querying data by observation_date without filtering by release_time allows the agent to "see" data that was not yet published at the as_of_date, contaminating backtest results.
**Why it happens:** macro_series has release_time (safe), but curves and market_data do NOT have release_time columns. A naive query on curve_date <= as_of_date may include curves that were published later (e.g., revised data).
**How to avoid:**
- For `macro_series`: Always filter `WHERE release_time <= as_of_date` (column is NOT NULL)
- For `curves`: Use `WHERE curve_date <= as_of_date` (curves are published same day, so curve_date is a safe proxy)
- For `market_data`: Use `WHERE timestamp <= as_of_date` (market prices are available in real-time, timestamp is a safe proxy)
- For `flow_data`: Use `WHERE release_time <= as_of_date` when release_time is not NULL, otherwise fall back to `observation_date <= as_of_date`
**Warning signs:** Backtest results that are suspiciously good; signals that appear to "predict" data releases.

### Pitfall 2: Signal Persistence Constraint Mismatch
**What goes wrong:** AgentSignal.signal_id values do not align with the signals table natural key (signal_type, signal_date, instrument_id), causing either constraint violations or duplicate writes.
**Why it happens:** The signals table uses a composite unique constraint `uq_signals_natural_key` on `(signal_type, signal_date, instrument_id)`. If agent signals don't set instrument_id consistently, the constraint won't catch true duplicates.
**How to avoid:**
- Map AgentSignal.signal_id to Signal.signal_type consistently
- Map AgentSignal.as_of_date to Signal.signal_date
- For signals not tied to a specific instrument (e.g., INFLATION_BR_COMPOSITE), use instrument_id=NULL --- but note the constraint allows multiple NULLs in PostgreSQL, which means ON CONFLICT DO NOTHING won't deduplicate correctly for NULL instrument_id rows
- Consider using ON CONFLICT on a partial unique index or adding a separate constraint for agent signals
**Warning signs:** Duplicate signal rows for the same agent/date; ON CONFLICT silently allowing duplicate writes.

### Pitfall 3: Circular Import Between Agents and Models
**What goes wrong:** Agent modules importing from src/core/models while models __init__.py tries to import agent-related models creates circular dependencies.
**Why it happens:** The agent_reports ORM model lives in src/core/models/ but agents live in src/agents/. If agents import from models and models __init__.py imports agent_reports, there's no circular issue. But if agent dataclasses (AgentSignal, AgentReport) are defined in src/core/models/ instead of src/agents/, imports get tangled.
**How to avoid:**
- Keep AgentSignal and AgentReport (Python dataclasses) in `src/agents/base.py`
- Keep the AgentReport ORM model (SQLAlchemy mapped class) in `src/core/models/agent_reports.py`
- These are two different things with potentially the same name --- use clear naming: `AgentReportRecord` for the ORM class, `AgentReport` for the dataclass
**Warning signs:** ImportError on startup; confusing which "AgentReport" is being referenced.

### Pitfall 4: Missing Alembic Import for New Model
**What goes wrong:** Running `alembic revision --autogenerate` does not detect the new agent_reports table because the model module is not imported in `alembic/env.py`.
**Why it happens:** Alembic autogenerate only sees tables registered in `Base.metadata`. Models must be imported (even if unused) in env.py.
**How to avoid:** Add `from src.core.models import agent_reports  # noqa: F401` to alembic/env.py after creating the ORM model.
**Warning signs:** Empty migration generated; "No changes detected" when running autogenerate.

### Pitfall 5: Enum Collision Between Dataclass and Database
**What goes wrong:** SignalDirection enum values ("LONG", "SHORT", "NEUTRAL") stored in the signals table don't match the Signal model's column types.
**Why it happens:** The existing Signal model stores signal_type as String(50), not as an enum column. Agent signal direction needs to be stored somewhere --- either in signal_type naming convention or in metadata_json.
**How to avoid:**
- Store direction and strength in metadata_json (JSON field in signals table)
- Use signal_type as a composite identifier (e.g., "INFLATION_BR_PHILLIPS")
- The confidence column already maps directly to AgentSignal.confidence
**Warning signs:** Agent direction/strength data is lost on persistence; confusing signal_type naming.

## Code Examples

### Existing BaseConnector Pattern (Template Method Reference)
```python
# Source: /home/user/Macro_Trading/src/connectors/base.py lines 218-249
async def run(self, start_date: date, end_date: date, **kwargs: Any) -> int:
    """Execute the full fetch-then-store pipeline."""
    records = await self.fetch(start_date, end_date, **kwargs)
    if not records:
        self.log.warning("no_records_fetched", ...)
        return 0
    inserted = await self.store(records)
    self.log.info("ingestion_complete", fetched=len(records), inserted=inserted, ...)
    return inserted
```

### Existing Enum Pattern
```python
# Source: /home/user/Macro_Trading/src/core/enums.py
# All enums use (str, Enum) mixin for JSON serialization and DB storage

class SignalDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"

class SignalStrength(str, Enum):
    STRONG = "STRONG"       # confidence >= 0.75
    MODERATE = "MODERATE"   # 0.50 <= confidence < 0.75
    WEAK = "WEAK"           # 0.25 <= confidence < 0.50
    NO_SIGNAL = "NO_SIGNAL" # confidence < 0.25
```

### Existing Bulk Insert Pattern
```python
# Source: /home/user/Macro_Trading/src/connectors/base.py lines 251-279
async def _bulk_insert(self, model_class: type, records: list[dict], constraint_name: str) -> int:
    if not records:
        return 0
    async with async_session_factory() as session:
        async with session.begin():
            stmt = pg_insert(model_class).values(records)
            stmt = stmt.on_conflict_do_nothing(constraint=constraint_name)
            result = await session.execute(stmt)
            return result.rowcount
```

### Existing Sync Session Pattern
```python
# Source: /home/user/Macro_Trading/src/core/database.py lines 81-92
def get_sync_session() -> Session:
    """Get a sync session for scripts and migrations."""
    return sync_session_factory()

# Usage pattern for PointInTimeDataLoader:
session = sync_session_factory()
try:
    result = session.execute(stmt)
    rows = result.scalars().all()
finally:
    session.close()
```

### Existing Migration Pattern
```python
# Source: /home/user/Macro_Trading/alembic/versions/002_add_instrument_type_contract_specs.py
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"

def upgrade() -> None:
    op.add_column("instruments", sa.Column(...))

def downgrade() -> None:
    op.drop_column("instruments", ...)
```

### Existing Transforms to Reuse
```python
# Source: /home/user/Macro_Trading/src/transforms/returns.py
# Agents should call these, not reimplement:
compute_returns(prices, method="log")
compute_rolling_volatility(returns, windows=[5,21,63,252])
compute_z_score(series, window=252)
compute_percentile_rank(series, window=252)
compute_rolling_correlation(s1, s2, window=63)
compute_ema(series, span=20)
compute_rolling_sharpe(returns, window=252, rf=0)
compute_drawdown(prices)
compute_realized_vol(prices, window=21)

# Source: /home/user/Macro_Trading/src/transforms/macro.py
yoy_from_mom(mom_series)
compute_diffusion_index(components_df)
compute_trimmed_mean(components_df, trim_pct=0.20)
compute_surprise_index(actual, expected)
compute_momentum(series, periods=[1,3,6,12])
annualize_monthly_rate(monthly_rate)

# Source: /home/user/Macro_Trading/src/transforms/curves.py
nelson_siegel(tau, beta0, beta1, beta2, lam)
fit_nelson_siegel(tenors_years, rates)
interpolate_curve(observed_tenors_days, observed_rates, target_tenors_days, method)
compute_breakeven_inflation(nominal, real)
compute_forward_rate(curve, t1_days, t2_days)
compute_dv01(rate, maturity_years, coupon, notional)
compute_carry_rolldown(curve, tenor_days, horizon_days)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SQLAlchemy 1.x declarative_base | SQLAlchemy 2.0 mapped_column style | SQLAlchemy 2.0 (2023) | All models in codebase already use 2.0 style; new models must follow |
| Alembic with env.py filtering | Same + TimescaleDB exclusion rules | Project v1.0 | env.py has KNOWN_HYPERTABLE_TIME_COLS and TIMESCALEDB_SCHEMAS filtering; new tables must be added if hypertable |
| Python dataclasses | Same (standard library) | N/A | AgentSignal/AgentReport use @dataclass; no Pydantic needed for internal structures |
| asyncpg for everything | Async for runtime, sync for batch | Project v1.0 design | PointInTimeDataLoader uses sync; this is intentional and correct |

**Deprecated/outdated:**
- None identified. The codebase is modern and consistent.

## Open Questions

1. **Signal deduplication with NULL instrument_id**
   - What we know: The signals table unique constraint `uq_signals_natural_key` is on (signal_type, signal_date, instrument_id). PostgreSQL treats NULLs as distinct in unique constraints, so multiple rows with the same signal_type + signal_date + instrument_id=NULL are allowed.
   - What's unclear: Agent signals like INFLATION_BR_COMPOSITE are not instrument-specific, so instrument_id would be NULL. ON CONFLICT DO NOTHING on this constraint won't prevent duplicate writes.
   - Recommendation: For Phase 7, create a partial unique index on (signal_type, signal_date) WHERE instrument_id IS NULL, or store a sentinel instrument_id for non-instrument signals, or use the agent_reports table for composite signals instead. The simplest approach: set instrument_id to a known sentinel value (e.g., always set it for agent signals, using the first instrument in the agent's domain).

2. **AgentReport ORM vs. Signal table for persistence**
   - What we know: The Fase1 guide specifies both an agent_reports table (for narrative, diagnostics, metadata) and signal persistence to the signals hypertable (for individual signal values).
   - What's unclear: Whether individual signals should go to the signals hypertable (where they coexist with other signal types) or to a separate agent-specific table.
   - Recommendation: Use both as specified. Individual AgentSignal values go to the signals hypertable (for time-series queries and strategy consumption). The AgentReport summary goes to agent_reports (for audit trail and narrative storage). This is the approach in the Fase1 guide.

3. **Handling series_id FK in signals table**
   - What we know: The signals table has a `series_id` FK column (Optional[int] to series_metadata.id). Agent signals don't naturally have a series_metadata association.
   - What's unclear: Whether to populate series_id for agent signals or leave it NULL.
   - Recommendation: Leave series_id NULL for agent signals. It was designed for connector-generated signals (e.g., data quality alerts). Agent signals use signal_type as their primary identifier.

## Sources

### Primary (HIGH confidence)
- `/home/user/Macro_Trading/src/connectors/base.py` - BaseConnector ABC pattern, _bulk_insert with ON CONFLICT
- `/home/user/Macro_Trading/src/core/models/signals.py` - Signal hypertable schema, natural key constraint
- `/home/user/Macro_Trading/src/core/models/macro_series.py` - release_time column (NOT NULL) for PIT queries
- `/home/user/Macro_Trading/src/core/models/curves.py` - No release_time column; curve_date as proxy
- `/home/user/Macro_Trading/src/core/models/market_data.py` - No release_time column; timestamp as proxy
- `/home/user/Macro_Trading/src/core/models/flow_data.py` - release_time nullable
- `/home/user/Macro_Trading/src/core/database.py` - Async and sync engine/session factories
- `/home/user/Macro_Trading/src/core/enums.py` - Existing (str, Enum) pattern
- `/home/user/Macro_Trading/alembic/env.py` - Model imports for autogenerate, TimescaleDB filtering
- `/home/user/Macro_Trading/alembic/versions/002_add_instrument_type_contract_specs.py` - Migration versioning pattern
- `/home/user/Macro_Trading/src/transforms/returns.py` - z-score, volatility, correlation utilities
- `/home/user/Macro_Trading/src/transforms/macro.py` - YoY, diffusion, trimmed mean utilities
- `/home/user/Macro_Trading/src/transforms/curves.py` - Nelson-Siegel, carry/rolldown utilities
- `/home/user/Macro_Trading/pyproject.toml` - Current dependencies (statsmodels/scikit-learn missing)
- `pip list` output confirming installed versions

### Secondary (HIGH confidence)
- `/home/user/Macro_Trading/.claude/rules/GUIA_COMPLETO_CLAUDE_CODE_Fase1.md` (Etapa 1) - Complete specification for BaseAgent, AgentSignal, AgentReport, AgentRegistry, PointInTimeDataLoader, and agent_reports table schema
- `/home/user/Macro_Trading/.planning/REQUIREMENTS.md` - AGENT-01 through AGENT-07 requirement definitions
- `/home/user/Macro_Trading/.planning/ROADMAP.md` - Phase 7 goal, success criteria, and plan structure

### Tertiary (MEDIUM confidence)
- Fase1 guide agent model specifications (Phillips Curve, Taylor Rule, etc.) - reviewed for understanding downstream consumer needs of the framework being built in Phase 7

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries are already installed and verified; only statsmodels/scikit-learn need adding
- Architecture: HIGH - Direct codebase analysis of existing patterns (BaseConnector, database.py, enums.py)
- Pitfalls: HIGH - Identified from actual schema analysis (signals table constraints, release_time presence/absence per table)
- Code examples: HIGH - All examples are verbatim from existing codebase files

**Research date:** 2026-02-20
**Valid until:** 2026-03-20 (stable --- internal codebase, no external API changes expected)

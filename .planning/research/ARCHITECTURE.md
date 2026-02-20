# Architecture Patterns: v2.0 Quantitative Models & Agents

**Domain:** Global macro fund -- analytical agents, backtesting, strategies, risk management
**Researched:** 2026-02-20
**Confidence:** HIGH (builds on proven v1.0 patterns, academic references well-established)

## System Overview

```
                          DAILY PIPELINE (orchestrated)
                                    |
    ┌───────────────────────────────┼───────────────────────────────┐
    |                               |                               |
    v                               v                               v
┌─────────┐  ┌──────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────┐
│ INGEST  │->│ QUALITY  │->│   AGENTS     │->│  STRATEGIES  │->│  RISK  │
│ (conn.) │  │ (checks) │  │ (5 models)   │  │ (8 initial)  │  │ (VaR)  │
└─────────┘  └──────────┘  └──────────────┘  └──────────────┘  └────────┘
    |               |              |                 |               |
    v               v              v                 v               v
┌─────────────────────────────────────────────────────────────────────────┐
│                      TimescaleDB (point-in-time)                        │
│  macro_series | curves | market_data | flow_data | signals | agent_rpts│
└─────────────────────────────────────────────────────────────────────────┘
    |                                                               |
    v                                                               v
┌──────────────┐                                         ┌──────────────┐
│  FastAPI REST │                                         │   Dashboard  │
│  (12+ v1 +   │                                         │  (HTML/CDN)  │
│   new v2 eps)│                                         │              │
└──────────────┘                                         └──────────────┘
```

### Layer Architecture (Medallion Extended)

| Layer | v1.0 (Complete) | v2.0 (This Milestone) |
|-------|----------------|-----------------------|
| **Bronze** | 11 connectors, raw ingestion | No changes needed |
| **Silver** | Transforms (curves, returns, macro, vol_surface) | No changes needed |
| **Gold** | FastAPI REST, Redis cache | New endpoints for agents/signals/risk |
| **Agent** | -- | 5 analytical agents consuming Silver/Gold data |
| **Strategy** | -- | 8 trading strategies consuming agent signals |
| **Risk** | -- | VaR, limits, circuit breakers, portfolio construction |
| **Pipeline** | Backfill orchestrator | Daily orchestration pipeline |
| **Presentation** | -- | HTML dashboard (single-file, CDN-based) |

## Component Boundaries

### Agent Layer

```
src/agents/
├── base.py                    # BaseAgent ABC (Template Method)
├── registry.py                # AgentRegistry -- ordered execution
├── data_loader.py             # PointInTimeDataLoader (single DB access layer)
├── narrative.py               # LLM narrative generation (Claude API + fallback)
├── inflation/
│   ├── agent.py               # InflationAgent(BaseAgent)
│   ├── features.py            # InflationFeatureEngine
│   └── models.py              # PhillipsCurve, IpcaBottomUp, SurpriseModel, PersistenceModel
├── monetary/
│   ├── agent.py               # MonetaryPolicyAgent(BaseAgent)
│   ├── features.py            # MonetaryFeatureEngine
│   └── models.py              # TaylorRule, KalmanFilterRStar, SelicPathModel, TermPremium
├── fiscal/
│   ├── agent.py               # FiscalAgent(BaseAgent)
│   ├── features.py            # FiscalFeatureEngine
│   └── models.py              # DebtSustainability, FiscalImpulse, FiscalDominanceRisk
├── fx/
│   ├── agent.py               # FxEquilibriumAgent(BaseAgent)
│   ├── features.py            # FxFeatureEngine
│   └── models.py              # BeerModel, CarryToRisk, FlowModel, CipBasisModel
└── cross_asset/
    ├── agent.py               # CrossAssetAgent(BaseAgent)
    └── models.py              # RegimeDetection, CorrelationAnalysis, RiskSentimentIndex
```

### Strategy Layer

```
src/strategies/
├── base.py                    # BaseStrategy ABC
├── rates_br/
│   ├── carry_rolldown.py      # RATES-01: DI Curve Carry & Roll-Down
│   ├── taylor_misalignment.py # RATES-02: Taylor Rule Misalignment
│   ├── curve_slope.py         # RATES-03: Flattener / Steepener
│   └── us_rates_spill.py      # RATES-04: US Rates Spillover
├── inflation_br/
│   └── breakeven_trade.py     # INF-01: Breakeven Inflation Trade
├── fx_br/
│   └── fx_carry_fundamental.py # FX-01: Carry & Fundamental
├── cupom_cambial/
│   └── cip_basis.py           # CUPOM-01: CIP Basis Mean Reversion
└── sovereign/
    └── fiscal_risk_premium.py # SOV-01: Fiscal Risk Premium
```

### Risk Layer

```
src/risk/
├── var.py                     # VaR: Historical, Parametric, Monte Carlo
├── limits.py                  # Position limits, leverage, loss limits
├── drawdown.py                # Circuit breakers (3 levels)
└── monitor.py                 # Aggregate risk monitoring and reporting
```

### Portfolio Layer

```
src/portfolio/
├── aggregator.py              # Signal aggregation across agents & strategies
├── constructor.py             # Portfolio construction (risk-parity-inspired)
└── allocator.py               # Capital allocation, constraint enforcement
```

### Backtesting Engine

```
src/backtesting/
├── engine.py                  # BacktestEngine (event-driven, PIT-correct)
├── portfolio.py               # Portfolio tracking, P&L, trade log
├── metrics.py                 # Sharpe, Sortino, Calmar, drawdown, win rate
└── report.py                  # Text reports + matplotlib charts
```

## Architectural Patterns

### Pattern 1: BaseAgent Template Method

**What:** Abstract base class with `run()` orchestrating 4 abstract steps.

**Why:** All 5 agents share the same lifecycle: load data, compute features, run models, generate narrative. The Template Method pattern enforces this structure while allowing each agent to customize each step.

```python
class BaseAgent(ABC):
    def run(self, as_of_date: date) -> AgentReport:
        """Template Method -- fixed sequence, variable steps."""
        data = self.load_data(as_of_date)          # abstract
        features = self.compute_features(data)       # abstract
        signals = self.run_models(features)          # abstract
        narrative = self.generate_narrative(signals, features)  # abstract
        self._persist_signals(signals)               # concrete
        return AgentReport(...)

    @abstractmethod
    def load_data(self, as_of_date: date) -> dict: ...
    @abstractmethod
    def compute_features(self, data: dict) -> dict: ...
    @abstractmethod
    def run_models(self, features: dict) -> list[AgentSignal]: ...
    @abstractmethod
    def generate_narrative(self, signals: list, features: dict) -> str: ...
```

**Critical constraint:** `load_data()` MUST use `PointInTimeDataLoader` with `release_time <= as_of_date`. This is the single enforcement point for look-ahead prevention.

### Pattern 2: PointInTimeDataLoader (Single Data Access Layer)

**What:** All agents and strategies access the database exclusively through this class.

**Why:** Centralizing PIT logic in one place eliminates the risk of individual agents accidentally querying future data. Every SQL query includes `WHERE release_time <= :as_of_date`.

```python
class PointInTimeDataLoader:
    def get_macro_series(self, series_id: str, as_of_date: date,
                         lookback_days: int = 3650) -> pd.DataFrame:
        """Only returns data where release_time <= as_of_date."""

    def get_curve(self, curve_id: str, as_of_date: date) -> dict[int, float]:
        """Most recent curve available at as_of_date."""

    def get_market_data(self, ticker: str, as_of_date: date,
                        lookback_days: int = 756) -> pd.DataFrame:
        """OHLCV where time <= as_of_date."""
```

**Sync execution:** Uses sync SQLAlchemy sessions (not async) because agent models use numpy/pandas/statsmodels which are all synchronous. Forcing async here adds complexity with no benefit.

### Pattern 3: Agent Dependency Chain (Sequential Execution)

**What:** Agents run in a fixed order: inflation -> monetary -> fiscal -> fx -> cross_asset.

**Why:** Cross-asset depends on outputs of all other agents. Monetary benefits from inflation state. FX benefits from fiscal and monetary signals. Running them sequentially (not in parallel) is correct because:
1. Total agent runtime is 5-15 seconds (no parallelism benefit)
2. Later agents may consume signals from earlier agents
3. Debugging sequential execution is trivially easier

```python
AGENT_ORDER = [
    "inflation_agent",     # independent
    "monetary_agent",      # reads inflation signals
    "fiscal_agent",        # independent (but benefits from monetary context)
    "fx_agent",            # reads monetary + fiscal signals
    "cross_asset_agent",   # reads ALL other agent signals
]
```

### Pattern 4: AgentSignal as Universal Currency

**What:** All agents produce `AgentSignal` dataclass instances. All strategies consume them.

```python
@dataclass
class AgentSignal:
    signal_id: str            # e.g., "INFLATION_BR_PHILLIPS"
    agent_id: str             # e.g., "inflation_agent_v1"
    timestamp: datetime
    as_of_date: date
    direction: SignalDirection  # LONG, SHORT, NEUTRAL
    strength: SignalStrength    # STRONG, MODERATE, WEAK, NO_SIGNAL
    confidence: float          # 0.0 to 1.0
    value: float               # numerical (z-score or model output)
    horizon_days: int          # signal horizon
    metadata: dict             # model-specific details
```

**Why:** Uniform signal format means strategies don't need to understand agent internals. Signal aggregation operates on a homogeneous collection. Persistence to the `signals` hypertable is straightforward.

### Pattern 5: Strategy-Agent Decoupling via Signals Table

**What:** Agents write signals to the `signals` hypertable. Strategies read signals from it.

**Why:** This decouples agent computation from strategy execution:
- Agents can be rerun independently
- Strategies can be tested with historical signals
- New strategies don't require agent changes
- Backtest engine can replay historical signals

### Pattern 6: Event-Driven Backtesting with PIT Enforcement

**What:** BacktestEngine iterates through calendar dates, calling strategy.generate_signals(as_of_date) at each rebalance point, and marks to market daily between rebalances.

```python
for current_date in all_business_days:
    portfolio.mark_to_market(current_date, data_loader)
    if current_date in rebalance_dates:
        signals = strategy.generate_signals(current_date)  # PIT-correct
        targets = strategy.signals_to_positions(signals, portfolio)
        portfolio.rebalance(targets, current_date, costs)
```

**Why custom engine (not Backtrader/Zipline):** Macro strategies trade curves, rates, and macro signals -- not equities. Off-the-shelf backtesters assume OHLCV bar data and equity-style execution. Building ~300 lines of custom engine is simpler than fighting framework assumptions.

### Pattern 7: Circuit Breakers (3-Level Drawdown Protection)

```
Level 0: Normal operation
Level 1 (-3% drawdown): Reduce all positions by 25%
Level 2 (-5% drawdown): Reduce all positions by 50%
Level 3 (-8% drawdown): Close all positions, require manual review
```

**Why 3 levels:** Graduated response prevents panic selling at shallow drawdowns while providing hard stops at dangerous levels. The -8% threshold aligns with macro fund industry norms.

## Data Flow Diagrams

### Daily Pipeline Flow

```
09:00  ┌─────────────────┐
       │  1. INGEST       │  fetch_latest() on all 11 connectors
       │  (5-10 min)      │  → bronze tables (macro_series, curves, market_data)
       └────────┬──────────┘
               v
09:10  ┌─────────────────┐
       │  2. QUALITY      │  DataQualityChecker.run_all_checks()
       │  (1-2 min)       │  → score, stale series, flagged values
       └────────┬──────────┘
               v
09:15  ┌─────────────────┐
       │  3. AGENTS       │  AgentRegistry.run_all(as_of_date)
       │  (5-15 sec)      │  inflation → monetary → fiscal → fx → cross_asset
       │                   │  → signals table, agent_reports table
       └────────┬──────────┘
               v
09:16  ┌─────────────────┐
       │  4. AGGREGATE    │  SignalAggregator.aggregate()
       │  (1-2 sec)       │  → consensus, conflict detection
       └────────┬──────────┘
               v
09:17  ┌─────────────────┐
       │  5. STRATEGIES   │  ALL_STRATEGIES[sid].generate_signals(as_of_date)
       │  (2-5 sec)       │  → strategy_signals table
       └────────┬──────────┘
               v
09:18  ┌─────────────────┐
       │  6. PORTFOLIO    │  PortfolioConstructor.construct_portfolio()
       │  (1-2 sec)       │  → target weights by ticker
       └────────┬──────────┘
               v
09:19  ┌─────────────────┐
       │  7. RISK         │  RiskMonitor.generate_risk_report()
       │  (2-3 sec)       │  → VaR, limits, circuit breakers, stress tests
       └────────┬──────────┘
               v
09:20  ┌─────────────────┐
       │  8. REPORT       │  NarrativeGenerator.generate_daily_brief()
       │  (5-10 sec)      │  → daily brief (LLM or template)
       └──────────────────┘
```

Total pipeline: ~12-15 minutes (dominated by data ingestion network I/O).

### Agent Signal Flow

```
                    ┌──────────────┐
                    │   macro_series│
                    │   curves      │
                    │   market_data │
                    │   flow_data   │
                    └──────┬───────┘
                           │ PointInTimeDataLoader
                           │ (WHERE release_time <= as_of_date)
                           v
        ┌─────────────────────────────────────────┐
        │              AGENT LAYER                 │
        │                                          │
        │  Inflation ──┐                           │
        │  Monetary  ──┼──> Cross-Asset ──> signals│
        │  Fiscal    ──┤       (regime,            │
        │  FX        ──┘        sentiment)         │
        └─────────────────────────┬────────────────┘
                                  │ AgentSignal objects
                                  │ persisted to signals table
                                  v
        ┌─────────────────────────────────────────┐
        │            STRATEGY LAYER                │
        │                                          │
        │  RATES-01..04  INF-01  FX-01  CUPOM-01  │
        │  SOV-01                                  │
        │  Each reads agent signals + market data  │
        └─────────────────────────┬────────────────┘
                                  │ StrategyPosition objects
                                  v
        ┌─────────────────────────────────────────┐
        │         PORTFOLIO / RISK LAYER           │
        │                                          │
        │  Aggregation → Construction → VaR        │
        │  → Limits → Circuit Breakers → Report    │
        └──────────────────────────────────────────┘
```

## New Database Tables (v2.0)

| Table | Type | Purpose |
|-------|------|---------|
| `agent_reports` | Regular | Store agent run metadata, narrative, diagnostics |
| `strategy_signals` | Hypertable | Store strategy-level target positions over time |
| `backtest_results` | Regular | Store backtest metrics and equity curves |

These join the existing 10 tables (instruments, market_data, curves, macro_series, vol_surfaces, fiscal_data, flow_data, signals, series_metadata + alembic_version).

## Anti-Patterns to Avoid

### Anti-Pattern 1: Async Agents
**What:** Making agent models async to match the FastAPI async style.
**Why bad:** Agent models use numpy, pandas, statsmodels, scipy -- all synchronous. Wrapping them in async adds complexity, hides blocking calls, and provides zero performance benefit since agent execution is CPU-bound not I/O-bound.
**Instead:** Use sync SQLAlchemy sessions in agents. Reserve async for data ingestion and API endpoints.

### Anti-Pattern 2: Shared Mutable State Between Agents
**What:** Agents directly modifying shared data structures that other agents read.
**Why bad:** Creates implicit dependencies, makes testing impossible, breaks backtesting reproducibility.
**Instead:** Agents communicate exclusively through the signals table. Each agent writes; later agents read.

### Anti-Pattern 3: Complex Model Ensembles Before Simple Models Work
**What:** Building Kalman Filter or HMM before basic OLS regression is validated.
**Why bad:** Complex models have more failure modes (convergence, overfitting, label switching). If the simple model doesn't produce reasonable results, the complex one won't either.
**Instead:** Implement in order of complexity: OLS first, then rolling OLS, then state-space models. Each must pass sanity checks before adding complexity.

### Anti-Pattern 4: Backtest Engine Accessing Database Directly
**What:** Strategy code making direct SQL queries instead of going through PointInTimeDataLoader.
**Why bad:** Bypasses PIT enforcement, creates look-ahead risk, makes backtests unreproducible.
**Instead:** All data access goes through PointInTimeDataLoader, which is the only class that touches the database for agent/strategy computations.

### Anti-Pattern 5: Monolithic Daily Pipeline Script
**What:** One giant function that does everything from ingestion to reporting.
**Why bad:** Any failure restarts the entire pipeline. Individual steps can't be tested or rerun.
**Instead:** Each pipeline step is an independent function that can be called individually. The orchestrator (`daily_run.py`) sequences them but each is self-contained.

## Scalability Considerations

| Concern | Current (v2.0) | Future (v3.0+) |
|---------|----------------|-----------------|
| Agent execution time | 5-15 sec total (5 sequential agents) | Parallelize independent agents if needed |
| Backtest speed | ~2 min for 10-year single strategy | Precompute feature matrices, cache |
| Data volume | ~250K rows in macro_series | TimescaleDB compression handles millions |
| API throughput | Single uvicorn process, ~100 req/s | Add workers, Redis response cache |
| Dashboard updates | Manual refresh / 60s auto-refresh | WebSocket push (v3.0) |
| Strategy count | 8 strategies | 25+ strategies (v3.0), still sequential is fine |
| Risk computation | ~2 sec for full VaR + stress | Pre-cache daily, recompute on position change |

## Build Order Recommendation

```
Phase 7:  Agent Framework + Data Loader + Inflation Agent (first agent proves pattern)
Phase 8:  Remaining 4 Agents (Monetary, Fiscal, FX, Cross-Asset)
Phase 9:  Backtesting Engine (needed to validate agents produce useful signals)
Phase 10: 8 Trading Strategies (consume agent signals)
Phase 11: Signal Aggregation + Portfolio Construction + Risk Management
Phase 12: Daily Pipeline + LLM Narrative + Dashboard + Integration Tests
```

**Rationale:** Build agents first because strategies depend on agent signals. Build backtesting before strategies so strategies can be validated as they're built. Risk and portfolio come after strategies exist. Dashboard and pipeline are integration layers that come last.

## Sources

- Taylor, J.B. (1993) "Discretion versus policy rules in practice" -- Taylor Rule
- Laubach, T. & Williams, J.C. (2003) "Measuring the Natural Rate of Interest" -- Kalman Filter r-star
- Clark, P. & MacDonald, R. (1998) "Exchange Rates and Economic Fundamentals" -- BEER model
- Hamilton, J.D. (1989) "A New Approach to the Economic Analysis of Nonstationary Time Series" -- HMM regime switching
- IMF (2013) "Staff Guidance Note for Public Debt Sustainability Analysis" -- DSA framework
- statsmodels documentation (Context7, verified 2026-02-20) -- OLS, UnobservedComponents, state-space
- hmmlearn documentation (PyPI, verified 2026-02-20) -- GaussianHMM
- Anthropic Python SDK documentation -- AsyncAnthropic client

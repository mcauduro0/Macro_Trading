# Feature Research: Macro Trading Data Infrastructure

**Domain:** Quantitative macro trading data platform (Brazil + US axis)
**Researched:** 2026-02-19
**Confidence:** HIGH (domain well-understood, project context is specific and detailed)

## Feature Landscape

### Table Stakes (System Is Useless Without These)

Features that the ~25 downstream strategies and AI agents will assume exist. Missing any of these means the data layer cannot serve its purpose.

#### TS-1: Multi-Source Data Ingestion (11+ Connectors)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| BCB SGS connector (~50 series) | Core Brazilian macro data: IPCA, Selic, GDP, industrial production, credit, employment | MEDIUM | Use `python-bcb` library (v0.3.3). Handles JSON web service. Must parse comma decimal separator ("1.234,56"). ~18,000 series available in SGS. |
| FRED connector (~50 series) | Core US macro data: CPI, PCE, NFP, rates, credit spreads, fiscal | MEDIUM | Use `fredapi` PyPI package. Supports vintage/revision queries via ALFRED real-time endpoints. 840,000+ series available. FRED API key required (free). |
| BCB Focus connector (expectations) | Market expectations for IPCA, Selic, GDP, FX by horizon. Published weekly (Mondays). Critical for monetary policy agent. | MEDIUM | Use `python-bcb` Expectativas class (OData API). Need to handle multiple horizons (current year, next year, 12-month, 4-year). |
| B3/Tesouro Direto connector (DI curve, NTN-B) | DI swap curve for BRL rates, NTN-B for real rates and breakeven inflation. Foundation of all rates strategies. | HIGH | BCB SGS series #7805-7816 for DI swap rates (12 tenors). Tesouro Direto JSON API for NTN-B prices. PYield library available for validation but build custom for control. |
| IBGE SIDRA connector (IPCA components) | Disaggregated IPCA by 9 groups with weights. Essential for inflation agent's diffusion/trimmed-mean analysis. | MEDIUM | SIDRA API is REST/JSON. Need to map IBGE table codes to component weights. Update ~15 days after reference month. |
| STN Fiscal connector | Primary balance, gross/net debt, debt composition by indexer. Drives fiscal agent and sovereign risk analysis. | MEDIUM | STN publishes via portal. Some data available via FRED (Brazil-tagged series). CSV/Excel scraping may be needed for debt composition. |
| CFTC COT connector (positioning) | 12 contracts x 4 categories = 48 series. Positioning is a core signal for FX and rates strategies. | MEDIUM | Use `cot_reports` PyPI package. Disaggregated Futures report. Parse Dealer, Asset Mgr, Leveraged Funds, Other. Published weekly (Fridays, Tuesday close). Note: publication was interrupted Oct-Nov 2025 due to appropriations lapse. |
| US Treasury connector (yield curves) | Nominal, TIPS real, and breakeven curves. Required for cross-market rates analysis and carry strategies. | LOW | Treasury publishes daily XML/CSV. Standard tenors (1M to 30Y). Well-documented format. |
| Yahoo Finance connector (25+ tickers) | FX pairs, equity indices, commodities, ETFs for cross-asset context. Fast, free, daily/intraday. | LOW | Use `yfinance` library. Reliable for daily OHLCV. Rate-limited but sufficient for daily macro. Not suitable as sole source for production prices. |
| BCB PTAX connector (FX fixing) | Official BRL/USD fixing rate. Required for Brazilian FX strategies and marking. | LOW | Use `python-bcb` PTAX class (OData API). MM-DD-YYYY date format (different from SGS DD/MM/YYYY). |
| BCB FX Flow connector | Commercial/financial flows, swap stock. Key signal for BRL positioning analysis. | MEDIUM | BCB publishes via press releases and SGS series. Some data may require scraping BCB press releases. |

**Confidence:** HIGH -- all data sources are publicly documented and have existing Python libraries or well-known API patterns.

#### TS-2: Storage Layer (TimescaleDB Hypertables)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| TimescaleDB hypertables for time-series data | Auto-partitioning by time, compression, efficient range queries. Core of the entire storage layer. | MEDIUM | 7 hypertables: market_data, macro_series, curves, flow_data, fiscal_data, vol_surfaces, signals. Chunk interval selection matters: monthly for daily macro, weekly for intraday. |
| Compression policies on historical chunks | 90%+ storage reduction on historical data. Without this, 15+ years of 200+ series becomes unwieldy. | LOW | TimescaleDB native compression. Set compress_after policy (e.g., 30 days). Compressed data still queryable via standard SQL. |
| Relational metadata tables | Instruments, series definitions, source registry, holidays. Joins with hypertables for context. | LOW | 3 core tables: instruments (~25 rows), series_metadata (150-200+ rows), data_sources (~11 rows). Standard PostgreSQL tables, not hypertables. |
| SQLAlchemy 2.0 async ORM models | Type-safe, async database access. Required for FastAPI integration and modern Python patterns. | MEDIUM | SQLAlchemy 2.0 async engine with asyncpg driver. 10 tables total. Need custom types for TimescaleDB-specific features. |

**Confidence:** HIGH -- TimescaleDB is well-documented for this use case; hypertable design is a solved problem.

#### TS-3: Point-in-Time (PIT) Correctness

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| release_time tracking on macro_series | Prevents look-ahead bias in backtesting. THE critical feature that separates a research-grade data platform from a toy. | HIGH | Every macro observation needs: observation_date (what period), release_time (when published), value. Query pattern: "give me all data that was known as-of date X." Bloomberg charges premium for this. |
| Revision tracking for revised series | NFP, GDP, industrial production are revised 2-3 times. First release != final. Must store all vintages. | HIGH | FRED/ALFRED provides vintage dates via real-time periods (realtime_start, realtime_end). BCB SGS does NOT natively provide revision history -- must capture snapshots over time. This is the hardest PIT problem. |
| Idempotent inserts (ON CONFLICT DO NOTHING) | Safe re-runs of backfill and daily ingestion. Without this, duplicate data corrupts everything. | LOW | PostgreSQL native UPSERT. Use (series_id, observation_date, release_time) as conflict key for macro data. (instrument_id, timestamp) for market data. |

**Confidence:** HIGH -- PIT is THE known hard problem in quant data. FRED/ALFRED provides revision data; BCB does not natively, requiring snapshot-based approach.

#### TS-4: Historical Backfill

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Parameterized backfill orchestrator | Backfill 2010-present for all series. Must be idempotent, resumable, date-range parameterized. | MEDIUM | Accept start_date/end_date parameters. Process in chunks (monthly windows). Throttle API calls to respect rate limits. Log progress for resumability. |
| Seed scripts for instruments and series metadata | Bootstrap the system with 25 instruments and 150-200+ series definitions before any data flows. | LOW | JSON/YAML seed files defining series_code, source, frequency, unit, transform_type. Idempotent: safe to re-run. |
| Business day calendar handling | ANBIMA holidays differ from NYSE. BRL market days != USD market days. Wrong calendar = wrong carry calculations. | MEDIUM | Two calendars: ANBIMA (BR business days) and NYSE (US). Use `pandas_market_calendars` or `exchange_calendars` library. Critical for DI curve tenor mapping and forward rate calculations. |

**Confidence:** HIGH -- backfill patterns are well-established; calendar handling is a known requirement for cross-market systems.

#### TS-5: Core Transforms (Silver Layer)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Returns (daily, weekly, monthly) | Basic building block. Every strategy needs returns. | LOW | Simple: log returns, arithmetic returns. Handle missing data (weekends, holidays) correctly. |
| Rolling statistics (vol, z-score, percentile rank) | Normalize signals across time. z-score of USDBRL implied vol vs. 1Y rolling is a core signal. | LOW | Standard rolling window calculations. Parameterize window (21d, 63d, 252d). Use pandas rolling or numpy for performance. |
| YoY/MoM conversions for macro series | IPCA is monthly; strategies need YoY. GDP is quarterly; need QoQ SAAR. | LOW | Straightforward time-series math. Must handle index-based series (CPI level -> YoY rate). |
| Correlation matrices (rolling) | Cross-asset correlations drive regime detection and risk management. | MEDIUM | Rolling pairwise correlations for configurable asset groups. 252-day standard window. Output as matrix per date. |

**Confidence:** HIGH -- these are textbook quant calculations; the only complexity is doing them correctly at scale.

#### TS-6: Curve Construction (Silver Layer)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Nelson-Siegel curve fitting | Extract level/slope/curvature factors from DI, UST, and NTN-B curves. Core input to rates strategies. | HIGH | Use `nelson_siegel_svensson` library for calibration. Must handle: missing tenors, stale quotes, fitting failures. Store NS parameters (beta0, beta1, beta2, tau) per date. |
| Forward rate calculation | Forward rates from spot curves. Carry and rolldown = core rates strategy signals. | MEDIUM | Bootstrap forward curve from fitted spot curve. Store implied forwards at standard tenors. |
| DV01 / duration calculation | Risk sensitivity per basis point. Required for position sizing across the curve. | MEDIUM | Analytical DV01 from curve shift. Can use QuantLib-Python or custom implementation. |
| Breakeven inflation (NTN-B vs DI nominal) | BEI = nominal - real rate. Core inflation expectations signal. | MEDIUM | Requires matched-maturity interpolation between DI nominal and NTN-B real curves. Nelson-Siegel on both curves enables this. |

**Confidence:** HIGH for Nelson-Siegel fitting (well-documented libraries exist); MEDIUM for DI-specific curve construction (BCB swap series as proxy has known limitations vs. actual DI futures).

#### TS-7: Data Serving API (Gold Layer)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| FastAPI REST endpoints for macro, curves, market data, flows | Agents and strategies consume data via HTTP. Standard interface for all downstream consumers. | MEDIUM | Endpoints: /macro/{series}, /curves/{curve_type}/{date}, /market/{instrument}, /flows/{type}. Use Pydantic models for response validation. Async endpoints with asyncpg. |
| Point-in-time query support in API | Strategies must be able to query "what was known as-of date X" for backtesting. | MEDIUM | Add `as_of` query parameter. Filter by release_time <= as_of. This is the API manifestation of TS-3. |
| Macro dashboard endpoint | Single endpoint returning latest values for key BR + US indicators. Quick health check and overview. | LOW | Aggregate latest values from multiple series. JSON response with indicator name, value, date, change. |

**Confidence:** HIGH -- FastAPI + Pydantic is a mature, well-documented stack for this pattern.

#### TS-8: Data Quality Framework

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Completeness checks | Detect missing observations. A gap in IPCA data = broken inflation agent. | MEDIUM | Per-series expected frequency vs. actual count. Alert on gaps > threshold (e.g., 2x expected interval). Check business day alignment. |
| Freshness monitoring | Detect stale data. If BCB SGS stops updating, strategies must know. | LOW | Track last_updated timestamp per series. Alert if staleness exceeds source publication schedule + buffer. |
| Curve integrity validation | Detect broken curves: negative rates, inverted beyond reason, missing tenors. | MEDIUM | Arbitrage-free checks: no negative nominal rates (within reason), monotonicity checks where expected, tenor count validation. |
| Cross-source consistency | PTAX vs. Yahoo Finance FX rate should agree within tolerance. | LOW | Pairwise comparison of overlapping series from different sources. Alert on divergence > threshold. |

**Confidence:** HIGH -- data quality dimensions are well-defined in the literature; implementation is straightforward per-check.

---

### Differentiators (Competitive Advantage for This System)

Features that elevate this from "a bunch of CSV files" to a research-grade data platform. Not strictly required for day 1, but provide significant value.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **D-1: Macro surprise index** | Measures actual vs. consensus expectations. Core alpha signal. Requires Focus expectations matched to actual releases. | HIGH | Join BCB Focus median expectations to IBGE/BCB actual releases by indicator + reference period. Surprise = (actual - expected) / historical_std. Few open-source implementations exist for Brazilian data. |
| **D-2: Diffusion index from IPCA components** | Breadth of inflation pressure. Not just headline IPCA level but % of components accelerating. | MEDIUM | From 9 IPCA components: compute MoM for each, count share > 0 or > median. Weight by official IBGE weights. |
| **D-3: Trimmed mean IPCA** | Core inflation proxy. Trims extreme components for better trend signal. | MEDIUM | Sort 9 components by MoM change, trim top/bottom N%, re-weight remainder. BCB publishes its own trimmed mean but with lag; computing it independently gives edge. |
| **D-4: Vol surface reconstruction** | Implied vol surface from delta-space quotes. Enables vol strategies (risk reversal, butterfly). | HIGH | Need FX option quotes (may require Bloomberg or paid source). Reconstruct strike-space vol from delta conventions. Interpolation across strikes and tenors. |
| **D-5: Carry/rolldown analytics** | Pre-computed carry and rolldown for every point on DI and UST curves. Core signal for rates strategies. | MEDIUM | Carry = forward rate - spot rate. Rolldown = P&L from curve riding over holding period. Requires clean forward curve from TS-6. |
| **D-6: ANBIMA ETTJ curve integration** | Official reference curves from ANBIMA (Brazilian bond market association). More authoritative than BCB swap proxy. | MEDIUM | ANBIMA publishes pre-interpolated curves daily. Access may require registration. Would replace/supplement BCB swap series for DI curve. |
| **D-7: Data lineage and series catalog** | Know where every number came from, when it was fetched, what transforms were applied. Audit trail for research. | MEDIUM | Metadata table linking raw ingestion -> transforms -> final series. Not a full enterprise data catalog (overkill), but series-level provenance. |
| **D-8: Snapshot-based BCB revision capture** | BCB SGS does not provide revision history natively. Daily snapshots enable building a home-grown "ALFRED for Brazil." | HIGH | Run daily snapshot job capturing current BCB values. Compare to previous day. Store diff as revision. Over time builds vintage dataset. Extremely valuable for PIT-correct Brazilian macro backtesting. Unique -- no public source offers this for Brazilian data. |
| **D-9: Drawdown and regime detection metrics** | Pre-computed drawdowns, high-water marks, and simple regime indicators (vol regime, rate regime). | MEDIUM | Rolling max drawdown, time-in-drawdown. Regime: classify by rolling vol quantile or rate level vs. history. |
| **D-10: Infrastructure health check script** | End-to-end verification: Docker up, DB connected, APIs reachable, recent data present. | LOW | Single script checking: container status, DB connectivity, series freshness, API response. Saves debugging time on cold starts. |

**Confidence:** HIGH for D-1 through D-5 (standard quant analytics); MEDIUM for D-6 (ANBIMA access terms need verification); HIGH for D-7 through D-10.

---

### Anti-Features (Explicitly NOT Building in Phase 0)

Features that seem appealing but would derail the data infrastructure phase with unnecessary complexity.

| Anti-Feature | Why Requested | Why Problematic | What to Do Instead |
|--------------|---------------|-----------------|-------------------|
| **Real-time streaming (Kafka consumers)** | "Everything should be real-time" | Macro data updates daily/weekly/monthly. Real-time adds massive infrastructure complexity (Kafka, consumers, exactly-once semantics) for data that moves once a day. The 25 strategies are research/backtesting focused. | Batch-first architecture. Scheduled daily pulls. Add Kafka in Phase 1+ only if live trading requires sub-minute latency. Keep Kafka in Docker Compose for future but do not build streaming pipelines now. |
| **Full feature store (Feast/Hopsworks)** | "ML models need point-in-time features" | Enterprise feature stores solve online/offline consistency at scale. This is a solo-user system with ~200 series. PIT correctness can be achieved with release_time filtering in SQL. Feature stores add operational overhead without proportional benefit. | Implement PIT via release_time column + as_of query parameter. Revisit feature store only if ML model count exceeds ~50 or online serving latency matters. |
| **Multi-user authentication/RBAC** | "Security best practice" | Solo user. Auth adds development time, testing burden, and operational friction for zero security benefit when running locally. | No auth in Phase 0. Add API key middleware in Phase 1+ if exposing API externally. Full RBAC only if multi-user becomes real. |
| **Frontend dashboard (React)** | "Need to visualize data" | Building a full React dashboard is a separate project. Phase 0 is about data, not visualization. | Use Jupyter notebooks for ad-hoc visualization. The macro dashboard API endpoint (TS-7) provides data; render it in notebooks. Defer React to Phase 1+. |
| **Bloomberg terminal integration** | "Institutional-grade data" | Costs $24k+/year. Free sources cover 90%+ of the needed data. The constraint is explicitly "free data sources only." | Use BCB SGS swap series as DI proxy, Tesouro Direto for NTN-B, Yahoo Finance for market data. Accept limitations (no real-time DI futures, no FX option quotes). |
| **Tick-level or intraday data storage** | "Need high-frequency data" | Macro strategies operate on daily/weekly/monthly frequencies. Tick data = 100-1000x storage, completely different query patterns, and different infrastructure. | Store daily OHLCV only. If specific strategies need intraday, add a separate intraday hypertable in Phase 1+ with distinct compression/retention policies. |
| **Automated strategy execution** | "Connect data directly to execution" | Phase 0 is data infrastructure. Execution requires broker APIs, order management, position tracking, risk limits -- each a major subsystem. | Data layer serves data via API. Strategies consume data but execute via separate system in Phase 1+. |
| **MongoDB for unstructured data** | "Store agent LLM outputs" | No AI agents exist yet (Phase 1+). Adding MongoDB to Phase 0 increases infrastructure complexity for zero immediate value. | Keep MongoDB in Docker Compose definition for future but do not build schemas or pipelines for it. Focus all effort on TimescaleDB. |
| **MinIO object storage** | "Store raw files and backups" | Useful long-term but not needed when data fits in TimescaleDB with compression. Adds another service to maintain. | Keep in Docker Compose for future. Use filesystem or TimescaleDB COPY for raw data archival in Phase 0. |

**Confidence:** HIGH -- these anti-feature decisions are driven by the project context (solo user, research focus, Phase 0 scope, free data sources).

---

## Feature Dependencies

```
[TS-1: Data Ingestion]
    |
    +--requires--> [TS-2: Storage Layer]
    |                  |
    |                  +--requires--> [TS-4: Historical Backfill]
    |                  |
    |                  +--enables--> [TS-8: Data Quality]
    |
    +--enables--> [TS-3: Point-in-Time]
    |                  |
    |                  +--enables--> [D-8: BCB Revision Capture]
    |
    +--enables--> [TS-5: Core Transforms]
    |                  |
    |                  +--requires--> [TS-2: Storage Layer]
    |                  |
    |                  +--enables--> [D-1: Surprise Index]
    |                  +--enables--> [D-2: Diffusion Index]
    |                  +--enables--> [D-3: Trimmed Mean]
    |                  +--enables--> [D-9: Drawdown/Regime]
    |
    +--enables--> [TS-6: Curve Construction]
    |                  |
    |                  +--requires--> [TS-2: Storage Layer]
    |                  +--requires--> B3/Tesouro Direto data (from TS-1)
    |                  |
    |                  +--enables--> [D-5: Carry/Rolldown]
    |
    +--all above--+--> [TS-7: Data Serving API]
                       |
                       +--requires--> [TS-3: PIT support]
                       +--requires--> [TS-5: Transforms]
                       +--requires--> [TS-6: Curves]
```

### Dependency Notes

- **TS-2 (Storage) must come first:** All other features depend on having hypertables and metadata tables defined.
- **TS-1 (Ingestion) requires TS-2:** Connectors need tables to write into.
- **TS-4 (Backfill) requires TS-1 + TS-2:** Uses connectors to fill storage.
- **TS-3 (PIT) is designed into TS-2:** The release_time column is part of the schema, not a bolt-on. Must be in initial schema design.
- **TS-5 and TS-6 (Transforms/Curves) require data to exist:** Run after backfill populates bronze layer.
- **TS-7 (API) is the capstone:** Serves everything above to downstream consumers. Build last.
- **TS-8 (Quality) can be developed in parallel** with TS-1/TS-4: validation rules defined alongside connectors.
- **D-1 (Surprise Index) requires both TS-1 (Focus connector) and TS-5 (transforms):** Cannot compute surprise without both expectations and actuals.
- **D-8 (BCB Revision Capture) requires TS-1 running daily:** Builds vintage dataset over time; value accrues the longer it runs.

---

## MVP Definition

### Launch With (v0.1 -- Minimum Viable Data Platform)

The absolute minimum to prove the data layer works end-to-end.

- [ ] **TS-2: Storage schema** -- 10 tables, 7 hypertables, compression policies, seed data
- [ ] **TS-1 (partial): 4 core connectors** -- BCB SGS, FRED, Yahoo Finance, US Treasury (covers both countries' essential macro + market data)
- [ ] **TS-3: PIT release_time tracking** -- baked into macro_series schema from day 1
- [ ] **TS-4: Historical backfill** -- 2010-present for core 4 connectors
- [ ] **TS-5 (partial): Basic transforms** -- returns, rolling vol, z-scores
- [ ] **TS-7 (partial): 2-3 API endpoints** -- /macro/{series}, /market/{instrument}, /health
- [ ] **D-10: Infrastructure health check** -- verify Docker, DB, API, data freshness

**Rationale:** This subset proves the full pipeline: ingest -> store -> transform -> serve. Everything else builds on this foundation.

### Add After Validation (v0.2 -- Full Connector Suite)

Once the core pipeline is proven, expand data coverage and transforms.

- [ ] **TS-1 (remaining): 7 more connectors** -- BCB Focus, B3/Tesouro Direto, IBGE, STN, CFTC, BCB PTAX, BCB FX Flow
- [ ] **TS-6: Curve construction** -- Nelson-Siegel, forwards, breakeven
- [ ] **TS-5 (remaining): Macro transforms** -- YoY conversions, correlations
- [ ] **TS-8: Data quality framework** -- completeness, freshness, cross-source consistency
- [ ] **D-1: Macro surprise index** -- once Focus + actuals both available
- [ ] **D-2 + D-3: IPCA diffusion + trimmed mean** -- once IBGE SIDRA connected
- [ ] **D-5: Carry/rolldown analytics** -- once curves are constructed

### Future Consideration (v1.0+ -- Beyond Phase 0)

Defer until data infrastructure is solid and AI agents are being built.

- [ ] **D-4: Vol surface reconstruction** -- requires FX option data source (may need paid data)
- [ ] **D-6: ANBIMA ETTJ integration** -- verify access terms first
- [ ] **D-8: BCB revision capture** -- start the daily snapshot job early but analysis tooling is v1.0+
- [ ] **Kafka streaming pipelines** -- only when live trading requires it
- [ ] **MongoDB schemas** -- only when AI agents produce outputs to store
- [ ] **React dashboard** -- only when visualization needs outgrow Jupyter

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority | Phase |
|---------|------------|---------------------|----------|-------|
| TS-2: Storage schema + hypertables | HIGH | MEDIUM | **P0** | v0.1 |
| TS-3: PIT release_time tracking | HIGH | LOW (schema design) | **P0** | v0.1 |
| TS-1 (core 4): BCB SGS, FRED, Yahoo, UST | HIGH | MEDIUM | **P0** | v0.1 |
| TS-4: Historical backfill orchestrator | HIGH | MEDIUM | **P0** | v0.1 |
| TS-5 (basic): Returns, vol, z-scores | HIGH | LOW | **P0** | v0.1 |
| TS-7 (basic): 2-3 API endpoints | HIGH | LOW | **P0** | v0.1 |
| D-10: Infrastructure health check | MEDIUM | LOW | **P0** | v0.1 |
| TS-1 (remaining 7): Focus, B3, IBGE, etc. | HIGH | HIGH | **P1** | v0.2 |
| TS-6: Curve construction (Nelson-Siegel) | HIGH | HIGH | **P1** | v0.2 |
| TS-8: Data quality framework | HIGH | MEDIUM | **P1** | v0.2 |
| TS-5 (macro): YoY, correlations | MEDIUM | LOW | **P1** | v0.2 |
| D-1: Macro surprise index | HIGH | HIGH | **P1** | v0.2 |
| D-2: IPCA diffusion index | MEDIUM | MEDIUM | **P1** | v0.2 |
| D-3: Trimmed mean IPCA | MEDIUM | MEDIUM | **P1** | v0.2 |
| D-5: Carry/rolldown analytics | HIGH | MEDIUM | **P1** | v0.2 |
| D-7: Data lineage / series catalog | MEDIUM | MEDIUM | **P2** | v0.2 |
| D-9: Drawdown / regime metrics | MEDIUM | LOW | **P2** | v0.2 |
| D-8: BCB revision capture | HIGH (long-term) | MEDIUM | **P2** | v0.2+ |
| D-4: Vol surface reconstruction | HIGH | HIGH | **P3** | v1.0+ |
| D-6: ANBIMA ETTJ integration | MEDIUM | MEDIUM | **P3** | v1.0+ |

**Priority key:**
- **P0:** Must have in first deliverable (v0.1). System does not function without these.
- **P1:** Should have in second deliverable (v0.2). Full data coverage and core analytics.
- **P2:** Nice to have in v0.2, can slip to v1.0. Enhances but not required.
- **P3:** Future consideration. Deferred for clear reasons.

---

## Competitor / Reference Platform Feature Analysis

| Feature | QuantConnect | Bloomberg Terminal | Refinitiv/LSEG | Our Approach |
|---------|-------------|-------------------|-----------------|--------------|
| Multi-source macro ingestion | Limited macro; equity-focused | Comprehensive; 300k+ series | Comprehensive; Datastream | 11+ free sources; BR+US focus |
| Point-in-time correctness | Built into LEAN engine | PIT data product (premium) | PIT available (premium) | release_time column + as_of queries |
| Revision tracking | Not native | ALFRED-style via BQL | Available | FRED vintages + home-grown BCB snapshots |
| Yield curve construction | Not applicable | Full curve toolkit | Curve construction available | Nelson-Siegel fitting; BCB swap proxy for DI |
| Positioning data (CFTC) | Not native | CoT data available | Available | CFTC COT direct ingestion |
| Brazilian macro data | Minimal | Comprehensive | Partial | Deep: BCB SGS, Focus, IBGE, STN, B3, ANBIMA |
| Cost | Free tier available | $24k+/year | $22k+/year | Free (all open data sources) |
| Customization | Template-based | BQL queries | Limited | Full code control; custom transforms |

**Key insight:** No existing platform provides deep, free, PIT-correct Brazilian macro data integrated with US macro and cross-asset data. This is the unique value proposition. Bloomberg does this but costs $24k+/year and cannot be customized with AI agent integration.

---

## Sources

### Authoritative (HIGH confidence)
- [FRED API Documentation](https://fred.stlouisfed.org/docs/api/fred/) -- Official FRED API docs
- [ALFRED Vintage Data](https://alfred.stlouisfed.org/) -- Official ALFRED archival data
- [python-bcb on PyPI](https://pypi.org/project/python-bcb/) -- BCB Python library (v0.3.3)
- [python-bcb SGS Documentation](https://wilsonfreitas.github.io/python-bcb/sgs.html) -- SGS module docs
- [PYield on GitHub](https://github.com/crdcj/PYield) -- Brazilian fixed income library
- [nelson_siegel_svensson on GitHub](https://github.com/luphord/nelson_siegel_svensson) -- NSS curve fitting
- [cot_reports on GitHub](https://github.com/NDelventhal/cot_reports) -- CFTC COT data library
- [TimescaleDB Best Practices](https://timeseriesdata.dev/article/Best_practices_for_designing_time_series_data_models_in_TimescaleDB.html) -- Schema design guidance
- [FastAPI Official Docs](https://fastapi.tiangolo.com/) -- Framework documentation
- [fredapi on PyPI](https://pypi.org/project/fredapi/) -- FRED Python client

### Research Context (MEDIUM confidence)
- [Quant 2.0 Architecture](https://altstreet.investments/blog/quant-2-architecture-modern-trading-stack-ai-mlops) -- Modern trading stack overview
- [Arcesium: Macro Hedge Fund Strategies](https://www.arcesium.com/blog/macro-hedge-fund-strategies) -- Data platform requirements
- [Calcbench: PIT Data for Backtesting](https://www.calcbench.com/blog/post/181646867408/quants-point-in-time-data-for-backtesting) -- PIT data importance
- [FactSet: Point-in-Time White Paper](https://insight.factset.com/hubfs/Resources%20Section/White%20Papers/ID11996_point_in_time.pdf) -- PIT methodology
- [ML4Devs: Backfilling Historical Data](https://www.ml4devs.com/what-is/backfilling-data/) -- Idempotent backfill patterns
- [Databricks: Medallion Architecture](https://www.databricks.com/glossary/medallion-architecture) -- Bronze/Silver/Gold pattern
- [Philadelphia Fed: Real-Time Data Set](https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/real-time-data-set-for-macroeconomists) -- Vintage macro data

### Community/Ecosystem (LOW confidence -- verify before relying on)
- [awesome-quant on GitHub](https://github.com/wilsonfreitas/awesome-quant) -- Curated quant library list
- [QuantStart: Securities Master Databases](https://www.quantstart.com/articles/Securities-Master-Databases-for-Algorithmic-Trading/) -- Database design patterns
- [rb3 R Package](https://docs.ropensci.org/rb3/) -- B3 yield curve fetching (R, not Python, but useful reference)

---
*Feature research for: Macro Trading Data Infrastructure (Phase 0)*
*Researched: 2026-02-19*

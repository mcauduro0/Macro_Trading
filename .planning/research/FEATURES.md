# Feature Landscape: v2.0 Quantitative Models & Agents

**Domain:** Global macro fund -- analytical agents, backtesting, strategies, risk management
**Researched:** 2026-02-20
**Confidence:** HIGH (requirements well-defined in PROJECT.md, academic models well-established)

## Table Stakes

Features users expect. Missing = product feels incomplete for a quantitative macro system.

| ID | Feature | Why Expected | Complexity | Notes |
|----|---------|--------------|------------|-------|
| TS-1 | BaseAgent ABC with Template Method | Every agent shares load-compute-signal-narrative cycle | Medium | Pattern proven in v1.0 BaseConnector |
| TS-2 | PointInTimeDataLoader | Prevents look-ahead bias -- the central invariant | Medium | Single class, all agents use it |
| TS-3 | At least 3 analytical agents | Minimum coverage for inflation + rates + FX | High | 5 planned; 3 is the floor for a credible system |
| TS-4 | Backtesting engine (PIT-correct) | Cannot evaluate strategies without backtesting | Medium | Custom, ~300 lines, event-driven |
| TS-5 | At least 4 trading strategies | Minimum diversification across 2+ asset classes | High | 8 planned; 4 is the floor |
| TS-6 | Basic risk metrics (VaR, max DD) | Risk monitoring is non-negotiable for trading | Medium | Historical VaR + parametric Gaussian |
| TS-7 | Signal persistence to database | Signals must be queryable for strategies and audit | Low | Write to existing signals hypertable |
| TS-8 | Daily pipeline orchestrator | Manual runs are not sustainable | Medium | Sequential script, ~200 lines |
| TS-9 | API endpoints for agents/signals | Dashboard and external tools need programmatic access | Medium | 5-8 new FastAPI endpoints |
| TS-10 | Backtest report (text + basic metrics) | Must verify strategies produce valid returns | Low | Sharpe, max DD, win rate, total return |

## Differentiators

Features that set the system apart. Not expected, but highly valued.

| ID | Feature | Value Proposition | Complexity | Notes |
|----|---------|-------------------|------------|-------|
| D-1 | Phillips Curve model for Brazil | Inflation prediction beyond naive extrapolation | Medium | OLS with rolling window; statsmodels |
| D-2 | Kalman Filter r-star estimation | Time-varying neutral rate for Taylor Rule accuracy | High | UnobservedComponents; convergence risk |
| D-3 | BEER model for USDBRL fair value | Fundamental FX valuation beyond PPP | Medium | OLS regression on macro fundamentals |
| D-4 | IMF-style Debt Sustainability Analysis | Fiscal trajectory projection under scenarios | Medium | Spreadsheet math in Python; 4 scenarios |
| D-5 | HMM regime detection (4 states) | Macro regime awareness for position sizing | High | hmmlearn GaussianHMM; label switching risk |
| D-6 | LLM narrative generation (Claude API) | Automated macro commentary from signals | Medium | Anthropic SDK with template fallback |
| D-7 | Signal aggregation with crowding penalty | Prevents herd behavior when all models agree | Low | ~150 lines; confidence-weighted + discount |
| D-8 | Circuit breakers (3-level drawdown) | Systematic risk protection beyond simple stops | Low | Rule-based; triggered by equity curve |
| D-9 | Cross-asset correlation monitoring | Detect correlation breakdowns signaling regime shift | Medium | Rolling correlations; z-score of deviations |
| D-10 | Single-file HTML dashboard | Zero-build-step monitoring for daily operations | Medium | React+Tailwind+Recharts via CDN |
| D-11 | Focus survey surprise integration | Leading indicator for BCB rate path | Low | Reads BCB Focus data already in DB |
| D-12 | Term premium decomposition | Separates rate expectations from risk compensation | Medium | Focus-implied path vs DI curve spread |

## Anti-Features

Features to explicitly NOT build in v2.0.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Live order execution | Research/backtesting focus first; execution is Phase 3+ | Paper trading signals only |
| Reinforcement learning for sizing | Requires massive backtesting infrastructure | Use simple sigmoid(z-score) sizing |
| Bloomberg/Refinitiv real-time feeds | Paid data sources, not needed for daily macro | Free APIs (BCB, FRED, Yahoo) sufficient |
| React SPA with npm build pipeline | Adds Node.js dependency, build complexity | Single HTML file with CDN imports |
| Dagster/Airflow orchestration | Over-engineered for 8-step daily pipeline | Simple Python script (daily_run.py) |
| Monte Carlo VaR with copulas | Complexity not justified for 8-strategy portfolio | Historical + parametric Gaussian VaR |
| NLP pipeline for COPOM/FOMC minutes | Requires web scraping, complex NLP, low signal | LLM can summarize if API key available |
| Multi-user authentication | Solo user for now | No auth in v2.0 |
| Kubernetes deployment | Local Docker Compose is sufficient | Docker Compose (existing) |
| Black-Litterman portfolio optimization | Overkill for 8 strategies; needs Bayesian priors | Inverse-vol risk parity weighting |

## Feature Dependencies

```
BaseAgent ABC ─────────────────────────────────────────────────────────┐
    │                                                                  │
    v                                                                  │
PointInTimeDataLoader ──────────────────────────────────┐              │
    │                                                   │              │
    v                                                   v              v
InflationAgent ──┐                               BacktestEngine   AgentRegistry
MonetaryAgent  ──┤                                    │
FiscalAgent    ──┼── CrossAssetAgent                  v
FxAgent        ──┘       │                     BacktestMetrics
                         │                     BacktestReport
                         v
              SignalAggregator
                    │
                    v
           8 Trading Strategies ── each reads agent signals
                    │
                    v
           PortfolioConstructor
                    │
                    v
        RiskManager (VaR, limits, circuit breakers)
                    │
                    v
           DailyPipeline (orchestrates all above)
                    │
                    v
        LLM Narrative + HTML Dashboard + API Endpoints
```

Key dependency chains:
- Agents depend on: BaseAgent + DataLoader + DB data
- Strategies depend on: Agent signals (persisted) + market data
- BacktestEngine depends on: Strategies + DataLoader (for PIT replay)
- Risk depends on: Portfolio positions + market data
- Dashboard depends on: API endpoints (which depend on everything)

## Agent Detail: Models Per Agent

### Inflation Agent (4 models)
| Model | Academic Basis | Input Features | Output |
|-------|---------------|----------------|--------|
| Phillips Curve | Friedman 1968, Lucas 1972 | Output gap, expectations, FX, commodities | 12M core inflation forecast |
| IPCA Bottom-Up | BCB methodology | 9 IPCA component trends + seasonal | Next-month IPCA MoM |
| Surprise Model | -- | Actual vs Focus median | Surprise z-score |
| Persistence Model | BCB Inflation Report | Diffusion, cores, services | Persistence score 0-100 |

### Monetary Policy Agent (4 models)
| Model | Academic Basis | Input Features | Output |
|-------|---------------|----------------|--------|
| Taylor Rule | Taylor 1993 | r*, inflation gap, output gap, inertia | Implied Selic rate |
| Kalman Filter r* | Laubach-Williams 2003 | Selic, inflation exp., output gap | Time-varying neutral rate |
| Selic Path Model | -- | DI curve, Focus survey | Meeting-by-meeting implied path |
| Term Premium | ACM 2013 (simplified) | DI curve vs Focus expected path | TP by tenor (bps) |

### Fiscal Agent (3 models)
| Model | Academic Basis | Input Features | Output |
|-------|---------------|----------------|--------|
| Debt Sustainability (DSA) | IMF 2013 | Debt/GDP, r-g, primary balance | 5-year debt trajectory |
| Fiscal Impulse | OECD methodology | Structural primary balance change | Impulse (% GDP) |
| Fiscal Dominance Risk | Blanchard 2019, Sargent-Wallace 1981 | r-g gap, debt composition, interest/revenue | Risk score 0-100 |

### FX Equilibrium Agent (4 models)
| Model | Academic Basis | Input Features | Output |
|-------|---------------|----------------|--------|
| BEER Model | Clark-MacDonald 1998 | ToT, rate differential, NFA, productivity | USDBRL fair value |
| Carry-to-Risk | Burnside 2011 | Rate differential / implied vol | Carry attractiveness ratio |
| Flow Model | Froot-Ramadorai 2005 | BCB flows, CFTC positioning | Flow pressure score |
| CIP Basis | Du-Tepper-Verdelhan 2018 | Cupom cambial - SOFR | Basis deviation (bps) |

### Cross-Asset Agent (3 models)
| Model | Academic Basis | Input Features | Output |
|-------|---------------|----------------|--------|
| Regime Detection | Hamilton 1989 | VIX, credit spreads, DXY, flows, curve | Regime (risk-on/off/transition) |
| Correlation Analysis | Longin-Solnik 2001 | 5 key asset pair rolling correlations | Correlation breaks |
| Risk Sentiment Index | -- | VIX, HY, DXY, CFTC, flows, CDS | Sentiment index 0-100 |

## Strategy Detail: 8 Initial Strategies

| ID | Name | Asset Class | Agent Dependency | Signal Type | Rebalance |
|----|------|-------------|-----------------|-------------|-----------|
| RATES-01 | Carry & Roll-Down | RATES_BR | Monetary (term premium) | Carry-to-risk ratio | Monthly |
| RATES-02 | Taylor Misalignment | RATES_BR | Monetary (Taylor Rule) | Policy gap (bps) | Monthly |
| RATES-03 | Curve Slope | RATES_BR | Monetary + Inflation | Cycle position | Monthly |
| RATES-04 | US Rates Spillover | RATES_BR | Monetary (US Fed) | DI-UST spread z-score | Weekly |
| INF-01 | Breakeven Inflation | INFLATION_BR | Inflation (composite) | BEI vs model deviation | Monthly |
| FX-01 | Carry & Fundamental | FX_BR | FX (BEER + carry + flow) | Composite FX score | Weekly |
| CUPOM-01 | CIP Basis Reversion | CUPOM_CAMBIAL | FX (CIP basis) | Basis z-score | Monthly |
| SOV-01 | Fiscal Risk Premium | SOVEREIGN | Fiscal + Cross-Asset | Fiscal-adjusted spread | Monthly |

## MVP Recommendation

### Must Have (blocks everything else)
1. **BaseAgent ABC + PointInTimeDataLoader** -- foundation for all agents
2. **InflationAgent** (proves the agent pattern works end-to-end)
3. **MonetaryPolicyAgent** (Taylor Rule is the most actionable signal)
4. **BacktestEngine** (validates agents produce useful signals)
5. **2-3 Strategies** (RATES-01, RATES-02, FX-01 minimum)
6. **Basic risk** (VaR, max drawdown, position limits)

### Should Have (completes the system)
7. **FiscalAgent + FxAgent + CrossAssetAgent** (complete agent suite)
8. **Remaining 5 strategies** (diversification)
9. **Signal aggregation + portfolio construction**
10. **Daily pipeline orchestrator**

### Nice to Have (enhances but not critical)
11. **LLM narrative generation** (useful but template fallback works)
12. **HTML dashboard** (API + curl is sufficient for v2.0)
13. **Kalman Filter r* estimation** (Taylor Rule works with fixed r*)
14. **HMM regime detection** (rule-based z-score fallback works)

### Defer to v3.0
- Live execution, Dagster orchestration, NLP pipeline, 17 additional strategies, Black-Litterman optimization, multi-user auth, Kubernetes deployment

## Sources

- PROJECT.md v2.0 milestone definition
- GUIA_COMPLETO_CLAUDE_CODE_Fase1.md (20 ETAPAs defining exact feature scope)
- Academic references listed per model above
- Web search: "macro trading backtesting pitfalls 2026" -- parsimony principle

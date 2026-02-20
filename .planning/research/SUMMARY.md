# Research Summary: v2.0 Quantitative Models & Agents

**Project:** Macro Trading System
**Domain:** Global macro fund -- analytical agents, backtesting, strategies, risk management
**Researched:** 2026-02-20
**Overall confidence:** HIGH

## Executive Summary

This milestone adds the analytical and trading layers on top of the completed v1.0 data infrastructure (11 connectors, 250+ series, TimescaleDB, FastAPI). The v2.0 scope includes 5 AI-driven analytical agents, a point-in-time backtesting engine, 8 initial trading strategies, signal aggregation, risk management, and a daily orchestration pipeline.

The technology stack requires 4 new core dependencies: **statsmodels** (>=0.14.6) for econometric models (OLS, Kalman Filter via UnobservedComponents), **hmmlearn** (>=0.3.3) for regime detection, **scikit-learn** (>=1.6) for Ledoit-Wolf covariance estimation in VaR calculations, and **anthropic** (>=0.81.0) for LLM narrative generation. The existing stack (Python 3.11, SQLAlchemy 2.0, FastAPI, pandas, numpy, scipy) remains unchanged.

Three critical architectural decisions drive the design: (1) Build custom backtesting, VaR, and signal aggregation rather than adopting frameworks, because macro strategies trade curves and rates rather than equities and off-the-shelf tools impose wrong assumptions. (2) Use a single `PointInTimeDataLoader` class as the exclusive data access layer for all agents and strategies, enforcing `WHERE release_time <= as_of_date` in every query. (3) Start with simple models (OLS, rule-based z-scores) and add complexity (Kalman Filter, HMM) only after simple versions are validated -- the parsimony principle.

The five most dangerous pitfalls are: look-ahead bias in agent computations (prevented by PointInTimeDataLoader), Kalman Filter convergence failures (mitigated by fixed r-star fallback), HMM label switching (mitigated by rule-based regime fallback), model overfitting to in-sample data (mitigated by walk-forward validation), and LLM hallucination in narratives (mitigated by template-based fallback as primary output).

## Key Findings

**Stack:** 4 new dependencies (statsmodels, hmmlearn, scikit-learn, anthropic) + 3 build-custom decisions (backtester, VaR, signal aggregation) + single-file HTML dashboard via CDN.

**Architecture:** Agent-Strategy-Risk layered architecture with Template Method agents, sequential execution chain, and uniform AgentSignal as communication currency. All data access through PointInTimeDataLoader.

**Critical pitfall:** Look-ahead bias is the single biggest risk. The entire v1.0 `release_time` infrastructure exists to prevent it, but one careless query in an agent model can bypass the protection.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Phase 7: Agent Framework + First Agent** - Build the foundation before scaling
   - Addresses: BaseAgent ABC, PointInTimeDataLoader, AgentSignal, AgentRegistry, InflationAgent (proves the pattern)
   - Avoids: Building all 5 agents before validating the pattern works
   - Research flag: Phillips Curve overfitting risk -- start with 3 features

2. **Phase 8: Remaining 4 Agents** - Complete the agent suite
   - Addresses: MonetaryPolicyAgent, FiscalAgent, FxEquilibriumAgent, CrossAssetAgent
   - Avoids: Kalman Filter convergence (start with fixed r*), HMM label switching (start rule-based)
   - Research flag: NEEDS deeper research if Kalman Filter is attempted

3. **Phase 9: Backtesting Engine** - Validate agents produce useful signals
   - Addresses: BacktestEngine, Portfolio, Metrics, Report
   - Avoids: Building strategies before confirming agents generate meaningful signals
   - Research flag: Standard patterns, unlikely to need additional research

4. **Phase 10: 8 Trading Strategies** - Consume agent signals for trading decisions
   - Addresses: BaseStrategy, 4 rates strategies, 1 inflation, 1 FX, 1 cupom cambial, 1 sovereign
   - Avoids: Strategy-agent coupling (strategies read from signals table, not agent objects)

5. **Phase 11: Signal Aggregation + Portfolio + Risk** - Combine strategies into portfolio
   - Addresses: SignalAggregator, PortfolioConstructor, CapitalAllocator, VaR, limits, circuit breakers
   - Avoids: Black-Litterman complexity (use inverse-vol risk parity instead)

6. **Phase 12: Daily Pipeline + LLM + Dashboard + Tests** - Integration and presentation
   - Addresses: DailyPipeline, NarrativeGenerator, HTML dashboard, API endpoints, integration tests
   - Avoids: Over-engineering pipeline (simple sequential script, not Dagster/Airflow)

**Phase ordering rationale:**
- Agents before strategies (strategies consume agent signals)
- Backtesting before strategies (need to validate agent signals first)
- Risk after strategies (risk operates on portfolio of strategy positions)
- Dashboard/pipeline last (integration layer that depends on everything)
- Agent framework + first agent in same phase (prove pattern works before scaling)

**Research flags for phases:**
- Phase 7: Standard patterns (Template Method, data loader). LOW risk.
- Phase 8: Kalman Filter and HMM are HIGH risk. Use simple fallbacks (fixed r*, rule-based regime) and only attempt complex models after simple versions work.
- Phase 9: Standard patterns (event-driven backtest). LOW risk.
- Phase 10: MEDIUM risk from signal correlation between strategies. Mitigate with crowding penalty.
- Phase 11: MEDIUM risk from VaR underestimation. Use 504-day window.
- Phase 12: LOW risk. Integration and presentation.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | statsmodels, hmmlearn, scikit-learn all verified via Context7/PyPI. Anthropic SDK verified. |
| Features | HIGH | Requirements clearly defined in PROJECT.md and GUIA Fase1. Academic models well-established. |
| Architecture | HIGH | Template Method pattern proven in v1.0 BaseConnector. PIT enforcement design is solid. |
| Pitfalls | HIGH | Kalman Filter and HMM pitfalls well-documented in academic literature and web research. |
| Agent models | MEDIUM | Phillips Curve, Taylor Rule, BEER are textbook. But calibration to Brazilian data needs validation. |
| Backtesting | HIGH | Event-driven PIT backtesting is a solved problem. Custom engine is straightforward. |
| Risk management | HIGH | VaR implementations are standard. Circuit breakers are simple rules. |
| LLM narrative | MEDIUM | Anthropic SDK is well-documented, but output quality depends on prompt engineering. Template fallback ensures minimum quality. |

## Gaps to Address

- **COPOM meeting calendar:** Need a mechanism to load meeting dates dynamically (not hardcoded). Research needed if BCB provides machine-readable calendar.
- **Cupom cambial data quality:** DDI curve data from free sources is sparse. May need proxy from DI + USDBRL NDF implied rate.
- **CDS 5Y Brazil:** Not available from free sources. EMB ETF spread is the best free proxy but imprecise. Strategy SOV-01 may need adjustment.
- **Vol surface for USDBRL:** The vol_surfaces table exists but free data for USDBRL option implied vols is limited. FX-related strategies may need to use realized vol instead.
- **Walk-forward validation infrastructure:** The backtest engine should support walk-forward out-of-sample testing, but this is an enhancement over basic backtesting. Can be added incrementally.

## Sources

- `/home/user/Macro_Trading/.planning/research/STACK.md` -- Technology recommendations (verified 2026-02-20)
- `/home/user/Macro_Trading/.planning/research/ARCHITECTURE.md` -- Architecture patterns (verified 2026-02-20)
- `/home/user/Macro_Trading/.planning/research/FEATURES.md` -- Feature landscape (verified 2026-02-20)
- `/home/user/Macro_Trading/.planning/research/PITFALLS.md` -- Domain pitfalls (verified 2026-02-20)
- `/home/user/Macro_Trading/.planning/PROJECT.md` -- v2.0 milestone definition
- `/home/user/Macro_Trading/.planning/MILESTONES.md` -- v1.0 completion record
- GUIA_COMPLETO_CLAUDE_CODE_Fase1.md -- Detailed implementation specification (20 ETAPAs)
- Web search findings: agent design patterns, backtesting pitfalls, Kalman Filter r-star, HMM regime detection
- Academic references: Taylor (1993), Laubach-Williams (2003), Clark-MacDonald (1998), Hamilton (1989), IMF (2013), Bailey-Lopez de Prado (2014), Harvey-Liu-Zhu (2016)

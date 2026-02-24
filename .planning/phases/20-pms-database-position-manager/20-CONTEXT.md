# Phase 20: PMS Database & Position Manager - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Database foundation and core position management for the Portfolio Management System. Delivers 5 new SQLAlchemy models (PortfolioPosition, TradeProposal, DecisionJournal, DailyBriefing, PositionPnLHistory) with TimescaleDB hypertables, Alembic migration, PositionManager service (open/close/MTM/book), and MarkToMarketService (price sourcing, instrument-aware pricing, VaR contribution). Trade workflow, API endpoints, and frontend are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Position data model
- Dual tracking for position size: both notional_brl and quantity are first-class fields. Use whichever is natural per instrument (contracts for DI futures, notional for OTC/NDF)
- BRL primary, USD derived: notional_brl is source of truth. notional_usd computed from PTAX/spot rate at entry date. FX positions still use BRL as primary notional
- Closed position handling: soft-delete + auto-archive. is_open=False immediately on close. Scheduled job archives positions older than configurable N days to portfolio_positions_archive table
- Full risk snapshot at entry: store DV01, delta, convexity, VaR contribution, and spread duration at position entry. Provides complete point-in-time context for Decision Journal retrospectives

### Mark-to-market sourcing
- DB auto, manual override: automatic MTM from TimescaleDB market_data table prices daily. Manager can override any price post-MTM via API/UI. System shows DB price, manager corrects if needed
- Stale/missing prices: use last available price with staleness alert (e.g., "price is 3 days old"). Position gets MTM'd with carried-forward price. Alert surfaces in morning pack
- MTM timing: daily EOD scheduled MTM (primary). Manager can trigger on-demand intraday MTM via API/UI. Intraday snapshots don't persist to position_pnl_history unless explicitly saved
- Instrument-aware pricing: separate pricing logic per asset class — DI futures use rate-to-PU (preço unitário) conversion, NTN-Bs use real yield to price, FX uses spot rate, CDS uses spread-to-price. Not generic price-based

### Decision Journal design
- Full decision log: captures trade decisions (OPEN, CLOSE, MODIFY, REJECT), manager notes/observations, AND automated system events (MTM adjustments, limit breaches, signal flips). Complete audit trail
- Per-entry SHA256 hash for integrity verification. Independent hashes, no chain dependency. Hash covers all content fields of the entry
- Market + portfolio snapshot per entry: key market indicators (SELIC, USDBRL, VIX, DI rates) and portfolio state (AUM, leverage, VaR) captured at decision time. Not full context dump, not minimal
- DB-level immutability: PostgreSQL trigger prevents UPDATE/DELETE on locked (is_locked=True) rows. Enforced at database level regardless of application path. Strongest guarantee

### P&L calculation approach
- Hybrid P&L for rates: PU (preço unitário) price-based P&L as primary computation (accurate, captures convexity). DV01 maintained separately for risk attribution and reporting. Both recomputed on MTM
- BRL + USD parallel: P&L reported in both currencies. USD P&L uses entry FX rate for entry and current FX rate for current value. Both stored in position_pnl_history
- Signal-weight proportional attribution: when a position is linked to multiple strategies, daily P&L attributed proportional to each strategy's signal conviction at entry
- Gross + cost breakdown: gross P&L and transaction costs tracked separately. Manager sees both gross and net P&L. Cost uses TransactionCostModel from v3.0 (Phase 14)

### Claude's Discretion
- Exact archive job scheduling (cron interval, retention period before archival)
- PostgreSQL trigger implementation details for journal immutability
- Specific market indicators included in the journal snapshot JSON
- PU conversion formulas for each DI tenor (standard B3 convention)
- position_pnl_history hypertable chunk interval and compression policy timing

</decisions>

<specifics>
## Specific Ideas

- Instrument-aware pricing should follow B3 conventions for DI futures (rate-to-PU: PU = 100000 / (1 + rate/100)^(DU/252))
- The fund is BRL-denominated but has USD exposure through FX and sovereign credit positions — USD P&L is important for those positions
- TransactionCostModel from Phase 14 already has per-instrument costs for 12 instruments — reuse for PMS cost tracking
- VaR contribution per position should use the existing Component VaR from Phase 17 risk engine
- Morning pack references in Decision Journal (Phase 22 will consume journal data for daily briefings)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 20-pms-database-position-manager*
*Context gathered: 2026-02-24*

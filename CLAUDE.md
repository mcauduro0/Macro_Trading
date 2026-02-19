# Macro Trading Project — Claude Code Configuration

## Project Overview

This is a **Macro Trading System** project focused on identifying and executing trades based on volatility signals and market sentiment analysis. The system integrates real-time market data APIs, generates trading signals, manages positions, and evaluates portfolio risk.

## Skills & Capabilities

This project is equipped with **145 Agent Skills** from 6 curated sources, plus the **GSD (Get Stuff Done) framework** for structured project management.

### Installed Frameworks & Skills

#### GSD Framework (Get Stuff Done)
- **Commands**: `/gsd:new-project`, `/gsd:plan-phase`, `/gsd:execute-phase`, `/gsd:discuss-phase`, `/gsd:debug`, `/gsd:verify-work`, and more
- **Agents**: gsd-planner, gsd-executor, gsd-debugger, gsd-verifier, gsd-codebase-mapper, gsd-roadmapper, and more
- **Location**: `.claude/commands/gsd/`, `.claude/agents/`, `.claude/get-shit-done/`

#### obra/superpowers (14 skills)
Battle-tested development skills: TDD, systematic debugging, code review, parallel agents, git worktrees, plan writing/execution, subagent-driven development, verification.

#### anthropics/skills (16 skills)
Official Anthropic skills: PDF/DOCX/XLSX/PPTX processing, MCP builder, frontend design, webapp testing, canvas design, doc co-authoring, brand guidelines.

#### alirezarezvani/claude-skills (53 skills)
Enterprise-grade skills organized by team: financial analyst, senior architect/backend/frontend/devops/ML/data-scientist, CEO/CTO advisor, product management, Jira/Confluence integration, code review, database design, RAG architect, security.

#### levnikolaevich/claude-code-skills (40 skills)
Full SDLC pipeline: scope decomposition, epic/story/task management, code execution, quality gates, auditors (security, code quality, dependencies, dead code, performance), DevOps setup (Docker, CI/CD), project bootstrap.

#### ComposioHQ/awesome-claude-skills (19 skills)
Third-party integrations and utilities: artifacts builder, changelog generator, content research, file organizer, lead research, MCP builder, meeting insights, webapp testing, Polygon/OpenAI/Snowflake automations.

#### hesreallyhim/awesome-claude-code (3 resource packs)
Curated resources: CLAUDE.md templates, workflow guides, and 23 additional slash commands (commit, PR review, release, optimize, etc.).

### Additional Slash Commands
Beyond GSD, the following commands are available: `/commit`, `/create-pr`, `/pr-review`, `/release`, `/optimize`, `/todo`, `/fix-github-issue`, `/create-prd`, `/testing_plan_integration`, and more.

## Development Phase Rules & Guides

This project follows a structured 4-phase development plan (Phase 0 through Phase 3). Each phase has a comprehensive guide located in `.claude/rules/` that serves as the **authoritative reference** for what to build, how to build it, and how to validate each step.

**IMPORTANT: Before starting work on any phase, you MUST read the corresponding guide file in full. These guides contain the exact specifications, code structures, database schemas, API endpoints, and validation criteria for each development step.**

| Phase | Guide File | Description | Estimated Time |
|---|---|---|---|
| **Phase 0** | `.claude/rules/GUIA_COMPLETO_CLAUDE_CODE_Fase0.md` | Data Infrastructure (15 steps) — Project scaffold, Docker Compose (TimescaleDB, Redis, MongoDB, Kafka, MinIO), 11+ data connectors (BCB, FRED, B3, ANBIMA, Yahoo, etc.), 200+ macro series, data quality checks, FastAPI endpoints | 6-10 hours |
| **Phase 1** | `.claude/rules/GUIA_COMPLETO_CLAUDE_CODE_Fase1.md` | Quantitative Models, Agents & Backtesting (20 steps) — Agent Framework, 5 Analytical Agents, Backtesting Engine, 8 Trading Strategies, Signal Aggregation, Risk Management | 10-16 hours |
| **Phase 2** | `.claude/rules/GUIA_COMPLETO_CLAUDE_CODE_Fase2.md` | Strategy Engine, Risk & Portfolio Management (18 steps) — 17 additional strategies, NLP Pipeline, Risk Engine (VaR, CVaR, stress testing), Portfolio Construction & Optimization, Production Orchestration (Dagster) | 12-18 hours |
| **Phase 3** | `.claude/rules/GUIA_COMPLETO_CLAUDE_CODE_Fase3.md` | Production Infrastructure, Live Trading & Go-Live — Execution Management System, FIX connectivity, Emergency Stop, Auth/Security, Go-Live Checklist | 8-12 hours |

### How to Use the Guides

1. Each guide contains numbered **ETAPAS** (steps) that are independent prompts
2. Each step is delimited by `═══ INÍCIO DO PROMPT N ═══` and `═══ FIM DO PROMPT N ═══`
3. Execute steps in order — each builds on the previous
4. Each step includes verification criteria (tests, migrations, health checks)
5. **Never skip verification** before moving to the next step

### Phase Dependencies

- **Phase 0** requires: Docker, Python 3.11+, Node.js 18+, Git, 16GB+ RAM, FRED API key
- **Phase 1** requires: Phase 0 complete (data infrastructure with TimescaleDB, 11 connectors, 200+ macro series, FastAPI)
- **Phase 2** requires: Phase 1 complete (5 agents, backtesting engine, 8 strategies, React dashboard)
- **Phase 3** requires: Phase 2 complete (25 strategies, risk engine, portfolio optimization, Dagster orchestration)

## Key Constraints

- **Language**: English (default working language)
- **Investment Focus**: Stocks only (no ETFs, mutual funds)
- **LLM Preference**: Claude Opus 4.5, GPT-5.2 Pro, Gemini 3 Pro
- **Data**: Real data only in production (no mocks)
- **Stack**: Python-based with open-source libraries

## Getting Started

1. Use `/gsd:new-project` to initialize the project structure
2. Use `/gsd:discuss-phase` to clarify approach for each phase
3. Use `/gsd:plan-phase` to create detailed phase plans
4. Use `/gsd:execute-phase` to build
5. Use `/gsd:verify-work` to validate

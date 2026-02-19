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

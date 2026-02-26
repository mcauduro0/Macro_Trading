# Plano de Ação: Fase 2 — Strategy Engine, Risk & Portfolio Management

**Projeto:** Macro Trading System  
**Autor:** Manus AI  
**Data:** 22 de fevereiro de 2026  
**Tempo Estimado:** 12-18 horas de trabalho no Claude Code  

---

## 1. Resumo Executivo

A Fase 2 representa a evolução do sistema de um framework de backtesting funcional para um **motor de estratégias de produção** com orquestração robusta, risk engine avançado e construção de portfólio otimizada. Com a Milestone v2.0 completa (Phases 1-13), o sistema já possui 8 estratégias, 5 agentes analíticos, um backtesting engine, pipeline diário e dashboard. A Fase 2 irá **refatorar, expandir e profissionalizar** esses componentes, adicionando 17 novas estratégias (totalizando ~25), um pipeline de NLP para comunicações de bancos centrais, risk engine com VaR/CVaR/stress testing, otimização de portfólio com Black-Litterman e Risk Parity, e orquestração de produção via Dagster.

---

## 2. Estado Atual do Projeto (Pré-Fase 2)

O repositório contém os seguintes módulos que serão expandidos ou refatorados pela Fase 2:

| Módulo | Arquivos | Estado Atual | O que a Fase 2 Fará |
|---|---|---|---|
| `src/strategies/` | 10 arquivos (base + 8 estratégias) | 8 estratégias implementadas | Refatorar base, adicionar 17 novas estratégias (total ~25) |
| `src/risk/` | 6 arquivos | VaR, StressTester, DrawdownManager, RiskLimits, RiskMonitor | Refatorar em Risk Engine centralizado com VaR paramétrico, histórico, Monte Carlo, CVaR e margin calculator |
| `src/portfolio/` | 4 arquivos | SignalAggregator, PortfolioConstructor, CapitalAllocator | Adicionar Risk Parity, Black-Litterman, otimização convexa |
| `src/pipeline/` | 2 arquivos | DailyPipeline com 8 passos | Migrar para Dagster com DAGs de produção |
| `src/agents/` | 7 arquivos | 5 agentes + framework + data loader | Adicionar Cross-Asset Agent v2 com regime detection |
| `src/narrative/` | 3 arquivos | LLM narrative com Claude API | Expandir com relatório PDF diário |
| `src/backtesting/` | 5 arquivos | Engine event-driven single-strategy | Refatorar para portfolio-level com custos e slippage |
| `tests/` | 49 arquivos | Testes unitários e integração | Expandir para cobertura da Fase 2 + CI/CD |

---

## 3. Plano Detalhado por Bloco

A Fase 2 contém **18 etapas** organizadas em **6 blocos lógicos**. Cada bloco será executado como uma ou mais super-fases no GSD, com o fluxo `/gsd:discuss-phase` → `/clear` → `/gsd:plan-phase --skip-research` → `/clear` → `/gsd:execute-phase`.

### Bloco A: Framework de Estratégias v2 (Etapas 1-2) — ~55 min

Este bloco refatora a fundação de estratégias e o backtesting engine para suportar o modelo de produção com 25+ estratégias.

| Etapa | Título | Tempo | O que será criado | Dependências |
|---|---|---|---|---|
| **1** | Strategy Base Classes & Signal Schema | ~25 min | `BaseStrategy` v2 com `compute_signal()` e `compute_signal_history()`, `StrategySignal` dataclass padronizado, `StrategyRegistry` com decorator `@register`, tabelas `strategy_state` e `backtest_results`, migração Alembic | Nenhuma (fundação) |
| **2** | Backtesting Engine v2 (Portfolio-Level) | ~30 min | `BacktestEngineV2` com suporte multi-estratégia, custos transacionais (bid-ask spread, corretagem), slippage model, rebalanceamento periódico, métricas de portfólio (Sharpe, Sortino, Calmar, Information Ratio) | Etapa 1 |

A Etapa 1 irá **substituir** o `src/strategies/base.py` atual com uma versão mais robusta que inclui enums (`SignalDirection`, `AssetClass`, `SignalStrength`), dataclasses padronizados (`StrategySignal`, `BacktestResult`) e um `StrategyRegistry` centralizado. As 8 estratégias existentes precisarão ser adaptadas para a nova interface. A Etapa 2 cria um novo `engine_v2.py` que opera no nível de portfólio, permitindo backtests simultâneos de múltiplas estratégias com alocação de capital.

**Skills de suporte:** `alireza-senior-backend`, `alireza-database-designer`, `superpowers-test-driven-development`

---

### Bloco B: Expansão de Estratégias (Etapas 3-6) — ~140 min

Este é o bloco mais extenso da Fase 2, adicionando **17 novas estratégias** em 4 etapas paralelas por asset class. Cada estratégia implementa a nova `BaseStrategy` e é registrada automaticamente no `StrategyRegistry`.

| Etapa | Título | Tempo | Estratégias | Asset Class |
|---|---|---|---|---|
| **3** | FX Strategies (FX-02 a FX-05) | ~35 min | FX-02 BEER Model, FX-03 Flow Tracker, FX-04 Vol Surface, FX-05 Carry Cross | FX |
| **4** | Rates Strategies (RATES-03 a RATES-06) | ~35 min | RATES-03 Curve Momentum, RATES-04 Fly/Butterfly, RATES-05 US Treasury RV, RATES-06 Cross-Market Spread | RATES_BR, RATES_US |
| **5** | Inflation & Cupom Cambial (INF-02, INF-03, CUPOM-01, CUPOM-02) | ~35 min | INF-02 Inflation Momentum, INF-03 Real Rate, CUPOM-01 CIP Basis v2, CUPOM-02 FRA×Cupom | INFLATION_BR, CUPOM_CAMBIAL |
| **6** | Sovereign Credit & Cross-Asset (SOV-01 a SOV-03, CROSS-01, CROSS-02) | ~35 min | SOV-01 CDS-Bond Basis, SOV-02 EM Spread, SOV-03 Fiscal Trajectory, CROSS-01 Risk-On/Off, CROSS-02 Regime Momentum | SOVEREIGN_CREDIT, CROSS_ASSET |

Após a conclusão deste bloco, o sistema terá **25 estratégias** cobrindo 8 asset classes. Cada estratégia consome dados dos agentes analíticos e dos conectores de dados já implementados na Fase 0/1. A tabela abaixo resume o catálogo completo:

| Asset Class | Estratégias Fase 1 | Novas Fase 2 | Total |
|---|---|---|---|
| FX | 1 (FX_BR_01) | 4 (FX-02 a FX-05) | 5 |
| Rates BR | 4 (RATES_BR_01 a 04) | 2 (RATES-03, 04) | 6 |
| Rates US | 0 | 2 (RATES-05, 06) | 2 |
| Inflation BR | 1 (INF_BR_01) | 2 (INF-02, INF-03) | 3 |
| Cupom Cambial | 1 (CUPOM_01) | 2 (CUPOM-01 v2, CUPOM-02) | 3 |
| Sovereign Credit | 1 (SOV_BR_01) | 3 (SOV-01 a 03) | 4 |
| Cross-Asset | 0 | 2 (CROSS-01, 02) | 2 |
| **Total** | **8** | **17** | **25** |

**Skills de suporte:** `alireza-financial-analyst`, `alireza-senior-data-engineer`, `superpowers-test-driven-development`

---

### Bloco C: Agentes Avançados & NLP (Etapas 7-8) — ~70 min

Este bloco adiciona inteligência avançada ao sistema através de um agente orquestrador com regime detection e um pipeline de NLP para comunicações de bancos centrais.

| Etapa | Título | Tempo | O que será criado |
|---|---|---|---|
| **7** | Cross-Asset Agent v2 (LLM-Powered) | ~30 min | `cross_asset_agent_v2.py` com Markov-switching regime detection (4 regimes: risk-on, risk-off, transition, crisis), síntese de sinais de todos os agentes, e geração de "macro view" via LLM |
| **8** | NLP Pipeline: Central Bank Communications | ~40 min | Novo módulo `src/nlp/` com scrapers para atas COPOM e FOMC, processadores de texto (LDA topic modeling, BERT sentiment), geração de "hawkish/dovish score", integração com MonetaryPolicyAgent |

A Etapa 7 cria uma versão avançada do Cross-Asset Agent que identifica o regime macroeconômico atual usando um modelo de Markov-switching com 4 estados. O agente sintetiza os sinais de todos os outros agentes e gera uma "macro view" consolidada que influencia o dimensionamento de posições no portfólio. A Etapa 8 implementa um pipeline completo de processamento de linguagem natural para extrair informações das atas do COPOM e do FOMC, gerando scores de hawkishness/dovishness que alimentam o MonetaryPolicyAgent.

**Skills de suporte:** `alireza-senior-prompt-engineer`, `alireza-rag-architect`, `alireza-senior-data-engineer`

---

### Bloco D: Portfolio & Risk Engine v2 (Etapas 9-11) — ~100 min

Este é o bloco mais crítico da Fase 2, implementando a camada de agregação de sinais, o risk engine centralizado e a construção otimizada de portfólio.

| Etapa | Título | Tempo | O que será criado |
|---|---|---|---|
| **9** | Signal Aggregation Layer | ~25 min | `signal_aggregator_v2.py` com resolução de conflitos entre estratégias, ponderação por confiança e regime, geração de "sinal de consenso" por asset class |
| **10** | Risk Engine (VaR, CVaR, Stress Testing) | ~40 min | `risk_engine.py` centralizado com VaR paramétrico (delta-normal), VaR histórico (rolling 252d), VaR Monte Carlo (10.000 simulações), CVaR (Expected Shortfall), stress testing com cenários customizáveis (Taper Tantrum, Joesley Day, COVID, etc.), margin calculator |
| **11** | Portfolio Construction & Optimization | ~35 min | `portfolio_optimizer.py` com Risk Parity (equal risk contribution), Black-Litterman (views dos agentes como inputs), otimização convexa (cvxpy), position sizing com Kelly Criterion fracionário, rebalanceamento com threshold de drift |

A Etapa 10 é a peça mais crítica do sistema. O Risk Engine centralizado substituirá os módulos individuais (`var_calculator.py`, `stress_tester.py`) por um sistema unificado que calcula todas as métricas de risco em uma única chamada. O VaR será calculado em 3 métodos (paramétrico, histórico e Monte Carlo) com nível de confiança de 95% e 99%. O stress testing incluirá cenários históricos (Taper Tantrum 2013, Joesley Day 2017, COVID 2020, Selic 14.25% 2015) e cenários hipotéticos configuráveis.

A Etapa 11 implementa otimização de portfólio usando Black-Litterman, onde as "views" dos agentes analíticos são traduzidas em retornos esperados que alimentam o otimizador. O Risk Parity garante que cada asset class contribua igualmente para o risco total do portfólio.

**Skills de suporte:** `alireza-financial-analyst`, `alireza-senior-backend`, `superpowers-test-driven-development`

---

### Bloco E: Orquestração & Monitoramento (Etapas 12-13) — ~55 min

Este bloco migra a orquestração do pipeline para uma ferramenta de produção (Dagster) e adiciona monitoramento com Grafana.

| Etapa | Título | Tempo | O que será criado |
|---|---|---|---|
| **12** | Production Orchestration (Dagster) | ~30 min | Novo módulo `src/orchestration/` com definições de assets e jobs do Dagster, `dagster.yaml` de configuração, adição de `dagster-daemon` e `dagit` ao `docker-compose.yml`, schedule diário às 6:00 BRT |
| **13** | Monitoring & Alerting (Grafana) | ~25 min | Diretório `grafana/` com dashboards pré-configurados (pipeline health, data freshness, portfolio risk, strategy performance), datasource PostgreSQL/TimescaleDB, alertas para falhas de ingestão, VaR breach e drawdown |

A migração para Dagster substituirá o `scripts/daily_run.py` por um pipeline declarativo com dependências explícitas entre assets. Cada etapa do pipeline (ingest → quality → agents → strategies → aggregation → portfolio → risk → report) será um asset do Dagster com materialização rastreável. O Dagit fornecerá uma interface web para monitorar execuções, logs e lineage de dados.

**Skills de suporte:** `ln-1000-pipeline-orchestrator`, `ln-731-docker-generator`, `alireza-senior-devops`

---

### Bloco F: Dashboard, API, Testes & Verificação (Etapas 14-18) — ~115 min

Este bloco finaliza a Fase 2 com expansão do dashboard, novos endpoints de API, relatório diário em PDF, testes abrangentes e verificação end-to-end.

| Etapa | Título | Tempo | O que será criado |
|---|---|---|---|
| **14** | Dashboard v2: Strategy & Risk Pages | ~35 min | Novas abas no dashboard React: Strategy Detail (sinais, backtest, equity curve por estratégia), Risk Dashboard (VaR heatmap, stress scenarios, drawdown chart), Portfolio Optimizer (alocação atual vs. ótima) |
| **15** | Daily Report Generator | ~20 min | `src/reports/daily_report.py` com geração de PDF consolidado (macro view, sinais, posições, risco, P&L), envio por email (SMTP), armazenamento em `reports/` |
| **16** | API Expansion & WebSocket | ~20 min | Novos endpoints v3 (risk engine, portfolio optimizer, strategy detail, NLP scores), WebSocket para live updates de sinais e posições |
| **17** | Comprehensive Testing & CI/CD | ~25 min | Testes de integração end-to-end para o pipeline Dagster, testes de regressão para todas as 25 estratégias, GitHub Actions CI pipeline (lint, test, type-check, coverage ≥80%) |
| **18** | Verification & Git Commit Final | ~15 min | Script de verificação end-to-end da Fase 2, checklist de 30+ itens, tag `v3.0.0-strategy-risk-engine`, README atualizado |

**Skills de suporte:** `alireza-senior-frontend`, `alireza-senior-qa`, `ln-732-cicd-generator`, `superpowers-verification-before-completion`

---

## 4. Dependências entre Blocos

O diagrama abaixo mostra as dependências entre os blocos. Os Blocos B e C podem ser executados em paralelo após o Bloco A.

```
Bloco A (Etapas 1-2)
  ├── Bloco B (Etapas 3-6)  ──┐
  └── Bloco C (Etapas 7-8)  ──┤
                               ├── Bloco D (Etapas 9-11)
                               │       │
                               │       └── Bloco E (Etapas 12-13)
                               │               │
                               └───────────────└── Bloco F (Etapas 14-18)
```

---

## 5. Resumo de Métricas

| Métrica | Valor |
|---|---|
| **Total de etapas** | 18 |
| **Tempo estimado** | 12-18 horas |
| **Novas estratégias** | 17 (total: 25) |
| **Novos módulos** | 4 (`src/nlp/`, `src/orchestration/`, `src/reports/`, `grafana/`) |
| **Módulos refatorados** | 4 (`strategies/`, `risk/`, `portfolio/`, `backtesting/`) |
| **Novas tabelas** | 2 (`strategy_state`, `backtest_results`) |
| **Novas migrações Alembic** | 1 |
| **Novos serviços Docker** | 3 (dagster-daemon, dagit, grafana) |
| **Meta de cobertura de testes** | ≥80% |
| **Tag final** | `v3.0.0-strategy-risk-engine` |

---

## 6. Como Executar no Claude Code

Para cada bloco, siga o fluxo padrão com `/clear` entre cada comando para evitar o bug de `tool_use ids`:

```bash
# Bloco A: Framework v2
/clear
Read docs/GUIA_COMPLETO_CLAUDE_CODE_Fase2.md and execute Etapa 1 (Strategy Base Classes & Signal Schema).

/clear
Read docs/GUIA_COMPLETO_CLAUDE_CODE_Fase2.md and execute Etapa 2 (Backtesting Engine v2).

# Bloco B: Estratégias (Etapas 3-6)
/clear
Read docs/GUIA_COMPLETO_CLAUDE_CODE_Fase2.md and execute Etapa 3 (FX Strategies FX-02 to FX-05).

/clear
Read docs/GUIA_COMPLETO_CLAUDE_CODE_Fase2.md and execute Etapa 4 (Rates Strategies RATES-03 to RATES-06).

/clear
Read docs/GUIA_COMPLETO_CLAUDE_CODE_Fase2.md and execute Etapa 5 (Inflation & Cupom Cambial Strategies).

/clear
Read docs/GUIA_COMPLETO_CLAUDE_CODE_Fase2.md and execute Etapa 6 (Sovereign Credit & Cross-Asset Strategies).

# ... continuar para Blocos C, D, E, F
```

**Importante:** Ao final de cada sessão de trabalho, sempre execute:

```
Merge your current branch into main and push.
```

Ou peça ao Manus para fazer o merge, como tem sido feito até agora.

---

## 7. Pré-Requisitos

Antes de iniciar a Fase 2, certifique-se de que:

1. O `main` está atualizado com toda a Milestone v2.0 (Phases 1-13) — **já confirmado**.
2. Docker + Docker Compose rodando com todos os serviços da Fase 0/1.
3. Banco populado e verificado (`make verify` → PASS).
4. API rodando (`http://localhost:8000/docs`).
5. Instalar dependências adicionais que serão necessárias: `dagster`, `dagit`, `cvxpy`, `scikit-learn`, `transformers` (para BERT), `gensim` (para LDA).

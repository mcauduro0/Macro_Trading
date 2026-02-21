# Plano de Ação: Fase 1 — Modelos Quantitativos & Agentes (v2.0)

**Objetivo:** Construir o cérebro do sistema de trading, desenvolvendo 5 agentes analíticos, 8 estratégias de trading, um backtesting engine, e um sistema completo de gestão de risco e portfólio.

**Status Atual:** A Fase 0 (Infraestrutura de Dados) e a Fase 7 do GSD (Agent Framework) estão completas e mergeadas no `main`. O sistema possui a fundação de dados e a estrutura base para criar agentes.

**Estratégia de Execução:**

O desenvolvimento seguirá o `ROADMAP.md` do GSD, que organiza a Fase 1 em 6 *super-fases* (Phases 8 a 13), cada uma com seus próprios planos de execução. Cada plano do GSD corresponde a uma ou mais etapas do `GUIA_COMPLETO_CLAUDE_CODE_Fase1.md`.

---

## Plano Detalhado por Fase do GSD

### Phase 8: Inflation & Monetary Agents (3 planos)
- **Objetivo:** Construir os 2 primeiros agentes analíticos, focados em inflação e política monetária.
- **Mapeamento:** Corresponde às **Etapas 2 e 3** do guia da Fase 1.
- **Requisitos GSD:** `INFL-01` a `INFL-07`, `MONP-01` a `MONP-06`, `TESTV2-01`, `TESTV2-02`.
- **Plano de Execução:**
  1.  **08-01-PLAN.md:** Implementar `InflationFeatureEngine`, `PhillipsCurveModel` e `IpcaBottomUpModel`.
  2.  **08-02-PLAN.md:** Implementar os modelos restantes de inflação e o `InflationAgent` que orquestra tudo.
  3.  **08-03-PLAN.md:** Implementar `MonetaryFeatureEngine`, `TaylorRuleModel`, `KalmanFilterRStar` e o `MonetaryPolicyAgent`.

### Phase 9: Fiscal & FX Agents (2 planos)
- **Objetivo:** Construir os agentes de análise fiscal e de câmbio.
- **Mapeamento:** Corresponde às **Etapas 4 e 5** do guia da Fase 1.
- **Requisitos GSD:** `FISC-01` a `FISC-04`, `FXEQ-01` a `FXEQ-05`.
- **Plano de Execução:**
  1.  **09-01-PLAN.md:** Implementar `FiscalFeatureEngine`, `DebtSustainabilityModel` e o `FiscalAgent`.
  2.  **09-02-PLAN.md:** Implementar `FxFeatureEngine`, `BeerModel` e o `FxEquilibriumAgent`.

### Phase 10: Cross-Asset Agent & Backtesting Engine (3 planos)
- **Objetivo:** Construir o último agente (contexto de mercado) e o motor de backtesting.
- **Mapeamento:** Corresponde às **Etapas 6 e 7** do guia da Fase 1.
- **Requisitos GSD:** `CRSA-01` a `CRSA-03`, `BACK-01` a `BACK-08`, `TESTV2-03`.
- **Plano de Execução:**
  1.  **10-01-PLAN.md:** Implementar o `CrossAssetAgent` com detecção de regime e sentimento.
  2.  **10-02-PLAN.md:** Implementar o `BacktestEngine` com suporte a `PointInTimeDataLoader`.
  3.  **10-03-PLAN.md:** Implementar a classe `BacktestResult` com todas as métricas de performance.

### Phase 11: Trading Strategies (3 planos)
- **Objetivo:** Implementar as 8 estratégias de trading iniciais.
- **Mapeamento:** Corresponde às **Etapas 8, 9 e 10** do guia da Fase 1.
- **Requisitos GSD:** `STRAT-01` a `STRAT-09`.
- **Plano de Execução:**
  1.  **11-01-PLAN.md:** Implementar `BaseStrategy` e as estratégias de Curva de Juros (Carry, Taylor Rule).
  2.  **11-02-PLAN.md:** Implementar as estratégias de Inflação e Câmbio (Breakeven, FX Carry, Cupom Cambial).
  3.  **11-03-PLAN.md:** Implementar as estratégias de Valor Relativo (Curve Steepener, Fiscal Sovereign, UST RV).

### Phase 12: Portfolio & Risk Management (3 planos)
- **Objetivo:** Construir o sistema de agregação de sinais, construção de portfólio e gestão de risco.
- **Mapeamento:** Corresponde às **Etapas 11 e 12** do guia da Fase 1.
- **Requisitos GSD:** `PORT-01` a `PORT-04`, `RISK-01` a `RISK-08`, `TESTV2-04`.
- **Plano de Execução:**
  1.  **12-01-PLAN.md:** Implementar `SignalAggregator`, `PortfolioConstructor` e `CapitalAllocator`.
  2.  **12-02-PLAN.md:** Implementar `VaRCalculator` e `StressTester`.
  3.  **12-03-PLAN.md:** Implementar `RiskLimitChecker`, `DrawdownManager` e `RiskMonitor`.

### Phase 13: Pipeline, LLM, Dashboard, API & Tests (4 planos)
- **Objetivo:** Finalizar o sistema com um pipeline diário, narrativas de LLM, dashboard, APIs e testes de integração.
- **Mapeamento:** Corresponde às **Etapas 13 a 20** do guia da Fase 1.
- **Requisitos GSD:** `PIPE-01` a `PIPE-03`, `LLM-01` a `LLM-04`, `DASH-01` a `DASH-05`, `APIV2-01` a `APIV2-09`, `TESTV2-05` a `TESTV2-07`.
- **Plano de Execução:**
  1.  **13-01-PLAN.md:** Criar o script de orquestração diária `scripts/daily_run.py`.
  2.  **13-02-PLAN.md:** Implementar `NarrativeGenerator` com integração à API da Anthropic.
  3.  **13-03-PLAN.md:** Criar o dashboard HTML auto-contido.
  4.  **13-04-PLAN.md:** Implementar os 9 novos endpoints da API, testes de integração e o script de verificação final.

---

### Próximos Passos

Para iniciar o desenvolvimento da Fase 1, o comando a ser executado no Claude Code é:

```
/gsd:discuss-phase 8
```

Isso iniciará a discussão e o planejamento da **Phase 8: Inflation & Monetary Agents**, que é o primeiro bloco de trabalho da Fase 1.

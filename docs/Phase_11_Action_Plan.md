# Plano de Ação: Phase 11 — Trading Strategies

**Objetivo:** Implementar a classe base `BaseStrategy` e as 8 estratégias de trading iniciais, conectando os sinais dos agentes (Phase 8-10) ao motor de backtesting (Phase 10).

**Status Atual:** O `11-CONTEXT.md` está pronto e define as regras de negócio. Os 5 agentes analíticos e o backtesting engine já existem. A pasta `src/strategies/` ainda não foi criada.

**Estratégia de Execução:**

A Phase 11 será executada em **3 planos de trabalho**, conforme definido no `ROADMAP.md`. Cada plano implementará um grupo de estratégias e seus testes unitários, garantindo que cada componente seja validado antes de prosseguir.

---

## Plano Detalhado por Etapa (GSD Plans)

### Plano 1: Base & Estratégias de Juros (11-01-PLAN.md)
- **Objetivo:** Criar a fundação para todas as estratégias e implementar as 2 primeiras, focadas na curva de juros brasileira.
- **Requisitos GSD:** `STRAT-01`, `STRAT-02`, `STRAT-03`.
- **Tarefas de Implementação:**
  1.  **Criar `src/strategies/`:** Criar a nova pasta para o código das estratégias.
  2.  **Definir Dataclasses:** Criar `src/strategies/base.py` com as dataclasses `StrategyConfig` e `StrategyPosition`.
  3.  **Implementar `BaseStrategy`:** Criar a classe abstrata `BaseStrategy` em `src/strategies/base.py`. Ela deve:
      - Receber `StrategyConfig` e `PointInTimeDataLoader` no `__init__`.
      - Ter um método abstrato `generate_signals(self, as_of_date: date) -> list[StrategyPosition]`.
      - Ter um método `get_agent_report(self, agent_id: str, as_of_date: date)` que busca o relatório de um agente via `AgentRegistry`.
  4.  **Implementar `RATES_BR_01_Carry`:** Criar `src/strategies/rates_br_01_carry.py`. A estratégia irá:
      - Carregar o `MonetaryPolicyAgent`.
      - Calcular o carry-to-risk para cada vértice da curva DI1.
      - Gerar um sinal `StrategyPosition` para o vértice com o maior ratio, se acima de um threshold.
  5.  **Implementar `RATES_BR_02_Taylor`:** Criar `src/strategies/rates_br_02_taylor.py`. A estratégia irá:
      - Carregar o `MonetaryPolicyAgent`.
      - Usar o sinal `TAYLOR_RULE_GAP`.
      - Gerar um sinal direcional para o DI1 futuro se o gap exceder 100bps.
  6.  **Testes:** Criar `tests/test_strategies_rates_br.py` com testes unitários para as duas estratégias, mockando os `AgentReport`s.

### Plano 2: Estratégias de Juros (cont.) & Inflação (11-02-PLAN.md)
- **Objetivo:** Implementar mais 3 estratégias, focadas em inclinação da curva, spillovers de juros dos EUA e inflação implícita.
- **Requisitos GSD:** `STRAT-04`, `STRAT-05`, `STRAT-06`.
- **Tarefas de Implementação:**
  1.  **Implementar `RATES_BR_03_Slope`:** Criar `src/strategies/rates_br_03_slope.py`. A estratégia irá:
      - Carregar o `MonetaryPolicyAgent` e o `InflationAgent`.
      - Analisar a posição no ciclo monetário e as expectativas de inflação para prever o movimento do spread 2Y-5Y.
      - Gerar posições de flattener/steepener.
  2.  **Implementar `RATES_BR_04_Spillover`:** Criar `src/strategies/rates_br_04_spillover.py`. A estratégia irá:
      - Carregar o `CrossAssetAgent`.
      - Monitorar o spread DI-UST e gerar sinais de reversão à média após movimentos semanais extremos.
  3.  **Implementar `INF_BR_01_Breakeven`:** Criar `src/strategies/inf_br_01_breakeven.py`. A estratégia irá:
      - Carregar o `InflationAgent`.
      - Comparar a previsão do agente para a inflação com a inflação implícita (breakeven) do mercado.
      - Gerar sinais quando a divergência for significativa.
  4.  **Testes:** Adicionar testes para as 3 novas estratégias em `tests/test_strategies_rates_br.py` e `tests/test_strategies_inflation.py`.

### Plano 3: Estratégias de Câmbio, Cupom & Risco Soberano (11-03-PLAN.md)
- **Objetivo:** Implementar as 3 últimas estratégias e criar o registro final que será usado pelo backtester.
- **Requisitos GSD:** `STRAT-07`, `STRAT-08`, `STRAT-09`.
- **Tarefas de Implementação:**
  1.  **Implementar `FX_BR_01_Composite`:** Criar `src/strategies/fx_br_01_composite.py`. A estratégia irá:
      - Carregar o `FxEquilibriumAgent` e o `CrossAssetAgent`.
      - Construir o sinal composto com os pesos definidos no `11-CONTEXT.md` (40% carry, 35% BEER, 25% flow).
      - Ajustar o tamanho da posição com base no regime de risco do `CrossAssetAgent`.
  2.  **Implementar `CUPOM_01_CIP`:** Criar `src/strategies/cupom_01_cip.py`. A estratégia irá:
      - Carregar o `FxEquilibriumAgent`.
      - Gerar sinais de reversão à média quando o z-score da base do cupom cambial vs SOFR estiver extremo.
  3.  **Implementar `SOV_BR_01_Fiscal`:** Criar `src/strategies/sov_br_01_fiscal.py`. A estratégia irá:
      - Carregar o `FiscalAgent`.
      - Gerar posições no DI longo e no USDBRL com base no risco de dominância fiscal.
  4.  **Criar Registro `ALL_STRATEGIES`:** Em `src/strategies/__init__.py`, criar um dicionário `ALL_STRATEGIES` que mapeia o ID de cada uma das 8 estratégias para sua respectiva classe.
  5.  **Testes:** Criar `tests/test_strategies_fx_sov.py` com testes para as 3 novas estratégias.

---

### Próximos Passos

Para iniciar o desenvolvimento da Phase 11, o comando a ser executado no Claude Code é:

```
/clear

/gsd:plan-phase 11 --skip-research
```

Isso irá gerar os 3 arquivos `PLAN.md` detalhados dentro de `.planning/phases/11-trading-strategies/`, prontos para serem executados com `/gsd:execute-phase 11-01`, `/gsd:execute-phase 11-02`, etc.

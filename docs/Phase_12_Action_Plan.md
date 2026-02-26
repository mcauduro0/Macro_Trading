# Plano de Ação: Phase 12 — Portfolio Construction & Risk Management

**Objetivo:** Implementar a camada de construção de portfólio e gestão de risco, transformando os sinais das 8 estratégias (Phase 11) em um portfólio agregado com controles de risco robustos.

**Status Atual:** A Phase 11 está completa, com 8 estratégias disponíveis no registro `ALL_STRATEGIES`. As pastas `src/portfolio/` e `src/risk/` ainda não existem.

**Estratégia de Execução:**
A Phase 12 será executada em **3 planos de trabalho**, conforme definido no `ROADMAP.md`. Cada plano implementará um componente do pipeline de portfólio e risco, com testes unitários para cada módulo.

---

## Plano Detalhado por Etapa (GSD Plans)

### Plano 1: Agregação de Sinais & Construção de Portfólio (12-01-PLAN.md)
- **Objetivo:** Criar a lógica para agregar sinais de agentes e estratégias, e construir um portfólio-alvo com base nesses sinais.
- **Requisitos GSD:** `PORT-01`, `PORT-02`, `PORT-03`, `PORT-04`.
- **Tarefas de Implementação:**
  1.  **Criar `src/portfolio/`:** Criar a nova pasta para o código de portfólio.
  2.  **Implementar `SignalAggregator`:** Em `src/portfolio/aggregator.py`, criar a classe que:
      - Carrega os relatórios dos 5 agentes via `AgentRegistry`.
      - Calcula um score de consenso direcional para `RATES_BR`, `FX_BR`, e `INFLATION_BR`.
      - Detecta e loga conflitos de sinal (ex: `InflationAgent` hawkish vs `MonetaryPolicyAgent` dovish).
  3.  **Implementar `PortfolioConstructor`:** Em `src/portfolio/constructor.py`, criar a classe que:
      - Recebe as `StrategyPosition`s de todas as 8 estratégias.
      - Calcula um orçamento de risco (risk budget) para cada estratégia (inicialmente peso igual, depois inverse-volatility).
      - Ajusta as posições com base no regime de risco do `CrossAssetAgent` (RISK_OFF → -50%).
      - Agrega as posições por instrumento para obter o portfólio-alvo líquido.
  4.  **Implementar `CapitalAllocator`:** Em `src/portfolio/allocator.py`, criar a classe que:
      - Aplica os limites de portfólio (max leverage 3x, max posição 25%, max classe de ativo 50%).
      - Verifica se o desvio do portfólio atual para o alvo excede um threshold (5%) para decidir se rebalanceia.
      - Calcula a lista de trades (compras/vendas) necessários para ir do portfólio atual para o alvo.
  5.  **Testes:** Criar `tests/test_portfolio/` com testes para `aggregator`, `constructor` e `allocator`.

### Plano 2: Métricas de Risco (VaR & Stress) (12-02-PLAN.md)
- **Objetivo:** Implementar os cálculos de Value at Risk (VaR) e os testes de estresse históricos.
- **Requisitos GSD:** `RISK-01`, `RISK-02`, `RISK-03`, `RISK-04`.
- **Tarefas de Implementação:**
  1.  **Criar `src/risk/`:** Criar a nova pasta para o código de risco.
  2.  **Implementar `VaRCalculator`:** Em `src/risk/var.py`, criar a classe que calcula:
      - **Historical VaR** (95% e 99%) e **Expected Shortfall (CVaR)** a partir dos retornos históricos do portfólio.
      - **Parametric VaR** (Gaussiano) usando a matriz de covariância.
  3.  **Implementar `StressTester`:** Adicionar um método `stress_var` na `VaRCalculator` que recalcula o P&L do portfólio sob 4 cenários históricos pré-definidos:
      - `taper_tantrum_2013`
      - `br_crisis_2015`
      - `covid_2020`
      - `rate_shock_2022`
  4.  **Testes:** Criar `tests/test_risk/test_var.py` com testes para os cálculos de VaR, CVaR e stress tests, usando um portfólio com retornos conhecidos.

### Plano 3: Limites, Drawdown & Monitoramento (12-03-PLAN.md)
- **Objetivo:** Implementar a verificação de limites, os circuit breakers de drawdown e o relatório de risco agregado.
- **Requisitos GSD:** `RISK-05`, `RISK-06`, `RISK-07`, `RISK-08`, `TESTV2-04`.
- **Tarefas de Implementação:**
  1.  **Implementar `RiskLimitChecker`:** Em `src/risk/limits.py`, criar a classe que:
      - Define os 9 limites de risco configuráveis (`RISK_LIMITS`).
      - Verifica o portfólio atual contra todos os limites.
      - Implementa uma função `check_pre_trade` que verifica se um trade proposto violaria algum limite.
  2.  **Implementar `DrawdownManager`:** Em `src/risk/drawdown.py`, criar a classe que:
      - Calcula o drawdown atual a partir da curva de equity do portfólio.
      - Implementa a lógica de **circuit breaker de 3 níveis**:
        - L1 (-3%): Reduz posições em 25%.
        - L2 (-5%): Reduz posições em 50%.
        - L3 (-8%): Fecha todas as posições.
  3.  **Implementar `RiskMonitor`:** Em `src/risk/monitor.py`, criar a classe que:
      - Gera um relatório de risco diário consolidado em formato de dicionário, contendo VaR, stress tests, utilização de limites e status do circuit breaker.
  4.  **Testes:** Criar `tests/test_risk/test_limits.py` e `test_drawdown.py` para validar a lógica de limites e circuit breakers.

---

### Próximos Passos

Para iniciar o desenvolvimento da Phase 12, o comando a ser executado no Claude Code é:

```
/clear

/gsd:discuss-phase 12
```

Isso irá gerar o `12-CONTEXT.md`. Depois, para gerar os 3 arquivos `PLAN.md` detalhados:

```
/clear

/gsd:plan-phase 12 --skip-research
```

E então, execute cada plano sequencialmente, lembrando de usar `/clear` entre eles e de fazer o merge para o `main` ao final da sessão.

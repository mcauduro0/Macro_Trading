# Plano de Ação: Phase 13 — Pipeline, LLM, Dashboard, API & Tests

**Objetivo:** Finalizar a Milestone v2.0 integrando todos os componentes em um pipeline diário, adicionando uma camada de narrativa com LLM, um dashboard de monitoramento e os endpoints de API restantes.

**Status Atual:** A Phase 12 está completa. Todos os componentes de agentes, estratégias, portfólio e risco estão implementados. A Phase 13 é a última etapa, focada em integração e exposição dos resultados.

**Estratégia de Execução:**
A Phase 13 será executada em **4 planos de trabalho**, conforme definido no `ROADMAP.md`. Cada plano corresponde a uma das 8 etapas finais do guia da Fase 1 (etapas 13-20).

---

## Plano Detalhado por Etapa (GSD Plans)

### Plano 1: Backtest Runner & Pipeline Diário (13-01-PLAN.md)
- **Objetivo:** Criar os scripts principais para executar o backtesting de estratégias e o pipeline diário end-to-end.
- **Requisitos GSD:** `PIPE-01`, `PIPE-02`, `PIPE-03`.
- **Etapas do Guia:** 13, 15.
- **Tarefas de Implementação:**
  1.  **`scripts/run_backtest.py`:**
      - Implementar CLI para rodar backtests para uma ou todas as estratégias, com período customizável.
      - Gerar um relatório de performance consolidado e salvar gráficos de equity curve.
      - Adicionar targets `backtest` e `backtest-recent` ao `Makefile`.
  2.  **`scripts/daily_run.py`:**
      - Implementar o pipeline de 8 passos: Ingest → Quality → Agents → Aggregate → Strategies → Portfolio → Risk → Report.
      - Adicionar CLI com opções `--date` e `--dry-run`.
      - Adicionar targets `daily` e `daily-dry` ao `Makefile`.

### Plano 2: Geração de Narrativa com LLM (13-02-PLAN.md)
- **Objetivo:** Implementar a geração de relatórios analíticos usando a API da Anthropic (Claude).
- **Requisitos GSD:** `LLM-01`, `LLM-02`, `LLM-03`, `LLM-04`.
- **Etapa do Guia:** 16.
- **Tarefas de Implementação:**
  1.  **Criar `src/agents/narrative.py`:**
      - Implementar a classe `NarrativeGenerator`.
      - Usar o SDK da Anthropic para gerar um "Daily Brief" com base nos sinais dos agentes, consenso e relatório de risco.
      - Criar um método `_fallback_narrative` que gera um relatório baseado em template caso a API key não esteja disponível.
  2.  **Integração:**
      - Adicionar `ANTHROPIC_API_KEY` ao `.env.example`.
      - Integrar o `NarrativeGenerator` no pipeline `daily_run.py`.
      - Adicionar o endpoint `GET /api/v1/reports/daily-brief`.

### Plano 3: Dashboard de Monitoramento (13-03-PLAN.md)
- **Objetivo:** Criar um dashboard web auto-contido para visualização dos dados do sistema.
- **Requisitos GSD:** `DASH-01`, `DASH-02`, `DASH-03`, `DASH-04`, `DASH-05`.
- **Etapa do Guia:** 17.
- **Tarefas de Implementação:**
  1.  **Criar `src/dashboard/index.html`:**
      - Usar React, TailwindCSS e Recharts via CDN para criar um single-page application.
      - Implementar 4 abas: Macro, Agent Signals, Portfolio, Backtests.
      - Consumir os dados dos endpoints da API REST.
  2.  **Servir o Dashboard:**
      - Criar `src/api/routes/dashboard_static.py` para servir o `index.html` no endpoint `/dashboard`.
      - Adicionar o novo router ao `main.py` da API.

### Plano 4: API Endpoints Finais & Testes de Integração (13-04-PLAN.md)
- **Objetivo:** Implementar os endpoints de API restantes e os testes de integração end-to-end.
- **Requisitos GSD:** `APIV2-01` a `APIV2-09`, `TESTV2-05`, `TESTV2-06`, `TESTV2-07`.
- **Etapas do Guia:** 14, 18, 19, 20.
- **Tarefas de Implementação:**
  1.  **Novos Endpoints:**
      - Implementar os 9 endpoints restantes em `src/api/routes/` para `agents`, `signals`, `strategies` e `portfolio`.
  2.  **Testes de Integração:**
      - Criar `tests/test_integration.py` com testes que validam o fluxo completo, desde o carregamento de dados até a verificação de limites de risco.
      - Adicionar testes para todos os endpoints da API usando o `TestClient` do FastAPI.
  3.  **Verificação e Finalização:**
      - Atualizar o script `scripts/verify_infrastructure.py` para cobrir todos os componentes da Fase 1.
      - Atualizar o `README.md` com a documentação da Fase 1.
      - Fazer o commit final da Milestone v2.0.

---

### Próximos Passos

Para iniciar a Phase 13, o fluxo no Claude Code é:

```
/clear
/gsd:discuss-phase 13

/clear
/gsd:plan-phase 13 --skip-research

# Executar cada plano sequencialmente
/clear
/gsd:execute-phase 13 --plan 01
# ... e assim por diante para 02, 03, 04
```

Ao final, fazer o merge para o `main` para concluir a Milestone v2.0.

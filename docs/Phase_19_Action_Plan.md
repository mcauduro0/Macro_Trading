# Plano de Ação: Fase 19 — Dashboard v2, API v3, CI/CD & Verificação Final

**Autor:** Manus AI
**Data:** 23 de Fevereiro de 2026

---

## 1. Visão Geral

A Fase 19 é a **etapa final da Milestone v3.0**, focada em consolidar a interface do usuário, expandir a API para suportar interações avançadas, e estabelecer um pipeline de CI/CD robusto para garantir a qualidade e a estabilidade do sistema. Esta fase transforma o protótipo funcional em um produto polido e pronto para a próxima etapa de produção.

O trabalho está organizado em **4 planos de execução**, cobrindo **14 requisitos** e as etapas 14 a 18 do guia da Fase 2.

| Plano | Foco | Requisitos | Etapas do Guia | O que será criado |
|---|---|---|---|---|
| **19-01** | Dashboard v2 (React) | DSHV-01, 02, 03, 04, 05, 06 | 14 | 5 páginas React, `App.tsx` com roteamento, sidebar, e componentes reutilizáveis. |
| **19-02** | API v3 & WebSocket | APIV-01, 02, 03, 04 | 16 | 12+ novos endpoints (backtest, strategy), 3 canais WebSocket. |
| **19-03** | Testes de Integração | TSTV-01, 02, 03, 04 | 17 | Testes E2E do pipeline, testes de todos os endpoints da API. |
| **19-04** | CI/CD & Verificação Final | CICD-01, 02, 03, FINAL-01, VERIF-01 | 17, 18 | Workflow GitHub Actions, `scripts/verify_phase2.py`, README atualizado, tag `v3.0.0`. |

---

## 2. Detalhamento dos Planos de Execução

### Plano 19-01: Dashboard v2 (React)

Este plano substitui o `dashboard.html` estático por uma aplicação React multi-página, interativa e rica em dados.

| Tarefa | Descrição | Arquivos Chave |
|---|---|---|
| **Setup do Projeto React** | Inicializar um projeto React com TypeScript, Vite, e Tailwind CSS dentro de `src/dashboard/frontend/`. | `package.json`, `vite.config.ts`, `tailwind.config.js` |
| **Estrutura da Aplicação** | Criar `App.tsx` com `react-router-dom` para navegação, um layout principal com sidebar e área de conteúdo. | `src/dashboard/frontend/src/App.tsx`, `components/Layout.tsx` |
| **Componentes de Página** | Desenvolver 5 componentes de página: `StrategiesPage`, `SignalsPage`, `RiskPage`, `PortfolioPage`, `AgentsPage`. | `pages/StrategiesPage.tsx`, etc. |
| **Componentes Reutilizáveis** | Criar componentes para gráficos (usando Recharts), tabelas (usando `react-table`), e cards. | `components/LineChart.tsx`, `components/DataTable.tsx` |
| **Integração com API** | Implementar hooks (`useQuery`, `useMutation`) para buscar dados dos endpoints da API FastAPI. | `hooks/useStrategies.ts`, etc. |

### Plano 19-02: API v3 & WebSocket

Expansão da API para suportar o novo dashboard e interações em tempo real.

| Tarefa | Descrição | Endpoints / Canais |
|---|---|---|
| **API de Backtest** | Endpoints para executar backtests sob demanda e comparar resultados. | `POST /v1/backtest/run`, `GET /v1/backtest/results`, `GET /v1/backtest/comparison` |
| **API de Estratégias** | Endpoints para detalhar estratégias, buscar histórico de sinais e atualizar parâmetros. | `GET /v1/strategies/{id}`, `GET /v1/strategies/{id}/signal/history`, `PUT /v1/strategies/{id}/params` |
| **WebSocket Manager** | Implementar um `ConnectionManager` para gerenciar conexões WebSocket e transmitir atualizações. | `src/api/websocket.py` |
| **Canais WebSocket** | Três canais para transmitir novos sinais, atualizações de portfólio e alertas de risco. | `/ws/signals`, `/ws/portfolio`, `/ws/alerts` |

### Plano 19-03: Testes de Integração

Validação completa do sistema, garantindo que todos os componentes funcionem em conjunto.

| Tarefa | Descrição | Arquivo Chave |
|---|---|---|
| **Teste E2E do Pipeline** | Um teste que executa o pipeline completo: ingestão de dados -> transformações -> agentes -> estratégias -> sinais -> portfólio -> risco -> relatório. | `tests/integration/test_full_pipeline.py` |
| **Teste de Endpoints da API** | Testes que chamam cada um dos endpoints da API (v1, v2, e v3) e validam os schemas de resposta e os status codes. | `tests/integration/test_api_endpoints.py` |
| **Teste de Backtest Suite** | Um teste que executa um backtest de 1 ano para cada uma das 24 estratégias para garantir que não há erros de execução. | `tests/integration/test_backtest_suite.py` |

### Plano 19-04: CI/CD & Verificação Final

Automatização do processo de teste e verificação final do projeto.

| Tarefa | Descrição | Arquivo Chave |
|---|---|---|
| **Workflow de CI/CD** | Criar um workflow no GitHub Actions (`.github/workflows/ci.yml`) com 3 jobs: `lint` (Ruff), `unit-tests` (Pytest), e `integration-tests` (Pytest com serviços Docker). | `.github/workflows/ci.yml` |
| **Script de Verificação** | Desenvolver `scripts/verify_phase2.py` que checa todos os componentes da Fase 2 e gera um relatório de status. | `scripts/verify_phase2.py` |
| **Atualização do README** | Adicionar uma seção detalhada sobre a Fase 2 no `README.md`, incluindo a lista de estratégias, a arquitetura do risk engine e a orquestração com Dagster. | `README.md` |
| **Git Tag Final** | Criar a tag `v3.0.0` para marcar a conclusão da Milestone. | `git tag -a v3.0.0 -m "Milestone v3.0: Complete"` |

---

## 3. Como Executar no Claude Code

Lembre-se de seguir o fluxo para evitar o bug de `tool_use ids`:

```
/gsd:discuss-phase 19  →  /clear  →  /gsd:plan-phase 19 --skip-research

/clear  →  /gsd:execute-phase 19 --plan 01
/clear  →  /gsd:execute-phase 19 --plan 02
/clear  →  /gsd:execute-phase 19 --plan 03
/clear  →  /gsd:execute-phase 19 --plan 04
```

Ao final da Phase 19, o projeto terá atingido a maturidade da **Milestone v3.0**, com um sistema robusto, testado e pronto para a próxima fase de implantação em produção e-mail e produção.

# Plano de Ação: Phase 18 — Dagster Orchestration & Monitoring

**Data:** 22 de Fevereiro de 2026
**Autor:** Manus AI
**Status:** Pronto para execução

---

## 1. Visão Geral

A **Phase 18** substitui o pipeline monolítico (`daily_pipeline.py`) por um orquestrador de dados moderno e declarativo, o **Dagster**, e introduz monitoramento robusto com **Grafana**. Esta fase transforma o sistema de um script sequencial para um conjunto de ativos de dados versionados, testáveis e observáveis. O trabalho está dividido em **2 planos de execução** que cobrem **8 requisitos** e **2 etapas** do guia (etapas 12-13), com tempo estimado de **~55 minutos**.

| Plano | Foco | Requisitos | Etapas do Guia | O que será criado |
|---|---|---|---|---|
| **18-01** | Dagster Pipeline | ORCH-01, 02, 03, 04 | 12 | `src/orchestration/` com 15+ Dagster assets, `docker-compose.yml` atualizado, `dagster.yaml` |
| **18-02** | Grafana Monitoring | MON-01, 02, 03, 04 | 13 | 4 dashboards JSON provisionados, `AlertManager` em `src/monitoring/`, 3 novas rotas de API |


## 2. Diagnóstico do Estado Atual

- **Pipeline Atual:** O `src/pipeline/daily_pipeline.py` é um script monolítico com 8 métodos (`_step_ingest`, `_step_agents`, etc.). É difícil de testar, não tem paralelismo e a lógica de dependência é implícita.
- **Orquestração:** **Inexistente.** Não há Dagster, Airflow ou similar. A execução é manual via `make daily`.
- **Monitoramento:** **Inexistente.** Não há Grafana, Prometheus ou qualquer ferramenta de observabilidade.
- **Docker Compose:** Contém 5 serviços (TimescaleDB, Redis, MongoDB, Kafka, Minio), mas falta o `dagster-webserver` e o `grafana`.


## 3. Plano de Execução Detalhado

### Plano 18-01: Dagster Pipeline (Etapa 12)

Este plano refatora o pipeline monolítico em um grafo de ativos do Dagster.

| Tarefa | Descrição | Dependências |
|---|---|---|
| **1. Setup do Dagster** | Adicionar `dagster`, `dagster-webserver`, `dagster-postgres` ao `requirements.txt`. Criar `dagster.yaml` na raiz. | `pip` |
| **2. Docker Compose** | Adicionar o serviço `dagster-webserver` ao `docker-compose.yml`, montando o `dagster.yaml` e o código-fonte. | `docker-compose.yml` |
| **3. Bronze Layer Assets** | Em `src/orchestration/assets/bronze.py`, criar um `@asset` para cada um dos 11 conectores, com `AutomationCondition.on_cron()` para agendamento. | `dagster`, `src/connectors/` |
| **4. Silver & Gold Assets** | Em `src/orchestration/assets/silver.py` e `gold.py`, criar assets para transforms, agents, signals, portfolio e risk, definindo as dependências (`deps=...`) para formar o DAG. | `dagster`, `src/transforms/`, `src/agents/`, etc. |
| **5. Definições** | Em `src/orchestration/definitions.py`, importar todos os assets e registrá-los em um objeto `Definitions`. | Assets criados |
| **6. Makefile** | Adicionar `make dagster` (para `docker compose up dagster-webserver`) e `make dagster-run-all` (para materializar todos os assets via CLI). | `Makefile` |
| **7. Testes** | Criar `tests/test_orchestration/test_assets.py` para testar a definição e as dependências dos assets. | `pytest`, `dagster` |

### Plano 18-02: Grafana Monitoring (Etapa 13)

Este plano implementa o stack de monitoramento e alertas.

| Tarefa | Descrição | Dependências |
|---|---|---|
| **1. Docker Compose** | Adicionar o serviço `grafana` ao `docker-compose.yml`, montando os volumes para provisioning e dashboards. | `docker-compose.yml` |
| **2. Provisioning** | Criar `infrastructure/grafana/provisioning/datasources/timescaledb.yml` para conectar o Grafana ao TimescaleDB. | Nenhum |
| **3. Dashboards** | Criar os 4 dashboards JSON em `infrastructure/grafana/dashboards/`: `pipeline_health.json`, `signal_overview.json`, `risk_dashboard.json`, `portfolio_performance.json`. | Conhecimento da estrutura do DB |
| **4. AlertManager** | Implementar `AlertManager` em `src/monitoring/alerts.py` com 10 regras de alerta e métodos para checar e enviar alertas (Slack/Email). | `httpx` (para webhooks) |
| **5. API de Monitoramento** | Criar `src/api/routes/monitoring.py` com 3 endpoints para expor o status do sistema. | `fastapi` |
| **6. Testes** | Criar `tests/test_monitoring/test_alerts.py` para testar a lógica do `AlertManager`. | `pytest`, `respx` |


## 4. Como Executar no Claude Code

Lembre-se da regra de ouro para evitar o bug `tool_use ids`:

```bash
# Iniciar a discussão da fase
/gsd:discuss-phase 18

# LIMPAR O CONTEXTO (MUITO IMPORTANTE)
/clear

# Planejar a fase (pulando o research, pois o CONTEXT.md já foi criado)
/gsd:plan-phase 18 --skip-research

# Executar o primeiro plano
/clear
/gsd:execute-phase 18 --plan 01

# Executar o segundo plano
/clear
/gsd:execute-phase 18 --plan 02

# Ao final da sessão, fazer o merge para o main
Merge your current branch into main and push.
```

Após a conclusão da Phase 18, o sistema terá um pipeline de dados robusto e observável, pronto para a fase final de integração (Phase 19).

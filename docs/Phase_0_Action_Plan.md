# Plano de Ação: Fase 0 — Infraestrutura de Dados

**Objetivo:** Construir a fundação completa do sistema de dados do projeto Macro Trading, seguindo as 15 etapas do guia `docs/GUIA_COMPLETO_CLAUDE_CODE_Fase0.md` e as melhores práticas do `Data_Architecture_Blueprint.md`.

**Status Atual:** O repositório está configurado com as skills e guias, mas não contém código-fonte. Esta fase irá construir a aplicação do zero.

**Estratégia de Execução:**

1.  **Framework GSD:** Utilizaremos o framework GSD para gerenciar o ciclo de vida de cada etapa. O fluxo será:
    *   `/gsd:discuss-phase`: Para alinhar a estratégia de cada etapa.
    *   `/gsd:plan-phase`: Para detalhar as subtarefas de cada etapa.
    *   `/gsd:execute-phase`: Para executar o desenvolvimento.
    *   `/gsd:verify-work`: Para validar a entrega de cada etapa.
2.  **Execução por Etapa:** Cada uma das 15 etapas do guia será tratada como um mini-projeto, garantindo que cada parte da infraestrutura seja construída e validada de forma incremental.
3.  **Skills de Suporte:** As skills de agente serão usadas para acelerar o desenvolvimento, garantir a qualidade e seguir as melhores práticas de arquitetura.

---

## Plano Detalhado por Etapa

| Etapa | Título | Foco Principal | Skills de Suporte | Verificação |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Scaffold do Projeto & Docker Compose** | Criar a estrutura de pastas, `docker-compose.yml` com 6 serviços (TimescaleDB, Redis, MongoDB, Kafka, Zookeeper, MinIO), `pyproject.toml`, `Makefile` e arquivos de configuração. | `alireza-senior-architect`, `ln-731-docker-generator`, `superpowers-writing-plans` | `make up` sobe todos os serviços sem erros. `docker compose ps` mostra todos os serviços `healthy`. |
| **2** | **SQLAlchemy Models & Alembic Migrations** | Implementar 9 modelos SQLAlchemy (instruments, market_data, curves, etc.), configurar Alembic e criar a migração inicial que converte 7 tabelas para hypertables TimescaleDB com compressão. | `alireza-database-designer`, `alireza-senior-backend`, `superpowers-test-driven-development` | `make migrate` executa com sucesso. `psql` confirma a criação das 9 tabelas e 7 hypertables. |
| **3** | **Base Connector & Utilities** | Criar a classe `BaseConnector` abstrata, utilitários de data (`date_utils.py`), logging (`logging_config.py`) e retry (`retry.py`). Configurar `pytest` com `conftest.py`. | `alireza-senior-backend`, `ln-520-test-planner`, `superpowers-test-driven-development` | `pytest tests/` passa, validando os utilitários de data. |
| **4** | **Conector BCB SGS** | Implementar o conector para o SGS do Banco Central, buscando ~50 séries macroeconômicas do Brasil. | `alireza-senior-data-engineer`, `superpowers-systematic-debugging` | `python -m src.connectors.bcb_sgs` executa e popula a tabela `macro_series` com dados. |
| **5** | **Conector FRED** | Implementar o conector para o FRED, buscando ~50 séries macroeconômicas dos EUA. | `alireza-senior-data-engineer`, `superpowers-systematic-debugging` | `python -m src.connectors.fred` executa e popula a tabela `macro_series`. |
| **6** | **Conector BCB Focus** | Implementar o conector para a pesquisa Focus, extraindo expectativas de mercado. | `alireza-senior-data-engineer` | `python -m src.connectors.bcb_focus` executa e popula a tabela `macro_series` com dados de expectativas. |
| **7** | **Conectores B3 / Anbima / Tesouro** | Implementar conectores para curvas de juros, títulos públicos e dados de mercado da B3. | `alireza-senior-data-engineer` | Scripts de teste validam a extração de dados de cada fonte. |
| **8** | **Conectores IBGE / STN** | Implementar conectores para dados de inflação desagregada (IBGE) e dados fiscais detalhados (Tesouro Nacional). | `alireza-senior-data-engineer` | Scripts de teste validam a extração de dados. |
| **9** | **Conectores Restantes** | Implementar os conectores para CFTC (posicionamento), Treasury.gov (taxas), Yahoo Finance (ações) e commodities. | `alireza-senior-data-engineer` | Scripts de teste validam a extração de dados. |
| **10** | **Seed Data** | Criar e executar scripts para popular as tabelas de referência `instruments` e `series_metadata` com mais de 200 instrumentos e séries. | `alireza-database-designer` | `make seed` executa com sucesso. `psql` confirma que as tabelas de metadados estão populadas. |
| **11**| **Backfill Histórico** | Criar e executar um script de backfill que busca dados históricos de todas as fontes desde 2010. | `alireza-senior-data-engineer`, `superpowers-executing-plans` | `make backfill` executa. `psql` confirma que as tabelas de dados contêm dados históricos. |
| **12**| **Transforms (Silver Layer)** | Implementar lógicas de transformação para criar dados derivados (ex: construção de curvas de juros a partir de pontos, cálculo de retornos). | `alireza-senior-data-scientist`, `superpowers-test-driven-development` | Testes unitários validam as transformações. |
| **13**| **FastAPI Backend** | Criar uma API REST com FastAPI para servir os dados processados, com endpoints para séries macro, curvas e dados de mercado. | `alireza-senior-backend`, `ln-520-test-planner` | `make api` sobe o servidor. `curl http://localhost:8000/health` retorna `{"status": "ok"}`. |
| **14**| **Data Quality & Verification** | Implementar checagens de qualidade de dados (ex: verificar gaps, outliers) e um script de verificação completo da infraestrutura. | `alireza-standards-quality`, `ln-511-code-quality-checker` | `make quality` e `make verify` executam sem erros. |
| **15**| **GIT & README Final** | Fazer o commit final da Fase 0, criar um tag `v0.1.0-data-infra` e atualizar o `README.md` com as instruções de uso da infraestrutura. | `superpowers-writing-plans` | Repositório no GitHub está completo e tag criada. `README.md` está atualizado. |

---

### Próximos Passos

Para iniciar, o comando a ser executado no Claude Code é:

```
/gsd:new-project
```

O sistema irá então guiar o processo de planejamento e execução da **Etapa 1: Scaffold do Projeto & Docker Compose**, usando o `docs/GUIA_COMPLETO_CLAUDE_CODE_Fase0.md` como referência principal.

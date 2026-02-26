# Plano de Ação: Phase 16 — Cross-Asset Agent v2 & NLP Pipeline

**Data:** 22 de Fevereiro de 2026
**Autor:** Manus AI
**Status:** Pronto para execução

---

## 1. Visão Geral

A **Phase 16** representa um salto qualitativo para o sistema, evoluindo de agentes analíticos isolados para um cérebro centralizado e sensível ao contexto. Esta fase implementa o **Cross-Asset Agent v2**, que introduz a detecção de regimes macroeconômicos, e o **NLP Pipeline**, que extrai sinais de comunicações de bancos centrais. O trabalho está dividido em **2 planos de execução** que cobrem **9 requisitos** e **2 etapas** do guia (etapas 7-8), com tempo estimado de **~70 minutos**.

| Plano | Foco | Requisitos | Etapas do Guia | O que será criado |
|---|---|---|---|---|
| **16-01** | Cross-Asset Agent v2 | CRSV-01, 02, 03, 04 | 7 | `CrossAssetAgent` v2 com HMM, `CrossAssetView` dataclass, LLM para narrativa, consistência cross-asset |
| **16-02** | NLP Pipeline | NLP-01, 02, 03, 04, 05 | 8 | Scrapers COPOM/FOMC, `CentralBankSentimentAnalyzer`, `NLPProcessor`, tabela `nlp_documents` |


## 2. Diagnóstico do Estado Atual

- **Cross-Asset Agent v1:** A versão atual (`src/agents/cross_asset_agent.py`) é um modelo simples baseado em z-score de 6 componentes, produzindo apenas um sinal binário de risk-on/risk-off. Ele será **completamente substituído** pelo v2.
- **NLP Pipeline:** **Inexistente.** A pasta `src/agents/nlp/` não existe e será criada do zero.
- **Modelos de Dados:** O `AgentSignal` é muito simples. A nova `CrossAssetView` será um dataclass rico e estruturado. A tabela `nlp_documents` também é nova.


## 3. Plano de Execução Detalhado

### Plano 16-01: Cross-Asset Agent v2 (Etapa 7)

Este plano substitui o agente v1 por um modelo sofisticado de 4 regimes macroeconômicos, utilizando um **Hidden Markov Model (HMM)**.

| Tarefa | Descrição | Dependências |
|---|---|---|
| **1. `CrossAssetView` Dataclass** | Criar o dataclass em `src/agents/cross_asset_agent.py` para a saída estruturada, incluindo `regime`, `regime_probabilities`, views por ativo, `narrative`, `key_trades`, etc. | Nenhum |
| **2. HMM Regime Classifier** | Implementar o classificador com 4 estados (e.g., Expansion, Contraction, Stagflation, Reflation) usando a biblioteca `hmmlearn`. Treinar o modelo com dados históricos dos 5 agentes. | `hmmlearn`, dados históricos dos 5 agentes |
| **3. Cross-Asset Agent v2** | Refatorar `CrossAssetAgent` para: 1) Coletar outputs dos 5 agentes; 2) Rodar o HMM; 3) Verificar consistência; 4) Usar LLM para gerar a narrativa; 5) Produzir a `CrossAssetView`. | `anthropic` (LLM), outputs dos 5 agentes |
| **4. Testes** | Criar `tests/test_agents/test_cross_asset_v2.py` com testes para o HMM, consistência e a estrutura da `CrossAssetView`. | `pytest` |

### Plano 16-02: NLP Pipeline (Etapa 8)

Este plano cria todo o pipeline para extrair sinais de sentimento de atas e comunicados do COPOM e FOMC.

| Tarefa | Descrição | Dependências |
|---|---|---|
| **1. Scrapers** | Implementar `COPOMScraper` e `FOMCScraper` em `src/agents/nlp/scrapers.py` usando `httpx` e `BeautifulSoup`. | `httpx`, `beautifulsoup4` |
| **2. Sentiment Analyzer** | Criar `CentralBankSentimentAnalyzer` em `src/agents/nlp/sentiment.py` com dicionários de termos hawkish/dovish em PT e EN. | Nenhum |
| **3. Tabela `nlp_documents`** | Definir o modelo em `src/core/models/nlp_documents.py` e criar a migração Alembic. | `sqlalchemy`, `alembic` |
| **4. NLP Processor** | Implementar o `NLPProcessor` em `src/agents/nlp/processor.py` para orquestrar o fluxo: scrape → score → persist. | Scrapers, Analyzer, `nlp_documents` model |
| **5. Testes** | Criar `tests/test_agents/test_nlp_pipeline.py` com testes para os scrapers (usando HTML mockado), o analyzer e o processor. | `pytest`, `respx` |


## 4. Como Executar no Claude Code

Lembre-se da regra de ouro para evitar o bug `tool_use ids`:

```bash
# Iniciar a discussão da fase
/gsd:discuss-phase 16

# LIMPAR O CONTEXTO (MUITO IMPORTANTE)
/clear

# Planejar a fase (pulando o research, pois o CONTEXT.md já foi criado)
/gsd:plan-phase 16 --skip-research

# Executar o primeiro plano
/clear
/gsd:execute-phase 16 --plan 01

# Executar o segundo plano
/clear
/gsd:execute-phase 16 --plan 02

# Ao final da sessão, fazer o merge para o main
Merge your current branch into main and push.
```

Após a conclusão da Phase 16, o sistema terá um "cérebro" macroeconômico e a capacidade de ler e interpretar a linguagem dos bancos centrais, um passo fundamental para a sofisticação do processo de investimento.

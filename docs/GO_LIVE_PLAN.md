# Macro Trading System — Plano de Go-Live

**Versão:** 1.0
**Data:** 2026-02-26
**Sistema:** Macro Trading Platform v4.0 (PMS)

---

## 1. Visão Geral

Este documento detalha o plano passo a passo para o deployment e a ativação do Macro Trading System em um ambiente de produção. O plano cobre desde a preparação da infraestrutura até a ativação do trading ao vivo, garantindo um processo seguro, verificável e robusto.

O plano está dividido em **5 fases principais**:

1.  **Fase 1: Preparação do Ambiente de Produção**
2.  **Fase 2: Deployment da Infraestrutura Core**
3.  **Fase 3: Deployment da Aplicação e Orquestração**
4.  **Fase 4: Verificação Pré-Go-Live e Backfill de Dados**
5.  **Fase 5: Ativação e Monitoramento Contínuo**

---

## 2. Requisitos de Produção

| Componente | Requisito Mínimo | Recomendado |
| :--- | :--- | :--- |
| **Servidor** | 4 vCPUs, 8 GB RAM, 160 GB SSD | 8 vCPUs, 16 GB RAM, 320 GB SSD |
| **Sistema Operacional** | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| **Software** | Docker, Docker Compose, Git | Docker, Docker Compose, Git, Nginx |
| **Rede** | Firewall configurado (UFW) | Firewall, Load Balancer (se houver múltiplos nós) |
| **Domínio** | (Opcional) Domínio para API/UI | Domínio com SSL/TLS (Let's Encrypt) |

---

## 3. Plano de Go-Live Detalhado

### Fase 1: Preparação do Ambiente de Produção

**Objetivo:** Configurar um servidor seguro e pronto para receber a aplicação.

| Passo | Ação | Comando/Verificação |
| :--- | :--- | :--- |
| **1.1** | **Provisionar Servidor:** Criar um novo Droplet na DigitalOcean (ou VM em outro provedor) com os requisitos recomendados. | `ssh root@<ip_do_servidor>` |
| **1.2** | **Criar Usuário Sudo:** Criar um usuário não-root com privilégios sudo para executar as operações. | `adduser <username> && usermod -aG sudo <username>` |
| **1.3** | **Configurar Firewall (UFW):** Permitir apenas tráfego SSH (22), HTTP (80) e HTTPS (443). | `ufw allow OpenSSH && ufw allow http && ufw allow https && ufw enable` |
| **1.4** | **Instalar Dependências:** Instalar Docker, Docker Compose e Git. | `apt update && apt install docker.io docker-compose-v2 git -y` |
| **1.5** | **Clonar Repositório:** Clonar o projeto do GitHub para o servidor. | `git clone https://github.com/mcauduro0/Macro_Trading.git /opt/macro_trading` |
| **1.6** | **Configurar Arquivo de Segredos:** Criar o arquivo `.env` a partir do `.env.example` e preencher **todas** as senhas e chaves de API. | `cd /opt/macro_trading && cp .env.example .env && nano .env` |

### Fase 2: Deployment da Infraestrutura Core

**Objetivo:** Iniciar os serviços de base (bancos de dados, message broker) e garantir que estejam operacionais.

| Passo | Ação | Comando/Verificação |
| :--- | :--- | :--- |
| **2.1** | **Iniciar Serviços Core:** Usar Docker Compose para iniciar TimescaleDB, Redis e MongoDB. | `cd /opt/macro_trading && docker compose up -d timescaledb redis mongodb` |
| **2.2** | **Verificar Saúde dos Serviços:** Garantir que todos os contêineres estão com status `healthy`. | `docker compose ps` (esperar até que todos mostrem `healthy`) |
| **2.3** | **Verificar Conectividade:** Executar o script de verificação de conectividade para confirmar que a aplicação pode se conectar aos bancos de dados. | `cd /opt/macro_trading && python3 scripts/verify_connectivity.py` |
| **2.4** | **Executar Migrações do Banco de Dados:** Aplicar todas as migrações do Alembic para criar o schema completo no TimescaleDB. | `cd /opt/macro_trading && make migrate` |
| **2.5** | **Verificar Schema:** Conectar no banco e verificar se as tabelas (ex: `market_data`, `portfolio_positions`) foram criadas. | `make psql` e depois `\dt` |

### Fase 3: Deployment da Aplicação e Orquestração

**Objetivo:** Iniciar os serviços da aplicação (API, Dagster) e o stack de monitoramento.

| Passo | Ação | Comando/Verificação |
| :--- | :--- | :--- |
| **3.1** | **Iniciar API e Serviços de Mensageria:** Iniciar os contêineres da API, Kafka e MinIO. | `cd /opt/macro_trading && docker compose --profile full up -d api kafka minio` |
| **3.2** | **Verificar Saúde da API:** Acessar o endpoint de saúde da API. | `curl http://localhost:8000/health` (deve retornar `{"status":"ok"}`) |
| **3.3** | **Iniciar Stack de Orquestração e Monitoramento:** Iniciar Dagster e Grafana. | `cd /opt/macro_trading && docker compose --profile dagster --profile monitoring up -d` |
| **3.4** | **Verificar Acesso às UIs:** | - **Dagster UI:** `http://<ip_do_servidor>:3001`
- **Grafana UI:** `http://<ip_do_servidor>:3002`
- **MinIO UI:** `http://<ip_do_servidor>:9001` |
| **3.5** | **Configurar Nginx (Opcional, Recomendado):** Configurar Nginx como proxy reverso para a API e UIs, com terminação SSL. | Criar arquivo de configuração em `/etc/nginx/sites-available/` |

### Fase 4: Verificação Pré-Go-Live e Backfill de Dados

**Objetivo:** Popular o banco de dados com dados históricos e executar uma bateria final de testes no ambiente de produção.

| Passo | Ação | Comando/Verificação |
| :--- | :--- | :--- |
| **4.1** | **Executar Seeding de Dados:** Popular as tabelas de referência (instrumentos, metadados de séries). | `cd /opt/macro_trading && make seed` |
| **4.2** | **Executar Backfill Histórico:** Carregar dados históricos de mercado. Use `backfill-fast` para um setup mais rápido. | `cd /opt/macro_trading && make backfill` (completo) ou `make backfill-fast` (rápido) |
| **4.3** | **Executar Pipeline Diário Manualmente:** Rodar o pipeline completo para o dia atual para gerar sinais, portfólios e análises. | `cd /opt/macro_trading && python3 scripts/daily_run.py` |
| **4.4** | **Executar Verificação de Infraestrutura:** Rodar o script completo de verificação. | `cd /opt/macro_trading && python3 scripts/verify_infrastructure.py --strict` |
| **4.5** | **Executar Verificação das Fases:** Rodar os scripts de verificação para as fases de desenvolvimento. | `python3 scripts/verify_phase2.py && python3 scripts/verify_phase3.py` |
| **4.6** | **Executar Teste de Fumaça do PMS:** Seguir os passos da seção 4 do `GOLIVE_CHECKLIST.md` para simular um ciclo de vida de trade. | `docs/GOLIVE_CHECKLIST.md` |
| **4.7** | **Criar Backup Inicial:** Realizar o primeiro backup completo do sistema. | `cd /opt/macro_trading && bash scripts/backup.sh` |

### Fase 5: Ativação e Monitoramento Contínuo

**Objetivo:** Ativar a execução automática do sistema e estabelecer rotinas de monitoramento.

| Passo | Ação | Comando/Verificação |
| :--- | :--- | :--- |
| **5.1** | **Ativar Schedules do Dagster:** No Dagster UI (`http://<ip_do_servidor>:3001`), ir para a aba "Schedules" e ativar os 3 schedules: `daily_pipeline_schedule`, `pms_eod_schedule`, `pms_preopen_schedule`. | Verificar o status "Running" nos schedules. |
| **5.2** | **Configurar Cron Job de Backup (Recomendado):** Adicionar o script de backup ao crontab do sistema para rodar diariamente. | `crontab -e` e adicionar `0 3 * * * /bin/bash /opt/macro_trading/scripts/backup.sh` |
| **5.3** | **Revisar Runbook Operacional:** Ler o `OPERATIONAL_RUNBOOK.md` para entender os procedimentos diários, semanais e de emergência. | `docs/OPERATIONAL_RUNBOOK.md` |
| **5.4** | **Monitorar Primeira Execução Agendada:** Acompanhar a primeira execução do `daily_pipeline_schedule` no Dagster UI para garantir que todos os assets foram materializados com sucesso. | Verificar os logs de execução no Dagster UI. |
| **5.5** | **Go-Live:** O sistema está oficialmente em produção. O trading pode começar seguindo o workflow diário descrito no `OPERATIONAL_RUNBOOK.md`. | Parabéns! |

---

## 4. Plano de Rollback

Em caso de falha crítica em qualquer fase, o plano de rollback é o seguinte:

1.  **Parar todos os serviços:** `docker compose down -v`
2.  **Remover o diretório do projeto:** `rm -rf /opt/macro_trading`
3.  **Desprovisionar o servidor.**

Para falhas de dados durante a Fase 4, utilize o script `scripts/restore.sh` para restaurar o banco de dados a partir do último backup válido.

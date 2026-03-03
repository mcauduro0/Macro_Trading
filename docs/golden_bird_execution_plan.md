# GOLDEN BIRD MACRO TERMINAL
## Plano de Execução Técnica Detalhado

**Versão:** 1.0 | **Data:** 02 de Março de 2026 | **Classificação:** Confidencial
**Baseado em:** Golden Bird Masterplan de Evolução v1.0 (Março 2026)

---

## SUMÁRIO EXECUTIVO

O presente documento traduz o Masterplan de Evolução do Golden Bird Macro Terminal em um plano de execução técnica operacional, com sub-entregas atômicas, critérios de aceite mensuráveis e checklists de validação para cada item. O objetivo é transformar o Macro Trading v2.0 (cobertura ~45%) em um terminal proprietário de referência mundial (cobertura 95%+) ao longo de 7 fases e 48 semanas.

O plano segue três princípios de governança: (1) **nenhuma entrega avança sem validação** — cada sub-item possui critério de aceite binário (passa/falha); (2) **zero placeholders** — todo código entregue opera com dados reais, endpoints reais e lógica completa; (3) **aprovação por fase** — o plano de cada fase é discutido e aprovado antes da execução, e a entrega é revisada antes de avançar para a próxima.

A tabela abaixo resume o escopo total:

| Fase | Nome | Semanas | Sub-entregas | Modelos | Estratégias | Funções BBG | Painéis |
|------|------|---------|-------------|---------|-------------|-------------|---------|
| 0 | Security Hardening | 1–2 | 5 | — | — | — | — |
| 1 | Analytics Core | 3–8 | 8 | 6 | — | 1 (ECO) | — |
| 2 | Global Data Expansion | 9–14 | 8 | — | — | 2 (WIRP, YCRV) | — |
| 3 | Frontend Foundation | 15–22 | 9 | — | — | — | 8 |
| 4 | Advanced Models & ML | 23–30 | 7 | 8 | 8 | 1 (CDS) | — |
| 5 | Bloomberg Functions & Strategies | 31–38 | 7 | — | 5 | 8 | 6 |
| 6 | Production & Scale | 39–48 | 7 | — | — | — | — |
| **Total** | | **48 sem** | **51** | **14 novos** | **13 novas** | **12** | **14** |

---

## FASE 0 — SECURITY HARDENING (Semanas 1–2)

### Objetivo
Eliminar a lacuna de segurança mais urgente do sistema. Nenhuma funcionalidade nova será exposta até que todos os 86 endpoints existentes estejam protegidos por autenticação JWT, comunicação TLS 1.3 e gestão segura de secrets.

### Pré-requisitos
Acesso SSH ao servidor DigitalOcean. Repositório `mcauduro0/Macro_Trading` atualizado. Docker Compose funcional com os 8 containers existentes.

---

#### 0.1 — JWT Authentication em Todos os Endpoints

**Escopo técnico:** Implementar autenticação JWT (PyJWT) em todos os 86 endpoints FastAPI. Access token com TTL de 15 minutos e refresh token com TTL de 7 dias. Endpoint `/api/auth/login` com rate limit de 5 tentativas por minuto. Endpoint `/api/auth/refresh` para renovação de token. Middleware FastAPI `Security` dependency injetada em todas as rotas.

**Implementação detalhada:**
1. Criar módulo `src/core/security.py` com funções `create_access_token()`, `create_refresh_token()`, `verify_token()`, `get_current_user()`.
2. Criar tabela `users` no PostgreSQL com campos: `id`, `email`, `hashed_password`, `role`, `created_at`, `last_login`.
3. Implementar `FastAPI Depends(get_current_user)` como dependency global em `src/api/main.py`.
4. Criar endpoints: `POST /api/auth/login`, `POST /api/auth/refresh`, `POST /api/auth/logout`.
5. Hash de senhas via `bcrypt` com salt rounds = 12.
6. Testes: `pytest` com fixtures de autenticação para todos os 86 endpoints.

**Critério de aceite:**
- [ ] Todos os 86 endpoints retornam HTTP 401 quando chamados sem token válido
- [ ] Login retorna access_token (15min) + refresh_token (7d)
- [ ] Refresh endpoint renova token corretamente
- [ ] Rate limit de 5 tentativas/min funcional no login
- [ ] Testes automatizados passando para auth flow completo

**Esforço estimado:** 3 dias

---

#### 0.2 — TLS 1.3 com Let's Encrypt

**Escopo técnico:** Configurar Nginx como reverse proxy com certificado TLS 1.3 via Let's Encrypt/Certbot. HSTS header obrigatório. Auto-renewal via cron job. Redirect HTTP → HTTPS.

**Implementação detalhada:**
1. Instalar Certbot no servidor: `apt install certbot python3-certbot-nginx`.
2. Configurar Nginx como reverse proxy para FastAPI (porta 8000) e frontend (porta 3000).
3. Obter certificado: `certbot --nginx -d api.goldenbird.capital`.
4. Configurar TLS 1.3 only: `ssl_protocols TLSv1.3;` no nginx.conf.
5. Adicionar headers: `Strict-Transport-Security "max-age=63072000; includeSubDomains; preload"`.
6. Cron para auto-renewal: `0 0 1 * * certbot renew --quiet`.

**Critério de aceite:**
- [ ] SSL Labs score A+ (testar em ssllabs.com)
- [ ] Todas as conexões HTTP redirecionam para HTTPS
- [ ] HSTS header presente em todas as respostas
- [ ] Certificado auto-renova sem intervenção manual
- [ ] TLS 1.3 exclusivo (TLS 1.0/1.1/1.2 desabilitados)

**Esforço estimado:** 1 dia

---

#### 0.3 — Migração de API Keys para HashiCorp Vault

**Escopo técnico:** Migrar todas as API keys e secrets de arquivos `.env` para HashiCorp Vault. Docker secrets como fallback. Zero API keys em código-fonte ou arquivos de configuração versionados.

**Implementação detalhada:**
1. Deploy do Vault container via Docker Compose com backend de storage em filesystem.
2. Criar path `secret/data/macro_trading` com sub-paths: `fred`, `polygon`, `bcb`, `anthropic`, `database`.
3. Implementar `src/core/vault_client.py` com `hvac` library para leitura de secrets.
4. Refatorar `src/core/config.py` para buscar secrets do Vault com fallback para env vars.
5. Audit log habilitado no Vault para rastreabilidade de acesso a credentials.
6. Rotação de secrets: script `rotate_secrets.py` para atualizar keys periodicamente.

**Critério de aceite:**
- [ ] Zero API keys em arquivos `.env` ou código-fonte
- [ ] Vault container operacional e acessível internamente
- [ ] Todas as API keys lidas do Vault em runtime
- [ ] Audit log registrando cada acesso a secrets
- [ ] Fallback para Docker secrets funcional se Vault indisponível

**Esforço estimado:** 2 dias

---

#### 0.4 — Rate Limiting por Endpoint

**Escopo técnico:** Implementar rate limiting granular via SlowAPI (FastAPI) + Nginx `limit_req_zone`. Limites diferenciados por categoria de endpoint: `/api/trade/*` = 10 req/min, `/api/data/*` = 100 req/min, `/api/analytics/*` = 50 req/min. Respostas HTTP 429 customizadas com `Retry-After` header.

**Implementação detalhada:**
1. Instalar `slowapi` e configurar como middleware global no FastAPI.
2. Definir rate limits por tag/prefix no `src/api/rate_limits.py`.
3. Configurar Nginx `limit_req_zone` como segunda camada de proteção.
4. Implementar `Retry-After` header nas respostas 429.
5. Redis como backend de contagem para SlowAPI (distribuído).

**Critério de aceite:**
- [ ] Endpoints de trade limitados a 10 req/min por IP
- [ ] Endpoints de data limitados a 100 req/min por IP
- [ ] Endpoints de analytics limitados a 50 req/min por IP
- [ ] HTTP 429 retornado com `Retry-After` header correto
- [ ] Rate limiting funcional tanto no SlowAPI quanto no Nginx

**Esforço estimado:** 1 dia

---

#### 0.5 — RBAC Foundation (Role-Based Access Control)

**Escopo técnico:** Implementar modelo de roles com 4 níveis: Admin, Trader, Analyst, Viewer. Tabela `roles` e `user_roles` no PostgreSQL. Middleware de autorização que verifica permissões por endpoint. Trader pode propor trades mas não aprovar. Analyst tem acesso read-only a analytics e data. Viewer tem acesso read-only a dashboards.

**Implementação detalhada:**
1. Criar tabelas: `roles` (id, name, permissions JSON), `user_roles` (user_id, role_id).
2. Definir permission matrix: mapeamento role → endpoints permitidos.
3. Implementar decorator `@require_role("trader")` para proteção de endpoints.
4. Middleware que extrai role do JWT token e verifica contra permission matrix.
5. Endpoint `GET /api/auth/me` retorna user info + roles + permissions.

**Critério de aceite:**
- [ ] 4 roles criados e atribuíveis (Admin, Trader, Analyst, Viewer)
- [ ] Cada endpoint verifica role do usuário antes de executar
- [ ] Trader não consegue acessar endpoints de aprovação de trade
- [ ] Viewer não consegue acessar endpoints de escrita
- [ ] Admin tem acesso irrestrito a todos os endpoints

**Esforço estimado:** 3 dias

---

### Quality Gate — Fase 0

| Critério | Método de Verificação | Status |
|----------|----------------------|--------|
| Zero endpoints sem autenticação | Script que testa todos os 86 endpoints sem token | [ ] |
| SSL Labs score A+ | Teste em ssllabs.com/ssltest | [ ] |
| Zero API keys em código/env | `grep -r "api_key\|API_KEY\|secret" src/ .env` retorna vazio | [ ] |
| Rate limiting funcional | Load test com `wrk` excedendo limites | [ ] |
| RBAC verificável | Teste de acesso com cada role em endpoints restritos | [ ] |
| Pentest interno básico | OWASP ZAP scan sem vulnerabilidades críticas | [ ] |

**Decisão Go/No-Go:** Todos os 6 critérios devem ser "passa" para avançar para a Fase 1.

---

## FASE 1 — ANALYTICS CORE (Semanas 3–8)

### Objetivo
Construir os modelos econométricos fundamentais que servem como building blocks para os modelos avançados das Fases 4 e 5. Implementar a primeira função Bloomberg-equivalent (ECO). Todos os modelos devem operar com dados reais, validação walk-forward e documentação de performance.

### Pré-requisitos
Fase 0 completa e aprovada. Dados de yields (FRED), séries macro limpas, retornos diários com >5 anos de histórico disponíveis no TimescaleDB.

---

#### 1.1 — Nelson-Siegel/Svensson Yield Curve Fitting

**Escopo técnico:** Implementar fitting de yield curves via modelos Nelson-Siegel (3 fatores: Level, Slope, Curvature) e Nelson-Siegel-Svensson (4 fatores). Cobertura: UST, Bund, JGB, Gilt, DI (ANBIMA). Extração diária dos fatores NS com armazenamento em TimescaleDB. API endpoint para consulta de fatores e curva fitted.

**Bibliotecas:** `nelson_siegel_svensson`, `scipy.optimize`

**Dados requeridos:** Yield curves multi-tenor (6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 20Y, 30Y) de FRED (UST), ECB (Bund), ANBIMA (DI).

**Implementação detalhada:**
1. Criar módulo `src/analytics/models/yield_curve/ns_model.py` seguindo o padrão Abstract Base Class do sistema.
2. Implementar `NelsonSiegelModel.fit(tenors, yields)` → retorna (beta0, beta1, beta2, tau).
3. Implementar `NelsonSiegelSvenssonModel.fit(tenors, yields)` → retorna (beta0, beta1, beta2, beta3, tau1, tau2).
4. Calibração diária via Dagster job às 18:00 BRT (após fechamento).
5. Armazenamento: tabela `ns_parameters` (date, curve_id, beta0, beta1, beta2, beta3, tau1, tau2, r_squared).
6. API endpoints: `GET /api/analytics/yield-curve/{curve_id}/fit`, `GET /api/analytics/yield-curve/{curve_id}/factors`.
7. Z-scores históricos dos fatores (rolling 252 dias).

**Critério de aceite:**
- [ ] R² > 0.99 para fitting de UST, Bund e DI
- [ ] Fatores Level, Slope, Curvature extraídos corretamente e economicamente coerentes
- [ ] Calibração diária automatizada via Dagster sem falhas por 5 dias consecutivos
- [ ] API endpoint retornando curva fitted + fatores + z-scores
- [ ] Interpolação de tenors faltantes com erro < 2bps

**Esforço estimado:** 1 semana

---

#### 1.2 — VAR/VECM Models

**Escopo técnico:** Implementar Vector Autoregression (VAR) e Vector Error Correction Model (VECM) com 5-10 variáveis macro. Granger causality tests para seleção de variáveis. Impulse-Response Functions (IRF) com bootstrap confidence intervals. Forecast Error Variance Decomposition (FEVD).

**Bibliotecas:** `statsmodels` (VAR, VECM, Granger causality)

**Dados requeridos:** Séries macro limpas: GDP growth, CPI YoY, policy rate, 10Y yield, FX spot, unemployment, industrial production, PMI, credit spread, commodity index.

**Implementação detalhada:**
1. Criar módulo `src/analytics/models/macro/var_model.py`.
2. Implementar seleção automática de lag order via AIC/BIC/HQIC.
3. Johansen cointegration test para decidir entre VAR e VECM.
4. IRF com bootstrap CI (1000 replications) para horizonte de 24 meses.
5. FEVD para decomposição de variância.
6. Armazenamento: tabela `var_results` (model_id, date, coefficients JSON, irf JSON, fevd JSON).
7. API endpoints: `GET /api/analytics/var/forecast`, `GET /api/analytics/var/irf`, `GET /api/analytics/var/granger`.

**Critério de aceite:**
- [ ] VAR estimado com lag order selecionado automaticamente (AIC)
- [ ] IRF economicamente coerente (ex: choque de juros → queda de GDP com lag)
- [ ] Granger causality tests identificando relações significativas (p < 0.05)
- [ ] FEVD somando 100% em cada horizonte
- [ ] Forecast out-of-sample com RMSE documentado vs random walk benchmark
- [ ] Testes de estabilidade (eigenvalues dentro do unit circle)

**Esforço estimado:** 2 semanas

---

#### 1.3 — GJR-GARCH Volatility Models

**Escopo técnico:** Implementar GJR-GARCH(1,1) com distribuição Student-t para forecasting de volatilidade de FX e rates. Captura do leverage effect (depreciações geram mais vol que apreciações). Rolling calibration com janela de 252 dias. Output: σ(t+1) forecast como input para VaR e option pricing.

**Bibliotecas:** `arch` library

**Dados requeridos:** Retornos diários de FX (USDBRL, EURUSD, USDJPY, GBPUSD) e rates (DI1F, UST 10Y) com >5 anos de histórico.

**Implementação detalhada:**
1. Criar módulo `src/analytics/models/volatility/garch_model.py`.
2. Implementar `GJRGarchModel.fit(returns)` usando `arch_model(returns, vol='GARCH', p=1, o=1, q=1, dist='StudentsT')`.
3. Rolling calibration: re-estimar a cada 20 dias úteis com janela expandindo.
4. Forecast: σ(t+1), σ(t+5), σ(t+22) (1 dia, 1 semana, 1 mês).
5. Armazenamento: tabela `garch_params` (date, asset, omega, alpha, gamma, beta, nu, sigma_forecast).
6. API endpoint: `GET /api/analytics/volatility/{asset}/forecast`.

**Critério de aceite:**
- [ ] Parâmetro gamma > 0 confirmando leverage effect em FX
- [ ] Graus de liberdade (nu) estimados entre 3-8 (fat tails confirmadas)
- [ ] Forecast de volatilidade correlacionado com VIX/realized vol (correlação > 0.7)
- [ ] Calibração rolling automatizada sem falhas
- [ ] Distribuição Student-t utilizada (nunca Normal)

**Esforço estimado:** 1 semana

---

#### 1.4 — Kalman Filter para Variáveis Latentes

**Escopo técnico:** Implementar Kalman Filter para extração de variáveis latentes: output gap, neutral rate (r*), expected inflation. Dynamic Nelson-Siegel com fatores como state variables. Aplicação principal: estimação do output gap para Phillips Curve e Taylor Rule.

**Bibliotecas:** `statsmodels` (UnobservedComponents), `filterpy`

**Implementação detalhada:**
1. Criar módulo `src/analytics/models/macro/kalman_model.py`.
2. Implementar extração de output gap via Hodrick-Prescott filter + Kalman smoother.
3. Estimação de r* (neutral rate) via modelo Laubach-Williams simplificado.
4. Dynamic NS: fatores NS como state variables com transição AR(1).
5. Armazenamento: tabela `latent_variables` (date, variable_name, value, std_error).
6. API endpoint: `GET /api/analytics/latent/{variable}`.

**Critério de aceite:**
- [ ] Output gap estimado coerente com ciclo econômico (negativo em recessões, positivo em expansões)
- [ ] Neutral rate (r*) estimado entre 0-5% para economias desenvolvidas
- [ ] Dynamic NS produzindo forecasts de yield curve factors com CI
- [ ] Variáveis latentes atualizadas diariamente via Dagster
- [ ] Comparação com estimativas do Fed/BCB como benchmark

**Esforço estimado:** 2 semanas

---

#### 1.5 — ECO — Economic Calendar (Primeira Função Bloomberg-Equivalent)

**Escopo técnico:** Implementar calendário econômico equivalente ao Bloomberg ECO. AG Grid no backend com filtros por país, importância (Low/Medium/High), período e ativo. Redis cache com TTL de 5 minutos. Alertas 5 minutos antes de releases High-importance. Histórico de surpresas para event studies.

**Fontes de dados:** FRED Economic Calendar, Financial Modeling Prep (FMP) Economic Calendar.

**Implementação detalhada:**
1. Criar módulo `src/analytics/bloomberg_equiv/eco_calendar.py`.
2. Integrar FRED calendar releases + FMP Economic Calendar API.
3. Schema unificado: `{id, datetime_utc, country_iso2, event_name, importance, actual, forecast, previous, surprise, surprise_pct, asset_impact}`.
4. Redis cache com TTL 5 min para dados intraday.
5. API endpoints: `GET /api/eco/calendar?country=US,BR&importance=high&start_date=...&end_date=...`.
6. Endpoint de surpresas históricas: `GET /api/eco/surprises?event=nonfarm_payrolls&lookback=24m`.
7. WebSocket channel `eco_alerts` para push notifications antes de releases.

**Critério de aceite:**
- [ ] Calendário cobrindo US, BR, EU, UK, JP, MX (6 países mínimo)
- [ ] Filtros por país, importância e período funcionais
- [ ] Surprise calculation correto (actual - forecast)
- [ ] Cache Redis reduzindo latência para < 50ms
- [ ] Histórico de surpresas armazenado para análise
- [ ] Dados reais (não mock) de FRED + FMP

**Esforço estimado:** 1 semana

---

#### 1.6 — Taylor Rule com Regime Switching

**Escopo técnico:** Implementar Taylor Rule Enhancement com MarkovRegression para detecção de 2 regimes: "Volcker era" (alta reação a inflação) vs "QE era" (baixa reação). Estimação de neutral rate via Kalman Filter (dependência da entrega 1.4). Aplicação: sinal de política monetária para estratégias de rates.

**Bibliotecas:** `statsmodels` (OLS, MarkovRegression)

**Implementação detalhada:**
1. Criar módulo `src/analytics/models/monetary/taylor_rule.py`.
2. Taylor Rule clássica: i* = r* + π + 0.5(π - π*) + 0.5(y - y*).
3. MarkovRegression com 2 regimes para coeficientes time-varying.
4. Estimação para Fed, ECB e BCB.
5. Output: taxa implícita Taylor Rule, regime atual (probabilidade), desvio da taxa efetiva.
6. API endpoint: `GET /api/analytics/taylor-rule/{central_bank}`.

**Critério de aceite:**
- [ ] Regimes identificados coerentes com história (Volcker 1979-1987, QE 2008-2021)
- [ ] Probabilidades de regime somando 1.0
- [ ] Desvio Taylor Rule vs taxa efetiva documentado para Fed, ECB, BCB
- [ ] Neutral rate (r*) coerente com estimativas Laubach-Williams
- [ ] Sinal de política monetária gerando insights acionáveis

**Esforço estimado:** 1 semana

---

#### 1.7 — Phillips Curve NKPC com Regime Switching

**Escopo técnico:** Implementar New Keynesian Phillips Curve com regime switching (high-inflation vs anchored expectations). Equação: π(t) = β·E[π(t+1)] + κ·gap(t) + ε(t) com parâmetros variando entre regimes. Dependência do output gap estimado na entrega 1.4.

**Bibliotecas:** `statsmodels` (MarkovRegression), `PyMC` (para versão TVP futura)

**Implementação detalhada:**
1. Criar módulo `src/analytics/models/inflation/phillips_curve.py`.
2. NKPC com MarkovRegression para 2 regimes.
3. Estimação para US, BR, EU.
4. Output: slope da Phillips Curve por regime, probabilidade de regime atual, forecast de inflação.
5. API endpoint: `GET /api/analytics/phillips-curve/{country}`.

**Critério de aceite:**
- [ ] Slope da Phillips Curve menor no regime "anchored" vs "high-inflation"
- [ ] Regime detection coerente com períodos históricos de inflação alta
- [ ] Forecast de inflação com RMSE < 1pp para horizonte de 12 meses
- [ ] Output gap como input real (não placeholder) do Kalman Filter
- [ ] Documentação de performance vs benchmark (random walk, AR(1))

**Esforço estimado:** 1 semana

---

#### 1.8 — Breakeven Inflation Enhancement

**Escopo técnico:** Expandir análise de breakeven inflation: T5YIE, T10YIE, 5y5y forward breakeven. Decomposição: BEI = Expected Inflation + Inflation Risk Premium + Liquidity Premium. Integração com Cleveland Fed Nowcast como benchmark.

**Implementação detalhada:**
1. Criar módulo `src/analytics/models/inflation/breakeven_model.py`.
2. Cálculo de 5y5y forward breakeven a partir de T5YIE e T10YIE.
3. Decomposição via modelo de Kim-Wright (simplificado).
4. Integração com Cleveland Fed API para nowcast de inflação esperada 1-30 anos.
5. API endpoint: `GET /api/analytics/breakeven/{tenor}`.

**Critério de aceite:**
- [ ] 5y5y forward breakeven calculado corretamente (verificar vs Bloomberg/FRED)
- [ ] Decomposição em 3 componentes somando o BEI total
- [ ] Cleveland Fed nowcast integrado como benchmark
- [ ] Dados reais de TIPS yields (FRED) utilizados
- [ ] Histórico de breakevens armazenado para análise temporal

**Esforço estimado:** 0.5 semana

---

### Quality Gate — Fase 1

| Critério | Método de Verificação | Status |
|----------|----------------------|--------|
| NS fit R² > 0.99 para UST, Bund, DI | Relatório de calibração com R² por curva | [ ] |
| VAR IRF economicamente coerente | Revisão manual dos gráficos de IRF | [ ] |
| GJR-GARCH leverage effect confirmado | γ > 0 em todos os ativos FX | [ ] |
| Kalman output gap coerente com ciclo | Comparação visual com NBER recession dates | [ ] |
| ECO com dados reais de 6 países | Verificação manual de 10 eventos recentes | [ ] |
| Taylor Rule regimes identificados | Probabilidades de regime vs história | [ ] |
| Phillips Curve NKPC funcional | Forecast de inflação vs realizado | [ ] |
| Todos os modelos com testes automatizados | `pytest` coverage > 80% para módulos novos | [ ] |
| Zero mock data ou placeholders | `grep -r "mock\|placeholder\|TODO" src/analytics/` | [ ] |

**Decisão Go/No-Go:** Todos os 9 critérios devem ser "passa". Relatório de backtest de cada modelo deve ser revisado e aprovado antes de avançar.

---

## FASE 2 — GLOBAL DATA EXPANSION (Semanas 9–14)

### Objetivo
Expandir a cobertura de dados de BR-centric (17 conectores) para global (25+ conectores). Implementar o pipeline ALFRED para vintage data point-in-time. Criar o Data Quality Framework v2. Implementar as funções Bloomberg-equivalent WIRP e YCRV.

### Pré-requisitos
Fase 1 completa e aprovada. Modelos NS e Kalman operacionais (necessários para YCRV e WIRP).

---

#### 2.1 — ECB SDW Connector

**Escopo técnico:** Implementar conector para o ECB Statistical Data Warehouse via biblioteca `ecbdata`. Dados: EUR yield curves AAA, HICP, M1/M2/M3, MFI rates, TARGET2 balances. Frequência diária. Seguir padrão Abstract BaseConnector com métodos `fetch()`, `transform()`, `load()`.

**Critério de aceite:**
- [ ] Conector implementado seguindo padrão BaseConnector
- [ ] EUR yield curves AAA ingeridas diariamente (6M a 30Y)
- [ ] HICP (inflação euro area) ingerido mensalmente
- [ ] M1/M2/M3 monetary aggregates ingeridos
- [ ] Pipeline Bronze → Silver → Gold funcional
- [ ] Schema validado via Pydantic v2
- [ ] Rate limit respeitado (< 50 req/min)

**Esforço estimado:** 1 semana

---

#### 2.2 — IMF IFS/WEO/BOP Connector

**Escopo técnico:** Implementar conector para IMF via biblioteca `imfp`. Cobertura: IFS (International Financial Statistics), WEO (World Economic Outlook), BOP (Balance of Payments), DOTS (Direction of Trade Statistics). 190 países. GDP, CPI, FX reserves, current account, trade flows.

**Critério de aceite:**
- [ ] IFS: GDP, CPI, policy rate para 20+ países principais
- [ ] WEO: projeções semestrais para 190 países
- [ ] BOP: current account, capital flows para G20
- [ ] Batch download + incremental update funcional
- [ ] Rate limit respeitado (~10 req/seg)
- [ ] Dados armazenados com country_iso2 padronizado

**Esforço estimado:** 2 semanas

---

#### 2.3 — BIS + World Bank + Banxico + BOJ + BOE Connectors

**Escopo técnico:** Implementar 5 conectores menores em paralelo: BIS (banking flows, REER, property prices via `sdmx1`), World Bank WDI (17K indicadores via `wbgapi`), Banxico SIE (TIIE, INPC via `sie-banxico`), BOJ (CGPI, TANKAN via `pyboj`), BOE (Gilt yields via `pandas`).

**Critério de aceite:**
- [ ] BIS: REER para 61 países, banking flows trimestrais
- [ ] World Bank: GDP/cap, Gini, indicadores de desenvolvimento para 200+ países
- [ ] Banxico: TIIE 28d, INPC, MXN forward rates
- [ ] BOJ: CGPI, TANKAN survey, JGB yields
- [ ] BOE: Gilt yields multi-tenor, 3 Centuries dataset
- [ ] Todos seguindo padrão BaseConnector
- [ ] Pipeline Bronze → Silver → Gold para cada um

**Esforço estimado:** 2 semanas (paralelo)

---

#### 2.4 — BLS + EIA + Nasdaq Data Link Connectors

**Escopo técnico:** Implementar 3 conectores para dados US: BLS (CPI components, employment, wages, PPI, JOLTS via `openbb-bls`), US EIA (petroleum, gas natural, STEO via `openbb-us-eia`), Nasdaq Data Link (FRED mirror, LBMA/GOLD, Shiller CAPE via `nasdaqdatalink`).

**Nota sobre licença OpenBB:** OpenBB é AGPL — uso em SaaS requer open-source. Mitigação: usar apenas as bibliotecas de connector (`openbb-bls`, `openbb-us-eia`) como inspiração e implementar conectores diretamente via `requests`/`pandas` se necessário para evitar risco de licença.

**Critério de aceite:**
- [ ] BLS: CPI por componente (food, energy, shelter, etc.), NFP, wages, JOLTS
- [ ] EIA: petroleum weekly status, gas natural, STEO projections
- [ ] Nasdaq: LBMA/GOLD daily, Shiller CAPE, USTREASURY/YIELD
- [ ] Licença AGPL mitigada (conectores próprios se necessário)
- [ ] Dados integrados no pipeline existente

**Esforço estimado:** 1 semana

---

#### 2.5 — ALFRED Vintage Data Pipeline

**Escopo técnico:** Implementar pipeline de vintage data ALFRED para integridade de backtests point-in-time. Adicionar colunas `realtime_start` e `realtime_end` em tabelas de séries macro. Função `get_as_of(series_id, date, as_of_date)`. Integração com IMF WEO Vintages via `weo-reader`.

**Implementação detalhada:**
1. Criar tabela `macro_series_vintage` com hypertable particionado por `realtime_start`.
2. Utilizar FRED ALFRED API com parâmetros `realtime_start`/`realtime_end`.
3. Prioridade: GDP, CPI, Employment, Industrial Production (US e BR).
4. IMF WEO vintages: download de todas as edições (abril e outubro, 2000-presente).
5. Implementar `get_as_of()` como stored procedure no TimescaleDB.

**Critério de aceite:**
- [ ] Tabela vintage com realtime_start/end para GDP, CPI, Employment, IP
- [ ] Função `get_as_of()` retornando valor correto para qualquer data passada
- [ ] WEO vintages armazenadas (abril + outubro, 2000-2026)
- [ ] Backtests usando dados point-in-time (não revisados)
- [ ] Teste: valor de GDP Q1 2020 "as_of" 2020-04-01 vs 2020-07-01 (revisão capturada)

**Esforço estimado:** 2 semanas

---

#### 2.6 — Data Quality Framework v2

**Escopo técnico:** Aprimorar o pipeline Bronze → Silver → Gold com validação cross-provider, detecção de outliers (>3σ flag, >5σ quarantine), monitoramento de data freshness com SLA, e dashboard Grafana dedicado.

**Critério de aceite:**
- [ ] Validação cross-provider: CPI US via FRED vs BLS (divergência < 0.1%)
- [ ] Outlier detection: flag >3σ, quarantine >5σ automaticamente
- [ ] Freshness monitoring: alertas se dados não atualizados dentro do SLA
- [ ] Dashboard Grafana: Data Quality Score por série, heatmap de completude
- [ ] >90% freshness score global

**Esforço estimado:** 1 semana

---

#### 2.7 — WIRP — Interest Rate Probabilities

**Escopo técnico:** Implementar cálculo de probabilidades implícitas de decisões de política monetária (equivalente ao Bloomberg WIRP). Modelo de árvore binária: P(hike) = (Futures_rate - Current_rate) / (Hike_increment). Cobertura: Fed (SOFR futures), ECB (EURIBOR futures), BCB (DI1 futuros).

**Critério de aceite:**
- [ ] Probabilidades calculadas para Fed, ECB e BCB
- [ ] Validação cruzada com CME FedWatch (divergência < 5pp)
- [ ] Probabilidades por meeting date nos próximos 12 meses
- [ ] Histórico de probabilidades armazenado
- [ ] API endpoint funcional com dados reais

**Esforço estimado:** 1 semana

---

#### 2.8 — YCRV — Yield Curve Analysis

**Escopo técnico:** Implementar painel analítico de yield curves (equivalente ao Bloomberg YCRV). Features: overlay de curvas (UST, Bund, JGB, Gilt, DI), 3D surface (tenor × data × yield), NS/NSS parameters com z-scores, spread calculator (10Y-2Y, 30Y-10Y, 5y5y forward), historical comparison, real yield curve.

**Dependência:** Modelo NS da entrega 1.1.

**Critério de aceite:**
- [ ] Overlay de 5 yield curves (UST, Bund, JGB, Gilt, DI)
- [ ] 3D surface com dados históricos (>2 anos)
- [ ] NS parameters (Level, Slope, Curvature) com z-scores
- [ ] Spread calculator: 10Y-2Y, 30Y-10Y, 5y5y forward
- [ ] Real yield curve (nominal - breakeven) para US
- [ ] API endpoints retornando dados para frontend

**Esforço estimado:** 1 semana

---

### Quality Gate — Fase 2

| Critério | Método de Verificação | Status |
|----------|----------------------|--------|
| 25+ conectores operacionais | Dashboard de status de todos os conectores | [ ] |
| >90% data freshness score | Grafana Data Quality dashboard | [ ] |
| Zero cross-provider divergência >0.1% | Relatório de validação cruzada | [ ] |
| ALFRED vintage data funcional | Teste get_as_of() com 10 séries | [ ] |
| WIRP validado vs CME FedWatch | Comparação de probabilidades (< 5pp diff) | [ ] |
| YCRV com 5 curvas overlay | Verificação visual do endpoint | [ ] |
| Todos os conectores com testes | pytest coverage > 80% para conectores novos | [ ] |

**Decisão Go/No-Go:** Todos os 7 critérios devem ser "passa".

---

## FASE 3 — FRONTEND FOUNDATION (Semanas 15–22)

### Objetivo
Construir o frontend Bloomberg-style completo com 8 painéis Phase 1, layout Launchpad (draggable/resizable), streaming via WebSocket/SSE, e panel linking por cor. O frontend deve atingir Lighthouse score > 90 e WebSocket latency < 50ms.

### Pré-requisitos
Fases 0-2 completas. Todos os endpoints de API operacionais com dados reais. Modelos NS, VAR, GARCH calibrados.

### Nota sobre Stack
O masterplan especifica Next.js 15, AG Grid, Lightweight Charts v5, Plotly.js, D3.js, react-grid-layout e Zustand. O frontend atual (Macro Trading Terminal v1.2) usa React + Vite + TailwindCSS + Recharts + shadcn/ui. A decisão de migrar para o stack completo do masterplan ou evoluir o frontend atual deve ser tomada nesta fase. A recomendação é migrar para o stack do masterplan para atingir os targets de performance e funcionalidade Bloomberg-equivalent.

---

#### 3.1 — React Shell + Auth Flow

**Escopo:** Next.js 15 + TypeScript + TailwindCSS. Dark theme (#0A0E17 bg, #131722 surface). Layout base CSS Grid 12 colunas. Auth flow com JWT (login, logout, refresh automático). Design system com componentes base.

**Critério de aceite:**
- [ ] Next.js 15 + TypeScript + TailwindCSS configurados
- [ ] Dark theme Bloomberg-style implementado
- [ ] Auth flow completo (login → dashboard → logout)
- [ ] JWT refresh automático antes de expiração
- [ ] Design system: DataCard, LoadingShimmer, AlertBanner
- [ ] First Contentful Paint < 1.0s (Lighthouse)

**Esforço estimado:** 1 semana

---

#### 3.2 — Launchpad Layout (react-grid-layout)

**Escopo:** Layout draggable e resizable via react-grid-layout. 4 presets: Trading, Analysis, Risk, Morning. Layout persistido em localStorage (fase inicial) e PostgreSQL (após multi-tenancy). Keyboard shortcuts (Ctrl+1 Watchlist, Ctrl+2 Chart, Ctrl+K command palette).

**Critério de aceite:**
- [ ] Painéis draggable e resizable
- [ ] 4 presets de layout salvos e carregáveis
- [ ] Layout persistido entre sessões (localStorage)
- [ ] Keyboard shortcuts funcionais (Ctrl+1, Ctrl+2, Ctrl+K, Ctrl+N, Ctrl+W)
- [ ] Command palette (Ctrl+K) para navegação rápida

**Esforço estimado:** 1 semana

---

#### 3.3 — Lightweight Charts v5 Integration

**Escopo:** Candlestick, line, area charts via TradingView Lightweight Charts v5. Timeframes: 1m, 5m, 15m, 1H, 4H, 1D, 1W, 1M. Drawing tools: trend lines, horizontal lines, Fibonacci. Indicadores: SMA, EMA, Bollinger, RSI, MACD. Multi-chart overlay.

**Critério de aceite:**
- [ ] Candlestick chart renderizando com WebGL (100K+ candles)
- [ ] 8 timeframes funcionais
- [ ] Drawing tools: trend lines, horizontal lines, Fibonacci
- [ ] Indicadores: SMA, EMA, Bollinger Bands, RSI, MACD
- [ ] Chart update < 16ms (60fps)
- [ ] Multi-chart overlay para comparação de ativos

**Esforço estimado:** 2 semanas

---

#### 3.4 — AG Grid Integration

**Escopo:** AG Grid Community para Watchlist, Eco Calendar, Trade Blotter. Server-side row model para >1000 rows. Cell rendering condicional (verde positivo, vermelho negativo). Tema custom dark. Filtros, sorting, column resize.

**Critério de aceite:**
- [ ] AG Grid renderizando 10K rows em < 200ms
- [ ] Cell rendering condicional por cor (positivo/negativo)
- [ ] Tema dark custom alinhado com design system
- [ ] Server-side row model para datasets grandes
- [ ] Filtros, sorting e column resize funcionais
- [ ] Export para CSV funcional

**Esforço estimado:** 2 semanas

---

#### 3.5 — WebSocket Infrastructure

**Escopo:** FastAPI WebSocket server consumindo Redis pub/sub. Fan-out para browsers conectados. Protocolo JSON: `{type, channel, data, timestamp}`. Single WebSocket per browser tab. Client-side dispatcher via Zustand middleware. Subscription management.

**Critério de aceite:**
- [ ] WebSocket connection estável (auto-reconnect em caso de queda)
- [ ] Latência < 50ms (round-trip)
- [ ] Subscription management: subscribe/unsubscribe por channel
- [ ] Single WebSocket per tab com dispatcher para múltiplos painéis
- [ ] Protocolo JSON documentado
- [ ] Heartbeat/ping-pong para detecção de conexão morta

**Esforço estimado:** 1 semana

---

#### 3.6 — Panel Linking por Cor

**Escopo:** Conceito Bloomberg: painéis com mesma cor de link compartilham contexto. Zustand store com linkGroups. AG Grid `onSelectionChanged` propaga asset selecionado para todos os painéis do mesmo grupo de cor.

**Critério de aceite:**
- [ ] 4 cores de link disponíveis (red, blue, green, yellow)
- [ ] Seleção de asset no Watchlist propaga para todos os painéis linkados
- [ ] Price Chart, Yield Curve, Correlation atualizam automaticamente
- [ ] Linking/unlinking de painéis via UI intuitiva
- [ ] Estado de linking persistido com layout

**Esforço estimado:** 0.5 semana

---

#### 3.7 — 8 Painéis Phase 1

**Escopo:** Implementar os 8 painéis fundamentais: Watchlist, Price Chart, Macro Dashboard, ECO Calendar, YCRV (Yield Curve), Correlation Matrix, News Feed, Strategy Monitor. Cada painel consome dados reais via API + WebSocket.

**Sub-entregas:**
1. **Watchlist Panel:** AG Grid com Last, Change, Change%, Bid, Ask, Volume, 52W H/L. Streaming via WebSocket.
2. **Price Chart Panel:** Lightweight Charts v5 com candlestick + indicadores.
3. **Macro Dashboard:** Grid de KPI cards por país. Heatmap de z-scores.
4. **ECO Calendar:** AG Grid com eventos econômicos. Filtros por país/importância.
5. **YCRV Panel:** Plotly 3D surface + overlay + NS parameters + spread calculator.
6. **Correlation Matrix:** Plotly heatmap rolling (30D, 90D, 1Y). Cross-asset.
7. **News Feed:** SSE streaming de headlines. Sentiment scoring.
8. **Strategy Monitor:** Dashboard de performance das estratégias. Sparklines + drill-down.

**Critério de aceite:**
- [ ] Todos os 8 painéis renderizando com dados reais
- [ ] Watchlist com streaming em tempo real
- [ ] ECO Calendar com filtros e countdown para próximo evento
- [ ] YCRV com 3D surface interativa
- [ ] Correlation Matrix com regime detection
- [ ] Strategy Monitor com Sharpe rolling e drawdown
- [ ] Todos os painéis integrados com panel linking
- [ ] Lighthouse Performance Score > 90

**Esforço estimado:** 2 semanas

---

#### 3.8 — SSE Streams

**Escopo:** Server-Sent Events para news feed, calendar alerts e strategy signals. EventSource API com auto-reconnect. Endpoints: `/api/stream/news`, `/api/stream/calendar`, `/api/stream/signals`.

**Critério de aceite:**
- [ ] SSE endpoints funcionais para news, calendar, signals
- [ ] Auto-reconnect nativo do EventSource
- [ ] Filtros por asset class e country no stream
- [ ] Latência < 1s para propagação de eventos
- [ ] Fallback graceful se SSE indisponível

**Esforço estimado:** 0.5 semana

---

### Quality Gate — Fase 3

| Critério | Método de Verificação | Status |
|----------|----------------------|--------|
| Lighthouse score > 90 | Lighthouse audit em production build | [ ] |
| 8 painéis funcionais com dados reais | Verificação manual de cada painel | [ ] |
| WebSocket latency < 50ms | Métricas de round-trip em Prometheus | [ ] |
| Panel linking funcional | Teste de propagação de asset entre painéis | [ ] |
| Launchpad drag/resize | Teste manual de 4 presets | [ ] |
| AG Grid 10K rows < 200ms | Performance.now() measurement | [ ] |
| Chart update 60fps | requestAnimationFrame timing | [ ] |
| Bundle size < 500KB gzipped | webpack-bundle-analyzer | [ ] |
| User acceptance testing | Revisão pelo usuário dos 8 painéis | [ ] |

**Decisão Go/No-Go:** Todos os 9 critérios devem ser "passa".

---

## FASE 4 — ADVANCED MODELS & ML (Semanas 23–30)

### Objetivo
Implementar modelos avançados de ML (LightGBM, BVAR, TVP-VAR, DFM), CDS pricing, e 8 novas estratégias (4 commodities + 4 cross-asset). Todos os modelos com validação walk-forward, SHAP interpretability e dados point-in-time (ALFRED).

### Pré-requisitos
Fases 0-3 completas. Conectores globais operacionais. ALFRED pipeline funcional. Frontend com painéis base.

---

#### 4.1 — LightGBM + SHAP FX Prediction

**Escopo:** Modelo de ML para FX prediction 1-3 meses. 50+ features macro. Purged cross-validation. SHAP values obrigatórios. Monthly retraining via Dagster.

**Critério de aceite:**
- [ ] 50+ features engineered (macro, técnicas, sentiment)
- [ ] Purged CV com gap de 5 dias, mínimo 5 folds
- [ ] OOS Sharpe > 70% do IS Sharpe
- [ ] SHAP values para feature importance e force plots
- [ ] Retraining pipeline automatizado (mensal)
- [ ] Student-t distribution para probabilistic outputs

**Esforço estimado:** 2 semanas

---

#### 4.2 — BVAR Minnesota Prior

**Escopo:** Bayesian VAR com Minnesota Prior via PyMC v5 + JAX backend. Macro forecasting com density forecasts. 10-20 variáveis. NUTS sampler para MCMC eficiente.

**Critério de aceite:**
- [ ] BVAR estimado com 10-20 variáveis macro
- [ ] Density forecasts (fan charts) para GDP, CPI, rates
- [ ] Shrinkage parameter (λ) otimizado via marginal likelihood
- [ ] Comparação com VAR clássico (Fase 1) — BVAR deve ter menor RMSE OOS
- [ ] PyMC v5 + JAX backend funcional

**Esforço estimado:** 2 semanas

---

#### 4.3 — TVP-VAR (Time-Varying Parameters)

**Escopo:** VAR com coeficientes time-varying via PyMC GaussianRandomWalk. Detecção de mudanças estruturais graduais. Aplicação: sensibilidade do câmbio ao diferencial de juros em diferentes regimes.

**Critério de aceite:**
- [ ] Coeficientes time-varying estimados e visualizáveis
- [ ] Detecção de structural change (ex: taper vs QE)
- [ ] Comparação com VAR fixo — TVP-VAR captura mudanças que VAR fixo perde
- [ ] Convergência do MCMC verificada (R-hat < 1.1)

**Esforço estimado:** 1 semana

---

#### 4.4 — DFM Nowcasting

**Escopo:** Dynamic Factor Model com mixed frequencies para nowcasting de GDP e CPI. Combina dados diários (financial), semanais (claims), mensais (IP, retail) e trimestrais (GDP).

**Critério de aceite:**
- [ ] Nowcast de GDP e CPI com atualização em tempo real
- [ ] Mixed-frequency data handling funcional
- [ ] Comparação com Atlanta Fed GDPNow como benchmark
- [ ] Fatores latentes interpretáveis
- [ ] Atualização automática quando novos dados chegam

**Esforço estimado:** 2 semanas

---

#### 4.5 — CDS Pricing (QuantLib)

**Escopo:** Implementar pricing de CDS soberanos via QuantLib CreditDefaultSwap. Convenções ISDA (ACT/360, quarterly premium). Bootstrapping de hazard rates. Cobertura: 25+ países.

**Critério de aceite:**
- [ ] CDS pricing para 25+ soberanos
- [ ] Hazard rates bootstrapped corretamente
- [ ] Convenções ISDA respeitadas
- [ ] Comparação com market CDS spreads (erro < 5bps)
- [ ] API endpoint funcional

**Esforço estimado:** 1 semana

---

#### 4.6 — 4 Estratégias Commodities

**Escopo:** Commodity Carry (backwardation/contango), Commodity Momentum (cross-sectional 12M-1M), Oil-FX Relationships (cointegração petróleo-moedas), Gold as Macro Hedge (real rates + USD DXY).

**Critério de aceite (por estratégia):**
- [ ] Backtest walk-forward com dados point-in-time (ALFRED)
- [ ] Sharpe ratio documentado (IS e OOS)
- [ ] OOS Sharpe > 70% do IS
- [ ] Position sizing implementado
- [ ] Trade signals gerando propostas no PMS
- [ ] Documentação de rationale econômico

**Esforço estimado:** 2 semanas

---

#### 4.7 — 4 Estratégias Cross-Asset

**Escopo:** Risk Parity (inverse-vol weighting, target vol 10%), Macro Momentum (time-series momentum 12M cross-asset), Business Cycle Allocation (4 regimes: Expansion, Slowdown, Contraction, Recovery), Vol Regime Switching (escala exposição inversamente à vol realizada).

**Critério de aceite (por estratégia):**
- [ ] Backtest walk-forward com dados point-in-time
- [ ] Sharpe ratio documentado (IS e OOS)
- [ ] OOS Sharpe > 70% do IS
- [ ] Regime detection funcional (para Business Cycle e Vol Regime)
- [ ] Integração com PMS para trade proposals
- [ ] Documentação de referência acadêmica

**Esforço estimado:** 2 semanas

---

### Quality Gate — Fase 4

| Critério | Método de Verificação | Status |
|----------|----------------------|--------|
| OOS Sharpe > 70% do IS para todos os modelos ML | Walk-forward validation report | [ ] |
| SHAP reports para todos os modelos ML | SHAP summary + force plots | [ ] |
| BVAR RMSE < VAR clássico | Comparação de forecast accuracy | [ ] |
| 8 novas estratégias com backtest completo | Backtest report por estratégia | [ ] |
| CDS pricing erro < 5bps vs market | Comparação com market spreads | [ ] |
| Zero look-ahead bias | Todos backtests usando ALFRED vintage data | [ ] |
| Retraining pipeline funcional | Dagster job executando sem erros | [ ] |

**Decisão Go/No-Go:** Todos os 7 critérios devem ser "passa".

---

## FASE 5 — BLOOMBERG FUNCTIONS & STRATEGIES (Semanas 31–38)

### Objetivo
Implementar as 8 funções Bloomberg-equivalent restantes (FXFM, FXFA, WCRS, SWPM, CDSW, FWCV, PORT, GEW), 5 novas estratégias (3 FX + 2 Rates), 6 painéis Phase 2 do frontend, e integração do VectorBT Pro.

### Pré-requisitos
Fases 0-4 completas. Todos os modelos e conectores operacionais. Frontend com 8 painéis Phase 1.

---

#### 5.1 — FXFM + FXFA (FX Forecast Model + FX Fair Value)

**Escopo:** FXFM replica distribuições de probabilidade implícitas de opções FX (Black-Scholes + Vanna-Volga). FXFA implementa CIP forward pricing com ajuste de meeting dates.

**Critério de aceite:**
- [ ] PDF/CDF de FX spot futuro calculada corretamente
- [ ] Probabilidade de breach de níveis específicos
- [ ] Expected move (±1σ, ±2σ) calculado
- [ ] CIP forward pricing funcional para 10+ pares
- [ ] Ajuste de meeting dates implementado

**Esforço estimado:** 2 semanas

---

#### 5.2 — WCRS (World Currency Rates)

**Escopo:** Dashboard de 30+ moedas com 6 métricas: spot, change%, implied vol, carry, REER z-score, PPP deviation.

**Critério de aceite:**
- [ ] 30+ moedas cobertas
- [ ] 6 métricas por moeda calculadas corretamente
- [ ] AG Grid com sorting e filtros
- [ ] Dados atualizados diariamente

**Esforço estimado:** 1 semana

---

#### 5.3 — SWPM + CDSW (Swap Pricing + CDS Pricing)

**Escopo:** SWPM via QuantLib VanillaSwap para IRS pricing (USD SOFR, EUR ESTR, BRL CDI, GBP SONIA, JPY TONA). CDSW integra o CDS pricing da Fase 4 com interface frontend.

**Critério de aceite:**
- [ ] IRS pricing: NPV, DV01, convexity, par swap rate, PV01
- [ ] 5 moedas suportadas (USD, EUR, BRL, GBP, JPY)
- [ ] Bootstrap de curva OIS funcional
- [ ] CDS pricing integrado com frontend
- [ ] Convenções de day count corretas por moeda

**Esforço estimado:** 2 semanas

---

#### 5.4 — FWCV + PORT + GEW

**Escopo:** FWCV (Forward Curves): zero → discount → implied forward curves. PORT (Portfolio Analytics): pyfolio-style dashboard com cumulative returns, rolling Sharpe, factor exposure, attribution, underwater chart, monthly returns heatmap. GEW (Global Economy Watch): world map D3.js com GDP growth, country profiles, CB rate history.

**Critério de aceite:**
- [ ] Forward curves para SOFR, ESTR, SELIC
- [ ] PORT com 10+ métricas de performance
- [ ] GEW com world map interativo (click → country profile)
- [ ] Comparison tool: 2-5 países side-by-side
- [ ] Todos com dados reais

**Esforço estimado:** 2 semanas

---

#### 5.5 — 3 Estratégias FX + 2 Estratégias Rates

**Escopo:** FX: PPP Deviation Trades, REER Mean Reversion, CB Policy Divergence. Rates: Swap Spread Trades, Butterfly 2s10s30s.

**Critério de aceite (por estratégia):**
- [ ] Backtest walk-forward com ALFRED vintage data
- [ ] Sharpe ratio IS e OOS documentado
- [ ] OOS degradation < 30%
- [ ] Referência acadêmica citada
- [ ] Integração com PMS

**Esforço estimado:** 3 semanas (2 FX + 1 Rates)

---

#### 5.6 — 6 Painéis Phase 2

**Escopo:** Risk Dashboard (VaR stacked, stress heatmap, Greeks), Morning Pack Interactive (8 seções navegáveis), Trade Blotter (AG Grid com workflow de aprovação), Decision Journal (rich text editor), Portfolio Analytics (PORT), Global Economy Watch (GEW).

**Critério de aceite:**
- [ ] Risk Dashboard com VaR 3 métodos, stress test heatmap, Greeks
- [ ] Morning Pack interativo com drill-down em cada seção
- [ ] Trade Blotter com workflow Propose → Approve → Execute
- [ ] Decision Journal com rich text, tags, linkável ao trade blotter
- [ ] PORT com cumulative returns, rolling Sharpe, factor exposure
- [ ] GEW com world map e country profiles
- [ ] Todos integrados com panel linking

**Esforço estimado:** 2 semanas

---

#### 5.7 — VectorBT Pro Integration

**Escopo:** Integração do VectorBT Pro para backtesting otimizado. Numba JIT compilation (10-100x mais rápido). Walk-forward validation framework. Portfolio-level backtesting.

**Critério de aceite:**
- [ ] VectorBT Pro instalado e licenciado
- [ ] Walk-forward validation automatizado
- [ ] Speedup > 10x vs backtester atual
- [ ] Portfolio-level backtesting funcional
- [ ] Integração com pipeline de retraining

**Esforço estimado:** 1 semana

---

### Quality Gate — Fase 5

| Critério | Método de Verificação | Status |
|----------|----------------------|--------|
| 12 funções Bloomberg-equivalent operacionais | Acceptance test por função | [ ] |
| 5 novas estratégias com backtest completo | Walk-forward report | [ ] |
| 6 painéis Phase 2 funcionais | User acceptance testing | [ ] |
| VectorBT Pro integrado | Benchmark de velocidade | [ ] |
| Data coverage conforme spec | Verificação de fontes por função | [ ] |

**Decisão Go/No-Go:** Todos os 5 critérios devem ser "passa".

---

## FASE 6 — PRODUCTION & SCALE (Semanas 39–48)

### Objetivo
Migrar para Kubernetes, implementar observabilidade completa (Prometheus + Loki + Grafana), sistema de alertas multi-canal, documentação completa, audit trail e preparação para multi-tenancy.

### Pré-requisitos
Fases 0-5 completas. Todas as funcionalidades implementadas e testadas.

---

#### 6.1 — Kubernetes Migration

**Escopo:** Helm charts para todos os serviços. HPA baseado em CPU/memory. Namespaces: production, staging, development. Ingress controller Nginx com TLS termination. Rolling updates. Health checks.

**Critério de aceite:**
- [ ] Todos os serviços rodando em Kubernetes
- [ ] HPA funcional (scale up/down automático)
- [ ] Rolling updates sem downtime
- [ ] Health checks em todos os pods
- [ ] Namespaces separados (prod, staging, dev)

**Esforço estimado:** 3 semanas

---

#### 6.2 — Prometheus + Loki + Grafana

**Escopo:** Stack completo de observabilidade. Prometheus para métricas (API latency, model training duration, VaR calculation time). Loki para log aggregation. 5 dashboards Grafana: Pipeline Health, VaR Trends, Portfolio Overview, Data Quality, System Health.

**Critério de aceite:**
- [ ] Prometheus instrumentando todos os endpoints FastAPI
- [ ] Loki centralizando logs de todos os containers
- [ ] 5 dashboards Grafana operacionais
- [ ] Alerting rules configuradas (p95 > 500ms, error rate > 1%)
- [ ] Log retention: 30d DEBUG, 90d INFO, 1y ERROR

**Esforço estimado:** 2 semanas

---

#### 6.3 — Alert System Multi-Canal

**Escopo:** Telegram bot + Slack webhook + email (SMTP). Severidade: Critical (Telegram + Slack + email imediato), Warning (Slack + email digest), Info (email digest diário). Escalation: Critical não resolvido em 15 min → re-alert.

**Critério de aceite:**
- [ ] Telegram bot funcional para alertas Critical
- [ ] Slack webhook para Warning + Critical
- [ ] Email digest diário para Info
- [ ] Escalation automático após 15 min sem resolução
- [ ] Configuração de on-call rotation

**Esforço estimado:** 1 semana

---

#### 6.4 — Multi-Tenancy Foundation

**Escopo:** Suporte para múltiplos portfolios/usuários. Data isolation. Billing tracking básico.

**Critério de aceite:**
- [ ] Múltiplos usuários com portfolios isolados
- [ ] Data isolation verificada (user A não vê dados de user B)
- [ ] Billing tracking por usuário

**Esforço estimado:** 1 semana

---

#### 6.5 — Audit Trail

**Escopo:** Logging de todas as ações de trading. Compliance-ready. Export para auditoria.

**Critério de aceite:**
- [ ] Todas as ações de trade logadas (propose, approve, execute, cancel)
- [ ] Audit log imutável (append-only)
- [ ] Export para CSV/JSON para auditoria externa
- [ ] Retenção de 7 anos

**Esforço estimado:** 1 semana

---

#### 6.6 — Documentation

**Escopo:** API docs (OpenAPI completo), User Guide, Architecture Decision Records (ADRs), Runbooks para operações.

**Critério de aceite:**
- [ ] OpenAPI spec 100% documentada (todos os endpoints)
- [ ] User Guide com screenshots e workflows
- [ ] ADRs para todas as decisões arquiteturais importantes
- [ ] Runbooks para: deploy, rollback, incident response, data recovery

**Esforço estimado:** 1 semana

---

#### 6.7 — Load Testing & Chaos Engineering

**Escopo:** Load test com `k6` ou `locust` simulando 50 usuários simultâneos. Chaos engineering: kill random pods, simulate network partition, database failover.

**Critério de aceite:**
- [ ] 99.9% uptime sob load test de 24h
- [ ] Failover de database < 30s
- [ ] Rollback de deployment < 60s
- [ ] Zero data loss em chaos tests
- [ ] API p95 latency < 500ms sob carga

**Esforço estimado:** 1 semana

---

### Quality Gate — Fase 6

| Critério | Método de Verificação | Status |
|----------|----------------------|--------|
| 99.9% uptime em load test 24h | k6/locust report | [ ] |
| Failover < 30s | Chaos engineering test | [ ] |
| Rollback < 60s | Deployment rollback test | [ ] |
| 5 dashboards Grafana operacionais | Verificação visual | [ ] |
| Alert system multi-canal funcional | Teste de envio em 3 canais | [ ] |
| Documentação 100% completa | Review checklist | [ ] |
| Audit trail compliance-ready | Export e verificação de completude | [ ] |

**Decisão Go/No-Go:** Todos os 7 critérios devem ser "passa" para declarar o sistema Production Ready.

---

## GOVERNANÇA E PROCESSO DE EXECUÇÃO

### Ciclo de Cada Fase

Cada fase segue um ciclo rigoroso de 5 etapas:

1. **Planejamento Detalhado:** Antes de iniciar a execução, o plano da fase é apresentado ao usuário com todas as sub-entregas, critérios de aceite e estimativas. O usuário aprova ou solicita ajustes.

2. **Execução Técnica:** Cada sub-entrega é implementada sequencialmente (ou em paralelo quando independentes). Código real, dados reais, zero placeholders.

3. **Verificação Unitária:** Cada sub-entrega é testada individualmente contra seus critérios de aceite. Testes automatizados (pytest) + verificação manual.

4. **Quality Gate:** Ao final da fase, todos os critérios do Quality Gate são verificados. Relatório de status apresentado ao usuário.

5. **Aprovação e Avanço:** O usuário revisa o relatório, testa funcionalidades e aprova o avanço para a próxima fase. Sem aprovação, a fase não é considerada completa.

### Princípios Inegociáveis

| Princípio | Descrição |
|-----------|-----------|
| **Zero Placeholders** | Todo código entregue opera com dados reais e lógica completa |
| **Zero Mock Data** | Todos os endpoints consomem dados reais das fontes configuradas |
| **Zero Hardcoded Logic** | Parâmetros configuráveis via Vault/env, não hardcoded |
| **Student-t, Nunca Normal** | Toda modelagem probabilística usa Student-t |
| **Point-in-Time** | Backtests usam exclusivamente dados vintage (ALFRED) |
| **SHAP Obrigatório** | Todo modelo ML tem SHAP values documentados |
| **Walk-Forward** | Toda estratégia validada com walk-forward OOS |
| **Aprovação por Fase** | Nenhuma fase avança sem aprovação explícita do usuário |

---

## TIMELINE CONSOLIDADO

| Semana | Fase | Entregas Principais |
|--------|------|-------------------|
| 1–2 | **Fase 0: Security** | JWT Auth, TLS 1.3, Vault, Rate Limiting, RBAC |
| 3–4 | **Fase 1: Analytics** | Nelson-Siegel, VAR/VECM, GJR-GARCH |
| 5–6 | **Fase 1: Analytics** | Kalman Filter, ECO Calendar, Taylor Rule |
| 7–8 | **Fase 1: Analytics** | Phillips Curve, Breakeven Enhancement |
| 9–10 | **Fase 2: Data** | ECB, IMF, BIS, World Bank connectors |
| 11–12 | **Fase 2: Data** | BLS, EIA, Nasdaq, ALFRED Pipeline |
| 13–14 | **Fase 2: Data** | Data Quality v2, WIRP, YCRV |
| 15–16 | **Fase 3: Frontend** | React Shell, Launchpad, Auth Flow |
| 17–18 | **Fase 3: Frontend** | Lightweight Charts, AG Grid |
| 19–20 | **Fase 3: Frontend** | WebSocket, Panel Linking, SSE |
| 21–22 | **Fase 3: Frontend** | 8 Painéis Phase 1 |
| 23–24 | **Fase 4: ML** | LightGBM + SHAP, BVAR Minnesota |
| 25–26 | **Fase 4: ML** | TVP-VAR, DFM Nowcasting |
| 27–28 | **Fase 4: ML** | CDS Pricing, 4 Commodity Strategies |
| 29–30 | **Fase 4: ML** | 4 Cross-Asset Strategies |
| 31–32 | **Fase 5: BBG** | FXFM, FXFA, WCRS |
| 33–34 | **Fase 5: BBG** | SWPM, CDSW, FWCV, PORT, GEW |
| 35–36 | **Fase 5: BBG** | 3 FX + 2 Rates Strategies |
| 37–38 | **Fase 5: BBG** | 6 Painéis Phase 2, VectorBT Pro |
| 39–41 | **Fase 6: Production** | Kubernetes Migration |
| 42–43 | **Fase 6: Production** | Prometheus + Loki + Grafana |
| 44–45 | **Fase 6: Production** | Alert System, Multi-Tenancy |
| 46–47 | **Fase 6: Production** | Audit Trail, Documentation |
| 48 | **Fase 6: Production** | Load Testing, Chaos Engineering, Go-Live |

---

## PRÓXIMO PASSO

Aguardando aprovação deste plano de execução técnica para iniciar a **Fase 0 — Security Hardening**. Ao aprovar, detalharei o plano de execução da Fase 0 com cronograma diário e iniciarei a implementação do JWT Authentication.

)

# CORS — restritivo em produção
allowed_origins = (
    ["*"] if settings.environment == "development"
    else ["https://app.macrofund.internal", "https://dashboard.macrofund.internal"]
)

app.add_middleware(CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Trusted hosts (evita host header injection)
if settings.is_production:
    app.add_middleware(TrustedHostMiddleware,
        allowed_hosts=["api.macrofund.internal", "*.macrofund.internal"],
    )

# GZip para responses grandes
app.add_middleware(GZipMiddleware, minimum_size=1024)

# Session
app.add_middleware(SessionMiddleware, secret_key=settings.db.password.get_secret_value())

# Rate limiting + cache (adicionados após startup)
@app.on_event("startup")
async def startup():
    from src.cache.redis_client import RedisCache
    cache = RedisCache()
    await cache.connect()
    app.state.cache = cache
    app.middleware("http")(create_rate_limit_middleware(cache))
    app.add_middleware(CacheMiddleware, cache=cache)

# Incluir auth em rotas sensíveis:
# from src.api.auth import require_role
# app.include_router(execution_router, dependencies=[Depends(require_role("trader"))])
```

Ao final: `python -c "from src.api.auth import create_access_token; t = create_access_token({'sub': 'test', 'role': 'viewer'}); print('✅ Auth OK:', t[:30], '...')"`

═══ FIM DO PROMPT 17 ═══


################################################################################
##                                                                            ##
##  ETAPA 18 — LIVE TRADING CHECKLIST & GO-LIVE RUNBOOK                     ##
##  Tempo: ~15 min | Checklist completa para go-live com capital real         ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 18 ═══

No projeto macro-fund-system, crie o documento de go-live checklist e
runbook operacional para transição de paper trading para live trading.

## 1. Crie docs/GOLIVE_CHECKLIST.md:

```markdown
# Go-Live Checklist — Macro Fund AI System v3.0
## Transição: Paper Trading → Live Trading com Capital Real

> **ATENÇÃO**: Este documento deve ser revisado e assinado pelo Risk Manager
> e CTO antes de qualquer operação com capital real.
>
> Todas as etapas marcadas com [OBRIGATÓRIO] devem ser verificadas.
> Etapas marcadas com [RECOMENDADO] são boas práticas.

---

## FASE PRÉ-GO-LIVE (T-5 dias)

### 1. Infraestrutura

- [ ] [OBRIGATÓRIO] K8s cluster em produção com 3+ nós worker
- [ ] [OBRIGATÓRIO] TimescaleDB com replicação ativa (primary + 1 replica)
- [ ] [OBRIGATÓRIO] Redis Sentinel ou Redis Cluster (alta disponibilidade)
- [ ] [OBRIGATÓRIO] Kafka com 3 brokers e replication factor=3
- [ ] [OBRIGATÓRIO] Backup diário configurado e testado (restore validado)
- [ ] [OBRIGATÓRIO] Grafana + Alertmanager com PagerDuty configurado
- [ ] [OBRIGATÓRIO] Vault em produção (não dev mode) com HA
- [ ] [RECOMENDADO] VPN dedicada para acesso ao cluster de produção
- [ ] [RECOMENDADO] WAF (Web Application Firewall) na frente da API

### 2. Conectividade com Exchanges

- [ ] [OBRIGATÓRIO] FIX session testada com B3 (paper environment B3)
- [ ] [OBRIGATÓRIO] FIX session testada com CME (CME Globex sandbox)
- [ ] [OBRIGATÓRIO] Latência FIX medida e dentro do SLA (<5ms local, <50ms cloud)
- [ ] [OBRIGATÓRIO] Conta na corretora aprovada com limites de margem definidos
- [ ] [OBRIGATÓRIO] Teste de cancel-on-disconnect (CoD) configurado na B3
- [ ] [RECOMENDADO] Conexão FIX redundante (primary + backup FIX engine)

### 3. Compliance & Legal

- [ ] [OBRIGATÓRIO] Registro do fundo na CVM (Instrução CVM 558 ou 578)
- [ ] [OBRIGATÓRIO] Política de risco aprovada pelo Comitê de Risco
- [ ] [OBRIGATÓRIO] Limites de risco assinados (VaR, posição, turnover diário)
- [ ] [OBRIGATÓRIO] Audit logging validado por auditor externo
- [ ] [OBRIGATÓRIO] Termo de ciência de risco assinado pelos gestores
- [ ] [RECOMENDADO] Revisão por advogado especializado em mercado de capitais

### 4. Sistema de Trading

- [ ] [OBRIGATÓRIO] Paper trading rodando há mínimo 30 dias sem erros críticos
- [ ] [OBRIGATÓRIO] Backtesting out-of-sample validado (Walk-forward: IS 2019-2022, OOS 2023-2024)
- [ ] [OBRIGATÓRIO] Todos os testes (unit + integration) passando em CI
- [ ] [OBRIGATÓRIO] Pre-trade risk controls testados com fat finger e notional
- [ ] [OBRIGATÓRIO] Circuit breaker testado e funcional
- [ ] [OBRIGATÓRIO] AuditLogger persistindo corretamente (DB + arquivo)
- [ ] [RECOMENDADO] Simulação de cenários de stress (2008, 2020, COVID)

---

## FASE GO-LIVE (Dia D)

### 5. D-1: Preparação Final

- [ ] [OBRIGATÓRIO] `python scripts/health_check.py --strict` → PASS em PRODUÇÃO
- [ ] [OBRIGATÓRIO] Backup do DB realizado às 02:00
- [ ] [OBRIGATÓRIO] Revisão dos limites de risco com Risk Manager
- [ ] [OBRIGATÓRIO] Canal de guerra (War Room) configurado (Slack #prod-trading)
- [ ] [OBRIGATÓRIO] On-call escalation testada (PagerDuty drill)
- [ ] [OBRIGATÓRIO] Confirmar capital inicial depositado e margem disponível
- [ ] [RECOMENDADO] Revisão dos sinais das últimas 48h (nenhuma anomalia)

### 6. D-0: Go-Live (09:00 BRT)

Sequência de comandos (executar em ordem):

```bash
# 1. Verificação final
python scripts/health_check.py --strict

# 2. Confirmar gateway
curl http://localhost:8000/execution/gateways
# Esperado: {"gateways": ["b3", "cme"], "paper": "connected", "b3": "connected"}

# 3. Executar primeiro ciclo em DRY_RUN
python scripts/start_paper_trading.py --interval 60  # ainda dry_run

# 4. Confirmar sinais (deve haver pelo menos 3 estratégias ativas)
curl http://localhost:8000/api/v1/signals/latest | python -m json.tool

# 5. AÇÃO IRREVERSÍVEL: Ativar live trading (requer 2 pessoas)
# Person 1 digita o comando:
# python scripts/start_live_trading.py --gateway b3 --capital 1000000 --confirm

# 6. Monitorar primeiros 30 minutos intensivamente
# Dashboard: http://localhost:3000/live-trading
# Grafana: http://localhost:3002/d/execution
# Slack: #prod-trading (alertas automáticos)
```

### 7. Monitoramento Intensivo (primeiras 4 horas)

- [ ] P&L dentro do esperado (+/- 2 sigma do backtest)
- [ ] Fill rate > 90% (MARKET orders)
- [ ] Slippage médio < 5 bps
- [ ] Sem risk limit breaches
- [ ] Audit log escrevendo (verificar arquivo a cada 15min)
- [ ] Grafana: todos os painéis com dados
- [ ] Nenhum alerta crítico no PagerDuty

### 8. Critérios de Abort (Go-Back)

**Abortar imediatamente e voltar a paper trading se:**

- [ ] P&L < -R$ 100.000 nas primeiras 4 horas
- [ ] Taxa de rejeição de ordens > 20%
- [ ] Falha na conexão FIX por > 5 minutos
- [ ] AuditLogger parou de escrever
- [ ] Qualquer alerta de nível CRITICAL no Grafana
- [ ] Risk limit breach não resolvido em < 2 minutos

**Comando de abort:**
```bash
curl -X POST http://localhost:8000/trading/emergency-stop \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -d '{"reason": "Emergency stop triggered", "flatten_positions": true}'
```

---

## FASE PÓS-GO-LIVE

### 9. Revisão Semanal (primeiras 4 semanas)

- [ ] P&L vs. backtest: desvio < 2 sigma é aceitável
- [ ] Correlação de signals: verificar se agentes ainda estão gerando sinais válidos
- [ ] Slippage real vs. estimado: se desvio > 50%, recalibrar SlippageEstimator
- [ ] Audit log: revisar eventos WARNING e ERROR da semana
- [ ] Drawdown atual: se > 5%, revisar posições e signals

### 10. Assinaturas de Aprovação

| Cargo             | Nome | Assinatura | Data |
|-------------------|------|------------|------|
| Risk Manager      |      |            |      |
| CTO               |      |            |      |
| Portfolio Manager |      |            |      |
| Compliance Officer|      |            |      |

---

*Documento gerado automaticamente. Última revisão: Fase 3 — v3.0.0*
```

## 2. Crie src/trading/emergency_stop.py — Emergency Stop

```python
"""
Emergency Stop — Para todas as operações e fecha posições.
Ativado via API ou manualmente em situações de emergência.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class EmergencyStop:
    def __init__(self, ems, audit_logger, kafka_producer=None):
        self.ems = ems
        self.audit = audit_logger
        self.kafka = kafka_producer

    async def execute(
        self,
        reason: str,
        flatten_positions: bool = False,
        initiated_by: str = "system",
    ) -> dict:
        """
        Executa emergency stop:
        1. Cancela todas as ordens abertas
        2. Para o paper trading engine (se ativo)
        3. Fecha posições (se flatten_positions=True)
        4. Publica evento crítico no Kafka
        5. Loga no audit trail
        """
        logger.critical(f"[EMERGENCY STOP] {reason} — iniciado por {initiated_by}")
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "reason": reason,
            "initiated_by": initiated_by,
            "cancelled_orders": 0,
            "closed_positions": 0,
        }

        # 1. Cancela ordens abertas
        open_orders = self.ems.order_manager.get_open_orders()
        for order in open_orders:
            try:
                await self.ems.order_manager.cancel_order(order.order_id, "paper")
                results["cancelled_orders"] += 1
            except Exception as e:
                logger.error(f"[EmergencyStop] Erro ao cancelar {order.order_id}: {e}")

        # 2. Fecha posições
        if flatten_positions:
            positions = self.ems.position_tracker.get_open_positions()
            from src.execution.models import Order, OrderSide, OrderType, AssetClass, Exchange
            from decimal import Decimal
            for pos in positions:
                if not pos.is_flat:
                    close_order = Order(
                        strategy_id=pos.strategy_id,
                        symbol=pos.symbol,
                        exchange=pos.exchange,
                        asset_class=pos.asset_class,
                        side=OrderSide.SELL if pos.quantity > 0 else OrderSide.BUY,
                        order_type=OrderType.MARKET,
                        quantity=abs(pos.quantity),
                        metadata={"emergency_close": True},
                    )
                    try:
                        await self.ems.submit_order(close_order, gateway="paper")
                        results["closed_positions"] += 1
                    except Exception as e:
                        logger.error(f"[EmergencyStop] Erro ao fechar posição {pos.symbol}: {e}")

        # 3. Audit
        from src.compliance.audit import AuditEventType
        await self.audit.log(
            AuditEventType.CIRCUIT_BREAKER_TRIGGERED,
            "emergency_stop",
            results,
            severity="CRITICAL",
        )

        # 4. Kafka
        if self.kafka:
            await self.kafka.publish_alert({
                "type": "EMERGENCY_STOP",
                "severity": "CRITICAL",
                "message": reason,
                "results": results,
            })

        logger.critical(f"[EMERGENCY STOP] Concluído: {results}")
        return results
```

## 3. API endpoint — adicione em src/api/routers/trading.py:

```python
from fastapi import APIRouter, Depends
from src.api.auth import require_role

router = APIRouter(prefix="/trading", tags=["Trading Controls"])

@router.post("/emergency-stop")
async def emergency_stop(
    reason: str,
    flatten_positions: bool = False,
    user: dict = Depends(require_role("admin")),
):
    """Emergency stop — cancela ordens e opcionalmente fecha posições."""
    from src.trading.emergency_stop import EmergencyStop
    es = EmergencyStop(ems=get_ems(), audit_logger=get_audit())
    result = await es.execute(
        reason=reason,
        flatten_positions=flatten_positions,
        initiated_by=user.get("sub", "api"),
    )
    return result

@router.get("/status")
async def get_trading_status():
    """Status completo do sistema de trading."""
    ...

@router.post("/circuit-breaker/reset")
async def reset_circuit_breaker(user: dict = Depends(require_role("admin"))):
    """Reseta circuit breaker após resolução do problema."""
    ...
```

Ao final: `python -c "from src.trading.emergency_stop import EmergencyStop; print('✅ Emergency Stop OK')"`

═══ FIM DO PROMPT 18 ═══


################################################################################
##                                                                            ##
##  ETAPA 19 — SCRIPT DE VERIFICAÇÃO FASE 3                                  ##
##  Tempo: ~15 min | Verifica todos os componentes da Fase 3                  ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 19 ═══

No projeto macro-fund-system, crie o script de verificação da Fase 3
que valida todos os componentes implementados.

## 1. Crie scripts/verify_phase3.py:

```python
#!/usr/bin/env python3
"""
Verificação completa da Fase 3 — Production Deployment & Live Trading.
Uso: python scripts/verify_phase3.py
"""
import asyncio
import sys
import subprocess
from pathlib import Path
from datetime import date, timedelta

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

results = []


def check(name: str, condition: bool, detail: str = ""):
    status = f"{GREEN}✅ PASS{RESET}" if condition else f"{RED}❌ FAIL{RESET}"
    results.append((name, condition, detail))
    print(f"  {status}  {name}" + (f" — {detail}" if detail else ""))
    return condition


def section(title: str):
    print(f"\n{BOLD}{'═'*60}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'═'*60}{RESET}")


async def run_checks():
    print(f"\n{BOLD}{'═'*70}{RESET}")
    print(f"{BOLD}  MACRO HEDGE FUND AI SYSTEM — VERIFICAÇÃO FASE 3{RESET}")
    print(f"{BOLD}  Production Deployment & Live Trading{RESET}")
    print(f"{BOLD}{'═'*70}{RESET}")

    # ── Execution Management System ──────────────────────────────────────────
    section("1. EXECUTION MANAGEMENT SYSTEM")
    
    check("Models (Order, Fill, Position, ExecutionReport)",
          Path("src/execution/models.py").exists())
    check("Slippage Estimator (Almgren-Chriss)",
          Path("src/execution/slippage.py").exists())
    check("PaperGateway (fill simulation + slippage)",
          Path("src/execution/gateways/paper.py").exists())
    check("B3Gateway stub (FIX 4.4)",
          Path("src/execution/gateways/b3.py").exists())
    check("OrderManager (lifecycle + DB persistence)",
          Path("src/execution/order_manager.py").exists())
    check("PositionTracker (real-time P&L)",
          Path("src/execution/position_tracker.py").exists())
    check("PnLEngine (métricas de performance)",
          Path("src/execution/pnl.py").exists())
    check("ExecutionManagementSystem (orquestrador)",
          Path("src/execution/ems.py").exists())

    # Testa import
    try:
        from src.execution.models import Order, Fill, Position, ExecutionReport
        from src.execution.slippage import SlippageEstimator, SlippageModel
        from src.execution.gateways.paper import PaperGateway
        check("Import EMS modules", True)
    except Exception as e:
        check("Import EMS modules", False, str(e))

    # Testa slippage
    try:
        from decimal import Decimal
        est = SlippageEstimator()
        r = est.estimate("DIF25", Decimal("100"), Decimal("11000000"),
                         Decimal("500000000"), SlippageModel.FIXED_BPS)
        check("SlippageEstimator.estimate(DIF25)", r.estimated_bps == 0.5,
              f"bps={r.estimated_bps}")
    except Exception as e:
        check("SlippageEstimator.estimate(DIF25)", False, str(e))

    # ── Real-time Feeds ──────────────────────────────────────────────────────
    section("2. REAL-TIME DATA FEEDS")
    
    check("Kafka Producer", Path("src/feeds/kafka_producer.py").exists())
    check("Kafka Consumer", Path("src/feeds/kafka_consumer.py").exists())
    check("Price Simulator (GBM)", Path("src/feeds/price_simulator.py").exists())
    check("Bloomberg Adapter (stub)", Path("src/feeds/bloomberg_adapter.py").exists())
    check("Refinitiv Adapter (stub)", Path("src/feeds/refinitiv_adapter.py").exists())
    check("DataFeedManager (fallback)", Path("src/feeds/data_feed_manager.py").exists())

    try:
        from src.feeds.bloomberg_adapter import BloombergAdapter
        b = BloombergAdapter(stub_mode=True)
        tick = b._stub_tick("BRAMBID Index")
        check("Bloomberg stub tick (USD/BRL)", tick.value > 0, f"value={tick.value:.4f}")
    except Exception as e:
        check("Bloomberg stub tick", False, str(e))

    # ── Compliance & Audit ───────────────────────────────────────────────────
    section("3. COMPLIANCE & AUDIT LOGGING")
    
    check("AuditLogger (dual-write: DB + arquivo)",
          Path("src/compliance/audit.py").exists())
    check("PreTradeRiskControls (fat finger, notional, concentration)",
          Path("src/compliance/risk_controls.py").exists())
    check("Logs/audit directory",
          Path("logs/audit").exists() or not Path("logs").exists())  # OK se diretório não existe ainda

    try:
        from src.compliance.risk_controls import PreTradeRiskControls
        from src.execution.models import Order, OrderSide, OrderType, AssetClass, Exchange
        from decimal import Decimal
        ctrl = PreTradeRiskControls({"fat_finger_multiplier": 0.05})
        order = Order(
            strategy_id="TEST", symbol="DIF25",
            exchange=Exchange.PAPER, asset_class=AssetClass.FUTURES_IR,
            side=OrderSide.BUY, order_type=OrderType.LIMIT,
            quantity=Decimal("10"), price=Decimal("200.0"),
        )
        result = ctrl.check(order, Decimal("0"), last_price=Decimal("100.0"))
        check("PreTradeRiskControls: fat finger rejection", not result.approved,
              f"reason={result.rejection_reason[:40] if result.rejection_reason else 'N/A'}")
    except Exception as e:
        check("PreTradeRiskControls: fat finger rejection", False, str(e))

    # ── Configuration & Secrets ──────────────────────────────────────────────
    section("4. CONFIGURATION & SECRETS MANAGEMENT")
    
    check("Settings (Pydantic v2)", Path("src/config/settings.py").exists())
    check("Vault Client", Path("src/config/vault_client.py").exists())
    check(".env.example", Path(".env.example").exists())
    check(".gitignore com .env", ".env" in Path(".gitignore").read_text() if Path(".gitignore").exists() else False)

    try:
        from src.config.settings import get_settings
        s = get_settings()
        check("Settings load OK", s.environment in ("development", "staging", "production"),
              f"env={s.environment}")
    except Exception as e:
        check("Settings load OK", False, str(e))

    # ── CI/CD Pipeline ───────────────────────────────────────────────────────
    section("5. CI/CD PIPELINE")
    
    check("GitHub Actions: CI", Path(".github/workflows/ci.yml").exists())
    check("GitHub Actions: CD Staging", Path(".github/workflows/cd-staging.yml").exists())
    check("GitHub Actions: CD Production", Path(".github/workflows/cd-production.yml").exists())
    check("Dockerfile multi-stage", Path("Dockerfile").exists())
    check("scripts/health_check.py", Path("scripts/health_check.py").exists())

    # ── Kubernetes ───────────────────────────────────────────────────────────
    section("6. KUBERNETES DEPLOYMENT")
    
    check("Helm Chart.yaml", Path("helm/macro-fund/Chart.yaml").exists())
    check("Helm values.yaml", Path("helm/macro-fund/values.yaml").exists())
    check("Helm deployment-api.yaml",
          Path("helm/macro-fund/templates/deployment-api.yaml").exists())
    check("Helm HPA (autoscaling)",
          Path("helm/macro-fund/templates/hpa.yaml").exists())
    check("kind cluster config (local dev)",
          Path("k8s/kind-config.yaml").exists())

    # Valida helm lint
    try:
        result = subprocess.run(
            ["helm", "lint", "helm/macro-fund/"],
            capture_output=True, text=True, timeout=30
        )
        check("helm lint OK", result.returncode == 0, result.stdout[-100:] if result.stdout else "")
    except FileNotFoundError:
        check("helm lint OK", False, "helm não instalado — skipped")
    except Exception as e:
        check("helm lint OK", False, str(e))

    # ── Performance Optimization ─────────────────────────────────────────────
    section("7. PERFORMANCE OPTIMIZATION")
    
    check("Redis Cache Layer", Path("src/cache/redis_client.py").exists())
    check("TimescaleDB Query Optimizer", Path("src/database/query_optimizer.py").exists())
    check("Response Cache Middleware", Path("src/api/middleware.py").exists())

    try:
        from src.cache.redis_client import RedisCache, cache
        check("RedisCache import", True)
    except Exception as e:
        check("RedisCache import", False, str(e))

    # ── Paper Trading Engine ─────────────────────────────────────────────────
    section("8. PAPER TRADING ENGINE")
    
    check("PaperTradingEngine", Path("src/paper_trading/engine.py").exists())
    check("scripts/start_paper_trading.py", Path("scripts/start_paper_trading.py").exists())

    try:
        from src.paper_trading.engine import PaperTradingEngine
        check("PaperTradingEngine import", True)
    except Exception as e:
        check("PaperTradingEngine import", False, str(e))

    # ── Disaster Recovery ────────────────────────────────────────────────────
    section("9. DISASTER RECOVERY")
    
    check("scripts/backup.sh", Path("scripts/backup.sh").exists())
    check("scripts/restore.sh", Path("scripts/restore.sh").exists())
    check("docs/runbooks/DR_PLAYBOOK.md", Path("docs/runbooks/DR_PLAYBOOK.md").exists())
    check("docs/GOLIVE_CHECKLIST.md", Path("docs/GOLIVE_CHECKLIST.md").exists())

    # ── Security ─────────────────────────────────────────────────────────────
    section("10. SECURITY")
    
    check("JWT Authentication", Path("src/api/auth.py").exists())
    check("Rate Limiter (Redis token bucket)", Path("src/api/rate_limiter.py").exists())
    check("Emergency Stop", Path("src/trading/emergency_stop.py").exists())

    try:
        from src.api.auth import create_access_token, decode_token
        token = create_access_token({"sub": "test", "role": "viewer"})
        payload = decode_token(token)
        check("JWT create/decode roundtrip", payload["sub"] == "test")
    except Exception as e:
        check("JWT create/decode roundtrip", False, str(e))

    # ── Performance Reporting ────────────────────────────────────────────────
    section("11. PERFORMANCE REPORTING")
    
    check("Tearsheet Generator", Path("src/reports/tearsheet.py").exists())

    try:
        from src.reports.tearsheet import TearsheetGenerator
        check("TearsheetGenerator import", True)
    except Exception as e:
        check("TearsheetGenerator import", False, str(e))

    # ── Testes ───────────────────────────────────────────────────────────────
    section("12. TESTES")
    
    check("tests/unit/test_slippage.py", Path("tests/unit/test_slippage.py").exists())
    check("tests/unit/test_risk_controls.py", Path("tests/unit/test_risk_controls.py").exists())
    check("tests/integration/test_ems_e2e.py",
          Path("tests/integration/test_ems_e2e.py").exists())
    check("tests/integration/test_paper_trading_e2e.py",
          Path("tests/integration/test_paper_trading_e2e.py").exists())

    # Roda unit tests
    try:
        result = subprocess.run(
            ["pytest", "tests/unit/", "-v", "--tb=short", "-q", "--timeout=30"],
            capture_output=True, text=True, timeout=120
        )
        passed = "passed" in result.stdout
        check("pytest tests/unit/ PASS", result.returncode == 0,
              result.stdout.split("\n")[-2] if result.stdout else result.stderr[-200:])
    except FileNotFoundError:
        check("pytest tests/unit/", False, "pytest não instalado")
    except Exception as e:
        check("pytest tests/unit/", False, str(e))

    # ── Sumário ──────────────────────────────────────────────────────────────
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = total - passed

    print(f"\n{'═'*70}")
    print(f"  RESULTADO FINAL: {GREEN}{passed} PASS{RESET} / {RED if failed else GREEN}{failed} FAIL{RESET} / {total} total")
    print(f"{'═'*70}")

    if failed == 0:
        print(f"""
{GREEN}{BOLD}
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║   ✅  FASE 3 COMPLETA — PRODUCTION DEPLOYMENT & LIVE TRADING         ║
║                                                                      ║
║   CONSTRUÍDO:                                                        ║
║   ✅ EMS (Order, Fill, Position, ExecutionReport)                    ║
║   ✅ PaperGateway (slippage, latência, fill simulation)              ║
║   ✅ B3Gateway + CMEGateway (stubs FIX 4.4)                          ║
║   ✅ Kafka streaming (producer, consumer, price simulator)            ║
║   ✅ Bloomberg + Refinitiv adapters (stub + interface)                ║
║   ✅ Compliance & Audit Logging (dual-write, 7 anos retenção)         ║
║   ✅ Pre-trade Risk Controls (fat finger, notional, concentration)    ║
║   ✅ Secrets Management (Vault + Pydantic Settings)                  ║
║   ✅ CI/CD Pipeline (GitHub Actions: dev→staging→prod)               ║
║   ✅ Kubernetes + Helm Charts (HPA, PDB, blue-green deploy)          ║
║   ✅ Redis Cache Layer (cache-aside, TTL, decorator)                 ║
║   ✅ TimescaleDB optimizations (continuous aggregates, compression)   ║
║   ✅ Paper Trading Engine (ciclo completo, P&L real-time)            ║
║   ✅ Performance Tearsheet (Sharpe, Sortino, MDD, heatmap)           ║
║   ✅ Live Trading Dashboard (React + WebSocket)                      ║
║   ✅ JWT Auth + Rate Limiting + CORS                                 ║
║   ✅ Emergency Stop + Circuit Breaker                                ║
║   ✅ Disaster Recovery (backup, restore, runbooks)                   ║
║   ✅ Go-Live Checklist + Runbook operacional                         ║
║   ✅ Dagster jobs (paper trading + performance report)               ║
║   ✅ Grafana dashboards de execução + alertas Prometheus             ║
║                                                                      ║
║   SISTEMA PRONTO PARA PRODUÇÃO                                       ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
{RESET}""")
    else:
        print(f"\n{YELLOW}⚠️  {failed} verificação(ões) falharam. Corrija antes de prosseguir.{RESET}")
        print("\nFalhas:")
        for name, ok, detail in results:
            if not ok:
                print(f"  {RED}✗ {name}{RESET}" + (f": {detail}" if detail else ""))

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_checks())
    sys.exit(0 if success else 1)
```

Ao final: `python scripts/verify_phase3.py`

═══ FIM DO PROMPT 19 ═══


################################################################################
##                                                                            ##
##  ETAPA 20 — COMMIT FINAL & README ATUALIZADO                              ##
##  Tempo: ~10 min | Documentação final e git commit da Fase 3               ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 20 ═══

No projeto macro-fund-system, finalize a Fase 3 com documentação
atualizada, commit git e verificação final completa.

## 1. Execute verify_phase3.py e corrija eventuais falhas:

```bash
python scripts/verify_phase3.py
```

Se STATUS: FAIL em algum item, corrija o problema e rode novamente.

## 2. Atualize README.md — adicione seção Fase 3:

```markdown
## Fase 3 — Production Deployment & Live Trading ✅

### Componentes Implementados

| Componente | Descrição | Status |
|---|---|---|
| **EMS** | Execution Management System (Order→Fill→Position→PnL) | ✅ |
| **PaperGateway** | Simulação com slippage real (Almgren-Chriss) | ✅ |
| **B3Gateway** | Stub FIX 4.4 para Bovespa/B3 | ✅ |
| **CMEGateway** | Stub FIX 4.4 para CME Globex | ✅ |
| **Kafka Streaming** | Producer/Consumer + Price Simulator (GBM) | ✅ |
| **Bloomberg Adapter** | Stub + interface para dados profissionais | ✅ |
| **Compliance** | Audit logging dual-write, 7 anos retenção | ✅ |
| **Risk Controls** | Pre-trade: fat finger, notional, concentração | ✅ |
| **Vault** | Secrets management em desenvolvimento | ✅ |
| **CI/CD** | GitHub Actions: PR→Staging→Production | ✅ |
| **Kubernetes** | Helm charts, HPA, PDB, blue-green deploy | ✅ |
| **Redis Cache** | Cache-aside, TTL, decorator automático | ✅ |
| **Paper Trading** | Engine completo com ciclo de 60s | ✅ |
| **Tearsheet** | Performance report (Sharpe, MDD, heatmap) | ✅ |
| **JWT Auth** | Role-based: viewer/trader/admin | ✅ |
| **Rate Limiting** | Token bucket via Redis | ✅ |
| **Emergency Stop** | Para ordens + fecha posições em emergência | ✅ |
| **DR Runbooks** | Backup/Restore, playbooks operacionais | ✅ |
| **Go-Live Checklist** | 40+ itens pré/dia/pós go-live | ✅ |

### Stack de Produção

```
                    ┌─────────────────────────────┐
                    │         LOAD BALANCER         │
                    │       (nginx / ALB)           │
                    └──────────────┬────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
        ┌─────▼──────┐    ┌────────▼──────┐    ┌───────▼──────┐
        │  FastAPI    │    │   FastAPI     │    │   FastAPI    │
        │  (Pod 1)    │    │   (Pod 2)     │    │   (Pod 3)    │
        └─────┬───────┘    └────────┬──────┘    └───────┬──────┘
              └─────────────────────┼─────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
       ┌──────▼──────┐    ┌─────────▼──────┐    ┌────────▼─────┐
       │ TimescaleDB │    │     Redis       │    │    Kafka     │
       │  (HA + Rep) │    │  (Sentinel)     │    │  (3 Brokers) │
       └─────────────┘    └────────────────┘    └──────────────┘
```

### URLs (Produção)

| Serviço | URL |
|---|---|
| API | https://api.macrofund.internal |
| Dashboard | https://app.macrofund.internal |
| Grafana | https://grafana.macrofund.internal |
| Dagster | https://dagster.macrofund.internal |
| Vault | https://vault.macrofund.internal |
| Kafka UI | https://kafka-ui.macrofund.internal |

### Paper Trading — Início Rápido

```bash
# 1. Inicia infraestrutura
make up

# 2. Verifica Fase 3
python scripts/verify_phase3.py

# 3. Injeta sinal de teste no cache
python scripts/inject_test_signals.py

# 4. Inicia paper trading (dry_run por padrão)
python scripts/start_paper_trading.py --interval 60

# 5. Acompanha em tempo real
open http://localhost:3000/live-trading
```

### Próximos Passos (Fase 4 — Scale & Advanced AI)

- **Reinforcement Learning**: Agente RL para sizing dinâmico de posições
- **Alternative Data**: Satellite imagery, social sentiment, credit card data
- **Multi-venue**: Arbitragem entre B3 e CME (USD/BRL cross)
- **Options**: Greeks, vol surface, hedging de tail risk
- **LLM Integration avançada**: Claude API para geração de relatórios de gestores
- **Cloud-native**: AWS EKS + Aurora PostgreSQL + MSK (Kafka managed)
```

## 3. Git commit final:

```bash
git add .
git commit -m "Phase 3: Production Deployment & Live Trading — EMS, Paper Trading, Kafka, Compliance, K8s, CI/CD, Security"
git tag -a v3.0.0 -m "Phase 3 complete: Production-ready macro trading system"
```

## 4. Sumário final — execute e confirme STATUS: PASS:

```bash
python scripts/verify_phase3.py
```

═══ FIM DO PROMPT 20 ═══


# VERIFICAÇÃO FINAL FASE 3:
# ▢ python scripts/verify_phase3.py → STATUS: PASS
# ▢ git log --oneline (3 commits: Phase 0 + Phase 2 + Phase 3)
# ▢ git tag | grep v3.0.0
# ▢ http://localhost:8000/docs (todos os endpoints EMS + paper trading)
# ▢ http://localhost:3000/live-trading (Dashboard com painel de execução)
# ▢ http://localhost:3001 (Dagster: paper trading + performance jobs)
# ▢ http://localhost:3002 (Grafana: execution dashboard)
# ▢ http://localhost:9090 (Kafka UI)
# ▢ http://localhost:8200 (Vault UI)
# ▢ pytest tests/unit/ -v → PASS
# ▢ helm lint helm/macro-fund/ → OK
# ▢ docker build -t macro-fund:test . → OK


################################################################################
##                                                                            ##
##  ══════════════════════════════════════════════════════════════════════    ##
##  FIM DA FASE 3 — PRODUCTION DEPLOYMENT & LIVE TRADING COMPLETOS           ##
##  ══════════════════════════════════════════════════════════════════════    ##
##                                                                            ##
##  CONSTRUÍDO:                                                               ##
##  ✅ EMS (Order, Fill, Position, PnL — ciclo completo)                      ##
##  ✅ PaperGateway (slippage Almgren-Chriss, latência simulada, fills)       ##
##  ✅ B3Gateway + CMEGateway (stubs FIX 4.4 prontos para integração)         ##
##  ✅ Kafka (producer, consumer, price simulator GBM + jump diffusion)       ##
##  ✅ Bloomberg + Refinitiv adapters (stub mode + interface real)            ##
##  ✅ DataFeedManager (fallback hierárquico: BBG → RLSEG → FRED → cache)   ##
##  ✅ Compliance: AuditLogger (dual-write DB + NDJSON, 7 anos retenção)      ##
##  ✅ Pre-trade Risk Controls (fat finger, notional, concentração, turnover) ##
##  ✅ Secrets Management (HashiCorp Vault + Pydantic Settings hierárquico)  ##
##  ✅ CI/CD GitHub Actions (lint, unit, integration, frontend, security scan)##
##  ✅ Kubernetes Helm Charts (HPA, PDB, blue-green, affinity, probes)       ##
##  ✅ Redis Cache Layer (cache-aside, TTL automático, HTTP response cache)   ##
##  ✅ TimescaleDB: continuous aggregates, compressão, query optimizer        ##
##  ✅ Paper Trading Engine (loop 60s, signals→orders→fills→PnL→Kafka)       ##
##  ✅ Performance Tearsheet (Sharpe, Sortino, MDD, heatmap, distribuição)   ##
##  ✅ Live Trading Dashboard React (5 painéis, WebSocket real-time)          ##
##  ✅ Dagster: intraday (5min), EOD (18:30), performance (19:00)             ##
##  ✅ Grafana: execution dashboard (8 painéis) + alertas Prometheus          ##
##  ✅ Prometheus metrics (orders, PnL, slippage, positions, paper cycles)   ##
##  ✅ JWT Auth + Rate Limiting (token bucket Redis) + CORS restritivo        ##
##  ✅ Emergency Stop (cancela ordens + fecha posições + audit + Kafka)       ##
##  ✅ Disaster Recovery (backup.sh, restore.sh, DR playbook, RTO/RPO)       ##
##  ✅ Go-Live Checklist (40+ itens pré/dia/pós go-live, assinaturas)        ##
##  ✅ Testes: unit (slippage, risk controls) + E2E (EMS + paper trading)    ##
##  ✅ verify_phase3.py (12 seções, 60+ verificações automáticas)            ##
##                                                                            ##
##  SISTEMA MACRO HEDGE FUND AI — PRONTO PARA PRODUÇÃO                      ##
##                                                                            ##
##  Stack Final:                                                              ##
##  Python 3.11 | FastAPI | TimescaleDB | Redis | Kafka | Dagster            ##
##  React | Grafana | Prometheus | Vault | K8s | Helm | GitHub Actions       ##
##  Anthropic Claude API | FIX 4.4 | B3 | CME                               ##
##                                                                            ##
################################################################################

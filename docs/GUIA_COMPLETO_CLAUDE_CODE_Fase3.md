################################################################################
##                                                                            ##
##  ══════════════════════════════════════════════════════════════════════    ##
##  MACRO HEDGE FUND AI SYSTEM — GUIA COMPLETO CLAUDE CODE                   ##
##  ══════════════════════════════════════════════════════════════════════    ##
##  FASE 3 — PORTFOLIO MANAGEMENT SYSTEM (PMS)                               ##
##  Execução Manual pelo Gestor | Human-in-the-Loop Architecture             ##
##  ══════════════════════════════════════════════════════════════════════    ##
##                                                                            ##
##  PRÉ-REQUISITO: Fases 0, 1 e 2 completas                                 ##
##  Verificar com: cd macro-fund-system && python scripts/verify_phase2.py   ##
##                                                                            ##
##  COMO USAR:                                                                ##
##  1. Copie o bloco entre "══ INÍCIO DO PROMPT ══" e "══ FIM DO PROMPT ══" ##
##  2. Cole no Claude Code e aguarde execução completa                        ##
##  3. Valide o resultado com os comandos de verificação antes de avançar    ##
##                                                                            ##
##  O QUE SERÁ CONSTRUÍDO:                                                   ##
##  — Portfolio Management System completo (7 telas operacionais)            ##
##  — Book de Posições com P&L em tempo real                                 ##
##  — Trade Blotter com revisão e aprovação manual (human-in-the-loop)       ##
##  — Morning Pack / Daily Briefing automatizado                              ##
##  — Risk Monitor com VaR, stress tests e limites visuais                   ##
##  — Performance Attribution multi-dimensional                               ##
##  — Trade Journal & Decision Log auditável                                 ##
##  — Agent Intelligence Hub com narrativas LLM                              ##
##  — API expandida com 20+ novos endpoints                                  ##
##  — Compliance, Audit e Segurança de produção                              ##
##                                                                            ##
##  FILOSOFIA DE DESIGN (referência: Brevan Howard, Bridgewater, Moore):     ##
##  O sistema maximiza o tempo do gestor em análise e decisão,               ##
##  eliminando o tempo gasto buscando e consolidando informação.             ##
##                                                                            ##
##  TEMPO TOTAL ESTIMADO: 36-46 horas (20 etapas)                           ##
##                                                                            ##
################################################################################


################################################################################
##                                                                            ##
##  ETAPA 1 — DATABASE SCHEMAS: PMS TABLES                                   ##
##  Tempo: ~25 min | Novos schemas para posições, trades e auditoria         ##
##                                                                            ##
################################################################################

══ INÍCIO DO PROMPT 1 ══

Estou trabalhando no projeto macro-fund-system (Fases 0, 1 e 2 completas — TimescaleDB, 5 agentes, 22+ estratégias, risk engine, Grafana, Dagster, React dashboard). Inicio agora a Fase 3: Portfolio Management System (PMS) para operação human-in-the-loop, sem execução eletrônica automatizada.

Nesta etapa, crie os novos database schemas para o PMS.

## 1. src/core/models/pms_models.py

Modelos SQLAlchemy para o Portfolio Management System:

```python
import uuid
from datetime import datetime, date
from enum import Enum as PyEnum
from sqlalchemy import (Column, String, Float, Integer, Boolean, DateTime,
                         Date, Text, JSON, Enum, ForeignKey, UniqueConstraint)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from src.core.models.base import Base

class AssetClass(str, PyEnum):
    RATES_BR = "RATES_BR"
    FX_BR = "FX_BR"
    INFLATION_BR = "INFLATION_BR"
    CUPOM_CAMBIAL = "CUPOM_CAMBIAL"
    SOVEREIGN_CREDIT = "SOVEREIGN_CREDIT"
    CROSS_ASSET = "CROSS_ASSET"

class Direction(str, PyEnum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"

class TradeStatus(str, PyEnum):
    PROPOSED = "PROPOSED"     # Gerado pelo sistema, aguardando revisão
    APPROVED = "APPROVED"     # Aprovado pelo gestor, aguardando execução
    EXECUTED = "EXECUTED"     # Executado e registrado com preço real
    REJECTED = "REJECTED"     # Rejeitado pelo gestor
    MODIFIED = "MODIFIED"     # Aprovado com modificações pelo gestor
    CANCELLED = "CANCELLED"   # Cancelado antes da execução

class PortfolioPosition(Base):
    """Posições abertas do portfólio — fonte da verdade para o book ao vivo."""
    __tablename__ = "portfolio_positions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Identificação
    ticker = Column(String(50), nullable=False, index=True)
    instrument_name = Column(String(200))
    asset_class = Column(Enum(AssetClass), nullable=False)
    direction = Column(Enum(Direction), nullable=False)
    
    # Dados de entrada (preenchidos pelo gestor na execução)
    entry_date = Column(Date, nullable=False)
    entry_price = Column(Float, nullable=False)
    notional_brl = Column(Float, nullable=False)      # Notional em BRL
    notional_usd = Column(Float)                       # Notional em USD (se aplicável)
    quantity = Column(Float)                           # Contratos/unidades
    
    # Métricas de risco na entrada
    dv01_entry = Column(Float)                         # DV01 para instrumentos de renda fixa
    delta_entry = Column(Float)                        # Delta para FX/opções
    
    # Estado atual (atualizado diariamente via mark-to-market)
    current_price = Column(Float)
    current_date = Column(Date)
    unrealized_pnl_brl = Column(Float, default=0.0)
    unrealized_pnl_pct = Column(Float, default=0.0)
    
    # Atribuição e contexto
    strategy_ids = Column(JSON)                        # ["RATES_BR_01", "RATES_BR_02"]
    signal_rationale = Column(Text)                    # Racional do sinal que gerou o trade
    manager_thesis = Column(Text)                      # Tese do gestor no momento da entrada
    
    # Controle
    is_open = Column(Boolean, default=True, nullable=False)
    closed_date = Column(Date)
    closed_price = Column(Float)
    realized_pnl_brl = Column(Float)
    
    # Metadados
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by = Column(String(100), default="manager")


class TradeProposal(Base):
    """Trade proposals gerados pelo sistema, aguardando revisão do gestor."""
    __tablename__ = "trade_proposals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Identificação do trade
    ticker = Column(String(50), nullable=False)
    instrument_name = Column(String(200))
    asset_class = Column(Enum(AssetClass), nullable=False)
    proposed_direction = Column(Enum(Direction), nullable=False)
    proposed_notional_brl = Column(Float, nullable=False)
    
    # Sinais que geraram a proposta
    primary_signal_id = Column(String(100))
    strategy_ids = Column(JSON)
    signal_conviction = Column(Float)                  # 0.0 a 1.0
    signal_direction_score = Column(Float)             # -1.0 a +1.0
    
    # Análise de impacto de risco (pré-trade)
    portfolio_var_before = Column(Float)
    portfolio_var_after_estimate = Column(Float)
    portfolio_leverage_before = Column(Float)
    portfolio_leverage_after_estimate = Column(Float)
    concentration_impact = Column(JSON)                # por asset class
    
    # Fundamentação completa (gerada pelo LLM)
    system_rationale = Column(Text)                    # Narrativa do sistema
    macro_context = Column(Text)                       # Contexto macro atual
    risk_factors = Column(Text)                        # Riscos identificados
    
    # Estimativas de custo
    estimated_cost_bps = Column(Float)
    estimated_cost_brl = Column(Float)
    
    # Decisão do gestor
    status = Column(Enum(TradeStatus), default=TradeStatus.PROPOSED, nullable=False)
    manager_decision_at = Column(DateTime(timezone=True))
    manager_notes = Column(Text)                       # Notas do gestor na decisão
    
    # Se executado: dados reais
    execution_price = Column(Float)
    execution_date = Column(Date)
    execution_notional_brl = Column(Float)             # Pode diferir do proposto
    position_id = Column(UUID(as_uuid=True), ForeignKey("portfolio_positions.id"))
    
    # Metadados
    proposed_at = Column(DateTime(timezone=True), server_default=func.now())
    proposal_date = Column(Date, nullable=False)       # Data do ciclo diário
    valid_until = Column(Date)                         # Proposta expira após N dias


class DecisionJournal(Base):
    """Log imutável de todas as decisões do gestor — compliance e aprendizado."""
    __tablename__ = "decision_journal"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Contexto da decisão
    decision_date = Column(Date, nullable=False, index=True)
    decision_timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # O que foi decidido
    decision_type = Column(String(50), nullable=False)  # OPEN, CLOSE, MODIFY, REJECT, NOTE
    trade_proposal_id = Column(UUID(as_uuid=True), ForeignKey("trade_proposals.id"))
    position_id = Column(UUID(as_uuid=True), ForeignKey("portfolio_positions.id"))
    
    # Dados do trade na decisão
    ticker = Column(String(50))
    asset_class = Column(Enum(AssetClass))
    direction = Column(Enum(Direction))
    notional_brl = Column(Float)
    execution_price = Column(Float)
    
    # Contexto macro no momento da decisão (snapshot)
    macro_snapshot = Column(JSON)                      # SELIC, USDBRL, etc. no momento
    portfolio_snapshot = Column(JSON)                  # Estado do portfólio antes
    risk_snapshot = Column(JSON)                       # VaR, leverage, etc. antes
    
    # Raciocínio do gestor (campo principal — narrativa qualitativa)
    manager_rationale = Column(Text)                   # Por que o gestor tomou essa decisão
    thesis_statement = Column(Text)                    # Tese de investimento
    key_risks = Column(Text)                           # Riscos identificados pelo gestor
    target_price = Column(Float)                       # Onde espera sair
    stop_loss = Column(Float)                          # Stop loss definido
    time_horizon = Column(String(50))                  # "1-2 semanas", "3 meses", etc.
    
    # Resultado ex-post (preenchido quando posição é fechada)
    outcome_pnl_brl = Column(Float)
    outcome_holding_days = Column(Integer)
    outcome_notes = Column(Text)                       # Lições aprendidas
    
    # Controle de imutabilidade
    is_locked = Column(Boolean, default=False)         # True = não pode ser editado
    hash_checksum = Column(String(64))                 # SHA256 para integridade


class DailyBriefing(Base):
    """Morning Pack gerado automaticamente pelo pipeline diário."""
    __tablename__ = "daily_briefings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    briefing_date = Column(Date, nullable=False, unique=True, index=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Snapshot de mercado (D0)
    market_snapshot = Column(JSON)
    macro_indicators = Column(JSON)
    
    # Leituras dos agentes
    agent_views = Column(JSON)
    regime_assessment = Column(JSON)
    
    # Sinais consolidados
    top_signals = Column(JSON)
    signal_changes = Column(JSON)                      # Mudanças vs dia anterior
    
    # Estado do portfólio
    portfolio_state = Column(JSON)
    risk_metrics = Column(JSON)
    
    # Trade proposals do dia
    trade_proposals = Column(JSON)
    
    # Narrativa macro (gerada por LLM — Claude API)
    macro_narrative = Column(Text)
    action_items = Column(JSON)
    
    # Alertas ativos
    active_alerts = Column(JSON)
    
    __table_args__ = (
        UniqueConstraint("briefing_date", name="uq_daily_briefing_date"),
    )


class PositionPnLHistory(Base):
    """Histórico diário de P&L por posição — TimescaleDB hypertable."""
    __tablename__ = "position_pnl_history"
    
    time = Column(DateTime(timezone=True), nullable=False, primary_key=True)
    position_id = Column(UUID(as_uuid=True), ForeignKey("portfolio_positions.id"),
                         nullable=False, primary_key=True)
    
    price = Column(Float, nullable=False)
    unrealized_pnl_brl = Column(Float)
    unrealized_pnl_pct = Column(Float)
    daily_pnl_brl = Column(Float)                      # PnL do dia
    
    # Métricas de risco do dia
    dv01 = Column(Float)
    delta = Column(Float)
    var_contribution_pct = Column(Float)               # Contribuição ao VaR do portfólio
    
    source = Column(String(50), default="manual")      # "manual" | "bloomberg" | "bacen"
```

## 2. Alembic migration

Crie a migration: `alembic revision --autogenerate -m "pms_tables_phase3"`

No upgrade(), após criar as tabelas, adicione:

```sql
-- portfolio_positions hypertable para histórico
-- position_pnl_history como hypertable
SELECT create_hypertable('position_pnl_history', 'time',
       chunk_time_interval => INTERVAL '1 month', if_not_exists => TRUE);

-- Compressão
ALTER TABLE position_pnl_history SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'position_id',
    timescaledb.compress_orderby = 'time DESC'
);
SELECT add_compression_policy('position_pnl_history', INTERVAL '90 days');

-- Índices para performance
CREATE INDEX idx_trade_proposals_date ON trade_proposals(proposal_date DESC);
CREATE INDEX idx_trade_proposals_status ON trade_proposals(status);
CREATE INDEX idx_decision_journal_date ON decision_journal(decision_date DESC);
CREATE INDEX idx_portfolio_positions_open ON portfolio_positions(is_open, asset_class);
```

## 3. Registre os novos modelos

Importe todos os modelos em `src/core/models/__init__.py` para o Alembic detectar.

## 4. Testes básicos

Crie `tests/test_pms_models.py`:
- test_create_portfolio_position: cria posição, verifica campos obrigatórios
- test_create_trade_proposal: cria proposta, verifica status inicial PROPOSED
- test_decision_journal_immutability: testa lock de registro

══ FIM DO PROMPT 1 ══

# VERIFICAÇÃO:
# □ alembic upgrade head → sem erros
# □ SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'portfolio%' OR table_name LIKE 'trade%' OR table_name LIKE 'decision%'
# □ pytest tests/test_pms_models.py -v


################################################################################
##                                                                            ##
##  ETAPA 2 — PMS SERVICE LAYER: POSITION MANAGER                            ##
##  Tempo: ~30 min | Core business logic para gerenciamento de posições       ##
##                                                                            ##
################################################################################

══ INÍCIO DO PROMPT 2 ══

No projeto macro-fund-system (Etapa 1 da Fase 3 completa — tabelas PMS criadas), implemente o Position Manager Service.

## 1. src/pms/position_manager.py

```python
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
import uuid
import hashlib
import json

class PositionManager:
    """
    Gerencia o ciclo de vida completo das posições do portfólio.
    Filosofia: todas as operações são registradas e auditáveis.
    Referência: sistema de portfolio accounting de prime brokers institucionais.
    """
    
    def __init__(self, db_session, price_fetcher=None):
        self.db = db_session
        self.price_fetcher = price_fetcher  # Opcional: para MTM automático
    
    async def open_position(
        self,
        ticker: str,
        asset_class: str,
        direction: str,
        entry_date: date,
        entry_price: float,
        notional_brl: float,
        strategy_ids: list[str],
        manager_thesis: str,
        signal_rationale: str = None,
        trade_proposal_id: str = None,
        **kwargs
    ) -> dict:
        """
        Abre nova posição no book.
        Calcula métricas de risco na entrada (DV01 para rates, delta para FX).
        Registra no DecisionJournal automaticamente.
        Retorna posição criada com risk metrics calculadas.
        """
        ...
    
    async def close_position(
        self,
        position_id: str,
        close_date: date,
        close_price: float,
        manager_notes: str = None
    ) -> dict:
        """
        Fecha posição, calcula P&L realizado.
        Atualiza DecisionJournal com outcome (pnl, holding days).
        """
        ...
    
    async def mark_to_market(
        self,
        as_of_date: date,
        prices: dict[str, float] = None  # {ticker: price} — se None, busca automaticamente
    ) -> dict:
        """
        Atualiza preços e P&L de todas as posições abertas.
        Registra em position_pnl_history.
        Retorna: {updated: N, total_unrealized_pnl_brl: X, positions: [...]}
        """
        ...
    
    async def get_book(self, as_of_date: date = None) -> dict:
        """
        Retorna estado completo do book ao vivo.
        Estrutura compatível com o frontend PMS.
        
        Returns:
        {
          "summary": {
            "total_positions": int,
            "aum_brl": float,
            "gross_notional_brl": float,
            "net_notional_brl": float,
            "gross_leverage": float,
            "net_leverage": float,
            "total_unrealized_pnl_brl": float,
            "total_unrealized_pnl_pct": float,
            "pnl_today_brl": float,
            "pnl_mtd_brl": float,
            "pnl_ytd_brl": float,
          },
          "positions": [
            {
              "id": str,
              "ticker": str,
              "instrument_name": str,
              "asset_class": str,
              "direction": str,
              "entry_date": str,
              "entry_price": float,
              "current_price": float,
              "notional_brl": float,
              "unrealized_pnl_brl": float,
              "unrealized_pnl_pct": float,
              "daily_pnl_brl": float,
              "holding_days": int,
              "dv01": float,          # para rates
              "delta": float,         # para FX
              "var_contribution_pct": float,
              "strategies": list[str],
              "manager_thesis": str,
            }
          ],
          "by_asset_class": {
            "RATES_BR": {"count": int, "notional_brl": float, "pnl_brl": float},
            ...
          }
        }
        """
        ...
    
    async def get_pnl_timeseries(
        self,
        start_date: date,
        end_date: date,
        position_id: str = None  # None = portfólio total
    ) -> list[dict]:
        """
        Retorna série temporal de P&L para equity curve.
        Se position_id fornecido, retorna P&L daquela posição específica.
        """
        ...
    
    async def compute_risk_metrics_on_entry(
        self,
        ticker: str,
        asset_class: str,
        notional_brl: float,
        direction: str
    ) -> dict:
        """
        Calcula DV01, delta e outras métricas de risco no momento da entrada.
        Para RATES_BR: DV01 = notional * duration_modified / 10000
        Para FX_BR: delta = notional_brl (exposição direta)
        """
        ...
    
    def _create_decision_journal_entry(
        self,
        decision_type: str,
        position_id: str,
        trade_proposal_id: str,
        ticker: str,
        asset_class: str,
        direction: str,
        notional_brl: float,
        execution_price: float,
        manager_rationale: str,
        **kwargs
    ) -> dict:
        """
        Cria entrada imutável no DecisionJournal.
        Inclui snapshot de mercado e portfólio no momento da decisão.
        Gera hash SHA256 para integridade.
        """
        ...
```

## 2. src/pms/mtm_service.py

```python
class MarkToMarketService:
    """
    Serviço de mark-to-market diário.
    Fontes de preço em ordem de prioridade:
    1. Preços manuais (input do gestor via UI)
    2. Dados do TimescaleDB (market_data table — Fase 0)
    3. BACEN API (para taxas de referência)
    """
    
    async def get_prices_for_positions(
        self,
        tickers: list[str],
        as_of_date: date,
        manual_overrides: dict[str, float] = None
    ) -> dict[str, float]:
        """
        Busca preços para os tickers das posições abertas.
        Fallback para último preço disponível com log de warning.
        """
        ...
    
    async def compute_dv01(self, ticker: str, notional: float, maturity_date) -> float:
        """
        DV01 simplificado: usa duration da curva DI_PRE para o prazo.
        DV01 = notional * modified_duration / 10000
        """
        ...
    
    async def compute_var_contributions(self, positions: list) -> dict[str, float]:
        """
        Contribuição de cada posição ao VaR do portfólio (componente VaR).
        Usa a VaR Engine da Fase 2.
        """
        ...
```

## 3. src/pms/__init__.py e estrutura de diretórios

```
src/pms/
├── __init__.py
├── position_manager.py
├── mtm_service.py
├── trade_workflow.py     # Etapa 3
├── morning_pack.py       # Etapa 5
├── attribution.py        # Etapa 7
└── compliance.py         # Etapa 15
```

## 4. Testes

`tests/test_pms/test_position_manager.py`:
- test_open_position: abre posição, verifica campos, verifica journal entry criada
- test_close_position: fecha, verifica P&L realizado calculado corretamente
- test_mark_to_market: MTM com preços mockados, verifica unrealized_pnl
- test_get_book_structure: get_book() retorna estrutura correta

══ FIM DO PROMPT 2 ══

# VERIFICAÇÃO:
# □ pytest tests/test_pms/test_position_manager.py -v


################################################################################
##                                                                            ##
##  ETAPA 3 — TRADE WORKFLOW: PROPOSALS & HUMAN-IN-THE-LOOP                  ##
##  Tempo: ~30 min | Motor de aprovação de trades pelo gestor                 ##
##                                                                            ##
################################################################################

══ INÍCIO DO PROMPT 3 ══

No projeto macro-fund-system (Etapas 1-2 da Fase 3 completas), implemente o Trade Workflow — o coração do sistema human-in-the-loop.

## 1. src/pms/trade_workflow.py

```python
class TradeWorkflowService:
    """
    Gerencia o ciclo de vida dos trade proposals:
    Sistema gera → Gestor revisa → Gestor decide → Sistema registra.
    
    Referência: workflow de trade review em macro funds tier-1,
    onde o PM tem visão completa do impacto de risco antes de executar.
    """
    
    def __init__(self, db_session, position_manager, risk_engine, signal_aggregator):
        ...
    
    async def generate_proposals_from_signals(self, as_of_date: date) -> list[dict]:
        """
        Pipeline principal: sinais → trade proposals.
        
        1. Carrega sinais agregados do dia (SignalAggregator — Fase 2)
        2. Compara com posições abertas (verifica se já tem posição)
        3. Para sinais novos/invertidos acima do threshold de convicção:
           a. Calcula notional proposto (baseado em vol target e convicção)
           b. Estima impacto no portfólio (VaR, leverage, concentração)
           c. Gera narrativa LLM com contexto macro (Claude API)
           d. Cria TradeProposal no banco com status PROPOSED
        4. Retorna lista de proposals geradas
        
        Thresholds:
        - conviction_min: 0.55 (só propõe se convicção > 55%)
        - flip_threshold: 0.60 (sinal invertido: convicção > 60%)
        - max_proposals_per_day: 5 (evita ruído)
        """
        ...
    
    async def get_pending_proposals(self, as_of_date: date = None) -> list[dict]:
        """
        Retorna proposals com status PROPOSED ordenados por convicção desc.
        Filtra propostas vencidas (valid_until).
        """
        ...
    
    async def approve_proposal(
        self,
        proposal_id: str,
        execution_price: float,
        execution_notional_brl: float,  # Gestor pode modificar o tamanho
        manager_notes: str = None,
        manager_thesis: str = None,
        target_price: float = None,
        stop_loss: float = None,
        time_horizon: str = None
    ) -> dict:
        """
        Gestor aprova e registra execução do trade.
        1. Atualiza TradeProposal para EXECUTED
        2. Cria PortfolioPosition com dados reais de execução
        3. Registra no DecisionJournal com todos os campos
        4. Retorna posição criada
        """
        ...
    
    async def reject_proposal(
        self,
        proposal_id: str,
        manager_notes: str  # Obrigatório ao rejeitar
    ) -> dict:
        """
        Gestor rejeita proposta com justificativa.
        Registra no DecisionJournal (decisões de não-fazer também são auditáveis).
        """
        ...
    
    async def modify_and_approve_proposal(
        self,
        proposal_id: str,
        modified_direction: str = None,    # Gestor pode inverter
        modified_notional_brl: float = None,
        execution_price: float = None,
        manager_notes: str = None,
        **kwargs
    ) -> dict:
        """
        Gestor modifica parâmetros e aprova.
        Status final: MODIFIED (distinto de EXECUTED para análise posterior).
        """
        ...
    
    async def open_discretionary_trade(
        self,
        ticker: str,
        asset_class: str,
        direction: str,
        notional_brl: float,
        execution_price: float,
        entry_date: date,
        manager_thesis: str,          # Obrigatório para trades discricionários
        target_price: float = None,
        stop_loss: float = None,
        time_horizon: str = None,
        strategy_ids: list[str] = None
    ) -> dict:
        """
        Gestor abre trade discricionário (não gerado pelo sistema).
        Cria TradeProposal retroativamente com status EXECUTED.
        Cria PortfolioPosition e registra no Journal.
        """
        ...
    
    async def close_position(
        self,
        position_id: str,
        close_price: float,
        close_date: date,
        manager_notes: str = None,
        outcome_notes: str = None   # Lições aprendidas
    ) -> dict:
        """
        Gestor fecha posição aberta.
        Calcula P&L realizado e registra outcome no Journal.
        """
        ...
    
    async def _estimate_portfolio_impact(
        self,
        ticker: str,
        asset_class: str,
        direction: str,
        notional_brl: float
    ) -> dict:
        """
        Estimativa de impacto pré-trade (pre-trade analytics).
        Retorna: {var_before, var_after, leverage_before, leverage_after,
                  concentration_by_asset_class, margin_available}
        """
        ...
    
    async def _generate_trade_rationale(
        self,
        ticker: str,
        asset_class: str,
        direction: str,
        signal_data: dict,
        portfolio_impact: dict,
        macro_context: dict
    ) -> str:
        """
        Gera narrativa do trade via Claude API.
        Inclui: sinal técnico, contexto macro, impacto de risco, riscos do trade.
        """
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic()
        
        prompt = f"""
        Você é um analista sênior de um macro hedge fund brasileiro.
        Gere uma narrativa concisa (max 300 palavras) justificando a seguinte proposta de trade:
        
        Instrumento: {ticker}
        Direção: {direction}
        Notional: R$ {notional_brl:,.0f}
        
        Sinais do Sistema:
        {json.dumps(signal_data, ensure_ascii=False, indent=2)}
        
        Contexto Macro Atual:
        {json.dumps(macro_context, ensure_ascii=False, indent=2)}
        
        Impacto no Portfólio:
        - VaR antes: {portfolio_impact.get('var_before', 'N/A')}
        - VaR depois (estimado): {portfolio_impact.get('var_after', 'N/A')}
        
        Estruture em: (1) Fundamento do trade, (2) Catalisadores, (3) Riscos principais.
        Seja objetivo e preciso. Use dados quantitativos quando disponível.
        """
        
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
```

## 2. Testes

`tests/test_pms/test_trade_workflow.py`:
- test_generate_proposals: simula sinais e verifica proposals geradas
- test_approve_proposal: aprova proposal, verifica posição criada e journal entry
- test_reject_proposal: rejeita com notas, verifica status e journal
- test_open_discretionary_trade: abre trade manual, verifica registro
- test_close_position_with_pnl: fecha posição, verifica P&L calculado

══ FIM DO PROMPT 3 ══

# VERIFICAÇÃO:
# □ pytest tests/test_pms/test_trade_workflow.py -v


################################################################################
##                                                                            ##
##  ETAPA 4 — API ENDPOINTS: PMS CORE                                        ##
##  Tempo: ~30 min | 20+ endpoints para o frontend PMS                        ##
##                                                                            ##
################################################################################

══ INÍCIO DO PROMPT 4 ══

No projeto macro-fund-system (Etapas 1-3 da Fase 3 completas), implemente os endpoints da API para o Portfolio Management System.

## 1. src/api/routes/pms_portfolio.py

```python
"""
Endpoints do Book de Posições e operações de portfolio.
"""
router = APIRouter(prefix="/api/v1/pms", tags=["PMS - Portfolio"])

# --- Book de Posições ---

@router.get("/book")
async def get_book(as_of_date: date = None, db=Depends(get_db)) -> dict:
    """Estado completo do book ao vivo com P&L e métricas de risco."""

@router.get("/book/positions")
async def get_positions(
    asset_class: str = None,
    is_open: bool = True,
    db=Depends(get_db)
) -> list[dict]:
    """Lista de posições com filtros opcionais."""

@router.post("/book/positions/open")
async def open_position(payload: OpenPositionRequest, db=Depends(get_db)) -> dict:
    """Abre nova posição manualmente (trade discricionário)."""

@router.post("/book/positions/{position_id}/close")
async def close_position(
    position_id: str,
    payload: ClosePositionRequest,
    db=Depends(get_db)
) -> dict:
    """Fecha posição e registra P&L realizado."""

@router.post("/book/positions/{position_id}/update-price")
async def update_position_price(
    position_id: str,
    price: float,
    price_date: date,
    db=Depends(get_db)
) -> dict:
    """Atualiza preço atual de uma posição (mark-to-market manual)."""

@router.post("/book/mtm")
async def mark_to_market(
    payload: MTMRequest,  # {as_of_date, manual_prices: {ticker: price}}
    db=Depends(get_db)
) -> dict:
    """Executa mark-to-market para todas as posições abertas."""

# --- P&L e Performance ---

@router.get("/pnl/summary")
async def get_pnl_summary(
    start_date: date = None,
    end_date: date = None,
    db=Depends(get_db)
) -> dict:
    """P&L consolidado: today, MTD, YTD, inception."""

@router.get("/pnl/equity-curve")
async def get_equity_curve(
    start_date: date,
    end_date: date = None,
    db=Depends(get_db)
) -> list[dict]:
    """Série temporal do portfólio para equity curve chart."""

@router.get("/pnl/attribution")
async def get_pnl_attribution(
    start_date: date = None,
    end_date: date = None,
    db=Depends(get_db)
) -> dict:
    """Atribuição de P&L por: estratégia, asset class, instrumento."""

@router.get("/pnl/monthly-heatmap")
async def get_monthly_heatmap(
    year: int = None,
    db=Depends(get_db)
) -> list[dict]:
    """Retornos mensais para heatmap: [{year, month, return_pct}]."""
```

## 2. src/api/routes/pms_trades.py

```python
"""
Endpoints do Trade Blotter — workflow de aprovação de trades.
"""
router = APIRouter(prefix="/api/v1/pms/trades", tags=["PMS - Trade Blotter"])

@router.get("/proposals")
async def get_proposals(
    status: str = "PROPOSED",  # PROPOSED | APPROVED | EXECUTED | REJECTED | ALL
    date_from: date = None,
    db=Depends(get_db)
) -> list[dict]:
    """Lista trade proposals com filtros de status e data."""

@router.get("/proposals/{proposal_id}")
async def get_proposal_detail(proposal_id: str, db=Depends(get_db)) -> dict:
    """Detalhes completos de um proposal incluindo análise de risco e narrativa."""

@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: str,
    payload: ApproveProposalRequest,
    db=Depends(get_db)
) -> dict:
    """Gestor aprova e registra execução do trade."""

@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: str,
    payload: RejectProposalRequest,  # {manager_notes: str (obrigatório)}
    db=Depends(get_db)
) -> dict:
    """Gestor rejeita proposal com justificativa."""

@router.post("/proposals/{proposal_id}/modify-approve")
async def modify_and_approve(
    proposal_id: str,
    payload: ModifyApproveRequest,
    db=Depends(get_db)
) -> dict:
    """Gestor modifica parâmetros e aprova."""

@router.post("/proposals/generate")
async def generate_proposals(
    as_of_date: date = None,
    db=Depends(get_db)
) -> dict:
    """Força geração de proposals a partir dos sinais do dia."""
```

## 3. src/api/routes/pms_journal.py

```python
"""
Endpoints do Decision Journal — log auditável de decisões.
"""
router = APIRouter(prefix="/api/v1/pms/journal", tags=["PMS - Decision Journal"])

@router.get("/")
async def get_journal_entries(
    date_from: date = None,
    date_to: date = None,
    decision_type: str = None,  # OPEN | CLOSE | REJECT | NOTE
    asset_class: str = None,
    skip: int = 0,
    limit: int = 50,
    db=Depends(get_db)
) -> dict:
    """Lista entradas do journal com paginação e filtros."""

@router.get("/{entry_id}")
async def get_journal_entry(entry_id: str, db=Depends(get_db)) -> dict:
    """Detalhes de uma decisão com snapshot de contexto."""

@router.post("/{entry_id}/outcome")
async def record_outcome(
    entry_id: str,
    payload: OutcomeRequest,  # {outcome_pnl, outcome_notes}
    db=Depends(get_db)
) -> dict:
    """Registra resultado ex-post de uma decisão (após fechamento da posição)."""

@router.get("/stats/decision-analysis")
async def get_decision_analysis(
    start_date: date = None,
    db=Depends(get_db)
) -> dict:
    """
    Análise estatística das decisões do gestor:
    - Taxa de acerto por asset class
    - P&L médio por tipo de trade
    - Holding period analysis
    - Razões mais frequentes de rejeição
    """
```

## 4. Pydantic Request/Response Models

Crie `src/api/schemas/pms_schemas.py` com todos os modelos Pydantic:
- OpenPositionRequest, ClosePositionRequest, MTMRequest
- ApproveProposalRequest, RejectProposalRequest, ModifyApproveRequest
- OutcomeRequest
- BookResponse, PositionResponse, TradeProposalResponse, JournalEntryResponse

## 5. Registre os routers em main.py

Adicione os três novos routers. Swagger tags: "PMS - Portfolio", "PMS - Trade Blotter", "PMS - Decision Journal".

## 6. Testes de API

`tests/test_pms/test_pms_api.py` com FastAPI TestClient:
- test_get_book_empty: book vazio retorna estrutura válida
- test_open_and_close_position: ciclo completo via API
- test_trade_proposal_workflow: generate → get → approve → verify position
- test_journal_entries_created: verifica entradas criadas automaticamente

══ FIM DO PROMPT 4 ══

# VERIFICAÇÃO:
# □ make api → http://localhost:8000/docs → seção "PMS" com todos os endpoints
# □ pytest tests/test_pms/test_pms_api.py -v


################################################################################
##                                                                            ##
##  ETAPA 5 — MORNING PACK SERVICE                                            ##
##  Tempo: ~35 min | Daily briefing automatizado                              ##
##                                                                            ##
################################################################################

══ INÍCIO DO PROMPT 5 ══

No projeto macro-fund-system (Etapas 1-4 da Fase 3 completas), implemente o Morning Pack Service — o daily briefing automatizado para o gestor.

## 1. src/pms/morning_pack.py

```python
class MorningPackService:
    """
    Gera o Morning Pack diário — equivalente ao "morning pack" que
    PMs de macro funds tier-1 recebem antes do mercado abrir.
    
    Estrutura baseada em práticas do Brevan Howard e BlueCrest:
    - Snapshot de mercado (preços D-1 e overnight)
    - Leituras dos agentes (posicionamento analítico)
    - Estado do portfólio (P&L, risco)
    - Trade proposals do dia
    - Narrativa macro (LLM)
    - Action items prioritizados
    """
    
    def __init__(self, db_session, signal_aggregator, risk_engine,
                 position_manager, trade_workflow, anthropic_client):
        ...
    
    async def generate(self, briefing_date: date, force: bool = False) -> dict:
        """
        Gera o Morning Pack completo para a data.
        Se já existe para a data e force=False, retorna o existente.
        
        Steps:
        1. Carrega macro snapshot (últimos valores das séries-chave)
        2. Carrega leituras dos 5 agentes
        3. Carrega regime assessment atual (HMM)
        4. Carrega top sinais por convicção
        5. Carrega sinais que mudaram vs dia anterior (flips e surges)
        6. Carrega estado do portfólio e risco
        7. Gera trade proposals (via TradeWorkflowService)
        8. Gera narrativa macro via Claude API
        9. Prioriza action items
        10. Persiste em daily_briefings
        """
        ...
    
    async def _get_macro_snapshot(self, as_of_date: date) -> dict:
        """
        Carrega os indicadores-chave da tabela macro_series.
        
        Grupos:
        - brazil_rates: SELIC_TARGET, DI_1Y, DI_3Y, DI_5Y, DI_10Y, NTN_B_2027, NTN_B_2035
        - brazil_macro: IPCA_12M, IPCA_MOM, FOCUS_IPCA_EOY, FOCUS_SELIC_EOY, IBC_BR_YOY
        - brazil_fiscal: NET_DEBT_GDP, PRIMARY_BALANCE_GDP
        - fx: USDBRL, PTAX, USDBRL_1Y_NDF
        - us_rates: FED_FUNDS, UST_2Y, UST_10Y, UST_30Y, TIPS_10Y, BREAKEVEN_10Y
        - us_macro: CPI_CORE_YOY, PCE_CORE_YOY, NFP_MOM, UNEMPLOYMENT
        - global: DXY, VIX, GOLD, OIL_WTI, EURUSD, EMBI_BR
        - credit: BR_CDS_5Y, EM_SPREADS
        
        Para cada indicador: {value, date, change_1d, change_5d, change_1m, z_score_1y}
        """
        ...
    
    async def _get_signal_changes(self, as_of_date: date) -> dict:
        """
        Identifica mudanças de sinal relevantes vs dia anterior:
        - Flips de direção (SHORT → LONG ou vice-versa)
        - Surges de convicção (>20% em 1 dia)
        - Novos sinais acima do threshold
        """
        ...
    
    async def _generate_macro_narrative(
        self,
        macro_snapshot: dict,
        agent_views: dict,
        regime: dict,
        portfolio_state: dict,
        signal_changes: dict
    ) -> str:
        """
        Gera narrativa macro concisa via Claude API.
        Max 500 palavras. Estrutura:
        1. Contexto macro atual (2-3 parágrafos)
        2. Drivers de mercado para o dia
        3. Implicações para o portfólio
        """
        ...
    
    async def _prioritize_action_items(
        self,
        trade_proposals: list,
        active_alerts: list,
        signal_changes: dict,
        portfolio_risk: dict
    ) -> list[dict]:
        """
        Lista priorizada de ações para o dia.
        Cada item: {priority, category, description, urgency}
        Prioridades: CRITICAL > HIGH > MEDIUM > LOW
        """
        ...
    
    async def get_latest(self) -> dict:
        """Retorna o Morning Pack mais recente disponível."""
        ...
    
    async def get_by_date(self, briefing_date: date) -> dict:
        """Retorna Morning Pack de uma data específica."""
        ...
```

## 2. API Endpoint para Morning Pack

Em `src/api/routes/pms_briefing.py`:

```
GET /api/v1/pms/morning-pack/latest          → Último Morning Pack
GET /api/v1/pms/morning-pack/{date}          → Morning Pack de data específica
POST /api/v1/pms/morning-pack/generate       → Força geração para hoje
GET /api/v1/pms/morning-pack/history?days=30 → Histórico resumido
```

## 3. Integração com Dagster

Em `src/orchestration/jobs.py` (Fase 2), adicione job:

```python
@job(name="daily_morning_pack")
def morning_pack_job():
    """Executa após daily_pipeline. Gera Morning Pack e proposals."""
    # Depende de: all_agents_job, signal_aggregation_job
    morning_pack_asset  # novo Dagster asset
```

Executar após os agentes rodarem, antes do mercado abrir (6:30 BRT).

## 4. Testes

`tests/test_pms/test_morning_pack.py`:
- test_generate_morning_pack: gera pack com dados mockados, verifica estrutura
- test_macro_snapshot_completeness: verifica que todas as séries-chave estão presentes
- test_signal_changes_detection: verifica detecção de flips
- test_action_items_prioritization: verifica ordenação por prioridade

══ FIM DO PROMPT 5 ══

# VERIFICAÇÃO:
# □ POST /api/v1/pms/morning-pack/generate → retorna pack completo
# □ GET /api/v1/pms/morning-pack/latest → dados estruturados
# □ pytest tests/test_pms/test_morning_pack.py -v


################################################################################
##                                                                            ##
##  ETAPA 6 — RISK MONITOR SERVICE                                            ##
##  Tempo: ~25 min | Risco em tempo real integrado ao PMS                     ##
##                                                                            ##
################################################################################

══ INÍCIO DO PROMPT 6 ══

No projeto macro-fund-system (Etapas 1-5 da Fase 3 completas), implemente o Risk Monitor Service integrado ao PMS.

## 1. src/pms/risk_monitor.py

```python
class PMSRiskMonitor:
    """
    Monitor de risco integrado ao Portfolio Management System.
    Adapta o Risk Engine da Fase 2 para o contexto do portfólio real (posições manuais).
    
    Referência: risk management framework de macro funds
    (Bridgewater Pure Alpha risk parity, Brevan Howard risk limits).
    """
    
    def __init__(self, db_session, risk_engine, position_manager):
        ...
    
    async def compute_live_risk(self, as_of_date: date = None) -> dict:
        """
        Calcula todas as métricas de risco para o portfólio atual.
        
        Returns:
        {
          "var": {
            "historical_95": float,    # % do AUM
            "historical_99": float,
            "parametric_95": float,
            "monte_carlo_95": float,
            "limit_95_pct": float,     # Limite definido
            "utilization_pct": float,  # Uso do limite (0-100)
          },
          "leverage": {
            "gross": float,
            "net": float,
            "limit_gross": float,
            "utilization_pct": float,
          },
          "drawdown": {
            "current_drawdown_pct": float,    # De HWM
            "hwm_date": str,
            "days_in_drawdown": int,
            "max_drawdown_pct": float,        # Histórico
            "limit_drawdown_pct": float,
          },
          "concentration": {
            "by_asset_class": {
              "RATES_BR": {"notional_pct": float, "limit_pct": float},
              "FX_BR": {...},
              ...
            },
            "top_3_positions_pct": float,     # Concentração top 3
          },
          "stress_tests": [
            {
              "scenario": "COPOM_hike_100bps",
              "pnl_brl": float,
              "pnl_pct": float,
              "description": str,
            },
            ...  # 6 cenários da Fase 2
          ],
          "alerts": [
            {
              "type": str,        # VAR_WARNING | LEVERAGE_BREACH | DRAWDOWN_ALERT
              "severity": str,    # CRITICAL | WARNING | INFO
              "message": str,
              "value": float,
              "limit": float,
            }
          ],
          "correlation_matrix": dict,    # Para visualização
          "factor_exposures": dict,      # Duration, DXY beta, etc.
        }
        """
        ...
    
    async def get_var_history(self, days: int = 252) -> list[dict]:
        """Série histórica de VaR para gráfico."""
        ...
    
    async def get_drawdown_history(self, start_date: date = None) -> list[dict]:
        """Série de drawdown para gráfico (drawdown = (equity - HWM) / HWM)."""
        ...
    
    async def run_stress_test(
        self,
        scenario_name: str,
        custom_shocks: dict[str, float] = None  # {ticker: shock_pct}
    ) -> dict:
        """Executa stress test ad-hoc."""
        ...
    
    async def compute_pre_trade_risk(
        self,
        ticker: str,
        asset_class: str,
        direction: str,
        notional_brl: float
    ) -> dict:
        """
        Análise de risco pré-trade: impacto no portfólio se o trade for executado.
        Retorna métricas antes e depois.
        """
        ...
    
    def _build_returns_matrix(self, positions: list, days: int = 252) -> np.ndarray:
        """
        Constrói matriz de retornos das posições atuais para VaR histórico.
        Usa market_data da Fase 0 para histórico de preços.
        """
        ...
```

## 2. API Endpoint

Em `src/api/routes/pms_risk.py`:

```
GET /api/v1/pms/risk/live                         → Métricas completas ao vivo
GET /api/v1/pms/risk/var-history?days=252          → Histórico de VaR
GET /api/v1/pms/risk/drawdown-history              → Histórico de drawdown
POST /api/v1/pms/risk/stress-test                  → Stress test ad-hoc
POST /api/v1/pms/risk/pre-trade                    → Análise pré-trade
GET /api/v1/pms/risk/limits                        → Limites e utilização atual
```

## 3. Limites de Risco Configuráveis

Crie `src/pms/risk_limits.py` com dataclass `PMSRiskLimits`:

```python
@dataclass
class PMSRiskLimits:
    # VaR
    var_95_limit_pct: float = 2.0        # 2% do AUM
    var_99_limit_pct: float = 3.0        # 3% do AUM
    
    # Leverage
    gross_leverage_limit: float = 4.0    # 4x
    net_leverage_limit: float = 2.0      # 2x
    
    # Drawdown
    drawdown_warning_pct: float = 5.0    # Warning em -5%
    drawdown_limit_pct: float = 10.0     # Hard limit em -10%
    
    # Concentração por asset class (% do gross notional)
    rates_br_max_pct: float = 60.0
    fx_br_max_pct: float = 40.0
    inflation_br_max_pct: float = 30.0
    sovereign_max_pct: float = 20.0
    
    # Carregue de config ou banco (permite ajuste pelo gestor)
    @classmethod
    def from_db(cls, db) -> "PMSRiskLimits": ...
    
    @classmethod
    def from_env(cls) -> "PMSRiskLimits": ...
```

## 4. Testes

`tests/test_pms/test_risk_monitor.py`:
- test_live_risk_structure: verifica estrutura completa do output
- test_var_computation: VaR calculado corretamente com posições mockadas
- test_concentration_limits: detecta breach de concentração
- test_pre_trade_risk: impacto pré-trade calculado corretamente

══ FIM DO PROMPT 6 ══

# VERIFICAÇÃO:
# □ GET /api/v1/pms/risk/live → métricas completas
# □ pytest tests/test_pms/test_risk_monitor.py -v


################################################################################
##                                                                            ##
##  ETAPA 7 — PERFORMANCE ATTRIBUTION ENGINE                                  ##
##  Tempo: ~25 min | Atribuição multi-dimensional de P&L                      ##
##                                                                            ##
################################################################################

══ INÍCIO DO PROMPT 7 ══

No projeto macro-fund-system (Etapas 1-6 da Fase 3 completas), implemente o Performance Attribution Engine.

## 1. src/pms/attribution.py

```python
class PerformanceAttributionEngine:
    """
    Calcula atribuição de performance multi-dimensional.
    
    Referências:
    - Brinson-Hood-Beebower (1986): atribuição por asset class
    - Factor attribution: duration, carry, FX beta
    - Lopez de Prado (2018): backtest analytics
    
    Dimensões de atribuição:
    1. Por estratégia (RATES_BR_01, FX_01, etc.)
    2. Por asset class (RATES_BR, FX_BR, etc.)
    3. Por instrumento (posição específica)
    4. Por fator de risco (duration, carry, FX)
    5. Por tipo de trade (sistemático vs discricionário)
    6. Por período (daily, MTD, YTD, desde inception)
    """
    
    def __init__(self, db_session, position_manager):
        ...
    
    async def compute_attribution(
        self,
        start_date: date,
        end_date: date = None
    ) -> dict:
        """
        Atribuição completa para o período.
        
        Returns:
        {
          "period": {"start": str, "end": str, "calendar_days": int},
          "total_return_pct": float,
          "total_pnl_brl": float,
          
          "by_strategy": [
            {
              "strategy_id": str,
              "strategy_name": str,
              "pnl_brl": float,
              "return_contribution_pct": float,
              "trades_count": int,
              "win_rate_pct": float,
            }
          ],
          
          "by_asset_class": [
            {
              "asset_class": str,
              "pnl_brl": float,
              "return_contribution_pct": float,
              "avg_notional_brl": float,
            }
          ],
          
          "by_position": [
            {
              "position_id": str,
              "ticker": str,
              "direction": str,
              "pnl_brl": float,
              "return_pct": float,
              "holding_days": int,
            }
          ],
          
          "by_trade_type": {
            "systematic": {"pnl_brl": float, "count": int},
            "discretionary": {"pnl_brl": float, "count": int},
          },
          
          "monthly_returns": [
            {"year": int, "month": int, "return_pct": float, "pnl_brl": float}
          ],
          
          "performance_stats": {
            "annualized_return_pct": float,
            "annualized_vol_pct": float,
            "sharpe_ratio": float,
            "sortino_ratio": float,
            "calmar_ratio": float,
            "max_drawdown_pct": float,
            "win_rate_pct": float,          # % de dias positivos
            "profit_factor": float,         # Ganhos totais / Perdas totais
            "avg_win_brl": float,
            "avg_loss_brl": float,
          }
        }
        """
        ...
    
    async def compute_equity_curve(
        self,
        start_date: date,
        end_date: date = None,
        base_aum: float = None
    ) -> list[dict]:
        """
        Série temporal da equity curve do fundo.
        [{date, equity_brl, return_pct_daily, return_pct_cumulative, drawdown_pct}]
        """
        ...
    
    async def compute_rolling_metrics(
        self,
        metric: str,  # "sharpe" | "vol" | "return"
        window_days: int = 63,  # ~1 trimestre
        start_date: date = None
    ) -> list[dict]:
        """Rolling Sharpe, vol e retorno para chart de tendência."""
        ...
    
    async def benchmark_comparison(
        self,
        start_date: date,
        end_date: date = None,
        benchmarks: list[str] = None  # ["CDI", "IMA_B", "IHFA"]
    ) -> dict:
        """
        Compara performance do fundo vs benchmarks.
        CDI e IMA_B disponíveis na macro_series table.
        """
        ...
```

## 2. API Endpoint

Em `src/api/routes/pms_attribution.py`:

```
GET /api/v1/pms/attribution?start_date=...&end_date=... → Atribuição completa
GET /api/v1/pms/attribution/equity-curve               → Equity curve
GET /api/v1/pms/attribution/monthly-heatmap            → Retornos mensais
GET /api/v1/pms/attribution/rolling?metric=sharpe&window=63 → Rolling metrics
GET /api/v1/pms/attribution/benchmark?benchmarks=CDI,IMA_B  → vs Benchmarks
GET /api/v1/pms/attribution/best-worst?n=10            → Top/bottom trades
```

## 3. Testes

`tests/test_pms/test_attribution.py`:
- test_equity_curve_consistency: equity curve soma corretamente
- test_monthly_heatmap_structure: 12 meses por ano
- test_attribution_sums_to_total: soma das partes = total
- test_sharpe_ratio_calculation: Sharpe com dados conhecidos

══ FIM DO PROMPT 7 ══

# VERIFICAÇÃO:
# □ GET /api/v1/pms/attribution → resposta estruturada
# □ pytest tests/test_pms/test_attribution.py -v


################################################################################
##                                                                            ##
##  ETAPA 8 — FRONTEND: DESIGN SYSTEM E ESTRUTURA BASE DO PMS                ##
##  Tempo: ~35 min | React app com design profissional                        ##
##                                                                            ##
################################################################################

══ INÍCIO DO PROMPT 8 ══

No projeto macro-fund-system (Etapas 1-7 da Fase 3 completas), configure o frontend PMS com design system profissional.

## Contexto de Design

O PMS deve ter aparência de terminal profissional de trading — dark theme, denso em informação, com hierarquia visual clara. Referência: Bloomberg Terminal (informação densa, eficiente), mas com UX moderna. Não deve parecer um dashboard genérico.

## 1. Configuração do projeto React (se não existir frontend/ da Fase 2, crie do zero)

```bash
# Se frontend/ já existe da Fase 2, apenas adicione dependências
cd frontend
npm install @tanstack/react-query recharts date-fns clsx tailwind-merge
npm install @radix-ui/react-dialog @radix-ui/react-tabs @radix-ui/react-tooltip
npm install react-hot-toast react-number-format
```

## 2. frontend/src/design-system/theme.ts

```typescript
// Paleta de cores: dark terminal profissional
export const colors = {
  // Backgrounds
  bg: {
    primary: "#0A0A0F",    // Fundo principal (quase preto)
    secondary: "#12121A",  // Cards e painéis
    tertiary: "#1A1A28",   // Nested elements
    elevated: "#1F1F2E",   // Modais e dropdowns
    border: "#2A2A3E",     // Bordas sutis
  },
  
  // Accent
  accent: {
    blue: "#3B82F6",       // Primary actions
    cyan: "#06B6D4",       // Highlights e links
    purple: "#8B5CF6",     // Secondary accent
  },
  
  // Semânticas de trading
  trading: {
    long: "#10B981",       // Verde: posição long / positivo
    short: "#EF4444",      // Vermelho: posição short / negativo
    neutral: "#6B7280",    // Cinza: neutro / flat
    warning: "#F59E0B",    // Amarelo: alertas
    critical: "#EF4444",   // Vermelho: crítico
  },
  
  // Texto
  text: {
    primary: "#E2E8F0",    // Texto principal
    secondary: "#94A3B8",  // Texto secundário
    muted: "#4B5563",      // Labels e legendas
    inverse: "#0A0A0F",    // Sobre backgrounds claros
  }
};

// Tipografia: monospace para números, sans para texto
export const typography = {
  mono: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
  sans: "'Inter', system-ui, sans-serif",
};
```

## 3. frontend/src/lib/api-client.ts

```typescript
import { QueryClient } from "@tanstack/react-query";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000/api/v1";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000,    // 30 segundos (dados de mercado)
      refetchInterval: 60 * 1000,  // Auto-refresh a cada 60s
      retry: 2,
    },
  },
});

export const pmsApi = {
  // Portfolio
  getBook: () => fetch(`${API_BASE}/pms/book`).then(r => r.json()),
  getPositions: (filters?: object) => /* ... */,
  openPosition: (data: object) => /* POST */,
  closePosition: (id: string, data: object) => /* POST */,
  markToMarket: (data: object) => /* POST */,
  
  // Trades
  getProposals: (status?: string) => /* ... */,
  approveProposal: (id: string, data: object) => /* POST */,
  rejectProposal: (id: string, data: object) => /* POST */,
  generateProposals: () => /* POST */,
  
  // Risk
  getLiveRisk: () => /* ... */,
  getPreTradeRisk: (data: object) => /* POST */,
  
  // Morning Pack
  getMorningPack: () => fetch(`${API_BASE}/pms/morning-pack/latest`).then(r => r.json()),
  
  // Attribution
  getAttribution: (params: object) => /* ... */,
  getEquityCurve: (params: object) => /* ... */,
  
  // Journal
  getJournal: (params: object) => /* ... */,
};
```

## 4. frontend/src/components/pms/ — Componentes Base

Crie os componentes reutilizáveis:

### MetricCard.tsx
```typescript
interface MetricCardProps {
  label: string;
  value: string | number;
  change?: number;       // % de mudança (positivo = verde, negativo = vermelho)
  changeLabel?: string;  // "vs ontem", "MTD", etc.
  format?: "currency" | "percent" | "number" | "bps";
  size?: "sm" | "md" | "lg";
  critical?: boolean;    // Borda vermelha se crítico
}
// Exibe valor com formatação automática, badge de mudança colorido
```

### SignalBadge.tsx
```typescript
// Badge para direção de sinal: LONG (verde), SHORT (vermelho), FLAT (cinza)
// Com conviction score como barra de progresso
```

### PriceDisplay.tsx
```typescript
// Número monospace com coloração por variação (+/-)
// Suporta: preço, taxa (%), bps, BRL, USD
```

### AlertBanner.tsx
```typescript
// Faixa de alerta: CRITICAL (vermelho), WARNING (amarelo), INFO (azul)
// Dismissível, com ícone
```

### DataTable.tsx
```typescript
// Tabela reutilizável com: sorting, filtering, row selection
// Células com formatação automática por tipo de dado
// Density: compact (terminal-style) e comfortable
```

### LoadingState.tsx e EmptyState.tsx
```typescript
// States padronizados para loading e dados vazios
```

## 5. frontend/src/App.tsx — Estrutura de Navegação

```typescript
// Layout: sidebar fixa à esquerda + header + conteúdo principal
// Sidebar com navegação por ícone + texto:
// 📋 Morning Pack
// 📊 Book de Posições
// 📝 Trade Blotter
// ⚠️ Risk Monitor
// 📈 Performance
// 🗒️ Decision Journal
// 🧠 Agent Intelligence
// ⚙️ Settings

// Header: logo + data atual + status do sistema + última atualização
```

## 6. Tailwind CSS configuração

Atualize `tailwind.config.js` com as cores customizadas do design system.

══ FIM DO PROMPT 8 ══

# VERIFICAÇÃO:
# □ npm run dev → http://localhost:3000 → layout base funcional
# □ Navegação entre seções funcional
# □ Design dark theme aplicado corretamente


################################################################################
##                                                                            ##
##  ETAPA 9 — FRONTEND: MORNING PACK PAGE                                     ##
##  Tempo: ~40 min | Tela de Daily Briefing                                   ##
##                                                                            ##
################################################################################

══ INÍCIO DO PROMPT 9 ══

No projeto macro-fund-system (Etapa 8 da Fase 3 completa — design system configurado), implemente a página Morning Pack.

## frontend/src/pages/MorningPackPage.tsx

Tela de Daily Briefing — primeira coisa que o gestor vê ao abrir o sistema.

### Layout (grid de 3 colunas em desktop):

**Coluna 1 — Macro Snapshot (largura: 1/3)**

```typescript
// Seção: RATES BRASIL
// Tabela compacta: Instrumento | Taxa | Δ1d | Δ5d | z-score
// Linhas: SELIC, DI Jan27, DI Jan29, DI Jan32, DI Jan35, NTN-B 2027, NTN-B 2035
// Formatação: taxas em %, variações em bps coloridas (verde/vermelho)

// Seção: CÂMBIO E GLOBAL
// Linhas: USDBRL, DXY, EUR/USD, VIX, EMBI BR, CDS 5Y BR
// Linhas: Fed Funds, UST 2Y, UST 10Y, Breakeven 10Y

// Seção: MACRO BRASIL
// Linhas: IPCA 12M, Focus IPCA Ano, Selic Atual, Focus Selic Ano, IBC-Br
```

**Coluna 2 — Agentes e Sinais (largura: 1/3)**

```typescript
// Seção: REGIME ASSESSMENT
// Card grande: regime atual (REFLATION / STAGFLATION / etc.)
// Com probabilidade (%) e seta de tendência

// Seção: AGENT VIEWS (5 mini-cards)
// Cada card: nome do agente, sinal principal, convicção (barra), 1 linha de texto
// Inflation | Monetary Policy | Fiscal | FX | Cross-Asset

// Seção: TOP SINAIS DO DIA
// Lista: top 5 sinais por convicção
// Ticker | Direção | Convicção | Estratégia | Mudança vs ontem
```

**Coluna 3 — Portfólio e Ações (largura: 1/3)**

```typescript
// Seção: ESTADO DO PORTFÓLIO
// Metrics: AUM, P&L Hoje, P&L MTD, VaR 95%, Leverage
// Cada métrica: valor + comparação com limite

// Seção: TRADE PROPOSALS (badge com contagem)
// Lista das proposals do dia: instrumento + direção + convicção
// Botão "Ver Blotter" para navegar ao Trade Blotter

// Seção: ACTION ITEMS
// Lista priorizada com ícones: 🔴 Critical, 🟡 Warning, 🔵 Info
// Cada item clicável navega para seção relevante

// Seção: ALERTAS ATIVOS
// AlertBanner para cada alerta ativo
```

**Área inferior — Narrativa Macro (largura: 100%)**

```typescript
// Card expansível com a narrativa gerada pelo LLM
// Header: "📝 Contexto Macro — {data}"
// Texto formatado com parágrafos
// Botão "Regenerar" (chama POST /morning-pack/generate)
// Timestamp: "Gerado às HH:MM"
```

### Comportamento:
- Auto-refresh a cada 5 minutos
- Botão "Atualizar" no header
- Estado de loading com skeleton
- Se dados de hoje não disponíveis: mostra botão "Gerar Morning Pack"
- Data switcher: botão para ver pack de datas anteriores

══ FIM DO PROMPT 9 ══

# VERIFICAÇÃO:
# □ http://localhost:3000 → Morning Pack carrega dados da API
# □ Todos os grupos de dados renderizando corretamente
# □ Narrativa macro exibida no rodapé


################################################################################
##                                                                            ##
##  ETAPA 10 — FRONTEND: BOOK DE POSIÇÕES                                    ##
##  Tempo: ~40 min | Tela do portfolio ao vivo                               ##
##                                                                            ##
################################################################################

══ INÍCIO DO PROMPT 10 ══

No projeto macro-fund-system (Etapa 9 da Fase 3 completa), implemente a página Book de Posições.

## frontend/src/pages/BookPage.tsx

### Header com KPIs do portfólio:

```typescript
// 6 MetricCards em linha:
// AUM Total | Gross Notional | Leverage (Gross/Net) | VaR 95% | P&L Hoje | P&L MTD
// Cada card: valor principal + variação percentual + indicador visual
// VaR: cor muda se próximo ao limite (>80% = amarelo, >95% = vermelho)
```

### Tabela Principal — Posições Abertas:

```typescript
// Colunas (ordenáveis):
// Ticker | Instrumento | Classe | Direção | Entry Date | Dias |
// Entry Price | Current Price | Notional (BRL) | P&L Hoje | P&L Total | P&L % |
// DV01/Delta | % VaR | Estratégias | Ações

// Formatação:
// Direção: badge LONG verde / SHORT vermelho
// P&L: positivo verde / negativo vermelho
// Dias: destacar posições com >30 dias (cor muted)
// % VaR: barra de progresso horizontal

// Row expansion (click para expandir):
// → Thesis do gestor | Signal rationale | Target price | Stop loss | Time horizon

// Ações por linha (inline buttons):
// [Fechar] → modal de closing com preço e notas
// [MTM] → modal para atualizar preço atual
// [Ver Journal] → filtra journal por essa posição
```

### Painel lateral — Summary por Asset Class:

```typescript
// Cards por asset class com total notional e P&L:
// RATES BR | FX BR | INFLATION BR | CUPOM | SOVEREIGN

// Gráfico Donut: distribuição por asset class (Recharts PieChart)
```

### Modal: Abrir Nova Posição (discricionária)

```typescript
// Form com campos:
// Ticker* | Instrumento | Asset Class* | Direção* (LONG/SHORT)
// Entry Date* | Entry Price* | Notional BRL* | Quantidade
// Estratégias (multi-select dos 22+ registrados)
// Tese do Gestor* (textarea — obrigatório)
// Target Price | Stop Loss | Time Horizon
// 
// Pré-trade risk preview (carrega via POST /risk/pre-trade ao inserir notional):
// "Impacto estimado: VaR +0.3%, Leverage: 2.1x → 2.4x"
```

### Modal: Fechar Posição

```typescript
// Close Price* | Close Date* | Manager Notes | Outcome Notes (lições aprendidas)
// Exibe P&L estimado antes de confirmar
```

### Modal: Mark-to-Market Manual

```typescript
// Para cada posição: campo de preço atual
// Bulk MTM: tabela com todos os tickers e preços editáveis
// Importação opcional: paste de CSV com {ticker, price}
```

══ FIM DO PROMPT 10 ══

# VERIFICAÇÃO:
# □ http://localhost:3000/book → tabela carrega posições da API
# □ Modal de abertura funciona e persiste via POST
# □ Modal de fechamento calcula P&L corretamente


################################################################################
##                                                                            ##
##  ETAPA 11 — FRONTEND: TRADE BLOTTER                                       ##
##  Tempo: ~40 min | Interface de revisão e aprovação de trades               ##
##                                                                            ##
################################################################################

══ INÍCIO DO PROMPT 11 ══

No projeto macro-fund-system (Etapa 10 da Fase 3 completa), implemente a página Trade Blotter.

## frontend/src/pages/TradeBlotterPage.tsx

Esta é a tela mais crítica operacionalmente — onde o gestor revisa e decide sobre os trade proposals do sistema.

### Header:

```typescript
// Badge: "X Proposals Pendentes" (pulsante se > 0)
// Botão: "Gerar Proposals" → POST /pms/trades/proposals/generate
// Filtros: Status (Todos | Pendentes | Aprovados | Rejeitados) | Data | Asset Class
```

### Seção 1: Proposals Pendentes (prioridade visual máxima)

```typescript
// Cards de proposal (não tabela — maior legibilidade):
// Um card por proposal, layout horizontal:
//
// ┌────────────────────────────────────────────────────────────┐
// │ 🟢 LONG  │  DI1F29 — DI Futuro Jan/2029                  │
// │ RATES_BR │  Notional: R$ 5.000.000  │  Convicção: 78%    │
// │          ├────────────────────────────────────────────────│
// │ Sistema: │  RATES_BR_02 (Taylor Rule Misalignment) +      │
// │          │  RATES_BR_01 (Carry & Roll-Down)               │
// │          ├────────────────────────────────────────────────│
// │ Impacto: │  VaR: 1.2% → 1.5%  │  Leverage: 2.1x → 2.4x │
// │          ├────────────────────────────────────────────────│
// │ Narrativa (expandível — gerada pelo LLM):                 │
// │ "O modelo Taylor Rule indica misalignment de +85bps..."   │
// │                                                            │
// │ [✅ Aprovar]  [✏️ Modificar]  [❌ Rejeitar]              │
// └────────────────────────────────────────────────────────────│

// Ordenado por convicção decrescente
// Máximo 5 cards visíveis (os mais urgentes)
```

### Modal: Aprovar Proposal

```typescript
// Pre-filled com dados do proposal, editáveis pelo gestor:
// Preço de Execução* | Notional Executado (pode diferir) | Data de Execução*
// Target Price | Stop Loss | Time Horizon (dropdown: "1-5 dias" | "1-4 semanas" | "1-3 meses")
// Tese do Gestor (textarea — pré-preenchida com narrativa do sistema, editável)
// Notas do Gestor (livre)
// 
// Preview: "Ao confirmar, abrirá posição LONG DI1F29 R$5M a 13.45%"
// Botão: [Confirmar Execução]
```

### Modal: Rejeitar Proposal

```typescript
// Campo obrigatório: Motivo da Rejeição (textarea)
// Quick-picks (chips): "Timing inadequado" | "Tamanho excessivo" | 
//                      "Já tenho exposição" | "Contra minha visão macro" | "Outro"
// Botão: [Registrar Rejeição]
```

### Seção 2: Histórico do Blotter (tabela compacta)

```typescript
// Tabela: Data | Ticker | Direção | Notional | Status | Preço Exec. | P&L Atual | Gestor
// Filtros: últimos 30d default
// Click na linha abre painel lateral com detalhes completos
```

### Painel de Estatísticas (sidebar direita)

```typescript
// Taxa de aprovação: X% dos proposals aprovados
// P&L médio por proposta aprovada: R$ X
// Proposals aprovados vs discricionários: donut chart
// Top 3 motivos de rejeição (últimos 30d)
```

══ FIM DO PROMPT 11 ══

# VERIFICAÇÃO:
# □ Proposals do sistema carregam em cards
# □ Modal de aprovação funciona e cria posição no book
# □ Modal de rejeição funciona com campo obrigatório


################################################################################
##                                                                            ##
##  ETAPA 12 — FRONTEND: RISK MONITOR                                         ##
##  Tempo: ~40 min | Painel de risco em tempo real                            ##
##                                                                            ##
################################################################################

══ INÍCIO DO PROMPT 12 ══

No projeto macro-fund-system (Etapa 11 da Fase 3 completa), implemente a página Risk Monitor.

## frontend/src/pages/RiskMonitorPage.tsx

### Faixa de Alertas (topo, full-width)

```typescript
// AlertBanner para cada alerta ativo (critical primeiro)
// Se sem alertas: faixa verde "✅ Todos os limites dentro do normal"
```

### Grid Principal (2 colunas):

**Coluna 1 — Gauges de Risco**

```typescript
// Componente: RiskGauge
// Gauge semicircular (Recharts RadialBarChart ou SVG customizado):
// 0% = verde | 80% = amarelo | 95% = vermelho
//
// Gauges exibidos:
// VaR 95%: {current}% do AUM  / limite: {limit}% → {utilization}% do limite
// VaR 99%: idem
// Gross Leverage: {current}x / limite {limit}x
// Drawdown Atual: {current}% / limite {limit}%
// Concentração RATES BR: {current}% / limite {limit}%
// Concentração FX BR: idem
```

**Coluna 2 — Histórico de VaR e Drawdown**

```typescript
// Recharts LineChart duplo:
// - VaR 95% histórico (linha azul) + limite (linha tracejada vermelha)
// - Drawdown histórico (área preenchida vermelha abaixo de 0)
// Período: últimos 252 dias úteis (1 ano)
// X-axis: datas | Y-axis: % do AUM
```

### Seção: Stress Tests

```typescript
// Tabela de cenários pré-definidos (6 da Fase 2):
// Cenário | Shock | P&L Estimado (BRL) | P&L Estimado (%) | Semáforo
//
// Cenários: COPOM +100bps, COPOM -100bps, BRL deprecia 10%,
//           BRL aprecia 10%, Crise EM (spreads +200bps), Recuo global (VIX +15)
//
// Botão: "Stress Test Customizado" → modal com shocks editáveis por ativo
```

### Seção: Concentração e Correlações

```typescript
// Heatmap de correlação entre posições (Recharts ou D3):
// Matriz N×N onde N = número de posições abertas
// Cor: azul escuro (-1) → branco (0) → vermelho escuro (+1)
// Alerta se correlação > 0.8 entre posições do mesmo lado (risco oculto)
//
// Pie chart: concentração por asset class (% do gross notional)
```

### Seção: Exposições Fatoriais

```typescript
// Tabela: Fator | Exposição | Unidade | Interpretação
// Duration total (anos) | DXY beta | Carry total (bps/ano)
// EM beta | Inflation sensitivity | Etc.
```

══ FIM DO PROMPT 12 ══

# VERIFICAÇÃO:
# □ Gauges renderizam com dados reais da API
# □ Chart de VaR histórico funcional
# □ Stress tests exibidos corretamente


################################################################################
##                                                                            ##
##  ETAPA 13 — FRONTEND: PERFORMANCE ATTRIBUTION                              ##
##  Tempo: ~40 min | Tela de análise de performance                           ##
##                                                                            ##
################################################################################

══ INÍCIO DO PROMPT 13 ══

No projeto macro-fund-system (Etapa 12 da Fase 3 completa), implemente a página Performance Attribution.

## frontend/src/pages/PerformancePage.tsx

### Header com Seletor de Período:

```typescript
// Pills: MTD | QTD | YTD | 6M | 1A | Personalizado (date picker)
// Benchmark toggle: vs CDI | vs IMA-B | vs IHFA | Sem benchmark
```

### Seção 1 — KPIs de Performance (6 cards)

```typescript
// Retorno Total (%) | Retorno Anualizado (%) | Volatilidade Anualizada (%)
// Sharpe Ratio | Max Drawdown (%) | Taxa de Acerto (%)
// Cada card com comparação vs benchmark selecionado
```

### Seção 2 — Equity Curve (full width)

```typescript
// Recharts LineChart:
// Linha 1: Portfólio (azul) — retorno acumulado
// Linha 2: Benchmark selecionado (cinza tracejado)
// Linha 3: Drawdown (área vermelha, escala à direita)
// X-axis: datas | Y-axis esquerda: retorno % | Y-axis direita: drawdown %
// Tooltip rico: data, equity, retorno acumulado, drawdown, benchmark
// Brush para zoom no período
```

### Seção 3 — Monthly Returns Heatmap

```typescript
// Grid anos × meses (Jan a Dez):
// Célula colorida: verde (retorno positivo) → vermelho (negativo)
// Intensidade proporcional ao retorno
// Hover: tooltip com retorno exato e P&L em BRL
// Coluna "Total Ano" e linha "Média Mensal"
```

### Seção 4 — Attribution por Dimensão (tabs)

```typescript
// Tab 1: Por Asset Class — Bar chart horizontal com P&L e % contribuição
// Tab 2: Por Estratégia — Bar chart + tabela com win rate, avg win/loss
// Tab 3: Por Posição — Tabela: top 10 ganhos e top 10 perdas
// Tab 4: Sistemático vs Discricionário — Donut + stats comparativos
```

### Seção 5 — Rolling Metrics

```typescript
// Recharts LineChart: Rolling Sharpe 63d + Rolling Vol 63d
// Annotation: linha horizontal no Sharpe = 1.0 (referência)
```

### Seção 6 — Trade Statistics

```typescript
// Tabela de estatísticas:
// Total de trades | Taxa de acerto | P&L médio por trade
// Melhor trade | Pior trade | Avg holding period (dias)
// Profit factor | Payoff ratio (avg win / avg loss)
```

══ FIM DO PROMPT 13 ══

# VERIFICAÇÃO:
# □ Equity curve renderiza com dados históricos
# □ Heatmap mensal funcional com cores
# □ Attribution tabs funcionam


################################################################################
##                                                                            ##
##  ETAPA 14 — FRONTEND: DECISION JOURNAL E AGENT INTELLIGENCE               ##
##  Tempo: ~35 min | Journal de decisões e hub de análise dos agentes         ##
##                                                                            ##
################################################################################

══ INÍCIO DO PROMPT 14 ══

No projeto macro-fund-system (Etapa 13 da Fase 3 completa), implemente as páginas Decision Journal e Agent Intelligence.

## 1. frontend/src/pages/JournalPage.tsx

### Timeline de Decisões

```typescript
// Layout: timeline vertical com cards de decisão
// Cada card:
// [Data] [Hora] | [Tipo: OPEN/CLOSE/REJECT] | [Ticker] | [Direção] | [Notional]
//
// Corpo expandível:
// → Tese do Gestor (destaque — campo mais importante)
// → Contexto macro no momento (snapshot pequeno)
// → Se proposta do sistema: comparação proposta vs executado
// → Target price | Stop loss | Time horizon
// → Se fechada: P&L realizado | Lições aprendidas
// → Timestamp e hash (para auditoria)
```

### Filtros e Busca:

```typescript
// Busca full-text na tese e notas
// Filtros: Data | Tipo | Asset Class | Status (aberto/fechado) | Estratégia
// Export: botão para exportar filtros atuais como CSV (compliance)
```

### Painel de Análise (sidebar):

```typescript
// Com as decisões filtradas atuais:
// Taxa de acerto | P&L médio | Holding period médio
// Gráfico: P&L por tipo de decisão
// Word cloud dos termos mais usados nas teses (opcional)
```

### Modal: Adicionar Nota ao Journal

```typescript
// Para decisões abertas: adicionar nota livre (não fecha, não altera)
// Campo: tipo de nota (UPDATE | THESIS_CHANGE | OBSERVATION)
// Texto livre
```

## 2. frontend/src/pages/AgentIntelligencePage.tsx

### Layout: 5 Cards de Agente (grid 3+2)

```typescript
// Cada card expandido:
// Header: [Nome do Agente] | [Última execução] | [Status: ativo]
//
// Sinais do agente: lista com direção colorida e convicção
// Modelos utilizados (Taylor Rule, Phillips Curve, etc.)
// Métricas-chave do modelo (valores numéricos atuais)
// Narrativa LLM (gerada pelo Cross-Asset ou pelo próprio agente)
// Badge: sinal mudou hoje? (NOVO / REFORÇADO / INVERTIDO / INALTERADO)
```

### Seção: Consensus View

```typescript
// Tabela: Asset Class | Sinal Consenso | Agentes de Acordo | Agentes em Conflito
// RATES BR: HAWKISH | Inflation ✅ Monetary ✅ | Fiscal ⚠️
// FX BR: BRL CHEAP | FX ✅ Cross-Asset ✅ | —
// Etc.
```

### Seção: Signal History (chart)

```typescript
// Recharts LineChart: evolução da convicção de cada agente nos últimos 60 dias
// Linha por agente | X-axis: datas | Y-axis: convicção [-1, +1]
// Tooltips com o sinal exato de cada data
```

### Seção: Divergências Detectadas

```typescript
// Lista de divergências: quando agentes conflitam
// "Inflation HAWKISH vs Monetary DOVISH — divergência desde {data}"
// Implicação: sinal agregado reduzido
```

══ FIM DO PROMPT 14 ══

# VERIFICAÇÃO:
# □ Journal exibe decisões em timeline
# □ Agent Intelligence mostra cards de todos os 5 agentes
# □ Consensus view renderiza corretamente


################################################################################
##                                                                            ##
##  ETAPA 15 — COMPLIANCE, AUDIT E SEGURANÇA                                 ##
##  Tempo: ~30 min | Infraestrutura de compliance para produção               ##
##                                                                            ##
################################################################################

══ INÍCIO DO PROMPT 15 ══

No projeto macro-fund-system (Etapas 1-14 da Fase 3 completas), implemente os módulos de compliance, auditoria e segurança da API.

## 1. src/compliance/audit.py

```python
class AuditLogger:
    """
    Dual-write audit logger: banco de dados + arquivo de log.
    Todos os eventos sensíveis são registrados com contexto completo.
    
    Eventos auditados:
    - POSITION_OPEN, POSITION_CLOSE, POSITION_MODIFY (todas as posições)
    - TRADE_APPROVED, TRADE_REJECTED, TRADE_MODIFIED
    - RISK_BREACH (qualquer limite violado)
    - EMERGENCY_STOP (se acionado)
    - API_AUTH_FAILURE, API_RATE_LIMIT
    - SYSTEM_STARTUP, SYSTEM_SHUTDOWN
    - MORNING_PACK_GENERATED
    - MTM_UPDATE
    """
    
    def __init__(self, db_session, log_file_path: str = "logs/audit.jsonl"):
        ...
    
    async def log_event(
        self,
        event_type: str,
        entity_type: str,    # "position" | "trade" | "system"
        entity_id: str,
        user: str,
        action: str,
        before_state: dict = None,  # Estado antes da mudança
        after_state: dict = None,   # Estado após a mudança
        metadata: dict = None,
        severity: str = "INFO"      # INFO | WARNING | CRITICAL
    ) -> str:
        """
        Registra evento no banco (tabela audit_log) e arquivo JSONL.
        Retorna ID do evento.
        Formato JSONL: uma linha JSON por evento, com timestamp ISO.
        """
        ...
    
    async def log_risk_breach(self, breach_type: str, value: float, limit: float, **kwargs):
        """Atalho para log de breaches de risco."""
        ...
    
    async def get_audit_trail(
        self,
        entity_id: str = None,
        event_type: str = None,
        start_date: date = None,
        end_date: date = None
    ) -> list[dict]:
        """Consulta trilha de auditoria com filtros."""
        ...
```

## 2. src/compliance/risk_controls.py

```python
class PreTradeRiskControls:
    """
    Verificações automáticas antes de registrar qualquer operação.
    Implementa os princípios de pre-trade compliance de fundos institucionais.
    """
    
    def __init__(self, risk_limits: PMSRiskLimits, position_manager):
        ...
    
    async def validate_trade(
        self,
        ticker: str,
        asset_class: str,
        direction: str,
        notional_brl: float,
        raise_on_hard_limit: bool = True
    ) -> dict:
        """
        Executa todas as verificações pre-trade.
        
        Checks:
        1. Fat finger: notional_brl < 0 ou > max_single_trade (configúrável, ex: R$50M)
        2. Leverage: gross leverage após trade < hard_limit
        3. Concentração: % by asset class após trade < limite
        4. VaR: VaR estimado após trade < limite
        5. Drawdown: não opera se drawdown > limite (protection mode)
        
        Returns: {
          "approved": bool,
          "checks": [{"name", "passed", "value", "limit", "message"}],
          "warnings": list[str],
          "hard_blocks": list[str]  # Motivos de bloqueio hard
        }
        """
        ...
    
    async def validate_notional(self, notional_brl: float, ticker: str) -> dict: ...
    async def validate_leverage_impact(self, notional_brl: float, direction: str) -> dict: ...
    async def validate_concentration(self, asset_class: str, notional_brl: float) -> dict: ...
    async def validate_var_impact(self, ...) -> dict: ...
```

## 3. src/api/auth.py — JWT Simples

```python
from fastapi.security import HTTPBearer
from jose import jwt

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-in-production")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 12

def create_token(username: str, role: str = "manager") -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

# Dependency: get_current_user
# Aplique em todos os endpoints PMS sensíveis (POST, PUT, DELETE)
# GET endpoints podem ser opcionalmente públicos para facilitar uso
```

## 4. src/api/middleware.py — Middleware de Segurança

```python
# Adicione ao FastAPI app:
# - CORSMiddleware (restrito ao domínio do frontend em produção)
# - TrustedHostMiddleware
# - Request logging middleware (loga todos os requests com user e timestamp)
# - Rate limit simples (100 req/min por IP, usando dict em memória)
```

## 5. src/trading/emergency_stop.py

```python
class EmergencyStopProcedure:
    """
    Procedimento de emergência documentado para o gestor.
    NÃO automatizado — requer confirmação explícita do gestor.
    Registra todas as ações no AuditLogger.
    """
    
    async def initiate(self, reason: str, manager_confirmation: str) -> dict:
        """
        Procedimento de emergência:
        1. Marca todas as posições para fechamento urgente (flag `needs_urgent_close`)
        2. Congela geração de novos proposals
        3. Gera relatório de todas as posições abertas com PLs
        4. Registra no AuditLogger com severity CRITICAL
        5. Retorna checklist de ações manuais para o gestor
        
        NÃO fecha posições automaticamente — apenas documenta e alerta.
        O gestor executa os fechamentos manualmente via Trade Blotter.
        """
        ...
```

## 6. API Endpoint de Compliance

```
GET /api/v1/compliance/audit-trail?entity_id=...&start=...
GET /api/v1/compliance/risk-controls/validate (pre-trade check)
POST /api/v1/compliance/emergency-stop
GET /api/v1/compliance/report?period=mtd (relatório compliance)
```

## 7. Tabela de Auditoria

Adicione migration para tabela `audit_log`:

```python
class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(UUID, PK)
    event_timestamp = Column(DateTime(timezone=True), nullable=False)
    event_type = Column(String(50), nullable=False)
    entity_type = Column(String(50))
    entity_id = Column(String(100))
    user = Column(String(100))
    action = Column(String(200))
    before_state = Column(JSON)
    after_state = Column(JSON)
    metadata = Column(JSON)
    severity = Column(String(20), default="INFO")
    ip_address = Column(String(50))
    session_id = Column(String(100))
    checksum = Column(String(64))  # Integridade
```

══ FIM DO PROMPT 15 ══

# VERIFICAÇÃO:
# □ alembic upgrade head → audit_log table criada
# □ Abrir posição via API → verificar entrada criada em audit_log
# □ Pre-trade check via POST /compliance/risk-controls/validate


################################################################################
##                                                                            ##
##  ETAPA 16 — PERFORMANCE OPTIMIZATION: REDIS CACHE                         ##
##  Tempo: ~20 min | Caching para dashboard responsivo                        ##
##                                                                            ##
################################################################################

══ INÍCIO DO PROMPT 16 ══

No projeto macro-fund-system (Etapa 15 da Fase 3 completa), implemente o Redis cache para o PMS.

## 1. src/cache/pms_cache.py

```python
class PMSCache:
    """
    Cache Redis para o Portfolio Management System.
    Estratégia: cache-aside com TTL diferenciado por tipo de dado.
    
    TTLs:
    - Morning Pack: 5 minutos (atualiza com o mercado)
    - Book de posições: 30 segundos (quase real-time)
    - Risk metrics: 60 segundos
    - Attribution: 5 minutos (cálculo pesado)
    - Signal data: 120 segundos
    - Historical series: 10 minutos
    """
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def get_book(self) -> dict | None: ...
    async def set_book(self, data: dict, ttl: int = 30): ...
    async def invalidate_book(self): ...
    
    async def get_morning_pack(self, date: str) -> dict | None: ...
    async def set_morning_pack(self, date: str, data: dict, ttl: int = 300): ...
    
    async def get_risk_metrics(self) -> dict | None: ...
    async def set_risk_metrics(self, data: dict, ttl: int = 60): ...
    
    async def get_attribution(self, period_key: str) -> dict | None: ...
    async def set_attribution(self, period_key: str, data: dict, ttl: int = 300): ...
    
    # Invalidação em cascata (quando posição é alterada, invalidar book + risk)
    async def invalidate_portfolio_data(self):
        """Invalida book, risk e attribution quando portfólio muda."""
        await asyncio.gather(
            self.invalidate_book(),
            self.redis.delete("pms:risk:live"),
            self.redis.delete("pms:attribution:*")  # pattern
        )
```

## 2. Aplique cache nos endpoints críticos

Em `src/api/routes/pms_portfolio.py` e `pms_risk.py`:

```python
@router.get("/book")
async def get_book(cache: PMSCache = Depends(get_cache), ...):
    # Try cache first
    cached = await cache.get_book()
    if cached:
        return {**cached, "cached": True, "cache_age_seconds": ...}
    
    # Compute
    result = await position_manager.get_book()
    await cache.set_book(result)
    return result
```

Invalide o cache nos endpoints de escrita (open_position, close_position, mtm).

## 3. TimescaleDB Continuous Aggregates para P&L

```sql
-- Aggregate diário de P&L do portfólio (para equity curve rápida)
CREATE MATERIALIZED VIEW IF NOT EXISTS portfolio_daily_pnl
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS day,
    SUM(daily_pnl_brl) AS total_pnl_brl,
    SUM(unrealized_pnl_brl) AS total_unrealized_pnl_brl,
    COUNT(DISTINCT position_id) AS open_positions
FROM position_pnl_history
GROUP BY day;

-- Refresh policy
SELECT add_continuous_aggregate_policy('portfolio_daily_pnl',
    start_offset => INTERVAL '30 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 hour');
```

## 4. WebSocket para live updates do book

Em `src/api/websocket.py` (Fase 2), adicione canal:

```python
# ws://localhost:8000/ws/pms/book → atualização do book a cada 30s
# ws://localhost:8000/ws/pms/alerts → alertas de risco em tempo real

@app.websocket("/ws/pms/book")
async def pms_book_ws(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            book = await position_manager.get_book()
            await websocket.send_json({"type": "book_update", "data": book})
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

══ FIM DO PROMPT 16 ══

# VERIFICAÇÃO:
# □ GET /api/v1/pms/book → header "cached: true" na segunda chamada
# □ Redis CLI: KEYS pms:* → mostra chaves criadas
# □ Continuous aggregate criado no TimescaleDB


################################################################################
##                                                                            ##
##  ETAPA 17 — DAGSTER INTEGRATION: PMS DAILY PIPELINE                       ##
##  Tempo: ~20 min | Orquestração do PMS no pipeline diário                   ##
##                                                                            ##
################################################################################

══ INÍCIO DO PROMPT 17 ══

No projeto macro-fund-system (Etapa 16 da Fase 3 completa), integre o PMS ao pipeline Dagster da Fase 2.

## 1. Novos Dagster assets em src/orchestration/pms_assets.py

```python
from dagster import asset, AssetIn, Output, MetadataValue

@asset(
    name="daily_mark_to_market",
    description="Mark-to-market de todas as posições abertas",
    deps=["market_data_refreshed"],  # Depende dos dados de mercado
    group_name="pms",
)
async def daily_mtm_asset(context) -> Output:
    """
    Executa MTM para todas as posições abertas usando os preços do dia.
    Prioridade: prices do market_data table → BACEN → preço anterior.
    """
    ...

@asset(
    name="daily_morning_pack",
    description="Geração do Morning Pack diário",
    deps=["daily_mark_to_market", "agent_signals_aggregated"],  # Após MTM e agentes
    group_name="pms",
)
async def morning_pack_asset(context) -> Output:
    """
    Gera o Morning Pack completo incluindo trade proposals do dia.
    Executar às 6:30 BRT (antes do mercado).
    """
    ...

@asset(
    name="trade_proposals_daily",
    description="Geração de trade proposals a partir dos sinais do dia",
    deps=["daily_morning_pack"],
    group_name="pms",
)
async def trade_proposals_asset(context) -> Output:
    """
    Gera proposals de trade para revisão do gestor.
    """
    ...

@asset(
    name="daily_risk_report",
    description="Relatório de risco diário do portfólio real",
    deps=["daily_mark_to_market"],
    group_name="pms",
)
async def risk_report_asset(context) -> Output:
    """
    Calcula VaR, stress tests e métricas de risco do portfólio real.
    Gera alertas se limites atingidos.
    """
    ...
```

## 2. Atualize o job principal em src/orchestration/jobs.py

```python
@job(name="daily_pms_pipeline")
def daily_pms_job():
    """
    Pipeline PMS diário — executa após o pipeline de dados e agentes:
    1. MTM das posições (6:00 BRT)
    2. Morning Pack geração (6:30 BRT)
    3. Trade proposals (6:35 BRT)
    4. Risk report (6:40 BRT)
    """
    mtm = daily_mark_to_market()
    pack = daily_morning_pack(mtm)
    proposals = trade_proposals_daily(pack)
    risk = daily_risk_report(mtm)
```

## 3. Schedule

```python
from dagster import ScheduleDefinition

pms_schedule = ScheduleDefinition(
    job=daily_pms_job,
    cron_schedule="0 6 * * 1-5",  # 6:00 BRT (9:00 UTC), dias úteis
    execution_timezone="America/Sao_Paulo",
)
```

## 4. Alertas via Dagster

Em caso de falha do pipeline PMS:
- Log de erro detalhado
- Alerta no AlertManager da Fase 2 (Slack/email)
- Notificação: "Morning Pack não gerado — verificar manualmente"

## 5. Sensor para alertas de risco em tempo real

```python
@sensor(job=risk_alert_job)
def risk_breach_sensor(context):
    """
    Verifica limites de risco a cada 5 minutos durante o horário de mercado.
    Dispara job de alerta se algum limite for atingido.
    """
    ...
```

══ FIM DO PROMPT 17 ══

# VERIFICAÇÃO:
# □ http://localhost:3001 (Dagster UI) → grupo "pms" visível com assets
# □ Trigger manual do daily_pms_pipeline → executa com sucesso
# □ Schedule configurado corretamente


################################################################################
##                                                                            ##
##  ETAPA 18 — GO-LIVE CHECKLIST E DISASTER RECOVERY                         ##
##  Tempo: ~20 min | Documentação operacional para produção                   ##
##                                                                            ##
################################################################################

══ INÍCIO DO PROMPT 18 ══

No projeto macro-fund-system (Etapas 1-17 da Fase 3 completas), crie a documentação de go-live.

## 1. docs/GOLIVE_CHECKLIST.md

Checklist completo adaptado para operação human-in-the-loop:

```markdown
# MACRO FUND PMS — GO-LIVE CHECKLIST

## PRÉ-REQUISITOS DE INFRAESTRUTURA
- [ ] TimescaleDB: conexão testada, dados até D-1 disponíveis
- [ ] Redis: conectado e respondendo (ping < 1ms)
- [ ] FastAPI: todos os endpoints respondendo (GET /health → 200)
- [ ] Frontend: build de produção servindo corretamente
- [ ] Dagster: pipeline PMS agendado e testado com dry-run
- [ ] Logs: diretório logs/ com permissão de escrita
- [ ] Backup: scripts/backup.sh testado e restauração validada

## CONFIGURAÇÃO DO PMS
- [ ] PMSRiskLimits configurados e revisados pelo gestor
- [ ] AUM inicial configurado (src/config/settings.py: FUND_AUM_BRL)
- [ ] JWT secret key configurado (variável de ambiente JWT_SECRET_KEY)
- [ ] Token de API Anthropic configurado (ANTHROPIC_API_KEY)
- [ ] Timezone configurado (America/Sao_Paulo)

## DADOS E QUALIDADE
- [ ] python scripts/verify_phase2.py → STATUS PASS
- [ ] Todas as séries-chave atualizadas (SELIC, DI, USDBRL, IPCA)
- [ ] Pelo menos 252 dias de dados de mercado disponíveis (para VaR histórico)
- [ ] Agentes rodaram com sucesso no último dia útil

## WORKFLOW DO GESTOR (TESTAR ANTES DO GO-LIVE)
- [ ] Abrir posição de teste: POST /api/v1/pms/book/positions/open
- [ ] Verificar entry no Decision Journal
- [ ] Executar MTM: POST /api/v1/pms/book/mtm
- [ ] Verificar P&L calculado corretamente
- [ ] Gerar Morning Pack: POST /api/v1/pms/morning-pack/generate
- [ ] Verificar proposals geradas
- [ ] Aprovar proposal de teste
- [ ] Verificar posição criada no book
- [ ] Rejeitar proposal de teste com nota
- [ ] Fechar posição de teste com P&L realizado
- [ ] Verificar trilha completa no AuditLog

## COMPLIANCE E SEGURANÇA
- [ ] Pre-trade checks funcionando (fat finger, VaR, concentration)
- [ ] AuditLogger gravando em banco E arquivo
- [ ] JWT autenticação funcionando nos endpoints POST
- [ ] Emergency stop documentado e procedimento revisado pelo gestor

## BACKUPS
- [ ] Backup automático configurado (scripts/backup.sh via cron)
- [ ] Último backup testado (restauração validada)
- [ ] DR_PLAYBOOK.md revisado

## MONITORAMENTO
- [ ] Grafana: 4 dashboards da Fase 2 + novo "PMS Overview"
- [ ] AlertManager: alertas de risco configurados
- [ ] Log rotation configurado (logs não crescem indefinidamente)
```

## 2. docs/runbooks/DR_PLAYBOOK.md

```markdown
# DISASTER RECOVERY PLAYBOOK

## Cenário 1: Banco de dados indisponível
Sintomas: API retorna 500, dashboard não carrega
Ações:
1. Verificar: docker compose ps timescaledb
2. Se parado: docker compose up timescaledb -d
3. Aguardar 30s, verificar: GET /health
4. Se corrompido: seguir procedimento de RESTORE abaixo

## Cenário 2: Redis indisponível
Sintomas: API mais lenta, erro em alguns endpoints
Ações:
1. docker compose up redis -d (cache stateless — sem perda de dados)
2. Verificar: GET /health/data-status

## Cenário 3: Posição incorreta registrada
Ações:
1. NÃO deletar o registro (imutabilidade)
2. POST /api/v1/pms/book/positions/{id}/close com preço de entrada
   (net zero — fecha pelo mesmo preço de entrada)
3. Adicionar nota no Journal explicando o erro
4. Abrir posição correta

## Cenário 4: P&L incorreto (preço errado no MTM)
Ações:
1. POST /api/v1/pms/book/positions/{id}/update-price com preço correto
2. POST /api/v1/pms/book/mtm para recalcular
3. Registrar correção no Journal

## PROCEDIMENTO DE RESTORE (TimescaleDB)
```bash
# Parar aplicação
docker compose stop api dagster

# Restaurar backup
bash scripts/restore.sh backup_YYYY-MM-DD.pgdump

# Verificar integridade
python scripts/verify_phase2.py

# Reiniciar
docker compose up -d
```
```

## 3. scripts/backup.sh e scripts/restore.sh

```bash
#!/bin/bash
# backup.sh: backup do TimescaleDB + export de logs de auditoria
DATE=$(date +%Y-%m-%d)
BACKUP_DIR="backups/${DATE}"
mkdir -p "$BACKUP_DIR"

# Dump do banco
docker compose exec timescaledb pg_dump -U macrofund macrofund | \
    gzip > "${BACKUP_DIR}/macrofund_${DATE}.pgdump.gz"

# Export do audit log (CSV)
docker compose exec timescaledb psql -U macrofund -c \
    "COPY audit_log TO STDOUT CSV HEADER" | \
    gzip > "${BACKUP_DIR}/audit_log_${DATE}.csv.gz"

echo "Backup completo: ${BACKUP_DIR}"
```

## 4. docs/OPERATIONAL_RUNBOOK.md — Rotina Diária do Gestor

```markdown
# ROTINA OPERACIONAL DIÁRIA

## 6:00 — Pré-Mercado
1. Verificar: Dagster rodou sem erros (UI Dagster ou email alert)
2. Abrir PMS → Morning Pack → revisar macro snapshot overnight
3. Revisar Trade Proposals do dia (aba Trade Blotter)
4. Verificar alertas de risco ativos

## 8:30 — Abertura de Mercado (BRT)
1. Executar MTM com preços da abertura (via UI ou POST /mtm)
2. Tomar decisões sobre proposals: aprovar, rejeitar ou modificar
3. Executar trades decididos (manualmente na corretora/banco)
4. Registrar execuções no sistema (preço real, notas)

## Intraday
1. Atualizar preços se movimentos relevantes (MTM manual)
2. Verificar Risk Monitor se mercado volátil
3. Adicionar notas ao Journal se relevante

## 17:30 — Fechamento de Mercado
1. MTM com preços de fechamento
2. Revisar P&L do dia
3. Verificar Risk Monitor pós-fechamento
4. Atualizar thesis de posições se necessário
```

══ FIM DO PROMPT 18 ══

# VERIFICAÇÃO:
# □ docs/GOLIVE_CHECKLIST.md completo
# □ bash scripts/backup.sh → executa sem erros
# □ docs/runbooks/DR_PLAYBOOK.md revisado


################################################################################
##                                                                            ##
##  ETAPA 19 — VERIFICATION SCRIPT FASE 3                                    ##
##  Tempo: ~20 min | Verificação automática completa                          ##
##                                                                            ##
################################################################################

══ INÍCIO DO PROMPT 19 ══

No projeto macro-fund-system (Etapas 1-18 da Fase 3 completas), crie o script de verificação final.

## scripts/verify_phase3.py

```python
#!/usr/bin/env python3
"""
Verificação completa da Fase 3 — Portfolio Management System.
Verifica todos os componentes implementados.
"""

def verify_phase3():
    print("═" * 60)
    print(" MACRO FUND — PHASE 3 VERIFICATION (PMS)")
    print("═" * 60)
    
    checks = []
    
    # 1. Database — novas tabelas PMS
    checks += [
        check_table_exists("portfolio_positions"),
        check_table_exists("trade_proposals"),
        check_table_exists("decision_journal"),
        check_table_exists("daily_briefings"),
        check_table_exists("position_pnl_history"),
        check_table_exists("audit_log"),
        check_hypertable("position_pnl_history"),
    ]
    
    # 2. PMS Services
    checks += [
        check_module_importable("src.pms.position_manager", "PositionManager"),
        check_module_importable("src.pms.trade_workflow", "TradeWorkflowService"),
        check_module_importable("src.pms.morning_pack", "MorningPackService"),
        check_module_importable("src.pms.risk_monitor", "PMSRiskMonitor"),
        check_module_importable("src.pms.attribution", "PerformanceAttributionEngine"),
    ]
    
    # 3. Compliance & Security
    checks += [
        check_module_importable("src.compliance.audit", "AuditLogger"),
        check_module_importable("src.compliance.risk_controls", "PreTradeRiskControls"),
        check_module_importable("src.api.auth", "create_token"),
        check_file_exists("src/trading/emergency_stop.py"),
    ]
    
    # 4. API Endpoints (se API estiver rodando)
    api_running = check_api_running()
    if api_running:
        checks += [
            check_endpoint("GET", "/api/v1/pms/book"),
            check_endpoint("GET", "/api/v1/pms/trades/proposals"),
            check_endpoint("GET", "/api/v1/pms/morning-pack/latest"),
            check_endpoint("GET", "/api/v1/pms/risk/live"),
            check_endpoint("GET", "/api/v1/pms/attribution"),
            check_endpoint("GET", "/api/v1/pms/journal/"),
            check_endpoint("GET", "/api/v1/compliance/audit-trail"),
        ]
    
    # 5. Frontend
    checks += [
        check_file_exists("frontend/src/pages/MorningPackPage.tsx"),
        check_file_exists("frontend/src/pages/BookPage.tsx"),
        check_file_exists("frontend/src/pages/TradeBlotterPage.tsx"),
        check_file_exists("frontend/src/pages/RiskMonitorPage.tsx"),
        check_file_exists("frontend/src/pages/PerformancePage.tsx"),
        check_file_exists("frontend/src/pages/JournalPage.tsx"),
        check_file_exists("frontend/src/pages/AgentIntelligencePage.tsx"),
    ]
    
    # 6. Dagster PMS Assets
    checks += [
        check_module_importable("src.orchestration.pms_assets", "daily_mtm_asset"),
        check_module_importable("src.orchestration.pms_assets", "morning_pack_asset"),
    ]
    
    # 7. Documentation
    checks += [
        check_file_exists("docs/GOLIVE_CHECKLIST.md"),
        check_file_exists("docs/runbooks/DR_PLAYBOOK.md"),
        check_file_exists("docs/OPERATIONAL_RUNBOOK.md"),
        check_file_exists("scripts/backup.sh"),
    ]
    
    # 8. Tests
    test_result = run_pms_tests()
    checks.append(test_result)
    
    # Report
    print_report(checks)
    
    passed = sum(1 for c in checks if c["passed"])
    total = len(checks)
    
    print(f"\n{'═' * 60}")
    if passed == total:
        print(f" STATUS: ✅ PASS ({passed}/{total})")
        print(" Macro Fund PMS — pronto para produção!")
    else:
        print(f" STATUS: ❌ FAIL ({passed}/{total} passaram)")
    print("═" * 60)
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    exit(verify_phase3())
```

## Adicione ao Makefile:

```makefile
# Fase 3 — PMS
verify-pms:
    python scripts/verify_phase3.py

pms-api:
    uvicorn src.api.main:app --reload --port 8000

pms-dev:
    docker compose up -d && make pms-api &
    cd frontend && npm run dev

backup:
    bash scripts/backup.sh

morning-pack:
    python -c "import asyncio; from src.pms.morning_pack import MorningPackService; ..."
```

══ FIM DO PROMPT 19 ══

# VERIFICAÇÃO:
# □ python scripts/verify_phase3.py → STATUS: PASS
# □ make verify-pms → executa sem erros


################################################################################
##                                                                            ##
##  ETAPA 20 — GIT COMMIT FINAL E DOCUMENTAÇÃO                               ##
##  Tempo: ~15 min | Finalização da Fase 3                                   ##
##                                                                            ##
################################################################################

══ INÍCIO DO PROMPT 20 ══

No projeto macro-fund-system (Etapas 1-19 da Fase 3 completas), finalize e documente o projeto.

## 1. Atualize README.md com seção Fase 3

```markdown
## Phase 3: Portfolio Management System (PMS)

### Visão Geral
Sistema de portfolio management para operação human-in-the-loop, onde o gestor 
revisa e executa manualmente todos os trades com suporte analítico completo do sistema.

### Telas do PMS
| Tela | Descrição |
|------|-----------|
| 📋 Morning Pack | Daily briefing com macro snapshot, sinais, portfolio e action items |
| 📊 Book de Posições | Portfolio ao vivo com P&L e métricas de risco por posição |
| 📝 Trade Blotter | Revisão e aprovação de trade proposals gerados pelo sistema |
| ⚠️ Risk Monitor | VaR, stress tests, limites e exposições em tempo real |
| 📈 Performance | Equity curve, attribution, heatmap mensal e estatísticas |
| 🗒️ Decision Journal | Log auditável de todas as decisões do gestor |
| 🧠 Agent Intelligence | Sinais e narrativas dos 5 agentes analíticos |

### Workflow Operacional
```
Sistema gera trade proposal (6:30 BRT)
         ↓
Gestor revisa no Trade Blotter
         ↓
Gestor decide: Aprovar / Rejeitar / Modificar
         ↓ (se aprovado)
Gestor executa manualmente na corretora
         ↓
Gestor registra preço de execução no sistema
         ↓
Sistema atualiza book, risco e journal automaticamente
```

### Componentes Principais
- **PositionManager**: ciclo de vida de posições, MTM, P&L
- **TradeWorkflowService**: geração e aprovação de proposals
- **MorningPackService**: daily briefing com narrativa LLM
- **PMSRiskMonitor**: VaR, stress tests, pré-trade analytics
- **PerformanceAttributionEngine**: Brinson-Hood-Beebower, rolling metrics
- **AuditLogger**: dual-write, compliance, imutabilidade
- **PreTradeRiskControls**: fat finger, leverage, concentration checks

### Comandos
```bash
make verify-pms       # Verificação completa Fase 3
make pms-dev          # Inicia backend + frontend em desenvolvimento
make morning-pack     # Gera morning pack manualmente
make backup           # Backup do banco e audit logs
```
```

## 2. Git commit e tag

```bash
git add -A
git commit -m "Phase 3: Portfolio Management System (PMS) — human-in-the-loop

- 7 telas React: Morning Pack, Book, Trade Blotter, Risk Monitor,
  Performance, Decision Journal, Agent Intelligence
- Position Manager com MTM e P&L em tempo real
- Trade Workflow: proposals → review → approve/reject → execute
- Risk Monitor: VaR live, stress tests, pre-trade analytics
- Performance Attribution: equity curve, heatmap, Brinson-Hood-Beebower
- Morning Pack com narrativa LLM (Claude API)
- Compliance: AuditLogger dual-write, PreTradeRiskControls, EmergencyStop
- Redis cache com TTL diferenciado
- Dagster pipeline PMS: MTM, morning pack, proposals, risk report
- Go-live checklist, DR playbook, operational runbook
- JWT auth, rate limiting, CORS security middleware"

git tag -a v3.0.0 -m "Macro Fund AI System — Fase 3 completa (PMS)"
git push origin main --tags
```

## 3. Atualização final do Makefile

```makefile
.PHONY: all verify verify-pms pms-dev morning-pack backup

all: verify verify-pms

verify:
    python scripts/verify_phase2.py

verify-pms:
    python scripts/verify_phase3.py

pms-dev:
    docker compose up -d
    uvicorn src.api.main:app --reload &
    cd frontend && npm run dev

morning-pack:
    python -m src.pms.cli generate-morning-pack

backup:
    bash scripts/backup.sh

restore:
    bash scripts/restore.sh $(FILE)
```

══ FIM DO PROMPT 20 ══

# VERIFICAÇÃO FINAL:
# □ python scripts/verify_phase3.py → STATUS: ✅ PASS
# □ python scripts/verify_phase2.py → STATUS: ✅ PASS (regressão)
# □ git log --oneline → 3 commits: Fase 0 + Fases 1-2 + Fase 3
# □ git tag → v3.0.0 criado
# □ http://localhost:3000 → todas as 7 telas do PMS funcionais
# □ http://localhost:8000/docs → seções PMS com todos os endpoints


################################################################################
##                                                                            ##
##  ══════════════════════════════════════════════════════════════════════    ##
##  FIM DA FASE 3 — PORTFOLIO MANAGEMENT SYSTEM                              ##
##  ══════════════════════════════════════════════════════════════════════    ##
##                                                                            ##
##  CONSTRUÍDO:                                                               ##
##  ✅ 6 novos schemas de banco (TimescaleDB + PostgreSQL)                   ##
##  ✅ PositionManager: ciclo de vida completo de posições                   ##
##  ✅ TradeWorkflowService: human-in-the-loop com auditoria total           ##
##  ✅ 20+ novos endpoints API (Portfolio, Trades, Journal, Risk)            ##
##  ✅ MorningPackService: daily briefing com LLM (Claude API)               ##
##  ✅ PMSRiskMonitor: VaR live, stress tests, pre-trade analytics           ##
##  ✅ PerformanceAttributionEngine: multi-dimensional, Brinson-Hood-Beebower##
##  ✅ 7 telas React profissionais (dark terminal design)                    ##
##  ✅ AuditLogger dual-write + PreTradeRiskControls + EmergencyStop        ##
##  ✅ Redis cache com TTL diferenciado por tipo de dado                     ##
##  ✅ Dagster PMS pipeline: MTM → Morning Pack → Proposals → Risk          ##
##  ✅ Go-live checklist + DR Playbook + Operational Runbook                 ##
##  ✅ JWT auth + rate limiting + CORS security                              ##
##                                                                            ##
##  SISTEMA COMPLETO — PRONTO PARA OPERAÇÃO COM CAPITAL REAL                 ##
##                                                                            ##
##  Fases concluídas:                                                         ##
##  ✅ Fase 0: Infraestrutura de dados (11 conectores, 200+ séries)          ##
##  ✅ Fases 1+2: 5 agentes, 22+ estratégias, risk engine, backtesting       ##
##  ✅ Fase 3: Portfolio Management System (human-in-the-loop)               ##
##                                                                            ##
################################################################################

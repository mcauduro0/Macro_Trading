# ═══════════════════════════════════════════════════════════════════════
# MACRO HEDGE FUND AI SYSTEM — GUIA COMPLETO CLAUDE CODE
# ═══════════════════════════════════════════════════════════════════════
# FASE 2: STRATEGY ENGINE, RISK & PORTFOLIO MANAGEMENT (18 ETAPAS)
# ═══════════════════════════════════════════════════════════════════════
#
# COMO USAR:
# 1. Cada ETAPA é um prompt independente para o Claude Code
# 2. Copie o bloco entre as linhas "═══ INÍCIO DO PROMPT ═══" e "═══ FIM DO PROMPT ═══"
# 3. Cole no Claude Code e aguarde execução completa
# 4. Valide o resultado antes de ir para a próxima etapa
# 5. Se houver erro, cole o erro no Claude Code e peça correção
#
# PRÉ-REQUISITOS:
# - Fase 0 completa (Data Infrastructure: TimescaleDB, 200+ séries, 11 conectores, FastAPI)
# - Fase 1 completa (Quant Models: 5 agentes, Backtesting Engine, 8 estratégias, Dashboard React)
# - Docker + Docker Compose rodando (make up)
# - Banco populado (make verify → PASS)
# - API rodando (http://localhost:8000/docs)
# - Dashboard rodando (http://localhost:3000)
#
# O QUE SERÁ CONSTRUÍDO NESTA FASE:
# ✦ 17 estratégias adicionais (completando ~25 estratégias totais)
# ✦ Cross-Asset Agent com regime detection
# ✦ NLP Pipeline para comunicações de Bancos Centrais (COPOM + FOMC)
# ✦ Risk Engine completo (VaR, CVaR, stress testing, margin)
# ✦ Portfolio Construction & Optimization (risk parity, Black-Litterman)
# ✦ Signal Aggregation Layer
# ✦ Production Orchestration (Dagster DAGs)
# ✦ Alerting & Monitoring (Grafana + alertas)
# ✦ Verificação end-to-end Fase 2
#
# TEMPO TOTAL ESTIMADO: 12-18 horas de trabalho
# ═══════════════════════════════════════════════════════════════════════


################################################################################
##                                                                            ##
##  ETAPA 1 — STRATEGY BASE CLASSES & SIGNAL SCHEMA                          ##
##  Tempo: ~25 min | Framework para todas as estratégias                      ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 1 ═══

No projeto macro-fund-system, implemente o framework base para estratégias em src/strategies/. Este framework será usado por todas as ~25 estratégias do sistema. Siga estas instruções com precisão:

## 1. src/strategies/base.py — BaseStrategy (classe abstrata)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional

class SignalDirection(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"

class AssetClass(Enum):
    FX = "FX"
    RATES_BR = "RATES_BR"
    RATES_US = "RATES_US"
    INFLATION_BR = "INFLATION_BR"
    INFLATION_US = "INFLATION_US"
    CUPOM_CAMBIAL = "CUPOM_CAMBIAL"
    SOVEREIGN_CREDIT = "SOVEREIGN_CREDIT"
    CROSS_ASSET = "CROSS_ASSET"

class SignalStrength(Enum):
    STRONG = "STRONG"       # z-score > 2.0 ou confiança > 80%
    MODERATE = "MODERATE"   # z-score 1.0-2.0 ou confiança 50-80%
    WEAK = "WEAK"           # z-score 0.5-1.0 ou confiança 30-50%
    NEUTRAL = "NEUTRAL"     # z-score < 0.5 ou confiança < 30%

@dataclass
class StrategySignal:
    """Output padronizado de cada estratégia."""
    strategy_id: str
    timestamp: datetime
    direction: SignalDirection
    strength: SignalStrength
    confidence: float              # 0.0 a 1.0
    z_score: float                 # z-score do sinal vs. história
    raw_value: float               # valor cru do modelo
    suggested_size: float          # tamanho sugerido em unidades de risco (0.0 a 1.0)
    asset_class: AssetClass
    instruments: list[str]         # tickers dos instrumentos a operar
    entry_level: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    holding_period_days: Optional[int] = None
    metadata: dict = field(default_factory=dict)  # dados adicionais do modelo

@dataclass
class BacktestResult:
    """Resultado de backtest de uma estratégia."""
    strategy_id: str
    start_date: date
    end_date: date
    total_return: float            # retorno total (decimal: 0.15 = 15%)
    annualized_return: float
    annualized_vol: float
    sharpe_ratio: float
    max_drawdown: float            # negativo: -0.15 = -15%
    calmar_ratio: float
    win_rate: float
    profit_factor: float
    avg_holding_days: float
    num_trades: int
    daily_returns: list[float]     # série de retornos diários
    monthly_returns: list[float]   # série de retornos mensais
    drawdown_series: list[float]
    metadata: dict = field(default_factory=dict)
```

### BaseStrategy (ABC):

```python
class BaseStrategy(ABC):
    def __init__(self, strategy_id: str, asset_class: AssetClass, 
                 instruments: list[str], params: dict = None):
        self.strategy_id = strategy_id
        self.asset_class = asset_class
        self.instruments = instruments
        self.params = params or self.default_params()
        self._validate_params()
    
    @abstractmethod
    def default_params(self) -> dict:
        """Retorna parâmetros default da estratégia."""
        ...
    
    @abstractmethod
    async def compute_signal(self, as_of_date: date) -> StrategySignal:
        """Calcula sinal para uma data específica (point-in-time)."""
        ...
    
    @abstractmethod
    async def compute_signal_history(self, start_date: date, end_date: date) -> list[StrategySignal]:
        """Calcula sinais para período inteiro (para backtest)."""
        ...
    
    def _validate_params(self):
        """Valida parâmetros contra default_params keys."""
        defaults = self.default_params()
        for key in self.params:
            if key not in defaults:
                raise ValueError(f"Parâmetro desconhecido: {key}")
    
    async def get_data(self, series_ids: list[str], start_date: date, 
                       end_date: date, point_in_time: bool = True) -> dict:
        """Busca dados do banco respeitando point-in-time."""
        ...
    
    def compute_z_score(self, value: float, history: list[float], 
                        window: int = 252) -> float:
        """Calcula z-score rolling."""
        ...
    
    def size_from_conviction(self, z_score: float, max_size: float = 1.0) -> float:
        """Mapeia z-score para tamanho. Sigmoid truncado."""
        ...
    
    def classify_strength(self, z_score: float) -> SignalStrength:
        """Classifica força do sinal baseado no z-score."""
        ...
```

## 2. src/strategies/registry.py — Strategy Registry

```python
class StrategyRegistry:
    """Registry central de todas as estratégias."""
    _strategies: dict[str, type[BaseStrategy]] = {}
    
    @classmethod
    def register(cls, strategy_id: str):
        """Decorator para registrar estratégia."""
        def decorator(strategy_class):
            cls._strategies[strategy_id] = strategy_class
            return strategy_class
        return decorator
    
    @classmethod
    def get(cls, strategy_id: str) -> type[BaseStrategy]:
        ...
    
    @classmethod
    def list_all(cls) -> list[str]:
        ...
    
    @classmethod
    def list_by_asset_class(cls, asset_class: AssetClass) -> list[str]:
        ...
    
    @classmethod
    def instantiate(cls, strategy_id: str, params: dict = None) -> BaseStrategy:
        ...
    
    @classmethod
    def instantiate_all(cls) -> list[BaseStrategy]:
        ...
```

## 3. src/core/models/strategy_state.py — Tabela `strategy_state`

Nova tabela para persistir estado das estratégias:

```
id: UUID, PK
strategy_id: String(50), NOT NULL, indexed
timestamp: DateTime(timezone=True), NOT NULL
direction: String(10), NOT NULL — LONG, SHORT, FLAT
strength: String(10), NOT NULL
confidence: Float, NOT NULL
z_score: Float
raw_value: Float
suggested_size: Float
instruments: JSON — lista de tickers
entry_level: Float, nullable
stop_loss: Float, nullable
take_profit: Float, nullable
holding_period_days: Integer, nullable
metadata_json: JSON, nullable
created_at: DateTime(timezone=True), server_default=now()
```
Index: (strategy_id, timestamp DESC). Não é hypertable (volume baixo).

## 4. src/core/models/backtest_results.py — Tabela `backtest_results`

```
id: UUID, PK
strategy_id: String(50), NOT NULL, indexed
run_timestamp: DateTime(timezone=True), NOT NULL
start_date: Date, NOT NULL
end_date: Date, NOT NULL
params_json: JSON — parâmetros usados
total_return: Float
annualized_return: Float
annualized_vol: Float
sharpe_ratio: Float
max_drawdown: Float
calmar_ratio: Float
win_rate: Float
profit_factor: Float
avg_holding_days: Float
num_trades: Integer
daily_returns_json: JSON — array de retornos diários
metadata_json: JSON
created_at: DateTime(timezone=True), server_default=now()
```

## 5. Gere Alembic migration:

```bash
alembic revision --autogenerate -m "add_strategy_state_and_backtest_results"
alembic upgrade head
```

## 6. src/strategies/__init__.py

Import BaseStrategy, StrategySignal, BacktestResult, StrategyRegistry, todos os enums.

## 7. Tests: tests/test_strategies/test_base.py

- Test StrategySignal dataclass creation
- Test SignalDirection, SignalStrength enums
- Test BaseStrategy._validate_params raises ValueError para parâmetros inválidos
- Test compute_z_score com dados conhecidos
- Test size_from_conviction retorna 0 para z=0, ~1 para z>>2
- Test classify_strength para cada range

═══ FIM DO PROMPT 1 ═══

# VERIFICAÇÃO:
# □ pytest tests/test_strategies/test_base.py -v
# □ alembic upgrade head (migration funcional)
# □ make psql → \dt (tabelas strategy_state e backtest_results existem)


################################################################################
##                                                                            ##
##  ETAPA 2 — BACKTESTING ENGINE v2 (PORTFOLIO-LEVEL)                        ##
##  Tempo: ~30 min | Engine de backtest multi-estratégia com custos           ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 2 ═══

No projeto macro-fund-system, implemente o Backtesting Engine v2 em src/strategies/backtesting/. Este engine deve suportar backtesting de múltiplas estratégias simultaneamente com alocação de risco, custos de transação e restrições de portfolio.

Referências acadêmicas: Lopez de Prado (2018) "Advances in Financial Machine Learning" — Cap. 10-12 sobre backtesting robusto; Harvey, Liu & Zhu (2016) sobre múltiplos testes e haircut de Sharpe.

## 1. src/strategies/backtesting/__init__.py

## 2. src/strategies/backtesting/engine.py — BacktestEngine

```python
@dataclass
class BacktestConfig:
    start_date: date
    end_date: date
    initial_capital: float = 100_000_000  # USD 100M AUM
    transaction_cost_bps: float = 2.0     # custo por trade (basis points)
    slippage_bps: float = 1.0             # slippage estimado
    funding_rate: float = 0.05            # custo de carry do capital
    max_leverage: float = 3.0             # alavancagem máxima total
    rebalance_frequency: str = "DAILY"    # DAILY, WEEKLY, MONTHLY
    point_in_time: bool = True            # CRÍTICO: usar dados point-in-time
    walk_forward: bool = False            # walk-forward validation
    walk_forward_train_months: int = 60   # 5 anos de treino
    walk_forward_test_months: int = 12    # 1 ano de teste

class BacktestEngine:
    def __init__(self, config: BacktestConfig):
        self.config = config
    
    async def run_single(self, strategy: BaseStrategy) -> BacktestResult:
        """Backtest de uma estratégia individual."""
        # 1. Gera sinais para o período inteiro (point-in-time)
        # 2. Converte sinais em posições (com delay de execução T+1)
        # 3. Calcula PnL diário: posição * retorno do instrumento
        # 4. Subtrai custos de transação nos dias de rebalanceamento
        # 5. Calcula métricas: Sharpe, drawdown, win rate, etc.
        ...
    
    async def run_portfolio(self, strategies: list[BaseStrategy], 
                            weights: dict[str, float] = None) -> BacktestResult:
        """Backtest multi-estratégia com alocação de risco."""
        # 1. Roda cada estratégia individualmente
        # 2. Aplica pesos (equal weight se não especificado)
        # 3. Respeita max_leverage constraint
        # 4. Calcula PnL portfolio-level
        # 5. Calcula correlação entre estratégias
        ...
    
    async def walk_forward_validation(self, strategy: BaseStrategy) -> list[BacktestResult]:
        """Walk-forward out-of-sample validation."""
        # Divide período em janelas train/test
        # Para cada janela:
        #   1. Otimiza parâmetros no train
        #   2. Roda backtest no test (out-of-sample)
        # Retorna lista de resultados por janela
        ...
    
    def compute_metrics(self, daily_returns: list[float], 
                        daily_positions: list[float]) -> BacktestResult:
        """Calcula todas as métricas de performance."""
        ...
    
    def deflated_sharpe(self, sharpe: float, n_trials: int, 
                        skew: float, kurtosis: float, 
                        n_observations: int) -> float:
        """Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014).
        Ajusta Sharpe para múltiplos testes."""
        ...
    
    def save_results(self, result: BacktestResult):
        """Persiste resultados na tabela backtest_results."""
        ...
```

## 3. src/strategies/backtesting/costs.py — Modelo de Custos

```python
class TransactionCostModel:
    """Modelo de custos de transação por instrumento."""
    
    # Custos típicos em bps (one-way)
    COST_TABLE = {
        "DI1": {"spread": 0.5, "commission": 0.3, "exchange_fee": 0.2},     # DI futuro B3
        "DDI": {"spread": 1.0, "commission": 0.3, "exchange_fee": 0.2},     # DDI futuro B3
        "DOL": {"spread": 0.3, "commission": 0.3, "exchange_fee": 0.2},     # Dólar futuro B3
        "USDBRL_NDF": {"spread": 2.0, "commission": 0.0, "exchange_fee": 0.0},  # NDF OTC
        "NTN_B": {"spread": 3.0, "commission": 0.0, "exchange_fee": 0.0},   # NTN-B OTC
        "LTN": {"spread": 1.5, "commission": 0.0, "exchange_fee": 0.0},     # LTN OTC
        "UST": {"spread": 0.5, "commission": 0.1, "exchange_fee": 0.0},     # US Treasuries
        "ZN": {"spread": 0.3, "commission": 0.5, "exchange_fee": 0.3},      # 10Y futures CME
        "ZF": {"spread": 0.3, "commission": 0.5, "exchange_fee": 0.3},      # 5Y futures CME
        "ES": {"spread": 0.2, "commission": 0.5, "exchange_fee": 0.3},      # S&P futures CME
        "CDS_BR": {"spread": 5.0, "commission": 0.0, "exchange_fee": 0.0},  # CDS soberano
        "IBOV_FUT": {"spread": 1.0, "commission": 0.3, "exchange_fee": 0.2},
    }
    
    def get_cost(self, instrument: str, notional: float, 
                 is_entry: bool = True) -> float:
        """Retorna custo total em USD para um trade."""
        ...
    
    def get_cost_bps(self, instrument: str) -> float:
        """Retorna custo total em bps (one-way)."""
        ...
```

## 4. src/strategies/backtesting/analytics.py — Funções Analíticas

```python
def compute_sharpe(returns: np.ndarray, risk_free_rate: float = 0.0, 
                   annualize: bool = True) -> float:
    """Sharpe ratio com anualização correta (√252 para daily)."""
    ...

def compute_sortino(returns: np.ndarray, target: float = 0.0) -> float:
    """Sortino ratio — penaliza apenas downside vol."""
    ...

def compute_max_drawdown(returns: np.ndarray) -> tuple[float, int, int]:
    """Max drawdown, índice do peak, índice do trough."""
    ...

def compute_calmar(returns: np.ndarray) -> float:
    """Calmar ratio = annualized return / |max drawdown|."""
    ...

def compute_information_ratio(returns: np.ndarray, benchmark: np.ndarray) -> float:
    """Information ratio vs benchmark."""
    ...

def compute_hit_rate(returns: np.ndarray) -> float:
    """Percentual de dias/trades positivos."""
    ...

def compute_profit_factor(returns: np.ndarray) -> float:
    """Soma dos ganhos / soma das perdas (absoluto)."""
    ...

def compute_tail_ratio(returns: np.ndarray, quantile: float = 0.05) -> float:
    """|p95| / |p05| — mede assimetria das caudas."""
    ...

def compute_turnover(positions: np.ndarray) -> float:
    """Turnover médio diário."""
    ...

def compute_rolling_sharpe(returns: np.ndarray, window: int = 252) -> np.ndarray:
    """Sharpe rolling para análise de estabilidade."""
    ...

def generate_tearsheet(result: BacktestResult) -> dict:
    """Gera dict completo para renderização no dashboard."""
    # Inclui: equity curve, drawdown chart, monthly returns heatmap,
    # rolling sharpe, trade analysis, return distribution
    ...
```

## 5. Tests: tests/test_strategies/test_backtesting.py

- Test compute_sharpe com retornos conhecidos (ex: retornos constantes = Sharpe alto)
- Test compute_max_drawdown com série simples
- Test TransactionCostModel.get_cost para instrumento conhecido
- Test BacktestEngine.run_single com MockStrategy que retorna sinais fixos
- Test que point_in_time=True não usa dados futuros
- Test deflated_sharpe < sharpe original quando n_trials > 1

═══ FIM DO PROMPT 2 ═══

# VERIFICAÇÃO:
# □ pytest tests/test_strategies/test_backtesting.py -v
# □ Import funcional: from src.strategies.backtesting import BacktestEngine

################################################################################
##                                                                            ##
##  ETAPA 3 — FX STRATEGIES (FX-02 a FX-05)                                  ##
##  Tempo: ~35 min | 4 estratégias FX adicionais                             ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 3 ═══

No projeto macro-fund-system, implemente 4 estratégias FX adicionais em src/strategies/fx/. A Fase 1 já implementou FX-01 (BEER Misalignment). Agora implemente FX-02 a FX-05.

## 1. src/strategies/fx/fx02_carry_momentum.py — FX-02: Carry-Adjusted Momentum

Referências: Burnside (2011) "Carry Trades and Risk"; Menkhoff et al. (2012) "Carry Trades and Global FX Volatility".

```python
@StrategyRegistry.register("FX-02")
class FXCarryMomentum(BaseStrategy):
    """
    Combina carry (diferencial de juros) com momentum de preço.
    
    LÓGICA:
    - carry_score = (selic_target - fed_funds) — diferencial de juros
    - momentum_score = retorno USDBRL 3M z-score (invertido: BRL forte = positivo)
    - vol_adjustment = 1 / realized_vol_21d (reduz size em alta vol)
    - combined = w_carry * carry_z + w_mom * momentum_z, ajustado por vol
    
    INSTRUMENTOS: DOL futuro (B3) ou USDBRL NDF
    HOLDING: 5-15 dias
    EXPECTED SHARPE: 0.6-0.9
    """
    
    def default_params(self) -> dict:
        return {
            "carry_weight": 0.5,
            "momentum_weight": 0.5,
            "momentum_lookback_days": 63,      # 3 meses
            "vol_lookback_days": 21,
            "z_score_window": 504,             # 2 anos
            "max_vol_threshold": 0.25,         # não opera se vol > 25%
            "rebalance_days": 5,
        }
    
    async def compute_signal(self, as_of_date: date) -> StrategySignal:
        # 1. Buscar BR_SELIC_TARGET, US_FED_FUNDS
        # 2. Buscar preços USDBRL para janela de momentum
        # 3. Calcular carry z-score e momentum z-score
        # 4. Calcular vol realizada 21d do USDBRL
        # 5. Combinar com pesos, ajustar por vol
        # 6. Mapear para StrategySignal
        ...
```

## 2. src/strategies/fx/fx03_flow_tactical.py — FX-03: Flow-Based Tactical FX

Referências: Evans & Lyons (2002) "Order Flow and Exchange Rate Dynamics"; Froot & Ramadorai (2005) "Currency Returns, Intrinsic Value, and Institutional-Investor Flows".

```python
@StrategyRegistry.register("FX-03")
class FXFlowTactical(BaseStrategy):
    """
    Opera USDBRL com base em fluxos cambiais do BCB e posicionamento CFTC.
    
    LÓGICA:
    - bcb_flow_score: z-score do fluxo cambial semanal (comercial + financeiro)
    - cftc_score: z-score do posicionamento net especulativo em BRL (CFTC COT)
    - b3_foreign_score: z-score do fluxo estrangeiro em bolsa/juros (B3)
    - contrarian quando posição extrema (|z| > 2), momentum caso contrário
    
    DADOS NECESSÁRIOS:
    - BCB FX Flow: BR_FX_FLOW_COMMERCIAL, BR_FX_FLOW_FINANCIAL (semanal)
    - CFTC COT: net positioning BRL (semanal, 3 dias de lag)
    - B3: fluxo estrangeiro em ações e juros (diário)
    
    INSTRUMENTOS: DOL futuro (B3)
    HOLDING: 5-20 dias
    EXPECTED SHARPE: 0.5-0.8
    """
    
    def default_params(self) -> dict:
        return {
            "bcb_flow_weight": 0.40,
            "cftc_weight": 0.35,
            "b3_foreign_weight": 0.25,
            "z_score_window": 104,             # 2 anos (semanal)
            "contrarian_threshold": 2.0,       # z > 2 = contrarian
            "flow_lookback_weeks": 4,          # média móvel 4 semanas
        }
    
    async def compute_signal(self, as_of_date: date) -> StrategySignal:
        # 1. Buscar séries de flow_data com point-in-time (release_time)
        # 2. Calcular médias móveis de 4 semanas
        # 3. Z-score de cada componente
        # 4. Lógica contrarian: se |z| > threshold, inverter sinal
        # 5. Combinar scores com pesos
        ...
```

## 3. src/strategies/fx/fx04_vol_surface_rv.py — FX-04: FX Vol Surface Relative Value

Referências: Carr & Wu (2007) "Stochastic Skew in Currency Options"; Bates (1996) "Jumps and Stochastic Volatility".

```python
@StrategyRegistry.register("FX-04")
class FXVolSurfaceRV(BaseStrategy):
    """
    Identifica distorções na superfície de vol de USDBRL e opera via opções/delta-hedged.
    
    LÓGICA:
    - risk_reversal_z: z-score do 25-delta risk reversal (skew)
    - butterfly_z: z-score do 25-delta butterfly (curvature)  
    - term_structure_z: z-score do spread 3M-1M implied vol
    - vol_level_z: z-score do ATM vol vs. realizada
    
    Combinação: 
    - Se risk_reversal muito positivo → puts caras → vender puts / long BRL
    - Se butterfly extremo → curvatura cara → vender wings
    - Se term structure invertida → near-term stress → cautela
    
    INSTRUMENTOS: Opções USDBRL (B3 ou OTC), delta-hedged com DOL futuro
    HOLDING: 10-30 dias (até vencimento da opção)
    EXPECTED SHARPE: 0.4-0.7 (alta convexidade)
    """
    
    def default_params(self) -> dict:
        return {
            "rr_weight": 0.35,
            "butterfly_weight": 0.25,
            "term_structure_weight": 0.20,
            "vol_premium_weight": 0.20,
            "z_score_window": 252,
            "implied_realized_threshold": 0.03,  # 3 vol points
        }
    
    async def compute_signal(self, as_of_date: date) -> StrategySignal:
        # 1. Buscar vol_surfaces para USDBRL
        # 2. Calcular risk reversal, butterfly, ATM vol
        # 3. Buscar realized vol (já na Silver Layer)
        # 4. Z-score cada componente
        # 5. Combinar em signal
        ...
```

## 4. src/strategies/fx/fx05_terms_of_trade.py — FX-05: Terms of Trade FX

Referências: Cashin, Céspedes & Sahay (2004) "Commodity Currencies and the Real Exchange Rate"; Chen & Rogoff (2003).

```python
@StrategyRegistry.register("FX-05")
class FXTermsOfTrade(BaseStrategy):
    """
    Opera USDBRL com base na evolução dos termos de troca do Brasil.
    
    LÓGICA:
    Brasil é exportador líquido de: soja, minério de ferro, petróleo, café, açúcar.
    - Constrói índice de termos de troca ponderado pelas exportações brasileiras
    - tot_index = weighted_avg(commodity_prices) / us_ppi
    - Compara tot_index vs USDBRL para medir desalinhamento
    - Quando commodities sobem e BRL não acompanha → LONG BRL
    
    PESOS DAS COMMODITIES (aprox. share de exportação):
    - Soja: 0.25, Minério: 0.20, Petróleo: 0.18, Açúcar: 0.08, 
    - Café: 0.06, Milho: 0.05, Carne: 0.05, Celulose: 0.05, Outros: 0.08
    
    INSTRUMENTOS: DOL futuro (B3), NDF OTC
    HOLDING: 15-60 dias (slow-moving)
    EXPECTED SHARPE: 0.5-0.7
    """
    
    def default_params(self) -> dict:
        return {
            "commodity_weights": {
                "SOYBEAN": 0.25, "IRON_ORE": 0.20, "OIL_WTI": 0.18,
                "SUGAR": 0.08, "COFFEE": 0.06, "CORN": 0.05,
                "BEEF": 0.05, "CELLULOSE": 0.05, "OTHER": 0.08,
            },
            "tot_lookback_days": 126,          # 6 meses
            "misalignment_window": 504,        # 2 anos
            "cointegration_lookback": 1260,    # 5 anos
            "mean_reversion_halflife": 45,     # dias
        }
    
    async def compute_signal(self, as_of_date: date) -> StrategySignal:
        # 1. Buscar preços de commodities do market_data
        # 2. Construir ToT index ponderado
        # 3. Normalizar por US PPI
        # 4. Calcular spread vs USDBRL (ou fazer regressão OLS rolling)
        # 5. Z-score do resíduo = sinal de misalignment
        ...
```

## 5. src/strategies/fx/__init__.py

Import de todas as 5 estratégias FX (FX-01 já existe da Fase 1).

## 6. Tests: tests/test_strategies/test_fx.py

- Test FXCarryMomentum.default_params retorna dict com keys esperadas
- Test FXFlowTactical contrarian logic: mock z_score > 2 → inverte sinal
- Test FXTermsOfTrade.compute_signal com dados mock → retorna StrategySignal válido
- Test que todas as 5 FX strategies estão no StrategyRegistry

═══ FIM DO PROMPT 3 ═══

# VERIFICAÇÃO:
# □ pytest tests/test_strategies/test_fx.py -v
# □ StrategyRegistry.list_by_asset_class(AssetClass.FX) retorna 5 estratégias


################################################################################
##                                                                            ##
##  ETAPA 4 — RATES STRATEGIES (RATES-03 a RATES-06)                         ##
##  Tempo: ~35 min | 4 estratégias de juros adicionais                       ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 4 ═══

No projeto macro-fund-system, implemente 4 estratégias de juros adicionais em src/strategies/rates/. A Fase 1 já implementou RATES-01 (DI Curve Slope) e RATES-02 (UST Curve Positioning). Implemente RATES-03 a RATES-06.

## 1. src/strategies/rates/rates03_br_us_spread.py — RATES-03: BR-US Rate Spread Trading

Referências: Frankel & Poonawala (2010) "The Forward Market in Emerging Currencies"; Du, Tepper & Verdelhan (2018) "Deviations from Covered Interest Rate Parity".

```python
@StrategyRegistry.register("RATES-03")
class BRUSRateSpread(BaseStrategy):
    """
    Opera o spread entre juros brasileiros e americanos.
    
    LÓGICA:
    - spread = DI_PRE(tenor) - UST_NOM(tenor) para cada vértice
    - z_score do spread vs. história rolling de 2 anos
    - Incorpora: prêmio de risco país (CDS 5Y), expectativa Focus Selic,
      FOMC implied path, inflação diferencial
    - Se spread comprimido demais (z < -1.5) vs fundamentais → LONG spread
    - Se spread alargado demais (z > 1.5) → SHORT spread
    
    INSTRUMENTOS: 
    - BR leg: DI1 futuro (B3) no vértice escolhido
    - US leg: ZN/ZF futures (CME) ou UST cash
    HEDGE: delta-neutral no FX (DOL futuro para neutralizar exposição cambial)
    
    TENORS DE FOCO: 2Y, 5Y
    HOLDING: 10-30 dias
    EXPECTED SHARPE: 0.5-0.8
    """
    
    def default_params(self) -> dict:
        return {
            "tenors": ["2Y", "5Y"],
            "z_score_window": 504,
            "cds_adjustment": True,
            "inflation_differential_weight": 0.3,
            "cds_weight": 0.3,
            "pure_spread_weight": 0.4,
            "entry_z_threshold": 1.5,
        }
    
    async def compute_signal(self, as_of_date: date) -> StrategySignal:
        # 1. Buscar curvas DI_PRE e UST_NOM para tenors de foco
        # 2. Calcular spread bruto
        # 3. Buscar CDS 5Y Brasil, inflação diferencial (IPCA_YOY - CPI_YOY)
        # 4. Calcular spread ajustado (removendo componente de CDS e inflação)
        # 5. Z-score do spread ajustado
        # 6. Gerar sinal
        ...
```

## 2. src/strategies/rates/rates04_term_premium.py — RATES-04: Term Premium Extraction

Referências: Adrian, Crump & Moench (2013) "Pricing the Term Structure with Linear Regressions" (ACM model); Kim & Wright (2005).

```python
@StrategyRegistry.register("RATES-04")
class TermPremiumExtraction(BaseStrategy):
    """
    Estima e opera o term premium da curva de juros brasileira.
    
    LÓGICA (modelo simplificado do ACM):
    - Decompõe a taxa de juros de longo prazo em:
      rate(n) = expected_short_rate(n) + term_premium(n)
    - expected_short_rate: média das expectativas Focus para Selic nos próximos n anos
    - term_premium = rate(n) - expected_short_rate(n)
    - Z-score do term premium vs. história
    - Quando TP excessivo (z > 1.5) → receiver de DI (aposta que TP vai comprimir)
    - Quando TP comprimido (z < -1.0) → payer de DI
    
    INSTRUMENTOS: DI1 futuro (B3) vértices 2Y, 3Y, 5Y
    HOLDING: 15-45 dias
    EXPECTED SHARPE: 0.4-0.7
    """
    
    def default_params(self) -> dict:
        return {
            "focus_tenor_months": [12, 24, 36, 48, 60],
            "z_score_window": 504,
            "entry_z_threshold_long": 1.5,
            "entry_z_threshold_short": -1.0,
            "use_kalman_filter": True,
            "kalman_obs_noise": 0.001,
            "kalman_process_noise": 0.0001,
        }
    
    async def compute_signal(self, as_of_date: date) -> StrategySignal:
        # 1. Buscar curva DI_PRE (2Y, 3Y, 5Y)
        # 2. Buscar expectativas Focus para Selic nos horizontes correspondentes
        # 3. Calcular expected_short_rate para cada tenor
        # 4. term_premium = DI_rate - expected_short_rate
        # 5. Aplicar Kalman Filter para suavizar série de TP
        # 6. Z-score e geração de sinal
        ...
```

## 3. src/strategies/rates/rates05_fomc_event.py — RATES-05: FOMC Event Strategy

Referências: Lucca & Moench (2015) "The Pre-FOMC Announcement Drift"; Cieslak, Morse & Vissing-Jorgensen (2019).

```python
@StrategyRegistry.register("RATES-05")
class FOMCEventStrategy(BaseStrategy):
    """
    Opera em torno de decisões do FOMC com base em desvio de expectativas.
    
    LÓGICA:
    - Antes do FOMC: posiciona com base no desvio entre:
      (a) FFR implied pela curva de Fed Funds futures
      (b) Estimativa do modelo (Taylor Rule + dados recentes)
    - Se mercado pricing corte > modelo sugere → payer (short bonds)
    - Se mercado pricing hike < modelo sugere → receiver (long bonds)
    - Após o FOMC: opera o "drift" de 24h pós-decisão em caso de surpresa
    
    CALENDAR: Opera apenas em janela [-5, +2] dias do FOMC
    
    INSTRUMENTOS: ZN, ZF futures (CME), SOFR futures
    HOLDING: 2-7 dias
    EXPECTED SHARPE: 0.3-0.6 (baixa frequência, alto hit rate)
    """
    
    def default_params(self) -> dict:
        return {
            "pre_event_days": 5,
            "post_event_days": 2,
            "min_surprise_bps": 5,
            "fomc_calendar": [],
            "taylor_rule_weight": 0.5,
            "market_implied_weight": 0.5,
        }
    
    async def compute_signal(self, as_of_date: date) -> StrategySignal:
        # 1. Verificar se estamos na janela [-5, +2] de um FOMC
        # 2. Se pre-event: comparar FFR implied vs Taylor Rule output
        # 3. Se post-event: comparar decisão real vs expectativa
        # 4. Gerar sinal
        ...
```

## 4. src/strategies/rates/rates06_copom_event.py — RATES-06: COPOM Event Strategy

```python
@StrategyRegistry.register("RATES-06")
class COPOMEventStrategy(BaseStrategy):
    """
    Opera em torno de decisões do COPOM com base em desvio de expectativas.
    
    LÓGICA:
    - Compara Selic implied pela curva DI (vértice curto) vs:
      (a) Mediana Focus para próxima Selic
      (b) Modelo Taylor Rule Brasil (do Monetary Policy Agent)
    - Pre-COPOM: posiciona se desvio > threshold
    - Post-COPOM: opera drift se surpresa
    
    CALENDAR: Opera apenas em janela [-5, +2] dias do COPOM (8x/ano)
    
    INSTRUMENTOS: DI1 futuro curto (B3)
    HOLDING: 2-7 dias
    EXPECTED SHARPE: 0.3-0.6
    """
    
    def default_params(self) -> dict:
        return {
            "pre_event_days": 5,
            "post_event_days": 2,
            "min_surprise_bps": 25,
            "copom_calendar": [],
            "focus_weight": 0.5,
            "di_implied_weight": 0.5,
        }
    
    async def compute_signal(self, as_of_date: date) -> StrategySignal:
        ...
```

## 5. Tests: tests/test_strategies/test_rates.py

- Test BRUSRateSpread com spreads mock → sinal correto
- Test TermPremiumExtraction: term_premium = rate - expected > 0 quando TP positivo
- Test FOMCEventStrategy retorna FLAT quando fora da janela de evento
- Test COPOMEventStrategy retorna FLAT quando fora da janela
- Test todas 6 RATES strategies no Registry

═══ FIM DO PROMPT 4 ═══

# VERIFICAÇÃO:
# □ pytest tests/test_strategies/test_rates.py -v
# □ StrategyRegistry.list_by_asset_class(AssetClass.RATES_BR) + RATES_US = 6

################################################################################
##                                                                            ##
##  ETAPA 5 — INFLATION & CUPOM CAMBIAL STRATEGIES                           ##
##  Tempo: ~35 min | INF-02, INF-03, CUPOM-01, CUPOM-02                     ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 5 ═══

No projeto macro-fund-system, implemente 4 estratégias adicionais: 2 de inflação e 2 de cupom cambial. A Fase 1 já implementou INF-01 (Breakeven Inflation Trade).

## 1. src/strategies/inflation/inf02_ipca_surprise.py — INF-02: IPCA Surprise Trade

Referências: Gürkaynak, Sack & Swanson (2005) "Do Actions Speak Louder Than Words?"; BCB — Inflation Targeting Framework.

```python
@StrategyRegistry.register("INF-02")
class IPCASurpriseTrade(BaseStrategy):
    """
    Opera NTN-Bs e breakevens em torno de releases de IPCA.
    
    LÓGICA:
    - Antes do IPCA: compara expectativa Focus IPCA vs modelo bottom-up do Inflation Agent
    - Se modelo prevê IPCA > Focus → LONG breakeven (compra NTN-B, vende LTN)
    - Se modelo prevê IPCA < Focus → SHORT breakeven
    - Após o IPCA: opera convergência se houve surpresa
    
    TIMING: 
    - IPCA mensal sai ~dia 10 do mês seguinte (IBGE)
    - IPCA-15 sai ~dia 25 do mês corrente (preview)
    - Usar IPCA-15 como leading indicator do IPCA cheio
    
    DADOS:
    - BR_IPCA_MOM, BR_IPCA15_MOM (macro_series)
    - Focus IPCA próximo mês
    - Inflation Agent bottom-up forecast
    - Curvas NTN_B_REAL, DI_PRE
    
    INSTRUMENTOS: NTN-B, LTN, DI1 futuro
    HOLDING: 5-15 dias (evento)
    EXPECTED SHARPE: 0.3-0.5
    """
    
    def default_params(self) -> dict:
        return {
            "pre_release_days": 5,
            "post_release_days": 3,
            "min_surprise_bps": 5,
            "ipca15_as_preview": True,
            "inflation_agent_weight": 0.6,
            "focus_weight": 0.4,
        }
    
    async def compute_signal(self, as_of_date: date) -> StrategySignal:
        ...
```

## 2. src/strategies/inflation/inf03_inflation_carry.py — INF-03: Inflation Carry (NTN-B vs LTN)

Referências: D'Amico, Kim & Wei (2018) "Tips from TIPS"; Fleckenstein, Longstaff & Lustig (2014) "The TIPS-Treasury Bond Puzzle".

```python
@StrategyRegistry.register("INF-03")
class InflationCarry(BaseStrategy):
    """
    Carry trade entre NTN-B (juros reais) e LTN (juros nominais).
    
    LÓGICA:
    - breakeven = DI_PRE(5Y) - NTN_B_REAL(5Y) = inflação implícita 5Y
    - compare breakeven vs:
      (a) Target de inflação BCB (3.0% centro)
      (b) IPCA YoY corrente
      (c) Focus IPCA 12M e 24M
    - Se breakeven muito acima do fundamentado → SHORT breakeven
    - Se breakeven comprimido → LONG breakeven
    
    INSTRUMENTOS: NTN-B, LTN (OTC), ou DI1 + NTN-B futuro
    HOLDING: 30-90 dias
    EXPECTED SHARPE: 0.5-0.8
    """
    
    def default_params(self) -> dict:
        return {
            "tenors": ["3Y", "5Y"],
            "z_score_window": 504,
            "inflation_target": 0.03,
            "focus_weight": 0.3,
            "current_ipca_weight": 0.3,
            "target_weight": 0.4,
        }
    
    async def compute_signal(self, as_of_date: date) -> StrategySignal:
        ...
```

## 3. src/strategies/cupom/cupom01_cip_basis.py — CUPOM-01: CIP Basis Trade

Referências: Du, Tepper & Verdelhan (2018) "Deviations from Covered Interest Rate Parity"; Avdjiev et al. (2019).

```python
@StrategyRegistry.register("CUPOM-01")
class CIPBasisTrade(BaseStrategy):
    """
    Explora desvios da Covered Interest Parity entre BRL e USD.
    
    LÓGICA:
    CIP implica: F/S = (1 + r_BRL) / (1 + r_USD)
    - cip_basis = DDI_cupom - UST_rate (para cada tenor)
    - Quando basis alargado (z > 1.5): recebe basis (mean reversion)
    - Quando basis comprimido (z < -1.5): paga basis
    
    O basis é influenciado por:
    - Demanda por hedge FX (exportadores vs importadores)
    - Fluxo cambial líquido
    - Atuação do BCB (swaps cambiais, leilões de linha)
    - Risk-off global (dólar escasso)
    
    INSTRUMENTOS: DDI futuro (B3) + UST futures (CME) ou FX swap OTC
    HOLDING: 15-45 dias
    EXPECTED SHARPE: 0.6-1.0 (estratégia clássica de RV)
    """
    
    def default_params(self) -> dict:
        return {
            "tenors": ["3M", "6M", "1Y", "2Y"],
            "z_score_window": 504,
            "entry_z_threshold": 1.5,
            "bcb_swap_adjustment": True,
            "flow_momentum_weight": 0.2,
        }
    
    async def compute_signal(self, as_of_date: date) -> StrategySignal:
        # 1. Buscar curvas DDI_CUPOM e UST_NOM para cada tenor
        # 2. Calcular CIP basis para cada tenor
        # 3. Z-score do basis
        # 4. Se bcb_swap_adjustment: buscar dados de swaps cambiais BCB
        # 5. Gerar sinal (mean reversion do basis)
        ...
```

## 4. src/strategies/cupom/cupom02_onshore_offshore.py — CUPOM-02: Onshore-Offshore Spread

Referências: Koepke (2019) "What Drives Capital Flows to Emerging Markets?"; Stulz (2005).

```python
@StrategyRegistry.register("CUPOM-02")
class OnshoreOffshoreSpread(BaseStrategy):
    """
    Opera o spread entre cupom cambial onshore (DDI B3) e taxa offshore (NDF implied).
    
    LÓGICA:
    - onshore_rate = DDI futuro (B3) = cupom cambial onshore
    - offshore_rate = taxa implícita no NDF USDBRL (mercado offshore)
    - spread = onshore - offshore
    - Quando spread alargado → oportunidade de arbitragem
    
    INSTRUMENTOS: DDI futuro (B3) vs NDF USDBRL (OTC)
    HOLDING: 10-30 dias
    EXPECTED SHARPE: 0.4-0.7
    """
    
    def default_params(self) -> dict:
        return {
            "tenors": ["3M", "6M"],
            "z_score_window": 252,
            "entry_z_threshold": 1.5,
        }
    
    async def compute_signal(self, as_of_date: date) -> StrategySignal:
        ...
```

## 5. Tests: tests/test_strategies/test_inflation.py e test_cupom.py

- Test INF-02 retorna FLAT fora da janela de release
- Test INF-03 breakeven calculation: DI_PRE - NTN_B = breakeven
- Test CUPOM-01 CIP basis calculation com rates mock
- Test CUPOM-02 spread calculation
- Test Registry counts: 3 inflation, 2 cupom cambial

═══ FIM DO PROMPT 5 ═══

# VERIFICAÇÃO:
# □ pytest tests/test_strategies/test_inflation.py tests/test_strategies/test_cupom.py -v


################################################################################
##                                                                            ##
##  ETAPA 6 — SOVEREIGN CREDIT & CROSS-ASSET STRATEGIES                      ##
##  Tempo: ~35 min | SOV-01, SOV-02, SOV-03, CROSS-01, CROSS-02             ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 6 ═══

No projeto macro-fund-system, implemente 5 estratégias finais: 3 de crédito soberano e 2 cross-asset.

## 1. src/strategies/sovereign/sov01_cds_curve.py — SOV-01: CDS Curve Trading

Referências: Pan & Singleton (2008) "Default and Recovery Implicit in the Term Structure of Sovereign CDS Spreads"; Longstaff et al. (2011).

```python
@StrategyRegistry.register("SOV-01")
class CDSCurveTrading(BaseStrategy):
    """
    Opera a curva de CDS do Brasil (1Y, 5Y, 10Y) com base em slope e nível.
    
    LÓGICA:
    - cds_slope = CDS_10Y - CDS_5Y (normalizado pelo nível)
    - cds_level_z = z-score do CDS 5Y vs história
    - fiscal_score = output do Fiscal Agent (DSA model)
    
    REGRAS:
    - Se fiscal melhorando E CDS ainda alto → LONG Brasil (sell protection)
    - Se fiscal deteriorando E CDS baixo → SHORT Brasil (buy protection)
    - Slope trade: se slope invertida (10Y < 5Y) → buy 1Y protection
    
    INSTRUMENTOS: CDS Brasil 1Y, 5Y, 10Y (OTC via ISDA)
    HOLDING: 20-60 dias
    EXPECTED SHARPE: 0.4-0.7
    """
    
    def default_params(self) -> dict:
        return {
            "z_score_window": 504,
            "fiscal_agent_weight": 0.40,
            "cds_level_weight": 0.35,
            "cds_slope_weight": 0.25,
            "entry_z_threshold": 1.0,
        }
    
    async def compute_signal(self, as_of_date: date) -> StrategySignal:
        ...
```

## 2. src/strategies/sovereign/sov02_em_relative_value.py — SOV-02: EM Sovereign RV

Referências: Duffie, Pedersen & Singleton (2003); Hilscher & Nosbusch (2010).

```python
@StrategyRegistry.register("SOV-02")
class EMSovereignRV(BaseStrategy):
    """
    Relative value do Brasil vs peers EM em CDS e bonds soberanos.
    
    LÓGICA:
    - Cross-section regression: CDS_i = f(fundamentals_i) + epsilon_i
    - epsilon_brasil = residual → se negativo, Brasil "barato" → sell CDS (long)
    
    PEERS: México, Colômbia, Chile, Peru, África do Sul, Turquia, Indonésia,
           Índia, Polônia, Hungria
    
    INSTRUMENTOS: CDS Brasil vs CDS peer (par trade), ou outright
    HOLDING: 30-90 dias
    EXPECTED SHARPE: 0.3-0.6
    """
    
    def default_params(self) -> dict:
        return {
            "peer_countries": ["MEX","COL","CHL","PER","ZAF","TUR","IDN","IND","POL","HUN"],
            "fundamental_vars": ["debt_gdp","primary_balance_gdp","current_account_gdp",
                                 "reserves_sted","rating_numeric","commodity_exposure"],
            "regression_window_years": 5,
            "z_score_window": 252,
            "entry_z_threshold": 1.5,
        }
    
    async def compute_signal(self, as_of_date: date) -> StrategySignal:
        # 1. Buscar fundamentais de todos os países
        # 2. Buscar CDS 5Y de todos os peers
        # 3. Cross-section OLS regression
        # 4. Calcular resíduo do Brasil
        # 5. Z-score do resíduo → sinal
        ...
```

## 3. src/strategies/sovereign/sov03_rating_migration.py — SOV-03: Rating Migration

```python
@StrategyRegistry.register("SOV-03")
class RatingMigrationAnticipation(BaseStrategy):
    """
    Antecipa upgrades/downgrades soberanos usando modelo de probabilidades.
    
    LÓGICA:
    - Modelo logístico: P(upgrade) = f(fiscal_trend, growth_trend, external_pos, political_risk)
    - Usa outputs dos agentes: Fiscal Agent, Inflation Agent, FX Agent
    
    INSTRUMENTOS: CDS, NTN-B longas, USDBRL
    HOLDING: 60-180 dias (slow-moving)
    EXPECTED SHARPE: 0.3-0.5
    """
    
    def default_params(self) -> dict:
        return {
            "upgrade_threshold": 0.6,
            "downgrade_threshold": 0.5,
            "fiscal_weight": 0.30,
            "growth_weight": 0.25,
            "external_weight": 0.25,
            "political_weight": 0.20,
            "lookback_months": 12,
        }
    
    async def compute_signal(self, as_of_date: date) -> StrategySignal:
        ...
```

## 4. src/strategies/cross_asset/cross01_macro_regime.py — CROSS-01: Macro Regime Allocation

Referências: Hamilton (1989) regime switching; Ang & Bekaert (2002).

```python
@StrategyRegistry.register("CROSS-01")
class MacroRegimeAllocation(BaseStrategy):
    """
    Aloca risco entre classes de ativos baseado no regime macroeconômico.
    
    REGIMES (Hidden Markov Model com 4 estados):
    1. GOLDILOCKS: crescimento alto, inflação baixa
    2. REFLATION: crescimento alto, inflação alta
    3. STAGFLATION: crescimento baixo, inflação alta
    4. DEFLATION: crescimento baixo, inflação baixa
    
    INPUTS DO HMM:
    - Crescimento: IBC-Br z-score, PMC, PMS, emprego (BR); GDP, NFP, ISM (US)
    - Inflação: IPCA YoY, núcleos, diffusion (BR); CPI, PCE core (US)
    
    INSTRUMENTOS: Todos (FX, DI, NTN-B, UST, equities)
    REBALANCE: Mensal
    EXPECTED SHARPE: 0.5-0.8
    """
    
    def default_params(self) -> dict:
        return {
            "n_regimes": 4,
            "hmm_lookback_months": 120,
            "regime_allocation_map": {
                "GOLDILOCKS":  {"FX": -0.2, "DI_SHORT": 0.3, "NTN_B": 0.3, "EQUITY": 0.2},
                "REFLATION":   {"FX": -0.1, "DI_SHORT": -0.1, "NTN_B": 0.4, "COMMODITY": 0.3},
                "STAGFLATION": {"FX": 0.2, "DI_SHORT": -0.3, "NTN_B": 0.2, "EQUITY": -0.2},
                "DEFLATION":   {"FX": 0.1, "DI_LONG": 0.4, "UST_LONG": 0.3, "EQUITY": -0.1},
            },
            "smoothing_window": 21,
        }
    
    async def compute_signal(self, as_of_date: date) -> StrategySignal:
        # 1. Buscar indicadores macro BR + US
        # 2. Construir features: z-scores de crescimento e inflação
        # 3. Rodar HMM ou usar modelo pré-calibrado
        # 4. Obter probabilidades dos 4 regimes
        # 5. Weighted allocation = Σ P(regime_i) * allocation_map[regime_i]
        ...
```

## 5. src/strategies/cross_asset/cross02_risk_appetite.py — CROSS-02: Global Risk Appetite

Referências: Rey (2013) "Dilemma not Trilemma"; Miranda-Agrippino & Rey (2020).

```python
@StrategyRegistry.register("CROSS-02")
class GlobalRiskAppetite(BaseStrategy):
    """
    Opera com base em índice proprietário de risk appetite global.
    
    COMPONENTES:
    - VIX z-score (inv): 0.20 | HY OAS z-score (inv): 0.15
    - DXY z-score (inv): 0.15 | EM FX carry: 0.15
    - CFTC net spec S&P: 0.10 | IG-HY spread: 0.10
    - S&P 1M return: 0.10      | Gold z-score (inv): 0.05
    
    REGRAS:
    - risk_appetite > 1.5 → contrarian (reduce risk)
    - -0.5 a 1.5 → pro-cíclico (momentum)
    - risk_appetite < -1.5 → contrarian (add risk)
    
    INSTRUMENTOS: USDBRL, DI1, IBOV, S&P, VIX futures
    HOLDING: 5-20 dias
    EXPECTED SHARPE: 0.4-0.7
    """
    
    def default_params(self) -> dict:
        return {
            "components": {
                "VIX": {"weight": 0.20, "invert": True},
                "US_HY_OAS": {"weight": 0.15, "invert": True},
                "DXY": {"weight": 0.15, "invert": True},
                "EM_FX_CARRY": {"weight": 0.15, "invert": False},
                "CFTC_SP500": {"weight": 0.10, "invert": False},
                "IG_HY_SPREAD": {"weight": 0.10, "invert": True},
                "SP500_MOM_1M": {"weight": 0.10, "invert": False},
                "GOLD": {"weight": 0.05, "invert": True},
            },
            "z_score_window": 252,
            "contrarian_threshold": 1.5,
        }
    
    async def compute_signal(self, as_of_date: date) -> StrategySignal:
        ...
```

## 6. Tests: tests/test_strategies/test_sovereign.py e test_cross_asset.py

- Test SOV-02 cross-section regression com dados sintéticos
- Test CROSS-01 regime allocation map values
- Test CROSS-02 risk appetite index normalização
- Test Registry: total >= 22 estratégias registradas

═══ FIM DO PROMPT 6 ═══

# VERIFICAÇÃO:
# □ pytest tests/test_strategies/ -v (TODOS os testes)
# □ len(StrategyRegistry.list_all()) >= 22

################################################################################
##                                                                            ##
##  ETAPA 7 — CROSS-ASSET AGENT (LLM-POWERED)                               ##
##  Tempo: ~30 min | Agente orquestrador que sintetiza todos os outros        ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 7 ═══

No projeto macro-fund-system, implemente o Cross-Asset Agent em src/agents/cross_asset_agent.py. Este agente sintetiza outputs de todos os agentes especializados (Inflation, Monetary Policy, Fiscal, FX Equilibrium — Fase 1) para produzir uma visão macro consolidada.

Referências: Dalio (2017) "Principles for Navigating Big Debt Crises"; Bridgewater "How the Economic Machine Works".

## 1. src/agents/cross_asset_agent.py

```python
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
import json

class MacroRegime(Enum):
    GOLDILOCKS = "GOLDILOCKS"
    REFLATION = "REFLATION"
    STAGFLATION = "STAGFLATION"
    DEFLATION = "DEFLATION"
    TRANSITION = "TRANSITION"

@dataclass
class AgentOutput:
    agent_id: str
    timestamp: date
    primary_signal: float            # -1.0 a +1.0
    confidence: float                # 0.0 a 1.0
    key_drivers: list[str]
    risk_factors: list[str]
    data_staleness_days: int
    metadata: dict = field(default_factory=dict)

@dataclass
class CrossAssetView:
    timestamp: date
    regime: MacroRegime
    regime_probabilities: dict[str, float]
    
    # Views por classe de ativo (-1 a +1)
    fx_view: float
    rates_br_view: float
    rates_us_view: float
    inflation_br_view: float
    cupom_view: float
    sovereign_view: float
    equity_view: float
    
    overall_risk_appetite: float
    tail_risk_probability: float
    
    agent_outputs: dict[str, AgentOutput]
    narrative: str                   # gerado por LLM ou regras
    key_trades: list[dict]
    risk_warnings: list[str]
    confidence: float

class CrossAssetAgent:
    """
    Agente orquestrador:
    1. Coleta outputs de: Inflation, Monetary Policy, Fiscal, FX Equilibrium Agents
    2. Roda HMM para classificar regime macro (4 estados)
    3. Aplica lógica de consistência cross-asset
    4. Usa LLM (Claude) para gerar narrativa e trade ideas
    5. Produz CrossAssetView
    """
    
    def __init__(self, llm_client=None, use_llm: bool = True):
        self.llm_client = llm_client
        self.use_llm = use_llm
        
    async def collect_agent_outputs(self, as_of_date: date) -> dict[str, AgentOutput]:
        """Busca da tabela signals os últimos outputs de cada agente."""
        ...
    
    async def classify_regime(self, agent_outputs: dict[str, AgentOutput],
                              macro_data: dict) -> tuple[MacroRegime, dict[str, float]]:
        """HMM com 4 estados + fallback baseado em regras."""
        ...
    
    async def compute_cross_asset_views(self, agent_outputs: dict[str, AgentOutput],
                                        regime: MacroRegime) -> dict[str, float]:
        """Matrix de mapeamento: agent_output × regime → asset_view."""
        ...
    
    async def check_consistency(self, views: dict[str, float], 
                                agent_outputs: dict[str, AgentOutput]) -> list[str]:
        """Verifica consistência lógica (ex: fx bull + rates higher = inconsistente)."""
        ...
    
    async def generate_narrative(self, view: CrossAssetView) -> str:
        """Gera narrativa usando Claude API ou fallback por regras."""
        if not self.use_llm:
            return self._rule_based_narrative(view)
        
        prompt = f"""
        Você é o estrategista-chefe de um macro hedge fund focado em Brasil e EUA.
        
        Dados dos agentes: {json.dumps({k: {"signal": v.primary_signal, 
            "confidence": v.confidence, "drivers": v.key_drivers} 
            for k, v in view.agent_outputs.items()}, indent=2)}
        
        Regime: {view.regime.value}
        Probabilidades: {json.dumps(view.regime_probabilities)}
        
        Views: FX={view.fx_view:.2f}, Juros BR={view.rates_br_view:.2f},
        Juros US={view.rates_us_view:.2f}, Inflação BR={view.inflation_br_view:.2f},
        Cupom={view.cupom_view:.2f}, Soberano={view.sovereign_view:.2f}
        
        Risk appetite: {view.overall_risk_appetite:.2f}
        Tail risk: {view.tail_risk_probability:.2f}
        
        Produza JSON com: "narrative" (3-5 parágrafos), "trades" (top 3), "risks"
        """
        ...
    
    async def run(self, as_of_date: date) -> CrossAssetView:
        """Pipeline completo do agente."""
        ...
    
    def _rule_based_narrative(self, view: CrossAssetView) -> str:
        """Fallback sem LLM."""
        ...
```

## 2. Rota API: src/api/routes/agents.py

```
GET /api/v1/agents/cross-asset/latest → Último CrossAssetView
GET /api/v1/agents/cross-asset/history?start=2024-01-01 → Série histórica
GET /api/v1/agents/{agent_id}/latest → Último AgentOutput de qualquer agente
POST /api/v1/agents/cross-asset/run → Trigger manual (retorna CrossAssetView)
```

## 3. Tests: tests/test_agents/test_cross_asset.py

- Test classify_regime com mock data → regime correto
- Test check_consistency detecta inconsistência
- Test _rule_based_narrative retorna string não-vazia
- Test run completo com mocks

═══ FIM DO PROMPT 7 ═══

# VERIFICAÇÃO:
# □ pytest tests/test_agents/test_cross_asset.py -v
# □ API: GET /api/v1/agents/cross-asset/latest retorna 200


################################################################################
##                                                                            ##
##  ETAPA 8 — NLP PIPELINE: CENTRAL BANK COMMUNICATIONS                      ##
##  Tempo: ~40 min | Scraper + processamento de atas COPOM e FOMC            ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 8 ═══

No projeto macro-fund-system, implemente o pipeline NLP para comunicações de bancos centrais em src/agents/nlp/. Referência: Data Architecture Blueprint seção 9.

Referências: Hansen & McMahon (2016) "Shocking Language"; Shapiro, Sudhof & Wilson (2022) "Measuring News Sentiment".

## 1. src/agents/nlp/__init__.py

## 2. src/agents/nlp/scrapers.py

```python
class COPOMScraper:
    """Scraper de atas e comunicados do COPOM (bcb.gov.br)."""
    async def scrape_atas(self, start_year: int = 2010) -> list[dict]: ...
    async def scrape_comunicados(self, start_year: int = 2010) -> list[dict]: ...

class FOMCScraper:
    """Scraper de statements e minutes do FOMC (federalreserve.gov)."""
    async def scrape_statements(self, start_year: int = 2010) -> list[dict]: ...
    async def scrape_minutes(self, start_year: int = 2010) -> list[dict]: ...
```

## 3. src/agents/nlp/sentiment.py

```python
class CentralBankSentimentAnalyzer:
    """Score hawkish/dovish [-1, +1] via dicionário, embeddings, e LLM."""
    
    HAWKISH_TERMS_PT = [
        "inflação persistente", "pressões inflacionárias", "vigilante",
        "ajuste necessário", "riscos altistas", "acima da meta",
        "desancoragem", "aperto monetário", "elevação da taxa", "cautela adicional",
    ]
    DOVISH_TERMS_PT = [
        "desaceleração", "inflação convergindo", "espaço para corte",
        "riscos baixistas", "abaixo da meta", "ancoragem", "flexibilização",
    ]
    HAWKISH_TERMS_EN = [
        "inflation persistent", "inflationary pressures", "restrictive stance",
        "upside risks", "above target", "labor market tight", "further tightening",
    ]
    DOVISH_TERMS_EN = [
        "disinflation", "slowing activity", "rate cuts", "downside risks",
        "below target", "easing", "accommodative", "gradual reduction",
    ]
    
    def score_document(self, text: str, language: str = "pt") -> float: ...
    def score_with_llm(self, text: str, language: str, llm_client=None) -> float: ...
    def compute_change_score(self, current: str, previous: str, language: str) -> float: ...
    def extract_key_phrases(self, text: str, language: str) -> list[dict]: ...
```

## 4. src/agents/nlp/processor.py — Pipeline Completo

```python
class NLPProcessor:
    async def process_document(self, doc: dict) -> dict:
        """Clean → Score hawk/dove → Extract phrases → Compare vs previous → Embed → Persist."""
        ...
    async def backfill_historical(self, start_year: int = 2010): ...
    async def process_new_document(self, doc: dict): ...
```

## 5. Nova tabela: src/core/models/nlp_documents.py

```
id: UUID, PK
document_type: String(30) — COPOM_ATA, COPOM_COMUNICADO, FOMC_STATEMENT, FOMC_MINUTES
institution: String(10) — BCB, FED
date: Date, NOT NULL
language: String(5) — pt, en
url: String(500)
text_hash: String(64) — SHA256
hawk_dove_score: Float — [-1, +1]
change_score: Float — vs documento anterior
key_phrases_json: JSON
metadata_json: JSON
created_at: DateTime(timezone=True), server_default=now()
```
Index: (institution, date DESC). Gere Alembic migration.

## 6. Tests: tests/test_agents/test_nlp.py

- Test score_document com texto hawkish → score > 0
- Test score_document com texto dovish → score < 0
- Test compute_change_score detecta mudança de tom
- Test COPOMScraper (mock HTTP)

═══ FIM DO PROMPT 8 ═══

# VERIFICAÇÃO:
# □ pytest tests/test_agents/test_nlp.py -v
# □ alembic upgrade head (tabela nlp_documents)


################################################################################
##                                                                            ##
##  ETAPA 9 — SIGNAL AGGREGATION LAYER                                       ##
##  Tempo: ~25 min | Combina sinais de todas as estratégias                   ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 9 ═══

No projeto macro-fund-system, implemente a Signal Aggregation Layer em src/strategies/aggregation/. Recebe sinais de ~25 estratégias e produz sinais agregados por instrumento.

Referências: Clemen (1989) "Combining Forecasts"; Timmermann (2006) "Forecast Combinations".

## 1. src/strategies/aggregation/aggregator.py

```python
@dataclass
class AggregatedSignal:
    instrument: str
    timestamp: datetime
    direction: SignalDirection
    net_signal: float              # -1 a +1
    confidence: float
    contributing_strategies: list[dict]
    regime_adjustment: float
    final_size: float
    metadata: dict = field(default_factory=dict)

class SignalAggregator:
    """
    MÉTODOS DE AGREGAÇÃO:
    1. Confidence-weighted average
    2. Rank-based (robusto a outliers)
    3. Bayesian (prior do regime + likelihood)
    
    AJUSTES:
    - Regime overlay (Cross-Asset Agent)
    - Crowding penalty (>80% concordam → reduz)
    - Staleness discount (dados desatualizados → menos peso)
    - Diversification bonus (lógicas diferentes → mais peso)
    """
    
    def __init__(self, method: str = "confidence_weighted"): ...
    
    async def aggregate(self, signals: list[StrategySignal], 
                        regime: MacroRegime = None,
                        risk_appetite: float = 0.0) -> list[AggregatedSignal]: ...
    
    def _confidence_weighted(self, signals: list[StrategySignal]) -> float: ...
    def _rank_based(self, signals: list[StrategySignal]) -> float: ...
    def _crowding_penalty(self, signals: list[StrategySignal]) -> float: ...
    def _staleness_discount(self, signal: StrategySignal, as_of: date) -> float: ...
```

## 2. src/strategies/aggregation/signal_monitor.py

```python
class SignalMonitor:
    async def check_signal_flips(self) -> list[dict]: ...
    async def check_conviction_surge(self, threshold: float = 0.3) -> list[dict]: ...
    async def check_strategy_divergence(self) -> list[dict]: ...
    async def generate_daily_summary(self, as_of_date: date) -> dict: ...
```

## 3. Rota API: src/api/routes/signals.py

```
GET /api/v1/signals/aggregated?date=2026-02-19
GET /api/v1/signals/aggregated/history?instrument=USDBRL&start=2024-01-01
GET /api/v1/signals/monitor/alerts
GET /api/v1/signals/daily-summary?date=2026-02-19
```

## 4. Tests: tests/test_strategies/test_aggregation.py

- Test confidence_weighted amplifica sinais de mesma direção
- Test confidence_weighted cancela sinais opostos
- Test crowding_penalty > 0 quando >80% concordam
- Test staleness_discount < 1 para sinais antigos

═══ FIM DO PROMPT 9 ═══

# VERIFICAÇÃO:
# □ pytest tests/test_strategies/test_aggregation.py -v
# □ API: GET /api/v1/signals/aggregated retorna 200

################################################################################
##                                                                            ##
##  ETAPA 10 — RISK ENGINE (VaR, CVaR, STRESS TESTING)                      ##
##  Tempo: ~40 min | Peça mais crítica do sistema                            ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 10 ═══

No projeto macro-fund-system, implemente o Risk Engine em src/risk/.

Referências: Jorion (2007) "Value at Risk"; McNeil, Frey & Embrechts (2015) "Quantitative Risk Management"; Glasserman (2003) "Monte Carlo Methods in Financial Engineering".

## 1. src/risk/var.py — VaR & CVaR

```python
@dataclass
class VaRResult:
    confidence_level: float
    horizon_days: int
    var_amount: float
    var_pct: float
    cvar_amount: float
    cvar_pct: float
    method: str         # HISTORICAL, PARAMETRIC, MONTE_CARLO
    breakdown_by_asset: dict[str, float]
    timestamp: datetime

class VaRCalculator:
    """Historical VaR, Parametric (Gaussian/t-Student), Monte Carlo (Cholesky)."""
    
    def __init__(self, confidence: float = 0.95, horizon_days: int = 1): ...
    
    def historical_var(self, positions: dict[str, float],
                       returns_df: pd.DataFrame, lookback: int = 504) -> VaRResult: ...
    
    def parametric_var(self, positions: dict[str, float],
                       returns_df: pd.DataFrame, lookback: int = 252) -> VaRResult:
        """Usa Ledoit-Wolf shrinkage para covariância."""
        ...
    
    def monte_carlo_var(self, positions: dict[str, float],
                        returns_df: pd.DataFrame, n_sims: int = 10000) -> VaRResult:
        """t-Student marginals + Gaussian copula + Cholesky."""
        ...
    
    def marginal_var(self, positions, returns_df) -> dict[str, float]: ...
    def component_var(self, positions, returns_df) -> dict[str, float]: ...
```

## 2. src/risk/stress.py — Stress Testing

```python
@dataclass
class StressScenario:
    name: str
    description: str
    shocks: dict[str, float]     # {instrument: shock %}
    probability: Optional[float]
    historical_analog: Optional[str]

@dataclass
class StressResult:
    scenario: StressScenario
    portfolio_pnl: float
    portfolio_pnl_pct: float
    pnl_by_asset: dict[str, float]
    worst_position: str
    recovery_time_est_days: int

class StressTester:
    SCENARIOS = [
        StressScenario("2015_BR_CRISIS", "Impeachment + downgrade S&P",
            {"USDBRL": 0.30, "DI_PRE_1Y": 0.04, "DI_PRE_5Y": 0.03,
             "IBOVESPA": -0.25, "CDS_BR_5Y": 0.015, "NTN_B_5Y": -0.08},
            0.05, "2015 BR Crisis"),
        StressScenario("2020_COVID", "Pandemia COVID-19 março 2020",
            {"USDBRL": 0.20, "DI_PRE_1Y": 0.02, "IBOVESPA": -0.35,
             "VIX": 2.0, "SP500": -0.30, "UST_10Y": -0.01, "OIL_WTI": -0.50},
            0.02, "2020 COVID"),
        StressScenario("EM_TAPER_TANTRUM", "Taper Tantrum 2013",
            {"USDBRL": 0.15, "DI_PRE_1Y": 0.02, "DI_PRE_5Y": 0.025, "UST_10Y": 0.01},
            0.08, "2013 Taper Tantrum"),
        StressScenario("BR_FISCAL_CRISIS", "Furo de teto de gastos",
            {"USDBRL": 0.25, "DI_PRE_1Y": 0.05, "DI_PRE_5Y": 0.04,
             "NTN_B_5Y": -0.12, "CDS_BR_5Y": 0.02, "IBOVESPA": -0.20},
            0.10, "2022 BR Fiscal Scare"),
        StressScenario("US_RECESSION", "Hard landing americano",
            {"SP500": -0.25, "UST_10Y": -0.015, "US_HY_OAS": 0.03,
             "VIX": 1.5, "USDBRL": 0.10},
            0.10, "2008 GFC lite"),
        StressScenario("GLOBAL_RISK_OFF", "Cisne negro geopolítico",
            {"USDBRL": 0.20, "IBOVESPA": -0.20, "SP500": -0.15, "VIX": 2.5,
             "GOLD": 0.10, "CDS_BR_5Y": 0.015, "OIL_WTI": -0.20},
            0.05, "Generic tail event"),
    ]
    
    def run_scenario(self, positions, scenario) -> StressResult: ...
    def run_all_scenarios(self, positions) -> list[StressResult]: ...
    def historical_replay(self, positions, start, end) -> StressResult: ...
    def reverse_stress(self, positions, max_loss_pct=0.10) -> list[StressScenario]: ...
```

## 3. src/risk/limits.py — Sistema de Limites

```python
@dataclass
class RiskLimit:
    name: str
    limit_type: str      # VAR, POSITION, LOSS, LEVERAGE, CONCENTRATION
    value: float
    current: float
    utilization: float
    is_breached: bool
    severity: str        # INFO, WARNING, CRITICAL

class RiskLimitsManager:
    DEFAULT_LIMITS = {
        "PORTFOLIO_VAR_95": {"type": "VAR", "value": 0.02},
        "PORTFOLIO_VAR_99": {"type": "VAR", "value": 0.035},
        "MAX_DRAWDOWN": {"type": "LOSS", "value": -0.10},
        "DAILY_LOSS_LIMIT": {"type": "LOSS", "value": -0.015},
        "WEEKLY_LOSS_LIMIT": {"type": "LOSS", "value": -0.03},
        "MAX_LEVERAGE": {"type": "LEVERAGE", "value": 3.0},
        "MAX_SINGLE_POSITION": {"type": "CONCENTRATION", "value": 0.15},
        "MAX_ASSET_CLASS": {"type": "CONCENTRATION", "value": 0.40},
        "MAX_COUNTRY_BR": {"type": "CONCENTRATION", "value": 0.60},
    }
    
    def check_all_limits(self, portfolio_state: dict) -> list[RiskLimit]: ...
    def check_pre_trade(self, proposed_trade, current_portfolio) -> tuple[bool, list[str]]: ...
    def get_available_risk_budget(self, current_portfolio) -> dict: ...
```

## 4. Rotas API: src/api/routes/risk.py

```
GET /api/v1/risk/var?method=HISTORICAL&confidence=0.95
GET /api/v1/risk/stress
GET /api/v1/risk/limits
GET /api/v1/risk/dashboard → resumo completo
```

## 5. Tests: tests/test_risk/

- test_var.py: historical_var, parametric_var com retornos conhecidos
- test_stress.py: run_scenario com posição simples
- test_limits.py: check_all_limits detecta breach

═══ FIM DO PROMPT 10 ═══

# □ pytest tests/test_risk/ -v
# □ API: GET /api/v1/risk/dashboard retorna 200


################################################################################
##                                                                            ##
##  ETAPA 11 — PORTFOLIO CONSTRUCTION & OPTIMIZATION                         ##
##  Tempo: ~35 min | Risk parity, Black-Litterman, position sizing           ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 11 ═══

No projeto macro-fund-system, implemente Portfolio Construction em src/risk/portfolio/.

Referências: Black & Litterman (1992); Maillard, Roncalli & Teïletche (2010) Risk Parity; Roncalli (2014).

## 1. src/risk/portfolio/optimizer.py

```python
@dataclass
class PortfolioTarget:
    instrument: str
    target_weight: float
    target_notional: float
    current_weight: float
    current_notional: float
    trade_needed: float
    strategy_attribution: dict[str, float]

class PortfolioOptimizer:
    def __init__(self, aum: float = 100_000_000, risk_budget_pct: float = 0.10): ...
    
    def signal_weighted(self, signals: list[AggregatedSignal],
                        risk_per_unit: dict[str, float]) -> list[PortfolioTarget]: ...
    
    def risk_parity(self, instruments: list[str], cov_matrix: np.ndarray,
                    risk_budget: dict[str, float] = None) -> list[PortfolioTarget]:
        """RC_i = w_i*(Σw)_i / σ_p = budget_i. Resolve via scipy.minimize."""
        ...
    
    def black_litterman(self, market_caps, cov_matrix, views, 
                        view_confidences, tau=0.05) -> list[PortfolioTarget]:
        """BL: E[r] = [(τΣ)⁻¹ + P'Ω⁻¹P]⁻¹[(τΣ)⁻¹π + P'Ω⁻¹Q]"""
        ...
    
    def mean_variance(self, expected_returns, cov_matrix, 
                      constraints=None) -> list[PortfolioTarget]: ...
    
    def apply_constraints(self, targets, limits_manager) -> list[PortfolioTarget]: ...
    def compute_rebalance_trades(self, targets, current) -> list[dict]: ...
```

## 2. src/risk/portfolio/position_sizer.py

```python
class PositionSizer:
    def vol_target(self, instrument, signal_size, target_vol=0.10, 
                   instrument_vol=None) -> float: ...
    def fractional_kelly(self, expected_return, volatility, 
                         fraction=0.25) -> float: ...
    def risk_budget_size(self, signal_confidence, risk_budget, 
                         instrument_var) -> float: ...
```

## 3. Nova tabela: src/core/models/portfolio_state.py

```
id: UUID, PK
timestamp: DateTime(timezone=True), NOT NULL
instrument: String(50), NOT NULL
direction: String(10)
notional: Float, NOT NULL
weight: Float
entry_price: Float
current_price: Float
unrealized_pnl: Float
realized_pnl: Float
strategy_attribution_json: JSON
risk_contribution: Float
metadata_json: JSON
created_at: DateTime(timezone=True), server_default=now()
```
Index: (timestamp DESC, instrument). Gere Alembic migration.

## 4. Rota API: src/api/routes/portfolio.py

```
GET /api/v1/portfolio/current → posições, PnL, risk contribution
GET /api/v1/portfolio/target → portfolio target
GET /api/v1/portfolio/rebalance-trades → trades necessários
GET /api/v1/portfolio/attribution → PnL por estratégia e ativo
```

## 5. Tests: tests/test_risk/test_portfolio.py

- Test signal_weighted produz targets na direção dos sinais
- Test risk_parity: contribuições de risco ~iguais
- Test apply_constraints respeita max_leverage
- Test compute_rebalance_trades

═══ FIM DO PROMPT 11 ═══

# □ pytest tests/test_risk/test_portfolio.py -v
# □ alembic upgrade head (tabela portfolio_state)
# □ API: GET /api/v1/portfolio/current retorna 200


################################################################################
##                                                                            ##
##  ETAPA 12 — PRODUCTION ORCHESTRATION (DAGSTER)                            ##
##  Tempo: ~30 min | DAGs de produção para todo o pipeline                   ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 12 ═══

No projeto macro-fund-system, implemente orquestração com Dagster em src/orchestration/. Referência: Data Architecture Blueprint seção 13 (Scheduling Matrix).

## 1. Adicione ao pyproject.toml:

```toml
[project.optional-dependencies]
orchestration = ["dagster>=1.6", "dagster-webserver>=1.6", "dagster-postgres>=0.22"]
```

## 2. Adicione ao docker-compose.yml serviço dagster-webserver (port 3001).

## 3. src/orchestration/assets.py — Dagster Assets

```python
import dagster as dg
from datetime import date

# ═══ BRONZE LAYER ═══
@dg.asset(group_name="bronze", 
          automation_condition=dg.AutomationCondition.on_cron("0 9 * * 1-5"))
def bcb_sgs_data(context): ...

@dg.asset(group_name="bronze", automation_condition=dg.AutomationCondition.on_cron("0 9 * * 1"))
def bcb_focus_data(context): ...

@dg.asset(group_name="bronze", automation_condition=dg.AutomationCondition.on_cron("0 8 * * 1-5"))
def fred_data(context): ...

@dg.asset(group_name="bronze", automation_condition=dg.AutomationCondition.on_cron("30 20 * * 1-5"))
def b3_market_data(context): ...

@dg.asset(group_name="bronze", automation_condition=dg.AutomationCondition.on_cron("0 18 * * 1-5"))
def yahoo_market_data(context): ...

@dg.asset(group_name="bronze", automation_condition=dg.AutomationCondition.on_cron("30 15 * * 1"))
def cftc_positioning_data(context): ...

# ═══ SILVER LAYER ═══
@dg.asset(group_name="silver", deps=[bcb_sgs_data, fred_data, b3_market_data])
def silver_transforms(context): ...

# ═══ AGENTS ═══
@dg.asset(group_name="agents", deps=[silver_transforms])
def inflation_agent_output(context): ...

@dg.asset(group_name="agents", deps=[silver_transforms])
def monetary_policy_agent_output(context): ...

@dg.asset(group_name="agents", deps=[silver_transforms])
def fiscal_agent_output(context): ...

@dg.asset(group_name="agents", deps=[silver_transforms])
def fx_equilibrium_agent_output(context): ...

@dg.asset(group_name="agents", 
          deps=[inflation_agent_output, monetary_policy_agent_output,
                fiscal_agent_output, fx_equilibrium_agent_output])
def cross_asset_agent_output(context): ...

# ═══ SIGNALS & PORTFOLIO ═══
@dg.asset(group_name="signals", deps=[cross_asset_agent_output])
def strategy_signals(context):
    """Roda todas as estratégias e gera sinais."""
    ...

@dg.asset(group_name="signals", deps=[strategy_signals, cross_asset_agent_output])
def aggregated_signals(context):
    """Agrega sinais por instrumento."""
    ...

@dg.asset(group_name="portfolio", deps=[aggregated_signals])
def portfolio_targets(context):
    """Calcula portfolio target."""
    ...

@dg.asset(group_name="risk", deps=[portfolio_targets])
def risk_metrics(context):
    """Calcula VaR, stress tests, limites."""
    ...

@dg.asset(group_name="reporting", deps=[risk_metrics, aggregated_signals])
def daily_report(context):
    """Gera relatório diário."""
    ...
```

## 4. src/orchestration/definitions.py

```python
import dagster as dg
from src.orchestration.assets import *

defs = dg.Definitions(
    assets=[bcb_sgs_data, bcb_focus_data, fred_data, b3_market_data,
            yahoo_market_data, cftc_positioning_data, silver_transforms,
            inflation_agent_output, monetary_policy_agent_output,
            fiscal_agent_output, fx_equilibrium_agent_output,
            cross_asset_agent_output, strategy_signals, aggregated_signals,
            portfolio_targets, risk_metrics, daily_report],
)
```

## 5. Makefile targets:

```makefile
dagster:
	dagster dev -f src/orchestration/definitions.py -p 3001

dagster-run-all:
	dagster asset materialize --select '*' -f src/orchestration/definitions.py
```

## 6. Tests: tests/test_orchestration/test_assets.py

- Test que todos os assets estão registrados
- Test dependências estão corretas (silver depende de bronze, agents de silver, etc.)

═══ FIM DO PROMPT 12 ═══

# □ make dagster (Dagster UI em http://localhost:3001)
# □ Verificar grafo de dependências na UI


################################################################################
##                                                                            ##
##  ETAPA 13 — MONITORING & ALERTING (GRAFANA)                               ##
##  Tempo: ~25 min | Dashboards de monitoramento e alertas                   ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 13 ═══

No projeto macro-fund-system, implemente monitoramento com Grafana e alertas. Referência: Data Architecture Blueprint seção 14.

## 1. Adicione ao docker-compose.yml:

```yaml
grafana:
  image: grafana/grafana:latest
  ports:
    - "3002:3000"
  environment:
    GF_SECURITY_ADMIN_PASSWORD: macrofund_dev
    GF_INSTALL_PLUGINS: grafana-clock-panel
  volumes:
    - grafana_data:/var/lib/grafana
    - ./infrastructure/grafana/provisioning:/etc/grafana/provisioning
    - ./infrastructure/grafana/dashboards:/var/lib/grafana/dashboards
  depends_on:
    - timescaledb
```

## 2. infrastructure/grafana/provisioning/datasources/timescaledb.yml

Datasource tipo postgres apontando para timescaledb:5432, database macrofund, com timescaledb: true.

## 3. infrastructure/grafana/dashboards/ — 4 dashboards JSON provisionados:

### a) pipeline_health.json
Painéis: última execução de cada conector, records ingeridos/dia (30d), data quality score, alertas de séries stale.

### b) signal_overview.json
Painéis: sinais agregados atuais (table), heatmap estratégia × classe, signal flips (30d), conviction distribution.

### c) risk_dashboard.json
Painéis: VaR 95%/99% (timeseries 252d), stress results (bar chart), utilização de limites (gauges), drawdown, concentração (pie).

### d) portfolio_performance.json
Painéis: equity curve, rolling Sharpe 252d, monthly heatmap, attribution por estratégia (stacked bar), PnL diário.

## 4. src/monitoring/alerts.py

```python
class AlertManager:
    ALERT_RULES = [
        {"name": "STALE_DATA", "condition": "series >3 biz days stale", "severity": "WARNING"},
        {"name": "VAR_BREACH", "condition": "VaR > 80% limite", "severity": "WARNING"},
        {"name": "VAR_CRITICAL", "condition": "VaR > 95% limite", "severity": "CRITICAL"},
        {"name": "DRAWDOWN_WARNING", "condition": "drawdown > 5%", "severity": "WARNING"},
        {"name": "DRAWDOWN_CRITICAL", "condition": "drawdown > 8%", "severity": "CRITICAL"},
        {"name": "LIMIT_BREACH", "condition": "qualquer limite violado", "severity": "CRITICAL"},
        {"name": "SIGNAL_FLIP", "condition": "sinal agregado mudou direção", "severity": "INFO"},
        {"name": "CONVICTION_SURGE", "condition": "convicção >30% em 1 dia", "severity": "INFO"},
        {"name": "PIPELINE_FAILURE", "condition": "DAG falhou", "severity": "CRITICAL"},
        {"name": "AGENT_STALE", "condition": "agente >1 dia útil sem rodar", "severity": "WARNING"},
    ]
    
    def __init__(self, slack_webhook: str = None, email_config: dict = None): ...
    async def check_all_rules(self) -> list[dict]: ...
    async def send_alert(self, alert: dict): ...
    async def send_daily_digest(self): ...
```

## 5. Rota API: src/api/routes/monitoring.py

```
GET /api/v1/monitoring/alerts
GET /api/v1/monitoring/pipeline-status
GET /api/v1/monitoring/system-health
POST /api/v1/monitoring/test-alert
```

═══ FIM DO PROMPT 13 ═══

# □ docker compose up grafana → http://localhost:3002
# □ 4 dashboards visíveis


################################################################################
##                                                                            ##
##  ETAPA 14 — DASHBOARD v2: STRATEGY & RISK PAGES                          ##
##  Tempo: ~35 min | Novas páginas React para o dashboard                    ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 14 ═══

No projeto macro-fund-system, expanda o Dashboard React (Fase 1, em frontend/) com 5 novas páginas.

## 1. frontend/src/pages/StrategiesPage.tsx
Tabela de todas as estratégias: ID, classe, direção, confiança, z-score. Click expande: backtest metrics, equity curve (recharts), parâmetros.

## 2. frontend/src/pages/SignalsPage.tsx
Sinais agregados por instrumento (cores verde/vermelho/cinza). Heatmap estratégias × classes. Timeline de flips (30d).

## 3. frontend/src/pages/RiskPage.tsx
Gauge meters: VaR 95%, VaR 99%, Drawdown, Leverage. Stress test bar chart. Tabela de limites. Concentração pie chart.

## 4. frontend/src/pages/PortfolioPage.tsx
Posições atuais com PnL e risk contribution. Equity curve. Monthly returns heatmap. Attribution por estratégia. Trades sugeridos.

## 5. frontend/src/pages/AgentsPage.tsx
Cards por agente (Inflation, Monetary Policy, Fiscal, FX, Cross-Asset). Sinal, confiança, drivers, risks. Narrativa do Cross-Asset Agent.

## 6. Atualize App.tsx com rotas e sidebar navigation. Use recharts + Tailwind CSS. Fetch da API FastAPI.

═══ FIM DO PROMPT 14 ═══

# □ npm run dev → http://localhost:3000
# □ 5 novas páginas renderizam com dados da API


################################################################################
##                                                                            ##
##  ETAPA 15 — DAILY REPORT GENERATOR                                        ##
##  Tempo: ~20 min | Relatório diário automatizado                           ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 15 ═══

No projeto macro-fund-system, implemente src/reporting/daily_report.py.

## 1. src/reporting/daily_report.py

```python
class DailyReportGenerator:
    """
    Seções: MARKET SNAPSHOT, REGIME ASSESSMENT, AGENT VIEWS, SIGNAL SUMMARY,
    PORTFOLIO STATUS, RISK METRICS, ACTION ITEMS.
    """
    async def generate(self, as_of_date: date) -> dict: ...
    async def to_markdown(self, report: dict) -> str: ...
    async def to_html(self, report: dict) -> str: ...
    async def send_email(self, report: dict, recipients: list[str]): ...
    async def send_slack(self, report: dict, channel: str): ...
```

## 2. Formato do relatório (exemplo):

```
═══════════════════════════════════════════════
 MACRO FUND — DAILY REPORT — {date}
═══════════════════════════════════════════════

MARKET SNAPSHOT
  USDBRL: 5.82 (-0.3%) | DI Jan27: 14.85% (+5bps) | UST 10Y: 4.52% (-2bps)
  IBOV: 128,450 (+0.8%) | S&P: 6,120 (+0.2%) | VIX: 15.2 | CDS 5Y: 145bps

MACRO REGIME: REFLATION (62%)
  Growth: improving | Inflation: rising

AGENT VIEWS:
  Inflation: HAWKISH (0.65) | MonPol: TIGHTER (+0.40) | Fiscal: NEUTRAL (-0.10)
  FX: BRL CHEAP (-0.55) | Cross-Asset: CAUTIOUS

TOP SIGNALS (by conviction):
  1. FX-01 BEER → LONG BRL (z:-1.8, conf:0.75)
  2. CUPOM-01 CIP → RECEIVE BASIS 6M (z:2.1, conf:0.70)
  ...

PORTFOLIO: AUM $100M | PnL Today +$120K (+0.12%) | MTD +$850K
  Leverage 1.8x | VaR95 1.2% | Max DD -2.3%

RISK ALERTS: VaR at 78% of limit

ACTIONS: Reduce DOL short $2M, Add NTN-B 2030 $3M, Monitor COPOM in 5 days
═══════════════════════════════════════════════
```

## 3. Rota API:

```
GET /api/v1/reports/daily?date=2026-02-19
GET /api/v1/reports/daily/latest
POST /api/v1/reports/daily/send
```

═══ FIM DO PROMPT 15 ═══

# □ GET /api/v1/reports/daily/latest retorna relatório


################################################################################
##                                                                            ##
##  ETAPA 16 — API EXPANSION & WEBSOCKET                                     ##
##  Tempo: ~20 min | Endpoints adicionais + WebSocket live updates           ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 16 ═══

No projeto macro-fund-system, expanda a API com endpoints e WebSocket.

## 1. src/api/routes/backtest.py

```
POST /api/v1/backtest/run → {strategy_id, start_date, end_date, params}
GET /api/v1/backtest/results?strategy_id=FX-01
POST /api/v1/backtest/portfolio → {strategy_ids, weights, start_date, end_date}
GET /api/v1/backtest/comparison?ids=FX-01,FX-02,FX-03
```

## 2. src/api/routes/strategies.py

```
GET /api/v1/strategies → lista com metadata
GET /api/v1/strategies/{strategy_id} → detalhes
GET /api/v1/strategies/{strategy_id}/signal/latest
GET /api/v1/strategies/{strategy_id}/signal/history?start=2024-01-01
PUT /api/v1/strategies/{strategy_id}/params → atualiza parâmetros
```

## 3. src/api/websocket.py

```python
class ConnectionManager:
    def __init__(self): self.active_connections: list[WebSocket] = []
    async def connect(self, ws: WebSocket): ...
    def disconnect(self, ws: WebSocket): ...
    async def broadcast(self, message: dict): ...

# ws://localhost:8000/ws/signals → novos sinais
# ws://localhost:8000/ws/portfolio → updates de portfolio
# ws://localhost:8000/ws/alerts → alertas em tempo real
```

## 4. Atualize src/api/main.py com todos os routers. Swagger tags: Health, Macro, Curves, Market Data, Flows, Agents, Signals, Risk, Portfolio, Backtest, Strategies, Reports, Monitoring.

═══ FIM DO PROMPT 16 ═══

# □ http://localhost:8000/docs → todos os endpoints organizados
# □ wscat -c ws://localhost:8000/ws/alerts → funcional


################################################################################
##                                                                            ##
##  ETAPA 17 — COMPREHENSIVE TESTING & CI/CD                                 ##
##  Tempo: ~25 min | Testes de integração + CI pipeline                      ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 17 ═══

No projeto macro-fund-system, implemente testes de integração e CI/CD.

## 1. tests/integration/test_full_pipeline.py

```python
@pytest.mark.integration
async def test_full_pipeline():
    """End-to-end: DB → transforms → agents → strategies → signals → portfolio → risk → report."""
    ...

@pytest.mark.integration
async def test_api_endpoints():
    """Testa todos os endpoints principais retornam 200."""
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        for endpoint in ["/health", "/api/v1/macro/dashboard", "/api/v1/signals/aggregated",
                         "/api/v1/risk/dashboard", "/api/v1/portfolio/current",
                         "/api/v1/strategies", "/api/v1/agents/cross-asset/latest"]:
            r = await client.get(endpoint)
            assert r.status_code == 200, f"{endpoint} failed"
```

## 2. tests/integration/test_backtest_suite.py

```python
@pytest.mark.integration
async def test_backtest_all_strategies():
    """Backtest 1 ano para cada estratégia — sanity checks."""
    config = BacktestConfig(start_date=date(2023,1,1), end_date=date(2024,1,1), point_in_time=True)
    engine = BacktestEngine(config)
    
    for strategy_id in StrategyRegistry.list_all():
        strategy = StrategyRegistry.instantiate(strategy_id)
        result = await engine.run_single(strategy)
        assert -1.0 < result.annualized_return < 2.0
        assert result.annualized_vol > 0
        assert result.max_drawdown <= 0
        assert 0 <= result.win_rate <= 1
```

## 3. Atualize .github/workflows/ci.yml:

```yaml
name: CI
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.11"}
      - run: pip install ruff && ruff check src/

  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.11"}
      - run: pip install -e ".[dev]"
      - run: pytest tests/ -v --ignore=tests/integration -k "not integration" --cov=src

  integration-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    services:
      timescaledb:
        image: timescale/timescaledb:latest-pg16
        env: {POSTGRES_DB: macrofund, POSTGRES_USER: macrofund, POSTGRES_PASSWORD: macrofund_dev}
        ports: ["5432:5432"]
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.11"}
      - run: pip install -e ".[dev,orchestration]"
      - run: alembic upgrade head && python scripts/seed_instruments.py
      - run: pytest tests/integration/ -v -m integration
```

═══ FIM DO PROMPT 17 ═══

# □ pytest tests/ -v --ignore=tests/integration → PASS
# □ pytest tests/integration/ -v -m integration → PASS (requer serviços up)


################################################################################
##                                                                            ##
##  ETAPA 18 — VERIFICATION & GIT COMMIT FINAL                               ##
##  Tempo: ~15 min | Verificação completa + commit                           ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 18 ═══

No projeto macro-fund-system, finalize a Fase 2:

## 1. scripts/verify_phase2.py

Script que verifica TODO o sistema Fase 2 e imprime relatório:

```
═══════════════════════════════════════════════════════
 MACRO FUND — PHASE 2 VERIFICATION
═══════════════════════════════════════════════════════

 Strategy Framework:
   Base classes:        ✅ BaseStrategy, StrategySignal, BacktestResult
   Registry:            ✅ {n} strategies registered
   By class:            ✅ FX:5 | RATES:6 | INF:3 | CUPOM:2 | SOV:3 | CROSS:2+

 Backtesting Engine:
   Engine v2:           ✅ Single + Portfolio + Walk-forward
   Cost Model:          ✅ 12 instruments
   Analytics:           ✅ Sharpe, Sortino, Calmar, DD, tearsheet

 Agents:
   Cross-Asset Agent:   ✅ Regime detection + LLM narrative
   NLP Pipeline:        ✅ COPOM + FOMC scraper + hawk/dove scoring
   Documents table:     ✅ nlp_documents

 Signal Aggregation:
   Aggregator:          ✅ Confidence-weighted + crowding penalty
   Monitor:             ✅ Flips, surges, divergence

 Risk Engine:
   VaR Calculator:      ✅ Historical, Parametric, Monte Carlo
   Stress Tester:       ✅ {n} scenarios
   Limits Manager:      ✅ {n} limits active

 Portfolio Construction:
   Optimizer:           ✅ Signal-weighted, Risk Parity, Black-Litterman
   Position Sizer:      ✅ Vol target, Kelly, Risk budget

 Orchestration:        ✅ Dagster ({n} assets)
 Monitoring:           ✅ Grafana (4 dashboards) + AlertManager ({n} rules)
 API:                  ✅ {n} endpoints + 3 WebSocket channels
 Dashboard:            ✅ {n} React pages
 Tests:                ✅ {passed}/{total} passed

═══════════════════════════════════════════════════════
 STATUS: ✅ PASS
 Ready for Phase 3 (Production Deployment & Live Trading)
═══════════════════════════════════════════════════════
```

## 2. Atualize README.md com seção Fase 2: overview, estratégias (tabela), risk engine, orchestration, e "Next Phase 3".

## 3. Git commit:

```bash
git add .
git commit -m "Phase 2: Strategy engine (22+ strategies), risk management, portfolio construction, NLP pipeline, Dagster orchestration, Grafana monitoring"
```

═══ FIM DO PROMPT 18 ═══

# VERIFICAÇÃO FINAL:
# □ python scripts/verify_phase2.py → STATUS: PASS
# □ git log --oneline (2 commits: Phase 0 + Phase 2)
# □ http://localhost:8000/docs (todos os endpoints)
# □ http://localhost:3000 (Dashboard com todas as páginas)
# □ http://localhost:3001 (Dagster UI com DAGs)
# □ http://localhost:3002 (Grafana com 4 dashboards)
# □ pytest tests/ -v --ignore=tests/integration (unit tests PASS)


################################################################################
##                                                                            ##
##  ═══════════════════════════════════════════════════════════════════════    ##
##  FIM DA FASE 2 — STRATEGY ENGINE, RISK & PORTFOLIO COMPLETOS              ##
##  ═══════════════════════════════════════════════════════════════════════    ##
##                                                                            ##
##  CONSTRUÍDO:                                                               ##
##  ✅ 22+ estratégias (FX:5, RATES:6, INF:3, CUPOM:2, SOV:3, CROSS:2+)     ##
##  ✅ Backtesting Engine v2 (portfolio-level, custos, walk-forward)          ##
##  ✅ Cross-Asset Agent com regime detection (HMM 4 estados)                 ##
##  ✅ NLP Pipeline (COPOM + FOMC scraper, hawk/dove scoring)                 ##
##  ✅ Signal Aggregation Layer (crowding penalty, staleness discount)        ##
##  ✅ Risk Engine (VaR 3 métodos, stress 6 cenários, 9 limites)             ##
##  ✅ Portfolio Construction (risk parity, Black-Litterman, mean-variance)   ##
##  ✅ Dagster orchestration (16+ assets, full dependency graph)              ##
##  ✅ Grafana monitoring (4 dashboards provisionados)                        ##
##  ✅ Alert system (10 regras, Slack + email)                                ##
##  ✅ Daily report generator (Markdown + HTML + email)                       ##
##  ✅ Dashboard React expandido (6 páginas)                                  ##
##  ✅ API expandida (30+ endpoints + 3 WebSocket channels)                   ##
##  ✅ CI/CD com testes unitários e de integração                             ##
##                                                                            ##
##  PRÓXIMO: Fase 3 — Production Deployment & Live Trading                    ##
##  - Bloomberg/Refinitiv real-time data feeds                                ##
##  - Execution engine (FIX protocol, B3/CME gateway)                         ##
##  - Paper trading (simulação com preços reais)                              ##
##  - Compliance & audit logging                                              ##
##  - Multi-environment (dev → staging → prod)                                ##
##  - Kubernetes deployment                                                   ##
##  - Performance optimization & caching                                      ##
##                                                                            ##
################################################################################

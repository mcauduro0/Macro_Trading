# ════════════════════════════════════════════════════════════════════
# MACRO HEDGE FUND AI SYSTEM — GUIA COMPLETO CLAUDE CODE
# ════════════════════════════════════════════════════════════════════
# FASE 1: QUANTITATIVE MODELS, AGENTS & BACKTESTING (20 ETAPAS)
# ════════════════════════════════════════════════════════════════════
#
# PRÉ-REQUISITO: Fase 0 completa (infraestrutura de dados funcionando)
# Verificar com: cd macro-fund-system && make verify
#
# COMO USAR:
# 1. Copie o bloco entre "═══ INÍCIO DO PROMPT ═══" e "═══ FIM DO PROMPT ═══"
# 2. Cole no Claude Code e aguarde execução completa
# 3. Valide o resultado antes de prosseguir
#
# O QUE SERÁ CONSTRUÍDO NESTA FASE:
# - Agent Framework (base para todos os agentes de IA)
# - 5 Agentes Analíticos especializados
# - Backtesting Engine com point-in-time correctness
# - 8 Estratégias de Trading iniciais
# - Signal Aggregation & Portfolio Construction
# - Risk Management Engine
# - API endpoints para agents/signals/strategies
# - Verificação end-to-end
#
# TEMPO TOTAL ESTIMADO: 10-16 horas de trabalho
# ════════════════════════════════════════════════════════════════════


################################################################################
##                                                                            ##
##  ETAPA 1 — AGENT FRAMEWORK & DATABASE SCHEMAS                             ##
##  Tempo: ~25 min | Infraestrutura base para todos os agentes                ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 1 ═══

Estou trabalhando no projeto macro-fund-system (já tem Fase 0 completa com TimescaleDB, 11 conectores, 200+ séries macro, FastAPI API). Agora início a Fase 1: Quantitative Models & Analytical Agents.

Nesta etapa, crie a infraestrutura base do Agent Framework e os schemas adicionais necessários.

## 1. Novos diretórios em src/agents/:

```
src/agents/
├── __init__.py
├── base.py                 # BaseAgent abstract class
├── registry.py             # Agent registry & orchestration
├── inflation/
│   ├── __init__.py
│   ├── agent.py            # InflationAgent
│   ├── models.py           # Phillips Curve, IPCA bottom-up, etc.
│   └── features.py         # Feature engineering for inflation
├── monetary/
│   ├── __init__.py
│   ├── agent.py            # MonetaryPolicyAgent
│   ├── models.py           # Taylor Rule, Kalman Filter, reaction function
│   └── features.py
├── fiscal/
│   ├── __init__.py
│   ├── agent.py            # FiscalAgent
│   ├── models.py           # DSA model, fiscal impulse
│   └── features.py
├── fx/
│   ├── __init__.py
│   ├── agent.py            # FxEquilibriumAgent
│   ├── models.py           # BEER model, fair value
│   └── features.py
└── cross_asset/
    ├── __init__.py
    ├── agent.py            # CrossAssetAgent
    └── models.py           # Regime detection, correlation analysis
```

## 2. src/agents/base.py — BaseAgent

```python
from abc import ABC, abstractmethod
from datetime import date, datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class SignalDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"

class SignalStrength(str, Enum):
    STRONG = "STRONG"         # High conviction: confidence >= 0.75
    MODERATE = "MODERATE"     # Medium conviction: 0.50 <= confidence < 0.75
    WEAK = "WEAK"             # Low conviction: 0.25 <= confidence < 0.50
    NO_SIGNAL = "NO_SIGNAL"   # Below threshold: confidence < 0.25

@dataclass
class AgentSignal:
    """Output of an agent's analysis for a specific theme/instrument."""
    signal_id: str                      # e.g., "INFLATION_BR_IPCA_12M"
    agent_id: str                       # e.g., "inflation_agent_v1"
    timestamp: datetime                 # when signal was generated
    as_of_date: date                    # point-in-time reference date
    direction: SignalDirection           # LONG, SHORT, NEUTRAL
    strength: SignalStrength             # STRONG, MODERATE, WEAK, NO_SIGNAL
    confidence: float                   # 0.0 to 1.0
    value: float                        # numerical signal value (e.g., z-score, model output)
    horizon_days: int                   # signal horizon in days (21=1M, 63=1Q, 252=1Y)
    metadata: dict = field(default_factory=dict)  # model-specific details
    # metadata examples: {"model": "phillips_curve", "inputs": {...}, "diagnostics": {...}}

@dataclass
class AgentReport:
    """Complete output from an agent run — narrative + signals."""
    agent_id: str
    as_of_date: date
    generated_at: datetime
    signals: list[AgentSignal]
    narrative: str                      # Human-readable analysis summary
    model_diagnostics: dict             # Model fit stats, feature importances, etc.
    data_quality_flags: list[str]       # Any data issues encountered

class BaseAgent(ABC):
    """Abstract base class for all analytical agents."""

    def __init__(self, agent_id: str, agent_name: str):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.logger = get_logger(f"agent.{agent_id}")

    @abstractmethod
    def load_data(self, as_of_date: date) -> dict[str, Any]:
        """Load all required data for analysis, respecting point-in-time.
        Must only use data with release_time <= as_of_date."""

    @abstractmethod
    def compute_features(self, data: dict) -> dict[str, Any]:
        """Transform raw data into model features."""

    @abstractmethod
    def run_models(self, features: dict) -> list[AgentSignal]:
        """Execute quantitative models and generate signals."""

    @abstractmethod
    def generate_narrative(self, signals: list[AgentSignal], features: dict) -> str:
        """Generate human-readable analysis."""

    def run(self, as_of_date: date) -> AgentReport:
        """Execute full agent pipeline: load → features → models → narrative.
        This is the main entry point. Template Method pattern."""
        self.logger.info(f"Running {self.agent_name} as_of {as_of_date}")
        start = datetime.utcnow()

        # 1. Load data (point-in-time)
        data = self.load_data(as_of_date)
        data_flags = self._check_data_quality(data)

        # 2. Compute features
        features = self.compute_features(data)

        # 3. Run models
        signals = self.run_models(features)

        # 4. Generate narrative
        narrative = self.generate_narrative(signals, features)

        # 5. Persist signals to database
        self._persist_signals(signals)

        elapsed = (datetime.utcnow() - start).total_seconds()
        self.logger.info(f"{self.agent_name} complete: {len(signals)} signals, {elapsed:.1f}s")

        return AgentReport(
            agent_id=self.agent_id,
            as_of_date=as_of_date,
            generated_at=datetime.utcnow(),
            signals=signals,
            narrative=narrative,
            model_diagnostics={},
            data_quality_flags=data_flags,
        )

    def _check_data_quality(self, data: dict) -> list[str]:
        """Check loaded data for issues: missing values, staleness, etc."""
        flags = []
        for key, df in data.items():
            if hasattr(df, 'isna') and df.isna().sum().sum() > 0:
                flags.append(f"{key}: contains {df.isna().sum().sum()} missing values")
        return flags

    def _persist_signals(self, signals: list[AgentSignal]):
        """Save signals to the 'signals' hypertable in TimescaleDB.
        Uses sync database session. ON CONFLICT DO NOTHING."""
        # Insert each signal: time=timestamp, signal_id, value, confidence,
        # metadata_json=metadata, agent_id
        pass  # implement with actual DB insert

    def backtest_run(self, as_of_date: date) -> AgentReport:
        """Same as run() but using point-in-time data strictly.
        Used by backtesting engine. Does NOT persist signals."""
        data = self.load_data(as_of_date)
        features = self.compute_features(data)
        signals = self.run_models(features)
        narrative = self.generate_narrative(signals, features)
        return AgentReport(
            agent_id=self.agent_id, as_of_date=as_of_date,
            generated_at=datetime.utcnow(), signals=signals,
            narrative=narrative, model_diagnostics={},
            data_quality_flags=[],
        )
```

## 3. src/agents/registry.py — Agent Orchestration

```python
class AgentRegistry:
    """Registry of all active agents. Manages execution order and dependencies."""

    _agents: dict[str, BaseAgent] = {}

    @classmethod
    def register(cls, agent: BaseAgent):
        cls._agents[agent.agent_id] = agent

    @classmethod
    def get(cls, agent_id: str) -> BaseAgent:
        return cls._agents[agent_id]

    @classmethod
    def run_all(cls, as_of_date: date) -> dict[str, AgentReport]:
        """Run all agents in dependency order. Returns dict of reports."""
        # Order: inflation → monetary → fiscal → fx → cross_asset
        order = ["inflation_agent", "monetary_agent", "fiscal_agent",
                 "fx_agent", "cross_asset_agent"]
        reports = {}
        for agent_id in order:
            if agent_id in cls._agents:
                reports[agent_id] = cls._agents[agent_id].run(as_of_date)
        return reports
```

## 4. Alembic migration for new tables:

Create a new migration that adds:

**agent_reports table** (regular table, not hypertable):
```
id: UUID PK
agent_id: String(50), NOT NULL
as_of_date: Date, NOT NULL
generated_at: DateTime(timezone=True), NOT NULL
signals_count: Integer
narrative: Text
model_diagnostics: JSON
data_quality_flags: JSON
created_at: DateTime(timezone=True), server_default=now()
```
Index: (agent_id, as_of_date DESC)

**strategy_signals table** (hypertable):
```
time: DateTime(timezone=True), PK part 1
strategy_id: String(50), PK part 2
instrument_ticker: String(50), NOT NULL
direction: String(10)   # LONG, SHORT, FLAT
target_weight: Float    # -1.0 to 1.0 (fraction of strategy notional)
confidence: Float       # 0.0 to 1.0
entry_level: Float, nullable
stop_loss: Float, nullable
take_profit: Float, nullable
metadata_json: JSON
agent_id: String(50)
created_at: DateTime(timezone=True), server_default=now()
```

**backtest_results table** (regular):
```
id: UUID PK
strategy_id: String(50), NOT NULL
run_date: DateTime(timezone=True), NOT NULL
start_date: Date, NOT NULL
end_date: Date, NOT NULL
total_return: Float
annualized_return: Float
annualized_vol: Float
sharpe_ratio: Float
max_drawdown: Float
calmar_ratio: Float
win_rate: Float
profit_factor: Float
num_trades: Integer
avg_holding_days: Float
parameters: JSON
equity_curve: JSON  # [{date, cumulative_return, drawdown}, ...]
monthly_returns: JSON  # [{month, return}, ...]
created_at: DateTime(timezone=True), server_default=now()
```
Index: (strategy_id, run_date DESC)

Run the migration: `alembic revision --autogenerate -m "add_agent_strategy_tables" && alembic upgrade head`

Also add the necessary SQLAlchemy ORM models in src/core/models/ (agent_reports.py, strategy_signals.py, backtest_results.py) and update __init__.py.

## 5. Helper: src/agents/data_loader.py

Utility to load point-in-time data for any agent:

```python
class PointInTimeDataLoader:
    """Load data respecting point-in-time constraints for backtesting."""

    def get_macro_series(self, series_id: str, as_of_date: date,
                         lookback_days: int = 3650) -> pd.DataFrame:
        """Load macro_series WHERE release_time <= as_of_date
        AND time >= as_of_date - lookback_days.
        For revised series, return only the latest revision available at as_of_date."""

    def get_latest_macro_value(self, series_id: str, as_of_date: date) -> float | None:
        """Return the most recent value for a series available at as_of_date."""

    def get_curve(self, curve_id: str, as_of_date: date) -> dict[int, float]:
        """Load most recent curve available at as_of_date. Returns {tenor_days: rate}."""

    def get_market_data(self, ticker: str, as_of_date: date,
                        lookback_days: int = 756) -> pd.DataFrame:
        """Load OHLCV for ticker WHERE time <= as_of_date."""

    def get_focus_expectations(self, indicator: str, as_of_date: date) -> pd.DataFrame:
        """Load Focus survey expectations available at as_of_date."""

    def get_flow_data(self, series_id: str, as_of_date: date,
                      lookback_days: int = 365) -> pd.DataFrame:
        """Load flow data available at as_of_date."""
```

Implement using sync database queries. This is the single data access layer used by ALL agents for both live execution and backtesting.

═══ FIM DO PROMPT 1 ═══

# VERIFICAÇÃO:
# □ alembic upgrade head (3 new tables created)
# □ SELECT * FROM information_schema.tables WHERE table_name LIKE '%agent%' OR table_name LIKE '%strategy%' OR table_name LIKE '%backtest%';
# □ python -c "from src.agents.base import BaseAgent, AgentSignal; print('OK')"


################################################################################
##                                                                            ##
##  ETAPA 2 — INFLATION AGENT                                                ##
##  Tempo: ~35 min | Modelos de inflação BR + US                              ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 2 ═══

No projeto macro-fund-system, implemente o Inflation Agent — o primeiro agente analítico completo. Este agente monitora inflação no Brasil e nos EUA e gera sinais sobre a trajetória inflacionária.

## Referencial Teórico:
- Phillips Curve (expectativas-aumentada): relação output gap → inflação (Friedman 1968, Lucas 1972)
- IPCA Bottom-Up: previsão por componentes (alimentação, administrados, serviços, industriais)
- Inflation Surprise: actual vs. expectativas Focus/Survey como leading indicator de repricing
- Persistence measures: núcleos, difusão, médias aparadas (BCB methodology)

## 1. src/agents/inflation/features.py

```python
class InflationFeatureEngine:
    """Compute all inflation-related features for the agent."""

    def __init__(self, data_loader: PointInTimeDataLoader):
        self.loader = data_loader

    def compute_brazil_features(self, as_of_date: date) -> dict:
        """
        Returns dict with all BR inflation features:

        # Current State
        "br_ipca_mom_latest": float,           # Latest IPCA MoM (%)
        "br_ipca_yoy_latest": float,           # Latest IPCA YoY (%)
        "br_ipca_core_ex3_yoy": float,         # Core EX3 YoY
        "br_ipca_core_ma_yoy": float,          # Core MA (trimmed mean) YoY
        "br_ipca_core_dp_yoy": float,          # Core DP (double-weighted) YoY
        "br_ipca_diffusion": float,            # Diffusion index (latest)
        "br_ipca15_mom_latest": float,         # IPCA-15 (leading indicator)
        "br_igpm_mom_latest": float,           # IGP-M (wholesale inflation)

        # Components (latest MoM %)
        "br_ipca_food_mom": float,
        "br_ipca_housing_mom": float,
        "br_ipca_transport_mom": float,
        "br_ipca_health_mom": float,
        "br_ipca_education_mom": float,
        "br_ipca_personal_mom": float,
        "br_ipca_communication_mom": float,
        "br_ipca_clothing_mom": float,
        "br_ipca_household_mom": float,

        # Dynamics (momentum & acceleration)
        "br_ipca_core_avg_3m_annualized": float,  # 3-month annualized core avg
        "br_ipca_core_avg_6m_annualized": float,  # 6-month annualized
        "br_ipca_acceleration": float,              # 3m ann. minus 12m (positive = accelerating)
        "br_ipca_diffusion_3m_avg": float,          # 3-month avg diffusion
        "br_ipca_services_trend": float,            # Services inflation 3m MA

        # Expectations
        "br_focus_ipca_cy_median": float,           # Focus current year IPCA median
        "br_focus_ipca_ny_median": float,           # Focus next year IPCA median
        "br_focus_ipca_12m_median": float,          # Focus 12-month-ahead
        "br_focus_ipca_cy_1w_change": float,        # Week-over-week change in Focus
        "br_bei_implied_1y": float,                 # Breakeven inflation 1Y (NTN-B curve if available)

        # Activity context (Phillips Curve inputs)
        "br_output_gap_proxy": float,               # Capacity utilization - long-term avg
        "br_unemployment_gap": float,               # Unemployment - NAIRU estimate (~9%)
        "br_fx_pass_through": float,                # USDBRL 3-month change (% — FX pass-through)
        "br_commodity_index_3m_chg": float,         # Commodity terms of trade change

        # Surprise
        "br_ipca_surprise_last": float,             # Last IPCA release - Focus median expectation
        "br_ipca_surprise_3m_avg": float,           # Average of last 3 surprises
        """

    def compute_us_features(self, as_of_date: date) -> dict:
        """
        Returns dict with all US inflation features:

        # Current State
        "us_cpi_yoy": float,
        "us_cpi_core_yoy": float,
        "us_pce_core_yoy": float,              # Fed's target metric
        "us_cpi_trimmed_mean_yoy": float,
        "us_cpi_median_yoy": float,
        "us_cpi_sticky_yoy": float,
        "us_ppi_yoy": float,

        # Dynamics
        "us_pce_core_3m_annualized": float,     # 3m SAAR
        "us_pce_core_6m_annualized": float,     # 6m SAAR
        "us_inflation_acceleration": float,     # 3m - 12m
        "us_cpi_services_ex_shelter": float,    # Supercore proxy

        # Expectations
        "us_michigan_1y": float,                # Michigan survey 1Y ahead
        "us_bei_5y": float,                     # 5Y breakeven
        "us_bei_10y": float,                    # 10Y breakeven
        "us_fwd_5y5y": float,                   # 5Y5Y forward

        # Context
        "us_output_gap_proxy": float,           # Capacity utilization gap
        "us_wage_growth_yoy": float,            # Average hourly earnings YoY
        "us_oil_yoy_chg": float,                # Oil price YoY change
        """

    def compute_all(self, as_of_date: date) -> dict:
        """Merge BR + US features."""
        return {**self.compute_brazil_features(as_of_date),
                **self.compute_us_features(as_of_date)}
```

## 2. src/agents/inflation/models.py

```python
class PhillipsCurveModel:
    """Expectations-augmented Phillips Curve for Brazil.
    π_t = π_e_t + α*(y_gap_t) + β*(fx_chg_t) + γ*(comm_chg_t) + ε
    Where: π=inflation, π_e=expectations, y_gap=output gap, fx=pass-through, comm=commodities.
    Estimated via OLS on trailing 10-year window."""

    def fit(self, features_history: pd.DataFrame) -> dict:
        """Fit Phillips Curve on historical features.
        Dependent var: br_ipca_core_ma_yoy
        Independent vars: br_focus_ipca_12m_median, br_output_gap_proxy,
                          br_fx_pass_through, br_commodity_index_3m_chg
        Returns: coefficients, R², residual std, t-stats"""

    def predict(self, features: dict) -> float:
        """Predict next 12M core inflation. Returns annualized %."""

    def signal(self, predicted: float, features: dict) -> AgentSignal:
        """Generate signal:
        - If predicted > Focus median + 0.3pp → SHORT (inflation higher than expected)
        - If predicted < Focus median - 0.3pp → LONG (inflation lower than expected)
        - Confidence = min(1.0, abs(predicted - focus_median) / 1.0)
        - direction context: SHORT = rates should go up = hawkish
        """

class IpcaBottomUpModel:
    """Bottom-up IPCA forecast by component group.
    For each of the 9 IPCA groups, estimate next-month MoM variation
    using seasonal pattern + trend + specific drivers.
    Aggregate using IBGE weights to get total IPCA forecast."""

    def estimate_components(self, features: dict) -> dict[str, float]:
        """
        For each group, estimate next-month MoM:
        - Food: seasonal pattern + IGP-M passthrough + PTAX change
        - Housing: energy tariff cycle + water/sewage
        - Transport: fuel (oil + PTAX) + public transport seasonal
        - Health: IPCA-15 as leading + insurance annual adjustment
        - Education: February/March spike + rest = ~0
        - Services: trailing 3m avg + unemployment gap
        - Others: trailing 3m avg

        Returns: {"food": 0.45, "housing": 0.38, ..., "total_ipca": 0.42}
        """

    def signal(self, forecast: dict, features: dict) -> AgentSignal:
        """If forecast total_ipca > Focus monthly expectation → hawkish signal."""

class InflationSurpriseModel:
    """Track inflation surprises (actual - expected) as regime indicator.
    Persistent positive surprises → inflation regime shift.
    Uses z-score of cumulative 3-month surprise."""

    def compute_surprise_score(self, features: dict) -> float:
        """Z-score of rolling 3-month surprise average. Positive = hawkish."""

    def signal(self, score: float) -> AgentSignal:
        """If |z-score| > 1.5 → signal. Direction based on sign."""

class InflationPersistenceModel:
    """Track inflation persistence through core measures and diffusion.
    High persistence (diffusion > 65%, cores accelerating) → hawkish.
    Reference: BCB Inflation Report methodology."""

    def compute_persistence_score(self, features: dict) -> float:
        """
        Composite score (0-100) based on:
        - Diffusion index level and trend (weight 25%)
        - Core measures acceleration (3m vs 12m, weight 30%)
        - Services inflation momentum (weight 25%)
        - Expectations anchoring (focus deviation from target, weight 20%)
        """

    def signal(self, score: float) -> AgentSignal:
        """Score > 65 → hawkish. Score < 35 → dovish."""

class UsInflationTrendModel:
    """US inflation trend analysis for cross-market comparison.
    Focus on PCE Core as Fed's target."""

    def compute_us_inflation_stance(self, features: dict) -> dict:
        """
        Returns:
        - pce_core_trend: 3m SAAR direction
        - target_gap: pce_core_yoy - 2.0 (Fed target)
        - supercore_momentum: services ex shelter trend
        - bei_real_vs_model: breakevens vs model fair value
        """

    def signal(self, stance: dict) -> AgentSignal:
        """PCE core 3m SAAR > 3.0% → hawkish for US rates."""
```

## 3. src/agents/inflation/agent.py

```python
class InflationAgent(BaseAgent):
    """
    Inflation Agent — monitors inflation dynamics in Brazil and US.
    
    Generates signals:
    - INFLATION_BR_PHILLIPS: Phillips Curve model output
    - INFLATION_BR_BOTTOMUP: Bottom-up IPCA forecast
    - INFLATION_BR_SURPRISE: Inflation surprise regime
    - INFLATION_BR_PERSISTENCE: Inflation persistence score
    - INFLATION_US_TREND: US PCE Core trend
    - INFLATION_BR_COMPOSITE: Weighted composite of BR signals
    
    Horizon: 1-3 months for IPCA MoM, 12 months for core trajectory.
    """

    def __init__(self):
        super().__init__("inflation_agent", "Inflation Agent v1")
        self.data_loader = PointInTimeDataLoader()
        self.feature_engine = InflationFeatureEngine(self.data_loader)
        self.phillips = PhillipsCurveModel()
        self.bottom_up = IpcaBottomUpModel()
        self.surprise = InflationSurpriseModel()
        self.persistence = InflationPersistenceModel()
        self.us_trend = UsInflationTrendModel()

    def load_data(self, as_of_date: date) -> dict:
        """Load all inflation-related data respecting point-in-time."""
        return {
            "br_ipca_mom": self.data_loader.get_macro_series("BR_IPCA_MOM", as_of_date, lookback_days=3650),
            "br_ipca_yoy": self.data_loader.get_macro_series("BR_IPCA_YOY", as_of_date),
            "br_ipca_cores": {
                core: self.data_loader.get_macro_series(core, as_of_date)
                for core in ["BR_IPCA_CORE_EX3", "BR_IPCA_CORE_MA", "BR_IPCA_CORE_DP"]
            },
            "br_ipca_diffusion": self.data_loader.get_macro_series("BR_IPCA_DIFFUSION", as_of_date),
            "br_ipca_groups": {
                g: self.data_loader.get_macro_series(f"BR_IPCA_{g}_MOM", as_of_date)
                for g in ["FOOD", "HOUSING", "TRANSPORT", "HEALTH", "EDUCATION",
                           "PERSONAL", "COMMUNICATION", "CLOTHING", "HOUSEHOLD"]
            },
            "br_focus": self.data_loader.get_focus_expectations("IPCA", as_of_date),
            "br_activity": {
                "capacity_util": self.data_loader.get_macro_series("BR_CAPACITY_UTIL", as_of_date),
                "unemployment": self.data_loader.get_macro_series("BR_UNEMPLOYMENT", as_of_date),
            },
            "usdbrl": self.data_loader.get_market_data("USDBRL", as_of_date),
            "us_cpi": self.data_loader.get_macro_series("US_CPI_ALL_SA", as_of_date),
            "us_pce_core": self.data_loader.get_macro_series("US_PCE_CORE", as_of_date),
            "us_bei": {
                "5y": self.data_loader.get_macro_series("US_BEI_5Y", as_of_date),
                "10y": self.data_loader.get_macro_series("US_BEI_10Y", as_of_date),
            },
        }

    def compute_features(self, data: dict) -> dict:
        # Use self.feature_engine.compute_all() but pass pre-loaded data
        # to avoid redundant DB queries
        pass

    def run_models(self, features: dict) -> list[AgentSignal]:
        signals = []

        # 1. Phillips Curve
        phillips_signal = self.phillips.signal(
            self.phillips.predict(features), features
        )
        signals.append(phillips_signal)

        # 2. Bottom-Up IPCA
        components = self.bottom_up.estimate_components(features)
        signals.append(self.bottom_up.signal(components, features))

        # 3. Surprise
        surprise_score = self.surprise.compute_surprise_score(features)
        signals.append(self.surprise.signal(surprise_score))

        # 4. Persistence
        persistence_score = self.persistence.compute_persistence_score(features)
        signals.append(self.persistence.signal(persistence_score))

        # 5. US Trend
        us_stance = self.us_trend.compute_us_inflation_stance(features)
        signals.append(self.us_trend.signal(us_stance))

        # 6. Composite BR
        br_signals = [s for s in signals if "BR" in s.signal_id]
        composite_value = np.mean([s.value for s in br_signals])
        composite_conf = np.mean([s.confidence for s in br_signals])
        signals.append(AgentSignal(
            signal_id="INFLATION_BR_COMPOSITE",
            agent_id=self.agent_id,
            timestamp=datetime.utcnow(),
            as_of_date=features.get("as_of_date", date.today()),
            direction=SignalDirection.SHORT if composite_value > 0 else SignalDirection.LONG,
            strength=_classify_strength(composite_conf),
            confidence=composite_conf,
            value=composite_value,
            horizon_days=63,
            metadata={"sub_signals": [s.signal_id for s in br_signals]}
        ))

        return signals

    def generate_narrative(self, signals: list[AgentSignal], features: dict) -> str:
        """Generate a 3-5 paragraph analysis in English covering:
        1. Current inflation state (headline IPCA, cores, diffusion)
        2. Model forecasts and surprises
        3. Expectations anchoring (Focus vs. model)
        4. Key risks and catalysts
        5. Directional conclusion for rates"""
        # Build narrative from features and signals
        pass
```

Implement ALL classes fully — not stubs. Each model must produce real calculations using the features dict. The Phillips Curve should use sklearn LinearRegression or statsmodels OLS. The bottom-up model should use component-level seasonal adjustments (use trailing 3-year seasonal pattern).

Also register the agent in registry.py: `AgentRegistry.register(InflationAgent())`

Write tests in tests/test_agents/test_inflation.py that verify:
- Feature computation returns all expected keys
- Phillips Curve signal direction is correct for a known set of inputs
- Composite signal aggregation works correctly

═══ FIM DO PROMPT 2 ═══

# VERIFICAÇÃO:
# □ pytest tests/test_agents/test_inflation.py -v
# □ python -c "from src.agents.inflation.agent import InflationAgent; a = InflationAgent(); print(a.agent_id)"


################################################################################
##                                                                            ##
##  ETAPA 3 — MONETARY POLICY AGENT                                          ##
##  Tempo: ~35 min | Taylor Rule, Selic path forecasting, Fed analysis        ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 3 ═══

No projeto macro-fund-system, implemente o Monetary Policy Agent.

## Referencial Teórico:
- Taylor Rule (Taylor, 1993): i* = r* + π + 0.5*(π - π*) + 0.5*(y - y*)
- Kalman Filter for estimating unobservable r* (natural rate) — Laubach & Williams (2003)
- BCB reaction function: Selic responds to IPCA deviation from target + output gap + inertia
- Term Premium estimation: separating rate expectations from term premium in the yield curve
- Fed Dots analysis: comparing market pricing vs. FOMC projections

## 1. src/agents/monetary/features.py

```python
class MonetaryFeatureEngine:
    def compute_brazil_features(self, as_of_date: date) -> dict:
        """
        # BCB Policy
        "br_selic_target": float,               # Current Selic target
        "br_selic_implied_12m": float,           # DI curve-implied Selic 12m ahead
        "br_selic_implied_24m": float,           # DI curve-implied Selic 24m ahead
        "br_focus_selic_cy_median": float,       # Focus year-end Selic
        "br_focus_selic_ny_median": float,       # Focus next year-end Selic
        "br_focus_selic_change_1w": float,       # Week-over-week change

        # DI Curve Shape
        "br_di_slope_2y_3m": float,             # 2Y - 3M spread (bps)
        "br_di_slope_5y_2y": float,             # 5Y - 2Y spread (belly)
        "br_di_curvature": float,               # 2*(5Y) - 2Y - 10Y (butterfly)
        "br_di_level_chg_1w": float,            # 5Y DI change last week (bps)
        "br_di_level_chg_1m": float,            # 5Y DI change last month

        # Real Rate
        "br_real_rate_ex_ante": float,           # Selic - Focus IPCA 12m
        "br_real_rate_neutral_estimate": float,  # Estimated r* (~4.5% for Brazil)
        "br_real_rate_gap": float,               # Actual real rate - r*

        # Taylor Rule Inputs (already in inflation features, cross-reference)
        "br_inflation_target_gap": float,        # IPCA YoY - target (currently 3.0%)
        "br_output_gap": float,                  # Capacity utilization proxy

        # Policy Inertia
        "br_selic_last_move_bps": float,         # Last COPOM move in bps
        "br_selic_cumulative_cycle": float,      # Cumulative change this cycle
        "br_months_since_last_move": float,
        """

    def compute_us_features(self, as_of_date: date) -> dict:
        """
        # Fed Policy
        "us_fed_funds_effective": float,
        "us_sofr": float,
        "us_fed_funds_implied_12m": float,      # From UST curve
        "us_fed_total_assets": float,            # QE/QT indicator
        "us_on_rrp": float,                      # Liquidity indicator

        # UST Curve Shape
        "us_ust_2s10s": float,                   # 10Y - 2Y spread
        "us_ust_3m10y": float,                   # 10Y - 3M spread (recession indicator)
        "us_ust_5y_level": float,
        "us_ust_10y_level": float,
        "us_ust_10y_chg_1m": float,
        "us_tips_5y_real": float,
        "us_tips_10y_real": float,

        # Taylor Rule Inputs
        "us_pce_core_target_gap": float,         # PCE core - 2.0%
        "us_output_gap_proxy": float,            # Capacity utilization

        # Financial Conditions
        "us_nfci": float,                        # Chicago Fed NFCI
        "us_hy_oas": float,                      # High yield spread
        "us_ig_oas": float,                      # Investment grade spread
        """
```

## 2. src/agents/monetary/models.py

```python
class TaylorRuleModel:
    """Classic and Modified Taylor Rule for BCB.

    Classic Taylor (1993):
    i* = r* + π + 0.5*(π - π*) + 0.5*(y_gap)

    BCB Modified (empirical):
    i* = r* + π_e + α*(π_e - π*) + β*(y_gap) + γ*(i_{t-1} - i*)  [inertia term]

    Where:
    - r* = neutral real rate (~4.5% for Brazil, ~0.5% for US)
    - π = current inflation (IPCA YoY for BR, PCE core for US)
    - π_e = expected inflation (Focus 12m for BR)
    - π* = inflation target (3.0% for BR, 2.0% for US)
    - y_gap = output gap
    - α = inflation response coefficient (~1.5 for BR)
    - β = output gap response coefficient (~0.5)
    - γ = policy inertia (~0.3)
    """

    def compute_taylor_rate(self, features: dict, variant: str = "modified") -> float:
        """Return implied Selic rate from Taylor Rule."""

    def compute_policy_gap(self, features: dict) -> float:
        """Current Selic - Taylor implied rate. Positive = policy too tight."""

    def signal(self, features: dict) -> AgentSignal:
        """
        Signal logic:
        - If Selic > Taylor by > 100bps → LONG duration (rates should fall)
        - If Selic < Taylor by > 100bps → SHORT duration (rates should rise)
        - Confidence = min(1.0, abs(policy_gap) / 300bps)
        - signal_id: "MONETARY_BR_TAYLOR"
        """

class KalmanFilterRStar:
    """Kalman Filter estimation of r* (natural rate of interest).
    
    State-space model (Laubach & Williams 2003 adapted for Brazil):
    Measurement equation: i_t = r*_t + π_e_t + noise
    Transition equation: r*_t = r*_{t-1} + ε_t (random walk)
    
    Uses: Selic history, inflation expectations, output gap.
    Estimates: time-varying r* for Brazil.
    """

    def __init__(self):
        self.r_star_history: pd.Series = None

    def estimate(self, selic_history: pd.Series,
                 inflation_expectations: pd.Series,
                 output_gap: pd.Series) -> pd.Series:
        """Run Kalman Filter and return r* time series.
        Use statsmodels UnobservedComponents or manual implementation."""

    def get_current_r_star(self) -> float:
        """Latest r* estimate."""

class SelicPathModel:
    """Model the expected path of Selic over next 8 COPOM meetings.
    
    Compare:
    1. DI curve-implied path (extract from DI swap tenors)
    2. Focus survey path (Focus Selic per meeting)
    3. Taylor Rule implied terminal rate
    
    Generate signal when market pricing diverges from model."""

    def extract_di_implied_path(self, di_curve: dict, as_of_date: date) -> list[dict]:
        """
        Extract meeting-by-meeting implied Selic from DI curve.
        COPOM meetings are approximately every 45 days.
        Returns: [{"meeting_date": date, "implied_selic": float}, ...]
        """

    def compute_terminal_rate(self, features: dict) -> float:
        """Terminal Selic = r* + inflation target + risk premium."""

    def signal(self, features: dict) -> AgentSignal:
        """
        If DI-implied terminal < model terminal by >50bps → SHORT (market too dovish)
        If DI-implied terminal > model terminal by >50bps → LONG (market too hawkish)
        signal_id: "MONETARY_BR_SELIC_PATH"
        """

class UsFedAnalysis:
    """Analyze Fed policy trajectory and implications for global rates."""

    def compute_us_taylor_rate(self, features: dict) -> float:
        """US Taylor Rule: r* + PCE + 0.5*(PCE-2.0) + 0.5*output_gap"""

    def compute_us_policy_gap(self, features: dict) -> float:
        """Fed Funds - US Taylor rate."""

    def signal(self, features: dict) -> AgentSignal:
        """signal_id: "MONETARY_US_FED_STANCE" """

class TermPremiumModel:
    """Estimate term premium in the DI curve.
    
    Term Premium = Observed long rate - Expected path of short rate
    A high term premium creates opportunities for carry trades.
    Reference: ACM model (Adrian, Crump & Moench, 2013)
    
    Simplified implementation:
    TP(n) = DI(n) - (1/n) * sum(expected_selic_i for i in 1..n)
    Where expected_selic comes from Focus survey interpolated.
    """

    def estimate_term_premium(self, di_curve: dict, focus_selic_path: list,
                               as_of_date: date) -> dict[str, float]:
        """Returns: {"tp_1y": float, "tp_2y": float, "tp_5y": float, "tp_10y": float}"""

    def signal(self, term_premium: dict) -> AgentSignal:
        """
        High TP (>200bps at 5Y) → potential carry trade opportunity → LONG duration
        Low/Negative TP → curve not compensating risk → neutral/SHORT
        signal_id: "MONETARY_BR_TERM_PREMIUM"
        """
```

## 3. src/agents/monetary/agent.py

```python
class MonetaryPolicyAgent(BaseAgent):
    """
    Monetary Policy Agent — analyzes central bank policy (BCB + Fed).
    
    Signals generated:
    - MONETARY_BR_TAYLOR: Taylor Rule gap
    - MONETARY_BR_SELIC_PATH: Market vs. model Selic path
    - MONETARY_BR_TERM_PREMIUM: Term premium estimate
    - MONETARY_US_FED_STANCE: US Fed policy gap
    - MONETARY_BR_COMPOSITE: Weighted composite
    
    Key outputs used by strategies:
    - Selic terminal rate estimate
    - DI curve fair value by tenor
    - Rate direction confidence
    """

    def __init__(self):
        super().__init__("monetary_agent", "Monetary Policy Agent v1")
        self.data_loader = PointInTimeDataLoader()
        self.feature_engine = MonetaryFeatureEngine(self.data_loader)
        self.taylor = TaylorRuleModel()
        self.kalman = KalmanFilterRStar()
        self.selic_path = SelicPathModel()
        self.us_fed = UsFedAnalysis()
        self.term_premium = TermPremiumModel()
```

Implement load_data, compute_features, run_models, generate_narrative following the same pattern as InflationAgent.

Register: `AgentRegistry.register(MonetaryPolicyAgent())`

Write tests for Taylor Rule calculation with known inputs.

═══ FIM DO PROMPT 3 ═══

# VERIFICAÇÃO:
# □ pytest tests/test_agents/test_monetary.py -v
# □ python -c "from src.agents.monetary.agent import MonetaryPolicyAgent; a = MonetaryPolicyAgent(); print(a.agent_id)"


################################################################################
##                                                                            ##
##  ETAPA 4 — FISCAL AGENT                                                   ##
##  Tempo: ~30 min | DSA model, fiscal impulse, debt sustainability           ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 4 ═══

No projeto macro-fund-system, implemente o Fiscal Agent.

## Referencial Teórico:
- Debt Sustainability Analysis (DSA): IMF framework (IMF, 2013) — projeta trajetória de dívida/PIB sob cenários
- Fiscal Impulse: mudança estrutural do resultado primário como % do PIB (Alesina & Perotti, 1995)
- r-g framework: quando custo da dívida (r) excede crescimento (g), dívida é insustentável sem superávit primário
- Fiscal dominance risk: quando política fiscal sobrecarrega política monetária (Sargent & Wallace, 1981)

## 1. src/agents/fiscal/features.py

```python
class FiscalFeatureEngine:
    def compute_brazil_features(self, as_of_date: date) -> dict:
        """
        # Debt
        "br_gross_debt_gdp": float,             # DBGG / PIB (%)
        "br_net_debt_gdp": float,               # DLSP / PIB (%)
        "br_gross_debt_gdp_12m_chg": float,     # 12-month change in ratio
        "br_net_debt_gdp_12m_chg": float,

        # Primary Balance
        "br_primary_balance_12m_gdp": float,    # Rolling 12M primary balance / GDP
        "br_primary_balance_monthly": float,     # Latest monthly
        "br_fiscal_impulse": float,              # Change in structural primary balance

        # Revenue & Expenditure
        "br_revenue_real_yoy": float,           # Real revenue growth YoY
        "br_expenditure_real_yoy": float,       # Real expenditure growth YoY
        "br_mandatory_expenditure_pct": float,  # Mandatory as % of total (rigidity)

        # r-g Dynamics
        "br_implicit_debt_rate": float,          # Implicit interest rate on debt
        "br_nominal_gdp_growth": float,          # Nominal GDP growth
        "br_r_minus_g": float,                   # r - g (positive = unfavorable)

        # Debt Composition
        "br_debt_selic_pct": float,             # % indexed to Selic (interest rate risk)
        "br_debt_ipca_pct": float,              # % indexed to IPCA
        "br_debt_prefixed_pct": float,          # % pre-fixed
        "br_debt_fx_pct": float,                # % FX-linked
        "br_avg_debt_maturity_months": float,   # Average maturity (from BCB)

        # Financing Needs
        "br_gross_financing_need_12m_pct_gdp": float,  # GFN = amortizations + deficit
        "br_reserves_to_gfn_ratio": float,              # Coverage ratio

        # Market Signals
        "br_cds_5y": float,                     # CDS 5Y spread (if available from Yahoo proxy)
        "br_embi_spread": float,                # EMBI+ Brazil (or EMB ETF proxy)
        "br_di_10y_level": float,               # Long-end DI rate

        # US Fiscal (for comparison)
        "us_debt_gdp": float,
        "us_deficit_gdp": float,
        """
```

## 2. src/agents/fiscal/models.py

```python
class DebtSustainabilityModel:
    """IMF-style Debt Sustainability Analysis for Brazil.
    
    Projects debt/GDP trajectory under scenarios:
    d_{t+1} = d_t * (1+r_t)/(1+g_t) - pb_t + sfa_t
    
    Where:
    - d = debt/GDP ratio
    - r = implicit interest rate on debt
    - g = nominal GDP growth
    - pb = primary balance / GDP
    - sfa = stock-flow adjustment (privatizations, recapitalizations, etc.)
    
    Scenarios:
    1. Baseline: current primary balance continues, consensus growth
    2. Fiscal adjustment: primary surplus improves by 0.5pp/year
    3. Stress: growth -2pp below consensus, rates +200bps
    4. Tailwind: growth +1pp above consensus, rates -100bps
    """

    def project_debt_path(self, features: dict, scenario: str = "baseline",
                           horizon_years: int = 5) -> pd.DataFrame:
        """Returns DataFrame: [year, debt_gdp, primary_balance, r, g, financing_need]"""

    def compute_required_primary_balance(self, features: dict) -> float:
        """Primary balance required to stabilize debt/GDP at current level.
        pb* = d * (r-g) / (1+g)"""

    def compute_fiscal_space(self, features: dict) -> float:
        """Distance between current primary balance and debt-stabilizing level.
        Positive = space to expand. Negative = adjustment needed."""

    def signal(self, features: dict) -> AgentSignal:
        """
        signal_id: "FISCAL_BR_DSA"
        If debt/GDP projected to rise >5pp in 3 years (baseline) → bearish for BRL/rates
        If debt stabilizing or falling → neutral/bullish
        Confidence based on how far scenarios diverge.
        """

class FiscalImpulseModel:
    """Compute fiscal impulse (change in structural fiscal balance).
    Positive impulse = fiscal expansion = stimulative.
    Negative impulse = fiscal contraction = contractionary.
    Reference: OECD methodology for cyclically-adjusted balance."""

    def compute_impulse(self, features: dict) -> float:
        """
        Cyclically-adjusted primary balance change:
        Structural PB = Actual PB + output_gap * revenue_elasticity
        Impulse = change in structural PB (negative = expansion)
        Returns: impulse as % of GDP
        """

    def signal(self, impulse: float) -> AgentSignal:
        """
        signal_id: "FISCAL_BR_IMPULSE"
        Positive impulse (expansion) > 0.5pp → bearish for BRL (more spending)
        Negative impulse (contraction) > 0.5pp → bullish for BRL (consolidation)
        """

class FiscalDominanceRisk:
    """Assess risk of fiscal dominance.
    When fiscal deficits are large enough that monetary policy loses effectiveness:
    - High debt + high rates → interest expense grows faster than revenue
    - Primary balance insufficient to cover interest → debt spiral risk
    - r > g persistently → Ponzi condition violated
    Reference: Blanchard (2019) "Public Debt and Low Interest Rates" """

    def compute_dominance_score(self, features: dict) -> float:
        """
        Score 0-100 based on:
        - r-g gap (positive = bad): weight 30%
        - Gross debt/GDP level vs. historical: weight 20%
        - Interest expense / revenue ratio: weight 20%
        - Debt composition risk (% short-term + Selic-indexed): weight 15%
        - Political fiscal risk (spending trajectory): weight 15%
        """

    def signal(self, score: float) -> AgentSignal:
        """
        signal_id: "FISCAL_BR_DOMINANCE_RISK"
        Score > 70 → HIGH risk → bearish BRL, bearish long-duration bonds
        Score 40-70 → MODERATE → neutral
        Score < 40 → LOW → supportive for assets
        """
```

## 3. src/agents/fiscal/agent.py

```python
class FiscalAgent(BaseAgent):
    """
    Fiscal Agent — analyzes sovereign fiscal dynamics for Brazil.
    
    Signals:
    - FISCAL_BR_DSA: Debt sustainability trajectory
    - FISCAL_BR_IMPULSE: Fiscal impulse direction
    - FISCAL_BR_DOMINANCE_RISK: Fiscal dominance risk score
    - FISCAL_BR_COMPOSITE: Weighted composite
    """

    def __init__(self):
        super().__init__("fiscal_agent", "Fiscal Agent v1")
        self.data_loader = PointInTimeDataLoader()
        self.feature_engine = FiscalFeatureEngine(self.data_loader)
        self.dsa = DebtSustainabilityModel()
        self.impulse = FiscalImpulseModel()
        self.dominance = FiscalDominanceRisk()
```

Implement fully. Register in AgentRegistry. Write tests.

═══ FIM DO PROMPT 4 ═══

# VERIFICAÇÃO:
# □ pytest tests/test_agents/test_fiscal.py -v
# □ python -c "from src.agents.fiscal.agent import FiscalAgent; print('OK')"


################################################################################
##                                                                            ##
##  ETAPA 5 — FX EQUILIBRIUM AGENT                                           ##
##  Tempo: ~30 min | BEER model, fair value USDBRL, flow analysis             ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 5 ═══

No projeto macro-fund-system, implemente o FX Equilibrium Agent.

## Referencial Teórico:
- BEER model (Behavioral Equilibrium Exchange Rate): Clark & MacDonald (1998) — fair value based on fundamentals (terms of trade, productivity differential, net foreign assets, real interest rate differential)
- Purchasing Power Parity (PPP): long-run anchor for exchange rates
- Interest Rate Parity (UIP/CIP): arbitrage condition linking FX to rate differentials
- Flow-based approach: net flows as short-term FX drivers (Froot & Ramadorai, 2005)
- Carry-to-risk: interest rate differential adjusted by volatility

## 1. src/agents/fx/features.py

```python
class FxFeatureEngine:
    def compute_features(self, as_of_date: date) -> dict:
        """
        # Spot & Dynamics
        "usdbrl_spot": float,
        "usdbrl_1m_return": float,
        "usdbrl_3m_return": float,
        "usdbrl_12m_return": float,
        "usdbrl_realized_vol_21d": float,
        "usdbrl_realized_vol_63d": float,
        "usdbrl_z_score_252d": float,           # Mean reversion signal

        # BEER Model Inputs
        "br_terms_of_trade_index": float,        # Commodity export basket (iron, soy, oil)
        "br_tot_3m_change": float,               # ToT 3-month change
        "br_us_real_rate_diff": float,            # BR real rate - US real rate
        "br_us_productivity_diff": float,         # IBC-Br trend vs US INDPRO trend (Balassa-Samuelson)
        "br_nfa_gdp": float,                      # Net Foreign Assets / GDP proxy (current account cumulative)
        "br_us_cpi_ratio": float,                  # Relative price level for PPP

        # Interest Rate Parity
        "br_us_rate_diff_1y": float,              # DI 1Y - UST 1Y (in %)
        "br_us_rate_diff_2y": float,
        "br_carry_to_risk": float,                # Rate differential / implied vol
        "br_cupom_cambial_1y": float,             # Cupom cambial (onshore dollar rate)
        "br_cip_basis_1y": float,                 # CIP deviation = cupom cambial - Libor/SOFR

        # Flows
        "br_fx_flow_financial_4w": float,          # 4-week sum financial FX flow
        "br_fx_flow_commercial_4w": float,
        "br_fx_flow_total_4w": float,
        "br_fx_flow_total_z_score": float,         # Z-score of 4w flow
        "br_bcb_swap_stock": float,                # BCB swap stock (USD bn)
        "br_bcb_swap_stock_chg_1m": float,         # Change in swap stock

        # CFTC Positioning
        "cftc_brl_leveraged_net": float,
        "cftc_brl_leveraged_z_score": float,
        "cftc_brl_assetmgr_net": float,

        # Global Context
        "dxy_level": float,
        "dxy_1m_return": float,
        "vix_level": float,
        "us_ust_10y_1m_chg": float,               # UST 10Y move impacts EM FX
        "emb_etf_1m_return": float,                # EM bond proxy

        # Fiscal Risk Premium
        "br_cds_proxy": float,                     # CDS or EMBI spread
        "br_gross_debt_gdp": float,
        """
```

## 2. src/agents/fx/models.py

```python
class BeerModel:
    """Behavioral Equilibrium Exchange Rate model for USDBRL.
    
    BEER(t) = α + β1*ToT(t) + β2*(r_BR - r_US)(t) + β3*NFA(t) + β4*ProductivityDiff(t) + ε
    
    Estimated via OLS on trailing 10-year window with quarterly data.
    The residual (actual USDBRL - BEER fair value) represents misalignment.
    
    Reference: Clark & MacDonald (1998), Ricci et al. (2008) for EM currencies.
    """

    def fit(self, features_history: pd.DataFrame) -> dict:
        """Fit BEER model. Returns coefficients and diagnostics."""

    def compute_fair_value(self, features: dict) -> float:
        """Return BEER-implied fair value of USDBRL."""

    def compute_misalignment(self, features: dict) -> float:
        """(Actual USDBRL - Fair Value) / Fair Value * 100.
        Positive = overvalued (BRL weak), Negative = undervalued (BRL strong)."""

    def signal(self, features: dict) -> AgentSignal:
        """
        signal_id: "FX_BR_BEER"
        If USDBRL > BEER fair value by >5% → LONG BRL (expect reversion)
        If USDBRL < BEER fair value by >5% → SHORT BRL
        Confidence scaled by magnitude of misalignment (capped at 15%)
        Horizon: 63-252 days (mean reversion is slow)
        """

class CarryToRiskModel:
    """Short-horizon FX model based on carry adjusted for risk.
    
    Carry-to-Risk = (BR_rate - US_rate) / Implied_Vol
    High carry-to-risk → BRL tends to appreciate (carry trade attractive)
    Low or negative → BRL under pressure
    
    Academic: Burnside et al. (2011) "Carry Trades and Currency Crashes"
    """

    def compute_carry_risk_ratio(self, features: dict) -> float:
        """Returns carry-to-risk ratio. Typical range: 0.5 to 3.0 for BRL."""

    def signal(self, features: dict) -> AgentSignal:
        """
        signal_id: "FX_BR_CARRY_RISK"
        Carry/risk > 2.0 → LONG BRL (attractive carry)
        Carry/risk < 1.0 → neutral/SHORT
        Horizon: 21-63 days
        """

class FlowModel:
    """Short-term FX model based on capital flows.
    
    Strong inflows (financial + commercial) → BRL appreciation pressure
    Strong outflows → BRL depreciation pressure
    BCB swap stock changes indicate policy response to flow imbalances.
    """

    def compute_flow_score(self, features: dict) -> float:
        """
        Composite flow score (-3 to +3):
        - Financial flow z-score (weight 40%)
        - Commercial flow z-score (weight 30%)
        - CFTC positioning z-score (weight 20%)
        - BCB swap intervention direction (weight 10%)
        Positive = inflow pressure (BRL bullish)
        """

    def signal(self, features: dict) -> AgentSignal:
        """signal_id: "FX_BR_FLOW" """

class CipBasisModel:
    """Covered Interest Parity (CIP) basis model.
    CIP basis = cupom cambial - SOFR (should be ~0 in theory).
    Persistent deviation signals funding stress or structural dollar shortage.
    Reference: Du, Tepper & Verdelhan (2018)"""

    def compute_basis(self, features: dict) -> float:
        """CIP basis in bps. Negative = dollar premium (funding stress)."""

    def signal(self, features: dict) -> AgentSignal:
        """signal_id: "FX_BR_CIP_BASIS" """
```

## 3. src/agents/fx/agent.py

```python
class FxEquilibriumAgent(BaseAgent):
    """
    FX Equilibrium Agent — models fair value of USDBRL and generates FX signals.
    
    Signals:
    - FX_BR_BEER: Fair value misalignment (medium-term)
    - FX_BR_CARRY_RISK: Carry-to-risk attractiveness (short-term)
    - FX_BR_FLOW: Capital flow pressure (short-term)
    - FX_BR_CIP_BASIS: CIP basis deviation (technical)
    - FX_BR_COMPOSITE: Weighted composite
    """
```

Implement fully. Register. Write tests.

═══ FIM DO PROMPT 5 ═══

# VERIFICAÇÃO:
# □ pytest tests/test_agents/test_fx.py -v


################################################################################
##                                                                            ##
##  ETAPA 6 — CROSS-ASSET AGENT                                              ##
##  Tempo: ~25 min | Regime detection, correlation analysis, risk sentiment   ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 6 ═══

No projeto macro-fund-system, implemente o Cross-Asset Agent.

## Referencial Teórico:
- Regime switching: Hamilton (1989) Markov-switching model — detect risk-on/risk-off regimes
- Risk appetite indicators: VIX, credit spreads, FX carry performance as regime indicators
- Cross-asset correlation dynamics: rolling correlations shift during stress (Longin & Solnik, 2001)
- Financial conditions indices: Goldman Sachs FCI, Chicago Fed NFCI as regime proxies

## 1. src/agents/cross_asset/models.py

```python
class RegimeDetectionModel:
    """Detect market regime: RISK_ON, RISK_OFF, or TRANSITION.
    
    Uses composite of:
    1. VIX level and trend (>25 = risk-off, <15 = risk-on)
    2. Credit spreads (HY OAS level and direction)
    3. USD direction (DXY rising = risk-off for EM)
    4. EM flows (positive = risk-on)
    5. UST curve slope (inversion = recession risk)
    
    Simplified approach (no HMM needed — rule-based composite):
    Each indicator scored -1 to +1. Weighted average determines regime.
    """

    def compute_regime_score(self, features: dict) -> float:
        """
        Returns score -1 (deep risk-off) to +1 (strong risk-on).
        
        Components:
        - VIX score: (20 - VIX) / 10, clamped [-1, 1]  (weight 25%)
        - Credit score: -(HY_OAS - 400) / 200, clamped [-1, 1]  (weight 20%)
        - DXY score: -z_score(DXY_1m_return)  (weight 15%)
        - EM flow score: z_score(emb_1m_return)  (weight 15%)
        - Curve score: sign(us_ust_3m10y) * min(abs(us_ust_3m10y)/100, 1)  (weight 15%)
        - BR fiscal: -(br_gross_debt_gdp - 75)/10, clamped [-1,1]  (weight 10%)
        """

    def classify_regime(self, score: float) -> str:
        """RISK_ON (>0.3), RISK_OFF (<-0.3), TRANSITION (otherwise)."""

    def signal(self, features: dict) -> AgentSignal:
        """signal_id: "CROSSASSET_REGIME" """

class CorrelationAnalysis:
    """Track rolling correlations between key asset pairs.
    Decorrelation or correlation breakdown signals regime change.
    
    Key pairs:
    - USDBRL vs DXY (should be ~0.7, lower = idiosyncratic risk)
    - DI 5Y vs UST 10Y (global rates transmission)
    - IBOVESPA vs SP500 (equity co-movement)
    - USDBRL vs VIX (risk premium)
    - Oil vs BRL (terms of trade)
    """

    def compute_correlation_dashboard(self, features: dict) -> dict:
        """Returns: {pair_name: {"current_63d": float, "avg_252d": float, "z_score": float}}"""

    def detect_correlation_breaks(self, dashboard: dict) -> list[str]:
        """Flag pairs where |z_score| > 2.0 (unusual correlation regime)."""

class RiskSentimentIndex:
    """Composite risk sentiment index for Brazil investing.
    
    Combines:
    - VIX level (weight 20%)
    - HY OAS level (weight 15%)
    - DXY momentum (weight 15%)
    - CFTC BRL positioning z-score (weight 15%)
    - BCB FX flow z-score (weight 15%)
    - BR CDS/EMBI proxy (weight 20%)
    
    Output: index 0-100 (0=extreme fear, 100=extreme greed)
    """

    def compute_index(self, features: dict) -> float:
        """Returns sentiment index 0-100."""

    def signal(self, features: dict) -> AgentSignal:
        """signal_id: "CROSSASSET_SENTIMENT" """
```

## 2. src/agents/cross_asset/agent.py

```python
class CrossAssetAgent(BaseAgent):
    """
    Cross-Asset Agent — provides market regime and risk context for all strategies.
    
    Signals:
    - CROSSASSET_REGIME: Risk-on/risk-off regime
    - CROSSASSET_SENTIMENT: Risk sentiment index (0-100)
    - CROSSASSET_CORRELATION: Correlation regime assessment
    
    This agent runs LAST and its signals are used to adjust
    position sizing and risk limits across all strategies.
    """
```

Implement fully. Register as last in AgentRegistry order. Write tests.

═══ FIM DO PROMPT 6 ═══

# VERIFICAÇÃO:
# □ pytest tests/test_agents/test_cross_asset.py -v
# □ python -c "from src.agents.registry import AgentRegistry; AgentRegistry.run_all(date.today())" (should run all 5 agents)


################################################################################
##                                                                            ##
##  ETAPA 7 — BACKTESTING ENGINE                                             ##
##  Tempo: ~35 min | Event-driven backtester with point-in-time correctness   ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 7 ═══

No projeto macro-fund-system, implemente o Backtesting Engine. Este é um componente crítico — todo o rigor point-in-time da Fase 0 serve para alimentar backtests confiáveis.

## Referencial:
- Event-driven backtesting: Zipline/Backtrader style, but simplified for macro strategies
- Point-in-time correctness: only use data available at the time (Harvey, Liu & Zhu, 2016)
- Transaction cost modeling: slippage, spread, market impact (Almgren & Chriss, 2000)
- Performance metrics: Sharpe, Sortino, Calmar, max drawdown, hit rate (Bailey & Lopez de Prado, 2012)

## Crie src/backtesting/:

```
src/backtesting/
├── __init__.py
├── engine.py           # Main backtesting engine
├── portfolio.py        # Portfolio tracking & P&L
├── metrics.py          # Performance analytics
└── report.py           # Generate backtest reports
```

## 1. src/backtesting/engine.py

```python
@dataclass
class BacktestConfig:
    strategy_id: str
    start_date: date
    end_date: date
    initial_capital: float = 10_000_000  # $10M notional
    rebalance_frequency: str = "monthly"  # daily, weekly, monthly
    transaction_cost_bps: float = 5.0     # 5bps round-trip
    slippage_bps: float = 2.0             # 2bps slippage
    max_leverage: float = 3.0             # Max 3x notional
    margin_requirement: float = 0.10      # 10% margin

class BacktestEngine:
    """Event-driven backtesting engine with strict point-in-time correctness.
    
    Flow:
    1. For each rebalance date in [start, end]:
       a. Load data available as of that date (point-in-time)
       b. Run strategy.generate_signals(as_of_date)
       c. Compute target portfolio from signals
       d. Execute rebalance (apply costs)
       e. Between rebalances, mark-to-market using daily prices
    2. After all dates, compute performance metrics
    3. Store results in backtest_results table
    """

    def __init__(self, config: BacktestConfig):
        self.config = config
        self.data_loader = PointInTimeDataLoader()
        self.portfolio = Portfolio(config.initial_capital)

    def run(self, strategy) -> BacktestResult:
        """Execute full backtest."""

        rebalance_dates = self._get_rebalance_dates()
        all_dates = self._get_all_business_days()

        for current_date in all_dates:
            # 1. Mark to market (daily)
            self.portfolio.mark_to_market(current_date, self.data_loader)

            # 2. Rebalance if scheduled
            if current_date in rebalance_dates:
                # a. Strategy generates signals using only point-in-time data
                signals = strategy.generate_signals(current_date)

                # b. Convert signals to target positions
                target_positions = strategy.signals_to_positions(signals, self.portfolio)

                # c. Execute rebalance
                trades = self.portfolio.rebalance(
                    target_positions, current_date,
                    cost_bps=self.config.transaction_cost_bps,
                    slippage_bps=self.config.slippage_bps
                )

        # 3. Compute metrics
        result = self._compute_result()
        self._persist_result(result)
        return result

    def _get_rebalance_dates(self) -> list[date]:
        """Generate rebalance dates based on frequency.
        monthly = first business day of each month
        weekly = every Monday (or next business day)
        daily = every business day"""

    def _get_all_business_days(self) -> list[date]:
        """All business days in [start, end] using BR+US combined calendar."""

    def _compute_result(self) -> BacktestResult:
        """Compute all performance metrics from portfolio equity curve."""

    def _persist_result(self, result):
        """Save to backtest_results table."""
```

## 2. src/backtesting/portfolio.py

```python
@dataclass
class Position:
    ticker: str
    quantity: float          # Can be negative (short)
    entry_price: float
    entry_date: date
    current_price: float
    current_value: float     # quantity * current_price
    unrealized_pnl: float

class Portfolio:
    """Track positions, P&L, and equity curve."""

    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: dict[str, Position] = {}
        self.equity_curve: list[dict] = []  # [{date, equity, cash, positions_value, drawdown}]
        self.trade_log: list[dict] = []     # [{date, ticker, side, quantity, price, cost}]

    @property
    def equity(self) -> float:
        return self.cash + sum(p.current_value for p in self.positions.values())

    @property
    def leverage(self) -> float:
        gross = sum(abs(p.current_value) for p in self.positions.values())
        return gross / self.equity if self.equity > 0 else 0

    def mark_to_market(self, current_date: date, data_loader):
        """Update all position prices to latest available as of date.
        Record equity curve point."""

    def rebalance(self, target_positions: dict[str, float],
                  current_date: date, cost_bps: float, slippage_bps: float) -> list[dict]:
        """
        target_positions: {ticker: target_weight}
        target_weight is fraction of equity (-1 to +1)
        
        For each ticker:
        1. Compute target_value = equity * target_weight
        2. Compute current_value = positions[ticker].current_value or 0
        3. trade_value = target_value - current_value
        4. Apply transaction cost: cost = abs(trade_value) * cost_bps / 10000
        5. Apply slippage: adj_price = price * (1 + sign(trade)*slippage_bps/10000)
        6. Update position or create new
        7. Log trade
        
        Returns: list of trade records
        """

    def close_position(self, ticker: str, current_date: date, price: float, cost_bps: float):
        """Close specific position and realize P&L."""

    def get_equity_df(self) -> pd.DataFrame:
        """Return equity curve as DataFrame."""
```

## 3. src/backtesting/metrics.py

```python
@dataclass
class BacktestResult:
    strategy_id: str
    start_date: date
    end_date: date
    # Returns
    total_return: float              # Cumulative return (%)
    annualized_return: float         # CAGR (%)
    annualized_vol: float            # Annualized std of returns
    # Risk-adjusted
    sharpe_ratio: float              # (return - rf) / vol
    sortino_ratio: float             # (return - rf) / downside_vol
    calmar_ratio: float              # return / max_drawdown
    # Drawdown
    max_drawdown: float              # Maximum peak-to-trough (%)
    max_drawdown_duration_days: int  # Longest drawdown duration
    avg_drawdown: float              # Average drawdown
    # Trade stats
    num_trades: int
    win_rate: float                  # % of winning trades
    profit_factor: float             # gross_profit / gross_loss
    avg_win: float                   # Average winning trade (%)
    avg_loss: float                  # Average losing trade (%)
    avg_holding_days: float
    # Monthly
    monthly_returns: list[dict]      # [{month, return}]
    best_month: float
    worst_month: float
    pct_positive_months: float
    # Equity curve
    equity_curve: list[dict]         # [{date, equity, drawdown}]

def compute_metrics(equity_curve: pd.DataFrame, trades: list[dict],
                    risk_free_rate: float = 0.0) -> BacktestResult:
    """Compute all metrics from equity curve and trade log."""
    # Implement each metric with proper calculation
    # Sharpe: annualized_return / annualized_vol
    # Sortino: annualized_return / downside_vol (only negative returns)
    # Max DD: max(1 - equity/cummax)
    # Win rate: count(profit > 0) / count(all trades)
    # Profit factor: sum(positive PnL) / abs(sum(negative PnL))
```

## 4. src/backtesting/report.py

```python
def generate_backtest_report(result: BacktestResult) -> str:
    """Generate formatted text report.
    
    ══════════════════════════════════════════════
    BACKTEST REPORT: {strategy_id}
    Period: {start} to {end} ({years} years)
    ══════════════════════════════════════════════
    
    RETURNS
      Total Return:      +35.2%
      Annualized Return: +6.3%
      Annualized Vol:    8.1%
      
    RISK-ADJUSTED
      Sharpe Ratio:      0.78
      Sortino Ratio:     1.12
      Calmar Ratio:      0.65
    
    DRAWDOWN
      Max Drawdown:      -9.7%
      Max DD Duration:   145 days
      Avg Drawdown:      -3.2%
    
    TRADES
      Total Trades:      156
      Win Rate:          58.3%
      Profit Factor:     1.45
      Avg Holding:       22.1 days
    
    MONTHLY RETURNS
      Best Month:        +4.2% (2023-01)
      Worst Month:       -3.1% (2022-10)
      % Positive Months: 61.7%
    ══════════════════════════════════════════════
    """

def plot_equity_curve(result: BacktestResult, save_path: str = None):
    """Generate equity curve plot using matplotlib. Save to file or show."""
```

Write comprehensive tests for:
- Portfolio mark-to-market with known prices
- Rebalance with cost calculation
- Metrics computation against known equity curve
- Sharpe ratio = 0 for flat equity curve

═══ FIM DO PROMPT 7 ═══

# VERIFICAÇÃO:
# □ pytest tests/test_backtesting/ -v
# □ python -c "from src.backtesting.engine import BacktestEngine, BacktestConfig; print('OK')"


################################################################################
##                                                                            ##
##  ETAPA 8 — STRATEGY FRAMEWORK & FIRST 2 STRATEGIES (DI CURVE)             ##
##  Tempo: ~35 min | Base strategy + Carry & Taylor Rule strategies           ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 8 ═══

No projeto macro-fund-system, crie o Strategy Framework e implemente as primeiras 2 estratégias de juros.

## 1. Novos diretórios:

```
src/strategies/
├── __init__.py
├── base.py              # BaseStrategy
├── rates_br/
│   ├── __init__.py
│   ├── carry_rolldown.py     # RATES-01: Carry & Roll-Down
│   └── taylor_misalignment.py # RATES-02: Taylor Rule Misalignment
├── inflation_br/
│   └── __init__.py
├── fx_br/
│   └── __init__.py
├── cupom_cambial/
│   └── __init__.py
└── sovereign/
    └── __init__.py
```

## 2. src/strategies/base.py — BaseStrategy

```python
@dataclass
class StrategyConfig:
    strategy_id: str
    name: str
    asset_class: str          # RATES_BR, INFLATION_BR, FX_BR, CUPOM_CAMBIAL, SOVEREIGN
    instruments: list[str]     # Tickers that this strategy trades
    rebalance_frequency: str   # daily, weekly, monthly
    max_gross_leverage: float  # Max total exposure / capital
    max_position_weight: float # Max single position weight
    stop_loss_pct: float       # Strategy-level stop loss
    take_profit_pct: float     # Strategy-level take profit

@dataclass
class StrategyPosition:
    ticker: str
    direction: str        # "LONG" or "SHORT"
    weight: float         # -1.0 to 1.0 (fraction of strategy notional)
    entry_rationale: str  # Human-readable reason
    confidence: float     # 0.0 to 1.0
    stop_loss: float | None
    take_profit: float | None

class BaseStrategy(ABC):
    """Abstract base class for all trading strategies."""

    def __init__(self, config: StrategyConfig):
        self.config = config
        self.data_loader = PointInTimeDataLoader()
        self.logger = get_logger(f"strategy.{config.strategy_id}")

    @abstractmethod
    def generate_signals(self, as_of_date: date) -> list[StrategyPosition]:
        """Generate target positions for the strategy as of a given date.
        Must use point-in-time data only."""

    def signals_to_positions(self, signals: list[StrategyPosition],
                              portfolio: Portfolio) -> dict[str, float]:
        """Convert strategy signals to target weights.
        Apply position limits and leverage constraints."""
        positions = {}
        for sig in signals:
            weight = sig.weight * sig.confidence
            weight = max(-self.config.max_position_weight,
                        min(self.config.max_position_weight, weight))
            positions[sig.ticker] = weight
        # Check gross leverage
        gross = sum(abs(w) for w in positions.values())
        if gross > self.config.max_gross_leverage:
            scale = self.config.max_gross_leverage / gross
            positions = {k: v * scale for k, v in positions.items()}
        return positions
```

## 3. src/strategies/rates_br/carry_rolldown.py — RATES-01

```python
class CarryRolldownStrategy(BaseStrategy):
    """
    RATES-01: DI Curve Carry & Roll-Down Strategy
    
    Concept: Capture positive carry and roll-down return from holding
    DI futures along the curve where carry-to-risk is maximized.
    
    Signal generation:
    1. For each tenor point (1Y, 2Y, 3Y, 5Y), compute:
       - Carry = curve rate at tenor - overnight rate (CDI)
       - Roll-down = rate change from tenor shortening (1 month)
       - Total expected return = carry + roll-down
       - Risk = realized volatility of DI rate at that tenor
       - Carry-to-risk ratio = total_return / risk
    
    2. Go LONG (receive fixed) at the tenor with highest carry-to-risk
       IF carry-to-risk > threshold (1.0) AND regime is not RISK_OFF
    
    3. Can also express curve flattener/steepener:
       - If short-end carry-to-risk >> long-end → steepener (long short-end, short long-end)
    
    Instruments: DI_SWAP_120D through DI_SWAP_360D (proxied by BCB swap rates)
    Rebalance: Monthly
    
    Risk management:
    - Stop-loss: -2% of notional per month
    - Position size: carry-to-risk / max_carry_risk * max_weight
    """

    def __init__(self):
        super().__init__(StrategyConfig(
            strategy_id="RATES_BR_01_CARRY",
            name="DI Curve Carry & Roll-Down",
            asset_class="RATES_BR",
            instruments=["DI_SWAP_90D", "DI_SWAP_180D", "DI_SWAP_270D", "DI_SWAP_360D"],
            rebalance_frequency="monthly",
            max_gross_leverage=2.0,
            max_position_weight=1.0,
            stop_loss_pct=2.0,
            take_profit_pct=5.0,
        ))
        self.carry_risk_threshold = 1.0

    def generate_signals(self, as_of_date: date) -> list[StrategyPosition]:
        """
        1. Load DI curve (from curves table, curve_id='DI_PRE')
        2. Load CDI daily rate
        3. For each tenor: compute carry, roll-down, vol, carry-to-risk
        4. Select best tenor
        5. Check regime from CrossAssetAgent signal (if available)
        6. Return StrategyPosition with appropriate weight
        """
```

## 4. src/strategies/rates_br/taylor_misalignment.py — RATES-02

```python
class TaylorMisalignmentStrategy(BaseStrategy):
    """
    RATES-02: Taylor Rule Misalignment Strategy
    
    Concept: Trade DI curve direction based on gap between
    current Selic and Taylor Rule-implied fair rate.
    
    Signal generation:
    1. Compute Taylor Rule implied rate (from MonetaryPolicyAgent)
    2. Compare with market-implied terminal Selic (from DI curve)
    
    If Taylor implied rate < Market pricing (market too hawkish):
       → LONG duration (receive fixed at belly/long-end)
       Instruments: DI_SWAP_360D (1Y point)
    
    If Taylor implied rate > Market pricing (market too dovish):
       → SHORT duration (pay fixed)
    
    Confidence = f(magnitude of gap, model R²)
    
    Rebalance: Monthly (after each COPOM meeting or significant data release)
    Risk: Stop-loss at 3% of notional
    """

    def __init__(self):
        super().__init__(StrategyConfig(
            strategy_id="RATES_BR_02_TAYLOR",
            name="Taylor Rule Misalignment",
            asset_class="RATES_BR",
            instruments=["DI_SWAP_360D"],
            rebalance_frequency="monthly",
            max_gross_leverage=1.5,
            max_position_weight=1.0,
            stop_loss_pct=3.0,
            take_profit_pct=6.0,
        ))

    def generate_signals(self, as_of_date: date) -> list[StrategyPosition]:
        """
        1. Get MonetaryPolicyAgent signal MONETARY_BR_TAYLOR from signals table
        2. Get market-implied terminal Selic from DI curve
        3. Compute gap and direction
        4. Return position with confidence proportional to gap magnitude
        """
```

Write tests that verify:
- Carry-to-risk calculation with a known curve
- Taylor strategy direction is correct for known gap
- Position limits are respected

═══ FIM DO PROMPT 8 ═══

# VERIFICAÇÃO:
# □ pytest tests/test_strategies/ -v


################################################################################
##                                                                            ##
##  ETAPA 9 — STRATEGIES 3-5 (INFLATION, FX, CUPOM CAMBIAL)                  ##
##  Tempo: ~30 min | 3 estratégias adicionais                                 ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 9 ═══

No projeto macro-fund-system, implemente 3 estratégias adicionais:

## 1. src/strategies/inflation_br/breakeven_trade.py — INF-01

```python
class BreakevenInflationStrategy(BaseStrategy):
    """
    INF-01: Breakeven Inflation Trade
    
    Concept: Trade breakeven inflation (NTN-B real rate vs NTN-F/DI nominal rate)
    based on model-predicted inflation trajectory vs. market-implied inflation.
    
    Signal:
    1. Compute market-implied breakeven inflation from curves:
       BEI = DI_PRE rate - NTN_B_REAL rate (at matching tenors)
    2. Get InflationAgent forecast: INFLATION_BR_COMPOSITE signal
    3. If agent predicts higher inflation than market BEI → LONG breakeven
       (long NTN-B + short DI pre-fixed, i.e., long inflation)
    4. If agent predicts lower inflation → SHORT breakeven
    
    Implementation:
    - LONG breakeven proxy: go long NTN_B curve point + short DI curve point
    - Since we don't trade bonds directly, proxy via:
      long_weight on NTN_B_REAL curve, short_weight on DI_PRE curve
    
    Instruments: NTN_B_REAL (via curves), DI_PRE (via curves)
    Rebalance: Monthly
    """

    def __init__(self):
        super().__init__(StrategyConfig(
            strategy_id="INF_BR_01_BREAKEVEN",
            name="Breakeven Inflation Trade",
            asset_class="INFLATION_BR",
            instruments=["NTN_B_5Y", "DI_SWAP_360D"],
            rebalance_frequency="monthly",
            max_gross_leverage=2.0,
            max_position_weight=1.0,
            stop_loss_pct=2.5,
            take_profit_pct=5.0,
        ))

    def generate_signals(self, as_of_date: date) -> list[StrategyPosition]:
        """
        1. Load DI_PRE curve and NTN_B_REAL curve for as_of_date
        2. Compute BEI at 2Y and 5Y tenors
        3. Load INFLATION_BR_COMPOSITE signal value
        4. Compare: if agent value > BEI → LONG breakeven (inflation underpriced)
        5. Confidence based on magnitude of deviation
        """
```

## 2. src/strategies/fx_br/fx_carry_fundamental.py — FX-01

```python
class FxCarryFundamentalStrategy(BaseStrategy):
    """
    FX-01: FX Carry & Fundamental Strategy
    
    Concept: Combine FX carry (interest rate differential) with
    BEER model fair value signal for USDBRL positioning.
    
    Signal:
    1. Carry component: BR-US rate differential / implied vol (CarryToRiskModel)
    2. Fundamental component: BEER misalignment (BeerModel)
    3. Flow component: Capital flow z-score (FlowModel)
    4. Composite: weighted average (40% carry, 35% fundamental, 25% flow)
    
    LONG BRL (short USDBRL) when composite > threshold
    SHORT BRL when composite < -threshold
    
    Instruments: USDBRL spot (proxied via Yahoo Finance OHLCV)
    Rebalance: Weekly (FX is faster-moving)
    """

    def __init__(self):
        super().__init__(StrategyConfig(
            strategy_id="FX_BR_01_CARRY_FUNDAMENTAL",
            name="FX Carry & Fundamental",
            asset_class="FX_BR",
            instruments=["USDBRL"],
            rebalance_frequency="weekly",
            max_gross_leverage=1.0,
            max_position_weight=1.0,
            stop_loss_pct=4.0,
            take_profit_pct=8.0,
        ))

    def generate_signals(self, as_of_date: date) -> list[StrategyPosition]:
        """
        1. Load FxEquilibriumAgent signals: FX_BR_CARRY_RISK, FX_BR_BEER, FX_BR_FLOW
        2. Composite = 0.40*carry_signal + 0.35*beer_signal + 0.25*flow_signal
        3. If composite > 0.3 → LONG BRL (SHORT USDBRL, weight = composite)
        4. If composite < -0.3 → SHORT BRL (LONG USDBRL)
        5. Adjust by CROSSASSET_REGIME signal (reduce size in RISK_OFF)
        """
```

## 3. src/strategies/cupom_cambial/cip_basis.py — CUPOM-01

```python
class CipBasisStrategy(BaseStrategy):
    """
    CUPOM-01: CIP Basis Trade
    
    Concept: Exploit deviations from Covered Interest Parity.
    When cupom cambial diverges from offshore dollar rates (SOFR/Libor),
    there's an arbitrage-like opportunity.
    
    CIP basis = Cupom Cambial - SOFR
    If basis is very negative (dollar premium): USD funding is expensive onshore
    → This tends to normalize over time
    → SHORT basis (expect convergence)
    
    In practice:
    - Negative basis widens in stress → entry opportunity
    - Basis normalizes as stress subsides → profit
    
    This is a mean-reversion strategy on the CIP basis.
    
    Instruments: DDI curve proxy (cupom cambial via BCB data)
    Rebalance: Monthly
    """

    def __init__(self):
        super().__init__(StrategyConfig(
            strategy_id="CUPOM_01_CIP_BASIS",
            name="CIP Basis Mean Reversion",
            asset_class="CUPOM_CAMBIAL",
            instruments=["DDI_1Y"],
            rebalance_frequency="monthly",
            max_gross_leverage=1.0,
            max_position_weight=1.0,
            stop_loss_pct=3.0,
            take_profit_pct=5.0,
        ))

    def generate_signals(self, as_of_date: date) -> list[StrategyPosition]:
        """
        1. Compute CIP basis from FxEquilibriumAgent: FX_BR_CIP_BASIS
        2. Compute z-score of basis over 252-day window
        3. If z-score < -1.5 → LONG (basis should normalize = converge)
        4. If z-score > 1.5 → SHORT (basis too tight)
        5. Confidence = min(1.0, abs(z_score) / 3.0)
        """
```

Implement all 3 strategies fully. Write tests.

═══ FIM DO PROMPT 9 ═══

# VERIFICAÇÃO:
# □ pytest tests/test_strategies/ -v (all strategies pass)


################################################################################
##                                                                            ##
##  ETAPA 10 — STRATEGIES 6-8 (CURVE, FISCAL SOVEREIGN, UST)                 ##
##  Tempo: ~30 min | Complete initial 8 strategies                            ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 10 ═══

No projeto macro-fund-system, implemente as últimas 3 estratégias do conjunto inicial:

## 1. src/strategies/rates_br/curve_slope.py — RATES-03

```python
class CurveSlopeStrategy(BaseStrategy):
    """
    RATES-03: DI Curve Slope Strategy (Flattener / Steepener)
    
    Concept: Trade the slope of the DI curve (2Y-5Y spread)
    based on monetary cycle position and inflation expectations.
    
    Logic:
    - Early tightening cycle (Selic rising, inflation high):
      → Curve flattens (long-end rises less than short-end)
      → FLATTENER: Long 5Y DI (receive), Short 2Y DI (pay)
    
    - Late tightening / early easing (Selic peaking, inflation falling):
      → Curve steepens (short-end falls more)
      → STEEPENER: Short 5Y DI (pay), Long 2Y DI (receive)
    
    Instruments: DI_SWAP_180D (short-end), DI_SWAP_360D (long-end)
    Position: always duration-neutral (DV01-neutral butterfly/slope)
    Rebalance: Monthly
    """

    def __init__(self):
        super().__init__(StrategyConfig(
            strategy_id="RATES_BR_03_CURVE_SLOPE",
            name="DI Curve Slope",
            asset_class="RATES_BR",
            instruments=["DI_SWAP_180D", "DI_SWAP_360D"],
            rebalance_frequency="monthly",
            max_gross_leverage=2.0,
            max_position_weight=1.0,
            stop_loss_pct=2.0,
            take_profit_pct=4.0,
        ))

    def generate_signals(self, as_of_date: date) -> list[StrategyPosition]:
        """
        1. Load MonetaryPolicyAgent MONETARY_BR_SELIC_PATH signal
        2. Load InflationAgent INFLATION_BR_COMPOSITE signal
        3. Determine cycle position:
           - If Selic rising + inflation signals hawkish → FLATTENER
           - If Selic stable/falling + inflation dovish → STEEPENER
        4. Compute slope z-score (current spread vs 252d window)
        5. Size based on z-score magnitude and agent confidence
        Return two positions: one LONG, one SHORT with appropriate weights
        """
```

## 2. src/strategies/sovereign/fiscal_risk_premium.py — SOV-01

```python
class FiscalRiskPremiumStrategy(BaseStrategy):
    """
    SOV-01: Fiscal Risk Premium Strategy
    
    Concept: Trade Brazil sovereign risk premium based on fiscal trajectory.
    When fiscal deterioration is priced in excessively → opportunities exist.
    When fiscal risks are underpriced → reduce exposure.
    
    Signal:
    1. FiscalAgent FISCAL_BR_DSA: debt trajectory
    2. FiscalAgent FISCAL_BR_DOMINANCE_RISK: fiscal dominance score
    3. CrossAssetAgent CROSSASSET_SENTIMENT: risk environment
    4. Market: DI 10Y level, CDS proxy (EMB ETF spread)
    
    If fiscal dominance risk LOW + sovereign spread wide → LONG BR risk
    (receive long-end DI, which benefits from spread compression)
    If fiscal dominance risk HIGH + spread tight → SHORT BR risk
    
    Instruments: DI_SWAP_360D (long-end proxy for risk premium)
    Also affects FX strategy sizing (BRL exposure linked to fiscal)
    Rebalance: Monthly
    """

    def __init__(self):
        super().__init__(StrategyConfig(
            strategy_id="SOV_BR_01_FISCAL_RISK",
            name="Fiscal Risk Premium",
            asset_class="SOVEREIGN",
            instruments=["DI_SWAP_360D", "USDBRL"],
            rebalance_frequency="monthly",
            max_gross_leverage=1.5,
            max_position_weight=0.75,
            stop_loss_pct=4.0,
            take_profit_pct=8.0,
        ))

    def generate_signals(self, as_of_date: date) -> list[StrategyPosition]:
        """
        1. Load FiscalAgent signals
        2. Load sovereign spread proxy (EMB ETF return as sentiment)
        3. Compute fiscal-adjusted spread z-score
        4. Generate positions:
           - DI_SWAP_360D: LONG if spread wide + fiscal OK; SHORT if tight + fiscal risk
           - USDBRL: small complementary position (fiscal improvement = BRL positive)
        """
```

## 3. src/strategies/rates_br/us_rates_spill.py — RATES-04

```python
class UsRatesSpilloverStrategy(BaseStrategy):
    """
    RATES-04: US Rates Spillover Strategy
    
    Concept: UST rate moves spill over to EM rates with a lag and amplification.
    When US rates move sharply, DI curve tends to overshoot.
    
    Signal:
    1. Monitor UST 10Y weekly change
    2. If UST 10Y moves >20bps in a week:
       - DI curve likely to overshoot in same direction
       - Wait for overshoot, then fade the move (mean reversion)
    3. Compare DI-UST spread z-score
    
    Entry: DI-UST spread reaches extreme z-score after US move
    Direction: Converge back to normal spread
    
    Instruments: DI_SWAP_360D
    Rebalance: Weekly (to capture fast spillover dynamics)
    """

    def __init__(self):
        super().__init__(StrategyConfig(
            strategy_id="RATES_BR_04_US_SPILL",
            name="US Rates Spillover",
            asset_class="RATES_BR",
            instruments=["DI_SWAP_360D"],
            rebalance_frequency="weekly",
            max_gross_leverage=1.0,
            max_position_weight=1.0,
            stop_loss_pct=2.5,
            take_profit_pct=4.0,
        ))

    def generate_signals(self, as_of_date: date) -> list[StrategyPosition]:
        """
        1. Load DI 1Y and UST 10Y history (252 days)
        2. Compute DI-UST spread time series
        3. Compute z-score of current spread
        4. Load UST 10Y 1-week change
        5. If UST moved >20bps AND DI-UST spread z-score > 1.5:
           → DI overshot → LONG (receive DI, spread will normalize)
        6. If UST moved >20bps AND spread z-score < -1.5:
           → DI undershot → SHORT (pay DI)
        7. No signal if UST move was small or spread is normal
        """
```

Implement all 3 strategies. Write tests. 

Also create src/strategies/__init__.py that imports all 8 strategies:
```python
ALL_STRATEGIES = {
    "RATES_BR_01_CARRY": CarryRolldownStrategy,
    "RATES_BR_02_TAYLOR": TaylorMisalignmentStrategy,
    "RATES_BR_03_CURVE_SLOPE": CurveSlopeStrategy,
    "RATES_BR_04_US_SPILL": UsRatesSpilloverStrategy,
    "INF_BR_01_BREAKEVEN": BreakevenInflationStrategy,
    "FX_BR_01_CARRY_FUNDAMENTAL": FxCarryFundamentalStrategy,
    "CUPOM_01_CIP_BASIS": CipBasisStrategy,
    "SOV_BR_01_FISCAL_RISK": FiscalRiskPremiumStrategy,
}
```

═══ FIM DO PROMPT 10 ═══

# VERIFICAÇÃO:
# □ python -c "from src.strategies import ALL_STRATEGIES; print(len(ALL_STRATEGIES), 'strategies loaded')"
# □ pytest tests/test_strategies/ -v


################################################################################
##                                                                            ##
##  ETAPA 11 — SIGNAL AGGREGATION & PORTFOLIO CONSTRUCTION                   ##
##  Tempo: ~25 min | Combina sinais em portfolio-level decisions              ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 11 ═══

No projeto macro-fund-system, implemente Signal Aggregation e Portfolio Construction.

## Crie src/portfolio/:

```
src/portfolio/
├── __init__.py
├── aggregator.py       # Signal aggregation across agents & strategies
├── constructor.py      # Portfolio construction & optimization
└── allocator.py        # Capital allocation across strategies
```

## 1. src/portfolio/aggregator.py

```python
class SignalAggregator:
    """Aggregate signals from all agents and strategies."""

    def aggregate_agent_signals(self, as_of_date: date) -> dict:
        """Load latest signals from all 5 agents. Return structured view:
        {"inflation": {"br_composite": {"direction","value","confidence"}, ...},
         "monetary": {...}, "fiscal": {...}, "fx": {...}, "cross_asset": {...}}"""

    def compute_directional_consensus(self, agent_signals: dict) -> dict:
        """For each asset class, compute consensus direction:
        RATES_BR: monetary + inflation + fiscal signals
        FX_BR: fx + fiscal + cross_asset
        INFLATION_BR: inflation signals
        Returns: {asset_class: {"direction", "consensus_score", "confidence"}}"""

    def detect_conflicting_signals(self, agent_signals: dict) -> list[str]:
        """Flag material agent disagreements (e.g., inflation hawkish but monetary dovish)."""
```

## 2. src/portfolio/constructor.py

```python
class PortfolioConstructor:
    """Construct target portfolio from strategy signals.
    Risk-parity-inspired: allocate inversely proportional to volatility."""

    def construct_portfolio(self, strategy_positions: dict[str, list],
                            risk_budget: dict[str, float],
                            regime: str) -> dict[str, float]:
        """
        1. For each strategy, get target weights
        2. Scale by risk_budget allocation
        3. Regime adjustment: RISK_OFF → -50%, TRANSITION → -25%
        4. Net positions across strategies trading same instrument
        5. Apply portfolio constraints (max leverage, max position)
        Returns: {ticker: net_weight}
        """

    def compute_risk_budget(self, strategy_configs: list,
                            backtest_results: dict = None) -> dict[str, float]:
        """Inverse-vol weighting if backtest available, else equal weight.
        Returns: {strategy_id: weight} summing to 1.0"""
```

## 3. src/portfolio/allocator.py

```python
class CapitalAllocator:
    def __init__(self, total_capital=10_000_000, max_leverage=3.0, max_single_pct=0.25):
        ...

    def apply_constraints(self, target_weights: dict) -> dict:
        """Enforce portfolio-level constraints."""

    def should_rebalance(self, current: dict, target: dict, threshold=0.05) -> bool:
        """True if any position drifts > threshold from target."""

    def compute_trades(self, current: dict, target: dict, equity: float) -> list[dict]:
        """Returns [{ticker, side, notional, weight_change}]."""
```

Write tests for all 3 components.

═══ FIM DO PROMPT 11 ═══

# VERIFICAÇÃO:
# □ pytest tests/test_portfolio/ -v


################################################################################
##                                                                            ##
##  ETAPA 12 — RISK MANAGEMENT ENGINE                                        ##
##  Tempo: ~25 min | VaR, position limits, drawdown, circuit breakers         ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 12 ═══

No projeto macro-fund-system, implemente o Risk Management Engine em src/risk/:

```
src/risk/
├── __init__.py
├── var.py              # Value at Risk
├── limits.py           # Position and exposure limits
├── drawdown.py         # Drawdown monitoring and circuit breakers
└── monitor.py          # Aggregate risk monitoring
```

## 1. src/risk/var.py

```python
class VaRCalculator:
    def historical_var(self, returns: pd.Series, confidence=0.95, horizon_days=1) -> float:
        """Historical VaR. Returns positive loss amount in %."""

    def parametric_var(self, returns: pd.Series, confidence=0.95, horizon_days=1) -> float:
        """Gaussian VaR = mu - z*sigma*sqrt(horizon)."""

    def expected_shortfall(self, returns: pd.Series, confidence=0.95) -> float:
        """CVaR = E[loss | loss > VaR]."""

    def component_var(self, positions: dict, correlation_matrix: pd.DataFrame,
                      volatilities: dict) -> dict[str, float]:
        """Decompose portfolio VaR by position."""

    def stress_var(self, positions: dict, scenario: dict) -> float:
        """VaR under stress scenario.
        Built-in scenarios: taper_tantrum_2013, br_crisis_2015, covid_2020, rate_shock_2022."""
```

## 2. src/risk/limits.py

```python
RISK_LIMITS = {
    "max_portfolio_leverage": 3.0,
    "max_var_95_1d_pct": 2.0,
    "max_var_99_1d_pct": 4.0,
    "max_single_position_pct": 25.0,
    "max_asset_class_pct": 50.0,
    "max_strategy_drawdown_pct": 5.0,
    "max_strategy_monthly_loss_pct": 3.0,
}

class RiskLimitChecker:
    def check_all_limits(self, portfolio, positions) -> list[dict]:
        """Check all limits. Returns list of breaches."""

    def check_pre_trade(self, proposed_trade, current_portfolio) -> dict:
        """Pre-trade check: {"allowed": bool, "breaches": [...]}"""
```

## 3. src/risk/drawdown.py

```python
class DrawdownManager:
    """Circuit breakers:
    Level 1 (-3%): Reduce positions 25%
    Level 2 (-5%): Reduce positions 50%
    Level 3 (-8%): Close all, wait for review"""

    def compute_current_drawdown(self, equity_curve: pd.Series) -> float
    def check_circuit_breakers(self, drawdown: float) -> dict:
        """{"level": 0|1|2|3, "action": str, "position_scale": float}"""
```

## 4. src/risk/monitor.py

```python
class RiskMonitor:
    def generate_risk_report(self, portfolio, as_of_date: date) -> dict:
        """Returns:
        {"portfolio": {nav, leverage, var_95, var_99, es_95, drawdown, circuit_breaker},
         "by_asset_class": {...},
         "by_strategy": {...},
         "limit_breaches": [],
         "stress_tests": {"taper_tantrum": float, "br_crisis_2015": float, "covid_2020": float, "rate_shock_2022": float}}"""
```

Implement all. Write tests with known portfolios.

═══ FIM DO PROMPT 12 ═══

# VERIFICAÇÃO:
# □ pytest tests/test_risk/ -v


################################################################################
##                                                                            ##
##  ETAPA 13 — BACKTEST RUNNER (ALL STRATEGIES)                              ##
##  Tempo: ~20 min | Script de backtesting + Makefile targets                 ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 13 ═══

No projeto macro-fund-system, implemente scripts/run_backtest.py.

## Interface:

```bash
python scripts/run_backtest.py --strategy all --start 2015-01-01 --end 2025-12-31
python scripts/run_backtest.py --strategy RATES_BR_01_CARRY --start 2020-01-01
```

## Implementation:

1. Parse args (--strategy, --start, --end, --capital, --output)
2. For each strategy: instantiate, create BacktestConfig, run BacktestEngine
3. Print formatted report per strategy
4. Save equity curve chart (matplotlib PNG) to output dir
5. Persist results to backtest_results table
6. If 'all': also run combined portfolio (risk-parity weighted)
7. Print summary table:

```
══════════════════════════════════════════════════════════════════
 Strategy                | Ann.Ret | Ann.Vol | Sharpe | MaxDD  | Calmar
 RATES_BR_01_CARRY       |  +5.2% |   6.8% |  0.76  | -8.3%  |  0.63
 ...
 COMBINED PORTFOLIO      |  +7.8% |   5.1% |  1.53  | -4.8%  |  1.63
══════════════════════════════════════════════════════════════════
```

Add to Makefile:
```makefile
backtest:
	python scripts/run_backtest.py --strategy all --start 2015-01-01
backtest-recent:
	python scripts/run_backtest.py --strategy all --start 2020-01-01
```

═══ FIM DO PROMPT 13 ═══

# VERIFICAÇÃO:
# □ make backtest-recent
# □ ls backtest_results/ (should have PNG charts and text reports)
# □ SELECT COUNT(*) FROM backtest_results;


################################################################################
##                                                                            ##
##  ETAPA 14 — API ENDPOINTS (AGENTS, SIGNALS, STRATEGIES, BACKTEST)         ##
##  Tempo: ~25 min | Novos endpoints FastAPI para Fase 1                      ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 14 ═══

No projeto macro-fund-system, adicione novos endpoints à API FastAPI para expor os componentes da Fase 1.

## Novos route files em src/api/routes/:

### src/api/routes/agents.py

```
GET /api/v1/agents
→ Lista de agentes registrados: [{"agent_id", "name", "last_run", "signals_count"}]

GET /api/v1/agents/{agent_id}/latest
→ Último AgentReport: {agent_id, as_of_date, signals, narrative, data_quality_flags}

POST /api/v1/agents/{agent_id}/run?as_of_date=2026-02-19
→ Executa o agente para a data. Retorna AgentReport.

POST /api/v1/agents/run-all?as_of_date=2026-02-19
→ Executa todos os agentes na ordem. Retorna dict de reports.
```

### src/api/routes/signals.py

```
GET /api/v1/signals/latest
→ Últimos sinais de todos os agentes com consensus e conflicts.

GET /api/v1/signals/{signal_id}/history?start=2024-01-01
→ Time series do sinal: [{time, value, confidence, direction}]
```

### src/api/routes/strategies.py

```
GET /api/v1/strategies
→ Lista das 8 estratégias: [{strategy_id, name, asset_class, status}]

GET /api/v1/strategies/{strategy_id}/current-position
→ Posições atuais da estratégia.

GET /api/v1/strategies/{strategy_id}/backtest?start=2015-01-01&end=2025-12-31
→ Backtest results completo com equity_curve e monthly_returns.
```

### src/api/routes/portfolio.py (novo)

```
GET /api/v1/portfolio/current
→ Portfolio consolidado: positions, gross/net leverage, contributing strategies.

GET /api/v1/portfolio/risk
→ Risk report: VaR, stress tests, limit breaches, circuit breaker status.
```

### Update main.py

Include todos os novos routers. Swagger docs em /docs deve refletir tudo.

Pydantic v2 response models para cada endpoint. Error handling (404, 422).

═══ FIM DO PROMPT 14 ═══

# VERIFICAÇÃO:
# □ make api && abrir http://localhost:8000/docs
# □ Testar GET /api/v1/agents, /api/v1/signals/latest, /api/v1/strategies


################################################################################
##                                                                            ##
##  ETAPA 15 — DAILY ORCHESTRATOR PIPELINE                                   ##
##  Tempo: ~20 min | Pipeline diário de execução end-to-end                   ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 15 ═══

No projeto macro-fund-system, implemente scripts/daily_run.py — pipeline diário.

## O que faz (8 steps):

1. **Ingest**: fetch_latest de todos os conectores
2. **Quality**: data quality checks
3. **Agents**: run all 5 agents (inflation → monetary → fiscal → fx → cross_asset)
4. **Aggregate**: signal aggregation, consensus, conflict detection
5. **Strategies**: run all 8 strategies, generate positions
6. **Portfolio**: construct target portfolio with risk budget and regime adjustment
7. **Risk**: VaR, limits, circuit breakers
8. **Report**: generate summary

## Interface:

```bash
python scripts/daily_run.py                    # today
python scripts/daily_run.py --date 2026-02-18  # specific date
python scripts/daily_run.py --dry-run           # don't persist
```

## Implementation:

```python
async def daily_pipeline(as_of_date: date, dry_run: bool = False):
    start = datetime.utcnow()
    
    print(f"\n{'='*60}")
    print(f" DAILY RUN — {as_of_date}")
    print(f"{'='*60}\n")

    # Step 1: Ingest
    print("[1/8] Ingesting latest data...")
    # Call fetch_latest() on each connector, log results

    # Step 2: Quality
    print("[2/8] Data quality checks...")
    # Run DataQualityChecker, report score

    # Step 3: Agents
    print("[3/8] Running agents...")
    agent_reports = AgentRegistry.run_all(as_of_date)
    for aid, rep in agent_reports.items():
        print(f"  ✓ {aid}: {len(rep.signals)} signals")

    # Step 4: Aggregate
    print("[4/8] Aggregating signals...")
    aggregator = SignalAggregator()
    consensus = aggregator.compute_directional_consensus(
        aggregator.aggregate_agent_signals(as_of_date)
    )

    # Step 5: Strategies
    print("[5/8] Running strategies...")
    strategy_positions = {}
    for sid, sclass in ALL_STRATEGIES.items():
        positions = sclass().generate_signals(as_of_date)
        strategy_positions[sid] = positions
        summary = ", ".join(f"{p.ticker}:{p.direction}" for p in positions) or "flat"
        print(f"  ✓ {sid}: {summary}")

    # Step 6: Portfolio
    print("[6/8] Constructing portfolio...")
    constructor = PortfolioConstructor()
    regime = "RISK_ON"  # from cross_asset agent
    target = constructor.construct_portfolio(
        strategy_positions,
        constructor.compute_risk_budget([s().config for s in ALL_STRATEGIES.values()]),
        regime
    )
    for t, w in sorted(target.items(), key=lambda x: -abs(x[1])):
        print(f"    {t}: {'LONG' if w>0 else 'SHORT'} {abs(w):.1%}")

    # Step 7: Risk
    print("[7/8] Risk checks...")
    risk = RiskMonitor().generate_risk_report(target, as_of_date)
    breaches = risk.get("limit_breaches", [])
    print(f"  VaR(95,1d): {risk['portfolio']['var_95_1d']:.2%}, Breaches: {len(breaches)}")

    # Step 8: Summary
    elapsed = (datetime.utcnow() - start).total_seconds()
    print(f"\n{'='*60}")
    print(f" SUMMARY: {len(agent_reports)} agents, {sum(len(r.signals) for r in agent_reports.values())} signals,")
    print(f"          {len(target)} positions, regime={regime}, {elapsed:.1f}s")
    print(f"{'='*60}\n")

    if not dry_run:
        # Persist to DB
        pass
```

Add to Makefile: `daily`, `daily-dry` targets.

═══ FIM DO PROMPT 15 ═══

# VERIFICAÇÃO:
# □ make daily-dry (pipeline completo sem persistir)


################################################################################
##                                                                            ##
##  ETAPA 16 — LLM NARRATIVE GENERATION                                      ##
##  Tempo: ~20 min | Relatórios analíticos via Claude API                     ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 16 ═══

No projeto macro-fund-system, implemente src/agents/narrative.py — geração de relatórios usando Claude API.

## NarrativeGenerator class:

```python
class NarrativeGenerator:
    """Generate analytical narratives from agent signals using Claude API."""

    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        self.model = "claude-sonnet-4-20250514"

    def generate_daily_brief(self, agent_reports: dict, consensus: dict,
                              risk_report: dict) -> str:
        """Generate 1-2 page daily macro brief covering:
        1. Market regime
        2. Inflation (BR + US)
        3. Monetary policy (BCB + Fed)
        4. Fiscal trajectory
        5. FX view
        6. Portfolio positioning
        7. Key risks
        
        Uses Claude API if key available, otherwise template fallback."""

    def generate_agent_narrative(self, agent_id: str, signals: list,
                                  features: dict) -> str:
        """Single agent analysis."""

    def _build_prompt(self, agent_reports, consensus, risk_report) -> str:
        """Build data-rich prompt with all signals and features."""

    def _fallback_narrative(self, agent_reports, consensus) -> str:
        """Template-based narrative when API key not available."""
```

Add `ANTHROPIC_API_KEY` to .env.example.

Add endpoint: `GET /api/v1/reports/daily-brief?as_of_date=2026-02-19`

Update each agent's generate_narrative() to use NarrativeGenerator when possible.

═══ FIM DO PROMPT 16 ═══

# VERIFICAÇÃO:
# □ python -c "from src.agents.narrative import NarrativeGenerator; print('OK')"


################################################################################
##                                                                            ##
##  ETAPA 17 — MONITORING DASHBOARD (HTML)                                   ##
##  Tempo: ~30 min | Dashboard web auto-contido                               ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 17 ═══

No projeto macro-fund-system, crie um dashboard web.

Crie um único arquivo HTML auto-contido (src/dashboard/index.html) servido pelo FastAPI em GET /dashboard.

O HTML deve usar React + Tailwind + Recharts via CDN e consumir a API REST.

## 4 seções com tabs:

### Tab 1: Macro Dashboard
- Tabela de indicadores-chave (Selic, IPCA, Fed Funds, CPI, USDBRL, VIX, etc.)
- Dados do endpoint /api/v1/macro/dashboard

### Tab 2: Agent Signals
- Card por agente (5 cards) com sinais, direção (cor verde/vermelha/cinza), confiança
- Consensus view por asset class
- Dados de /api/v1/signals/latest

### Tab 3: Portfolio
- Tabela de posições (ticker, direction, weight, strategies)
- Risk metrics: VaR, leverage, drawdown
- Dados de /api/v1/portfolio/current e /api/v1/portfolio/risk

### Tab 4: Backtests
- Tabela com resultados de cada estratégia (return, sharpe, max DD)
- Equity curve chart (Recharts LineChart)
- Dados de /api/v1/strategies

## FastAPI serving:

```python
# src/api/routes/dashboard_static.py
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pathlib import Path

router = APIRouter()

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    html_path = Path(__file__).parent.parent.parent / "dashboard" / "index.html"
    return HTMLResponse(content=html_path.read_text())
```

Auto-refresh a cada 60 segundos. Design limpo, profissional, dark theme.

═══ FIM DO PROMPT 17 ═══

# VERIFICAÇÃO:
# □ make api && abrir http://localhost:8000/dashboard


################################################################################
##                                                                            ##
##  ETAPA 18 — INTEGRATION TESTS                                             ##
##  Tempo: ~20 min | Tests end-to-end                                         ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 18 ═══

No projeto macro-fund-system, implemente tests/test_integration.py com testes que verificam o pipeline completo:

1. **test_agent_data_loading**: PointInTimeDataLoader retorna dados para data conhecida
2. **test_inflation_agent_run**: InflationAgent.backtest_run() gera >=4 sinais com confidence [0,1]
3. **test_all_agents_run**: AgentRegistry.run_all() retorna 5 reports
4. **test_strategy_signals**: Cada estratégia gera posições válidas (weight [-1,1], confidence [0,1])
5. **test_backtest_execution**: BacktestEngine roda para 1 ano e produz métricas
6. **test_portfolio_construction**: PortfolioConstructor respeita constraints de leverage
7. **test_risk_limits**: RiskLimitChecker não reporta breaches para portfolio small
8. **test_api_endpoints**: FastAPI TestClient — todos endpoints retornam 200

Usar date(2024, 6, 15) como data de teste (deve ter dados do backfill).

═══ FIM DO PROMPT 18 ═══

# VERIFICAÇÃO:
# □ pytest tests/test_integration.py -v --timeout=120


################################################################################
##                                                                            ##
##  ETAPA 19 — VERIFICATION SCRIPT ATUALIZADO                                ##
##  Tempo: ~15 min | Verificação completa Fase 0 + Fase 1                     ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 19 ═══

No projeto macro-fund-system, atualize scripts/verify_infrastructure.py para cobrir Fase 0 + Fase 1.

O script deve verificar e reportar:

**Phase 0:** Database, tables, hypertables, instruments, series, data volume, data freshness, quality score.

**Phase 1:** 5 agents loaded (com contagem de modelos), 8 strategies registered, backtesting engine functional, risk management loaded (VaR, limits, circuit breakers), todos API endpoints respondendo (Phase 0 + Phase 1).

Output formatado com ✅ / ⚠️ / ❌. Exit code 0 se PASS, 1 se FAIL.

═══ FIM DO PROMPT 19 ═══

# VERIFICAÇÃO:
# □ make verify (relatório completo)


################################################################################
##                                                                            ##
##  ETAPA 20 — GIT COMMIT + README FINAL                                     ##
##  Tempo: ~10 min                                                            ##
##                                                                            ##
################################################################################

═══ INÍCIO DO PROMPT 20 ═══

No projeto macro-fund-system, finalize a Fase 1:

1. **README.md**: Adicione seção Phase 1 com: tabela dos 5 agentes (nome, domínio, modelos, sinais), tabela das 8 estratégias (ID, asset class, conceito), diagrama ASCII do pipeline diário, comandos make (daily, backtest, agents, dashboard, verify).

2. **Makefile**: Adicione targets: agents, daily, daily-dry, backtest, backtest-recent, dashboard.

3. **Git commit**:
```bash
git add -A
git commit -m "Phase 1: 5 agents, 8 strategies, backtesting, risk management, dashboard"
```

═══ FIM DO PROMPT 20 ═══

# VERIFICAÇÃO FINAL:
# □ git log --oneline (2 commits)
# □ make verify (PASS)
# □ make daily-dry (pipeline sem erros)
# □ make backtest-recent (backtests executam)
# □ http://localhost:8000/dashboard (dashboard funcional)


################################################################################
##                                                                            ##
##  ═══════════════════════════════════════════════════════════════════        ##
##  FIM DA FASE 1 — QUANTITATIVE MODELS & AGENTS                             ##
##  ═══════════════════════════════════════════════════════════════════        ##
##                                                                            ##
##  CONSTRUÍDO:                                                               ##
##  ✅ Agent Framework (BaseAgent, signals, reports, data loader)             ##
##  ✅ 5 Agentes Analíticos:                                                  ##
##     - Inflation (Phillips Curve, IPCA bottom-up, persistence, surprise)    ##
##     - Monetary (Taylor Rule, Kalman r*, Selic path, term premium)          ##
##     - Fiscal (DSA, impulse, dominance risk)                                ##
##     - FX (BEER, carry-to-risk, flows, CIP basis)                          ##
##     - Cross-Asset (regime detection, sentiment, correlations)              ##
##  ✅ 8 Estratégias de Trading:                                              ##
##     - RATES-01 Carry & Roll-Down                                           ##
##     - RATES-02 Taylor Rule Misalignment                                    ##
##     - RATES-03 Curve Slope (Flattener/Steepener)                           ##
##     - RATES-04 US Rates Spillover                                          ##
##     - INF-01 Breakeven Inflation Trade                                     ##
##     - FX-01 Carry & Fundamental                                            ##
##     - CUPOM-01 CIP Basis Mean Reversion                                    ##
##     - SOV-01 Fiscal Risk Premium                                           ##
##  ✅ Backtesting Engine (point-in-time, event-driven)                       ##
##  ✅ Signal Aggregation & Portfolio Construction                             ##
##  ✅ Risk Management (VaR, limits, circuit breakers, stress tests)          ##
##  ✅ Daily Orchestration Pipeline                                            ##
##  ✅ LLM Narrative Generation (Claude API)                                   ##
##  ✅ Web Dashboard                                                           ##
##  ✅ Integration Tests                                                       ##
##                                                                            ##
##  PRÓXIMO: Fase 2 — Production & Scaling                                    ##
##  - Airflow/Dagster scheduling                                               ##
##  - Real-time streaming (Kafka)                                              ##
##  - 17 estratégias adicionais (total: 25)                                    ##
##  - NLP pipeline (COPOM/FOMC minutes)                                        ##
##  - Bloomberg integration                                                    ##
##  - Black-Litterman portfolio optimization                                   ##
##  - Execution management system                                              ##
##  - Cloud deployment (AWS/GCP)                                               ##
##                                                                            ##
################################################################################

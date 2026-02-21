# Phase 10: Cross-Asset Agent & Backtesting Engine - Research

**Researched:** 2026-02-21
**Domain:** Cross-asset regime detection agent + event-driven backtesting engine with point-in-time correctness
**Confidence:** HIGH (based on direct codebase inspection of Phases 7-9 implementation patterns)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CRSA-01 | CrossAssetAgent with RegimeDetectionModel scoring -1 (risk-off) to +1 (risk-on) from VIX, credit spreads, DXY, EM flows, UST curve slope, BR fiscal | VIX and DXY confirmed in market_data via YahooFinanceConnector; HY OAS (US_HY_OAS) confirmed in macro_series via FredConnector; DXY leveraged net in flow_data via CFTC; BR fiscal from macro_series; UST curve slope from macro_series (US_UST_2Y, US_UST_10Y) |
| CRSA-02 | CorrelationAnalysis — rolling 63d correlations for 5 key pairs with break detection at |z|>2 | All 5 instruments confirmed in market_data (USDBRL_PTAX, VIX, IBOVESPA, SP500, OIL_WTI) and macro_series (DXY via market_data); pandas rolling().corr() is the correct tool |
| CRSA-03 | RiskSentimentIndex — composite 0-100 index (fear-to-greed) from VIX, HY OAS, DXY, CFTC BRL, BCB flows, CDS/EMBI proxy | VIX, DXY in market_data; US_HY_OAS in macro_series; CFTC_6L_LEVERAGED_NET in flow_data; BCB flows in flow_data; CDS/EMBI available as proxy via BR long-end DI spread over UST |
| BACK-01 | BacktestEngine with BacktestConfig (start/end date, initial capital, rebalance frequency, transaction costs, slippage, max leverage) | Pure Python dataclass — no new library needed; BacktestConfig is a frozen dataclass; BacktestEngine.run() iterates business days using pandas.bdate_range() |
| BACK-02 | Portfolio class tracking positions, cash, equity curve, trade log with mark-to-market using PointInTimeDataLoader | Portfolio is a plain Python class; mark-to-market calls loader.get_market_data(); equity curve is list[(date, float)] appended each rebalance period |
| BACK-03 | Rebalance execution applying target weights, transaction cost (bps), slippage (bps), and position limit enforcement | Weight-to-shares conversion uses equity * weight / price; cost = abs(trade_notional) * (tc_bps + slip_bps) / 10000 |
| BACK-04 | BacktestResult with complete metrics: total/annualized return, volatility, Sharpe, Sortino, Calmar, max drawdown, win rate, profit factor, monthly returns | All metrics computable with numpy + pandas — no external library needed; verified with code test |
| BACK-05 | Point-in-time correctness enforcement — strategy.generate_signals(as_of_date) only sees data with release_time <= as_of_date | Enforced by PointInTimeDataLoader (already implemented); BacktestEngine passes as_of_date to strategy.generate_signals(); no additional infrastructure needed |
| BACK-06 | Formatted backtest report (text) and optional equity curve chart (matplotlib PNG) | Text report: Python f-strings; Chart: matplotlib NOT currently installed — must be added to pyproject.toml |
| BACK-07 | Backtest results persistence to backtest_results table with equity_curve and monthly_returns JSON | New ORM model BacktestResult with JSONB columns; sync session insert using same pattern as AgentReportRecord |
| BACK-08 | Alembic migration adding strategy_signals hypertable and backtest_results table | Migration 004_xxx.py following pattern of 003_add_agent_reports_table.py; strategy_signals needs create_hypertable(); backtest_results is a regular table |
| TESTV2-03 | Unit tests for backtesting engine (portfolio mark-to-market, rebalance with costs, metrics computation) | Unit test pattern identical to test_monetary_agent.py — synthetic data dicts, no DB connection |
</phase_requirements>

---

## Summary

Phase 10 has two distinct domains: (1) the CrossAssetAgent completing the 5-agent pipeline, and (2) a complete event-driven backtesting engine. Both build on patterns already established in Phases 7-9.

The CrossAssetAgent is the simplest agent in the system — all its data sources are already confirmed in the database (VIX, DXY, IBOVESPA, SP500, OIL_WTI in market_data via YahooFinanceConnector; US_HY_OAS, US_UST_2Y, US_UST_10Y in macro_series via FredConnector; CFTC_DX and CFTC_6L positioning in flow_data; BCB FX flows in flow_data; BR fiscal series in macro_series). The agent follows the exact same BaseAgent ABC pattern as the 4 existing agents. The RegimeDetectionModel is a composite z-score aggregator, CorrelationAnalysis uses pandas rolling().corr() with z-score break detection, and RiskSentimentIndex normalizes inputs to a 0-100 fear-greed scale.

The BacktestEngine is a new module with no direct precedent in the codebase, but the design is straightforward: a date-iterator loop over business days, calling an abstract strategy interface for signals, computing portfolio mark-to-market using existing PointInTimeDataLoader, applying transaction costs, and computing standard financial metrics using only numpy and pandas. The critical addition is matplotlib for chart generation (BACK-06) — it is NOT currently installed and must be added to pyproject.toml.

**Primary recommendation:** Build in 3 plans: Plan 10-01 (CrossAssetAgent — feature engine + 3 models + tests, Wave 1), Plan 10-02 (BacktestEngine core — BacktestConfig, Portfolio, rebalance, PIT enforcement, Alembic migration, Wave 1 independent), Plan 10-03 (BacktestResult metrics, report generation, chart, persistence, backtesting tests, Wave 2).

---

## Standard Stack

### Core (all installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| numpy | 2.4.2 | All metric calculations (Sharpe, Sortino, Calmar, max DD) | Installed; all metric formulas implementable directly |
| pandas | 3.0.1 | Rolling correlations, equity curve, monthly returns, bdate_range | Installed; resample("ME") for monthly returns, bdate_range for date iteration |
| statsmodels | 0.14.6 | Z-score normalization (already used in agents) | Installed; keep pattern consistent |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| matplotlib | NOT INSTALLED | Equity curve PNG chart (BACK-06) | Must add to pyproject.toml: `"matplotlib>=3.8"` |
| dataclasses (stdlib) | N/A | BacktestConfig, BacktestResult as frozen dataclasses | Use Python stdlib — no extra dependency |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom metric implementation | quantstats, pyfolio, empyrical | These libraries are NOT installed and add dependencies; all required metrics (Sharpe, Sortino, Calmar, max DD, win rate, profit factor) are implementable in ~50 lines of numpy/pandas |
| pandas bdate_range | bizdays (installed) | bizdays is installed and supports Brazilian holidays; bdate_range is simpler for US business days; use bdate_range unless BR holiday calendar is explicitly needed |

**Installation (only one new package):**
```bash
pip install matplotlib>=3.8
# Add to pyproject.toml dependencies: "matplotlib>=3.8"
```

---

## Architecture Patterns

### Recommended Project Structure
```
src/
├── agents/
│   ├── features/
│   │   └── cross_asset_features.py    # NEW: CrossAssetFeatureEngine
│   ├── cross_asset_agent.py           # NEW: CrossAssetAgent + 3 model classes
│   └── features/__init__.py           # UPDATE: add CrossAssetFeatureEngine conditional import
├── backtesting/
│   ├── __init__.py                    # NEW: package init
│   ├── engine.py                      # NEW: BacktestEngine, BacktestConfig
│   ├── portfolio.py                   # NEW: Portfolio class
│   └── metrics.py                     # NEW: BacktestResult, compute_metrics()
└── core/
    └── models/
        └── backtest_results.py        # NEW: BacktestResult ORM model
alembic/versions/
└── 004_add_strategy_signals_backtest.py  # NEW: migration
tests/
├── test_cross_asset_agent.py          # NEW: unit tests
└── test_backtesting.py                # NEW: unit tests (TESTV2-03)
```

### Pattern 1: CrossAssetFeatureEngine (mirrors FxFeatureEngine exactly)
**What:** Stateless `compute(data, as_of_date) -> dict` method. No DB access. Private keys for model classes.
**When to use:** CrossAssetAgent.compute_features() delegates entirely to this.
```python
class CrossAssetFeatureEngine:
    """Compute cross-asset features from raw point-in-time data."""

    def compute(self, data: dict, as_of_date: date) -> dict[str, Any]:
        features: dict[str, Any] = {}
        features["_as_of_date"] = as_of_date
        features.update(self._vix_features(data))
        features.update(self._credit_features(data))
        features.update(self._dxy_features(data))
        features.update(self._em_flow_features(data))
        features.update(self._ust_curve_features(data))
        features.update(self._br_fiscal_features(data))
        # Private keys for models
        features["_regime_components"] = self._build_regime_components(data, features)
        features["_correlation_pairs"] = self._build_correlation_pairs(data)
        features["_sentiment_components"] = self._build_sentiment_components(data, features)
        return features
```

### Pattern 2: CrossAssetAgent structure (mirrors FxEquilibriumAgent exactly)
**What:** BaseAgent subclass with AGENT_ID = "cross_asset_agent", runs last in registry.
**When to use:** CrossAssetAgent is the 5th and final agent in EXECUTION_ORDER.
```python
class CrossAssetAgent(BaseAgent):
    AGENT_ID = "cross_asset_agent"
    AGENT_NAME = "Cross-Asset Agent"

    def __init__(self, loader: PointInTimeDataLoader) -> None:
        super().__init__(self.AGENT_ID, self.AGENT_NAME)
        self.loader = loader
        self.feature_engine = CrossAssetFeatureEngine()
        self.regime_model = RegimeDetectionModel()
        self.correlation_model = CorrelationAnalysis()
        self.sentiment_model = RiskSentimentIndex()
```

### Pattern 3: RegimeDetectionModel — normalized multi-factor z-score
**What:** Scores 6 factors into [-1, +1] risk-off/on composite.
**When to use:** Called by CrossAssetAgent.run_models().
```python
class RegimeDetectionModel:
    """Score global risk regime from -1 (risk-off) to +1 (risk-on).

    Factors (all z-scored vs trailing 252-day history):
    - VIX level: high VIX → risk-off
    - US_HY_OAS credit spread: wide spread → risk-off
    - DXY level: strong USD → risk-off
    - EM flows (BCB FX flow net): outflows → risk-off
    - UST curve slope (10Y-2Y): inversion → risk-off
    - BR fiscal dominance signal (from FiscalDominanceRisk score)
    """
    SIGNAL_ID = "CROSSASSET_REGIME"

    def run(self, features: dict, as_of_date: date) -> AgentSignal:
        components = features.get("_regime_components")
        if not components:
            return _no_signal("no_components")
        # Each component z-scored; combine with equal weights
        # Negative composite = risk-off; Positive = risk-on
        raw = components  # dict of factor_name -> z_score
        composite = np.nanmean(list(raw.values()))
        # Scale to [-1, +1] via tanh or clamp
        score = float(np.clip(composite / 2.0, -1.0, 1.0))
        direction = SignalDirection.SHORT if score < -0.2 else (
            SignalDirection.LONG if score > 0.2 else SignalDirection.NEUTRAL
        )
        ...
```

### Pattern 4: CorrelationAnalysis — rolling 63d + break detection
**What:** Computes rolling 63d correlation for 5 pairs; break detected when |z|>2 vs prior 63d distribution.
**When to use:** Called by CrossAssetAgent.run_models() after RegimeDetectionModel.
```python
class CorrelationAnalysis:
    """Rolling 63d correlations for 5 key pairs with break detection.

    Pairs: USDBRL/DXY, DI/UST, IBOV/SP500, USDBRL/VIX, Oil/BRL
    Break detection: z-score of current correlation vs prior 63d mean/std.
    Signal fires when any pair shows |z| > 2.0 break.
    """
    SIGNAL_ID = "CROSSASSET_CORRELATION"
    WINDOW = 63       # business days
    BREAK_Z = 2.0     # z-score threshold for break detection

    def run(self, features: dict, as_of_date: date) -> AgentSignal:
        pairs = features.get("_correlation_pairs")  # dict of pair -> pd.Series
        ...
        # For each pair:
        roll_corr = series_x.rolling(self.WINDOW).corr(series_y)
        current = roll_corr.iloc[-1]
        hist_mean = roll_corr.iloc[-self.WINDOW-1:-1].mean()
        hist_std = roll_corr.iloc[-self.WINDOW-1:-1].std()
        z = (current - hist_mean) / hist_std if hist_std > 0 else 0.0
        if abs(z) > self.BREAK_Z:
            # correlation break detected
```

### Pattern 5: RiskSentimentIndex — 0-100 fear-to-greed
**What:** Mirrors InflationPersistenceModel (0-100 composite). Components each mapped to [0,100] subscores.
**When to use:** Called by CrossAssetAgent.run_models().
```python
class RiskSentimentIndex:
    """Composite 0-100 risk sentiment index (0=extreme fear, 100=extreme greed).

    Components:
    - VIX level: VIX=10 → 100 (greed); VIX=40 → 0 (fear)
    - US_HY_OAS: OAS=300 → 100; OAS=1000 → 0 (fear)
    - DXY: DXY=90 → 100; DXY=115 → 0 (extreme USD strength = fear)
    - CFTC_6L_LEVERAGED_NET: net long BRL → greed; net short → fear
    - BCB FX flows (net): inflows → greed; outflows → fear
    - CDS/EMBI proxy: DI_5Y - UST_5Y spread (lower = less credit risk = greed)
    """
    SIGNAL_ID = "CROSSASSET_SENTIMENT"
    WEIGHTS = {"vix": 0.25, "hy_oas": 0.20, "dxy": 0.15,
               "cftc_brl": 0.15, "em_flows": 0.15, "credit_proxy": 0.10}
```

### Pattern 6: BacktestEngine — date-iterator event loop
**What:** Iterates business days from start to end, calls strategy, rebalances, marks to market.
**When to use:** BacktestEngine.run(strategy, config) is the main entry point.
```python
@dataclass(frozen=True)
class BacktestConfig:
    start_date: date
    end_date: date
    initial_capital: float
    rebalance_frequency: str   # "daily", "weekly", "monthly"
    transaction_cost_bps: float = 5.0   # basis points round-trip
    slippage_bps: float = 2.0           # basis points per trade
    max_leverage: float = 1.0

class BacktestEngine:
    def __init__(self, config: BacktestConfig, loader: PointInTimeDataLoader):
        self.config = config
        self.loader = loader

    def run(self, strategy) -> "BacktestResult":
        portfolio = Portfolio(initial_capital=self.config.initial_capital)
        rebalance_dates = self._get_rebalance_dates()
        for as_of_date in rebalance_dates:
            # 1. Strategy sees only PIT data (enforced by PointInTimeDataLoader)
            target_weights = strategy.generate_signals(as_of_date)
            # 2. Get current prices (PIT)
            prices = self._get_prices(as_of_date)
            # 3. Mark-to-market at current prices
            portfolio.mark_to_market(prices)
            # 4. Apply rebalance with costs
            portfolio.rebalance(target_weights, prices, self.config)
            # 5. Record equity
            portfolio.equity_curve.append((as_of_date, portfolio.total_equity))
        return compute_metrics(portfolio, self.config)
```

### Pattern 7: Portfolio class — positions, cash, equity curve, trade log
**What:** Mutable state tracking the portfolio over time. No DB access — pure in-memory.
```python
class Portfolio:
    def __init__(self, initial_capital: float):
        self.cash: float = initial_capital
        self.positions: dict[str, float] = {}   # ticker -> notional value (not shares)
        self.equity_curve: list[tuple[date, float]] = []
        self.trade_log: list[dict] = []         # {date, ticker, direction, notional, cost}

    @property
    def total_equity(self) -> float:
        return self.cash + sum(self.positions.values())

    def mark_to_market(self, prices: dict[str, float]) -> None:
        """Update position values based on new prices."""
        for ticker in self.positions:
            if ticker in prices:
                # positions stored as shares; equity = shares * price
                pass  # implementation detail

    def rebalance(self, target_weights: dict[str, float],
                  prices: dict[str, float], config: BacktestConfig) -> None:
        """Apply target weights, compute trades, apply costs."""
        total_equity = self.total_equity
        for ticker, weight in target_weights.items():
            target_notional = total_equity * weight
            current_notional = self.positions.get(ticker, 0.0)
            trade_notional = target_notional - current_notional
            # Apply transaction cost + slippage
            cost = abs(trade_notional) * (config.transaction_cost_bps
                                          + config.slippage_bps) / 10_000
            self.cash -= cost
            self.positions[ticker] = target_notional
```

**Design decision:** Store positions as notional values (not shares) to avoid price-lookup complexity during rebalancing. Positions dict maps ticker -> current_notional. This simplifies mark-to-market significantly.

### Pattern 8: Metrics computation — pure numpy/pandas
**What:** BacktestResult dataclass holding all computed metrics. No external library.
```python
@dataclass
class BacktestResult:
    strategy_id: str
    start_date: date
    end_date: date
    initial_capital: float
    final_equity: float
    total_return: float          # %
    annualized_return: float     # %
    annualized_volatility: float # %
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float          # negative %
    win_rate: float              # fraction [0,1]
    profit_factor: float         # gross_profit / gross_loss
    monthly_returns: dict        # {YYYY-MM: return%}
    equity_curve: list[tuple]    # [(date, equity)]
    total_trades: int

def compute_metrics(portfolio: Portfolio, config: BacktestConfig,
                    strategy_id: str) -> BacktestResult:
    equity = pd.Series(
        [e for _, e in portfolio.equity_curve],
        index=[d for d, _ in portfolio.equity_curve]
    )
    returns = equity.pct_change().dropna()
    n_years = (config.end_date - config.start_date).days / 365.25

    total_return = (equity.iloc[-1] / equity.iloc[0] - 1) * 100
    ann_return = ((1 + total_return/100) ** (1/n_years) - 1) * 100
    ann_vol = returns.std() * np.sqrt(252) * 100

    # Sharpe (assuming risk-free rate 0 for simplicity)
    sharpe = (ann_return / ann_vol) if ann_vol > 0 else 0.0

    # Sortino (downside deviation only)
    downside = returns[returns < 0]
    sortino_denom = downside.std() * np.sqrt(252) * 100
    sortino = (ann_return / sortino_denom) if sortino_denom > 0 else 0.0

    # Max drawdown
    rolling_max = equity.expanding().max()
    drawdown = equity / rolling_max - 1
    max_dd = float(drawdown.min()) * 100  # negative %

    # Calmar
    calmar = (ann_return / abs(max_dd)) if max_dd < 0 else 0.0

    # Monthly returns
    monthly = equity.resample("ME").last().pct_change().dropna()
    monthly_dict = {str(d.date())[:7]: round(float(v)*100, 4) for d, v in monthly.items()}

    # Win rate and profit factor from trade log
    trades = [t["pnl"] for t in portfolio.trade_log if "pnl" in t]
    wins = [t for t in trades if t > 0]
    losses = [t for t in trades if t <= 0]
    win_rate = len(wins) / len(trades) if trades else 0.0
    profit_factor = sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else 0.0
```

### Pattern 9: Alembic migration — strategy_signals hypertable + backtest_results table
**What:** Migration 004 following exact pattern of migration 003 (agent_reports).
```python
# revision ID: d4e5f6g7h8i9 (or similar)
# down_revision: c3d4e5f6g7h8  (current head)

def upgrade() -> None:
    # strategy_signals hypertable (composite PK like signals table)
    op.create_table(
        "strategy_signals",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("strategy_id", sa.String(50), nullable=False),
        sa.Column("signal_date", sa.Date(), primary_key=True, nullable=False),
        sa.Column("ticker", sa.String(50), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", "signal_date"),
    )
    op.execute(
        "SELECT create_hypertable('strategy_signals', 'signal_date', "
        "chunk_time_interval => INTERVAL '1 year', if_not_exists => TRUE);"
    )

    # backtest_results — regular table (low volume)
    op.create_table(
        "backtest_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("strategy_id", sa.String(50), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("initial_capital", sa.Float(), nullable=False),
        sa.Column("total_return", sa.Float(), nullable=True),
        sa.Column("annualized_return", sa.Float(), nullable=True),
        sa.Column("sharpe_ratio", sa.Float(), nullable=True),
        sa.Column("sortino_ratio", sa.Float(), nullable=True),
        sa.Column("calmar_ratio", sa.Float(), nullable=True),
        sa.Column("max_drawdown", sa.Float(), nullable=True),
        sa.Column("win_rate", sa.Float(), nullable=True),
        sa.Column("profit_factor", sa.Float(), nullable=True),
        sa.Column("equity_curve", JSONB(), nullable=True),
        sa.Column("monthly_returns", JSONB(), nullable=True),
        sa.Column("config_json", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_backtest_results"),
    )
```

### Anti-Patterns to Avoid
- **Using `pd.Series.corr()` (scalar):** This gives a single correlation number. For rolling correlations, use `series_x.rolling(63).corr(series_y)` which returns a time series. The distinction is critical.
- **Storing shares instead of notional in Portfolio:** Storing shares requires price lookup on every access. Storing notional value simplifies rebalancing significantly and is correct for a strategy-weight-based system.
- **Float division for win_rate when trade list is empty:** Always guard `len(trades) > 0` before computing win_rate or profit_factor to avoid ZeroDivisionError.
- **Using matplotlib blocking mode in production:** Use `matplotlib.use("Agg")` backend (non-interactive) before importing pyplot when generating PNG files in a server/batch context.
- **Connecting to DB inside Portfolio.mark_to_market:** Portfolio must be data-agnostic. BacktestEngine fetches prices from PointInTimeDataLoader and passes them to Portfolio — Portfolio never touches DB directly.
- **Importing cross_asset_agent at module level before it exists:** Use conditional import pattern in `features/__init__.py` (same as Phase 9 pattern) to maintain wave independence.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Business day iteration | Custom weekday loop | `pd.bdate_range(start, end, freq="B")` | Handles month-end, year-end correctly; already in codebase |
| Monthly return resampling | Manual month bucketing | `equity_series.resample("ME").last().pct_change()` | Pandas ME frequency handles month boundaries correctly |
| Rolling correlation | Manual covariance/variance | `series_x.rolling(63).corr(series_y)` | Pandas implements Pearson correlation correctly with NaN handling |
| Z-score normalization | Manual mean/std | `pd.Series.rolling(N).mean()` and `.std()` | Already used throughout agents; consistent pattern |
| Expanding max for drawdown | Custom loop | `equity.expanding().max()` | Pandas vectorized; no loop required |
| Signal persistence | Custom SQL | `pg_insert(BacktestResultORM).values(...)` with sync_session_factory | Same ON CONFLICT DO NOTHING pattern as all other persistence |
| Text report | Template engine | Python f-strings with tabular formatting | Simple and deterministic; no extra dependency |

**Key insight:** The backtesting engine is intentionally simple — it is a strategy validation tool, not a production trading system. All metrics are implementable in pure numpy/pandas. The complexity is in the data access layer (PointInTimeDataLoader, already done) and position tracking, not the math.

---

## Critical Data Availability Findings

### CrossAssetAgent Data Sources — All Confirmed in System

**VIX (BACK-01 CRSA-01, CRSA-03):**
- Ticker: `"VIX"` in market_data (via YahooFinanceConnector, symbol `^VIX`)
- Access: `loader.get_market_data("VIX", as_of_date, lookback_days=756)`
- Returns: DataFrame with `close` column (VIX level)

**DXY US Dollar Index (CRSA-01, CRSA-03):**
- Ticker: `"DXY"` in market_data (via YahooFinanceConnector, symbol `DX-Y.NYB`)
- Access: `loader.get_market_data("DXY", as_of_date, lookback_days=756)`
- Returns: DataFrame with `close` column

**US HY OAS — Credit Spreads (CRSA-01, CRSA-03):**
- Series code: `"US_HY_OAS"` in macro_series (via FredConnector, FRED code `BAMLH0A0HYM2`)
- Access: `loader.get_macro_series("BAMLH0A0HYM2", as_of_date)` — note: FRED stores by FRED code
- Returns: DataFrame with `value` column (OAS in basis points, daily)

**IMPORTANT — FRED series code naming:** FredConnector stores series using the FRED series ID as `series_code` in series_metadata (e.g., `"BAMLH0A0HYM2"`, `"DGS2"`, `"DGS10"`), NOT the internal registry key (`"US_HY_OAS"`, `"US_UST_2Y"`). Verify actual series_code used in series_metadata before querying. The InflationAgent uses `"FRED-CPILFESL"` format (with `FRED-` prefix), so FredConnector may store with prefix. Need to check by examining existing series_metadata queries in agent code.

**UST Curve Slope (CRSA-01):**
- Series: `"FRED-DGS10"` (10Y) and `"FRED-DGS2"` (2Y) — prefix format used by InflationAgent
- Access: `loader.get_macro_series("FRED-DGS10", as_of_date)` and `"FRED-DGS2"`
- Slope = 10Y - 2Y in bps; inversion (slope < 0) is risk-off indicator

**IBOVESPA and SP500 (CRSA-02):**
- Tickers: `"IBOVESPA"` and `"SP500"` in market_data (via YahooFinanceConnector)
- Access: `loader.get_market_data("IBOVESPA", as_of_date)` and `"SP500"`

**USDBRL (CRSA-02):**
- Ticker: `"USDBRL_PTAX"` in market_data (via BcbPtaxConnector)
- Access: `loader.get_market_data("USDBRL_PTAX", as_of_date, lookback_days=756)`

**Oil/WTI (CRSA-02):**
- Ticker: `"OIL_WTI"` in market_data (via YahooFinanceConnector, symbol `CL=F`)
- Access: `loader.get_market_data("OIL_WTI", as_of_date, lookback_days=756)`

**CFTC BRL Positioning (CRSA-03):**
- Series code: `"CFTC_6L_LEVERAGED_NET"` in flow_data (via CftcCotConnector; BRL was added in Phase 9 Plan 09-01)
- Access: `loader.get_flow_data("CFTC_6L_LEVERAGED_NET", as_of_date)`
- CONFIRMED: Phase 9 Plan 09-01 added `"6L": "102741"` to CftcCotConnector.CONTRACT_CODES

**BCB FX Flows for EM flows proxy (CRSA-01, CRSA-03):**
- Series: `"BR_FX_FLOW_COMMERCIAL"` in flow_data (via BcbFxFlowConnector)
- Access: `loader.get_flow_data("BR_FX_FLOW_COMMERCIAL", as_of_date)`

**BR Fiscal (CRSA-01):**
- Can reuse: `loader.get_macro_series("BR_GROSS_DEBT_GDP", as_of_date)` or use macro_series for fiscal dominance score (if FiscalAgent ran first, its signals are already in the DB — but CrossAssetAgent should compute independently from raw data for robustness)

**CDS/EMBI proxy (CRSA-03):**
- No direct CDS or EMBI data in the system (confirmed: no CDS connector, no EMBI connector)
- Proxy: DI 5Y rate minus UST 5Y rate = Brazil sovereign credit spread proxy
- Access: `loader.get_curve("DI", as_of_date)` for DI rates + `loader.get_macro_series("FRED-DGS5", as_of_date)` for UST 5Y
- This is a LOW confidence proxy — the planner should document this limitation

---

## Common Pitfalls

### Pitfall 1: FRED Series Code Format in series_metadata
**What goes wrong:** Developer calls `loader.get_macro_series("US_HY_OAS", as_of_date)` which returns empty DataFrame because the series_metadata.series_code stores the raw FRED ID (e.g., `"BAMLH0A0HYM2"`) or a prefixed format (e.g., `"FRED-BAMLH0A0HYM2"`).
**Why it happens:** FredConnector.SERIES_REGISTRY maps internal keys to FRED codes; it's unclear which format is stored in series_metadata without confirming from existing agent code.
**How to avoid:** Check how InflationAgent or MonetaryPolicyAgent accesses FRED series in their load_data() — they use formats like `"FRED-CPILFESL"` and `"FRED-DFF"`. Use the same `"FRED-{FRED_CODE}"` prefix pattern for CrossAssetAgent. So: `"FRED-BAMLH0A0HYM2"` for HY OAS, `"FRED-DGS2"` for UST 2Y, `"FRED-DGS10"` for UST 10Y.
**Warning signs:** Empty DataFrame returned for FRED macro series in CrossAssetAgent.

### Pitfall 2: VIX Ticker Case Sensitivity in market_data
**What goes wrong:** `loader.get_market_data("VIX", as_of_date)` returns empty if instrument was stored with different case or different ticker format.
**Why it happens:** YahooFinanceConnector stores instruments with tickers from `TICKER_MAP` dict. Verify ticker is exactly `"VIX"` (not `"^VIX"`) — the Yahoo symbol `^VIX` is converted to `"VIX"` ticker in the database (per the `TICKER_MAP` in yahoo_finance.py).
**Warning signs:** Empty DataFrame for VIX or IBOVESPA market data.

### Pitfall 3: BacktestEngine Date Iteration vs Strategy Signal Availability
**What goes wrong:** BacktestEngine iterates to a date where market_data has no price (weekend, holiday) — `get_market_data()` returns empty DataFrame — mark-to-market fails with index error.
**Why it happens:** `pd.bdate_range()` generates US business days but Brazilian markets have different holidays; also data may lag by 1 day.
**How to avoid:** In BacktestEngine._get_prices(), guard for empty DataFrames: if no price available for a ticker on as_of_date, use the most recent available price (forward-fill at the portfolio level). Add a `_last_known_prices` dict to BacktestEngine that caches the most recent valid price per ticker.

### Pitfall 4: matplotlib Backend in Batch Context
**What goes wrong:** `import matplotlib.pyplot as plt` fails or opens a GUI window in a batch/server context with no display.
**Why it happens:** matplotlib defaults to interactive backend when display is available; in CI/headless environments it may error.
**How to avoid:** In `metrics.py` or wherever chart generation happens:
```python
import matplotlib
matplotlib.use("Agg")  # Must be called BEFORE importing pyplot
import matplotlib.pyplot as plt
```
**Warning signs:** `RuntimeError: Invalid DISPLAY variable` or `_tkinter.TclError`.

### Pitfall 5: Correlation Break Detection — Need Sufficient History
**What goes wrong:** CorrelationAnalysis returns NO_SIGNAL for all pairs because there are not enough data points to compute both the rolling correlation AND its z-score.
**Why it happens:** 63d rolling correlation requires 63 data points; z-score vs prior 63d requires another 63 points of rolling correlation history. Total minimum: 63 + 63 = 126 business days (~6 months) of price data needed.
**How to avoid:** Set `MIN_OBS = 130` (buffer above 126). In `_build_correlation_pairs()`, return None for pairs with fewer than MIN_OBS aligned observations. CorrelationAnalysis.run() returns NO_SIGNAL with reason `"insufficient_history"`.

### Pitfall 6: Portfolio Rebalance Produces Negative Cash
**What goes wrong:** After rebalancing + applying transaction costs, portfolio.cash goes negative, leading to incorrect equity calculations.
**Why it happens:** Transaction costs are deducted from cash; if total allocation = 100% of equity and costs are applied, cash becomes negative.
**How to avoid:** Apply position limit enforcement BEFORE costs: `max_leverage` config limits total absolute weight. For rebalancing, reduce target weights proportionally if `sum(abs(weights)) > max_leverage`. Apply costs after position limits.

### Pitfall 7: Monthly Returns for Short Backtests
**What goes wrong:** `equity_series.resample("ME").last().pct_change()` returns a single NaN value when the backtest covers only one calendar month.
**Why it happens:** `pct_change()` on a single-element Series returns NaN for the first element.
**How to avoid:** Guard: if `len(monthly) < 2`, return empty dict for monthly_returns. This also applies to profit_factor when there are no losing trades (set to 0.0 or float("inf")).

---

## Code Examples

Verified patterns from existing codebase:

### CrossAssetAgent load_data() — safe loading with _safe_load helper
```python
# Source: src/agents/fx_agent.py (FxEquilibriumAgent.load_data pattern)
def load_data(self, as_of_date: date) -> dict[str, Any]:
    data: dict[str, Any] = {}

    def _safe_load(key: str, loader_fn, *args, **kwargs) -> None:
        try:
            data[key] = loader_fn(*args, **kwargs)
        except Exception as exc:
            self.log.warning("data_load_failed", key=key, error=str(exc))
            data[key] = None

    _safe_load("vix", self.loader.get_market_data, "VIX", as_of_date, lookback_days=756)
    _safe_load("dxy", self.loader.get_market_data, "DXY", as_of_date, lookback_days=756)
    _safe_load("ibovespa", self.loader.get_market_data, "IBOVESPA", as_of_date, lookback_days=756)
    _safe_load("sp500", self.loader.get_market_data, "SP500", as_of_date, lookback_days=756)
    _safe_load("oil_wti", self.loader.get_market_data, "OIL_WTI", as_of_date, lookback_days=756)
    _safe_load("hy_oas", self.loader.get_macro_series, "FRED-BAMLH0A0HYM2", as_of_date, lookback_days=756)
    _safe_load("ust_2y", self.loader.get_macro_series, "FRED-DGS2", as_of_date, lookback_days=756)
    _safe_load("ust_10y", self.loader.get_macro_series, "FRED-DGS10", as_of_date, lookback_days=756)
    _safe_load("cftc_brl", self.loader.get_flow_data, "CFTC_6L_LEVERAGED_NET", as_of_date, lookback_days=756)
    _safe_load("bcb_flow", self.loader.get_flow_data, "BR_FX_FLOW_COMMERCIAL", as_of_date, lookback_days=365)
    try:
        data["di_curve"] = self.loader.get_curve("DI", as_of_date)
    except Exception as exc:
        self.log.warning("di_curve_load_failed", error=str(exc))
        data["di_curve"] = {}
    data["_as_of_date"] = as_of_date
    return data
```

### Rolling Correlation with Break Detection
```python
# Source: derived from pandas docs + Phase 9 pattern (no existing cross-asset code)
import pandas as pd
import numpy as np

def compute_correlation_break(series_x: pd.Series, series_y: pd.Series,
                               window: int = 63) -> tuple[float, float, bool]:
    """Compute rolling correlation and z-score break for a pair.

    Returns: (current_corr, z_score, is_break)
    """
    # Align series by index
    aligned = pd.concat([series_x, series_y], axis=1).dropna()
    if len(aligned) < window * 2:
        return float("nan"), float("nan"), False

    x = aligned.iloc[:, 0]
    y = aligned.iloc[:, 1]

    roll_corr = x.rolling(window).corr(y).dropna()
    if len(roll_corr) < window:
        return float("nan"), float("nan"), False

    current = float(roll_corr.iloc[-1])
    hist = roll_corr.iloc[-window-1:-1]
    hist_mean = float(hist.mean())
    hist_std = float(hist.std())

    z = (current - hist_mean) / hist_std if hist_std > 1e-8 else 0.0
    return current, z, abs(z) > 2.0
```

### Max Drawdown and Calmar Computation
```python
# Source: verified by running in project Python environment (numpy 2.4.2, pandas 3.0.1)
import numpy as np
import pandas as pd

def compute_max_drawdown(equity: pd.Series) -> float:
    """Compute maximum drawdown as a negative percentage."""
    rolling_max = equity.expanding().max()
    drawdown = equity / rolling_max - 1
    return float(drawdown.min()) * 100  # e.g., -15.3 means -15.3% max DD

def compute_calmar(ann_return_pct: float, max_drawdown_pct: float) -> float:
    """Calmar ratio = annualized_return / abs(max_drawdown)."""
    if max_drawdown_pct >= 0:
        return 0.0
    return ann_return_pct / abs(max_drawdown_pct)
```

### BacktestEngine Date Iteration
```python
# Source: pandas bdate_range docs; verified to work in project environment
import pandas as pd
from datetime import date

def _get_rebalance_dates(start: date, end: date,
                         frequency: str = "monthly") -> list[date]:
    """Generate rebalance dates based on frequency."""
    all_bdays = pd.bdate_range(start=start, end=end, freq="B")

    if frequency == "daily":
        return [d.date() for d in all_bdays]
    elif frequency == "weekly":
        # Last business day of each week
        weekly = all_bdays.to_frame().resample("W").last()
        return [d.date() for d in weekly.index]
    elif frequency == "monthly":
        # Last business day of each month
        monthly = all_bdays.to_frame().resample("ME").last()
        return [d.date() for d in monthly.index]
    else:
        raise ValueError(f"Unknown frequency: {frequency}")
```

### ORM Model for backtest_results
```python
# Source: Pattern from src/core/models/agent_reports.py (AgentReportRecord)
from sqlalchemy import Date, DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base

class BacktestResultRecord(Base):
    """ORM model for the backtest_results table."""
    __tablename__ = "backtest_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy_id: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    initial_capital: Mapped[float] = mapped_column(Float, nullable=False)
    total_return: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    annualized_return: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sharpe_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sortino_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    calmar_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    win_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    profit_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    equity_curve: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    monthly_returns: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    config_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

### Unit Test Pattern for Backtesting
```python
# Source: Pattern from tests/test_monetary_agent.py (no DB required)
from datetime import date
from src.backtesting.portfolio import Portfolio
from src.backtesting.engine import BacktestConfig
from src.backtesting.metrics import compute_metrics

def test_portfolio_mark_to_market():
    """Mark-to-market updates position values correctly."""
    portfolio = Portfolio(initial_capital=1_000_000.0)
    portfolio.positions = {"IBOVESPA": 500_000.0, "USDBRL": -200_000.0}
    portfolio.cash = 700_000.0  # 1M - 500K + 200K = 700K cash
    assert abs(portfolio.total_equity - 1_000_000.0) < 1.0

def test_rebalance_applies_transaction_costs():
    """Rebalance deducts transaction costs from cash."""
    portfolio = Portfolio(initial_capital=1_000_000.0)
    config = BacktestConfig(
        start_date=date(2024, 1, 1), end_date=date(2024, 12, 31),
        initial_capital=1_000_000.0, rebalance_frequency="monthly",
        transaction_cost_bps=5.0, slippage_bps=2.0
    )
    prices = {"IBOVESPA": 100_000.0}
    weights = {"IBOVESPA": 0.5}
    portfolio.rebalance(weights, prices, config)
    # 500K position at 7bps = 35 cost
    assert portfolio.cash < 500_000.0
    assert portfolio.total_equity < 1_000_000.0

def test_compute_metrics_sharpe():
    """Sharpe ratio positive for consistent positive returns."""
    portfolio = Portfolio(initial_capital=1_000_000.0)
    # Add equity curve with consistent daily growth
    from datetime import timedelta
    start = date(2024, 1, 2)
    equity = 1_000_000.0
    for i in range(252):
        d = start + timedelta(days=i)
        equity *= 1.001  # 0.1% daily return
        portfolio.equity_curve.append((d, equity))
    config = BacktestConfig(
        start_date=start, end_date=date(2024, 12, 31),
        initial_capital=1_000_000.0, rebalance_frequency="monthly"
    )
    result = compute_metrics(portfolio, config, "TEST_STRATEGY")
    assert result.sharpe_ratio > 0
    assert result.max_drawdown == 0.0  # no drawdown with monotonic returns
```

---

## Module Organization

### New File Locations

| File | Contents | Notes |
|------|----------|-------|
| `src/agents/features/cross_asset_features.py` | CrossAssetFeatureEngine | Pattern from fx_features.py |
| `src/agents/cross_asset_agent.py` | CrossAssetAgent, RegimeDetectionModel, CorrelationAnalysis, RiskSentimentIndex | Pattern from fx_agent.py |
| `src/agents/features/__init__.py` | Updated with CrossAssetFeatureEngine conditional import | Same update pattern as Phase 9 |
| `src/backtesting/__init__.py` | Package init, re-exports | New module |
| `src/backtesting/engine.py` | BacktestConfig, BacktestEngine | New module |
| `src/backtesting/portfolio.py` | Portfolio class | New module |
| `src/backtesting/metrics.py` | BacktestResult dataclass, compute_metrics() | New module |
| `src/core/models/backtest_results.py` | BacktestResultRecord ORM model | Pattern from agent_reports.py |
| `src/core/models/__init__.py` | Updated to export BacktestResultRecord | Add to existing imports |
| `alembic/env.py` | Updated to import backtest_results model | Same pattern as existing |
| `alembic/versions/004_add_strategy_signals_backtest.py` | Alembic migration | Pattern from 003_add_agent_reports_table.py |
| `tests/test_cross_asset_agent.py` | CrossAsset unit tests | Pattern from test_fx_agent.py |
| `tests/test_backtesting.py` | Backtesting unit tests (TESTV2-03) | Pattern from test_monetary_agent.py |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Backtesting with external library (backtrader, zipline) | Pure numpy/pandas implementation | Design decision in Phase 10 | No external dependency; full control over PIT enforcement; simpler debugging |
| Third-party metrics library (quantstats, pyfolio) | Hand-rolled metrics from pandas Series | Design decision in Phase 10 | No new dependency; all required metrics implementable in ~80 lines |
| matplotlib interactive backend | matplotlib Agg backend for headless PNG | Standard practice for server-side chart generation | Required for CI and batch contexts |
| pandas resample "M" frequency | pandas resample "ME" (month-end) frequency | pandas 2.2+ deprecated "M" | pandas 3.0.1 (installed) uses "ME" exclusively |

**Deprecated patterns to avoid:**
- `pd.bdate_range(..., freq="BM")` for business month-end — use `"BME"` or resample pattern
- `pd.resample("M")` — use `"ME"` in pandas 3.0.1
- `plt.show()` in batch context — always use `plt.savefig()` with Agg backend

---

## Open Questions

1. **FRED series code format in series_metadata**
   - What we know: InflationAgent uses `"FRED-CPILFESL"` and `"FRED-DFF"` formats when calling `get_macro_series()`. FredConnector stores series by the FRED code with a `"FRED-"` prefix.
   - What's unclear: Exact format for HY OAS — is it stored as `"FRED-BAMLH0A0HYM2"` or `"BAMLH0A0HYM2"` or `"US_HY_OAS"`?
   - Recommendation: In Plan 10-01 Task 1 (load_data), use the `"FRED-{FRED_CODE}"` prefix format (e.g., `"FRED-BAMLH0A0HYM2"` for HY OAS) — this is consistent with all existing agent code. If series returns empty, fall back gracefully with `_no_signal("no_hy_oas_data")`.

2. **DI/UST correlation pair — matching frequencies**
   - What we know: DI rates are from the DI curve (via get_curve()), which is daily. UST rates are from macro_series (FRED daily series DGS2, DGS10).
   - What's unclear: Whether `get_curve()` returns data at the same frequency as FRED macro series; DI curve may have gaps.
   - Recommendation: In CrossAssetFeatureEngine, build the DI-UST correlation using `get_curve_history("DI", 365, as_of_date)` (DI 1Y tenor history) and `get_macro_series("FRED-DGS2", as_of_date)` (2Y UST). Use inner join (`.dropna()` after concat) to align dates.

3. **strategy_signals hypertable necessity**
   - What we know: BACK-08 specifies creating a strategy_signals hypertable. Phase 11 will implement BaseStrategy and generate_signals().
   - What's unclear: Whether Phase 10 should actually write to strategy_signals (no strategies exist yet) or just create the table schema for Phase 11.
   - Recommendation: Plan 10-02 creates the table via Alembic migration but does NOT add an ORM write path — Phase 11 will add signal persistence when strategies are built. The migration only creates the schema.

4. **Trade log PnL tracking for win rate / profit factor**
   - What we know: BACK-04 requires win rate and profit factor. These require per-trade PnL.
   - What's unclear: How to compute per-trade PnL in a weight-based portfolio (vs share-based with explicit entry/exit prices).
   - Recommendation: Track "round-trip trades" in trade_log. When rebalancing, compute PnL of each closed/reduced position: `pnl = (current_price / entry_price - 1) * abs(prior_notional) - prior_cost`. Store entry prices in a `_entry_prices` dict keyed by ticker. Win = trade_pnl > 0; loss = trade_pnl <= 0. Profit factor = sum(wins) / abs(sum(losses)).

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection:
  - `src/agents/base.py` — BaseAgent, AgentSignal, backtest_run() pattern
  - `src/agents/data_loader.py` — PointInTimeDataLoader methods (all 5 methods)
  - `src/agents/registry.py` — EXECUTION_ORDER confirms cross_asset_agent runs last
  - `src/agents/fx_agent.py` — FxEquilibriumAgent pattern (template for CrossAssetAgent)
  - `src/agents/features/fx_features.py` — FxFeatureEngine pattern (template for CrossAssetFeatureEngine)
  - `src/core/models/agent_reports.py` — AgentReportRecord ORM (template for BacktestResultRecord)
  - `src/core/models/signals.py` — Signal hypertable schema (template for strategy_signals)
  - `src/core/models/__init__.py` — ORM model registration pattern
  - `src/core/models/base.py` — Base ORM class with naming convention
  - `src/connectors/yahoo_finance.py` — VIX, DXY, IBOVESPA, SP500, OIL_WTI confirmed tickers
  - `src/connectors/fred.py` — US_HY_OAS, US_UST_2Y, US_UST_10Y confirmed series
  - `src/connectors/cftc_cot.py` — CFTC_6L (BRL futures) confirmed in CONTRACT_CODES
  - `src/connectors/bcb_sgs.py` — BR fiscal series confirmed in macro_series
  - `alembic/versions/003_add_agent_reports_table.py` — Migration pattern for regular tables
  - `alembic/versions/001_initial_schema.py` — create_hypertable() pattern
  - `alembic/env.py` — How to register new ORM models for Alembic autogenerate
  - `tests/test_monetary_agent.py` — Unit test pattern (synthetic data, no DB)
  - `pyproject.toml` — Installed dependencies confirmed (matplotlib NOT present)
  - `.planning/phases/09-*/09-RESEARCH.md` — Phase 9 research conclusions (CFTC BRL gap now resolved)
  - `.planning/REQUIREMENTS.md` — All Phase 10 requirements confirmed
  - `.planning/ROADMAP.md` — Phase 10 success criteria and plan breakdown

### Secondary (MEDIUM confidence)
- pandas 3.0.1 "ME" frequency (verified by checking installed version is 3.0.1 which removed deprecated "M")
- matplotlib Agg backend for headless chart generation — standard practice, consistent with matplotlib docs

### Tertiary (LOW confidence)
- CDS/EMBI proxy via DI 5Y - UST 5Y spread: acceptable proxy but not true sovereign CDS data
- FRED series code format "FRED-BAMLH0A0HYM2" — HIGH likelihood based on pattern in inflation_agent.py using "FRED-CPILFESL", but not directly verified for HY OAS series

---

## Metadata

**Confidence breakdown:**
- CrossAssetAgent architecture: HIGH — identical to FxEquilibriumAgent pattern; all data sources confirmed
- CrossAssetAgent data availability: HIGH for VIX/DXY/IBOVESPA/SP500/OIL (Yahoo); HIGH for HY OAS/UST slope (FRED); HIGH for CFTC BRL (confirmed added in Phase 9); MEDIUM for CDS/EMBI proxy
- BacktestEngine design: HIGH — clear design from requirements; all tools (pandas, numpy) confirmed installed
- BacktestResult metrics: HIGH — verified metric computations run correctly in project Python environment
- matplotlib installation: CONFIRMED MISSING — must be added to pyproject.toml
- Alembic migration pattern: HIGH — directly modeled on existing 003 migration

**Research date:** 2026-02-21
**Valid until:** 2026-03-21 (30 days — stable codebase, Phase 9 just completed)

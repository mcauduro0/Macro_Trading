# Technology Stack: v2.0 Quantitative Models & Agents

**Project:** Macro Trading System
**Milestone:** v2.0 -- Quantitative Models, Agents, Backtesting, Risk Management
**Researched:** 2026-02-20
**Overall confidence:** HIGH

---

## Existing Stack (Inherited from v1.0 -- Cannot Change)

These libraries are already installed, tested, and in production use across 11 connectors, 10 ORM models, 4 transform modules, and 12 API endpoints:

| Component | Library | Version | Status |
|-----------|---------|---------|--------|
| ORM | SQLAlchemy 2.0 (async) | >=2.0.36 | Locked |
| Async DB Driver | asyncpg | >=0.30.0 | Locked |
| Sync DB Driver | psycopg2-binary | >=2.9.10 | Locked |
| Migrations | Alembic | >=1.14.0 | Locked |
| Validation | Pydantic v2 | >=2.10.0 | Locked |
| Settings | pydantic-settings | >=2.7.0 | Locked |
| Cache | redis[hiredis] | >=5.2.0 | Locked |
| HTTP Client | httpx | >=0.27.0 | Locked |
| Logging | structlog | >=24.4.0 | Locked |
| Retry | tenacity | >=8.2.0 | Locked |
| Market Data | yfinance | >=0.2.36 | Locked |
| BR Calendar | bizdays + exchange_calendars | >=1.0.0 / >=4.5.0 | Locked |
| Data Processing | pandas (implied via yfinance) | >=2.1 | Locked |
| Numeric | numpy (implied via scipy) | >=1.26 | Locked |
| Scientific | scipy | >=1.12 | Locked (used in transforms/curves.py) |

**Infrastructure (Docker Compose):** TimescaleDB (PG16), Redis 7, MongoDB 7, Kafka (Confluent 7.6), MinIO

---

## New Dependencies for v2.0

### 1. Quantitative Modeling -- statsmodels

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **statsmodels** | >=0.14.6 | OLS regression, Kalman Filter, state space models | Industry standard Python econometrics library. Provides full statistical inference (p-values, R-squared, confidence intervals, diagnostic tests) that sklearn does not. Critical for Taylor Rule estimation, Phillips Curve, and r-star Kalman filter. |

**Confidence:** HIGH

**Why statsmodels over sklearn for regression:**
- The agents need *inference*, not just prediction. Taylor Rule model diagnostics require p-values, t-stats, and R-squared to assess model fit and communicate to portfolio managers.
- statsmodels OLS provides `summary()` with full regression diagnostics in one call.
- statsmodels has `RollingOLS` built-in for rolling-window coefficient estimation -- essential for time-varying Phillips Curve and BEER model coefficients.
- WLS (Weighted Least Squares) for correcting heteroskedasticity in macroeconomic regression is available out-of-the-box.

**Key statsmodels modules we will use:**

| Module | Use Case | Agent |
|--------|----------|-------|
| `statsmodels.regression.linear_model.OLS` | Phillips Curve, Taylor Rule, BEER model | Inflation, Monetary, FX |
| `statsmodels.regression.rolling.RollingOLS` | Time-varying coefficient estimation | All agents |
| `statsmodels.tsa.statespace.structural.UnobservedComponents` | Laubach-Williams r-star estimation | Monetary Policy |
| `statsmodels.tsa.statespace.MLEModel` | Custom Kalman Filter state-space models | Monetary Policy |
| `statsmodels.stats.diagnostic` | Regression diagnostics (heteroskedasticity, autocorrelation) | All agents |

**UnobservedComponents for r-star:** The `UnobservedComponents` class supports local linear trend decomposition out of the box via `sm.tsa.UnobservedComponents(endog, 'lltrend')`. This gives us the Laubach-Williams natural rate of interest (r*) estimation with zero custom Kalman filter code. The heavy lifting runs in Cython for performance. Parameters estimated via MLE with prediction error decomposition.

**What NOT to use for econometric regression:** Do NOT use `sklearn.linear_model.LinearRegression` for agent models. It produces coefficients and R-squared but no p-values, no coefficient standard errors, no F-test, no residual diagnostics. This makes model validation and narrative generation impossible. sklearn is appropriate only for the covariance estimation use case (see below).

Sources:
- [statsmodels 0.14.6 stable docs](https://www.statsmodels.org/stable/index.html)
- [statsmodels state space methods](https://www.statsmodels.org/stable/statespace.html)
- [UnobservedComponents docs](https://www.statsmodels.org/stable/generated/statsmodels.tsa.statespace.structural.UnobservedComponents.html)
- [Chad Fulton: Implementing state space models](http://www.chadfulton.com/topics/implementing_state_space.html)

---

### 2. Regime Detection -- hmmlearn

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **hmmlearn** | >=0.3.3 | Hidden Markov Model for macro regime classification | Standard Python HMM library with sklearn-compatible API. GaussianHMM class for 4-state regime detection (Goldilocks, Reflation, Stagflation, Deflation). |

**Confidence:** MEDIUM

**Why hmmlearn:**
- `GaussianHMM` is the established tool for financial regime detection, cited in numerous academic papers and quantitative finance workflows.
- sklearn-compatible `.fit()` / `.predict()` API -- familiar pattern for the codebase.
- Pre-built wheels available for Python 3.11-3.13 on Linux/macOS/Windows.
- Only 3 parameters to configure: `n_components` (4 regimes), `covariance_type` ("full"), `n_iter` (1000).

**Limitations flagged:**
- hmmlearn is in "limited maintenance mode" -- no new releases in the past 12 months. The library is functionally complete for our use case (GaussianHMM has not changed in years), but this means no active bug fixes.
- Gaussian emission assumption may not capture heavy tails of financial returns. Mitigation: use z-scored features (growth z-score, inflation z-score) as inputs rather than raw returns, which normalizes the distribution.
- Requires a C compiler for installation (pre-built wheels available on common platforms).

**Fallback:** If hmmlearn proves problematic, implement a rule-based regime classifier using z-score thresholds on growth and inflation features. The Cross-Asset Agent already needs this as a fallback when HMM training data is insufficient (early backtest dates). The rule-based approach is simpler and more transparent, and the HMM adds marginal value for regime transition probability estimation.

Sources:
- [hmmlearn PyPI](https://pypi.org/project/hmmlearn/)
- [hmmlearn GitHub](https://github.com/hmmlearn/hmmlearn)
- [QuantStart: Market Regime Detection using HMMs](https://www.quantstart.com/articles/market-regime-detection-using-hidden-markov-models-in-qstrader/)
- [QuantInsti: Regime-Adaptive Trading 2025](https://blog.quantinsti.com/regime-adaptive-trading-python/)

---

### 3. Covariance Estimation & Portfolio Risk -- scikit-learn (covariance only)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **scikit-learn** | >=1.6 | Ledoit-Wolf shrinkage covariance, portfolio risk | Robust covariance matrix estimation for VaR and portfolio construction. `LedoitWolf` produces well-conditioned covariance matrices even when n_samples < n_features. |

**Confidence:** HIGH

**Scope is deliberately narrow:** We use sklearn exclusively for `sklearn.covariance.LedoitWolf` and `sklearn.covariance.ledoit_wolf`. We do NOT use sklearn for regression (use statsmodels), classification, or any ML pipeline. This keeps the dependency purposeful.

**Why Ledoit-Wolf over sample covariance:**
- Sample covariance matrices are poorly conditioned when the number of assets approaches the number of observations. With 15-20 instruments and 252 trading days, shrinkage is essential.
- `LedoitWolf` automatically computes the optimal shrinkage coefficient -- no manual tuning needed.
- The regularized covariance `(1 - shrinkage) * cov + shrinkage * mu * I` produces positive-definite matrices that Cholesky decomposition (needed for Monte Carlo VaR) never fails on.

**Usage pattern:**
```python
from sklearn.covariance import LedoitWolf

lw = LedoitWolf()
lw.fit(returns_matrix)  # n_samples x n_instruments
cov_matrix = lw.covariance_  # well-conditioned covariance
```

Sources:
- [sklearn LedoitWolf docs](https://scikit-learn.org/stable/modules/generated/sklearn.covariance.LedoitWolf.html)
- [sklearn covariance estimation](https://scikit-learn.org/stable/modules/covariance.html)

---

### 4. LLM Integration -- Anthropic Python SDK

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **anthropic** | >=0.81.0 | Claude API for narrative generation | Official SDK with async support (`AsyncAnthropic`), structured outputs, and httpx-based HTTP client (matches our existing HTTP stack). |

**Confidence:** HIGH

**Why the Anthropic SDK directly (not LangChain):**
- We need exactly one LLM capability: generate a 3-5 paragraph macro analysis narrative from structured agent signal data. LangChain adds massive dependency overhead for a simple `messages.create()` call.
- The SDK provides `AsyncAnthropic` client which integrates naturally with our async FastAPI architecture.
- Structured outputs (`output_config.format`) allow us to get JSON-structured responses when we need them (e.g., extracting key trades, risk warnings).
- The SDK uses httpx internally, consistent with our HTTP client stack.

**Integration pattern:**
```python
from anthropic import AsyncAnthropic

client = AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env

message = await client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=2048,
    messages=[{"role": "user", "content": prompt}],
)
narrative = message.content[0].text
```

**Fallback design (critical):** The narrative generator MUST work without an API key. When `ANTHROPIC_API_KEY` is empty or unset, fall back to a template-based narrative builder that uses the same structured signal data to produce a readable report. This ensures:
- Backtesting works without API costs (thousands of runs).
- CI/CD tests pass without secrets.
- Development works offline.

**Model selection:**
- Use `claude-sonnet-4-20250514` (or latest Sonnet) for daily narratives -- fast and cost-effective.
- Reserve `claude-opus-4-20250514` for weekly deep-dive reports where analytical depth justifies the cost.
- Make model configurable via environment variable `CLAUDE_MODEL` with Sonnet as default.

Sources:
- [Anthropic SDK GitHub](https://github.com/anthropics/anthropic-sdk-python)
- [Anthropic Client SDKs docs](https://docs.anthropic.com/en/api/client-sdks)
- [Anthropic SDK PyPI](https://pypi.org/project/anthropic/)

---

### 5. FastAPI Extension -- API serving for dashboard

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **uvicorn[standard]** | >=0.27 | ASGI server for FastAPI | Required for serving the API. Already implied by FastAPI but must be explicit in dependencies. |
| **fastapi** | >=0.109 | API framework | Already in use. v2.0 adds 10+ new endpoints for agents, signals, strategies, risk. |

**Note:** FastAPI is already a dependency but not explicitly listed in pyproject.toml. It is served via `uvicorn` which IS listed. We need to add FastAPI explicitly.

---

### 6. Dashboard -- Single-file HTML (no React build step)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **React** (CDN) | 18.x | UI components | Loaded via `unpkg.com/react@18`. No build step, no node_modules, no webpack. |
| **Tailwind CSS** (CDN) | 3.x | Styling | Loaded via `cdn.tailwindcss.com`. Dark theme, responsive. |
| **Recharts** (CDN) | 2.x | Charts (equity curves, time series) | Loaded via `unpkg.com/recharts@2`. LineChart, BarChart, AreaChart for signals and backtest results. |
| **Babel Standalone** (CDN) | 7.x | JSX transformation in browser | Enables writing React JSX in a single HTML file without a build step. |

**Confidence:** HIGH

**Why single-file HTML over a full React app (npm/vite):**
- Zero build infrastructure. No `package.json`, no `node_modules`, no CI step for frontend.
- FastAPI serves the file directly via `HTMLResponse(content=html_path.read_text())`.
- Auto-refresh with `setInterval(fetchData, 60000)` is trivial to implement.
- The dashboard is a monitoring tool, not a user-facing product. Developer ergonomics and zero-maintenance trump sophisticated UI patterns.
- Pattern proven by [single-file-react](https://github.com/oblique-works/single-file-react) template.

**Trade-offs:**
- No TypeScript type checking. Acceptable for a monitoring dashboard.
- No code splitting. Acceptable -- the entire dashboard is a single page with tabs.
- CDN dependency for loading. Acceptable -- this runs on a local network, not public internet.

**Alternative considered and rejected:** Full Vite + React + TypeScript app in `frontend/`. This adds `npm install`, `npm run build`, a `frontend/` directory tree, and CI integration for a tool that has 4 tabs and fetches JSON from the API. Overkill.

Sources:
- [single-file-react GitHub](https://github.com/oblique-works/single-file-react)
- [Tremor (Recharts-based dashboard components)](https://www.tremor.so/)

---

## Backtesting Engine -- Build Custom (No External Framework)

**Confidence:** HIGH

**Decision: Build a custom event-driven backtester, do not use Backtrader/Zipline/bt.**

**Rationale:**
1. **Macro strategies are fundamentally different from equity strategies.** Backtrader, Zipline, and bt are designed for equity tick/bar-level trading with order books, limit orders, and minute-by-minute fills. Macro strategies rebalance monthly or weekly based on economic indicators, not price bars.
2. **Point-in-time correctness is the primary concern.** The entire v1.0 data infrastructure was built around `release_time` fields for point-in-time queries. A custom backtester can enforce this at the architecture level -- the `PointInTimeDataLoader` loads only data with `release_time <= as_of_date`. External frameworks have no concept of economic data publication lag.
3. **The backtester is simple.** A macro backtester iterates over rebalance dates, calls `strategy.generate_signals(as_of_date)`, converts signals to weights, applies transaction costs, and marks to market between rebalances. This is ~300 lines of Python, not a framework-scale problem.
4. **Transition to live trading.** The `BaseStrategy.generate_signals(as_of_date)` interface works identically for backtesting (historical date) and live execution (today's date). External frameworks impose their own event loop and data model, making this dual-use pattern harder.

**What we build:**
- `BacktestEngine`: iterates rebalance dates, calls strategies, tracks portfolio
- `Portfolio`: tracks positions, cash, equity curve, trade log
- `compute_metrics()`: Sharpe, Sortino, Calmar, max drawdown, win rate, profit factor
- `BacktestResult` dataclass: all metrics + equity curve + monthly returns

**Libraries used within the backtester:** numpy (returns math), pandas (equity curve DataFrame), scipy (none additional beyond what transforms already use).

Sources:
- [QuantStart: Event-Driven Backtesting](https://www.quantstart.com/articles/Event-Driven-Backtesting-with-Python-Part-I/)
- [Macrosynergy: How to build a macro trading strategy](https://macrosynergy.com/research/how-to-build-a-macro-trading-strategy-with-open-source-python/)
- [Timothy Kimutai: Event-Driven Backtesting Engine (Oct 2025)](https://timkimutai.medium.com/how-i-built-an-event-driven-backtesting-engine-in-python-25179a80cde0)

---

## VaR Calculation -- Build with numpy/scipy (No External Package)

**Confidence:** HIGH

**Decision: Implement VaR calculation using numpy, scipy, and sklearn (Ledoit-Wolf) directly. Do not use an external VaR package.**

**Rationale:**
- The `ibaris/VaR` package and similar are thin wrappers around numpy operations. Adding a dependency for `np.percentile(losses, 5)` (Historical VaR) or `norm.ppf(0.05) * vol` (Parametric VaR) is unnecessary.
- Monte Carlo VaR requires Cholesky decomposition of the covariance matrix (`np.linalg.cholesky(cov)`) followed by random sampling (`np.random.multivariate_normal`). These are one-liners in numpy.
- The Ledoit-Wolf covariance from sklearn ensures the covariance matrix is positive definite, which is the hard part. The VaR calculation itself is straightforward.

**Implementation approach:**

| VaR Method | Implementation | Lines of Code |
|------------|---------------|---------------|
| Historical | `np.percentile(portfolio_returns, (1-confidence)*100)` | ~10 |
| Parametric (Gaussian) | `mu - z_score * vol * sqrt(horizon)` | ~15 |
| Parametric (t-Student) | `scipy.stats.t.ppf(alpha, df) * vol * sqrt(horizon)` | ~20 |
| Monte Carlo | `np.random.multivariate_normal(mu, cov, n_sims)` then percentile | ~30 |
| Component VaR | Marginal VaR decomposition via covariance | ~25 |
| Expected Shortfall | `np.mean(returns[returns < var_threshold])` | ~5 |

**Stress testing:** Predefined shock scenarios (2015 BR Crisis, 2020 COVID, Taper Tantrum) applied as deterministic percentage moves to positions. No external library needed -- this is dictionary lookup + arithmetic.

---

## Signal Aggregation -- Build Custom

**Confidence:** HIGH

No external library exists for combining macro model signals. Signal aggregation is domain-specific logic:
- Confidence-weighted averaging of agent signals by instrument
- Crowding penalty when >80% of strategies agree (reduce position to avoid consensus trades)
- Staleness discount for signals based on old data
- Regime overlay from Cross-Asset Agent

This is ~150 lines of business logic using numpy for weighted averages. No framework needed.

---

## Complete Recommended Stack for v2.0

### Core New Dependencies (add to pyproject.toml)

```toml
dependencies = [
    # ... existing v1.0 dependencies ...

    # v2.0 Quantitative Modeling
    "statsmodels>=0.14.6",       # OLS, Kalman Filter, state space models
    "scikit-learn>=1.6",         # Ledoit-Wolf covariance for VaR/portfolio
    "hmmlearn>=0.3.3",           # HMM regime detection
    "anthropic>=0.81.0",         # Claude API for narrative generation
    "fastapi>=0.109",            # API framework (make explicit)
    "uvicorn[standard]>=0.27",   # ASGI server (make explicit)
    "matplotlib>=3.8",           # Backtest report charts (equity curves, heatmaps)
]
```

### Supporting Libraries (already available via transitive deps)

| Library | Provided By | Use in v2.0 |
|---------|-------------|-------------|
| numpy | scipy, pandas, statsmodels | All numeric computation |
| pandas | yfinance, statsmodels | DataFrames for features, signals, equity curves |
| scipy | already installed | Curve fitting (v1.0), optimization (scipy.minimize for risk parity) |

### Development Dependencies (add to [dev])

```toml
[project.optional-dependencies]
dev = [
    # ... existing dev deps ...
    "pytest-timeout>=2.2.0",     # Timeout for integration tests
]
```

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Econometric regression | statsmodels OLS | sklearn LinearRegression | No p-values, no diagnostic tests, no statistical inference |
| Regime detection | hmmlearn GaussianHMM | Manual rule-based | HMM provides transition probabilities; rule-based is the fallback |
| Kalman Filter | statsmodels UnobservedComponents | filterpy, pykalman | statsmodels already a dependency; UC class handles Laubach-Williams directly |
| Covariance estimation | sklearn LedoitWolf | numpy sample covariance | Sample cov is ill-conditioned; Ledoit-Wolf shrinkage is essential |
| LLM SDK | anthropic (official) | LangChain, litellm | One API call does not need an abstraction framework |
| Backtesting | Custom engine | Backtrader, Zipline, bt | Equity-focused; no point-in-time support; impedance mismatch with macro |
| VaR calculation | numpy + scipy | ibaris/VaR, riskfolio-lib | Thin wrappers; 50 lines of numpy replaces the package |
| Dashboard | Single-file HTML + CDN React | Vite + React app | Zero build step; monitoring tool, not user product |
| Charts | Recharts (CDN) | Plotly, D3 | Recharts simpler API; sufficient for line/bar/area charts |
| Portfolio optimization | scipy.optimize.minimize | cvxpy, PyPortfolioOpt | Risk parity is one scipy.minimize call; no need for full optimization library |

---

## Installation

```bash
# Core v2.0 dependencies
pip install statsmodels>=0.14.6 scikit-learn>=1.6 hmmlearn>=0.3.3 anthropic>=0.81.0 matplotlib>=3.8

# Or install from pyproject.toml
pip install -e ".[dev]"
```

### Environment Variables (new for v2.0)

```env
# LLM (optional -- fallback to template if not set)
ANTHROPIC_API_KEY=your_key_here
CLAUDE_MODEL=claude-sonnet-4-20250514

# Risk Management
RISK_VAR_CONFIDENCE=0.95
RISK_MAX_LEVERAGE=3.0
RISK_MAX_DRAWDOWN=0.10
```

---

## Dependency Weight Analysis

| Library | Size (installed) | Transitive Deps | Justification |
|---------|-----------------|-----------------|---------------|
| statsmodels | ~40 MB | scipy, patsy | Heavy but essential. No alternative for econometric inference. |
| scikit-learn | ~30 MB | scipy, joblib, threadpoolctl | Heavy but uses only covariance module. Justified for Ledoit-Wolf. |
| hmmlearn | ~2 MB | scikit-learn (already added) | Lightweight. Adds negligible overhead. |
| anthropic | ~5 MB | httpx (already installed), pydantic (already installed) | Lightweight. Perfect fit with existing dependency tree. |
| matplotlib | ~35 MB | numpy, pillow | Heavy but standard. Needed for backtest report generation (PNG equity curves). |

**Total new dependency footprint:** ~110 MB installed. Acceptable for a quantitative research system.

---

## Architecture Notes for v2.0

1. **statsmodels for model fitting, numpy for signal generation.** Agents fit models (OLS, Kalman) during `run_models()` which runs once per rebalance date. The fitted parameters then produce signals using numpy arithmetic. statsmodels is NOT on the hot path.

2. **Sync database access for agents.** Agent `load_data()` uses sync SQLAlchemy sessions (psycopg2). Agents run sequentially in dependency order (inflation -> monetary -> fiscal -> fx -> cross_asset). Async is unnecessary complexity here because agents have no I/O parallelism opportunity -- each agent depends on the previous.

3. **Point-in-time data loader is the single data access pattern.** Both live execution and backtesting call `PointInTimeDataLoader.get_macro_series(series_id, as_of_date)`. The loader enforces `WHERE release_time <= as_of_date`. This is the critical invariant of the entire system.

4. **Anthropic SDK is async-compatible but used in sync context.** Daily pipeline runs in asyncio (`scripts/daily_run.py`), so use `AsyncAnthropic`. Backtesting uses sync code, so skip narrative generation during backtests (it adds latency and cost with no value for backtesting).

5. **matplotlib generates static PNGs, not interactive charts.** Backtest reports save equity curve plots as PNG files. The interactive dashboard uses Recharts (browser-side) which fetches data from the API. These are separate concerns.

---

*Research completed: 2026-02-20*
*Confidence: HIGH for core modeling stack (statsmodels, sklearn), MEDIUM for hmmlearn (maintenance status), HIGH for anthropic SDK, HIGH for dashboard approach*

# Phase 12: Portfolio Construction & Risk Management - Research

**Researched:** 2026-02-21
**Domain:** Signal aggregation, portfolio construction, quantitative risk management (VaR, CVaR, stress testing, circuit breakers)
**Confidence:** HIGH

## Summary

Phase 12 takes the outputs of 5 analytical agents (Phases 8-10) and 8 trading strategies (Phase 11) and wires them into a self-managing portfolio. The work divides into three pillars: (1) signal aggregation -- combining agent-level signals into directional consensus per asset class using weighted voting with conflict detection and CrossAsset veto; (2) portfolio construction -- converting strategy positions into net portfolio weights using risk parity with conviction overlay, regime scaling, and constraint enforcement; (3) risk management -- a complete engine computing Monte Carlo VaR/CVaR, running historical stress scenarios, enforcing risk limits, and managing tiered circuit breakers.

The existing codebase provides solid foundations. Agents produce `AgentSignal` dataclasses with `direction`, `strength`, `confidence`, and `value` fields. Strategies produce `StrategyPosition` objects with `weight`, `confidence`, and `direction`. The `Portfolio` class in `src/backtesting/portfolio.py` already handles notional-based positions with mark-to-market and rebalancing with costs. The `BacktestResult` dataclass in `src/backtesting/metrics.py` computes Sharpe, Sortino, max drawdown, and other metrics. All code is pure Python using numpy, scipy, pandas, statsmodels, and scikit-learn -- no external quant libraries (PyPortfolioOpt, riskfolio-lib) are in the project, and the pattern is to implement from these primitives.

**Primary recommendation:** Build all Phase 12 modules in a new `src/portfolio/` package (signal aggregation, portfolio construction, capital allocation) and a new `src/risk/` package (VaR, stress testing, limits, drawdown management, risk monitoring). Use numpy/scipy/sklearn for all computations -- the existing stack is sufficient and no new dependencies are needed. Follow the codebase's established patterns: frozen dataclasses for configs, mutable dataclasses for results, structlog logging, and pure-function computation cores.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Signal conflict resolution:** Weighted vote -- each agent has a fixed weight, the weighted sum determines net direction. Conflicting signals partially cancel out.
- **Agent weights:** Domain-tuned per asset class. E.g., for DI rates: MonetaryPolicy gets highest weight, Inflation second, etc. Weights are NOT equal -- each agent's relevance varies by asset class. Claude to determine sensible default weight matrices during implementation.
- **CrossAsset veto:** CrossAssetAgent has veto power to reduce/flatten positions when its regime score is extreme (e.g., < -0.7). Other agents cannot veto.
- **Intra-asset-class conflicts:** When strategies within the same asset class conflict (e.g., RATES_BR_01 says LONG but RATES_BR_02 says SHORT), flag the conflict in the risk report AND dampen the net position size (reduce by 30-50%) as a penalty for low conviction.
- **Base methodology:** Risk parity + conviction overlay. Risk parity as the base allocation (each position sized to contribute equally to portfolio risk), then scaled up/down by signal conviction.
- **Regime scaling:** 3 discrete regimes -- Risk-On (100% allocation), Neutral (70%), Risk-Off (40%). Sharp steps, easy to reason about.
- **Regime transitions:** Gradual adjustment over 2-3 days when regime changes (e.g., 50% of adjustment day 1, 100% by day 3). Avoids market impact and whipsaw.
- **Max position concentration:** No single position can exceed 20% of portfolio risk budget.
- **Rebalancing trigger:** Threshold-triggered -- rebalance only when positions drift beyond thresholds (e.g., >5% deviation from target). Only trades when needed, no fixed daily schedule.
- **Drawdown response:** Tiered de-risking. At -5% drawdown, reduce exposure by 50%. At -10%, flatten all positions. Clear escalation path. (Note: roadmap specifies 3 levels at -3%/-5%/-8% -- Claude to reconcile these during planning, using the user's intent of tiered escalation.)
- **Re-entry conditions:** Automatic re-entry after a cooldown period (5 trading days) if drawdown recovers above -3%. Gradual ramp-up to full exposure over 3 days.
- **Loss limit granularity:** Three layers of circuit breakers -- portfolio-level drawdown, per-strategy daily loss, and per-asset-class loss. Each can fire independently.
- **Alerting:** Log to monitoring system + send real-time alert (webhook/email). Every circuit breaker event is logged with full context (positions, P&L, signals at time of trigger).
- **Scenario type:** Historical replay only -- replaying actual market moves from real crises. No hypothetical/synthetic scenarios in this phase.
- **Stress test impact:** Advisory only -- stress results are reported but don't automatically change positions. Risk manager reviews and decides.
- **VaR methodology:** Monte Carlo simulation with fitted distributions. Most flexible, captures complex portfolio interactions.
- **Computation frequency:** Daily VaR/CVaR calculations + weekly full stress scenario replays. Balances computational cost with timeliness.

### Claude's Discretion
- Exact domain-tuned weight matrices per agent per asset class (within the weighted vote framework)
- Monte Carlo simulation parameters (number of simulations, distribution fitting approach)
- Historical stress scenario selection (roadmap suggests Taper Tantrum 2013, BR Crisis 2015, COVID 2020, Rate Shock 2022 -- Claude may adjust)
- Exact drift thresholds for rebalancing trigger
- Cooldown period fine-tuning
- Risk report format and content layout
- Damping factor for intra-asset-class conflicts (within 30-50% range)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PORT-01 | SignalAggregator combining agent signals into directional consensus per asset class with conflict detection | Weighted vote aggregation using AgentSignal.direction/confidence/strength fields; group by StrategyConfig.asset_class; conflict detection via direction disagreement within asset class |
| PORT-02 | PortfolioConstructor converting strategy positions to net portfolio weights with risk-budget scaling and regime adjustment (RISK_OFF -> -50%) | Risk parity via scipy.optimize.minimize (SLSQP) with equal risk contribution objective; conviction overlay using STRENGTH_MAP values; 3-level regime scaling (100%/70%/40%) |
| PORT-03 | CapitalAllocator enforcing portfolio constraints (max leverage, max single position, max asset class concentration) | Constraint checks on weights: max 3x leverage (sum abs weights), max 25% single position (per roadmap), max 50% asset class; reuses existing leverage enforcement pattern from Portfolio.rebalance() |
| PORT-04 | Rebalance threshold check (drift > 5% triggers rebalance) and trade computation | Drift = abs(current_weight - target_weight); compute trades as delta notional values; follows existing Portfolio.rebalance() trade computation pattern |
| RISK-01 | VaR calculator with historical VaR (95% and 99%, 1-day horizon) from portfolio returns | np.percentile on portfolio return series; straightforward quantile computation |
| RISK-02 | Parametric VaR using Gaussian assumption with portfolio covariance | sklearn.covariance.LedoitWolf for robust covariance estimation; scipy.stats.norm.ppf for quantile |
| RISK-03 | Expected Shortfall (CVaR) as conditional expectation beyond VaR threshold | Mean of returns below VaR threshold (historical); analytical formula for parametric (Gaussian); mean of tail simulations for Monte Carlo |
| RISK-04 | Stress testing against 4+ historical scenarios (2013 Taper Tantrum, 2015 BR Crisis, 2020 COVID, 2022 Rate Shock) | Historical replay: apply scenario shocks (% moves) to current positions; compute position-level and portfolio-level P&L impact |
| RISK-05 | Risk limits configuration (max VaR, max drawdown, max leverage, max position, max asset class concentration) | Configurable dataclass with 9 limit definitions; check current portfolio state against each limit; compute utilization % |
| RISK-06 | Pre-trade limit checking -- verify proposed trades don't breach limits before execution | Simulate portfolio state after proposed trades; check all limits on hypothetical state; return pass/fail with breach details |
| RISK-07 | DrawdownManager with 3-level circuit breakers: L1 (-3%) reduce 25%, L2 (-5%) reduce 50%, L3 (-8%) close all | Track running drawdown from equity high-water mark; tiered response with escalation; cooldown period (5 days) and gradual re-entry |
| RISK-08 | RiskMonitor generating aggregate risk report (portfolio VaR, stress tests, limit utilization, circuit breaker status) | Orchestrator class that runs VaR, stress tests, checks limits, checks circuit breakers; produces RiskReport dataclass |
| TESTV2-04 | Unit tests for risk management (VaR calculation, limit checking, circuit breakers) | Test with known synthetic returns (constant, trending, crash scenarios); verify VaR/CVaR values against manual calculation; test circuit breaker state transitions |
</phase_requirements>

## Standard Stack

### Core (already installed -- no new dependencies needed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| numpy | >=1.26 | Array computation, percentile/quantile for VaR, random number generation for Monte Carlo | Already used throughout codebase; np.percentile for historical VaR, np.random for MC simulations, np.linalg.cholesky for correlated draws |
| scipy | >=1.12 | Optimization (risk parity), statistical distributions (t-distribution fitting for MC VaR), Cholesky decomposition | scipy.optimize.minimize with SLSQP for risk parity; scipy.stats.t.fit() for distribution fitting; scipy.stats.norm.ppf for parametric VaR |
| pandas | >=2.1 | Time series manipulation, rolling windows, return computation | Already used for equity curves, price histories; pd.DataFrame for returns matrix |
| scikit-learn | >=1.4 | Covariance estimation (Ledoit-Wolf shrinkage) | sklearn.covariance.LedoitWolf for robust covariance matrix estimation; already installed, used in agents |
| statsmodels | >=0.14 | Statistical testing, distribution diagnostics | Available for Jarque-Bera normality tests, QQ plots for distribution validation |
| structlog | >=24.4 | Structured logging | Codebase standard; all agents and strategies use structlog |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | >=2.10 | Config validation for risk limits | Use Pydantic models for RiskLimitsConfig if runtime validation is needed; otherwise frozen dataclasses match codebase pattern |
| matplotlib | >=3.8 | Risk report visualizations (drawdown charts, VaR distribution plots) | For generating risk report charts; already used in backtesting report |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled risk parity (scipy.optimize) | PyPortfolioOpt / riskfolio-lib | External libs add dependency; codebase pattern is to use primitives (numpy/scipy/sklearn). Risk parity optimizer is ~30 lines with scipy.minimize -- not worth adding a dependency |
| Hand-rolled VaR (numpy.percentile) | empyrical / pyfolio | These are primarily analysis/reporting tools, not computation engines; numpy.percentile is the standard approach for historical VaR |
| sklearn LedoitWolf | Manual shrinkage implementation | sklearn's implementation is well-tested, already in the project; no reason to reimplement |

**Installation:** No new packages needed. All required libraries are already in pyproject.toml.

## Architecture Patterns

### Recommended Project Structure
```
src/
├── portfolio/                    # NEW -- signal aggregation + portfolio construction
│   ├── __init__.py
│   ├── signal_aggregator.py      # PORT-01: weighted vote, conflict detection
│   ├── portfolio_constructor.py  # PORT-02: risk parity + conviction overlay + regime
│   └── capital_allocator.py      # PORT-03, PORT-04: constraints, drift check, trades
├── risk/                         # NEW -- risk management engine
│   ├── __init__.py
│   ├── var_calculator.py         # RISK-01, RISK-02, RISK-03: VaR, parametric VaR, CVaR
│   ├── stress_tester.py          # RISK-04: historical scenario replay
│   ├── risk_limits.py            # RISK-05, RISK-06: limit config, pre-trade checking
│   ├── drawdown_manager.py       # RISK-07: 3-level circuit breakers
│   └── risk_monitor.py           # RISK-08: aggregate risk report orchestrator
├── agents/                       # EXISTING -- provides AgentSignal, AgentReport
├── strategies/                   # EXISTING -- provides StrategyPosition, ALL_STRATEGIES
├── backtesting/                  # EXISTING -- provides Portfolio, BacktestResult
└── core/                         # EXISTING -- provides enums, config, models
```

### Pattern 1: Dataclass-First Design (Matching Codebase Convention)
**What:** All inputs and outputs are frozen/unfrozen dataclasses. No raw dicts for structured data.
**When to use:** Every new type in Phase 12 -- signal aggregation results, portfolio targets, VaR results, stress results, risk limits, circuit breaker state, risk reports.
**Example:**
```python
# Follows AgentSignal / StrategyPosition pattern from existing code
from dataclasses import dataclass, field
from datetime import date, datetime
from src.core.enums import AssetClass, SignalDirection

@dataclass
class AggregatedSignal:
    """Consensus signal for a single asset class after weighted vote aggregation."""
    asset_class: AssetClass
    direction: SignalDirection
    net_score: float           # weighted sum in [-1, +1]
    confidence: float          # [0, 1]
    contributing_agents: list[dict]
    conflicts_detected: bool
    conflict_details: list[str]
    veto_applied: bool         # True if CrossAsset veto fired
    timestamp: datetime = field(default_factory=datetime.utcnow)
```

### Pattern 2: Pure Computation + Orchestrator (Template Method)
**What:** Core math functions are pure (take data in, return results). An orchestrator class composes them.
**When to use:** VaR computation, stress testing, risk monitoring. Keeps computation testable without mocks.
**Example:**
```python
# Pure function for historical VaR -- easy to test
def compute_historical_var(
    returns: np.ndarray, confidence: float = 0.95
) -> tuple[float, float]:
    """Compute VaR and CVaR from return series.

    Returns:
        (var, cvar) -- both as negative numbers representing loss.
    """
    var = float(np.percentile(returns, (1 - confidence) * 100))
    cvar = float(returns[returns <= var].mean())
    return var, cvar

# Orchestrator class composes pure functions
class VaRCalculator:
    def __init__(self, confidence: float = 0.95, horizon_days: int = 1):
        self.confidence = confidence
        self.horizon_days = horizon_days

    def calculate(self, portfolio_returns: np.ndarray, method: str = "historical") -> VaRResult:
        if method == "historical":
            var, cvar = compute_historical_var(portfolio_returns, self.confidence)
        elif method == "parametric":
            var, cvar = compute_parametric_var(portfolio_returns, self.confidence)
        elif method == "monte_carlo":
            var, cvar = compute_monte_carlo_var(portfolio_returns, self.confidence)
        return VaRResult(var_pct=var, cvar_pct=cvar, method=method, ...)
```

### Pattern 3: Registry Pattern for Strategies and Agents
**What:** ALL_STRATEGIES dict maps strategy_id to class; AgentRegistry maps agent_id to instance. SignalAggregator should accept these registries as input, not hard-code agent/strategy lists.
**When to use:** When SignalAggregator needs to iterate over all agents/strategies. When PortfolioConstructor needs to look up strategy configs (asset class, instruments).
**Example:**
```python
class SignalAggregator:
    def __init__(self, agent_weights: dict[str, dict[AssetClass, float]]):
        """
        agent_weights: {agent_id: {AssetClass: weight}}
        e.g., {"monetary_agent": {AssetClass.FIXED_INCOME: 0.35, AssetClass.FX: 0.15, ...}}
        """
        self.agent_weights = agent_weights

    def aggregate(
        self,
        agent_reports: dict[str, AgentReport],
        strategy_positions: dict[str, list[StrategyPosition]],
    ) -> list[AggregatedSignal]:
        ...
```

### Pattern 4: State Machine for Circuit Breakers
**What:** DrawdownManager as a state machine with well-defined states and transitions.
**When to use:** Circuit breaker logic where state (NORMAL, L1, L2, L3, COOLDOWN) determines behavior.
**Example:**
```python
from enum import Enum

class CircuitBreakerState(str, Enum):
    NORMAL = "NORMAL"
    L1_TRIGGERED = "L1_TRIGGERED"      # -3% drawdown, reduce 25%
    L2_TRIGGERED = "L2_TRIGGERED"      # -5% drawdown, reduce 50%
    L3_TRIGGERED = "L3_TRIGGERED"      # -8% drawdown, close all
    COOLDOWN = "COOLDOWN"              # 5-day waiting period
    RECOVERING = "RECOVERING"          # Gradual ramp-up

@dataclass
class DrawdownState:
    state: CircuitBreakerState
    high_water_mark: float
    current_drawdown_pct: float
    triggered_at: date | None
    cooldown_remaining_days: int
    recovery_scale: float        # 0.0 to 1.0 during ramp-up
```

### Anti-Patterns to Avoid
- **Mixing computation and I/O:** VaR calculations should be pure numpy/scipy functions. Database reads for returns should happen in the orchestrator, not inside the VaR math.
- **Hard-coding agent/strategy lists:** Use the existing registries (AgentRegistry, ALL_STRATEGIES). New agents/strategies added in future phases should automatically flow through.
- **Mutable config objects:** Follow the codebase's `frozen=True` pattern for configs (StrategyConfig, BacktestConfig). Risk limits config should be immutable too.
- **Float equality comparisons in circuit breakers:** Use threshold comparisons with small epsilon, never `==` on floats for drawdown levels.
- **Ignoring the async/sync bridge:** The codebase uses sync execution for agents/strategies (BaseAgent.run is sync, BaseStrategy.generate_signals is sync). Keep Phase 12 modules sync to match.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Covariance matrix estimation | Sample covariance with manual shrinkage | `sklearn.covariance.LedoitWolf` | Handles numerical stability, optimal shrinkage coefficient; well-tested against edge cases (singular matrices, small samples) |
| Risk parity optimization | Iterative heuristic / equal-weight approximation | `scipy.optimize.minimize(method='SLSQP')` with risk contribution objective | SLSQP handles the nonlinear constraints correctly; heuristics often fail to converge for correlated assets |
| Cholesky decomposition for Monte Carlo | Manual matrix factorization | `np.linalg.cholesky` or `scipy.linalg.cholesky` | Numerical stability, handles near-singular matrices gracefully, orders of magnitude faster |
| Percentile computation for VaR | Manual sorting + index lookup | `np.percentile` / `np.quantile` | Handles interpolation modes correctly, vectorized, edge-case tested |
| Distribution fitting for Monte Carlo | Manual MLE optimization | `scipy.stats.t.fit(data)` | Handles convergence, initial parameter estimation, bounded optimization internally |

**Key insight:** The entire Phase 12 computation stack (VaR, risk parity, Monte Carlo, covariance) is well-served by numpy + scipy + sklearn. These are the exact tools that quantitative finance teams use. Adding higher-level finance libraries (PyPortfolioOpt, empyrical, pyfolio) would add dependency complexity without meaningfully simplifying the ~200 lines of core math involved.

## Common Pitfalls

### Pitfall 1: Singular Covariance Matrices
**What goes wrong:** With 8 strategies across 4-5 asset classes, the returns matrix may have more columns than rows, or highly correlated columns. Sample covariance becomes singular, Cholesky fails, risk parity optimizer diverges.
**Why it happens:** Short lookback windows, similar strategies on the same DI curve, or strategies that haven't traded yet (all-zero returns).
**How to avoid:** Always use Ledoit-Wolf shrinkage covariance (already planned). Add a minimum eigenvalue floor: after shrinkage, clamp eigenvalues to `max(eigenvalue, 1e-8)`. For Cholesky, use `scipy.linalg.cholesky` which raises `LinAlgError` for non-positive-definite matrices -- catch and fall back to eigenvalue-clamped version.
**Warning signs:** `LinAlgError` from cholesky, `NaN` in optimizer output, zero-valued risk contributions.

### Pitfall 2: VaR Underestimation with Short History
**What goes wrong:** Historical VaR with <252 days of returns misses tail events. The 99% VaR from 100 observations is just the single worst day -- statistically meaningless.
**Why it happens:** New strategies with short backtests, or using only recent calm-market data.
**How to avoid:** Require minimum 252 observations for historical VaR (1 year of daily returns). If insufficient history, fall back to parametric VaR with warning flag. For Monte Carlo, fit distributions on available data but flag the confidence level.
**Warning signs:** Historical VaR that looks suspiciously small; VaR of zero; CVaR == VaR (only one observation in the tail).

### Pitfall 3: Circuit Breaker Oscillation (Whipsaw)
**What goes wrong:** Portfolio hits -3% drawdown, reduces 25%, then recovers to -2.5%, resumes full size, drops again to -3.2%, reduces again... Repeated cycling between states.
**Why it happens:** No cooldown period between de-risk and re-entry; drawdown oscillates around the threshold.
**How to avoid:** The user specified 5-day cooldown + gradual re-entry (3 days). Implement hysteresis: the recovery threshold should be meaningfully better than the trigger threshold (e.g., trigger at -3%, but only reset after recovering to better than -2%). This is already partially addressed by the user's "recover above -3%" specification but needs careful implementation.
**Warning signs:** Frequent state transitions in circuit breaker log; high transaction costs from repeated position reductions.

### Pitfall 4: Regime Score vs. Regime Classification Mismatch
**What goes wrong:** The CrossAssetAgent's `CROSSASSET_REGIME` signal has a continuous `value` field (regime score in [-1, +1]) but the PortfolioConstructor needs a discrete regime (RISK_ON / NEUTRAL / RISK_OFF). The mapping thresholds must be consistent.
**Why it happens:** The regime model uses thresholds (+0.2 / -0.2) for direction, but the portfolio constructor needs different thresholds for the 3-level scaling system.
**How to avoid:** Define clear threshold constants in a shared location. The regime model's `value` field already provides a score in [-1, +1]. Map to: score < -0.3 -> RISK_ON (100%), -0.3 <= score <= 0.3 -> NEUTRAL (70%), score > 0.3 -> RISK_OFF (40%). The CrossAsset veto fires at score < -0.7 or > 0.7 (extreme). Document these thresholds in a config dataclass.
**Warning signs:** Regime shows NEUTRAL but positions are being scaled to 40%; or RISK_OFF but no scaling applied.

### Pitfall 5: Agent Weight Matrix Incompleteness
**What goes wrong:** When adding agent weight matrices per asset class, some agents may not be relevant to some asset classes (e.g., FiscalAgent for FX). If all weights are zero for an asset class, the weighted vote produces 0/0 division.
**Why it happens:** Sparse weight matrix with missing entries defaulting to 0.
**How to avoid:** Always normalize weights by the sum of non-zero weights for each asset class. If all agent weights are zero for an asset class, produce a NO_SIGNAL consensus rather than dividing by zero. Document explicitly which agents contribute to which asset classes.
**Warning signs:** `NaN` in aggregated signals; division by zero warnings.

### Pitfall 6: Notional vs. Weight Confusion
**What goes wrong:** The backtesting `Portfolio` tracks positions as notional values, but strategies produce target weights. The `Portfolio.rebalance()` method converts weights to notionals via `total_equity * weight`. Phase 12's PortfolioConstructor must output weights (not notionals) to be compatible.
**Why it happens:** Mixing the two representations in different parts of the pipeline.
**How to avoid:** Establish clear convention: SignalAggregator and PortfolioConstructor always work in weight space ([-1, +1] per position). CapitalAllocator converts to notionals only at the final step when computing trades. This matches the existing `Portfolio.rebalance(target_weights, ...)` interface.
**Warning signs:** Position sizes 1000x too large or too small; leverage calculations that don't make sense.

## Code Examples

### Historical VaR and CVaR (Pure Function)
```python
# Source: Standard quantitative finance implementation using numpy
import numpy as np

def compute_historical_var(
    returns: np.ndarray,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Compute VaR and CVaR from a return series.

    Args:
        returns: Array of portfolio returns (daily).
        confidence: Confidence level (0.95 or 0.99).

    Returns:
        (var, cvar) -- VaR as the loss threshold, CVaR as the mean of tail losses.
        Both are negative numbers (losses).
    """
    if len(returns) < 10:
        return 0.0, 0.0
    alpha = 1 - confidence
    var = float(np.percentile(returns, alpha * 100))
    tail = returns[returns <= var]
    cvar = float(tail.mean()) if len(tail) > 0 else var
    return var, cvar
```

### Monte Carlo VaR with Fitted Distributions
```python
# Source: scipy.stats.t for distribution fitting, np.linalg.cholesky for correlation
import numpy as np
from scipy import stats
from sklearn.covariance import LedoitWolf

def compute_monte_carlo_var(
    returns_matrix: np.ndarray,  # (n_obs, n_assets)
    weights: np.ndarray,         # (n_assets,)
    confidence: float = 0.95,
    n_simulations: int = 10_000,
) -> tuple[float, float]:
    """Monte Carlo VaR using t-distribution marginals and Cholesky correlation.

    Steps:
    1. Fit t-distribution to each asset's returns (scipy.stats.t.fit)
    2. Estimate correlation matrix using Ledoit-Wolf shrinkage
    3. Generate correlated uniform samples via Cholesky + normal CDF
    4. Transform to t-distributed marginals via inverse CDF
    5. Compute portfolio returns and extract VaR/CVaR
    """
    n_obs, n_assets = returns_matrix.shape

    # 1. Fit t-distribution to each marginal
    t_params = []
    for i in range(n_assets):
        df, loc, scale = stats.t.fit(returns_matrix[:, i])
        t_params.append((df, loc, scale))

    # 2. Robust covariance -> correlation matrix
    lw = LedoitWolf().fit(returns_matrix)
    cov = lw.covariance_
    std = np.sqrt(np.diag(cov))
    std[std < 1e-10] = 1e-10
    corr = cov / np.outer(std, std)
    np.fill_diagonal(corr, 1.0)

    # 3. Cholesky decomposition
    L = np.linalg.cholesky(corr)

    # 4. Generate correlated samples
    z = np.random.standard_normal((n_simulations, n_assets))
    corr_z = z @ L.T

    # 5. Transform to t-distributed marginals
    uniform = stats.norm.cdf(corr_z)
    sim_returns = np.zeros_like(uniform)
    for i, (df, loc, scale) in enumerate(t_params):
        sim_returns[:, i] = stats.t.ppf(uniform[:, i], df, loc, scale)

    # 6. Portfolio returns
    portfolio_returns = sim_returns @ weights
    alpha = 1 - confidence
    var = float(np.percentile(portfolio_returns, alpha * 100))
    cvar = float(portfolio_returns[portfolio_returns <= var].mean())
    return var, cvar
```

### Risk Parity Optimization
```python
# Source: scipy.optimize.minimize with SLSQP for risk parity
import numpy as np
from scipy.optimize import minimize

def risk_parity_weights(cov_matrix: np.ndarray) -> np.ndarray:
    """Compute risk parity weights where each asset contributes equally to portfolio risk.

    Objective: minimize sum of (RC_i - 1/n)^2
    where RC_i = w_i * (Sigma @ w)_i / (w' Sigma w)

    Args:
        cov_matrix: (n x n) covariance matrix.

    Returns:
        Optimal weights array of shape (n,).
    """
    n = cov_matrix.shape[0]
    target_risk = 1.0 / n

    def objective(w):
        port_var = w @ cov_matrix @ w
        if port_var < 1e-12:
            return 0.0
        marginal_contrib = cov_matrix @ w
        risk_contrib = w * marginal_contrib / port_var
        return float(np.sum((risk_contrib - target_risk) ** 2))

    w0 = np.ones(n) / n
    bounds = [(0.01, 1.0)] * n
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

    result = minimize(
        objective, w0, method="SLSQP",
        bounds=bounds, constraints=constraints,
        options={"ftol": 1e-12, "maxiter": 1000},
    )
    return result.x / result.x.sum()  # renormalize
```

### Stress Scenario Application
```python
# Source: Standard financial stress testing -- apply shocks to positions
from dataclasses import dataclass

@dataclass(frozen=True)
class StressScenario:
    name: str
    description: str
    shocks: dict[str, float]  # {instrument: pct_move} e.g., {"USDBRL": 0.20} = +20%
    historical_period: str    # e.g., "2020-02-15 to 2020-03-23"

def apply_stress_scenario(
    positions: dict[str, float],     # {instrument: notional}
    scenario: StressScenario,
) -> tuple[float, dict[str, float]]:
    """Apply stress scenario shocks to positions and compute P&L.

    Returns:
        (portfolio_pnl, {instrument: position_pnl})
    """
    pnl_by_instrument: dict[str, float] = {}
    for instrument, notional in positions.items():
        shock = scenario.shocks.get(instrument, 0.0)
        pnl = notional * shock
        pnl_by_instrument[instrument] = pnl
    total_pnl = sum(pnl_by_instrument.values())
    return total_pnl, pnl_by_instrument
```

### Agent Weight Matrix (Discretion Item -- Recommended Defaults)
```python
# Recommended default agent weight matrices per asset class
# Weights are normalized to sum to 1.0 per asset class
# Higher weight = more influence on directional consensus for that asset class

from src.core.enums import AssetClass

AGENT_WEIGHTS: dict[str, dict[AssetClass, float]] = {
    "inflation_agent": {
        AssetClass.FIXED_INCOME: 0.25,  # Inflation directly affects rates
        AssetClass.FX: 0.10,            # Inflation differentials affect FX
        AssetClass.EQUITY_INDEX: 0.10,
        AssetClass.COMMODITY: 0.15,
    },
    "monetary_agent": {
        AssetClass.FIXED_INCOME: 0.35,  # Most relevant for DI rates
        AssetClass.FX: 0.20,            # Rate differentials drive carry
        AssetClass.EQUITY_INDEX: 0.15,
        AssetClass.COMMODITY: 0.05,
    },
    "fiscal_agent": {
        AssetClass.FIXED_INCOME: 0.20,  # Fiscal risk premium in DI
        AssetClass.FX: 0.15,            # Fiscal drives BRL risk
        AssetClass.EQUITY_INDEX: 0.20,  # Fiscal outlook affects equities
        AssetClass.COMMODITY: 0.05,
    },
    "fx_agent": {
        AssetClass.FIXED_INCOME: 0.05,  # Weak link to rates
        AssetClass.FX: 0.40,            # Primary domain
        AssetClass.EQUITY_INDEX: 0.10,
        AssetClass.COMMODITY: 0.20,
    },
    "cross_asset_agent": {
        AssetClass.FIXED_INCOME: 0.15,  # Regime context for all
        AssetClass.FX: 0.15,
        AssetClass.EQUITY_INDEX: 0.45,  # Regime most impacts equities
        AssetClass.COMMODITY: 0.55,
    },
}
# Note: Weights per asset class should sum to 1.0 across all agents.
# cross_asset_agent also has VETO power (separate from weighted vote).
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sample covariance for portfolio optimization | Ledoit-Wolf / OAS shrinkage estimators | 2004+ (Ledoit-Wolf paper) | Dramatically more stable portfolio weights; essential when n_assets > n_observations/5 |
| VaR only (single quantile) | VaR + CVaR (Expected Shortfall) | Basel III (2013+) | CVaR captures tail shape, is subadditive (unlike VaR), better for portfolio optimization |
| Gaussian VaR assumptions | Student-t / fitted distributions for MC VaR | Post-2008 consensus | Fat-tailed distributions capture real market crash behavior; Gaussian dramatically underestimates tail risk |
| Fixed daily rebalancing | Threshold-triggered rebalancing | Industry standard | Reduces transaction costs by 30-50% vs. daily; only trades when drift is meaningful |
| Hard position limits | Risk-budget-based limits (VaR contribution per position) | Post-2010 industry shift | Accounts for correlation; a hedging position and a directional bet should have different limits |

**Deprecated/outdated:**
- Equal-weighted risk parity (treats all correlations as zero): Use optimization-based risk parity with full covariance
- Daily scheduled rebalancing: Use threshold-triggered (user decision)
- Single circuit breaker threshold: Use tiered response (user decision)

## Discretion Recommendations

### Monte Carlo Parameters
- **Number of simulations:** 10,000 for daily VaR (runs in ~0.5s for 8 assets). Increase to 50,000 for weekly stress reports. Configurable via parameter.
- **Distribution fitting:** Use `scipy.stats.t.fit()` for Student-t marginals. If t-fit fails (< 30 observations), fall back to normal distribution.
- **Lookback for fitting:** 504 trading days (2 years) as default. Recalibrate weekly (not daily -- distribution parameters change slowly).

### Historical Stress Scenarios
The 4 required scenarios from the roadmap are well-chosen. Recommended shocks:

1. **Taper Tantrum 2013** (May-Aug 2013): USDBRL +15%, DI_PRE_1Y +200bps, DI_PRE_5Y +250bps, UST_10Y +100bps, IBOVESPA -15%
2. **BR Crisis 2015** (Sep 2015 - Feb 2016): USDBRL +30%, DI_PRE_1Y +400bps, DI_PRE_5Y +300bps, IBOVESPA -25%, CDS_BR +150bps
3. **COVID 2020** (Feb-Mar 2020): USDBRL +20%, DI_PRE_1Y +200bps, IBOVESPA -35%, VIX +200%, SP500 -30%, OIL -50%
4. **Rate Shock 2022** (BR fiscal scare, Oct-Nov 2022): USDBRL +25%, DI_PRE_1Y +500bps, DI_PRE_5Y +400bps, NTN_B -12%

These magnitudes are sourced from the Fase 2 guide's StressTester specification and represent actual observed moves during these periods.

### Drift Threshold for Rebalancing
- **Recommended:** 5% absolute weight deviation (as specified). For a position with target weight 0.20, rebalance triggers at 0.15 or 0.25.
- **Minimum trade size:** Implement a minimum notional filter (e.g., $10,000 equivalent) to avoid micro-rebalances when threshold is just barely crossed.

### Damping Factor for Intra-Asset-Class Conflicts
- **Recommended:** 40% reduction (middle of the 30-50% range). Apply when >= 2 strategies in the same asset class have opposing directions (LONG vs. SHORT). The damped weight = original_weight * 0.60.

### Cooldown Period
- **Recommended:** 5 trading days (as specified). After L3 circuit breaker (close all), wait 5 trading days. Re-entry: 33% exposure day 1, 66% day 2, 100% day 3.

### Risk Report Format
- **Recommended layout:** Plain-text formatted report (matching existing backtest report pattern in `src/backtesting/report.py`) with sections: Portfolio Summary, VaR/CVaR, Stress Test Results, Limit Utilization, Circuit Breaker Status, Conflict Log.

## Reconciliation Notes

### Circuit Breaker Thresholds (User vs. Roadmap)
The roadmap specifies: L1 (-3%) reduce 25%, L2 (-5%) reduce 50%, L3 (-8%) close all.
The user specified: -5% reduce 50%, -10% flatten all (during discussion).
**Resolution:** Use the roadmap's 3-level specification (-3%/-5%/-8%) since the user explicitly stated "tiered escalation" and the roadmap's thresholds are more conservative and granular. The user's -5%/-10% can be interpreted as approximate, while the roadmap provides exact numbers that implement the same concept.

### Constraint Values (User vs. Roadmap)
- Roadmap says: max 3x leverage, max 25% single position, max 50% asset class concentration.
- User says: max 20% of portfolio risk budget for single position.
**Resolution:** These are complementary. Implement both: 25% maximum absolute weight AND 20% maximum risk contribution. The risk contribution limit is the binding one in practice (a position contributing 20% of risk is usually well under 25% weight).

## Open Questions

1. **How to map strategy instrument IDs to stress scenario instrument IDs?**
   - What we know: Strategies reference instruments like "DI_PRE", "USDBRL", "IBOVESPA". Stress scenarios define shocks by similar identifiers.
   - What's unclear: Is the naming exactly consistent? Do we need a mapping table?
   - Recommendation: Use instrument IDs directly from StrategyConfig.instruments. If a strategy's instrument isn't in a stress scenario's shocks dict, assume zero shock (no impact). Add a warning log when >50% of positions have no applicable shock.

2. **Portfolio returns history for VaR -- where does it come from?**
   - What we know: For backtesting, BacktestResult has equity_curve. For live, we would need daily portfolio return history.
   - What's unclear: Should VaRCalculator accept raw returns or compute them from position history?
   - Recommendation: Accept a `np.ndarray` of portfolio returns. In backtesting context, derive from equity_curve. In live context (Phase 13+), derive from daily P&L records. Keep VaRCalculator agnostic to the source.

3. **Integration with existing BacktestEngine -- should Phase 12 modules run inside backtest?**
   - What we know: BacktestEngine currently runs strategy -> portfolio -> metrics. Adding risk management to the backtest loop would let us test circuit breakers historically.
   - What's unclear: Is this in scope for Phase 12, or deferred to Phase 13 (daily pipeline)?
   - Recommendation: Build Phase 12 modules as standalone (can be called from backtest OR live). In Phase 12 tests, test them with synthetic data. Integration into BacktestEngine is a Phase 13 task.

## Sources

### Primary (HIGH confidence)
- scikit-learn 1.8.0 documentation -- [LedoitWolf estimator](https://scikit-learn.org/stable/modules/generated/sklearn.covariance.LedoitWolf.html) and [Covariance estimation guide](https://scikit-learn.org/stable/modules/covariance.html)
- SciPy v1.17.0 documentation -- [scipy.stats distributions](https://docs.scipy.org/doc/scipy/reference/stats.html), [scipy.optimize.minimize](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.minimize.html)
- Existing codebase files (verified by direct inspection):
  - `src/agents/base.py` -- AgentSignal, AgentReport, BaseAgent
  - `src/strategies/base.py` -- StrategyPosition, StrategyConfig, BaseStrategy, STRENGTH_MAP
  - `src/strategies/__init__.py` -- ALL_STRATEGIES registry
  - `src/agents/registry.py` -- AgentRegistry, EXECUTION_ORDER
  - `src/backtesting/portfolio.py` -- Portfolio (notional-based positions)
  - `src/backtesting/metrics.py` -- BacktestResult, compute_metrics
  - `src/backtesting/engine.py` -- BacktestEngine, BacktestConfig
  - `src/core/enums.py` -- AssetClass, SignalDirection, SignalStrength
  - `src/agents/cross_asset_agent.py` -- RegimeDetectionModel (regime score in [-1, +1])

### Secondary (MEDIUM confidence)
- Fase 2 guide (`docs/GUIA_COMPLETO_CLAUDE_CODE_Fase2.md`) Etapas 9-11 -- Signal Aggregation, Risk Engine, Portfolio Construction specifications. Used for stress scenario shock magnitudes and risk limit defaults.
- [QuantInsti -- CVaR/Expected Shortfall](https://blog.quantinsti.com/cvar-expected-shortfall/) -- Verified VaR/CVaR computation approach
- [PyQuant News -- VaR and CVaR Guide](https://www.pyquantnews.com/free-python-resources/risk-metrics-in-python-var-and-cvar-guide) -- Verified computation patterns
- [SSRN -- Correlated Monte Carlo Simulation using Cholesky Decomposition](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4066115) -- Verified Cholesky + copula approach

### Tertiary (LOW confidence)
- Agent weight matrix defaults are recommendations based on domain knowledge, not sourced from a specific paper. Should be validated through backtesting in Phase 13.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- numpy/scipy/sklearn are the established tools for this domain; all already installed in the project
- Architecture: HIGH -- patterns directly follow existing codebase conventions (dataclasses, structlog, pure functions, sync execution)
- Integration points: HIGH -- all upstream interfaces verified by reading actual source code (AgentSignal, StrategyPosition, Portfolio, etc.)
- Risk computations (VaR, CVaR, MC): HIGH -- standard algorithms verified against official scipy docs and multiple credible sources
- Pitfalls: MEDIUM -- based on practical experience and literature; some edge cases may only surface during implementation
- Agent weight defaults: LOW -- reasonable recommendations but unvalidated against actual data; should be tuned during backtesting

**Research date:** 2026-02-21
**Valid until:** 2026-03-21 (30 days -- stable domain, no fast-moving dependencies)

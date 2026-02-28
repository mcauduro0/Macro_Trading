"""Value-at-Risk (VaR) and Expected Shortfall (CVaR) computation engine.

Provides three VaR methodologies:
- Historical: empirical quantile of portfolio return series
- Parametric: Gaussian assumption with analytical CVaR formula (Ledoit-Wolf shrinkage)
- Monte Carlo: Student-t fitted marginals with Gaussian copula (Cholesky decomposition)

Enhanced with marginal VaR and component VaR decomposition, 756-day lookback,
and always-report-both-VaR-and-CVaR at 95% and 99% confidence levels.

All functions are pure computation -- no I/O or database access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import structlog
from scipy import stats
from sklearn.covariance import LedoitWolf

logger = structlog.get_logger(__name__)


@dataclass
class VaRResult:
    """Result of a VaR/CVaR computation."""

    var_95: float
    var_99: float
    cvar_95: float
    cvar_99: float
    method: str
    n_observations: int
    confidence_warning: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class VaRDecomposition:
    """Decomposition of portfolio VaR into per-instrument contributions.

    Attributes:
        total_var: Total portfolio VaR (negative = loss).
        total_cvar: Total portfolio CVaR (negative = loss).
        confidence: Confidence level used (e.g., 0.95).
        marginal_var: Per-instrument marginal VaR (change in portfolio VaR
            from a small increase in position weight).
        component_var: Per-instrument component VaR (weight * marginal VaR).
            Sum of all component VaRs approximately equals total VaR.
        pct_contribution: Per-instrument percentage contribution to total VaR.
    """

    total_var: float
    total_cvar: float
    confidence: float
    marginal_var: dict[str, float]
    component_var: dict[str, float]
    pct_contribution: dict[str, float]


# ---------------------------------------------------------------------------
# Pure computation functions
# ---------------------------------------------------------------------------


def compute_historical_var(
    returns: np.ndarray, confidence: float = 0.95
) -> tuple[float, float]:
    """Compute VaR and CVaR from a return series using historical simulation.

    Args:
        returns: 1-D array of portfolio daily returns.
        confidence: Confidence level (0.95 or 0.99).

    Returns:
        (var, cvar) -- both negative numbers representing losses.
        Returns (0.0, 0.0) if fewer than 10 observations.
    """
    if len(returns) < 10:
        return 0.0, 0.0

    alpha = 1.0 - confidence
    var = float(np.percentile(returns, alpha * 100.0))

    tail = returns[returns <= var]
    cvar = float(tail.mean()) if len(tail) > 0 else var

    return var, cvar


def compute_parametric_var(
    returns: np.ndarray, confidence: float = 0.95
) -> tuple[float, float]:
    """Compute VaR and CVaR assuming Gaussian returns.

    Uses the analytical formula for Expected Shortfall of a normal
    distribution:  CVaR = mu - sigma * phi(z_alpha) / (1 - confidence)

    Args:
        returns: 1-D array of portfolio daily returns.
        confidence: Confidence level (0.95 or 0.99).

    Returns:
        (var, cvar) -- both negative numbers representing losses.
    """
    if len(returns) < 2:
        return 0.0, 0.0

    mu = float(np.mean(returns))
    sigma = float(np.std(returns, ddof=1))

    if sigma < 1e-12:
        return 0.0, 0.0

    z_alpha = stats.norm.ppf(1.0 - confidence)  # negative z-score
    var = mu + sigma * z_alpha
    cvar = mu - sigma * stats.norm.pdf(z_alpha) / (1.0 - confidence)

    return float(var), float(cvar)


def compute_monte_carlo_var(
    returns_matrix: np.ndarray,
    weights: np.ndarray,
    confidence: float = 0.95,
    n_simulations: int = 10_000,
    rng: np.random.Generator | None = None,
) -> tuple[float, float]:
    """Monte Carlo VaR using Student-t marginals with Cholesky correlation.

    Steps:
        1. Fit Student-t distribution to each asset's returns.
        2. Estimate correlation matrix via Ledoit-Wolf shrinkage.
        3. Cholesky decomposition (with eigenvalue floor fallback).
        4. Generate correlated normal samples -> uniform via CDF -> t-marginals.
        5. Compute portfolio returns and extract VaR/CVaR.

    Args:
        returns_matrix: Shape (n_obs, n_assets) array of asset returns.
        weights: Shape (n_assets,) portfolio weights.
        confidence: Confidence level (0.95 or 0.99).
        n_simulations: Number of Monte Carlo draws.
        rng: Optional numpy random Generator for reproducibility.

    Returns:
        (var, cvar) -- both negative numbers representing losses.
    """
    if rng is None:
        rng = np.random.default_rng(seed=42)

    n_obs, n_assets = returns_matrix.shape

    # Step 1: Fit Student-t distribution to each asset's returns
    t_params: list[tuple[float, float, float]] = []
    for i in range(n_assets):
        asset_returns = returns_matrix[:, i]
        if n_obs < 30:
            # Fall back to normal (df=inf equivalent: very large df)
            loc = float(np.mean(asset_returns))
            scale = float(np.std(asset_returns, ddof=1))
            if scale < 1e-12:
                scale = 1e-12
            t_params.append((1e6, loc, scale))
            logger.warning(
                "monte_carlo_var_short_history",
                asset_index=i,
                n_obs=n_obs,
                fallback="normal",
            )
        else:
            try:
                df, loc, scale = stats.t.fit(asset_returns)
                if scale < 1e-12:
                    scale = 1e-12
                t_params.append((df, loc, scale))
            except Exception:
                loc = float(np.mean(asset_returns))
                scale = float(np.std(asset_returns, ddof=1))
                if scale < 1e-12:
                    scale = 1e-12
                t_params.append((1e6, loc, scale))
                logger.warning(
                    "monte_carlo_var_fit_failed",
                    asset_index=i,
                    fallback="normal",
                )

    # Step 2: Robust covariance -> correlation matrix via Ledoit-Wolf
    lw = LedoitWolf().fit(returns_matrix)
    cov = lw.covariance_
    std_diag = np.sqrt(np.diag(cov))
    std_diag[std_diag < 1e-10] = 1e-10
    corr = cov / np.outer(std_diag, std_diag)
    np.fill_diagonal(corr, 1.0)

    # Step 3: Cholesky decomposition with eigenvalue floor fallback
    try:
        chol_lower = np.linalg.cholesky(corr)
    except np.linalg.LinAlgError:
        logger.warning(
            "monte_carlo_var_eigenvalue_floor",
            message="Correlation matrix not positive-definite, applying eigenvalue floor",
        )
        eigenvalues, eigenvectors = np.linalg.eigh(corr)
        eigenvalues = np.maximum(eigenvalues, 1e-8)
        corr_fixed = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
        # Re-normalize to correlation
        d = np.sqrt(np.diag(corr_fixed))
        d[d < 1e-10] = 1e-10
        corr_fixed = corr_fixed / np.outer(d, d)
        np.fill_diagonal(corr_fixed, 1.0)
        chol_lower = np.linalg.cholesky(corr_fixed)

    # Step 4: Generate correlated normal samples
    z = rng.standard_normal((n_simulations, n_assets))
    corr_z = z @ chol_lower.T

    # Step 5: Transform to uniform via normal CDF, then to t-marginals
    uniform = stats.norm.cdf(corr_z)
    # Clamp to avoid 0/1 which cause inf in ppf
    uniform = np.clip(uniform, 1e-6, 1.0 - 1e-6)

    sim_returns = np.zeros_like(uniform)
    for i, (df, loc, scale) in enumerate(t_params):
        sim_returns[:, i] = stats.t.ppf(uniform[:, i], df, loc=loc, scale=scale)

    # Step 6: Compute portfolio returns and extract VaR/CVaR
    portfolio_returns = sim_returns @ weights

    alpha = 1.0 - confidence
    var = float(np.percentile(portfolio_returns, alpha * 100.0))
    tail = portfolio_returns[portfolio_returns <= var]
    cvar = float(tail.mean()) if len(tail) > 0 else var

    return var, cvar


# ---------------------------------------------------------------------------
# Marginal and component VaR decomposition
# ---------------------------------------------------------------------------


def compute_marginal_var(
    returns_matrix: np.ndarray,
    weights: np.ndarray,
    confidence: float = 0.95,
    method: str = "parametric",
) -> dict[int, float]:
    """Compute marginal VaR for each position.

    Marginal VaR measures the change in portfolio VaR from a small increase
    in each position's weight. Uses finite-difference approximation:
    MarginalVaR_i = (VaR(w + eps*e_i) - VaR(w - eps*e_i)) / (2 * eps)

    For parametric method, uses Ledoit-Wolf shrinkage covariance for robust
    estimation.

    Args:
        returns_matrix: Shape (n_obs, n_assets) array of asset returns.
        weights: Shape (n_assets,) portfolio weights.
        confidence: Confidence level (0.95 or 0.99).
        method: VaR method -- "parametric" or "historical".

    Returns:
        Dict mapping position index -> marginal VaR contribution.
    """
    weights = np.asarray(weights, dtype=np.float64)
    returns_matrix = np.asarray(returns_matrix, dtype=np.float64)
    n_assets = len(weights)
    epsilon = 0.001

    if method == "parametric":
        # Analytical marginal VaR using Ledoit-Wolf covariance
        lw = LedoitWolf().fit(returns_matrix)
        cov = lw.covariance_
        z_alpha = stats.norm.ppf(1.0 - confidence)  # negative

        sigma_w = cov @ weights
        port_vol = float(np.sqrt(weights @ cov @ weights))

        if port_vol < 1e-12:
            return {i: 0.0 for i in range(n_assets)}

        marginal = {}
        for i in range(n_assets):
            marginal[i] = float(sigma_w[i] / port_vol * z_alpha)
        return marginal
    else:
        # Finite-difference approximation for any method
        marginal = {}
        for i in range(n_assets):
            w_plus = weights.copy()
            w_minus = weights.copy()
            w_plus[i] += epsilon
            w_minus[i] -= epsilon

            port_ret_plus = returns_matrix @ w_plus
            port_ret_minus = returns_matrix @ w_minus

            var_plus, _ = compute_historical_var(port_ret_plus, confidence)
            var_minus, _ = compute_historical_var(port_ret_minus, confidence)

            marginal[i] = float((var_plus - var_minus) / (2.0 * epsilon))

        return marginal


def compute_component_var(
    returns_matrix: np.ndarray,
    weights: np.ndarray,
    confidence: float = 0.95,
) -> dict[int, float]:
    """Compute component VaR for each position.

    Component VaR decomposes total VaR by position:
    ComponentVaR_i = w_i * (Sigma @ w)_i / sqrt(w^T @ Sigma @ w) * z_alpha

    Sum of all component VaRs equals total parametric VaR.

    Uses Ledoit-Wolf shrinkage covariance for robust estimation.

    Args:
        returns_matrix: Shape (n_obs, n_assets) array of asset returns.
        weights: Shape (n_assets,) portfolio weights.
        confidence: Confidence level (0.95 or 0.99).

    Returns:
        Dict mapping position index -> component VaR.
    """
    weights = np.asarray(weights, dtype=np.float64)
    returns_matrix = np.asarray(returns_matrix, dtype=np.float64)
    n_assets = len(weights)

    lw = LedoitWolf().fit(returns_matrix)
    cov = lw.covariance_
    z_alpha = stats.norm.ppf(1.0 - confidence)  # negative

    sigma_w = cov @ weights
    port_vol = float(np.sqrt(weights @ cov @ weights))

    if port_vol < 1e-12:
        return {i: 0.0 for i in range(n_assets)}

    component = {}
    for i in range(n_assets):
        component[i] = float(weights[i] * sigma_w[i] / port_vol * z_alpha)

    return component


# ---------------------------------------------------------------------------
# VaRCalculator orchestrator
# ---------------------------------------------------------------------------


class VaRCalculator:
    """Orchestrator for VaR/CVaR computation across multiple methods.

    Args:
        min_historical_obs: Minimum observations for historical VaR.
            Falls back to parametric with a warning if insufficient.
        mc_simulations: Number of Monte Carlo simulations.
        lookback_days: Number of days to use for Monte Carlo fitting.
            Defaults to 756 (3 years). If returns_matrix has more rows,
            only the last ``lookback_days`` rows are used.
    """

    def __init__(
        self,
        min_historical_obs: int = 756,
        mc_simulations: int = 10_000,
        lookback_days: int = 756,
    ) -> None:
        self.min_historical_obs = min_historical_obs
        self.mc_simulations = mc_simulations
        self.lookback_days = lookback_days

    def calculate(
        self,
        portfolio_returns: np.ndarray,
        method: str = "historical",
    ) -> VaRResult:
        """Compute VaR/CVaR for a portfolio return series.

        Args:
            portfolio_returns: 1-D array of daily portfolio returns.
            method: One of "historical" or "parametric".

        Returns:
            VaRResult with VaR and CVaR at 95% and 99% confidence.
        """
        portfolio_returns = np.asarray(portfolio_returns, dtype=np.float64).ravel()
        n_obs = len(portfolio_returns)

        confidence_warning: str | None = None

        if method == "historical" and n_obs < self.min_historical_obs:
            confidence_warning = (
                f"Insufficient history ({n_obs} < {self.min_historical_obs}). "
                f"Falling back to parametric VaR."
            )
            logger.warning(
                "var_historical_fallback",
                n_obs=n_obs,
                min_required=self.min_historical_obs,
            )
            method = "parametric"

        if method == "historical":
            var_95, cvar_95 = compute_historical_var(portfolio_returns, 0.95)
            var_99, cvar_99 = compute_historical_var(portfolio_returns, 0.99)
        elif method == "parametric":
            var_95, cvar_95 = compute_parametric_var(portfolio_returns, 0.95)
            var_99, cvar_99 = compute_parametric_var(portfolio_returns, 0.99)
        else:
            raise ValueError(
                f"Unknown method '{method}'. Use 'historical', 'parametric', "
                f"or call calculate_monte_carlo() for Monte Carlo VaR."
            )

        return VaRResult(
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            method=method,
            n_observations=n_obs,
            confidence_warning=confidence_warning,
        )

    def calculate_monte_carlo(
        self,
        returns_matrix: np.ndarray,
        weights: np.ndarray,
        rng: np.random.Generator | None = None,
    ) -> VaRResult:
        """Convenience method for Monte Carlo VaR.

        Args:
            returns_matrix: Shape (n_obs, n_assets) array.
            weights: Shape (n_assets,) portfolio weights.
            rng: Optional random generator for reproducibility.

        Returns:
            VaRResult with method="monte_carlo".
        """
        returns_matrix = np.asarray(returns_matrix, dtype=np.float64)
        weights = np.asarray(weights, dtype=np.float64)

        # Trim to lookback_days if returns_matrix is longer
        if returns_matrix.shape[0] > self.lookback_days:
            returns_matrix = returns_matrix[-self.lookback_days :]
        n_obs = returns_matrix.shape[0]

        var_95, cvar_95 = compute_monte_carlo_var(
            returns_matrix, weights, 0.95, self.mc_simulations, rng=rng
        )
        var_99, cvar_99 = compute_monte_carlo_var(
            returns_matrix, weights, 0.99, self.mc_simulations, rng=rng
        )

        return VaRResult(
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            method="monte_carlo",
            n_observations=n_obs,
        )

    def calculate_all_methods(
        self,
        portfolio_returns: np.ndarray,
        returns_matrix: np.ndarray | None = None,
        weights: np.ndarray | None = None,
        rng: np.random.Generator | None = None,
    ) -> dict[str, VaRResult]:
        """Run all available VaR methods and return results keyed by method name.

        Monte Carlo is only included if returns_matrix and weights are provided.
        """
        results: dict[str, VaRResult] = {}

        results["historical"] = self.calculate(portfolio_returns, method="historical")
        results["parametric"] = self.calculate(portfolio_returns, method="parametric")

        if returns_matrix is not None and weights is not None:
            results["monte_carlo"] = self.calculate_monte_carlo(
                returns_matrix, weights, rng=rng
            )

        return results

    def decompose_var(
        self,
        returns_matrix: np.ndarray,
        weights: np.ndarray,
        instrument_names: list[str],
        confidence: float = 0.95,
    ) -> VaRDecomposition:
        """Decompose portfolio VaR into per-instrument marginal and component VaR.

        Combines ``compute_marginal_var`` (parametric method) and
        ``compute_component_var`` to produce a full decomposition that maps
        position indices to human-readable instrument names.

        Args:
            returns_matrix: Shape (n_obs, n_assets) array of asset returns.
            weights: Shape (n_assets,) portfolio weights.
            instrument_names: List of instrument names matching columns of
                returns_matrix.
            confidence: Confidence level (0.95 or 0.99).

        Returns:
            VaRDecomposition with marginal VaR, component VaR, and percentage
            contribution per instrument.
        """
        returns_matrix = np.asarray(returns_matrix, dtype=np.float64)
        weights = np.asarray(weights, dtype=np.float64)

        # Trim to lookback window
        if returns_matrix.shape[0] > self.lookback_days:
            returns_matrix = returns_matrix[-self.lookback_days :]

        # Compute portfolio returns for total VaR/CVaR
        portfolio_returns = returns_matrix @ weights
        total_var, total_cvar = compute_parametric_var(portfolio_returns, confidence)

        # Marginal and component VaR
        marginal_idx = compute_marginal_var(
            returns_matrix, weights, confidence, method="parametric"
        )
        component_idx = compute_component_var(returns_matrix, weights, confidence)

        # Map indices to instrument names
        marginal_named = {
            instrument_names[i]: marginal_idx[i] for i in range(len(instrument_names))
        }
        component_named = {
            instrument_names[i]: component_idx[i] for i in range(len(instrument_names))
        }

        # Percentage contribution: component_var_i / total_var
        pct_contribution: dict[str, float] = {}
        for name in instrument_names:
            if abs(total_var) > 1e-12:
                pct_contribution[name] = component_named[name] / total_var
            else:
                pct_contribution[name] = 0.0

        return VaRDecomposition(
            total_var=total_var,
            total_cvar=total_cvar,
            confidence=confidence,
            marginal_var=marginal_named,
            component_var=component_named,
            pct_contribution=pct_contribution,
        )

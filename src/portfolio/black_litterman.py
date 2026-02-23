"""Black-Litterman portfolio optimization model with regime-adjusted view confidence.

Combines market equilibrium returns (implied from capitalization weights) with
agent views expressed via P/Q matrices.  View confidence is regime-adjusted:
    adjusted_confidence = agent_confidence * regime_clarity

High HMM probability + confident agent = tight view distribution (small Omega).
Uncertain regime discounts even confident agents (large Omega).

References:
    - Black & Litterman (1992): "Global Portfolio Optimization"
    - Idzorek (2004): "A Step-by-Step Guide to the Black-Litterman Model"
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BlackLittermanConfig:
    """Configuration for the Black-Litterman model.

    Attributes:
        risk_aversion: Market risk aversion parameter (delta).
            Higher values imply investors are more risk-averse.
        tau: Scaling factor for uncertainty in equilibrium.
            Small values (0.01-0.10) reflect high confidence in equilibrium.
        default_view_confidence: Fallback confidence when no regime info available.
    """

    risk_aversion: float = 2.5
    tau: float = 0.05
    default_view_confidence: float = 0.5


# ---------------------------------------------------------------------------
# Agent View
# ---------------------------------------------------------------------------
@dataclass
class AgentView:
    """A single agent's directional view on an instrument.

    Attributes:
        instrument: Target instrument identifier.
        expected_return: Agent's view on the expected return.
        confidence: Agent's raw confidence in [0, 1].
        source: Agent or strategy that generated this view.
    """

    instrument: str
    expected_return: float
    confidence: float
    source: str


# ---------------------------------------------------------------------------
# Black-Litterman Model
# ---------------------------------------------------------------------------
class BlackLitterman:
    """Black-Litterman model combining equilibrium returns with agent views.

    The model follows these steps:
    1. Compute equilibrium excess returns from market capitalization weights.
    2. Build P (pick), Q (view return), and Omega (uncertainty) matrices
       from agent views with regime-adjusted confidence.
    3. Compute posterior returns via the BL closed-form formula.

    Args:
        config: BlackLittermanConfig. Uses defaults if None.
    """

    def __init__(self, config: BlackLittermanConfig | None = None) -> None:
        self.config = config or BlackLittermanConfig()

    def compute_equilibrium_returns(
        self,
        covariance: np.ndarray,
        market_weights: np.ndarray,
    ) -> np.ndarray:
        """Compute equilibrium excess returns (implied returns).

        The equilibrium returns are those consistent with the observed
        market capitalization weights under the given risk aversion:
            pi = delta * Sigma * w_mkt

        Args:
            covariance: (n x n) covariance matrix of asset returns.
            market_weights: (n,) market capitalization weights.

        Returns:
            (n,) array of implied equilibrium excess returns.
        """
        covariance = np.asarray(covariance, dtype=np.float64)
        market_weights = np.asarray(market_weights, dtype=np.float64)
        pi = self.config.risk_aversion * covariance @ market_weights
        return pi

    def build_views(
        self,
        views: list[AgentView],
        instrument_names: list[str],
        regime_clarity: float = 1.0,
        covariance: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Build P, Q, and Omega matrices from agent views.

        View confidence is regime-adjusted:
            adjusted_conf = agent_confidence * regime_clarity
        Omega diagonal elements reflect uncertainty inversely proportional
        to adjusted confidence:
            Omega_ii = 1 / (adjusted_conf + epsilon) * tau * (p_i @ Sigma @ p_i)

        If covariance is not provided, Omega uses a simpler scaling:
            Omega_ii = 1 / (adjusted_conf + epsilon) * tau

        Args:
            views: List of AgentView objects.
            instrument_names: List of instrument names matching covariance columns.
            regime_clarity: HMM regime probability clarity in [0, 1].
                1.0 = very clear regime, 0.0 = maximum uncertainty.
            covariance: Optional (n x n) covariance matrix for view uncertainty.

        Returns:
            Tuple of (P, Q, Omega):
                P: (k x n) pick matrix where k = number of views.
                Q: (k,) view expected returns.
                Omega: (k x k) diagonal view uncertainty matrix.
        """
        k = len(views)
        n = len(instrument_names)
        epsilon = 1e-6
        tau = self.config.tau

        # Map instrument names to column indices
        name_to_idx = {name: i for i, name in enumerate(instrument_names)}

        P = np.zeros((k, n), dtype=np.float64)
        Q = np.zeros(k, dtype=np.float64)
        omega_diag = np.zeros(k, dtype=np.float64)

        for i, view in enumerate(views):
            idx = name_to_idx.get(view.instrument)
            if idx is None:
                logger.warning(
                    "view_instrument_not_found",
                    instrument=view.instrument,
                    available=instrument_names,
                )
                continue

            P[i, idx] = 1.0
            Q[i] = view.expected_return

            # Regime-adjusted confidence
            adjusted_conf = view.confidence * max(regime_clarity, 0.0)

            # View uncertainty: inversely proportional to adjusted confidence
            if covariance is not None:
                p_row = P[i]
                view_var = float(p_row @ covariance @ p_row)
                omega_diag[i] = (1.0 / (adjusted_conf + epsilon)) * tau * view_var
            else:
                omega_diag[i] = (1.0 / (adjusted_conf + epsilon)) * tau

        Omega = np.diag(omega_diag)

        logger.info(
            "views_built",
            n_views=k,
            regime_clarity=round(regime_clarity, 3),
            avg_omega=round(float(omega_diag.mean()), 6) if k > 0 else 0.0,
        )

        return P, Q, Omega

    def posterior_returns(
        self,
        equilibrium: np.ndarray,
        covariance: np.ndarray,
        P: np.ndarray,
        Q: np.ndarray,
        Omega: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Compute posterior expected returns and covariance via BL formula.

        Posterior mean:
            mu_BL = inv(inv(tau*Sigma) + P^T @ Omega^-1 @ P) @
                    (inv(tau*Sigma) @ pi + P^T @ Omega^-1 @ Q)

        Posterior covariance:
            Sigma_BL = inv(inv(tau*Sigma) + P^T @ Omega^-1 @ P)

        Args:
            equilibrium: (n,) equilibrium excess returns (pi).
            covariance: (n x n) asset covariance matrix.
            P: (k x n) pick matrix.
            Q: (k,) view expected returns.
            Omega: (k x k) view uncertainty matrix.

        Returns:
            Tuple of (posterior_mu, posterior_sigma):
                posterior_mu: (n,) posterior expected returns.
                posterior_sigma: (n x n) posterior covariance.
        """
        equilibrium = np.asarray(equilibrium, dtype=np.float64)
        covariance = np.asarray(covariance, dtype=np.float64)
        P = np.asarray(P, dtype=np.float64)
        Q = np.asarray(Q, dtype=np.float64)
        Omega = np.asarray(Omega, dtype=np.float64)

        tau = self.config.tau
        tau_sigma = tau * covariance

        # inv(tau * Sigma)
        tau_sigma_inv = np.linalg.inv(tau_sigma)

        # inv(Omega)
        omega_inv = np.linalg.inv(Omega)

        # Posterior covariance: inv(inv(tau*Sigma) + P^T @ Omega^-1 @ P)
        posterior_sigma = np.linalg.inv(
            tau_sigma_inv + P.T @ omega_inv @ P
        )

        # Posterior mean
        posterior_mu = posterior_sigma @ (
            tau_sigma_inv @ equilibrium + P.T @ omega_inv @ Q
        )

        return posterior_mu, posterior_sigma

    def optimize(
        self,
        views: list[AgentView],
        covariance: np.ndarray,
        market_weights: np.ndarray,
        instrument_names: list[str],
        regime_clarity: float = 1.0,
    ) -> dict:
        """Full Black-Litterman pipeline: equilibrium -> views -> posterior.

        Args:
            views: List of agent views.
            covariance: (n x n) covariance matrix.
            market_weights: (n,) market capitalization weights.
            instrument_names: List of instrument names.
            regime_clarity: HMM regime probability clarity in [0, 1].

        Returns:
            Dict containing:
                - posterior_returns: dict of instrument -> posterior expected return.
                - posterior_covariance: (n x n) posterior covariance matrix.
                - equilibrium_returns: dict of instrument -> equilibrium return.
                - regime_clarity: float regime clarity used.
        """
        covariance = np.asarray(covariance, dtype=np.float64)
        market_weights = np.asarray(market_weights, dtype=np.float64)

        # Step 1: Equilibrium returns
        equilibrium = self.compute_equilibrium_returns(covariance, market_weights)

        if not views:
            # No views -- return equilibrium unchanged
            logger.info("no_views_provided", returning="equilibrium")
            return {
                "posterior_returns": dict(zip(instrument_names, equilibrium.tolist())),
                "posterior_covariance": covariance,
                "equilibrium_returns": dict(zip(instrument_names, equilibrium.tolist())),
                "regime_clarity": regime_clarity,
            }

        # Step 2: Build view matrices
        P, Q, Omega = self.build_views(
            views, instrument_names, regime_clarity, covariance
        )

        # Step 3: Posterior
        posterior_mu, posterior_sigma = self.posterior_returns(
            equilibrium, covariance, P, Q, Omega
        )

        equilibrium_dict = dict(zip(instrument_names, equilibrium.tolist()))
        posterior_dict = dict(zip(instrument_names, posterior_mu.tolist()))

        logger.info(
            "black_litterman_complete",
            n_instruments=len(instrument_names),
            n_views=len(views),
            regime_clarity=round(regime_clarity, 3),
        )

        return {
            "posterior_returns": posterior_dict,
            "posterior_covariance": posterior_sigma,
            "equilibrium_returns": equilibrium_dict,
            "regime_clarity": regime_clarity,
        }

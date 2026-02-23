"""Position sizing with vol-target, fractional Kelly, and risk-budget methods.

Provides three complementary sizing approaches:
- vol_target: target_vol / instrument_vol -- inverse volatility sizing
- fractional_kelly: half Kelly (0.5x) of f* = expected_return / variance
- risk_budget_size: proportional to component VaR share of total VaR

Soft position limits: limits trigger warnings but can be exceeded by 20%
when conviction is very high (> 0.8).

This module is pure computation -- no database or I/O access.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


class PositionSizer:
    """Position sizing with three methods and soft limit overrides.

    Args:
        target_vol: Target portfolio volatility for vol_target sizing.
        kelly_fraction: Fraction of full Kelly to use (default 0.5 = half Kelly).
        max_position: Maximum position size (absolute weight).
    """

    def __init__(
        self,
        target_vol: float = 0.10,
        kelly_fraction: float = 0.5,
        max_position: float = 0.25,
    ) -> None:
        self.target_vol = target_vol
        self.kelly_fraction = kelly_fraction
        self.max_position = max_position

    def vol_target_size(self, instrument_vol: float) -> float:
        """Size position using inverse volatility targeting.

        size = target_vol / instrument_vol, clamped to [0, max_position].

        Args:
            instrument_vol: Annualized volatility of the instrument.

        Returns:
            Position size in [0, max_position].
        """
        if instrument_vol <= 0:
            return 0.0

        size = self.target_vol / instrument_vol
        return min(size, self.max_position)

    def fractional_kelly_size(self, expected_return: float, return_variance: float) -> float:
        """Size position using fractional Kelly criterion.

        Full Kelly: f* = expected_return / return_variance
        Fractional: size = kelly_fraction * f*

        Clamped to [-max_position, max_position].

        Args:
            expected_return: Expected return of the instrument.
            return_variance: Variance of the instrument's returns.

        Returns:
            Signed position size in [-max_position, max_position].
        """
        if return_variance <= 0:
            return 0.0

        full_kelly = expected_return / return_variance
        size = self.kelly_fraction * full_kelly

        # Clamp to position limits
        return max(-self.max_position, min(size, self.max_position))

    def risk_budget_size(
        self,
        total_risk_budget: float,
        component_var: float,
        total_var: float,
    ) -> float:
        """Size position proportional to component VaR share.

        size = total_risk_budget * (component_var / total_var)

        Clamped to [-max_position, max_position].

        Args:
            total_risk_budget: Total risk budget (fraction of portfolio).
            component_var: Component VaR for this instrument.
            total_var: Total portfolio VaR.

        Returns:
            Signed position size in [-max_position, max_position].
        """
        if total_var == 0:
            return 0.0

        size = total_risk_budget * (component_var / total_var)
        return max(-self.max_position, min(size, self.max_position))

    def _raw_vol_target_size(self, instrument_vol: float) -> float:
        """Compute raw vol-target size without clamping."""
        if instrument_vol <= 0:
            return 0.0
        return self.target_vol / instrument_vol

    def _raw_fractional_kelly_size(
        self, expected_return: float, return_variance: float
    ) -> float:
        """Compute raw fractional Kelly size without clamping."""
        if return_variance <= 0:
            return 0.0
        return self.kelly_fraction * (expected_return / return_variance)

    def _raw_risk_budget_size(
        self, total_risk_budget: float, component_var: float, total_var: float
    ) -> float:
        """Compute raw risk-budget size without clamping."""
        if total_var == 0:
            return 0.0
        return total_risk_budget * (component_var / total_var)

    def size_portfolio(
        self,
        positions: dict[str, dict],
        method: str = "vol_target",
    ) -> dict[str, float]:
        """Apply chosen sizing method to each position in the portfolio.

        Uses raw (unclamped) sizes so that soft limit overrides can take
        effect when conviction > 0.8.

        Args:
            positions: Dict of instrument -> position data. Each value is a
                dict with keys depending on the method:
                - vol_target: {volatility: float}
                - fractional_kelly: {expected_return: float, variance: float}
                - risk_budget: {component_var: float, total_var: float,
                    total_risk_budget: float}
                Optional key for all methods:
                - conviction: float in [0, 1] for soft limit override

        Returns:
            Dict of instrument -> sized weight.
        """
        result: dict[str, float] = {}

        for instrument, data in positions.items():
            conviction = data.get("conviction", 0.0)

            if method == "vol_target":
                raw_size = self._raw_vol_target_size(data.get("volatility", 0.0))
            elif method == "fractional_kelly":
                raw_size = self._raw_fractional_kelly_size(
                    data.get("expected_return", 0.0),
                    data.get("variance", 0.0),
                )
            elif method == "risk_budget":
                raw_size = self._raw_risk_budget_size(
                    data.get("total_risk_budget", 0.0),
                    data.get("component_var", 0.0),
                    data.get("total_var", 0.0),
                )
            else:
                logger.warning("unknown_sizing_method", method=method, instrument=instrument)
                raw_size = 0.0

            # Determine effective limit based on conviction
            if conviction > 0.8:
                effective_limit = self.max_position * 1.2
                if abs(raw_size) > self.max_position:
                    logger.warning(
                        "soft_limit_override",
                        instrument=instrument,
                        conviction=round(conviction, 3),
                        raw_size=round(raw_size, 6),
                        override_limit=round(effective_limit, 4),
                    )
            else:
                effective_limit = self.max_position

            # Clamp to effective limit
            size = max(-effective_limit, min(raw_size, effective_limit))

            result[instrument] = round(size, 8)

        logger.info(
            "portfolio_sized",
            method=method,
            n_instruments=len(result),
        )

        return result

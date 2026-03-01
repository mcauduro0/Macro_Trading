"""Pre-trade risk controls for the compliance module.

Validates proposed trades against a configurable set of hard and soft limits
before they reach the execution layer. Each check returns a structured result
so that the trade workflow can surface clear accept/reject reasoning.

Checks implemented:
    1. Fat-finger guard (notional sanity bounds)
    2. Leverage cap (gross leverage vs. limit)
    3. Asset-class concentration (single asset class weight vs. limit)
    4. VaR impact (post-trade VaR must not exceed portfolio limit)
    5. Drawdown protection (block new risk when drawdown exceeds threshold)

All functions are pure computation -- no I/O or database access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PreTradeRiskConfig:
    """Configurable thresholds for pre-trade risk checks.

    Attributes:
        max_notional: Maximum allowable notional per single trade (BRL).
            Trades with notional <= 0 or > max_notional are fat-finger blocked.
        max_gross_leverage: Maximum allowable gross leverage (sum of absolute
            position weights divided by NAV). Default 4.0.
        max_asset_class_weight: Maximum concentration in any single asset class
            as a fraction of NAV. Default 0.50 (50%).
        max_post_trade_var_95: Maximum portfolio VaR (95%) after the proposed
            trade. Expressed as a positive fraction of NAV. Default 0.03 (3%).
        max_drawdown_pct: If current drawdown exceeds this threshold, all new
            risk-taking trades are blocked. Default 0.10 (10%).
    """

    max_notional: float = 50_000_000.0
    max_gross_leverage: float = 4.0
    max_asset_class_weight: float = 0.50
    max_post_trade_var_95: float = 0.03
    max_drawdown_pct: float = 0.10


# ---------------------------------------------------------------------------
# Check result
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    """Outcome of a single pre-trade risk check.

    Attributes:
        name: Human-readable check name (e.g. ``"fat_finger"``).
        passed: True if the check passed (trade is acceptable for this check).
        value: The observed value being tested.
        limit: The threshold the value was tested against.
        message: Human-readable explanation of the result.
    """

    name: str
    passed: bool
    value: float
    limit: float
    message: str


# ---------------------------------------------------------------------------
# PreTradeRiskControls
# ---------------------------------------------------------------------------


class PreTradeRiskControls:
    """Run a battery of pre-trade risk checks against a proposed trade.

    Usage::

        controls = PreTradeRiskControls()
        result = controls.validate_trade(
            notional=5_000_000.0,
            asset_class="fx",
            portfolio_state={
                "gross_leverage": 2.5,
                "asset_class_weights": {"fx": 0.30, "rates": 0.20},
                "var_95": 0.02,
                "drawdown_pct": 0.04,
            },
            proposed_weight=0.10,
            proposed_var_impact=0.005,
        )
        if not result["approved"]:
            print(result["hard_blocks"])

    Args:
        config: Optional :class:`PreTradeRiskConfig`. Uses defaults if omitted.
    """

    def __init__(self, config: PreTradeRiskConfig | None = None) -> None:
        self.config = config if config is not None else PreTradeRiskConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_trade(
        self,
        notional: float,
        asset_class: str,
        portfolio_state: dict[str, Any],
        proposed_weight: float = 0.0,
        proposed_var_impact: float = 0.0,
    ) -> dict[str, Any]:
        """Run all pre-trade risk checks and return a structured verdict.

        Args:
            notional: Trade notional in BRL.
            asset_class: Asset class of the proposed trade (e.g. ``"fx"``).
            portfolio_state: Current portfolio snapshot containing:
                - ``gross_leverage`` (float): Current gross leverage.
                - ``asset_class_weights`` (dict[str, float]): Current asset
                  class weights as fractions of NAV.
                - ``var_95`` (float): Current portfolio VaR at 95% confidence
                  as a positive fraction.
                - ``drawdown_pct`` (float): Current peak-to-trough drawdown as
                  a positive fraction.
            proposed_weight: Absolute weight the proposed trade would add to
                gross leverage.
            proposed_var_impact: Estimated marginal VaR contribution of the
                proposed trade (positive fraction).

        Returns:
            dict with keys:
                - ``approved`` (bool): True only if no hard blocks.
                - ``checks`` (list[dict]): All check results as dicts.
                - ``warnings`` (list[dict]): Checks that passed but carry a
                  warning (utilization > 80%).
                - ``hard_blocks`` (list[dict]): Checks that failed --
                  the trade must not proceed.
        """
        checks: list[CheckResult] = [
            self._check_fat_finger(notional),
            self._check_leverage(portfolio_state, proposed_weight),
            self._check_concentration(portfolio_state, asset_class, proposed_weight),
            self._check_var_impact(portfolio_state, proposed_var_impact),
            self._check_drawdown_protection(portfolio_state),
        ]

        hard_blocks = [c for c in checks if not c.passed]
        warnings = [
            c for c in checks
            if c.passed and c.limit > 0 and (c.value / c.limit) > 0.80
        ]
        approved = len(hard_blocks) == 0

        result = {
            "approved": approved,
            "checks": [_check_to_dict(c) for c in checks],
            "warnings": [_check_to_dict(c) for c in warnings],
            "hard_blocks": [_check_to_dict(c) for c in hard_blocks],
        }

        logger.info(
            "pre_trade_risk.validate",
            approved=approved,
            n_checks=len(checks),
            n_hard_blocks=len(hard_blocks),
            n_warnings=len(warnings),
            notional=notional,
            asset_class=asset_class,
        )
        return result

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_fat_finger(self, notional: float) -> CheckResult:
        """Reject trades with nonsensical notional values.

        A notional <= 0 is always invalid. A notional exceeding the
        configured maximum is treated as a likely input error ("fat finger").
        """
        limit = self.config.max_notional
        if notional <= 0:
            return CheckResult(
                name="fat_finger",
                passed=False,
                value=notional,
                limit=limit,
                message=f"Notional must be positive; got {notional:,.2f}",
            )
        if notional > limit:
            return CheckResult(
                name="fat_finger",
                passed=False,
                value=notional,
                limit=limit,
                message=(
                    f"Notional {notional:,.2f} exceeds fat-finger limit "
                    f"of {limit:,.2f}"
                ),
            )
        return CheckResult(
            name="fat_finger",
            passed=True,
            value=notional,
            limit=limit,
            message=f"Notional {notional:,.2f} within limit {limit:,.2f}",
        )

    def _check_leverage(
        self,
        portfolio_state: dict[str, Any],
        proposed_weight: float,
    ) -> CheckResult:
        """Reject if post-trade gross leverage would exceed the limit."""
        current_leverage = float(portfolio_state.get("gross_leverage", 0.0))
        post_trade_leverage = current_leverage + abs(proposed_weight)
        limit = self.config.max_gross_leverage
        passed = post_trade_leverage < limit

        return CheckResult(
            name="leverage",
            passed=passed,
            value=post_trade_leverage,
            limit=limit,
            message=(
                f"Post-trade gross leverage {post_trade_leverage:.2f} "
                f"{'within' if passed else 'exceeds'} limit {limit:.2f}"
            ),
        )

    def _check_concentration(
        self,
        portfolio_state: dict[str, Any],
        asset_class: str,
        proposed_weight: float,
    ) -> CheckResult:
        """Reject if the asset class concentration would exceed the limit."""
        ac_weights: dict[str, float] = dict(
            portfolio_state.get("asset_class_weights", {})
        )
        current_ac_weight = abs(ac_weights.get(asset_class, 0.0))
        post_trade_weight = current_ac_weight + abs(proposed_weight)
        limit = self.config.max_asset_class_weight
        passed = post_trade_weight < limit

        return CheckResult(
            name="concentration",
            passed=passed,
            value=post_trade_weight,
            limit=limit,
            message=(
                f"Post-trade {asset_class} concentration {post_trade_weight:.4f} "
                f"{'within' if passed else 'exceeds'} limit {limit:.4f}"
            ),
        )

    def _check_var_impact(
        self,
        portfolio_state: dict[str, Any],
        proposed_var_impact: float,
    ) -> CheckResult:
        """Reject if post-trade VaR (95%) would exceed the portfolio limit."""
        current_var = abs(float(portfolio_state.get("var_95", 0.0)))
        post_trade_var = current_var + abs(proposed_var_impact)
        limit = self.config.max_post_trade_var_95
        passed = post_trade_var < limit

        return CheckResult(
            name="var_impact",
            passed=passed,
            value=post_trade_var,
            limit=limit,
            message=(
                f"Post-trade VaR 95% {post_trade_var:.4f} "
                f"{'within' if passed else 'exceeds'} limit {limit:.4f}"
            ),
        )

    def _check_drawdown_protection(
        self,
        portfolio_state: dict[str, Any],
    ) -> CheckResult:
        """Block all new risk-taking trades if drawdown exceeds threshold.

        This is a hard stop: when the portfolio is experiencing a significant
        drawdown, no new positions are allowed until the drawdown recovers
        below the limit.
        """
        current_drawdown = abs(float(portfolio_state.get("drawdown_pct", 0.0)))
        limit = self.config.max_drawdown_pct
        passed = current_drawdown < limit

        return CheckResult(
            name="drawdown_protection",
            passed=passed,
            value=current_drawdown,
            limit=limit,
            message=(
                f"Current drawdown {current_drawdown:.4f} "
                f"{'within' if passed else 'exceeds'} threshold {limit:.4f}"
                + ("" if passed else " -- new trades blocked")
            ),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_to_dict(check: CheckResult) -> dict[str, Any]:
    """Convert a CheckResult dataclass to a plain dict for JSON serialization."""
    return {
        "name": check.name,
        "passed": check.passed,
        "value": check.value,
        "limit": check.limit,
        "message": check.message,
    }

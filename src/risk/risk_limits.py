"""Risk limit checking and pre-trade validation.

Provides 9 configurable risk limits with utilization reporting and
pre-trade simulation. All functions are pure computation -- no I/O
or database access.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskLimitsConfig:
    """Configuration for 9 risk limits.

    Attributes:
        max_var_95_pct: Max daily VaR at 95% confidence (positive number).
        max_var_99_pct: Max daily VaR at 99% confidence (positive number).
        max_drawdown_pct: Max peak-to-trough drawdown (positive number).
        max_leverage: Max sum of absolute weights.
        max_single_position_pct: Max single position weight (positive number).
        max_asset_class_pct: Max asset class concentration (positive number).
        max_risk_budget_pct: Max risk contribution per position (positive number).
        max_strategy_daily_loss_pct: Max daily loss per strategy (positive number).
        max_asset_class_daily_loss_pct: Max daily loss per asset class (positive number).
    """

    max_var_95_pct: float = 0.03
    max_var_99_pct: float = 0.05
    max_drawdown_pct: float = 0.10
    max_leverage: float = 3.0
    max_single_position_pct: float = 0.25
    max_asset_class_pct: float = 0.50
    max_risk_budget_pct: float = 0.20
    max_strategy_daily_loss_pct: float = 0.02
    max_asset_class_daily_loss_pct: float = 0.03


@dataclass
class LimitCheckResult:
    """Result of a single limit check.

    Attributes:
        limit_name: Human-readable limit identifier.
        limit_value: The configured threshold.
        current_value: The observed value for this metric.
        utilization_pct: current_value / limit_value * 100.
        breached: True if the limit was violated.
        details: Additional context about the check.
    """

    limit_name: str
    limit_value: float
    current_value: float
    utilization_pct: float
    breached: bool
    details: str


class RiskLimitChecker:
    """Checks portfolio state against 9 configurable risk limits.

    Args:
        config: Risk limits configuration. Defaults to RiskLimitsConfig().
    """

    def __init__(self, config: RiskLimitsConfig | None = None) -> None:
        self.config = config if config is not None else RiskLimitsConfig()

    def _check_single(
        self,
        limit_name: str,
        limit_value: float,
        current_value: float,
        details: str = "",
    ) -> LimitCheckResult:
        """Create a LimitCheckResult for one limit."""
        if abs(limit_value) < 1e-12:
            utilization_pct = 0.0
        else:
            utilization_pct = abs(current_value) / abs(limit_value) * 100.0
        breached = abs(current_value) >= abs(limit_value)
        return LimitCheckResult(
            limit_name=limit_name,
            limit_value=limit_value,
            current_value=current_value,
            utilization_pct=utilization_pct,
            breached=breached,
            details=details,
        )

    def check_all(self, portfolio_state: dict) -> list[LimitCheckResult]:
        """Check all 9 risk limits against the given portfolio state.

        Args:
            portfolio_state: Dictionary containing:
                - weights: dict[str, float] -- position weights
                - leverage: float -- sum of absolute weights
                - var_95: float -- daily VaR at 95%
                - var_99: float -- daily VaR at 99%
                - drawdown_pct: float -- current peak-to-trough drawdown
                - risk_contributions: dict[str, float] | None
                - asset_class_weights: dict[str, float] | None
                - strategy_daily_pnl: dict[str, float] | None
                - asset_class_daily_pnl: dict[str, float] | None

        Returns:
            List of LimitCheckResult for all checked limits.
        """
        results: list[LimitCheckResult] = []
        cfg = self.config

        # 1. VaR 95%
        var_95 = portfolio_state.get("var_95")
        if var_95 is not None:
            results.append(
                self._check_single(
                    "max_var_95",
                    cfg.max_var_95_pct,
                    abs(var_95),
                    f"VaR 95% = {var_95:.4f}, limit = {cfg.max_var_95_pct:.4f}",
                )
            )

        # 2. VaR 99%
        var_99 = portfolio_state.get("var_99")
        if var_99 is not None:
            results.append(
                self._check_single(
                    "max_var_99",
                    cfg.max_var_99_pct,
                    abs(var_99),
                    f"VaR 99% = {var_99:.4f}, limit = {cfg.max_var_99_pct:.4f}",
                )
            )

        # 3. Drawdown
        drawdown_pct = portfolio_state.get("drawdown_pct")
        if drawdown_pct is not None:
            results.append(
                self._check_single(
                    "max_drawdown",
                    cfg.max_drawdown_pct,
                    abs(drawdown_pct),
                    f"Drawdown = {drawdown_pct:.4f}, limit = {cfg.max_drawdown_pct:.4f}",
                )
            )

        # 4. Leverage
        leverage = portfolio_state.get("leverage")
        if leverage is not None:
            results.append(
                self._check_single(
                    "max_leverage",
                    cfg.max_leverage,
                    leverage,
                    f"Leverage = {leverage:.2f}, limit = {cfg.max_leverage:.2f}",
                )
            )

        # 5. Single position concentration
        weights = portfolio_state.get("weights")
        if weights is not None:
            max_pos_name = ""
            max_pos_weight = 0.0
            for name, w in weights.items():
                if abs(w) > max_pos_weight:
                    max_pos_weight = abs(w)
                    max_pos_name = name
            results.append(
                self._check_single(
                    "max_single_position",
                    cfg.max_single_position_pct,
                    max_pos_weight,
                    f"Largest position: {max_pos_name} = {max_pos_weight:.4f}",
                )
            )

        # 6. Asset class concentration
        asset_class_weights = portfolio_state.get("asset_class_weights")
        if asset_class_weights is not None:
            max_ac_name = ""
            max_ac_weight = 0.0
            for ac, w in asset_class_weights.items():
                if abs(w) > max_ac_weight:
                    max_ac_weight = abs(w)
                    max_ac_name = ac
            results.append(
                self._check_single(
                    "max_asset_class_concentration",
                    cfg.max_asset_class_pct,
                    max_ac_weight,
                    f"Largest asset class: {max_ac_name} = {max_ac_weight:.4f}",
                )
            )

        # 7. Risk budget
        risk_contributions = portfolio_state.get("risk_contributions")
        if risk_contributions is not None:
            max_rb_name = ""
            max_rb_value = 0.0
            for name, rc in risk_contributions.items():
                if abs(rc) > max_rb_value:
                    max_rb_value = abs(rc)
                    max_rb_name = name
            results.append(
                self._check_single(
                    "max_risk_budget",
                    cfg.max_risk_budget_pct,
                    max_rb_value,
                    f"Largest risk contributor: {max_rb_name} = {max_rb_value:.4f}",
                )
            )

        # 8. Strategy daily loss
        strategy_daily_pnl = portfolio_state.get("strategy_daily_pnl")
        if strategy_daily_pnl is not None:
            worst_strat_name = ""
            worst_strat_loss = 0.0
            for strat, pnl in strategy_daily_pnl.items():
                loss = abs(min(pnl, 0.0))
                if loss > worst_strat_loss:
                    worst_strat_loss = loss
                    worst_strat_name = strat
            results.append(
                self._check_single(
                    "max_strategy_daily_loss",
                    cfg.max_strategy_daily_loss_pct,
                    worst_strat_loss,
                    f"Worst strategy: {worst_strat_name} = -{worst_strat_loss:.4f}",
                )
            )

        # 9. Asset class daily loss
        asset_class_daily_pnl = portfolio_state.get("asset_class_daily_pnl")
        if asset_class_daily_pnl is not None:
            worst_ac_name = ""
            worst_ac_loss = 0.0
            for ac, pnl in asset_class_daily_pnl.items():
                loss = abs(min(pnl, 0.0))
                if loss > worst_ac_loss:
                    worst_ac_loss = loss
                    worst_ac_name = ac
            results.append(
                self._check_single(
                    "max_asset_class_daily_loss",
                    cfg.max_asset_class_daily_loss_pct,
                    worst_ac_loss,
                    f"Worst asset class: {worst_ac_name} = -{worst_ac_loss:.4f}",
                )
            )

        return results

    def check_pre_trade(
        self,
        current_state: dict,
        proposed_weights: dict[str, float],
    ) -> tuple[bool, list[LimitCheckResult]]:
        """Simulate a proposed trade and verify no limits breached.

        Merges proposed_weights into current_state to create a hypothetical
        post-trade state, then runs check_all on it.

        Args:
            current_state: Current portfolio state dict.
            proposed_weights: Proposed position weights to add/replace.

        Returns:
            (all_pass, results) where all_pass is True if no limits breached.
        """
        # Merge proposed weights into current weights
        current_weights = dict(current_state.get("weights", {}))
        current_weights.update(proposed_weights)

        # Recompute leverage from merged weights
        new_leverage = sum(abs(w) for w in current_weights.values())

        # Build hypothetical post-trade state
        hypothetical_state = dict(current_state)
        hypothetical_state["weights"] = current_weights
        hypothetical_state["leverage"] = new_leverage

        results = self.check_all(hypothetical_state)
        all_pass = all(not r.breached for r in results)
        return all_pass, results

    def utilization_report(
        self, results: list[LimitCheckResult]
    ) -> dict[str, float]:
        """Generate a utilization report for dashboard display.

        Args:
            results: List of LimitCheckResult from check_all().

        Returns:
            Dict of {limit_name: utilization_pct} sorted by utilization descending.
        """
        report = {r.limit_name: r.utilization_pct for r in results}
        return dict(sorted(report.items(), key=lambda x: x[1], reverse=True))

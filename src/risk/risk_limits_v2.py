"""Enhanced risk limit management with temporal loss tracking and risk budgets.

RiskLimitsManager v2 extends the existing RiskLimitChecker (Phase 12) with:
- Daily and weekly cumulative loss tracking with configurable limits
- Risk budget allocation monitoring per position and per asset class
- Available risk budget reporting for portfolio managers

All functions are pure computation -- no I/O or database access.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import date

from src.risk.risk_limits import (
    LimitCheckResult,
    RiskLimitChecker,
    RiskLimitsConfig,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RiskLimitsManagerConfig:
    """Configuration for RiskLimitsManager v2.

    Attributes:
        daily_loss_limit_pct: Max daily portfolio loss as positive fraction (2%).
        weekly_loss_limit_pct: Max weekly (rolling 5 business days) portfolio
            loss as positive fraction (5%).
        total_risk_budget: Total risk budget (1.0 = 100%).
        risk_budget_per_position: Max risk contribution per single position (20%).
        risk_budget_per_asset_class: Max risk contribution per asset class (40%).
        limits_config: Embedded RiskLimitsConfig for the underlying RiskLimitChecker.
    """

    daily_loss_limit_pct: float = 0.02
    weekly_loss_limit_pct: float = 0.05
    total_risk_budget: float = 1.0
    risk_budget_per_position: float = 0.20
    risk_budget_per_asset_class: float = 0.40
    limits_config: RiskLimitsConfig = field(default_factory=RiskLimitsConfig)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class LossRecord:
    """Record of daily P&L observation.

    Attributes:
        date: Calendar date of the observation.
        daily_pnl: Daily P&L as a fraction of portfolio (negative = loss).
        cumulative_weekly_pnl: Rolling 5-business-day cumulative P&L.
        strategies_pnl: Per-strategy daily P&L (if provided).
        breach_daily: True if |daily_pnl| exceeded the daily loss limit.
        breach_weekly: True if |cumulative_weekly_pnl| exceeded the weekly limit.
    """

    date: date
    daily_pnl: float
    cumulative_weekly_pnl: float
    strategies_pnl: dict[str, float]
    breach_daily: bool
    breach_weekly: bool


@dataclass
class RiskBudgetReport:
    """Risk budget allocation report.

    Attributes:
        total_risk_budget: Total risk budget (1.0 = 100%).
        allocated_risk: Sum of position risk contributions.
        available_risk_budget: total - allocated.
        utilization_pct: allocated / total * 100.
        position_budgets: Per-position budget details.
        asset_class_budgets: Per-asset-class budget details.
        can_add_risk: True if available_risk_budget > 0.05 (5% headroom).
    """

    total_risk_budget: float
    allocated_risk: float
    available_risk_budget: float
    utilization_pct: float
    position_budgets: dict[str, dict]
    asset_class_budgets: dict[str, dict]
    can_add_risk: bool


# ---------------------------------------------------------------------------
# RiskLimitsManager v2
# ---------------------------------------------------------------------------


class RiskLimitsManager:
    """Enhanced risk limits manager with temporal loss tracking and risk budgets.

    Extends the existing RiskLimitChecker with:
    - Daily and weekly cumulative loss tracking
    - Risk budget allocation monitoring per position and asset class
    - Convenience check_all_v2 combining limits, losses, and budgets

    Args:
        config: Manager configuration. Defaults to RiskLimitsManagerConfig().
    """

    MAX_HISTORY = 30

    def __init__(self, config: RiskLimitsManagerConfig | None = None) -> None:
        self.config = config if config is not None else RiskLimitsManagerConfig()
        self._loss_history: deque[LossRecord] = deque(maxlen=self.MAX_HISTORY)
        self._checker = RiskLimitChecker(self.config.limits_config)
        self._last_allocated_risk: float = 0.0

    def record_daily_pnl(
        self,
        obs_date: date,
        daily_pnl: float,
        strategies_pnl: dict[str, float] | None = None,
    ) -> LossRecord:
        """Record a daily P&L observation and check against limits.

        Args:
            obs_date: Calendar date of the observation.
            daily_pnl: Daily P&L as a fraction of portfolio (negative = loss).
            strategies_pnl: Per-strategy daily P&L breakdown (optional).

        Returns:
            LossRecord with breach flags.
        """
        strategies_pnl = strategies_pnl if strategies_pnl is not None else {}

        # Compute rolling 5-business-day cumulative P&L
        # Include current day + last 4 records (total of 5 most recent days)
        recent_pnls = [r.daily_pnl for r in self._loss_history]
        # Take the last 4 from history + current day
        window = recent_pnls[-4:] + [daily_pnl]
        cumulative_weekly_pnl = sum(window)

        # Check breaches (compare absolute values against positive limits)
        breach_daily = abs(daily_pnl) > self.config.daily_loss_limit_pct
        breach_weekly = abs(cumulative_weekly_pnl) > self.config.weekly_loss_limit_pct

        record = LossRecord(
            date=obs_date,
            daily_pnl=daily_pnl,
            cumulative_weekly_pnl=cumulative_weekly_pnl,
            strategies_pnl=strategies_pnl,
            breach_daily=breach_daily,
            breach_weekly=breach_weekly,
        )

        self._loss_history.append(record)
        return record

    def get_loss_history(self, n_days: int = 5) -> list[LossRecord]:
        """Return the last n_days of loss records.

        Args:
            n_days: Number of recent records to return.

        Returns:
            List of LossRecord, most recent last.
        """
        records = list(self._loss_history)
        return records[-n_days:] if len(records) > n_days else records

    def compute_risk_budget(
        self,
        risk_contributions: dict[str, float],
        asset_class_map: dict[str, str],
    ) -> RiskBudgetReport:
        """Compute risk budget allocation from position risk contributions.

        Args:
            risk_contributions: Per-position risk contribution as fraction of
                total portfolio risk. E.g., ``{"USDBRL": 0.25, "DI_PRE": 0.35}``.
            asset_class_map: Mapping of position name -> asset class name.
                E.g., ``{"USDBRL": "FX", "DI_PRE": "FIXED_INCOME"}``.

        Returns:
            RiskBudgetReport with per-position and per-asset-class budgets.
        """
        total_budget = self.config.total_risk_budget
        pos_limit = self.config.risk_budget_per_position
        ac_limit = self.config.risk_budget_per_asset_class

        allocated_risk = sum(abs(v) for v in risk_contributions.values())
        available = total_budget - allocated_risk
        utilization_pct = (allocated_risk / total_budget * 100.0) if total_budget > 1e-12 else 0.0

        # Per-position budgets
        position_budgets: dict[str, dict] = {}
        for pos_name, contrib in risk_contributions.items():
            abs_contrib = abs(contrib)
            pos_util = (abs_contrib / pos_limit * 100.0) if pos_limit > 1e-12 else 0.0
            position_budgets[pos_name] = {
                "allocated": abs_contrib,
                "limit": pos_limit,
                "utilization_pct": round(pos_util, 2),
                "breached": abs_contrib > pos_limit,
            }

        # Aggregate by asset class
        ac_totals: dict[str, float] = {}
        for pos_name, contrib in risk_contributions.items():
            ac = asset_class_map.get(pos_name, "UNKNOWN")
            ac_totals[ac] = ac_totals.get(ac, 0.0) + abs(contrib)

        asset_class_budgets: dict[str, dict] = {}
        for ac_name, ac_total in ac_totals.items():
            ac_util = (ac_total / ac_limit * 100.0) if ac_limit > 1e-12 else 0.0
            asset_class_budgets[ac_name] = {
                "allocated": ac_total,
                "limit": ac_limit,
                "utilization_pct": round(ac_util, 2),
                "breached": ac_total > ac_limit,
            }

        can_add_risk = available > 0.05

        # Store for available_risk_budget accessor
        self._last_allocated_risk = allocated_risk

        return RiskBudgetReport(
            total_risk_budget=total_budget,
            allocated_risk=allocated_risk,
            available_risk_budget=available,
            utilization_pct=round(utilization_pct, 2),
            position_budgets=position_budgets,
            asset_class_budgets=asset_class_budgets,
            can_add_risk=can_add_risk,
        )

    def check_all_v2(self, portfolio_state: dict) -> dict:
        """Combined check: limits + daily/weekly loss + risk budget.

        Calls the underlying RiskLimitChecker.check_all() and augments with
        temporal loss status and risk budget information.

        Args:
            portfolio_state: Dictionary as expected by RiskLimitChecker.check_all().
                Optionally includes:
                - ``risk_contributions``: dict[str, float] for budget computation
                - ``asset_class_map``: dict[str, str] for budget aggregation

        Returns:
            Dict with keys:
            - ``limit_results``: list[LimitCheckResult] from underlying checker
            - ``loss_status``: Most recent LossRecord or None
            - ``risk_budget``: RiskBudgetReport or None
            - ``overall_status``: "OK", "WARNING", or "BREACHED"
        """
        # Underlying limit checks
        limit_results = self._checker.check_all(portfolio_state)

        # Loss status from history
        loss_status: LossRecord | None = None
        if self._loss_history:
            loss_status = self._loss_history[-1]

        # Risk budget (if contributions provided)
        risk_budget: RiskBudgetReport | None = None
        risk_contributions = portfolio_state.get("risk_contributions")
        asset_class_map = portfolio_state.get("asset_class_map")
        if risk_contributions and asset_class_map:
            risk_budget = self.compute_risk_budget(risk_contributions, asset_class_map)

        # Determine overall status
        any_limit_breach = any(r.breached for r in limit_results)
        any_loss_breach = False
        if loss_status is not None:
            any_loss_breach = loss_status.breach_daily or loss_status.breach_weekly
        any_budget_breach = False
        if risk_budget is not None:
            any_budget_breach = any(
                p["breached"] for p in risk_budget.position_budgets.values()
            ) or any(
                a["breached"] for a in risk_budget.asset_class_budgets.values()
            )

        if any_limit_breach or any_loss_breach or any_budget_breach:
            overall_status = "BREACHED"
        elif loss_status is not None and (
            abs(loss_status.daily_pnl) > self.config.daily_loss_limit_pct * 0.8
            or abs(loss_status.cumulative_weekly_pnl) > self.config.weekly_loss_limit_pct * 0.8
        ):
            overall_status = "WARNING"
        elif risk_budget is not None and risk_budget.utilization_pct > 80.0:
            overall_status = "WARNING"
        else:
            overall_status = "OK"

        return {
            "limit_results": limit_results,
            "loss_status": loss_status,
            "risk_budget": risk_budget,
            "overall_status": overall_status,
        }

    def available_risk_budget(self) -> float:
        """Quick accessor returning total risk budget minus last known allocated risk.

        Returns:
            Available risk budget as a fraction (e.g., 0.4 = 40% remaining).
        """
        return self.config.total_risk_budget - self._last_allocated_risk

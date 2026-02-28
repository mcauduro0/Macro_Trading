"""Drawdown management with 3-level circuit breakers.

Implements a state machine with 6 states: NORMAL, L1_TRIGGERED,
L2_TRIGGERED, L3_TRIGGERED, COOLDOWN, RECOVERING. Includes per-strategy
and per-asset-class loss trackers as independent circuit breaker layers.

AlertDispatcher provides configurable webhook/email delivery of circuit
breaker events with graceful failure handling.

All functions are pure computation -- no I/O or database access (except
optional webhook POST from AlertDispatcher).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Enums and data classes
# ---------------------------------------------------------------------------


class CircuitBreakerState(str, Enum):
    """States for the portfolio drawdown circuit breaker."""

    NORMAL = "NORMAL"
    L1_TRIGGERED = "L1_TRIGGERED"
    L2_TRIGGERED = "L2_TRIGGERED"
    L3_TRIGGERED = "L3_TRIGGERED"
    COOLDOWN = "COOLDOWN"
    RECOVERING = "RECOVERING"


@dataclass
class CircuitBreakerEvent:
    """Record of a circuit breaker state transition.

    Full context is captured for post-mortem analysis (locked decision:
    full context logging on every state transition).
    """

    timestamp: datetime
    state_from: CircuitBreakerState
    state_to: CircuitBreakerState
    drawdown_pct: float
    action: str
    positions_snapshot: dict[str, float]
    pnl_at_trigger: float
    signals_at_trigger: dict


@dataclass(frozen=True)
class CircuitBreakerConfig:
    """Configuration for 3-level circuit breakers with cooldown and recovery.

    All drawdown values are positive fractions (e.g., 0.03 = 3%).
    """

    l1_drawdown_pct: float = 0.03  # L1 threshold: -3%
    l1_reduction: float = 0.25  # Reduce by 25%
    l2_drawdown_pct: float = 0.05  # L2 threshold: -5%
    l2_reduction: float = 0.50  # Reduce by 50%
    l3_drawdown_pct: float = 0.08  # L3 threshold: -8%
    l3_reduction: float = 1.00  # Close all (100% reduction)
    cooldown_days: int = 5  # Days before re-entry allowed
    recovery_days: int = 3  # Days to ramp back to full exposure
    recovery_threshold_pct: float = 0.03  # Drawdown must recover above -3%


# ---------------------------------------------------------------------------
# AlertDispatcher
# ---------------------------------------------------------------------------


class AlertDispatcher:
    """Dispatches circuit breaker events via structlog and optional webhook.

    Always logs events at WARNING level. If webhook_url is configured and
    enabled, sends JSON POST. Never raises on HTTP failure -- alerting
    must not crash the trading loop.

    Args:
        webhook_url: Optional HTTP endpoint for alert delivery.
        enabled: Toggle to disable alerting in tests or dry-run.
    """

    def __init__(
        self,
        webhook_url: str | None = None,
        enabled: bool = True,
    ) -> None:
        self.webhook_url = webhook_url
        self.enabled = enabled
        self._logger = structlog.get_logger("alert_dispatcher")

    def dispatch(self, event: CircuitBreakerEvent) -> bool:
        """Dispatch a circuit breaker event.

        Args:
            event: The circuit breaker event to dispatch.

        Returns:
            True if dispatch succeeded (or webhook not configured),
            False if HTTP POST failed.
        """
        # Always log the event
        self._logger.warning(
            "circuit_breaker_event",
            state_from=event.state_from.value,
            state_to=event.state_to.value,
            drawdown_pct=event.drawdown_pct,
            action=event.action,
            timestamp=event.timestamp.isoformat(),
        )

        if not self.enabled:
            return True

        if self.webhook_url is None:
            return True

        # POST to webhook
        payload = {
            "event_type": "circuit_breaker",
            "state_from": event.state_from.value,
            "state_to": event.state_to.value,
            "drawdown_pct": event.drawdown_pct,
            "action": event.action,
            "timestamp": event.timestamp.isoformat(),
            "positions_snapshot": event.positions_snapshot,
            "pnl_at_trigger": event.pnl_at_trigger,
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urlopen(req, timeout=5)  # noqa: S310
            return True
        except (URLError, HTTPError, OSError) as exc:
            self._logger.error(
                "alert_dispatch_failed",
                webhook_url=self.webhook_url,
                error=str(exc),
            )
            return False


# ---------------------------------------------------------------------------
# DrawdownManager
# ---------------------------------------------------------------------------


class DrawdownManager:
    """Portfolio drawdown manager with 3-level circuit breakers.

    State machine: NORMAL -> L1 -> L2 -> L3 -> COOLDOWN -> RECOVERING -> NORMAL

    Args:
        config: Circuit breaker configuration. Defaults to CircuitBreakerConfig().
        alert_dispatcher: Optional AlertDispatcher for event delivery.
    """

    def __init__(
        self,
        config: CircuitBreakerConfig | None = None,
        alert_dispatcher: AlertDispatcher | None = None,
    ) -> None:
        self.config = config or CircuitBreakerConfig()
        self.alert_dispatcher = alert_dispatcher
        self.state: CircuitBreakerState = CircuitBreakerState.NORMAL
        self.high_water_mark: float = 0.0
        self.cooldown_counter: int = 0
        self.recovery_day: int = 0
        self.event_log: list[CircuitBreakerEvent] = []
        self._hwm_initialized: bool = False
        self._current_drawdown: float = 0.0

    def update(
        self,
        current_equity: float,
        positions: dict[str, float] | None = None,
        pnl: float = 0.0,
        signals: dict | None = None,
    ) -> float:
        """Update drawdown state and return position scale factor.

        Args:
            current_equity: Current portfolio equity value.
            positions: Current positions (for event logging).
            pnl: Current P&L (for event logging).
            signals: Current signal state (for event logging).

        Returns:
            Scale factor: 1.0 (NORMAL), 0.75 (L1), 0.50 (L2), 0.0 (L3/COOLDOWN),
            or gradual ramp (RECOVERING).
        """
        positions = positions or {}
        signals = signals or {}

        # Initialize HWM on first call
        if not self._hwm_initialized:
            self.high_water_mark = current_equity
            self._hwm_initialized = True

        # Update HWM (only goes up)
        if current_equity > self.high_water_mark:
            self.high_water_mark = current_equity

        # Compute current drawdown (positive number representing loss)
        if self.high_water_mark > 0:
            self._current_drawdown = (
                self.high_water_mark - current_equity
            ) / self.high_water_mark
        else:
            self._current_drawdown = 0.0

        dd = self._current_drawdown
        cfg = self.config

        # State machine transitions
        old_state = self.state

        if self.state == CircuitBreakerState.NORMAL:
            if dd >= cfg.l1_drawdown_pct:
                self.state = CircuitBreakerState.L1_TRIGGERED
                self._log_event(
                    old_state,
                    self.state,
                    dd,
                    "reduce_25%",
                    positions,
                    pnl,
                    signals,
                )

        elif self.state == CircuitBreakerState.L1_TRIGGERED:
            if dd >= cfg.l2_drawdown_pct:
                self.state = CircuitBreakerState.L2_TRIGGERED
                self._log_event(
                    old_state,
                    self.state,
                    dd,
                    "reduce_50%",
                    positions,
                    pnl,
                    signals,
                )
            elif dd < cfg.l1_drawdown_pct * 0.5:
                self.state = CircuitBreakerState.NORMAL
                self._log_event(
                    old_state,
                    self.state,
                    dd,
                    "recovery_to_normal",
                    positions,
                    pnl,
                    signals,
                )

        elif self.state == CircuitBreakerState.L2_TRIGGERED:
            if dd >= cfg.l3_drawdown_pct:
                self.state = CircuitBreakerState.L3_TRIGGERED
                self._log_event(
                    old_state,
                    self.state,
                    dd,
                    "close_all",
                    positions,
                    pnl,
                    signals,
                )
                # L3_TRIGGERED immediately transitions to COOLDOWN
                l3_state = self.state
                self.cooldown_counter = cfg.cooldown_days
                self.state = CircuitBreakerState.COOLDOWN
                self._log_event(
                    l3_state,
                    self.state,
                    dd,
                    "cooldown_start",
                    positions,
                    pnl,
                    signals,
                )
            elif dd < cfg.l1_drawdown_pct:
                self.state = CircuitBreakerState.L1_TRIGGERED
                self._log_event(
                    old_state,
                    self.state,
                    dd,
                    "de_escalation_to_l1",
                    positions,
                    pnl,
                    signals,
                )

        elif self.state == CircuitBreakerState.L3_TRIGGERED:
            # Safety: if we somehow end up in L3 (shouldn't happen since L2
            # immediately chains to COOLDOWN), still transition to COOLDOWN
            self.cooldown_counter = cfg.cooldown_days
            self.state = CircuitBreakerState.COOLDOWN
            self._log_event(
                old_state,
                self.state,
                dd,
                "cooldown_start",
                positions,
                pnl,
                signals,
            )

        elif self.state == CircuitBreakerState.COOLDOWN:
            self.cooldown_counter -= 1
            if self.cooldown_counter <= 0 and dd < cfg.recovery_threshold_pct:
                self.recovery_day = 0
                self.state = CircuitBreakerState.RECOVERING
                self._log_event(
                    old_state,
                    self.state,
                    dd,
                    "recovery_start",
                    positions,
                    pnl,
                    signals,
                )

        elif self.state == CircuitBreakerState.RECOVERING:
            self.recovery_day += 1
            if self.recovery_day >= cfg.recovery_days:
                self.state = CircuitBreakerState.NORMAL
                # Reset HWM to current equity on full recovery
                self.high_water_mark = current_equity
                self._log_event(
                    old_state,
                    self.state,
                    dd,
                    "full_recovery",
                    positions,
                    pnl,
                    signals,
                )

        # Return scale factor based on current state
        return self._scale_factor()

    def current_drawdown(self) -> float:
        """Return current drawdown percentage (positive = loss)."""
        return self._current_drawdown

    def get_events(self) -> list[CircuitBreakerEvent]:
        """Return a copy of the event log."""
        return list(self.event_log)

    def reset(self) -> None:
        """Reset to NORMAL state with cleared event log. For testing."""
        self.state = CircuitBreakerState.NORMAL
        self.high_water_mark = 0.0
        self.cooldown_counter = 0
        self.recovery_day = 0
        self.event_log = []
        self._hwm_initialized = False
        self._current_drawdown = 0.0

    def _scale_factor(self) -> float:
        """Return position scale factor for the current state."""
        cfg = self.config
        if self.state == CircuitBreakerState.NORMAL:
            return 1.0
        if self.state == CircuitBreakerState.L1_TRIGGERED:
            return 1.0 - cfg.l1_reduction  # 0.75
        if self.state == CircuitBreakerState.L2_TRIGGERED:
            return 1.0 - cfg.l2_reduction  # 0.50
        if self.state in (
            CircuitBreakerState.L3_TRIGGERED,
            CircuitBreakerState.COOLDOWN,
        ):
            return 0.0
        if self.state == CircuitBreakerState.RECOVERING:
            # Gradual ramp: recovery_day 1->0%, 2->50%, 3->100% (for 3-day recovery)
            # Uses (recovery_day - 1) so first day in recovery starts at 0% exposure
            if self.config.recovery_days > 1:
                return max(
                    0.0, (self.recovery_day - 1) / (self.config.recovery_days - 1)
                )
            return 1.0
        return 1.0

    def _log_event(
        self,
        state_from: CircuitBreakerState,
        state_to: CircuitBreakerState,
        drawdown_pct: float,
        action: str,
        positions: dict[str, float],
        pnl: float,
        signals: dict,
    ) -> None:
        """Record a state transition event and dispatch alert if configured."""
        event = CircuitBreakerEvent(
            timestamp=datetime.utcnow(),
            state_from=state_from,
            state_to=state_to,
            drawdown_pct=drawdown_pct,
            action=action,
            positions_snapshot=dict(positions),
            pnl_at_trigger=pnl,
            signals_at_trigger=dict(signals),
        )
        self.event_log.append(event)

        logger.warning(
            "circuit_breaker_transition",
            state_from=state_from.value,
            state_to=state_to.value,
            drawdown_pct=drawdown_pct,
            action=action,
        )

        if self.alert_dispatcher is not None:
            self.alert_dispatcher.dispatch(event)


# ---------------------------------------------------------------------------
# Per-strategy and per-asset-class circuit breakers
# ---------------------------------------------------------------------------


class StrategyLossTracker:
    """Tracks daily P&L per strategy and detects limit breaches.

    Fires independently of the portfolio-level DrawdownManager.

    Args:
        max_daily_loss_pct: Maximum daily loss per strategy (positive fraction).
        alert_dispatcher: Optional AlertDispatcher for breach events.
    """

    def __init__(
        self,
        max_daily_loss_pct: float = 0.02,
        alert_dispatcher: AlertDispatcher | None = None,
    ) -> None:
        self.max_daily_loss_pct = max_daily_loss_pct
        self.alert_dispatcher = alert_dispatcher
        self.daily_pnl: dict[str, float] = {}
        self.event_log: list[CircuitBreakerEvent] = []

    def update(self, strategy_id: str, daily_pnl_pct: float) -> bool:
        """Update daily P&L for a strategy and check for breach.

        Args:
            strategy_id: Identifier for the strategy.
            daily_pnl_pct: Daily P&L as a fraction (negative = loss).

        Returns:
            True if the strategy daily loss limit was breached.
        """
        self.daily_pnl[strategy_id] = daily_pnl_pct
        loss = abs(min(daily_pnl_pct, 0.0))
        breached = loss > self.max_daily_loss_pct

        if breached:
            event = CircuitBreakerEvent(
                timestamp=datetime.utcnow(),
                state_from=CircuitBreakerState.NORMAL,
                state_to=CircuitBreakerState.L1_TRIGGERED,
                drawdown_pct=loss,
                action=f"strategy_loss_breach:{strategy_id}",
                positions_snapshot={strategy_id: daily_pnl_pct},
                pnl_at_trigger=daily_pnl_pct,
                signals_at_trigger={"strategy_id": strategy_id},
            )
            self.event_log.append(event)
            logger.warning(
                "strategy_loss_breach",
                strategy_id=strategy_id,
                daily_loss_pct=loss,
                limit=self.max_daily_loss_pct,
            )
            if self.alert_dispatcher is not None:
                self.alert_dispatcher.dispatch(event)

        return breached

    def reset(self) -> None:
        """Reset daily P&L tracking. Called at start of each trading day."""
        self.daily_pnl.clear()


class AssetClassLossTracker:
    """Tracks daily P&L per asset class and detects limit breaches.

    Fires independently of the portfolio-level DrawdownManager.

    Args:
        max_daily_loss_pct: Maximum daily loss per asset class (positive fraction).
        alert_dispatcher: Optional AlertDispatcher for breach events.
    """

    def __init__(
        self,
        max_daily_loss_pct: float = 0.03,
        alert_dispatcher: AlertDispatcher | None = None,
    ) -> None:
        self.max_daily_loss_pct = max_daily_loss_pct
        self.alert_dispatcher = alert_dispatcher
        self.daily_pnl: dict[str, float] = {}
        self.event_log: list[CircuitBreakerEvent] = []

    def update(self, asset_class: str, daily_pnl_pct: float) -> bool:
        """Update daily P&L for an asset class and check for breach.

        Args:
            asset_class: Asset class identifier (e.g., "FIXED_INCOME").
            daily_pnl_pct: Daily P&L as a fraction (negative = loss).

        Returns:
            True if the asset class daily loss limit was breached.
        """
        self.daily_pnl[asset_class] = daily_pnl_pct
        loss = abs(min(daily_pnl_pct, 0.0))
        breached = loss > self.max_daily_loss_pct

        if breached:
            event = CircuitBreakerEvent(
                timestamp=datetime.utcnow(),
                state_from=CircuitBreakerState.NORMAL,
                state_to=CircuitBreakerState.L1_TRIGGERED,
                drawdown_pct=loss,
                action=f"asset_class_loss_breach:{asset_class}",
                positions_snapshot={asset_class: daily_pnl_pct},
                pnl_at_trigger=daily_pnl_pct,
                signals_at_trigger={"asset_class": asset_class},
            )
            self.event_log.append(event)
            logger.warning(
                "asset_class_loss_breach",
                asset_class=asset_class,
                daily_loss_pct=loss,
                limit=self.max_daily_loss_pct,
            )
            if self.alert_dispatcher is not None:
                self.alert_dispatcher.dispatch(event)

        return breached

    def reset(self) -> None:
        """Reset daily P&L tracking. Called at start of each trading day."""
        self.daily_pnl.clear()

"""Unit tests for DrawdownManager -- core TESTV2-04 coverage.

Tests all 6 circuit breaker states, transitions, cooldown, recovery,
event logging with full context, alert dispatching (structlog + webhook),
and per-strategy/per-asset-class loss trackers.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

from src.risk.drawdown_manager import (
    AlertDispatcher,
    AssetClassLossTracker,
    CircuitBreakerEvent,
    CircuitBreakerState,
    DrawdownManager,
    StrategyLossTracker,
)


class TestDrawdownManager:
    """Tests for DrawdownManager state machine."""

    def test_normal_no_drawdown(self) -> None:
        """Equity at or above HWM should stay NORMAL with scale 1.0."""
        dm = DrawdownManager()
        scale = dm.update(100_000.0)
        assert dm.state == CircuitBreakerState.NORMAL
        assert scale == 1.0
        # Equity rises
        scale = dm.update(101_000.0)
        assert dm.state == CircuitBreakerState.NORMAL
        assert scale == 1.0

    def test_l1_trigger(self) -> None:
        """3% drop from HWM should trigger L1 with scale 0.75."""
        dm = DrawdownManager()
        dm.update(100_000.0)  # Set HWM
        scale = dm.update(97_000.0)  # 3% drop
        assert dm.state == CircuitBreakerState.L1_TRIGGERED
        assert scale == pytest.approx(0.75)

    def test_l2_trigger(self) -> None:
        """5% drop from HWM should trigger L2 with scale 0.50."""
        dm = DrawdownManager()
        dm.update(100_000.0)
        dm.update(97_000.0)  # L1
        scale = dm.update(95_000.0)  # 5% drop -> L2
        assert dm.state == CircuitBreakerState.L2_TRIGGERED
        assert scale == pytest.approx(0.50)

    def test_l3_trigger(self) -> None:
        """8% drop from HWM should trigger L3 then immediately COOLDOWN."""
        dm = DrawdownManager()
        dm.update(100_000.0)
        dm.update(97_000.0)  # L1
        dm.update(95_000.0)  # L2
        scale = dm.update(92_000.0)  # 8% drop -> L3 -> COOLDOWN
        assert dm.state == CircuitBreakerState.COOLDOWN
        assert scale == 0.0

    def test_cooldown_duration(self) -> None:
        """Cooldown should last 5 update calls before allowing recovery."""
        dm = DrawdownManager()
        dm.update(100_000.0)
        dm.update(97_000.0)  # L1
        dm.update(95_000.0)  # L2
        dm.update(92_000.0)  # L3 -> COOLDOWN

        # 5 days of cooldown with equity recovered
        for i in range(4):
            scale = dm.update(99_000.0)  # drawdown well below recovery threshold
            assert dm.state == CircuitBreakerState.COOLDOWN, f"Day {i+1}"
            assert scale == 0.0

        # 5th cooldown day -> should transition to RECOVERING (drawdown < 3%)
        scale = dm.update(99_000.0)
        assert dm.state == CircuitBreakerState.RECOVERING

    def test_cooldown_no_exit_if_drawdown_high(self) -> None:
        """Cooldown should not exit if drawdown is still above recovery threshold."""
        dm = DrawdownManager()
        dm.update(100_000.0)
        dm.update(97_000.0)  # L1
        dm.update(95_000.0)  # L2
        dm.update(92_000.0)  # L3 -> COOLDOWN

        # 5 days of cooldown but equity still low
        for _ in range(5):
            scale = dm.update(94_000.0)  # 6% drawdown > 3% threshold

        # Should still be in COOLDOWN
        assert dm.state == CircuitBreakerState.COOLDOWN
        assert scale == 0.0

    def test_recovery_gradual_ramp(self) -> None:
        """Recovery ramps via (day-1)/(days-1): 0.0, 0.5, 1.0 for 3-day.

        The scale formula is max(0, (recovery_day - 1) / (recovery_days - 1)).
        Day 1 starts at 0% exposure (conservative re-entry), Day 2 at 50%,
        and Day 3 reaches full exposure and transitions to NORMAL.
        """
        dm = DrawdownManager()
        dm.update(100_000.0)
        dm.update(97_000.0)  # L1
        dm.update(95_000.0)  # L2
        dm.update(92_000.0)  # L3 -> COOLDOWN

        # Burn through cooldown
        for _ in range(5):
            dm.update(99_000.0)

        assert dm.state == CircuitBreakerState.RECOVERING

        # Day 1 of recovery: (1-1)/(3-1) = 0.0
        scale = dm.update(99_500.0)
        assert dm.state == CircuitBreakerState.RECOVERING
        assert scale == pytest.approx(0.0, abs=0.01)

        # Day 2 of recovery: (2-1)/(3-1) = 0.5
        scale = dm.update(99_600.0)
        assert dm.state == CircuitBreakerState.RECOVERING
        assert scale == pytest.approx(0.5, abs=0.01)

        # Day 3 of recovery -> NORMAL: scale = 1.0
        scale = dm.update(99_700.0)
        assert dm.state == CircuitBreakerState.NORMAL
        assert scale == 1.0

    def test_recovery_to_normal(self) -> None:
        """After 3 recovery days should return to NORMAL with HWM reset."""
        dm = DrawdownManager()
        dm.update(100_000.0)
        dm.update(97_000.0)  # L1
        dm.update(95_000.0)  # L2
        dm.update(92_000.0)  # L3 -> COOLDOWN

        for _ in range(5):
            dm.update(99_000.0)

        # 3 recovery days
        dm.update(99_500.0)
        dm.update(99_600.0)
        dm.update(99_700.0)

        assert dm.state == CircuitBreakerState.NORMAL
        # HWM should be reset to last equity value (99_700)
        assert dm.high_water_mark == pytest.approx(99_700.0)

    def test_event_logging(self) -> None:
        """Each state transition should produce a CircuitBreakerEvent."""
        dm = DrawdownManager()
        dm.update(100_000.0)
        dm.update(97_000.0)  # L1 (1 event)
        dm.update(95_000.0)  # L2 (1 event)

        events = dm.get_events()
        assert len(events) == 2
        assert events[0].state_from == CircuitBreakerState.NORMAL
        assert events[0].state_to == CircuitBreakerState.L1_TRIGGERED
        assert events[1].state_from == CircuitBreakerState.L1_TRIGGERED
        assert events[1].state_to == CircuitBreakerState.L2_TRIGGERED

    def test_event_has_positions_snapshot(self) -> None:
        """Event should capture positions at the time of trigger."""
        dm = DrawdownManager()
        dm.update(100_000.0)
        positions = {"DI_PRE_365": 50_000.0, "USDBRL": -30_000.0}
        dm.update(97_000.0, positions=positions)

        events = dm.get_events()
        assert len(events) == 1
        assert events[0].positions_snapshot == positions

    def test_l1_recovery(self) -> None:
        """Equity recovering from -3% to above -1.5% should return to NORMAL."""
        dm = DrawdownManager()
        dm.update(100_000.0)
        dm.update(97_000.0)  # L1 at -3%
        assert dm.state == CircuitBreakerState.L1_TRIGGERED

        # Recover to above -1.5% (l1 * 0.5 = 1.5%)
        dm.update(99_000.0)  # drawdown = 1% < 1.5%
        assert dm.state == CircuitBreakerState.NORMAL

    def test_escalation_l1_to_l2(self) -> None:
        """Equity worsening from -3% to -5% should escalate L1 to L2."""
        dm = DrawdownManager()
        dm.update(100_000.0)
        dm.update(97_000.0)  # L1
        assert dm.state == CircuitBreakerState.L1_TRIGGERED

        dm.update(95_000.0)  # 5% drop -> L2
        assert dm.state == CircuitBreakerState.L2_TRIGGERED

    def test_hwm_updates_only_upward(self) -> None:
        """HWM should only increase, never decrease."""
        dm = DrawdownManager()
        dm.update(100_000.0)
        assert dm.high_water_mark == 100_000.0

        dm.update(95_000.0)  # Drop
        assert dm.high_water_mark == 100_000.0  # Stays at 100k

        dm.update(102_000.0)  # New high
        assert dm.high_water_mark == 102_000.0

        dm.update(101_000.0)  # Drop again
        assert dm.high_water_mark == 102_000.0  # Stays at 102k

    def test_reset(self) -> None:
        """Reset should return to NORMAL with cleared event log."""
        dm = DrawdownManager()
        dm.update(100_000.0)
        dm.update(97_000.0)  # L1
        assert dm.state == CircuitBreakerState.L1_TRIGGERED
        assert len(dm.get_events()) > 0

        dm.reset()
        assert dm.state == CircuitBreakerState.NORMAL
        assert dm.high_water_mark == 0.0
        assert len(dm.get_events()) == 0


class TestAlertDispatcher:
    """Tests for AlertDispatcher."""

    def test_alert_dispatcher_logs_on_transition(self) -> None:
        """AlertDispatcher should log event at WARNING level via structlog."""
        dispatcher = AlertDispatcher(enabled=True)

        event = CircuitBreakerEvent(
            timestamp=__import__("datetime").datetime(2026, 1, 1),
            state_from=CircuitBreakerState.NORMAL,
            state_to=CircuitBreakerState.L1_TRIGGERED,
            drawdown_pct=0.03,
            action="reduce_25%",
            positions_snapshot={"A": 100.0},
            pnl_at_trigger=-300.0,
            signals_at_trigger={},
        )

        with patch.object(dispatcher, "_logger") as mock_logger:
            result = dispatcher.dispatch(event)

        assert result is True
        mock_logger.warning.assert_called_once()
        call_kwargs = mock_logger.warning.call_args
        assert "circuit_breaker_event" in call_kwargs.args

    def test_alert_dispatcher_webhook_post(self) -> None:
        """AlertDispatcher should POST JSON to webhook URL."""
        dispatcher = AlertDispatcher(
            webhook_url="http://localhost:9999/hook", enabled=True
        )

        event = CircuitBreakerEvent(
            timestamp=__import__("datetime").datetime(2026, 1, 1),
            state_from=CircuitBreakerState.NORMAL,
            state_to=CircuitBreakerState.L1_TRIGGERED,
            drawdown_pct=0.03,
            action="reduce_25%",
            positions_snapshot={"A": 100.0},
            pnl_at_trigger=-300.0,
            signals_at_trigger={},
        )

        with patch("src.risk.drawdown_manager.urlopen") as mock_urlopen:
            result = dispatcher.dispatch(event)

        assert result is True
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        assert req.method == "POST"
        import json

        payload = json.loads(req.data)
        assert payload["event_type"] == "circuit_breaker"
        assert payload["state_to"] == "L1_TRIGGERED"
        assert payload["drawdown_pct"] == 0.03

    def test_alert_dispatcher_webhook_failure_no_crash(self) -> None:
        """AlertDispatcher should handle HTTP error gracefully."""
        dispatcher = AlertDispatcher(
            webhook_url="http://localhost:9999/hook", enabled=True
        )

        event = CircuitBreakerEvent(
            timestamp=__import__("datetime").datetime(2026, 1, 1),
            state_from=CircuitBreakerState.NORMAL,
            state_to=CircuitBreakerState.L1_TRIGGERED,
            drawdown_pct=0.03,
            action="reduce_25%",
            positions_snapshot={},
            pnl_at_trigger=0.0,
            signals_at_trigger={},
        )

        with patch(
            "src.risk.drawdown_manager.urlopen",
            side_effect=URLError("Connection refused"),
        ):
            result = dispatcher.dispatch(event)

        # Should return False but NOT raise
        assert result is False

    def test_drawdown_manager_calls_dispatcher(self) -> None:
        """DrawdownManager should call dispatcher on state transition."""
        mock_dispatcher = MagicMock(spec=AlertDispatcher)
        mock_dispatcher.dispatch.return_value = True

        dm = DrawdownManager(alert_dispatcher=mock_dispatcher)
        dm.update(100_000.0)
        dm.update(97_000.0)  # L1 trigger

        mock_dispatcher.dispatch.assert_called_once()
        event = mock_dispatcher.dispatch.call_args[0][0]
        assert isinstance(event, CircuitBreakerEvent)
        assert event.state_to == CircuitBreakerState.L1_TRIGGERED


class TestStrategyLossTracker:
    """Tests for StrategyLossTracker."""

    def test_strategy_loss_tracker_breach(self) -> None:
        """Strategy daily loss exceeding threshold should return True."""
        tracker = StrategyLossTracker(max_daily_loss_pct=0.02)
        breached = tracker.update("RATES_BR_01", -0.025)  # 2.5% > 2%
        assert breached is True
        assert len(tracker.event_log) == 1

    def test_strategy_loss_tracker_no_breach(self) -> None:
        """Strategy daily loss within threshold should return False."""
        tracker = StrategyLossTracker(max_daily_loss_pct=0.02)
        breached = tracker.update("RATES_BR_01", -0.01)  # 1% < 2%
        assert breached is False
        assert len(tracker.event_log) == 0

    def test_strategy_loss_tracker_positive_pnl(self) -> None:
        """Positive P&L should never trigger a breach."""
        tracker = StrategyLossTracker(max_daily_loss_pct=0.02)
        breached = tracker.update("FX_BR_01", 0.05)
        assert breached is False


class TestAssetClassLossTracker:
    """Tests for AssetClassLossTracker."""

    def test_asset_class_loss_tracker_breach(self) -> None:
        """Asset class daily loss exceeding threshold should return True."""
        tracker = AssetClassLossTracker(max_daily_loss_pct=0.03)
        breached = tracker.update("FIXED_INCOME", -0.04)  # 4% > 3%
        assert breached is True
        assert len(tracker.event_log) == 1

    def test_asset_class_loss_tracker_no_breach(self) -> None:
        """Asset class daily loss within threshold should return False."""
        tracker = AssetClassLossTracker(max_daily_loss_pct=0.03)
        breached = tracker.update("EQUITY_INDEX", -0.01)
        assert breached is False
        assert len(tracker.event_log) == 0

"""Tests for RiskMonitorService and PMSRiskLimits.

Covers:
- test_live_risk_structure: All top-level keys present in risk snapshot
- test_two_tier_alerts: WARNING at 80%, BREACH at 100% utilization
- test_concentration_by_asset_class: Concentration limit detection
- test_30_day_trend: Trend history accumulation via get_risk_trend()
- test_graceful_degradation: Valid output with only position_manager (all others None)
"""

from datetime import date

import pytest

from src.pms.position_manager import PositionManager
from src.pms.risk_limits_config import PMSRiskLimits
from src.pms.risk_monitor import RiskMonitorService

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def pm() -> PositionManager:
    """Fresh PositionManager with 100M BRL AUM."""
    return PositionManager(aum=100_000_000.0)


@pytest.fixture
def pm_with_positions(pm: PositionManager) -> PositionManager:
    """PositionManager pre-loaded with 2 positions and MTM run."""
    pm.open_position(
        instrument="DI1_F26",
        asset_class="RATES",
        direction="LONG",
        notional_brl=50_000_000.0,
        entry_price=90000.0,
        entry_date=date(2026, 2, 20),
        rate_pct=10.0,
        business_days=252,
        entry_fx_rate=5.0,
    )
    pm.open_position(
        instrument="USDBRL",
        asset_class="FX",
        direction="LONG",
        notional_brl=20_000_000.0,
        entry_price=5.0,
        entry_date=date(2026, 2, 20),
        entry_fx_rate=5.0,
    )
    # Run MTM to generate P&L history
    pm.mark_to_market(
        price_overrides={"DI1_F26": 91000.0, "USDBRL": 5.1},
        current_fx_rate=5.1,
        as_of_date=date(2026, 2, 21),
    )
    return pm


# =============================================================================
# Tests
# =============================================================================


class TestLiveRiskStructure:
    """Test that compute_live_risk returns all required top-level keys."""

    def test_live_risk_structure(self, pm_with_positions: PositionManager):
        """Create RiskMonitorService, compute_live_risk(), verify all keys."""
        svc = RiskMonitorService(position_manager=pm_with_positions)
        risk = svc.compute_live_risk(as_of_date=date(2026, 2, 21))

        # All top-level keys present
        assert "as_of_date" in risk
        assert "var" in risk
        assert "leverage" in risk
        assert "drawdown" in risk
        assert "concentration" in risk
        assert "stress_tests" in risk
        assert "limits_summary" in risk
        assert "alerts" in risk

        # VaR section keys
        var = risk["var"]
        assert "parametric_95" in var
        assert "parametric_99" in var
        assert "monte_carlo_95" in var
        assert "monte_carlo_99" in var
        assert "limit_95_pct" in var
        assert "limit_99_pct" in var
        assert "utilization_95_pct" in var
        assert "utilization_99_pct" in var

        # Leverage section keys
        lev = risk["leverage"]
        assert "gross" in lev
        assert "net" in lev
        assert "limit_gross" in lev
        assert "limit_net" in lev
        assert "utilization_gross_pct" in lev
        assert "utilization_net_pct" in lev

        # Drawdown section keys
        dd = risk["drawdown"]
        assert "current_drawdown_pct" in dd
        assert "max_drawdown_pct" in dd
        assert "limit_pct" in dd
        assert "warning_pct" in dd
        assert "days_in_drawdown" in dd

        # Concentration section keys
        conc = risk["concentration"]
        assert "by_asset_class" in conc
        assert "top_3_positions_pct" in conc

        # Limits summary keys
        limits = risk["limits_summary"]
        assert "overall_status" in limits
        assert "checks" in limits
        assert limits["overall_status"] in ("OK", "WARNING", "BREACHED")

        # Alerts is a list
        assert isinstance(risk["alerts"], list)

    def test_live_risk_leverage_values(self, pm_with_positions: PositionManager):
        """Verify leverage computation matches expected values."""
        svc = RiskMonitorService(position_manager=pm_with_positions)
        risk = svc.compute_live_risk(as_of_date=date(2026, 2, 21))

        # Gross leverage = (50M + 20M) / 100M = 0.7
        assert abs(risk["leverage"]["gross"] - 0.7) < 0.01

        # Net leverage: both LONG -> (50M + 20M) / 100M = 0.7
        assert abs(risk["leverage"]["net"] - 0.7) < 0.01


class TestTwoTierAlerts:
    """Test two-tier alert generation: WARNING at 80%, BREACH at 100%."""

    def test_leverage_warning_at_80_pct(self):
        """High leverage at 87.5% utilization -> WARNING alert."""
        pm = PositionManager(aum=100_000_000.0)
        # Open position with notional = 3.5x AUM (limit is 4.0x)
        # Utilization = 3.5 / 4.0 = 87.5%
        pm.open_position(
            instrument="DI1_F26",
            asset_class="RATES",
            direction="LONG",
            notional_brl=350_000_000.0,
            entry_price=90000.0,
        )

        svc = RiskMonitorService(position_manager=pm)
        risk = svc.compute_live_risk()

        leverage_alerts = [a for a in risk["alerts"] if "LEVERAGE" in a["type"]]
        warning_alerts = [a for a in leverage_alerts if a["severity"] == "WARNING"]
        assert (
            len(warning_alerts) > 0
        ), f"Expected WARNING leverage alert, got: {leverage_alerts}"

    def test_leverage_breach_at_100_pct(self):
        """Leverage at 4.5x (limit 4.0x) -> BREACH alert."""
        pm = PositionManager(aum=100_000_000.0)
        # Open position with notional = 4.5x AUM (limit is 4.0x)
        pm.open_position(
            instrument="DI1_F26",
            asset_class="RATES",
            direction="LONG",
            notional_brl=450_000_000.0,
            entry_price=90000.0,
        )

        svc = RiskMonitorService(position_manager=pm)
        risk = svc.compute_live_risk()

        leverage_alerts = [a for a in risk["alerts"] if "LEVERAGE" in a["type"]]
        breach_alerts = [a for a in leverage_alerts if a["severity"] == "BREACH"]
        assert (
            len(breach_alerts) > 0
        ), f"Expected BREACH leverage alert, got: {leverage_alerts}"

    def test_alert_severity_values(self):
        """Verify alert severity is always 'WARNING' or 'BREACH'."""
        pm = PositionManager(aum=100_000_000.0)
        pm.open_position(
            instrument="DI1_F26",
            asset_class="RATES",
            direction="LONG",
            notional_brl=350_000_000.0,
            entry_price=90000.0,
        )

        svc = RiskMonitorService(position_manager=pm)
        risk = svc.compute_live_risk()

        for alert in risk["alerts"]:
            assert alert["severity"] in ("WARNING", "BREACH")
            assert "type" in alert
            assert "message" in alert
            assert "value" in alert
            assert "limit" in alert


class TestConcentrationByAssetClass:
    """Test concentration breakdown with limit detection."""

    def test_concentration_breached(self):
        """3 RATES positions totaling 65% of gross -> BREACHED (limit 60%)."""
        pm = PositionManager(aum=100_000_000.0)
        # Open 3 RATES positions totaling 65M of 100M gross
        pm.open_position(
            instrument="DI1_F26",
            asset_class="RATES",
            direction="LONG",
            notional_brl=30_000_000.0,
            entry_price=90000.0,
        )
        pm.open_position(
            instrument="DI1_F27",
            asset_class="RATES",
            direction="LONG",
            notional_brl=20_000_000.0,
            entry_price=88000.0,
        )
        pm.open_position(
            instrument="DI1_F28",
            asset_class="RATES",
            direction="LONG",
            notional_brl=15_000_000.0,
            entry_price=86000.0,
        )
        # One FX position to dilute slightly (35M total)
        pm.open_position(
            instrument="USDBRL",
            asset_class="FX",
            direction="LONG",
            notional_brl=35_000_000.0,
            entry_price=5.0,
        )

        svc = RiskMonitorService(position_manager=pm)
        risk = svc.compute_live_risk()

        conc = risk["concentration"]["by_asset_class"]
        assert "RATES" in conc
        assert conc["RATES"]["status"] == "BREACHED"
        assert conc["RATES"]["notional_pct"] == pytest.approx(65.0, abs=0.5)
        assert conc["RATES"]["limit_pct"] == 60.0

    def test_concentration_ok(self):
        """Balanced allocation within limits -> OK status."""
        pm = PositionManager(aum=100_000_000.0)
        # RATES 20M, FX 10M, EQUITY 10M -> total 40M
        # RATES: 50%/60% = 83% utilization -> WARNING with default 80% threshold
        # Use generous limits to keep all under 80% utilization
        pm.open_position(
            instrument="DI1_F26",
            asset_class="RATES",
            direction="LONG",
            notional_brl=20_000_000.0,
            entry_price=90000.0,
        )
        pm.open_position(
            instrument="USDBRL",
            asset_class="FX",
            direction="LONG",
            notional_brl=10_000_000.0,
            entry_price=5.0,
        )
        pm.open_position(
            instrument="IBOV_FUT",
            asset_class="EQUITY",
            direction="LONG",
            notional_brl=10_000_000.0,
            entry_price=100.0,
        )

        # With total gross 40M: RATES 50%, FX 25%, EQUITY 25%
        # Use limits high enough so utilization stays under 80%
        limits = PMSRiskLimits(
            concentration_limits={
                "RATES": 80.0,  # 50/80 = 62.5% util (OK)
                "FX": 50.0,  # 25/50 = 50% util (OK)
                "EQUITY": 50.0,  # 25/50 = 50% util (OK)
            },
        )
        svc = RiskMonitorService(position_manager=pm, pms_limits=limits)
        risk = svc.compute_live_risk()

        conc = risk["concentration"]["by_asset_class"]
        assert conc["RATES"]["status"] == "OK"
        assert conc["FX"]["status"] == "OK"
        assert conc["EQUITY"]["status"] == "OK"


class TestRiskTrend:
    """Test 30-day trend history accumulation."""

    def test_30_day_trend(self):
        """Call compute_live_risk() 3 times, verify get_risk_trend() returns 3."""
        pm = PositionManager(aum=100_000_000.0)
        pm.open_position(
            instrument="DI1_F26",
            asset_class="RATES",
            direction="LONG",
            notional_brl=50_000_000.0,
            entry_price=90000.0,
        )

        svc = RiskMonitorService(position_manager=pm)

        # Call compute_live_risk for 3 different dates
        svc.compute_live_risk(as_of_date=date(2026, 2, 20))
        svc.compute_live_risk(as_of_date=date(2026, 2, 21))
        svc.compute_live_risk(as_of_date=date(2026, 2, 22))

        trend = svc.get_risk_trend(30)
        assert len(trend) == 3
        assert trend[0]["date"] == date(2026, 2, 20)
        assert trend[1]["date"] == date(2026, 2, 21)
        assert trend[2]["date"] == date(2026, 2, 22)

        # Each entry should have required keys
        for entry in trend:
            assert "var_95" in entry
            assert "leverage_gross" in entry
            assert "drawdown_pct" in entry
            assert "alert_count" in entry
            assert "overall_status" in entry

    def test_trend_limited_by_days_param(self):
        """get_risk_trend(2) on 3 snapshots returns only 2."""
        pm = PositionManager(aum=100_000_000.0)
        pm.open_position(
            instrument="DI1_F26",
            asset_class="RATES",
            direction="LONG",
            notional_brl=50_000_000.0,
            entry_price=90000.0,
        )

        svc = RiskMonitorService(position_manager=pm)
        svc.compute_live_risk(as_of_date=date(2026, 2, 20))
        svc.compute_live_risk(as_of_date=date(2026, 2, 21))
        svc.compute_live_risk(as_of_date=date(2026, 2, 22))

        trend = svc.get_risk_trend(2)
        assert len(trend) == 2


class TestGracefulDegradation:
    """Test valid output when optional components are None."""

    def test_graceful_degradation(self):
        """Only position_manager provided, all others None."""
        pm = PositionManager(aum=100_000_000.0)
        pm.open_position(
            instrument="DI1_F26",
            asset_class="RATES",
            direction="LONG",
            notional_brl=50_000_000.0,
            entry_price=90000.0,
        )
        pm.open_position(
            instrument="USDBRL",
            asset_class="FX",
            direction="LONG",
            notional_brl=20_000_000.0,
            entry_price=5.0,
        )

        svc = RiskMonitorService(
            position_manager=pm,
            risk_limits_manager=None,
            var_calculator=None,
            stress_tester=None,
        )
        risk = svc.compute_live_risk()

        # Structure valid even without optional components
        assert risk["stress_tests"] == []
        assert risk["var"]["monte_carlo_95"] is None
        assert risk["var"]["monte_carlo_99"] is None

        # Limits summary should still have PMS-based checks
        assert risk["limits_summary"]["overall_status"] in ("OK", "WARNING", "BREACHED")
        assert len(risk["limits_summary"]["checks"]) >= 5  # 5 PMS limit checks

        # Leverage and concentration still computed from position book
        assert risk["leverage"]["gross"] > 0
        assert len(risk["concentration"]["by_asset_class"]) >= 2

    def test_no_position_manager(self):
        """No position_manager at all -> still returns valid empty structure."""
        svc = RiskMonitorService(position_manager=None)
        risk = svc.compute_live_risk()

        assert risk["leverage"]["gross"] == 0.0
        assert risk["stress_tests"] == []
        assert risk["concentration"]["by_asset_class"] == {}
        assert isinstance(risk["alerts"], list)


class TestPMSRiskLimits:
    """Test PMSRiskLimits dataclass."""

    def test_defaults(self):
        """Verify default values match spec."""
        limits = PMSRiskLimits()
        assert limits.var_95_limit_pct == 2.0
        assert limits.var_99_limit_pct == 3.0
        assert limits.gross_leverage_limit == 4.0
        assert limits.net_leverage_limit == 2.0
        assert limits.drawdown_warning_pct == 5.0
        assert limits.drawdown_limit_pct == 10.0
        assert limits.warning_threshold_pct == 80.0
        assert "RATES" in limits.concentration_limits
        assert limits.concentration_limits["RATES"] == 60.0

    def test_from_env(self, monkeypatch):
        """from_env() reads PMS_RISK_* env vars."""
        monkeypatch.setenv("PMS_RISK_VAR_95_LIMIT_PCT", "3.5")
        monkeypatch.setenv("PMS_RISK_GROSS_LEVERAGE_LIMIT", "5.0")
        limits = PMSRiskLimits.from_env()
        assert limits.var_95_limit_pct == 3.5
        assert limits.gross_leverage_limit == 5.0
        # Non-overridden defaults remain
        assert limits.var_99_limit_pct == 3.0

    def test_frozen(self):
        """PMSRiskLimits is frozen (immutable)."""
        limits = PMSRiskLimits()
        with pytest.raises(AttributeError):
            limits.var_95_limit_pct = 999.0  # type: ignore[misc]

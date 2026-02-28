"""Tests for enhanced stress tester v2 features.

Tests 6 scenarios (including BR Fiscal Crisis and Global Risk-Off),
reverse stress testing, historical replay, and run_all_v2.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.risk.stress_tester import (
    DEFAULT_SCENARIOS,
    StressResult,
    StressTester,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tester() -> StressTester:
    """StressTester with default 6 scenarios."""
    return StressTester()


@pytest.fixture
def sample_positions() -> dict[str, float]:
    """Sample portfolio positions for stress testing.

    Includes instruments that match several scenario shock keys.
    """
    return {
        "USDBRL": -500_000.0,  # Short USD (long BRL)
        "DI_PRE_365": 1_000_000.0,  # Long DI
        "IBOVESPA": 800_000.0,  # Long equities
        "SP500": 300_000.0,  # Long US equities
        "NTN_B_REAL": 600_000.0,  # Long inflation-linked
        "OIL": 200_000.0,  # Long oil
        "CDS_BR": -100_000.0,  # Short CDS protection
    }


# ---------------------------------------------------------------------------
# Scenario count tests
# ---------------------------------------------------------------------------


class TestScenarioCount:
    """Tests that DEFAULT_SCENARIOS has the expected 6 scenarios."""

    def test_default_scenarios_has_6(self) -> None:
        """DEFAULT_SCENARIOS should contain exactly 6 scenarios."""
        assert (
            len(DEFAULT_SCENARIOS) >= 6
        ), f"Expected at least 6 scenarios, got {len(DEFAULT_SCENARIOS)}"

    def test_scenario_names(self) -> None:
        """All expected scenario names should be present."""
        names = {s.name for s in DEFAULT_SCENARIOS}
        expected = {
            "Taper Tantrum 2013",
            "BR Crisis 2015",
            "COVID 2020",
            "Rate Shock 2022",
            "BR Fiscal Crisis (Teto de Gastos)",
            "Global Risk-Off (Geopolitical)",
        }
        assert expected.issubset(names), f"Missing scenarios: {expected - names}"


# ---------------------------------------------------------------------------
# BR Fiscal Crisis scenario tests
# ---------------------------------------------------------------------------


class TestBRFiscalCrisis:
    """Tests for the BR Fiscal Crisis (Teto de Gastos) scenario."""

    def test_fiscal_crisis_shocks_di_pre(
        self, tester: StressTester, sample_positions: dict[str, float]
    ) -> None:
        """BR Fiscal Crisis should apply DI_PRE shock to DI positions."""
        fiscal_scenario = next(s for s in tester.scenarios if "Fiscal" in s.name)
        result = tester.run_scenario(sample_positions, fiscal_scenario, 3_500_000.0)

        # DI_PRE_365 matches DI_PRE via prefix matching
        assert result.position_pnl["DI_PRE_365"] != 0.0
        # DI_PRE shock is +0.035, notional is 1,000,000 => PnL = +35,000
        assert result.position_pnl["DI_PRE_365"] == pytest.approx(
            1_000_000.0 * 0.035, rel=1e-6
        )

    def test_fiscal_crisis_shocks_usdbrl(
        self, tester: StressTester, sample_positions: dict[str, float]
    ) -> None:
        """BR Fiscal Crisis should apply USDBRL shock."""
        fiscal_scenario = next(s for s in tester.scenarios if "Fiscal" in s.name)
        result = tester.run_scenario(sample_positions, fiscal_scenario, 3_500_000.0)

        # USDBRL shock = +0.25, short position = -500,000 => PnL = -125,000
        assert result.position_pnl["USDBRL"] == pytest.approx(
            -500_000.0 * 0.25, rel=1e-6
        )

    def test_fiscal_crisis_has_cds_shock(self) -> None:
        """BR Fiscal Crisis should include CDS_BR shock."""
        fiscal_scenario = next(s for s in DEFAULT_SCENARIOS if "Fiscal" in s.name)
        assert "CDS_BR" in fiscal_scenario.shocks
        assert fiscal_scenario.shocks["CDS_BR"] == 0.40


# ---------------------------------------------------------------------------
# Global Risk-Off scenario tests
# ---------------------------------------------------------------------------


class TestGlobalRiskOff:
    """Tests for the Global Risk-Off (Geopolitical) scenario."""

    def test_risk_off_shocks_ibovespa(
        self, tester: StressTester, sample_positions: dict[str, float]
    ) -> None:
        """Global Risk-Off should apply IBOVESPA shock."""
        risk_off = next(s for s in tester.scenarios if "Risk-Off" in s.name)
        result = tester.run_scenario(sample_positions, risk_off, 3_500_000.0)

        # IBOVESPA shock = -0.30, long 800,000 => PnL = -240,000
        assert result.position_pnl["IBOVESPA"] == pytest.approx(
            800_000.0 * (-0.30), rel=1e-6
        )

    def test_risk_off_shocks_sp500(
        self, tester: StressTester, sample_positions: dict[str, float]
    ) -> None:
        """Global Risk-Off should apply SP500 shock."""
        risk_off = next(s for s in tester.scenarios if "Risk-Off" in s.name)
        result = tester.run_scenario(sample_positions, risk_off, 3_500_000.0)

        # SP500 shock = -0.25, long 300,000 => PnL = -75,000
        assert result.position_pnl["SP500"] == pytest.approx(
            300_000.0 * (-0.25), rel=1e-6
        )

    def test_risk_off_has_oil_shock(self) -> None:
        """Global Risk-Off should include OIL shock."""
        risk_off = next(s for s in DEFAULT_SCENARIOS if "Risk-Off" in s.name)
        assert "OIL" in risk_off.shocks
        assert risk_off.shocks["OIL"] == -0.40


# ---------------------------------------------------------------------------
# Reverse stress testing
# ---------------------------------------------------------------------------


class TestReverseStressTest:
    """Tests for the reverse_stress_test method."""

    def test_finds_multiplier_for_10pct_loss(self, tester: StressTester) -> None:
        """Reverse stress test should find multiplier producing ~10% loss."""
        # Simple portfolio with clear exposure to Taper Tantrum shocks
        positions = {
            "IBOVESPA": 1_000_000.0,
            "USDBRL": -500_000.0,
        }
        portfolio_value = 1_500_000.0

        results = tester.reverse_stress_test(
            positions, portfolio_value, max_loss_pct=-0.10
        )

        # At least one scenario should be feasible
        feasible = {k: v for k, v in results.items() if v["feasible"]}
        assert len(feasible) > 0, "At least one scenario should be feasible"

        # Check that feasible scenarios produce approximately -10% loss
        for name, result in feasible.items():
            assert abs(result["resulting_loss_pct"] - (-0.10)) < 0.001, (
                f"Scenario '{name}' loss {result['resulting_loss_pct']:.6f} "
                f"should be approximately -0.10"
            )

    def test_infeasible_when_no_exposure(self, tester: StressTester) -> None:
        """Reverse stress should be infeasible when positions have no scenario exposure."""
        # Positions not matching any scenario shock keys
        positions = {
            "RANDOM_ASSET_1": 1_000_000.0,
            "RANDOM_ASSET_2": 500_000.0,
        }
        portfolio_value = 1_500_000.0

        results = tester.reverse_stress_test(
            positions, portfolio_value, max_loss_pct=-0.10
        )

        for name, result in results.items():
            assert (
                result["feasible"] is False
            ), f"Scenario '{name}' should be infeasible for unexposed positions"

    def test_returns_all_scenarios(self, tester: StressTester) -> None:
        """Reverse stress test should return results for all 6 scenarios."""
        positions = {"IBOVESPA": 1_000_000.0}
        results = tester.reverse_stress_test(positions, 1_000_000.0)
        assert len(results) == len(tester.scenarios)

    def test_required_shocks_scaled_by_multiplier(self, tester: StressTester) -> None:
        """Required shocks should be scenario shocks scaled by the multiplier."""
        positions = {"IBOVESPA": 1_000_000.0}
        results = tester.reverse_stress_test(positions, 1_000_000.0, max_loss_pct=-0.10)

        for name, result in results.items():
            if result["feasible"] and result["multiplier"] > 0:
                scenario = next(s for s in tester.scenarios if s.name == name)
                for key, shock in result["required_shocks"].items():
                    expected = scenario.shocks[key] * result["multiplier"]
                    assert (
                        abs(shock - expected) < 1e-4
                    ), f"Shock for {key} should be {expected:.6f}, got {shock:.6f}"


# ---------------------------------------------------------------------------
# Historical replay
# ---------------------------------------------------------------------------


class TestHistoricalReplay:
    """Tests for the historical_replay method."""

    def test_computes_correct_cumulative_pnl(self, tester: StressTester) -> None:
        """Historical replay should compute correct cumulative P&L from daily returns."""
        positions = {"IBOVESPA": 1_000_000.0}
        # 5 days of returns: -2%, -3%, +1%, -4%, +2%
        historical_returns = {
            "IBOVESPA": np.array([-0.02, -0.03, 0.01, -0.04, 0.02]),
        }

        result = tester.historical_replay(
            positions, historical_returns, 1_000_000.0, period_name="Test Crisis"
        )

        # Cumulative P&L: day 1: -20K, day 2: -50K, day 3: -40K, day 4: -80K, day 5: -60K
        # Worst point is day 4: -80K
        assert result.portfolio_pnl == pytest.approx(-80_000.0, rel=1e-6)
        assert result.scenario_name == "Historical Replay: Test Crisis"

    def test_identifies_worst_drawdown_point(self, tester: StressTester) -> None:
        """Historical replay should identify the worst drawdown day."""
        positions = {"IBOVESPA": 1_000_000.0, "SP500": 500_000.0}
        historical_returns = {
            "IBOVESPA": np.array([-0.01, -0.05, 0.02, -0.01]),
            "SP500": np.array([-0.02, -0.03, 0.01, 0.01]),
        }

        result = tester.historical_replay(
            positions, historical_returns, 1_500_000.0, period_name="Multi-Asset"
        )

        # IBOV: cum day-by-day: -10K, -60K, -40K, -50K
        # SP500: cum day-by-day: -10K, -25K, -20K, -15K
        # Total: -20K, -85K, -60K, -65K => worst at day 2 (index 1): -85K
        assert result.portfolio_pnl == pytest.approx(-85_000.0, rel=1e-6)
        assert result.portfolio_pnl_pct == pytest.approx(
            -85_000.0 / 1_500_000.0, rel=1e-6
        )

    def test_pnl_pct_is_relative_to_portfolio_value(self, tester: StressTester) -> None:
        """Portfolio P&L percentage should be relative to portfolio_value."""
        positions = {"IBOVESPA": 1_000_000.0}
        historical_returns = {
            "IBOVESPA": np.array([-0.10]),  # -10% in one day
        }

        result = tester.historical_replay(positions, historical_returns, 2_000_000.0)

        # P&L: -100K, pct: -100K / 2M = -5%
        assert result.portfolio_pnl == pytest.approx(-100_000.0, rel=1e-6)
        assert result.portfolio_pnl_pct == pytest.approx(-0.05, rel=1e-6)

    def test_handles_unmatched_instruments(self, tester: StressTester) -> None:
        """Instruments without historical returns should contribute zero P&L."""
        positions = {
            "IBOVESPA": 1_000_000.0,
            "UNKNOWN_ASSET": 500_000.0,
        }
        historical_returns = {
            "IBOVESPA": np.array([-0.05, -0.03]),
        }

        result = tester.historical_replay(positions, historical_returns, 1_500_000.0)

        assert result.positions_impacted == 1
        assert result.positions_unaffected == 1
        # UNKNOWN_ASSET PnL should be 0
        assert result.position_pnl["UNKNOWN_ASSET"] == 0.0


# ---------------------------------------------------------------------------
# run_all_v2
# ---------------------------------------------------------------------------


class TestRunAllV2:
    """Tests for the run_all_v2 convenience method."""

    def test_returns_all_scenario_results(self, tester: StressTester) -> None:
        """run_all_v2 should return results for all 6 scenarios."""
        positions = {"IBOVESPA": 1_000_000.0}
        result = tester.run_all_v2(positions, 1_000_000.0)

        assert "scenarios" in result
        assert len(result["scenarios"]) == 6

    def test_includes_reverse_results(self, tester: StressTester) -> None:
        """run_all_v2 should include reverse stress test results when enabled."""
        positions = {"IBOVESPA": 1_000_000.0}
        result = tester.run_all_v2(positions, 1_000_000.0, include_reverse=True)

        assert result["reverse"] is not None
        assert len(result["reverse"]) == 6

    def test_excludes_reverse_when_disabled(self, tester: StressTester) -> None:
        """run_all_v2 should exclude reverse results when include_reverse=False."""
        positions = {"IBOVESPA": 1_000_000.0}
        result = tester.run_all_v2(positions, 1_000_000.0, include_reverse=False)

        assert result["reverse"] is None

    def test_identifies_worst_case(self, tester: StressTester) -> None:
        """run_all_v2 should identify the worst case scenario."""
        positions = {
            "IBOVESPA": 1_000_000.0,
            "USDBRL": -500_000.0,
            "SP500": 500_000.0,
            "OIL": 200_000.0,
        }
        result = tester.run_all_v2(positions, 2_200_000.0, include_reverse=False)

        assert result["worst_case"] is not None
        assert isinstance(result["worst_case"], StressResult)
        # Worst case should be the scenario with most negative P&L
        all_pnls = [r.portfolio_pnl for r in result["scenarios"]]
        assert result["worst_case"].portfolio_pnl == min(all_pnls)

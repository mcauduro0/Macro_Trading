"""Unit tests for the StressTester and historical scenario replay.

Covers single-scenario P&L computation, short/long positions, prefix
matching for DI instruments, portfolio percentage calculation, worst-case
identification, advisory-only guarantee, and edge cases.
"""

from __future__ import annotations

import copy

import pytest

from src.risk.stress_tester import (
    DEFAULT_SCENARIOS,
    StressResult,
    StressScenario,
    StressTester,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tester() -> StressTester:
    """Default StressTester with the 4 built-in scenarios."""
    return StressTester()


@pytest.fixture
def taper_tantrum() -> StressScenario:
    """The Taper Tantrum 2013 scenario."""
    return DEFAULT_SCENARIOS[0]


@pytest.fixture
def simple_positions() -> dict[str, float]:
    """Simple portfolio for deterministic P&L tests."""
    return {
        "USDBRL": 100_000.0,   # Long USDBRL
        "IBOVESPA": -50_000.0,  # Short IBOVESPA
        "DI_PRE": 200_000.0,   # Long DI
    }


# ---------------------------------------------------------------------------
# Single scenario tests
# ---------------------------------------------------------------------------


class TestSingleScenario:
    def test_single_scenario_known_pnl(
        self, tester: StressTester, taper_tantrum: StressScenario
    ) -> None:
        """Long USDBRL 100K, Taper Tantrum +15% shock -> pnl = +15K."""
        positions = {"USDBRL": 100_000.0}
        result = tester.run_scenario(positions, taper_tantrum)

        assert result.portfolio_pnl == pytest.approx(15_000.0)
        assert result.position_pnl["USDBRL"] == pytest.approx(15_000.0)

    def test_single_scenario_short_position(
        self, tester: StressTester, taper_tantrum: StressScenario
    ) -> None:
        """Short USDBRL -100K, +15% shock -> pnl = -15K."""
        positions = {"USDBRL": -100_000.0}
        result = tester.run_scenario(positions, taper_tantrum)

        assert result.portfolio_pnl == pytest.approx(-15_000.0)
        assert result.position_pnl["USDBRL"] == pytest.approx(-15_000.0)

    def test_no_matching_shock(
        self, tester: StressTester, taper_tantrum: StressScenario
    ) -> None:
        """Position in instrument not in scenario -> zero P&L."""
        positions = {"UNKNOWN_INSTRUMENT": 500_000.0}
        result = tester.run_scenario(positions, taper_tantrum)

        assert result.position_pnl["UNKNOWN_INSTRUMENT"] == pytest.approx(0.0)
        assert result.portfolio_pnl == pytest.approx(0.0)
        assert result.positions_unaffected == 1
        assert result.positions_impacted == 0


# ---------------------------------------------------------------------------
# Prefix matching tests
# ---------------------------------------------------------------------------


class TestPrefixMatching:
    def test_prefix_matching_di_pre(
        self, tester: StressTester, taper_tantrum: StressScenario
    ) -> None:
        """DI_PRE_365 position matches DI_PRE shock."""
        positions = {"DI_PRE_365": 100_000.0}
        result = tester.run_scenario(positions, taper_tantrum)

        # DI_PRE shock is +0.02 in Taper Tantrum
        assert result.position_pnl["DI_PRE_365"] == pytest.approx(2_000.0)
        assert result.positions_impacted == 1

    def test_exact_match_takes_precedence(
        self, tester: StressTester
    ) -> None:
        """Exact match should be preferred over prefix match."""
        scenario = StressScenario(
            name="Test",
            description="Test scenario",
            shocks={"DI_PRE": 0.02, "DI_PRE_365": 0.05},
            historical_period="Test period",
        )
        positions = {"DI_PRE_365": 100_000.0}
        result = tester.run_scenario(positions, scenario)

        # Should use exact DI_PRE_365 shock (0.05), not prefix DI_PRE (0.02)
        assert result.position_pnl["DI_PRE_365"] == pytest.approx(5_000.0)


# ---------------------------------------------------------------------------
# Run all scenarios
# ---------------------------------------------------------------------------


class TestRunAll:
    def test_run_all_returns_4_results(self, tester: StressTester) -> None:
        """Default scenarios -> 4 StressResult objects."""
        positions = {"USDBRL": 100_000.0, "IBOVESPA": -50_000.0}
        results = tester.run_all(positions)

        assert len(results) == 4
        assert all(isinstance(r, StressResult) for r in results)

    def test_run_all_scenario_names(self, tester: StressTester) -> None:
        """All 4 default scenario names should appear in results."""
        positions = {"USDBRL": 100_000.0}
        results = tester.run_all(positions)

        names = {r.scenario_name for r in results}
        assert "Taper Tantrum 2013" in names
        assert "BR Crisis 2015" in names
        assert "COVID 2020" in names
        assert "Rate Shock 2022" in names


# ---------------------------------------------------------------------------
# Worst case
# ---------------------------------------------------------------------------


class TestWorstCase:
    def test_worst_case_selection(self, tester: StressTester) -> None:
        """worst_case returns scenario with most negative portfolio P&L."""
        # Short USDBRL loses when USDBRL goes up; BR Crisis has +30% shock (worst)
        positions = {"USDBRL": -100_000.0}
        results = tester.run_all(positions)

        worst = tester.worst_case(results)
        # BR Crisis has +0.30 shock -> short loses -30K
        assert worst.scenario_name == "BR Crisis 2015"
        assert worst.portfolio_pnl == pytest.approx(-30_000.0)

    def test_worst_case_empty_raises(self, tester: StressTester) -> None:
        """Empty results list should raise ValueError."""
        with pytest.raises(ValueError, match="empty"):
            tester.worst_case([])


# ---------------------------------------------------------------------------
# Portfolio percentage
# ---------------------------------------------------------------------------


class TestPortfolioPercentage:
    def test_portfolio_pnl_pct(
        self, tester: StressTester, taper_tantrum: StressScenario
    ) -> None:
        """Verify percentage calculation against known portfolio value."""
        positions = {"USDBRL": 100_000.0}
        result = tester.run_scenario(
            positions, taper_tantrum, portfolio_value=1_000_000.0
        )

        expected_pct = 15_000.0 / 1_000_000.0
        assert result.portfolio_pnl_pct == pytest.approx(expected_pct)

    def test_portfolio_pnl_pct_approx_without_value(
        self, tester: StressTester, taper_tantrum: StressScenario
    ) -> None:
        """Without portfolio_value, uses sum(abs(notionals)) as denominator."""
        positions = {"USDBRL": 100_000.0, "IBOVESPA": -50_000.0}
        result = tester.run_scenario(positions, taper_tantrum)

        # Total abs notional = 150K
        expected_pct = result.portfolio_pnl / 150_000.0
        assert result.portfolio_pnl_pct == pytest.approx(expected_pct)


# ---------------------------------------------------------------------------
# Advisory only / no side effects
# ---------------------------------------------------------------------------


class TestAdvisoryOnly:
    def test_advisory_only_no_side_effects(
        self, tester: StressTester, taper_tantrum: StressScenario
    ) -> None:
        """Stress test does not modify input positions dict."""
        positions = {"USDBRL": 100_000.0, "IBOVESPA": -50_000.0}
        original = copy.deepcopy(positions)

        tester.run_scenario(positions, taper_tantrum)

        assert positions == original, "Positions dict must not be modified"

    def test_run_all_no_side_effects(self, tester: StressTester) -> None:
        """run_all does not modify input positions."""
        positions = {"USDBRL": 100_000.0, "DI_PRE_365": 200_000.0}
        original = copy.deepcopy(positions)

        tester.run_all(positions)

        assert positions == original


# ---------------------------------------------------------------------------
# Worst position identification
# ---------------------------------------------------------------------------


class TestWorstPosition:
    def test_worst_position_identified(
        self, tester: StressTester, taper_tantrum: StressScenario
    ) -> None:
        """Correctly identifies instrument with largest loss."""
        positions = {
            "USDBRL": 50_000.0,     # +15% -> +7.5K
            "IBOVESPA": 100_000.0,  # -15% -> -15K (worst)
            "DI_PRE": 50_000.0,     # +2%  -> +1K
        }
        result = tester.run_scenario(positions, taper_tantrum)

        assert result.worst_position == "IBOVESPA"
        assert result.worst_position_pnl == pytest.approx(-15_000.0)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_positions(self, tester: StressTester) -> None:
        """Empty portfolio -> zero P&L for all scenarios."""
        results = tester.run_all({})

        for r in results:
            assert r.portfolio_pnl == pytest.approx(0.0)
            assert r.portfolio_pnl_pct == pytest.approx(0.0)
            assert r.positions_impacted == 0
            assert r.positions_unaffected == 0

    def test_custom_scenarios(self) -> None:
        """StressTester accepts custom scenario list."""
        custom = [
            StressScenario(
                name="Custom",
                description="Test",
                shocks={"USDBRL": 0.50},
                historical_period="N/A",
            )
        ]
        tester = StressTester(scenarios=custom)
        results = tester.run_all({"USDBRL": 100_000.0})

        assert len(results) == 1
        assert results[0].portfolio_pnl == pytest.approx(50_000.0)

    def test_default_scenarios_count(self) -> None:
        """4 default scenarios are defined."""
        assert len(DEFAULT_SCENARIOS) == 4


# Run with: python -m pytest tests/test_risk/test_stress_tester.py -v

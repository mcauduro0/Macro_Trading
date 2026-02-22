"""Historical stress scenario replay engine.

Defines 4 locked historical crisis scenarios (Taper Tantrum 2013,
BR Crisis 2015, COVID 2020, Rate Shock 2022) and applies their shocks
to current portfolio positions to estimate position-level and
portfolio-level P&L impact.

Stress tests are advisory only -- they report results but do not
trigger position changes. All functions are pure computation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StressScenario:
    """Definition of a historical stress scenario.

    Attributes:
        name: Human-readable scenario name.
        description: Brief narrative of the crisis.
        shocks: Mapping of instrument_id -> percentage move.
            E.g., ``{"USDBRL": 0.15}`` means +15% move in USDBRL.
        historical_period: Time range of the original crisis.
    """

    name: str
    description: str
    shocks: dict[str, float]
    historical_period: str


@dataclass
class StressResult:
    """Result of applying a stress scenario to a portfolio.

    Attributes:
        scenario_name: Name of the scenario that was applied.
        portfolio_pnl: Total portfolio P&L from the scenario.
        portfolio_pnl_pct: P&L as a percentage of portfolio value.
        position_pnl: Per-instrument P&L breakdown.
        worst_position: Instrument with the largest loss.
        worst_position_pnl: P&L of the worst position.
        positions_impacted: Count of positions with non-zero shock applied.
        positions_unaffected: Count of positions with no applicable shock.
        timestamp: When the stress test was computed.
    """

    scenario_name: str
    portfolio_pnl: float
    portfolio_pnl_pct: float
    position_pnl: dict[str, float]
    worst_position: str
    worst_position_pnl: float
    positions_impacted: int
    positions_unaffected: int
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Default historical scenarios (locked)
# ---------------------------------------------------------------------------


DEFAULT_SCENARIOS: list[StressScenario] = [
    StressScenario(
        name="Taper Tantrum 2013",
        description=(
            "Fed taper announcement triggered EM sell-off. BRL weakened, "
            "DI rates spiked, equities sold off."
        ),
        shocks={
            "USDBRL": 0.15,
            "DI_PRE": 0.02,
            "NTN_B_REAL": -0.08,
            "IBOVESPA": -0.15,
            "UST_NOM": 0.01,
        },
        historical_period="May 2013 - Aug 2013",
    ),
    StressScenario(
        name="BR Crisis 2015",
        description=(
            "Brazil sovereign downgrade, impeachment crisis. BRL collapsed, "
            "DI rates surged, equities cratered."
        ),
        shocks={
            "USDBRL": 0.30,
            "DI_PRE": 0.04,
            "NTN_B_REAL": -0.15,
            "IBOVESPA": -0.25,
        },
        historical_period="Sep 2015 - Feb 2016",
    ),
    StressScenario(
        name="COVID 2020",
        description=(
            "Global pandemic panic. Risk assets sold off sharply, BRL weakened, "
            "oil crashed, volatility spiked."
        ),
        shocks={
            "USDBRL": 0.20,
            "DI_PRE": 0.02,
            "IBOVESPA": -0.35,
            "SP500": -0.30,
            "OIL": -0.50,
        },
        historical_period="Feb 2020 - Mar 2020",
    ),
    StressScenario(
        name="Rate Shock 2022",
        description=(
            "Brazilian fiscal scare drove massive DI rate repricing, BRL weakened, "
            "real rates surged."
        ),
        shocks={
            "USDBRL": 0.25,
            "DI_PRE": 0.05,
            "NTN_B_REAL": -0.12,
        },
        historical_period="Oct 2022 - Nov 2022",
    ),
]


# ---------------------------------------------------------------------------
# StressTester class
# ---------------------------------------------------------------------------


def _find_shock(instrument: str, shocks: dict[str, float]) -> float | None:
    """Look up shock for an instrument: exact match first, then prefix match.

    For DI-related positions, ``DI_PRE_365`` matches the ``DI_PRE`` shock
    if no exact match exists.

    Returns:
        The shock percentage, or None if no match found.
    """
    # Exact match
    if instrument in shocks:
        return shocks[instrument]

    # Prefix match (e.g., DI_PRE_365 matches DI_PRE)
    for shock_key, shock_val in shocks.items():
        if instrument.startswith(shock_key):
            return shock_val

    return None


class StressTester:
    """Runs historical stress scenarios against portfolio positions.

    Stress tests are advisory only -- they report results but do not
    trigger any position changes (locked decision from CONTEXT.md).

    Args:
        scenarios: List of stress scenarios. Defaults to DEFAULT_SCENARIOS.
    """

    def __init__(
        self,
        scenarios: list[StressScenario] | None = None,
    ) -> None:
        self.scenarios = scenarios if scenarios is not None else list(DEFAULT_SCENARIOS)

    def run_scenario(
        self,
        positions: dict[str, float],
        scenario: StressScenario,
        portfolio_value: float | None = None,
    ) -> StressResult:
        """Apply a single stress scenario to the portfolio.

        Args:
            positions: Mapping of instrument_id -> notional value.
            scenario: The stress scenario to apply.
            portfolio_value: Total portfolio value for percentage computation.
                If None, uses sum of absolute position notionals as approximation.

        Returns:
            StressResult with position-level and portfolio-level P&L.
        """
        position_pnl: dict[str, float] = {}
        impacted = 0
        unaffected = 0

        for instrument, notional in positions.items():
            shock = _find_shock(instrument, scenario.shocks)
            if shock is not None:
                pnl = notional * shock
                position_pnl[instrument] = pnl
                impacted += 1
            else:
                position_pnl[instrument] = 0.0
                unaffected += 1

        total_positions = impacted + unaffected
        if total_positions > 0 and unaffected / total_positions > 0.5:
            logger.warning(
                "stress_test_low_coverage",
                scenario=scenario.name,
                positions_unaffected=unaffected,
                total_positions=total_positions,
                pct_unaffected=round(unaffected / total_positions * 100, 1),
            )

        portfolio_pnl = sum(position_pnl.values())

        # Portfolio P&L percentage
        if portfolio_value is not None and abs(portfolio_value) > 1e-12:
            portfolio_pnl_pct = portfolio_pnl / portfolio_value
        else:
            abs_notional = sum(abs(v) for v in positions.values())
            if abs_notional > 1e-12:
                portfolio_pnl_pct = portfolio_pnl / abs_notional
            else:
                portfolio_pnl_pct = 0.0

        # Identify worst position (most negative P&L)
        if position_pnl:
            worst_instrument = min(position_pnl, key=position_pnl.get)  # type: ignore[arg-type]
            worst_pnl = position_pnl[worst_instrument]
        else:
            worst_instrument = ""
            worst_pnl = 0.0

        return StressResult(
            scenario_name=scenario.name,
            portfolio_pnl=portfolio_pnl,
            portfolio_pnl_pct=portfolio_pnl_pct,
            position_pnl=position_pnl,
            worst_position=worst_instrument,
            worst_position_pnl=worst_pnl,
            positions_impacted=impacted,
            positions_unaffected=unaffected,
        )

    def run_all(
        self,
        positions: dict[str, float],
        portfolio_value: float | None = None,
    ) -> list[StressResult]:
        """Run all configured scenarios against the portfolio.

        Args:
            positions: Mapping of instrument_id -> notional value.
            portfolio_value: Total portfolio value for percentage computation.

        Returns:
            List of StressResult, one per scenario.
        """
        return [
            self.run_scenario(positions, scenario, portfolio_value)
            for scenario in self.scenarios
        ]

    def worst_case(self, results: list[StressResult]) -> StressResult:
        """Return the scenario with the most negative portfolio P&L.

        Args:
            results: List of StressResult from run_all().

        Returns:
            StressResult with the worst portfolio P&L.

        Raises:
            ValueError: If results list is empty.
        """
        if not results:
            raise ValueError("Cannot determine worst case from empty results list")
        return min(results, key=lambda r: r.portfolio_pnl)

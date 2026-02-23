"""Historical stress scenario replay engine.

Defines 6 historical crisis scenarios (Taper Tantrum 2013, BR Crisis 2015,
COVID 2020, Rate Shock 2022, BR Fiscal Crisis, Global Risk-Off) and applies
their shocks to current portfolio positions to estimate position-level and
portfolio-level P&L impact.

Enhanced with reverse stress testing (find scenarios producing a target max
loss) and historical replay (apply actual daily returns from a crisis period).

Stress tests are advisory only -- they report results but do not
trigger position changes. All functions are pure computation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
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
    StressScenario(
        name="BR Fiscal Crisis (Teto de Gastos)",
        description=(
            "Fiscal ceiling crisis with spending cap breach fears. BRL weakened, "
            "DI rates surged, NTN-B sold off, sovereign risk repriced. "
            "Calibrated to 2015 crisis magnitude."
        ),
        shocks={
            "USDBRL": 0.25,
            "DI_PRE": 0.035,
            "NTN_B_REAL": -0.10,
            "IBOVESPA": -0.18,
            "CDS_BR": 0.40,
        },
        historical_period="Sep 2015 - Mar 2016",
    ),
    StressScenario(
        name="Global Risk-Off (Geopolitical)",
        description=(
            "Global risk-off event with flight to quality. EM currencies weakened, "
            "equities dropped, oil declined, USD strengthened, UST rallied. "
            "Calibrated to 2020 COVID shock magnitude."
        ),
        shocks={
            "USDBRL": 0.20,
            "DI_PRE": 0.015,
            "IBOVESPA": -0.30,
            "SP500": -0.25,
            "OIL": -0.40,
            "UST_NOM": -0.005,
            "CDS_BR": 0.30,
        },
        historical_period="Feb 2020 - Mar 2020",
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

    def reverse_stress_test(
        self,
        positions: dict[str, float],
        portfolio_value: float,
        max_loss_pct: float = -0.10,
        step_size: float = 0.01,
        max_iterations: int = 100,
    ) -> dict[str, dict]:
        """Find shock multipliers that produce exactly ``max_loss_pct`` portfolio loss.

        For each configured scenario, runs a binary search over multipliers
        (between 0.01 and 5.0) to find the multiplier *k* such that::

            sum(position_i * shock_i * k) / portfolio_value == max_loss_pct

        Args:
            positions: Mapping of instrument_id -> notional value.
            portfolio_value: Total portfolio value for percentage computation.
            max_loss_pct: Target loss as a negative fraction (e.g., -0.10 = -10%).
            step_size: Unused (kept for API compatibility). Binary search is used.
            max_iterations: Maximum binary search iterations per scenario.

        Returns:
            Dict keyed by scenario name, each value a dict with:
            - ``multiplier``: The multiplier that produces the target loss.
            - ``required_shocks``: Shock magnitudes at that multiplier.
            - ``resulting_loss_pct``: Actual loss percentage achieved.
            - ``feasible``: Whether the target loss is achievable within 5x.
        """
        target_pnl = max_loss_pct * portfolio_value  # negative number

        results: dict[str, dict] = {}

        for scenario in self.scenarios:
            # Compute base P&L at 1x multiplier for this scenario's shocks
            base_pnl = 0.0
            exposed_instruments: list[str] = []
            for instrument, notional in positions.items():
                shock = _find_shock(instrument, scenario.shocks)
                if shock is not None:
                    base_pnl += notional * shock
                    exposed_instruments.append(instrument)

            # If no exposure at all, mark infeasible
            if abs(base_pnl) < 1e-12 or not exposed_instruments:
                results[scenario.name] = {
                    "multiplier": 0.0,
                    "required_shocks": {},
                    "resulting_loss_pct": 0.0,
                    "feasible": False,
                }
                continue

            # If base P&L is positive (scenario helps portfolio), scenario
            # can never produce a loss -- infeasible
            if base_pnl >= 0.0 and target_pnl < 0.0:
                results[scenario.name] = {
                    "multiplier": 0.0,
                    "required_shocks": {},
                    "resulting_loss_pct": 0.0,
                    "feasible": False,
                }
                continue

            # Binary search for multiplier k such that base_pnl * k == target_pnl
            lo, hi = 0.01, 5.0

            # Check if 5x multiplier can reach the target
            pnl_at_max = base_pnl * hi
            if base_pnl < 0.0 and pnl_at_max > target_pnl:
                # Cannot reach target even at max multiplier
                results[scenario.name] = {
                    "multiplier": hi,
                    "required_shocks": {
                        k: v * hi for k, v in scenario.shocks.items()
                    },
                    "resulting_loss_pct": pnl_at_max / portfolio_value,
                    "feasible": False,
                }
                continue

            for _ in range(max_iterations):
                mid = (lo + hi) / 2.0
                pnl_mid = base_pnl * mid

                if abs(pnl_mid - target_pnl) / abs(portfolio_value) < 1e-6:
                    break

                if base_pnl < 0.0:
                    # base_pnl is negative, so pnl_mid becomes more negative as mid increases
                    if pnl_mid > target_pnl:
                        lo = mid  # Need more loss -> increase multiplier
                    else:
                        hi = mid  # Overshot -> decrease multiplier
                else:
                    # base_pnl is positive (unusual), pnl_mid becomes more positive
                    if pnl_mid < target_pnl:
                        lo = mid
                    else:
                        hi = mid

            final_multiplier = (lo + hi) / 2.0
            final_pnl = base_pnl * final_multiplier

            results[scenario.name] = {
                "multiplier": round(final_multiplier, 6),
                "required_shocks": {
                    k: round(v * final_multiplier, 6)
                    for k, v in scenario.shocks.items()
                },
                "resulting_loss_pct": round(final_pnl / portfolio_value, 6),
                "feasible": True,
            }

        return results

    def historical_replay(
        self,
        positions: dict[str, float],
        historical_returns: dict[str, np.ndarray],
        portfolio_value: float,
        period_name: str = "Custom Period",
    ) -> StressResult:
        """Replay actual historical daily returns through current positions.

        Computes cumulative P&L by applying daily returns to notional positions
        day by day, then reports the worst cumulative drawdown during the period.

        Args:
            positions: Mapping of instrument_id -> notional value.
            historical_returns: Mapping of instrument_id -> 1-D array of daily
                returns for the crisis period (e.g., 20-30 trading days).
            portfolio_value: Total portfolio value for percentage computation.
            period_name: Human-readable label for the replay period.

        Returns:
            StressResult where ``portfolio_pnl`` is the worst cumulative
            drawdown P&L and ``position_pnl`` shows per-instrument cumulative
            contribution at the worst point.
        """
        # Determine number of days from the longest return series
        n_days = max(
            (len(arr) for arr in historical_returns.values()),
            default=0,
        )

        if n_days == 0:
            return StressResult(
                scenario_name=f"Historical Replay: {period_name}",
                portfolio_pnl=0.0,
                portfolio_pnl_pct=0.0,
                position_pnl={inst: 0.0 for inst in positions},
                worst_position="",
                worst_position_pnl=0.0,
                positions_impacted=0,
                positions_unaffected=len(positions),
            )

        # Track cumulative P&L per instrument and total per day
        cum_pnl_by_instrument: dict[str, np.ndarray] = {}
        impacted = 0
        unaffected = 0

        for instrument, notional in positions.items():
            if instrument in historical_returns:
                daily_rets = np.asarray(historical_returns[instrument], dtype=np.float64)
                # Pad shorter series with zeros
                if len(daily_rets) < n_days:
                    padded = np.zeros(n_days)
                    padded[: len(daily_rets)] = daily_rets
                    daily_rets = padded
                cum_pnl_by_instrument[instrument] = np.cumsum(notional * daily_rets)
                impacted += 1
            else:
                cum_pnl_by_instrument[instrument] = np.zeros(n_days)
                unaffected += 1

        # Total cumulative P&L per day
        total_cum_pnl = np.zeros(n_days)
        for arr in cum_pnl_by_instrument.values():
            total_cum_pnl += arr

        # Worst drawdown point (most negative cumulative P&L)
        worst_day_idx = int(np.argmin(total_cum_pnl))
        worst_pnl = float(total_cum_pnl[worst_day_idx])

        # Per-instrument P&L at the worst day
        position_pnl = {
            inst: float(arr[worst_day_idx])
            for inst, arr in cum_pnl_by_instrument.items()
        }

        # Identify worst position at that day
        if position_pnl:
            worst_instrument = min(position_pnl, key=position_pnl.get)  # type: ignore[arg-type]
            worst_position_pnl = position_pnl[worst_instrument]
        else:
            worst_instrument = ""
            worst_position_pnl = 0.0

        pnl_pct = worst_pnl / portfolio_value if abs(portfolio_value) > 1e-12 else 0.0

        return StressResult(
            scenario_name=f"Historical Replay: {period_name}",
            portfolio_pnl=worst_pnl,
            portfolio_pnl_pct=pnl_pct,
            position_pnl=position_pnl,
            worst_position=worst_instrument,
            worst_position_pnl=worst_position_pnl,
            positions_impacted=impacted,
            positions_unaffected=unaffected,
        )

    def run_all_v2(
        self,
        positions: dict[str, float],
        portfolio_value: float,
        include_reverse: bool = True,
        max_loss_pct: float = -0.10,
    ) -> dict[str, object]:
        """Run all scenarios, optionally reverse stress test, and identify worst case.

        Convenience method combining ``run_all()``, ``reverse_stress_test()``,
        and ``worst_case()`` into a single call.

        Args:
            positions: Mapping of instrument_id -> notional value.
            portfolio_value: Total portfolio value.
            include_reverse: Whether to include reverse stress test results.
            max_loss_pct: Target loss for reverse stress testing.

        Returns:
            Dict with keys:
            - ``scenarios``: list[StressResult] from run_all().
            - ``reverse``: reverse stress test results (or None).
            - ``worst_case``: StressResult with worst portfolio P&L.
        """
        scenario_results = self.run_all(positions, portfolio_value)

        reverse_results = None
        if include_reverse:
            reverse_results = self.reverse_stress_test(
                positions, portfolio_value, max_loss_pct=max_loss_pct
            )

        worst = self.worst_case(scenario_results) if scenario_results else None

        return {
            "scenarios": scenario_results,
            "reverse": reverse_results,
            "worst_case": worst,
        }

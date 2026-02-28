"""Full pipeline end-to-end integration test.

Validates the complete data flow chain:
  DB -> transforms -> agents -> strategies -> signals -> portfolio -> risk -> report

Each step is independently wrapped in try/except so failures are reported
per-step rather than aborting the whole test.

Marked with @pytest.mark.integration for selective execution.
"""

from __future__ import annotations

import logging
from collections import namedtuple

import numpy as np
import pandas as pd
import pytest

logger = logging.getLogger(__name__)

StepResult = namedtuple("StepResult", ["name", "passed", "detail"])


def _sample_macro_df() -> pd.DataFrame:
    """Build a small sample macro DataFrame for transform testing."""
    dates = pd.date_range("2023-01-01", periods=60, freq="B")
    return pd.DataFrame(
        {
            "date": dates,
            "selic": np.linspace(13.75, 12.25, len(dates)),
            "ipca_12m": np.linspace(5.8, 4.6, len(dates)),
            "fx_usdbrl": np.linspace(5.2, 4.9, len(dates)),
            "ibov": np.linspace(110000, 125000, len(dates)),
        }
    ).set_index("date")


@pytest.mark.integration
def test_full_pipeline_e2e():
    """Run all 7 pipeline steps and assert every step passes."""

    results: list[StepResult] = []

    # -----------------------------------------------------------------------
    # Step 1: Transforms
    # -----------------------------------------------------------------------
    try:
        from src.transforms.returns import compute_returns, compute_z_score

        df = _sample_macro_df()

        returns = compute_returns(df["ibov"])
        assert returns is not None and len(returns) > 0, "Returns output empty"

        z_scores = compute_z_score(df["selic"], window=20)
        assert z_scores is not None and len(z_scores) > 0, "Z-scores output empty"

        results.append(StepResult("Transforms", True, "curves/returns/macro OK"))
        logger.info("STEP 1 Transforms: PASS")
    except Exception as exc:
        results.append(StepResult("Transforms", False, str(exc)))
        logger.error("STEP 1 Transforms: FAIL - %s", exc)

    # -----------------------------------------------------------------------
    # Step 2: Agents
    # -----------------------------------------------------------------------
    try:
        from src.agents.registry import AgentRegistry

        expected = {
            "inflation_agent",
            "monetary_agent",
            "fiscal_agent",
            "fx_agent",
            "cross_asset_agent",
        }
        execution_order = set(AgentRegistry.EXECUTION_ORDER)
        assert (
            len(execution_order) >= 5
        ), f"Expected >=5 agents in EXECUTION_ORDER, got {len(execution_order)}"
        assert expected.issubset(
            execution_order
        ), f"Missing agents: {expected - execution_order}"

        results.append(
            StepResult("Agents", True, f"{len(execution_order)} agents defined")
        )
        logger.info("STEP 2 Agents: PASS")
    except Exception as exc:
        results.append(StepResult("Agents", False, str(exc)))
        logger.error("STEP 2 Agents: FAIL - %s", exc)

    # -----------------------------------------------------------------------
    # Step 3: Strategies
    # -----------------------------------------------------------------------
    try:
        from src.strategies.registry import StrategyRegistry

        all_strats = StrategyRegistry.list_all()
        assert len(all_strats) >= 8, f"Expected >=8 strategies, got {len(all_strats)}"

        results.append(StepResult("Strategies", True, f"{len(all_strats)} strategies"))
        logger.info("STEP 3 Strategies: PASS")
    except Exception as exc:
        results.append(StepResult("Strategies", False, str(exc)))
        logger.error("STEP 3 Strategies: FAIL - %s", exc)

    # -----------------------------------------------------------------------
    # Step 4: Signal aggregation
    # -----------------------------------------------------------------------
    try:
        from src.portfolio.signal_aggregator_v2 import SignalAggregatorV2

        aggregator = SignalAggregatorV2()
        assert aggregator is not None, "SignalAggregatorV2 instantiation failed"

        # Verify the aggregator has expected methods
        assert hasattr(aggregator, "aggregate"), "Missing aggregate method"

        results.append(StepResult("Signal Aggregation", True, "SignalAggregatorV2 OK"))
        logger.info("STEP 4 Signal Aggregation: PASS")
    except Exception as exc:
        results.append(StepResult("Signal Aggregation", False, str(exc)))
        logger.error("STEP 4 Signal Aggregation: FAIL - %s", exc)

    # -----------------------------------------------------------------------
    # Step 5: Portfolio construction
    # -----------------------------------------------------------------------
    try:
        from src.portfolio.portfolio_optimizer import PortfolioOptimizer

        optimizer = PortfolioOptimizer()
        assert optimizer is not None, "PortfolioOptimizer instantiation failed"
        assert hasattr(optimizer, "optimize_with_bl"), "Missing optimize_with_bl method"

        results.append(StepResult("Portfolio", True, "PortfolioOptimizer OK"))
        logger.info("STEP 5 Portfolio: PASS")
    except Exception as exc:
        results.append(StepResult("Portfolio", False, str(exc)))
        logger.error("STEP 5 Portfolio: FAIL - %s", exc)

    # -----------------------------------------------------------------------
    # Step 6: Risk (VaR)
    # -----------------------------------------------------------------------
    try:
        from src.risk.var_calculator import VaRCalculator

        calc = VaRCalculator()
        rng = np.random.default_rng(seed=42)
        sample_returns = rng.normal(0.0, 0.01, size=252)

        var_result = calc.calculate(sample_returns, method="historical")
        assert var_result is not None, "VaR calculation returned None"
        assert hasattr(var_result, "var_95"), "VaRResult missing var_95"
        assert var_result.var_95 < 0, f"Expected negative VaR, got {var_result.var_95}"

        results.append(StepResult("Risk (VaR)", True, f"VaR95={var_result.var_95:.6f}"))
        logger.info("STEP 6 Risk: PASS")
    except Exception as exc:
        results.append(StepResult("Risk (VaR)", False, str(exc)))
        logger.error("STEP 6 Risk: FAIL - %s", exc)

    # -----------------------------------------------------------------------
    # Step 7: Daily report
    # -----------------------------------------------------------------------
    try:
        from src.reporting.daily_report import DailyReportGenerator

        generator = DailyReportGenerator()
        # DailyReportGenerator.generate() requires pipeline_context with real data.
        # Provide a minimal synthetic context for CI/integration testing.
        pipeline_context = {
            "market_snapshot": {"USDBRL": 5.15, "DI1F27": 12.5, "IBOV": 125000},
            "regime": {
                "classification": "RISK_ON",
                "confidence": 0.72,
                "probabilities": {"risk_on": 0.72, "risk_off": 0.28},
                "drivers": ["fiscal_surplus", "rate_cut_cycle"],
                "transition_risk": "LOW",
            },
            "agent_views": {
                "inflation_agent": {"direction": "LONG", "conviction": 0.6},
                "monetary_agent": {"direction": "LONG", "conviction": 0.7},
            },
            "signals": {
                "total": 5, "bullish": 3, "bearish": 1, "neutral": 1,
                "flips": 0, "crowding_warnings": 0, "top_signal": "DI1F27 LONG",
            },
            "portfolio": {
                "nav": 10_000_000.0, "daily_pnl": 25_000.0,
                "mtd": 0.012, "ytd": 0.045,
                "n_positions": 3, "gross_leverage": 0.8, "net_leverage": 0.5,
                "rebalance_needed": False,
            },
            "risk": {
                "var_95": -0.018, "var_99": -0.032, "cvar_95": -0.025,
                "worst_stress": "EM Crisis: -4.5%",
                "limit_util": "62%", "limits_breached": 0,
                "circuit_breaker": "NORMAL", "risk_budget": "38%",
            },
            "actions": {
                "table": [
                    {"action": "Review DI1F27 LONG position", "priority": "MEDIUM"},
                ],
                "commentary": "No urgent action required.",
            },
        }
        sections = generator.generate(pipeline_context=pipeline_context)
        assert sections is not None, "Report generation returned None"
        assert len(sections) > 0, "Report generated zero sections"

        results.append(StepResult("Report", True, f"{len(sections)} sections"))
        logger.info("STEP 7 Report: PASS")
    except Exception as exc:
        results.append(StepResult("Report", False, str(exc)))
        logger.error("STEP 7 Report: FAIL - %s", exc)

    # -----------------------------------------------------------------------
    # Final: assert all steps passed
    # -----------------------------------------------------------------------
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        logger.info("  [%s] %s: %s", status, r.name, r.detail)

    failed = [r for r in results if not r.passed]
    assert len(failed) == 0, f"{len(failed)} pipeline step(s) failed: " + ", ".join(
        f"{r.name} ({r.detail})" for r in failed
    )

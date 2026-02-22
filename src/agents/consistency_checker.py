"""Cross-asset consistency checker.

Detects contradictions between agent signals and strategy signals,
flagging them as ConsistencyIssue objects with a 0.5x sizing penalty
on affected instruments.

Rules are defined as extensible dicts with callable check functions.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from src.agents.cross_asset_view import ConsistencyIssue

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: extract signal direction from various signal formats
# ---------------------------------------------------------------------------
def _get_direction(signals: dict[str, Any], key: str) -> str | None:
    """Extract direction string from a signals dict.

    Handles both dict-style signals ({"direction": "LONG"}) and
    objects with a .direction attribute.

    Args:
        signals: Dict mapping signal keys to signal values.
        key: The signal key to look up.

    Returns:
        Direction string ("LONG", "SHORT", "NEUTRAL") or None.
    """
    val = signals.get(key)
    if val is None:
        return None
    if isinstance(val, dict):
        d = val.get("direction")
        return d if isinstance(d, str) else None
    if hasattr(val, "direction"):
        d = val.direction
        return d.value if hasattr(d, "value") else str(d)
    return None


def _get_value(signals: dict[str, Any], key: str) -> float | None:
    """Extract numeric value from a signals dict.

    Args:
        signals: Dict mapping signal keys to signal values.
        key: The signal key to look up.

    Returns:
        Float value or None.
    """
    val = signals.get(key)
    if val is None:
        return None
    if isinstance(val, dict):
        v = val.get("value")
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                return None
        return None
    if hasattr(val, "value"):
        try:
            return float(val.value)
        except (TypeError, ValueError):
            return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Rule check functions
# ---------------------------------------------------------------------------
def _check_fx_rates_contradiction(
    agent_signals: dict, strategy_signals: dict, regime: str
) -> ConsistencyIssue | None:
    """FX bullish BRL (SHORT USDBRL) + rates higher (SHORT DI) = inconsistent.

    Logic: if you expect BRL to strengthen (good macro), you would not
    simultaneously expect rates to rise (hawkish BCB).
    """
    fx_dir = _get_direction(strategy_signals, "USDBRL") or _get_direction(
        agent_signals, "FX_USDBRL"
    )
    rates_dir = _get_direction(strategy_signals, "DI_PRE") or _get_direction(
        agent_signals, "DI"
    )

    if fx_dir == "SHORT" and rates_dir == "SHORT":
        return ConsistencyIssue(
            rule_id="FX_RATES_CONTRADICTION",
            description=(
                "FX bullish BRL (SHORT USDBRL) contradicts hawkish rates (SHORT DI). "
                "Bullish BRL implies favorable macro, which would suggest rate cuts."
            ),
            affected_instruments=("USDBRL", "DI_PRE"),
            severity="warning",
            sizing_penalty=0.5,
        )
    return None


def _check_equity_rates_contradiction(
    agent_signals: dict, strategy_signals: dict, regime: str
) -> ConsistencyIssue | None:
    """LONG equities + SHORT DI aggressively = inconsistent (risk-on + hawkish)."""
    equity_dir = _get_direction(strategy_signals, "IBOV_FUT") or _get_direction(
        agent_signals, "IBOVESPA"
    )
    rates_dir = _get_direction(strategy_signals, "DI_PRE") or _get_direction(
        agent_signals, "DI"
    )

    if equity_dir == "LONG" and rates_dir == "SHORT":
        return ConsistencyIssue(
            rule_id="EQUITY_RATES_CONTRADICTION",
            description=(
                "LONG equities (risk-on) contradicts aggressively SHORT DI (hawkish rates). "
                "Higher rates typically pressure equity valuations."
            ),
            affected_instruments=("IBOV_FUT", "DI_PRE"),
            severity="warning",
            sizing_penalty=0.5,
        )
    return None


def _check_regime_fx_mismatch(
    agent_signals: dict, strategy_signals: dict, regime: str
) -> ConsistencyIssue | None:
    """Stagflation regime + SHORT USDBRL = inconsistent."""
    if regime != "Stagflation":
        return None

    fx_dir = _get_direction(strategy_signals, "USDBRL") or _get_direction(
        agent_signals, "FX_USDBRL"
    )

    if fx_dir == "SHORT":
        return ConsistencyIssue(
            rule_id="REGIME_FX_MISMATCH",
            description=(
                "Stagflation regime contradicts bullish BRL (SHORT USDBRL). "
                "Stagflation typically weakens EM currencies."
            ),
            affected_instruments=("USDBRL",),
            severity="warning",
            sizing_penalty=0.5,
        )
    return None


def _check_regime_equity_mismatch(
    agent_signals: dict, strategy_signals: dict, regime: str
) -> ConsistencyIssue | None:
    """Stagflation/Deflation regime + LONG equities = inconsistent."""
    if regime not in ("Stagflation", "Deflation"):
        return None

    equity_dir = _get_direction(strategy_signals, "IBOV_FUT") or _get_direction(
        agent_signals, "IBOVESPA"
    )

    if equity_dir == "LONG":
        return ConsistencyIssue(
            rule_id="REGIME_EQUITY_MISMATCH",
            description=(
                f"{regime} regime contradicts LONG equities. "
                f"{regime} is unfavorable for equity risk exposure."
            ),
            affected_instruments=("IBOV_FUT",),
            severity="warning",
            sizing_penalty=0.5,
        )
    return None


def _check_inflation_rates_contradiction(
    agent_signals: dict, strategy_signals: dict, regime: str
) -> ConsistencyIssue | None:
    """High inflation signal + LONG DI (receive) = inconsistent."""
    inflation_dir = _get_direction(agent_signals, "INFLATION_BR") or _get_direction(
        agent_signals, "INFLATION"
    )
    rates_dir = _get_direction(strategy_signals, "DI_PRE") or _get_direction(
        agent_signals, "DI"
    )

    # HIGH inflation = SHORT direction in our convention (SHORT = rates go up)
    # LONG DI = receive rates = expect rates to fall
    if inflation_dir == "SHORT" and rates_dir == "LONG":
        return ConsistencyIssue(
            rule_id="INFLATION_RATES_CONTRADICTION",
            description=(
                "High inflation signal contradicts receiving rates (LONG DI). "
                "High inflation should push rates higher, not lower."
            ),
            affected_instruments=("DI_PRE",),
            severity="warning",
            sizing_penalty=0.5,
        )
    return None


def _check_risk_appetite_direction(
    agent_signals: dict, strategy_signals: dict, regime: str
) -> ConsistencyIssue | None:
    """Risk appetite < 30 (fear) + LONG risk assets = inconsistent."""
    sentiment_val = _get_value(agent_signals, "CROSSASSET_SENTIMENT")
    if sentiment_val is None or sentiment_val >= 30:
        return None

    # Check for LONG risk assets
    risk_assets = ["IBOV_FUT", "IBOVESPA"]
    for asset in risk_assets:
        asset_dir = _get_direction(strategy_signals, asset) or _get_direction(
            agent_signals, asset
        )
        if asset_dir == "LONG":
            return ConsistencyIssue(
                rule_id="RISK_APPETITE_DIRECTION",
                description=(
                    f"Risk appetite score {sentiment_val:.0f} (fear) contradicts "
                    f"LONG {asset}. Low risk appetite suggests reducing risk exposure."
                ),
                affected_instruments=(asset,),
                severity="warning",
                sizing_penalty=0.5,
            )
    return None


def _check_sovereign_fx_divergence(
    agent_signals: dict, strategy_signals: dict, regime: str
) -> ConsistencyIssue | None:
    """Positive sovereign risk + SHORT USDBRL = inconsistent.

    Positive sovereign risk (CDS widening) = bearish BRL, so SHORT USDBRL
    (bullish BRL) is contradictory.
    """
    sov_dir = _get_direction(agent_signals, "SOVEREIGN_RISK") or _get_direction(
        agent_signals, "SOV"
    )
    fx_dir = _get_direction(strategy_signals, "USDBRL") or _get_direction(
        agent_signals, "FX_USDBRL"
    )

    # SHORT sovereign = elevated risk; SHORT USDBRL = bullish BRL
    if sov_dir == "SHORT" and fx_dir == "SHORT":
        return ConsistencyIssue(
            rule_id="SOVEREIGN_FX_DIVERGENCE",
            description=(
                "Elevated sovereign risk contradicts bullish BRL (SHORT USDBRL). "
                "Rising sovereign spreads typically weaken the local currency."
            ),
            affected_instruments=("USDBRL",),
            severity="warning",
            sizing_penalty=0.5,
        )
    return None


# ---------------------------------------------------------------------------
# CrossAssetConsistencyChecker
# ---------------------------------------------------------------------------
class CrossAssetConsistencyChecker:
    """Checks agent and strategy signals for cross-asset contradictions.

    Rules are defined as dicts with check_fn callables. Each rule returns
    a ConsistencyIssue or None.

    Usage::

        checker = CrossAssetConsistencyChecker()
        issues = checker.check(agent_signals, strategy_signals, regime)
    """

    RULES: list[dict[str, Any]] = [
        {
            "rule_id": "FX_RATES_CONTRADICTION",
            "description": "FX bullish BRL + hawkish rates",
            "check_fn": _check_fx_rates_contradiction,
            "affected_instruments": ["USDBRL", "DI_PRE"],
            "severity": "warning",
        },
        {
            "rule_id": "EQUITY_RATES_CONTRADICTION",
            "description": "LONG equities + SHORT DI aggressively",
            "check_fn": _check_equity_rates_contradiction,
            "affected_instruments": ["IBOV_FUT", "DI_PRE"],
            "severity": "warning",
        },
        {
            "rule_id": "REGIME_FX_MISMATCH",
            "description": "Stagflation regime + SHORT USDBRL",
            "check_fn": _check_regime_fx_mismatch,
            "affected_instruments": ["USDBRL"],
            "severity": "warning",
        },
        {
            "rule_id": "REGIME_EQUITY_MISMATCH",
            "description": "Stagflation/Deflation + LONG equities",
            "check_fn": _check_regime_equity_mismatch,
            "affected_instruments": ["IBOV_FUT"],
            "severity": "warning",
        },
        {
            "rule_id": "INFLATION_RATES_CONTRADICTION",
            "description": "High inflation + receiving rates",
            "check_fn": _check_inflation_rates_contradiction,
            "affected_instruments": ["DI_PRE"],
            "severity": "warning",
        },
        {
            "rule_id": "RISK_APPETITE_DIRECTION",
            "description": "Fear regime + LONG risk assets",
            "check_fn": _check_risk_appetite_direction,
            "affected_instruments": ["IBOV_FUT"],
            "severity": "warning",
        },
        {
            "rule_id": "SOVEREIGN_FX_DIVERGENCE",
            "description": "Positive sovereign risk + SHORT USDBRL",
            "check_fn": _check_sovereign_fx_divergence,
            "affected_instruments": ["USDBRL"],
            "severity": "warning",
        },
    ]

    def check(
        self,
        agent_signals: dict[str, Any],
        strategy_signals: dict[str, Any],
        regime: str,
    ) -> list[ConsistencyIssue]:
        """Run all consistency rules against current signals.

        Args:
            agent_signals: Dict mapping signal_id to signal object/dict.
            strategy_signals: Dict mapping instrument to signal object/dict.
            regime: Current regime classification string.

        Returns:
            List of ConsistencyIssue objects for triggered rules.
        """
        issues: list[ConsistencyIssue] = []

        for rule in self.RULES:
            try:
                check_fn = rule["check_fn"]
                result = check_fn(agent_signals, strategy_signals, regime)
                if result is not None:
                    issues.append(result)
            except Exception as exc:
                logger.warning(
                    "Consistency rule %s failed: %s",
                    rule.get("rule_id", "unknown"),
                    exc,
                )

        return issues

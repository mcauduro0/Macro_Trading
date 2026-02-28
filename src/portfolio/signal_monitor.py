"""Signal monitoring for anomaly detection and daily reporting.

SignalMonitor tracks aggregated signals over time and detects:
- Signal flips: Any sign change in conviction between periods
- Conviction surges: Absolute conviction jump > 0.3 (configurable)
- Strategy divergence: Pairwise disagreement > 0.5 within asset class

Also generates comprehensive daily summaries grouped by asset class with
regime context and all triggered alerts.

This module is pure computation -- no database or I/O access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import structlog

from src.core.enums import SignalDirection
from src.portfolio.signal_aggregator_v2 import AggregatedSignalV2
from src.strategies.base import StrategySignal

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Strategy prefix -> asset class mapping
# ---------------------------------------------------------------------------
_STRATEGY_ASSET_CLASS_MAP: dict[str, str] = {
    "RATES_": "FIXED_INCOME",
    "CUPOM_": "FIXED_INCOME",
    "INF_": "FIXED_INCOME",
    "SOV_": "FIXED_INCOME",
    "FX_": "FX",
    "EQ_": "EQUITY_INDEX",
    "EQUITY_": "EQUITY_INDEX",
    "COMM_": "COMMODITY",
    "COMMODITY_": "COMMODITY",
    "CROSS_": "CROSS_ASSET",
}


def _infer_asset_class(strategy_id: str) -> str:
    """Infer asset class from strategy_id prefix.

    Returns 'OTHER' if no known prefix matches.
    """
    upper = strategy_id.upper()
    for prefix, ac in _STRATEGY_ASSET_CLASS_MAP.items():
        if upper.startswith(prefix):
            return ac
    return "OTHER"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class SignalFlip:
    """Detected sign change in conviction between periods.

    Attributes:
        instrument: Target instrument.
        previous_direction: Direction before flip.
        current_direction: Direction after flip.
        previous_conviction: Conviction before flip.
        current_conviction: Conviction after flip.
        timestamp: When the flip was detected.
    """

    instrument: str
    previous_direction: SignalDirection
    current_direction: SignalDirection
    previous_conviction: float
    current_conviction: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ConvictionSurge:
    """Detected large jump in conviction magnitude.

    Attributes:
        instrument: Target instrument.
        previous_conviction: Conviction before surge.
        current_conviction: Conviction after surge.
        absolute_change: Absolute difference in conviction.
        timestamp: When the surge was detected.
    """

    instrument: str
    previous_conviction: float
    current_conviction: float
    absolute_change: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class StrategyDivergence:
    """Detected pairwise disagreement within an asset class.

    Attributes:
        asset_class: Asset class where divergence found.
        strategy_a: First strategy identifier.
        strategy_b: Second strategy identifier.
        conviction_a: Conviction of strategy A.
        conviction_b: Conviction of strategy B.
        divergence: Absolute difference in convictions.
        timestamp: When the divergence was detected.
    """

    asset_class: str
    strategy_a: str
    strategy_b: str
    conviction_a: float
    conviction_b: float
    divergence: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DailySignalSummary:
    """Comprehensive daily signal report.

    Attributes:
        date: Report date.
        active_signals: All non-zero conviction signals grouped by asset class.
        regime_context: Current regime name.
        flips: Detected signal flips.
        surges: Detected conviction surges.
        divergences: Detected strategy divergences.
        weekly_flip_count: Flips in last 7 calendar days.
        alert_count: Total alerts (flips + surges + divergences).
        summary_text: Formatted human-readable report.
    """

    date: date
    active_signals: list[dict] = field(default_factory=list)
    regime_context: str = "Unknown"
    flips: list[SignalFlip] = field(default_factory=list)
    surges: list[ConvictionSurge] = field(default_factory=list)
    divergences: list[StrategyDivergence] = field(default_factory=list)
    weekly_flip_count: int = 0
    alert_count: int = 0
    summary_text: str = ""


# ---------------------------------------------------------------------------
# SignalMonitor
# ---------------------------------------------------------------------------
class SignalMonitor:
    """Monitor aggregated signals for anomalies and generate daily reports.

    Detects signal flips (any sign change), conviction surges (>threshold
    absolute jump), and strategy divergence (>threshold within asset class).

    Args:
        surge_threshold: Minimum absolute conviction change to flag as surge.
        divergence_threshold: Minimum pairwise conviction difference within
            an asset class to flag as divergence.
    """

    def __init__(
        self,
        surge_threshold: float = 0.3,
        divergence_threshold: float = 0.5,
    ) -> None:
        self.surge_threshold = surge_threshold
        self.divergence_threshold = divergence_threshold

        # Internal state for tracking history
        self._signal_history: dict[str, list[tuple[datetime, float]]] = {}
        self._flip_history: list[SignalFlip] = []

    # ------------------------------------------------------------------
    # Flip detection
    # ------------------------------------------------------------------
    def check_signal_flips(
        self,
        previous: list[AggregatedSignalV2],
        current: list[AggregatedSignalV2],
    ) -> list[SignalFlip]:
        """Detect any sign change in conviction between previous and current.

        Matches signals by instrument. Any change from positive to negative
        or vice versa (including transitions through zero) is flagged.

        Args:
            previous: Previous period's aggregated signals.
            current: Current period's aggregated signals.

        Returns:
            List of detected SignalFlip objects.
        """
        prev_map: dict[str, AggregatedSignalV2] = {s.instrument: s for s in previous}

        flips: list[SignalFlip] = []
        for cur in current:
            prev = prev_map.get(cur.instrument)
            if prev is None:
                continue

            # Detect sign change: positive->negative, negative->positive,
            # positive->zero, negative->zero, zero->positive, zero->negative
            prev_sign = _sign(prev.conviction)
            cur_sign = _sign(cur.conviction)

            if prev_sign != cur_sign:
                flip = SignalFlip(
                    instrument=cur.instrument,
                    previous_direction=prev.direction,
                    current_direction=cur.direction,
                    previous_conviction=prev.conviction,
                    current_conviction=cur.conviction,
                    timestamp=cur.timestamp,
                )
                flips.append(flip)
                self._flip_history.append(flip)

                log.info(
                    "signal_flip_detected",
                    instrument=cur.instrument,
                    from_direction=prev.direction.value,
                    to_direction=cur.direction.value,
                )

        return flips

    # ------------------------------------------------------------------
    # Conviction surge detection
    # ------------------------------------------------------------------
    def check_conviction_surge(
        self,
        previous: list[AggregatedSignalV2],
        current: list[AggregatedSignalV2],
    ) -> list[ConvictionSurge]:
        """Detect large jumps in conviction magnitude.

        Flags when the absolute change in conviction exceeds surge_threshold.
        Pure magnitude check -- does not adapt to recent volatility.

        Args:
            previous: Previous period's aggregated signals.
            current: Current period's aggregated signals.

        Returns:
            List of detected ConvictionSurge objects.
        """
        prev_map: dict[str, AggregatedSignalV2] = {s.instrument: s for s in previous}

        surges: list[ConvictionSurge] = []
        for cur in current:
            prev = prev_map.get(cur.instrument)
            if prev is None:
                continue

            abs_change = abs(cur.conviction - prev.conviction)
            if abs_change > self.surge_threshold:
                surge = ConvictionSurge(
                    instrument=cur.instrument,
                    previous_conviction=prev.conviction,
                    current_conviction=cur.conviction,
                    absolute_change=abs_change,
                    timestamp=cur.timestamp,
                )
                surges.append(surge)

                log.info(
                    "conviction_surge_detected",
                    instrument=cur.instrument,
                    change=abs_change,
                    from_conviction=prev.conviction,
                    to_conviction=cur.conviction,
                )

        return surges

    # ------------------------------------------------------------------
    # Strategy divergence detection
    # ------------------------------------------------------------------
    def check_strategy_divergence(
        self,
        signals: list[StrategySignal],
    ) -> list[StrategyDivergence]:
        """Detect pairwise disagreement within asset classes.

        Groups strategy signals by asset class (inferred from strategy_id
        prefix), then checks all pairs within each class. Flags when any two
        strategies disagree by more than divergence_threshold.

        Args:
            signals: Raw StrategySignal objects from strategies.

        Returns:
            List of detected StrategyDivergence objects.
        """
        # Group by asset class
        ac_groups: dict[str, list[StrategySignal]] = {}
        for sig in signals:
            ac = _infer_asset_class(sig.strategy_id)
            ac_groups.setdefault(ac, []).append(sig)

        divergences: list[StrategyDivergence] = []
        now = datetime.utcnow()

        for ac, group in sorted(ac_groups.items()):
            # Deduplicate: use most recent signal per strategy_id
            strategy_signals: dict[str, StrategySignal] = {}
            for sig in group:
                existing = strategy_signals.get(sig.strategy_id)
                if existing is None or sig.timestamp > existing.timestamp:
                    strategy_signals[sig.strategy_id] = sig

            strategies = sorted(strategy_signals.keys())

            # Check all pairs
            for i in range(len(strategies)):
                for j in range(i + 1, len(strategies)):
                    sig_a = strategy_signals[strategies[i]]
                    sig_b = strategy_signals[strategies[j]]

                    # Use z_score / 2.0 clamped to [-1, +1] as conviction proxy
                    conv_a = max(-1.0, min(1.0, sig_a.z_score / 2.0))
                    conv_b = max(-1.0, min(1.0, sig_b.z_score / 2.0))

                    div = abs(conv_a - conv_b)
                    if div > self.divergence_threshold:
                        divergences.append(
                            StrategyDivergence(
                                asset_class=ac,
                                strategy_a=strategies[i],
                                strategy_b=strategies[j],
                                conviction_a=conv_a,
                                conviction_b=conv_b,
                                divergence=div,
                                timestamp=now,
                            )
                        )

                        log.info(
                            "strategy_divergence_detected",
                            asset_class=ac,
                            strategy_a=strategies[i],
                            strategy_b=strategies[j],
                            divergence=div,
                        )

        return divergences

    # ------------------------------------------------------------------
    # Daily summary
    # ------------------------------------------------------------------
    def generate_daily_summary(
        self,
        current_signals: list[AggregatedSignalV2],
        raw_signals: list[StrategySignal],
        regime: str = "Unknown",
        previous_signals: list[AggregatedSignalV2] | None = None,
    ) -> DailySignalSummary:
        """Generate comprehensive daily signal report.

        Includes all active signals grouped by asset class, regime context,
        and all triggered alerts. Runs flip and surge detection if previous
        signals provided; always runs divergence detection.

        Args:
            current_signals: Current aggregated signals.
            raw_signals: Raw strategy signals for divergence detection.
            regime: Current regime name.
            previous_signals: Previous period signals for flip/surge detection.

        Returns:
            DailySignalSummary with formatted text report.
        """
        today = date.today()

        # Detect flips and surges (if previous available)
        flips: list[SignalFlip] = []
        surges: list[ConvictionSurge] = []
        if previous_signals is not None:
            flips = self.check_signal_flips(previous_signals, current_signals)
            surges = self.check_conviction_surge(previous_signals, current_signals)

        # Always check divergence
        divergences = self.check_strategy_divergence(raw_signals)

        # Group active signals by asset class
        active_by_ac: dict[str, list[dict]] = {}
        for sig in current_signals:
            if abs(sig.conviction) > 0.001:  # Non-zero conviction
                ac = _infer_instrument_asset_class(sig)
                entry = {
                    "instrument": sig.instrument,
                    "conviction": sig.conviction,
                    "confidence": sig.confidence,
                    "direction": sig.direction.value,
                }
                active_by_ac.setdefault(ac, []).append(entry)

        active_signals = [
            {"asset_class": ac, "signals": sigs}
            for ac, sigs in sorted(active_by_ac.items())
        ]

        # Weekly flip count
        week_ago = datetime.utcnow() - timedelta(days=7)
        weekly_flip_count = sum(
            1 for f in self._flip_history if f.timestamp >= week_ago
        )

        alert_count = len(flips) + len(surges) + len(divergences)

        # Build summary text
        summary_text = self._format_summary_text(
            today,
            regime,
            active_by_ac,
            flips,
            surges,
            divergences,
            weekly_flip_count,
            alert_count,
        )

        return DailySignalSummary(
            date=today,
            active_signals=active_signals,
            regime_context=regime,
            flips=flips,
            surges=surges,
            divergences=divergences,
            weekly_flip_count=weekly_flip_count,
            alert_count=alert_count,
            summary_text=summary_text,
        )

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------
    @staticmethod
    def _format_summary_text(
        report_date: date,
        regime: str,
        active_by_ac: dict[str, list[dict]],
        flips: list[SignalFlip],
        surges: list[ConvictionSurge],
        divergences: list[StrategyDivergence],
        weekly_flip_count: int,
        alert_count: int,
    ) -> str:
        """Build a human-readable daily summary report."""
        total_signals = sum(len(sigs) for sigs in active_by_ac.values())

        lines: list[str] = [
            f"=== DAILY SIGNAL SUMMARY ({report_date.isoformat()}) ===",
            f"Regime: {regime}",
            f"Active Signals: {total_signals} | Alerts: {alert_count}",
            "",
        ]

        # Active signals by asset class
        for ac in sorted(active_by_ac.keys()):
            lines.append(f"{ac}:")
            for entry in active_by_ac[ac]:
                sign = "+" if entry["conviction"] >= 0 else ""
                lines.append(
                    f"  {entry['instrument']}: conviction={sign}{entry['conviction']:.2f}, "
                    f"confidence={entry['confidence']:.2f}, direction={entry['direction']}"
                )
            lines.append("")

        # Alerts section
        if alert_count > 0:
            lines.append("ALERTS:")
            for flip in flips:
                lines.append(
                    f"  [FLIP] {flip.instrument}: "
                    f"{flip.previous_direction.value} -> {flip.current_direction.value}"
                )
            for surge in surges:
                sign = (
                    "+"
                    if surge.current_conviction >= surge.previous_conviction
                    else "-"
                )
                lines.append(
                    f"  [SURGE] {surge.instrument}: conviction jumped "
                    f"{sign}{surge.absolute_change:.2f} "
                    f"(from {surge.previous_conviction:+.2f} to {surge.current_conviction:+.2f})"
                )
            for div in divergences:
                lines.append(
                    f"  [DIVERGENCE] {div.asset_class}: "
                    f"{div.strategy_a} ({div.conviction_a:+.2f}) vs "
                    f"{div.strategy_b} ({div.conviction_b:+.2f}) "
                    f"-- divergence {div.divergence:.2f}"
                )
            lines.append("")

        # Weekly flip count
        if weekly_flip_count > 0:
            lines.append(
                f"Weekly Flip Count: {weekly_flip_count} "
                "(unstable signals may need investigation)"
            )
        else:
            lines.append("Weekly Flip Count: 0")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------
def _sign(value: float) -> int:
    """Return sign of value: 1, -1, or 0."""
    if value > 0:
        return 1
    elif value < 0:
        return -1
    return 0


def _infer_instrument_asset_class(signal: AggregatedSignalV2) -> str:
    """Infer asset class from an aggregated signal's contributing strategies.

    Falls back to instrument prefix matching if no strategy info available.
    """
    if signal.contributing_strategies:
        # Use first contributing strategy's prefix
        first_strategy = signal.contributing_strategies[0].get("strategy_id", "")
        return _infer_asset_class(first_strategy)

    # Fallback: infer from instrument name
    upper = signal.instrument.upper()
    if any(upper.startswith(p) for p in ("DI_", "NTN_", "LTN_")):
        return "FIXED_INCOME"
    if any(upper.startswith(p) for p in ("USD", "EUR", "GBP")):
        return "FX"
    return "OTHER"

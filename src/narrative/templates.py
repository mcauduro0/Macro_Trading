"""Template-based fallback narrative generator.

Produces a structured data dump with ASCII tables when no LLM API key
is available.  Output is pure tables -- no prose, no filler words.
Fast and scannable per CONTEXT.md decision.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime


def render_template(
    agent_reports: dict,
    features: dict | None,
    as_of_date: date,
) -> str:
    """Render a structured macro brief from agent reports using tables only.

    Args:
        agent_reports: Mapping of agent_id -> AgentReport dataclass.
        features: Optional dict of additional feature data.
        as_of_date: Reference date for the brief header.

    Returns:
        Multi-section ASCII table string with signal data grouped by agent.
    """
    lines: list[str] = []
    date_str = as_of_date.isoformat()

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    lines.append(f"DAILY MACRO BRIEF -- {date_str}")
    lines.append("Source: Template (no LLM API key configured)")
    lines.append("=" * 55)
    lines.append("")

    # ------------------------------------------------------------------
    # Collect all signals grouped by agent
    # ------------------------------------------------------------------
    all_signals: list[dict] = []
    agent_signals: dict[str, list[dict]] = defaultdict(list)

    for agent_id, report in sorted(agent_reports.items()):
        for sig in report.signals:
            entry = {
                "signal_id": sig.signal_id,
                "agent_id": sig.agent_id,
                "direction": (
                    sig.direction.value
                    if hasattr(sig.direction, "value")
                    else str(sig.direction)
                ),
                "strength": (
                    sig.strength.value
                    if hasattr(sig.strength, "value")
                    else str(sig.strength)
                ),
                "confidence": sig.confidence,
                "value": sig.value,
            }
            all_signals.append(entry)
            agent_signals[agent_id].append(entry)

    # ------------------------------------------------------------------
    # Agent Signals table (grouped by agent)
    # ------------------------------------------------------------------
    lines.append("AGENT SIGNALS")

    if not all_signals:
        lines.append("  No signals available.")
        lines.append("")
    else:
        # Column widths
        sig_w = max(len(s["signal_id"]) for s in all_signals)
        sig_w = max(sig_w, len("Signal"))
        dir_w = max(len(s["direction"]) for s in all_signals)
        dir_w = max(dir_w, len("Direction"))
        str_w = max(len(s["strength"]) for s in all_signals)
        str_w = max(str_w, len("Strength"))
        conf_w = max(len("Confidence"), 10)

        def _hline(char: str = "-") -> str:
            return (
                f"+{char * (sig_w + 2)}"
                f"+{char * (dir_w + 2)}"
                f"+{char * (str_w + 2)}"
                f"+{char * (conf_w + 2)}+"
            )

        def _row(sig: str, dirn: str, stren: str, conf: str) -> str:
            return (
                f"| {sig:<{sig_w}} "
                f"| {dirn:<{dir_w}} "
                f"| {stren:<{str_w}} "
                f"| {conf:<{conf_w}} |"
            )

        for agent_id in sorted(agent_signals.keys()):
            sigs = agent_signals[agent_id]
            lines.append(f"  [{agent_id}]")
            lines.append(_hline("-"))
            lines.append(_row("Signal", "Direction", "Strength", "Confidence"))
            lines.append(_hline("-"))
            for s in sigs:
                lines.append(
                    _row(
                        s["signal_id"],
                        s["direction"],
                        s["strength"],
                        f'{s["confidence"]:.2f}',
                    )
                )
            lines.append(_hline("-"))
            lines.append("")

    # ------------------------------------------------------------------
    # Consensus by asset class (aggregate direction per asset class)
    # ------------------------------------------------------------------
    lines.append("CONSENSUS BY ASSET CLASS")

    # Group signals by inferred asset class from signal_id prefix
    asset_class_map: dict[str, list[dict]] = defaultdict(list)
    for s in all_signals:
        sid = s["signal_id"].upper()
        if "INFLATION" in sid or "IPCA" in sid:
            asset_class_map["FIXED_INCOME"].append(s)
        elif (
            "MONETARY" in sid
            or "SELIC" in sid
            or "TAYLOR" in sid
            or "TERM" in sid
            or "RATES" in sid
        ):
            asset_class_map["FIXED_INCOME"].append(s)
        elif (
            "FX" in sid
            or "BEER" in sid
            or "CARRY" in sid
            or "CIP" in sid
            or "FLOW" in sid
            or "USDBRL" in sid
        ):
            asset_class_map["FX"].append(s)
        elif "FISCAL" in sid or "DSA" in sid or "IMPULSE" in sid or "DOMINANCE" in sid:
            asset_class_map["FIXED_INCOME"].append(s)
        elif "REGIME" in sid or "SENTIMENT" in sid or "CORRELATION" in sid:
            asset_class_map["EQUITY_INDEX"].append(s)
        else:
            asset_class_map["OTHER"].append(s)

    if not asset_class_map:
        lines.append("  No consensus data available.")
        lines.append("")
    else:
        ac_w = max(len(k) for k in asset_class_map)
        ac_w = max(ac_w, len("Asset Class"))

        def _ac_hline(char: str = "-") -> str:
            return f"+{char * (ac_w + 2)}+{char * 12}+{char * 12}+"

        def _ac_row(ac: str, dirn: str, conf: str) -> str:
            return f"| {ac:<{ac_w}} | {dirn:<10} | {conf:<10} |"

        lines.append(_ac_hline("-"))
        lines.append(_ac_row("Asset Class", "Direction", "Confidence"))
        lines.append(_ac_hline("-"))

        for ac_name in sorted(asset_class_map.keys()):
            ac_sigs = asset_class_map[ac_name]
            # Consensus: majority direction, average confidence
            dir_counts: dict[str, int] = defaultdict(int)
            conf_sum = 0.0
            for s in ac_sigs:
                dir_counts[s["direction"]] += 1
                conf_sum += s["confidence"]
            majority_dir = max(dir_counts, key=dir_counts.get)  # type: ignore[arg-type]
            avg_conf = conf_sum / len(ac_sigs)
            lines.append(_ac_row(ac_name, majority_dir, f"{avg_conf:.2f}"))

        lines.append(_ac_hline("-"))
        lines.append("")

    # ------------------------------------------------------------------
    # Footer
    # ------------------------------------------------------------------
    lines.append(f"Generated: {datetime.utcnow().isoformat(timespec='seconds')}Z")

    return "\n".join(lines)

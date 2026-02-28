"""NarrativeGenerator -- daily macro brief via Claude API or template fallback.

Produces an actionable morning call note from agent signals.  When an
Anthropic API key is available, uses Claude claude-sonnet-4-5 for natural-language
prose.  Otherwise falls back to a structured template (ASCII tables, no prose).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from src.narrative.templates import render_template

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Anthropic SDK -- conditional import
# ---------------------------------------------------------------------------
try:
    import anthropic

    _ANTHROPIC_AVAILABLE = True
except ImportError:
    anthropic = None  # type: ignore[assignment]
    _ANTHROPIC_AVAILABLE = False


# ---------------------------------------------------------------------------
# NarrativeBrief dataclass
# ---------------------------------------------------------------------------
@dataclass
class NarrativeBrief:
    """Output container for a generated macro narrative.

    Attributes:
        content: The narrative text (prose or table).
        source: ``"llm"``, ``"template"``, or ``"template_fallback"``.
        model: Claude model identifier (None for template).
        as_of_date: Point-in-time reference date.
        generated_at: UTC datetime of generation.
        word_count: Number of whitespace-delimited words in *content*.
    """

    content: str
    source: str
    model: str | None
    as_of_date: date
    generated_at: datetime
    word_count: int = field(init=False)

    def __post_init__(self) -> None:
        self.word_count = len(self.content.split())


# ---------------------------------------------------------------------------
# System & user prompt constants
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = (
    "You are a senior macro strategist at a global macro hedge fund. "
    "Write an internal morning call note for the trading desk."
)

_USER_INSTRUCTIONS = (
    "Write a daily macro brief (800-1500 words) covering: "
    "Executive Summary (2-3 sentences), Regime Assessment, Inflation Dynamics, "
    "Monetary Policy, Fiscal Outlook, FX & External, Portfolio Positioning, "
    "Key Risks & Watchlist.\n\n"
    "Tone: internal trading desk -- direct, first-person plural. "
    "'We're seeing hawkish signals.' 'Our regime model flipped to risk-off.'"
)

_MODEL_ID = "claude-sonnet-4-5"


# ---------------------------------------------------------------------------
# NarrativeGenerator
# ---------------------------------------------------------------------------
class NarrativeGenerator:
    """Generate a daily macro brief using Claude API or template fallback.

    Args:
        api_key: Anthropic API key.  If *None*, reads from
            ``settings.anthropic_api_key``.  If empty string, template
            fallback is used.
    """

    def __init__(self, api_key: str | None = None) -> None:
        if api_key is None:
            from src.core.config import settings

            api_key = settings.anthropic_api_key

        self._has_api_key = bool(api_key)

        if self._has_api_key:
            if not _ANTHROPIC_AVAILABLE:
                raise ImportError(
                    "The 'anthropic' package is required for LLM narrative "
                    "generation.  Install it with: pip install anthropic"
                )
            self._client = anthropic.Anthropic(api_key=api_key)
        else:
            self._client = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def generate(
        self,
        agent_reports: dict[str, Any],
        features: dict | None = None,
        as_of_date: date | None = None,
    ) -> NarrativeBrief:
        """Generate a macro brief from agent reports.

        Args:
            agent_reports: Mapping of agent_id to AgentReport.
            features: Optional additional feature data dict.
            as_of_date: Reference date (defaults to today).

        Returns:
            NarrativeBrief with content and metadata.
        """
        if as_of_date is None:
            as_of_date = date.today()

        if self._has_api_key:
            return self._generate_llm(agent_reports, features, as_of_date)
        return self._generate_template(agent_reports, features, as_of_date)

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------
    def _generate_llm(
        self,
        agent_reports: dict[str, Any],
        features: dict | None,
        as_of_date: date,
    ) -> NarrativeBrief:
        """Generate narrative via Claude API.

        Falls back to template on any API error.
        """
        prompt_data = self._build_prompt_data(agent_reports, features)
        user_message = (
            f"Date: {as_of_date.isoformat()}\n\n"
            f"AGENT SIGNAL DATA:\n{prompt_data}\n\n"
            f"{_USER_INSTRUCTIONS}"
        )

        try:
            response = self._client.messages.create(  # type: ignore[union-attr]
                model=_MODEL_ID,
                max_tokens=2048,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            content = response.content[0].text
            return NarrativeBrief(
                content=content,
                source="llm",
                model=_MODEL_ID,
                as_of_date=as_of_date,
                generated_at=datetime.utcnow(),
            )
        except Exception as exc:
            logger.warning("LLM generation failed, falling back to template: %s", exc)
            content = render_template(agent_reports, features, as_of_date)
            return NarrativeBrief(
                content=content,
                source="template_fallback",
                model=None,
                as_of_date=as_of_date,
                generated_at=datetime.utcnow(),
            )

    # ------------------------------------------------------------------
    # Template path
    # ------------------------------------------------------------------
    def _generate_template(
        self,
        agent_reports: dict[str, Any],
        features: dict | None,
        as_of_date: date,
    ) -> NarrativeBrief:
        """Generate narrative via structured template (no LLM)."""
        content = render_template(agent_reports, features, as_of_date)
        return NarrativeBrief(
            content=content,
            source="template",
            model=None,
            as_of_date=as_of_date,
            generated_at=datetime.utcnow(),
        )

    # ------------------------------------------------------------------
    # v2: Cross-asset narrative from CrossAssetView
    # ------------------------------------------------------------------
    def generate_cross_asset_narrative(self, view: Any) -> str:
        """Generate a cross-asset narrative section from a CrossAssetView.

        If API key available, uses structured LLM prompt requesting 3-5
        sentences explaining regime, key drivers, trade rationale, and risks.
        Falls back to template-based ASCII summary.

        Args:
            view: CrossAssetView instance (imported lazily to avoid circular).

        Returns:
            Cross-asset narrative string.
        """
        if self._has_api_key:
            try:
                return self._generate_cross_asset_llm(view)
            except Exception as exc:
                logger.warning(
                    "LLM cross-asset narrative failed, using template: %s", exc
                )

        return self._generate_cross_asset_template(view)

    def _generate_cross_asset_llm(self, view: Any) -> str:
        """Generate cross-asset narrative via LLM.

        Args:
            view: CrossAssetView instance.

        Returns:
            LLM-generated narrative string.
        """
        prompt = (
            "Write a concise 3-5 sentence cross-asset regime narrative for the "
            "trading desk based on the following data. Return ONLY the narrative text, "
            "no JSON wrapper.\n\n"
            f"Regime: {view.regime} (probabilities: {view.regime_probabilities})\n"
            f"Risk Appetite: {view.risk_appetite:.0f}/100\n"
        )

        if view.tail_risk:
            prompt += (
                f"Tail Risk: {view.tail_risk.assessment} "
                f"(composite={view.tail_risk.composite_score:.0f}, "
                f"transition_prob={view.tail_risk.regime_transition_prob:.2%})\n"
            )

        if view.key_trades:
            trades_str = ", ".join(
                f"{t.direction} {t.instrument} ({t.conviction:.0%})"
                for t in view.key_trades
            )
            prompt += f"Key Trades: {trades_str}\n"

        if view.risk_warnings:
            prompt += f"Warnings: {'; '.join(view.risk_warnings)}\n"

        response = self._client.messages.create(  # type: ignore[union-attr]
            model=_MODEL_ID,
            max_tokens=500,
            system=("You are a senior macro strategist. Write concise internal notes."),
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    @staticmethod
    def _generate_cross_asset_template(view: Any) -> str:
        """Generate cross-asset narrative using template (no LLM).

        Args:
            view: CrossAssetView instance.

        Returns:
            Template-based narrative string.
        """
        lines = []
        lines.append(f"CROSS-ASSET VIEW ({view.as_of_date})")
        lines.append(f"  Regime: {view.regime}")

        if view.regime_probabilities:
            probs = ", ".join(
                f"{k}={v:.0%}"
                for k, v in sorted(
                    view.regime_probabilities.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )
            )
            lines.append(f"  Probabilities: {probs}")

        lines.append(f"  Risk Appetite: {view.risk_appetite:.0f}/100")

        if view.tail_risk:
            lines.append(
                f"  Tail Risk: {view.tail_risk.assessment} "
                f"(score={view.tail_risk.composite_score:.0f})"
            )

        if view.key_trades:
            lines.append("  Key Trades:")
            for t in view.key_trades:
                lines.append(
                    f"    {t.direction} {t.instrument} "
                    f"({t.conviction:.0%}) -- {t.rationale}"
                )

        if view.risk_warnings:
            lines.append("  Warnings:")
            for w in view.risk_warnings:
                lines.append(f"    - {w}")

        if view.consistency_issues:
            lines.append("  Consistency Issues:")
            for issue in view.consistency_issues:
                lines.append(
                    f"    [{issue.rule_id}] {issue.description} "
                    f"(penalty={issue.sizing_penalty}x)"
                )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Prompt builder
    # ------------------------------------------------------------------
    @staticmethod
    def _build_prompt_data(
        agent_reports: dict[str, Any],
        features: dict | None,
    ) -> str:
        """Serialize agent reports into structured text for the LLM prompt.

        Includes CrossAssetView data when available in features.

        Args:
            agent_reports: Mapping of agent_id to AgentReport.
            features: Optional features dict.

        Returns:
            Multi-line string with all signal data.
        """
        parts: list[str] = []

        for agent_id, report in sorted(agent_reports.items()):
            parts.append(f"--- Agent: {agent_id} ---")
            parts.append(f"  Signal count: {len(report.signals)}")
            for sig in report.signals:
                direction = (
                    sig.direction.value
                    if hasattr(sig.direction, "value")
                    else str(sig.direction)
                )
                strength = (
                    sig.strength.value
                    if hasattr(sig.strength, "value")
                    else str(sig.strength)
                )
                parts.append(f"  Signal: {sig.signal_id}")
                parts.append(f"    Direction: {direction}")
                parts.append(f"    Strength:  {strength}")
                parts.append(f"    Confidence: {sig.confidence:.2f}")
                parts.append(f"    Value:      {sig.value:.4f}")
            parts.append("")

        if features:
            parts.append("--- Additional Features ---")
            for key, val in sorted(features.items()):
                if key.startswith("_"):
                    continue  # skip private keys
                parts.append(f"  {key}: {val}")
            parts.append("")

            # v2: Include CrossAssetView data if available
            cross_view = features.get("_cross_asset_view")
            if cross_view is not None:
                parts.append("--- Cross-Asset View ---")
                parts.append(f"  Regime: {cross_view.regime}")
                parts.append(f"  Risk Appetite: {cross_view.risk_appetite:.0f}")
                if cross_view.tail_risk:
                    parts.append(f"  Tail Risk: {cross_view.tail_risk.assessment}")
                if cross_view.key_trades:
                    for t in cross_view.key_trades:
                        parts.append(
                            f"  Trade: {t.direction} {t.instrument} "
                            f"({t.conviction:.2f})"
                        )
                parts.append("")

        return "\n".join(parts)

"""Unit tests for NarrativeGenerator -- LLM and template paths.

All tests use mocks for the Anthropic SDK.  No real API calls are made.
"""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock, patch

from src.agents.base import AgentReport, AgentSignal
from src.core.enums import SignalDirection, SignalStrength
from src.narrative.generator import NarrativeBrief, NarrativeGenerator


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------
def _make_signal(
    signal_id: str,
    agent_id: str,
    direction: SignalDirection = SignalDirection.LONG,
    strength: SignalStrength = SignalStrength.STRONG,
    confidence: float = 0.85,
    value: float = 1.5,
) -> AgentSignal:
    return AgentSignal(
        signal_id=signal_id,
        agent_id=agent_id,
        timestamp=datetime(2024, 1, 15, 8, 0, 0),
        as_of_date=date(2024, 1, 15),
        direction=direction,
        strength=strength,
        confidence=confidence,
        value=value,
        horizon_days=21,
        metadata={},
    )


def _make_mock_reports() -> dict[str, AgentReport]:
    """Create a dict of 5 agent reports with realistic signal data."""
    reports: dict[str, AgentReport] = {}

    # Inflation agent -- 3 signals
    reports["inflation_agent"] = AgentReport(
        agent_id="inflation_agent",
        as_of_date=date(2024, 1, 15),
        generated_at=datetime(2024, 1, 15, 8, 0),
        signals=[
            _make_signal("INFLATION_BR_PHILLIPS", "inflation_agent",
                         SignalDirection.LONG, SignalStrength.STRONG, 0.85, 1.2),
            _make_signal("INFLATION_BR_PERSISTENCE", "inflation_agent",
                         SignalDirection.LONG, SignalStrength.MODERATE, 0.60, 0.8),
            _make_signal("INFLATION_BR_COMPOSITE", "inflation_agent",
                         SignalDirection.LONG, SignalStrength.STRONG, 0.78, 1.0),
        ],
        narrative="Inflation pressures rising.",
    )

    # Monetary agent -- 4 signals
    reports["monetary_agent"] = AgentReport(
        agent_id="monetary_agent",
        as_of_date=date(2024, 1, 15),
        generated_at=datetime(2024, 1, 15, 8, 0),
        signals=[
            _make_signal("MONETARY_BR_TAYLOR", "monetary_agent",
                         SignalDirection.SHORT, SignalStrength.STRONG, 0.90, -1.5),
            _make_signal("MONETARY_BR_SELIC_PATH", "monetary_agent",
                         SignalDirection.SHORT, SignalStrength.MODERATE, 0.65, -0.9),
            _make_signal("MONETARY_BR_TERM_PREMIUM", "monetary_agent",
                         SignalDirection.NEUTRAL, SignalStrength.WEAK, 0.35, 0.1),
            _make_signal("MONETARY_BR_COMPOSITE", "monetary_agent",
                         SignalDirection.SHORT, SignalStrength.MODERATE, 0.62, -0.7),
        ],
        narrative="Hawkish signals from Taylor rule.",
    )

    # Fiscal agent -- 3 signals
    reports["fiscal_agent"] = AgentReport(
        agent_id="fiscal_agent",
        as_of_date=date(2024, 1, 15),
        generated_at=datetime(2024, 1, 15, 8, 0),
        signals=[
            _make_signal("FISCAL_BR_DSA", "fiscal_agent",
                         SignalDirection.SHORT, SignalStrength.MODERATE, 0.55, -0.6),
            _make_signal("FISCAL_BR_IMPULSE", "fiscal_agent",
                         SignalDirection.SHORT, SignalStrength.WEAK, 0.40, -0.3),
            _make_signal("FISCAL_BR_COMPOSITE", "fiscal_agent",
                         SignalDirection.SHORT, SignalStrength.MODERATE, 0.50, -0.5),
        ],
        narrative="Fiscal deterioration ongoing.",
    )

    # FX agent -- 5 signals
    reports["fx_agent"] = AgentReport(
        agent_id="fx_agent",
        as_of_date=date(2024, 1, 15),
        generated_at=datetime(2024, 1, 15, 8, 0),
        signals=[
            _make_signal("FX_BR_BEER", "fx_agent",
                         SignalDirection.LONG, SignalStrength.MODERATE, 0.60, 0.7),
            _make_signal("FX_BR_CARRY", "fx_agent",
                         SignalDirection.LONG, SignalStrength.STRONG, 0.80, 1.1),
            _make_signal("FX_BR_FLOW", "fx_agent",
                         SignalDirection.NEUTRAL, SignalStrength.WEAK, 0.30, 0.1),
            _make_signal("FX_BR_CIP", "fx_agent",
                         SignalDirection.LONG, SignalStrength.WEAK, 0.35, 0.2),
            _make_signal("FX_BR_COMPOSITE", "fx_agent",
                         SignalDirection.LONG, SignalStrength.MODERATE, 0.55, 0.5),
        ],
        narrative="BRL undervalued vs BEER estimate.",
    )

    # Cross-asset / regime agent -- 3 signals
    reports["cross_asset_agent"] = AgentReport(
        agent_id="cross_asset_agent",
        as_of_date=date(2024, 1, 15),
        generated_at=datetime(2024, 1, 15, 8, 0),
        signals=[
            _make_signal("REGIME_DETECTION", "cross_asset_agent",
                         SignalDirection.SHORT, SignalStrength.MODERATE, 0.58, -0.4),
            _make_signal("CORRELATION_ANALYSIS", "cross_asset_agent",
                         SignalDirection.NEUTRAL, SignalStrength.WEAK, 0.30, 0.0),
            _make_signal("RISK_SENTIMENT_INDEX", "cross_asset_agent",
                         SignalDirection.SHORT, SignalStrength.MODERATE, 0.55, -0.3),
        ],
        narrative="Regime shifting to risk-off.",
    )

    return reports


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestNarrativeBriefDataclass:
    """Test NarrativeBrief fields and word_count computation."""

    def test_narrative_brief_dataclass(self) -> None:
        brief = NarrativeBrief(
            content="This is a test narrative with exactly ten words in it.",
            source="template",
            model=None,
            as_of_date=date(2024, 1, 15),
            generated_at=datetime(2024, 1, 15, 8, 0),
        )
        assert brief.source == "template"
        assert brief.model is None
        assert brief.as_of_date == date(2024, 1, 15)
        assert brief.word_count == 11
        assert isinstance(brief.generated_at, datetime)

    def test_narrative_word_count_range(self) -> None:
        """LLM mock returns 1000-word text; verify word_count is in range."""
        words = " ".join(["macro"] * 1000)
        brief = NarrativeBrief(
            content=words,
            source="llm",
            model="claude-sonnet-4-5",
            as_of_date=date(2024, 1, 15),
            generated_at=datetime(2024, 1, 15, 8, 0),
        )
        assert 900 <= brief.word_count <= 1100


class TestNarrativeGeneratorLLM:
    """Tests for the LLM generation path (mocked)."""

    @patch("src.narrative.generator.anthropic")
    def test_generate_with_api_key_calls_llm(self, mock_anthropic_module: MagicMock) -> None:
        """Mock anthropic.Anthropic; verify client.messages.create() is called."""
        mock_client = MagicMock()
        mock_anthropic_module.Anthropic.return_value = mock_client
        mock_anthropic_module.__bool__ = lambda self: True

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Generated macro brief with lots of words.")]
        mock_client.messages.create.return_value = mock_response

        # Patch _ANTHROPIC_AVAILABLE for the import check
        with patch("src.narrative.generator._ANTHROPIC_AVAILABLE", True):
            gen = NarrativeGenerator(api_key="sk-test-key-123")
            reports = _make_mock_reports()
            brief = gen.generate(reports, as_of_date=date(2024, 1, 15))

        assert brief.source == "llm"
        assert brief.model == "claude-sonnet-4-5"
        mock_client.messages.create.assert_called_once()

        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs.get("model") or call_kwargs[1].get("model") == "claude-sonnet-4-5"

    @patch("src.narrative.generator.anthropic")
    def test_llm_fallback_on_api_error(self, mock_anthropic_module: MagicMock) -> None:
        """Mock API to raise exception; verify graceful fallback to template."""
        mock_client = MagicMock()
        mock_anthropic_module.Anthropic.return_value = mock_client

        mock_client.messages.create.side_effect = Exception("API rate limit exceeded")

        with patch("src.narrative.generator._ANTHROPIC_AVAILABLE", True):
            gen = NarrativeGenerator(api_key="sk-test-key-123")
            reports = _make_mock_reports()
            brief = gen.generate(reports, as_of_date=date(2024, 1, 15))

        assert brief.source == "template_fallback"
        assert brief.model is None
        assert "DAILY MACRO BRIEF" in brief.content


class TestNarrativeGeneratorTemplate:
    """Tests for the template fallback path."""

    def test_generate_without_api_key_uses_template(self) -> None:
        """NarrativeGenerator(api_key='') falls back to template."""
        gen = NarrativeGenerator(api_key="")
        reports = _make_mock_reports()
        brief = gen.generate(reports, as_of_date=date(2024, 1, 15))

        assert brief.source == "template"
        assert brief.model is None
        assert "DAILY MACRO BRIEF" in brief.content
        assert "2024-01-15" in brief.content

    def test_template_output_contains_signal_table(self) -> None:
        """Template output contains signal direction, strength, confidence."""
        gen = NarrativeGenerator(api_key="")
        reports = _make_mock_reports()
        brief = gen.generate(reports, as_of_date=date(2024, 1, 15))

        # Check for presence of table data
        assert "LONG" in brief.content
        assert "SHORT" in brief.content
        assert "STRONG" in brief.content
        assert "MODERATE" in brief.content
        assert "0.85" in brief.content
        assert "INFLATION_BR_PHILLIPS" in brief.content

    def test_template_output_no_prose(self) -> None:
        """Template output does not contain filler/prose words."""
        gen = NarrativeGenerator(api_key="")
        reports = _make_mock_reports()
        brief = gen.generate(reports, as_of_date=date(2024, 1, 15))

        content_lower = brief.content.lower()
        for filler in ["suggests", "indicates", "appears", "seems", "likely"]:
            assert filler not in content_lower, (
                f"Template should not contain prose word '{filler}'"
            )

    def test_template_groups_by_agent(self) -> None:
        """Each agent section appears with its signals grouped together."""
        gen = NarrativeGenerator(api_key="")
        reports = _make_mock_reports()
        brief = gen.generate(reports, as_of_date=date(2024, 1, 15))

        # Each agent_id should appear as a section header
        for agent_id in reports:
            assert agent_id in brief.content, (
                f"Agent '{agent_id}' not found in template output"
            )

        # Signals within the same agent should appear together (consecutive)
        content = brief.content
        for agent_id, report in reports.items():
            agent_pos = content.index(agent_id)
            for sig in report.signals:
                sig_pos = content.index(sig.signal_id)
                # Signal should appear after its agent header
                assert sig_pos > agent_pos, (
                    f"Signal '{sig.signal_id}' should appear after agent "
                    f"'{agent_id}' header"
                )


class TestBuildPromptData:
    """Test _build_prompt_data serialization."""

    def test_build_prompt_data_serialization(self) -> None:
        """_build_prompt_data includes all agent signals with direction/strength/confidence."""
        reports = _make_mock_reports()
        prompt_data = NarrativeGenerator._build_prompt_data(reports, None)

        # Every agent should be represented
        for agent_id in reports:
            assert f"Agent: {agent_id}" in prompt_data

        # Every signal should have direction/strength/confidence
        for report in reports.values():
            for sig in report.signals:
                assert sig.signal_id in prompt_data
                assert sig.direction.value in prompt_data
                assert sig.strength.value in prompt_data
                assert f"{sig.confidence:.2f}" in prompt_data

    def test_build_prompt_data_includes_features(self) -> None:
        """_build_prompt_data includes features dict when provided."""
        reports = _make_mock_reports()
        features = {"vix_level": 22.5, "dxy_index": 104.3}
        prompt_data = NarrativeGenerator._build_prompt_data(reports, features)

        assert "Additional Features" in prompt_data
        assert "vix_level" in prompt_data
        assert "dxy_index" in prompt_data


class TestSettingsIntegration:
    """Test config integration."""

    def test_settings_has_anthropic_key(self) -> None:
        """Import settings, verify anthropic_api_key attribute exists."""
        from src.core.config import settings

        assert hasattr(settings, "anthropic_api_key")
        assert isinstance(settings.anthropic_api_key, str)

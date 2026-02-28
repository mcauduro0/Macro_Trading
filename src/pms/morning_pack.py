"""Morning Pack daily briefing service for the Portfolio Management System.

Consolidates system intelligence (signals, agents, regime, risk, portfolio state)
into a structured daily briefing with action-first ordering. Optionally generates
an LLM-powered macro narrative with template-based fallback.

MorningPackService is the daily command center for the portfolio manager,
providing a single-view summary of everything needed to start the trading day.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime
from typing import Any

import structlog

from .position_manager import PositionManager
from .trade_workflow import TradeWorkflowService

logger = structlog.get_logger(__name__)

# Priority ordering for action items (lower index = higher priority)
_PRIORITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


class MorningPackService:
    """Generates structured daily briefings for the portfolio manager.

    The morning pack is the operational command center: action items and trade
    proposals come first, followed by context (market data, agent views, regime,
    signals, portfolio state) and an analytical narrative.

    All components are optional -- the service degrades gracefully when any
    dependency is unavailable, marking the corresponding section as
    ``{"status": "unavailable", "reason": ...}``.

    Briefings are auto-persisted to an internal ``_briefings`` list using the
    same in-memory pattern as ``PositionManager._positions``.

    Args:
        position_manager: PositionManager instance for portfolio state.
        trade_workflow: TradeWorkflowService for pending proposals.
        signal_aggregator: SignalAggregatorV2 for top signals.
        signal_monitor: SignalMonitor for signal changes.
        risk_limits_manager: RiskLimitsManager for risk limit breaches.
        var_calculator: VaRCalculator for portfolio VaR.
        stress_tester: StressTester for stress test results.
    """

    def __init__(
        self,
        position_manager: PositionManager | None = None,
        trade_workflow: TradeWorkflowService | None = None,
        signal_aggregator: Any | None = None,
        signal_monitor: Any | None = None,
        risk_limits_manager: Any | None = None,
        var_calculator: Any | None = None,
        stress_tester: Any | None = None,
    ) -> None:
        self.position_manager = position_manager
        self.trade_workflow = trade_workflow
        self.signal_aggregator = signal_aggregator
        self.signal_monitor = signal_monitor
        self.risk_limits_manager = risk_limits_manager
        self.var_calculator = var_calculator
        self.stress_tester = stress_tester
        self._briefings: list[dict] = []

    # -------------------------------------------------------------------------
    # Core: generate daily briefing
    # -------------------------------------------------------------------------

    def generate(self, briefing_date: date, force: bool = False) -> dict:
        """Generate a complete daily briefing for the given date.

        If a briefing for this date already exists and ``force`` is False,
        returns the existing briefing without regenerating.

        The briefing uses action-first ordering: action_items and
        trade_proposals appear before contextual sections.

        Args:
            briefing_date: Date for the briefing.
            force: If True, regenerate even if a briefing already exists.

        Returns:
            Complete DailyBriefing dict with all sections.
        """
        # Check for existing briefing
        if not force:
            existing = self.get_by_date(briefing_date)
            if existing is not None:
                logger.info("briefing_exists", briefing_date=str(briefing_date))
                return existing

        now = datetime.utcnow()

        # Collect all sections with graceful degradation
        trade_proposals = self._collect_trade_proposals(briefing_date)
        portfolio_state = self._collect_portfolio_state(briefing_date)
        agent_views = self._collect_agent_views()
        regime = self._collect_regime()
        top_signals = self._collect_top_signals()
        signal_changes = self._collect_signal_changes()
        market_snapshot = self._collect_market_snapshot()

        # Build action items from collected data (must come after other sections)
        action_items = self._build_action_items(
            trade_proposals, signal_changes, portfolio_state, regime
        )

        # Generate macro narrative (LLM with template fallback)
        macro_narrative = self._generate_macro_narrative(
            agent_views, regime, top_signals, portfolio_state, briefing_date
        )

        # Assemble briefing with action-first ordering
        briefing: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "briefing_date": briefing_date,
            "created_at": now,
            "action_items": action_items,
            "trade_proposals": trade_proposals,
            "market_snapshot": market_snapshot,
            "agent_views": agent_views,
            "regime": regime,
            "top_signals": top_signals,
            "signal_changes": signal_changes,
            "portfolio_state": portfolio_state,
            "macro_narrative": macro_narrative,
        }

        # Auto-persist
        self._briefings.append(briefing)

        logger.info(
            "briefing_generated",
            briefing_date=str(briefing_date),
            action_items_count=(
                len(action_items) if isinstance(action_items, list) else 0
            ),
            sections=len(briefing) - 3,  # exclude id, date, created_at
        )

        return briefing

    # -------------------------------------------------------------------------
    # Retrieval methods
    # -------------------------------------------------------------------------

    def get_latest(self) -> dict | None:
        """Return the most recent briefing, or None if no briefings exist."""
        if not self._briefings:
            return None
        return self._briefings[-1]

    def get_by_date(self, briefing_date: date) -> dict | None:
        """Find a briefing by date.

        Args:
            briefing_date: Date to search for.

        Returns:
            Briefing dict if found, else None.
        """
        for b in reversed(self._briefings):
            if b.get("briefing_date") == briefing_date:
                return b
        return None

    def get_history(self, days: int = 30) -> list[dict]:
        """Return summaries of the last N briefings.

        Args:
            days: Maximum number of recent briefings to return.

        Returns:
            List of summary dicts (date, action count, narrative excerpt).
        """
        recent = (
            self._briefings[-days:] if len(self._briefings) > days else self._briefings
        )
        summaries = []
        for b in recent:
            action_items = b.get("action_items", [])
            narrative = b.get("macro_narrative", "")
            narrative_excerpt = ""
            if isinstance(narrative, str) and len(narrative) > 200:
                narrative_excerpt = narrative[:200] + "..."
            elif isinstance(narrative, str):
                narrative_excerpt = narrative
            elif isinstance(narrative, dict):
                narrative_excerpt = str(narrative.get("status", ""))

            summaries.append(
                {
                    "briefing_date": b.get("briefing_date"),
                    "action_items_count": (
                        len(action_items) if isinstance(action_items, list) else 0
                    ),
                    "narrative_excerpt": narrative_excerpt,
                }
            )
        return summaries

    # -------------------------------------------------------------------------
    # Section collectors (each wraps in try/except for graceful degradation)
    # -------------------------------------------------------------------------

    def _collect_trade_proposals(self, briefing_date: date) -> list[dict] | dict:
        """Collect pending trade proposals from the trade workflow service."""
        if self.trade_workflow is None:
            return {
                "status": "unavailable",
                "reason": "TradeWorkflowService not configured",
            }
        try:
            proposals = self.trade_workflow.get_pending_proposals(
                as_of_date=briefing_date
            )
            # Also include proposals without date filter
            if not proposals:
                proposals = self.trade_workflow.get_pending_proposals()
            return proposals
        except Exception as exc:
            logger.warning("trade_proposals_failed", error=str(exc))
            return {"status": "unavailable", "reason": str(exc)}

    def _collect_portfolio_state(self, briefing_date: date) -> dict:
        """Collect portfolio state from the position manager."""
        if self.position_manager is None:
            return {"status": "unavailable", "reason": "PositionManager not configured"}
        try:
            book = self.position_manager.get_book(as_of_date=briefing_date)
            return book
        except Exception as exc:
            logger.warning("portfolio_state_failed", error=str(exc))
            return {"status": "unavailable", "reason": str(exc)}

    def _collect_agent_views(self) -> list[dict] | dict:
        """Collect latest views from all 5 analytical agents via AgentRegistry."""
        try:
            from src.agents.registry import AgentRegistry

            agent_ids = [
                "inflation_agent",
                "monetary_agent",
                "fiscal_agent",
                "fx_agent",
                "cross_asset_agent",
            ]

            views = []
            for agent_id in agent_ids:
                try:
                    agent = AgentRegistry.get(agent_id)
                    # Try to get the latest report if available
                    report = getattr(agent, "latest_report", None)
                    views.append(
                        {
                            "agent_id": agent_id,
                            "signal_direction": (
                                getattr(report, "direction", "NEUTRAL")
                                if report
                                else "NEUTRAL"
                            ),
                            "conviction": (
                                getattr(report, "conviction", 0.0) if report else 0.0
                            ),
                            "key_drivers": (
                                getattr(report, "key_drivers", []) if report else []
                            ),
                            "risks": getattr(report, "risks", []) if report else [],
                            "narrative_excerpt": (
                                getattr(report, "narrative", "")[:200]
                                if report and hasattr(report, "narrative")
                                else ""
                            ),
                        }
                    )
                except (KeyError, Exception):
                    views.append(
                        {
                            "agent_id": agent_id,
                            "signal_direction": "NEUTRAL",
                            "conviction": 0.0,
                            "key_drivers": [],
                            "risks": [],
                            "narrative_excerpt": "Agent not registered or unavailable.",
                        }
                    )

            return views
        except ImportError:
            return {"status": "unavailable", "reason": "AgentRegistry not importable"}
        except Exception as exc:
            logger.warning("agent_views_failed", error=str(exc))
            return {"status": "unavailable", "reason": str(exc)}

    def _collect_regime(self) -> dict:
        """Collect current regime classification from CrossAssetAgent view."""
        try:
            from src.agents.registry import AgentRegistry

            agent = AgentRegistry.get("cross_asset_agent")
            report = getattr(agent, "latest_report", None)
            if report and hasattr(report, "regime"):
                regime_data = report.regime
                return {
                    "current_regime": getattr(regime_data, "name", "Unknown"),
                    "probabilities": getattr(regime_data, "probabilities", {}),
                    "transition_risk": getattr(regime_data, "transition_prob", 0.0),
                }
            return {
                "current_regime": "Unknown",
                "probabilities": {
                    "Goldilocks": 0.25,
                    "Reflation": 0.25,
                    "Stagflation": 0.25,
                    "Deflation": 0.25,
                },
                "transition_risk": 0.0,
            }
        except (KeyError, ImportError, Exception):
            return {
                "current_regime": "Unknown",
                "probabilities": {
                    "Goldilocks": 0.25,
                    "Reflation": 0.25,
                    "Stagflation": 0.25,
                    "Deflation": 0.25,
                },
                "transition_risk": 0.0,
            }

    def _collect_top_signals(self) -> list[dict] | dict:
        """Collect top 10 signals by conviction from the signal aggregator."""
        if self.signal_aggregator is None:
            return {
                "status": "unavailable",
                "reason": "SignalAggregatorV2 not configured",
            }
        try:
            # SignalAggregatorV2 stores results in _latest_results after aggregate()
            latest = getattr(self.signal_aggregator, "_latest_results", None)
            if latest and isinstance(latest, list):
                # Sort by absolute conviction, take top 10
                sorted_signals = sorted(
                    latest, key=lambda s: abs(getattr(s, "conviction", 0)), reverse=True
                )[:10]
                return [
                    {
                        "instrument": getattr(s, "instrument", ""),
                        "direction": str(getattr(s, "direction", "NEUTRAL")),
                        "conviction": getattr(s, "conviction", 0.0),
                        "confidence": getattr(s, "confidence", 0.0),
                        "method": getattr(s, "method", ""),
                    }
                    for s in sorted_signals
                ]
            return {
                "status": "unavailable",
                "reason": "No aggregated signals available",
            }
        except Exception as exc:
            logger.warning("top_signals_failed", error=str(exc))
            return {"status": "unavailable", "reason": str(exc)}

    def _collect_signal_changes(self) -> dict:
        """Collect signal flips, surges, and new signals from signal monitor."""
        if self.signal_monitor is None:
            return {"status": "unavailable", "reason": "SignalMonitor not configured"}
        try:
            # SignalMonitor stores detected anomalies after generate_daily_summary()
            flips = getattr(self.signal_monitor, "_latest_flips", [])
            surges = getattr(self.signal_monitor, "_latest_surges", [])
            return {
                "flips": [
                    {
                        "instrument": getattr(f, "instrument", ""),
                        "previous_direction": str(getattr(f, "previous_direction", "")),
                        "current_direction": str(getattr(f, "current_direction", "")),
                    }
                    for f in flips
                ],
                "surges": [
                    {
                        "instrument": getattr(s, "instrument", ""),
                        "previous_conviction": getattr(s, "previous_conviction", 0.0),
                        "current_conviction": getattr(s, "current_conviction", 0.0),
                    }
                    for s in surges
                ],
                "new_above_threshold": [],
            }
        except Exception as exc:
            logger.warning("signal_changes_failed", error=str(exc))
            return {"status": "unavailable", "reason": str(exc)}

    def _collect_market_snapshot(self) -> dict:
        """Collect market snapshot from database macro series.

        Queries the latest values for key macro indicators from TimescaleDB.
        Returns structured dict with real market data, or unavailable status
        if database is not accessible.
        """
        try:
            from sqlalchemy import create_engine, text

            from src.core.config import get_settings

            settings = get_settings()
            engine = create_engine(settings.database_url)

            snapshot: dict[str, dict] = {
                "brazil_rates": {},
                "brazil_macro": {},
                "fx": {},
                "us_rates": {},
                "us_macro": {},
                "global_": {},
                "credit": {},
            }

            # Key series mappings: {db_series_id: (category, display_name)}
            series_map = {
                "BCB_432": ("brazil_rates", "SELIC"),
                "BCB_4389": ("fx", "USDBRL"),
                "BCB_433": ("brazil_macro", "IPCA_12M"),
                "FRED_DFF": ("us_rates", "FED_FUNDS"),
                "FRED_DGS10": ("us_rates", "UST_10Y"),
                "FRED_VIXCLS": ("global_", "VIX"),
            }

            with engine.connect() as conn:
                for series_id, (category, name) in series_map.items():
                    try:
                        result = conn.execute(
                            text(
                                "SELECT value, reference_date FROM macro_series "
                                "WHERE series_id = :sid "
                                "ORDER BY reference_date DESC LIMIT 1"
                            ),
                            {"sid": series_id},
                        )
                        row = result.first()
                        if row:
                            snapshot[category][name] = {
                                "value": float(row.value),
                                "date": str(row.reference_date),
                            }
                    except Exception:
                        continue

            return snapshot

        except Exception as exc:
            logger.warning("market_snapshot_db_unavailable: %s", exc)
            return {
                "brazil_rates": {},
                "brazil_macro": {},
                "fx": {},
                "us_rates": {},
                "us_macro": {},
                "global_": {},
                "credit": {},
                "status": "partial",
                "reason": f"Database unavailable for market snapshot: {exc}",
            }

    # -------------------------------------------------------------------------
    # Action items builder
    # -------------------------------------------------------------------------

    def _build_action_items(
        self,
        trade_proposals: list[dict] | dict,
        signal_changes: dict,
        portfolio_state: dict,
        regime: dict,
    ) -> list[dict]:
        """Build prioritized action items from all available data.

        Action items are sorted by priority (CRITICAL first).

        Args:
            trade_proposals: Pending proposals or unavailable dict.
            signal_changes: Signal flips/surges or unavailable dict.
            portfolio_state: Portfolio book or unavailable dict.
            regime: Regime info.

        Returns:
            List of action item dicts sorted by priority.
        """
        items: list[dict] = []

        # 1. Trade proposals needing review
        if isinstance(trade_proposals, list):
            for proposal in trade_proposals:
                priority = "HIGH"
                if proposal.get("is_flip"):
                    priority = "CRITICAL"
                elif proposal.get("conviction", 0) >= 0.8:
                    priority = "HIGH"
                else:
                    priority = "MEDIUM"

                items.append(
                    {
                        "priority": priority,
                        "category": "trade_proposal",
                        "description": (
                            f"{proposal.get('direction', 'UNKNOWN')} "
                            f"{proposal.get('instrument', 'UNKNOWN')} "
                            f"({proposal.get('conviction', 0):.0%} conviction)"
                            f"{' [FLIP]' if proposal.get('is_flip') else ''}"
                        ),
                        "urgency": "Requires review today",
                    }
                )

        # 2. Risk limit breaches
        if self.risk_limits_manager is not None:
            try:
                check_result = self.risk_limits_manager.check_all_v2({})
                overall = check_result.get("overall_status", "OK")
                if overall in ("WARNING", "BREACHED"):
                    priority = "CRITICAL" if overall == "BREACHED" else "HIGH"
                    items.append(
                        {
                            "priority": priority,
                            "category": "risk_breach",
                            "description": f"Risk limits {overall.lower()}: review portfolio exposure",
                            "urgency": (
                                "Immediate attention required"
                                if overall == "BREACHED"
                                else "Review within morning session"
                            ),
                        }
                    )
            except Exception:
                pass

        # 3. Signal flips and conviction surges
        if isinstance(signal_changes, dict) and "flips" in signal_changes:
            for flip in signal_changes.get("flips", []):
                items.append(
                    {
                        "priority": "HIGH",
                        "category": "signal_flip",
                        "description": (
                            f"Signal flip on {flip.get('instrument', 'UNKNOWN')}: "
                            f"{flip.get('previous_direction', '?')} -> {flip.get('current_direction', '?')}"
                        ),
                        "urgency": "Review position alignment",
                    }
                )

            for surge in signal_changes.get("surges", []):
                items.append(
                    {
                        "priority": "MEDIUM",
                        "category": "conviction_surge",
                        "description": (
                            f"Conviction surge on {surge.get('instrument', 'UNKNOWN')}: "
                            f"{surge.get('previous_conviction', 0):.2f} -> {surge.get('current_conviction', 0):.2f}"
                        ),
                        "urgency": "Monitor during session",
                    }
                )

        # 4. Stale data warnings (any section that failed to load)
        for section_name, section_data in [
            ("trade_proposals", trade_proposals),
            ("portfolio_state", portfolio_state),
        ]:
            if (
                isinstance(section_data, dict)
                and section_data.get("status") == "unavailable"
            ):
                items.append(
                    {
                        "priority": "LOW",
                        "category": "stale_data",
                        "description": f"{section_name} data unavailable: {section_data.get('reason', 'unknown')}",
                        "urgency": "Informational",
                    }
                )

        # 5. Regime change warning
        regime_name = regime.get("current_regime", "Unknown")
        transition_risk = regime.get("transition_risk", 0.0)
        if transition_risk > 0.3:
            items.append(
                {
                    "priority": "HIGH",
                    "category": "regime_change",
                    "description": f"Elevated regime transition risk ({transition_risk:.0%}) from {regime_name}",
                    "urgency": "Review portfolio positioning",
                }
            )

        # Sort by priority
        items.sort(key=lambda x: _PRIORITY_ORDER.get(x.get("priority", "LOW"), 99))

        return items

    # -------------------------------------------------------------------------
    # Macro narrative generation
    # -------------------------------------------------------------------------

    def _generate_macro_narrative(
        self,
        agent_views: list[dict] | dict,
        regime: dict,
        top_signals: list[dict] | dict,
        portfolio_state: dict,
        briefing_date: date,
    ) -> str:
        """Generate a 4-5 paragraph analytical brief.

        Attempts LLM generation via Claude API (ANTHROPIC_API_KEY).
        Falls back to template-based narrative on any failure.

        Args:
            agent_views: Agent views section.
            regime: Regime info section.
            top_signals: Top signals section.
            portfolio_state: Portfolio state section.
            briefing_date: Briefing date.

        Returns:
            Multi-paragraph narrative string.
        """
        # Always build template as fallback
        template_narrative = self._template_narrative(
            agent_views, regime, top_signals, portfolio_state, briefing_date
        )

        # Attempt LLM generation
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            try:
                import httpx

                # Build context for the LLM
                context_parts = [
                    f"Date: {briefing_date}",
                    f"Regime: {regime.get('current_regime', 'Unknown')}",
                ]

                if isinstance(agent_views, list):
                    for av in agent_views:
                        context_parts.append(
                            f"Agent {av.get('agent_id', '?')}: "
                            f"{av.get('signal_direction', 'NEUTRAL')} "
                            f"(conviction {av.get('conviction', 0):.2f})"
                        )

                if isinstance(top_signals, list):
                    for sig in top_signals[:5]:
                        context_parts.append(
                            f"Signal {sig.get('instrument', '?')}: "
                            f"{sig.get('direction', 'NEUTRAL')} "
                            f"(conviction {sig.get('conviction', 0):.2f})"
                        )

                if isinstance(portfolio_state, dict) and "summary" in portfolio_state:
                    summary = portfolio_state["summary"]
                    context_parts.append(
                        f"Portfolio: {summary.get('open_positions', 0)} positions, "
                        f"leverage {summary.get('leverage', 0):.2f}x, "
                        f"P&L today {summary.get('pnl_today_brl', 0):,.0f} BRL"
                    )

                context_str = "\n".join(context_parts)

                prompt = (
                    "You are a macro research analyst at a Brazilian macro hedge fund. "
                    "Write a 4-5 paragraph analytical brief (~400 words) for the morning "
                    "briefing that connects dots across the agent views, regime classification, "
                    "signal dashboard, and portfolio state. Use a research-note style: "
                    "objective, data-driven, forward-looking. Highlight key risks and "
                    "opportunities. Do not use bullet points.\n\n"
                    f"Context:\n{context_str}"
                )

                response = httpx.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 1024,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                    timeout=15.0,
                )
                response.raise_for_status()
                data = response.json()
                llm_text = data.get("content", [{}])[0].get("text", "")
                if llm_text.strip():
                    return llm_text.strip()
            except Exception:
                logger.debug(
                    "llm_narrative_fallback", reason="LLM call failed, using template"
                )

        return template_narrative

    def _template_narrative(
        self,
        agent_views: list[dict] | dict,
        regime: dict,
        top_signals: list[dict] | dict,
        portfolio_state: dict,
        briefing_date: date,
    ) -> str:
        """Generate a template-based narrative from available data points.

        Produces a 4-5 paragraph analytical brief by concatenating key
        data points into a coherent structure.

        Args:
            agent_views: Agent views section.
            regime: Regime info section.
            top_signals: Top signals section.
            portfolio_state: Portfolio state section.
            briefing_date: Briefing date.

        Returns:
            Multi-paragraph narrative string.
        """
        paragraphs: list[str] = []

        # Paragraph 1: Regime and macro environment
        regime_name = regime.get("current_regime", "Unknown")
        probs = regime.get("probabilities", {})
        top_prob = max(probs.values()) if probs else 0
        paragraphs.append(
            f"As of {briefing_date}, the macro regime is classified as {regime_name} "
            f"with {top_prob:.0%} probability. "
            f"The regime assessment reflects the current balance of growth, inflation, "
            f"and monetary policy dynamics across developed and emerging markets. "
            f"Transition risk stands at {regime.get('transition_risk', 0):.0%}, "
            f"suggesting {'elevated caution' if regime.get('transition_risk', 0) > 0.3 else 'a stable macro backdrop'} "
            f"for position management."
        )

        # Paragraph 2: Agent consensus and divergence
        if isinstance(agent_views, list) and agent_views:
            directions = [av.get("signal_direction", "NEUTRAL") for av in agent_views]
            long_count = sum(1 for d in directions if d == "LONG")
            short_count = sum(1 for d in directions if d == "SHORT")
            neutral_count = sum(1 for d in directions if d == "NEUTRAL")
            avg_conviction = sum(av.get("conviction", 0) for av in agent_views) / len(
                agent_views
            )

            paragraphs.append(
                f"Across the analytical agent complex, the directional split is "
                f"{long_count} bullish, {short_count} bearish, and {neutral_count} neutral "
                f"with average conviction at {avg_conviction:.2f}. "
                f"{'Strong consensus ' if long_count >= 4 or short_count >= 4 else 'Divergent views '}"
                f"{'warrants attention to crowding risk.' if long_count >= 4 or short_count >= 4 else 'suggest a differentiated approach.'}"  # noqa: E501
            )
        else:
            paragraphs.append(
                "Agent views are currently unavailable. The briefing relies on "
                "signal and portfolio data for directional guidance."
            )

        # Paragraph 3: Signal landscape
        if isinstance(top_signals, list) and top_signals:
            top_3 = top_signals[:3]
            signal_desc = "; ".join(
                f"{s.get('instrument', '?')} ({s.get('direction', '?')}, {s.get('conviction', 0):.2f})"
                for s in top_3
            )
            paragraphs.append(
                f"The signal dashboard highlights the following top-conviction opportunities: "
                f"{signal_desc}. "
                f"A total of {len(top_signals)} signals are active across asset classes, "
                f"reflecting the breadth of systematic coverage."
            )
        else:
            paragraphs.append(
                "The signal pipeline has no active signals above threshold at this time. "
                "This may indicate a low-conviction environment or pending data refresh."
            )

        # Paragraph 4: Portfolio positioning and risk
        if isinstance(portfolio_state, dict) and "summary" in portfolio_state:
            summary = portfolio_state["summary"]
            paragraphs.append(
                f"The portfolio currently holds {summary.get('open_positions', 0)} open positions "
                f"with total leverage of {summary.get('leverage', 0):.2f}x. "
                f"Today's P&L stands at {summary.get('pnl_today_brl', 0):,.0f} BRL, "
                f"with MTD at {summary.get('pnl_mtd_brl', 0):,.0f} BRL and "
                f"YTD at {summary.get('pnl_ytd_brl', 0):,.0f} BRL. "
                f"Unrealized P&L across open positions is "
                f"{summary.get('total_unrealized_pnl_brl', 0):,.0f} BRL."
            )
        else:
            paragraphs.append(
                "Portfolio state data is unavailable for this briefing. "
                "Position and P&L metrics will be updated once the position manager is connected."
            )

        # Paragraph 5: Forward-looking risk assessment
        paragraphs.append(
            f"Looking ahead, portfolio managers should monitor regime transition signals "
            f"and any divergence between agent views and realized market moves. "
            f"Key risks include "
            f"{'macro regime shift' if regime.get('transition_risk', 0) > 0.2 else 'idiosyncratic position risk'}, "
            f"and the focus for today should be on reviewing pending action items "
            f"and aligning position sizing with current conviction levels."
        )

        return "\n\n".join(paragraphs)

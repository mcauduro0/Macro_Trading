"""DailyReportGenerator with 7 sections in markdown, HTML, email, and Slack formats.

Generates a comprehensive daily report covering:
1. Market Snapshot — key levels and changes
2. Regime Assessment — current regime and transition risk
3. Agent Views — per-agent signal summary
4. Signal Summary — aggregated signals and anomalies
5. Portfolio Status — positions, weights, and P&L
6. Risk Metrics — VaR, stress tests, limits
7. Action Items — concrete trade recommendations

All sections require real pipeline_context data. When data is missing,
sections explicitly report "data unavailable" instead of showing fake values.
"""

import json
import logging
import os
import smtplib
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from src.reporting import templates

logger = logging.getLogger("daily_report")


@dataclass
class ReportSection:
    """A single section of the daily report."""

    title: str
    content: dict[str, Any]
    charts: list[str] = field(default_factory=list)
    commentary: str = ""


class DailyReportGenerator:
    """Generates comprehensive daily trading reports with 7 sections.

    Requires a pipeline_context dict populated by the daily pipeline with
    real data from agents, strategies, PMS, and risk engine. Will not
    generate reports with fake/placeholder data.
    """

    def __init__(self, as_of_date: date | None = None):
        self.as_of_date = as_of_date or date.today()
        self.sections: dict[str, ReportSection] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, pipeline_context: dict | None = None) -> dict:
        """Build all 7 sections. Returns dict of section_key -> ReportSection.

        Args:
            pipeline_context: Dict with real data from the daily pipeline.
                Required keys: market_snapshot, regime, agent_views, signals,
                portfolio, risk, actions. Missing keys will produce sections
                with explicit "data unavailable" content.

        Raises:
            ValueError: If pipeline_context is None (no data provided).
        """
        if pipeline_context is None:
            raise ValueError(
                "pipeline_context is required. Run the daily pipeline first to "
                "collect real market data, agent views, signals, portfolio state, "
                "and risk metrics. Report generation requires real data."
            )

        ctx = pipeline_context

        self.sections["market_snapshot"] = self._build_market_snapshot(ctx)
        self.sections["regime"] = self._build_regime(ctx)
        self.sections["agent_views"] = self._build_agent_views(ctx)
        self.sections["signals"] = self._build_signals(ctx)
        self.sections["portfolio"] = self._build_portfolio(ctx)
        self.sections["risk"] = self._build_risk(ctx)
        self.sections["actions"] = self._build_actions(ctx)

        return self.sections

    def to_markdown(self) -> str:
        """Render the report as formatted markdown."""
        if not self.sections:
            raise RuntimeError("Call generate() with real pipeline data first.")
        return templates.render_markdown(self.sections)

    def to_html(self) -> str:
        """Render the report as professional HTML with embedded charts."""
        if not self.sections:
            raise RuntimeError("Call generate() with real pipeline data first.")

        charts: dict[str, str] = {}
        try:
            charts = self._generate_charts()
        except Exception:
            logger.warning("Chart generation failed, proceeding without charts")

        return templates.render_html(self.sections, charts)

    def send_email(self, recipients: list[str] | None = None) -> bool:
        """Send the full HTML report via SMTP email."""
        smtp_host = os.environ.get("SMTP_HOST")
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        smtp_user = os.environ.get("SMTP_USER")
        smtp_pass = os.environ.get("SMTP_PASS")
        default_recipients = os.environ.get("ALERT_RECIPIENTS", "").split(",")
        recipients = recipients or [r.strip() for r in default_recipients if r.strip()]

        if not smtp_host or not recipients:
            logger.warning("SMTP not configured or no recipients; skipping email")
            return False

        html = self.to_html()

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Macro Trading Daily Report - {self.as_of_date}"
        msg["From"] = smtp_user or "macro-trading@system.local"
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(html, "html"))

        try:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.sendmail(msg["From"], recipients, msg.as_string())
            logger.info("Daily report emailed to %s", recipients)
            return True
        except Exception as exc:
            logger.error("Email send failed: %s", exc)
            return False

    def send_slack(self, webhook_url: str | None = None) -> bool:
        """Send a condensed summary to Slack with a link to the full report."""
        url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL")
        if not url:
            logger.warning("No Slack webhook URL configured; skipping Slack")
            return False

        if not self.sections:
            raise RuntimeError("Call generate() with real pipeline data first.")

        summary = self._build_slack_summary()
        blocks = templates.render_slack_blocks(summary)
        payload = json.dumps({"blocks": blocks}).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                logger.info("Slack summary sent: %s", resp.status)
            return True
        except Exception as exc:
            logger.error("Slack send failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Section builders — require real data, no hardcoded defaults
    # ------------------------------------------------------------------

    def _build_market_snapshot(self, ctx: dict) -> ReportSection:
        market = ctx.get("market_snapshot", {})
        if not market:
            return ReportSection(
                title="Market Snapshot",
                content={
                    "status": "Data unavailable — run daily pipeline to collect market data"
                },
                commentary="Market snapshot data not yet collected for this date.",
            )
        return ReportSection(
            title="Market Snapshot",
            content={
                "date": str(self.as_of_date),
                **{k: v for k, v in market.items() if k != "commentary"},
            },
            commentary=market.get("commentary", ""),
        )

    def _build_regime(self, ctx: dict) -> ReportSection:
        regime = ctx.get("regime", {})
        if not regime:
            return ReportSection(
                title="Regime Assessment",
                content={
                    "status": "Data unavailable — run cross-asset agent to classify regime"
                },
                commentary="Regime classification not yet run for this date.",
            )
        return ReportSection(
            title="Regime Assessment",
            content={
                "Current Regime": regime.get("classification", "Unknown"),
                "Confidence": regime.get("confidence", "N/A"),
                "Probabilities": regime.get("probabilities", "N/A"),
                "Key Drivers": regime.get("drivers", "N/A"),
                "Transition Risk": regime.get("transition_risk", "N/A"),
            },
            commentary=regime.get("commentary", ""),
        )

    def _build_agent_views(self, ctx: dict) -> ReportSection:
        agents = ctx.get("agent_views", {})
        if not agents:
            return ReportSection(
                title="Agent Views",
                content={
                    "status": "Data unavailable — run analytical agents to generate views"
                },
                commentary="Agent views not yet generated for this date.",
            )
        return ReportSection(
            title="Agent Views",
            content=agents.get("table", agents),
            commentary=agents.get("commentary", ""),
        )

    def _build_signals(self, ctx: dict) -> ReportSection:
        signals = ctx.get("signals", {})
        if not signals:
            return ReportSection(
                title="Signal Summary",
                content={
                    "status": "Data unavailable — run signal aggregation pipeline"
                },
                commentary="Signal aggregation not yet run for this date.",
            )
        return ReportSection(
            title="Signal Summary",
            content={
                "Total Signals": signals.get("total", "N/A"),
                "Bullish": signals.get("bullish", "N/A"),
                "Bearish": signals.get("bearish", "N/A"),
                "Neutral": signals.get("neutral", "N/A"),
                "Signal Flips (24h)": signals.get("flips", "N/A"),
                "Crowding Warnings": signals.get("crowding_warnings", "N/A"),
                "Top Signal": signals.get("top_signal", "N/A"),
            },
            commentary=signals.get("commentary", ""),
        )

    def _build_portfolio(self, ctx: dict) -> ReportSection:
        portfolio = ctx.get("portfolio", {})
        if not portfolio:
            return ReportSection(
                title="Portfolio Status",
                content={"status": "Data unavailable — PMS portfolio data not loaded"},
                commentary="Portfolio data not available. Ensure PMS is configured.",
            )
        return ReportSection(
            title="Portfolio Status",
            content={
                "NAV": portfolio.get("nav", "N/A"),
                "Daily P&L": portfolio.get("daily_pnl", "N/A"),
                "MTD Return": portfolio.get("mtd", "N/A"),
                "YTD Return": portfolio.get("ytd", "N/A"),
                "Positions": portfolio.get("n_positions", "N/A"),
                "Gross Leverage": portfolio.get("gross_leverage", "N/A"),
                "Net Leverage": portfolio.get("net_leverage", "N/A"),
                "Rebalance Needed": portfolio.get("rebalance_needed", "N/A"),
            },
            commentary=portfolio.get("commentary", ""),
        )

    def _build_risk(self, ctx: dict) -> ReportSection:
        risk = ctx.get("risk", {})
        if not risk:
            return ReportSection(
                title="Risk Metrics",
                content={
                    "status": "Data unavailable — run risk engine to compute metrics"
                },
                commentary="Risk metrics not yet computed for this date.",
            )
        return ReportSection(
            title="Risk Metrics",
            content={
                "VaR 95%": risk.get("var_95", "N/A"),
                "VaR 99%": risk.get("var_99", "N/A"),
                "CVaR 95%": risk.get("cvar_95", "N/A"),
                "Worst Stress Scenario": risk.get("worst_stress", "N/A"),
                "Limit Utilization": risk.get("limit_util", "N/A"),
                "Limits Breached": risk.get("limits_breached", "N/A"),
                "Circuit Breaker": risk.get("circuit_breaker", "N/A"),
                "Risk Budget Remaining": risk.get("risk_budget", "N/A"),
            },
            commentary=risk.get("commentary", ""),
        )

    def _build_actions(self, ctx: dict) -> ReportSection:
        actions = ctx.get("actions", {})
        if not actions:
            return ReportSection(
                title="Action Items",
                content={"status": "No action items — pipeline data not available"},
                commentary="Action items will be generated once the full pipeline runs.",
            )
        return ReportSection(
            title="Action Items",
            content=actions.get("table", actions),
            commentary=actions.get("commentary", ""),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_slack_summary(self) -> dict:
        """Build condensed summary dict for Slack."""
        portfolio = self.sections.get("portfolio")
        risk = self.sections.get("risk")
        regime = self.sections.get("regime")
        signals = self.sections.get("signals")
        actions = self.sections.get("actions")

        top_signals_list = []
        if signals and "status" not in signals.content:
            top_signals_list.append(f"Top: {signals.content.get('Top Signal', 'N/A')}")
            bullish = signals.content.get("Bullish", 0)
            bearish = signals.content.get("Bearish", 0)
            top_signals_list.append(f"Bullish: {bullish} | Bearish: {bearish}")

        action_count = 0
        if actions and "Priority" in actions.content:
            action_count = len(actions.content["Priority"])

        return {
            "report_date": str(self.as_of_date),
            "portfolio_return": (
                portfolio.content.get("Daily P&L", "N/A")
                if portfolio and "status" not in portfolio.content
                else "N/A"
            ),
            "var_95": (
                risk.content.get("VaR 95%", "N/A")
                if risk and "status" not in risk.content
                else "N/A"
            ),
            "regime": (
                regime.content.get("Current Regime", "N/A")
                if regime and "status" not in regime.content
                else "N/A"
            ),
            "risk_status": (
                risk.content.get("Circuit Breaker", "N/A")
                if risk and "status" not in risk.content
                else "N/A"
            ),
            "top_signals": "\n".join(top_signals_list) if top_signals_list else "N/A",
            "action_count": action_count,
            "report_url": os.environ.get(
                "REPORT_BASE_URL", "http://localhost:8000/api/v1/reports/daily/latest"
            ),
        }

    def _generate_charts(self) -> dict[str, str]:
        """Generate base64-encoded PNG charts from real portfolio data.

        Charts are generated from actual portfolio equity curve and risk
        metrics stored in the report sections. Returns empty dict if
        matplotlib is unavailable or data is insufficient.
        """
        import base64
        import io

        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        charts: dict[str, str] = {}

        # Portfolio equity curve from real data
        portfolio_section = self.sections.get("portfolio")
        if portfolio_section and "status" not in portfolio_section.content:
            equity_data = portfolio_section.content.get("equity_curve")
            if equity_data and len(equity_data) >= 5:
                fig, ax = plt.subplots(figsize=(7, 3))
                ax.plot(
                    range(len(equity_data)), equity_data, color="#2563eb", linewidth=1.5
                )
                ax.fill_between(
                    range(len(equity_data)),
                    equity_data,
                    min(equity_data),
                    alpha=0.1,
                    color="#2563eb",
                )
                ax.set_title("Equity Curve (YTD)", fontsize=12)
                ax.set_ylabel("NAV Index")
                ax.grid(alpha=0.3)
                fig.tight_layout()
                buf = io.BytesIO()
                fig.savefig(buf, format="png", dpi=100)
                plt.close(fig)
                buf.seek(0)
                charts["portfolio"] = base64.b64encode(buf.read()).decode()

        # Risk VaR history from real data
        risk_section = self.sections.get("risk")
        if risk_section and "status" not in risk_section.content:
            var_history = risk_section.content.get("var_history")
            if var_history and len(var_history) >= 5:
                fig, ax = plt.subplots(figsize=(7, 2.5))
                ax.plot(var_history, color="#dc2626", linewidth=1.5, label="VaR 95%")
                ax.axhline(
                    0.05, color="#d97706", linestyle="--", linewidth=1, label="Limit"
                )
                ax.set_title("VaR 95% (60-day)", fontsize=12)
                ax.legend(fontsize=9)
                ax.grid(alpha=0.3)
                fig.tight_layout()
                buf = io.BytesIO()
                fig.savefig(buf, format="png", dpi=100)
                plt.close(fig)
                buf.seek(0)
                charts["risk"] = base64.b64encode(buf.read()).decode()

        return charts

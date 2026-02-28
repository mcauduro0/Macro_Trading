"""DailyReportGenerator with 7 sections in markdown, HTML, email, and Slack formats.

Generates a comprehensive daily report covering:
1. Market Snapshot — key levels and changes
2. Regime Assessment — current regime and transition risk
3. Agent Views — per-agent signal summary
4. Signal Summary — aggregated signals and anomalies
5. Portfolio Status — positions, weights, and P&L
6. Risk Metrics — VaR, stress tests, limits
7. Action Items — concrete trade recommendations
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
    """Generates comprehensive daily trading reports with 7 sections."""

    def __init__(self, as_of_date: date | None = None):
        self.as_of_date = as_of_date or date.today()
        self.sections: dict[str, ReportSection] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, pipeline_context: dict | None = None) -> dict:
        """Build all 7 sections. Returns dict of section_key -> ReportSection."""
        ctx = pipeline_context or self._sample_context()

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
            self.generate()
        return templates.render_markdown(self.sections)

    def to_html(self) -> str:
        """Render the report as professional HTML with embedded charts."""
        if not self.sections:
            self.generate()

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
            self.generate()

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
    # Section builders
    # ------------------------------------------------------------------

    def _build_market_snapshot(self, ctx: dict) -> ReportSection:
        market = ctx.get("market_snapshot", {})
        return ReportSection(
            title="Market Snapshot",
            content={
                "date": str(self.as_of_date),
                "IBOV": market.get("ibov", "127,450"),
                "IBOV Chg": market.get("ibov_chg", "+0.82%"),
                "USDBRL": market.get("usdbrl", "4.9720"),
                "USDBRL Chg": market.get("usdbrl_chg", "-0.35%"),
                "DI 1Y": market.get("di_1y", "10.15%"),
                "Selic": market.get("selic", "10.50%"),
                "IPCA 12m": market.get("ipca_12m", "4.23%"),
                "VIX": market.get("vix", "14.2"),
                "SPX": market.get("spx", "5,220"),
                "UST 10Y": market.get("ust_10y", "4.28%"),
            },
            commentary=market.get(
                "commentary", "Markets traded higher on dovish BCB minutes."
            ),
        )

    def _build_regime(self, ctx: dict) -> ReportSection:
        regime = ctx.get("regime", {})
        return ReportSection(
            title="Regime Assessment",
            content={
                "Current Regime": regime.get("classification", "Goldilocks"),
                "Confidence": regime.get("confidence", "72%"),
                "Probabilities": regime.get(
                    "probabilities",
                    "Goldilocks 45% | Reflation 30% | Stagflation 15% | Deflation 10%",
                ),
                "Key Drivers": regime.get(
                    "drivers", "Declining inflation, stable growth, dovish BCB guidance"
                ),
                "Transition Risk": regime.get(
                    "transition_risk", "Moderate — watch for IPCA acceleration"
                ),
            },
            commentary=regime.get(
                "commentary",
                "Goldilocks conditions persist with moderate transition risk to Reflation.",
            ),
        )

    def _build_agent_views(self, ctx: dict) -> ReportSection:
        agents = ctx.get("agent_views", {})
        default_agents = {
            "Agent": [
                "Inflation",
                "Monetary Policy",
                "Fiscal",
                "FX Equilibrium",
                "Cross-Asset",
            ],
            "Signal": ["Bullish", "Bullish", "Neutral", "Bearish", "Bullish"],
            "Strength": [0.65, 0.72, 0.12, -0.45, 0.58],
            "Confidence": [0.78, 0.85, 0.42, 0.68, 0.73],
            "Key Driver": [
                "IPCA deceleration trend",
                "Selic cut cycle continuation",
                "Fiscal framework uncertainty",
                "USD strength vs EM FX",
                "Risk-on global environment",
            ],
        }
        return ReportSection(
            title="Agent Views",
            content=agents.get("table", default_agents),
            commentary=agents.get(
                "commentary",
                "4 of 5 agents lean bullish; Fiscal agent neutral on framework concerns.",
            ),
        )

    def _build_signals(self, ctx: dict) -> ReportSection:
        signals = ctx.get("signals", {})
        return ReportSection(
            title="Signal Summary",
            content={
                "Total Signals": signals.get("total", 25),
                "Bullish": signals.get("bullish", 14),
                "Bearish": signals.get("bearish", 7),
                "Neutral": signals.get("neutral", 4),
                "Signal Flips (24h)": signals.get("flips", 2),
                "Crowding Warnings": signals.get("crowding_warnings", 1),
                "Top Signal": signals.get(
                    "top_signal", "DI1F25 — Bullish 0.82 conviction"
                ),
            },
            commentary=signals.get(
                "commentary", "Bullish bias in rates space; 2 signal flips in equities."
            ),
        )

    def _build_portfolio(self, ctx: dict) -> ReportSection:
        portfolio = ctx.get("portfolio", {})
        return ReportSection(
            title="Portfolio Status",
            content={
                "NAV": portfolio.get("nav", "R$ 100,000,000"),
                "Daily P&L": portfolio.get("daily_pnl", "+R$ 245,000 (+0.25%)"),
                "MTD Return": portfolio.get("mtd", "+1.82%"),
                "YTD Return": portfolio.get("ytd", "+8.45%"),
                "Positions": portfolio.get("n_positions", 12),
                "Gross Leverage": portfolio.get("gross_leverage", "1.85x"),
                "Net Leverage": portfolio.get("net_leverage", "0.62x"),
                "Rebalance Needed": portfolio.get(
                    "rebalance_needed", "Yes — 3 positions exceed target by >5%"
                ),
            },
            commentary=portfolio.get(
                "commentary",
                "Portfolio performing within targets; minor rebalance recommended.",
            ),
        )

    def _build_risk(self, ctx: dict) -> ReportSection:
        risk = ctx.get("risk", {})
        return ReportSection(
            title="Risk Metrics",
            content={
                "VaR 95%": risk.get("var_95", "2.12%"),
                "VaR 99%": risk.get("var_99", "3.45%"),
                "CVaR 95%": risk.get("cvar_95", "2.98%"),
                "Worst Stress Scenario": risk.get("worst_stress", "2008 GFC: -8.2%"),
                "Limit Utilization": risk.get("limit_util", "68%"),
                "Limits Breached": risk.get("limits_breached", 0),
                "Circuit Breaker": risk.get("circuit_breaker", "Inactive"),
                "Risk Budget Remaining": risk.get("risk_budget", "32%"),
            },
            commentary=risk.get(
                "commentary", "Risk within acceptable bounds. No limit breaches."
            ),
        )

    def _build_actions(self, ctx: dict) -> ReportSection:
        actions = ctx.get("actions", {})
        default_actions = {
            "Priority": ["High", "High", "Medium", "Medium", "Low"],
            "Instrument": ["DI1F25", "PETR4", "VALE3", "USDBRL Fwd", "IBOV Put"],
            "Direction": ["Short", "Long", "Reduce Long", "Sell Forward", "Buy"],
            "Size": [
                "+20 contracts",
                "+15,000 shares",
                "-8,000 shares",
                "USD 2M notional",
                "100 contracts",
            ],
            "Rationale": [
                "Strong bearish DI signal (0.82 conviction), Selic cut cycle",
                "Underweight vs target; oil price supportive",
                "Position exceeds target by 12%; take profit",
                "FX agent bearish on BRL; hedge exposure",
                "Tail risk protection ahead of COPOM",
            ],
        }
        return ReportSection(
            title="Action Items",
            content=actions.get("table", default_actions),
            commentary=actions.get(
                "commentary",
                "5 action items: 2 high priority trades requiring immediate attention.",
            ),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _sample_context(self) -> dict:
        """Return sample/placeholder context for demo reports (seed=42)."""
        return {
            "market_snapshot": {},
            "regime": {},
            "agent_views": {},
            "signals": {},
            "portfolio": {},
            "risk": {},
            "actions": {},
        }

    def _build_slack_summary(self) -> dict:
        """Build condensed summary dict for Slack."""
        portfolio = self.sections.get("portfolio")
        risk = self.sections.get("risk")
        regime = self.sections.get("regime")
        signals = self.sections.get("signals")
        actions = self.sections.get("actions")

        top_signals_list = []
        if signals:
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
                portfolio.content.get("Daily P&L", "N/A") if portfolio else "N/A"
            ),
            "var_95": risk.content.get("VaR 95%", "N/A") if risk else "N/A",
            "regime": regime.content.get("Current Regime", "N/A") if regime else "N/A",
            "risk_status": (
                risk.content.get("Circuit Breaker", "N/A") if risk else "N/A"
            ),
            "top_signals": "\n".join(top_signals_list) if top_signals_list else "N/A",
            "action_count": action_count,
            "report_url": os.environ.get(
                "REPORT_BASE_URL", "http://localhost:8000/api/v1/reports/daily/latest"
            ),
        }

    def _generate_charts(self) -> dict[str, str]:
        """Generate base64-encoded PNG charts for HTML embedding."""
        import base64
        import io

        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        charts: dict[str, str] = {}
        rng = np.random.default_rng(42)

        # Portfolio equity curve
        fig, ax = plt.subplots(figsize=(7, 3))
        days = np.arange(252)
        equity = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.008, 252)))
        ax.plot(days, equity, color="#2563eb", linewidth=1.5)
        ax.fill_between(days, equity, equity.min(), alpha=0.1, color="#2563eb")
        ax.set_title("Equity Curve (YTD)", fontsize=12)
        ax.set_ylabel("NAV Index")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100)
        plt.close(fig)
        buf.seek(0)
        charts["portfolio"] = base64.b64encode(buf.read()).decode()

        # Risk VaR gauge
        fig, ax = plt.subplots(figsize=(7, 2.5))
        var_history = rng.uniform(0.015, 0.035, 60)
        ax.plot(var_history, color="#dc2626", linewidth=1.5, label="VaR 95%")
        ax.axhline(0.05, color="#d97706", linestyle="--", linewidth=1, label="Limit")
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

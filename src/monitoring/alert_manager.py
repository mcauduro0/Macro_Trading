"""AlertManager -- evaluates alert rules and dispatches notifications.

Provides:
- 30-minute cooldown per alert type to prevent notification flooding
- Dual-channel dispatch: Slack (Block Kit) + email (HTML) for all alerts
- Runtime rule configuration (enable/disable, threshold updates)
- Active alert tracking within cooldown windows
"""

from __future__ import annotations

import json
import os
import smtplib
import urllib.request
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import structlog

from src.monitoring.alert_rules import DEFAULT_RULES, AlertRule

logger = structlog.get_logger("alert_manager")


class AlertManager:
    """Evaluate alert rules and dispatch notifications to Slack and email.

    Parameters:
        rules: List of ``AlertRule`` instances (defaults to ``DEFAULT_RULES``).
        slack_webhook_url: Slack Incoming Webhook URL.  Falls back to
            ``SLACK_WEBHOOK_URL`` environment variable.
        email_config: SMTP configuration dict.  Falls back to environment
            variables (``SMTP_HOST``, ``SMTP_PORT``, ``SMTP_USER``,
            ``SMTP_PASS``, ``ALERT_RECIPIENTS``).
    """

    def __init__(
        self,
        rules: list[AlertRule] | None = None,
        slack_webhook_url: str | None = None,
        email_config: dict | None = None,
    ):
        self.rules: dict[str, AlertRule] = {
            r.rule_id: r for r in (rules or DEFAULT_RULES)
        }
        self.slack_webhook_url = slack_webhook_url or os.environ.get(
            "SLACK_WEBHOOK_URL"
        )
        self.email_config = email_config or self._load_email_config()
        self._last_fired: dict[str, datetime] = {}  # rule_id -> last fire time
        self._active_alerts: list[dict[str, Any]] = []
        self._logger = logger

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        """Evaluate all enabled rules against *context*.

        For each rule that fires and is not in cooldown, an alert dict is
        created and dispatched to both Slack and email.  Returns the list
        of fired alert dicts.
        """
        fired: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        for rule_id, rule in self.rules.items():
            if not rule.enabled:
                continue

            # Inject threshold into context so check_fn can use it
            ctx = {**context, "_threshold": rule.threshold}

            try:
                triggered = rule.check_fn(ctx)
            except Exception as exc:
                self._logger.warning(
                    "rule_check_error", rule_id=rule_id, error=str(exc)
                )
                continue

            if not triggered:
                continue

            if self._in_cooldown(rule_id):
                self._logger.debug(
                    "rule_in_cooldown", rule_id=rule_id
                )
                continue

            alert = {
                "rule_id": rule_id,
                "name": rule.name,
                "description": rule.description,
                "severity": rule.severity,
                "threshold": rule.threshold,
                "timestamp": now.isoformat(),
                "fired_at": now,
            }

            # Dispatch to both channels per user decision
            self.send_slack(alert)
            self.send_email(alert)

            self._last_fired[rule_id] = now
            self._active_alerts.append(alert)
            fired.append(alert)

            self._logger.info(
                "alert_fired",
                rule_id=rule_id,
                severity=rule.severity,
                name=rule.name,
            )

        return fired

    def send_slack(self, alert: dict[str, Any]) -> bool:
        """POST alert to Slack via Incoming Webhook with Block Kit formatting.

        Returns ``True`` on success, ``False`` on failure (logged, no crash).
        """
        if not self.slack_webhook_url:
            self._logger.warning(
                "slack_not_configured",
                msg="SLACK_WEBHOOK_URL not set -- skipping Slack dispatch",
            )
            return False

        severity_emoji = ":red_circle:" if alert["severity"] == "critical" else ":warning:"
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{severity_emoji} Alert: {alert['name']}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Severity:* {alert['severity'].upper()}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Rule:* {alert['rule_id']}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Threshold:* {alert['threshold']}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Time:* {alert['timestamp']}",
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"_{alert['description']}_",
                },
            },
        ]

        payload = json.dumps({"blocks": blocks}).encode("utf-8")
        req = urllib.request.Request(
            self.slack_webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                self._logger.info(
                    "slack_sent",
                    rule_id=alert["rule_id"],
                    status=resp.status,
                )
                return True
        except Exception as exc:
            self._logger.error(
                "slack_send_failed",
                rule_id=alert["rule_id"],
                error=str(exc),
            )
            return False

    def send_email(self, alert: dict[str, Any]) -> bool:
        """Send alert via SMTP as an HTML email.

        Returns ``True`` on success, ``False`` on failure (graceful fallback).
        """
        cfg = self.email_config
        if not cfg.get("host"):
            self._logger.warning(
                "email_not_configured",
                msg="SMTP_HOST not set -- skipping email dispatch",
            )
            return False

        recipients = cfg.get("recipients", [])
        if not recipients:
            self._logger.warning(
                "email_no_recipients",
                msg="ALERT_RECIPIENTS not set -- skipping email dispatch",
            )
            return False

        severity_color = "#dc3545" if alert["severity"] == "critical" else "#ffc107"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: {severity_color}; color: white; padding: 16px; border-radius: 4px 4px 0 0;">
                <h2 style="margin: 0;">Alert: {alert['name']}</h2>
            </div>
            <div style="padding: 16px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 4px 4px;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 8px; font-weight: bold;">Severity</td>
                    <td style="padding: 8px;">{alert['severity'].upper()}</td></tr>
                    <tr><td style="padding: 8px; font-weight: bold;">Rule</td>
                    <td style="padding: 8px;">{alert['rule_id']}</td></tr>
                    <tr><td style="padding: 8px; font-weight: bold;">Threshold</td>
                    <td style="padding: 8px;">{alert['threshold']}</td></tr>
                    <tr><td style="padding: 8px; font-weight: bold;">Time</td>
                    <td style="padding: 8px;">{alert['timestamp']}</td></tr>
                </table>
                <p style="margin-top: 16px; color: #666;">{alert['description']}</p>
            </div>
            <p style="font-size: 11px; color: #999; text-align: center;">Generated by Macro Trading Alert System</p>
        </body>
        </html>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[{alert['severity'].upper()}] {alert['name']} - Macro Trading Alert"
        msg["From"] = cfg.get("user", "alerts@macrotrading.local")
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(html_body, "html"))

        try:
            port = int(cfg.get("port", 587))
            with smtplib.SMTP(cfg["host"], port, timeout=10) as server:
                if port == 587:
                    server.starttls()
                user = cfg.get("user")
                password = cfg.get("password")
                if user and password:
                    server.login(user, password)
                server.sendmail(msg["From"], recipients, msg.as_string())
            self._logger.info(
                "email_sent",
                rule_id=alert["rule_id"],
                recipients=len(recipients),
            )
            return True
        except Exception as exc:
            self._logger.error(
                "email_send_failed",
                rule_id=alert["rule_id"],
                error=str(exc),
            )
            return False

    def enable_rule(self, rule_id: str) -> None:
        """Enable a rule at runtime."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
            self._logger.info("rule_enabled", rule_id=rule_id)
        else:
            raise KeyError(f"Unknown rule: {rule_id}")

    def disable_rule(self, rule_id: str) -> None:
        """Disable a rule at runtime."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
            self._logger.info("rule_disabled", rule_id=rule_id)
        else:
            raise KeyError(f"Unknown rule: {rule_id}")

    def update_threshold(self, rule_id: str, threshold: float) -> None:
        """Update a rule's threshold at runtime."""
        if rule_id in self.rules:
            old = self.rules[rule_id].threshold
            self.rules[rule_id].threshold = threshold
            self._logger.info(
                "threshold_updated",
                rule_id=rule_id,
                old=old,
                new=threshold,
            )
        else:
            raise KeyError(f"Unknown rule: {rule_id}")

    def get_active_alerts(self) -> list[dict[str, Any]]:
        """Return alerts fired within their cooldown window (still active)."""
        now = datetime.now(timezone.utc)
        active: list[dict[str, Any]] = []
        for alert in self._active_alerts:
            rule_id = alert["rule_id"]
            rule = self.rules.get(rule_id)
            if rule is None:
                continue
            cooldown = timedelta(minutes=rule.cooldown_minutes)
            fired_at = alert.get("fired_at")
            if fired_at and (now - fired_at) < cooldown:
                # Return serializable copy (no datetime objects)
                serializable = {
                    k: v for k, v in alert.items() if k != "fired_at"
                }
                active.append(serializable)
        return active

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _in_cooldown(self, rule_id: str) -> bool:
        """Check if rule was fired within its cooldown window."""
        last = self._last_fired.get(rule_id)
        if last is None:
            return False
        rule = self.rules[rule_id]
        cooldown = timedelta(minutes=rule.cooldown_minutes)
        return (datetime.now(timezone.utc) - last) < cooldown

    def _load_email_config(self) -> dict[str, Any]:
        """Load SMTP configuration from environment variables."""
        recipients_raw = os.environ.get("ALERT_RECIPIENTS", "")
        recipients = [
            r.strip() for r in recipients_raw.split(",") if r.strip()
        ]
        return {
            "host": os.environ.get("SMTP_HOST", ""),
            "port": os.environ.get("SMTP_PORT", "587"),
            "user": os.environ.get("SMTP_USER", ""),
            "password": os.environ.get("SMTP_PASS", ""),
            "recipients": recipients,
        }

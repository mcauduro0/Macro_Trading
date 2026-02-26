"""Monitoring package -- alert management and system health monitoring.

Provides:
- AlertManager: Evaluates alert rules, dispatches notifications (Slack + email)
- AlertRule: Configurable alert rule dataclass
- DEFAULT_RULES: 10 pre-defined alert rules for the Macro Trading system
"""

from src.monitoring.alert_manager import AlertManager
from src.monitoring.alert_rules import DEFAULT_RULES, AlertRule

__all__ = ["AlertManager", "AlertRule", "DEFAULT_RULES"]

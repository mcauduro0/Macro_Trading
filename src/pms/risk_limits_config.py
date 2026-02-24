"""PMS risk limits configuration for the Risk Monitor dashboard.

Frozen dataclass PMSRiskLimits provides configurable thresholds for:
- VaR (95% and 99%) as % of AUM
- Gross and net leverage limits
- Drawdown warning and hard limits
- Concentration limits by asset class (% of gross notional)
- Warning threshold (percentage of limit before breach)

All limits use positive numbers (percentages or multiples).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PMSRiskLimits:
    """Configurable risk limits for the PMS Risk Monitor.

    Attributes:
        var_95_limit_pct: VaR 95% limit as % of AUM (positive).
        var_99_limit_pct: VaR 99% limit as % of AUM (positive).
        gross_leverage_limit: Maximum gross leverage (sum of abs notional / AUM).
        net_leverage_limit: Maximum net leverage (long - short notional / AUM).
        drawdown_warning_pct: Drawdown warning threshold (positive %).
        drawdown_limit_pct: Drawdown hard limit (positive %).
        concentration_limits: Max % of gross notional per asset class.
        warning_threshold_pct: Utilization % at which WARNING alerts fire.
    """

    # VaR limits (% of AUM, positive numbers)
    var_95_limit_pct: float = 2.0       # 2%
    var_99_limit_pct: float = 3.0       # 3%
    # Leverage
    gross_leverage_limit: float = 4.0   # 4x
    net_leverage_limit: float = 2.0     # 2x
    # Drawdown
    drawdown_warning_pct: float = 5.0   # -5% warning
    drawdown_limit_pct: float = 10.0    # -10% hard limit
    # Concentration by asset class (% of gross notional)
    concentration_limits: dict = field(default_factory=lambda: {
        "RATES": 60.0,
        "FX": 40.0,
        "INFLATION": 30.0,
        "SOVEREIGN": 20.0,
        "CREDIT": 20.0,
        "EQUITY": 30.0,
    })
    # Warning threshold (% of limit before breach)
    warning_threshold_pct: float = 80.0  # 80% = WARNING

    @classmethod
    def from_env(cls) -> PMSRiskLimits:
        """Create PMSRiskLimits from PMS_RISK_* environment variables.

        Reads environment variables with PMS_RISK_ prefix. Falls back to
        dataclass defaults when env vars are not set.

        Environment variables:
            PMS_RISK_VAR_95_LIMIT_PCT
            PMS_RISK_VAR_99_LIMIT_PCT
            PMS_RISK_GROSS_LEVERAGE_LIMIT
            PMS_RISK_NET_LEVERAGE_LIMIT
            PMS_RISK_DRAWDOWN_WARNING_PCT
            PMS_RISK_DRAWDOWN_LIMIT_PCT
            PMS_RISK_WARNING_THRESHOLD_PCT

        Returns:
            PMSRiskLimits configured from environment or defaults.
        """
        defaults = cls()
        return cls(
            var_95_limit_pct=float(
                os.environ.get("PMS_RISK_VAR_95_LIMIT_PCT", defaults.var_95_limit_pct)
            ),
            var_99_limit_pct=float(
                os.environ.get("PMS_RISK_VAR_99_LIMIT_PCT", defaults.var_99_limit_pct)
            ),
            gross_leverage_limit=float(
                os.environ.get("PMS_RISK_GROSS_LEVERAGE_LIMIT", defaults.gross_leverage_limit)
            ),
            net_leverage_limit=float(
                os.environ.get("PMS_RISK_NET_LEVERAGE_LIMIT", defaults.net_leverage_limit)
            ),
            drawdown_warning_pct=float(
                os.environ.get("PMS_RISK_DRAWDOWN_WARNING_PCT", defaults.drawdown_warning_pct)
            ),
            drawdown_limit_pct=float(
                os.environ.get("PMS_RISK_DRAWDOWN_LIMIT_PCT", defaults.drawdown_limit_pct)
            ),
            warning_threshold_pct=float(
                os.environ.get("PMS_RISK_WARNING_THRESHOLD_PCT", defaults.warning_threshold_pct)
            ),
        )

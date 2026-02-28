"""SOV_02: EM Sovereign Relative Value strategy.

Trades Brazil CDS based on cross-section regression of CDS levels vs
fundamental factors across 10 EM peers. The Brazil residual (actual CDS
minus model-predicted CDS) identifies mispricing:

- **Positive residual**: Brazil CDS is expensive relative to fundamentals =>
  SHORT CDS (sell protection, expect mean reversion).
- **Negative residual**: Brazil CDS is cheap => LONG CDS (buy protection).

The cross-section model uses OLS regression:
    CDS_level ~ debt_to_gdp + current_account + inflation + growth + political

Peer fundamentals are semi-static (updated periodically in code). The
strategy focuses on Brazil CDS dynamics vs its predicted fair value.

Entry threshold: |residual_z| >= 1.5.
Stop-loss: 20% of CDS level.
Take-profit: 15% of CDS level.
Holding period: 28 days.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import structlog

from src.agents.data_loader import PointInTimeDataLoader
from src.core.enums import AssetClass, Frequency, SignalDirection
from src.strategies.base import BaseStrategy, StrategyConfig, StrategySignal
from src.strategies.registry import StrategyRegistry

# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------
SOV_02_CONFIG = StrategyConfig(
    strategy_id="SOV_02",
    strategy_name="EM Sovereign Relative Value",
    asset_class=AssetClass.SOVEREIGN_CREDIT,
    instruments=["CDS_BR"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
    max_leverage=3.0,
    stop_loss_pct=0.20,
    take_profit_pct=0.15,
)

# ---------------------------------------------------------------------------
# Strategy parameters
# ---------------------------------------------------------------------------
_ENTRY_THRESHOLD = 1.5
_CDS_LOOKBACK = 1260
_ZSCORE_WINDOW = 252
_HOLDING_PERIOD = 28

# ---------------------------------------------------------------------------
# EM Peer fundamental profiles (semi-static, updated periodically)
# Each peer: {name, cds_approx, debt_to_gdp, current_account_pct,
#             inflation_yoy, growth_yoy, political_stability_score}
# Political stability: 0-100 where higher = more stable.
# CDS approx values are approximate recent 5Y CDS levels in bps.
# ---------------------------------------------------------------------------
EM_PEERS: list[dict] = [
    {
        "name": "Brazil",
        "cds_approx": 180,
        "debt_to_gdp": 78,
        "current_account_pct": -2.5,
        "inflation_yoy": 4.5,
        "growth_yoy": 2.5,
        "political_stability": 45,
    },
    {
        "name": "Mexico",
        "cds_approx": 120,
        "debt_to_gdp": 55,
        "current_account_pct": -1.0,
        "inflation_yoy": 4.0,
        "growth_yoy": 2.0,
        "political_stability": 50,
    },
    {
        "name": "Colombia",
        "cds_approx": 160,
        "debt_to_gdp": 60,
        "current_account_pct": -4.0,
        "inflation_yoy": 6.0,
        "growth_yoy": 1.5,
        "political_stability": 40,
    },
    {
        "name": "Chile",
        "cds_approx": 65,
        "debt_to_gdp": 38,
        "current_account_pct": -3.5,
        "inflation_yoy": 3.5,
        "growth_yoy": 2.0,
        "political_stability": 65,
    },
    {
        "name": "Peru",
        "cds_approx": 90,
        "debt_to_gdp": 35,
        "current_account_pct": -2.0,
        "inflation_yoy": 3.0,
        "growth_yoy": 2.5,
        "political_stability": 50,
    },
    {
        "name": "South Africa",
        "cds_approx": 200,
        "debt_to_gdp": 72,
        "current_account_pct": -1.5,
        "inflation_yoy": 5.5,
        "growth_yoy": 0.5,
        "political_stability": 35,
    },
    {
        "name": "Turkey",
        "cds_approx": 320,
        "debt_to_gdp": 40,
        "current_account_pct": -5.0,
        "inflation_yoy": 50.0,
        "growth_yoy": 4.0,
        "political_stability": 30,
    },
    {
        "name": "Indonesia",
        "cds_approx": 85,
        "debt_to_gdp": 40,
        "current_account_pct": -0.5,
        "inflation_yoy": 3.5,
        "growth_yoy": 5.0,
        "political_stability": 55,
    },
    {
        "name": "India",
        "cds_approx": 100,
        "debt_to_gdp": 83,
        "current_account_pct": -1.5,
        "inflation_yoy": 5.0,
        "growth_yoy": 6.5,
        "political_stability": 50,
    },
    {
        "name": "Poland",
        "cds_approx": 55,
        "debt_to_gdp": 50,
        "current_account_pct": 1.0,
        "inflation_yoy": 4.0,
        "growth_yoy": 3.0,
        "political_stability": 60,
    },
]


@StrategyRegistry.register(
    "SOV_02",
    asset_class=AssetClass.SOVEREIGN_CREDIT,
    instruments=["CDS_BR"],
)
class Sov02EmRelativeValueStrategy(BaseStrategy):
    """EM Sovereign Relative Value strategy.

    Runs OLS regression of CDS vs fundamentals across 10 EM peers
    and trades the Brazil residual (actual minus predicted CDS).

    Args:
        data_loader: PointInTimeDataLoader for fetching macro data.
        config: Optional StrategyConfig override.
    """

    def __init__(
        self,
        data_loader: PointInTimeDataLoader,
        config: StrategyConfig | None = None,
    ) -> None:
        super().__init__(config=config or SOV_02_CONFIG)
        self.data_loader = data_loader
        self.log = structlog.get_logger().bind(strategy=self.strategy_id)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def generate_signals(self, as_of_date: date) -> list[StrategySignal]:
        """Produce StrategySignal for Brazil CDS based on EM relative value.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            List with a single StrategySignal, or empty list when data
            is missing or signal below threshold.
        """
        # Load actual Brazil CDS
        br_cds = self.data_loader.get_latest_macro_value(
            "BR_CDS_5Y",
            as_of_date,
        )
        if br_cds is None:
            self.log.warning("sov02_missing_br_cds", as_of_date=str(as_of_date))
            return []

        # Run cross-section regression
        predicted_br_cds = self._run_cross_section_model(br_cds)
        if predicted_br_cds is None:
            self.log.warning("sov02_model_failed")
            return []

        # Compute residual
        residual = br_cds - predicted_br_cds

        # Z-score the residual vs historical residuals
        residual_z = self._compute_residual_z(as_of_date, predicted_br_cds)
        if residual_z is None:
            # Fallback: use simple normalization
            residual_z = residual / max(1.0, abs(predicted_br_cds) * 0.1)

        self.log.info(
            "sov02_relative_value",
            br_cds=round(br_cds, 2),
            predicted=round(predicted_br_cds, 2),
            residual=round(residual, 2),
            residual_z=round(residual_z, 4),
        )

        # Entry threshold
        if abs(residual_z) < _ENTRY_THRESHOLD:
            return []

        # Direction: positive residual (expensive) => SHORT CDS
        if residual_z > 0:
            direction = SignalDirection.SHORT
        else:
            direction = SignalDirection.LONG

        # Stop/take-profit
        entry_level = br_cds
        stop_loss = (
            entry_level * (1 + self.config.stop_loss_pct)
            if direction == SignalDirection.LONG
            else entry_level * (1 + self.config.stop_loss_pct)
        )
        take_profit = (
            entry_level * (1 - self.config.take_profit_pct)
            if direction == SignalDirection.SHORT
            else entry_level * (1 + self.config.take_profit_pct)
        )
        if direction == SignalDirection.SHORT:
            stop_loss = entry_level * (1 + self.config.stop_loss_pct)
            take_profit = entry_level * (1 - self.config.take_profit_pct)
        else:
            stop_loss = entry_level * (1 - self.config.stop_loss_pct)
            take_profit = entry_level * (1 + self.config.take_profit_pct)

        strength = self.classify_strength(residual_z)
        confidence = min(1.0, abs(residual_z) / 3.0)
        suggested_size = self.size_from_conviction(residual_z)

        signal = StrategySignal(
            strategy_id=self.strategy_id,
            timestamp=datetime.utcnow(),
            direction=direction,
            strength=strength,
            confidence=confidence,
            z_score=residual_z,
            raw_value=residual,
            suggested_size=suggested_size,
            asset_class=AssetClass.SOVEREIGN_CREDIT,
            instruments=["CDS_BR"],
            entry_level=entry_level,
            stop_loss=stop_loss,
            take_profit=take_profit,
            holding_period_days=_HOLDING_PERIOD,
            metadata={
                "br_cds_actual": br_cds,
                "br_cds_predicted": predicted_br_cds,
                "residual": residual,
                "residual_z": residual_z,
            },
        )
        return [signal]

    # ------------------------------------------------------------------
    # Cross-section regression model
    # ------------------------------------------------------------------
    def _run_cross_section_model(self, actual_br_cds: float) -> Optional[float]:
        """Run OLS regression of CDS ~ fundamentals across EM peers.

        Uses hardcoded peer data with the actual Brazil CDS substituted in.
        Returns the model-predicted fair value for Brazil CDS.
        """
        n = len(EM_PEERS)
        if n < 3:
            return None

        # Build matrices for OLS: y = CDS, X = [1, debt, ca, infl, growth, pol]
        # Use peer approximate CDS, but substitute actual BR CDS
        y = []
        X = []
        for peer in EM_PEERS:
            cds_val = actual_br_cds if peer["name"] == "Brazil" else peer["cds_approx"]
            y.append(cds_val)
            X.append(
                [
                    1.0,  # intercept
                    peer["debt_to_gdp"],
                    peer["current_account_pct"],
                    peer["inflation_yoy"],
                    peer["growth_yoy"],
                    peer["political_stability"],
                ]
            )

        # Simple OLS: beta = (X'X)^{-1} X'y
        # Implemented without numpy to keep dependency light
        k = len(X[0])

        # X'X
        XtX = [[0.0] * k for _ in range(k)]
        for i in range(k):
            for j in range(k):
                for row in X:
                    XtX[i][j] += row[i] * row[j]

        # X'y
        Xty = [0.0] * k
        for i in range(k):
            for idx, row in enumerate(X):
                Xty[i] += row[i] * y[idx]

        # Solve via Gaussian elimination
        beta = self._solve_linear_system(XtX, Xty)
        if beta is None:
            return None

        # Brazil predicted CDS
        br_peer = next(p for p in EM_PEERS if p["name"] == "Brazil")
        br_x = [
            1.0,
            br_peer["debt_to_gdp"],
            br_peer["current_account_pct"],
            br_peer["inflation_yoy"],
            br_peer["growth_yoy"],
            br_peer["political_stability"],
        ]

        predicted = sum(b * x for b, x in zip(beta, br_x))
        return predicted

    @staticmethod
    def _solve_linear_system(
        A: list[list[float]],
        b: list[float],
    ) -> Optional[list[float]]:
        """Solve Ax = b via Gaussian elimination with partial pivoting.

        Returns None if the system is singular.
        """
        n = len(b)
        # Augmented matrix
        aug = [row[:] + [b[i]] for i, row in enumerate(A)]

        for col in range(n):
            # Partial pivoting
            max_row = col
            for row in range(col + 1, n):
                if abs(aug[row][col]) > abs(aug[max_row][col]):
                    max_row = row
            aug[col], aug[max_row] = aug[max_row], aug[col]

            if abs(aug[col][col]) < 1e-12:
                return None

            # Eliminate below
            for row in range(col + 1, n):
                factor = aug[row][col] / aug[col][col]
                for j in range(col, n + 1):
                    aug[row][j] -= factor * aug[col][j]

        # Back substitution
        x = [0.0] * n
        for i in range(n - 1, -1, -1):
            x[i] = aug[i][n]
            for j in range(i + 1, n):
                x[i] -= aug[i][j] * x[j]
            if abs(aug[i][i]) < 1e-12:
                return None
            x[i] /= aug[i][i]

        return x

    # ------------------------------------------------------------------
    # Residual z-score computation
    # ------------------------------------------------------------------
    def _compute_residual_z(
        self,
        as_of_date: date,
        current_predicted: float,
    ) -> Optional[float]:
        """Compute z-score of residual vs rolling 252-day history.

        Uses CDS historical values and the constant model prediction
        (since fundamentals are semi-static, predicted changes slowly).
        """
        cds_df = self.data_loader.get_macro_series(
            "BR_CDS_5Y",
            as_of_date,
            lookback_days=_CDS_LOOKBACK,
        )
        if cds_df.empty or len(cds_df) < 60:
            return None

        # Compute residual history = actual - predicted
        # Since fundamentals are semi-static, model prediction is ~constant
        residuals = [v - current_predicted for v in cds_df["value"].tolist()]
        current_residual = residuals[-1]

        return self.compute_z_score(
            current_residual,
            residuals,
            window=_ZSCORE_WINDOW,
        )

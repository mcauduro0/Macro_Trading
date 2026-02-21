"""RATES_BR_01: BR DI Carry & Roll-Down strategy.

Computes carry-to-risk at each DI curve tenor and goes long at the optimal
point (maximum carry-to-risk ratio) when the ratio exceeds a configurable
threshold.  Goes short when carry-to-risk is below the negative threshold.

The strategy consumes DI curve data via the PointInTimeDataLoader and
produces a single StrategyPosition for the optimal tenor.
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import structlog

from src.agents.base import AgentSignal, classify_strength
from src.agents.data_loader import PointInTimeDataLoader
from src.core.enums import AssetClass, Frequency, SignalDirection
from src.strategies.base import BaseStrategy, StrategyConfig, StrategyPosition

# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------
RATES_BR_01_CONFIG = StrategyConfig(
    strategy_id="RATES_BR_01",
    strategy_name="BR DI Carry & Roll-Down",
    asset_class=AssetClass.FIXED_INCOME,
    instruments=["DI_PRE"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
    max_leverage=3.0,
    stop_loss_pct=0.03,
    take_profit_pct=0.08,
)


class RatesBR01CarryStrategy(BaseStrategy):
    """Carry & Roll-Down strategy on the BR DI curve.

    Identifies the tenor with the highest carry-to-risk ratio and generates
    a LONG position when the ratio exceeds the threshold, or SHORT when
    it is below the negative threshold.

    Args:
        data_loader: PointInTimeDataLoader for fetching curve data.
        carry_threshold: Minimum absolute carry-to-risk ratio to generate
            a signal (default 1.5).
        config: Optional StrategyConfig override.
    """

    def __init__(
        self,
        data_loader: PointInTimeDataLoader,
        carry_threshold: float = 1.5,
        config: StrategyConfig | None = None,
    ) -> None:
        super().__init__(config=config or RATES_BR_01_CONFIG)
        self.data_loader = data_loader
        self.carry_threshold = carry_threshold
        self.log = structlog.get_logger().bind(strategy=self.strategy_id)

    def generate_signals(self, as_of_date: date) -> list[StrategyPosition]:
        """Produce target positions based on DI curve carry-to-risk analysis.

        Steps:
            1. Load DI curve snapshot.
            2. For each tenor pair, compute carry (rate differential).
            3. Compute risk as annualized rolling std of rate changes.
            4. Find optimal tenor (max carry-to-risk).
            5. Generate LONG/SHORT/NEUTRAL based on threshold.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            List with a single StrategyPosition, or empty list if data
            is insufficient or carry-to-risk is within threshold.
        """
        # 1. Load current DI curve
        curve = self.data_loader.get_curve("DI_PRE", as_of_date)
        if not curve:
            self.log.warning("empty_curve", as_of_date=str(as_of_date))
            return []

        tenors = sorted(curve.keys())
        if len(tenors) < 2:
            self.log.warning("insufficient_tenors", count=len(tenors))
            return []

        # 2-4. Compute carry-to-risk for each adjacent tenor pair
        carry_risk_map: dict[int, float] = {}
        for i in range(len(tenors) - 1):
            t_short = tenors[i]
            t_long = tenors[i + 1]
            carry = curve[t_long] - curve[t_short]

            # Load history for the shorter tenor to compute volatility
            history = self.data_loader.get_curve_history(
                "DI_PRE", t_short, as_of_date, lookback_days=252
            )

            if history.empty or len(history) < 20:
                continue

            rate_changes = history["rate"].diff().dropna()
            if rate_changes.empty:
                continue

            risk = float(rate_changes.std()) * math.sqrt(252)
            if risk <= 0 or math.isnan(risk):
                continue

            carry_risk_map[t_short] = carry / risk

        if not carry_risk_map:
            self.log.info("no_valid_tenors", as_of_date=str(as_of_date))
            return []

        # 5. Identify optimal tenor (max absolute carry-to-risk)
        optimal_tenor = max(carry_risk_map, key=lambda t: carry_risk_map[t])
        max_ratio = carry_risk_map[optimal_tenor]

        # 6. Generate signal based on threshold
        if max_ratio > self.carry_threshold:
            # Go LONG at optimal tenor
            confidence = min(1.0, max_ratio / (self.carry_threshold * 2))
            strength = classify_strength(confidence)
            direction = SignalDirection.LONG
        elif max_ratio < -self.carry_threshold:
            # Check if we should go SHORT
            # Find the tenor with the most negative ratio
            min_tenor = min(carry_risk_map, key=lambda t: carry_risk_map[t])
            min_ratio = carry_risk_map[min_tenor]
            if min_ratio < -self.carry_threshold:
                optimal_tenor = min_tenor
                max_ratio = min_ratio
                confidence = min(1.0, abs(min_ratio) / (self.carry_threshold * 2))
                strength = classify_strength(confidence)
                direction = SignalDirection.SHORT
            else:
                return []
        else:
            # Within threshold — NEUTRAL (no position)
            return []

        # Build AgentSignal to feed through signals_to_positions
        agent_signal = AgentSignal(
            signal_id=f"DI_PRE_{optimal_tenor}",
            agent_id=self.strategy_id,
            timestamp=np.datetime64("now"),
            as_of_date=as_of_date,
            direction=direction,
            strength=strength,
            confidence=confidence,
            value=max_ratio,
            horizon_days=21,
            metadata={
                "optimal_tenor": optimal_tenor,
                "carry_to_risk": max_ratio,
                "threshold": self.carry_threshold,
            },
        )

        positions = self.signals_to_positions([agent_signal])

        # Enrich position metadata
        for pos in positions:
            pos.metadata.update({
                "optimal_tenor": optimal_tenor,
                "carry_to_risk": max_ratio,
                "curve_date": str(as_of_date),
            })

        return positions

"""RATES_BR_02: BR Taylor Rule Misalignment strategy.

Computes the Taylor-implied policy rate and compares it to the market DI
rate (1Y tenor).  When the gap exceeds the threshold, the strategy trades
in the direction of convergence:

- Taylor > market (market too dovish): SHORT DI (expect rates to rise)
- Taylor < market (market too hawkish): LONG DI (expect rates to fall)

The strategy consumes macro data (Selic, Focus IPCA) and the DI curve
via the PointInTimeDataLoader.
"""

from __future__ import annotations

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
RATES_BR_02_CONFIG = StrategyConfig(
    strategy_id="RATES_BR_02",
    strategy_name="BR Taylor Rule Misalignment",
    asset_class=AssetClass.FIXED_INCOME,
    instruments=["DI_PRE"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
    max_leverage=3.0,
    stop_loss_pct=0.04,
    take_profit_pct=0.10,
)


class RatesBR02TaylorStrategy(BaseStrategy):
    """Taylor Rule Misalignment strategy on the BR DI curve.

    Computes the Taylor-implied rate and trades DI when the gap between
    the implied rate and the market 1Y rate exceeds the threshold.

    Args:
        data_loader: PointInTimeDataLoader for fetching macro and curve data.
        gap_threshold_bps: Minimum absolute gap in basis points to trigger
            a position (default 100).
        r_star: Neutral real interest rate estimate (default 4.5% per BCB).
        pi_target: BCB inflation target center (default 3.0%).
        alpha: Inflation response coefficient (default 1.5).
        beta: Output gap coefficient (default 0.5).
        config: Optional StrategyConfig override.
    """

    def __init__(
        self,
        data_loader: PointInTimeDataLoader,
        gap_threshold_bps: float = 100.0,
        r_star: float = 4.5,
        pi_target: float = 3.0,
        alpha: float = 1.5,
        beta: float = 0.5,
        config: StrategyConfig | None = None,
    ) -> None:
        super().__init__(config=config or RATES_BR_02_CONFIG)
        self.data_loader = data_loader
        self.gap_threshold_bps = gap_threshold_bps
        self.r_star = r_star
        self.pi_target = pi_target
        self.alpha = alpha
        self.beta = beta
        self.log = structlog.get_logger().bind(strategy=self.strategy_id)

    def generate_signals(self, as_of_date: date) -> list[StrategyPosition]:
        """Produce target positions based on Taylor-market gap analysis.

        Steps:
            1. Load Selic target, Focus IPCA expectations, DI curve.
            2. Compute Taylor-implied rate.
            3. Compute gap vs market 1Y DI rate.
            4. Generate SHORT (gap > 0) or LONG (gap < 0) if exceeds threshold.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            List with a single StrategyPosition, or empty list if data
            is missing or gap is within threshold.
        """
        # 1. Load data
        selic = self.data_loader.get_latest_macro_value("BR_SELIC_TARGET", as_of_date)
        if selic is None:
            self.log.warning("missing_selic", as_of_date=str(as_of_date))
            return []

        focus_ipca = self.data_loader.get_latest_macro_value(
            f"BR_FOCUS_IPCA_{as_of_date.year}_MEDIAN", as_of_date
        )
        if focus_ipca is None:
            self.log.warning("missing_focus_ipca", as_of_date=str(as_of_date))
            return []

        curve = self.data_loader.get_curve("DI_PRE", as_of_date)
        if not curve:
            self.log.warning("missing_di_curve", as_of_date=str(as_of_date))
            return []

        # Find 1Y (252 trading days) tenor — use closest available
        market_rate = self._get_1y_rate(curve)
        if market_rate is None:
            self.log.warning("no_1y_tenor", available_tenors=list(curve.keys()))
            return []

        # 2. Load output gap (optional — default to 0.0)
        output_gap = self._get_output_gap(as_of_date)

        # 3. Compute Taylor-implied rate
        pi_e = focus_ipca
        taylor_rate = (
            self.r_star
            + pi_e
            + self.alpha * (pi_e - self.pi_target)
            + self.beta * output_gap
        )

        # 4. Compute gap
        gap = taylor_rate - market_rate
        gap_bps = gap * 100  # convert to basis points

        self.log.info(
            "taylor_gap_computed",
            taylor_rate=round(taylor_rate, 4),
            market_rate=round(market_rate, 4),
            gap_bps=round(gap_bps, 2),
            selic=selic,
            focus_ipca=focus_ipca,
        )

        # 5. Generate signal if gap exceeds threshold
        if abs(gap_bps) <= self.gap_threshold_bps:
            return []

        if gap > 0:
            # Taylor says higher than market -> SHORT DI (rates should rise)
            direction = SignalDirection.SHORT
        else:
            # Taylor says lower than market -> LONG DI (rates should fall)
            direction = SignalDirection.LONG

        confidence = min(1.0, abs(gap_bps) / (self.gap_threshold_bps * 3))
        strength = classify_strength(confidence)

        agent_signal = AgentSignal(
            signal_id="DI_PRE_252",
            agent_id=self.strategy_id,
            timestamp=np.datetime64("now"),
            as_of_date=as_of_date,
            direction=direction,
            strength=strength,
            confidence=confidence,
            value=gap_bps,
            horizon_days=63,  # 1 quarter horizon
            metadata={
                "taylor_rate": taylor_rate,
                "market_rate": market_rate,
                "gap_bps": gap_bps,
                "selic": selic,
                "focus_ipca": focus_ipca,
                "r_star": self.r_star,
                "output_gap": output_gap,
            },
        )

        positions = self.signals_to_positions([agent_signal])

        # Enrich metadata
        for pos in positions:
            pos.metadata.update(
                {
                    "taylor_rate": taylor_rate,
                    "market_rate": market_rate,
                    "gap_bps": gap_bps,
                }
            )

        return positions

    def _get_1y_rate(self, curve: dict[int, float]) -> float | None:
        """Extract the 1Y (~252 day) rate from the DI curve.

        Looks for the closest tenor to 252 days within a 50-day tolerance.

        Args:
            curve: ``{tenor_days: rate}`` dictionary.

        Returns:
            Rate for the 1Y tenor, or None if no suitable tenor found.
        """
        target = 252
        tolerance = 50
        best_tenor = None
        best_dist = float("inf")

        for tenor in curve:
            dist = abs(tenor - target)
            if dist < best_dist and dist <= tolerance:
                best_dist = dist
                best_tenor = tenor

        if best_tenor is None:
            return None
        return curve[best_tenor]

    def _get_output_gap(self, as_of_date: date) -> float:
        """Attempt to load output gap; default to 0.0 if unavailable.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            Output gap value, or 0.0 if unavailable.
        """
        try:
            val = self.data_loader.get_latest_macro_value("BR_OUTPUT_GAP", as_of_date)
            if val is not None:
                return val
        except Exception:
            pass
        return 0.0

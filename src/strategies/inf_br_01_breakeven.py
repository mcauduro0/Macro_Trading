"""INF_BR_01: BR Breakeven Inflation Trade strategy.

Trades breakeven inflation (nominal DI rate minus NTN-B real rate) when the
agent's inflation forecast (Focus IPCA median) diverges from the market-implied
breakeven by more than a configurable threshold:

- Agent sees higher inflation than market: LONG breakeven
  (long NTN-B/real, short DI/nominal -- positive weight).
- Agent sees lower inflation than market: SHORT breakeven
  (short NTN-B/real, long DI/nominal -- negative weight).

The strategy focuses on the 2Y tenor as the primary signal -- it is
the most liquid and responsive point on the Brazilian inflation curve.

The strategy consumes DI and NTN-B curve data plus Focus survey
expectations via the PointInTimeDataLoader.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import structlog

from src.agents.base import AgentSignal, classify_strength
from src.agents.data_loader import PointInTimeDataLoader
from src.core.enums import AssetClass, Frequency, SignalDirection
from src.core.utils.tenors import find_closest_tenor
from src.strategies.base import BaseStrategy, StrategyConfig, StrategyPosition

# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------
INF_BR_01_CONFIG = StrategyConfig(
    strategy_id="INF_BR_01",
    strategy_name="BR Breakeven Inflation Trade",
    asset_class=AssetClass.FIXED_INCOME,
    instruments=["DI_PRE", "NTN_B_REAL"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
    max_leverage=3.0,
    stop_loss_pct=0.03,
    take_profit_pct=0.06,
)

# Tenor target for primary signal
_2Y_TARGET = 504  # ~2 years in business days
_TENOR_TOLERANCE = 100


class InfBR01BreakevenStrategy(BaseStrategy):
    """Breakeven Inflation Trade strategy on BR DI and NTN-B curves.

    Compares the Focus survey inflation forecast to the market-implied
    breakeven inflation (nominal DI minus NTN-B real rate) and trades
    the divergence when it exceeds the threshold.

    Args:
        data_loader: PointInTimeDataLoader for fetching curve and macro data.
        divergence_threshold_bps: Minimum divergence in bps between agent
            forecast and market breakeven to trigger a position (default 50.0).
        config: Optional StrategyConfig override.
    """

    def __init__(
        self,
        data_loader: PointInTimeDataLoader,
        divergence_threshold_bps: float = 50.0,
        config: StrategyConfig | None = None,
    ) -> None:
        super().__init__(config=config or INF_BR_01_CONFIG)
        self.data_loader = data_loader
        self.divergence_threshold_bps = divergence_threshold_bps
        self.log = structlog.get_logger().bind(strategy=self.strategy_id)

    def generate_signals(self, as_of_date: date) -> list[StrategyPosition]:
        """Produce target positions based on breakeven inflation divergence.

        Steps:
            1. Load DI_PRE (nominal) and NTN_B_REAL curves.
            2. Compute market-implied breakeven at 2Y tenor.
            3. Load agent inflation forecast (Focus IPCA CY median).
            4. Compute divergence = forecast - market breakeven.
            5. Generate LONG/SHORT breakeven if divergence exceeds threshold.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            List with a single StrategyPosition, or empty list if data
            is insufficient or divergence is within threshold.
        """
        # 1. Load nominal DI curve
        di_curve = self.data_loader.get_curve("DI_PRE", as_of_date)
        if not di_curve:
            self.log.warning("missing_di_curve", as_of_date=str(as_of_date))
            return []

        # 2. Load real NTN-B curve
        ntnb_curve = self.data_loader.get_curve("NTN_B_REAL", as_of_date)
        if not ntnb_curve:
            self.log.warning("missing_ntnb_curve", as_of_date=str(as_of_date))
            return []

        # 3. Find matching 2Y tenors
        di_tenor = find_closest_tenor(di_curve, _2Y_TARGET, _TENOR_TOLERANCE)
        ntnb_tenor = find_closest_tenor(ntnb_curve, _2Y_TARGET, _TENOR_TOLERANCE)

        if di_tenor is None or ntnb_tenor is None:
            self.log.warning(
                "no_matching_tenors",
                di_tenor=di_tenor,
                ntnb_tenor=ntnb_tenor,
                di_tenors=list(di_curve.keys()),
                ntnb_tenors=list(ntnb_curve.keys()),
            )
            return []

        # 4. Compute market-implied breakeven
        nominal_rate = di_curve[di_tenor]
        real_rate = ntnb_curve[ntnb_tenor]
        market_breakeven = nominal_rate - real_rate

        # 5. Load agent inflation forecast
        agent_forecast = self.data_loader.get_latest_macro_value(
            "BR_FOCUS_IPCA_CY_MEDIAN", as_of_date,
        )
        if agent_forecast is None:
            self.log.warning("missing_focus_forecast", as_of_date=str(as_of_date))
            return []

        # 6. Compute divergence
        divergence = agent_forecast - market_breakeven  # in percentage points
        divergence_bps = divergence * 100

        self.log.info(
            "breakeven_analysis",
            nominal_rate=round(nominal_rate, 4),
            real_rate=round(real_rate, 4),
            market_breakeven=round(market_breakeven, 4),
            agent_forecast=agent_forecast,
            divergence_bps=round(divergence_bps, 2),
        )

        # 7. Generate signal
        return self._generate_breakeven_position(
            divergence_bps,
            market_breakeven,
            agent_forecast,
            nominal_rate,
            real_rate,
            di_tenor,
            ntnb_tenor,
            as_of_date,
        )

    def _generate_breakeven_position(
        self,
        divergence_bps: float,
        market_breakeven: float,
        agent_forecast: float,
        nominal_rate: float,
        real_rate: float,
        di_tenor: int,
        ntnb_tenor: int,
        as_of_date: date,
    ) -> list[StrategyPosition]:
        """Generate position from breakeven inflation divergence.

        Args:
            divergence_bps: Divergence in basis points.
            market_breakeven: Market-implied breakeven rate.
            agent_forecast: Agent's inflation forecast.
            nominal_rate: Nominal DI rate.
            real_rate: Real NTN-B rate.
            di_tenor: Matched DI tenor.
            ntnb_tenor: Matched NTN-B tenor.
            as_of_date: Reference date.

        Returns:
            List with single position or empty list.
        """
        if divergence_bps > self.divergence_threshold_bps:
            # Agent sees higher inflation -> LONG breakeven
            # (long NTN-B real, short DI nominal)
            direction = SignalDirection.LONG
        elif divergence_bps < -self.divergence_threshold_bps:
            # Agent sees lower inflation -> SHORT breakeven
            # (short NTN-B real, long DI nominal)
            direction = SignalDirection.SHORT
        else:
            # Within threshold -> NEUTRAL
            return []

        confidence = min(
            1.0,
            abs(divergence_bps) / (self.divergence_threshold_bps * 3),
        )
        strength = classify_strength(confidence)

        signal_id = f"BREAKEVEN_{di_tenor}_{ntnb_tenor}"

        agent_signal = AgentSignal(
            signal_id=signal_id,
            agent_id=self.strategy_id,
            timestamp=np.datetime64("now"),
            as_of_date=as_of_date,
            direction=direction,
            strength=strength,
            confidence=confidence,
            value=divergence_bps,
            horizon_days=63,  # quarterly horizon
            metadata={
                "divergence_bps": divergence_bps,
                "market_breakeven": market_breakeven,
                "agent_forecast": agent_forecast,
                "nominal_rate": nominal_rate,
                "real_rate": real_rate,
            },
        )

        positions = self.signals_to_positions([agent_signal])

        # Enrich metadata
        for pos in positions:
            pos.metadata.update({
                "divergence_bps": divergence_bps,
                "market_breakeven": market_breakeven,
                "agent_forecast": agent_forecast,
                "nominal_rate": nominal_rate,
                "real_rate": real_rate,
                "di_tenor": di_tenor,
                "ntnb_tenor": ntnb_tenor,
                "curve_date": str(as_of_date),
            })

        self.log.info(
            "breakeven_signal_generated",
            divergence_bps=round(divergence_bps, 2),
            direction=direction.value,
            confidence=round(confidence, 3),
        )

        return positions

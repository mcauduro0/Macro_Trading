"""FX_BR_01: USDBRL Carry & Fundamental composite strategy.

Composites three components into a directional USDBRL signal:

- **Carry-to-Risk** (40%): BR-US rate differential normalized by USDBRL
  realized volatility.  High carry-to-risk => long BRL (short USDBRL).
- **BEER Misalignment** (35%): Spot vs. 252-day rolling mean as a
  simplified Behavioural Equilibrium Exchange Rate proxy.  BRL undervalued
  (spot > fair value) => long BRL.
- **Flow Score** (25%): Net FX flow z-score.  Positive net inflows =>
  long BRL.

An optional **regime adjustment** scales the final weight by 50% when the
cross-asset regime is risk-off (regime_score < -0.3).

The strategy produces a single StrategyPosition for USDBRL.
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
FX_BR_01_CONFIG = StrategyConfig(
    strategy_id="FX_BR_01",
    strategy_name="USDBRL Carry & Fundamental",
    asset_class=AssetClass.FX,
    instruments=["USDBRL"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
    max_leverage=3.0,
    stop_loss_pct=0.05,
    take_profit_pct=0.10,
)


class FxBR01CarryFundamentalStrategy(BaseStrategy):
    """USDBRL Carry & Fundamental composite strategy.

    Composites carry-to-risk (40%), BEER misalignment (35%), and FX flow
    score (25%) into a directional USDBRL signal.  An optional regime
    adjustment scales the position by 50% in risk-off environments.

    Args:
        data_loader: PointInTimeDataLoader for fetching macro / market data.
        carry_weight: Component weight for carry-to-risk (default 0.40).
        beer_weight: Component weight for BEER misalignment (default 0.35).
        flow_weight: Component weight for flow score (default 0.25).
        regime_scale: Scale-down factor in unfavorable regime (default 0.50).
        config: Optional StrategyConfig override.
    """

    def __init__(
        self,
        data_loader: PointInTimeDataLoader,
        carry_weight: float = 0.40,
        beer_weight: float = 0.35,
        flow_weight: float = 0.25,
        regime_scale: float = 0.50,
        config: StrategyConfig | None = None,
    ) -> None:
        super().__init__(config=config or FX_BR_01_CONFIG)
        self.data_loader = data_loader
        self.carry_weight = carry_weight
        self.beer_weight = beer_weight
        self.flow_weight = flow_weight
        self.regime_scale = regime_scale
        self.log = structlog.get_logger().bind(strategy=self.strategy_id)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def generate_signals(
        self,
        as_of_date: date,
        regime_score: float | None = None,
    ) -> list[StrategyPosition]:
        """Produce target positions for USDBRL based on composite signal.

        Args:
            as_of_date: Point-in-time reference date.
            regime_score: Optional cross-asset regime score from Phase 12.
                If provided and > 0.3 (risk-off) the final weight is scaled by
                ``regime_scale``.

        Returns:
            List with a single StrategyPosition, or empty list when data
            is missing or the composite signal is below the neutral zone.
        """
        # --- Component 1: Carry-to-Risk (40%) ---
        carry_score = self._compute_carry_score(as_of_date)
        if carry_score is None:
            return []

        # --- Component 2: BEER Misalignment (35%) ---
        beer_score = self._compute_beer_score(as_of_date)
        if beer_score is None:
            return []

        # --- Component 3: Flow Score (25%) ---
        flow_score = self._compute_flow_score(as_of_date)
        # flow_score can be None if no flow data — treat as 0
        if flow_score is None:
            flow_score = 0.0

        # --- Composite ---
        composite = (
            carry_score * self.carry_weight
            + beer_score * self.beer_weight
            + flow_score * self.flow_weight
        )

        self.log.info(
            "fx_composite",
            carry_score=round(carry_score, 4),
            beer_score=round(beer_score, 4),
            flow_score=round(flow_score, 4),
            composite=round(composite, 4),
            regime_score=regime_score,
        )

        # Neutral zone
        if abs(composite) < 0.1:
            return []

        # Direction: composite > 0 => long BRL = SHORT USDBRL
        if composite > 0:
            direction = SignalDirection.SHORT
        else:
            direction = SignalDirection.LONG

        confidence = min(1.0, abs(composite))
        strength = classify_strength(confidence)

        # --- Regime adjustment ---
        # Scale down in risk-off environments (regime_score > 0.3 = RISK_OFF)
        weight_scale = 1.0
        if regime_score is not None and regime_score > 0.3:
            weight_scale = self.regime_scale

        signal = AgentSignal(
            signal_id="USDBRL",
            agent_id=self.strategy_id,
            timestamp=np.datetime64("now"),
            as_of_date=as_of_date,
            direction=direction,
            strength=strength,
            confidence=confidence,
            value=composite,
            horizon_days=21,
            metadata={
                "carry_score": carry_score,
                "beer_score": beer_score,
                "flow_score": flow_score,
                "composite": composite,
                "regime_score": regime_score,
            },
        )

        positions = self.signals_to_positions([signal])

        # Apply regime scale-down to weight
        if weight_scale < 1.0:
            for pos in positions:
                pos.weight = pos.weight * weight_scale

        # Enrich metadata
        for pos in positions:
            pos.metadata.update({
                "carry_score": carry_score,
                "beer_score": beer_score,
                "flow_score": flow_score,
                "composite": composite,
                "regime_score": regime_score,
                "regime_scale_applied": weight_scale < 1.0,
                "curve_date": str(as_of_date),
            })

        return positions

    # ------------------------------------------------------------------
    # Component 1: Carry-to-Risk
    # ------------------------------------------------------------------
    def _compute_carry_score(self, as_of_date: date) -> float | None:
        """Compute carry-to-risk score in [-1, 1].

        Positive => BRL carry advantage => long BRL (short USDBRL).
        """
        # Load BR rate
        br_rate = self.data_loader.get_latest_macro_value(
            "BR_SELIC_TARGET", as_of_date,
        )
        if br_rate is None:
            # Fallback: DI 1Y
            di_curve = self.data_loader.get_curve("DI_PRE", as_of_date)
            if di_curve:
                # Find ~1Y tenor
                for tenor in sorted(di_curve.keys()):
                    if tenor >= 200:
                        br_rate = di_curve[tenor]
                        break
            if br_rate is None:
                self.log.warning("missing_br_rate", as_of_date=str(as_of_date))
                return None

        # Load US rate
        us_rate = self.data_loader.get_latest_macro_value(
            "US_FED_FUNDS", as_of_date,
        )
        if us_rate is None:
            us_rate = self.data_loader.get_latest_macro_value(
                "US_SOFR", as_of_date,
            )
        if us_rate is None:
            self.log.warning("missing_us_rate", as_of_date=str(as_of_date))
            return None

        carry = br_rate - us_rate  # positive = BRL carry advantage

        # Load USDBRL history for realized vol
        usdbrl_df = self.data_loader.get_market_data(
            "USDBRL", as_of_date, lookback_days=63,
        )
        if usdbrl_df.empty or len(usdbrl_df) < 21:
            self.log.warning(
                "insufficient_usdbrl_vol_data",
                rows=len(usdbrl_df) if not usdbrl_df.empty else 0,
            )
            return None

        # 21-day realized vol (annualized)
        returns = usdbrl_df["close"].pct_change().dropna().tail(21)
        if len(returns) < 10:
            return None

        vol = float(returns.std()) * math.sqrt(252)
        if vol <= 0 or math.isnan(vol):
            return None

        carry_to_risk = carry / (vol * 100)
        carry_score = math.tanh(carry_to_risk / 2)
        return carry_score

    # ------------------------------------------------------------------
    # Component 2: BEER Misalignment
    # ------------------------------------------------------------------
    def _compute_beer_score(self, as_of_date: date) -> float | None:
        """Compute simplified BEER misalignment score in [-1, 1].

        USDBRL above 252-day mean => BRL undervalued => positive score
        (long BRL = short USDBRL).
        """
        usdbrl_df = self.data_loader.get_market_data(
            "USDBRL", as_of_date, lookback_days=756,
        )
        if usdbrl_df.empty or len(usdbrl_df) < 252:
            self.log.warning(
                "insufficient_usdbrl_beer_data",
                rows=len(usdbrl_df) if not usdbrl_df.empty else 0,
            )
            return None

        spot = float(usdbrl_df["close"].iloc[-1])
        fair_value = float(usdbrl_df["close"].tail(252).mean())

        if fair_value <= 0:
            return None

        misalignment_pct = (spot - fair_value) / fair_value * 100

        # USDBRL above fair value => BRL undervalued => positive score (long BRL)
        beer_score = math.tanh(misalignment_pct / 10)
        return beer_score

    # ------------------------------------------------------------------
    # Component 3: Flow Score
    # ------------------------------------------------------------------
    def _compute_flow_score(self, as_of_date: date) -> float | None:
        """Compute FX flow z-score in [-1, 1].

        Positive net flow => long BRL (short USDBRL).
        """
        flow_df = self.data_loader.get_flow_data(
            "BR_FX_FLOW_NET", as_of_date, lookback_days=365,
        )
        if flow_df.empty or len(flow_df) < 30:
            return None

        # Cumulative net flow over last 21 observations
        recent_flow = float(flow_df["value"].tail(21).sum())

        # Z-score vs 252-day history
        rolling_sums = flow_df["value"].rolling(21).sum().dropna()
        if len(rolling_sums) < 60:
            return None

        hist_window = rolling_sums.tail(252) if len(rolling_sums) >= 252 else rolling_sums
        mean_flow = float(hist_window.mean())
        std_flow = float(hist_window.std())

        if std_flow <= 0 or math.isnan(std_flow):
            return None

        flow_z = (recent_flow - mean_flow) / std_flow
        flow_score = math.tanh(flow_z / 2)
        return flow_score

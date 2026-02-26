"""CUPOM_02: Onshore-Offshore Spread strategy.

Trades the spread between the onshore DI rate and the offshore-implied rate
(UST + USDBRL forward points).  When the spread z-score is elevated
(onshore premium too high), the strategy shorts the spread expecting mean
reversion.  When the spread is abnormally compressed, the strategy goes long.

Spread computation:
    onshore_rate  = DI_PRE rate at 3M (63d) or 6M (126d) tenor
    offshore_implied = UST rate + (DI - UST) * tenor_fraction  (CIP proxy)
    spread = onshore_rate - offshore_implied

In practice the CIP basis serves as a proxy for the onshore-offshore
spread.  We compute: spread = DI_rate - (UST_rate + fwd_premium), where
fwd_premium is approximated from the DI/UST differential.

This strategy uses z-score mean reversion on the spread with a 252-day
lookback and a higher entry threshold (1.5) to account for noise.
"""

from __future__ import annotations

from datetime import date, datetime

import structlog

from src.agents.data_loader import PointInTimeDataLoader
from src.core.enums import AssetClass, Frequency, SignalDirection
from src.core.utils.tenors import find_closest_tenor
from src.strategies.base import BaseStrategy, StrategyConfig, StrategySignal
from src.strategies.registry import StrategyRegistry

# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------
CUPOM_02_CONFIG = StrategyConfig(
    strategy_id="CUPOM_02",
    strategy_name="Onshore-Offshore Spread",
    asset_class=AssetClass.CUPOM_CAMBIAL,
    instruments=["DDI", "NDF"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
    max_leverage=3.0,
    stop_loss_pct=0.02,
    take_profit_pct=0.03,
)

# Tenor targets: 3M and 6M
_3M_TARGET = 63
_6M_TARGET = 126
_TENOR_TOLERANCE = 30

# Signal parameters
_ENTRY_Z_THRESHOLD = 1.5
_HOLDING_PERIOD_DAYS = 21
_HISTORY_WINDOW = 252
_HISTORY_LOOKBACK_DAYS = 756  # ~3 years


@StrategyRegistry.register(
    "CUPOM_02",
    asset_class=AssetClass.CUPOM_CAMBIAL,
    instruments=["DDI", "NDF"],
)
class Cupom02OnshoreOffshoreStrategy(BaseStrategy):
    """Onshore-Offshore Spread mean reversion strategy.

    Trades the spread between Brazilian onshore DI rates and
    offshore-implied rates (UST + forward premium proxy) using
    z-score mean reversion.

    Args:
        data_loader: PointInTimeDataLoader for fetching curve and market data.
        entry_z_threshold: Minimum |z-score| to trigger entry (default 1.5).
        config: Optional StrategyConfig override.
    """

    def __init__(
        self,
        data_loader: PointInTimeDataLoader,
        entry_z_threshold: float = _ENTRY_Z_THRESHOLD,
        config: StrategyConfig | None = None,
    ) -> None:
        super().__init__(config=config or CUPOM_02_CONFIG)
        self.data_loader = data_loader
        self.entry_z_threshold = entry_z_threshold
        self.log = structlog.get_logger().bind(strategy=self.strategy_id)

    # ------------------------------------------------------------------
    # Main signal generation
    # ------------------------------------------------------------------
    def generate_signals(self, as_of_date: date) -> list[StrategySignal]:
        """Generate signals based on onshore-offshore spread z-score.

        Steps:
            1. Load DI_PRE curve and extract 3M/6M rate.
            2. Load UST_NOM curve and extract matching tenor.
            3. Load USDBRL spot for context.
            4. Compute onshore-offshore spread.
            5. Z-score the spread vs 252-day history.
            6. Mean reversion: fade extreme z-scores.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            List of StrategySignal objects, or empty list.
        """
        # 1. Load DI curve
        di_curve = self.data_loader.get_curve("DI_PRE", as_of_date)
        if not di_curve:
            self.log.warning("missing_di_curve", as_of_date=str(as_of_date))
            return []

        # 2. Load UST curve
        ust_curve = self.data_loader.get_curve("UST_NOM", as_of_date)
        if not ust_curve:
            self.log.warning("missing_ust_curve", as_of_date=str(as_of_date))
            return []

        # 3. Find matching tenors -- prefer 6M, fall back to 3M
        di_tenor = find_closest_tenor(di_curve, _6M_TARGET, _TENOR_TOLERANCE)
        ust_tenor = find_closest_tenor(ust_curve, _6M_TARGET, _TENOR_TOLERANCE)

        if di_tenor is None or ust_tenor is None:
            # Fallback to 3M
            di_tenor = find_closest_tenor(di_curve, _3M_TARGET, _TENOR_TOLERANCE)
            ust_tenor = find_closest_tenor(ust_curve, _3M_TARGET, _TENOR_TOLERANCE)

        if di_tenor is None or ust_tenor is None:
            self.log.warning(
                "no_matching_tenors",
                di_tenors=list(di_curve.keys()),
                ust_tenors=list(ust_curve.keys()),
            )
            return []

        # 4. Compute onshore and offshore-implied rates
        onshore_rate = di_curve[di_tenor]
        ust_rate = ust_curve[ust_tenor]

        # Offshore implied rate: UST + forward premium
        # Forward premium proxy: (DI - UST) represents the carry
        # differential that should be captured in FX forwards.
        # The spread we trade is the residual: how much onshore rate
        # exceeds what CIP would imply.
        # Simplified: spread = DI - UST (the CIP basis itself)
        current_spread = onshore_rate - ust_rate

        # 5. Load curve histories for z-score
        di_history = self.data_loader.get_curve_history(
            "DI_PRE", di_tenor, as_of_date,
            lookback_days=_HISTORY_LOOKBACK_DAYS,
        )
        ust_history = self.data_loader.get_curve_history(
            "UST_NOM", ust_tenor, as_of_date,
            lookback_days=_HISTORY_LOOKBACK_DAYS,
        )

        if di_history.empty or ust_history.empty:
            self.log.warning("missing_curve_history")
            return []

        # Compute historical spread series
        combined = di_history[["rate"]].rename(columns={"rate": "di_rate"}).join(
            ust_history[["rate"]].rename(columns={"rate": "ust_rate"}),
            how="inner",
        )

        if len(combined) < 60:
            self.log.warning("insufficient_history", rows=len(combined))
            return []

        combined["spread"] = combined["di_rate"] - combined["ust_rate"]
        spread_history = combined["spread"].tolist()

        # 6. Compute z-score
        z_score = self.compute_z_score(
            current_spread, spread_history, window=_HISTORY_WINDOW,
        )

        self.log.info(
            "onshore_offshore_analysis",
            onshore_rate=round(onshore_rate, 4),
            ust_rate=round(ust_rate, 4),
            current_spread=round(current_spread, 4),
            z_score=round(z_score, 3),
            di_tenor=di_tenor,
            ust_tenor=ust_tenor,
        )

        # 7. Check entry threshold
        if abs(z_score) < self.entry_z_threshold:
            return []

        # 8. Mean reversion direction
        # z > 0: onshore premium elevated => SHORT spread (expect compression)
        # z < 0: spread compressed => LONG spread (expect widening)
        if z_score > 0:
            direction = SignalDirection.SHORT
        else:
            direction = SignalDirection.LONG

        strength = self.classify_strength(z_score)
        confidence = min(1.0, abs(z_score) / 4.0)
        suggested_size = self.size_from_conviction(z_score)

        signal = StrategySignal(
            strategy_id=self.strategy_id,
            timestamp=datetime.utcnow(),
            direction=direction,
            strength=strength,
            confidence=confidence,
            z_score=z_score,
            raw_value=current_spread,
            suggested_size=suggested_size,
            asset_class=AssetClass.CUPOM_CAMBIAL,
            instruments=self.config.instruments,
            stop_loss=self.config.stop_loss_pct,
            take_profit=self.config.take_profit_pct,
            holding_period_days=_HOLDING_PERIOD_DAYS,
            metadata={
                "onshore_rate": onshore_rate,
                "ust_rate": ust_rate,
                "current_spread": current_spread,
                "z_score": z_score,
                "di_tenor": di_tenor,
                "ust_tenor": ust_tenor,
                "as_of_date": str(as_of_date),
            },
        )

        self.log.info(
            "onshore_offshore_signal",
            direction=direction.value,
            z_score=round(z_score, 3),
            confidence=round(confidence, 3),
        )

        return [signal]


"""RATES_03: BR-US Rate Spread strategy.

Trades the DI-UST spread adjusted for sovereign CDS at 2Y and 5Y tenors
via z-score mean reversion.  When the spread is wide relative to history
(z > threshold), the strategy goes LONG DI (expects spread compression).
When narrow (z < -threshold), goes SHORT DI.

The 2Y tenor is the primary signal (more liquid), with 5Y used as
confirmation.  CDS and inflation differentials provide adjustments.
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
RATES_03_CONFIG = StrategyConfig(
    strategy_id="RATES_03",
    strategy_name="BR-US Rate Spread",
    asset_class=AssetClass.RATES_BR,
    instruments=["DI_PRE", "UST_NOM"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
    max_leverage=3.0,
    stop_loss_pct=0.02,
    take_profit_pct=0.03,
)

# Tenor targets (business days for DI, calendar days for UST approximation)
_2Y_TENOR = 504
_5Y_TENOR = 1260
_SPREAD_LOOKBACK = 504  # ~2 years of business days for z-score


# Tolerance for tenor matching (large to replicate "find closest" behavior)
_TENOR_TOLERANCE = 10000


@StrategyRegistry.register(
    "RATES_03",
    asset_class=AssetClass.RATES_BR,
    instruments=["DI_PRE", "UST_NOM"],
)
class Rates03BrUsSpreadStrategy(BaseStrategy):
    """BR-US rate spread mean-reversion strategy.

    Trades the DI-UST spread at 2Y and 5Y tenors with CDS and inflation
    adjustments.  Uses z-score of the spread vs rolling history to
    identify mean-reversion opportunities.

    Args:
        data_loader: PointInTimeDataLoader for fetching curve and macro data.
        entry_z_threshold: Minimum |z| to trigger an entry (default 1.25).
        config: Optional StrategyConfig override.
    """

    def __init__(
        self,
        data_loader: PointInTimeDataLoader,
        entry_z_threshold: float = 1.25,
        config: StrategyConfig | None = None,
    ) -> None:
        super().__init__(config=config or RATES_03_CONFIG)
        self.data_loader = data_loader
        self.entry_z_threshold = entry_z_threshold
        self.log = structlog.get_logger().bind(strategy=self.strategy_id)

    def generate_signals(self, as_of_date: date) -> list[StrategySignal]:
        """Produce signals based on BR-US spread z-score mean reversion.

        Steps:
            1. Load DI and UST curves, extract 2Y and 5Y tenors.
            2. Compute raw and adjusted spreads (CDS, inflation).
            3. Build spread history, compute z-score.
            4. Use 2Y as primary signal, 5Y as confirmation.
            5. Return StrategySignal if |z| >= threshold.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            List of StrategySignal, or empty list if data insufficient.
        """
        # 1. Load current curves
        di_curve = self.data_loader.get_curve("DI_PRE", as_of_date)
        ust_curve = self.data_loader.get_curve("UST_NOM", as_of_date)

        if not di_curve or not ust_curve:
            self.log.warning("missing_curve_data", as_of_date=str(as_of_date))
            return []

        # Find closest tenors
        di_2y_tenor = find_closest_tenor(di_curve, _2Y_TENOR, _TENOR_TOLERANCE)
        ust_2y_tenor = find_closest_tenor(ust_curve, _2Y_TENOR, _TENOR_TOLERANCE)
        di_5y_tenor = find_closest_tenor(di_curve, _5Y_TENOR, _TENOR_TOLERANCE)
        ust_5y_tenor = find_closest_tenor(ust_curve, _5Y_TENOR, _TENOR_TOLERANCE)

        if any(
            t is None for t in [di_2y_tenor, ust_2y_tenor, di_5y_tenor, ust_5y_tenor]
        ):
            self.log.warning("tenor_not_found", as_of_date=str(as_of_date))
            return []

        # 2. Compute raw spreads
        raw_spread_2y = di_curve[di_2y_tenor] - ust_curve[ust_2y_tenor]
        raw_spread_5y = di_curve[di_5y_tenor] - ust_curve[ust_5y_tenor]

        # CDS adjustment
        cds_5y = self.data_loader.get_latest_macro_value("BR_CDS_5Y", as_of_date)
        if cds_5y is not None:
            # Convert CDS bps to percentage (e.g., 200bps -> 2.0%)
            cds_pct = cds_5y / 100.0
            adjusted_spread_2y = raw_spread_2y - cds_pct
            adjusted_spread_5y = raw_spread_5y - cds_pct
        else:
            adjusted_spread_2y = raw_spread_2y
            adjusted_spread_5y = raw_spread_5y

        # Inflation differential adjustment
        br_ipca = self.data_loader.get_latest_macro_value("BR_IPCA_12M", as_of_date)
        us_cpi = self.data_loader.get_latest_macro_value("US_CPI_YOY", as_of_date)
        if br_ipca is not None and us_cpi is not None:
            real_spread_2y = adjusted_spread_2y - (br_ipca - us_cpi)
            _ = adjusted_spread_5y - (br_ipca - us_cpi)  # 5Y reserved for future use
        else:
            real_spread_2y = adjusted_spread_2y
            _ = adjusted_spread_5y  # 5Y real spread reserved for future use

        # 3. Build spread history for 2Y (primary) using curve_history
        di_2y_hist = self.data_loader.get_curve_history(
            "DI_PRE", di_2y_tenor, as_of_date, lookback_days=756
        )
        ust_2y_hist = self.data_loader.get_curve_history(
            "UST_NOM", ust_2y_tenor, as_of_date, lookback_days=756
        )

        if di_2y_hist.empty or ust_2y_hist.empty:
            self.log.warning("insufficient_history", as_of_date=str(as_of_date))
            return []

        # Compute spread history
        spread_history = self._compute_spread_history(di_2y_hist, ust_2y_hist)
        if len(spread_history) < 60:
            self.log.warning(
                "short_spread_history",
                points=len(spread_history),
                as_of_date=str(as_of_date),
            )
            return []

        # Z-score of current 2Y spread vs history
        z_2y = self.compute_z_score(
            adjusted_spread_2y, spread_history, window=_SPREAD_LOOKBACK
        )

        # 5Y confirmation z-score (optional -- used for confirmation only)
        di_5y_hist = self.data_loader.get_curve_history(
            "DI_PRE", di_5y_tenor, as_of_date, lookback_days=756
        )
        ust_5y_hist = self.data_loader.get_curve_history(
            "UST_NOM", ust_5y_tenor, as_of_date, lookback_days=756
        )

        z_5y = 0.0
        if not di_5y_hist.empty and not ust_5y_hist.empty:
            spread_5y_hist = self._compute_spread_history(di_5y_hist, ust_5y_hist)
            if len(spread_5y_hist) >= 60:
                z_5y = self.compute_z_score(
                    adjusted_spread_5y, spread_5y_hist, window=_SPREAD_LOOKBACK
                )

        # 4. Signal generation
        if abs(z_2y) < self.entry_z_threshold:
            return []

        # Direction: z > 0 -> spread wide -> expect compression -> LONG DI
        # z < 0 -> spread narrow -> expect widening -> SHORT DI
        if z_2y > 0:
            direction = SignalDirection.LONG
        else:
            direction = SignalDirection.SHORT

        # Confirmation: if 5Y agrees, boost confidence
        same_direction = (z_2y > 0 and z_5y > 0) or (z_2y < 0 and z_5y < 0)
        confirmation_boost = 0.1 if same_direction else 0.0

        strength = self.classify_strength(z_2y)
        base_confidence = min(1.0, abs(z_2y) / (self.entry_z_threshold * 3))
        confidence = min(1.0, base_confidence + confirmation_boost)
        suggested_size = self.size_from_conviction(
            z_2y, max_size=self.config.max_position_size
        )

        signal = StrategySignal(
            strategy_id=self.config.strategy_id,
            timestamp=datetime.utcnow(),
            direction=direction,
            strength=strength,
            confidence=confidence,
            z_score=z_2y,
            raw_value=adjusted_spread_2y,
            suggested_size=suggested_size,
            asset_class=self.config.asset_class,
            instruments=self.config.instruments,
            stop_loss=self.config.stop_loss_pct,
            take_profit=self.config.take_profit_pct,
            holding_period_days=21,
            metadata={
                "raw_spread_2y": raw_spread_2y,
                "adjusted_spread_2y": adjusted_spread_2y,
                "real_spread_2y": real_spread_2y,
                "z_2y": z_2y,
                "z_5y": z_5y,
                "cds_5y": cds_5y,
                "br_ipca": br_ipca,
                "us_cpi": us_cpi,
                "di_2y_tenor": di_2y_tenor,
                "ust_2y_tenor": ust_2y_tenor,
                "confirmation": same_direction,
            },
        )

        self.log.info(
            "spread_signal",
            z_2y=round(z_2y, 3),
            z_5y=round(z_5y, 3),
            direction=direction.value,
            spread=round(adjusted_spread_2y, 4),
        )

        return [signal]

    def _compute_spread_history(
        self,
        di_hist,
        ust_hist,
    ) -> list[float]:
        """Compute DI-UST spread history as a list of floats.

        Aligns the two DataFrames on date, forward-fills holiday gaps,
        and returns the spread values as a list.

        Args:
            di_hist: DataFrame with 'rate' column for DI tenor.
            ust_hist: DataFrame with 'rate' column for UST tenor.

        Returns:
            List of spread values (DI - UST), most recent last.
        """
        combined = di_hist[["rate"]].join(
            ust_hist[["rate"]], lsuffix="_di", rsuffix="_ust", how="outer"
        )
        combined = combined.ffill().dropna()
        if combined.empty:
            return []
        spread_series = combined["rate_di"] - combined["rate_ust"]
        return spread_series.tolist()

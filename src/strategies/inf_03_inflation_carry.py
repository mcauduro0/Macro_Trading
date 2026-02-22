"""INF_03: Inflation Carry strategy.

Long/short breakeven (DI_PRE minus NTN_B_REAL) based on a composite score
comparing the market-implied breakeven to three fundamental benchmarks:

    1. BCB inflation target (3.0% +/- 1.5pp band).
    2. Current trailing 12M IPCA.
    3. Focus survey IPCA expectation.

When the composite z-score indicates the breakeven is too high relative
to fundamentals, the strategy shorts the breakeven (receive NTN-B, pay
DI_PRE).  When the breakeven is too low, the strategy goes long.

This is a carry-style strategy with a 21-day holding period.
"""

from __future__ import annotations

import math
from datetime import date, datetime

import structlog

from src.agents.data_loader import PointInTimeDataLoader
from src.core.enums import AssetClass, Frequency, SignalDirection, SignalStrength
from src.strategies.base import BaseStrategy, StrategyConfig, StrategySignal
from src.strategies.registry import StrategyRegistry

# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------
INF_03_CONFIG = StrategyConfig(
    strategy_id="INF_03",
    strategy_name="Inflation Carry",
    asset_class=AssetClass.INFLATION_BR,
    instruments=["DI_PRE", "NTN_B_REAL"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
    max_leverage=3.0,
    stop_loss_pct=0.015,
    take_profit_pct=0.020,
)

# BCB inflation target parameters
_BCB_TARGET = 3.0  # percent
_BCB_BAND = 1.5  # +/- 1.5pp
_BCB_UPPER = _BCB_TARGET + _BCB_BAND  # 4.5%

# 2Y tenor target
_2Y_TARGET = 504  # ~2 years in business days
_TENOR_TOLERANCE = 100

# Signal parameters
_ENTRY_Z_THRESHOLD = 1.0
_HOLDING_PERIOD_DAYS = 21
_HISTORY_WINDOW = 252  # 1 year of business days


@StrategyRegistry.register(
    "INF_03",
    asset_class=AssetClass.INFLATION_BR,
    instruments=["DI_PRE", "NTN_B_REAL"],
)
class Inf03InflationCarryStrategy(BaseStrategy):
    """Inflation Carry strategy comparing breakeven to fundamentals.

    Computes a composite z-score from three benchmark comparisons and
    trades the breakeven when the composite exceeds the entry threshold.

    Args:
        data_loader: PointInTimeDataLoader for fetching curve and macro data.
        entry_z_threshold: Minimum |composite_z| to trigger entry (default 1.0).
        config: Optional StrategyConfig override.
    """

    def __init__(
        self,
        data_loader: PointInTimeDataLoader,
        entry_z_threshold: float = _ENTRY_Z_THRESHOLD,
        config: StrategyConfig | None = None,
    ) -> None:
        super().__init__(config=config or INF_03_CONFIG)
        self.data_loader = data_loader
        self.entry_z_threshold = entry_z_threshold
        self.log = structlog.get_logger().bind(strategy=self.strategy_id)

    # ------------------------------------------------------------------
    # Main signal generation
    # ------------------------------------------------------------------
    def generate_signals(self, as_of_date: date) -> list[StrategySignal]:
        """Generate signals based on breakeven vs fundamentals.

        Steps:
            1. Load DI_PRE and NTN_B_REAL curves; extract 2Y rates.
            2. Compute breakeven_2y = DI_PRE_2Y - NTN_B_REAL_2Y.
            3. Load 3 benchmarks: BCB target, current IPCA 12M, Focus IPCA.
            4. Compute composite z-score from 3 comparisons over 252-day history.
            5. Generate signal if |composite_z| >= threshold.

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

        # 2. Load NTN-B curve
        ntnb_curve = self.data_loader.get_curve("NTN_B_REAL", as_of_date)
        if not ntnb_curve:
            self.log.warning("missing_ntnb_curve", as_of_date=str(as_of_date))
            return []

        # 3. Find 2Y tenors
        di_tenor = self._find_closest_tenor(di_curve, _2Y_TARGET, _TENOR_TOLERANCE)
        ntnb_tenor = self._find_closest_tenor(ntnb_curve, _2Y_TARGET, _TENOR_TOLERANCE)

        if di_tenor is None or ntnb_tenor is None:
            self.log.warning(
                "no_matching_2y_tenors",
                di_tenors=list(di_curve.keys()),
                ntnb_tenors=list(ntnb_curve.keys()),
            )
            return []

        # 4. Compute current breakeven
        di_2y = di_curve[di_tenor]
        ntnb_2y = ntnb_curve[ntnb_tenor]
        breakeven_2y = di_2y - ntnb_2y

        # 5. Load benchmarks
        # a. BCB target is a constant (3.0% with 1.5pp band)
        bcb_ref = _BCB_TARGET

        # b. Current IPCA 12M
        ipca_12m = self.data_loader.get_latest_macro_value(
            "BR_IPCA_12M", as_of_date,
        )
        if ipca_12m is None:
            self.log.warning("missing_ipca_12m", as_of_date=str(as_of_date))
            return []

        # c. Focus IPCA expectation
        focus_df = self.data_loader.get_focus_expectations("IPCA", as_of_date)
        if focus_df.empty:
            self.log.warning("missing_focus_ipca", as_of_date=str(as_of_date))
            return []
        focus_ipca = float(focus_df["value"].iloc[-1])

        # 6. Load breakeven history for z-score computation
        di_history = self.data_loader.get_curve_history(
            "DI_PRE", di_tenor, as_of_date, lookback_days=756,
        )
        ntnb_history = self.data_loader.get_curve_history(
            "NTN_B_REAL", ntnb_tenor, as_of_date, lookback_days=756,
        )

        if di_history.empty or ntnb_history.empty:
            self.log.warning("missing_curve_history")
            return []

        # Compute historical breakeven series
        combined = di_history[["rate"]].rename(columns={"rate": "di_rate"}).join(
            ntnb_history[["rate"]].rename(columns={"rate": "ntnb_rate"}),
            how="inner",
        )

        if len(combined) < 60:
            self.log.warning("insufficient_history", rows=len(combined))
            return []

        combined["breakeven"] = combined["di_rate"] - combined["ntnb_rate"]
        be_history = combined["breakeven"].tolist()

        # 7. Compute 3 z-scores comparing breakeven to benchmarks
        z_bcb = self.compute_z_score(
            breakeven_2y - bcb_ref,
            [(be - bcb_ref) for be in be_history],
            window=_HISTORY_WINDOW,
        )
        z_ipca = self.compute_z_score(
            breakeven_2y - ipca_12m,
            [(be - ipca_12m) for be in be_history],
            window=_HISTORY_WINDOW,
        )
        z_focus = self.compute_z_score(
            breakeven_2y - focus_ipca,
            [(be - focus_ipca) for be in be_history],
            window=_HISTORY_WINDOW,
        )

        composite_z = (z_bcb + z_ipca + z_focus) / 3.0

        self.log.info(
            "inflation_carry_analysis",
            breakeven_2y=round(breakeven_2y, 4),
            bcb_target=_BCB_TARGET,
            ipca_12m=round(ipca_12m, 4),
            focus_ipca=round(focus_ipca, 4),
            z_bcb=round(z_bcb, 3),
            z_ipca=round(z_ipca, 3),
            z_focus=round(z_focus, 3),
            composite_z=round(composite_z, 3),
        )

        # 8. Check entry threshold
        if abs(composite_z) < self.entry_z_threshold:
            return []

        # 9. Direction
        # composite > 0: breakeven too high vs fundamentals => SHORT breakeven
        # composite < 0: breakeven too low => LONG breakeven
        if composite_z > 0:
            direction = SignalDirection.SHORT
        else:
            direction = SignalDirection.LONG

        strength = self.classify_strength(composite_z)
        confidence = min(1.0, abs(composite_z) / 3.0)
        suggested_size = self.size_from_conviction(composite_z)

        signal = StrategySignal(
            strategy_id=self.strategy_id,
            timestamp=datetime.utcnow(),
            direction=direction,
            strength=strength,
            confidence=confidence,
            z_score=composite_z,
            raw_value=breakeven_2y,
            suggested_size=suggested_size,
            asset_class=AssetClass.INFLATION_BR,
            instruments=self.config.instruments,
            stop_loss=self.config.stop_loss_pct,
            take_profit=self.config.take_profit_pct,
            holding_period_days=_HOLDING_PERIOD_DAYS,
            metadata={
                "breakeven_2y": breakeven_2y,
                "di_2y": di_2y,
                "ntnb_2y": ntnb_2y,
                "bcb_target": _BCB_TARGET,
                "ipca_12m": ipca_12m,
                "focus_ipca": focus_ipca,
                "z_bcb": z_bcb,
                "z_ipca": z_ipca,
                "z_focus": z_focus,
                "composite_z": composite_z,
                "as_of_date": str(as_of_date),
            },
        )

        self.log.info(
            "inflation_carry_signal",
            direction=direction.value,
            composite_z=round(composite_z, 3),
            confidence=round(confidence, 3),
        )

        return [signal]

    # ------------------------------------------------------------------
    # Tenor matching helper
    # ------------------------------------------------------------------
    @staticmethod
    def _find_closest_tenor(
        curve: dict[int, float],
        target: int,
        tolerance: int,
    ) -> int | None:
        """Find the closest available tenor to the target within tolerance.

        Args:
            curve: Tenor-to-rate mapping.
            target: Target tenor in days.
            tolerance: Maximum allowed distance from target.

        Returns:
            Closest tenor, or None if nothing within tolerance.
        """
        best_tenor = None
        best_dist = float("inf")
        for tenor in curve:
            dist = abs(tenor - target)
            if dist < best_dist and dist <= tolerance:
                best_dist = dist
                best_tenor = tenor
        return best_tenor

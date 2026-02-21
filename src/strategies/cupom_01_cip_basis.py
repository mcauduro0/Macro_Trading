"""CUPOM_01: Cupom Cambial CIP Basis Mean Reversion strategy.

Fades extreme z-scores in the CIP (Covered Interest Parity) basis
-- the cupom cambial minus the SOFR rate.  When the basis is abnormally
wide (BRL funding premium too high) the strategy shorts the basis
(expects compression).  When the basis is abnormally narrow the strategy
goes long the basis (expects widening).

The strategy produces a single StrategyPosition for the basis trade
using DI_PRE and USDBRL as instruments.
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
CUPOM_01_CONFIG = StrategyConfig(
    strategy_id="CUPOM_01",
    strategy_name="Cupom Cambial CIP Basis Mean Reversion",
    asset_class=AssetClass.FIXED_INCOME,
    instruments=["DI_PRE", "USDBRL"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
    max_leverage=3.0,
    stop_loss_pct=0.03,
    take_profit_pct=0.06,
)

# 1Y tenor target and tolerance for curve tenor matching
_1Y_TARGET = 365
_TENOR_TOLERANCE = 80


class Cupom01CipBasisStrategy(BaseStrategy):
    """CIP Basis Mean Reversion strategy on cupom cambial vs SOFR.

    Computes the CIP basis (simplified cupom cambial minus SOFR) and
    fades extreme z-scores relative to a 252-day rolling window.

    Args:
        data_loader: PointInTimeDataLoader for fetching curve and macro data.
        basis_z_threshold: Z-score threshold to trigger a position (default 2.0).
        config: Optional StrategyConfig override.
    """

    def __init__(
        self,
        data_loader: PointInTimeDataLoader,
        basis_z_threshold: float = 2.0,
        config: StrategyConfig | None = None,
    ) -> None:
        super().__init__(config=config or CUPOM_01_CONFIG)
        self.data_loader = data_loader
        self.basis_z_threshold = basis_z_threshold
        self.log = structlog.get_logger().bind(strategy=self.strategy_id)

    def generate_signals(self, as_of_date: date) -> list[StrategyPosition]:
        """Produce target positions based on CIP basis mean reversion.

        Steps:
            1. Load DI_PRE and UST_NOM curves for 1Y tenor.
            2. Compute cupom cambial = DI_1Y - UST_1Y.
            3. Load SOFR (or Fed Funds fallback).
            4. Compute CIP basis = cupom - sofr.
            5. Compute z-score of current basis vs 252-day history.
            6. Mean reversion: fade extreme z-scores.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            List with a single StrategyPosition, or empty list when data
            is missing or basis is within the neutral z-score band.
        """
        # 1. Load DI_PRE curve
        di_curve = self.data_loader.get_curve("DI_PRE", as_of_date)
        if not di_curve:
            self.log.warning("missing_di_curve", as_of_date=str(as_of_date))
            return []

        # 2. Load UST_NOM curve
        ust_curve = self.data_loader.get_curve("UST_NOM", as_of_date)
        if not ust_curve:
            self.log.warning("missing_ust_curve", as_of_date=str(as_of_date))
            return []

        # 3. Find 1Y tenors
        di_1y = self._find_closest_tenor(di_curve, _1Y_TARGET, _TENOR_TOLERANCE)
        ust_1y = self._find_closest_tenor(ust_curve, _1Y_TARGET, _TENOR_TOLERANCE)

        if di_1y is None or ust_1y is None:
            self.log.warning(
                "no_matching_1y_tenors",
                di_tenors=list(di_curve.keys()),
                ust_tenors=list(ust_curve.keys()),
            )
            return []

        # 4. Compute cupom cambial (simplified: DI_1Y - UST_1Y)
        cupom_cambial = di_curve[di_1y] - ust_curve[ust_1y]

        # 5. Load SOFR / Fed Funds
        sofr_rate = self.data_loader.get_latest_macro_value("US_SOFR", as_of_date)
        if sofr_rate is None:
            sofr_rate = self.data_loader.get_latest_macro_value(
                "US_FED_FUNDS", as_of_date,
            )
        if sofr_rate is None:
            self.log.warning("missing_sofr", as_of_date=str(as_of_date))
            return []

        # 6. Compute current CIP basis
        current_basis = cupom_cambial - sofr_rate

        # 7. Load historical basis from curve histories
        di_history = self.data_loader.get_curve_history(
            "DI_PRE", di_1y, as_of_date, lookback_days=756,
        )
        ust_history = self.data_loader.get_curve_history(
            "UST_NOM", ust_1y, as_of_date, lookback_days=756,
        )

        if di_history.empty or ust_history.empty:
            self.log.warning("insufficient_curve_history")
            return []

        # Align histories via outer join + forward fill
        combined = di_history[["rate"]].rename(columns={"rate": "di_rate"}).join(
            ust_history[["rate"]].rename(columns={"rate": "ust_rate"}),
            how="inner",
        )

        if len(combined) < 60:
            self.log.warning("insufficient_history_overlap", rows=len(combined))
            return []

        # Historical basis series (simplified: DI - UST - SOFR)
        combined["basis"] = combined["di_rate"] - combined["ust_rate"] - sofr_rate

        # 8. Compute z-score of current basis vs 252-day rolling stats
        hist_window = combined["basis"].tail(252) if len(combined) >= 252 else combined["basis"]
        basis_mean = float(hist_window.mean())
        basis_std = float(hist_window.std())

        if basis_std <= 0 or math.isnan(basis_std):
            self.log.warning("zero_basis_std")
            return []

        z_score = (current_basis - basis_mean) / basis_std

        self.log.info(
            "cip_basis_analysis",
            cupom_cambial=round(cupom_cambial, 4),
            sofr_rate=sofr_rate,
            current_basis=round(current_basis, 4),
            basis_mean=round(basis_mean, 4),
            basis_std=round(basis_std, 4),
            z_score=round(z_score, 4),
        )

        # 9. Strategy logic: mean reversion on CIP basis extremes
        if z_score > self.basis_z_threshold:
            # Basis extremely wide -> SHORT basis (expect compression)
            direction = SignalDirection.SHORT
        elif z_score < -self.basis_z_threshold:
            # Basis extremely narrow -> LONG basis (expect widening)
            direction = SignalDirection.LONG
        else:
            # Within neutral band
            return []

        confidence = min(1.0, abs(z_score) / (self.basis_z_threshold * 2))
        strength = classify_strength(confidence)

        signal = AgentSignal(
            signal_id=f"CIP_BASIS_{di_1y}",
            agent_id=self.strategy_id,
            timestamp=np.datetime64("now"),
            as_of_date=as_of_date,
            direction=direction,
            strength=strength,
            confidence=confidence,
            value=z_score,
            horizon_days=63,  # quarterly horizon
            metadata={
                "cupom_cambial": cupom_cambial,
                "sofr_rate": sofr_rate,
                "current_basis": current_basis,
                "basis_mean": basis_mean,
                "basis_std": basis_std,
                "z_score": z_score,
            },
        )

        positions = self.signals_to_positions([signal])

        # Enrich metadata
        for pos in positions:
            pos.metadata.update({
                "cupom_cambial": cupom_cambial,
                "sofr_rate": sofr_rate,
                "current_basis": current_basis,
                "z_score": z_score,
                "di_tenor": di_1y,
                "ust_tenor": ust_1y,
                "curve_date": str(as_of_date),
            })

        return positions

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

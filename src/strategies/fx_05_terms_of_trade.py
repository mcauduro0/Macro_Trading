"""FX_05: Terms of Trade FX strategy for USDBRL.

Builds a commodity-weighted terms of trade (ToT) index for Brazil and
compares its movement to USDBRL to detect misalignment:

- **ToT Index**: Weighted sum of 63-day log returns for:
  - Soybean (30%), Iron Ore (25%), Oil/Brent (20%), Sugar (15%), Coffee (10%)
- **Misalignment**: ToT z-score minus USDBRL return z-score.
  - Positive misalignment: ToT improving faster than BRL appreciating
    => SHORT USDBRL (expect BRL catch-up).
  - Negative misalignment: ToT deteriorating faster than BRL depreciating
    => LONG USDBRL.

Entry threshold: |misalignment| >= 1.0.
Stop-loss: fixed 4% (slow-moving fundamental).
Take-profit: fixed 6%.
Holding period: 28 days.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Optional

import numpy as np
import structlog

from src.agents.data_loader import PointInTimeDataLoader
from src.core.enums import AssetClass, Frequency, SignalDirection, SignalStrength
from src.strategies.base import (
    BaseStrategy,
    StrategyConfig,
    StrategySignal,
)
from src.strategies.registry import StrategyRegistry

# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------
FX_05_CONFIG = StrategyConfig(
    strategy_id="FX_05",
    strategy_name="USDBRL Terms of Trade Misalignment",
    asset_class=AssetClass.FX,
    instruments=["USDBRL"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
    max_leverage=3.0,
    stop_loss_pct=0.04,
    take_profit_pct=0.06,
)

# ---------------------------------------------------------------------------
# Strategy parameters
# ---------------------------------------------------------------------------
# Commodity weights reflecting Brazil export composition
_COMMODITY_WEIGHTS: dict[str, float] = {
    "ZS=F": 0.30,   # Soybean
    "TIO=F": 0.25,  # Iron Ore
    "BZ=F": 0.20,   # Brent Oil
    "SB=F": 0.15,   # Sugar
    "KC=F": 0.10,   # Coffee
}
# Fallback tickers for commodities
_COMMODITY_FALLBACKS: dict[str, list[str]] = {
    "ZS=F": ["SOYBEAN", "ZS_F"],
    "TIO=F": ["IRON_ORE", "VALE", "TIO_F"],
    "BZ=F": ["BRENT", "BZ_F", "CL=F"],
    "SB=F": ["SUGAR", "SB_F"],
    "KC=F": ["COFFEE", "KC_F"],
}
_RETURN_WINDOW = 63
_HISTORY_LOOKBACK = 504
_ENTRY_THRESHOLD = 1.0
_STOP_LOSS_PCT = 0.04
_TAKE_PROFIT_PCT = 0.06
_HOLDING_PERIOD = 28


@StrategyRegistry.register("FX_05", asset_class=AssetClass.FX, instruments=["USDBRL"])
class Fx05TermsOfTradeStrategy(BaseStrategy):
    """USDBRL Terms of Trade Misalignment strategy.

    Compares commodity-weighted ToT index changes to USDBRL movements
    and trades the misalignment.

    Args:
        data_loader: PointInTimeDataLoader for fetching market data.
        config: Optional StrategyConfig override.
    """

    def __init__(
        self,
        data_loader: PointInTimeDataLoader,
        config: StrategyConfig | None = None,
    ) -> None:
        super().__init__(config=config or FX_05_CONFIG)
        self.data_loader = data_loader
        self.log = structlog.get_logger().bind(strategy=self.strategy_id)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def generate_signals(self, as_of_date: date) -> list[StrategySignal]:
        """Produce StrategySignal for USDBRL based on ToT misalignment.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            List with a single StrategySignal, or empty list when data
            is missing or the misalignment is below entry threshold.
        """
        # --- Compute ToT z-score ---
        tot_z = self._compute_tot_z(as_of_date)
        if tot_z is None:
            return []

        # --- Compute USDBRL return z-score ---
        usdbrl_z = self._compute_usdbrl_return_z(as_of_date)
        if usdbrl_z is None:
            return []

        # --- Misalignment ---
        misalignment = tot_z - usdbrl_z

        self.log.info(
            "fx05_misalignment",
            tot_z=round(tot_z, 4),
            usdbrl_z=round(usdbrl_z, 4),
            misalignment=round(misalignment, 4),
        )

        # Entry threshold
        if abs(misalignment) < _ENTRY_THRESHOLD:
            return []

        # Direction:
        # misalignment > 0: ToT improving faster => SHORT USDBRL (BRL catch-up)
        # misalignment < 0: ToT deteriorating faster => LONG USDBRL
        if misalignment > 0:
            direction = SignalDirection.SHORT
        else:
            direction = SignalDirection.LONG

        # --- USDBRL spot for stop/take-profit ---
        usdbrl_df = self.data_loader.get_market_data(
            "USDBRL", as_of_date, lookback_days=30,
        )
        if usdbrl_df.empty:
            return []

        spot = float(usdbrl_df["close"].iloc[-1])

        # Fixed stop/take-profit
        if direction == SignalDirection.SHORT:
            stop_loss = spot * (1.0 + _STOP_LOSS_PCT)
            take_profit = spot * (1.0 - _TAKE_PROFIT_PCT)
        else:
            stop_loss = spot * (1.0 - _STOP_LOSS_PCT)
            take_profit = spot * (1.0 + _TAKE_PROFIT_PCT)

        strength = self.classify_strength(misalignment)
        confidence = min(1.0, abs(misalignment) / 3.0)
        suggested_size = self.size_from_conviction(misalignment)

        signal = StrategySignal(
            strategy_id=self.strategy_id,
            timestamp=datetime.utcnow(),
            direction=direction,
            strength=strength,
            confidence=confidence,
            z_score=misalignment,
            raw_value=misalignment,
            suggested_size=suggested_size,
            asset_class=AssetClass.FX,
            instruments=["USDBRL"],
            entry_level=spot,
            stop_loss=stop_loss,
            take_profit=take_profit,
            holding_period_days=_HOLDING_PERIOD,
            metadata={
                "tot_z": tot_z,
                "usdbrl_z": usdbrl_z,
                "misalignment": misalignment,
                "spot": spot,
            },
        )
        return [signal]

    # ------------------------------------------------------------------
    # ToT index computation
    # ------------------------------------------------------------------
    def _compute_tot_z(self, as_of_date: date) -> Optional[float]:
        """Compute commodity-weighted ToT change z-score.

        Returns None if insufficient commodity data is available.
        """
        commodity_returns: dict[str, list[float]] = {}

        for primary_ticker, weight in _COMMODITY_WEIGHTS.items():
            # Try primary ticker first, then fallbacks
            tickers_to_try = [primary_ticker] + _COMMODITY_FALLBACKS.get(primary_ticker, [])
            df = None

            for ticker in tickers_to_try:
                candidate = self.data_loader.get_market_data(
                    ticker, as_of_date, lookback_days=_HISTORY_LOOKBACK + 100,
                )
                if not candidate.empty and len(candidate) >= _RETURN_WINDOW + 20:
                    df = candidate
                    break

            if df is None:
                self.log.warning(
                    "fx05_missing_commodity",
                    ticker=primary_ticker,
                    as_of_date=str(as_of_date),
                )
                return None

            # Compute 63-day log returns
            closes = df["close"]
            log_ret = np.log(closes / closes.shift(_RETURN_WINDOW)).dropna()
            commodity_returns[primary_ticker] = log_ret

        # Align all commodity return series on common dates
        if not commodity_returns:
            return None

        # Find common index across all commodities
        common_idx = None
        for series in commodity_returns.values():
            if common_idx is None:
                common_idx = series.index
            else:
                common_idx = common_idx.intersection(series.index)

        if common_idx is None or len(common_idx) < 20:
            return None

        # Compute weighted ToT changes
        tot_changes = np.zeros(len(common_idx))
        for primary_ticker, weight in _COMMODITY_WEIGHTS.items():
            aligned = commodity_returns[primary_ticker].reindex(common_idx)
            tot_changes += weight * aligned.values

        if len(tot_changes) < 20:
            return None

        current_tot = float(tot_changes[-1])
        history_list = list(tot_changes[-_HISTORY_LOOKBACK:])
        return self.compute_z_score(current_tot, history_list, window=_HISTORY_LOOKBACK)

    # ------------------------------------------------------------------
    # USDBRL return z-score
    # ------------------------------------------------------------------
    def _compute_usdbrl_return_z(self, as_of_date: date) -> Optional[float]:
        """Compute USDBRL 63-day return z-score vs history.

        Returns None if insufficient data.
        """
        usdbrl_df = self.data_loader.get_market_data(
            "USDBRL", as_of_date, lookback_days=_HISTORY_LOOKBACK + 100,
        )
        if usdbrl_df.empty or len(usdbrl_df) < _RETURN_WINDOW + 20:
            return None

        closes = usdbrl_df["close"]
        log_ret = np.log(closes / closes.shift(_RETURN_WINDOW)).dropna()

        if len(log_ret) < 20:
            return None

        current_ret = float(log_ret.iloc[-1])
        history_list = log_ret.tail(_HISTORY_LOOKBACK).tolist()
        return self.compute_z_score(current_ret, history_list, window=_HISTORY_LOOKBACK)

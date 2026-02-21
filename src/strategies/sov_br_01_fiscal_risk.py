"""SOV_BR_01: BR Fiscal Risk Premium strategy.

Trades the fiscal dominance risk premium in long-end DI rates and USDBRL.
Combines a fiscal risk score (debt-to-GDP + primary balance) with the
sovereign spread level to identify mispricing:

- **High fiscal risk + spread underpriced** -> SHORT long-end DI (expect
  rates to rise) and LONG USDBRL (expect BRL depreciation).
- **Low fiscal risk + spread overpriced** -> LONG long-end DI (expect rates
  to fall) and SHORT USDBRL (expect BRL appreciation).

The strategy may produce up to 2 positions (DI + USDBRL) when both
instruments are triggered.
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
SOV_BR_01_CONFIG = StrategyConfig(
    strategy_id="SOV_BR_01",
    strategy_name="BR Fiscal Risk Premium",
    asset_class=AssetClass.FIXED_INCOME,
    instruments=["DI_PRE", "USDBRL"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
    max_leverage=3.0,
    stop_loss_pct=0.05,
    take_profit_pct=0.12,
)


class SovBR01FiscalRiskStrategy(BaseStrategy):
    """BR Fiscal Risk Premium strategy.

    Combines a fiscal risk score with the sovereign spread z-score
    to identify fiscal dominance risk mispricing in long-end DI
    rates and USDBRL.

    Args:
        data_loader: PointInTimeDataLoader for fetching macro/curve data.
        debt_gdp_warning: Debt-to-GDP threshold for elevated risk (default 80.0).
        spread_z_threshold: Z-score threshold for spread mispricing (default 1.5).
        config: Optional StrategyConfig override.
    """

    def __init__(
        self,
        data_loader: PointInTimeDataLoader,
        debt_gdp_warning: float = 80.0,
        spread_z_threshold: float = 1.5,
        config: StrategyConfig | None = None,
    ) -> None:
        super().__init__(config=config or SOV_BR_01_CONFIG)
        self.data_loader = data_loader
        self.debt_gdp_warning = debt_gdp_warning
        self.spread_z_threshold = spread_z_threshold
        self.log = structlog.get_logger().bind(strategy=self.strategy_id)

    def generate_signals(self, as_of_date: date) -> list[StrategyPosition]:
        """Produce target positions based on fiscal risk vs spread mispricing.

        Steps:
            1. Load fiscal data (debt-to-GDP, primary balance).
            2. Compute fiscal risk score (0-1).
            3. Load long-end DI rate and sovereign spread.
            4. Compute spread z-score vs 252-day history.
            5. Generate positions based on risk/spread combination.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            List of 0-2 StrategyPosition objects.
        """
        # 1. Load debt-to-GDP
        debt_gdp = self.data_loader.get_latest_macro_value(
            "BR_GROSS_DEBT_GDP", as_of_date,
        )
        if debt_gdp is None:
            debt_gdp = self.data_loader.get_latest_macro_value(
                "BR_NET_DEBT_GDP", as_of_date,
            )
        if debt_gdp is None:
            self.log.warning("missing_debt_gdp", as_of_date=str(as_of_date))
            return []

        # 2. Load primary balance
        primary_balance = self.data_loader.get_latest_macro_value(
            "BR_PRIMARY_BALANCE_GDP", as_of_date,
        )
        if primary_balance is None:
            self.log.warning("missing_primary_balance", as_of_date=str(as_of_date))
            return []

        # 3. Compute fiscal risk score (0-1)
        fiscal_risk = self._compute_fiscal_risk(debt_gdp, primary_balance)

        # 4. Load long-end DI rate
        di_curve = self.data_loader.get_curve("DI_PRE", as_of_date)
        if not di_curve:
            self.log.warning("missing_di_curve", as_of_date=str(as_of_date))
            return []

        # Get longest available tenor (5Y or 10Y)
        long_tenor = max(di_curve.keys())
        long_di_rate = di_curve[long_tenor]

        # 5. Load sovereign spread proxy
        spread = self._get_sovereign_spread(as_of_date, di_curve, long_tenor)
        if spread is None:
            self.log.warning("missing_spread", as_of_date=str(as_of_date))
            return []

        # 6. Compute spread z-score vs 252-day history
        spread_z = self._compute_spread_zscore(
            as_of_date, di_curve, long_tenor, spread,
        )
        if spread_z is None:
            self.log.warning("insufficient_spread_history")
            return []

        self.log.info(
            "fiscal_risk_analysis",
            debt_gdp=debt_gdp,
            primary_balance=primary_balance,
            fiscal_risk=round(fiscal_risk, 4),
            long_di_rate=round(long_di_rate, 4),
            spread=round(spread, 4),
            spread_z=round(spread_z, 4),
        )

        # 7. Strategy logic
        return self._generate_positions(
            fiscal_risk, spread_z, long_tenor, as_of_date,
            debt_gdp, primary_balance, long_di_rate, spread,
        )

    # ------------------------------------------------------------------
    # Fiscal risk computation
    # ------------------------------------------------------------------
    def _compute_fiscal_risk(
        self,
        debt_gdp: float,
        primary_balance: float,
    ) -> float:
        """Compute normalized fiscal risk score in [0, 1].

        Args:
            debt_gdp: Debt-to-GDP ratio in percent.
            primary_balance: Primary balance as % of GDP (negative = deficit).

        Returns:
            Fiscal risk score between 0 and 1.
        """
        # Debt risk: linear mapping from 60% to 100% GDP
        debt_risk = min(100.0, max(0.0, (debt_gdp - 60.0) / 40.0 * 100.0))

        # Balance risk: deficit increases risk, surplus decreases it
        balance_risk = 0.0
        if primary_balance < 0:
            balance_risk = abs(primary_balance) * 20.0
        else:
            balance_risk = -primary_balance * 10.0

        fiscal_raw = max(0.0, min(100.0, debt_risk + balance_risk))
        return fiscal_raw / 100.0

    # ------------------------------------------------------------------
    # Sovereign spread
    # ------------------------------------------------------------------
    def _get_sovereign_spread(
        self,
        as_of_date: date,
        di_curve: dict[int, float],
        long_tenor: int,
    ) -> float | None:
        """Get sovereign spread (CDS or DI-UST spread proxy).

        Args:
            as_of_date: PIT reference date.
            di_curve: DI curve snapshot.
            long_tenor: Longest DI tenor.

        Returns:
            Spread in percentage points, or None if unavailable.
        """
        # Try CDS 5Y first
        cds = self.data_loader.get_latest_macro_value("BR_CDS_5Y", as_of_date)
        if cds is not None:
            return cds / 100.0  # CDS in bps -> percentage points

        # Fallback: DI_5Y - UST_5Y
        ust_curve = self.data_loader.get_curve("UST_NOM", as_of_date)
        if not ust_curve:
            # Use DI long-end directly as spread proxy
            return di_curve[long_tenor]

        # Find matching UST tenor
        ust_tenor = None
        best_dist = float("inf")
        for tenor in ust_curve:
            dist = abs(tenor - long_tenor)
            if dist < best_dist:
                best_dist = dist
                ust_tenor = tenor

        if ust_tenor is None:
            return di_curve[long_tenor]

        return di_curve[long_tenor] - ust_curve[ust_tenor]

    # ------------------------------------------------------------------
    # Spread z-score
    # ------------------------------------------------------------------
    def _compute_spread_zscore(
        self,
        as_of_date: date,
        di_curve: dict[int, float],
        long_tenor: int,
        current_spread: float,
    ) -> float | None:
        """Compute z-score of current spread vs 252-day rolling stats.

        Uses the long-end DI rate history as spread proxy history.

        Args:
            as_of_date: PIT reference date.
            di_curve: DI curve snapshot.
            long_tenor: DI curve tenor.
            current_spread: Current sovereign spread.

        Returns:
            Z-score, or None if insufficient history.
        """
        di_history = self.data_loader.get_curve_history(
            "DI_PRE", long_tenor, as_of_date, lookback_days=756,
        )

        if di_history.empty or len(di_history) < 60:
            return None

        # Use DI long-end rate history as spread proxy
        hist_window = di_history["rate"].tail(252) if len(di_history) >= 252 else di_history["rate"]
        spread_mean = float(hist_window.mean())
        spread_std = float(hist_window.std())

        if spread_std <= 0 or math.isnan(spread_std):
            return None

        # Current long-end DI rate z-score (used as spread z-score proxy)
        z_score = (di_curve[long_tenor] - spread_mean) / spread_std
        return z_score

    # ------------------------------------------------------------------
    # Position generation
    # ------------------------------------------------------------------
    def _generate_positions(
        self,
        fiscal_risk: float,
        spread_z: float,
        long_tenor: int,
        as_of_date: date,
        debt_gdp: float,
        primary_balance: float,
        long_di_rate: float,
        spread: float,
    ) -> list[StrategyPosition]:
        """Generate positions based on fiscal risk and spread mispricing.

        Args:
            fiscal_risk: Normalized fiscal risk score [0, 1].
            spread_z: Spread z-score.
            long_tenor: DI curve tenor used.
            as_of_date: Reference date.
            debt_gdp: Debt-to-GDP for metadata.
            primary_balance: Primary balance for metadata.
            long_di_rate: Long-end DI rate for metadata.
            spread: Current spread for metadata.

        Returns:
            List of 0-2 StrategyPosition objects.
        """
        positions: list[StrategyPosition] = []

        base_metadata = {
            "fiscal_risk": fiscal_risk,
            "spread_z": spread_z,
            "debt_gdp": debt_gdp,
            "primary_balance": primary_balance,
            "long_di_rate": long_di_rate,
            "spread": spread,
            "long_tenor": long_tenor,
            "curve_date": str(as_of_date),
        }

        if fiscal_risk > 0.6 and spread_z < -self.spread_z_threshold:
            # High fiscal risk + spread below average (underpriced risk)
            # SHORT DI long-end (expect rates to rise)
            confidence_di = min(
                1.0, fiscal_risk * abs(spread_z) / self.spread_z_threshold,
            )
            strength_di = classify_strength(confidence_di)

            di_signal = AgentSignal(
                signal_id=f"DI_PRE_{long_tenor}",
                agent_id=self.strategy_id,
                timestamp=np.datetime64("now"),
                as_of_date=as_of_date,
                direction=SignalDirection.SHORT,
                strength=strength_di,
                confidence=confidence_di,
                value=spread_z,
                horizon_days=63,
                metadata=base_metadata,
            )
            di_positions = self.signals_to_positions([di_signal])
            for pos in di_positions:
                pos.metadata.update(base_metadata)
                pos.metadata["trade_type"] = "fiscal_dominance_short_di"
            positions.extend(di_positions)

            # LONG USDBRL (expect BRL depreciation)
            usdbrl_signal = AgentSignal(
                signal_id="USDBRL",
                agent_id=self.strategy_id,
                timestamp=np.datetime64("now"),
                as_of_date=as_of_date,
                direction=SignalDirection.LONG,
                strength=strength_di,
                confidence=confidence_di,
                value=spread_z,
                horizon_days=63,
                metadata=base_metadata,
            )
            usdbrl_positions = self.signals_to_positions([usdbrl_signal])
            for pos in usdbrl_positions:
                pos.metadata.update(base_metadata)
                pos.metadata["trade_type"] = "fiscal_dominance_long_usdbrl"
            positions.extend(usdbrl_positions)

        elif fiscal_risk < 0.3 and spread_z > self.spread_z_threshold:
            # Low fiscal risk + spread above average (overpriced risk)
            # LONG DI long-end (expect rates to fall)
            confidence_di = min(
                1.0,
                (1.0 - fiscal_risk) * abs(spread_z) / self.spread_z_threshold,
            )
            strength_di = classify_strength(confidence_di)

            di_signal = AgentSignal(
                signal_id=f"DI_PRE_{long_tenor}",
                agent_id=self.strategy_id,
                timestamp=np.datetime64("now"),
                as_of_date=as_of_date,
                direction=SignalDirection.LONG,
                strength=strength_di,
                confidence=confidence_di,
                value=spread_z,
                horizon_days=63,
                metadata=base_metadata,
            )
            di_positions = self.signals_to_positions([di_signal])
            for pos in di_positions:
                pos.metadata.update(base_metadata)
                pos.metadata["trade_type"] = "fiscal_compression_long_di"
            positions.extend(di_positions)

            # SHORT USDBRL (expect BRL appreciation)
            usdbrl_signal = AgentSignal(
                signal_id="USDBRL",
                agent_id=self.strategy_id,
                timestamp=np.datetime64("now"),
                as_of_date=as_of_date,
                direction=SignalDirection.SHORT,
                strength=strength_di,
                confidence=confidence_di,
                value=spread_z,
                horizon_days=63,
                metadata=base_metadata,
            )
            usdbrl_positions = self.signals_to_positions([usdbrl_signal])
            for pos in usdbrl_positions:
                pos.metadata.update(base_metadata)
                pos.metadata["trade_type"] = "fiscal_compression_short_usdbrl"
            positions.extend(usdbrl_positions)

        # Else: NEUTRAL -- no positions

        return positions

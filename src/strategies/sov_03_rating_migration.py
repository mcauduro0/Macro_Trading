"""SOV_03: Rating Migration Anticipation strategy.

Logistic model for upgrade/downgrade probability based on four
fundamental factors:

- **Fiscal factor (35%)**: Debt-to-GDP deviation from 80% threshold.
- **Growth factor (25%)**: GDP growth deviation from 2.0% neutral.
- **External factor (20%)**: Trade balance proxy (surplus = positive for
  rating).
- **Political/institutional factor (20%)**: 63-day CDS change z-score
  as market-perceived institutional risk proxy.

Trade logic:
    - p_downgrade > 0.65 => LONG CDS (buy protection, anticipate downgrade).
    - p_downgrade < 0.35 (p_upgrade > 0.65) => SHORT CDS (sell protection,
      anticipate upgrade).
    - Between 0.35 and 0.65 => no signal.

Entry threshold: |z| >= 1.0 (equivalent to p outside 0.35-0.65 range).
Stop-loss: 20% of CDS level.
Take-profit: 15%.
Holding period: 28 days (rating changes are slow).
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Optional

import structlog

from src.agents.data_loader import PointInTimeDataLoader
from src.core.enums import AssetClass, Frequency, SignalDirection, SignalStrength
from src.strategies.base import BaseStrategy, StrategyConfig, StrategySignal
from src.strategies.registry import StrategyRegistry

# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------
SOV_03_CONFIG = StrategyConfig(
    strategy_id="SOV_03",
    strategy_name="Rating Migration Anticipation",
    asset_class=AssetClass.SOVEREIGN_CREDIT,
    instruments=["CDS_BR", "DI_PRE"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
    max_leverage=3.0,
    stop_loss_pct=0.20,
    take_profit_pct=0.15,
)

# ---------------------------------------------------------------------------
# Strategy parameters
# ---------------------------------------------------------------------------
_W_FISCAL = 0.35
_W_GROWTH = 0.25
_W_EXTERNAL = 0.20
_W_POLITICAL = 0.20
_FISCAL_THRESHOLD = 80.0
_FISCAL_SCALE = 10.0
_GROWTH_NEUTRAL = 2.0
_GROWTH_SCALE = 1.5
_P_DOWNGRADE_HIGH = 0.65
_P_DOWNGRADE_LOW = 0.35
_ENTRY_THRESHOLD = 1.0
_CDS_MOMENTUM_WINDOW = 63
_CDS_LOOKBACK = 756
_ZSCORE_WINDOW = 252
_HOLDING_PERIOD = 28


@StrategyRegistry.register(
    "SOV_03",
    asset_class=AssetClass.SOVEREIGN_CREDIT,
    instruments=["CDS_BR", "DI_PRE"],
)
class Sov03RatingMigrationStrategy(BaseStrategy):
    """Rating Migration Anticipation strategy.

    Uses a logistic model with four fundamental factors to estimate
    upgrade/downgrade probability for Brazil sovereign rating.

    Args:
        data_loader: PointInTimeDataLoader for fetching macro data.
        config: Optional StrategyConfig override.
    """

    def __init__(
        self,
        data_loader: PointInTimeDataLoader,
        config: StrategyConfig | None = None,
    ) -> None:
        super().__init__(config=config or SOV_03_CONFIG)
        self.data_loader = data_loader
        self.log = structlog.get_logger().bind(strategy=self.strategy_id)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def generate_signals(self, as_of_date: date) -> list[StrategySignal]:
        """Produce StrategySignal based on rating migration probability.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            List with a single StrategySignal, or empty list when data
            is missing or probability is in the neutral zone (0.35-0.65).
        """
        # --- Factor 1: Fiscal ---
        fiscal = self._compute_fiscal_factor(as_of_date)
        if fiscal is None:
            return []

        # --- Factor 2: Growth ---
        growth = self._compute_growth_factor(as_of_date)
        if growth is None:
            growth = 0.0  # Neutral fallback

        # --- Factor 3: External ---
        external = self._compute_external_factor(as_of_date)
        if external is None:
            external = 0.0  # Neutral fallback

        # --- Factor 4: Political/institutional ---
        political = self._compute_political_factor(as_of_date)
        if political is None:
            political = 0.0  # Neutral fallback

        # --- Logistic probability ---
        linear_combo = (
            _W_FISCAL * fiscal
            + _W_GROWTH * growth
            + _W_EXTERNAL * external
            + _W_POLITICAL * political
        )

        # Sigmoid
        p_downgrade = 1.0 / (1.0 + math.exp(-linear_combo))

        # Z-score: logit(p) - logit(0.5) normalized
        # logit(0.5) = 0, so z = logit(p) / normalization
        if p_downgrade <= 0.01:
            p_downgrade = 0.01
        if p_downgrade >= 0.99:
            p_downgrade = 0.99
        logit_p = math.log(p_downgrade / (1.0 - p_downgrade))
        # Normalize by typical std of linear_combo (~1.0)
        z_score = logit_p

        self.log.info(
            "sov03_rating_migration",
            fiscal=round(fiscal, 4),
            growth=round(growth, 4),
            external=round(external, 4),
            political=round(political, 4),
            p_downgrade=round(p_downgrade, 4),
            z_score=round(z_score, 4),
        )

        # Trade logic based on probability thresholds
        if p_downgrade > _P_DOWNGRADE_HIGH:
            # Anticipate downgrade => LONG CDS (buy protection)
            direction = SignalDirection.LONG
        elif p_downgrade < _P_DOWNGRADE_LOW:
            # Anticipate upgrade => SHORT CDS (sell protection)
            direction = SignalDirection.SHORT
        else:
            # Neutral zone => no signal
            return []

        # Entry threshold on z-score
        if abs(z_score) < _ENTRY_THRESHOLD:
            return []

        # CDS level for stop/take-profit
        cds_level = self.data_loader.get_latest_macro_value(
            "BR_CDS_5Y", as_of_date,
        )
        entry_level = cds_level if cds_level is not None else 200.0

        if direction == SignalDirection.LONG:
            stop_loss = entry_level * (1 - self.config.stop_loss_pct)
            take_profit = entry_level * (1 + self.config.take_profit_pct)
        else:
            stop_loss = entry_level * (1 + self.config.stop_loss_pct)
            take_profit = entry_level * (1 - self.config.take_profit_pct)

        strength = self.classify_strength(z_score)
        confidence = min(1.0, abs(z_score) / 3.0)
        suggested_size = self.size_from_conviction(z_score)

        signal = StrategySignal(
            strategy_id=self.strategy_id,
            timestamp=datetime.utcnow(),
            direction=direction,
            strength=strength,
            confidence=confidence,
            z_score=z_score,
            raw_value=p_downgrade,
            suggested_size=suggested_size,
            asset_class=AssetClass.SOVEREIGN_CREDIT,
            instruments=["CDS_BR", "DI_PRE"],
            entry_level=entry_level,
            stop_loss=stop_loss,
            take_profit=take_profit,
            holding_period_days=_HOLDING_PERIOD,
            metadata={
                "p_downgrade": p_downgrade,
                "p_upgrade": 1.0 - p_downgrade,
                "fiscal_factor": fiscal,
                "growth_factor": growth,
                "external_factor": external,
                "political_factor": political,
                "linear_combo": linear_combo,
            },
        )
        return [signal]

    # ------------------------------------------------------------------
    # Factor 1: Fiscal
    # ------------------------------------------------------------------
    def _compute_fiscal_factor(self, as_of_date: date) -> Optional[float]:
        """Compute fiscal factor: (debt - 80) / 10, clamped to [-2, 2].

        Higher debt = higher downgrade risk.
        """
        debt_pct = self.data_loader.get_latest_macro_value(
            "BR_GROSS_DEBT_PCT_GDP", as_of_date,
        )
        if debt_pct is None:
            debt_pct = self.data_loader.get_latest_macro_value(
                "BR_GROSS_DEBT_GDP", as_of_date,
            )
        if debt_pct is None:
            return None

        factor = (debt_pct - _FISCAL_THRESHOLD) / _FISCAL_SCALE
        return max(-2.0, min(2.0, factor))

    # ------------------------------------------------------------------
    # Factor 2: Growth
    # ------------------------------------------------------------------
    def _compute_growth_factor(self, as_of_date: date) -> Optional[float]:
        """Compute growth factor: -(gdp - 2.0) / 1.5.

        Negative because high growth is good for rating (reduces downgrade p).
        """
        gdp_growth = self.data_loader.get_latest_macro_value(
            "BR_GDP_GROWTH_YOY", as_of_date,
        )
        if gdp_growth is None:
            # Try IBC-Br proxy
            gdp_growth = self.data_loader.get_latest_macro_value(
                "BR_IBC_BR_YOY", as_of_date,
            )
        if gdp_growth is None:
            return None

        factor = -(gdp_growth - _GROWTH_NEUTRAL) / _GROWTH_SCALE
        return max(-2.0, min(2.0, factor))

    # ------------------------------------------------------------------
    # Factor 3: External
    # ------------------------------------------------------------------
    def _compute_external_factor(self, as_of_date: date) -> Optional[float]:
        """Compute external factor from trade balance.

        Surplus is positive for rating => invert sign.
        """
        trade_balance = self.data_loader.get_latest_macro_value(
            "BR_TRADE_BALANCE", as_of_date,
        )
        if trade_balance is None:
            trade_balance = self.data_loader.get_latest_macro_value(
                "BR_CURRENT_ACCOUNT", as_of_date,
            )
        if trade_balance is None:
            return None

        # Normalize: surplus (positive) is good => negative factor
        # Scale: typical trade balance ~5-10 USD bn
        factor = -trade_balance / 5.0
        return max(-2.0, min(2.0, factor))

    # ------------------------------------------------------------------
    # Factor 4: Political/institutional
    # ------------------------------------------------------------------
    def _compute_political_factor(self, as_of_date: date) -> Optional[float]:
        """Compute political factor from 63-day CDS momentum z-score.

        Rising CDS = market perceives increasing institutional risk.
        """
        cds_df = self.data_loader.get_macro_series(
            "BR_CDS_5Y", as_of_date, lookback_days=_CDS_LOOKBACK,
        )
        if cds_df.empty or len(cds_df) < _CDS_MOMENTUM_WINDOW + 20:
            return None

        values = cds_df["value"].tolist()
        # 63-day change
        current = values[-1]
        past = values[-min(len(values), _CDS_MOMENTUM_WINDOW + 1)]

        cds_change = current - past

        # Build history of 63-day changes
        changes = []
        for i in range(_CDS_MOMENTUM_WINDOW, len(values)):
            changes.append(values[i] - values[i - _CDS_MOMENTUM_WINDOW])

        if len(changes) < 20:
            return None

        return self.compute_z_score(cds_change, changes, window=_ZSCORE_WINDOW)

"""CROSS_02: Global Risk Appetite strategy.

Proprietary composite risk appetite index from market-based indicators only
(locked decision: no positioning/flow data):

Components (all market-based):
    - **VIX (25%)**: inverted z-score (high VIX = risk-off).
    - **Credit spreads (20%)**: BR CDS 5Y inverted z-score.
    - **FX implied vol (15%)**: USDBRL realized vol as proxy, inverted.
    - **Equity-bond correlation (15%)**: 63-day rolling corr of equity
      returns and DI rate changes. Positive = risk-on.
    - **Funding spreads (15%)**: DI short-end minus Selic, inverted.
    - **Equity momentum (10%)**: IBOVESPA 63-day return z-score.

Composite index typically in [-3, +3] range.

Trade recommendations:
    - risk_appetite > 1.0: Risk-on => LONG equities, SHORT USDBRL, LONG DI
    - risk_appetite < -1.0: Risk-off => SHORT equities, LONG USDBRL, SHORT DI
    - Between -1.0 and 1.0: NEUTRAL, no signal.

Entry threshold: |risk_appetite| >= 1.0.
Stop-loss: 3%.
Take-profit: 4%.
Holding period: 14 days.
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
CROSS_02_CONFIG = StrategyConfig(
    strategy_id="CROSS_02",
    strategy_name="Global Risk Appetite",
    asset_class=AssetClass.CROSS_ASSET,
    instruments=["DI_PRE", "USDBRL", "IBOV_FUT"],
    rebalance_frequency=Frequency.DAILY,
    max_position_size=1.0,
    max_leverage=3.0,
    stop_loss_pct=0.03,
    take_profit_pct=0.04,
)

# ---------------------------------------------------------------------------
# Component weights
# ---------------------------------------------------------------------------
_W_VIX = 0.25
_W_CREDIT = 0.20
_W_FX_VOL = 0.15
_W_EQ_BOND_CORR = 0.15
_W_FUNDING = 0.15
_W_EQ_MOMENTUM = 0.10

# Other parameters
_RISK_ON_THRESHOLD = 1.0
_RISK_OFF_THRESHOLD = -1.0
_ZSCORE_WINDOW = 252
_VOL_WINDOW = 21
_CORR_WINDOW = 63
_MOMENTUM_WINDOW = 63
_LOOKBACK_DAYS = 756
_HOLDING_PERIOD = 14

# Risk-on trade map: (instrument, direction)
_RISK_ON_TRADES = [
    ("IBOV_FUT", SignalDirection.LONG),
    ("USDBRL", SignalDirection.SHORT),
    ("DI_PRE", SignalDirection.LONG),    # receive rates
]

# Risk-off trade map: (instrument, direction)
_RISK_OFF_TRADES = [
    ("IBOV_FUT", SignalDirection.SHORT),
    ("USDBRL", SignalDirection.LONG),
    ("DI_PRE", SignalDirection.SHORT),   # pay rates
]


@StrategyRegistry.register(
    "CROSS_02",
    asset_class=AssetClass.CROSS_ASSET,
    instruments=["DI_PRE", "USDBRL", "IBOV_FUT"],
)
class Cross02RiskAppetiteStrategy(BaseStrategy):
    """Global Risk Appetite strategy.

    Builds a composite risk appetite index from market-only indicators
    and produces explicit trade recommendations.

    Args:
        data_loader: PointInTimeDataLoader for fetching macro / market data.
        config: Optional StrategyConfig override.
    """

    def __init__(
        self,
        data_loader: PointInTimeDataLoader,
        config: StrategyConfig | None = None,
    ) -> None:
        super().__init__(config=config or CROSS_02_CONFIG)
        self.data_loader = data_loader
        self.log = structlog.get_logger().bind(strategy=self.strategy_id)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def generate_signals(self, as_of_date: date) -> list[StrategySignal]:
        """Produce StrategySignals based on risk appetite composite.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            List of StrategySignals (one per instrument), or empty list
            when data is missing or risk appetite is in neutral zone.
        """
        components: dict[str, Optional[float]] = {}

        # --- Component a: VIX (25%) ---
        vix_z = self._compute_vix_z(as_of_date)
        components["vix_z"] = vix_z
        vix_component = -vix_z if vix_z is not None else None

        # --- Component b: Credit spreads (20%) ---
        cds_z = self._compute_cds_z(as_of_date)
        components["cds_z"] = cds_z
        credit_component = -cds_z if cds_z is not None else None

        # --- Component c: FX implied vol (15%) ---
        fx_vol_z = self._compute_fx_vol_z(as_of_date)
        components["fx_vol_z"] = fx_vol_z
        fx_vol_component = -fx_vol_z if fx_vol_z is not None else None

        # --- Component d: Equity-bond correlation (15%) ---
        eq_bond_corr_z = self._compute_eq_bond_corr_z(as_of_date)
        components["eq_bond_corr_z"] = eq_bond_corr_z
        corr_component = eq_bond_corr_z  # positive correlation = risk-on

        # --- Component e: Funding spreads (15%) ---
        funding_z = self._compute_funding_z(as_of_date)
        components["funding_z"] = funding_z
        funding_component = -funding_z if funding_z is not None else None

        # --- Component f: Equity momentum (10%) ---
        momentum_z = self._compute_momentum_z(as_of_date)
        components["momentum_z"] = momentum_z
        momentum_component = momentum_z  # positive = risk-on

        # --- Composite index ---
        weighted_parts: list[tuple[float, float]] = []
        if vix_component is not None:
            weighted_parts.append((_W_VIX, vix_component))
        if credit_component is not None:
            weighted_parts.append((_W_CREDIT, credit_component))
        if fx_vol_component is not None:
            weighted_parts.append((_W_FX_VOL, fx_vol_component))
        if corr_component is not None:
            weighted_parts.append((_W_EQ_BOND_CORR, corr_component))
        if funding_component is not None:
            weighted_parts.append((_W_FUNDING, funding_component))
        if momentum_component is not None:
            weighted_parts.append((_W_EQ_MOMENTUM, momentum_component))

        if not weighted_parts:
            self.log.warning("cross02_no_components", as_of_date=str(as_of_date))
            return []

        # Renormalize weights to sum to 1.0
        total_weight = sum(w for w, _ in weighted_parts)
        if total_weight <= 0:
            return []

        risk_appetite = sum(w * v / total_weight for w, v in weighted_parts)

        self.log.info(
            "cross02_risk_appetite",
            risk_appetite=round(risk_appetite, 4),
            n_components=len(weighted_parts),
            **{k: round(v, 4) if v is not None else None for k, v in components.items()},
        )

        # --- Trade decision ---
        if risk_appetite > _RISK_ON_THRESHOLD:
            trades = _RISK_ON_TRADES
        elif risk_appetite < _RISK_OFF_THRESHOLD:
            trades = _RISK_OFF_TRADES
        else:
            # Neutral zone
            return []

        # Generate signals
        signals: list[StrategySignal] = []
        for instrument, direction in trades:
            strength = self.classify_strength(risk_appetite)
            confidence = min(1.0, abs(risk_appetite) / 3.0)
            suggested_size = self.size_from_conviction(risk_appetite)

            signal = StrategySignal(
                strategy_id=self.strategy_id,
                timestamp=datetime.utcnow(),
                direction=direction,
                strength=strength,
                confidence=confidence,
                z_score=risk_appetite,
                raw_value=risk_appetite,
                suggested_size=suggested_size,
                asset_class=AssetClass.CROSS_ASSET,
                instruments=[instrument],
                entry_level=None,
                stop_loss=None,
                take_profit=None,
                holding_period_days=_HOLDING_PERIOD,
                metadata={
                    "risk_appetite": risk_appetite,
                    "instrument": instrument,
                    **{k: v for k, v in components.items()},
                },
            )
            signals.append(signal)

        return signals

    # ------------------------------------------------------------------
    # Component a: VIX z-score
    # ------------------------------------------------------------------
    def _compute_vix_z(self, as_of_date: date) -> Optional[float]:
        """VIX z-score vs 252-day history."""
        vix_df = self.data_loader.get_market_data(
            "^VIX", as_of_date, lookback_days=_LOOKBACK_DAYS,
        )
        if vix_df.empty or len(vix_df) < 60:
            return None

        values = vix_df["close"].tolist()
        current = values[-1]
        return self.compute_z_score(current, values, window=_ZSCORE_WINDOW)

    # ------------------------------------------------------------------
    # Component b: BR CDS z-score
    # ------------------------------------------------------------------
    def _compute_cds_z(self, as_of_date: date) -> Optional[float]:
        """BR CDS 5Y z-score vs 252-day history."""
        cds_df = self.data_loader.get_macro_series(
            "BR_CDS_5Y", as_of_date, lookback_days=_LOOKBACK_DAYS,
        )
        if cds_df.empty or len(cds_df) < 60:
            return None

        values = cds_df["value"].tolist()
        current = values[-1]
        return self.compute_z_score(current, values, window=_ZSCORE_WINDOW)

    # ------------------------------------------------------------------
    # Component c: USDBRL realized vol z-score
    # ------------------------------------------------------------------
    def _compute_fx_vol_z(self, as_of_date: date) -> Optional[float]:
        """21-day USDBRL realized vol z-scored vs history."""
        usdbrl_df = self.data_loader.get_market_data(
            "USDBRL", as_of_date, lookback_days=_LOOKBACK_DAYS,
        )
        if usdbrl_df.empty or len(usdbrl_df) < _VOL_WINDOW + 60:
            return None

        closes = usdbrl_df["close"]
        returns = closes.pct_change().dropna()

        if len(returns) < _VOL_WINDOW + 60:
            return None

        # Rolling 21-day realized vol
        rolling_vols = []
        returns_list = returns.tolist()
        for i in range(_VOL_WINDOW, len(returns_list)):
            window = returns_list[i - _VOL_WINDOW:i]
            mean_w = sum(window) / len(window)
            var_w = sum((x - mean_w) ** 2 for x in window) / len(window)
            rolling_vols.append(math.sqrt(var_w) * math.sqrt(252))

        if len(rolling_vols) < 20:
            return None

        current_vol = rolling_vols[-1]
        return self.compute_z_score(current_vol, rolling_vols, window=_ZSCORE_WINDOW)

    # ------------------------------------------------------------------
    # Component d: Equity-bond correlation z-score
    # ------------------------------------------------------------------
    def _compute_eq_bond_corr_z(self, as_of_date: date) -> Optional[float]:
        """63-day rolling correlation between equity returns and DI changes."""
        eq_df = self.data_loader.get_market_data(
            "IBOVESPA", as_of_date, lookback_days=_LOOKBACK_DAYS,
        )
        if eq_df.empty or len(eq_df) < _CORR_WINDOW + 60:
            return None

        # Get DI 1Y rate history
        di_df = self.data_loader.get_curve_history(
            "DI_PRE", 252, as_of_date, lookback_days=_LOOKBACK_DAYS,
        )
        if di_df.empty or len(di_df) < _CORR_WINDOW + 60:
            return None

        eq_returns = eq_df["close"].pct_change().dropna()
        di_changes = di_df["rate"].diff().dropna()

        # Align on common dates
        common = eq_returns.index.intersection(di_changes.index)
        if len(common) < _CORR_WINDOW + 20:
            return None

        eq_vals = eq_returns.loc[common].tolist()
        di_vals = di_changes.loc[common].tolist()

        # Rolling 63-day correlation
        correlations = []
        for i in range(_CORR_WINDOW, len(eq_vals)):
            eq_w = eq_vals[i - _CORR_WINDOW:i]
            di_w = di_vals[i - _CORR_WINDOW:i]

            # Pearson correlation
            n = len(eq_w)
            mean_eq = sum(eq_w) / n
            mean_di = sum(di_w) / n
            cov = sum((e - mean_eq) * (d - mean_di) for e, d in zip(eq_w, di_w)) / n
            std_eq = math.sqrt(sum((e - mean_eq) ** 2 for e in eq_w) / n)
            std_di = math.sqrt(sum((d - mean_di) ** 2 for d in di_w) / n)

            if std_eq > 0 and std_di > 0:
                correlations.append(cov / (std_eq * std_di))
            else:
                correlations.append(0.0)

        if len(correlations) < 20:
            return None

        current_corr = correlations[-1]
        return self.compute_z_score(current_corr, correlations, window=_ZSCORE_WINDOW)

    # ------------------------------------------------------------------
    # Component e: Funding spread z-score
    # ------------------------------------------------------------------
    def _compute_funding_z(self, as_of_date: date) -> Optional[float]:
        """DI short-end minus Selic z-score."""
        di_curve = self.data_loader.get_curve("DI_PRE", as_of_date)
        if not di_curve:
            return None

        # Get shortest tenor (1M or 63 days)
        short_tenors = sorted(di_curve.keys())
        if not short_tenors:
            return None
        short_di = di_curve[short_tenors[0]]

        selic = self.data_loader.get_latest_macro_value(
            "BR_SELIC_TARGET", as_of_date,
        )
        if selic is None:
            return None

        current_spread = short_di - selic

        # Build history (using DI short rate history as proxy)
        di_history = self.data_loader.get_curve_history(
            "DI_PRE", short_tenors[0], as_of_date, lookback_days=_LOOKBACK_DAYS,
        )
        if di_history.empty or len(di_history) < 60:
            return None

        # Use DI rate history - selic as spread history proxy
        spread_history = [float(r) - selic for r in di_history["rate"].tolist()]
        return self.compute_z_score(current_spread, spread_history, window=_ZSCORE_WINDOW)

    # ------------------------------------------------------------------
    # Component f: Equity momentum z-score
    # ------------------------------------------------------------------
    def _compute_momentum_z(self, as_of_date: date) -> Optional[float]:
        """IBOVESPA 63-day return z-scored vs history."""
        eq_df = self.data_loader.get_market_data(
            "IBOVESPA", as_of_date, lookback_days=_LOOKBACK_DAYS,
        )
        if eq_df.empty or len(eq_df) < _MOMENTUM_WINDOW + 60:
            return None

        closes = eq_df["close"].tolist()

        # Rolling 63-day returns
        returns_63d = []
        for i in range(_MOMENTUM_WINDOW, len(closes)):
            if closes[i - _MOMENTUM_WINDOW] > 0:
                ret = (closes[i] / closes[i - _MOMENTUM_WINDOW]) - 1.0
                returns_63d.append(ret)

        if len(returns_63d) < 20:
            return None

        current_return = returns_63d[-1]
        return self.compute_z_score(current_return, returns_63d, window=_ZSCORE_WINDOW)

"""Strategy framework core -- BaseStrategy ABC, StrategyConfig, StrategyPosition, StrategySignal.

BaseStrategy mirrors the BaseAgent ABC pattern: subclasses implement
``generate_signals(as_of_date)`` to produce a list of target positions.

The ``signals_to_positions`` method converts agent-level signals
(AgentSignal) into StrategyPosition objects using the locked weight formula:

    raw_weight = STRENGTH_MAP[strength] * confidence * max_position_size

Direction and NEUTRAL scale-down rules are applied, followed by clamping
and leverage enforcement.

v3.0 additions:
- StrategySignal: Rich signal dataclass with z_score, entry/stop/take-profit levels
- BaseStrategy utility methods: compute_z_score, size_from_conviction, classify_strength
"""

import abc
import copy
import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

import structlog

from src.agents.base import AgentSignal
from src.core.enums import AssetClass, Frequency, SignalDirection, SignalStrength

# ---------------------------------------------------------------------------
# Strength -> weight multiplier mapping (locked decision)
# ---------------------------------------------------------------------------
STRENGTH_MAP: dict[SignalStrength, float] = {
    SignalStrength.STRONG: 1.0,
    SignalStrength.MODERATE: 0.6,
    SignalStrength.WEAK: 0.3,
    SignalStrength.NO_SIGNAL: 0.0,
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class StrategyConfig:
    """Immutable configuration for a trading strategy.

    Attributes:
        strategy_id: Unique identifier, e.g. ``"RATES_BR_01"``.
        strategy_name: Human-readable name.
        asset_class: Target asset class from ``AssetClass`` enum.
        instruments: List of tradeable instrument IDs (e.g. ``["DI_PRE"]``).
        rebalance_frequency: How often the strategy rebalances.
        max_position_size: Maximum absolute weight per position.
        max_leverage: Maximum sum of absolute weights across all positions.
        stop_loss_pct: Stop loss in percentage (e.g. 0.05 = 5%).
        take_profit_pct: Take profit in percentage (e.g. 0.10 = 10%).
    """

    strategy_id: str
    strategy_name: str
    asset_class: AssetClass
    instruments: list[str]
    rebalance_frequency: Frequency
    max_position_size: float
    max_leverage: float = 3.0
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.10


@dataclass
class StrategyPosition:
    """Target position produced by a strategy.

    Attributes:
        strategy_id: Source strategy identifier.
        instrument: Instrument identifier (e.g. ``"DI_PRE_365"``).
        weight: Position weight in ``[-1, 1]`` (negative = short).
        confidence: Signal confidence in ``[0, 1]``.
        direction: LONG, SHORT, or NEUTRAL.
        entry_signal: Signal ID that triggered this position.
        metadata: Strategy-specific details.
    """

    strategy_id: str
    instrument: str
    weight: float
    confidence: float
    direction: SignalDirection
    entry_signal: str
    metadata: dict = field(default_factory=dict)


@dataclass
class StrategySignal:
    """Rich signal dataclass for v3.0 strategy framework (SFWK-01).

    Contains quantitative fields needed for rigorous backtesting:
    z_score, entry/stop/take-profit levels, and suggested position sizing.

    Attributes:
        strategy_id: Source strategy identifier.
        timestamp: Signal generation time.
        direction: LONG, SHORT, or NEUTRAL.
        strength: Signal strength bucket.
        confidence: Signal confidence in [0, 1].
        z_score: Z-score of the signal vs history.
        raw_value: Raw model output before transformation.
        suggested_size: Suggested position size in [0, 1] risk units.
        asset_class: Target asset class.
        instruments: List of tradeable instrument tickers.
        entry_level: Optional entry price level.
        stop_loss: Optional stop loss price level.
        take_profit: Optional take profit price level.
        holding_period_days: Optional expected holding period in days.
        metadata: Strategy-specific additional data.
    """

    strategy_id: str
    timestamp: datetime
    direction: SignalDirection
    strength: SignalStrength
    confidence: float
    z_score: float
    raw_value: float
    suggested_size: float
    asset_class: AssetClass
    instruments: list[str]
    entry_level: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    holding_period_days: Optional[int] = None
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# BaseStrategy ABC
# ---------------------------------------------------------------------------
class BaseStrategy(abc.ABC):
    """Abstract base class for all trading strategies.

    Subclasses implement ``generate_signals(as_of_date)`` to produce target
    positions.  The concrete ``signals_to_positions`` and ``validate_position``
    methods enforce weight formulas and constraint limits.

    Follows the BaseAgent pattern with structlog-based logging.
    """

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config
        self.log = structlog.get_logger().bind(strategy=config.strategy_id)

    @property
    def strategy_id(self) -> str:
        """Return the strategy's unique identifier."""
        return self.config.strategy_id

    # ------------------------------------------------------------------
    # Abstract interface (subclasses MUST implement)
    # ------------------------------------------------------------------
    @abc.abstractmethod
    def generate_signals(self, as_of_date: date) -> list[StrategyPosition]:
        """Produce target positions for the given date.

        Timing convention: signals generated for date D use data available
        at D's bar close and are executed at next open (D+1).  The
        backtesting engine enforces this via the PIT data loader; strategies
        only need to use ``as_of_date`` consistently.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            List of StrategyPosition objects.
        """
        ...

    # ------------------------------------------------------------------
    # Concrete methods
    # ------------------------------------------------------------------
    def signals_to_positions(
        self,
        agent_signals: list[AgentSignal],
        existing_weights: dict[str, float] | None = None,
    ) -> list[StrategyPosition]:
        """Convert agent signals to strategy positions using locked weight formula.

        Weight formula (locked decision):
            raw_weight = STRENGTH_MAP[strength] * confidence * max_position_size

        NEUTRAL handling:
            - If existing position exists: weight = existing_weight * 0.5
            - If no existing position: weight = 0.0

        After computing raw weights, positions are clamped to
        ``[-max_position_size, max_position_size]`` and leverage is enforced
        by scaling all weights proportionally if total absolute weight exceeds
        ``max_leverage``.

        Args:
            agent_signals: List of AgentSignal objects from agents.
            existing_weights: Optional dict of instrument -> current weight
                for NEUTRAL scale-down handling.

        Returns:
            List of validated StrategyPosition objects.
        """
        if existing_weights is None:
            existing_weights = {}

        positions: list[StrategyPosition] = []

        for signal in agent_signals:
            instrument = signal.signal_id
            strength_base = STRENGTH_MAP.get(signal.strength, 0.0)

            if signal.direction == SignalDirection.NEUTRAL:
                if instrument in existing_weights:
                    raw_weight = existing_weights[instrument] * 0.5
                else:
                    raw_weight = 0.0
            else:
                raw_weight = strength_base * signal.confidence * self.config.max_position_size
                if signal.direction == SignalDirection.SHORT:
                    raw_weight = -raw_weight

            # Clamp to max_position_size
            clamped_weight = max(
                -self.config.max_position_size,
                min(self.config.max_position_size, raw_weight),
            )

            pos = StrategyPosition(
                strategy_id=self.config.strategy_id,
                instrument=instrument,
                weight=clamped_weight,
                confidence=max(0.0, min(1.0, signal.confidence)),
                direction=signal.direction,
                entry_signal=signal.signal_id,
                metadata={
                    "agent_id": signal.agent_id,
                    "strength": signal.strength.value,
                    "raw_weight": raw_weight,
                },
            )
            positions.append(pos)

        # Enforce max_leverage
        total_abs = sum(abs(p.weight) for p in positions)
        if total_abs > self.config.max_leverage and total_abs > 0:
            scale_factor = self.config.max_leverage / total_abs
            for pos in positions:
                pos.weight = pos.weight * scale_factor

        return positions

    def validate_position(self, position: StrategyPosition) -> StrategyPosition:
        """Enforce weight in [-1, 1] and confidence in [0, 1].

        Returns a new StrategyPosition with clamped values (does not modify
        the original).

        Args:
            position: Position to validate.

        Returns:
            New StrategyPosition with clamped weight and confidence.
        """
        validated = copy.copy(position)
        validated.weight = max(-1.0, min(1.0, position.weight))
        validated.confidence = max(0.0, min(1.0, position.confidence))
        return validated

    # ------------------------------------------------------------------
    # v3.0 utility methods (concrete -- not abstract)
    # ------------------------------------------------------------------
    def compute_z_score(
        self, value: float, history: list[float], window: int = 252
    ) -> float:
        """Compute rolling z-score of *value* against *history*.

        Uses the last *window* values of history.  Returns 0.0 if history
        has fewer than 2 elements or if standard deviation is zero.

        Args:
            value: Current observation.
            history: Historical observations (most recent last).
            window: Lookback window size.

        Returns:
            Z-score as float, or 0.0 for degenerate cases.
        """
        if len(history) < 2:
            return 0.0
        window_data = history[-window:]
        mean = sum(window_data) / len(window_data)
        variance = sum((x - mean) ** 2 for x in window_data) / len(window_data)
        std = math.sqrt(variance)
        if std == 0.0:
            return 0.0
        return (value - mean) / std

    def size_from_conviction(
        self, z_score: float, max_size: float = 1.0
    ) -> float:
        """Map z-score to position size using sigmoid truncation.

        Uses ``min(max_size, max_size * (2 / (1 + exp(-|z|)) - 1))``.
        Returns 0 for z=0, approaches *max_size* for large |z|.

        Args:
            z_score: Signal z-score (sign is ignored).
            max_size: Maximum position size.

        Returns:
            Position size in [0, max_size].
        """
        return min(
            max_size,
            max_size * (2.0 / (1.0 + math.exp(-abs(z_score))) - 1.0),
        )

    def classify_strength(self, z_score: float) -> SignalStrength:
        """Classify signal strength from z-score magnitude.

        Thresholds:
        - |z| >= 2.0 -> STRONG
        - |z| >= 1.0 -> MODERATE
        - |z| >= 0.5 -> WEAK
        - |z| < 0.5  -> NO_SIGNAL

        Args:
            z_score: Signal z-score.

        Returns:
            SignalStrength enum value.
        """
        az = abs(z_score)
        if az >= 2.0:
            return SignalStrength.STRONG
        if az >= 1.0:
            return SignalStrength.MODERATE
        if az >= 0.5:
            return SignalStrength.WEAK
        return SignalStrength.NO_SIGNAL

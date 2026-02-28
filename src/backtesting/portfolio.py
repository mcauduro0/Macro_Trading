"""Portfolio state tracking for the backtesting engine.

Positions are stored as notional values (not shares) to simplify
rebalancing -- no price lookup required during position access.
Portfolio never accesses the database directly; BacktestEngine passes
prices from PointInTimeDataLoader.
"""

from __future__ import annotations

from datetime import date
from typing import Any


class Portfolio:
    """Mutable in-memory portfolio state.

    Attributes:
        cash: Available cash (USD/BRL equivalent).
        positions: {ticker: current_notional_value}. Notional, not shares.
        equity_curve: [(date, total_equity)] appended each rebalance period.
        trade_log: [{date, ticker, direction, trade_notional, cost, entry_price, pnl}]
        _entry_prices: {ticker: avg_entry_price} for PnL computation.
        _last_prices: {ticker: last_known_price} for mark-to-market.
    """

    def __init__(self, initial_capital: float) -> None:
        self.cash: float = initial_capital
        self.positions: dict[str, float] = {}  # ticker -> notional value
        self.equity_curve: list[tuple[date, float]] = []
        self.trade_log: list[dict[str, Any]] = []
        self._entry_prices: dict[str, float] = {}  # ticker -> price at entry
        self._last_prices: dict[str, float] = {}  # ticker -> last known price

    @property
    def total_equity(self) -> float:
        """Cash plus sum of all position notional values."""
        return self.cash + sum(self.positions.values())

    def mark_to_market(self, prices: dict[str, float]) -> None:
        """Update position notional values based on new prices.

        For notional-based positions, mark-to-market adjusts the notional
        by the price return since last known price.

        Args:
            prices: {ticker: current_price}. Tickers missing from prices
                are unchanged (uses last known value -- handles gaps).
        """
        for ticker, current_price in prices.items():
            if current_price <= 0:
                continue
            self._last_prices[ticker] = current_price
            if ticker in self.positions and self.positions[ticker] != 0:
                last_price = self._entry_prices.get(ticker, current_price)
                if last_price > 0:
                    price_return = current_price / last_price
                    self.positions[ticker] = self.positions[ticker] * price_return
                    self._entry_prices[ticker] = current_price

    def rebalance(
        self,
        target_weights: dict[str, float],
        prices: dict[str, float],
        config: Any,  # BacktestConfig (forward ref)
    ) -> None:
        """Apply target weights, compute trades, deduct transaction costs.

        Position limit enforcement: total absolute weight capped at
        config.max_leverage before computing trades.

        Steps:
        1. Enforce max_leverage: scale weights if sum(abs(w)) > max_leverage
        2. For each ticker in target_weights, compute target notional
        3. Compute trade_notional = target_notional - current_notional
        4. cost = abs(trade_notional) * (tc_bps + slip_bps) / 10_000
        5. Deduct cost from cash
        6. Set positions[ticker] = target_notional (skip if price unknown)
        7. Log trade to trade_log with estimated PnL for closed/reduced positions

        Args:
            target_weights: {ticker: weight} where weight in [-1, max_leverage].
            prices: {ticker: current_price}. Tickers without prices are skipped.
            config: BacktestConfig instance with cost parameters.
        """
        total_equity = self.total_equity
        if total_equity <= 0:
            return

        # Step 1: Enforce max_leverage
        total_abs_weight = sum(abs(w) for w in target_weights.values())
        if total_abs_weight > config.max_leverage and total_abs_weight > 0:
            scale = config.max_leverage / total_abs_weight
            target_weights = {k: v * scale for k, v in target_weights.items()}

        # Step 2-7: Apply rebalance per ticker
        # Note: BacktestEngine sets portfolio._rebalance_date before calling rebalance()
        rebalance_date = getattr(self, "_rebalance_date", date.today())

        for ticker, weight in target_weights.items():
            if ticker not in prices or prices[ticker] <= 0:
                continue

            target_notional = total_equity * weight
            current_notional = self.positions.get(ticker, 0.0)
            trade_notional = target_notional - current_notional

            if abs(trade_notional) < 1.0:  # skip trivial trades
                continue

            # Transaction cost + slippage
            cost = (
                abs(trade_notional)
                * (config.transaction_cost_bps + config.slippage_bps)
                / 10_000
            )
            # Move capital from cash to position (or vice versa) + deduct cost
            self.cash -= trade_notional + cost

            # PnL for reduced/closed positions (round-trip tracking)
            pnl = 0.0
            if current_notional != 0 and abs(trade_notional) > 0:
                entry_price = self._entry_prices.get(ticker, prices[ticker])
                current_price = prices[ticker]
                if entry_price > 0:
                    pnl = (current_price / entry_price - 1) * abs(current_notional)
                    # Only count PnL for the portion being closed
                    if abs(trade_notional) < abs(current_notional):
                        fraction = abs(trade_notional) / abs(current_notional)
                        pnl *= fraction

            # Log trade
            direction = "BUY" if trade_notional > 0 else "SELL"
            self.trade_log.append(
                {
                    "date": rebalance_date,
                    "ticker": ticker,
                    "direction": direction,
                    "trade_notional": round(trade_notional, 2),
                    "cost": round(cost, 2),
                    "price": prices[ticker],
                    "pnl": round(pnl, 2),
                }
            )

            # Update position and entry price
            self.positions[ticker] = target_notional
            if trade_notional != 0:
                self._entry_prices[ticker] = prices[ticker]

        # Zero out tickers in positions but not in target_weights (full exit)
        for ticker in list(self.positions.keys()):
            if ticker not in target_weights:
                current_notional = self.positions[ticker]
                if abs(current_notional) > 1.0:
                    cost = (
                        abs(current_notional)
                        * (config.transaction_cost_bps + config.slippage_bps)
                        / 10_000
                    )
                    # Return position notional to cash, deduct exit cost
                    self.cash += current_notional - cost
                    entry_price = self._entry_prices.get(
                        ticker, prices.get(ticker, 1.0)
                    )
                    current_price = prices.get(ticker, entry_price)
                    pnl = (
                        (current_price / entry_price - 1) * abs(current_notional)
                        if entry_price > 0
                        else 0.0
                    )
                    self.trade_log.append(
                        {
                            "date": rebalance_date,
                            "ticker": ticker,
                            "direction": "EXIT",
                            "trade_notional": round(-current_notional, 2),
                            "cost": round(cost, 2),
                            "price": current_price,
                            "pnl": round(pnl, 2),
                        }
                    )
                self.positions[ticker] = 0.0
                self._entry_prices.pop(ticker, None)

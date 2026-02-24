"""Mark-to-Market service for PMS position pricing.

Handles instrument-aware price sourcing from DB with manual override support,
staleness detection, and risk metric computation (DV01, delta, VaR contribution).

Actual DB price lookup will be wired in Phase 21/27 when the MTM pipeline runs
against live TimescaleDB. For now, uses entry_price or override as price source.
"""

from __future__ import annotations

from datetime import date

import structlog

import importlib.util
import os

# Import costs module directly to avoid heavy backtesting.__init__ import chain
# (which pulls in agents, database, asyncpg, etc.)
_costs_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backtesting",
    "costs.py",
)
_spec = importlib.util.spec_from_file_location("src.backtesting.costs", _costs_path)
_costs_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_costs_mod)
TransactionCostModel = _costs_mod.TransactionCostModel
from .pricing import (
    compute_dv01_from_pu,
    compute_fx_delta,
    compute_pnl_brl,
    compute_pnl_usd,
    rate_to_pu,
)

logger = structlog.get_logger(__name__)


class MarkToMarketService:
    """Service for mark-to-market pricing of portfolio positions.

    Handles instrument-aware price sourcing from DB with manual override support,
    staleness detection, and risk metric computation (DV01, delta, VaR contribution).
    """

    STALE_THRESHOLD_DAYS = 3  # Alert if price older than this

    def __init__(self, cost_model: TransactionCostModel | None = None) -> None:
        self.cost_model = cost_model or TransactionCostModel()

    def get_prices_for_positions(
        self,
        positions: list[dict],
        price_overrides: dict[str, float] | None = None,
        as_of_date: date | None = None,
    ) -> dict[str, dict]:
        """Get current prices for a list of positions.

        Returns dict keyed by instrument with:
        {price: float, source: str, date: date, is_stale: bool, staleness_days: int}

        Price resolution order:
        1. Manual override (if provided in price_overrides)
        2. DB lookup (placeholder -- returns entry_price as fallback in v4.0-P20)
        3. Carry-forward last known price with staleness alert

        Note: Actual DB price lookup will be wired in Phase 21/27 when MTM
        pipeline runs against live TimescaleDB. For now, uses entry_price
        or override as price source.

        Args:
            positions: List of position dicts, each with 'instrument' and 'entry_price'.
            price_overrides: Optional dict of {instrument: price} for manual overrides.
            as_of_date: Reference date for staleness calculation.

        Returns:
            Dict keyed by instrument with price info.
        """
        overrides = price_overrides or {}
        ref_date = as_of_date or date.today()
        result: dict[str, dict] = {}

        for pos in positions:
            instrument = pos.get("instrument", "UNKNOWN")
            entry_price = pos.get("entry_price", 0.0)

            if instrument in overrides:
                result[instrument] = {
                    "price": overrides[instrument],
                    "source": "manual_override",
                    "date": ref_date,
                    "is_stale": False,
                    "staleness_days": 0,
                }
                logger.debug(
                    "price_override_applied",
                    instrument=instrument,
                    price=overrides[instrument],
                )
            elif instrument in result:
                # Already resolved this instrument from a previous position
                continue
            else:
                # Placeholder: use entry_price as fallback until DB wiring
                # In production, this would query TimescaleDB for latest price
                entry_date = pos.get("entry_date", ref_date)
                if isinstance(entry_date, str):
                    entry_date = date.fromisoformat(entry_date)
                staleness = (ref_date - entry_date).days if isinstance(entry_date, date) else 0
                is_stale = staleness > self.STALE_THRESHOLD_DAYS

                if is_stale:
                    logger.warning(
                        "stale_price_detected",
                        instrument=instrument,
                        staleness_days=staleness,
                        threshold=self.STALE_THRESHOLD_DAYS,
                    )

                result[instrument] = {
                    "price": entry_price,
                    "source": "entry_price_fallback",
                    "date": entry_date if isinstance(entry_date, date) else ref_date,
                    "is_stale": is_stale,
                    "staleness_days": max(staleness, 0),
                }

        return result

    def compute_position_mtm(
        self,
        position: dict,
        current_price: float,
        current_fx_rate: float | None = None,
    ) -> dict:
        """Compute MTM for a single position.

        Args:
            position: Position dict with entry_price, notional_brl, direction,
                instrument, asset_class fields.
            current_price: Current mark price.
            current_fx_rate: Current USDBRL rate for USD conversion.

        Returns:
            Dict with unrealized_pnl_brl, unrealized_pnl_usd, daily_pnl_brl,
            daily_pnl_usd, current_dv01, current_delta, mark_price, fx_rate.
        """
        entry_price = position.get("entry_price", 0.0)
        notional_brl = position.get("notional_brl", 0.0)
        direction = position.get("direction", "LONG")
        instrument = position.get("instrument", "UNKNOWN")
        asset_class = position.get("asset_class", "GENERAL")
        fx_rate = current_fx_rate or position.get("entry_fx_rate") or 5.0

        # Compute unrealized P&L
        unrealized_pnl_brl = compute_pnl_brl(
            entry_price, current_price, notional_brl, direction, instrument, asset_class
        )
        unrealized_pnl_usd = compute_pnl_usd(unrealized_pnl_brl, fx_rate)

        # Daily P&L: difference between current unrealized and previous mark
        previous_unrealized = position.get("unrealized_pnl_brl", 0.0) or 0.0
        daily_pnl_brl = unrealized_pnl_brl - previous_unrealized
        daily_pnl_usd = compute_pnl_usd(daily_pnl_brl, fx_rate)

        # Risk metrics
        current_dv01 = 0.0
        current_delta = 0.0

        if asset_class.upper() == "RATES":
            rate_pct = position.get("rate_pct", 0.0)
            business_days = position.get("business_days", 252)
            if rate_pct and business_days:
                pu = rate_to_pu(rate_pct, business_days)
                current_dv01 = compute_dv01_from_pu(pu, rate_pct, business_days, notional_brl)
        elif asset_class.upper() == "FX":
            current_delta = compute_fx_delta(notional_brl, fx_rate)

        return {
            "unrealized_pnl_brl": unrealized_pnl_brl,
            "unrealized_pnl_usd": unrealized_pnl_usd,
            "daily_pnl_brl": daily_pnl_brl,
            "daily_pnl_usd": daily_pnl_usd,
            "current_dv01": current_dv01,
            "current_delta": current_delta,
            "mark_price": current_price,
            "fx_rate": fx_rate,
        }

    def compute_dv01(
        self,
        instrument: str,
        rate_pct: float,
        business_days: int,
        notional_brl: float,
    ) -> float:
        """Compute DV01 for a rates instrument.

        Delegates to pricing.compute_dv01_from_pu.

        Args:
            instrument: Instrument ticker (for logging).
            rate_pct: Annual rate in percent.
            business_days: Business days to maturity.
            notional_brl: Position notional in BRL.

        Returns:
            DV01 in BRL.
        """
        pu = rate_to_pu(rate_pct, business_days)
        dv01 = compute_dv01_from_pu(pu, rate_pct, business_days, notional_brl)
        logger.debug("dv01_computed", instrument=instrument, dv01=dv01, rate_pct=rate_pct)
        return dv01

    def compute_var_contributions(
        self,
        positions: list[dict],
        total_var: float | None = None,
    ) -> dict[str, float]:
        """Compute per-position VaR contribution.

        If total_var not provided, uses a simplified proportional allocation
        based on position notional weights. Full Component VaR from Phase 17
        risk engine will be integrated in Phase 22.

        Args:
            positions: List of position dicts with 'id' and 'notional_brl'.
            total_var: Optional total portfolio VaR (if available from risk engine).

        Returns:
            Dict of {position_id: var_contribution}.
        """
        if not positions:
            return {}

        total_notional = sum(abs(p.get("notional_brl", 0.0)) for p in positions)
        if total_notional == 0:
            return {str(p.get("id", i)): 0.0 for i, p in enumerate(positions)}

        # Use provided total_var or estimate as 2% of total notional (simplified)
        effective_var = total_var if total_var is not None else total_notional * 0.02

        contributions: dict[str, float] = {}
        for pos in positions:
            pos_id = str(pos.get("id", ""))
            weight = abs(pos.get("notional_brl", 0.0)) / total_notional
            contributions[pos_id] = weight * effective_var

        logger.debug(
            "var_contributions_computed",
            n_positions=len(positions),
            total_var=effective_var,
        )

        return contributions

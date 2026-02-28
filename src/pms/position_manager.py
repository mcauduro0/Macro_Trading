"""Core position management service for the Portfolio Management System.

Manages position lifecycle: open, close, mark-to-market, and book reporting.
All position changes are journaled automatically in the DecisionJournal.

This class operates on dicts representing positions (not ORM objects directly)
to decouple from SQLAlchemy sessions. The caller (API layer or Dagster pipeline)
is responsible for session management and persistence.
"""

from __future__ import annotations

import hashlib

# Import TransactionCostModel directly to avoid heavy backtesting.__init__ chain
import importlib.util
import json
import os
from datetime import date, datetime
from typing import Any

import structlog

from .mtm_service import MarkToMarketService
from .pricing import (
    compute_dv01_from_pu,
    compute_fx_delta,
    compute_pnl_brl,
    compute_pnl_usd,
    rate_to_pu,
)

_costs_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backtesting",
    "costs.py",
)
_spec = importlib.util.spec_from_file_location("_backtesting_costs", _costs_path)
_costs_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_costs_mod)
TransactionCostModel = _costs_mod.TransactionCostModel

logger = structlog.get_logger(__name__)


class PositionManager:
    """Core position management service for the Portfolio Management System.

    Manages position lifecycle: open, close, mark-to-market, and book reporting.
    All position changes are journaled automatically in the DecisionJournal.

    This class operates on dicts representing positions (not ORM objects directly)
    to decouple from SQLAlchemy sessions. The caller (API layer or Dagster pipeline)
    is responsible for session management and persistence.
    """

    def __init__(
        self,
        mtm_service: MarkToMarketService | None = None,
        cost_model: TransactionCostModel | None = None,
        aum: float = 100_000_000.0,  # Default 100M BRL AUM
    ) -> None:
        self.mtm_service = mtm_service or MarkToMarketService()
        self.cost_model = cost_model or TransactionCostModel()
        self.aum = aum
        self._positions: list[dict] = (
            []
        )  # In-memory position store (DB wiring in Phase 21)
        self._journal: list[dict] = []  # In-memory journal store
        self._pnl_history: list[dict] = []  # In-memory P&L snapshots

    # -------------------------------------------------------------------------
    # Open position
    # -------------------------------------------------------------------------

    def open_position(
        self,
        instrument: str,
        asset_class: str,
        direction: str,
        notional_brl: float,
        entry_price: float,
        entry_date: date | datetime | None = None,
        quantity: float | None = None,
        entry_fx_rate: float | None = None,
        strategy_ids: list[str] | None = None,
        strategy_weights: dict[str, float] | None = None,
        notes: str | None = None,
        rate_pct: float | None = None,
        business_days: int | None = None,
        **kwargs: Any,
    ) -> dict:
        """Open a new position with risk metrics and journal entry.

        Args:
            instrument: Instrument ticker (e.g. "DI1_F26", "USDBRL").
            asset_class: Asset class ("RATES", "FX", "CREDIT", "EQUITY", "SOVEREIGN").
            direction: "LONG" or "SHORT".
            notional_brl: Position notional in BRL.
            entry_price: Entry price (PU for rates, spot for FX/equity).
            entry_date: Entry date (defaults to today).
            quantity: Optional quantity (contracts, lots).
            entry_fx_rate: USDBRL rate at entry for dual-currency tracking.
            strategy_ids: List of strategy IDs generating this position.
            strategy_weights: Dict of {strategy_id: weight} for attribution.
            notes: Manager notes.
            rate_pct: Annual rate in % (for RATES instruments, used for DV01).
            business_days: Business days to maturity (for RATES instruments).
            **kwargs: Additional fields (entry_convexity, entry_var_contribution,
                entry_spread_duration, market_snapshot, portfolio_snapshot).

        Returns:
            Complete position dict with all fields populated.
        """
        now = datetime.utcnow()
        today = date.today()
        pos_id = len(self._positions) + 1
        effective_date = entry_date or today

        # Compute USD notional if FX rate provided
        notional_usd = (
            notional_brl / entry_fx_rate
            if entry_fx_rate and entry_fx_rate > 0
            else None
        )

        # Risk metrics at entry
        entry_dv01 = 0.0
        entry_delta = 0.0

        if (
            asset_class.upper() == "RATES"
            and rate_pct is not None
            and business_days is not None
        ):
            pu = rate_to_pu(rate_pct, business_days)
            entry_dv01 = compute_dv01_from_pu(pu, rate_pct, business_days, notional_brl)

        if asset_class.upper() == "FX" and entry_fx_rate and entry_fx_rate > 0:
            entry_delta = compute_fx_delta(notional_brl, entry_fx_rate)

        # Transaction cost
        transaction_cost_brl = self.cost_model.get_cost(instrument, notional_brl)

        position = {
            "id": pos_id,
            "created_at": now,
            "updated_at": now,
            "instrument": instrument,
            "asset_class": asset_class.upper(),
            "direction": direction.upper(),
            "quantity": quantity,
            "notional_brl": notional_brl,
            "notional_usd": notional_usd,
            "entry_price": entry_price,
            "entry_date": effective_date if isinstance(effective_date, date) else today,
            "entry_fx_rate": entry_fx_rate,
            "current_price": entry_price,
            "unrealized_pnl_brl": 0.0,
            "unrealized_pnl_usd": 0.0,
            "realized_pnl_brl": 0.0,
            "realized_pnl_usd": 0.0,
            "transaction_cost_brl": transaction_cost_brl,
            "is_open": True,
            "closed_at": None,
            "close_price": None,
            # Risk snapshot
            "entry_dv01": entry_dv01 if entry_dv01 else None,
            "entry_delta": entry_delta if entry_delta else None,
            "entry_convexity": kwargs.get("entry_convexity"),
            "entry_var_contribution": kwargs.get("entry_var_contribution"),
            "entry_spread_duration": kwargs.get("entry_spread_duration"),
            # Strategy linkage
            "strategy_ids": strategy_ids,
            "strategy_weights": strategy_weights,
            "notes": notes,
            # Extra metadata for MTM recomputation
            "rate_pct": rate_pct,
            "business_days": business_days,
        }

        self._positions.append(position)

        # Create journal entry
        journal_content = {
            "entry_type": "OPEN",
            "instrument": instrument,
            "direction": direction.upper(),
            "notional_brl": notional_brl,
            "entry_price": entry_price,
            "manager_notes": notes,
            "system_notes": (
                f"Position #{pos_id} opened. DV01={entry_dv01:.2f},"
                f" delta={entry_delta:.2f}, cost={transaction_cost_brl:.2f}"
            ),
        }
        content_hash = self._compute_content_hash(**journal_content)

        journal_entry = {
            "id": len(self._journal) + 1,
            "created_at": now,
            "entry_type": "OPEN",
            "position_id": pos_id,
            "proposal_id": None,
            "instrument": instrument,
            "direction": direction.upper(),
            "notional_brl": notional_brl,
            "entry_price": entry_price,
            "manager_notes": notes,
            "system_notes": journal_content["system_notes"],
            "market_snapshot": kwargs.get("market_snapshot", {}),
            "portfolio_snapshot": kwargs.get("portfolio_snapshot", {}),
            "content_hash": content_hash,
            "is_locked": True,
        }

        self._journal.append(journal_entry)

        logger.info(
            "position_opened",
            position_id=pos_id,
            instrument=instrument,
            direction=direction,
            notional_brl=notional_brl,
            entry_dv01=entry_dv01,
        )

        return position

    # -------------------------------------------------------------------------
    # Close position
    # -------------------------------------------------------------------------

    def close_position(
        self,
        position_id: int,
        close_price: float,
        close_date: datetime | None = None,
        current_fx_rate: float | None = None,
        notes: str | None = None,
    ) -> dict:
        """Close an open position with realized P&L computation.

        Args:
            position_id: ID of the position to close.
            close_price: Closing price.
            close_date: Close date/time (defaults to now).
            current_fx_rate: Current USDBRL rate for USD P&L conversion.
            notes: Manager notes on the close decision.

        Returns:
            Updated position dict with realized P&L.

        Raises:
            ValueError: If position not found or already closed.
        """
        position = self._find_position(position_id)
        if position is None:
            raise ValueError(f"Position {position_id} not found")
        if not position["is_open"]:
            raise ValueError(f"Position {position_id} is already closed")

        now = close_date or datetime.utcnow()
        fx_rate = current_fx_rate or position.get("entry_fx_rate") or 5.0

        # Compute realized P&L
        realized_pnl_brl = compute_pnl_brl(
            position["entry_price"],
            close_price,
            position["notional_brl"],
            position["direction"],
            position["instrument"],
            position["asset_class"],
        )

        # Subtract exit transaction cost
        exit_cost = self.cost_model.get_cost(
            position["instrument"], position["notional_brl"]
        )
        realized_pnl_brl -= exit_cost

        realized_pnl_usd = compute_pnl_usd(realized_pnl_brl, fx_rate)

        # Update position
        position["is_open"] = False
        position["closed_at"] = now
        position["close_price"] = close_price
        position["realized_pnl_brl"] = realized_pnl_brl
        position["realized_pnl_usd"] = realized_pnl_usd
        position["unrealized_pnl_brl"] = 0.0
        position["unrealized_pnl_usd"] = 0.0
        position["updated_at"] = now
        position["transaction_cost_brl"] = (
            position.get("transaction_cost_brl") or 0.0
        ) + exit_cost

        # Create journal entry
        journal_content = {
            "entry_type": "CLOSE",
            "instrument": position["instrument"],
            "direction": position["direction"],
            "notional_brl": position["notional_brl"],
            "entry_price": close_price,
            "manager_notes": notes,
            "system_notes": (
                f"Position #{position_id} closed."
                f" Realized P&L: {realized_pnl_brl:.2f} BRL / {realized_pnl_usd:.2f} USD"
            ),
        }
        content_hash = self._compute_content_hash(**journal_content)

        journal_entry = {
            "id": len(self._journal) + 1,
            "created_at": now if isinstance(now, datetime) else datetime.utcnow(),
            "entry_type": "CLOSE",
            "position_id": position_id,
            "proposal_id": None,
            "instrument": position["instrument"],
            "direction": position["direction"],
            "notional_brl": position["notional_brl"],
            "entry_price": close_price,
            "manager_notes": notes,
            "system_notes": journal_content["system_notes"],
            "market_snapshot": {},
            "portfolio_snapshot": {},
            "content_hash": content_hash,
            "is_locked": True,
        }

        self._journal.append(journal_entry)

        logger.info(
            "position_closed",
            position_id=position_id,
            instrument=position["instrument"],
            realized_pnl_brl=realized_pnl_brl,
            realized_pnl_usd=realized_pnl_usd,
        )

        return position

    # -------------------------------------------------------------------------
    # Mark to market
    # -------------------------------------------------------------------------

    def mark_to_market(
        self,
        price_overrides: dict[str, float] | None = None,
        current_fx_rate: float | None = None,
        as_of_date: date | None = None,
        persist_snapshot: bool = True,
    ) -> list[dict]:
        """Mark all open positions to market.

        Args:
            price_overrides: Optional dict of {instrument: price} for manual overrides.
            current_fx_rate: Current USDBRL rate for USD conversion.
            as_of_date: Reference date for the mark.
            persist_snapshot: Whether to save P&L snapshots to history.

        Returns:
            List of updated position dicts for open positions.
        """
        open_positions = [p for p in self._positions if p["is_open"]]
        if not open_positions:
            return []

        ref_date = as_of_date or date.today()
        fx_rate = current_fx_rate or 5.0

        # Get prices
        prices = self.mtm_service.get_prices_for_positions(
            open_positions, price_overrides, ref_date
        )

        updated = []
        for pos in open_positions:
            instrument = pos["instrument"]
            price_info = prices.get(instrument, {})
            current_price = price_info.get("price", pos["entry_price"])

            # Use override if available
            if price_overrides and instrument in price_overrides:
                current_price = price_overrides[instrument]

            # Compute MTM
            mtm = self.mtm_service.compute_position_mtm(pos, current_price, fx_rate)

            # Update position
            pos["current_price"] = current_price
            pos["unrealized_pnl_brl"] = mtm["unrealized_pnl_brl"]
            pos["unrealized_pnl_usd"] = mtm["unrealized_pnl_usd"]
            pos["updated_at"] = datetime.utcnow()

            # Persist snapshot
            if persist_snapshot:
                snapshot = {
                    "id": len(self._pnl_history) + 1,
                    "snapshot_date": ref_date,
                    "position_id": pos["id"],
                    "instrument": instrument,
                    "mark_price": current_price,
                    "unrealized_pnl_brl": mtm["unrealized_pnl_brl"],
                    "unrealized_pnl_usd": mtm["unrealized_pnl_usd"],
                    "daily_pnl_brl": mtm["daily_pnl_brl"],
                    "daily_pnl_usd": mtm["daily_pnl_usd"],
                    "cumulative_pnl_brl": mtm["unrealized_pnl_brl"],
                    "dv01": mtm["current_dv01"],
                    "delta": mtm["current_delta"],
                    "var_contribution": None,
                    "fx_rate": fx_rate,
                    "is_manual_override": bool(
                        price_overrides and instrument in price_overrides
                    ),
                }
                self._pnl_history.append(snapshot)

            updated.append(pos)

        logger.info(
            "mtm_completed",
            n_positions=len(updated),
            as_of_date=str(ref_date),
        )

        return updated

    # -------------------------------------------------------------------------
    # Get book
    # -------------------------------------------------------------------------

    def get_book(self, as_of_date: date | None = None) -> dict:
        """Get portfolio book with summary, positions, and asset class breakdown.

        Args:
            as_of_date: Reference date for the book (defaults to today).

        Returns:
            Structured dict with summary, positions, by_asset_class, closed_today.
        """
        ref_date = as_of_date or date.today()

        open_positions = [p for p in self._positions if p["is_open"]]
        closed_positions = [p for p in self._positions if not p["is_open"]]

        # Closed today
        closed_today = []
        for p in closed_positions:
            closed_at = p.get("closed_at")
            if closed_at is not None:
                close_date = (
                    closed_at.date() if isinstance(closed_at, datetime) else closed_at
                )
                if close_date == ref_date:
                    closed_today.append(p)

        # Summary calculations
        total_notional = sum(abs(p["notional_brl"]) for p in open_positions)
        leverage = total_notional / self.aum if self.aum > 0 else 0.0

        total_unrealized_pnl_brl = sum(
            (p.get("unrealized_pnl_brl") or 0.0) for p in open_positions
        )
        total_unrealized_pnl_usd = sum(
            (p.get("unrealized_pnl_usd") or 0.0) for p in open_positions
        )
        total_realized_pnl_brl = sum(
            (p.get("realized_pnl_brl") or 0.0) for p in closed_positions
        )

        # P&L today/MTD/YTD from pnl_history
        pnl_today_brl = 0.0
        pnl_today_usd = 0.0
        pnl_mtd_brl = 0.0
        pnl_ytd_brl = 0.0
        pnl_mtd_usd = 0.0
        pnl_ytd_usd = 0.0

        for snap in self._pnl_history:
            snap_date = snap.get("snapshot_date")
            if not snap_date:
                continue
            daily_brl = snap.get("daily_pnl_brl") or 0.0
            daily_usd = snap.get("daily_pnl_usd") or 0.0

            if snap_date == ref_date:
                pnl_today_brl += daily_brl
                pnl_today_usd += daily_usd

            if (
                isinstance(snap_date, date)
                and snap_date.year == ref_date.year
                and snap_date.month == ref_date.month
            ):
                pnl_mtd_brl += daily_brl
                pnl_mtd_usd += daily_usd

            if isinstance(snap_date, date) and snap_date.year == ref_date.year:
                pnl_ytd_brl += daily_brl
                pnl_ytd_usd += daily_usd

        # By asset class breakdown
        by_asset_class: dict[str, dict] = {}
        for p in open_positions:
            ac = p.get("asset_class", "UNKNOWN")
            if ac not in by_asset_class:
                by_asset_class[ac] = {
                    "count": 0,
                    "notional_brl": 0.0,
                    "unrealized_pnl_brl": 0.0,
                }
            by_asset_class[ac]["count"] += 1
            by_asset_class[ac]["notional_brl"] += abs(p["notional_brl"])
            by_asset_class[ac]["unrealized_pnl_brl"] += (
                p.get("unrealized_pnl_brl") or 0.0
            )

        return {
            "summary": {
                "aum": self.aum,
                "total_notional_brl": total_notional,
                "leverage": leverage,
                "open_positions": len(open_positions),
                "pnl_today_brl": pnl_today_brl,
                "pnl_mtd_brl": pnl_mtd_brl,
                "pnl_ytd_brl": pnl_ytd_brl,
                "pnl_today_usd": pnl_today_usd,
                "pnl_mtd_usd": pnl_mtd_usd,
                "pnl_ytd_usd": pnl_ytd_usd,
                "total_unrealized_pnl_brl": total_unrealized_pnl_brl,
                "total_unrealized_pnl_usd": total_unrealized_pnl_usd,
                "total_realized_pnl_brl": total_realized_pnl_brl,
            },
            "positions": open_positions,
            "by_asset_class": by_asset_class,
            "closed_today": closed_today,
        }

    # -------------------------------------------------------------------------
    # P&L timeseries
    # -------------------------------------------------------------------------

    def get_pnl_timeseries(
        self,
        position_id: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict]:
        """Get P&L history timeseries.

        Args:
            position_id: Filter by position ID (None = portfolio-level aggregate).
            start_date: Filter start date (inclusive).
            end_date: Filter end date (inclusive).

        Returns:
            List of P&L snapshot dicts, filtered and optionally aggregated.
        """
        filtered = self._pnl_history

        if position_id is not None:
            filtered = [s for s in filtered if s.get("position_id") == position_id]

        if start_date is not None:
            filtered = [
                s
                for s in filtered
                if s.get("snapshot_date") and s["snapshot_date"] >= start_date
            ]

        if end_date is not None:
            filtered = [
                s
                for s in filtered
                if s.get("snapshot_date") and s["snapshot_date"] <= end_date
            ]

        if position_id is not None:
            return sorted(filtered, key=lambda s: s.get("snapshot_date", date.min))

        # Portfolio-level: aggregate by date
        by_date: dict[date, dict] = {}
        for snap in filtered:
            snap_date = snap.get("snapshot_date")
            if snap_date is None:
                continue
            if snap_date not in by_date:
                by_date[snap_date] = {
                    "snapshot_date": snap_date,
                    "daily_pnl_brl": 0.0,
                    "daily_pnl_usd": 0.0,
                    "cumulative_pnl_brl": 0.0,
                    "unrealized_pnl_brl": 0.0,
                }
            by_date[snap_date]["daily_pnl_brl"] += snap.get("daily_pnl_brl") or 0.0
            by_date[snap_date]["daily_pnl_usd"] += snap.get("daily_pnl_usd") or 0.0
            by_date[snap_date]["cumulative_pnl_brl"] += (
                snap.get("cumulative_pnl_brl") or 0.0
            )
            by_date[snap_date]["unrealized_pnl_brl"] += (
                snap.get("unrealized_pnl_brl") or 0.0
            )

        return sorted(by_date.values(), key=lambda s: s.get("snapshot_date", date.min))

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _find_position(self, position_id: int) -> dict | None:
        """Find position by ID."""
        for p in self._positions:
            if p["id"] == position_id:
                return p
        return None

    def _compute_content_hash(self, **fields: Any) -> str:
        """Compute SHA256 content hash for journal entry integrity.

        Args:
            **fields: Key-value pairs to hash.

        Returns:
            Hex-encoded SHA256 hash string (64 chars).
        """
        serialized = json.dumps(fields, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()

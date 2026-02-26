"""Performance attribution engine for the Portfolio Management System.

Decomposes portfolio P&L across multiple dimensions:
- By strategy (strategy_ids on each position)
- By asset class
- By instrument (per position)
- By factor (tag-based mapping from FACTOR_TAGS)
- By time period (weekly/monthly sub-buckets)
- By trade type (systematic vs discretionary)

All attribution dimensions are additive: each dimension sums to the total P&L
independently. The engine supports standard periods (daily, WTD, MTD, QTD, YTD,
inception) and custom date ranges.

This class operates on in-memory data from PositionManager (no DB dependency).
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta

import structlog

from .position_manager import PositionManager

logger = structlog.get_logger(__name__)


class PerformanceAttributionEngine:
    """Multi-dimensional P&L attribution engine.

    Decomposes portfolio returns across strategy, asset class, instrument,
    factor, time period, and trade type dimensions. Each dimension sums
    independently to the total P&L (additive attribution).

    Factor attribution uses a tag-based mapping (FACTOR_TAGS) that maps
    strategy IDs to one or more factor categories. When a position maps
    to multiple factors, P&L is split equally across them.

    Args:
        position_manager: PositionManager instance with positions and P&L history.
    """

    # -------------------------------------------------------------------------
    # Factor tag mapping: strategy_id -> list of factor tags
    # -------------------------------------------------------------------------
    FACTOR_TAGS: dict[str, list[str]] = {
        "RATES_BR_01": ["carry"],
        "RATES_BR_02": ["macro-discretionary"],
        "RATES_BR_03": ["momentum", "mean-reversion"],
        "RATES_BR_04": ["macro-discretionary"],
        "RATES_03": ["relative-value"],
        "RATES_04": ["carry", "mean-reversion"],
        "RATES_05": ["event-driven"],
        "RATES_06": ["event-driven"],
        "FX_BR_01": ["carry"],
        "FX_02": ["carry", "momentum"],
        "FX_03": ["momentum"],
        "FX_04": ["relative-value"],
        "FX_05": ["macro-discretionary"],
        "INF_BR_01": ["carry"],
        "INF_02": ["event-driven"],
        "INF_03": ["carry"],
        "CUPOM_01": ["carry", "relative-value"],
        "CUPOM_02": ["relative-value"],
        "SOV_BR_01": ["macro-discretionary"],
        "SOV_01": ["momentum"],
        "SOV_02": ["relative-value"],
        "SOV_03": ["event-driven"],
        "CROSS_01": ["macro-discretionary"],
        "CROSS_02": ["momentum"],
    }

    def __init__(self, position_manager: PositionManager | None = None) -> None:
        self.position_manager = position_manager

    # -------------------------------------------------------------------------
    # Main attribution method
    # -------------------------------------------------------------------------

    def compute_attribution(
        self,
        start_date: date,
        end_date: date | None = None,
        period_label: str | None = None,
    ) -> dict:
        """Compute multi-dimensional P&L attribution for a date range.

        Args:
            start_date: Start of the attribution period (inclusive).
            end_date: End of the attribution period (inclusive). Defaults to today.
            period_label: Label for the period (e.g., "MTD", "YTD"). Auto-computed if None.

        Returns:
            Dict with keys: period, total_pnl_brl, total_return_pct,
            by_strategy, by_asset_class, by_instrument, by_factor,
            by_time_period, by_trade_type, performance_stats.
        """
        end_date = end_date or date.today()
        label = period_label or f"{start_date} to {end_date}"
        calendar_days = (end_date - start_date).days + 1

        if self.position_manager is None:
            return self._empty_attribution(start_date, end_date, label, calendar_days)

        # Collect positions active during the period
        positions = self._get_active_positions(start_date, end_date)
        aum = self.position_manager.aum or 100_000_000.0

        # Compute total P&L
        total_pnl_brl = self._compute_total_pnl(positions)
        total_return_pct = (total_pnl_brl / aum * 100) if aum > 0 else 0.0

        # Build each attribution dimension
        by_strategy = self._attribute_by_strategy(positions, aum)
        by_asset_class = self._attribute_by_asset_class(positions, aum)
        by_instrument = self._attribute_by_instrument(positions)
        by_factor = self._attribute_by_factor(positions, aum)
        by_time_period = self._attribute_by_time_period(start_date, end_date, aum)
        by_trade_type = self._attribute_by_trade_type(positions)
        performance_stats = self._compute_performance_stats(start_date, end_date, aum)

        return {
            "period": {
                "start": start_date,
                "end": end_date,
                "calendar_days": calendar_days,
                "label": label,
            },
            "total_pnl_brl": total_pnl_brl,
            "total_return_pct": total_return_pct,
            "by_strategy": by_strategy,
            "by_asset_class": by_asset_class,
            "by_instrument": by_instrument,
            "by_factor": by_factor,
            "by_time_period": by_time_period,
            "by_trade_type": by_trade_type,
            "performance_stats": performance_stats,
        }

    # -------------------------------------------------------------------------
    # Convenience period methods
    # -------------------------------------------------------------------------

    def compute_for_period(self, period: str, as_of: date | None = None) -> dict:
        """Compute attribution for a named period.

        Args:
            period: One of "daily", "WTD", "MTD", "QTD", "YTD",
                    "inception", "custom".
            as_of: Reference date (defaults to today).

        Returns:
            Attribution dict from compute_attribution().
        """
        ref = as_of or date.today()

        if period == "daily":
            return self.compute_attribution(ref, ref, period_label="Daily")

        elif period == "WTD":
            # Monday of current week
            weekday = ref.weekday()  # Monday=0
            start = ref - timedelta(days=weekday)
            return self.compute_attribution(start, ref, period_label="WTD")

        elif period == "MTD":
            start = ref.replace(day=1)
            return self.compute_attribution(start, ref, period_label="MTD")

        elif period == "QTD":
            quarter_start_month = ((ref.month - 1) // 3) * 3 + 1
            start = ref.replace(month=quarter_start_month, day=1)
            return self.compute_attribution(start, ref, period_label="QTD")

        elif period == "YTD":
            start = ref.replace(month=1, day=1)
            return self.compute_attribution(start, ref, period_label="YTD")

        elif period == "inception":
            start = self._get_inception_date()
            return self.compute_attribution(start, ref, period_label="Inception")

        else:
            # Fallback: daily
            return self.compute_attribution(ref, ref, period_label=period)

    def compute_custom_range(self, start_date: date, end_date: date) -> dict:
        """Compute attribution for an explicit date range.

        Args:
            start_date: Start date (inclusive).
            end_date: End date (inclusive).

        Returns:
            Attribution dict from compute_attribution().
        """
        return self.compute_attribution(start_date, end_date, period_label="Custom")

    # -------------------------------------------------------------------------
    # Equity curve
    # -------------------------------------------------------------------------

    def compute_equity_curve(
        self, start_date: date, end_date: date | None = None
    ) -> list[dict]:
        """Compute daily equity curve from P&L history.

        Args:
            start_date: Start date (inclusive).
            end_date: End date (inclusive). Defaults to today.

        Returns:
            List of dicts with date, equity_brl, return_pct_daily,
            return_pct_cumulative, drawdown_pct.
        """
        end_date = end_date or date.today()

        if self.position_manager is None:
            return []

        aum = self.position_manager.aum or 100_000_000.0

        # Aggregate daily P&L from history
        daily_pnl = self._aggregate_daily_pnl(start_date, end_date)
        if not daily_pnl:
            return []

        curve: list[dict] = []
        cumulative_pnl = 0.0
        peak_equity = aum

        for snap_date in sorted(daily_pnl.keys()):
            day_pnl = daily_pnl[snap_date]
            cumulative_pnl += day_pnl
            equity = aum + cumulative_pnl

            return_daily = (day_pnl / aum * 100) if aum > 0 else 0.0
            return_cumulative = (cumulative_pnl / aum * 100) if aum > 0 else 0.0

            peak_equity = max(peak_equity, equity)
            drawdown = ((equity - peak_equity) / peak_equity * 100) if peak_equity > 0 else 0.0

            curve.append({
                "date": snap_date,
                "equity_brl": equity,
                "return_pct_daily": return_daily,
                "return_pct_cumulative": return_cumulative,
                "drawdown_pct": drawdown,
            })

        return curve

    # -------------------------------------------------------------------------
    # Factor tag lookup
    # -------------------------------------------------------------------------

    def _get_factor_tags(self, strategy_id: str) -> list[str]:
        """Look up factor tags for a strategy ID.

        Args:
            strategy_id: Strategy identifier to look up.

        Returns:
            List of factor tags, or ["untagged"] if not found.
        """
        return self.FACTOR_TAGS.get(strategy_id, ["untagged"])

    # -------------------------------------------------------------------------
    # Internal: active positions
    # -------------------------------------------------------------------------

    def _get_active_positions(self, start_date: date, end_date: date) -> list[dict]:
        """Get all positions active during the period.

        A position is active if it was opened before end_date AND
        (still open OR closed after start_date).

        Args:
            start_date: Period start (inclusive).
            end_date: Period end (inclusive).

        Returns:
            List of position dicts.
        """
        if self.position_manager is None:
            return []

        active: list[dict] = []
        for pos in self.position_manager._positions:
            entry_date = pos.get("entry_date")
            if entry_date is None:
                continue

            # Must have been opened on or before end_date
            if isinstance(entry_date, datetime):
                entry_date = entry_date.date()
            if entry_date > end_date:
                continue

            # If closed, must have been closed on or after start_date
            if not pos["is_open"]:
                closed_at = pos.get("closed_at")
                if closed_at is not None:
                    close_date = closed_at.date() if isinstance(closed_at, datetime) else closed_at
                    if close_date < start_date:
                        continue

            active.append(pos)

        return active

    # -------------------------------------------------------------------------
    # Internal: total P&L
    # -------------------------------------------------------------------------

    def _compute_total_pnl(self, positions: list[dict]) -> float:
        """Compute total P&L from active positions.

        For closed positions: use realized_pnl_brl.
        For open positions: use unrealized_pnl_brl.
        """
        total = 0.0
        for pos in positions:
            if pos["is_open"]:
                total += pos.get("unrealized_pnl_brl") or 0.0
            else:
                total += pos.get("realized_pnl_brl") or 0.0
        return total

    # -------------------------------------------------------------------------
    # Attribution dimensions
    # -------------------------------------------------------------------------

    def _attribute_by_strategy(self, positions: list[dict], aum: float) -> list[dict]:
        """Group P&L by strategy_id. Additive: sums to total."""
        strategy_data: dict[str, dict] = {}

        for pos in positions:
            pnl = self._position_pnl(pos)
            strategy_ids = pos.get("strategy_ids") or ["UNASSIGNED"]
            strategy_weights = pos.get("strategy_weights") or {}

            # Split P&L across strategies
            if strategy_weights:
                total_weight = sum(strategy_weights.values()) or 1.0
                for sid, weight in strategy_weights.items():
                    share = pnl * (weight / total_weight)
                    self._accumulate_strategy(strategy_data, sid, share, pos)
            else:
                # Equal split across strategy_ids
                n = len(strategy_ids)
                for sid in strategy_ids:
                    share = pnl / n
                    self._accumulate_strategy(strategy_data, sid, share, pos)

        result = []
        for sid, data in sorted(strategy_data.items()):
            wins = data["wins"]
            total = data["trades"]
            result.append({
                "strategy_id": sid,
                "pnl_brl": data["pnl"],
                "return_contribution_pct": (data["pnl"] / aum * 100) if aum > 0 else 0.0,
                "trades_count": total,
                "win_rate_pct": (wins / total * 100) if total > 0 else 0.0,
            })

        return result

    def _accumulate_strategy(
        self, data: dict[str, dict], sid: str, pnl_share: float, pos: dict
    ) -> None:
        """Helper to accumulate strategy attribution data."""
        if sid not in data:
            data[sid] = {"pnl": 0.0, "trades": 0, "wins": 0}
        data[sid]["pnl"] += pnl_share
        data[sid]["trades"] += 1
        if pnl_share > 0:
            data[sid]["wins"] += 1

    def _attribute_by_asset_class(self, positions: list[dict], aum: float) -> list[dict]:
        """Group P&L by asset class. Additive: sums to total."""
        ac_data: dict[str, dict] = {}

        for pos in positions:
            ac = pos.get("asset_class", "UNKNOWN")
            pnl = self._position_pnl(pos)
            notional = abs(pos.get("notional_brl") or 0.0)

            if ac not in ac_data:
                ac_data[ac] = {"pnl": 0.0, "notional_sum": 0.0, "count": 0}
            ac_data[ac]["pnl"] += pnl
            ac_data[ac]["notional_sum"] += notional
            ac_data[ac]["count"] += 1

        result = []
        for ac, data in sorted(ac_data.items()):
            result.append({
                "asset_class": ac,
                "pnl_brl": data["pnl"],
                "return_contribution_pct": (data["pnl"] / aum * 100) if aum > 0 else 0.0,
                "avg_notional_brl": data["notional_sum"] / data["count"] if data["count"] > 0 else 0.0,
            })

        return result

    def _attribute_by_instrument(self, positions: list[dict]) -> list[dict]:
        """Per-position attribution. Additive: sums to total."""
        result = []
        for pos in positions:
            pnl = self._position_pnl(pos)
            entry_date = pos.get("entry_date", date.today())
            if isinstance(entry_date, datetime):
                entry_date = entry_date.date()

            # Holding days
            if pos["is_open"]:
                holding_days = (date.today() - entry_date).days
            else:
                closed_at = pos.get("closed_at")
                if closed_at is not None:
                    close_date = closed_at.date() if isinstance(closed_at, datetime) else closed_at
                    holding_days = (close_date - entry_date).days
                else:
                    holding_days = 0

            notional = abs(pos.get("notional_brl") or 1.0)
            return_pct = (pnl / notional * 100) if notional > 0 else 0.0

            result.append({
                "position_id": pos["id"],
                "instrument": pos.get("instrument", "UNKNOWN"),
                "direction": pos.get("direction", "UNKNOWN"),
                "pnl_brl": pnl,
                "return_pct": return_pct,
                "holding_days": holding_days,
            })

        return result

    def _attribute_by_factor(self, positions: list[dict], aum: float) -> list[dict]:
        """Factor-based attribution using FACTOR_TAGS. Additive: sums to total."""
        factor_data: dict[str, dict] = {}

        for pos in positions:
            pnl = self._position_pnl(pos)
            strategy_ids = pos.get("strategy_ids") or ["UNASSIGNED"]

            # Collect all factors for this position
            all_factors: list[str] = []
            for sid in strategy_ids:
                all_factors.extend(self._get_factor_tags(sid))

            # Deduplicate
            unique_factors = list(set(all_factors))
            n_factors = len(unique_factors)

            # Split P&L equally across factors
            for factor in unique_factors:
                share = pnl / n_factors
                if factor not in factor_data:
                    factor_data[factor] = {"pnl": 0.0, "strategies": set()}
                factor_data[factor]["pnl"] += share
                for sid in strategy_ids:
                    if factor in self._get_factor_tags(sid):
                        factor_data[factor]["strategies"].add(sid)

        result = []
        for factor, data in sorted(factor_data.items()):
            result.append({
                "factor": factor,
                "pnl_brl": data["pnl"],
                "return_contribution_pct": (data["pnl"] / aum * 100) if aum > 0 else 0.0,
                "strategies_count": len(data["strategies"]),
            })

        return result

    def _attribute_by_time_period(
        self, start_date: date, end_date: date, aum: float
    ) -> list[dict]:
        """Sub-period breakdown. Weekly if <= 90 days, monthly if > 90 days."""
        daily_pnl = self._aggregate_daily_pnl(start_date, end_date)
        if not daily_pnl:
            return []

        range_days = (end_date - start_date).days + 1
        use_weekly = range_days <= 90

        # Build buckets
        buckets: list[dict] = []
        if use_weekly:
            buckets = self._build_weekly_buckets(start_date, end_date)
        else:
            buckets = self._build_monthly_buckets(start_date, end_date)

        # Assign daily P&L to buckets
        cumulative = 0.0
        for bucket in buckets:
            bucket_pnl = 0.0
            for d in sorted(daily_pnl.keys()):
                if bucket["period_start"] <= d <= bucket["period_end"]:
                    bucket_pnl += daily_pnl[d]
            cumulative += bucket_pnl
            bucket["pnl_brl"] = bucket_pnl
            bucket["return_pct"] = (bucket_pnl / aum * 100) if aum > 0 else 0.0
            bucket["cumulative_pnl_brl"] = cumulative

        return buckets

    def _build_weekly_buckets(self, start_date: date, end_date: date) -> list[dict]:
        """Build weekly period buckets."""
        buckets = []
        current = start_date
        week_num = 1
        while current <= end_date:
            week_end = min(current + timedelta(days=6), end_date)
            buckets.append({
                "period_start": current,
                "period_end": week_end,
                "label": f"Week {week_num}",
                "pnl_brl": 0.0,
                "return_pct": 0.0,
                "cumulative_pnl_brl": 0.0,
            })
            current = week_end + timedelta(days=1)
            week_num += 1
        return buckets

    def _build_monthly_buckets(self, start_date: date, end_date: date) -> list[dict]:
        """Build monthly period buckets."""
        buckets = []
        current = start_date
        while current <= end_date:
            # End of month
            if current.month == 12:
                month_end = date(current.year + 1, 1, 1) - timedelta(days=1)
            else:
                month_end = date(current.year, current.month + 1, 1) - timedelta(days=1)
            month_end = min(month_end, end_date)

            month_names = [
                "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
            ]
            label = f"{month_names[current.month]} {current.year}"

            buckets.append({
                "period_start": current,
                "period_end": month_end,
                "label": label,
                "pnl_brl": 0.0,
                "return_pct": 0.0,
                "cumulative_pnl_brl": 0.0,
            })

            # Move to first of next month
            if current.month == 12:
                current = date(current.year + 1, 1, 1)
            else:
                current = date(current.year, current.month + 1, 1)

        return buckets

    def _attribute_by_trade_type(self, positions: list[dict]) -> dict:
        """Attribution by trade type: systematic vs discretionary."""
        systematic_pnl = 0.0
        systematic_count = 0
        discretionary_pnl = 0.0
        discretionary_count = 0

        for pos in positions:
            pnl = self._position_pnl(pos)
            # Check if this position originated from a discretionary proposal
            # For simplicity, positions with notes containing "discretionary" or
            # without strategy_ids are discretionary; otherwise systematic
            notes = (pos.get("notes") or "").lower()
            strategy_ids = pos.get("strategy_ids") or []

            if "discretionary" in notes or not strategy_ids:
                discretionary_pnl += pnl
                discretionary_count += 1
            else:
                systematic_pnl += pnl
                systematic_count += 1

        return {
            "systematic": {"pnl_brl": systematic_pnl, "count": systematic_count},
            "discretionary": {"pnl_brl": discretionary_pnl, "count": discretionary_count},
        }

    # -------------------------------------------------------------------------
    # Performance statistics
    # -------------------------------------------------------------------------

    def _compute_performance_stats(
        self, start_date: date, end_date: date, aum: float
    ) -> dict:
        """Compute performance statistics from daily P&L snapshots."""
        daily_pnl = self._aggregate_daily_pnl(start_date, end_date)
        if not daily_pnl:
            return {
                "annualized_return_pct": 0.0,
                "annualized_vol_pct": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "max_drawdown_pct": 0.0,
                "win_rate_pct": 0.0,
                "profit_factor": 0.0,
                "avg_win_brl": 0.0,
                "avg_loss_brl": 0.0,
            }

        sorted_dates = sorted(daily_pnl.keys())
        daily_returns = [daily_pnl[d] / aum for d in sorted_dates] if aum > 0 else []
        n_days = len(daily_returns)

        if n_days == 0:
            return {
                "annualized_return_pct": 0.0,
                "annualized_vol_pct": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "max_drawdown_pct": 0.0,
                "win_rate_pct": 0.0,
                "profit_factor": 0.0,
                "avg_win_brl": 0.0,
                "avg_loss_brl": 0.0,
            }

        # Mean and std
        mean_return = sum(daily_returns) / n_days
        variance = sum((r - mean_return) ** 2 for r in daily_returns) / n_days if n_days > 0 else 0.0
        std_return = math.sqrt(variance) if variance > 0 else 0.0

        # Downside deviation (for Sortino)
        downside_returns = [r for r in daily_returns if r < 0]
        downside_var = (
            sum(r ** 2 for r in downside_returns) / n_days
            if n_days > 0
            else 0.0
        )
        downside_std = math.sqrt(downside_var)

        # Annualization factor
        ann_factor = 252

        annualized_return = mean_return * ann_factor * 100
        annualized_vol = std_return * math.sqrt(ann_factor) * 100

        sharpe = (mean_return / std_return * math.sqrt(ann_factor)) if std_return > 0 else 0.0
        sortino = (mean_return / downside_std * math.sqrt(ann_factor)) if downside_std > 0 else 0.0

        # Max drawdown
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for r in daily_returns:
            cumulative += r
            peak = max(peak, cumulative)
            dd = cumulative - peak
            max_dd = min(max_dd, dd)

        # Win/loss stats
        daily_pnl_values = [daily_pnl[d] for d in sorted_dates]
        wins = [p for p in daily_pnl_values if p > 0]
        losses = [p for p in daily_pnl_values if p < 0]

        win_rate = (len(wins) / n_days * 100) if n_days > 0 else 0.0
        total_wins = sum(wins) if wins else 0.0
        total_losses = abs(sum(losses)) if losses else 0.0
        profit_factor = (total_wins / total_losses) if total_losses > 0 else 0.0
        avg_win = (total_wins / len(wins)) if wins else 0.0
        avg_loss = (sum(losses) / len(losses)) if losses else 0.0

        return {
            "annualized_return_pct": annualized_return,
            "annualized_vol_pct": annualized_vol,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "max_drawdown_pct": max_dd * 100,
            "win_rate_pct": win_rate,
            "profit_factor": profit_factor,
            "avg_win_brl": avg_win,
            "avg_loss_brl": avg_loss,
        }

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _position_pnl(self, pos: dict) -> float:
        """Get P&L for a position (realized if closed, unrealized if open)."""
        if pos["is_open"]:
            return pos.get("unrealized_pnl_brl") or 0.0
        return pos.get("realized_pnl_brl") or 0.0

    def _aggregate_daily_pnl(
        self, start_date: date, end_date: date
    ) -> dict[date, float]:
        """Aggregate daily P&L from _pnl_history within the date range."""
        if self.position_manager is None:
            return {}

        daily: dict[date, float] = {}
        for snap in self.position_manager._pnl_history:
            snap_date = snap.get("snapshot_date")
            if snap_date is None:
                continue
            if isinstance(snap_date, datetime):
                snap_date = snap_date.date()
            if start_date <= snap_date <= end_date:
                daily_pnl = snap.get("daily_pnl_brl") or 0.0
                daily[snap_date] = daily.get(snap_date, 0.0) + daily_pnl

        return daily

    def _get_inception_date(self) -> date:
        """Get the earliest position entry date for inception period."""
        if self.position_manager is None or not self.position_manager._positions:
            return date.today()

        earliest = date.today()
        for pos in self.position_manager._positions:
            entry_date = pos.get("entry_date")
            if entry_date is not None:
                if isinstance(entry_date, datetime):
                    entry_date = entry_date.date()
                if entry_date < earliest:
                    earliest = entry_date

        return earliest

    def _empty_attribution(
        self, start_date: date, end_date: date, label: str, calendar_days: int
    ) -> dict:
        """Return empty attribution when no position manager is available."""
        return {
            "period": {
                "start": start_date,
                "end": end_date,
                "calendar_days": calendar_days,
                "label": label,
            },
            "total_pnl_brl": 0.0,
            "total_return_pct": 0.0,
            "by_strategy": [],
            "by_asset_class": [],
            "by_instrument": [],
            "by_factor": [],
            "by_time_period": [],
            "by_trade_type": {
                "systematic": {"pnl_brl": 0.0, "count": 0},
                "discretionary": {"pnl_brl": 0.0, "count": 0},
            },
            "performance_stats": {
                "annualized_return_pct": 0.0,
                "annualized_vol_pct": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "max_drawdown_pct": 0.0,
                "win_rate_pct": 0.0,
                "profit_factor": 0.0,
                "avg_win_brl": 0.0,
                "avg_loss_brl": 0.0,
            },
        }

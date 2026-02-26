"""Tests for PerformanceAttributionEngine multi-dimensional P&L decomposition.

Verifies:
- Additive attribution: by_strategy sum == by_asset_class sum == by_instrument sum == total
- Factor tags applied correctly via FACTOR_TAGS mapping
- Standard periods (MTD, YTD, inception) return valid attribution
- Equity curve consistency with P&L history
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from src.pms.attribution import PerformanceAttributionEngine
from src.pms.position_manager import PositionManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def populated_pm() -> PositionManager:
    """Create a PositionManager with 3 positions across 2 asset classes, MTM snapshots, and one closed."""
    pm = PositionManager()

    # Position 1: RATES (still open)
    pm.open_position(
        instrument="DI1_F27",
        asset_class="RATES",
        direction="LONG",
        notional_brl=10_000_000.0,
        entry_price=11.50,
        entry_date=date(2026, 2, 10),
        strategy_ids=["RATES_BR_01"],
    )

    # Position 2: FX (still open)
    pm.open_position(
        instrument="USDBRL",
        asset_class="FX",
        direction="SHORT",
        notional_brl=5_000_000.0,
        entry_price=5.80,
        entry_date=date(2026, 2, 12),
        strategy_ids=["FX_02"],
    )

    # Position 3: RATES (will be closed)
    pm.open_position(
        instrument="DI1_F28",
        asset_class="RATES",
        direction="LONG",
        notional_brl=8_000_000.0,
        entry_price=12.00,
        entry_date=date(2026, 2, 14),
        strategy_ids=["RATES_BR_02"],
    )

    # Mark-to-market open positions with specific prices
    pm.mark_to_market(
        price_overrides={
            "DI1_F27": 11.55,
            "USDBRL": 5.75,
            "DI1_F28": 12.10,
        },
        as_of_date=date(2026, 2, 20),
    )

    # Add additional MTM snapshots for equity curve testing
    pm.mark_to_market(
        price_overrides={
            "DI1_F27": 11.60,
            "USDBRL": 5.70,
            "DI1_F28": 12.15,
        },
        as_of_date=date(2026, 2, 21),
    )

    pm.mark_to_market(
        price_overrides={
            "DI1_F27": 11.58,
            "USDBRL": 5.72,
            "DI1_F28": 12.12,
        },
        as_of_date=date(2026, 2, 22),
    )

    # Close position 3
    pm.close_position(
        position_id=3,
        close_price=12.12,
        close_date=datetime(2026, 2, 22, 16, 0, 0),
    )

    return pm


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAttribution:
    """Tests for PerformanceAttributionEngine."""

    def test_attribution_sums_to_total(self, populated_pm: PositionManager) -> None:
        """Verify additive attribution: all dimensions sum to total_pnl_brl."""
        engine = PerformanceAttributionEngine(position_manager=populated_pm)

        result = engine.compute_attribution(
            start_date=date(2026, 2, 10),
            end_date=date(2026, 2, 22),
        )

        total = result["total_pnl_brl"]

        # by_strategy sums to total
        strategy_sum = sum(s["pnl_brl"] for s in result["by_strategy"])
        assert abs(strategy_sum - total) < 0.01, (
            f"by_strategy sum {strategy_sum:.2f} != total {total:.2f}"
        )

        # by_asset_class sums to total
        ac_sum = sum(ac["pnl_brl"] for ac in result["by_asset_class"])
        assert abs(ac_sum - total) < 0.01, (
            f"by_asset_class sum {ac_sum:.2f} != total {total:.2f}"
        )

        # by_instrument sums to total
        inst_sum = sum(i["pnl_brl"] for i in result["by_instrument"])
        assert abs(inst_sum - total) < 0.01, (
            f"by_instrument sum {inst_sum:.2f} != total {total:.2f}"
        )

        # by_factor sums to total
        factor_sum = sum(f["pnl_brl"] for f in result["by_factor"])
        assert abs(factor_sum - total) < 0.01, (
            f"by_factor sum {factor_sum:.2f} != total {total:.2f}"
        )

        # by_trade_type sums to total
        trade_type_sum = (
            result["by_trade_type"]["systematic"]["pnl_brl"]
            + result["by_trade_type"]["discretionary"]["pnl_brl"]
        )
        assert abs(trade_type_sum - total) < 0.01, (
            f"by_trade_type sum {trade_type_sum:.2f} != total {total:.2f}"
        )

        # Verify we have results in each dimension
        assert len(result["by_strategy"]) >= 2  # At least 2 strategies
        assert len(result["by_asset_class"]) >= 2  # RATES and FX
        assert len(result["by_instrument"]) >= 3  # 3 positions
        assert len(result["by_factor"]) >= 1  # At least one factor

        # Verify period metadata
        assert result["period"]["start"] == date(2026, 2, 10)
        assert result["period"]["end"] == date(2026, 2, 22)
        assert result["period"]["calendar_days"] == 13

    def test_factor_attribution(self, populated_pm: PositionManager) -> None:
        """Verify factor tags are applied correctly."""
        engine = PerformanceAttributionEngine(position_manager=populated_pm)

        # FX_02 should map to ["carry", "momentum"]
        tags = engine._get_factor_tags("FX_02")
        assert "carry" in tags
        assert "momentum" in tags
        assert len(tags) == 2

        # RATES_BR_01 should map to ["carry"]
        tags = engine._get_factor_tags("RATES_BR_01")
        assert tags == ["carry"]

        # RATES_BR_02 should map to ["macro-discretionary"]
        tags = engine._get_factor_tags("RATES_BR_02")
        assert tags == ["macro-discretionary"]

        # Unknown strategy should map to ["untagged"]
        tags = engine._get_factor_tags("UNKNOWN_99")
        assert tags == ["untagged"]

        # Run full attribution and verify factors appear
        result = engine.compute_attribution(
            start_date=date(2026, 2, 10),
            end_date=date(2026, 2, 22),
        )

        factor_names = {f["factor"] for f in result["by_factor"]}
        # FX_02 contributes carry + momentum; RATES_BR_01 contributes carry;
        # RATES_BR_02 contributes macro-discretionary
        assert "carry" in factor_names
        assert "macro-discretionary" in factor_names

        # Verify all 24 strategies have tags defined
        assert len(engine.FACTOR_TAGS) == 24

    def test_extended_periods(self, populated_pm: PositionManager) -> None:
        """Test compute_for_period with MTD, YTD, inception."""
        engine = PerformanceAttributionEngine(position_manager=populated_pm)

        # MTD
        mtd = engine.compute_for_period("MTD", as_of=date(2026, 2, 22))
        assert mtd["period"]["label"] == "MTD"
        assert mtd["period"]["start"] == date(2026, 2, 1)
        assert mtd["period"]["end"] == date(2026, 2, 22)
        assert "total_pnl_brl" in mtd
        assert "by_strategy" in mtd

        # YTD
        ytd = engine.compute_for_period("YTD", as_of=date(2026, 2, 22))
        assert ytd["period"]["label"] == "YTD"
        assert ytd["period"]["start"] == date(2026, 1, 1)
        assert ytd["period"]["end"] == date(2026, 2, 22)

        # Inception
        inception = engine.compute_for_period("inception", as_of=date(2026, 2, 22))
        assert inception["period"]["label"] == "Inception"
        # Inception start should be earliest position date (2026-02-10)
        assert inception["period"]["start"] == date(2026, 2, 10)

        # All periods should have valid attribution dicts
        for result in [mtd, ytd, inception]:
            assert "total_pnl_brl" in result
            assert "by_strategy" in result
            assert "by_asset_class" in result
            assert "by_instrument" in result
            assert "by_factor" in result
            assert "by_time_period" in result
            assert "by_trade_type" in result
            assert "performance_stats" in result

    def test_equity_curve_consistency(self, populated_pm: PositionManager) -> None:
        """Verify equity curve has correct points and cumulative returns."""
        engine = PerformanceAttributionEngine(position_manager=populated_pm)

        curve = engine.compute_equity_curve(
            start_date=date(2026, 2, 20),
            end_date=date(2026, 2, 22),
        )

        # We have 3 MTM dates: 2/20, 2/21, 2/22
        assert len(curve) == 3, f"Expected 3 equity curve points, got {len(curve)}"

        # Verify each point has required fields
        for point in curve:
            assert "date" in point
            assert "equity_brl" in point
            assert "return_pct_daily" in point
            assert "return_pct_cumulative" in point
            assert "drawdown_pct" in point

        # Dates should be in order
        dates = [p["date"] for p in curve]
        assert dates == sorted(dates)

        # Cumulative return at each point should accumulate from the start
        # First point cumulative == first point daily
        assert abs(curve[0]["return_pct_cumulative"] - curve[0]["return_pct_daily"]) < 0.01

        # Equity should be AUM + cumulative P&L
        aum = populated_pm.aum
        for point in curve:
            expected_equity = aum * (1 + point["return_pct_cumulative"] / 100)
            assert abs(point["equity_brl"] - expected_equity) < 1.0, (
                f"Equity mismatch on {point['date']}: "
                f"expected ~{expected_equity:.0f}, got {point['equity_brl']:.0f}"
            )

        # Drawdown should be <= 0
        for point in curve:
            assert point["drawdown_pct"] <= 0.0001, (
                f"Drawdown should be <= 0, got {point['drawdown_pct']} on {point['date']}"
            )

"""Comprehensive tests for PositionManager, MarkToMarketService, and pricing module.

All tests use pure in-memory PositionManager (no DB dependency).
30+ tests covering open, close, MTM, book, P&L timeseries, and pricing functions.
"""

from datetime import date, datetime

import pytest

from src.pms.mtm_service import MarkToMarketService
from src.pms.position_manager import PositionManager
from src.pms.pricing import (
    compute_dv01_from_pu,
    compute_fx_delta,
    compute_pnl_brl,
    compute_pnl_usd,
    ntnb_yield_to_price,
    pu_to_rate,
    rate_to_pu,
)

# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def pm() -> PositionManager:
    """Fresh PositionManager with 100M BRL AUM."""
    return PositionManager(aum=100_000_000.0)


@pytest.fixture
def pm_with_positions(pm: PositionManager) -> PositionManager:
    """PositionManager pre-loaded with 3 positions across 2 asset classes."""
    pm.open_position(
        instrument="DI1_F26",
        asset_class="RATES",
        direction="LONG",
        notional_brl=50_000_000.0,
        entry_price=90000.0,
        entry_date=date(2026, 2, 20),
        rate_pct=10.0,
        business_days=252,
        entry_fx_rate=5.0,
    )
    pm.open_position(
        instrument="USDBRL",
        asset_class="FX",
        direction="LONG",
        notional_brl=20_000_000.0,
        entry_price=5.0,
        entry_date=date(2026, 2, 20),
        entry_fx_rate=5.0,
    )
    pm.open_position(
        instrument="CDS_BR_5Y",
        asset_class="CREDIT",
        direction="SHORT",
        notional_brl=10_000_000.0,
        entry_price=150.0,
        entry_date=date(2026, 2, 20),
        entry_fx_rate=5.0,
    )
    return pm


# =============================================================================
# Pricing module tests
# =============================================================================

class TestPricing:
    """Tests for pure pricing functions."""

    def test_rate_to_pu_known_value(self):
        """rate=10%, 252 days -> ~90909.09 (100_000 / 1.10)."""
        result = rate_to_pu(10.0, 252)
        assert abs(result - 90909.09) < 1.0

    def test_pu_to_rate_inverse(self):
        """Verify round-trip: rate -> PU -> rate."""
        original_rate = 12.5
        pu = rate_to_pu(original_rate, 252)
        recovered_rate = pu_to_rate(pu, 252)
        assert abs(recovered_rate - original_rate) < 0.001

    def test_rate_to_pu_zero_days(self):
        """Zero business days returns 100_000 (par)."""
        assert rate_to_pu(10.0, 0) == 100_000.0

    def test_pu_to_rate_edge_cases(self):
        """Edge cases for pu_to_rate."""
        assert pu_to_rate(0, 252) == 0.0
        assert pu_to_rate(100_000, 0) == 0.0

    def test_compute_dv01_positive(self):
        """DV01 should be positive for any valid inputs."""
        pu = rate_to_pu(10.0, 252)
        dv01 = compute_dv01_from_pu(pu, 10.0, 252, 10_000_000.0)
        assert dv01 > 0

    def test_compute_dv01_zero_days(self):
        """DV01 with zero business days should be 0."""
        assert compute_dv01_from_pu(100_000, 10.0, 0, 10_000_000) == 0.0

    def test_compute_fx_delta(self):
        """FX delta = notional / spot."""
        delta = compute_fx_delta(5_000_000.0, 5.0)
        assert abs(delta - 1_000_000.0) < 0.01

    def test_compute_fx_delta_zero_spot(self):
        """FX delta with zero spot returns 0."""
        assert compute_fx_delta(5_000_000.0, 0.0) == 0.0

    def test_compute_pnl_brl_long_profit(self):
        """LONG position, price up -> positive P&L."""
        pnl = compute_pnl_brl(100.0, 110.0, 1_000_000.0, "LONG", "IBOV", "EQUITY")
        assert pnl > 0

    def test_compute_pnl_brl_short_profit(self):
        """SHORT position, price down -> positive P&L."""
        pnl = compute_pnl_brl(100.0, 90.0, 1_000_000.0, "SHORT", "IBOV", "EQUITY")
        assert pnl > 0

    def test_compute_pnl_brl_rates_long(self):
        """RATES LONG (receive fixed): PU increase -> positive P&L."""
        pnl = compute_pnl_brl(90000.0, 91000.0, 10_000_000.0, "LONG", "DI1_F26", "RATES")
        assert pnl > 0

    def test_compute_pnl_brl_rates_short(self):
        """RATES SHORT (pay fixed): PU decrease -> positive P&L."""
        pnl = compute_pnl_brl(90000.0, 89000.0, 10_000_000.0, "SHORT", "DI1_F26", "RATES")
        assert pnl > 0

    def test_compute_pnl_brl_zero_entry(self):
        """Zero entry price returns 0 P&L."""
        pnl = compute_pnl_brl(0.0, 100.0, 1_000_000.0, "LONG", "X", "EQUITY")
        assert pnl == 0.0

    def test_compute_pnl_usd_conversion(self):
        """USD P&L = BRL P&L / fx_rate."""
        usd = compute_pnl_usd(5_000.0, 5.0)
        assert abs(usd - 1_000.0) < 0.01

    def test_compute_pnl_usd_zero_rate(self):
        """Zero FX rate returns 0."""
        assert compute_pnl_usd(5_000.0, 0.0) == 0.0

    def test_ntnb_yield_to_price_positive(self):
        """NTN-B price should be positive."""
        price = ntnb_yield_to_price(6.0, 6.0, 5.0)
        assert price > 0


# =============================================================================
# open_position tests
# =============================================================================

class TestOpenPosition:
    """Tests for PositionManager.open_position."""

    def test_open_position_basic(self, pm: PositionManager):
        """Open a RATES position, verify returned dict has all required fields."""
        pos = pm.open_position(
            instrument="DI1_F26",
            asset_class="RATES",
            direction="LONG",
            notional_brl=10_000_000.0,
            entry_price=90000.0,
        )
        assert pos["id"] == 1
        assert pos["instrument"] == "DI1_F26"
        assert pos["asset_class"] == "RATES"
        assert pos["direction"] == "LONG"
        assert pos["notional_brl"] == 10_000_000.0
        assert pos["entry_price"] == 90000.0
        assert pos["is_open"] is True
        assert pos["unrealized_pnl_brl"] == 0.0

    def test_open_position_creates_journal_entry(self, pm: PositionManager):
        """Verify journal entry created with OPEN type."""
        pm.open_position(
            instrument="DI1_F26",
            asset_class="RATES",
            direction="LONG",
            notional_brl=10_000_000.0,
            entry_price=90000.0,
        )
        assert len(pm._journal) == 1
        assert pm._journal[0]["entry_type"] == "OPEN"
        assert pm._journal[0]["position_id"] == 1

    def test_open_position_computes_dv01_for_rates(self, pm: PositionManager):
        """Provide rate_pct + business_days, verify entry_dv01 > 0."""
        pos = pm.open_position(
            instrument="DI1_F26",
            asset_class="RATES",
            direction="LONG",
            notional_brl=10_000_000.0,
            entry_price=90000.0,
            rate_pct=10.0,
            business_days=252,
        )
        assert pos["entry_dv01"] is not None
        assert pos["entry_dv01"] > 0

    def test_open_position_computes_delta_for_fx(self, pm: PositionManager):
        """FX position, verify entry_delta computed."""
        pos = pm.open_position(
            instrument="USDBRL",
            asset_class="FX",
            direction="LONG",
            notional_brl=5_000_000.0,
            entry_price=5.0,
            entry_fx_rate=5.0,
        )
        assert pos["entry_delta"] is not None
        assert pos["entry_delta"] > 0
        assert abs(pos["entry_delta"] - 1_000_000.0) < 0.01

    def test_open_position_dual_notional(self, pm: PositionManager):
        """Provide entry_fx_rate, verify notional_usd = notional_brl / fx_rate."""
        pos = pm.open_position(
            instrument="DI1_F26",
            asset_class="RATES",
            direction="LONG",
            notional_brl=10_000_000.0,
            entry_price=90000.0,
            entry_fx_rate=5.0,
        )
        assert pos["notional_usd"] is not None
        assert abs(pos["notional_usd"] - 2_000_000.0) < 0.01

    def test_open_position_records_transaction_cost(self, pm: PositionManager):
        """Verify transaction_cost_brl > 0."""
        pos = pm.open_position(
            instrument="DI1_F26",
            asset_class="RATES",
            direction="LONG",
            notional_brl=10_000_000.0,
            entry_price=90000.0,
        )
        assert pos["transaction_cost_brl"] > 0

    def test_open_position_content_hash(self, pm: PositionManager):
        """Verify journal entry has valid SHA256 hex (64 chars)."""
        pm.open_position(
            instrument="DI1_F26",
            asset_class="RATES",
            direction="LONG",
            notional_brl=10_000_000.0,
            entry_price=90000.0,
        )
        hash_val = pm._journal[0]["content_hash"]
        assert isinstance(hash_val, str)
        assert len(hash_val) == 64
        # Verify it's valid hex
        int(hash_val, 16)

    def test_open_position_strategy_attribution(self, pm: PositionManager):
        """Pass strategy_ids and strategy_weights, verify stored."""
        pos = pm.open_position(
            instrument="DI1_F26",
            asset_class="RATES",
            direction="LONG",
            notional_brl=10_000_000.0,
            entry_price=90000.0,
            strategy_ids=["RATES-01", "RATES-02"],
            strategy_weights={"RATES-01": 0.6, "RATES-02": 0.4},
        )
        assert pos["strategy_ids"] == ["RATES-01", "RATES-02"]
        assert pos["strategy_weights"] == {"RATES-01": 0.6, "RATES-02": 0.4}


# =============================================================================
# close_position tests
# =============================================================================

class TestClosePosition:
    """Tests for PositionManager.close_position."""

    def test_close_position_basic(self, pm: PositionManager):
        """Close an open position, verify is_open=False."""
        pm.open_position(
            instrument="IBOV_FUT",
            asset_class="EQUITY",
            direction="LONG",
            notional_brl=5_000_000.0,
            entry_price=100.0,
        )
        result = pm.close_position(1, close_price=110.0)
        assert result["is_open"] is False
        assert result["close_price"] == 110.0

    def test_close_position_realized_pnl_long(self, pm: PositionManager):
        """LONG position, close higher -> positive P&L."""
        pm.open_position(
            instrument="IBOV_FUT",
            asset_class="EQUITY",
            direction="LONG",
            notional_brl=1_000_000.0,
            entry_price=100.0,
        )
        result = pm.close_position(1, close_price=110.0)
        assert result["realized_pnl_brl"] > 0

    def test_close_position_realized_pnl_short(self, pm: PositionManager):
        """SHORT position, close lower -> positive P&L."""
        pm.open_position(
            instrument="IBOV_FUT",
            asset_class="EQUITY",
            direction="SHORT",
            notional_brl=1_000_000.0,
            entry_price=100.0,
        )
        result = pm.close_position(1, close_price=90.0)
        assert result["realized_pnl_brl"] > 0

    def test_close_position_creates_journal(self, pm: PositionManager):
        """Verify CLOSE journal entry created."""
        pm.open_position(
            instrument="IBOV_FUT",
            asset_class="EQUITY",
            direction="LONG",
            notional_brl=1_000_000.0,
            entry_price=100.0,
        )
        pm.close_position(1, close_price=110.0)
        close_entries = [j for j in pm._journal if j["entry_type"] == "CLOSE"]
        assert len(close_entries) == 1
        assert close_entries[0]["position_id"] == 1

    def test_close_position_not_found(self, pm: PositionManager):
        """Raise ValueError for non-existent id."""
        with pytest.raises(ValueError, match="not found"):
            pm.close_position(999, close_price=100.0)

    def test_close_position_already_closed(self, pm: PositionManager):
        """Raise ValueError for already closed position."""
        pm.open_position(
            instrument="IBOV_FUT",
            asset_class="EQUITY",
            direction="LONG",
            notional_brl=1_000_000.0,
            entry_price=100.0,
        )
        pm.close_position(1, close_price=110.0)
        with pytest.raises(ValueError, match="already closed"):
            pm.close_position(1, close_price=115.0)

    def test_close_position_pnl_usd(self, pm: PositionManager):
        """Verify USD P&L computed when fx_rate provided."""
        pm.open_position(
            instrument="IBOV_FUT",
            asset_class="EQUITY",
            direction="LONG",
            notional_brl=1_000_000.0,
            entry_price=100.0,
            entry_fx_rate=5.0,
        )
        result = pm.close_position(1, close_price=110.0, current_fx_rate=5.0)
        assert result["realized_pnl_usd"] != 0.0
        # USD P&L should be BRL P&L / 5.0
        expected_usd = result["realized_pnl_brl"] / 5.0
        assert abs(result["realized_pnl_usd"] - expected_usd) < 0.01


# =============================================================================
# mark_to_market tests
# =============================================================================

class TestMarkToMarket:
    """Tests for PositionManager.mark_to_market."""

    def test_mtm_updates_open_positions(self, pm_with_positions: PositionManager):
        """Open 3 positions, MTM with price overrides, verify updated."""
        overrides = {
            "DI1_F26": 91000.0,
            "USDBRL": 5.2,
            "CDS_BR_5Y": 140.0,
        }
        updated = pm_with_positions.mark_to_market(
            price_overrides=overrides, current_fx_rate=5.2
        )
        assert len(updated) == 3
        for p in updated:
            assert p["current_price"] in overrides.values()

    def test_mtm_creates_pnl_snapshot(self, pm_with_positions: PositionManager):
        """Verify _pnl_history has entries after MTM."""
        overrides = {"DI1_F26": 91000.0, "USDBRL": 5.2, "CDS_BR_5Y": 140.0}
        pm_with_positions.mark_to_market(price_overrides=overrides, current_fx_rate=5.2)
        assert len(pm_with_positions._pnl_history) == 3

    def test_mtm_skips_closed_positions(self, pm_with_positions: PositionManager):
        """Close one, MTM, verify only open ones updated."""
        pm_with_positions.close_position(2, close_price=5.1, current_fx_rate=5.1)
        overrides = {"DI1_F26": 91000.0, "CDS_BR_5Y": 140.0}
        updated = pm_with_positions.mark_to_market(
            price_overrides=overrides, current_fx_rate=5.2
        )
        assert len(updated) == 2
        instruments = [p["instrument"] for p in updated]
        assert "USDBRL" not in instruments

    def test_mtm_with_manual_override(self, pm: PositionManager):
        """Pass price_overrides, verify override price used."""
        pm.open_position(
            instrument="IBOV_FUT",
            asset_class="EQUITY",
            direction="LONG",
            notional_brl=1_000_000.0,
            entry_price=100.0,
        )
        updated = pm.mark_to_market(
            price_overrides={"IBOV_FUT": 105.0}, current_fx_rate=5.0
        )
        assert len(updated) == 1
        assert updated[0]["current_price"] == 105.0
        assert updated[0]["unrealized_pnl_brl"] > 0

    def test_mtm_rate_position_dv01_recomputed(self, pm: PositionManager):
        """Rates position gets DV01 updated during MTM."""
        pm.open_position(
            instrument="DI1_F26",
            asset_class="RATES",
            direction="LONG",
            notional_brl=10_000_000.0,
            entry_price=90000.0,
            rate_pct=10.0,
            business_days=252,
        )
        updated = pm.mark_to_market(
            price_overrides={"DI1_F26": 91000.0}, current_fx_rate=5.0
        )
        assert len(updated) == 1
        # Verify DV01 snapshot exists in pnl_history
        assert pm._pnl_history[0]["dv01"] > 0


# =============================================================================
# get_book tests
# =============================================================================

class TestGetBook:
    """Tests for PositionManager.get_book."""

    def test_get_book_empty(self, pm: PositionManager):
        """No positions -> summary with zeros."""
        book = pm.get_book()
        assert book["summary"]["open_positions"] == 0
        assert book["summary"]["leverage"] == 0.0
        assert book["summary"]["total_notional_brl"] == 0.0
        assert book["positions"] == []
        assert book["by_asset_class"] == {}

    def test_get_book_with_positions(self, pm_with_positions: PositionManager):
        """Open 3 positions across 2 asset classes, verify structure."""
        book = pm_with_positions.get_book()
        assert book["summary"]["open_positions"] == 3
        assert book["summary"]["aum"] == 100_000_000.0
        assert len(book["positions"]) == 3
        assert len(book["by_asset_class"]) >= 2  # RATES and FX at minimum

    def test_get_book_leverage_calculation(self, pm_with_positions: PositionManager):
        """Verify leverage = total_notional / aum."""
        book = pm_with_positions.get_book()
        expected_leverage = (50_000_000 + 20_000_000 + 10_000_000) / 100_000_000
        assert abs(book["summary"]["leverage"] - expected_leverage) < 0.001

    def test_get_book_by_asset_class_breakdown(self, pm_with_positions: PositionManager):
        """Verify grouping and sums."""
        book = pm_with_positions.get_book()
        assert "RATES" in book["by_asset_class"]
        assert book["by_asset_class"]["RATES"]["count"] == 1
        assert book["by_asset_class"]["RATES"]["notional_brl"] == 50_000_000.0
        assert "FX" in book["by_asset_class"]
        assert book["by_asset_class"]["FX"]["count"] == 1

    def test_get_book_closed_today(self, pm_with_positions: PositionManager):
        """Close a position, verify it appears in closed_today."""
        today = date.today()
        pm_with_positions.close_position(
            2, close_price=5.1, close_date=datetime(today.year, today.month, today.day, 12, 0, 0)
        )
        book = pm_with_positions.get_book(as_of_date=today)
        assert len(book["closed_today"]) == 1
        assert book["closed_today"][0]["instrument"] == "USDBRL"


# =============================================================================
# get_pnl_timeseries tests
# =============================================================================

class TestPnLTimeseries:
    """Tests for PositionManager.get_pnl_timeseries."""

    def test_pnl_timeseries_single_position(self, pm: PositionManager):
        """MTM a position, get timeseries for it."""
        pm.open_position(
            instrument="DI1_F26",
            asset_class="RATES",
            direction="LONG",
            notional_brl=10_000_000.0,
            entry_price=90000.0,
            rate_pct=10.0,
            business_days=252,
        )
        pm.mark_to_market(
            price_overrides={"DI1_F26": 91000.0},
            current_fx_rate=5.0,
            as_of_date=date(2026, 2, 24),
        )
        ts = pm.get_pnl_timeseries(position_id=1)
        assert len(ts) == 1
        assert ts[0]["snapshot_date"] == date(2026, 2, 24)

    def test_pnl_timeseries_portfolio_level(self, pm_with_positions: PositionManager):
        """MTM multiple positions, get aggregate."""
        overrides = {"DI1_F26": 91000.0, "USDBRL": 5.2, "CDS_BR_5Y": 140.0}
        pm_with_positions.mark_to_market(
            price_overrides=overrides,
            current_fx_rate=5.2,
            as_of_date=date(2026, 2, 24),
        )
        ts = pm_with_positions.get_pnl_timeseries()
        assert len(ts) == 1  # One date, aggregated
        assert ts[0]["snapshot_date"] == date(2026, 2, 24)
        assert ts[0]["daily_pnl_brl"] != 0.0


# =============================================================================
# MarkToMarketService tests
# =============================================================================

class TestMarkToMarketService:
    """Tests for MarkToMarketService standalone."""

    def test_get_prices_with_override(self):
        """Manual override takes precedence."""
        svc = MarkToMarketService()
        positions = [{"instrument": "DI1_F26", "entry_price": 90000.0, "entry_date": date(2026, 2, 20)}]
        prices = svc.get_prices_for_positions(
            positions, price_overrides={"DI1_F26": 91000.0}
        )
        assert prices["DI1_F26"]["price"] == 91000.0
        assert prices["DI1_F26"]["source"] == "manual_override"

    def test_get_prices_fallback(self):
        """Fallback to entry_price when no override."""
        svc = MarkToMarketService()
        positions = [{"instrument": "DI1_F26", "entry_price": 90000.0, "entry_date": date(2026, 2, 24)}]
        prices = svc.get_prices_for_positions(positions, as_of_date=date(2026, 2, 24))
        assert prices["DI1_F26"]["price"] == 90000.0
        assert prices["DI1_F26"]["source"] == "entry_price_fallback"

    def test_var_contributions_proportional(self):
        """VaR contributions proportional to notional."""
        svc = MarkToMarketService()
        positions = [
            {"id": 1, "notional_brl": 60_000_000},
            {"id": 2, "notional_brl": 40_000_000},
        ]
        contribs = svc.compute_var_contributions(positions, total_var=1_000_000)
        assert abs(contribs["1"] - 600_000) < 1.0
        assert abs(contribs["2"] - 400_000) < 1.0

    def test_var_contributions_empty(self):
        """Empty positions list returns empty dict."""
        svc = MarkToMarketService()
        assert svc.compute_var_contributions([]) == {}

    def test_compute_dv01_delegation(self):
        """DV01 delegation to pricing module."""
        svc = MarkToMarketService()
        dv01 = svc.compute_dv01("DI1_F26", 10.0, 252, 10_000_000)
        assert dv01 > 0

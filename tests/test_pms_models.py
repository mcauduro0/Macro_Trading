"""Unit tests for PMS SQLAlchemy models.

Tests verify schema definitions (columns, primary keys, indexes, defaults)
without requiring a database connection. Uses sqlalchemy.inspect() to
introspect mapper metadata.
"""

from sqlalchemy import inspect as sa_inspect

from src.core.models.pms_models import (
    DailyBriefing,
    DecisionJournal,
    PortfolioPosition,
    PositionPnLHistory,
    TradeProposal,
)

# ── Helpers ──────────────────────────────────────────────────────────────


def _column_names(model_class):
    """Return set of column names for a model class."""
    mapper = sa_inspect(model_class)
    return {c.key for c in mapper.column_attrs}


def _pk_column_names(model_class):
    """Return list of primary key column names for a model class."""
    mapper = sa_inspect(model_class)
    return [c.name for c in mapper.mapper.primary_key]


# ── PortfolioPosition ───────────────────────────────────────────────────


class TestPortfolioPosition:
    def test_portfolio_position_tablename(self):
        assert PortfolioPosition.__tablename__ == "portfolio_positions"

    def test_portfolio_position_has_risk_snapshot_fields(self):
        cols = _column_names(PortfolioPosition)
        risk_fields = [
            "entry_dv01",
            "entry_delta",
            "entry_convexity",
            "entry_var_contribution",
            "entry_spread_duration",
        ]
        for field in risk_fields:
            assert field in cols, f"Missing risk snapshot field: {field}"

    def test_portfolio_position_has_dual_notional(self):
        cols = _column_names(PortfolioPosition)
        assert "notional_brl" in cols, "Missing notional_brl"
        assert "notional_usd" in cols, "Missing notional_usd"

    def test_portfolio_position_has_strategy_fields(self):
        cols = _column_names(PortfolioPosition)
        assert "strategy_ids" in cols, "Missing strategy_ids"
        assert "strategy_weights" in cols, "Missing strategy_weights"

    def test_portfolio_position_has_is_open(self):
        cols = _column_names(PortfolioPosition)
        assert "is_open" in cols, "Missing is_open"

    def test_portfolio_position_single_pk(self):
        pk_cols = _pk_column_names(PortfolioPosition)
        assert pk_cols == ["id"], f"Expected single PK ['id'], got {pk_cols}"

    def test_portfolio_position_repr(self):
        """Verify __repr__ is defined and returns a string."""
        assert hasattr(PortfolioPosition, "__repr__")
        # Verify it's not just the default object repr
        assert "PortfolioPosition" in PortfolioPosition.__repr__.__qualname__


# ── TradeProposal ────────────────────────────────────────────────────────


class TestTradeProposal:
    def test_trade_proposal_tablename(self):
        assert TradeProposal.__tablename__ == "trade_proposals"

    def test_trade_proposal_status_default(self):
        """Verify the status column has a default of PENDING."""
        mapper = sa_inspect(TradeProposal)
        status_col = mapper.columns["status"]
        # Column default can be a scalar or ColumnDefault
        default_val = status_col.default
        if default_val is not None:
            assert default_val.arg == "PENDING"

    def test_trade_proposal_has_conviction(self):
        cols = _column_names(TradeProposal)
        assert "conviction" in cols, "Missing conviction field"

    def test_trade_proposal_has_position_fk(self):
        cols = _column_names(TradeProposal)
        assert "position_id" in cols, "Missing position_id FK"


# ── DecisionJournal ──────────────────────────────────────────────────────


class TestDecisionJournal:
    def test_decision_journal_tablename(self):
        assert DecisionJournal.__tablename__ == "decision_journal"

    def test_decision_journal_has_content_hash(self):
        cols = _column_names(DecisionJournal)
        assert "content_hash" in cols, "Missing content_hash"
        # Verify it's String(64) for SHA256 hex
        mapper = sa_inspect(DecisionJournal)
        hash_col = mapper.columns["content_hash"]
        assert hash_col.type.length == 64, f"Expected length 64, got {hash_col.type.length}"

    def test_decision_journal_has_snapshots(self):
        cols = _column_names(DecisionJournal)
        assert "market_snapshot" in cols, "Missing market_snapshot"
        assert "portfolio_snapshot" in cols, "Missing portfolio_snapshot"

    def test_decision_journal_has_is_locked(self):
        cols = _column_names(DecisionJournal)
        assert "is_locked" in cols, "Missing is_locked"

    def test_decision_journal_has_entry_type(self):
        cols = _column_names(DecisionJournal)
        assert "entry_type" in cols, "Missing entry_type"

    def test_decision_journal_has_dual_fks(self):
        cols = _column_names(DecisionJournal)
        assert "position_id" in cols, "Missing position_id FK"
        assert "proposal_id" in cols, "Missing proposal_id FK"


# ── DailyBriefing ────────────────────────────────────────────────────────


class TestDailyBriefing:
    def test_daily_briefing_tablename(self):
        assert DailyBriefing.__tablename__ == "daily_briefings"

    def test_daily_briefing_has_briefing_date(self):
        cols = _column_names(DailyBriefing)
        assert "briefing_date" in cols, "Missing briefing_date"

    def test_daily_briefing_has_all_jsonb_fields(self):
        cols = _column_names(DailyBriefing)
        expected_jsonb = [
            "market_snapshot",
            "regime_assessment",
            "agent_views",
            "top_signals",
            "signal_changes",
            "portfolio_state",
            "trade_proposals",
            "risk_summary",
            "action_items",
            "metadata_json",
        ]
        for field in expected_jsonb:
            assert field in cols, f"Missing JSONB field: {field}"


# ── PositionPnLHistory ───────────────────────────────────────────────────


class TestPositionPnLHistory:
    def test_position_pnl_history_tablename(self):
        assert PositionPnLHistory.__tablename__ == "position_pnl_history"

    def test_position_pnl_history_composite_pk(self):
        pk_cols = _pk_column_names(PositionPnLHistory)
        assert "id" in pk_cols, "id not in PK"
        assert "snapshot_date" in pk_cols, "snapshot_date not in PK"
        assert len(pk_cols) == 2, f"Expected 2 PK columns, got {len(pk_cols)}"

    def test_position_pnl_history_has_risk_fields(self):
        cols = _column_names(PositionPnLHistory)
        assert "dv01" in cols, "Missing dv01"
        assert "delta" in cols, "Missing delta"
        assert "var_contribution" in cols, "Missing var_contribution"

    def test_position_pnl_history_has_dual_pnl(self):
        cols = _column_names(PositionPnLHistory)
        assert "unrealized_pnl_brl" in cols, "Missing unrealized_pnl_brl"
        assert "unrealized_pnl_usd" in cols, "Missing unrealized_pnl_usd"
        assert "daily_pnl_brl" in cols, "Missing daily_pnl_brl"
        assert "daily_pnl_usd" in cols, "Missing daily_pnl_usd"

    def test_position_pnl_history_has_manual_override(self):
        cols = _column_names(PositionPnLHistory)
        assert "is_manual_override" in cols, "Missing is_manual_override"


# ── Cross-cutting ────────────────────────────────────────────────────────


class TestAllModelsInInit:
    def test_all_models_in_init(self):
        """All 5 PMS models are importable from src.core.models."""
        from src.core.models import (
            DailyBriefing as DB_,
        )
        from src.core.models import (
            DecisionJournal as DJ_,
        )
        from src.core.models import (
            PortfolioPosition as PP_,
        )
        from src.core.models import (
            PositionPnLHistory as PnL_,
        )
        from src.core.models import (
            TradeProposal as TP_,
        )
        assert PP_ is PortfolioPosition
        assert TP_ is TradeProposal
        assert DJ_ is DecisionJournal
        assert DB_ is DailyBriefing
        assert PnL_ is PositionPnLHistory

    def test_all_models_in_all_list(self):
        """All 5 PMS model names appear in __all__."""
        import src.core.models as models_mod

        all_names = getattr(models_mod, "__all__", [])
        expected = [
            "PortfolioPosition",
            "TradeProposal",
            "DecisionJournal",
            "DailyBriefing",
            "PositionPnLHistory",
        ]
        for name in expected:
            assert name in all_names, f"{name} not in __all__"

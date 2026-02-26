#!/usr/bin/env python3
"""Comprehensive v4.0 verification script.

Validates all major components of the Macro Trading v4.0 system,
covering v1 (Data Infrastructure) through v4 (PMS) in 29 checks
across 6 component groups.

Outputs a formatted PASS/FAIL table with box-drawing characters
and color-coded status.

Usage:
    python scripts/verify_phase3.py

Exit code: 0 if all checks pass, 1 if any fail.
"""

from __future__ import annotations

import os
import sys
from collections import namedtuple
from pathlib import Path

# Ensure project root is on sys.path for standalone execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

CheckResult = namedtuple("CheckResult", ["name", "status", "detail"])


# ---------------------------------------------------------------------------
# ANSI color helpers
# ---------------------------------------------------------------------------
def _supports_color() -> bool:
    """Detect whether the terminal supports ANSI color codes."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


USE_COLOR = _supports_color()


def _green(text: str) -> str:
    return f"\033[92m{text}\033[0m" if USE_COLOR else text


def _red(text: str) -> str:
    return f"\033[91m{text}\033[0m" if USE_COLOR else text


def _bold(text: str) -> str:
    return f"\033[1m{text}\033[0m" if USE_COLOR else text


# ===========================================================================
# Group 1: v1.0 Data Infrastructure (4 checks)
# ===========================================================================

def verify_orm_models() -> CheckResult:
    """Check 1: ORM models from src.core.models -- should have 10+ models."""
    try:
        from src.core.models import (
            Instrument, SeriesMetadata, DataSource,
            MarketData, MacroSeries, CurveData, FlowData,
            FiscalData, VolSurface, Signal,
            AgentReportRecord, BacktestResultRecord,
            StrategyStateRecord, NlpDocumentRecord, PortfolioStateRecord,
            PortfolioPosition, TradeProposal, DecisionJournal,
            DailyBriefing, PositionPnLHistory,
        )
        models = [
            Instrument, SeriesMetadata, DataSource,
            MarketData, MacroSeries, CurveData, FlowData,
            FiscalData, VolSurface, Signal,
            AgentReportRecord, BacktestResultRecord,
            StrategyStateRecord, NlpDocumentRecord, PortfolioStateRecord,
            PortfolioPosition, TradeProposal, DecisionJournal,
            DailyBriefing, PositionPnLHistory,
        ]
        count = len(models)
        if count >= 10:
            return CheckResult("ORM Models (10+ classes)", "PASS", f"{count} models imported")
        return CheckResult("ORM Models (10+ classes)", "FAIL", f"Only {count} models")
    except Exception as exc:
        return CheckResult("ORM Models (10+ classes)", "FAIL", str(exc)[:60])


def verify_connectors() -> CheckResult:
    """Check 2: 11 connectors importable from src.connectors."""
    try:
        from src.connectors import (
            BcbSgsConnector, FredConnector, YahooFinanceConnector,
            BcbPtaxConnector, B3MarketDataConnector, BcbFocusConnector,
            BcbFxFlowConnector, CftcCotConnector, IbgeSidraConnector,
            StnFiscalConnector, TreasuryGovConnector,
        )
        connectors = [
            BcbSgsConnector, FredConnector, YahooFinanceConnector,
            BcbPtaxConnector, B3MarketDataConnector, BcbFocusConnector,
            BcbFxFlowConnector, CftcCotConnector, IbgeSidraConnector,
            StnFiscalConnector, TreasuryGovConnector,
        ]
        count = len(connectors)
        if count >= 11:
            return CheckResult("Connectors (11 sources)", "PASS", f"{count} connectors")
        return CheckResult("Connectors (11 sources)", "FAIL", f"Only {count}")
    except Exception as exc:
        return CheckResult("Connectors (11 sources)", "FAIL", str(exc)[:60])


def verify_transforms() -> CheckResult:
    """Check 3: Transform modules (curves, returns, macro)."""
    try:
        from src.transforms import curves, returns, macro
        modules = [curves, returns, macro]
        names = [m.__name__.split(".")[-1] for m in modules]
        return CheckResult("Transforms (curve/returns/macro)", "PASS", ", ".join(names))
    except Exception as exc:
        return CheckResult("Transforms (curve/returns/macro)", "FAIL", str(exc)[:60])


def verify_api_health() -> CheckResult:
    """Check 4: FastAPI app importable, /health route exists."""
    try:
        from src.api.main import app
        routes = set()
        for route in app.routes:
            if hasattr(route, "path"):
                routes.add(route.path)
        if "/health" in routes:
            return CheckResult("API /health endpoint", "PASS", "/health route registered")
        return CheckResult("API /health endpoint", "FAIL", "Missing /health route")
    except Exception as exc:
        return CheckResult("API /health endpoint", "FAIL", str(exc)[:60])


# ===========================================================================
# Group 2: v2.0 Agents & Strategies (4 checks)
# ===========================================================================

def verify_agents() -> CheckResult:
    """Check 5: AgentRegistry defines 5 agents in EXECUTION_ORDER."""
    try:
        from src.agents.registry import AgentRegistry
        expected = {"inflation_agent", "monetary_agent", "fiscal_agent",
                    "fx_agent", "cross_asset_agent"}
        execution_order = set(AgentRegistry.EXECUTION_ORDER)
        if expected.issubset(execution_order):
            return CheckResult("Agents (5 in EXECUTION_ORDER)", "PASS",
                               f"{len(execution_order)} agents")
        missing = expected - execution_order
        return CheckResult("Agents (5 in EXECUTION_ORDER)", "FAIL",
                           f"Missing: {missing}")
    except Exception as exc:
        return CheckResult("Agents (5 in EXECUTION_ORDER)", "FAIL", str(exc)[:60])


def verify_strategy_registry() -> CheckResult:
    """Check 6: StrategyRegistry has >= 24 strategies registered."""
    try:
        from src.strategies.registry import StrategyRegistry
        all_strats = StrategyRegistry.list_all()
        count = len(all_strats)
        if count >= 24:
            return CheckResult("StrategyRegistry (24+ strategies)", "PASS",
                               f"{count} registered")
        return CheckResult("StrategyRegistry (24+ strategies)", "FAIL",
                           f"Only {count} registered")
    except Exception as exc:
        return CheckResult("StrategyRegistry (24+ strategies)", "FAIL", str(exc)[:60])


def verify_backtesting() -> CheckResult:
    """Check 7: BacktestEngine has run and run_portfolio methods."""
    try:
        from src.backtesting.engine import BacktestEngine
        engine = BacktestEngine.__new__(BacktestEngine)
        has_run = hasattr(engine, "run")
        has_portfolio = hasattr(engine, "run_portfolio")
        if has_run and has_portfolio:
            return CheckResult("BacktestEngine (run + portfolio)", "PASS",
                               "run & run_portfolio present")
        missing = []
        if not has_run:
            missing.append("run")
        if not has_portfolio:
            missing.append("run_portfolio")
        return CheckResult("BacktestEngine (run + portfolio)", "FAIL",
                           f"Missing: {', '.join(missing)}")
    except Exception as exc:
        return CheckResult("BacktestEngine (run + portfolio)", "FAIL", str(exc)[:60])


def verify_signal_aggregation() -> CheckResult:
    """Check 8: SignalAggregatorV2 has aggregate method."""
    try:
        from src.portfolio.signal_aggregator_v2 import SignalAggregatorV2
        agg = SignalAggregatorV2()
        if hasattr(agg, "aggregate"):
            return CheckResult("SignalAggregatorV2 (aggregate)", "PASS",
                               "aggregate method present")
        return CheckResult("SignalAggregatorV2 (aggregate)", "FAIL",
                           "Missing aggregate method")
    except Exception as exc:
        return CheckResult("SignalAggregatorV2 (aggregate)", "FAIL", str(exc)[:60])


# ===========================================================================
# Group 3: v3.0 Risk, Portfolio, Orchestration (5 checks)
# ===========================================================================

def verify_var_calculator() -> CheckResult:
    """Check 9: VaRCalculator computes historical VaR on sample data."""
    try:
        import numpy as np
        from src.risk.var_calculator import VaRCalculator
        calc = VaRCalculator()
        rng = np.random.default_rng(seed=42)
        returns = rng.normal(0.0, 0.01, size=252)
        result = calc.calculate(returns, method="historical")
        if hasattr(result, "var_95") and result.var_95 < 0:
            return CheckResult("VaRCalculator (historical)", "PASS",
                               f"VaR95={result.var_95:.6f}")
        return CheckResult("VaRCalculator (historical)", "FAIL",
                           "Invalid VaR result")
    except Exception as exc:
        return CheckResult("VaRCalculator (historical)", "FAIL", str(exc)[:60])


def verify_stress_tester() -> CheckResult:
    """Check 10: StressTester has 6+ scenarios."""
    try:
        from src.risk.stress_tester import StressTester
        tester = StressTester()
        scenarios = (getattr(tester, "DEFAULT_SCENARIOS", None)
                     or getattr(tester, "scenarios", None))
        if scenarios is None:
            positions = {"USDBRL": 100_000.0}
            results = tester.run_all(positions, 1_000_000.0)
            count = len(results)
        else:
            count = len(scenarios)
        if count >= 6:
            return CheckResult("StressTester (6+ scenarios)", "PASS",
                               f"{count} scenarios")
        return CheckResult("StressTester (6+ scenarios)", "FAIL",
                           f"Only {count} scenarios")
    except Exception as exc:
        return CheckResult("StressTester (6+ scenarios)", "FAIL", str(exc)[:60])


def verify_black_litterman() -> CheckResult:
    """Check 11: BlackLitterman has optimize method."""
    try:
        from src.portfolio.black_litterman import BlackLitterman
        bl = BlackLitterman()
        if hasattr(bl, "optimize"):
            return CheckResult("Black-Litterman (optimize)", "PASS",
                               "optimize method present")
        return CheckResult("Black-Litterman (optimize)", "FAIL",
                           "Missing optimize method")
    except Exception as exc:
        return CheckResult("Black-Litterman (optimize)", "FAIL", str(exc)[:60])


def verify_dagster_assets() -> CheckResult:
    """Check 12: @asset decorators in src/orchestration/*.py >= 26."""
    try:
        assets_dir = PROJECT_ROOT / "src" / "orchestration"
        if not assets_dir.exists():
            return CheckResult("Dagster Assets (26+ defs)", "FAIL",
                               "Directory not found")
        asset_count = 0
        for py_file in assets_dir.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            content = py_file.read_text()
            asset_count += content.count("@asset")
        if asset_count >= 26:
            return CheckResult("Dagster Assets (26+ defs)", "PASS",
                               f"{asset_count} @asset decorators")
        return CheckResult("Dagster Assets (26+ defs)", "FAIL",
                           f"Only {asset_count} @asset decorators")
    except Exception as exc:
        return CheckResult("Dagster Assets (26+ defs)", "FAIL", str(exc)[:60])


def verify_grafana_dashboards() -> CheckResult:
    """Check 13: 4+ JSON files in monitoring/grafana/dashboards/."""
    try:
        dashboards_dir = PROJECT_ROOT / "monitoring" / "grafana" / "dashboards"
        if not dashboards_dir.exists():
            return CheckResult("Grafana Dashboards (4 JSON)", "FAIL",
                               "Directory not found")
        json_files = list(dashboards_dir.glob("*.json"))
        count = len(json_files)
        if count >= 4:
            return CheckResult("Grafana Dashboards (4 JSON)", "PASS",
                               f"{count} dashboards")
        return CheckResult("Grafana Dashboards (4 JSON)", "FAIL",
                           f"Only {count} JSON files")
    except Exception as exc:
        return CheckResult("Grafana Dashboards (4 JSON)", "FAIL", str(exc)[:60])


# ===========================================================================
# Group 4: v4.0 PMS Services (6 checks)
# ===========================================================================

def verify_position_manager() -> CheckResult:
    """Check 14: PositionManager has open/close/MTM/book methods."""
    try:
        from src.pms import PositionManager
        pm = PositionManager()
        required = ["open_position", "close_position", "mark_to_market", "get_book"]
        present = [m for m in required if hasattr(pm, m)]
        missing = [m for m in required if not hasattr(pm, m)]
        if not missing:
            return CheckResult("PositionManager (4 methods)", "PASS",
                               ", ".join(present))
        return CheckResult("PositionManager (4 methods)", "FAIL",
                           f"Missing: {', '.join(missing)}")
    except Exception as exc:
        return CheckResult("PositionManager (4 methods)", "FAIL", str(exc)[:60])


def verify_trade_workflow() -> CheckResult:
    """Check 15: TradeWorkflowService has generate/approve/reject methods."""
    try:
        from src.pms import TradeWorkflowService
        tw = TradeWorkflowService()
        required = ["generate_proposals_from_signals", "approve_proposal",
                     "reject_proposal"]
        present = [m for m in required if hasattr(tw, m)]
        missing = [m for m in required if not hasattr(tw, m)]
        if not missing:
            return CheckResult("TradeWorkflowService (3 methods)", "PASS",
                               "generate/approve/reject")
        return CheckResult("TradeWorkflowService (3 methods)", "FAIL",
                           f"Missing: {', '.join(missing)}")
    except Exception as exc:
        return CheckResult("TradeWorkflowService (3 methods)", "FAIL", str(exc)[:60])


def verify_morning_pack() -> CheckResult:
    """Check 16: MorningPackService has generate method."""
    try:
        from src.pms import MorningPackService
        ms = MorningPackService()
        if hasattr(ms, "generate"):
            return CheckResult("MorningPackService (generate)", "PASS",
                               "generate method present")
        return CheckResult("MorningPackService (generate)", "FAIL",
                           "Missing generate method")
    except Exception as exc:
        return CheckResult("MorningPackService (generate)", "FAIL", str(exc)[:60])


def verify_risk_monitor() -> CheckResult:
    """Check 17: RiskMonitorService has compute_live_risk method."""
    try:
        from src.pms import RiskMonitorService
        rm = RiskMonitorService()
        if hasattr(rm, "compute_live_risk"):
            return CheckResult("RiskMonitorService (compute_live_risk)", "PASS",
                               "compute_live_risk present")
        return CheckResult("RiskMonitorService (compute_live_risk)", "FAIL",
                           "Missing compute_live_risk method")
    except Exception as exc:
        return CheckResult("RiskMonitorService (compute_live_risk)", "FAIL",
                           str(exc)[:60])


def verify_attribution() -> CheckResult:
    """Check 18: PerformanceAttributionEngine has compute_attribution."""
    try:
        from src.pms import PerformanceAttributionEngine
        pa = PerformanceAttributionEngine()
        if hasattr(pa, "compute_attribution"):
            return CheckResult("PerformanceAttribution (compute)", "PASS",
                               "compute_attribution present")
        return CheckResult("PerformanceAttribution (compute)", "FAIL",
                           "Missing compute_attribution method")
    except Exception as exc:
        return CheckResult("PerformanceAttribution (compute)", "FAIL",
                           str(exc)[:60])


def verify_pms_cache() -> CheckResult:
    """Check 19: PMSCache has get_book, set_book, invalidate methods."""
    try:
        from src.cache.pms_cache import PMSCache
        # PMSCache requires a redis client -- check class has the methods
        required = ["get_book", "set_book", "invalidate_portfolio_data"]
        present = [m for m in required if hasattr(PMSCache, m)]
        missing = [m for m in required if not hasattr(PMSCache, m)]
        if not missing:
            return CheckResult("PMSCache (3 key methods)", "PASS",
                               "get/set_book + invalidate")
        return CheckResult("PMSCache (3 key methods)", "FAIL",
                           f"Missing: {', '.join(missing)}")
    except Exception as exc:
        return CheckResult("PMSCache (3 key methods)", "FAIL", str(exc)[:60])


# ===========================================================================
# Group 5: v4.0 PMS API & Frontend (5 checks)
# ===========================================================================

def verify_pms_api_routes() -> CheckResult:
    """Check 20: 6 PMS routers registered, >= 20 PMS routes."""
    try:
        from src.api.main import app
        pms_routes = set()
        for route in app.routes:
            path = getattr(route, "path", "")
            if "/pms/" in path:
                pms_routes.add(path)
        count = len(pms_routes)
        if count >= 20:
            return CheckResult("PMS API Routes (6 routers, 20+)", "PASS",
                               f"{count} PMS routes")
        return CheckResult("PMS API Routes (6 routers, 20+)", "FAIL",
                           f"Only {count} PMS routes")
    except Exception as exc:
        return CheckResult("PMS API Routes (6 routers, 20+)", "FAIL",
                           str(exc)[:60])


def verify_pms_frontend_pages() -> CheckResult:
    """Check 21: 8 PMS page JSX files exist."""
    try:
        pages_dir = (PROJECT_ROOT / "src" / "api" / "static" / "js"
                     / "pms" / "pages")
        expected = [
            "MorningPackPage.jsx",
            "PositionBookPage.jsx",
            "TradeBlotterPage.jsx",
            "RiskMonitorPage.jsx",
            "PerformanceAttributionPage.jsx",
            "DecisionJournalPage.jsx",
            "AgentIntelPage.jsx",
            "ComplianceAuditPage.jsx",
        ]
        found = [f for f in expected if (pages_dir / f).exists()]
        missing = [f for f in expected if not (pages_dir / f).exists()]
        if not missing:
            return CheckResult("PMS Frontend Pages (8 JSX)", "PASS",
                               f"{len(found)} pages")
        return CheckResult("PMS Frontend Pages (8 JSX)", "FAIL",
                           f"Missing: {', '.join(missing)[:50]}")
    except Exception as exc:
        return CheckResult("PMS Frontend Pages (8 JSX)", "FAIL", str(exc)[:60])


def verify_pms_design_system() -> CheckResult:
    """Check 22: theme.jsx and components.jsx exist."""
    try:
        pms_dir = PROJECT_ROOT / "src" / "api" / "static" / "js" / "pms"
        theme = (pms_dir / "theme.jsx").exists()
        components = (pms_dir / "components.jsx").exists()
        if theme and components:
            return CheckResult("PMS Design System (theme+components)", "PASS",
                               "theme.jsx + components.jsx")
        missing = []
        if not theme:
            missing.append("theme.jsx")
        if not components:
            missing.append("components.jsx")
        return CheckResult("PMS Design System (theme+components)", "FAIL",
                           f"Missing: {', '.join(missing)}")
    except Exception as exc:
        return CheckResult("PMS Design System (theme+components)", "FAIL",
                           str(exc)[:60])


def verify_dashboard_html() -> CheckResult:
    """Check 23: dashboard.html contains text/babel."""
    try:
        html_path = PROJECT_ROOT / "src" / "api" / "static" / "dashboard.html"
        if not html_path.exists():
            return CheckResult("Dashboard HTML (text/babel)", "FAIL",
                               "File not found")
        content = html_path.read_text()
        if "text/babel" in content:
            return CheckResult("Dashboard HTML (text/babel)", "PASS",
                               "Contains text/babel")
        return CheckResult("Dashboard HTML (text/babel)", "FAIL",
                           "Missing text/babel")
    except Exception as exc:
        return CheckResult("Dashboard HTML (text/babel)", "FAIL", str(exc)[:60])


def verify_websocket_channels() -> CheckResult:
    """Check 24: ConnectionManager has connect and broadcast."""
    try:
        from src.api.routes.websocket_api import ConnectionManager
        mgr = ConnectionManager()
        assert mgr is not None, "ConnectionManager instantiation failed"
        has_connect = hasattr(mgr, "connect")
        has_broadcast = hasattr(mgr, "broadcast")
        if has_connect and has_broadcast:
            return CheckResult("WebSocket ConnectionManager", "PASS",
                               "connect + broadcast present")
        missing = []
        if not has_connect:
            missing.append("connect")
        if not has_broadcast:
            missing.append("broadcast")
        return CheckResult("WebSocket ConnectionManager", "FAIL",
                           f"Missing: {', '.join(missing)}")
    except Exception as exc:
        return CheckResult("WebSocket ConnectionManager", "FAIL", str(exc)[:60])


# ===========================================================================
# Group 6: v4.0 PMS Pipeline & Ops (5 checks)
# ===========================================================================

def verify_dagster_pms_assets() -> CheckResult:
    """Check 25: 4 PMS assets importable from src.orchestration.assets_pms."""
    try:
        from src.orchestration.assets_pms import (
            pms_mark_to_market,
            pms_trade_proposals,
            pms_morning_pack,
            pms_performance_attribution,
        )
        assets = [pms_mark_to_market, pms_trade_proposals,
                  pms_morning_pack, pms_performance_attribution]
        count = len(assets)
        if count == 4:
            return CheckResult("Dagster PMS Assets (4)", "PASS",
                               "MTM/proposals/pack/attribution")
        return CheckResult("Dagster PMS Assets (4)", "FAIL",
                           f"Only {count} imported")
    except Exception as exc:
        return CheckResult("Dagster PMS Assets (4)", "FAIL", str(exc)[:60])


def verify_dagster_pms_schedules() -> CheckResult:
    """Check 26: Dagster defs have 3 schedules registered."""
    try:
        from src.orchestration.definitions import defs
        schedules = defs.get_schedule_defs()
        count = len(schedules)
        names = [s.name for s in schedules]
        if count >= 3:
            return CheckResult("Dagster Schedules (3+)", "PASS",
                               f"{count}: {', '.join(names)[:40]}")
        return CheckResult("Dagster Schedules (3+)", "FAIL",
                           f"Only {count} schedules")
    except Exception as exc:
        return CheckResult("Dagster Schedules (3+)", "FAIL", str(exc)[:60])


def verify_golive_docs() -> CheckResult:
    """Check 27: Go-live docs exist (checklist, runbook, DR playbook)."""
    try:
        docs_dir = PROJECT_ROOT / "docs"
        expected = [
            "GOLIVE_CHECKLIST.md",
            "OPERATIONAL_RUNBOOK.md",
            "DR_PLAYBOOK.md",
        ]
        found = [f for f in expected if (docs_dir / f).exists()]
        missing = [f for f in expected if not (docs_dir / f).exists()]
        if not missing:
            return CheckResult("Go-Live Docs (3 files)", "PASS",
                               ", ".join(found))
        return CheckResult("Go-Live Docs (3 files)", "FAIL",
                           f"Missing: {', '.join(missing)}")
    except Exception as exc:
        return CheckResult("Go-Live Docs (3 files)", "FAIL", str(exc)[:60])


def verify_backup_scripts() -> CheckResult:
    """Check 28: backup.sh and restore.sh exist and are executable."""
    try:
        scripts_dir = PROJECT_ROOT / "scripts"
        backup = scripts_dir / "backup.sh"
        restore = scripts_dir / "restore.sh"
        issues = []
        if not backup.exists():
            issues.append("backup.sh missing")
        elif not os.access(backup, os.X_OK):
            issues.append("backup.sh not executable")
        if not restore.exists():
            issues.append("restore.sh missing")
        elif not os.access(restore, os.X_OK):
            issues.append("restore.sh not executable")
        if not issues:
            return CheckResult("Backup Scripts (backup+restore)", "PASS",
                               "backup.sh + restore.sh executable")
        return CheckResult("Backup Scripts (backup+restore)", "FAIL",
                           "; ".join(issues)[:60])
    except Exception as exc:
        return CheckResult("Backup Scripts (backup+restore)", "FAIL",
                           str(exc)[:60])


def verify_alert_rules() -> CheckResult:
    """Check 29: AlertManager has 10+ rules."""
    try:
        from src.monitoring.alert_manager import AlertManager
        mgr = AlertManager()
        rules = (getattr(mgr, "rules", None) or getattr(mgr, "_rules", None)
                 or getattr(mgr, "default_rules", None)
                 or getattr(mgr, "alert_rules", None))
        if rules is not None:
            count = len(rules)
            if count >= 10:
                return CheckResult("Alert Rules (10+ default)", "PASS",
                                   f"{count} rules")
            return CheckResult("Alert Rules (10+ default)", "FAIL",
                               f"Only {count} rules")
        return CheckResult("Alert Rules (10+ default)", "FAIL",
                           "No rules attribute found")
    except Exception as exc:
        return CheckResult("Alert Rules (10+ default)", "FAIL", str(exc)[:60])


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
ALL_CHECKS = [
    # Group 1: v1.0 Data Infrastructure (4)
    verify_orm_models,
    verify_connectors,
    verify_transforms,
    verify_api_health,
    # Group 2: v2.0 Agents & Strategies (4)
    verify_agents,
    verify_strategy_registry,
    verify_backtesting,
    verify_signal_aggregation,
    # Group 3: v3.0 Risk, Portfolio, Orchestration (5)
    verify_var_calculator,
    verify_stress_tester,
    verify_black_litterman,
    verify_dagster_assets,
    verify_grafana_dashboards,
    # Group 4: v4.0 PMS Services (6)
    verify_position_manager,
    verify_trade_workflow,
    verify_morning_pack,
    verify_risk_monitor,
    verify_attribution,
    verify_pms_cache,
    # Group 5: v4.0 PMS API & Frontend (5)
    verify_pms_api_routes,
    verify_pms_frontend_pages,
    verify_pms_design_system,
    verify_dashboard_html,
    verify_websocket_channels,
    # Group 6: v4.0 PMS Pipeline & Ops (5)
    verify_dagster_pms_assets,
    verify_dagster_pms_schedules,
    verify_golive_docs,
    verify_backup_scripts,
    verify_alert_rules,
]


def run_all_checks() -> list[CheckResult]:
    """Execute all verification checks and return results."""
    results = []
    for check_fn in ALL_CHECKS:
        try:
            result = check_fn()
        except Exception as exc:
            result = CheckResult(check_fn.__name__, "FAIL", str(exc)[:60])
        results.append(result)
    return results


def print_table(results: list[CheckResult]) -> None:
    """Print a formatted table with box-drawing characters."""
    # Column widths
    col1 = max(len(r.name) for r in results) + 2
    col2 = 8  # " PASS " or " FAIL "
    col3 = max(len(r.detail) for r in results) + 2

    # Header
    print()
    print(_bold("  Macro Trading v4.0 -- Full System Verification (v1-v4)"))
    print()
    print(f"  {'='*(col1 + col2 + col3 + 8)}")
    print(f"  | {'Component':<{col1}} | {'Status':^{col2}} | {'Detail':<{col3}} |")
    print(f"  |{'-'*(col1 + 2)}|{'-'*(col2 + 2)}|{'-'*(col3 + 2)}|")

    # Group labels
    group_boundaries = {
        0: "v1.0 Data Infrastructure",
        4: "v2.0 Agents & Strategies",
        8: "v3.0 Risk, Portfolio, Orchestration",
        13: "v4.0 PMS Services",
        19: "v4.0 PMS API & Frontend",
        24: "v4.0 PMS Pipeline & Ops",
    }

    for i, r in enumerate(results):
        if i in group_boundaries:
            label = group_boundaries[i]
            print(f"  |{'-'*(col1 + 2)}|{'-'*(col2 + 2)}|{'-'*(col3 + 2)}|")
            pad = col1 + col2 + col3 + 6
            print(f"  | {_bold(label):<{pad}} |")
            print(f"  |{'-'*(col1 + 2)}|{'-'*(col2 + 2)}|{'-'*(col3 + 2)}|")

        if r.status == "PASS":
            status_str = _green(f"{'PASS':^{col2}}")
        else:
            status_str = _red(f"{'FAIL':^{col2}}")

        print(f"  | {r.name:<{col1}} | {status_str} | {r.detail:<{col3}} |")

    print(f"  {'='*(col1 + col2 + col3 + 8)}")

    # Summary
    passed = sum(1 for r in results if r.status == "PASS")
    total = len(results)
    summary = f"{passed}/{total} checks passed"
    if passed == total:
        print(f"\n  {_green(_bold(summary))}")
    else:
        failed = total - passed
        print(f"\n  {_red(_bold(summary))} ({failed} failed)")
    print()


def main() -> int:
    """Run all checks, print table, return exit code."""
    results = run_all_checks()
    print_table(results)
    return 0 if all(r.status == "PASS" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())

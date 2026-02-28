"""FastAPI application entry-point for the Macro Trading API.

Configures CORS, lifespan startup/shutdown, and mounts all route modules.
Run with:  uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text

from src.api.routes import (
    agents,
    curves,
    dashboard,
    flows,
    health,
    macro,
    market_data,
    portfolio_api,
    reports,
    risk_api,
    signals,
    strategies_api,
)
from src.api.routes.backtest_api import router as backtest_router
from src.api.routes.monitoring_api import router as monitoring_router
from src.api.routes.pms_attribution import router as pms_attribution_router
from src.api.routes.pms_briefing import router as pms_briefing_router
from src.api.routes.pms_journal import router as pms_journal_router
from src.api.routes.pms_pipeline import router as pms_pipeline_router
from src.api.routes.pms_portfolio import router as pms_portfolio_router
from src.api.routes.pms_risk import router as pms_risk_router
from src.api.routes.pms_trades import router as pms_trades_router
from src.api.routes.reports_api import router as reports_api_router
from src.api.routes.websocket_api import router as websocket_router
from src.core.config import settings
from src.core.database import async_engine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan -- run once at startup / shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Test the database connection on startup; dispose engine on shutdown."""
    # Startup
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection verified")
    except Exception as exc:
        logger.error("Database connection failed: %s", exc)

    # Register all analytical agents at startup
    try:
        from src.agents.cross_asset_agent import CrossAssetAgent
        from src.agents.fiscal_agent import FiscalAgent
        from src.agents.fx_agent import FxEquilibriumAgent
        from src.agents.inflation_agent import InflationAgent
        from src.agents.monetary_agent import MonetaryPolicyAgent
        from src.agents.registry import AgentRegistry

        for agent_cls in [
            InflationAgent,
            MonetaryPolicyAgent,
            FiscalAgent,
            FxEquilibriumAgent,
            CrossAssetAgent,
        ]:
            try:
                AgentRegistry.register(agent_cls())
            except ValueError:
                pass  # Already registered
        logger.info("Agents registered: %s", AgentRegistry.list_registered())
    except Exception as exc:
        logger.warning("Agent registration failed: %s", exc)

    yield
    # Shutdown
    await async_engine.dispose()
    logger.info("Database engine disposed")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
openapi_tags = [
    {"name": "Health", "description": "Health check endpoints"},
    {"name": "Macro", "description": "Macroeconomic data series"},
    {"name": "Curves", "description": "Yield curve data"},
    {"name": "Market Data", "description": "Market prices and indicators"},
    {"name": "Flows", "description": "Capital flows and positioning"},
    {"name": "Agents", "description": "Analytical agent signals and reports"},
    {"name": "Signals", "description": "Trading signal aggregation"},
    {"name": "Risk", "description": "VaR, stress testing, and risk limits"},
    {"name": "Portfolio", "description": "Portfolio positions and optimization"},
    {"name": "Backtest", "description": "Strategy backtesting endpoints"},
    {"name": "Strategies", "description": "Strategy management and configuration"},
    {"name": "Reports", "description": "Daily reports and notifications"},
    {"name": "Monitoring", "description": "System monitoring and alerts"},
    {"name": "WebSocket", "description": "Real-time WebSocket channels"},
    {
        "name": "PMS - Portfolio",
        "description": "Portfolio positions, P&L, and book management",
    },
    {
        "name": "PMS - Trade Blotter",
        "description": "Trade proposals and approval workflow",
    },
    {"name": "PMS - Decision Journal", "description": "Immutable decision audit log"},
    {
        "name": "PMS - Morning Pack",
        "description": "Daily briefing generation and retrieval",
    },
    {
        "name": "PMS - Risk Monitor",
        "description": "Real-time risk metrics, limits, and alerts",
    },
    {
        "name": "PMS - Attribution",
        "description": "Multi-dimensional P&L attribution and performance analytics",
    },
]

app = FastAPI(
    title="Macro Trading API",
    version="0.1.0",
    description=(
        "REST API for the Macro Trading system. Serves macro-economic data, "
        "yield curves, market prices, capital flows, and positioning data."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    openapi_tags=openapi_tags,
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
_allowed_origins = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://157.230.187.3:8000",
]
if settings.allowed_origins:
    _allowed_origins.extend(
        o.strip() for o in settings.allowed_origins.split(",") if o.strip()
    )
if settings.debug:
    _allowed_origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
# Health endpoints live at the root (no prefix)
app.include_router(health.router)

# All data endpoints sit under /api/v1
app.include_router(macro.router, prefix="/api/v1")
app.include_router(curves.router, prefix="/api/v1")
app.include_router(market_data.router, prefix="/api/v1")
app.include_router(flows.router, prefix="/api/v1")

# v2 endpoints: agents, signals, strategies, portfolio, risk, reports
app.include_router(agents.router, prefix="/api/v1")
app.include_router(signals.router, prefix="/api/v1")
app.include_router(strategies_api.router, prefix="/api/v1")
app.include_router(portfolio_api.router, prefix="/api/v1")
app.include_router(risk_api.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")

# Monitoring endpoints
app.include_router(monitoring_router, prefix="/api/v1")

# Reports v2 endpoints (DailyReportGenerator)
app.include_router(reports_api_router, prefix="/api/v1")

# Backtest endpoints
app.include_router(backtest_router, prefix="/api/v1")

# PMS v4.0 endpoints
app.include_router(pms_portfolio_router, prefix="/api/v1")
app.include_router(pms_trades_router, prefix="/api/v1")
app.include_router(pms_journal_router, prefix="/api/v1")
app.include_router(pms_briefing_router, prefix="/api/v1")
app.include_router(pms_risk_router, prefix="/api/v1")
app.include_router(pms_attribution_router, prefix="/api/v1")
app.include_router(pms_pipeline_router, prefix="/api/v1")

# WebSocket endpoints at root (no prefix — ws:// paths)
app.include_router(websocket_router)

# Dashboard served at root (no prefix) — GET /dashboard
app.include_router(dashboard.router)

# Static files mount — serves .jsx files at /static/js/*.jsx for CDN Babel
app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).resolve().parent / "static")),
    name="static",
)

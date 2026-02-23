"""FastAPI application entry-point for the Macro Trading API.

Configures CORS, lifespan startup/shutdown, and mounts all route modules.
Run with:  uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from src.core.database import async_engine
from src.api.routes import (
    health, macro, curves, market_data, flows, dashboard,
    agents, signals, strategies_api, portfolio_api, risk_api, reports,
)
from src.api.routes.monitoring_api import router as monitoring_router

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
    yield
    # Shutdown
    await async_engine.dispose()
    logger.info("Database engine disposed")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
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
)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

# Dashboard served at root (no prefix) — GET /dashboard
app.include_router(dashboard.router)

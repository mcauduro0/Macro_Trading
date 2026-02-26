"""Tests for the dashboard endpoint — GET /dashboard.

Verifies the single-page HTML dashboard is served correctly with
all expected content: React, Tailwind, Recharts, 4 tabs, dark theme.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_test_app() -> FastAPI:
    """Build a minimal app with dashboard router (no DB lifespan)."""

    @asynccontextmanager
    async def _noop_lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield

    # Patch the lifespan to avoid DB connection attempts during tests
    with patch("src.api.main.lifespan", _noop_lifespan):
        # Re-import to get the app with patched lifespan
        from src.api.routes import dashboard as dashboard_mod

        app = FastAPI(lifespan=_noop_lifespan)
        app.include_router(dashboard_mod.router)
        return app


@pytest.fixture(scope="module")
def client():
    """Provide a TestClient for the dashboard-only app."""
    app = _make_test_app()
    with TestClient(app) as c:
        yield c


# -----------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------


def test_dashboard_returns_200(client: TestClient):
    """GET /dashboard returns HTTP 200."""
    response = client.get("/dashboard")
    assert response.status_code == 200


def test_dashboard_returns_html(client: TestClient):
    """Response content-type is text/html."""
    response = client.get("/dashboard")
    content_type = response.headers.get("content-type", "")
    assert "text/html" in content_type


def test_dashboard_contains_react(client: TestClient):
    """Response body contains React (confirming full HTML is served)."""
    response = client.get("/dashboard")
    body = response.text
    assert "React" in body


def test_dashboard_contains_all_tabs(client: TestClient):
    """Response body contains all 5 navigation tab labels."""
    response = client.get("/dashboard")
    body = response.text
    assert "Strategies" in body
    assert "Signals" in body
    assert "Risk" in body
    assert "Portfolio" in body
    assert "Agents" in body


def test_dashboard_dark_theme(client: TestClient):
    """Response body contains dark theme indicators."""
    response = client.get("/dashboard")
    body = response.text
    assert "darkMode" in body

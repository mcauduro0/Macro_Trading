"""Connector-specific pytest fixtures.

Loads sample API response fixtures for all connector test modules.

Phase 2 fixtures: BCB SGS, FRED, PTAX, Yahoo Finance (JSON)
Phase 3 fixtures: BCB FX Flow, BCB Focus, IBGE SIDRA, STN Fiscal (JSON),
                  Tesouro Direto (JSON), Treasury yield (CSV),
                  CFTC disaggregated (CSV)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _load_json(filename: str) -> Any:
    """Load a JSON fixture file."""
    filepath = FIXTURES_DIR / filename
    with filepath.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_text(filename: str) -> str:
    """Load a text/CSV fixture file."""
    filepath = FIXTURES_DIR / filename
    return filepath.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Phase 2 fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def bcb_sgs_response() -> list[dict[str, str]]:
    """Sample BCB SGS API response (SELIC daily rates)."""
    return _load_json("bcb_sgs_sample.json")


@pytest.fixture
def fred_response() -> dict[str, Any]:
    """Sample FRED API response (CPI observations)."""
    return _load_json("fred_sample.json")


@pytest.fixture
def ptax_response() -> dict[str, Any]:
    """Sample BCB PTAX API response (USD/BRL exchange rates)."""
    return _load_json("ptax_sample.json")


# ---------------------------------------------------------------------------
# Phase 3 fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def bcb_fx_flow_response() -> list[dict[str, str]]:
    """Sample BCB SGS response for FX flow series."""
    return _load_json("bcb_fx_flow_sample.json")


@pytest.fixture
def bcb_focus_response() -> dict[str, Any]:
    """Sample BCB Focus OData API response."""
    return _load_json("bcb_focus_sample.json")


@pytest.fixture
def ibge_sidra_response() -> list[dict[str, Any]]:
    """Sample IBGE SIDRA API response (IPCA by group)."""
    return _load_json("ibge_sidra_sample.json")


@pytest.fixture
def stn_fiscal_response() -> list[dict[str, str]]:
    """Sample BCB SGS response for STN fiscal series."""
    return _load_json("stn_fiscal_sample.json")


@pytest.fixture
def tesouro_direto_response() -> dict[str, Any]:
    """Sample Tesouro Direto JSON API response."""
    return _load_json("tesouro_direto_sample.json")


@pytest.fixture
def treasury_yield_csv() -> str:
    """Sample US Treasury yield curve CSV."""
    return _load_text("treasury_yield_sample.csv")


@pytest.fixture
def cftc_disagg_csv() -> str:
    """Sample CFTC disaggregated futures CSV."""
    return _load_text("cftc_disagg_sample.csv")

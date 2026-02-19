"""Connector-specific pytest fixtures.

Loads sample API response fixtures for BCB SGS, FRED, and PTAX connectors.
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

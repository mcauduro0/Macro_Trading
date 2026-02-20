"""Root pytest configuration and shared fixtures.

Provides common test fixtures used across all test modules:
- sample_dates: dict of commonly used test date ranges
- load_fixture: callable to load JSON fixtures from tests/fixtures/
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_dates() -> dict[str, date]:
    """Return a dict of commonly used test dates.

    Keys:
        start_2024, end_2024, start_2025, mid_2025
    """
    return {
        "start_2024": date(2024, 1, 1),
        "end_2024": date(2024, 12, 31),
        "start_2025": date(2025, 1, 1),
        "mid_2025": date(2025, 6, 15),
    }


@pytest.fixture
def load_fixture() -> Any:
    """Return a callable that loads JSON fixtures from tests/fixtures/.

    Usage::

        def test_something(load_fixture):
            data = load_fixture("bcb_sgs_sample.json")
    """
    def _load(filename: str) -> Any:
        filepath = FIXTURES_DIR / filename
        with filepath.open("r", encoding="utf-8") as f:
            return json.load(f)
    return _load

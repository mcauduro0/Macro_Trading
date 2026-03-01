#!/usr/bin/env python3
"""Initial data loading script for Macro Trading System.

Runs all data connectors to populate the Bronze layer with historical data.
Each connector is executed independently so a single failure does not block
the rest. Results are summarized at the end.

Usage:
    python scripts/init_data.py              # Run all connectors
    python scripts/init_data.py --quick      # Only essential connectors (BCB, FRED, Yahoo)
    python scripts/init_data.py --connector fred   # Run a specific connector

Prerequisites:
    - TimescaleDB running and migrations applied
    - .env file with API keys configured
    - pip install -e ".[dev]"
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
import traceback
from datetime import date, timedelta
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.connectors import (
    B3MarketDataConnector,
    BcbFocusConnector,
    BcbFxFlowConnector,
    BcbPtaxConnector,
    BcbSgsConnector,
    CftcCotConnector,
    FmpTreasuryConnector,
    FredConnector,
    IbgeSidraConnector,
    OecdSdmxConnector,
    StnFiscalConnector,
    TreasuryGovConnector,
    YahooFinanceConnector,
)

# Colors
_GREEN = "\033[92m"
_RED = "\033[91m"
_YELLOW = "\033[93m"
_BLUE = "\033[94m"
_BOLD = "\033[1m"
_RESET = "\033[0m"

# Connector registry: (name, class, requires_api_key)
CONNECTORS = [
    # Essential (no API key needed)
    ("bcb_sgs", BcbSgsConnector, False),
    ("bcb_ptax", BcbPtaxConnector, False),
    ("yahoo", YahooFinanceConnector, False),
    ("treasury_gov", TreasuryGovConnector, False),
    ("b3_market_data", B3MarketDataConnector, False),
    ("bcb_focus", BcbFocusConnector, False),
    ("bcb_fx_flow", BcbFxFlowConnector, False),
    ("ibge_sidra", IbgeSidraConnector, False),
    ("stn_fiscal", StnFiscalConnector, False),
    ("oecd_sdmx", OecdSdmxConnector, False),
    ("cftc_cot", CftcCotConnector, False),
    # API key required
    ("fred", FredConnector, True),
    ("fmp_treasury", FmpTreasuryConnector, True),
]

QUICK_SET = {"bcb_sgs", "bcb_ptax", "fred", "yahoo", "treasury_gov"}


async def run_connector(name: str, connector_cls: type, ref_date: date) -> dict:
    """Run a single connector and return status."""
    t0 = time.time()
    try:
        connector = connector_cls()
        result = await connector.fetch(reference_date=ref_date)
        elapsed = time.time() - t0

        # Count records
        count = 0
        if hasattr(result, "__len__"):
            count = len(result)
        elif isinstance(result, dict):
            count = sum(len(v) for v in result.values() if hasattr(v, "__len__"))

        return {
            "name": name,
            "status": "OK",
            "records": count,
            "elapsed": elapsed,
            "error": None,
        }
    except Exception as e:
        elapsed = time.time() - t0
        return {
            "name": name,
            "status": "FAIL",
            "records": 0,
            "elapsed": elapsed,
            "error": f"{type(e).__name__}: {e}",
        }


async def main(args: argparse.Namespace) -> int:
    ref_date = date.today() - timedelta(days=1)  # Yesterday
    print(f"\n{_BOLD}{'=' * 60}{_RESET}")
    print(f"{_BOLD}  Macro Trading — Initial Data Loading{_RESET}")
    print(f"{_BOLD}  Reference date: {ref_date}{_RESET}")
    print(f"{_BOLD}{'=' * 60}{_RESET}\n")

    # Filter connectors
    connectors_to_run = CONNECTORS
    if args.quick:
        connectors_to_run = [(n, c, k) for n, c, k in CONNECTORS if n in QUICK_SET]
        print(f"{_YELLOW}Quick mode: running {len(connectors_to_run)} essential connectors{_RESET}\n")
    elif args.connector:
        connectors_to_run = [(n, c, k) for n, c, k in CONNECTORS if n == args.connector]
        if not connectors_to_run:
            print(f"{_RED}Unknown connector: {args.connector}{_RESET}")
            print(f"Available: {', '.join(n for n, _, _ in CONNECTORS)}")
            return 1

    results = []
    for name, cls, needs_key in connectors_to_run:
        print(f"  {_BLUE}[RUN]{_RESET}  {name}...", end="", flush=True)
        result = await run_connector(name, cls, ref_date)
        results.append(result)

        if result["status"] == "OK":
            print(f"\r  {_GREEN}[OK]{_RESET}   {name:<20s} {result['records']:>6} records  ({result['elapsed']:.1f}s)")
        else:
            print(f"\r  {_RED}[FAIL]{_RESET} {name:<20s} {result['error']}")

    # Summary
    ok_count = sum(1 for r in results if r["status"] == "OK")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    total_records = sum(r["records"] for r in results)

    print(f"\n{_BOLD}{'=' * 60}{_RESET}")
    print(f"  {_GREEN}Passed: {ok_count}{_RESET}  |  {_RED}Failed: {fail_count}{_RESET}  |  Total records: {total_records}")
    print(f"{_BOLD}{'=' * 60}{_RESET}\n")

    if fail_count > 0:
        print(f"{_YELLOW}Failed connectors:{_RESET}")
        for r in results:
            if r["status"] == "FAIL":
                print(f"  - {r['name']}: {r['error']}")
        print()

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Macro Trading — Initial Data Loading")
    parser.add_argument("--quick", action="store_true", help="Run only essential connectors")
    parser.add_argument("--connector", type=str, help="Run a specific connector by name")
    args = parser.parse_args()

    exit_code = asyncio.run(main(args))
    sys.exit(exit_code)

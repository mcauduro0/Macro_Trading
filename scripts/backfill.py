#!/usr/bin/env python3
"""Historical data backfill orchestrator for the Macro Fund system.

Iterates through all configured data source connectors and runs their
fetch-then-store pipeline for a given date range.  Each connector is
instantiated as an async context manager and called via its ``run()``
method, which returns the number of records inserted.

Features:
- Idempotent: every connector uses INSERT ... ON CONFLICT DO NOTHING.
- Fault-tolerant: if one source fails the script logs a warning and
  continues with the remaining sources.
- CLI via argparse with ``--source``, ``--start-date``, ``--end-date``,
  and ``--dry-run`` flags.
- Formatted summary table printed at the end.

Usage::

    python scripts/backfill.py --source all --start-date 2010-01-01
    python scripts/backfill.py --source bcb_sgs,fred,yahoo --start-date 2020-01-01
    python scripts/backfill.py --source bcb_sgs --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
import traceback
from datetime import date, datetime
from pathlib import Path
from typing import Type

# Ensure project root is on sys.path so ``src.*`` imports work when this
# script is executed directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.connectors import (
    BaseConnector,
    BcbFocusConnector,
    BcbFxFlowConnector,
    BcbPtaxConnector,
    BcbSgsConnector,
    B3MarketDataConnector,
    CftcCotConnector,
    FredConnector,
    IbgeSidraConnector,
    StnFiscalConnector,
    TreasuryGovConnector,
    YahooFinanceConnector,
)

# ---------------------------------------------------------------------------
# Ordered list of (key, description, connector_class).
# Execution follows this order so that foundational data (BCB SGS, FRED)
# is ingested before derived sources that may depend on reference tables.
# ---------------------------------------------------------------------------
SOURCES: list[tuple[str, str, Type[BaseConnector]]] = [
    ("bcb_sgs",     "BCB SGS (50 macro series BR)",      BcbSgsConnector),
    ("fred",        "FRED (50 macro series US)",          FredConnector),
    ("bcb_focus",   "BCB Focus (market expectations)",    BcbFocusConnector),
    ("bcb_ptax",    "BCB PTAX (official FX rate)",        BcbPtaxConnector),
    ("bcb_fx_flow", "BCB FX Flow (capital flows)",        BcbFxFlowConnector),
    ("ibge",        "IBGE SIDRA (IPCA by component)",     IbgeSidraConnector),
    ("stn",         "STN Fiscal (fiscal data)",           StnFiscalConnector),
    ("b3",          "B3/Tesouro (DI curve, NTN-B)",       B3MarketDataConnector),
    ("treasury",    "Treasury.gov (US yield curves)",     TreasuryGovConnector),
    ("yahoo",       "Yahoo Finance (market prices)",      YahooFinanceConnector),
    ("cftc",        "CFTC COT (positioning)",             CftcCotConnector),
]

# Quick lookup by key
_SOURCE_KEYS = {key for key, _, _ in SOURCES}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _format_number(n: int) -> str:
    """Return an integer formatted with comma thousands separator."""
    return f"{n:,}"


def _format_seconds(s: float) -> str:
    """Return seconds as a human-friendly string."""
    if s < 60:
        return f"{s:.1f}s"
    minutes = int(s // 60)
    secs = s % 60
    return f"{minutes}m{secs:.0f}s"


def _parse_date(value: str) -> date:
    """Parse a YYYY-MM-DD string into a date object."""
    return datetime.strptime(value, "%Y-%m-%d").date()


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------
async def _run_source(
    index: int,
    total: int,
    key: str,
    description: str,
    connector_class: Type[BaseConnector],
    start_date: date,
    end_date: date,
) -> tuple[str, int, float, str]:
    """Run a single connector and return (key, records, elapsed_secs, status).

    If the connector raises an exception, the error is logged and a status of
    ``"FAIL"`` is returned instead of propagating.
    """
    print(f"\n[{index}/{total}] {description}...")

    t0 = time.monotonic()
    try:
        async with connector_class() as conn:
            records = await conn.run(start_date, end_date)
        elapsed = time.monotonic() - t0
        print(f"  Done: {_format_number(records)} records, {_format_seconds(elapsed)}")
        return key, records, elapsed, "OK"
    except Exception as exc:  # noqa: BLE001
        elapsed = time.monotonic() - t0
        print(f"  FAILED after {_format_seconds(elapsed)}: {exc}")
        traceback.print_exc()
        return key, 0, elapsed, "FAIL"


async def backfill(
    source_keys: list[str],
    start_date: date,
    end_date: date,
    dry_run: bool = False,
) -> bool:
    """Execute the backfill pipeline for the requested sources.

    Args:
        source_keys: List of source keys to run (or all keys if ``"all"``
            was specified).
        start_date: Inclusive start of the historical range.
        end_date: Inclusive end of the historical range.
        dry_run: If True, print what would run without executing.

    Returns:
        True if all sources succeeded, False if any failed.
    """
    # Filter SOURCES to only the requested keys, preserving order.
    selected = [(k, desc, cls) for k, desc, cls in SOURCES if k in source_keys]

    source_label = "all" if len(selected) == len(SOURCES) else ",".join(source_keys)

    print()
    print("=" * 56)
    print(f" MACRO FUND — HISTORICAL BACKFILL")
    print(f" Sources: {source_label} | Range: {start_date} to {end_date}")
    print("=" * 56)

    if dry_run:
        print("\n  *** DRY RUN — no data will be fetched or stored ***\n")
        for i, (key, desc, cls) in enumerate(selected, 1):
            print(f"  [{i}/{len(selected)}] {desc} ({cls.__name__})")
        print(f"\n  Would execute {len(selected)} connector(s).")
        print("=" * 56)
        return True

    # Execute each source sequentially
    results: list[tuple[str, int, float, str]] = []
    pipeline_start = time.monotonic()

    for i, (key, desc, cls) in enumerate(selected, 1):
        result = await _run_source(i, len(selected), key, desc, cls, start_date, end_date)
        results.append(result)

    pipeline_elapsed = time.monotonic() - pipeline_start

    # ------------------------------------------------------------------
    # Summary table
    # ------------------------------------------------------------------
    total_records = sum(r for _, r, _, _ in results)
    all_ok = all(s == "OK" for _, _, _, s in results)

    # Determine column widths dynamically
    name_width = max(len(k) for k, _, _, _ in results) + 2
    rec_width = max(len(_format_number(r)) for _, r, _, _ in results)
    rec_width = max(rec_width, 7)  # minimum "Records"

    print()
    print("=" * 56)
    print(" SUMMARY")
    print("=" * 56)
    header = f" {'Source':<{name_width}} | {'Records':>{rec_width}} | {'Time':>7} | Status"
    print(header)
    print(" " + "-" * (len(header) - 1))

    for key, records, elapsed, status in results:
        status_str = status if status == "OK" else f"\033[91m{status}\033[0m"
        print(
            f" {key:<{name_width}} | "
            f"{_format_number(records):>{rec_width}} | "
            f"{_format_seconds(elapsed):>7} | "
            f"{status_str}"
        )

    print(" " + "-" * (len(header) - 1))
    overall = "ALL OK" if all_ok else "SOME FAILED"
    print(
        f" {'TOTAL':<{name_width}} | "
        f"{_format_number(total_records):>{rec_width}} | "
        f"{_format_seconds(pipeline_elapsed):>7} | "
        f"{overall}"
    )
    print("=" * 56)
    print()

    return all_ok


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Macro Fund — Historical Data Backfill Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/backfill.py --source all --start-date 2010-01-01\n"
            "  python scripts/backfill.py --source bcb_sgs,fred,yahoo --start-date 2020-01-01\n"
            "  python scripts/backfill.py --source bcb_sgs --dry-run\n"
        ),
    )
    parser.add_argument(
        "--source",
        type=str,
        default="all",
        help=(
            "Comma-separated list of source keys or 'all'. "
            f"Available: {', '.join(k for k, _, _ in SOURCES)}"
        ),
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="2010-01-01",
        help="Start date in YYYY-MM-DD format (default: 2010-01-01)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="End date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show what would run without executing any connector",
    )
    return parser.parse_args(argv)


def _resolve_source_keys(raw: str) -> list[str]:
    """Resolve the ``--source`` argument into a validated list of keys.

    Raises:
        SystemExit: If any key is unrecognised.
    """
    if raw.strip().lower() == "all":
        return [key for key, _, _ in SOURCES]

    keys = [k.strip().lower() for k in raw.split(",") if k.strip()]
    invalid = [k for k in keys if k not in _SOURCE_KEYS]
    if invalid:
        print(f"Error: unknown source(s): {', '.join(invalid)}")
        print(f"Available sources: {', '.join(sorted(_SOURCE_KEYS))}")
        sys.exit(1)
    return keys


def main(argv: list[str] | None = None) -> None:
    """Entry point: parse arguments and execute the async backfill pipeline."""
    args = parse_args(argv)

    source_keys = _resolve_source_keys(args.source)
    start_date = _parse_date(args.start_date)
    end_date = _parse_date(args.end_date) if args.end_date else date.today()

    if start_date > end_date:
        print(f"Error: start-date ({start_date}) is after end-date ({end_date})")
        sys.exit(1)

    success = asyncio.run(
        backfill(
            source_keys=source_keys,
            start_date=start_date,
            end_date=end_date,
            dry_run=args.dry_run,
        )
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

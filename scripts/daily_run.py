#!/usr/bin/env python3
"""Daily pipeline CLI entry point.

Runs the 8-step daily orchestration pipeline:
  ingest -> quality -> agents -> aggregate -> strategies
  -> portfolio -> risk -> report

Usage::

    python scripts/daily_run.py                        # today, with DB writes
    python scripts/daily_run.py --dry-run              # today, no DB writes
    python scripts/daily_run.py --date 2024-01-15      # specific date
    python scripts/daily_run.py --date 2024-01-15 --dry-run
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path so ``src.*`` imports work when this
# script is invoked directly (e.g. ``python scripts/daily_run.py``).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date, datetime

from src.pipeline import DailyPipeline


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed namespace with ``date`` and ``dry_run`` attributes.
    """
    parser = argparse.ArgumentParser(
        description="Run the daily macro trading pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/daily_run.py\n"
            "  python scripts/daily_run.py --dry-run\n"
            "  python scripts/daily_run.py --date 2024-01-15\n"
            "  python scripts/daily_run.py --date 2024-01-15 --dry-run\n"
        ),
    )
    parser.add_argument(
        "--date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=date.today(),
        help="Target date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Run full computation but skip all DB persistence",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point for the daily pipeline CLI.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Exit code: 0 on success, 1 on failure.
    """
    args = parse_args(argv)
    pipeline = DailyPipeline(as_of_date=args.date, dry_run=args.dry_run)

    try:
        result = pipeline.run()
        return 0 if result.status == "SUCCESS" else 1
    except Exception as exc:
        print(f"\nPipeline failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

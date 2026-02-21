#!/usr/bin/env python3
"""Macro Trading -- Infrastructure Verification Script.

Performs a comprehensive check of the entire system and prints a formatted
report.  Each check is wrapped in try/except so a single failure does not
abort the remaining checks.

Usage:
    python scripts/verify_infrastructure.py          # full verification
    python scripts/verify_infrastructure.py --quick   # skip data quality (faster)

Exit code 0 if overall status is PASS, 1 otherwise.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
_GREEN = "\033[92m"
_RED = "\033[91m"
_YELLOW = "\033[93m"
_BOLD = "\033[1m"
_RESET = "\033[0m"

_CHECK = f"{_GREEN}OK{_RESET}"
_CROSS = f"{_RED}FAIL{_RESET}"
_WARN_MARK = f"{_YELLOW}WARN{_RESET}"

_failures: list[str] = []
_warnings: list[str] = []


def _pass(label: str, detail: str = "") -> None:
    suffix = f"  ({detail})" if detail else ""
    print(f"  {_CHECK}  {label}{suffix}")


def _fail(label: str, detail: str = "") -> None:
    suffix = f"  ({detail})" if detail else ""
    print(f"  {_CROSS}  {label}{suffix}")
    _failures.append(f"{label}: {detail}" if detail else label)


def _warn(label: str, detail: str = "") -> None:
    suffix = f"  ({detail})" if detail else ""
    print(f"  {_WARN_MARK}  {label}{suffix}")
    _warnings.append(f"{label}: {detail}" if detail else label)


def _section(title: str) -> None:
    print(f"\n {_BOLD}{title}{_RESET}")
    print(f" {'-' * (len(title) + 2)}")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# ---------------------------------------------------------------------------
# 1. Database connectivity
# ---------------------------------------------------------------------------
def check_database() -> bool:
    """Verify sync database connection and return True if connected."""
    _section("Database")
    try:
        from sqlalchemy import text
        from src.core.database import sync_engine

        with sync_engine.connect() as conn:
            row = conn.execute(text("SELECT version()")).fetchone()
            if row:
                ver = str(row[0]).split(",")[0]  # e.g. "PostgreSQL 16.x"
                _pass("Connected", ver)
                return True
            else:
                _fail("Connected", "SELECT version() returned no rows")
                return False
    except Exception as exc:
        _fail("Connected", str(exc)[:120])
        return False


# ---------------------------------------------------------------------------
# 2. Tables
# ---------------------------------------------------------------------------
def check_tables() -> int:
    """Count public-schema tables and check expected ones exist."""
    _section("Tables")
    try:
        from sqlalchemy import text
        from src.core.database import sync_engine

        with sync_engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
                )
            ).fetchall()
            existing = {r[0] for r in rows}
            count = len(existing)

            expected = {
                "instruments",
                "series_metadata",
                "data_sources",
                "macro_series",
                "market_data",
                "curves",
                "flow_data",
                "fiscal_data",
                "vol_surfaces",
                "signals",
            }
            found = expected & existing
            missing = expected - existing

            if missing:
                _warn(f"Tables: {len(found)}/{len(expected)} expected",
                      f"missing: {', '.join(sorted(missing))}")
            else:
                _pass(f"Tables: {len(found)}/{len(expected)} expected present",
                      f"{count} total in schema")
            return count
    except Exception as exc:
        _fail("Tables query", str(exc)[:120])
        return 0


# ---------------------------------------------------------------------------
# 3. Hypertables
# ---------------------------------------------------------------------------
def check_hypertables() -> int:
    """Query TimescaleDB hypertable catalog."""
    _section("Hypertables")
    try:
        from sqlalchemy import text
        from src.core.database import sync_engine

        with sync_engine.connect() as conn:
            # Check extension is available
            ext_row = conn.execute(
                text(
                    "SELECT installed_version FROM pg_available_extensions "
                    "WHERE name = 'timescaledb'"
                )
            ).fetchone()
            if ext_row and ext_row[0]:
                _pass("TimescaleDB extension", f"version {ext_row[0]}")
            else:
                _warn("TimescaleDB extension", "not installed")
                return 0

            rows = conn.execute(
                text(
                    "SELECT hypertable_name "
                    "FROM timescaledb_information.hypertables "
                    "ORDER BY hypertable_name"
                )
            ).fetchall()
            names = [r[0] for r in rows]
            count = len(names)

            expected = {
                "macro_series", "market_data", "curves",
                "flow_data", "fiscal_data", "vol_surfaces", "signals",
            }
            found = expected & set(names)
            missing = expected - set(names)

            if missing:
                _warn(f"Hypertables: {len(found)}/7 configured",
                      f"missing: {', '.join(sorted(missing))}")
            else:
                _pass(f"Hypertables: {len(found)}/7 configured")

            # Compression policies
            try:
                comp_rows = conn.execute(
                    text(
                        "SELECT hypertable_name "
                        "FROM timescaledb_information.compression_settings "
                        "GROUP BY hypertable_name"
                    )
                ).fetchall()
                comp_count = len(comp_rows)
                if comp_count >= 7:
                    _pass(f"Compression policies: {comp_count}/7 active")
                elif comp_count > 0:
                    _warn(f"Compression policies: {comp_count}/7 active")
                else:
                    _warn("Compression policies: none found")
            except Exception:
                _warn("Compression policies", "query not available")

            return count
    except Exception as exc:
        _warn("Hypertables query", str(exc)[:120])
        return 0


# ---------------------------------------------------------------------------
# 4. Redis
# ---------------------------------------------------------------------------
def check_redis() -> bool:
    """Try synchronous Redis ping."""
    _section("Redis")
    try:
        import redis as sync_redis
        from src.core.config import settings

        client = sync_redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            socket_connect_timeout=3,
        )
        pong = client.ping()
        client.close()
        if pong:
            _pass("Connected", f"{settings.redis_host}:{settings.redis_port}")
            return True
        else:
            _fail("PING", "unexpected response")
            return False
    except Exception as exc:
        _fail("Connected", str(exc)[:120])
        return False


# ---------------------------------------------------------------------------
# 5. Reference data counts
# ---------------------------------------------------------------------------
def check_reference_data() -> tuple[int, int]:
    """Count instruments and series_metadata rows."""
    _section("Reference Data")
    instruments = 0
    series = 0
    try:
        from sqlalchemy import text
        from src.core.database import sync_engine

        with sync_engine.connect() as conn:
            instruments = conn.execute(
                text("SELECT COUNT(*) FROM instruments")
            ).scalar() or 0
            series = conn.execute(
                text("SELECT COUNT(*) FROM series_metadata")
            ).scalar() or 0

        if instruments > 0:
            _pass(f"Instruments: {instruments} registered")
        else:
            _warn("Instruments: 0 registered")

        if series > 0:
            _pass(f"Series Metadata: {series} registered")
        else:
            _warn("Series Metadata: 0 registered")
    except Exception as exc:
        _fail("Reference data query", str(exc)[:120])

    return instruments, series


# ---------------------------------------------------------------------------
# 6. Data volume per table
# ---------------------------------------------------------------------------
def check_data_volume() -> dict[str, dict]:
    """Count records and latest date per data table."""
    _section("Data Volume")

    tables_info: dict[str, dict] = {}

    table_queries = {
        "macro_series": (
            "SELECT COUNT(*), MAX(observation_date) FROM macro_series",
        ),
        "market_data": (
            "SELECT COUNT(*), MAX(timestamp) FROM market_data",
        ),
        "curves": (
            "SELECT COUNT(*), MAX(curve_date) FROM curves",
        ),
        "flow_data": (
            "SELECT COUNT(*), MAX(observation_date) FROM flow_data",
        ),
        "fiscal_data": (
            "SELECT COUNT(*), MAX(observation_date) FROM fiscal_data",
        ),
    }

    try:
        from sqlalchemy import text
        from src.core.database import sync_engine

        with sync_engine.connect() as conn:
            for tbl, (query,) in table_queries.items():
                try:
                    row = conn.execute(text(query)).fetchone()
                    count = row[0] if row else 0
                    latest = row[1] if row else None
                    latest_str = str(latest)[:10] if latest else "N/A"
                    tables_info[tbl] = {"count": count, "latest": latest_str}

                    if count > 0:
                        _pass(
                            f"{tbl}: {count:,} records",
                            f"latest: {latest_str}",
                        )
                    else:
                        _warn(f"{tbl}: 0 records")
                except Exception as exc:
                    _warn(f"{tbl}", str(exc)[:80])
                    tables_info[tbl] = {"count": 0, "latest": "error"}
    except Exception as exc:
        _fail("Data volume queries", str(exc)[:120])

    return tables_info


# ---------------------------------------------------------------------------
# 7. Data quality score
# ---------------------------------------------------------------------------
def check_data_quality() -> dict:
    """Run DataQualityChecker.run_all_checks and report score."""
    _section("Data Quality")
    try:
        from src.quality.checks import DataQualityChecker

        checker = DataQualityChecker()
        summary = checker.run_all_checks()
        score = summary.get("score", 0)
        status = summary.get("status", "UNKNOWN")

        stale = summary.get("completeness", {}).get("stale", 0)
        total = summary.get("completeness", {}).get("total", 1)
        accuracy = summary.get("accuracy", {}).get("flagged", 0)
        curve_issues = summary.get("curve_integrity", {}).get("issues", 0)
        pit = summary.get("point_in_time", {}).get("violations", 0)

        if status == "PASS":
            _pass(f"Score: {score}/100 ({status})")
        elif status == "WARN":
            _warn(f"Score: {score}/100 ({status})")
        else:
            _fail(f"Score: {score}/100 ({status})")

        # Detail breakdown
        print(f"     Stale series: {stale}/{total}")
        print(f"     Accuracy flags: {accuracy}")
        print(f"     Curve issues: {curve_issues}")
        print(f"     PIT violations: {pit}")

        return summary
    except Exception as exc:
        _warn("Data quality checks", str(exc)[:120])
        return {}


# ---------------------------------------------------------------------------
# 8. API health (optional -- only if running)
# ---------------------------------------------------------------------------
def check_api() -> bool:
    """Try GET /health on localhost:8000."""
    _section("API (if running)")
    api_ok = True
    try:
        import httpx

        base = "http://localhost:8000"
        endpoints = [
            "/health",
        ]

        with httpx.Client(timeout=5.0) as client:
            for ep in endpoints:
                try:
                    resp = client.get(f"{base}{ep}")
                    if resp.status_code == 200:
                        _pass(f"GET {ep}", f"{resp.status_code}")
                    else:
                        _warn(f"GET {ep}", f"status {resp.status_code}")
                        api_ok = False
                except httpx.ConnectError:
                    _warn(f"GET {ep}", "API not running on localhost:8000")
                    api_ok = False
                except Exception as exc:
                    _warn(f"GET {ep}", str(exc)[:80])
                    api_ok = False
    except ImportError:
        _warn("httpx not installed", "skipping API checks")
        api_ok = False

    return api_ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Macro Trading -- Infrastructure Verification"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Skip data quality checks (faster).",
    )
    args = parser.parse_args()

    print()
    print(f"{_BOLD}{'=' * 56}{_RESET}")
    print(f"{_BOLD} MACRO FUND -- INFRASTRUCTURE VERIFICATION{_RESET}")
    print(f"{_BOLD}{'=' * 56}{_RESET}")
    print(f" Time: {_now()}")

    # --- Run checks ---
    db_ok = check_database()
    table_count = check_tables() if db_ok else 0
    ht_count = check_hypertables() if db_ok else 0
    redis_ok = check_redis()

    n_instruments, n_series = (0, 0)
    if db_ok:
        n_instruments, n_series = check_reference_data()

    volumes: dict = {}
    if db_ok:
        volumes = check_data_volume()

    quality_summary: dict = {}
    if db_ok and not args.quick:
        quality_summary = check_data_quality()
    elif args.quick:
        _section("Data Quality")
        _warn("Skipped (--quick)")

    api_ok = check_api()

    # --- Summary ---
    print()
    print(f"{_BOLD}{'=' * 56}{_RESET}")

    total_records = sum(v.get("count", 0) for v in volumes.values())

    if _failures:
        print(f" {_RED}{_BOLD}STATUS: FAIL{_RESET}")
        print(f" {len(_failures)} failure(s):")
        for f in _failures:
            print(f"   - {f}")
        if _warnings:
            print(f" {len(_warnings)} warning(s):")
            for w in _warnings:
                print(f"   - {w}")
    elif _warnings:
        print(f" {_YELLOW}{_BOLD}STATUS: WARN{_RESET}")
        print(f" No failures, but {len(_warnings)} warning(s):")
        for w in _warnings:
            print(f"   - {w}")
    else:
        print(f" {_GREEN}{_BOLD}STATUS: PASS{_RESET}")

    print()
    print(f" Database:      {'Connected' if db_ok else 'Not connected'}")
    print(f" Tables:        {table_count}")
    print(f" Hypertables:   {ht_count}")
    print(f" Redis:         {'Connected' if redis_ok else 'Not connected'}")
    print(f" Instruments:   {n_instruments}")
    print(f" Series:        {n_series}")
    print(f" Total records: {total_records:,}")
    if quality_summary:
        print(f" Quality score: {quality_summary.get('score', '?')}/100")
    print(f" API:           {'Responding' if api_ok else 'Not available'}")

    ready = not _failures
    if ready:
        print()
        print(f" {_GREEN}Ready for next phase{_RESET}")

    print(f"{_BOLD}{'=' * 56}{_RESET}")
    print()

    sys.exit(0 if not _failures else 1)


if __name__ == "__main__":
    main()

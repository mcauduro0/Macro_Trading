#!/usr/bin/env python3
"""Macro Trading: Infrastructure Connectivity Verification Script.

Verifies end-to-end connectivity to all infrastructure services:
  - TimescaleDB (async via asyncpg)
  - TimescaleDB (sync via psycopg2)
  - Redis (async via redis-py)

Usage:
    python scripts/verify_connectivity.py          # Basic connectivity checks
    python scripts/verify_connectivity.py --strict  # + schema validation (tables, hypertables)
"""

import argparse
import asyncio
import sys
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def _now() -> str:
    """Return current UTC timestamp string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _pass(label: str, detail: str = "") -> None:
    suffix = f" -- {detail}" if detail else ""
    print(f"  [PASS] {label}{suffix}")


def _fail(label: str, detail: str = "") -> None:
    suffix = f" -- {detail}" if detail else ""
    print(f"  [FAIL] {label}{suffix}")


def _warn(label: str, detail: str = "") -> None:
    suffix = f" -- {detail}" if detail else ""
    print(f"  [WARN] {label}{suffix}")


# ---------------------------------------------------------------------------
# Check: TimescaleDB async connection (asyncpg)
# ---------------------------------------------------------------------------
async def check_async_db(strict: bool) -> list[str]:
    """Test async database connectivity. Returns list of failure descriptions."""
    from sqlalchemy import text

    from src.core.database import async_session_factory

    failures: list[str] = []
    print(f"\n[{_now()}] Checking TimescaleDB (async / asyncpg)...")

    try:
        async with async_session_factory() as session:
            # Basic connectivity: SELECT 1
            result = await session.execute(text("SELECT 1"))
            value = result.scalar()
            if value == 1:
                _pass("SELECT 1", "async connection works")
            else:
                _fail("SELECT 1", f"expected 1, got {value}")
                failures.append("Async SELECT 1 returned unexpected value")

            # TimescaleDB extension version
            try:
                result = await session.execute(
                    text(
                        "SELECT installed_version FROM pg_available_extensions "
                        "WHERE name = 'timescaledb'"
                    )
                )
                row = result.first()
                if row and row[0]:
                    _pass("TimescaleDB extension", f"version {row[0]}")
                else:
                    _warn("TimescaleDB extension", "not installed or no version")
            except Exception as exc:
                _warn("TimescaleDB extension", str(exc))

            # Hypertable listing
            try:
                result = await session.execute(
                    text(
                        "SELECT hypertable_name "
                        "FROM timescaledb_information.hypertables "
                        "ORDER BY hypertable_name"
                    )
                )
                rows = result.fetchall()
                hypertable_names = [r[0] for r in rows]
                count = len(hypertable_names)
                if count > 0:
                    _pass("Hypertables", f"{count} found: {', '.join(hypertable_names)}")
                else:
                    if strict:
                        _fail("Hypertables", "0 found (expected 7 in strict mode)")
                        failures.append("No hypertables found (strict mode)")
                    else:
                        _warn("Hypertables", "0 found (migration may not have run yet)")
            except Exception as exc:
                if strict:
                    _fail("Hypertables query", str(exc))
                    failures.append(f"Hypertables query failed: {exc}")
                else:
                    _warn("Hypertables query", str(exc))

            # Table count in public schema
            try:
                result = await session.execute(
                    text(
                        "SELECT COUNT(*) FROM information_schema.tables "
                        "WHERE table_schema = 'public'"
                    )
                )
                table_count = result.scalar()
                if strict and table_count < 10:
                    _fail("Table count", f"{table_count} tables (expected >= 10 in strict mode)")
                    failures.append(f"Only {table_count} tables found (strict expects >= 10)")
                elif table_count >= 10:
                    _pass("Table count", f"{table_count} tables in public schema")
                else:
                    _warn("Table count", f"{table_count} tables (migration may not have run yet)")
            except Exception as exc:
                _warn("Table count", str(exc))

    except Exception as exc:
        _fail("Async DB connection", str(exc))
        failures.append(f"Async DB connection failed: {exc}")

    return failures


# ---------------------------------------------------------------------------
# Check: TimescaleDB sync connection (psycopg2)
# ---------------------------------------------------------------------------
def check_sync_db() -> list[str]:
    """Test sync database connectivity. Returns list of failure descriptions."""
    from sqlalchemy import text

    from src.core.database import get_sync_session

    failures: list[str] = []
    print(f"\n[{_now()}] Checking TimescaleDB (sync / psycopg2)...")

    try:
        session = get_sync_session()
        try:
            result = session.execute(text("SELECT 1"))
            value = result.scalar()
            if value == 1:
                _pass("SELECT 1", "sync connection works")
            else:
                _fail("SELECT 1", f"expected 1, got {value}")
                failures.append("Sync SELECT 1 returned unexpected value")
        finally:
            session.close()
    except Exception as exc:
        _fail("Sync DB connection", str(exc))
        failures.append(f"Sync DB connection failed: {exc}")

    return failures


# ---------------------------------------------------------------------------
# Check: Redis async connection
# ---------------------------------------------------------------------------
async def check_redis() -> list[str]:
    """Test Redis connectivity. Returns list of failure descriptions."""
    from src.core.redis import close_redis, get_redis

    failures: list[str] = []
    print(f"\n[{_now()}] Checking Redis...")

    try:
        redis = await get_redis()

        # PING
        pong = await redis.ping()
        if pong:
            _pass("PING", "Redis is responsive")
        else:
            _fail("PING", f"unexpected response: {pong}")
            failures.append("Redis PING returned unexpected response")

        # SET / GET / DELETE
        test_key = "macro:test:connectivity"
        await redis.set(test_key, "ok", ex=60)
        value = await redis.get(test_key)
        if value == "ok":
            _pass("SET/GET", f"key '{test_key}' = '{value}'")
        else:
            _fail("SET/GET", f"expected 'ok', got '{value}'")
            failures.append("Redis SET/GET returned unexpected value")

        await redis.delete(test_key)
        _pass("DELETE", f"cleaned up test key '{test_key}'")

    except Exception as exc:
        _fail("Redis connection", str(exc))
        failures.append(f"Redis connection failed: {exc}")
    finally:
        try:
            await close_redis()
        except Exception:
            pass

    return failures


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify Macro Trading infrastructure connectivity"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Also validate schema (10 tables, 7 hypertables). "
        "Fails if migration has not been applied.",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  Macro Trading: Infrastructure Connectivity Check")
    print("=" * 60)
    print(f"  Mode: {'STRICT' if args.strict else 'BASIC'}")
    print(f"  Time: {_now()}")

    all_failures: list[str] = []

    # 1. Async DB
    failures = await check_async_db(strict=args.strict)
    all_failures.extend(failures)

    # 2. Sync DB
    failures = check_sync_db()
    all_failures.extend(failures)

    # 3. Redis
    failures = await check_redis()
    all_failures.extend(failures)

    # Summary
    total_checks = 3  # async DB, sync DB, Redis
    passed = total_checks - min(len(all_failures), total_checks)

    print("\n" + "=" * 60)
    if not all_failures:
        print(f"  RESULT: All {total_checks} infrastructure connectivity checks PASSED")
    else:
        print(f"  RESULT: {passed}/{total_checks} checks passed, {len(all_failures)} failure(s):")
        for f in all_failures:
            print(f"    - {f}")
    print("=" * 60)

    if all_failures:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

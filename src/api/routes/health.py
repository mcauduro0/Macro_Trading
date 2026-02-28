"""Health-check and data-status endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check(session: AsyncSession = Depends(get_db)) -> dict:
    """Basic liveness probe -- verifies the database connection."""
    db_status = "disconnected"
    try:
        await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        db_status = f"disconnected: {exc}"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/data-status")
async def data_status(session: AsyncSession = Depends(get_db)) -> dict:
    """Return record counts for every data table, plus reference-table totals."""

    table_counts: dict[str, int] = {}
    for table_name in (
        "macro_series",
        "market_data",
        "curves",
        "flow_data",
        "fiscal_data",
    ):
        result = await session.execute(
            text(f"SELECT COUNT(*) FROM {table_name}")  # noqa: S608
        )
        table_counts[table_name] = result.scalar_one()

    instruments_result = await session.execute(text("SELECT COUNT(*) FROM instruments"))
    series_meta_result = await session.execute(
        text("SELECT COUNT(*) FROM series_metadata")
    )

    return {
        "table_counts": table_counts,
        "total_instruments": instruments_result.scalar_one(),
        "total_series_metadata": series_meta_result.scalar_one(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

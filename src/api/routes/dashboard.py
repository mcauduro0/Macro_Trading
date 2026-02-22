"""Dashboard route — serves the single-page HTML trading dashboard."""

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pathlib import Path

router = APIRouter(tags=["dashboard"])

DASHBOARD_HTML = Path(__file__).resolve().parent.parent / "static" / "dashboard.html"


@router.get("/dashboard", response_class=FileResponse)
async def get_dashboard():
    """Serve the single-page HTML dashboard."""
    return FileResponse(
        path=DASHBOARD_HTML,
        media_type="text/html",
    )

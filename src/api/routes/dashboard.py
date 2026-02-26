"""Dashboard route — serves the multi-file React trading dashboard.

Serves the shell HTML at GET /dashboard, which loads .jsx files from
the /static/js/ directory via Babel standalone transpilation.
"""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["dashboard"])

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
DASHBOARD_HTML = STATIC_DIR / "dashboard.html"


@router.get("/dashboard", response_class=FileResponse)
async def get_dashboard():
    """Serve the shell HTML that loads all .jsx scripts via Babel standalone."""
    return FileResponse(
        path=DASHBOARD_HTML,
        media_type="text/html",
    )

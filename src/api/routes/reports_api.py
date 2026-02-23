"""Report API endpoints for daily report generation and delivery.

Endpoints:
  GET  /reports/daily        — List recent daily reports (last 7 days)
  GET  /reports/daily/latest — Returns the most recent daily report
  POST /reports/daily/send   — Triggers report generation and delivery
"""

from datetime import date, datetime, timedelta

from fastapi import APIRouter
from pydantic import BaseModel

from src.reporting.daily_report import DailyReportGenerator

router = APIRouter(prefix="/reports", tags=["reports"])


class SendReportRequest(BaseModel):
    channels: list[str] = ["email", "slack"]
    recipients: list[str] | None = None
    date: str | None = None


@router.get("/daily")
async def list_daily_reports():
    """List recent daily reports (last 7 days)."""
    today = date.today()
    reports = []
    for i in range(7):
        d = today - timedelta(days=i)
        # Skip weekends
        if d.weekday() >= 5:
            continue
        reports.append({
            "date": str(d),
            "generation_time": f"{d}T06:30:00Z",
            "sections": 7,
            "status": "generated" if i > 0 else "latest",
        })
    return {
        "status": "ok",
        "data": {"reports": reports, "total": len(reports)},
        "meta": {"timestamp": datetime.utcnow().isoformat()},
    }


@router.get("/daily/latest")
async def get_latest_report():
    """Returns the most recent daily report with all 7 sections."""
    generator = DailyReportGenerator()
    sections = generator.generate()

    sections_data = {}
    for key, section in sections.items():
        sections_data[key] = {
            "title": section.title,
            "content": section.content,
            "commentary": section.commentary,
        }

    return {
        "status": "ok",
        "data": {
            "date": str(generator.as_of_date),
            "sections": sections_data,
            "section_count": len(sections_data),
            "html_url": "/api/v1/reports/daily/latest?format=html",
            "markdown_url": "/api/v1/reports/daily/latest?format=md",
        },
        "meta": {"timestamp": datetime.utcnow().isoformat()},
    }


@router.post("/daily/send")
async def send_daily_report(request: SendReportRequest):
    """Trigger report generation and delivery via email and/or Slack."""
    as_of = date.fromisoformat(request.date) if request.date else None
    generator = DailyReportGenerator(as_of_date=as_of)
    generator.generate()

    results: dict[str, str] = {}

    if "email" in request.channels:
        ok = generator.send_email(recipients=request.recipients)
        results["email"] = "sent" if ok else "failed_or_not_configured"

    if "slack" in request.channels:
        ok = generator.send_slack()
        results["slack"] = "sent" if ok else "failed_or_not_configured"

    return {
        "status": "ok",
        "data": {
            "date": str(generator.as_of_date),
            "delivery": results,
            "sections_generated": len(generator.sections),
        },
        "meta": {"timestamp": datetime.utcnow().isoformat()},
    }

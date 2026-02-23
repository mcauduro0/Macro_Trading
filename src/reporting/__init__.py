"""Reporting package for the Macro Trading system.

Provides DailyReportGenerator with 7 sections in markdown, HTML, email,
and Slack output formats.
"""

from src.reporting.daily_report import DailyReportGenerator, ReportSection

__all__ = ["DailyReportGenerator", "ReportSection"]

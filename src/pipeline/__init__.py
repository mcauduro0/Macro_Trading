"""Daily orchestration pipeline for the Macro Trading system.

Provides the DailyPipeline class that executes the 8-step daily workflow:
ingest -> quality -> agents -> aggregate -> strategies -> portfolio -> risk -> report.

Usage::

    from src.pipeline import DailyPipeline
    result = DailyPipeline(as_of_date=date.today(), dry_run=True).run()
"""

from src.pipeline.daily_pipeline import DailyPipeline, PipelineResult

__all__ = [
    "DailyPipeline",
    "PipelineResult",
]

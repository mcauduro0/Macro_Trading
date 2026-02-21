"""Data quality alerting -- log-based alerts for quality issues.

Provides helper functions that emit structured log messages at appropriate
severity levels based on quality check results.  These can be wired into
monitoring (Grafana, Slack webhooks, etc.) by attaching structlog processors
that forward WARNING / ERROR entries.
"""

from __future__ import annotations

from typing import Any

from src.core.utils.logging_config import get_logger

logger = get_logger("quality.alerts")


def alert_stale_series(stale_list: list[dict[str, Any]]) -> int:
    """Log warnings for each stale data series.

    Args:
        stale_list: Output of ``DataQualityChecker.check_completeness()``
            -- only entries where ``is_stale`` is ``True`` are logged.

    Returns:
        Number of alerts emitted.
    """
    count = 0
    for entry in stale_list:
        if not entry.get("is_stale"):
            continue
        logger.warning(
            "Stale data detected",
            series_code=entry.get("series_code"),
            frequency=entry.get("frequency"),
            last_date=entry.get("last_date", "NONE"),
            days_behind=entry.get("days_behind", "N/A"),
            table=entry.get("table"),
        )
        count += 1
    return count


def alert_accuracy_issues(flagged: list[dict[str, Any]]) -> int:
    """Log warnings for accuracy / range violations.

    Args:
        flagged: Output of ``DataQualityChecker.check_accuracy()``.

    Returns:
        Number of alerts emitted.
    """
    count = 0
    for entry in flagged:
        logger.warning(
            "Accuracy violation",
            series_code=entry.get("series_code"),
            date=entry.get("date"),
            value=entry.get("value"),
            expected_range=entry.get("expected_range"),
        )
        count += 1
    return count


def alert_curve_issues(issues: list[dict[str, Any]]) -> int:
    """Log warnings for curve integrity problems.

    Args:
        issues: Output of ``DataQualityChecker.check_curve_integrity()``.

    Returns:
        Number of alerts emitted.
    """
    count = 0
    for entry in issues:
        check_type = entry.get("check", "UNKNOWN")
        if check_type == "INSUFFICIENT_TENORS":
            logger.warning(
                "Curve has fewer than 5 tenor points",
                curve_id=entry.get("curve_id"),
                date=entry.get("date"),
                n_tenors=entry.get("n_tenors"),
            )
        elif check_type == "NEGATIVE_RATE":
            logger.warning(
                "Negative rate on nominal curve",
                curve_id=entry.get("curve_id"),
                date=entry.get("date"),
                tenor=entry.get("tenor"),
                rate=entry.get("rate"),
            )
        else:
            logger.warning("Curve integrity issue", **entry)
        count += 1
    return count


def alert_pit_violations(violations: list[dict[str, Any]]) -> int:
    """Log errors for point-in-time violations.

    PIT violations are logged at ERROR level because they can corrupt
    backtest results.

    Args:
        violations: Output of ``DataQualityChecker.check_point_in_time()``.

    Returns:
        Number of alerts emitted.
    """
    count = 0
    for entry in violations:
        logger.error(
            "Point-in-time violation: release_time < observation_date",
            series_code=entry.get("series_code"),
            observation_date=entry.get("observation_date"),
            release_time=entry.get("release_time"),
        )
        count += 1
    return count


def alert_quality_score(summary: dict[str, Any]) -> None:
    """Log the overall data quality score at the appropriate severity.

    * FAIL (score < 40) => ERROR
    * WARN (40 <= score < 70) => WARNING
    * PASS (score >= 70) => INFO
    """
    score = summary.get("score", 0)
    status = summary.get("status", "UNKNOWN")
    completeness = summary.get("completeness", {})
    accuracy = summary.get("accuracy", {})
    curve_integrity = summary.get("curve_integrity", {})
    point_in_time = summary.get("point_in_time", {})

    kwargs = dict(
        score=score,
        status=status,
        stale_series=completeness.get("stale", 0),
        total_series=completeness.get("total", 0),
        accuracy_flags=accuracy.get("flagged", 0),
        curve_issues=curve_integrity.get("issues", 0),
        pit_violations=point_in_time.get("violations", 0),
    )

    if status == "FAIL":
        logger.error("DATA QUALITY FAIL", **kwargs)
    elif status == "WARN":
        logger.warning("DATA QUALITY WARN", **kwargs)
    else:
        logger.info("DATA QUALITY PASS", **kwargs)

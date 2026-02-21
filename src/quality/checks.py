"""Data quality checks -- completeness, accuracy, curve integrity, PIT correctness.

Uses sync engine since quality checks are typically run offline / in scripts.
Each check method returns a list of issue dicts and can be called independently.
The ``run_all_checks`` method runs every check and produces a composite score.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import text

from src.core.database import sync_engine
from src.core.utils.logging_config import get_logger

logger = get_logger("quality.checks")

# ---------------------------------------------------------------------------
# Staleness thresholds (days) by frequency code
# ---------------------------------------------------------------------------
_STALENESS_THRESHOLDS: dict[str, int] = {
    "TICK": 3,
    "DAILY": 5,
    "WEEKLY": 12,
    "BIWEEKLY": 20,
    "MONTHLY": 50,
    "QUARTERLY": 120,
    "ANNUAL": 400,
}

# ---------------------------------------------------------------------------
# Expected value ranges for key series (series_code -> (min, max))
# ---------------------------------------------------------------------------
_RANGE_CHECKS: dict[str, tuple[float, float]] = {
    "BR_SELIC_TARGET": (0.0, 50.0),
    "BR_SELIC_DAILY": (0.0, 50.0),
    "BR_CDI_DAILY": (0.0, 50.0),
    "BR_IPCA_MOM": (-3.0, 5.0),
    "BR_IPCA_YOY": (-5.0, 40.0),
    "BR_IPCA15_MOM": (-3.0, 5.0),
    "BR_IGP_M_MOM": (-5.0, 10.0),
    "BR_UNEMPLOYMENT": (2.0, 30.0),
    "BR_GROSS_DEBT_GDP": (10.0, 120.0),
    "BR_NET_DEBT_GDP": (0.0, 100.0),
    "US_FED_FUNDS": (0.0, 25.0),
    "US_CPI_ALL_SA": (50.0, 500.0),
    "US_CPI_CORE": (50.0, 500.0),
    "US_PCE_CORE": (50.0, 500.0),
    "US_UNEMP_U3": (1.0, 25.0),
    "US_UST_10Y": (-1.0, 20.0),
    "US_UST_2Y": (-1.0, 20.0),
}

# Hypertable names expected from the initial migration
_EXPECTED_HYPERTABLES = {
    "macro_series",
    "market_data",
    "curves",
    "flow_data",
    "fiscal_data",
    "vol_surfaces",
    "signals",
}

# All tables created by the project (metadata + hypertables + alembic)
_EXPECTED_TABLES = {
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


class DataQualityChecker:
    """Run data quality checks against the Macro Trading database.

    Each ``check_*`` method returns a list of issue dicts.  The
    ``run_all_checks`` method aggregates all checks into a single summary
    dict with a 0-100 score and an overall PASS / WARN / FAIL status.
    """

    def __init__(self) -> None:
        self._completeness_results: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # 1. Completeness
    # ------------------------------------------------------------------
    def check_completeness(self) -> list[dict[str, Any]]:
        """For each active series in *series_metadata*, verify recent data exists.

        Staleness thresholds by frequency:
          DAILY  => stale if > 5 calendar days behind
          WEEKLY => stale if > 12 days
          MONTHLY => stale if > 50 days

        Returns:
            List of dicts with keys: series_code, name, frequency, last_date,
            is_stale, days_behind, table.
        """
        results: list[dict[str, Any]] = []
        today = date.today()

        with sync_engine.connect() as conn:
            # -- macro_series completeness --
            rows = conn.execute(
                text(
                    """
                    SELECT sm.series_code,
                           sm.name,
                           sm.frequency,
                           MAX(ms.observation_date) AS last_date
                      FROM series_metadata sm
                      LEFT JOIN macro_series ms ON sm.id = ms.series_id
                     WHERE sm.is_active = true
                     GROUP BY sm.id, sm.series_code, sm.name, sm.frequency
                     ORDER BY sm.series_code
                    """
                )
            ).fetchall()

            for row in rows:
                code, name, freq, last_date = row[0], row[1], row[2], row[3]
                if last_date is None:
                    results.append(
                        {
                            "series_code": code,
                            "name": name,
                            "frequency": freq,
                            "last_date": None,
                            "is_stale": True,
                            "days_behind": None,
                            "table": "macro_series",
                        }
                    )
                    continue
                days_behind = (today - last_date).days
                threshold = _STALENESS_THRESHOLDS.get(freq, 50)
                results.append(
                    {
                        "series_code": code,
                        "name": name,
                        "frequency": freq,
                        "last_date": str(last_date),
                        "is_stale": days_behind > threshold,
                        "days_behind": days_behind,
                        "table": "macro_series",
                    }
                )

            # -- market_data completeness (instruments) --
            md_rows = conn.execute(
                text(
                    """
                    SELECT i.ticker,
                           i.name,
                           MAX(md.timestamp) AS last_ts
                      FROM instruments i
                      LEFT JOIN market_data md ON i.id = md.instrument_id
                     WHERE i.is_active = true
                     GROUP BY i.id, i.ticker, i.name
                     ORDER BY i.ticker
                    """
                )
            ).fetchall()

            for row in md_rows:
                ticker, name, last_ts = row[0], row[1], row[2]
                if last_ts is None:
                    results.append(
                        {
                            "series_code": ticker,
                            "name": name,
                            "frequency": "DAILY",
                            "last_date": None,
                            "is_stale": True,
                            "days_behind": None,
                            "table": "market_data",
                        }
                    )
                    continue
                last_date_md = last_ts.date() if hasattr(last_ts, "date") else last_ts
                days_behind = (today - last_date_md).days
                results.append(
                    {
                        "series_code": ticker,
                        "name": name,
                        "frequency": "DAILY",
                        "last_date": str(last_date_md),
                        "is_stale": days_behind > _STALENESS_THRESHOLDS["DAILY"],
                        "days_behind": days_behind,
                        "table": "market_data",
                    }
                )

        self._completeness_results = results
        return results

    # ------------------------------------------------------------------
    # 2. Accuracy
    # ------------------------------------------------------------------
    def check_accuracy(self) -> list[dict[str, Any]]:
        """Validate value ranges for key series.

        For each series_code listed in ``_RANGE_CHECKS``, flag any rows whose
        ``value`` falls outside the expected ``(min, max)`` interval.

        Returns:
            List of dicts with keys: series_code, date, value, expected_range,
            check.
        """
        flagged: list[dict[str, Any]] = []

        with sync_engine.connect() as conn:
            for series_code, (low, high) in _RANGE_CHECKS.items():
                rows = conn.execute(
                    text(
                        """
                        SELECT ms.observation_date, ms.value
                          FROM macro_series ms
                          JOIN series_metadata sm ON sm.id = ms.series_id
                         WHERE sm.series_code = :code
                           AND (ms.value < :low OR ms.value > :high)
                         ORDER BY ms.observation_date DESC
                         LIMIT 10
                        """
                    ),
                    {"code": series_code, "low": low, "high": high},
                ).fetchall()

                for row in rows:
                    flagged.append(
                        {
                            "series_code": series_code,
                            "date": str(row[0]),
                            "value": float(row[1]),
                            "expected_range": f"[{low}, {high}]",
                            "check": "RANGE_VIOLATION",
                        }
                    )

        return flagged

    # ------------------------------------------------------------------
    # 3. Curve integrity
    # ------------------------------------------------------------------
    def check_curve_integrity(self) -> list[dict[str, Any]]:
        """Check yield / swap curve data quality.

        Checks:
          * At least 5 tenor points per curve_id per date.
          * No negative rates except for curves containing 'REAL' or 'BEI'
            in their curve_id (TIPS / breakeven curves can legitimately be
            negative).
        """
        issues: list[dict[str, Any]] = []

        with sync_engine.connect() as conn:
            # Insufficient tenors
            rows = conn.execute(
                text(
                    """
                    SELECT curve_id, curve_date, COUNT(*) AS n_tenors
                      FROM curves
                     GROUP BY curve_id, curve_date
                    HAVING COUNT(*) < 5
                     ORDER BY curve_date DESC
                     LIMIT 50
                    """
                )
            ).fetchall()

            for row in rows:
                issues.append(
                    {
                        "curve_id": row[0],
                        "date": str(row[1]),
                        "n_tenors": int(row[2]),
                        "check": "INSUFFICIENT_TENORS",
                    }
                )

            # Negative rates on nominal curves
            neg_rows = conn.execute(
                text(
                    """
                    SELECT curve_id, curve_date, tenor_label, rate
                      FROM curves
                     WHERE rate < 0
                       AND curve_id NOT LIKE '%REAL%'
                       AND curve_id NOT LIKE '%BEI%'
                     ORDER BY curve_date DESC
                     LIMIT 50
                    """
                )
            ).fetchall()

            for row in neg_rows:
                issues.append(
                    {
                        "curve_id": row[0],
                        "date": str(row[1]),
                        "tenor": row[2],
                        "rate": float(row[3]),
                        "check": "NEGATIVE_RATE",
                    }
                )

        return issues

    # ------------------------------------------------------------------
    # 4. Point-in-time correctness
    # ------------------------------------------------------------------
    def check_point_in_time(self) -> list[dict[str, Any]]:
        """Verify that ``release_time >= observation_date`` for macro_series.

        Point-in-time correctness requires that a data point was released no
        earlier than the period it refers to.
        """
        violations: list[dict[str, Any]] = []

        with sync_engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT ms.observation_date,
                           ms.release_time,
                           sm.series_code
                      FROM macro_series ms
                      JOIN series_metadata sm ON sm.id = ms.series_id
                     WHERE ms.release_time IS NOT NULL
                       AND ms.release_time::date < ms.observation_date
                     LIMIT 50
                    """
                )
            ).fetchall()

            for row in rows:
                violations.append(
                    {
                        "observation_date": str(row[0]),
                        "release_time": str(row[1]),
                        "series_code": row[2],
                        "check": "PIT_VIOLATION",
                    }
                )

        return violations

    # ------------------------------------------------------------------
    # Aggregate
    # ------------------------------------------------------------------
    def run_all_checks(self) -> dict[str, Any]:
        """Run every check and produce a summary with a 0-100 score.

        Scoring:
          * Starts at 100.
          * Up to -30 for staleness (proportional to stale-series ratio).
          * Up to -20 for accuracy violations (2 points each, capped).
          * Up to -20 for curve integrity issues (2 points each, capped).
          * Up to -30 for point-in-time violations (5 points each, capped).

        Returns:
            Dict with keys: score, status (PASS / WARN / FAIL),
            completeness, accuracy, curve_integrity, point_in_time.
        """
        logger.info("Running all data quality checks")

        completeness = self.check_completeness()
        accuracy = self.check_accuracy()
        curve = self.check_curve_integrity()
        pit = self.check_point_in_time()

        n_total = len(completeness) or 1
        n_stale = sum(1 for r in completeness if r.get("is_stale"))

        score = 100.0
        score -= min(30.0, (n_stale / n_total) * 30.0)
        score -= min(20.0, len(accuracy) * 2.0)
        score -= min(20.0, len(curve) * 2.0)
        score -= min(30.0, len(pit) * 5.0)
        score = max(0.0, round(score))

        if score >= 70:
            status = "PASS"
        elif score >= 40:
            status = "WARN"
        else:
            status = "FAIL"

        summary = {
            "score": int(score),
            "status": status,
            "completeness": {"total": n_total, "stale": n_stale},
            "accuracy": {"flagged": len(accuracy), "details": accuracy[:10]},
            "curve_integrity": {"issues": len(curve), "details": curve[:10]},
            "point_in_time": {"violations": len(pit), "details": pit[:10]},
        }

        logger.info(
            "Data quality check complete",
            score=summary["score"],
            status=summary["status"],
        )
        return summary

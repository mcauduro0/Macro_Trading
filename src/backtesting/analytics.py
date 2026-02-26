"""Advanced analytics for backtest results (BTST-03, BTST-05, BTST-06).

Provides:
- compute_sortino: Sortino ratio (downside risk-adjusted return)
- compute_information_ratio: Active return / tracking error
- compute_tail_ratio: Asymmetry of return tails
- compute_turnover: Average position change per period
- compute_rolling_sharpe: Rolling window Sharpe ratio
- deflated_sharpe: Bailey & Lopez de Prado (2014) Deflated Sharpe Ratio
- generate_tearsheet: Complete dict for dashboard rendering

All functions accept numpy arrays and return numeric results.
Edge cases (empty arrays, zero variance, etc.) return 0.0 gracefully.
"""
from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
from scipy.stats import kurtosis as scipy_kurtosis
from scipy.stats import norm
from scipy.stats import skew as scipy_skew

from src.backtesting.metrics import BacktestResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------
# Individual metric functions (BTST-05)
# ---------------------------------------------------------------

def compute_sortino(returns: np.ndarray, target: float = 0.0) -> float:
    """Sortino ratio: risk-adjusted return using downside deviation only.

    Args:
        returns: Array of periodic returns.
        target: Minimum acceptable return (default 0.0).

    Returns:
        Annualized Sortino ratio. 0.0 if returns is empty or downside_std is zero.
    """
    if len(returns) == 0:
        return 0.0

    excess = np.mean(returns) - target
    downside = returns[returns < target] - target
    if len(downside) == 0:
        return 0.0

    downside_std = float(np.std(downside, ddof=0))
    if downside_std < 1e-12:
        return 0.0

    return float(excess * math.sqrt(252) / downside_std)


def compute_information_ratio(
    returns: np.ndarray, benchmark: np.ndarray
) -> float:
    """Information ratio: active return / tracking error.

    Args:
        returns: Array of strategy returns.
        benchmark: Array of benchmark returns.

    Returns:
        Annualized information ratio. 0.0 if tracking error is zero.
    """
    # Truncate to shorter length
    min_len = min(len(returns), len(benchmark))
    if min_len == 0:
        return 0.0

    active = returns[:min_len] - benchmark[:min_len]
    tracking_error = float(np.std(active, ddof=0))
    if tracking_error < 1e-12:
        return 0.0

    return float(np.mean(active) * math.sqrt(252) / tracking_error)


def compute_tail_ratio(returns: np.ndarray, quantile: float = 0.05) -> float:
    """Tail ratio: right-tail / left-tail magnitude.

    Measures asymmetry of return distribution tails.
    Values > 1 indicate fatter right tail (more large gains than losses).

    Args:
        returns: Array of returns.
        quantile: Tail quantile (default 5%).

    Returns:
        Tail ratio. 0.0 if denominator is zero or returns is empty.
    """
    if len(returns) == 0:
        return 0.0

    right_tail = abs(float(np.percentile(returns, 100 * (1 - quantile))))
    left_tail = abs(float(np.percentile(returns, 100 * quantile)))

    if left_tail < 1e-12:
        return 0.0

    return float(right_tail / left_tail)


def compute_turnover(positions: np.ndarray) -> float:
    """Average absolute change in positions per period.

    Args:
        positions: Array of position sizes over time.

    Returns:
        Mean absolute change. 0.0 if fewer than 2 data points.
    """
    if len(positions) < 2:
        return 0.0

    deltas = np.abs(np.diff(positions))
    return float(np.mean(deltas))


def compute_rolling_sharpe(
    returns: np.ndarray, window: int = 252
) -> np.ndarray:
    """Rolling Sharpe ratio with given window.

    Args:
        returns: Array of periodic returns.
        window: Rolling window size (default 252 for annual).

    Returns:
        Array of same length as returns. First window-1 values are NaN.
    """
    n = len(returns)
    result = np.full(n, np.nan)

    for i in range(window - 1, n):
        w = returns[i - window + 1 : i + 1]
        std = float(np.std(w, ddof=0))
        if std < 1e-12:
            result[i] = 0.0
        else:
            result[i] = float(np.mean(w)) * math.sqrt(252) / std

    return result


# ---------------------------------------------------------------
# Deflated Sharpe Ratio (BTST-03)
# ---------------------------------------------------------------

def deflated_sharpe(
    observed_sharpe: float,
    n_trials: int,
    skewness: float,
    kurtosis_excess: float,
    n_observations: int,
    variance_of_sharpe_estimates: float | None = None,
) -> float:
    """Bailey & Lopez de Prado (2014) Deflated Sharpe Ratio.

    Tests H0: SR* = 0 vs H1: SR* > 0, adjusting for the fact that the
    best Sharpe was selected from n_trials trials.

    Values > 0.95 suggest the observed Sharpe is likely real, not a
    result of data mining.

    Args:
        observed_sharpe: The best observed Sharpe ratio.
        n_trials: Number of strategy trials performed.
        skewness: Skewness of returns.
        kurtosis_excess: Excess kurtosis of returns (kurtosis - 3).
        n_observations: Number of return observations.
        variance_of_sharpe_estimates: Variance of Sharpe estimates across
            trials. If None, estimated from the formula.

    Returns:
        DSR probability in [0, 1]. 0.0 for invalid inputs.
    """
    if n_trials <= 0 or n_observations <= 1:
        return 0.0

    # Estimate variance of Sharpe ratio
    if variance_of_sharpe_estimates is None:
        var_sr = (
            1
            - skewness * observed_sharpe
            + (kurtosis_excess / 4) * observed_sharpe ** 2
        ) / (n_observations - 1)
    else:
        var_sr = variance_of_sharpe_estimates

    # Guard against non-positive variance
    if var_sr <= 0:
        var_sr = 1e-10

    # Expected max Sharpe from i.i.d. trials (Euler-Mascheroni approximation)
    gamma = 0.5772156649015329  # Euler-Mascheroni constant
    e = math.e

    if n_trials == 1:
        e_max_sr = 0.0
    else:
        e_max_sr = math.sqrt(var_sr) * (
            (1 - gamma) * norm.ppf(1 - 1 / n_trials)
            + gamma * norm.ppf(1 - 1 / (n_trials * e))
        )

    # Deflated Sharpe = P(SR < observed | SR* = E_max_SR)
    denom = math.sqrt(var_sr * n_observations)
    if denom < 1e-12:
        return 0.0

    psr = float(
        norm.cdf(
            (observed_sharpe - e_max_sr)
            * math.sqrt(n_observations - 1)
            / denom
        )
    )

    return max(0.0, min(1.0, psr))


# ---------------------------------------------------------------
# Tearsheet generation (BTST-06)
# ---------------------------------------------------------------

def generate_tearsheet(result: BacktestResult) -> dict[str, Any]:
    """Generate a complete tearsheet dict for dashboard rendering.

    Produces all data needed for: equity curve chart, drawdown chart,
    monthly returns heatmap, rolling Sharpe plot, trade analysis table,
    and return distribution histogram.

    Args:
        result: BacktestResult from BacktestEngine.run() or compute_metrics().

    Returns:
        Dict with keys: summary, equity_curve, drawdown_chart,
        monthly_heatmap, rolling_sharpe, trade_analysis, return_distribution.
    """
    # -- Summary section --
    summary = {
        "strategy_id": result.strategy_id,
        "start_date": str(result.start_date),
        "end_date": str(result.end_date),
        "total_return": result.total_return,
        "annualized_return": result.annualized_return,
        "annualized_volatility": result.annualized_volatility,
        "sharpe_ratio": result.sharpe_ratio,
        "sortino_ratio": result.sortino_ratio,
        "calmar_ratio": result.calmar_ratio,
        "max_drawdown": result.max_drawdown,
        "win_rate": result.win_rate,
        "profit_factor": result.profit_factor,
        "total_trades": result.total_trades,
    }

    # -- Equity curve --
    equity_curve_list = [
        {"date": str(d), "equity": float(e)} for d, e in result.equity_curve
    ]

    # -- Drawdown chart --
    drawdown_chart: list[dict[str, Any]] = []
    if len(result.equity_curve) >= 2:
        equities = np.array([e for _, e in result.equity_curve], dtype=float)
        running_max = np.maximum.accumulate(equities)
        # Avoid division by zero
        safe_max = np.where(running_max > 0, running_max, 1.0)
        dd_series = (equities / safe_max - 1) * 100
        drawdown_chart = [
            {"date": str(d), "drawdown_pct": round(float(dd_series[i]), 4)}
            for i, (d, _) in enumerate(result.equity_curve)
        ]

    # -- Monthly heatmap --
    monthly_heatmap = _build_monthly_heatmap(result.monthly_returns)

    # -- Rolling Sharpe (63-day / quarterly window) --
    rolling_sharpe_list: list[dict[str, Any]] = []
    if len(result.equity_curve) >= 2:
        equities_arr = np.array(
            [e for _, e in result.equity_curve], dtype=float
        )
        daily_rets = np.diff(equities_arr) / equities_arr[:-1]
        # Filter out any inf/nan from division
        daily_rets = np.nan_to_num(daily_rets, nan=0.0, posinf=0.0, neginf=0.0)

        window = min(63, len(daily_rets))
        if window >= 2:
            rs = compute_rolling_sharpe(daily_rets, window=window)
            # Map back to dates (daily_rets[i] corresponds to equity_curve[i+1])
            for i, val in enumerate(rs):
                if not np.isnan(val):
                    d = result.equity_curve[i + 1][0]
                    rolling_sharpe_list.append(
                        {"date": str(d), "sharpe": round(float(val), 4)}
                    )

    # -- Trade analysis --
    trade_analysis = _build_trade_analysis(result)

    # -- Return distribution --
    return_distribution = _build_return_distribution(result)

    return {
        "summary": summary,
        "equity_curve": equity_curve_list,
        "drawdown_chart": drawdown_chart,
        "monthly_heatmap": monthly_heatmap,
        "rolling_sharpe": rolling_sharpe_list,
        "trade_analysis": trade_analysis,
        "return_distribution": return_distribution,
    }


def _build_monthly_heatmap(monthly_returns: dict) -> dict[str, Any]:
    """Build monthly returns heatmap from monthly_returns dict.

    Args:
        monthly_returns: {"YYYY-MM": return_pct} from BacktestResult.

    Returns:
        {"years": [...], "data": [[jan, feb, ..., dec, ytd], ...]}
    """
    if not monthly_returns:
        return {"years": [], "data": []}

    # Group by year
    year_month_data: dict[int, dict[int, float]] = {}
    for ym_str, ret in monthly_returns.items():
        try:
            parts = ym_str.split("-")
            year = int(parts[0])
            month = int(parts[1])
            year_month_data.setdefault(year, {})[month] = float(ret)
        except (ValueError, IndexError):
            continue

    years = sorted(year_month_data.keys())
    data: list[list[float | None]] = []

    for year in years:
        row: list[float | None] = []
        ytd_compound = 1.0
        for m in range(1, 13):
            val = year_month_data[year].get(m)
            if val is not None:
                row.append(round(val, 4))
                ytd_compound *= 1 + val / 100
            else:
                row.append(None)
        # YTD column
        ytd = round((ytd_compound - 1) * 100, 4)
        row.append(ytd)
        data.append(row)

    return {"years": years, "data": data}


def _build_trade_analysis(result: BacktestResult) -> dict[str, Any]:
    """Build trade analysis section from BacktestResult fields.

    Uses result-level metrics and monthly_returns as proxy for
    per-trade statistics when trade-level data is not available.
    """
    total_trades = result.total_trades
    win_rate = result.win_rate
    winning_trades = int(round(total_trades * win_rate)) if total_trades > 0 else 0
    losing_trades = total_trades - winning_trades

    # Estimate avg win/loss from monthly returns as proxy
    monthly_vals = list(result.monthly_returns.values())
    positive_months = [v for v in monthly_vals if v > 0]
    negative_months = [v for v in monthly_vals if v <= 0]

    avg_win = float(np.mean(positive_months)) if positive_months else 0.0
    avg_loss = float(np.mean(negative_months)) if negative_months else 0.0
    largest_win = float(max(positive_months)) if positive_months else 0.0
    largest_loss = float(min(negative_months)) if negative_months else 0.0

    return {
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": win_rate,
        "avg_win": round(avg_win, 4),
        "avg_loss": round(avg_loss, 4),
        "profit_factor": result.profit_factor,
        "largest_win": round(largest_win, 4),
        "largest_loss": round(largest_loss, 4),
    }


def _build_return_distribution(result: BacktestResult) -> dict[str, Any]:
    """Build return distribution statistics from equity curve.

    Computes daily returns from equity curve and provides descriptive
    statistics including mean, std, skewness, kurtosis, and percentiles.
    """
    if len(result.equity_curve) < 2:
        return {
            "mean": 0.0,
            "std": 0.0,
            "skewness": 0.0,
            "kurtosis": 0.0,
            "percentiles": {
                "5": 0.0, "25": 0.0, "50": 0.0, "75": 0.0, "95": 0.0
            },
        }

    equities = np.array([e for _, e in result.equity_curve], dtype=float)
    daily_rets = np.diff(equities) / equities[:-1]
    daily_rets = np.nan_to_num(daily_rets, nan=0.0, posinf=0.0, neginf=0.0)

    if len(daily_rets) == 0:
        return {
            "mean": 0.0,
            "std": 0.0,
            "skewness": 0.0,
            "kurtosis": 0.0,
            "percentiles": {
                "5": 0.0, "25": 0.0, "50": 0.0, "75": 0.0, "95": 0.0
            },
        }

    ret_mean = float(np.mean(daily_rets))
    ret_std = float(np.std(daily_rets, ddof=1)) if len(daily_rets) > 1 else 0.0

    # Skewness and kurtosis via scipy
    if len(daily_rets) >= 3:
        ret_skew = float(scipy_skew(daily_rets, bias=False))
    else:
        ret_skew = 0.0

    if len(daily_rets) >= 4:
        ret_kurt = float(scipy_kurtosis(daily_rets, bias=False))
    else:
        ret_kurt = 0.0

    percentiles = {
        "5": round(float(np.percentile(daily_rets, 5)), 6),
        "25": round(float(np.percentile(daily_rets, 25)), 6),
        "50": round(float(np.percentile(daily_rets, 50)), 6),
        "75": round(float(np.percentile(daily_rets, 75)), 6),
        "95": round(float(np.percentile(daily_rets, 95)), 6),
    }

    return {
        "mean": round(ret_mean, 6),
        "std": round(ret_std, 6),
        "skewness": round(ret_skew, 4),
        "kurtosis": round(ret_kurt, 4),
        "percentiles": percentiles,
    }

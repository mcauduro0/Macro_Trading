"""Backtest reporting: text summary and equity curve chart.

Uses matplotlib Agg backend for headless PNG generation.
matplotlib.use("Agg") MUST be called before importing pyplot.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend; MUST be before pyplot import
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from src.backtesting.metrics import BacktestResult

logger = logging.getLogger(__name__)

_REPORT_TEMPLATE = """
======================================================================
  BACKTEST REPORT: {strategy_id:<48}
======================================================================
  Period:          {start_date} -> {end_date:<39}
  Initial Capital: {initial_capital:>15,.0f}
  Final Equity:    {final_equity:>15,.0f}
======================================================================
  RETURN METRICS
    Total Return:          {total_return:>8.2f}%
    Annualized Return:     {annualized_return:>8.2f}%
    Annualized Volatility: {annualized_volatility:>8.2f}%
======================================================================
  RISK METRICS
    Sharpe Ratio:          {sharpe_ratio:>8.4f}
    Sortino Ratio:         {sortino_ratio:>8.4f}
    Calmar Ratio:          {calmar_ratio:>8.4f}
    Max Drawdown:          {max_drawdown:>8.2f}%
======================================================================
  TRADE STATISTICS
    Total Trades:          {total_trades:>8d}
    Win Rate:              {win_rate_pct:>8.2f}%
    Profit Factor:         {profit_factor:>8.4f}
======================================================================
"""


def generate_report(result: BacktestResult) -> str:
    """Generate a formatted text backtest report.

    Args:
        result: BacktestResult from compute_metrics().

    Returns:
        Multi-line string with tabular metrics. Suitable for logging or stdout.
    """
    return _REPORT_TEMPLATE.format(
        strategy_id=result.strategy_id,
        start_date=str(result.start_date),
        end_date=str(result.end_date),
        initial_capital=result.initial_capital,
        final_equity=result.final_equity,
        total_return=result.total_return,
        annualized_return=result.annualized_return,
        annualized_volatility=result.annualized_volatility,
        sharpe_ratio=result.sharpe_ratio,
        sortino_ratio=result.sortino_ratio,
        calmar_ratio=result.calmar_ratio,
        max_drawdown=result.max_drawdown,
        total_trades=result.total_trades,
        win_rate_pct=result.win_rate * 100,
        profit_factor=result.profit_factor,
    )


def generate_equity_chart(
    result: BacktestResult,
    output_path: Optional[str] = None,
    show_drawdown: bool = True,
) -> str:
    """Generate equity curve PNG chart and save to file.

    Uses matplotlib Agg backend (non-interactive, headless-safe).

    Args:
        result: BacktestResult from compute_metrics().
        output_path: Path to save PNG. Defaults to /tmp/{strategy_id}_equity.png.
        show_drawdown: If True, add a drawdown subplot below the equity curve.

    Returns:
        Absolute path to saved PNG file.
    """
    if output_path is None:
        output_path = f"/tmp/{result.strategy_id}_equity.png"

    output_path = str(Path(output_path).resolve())

    # Build equity series
    if not result.equity_curve:
        logger.warning("generate_equity_chart: empty equity curve, skipping chart")
        return output_path

    import pandas as pd

    dates = [pd.Timestamp(d) for d, _ in result.equity_curve]
    equities = [e for _, e in result.equity_curve]
    equity_series = pd.Series(equities, index=dates)

    if show_drawdown and len(equity_series) > 1:
        fig, (ax1, ax2) = plt.subplots(
            2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [3, 1]}
        )
    else:
        fig, ax1 = plt.subplots(1, 1, figsize=(12, 5))
        ax2 = None

    # Equity curve
    ax1.plot(
        equity_series.index,
        equity_series.values,
        color="#2196F3",
        linewidth=1.5,
        label="Portfolio Equity",
    )
    ax1.axhline(
        y=result.initial_capital,
        color="#9E9E9E",
        linestyle="--",
        linewidth=0.8,
        alpha=0.7,
        label="Initial Capital",
    )
    ax1.set_title(
        f"{result.strategy_id} -- Equity Curve\n"
        f"Return: {result.total_return:.1f}% | Sharpe: {result.sharpe_ratio:.2f} | "
        f"Max DD: {result.max_drawdown:.1f}%",
        fontsize=12,
    )
    ax1.set_ylabel("Portfolio Value")
    ax1.legend(loc="upper left", fontsize=9)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=30, ha="right")
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))

    # Drawdown subplot
    if ax2 is not None:
        rolling_max = equity_series.expanding().max()
        drawdown = (equity_series / rolling_max - 1) * 100
        ax2.fill_between(
            drawdown.index,
            drawdown.values,
            0,
            color="#F44336",
            alpha=0.4,
            label="Drawdown",
        )
        ax2.plot(drawdown.index, drawdown.values, color="#F44336", linewidth=0.8)
        ax2.set_ylabel("Drawdown %")
        ax2.set_xlabel("Date")
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=30, ha="right")
        ax2.grid(True, alpha=0.3)
        ax2.legend(loc="lower left", fontsize=9)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    logger.info("equity_chart_saved", path=output_path)
    return output_path

import numpy as np
import pandas as pd


def yoy_from_mom(mom_series: pd.Series) -> pd.Series:
    """YoY from monthly MoM percent changes.
    YoY = product(1 + MoM_i/100, i over 12 months) - 1, times 100."""
    factor = 1 + mom_series / 100.0
    rolling_product = factor.rolling(12).apply(lambda x: x.prod(), raw=True)
    return (rolling_product - 1) * 100


def compute_diffusion_index(components_df: pd.DataFrame) -> pd.Series:
    """Percentage of components with positive MoM change."""
    positive = (components_df > 0).sum(axis=1)
    total = components_df.notna().sum(axis=1)
    return (positive / total * 100).replace([np.inf, -np.inf], np.nan)


def compute_trimmed_mean(
    components_df: pd.DataFrame, trim_pct: float = 0.20
) -> pd.Series:
    """Trimmed mean: drop top and bottom trim_pct of observations per period."""

    def _trimmed(row):
        vals = row.dropna().sort_values()
        n = len(vals)
        if n < 3:
            return vals.mean()
        k = int(np.floor(n * trim_pct))
        return vals.iloc[k : n - k].mean()

    return components_df.apply(_trimmed, axis=1)


def compute_surprise_index(actual: pd.Series, expected: pd.Series) -> pd.Series:
    """Surprise = actual - expected. Positive = upside surprise."""
    return actual - expected


def compute_momentum(
    series: pd.Series, periods: list[int] | None = None
) -> pd.DataFrame:
    """Compute momentum (change) over multiple periods."""
    if periods is None:
        periods = [1, 3, 6, 12]
    result = pd.DataFrame(index=series.index)
    for p in periods:
        result[f"mom_{p}m"] = series.diff(p)
    return result


def annualize_monthly_rate(mom_series: pd.Series, window: int = 3) -> pd.Series:
    """Seasonally adjusted annualized rate (SAAR) from monthly changes.
    SAAR = ((1 + avg_monthly/100)^12 - 1) * 100."""
    avg_monthly = mom_series.rolling(window).mean()
    return ((1 + avg_monthly / 100) ** 12 - 1) * 100

import numpy as np
import pandas as pd


def compute_returns(prices: pd.Series, method: str = "log") -> pd.Series:
    """Compute returns. method: 'log' or 'simple'."""
    if method == "log":
        return np.log(prices / prices.shift(1)).dropna()
    return prices.pct_change().dropna()


def compute_rolling_volatility(returns: pd.Series, windows: list[int] | None = None) -> pd.DataFrame:
    """Annualized rolling volatility for multiple windows."""
    if windows is None:
        windows = [5, 21, 63, 252]
    result = pd.DataFrame(index=returns.index)
    for w in windows:
        result[f"vol_{w}d"] = returns.rolling(w).std() * np.sqrt(252)
    return result


def compute_z_score(series: pd.Series, window: int = 252) -> pd.Series:
    """Rolling z-score: (x - rolling_mean) / rolling_std."""
    rolling_mean = series.rolling(window).mean()
    rolling_std = series.rolling(window).std()
    return ((series - rolling_mean) / rolling_std).replace([np.inf, -np.inf], np.nan)


def compute_percentile_rank(series: pd.Series, window: int = 252) -> pd.Series:
    """Rolling percentile rank (0-100)."""
    def _rank(x):
        if len(x) < 2:
            return 50.0
        return (x.values[:-1] < x.values[-1]).sum() / (len(x) - 1) * 100
    return series.rolling(window).apply(_rank, raw=False)


def compute_rolling_correlation(s1: pd.Series, s2: pd.Series, window: int = 63) -> pd.Series:
    """Rolling Pearson correlation."""
    return s1.rolling(window).corr(s2)


def compute_ema(series: pd.Series, span: int = 20) -> pd.Series:
    """Exponential moving average."""
    return series.ewm(span=span, adjust=False).mean()


def compute_rolling_sharpe(returns: pd.Series, window: int = 252, rf: float = 0.0) -> pd.Series:
    """Rolling annualized Sharpe ratio."""
    excess = returns - rf / 252
    mean_r = excess.rolling(window).mean() * 252
    vol_r = returns.rolling(window).std() * np.sqrt(252)
    return (mean_r / vol_r).replace([np.inf, -np.inf], np.nan)


def compute_drawdown(prices: pd.Series) -> pd.DataFrame:
    """Returns DataFrame with columns: cummax, drawdown, drawdown_pct."""
    cummax = prices.cummax()
    dd = prices - cummax
    dd_pct = dd / cummax
    return pd.DataFrame({"cummax": cummax, "drawdown": dd, "drawdown_pct": dd_pct}, index=prices.index)


def compute_realized_vol(prices: pd.Series, window: int = 21) -> pd.Series:
    """Annualized realized volatility from log returns."""
    log_ret = np.log(prices / prices.shift(1))
    return log_ret.rolling(window).std() * np.sqrt(252)

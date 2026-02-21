"""Tests for src/transforms/returns.py

Covers: compute_returns, compute_rolling_volatility, compute_z_score,
        compute_percentile_rank, compute_rolling_correlation, compute_ema,
        compute_rolling_sharpe, compute_drawdown, compute_realized_vol.
"""

import numpy as np
import pandas as pd
import pytest

from src.transforms.returns import (
    compute_returns,
    compute_rolling_volatility,
    compute_z_score,
    compute_percentile_rank,
    compute_rolling_correlation,
    compute_ema,
    compute_rolling_sharpe,
    compute_drawdown,
    compute_realized_vol,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def simple_prices():
    """A simple deterministic price series: 100, 110, 105, 115, 120."""
    idx = pd.date_range("2024-01-01", periods=5, freq="B")
    return pd.Series([100.0, 110.0, 105.0, 115.0, 120.0], index=idx, name="price")


@pytest.fixture
def long_prices():
    """A longer price series (500 days) with geometric Brownian motion style."""
    np.random.seed(42)
    n = 500
    idx = pd.date_range("2022-01-01", periods=n, freq="B")
    log_rets = np.random.normal(0.0003, 0.015, n)
    log_rets[0] = 0
    prices = 100.0 * np.exp(np.cumsum(log_rets))
    return pd.Series(prices, index=idx, name="price")


# ---------------------------------------------------------------------------
# compute_returns
# ---------------------------------------------------------------------------


class TestComputeReturns:
    """Tests for return computation."""

    def test_log_returns_sum_property(self, simple_prices):
        """Log returns should be additive: sum of log returns = log(P_end/P_start)."""
        log_rets = compute_returns(simple_prices, method="log")
        total_log_ret = log_rets.sum()
        expected = np.log(simple_prices.iloc[-1] / simple_prices.iloc[0])
        assert abs(total_log_ret - expected) < 1e-10

    def test_simple_returns_multiplicative_property(self, simple_prices):
        """Compounding simple returns: prod(1+r_i) = P_end/P_start."""
        simple_rets = compute_returns(simple_prices, method="simple")
        compounded = (1 + simple_rets).prod()
        expected = simple_prices.iloc[-1] / simple_prices.iloc[0]
        assert abs(compounded - expected) < 1e-10

    def test_log_returns_length(self, simple_prices):
        """Log returns should have one fewer element than prices (NaN dropped)."""
        log_rets = compute_returns(simple_prices, method="log")
        assert len(log_rets) == len(simple_prices) - 1

    def test_simple_returns_length(self, simple_prices):
        """Simple returns should have one fewer element than prices."""
        simple_rets = compute_returns(simple_prices, method="simple")
        assert len(simple_rets) == len(simple_prices) - 1

    def test_known_simple_return(self):
        """100 -> 110 is a 10% simple return."""
        prices = pd.Series([100.0, 110.0])
        rets = compute_returns(prices, method="simple")
        assert abs(rets.iloc[0] - 0.10) < 1e-10

    def test_known_log_return(self):
        """100 -> 110: log return = ln(110/100)."""
        prices = pd.Series([100.0, 110.0])
        rets = compute_returns(prices, method="log")
        assert abs(rets.iloc[0] - np.log(1.1)) < 1e-10


# ---------------------------------------------------------------------------
# compute_rolling_volatility
# ---------------------------------------------------------------------------


class TestComputeRollingVolatility:
    """Tests for rolling annualized volatility."""

    def test_output_columns(self, long_prices):
        """Default windows [5,21,63,252] should produce matching column names."""
        rets = compute_returns(long_prices)
        vol_df = compute_rolling_volatility(rets)
        assert list(vol_df.columns) == ["vol_5d", "vol_21d", "vol_63d", "vol_252d"]

    def test_custom_windows(self, long_prices):
        """Custom windows should produce matching column names."""
        rets = compute_returns(long_prices)
        vol_df = compute_rolling_volatility(rets, windows=[10, 30])
        assert list(vol_df.columns) == ["vol_10d", "vol_30d"]

    def test_volatility_positive(self, long_prices):
        """Volatility should be non-negative (NaN for insufficient data)."""
        rets = compute_returns(long_prices)
        vol_df = compute_rolling_volatility(rets, windows=[21])
        valid_vol = vol_df["vol_21d"].dropna()
        assert (valid_vol >= 0).all()

    def test_annualization_factor(self, long_prices):
        """Annualized vol should be sqrt(252) times the daily std."""
        rets = compute_returns(long_prices)
        vol_df = compute_rolling_volatility(rets, windows=[21])
        # Check the last valid entry
        last_idx = vol_df["vol_21d"].last_valid_index()
        raw_std = rets.rolling(21).std().loc[last_idx]
        annualized = raw_std * np.sqrt(252)
        assert abs(vol_df.loc[last_idx, "vol_21d"] - annualized) < 1e-10


# ---------------------------------------------------------------------------
# compute_z_score
# ---------------------------------------------------------------------------


class TestComputeZScore:
    """Tests for rolling z-score computation."""

    def test_z_score_mean_approx_zero(self):
        """For a large random sample, the z-score should have mean close to 0."""
        np.random.seed(123)
        n = 1000
        series = pd.Series(np.random.normal(50, 10, n))
        z = compute_z_score(series, window=252)
        valid = z.dropna()
        assert abs(valid.mean()) < 0.15

    def test_z_score_std_approx_one(self):
        """For a large random sample, the z-score std should be close to 1."""
        np.random.seed(123)
        n = 1000
        series = pd.Series(np.random.normal(50, 10, n))
        z = compute_z_score(series, window=252)
        valid = z.dropna()
        assert abs(valid.std() - 1.0) < 0.15

    def test_z_score_detects_outlier(self):
        """A sudden spike should produce a large positive z-score."""
        data = [10.0] * 260 + [100.0]  # 260 values at 10, then 100
        series = pd.Series(data)
        z = compute_z_score(series, window=252)
        assert z.iloc[-1] > 3.0

    def test_z_score_nan_for_insufficient_data(self):
        """First window-1 values should be NaN."""
        series = pd.Series(range(100), dtype=float)
        z = compute_z_score(series, window=50)
        assert z.iloc[:49].isna().all()


# ---------------------------------------------------------------------------
# compute_percentile_rank
# ---------------------------------------------------------------------------


class TestComputePercentileRank:
    """Tests for rolling percentile rank."""

    def test_percentile_range_0_to_100(self):
        """All valid percentile values should be between 0 and 100."""
        np.random.seed(42)
        series = pd.Series(np.random.randn(500))
        pct = compute_percentile_rank(series, window=100)
        valid = pct.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_max_value_gets_high_percentile(self):
        """A new high should get a percentile rank of 100."""
        data = list(range(1, 101)) + [200]  # monotonically increasing then big jump
        series = pd.Series(data, dtype=float)
        pct = compute_percentile_rank(series, window=100)
        assert pct.iloc[-1] == 100.0

    def test_min_value_gets_low_percentile(self):
        """A new low should get a percentile rank of 0."""
        data = list(range(100, 0, -1)) + [-100]  # decreasing then big drop
        series = pd.Series(data, dtype=float)
        pct = compute_percentile_rank(series, window=100)
        assert pct.iloc[-1] == 0.0


# ---------------------------------------------------------------------------
# compute_rolling_correlation
# ---------------------------------------------------------------------------


class TestComputeRollingCorrelation:
    """Tests for rolling Pearson correlation."""

    def test_perfect_positive_correlation(self):
        """Two identical series should have correlation 1.0."""
        np.random.seed(42)
        s = pd.Series(np.random.randn(200))
        corr = compute_rolling_correlation(s, s, window=63)
        valid = corr.dropna()
        np.testing.assert_allclose(valid, 1.0, atol=1e-10)

    def test_perfect_negative_correlation(self):
        """A series and its negation should have correlation -1.0."""
        np.random.seed(42)
        s = pd.Series(np.random.randn(200))
        corr = compute_rolling_correlation(s, -s, window=63)
        valid = corr.dropna()
        np.testing.assert_allclose(valid, -1.0, atol=1e-10)

    def test_uncorrelated_near_zero(self):
        """Two independent random series should have correlation near 0."""
        np.random.seed(42)
        s1 = pd.Series(np.random.randn(2000))
        np.random.seed(99)
        s2 = pd.Series(np.random.randn(2000))
        corr = compute_rolling_correlation(s1, s2, window=252)
        valid = corr.dropna()
        assert abs(valid.mean()) < 0.15

    def test_correlation_range(self):
        """All correlation values should be in [-1, 1]."""
        np.random.seed(42)
        s1 = pd.Series(np.random.randn(500))
        s2 = pd.Series(np.random.randn(500))
        corr = compute_rolling_correlation(s1, s2, window=63)
        valid = corr.dropna()
        assert (valid >= -1.0 - 1e-10).all()
        assert (valid <= 1.0 + 1e-10).all()


# ---------------------------------------------------------------------------
# compute_ema
# ---------------------------------------------------------------------------


class TestComputeEma:
    """Tests for exponential moving average."""

    def test_ema_converges_to_constant(self):
        """For a constant series, EMA should equal the constant."""
        series = pd.Series([5.0] * 100)
        ema = compute_ema(series, span=20)
        np.testing.assert_allclose(ema.values, 5.0, atol=1e-10)

    def test_ema_first_value(self):
        """With adjust=False, first EMA value equals first series value."""
        series = pd.Series([10.0, 20.0, 30.0, 40.0])
        ema = compute_ema(series, span=3)
        assert abs(ema.iloc[0] - 10.0) < 1e-10

    def test_ema_smooths_noise(self):
        """EMA of noisy data should have lower std than the original."""
        np.random.seed(42)
        series = pd.Series(np.random.randn(500))
        ema = compute_ema(series, span=20)
        assert ema.std() < series.std()

    def test_ema_responds_to_step(self):
        """After a step change, EMA should move toward the new level."""
        series = pd.Series([0.0] * 50 + [1.0] * 50)
        ema = compute_ema(series, span=10)
        # After 50 periods at the new level, EMA should be close to 1.0
        assert ema.iloc[-1] > 0.99


# ---------------------------------------------------------------------------
# compute_rolling_sharpe
# ---------------------------------------------------------------------------


class TestComputeRollingSharpe:
    """Tests for rolling annualized Sharpe ratio."""

    def test_zero_returns_sharpe_zero(self):
        """Zero returns with zero RF should yield Sharpe = 0 (or NaN from 0/0)."""
        rets = pd.Series([0.0] * 300)
        sharpe = compute_rolling_sharpe(rets, window=252, rf=0.0)
        valid = sharpe.dropna()
        # All returns zero -> std = 0 -> Sharpe is NaN (replaced by NaN in source)
        # If all NaN, that is expected behavior
        if len(valid) > 0:
            assert (valid == 0).all() or valid.isna().all()

    def test_positive_returns_positive_sharpe(self, long_prices):
        """Positive drift in prices should yield positive Sharpe on average."""
        rets = compute_returns(long_prices)
        sharpe = compute_rolling_sharpe(rets, window=252, rf=0.0)
        valid = sharpe.dropna()
        if len(valid) > 0:
            # The seed has positive drift, so mean Sharpe should be positive
            assert valid.mean() > 0

    def test_sharpe_length_matches_returns(self, long_prices):
        """Output should have same length as input returns."""
        rets = compute_returns(long_prices)
        sharpe = compute_rolling_sharpe(rets, window=252)
        assert len(sharpe) == len(rets)


# ---------------------------------------------------------------------------
# compute_drawdown
# ---------------------------------------------------------------------------


class TestComputeDrawdown:
    """Tests for drawdown computation."""

    def test_known_drawdown_scenario(self):
        """100 -> 120 -> 90 -> 110: max drawdown = (90-120)/120 = -25%."""
        prices = pd.Series([100.0, 120.0, 90.0, 110.0])
        dd = compute_drawdown(prices)

        # Column existence
        assert "cummax" in dd.columns
        assert "drawdown" in dd.columns
        assert "drawdown_pct" in dd.columns

        # Cummax values
        assert dd["cummax"].iloc[0] == 100.0
        assert dd["cummax"].iloc[1] == 120.0
        assert dd["cummax"].iloc[2] == 120.0  # still 120
        assert dd["cummax"].iloc[3] == 120.0

        # Max drawdown at index 2: 90 - 120 = -30
        assert abs(dd["drawdown"].iloc[2] - (-30.0)) < 1e-10
        assert abs(dd["drawdown_pct"].iloc[2] - (-0.25)) < 1e-10

    def test_no_drawdown_monotonic_increase(self):
        """A monotonically increasing series has zero drawdown everywhere."""
        prices = pd.Series([100.0, 110.0, 120.0, 130.0, 140.0])
        dd = compute_drawdown(prices)
        assert (dd["drawdown"] == 0).all()
        assert (dd["drawdown_pct"] == 0).all()

    def test_drawdown_pct_always_nonpositive(self, long_prices):
        """Drawdown percent should always be <= 0."""
        dd = compute_drawdown(long_prices)
        assert (dd["drawdown_pct"] <= 0 + 1e-10).all()

    def test_drawdown_matches_cummax_minus_price(self, simple_prices):
        """Drawdown should equal price - cummax at each point."""
        dd = compute_drawdown(simple_prices)
        expected_dd = simple_prices - simple_prices.cummax()
        pd.testing.assert_series_equal(dd["drawdown"], expected_dd, check_names=False)


# ---------------------------------------------------------------------------
# compute_realized_vol
# ---------------------------------------------------------------------------


class TestComputeRealizedVol:
    """Tests for realized volatility."""

    def test_realized_vol_positive(self, long_prices):
        """Realized vol should be non-negative."""
        rv = compute_realized_vol(long_prices, window=21)
        valid = rv.dropna()
        assert (valid >= 0).all()

    def test_realized_vol_constant_prices(self):
        """Constant prices should have zero realized vol."""
        prices = pd.Series([100.0] * 50)
        rv = compute_realized_vol(prices, window=21)
        valid = rv.dropna()
        np.testing.assert_allclose(valid, 0.0, atol=1e-10)

    def test_realized_vol_annualized(self, long_prices):
        """Realized vol should be annualized (close to sqrt(252) * daily std)."""
        rv = compute_realized_vol(long_prices, window=21)
        log_rets = np.log(long_prices / long_prices.shift(1))
        raw_std = log_rets.rolling(21).std()
        annualized = raw_std * np.sqrt(252)
        # Compare at last valid index
        last_idx = rv.last_valid_index()
        assert abs(rv.loc[last_idx] - annualized.loc[last_idx]) < 1e-10

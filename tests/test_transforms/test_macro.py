"""Tests for src/transforms/macro.py

Covers: yoy_from_mom, compute_diffusion_index, compute_trimmed_mean,
        compute_surprise_index, compute_momentum, annualize_monthly_rate.
"""

import numpy as np
import pandas as pd

from src.transforms.macro import (
    annualize_monthly_rate,
    compute_diffusion_index,
    compute_momentum,
    compute_surprise_index,
    compute_trimmed_mean,
    yoy_from_mom,
)

# ---------------------------------------------------------------------------
# yoy_from_mom
# ---------------------------------------------------------------------------


class TestYoyFromMom:
    """Tests for year-over-year from month-over-month computation."""

    def test_constant_monthly_inflation(self):
        """If MoM is constant at 0.5% for 12 months, YoY = (1.005^12 - 1)*100."""
        mom = pd.Series([0.5] * 24)  # 24 months of 0.5%
        yoy = yoy_from_mom(mom)
        expected = ((1.005 ** 12) - 1) * 100  # ~ 6.17%
        # First 11 values are NaN (need 12 months of data)
        valid = yoy.dropna()
        assert len(valid) == 13  # indices 11..23
        assert abs(valid.iloc[0] - expected) < 0.01

    def test_zero_inflation(self):
        """If all MoM are 0, YoY should be 0."""
        mom = pd.Series([0.0] * 24)
        yoy = yoy_from_mom(mom)
        valid = yoy.dropna()
        np.testing.assert_allclose(valid, 0.0, atol=1e-10)

    def test_known_monthly_data(self):
        """12 months of exactly 1% MoM should give YoY = (1.01^12 - 1)*100."""
        mom = pd.Series([1.0] * 12)
        yoy = yoy_from_mom(mom)
        expected = ((1.01 ** 12) - 1) * 100  # ~ 12.68%
        assert abs(yoy.iloc[-1] - expected) < 0.01

    def test_negative_deflation(self):
        """Negative MoM should produce negative YoY (deflation)."""
        mom = pd.Series([-0.3] * 24)
        yoy = yoy_from_mom(mom)
        valid = yoy.dropna()
        assert (valid < 0).all()

    def test_first_11_are_nan(self):
        """YoY requires 12 observations; first 11 rolling products are NaN."""
        mom = pd.Series([0.5] * 15)
        yoy = yoy_from_mom(mom)
        assert yoy.iloc[:11].isna().all()
        assert yoy.iloc[11:].notna().all()


# ---------------------------------------------------------------------------
# compute_diffusion_index
# ---------------------------------------------------------------------------


class TestComputeDiffusionIndex:
    """Tests for the diffusion index (% of components with positive change)."""

    def test_all_positive_gives_100(self):
        """If all components are positive, diffusion = 100."""
        df = pd.DataFrame({
            "food": [0.5, 0.3, 0.8],
            "housing": [0.2, 0.4, 0.1],
            "transport": [0.1, 0.6, 0.3],
        })
        di = compute_diffusion_index(df)
        np.testing.assert_allclose(di, 100.0)

    def test_all_negative_gives_0(self):
        """If all components are negative, diffusion = 0."""
        df = pd.DataFrame({
            "food": [-0.5, -0.3],
            "housing": [-0.2, -0.4],
            "transport": [-0.1, -0.6],
        })
        di = compute_diffusion_index(df)
        np.testing.assert_allclose(di, 0.0)

    def test_mixed_gives_partial(self):
        """2 of 4 positive -> 50%."""
        df = pd.DataFrame({
            "food": [0.5],
            "housing": [-0.2],
            "transport": [0.1],
            "clothing": [-0.3],
        })
        di = compute_diffusion_index(df)
        assert abs(di.iloc[0] - 50.0) < 1e-10

    def test_zero_counted_as_not_positive(self):
        """Components at exactly 0 are not > 0, so should not count as positive."""
        df = pd.DataFrame({
            "a": [0.0],
            "b": [0.0],
            "c": [1.0],
        })
        di = compute_diffusion_index(df)
        assert abs(di.iloc[0] - (1.0 / 3.0) * 100) < 1e-6

    def test_nan_handling(self):
        """NaN components should be excluded from the denominator."""
        df = pd.DataFrame({
            "a": [0.5],
            "b": [np.nan],
            "c": [-0.1],
        })
        di = compute_diffusion_index(df)
        # 1 positive out of 2 non-NaN = 50%
        assert abs(di.iloc[0] - 50.0) < 1e-10


# ---------------------------------------------------------------------------
# compute_trimmed_mean
# ---------------------------------------------------------------------------


class TestComputeTrimmedMean:
    """Tests for the trimmed mean computation."""

    def test_trims_extremes(self):
        """With 20% trim on 10 values, top 2 and bottom 2 should be removed."""
        # Values: 1,2,3,4,5,6,7,8,9,10 -> trim 2 each side -> mean(3..8)
        row_data = list(range(1, 11))
        df = pd.DataFrame([row_data], columns=[f"c{i}" for i in range(10)])
        tm = compute_trimmed_mean(df, trim_pct=0.20)
        expected = np.mean([3, 4, 5, 6, 7, 8])  # 5.5
        assert abs(tm.iloc[0] - expected) < 1e-10

    def test_no_trim(self):
        """With 0% trim, result should equal plain mean."""
        df = pd.DataFrame([[1.0, 2.0, 3.0, 4.0, 5.0]])
        tm = compute_trimmed_mean(df, trim_pct=0.0)
        assert abs(tm.iloc[0] - 3.0) < 1e-10

    def test_symmetric_values(self):
        """For symmetric data, trimmed mean should equal regular mean."""
        df = pd.DataFrame([[1.0, 3.0, 5.0, 7.0, 9.0]])
        tm = compute_trimmed_mean(df, trim_pct=0.20)
        # Trim 1 from each side: mean(3,5,7) = 5.0
        expected = np.mean([3.0, 5.0, 7.0])
        assert abs(tm.iloc[0] - expected) < 1e-10

    def test_outlier_resistance(self):
        """Trimmed mean should resist extreme outliers better than plain mean."""
        normal_values = [2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
        with_outlier = normal_values + [1000.0, -500.0]  # extreme outliers
        df = pd.DataFrame([with_outlier], columns=[f"c{i}" for i in range(10)])

        tm = compute_trimmed_mean(df, trim_pct=0.20)
        plain_mean = np.mean(with_outlier)
        # Trimmed mean should be much closer to the center than plain mean
        assert abs(tm.iloc[0] - 5.5) < abs(plain_mean - 5.5)

    def test_small_sample_fallback(self):
        """With fewer than 3 values, should return plain mean."""
        df = pd.DataFrame([[10.0, 20.0]])
        tm = compute_trimmed_mean(df, trim_pct=0.20)
        assert abs(tm.iloc[0] - 15.0) < 1e-10


# ---------------------------------------------------------------------------
# compute_surprise_index
# ---------------------------------------------------------------------------


class TestComputeSurpriseIndex:
    """Tests for the surprise index (actual - expected)."""

    def test_positive_surprise(self):
        """Actual > expected should yield positive surprise."""
        actual = pd.Series([5.0, 6.0, 7.0])
        expected = pd.Series([4.5, 5.5, 6.5])
        surprise = compute_surprise_index(actual, expected)
        assert (surprise > 0).all()

    def test_negative_surprise(self):
        """Actual < expected should yield negative surprise."""
        actual = pd.Series([4.0, 5.0])
        expected = pd.Series([5.0, 6.0])
        surprise = compute_surprise_index(actual, expected)
        assert (surprise < 0).all()

    def test_no_surprise(self):
        """Actual == expected should yield zero surprise."""
        values = pd.Series([3.0, 4.0, 5.0])
        surprise = compute_surprise_index(values, values)
        np.testing.assert_allclose(surprise, 0.0)

    def test_known_values(self):
        """Verify exact surprise values."""
        actual = pd.Series([0.45, 0.30, 0.60])
        expected = pd.Series([0.40, 0.35, 0.50])
        surprise = compute_surprise_index(actual, expected)
        np.testing.assert_allclose(surprise, [0.05, -0.05, 0.10])

    def test_preserves_index(self):
        """Output should have the same index as input."""
        idx = pd.date_range("2024-01-01", periods=3, freq="MS")
        actual = pd.Series([1.0, 2.0, 3.0], index=idx)
        expected = pd.Series([0.5, 1.5, 2.5], index=idx)
        surprise = compute_surprise_index(actual, expected)
        pd.testing.assert_index_equal(surprise.index, idx)


# ---------------------------------------------------------------------------
# compute_momentum
# ---------------------------------------------------------------------------


class TestComputeMomentum:
    """Tests for multi-period momentum (change) computation."""

    def test_default_periods(self):
        """Default periods [1,3,6,12] should produce 4 columns."""
        series = pd.Series(range(20), dtype=float)
        result = compute_momentum(series)
        assert list(result.columns) == ["mom_1m", "mom_3m", "mom_6m", "mom_12m"]

    def test_custom_periods(self):
        """Custom periods should produce matching columns."""
        series = pd.Series(range(20), dtype=float)
        result = compute_momentum(series, periods=[1, 2, 5])
        assert list(result.columns) == ["mom_1m", "mom_2m", "mom_5m"]

    def test_known_momentum_values(self):
        """For a linear series 0,1,2,...,19 the 1-period diff is always 1."""
        series = pd.Series(range(20), dtype=float)
        result = compute_momentum(series, periods=[1])
        valid = result["mom_1m"].dropna()
        assert (valid == 1.0).all()

    def test_3_period_momentum(self):
        """3-period momentum on linear series should be 3."""
        series = pd.Series(range(20), dtype=float)
        result = compute_momentum(series, periods=[3])
        valid = result["mom_3m"].dropna()
        assert (valid == 3.0).all()

    def test_nan_for_insufficient_data(self):
        """First p values of p-period momentum should be NaN."""
        series = pd.Series(range(10), dtype=float)
        result = compute_momentum(series, periods=[3])
        assert result["mom_3m"].iloc[:3].isna().all()
        assert result["mom_3m"].iloc[3:].notna().all()


# ---------------------------------------------------------------------------
# annualize_monthly_rate (SAAR)
# ---------------------------------------------------------------------------


class TestAnnualizeMonthlyRate:
    """Tests for Seasonally Adjusted Annualized Rate."""

    def test_known_saar(self):
        """3-month average of 0.5% MoM -> SAAR = ((1.005)^12 - 1) * 100 ~ 6.17%."""
        mom = pd.Series([0.5] * 10)
        saar = annualize_monthly_rate(mom, window=3)
        valid = saar.dropna()
        expected = ((1.005 ** 12) - 1) * 100
        np.testing.assert_allclose(valid, expected, atol=0.01)

    def test_zero_monthly_gives_zero_saar(self):
        """Zero MoM should produce zero SAAR."""
        mom = pd.Series([0.0] * 10)
        saar = annualize_monthly_rate(mom, window=3)
        valid = saar.dropna()
        np.testing.assert_allclose(valid, 0.0, atol=1e-10)

    def test_negative_monthly_gives_negative_saar(self):
        """Negative MoM should yield negative SAAR."""
        mom = pd.Series([-0.3] * 10)
        saar = annualize_monthly_rate(mom, window=3)
        valid = saar.dropna()
        assert (valid < 0).all()

    def test_saar_larger_than_monthly(self):
        """Annualizing a positive monthly rate should amplify it."""
        mom = pd.Series([1.0] * 10)
        saar = annualize_monthly_rate(mom, window=3)
        valid = saar.dropna()
        # SAAR of 1% monthly >> 1%
        assert (valid > 1.0).all()

    def test_window_size_affects_smoothing(self):
        """Larger window should produce smoother SAAR."""
        mom = pd.Series([0.3, 0.6, 0.2, 0.8, 0.1, 0.5, 0.4, 0.7, 0.3, 0.6])
        saar_3 = annualize_monthly_rate(mom, window=3)
        saar_6 = annualize_monthly_rate(mom, window=6)
        # Larger window should have lower standard deviation (smoother)
        assert saar_6.dropna().std() < saar_3.dropna().std()

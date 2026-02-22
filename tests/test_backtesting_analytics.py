"""Comprehensive tests for backtesting analytics functions.

Tests cover:
- compute_sortino: Sortino ratio with edge cases
- compute_information_ratio: Active return / tracking error
- compute_tail_ratio: Tail asymmetry measurement
- compute_turnover: Average position change
- compute_rolling_sharpe: Rolling window Sharpe
- deflated_sharpe: Bailey & Lopez de Prado (2014) DSR (BTST-03)
- generate_tearsheet: Complete tearsheet dict (BTST-06)
"""
from datetime import date

import numpy as np
import pytest

from src.backtesting.analytics import (
    compute_information_ratio,
    compute_rolling_sharpe,
    compute_sortino,
    compute_tail_ratio,
    compute_turnover,
    deflated_sharpe,
    generate_tearsheet,
)
from src.backtesting.metrics import BacktestResult


# ---------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------

@pytest.fixture
def sample_returns():
    """Sample returns array for basic tests."""
    return np.array([0.01, -0.02, 0.015, -0.005, 0.01])


@pytest.fixture
def realistic_backtest_result():
    """BacktestResult with 252-day synthetic equity curve."""
    np.random.seed(42)
    n_days = 252
    start = date(2023, 1, 2)
    daily_returns = np.random.normal(0.0004, 0.01, n_days)
    equity = [1_000_000.0]
    dates = []
    current = start
    for i in range(n_days):
        # Skip weekends simply
        equity.append(equity[-1] * (1 + daily_returns[i]))
        dates.append(current)
        # Advance by 1 day (simplified)
        from datetime import timedelta
        current = current + timedelta(days=1)
        # Skip weekends
        while current.weekday() >= 5:
            current = current + timedelta(days=1)

    dates.append(current)
    equity_curve = list(zip(dates, equity))

    # Build monthly returns dict
    monthly_returns = {}
    for m in range(1, 13):
        key = f"2023-{m:02d}"
        monthly_returns[key] = round(np.random.normal(0.5, 2.0), 4)

    final_eq = equity[-1]
    total_ret = (final_eq / 1_000_000 - 1) * 100

    return BacktestResult(
        strategy_id="TEST_STRAT",
        start_date=date(2023, 1, 2),
        end_date=current,
        initial_capital=1_000_000.0,
        final_equity=final_eq,
        total_return=round(total_ret, 4),
        annualized_return=round(total_ret, 4),  # ~1yr so approx same
        annualized_volatility=15.0,
        sharpe_ratio=1.2,
        sortino_ratio=1.5,
        calmar_ratio=0.8,
        max_drawdown=-5.5,
        win_rate=0.55,
        profit_factor=1.3,
        total_trades=120,
        monthly_returns=monthly_returns,
        equity_curve=equity_curve,
    )


@pytest.fixture
def empty_backtest_result():
    """BacktestResult with empty equity curve."""
    return BacktestResult(
        strategy_id="EMPTY",
        start_date=date(2023, 1, 1),
        end_date=date(2023, 12, 31),
        initial_capital=1_000_000.0,
        final_equity=1_000_000.0,
        total_return=0.0,
        annualized_return=0.0,
        annualized_volatility=0.0,
        sharpe_ratio=0.0,
        sortino_ratio=0.0,
        calmar_ratio=0.0,
        max_drawdown=0.0,
        win_rate=0.0,
        profit_factor=0.0,
        total_trades=0,
        monthly_returns={},
        equity_curve=[],
    )


# ---------------------------------------------------------------
# compute_sortino tests
# ---------------------------------------------------------------

class TestComputeSortino:
    def test_sortino_known_value(self, sample_returns):
        """Known returns produce a float Sortino value."""
        result = compute_sortino(sample_returns)
        assert isinstance(result, float)
        # With mix of positive/negative returns, Sortino should be nonzero
        assert result != 0.0

    def test_sortino_positive_returns_only(self):
        """All positive returns -> downside std is zero -> returns 0.0."""
        rets = np.array([0.01, 0.02, 0.015, 0.005, 0.01])
        result = compute_sortino(rets)
        assert result == 0.0

    def test_sortino_empty_returns(self):
        """Empty array returns 0.0."""
        assert compute_sortino(np.array([])) == 0.0

    def test_sortino_all_negative(self):
        """All negative returns produce a negative Sortino."""
        rets = np.array([-0.01, -0.02, -0.015, -0.005, -0.01])
        result = compute_sortino(rets)
        assert result < 0.0

    def test_sortino_single_value(self):
        """Single value: downside_std is 0 if value >= 0."""
        assert compute_sortino(np.array([0.01])) == 0.0
        # Single negative value
        result = compute_sortino(np.array([-0.01]))
        # downside_std with ddof=0 for single element is 0.0
        assert result == 0.0


# ---------------------------------------------------------------
# compute_information_ratio tests
# ---------------------------------------------------------------

class TestComputeInformationRatio:
    def test_ir_identical_returns(self):
        """Identical returns and benchmark -> IR = 0.0."""
        rets = np.array([0.01, -0.005, 0.008])
        assert compute_information_ratio(rets, rets) == 0.0

    def test_ir_outperformance(self):
        """Returns consistently > benchmark -> IR > 0."""
        rets = np.array([0.02, 0.01, 0.03, 0.015, 0.025])
        bench = np.array([0.01, 0.005, 0.01, 0.005, 0.01])
        ir = compute_information_ratio(rets, bench)
        assert ir > 0

    def test_ir_different_lengths(self):
        """Arrays of different lengths truncated to shorter."""
        rets = np.array([0.02, 0.01, 0.03, 0.015, 0.025])
        bench = np.array([0.01, 0.005, 0.01])
        ir = compute_information_ratio(rets, bench)
        assert isinstance(ir, float)

    def test_ir_empty(self):
        """Empty arrays return 0.0."""
        assert compute_information_ratio(np.array([]), np.array([])) == 0.0


# ---------------------------------------------------------------
# compute_tail_ratio tests
# ---------------------------------------------------------------

class TestComputeTailRatio:
    def test_tail_ratio_symmetric(self):
        """Normal distribution returns -> tail ratio close to 1.0."""
        np.random.seed(123)
        rets = np.random.normal(0, 0.01, 10000)
        ratio = compute_tail_ratio(rets)
        assert 0.8 < ratio < 1.2

    def test_tail_ratio_positive_skew(self):
        """Positive skew -> more large gains -> tail ratio > 1.0."""
        np.random.seed(42)
        # Lognormal-ish: fat right tail
        rets = np.random.lognormal(0, 0.5, 10000) - 1
        ratio = compute_tail_ratio(rets)
        assert ratio > 1.0

    def test_tail_ratio_empty(self):
        """Empty returns -> 0.0."""
        assert compute_tail_ratio(np.array([])) == 0.0


# ---------------------------------------------------------------
# compute_turnover tests
# ---------------------------------------------------------------

class TestComputeTurnover:
    def test_turnover_constant_positions(self):
        """No change in positions -> 0.0."""
        positions = np.array([1.0, 1.0, 1.0, 1.0])
        assert compute_turnover(positions) == 0.0

    def test_turnover_alternating(self):
        """[1, -1, 1, -1] -> mean(|delta|) = 2.0."""
        positions = np.array([1.0, -1.0, 1.0, -1.0])
        assert compute_turnover(positions) == 2.0

    def test_turnover_single(self):
        """Single position -> 0.0."""
        assert compute_turnover(np.array([1.0])) == 0.0

    def test_turnover_empty(self):
        """Empty positions -> 0.0."""
        assert compute_turnover(np.array([])) == 0.0


# ---------------------------------------------------------------
# compute_rolling_sharpe tests
# ---------------------------------------------------------------

class TestComputeRollingSharpe:
    def test_rolling_sharpe_output_length(self):
        """Output length matches input length."""
        rets = np.random.normal(0, 0.01, 100)
        result = compute_rolling_sharpe(rets, window=20)
        assert len(result) == len(rets)

    def test_rolling_sharpe_nans_at_start(self):
        """First window-1 values are NaN."""
        rets = np.random.normal(0, 0.01, 100)
        window = 20
        result = compute_rolling_sharpe(rets, window=window)
        assert all(np.isnan(result[i]) for i in range(window - 1))
        # First valid value is at index window-1
        assert not np.isnan(result[window - 1])

    def test_rolling_sharpe_constant_returns(self):
        """Constant positive returns -> rolling Sharpe is 0.0 (zero std)."""
        rets = np.full(50, 0.01)
        result = compute_rolling_sharpe(rets, window=10)
        # Where defined, should be 0.0 (zero variance guard)
        for val in result[9:]:
            assert val == 0.0

    def test_rolling_sharpe_short_input(self):
        """Input shorter than window -> all NaN."""
        rets = np.array([0.01, -0.005, 0.008])
        result = compute_rolling_sharpe(rets, window=10)
        assert all(np.isnan(result))


# ---------------------------------------------------------------
# deflated_sharpe tests (BTST-03)
# ---------------------------------------------------------------

class TestDeflatedSharpe:
    def test_dsr_single_trial(self):
        """Single trial: no multiple-testing penalty -> high DSR for good Sharpe."""
        dsr = deflated_sharpe(
            observed_sharpe=2.0,
            n_trials=1,
            skewness=0.0,
            kurtosis_excess=3.0,
            n_observations=252,
        )
        assert dsr > 0.9

    def test_dsr_many_trials_reduces_significance(self):
        """More trials reduces DSR (multiple testing penalty).

        Uses moderate Sharpe and few observations to avoid CDF saturation.
        """
        dsr_1 = deflated_sharpe(
            observed_sharpe=0.5,
            n_trials=1,
            skewness=0.0,
            kurtosis_excess=3.0,
            n_observations=60,
        )
        dsr_100 = deflated_sharpe(
            observed_sharpe=0.5,
            n_trials=100,
            skewness=0.0,
            kurtosis_excess=3.0,
            n_observations=60,
        )
        assert dsr_1 > dsr_100

    def test_dsr_range_0_to_1(self):
        """DSR is always in [0, 1]."""
        for sr in [0.1, 0.5, 1.0, 2.0, 5.0]:
            for trials in [1, 5, 10, 50, 100]:
                result = deflated_sharpe(
                    observed_sharpe=sr,
                    n_trials=trials,
                    skewness=0.0,
                    kurtosis_excess=3.0,
                    n_observations=252,
                )
                assert 0.0 <= result <= 1.0, (
                    f"DSR={result} out of range for sr={sr}, trials={trials}"
                )

    def test_dsr_zero_trials_returns_zero(self):
        """n_trials=0 -> 0.0."""
        assert deflated_sharpe(2.0, 0, 0.0, 3.0, 252) == 0.0

    def test_dsr_low_sharpe_low_probability(self):
        """Low Sharpe with many trials -> DSR < 0.5."""
        dsr = deflated_sharpe(
            observed_sharpe=0.1,
            n_trials=50,
            skewness=0.0,
            kurtosis_excess=3.0,
            n_observations=252,
        )
        assert dsr < 0.5

    def test_dsr_high_sharpe_high_probability(self):
        """High Sharpe with few trials, many observations -> DSR > 0.8."""
        dsr = deflated_sharpe(
            observed_sharpe=3.0,
            n_trials=5,
            skewness=0.0,
            kurtosis_excess=3.0,
            n_observations=1000,
        )
        assert dsr > 0.8

    def test_dsr_n_observations_one_returns_zero(self):
        """n_observations <= 1 -> 0.0."""
        assert deflated_sharpe(2.0, 10, 0.0, 3.0, 1) == 0.0
        assert deflated_sharpe(2.0, 10, 0.0, 3.0, 0) == 0.0

    def test_dsr_with_explicit_variance(self):
        """Providing variance_of_sharpe_estimates uses that value."""
        dsr = deflated_sharpe(
            observed_sharpe=2.0,
            n_trials=10,
            skewness=0.0,
            kurtosis_excess=3.0,
            n_observations=252,
            variance_of_sharpe_estimates=0.01,
        )
        assert 0.0 <= dsr <= 1.0


# ---------------------------------------------------------------
# generate_tearsheet tests (BTST-06)
# ---------------------------------------------------------------

class TestGenerateTearsheet:
    def test_tearsheet_structure(self, realistic_backtest_result):
        """All 7 top-level keys present."""
        ts = generate_tearsheet(realistic_backtest_result)
        expected_keys = {
            "summary", "equity_curve", "drawdown_chart",
            "monthly_heatmap", "rolling_sharpe", "trade_analysis",
            "return_distribution",
        }
        assert set(ts.keys()) == expected_keys

    def test_tearsheet_equity_curve_format(self, realistic_backtest_result):
        """Each equity curve element has 'date' and 'equity' keys."""
        ts = generate_tearsheet(realistic_backtest_result)
        assert len(ts["equity_curve"]) > 0
        for entry in ts["equity_curve"]:
            assert "date" in entry
            assert "equity" in entry
            assert isinstance(entry["equity"], float)

    def test_tearsheet_drawdown_chart_values(self, realistic_backtest_result):
        """All drawdown_pct values <= 0."""
        ts = generate_tearsheet(realistic_backtest_result)
        assert len(ts["drawdown_chart"]) > 0
        for entry in ts["drawdown_chart"]:
            assert "date" in entry
            assert "drawdown_pct" in entry
            assert entry["drawdown_pct"] <= 0.0001  # allow tiny float tolerance

    def test_tearsheet_monthly_heatmap_structure(self, realistic_backtest_result):
        """Heatmap has 'years' (list of ints) and 'data' (list of lists)."""
        ts = generate_tearsheet(realistic_backtest_result)
        hm = ts["monthly_heatmap"]
        assert "years" in hm
        assert "data" in hm
        assert isinstance(hm["years"], list)
        assert isinstance(hm["data"], list)
        if hm["years"]:
            assert all(isinstance(y, int) for y in hm["years"])
            # Each row has 13 elements (12 months + YTD)
            for row in hm["data"]:
                assert len(row) == 13

    def test_tearsheet_summary_fields(self, realistic_backtest_result):
        """Summary dict has all expected keys."""
        ts = generate_tearsheet(realistic_backtest_result)
        summary = ts["summary"]
        expected_fields = {
            "strategy_id", "start_date", "end_date",
            "total_return", "annualized_return", "annualized_volatility",
            "sharpe_ratio", "sortino_ratio", "calmar_ratio", "max_drawdown",
            "win_rate", "profit_factor", "total_trades",
        }
        assert expected_fields.issubset(set(summary.keys()))

    def test_tearsheet_trade_analysis(self, realistic_backtest_result):
        """Trade analysis section has expected fields."""
        ts = generate_tearsheet(realistic_backtest_result)
        ta = ts["trade_analysis"]
        expected = {
            "total_trades", "winning_trades", "losing_trades",
            "win_rate", "avg_win", "avg_loss",
            "profit_factor", "largest_win", "largest_loss",
        }
        assert expected.issubset(set(ta.keys()))

    def test_tearsheet_return_distribution(self, realistic_backtest_result):
        """Return distribution has mean, std, skewness, kurtosis, percentiles."""
        ts = generate_tearsheet(realistic_backtest_result)
        rd = ts["return_distribution"]
        assert "mean" in rd
        assert "std" in rd
        assert "skewness" in rd
        assert "kurtosis" in rd
        assert "percentiles" in rd
        for pct in ["5", "25", "50", "75", "95"]:
            assert pct in rd["percentiles"]

    def test_tearsheet_empty_equity_curve(self, empty_backtest_result):
        """Empty result -> valid dict with empty lists/zero values."""
        ts = generate_tearsheet(empty_backtest_result)
        assert len(ts["equity_curve"]) == 0
        assert len(ts["drawdown_chart"]) == 0
        assert ts["monthly_heatmap"]["years"] == []
        assert len(ts["rolling_sharpe"]) == 0
        assert ts["return_distribution"]["mean"] == 0.0

    def test_tearsheet_rolling_sharpe_format(self, realistic_backtest_result):
        """Rolling Sharpe entries have 'date' and 'sharpe' keys."""
        ts = generate_tearsheet(realistic_backtest_result)
        if len(ts["rolling_sharpe"]) > 0:
            for entry in ts["rolling_sharpe"]:
                assert "date" in entry
                assert "sharpe" in entry
                assert isinstance(entry["sharpe"], float)

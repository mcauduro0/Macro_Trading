"""Unit tests for MonetaryPolicyAgent and all 5 sub-models.

All tests use synthetic feature dicts or synthetic DataFrames — no database
connection required.  Mirrors the pattern from tests/test_agents/test_base.py.

Tests address requirements TESTV2-01 and TESTV2-02:
- TESTV2-01: Feature computation returns expected keys
- TESTV2-02: Model signals have correct direction for known inputs
"""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from src.agents.base import AgentSignal
from src.agents.features.monetary_features import MonetaryFeatureEngine
from src.agents.monetary_agent import (
    KalmanFilterRStar,
    MonetaryPolicyAgent,
    SelicPathModel,
    TaylorRuleModel,
    TermPremiumModel,
    UsFedAnalysis,
)
from src.core.enums import SignalDirection, SignalStrength


# ---------------------------------------------------------------------------
# Helper: build a synthetic AgentSignal
# ---------------------------------------------------------------------------
def make_signal(
    signal_id: str,
    direction: SignalDirection,
    strength: SignalStrength,
    confidence: float = 0.7,
    value: float = 1.0,
) -> AgentSignal:
    """Create a synthetic AgentSignal for composite/dampening tests."""
    return AgentSignal(
        signal_id=signal_id,
        agent_id="monetary_agent",
        timestamp=datetime.utcnow(),
        as_of_date=date(2024, 1, 31),
        direction=direction,
        strength=strength,
        confidence=confidence,
        value=value,
        horizon_days=252,
    )


# ---------------------------------------------------------------------------
# Helper: build synthetic MonetaryFeatureEngine input data dict
# ---------------------------------------------------------------------------
def _make_di_curve_df(
    tenor_1y: float = 12.5,
    tenor_2y: float = 12.8,
    tenor_5y: float = 13.0,
    tenor_10y: float = 13.2,
) -> pd.DataFrame:
    rows = [
        {
            "tenor_1y": tenor_1y,
            "tenor_2y": tenor_2y,
            "tenor_5y": tenor_5y,
            "tenor_10y": tenor_10y,
        }
        for _ in range(5)
    ]
    return pd.DataFrame(rows)


def _make_selic_df(value: float = 12.25, n: int = 60) -> pd.DataFrame:
    dates = pd.date_range("2019-01-01", periods=n, freq="ME")
    return pd.DataFrame({"value": [value] * n}, index=dates)


def _make_focus_df(value: float = 4.5, n: int = 60) -> pd.DataFrame:
    dates = pd.date_range("2019-01-01", periods=n, freq="ME")
    return pd.DataFrame({"value": [value] * n}, index=dates)


def _make_ibc_df(n: int = 60) -> pd.DataFrame:
    """IBC-Br monthly index ~150 with slight upward trend."""
    dates = pd.date_range("2019-01-01", periods=n, freq="ME")
    vals = [150.0 + i * 0.1 for i in range(n)]
    return pd.DataFrame({"value": vals}, index=dates)


def _make_synthetic_data(
    di_tenor_1y: float = 12.5,
    di_tenor_2y: float = 12.8,
    di_tenor_5y: float = 13.0,
    di_tenor_10y: float = 13.2,
    selic_value: float = 12.25,
    focus_value: float = 4.5,
    ibc_n: int = 60,
) -> dict:
    """Build a complete synthetic data dict for MonetaryFeatureEngine."""
    return {
        "di_curve": _make_di_curve_df(
            di_tenor_1y, di_tenor_2y, di_tenor_5y, di_tenor_10y
        ),
        "selic": _make_selic_df(selic_value),
        "focus": _make_focus_df(focus_value),
        "ibc_br": _make_ibc_df(ibc_n),
        "fed_funds": pd.DataFrame(
            {"value": [5.25]}, index=pd.date_range("2024-01-01", periods=1)
        ),
        "ust_curve": pd.DataFrame([{"ust_2y": 4.8, "ust_5y": 4.6, "ust_10y": 4.5}]),
        "nfci": pd.DataFrame(
            {"value": [-0.1]}, index=pd.date_range("2024-01-01", periods=1)
        ),
        "pce_core": pd.DataFrame(
            {"value": [3.2]}, index=pd.date_range("2024-01-01", periods=1)
        ),
        "us_breakeven": pd.DataFrame(
            {"value": [2.3]}, index=pd.date_range("2024-01-01", periods=1)
        ),
    }


# ===========================================================================
# Test 1: MonetaryFeatureEngine — required keys (TESTV2-01)
# ===========================================================================
class TestMonetaryFeatureEngineKeys:
    def test_monetary_feature_engine_keys(self) -> None:
        """Verify all required feature keys are present in output."""
        data = _make_synthetic_data()
        features = MonetaryFeatureEngine().compute(data, date(2024, 1, 31))

        required_keys = [
            "di_slope",
            "di_belly",
            "di_long_premium",
            "di_1y_real",
            "selic_target",
            "real_rate_gap",
            "policy_inertia",
            "focus_ipca_12m",
            "ibc_br_output_gap",
        ]
        for key in required_keys:
            assert key in features, f"Missing feature key: {key}"

        # Private keys for downstream models
        assert "_selic_history_series" in features
        assert "_focus_history_series" in features
        assert "_ibc_gap_series" in features

    def test_di_slope_value(self) -> None:
        """DI slope = di_10y - di_1y = 13.2 - 12.5 = 0.7."""
        data = _make_synthetic_data(
            di_tenor_1y=12.5, di_tenor_2y=12.8, di_tenor_5y=13.0, di_tenor_10y=13.2
        )
        features = MonetaryFeatureEngine().compute(data, date(2024, 1, 31))
        assert features["di_slope"] == pytest.approx(13.2 - 12.5, abs=0.01)

    def test_di_belly_value(self) -> None:
        """DI belly = di_2y - (di_1y + di_5y) / 2 = 12.8 - 12.75 = 0.05."""
        data = _make_synthetic_data(
            di_tenor_1y=12.5, di_tenor_2y=12.8, di_tenor_5y=13.0, di_tenor_10y=13.2
        )
        features = MonetaryFeatureEngine().compute(data, date(2024, 1, 31))
        expected_belly = 12.8 - (12.5 + 13.0) / 2.0
        assert features["di_belly"] == pytest.approx(expected_belly, abs=0.01)

    def test_empty_data_returns_nan_gracefully(self) -> None:
        """Empty data dict should return NaN values without raising exceptions."""
        features = MonetaryFeatureEngine().compute({}, date(2024, 1, 31))
        assert "di_slope" in features
        assert np.isnan(features["di_slope"])


# ===========================================================================
# Test 2: TaylorRuleModel — SHORT when gap=3.25 (STRONG) (TESTV2-02)
# ===========================================================================
class TestTaylorRuleModel:
    def test_gap_signal_short_strong(self) -> None:
        """Selic far above Taylor → SHORT/STRONG.

        i_star = 3.0 + 5.0 + 1.5*(5.0-3.0) + 0.5*1.0 + 0.5*0.0
               = 3.0 + 5.0 + 3.0 + 0.5 + 0.0 = 11.5
        gap = 14.75 - 11.5 = 3.25 (> MODERATE_BAND 1.5 → STRONG)
        """
        features = {
            "selic_target": 14.75,
            "focus_ipca_12m": 5.0,
            "ibc_br_output_gap": 1.0,
            "policy_inertia": 0.0,
        }
        sig = TaylorRuleModel().run(features, r_star=3.0, as_of_date=date(2024, 1, 31))

        assert sig.direction == SignalDirection.SHORT
        assert sig.strength == SignalStrength.STRONG
        assert sig.signal_id == "MONETARY_BR_TAYLOR"
        assert sig.value == pytest.approx(3.25, abs=0.01)
        assert sig.metadata["policy_gap_bps"] == pytest.approx(325.0, abs=1.0)

    def test_gap_signal_no_signal_below_floor(self) -> None:
        """Gap below 100bps floor → NO_SIGNAL.

        i_star = 3.0 + 4.5 + 1.5*(4.5-3.0) + 0.5*0 + 0.5*0 = 9.75
        gap = 10.0 - 9.75 = 0.25 < 1.0 floor → NO_SIGNAL
        """
        features = {
            "selic_target": 10.0,
            "focus_ipca_12m": 4.5,
            "ibc_br_output_gap": 0.0,
            "policy_inertia": 0.0,
        }
        sig = TaylorRuleModel().run(features, r_star=3.0, as_of_date=date(2024, 1, 31))

        assert sig.strength == SignalStrength.NO_SIGNAL
        assert sig.direction == SignalDirection.NEUTRAL

    def test_gap_signal_long(self) -> None:
        """Selic below Taylor → LONG.

        i_star = 3.0 + 4.5 + 1.5*(4.5-3.0) + 0.0 + 0.0 = 9.75
        gap = 8.0 - 9.75 = -1.75 → LONG (policy loose)
        |gap|=1.75 > 1.5 MODERATE_BAND → STRONG
        """
        features = {
            "selic_target": 8.0,
            "focus_ipca_12m": 4.5,
            "ibc_br_output_gap": 0.0,
            "policy_inertia": 0.0,
        }
        sig = TaylorRuleModel().run(features, r_star=3.0, as_of_date=date(2024, 1, 31))

        assert sig.direction == SignalDirection.LONG
        assert sig.strength == SignalStrength.STRONG

    def test_gap_signal_moderate(self) -> None:
        """Gap in [1.0, 1.5) → MODERATE.

        i_star = 3.0 + 4.5 + 1.5*(4.5-3.0) + 0.0 + 0.0 = 9.75
        gap = 11.0 - 9.75 = 1.25 → in [1.0, 1.5) → MODERATE SHORT
        """
        features = {
            "selic_target": 11.0,
            "focus_ipca_12m": 4.5,
            "ibc_br_output_gap": 0.0,
            "policy_inertia": 0.0,
        }
        sig = TaylorRuleModel().run(features, r_star=3.0, as_of_date=date(2024, 1, 31))

        assert sig.direction == SignalDirection.SHORT
        assert sig.strength == SignalStrength.MODERATE

    def test_nan_feature_returns_no_signal(self) -> None:
        """NaN in any required feature → NO_SIGNAL."""
        features = {
            "selic_target": float("nan"),
            "focus_ipca_12m": 5.0,
            "ibc_br_output_gap": 1.0,
            "policy_inertia": 0.0,
        }
        sig = TaylorRuleModel().run(features, r_star=3.0, as_of_date=date(2024, 1, 31))
        assert sig.strength == SignalStrength.NO_SIGNAL

    def test_gap_floor_is_100bps(self) -> None:
        """GAP_FLOOR must equal 1.0 (100bps) — locked per CONTEXT.md."""
        assert TaylorRuleModel.GAP_FLOOR == 1.0


# ===========================================================================
# Test 3: KalmanFilterRStar (TESTV2-01, TESTV2-02)
# ===========================================================================
class TestKalmanFilterRStar:
    def test_returns_float_r_star(self) -> None:
        """Sufficient data → returns (float, float) r_star, uncertainty."""
        selic_series = pd.Series([12.5] * 60)
        expectations_series = pd.Series([4.5] * 60)
        gap_series = pd.Series([0.5] * 60)

        r_star, uncertainty = KalmanFilterRStar().estimate(
            selic_series, expectations_series, gap_series
        )

        assert isinstance(r_star, float)
        assert 0.0 < r_star < 20.0  # Reasonable r* range
        assert isinstance(uncertainty, float)

    def test_r_star_reasonable_value(self) -> None:
        """Selic - expectations ≈ 8.0 → LW 2-state model: r* + g*/2 ≈ 8.0.

        The Laubach-Williams model decomposes the observed real rate (8.0)
        into r* and g*/2. With zero output gap, the filter distributes the
        signal across both states, so r* alone is lower than 8.0.
        """
        selic_series = pd.Series([12.5] * 60)
        expectations_series = pd.Series([4.5] * 60)
        gap_series = pd.Series([0.0] * 60)

        r_star, _ = KalmanFilterRStar().estimate(
            selic_series, expectations_series, gap_series
        )
        # LW 2-state: obs = r* + 0.5*g*, so r* < 8.0 (g* absorbs part)
        # r* should be positive and within a reasonable range
        assert 2.0 < r_star < 8.5

    def test_insufficient_data_returns_default(self) -> None:
        """Less than MIN_OBS observations → (DEFAULT_R_STAR, inf)."""
        selic_series = pd.Series([12.5] * 10)
        expectations_series = pd.Series([4.5] * 10)
        gap_series = pd.Series([0.5] * 10)

        r_star, uncertainty = KalmanFilterRStar().estimate(
            selic_series, expectations_series, gap_series
        )

        assert r_star == KalmanFilterRStar.DEFAULT_R_STAR  # 3.0
        assert uncertainty == float("inf")

    def test_min_obs_is_24(self) -> None:
        """Exactly at boundary: 24 observations should succeed (not return default)."""
        selic_series = pd.Series([12.0] * 24)
        expectations_series = pd.Series([4.0] * 24)
        gap_series = pd.Series([0.0] * 24)

        r_star, uncertainty = KalmanFilterRStar().estimate(
            selic_series, expectations_series, gap_series
        )

        # 24 obs should run the filter, not return default
        assert r_star != KalmanFilterRStar.DEFAULT_R_STAR or uncertainty != float("inf")


# ===========================================================================
# Test 4: SelicPathModel (TESTV2-01, TESTV2-02)
# ===========================================================================
class TestSelicPathModel:
    def test_market_above_model_returns_short(self) -> None:
        """market DI > model Taylor → SHORT (fade hike pricing).

        di_1y=13.5, i_star=11.5 → market_vs_model=2.0 → SHORT
        """
        features = {
            "di_1y": 13.5,
            "_as_of_date": date(2024, 1, 31),
        }
        sig = SelicPathModel().run(features, i_star=11.5, as_of_date=date(2024, 1, 31))

        assert sig.direction == SignalDirection.SHORT
        assert sig.signal_id == "MONETARY_BR_SELIC_PATH"
        assert sig.value == pytest.approx(2.0, abs=0.01)

    def test_market_below_model_returns_long(self) -> None:
        """market DI < model Taylor → LONG (market underpricing hike risk).

        di_1y=9.0, i_star=11.5 → market_vs_model=-2.5 → LONG
        """
        features = {
            "di_1y": 9.0,
            "_as_of_date": date(2024, 1, 31),
        }
        sig = SelicPathModel().run(features, i_star=11.5, as_of_date=date(2024, 1, 31))

        assert sig.direction == SignalDirection.LONG
        assert sig.signal_id == "MONETARY_BR_SELIC_PATH"

    def test_below_threshold_returns_no_signal(self) -> None:
        """Deviation below 50bps → NO_SIGNAL."""
        features = {
            "di_1y": 11.7,
            "_as_of_date": date(2024, 1, 31),
        }
        sig = SelicPathModel().run(features, i_star=11.5, as_of_date=date(2024, 1, 31))

        assert sig.strength == SignalStrength.NO_SIGNAL

    def test_nan_di_1y_returns_no_signal(self) -> None:
        """NaN di_1y → NO_SIGNAL."""
        features = {
            "di_1y": float("nan"),
            "_as_of_date": date(2024, 1, 31),
        }
        sig = SelicPathModel().run(features, i_star=11.5, as_of_date=date(2024, 1, 31))

        assert sig.strength == SignalStrength.NO_SIGNAL


# ===========================================================================
# Test 5: TermPremiumModel
# ===========================================================================
class TestTermPremiumModel:
    def test_high_tp_returns_long(self) -> None:
        """High TP z-score → LONG (duration attractive).

        history mean=1.0, std=0.5; current_tp=7.0 → z=(7-1)/0.5=12 >> 1.5 → LONG
        """
        tp_series = pd.Series([1.0] * 24)
        # Override mean/std: set mean=1.0, std=0.5 by adjusting values
        tp_series = pd.Series([0.5, 1.5] * 12)  # mean=1.0, std≈0.5
        features = {
            "di_10y": 15.0,
            "focus_ipca_12m": 5.0,
            "_r_star_estimate": 3.0,
            "_tp_history": tp_series,
        }
        sig = TermPremiumModel().run(features, as_of_date=date(2024, 1, 31))

        # current_tp = 15.0 - (5.0+3.0) = 7.0; z >> Z_HIGH=1.5 → LONG
        assert sig.direction == SignalDirection.LONG
        assert sig.signal_id == "MONETARY_BR_TERM_PREMIUM"

    def test_low_tp_returns_short(self) -> None:
        """Very low TP z-score → SHORT (duration expensive).

        history mean=7.0, std=0.5; current_tp=2.0 → z=(2-7)/0.5=-10 << -1.5 → SHORT
        """
        tp_series = pd.Series([7.5, 6.5] * 12)  # mean=7.0, std≈0.5
        features = {
            "di_10y": 9.5,
            "focus_ipca_12m": 4.0,
            "_r_star_estimate": 3.0,
            "_tp_history": tp_series,
        }
        # current_tp = 9.5 - (4.0+3.0) = 2.5; z << -1.5 → SHORT
        sig = TermPremiumModel().run(features, as_of_date=date(2024, 1, 31))

        assert sig.direction == SignalDirection.SHORT

    def test_insufficient_history_returns_no_signal(self) -> None:
        """Less than MIN_HISTORY months → NO_SIGNAL."""
        features = {
            "di_10y": 13.0,
            "focus_ipca_12m": 4.5,
            "_r_star_estimate": 3.0,
            "_tp_history": pd.Series([1.0] * 5),  # Only 5 obs < 12
        }
        sig = TermPremiumModel().run(features, as_of_date=date(2024, 1, 31))

        assert sig.strength == SignalStrength.NO_SIGNAL


# ===========================================================================
# Test 6: MonetaryPolicyAgent composite and dampening
# ===========================================================================
class TestMonetaryComposite:
    def _get_agent(self) -> MonetaryPolicyAgent:
        """Create agent with MagicMock loader (no DB required)."""
        loader = MagicMock()
        return MonetaryPolicyAgent(loader)

    def test_composite_with_conflict_dampening(self) -> None:
        """2 SHORT vs 1 LONG → dampening=0.70, direction=SHORT.

        Taylor=SHORT, SelicPath=SHORT, TermPremium=LONG — conflict detected.
        """
        agent = self._get_agent()

        signals = [
            make_signal(
                "MONETARY_BR_TAYLOR", SignalDirection.SHORT, SignalStrength.STRONG, 0.85
            ),
            make_signal(
                "MONETARY_BR_SELIC_PATH",
                SignalDirection.SHORT,
                SignalStrength.MODERATE,
                0.65,
            ),
            make_signal(
                "MONETARY_BR_TERM_PREMIUM",
                SignalDirection.LONG,
                SignalStrength.MODERATE,
                0.65,
            ),
        ]

        composite = agent._build_composite(signals, date(2024, 1, 31))

        assert composite.metadata["dampening"] == 0.70
        assert composite.direction == SignalDirection.SHORT
        assert composite.signal_id == "MONETARY_BR_COMPOSITE"

    def test_composite_no_conflict_full_weight(self) -> None:
        """All 3 SHORT → no conflict → dampening=1.0."""
        agent = self._get_agent()

        signals = [
            make_signal(
                "MONETARY_BR_TAYLOR", SignalDirection.SHORT, SignalStrength.STRONG, 0.85
            ),
            make_signal(
                "MONETARY_BR_SELIC_PATH",
                SignalDirection.SHORT,
                SignalStrength.MODERATE,
                0.65,
            ),
            make_signal(
                "MONETARY_BR_TERM_PREMIUM",
                SignalDirection.SHORT,
                SignalStrength.MODERATE,
                0.65,
            ),
        ]

        composite = agent._build_composite(signals, date(2024, 1, 31))

        assert composite.metadata["dampening"] == 1.0
        assert composite.direction == SignalDirection.SHORT
        assert composite.signal_id == "MONETARY_BR_COMPOSITE"

    def test_composite_all_no_signal(self) -> None:
        """All sub-signals NO_SIGNAL → composite is NO_SIGNAL."""
        agent = self._get_agent()

        signals = [
            make_signal(
                "MONETARY_BR_TAYLOR",
                SignalDirection.NEUTRAL,
                SignalStrength.NO_SIGNAL,
                0.0,
            ),
            make_signal(
                "MONETARY_BR_SELIC_PATH",
                SignalDirection.NEUTRAL,
                SignalStrength.NO_SIGNAL,
                0.0,
            ),
            make_signal(
                "MONETARY_BR_TERM_PREMIUM",
                SignalDirection.NEUTRAL,
                SignalStrength.NO_SIGNAL,
                0.0,
            ),
        ]

        composite = agent._build_composite(signals, date(2024, 1, 31))

        assert composite.strength == SignalStrength.NO_SIGNAL
        assert composite.signal_id == "MONETARY_BR_COMPOSITE"

    def test_composite_weights_sum_to_one(self) -> None:
        """Effective weights in metadata should sum to ~1.0."""
        agent = self._get_agent()

        signals = [
            make_signal(
                "MONETARY_BR_TAYLOR", SignalDirection.LONG, SignalStrength.STRONG, 0.85
            ),
            make_signal(
                "MONETARY_BR_SELIC_PATH",
                SignalDirection.LONG,
                SignalStrength.MODERATE,
                0.65,
            ),
            make_signal(
                "MONETARY_BR_TERM_PREMIUM",
                SignalDirection.LONG,
                SignalStrength.MODERATE,
                0.65,
            ),
        ]

        composite = agent._build_composite(signals, date(2024, 1, 31))
        weights_sum = sum(composite.metadata["weights"].values())

        assert weights_sum == pytest.approx(1.0, abs=0.01)


# ===========================================================================
# Test 7: UsFedAnalysis
# ===========================================================================
class TestUsFedAnalysis:
    def test_restrictive_fed_returns_short(self) -> None:
        """Fed above Taylor (restrictive) → SHORT (tight global = BRL bearish).

        pce=4.0: i_star = 2.5 + 1.5*(4.0-2.0) + 0 = 5.5
        gap = 5.75 - 5.5 = 0.25 < 0.5 floor → NO_SIGNAL. Use pce=5.0:
        i_star = 2.5+1.5*(5.0-2.0)+0 = 7.0; gap=5.5-7.0 → negative. Try:
        fed=7.5, pce=3.0: i_star=2.5+1.5*(3.0-2.0)+0=4.0; gap=7.5-4.0=3.5 → SHORT
        """
        features = {
            "fed_funds_rate": 7.5,
            "us_pce_core_yoy": 3.0,
            "ust_slope": 0.5,
        }
        sig = UsFedAnalysis().run(features, as_of_date=date(2024, 1, 31))

        assert sig.direction == SignalDirection.SHORT
        assert sig.signal_id == "MONETARY_US_FED_STANCE"

    def test_accommodative_fed_returns_long(self) -> None:
        """Fed below Taylor (accommodative) → LONG (easy global = BRL supportive).

        fed=2.0, pce=3.0: i_star=2.5+1.5*(3.0-2.0)+0=4.0; gap=2.0-4.0=-2.0 → LONG
        """
        features = {
            "fed_funds_rate": 2.0,
            "us_pce_core_yoy": 3.0,
            "ust_slope": 0.5,
        }
        sig = UsFedAnalysis().run(features, as_of_date=date(2024, 1, 31))

        assert sig.direction == SignalDirection.LONG

    def test_missing_pce_returns_no_signal(self) -> None:
        """NaN PCE → NO_SIGNAL."""
        features = {
            "fed_funds_rate": 5.25,
            "us_pce_core_yoy": float("nan"),
            "ust_slope": -0.2,
        }
        sig = UsFedAnalysis().run(features, as_of_date=date(2024, 1, 31))
        assert sig.strength == SignalStrength.NO_SIGNAL

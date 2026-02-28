"""Unit tests for InflationAgent models and InflationFeatureEngine.

All tests use synthetic data and mock the PointInTimeDataLoader.
No database connection required.
"""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from src.agents.features.inflation_features import InflationFeatureEngine
from src.agents.inflation_agent import (
    InflationAgent,
    InflationPersistenceModel,
    InflationSurpriseModel,
    IpcaBottomUpModel,
    PhillipsCurveModel,
    UsInflationTrendModel,
)
from src.core.enums import SignalDirection, SignalStrength

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_MONTHLY_INDEX_60 = pd.date_range("2019-01-31", periods=60, freq="ME")
_MONTHLY_INDEX_20 = pd.date_range("2022-04-30", periods=20, freq="ME")
_AS_OF_DATE = date(2024, 1, 31)


def _monthly_df(values, index=None) -> pd.DataFrame:
    """Build a simple monthly DataFrame with a 'value' column."""
    idx = index if index is not None else _MONTHLY_INDEX_60
    return pd.DataFrame({"value": values}, index=idx)


def _flat_df(val: float = 0.5, n: int = 60) -> pd.DataFrame:
    """Monthly DataFrame with constant value column."""
    return _monthly_df([val] * n)


def _make_surprise_series(
    actual_mom: float = 0.6, focus_mom: float = 0.3, n: int = 15
) -> pd.DataFrame:
    """Build a _surprise_series DataFrame for InflationSurpriseModel."""
    idx = pd.date_range("2022-10-31", periods=n, freq="ME")
    return pd.DataFrame(
        {
            "actual_mom": [actual_mom] * n,
            "focus_mom_median": [focus_mom] * n,
        },
        index=idx,
    )


def _make_core_series_df(val: float = 5.0, n: int = 120) -> pd.DataFrame:
    """Build a _raw_ols_data DataFrame suitable for PhillipsCurveModel."""
    idx = pd.date_range("2014-01-31", periods=n, freq="ME")
    return pd.DataFrame(
        {
            "core_yoy": [val] * n,
            "expectations_12m": [4.5] * n,
            "output_gap": [1.5] * n,
            "usdbrl_yoy": [8.0] * n,
            "crb_yoy": [3.0] * n,
        },
        index=idx,
    )


def _make_agent() -> InflationAgent:
    """Create an InflationAgent with a MagicMock loader."""
    loader = MagicMock()
    agent = InflationAgent(loader)
    # Patch out DB persistence so tests don't touch a real DB
    agent._persist_signals = MagicMock(return_value=0)  # type: ignore[method-assign]
    agent._persist_report = MagicMock()  # type: ignore[method-assign]
    return agent


# ---------------------------------------------------------------------------
# Test 1: InflationFeatureEngine key completeness
# ---------------------------------------------------------------------------
class TestInflationFeatureEngineKeys:
    """Addresses requirement TESTV2-01: feature engine key verification."""

    def _make_data(self) -> dict:
        """Build minimal synthetic data dict for InflationFeatureEngine."""
        mom_df = _flat_df(0.5)
        return {
            "ipca": mom_df.copy(),
            "ipca_cores": {
                "smoothed": mom_df.copy(),
                "trimmed": mom_df.copy(),
                "ex_fe": mom_df.copy(),
            },
            "ipca_components": {
                key: mom_df.copy()
                for key in [
                    "food_home",
                    "food_away",
                    "housing",
                    "clothing",
                    "health",
                    "personal_care",
                    "education",
                    "transport",
                    "communication",
                ]
            },
            "ipca_services": mom_df.copy(),
            "ipca_industrial": mom_df.copy(),
            "ipca_diffusion": _flat_df(70.0),
            "focus": pd.DataFrame(
                {"ipca_12m": [5.5] * 60},
                index=_MONTHLY_INDEX_60,
            ),
            "ibc_br": _flat_df(120.0),
            "usdbrl": pd.DataFrame(
                {"adjusted_close": [5.0] * 300},
                index=pd.date_range("2020-08-31", periods=300, freq="B"),
            ),
            "crb": pd.DataFrame(
                {"adjusted_close": [300.0] * 300},
                index=pd.date_range("2020-08-31", periods=300, freq="B"),
            ),
            "us_cpi": _flat_df(1.0, 60),
            "us_pce": pd.DataFrame(
                {"value": list(range(100, 160))},
                index=_MONTHLY_INDEX_60,
            ),
            "us_pce_supercore": _flat_df(0.3),
            "us_breakevens": pd.DataFrame(
                {"be_5y": [2.3] * 60, "be_10y": [2.5] * 60},
                index=_MONTHLY_INDEX_60,
            ),
            "us_michigan": pd.DataFrame(
                {"mich_1y": [3.1] * 60, "mich_5y": [2.9] * 60},
                index=_MONTHLY_INDEX_60,
            ),
        }

    def test_inflation_feature_engine_keys(self) -> None:
        """All required feature keys must be present in compute() output."""
        engine = InflationFeatureEngine()
        data = self._make_data()
        features = engine.compute(data, _AS_OF_DATE)

        required_keys = [
            "ipca_yoy",
            "ipca_mom",
            "ipca_core_smoothed",
            "focus_ipca_12m",
            "ibc_br_level",
            "ibc_br_output_gap",
            "usdbrl_yoy",
            "crb_yoy",
            "us_pce_core_yoy",
            "us_pce_core_3m_saar",
            "us_pce_target_gap",
        ]

        for key in required_keys:
            assert key in features, f"Missing required feature key: {key}"

        # Private model-data keys
        assert "_raw_ols_data" in features, "Missing _raw_ols_data"
        assert "_raw_components" in features, "Missing _raw_components"


# ---------------------------------------------------------------------------
# Test 2 & 3: PhillipsCurveModel direction and NO_SIGNAL path
# ---------------------------------------------------------------------------
class TestPhillipsCurveModel:
    """Addresses requirement TESTV2-02: PhillipsCurve OLS direction and fallback."""

    def test_phillips_curve_model_direction_long(self) -> None:
        """High-inflation scenario should return LONG direction."""
        df = _make_core_series_df(
            val=8.0, n=120
        )  # core_yoy=8%, well above 3.5% threshold
        features = {"_raw_ols_data": df, "_as_of_date": _AS_OF_DATE}

        signal = PhillipsCurveModel().run(features, _AS_OF_DATE)

        assert (
            signal.direction == SignalDirection.LONG
        ), f"Expected LONG for high-inflation scenario, got {signal.direction}"
        assert signal.signal_id == "INFLATION_BR_PHILLIPS"
        assert 0.0 <= signal.confidence <= 1.0

    def test_phillips_curve_model_no_signal_insufficient_data(self) -> None:
        """Fewer than MIN_OBS rows must return NO_SIGNAL."""
        df = _make_core_series_df(val=5.0, n=10)
        features = {"_raw_ols_data": df, "_as_of_date": _AS_OF_DATE}

        signal = PhillipsCurveModel().run(features, _AS_OF_DATE)

        assert signal.strength == SignalStrength.NO_SIGNAL
        assert signal.confidence == 0.0

    def test_phillips_curve_model_returns_correct_signal_id(self) -> None:
        """Signal ID must be INFLATION_BR_PHILLIPS regardless of direction."""
        df = _make_core_series_df(val=5.0, n=10)
        features = {"_raw_ols_data": df, "_as_of_date": _AS_OF_DATE}
        signal = PhillipsCurveModel().run(features, _AS_OF_DATE)
        assert signal.signal_id == "INFLATION_BR_PHILLIPS"


# ---------------------------------------------------------------------------
# Test 4: IpcaBottomUpModel seasonal projection
# ---------------------------------------------------------------------------
class TestIpcaBottomUpModel:
    """Addresses requirement TESTV2-01: bottom-up seasonal forecast."""

    def test_ipca_bottom_up_seasonal(self) -> None:
        """0.5 MoM for all components should produce forecast > 3% target."""
        comp_data = {
            key: _flat_df(0.5)
            for key in [
                "food_home",
                "food_away",
                "housing",
                "clothing",
                "health",
                "personal_care",
                "education",
                "transport",
                "communication",
            ]
        }
        features = {"_raw_components": comp_data, "_as_of_date": _AS_OF_DATE}

        signal = IpcaBottomUpModel().run(features, _AS_OF_DATE)

        # Signal should NOT be NO_SIGNAL (seasonal factors computed successfully)
        assert (
            signal.strength != SignalStrength.NO_SIGNAL
        ), "Expected a non-NO_SIGNAL result"
        # 0.5 MoM * 12 months annualized (compounded) ~6.2%, well above 3% target
        assert signal.value > 3.0, f"Expected forecast > 3.0, got {signal.value}"
        assert isinstance(signal.value, float)

    def test_ipca_bottom_up_no_signal_empty_components(self) -> None:
        """No components should return NO_SIGNAL."""
        features = {"_raw_components": {}, "_as_of_date": _AS_OF_DATE}
        signal = IpcaBottomUpModel().run(features, _AS_OF_DATE)
        assert signal.strength == SignalStrength.NO_SIGNAL


# ---------------------------------------------------------------------------
# Tests 5 & 6: InflationSurpriseModel
# ---------------------------------------------------------------------------
class TestInflationSurpriseModel:
    """Addresses requirements TESTV2-01 and TESTV2-02 for surprise model."""

    def test_inflation_surprise_model_long_signal(self) -> None:
        """Persistent upside surprise should return LONG (hawkish).

        To ensure z > 1.0 (Z_FIRE), last 3M must have a materially higher
        surprise than the preceding 9 months.  We set the first 12 months
        to near-zero surprise (actual=focus=0.4) then the last 3 months to
        strong upside (actual=0.9, focus=0.3), creating a z-score >> 1.0.
        """
        idx = pd.date_range("2022-10-31", periods=15, freq="ME")
        actual = [0.4] * 12 + [0.9, 0.9, 0.9]  # last 3M: strong upside
        focus = [0.4] * 12 + [0.3, 0.3, 0.3]  # focus stays low
        surprise_df = pd.DataFrame(
            {"actual_mom": actual, "focus_mom_median": focus},
            index=idx,
        )
        features = {"_surprise_series": surprise_df, "_as_of_date": _AS_OF_DATE}

        signal = InflationSurpriseModel().run(features, _AS_OF_DATE)

        assert signal.direction == SignalDirection.LONG, (
            f"Expected LONG for upside surprise, got {signal.direction} "
            f"(signal strength: {signal.strength}, z={signal.value})"
        )
        # Signal should fire (strength not NO_SIGNAL)
        assert signal.strength in {
            SignalStrength.MODERATE,
            SignalStrength.STRONG,
            SignalStrength.WEAK,
        }, f"Expected a non-NO_SIGNAL strength, got {signal.strength}"

    def test_inflation_surprise_model_strong_signal(self) -> None:
        """Extreme upside surprise should return STRONG strength (|z| > 2.0)."""
        # actual_mom=0.9, focus_mom=0.1 → massive 0.8pp surprise consistently
        idx = pd.date_range("2022-06-30", periods=15, freq="ME")
        # Make last 3 months extreme, earlier months neutral to create high z
        actual = [0.4] * 12 + [1.2, 1.2, 1.2]  # last 3M extreme upside
        focus = [0.4] * 15  # flat consensus
        surprise_df = pd.DataFrame(
            {"actual_mom": actual, "focus_mom_median": focus},
            index=idx,
        )
        features = {"_surprise_series": surprise_df, "_as_of_date": _AS_OF_DATE}

        signal = InflationSurpriseModel().run(features, _AS_OF_DATE)

        # With extreme 3M surprise vs flat trailing 12M, z should be >> 2
        assert signal.strength == SignalStrength.STRONG, (
            f"Expected STRONG for extreme upside, got {signal.strength} "
            f"(z={signal.value}, direction={signal.direction})"
        )
        assert signal.direction == SignalDirection.LONG

    def test_inflation_surprise_model_no_signal_insufficient_data(self) -> None:
        """Fewer than 12 months of data should return NO_SIGNAL."""
        surprise_df = _make_surprise_series(n=8)
        features = {"_surprise_series": surprise_df, "_as_of_date": _AS_OF_DATE}
        signal = InflationSurpriseModel().run(features, _AS_OF_DATE)
        assert signal.strength == SignalStrength.NO_SIGNAL

    def test_inflation_surprise_model_no_signal_empty(self) -> None:
        """Empty surprise series should return NO_SIGNAL."""
        features = {"_surprise_series": pd.DataFrame(), "_as_of_date": _AS_OF_DATE}
        signal = InflationSurpriseModel().run(features, _AS_OF_DATE)
        assert signal.strength == SignalStrength.NO_SIGNAL
        assert signal.signal_id == "INFLATION_BR_SURPRISE"


# ---------------------------------------------------------------------------
# Tests 7 & 8: InflationPersistenceModel
# ---------------------------------------------------------------------------
class TestInflationPersistenceModel:
    """Addresses requirement TESTV2-01 for persistence score."""

    def test_persistence_model_long_high_diffusion(self) -> None:
        """High diffusion + well-anchored expectations + high services → LONG.

        Designed to produce composite score clearly > 60:
        - diffusion=95 → sub=95
        - core_accel: flat (no trend change) → sub=50
        - services_saar=12.0 → sub=12/15*100=80
        - focus=3.0 exactly on BCB target → anchoring_sub=100
        Expected score ≈ (95+50+80+100)/4 = 81.25 >> 60
        """
        n = 60
        idx = pd.date_range("2019-01-31", periods=n, freq="ME")
        # Flat core (no acceleration) so core_accel=50
        ols_df = pd.DataFrame(
            {
                "core_yoy": [6.0] * n,
                "expectations_12m": [5.0] * n,
                "output_gap": [2.0] * n,
                "usdbrl_yoy": [10.0] * n,
                "crb_yoy": [5.0] * n,
            },
            index=idx,
        )

        features = {
            "ipca_diffusion": 95.0,  # high diffusion: sub=95
            "ipca_core_smoothed": 7.0,
            "_raw_ols_data": ols_df,
            "_services_3m_saar": 12.0,  # services SAAR: sub=80
            "focus_ipca_12m": 3.0,  # exactly on target: anchoring_sub=100
            "_as_of_date": _AS_OF_DATE,
        }

        signal = InflationPersistenceModel().run(features, _AS_OF_DATE)

        assert signal.direction == SignalDirection.LONG, (
            f"Expected LONG for high persistence scenario, got {signal.direction} "
            f"(score={signal.value})"
        )

    def test_persistence_model_short_low_diffusion(self) -> None:
        """Low diffusion + unanchored expectations (far above) → SHORT.

        Designed to produce composite score clearly < 40:
        - diffusion=5 → sub=5
        - core_accel: flat → sub=50
        - services_saar=0.5 → sub=0.5/15*100=3.3
        - focus=8.0 → anchoring_sub=max(0, 100-|8-3|*20)=0
        Expected score ≈ (5+50+3.3+0)/4 = 14.6 << 40
        """
        n = 60
        idx = pd.date_range("2019-01-31", periods=n, freq="ME")
        # Flat core (no acceleration) so core_accel=50
        ols_df = pd.DataFrame(
            {
                "core_yoy": [2.0] * n,
                "expectations_12m": [2.5] * n,
                "output_gap": [-2.0] * n,
                "usdbrl_yoy": [-3.0] * n,
                "crb_yoy": [-2.0] * n,
            },
            index=idx,
        )

        features = {
            "ipca_diffusion": 5.0,  # very low diffusion: sub=5
            "ipca_core_smoothed": 1.5,
            "_raw_ols_data": ols_df,
            "_services_3m_saar": 0.5,  # very low services SAAR: sub≈3.3
            "focus_ipca_12m": 8.0,  # far above target: anchoring_sub=0
            "_as_of_date": _AS_OF_DATE,
        }

        signal = InflationPersistenceModel().run(features, _AS_OF_DATE)

        assert signal.direction == SignalDirection.SHORT, (
            f"Expected SHORT for low persistence scenario, got {signal.direction} "
            f"(score={signal.value})"
        )

    def test_persistence_model_no_signal_all_nan(self) -> None:
        """All NaN inputs should return NO_SIGNAL."""
        features = {
            "ipca_diffusion": np.nan,
            "ipca_core_smoothed": np.nan,
            "_raw_ols_data": pd.DataFrame(
                columns=[
                    "core_yoy",
                    "expectations_12m",
                    "output_gap",
                    "usdbrl_yoy",
                    "crb_yoy",
                ]
            ),
            "_services_3m_saar": np.nan,
            "focus_ipca_12m": np.nan,
            "_as_of_date": _AS_OF_DATE,
        }
        signal = InflationPersistenceModel().run(features, _AS_OF_DATE)
        assert signal.strength == SignalStrength.NO_SIGNAL


# ---------------------------------------------------------------------------
# Test 9: UsInflationTrendModel
# ---------------------------------------------------------------------------
class TestUsInflationTrendModel:
    """Tests for US inflation trend signal."""

    def test_us_inflation_trend_above_target(self) -> None:
        """PCE core 3.5% > 2% target and YoY > target → LONG."""
        features = {
            "us_pce_core_3m_saar": 3.5,
            "us_pce_core_yoy": 3.2,
            "us_pce_supercore_mom_3m": 0.3,
        }
        signal = UsInflationTrendModel().run(features, _AS_OF_DATE)
        assert signal.direction == SignalDirection.LONG
        assert signal.signal_id == "INFLATION_US_TREND"
        assert 0.0 <= signal.confidence <= 1.0

    def test_us_inflation_trend_below_target(self) -> None:
        """PCE core 1.2% < 2% target → SHORT."""
        features = {
            "us_pce_core_3m_saar": 1.2,
            "us_pce_core_yoy": 1.5,
            "us_pce_supercore_mom_3m": -0.1,
        }
        signal = UsInflationTrendModel().run(features, _AS_OF_DATE)
        assert signal.direction == SignalDirection.SHORT

    def test_us_inflation_trend_no_signal_all_nan(self) -> None:
        """All NaN → NO_SIGNAL."""
        features = {
            "us_pce_core_3m_saar": np.nan,
            "us_pce_core_yoy": np.nan,
            "us_pce_supercore_mom_3m": np.nan,
        }
        signal = UsInflationTrendModel().run(features, _AS_OF_DATE)
        assert signal.strength == SignalStrength.NO_SIGNAL

    def test_us_inflation_trend_horizon_days(self) -> None:
        """UsInflationTrendModel should use horizon_days=252 (annual)."""
        features = {
            "us_pce_core_3m_saar": 3.0,
            "us_pce_core_yoy": 3.0,
            "us_pce_supercore_mom_3m": 0.2,
        }
        signal = UsInflationTrendModel().run(features, _AS_OF_DATE)
        assert signal.horizon_days == 252


# ---------------------------------------------------------------------------
# Test 10: INFLATION_BR_COMPOSITE majority vote
# ---------------------------------------------------------------------------
class TestInflationComposite:
    """Tests for InflationAgent._build_composite()."""

    def _make_br_signal(
        self,
        signal_id: str,
        direction: SignalDirection,
        confidence: float = 0.7,
    ):
        return __import__("src.agents.base", fromlist=["AgentSignal"]).AgentSignal(
            signal_id=signal_id,
            agent_id="inflation_agent",
            timestamp=datetime.utcnow(),
            as_of_date=_AS_OF_DATE,
            direction=direction,
            strength=(
                SignalStrength.MODERATE if confidence >= 0.5 else SignalStrength.WEAK
            ),
            confidence=confidence,
            value=confidence,
            horizon_days=252,
        )

    def test_inflation_composite_majority_vote(self) -> None:
        """3 LONG + 1 SHORT (unweighted) → composite should be LONG."""
        signals = [
            self._make_br_signal("INFLATION_BR_PHILLIPS", SignalDirection.LONG, 0.8),
            self._make_br_signal("INFLATION_BR_BOTTOMUP", SignalDirection.LONG, 0.7),
            self._make_br_signal("INFLATION_BR_SURPRISE", SignalDirection.LONG, 0.6),
            self._make_br_signal(
                "INFLATION_BR_PERSISTENCE", SignalDirection.SHORT, 0.6
            ),
            # US trend is excluded from BR composite:
            self._make_br_signal("INFLATION_US_TREND", SignalDirection.SHORT, 0.9),
        ]

        agent = _make_agent()
        composite = agent._build_composite(signals, _AS_OF_DATE)

        assert (
            composite.direction == SignalDirection.LONG
        ), f"Expected LONG majority vote, got {composite.direction}"
        assert composite.signal_id == "INFLATION_BR_COMPOSITE"
        assert 0.0 < composite.confidence <= 1.0

    def test_inflation_composite_conflict_dampening(self) -> None:
        """2 LONG + 2 SHORT (all BR) → dampening=0.70 applied."""
        signals = [
            self._make_br_signal("INFLATION_BR_PHILLIPS", SignalDirection.LONG, 0.8),
            self._make_br_signal("INFLATION_BR_BOTTOMUP", SignalDirection.LONG, 0.8),
            self._make_br_signal("INFLATION_BR_SURPRISE", SignalDirection.SHORT, 0.8),
            self._make_br_signal(
                "INFLATION_BR_PERSISTENCE", SignalDirection.SHORT, 0.8
            ),
        ]

        agent = _make_agent()
        composite = agent._build_composite(signals, _AS_OF_DATE)

        # With 2 disagreements (>= 2), dampening must be 0.70
        assert composite.metadata["dampening"] == pytest.approx(
            0.70
        ), f"Expected dampening=0.70, got {composite.metadata['dampening']}"
        # Composite confidence should be < undampened weighted confidence
        undampened_conf = 0.8  # all sigs at 0.8, weights balanced
        assert composite.confidence < undampened_conf

    def test_inflation_composite_no_active_signals(self) -> None:
        """If all BR signals are NO_SIGNAL, composite must be NO_SIGNAL."""
        from src.agents.base import AgentSignal

        signals = [
            AgentSignal(
                signal_id="INFLATION_BR_PHILLIPS",
                agent_id="inflation_agent",
                timestamp=datetime.utcnow(),
                as_of_date=_AS_OF_DATE,
                direction=SignalDirection.NEUTRAL,
                strength=SignalStrength.NO_SIGNAL,
                confidence=0.0,
                value=0.0,
                horizon_days=252,
            )
        ]

        agent = _make_agent()
        composite = agent._build_composite(signals, _AS_OF_DATE)
        assert composite.strength == SignalStrength.NO_SIGNAL

    def test_inflation_composite_no_dampening_consensus(self) -> None:
        """Consensus (all LONG, < 2 conflicts) should have dampening=1.0."""
        signals = [
            self._make_br_signal("INFLATION_BR_PHILLIPS", SignalDirection.LONG, 0.9),
            self._make_br_signal("INFLATION_BR_BOTTOMUP", SignalDirection.LONG, 0.8),
            self._make_br_signal("INFLATION_BR_SURPRISE", SignalDirection.LONG, 0.7),
            self._make_br_signal(
                "INFLATION_BR_PERSISTENCE", SignalDirection.LONG, 0.75
            ),
        ]

        agent = _make_agent()
        composite = agent._build_composite(signals, _AS_OF_DATE)

        assert composite.metadata["dampening"] == pytest.approx(1.0)
        assert composite.direction == SignalDirection.LONG

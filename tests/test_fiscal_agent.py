"""Unit tests for FiscalAgent and all 3 sub-models.

All tests use synthetic feature dicts or synthetic DataFrames — no database
connection required.  Mirrors the pattern from tests/test_monetary_agent.py.

Tests cover:
- FiscalFeatureEngine: key presence and correctness
- DebtSustainabilityModel: LONG (rising debt), SHORT (declining), NEUTRAL (stable),
  NO_SIGNAL (insufficient data / insufficient history)
- FiscalImpulseModel: LONG (fiscal expansion), SHORT (contraction), NO_SIGNAL
- FiscalDominanceRisk: LOW score → SHORT, HIGH score → LONG, signal_id
- FiscalAgent composite: conflict dampening, unanimous consensus
"""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from src.agents.base import AgentSignal
from src.agents.features.fiscal_features import FiscalFeatureEngine
from src.agents.fiscal_agent import (
    DebtSustainabilityModel,
    FiscalAgent,
    FiscalDominanceRisk,
    FiscalImpulseModel,
)
from src.core.enums import SignalDirection, SignalStrength

AS_OF = date(2024, 1, 31)


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
        agent_id="fiscal_agent",
        timestamp=datetime.utcnow(),
        as_of_date=AS_OF,
        direction=direction,
        strength=strength,
        confidence=confidence,
        value=value,
        horizon_days=252,
    )


# ---------------------------------------------------------------------------
# Helper: build synthetic DataFrames
# ---------------------------------------------------------------------------
def _make_monthly_df(value: float = 85.0, n: int = 60) -> pd.DataFrame:
    dates = pd.date_range("2019-01-31", periods=n, freq="ME")
    return pd.DataFrame({"value": [value] * n}, index=dates)


def _make_quarterly_df(value: float = 0.5, n: int = 60) -> pd.DataFrame:
    dates = pd.date_range("2009-01-31", periods=n, freq="QE")
    return pd.DataFrame({"value": [value] * n}, index=dates)


def _make_pb_history(n: int = 60) -> pd.Series:
    """Build synthetic monthly primary balance/GDP series."""
    dates = pd.date_range("2019-01-31", periods=n, freq="ME")
    return pd.Series([1.0] * n, index=dates, name="pb_gdp")


def _make_dsa_features(
    debt_gdp: float = 85.0,
    r_real: float = 4.0,
    g_real: float = 2.0,
    pb_gdp: float = 0.0,
    r_nominal: float = 13.75,
    focus_ipca_12m: float = 4.5,
    g_focus: float | None = None,
    pb_history_n: int = 24,
) -> dict:
    """Build minimal feature dict for DebtSustainabilityModel."""
    return {
        "_dsa_raw_data": {
            "debt_gdp": debt_gdp,
            "r_nominal": r_nominal,
            "g_real": g_real,
            "pb_gdp": pb_gdp,
            "r_real": r_real,
            "focus_ipca_12m": focus_ipca_12m,
            "g_focus": g_focus if g_focus is not None else g_real,
        },
        "_pb_history": _make_pb_history(pb_history_n),
        "_di_curve": {},
    }


# ---------------------------------------------------------------------------
# Test 1: FiscalFeatureEngine keys
# ---------------------------------------------------------------------------
class TestFiscalFeatureEngineKeys:
    def _build_data(self) -> dict:
        return {
            "gross_debt": _make_monthly_df(85.0, 60),
            "net_debt": _make_monthly_df(62.0, 60),
            "primary_balance": _make_monthly_df(-200_000.0, 60),
            "gdp_qoq": _make_quarterly_df(0.5, 60),
            "selic": _make_monthly_df(13.75, 60),
            "focus": _make_monthly_df(4.5, 60),
            "focus_pib_cy": None,
            "focus_pib_ny": None,
            "di_curve": {},
        }

    def test_fiscal_feature_engine_keys(self):
        data = self._build_data()
        features = FiscalFeatureEngine().compute(data, AS_OF)

        # Required scalar keys
        required_scalar = [
            "gross_debt_gdp",
            "net_debt_gdp",
            "r_g_spread",
            "r_real",
            "focus_ipca_12m",
            "focus_ipca_12m_abs_dev",
        ]
        for key in required_scalar:
            assert key in features, f"Missing key: {key}"

        # Private keys
        assert "_dsa_raw_data" in features
        assert isinstance(features["_dsa_raw_data"], dict)
        assert "_pb_history" in features
        assert isinstance(features["_pb_history"], pd.Series)
        assert "_as_of_date" in features
        assert features["_as_of_date"] == AS_OF

        # abs_dev value
        expected_abs_dev = abs(4.5 - 3.0)
        assert features["focus_ipca_12m_abs_dev"] == pytest.approx(expected_abs_dev, abs=0.01)


# ---------------------------------------------------------------------------
# Tests 2-6: DebtSustainabilityModel
# ---------------------------------------------------------------------------
class TestDebtSustainabilityModel:
    def _run(self, **kwargs) -> AgentSignal:
        features = _make_dsa_features(**kwargs)
        return DebtSustainabilityModel().run(features, AS_OF)

    def test_dsa_rising_debt_long(self):
        """r_real=6.5 >> g_real=1.5, primary deficit → debt rising → LONG."""
        sig = self._run(debt_gdp=85.0, r_real=6.5, g_real=1.5, pb_gdp=-1.0)
        assert sig.direction == SignalDirection.LONG
        assert sig.signal_id == "FISCAL_BR_DSA"
        assert sig.horizon_days == 252 * 5

    def test_dsa_declining_debt_short(self):
        """g_real=4.0 > r_real=2.0, primary surplus → debt shrinks → SHORT."""
        sig = self._run(debt_gdp=60.0, r_real=2.0, g_real=4.0, pb_gdp=2.0)
        assert sig.direction == SignalDirection.SHORT

    def test_dsa_stable_debt_neutral(self):
        """r=g=3.0, pb=0 → near-zero delta → NEUTRAL."""
        sig = self._run(debt_gdp=75.0, r_real=3.0, g_real=3.0, pb_gdp=0.0)
        assert sig.direction == SignalDirection.NEUTRAL

    def test_dsa_insufficient_data_no_signal(self):
        """All NaN in _dsa_raw_data → NO_SIGNAL."""
        features = {
            "_dsa_raw_data": {
                "debt_gdp": np.nan,
                "r_nominal": np.nan,
                "g_real": np.nan,
                "pb_gdp": np.nan,
                "r_real": np.nan,
                "focus_ipca_12m": np.nan,
                "g_focus": np.nan,
            },
            "_pb_history": _make_pb_history(24),
            "_di_curve": {},
        }
        sig = DebtSustainabilityModel().run(features, AS_OF)
        assert sig.strength == SignalStrength.NO_SIGNAL

    def test_dsa_min_obs_guard(self):
        """pb_history with only 5 values (< MIN_OBS=12) → NO_SIGNAL with reason."""
        features = _make_dsa_features(pb_history_n=5)
        sig = DebtSustainabilityModel().run(features, AS_OF)
        assert sig.strength == SignalStrength.NO_SIGNAL
        assert "insufficient_history" in sig.metadata.get("reason", "")


# ---------------------------------------------------------------------------
# Tests 7-9: FiscalImpulseModel
# ---------------------------------------------------------------------------
class TestFiscalImpulseModel:
    def test_fiscal_impulse_expansionary_long(self):
        """pb deteriorating over last 12M → fiscal expansion → LONG."""
        # First 36 months stable at 1.0, last 24 months declining to -0.5
        n = 60
        dates = pd.date_range("2019-01-31", periods=n, freq="ME")
        values = [1.0] * 36 + list(np.linspace(0.9, -0.5, 24))
        pb_history = pd.Series(values, index=dates)

        features = {"_pb_history": pb_history}
        sig = FiscalImpulseModel().run(features, AS_OF)
        # Last obs ~-0.5 vs 12M ago ~0.9 → 12M change ~ -1.4 → negative z → LONG
        assert sig.direction == SignalDirection.LONG
        assert sig.signal_id == "FISCAL_BR_IMPULSE"

    def test_fiscal_impulse_contractionary_short(self):
        """pb improving over last 12M → fiscal contraction → SHORT."""
        n = 60
        dates = pd.date_range("2019-01-31", periods=n, freq="ME")
        # Start negative, gradually improve to positive
        values = [-1.0] * 36 + list(np.linspace(-0.9, 1.5, 24))
        pb_history = pd.Series(values, index=dates)

        features = {"_pb_history": pb_history}
        sig = FiscalImpulseModel().run(features, AS_OF)
        # Last obs ~1.5 vs 12M ago ~-0.9 → 12M change ~ +2.4 → positive z → SHORT
        assert sig.direction == SignalDirection.SHORT

    def test_fiscal_impulse_no_signal_insufficient_data(self):
        """pb_history with only 10 values → NO_SIGNAL."""
        dates = pd.date_range("2023-01-31", periods=10, freq="ME")
        pb_history = pd.Series([1.0] * 10, index=dates)
        features = {"_pb_history": pb_history}
        sig = FiscalImpulseModel().run(features, AS_OF)
        assert sig.strength == SignalStrength.NO_SIGNAL


# ---------------------------------------------------------------------------
# Tests 10-12: FiscalDominanceRisk
# ---------------------------------------------------------------------------
class TestFiscalDominanceRisk:
    def test_dominance_risk_low_score_short(self):
        """Low debt, r < g, improving pb, anchored CB → composite < 33 → SHORT."""
        features = {
            "gross_debt_gdp": 40.0,
            "r_g_spread": -2.0,
            "pb_12m_change": 1.0,
            "focus_ipca_12m_abs_dev": 0.2,
        }
        sig = FiscalDominanceRisk().run(features, AS_OF)
        assert sig.direction == SignalDirection.SHORT
        assert sig.value < 33.0

    def test_dominance_risk_high_score_long(self):
        """High debt, r >> g, deteriorating pb, unanchored CB → composite > 66 → LONG."""
        features = {
            "gross_debt_gdp": 88.0,
            "r_g_spread": 5.0,
            "pb_12m_change": -1.5,
            "focus_ipca_12m_abs_dev": 3.0,
        }
        sig = FiscalDominanceRisk().run(features, AS_OF)
        assert sig.direction == SignalDirection.LONG
        assert sig.value > 66.0
        assert "composite_score" in sig.metadata

    def test_dominance_risk_signal_id(self):
        """Signal ID must always be FISCAL_BR_DOMINANCE_RISK."""
        features = {
            "gross_debt_gdp": 70.0,
            "r_g_spread": 1.0,
            "pb_12m_change": -0.2,
            "focus_ipca_12m_abs_dev": 1.0,
        }
        sig = FiscalDominanceRisk().run(features, AS_OF)
        assert sig.signal_id == "FISCAL_BR_DOMINANCE_RISK"


# ---------------------------------------------------------------------------
# Tests 13-14: FiscalAgent composite
# ---------------------------------------------------------------------------
class TestFiscalAgentComposite:
    def _make_agent(self) -> FiscalAgent:
        loader = MagicMock()
        return FiscalAgent(loader=loader)

    def test_fiscal_composite_conflict_dampening(self):
        """2 LONG + 1 SHORT → plurality LONG, dampening=0.70."""
        agent = self._make_agent()
        signals = [
            make_signal("FISCAL_BR_DSA", SignalDirection.LONG, SignalStrength.MODERATE, 0.7),
            make_signal("FISCAL_BR_IMPULSE", SignalDirection.SHORT, SignalStrength.MODERATE, 0.7),
            make_signal("FISCAL_BR_DOMINANCE_RISK", SignalDirection.LONG, SignalStrength.MODERATE, 0.7),
        ]
        composite = agent._build_composite(signals, AS_OF)
        assert composite.direction == SignalDirection.LONG
        assert composite.metadata["dampening"] == pytest.approx(0.70, abs=0.01)
        assert composite.signal_id == "FISCAL_BR_COMPOSITE"

    def test_fiscal_composite_unanimous(self):
        """3 LONG → direction LONG, dampening=1.0 (no conflict)."""
        agent = self._make_agent()
        signals = [
            make_signal("FISCAL_BR_DSA", SignalDirection.LONG, SignalStrength.STRONG, 0.8),
            make_signal("FISCAL_BR_IMPULSE", SignalDirection.LONG, SignalStrength.MODERATE, 0.6),
            make_signal("FISCAL_BR_DOMINANCE_RISK", SignalDirection.LONG, SignalStrength.MODERATE, 0.7),
        ]
        composite = agent._build_composite(signals, AS_OF)
        assert composite.direction == SignalDirection.LONG
        assert composite.metadata["dampening"] == pytest.approx(1.0, abs=0.01)

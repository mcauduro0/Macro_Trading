"""Unit tests for FxEquilibriumAgent and all 4 sub-models.

All tests use synthetic feature dicts or synthetic DataFrames — no database
connection required.  Mirrors the pattern from tests/test_fiscal_agent.py.

Tests cover:
- FxFeatureEngine: key presence and type assertions
- BeerModel: SHORT (undervalued >5%), LONG (overvalued >5%), NEUTRAL (<5%),
  NO_SIGNAL (insufficient predictors or data)
- CarryToRiskModel: SHORT (high carry z>1), LONG (low carry z<-1), NO_SIGNAL
- FlowModel: SHORT (positive composite), LONG (negative), partial NaN handling
- CipBasisModel: LONG (positive basis locked), SHORT (negative basis)
- FxEquilibriumAgent composite: locked weights, conflict dampening, unanimous
"""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from src.agents.base import AgentSignal
from src.agents.features.fx_features import FxFeatureEngine
from src.agents.fx_agent import (
    BeerModel,
    CarryToRiskModel,
    CipBasisModel,
    FlowModel,
    FxEquilibriumAgent,
)
from src.core.enums import SignalDirection, SignalStrength

AS_OF = date(2024, 1, 31)


# ---------------------------------------------------------------------------
# Helpers
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
        agent_id="fx_agent",
        timestamp=datetime.utcnow(),
        as_of_date=AS_OF,
        direction=direction,
        strength=strength,
        confidence=confidence,
        value=value,
        horizon_days=252,
    )


def make_monthly_df(values: list[float], col: str = "value") -> pd.DataFrame:
    """Build a monthly DatetimeIndex DataFrame with a single column."""
    idx = pd.date_range("2010-01-31", periods=len(values), freq="ME")
    return pd.DataFrame({col: values}, index=idx)


def _make_ptax_df(n: int = 756, close_val: float = 5.0) -> pd.DataFrame:
    """Build synthetic daily USDBRL PTAX DataFrame."""
    idx = pd.date_range("2021-01-01", periods=n, freq="B")
    return pd.DataFrame({"close": [close_val] * n}, index=idx)


def _make_beer_df(
    n: int = 60,
    log_usdbrl_vals: list[float] | None = None,
) -> pd.DataFrame:
    """Build synthetic monthly BEER OLS DataFrame (2010-present)."""
    idx = pd.date_range("2010-01-31", periods=n, freq="ME")
    if log_usdbrl_vals is None:
        log_usdbrl_vals = [np.log(5.5)] * n
    df = pd.DataFrame(
        {
            "log_usdbrl": log_usdbrl_vals,
            "tot_proxy": [0.02] * n,
            "real_rate_diff": [0.05] * n,
            "nfa_proxy": [np.log(350)] * n,
        },
        index=idx,
    )
    return df


def _make_carry_history(
    n: int = 24,
    mean: float = 2.0,
    std: float = 0.5,
    last_val: float | None = None,
) -> pd.Series:
    """Build synthetic monthly carry-to-risk ratio Series."""
    idx = pd.date_range("2022-01-31", periods=n, freq="ME")
    vals = [mean] * n
    if last_val is not None:
        vals[-1] = last_val
    return pd.Series(vals, index=idx)


def _make_flow_df(bcb_z: float = 0.0, cftc_z: float = 0.0) -> pd.DataFrame:
    """Build synthetic flow DataFrame with a single last row."""
    idx = pd.DatetimeIndex([pd.Timestamp("2024-01-31")])
    return pd.DataFrame(
        {"bcb_flow_zscore": [bcb_z], "cftc_zscore": [cftc_z]},
        index=idx,
    )


# ---------------------------------------------------------------------------
# Test 1: FxFeatureEngine key presence
# ---------------------------------------------------------------------------
def test_fx_feature_engine_keys():
    """FxFeatureEngine.compute() returns expected scalar and private keys."""
    n_daily = 756
    n_monthly = 60

    ptax_idx = pd.date_range("2021-01-01", periods=n_daily, freq="B")
    ptax_df = pd.DataFrame({"close": [5.0] * n_daily}, index=ptax_idx)

    monthly_idx = pd.date_range("2019-01-31", periods=n_monthly, freq="ME")
    selic_df = pd.DataFrame({"value": [13.75] * n_monthly}, index=monthly_idx)
    fed_funds_df = pd.DataFrame({"value": [5.25] * n_monthly}, index=monthly_idx)
    sofr_df = pd.DataFrame({"value": [5.10] * n_monthly}, index=monthly_idx)
    fx_reserves_df = pd.DataFrame({"value": [350.0] * n_monthly}, index=monthly_idx)
    trade_balance_df = pd.DataFrame({"value": [10.0] * n_monthly}, index=monthly_idx)
    focus_ipca_df = pd.DataFrame({"value": [4.5] * n_monthly}, index=monthly_idx)
    focus_cambio_df = pd.DataFrame({"value": [5.2] * n_monthly}, index=monthly_idx)

    data = {
        "ptax": ptax_df,
        "selic": selic_df,
        "fed_funds": fed_funds_df,
        "sofr": sofr_df,
        "fx_reserves": fx_reserves_df,
        "trade_balance": trade_balance_df,
        "focus_ipca": focus_ipca_df,
        "focus_cambio": focus_cambio_df,
        "di_curve": {252: 12.5, 504: 12.8, 1260: 13.0},
        "di_curve_history": pd.DataFrame(columns=["date", "rate"]),
        "ust_5y_history": pd.DataFrame(columns=["date", "rate"]),
        "bcb_flow": None,
        "cftc_brl": None,
    }

    features = FxFeatureEngine().compute(data, date(2024, 1, 31))

    # Scalar keys
    for key in ["usdbrl_spot", "carry_raw", "vol_30d_realized", "carry_to_risk_ratio"]:
        assert key in features, f"Missing scalar key: {key}"

    # Private model keys
    for key in ["_beer_ols_data", "_ptax_daily", "_carry_ratio_history", "_flow_combined", "_as_of_date"]:
        assert key in features, f"Missing private key: {key}"

    # Type and value checks
    assert features["_as_of_date"] == date(2024, 1, 31)
    assert isinstance(features["_beer_ols_data"], pd.DataFrame)
    assert "log_usdbrl" in features["_beer_ols_data"].columns


# ---------------------------------------------------------------------------
# Test 2: BeerModel — USDBRL undervalued → SHORT
# ---------------------------------------------------------------------------
def test_beer_model_undervalued_short():
    """USDBRL >5% above OLS fair value → SHORT (BRL undervalued)."""
    # 60 rows with log(5.5), except last = log(6.0)
    n = 60
    vals = [np.log(5.5)] * n
    vals[-1] = np.log(6.0)  # last row: actual USDBRL much higher than fair
    df = _make_beer_df(n=n, log_usdbrl_vals=vals)

    model = BeerModel()
    sig = model.run({"_beer_ols_data": df}, AS_OF)

    # USDBRL=6.0 vs fair~5.5 → +9% misalignment → SHORT
    assert sig.direction == SignalDirection.SHORT, (
        f"Expected SHORT (BRL undervalued), got {sig.direction}"
    )
    assert sig.signal_id == "FX_BR_BEER"
    assert sig.value > BeerModel.THRESHOLD  # misalignment > 5%


# ---------------------------------------------------------------------------
# Test 3: BeerModel — USDBRL overvalued → LONG
# ---------------------------------------------------------------------------
def test_beer_model_overvalued_long():
    """USDBRL >5% below OLS fair value → LONG (BRL overvalued)."""
    n = 60
    vals = [np.log(5.5)] * n
    vals[-1] = np.log(4.8)  # actual USDBRL much lower than fair
    df = _make_beer_df(n=n, log_usdbrl_vals=vals)

    model = BeerModel()
    sig = model.run({"_beer_ols_data": df}, AS_OF)

    assert sig.direction == SignalDirection.LONG, (
        f"Expected LONG (BRL overvalued), got {sig.direction}"
    )


# ---------------------------------------------------------------------------
# Test 4: BeerModel — insufficient predictors → NO_SIGNAL
# ---------------------------------------------------------------------------
def test_beer_model_no_signal_insufficient_predictors():
    """Only 1 predictor column → NO_SIGNAL with reason."""
    df = _make_beer_df()
    # Drop 2 predictors leaving only tot_proxy
    df = df.drop(columns=["real_rate_diff", "nfa_proxy"])

    sig = BeerModel().run({"_beer_ols_data": df}, AS_OF)

    assert sig.strength == SignalStrength.NO_SIGNAL
    assert "insufficient_predictors" in sig.metadata.get("reason", "")


# ---------------------------------------------------------------------------
# Test 5: BeerModel — insufficient data rows → NO_SIGNAL
# ---------------------------------------------------------------------------
def test_beer_model_no_signal_insufficient_data():
    """Only 10 rows (< MIN_OBS=24) → NO_SIGNAL."""
    df = _make_beer_df(n=10)
    sig = BeerModel().run({"_beer_ols_data": df}, AS_OF)

    assert sig.strength == SignalStrength.NO_SIGNAL


# ---------------------------------------------------------------------------
# Test 6: BeerModel — within threshold → NEUTRAL
# ---------------------------------------------------------------------------
def test_beer_model_neutral_within_threshold():
    """Misalignment < 5% → NEUTRAL direction."""
    n = 60
    # All rows = log(5.0), last = log(5.1) → only ~2% mismatch
    vals = [np.log(5.0)] * n
    vals[-1] = np.log(5.1)
    df = _make_beer_df(n=n, log_usdbrl_vals=vals)
    # Override predictors so OLS fair value stays ~5.0
    df["tot_proxy"] = 0.0
    df["real_rate_diff"] = 0.0
    df["nfa_proxy"] = 0.0

    sig = BeerModel().run({"_beer_ols_data": df}, AS_OF)

    assert sig.direction == SignalDirection.NEUTRAL


# ---------------------------------------------------------------------------
# Test 7: CarryToRiskModel — high carry z → SHORT
# ---------------------------------------------------------------------------
def test_carry_to_risk_short_high_carry():
    """Carry z = 4.0 >> 1.0 → SHORT (attractive carry = BRL inflows)."""
    # Build history: set only last element to outlier, rest constant.
    idx = pd.date_range("2022-01-31", periods=24, freq="ME")
    vals2 = [2.0] * 23 + [4.0]
    history2 = pd.Series(vals2, index=idx)

    features = {
        "_carry_ratio_history": history2,
        "carry_raw": 8.5,
        "vol_30d_realized": 20.0,
    }

    sig = CarryToRiskModel().run(features, AS_OF)

    assert sig.direction == SignalDirection.SHORT, (
        f"Expected SHORT (attractive carry), got {sig.direction}"
    )
    assert sig.signal_id == "FX_BR_CARRY_RISK"
    # z > 1.0 → value > 1.0
    assert sig.value > 1.0


# ---------------------------------------------------------------------------
# Test 8: CarryToRiskModel — low carry z → LONG
# ---------------------------------------------------------------------------
def test_carry_to_risk_long_low_carry():
    """Carry z = -4.0 << -1.0 → LONG (carry unwind risk)."""
    idx = pd.date_range("2022-01-31", periods=24, freq="ME")
    vals = [2.0] * 23 + [0.0]  # last value much lower than rolling mean
    history = pd.Series(vals, index=idx)

    features = {"_carry_ratio_history": history, "carry_raw": 8.5, "vol_30d_realized": 20.0}
    sig = CarryToRiskModel().run(features, AS_OF)

    assert sig.direction == SignalDirection.LONG, (
        f"Expected LONG (carry unwind risk), got {sig.direction}"
    )


# ---------------------------------------------------------------------------
# Test 9: CarryToRiskModel — insufficient data → NO_SIGNAL
# ---------------------------------------------------------------------------
def test_carry_to_risk_no_signal_insufficient_data():
    """Only 5 values (< MIN_OBS=13) → NO_SIGNAL."""
    history = pd.Series([2.0] * 5, index=pd.date_range("2023-01-31", periods=5, freq="ME"))
    sig = CarryToRiskModel().run({"_carry_ratio_history": history}, AS_OF)
    assert sig.strength == SignalStrength.NO_SIGNAL


# ---------------------------------------------------------------------------
# Test 10: FlowModel — positive composite → SHORT
# ---------------------------------------------------------------------------
def test_flow_model_positive_composite_short():
    """bcb_z=1.5, cftc_z=1.2 → composite=1.35 > 0.5 → SHORT."""
    flow_df = _make_flow_df(bcb_z=1.5, cftc_z=1.2)
    sig = FlowModel().run({"_flow_combined": flow_df}, AS_OF)

    assert sig.direction == SignalDirection.SHORT
    assert sig.signal_id == "FX_BR_FLOW"


# ---------------------------------------------------------------------------
# Test 11: FlowModel — negative composite → LONG
# ---------------------------------------------------------------------------
def test_flow_model_negative_composite_long():
    """bcb_z=-1.5, cftc_z=-1.0 → composite=-1.25 < -0.5 → LONG."""
    flow_df = _make_flow_df(bcb_z=-1.5, cftc_z=-1.0)
    sig = FlowModel().run({"_flow_combined": flow_df}, AS_OF)

    assert sig.direction == SignalDirection.LONG


# ---------------------------------------------------------------------------
# Test 12: FlowModel — one component NaN → uses other
# ---------------------------------------------------------------------------
def test_flow_model_one_component_nan():
    """bcb_z=NaN, cftc_z=1.5 → use CFTC only → composite=1.5 → SHORT."""
    idx = pd.DatetimeIndex([pd.Timestamp("2024-01-31")])
    flow_df = pd.DataFrame(
        {"bcb_flow_zscore": [np.nan], "cftc_zscore": [1.5]},
        index=idx,
    )
    sig = FlowModel().run({"_flow_combined": flow_df}, AS_OF)

    assert sig.direction == SignalDirection.SHORT, (
        f"Expected SHORT (CFTC-only positive), got {sig.direction}"
    )


# ---------------------------------------------------------------------------
# Test 13: CipBasisModel — positive basis → LONG (locked)
# ---------------------------------------------------------------------------
def test_cip_basis_positive_long():
    """Positive CIP basis (DI > offshore) → LONG USDBRL (locked in CONTEXT.md)."""
    features = {
        "cip_basis": 7.2,
        "_di_1y_rate": 12.5,
        "_sofr_rate": 5.3,
    }
    sig = CipBasisModel().run(features, AS_OF)

    assert sig.direction == SignalDirection.LONG, (
        f"Expected LONG (positive basis = BRL less attractive), got {sig.direction}"
    )
    assert sig.signal_id == "FX_BR_CIP_BASIS"


# ---------------------------------------------------------------------------
# Test 14: CipBasisModel — negative basis → SHORT
# ---------------------------------------------------------------------------
def test_cip_basis_negative_short():
    """Negative CIP basis → SHORT USDBRL."""
    features = {
        "cip_basis": -1.5,
        "_di_1y_rate": 10.0,
        "_sofr_rate": 5.3,
    }
    sig = CipBasisModel().run(features, AS_OF)

    assert sig.direction == SignalDirection.SHORT


# ---------------------------------------------------------------------------
# Test 15: FxEquilibriumAgent composite — locked weights and dampening
# ---------------------------------------------------------------------------
def test_fx_composite_locked_weights():
    """Composite with conflict: BEER+Carry=SHORT(70%), Flow+CIP=LONG(30%) → SHORT, dampening=0.70."""
    beer_sig = make_signal("FX_BR_BEER", SignalDirection.SHORT, SignalStrength.STRONG, 0.8)
    carry_sig = make_signal("FX_BR_CARRY_RISK", SignalDirection.SHORT, SignalStrength.STRONG, 0.7)
    flow_sig = make_signal("FX_BR_FLOW", SignalDirection.LONG, SignalStrength.MODERATE, 0.6)
    cip_sig = make_signal("FX_BR_CIP_BASIS", SignalDirection.LONG, SignalStrength.WEAK, 0.5)

    agent = FxEquilibriumAgent(loader=MagicMock())
    composite = agent._build_composite([beer_sig, carry_sig, flow_sig, cip_sig], AS_OF)

    # BEER=0.40 SHORT, Carry=0.30 SHORT → short_w=0.70
    # Flow=0.20 LONG, CIP=0.10 LONG → long_w=0.30
    # Plurality = SHORT; 2 disagreements → dampening=0.70
    assert composite.direction == SignalDirection.SHORT
    assert composite.metadata["dampening"] == pytest.approx(0.70, abs=0.01)
    assert composite.signal_id == "FX_BR_COMPOSITE"


# ---------------------------------------------------------------------------
# Test 16: FxEquilibriumAgent composite — unanimous → no dampening
# ---------------------------------------------------------------------------
def test_fx_composite_unanimous_no_dampening():
    """All 4 signals SHORT → dampening=1.0 (no conflict)."""
    signals = [
        make_signal("FX_BR_BEER", SignalDirection.SHORT, SignalStrength.STRONG, 0.8),
        make_signal("FX_BR_CARRY_RISK", SignalDirection.SHORT, SignalStrength.STRONG, 0.8),
        make_signal("FX_BR_FLOW", SignalDirection.SHORT, SignalStrength.MODERATE, 0.7),
        make_signal("FX_BR_CIP_BASIS", SignalDirection.SHORT, SignalStrength.WEAK, 0.6),
    ]

    agent = FxEquilibriumAgent(loader=MagicMock())
    composite = agent._build_composite(signals, AS_OF)

    assert composite.direction == SignalDirection.SHORT
    assert composite.metadata["dampening"] == pytest.approx(1.0, abs=0.01)


# ---------------------------------------------------------------------------
# Test 17: BeerModel — no data → NO_SIGNAL
# ---------------------------------------------------------------------------
def test_beer_model_no_data():
    """Empty _beer_ols_data → NO_SIGNAL with reason=no_data."""
    sig = BeerModel().run({"_beer_ols_data": None}, AS_OF)
    assert sig.strength == SignalStrength.NO_SIGNAL
    assert sig.metadata.get("reason") == "no_data"


# ---------------------------------------------------------------------------
# Test 18: FlowModel — both components NaN → NO_SIGNAL
# ---------------------------------------------------------------------------
def test_flow_model_all_nan():
    """Both bcb_z and cftc_z are NaN → NO_SIGNAL."""
    idx = pd.DatetimeIndex([pd.Timestamp("2024-01-31")])
    flow_df = pd.DataFrame(
        {"bcb_flow_zscore": [np.nan], "cftc_zscore": [np.nan]},
        index=idx,
    )
    sig = FlowModel().run({"_flow_combined": flow_df}, AS_OF)
    assert sig.strength == SignalStrength.NO_SIGNAL


# ---------------------------------------------------------------------------
# Test 19: CipBasisModel — no data → NO_SIGNAL
# ---------------------------------------------------------------------------
def test_cip_basis_no_data():
    """No cip_basis and no di/sofr rates → NO_SIGNAL."""
    sig = CipBasisModel().run({"cip_basis": np.nan, "_di_1y_rate": np.nan, "_sofr_rate": np.nan}, AS_OF)
    assert sig.strength == SignalStrength.NO_SIGNAL


# ---------------------------------------------------------------------------
# Test 20: FxEquilibriumAgent.AGENT_ID constant
# ---------------------------------------------------------------------------
def test_fx_agent_id():
    """FxEquilibriumAgent.AGENT_ID must equal 'fx_agent' for AgentRegistry."""
    assert FxEquilibriumAgent.AGENT_ID == "fx_agent"

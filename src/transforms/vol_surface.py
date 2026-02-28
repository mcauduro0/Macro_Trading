import numpy as np


def reconstruct_smile(
    atm: float,
    rr25: float,
    bf25: float,
    rr10: float | None = None,
    bf10: float | None = None,
) -> dict[str, float]:
    """Reconstruct vol smile from risk reversals and butterflies.
    Call_25d = ATM + 0.5*RR25 + BF25
    Put_25d = ATM - 0.5*RR25 + BF25
    """
    call_25d = atm + 0.5 * rr25 + bf25
    put_25d = atm - 0.5 * rr25 + bf25
    result = {"atm": atm, "call_25d": call_25d, "put_25d": put_25d}
    if rr10 is not None and bf10 is not None:
        result["call_10d"] = atm + 0.5 * rr10 + bf10
        result["put_10d"] = atm - 0.5 * rr10 + bf10
    return result


def compute_iv_rv_ratio(implied: float, realized: float) -> float:
    """Implied vol / realized vol ratio. >1 = vol premium."""
    if realized <= 0:
        return float("nan")
    return implied / realized


def compute_vol_slope(short_vol: float, long_vol: float) -> float:
    """Term structure slope: long - short. Negative = inverted."""
    return long_vol - short_vol


def compute_vol_zscore(
    current_vol: float, vol_history: np.ndarray, window: int = 252
) -> float:
    """Z-score of current vol vs historical window."""
    history = vol_history[-window:] if len(vol_history) > window else vol_history
    if len(history) < 2:
        return 0.0
    mean = np.mean(history)
    std = np.std(history)
    if std == 0:
        return 0.0
    return (current_vol - mean) / std

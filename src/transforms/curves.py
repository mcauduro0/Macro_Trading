import numpy as np
from scipy.optimize import minimize
from scipy.interpolate import CubicSpline

STANDARD_TENORS_DAYS = [30, 60, 90, 180, 365, 730, 1095, 1825, 2555, 3650]


def nelson_siegel(tau: np.ndarray, beta0: float, beta1: float, beta2: float, lam: float) -> np.ndarray:
    """Nelson-Siegel formula: y(τ) = β0 + β1*[(1-e^(-τ/λ))/(τ/λ)] + β2*[(1-e^(-τ/λ))/(τ/λ) - e^(-τ/λ)]
    tau is in years. Returns rates in decimal."""
    x = tau / lam
    # Guard against division by zero
    with np.errstate(divide='ignore', invalid='ignore'):
        factor1 = np.where(x == 0, 1.0, (1 - np.exp(-x)) / x)
        factor2 = factor1 - np.exp(-x)
    return beta0 + beta1 * factor1 + beta2 * factor2


def fit_nelson_siegel(tenors_years: np.ndarray, rates: np.ndarray) -> tuple[float, float, float, float]:
    """Fit NS params using scipy minimize. Returns (beta0, beta1, beta2, lambda)."""
    def objective(params):
        b0, b1, b2, lam = params
        if lam <= 0.01:
            return 1e10
        predicted = nelson_siegel(tenors_years, b0, b1, b2, lam)
        return np.sum((predicted - rates) ** 2)

    # Initial guess: level=long rate, slope=short-long, curvature=0, lambda=1.5
    x0 = [rates[-1], rates[0] - rates[-1], 0.0, 1.5]
    bounds = [(None, None), (None, None), (None, None), (0.05, 10.0)]
    result = minimize(objective, x0, bounds=bounds, method='L-BFGS-B')
    return tuple(result.x)


def interpolate_curve(
    observed_tenors_days: list[int],
    observed_rates: list[float],
    target_tenors_days: list[int] | None = None,
    method: str = "nelson_siegel",
) -> dict[int, float]:
    """Interpolate to standard tenors. Methods: nelson_siegel, cubic_spline, linear."""
    if target_tenors_days is None:
        target_tenors_days = STANDARD_TENORS_DAYS

    obs_years = np.array(observed_tenors_days) / 365.0
    obs_rates = np.array(observed_rates)
    tgt_years = np.array(target_tenors_days) / 365.0

    if method == "nelson_siegel":
        b0, b1, b2, lam = fit_nelson_siegel(obs_years, obs_rates)
        fitted = nelson_siegel(tgt_years, b0, b1, b2, lam)
    elif method == "cubic_spline":
        cs = CubicSpline(obs_years, obs_rates, extrapolate=True)
        fitted = cs(tgt_years)
    elif method == "linear":
        fitted = np.interp(tgt_years, obs_years, obs_rates)
    else:
        raise ValueError(f"Unknown interpolation method: {method}")

    return dict(zip(target_tenors_days, fitted.tolist()))


def compute_breakeven_inflation(nominal: dict[int, float], real: dict[int, float]) -> dict[int, float]:
    """BEI = nominal - real at matching tenors."""
    common = set(nominal) & set(real)
    return {t: nominal[t] - real[t] for t in sorted(common)}


def compute_forward_rate(curve: dict[int, float], t1_days: int, t2_days: int) -> float:
    """Forward rate between t1 and t2 (in days). Simple compounding."""
    if t1_days not in curve or t2_days not in curve:
        raise ValueError(f"Tenors {t1_days} and {t2_days} must be in curve")
    r1 = curve[t1_days]
    r2 = curve[t2_days]
    y1 = t1_days / 365.0
    y2 = t2_days / 365.0
    # f(t1,t2) = (r2*y2 - r1*y1) / (y2 - y1)
    if y2 == y1:
        return r2
    return (r2 * y2 - r1 * y1) / (y2 - y1)


def compute_dv01(rate: float, maturity_years: float, coupon: float = 0.0, notional: float = 100.0) -> float:
    """Dollar value of 1bp move. For zero coupon: DV01 = notional * maturity * e^(-r*T) * 0.0001."""
    discount = np.exp(-rate * maturity_years)
    return notional * maturity_years * discount * 0.0001


def compute_carry_rolldown(curve: dict[int, float], tenor_days: int, horizon_days: int = 21) -> dict[str, float]:
    """Returns: carry_bps, rolldown_bps, total_bps."""
    sorted_tenors = sorted(curve.keys())
    if tenor_days not in curve:
        raise ValueError(f"Tenor {tenor_days} not in curve")

    # Carry: earn the tenor rate, fund at short rate
    short_rate = curve[sorted_tenors[0]]
    tenor_rate = curve[tenor_days]
    carry_bps = (tenor_rate - short_rate) * 10000 * (horizon_days / 365.0)

    # Roll-down: rate change from tenor shortening
    new_tenor = tenor_days - horizon_days
    if new_tenor <= 0:
        rolldown_bps = 0.0
    else:
        # Interpolate the rate at new_tenor
        rates = np.interp(new_tenor, sorted_tenors, [curve[t] for t in sorted_tenors])
        rolldown_bps = (tenor_rate - float(rates)) * 10000

    return {"carry_bps": carry_bps, "rolldown_bps": rolldown_bps, "total_bps": carry_bps + rolldown_bps}

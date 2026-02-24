"""Instrument-aware pricing functions for PMS mark-to-market.

Pure computation module -- no DB or I/O. All functions are stateless.

Implements B3 DI futures convention (rate -> PU -> DV01), NTN-B real-yield
pricing, CDS spread-to-price, FX delta, and instrument-aware P&L in BRL/USD.
"""

from __future__ import annotations


def rate_to_pu(rate_pct: float, business_days: int) -> float:
    """Convert annual rate (percent) to preco unitario (PU) using B3 DI convention.

    Formula: PU = 100_000 / (1 + rate_pct / 100) ** (business_days / 252)

    Args:
        rate_pct: Annual rate in percent (e.g. 10.0 for 10%).
        business_days: Number of business days to maturity.

    Returns:
        Preco unitario (PU).
    """
    if business_days <= 0:
        return 100_000.0
    return 100_000.0 / (1.0 + rate_pct / 100.0) ** (business_days / 252.0)


def pu_to_rate(pu: float, business_days: int) -> float:
    """Convert PU back to annual rate (percent). Inverse of rate_to_pu.

    Formula: rate_pct = ((100_000 / pu) ** (252 / business_days) - 1) * 100

    Args:
        pu: Preco unitario.
        business_days: Number of business days to maturity.

    Returns:
        Annual rate in percent.
    """
    if business_days <= 0 or pu <= 0:
        return 0.0
    return ((100_000.0 / pu) ** (252.0 / business_days) - 1.0) * 100.0


def compute_dv01_from_pu(
    pu: float,
    rate_pct: float,
    business_days: int,
    notional_brl: float,
) -> float:
    """Compute DV01 (dollar value of a basis point) for a rates instrument.

    DV01 = change in PU for a 1bp rate move * (notional / 100_000).

    Args:
        pu: Current preco unitario.
        rate_pct: Current annual rate in percent.
        business_days: Business days to maturity.
        notional_brl: Position notional in BRL.

    Returns:
        DV01 in BRL (absolute value, always positive).
    """
    if business_days <= 0:
        return 0.0
    pu_shifted = rate_to_pu(rate_pct + 0.01, business_days)
    return abs(pu_shifted - pu) * (notional_brl / 100_000.0)


def ntnb_yield_to_price(
    real_yield_pct: float,
    coupon_rate: float,
    years_to_maturity: float,
) -> float:
    """Simplified NTN-B pricing: PV of semi-annual coupons + par at real yield.

    Semi-annual coupon = (1 + coupon_rate/100)^0.5 - 1 per period.
    Price per 1000 face = sum of discounted cashflows.

    Args:
        real_yield_pct: Real yield in percent (e.g. 6.0 for 6%).
        coupon_rate: Annual coupon rate in percent (e.g. 6.0 for IPCA+6%).
        years_to_maturity: Years remaining to maturity.

    Returns:
        Price per 1000 face value.
    """
    if years_to_maturity <= 0:
        return 1000.0

    semi_coupon = (1.0 + coupon_rate / 100.0) ** 0.5 - 1.0
    n_periods = int(years_to_maturity * 2)
    if n_periods < 1:
        n_periods = 1

    semi_yield = (1.0 + real_yield_pct / 100.0) ** 0.5 - 1.0
    if semi_yield <= -1.0:
        semi_yield = 0.001  # guard against extreme negative yields

    price = 0.0
    for t in range(1, n_periods + 1):
        cf = semi_coupon * 1000.0
        if t == n_periods:
            cf += 1000.0  # par redemption
        price += cf / (1.0 + semi_yield) ** t

    return price


def cds_spread_to_price(
    spread_bps: float,
    recovery_rate: float,
    years: float,
    risk_free_rate: float,
) -> float:
    """CDS mark-to-market price representation.

    For MTM tracking, returns spread_bps directly as the "price" since CDS
    is spread-quoted. P&L comes from spread changes.

    Args:
        spread_bps: CDS spread in basis points.
        recovery_rate: Expected recovery rate (0-1).
        years: Protection period in years.
        risk_free_rate: Risk-free rate for discounting.

    Returns:
        The spread in bps (used as price for MTM tracking).
    """
    return spread_bps


def compute_fx_delta(notional_brl: float, spot_rate: float) -> float:
    """Compute FX delta (USD equivalent exposure).

    Args:
        notional_brl: Position notional in BRL.
        spot_rate: Current USDBRL spot rate.

    Returns:
        FX delta in USD. Returns 0.0 if spot_rate <= 0.
    """
    if spot_rate <= 0:
        return 0.0
    return notional_brl / spot_rate


def compute_pnl_brl(
    entry_price: float,
    current_price: float,
    notional_brl: float,
    direction: str,
    instrument: str,
    asset_class: str,
) -> float:
    """Compute P&L in BRL using instrument-aware logic.

    For RATES (DI): prices are already PU. P&L = (current - entry) * quantity.
        LONG = receive fixed (benefit from PU increase).
        SHORT = pay fixed (benefit from PU decrease).
    For FX and general: P&L = notional * (current / entry - 1) * direction_sign.

    Args:
        entry_price: Entry price (PU for rates, spot for FX).
        current_price: Current price.
        notional_brl: Position notional in BRL.
        direction: "LONG" or "SHORT".
        instrument: Instrument ticker (e.g. "DI1_F25").
        asset_class: Asset class (e.g. "RATES", "FX", "CREDIT").

    Returns:
        P&L in BRL.
    """
    direction_sign = 1.0 if direction.upper() == "LONG" else -1.0

    if entry_price == 0:
        return 0.0

    if asset_class.upper() == "RATES":
        # Both prices are PU. Quantity = notional / 100_000 (contracts)
        quantity = notional_brl / 100_000.0
        return (current_price - entry_price) * quantity * direction_sign
    else:
        # General / FX: percentage return on notional
        return notional_brl * (current_price / entry_price - 1.0) * direction_sign


def compute_pnl_usd(pnl_brl: float, current_fx_rate: float) -> float:
    """Convert BRL P&L to USD.

    Args:
        pnl_brl: P&L in BRL.
        current_fx_rate: Current USDBRL rate.

    Returns:
        P&L in USD. Returns 0.0 if rate <= 0.
    """
    if current_fx_rate <= 0:
        return 0.0
    return pnl_brl / current_fx_rate

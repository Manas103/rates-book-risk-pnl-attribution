"""Reprices every position type off the single curve in `curve.py`. Every
pricer here calls `curve.df` or `curve.pvbp_continuous` directly, which is
what "all positions priced off one bootstrapped curve" means concretely:
there is no separate discounting assumption anywhere in this module.

Each idiosyncratic spread (`spread_bp` on cash Treasuries/futures/swaps)
is applied as a constant OAS-style multiplicative discount on top of the
curve's own discount factors (`exp(-spread * t)`), not a second
independently bootstrapped curve: a position's basis versus the curve is
real and tracked, but it is not given its own term structure.

Cash Treasuries pay annually, not semiannually: a real Treasury note
pays semiannual coupons, but this book's curve is itself an annual-pay
bootstrap (`curve.py`), and discounting a semiannual coupon schedule off
an annual-pay curve would not reprice a par bond to par. Annual pay here
keeps the par-bond-prices-to-par identity (`tests/test_pricer.py`) exact
rather than approximate, at the cost of one more disclosed simplification
on top of the ones `curve.py` already states.
"""
from __future__ import annotations

import math

from . import book as book_module
from .curve import Curve
from .swaption import payer_swaption_price

FACE = 100.0
FREQ = 1  # annual coupons, matching curve.py's own annual-pay bootstrap convention exactly


def _cashflow_times(effective_tenor: float, freq: int = FREQ) -> list[float]:
    n = max(round(effective_tenor * freq), 1)
    return [effective_tenor - (n - k) / freq for k in range(1, n + 1)]


def price_cash_treasury(pos: book_module.CashTreasury, curve: Curve, effective_tenor: float, spread_bp: float) -> float:
    if effective_tenor <= 0:
        return pos.notional  # matured: pays face
    times = _cashflow_times(effective_tenor)
    n = len(times)
    coupon = pos.coupon_rate / FREQ * FACE
    spread = spread_bp / 10000.0
    pv_per_100 = 0.0
    for k, t in enumerate(times, start=1):
        cashflow = coupon + (FACE if k == n else 0.0)
        pv_per_100 += cashflow * curve.df(t) * math.exp(-spread * t)
    return pos.notional / FACE * pv_per_100


def price_future(pos: book_module.Future, curve: Curve, effective_tenor: float, spread_bp: float) -> float:
    underlying = book_module.CashTreasury(pos.position_id, pos.tenor, FACE, curve.par_rate_at(round(pos.tenor)), 0.0)
    underlying_pv_per_100 = price_cash_treasury(underlying, curve, effective_tenor, spread_bp)
    future_price = underlying_pv_per_100 / pos.conversion_factor
    return pos.notional / FACE * future_price


def price_swap(pos: book_module.Swap, curve: Curve, effective_tenor: float, spread_bp: float) -> float:
    if effective_tenor <= 0:
        return 0.0
    current_par = curve.par_rate_at(effective_tenor) + spread_bp / 10000.0
    pvbp = curve.pvbp_continuous(effective_tenor)
    return pos.notional * (pos.fixed_rate - current_par) * pvbp / 100.0


def price_swaption(pos: book_module.Swaption, curve: Curve, effective_tenor: float, effective_expiry: float,
                    vol: float) -> float:
    if effective_expiry <= 0:
        forward = curve.par_rate_at(max(effective_tenor, 0.25))
        pvbp = curve.pvbp_continuous(max(effective_tenor, 0.25))
        return pos.notional * pvbp * max(forward - pos.strike, 0.0) / 100.0
    forward = curve.par_rate_at(effective_tenor)
    pvbp = curve.pvbp_continuous(effective_tenor)
    price_per_100 = payer_swaption_price(forward, pos.strike, vol, effective_expiry, pvbp, notional=100.0)
    return pos.notional / 100.0 * price_per_100


def price_position(pos, curve: Curve, t_years: float, spread_bp_override: float = None, vol: float = 0.20) -> float:
    """t_years: time elapsed since book inception (all tenors/expiries
    shrink by this amount); spread_bp_override: if given, used instead of
    the position's own book-defined spread (used by attribution to isolate
    the spread-only counterfactual)."""
    if isinstance(pos, book_module.CashTreasury):
        spread = pos.spread_bp if spread_bp_override is None else spread_bp_override
        return price_cash_treasury(pos, curve, pos.tenor - t_years, spread)
    if isinstance(pos, book_module.Future):
        spread = pos.spread_bp if spread_bp_override is None else spread_bp_override
        return price_future(pos, curve, pos.tenor - t_years, spread)
    if isinstance(pos, book_module.Swap):
        spread = pos.spread_bp if spread_bp_override is None else spread_bp_override
        return price_swap(pos, curve, pos.tenor - t_years, spread)
    if isinstance(pos, book_module.Swaption):
        return price_swaption(pos, curve, pos.tenor - t_years, pos.expiry_years - t_years, vol)
    raise TypeError(f"unknown position type: {type(pos)}")


def reval_book(positions: list, curve: Curve, t_years: float = 0.0, spread_overrides: dict = None,
               vol: float = 0.20) -> dict:
    spread_overrides = spread_overrides or {}
    per_position = {}
    for pos in positions:
        override = spread_overrides.get(pos.position_id)
        per_position[pos.position_id] = price_position(pos, curve, t_years, spread_bp_override=override, vol=vol)
    return per_position


def total_pv(positions: list, curve: Curve, t_years: float = 0.0, spread_overrides: dict = None,
             vol: float = 0.20) -> float:
    return sum(reval_book(positions, curve, t_years, spread_overrides, vol).values())

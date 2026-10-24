"""The simulated 40-position book: cash Treasuries, futures, swaps and one
payer swaption, all priced off the single curve in `curve.py`. Every
position's economic terms (notional, direction, tenor) are fixed and
deterministic (no randomness in the book's own construction; only the
market data each position is priced against, in `market_sim.py`, is
randomly simulated), so the same book is used for every scenario, every
session, and every test in this repository.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class CashTreasury:
    position_id: int
    tenor: float      # original years to maturity at book inception
    notional: float   # signed: positive = long
    coupon_rate: float
    spread_bp: float  # idiosyncratic offset vs the curve's own par rate at this tenor, basis points


@dataclass(frozen=True)
class Future:
    position_id: int
    tenor: float          # underlying note's original years to maturity
    notional: float
    conversion_factor: float
    spread_bp: float


@dataclass(frozen=True)
class Swap:
    position_id: int
    tenor: float
    notional: float   # signed: positive = receive-fixed (long duration), negative = pay-fixed
    fixed_rate: float
    spread_bp: float  # idiosyncratic valuation noise vs the curve's own par rate


@dataclass(frozen=True)
class Swaption:
    position_id: int
    tenor: float          # underlying swap tenor
    notional: float
    strike: float
    expiry_years: float   # original time to expiry at book inception


def build_book(base_curve_par_rates: dict) -> list:
    positions = []
    pid = 0

    treasury_tenors = [2.0, 5.0, 10.0, 30.0]
    for i, tenor in enumerate(treasury_tenors):
        for j in range(4):  # 4 notional buckets per tenor = 16 positions
            notional = (50.0 + 25.0 * j) * (1 if j % 2 == 0 else -1)
            coupon = base_curve_par_rates[int(tenor)]
            spread_bp = 1.5 * (1 if j % 2 == 0 else -1) + 0.3 * i
            positions.append(CashTreasury(pid, tenor, notional, coupon, spread_bp))
            pid += 1

    future_tenors = [2.0, 5.0, 10.0, 30.0]
    for i, tenor in enumerate(future_tenors):
        for j in range(3):  # 3 notional buckets per tenor = 12 positions
            notional = (40.0 + 20.0 * j) * (1 if (i + j) % 2 == 1 else -1)
            cf = 0.90 + 0.02 * i
            spread_bp = 0.8 * (1 if j % 2 == 0 else -1)
            positions.append(Future(pid, tenor, notional, cf, spread_bp))
            pid += 1

    swap_tenors = [2.0, 5.0, 10.0, 20.0, 30.0]
    swap_counts = [2, 3, 3, 2, 1]  # sums to 11
    for tenor, count in zip(swap_tenors, swap_counts):
        for j in range(count):
            notional = (60.0 + 15.0 * j) * (1 if j % 2 == 0 else -1)
            fixed_rate = 0.03 + 0.012 * (1.0 - math.exp(-tenor / 8.0))
            spread_bp = 0.5 * (1 if j % 2 == 0 else -1)
            positions.append(Swap(pid, tenor, notional, fixed_rate, spread_bp))
            pid += 1

    positions.append(Swaption(pid, tenor=10.0, notional=75.0, strike=0.05, expiry_years=1.0))
    pid += 1

    assert pid == 40, f"expected exactly 40 positions, built {pid}"
    return positions

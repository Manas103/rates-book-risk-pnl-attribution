"""Independent re-verification of the DV01-neutral sizing claim: instead of
summing each leg's precomputed per-unit DV01 times its notional (the fast
path in `legs.net_dv01`), this builds the actual sized positions and
reprices the whole basket twice (base curve, +1bp parallel) directly, the
same way `rates_risk.pricer`/`screen.forward_swap` price any other
position. Any discrepancy would mean the fast path's linearity assumption
does not actually hold for some instrument, not just a rounding error.
"""

from __future__ import annotations

from dataclasses import replace

from rates_risk import curve as curve_module
from rates_risk import key_rate
from rates_risk.pricer import price_position

from screen import config
from screen.forward_swap import ForwardStartingSwap, price_forward_starting_swap


def _sized_position(leg, notional: float):
    pos = leg.position
    if isinstance(pos, ForwardStartingSwap):
        return replace(pos, notional=notional)
    return replace(pos, notional=notional)


def _price_any(pos, curve) -> float:
    if isinstance(pos, ForwardStartingSwap):
        return price_forward_starting_swap(pos, curve, t_years=0.0)
    return price_position(pos, curve, t_years=0.0)


def basket_net_dv01_oracle(legs_list, notionals: list[float], curve, bump_bp: float = config.DV01_BUMP_BP) -> float:
    sized = [_sized_position(leg, n) for leg, n in zip(legs_list, notionals)]
    base_total = sum(_price_any(pos, curve) for pos in sized)
    bumped_rates = curve_module.shifted_par_rates(curve.par_rates, lambda t: key_rate.parallel_weight(t) * bump_bp / 10000.0)
    bumped_curve = curve_module.bootstrap(bumped_rates)
    bumped_total = sum(_price_any(pos, bumped_curve) for pos in sized)
    return base_total - bumped_total

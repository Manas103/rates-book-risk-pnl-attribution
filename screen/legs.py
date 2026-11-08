"""Leg construction and DV01-neutral sizing for the three candidate trade
shapes (slope, butterfly, swap spread). Every leg is one of the four
curve-priced instrument families this portfolio already has (cash
Treasury, future, par swap) plus the fifth family this package adds
(forward-starting swap); DV01 is always a parallel bump-and-reprice off
the identical `rates_risk.curve.Curve` object, never a second curve.
"""

from __future__ import annotations

from dataclasses import dataclass

from rates_risk import book as book_module
from rates_risk import curve as curve_module
from rates_risk import key_rate
from rates_risk.curve import Curve
from rates_risk.pricer import price_position

from screen import config
from screen.forward_swap import ForwardStartingSwap
from screen.forward_swap import dv01 as fss_dv01
from screen.forward_swap import price_forward_starting_swap


@dataclass(frozen=True)
class Leg:
    position: object
    direction: float  # +1 or -1, the sign applied on top of the position's own unit-notional build
    dv01_per_unit: float  # DV01 at notional=1 (or =1 for FSS), same sign convention as curve.py's dv01


def _unit_swap(tenor: float, curve: Curve) -> book_module.Swap:
    return book_module.Swap(position_id=-1, tenor=tenor, notional=1.0, fixed_rate=curve.par_rate_at(tenor), spread_bp=0.0)


def _unit_future(tenor: float, curve: Curve) -> book_module.Future:
    return book_module.Future(position_id=-1, tenor=tenor, notional=1.0, conversion_factor=1.0, spread_bp=0.0)


def _unit_fss(start: float, tenor: float, curve: Curve) -> ForwardStartingSwap:
    from screen.forward_swap import forward_par_rate

    return ForwardStartingSwap(position_id=-1, start_years=start, tenor_years=tenor, notional=1.0,
                                fixed_rate=forward_par_rate(curve, start, tenor))


def _dv01_per_unit_curve_position(pos, curve: Curve, bump_bp: float = config.DV01_BUMP_BP) -> float:
    base = price_position(pos, curve, t_years=0.0)
    bumped_rates = curve_module.shifted_par_rates(curve.par_rates, lambda t: key_rate.parallel_weight(t) * bump_bp / 10000.0)
    bumped = curve_module.bootstrap(bumped_rates)
    bumped_price = price_position(pos, bumped, t_years=0.0)
    return base - bumped_price


def build_slope_legs(name: str, curve: Curve) -> tuple[Leg, Leg]:
    """A 1-year-forward-starting swap on the short tenor (isolating the
    forward-curve view from near-dated roll noise) against a spot par
    swap on the long tenor (a 1-year-forward 30-year leg would run to
    year 31, past this curve's longest pillar, so only the short leg uses
    the forward start)."""
    short_t, long_t = config.SLOPE_PAIRS[name]
    short_leg = _unit_fss(config.FWD_START_YEARS, short_t, curve)
    long_leg = _unit_swap(long_t, curve)
    dv01_short = fss_dv01(short_leg, curve, t_years=0.0, bump_bp=config.DV01_BUMP_BP)
    dv01_long = _dv01_per_unit_curve_position(long_leg, curve)
    return (
        Leg(short_leg, direction=1.0, dv01_per_unit=dv01_short),
        Leg(long_leg, direction=-1.0, dv01_per_unit=dv01_long),
    )


def build_fly_legs(name: str, curve: Curve) -> tuple[Leg, Leg, Leg]:
    """Spot par swaps, 3 legs: belly vs two wings."""
    a, b, c = config.FLY_TRIPLES[name]
    wing1 = _unit_swap(a, curve)
    belly = _unit_swap(b, curve)
    wing2 = _unit_swap(c, curve)
    return (
        Leg(wing1, direction=-1.0, dv01_per_unit=_dv01_per_unit_curve_position(wing1, curve)),
        Leg(belly, direction=2.0, dv01_per_unit=_dv01_per_unit_curve_position(belly, curve)),
        Leg(wing2, direction=-1.0, dv01_per_unit=_dv01_per_unit_curve_position(wing2, curve)),
    )


def build_swap_spread_legs(tenor: float, curve: Curve) -> tuple[Leg, Leg]:
    """A spot par swap vs a Treasury future at the same tenor."""
    swap_leg = _unit_swap(tenor, curve)
    future_leg = _unit_future(tenor, curve)
    return (
        Leg(swap_leg, direction=1.0, dv01_per_unit=_dv01_per_unit_curve_position(swap_leg, curve)),
        Leg(future_leg, direction=-1.0, dv01_per_unit=_dv01_per_unit_curve_position(future_leg, curve)),
    )


def size_two_leg_dv01_neutral(legs: tuple[Leg, Leg], anchor_notional: float = config.REFERENCE_NOTIONAL) -> list[float]:
    """Notionals (signed) for a 2-leg trade: the first leg gets
    `anchor_notional` in its own direction; the second is sized so its
    DV01 exactly offsets the first's."""
    leg_a, leg_b = legs
    notional_a = anchor_notional * leg_a.direction
    dv01_a = notional_a * leg_a.dv01_per_unit
    notional_b = -dv01_a / leg_b.dv01_per_unit if leg_b.dv01_per_unit != 0 else 0.0
    return [notional_a, notional_b]


def size_fly_dv01_neutral(legs: tuple[Leg, Leg, Leg], belly_notional: float = config.REFERENCE_NOTIONAL) -> list[float]:
    """Belly gets `belly_notional`; each wing gets half of the belly's
    DV01, offsetting sign, split evenly between the two wings."""
    wing1, belly, wing2 = legs
    notional_belly = belly_notional * belly.direction
    dv01_belly = notional_belly * belly.dv01_per_unit
    target_wing_dv01 = -dv01_belly / 2.0
    notional_wing1 = target_wing_dv01 / wing1.dv01_per_unit if wing1.dv01_per_unit != 0 else 0.0
    notional_wing2 = target_wing_dv01 / wing2.dv01_per_unit if wing2.dv01_per_unit != 0 else 0.0
    return [notional_wing1, notional_belly, notional_wing2]


def net_dv01(legs: list[Leg], notionals: list[float]) -> float:
    return sum(n * leg.dv01_per_unit for leg, n in zip(legs, notionals))

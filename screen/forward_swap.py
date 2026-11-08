"""Forward-starting swaps: the fifth instrument family. Priced off the
identical `rates_risk.curve.Curve` every other position in this portfolio
uses, via the same discount factors, not a second curve.
"""

from __future__ import annotations

from dataclasses import dataclass

from rates_risk.curve import Curve


@dataclass(frozen=True)
class ForwardStartingSwap:
    position_id: int
    start_years: float   # years from today to the swap's own effective date
    tenor_years: float    # swap length once it starts
    notional: float        # signed: positive = receive-fixed
    fixed_rate: float


def forward_par_rate(curve: Curve, start: float, tenor: float) -> float:
    """The par rate of a swap that starts in `start` years and runs for
    `tenor` years, both whole-year boundaries in every call this package
    makes, so `curve.pvbp` (integer-year annuity) is exact, no fractional
    interpolation needed."""
    end = start + tenor
    annuity = curve.pvbp(int(end)) - curve.pvbp(int(start))
    return (curve.df(start) - curve.df(end)) / annuity


def price_forward_starting_swap(pos: ForwardStartingSwap, curve: Curve, t_years: float) -> float:
    """t_years: time elapsed since the trade was put on. Before the swap's
    own effective date, this is a genuine forward-starting swap (discounted
    back to today through the curve's own discount factors, no separate
    forward-measure adjustment needed since the annuity above already does
    that). Once the effective date has passed, it behaves like any other
    spot-starting swap with a shrinking remaining tenor."""
    remaining_to_start = pos.start_years - t_years
    if remaining_to_start > 0:
        forward_rate = forward_par_rate(curve, remaining_to_start, pos.tenor_years)
        end = remaining_to_start + pos.tenor_years
        annuity = curve.pvbp(int(end)) - curve.pvbp(int(remaining_to_start))
        return pos.notional * (pos.fixed_rate - forward_rate) * annuity / 100.0
    remaining_tenor = pos.tenor_years + remaining_to_start  # remaining_to_start is <= 0 here
    if remaining_tenor <= 0:
        return 0.0
    current_par = curve.par_rate_at(remaining_tenor)
    pvbp = curve.pvbp_continuous(remaining_tenor)
    return pos.notional * (pos.fixed_rate - current_par) * pvbp / 100.0


def dv01(pos: ForwardStartingSwap, curve: Curve, t_years: float, bump_bp: float) -> float:
    """Parallel bump-and-reprice DV01: price drop per `bump_bp` of
    parallel curve increase (positive for a receive-fixed/long-duration
    position)."""
    from rates_risk import curve as curve_module
    from rates_risk import key_rate

    base_price = price_forward_starting_swap(pos, curve, t_years)
    bumped_rates = curve_module.shifted_par_rates(curve.par_rates, lambda t: key_rate.parallel_weight(t) * bump_bp / 10000.0)
    bumped_curve = curve_module.bootstrap(bumped_rates)
    bumped_price = price_forward_starting_swap(pos, bumped_curve, t_years)
    return base_price - bumped_price

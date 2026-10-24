"""OIS-discounted par-swap curve bootstrap, the single curve every
position in the book is priced from. Self-contained: this repo does not
import from any other repo in the portfolio, even though the bootstrap
technique (annual-pay par-swap identity, bisection-solved for tenors not
adjacent to the last pinned integer year) is the same one used in
`treasury-basis-implied-repo-monitor`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

TENORS: list[int] = [1, 2, 3, 5, 7, 10, 15, 20, 30]


@dataclass
class Curve:
    par_rates: dict
    discount_factors: dict = field(default_factory=dict)

    def df(self, t) -> float:
        lo = int(t)
        if lo == t:
            return self.discount_factors[lo]
        hi = lo + 1
        frac = t - lo
        # log-linear interpolation between adjacent integer-year discount factors
        return self.discount_factors[lo] ** (1.0 - frac) * self.discount_factors[hi] ** frac

    def zero_rate(self, t) -> float:
        return -math.log(self.df(t)) / t if t > 0 else 0.0

    def pvbp(self, tenor: int) -> float:
        return sum(self.discount_factors[k] for k in range(1, tenor + 1))

    def pvbp_continuous(self, tenor: float) -> float:
        """Annual-pay annuity factor at a possibly fractional tenor: full
        integer years at their own discount factor, plus one partial final
        period sized by the fractional remainder, both consistent with the
        curve's own annual-pay bootstrap convention."""
        whole = int(tenor)
        frac = tenor - whole
        total = sum(self.discount_factors[k] for k in range(1, whole + 1))
        if frac > 0:
            total += frac * self.df(tenor)
        return total

    def par_rate_at(self, tenor: int) -> float:
        """Par rate at an input tenor (exact) or, for an arbitrary tenor,
        the rate implied by the curve's own discount factors."""
        if tenor in self.par_rates:
            return self.par_rates[tenor]
        return (1.0 - self.df(tenor)) / sum(self.df(k) for k in range(1, int(tenor) + 1))

    def implied_par_rate(self, tenor: int) -> float:
        return (1.0 - self.discount_factors[tenor]) / self.pvbp(tenor)


def _interp_weight(k: int, t_prev: int, t_new: int) -> float:
    return (k - t_prev) / (t_new - t_prev)


def _par_condition(df_new: float, t_prev: int, df_prev: float, t_new: int, par_rate: float, known_sum: float) -> float:
    unknown_sum = 0.0
    for k in range(t_prev + 1, t_new + 1):
        if k == t_new:
            unknown_sum += df_new
        else:
            w = _interp_weight(k, t_prev, t_new)
            unknown_sum += (df_prev ** (1.0 - w)) * (df_new ** w)
    return par_rate * (known_sum + unknown_sum) - (1.0 - df_new)


def _solve_unknown_df(t_prev: int, df_prev: float, t_new: int, par_rate: float, known_sum: float,
                       lo: float = 1e-6, hi: float = 1.5, tol: float = 1e-14, max_iter: int = 200) -> float:
    f_lo = _par_condition(lo, t_prev, df_prev, t_new, par_rate, known_sum)
    f_hi = _par_condition(hi, t_prev, df_prev, t_new, par_rate, known_sum)
    if f_lo * f_hi > 0:
        raise ValueError(f"root not bracketed for tenor {t_new}")
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        f_mid = _par_condition(mid, t_prev, df_prev, t_new, par_rate, known_sum)
        if abs(f_mid) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2.0


def bootstrap(par_rates: dict) -> Curve:
    if sorted(par_rates) != TENORS:
        raise ValueError(f"expected exactly the tenors {TENORS}, got {sorted(par_rates)}")

    dfs = {0: 1.0}
    t_prev, df_prev = 0, 1.0
    for t in TENORS:
        s = par_rates[t]
        known_sum = sum(dfs[k] for k in range(1, t_prev + 1))
        df_t = _solve_unknown_df(t_prev, df_prev, t, s, known_sum)
        for k in range(t_prev + 1, t):
            w = _interp_weight(k, t_prev, t)
            dfs[k] = (df_prev ** (1.0 - w)) * (df_t ** w)
        dfs[t] = df_t
        t_prev, df_prev = t, df_t

    return Curve(par_rates=dict(par_rates), discount_factors=dfs)


def shifted_par_rates(par_rates: dict, weight_fn) -> dict:
    """Returns a new par-rate dict with every tenor bumped by
    `weight_fn(tenor)` basis points (in decimal, i.e. already divided by
    10000), used by both the parallel-shift scenario (weight_fn == 1
    everywhere) and the key-rate bucket shocks (a triangular weight_fn)."""
    return {t: r + weight_fn(t) for t, r in par_rates.items()}

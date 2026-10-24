"""Daily P&L attribution into curve, carry, spread and residual.

Each of the first three buckets is a full-reprice counterfactual (not a
linear Taylor sum of Greeks): starting from yesterday's actual priced
state, perturb exactly one input (the curve, the elapsed time, or the
positions' idiosyncratic spreads/vol) to today's value while holding the
other two fixed at yesterday's, and reprice the whole book. The residual
is whatever is left after the actual day-over-day P&L has those three
counterfactual moves subtracted; it is not forced to be the three
Greeks' leftover analytically, it is measured as the gap between four
full repricings and reported however large or small it comes out.
"""
from __future__ import annotations

from .curve import TENORS, bootstrap
from .market_sim import par_rates_on, spreads_on
from .pricer import total_pv

TRADING_DAYS_PER_YEAR = 252


def _bootstrap_all_sessions(sim: dict) -> list:
    return [bootstrap(par_rates_on(sim, s)) for s in range(sim["num_sessions"])]


def daily_attribution(positions: list, sim: dict) -> list:
    curves = _bootstrap_all_sessions(sim)
    rows = []

    for t in range(1, sim["num_sessions"]):
        t_prev_years = (t - 1) / TRADING_DAYS_PER_YEAR
        t_curr_years = t / TRADING_DAYS_PER_YEAR

        curve_prev, curve_curr = curves[t - 1], curves[t]
        spreads_prev, spreads_curr = spreads_on(sim, t - 1), spreads_on(sim, t)
        vol_prev, vol_curr = sim["vol_path"][t - 1], sim["vol_path"][t]

        pv_prev = total_pv(positions, curve_prev, t_prev_years, spreads_prev, vol_prev)
        pv_curr = total_pv(positions, curve_curr, t_curr_years, spreads_curr, vol_curr)
        actual_pnl = pv_curr - pv_prev

        curve_only_pv = total_pv(positions, curve_curr, t_prev_years, spreads_prev, vol_prev)
        curve_component = curve_only_pv - pv_prev

        carry_only_pv = total_pv(positions, curve_prev, t_curr_years, spreads_prev, vol_prev)
        carry_component = carry_only_pv - pv_prev

        spread_only_pv = total_pv(positions, curve_prev, t_prev_years, spreads_curr, vol_curr)
        spread_component = spread_only_pv - pv_prev

        residual = actual_pnl - curve_component - carry_component - spread_component

        rows.append(
            {
                "session": t,
                "actual_pnl": actual_pnl,
                "curve": curve_component,
                "carry": carry_component,
                "spread": spread_component,
                "residual": residual,
            }
        )

    return rows


def summarize(rows: list) -> dict:
    gross_pnl = sum(abs(r["actual_pnl"]) for r in rows)
    gross_residual = sum(abs(r["residual"]) for r in rows)
    pct_unexplained = 100.0 * gross_residual / gross_pnl if gross_pnl > 0 else float("nan")
    return {
        "num_sessions": len(rows),
        "gross_pnl": gross_pnl,
        "gross_residual": gross_residual,
        "pct_unexplained": pct_unexplained,
        "total_curve": sum(r["curve"] for r in rows),
        "total_carry": sum(r["carry"] for r in rows),
        "total_spread": sum(r["spread"] for r in rows),
        "total_residual": sum(r["residual"] for r in rows),
        "total_actual": sum(r["actual_pnl"] for r in rows),
    }

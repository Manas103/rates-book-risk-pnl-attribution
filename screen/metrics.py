"""The five screened series (2 slopes, 2 butterflies, 5 swap spreads)
across 500 simulated sessions, and the carry-plus-roll-down natural drift
of each, computed straight from the curve's own par rates.
"""

from __future__ import annotations

import random

from rates_risk import market_sim

from screen import base_curve, config


def simulate_curve_paths(seed: int = config.SEED, num_sessions: int = config.N_SESSIONS) -> dict:
    """Reuses rates_risk.market_sim.simulate unmodified, with an empty
    position list (this screener needs the curve-input random walk only,
    not the book's own per-position spread paths)."""
    return market_sim.simulate(base_curve.BASE_PAR_RATES, positions=[], num_sessions=num_sessions, seed=seed)


def simulate_swap_spreads(seed: int = config.SEED + 1, num_sessions: int = config.N_SESSIONS) -> dict:
    """Mean-reverting (AR(1)) around each tenor's own declared basis, not a
    random walk: a real swap spread oscillates around a repo/credit-driven
    level rather than drifting arbitrarily far from it, which is also what
    makes "2-sigma dislocation that should revert" an economically
    coherent screen in the first place (see README Findings for the first,
    random-walk design this replaced)."""
    rng = random.Random(seed)
    rho = config.SWAP_SPREAD_MEAN_REVERSION
    paths = {t: [config.SWAP_SPREAD_BASIS_BP[t]] for t in config.SWAP_SPREAD_TENORS}
    for _ in range(1, num_sessions):
        for t in config.SWAP_SPREAD_TENORS:
            basis = config.SWAP_SPREAD_BASIS_BP[t]
            prev_dev = paths[t][-1] - basis
            new_dev = rho * prev_dev + rng.gauss(0, config.SWAP_SPREAD_DAILY_VOL_BP)
            paths[t].append(basis + new_dev)
    return paths


def slope_series(sim: dict, name: str) -> list[float]:
    short_t, long_t = config.SLOPE_PAIRS[name]
    return [b - a for a, b in zip(sim["par_rate_paths"][short_t], sim["par_rate_paths"][long_t])]


def fly_series(sim: dict, name: str) -> list[float]:
    a, b, c = config.FLY_TRIPLES[name]
    pa, pb, pc = sim["par_rate_paths"][a], sim["par_rate_paths"][b], sim["par_rate_paths"][c]
    return [-x + 2 * y - z for x, y, z in zip(pa, pb, pc)]


def swap_spread_series(spread_sim: dict, tenor: int) -> list[float]:
    return spread_sim[tenor]


def rolldown_bp(curve, tenor: float, horizon: float = config.HORIZON_YEARS) -> float:
    shorter = max(tenor - horizon, 0.01)
    return (curve.par_rate_at(tenor) - curve.par_rate_at(shorter)) * 10000.0


def carry_bp(curve, tenor: float, funding_rate: float, horizon: float = config.HORIZON_YEARS) -> float:
    return (curve.par_rate_at(tenor) - funding_rate) * 10000.0 * horizon


def leg_drift_bp(curve, tenor: float, funding_rate: float, horizon: float = config.HORIZON_YEARS) -> float:
    return rolldown_bp(curve, tenor, horizon) + carry_bp(curve, tenor, funding_rate, horizon)


def slope_drift_bp(curve, name: str, funding_rate: float) -> float:
    short_t, long_t = config.SLOPE_PAIRS[name]
    return leg_drift_bp(curve, long_t, funding_rate) - leg_drift_bp(curve, short_t, funding_rate)


def fly_drift_bp(curve, name: str, funding_rate: float) -> float:
    a, b, c = config.FLY_TRIPLES[name]
    return -leg_drift_bp(curve, a, funding_rate) + 2 * leg_drift_bp(curve, b, funding_rate) - leg_drift_bp(curve, c, funding_rate)


def swap_spread_drift_bp(horizon: float = config.HORIZON_YEARS) -> float:
    """The swap leg carries at a small persistent discount to the futures
    leg's repo rate (REPO_SPECIAL_BP); the curve-level carry/roll-down is
    identical on both legs in this simulated world (same curve), so it
    cancels and only the repo-specialness drift survives."""
    return config.REPO_SPECIAL_BP * horizon

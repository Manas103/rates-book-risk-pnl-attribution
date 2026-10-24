"""Synthetic 250-session market: a fixed-seed daily random walk of the
curve's own 9 par-rate inputs, a repo/funding rate, each of the book's 39
cash/futures/swap positions' own idiosyncratic spread (independent small
daily noise, the source of the "spread" attribution bucket), and the
swaption's implied vol. Entirely synthetic; no live or historical market
data anywhere in this repository.
"""
from __future__ import annotations

import random

from .book import Swaption
from .curve import TENORS

SEED = 77061
NUM_SESSIONS = 250
TRADING_DAYS_PER_YEAR = 252

LEVEL_DAILY_VOL = 0.00035
FUNDING_START = 0.0500
FUNDING_DAILY_VOL = 0.00020
FUNDING_MIN, FUNDING_MAX = 0.02, 0.08
SPREAD_DAILY_VOL_BP = 0.15
VOL_START = 0.20
VOL_DAILY_VOL = 0.0015
VOL_MIN, VOL_MAX = 0.08, 0.40


def simulate(base_par_rates: dict, positions: list, num_sessions: int = NUM_SESSIONS, seed: int = SEED) -> dict:
    rng = random.Random(seed)

    par_rate_paths = {t: [base_par_rates[t]] for t in TENORS}
    funding_path = [FUNDING_START]
    vol_path = [VOL_START]
    spread_paths = {pos.position_id: [pos.spread_bp] for pos in positions if not isinstance(pos, Swaption)}

    for _ in range(1, num_sessions):
        level_shock = rng.gauss(0, LEVEL_DAILY_VOL)
        for t in TENORS:
            idio = rng.gauss(0, LEVEL_DAILY_VOL * 0.15)
            par_rate_paths[t].append(par_rate_paths[t][-1] + level_shock + idio)

        funding = funding_path[-1] + rng.gauss(0, FUNDING_DAILY_VOL)
        funding_path.append(min(max(funding, FUNDING_MIN), FUNDING_MAX))

        vol = vol_path[-1] + rng.gauss(0, VOL_DAILY_VOL)
        vol_path.append(min(max(vol, VOL_MIN), VOL_MAX))

        for pos_id in spread_paths:
            spread_paths[pos_id].append(spread_paths[pos_id][-1] + rng.gauss(0, SPREAD_DAILY_VOL_BP))

    return {
        "par_rate_paths": par_rate_paths,
        "funding_path": funding_path,
        "vol_path": vol_path,
        "spread_paths": spread_paths,
        "num_sessions": num_sessions,
    }


def par_rates_on(sim: dict, session: int) -> dict:
    return {t: sim["par_rate_paths"][t][session] for t in TENORS}


def spreads_on(sim: dict, session: int) -> dict:
    return {pos_id: path[session] for pos_id, path in sim["spread_paths"].items()}

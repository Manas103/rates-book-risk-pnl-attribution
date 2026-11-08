"""Shared constants for the rates relative-value screener. Nothing here
modifies `rates_risk/`; this package only imports its curve, key-rate and
market-sim modules and adds a fifth instrument family (forward-starting
swaps) and a new, separate 500-session simulation on top.
"""

from __future__ import annotations

SEED = 81031
N_SESSIONS = 500

Z_THRESHOLD = 2.0
ROLL_WINDOW = 200  # trailing sessions used for the rolling mean/std, point-in-time

HORIZON_YEARS = 1.0 / 12.0  # one-month holding period for carry/roll-down

SLOPE_PAIRS = {
    "2s10s": (2, 10),
    "5s30s": (5, 30),
}
FLY_TRIPLES = {
    "2s5s10s": (2, 5, 10),
    "5s10s30s": (5, 10, 30),
}
SWAP_SPREAD_TENORS = [2, 5, 10, 20, 30]

# Declared swap-vs-Treasury basis curve (bp) and its own small simulated
# daily noise; the basis itself is not derived from the OIS curve (a real
# swap spread reflects repo specialness and credit, not the discounting
# curve both legs happen to share in this simulated world).
SWAP_SPREAD_BASIS_BP = {2: 12.0, 5: 18.0, 10: 24.0, 20: 16.0, 30: 8.0}
SWAP_SPREAD_DAILY_VOL_BP = 0.4
SWAP_SPREAD_MEAN_REVERSION = 0.92  # AR(1) rho on the deviation from basis

# Forward-starting swaps used for the two slope trades: a 1-year-forward
# 2-year and a 1-year-forward 10-year swap for 2s10s, and similarly for
# 5s30s, isolating the forward-curve view from near-dated roll noise.
FWD_START_YEARS = 1.0

# A general collateralized-funding proxy (reused, not re-simulated, from
# rates_risk.market_sim.FUNDING_START) and the repo-specialness drift
# applied only to the swap leg of a swap-spread trade: Treasury repo
# trades persistently a little special (cheaper) than unsecured OIS
# funding, which is the real-world carry driver of a swap-spread position
# once both legs share the same discounting curve.
REPO_SPECIAL_BP = -3.0

# Illustrative half-spread (round-trip execution cost), bp of the metric
# itself, one per trade shape (2-leg slope, 3-leg fly, 2-leg swap spread).
HALF_SPREAD_BP = {
    "slope": 1.2,
    "fly": 2.0,
    "swap_spread": 1.0,
}

DV01_BUMP_BP = 1.0
REFERENCE_NOTIONAL = 100.0  # the belly/anchor leg's notional, $mm
DV01_NEUTRAL_TOLERANCE_USD = 1.0  # out of a gross leg DV01 on the order of $1,000s-$10,000s

"""Scenario P&L: parallel shifts, 2s10s twists and a 25bp funding shock.

Parallel shifts and twists are full revaluations (the whole book repriced
under the shocked curve, not a linear DV01 projection), so each scenario
also reports the linear (DV01-based) approximation alongside the full
reval, the same full-reval-vs-Taylor comparison
`options-pricing-greeks-engine`'s scenario/VaR extension makes for an
equity options book.

The funding shock is not a curve shock: cash Treasury positions in a real
book are financed in repo, a cost that does not run through the pricing
curve at all here (the curve is OIS/swap, not a repo curve). It is
modeled the same way `treasury-basis-implied-repo-monitor`'s
`funding_shock.py` treats it, as a comparative-statics add-on isolating
the financing channel, reimplemented independently in this self-contained
repo.
"""
from __future__ import annotations

from .book import CashTreasury
from .curve import Curve
from .key_rate import KEY_RATE_NODES, parallel_weight, shock_curve, triangular_weight
from .pricer import total_pv

FUNDING_SHOCK_HOLDING_DAYS = 20


def parallel_shift_pnl(positions: list, curve: Curve, shift_bp: float, total_dv01: float) -> dict:
    pv0 = total_pv(positions, curve)
    shocked = shock_curve(curve, parallel_weight, shift_bp)
    pv1 = total_pv(positions, shocked)
    full_reval = pv1 - pv0
    linear_approx = -total_dv01 * shift_bp
    return {"shift_bp": shift_bp, "full_reval": full_reval, "linear_approx": linear_approx,
            "convexity_residual": full_reval - linear_approx}


def twist_pnl(positions: list, curve: Curve, short_node: int, long_node: int, size_bp: float) -> dict:
    """Steepener: short_node down by size_bp, long_node up by size_bp,
    the standard construction for a 2s10s steepening twist."""
    pv0 = total_pv(positions, curve)

    def twist_weight(tenor):
        return -triangular_weight(short_node)(tenor) + triangular_weight(long_node)(tenor)

    shocked = shock_curve(curve, twist_weight, size_bp)
    pv1 = total_pv(positions, shocked)
    return {"short_node": short_node, "long_node": long_node, "size_bp": size_bp, "full_reval": pv1 - pv0}


def funding_shock_pnl(positions: list, shock_bp: float, holding_days: int = FUNDING_SHOCK_HOLDING_DAYS) -> float:
    """Sum over cash Treasury positions only (the financed, repo-carried
    legs of the book): -notional * shock * holding_days/360, the same
    financing-cost-delta shape as the sibling repo's funding shock."""
    total = 0.0
    for pos in positions:
        if isinstance(pos, CashTreasury):
            total += -pos.notional * (shock_bp / 10000.0) * (holding_days / 360.0)
    return total


def total_dv01(positions: list, curve: Curve, bp_size: float = 1.0) -> float:
    pv0 = total_pv(positions, curve)
    shocked = shock_curve(curve, parallel_weight, bp_size)
    return (pv0 - total_pv(positions, shocked)) / bp_size


def key_rate_dv01s(positions: list, curve: Curve, bp_size: float = 1.0) -> dict:
    pv0 = total_pv(positions, curve)
    out = {}
    for node in KEY_RATE_NODES:
        shocked = shock_curve(curve, triangular_weight(node), bp_size)
        out[node] = (pv0 - total_pv(positions, shocked)) / bp_size
    return out

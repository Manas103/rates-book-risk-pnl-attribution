"""Key-rate (partial-duration) shock construction: a standard triangular
basis over the 6 key-rate nodes, each node's weight function equal to 1 at
its own node and falling linearly to 0 at the two adjacent key-rate
nodes, 0 beyond. By construction these 6 weight functions sum to exactly
1 at every one of the curve's own 9 input tenors, which is what lets the
book's 6 key-rate DV01s be compared against its single parallel-shift
DV01 as a reconciliation check (`scripts/run_key_rate_check.py`): to the
extent the two disagree, it is because the curve bootstrap and the book's
own pricers are nonlinear in the curve inputs, not because the triangular
weights fail to add up to a parallel shift.
"""
from __future__ import annotations

from . import curve as curve_module

KEY_RATE_NODES: list[int] = [1, 2, 5, 10, 20, 30]


def triangular_weight(node: int, nodes: list[int] = KEY_RATE_NODES):
    nodes = sorted(nodes)
    i = nodes.index(node)
    left = nodes[i - 1] if i > 0 else None
    right = nodes[i + 1] if i < len(nodes) - 1 else None

    def weight(tenor: float) -> float:
        if tenor == node:
            return 1.0
        if tenor < node:
            if left is None:
                return 1.0  # flat-extrapolated below the shortest key-rate node
            if tenor <= left:
                return 0.0
            return (tenor - left) / (node - left)
        if right is None:
            return 1.0  # flat-extrapolated beyond the longest key-rate node
        if tenor >= right:
            return 0.0
        return (right - tenor) / (right - node)

    return weight


def parallel_weight(tenor: float) -> float:
    return 1.0


def shock_curve(base_curve: curve_module.Curve, weight_fn, bp_size: float) -> curve_module.Curve:
    bumped = curve_module.shifted_par_rates(base_curve.par_rates, lambda t: weight_fn(t) * bp_size / 10000.0)
    return curve_module.bootstrap(bumped)

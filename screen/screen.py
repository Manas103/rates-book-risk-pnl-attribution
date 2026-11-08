"""The cross-sectional screen: rolling z-scores on 9 curve-shaped series
across 500 simulated sessions, every |z| >= 2 candidate's raw mean-
reversion view compared against the same trade's carry, roll-down and an
illustrative half-spread, and DV01-neutral leg sizing for every candidate
actually built.
"""

from __future__ import annotations

from dataclasses import dataclass

from rates_risk.curve import bootstrap

from screen import config, legs, metrics


def rolling_zscores(series: list[float], window: int = config.ROLL_WINDOW) -> list[float | None]:
    """Point-in-time: z[i] uses only series[i-window:i] (strictly before i).
    None for the first `window` sessions, where there is no full trailing
    window yet."""
    out: list[float | None] = [None] * len(series)
    for i in range(window, len(series)):
        trailing = series[i - window:i]
        mean = sum(trailing) / window
        var = sum((x - mean) ** 2 for x in trailing) / (window - 1)
        std = var ** 0.5
        out[i] = 0.0 if std == 0 else (series[i] - mean) / std
    return out


@dataclass
class Candidate:
    metric: str
    session: int
    z: float
    reversion_bp: float
    drift_bp: float
    half_spread_bp: float
    net_before_cost_bp: float
    net_after_cost_bp: float
    reversed: bool


def _std_of_window(series: list[float], i: int, window: int) -> float:
    trailing = series[i - window:i]
    mean = sum(trailing) / window
    var = sum((x - mean) ** 2 for x in trailing) / (window - 1)
    return var ** 0.5


def build_all_series(sim: dict, spread_sim: dict) -> dict[str, list[float]]:
    series = {}
    for name in config.SLOPE_PAIRS:
        series[name] = metrics.slope_series(sim, name)
    for name in config.FLY_TRIPLES:
        series[name] = metrics.fly_series(sim, name)
    for tenor in config.SWAP_SPREAD_TENORS:
        series[f"swap_spread_{tenor}y"] = metrics.swap_spread_series(spread_sim, tenor)
    return series


def _trade_shape(metric: str) -> str:
    if metric in config.SLOPE_PAIRS:
        return "slope"
    if metric in config.FLY_TRIPLES:
        return "fly"
    return "swap_spread"


def _drift_bp_for(metric: str, curve, funding_rate: float) -> float:
    if metric in config.SLOPE_PAIRS:
        return metrics.slope_drift_bp(curve, metric, funding_rate)
    if metric in config.FLY_TRIPLES:
        return metrics.fly_drift_bp(curve, metric, funding_rate)
    return metrics.swap_spread_drift_bp()


def run_screen() -> dict:
    sim = metrics.simulate_curve_paths()
    spread_sim = metrics.simulate_swap_spreads()
    all_series = build_all_series(sim, spread_sim)

    z_by_metric = {name: rolling_zscores(s) for name, s in all_series.items()}

    candidates: list[Candidate] = []
    for metric, zseries in z_by_metric.items():
        shape = _trade_shape(metric)
        half_spread = config.HALF_SPREAD_BP[shape]
        for i, z in enumerate(zseries):
            if z is None or abs(z) < config.Z_THRESHOLD:
                continue
            std = _std_of_window(all_series[metric], i, config.ROLL_WINDOW)
            reversion_bp = -z * std * 10000.0 if shape != "swap_spread" else -z * std
            par_rates_i = {t: sim["par_rate_paths"][t][i] for t in sim["par_rate_paths"]}
            curve_i = bootstrap(par_rates_i)
            drift_bp = _drift_bp_for(metric, curve_i, sim["funding_path"][i])
            net_before = reversion_bp + drift_bp
            net_after = net_before - half_spread * (1.0 if net_before >= 0 else -1.0)
            reversed_sign = (net_after >= 0) != (reversion_bp >= 0)
            candidates.append(
                Candidate(metric, i, z, reversion_bp, drift_bp, half_spread, net_before, net_after, reversed_sign)
            )

    n_candidates = len(candidates)
    n_reversed = sum(1 for c in candidates if c.reversed)

    dv01_check = _check_dv01_neutral_sizing()

    return {
        "n_candidates": n_candidates,
        "n_reversed": n_reversed,
        "reversed_pct": (n_reversed / n_candidates * 100.0) if n_candidates else 0.0,
        "candidates": candidates,
        "dv01_neutral_check": dv01_check,
    }


def _check_dv01_neutral_sizing() -> dict:
    from screen import base_curve, oracle

    curve = bootstrap(base_curve.BASE_PAR_RATES)
    max_abs_net_dv01 = 0.0
    max_gross_dv01 = 0.0
    max_oracle_diff = 0.0
    n_checked = 0

    def _check(leg_group, notionals):
        nonlocal max_abs_net_dv01, max_gross_dv01, max_oracle_diff, n_checked
        net = legs.net_dv01(list(leg_group), notionals)
        gross = sum(abs(n * leg.dv01_per_unit) for n, leg in zip(notionals, leg_group))
        oracle_net = oracle.basket_net_dv01_oracle(list(leg_group), notionals, curve)
        max_abs_net_dv01 = max(max_abs_net_dv01, abs(net))
        max_gross_dv01 = max(max_gross_dv01, gross)
        max_oracle_diff = max(max_oracle_diff, abs(net - oracle_net))
        n_checked += 1

    for name in config.SLOPE_PAIRS:
        leg_pair = legs.build_slope_legs(name, curve)
        _check(leg_pair, legs.size_two_leg_dv01_neutral(leg_pair))
    for name in config.FLY_TRIPLES:
        leg_triple = legs.build_fly_legs(name, curve)
        _check(leg_triple, legs.size_fly_dv01_neutral(leg_triple))
    for tenor in config.SWAP_SPREAD_TENORS:
        leg_pair = legs.build_swap_spread_legs(tenor, curve)
        _check(leg_pair, legs.size_two_leg_dv01_neutral(leg_pair))

    return {
        "n_trade_shapes_checked": n_checked,
        "max_abs_net_dv01_usd": max_abs_net_dv01,
        "max_gross_leg_dv01_usd": max_gross_dv01,
        "max_oracle_diff_usd": max_oracle_diff,
        "meets_tolerance": max_abs_net_dv01 <= config.DV01_NEUTRAL_TOLERANCE_USD,
    }

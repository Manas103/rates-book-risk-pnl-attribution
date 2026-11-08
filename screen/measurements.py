"""The claim measurements for the relative-value screener, each an honest
measured number, not a target."""

from __future__ import annotations

from screen import config, screen as screen_module


def measure_screen() -> dict:
    result = screen_module.run_screen()
    return {
        "n_sessions": config.N_SESSIONS,
        "n_metrics_screened": len(config.SLOPE_PAIRS) + len(config.FLY_TRIPLES) + len(config.SWAP_SPREAD_TENORS),
        "z_threshold": config.Z_THRESHOLD,
        "n_two_sigma_candidates": result["n_candidates"],
        "n_reversed_by_cost": result["n_reversed"],
        "reversed_pct": result["reversed_pct"],
        "dv01_neutral_check": result["dv01_neutral_check"],
    }


def measure_instrument_families() -> dict:
    """Claim: cash Treasuries, futures, par swaps and forward-starting
    swaps all priced off one OIS-bootstrapped curve."""
    from rates_risk import book as book_module
    from rates_risk.curve import bootstrap
    from rates_risk.pricer import price_position

    from screen import base_curve, legs
    from screen.forward_swap import price_forward_starting_swap

    curve = bootstrap(base_curve.BASE_PAR_RATES)
    book = book_module.build_book(base_curve.BASE_PAR_RATES)
    families_priced = {
        "cash_treasury": any(isinstance(p, book_module.CashTreasury) for p in book) and
        price_position(next(p for p in book if isinstance(p, book_module.CashTreasury)), curve, 0.0) is not None,
        "future": any(isinstance(p, book_module.Future) for p in book),
        "swap": any(isinstance(p, book_module.Swap) for p in book),
    }
    fss_leg = legs.build_slope_legs("2s10s", curve)[0]
    families_priced["forward_starting_swap"] = price_forward_starting_swap(fss_leg.position, curve, 0.0) is not None
    return {
        "families_priced_off_one_curve": families_priced,
        "all_four_present": all(families_priced.values()),
    }

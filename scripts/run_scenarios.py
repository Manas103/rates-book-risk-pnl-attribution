#!/usr/bin/env python
"""Runs the parallel-shift, 2s10s twist and 25bp funding-shock scenarios
against the base book and curve.

Usage: python scripts/run_scenarios.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rates_risk.book import build_book
from rates_risk.curve import TENORS, bootstrap
from rates_risk.scenarios import funding_shock_pnl, parallel_shift_pnl, total_dv01, twist_pnl


def main() -> None:
    par_rates = {t: 0.03 + 0.012 * (1.0 - math.exp(-t / 8.0)) for t in TENORS}
    curve = bootstrap(par_rates)
    book = build_book(par_rates)

    dv01 = total_dv01(book, curve)
    print(f"total book DV01 (1bp parallel, full reval): {dv01:.6f}")
    print()

    print("parallel shifts (full reval vs linear DV01 approximation):")
    for shift in (-100, -50, 50, 100):
        result = parallel_shift_pnl(book, curve, shift, dv01)
        print(f"  {shift:+d}bp: full_reval={result['full_reval']:.4f}  "
              f"linear_approx={result['linear_approx']:.4f}  "
              f"convexity_residual={result['convexity_residual']:.4f}")
    print()

    print("2s10s steepening twist (+/-25bp each leg):")
    for size in (25, -25):
        result = twist_pnl(book, curve, 2, 10, size)
        print(f"  {size:+d}bp: full_reval={result['full_reval']:.4f}")
    print()

    print("25bp funding shock (cash Treasury financing cost, 20-day assumed holding period):")
    for shock in (25, -25):
        pnl = funding_shock_pnl(book, shock)
        print(f"  {shock:+d}bp: pnl={pnl:.6f}")


if __name__ == "__main__":
    main()

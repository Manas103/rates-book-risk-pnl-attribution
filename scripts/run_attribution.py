#!/usr/bin/env python
"""Builds the base curve and the 40-position book, simulates 250 sessions
of market data, and runs the daily P&L attribution.

Usage: python scripts/run_attribution.py
"""
from __future__ import annotations

import math
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rates_risk.attribution import daily_attribution, summarize
from rates_risk.book import build_book
from rates_risk.curve import TENORS, bootstrap
from rates_risk.market_sim import NUM_SESSIONS, SEED, simulate


def main() -> None:
    print(f"platform: {platform.platform()}")
    print(f"python: {sys.version.splitlines()[0]}")
    print(f"curve tenors: {TENORS}")

    par_rates = {t: 0.03 + 0.012 * (1.0 - math.exp(-t / 8.0)) for t in TENORS}
    curve = bootstrap(par_rates)
    book = build_book(par_rates)
    print(f"book size: {len(book)} positions")

    sim = simulate(par_rates, book, num_sessions=NUM_SESSIONS, seed=SEED)
    print(f"simulated {NUM_SESSIONS} sessions (seed={SEED})")

    t0 = time.time()
    rows = daily_attribution(book, sim)
    elapsed = time.time() - t0
    summary = summarize(rows)

    print(f"attribution computed for {summary['num_sessions']} sessions in {elapsed:.2f}s")
    print(f"gross P&L (sum of |actual daily P&L|): {summary['gross_pnl']:.4f}")
    print(f"total curve component: {summary['total_curve']:.4f}")
    print(f"total carry component: {summary['total_carry']:.4f}")
    print(f"total spread component: {summary['total_spread']:.4f}")
    print(f"total residual: {summary['total_residual']:.4f}")
    print(f"total actual P&L: {summary['total_actual']:.4f}")
    print(f"gross residual (sum of |residual|): {summary['gross_residual']:.4f}")
    print(f"pct of gross P&L unexplained: {summary['pct_unexplained']:.4f}%")

    reconciled = max(abs(
        r["curve"] + r["carry"] + r["spread"] + r["residual"] - r["actual_pnl"]
    ) for r in rows)
    print(f"max |((curve+carry+spread+residual) - actual)| across all {len(rows)} sessions: {reconciled:.2e}")


if __name__ == "__main__":
    main()

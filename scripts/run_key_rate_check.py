#!/usr/bin/env python
"""Computes the book's total (parallel) DV01 and its 6 key-rate DV01s by
full revaluation, and reports how closely the key-rate DV01s sum back to
the parallel DV01.

Usage: python scripts/run_key_rate_check.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rates_risk.book import build_book
from rates_risk.curve import TENORS, bootstrap
from rates_risk.key_rate import KEY_RATE_NODES
from rates_risk.scenarios import key_rate_dv01s, total_dv01


def main() -> None:
    par_rates = {t: 0.03 + 0.012 * (1.0 - math.exp(-t / 8.0)) for t in TENORS}
    curve = bootstrap(par_rates)
    book = build_book(par_rates)

    total = total_dv01(book, curve)
    kr = key_rate_dv01s(book, curve)

    print(f"key-rate nodes: {KEY_RATE_NODES}")
    for node in KEY_RATE_NODES:
        print(f"  KR DV01 at {node}y: {kr[node]:.6f}")

    kr_sum = sum(kr.values())
    pct_diff = abs(kr_sum - total) / abs(total) * 100.0
    print(f"sum of key-rate DV01s: {kr_sum:.6f}")
    print(f"total (parallel) DV01: {total:.6f}")
    print(f"pct difference: {pct_diff:.4f}% (target: within 0.3%)")


if __name__ == "__main__":
    main()

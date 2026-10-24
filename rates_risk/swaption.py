"""Black-76 payer swaption on the forward par swap rate, priced directly
off `curve.py`'s own PVBP (no separate annuity model). stdlib only
(`math.erf` for the normal CDF, no scipy dependency)."""
from __future__ import annotations

import math


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def payer_swaption_price(forward_rate: float, strike: float, vol: float, expiry_years: float, pvbp: float,
                          notional: float = 100.0) -> float:
    """Black-76 payer swaption value: notional * PVBP * (F*N(d1) - K*N(d2))."""
    if expiry_years <= 0 or vol <= 0:
        return notional * pvbp * max(forward_rate - strike, 0.0)
    sqrt_t = math.sqrt(expiry_years)
    d1 = (math.log(forward_rate / strike) + 0.5 * vol * vol * expiry_years) / (vol * sqrt_t)
    d2 = d1 - vol * sqrt_t
    return notional * pvbp * (forward_rate * _norm_cdf(d1) - strike * _norm_cdf(d2))

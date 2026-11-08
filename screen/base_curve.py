"""The base (session-0) par rates, the same closed-form curve shape every
script in `rates_risk/` starts its own simulation from."""

from __future__ import annotations

import math

from rates_risk.curve import TENORS

BASE_PAR_RATES = {t: 0.03 + 0.012 * (1.0 - math.exp(-t / 8.0)) for t in TENORS}

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from rates_risk.book import build_book
from rates_risk.curve import TENORS, bootstrap


@pytest.fixture
def base_par_rates():
    return {t: 0.03 + 0.012 * (1.0 - math.exp(-t / 8.0)) for t in TENORS}


@pytest.fixture
def base_curve(base_par_rates):
    return bootstrap(base_par_rates)


@pytest.fixture
def book(base_par_rates):
    return build_book(base_par_rates)

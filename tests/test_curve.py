import pytest

from rates_risk.curve import TENORS, bootstrap


def test_flat_curve_matches_closed_form_discounting():
    r = 0.04
    curve = bootstrap({t: r for t in TENORS})
    for t in range(0, max(TENORS) + 1):
        assert curve.df(t) == pytest.approx((1.0 + r) ** -t, abs=1e-10)


def test_every_input_reprices_within_tolerance(base_par_rates, base_curve):
    for t in TENORS:
        err_bp = abs(base_curve.implied_par_rate(t) - base_par_rates[t]) * 10000.0
        assert err_bp < 0.02


def test_rejects_wrong_tenor_set():
    with pytest.raises(ValueError):
        bootstrap({1: 0.04, 2: 0.041})


def test_discount_factors_decrease_monotonically(base_curve):
    years = sorted(base_curve.discount_factors)
    for a, b in zip(years, years[1:]):
        assert base_curve.df(b) < base_curve.df(a)


def test_fractional_tenor_interpolates_between_integer_years(base_curve):
    mid = base_curve.df(5.5)
    assert base_curve.df(6) < mid < base_curve.df(5)


def test_pvbp_continuous_matches_pvbp_at_integer_tenor(base_curve):
    assert base_curve.pvbp_continuous(10) == pytest.approx(base_curve.pvbp(10), abs=1e-12)

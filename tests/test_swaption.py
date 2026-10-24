import pytest

from rates_risk.swaption import payer_swaption_price


def test_atm_payer_swaption_has_positive_time_value():
    price = payer_swaption_price(forward_rate=0.05, strike=0.05, vol=0.20, expiry_years=1.0, pvbp=8.0)
    assert price > 0


def test_price_increases_with_volatility():
    low_vol = payer_swaption_price(0.05, 0.05, 0.10, 1.0, 8.0)
    high_vol = payer_swaption_price(0.05, 0.05, 0.30, 1.0, 8.0)
    assert high_vol > low_vol


def test_deep_in_the_money_converges_to_intrinsic():
    price = payer_swaption_price(forward_rate=0.10, strike=0.02, vol=0.001, expiry_years=0.5, pvbp=8.0)
    intrinsic = 100.0 * 8.0 * (0.10 - 0.02)
    assert price == pytest.approx(intrinsic, rel=1e-3)


def test_zero_expiry_is_pure_intrinsic():
    price = payer_swaption_price(forward_rate=0.06, strike=0.05, vol=0.20, expiry_years=0.0, pvbp=8.0)
    assert price == pytest.approx(100.0 * 8.0 * 0.01, abs=1e-9)

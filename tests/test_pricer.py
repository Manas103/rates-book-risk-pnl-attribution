import pytest

from rates_risk.book import CashTreasury
from rates_risk.pricer import price_cash_treasury, price_position, total_pv


def test_par_bond_with_zero_spread_prices_to_par(base_curve, base_par_rates):
    pos = CashTreasury(999, 10.0, 100.0, base_par_rates[10], 0.0)
    price = price_cash_treasury(pos, base_curve, effective_tenor=10.0, spread_bp=0.0)
    assert price == pytest.approx(100.0, abs=1e-6)


def test_matured_treasury_prices_to_face(base_curve):
    pos = CashTreasury(998, 2.0, 50.0, 0.04, 1.0)
    price = price_position(pos, base_curve, t_years=2.0)
    assert price == pytest.approx(50.0, abs=1e-9)


def test_total_pv_is_the_sum_of_every_position(book, base_curve):
    from rates_risk.pricer import reval_book

    per_position = reval_book(book, base_curve)
    assert total_pv(book, base_curve) == pytest.approx(sum(per_position.values()), abs=1e-9)


def test_higher_spread_lowers_a_positive_notional_treasurys_price(base_curve, base_par_rates):
    pos_low = CashTreasury(1, 10.0, 100.0, base_par_rates[10], 0.0)
    pos_high = CashTreasury(1, 10.0, 100.0, base_par_rates[10], 50.0)
    price_low = price_position(pos_low, base_curve, t_years=0.0)
    price_high = price_position(pos_high, base_curve, t_years=0.0)
    assert price_high < price_low

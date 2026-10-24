import pytest

from rates_risk.scenarios import (
    funding_shock_pnl,
    key_rate_dv01s,
    parallel_shift_pnl,
    total_dv01,
    twist_pnl,
)


def test_key_rate_dv01s_sum_within_point_three_percent_of_total(book, base_curve):
    total = total_dv01(book, base_curve)
    kr = key_rate_dv01s(book, base_curve)
    pct_diff = abs(sum(kr.values()) - total) / abs(total) * 100.0
    assert pct_diff < 0.3


def test_parallel_shift_full_reval_and_linear_agree_in_direction(book, base_curve):
    dv01 = total_dv01(book, base_curve)
    result = parallel_shift_pnl(book, base_curve, 50.0, dv01)
    assert (result["full_reval"] > 0) == (result["linear_approx"] > 0)


def test_opposite_shifts_have_opposite_sign_pnl(book, base_curve):
    dv01 = total_dv01(book, base_curve)
    up = parallel_shift_pnl(book, base_curve, 50.0, dv01)
    down = parallel_shift_pnl(book, base_curve, -50.0, dv01)
    assert up["full_reval"] * down["full_reval"] <= 0


def test_twist_pnl_runs_and_returns_a_float(book, base_curve):
    result = twist_pnl(book, base_curve, 2, 10, 25.0)
    assert isinstance(result["full_reval"], float)


def test_funding_shock_scales_linearly_with_shock_size(book):
    small = funding_shock_pnl(book, 25.0)
    large = funding_shock_pnl(book, 50.0)
    assert large == pytest.approx(2.0 * small, rel=1e-9)


def test_funding_shock_is_nonzero_for_a_nonzero_net_cash_book(book):
    assert funding_shock_pnl(book, 25.0) != 0.0

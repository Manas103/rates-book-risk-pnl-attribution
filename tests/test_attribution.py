import pytest

from rates_risk.attribution import daily_attribution, summarize
from rates_risk.market_sim import simulate


@pytest.fixture
def attribution_rows(base_par_rates, book):
    sim = simulate(base_par_rates, book, num_sessions=60, seed=3)
    return daily_attribution(book, sim)


def test_every_session_after_the_first_has_a_row(attribution_rows):
    assert len(attribution_rows) == 59


def test_components_sum_to_actual_pnl_plus_residual(attribution_rows):
    for row in attribution_rows:
        reconstructed = row["curve"] + row["carry"] + row["spread"] + row["residual"]
        assert reconstructed == pytest.approx(row["actual_pnl"], abs=1e-9)


def test_summary_pct_unexplained_is_between_zero_and_a_hundred(attribution_rows):
    summary = summarize(attribution_rows)
    assert 0.0 <= summary["pct_unexplained"] <= 100.0


def test_summary_totals_match_the_row_sums(attribution_rows):
    summary = summarize(attribution_rows)
    assert summary["total_curve"] == pytest.approx(sum(r["curve"] for r in attribution_rows), abs=1e-9)
    assert summary["total_actual"] == pytest.approx(sum(r["actual_pnl"] for r in attribution_rows), abs=1e-9)

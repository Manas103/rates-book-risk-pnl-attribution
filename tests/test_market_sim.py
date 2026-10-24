from rates_risk.curve import TENORS
from rates_risk.market_sim import par_rates_on, simulate, spreads_on


def test_simulation_is_reproducible_given_the_same_seed(base_par_rates, book):
    sim_a = simulate(base_par_rates, book, num_sessions=30, seed=11)
    sim_b = simulate(base_par_rates, book, num_sessions=30, seed=11)
    assert sim_a["par_rate_paths"] == sim_b["par_rate_paths"]
    assert sim_a["funding_path"] == sim_b["funding_path"]


def test_every_tenor_has_a_full_path(base_par_rates, book):
    sim = simulate(base_par_rates, book, num_sessions=20)
    for t in TENORS:
        assert len(sim["par_rate_paths"][t]) == 20


def test_par_rates_on_returns_every_tenor(base_par_rates, book):
    sim = simulate(base_par_rates, book, num_sessions=20)
    rates = par_rates_on(sim, 5)
    assert set(rates.keys()) == set(TENORS)


def test_spreads_on_covers_every_non_swaption_position(base_par_rates, book):
    from rates_risk.book import Swaption

    sim = simulate(base_par_rates, book, num_sessions=20)
    spreads = spreads_on(sim, 5)
    expected_ids = {p.position_id for p in book if not isinstance(p, Swaption)}
    assert set(spreads.keys()) == expected_ids


def test_funding_and_vol_stay_within_their_bounds(base_par_rates, book):
    sim = simulate(base_par_rates, book, num_sessions=250)
    assert all(0.02 <= f <= 0.08 for f in sim["funding_path"])
    assert all(0.08 <= v <= 0.40 for v in sim["vol_path"])

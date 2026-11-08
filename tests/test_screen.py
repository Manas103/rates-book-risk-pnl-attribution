import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rates_risk.curve import bootstrap

from screen import base_curve, config, legs, measurements, metrics, oracle, screen


def test_instrument_families_all_present():
    result = measurements.measure_instrument_families()
    assert result["all_four_present"]
    assert set(result["families_priced_off_one_curve"]) == {
        "cash_treasury", "future", "swap", "forward_starting_swap",
    }


def test_simulated_sessions_count():
    sim = metrics.simulate_curve_paths()
    assert len(sim["par_rate_paths"][2]) == config.N_SESSIONS == 500


def test_slope_and_fly_series_are_linear_combinations_of_par_rates():
    sim = metrics.simulate_curve_paths()
    slope = metrics.slope_series(sim, "2s10s")
    assert len(slope) == config.N_SESSIONS
    for i in range(0, config.N_SESSIONS, 97):
        assert abs(slope[i] - (sim["par_rate_paths"][10][i] - sim["par_rate_paths"][2][i])) < 1e-15


def test_dv01_neutral_sizing_within_tolerance_and_matches_oracle():
    curve = bootstrap(base_curve.BASE_PAR_RATES)
    leg_pair = legs.build_slope_legs("2s10s", curve)
    notionals = legs.size_two_leg_dv01_neutral(leg_pair)
    net = legs.net_dv01(list(leg_pair), notionals)
    assert abs(net) < 1e-6
    oracle_net = oracle.basket_net_dv01_oracle(list(leg_pair), notionals, curve)
    assert abs(net - oracle_net) < 1e-3


def test_fly_dv01_neutral_sizing():
    curve = bootstrap(base_curve.BASE_PAR_RATES)
    leg_triple = legs.build_fly_legs("2s5s10s", curve)
    notionals = legs.size_fly_dv01_neutral(leg_triple)
    net = legs.net_dv01(list(leg_triple), notionals)
    assert abs(net) < 1e-6


def test_forward_starting_swap_reduces_to_spot_swap_after_its_start_date():
    from rates_risk.book import Swap
    from rates_risk.pricer import price_position

    from screen.forward_swap import ForwardStartingSwap, price_forward_starting_swap

    curve = bootstrap(base_curve.BASE_PAR_RATES)
    fss = ForwardStartingSwap(position_id=-1, start_years=1.0, tenor_years=5.0, notional=10.0, fixed_rate=0.04)
    # at t_years == start_years, remaining_to_start == 0, so it should price
    # identically to a spot 5y swap with the same fixed rate.
    spot_equivalent = Swap(position_id=-1, tenor=5.0, notional=10.0, fixed_rate=0.04, spread_bp=0.0)
    fss_price = price_forward_starting_swap(fss, curve, t_years=1.0)
    spot_price = price_position(spot_equivalent, curve, t_years=0.0)
    assert abs(fss_price - spot_price) < 1e-9


def test_rolling_zscore_has_no_lookahead():
    series = [float(i % 7) for i in range(50)]
    z = screen.rolling_zscores(series, window=10)
    # perturbing a future value must not change an earlier z-score
    series2 = list(series)
    series2[40] = 999.0
    z2 = screen.rolling_zscores(series2, window=10)
    assert z[:40] == z2[:40]


def test_screen_runs_and_dv01_check_passes():
    result = screen.run_screen()
    assert result["n_candidates"] > 0
    assert result["dv01_neutral_check"]["meets_tolerance"]


def test_swap_spread_simulation_is_stationary_not_a_random_walk():
    paths = metrics.simulate_swap_spreads(num_sessions=400)
    for tenor, path in paths.items():
        basis = config.SWAP_SPREAD_BASIS_BP[tenor]
        first_half_mean = sum(path[:200]) / 200
        second_half_mean = sum(path[200:]) / 200
        # a true random walk would typically wander far from its own start;
        # a mean-reverting series stays within a few bp of its declared basis
        assert abs(first_half_mean - basis) < 10.0
        assert abs(second_half_mean - basis) < 10.0

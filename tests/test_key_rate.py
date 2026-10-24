import pytest

from rates_risk.curve import TENORS
from rates_risk.key_rate import KEY_RATE_NODES, triangular_weight, parallel_weight


def test_triangular_weights_sum_to_one_at_every_curve_tenor():
    for t in TENORS:
        total = sum(triangular_weight(n)(t) for n in KEY_RATE_NODES)
        assert total == pytest.approx(1.0, abs=1e-12)


def test_weight_is_one_at_its_own_node():
    for n in KEY_RATE_NODES:
        assert triangular_weight(n)(n) == 1.0


def test_weight_is_zero_at_the_next_node_over():
    nodes = sorted(KEY_RATE_NODES)
    for i, n in enumerate(nodes[:-1]):
        assert triangular_weight(n)(nodes[i + 1]) == 0.0


def test_parallel_weight_is_always_one():
    for t in [0.5, 1, 7, 29.9, 30]:
        assert parallel_weight(t) == 1.0

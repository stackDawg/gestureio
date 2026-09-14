import numpy as np
import pytest

from gestureio.coordinator.features import angle_delta_deg
from gestureio.coordinator.filters import OneEuroFilter


@pytest.mark.parametrize("a, b, expected", [
    (-170.0, 170.0, 20.0),
    (170.0, -170.0, -20.0),
    (10.0, -10.0, 20.0),
    (180.0, -180.0, 0.0),
    (0.0, 180.0, 180.0),
])
def test_angle_delta_wraps(a, b, expected):
    assert angle_delta_deg(a, b) == pytest.approx(expected)


def test_accumulating_across_the_boundary_does_not_jump():
    # A knob turned from 170 deg through +/-180 to -170 deg is +20 deg, not -340.
    angles = [((170.0 + step + 180.0) % 360.0) - 180.0 for step in range(0, 21, 2)]
    total = sum(angle_delta_deg(cur, prev) for prev, cur in zip(angles, angles[1:]))
    assert total == pytest.approx(20.0)
    assert max(abs(angle_delta_deg(c, p)) for p, c in zip(angles, angles[1:])) <= 2.0 + 1e-9


def test_one_euro_passes_first_sample_and_converges():
    f = OneEuroFilter(min_cutoff=1.0, beta=0.0)
    assert f(5.0, 0.0) == 5.0
    y = 5.0
    for i in range(1, 300):
        y = f(10.0, i / 30)
    assert y == pytest.approx(10.0, abs=1e-3)


def test_one_euro_beta_reduces_lag_on_fast_motion():
    slow, fast = OneEuroFilter(1.0, beta=0.0), OneEuroFilter(1.0, beta=1.0)
    for f in (slow, fast):
        f(0.0, 0.0)
    ys, yf = slow(10.0, 1 / 30), fast(10.0, 1 / 30)
    assert yf > ys


def test_one_euro_handles_arrays_and_repeated_timestamps():
    f = OneEuroFilter()
    first = f(np.array([1.0, 2.0]), 0.0)
    again = f(np.array([9.0, 9.0]), 0.0)
    assert np.allclose(first, again)

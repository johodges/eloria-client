"""The Amberwood approaches: routed branches graded as authored earth surfaces."""
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import amberwood_support as A


class Roads:
    def __init__(self, roads):
        self.roads = roads


def test_the_ridge_camp_branch_is_an_approach_taken_from_its_routed_road():
    world = Roads([{'id': 'discovery-amberwood-473', 'points': [[556., 83., 472.], [576., 92., 480.], [605., 107., 457.]]}])
    routes = A.branch_routes(world)
    assert list(routes) == ['amber-ridge-camp-branch']
    np.testing.assert_array_equal(routes['amber-ridge-camp-branch'], [[556., 472.], [576., 480.], [605., 457.]])
    with pytest.raises(ValueError, match='was not routed'):
        A.branch_routes(Roads([]))


def test_a_branch_profile_keeps_its_ends_and_cuts_the_feather_step_to_the_grade():
    stations = np.array([0., 10., 20., 30., 40., 50.])
    levels = np.array([80., 84., 88., 97., 100., 102.])   # a 9 m step over 10 m: the plateau's footing feather
    profile = A.branch_profile(levels, stations)
    assert profile[0] == 80. and profile[-1] == 102.
    assert np.max(np.abs(np.diff(profile)) / np.diff(stations)) <= A.APPROACH_GRADE + 1e-9
    assert profile[3] < 97.   # the step is cut, not left for the served fold to block

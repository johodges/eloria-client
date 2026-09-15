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
    world.roads.append({'id': 'discovery-amberwood-481', 'points': [[644., 101., 496.], [603., 102., 493.]]})
    routes = A.branch_routes(world)
    assert list(routes) == ['amber-ridge-camp-branch', 'amber-undercut-branch']
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


def test_other_roads_are_measured_by_centreline_distance_except_the_excluded_ones():
    world = Roads([{'id': 'street', 'points': [[0., 0., 0.], [40., 0., 0.]]},
                   {'id': 'discovery-amberwood-473', 'points': [[0., 0., 10.], [40., 0., 10.]]},
                   {'id': 'far-away', 'points': [[500., 0., 500.], [540., 0., 500.]]}])
    x, z = np.meshgrid(np.arange(0., 41., 2.), np.arange(0., 21., 2.))
    distance = A.other_road_distance(world, {'amber-ridge-camp-branch', 'discovery-amberwood-473'}, x, z)
    np.testing.assert_allclose(distance, z)   # the street along z = 0 is the only other road in reach
    assert np.isinf(A.other_road_distance(Roads([]), set(), x, z)).all()


def test_the_village_yard_approach_runs_from_the_west_ground_to_the_root_ramp_foot():
    from amberwood_access import ROOT_RAMP_FOOT
    world = Roads([]); world.regions = {'amberwood': {'center': [510., 540.]}}
    routes = A.authored_routes(world)
    path = routes['amber-yard-approach']
    assert path[0][0] < ROOT_RAMP_FOOT[0] - 15   # starts well west of the ramp foot, on the open ground
    np.testing.assert_allclose(path[-1], ROOT_RAMP_FOOT + [0., 1.], atol=1.5)   # ends at the ramp's foot
    assert np.all(path[:, 1] < 479.)   # south of Canopy Platform 2 (z 479..495)


def test_the_chapel_bank_approach_climbs_from_the_hub_side_ground_to_the_plateau_edge():
    world = Roads([]); world.regions = {'amberwood': {'center': [510., 540.]}}
    path = A.authored_routes(world)['amber-chapel-bank']
    assert path[0][1] > 517. and path[-1][1] < 506.   # from below the bank (z > 517) up to the plateau edge
    length = np.sum(np.linalg.norm(np.diff(path, axis=0), axis=1))
    assert 8. / length < A.APPROACH_GRADE   # 8 m of rise within the corridor grade


def test_a_branch_is_regraded_along_its_steep_runs_only():
    stations = np.array([0., 10., 20., 30., 40., 50.])
    levels = np.array([80., 84., 88., 97., 100., 102.])   # one steep segment (.9) between 20 and 30 m
    profile, runs = A.branch_runs(levels, stations)
    assert profile[0] == 80. and profile[-1] == 102.
    assert np.max(np.abs(np.diff(profile)) / np.diff(stations)) <= A.APPROACH_GRADE + 1e-9
    assert profile[3] < 97.
    assert runs == [[0., 50.]]   # padded by 6 m, then widened until its ends' rise fits the grade
    gentle = np.array([80., 82., 84., 86.])
    profile, runs = A.branch_runs(gentle, stations[:4])
    np.testing.assert_array_equal(profile, gentle); assert runs == []
    need = A.branch_need(np.array([-5., 0., 25., 50., 51.5, 53., 60.]), [[0., 50.]])
    np.testing.assert_allclose(need, [0., 1., 1., 1., .5, 0., 0.])

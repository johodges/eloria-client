"""Bank contact, real mooring water and physical emitted ferry geometry."""
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / '_toolkit'))
import ferry_export as F
import glb_reader as GLB


class Shore:
    plan = {'sea_level': 0., 'rivers': [], 'lakes': []}
    # Deliberately unrelated to the shore direction: a centre-bearing heuristic
    # would send these ferries west into dry land instead of east onto water.
    regions = {name: {'center': [-1000, 0]} for name in ('a', 'b', 'c', 'island')}
    ids = list(regions)

    def __init__(self):
        self.connections = [dict(id=name+'--island', type='ferry', regions=[name, 'island'],
                                 landings=[[-12., 30.*i], [-12., 100.+i]])
                            for i, name in enumerate(('a', 'b', 'c'))]

    def height_at(self, x, z):
        return -.15 * np.asarray(x)


def test_fit_follows_actual_water_and_keeps_clear_access_and_grade():
    world = Shore()
    fit = F.fit_landing(world, [-12, 0], 'a')
    assert fit['forward'][0] > .8
    assert fit['maximumGrade'] <= .45
    assert fit['contactError'] <= .16
    footprint = F.boat_points(fit['boatCenter'], fit['forward'], fit['side'])
    _, water = F.samples(world, footprint)
    assert np.asarray(water['mask']).all() and np.min(water['depth']) >= .65
    # The complete hull stays outside the clear strip, including its widest end.
    across = (footprint - np.asarray(fit['landing'])) @ fit['side']
    assert np.min(abs(across)) > F.HALF_WIDTH + .8
    floor = dict(F.skiff_meshes(fit))['Floor']
    assert np.min(floor.positions[:, 1]) > fit['waterLevel'] + .04
    faces = floor.positions[floor.indices.reshape(-1, 3)]
    assert (np.cross(faces[:, 1]-faces[:, 0], faces[:, 2]-faces[:, 0])[:, 1] > 0).all()


def test_three_routes_share_a_single_nearby_island_quay():
    groups = F.landing_groups(Shore())
    assert len(groups) == 4
    island = next(group for group in groups if group['region'] == 'island')
    assert len(island['connections']) == 3


def test_no_actual_water_fails_before_creating_output(tmp_path):
    world = Shore()
    world.height_at = lambda x, z: np.full(np.broadcast_arrays(x, z)[0].shape, 5.)
    target = tmp_path / 'absent' / 'ferries.glb'
    with pytest.raises(ValueError, match='no suitable actual water'):
        F.build_ferries(world, target)
    assert not target.exists() and not target.parent.exists()


def test_unbuildable_cliff_is_reported_instead_of_a_floating_arrival():
    world = Shore()
    world.height_at = lambda x, z: np.where(np.asarray(x) < 0, 50., -2.)
    with pytest.raises(ValueError, match='cannot fit a <=.45 grade quay'):
        F.fit_landing(world, [-12, 0], 'a')


def test_water_centre_without_room_for_the_hull_is_not_a_mooring():
    world = Shore()
    def thin_water(x, z, height, plan):
        mask = (np.asarray(x) > 0) & (abs(np.asarray(z)) < .4)
        return dict(mask=mask, depth=np.where(mask, 2., 0.), surface=np.zeros_like(np.asarray(x)))
    with pytest.raises(ValueError, match='cannot fit a <=.45 grade quay'):
        F.fit_landing(world, [-12, 0], 'a', water_fields=thin_water)


def test_inland_pond_is_not_an_outer_ocean_ferry_destination():
    world = Shore()
    world.x = world.z = np.arange(-60., 62., 2.)
    x, z = np.meshgrid(world.x, world.z)
    world.height = np.where(x > 30, -2., 5.)
    world.height[(abs(x) < 10) & (abs(z) < 10)] = -3.
    ocean = F.ocean_membership(world)
    assert ocean([[40., 0.]]).tolist() == [True]
    assert ocean([[0., 0.], [28., 0.], [99., 0.]]).tolist() == [False, False, False]


def test_emitted_walk_floor_faces_up_piles_touch_bed_and_export_is_repeatable(tmp_path):
    world = Shore()
    before = repr(world.connections)
    first = tmp_path / 'first.glb'
    parts = F.build_ferries(world, first)
    doc, body = GLB.load(first)
    assert len(parts) == len(doc['nodes']) and all(set(('region', 'roots', 'bounds', 'node', 'segment')) <= set(part) for part in parts)
    walk = [index for index, node in enumerate(doc['nodes']) if node['name'].startswith('Walk_FerryQuay_')]
    assert len(walk) == 4
    triangles = GLB.triangles(doc, body, walk)
    normals = np.cross(triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0])
    assert (normals[:, 1] > 0).all()
    assert np.max(np.linalg.norm(normals[:, [0, 2]], axis=1) / normals[:, 1]) <= .45001
    for node in doc['nodes']:
        if node['name'].endswith('_MooringRopes'):
            quay = next(row for row in world.ferry_report['landings'] if node['name'].startswith(row['node'].removeprefix('Walk_')))
            primitive = doc['meshes'][node['mesh']]['primitives'][0]
            points = GLB.accessor(doc, body, primitive['attributes']['POSITION'])
            across = (points[:, [0, 2]] - np.asarray(quay['landing'])) @ np.asarray(quay['side'])
            assert np.min(abs(across)) > F.HALF_WIDTH
        if not node['name'].endswith('_PilesAndPosts'):
            continue
        primitive = doc['meshes'][node['mesh']]['primitives'][0]
        points = GLB.accessor(doc, body, primitive['attributes']['POSITION'])
        bottoms = {}
        for x, y, z in points:
            bottoms[(float(x), float(z))] = min(float(y), bottoms.get((float(x), float(z)), np.inf))
        for (x, z), y in bottoms.items():
            assert -.205 < y - float(world.height_at(x, z)) < -.155
    assert world.ferry_report['ferryEnds'] == 6 and world.ferry_report['uniqueQuays'] == 4
    assert repr(world.connections) == before
    second = tmp_path / 'second.glb'
    F.build_ferries(world, second)
    assert first.read_bytes() == second.read_bytes()

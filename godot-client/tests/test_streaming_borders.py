"""Receiving approaches are exact pieces of authored geometry, never whole-map cuts."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] /
                     'eloria-assets/maps/nymara-regions/_toolkit'))
from amberwood import mesh as M
from amberwood import terrain as T
from amberwood.stonework import MeshGroup
from regionbuild import Placement, RegionBuild
from verify_runtime import VerticalRayIndex
import streaming_borders as S


def square():
    return M.Mesh(positions=np.array([[-100., 2, -100], [100., 2, -100],
                                     [100., 2, 100], [-100., 2, 100]]),
                  normals=np.tile([0., 1, 0], (4, 1)),
                  uvs=np.array([[0., 0], [1., 0], [1., 1], [0., 1]]),
                  colors=np.ones((4, 4)), indices=np.array([0, 1, 2, 0, 2, 3]),
                  material='meadow_grass_ground')


def area(mesh):
    t = mesh.positions[mesh.indices.reshape(-1, 3)]
    return np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1).sum() / 2


@pytest.mark.parametrize('direction', [(0, 1), (1, 0), (0, -1), (-1, 0)])
def test_large_triangles_partition_without_holes_or_overlapping_area(direction):
    source = square()
    forward = np.array(direction, float)
    side = np.array([-forward[1], forward[0]])
    front, overflow = S.split_overflow(source, np.zeros(2), forward, side)
    assert area(front) + area(overflow) == pytest.approx(area(source))
    assert area(overflow) == pytest.approx(8000)
    for part in (front, overflow):
        assert part.material == source.material
        assert np.allclose(part.normals, [0, 1, 0])
        assert np.allclose(part.uvs, (part.positions[:, [0, 2]] + 100) / 200)


def test_receiving_view_is_bounded_and_keeps_original_surface_height():
    view = S.clip_rect(square(), np.zeros(2), np.array([0., 1]),
                       np.array([-1., 0]), -75, 0)
    assert area(view) == pytest.approx(6000)
    assert np.all(view.positions[:, 1] == 2)
    assert np.max(abs(view.positions[:, 0])) <= 40
    assert view.positions[:, 2].min() >= -75
    assert view.positions[:, 2].max() <= 0


def test_empty_overflow_keeps_its_material():
    front, overflow = S.split_overflow(square(), np.array([0., 200]),
                                       np.array([0., 1]), np.array([-1., 0]))
    assert not overflow.triangle_count
    assert front.material == overflow.material == square().material


def test_every_survey_is_reciprocal_and_has_one_independent_view():
    specs = [s for r in ('amberwood', 'whitehorn_range', 'grey_moors',
                        'mirrorhold', 'amethyst_barrens', 'westhaven',
                        'four_gates', 'crownwater') for s in S.region_specs(r)]
    assert len(specs) == 18
    for identity, *_ in S.LINKS:
        ends = [s for s in specs if s['id'] == identity]
        assert len(ends) == 2
        assert ends[0]['palette'] == ends[1]['palette']
        assert ends[0]['uvSign'] == -ends[1]['uvSign']
        assert ends[0]['previewPrefix'] == ends[1]['previewPrefix']
        assert ends[0]['overflowSuffix'].endswith(identity)


def test_replacing_water_preserves_area_without_overlapping_patches():
    source = square()
    edge, forward, side = np.zeros(2), np.array([0.,1]), np.array([-1.,0])
    patch = S.clip_rect(source,edge,forward,side,-42,80)
    remaining = S.outside_rect(source,edge,forward,side,-42,80)
    assert area(patch) == pytest.approx(122 * 80)
    assert area(patch) + area(remaining) == pytest.approx(area(source))


@pytest.mark.parametrize('region', ['crownwater','four_gates'])
def test_causeway_has_seven_clear_lanes_above_water_and_no_earth_plug(monkeypatch, region):
    spec = next(s for s in S.region_specs(region) if s['id']=='four-gates-crownwater')
    monkeypatch.setattr(S, 'region_specs', lambda region: [spec])
    x, level, z = spec['anchor']
    t = T.Terrain(x-100,z-100,200,200,2)
    t.height[:] = level + 12  # A bad legacy land platform must become a lake bed.
    build = RegionBuild(t)
    build.terrain_meshes = t.build_meshes()
    water = square(); water.positions[:,[0,2]] += [x,z]
    water.positions[:,1] = level-4
    build.water_meshes['Water_Lake'] = water
    S.apply(build,region)
    def rays(bucket, prefix):
        triangles=[m.positions[m.indices.reshape(-1,3)] for n,m in bucket.items()
                   if n.startswith(prefix) and not n.startswith(S.VIEW_PREFIX) and m.triangle_count]
        return VerticalRayIndex(np.concatenate(triangles))
    deck, bed, lake = rays(build.terrain_meshes,'Walk_'), rays(build.terrain_meshes,'Terrain_'), rays(build.water_meshes,'Water_')
    f=np.array(spec['outward']); side=np.array([-f[1],f[0]])
    for depth in (-10,-.001,.001,4):
        for lateral in range(-3,4):
            px,pz=np.array([x,z])+f*depth+side*lateral
            assert deck.top_hit(px,pz) == pytest.approx(level,abs=1e-5)
            assert lake.top_hit(px,pz) == pytest.approx(level-4,abs=1e-5)
            assert bed.top_hit(px,pz) == pytest.approx(level-6,abs=1e-5)
        for lateral in (-30,-10,10,30):
            px,pz=np.array([x,z])+f*depth+side*lateral
            assert deck.top_hit(px,pz) is None
            assert lake.top_hit(px,pz) == pytest.approx(level-4,abs=1e-5)
    assert any(n.startswith(spec['previewPrefix']+'Walk_') for n in build.terrain_meshes)


def test_pasture_crossing_remains_low_rolling_ground():
    spec=next(s for s in S.region_specs('westhaven') if s['id']=='grey-westhaven')
    x,level,z=spec['anchor']
    t=T.Terrain(x-100,z-100,200,200,2);t.height[:]=level
    b=RegionBuild(t);b.terrain_meshes=t.build_meshes()
    S._apply_one(b,spec,[spec])
    for lateral in (-39.9,0,39.9):
        assert level <= b.terrain.height_at(x+lateral,z) <= level+1.4


def _prop_view(monkeypatch, direction=(0, -1)):
    spec = dict(S.region_specs('grey_moors')[0], anchor=[0, 4, 0], outward=list(direction))
    monkeypatch.setattr(S, 'region_specs', lambda region: [spec])
    return RegionBuild(T.Terrain(-200, -200, 400, 400, 20)), spec


def _preview_nodes(build, spec):
    return {p.node.removeprefix(spec['previewPrefix']): p for p in build.placements
            if p.node.startswith(spec['previewPrefix'])}


@pytest.mark.parametrize('direction', [(0, 1), (1, 0), (0, -1), (-1, 0)])
def test_near_edge_boulder_is_previewed_as_the_same_whole_mesh(monkeypatch, direction):
    """Mirrorhold's boulder at depth -1.944 must already exist before adoption."""
    build, spec = _prop_view(monkeypatch, direction)
    forward = np.array(direction)
    side = np.array([-forward[1], forward[0]])
    x, z = -1.944 * forward + 10.608 * side
    mesh = M.box((4, 2, 4))
    before = mesh.positions.copy()
    build.meshes['boulder'] = mesh
    original = Placement('Near_edge_boulder', 'boulder', (x, 4, z),
                         collides=True, kind='rock', extras={'authored': True})
    build.place(original)
    S.apply(build, 'grey_moors')
    duplicate = _preview_nodes(build, spec)[original.node]
    assert duplicate is not original
    assert build.meshes[duplicate.mesh] is mesh
    assert duplicate.position == original.position
    assert duplicate.rotation_y == original.rotation_y
    assert duplicate.scale == original.scale
    assert not duplicate.collides and duplicate.extras is None
    assert original.collides and original.extras == {'authored': True}
    np.testing.assert_array_equal(mesh.positions, before)


@pytest.mark.parametrize('depth,lateral', [(-50, -44), (-50, 44), (-149, 15)])
def test_canopy_bounds_crossing_side_or_far_edge_are_previewed(monkeypatch, depth, lateral):
    """Include the full group even when only its canopy enters the receiving strip."""
    build, spec = _prop_view(monkeypatch)
    tree = MeshGroup().add(M.box((1, 8, 1)))
    tree.add_overhead(M.box((12, 4, 12), center=(0, 10, 0)))
    build.meshes['tree'] = tree
    build.place(Placement('Edge_canopy', 'tree', (lateral, 4, -depth), kind='tree'))
    S.apply(build, 'grey_moors')
    assert 'Edge_canopy' in _preview_nodes(build, spec)


def test_preview_bounds_apply_mesh_offset_yaw_and_placement_scale(monkeypatch):
    build, spec = _prop_view(monkeypatch)
    # Its pivot is 8m outside; the authored offset and transformed canopy reach
    # x=38..42. Ignoring offset, rotation, or scale would wrongly exclude it.
    mesh = M.box((1, 4, 2), center=(0, 10, 4))
    before = mesh.positions.copy()
    build.meshes['offset_canopy'] = mesh
    original = Placement('Rotated_canopy', 'offset_canopy', (48, 4, 50),
                         rotation_y=-np.pi / 2, scale=2)
    build.place(original)
    S.apply(build, 'grey_moors')
    duplicate = _preview_nodes(build, spec)[original.node]
    assert duplicate.mesh == original.mesh
    assert duplicate.rotation_y == original.rotation_y and duplicate.scale == original.scale
    np.testing.assert_array_equal(mesh.positions, before)


@pytest.mark.parametrize('position,mesh_offset', [
    ((0, 4, 150), (0, 0, 0)),  # Beyond the far edge.
    ((42, 4, 50), (0, 0, 0)),  # Beyond the lateral edge.
    ((0, 4, 50), (90, 0, 0)),  # Pivot inside, but every rendered part outside.
])
def test_preview_excludes_full_bounds_outside_receiving_strip(monkeypatch, position, mesh_offset):
    build, spec = _prop_view(monkeypatch)
    build.meshes['outside'] = M.box((2, 2, 2), center=mesh_offset)
    build.place(Placement('Outside', 'outside', position))
    S.apply(build, 'grey_moors')
    assert not _preview_nodes(build, spec)


def test_empty_or_missing_mesh_does_not_create_preview(monkeypatch):
    build, spec = _prop_view(monkeypatch)
    build.meshes['empty'] = MeshGroup()
    for mesh in ('empty', 'missing'):
        build.place(Placement(mesh, mesh, (15, 4, 20)))
    S.apply(build, 'grey_moors')
    assert not _preview_nodes(build, spec)


def test_linked_portal_return_spawn_and_secret_keep_authored_height_offsets(monkeypatch):
    build, spec = _prop_view(monkeypatch)
    build.terrain.height[:] = 20
    cave = Placement('Landmark_cave', 'unused', (15, 20, 10), kind='landmark')
    secret = Placement('Secret_ice_well', 'unused', (25, 19.95, 10))
    build.placements.extend([cave, secret])
    landmark = {'id': 'cave', 'node': cave.node, 'position': [15, 20.7, 10]}
    portal = {'id': 'cave-mouth', 'landmark': 'cave', 'position': [15, 21, 10]}
    spawn = {'id': 'cave-mouth', 'position': [15, 20.25, 10]}
    interactive = {'id': 'secret-ice-well', 'secret': 'ice-well', 'position': [25, 20.4, 10]}
    unrelated = {'id': 'unlinked', 'position': [15, 123, 10]}
    build.landmarks.append(landmark)
    build.portals.append(portal)
    build.spawns.append(spawn)
    # Reusing the portal record must not apply the same lift twice.
    build.interactives.extend([interactive, portal, unrelated])
    S._apply_one(build, spec, [spec])
    assert abs(cave.position[1] - 20) > 1
    assert abs(secret.position[1] - 19.95) > 1
    for record, offset in ((landmark, .7), (portal, 1), (spawn, .25)):
        assert record['position'][1] == pytest.approx(cave.position[1] + offset)
    assert interactive['position'][1] == pytest.approx(secret.position[1] + .45)
    assert unrelated['position'][1] == 123


def _northern_ground():
    """A small, sloping piece of Mirrorhold covering both neighbouring cols."""
    terrain = T.Terrain(-120.5, -290.5, 176, 58, 2)
    terrain.height = 70 + .04 * terrain.gx - .03 * terrain.gz
    build = RegionBuild(terrain)
    build.terrain_meshes = terrain.build_meshes()
    return build


def _ground_rays(build):
    # Paint layers are deliberately offset by centimetres; compare the actual
    # earth surface, including overflow, so alpha coverage cannot mask a crack.
    triangles = [mesh.positions[mesh.indices.reshape(-1, 3)]
                 for name, mesh in build.terrain_meshes.items()
                 if '_StreamCollar_' not in name and mesh.triangle_count]
    return VerticalRayIndex(np.concatenate(triangles))


@pytest.fixture(params=[False, True], ids=['whitehorn-first', 'amethyst-first'])
def overlapping_cols(request):
    specs = [spec for spec in S.region_specs('mirrorhold')
             if spec['outward'] == [0, -1]]
    assert len(specs) == 2
    if request.param:
        specs.reverse()
    combined = _northern_ground()
    isolated = {}
    for spec in specs:
        S._apply_one(combined, spec, specs)
        alone = _northern_ground()
        S._apply_one(alone, spec, [spec])
        isolated[spec['id']] = _ground_rays(alone)
    return specs, _ground_rays(combined), isolated


def test_overlapping_cols_keep_both_full_seam_shoulders(overlapping_cols):
    """A second road must not lift the first road away from its reciprocal bank."""
    specs, combined, isolated = overlapping_cols
    for spec in specs:
        for lateral in [-39.9, -35, -30, -25, 0, 25, 30, 35, 39.9]:
            x, z = spec['anchor'][0] + lateral, spec['anchor'][2] + .02
            expected = isolated[spec['id']].top_hit(x, z)
            actual = combined.top_hit(x, z)
            assert expected is not None and actual is not None
            assert actual == pytest.approx(expected, abs=.075), (
                f"{spec['id']} shoulder {lateral}m changed by {actual - expected:.3f}m")


def test_overlapping_cols_keep_overflow_flanks_continuous(overlapping_cols):
    """Splitting one road's overflow must not leave a cliff after its peer grades."""
    specs, combined, _ = overlapping_cols
    for spec in specs:
        for side in [-1, 1]:
            edge = spec['anchor'][0] + side * S.HALF_WIDTH
            for depth in [.5, 1.5, 5]:
                z = spec['anchor'][2] - depth
                left, right = combined.top_hit(edge - .001, z), combined.top_hit(edge + .001, z)
                assert left is not None and right is not None, (spec['id'], edge, z)
                assert abs(left - right) < .02, (
                    f"{spec['id']} overflow flank ({edge}, {z}) jumps {abs(left - right):.3f}m")

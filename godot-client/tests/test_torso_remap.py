"""The source-pose torso path keeps artwork and skinning consistent."""
from io import BytesIO
from pathlib import Path
import sys

import numpy as np
from PIL import Image
import pytest

TOOLS = Path(__file__).resolve().parents[2] / 'eloria-assets/tools'
sys.path.insert(0, str(TOOLS))
import conform_equipment as ce
import equipment_authoring as ea
import torso_remap as remap
import garment_coverage as coverage


@pytest.fixture(scope='module')
def rig():
    return ea.load_rig(ce.RACES / 'luminous_male.glb', ce.BODY_MESH)


def test_limb_rotation_preserves_lengths_and_handedness():
    source = np.array([.14, -.70, .06])
    target = np.array([.494, 0., -.001])
    rotation = remap.rotation_between(source, target)
    np.testing.assert_allclose(rotation.T @ rotation, np.eye(3), atol=1e-12)
    assert np.linalg.det(rotation) == pytest.approx(1.)
    np.testing.assert_allclose(rotation @ (source / np.linalg.norm(source)),
                               target / np.linalg.norm(target), atol=1e-12)


def test_uv_split_positions_receive_identical_mapping_and_weights(rig):
    # A closed little sleeve island, split at every texture seam, plus torso
    # landmarks. Changing UV topology must never shear coincident positions.
    p = np.array([[.30, -.10, .02], [.34, -.10, .02],
                  [.32, -.15, .02], [.32, -.12, .06],
                  [0., -.5, 0.], [0., .5, 0.]])
    faces = np.array([[0, 2, 1], [0, 1, 3], [1, 2, 3], [2, 0, 3]])
    expanded = np.vstack((p[faces.ravel()], p[4:]))
    tris = np.arange(12).reshape(-1, 3)
    mapped, joints, weights, keep, _ = remap.remap(expanded, tris, rig)
    for original in range(4):
        copies = np.flatnonzero(faces.ravel() == original)
        np.testing.assert_allclose(mapped[copies], np.tile(mapped[copies[0]], (len(copies), 1)))
        np.testing.assert_array_equal(joints[copies], np.tile(joints[copies[0]], (len(copies), 1)))
        np.testing.assert_allclose(weights[copies], np.tile(weights[copies[0]], (len(copies), 1)))
    assert keep.all()
    np.testing.assert_allclose(weights.sum(axis=1), 1.)


def test_shallow_contact_shell_cannot_throw_the_backplate_outward(rig):
    p = np.array([[x, y, z] for x in [-.18, .18]
                  for y in [1.04, 1.52] for z in [-.10, .05]])
    faces = np.array([[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5],
                      [0, 4, 5], [0, 5, 1], [2, 3, 7], [2, 7, 6],
                      [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]])
    before = p.copy()
    remap._clear_trunk(p, faces, rig, np.ones(len(p)), np.zeros(len(p), dtype=int))
    # The old median-depth rule sent these shallow shoulder contacts far
    # behind the body. A shirt opening must not become a dorsal fin.
    assert np.max(np.linalg.norm(p - before, axis=1)) < .07
    assert np.ptp(p[:, 2]) > np.ptp(before[:, 2])  # still fits, rather than skipping the cage


def test_raised_collar_keeps_shoulder_and_small_ornaments_rigid(rig):
    box_faces = np.array([[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5],
                          [0, 4, 5], [0, 5, 1], [2, 3, 7], [2, 7, 6],
                          [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]])
    collar = np.array([[x, y, z] for x in [-.08, .08]
                       for y in [.10, .50] for z in [-.04, .04]])
    ornament = np.array([[x, y, z] for x in [-.02, .02]
                         for y in [.42, .44] for z in [.045, .055]])
    shoulder = np.array([[x, y, z] for x in [.23, .35]
                         for y in [.25, .37] for z in [-.05, .05]])
    p = np.vstack((collar, ornament, shoulder, [[0., -.50, 0.]]))
    faces = np.vstack([box_faces + offset for offset in [0, 8, 16]])
    before, _, _, _, _ = remap.remap(p, faces, rig)
    after, joints, weights, _, report = remap.remap(p, faces, rig, collar_lift=.045)
    np.testing.assert_allclose(after[16:], before[16:])
    assert set(joints[16:24, 0]) == {rig.joint_names.index('clavicle_l')}
    np.testing.assert_allclose(weights[16:24, 0], 1.)
    np.testing.assert_allclose(after[8:16] - after[8], before[8:16] - before[8])
    assert after[8, 1] > before[8, 1] + .02
    assert after[:8, 1].max() - before[:8, 1].max() == pytest.approx(.045 * rig.fit_scale)
    np.testing.assert_allclose(after[:, [0, 2]], before[:, [0, 2]])
    assert next(p for p in report['passes'] if p['name'] == 'raised_collar')['movedVertices'] > 0


def test_original_glb_bypasses_legacy_fitting_and_keeps_image_encoding(tmp_path, rig, monkeypatch):
    source = tmp_path / 'piece.glb'
    original = tmp_path / 'piece.glb.orig'
    source.write_bytes(b'processed file must not be read')
    points = np.array([[-.2, -.5, -.1], [.2, -.5, -.1], [0., .5, -.1], [0., 0., .2]])
    faces = np.array([[0, 2, 1], [0, 1, 3], [1, 2, 3], [2, 0, 3]])
    image = BytesIO()
    Image.new('RGB', (4, 4), (65, 52, 31)).save(image, format='JPEG')
    glb = ea.EquipmentGLB()
    material = ce.textured_material(glb, 'Original', image.getvalue(), double_sided=True)
    glb.doc['images'][0]['mimeType'] = 'image/jpeg'
    glb.mesh('Original', [glb.primitive(points, np.ones_like(points),
        np.zeros((len(points), 2)), faces.ravel(), material)])
    glb.write(original)
    def legacy(*args, **kwargs):
        pytest.fail('torso entered the legacy conversion')
    monkeypatch.setattr(ce, 'seat', legacy)
    monkeypatch.setattr(ce, 'repose', legacy)
    out = tmp_path / 'fitted.glb'
    report = ce.build(source, out, rig, 'cuirass', 'Fixture')
    doc, binary = ea.read_glb(out)
    assert report['source'] == original.name
    assert doc['images'][0]['mimeType'] == 'image/jpeg'
    view = doc['bufferViews'][doc['images'][0]['bufferView']]
    offset = view.get('byteOffset', 0)
    assert binary[offset:offset + view['byteLength']] == image.getvalue()
    assert doc['materials'][0]['doubleSided']
    assert any(m['name'] == 'GeneratedArmorBacking' for m in doc['meshes'])
    primitives, _, _ = coverage.load(str(out))
    shells = coverage.components(primitives[1].points, primitives[1].triangles)
    assert shells and all(s.closed and s.volume > 0 for s in shells)
    np.testing.assert_allclose(primitives[1].weights.sum(axis=1), 1., atol=1e-6)


@pytest.mark.parametrize('width', [.220, .244])
def test_source_boundary_preserves_each_drawings_trunk_width(width):
    # Independent side walls with the same overall source height. The wider
    # wrap must retain its chest rather than receive the narrow coat's cut.
    points = np.array([[x, y, z] for x in [-width, width]
                       for y in [-.3, .3] for z in [-.10, .10]])
    faces = np.array([[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5]])
    points = np.vstack([points, [0., -.5, 0.], [0., .5, 0.]])
    boundaries = remap.source_seam_boundaries(points, faces)
    for side in ['l', 'r']:
        assert boundaries[side]['fraction'] == pytest.approx(width)


def test_chest_coverage_does_not_count_the_bridges_removed_from_sleeves(monkeypatch):
    from types import SimpleNamespace
    body = np.array([[-.2, 1.2, 0.], [.2, 1.2, 0.], [.2, 1.4, 0.], [-.2, 1.4, 0.]])
    faces = np.array([[0, 1, 2], [0, 2, 3]])
    fake_rig = SimpleNamespace(positions=body, faces=faces, fit_scale=1.,
                              origin=lambda _: np.array([0., 1.28, 0.]))
    bridge = body + [0., 0., .03]
    narrow = body * [0.25, 1., 1.] + [0., 0., .02]
    points = np.vstack([bridge, narrow])
    faces = np.vstack([faces, faces + 4])
    influence = np.r_[np.zeros(4), np.ones(4)]
    solved = []
    monkeypatch.setattr(remap, '_bounded_trunk', lambda *args: None)
    monkeypatch.setattr(remap, '_paired_trunk', lambda *args: solved.append(True))
    remap._clear_trunk(points, faces, fake_rig, influence, np.zeros(8, dtype=int))
    assert solved == [True]


def test_cut_debris_is_removed_without_deleting_original_floating_ornaments():
    points = np.array([[x*.01, y*.01, 0.] for y in range(9) for x in range(9)])
    faces = []
    for y in range(8):
        for x in range(8):
            i = y*9+x
            faces.extend([[i, i+1, i+10], [i, i+10, i+9]])
    count = len(points)
    points = np.vstack([points, [[.4,0.,0.], [.41,0.,0.], [.4,.01,0.]],
                        [[-.4,0.,0.], [-.41,0.,0.], [-.4,.01,0.]]])
    faces = np.vstack([faces, [count,count+1,count+2], [count+3,count+4,count+5]])
    original = np.r_[np.zeros(count+3,dtype=int), np.ones(3,dtype=int)]
    keep, removed = remap.drop_cut_fragments(points, faces, np.ones(len(faces),dtype=bool), original, 1.)
    assert removed == 1
    assert not keep[-2] and keep[-1]
    assert keep[:-2].all()


def test_nearly_mirrored_long_sleeves_keep_the_same_arm_assignment(rig):
    box_faces = np.array([[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5],
                          [0, 4, 5], [0, 5, 1], [2, 3, 7], [2, 7, 6],
                          [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]])
    trunk = np.array([[x, y, z] for x in [-.10, .10]
                      for y in [-.50, .50] for z in [-.1, .1]])
    sleeves = [np.array([[center+x, y, z] for x in [-.05, .05]
                         for y in [-.215, .355] for z in [-.08, .08]])
               for center in [.2496, -.2526]]
    points = np.vstack([trunk, *sleeves])
    faces = np.vstack([box_faces+offset for offset in [0, 8, 16]])
    parts = np.zeros(len(points), dtype=int)
    remap.remap(points, faces, rig, parts_out=parts)
    assert (parts[8:16] == 1).all()
    assert (parts[16:24] == 2).all()
    # A matching width on a low skirt island does not make it a sleeve.
    low = sleeves[0] - [0., .5, 0.]
    frame = remap.source_skeleton(points)['l']
    assert not remap.long_sleeve_island(low, low.mean(axis=0), *frame, 1.)


def test_broad_connected_cloth_sleeves_keep_their_outer_panels(rig):
    # A broad cloth panel lies outside the narrow arm-axis cylinder. Its
    # shared connection to the chest must not turn the outer cloth into trunk.
    trunk = np.array([[x, y, z] for x in [-.1, .1]
                      for y in [-.5, .5] for z in [-.08, .08]])
    faces = [[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5],
             [0, 4, 5], [0, 5, 1], [2, 3, 7], [2, 7, 6]]
    panels = [np.array([[sign*.52, y, z] for y in [.13, .20]
                        for z in [-.08, .08]]) for sign in [1., -1.]]
    for start, anchor in [(8, 6), (12, 2)]:
        faces.extend([[anchor, start, start+1], [anchor, start+1, start+3],
                      [anchor, start+3, start+2]])
    points = np.vstack([trunk, *panels])
    parts = np.zeros(len(points), dtype=int)
    remap.remap(points, np.asarray(faces), rig, parts_out=parts)
    assert (parts[8:12] == 1).all()
    assert (parts[12:16] == 2).all()


def test_low_hem_tabs_follow_the_trunk_instead_of_the_hand(rig, monkeypatch):
    box_faces = np.array([[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5],
                          [0, 4, 5], [0, 5, 1], [2, 3, 7], [2, 7, 6],
                          [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]])
    trunk = np.array([[x, y, z] for x in [-.10, .10]
                      for y in [-.50, .50] for z in [-.1, .1]])
    tabs = [np.array([[sign*x, y, z] for x in [.25, .272]
                      for y in [-.40, -.382] for z in [-.05, .07]]) for sign in [1, -1]]
    cuff = tabs[0] + [0., .32, 0.]
    points = np.vstack([trunk, *tabs, cuff])
    faces = np.vstack([box_faces+offset for offset in [0, 8, 16, 24]])
    monkeypatch.setattr(remap, 'source_skeleton', lambda _: {
        side: (np.array([sign*.23, .33, -.04]), np.array([sign*.32, -.09, -.07]))
        for side, sign in [('l', 1), ('r', -1)]})
    parts = np.zeros(len(points), dtype=int)
    remap.remap(points, faces, rig, parts_out=parts)
    assert (parts[8:24] == 0).all()
    assert (parts[24:] == 1).all()


@pytest.mark.parametrize('scale', [1., .98])
def test_lining_opens_the_throat_without_lowering_shoulder_coverage(scale):
    # The source shirt may contain an interior collar fold as well as a rim.
    # Both cross the throat opening; the separate shoulder must remain intact.
    points = np.array([[-.04,1.37,.10],[.04,1.37,.10],[.04,1.48,.10],[-.04,1.48,.10],
                       [-.03,1.39,.08],[.03,1.39,.08],[0.,1.47,.09],
                       [.22,1.42,.04],[.25,1.42,.04],[.25,1.46,.04]]) * scale
    faces = np.array([[0,1,2],[0,2,3],[4,5,6],[7,8,9]])
    out, triangles = remap.clip_lining_neckline(points, faces, scale)
    assert out[np.abs(out[:,0]) < .08*scale,1].max() == pytest.approx(1.40*scale)
    for point in points[7:]:
        assert np.linalg.norm(out-point,axis=1).min() < 1e-12
    area = np.linalg.norm(np.cross(out[triangles[:,1]]-out[triangles[:,0]],
                                  out[triangles[:,2]]-out[triangles[:,0]]),axis=1)
    assert (area > 1e-10).all()
    # Clipping retains the original face planes instead of flattening a shell.
    assert np.max(out[:,2]) <= np.max(points[:,2]) + 1e-12

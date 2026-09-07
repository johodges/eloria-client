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

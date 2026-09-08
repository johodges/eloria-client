"""Regressions for the folded groin and upper back reported on 2026-09-08.

Check the serialized rest surface itself: smooth weights can still leave a
fold baked into positions when source/canonical pelvis origins differ.
"""
import hashlib
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'eloria-assets/tools'))
from shared_player_bodies import g


@pytest.fixture(params=['male', 'female'])
def model(request):
    path = ROOT / f'godot-client/assets/actors/native/races/luminous_{request.param}.glb'
    d, b = g.read(path)
    return request.param, d, b


def surfaces(d, b):
    for mesh in d['meshes']:
        for p in mesh['primitives']:
            yield (mesh['name'],
                   {k: g.accessor(d, b, v) for k, v in p['attributes'].items()},
                   g.accessor(d, b, p['indices']).astype(int).reshape(-1, 3))


def orientation(a, f):
    points = a['POSITION'][f]
    geometric = np.cross(points[:, 1]-points[:, 0], points[:, 2]-points[:, 0])
    geometric /= np.maximum(np.linalg.norm(geometric, axis=1, keepdims=True), 1e-15)
    authored = a['NORMAL'][f].mean(1)
    authored /= np.maximum(np.linalg.norm(authored, axis=1, keepdims=True), 1e-15)
    return points.mean(1), (geometric*authored).sum(1)


def test_front_trousers_do_not_fold_back_through_themselves(model):
    _, d, b = model
    for name, a, f in surfaces(d, b):
        if name != 'wardrobe_pants':
            continue
        c, dot = orientation(a, f)
        region = (abs(c[:, 0]) < .16) & (c[:, 1] > .72) & (c[:, 1] < 1.02) & (c[:, 2] > 0)
        assert region.sum() > 1000
        # The previous male/female bodies had 180/114 reversed faces here.
        assert np.count_nonzero(dot[region] < 0) == 0


def test_upper_back_has_no_broad_fold(model):
    _, d, b = model
    for name, a, f in surfaces(d, b):
        if name != 'wardrobe_shirt':
            continue
        c, dot = orientation(a, f)
        region = (abs(c[:, 0]) < .20) & (c[:, 1] > 1.24) & (c[:, 1] < 1.52) & (c[:, 2] < -.025)
        assert region.sum() > 2000
        # Allow the source collar's small sharp lips; reject the broad
        # crumpled patch (0.92% male / 1.67% female in the reported models).
        assert np.mean(dot[region] < 0) < .008


def test_waistband_still_follows_the_pelvis(model):
    _, d, b = model
    names = [d['nodes'][j]['name'] for j in d['skins'][0]['joints']]
    pelvis = names.index('pelvis')
    for name, a, _ in surfaces(d, b):
        if name != 'wardrobe_pants':
            continue
        influence = (a['WEIGHTS_0'] * (a['JOINTS_0'] == pelvis)).sum(1)
        # Moving the geometric fit anchor must not bind the whole waistband
        # to the lumbar spine merely because the donor Hips origin was high.
        assert influence.max() > .99
        assert np.count_nonzero(influence > .5) > 500


def test_body_repair_preserves_the_approved_head(model):
    sex, d, b = model
    # Positions, normals and UVs above the neck from release 8b8d9a68.
    expected = {'male': '67c6cba89fba83fc658d7bd4449dc118c24e53599f50c22b3b861a11aa44ae0a',
                'female': '81ed608e989cc00b4d78855e6501469cbdc192e95db75f0e0c1ec3c87f3d307f'}
    head = hashlib.sha256()
    for name, a, _ in surfaces(d, b):
        if name not in ('body', 'eyes', 'eyebrows', 'scalp'):
            continue
        mask = a['POSITION'][:, 1] > 1.54
        for key in ('POSITION', 'NORMAL', 'TEXCOORD_0'):
            head.update(a[key][mask].tobytes())
    assert head.hexdigest() == expected[sex]

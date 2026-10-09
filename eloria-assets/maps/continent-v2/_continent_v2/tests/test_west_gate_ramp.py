"""The shipped west-gate ramp has aligned, joined decks at both module seams."""
from pathlib import Path
import sys

import numpy as np
import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import export_collision as X

NAMES = [
    'Authored_sw_isle_kit_sw_causeway_arch_ramp_g053_001',
    'Authored_sw_isle_kit_sw_causeway_arch_ramp_g053_002',
    'Authored_sw_isle_kit_sw_causeway_arch_ramp_g037_001',
]


@pytest.fixture(scope='module')
def decks():
    document, body = X.GR.load(HERE.parent / 'sw_isle/client/chunks/05_12/world.glb')
    matrices, parents = X.GR.hierarchy(document)
    nodes = document['nodes']
    result = []
    for name in NAMES:
        root = next(i for i, n in enumerate(nodes) if n.get('name') == name)
        meshes = []
        for i, node in enumerate(nodes):
            if 'mesh' not in node:
                continue
            current, walk = i, False
            while True:
                walk |= nodes[current].get('name', '').startswith('Walk_')
                if current == root:
                    if walk:
                        meshes.append(i)
                    break
                if current not in parents:
                    break
                current = parents[current]
        assert meshes, name
        points = X.GR.triangles(document, body, meshes).reshape(-1, 3)
        axis = matrices[root][[0, 2], 0]
        axis = axis / np.linalg.norm(axis)
        across = np.array([-axis[1], axis[0]])
        distance = points[:, [0, 2]] @ axis
        result.append(dict(axis=axis, centre=matrices[root][[0, 2], 3] @ across,
                           low=distance.min(), high=distance.max(),
                           low_height=np.median(points[np.isclose(distance, distance.min(), atol=1e-4,
                                                                 rtol=0), 1]),
                           high_height=np.median(points[np.isclose(distance, distance.max(), atol=1e-4,
                                                                  rtol=0), 1])))
    return result


@pytest.mark.parametrize('joint', [0, 1])
def test_published_decks_meet_without_a_gap_or_sideways_offset(decks, joint):
    lower, upper = decks[joint:joint + 2]
    np.testing.assert_allclose(lower['axis'], upper['axis'], atol=1e-5)
    assert abs(lower['centre'] - upper['centre']) < .01
    assert abs(upper['low'] - lower['high']) < .01
    assert abs(upper['low_height'] - lower['high_height']) < .04

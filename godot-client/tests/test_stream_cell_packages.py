"""The emitted files must publish actual shared cells, not empty fresh frames."""
import json
from pathlib import Path
import struct

import pytest

MAPS = Path(__file__).resolve().parents[2] / 'eloria-assets/maps'
REGIONS = ('amberwood','whitehorn_range','grey_moors','mirrorhold',
    'amethyst_barrens','westhaven','four_gates','crownwater',
    'sunmane_steppe','verdant_stair','ssarathi_ruins')


def document(path):
    with path.open('rb') as file:
        file.seek(12)
        size,kind=struct.unpack('<II',file.read(8))
        assert kind==0x4e4f534a
        return json.loads(file.read(size))


@pytest.mark.parametrize('region',REGIONS)
def test_emitted_region_uses_resolving_single_copy_approaches(region):
    package=MAPS/'four-gates' if region=='four_gates' else MAPS/'nymara-regions'/region
    manifest=json.loads((package/'world.json').read_text(encoding='utf-8'))
    doc=document(package/'world.glb')
    names={n.get('name','') for n in doc['nodes']}
    for frame in manifest['streamingBorders']:
        assert frame['geometryMode']=='shared-cells-v2'
        declared=frame['sceneNodes']
        assert declared,(region,frame['id'],'empty receiving view')
        assert len(declared)==len(set(declared)),(region,frame['id'],'duplicate membership')
        assert not set(declared)-names,(region,frame['id'],sorted(set(declared)-names))
        assert any('_StreamCell_' in name for name in declared)
    for path in package.glob('world*.glb'):
        assert not [n['name'] for n in document(path)['nodes'] if
            n.get('name','').startswith('StreamView_') or '_StreamOverflow_' in n.get('name','')],path

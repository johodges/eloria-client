"""Whitehorn's approved vendor asset stays attributed through publication."""
import json
from pathlib import Path
import sys


CONTINENT = Path(__file__).resolve().parents[1]
REGIONS = CONTINENT.parent
sys.path.insert(0, str(CONTINENT))
sys.path.insert(0, str(REGIONS / 'whitehorn_range' / 'source'))

import build_continent as BC
import build_library as BL
import build_whitehorn as WHITEHORN


def test_whitehorn_vendor_provenance_survives_library_json_and_continent_overlay():
    payload = BL.regional_publication_metadata(WHITEHORN)
    library_metadata = json.loads(json.dumps({'publicationMetadata': payload}))
    manifest = {
        'sources': ['existing-continent-source.py'],
        'sourceAssets': {'existing': {'sha256': 'kept'}},
        'provenance': {'assets': 'obsolete all-procedural claim', 'existing': 'kept'},
    }

    BC.apply_publication_metadata(manifest, library_metadata)

    cave = manifest['sourceAssets']['caveModel']
    assert manifest['sources'] == ['existing-continent-source.py']
    assert manifest['sourceAssets']['existing'] == {'sha256': 'kept'}
    assert manifest['provenance']['existing'] == 'kept'
    assert 'except' in manifest['provenance']['assets']
    assert manifest['provenance']['thirdPartyModels']['whitehornIceCaveMouthV001'] == cave
    assert cave == {
        'generator': 'Meshy',
        'taskId': '01a0b927-06cb-725a-9639-ac8a2091b1aa',
        'credits': 15,
        'source': 'assets/whitehorn-ice-cave-mouth-v001/model-reference.glb',
        'sha256': '44b0f68e60fa26e200ecccf0a09318e946e611b77ee9b7a3ee96b30a23249873',
        'triangles': 3859,
        'textureResolution': '2048x2048',
        'ownerApprovalDate': '2026-09-19',
        'ownerApprovalRecord': 'owner-review/map-assets/whitehorn-ice-cave-mouth/v001/approval.json',
    }

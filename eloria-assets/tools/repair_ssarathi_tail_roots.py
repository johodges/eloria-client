"""Remove legacy source-trouser patches from retained Ssarathi tails."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import shutil

from shared_player_bodies import clean_tail_root, digest, g, write_group
from verify_shared_player_bodies import primitives, signatures


def repair(source: Path, target: Path) -> dict:
    original, blob = g.read(source)
    document = copy.deepcopy(original)
    binary = bytearray(blob)
    removed = 0
    for mesh in document['meshes']:
        output = []
        for primitive in mesh['primitives']:
            if primitive.get('extras', {}).get('sourceRole') != 'race_tail':
                output.append(primitive)
                continue
            attrs = {key: g.accessor(original, blob, index)
                     for key, index in primitive['attributes'].items()}
            faces = g.accessor(original, blob, primitive['indices']).astype(int).reshape(-1, 3)
            key = (mesh['name'], primitive['material'])
            group = clean_tail_root({'a': attrs, 'f': {key: faces}, 'role': 'race_tail'})
            kept = group['f'].get(key, faces[:0])
            removed += len(faces) - len(kept)
            # Every source triangle beyond the attachment must survive exactly.
            distal = (attrs['POSITION'][faces, 0] > .30).any(axis=1)
            assert not signatures(attrs, faces[distal]) - signatures(attrs, kept)
            pieces = {}
            write_group(document, binary, group, pieces)
            output.extend(pieces.get(mesh['name'], []))
        mesh['primitives'] = output
    document, binary = g.compact(document, bytes(binary))
    target.parent.mkdir(parents=True, exist_ok=True)
    g.write(target, document, binary)
    # Compacting changes accessor indices, but no surviving triangle's data.
    before = list(primitives(original, blob))
    after = list(primitives(document, binary))
    for name, role, attrs, faces in after:
        matches = [signatures(a, f) for n, r, a, f in before if (n, r) == (name, role)]
        expected = sum(matches[1:], matches[0].copy())
        actual = signatures(attrs, faces)
        assert not actual - expected, (source.name, name, role)
    assert original['nodes'] == document['nodes']
    assert original['materials'] == document['materials']
    assert original['skins'][0]['joints'] == document['skins'][0]['joints']
    assert (g.accessor(original, blob, original['skins'][0]['inverseBindMatrices']) ==
            g.accessor(document, binary, document['skins'][0]['inverseBindMatrices'])).all()
    return {'sourceSHA256': digest(source), 'sha256': digest(target),
            'removedRootTriangles': removed,
            'triangles': sum(len(f) for _, _, _, f in after),
            'vertices': sum(len(a['POSITION']) for _, _, a, _ in after),
            'retainedTailTriangles': sum(len(f) for _, role, _, f in after if role == 'race_tail')}


def run(root: Path, out: Path, install: bool = False) -> dict:
    client = root / 'godot-client'
    races = client / 'assets/actors/native/races'
    catalog_path = client / 'data/actors/native_asset_catalog.json'
    masks_path = client / 'assets/actors/native/face_masks/manifest.json'
    report = {}
    for sex in ('male', 'female'):
        slug = 'ssarathi_' + sex
        report[slug] = repair(races / (slug + '.glb'), out / (slug + '.glb'))
    if install:
        backup = out / 'pre-install'
        backup.mkdir(exist_ok=True)
        catalog = json.loads(catalog_path.read_text())
        masks = json.loads(masks_path.read_text())
        for path in (catalog_path, masks_path, *(races / (s + '.glb') for s in report)):
            if not (backup / path.name).exists():
                shutil.copy2(path, backup / path.name)
        for slug, record in report.items():
            shutil.copy2(out / (slug + '.glb'), races / (slug + '.glb'))
            catalog['races'][slug].update({key: record[key] for key in
                ('sha256', 'triangles', 'vertices', 'retainedTailTriangles')})
            masks[slug]['modelSHA256'] = record['sha256']
        catalog_path.write_text(json.dumps(catalog, indent=2) + '\n')
        masks_path.write_text(json.dumps(masks, indent=2) + '\n')
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--install', action='store_true')
    print(json.dumps(run(**vars(parser.parse_args())), indent=2))

"""Install reviewed neck candidates while preserving hair, face masks and tails."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import numpy as np

from shared_player_bodies import g, digest, copy_materials, write_group, material_image
from compact_character_materials import compact_materials
from verify_shared_player_bodies import verify, neck_join_checks, primitives


SLUGS = ('ssarathi_female', 'ssarathi_male', 'glasswarden_female', 'glasswarden_male')


def run(root, candidates, heads):
    client = root/'godot-client'
    native = client/'assets/actors/native'
    files = {'models': client/'data/actors/models.json',
             'catalog': client/'data/actors/native_asset_catalog.json',
             'masks': native/'face_masks/manifest.json'}
    data = {key: json.loads(path.read_text()) for key, path in files.items()}
    reports = {}
    # Validate every graft before replacing any installed model.
    for slug in SLUGS:
        report = verify(candidates/(slug+'.glb'), heads/slug/'head.glb',
                        native/'races'/('luminous_'+slug.rsplit('_', 1)[1]+'.glb'))
        if report['errors']: raise ValueError((slug, report['errors']))
        reports[slug] = report
    backup = candidates/'pre-install'
    backup.mkdir(parents=True, exist_ok=True)
    for key, path in files.items():
        if not (backup/(key+'.json')).exists(): shutil.copy2(path, backup/(key+'.json'))
    for slug in SLUGS:
        path = native/'races'/(slug+'.glb')
        if not (backup/path.name).exists(): shutil.copy2(path, backup/path.name)
        old, old_binary = g.read(backup/path.name)
        d, b = g.read(candidates/path.name)
        binary = bytearray(b)
        body = next(m for m in d['meshes'] if m['name'] == 'body')
        if slug.startswith('ssarathi_'):
            mapping = copy_materials(d, binary, old, old_binary)
            for mesh in old['meshes']:
                for p in mesh['primitives']:
                    if p.get('extras', {}).get('sourceRole') != 'race_tail': continue
                    a = {k: g.accessor(old, old_binary, v) for k, v in p['attributes'].items()}
                    f = g.accessor(old, old_binary, p['indices']).astype(int).reshape(-1, 3)
                    pieces = {}
                    write_group(d, binary, {'a': a, 'f': {('body', mapping[p['material']]): f},
                                           'role': 'race_tail'}, pieces)
                    body['primitives'].extend(pieces.get('body', []))
        # Masks remain valid only when the original face atlas is unchanged.
        prior_body = next(m for m in old['meshes'] if m['name'] == 'body')
        prior_head = next(p for p in prior_body['primitives'] if p.get('extras', {}).get('sourceRole') == 'race_head')
        head = next(p for p in body['primitives'] if p.get('extras', {}).get('sourceRole') == 'race_head')
        np.testing.assert_array_equal(material_image(old, old_binary, prior_head['material'])[1],
                                      material_image(d, binary, head['material'])[1])
        for key in ('sourceSHA256', 'eloriaSurfacesSplit'):
            d['asset']['extras'][key] = copy.deepcopy(old['asset']['extras'][key])
        # Older reviewed candidates may still contain repeated atlas corners.
        for mesh in d['meshes']:
            packed = {}
            for p in mesh['primitives']:
                a = {k: g.accessor(d, bytes(binary), v) for k, v in p['attributes'].items()}
                f = g.accessor(d, bytes(binary), p['indices']).astype(int).reshape(-1, 3)
                piece = {}
                write_group(d, binary, {'a': a, 'f': {(mesh['name'], p['material']): f},
                            'role': p.get('extras', {}).get('sourceRole')}, piece)
                packed.setdefault(mesh['name'], []).extend(piece[mesh['name']])
            mesh['primitives'] = packed[mesh['name']]
        d = compact_materials(d, bytes(binary))
        d, binary = g.compact(d, bytes(binary))
        g.write(path, d, binary)
        surface, head = next((i, p) for m in d['meshes'] if m['name'] == 'body'
                             for i, p in enumerate(m['primitives']) if p.get('extras', {}).get('sourceRole') == 'race_head')
        data['models']['models'][slug]['faceAppearance']['sourceSurface'] = surface
        data['masks'][slug].update(modelSHA256=digest(path), sourceMaterial=head['material'])
        # The garment-bearing body and foot anchors did not move. Preserve
        # reviewed equipment dimensions: sample quantiles can drift when
        # identical vertices are removed even though the surface is unchanged.
        parts = [p for m in d['meshes'] for p in m['primitives']]
        if slug.startswith('ssarathi_'):
            data['catalog']['races'][slug]['retainedTailTriangles'] = sum(
                d['accessors'][p['indices']]['count']//3 for p in parts
                if p.get('extras', {}).get('sourceRole') == 'race_tail')
        data['catalog']['races'][slug].update(sha256=digest(path), sharedBodyShape=d['asset']['extras']['sharedBodyShape'],
            neckAdaptorTriangles=sum(d['accessors'][p['indices']]['count']//3 for p in parts if p.get('extras', {}).get('sourceRole') == 'neck_join'),
            triangles=sum(d['accessors'][p['indices']]['count']//3 for p in parts),
            vertices=sum(d['accessors'][p['attributes']['POSITION']]['count'] for p in parts))
        reports[slug]['installedSHA256'] = digest(path)
        reports[slug]['installedJoinChecks'] = neck_join_checks(list(primitives(d, bytes(binary))))
        print('Installed', slug, flush=True)
    for key, path in files.items(): path.write_text(json.dumps(data[key], indent=2)+'\n')
    (candidates/'installation.json').write_text(json.dumps(reports, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'candidates', 'heads'): parser.add_argument('--'+name, type=Path, required=True)
    run(**vars(parser.parse_args()))

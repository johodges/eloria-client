"""Restore the authored buzzcut as a distinct, fitted fifth hair style."""
import argparse
import json
from pathlib import Path

from fit_character_appearance import fit_hair, head_data, sha
from integrate_luminous_sources import source_head
from shared_player_bodies import g
from race_hair_skull import hair_skull, allows_protrusions


def run(root):
    client = root / 'godot-client'
    native = client / 'assets/actors/native'
    models_path = client / 'data/actors/models.json'
    catalog_path = client / 'data/actors/native_asset_catalog.json'
    models = json.loads(models_path.read_text())
    catalog = json.loads(catalog_path.read_text())
    for slug, config in models['models'].items():
        if 'bodyTemplate' not in config:
            continue
        sex = slug.rsplit('_', 1)[1]
        document, binary = g.read(client / config['scene'].removeprefix('res://'))
        skull = source_head(document, binary) if slug.startswith('luminous_') else head_data(document, binary)
        if allows_protrusions(slug):skull=hair_skull(document,binary,slug)
        horizontal=.95 if allows_protrusions(slug) else 1.
        target = native / 'hair/fitted' / f'{slug}_buzzed_{sex}.glb'
        report = fit_hair(native / 'hair' / f'buzzed_{sex}.glb', target, skull,
                          {'scale': [horizontal, 1, horizontal], 'offset': [0, 0, -.015]}, document, binary)
        config['hairStyles'] = config['hairStyles'][:4] + ['res://' + target.relative_to(client).as_posix()] + config['hairStyles'][5:]
        hair, _ = g.read(target)
        catalog['fittedHair'][f'{slug}:4'] = {
            'path': target.relative_to(root).as_posix(), 'sha256': sha(target), 'joints': 77,
            'triangles': sum(hair['accessors'][p['indices']]['count'] // 3
                             for m in hair['meshes'] for p in m['primitives'])}
        print(slug, report['maxRadialCorrectionM'], flush=True)
    models_path.write_text(json.dumps(models, indent=2) + '\n')
    catalog_path.write_text(json.dumps(catalog, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    run(parser.parse_args().root)

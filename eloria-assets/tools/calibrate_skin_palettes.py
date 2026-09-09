"""Measure authored skin albedo on mesh UVs for consistent runtime dyes.

Calibration is area weighted, excludes protected eye/brow pixels, and does not
modify source textures, geometry or animation. Each skin material retains its
own lighting detail while all characters use the same named target colors.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from shared_player_bodies import g, material_image, sample_image, digest


def weighted_median(values, weights):
    result = []
    for column in values.T:
        order = np.argsort(column)
        result.append(float(column[order[np.searchsorted(np.cumsum(weights[order]), weights.sum() / 2)]]))
    return result


def run(root):
    client = root / 'godot-client'
    path = client / 'data/actors/models.json'
    models = json.loads(path.read_text())
    for slug, config in models['models'].items():
        if 'bodyTemplate' not in config:
            continue
        model = client / config['scene'][6:]
        document, binary = g.read(model)
        spec = config['faceAppearance']
        mask = np.asarray(Image.open(client / spec['mask'][6:]).convert('RGB'))
        refs = {}
        for mesh in document['meshes']:
            part = mesh['name']
            if part not in ('body', 'scalp', 'eyes', 'eyebrows'):
                continue
            refs[part] = []
            for surface, primitive in enumerate(mesh['primitives']):
                vertices = g.accessor(document, binary, primitive['attributes']['POSITION'])
                uv = g.accessor(document, binary, primitive['attributes']['TEXCOORD_0'])
                faces = g.accessor(document, binary, primitive['indices']).astype(int).reshape(-1, 3)
                area = np.linalg.norm(np.cross(vertices[faces[:, 1]] - vertices[faces[:, 0]], vertices[faces[:, 2]] - vertices[faces[:, 0]]), axis=1)
                centers = uv[faces].mean(1)
                _, pixels = material_image(document, binary, primitive['material'])
                colors = sample_image(pixels, centers)
                use = area > 1e-12
                is_face = part != 'body' or surface == spec['sourceSurface']
                if is_face:
                    crop = spec.get('groups', {}).get(part, {})
                    regions = sample_image(mask, centers * crop.get('uvScale', [1, 1]) + crop.get('uvOffset', [0, 0]))
                    use &= regions.max(1) < .094
                # Pure black atlas gutters and eye pupils are not skin albedo.
                use &= colors.max(1) > .10
                refs[part].append(weighted_median(colors[use], area[use]) if use.any() else [0.7, 0.6, 0.5])
        # The face partitions share one skin calibration: tiny eyelid strips
        # and forehead islands must not establish independent brightness.
        face = refs['body'][spec['sourceSurface']]
        for part in ('eyes', 'eyebrows', 'scalp'):
            if part in refs:
                refs[part] = [face for _ in refs[part]]
        config['skinPalette'] = {'version': 1, 'sourceSHA256': digest(model), 'references': refs}
        print(slug, np.round(face, 3).tolist(), flush=True)
    path.write_text(json.dumps(models, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    run(parser.parse_args().root)

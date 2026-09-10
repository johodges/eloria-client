"""Give the Ssarathi waistband its trouser material and a clean hem.

The shared shirt includes triangles below its textured hem. Those triangles
sample the source's dark trousers from the shirt atlas, producing a black,
sawtooth strip. Reclassify the faces at the hem and map that narrow strip to
the existing trouser cloth. Every triangle, normal and skinning weight is kept.
No texture pixels, skeletons, tails or head surfaces are edited.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
from collections import Counter
import numpy as np
from scipy.spatial import cKDTree

from shared_player_bodies import g, write_group, digest
from verify_shared_player_bodies import primitives, signatures, GEOMETRY_FIELDS

HEM_HEIGHTS = {'ssarathi_male': 1.068, 'ssarathi_female': 1.083}


def project_uv(points, source, faces, uv):
    triangles = source[faces]
    tree = cKDTree(triangles.mean(axis=1))
    query = points.copy()
    # Sample the same side's cloth below the belt and its baked contact shadow.
    query[:, 1] -= .065
    _, ids = tree.query(query, k=12)
    tri = triangles[ids]
    a, b, c = tri[:, :, 0], tri[:, :, 1], tri[:, :, 2]
    v0, v1, v2 = b-a, c-a, query[:, None, :]-a
    d00 = np.sum(v0*v0, axis=2); d01 = np.sum(v0*v1, axis=2)
    d11 = np.sum(v1*v1, axis=2); d20 = np.sum(v2*v0, axis=2)
    d21 = np.sum(v2*v1, axis=2)
    denom = np.maximum(d00*d11-d01*d01, 1e-15)
    v = (d11*d20-d01*d21)/denom
    w = (d00*d21-d01*d20)/denom
    bary = np.maximum(np.stack([1-v-w, v, w], axis=2), 0)
    bary /= np.maximum(bary.sum(axis=2, keepdims=True), 1e-10)
    closest = np.sum(tri*bary[:, :, :, None], axis=2)
    picked = np.argmin(np.sum((closest-query[:, None, :])**2, axis=2), axis=1)
    rows = np.arange(len(points))
    return np.sum(uv[faces[ids[rows, picked]]]*bary[rows, picked, :, None], axis=1)


def repair_document(document, old, slug):
    d = copy.deepcopy(document)
    extras = d['asset'].setdefault('extras', {})
    if extras.get('waistSeamRepair', {}).get('version') == 1:
        return d, old
    height = HEM_HEIGHTS[slug]
    b = bytearray(old)
    shirt = next(m for m in d['meshes'] if m['name'] == 'wardrobe_shirt')
    pants = next(m for m in d['meshes'] if m['name'] == 'wardrobe_pants')
    pp = pants['primitives'][0]
    pa = {k: g.accessor(d, old, i) for k, i in pp['attributes'].items()}
    pf = g.accessor(d, old, pp['indices']).astype(int).reshape(-1, 3)
    output = []
    transferred = 0
    for primitive in shirt['primitives']:
        attrs = {k: g.accessor(d, old, i) for k, i in primitive['attributes'].items()}
        attrs['JOINTS_0'] = attrs['JOINTS_0'].astype('<u2')
        if attrs['POSITION'][:, 1].min() > height:
            output.append(primitive)
            continue
        faces = g.accessor(d, old, primitive['indices']).astype(int).reshape(-1, 3)
        below = attrs['POSITION'][faces, 1].mean(axis=1) < height
        key = ('wardrobe_shirt', primitive['material'])
        upper = {'a': attrs, 'f': {key: faces[~below]}}
        lower = {'a': attrs.copy(), 'f': {key: faces[below]}}
        upper['role'] = lower['role'] = primitive.get('extras', {}).get('sourceRole', 'shared_body')
        lf = next(iter(lower['f'].values()))
        transferred += len(lf)
        # One local cloth sample per narrow triangle avoids interpolation
        # across unrelated UV islands; the existing facet normals retain folds.
        lower['a'] = {k: value[lf.ravel()] for k, value in lower['a'].items()}
        centres = lower['a']['POSITION'].reshape(-1, 3, 3).mean(axis=1)
        lower['a']['TEXCOORD_0'] = np.repeat(project_uv(centres, pa['POSITION'], pf, pa['TEXCOORD_0']), 3, axis=0).astype('<f4')
        lower['f'] = {('wardrobe_pants', pp['material']): np.arange(lf.size).reshape(-1, 3)}
        pieces = {}
        write_group(d, b, upper, pieces)
        write_group(d, b, lower, pieces)
        output.extend(pieces['wardrobe_shirt'])
        pants['primitives'].extend(pieces['wardrobe_pants'])
    shirt['primitives'] = output
    extras['waistSeamRepair'] = {'version': 1, 'hemHeightM': height,
        'waistbandTriangles': transferred, 'texturesUnchanged': True,
        'geometryUnchanged': True}
    d, b = g.compact(d, b)
    def geometry(doc, blob):
        result = Counter()
        for _, _, attrs, faces in primitives(doc, blob):
            result.update(signatures(attrs, faces, GEOMETRY_FIELDS))
        return result
    if geometry(document, old) != geometry(d, b):
        raise ValueError('Waist material repair changed geometry or skinning')
    return d, b


def run(root, out, install=False):
    client = root/'godot-client'
    races = client/'assets/actors/native/races'
    out.mkdir(parents=True, exist_ok=True)
    if out.resolve() == races.resolve():
        raise ValueError('Use a separate candidate directory')
    report = {}
    for slug in HEM_HEIGHTS:
        source = races/(slug+'.glb')
        d, b = g.read(source)
        d, b = repair_document(d, b, slug)
        target = out/source.name
        g.write(target, d, b)
        parts = [p for mesh in d['meshes'] for p in mesh['primitives']]
        report[slug] = {'sourceSHA256': digest(source), 'sha256': digest(target),
            'triangles': sum(d['accessors'][p['indices']]['count']//3 for p in parts),
            'vertices': sum(d['accessors'][p['attributes']['POSITION']]['count'] for p in parts),
            'waistSeamRepair': d['asset']['extras']['waistSeamRepair']}
    if install:
        catalog_path = client/'data/actors/native_asset_catalog.json'
        masks_path = client/'assets/actors/native/face_masks/manifest.json'
        backup = out/'pre-install'
        backup.mkdir(exist_ok=True)
        catalog = json.loads(catalog_path.read_text())
        masks = json.loads(masks_path.read_text())
        for path in (catalog_path, masks_path, *(races/(s+'.glb') for s in HEM_HEIGHTS)):
            if not (backup/path.name).exists():
                shutil.copy2(path, backup/path.name)
        for slug, record in report.items():
            if digest(races/(slug+'.glb')) != record['sourceSHA256']:
                raise ValueError('Source changed during repair: '+slug)
        for slug, record in report.items():
            shutil.copy2(out/(slug+'.glb'), races/(slug+'.glb'))
            catalog['races'][slug].update({key: record[key] for key in
                ('sha256', 'triangles', 'vertices', 'waistSeamRepair')})
            masks[slug]['modelSHA256'] = record['sha256']
        catalog_path.write_text(json.dumps(catalog, indent=2)+'\n')
        masks_path.write_text(json.dumps(masks, indent=2)+'\n')
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--install', action='store_true')
    print(json.dumps(run(**vars(parser.parse_args())), indent=2))

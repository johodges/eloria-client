"""Refresh only the surveyed Four Gates north-gate slope from source geometry.

Run after changing collision_export's approach policy. A complete continent
export applies the same policy. This maintenance pass leaves every cell outside
the apron untouched, and still checks actual structures and water before opening.
"""
from pathlib import Path
from types import SimpleNamespace
import argparse
import hashlib
import json
import struct

import numpy as np

import collision_export as C
from world_layout import triangle_sample


def refresh(package, apply=False):
    package = Path(package)
    manifest = json.loads((package / 'world.json').read_text(encoding='utf-8'))
    snapshot = json.loads((package / 'authoring/continent-authoring.json').read_text(encoding='utf-8'))
    terrain = snapshot['terrain']
    heights = np.fromfile(package / 'authoring' / terrain['resolvedHeights']['path'], dtype='<f4')
    heights = heights.reshape(terrain['height'], terrain['width'])
    world = SimpleNamespace(height=heights, x0=terrain['origin'][0],
                            z0=terrain['origin'][1], cell=terrain['cellMetres'])
    raw = (package / 'collision.bin').read_bytes()
    magic, version, flags, width, rows = struct.unpack_from('<4sHHII', raw)
    if magic != b'EWCG' or version != 2 or flags or len(raw) != 16 + width * rows:
        raise ValueError('Expected an unextended EWCG v2 grid')
    grid = np.frombuffer(raw, dtype=np.uint8, offset=16).reshape(rows, width).copy()
    ox, oz = manifest['collision']['originMetres']
    x0, z0, x1, z1 = C.NORTH_GATE_APPROACH
    c0, c1 = round((x0-ox)/C.CELL), round((x1-ox)/C.CELL)
    r0, r1 = round((oz-z1)/C.CELL), round((oz-z0)/C.CELL)
    x, z = np.meshgrid(x0 + (np.arange(c1-c0)+.5)*C.CELL,
                       z1 - (np.arange(r1-r0)+.5)*C.CELL)
    surface = triangle_sample(heights, x, z, world.x0, world.z0, world.cell)
    grade = C.terrain_grade(world, x, z)
    document, body = C.GR.load(package / 'world.glb')
    walk, structures, _ = C._mesh_groups(document, body, manifest)
    covered, deck = C.GR.rasterise(walk, c1-c0, r1-r0, x0, z1, C.CELL,
                                  upward=1/np.sqrt(1+C.MAX_GRADE**2)-1e-9)
    support = covered & (deck >= surface-.03)
    surface = np.where(support, deck, surface)
    blocked = C.structural_mask(structures, surface, x0, z1)
    wet, water = C.GR.rasterise(C.GR.triangles(document, body, C.GR.named(document, 'Water_')),
                               c1-c0, r1-r0, x0, z1, C.CELL, upward=.001)
    eligible = ((grade <= C.terrain_grade_limit('four_gates', x, z)+1e-9) | support)
    eligible &= ~blocked & ~(wet & (surface < water-C.WADE)) & np.isfinite(surface)
    encoding = manifest['collision']['heightEncoding']
    codes = np.rint((surface-encoding['origin'])/encoding['step'])
    eligible &= (codes >= 1) & (codes <= 255)
    patch = grid[r0:r1, c0:c1]
    # The existing ownership mask remains authoritative. This interior apron
    # is far from all territory borders, and only its newly permitted slope
    # cells are candidates; other previously closed cells remain closed.
    opened = (patch == 0) & eligible & (grade > C.MAX_GRADE)
    patch[opened] = codes[opened].astype(np.uint8)
    report = {'openedHalfCells': int(opened.sum()), 'maximumOpenedGrade':
              float(grade[opened].max()) if opened.any() else 0.,
              'boundsMetres': list(C.NORTH_GATE_APPROACH), 'structuresChecked': True}
    if apply:
        (package / 'collision.bin').write_bytes(raw[:16] + grid.tobytes())
        collision = manifest['collision']
        collision['walkableCells'] = int(np.count_nonzero(grid))
        collision['walkableFraction'] = round(float(np.count_nonzero(grid)/grid.size), 6)
        collision['exportStatistics']['steepCells'] -= int(opened.sum())
        collision['terrainGradeApproaches'] = [{'id': 'north-gate-quarry-apron',
            'boundsMetres': list(C.NORTH_GATE_APPROACH), 'maximumGrade': C.NORTH_GATE_APPROACH_GRADE}]
        for name in ('world.json', 'world-lod2.json'):
            path = package / name
            if path.exists():
                out = manifest if name == 'world.json' else json.loads(path.read_text(encoding='utf-8'))
                out['collision'] = collision
                if 'continentPublication' in out:
                    out['continentPublication']['collisionSha256'] = hashlib.sha256((package/'collision.bin').read_bytes()).hexdigest()
                newline = '\r\n' if b'\r\n' in path.read_bytes() else '\n'
                path.write_bytes((json.dumps(out, indent=2, ensure_ascii=False)+'\n').replace('\n', newline).encode('utf-8'))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(refresh(args.package, args.apply), indent=2))

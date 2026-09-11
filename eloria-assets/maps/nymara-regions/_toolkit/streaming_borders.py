"""Authored, reciprocal road collars for exterior scene streaming.

Coordinates are tile centres. The seam sits one metre inward from the trigger;
the two-metre arrival offset therefore preserves the traveller's world position.
Overflow remains in the collision survey and is hidden only while its real
neighbour is resident. No server or rendered walking surface is invented at run time.
"""
import numpy as np
from border_vistas import clip_window
from amberwood.terrain import _compact

PAIR = {
    'amberwood': dict(portal='north-pass', destination='whitehorn_range',
                     anchor=[67.5, 55.2, -256.5], outward=[0, -1], uvSign=1),
    'whitehorn_range': dict(portal='west-pass', destination='amberwood',
                           anchor=[-106.5, 35.8, -54.5], outward=[-1, 0], uvSign=-1),
}


def _refine_collar(mesh, edge, forward, side):
    """Keep the material edge below a metre instead of a repeated triangle saw."""
    columns = [mesh.positions, mesh.normals, mesh.uvs]
    if mesh.colors is not None: columns.append(mesh.colors)
    values = np.concatenate(columns, axis=1)
    faces = mesh.indices.reshape(-1, 3)
    for _ in range(3):
        triangles = values[faces, :3]
        centres = triangles.mean(axis=1)[:, [0, 2]] - edge
        depth, lateral = centres @ forward, centres @ side
        longest = np.maximum.reduce([np.linalg.norm(triangles[:, a] - triangles[:, b], axis=1)
                                     for a, b in ((0, 1), (1, 2), (2, 0))])
        selected = (depth > -16) & (depth < 5) & (abs(lateral) < 55) & (longest > .9)
        if not selected.any(): break
        old = faces[selected]
        mids = np.stack([(values[old[:, a]] + values[old[:, b]]) / 2
                         for a, b in ((0, 1), (1, 2), (2, 0))], axis=1)
        ids = np.arange(len(values), len(values) + 3 * len(old)).reshape(-1, 3)
        values = np.concatenate([values, mids.reshape(-1, values.shape[1])])
        a, b, c = old.T; ab, bc, ca = ids.T
        faces = np.concatenate([faces[~selected], np.stack([a, ab, ca], axis=1),
            np.stack([ab, b, bc], axis=1), np.stack([ca, bc, c], axis=1), np.stack([ab, bc, ca], axis=1)])
    mesh.positions, mesh.normals, mesh.uvs = values[:, :3], values[:, 3:6], values[:, 6:8]
    if mesh.colors is not None: mesh.colors = values[:, 8:12]
    mesh.indices = faces.reshape(-1)


def apply(build, region):
    spec = PAIR[region]
    edge = np.array(spec['anchor'])[[0, 2]]
    forward = np.array(spec['outward'], float)
    side = np.array([-forward[1], forward[0]])
    level = spec['anchor'][1]

    def grade(points):
        points = points.copy()
        relative = points[:, [0, 2]] - edge
        depth, lateral = relative @ forward, relative @ side
        # One broad saddle, open across the road and rising into both shoulders.
        target = level + 8 * (1 - np.exp(-(lateral / 30)**2))
        blend = np.clip((depth + 42) / 32, 0, 1)
        blend = blend * blend * (3 - 2 * blend)
        shoulder = np.clip((abs(lateral) - 38) / 30, 0, 1)
        blend *= 1 - shoulder * shoulder * (3 - 2 * shoulder)
        points[:, 1] += (target - points[:, 1]) * blend
        return points

    for bucket in (build.terrain_meshes, build.water_meshes):
        for name, original in list(bucket.items()):
            if name.startswith('Backdrop_Neighbour_') or name.startswith('Backdrop_NeighbourRoad_'):
                continue
            if name.startswith('Terrain_'):
                _refine_collar(original, edge, forward, side)
            original.positions = grade(original.positions)
            original.recompute_normals(180)
            # Both directions use the same gravel and UV frame for the last
            # few metres. A ragged inner edge blends back to each region's soil.
            if name.startswith('Terrain_'):
                faces = original.indices.reshape(-1, 3)
                coords = original.positions[:, [0, 2]] - edge
                depth, lateral = coords @ forward, coords @ side
                near = np.minimum(np.clip(.5 + (depth + 10 - 1.8 * np.sin(lateral * .19)
                                             - .7 * np.sin(lateral * .73)) / 1.2, 0, 1),
                                  np.clip((60 - abs(lateral)) / 3, 0, 1))
                if near.max(initial=0) > .5:
                    if original.colors is None: original.colors = np.ones((len(original.positions), 4))
                    alpha = original.colors[:, 3].copy()
                    u, v = lateral * spec['uvSign'], depth * spec['uvSign']
                    road = np.clip(.5 + (3.4 + .4 * np.sin(v * .3) - abs(u)) / 1.0, 0, 1)
                    frost = np.minimum(np.clip((abs(u) - 7) / 1.2, 0, 1),
                        np.clip(.5 + (np.sin(u * .17) + np.cos(v * .23) +
                            .45 * np.sin((u + v) * .37) - .35) / .8, 0, 1))
                    # Continuous substrate below the cutout paint prevents
                    # cracks where interpolated masks meet inside a triangle.
                    # Centimetre offsets avoid coplanar depth fighting.
                    for suffix, mask, material, lift in [
                            ('Turf', np.ones_like(road), 'alpine_turf_ground', .008),
                            ('Frost', frost, 'alpine_snowfield_ground', .016),
                            ('Road', road, 'alpine_gravel_ground', .024)]:
                        gravel = original.copy()
                        gravel.positions[:, 1] += lift
                        gravel.colors[:, 3] = np.minimum.reduce([alpha, near, mask])
                        gravel.indices = faces[gravel.colors[faces, 3].max(axis=1) >= .5].reshape(-1)
                        gravel.material = material
                        gravel.uvs = np.stack([u, v], axis=1) * .28
                        bucket[name + '_StreamCollar' + suffix] = _compact(gravel)
            bucket[name] = _compact(original)
        # Split every triangle on the exact plane, including background hills.
        # The hidden half still supplies the departure tile's physics surface.
        for name, original in list(bucket.items()):
            if original.triangle_count == 0: continue
            front, overflow = original.copy(), original.copy()
            clip_window(front, edge, forward, side, half_width=100000)
            clip_window(overflow, edge, -forward, -side, half_width=100000)
            bucket[name] = _compact(front)
            if overflow.triangle_count:
                bucket[name + '_StreamOverflow'] = _compact(overflow)
    kept = []
    for placement in build.placements:
        p = np.asarray(placement.position, float)
        relative = p[[0, 2]] - edge
        depth, lateral = relative @ forward, relative @ side
        if depth > -42:
            # The receiving scene supplies this side of the border. Removing
            # only perimeter dressing leaves services and landmarks unchanged.
            if depth > 0 or (abs(lateral) < 7 and placement.kind in ('tree', 'foliage', 'rock', 'undergrowth')):
                continue
            placement.position = tuple(grade(p[None, :])[0])
        kept.append(placement)
    build.placements[:] = kept
    build.streaming_borders = [dict(id='amberwood-whitehorn', **spec,
        preloadDistance=170, retainDistance=220, blendDistance=65,
        overflowSuffix='_StreamOverflow', collarDepth=42, halfWidthTiles=3)]

"""Small ferry quays fitted to frozen bank and water geometry.

No terrain or landing coordinates are changed. A missing shoreline, submerged
arrival, shallow mooring or unbuildable ramp fails before a GLB is written.
"""
from __future__ import annotations

from pathlib import Path
import math
import sys

import numpy as np
from scipy.ndimage import label

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / '_toolkit'))
import landscape as L
from amberwood import gltf as G, mesh as M

MAX_GRADE = .45
RAMP_GRADE = .445
HALF_WIDTH = 1.35
MAX_REACH = 48.
DECK_CLEARANCE = .72


def samples(world, points, water_fields=None):
    points = np.asarray(points, float)
    bed = np.asarray(world.height_at(points[..., 0], points[..., 1]), float)
    water = (water_fields or L.water_fields)(points[..., 0], points[..., 1], height=bed, plan=world.plan)
    if not np.isfinite(bed).all() or not np.isfinite(water['surface']).all():
        raise ValueError('Ferry shoreline contains non-finite ground or water')
    return bed, water


def profile_above(lower, spacing):
    """Nearest grade-bounded surface above all bank/clearance constraints."""
    result = np.asarray(lower, float).copy()
    allowance = spacing * RAMP_GRADE
    for index in range(1, len(result)):
        result[index] = max(result[index], result[index-1] - allowance)
    for index in range(len(result)-2, -1, -1):
        result[index] = max(result[index], result[index+1] - allowance)
    return result


def boat_points(center, forward, side):
    # Include the widest hull and its extremities, not only a wet centre point.
    return np.array([center + forward * z + side * x
                     for z in (-3., -1.5, 0., 1.5, 3.) for x in (-1.2, 0., 1.2)])


def ocean_membership(world):
    """Conservative outer-ocean membership from the final frozen bed grid.

    A low inland pond or raised river cannot silently become a sea-ferry berth.
    Tiny synthetic worlds without a sampled grid retain explicit water checks.
    """
    if not all(hasattr(world, name) for name in ('height', 'x', 'z')):
        return lambda points: np.ones(np.asarray(points).shape[:-1], bool)
    grid = np.asarray(world.height) < float(world.plan['sea_level']) - .015
    labels, _ = label(grid, structure=np.ones((3, 3)))
    outer = np.unique(np.r_[labels[0], labels[-1], labels[:, 0], labels[:, -1]])
    ocean = np.isin(labels, outer[outer > 0])
    xs, zs = np.asarray(world.x), np.asarray(world.z)
    def query(points):
        points = np.asarray(points, float)
        ix = (points[..., 0] - xs[0]) / (xs[1]-xs[0])
        iz = (points[..., 1] - zs[0]) / (zs[1]-zs[0])
        x0, z0 = np.floor(ix).astype(int), np.floor(iz).astype(int)
        x1, z1 = np.ceil(ix).astype(int), np.ceil(iz).astype(int)
        valid = (x0 >= 0) & (z0 >= 0) & (x1 < ocean.shape[1]) & (z1 < ocean.shape[0])
        x0, x1 = np.clip(x0, 0, ocean.shape[1]-1), np.clip(x1, 0, ocean.shape[1]-1)
        z0, z1 = np.clip(z0, 0, ocean.shape[0]-1), np.clip(z1, 0, ocean.shape[0]-1)
        return valid & ocean[z0, x0] & ocean[z0, x1] & ocean[z1, x0] & ocean[z1, x1]
    return query


def clear_of_retained_routes(world, points):
    """A quay/skiff must not cross retained causeways or existing working quays."""
    mask=getattr(world,'ferry_exclusion',None)
    if mask is None:return True
    points=np.asarray(points,float).reshape(-1,2)
    spacing=float(world.x[1]-world.x[0])
    ix=np.floor((points[:,0]-world.x[0])/spacing).astype(int)
    iz=np.floor((points[:,1]-world.z[0])/spacing).astype(int)
    for dx,dz in ((0,0),(1,0),(0,1),(1,1)):
        x=np.clip(ix+dx,0,mask.shape[1]-1);z=np.clip(iz+dz,0,mask.shape[0]-1)
        if np.any(mask[z,x]):return False
    return True


def fit_landing(world, landing, region, *, water_fields=None):
    """Search actual water directions rather than a continent-centre bearing."""
    landing = np.asarray(landing, float)
    ground, initial = samples(world, landing[None, :], water_fields)
    if bool(initial['mask'][0]) and float(initial['depth'][0]) > .12:
        raise ValueError(f'{region}: ferry landing is already under water at {landing.tolist()}')
    angles = np.arange(64) * (2 * math.pi / 64)
    directions = np.c_[np.cos(angles), np.sin(angles)]
    distances = np.arange(6., MAX_REACH + .01, 2.)
    candidates = landing + directions[:, None, :] * distances[None, :, None]
    _, field = samples(world, candidates, water_fields)
    in_ocean = ocean_membership(world)
    available = np.argwhere(field['mask'] & (field['depth'] >= 1.15) & (field['depth'] < 8.) & in_ocean(candidates)
                            & (abs(field['surface'] - float(world.plan['sea_level'])) < .12))
    if not len(available):
        raise ValueError(f'{region}: no suitable actual water within {MAX_REACH:g}m of ferry landing {landing.tolist()}')
    fits, rejected = [], []
    for angle, station in sorted(available, key=lambda index: (distances[index[1]], int(index[0]))):
        distance = float(distances[station])
        # Once a compact fit exists, distant alternatives cannot improve it.
        if fits and distance > min(f['reach'] for f in fits) + 4:
            break
        forward = directions[angle]
        side = np.array([-forward[1], forward[0]])
        endpoint = candidates[angle, station]
        for mooring_side in (-1., 1.):
            boat_center = endpoint + side * (4.1 * mooring_side) - forward * 1.2
            footprint = boat_points(boat_center, forward, side)
            if not clear_of_retained_routes(world,footprint):continue
            boat_bed, boat_water = samples(world, footprint, water_fields)
            if not (np.asarray(boat_water['mask']).all() and in_ocean(footprint).all() and np.min(boat_water['depth']) >= .65
                    and np.ptp(boat_water['surface']) < .12):
                continue
            stations = np.linspace(-4., distance, int(round((distance + 4.) * 2)) + 1)
            centres = landing + stations[:, None] * forward
            banks = centres[:, None, :] + np.array([-HALF_WIDTH, 0., HALF_WIDTH])[None, :, None] * side
            if not clear_of_retained_routes(world,banks):continue
            bed, water = samples(world, banks, water_fields)
            lower = np.max(np.where(water['mask'], np.maximum(bed + .025, water['surface'] + DECK_CLEARANCE), bed + .025), axis=1)
            heights = profile_above(lower, stations[1] - stations[0])
            landing_index = int(np.argmin(abs(stations)))
            # Both the dry arrival end and the actual ferry trigger must meet
            # existing ground. A smooth ramp floating above the trigger fails.
            contact_error = max(float(heights[0] - bed[0, 1]), float(heights[landing_index] - ground[0]))
            above_water = float(heights[-1] - field['surface'][angle, station])
            tallest_pile = float(np.max(heights[:, None] - bed))
            if contact_error > .16 or bool(water['mask'][0, 1]) or above_water > 2.2 or tallest_pile > 10.:
                rejected.append((max(contact_error/.16, above_water/2.2, tallest_pile/10.,
                                     100. if water['mask'][0, 1] else 0.), contact_error, above_water, tallest_pile))
                continue
            grade = float(np.max(abs(np.diff(heights)) / np.diff(stations)))
            fits.append(dict(region=region, landing=landing, forward=forward, side=side,
                             centres=centres, stations=stations, heights=heights, reach=distance,
                             boatCenter=boat_center, waterLevel=float(np.mean(boat_water['surface'])),
                             minimumBoatDepth=float(np.min(boat_water['depth'])), contactError=contact_error,
                             maximumGrade=grade, mooringSide=mooring_side))
    if not fits:
        detail = ''
        if rejected:
            _, contact, deck, pile = min(rejected)
            detail = f'; best rejected fit lifts the contact {contact:.3f}m, ends {deck:.3f}m above water and needs {pile:.3f}m piles'
        raise ValueError(f'{region}: actual shoreline cannot fit a <=.45 grade quay and wet mooring within {MAX_REACH:g}m at {landing.tolist()}' + detail)
    return min(fits, key=lambda fit: (fit['reach'], fit['contactError'], fit['maximumGrade']))


def landing_groups(world, *, water_fields=None):
    groups = []
    for connection in sorted(world.connections, key=lambda item: item['id']):
        if connection['type'] != 'ferry':
            continue
        if len(connection.get('landings', [])) != 2:
            raise ValueError(connection['id'] + ': ferry requires two actual authored landings')
        for region, position in zip(connection['regions'], connection['landings']):
            near = None
            for group in groups:
                if group['region'] != region or np.linalg.norm(np.asarray(position) - group['landing']) > 8.:
                    continue
                _, water = samples(world, np.linspace(group['landing'], position, 17), water_fields)
                if not np.asarray(water['mask']).any():
                    near = group
                    break
            if near is None:
                near = dict(region=region, landing=np.asarray(position, float), connections=[])
                groups.append(near)
            near['connections'].append(connection['id'])
    return groups


def ribbon(centres, heights, side, half_width, material):
    points = np.empty((len(centres), 2, 3))
    for column, across in enumerate((-half_width, half_width)):
        points[:, column, :][:, [0, 2]] = centres + side * across
        points[:, column, 1] = heights
    a = np.arange(len(centres)-1) * 2
    indices = np.c_[a, a+1, a+2, a+1, a+3, a+2].ravel()
    mesh = M.Mesh(positions=points.reshape(-1, 3), normals=np.tile([0., 1., 0.], (len(points)*2, 1)),
                  uvs=np.c_[np.repeat(np.arange(len(points)) * .5, 2), np.tile([0., 1.], len(points))],
                  indices=indices, material=material)
    mesh.recompute_normals(180)
    return mesh


def oriented_box(size, center, forward, material):
    side = np.array([forward[1], -forward[0]])
    matrix = np.eye(4)
    matrix[:3, 0] = [side[0], 0., side[1]]
    matrix[:3, 2] = [forward[0], 0., forward[1]]
    matrix[:3, 3] = center
    return M.box(size, material=material).transform(matrix)


def mooring_rope(start, end):
    start, end = np.asarray(start), np.asarray(end)
    delta = end-start
    up = delta/np.linalg.norm(delta)
    right = np.cross(up, [0., 1., 0.])
    right /= np.linalg.norm(right)
    matrix = np.eye(4)
    matrix[:3, 0], matrix[:3, 1], matrix[:3, 2] = right, up, np.cross(right, up)
    matrix[:3, 3] = (start+end)*.5
    return M.box((.075, np.linalg.norm(delta), .075), material='ferry_trim').transform(matrix)


def skiff_meshes(fit):
    center, forward, side, level = fit['boatCenter'], fit['forward'], fit['side'], fit['waterLevel']
    def point(x, y, z):
        p = center + side * x + forward * z
        return (p[0], level + y, p[1])
    ring = [(-.08, -3.), (-1.05, -1.9), (-1.2, .8), (-.75, 2.5), (0., 3.),
            (.75, 2.5), (1.2, .8), (1.05, -1.9), (.08, -3.)]
    sides, trim = [], []
    for (ax, az), (bx, bz) in zip(ring, ring[1:] + ring[:1]):
        sides.append(M.quad([point(ax*.62, -.32, az*.91), point(bx*.62, -.32, bz*.91),
                             point(bx, .48, bz), point(ax, .48, az)], material='ferry_hull'))
        trim.append(M.quad([point(ax, .48, az), point(bx, .48, bz),
                           point(bx*.88, .46, bz*.97), point(ax*.88, .46, az*.97)], material='ferry_trim'))
    yield 'Hull', M.merge(sides, material='ferry_hull')
    yield 'Gunwale', M.merge(trim, material='ferry_trim')
    # Cover the complete interior above the shared sea plane. A floor below
    # water (or a narrow rectangle inside this tapered hull) looks flooded.
    floor_points = np.asarray([point(0., .08, 0.)] + [point(x*.85, .08, z*.96) for x, z in ring])
    edge_indices = np.arange(1, len(floor_points))
    indices = np.c_[np.zeros(len(edge_indices), int), edge_indices, np.roll(edge_indices, -1)]
    triangle = floor_points[indices[0]]
    if np.cross(triangle[1]-triangle[0], triangle[2]-triangle[0])[1] < 0:
        indices[:, [1, 2]] = indices[:, [2, 1]]
    yield 'Floor', M.Mesh(positions=floor_points, normals=np.tile([0., 1., 0.], (len(floor_points), 1)),
                          uvs=floor_points[:, [0, 2]], indices=indices.ravel(), material='ferry_timber')
    for index, station in enumerate((-1.45, .15, 1.5)):
        p = center + forward * station
        yield 'Seat_' + str(index), oriented_box((1.75, .14, .34), (p[0], level+.25, p[1]), forward, 'ferry_timber')
    mast = center + forward * .5
    yield 'Mast', M.box((.14, 2.5, .14), center=(mast[0], level+1.1, mast[1]), material='ferry_timber')
    yield 'FurledSail', oriented_box((.55, 1.55, .18), (mast[0], level+1.5, mast[1]), forward, 'ferry_canvas')


def build_ferries(world, path, *, water_fields=None):
    """Return global scene parts for named ownership/chunk export, like bridges."""
    groups = landing_groups(world, water_fields=water_fields)
    fits = [fit_landing(world, group['landing'], group['region'], water_fields=water_fields) for group in groups]
    builder = G.GltfBuilder('Eloria bank-fitted timber ferry landings')
    for name, color in [('timber', (.47, .31, .17)), ('hull', (.24, .18, .13)),
                        ('trim', (.68, .54, .30)), ('canvas', (.78, .73, .56))]:
        builder.add_material(G.Material('ferry_' + name, base_color=tuple(np.asarray(color)**2.2)+(1.,), roughness=.9,
                                        double_sided=name in ('hull', 'trim', 'canvas')))
    parts, reports, walk_triangles = [], [], []
    def add(region, name, mesh):
        # A quay deck is a designed deck the plan names (landscape.designed_deck_entry).
        if name.startswith('Walk_'):
            L.require_designed_deck(getattr(world, 'plan', None) or {}, name, 'ferry_export')
        builder.add_mesh(name, mesh, with_tangents=False)
        root = builder.add_node(G.Node(name, mesh=name))
        parts.append(dict(region=region, roots=[root], bounds=mesh.bounds(), node=name, segment=[]))
    for number, (group, fit) in enumerate(zip(groups, fits)):
        name = f"FerryQuay_{group['region']}_{number:02d}"
        region, side, forward = group['region'], fit['side'], fit['forward']
        centres, heights = fit['centres'], fit['heights']
        deck = ribbon(centres, heights, side, HALF_WIDTH, 'ferry_timber')
        add(region, 'Walk_' + name, deck)
        walk_triangles.append(deck.positions[deck.indices.reshape(-1, 3)])
        # Fascia below the actual walk plane gives the modest deck a solid edge.
        for direction in (-1., 1.):
            edge = centres + side * (HALF_WIDTH * direction)
            fascia = []
            for a, b, ya, yb in zip(edge, edge[1:], heights, heights[1:]):
                fascia.append(M.quad([(a[0], ya, a[1]), (b[0], yb, b[1]),
                                      (b[0], yb-.22, b[1]), (a[0], ya-.22, a[1])], material='ferry_hull'))
            add(region, name + '_Fascia_' + str(int(direction)), M.merge(fascia, material='ferry_hull'))
        piles = []
        pile_stations = sorted(set(range(0, len(centres), 8)) | {len(centres)-1})
        for index in pile_stations:
            for direction in (-1., 1.):
                p = centres[index] + side * (1.48 * direction)
                bed = float(world.height_at(*p))
                top = float(heights[index]) + .85
                pile = M.box((.23, top-bed+.18, .23), center=(p[0], (top+bed-.18)*.5, p[1]), material='ferry_timber')
                piles.append(pile)
        add(region, name + '_PilesAndPosts', M.merge(piles, material='ferry_timber'))
        # A sign silhouette stays outside the clear 2.7m walking strip.
        p = centres[min(8, len(centres)-1)] + side * 2.0
        ground = float(world.height_at(*p))
        add(region, name + '_Signpost', M.box((.2, 2.35, .2), center=(p[0], ground+1.05, p[1]), material='ferry_timber'))
        add(region, name + '_FerrySign', oriented_box((1.35, .68, .16), (p[0], ground+2.05, p[1]), forward, 'ferry_trim'))
        for suffix, mesh in skiff_meshes(fit):
            add(region, name + '_Skiff_' + suffix, mesh)
        ropes = []
        for station, along_boat in ((len(centres)-1, 1.8),
                                   (min(pile_stations, key=lambda index: abs(index-(len(centres)-9))), -1.8)):
            dock = centres[station] + side * (1.48 * fit['mooringSide'])
            boat = fit['boatCenter'] + forward * along_boat - side * fit['mooringSide']
            ropes.append(mooring_rope((dock[0], heights[station]+.65, dock[1]),
                                       (boat[0], fit['waterLevel']+.48, boat[1])))
        add(region, name + '_MooringRopes', M.merge(ropes, material='ferry_trim'))
        reports.append({key: (value.tolist() if isinstance(value, np.ndarray) else value)
                        for key, value in fit.items() if key not in ('centres', 'heights', 'stations')})
        reports[-1]['connections'] = group['connections']
        reports[-1]['node'] = 'Walk_' + name
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    builder.write_glb(str(path))
    world.ferry_triangles = np.concatenate(walk_triangles) if walk_triangles else np.empty((0, 3, 3))
    world.ferry_report = dict(landings=reports, uniqueQuays=len(groups), ferryEnds=sum(len(c['regions']) for c in world.connections if c['type']=='ferry'),
                             maximumGrade=MAX_GRADE, policy='Actual frozen bank and wet boat footprint; no terrain or travel-contract movement.')
    return parts

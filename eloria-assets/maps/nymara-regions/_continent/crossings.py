"""Survey reciprocal territory gates in the single global coordinate system."""
from __future__ import annotations
import numpy as np

# A land crossing has been a gate: seven lanes about a surveyed anchor, with an
# authored threshold deck under them, and the rest of the border impassable
# however gentle the ground either side of it. A seam is crossed instead
# wherever the ground allows, which is every tile of the border a walker can
# stand on on both maps: its lanes come from the two served collision grids and
# its collar from the whole border (collision_export.seam_collar).
#
# Manymouth Delta to Verdant Stair was opened first, on its own, and went from
# seven lanes a side to 298 and 290 with no contract failing. A seam named here
# keeps only the seven lanes of its gate.
GATED_SEAMS = ()


def widened(identity):
    """Whether a land seam is crossed along its length or only at its gate."""
    return identity not in GATED_SEAMS


def tile_for(world, region, global_xz):
    origin, _ = world.address(region)
    p = np.asarray(global_xz) - world.regions[region]['center']
    return [int(np.floor(p[0] + origin[0])), int(np.floor(origin[1] - p[1]))]


def global_tile(world, region, tile):
    origin, _ = world.address(region)
    center = world.regions[region]['center']
    return np.array([tile[0] + .5 - origin[0] + center[0],
                     origin[1] - tile[1] - .5 + center[1]])


def tiles_at(world, region, gx, gz):
    """The tiles under global points, in one region's own tile frame.

    Every territory's tile grid is the same metre grid in the shared frame -
    the server origins are whole tiles and the translations whole metres - so
    this is exact, and the tile of one map that answers to a global point names
    the same ground as the tile of another map that answers to it.
    """
    origin, _ = world.address(region)
    center = world.regions[region]['center']
    return (np.rint(np.asarray(gx, dtype=float) - center[0] + origin[0] - .5).astype(int),
            np.rint(origin[1] + center[1] - np.asarray(gz, dtype=float) - .5).astype(int))


def seam_tiles(world, link, side):
    """The tiles either side of one border, in the near region's own tile frame.

    ``outward`` is the neighbour's first tile beyond the border and ``inward``
    the near territory's last tile inside it. A crossing is stood on the
    outward ring: a walker steps off their own ground onto the first tile of
    the neighbour's, and the portal under it hands them to the neighbour's map
    at that same cell - which is why a crossing moves nobody and needs no fade.
    Both rings are eight-connected because a walker's step is, so there is no
    tile beyond a border that can be reached without standing on a crossing.
    """
    from scipy.ndimage import binary_dilation
    region, other = link['regions'][side], link['regions'][1 - side]
    origin, cells = world.address(region)
    segments = np.asarray(link['edgeSegments'], dtype=float).reshape(-1, 2)
    low, high = segments.min(axis=0) - 4., segments.max(axis=0) + 4.
    x0, y1 = tiles_at(world, region, low[0], low[1])
    x1, y0 = tiles_at(world, region, high[0], high[1])
    xs = np.arange(max(0, int(x0)), min(int(cells[0]), int(x1) + 1))
    ys = np.arange(max(0, int(y0)), min(int(cells[1]), int(y1) + 1))
    if xs.size == 0 or ys.size == 0:
        return None
    tx, ty = np.meshgrid(xs, ys)
    gx = tx + .5 - origin[0] + world.regions[region]['center'][0]
    gz = origin[1] - ty - .5 + world.regions[region]['center'][1]
    owner = world.owner_at(gx, gz)
    mine, theirs = owner == world.ids.index(region), owner == world.ids.index(other)
    step = np.ones((3, 3), dtype=bool)
    return {'tx': tx, 'ty': ty, 'gx': gx, 'gz': gz,
            'outward': theirs & binary_dilation(mine, step),
            'inward': mine & binary_dilation(theirs, step)}


def own_ground(world, region, grid, arrival, reach):
    """A map's served grid, the tiles its territory owns, and what its hub reaches on them.

    ``reach(heights, start)`` is the server's own flood at the contract's climb
    limit (collision_sources.reachable_from). Every tile a neighbour owns is
    closed first: stepping onto one is a crossing, so ground this map reaches
    only through a neighbour's tiles is not reached at all - it is behind a
    border lane that fires first. Flooding through them, as the contract's own
    reachability does, took a strip of the neighbour for a corridor and found
    lanes no walker can step onto.
    """
    origin, _ = world.address(region)
    center = world.regions[region]['center']
    ys, xs = np.indices(grid.shape)
    mine = np.asarray(world.owner_at(xs + .5 - origin[0] + center[0], origin[1] - ys - .5 + center[1])) \
        == world.ids.index(region)
    return {'grid': grid, 'own': mine, 'reach': np.asarray(reach(np.where(mine, grid, 0), tuple(arrival)), dtype=bool)}


def crossing_lanes(world, link, side, served, step):
    """Every lane this border offers, by the server's own walking rules.

    ``served`` holds each map's ``own_ground``; ``step(heights, y, x, dy, dx)`` is
    the server's step test (collision_sources.walk_step_ok at the contract's
    climb limit). A lane is the neighbour's first tile across the border that a
    walker can step onto from ground their hub reaches without crossing, and
    whose cell the neighbour's hub reaches the same way; it is paired with the
    tile it is stepped onto from, where a walker arriving the other way lands.
    """
    rings = seam_tiles(world, link, side)
    region, other = link['regions'][side], link['regions'][1 - side]
    near, far = served.get(region), served.get(other)
    if rings is None or near is None or far is None:
        return []
    mask = rings['outward']
    tx, ty = rings['tx'][mask], rings['ty'][mask]
    ox, oy = tiles_at(world, other, rings['gx'][mask], rings['gz'][mask])
    rows, columns = near['grid'].shape
    far_rows, far_columns = far['grid'].shape
    lanes = []
    for x, y, fx, fy in zip(tx.tolist(), ty.tolist(), ox.tolist(), oy.tolist()):
        if not (0 <= fx < far_columns and 0 <= fy < far_rows) or not far['reach'][fy, fx]:
            continue
        # From each tile of this map's own reached ground beside it, straight
        # steps first so a straight seam pairs straight across.
        partners = [(x + dx, y + dy) for dx in (0, -1, 1) for dy in (0, -1, 1) if dx or dy
                    if 0 <= x + dx < columns and 0 <= y + dy < rows
                    and near['own'][y + dy, x + dx] and near['reach'][y + dy, x + dx]
                    and step(near['grid'], y + dy, x + dx, -dy, -dx)]
        if not partners:
            continue
        partner = min(partners, key=lambda t: (abs(t[0] - x) + abs(t[1] - y), t[1], t[0]))
        lanes.append({'tile': [x, y], 'arrival': [partner[0], partner[1]]})
    return lanes


def departs_outward(world, region, lane):
    """Whether a lane is stood on beyond its own territory, as a crossing must be.

    A gate's lanes are laid by geometry - seven offsets along the surveyed
    seam from its anchor - and where the ownership raster steps near the anchor
    one of them can land on its own map's side of the border. While that seam
    was nowhere else crossable it did no harm. Once the other map's lanes run
    the whole border, that tile is also the other map's first tile across, so
    each map would send a walker to the other from the one cell: the arrival
    would trigger the crossing back at once.
    """
    point = global_tile(world, region, lane['tile'])
    return int(np.asarray(world.owner_at(point[0], point[1]))) != world.ids.index(region)


def reseat(world, end):
    """Keep an end's own crossing - its tile, arrival and position - on one of its lanes.

    The end's tile is the gate's middle lane, and its position is where a
    client walking to the neighbour aims its first leg. When the border opens,
    the gate's lanes become the border lanes nearest them, so the end moves to
    the lane that now carries the gate's middle offset, or failing that the
    lane nearest where it stood.
    """
    if not end['lanes'] or any(lane['tile'] == end['tile'] and lane.get('gate') == 0 for lane in end['lanes']):
        return
    middle = [lane for lane in end['lanes'] if lane.get('gate') == 0]
    lane = middle[0] if middle else min(end['lanes'], key=lambda lane: (
        (lane['tile'][0] - end['tile'][0]) ** 2 + (lane['tile'][1] - end['tile'][1]) ** 2, lane['tile']))
    region = end['region']
    center = np.asarray(world.regions[region]['center'], dtype=float)
    point = global_tile(world, region, lane['tile'])
    end['tile'], end['arrival'] = list(lane['tile']), list(lane['arrival'])
    end['position'] = [float(point[0] - center[0]), float(world.height_at(*point)), float(point[1] - center[1])]


def widen_seams(world, connections, served, step, gated=None):
    """Give each open seam every lane its two maps' ground allows, and nothing else.

    Every published lane is a border lane (``crossing_lanes``): the neighbour's
    first tile across the border, stepped onto from ground this map's hub
    reaches without crossing. The gate's surveyed lanes are not kept for their
    own sake. The survey lays one side's on the second tile beyond the border,
    which a walker can only reach over the first - a border lane that fires
    before it - and where the ownership raster steps beside an anchor it lays
    others on the map's own side of the border (``departs_outward``) or where no
    step reaches them. The live proof walks every lane by the server's own
    rules and refused all of those. So each gate lane that is a border lane
    keeps its offset along the seam ('gate'), and each that is not hands its
    offset to the free border lane nearest it: the gate's walks still start at
    the gate. A seam whose border offers no lane at all keeps its gate as
    surveyed, where it has always worked.
    """
    report = []
    # A world with no surveyed links has no seam to widen: several contract tests
    # exercise the export against a stand-in that carries only what it reads.
    links = {link['id']: link for link in getattr(world, 'connections', ())}
    for connection in connections:
        if connection.get('type') != 'walk' or connection['id'] in (GATED_SEAMS if gated is None else gated):
            continue
        link = links[connection['id']]
        widths = []
        for side, end in enumerate(connection['ends']):
            border = {tuple(lane['tile']): lane for lane in crossing_lanes(world, link, side, served, step)}
            gate = [lane for lane in end['lanes'] if 'gate' in lane]
            if not border:
                widths.append({'region': end['region'], 'gateLanes': len(gate), 'gateLanesMoved': 0,
                               'lanes': len(end['lanes']), 'keptSurveyedGate': True})
                continue
            direct = [lane for lane in gate if tuple(lane['tile']) in border]
            for lane in direct:
                border[tuple(lane['tile'])]['gate'] = lane['gate']
            moved = 0
            for lane in gate:
                if tuple(lane['tile']) in border:
                    continue
                free = [key for key, candidate in border.items() if 'gate' not in candidate]
                if free:
                    key = tuple(lane['tile'])
                    nearest = min(free, key=lambda t: ((t[0] - key[0]) ** 2 + (t[1] - key[1]) ** 2, t))
                    border[nearest]['gate'] = lane['gate']
                    moved += 1
            end['lanes'] = [border[key] for key in sorted(border, key=lambda t: (t[1], t[0]))]
            reseat(world, end)
            widths.append({'region': end['region'], 'gateLanes': len(direct), 'gateLanesMoved': moved,
                           'lanes': len(border)})
        report.append({'id': connection['id'], 'ends': widths})
    return report


def frame_for(world, link, region, side):
    center = np.asarray(world.regions[region]['center'])
    anchor = np.asarray(link['anchor']); normal = np.asarray(link['normal']) * (1 if side == 0 else -1)
    height = float(world.height_at(*anchor))
    other = link['regions'][1-side]
    return {'id':link['id'], 'portal':'road-to-' + other, 'destination':other,
        'anchor':[float(anchor[0]-center[0]),height,float(anchor[1]-center[1])],
        'globalAnchor':[float(anchor[0]),height,float(anchor[1])],
        'globalTranslation':[float(center[0]),0,float(center[1])],
        'outward':normal.tolist(), 'uvSign':1, 'preloadDistance':320, 'retainDistance':420,
        'blendDistance':0, 'collarDepth':2, 'halfWidthTiles':3, 'viewHalfWidth':240,
        'viewDepth':320, 'geometryMode':'continent-chunks-v1', 'sceneNodes':[]}


def ferry_arrival(world, link, region, landing):
    """Return along the actual fitted bank, inside its four-metre quay apron."""
    landing=np.asarray(landing,dtype=float)
    fits=getattr(world,'ferry_shore_report',{}).get('finalFits',[])
    matches=[fit for fit in fits if fit.get('region')==region
        and link['id'] in fit.get('connections',[])
        and np.array_equal(np.asarray(fit.get('landing'),dtype=float),landing)]
    if len(matches)!=1:
        raise ValueError(f"{link['id']}:{region}: ferry arrival needs one exact final bank fit")
    forward=np.asarray(matches[0].get('forward'),dtype=float)
    if forward.shape!=(2,) or not np.isfinite(forward).all() or abs(np.linalg.norm(forward)-1)>1e-7:
        raise ValueError(f"{link['id']}:{region}: final bank direction must be a finite unit vector")
    # Rounding the full four-metre endpoint can put part of the actor beyond
    # the deck. One metre of margin keeps all four half-cells on the apron.
    arrival=tile_for(world,region,landing-forward*3)
    if arrival==tile_for(world,region,landing):
        raise ValueError(f"{link['id']}:{region}: ferry arrival overlaps its return trigger")
    return arrival


def prepare_contracts(world):
    """Same physical cell for departure/arrival; reverse triggers are across it."""
    connections=[]
    for link in world.connections:
        ends=[]
        for side,region in enumerate(link['regions']):
            other=link['regions'][1-side]; center=np.asarray(world.regions[region]['center'])
            if link['type']=='walk':
                anchor=np.asarray(link['anchor']);normal=np.asarray(link['normal'])*(1 if side==0 else -1)
                # A common global tangent keeps lane ordering stable on both ends.
                tangent=np.array([-link['normal'][1],link['normal'][0]])
                lanes=[]
                for offset in range(-3,4):
                    departure=tile_for(world,region,anchor+normal+offset*tangent)
                    arrival=tile_for(world,region,anchor-normal+offset*tangent)
                    # 'gate' is the lane's offset along the surveyed seam: what tells the gate's
                    # own lanes from the rest of an open border, and which of them is which.
                    lanes.append({'tile':departure,'arrival':arrival,'gate':offset})
                frame=frame_for(world,link,region,side)
                p=global_tile(world,region,lanes[3]['tile']);height=float(world.height_at(*p))
                edges=(np.asarray(link['edgeSegments'])-center).tolist()
                ends.append({'region':region,'portal':frame['portal'],**lanes[3], 'lanes':lanes,
                    'position':[float(p[0]-center[0]),height,float(p[1]-center[1])],
                    'frame':frame,'preloadEdges':edges})
            else:
                landing=np.asarray(link['landings'][side]); tile=tile_for(world,region,landing)
                p=global_tile(world,region,tile);height=float(world.height_at(*p))
                arrival=ferry_arrival(world,link,region,landing)
                ends.append({'region':region,'portal':'ferry-to-'+other,'tile':tile,'arrival':arrival,
                    'position':[float(p[0]-center[0]),height,float(p[1]-center[1])]})
        connections.append({'id':link['id'],'type':link['type'],'ends':ends})
    world.publication_connections=connections
    existing={tuple(sorted(c['regions'])) for c in world.connections if c['type']=='walk'}
    visuals=[]
    for (ia,ib),segments in world.adjacent_edges().items():
        ra,rb=world.ids[ia],world.ids[ib]
        if tuple(sorted((ra,rb))) in existing:continue
        mid=np.asarray(segments).mean(axis=(0,1));delta=world.centers[ib]-world.centers[ia]
        normal=delta/np.linalg.norm(delta)
        link={'id':'view--'+ra+'--'+rb,'anchor':mid.tolist(),'normal':normal.tolist(),'regions':[ra,rb]}
        ends=[]
        for side,region in enumerate((ra,rb)):
            center=np.asarray(world.regions[region]['center']);frame=frame_for(world,link,region,side)
            ends.append({'map':region,'portal':'','frame':frame,'position':frame['anchor'],
                'preloadEdges':(np.asarray(segments)-center).tolist()})
        visuals.append({'id':link['id'],'seamless':True,'visualOnly':True,'ends':ends})
    world.visual_connections=visuals
    return connections


def apply_manifest(world,region,manifest):
    for connection in world.publication_connections:
        end=next((e for e in connection['ends'] if e['region']==region),None)
        if end is None:continue
        other=next(e for e in connection['ends'] if e['region']!=region)
        portal={'id':end['portal'],'name':('Road to ' if connection['type']=='walk' else 'Ferry to ')+other['region'].replace('_',' ').title(),
            'position':end['position'],'serverTile':end['tile'],'destinationMap':other['region'],
            'destinationTile':other['arrival'],'type':connection['type']}
        manifest.setdefault('portals',[]).append(portal)
        if 'frame' in end:manifest.setdefault('streamingBorders',[]).append(end['frame'])

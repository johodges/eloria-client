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


def crossing_lanes(world, link, side, served):
    """Every lane this border offers: a tile a walker can stand on on both maps.

    ``served`` is each region's served tile grid as a boolean - the fold the
    server itself walks on, not the half-cell raster under it - so a lane
    exists exactly where both maps agree an actor may stand. Each lane pairs
    the tile it is stood on with the tile behind it that a walker arriving the
    other way lands on.
    """
    rings = seam_tiles(world, link, side)
    region, other = link['regions'][side], link['regions'][1 - side]
    near, far = served.get(region), served.get(other)
    if rings is None or near is None or far is None:
        return []

    def standing(mask):
        tx, ty = rings['tx'][mask], rings['ty'][mask]
        ox, oy = tiles_at(world, other, rings['gx'][mask], rings['gz'][mask])
        inside = ((tx >= 0) & (ty >= 0) & (tx < near.shape[1]) & (ty < near.shape[0])
                  & (ox >= 0) & (oy >= 0) & (ox < far.shape[1]) & (oy < far.shape[0]))
        tx, ty, ox, oy = tx[inside], ty[inside], ox[inside], oy[inside]
        both = near[ty, tx] & far[oy, ox]
        return tx[both], ty[both]

    departures = np.stack(standing(rings['outward']), axis=1)
    behind = {(int(x), int(y)) for x, y in np.stack(standing(rings['inward']), axis=1)}
    lanes = []
    for x, y in departures.tolist():
        # The tile a walker coming the other way lands on: the nearest ground
        # of this territory behind the crossing, sideways steps last so a
        # straight seam pairs straight across. A crossing with none behind it
        # is ground nobody can have walked from and is no lane at all.
        partners = [(x + dx, y + dy) for dx in (0, -1, 1) for dy in (0, -1, 1)
                    if (x + dx, y + dy) in behind]
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
    client walking to the neighbour aims its first leg. A gate lane that
    departed from its own side of the border is dropped, and when that is the
    middle one the end would send a walker to a tile that no longer crosses
    anything; the lane nearest it takes its place.
    """
    if not end['lanes'] or any(lane['tile'] == end['tile'] for lane in end['lanes']):
        return
    lane = min(end['lanes'], key=lambda lane: ((lane['tile'][0] - end['tile'][0]) ** 2
                                               + (lane['tile'][1] - end['tile'][1]) ** 2, lane['tile']))
    region = end['region']
    center = np.asarray(world.regions[region]['center'], dtype=float)
    point = global_tile(world, region, lane['tile'])
    end['tile'], end['arrival'] = list(lane['tile']), list(lane['arrival'])
    end['position'] = [float(point[0] - center[0]), float(world.height_at(*point)), float(point[1] - center[1])]


def widen_seams(world, connections, served, gated=None):
    """Give each open seam every lane its two served grids allow.

    The gate's own lanes are kept whatever the grids say - they stand on an
    authored threshold deck, so a widened seam can only gain ways across - but
    not one that departs from its own map's ground (``departs_outward``): no
    departure is ever owned by the map it departs from, which is what keeps
    every arrival clear of the crossing back.
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
            kept = [lane for lane in end['lanes'] if departs_outward(world, end['region'], lane)]
            lanes = {tuple(lane['tile']): lane for lane in kept}
            for lane in crossing_lanes(world, link, side, served):
                lanes.setdefault(tuple(lane['tile']), lane)
            inside = len(end['lanes']) - len(kept)
            end['lanes'] = [lanes[key] for key in sorted(lanes, key=lambda t: (t[1], t[0]))]
            reseat(world, end)
            widths.append({'region': end['region'], 'gateLanes': len(kept), 'gateLanesInside': inside,
                           'lanes': len(lanes)})
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

"""Survey reciprocal territory gates in the single global coordinate system."""
from __future__ import annotations
import numpy as np


def tile_for(world, region, global_xz):
    origin, _ = world.address(region)
    p = np.asarray(global_xz) - world.regions[region]['center']
    return [int(np.floor(p[0] + origin[0])), int(np.floor(origin[1] - p[1]))]


def global_tile(world, region, tile):
    origin, _ = world.address(region)
    center = world.regions[region]['center']
    return np.array([tile[0] + .5 - origin[0] + center[0],
                     origin[1] - tile[1] - .5 + center[1]])


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
                    lanes.append({'tile':departure,'arrival':arrival})
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

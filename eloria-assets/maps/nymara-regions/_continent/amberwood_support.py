"""Authored dry approaches around Amberwood's retained tree and hillside workyards.

These are visible earth roads with local cut/fill and broad shoulders. The
canopy compound, kiln buildings and authored discovery identities stay fixed.
"""
from __future__ import annotations
import numpy as np
import landscape as L
from world_layout import corridor_grade,graded_profile
from four_gates_support import path_field

REGION='amberwood'
# Routed branches graded as approaches (approach name -> road id). The ridge
# camp's discovery branch (maps.txt 473, the boar-run door) climbs the
# plateau's north feather from whichever public road stands nearest. The
# shared road solve holds a footing feather at its blended ground, so the
# branch climbed it at 1.1-1.4 once the terrain terms took the seam and door
# roads off the ridge (the fifteenth's three roads had graded that hillside
# together); its bed is one authored earth surface here like the paths above.
APPROACH_BRANCHES={'amber-ridge-camp-branch':'discovery-amberwood-473'}
APPROACH_GRADE=.45


def branch_routes(world):
    """The routed branches graded as approaches, by approach name, as XZ stations."""
    routes={}
    for name,road_id in APPROACH_BRANCHES.items():
        road=next((r for r in world.roads if r['id']==road_id),None)
        if road is None:raise ValueError(f'{name}: branch {road_id} was not routed')
        routes[name]=np.asarray(road['points'],float)[:,[0,2]]
    return routes


def branch_profile(levels,stations,maximum_grade=APPROACH_GRADE):
    """A routed branch keeps its ends and its general rise; the feather step is cut and filled to the grade."""
    return graded_profile(levels,stations,maximum_grade=maximum_grade)


def authored_routes(world):
    offset=np.asarray(world.regions[REGION]['center'])-[510.,540.]
    return {
        'amber-side-kilnyard':np.array([[638,613],[634,617],[630,624],[629,634]],float)+offset,
        'amber-chapel-climb':np.array([[626,491],[634,491],[641,494],[646,503],[654,510],[663,511],[666,509]],float)+offset,
        'amber-motherroot-yard':np.array([[510,522],[510,517],[512,513]],float)+offset,
        'amber-moot-path':np.array([[496,500],[495,505],[500,508],[503,504]],float)+offset,
        'amber-ridge-camp':np.array([[604,435],[605,445],[599,452],[591,456],[584,456],[578,450]],float)+offset,
        # The undercut path bends east between the two ruins (33.8 m, end-to-end
        # grade .45): with the structures registered where they stand
        # (content.register_obstacles) the cinder chapel door road takes its direct
        # line up the hill and the chapel foot at (626, 491) lies 26 m lower than
        # the fourteenth left it; the former 28 m line climbed at .54.
        'amber-undercut-path':np.array([[626,491],[634,491],[641,487],[647,486],[650,481],[647,476]],float)+offset,
    }


def prepare_amberwood_routes(world,content):
    """Add the alternate workyard approaches before the shared road grade solve."""
    if REGION not in world.ids:return {}
    paths=authored_routes(world)
    for name,path in paths.items():
        if any(r['id']==name for r in world.roads):raise ValueError('Amber approaches were already prepared')
        world.add_road(path,width=2.2,name=name)
    return {'roads':list(paths)}


def apply_amberwood_support(world,content):
    if REGION not in world.ids:return {}
    rows=[]
    for name,points in list(authored_routes(world).items())+list(branch_routes(world).items()):
        # Final road ends join the actual current earth, not a cached camera Y.
        levels=world.height_at(points[:,0],points[:,1])
        stations=np.r_[0,np.cumsum(np.linalg.norm(np.diff(points,axis=0),axis=1))]
        branch=name in APPROACH_BRANCHES
        profile=branch_profile(levels,stations) if branch else np.interp(stations,[0,stations[-1]],[levels[0],levels[-1]])
        if abs(levels[-1]-levels[0])/stations[-1]>(APPROACH_GRADE if branch else .48):
            raise ValueError(f'{name}: authored climb must be lengthened')
        half_width=3.6;shoulder=10.
        low=points.min(axis=0)-half_width-shoulder;high=points.max(axis=0)+half_width+shoulder
        ix0,iz0=np.maximum(0,np.floor((low-[world.x0,world.z0])/2).astype(int))
        ix1,iz1=np.minimum([len(world.x),len(world.z)],np.ceil((high-[world.x0,world.z0])/2).astype(int)+1)
        sl=np.s_[iz0:iz1,ix0:ix1];gx,gz=world.gx[sl],world.gz[sl]
        target,distance,along,length=path_field(points,profile,gx,gz)
        active=distance<=half_width
        target=corridor_grade(target,active,maximum_grade=.45)
        weight=(1-L.smoothstep(half_width,half_width+shoulder,distance))
        weight*=~world.water['mask'][sl]
        weight*=world.owner_at(gx,gz)==world.ids.index(REGION)
        # Architectural interiors keep their foundation. The Motherroot's
        # surface roots remain visible outside the small worn path opening.
        occupied=np.zeros_like(weight,dtype=bool)
        for obj in content.objects:
            if obj['region']!=REGION or not obj.get('collides') or obj.get('assembly'):continue
            if obj['node'].startswith(('Stone_RuinFragment','LogPile_','Cart_')):continue
            if obj.get('kind') in ('tree','rock','foliage','undergrowth','scrub'):continue
            a,b=obj['low'],obj['high']
            occupied|=(gx>=a[0]-.25)&(gx<=b[0]+.25)&(gz>=a[2]-.25)&(gz<=b[2]+.25)
        weight*=~occupied
        # Routed roads crossing an approach are regraded with it: the approach
        # is one authored earth surface and the corridors it crosses become
        # part of it. Two guards were tried in the fifteenth publication and
        # each stepped a served corridor at the crossing (excluding the other
        # road's core cut the ridge camp approach at its own stations; blending
        # into the core made the kilnyard yard steep beside the Hamlet Elder).
        old=world.height[sl].copy();new=old*(1-weight)+target*weight
        world.height[sl]=new
        rows.append({'road':name,'lengthMetres':float(length),'changedVertices':int(np.count_nonzero(abs(new-old)>1e-8)),
                     'maximumCut':float(np.max(old-new,initial=0)),'maximumFill':float(np.max(new-old,initial=0))})
        road=next((r for r in world.roads if r['id']==APPROACH_BRANCHES.get(name,name)),None)
        if road is not None:
            p=np.asarray(road['points']);p[:,1]=world.height_at(p[:,0],p[:,2]);road['points']=p.tolist()
    world.amberwood_support={'approaches':rows}
    from amberwood_access import refresh_amberwood_access_heights
    refresh_amberwood_access_heights(world,content)
    return world.amberwood_support

"""Authored dry approaches around Amberwood's retained tree and hillside workyards.

These are visible earth roads with local cut/fill and broad shoulders. The
canopy compound, kiln buildings and authored discovery identities stay fixed.
"""
from __future__ import annotations
import numpy as np
import landscape as L
from world_layout import corridor_grade
from four_gates_support import path_field

REGION='amberwood'


def authored_routes(world):
    offset=np.asarray(world.regions[REGION]['center'])-[510.,540.]
    return {
        'amber-side-kilnyard':np.array([[638,613],[634,617],[630,624],[629,634]],float)+offset,
        'amber-chapel-climb':np.array([[626,491],[634,491],[641,494],[646,503],[654,510],[663,511],[666,509]],float)+offset,
        'amber-motherroot-yard':np.array([[510,522],[510,517],[512,513]],float)+offset,
        'amber-moot-path':np.array([[496,500],[495,505],[500,508],[503,504]],float)+offset,
        'amber-ridge-camp':np.array([[604,435],[605,445],[599,452],[591,456],[584,456],[578,450]],float)+offset,
        'amber-undercut-path':np.array([[626,491],[634,491],[640,485],[646,480],[647,476]],float)+offset,
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
    for name,points in authored_routes(world).items():
        # Final road ends join the actual current earth, not a cached camera Y.
        levels=world.height_at(points[:,0],points[:,1])
        stations=np.r_[0,np.cumsum(np.linalg.norm(np.diff(points,axis=0),axis=1))]
        profile=np.interp(stations,[0,stations[-1]],[levels[0],levels[-1]])
        if abs(levels[-1]-levels[0])/stations[-1]>.48:
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
        old=world.height[sl].copy();new=old*(1-weight)+target*weight
        world.height[sl]=new
        rows.append({'road':name,'lengthMetres':float(length),'changedVertices':int(np.count_nonzero(abs(new-old)>1e-8)),
                     'maximumCut':float(np.max(old-new,initial=0)),'maximumFill':float(np.max(new-old,initial=0))})
        road=next((r for r in world.roads if r['id']==name),None)
        if road is not None:
            p=np.asarray(road['points']);p[:,1]=world.height_at(p[:,0],p[:,2]);road['points']=p.tolist()
    world.amberwood_support={'approaches':rows}
    from amberwood_access import refresh_amberwood_access_heights
    refresh_amberwood_access_heights(world,content)
    return world.amberwood_support

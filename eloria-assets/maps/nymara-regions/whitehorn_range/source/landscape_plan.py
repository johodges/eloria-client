"""Compact Whitehorn: sheltered lower valleys below an exposed glacial crown."""
from pathlib import Path
from copy import deepcopy
import math
import numpy as np
from amberwood import terrain as TER, landscape as LAND, noise as N
from amberwood import routecraft as RC, props as P
from compact_landscape import Axis, CompactLandscape
from border_vistas import add_vista
from regionbuild import Placement
import region as REG
import layout

SERVER_CELLS=396
SERVER_ORIGIN=(120.0,120.0)
PLAY_MIN_X,PLAY_MAX_X=-120.0,275.0
PLAY_MIN_Z,PLAY_MAX_Z=-275.0,120.0
PLAN=CompactLandscape(Axis(-174,402,-120,276,(-45,120)),
                      Axis(-402,174,-276,120,(-110,100)),
                      REG.SERVER_ORIGIN,SERVER_ORIGIN)
GROUND={TER.PATH:'alpine_gravel',TER.PAVING:'alpine_gravel',
        TER.SNOW:'alpine_snowfield',TER.ICE:'alpine_blue_ice',TER.ROCK:'alpine_bedrock'}
PALETTE={'snow_pack':'alpine_snowfield','glacier_ice':'alpine_blue_ice'}
BORDER_ROADS={
 'amber_saddle':([(-112,-42),(-138,-36),(-162,-36),(-180,-36),(-212,-35)],
                 [31,35,36,36,34],6),
 'southern_descent':([(-12,89),(-6,126),(0,153),(0,175),(2,208)],
                     [19.66,15,12,11,9],7),
 'barrens_saddle':([(330,-18),(361,-15),(382,-12),(404,-12),(434,-14)],
                   [37.35,36,36,36,35],7),
}


def prepare(t,seed):
    # The adit enters the mountain's shoulder behind its mouth.
    dx,dz=t.gx-288,t.gz+138
    along=dx*.759-dz*.651;across=abs(dx*.651+dz*.759)
    mound=LAND.smoothstep(1,8,along)*(1-LAND.smoothstep(7,23,across))*(1-LAND.smoothstep(20,55,along))
    t.height=np.where(mound>0,np.maximum(t.height,50.33+12*mound),t.height)
    t.surface[(mound>.25)]=TER.ROCK
    t.tree_block|=mound>.1
    # Icefalls belong to two shelf edges beside the pilgrim trail. The frozen
    # pools meet the ground; the lips enter the uphill rock shoulder.
    t.cascade_sites={'frozen_falls':(95,-184,34), 'upper_falls':(131,-226,51)}
    for x,z,y in t.cascade_sites.values():
        distance=np.hypot(t.gx-x,t.gz-z)
        LAND.feather_level(t,distance-7,y,shoulder=9)
        t.surface[distance<7]=TER.ICE;t.tree_block|=distance<12
        back=LAND.smoothstep(1,8,z-t.gz)*(1-LAND.smoothstep(8,22,abs(t.gx-x)))*(1-LAND.smoothstep(18,38,z-t.gz))
        t.height=np.where(back>0,np.maximum(t.height,y+20*back),t.height)
        t.surface[back>.2]=TER.ROCK;t.tree_block|=back>.1
    # Long, open pastures lie in the lower glacial valley, not at every POI.
    mask=np.zeros_like(t.height)
    wobble=(N.value_noise(t.gx/26,t.gz/26,seed+120)-.5)*.25
    for x,z,rx,rz in [(-75,42,38,32),(95,82,37,28),(228,57,32,23)]:
        r=np.hypot((t.gx-x)/rx,(t.gz-z)/rz)+wobble
        mask=np.maximum(mask,1-LAND.smoothstep(.6,1.2,r))
    natural=np.isin(t.surface,[TER.SNOW,TER.TURF])
    t.surface[natural & (mask>.42) & (t.height<42)] = TER.TURF
    t.tree_block |= mask>.72
    t.alpine_open=mask
    for name,(points,heights,width) in BORDER_ROADS.items():
        RC.grade_road(t,points,heights,width=width,shoulder=34,
                      surface=TER.PATH,clearance=6)
    # Remove the old 15 m pass cut's painted apron. The cut remains a broad
    # saddle, but only the travelled strip reads as road.
    for points,heights,width in BORDER_ROADS.values():
        d=LAND.distance_field(t,[points])
        shoulder=(d>width*.65)&(d<34)&(t.surface==TER.PATH)
        t.surface[shoulder]=TER.TURF
    # A usable measuring station beside the snowline path, large enough for
    # a traveller to stop without standing in its neighbouring stone markers.
    RC.grade_road(t,[(190,-146),(197,-146)],[55,55],width=12,shoulder=10,
                  surface=TER.PATH,clearance=6)
    # The two refuge fronts share one court. Grey gravel is ordinary working
    # ground; marble remains reserved for the temple and formal shrines.
    court=(t.gx>-38)&(t.gx<16)&(t.gz>56)&(t.gz<81)
    t.height[court]=19.66;t.surface[court]=TER.PAVING;t.surface_strength[court]=1
    t.tree_block|=court
    for name,(points,heights,width) in layout.ROADS.items():
        if name=='gate_court':continue
        LAND.worn_path(t,points,min(width,4.8),seed+N.stable_hash(name)%997)
    # No random vegetation lottery on every eligible square: conifers collect
    # on sheltered lee slopes, leaving grazing shelves open.
    g,_,_=LAND.grove_density(t,list(REG.ROUTES.values())+
        [v[0] for v in layout.ROADS.values()],list(REG.STREAMS.values()),seed,
        open_ground=mask)
    t.alpine_density=g*(1-LAND.smoothstep(32,52,t.height))


def dress(build,seed):
    t=build.terrain
    # Fuel and stores belong against refuge walls; four compact sledges make
    # the mine a freight destination. Existing services and entrances stay put.
    for i,(x,z) in enumerate([(-31,60),(-23,60),(5,60),(12,60)]):
        item=P.barrel(seed=seed+i) if i%2 else P.crate(seed=seed+i)
        key=f'Prop_RefugeStores_{i}'
        build.add_mesh(key,item)
        build.place(Placement(key,key,(x,float(t.height_at(x,z)),z),.13*i))
    # Debris follows three exposed shoulders instead of covering all snow.
    keep=[]
    for p in build.placements:
        if p.node.startswith('Prop_rocks_'):
            x,_,z=p.position
            relation=min(np.hypot((x-a)/rx,(z-b)/rz) for a,b,rx,rz in
                [(-90,-180,55,100),(291,-195,60,115),(216,2,66,36)])
            if relation>1.1:continue
        keep.append(p)
    build.placements[:]=keep
    for item in build.meshes.values():
        for part in getattr(item,'all_parts',[item]):
            part.material=PALETTE.get(part.material,part.material)


def compact(build):
    # Both rope bridges are MeshGroups whose authored walking parts must
    # follow the bank survey. Their rails keep the same transformed frame.
    for p in build.placements:
        if p.node.startswith('Landmark_rope_bridge_'):p.walk_surface=True
    PLAN.apply(build)
    lines=[np.asarray([[float(PLAN.x(x)),float(PLAN.z(z))] for x,z in pts])
           for pts in list(REG.ROUTES.values())+[v[0] for v in layout.ROADS.values()]+
           [v[0] for v in BORDER_ROADS.values()]]
    from amberwood.terrain import _polyline_distance
    x=np.asarray([p.position[0] for p in build.placements]);z=np.asarray([p.position[2] for p in build.placements])
    distance=np.full(x.shape,np.inf)
    for line in lines:distance=np.minimum(distance,_polyline_distance(x,z,line)[0])
    build.placements[:]=[p for p,d in zip(build.placements,distance)
        if p.kind not in ('tree','foliage','rock') or d>(6 if p.kind in ('tree','foliage') else 2.2)]
    # Unscaled crowns need room after travel space contracts. Keep irregular
    # groves while removing crowns that would interpenetrate coplanar layers.
    trees=[];kept=[]
    for p in build.placements:
        if p.kind=='tree':
            low,high=build.meshes[p.mesh].bounds()
            radius=max(abs(low[0]),abs(high[0]),abs(low[2]),abs(high[2]))*p.scale
            x,_,z=p.position
            if any(math.hypot(x-a,z-b)<.88*(radius+r) for a,b,r in trees):continue
            trees.append((x,z,radius))
        kept.append(p)
    build.placements[:]=kept
    removed={p.node for p in build.placements if p.node.startswith('March_') and
             (p.node.endswith('_Stone') or '_Furniture_' in p.node)}
    build.placements[:]=[p for p in build.placements if p.node not in removed]
    for l in build.landmarks:
        if l.get('node') in removed:l['node']=l['node'].replace('_Stone','_Signpost')
    used={p.mesh for p in build.placements}
    build.meshes={k:v for k,v in build.meshes.items() if k in used}
    build.border_vistas=[]
    root=Path(__file__).resolve().parents[2]
    for region,portal,edge,forward,inward,material in [
        ('mirrorhold','north-pass',(float(PLAN.x(0)),122),(0,1),(0,1),'alpine_turf'),
        ('amethyst_barrens','north-pass',(277,float(PLAN.z(-12))),(1,0),(0,1),'alpine_bedrock')]:
        build.border_vistas.append(add_vista(build,root/region,portal,edge,forward,inward,material,region))
    from streaming_borders import apply as stitch_border
    stitch_border(build, 'whitehorn_range')


def content_layout():
    result=PLAN.metadata(deepcopy(layout.CONTENT_LAYOUT))
    result['npcs']={name:PLAN.point(p) for name,p in layout.CONTENT_LAYOUT['npcs'].items()}
    for category in ('harvest','wildlife'):
        result[category]={name:[[float(PLAN.x(x)),float(PLAN.z(z)),r*.68] for x,z,r in patches]
                          for name,patches in layout.CONTENT_LAYOUT[category].items()}
    return result


def roads():
    return [{'id':name,'width':width,'waypoints':[PLAN.point([x,y,z])
             for (x,z),y in zip(pts,heights)]}
            for name,(pts,heights,width) in (layout.ROADS|BORDER_ROADS).items()]


def block_walls(blockers,gx,gz):
    for name,(x,z),w,d,angle,y in layout.SHELTERS:
        dx,dz=gx-float(PLAN.x(x)),gz-float(PLAN.z(z))
        lx=dx*math.cos(angle)-dz*math.sin(angle);lz=dx*math.sin(angle)+dz*math.cos(angle)
        blockers|=(abs(lx)<w/2+.3)&(abs(lz+d/2)<.55)
        blockers|=(abs(abs(lx)-(w/2-.24))<.55)&(abs(lz-.03)<(d-.54)/2+.3)

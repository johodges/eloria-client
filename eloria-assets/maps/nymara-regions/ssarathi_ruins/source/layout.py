"""The inhabited quay, working docks and surveyed crossings of the drowned city."""
from __future__ import annotations
import math
import numpy as np
from amberwood import routecraft as RC, civiccraft as CIV, props as PROP
from amberwood import terrain as TER
import region as REG
import ssarathikit as SK

CISTERN = (-102.0, -60.0)
CISTERN_DOOR = (-97.0, -60.0)
FERRY = (8.0, 99.0)
FERRY_STATION = (8.0, 132.0)
CONTENT_LAYOUT = {
    "services": [
        {"role":"information","position":[0,1.45,6]},
        {"role":"storage","position":[-9,1.45,-3]},
        {"role":"crafting_station","position":[9,1.45,-3]},
        {"role":"training","position":[12,1.45,7]}],
    "roadClearance": 3.0,
    "npcs": {
        "Archivist Sesh":[-8,1.45,5], "Vess Scale":[-11,1.45,-7],
        "Sun-Vault Warden Hass-Ile":[49,13,-199],
        "Lineage Reader Ssiran-Ta":[69,2,-22],
        "Hatchery Keeper Nuu-Sesh":[176,2,-116],
        "Cistern Sounder Vek-Ora":[-98,2,-63],
        "Stela Copyist Ilhu-Ren":[194,14,-198],
        "Water-Gate Marshal Set-Kaal":[8,1.25,132],
        "Lily Court Steward Aa-Nesh":[-34,2,-58],
        "Marchstone Priest Osu-Val":[294,1.8,-125],
        "Undercroft Digger Rell Marrow":[215,3,78],
        "Falls Measurer Ith-Anu":[280,4,-317],
        "Coil Bridge Toll-Taker Ude-Sar":[70,1.8,-75],
        "Ssethis the Doorkeeper":[73,2,49]},
    "wildlife": {
        "canopy_glider":[[221,69,28],[307,-119,26]],
        "swamp_heron":[[-45,-60,22],[181,-39,24]],
        "delta_mud_crab":[[-62,40,24],[240,-12,24]],
        "scalevine_stalker":[[231,68,26],[-129,-160,26]],
        "saltmarsh_crocodile":[[281,-61,24],[-102,-91,28]],
        "sunscale_basilisk":[[187,-189,26],[124,-268,26]],
        "rune_stone_golem":[[-66,-220,28],[135,-279,28]],
        "void_tentacle_construct":[[-113,-173,27],[97,-273,28]],
        "gloom_wyvern":[[-9,-259,50],[-131,-293,35],[101,-257,37]],
        "emerald_canopy_dragon":[[-7,-257,45],[112,-278,40],[360,-91,38]]},
    "harvest": {
        "Lichen":[[-45,-62,22],[183,-42,23]],
        "Lotus":[[172,-49,20]],
        "Watercress":[[-39,-62,22]],
        "Venom Bulb":[[223,74,24]],
        "Toadstool":[[307,-132,25]],
        "Geode":[[189,-197,24]],
        "Flint":[[-105,-158,22]]},
}

def dock_routes():
    routes = {}
    for i,z in enumerate((-25.,-18.,-11.)):
        routes[f"east_dock_{i}"] = ([(264.,z),(286.,z)], 3.4)
    for i,z in enumerate((39.,44.,49.)):
        routes[f"west_dock_{i}"] = ([(-78.,z),(-62.,z)], 3.2)
    for i,x in enumerate((8.,30.)):
        routes[f"south_dock_{i}"] = ([(x,123.),(x,97.)], 3.6)
    return routes

def prepare(t):
    # Keep the arrival's service floor open, with its exit aimed at the axis.
    RC.grade_road(t,[(-17,-3),(17,-3)],[1.45,1.45],width=20,shoulder=2,
                  surface=REG.JADE_PAVING,clearance=3)
    # The old market scatter put stalls across both approaches. Its two rows
    # are placed on this court, leaving a central aisle and cross aisle.
    RC.grade_road(t,[(179,12),(217,12)],[1.9,1.9],width=28,shoulder=3,
                  surface=REG.JADE_PAVING,clearance=3)
    t._survey = {}
    for span in REG.bridge_spans():
        c=np.asarray(span["centre"]);d=np.asarray(span["heading"])
        pts=np.array([c-d*(span["half_span"]+1.0),c+d*(span["half_span"]+1.0)])
        hs=[max(REG.DECK,float(t.height_at(*p)))+0.22 for p in pts]
        t._survey[span["name"]]=(pts,hs,span["half_width"]*2,"stone")
    for name,(pts,width) in dock_routes().items():
        pts=np.asarray(pts)
        t._survey[name]=(pts,[max(1.25,float(t.height_at(*pts[0])))+0.22,1.2],width,"wood")
    t._survey["cistern_walk"]=(np.array([[-38.,-60.],[-96.,-60.]]),[2.25,2.0],3.4,"wood")
    # Every deck has a recessed bed and a short shore landing. The wet end of
    # a jetty remains water: land is never raised to manufacture access.
    for name,(pts,hs,width,kind) in t._survey.items():
        a,b=pts;run=b-a;length=float(np.linalg.norm(run));d=run/length
        for p,h,sign in ((a,hs[0],-1),(b,hs[1],1)):
            if kind=="wood" and sign==1:continue
            back=p+d*sign*6
            RC.grade_road(t,[back,p],[max(1.2,float(t.height_at(*back))),h-0.2],
                          width=width+1,shoulder=2.5,surface=REG.JADE_PAVING,clearance=2)
        u=((t.gx-a[0])*run[0]+(t.gz-a[1])*run[1])/length**2
        v=np.abs((t.gx-a[0])*run[1]-(t.gz-a[1])*run[0])/length
        mask=(u>=-2/length)&(u<=1+2/length)&(v<width/2+2)
        t.height=np.where(mask,np.minimum(t.height,hs[0]+(hs[1]-hs[0])*u-0.22),t.height)
        t.tree_block|=mask
    t.mark_blocked_disc(CISTERN,9)

def dress_crossings(build,seed):
    import populate as POP
    for name,(pts,hs,width,kind) in build.terrain._survey.items():
        a,b=pts;length=float(np.linalg.norm(b-a))
        if kind=="stone":
            mesh=CIV.arcaded_causeway(length,*hs,width=width,arches=3,foot=-7,
                       stone=SK.JADE_ASHLAR,paving=SK.JADE_PAVING,trim=SK.JADE_SCALE)
            angle=math.atan2(-(b[1]-a[1]),b[0]-a[0])
            node="Bridge_"+name
        else:
            mesh=CIV.sloped_boardwalk(length,*hs,width=width,foot=-7,
                                     timber=SK.TIMBER,rope=SK.TIMBER)
            mesh.translate(0,0,-length/2)
            angle=math.atan2(b[0]-a[0],b[1]-a[1]);node="Dock_"+name
        POP._add(build,node,node,mesh,(float((a+b)[0]/2),0,float((a+b)[1]/2)),
                 angle,kind="structure")
        build.crossings.append({"id":name,"endpoints":RC.crossing_endpoints(
            [[float(a[0]),hs[0],float(a[1])],[float(b[0]),hs[1],float(b[1])]])})
        if name=="great_causeway__channel_main":
            build.landmarks.append({"id":"channel-bridge","name":"The Coil Bridge",
               "node":node,"type":"bridge","position":[float((a+b)[0]/2),sum(hs)/2,float((a+b)[1]/2)]})

def dress(build,seed):
    import populate as POP
    t=build.terrain
    for i,x in enumerate((-9.,9.)):
        mesh=CIV.market_shelter(width=12,depth=5,stone=SK.JADE_ASHLAR,
                                timber=SK.TIMBER,roof=SK.CANVAS)
        POP._add(build,f"QuayShelter_{i}","QuayShelter",mesh,(x,1.45,-6),kind="structure")
    build.landmarks.append({"id":"arrival-exchange","name":"Archive Supply Quay",
         "node":"QuayShelter_0","type":"market","position":[0,1.45,-3]})
    for i,(x,z,angle) in enumerate([(291,-18,0),(-58,44,0),(3,101,math.pi/2)]):
        POP._add(build,f"MooredPunt_{i}","MooredPunt",
                 PROP.rowing_boat(length=5.5,beam_width=1.8,seed=seed+3400),
                 (x,0.03,z),angle,kind="prop")
    for i,(x,z) in enumerate([(-16,-6),(-16,-4),(17,-8),(247,-13),(247,-11),(13,132)]):
        POP._add(build,f"QuayCargo_{i}","QuayCargo",
                 PROP.crate(size=0.9,seed=seed+3500),(x,float(t.height_at(x,z)),z),
                 kind="prop",collides=True)
    build.notes.append("Archive supply quay, aligned market rows, five surveyed channel bridges and eight working jetties.")

def dress_cistern(build,seed):
    import populate as POP
    mesh=CIV.sounding_stage(stone=SK.JADE_ASHLAR,timber=SK.TIMBER,foot=-5)
    placed=POP._add(build,"CisternShaft","CisternShaft",mesh,(-102,2.0,-60),
             kind="landmark",collides=True,landmark="cistern-shaft")
    placed.extras={"solidRadius":2.2}

def clear_routes(build):
    lines=[[[float(x),0,float(z)] for x,z in points]
           for points in REG.street_routes().values()]
    lines += [[[float(x),0,float(z)] for x,z in data[0]] for data in build.terrain._survey.values()]
    RC.clear_walk_corridors(build,lines,{"tree":5.0,"foliage":4.5,"prop":2.5})
    # Old street kerbs used to divide both working courts, and some ruin
    # blocks were generated across the newly surveyed water routes.
    kept=[];removed=[]
    wet=[(np.asarray(v[0]),v[2]) for v in build.terrain._survey.values() if v[3]=="wood"]
    for p in build.placements:
        discard=False
        if p.node.startswith("Kerb_") or p.mesh.startswith(("RuinBuilding_","RuinTower_")):
            low,high=build.meshes[p.mesh].bounds();c,s=math.cos(p.rotation_y),math.sin(p.rotation_y)
            corners=np.array([(p.position[0]+p.scale*(c*x+s*z),p.position[2]+p.scale*(-s*x+c*z))
                              for x in (low[0],high[0]) for z in (low[2],high[2])])
            lo,hi=corners.min(axis=0),corners.max(axis=0)
            if p.node.startswith("Kerb_"):
                for x0,x1,z0,z1 in [(-24,25,-14,15),(175,222,-5,29)]:
                    discard |= lo[0]<x1 and hi[0]>x0 and lo[1]<z1 and hi[1]>z0
            else:
                centre=(lo+hi)/2;radius=float(np.linalg.norm(hi-lo))/2
                for points,width in wet:
                    a,b=points;d=b-a;u=np.clip(np.dot(centre-a,d)/np.dot(d,d),0,1)
                    discard |= np.linalg.norm(centre-(a+u*d))<radius+width/2+1.5
        if p.kind=="prop" and not p.node.startswith("QuayCargo"):
            x,_,z=p.position
            discard |= (-21<x<21 and -13<z<12) or (177<x<220 and 8<z<16)
        if discard:removed.append(p.node)
        else:kept.append(p)
    build.placements=kept
    build.notes.append("Cleared quay, market and jetty conflicts: "+", ".join(removed))

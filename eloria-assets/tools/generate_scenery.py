#!/usr/bin/env python3
"""Generate original native-E3D scenery and harvestable models for Emberhaven."""
from __future__ import annotations
import argparse, hashlib, math, struct
from pathlib import Path
from generate_bootstrap_pack import png

Vertex = tuple[float,float,float,float,float,float,float,float]

def face(vertices, indices, points, normal):
    base=len(vertices)
    for (x,y,z),(u,v) in zip(points,((0,0),(1,0),(1,1),(0,1))):
        vertices.append((u,v,*normal,x,y,z))
    indices.extend((base,base+1,base+2,base,base+2,base+3))

def box(vertices,indices,c,size):
    cx,cy,cz=c; sx,sy,sz=(q/2 for q in size)
    p=[(cx+x*sx,cy+y*sy,cz+z*sz) for x,y,z in ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1))]
    for q,n in zip(((0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(4,0,3,7)),((0,0,-1),(0,0,1),(0,-1,0),(1,0,0),(0,1,0),(-1,0,0))): face(vertices,indices,[p[i] for i in q],n)

def tapered(vertices,indices,z0,z1,r0,r1,sides=8,center=(0,0)):
    cx,cy=center
    for i in range(sides):
        a=2*math.pi*i/sides; b=2*math.pi*(i+1)/sides
        n=(math.cos((a+b)/2),math.sin((a+b)/2),0)
        face(vertices,indices,[(cx+r0*math.cos(a),cy+r0*math.sin(a),z0),(cx+r0*math.cos(b),cy+r0*math.sin(b),z0),(cx+r1*math.cos(b),cy+r1*math.sin(b),z1),(cx+r1*math.cos(a),cy+r1*math.sin(a),z1)],n)

def crossed_leaves(vertices,indices,z0,z1,width,count=3):
    for i in range(count):
        a=math.pi*i/count; dx=math.cos(a)*width/2; dy=math.sin(a)*width/2
        face(vertices,indices,[(-dx,-dy,z0),(dx,dy,z0),(dx,dy,z1),(-dx,-dy,z1)],(math.sin(a),-math.cos(a),0))

def e3d(path, texture, build):
    vertices=[]; indices=[]; build(vertices,indices)
    path.parent.mkdir(parents=True,exist_ok=True)
    vertex_data=b''.join(struct.pack('<8f',*v) for v in vertices)
    index_data=struct.pack('<'+'H'*len(indices),*indices)
    mn=[min(v[5+i] for v in vertices) for i in range(3)]; mx=[max(v[5+i] for v in vertices) for i in range(3)]
    name=texture.encode()[:127]+b'\0'; name=name.ljust(128,b'\0')
    material=struct.pack('<i128s6f4i',0,name,*mn,*mx,min(indices),max(indices),0,len(indices))
    elc_size=28; hdr_size=40; vo=elc_size+hdr_size; io=vo+len(vertex_data); mo=io+len(index_data)
    header=struct.pack('<9i4B',len(vertices),32,vo,len(indices),2,io,1,172,mo,1,0x10,0,0)
    payload=header+vertex_data+index_data+material
    elc=struct.pack('<4s4s16si',b'e3dx',bytes((1,1,0,0)),hashlib.md5(payload).digest(),elc_size)
    path.write_bytes(elc+payload)

def texture(path,colors):
    a,b=colors
    def material(x,y):
        grain=((x*23+y*41+(x^y)*5)%31)-15
        broad=(math.sin(x*.071)+math.sin((x+y)*.039)+math.cos(y*.053))/3
        base=a if broad<.08 else b
        seam=(x%64 in (0,1) or y%64 in (0,1))
        color=tuple(int(c*.72) for c in base) if seam else base
        return (*(max(0,min(255,c+grain//2)) for c in color),255)
    png(path,256,256,material)

def tree(v,i): tapered(v,i,0,2.5,.32,.20); tapered(v,i,1.6,4.6,1.7,0,10)
def pine(v,i): tapered(v,i,0,3,.24,.16); tapered(v,i,1.2,4.8,1.55,0,10); tapered(v,i,2.4,5.4,1.15,0,10)
def boulder(v,i): tapered(v,i,0,1.2,1.2,.62,7)
def cottage(v,i): box(v,i,(0,0,1.1),(3.8,3.0,2.2)); tapered(v,i,2.2,3.7,2.65,0,4)
def signpost(v,i): box(v,i,(0,0,1.25),(.18,.18,2.5)); box(v,i,(0,.03,2.15),(1.5,.16,.55))
def lamp(v,i): tapered(v,i,0,2.8,.12,.08,8); box(v,i,(0,0,2.9),(.5,.5,.7))
def dock(v,i):
    for x in (-1.2,-.4,.4,1.2): box(v,i,(x,0,.18),(.72,4,.25))
    for x in (-1.55,1.55):
        for y in (-1.7,1.7): tapered(v,i,-.8,.5,.11,.11,8,(x,y))
def sunleaf(v,i): crossed_leaves(v,i,0,1.05,.85,4); tapered(v,i,.75,1.3,.28,0,7)
def frost_reed(v,i):
    for x,y in ((-.18,0),(.18,.08),(0,-.15)): tapered(v,i,0,1.45,.045,.025,6,(x,y))
def copper_bloom(v,i): tapered(v,i,0,.8,.05,.035,6); tapered(v,i,.65,1.15,.42,0,8)
def ember_crystal(v,i):
    for x,y,h in ((0,0,1.4),(.35,.12,.9),(-.28,.18,1.05)): tapered(v,i,0,h,.24,0,5,(x,y))
def slate(v,i):
    box(v,i,(0,0,.35),(1.6,1.2,.7)); box(v,i,(.42,.18,.8),(.75,.62,.9))

def timber_wall(v,i):
    for x in (-1.5,-.75,0,.75,1.5): box(v,i,(x,0,1.35),(.18,.28,2.7))
    for z in (.25,1.35,2.45): box(v,i,(0,0,z),(3.4,.22,.18))
def stone_wall(v,i): box(v,i,(0,0,1.25),(4,.75,2.5))
def tower(v,i): tapered(v,i,0,5,1.65,1.65,10); tapered(v,i,5,6.2,2.0,0,10)
def gate(v,i):
    box(v,i,(-1.55,0,1.8),(1.1,1.0,3.6)); box(v,i,(1.55,0,1.8),(1.1,1.0,3.6)); box(v,i,(0,0,3.45),(2.1,1.0,.55))
def roof(v,i): tapered(v,i,0,1.55,2.8,0,4)
def door(v,i): box(v,i,(0,0,1.15),(1.35,.18,2.3))
def battlement(v,i):
    box(v,i,(0,0,.55),(4,.85,1.1))
    for x in (-1.6,-.8,0,.8,1.6): box(v,i,(x,0,1.25),(.42,.85,.65))
def column(v,i): tapered(v,i,0,3,.34,.28,10); tapered(v,i,0,.25,.55,.48,10); tapered(v,i,2.75,3,.48,.55,10)
def bridge(v,i):
    for x in (-1.25,-.75,-.25,.25,.75,1.25): box(v,i,(x,0,.15),(.42,4,.28))
    for x in (-1.55,1.55): box(v,i,(x,0,.55),(.16,4,.16))
def palm(v,i): tapered(v,i,0,4,.28,.16,9); crossed_leaves(v,i,3.8,4.25,3.5,6)
def cactus(v,i):
    tapered(v,i,0,2.6,.28,.22,8); tapered(v,i,.7,1.8,.16,.12,7,(.42,0)); tapered(v,i,.9,2.1,.16,.12,7,(-.4,.08))
def dead_tree(v,i):
    tapered(v,i,0,3.6,.34,.12,8); tapered(v,i,2.2,3.8,.13,.05,7,(.45,0)); tapered(v,i,1.8,3.15,.12,.04,7,(-.5,.1))
def snow_pine(v,i): tapered(v,i,0,3.2,.25,.14,9); tapered(v,i,1.0,4.7,1.8,0,10); tapered(v,i,2.2,5.3,1.35,0,10)
def ice_boulder(v,i): tapered(v,i,0,1.5,1.35,.5,6)
def cypress(v,i): tapered(v,i,0,3.4,.38,.18,9); tapered(v,i,1.7,5.2,1.25,.15,10)
def fern(v,i): crossed_leaves(v,i,0,1.35,1.8,7)
def basalt(v,i):
    for x,y,h,r in ((0,0,3,.45),(.55,.18,2.1,.34),(-.48,.1,2.45,.38)): tapered(v,i,0,h,r,r*.72,6,(x,y))
def lava_rock(v,i): tapered(v,i,0,1.0,1.3,.62,7)
def dune_grass(v,i): crossed_leaves(v,i,0,.9,1.1,8)
def wheat(v,i):
    for x,y in ((0,0),(.18,.08),(-.17,.1),(.08,-.18),(-.12,-.16)): tapered(v,i,0,1.2,.025,.018,5,(x,y)); tapered(v,i,1.0,1.35,.11,0,6,(x,y))
def cotton(v,i): tapered(v,i,0,1.0,.05,.035,6); box(v,i,(0,0,1.05),(.42,.42,.34))
def herb(v,i): crossed_leaves(v,i,0,.72,.72,5); tapered(v,i,.48,.92,.16,0,7)
def flax(v,i):
    for x,y in ((0,0),(.14,.05),(-.14,.05)): tapered(v,i,0,1.0,.025,.015,5,(x,y)); tapered(v,i,.9,1.12,.13,0,7,(x,y))
def mushroom(v,i): tapered(v,i,0,.45,.1,.08,7); tapered(v,i,.38,.72,.42,0,10)
def berry(v,i): tapered(v,i,0,.9,.08,.04,7); crossed_leaves(v,i,.25,.95,.8,5); box(v,i,(.18,.05,.72),(.18,.18,.18))
def ore(v,i):
    box(v,i,(0,0,.3),(1.45,1.15,.6)); tapered(v,i,.35,1.0,.38,0,6,(.28,.08))

ASSETS={
 'scenery/alder_tree':(tree,((83,74,48),(106,132,78))), 'scenery/highland_pine':(pine,((65,58,42),(54,91,67))),
 'scenery/boulder':(boulder,((91,92,88),(116,112,103))), 'scenery/cottage':(cottage,((118,83,53),(154,128,82))),
 'scenery/signpost':(signpost,((112,76,43),(146,106,65))), 'scenery/lantern':(lamp,((58,57,54),(224,146,62))),
 'scenery/dock':(dock,((100,71,44),(132,94,54))), 'harvestables/sunleaf':(sunleaf,((72,116,64),(222,160,61))),
 'harvestables/frost_reed':(frost_reed,((78,119,113),(171,214,201))), 'harvestables/copper_bloom':(copper_bloom,((66,105,62),(184,99,55))),
 'harvestables/ember_crystal':(ember_crystal,((109,54,49),(235,106,53))), 'harvestables/slate_outcrop':(slate,((70,75,81),(112,119,126))),
 'architecture/timber_wall':(timber_wall,((92,62,39),(143,99,57))), 'architecture/stone_wall':(stone_wall,((83,84,81),(119,116,108))),
 'architecture/stone_tower':(tower,((77,79,78),(112,109,103))), 'architecture/gate_arch':(gate,((82,83,80),(124,119,108))),
 'architecture/roof_section':(roof,((103,58,43),(151,86,55))), 'architecture/wooden_door':(door,((91,56,31),(136,88,48))),
 'architecture/castle_battlement':(battlement,((88,89,86),(128,125,117))), 'architecture/column':(column,((105,103,96),(148,143,132))),
 'architecture/bridge_segment':(bridge,((91,65,40),(133,95,55))),
 'biomes/desert/palm':(palm,((98,72,42),(69,117,70))), 'biomes/desert/cactus':(cactus,((62,119,72),(89,143,79))),
 'biomes/desert/dead_tree':(dead_tree,((85,60,39),(121,83,47))), 'biomes/snow/snow_pine':(snow_pine,((56,82,69),(187,207,198))),
 'biomes/snow/ice_boulder':(ice_boulder,((102,151,164),(188,224,229))), 'biomes/swamp/cypress':(cypress,((67,55,38),(50,87,61))),
 'biomes/tropical/giant_fern':(fern,((47,104,58),(83,142,70))), 'biomes/volcanic/basalt_spire':(basalt,((49,47,48),(79,72,69))),
 'biomes/volcanic/lava_rock':(lava_rock,((53,48,47),(151,58,35))), 'biomes/desert/dune_grass':(dune_grass,((145,126,73),(183,158,87))),
 'harvestables/wheat':(wheat,((117,105,48),(211,176,73))), 'harvestables/cotton':(cotton,((72,112,66),(226,222,202))),
 'harvestables/lavender':(herb,((72,106,65),(137,94,160))), 'harvestables/flax':(flax,((73,111,67),(104,143,184))),
 'harvestables/sage':(herb,((82,111,82),(139,155,117))), 'harvestables/rosemary':(herb,((48,91,60),(91,123,72))),
 'harvestables/mushroom':(mushroom,((213,198,157),(151,75,55))), 'harvestables/grave_moss':(herb,((48,67,52),(89,104,74))), 'harvestables/blueberries':(berry,((55,98,59),(54,63,139))),
 'harvestables/coal':(ore,((37,39,42),(62,63,65))), 'harvestables/iron_ore':(ore,((91,77,66),(145,105,76))),
 'harvestables/stormglass':(ore,((79,111,139),(157,205,221))), 'harvestables/moon_salt':(ore,((168,174,186),(235,231,211))),
 'harvestables/quartz':(ore,((151,147,142),(224,217,207))), 'harvestables/sulfur':(ore,((153,143,50),(224,206,68))) }

def main():
    p=argparse.ArgumentParser(); p.add_argument('output',nargs='?',default='build/eloria-data'); root=Path(p.parse_args().output)
    for name,(builder,colors) in ASSETS.items():
        model=root/'3dobjects'/f'{name}.e3d'; tex=model.with_suffix('.png'); texture(tex,colors); e3d(model,tex.name,builder)
    (root/'harvestables_eloria.lst').write_text('\n'.join(f'{i+1} | {name.split("/")[-1].replace("_"," ").title()} | 3dobjects/{name}.e3d' for i,name in enumerate(n for n in ASSETS if n.startswith('harvestables/')))+'\n')
if __name__=='__main__': main()

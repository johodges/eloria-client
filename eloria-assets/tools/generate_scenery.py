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
    png(path,128,128,lambda x,y:(*(a if ((x//16+y//16)&1)==0 else b),255))

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

ASSETS={
 'scenery/alder_tree':(tree,((83,74,48),(106,132,78))), 'scenery/highland_pine':(pine,((65,58,42),(54,91,67))),
 'scenery/boulder':(boulder,((91,92,88),(116,112,103))), 'scenery/cottage':(cottage,((118,83,53),(154,128,82))),
 'scenery/signpost':(signpost,((112,76,43),(146,106,65))), 'scenery/lantern':(lamp,((58,57,54),(224,146,62))),
 'scenery/dock':(dock,((100,71,44),(132,94,54))), 'harvestables/sunleaf':(sunleaf,((72,116,64),(222,160,61))),
 'harvestables/frost_reed':(frost_reed,((78,119,113),(171,214,201))), 'harvestables/copper_bloom':(copper_bloom,((66,105,62),(184,99,55))),
 'harvestables/ember_crystal':(ember_crystal,((109,54,49),(235,106,53))), 'harvestables/slate_outcrop':(slate,((70,75,81),(112,119,126))) }

def main():
    p=argparse.ArgumentParser(); p.add_argument('output',nargs='?',default='build/eloria-data'); root=Path(p.parse_args().output)
    for name,(builder,colors) in ASSETS.items():
        model=root/'3dobjects'/f'{name}.e3d'; tex=model.with_suffix('.png'); texture(tex,colors); e3d(model,tex.name,builder)
    (root/'harvestables_eloria.lst').write_text('\n'.join(f'{i+1} | {name.split("/")[-1].replace("_"," ").title()} | 3dobjects/{name}.e3d' for i,name in enumerate(n for n in ASSETS if n.startswith('harvestables/')))+'\n')
if __name__=='__main__': main()

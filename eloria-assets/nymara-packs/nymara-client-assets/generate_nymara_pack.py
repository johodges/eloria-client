#!/usr/bin/env python3
"""Generate an original Nymara client-ready 2D/3D asset pack.

Outputs native E3D models plus PNG textures/icons. Geometry and pixels are
procedural and independent; concept art is used only as art-direction input.
"""
from __future__ import annotations
import hashlib, json, math, struct, sys, zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOOLS = ROOT.parents[1] / 'tools'
if str(TOOLS) not in sys.path: sys.path.insert(0, str(TOOLS))
import harvestables  # noqa: E402  shared harvestable catalogue
Vertex = tuple[float,float,float,float,float,float,float,float]

def png(path,w,h,pixel):
    raw=bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w): raw.extend(pixel(x,y))
    def chunk(t,d): return struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(bytes(raw),9))+chunk(b'IEND',b''))

def face(v,i,pts,n,uv=((0,0),(1,0),(1,1),(0,1))):
    b=len(v)
    for (x,y,z),(u,t) in zip(pts,uv): v.append((u,t,*n,x,y,z))
    i.extend((b,b+1,b+2,b,b+2,b+3))
def box(v,i,c,s):
    cx,cy,cz=c;sx,sy,sz=(q/2 for q in s)
    p=[(cx+x*sx,cy+y*sy,cz+z*sz) for x,y,z in ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1))]
    for q,n in zip(((0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(4,0,3,7)),((0,0,-1),(0,0,1),(0,-1,0),(1,0,0),(0,1,0),(-1,0,0))): face(v,i,[p[k] for k in q],n)
def taper(v,i,z0,z1,r0,r1,sides=8,c=(0,0)):
    cx,cy=c
    for k in range(sides):
        a=2*math.pi*k/sides;b=2*math.pi*(k+1)/sides;m=(a+b)/2
        face(v,i,[(cx+r0*math.cos(a),cy+r0*math.sin(a),z0),(cx+r0*math.cos(b),cy+r0*math.sin(b),z0),(cx+r1*math.cos(b),cy+r1*math.sin(b),z1),(cx+r1*math.cos(a),cy+r1*math.sin(a),z1)],(math.cos(m),math.sin(m),0))
def leaves(v,i,z0,z1,w,count=4):
    for k in range(count):
        a=math.pi*k/count;dx=math.cos(a)*w/2;dy=math.sin(a)*w/2
        face(v,i,[(-dx,-dy,z0),(dx,dy,z0),(dx,dy,z1),(-dx,-dy,z1)],(math.sin(a),-math.cos(a),0))

def e3d(path,tex,build):
    v=[];i=[];build(v,i);vd=b''.join(struct.pack('<8f',*x) for x in v);ids=struct.pack('<'+'H'*len(i),*i)
    mn=[min(x[5+j] for x in v) for j in range(3)];mx=[max(x[5+j] for x in v) for j in range(3)]
    mat=struct.pack('<i128s6f4i',0,(tex.encode()+b'\0')[:128].ljust(128,b'\0'),*mn,*mx,min(i),max(i),0,len(i))
    vo=68;io=vo+len(vd);mo=io+len(ids);hdr=struct.pack('<9i4B',len(v),32,vo,len(i),2,io,1,172,mo,1,0x10,0,0)
    payload=hdr+vd+ids+mat;path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(struct.pack('<4s4s16si',b'e3dx',bytes((1,1,0,0)),hashlib.md5(payload).digest(),28)+payload)

def obj(path,build,mat,texture):
    v=[];i=[];build(v,i);path.parent.mkdir(parents=True,exist_ok=True)
    out=[f'mtllib {path.stem}.mtl',f'usemtl {mat}']
    out += [f'v {x[5]:.5f} {x[6]:.5f} {x[7]:.5f}' for x in v]
    out += [f'vt {x[0]:.5f} {1-x[1]:.5f}' for x in v]
    out += [f'vn {x[2]:.5f} {x[3]:.5f} {x[4]:.5f}' for x in v]
    out += [f'f {i[k]+1}/{i[k]+1}/{i[k]+1} {i[k+1]+1}/{i[k+1]+1}/{i[k+1]+1} {i[k+2]+1}/{i[k+2]+1}/{i[k+2]+1}' for k in range(0,len(i),3)]
    path.write_text('\n'.join(out)+'\n');path.with_suffix('.mtl').write_text(f'newmtl {mat}\nKd 1 1 1\nmap_Kd ../runtime/3dobjects/nymara/{texture}\n')

def building(v,i): box(v,i,(0,0,1.2),(4,3.2,2.4));taper(v,i,2.4,4,2.8,0,8)
def tower(v,i): taper(v,i,0,5,1.45,1.3,12);taper(v,i,5,6.1,1.9,0,12)
def bridge(v,i):
    for x in (-1.5,-.9,-.3,.3,.9,1.5): box(v,i,(x,0,.18),(.52,5,.3))
    for x in (-1.85,1.85): box(v,i,(x,0,.65),(.16,5,.18))
def gate(v,i): box(v,i,(-1.6,0,2),(1.15,1.2,4));box(v,i,(1.6,0,2),(1.15,1.2,4));box(v,i,(0,0,3.75),(2.1,1.2,.55))
def four_gates_wall(v,i):
    box(v,i,(0,0,.55),(5.6,1.15,1.1));box(v,i,(0,0,1.45),(5.15,.82,.72))
    for x in (-2.35,-1.4,-.47,.47,1.4,2.35): box(v,i,(x,0,2.05),(.52,.9,.55))
    for x in (-2.7,2.7): taper(v,i,0,2.25,.42,.3,8,(x,0))
def four_gates_tower(v,i):
    taper(v,i,0,.6,1.65,1.45,12);taper(v,i,.6,4.8,1.28,1.05,12)
    for z in (1.0,2.6,4.25): taper(v,i,z,z+.22,1.42,1.42,12)
    for angle in range(0,360,45):
        a=math.radians(angle); box(v,i,(1.18*math.cos(a),1.18*math.sin(a),4.9),(.26,.26,1.15))
    taper(v,i,5.35,5.72,1.62,1.62,12);taper(v,i,5.72,7.0,1.6,.18,12)
    taper(v,i,7.0,7.65,.16,0,8)
def four_gates_bridge(v,i):
    for y in (-2.25,-1.35,-.45,.45,1.35,2.25): box(v,i,(0,y,.28),(3.8,.78,.32))
    for x in (-2.0,2.0):
        box(v,i,(x,0,.72),(.18,5.4,.18))
        for y in (-2.45,0,2.45): taper(v,i,-.65,1.45,.22,.16,8,(x,y))
    for x in (-1.2,1.2):
        for y in (-2.45,2.45): taper(v,i,-.5,.4,.32,.24,8,(x,y))
def four_gates_pavilion(v,i):
    taper(v,i,0,.45,2.65,2.4,12);taper(v,i,.45,.7,2.25,2.25,12)
    for angle in range(0,360,45):
        a=math.radians(angle); taper(v,i,.7,3.35,.18,.14,8,(1.78*math.cos(a),1.78*math.sin(a)))
    taper(v,i,3.25,3.5,2.25,2.25,12);taper(v,i,3.5,4.75,2.2,.2,12)
    taper(v,i,4.7,5.35,.14,0,8)
def four_gates_tree(v,i):
    taper(v,i,0,3.4,.38,.2,10)
    for angle,height in ((0,3.8),(72,3.5),(144,4.0),(216,3.6),(288,3.9)):
        a=math.radians(angle); cx=.65*math.cos(a); cy=.65*math.sin(a)
        taper(v,i,2.2,height,.18,.05,8,(cx,cy))
        taper(v,i,2.6,height+1.35,1.05,.08,10,(cx*1.35,cy*1.35))
    taper(v,i,2.8,5.6,1.25,.1,12)
def four_gates_gatehouse(v,i):
    # Monumental paired towers frame a broad unobstructed portal opening.
    for x in (-2.15,2.15):
        taper(v,i,0,.55,1.2,1.05,12,(x,0));taper(v,i,.55,4.9,.95,.82,12,(x,0))
        for z in (1.0,3.0,4.55): taper(v,i,z,z+.2,1.08,1.08,12,(x,0))
        taper(v,i,4.75,5.85,1.22,.12,12,(x,0));taper(v,i,5.8,6.35,.11,0,8,(x,0))
    box(v,i,(0,0,4.25),(2.55,1.25,.62));box(v,i,(0,0,4.75),(3.2,1.0,.38))
    for x in (-1.2,-.4,.4,1.2): box(v,i,(x,0,5.18),(.35,1.05,.55))
    for x in (-3.05,3.05): taper(v,i,0,3.2,.38,.25,8,(x,0))
def four_gates_waystone(v,i):
    taper(v,i,0,.35,1.75,1.5,12);taper(v,i,.35,.7,1.35,1.2,12)
    for angle in (0,120,240):
        a=math.radians(angle); x=.72*math.cos(a); y=.72*math.sin(a)
        taper(v,i,.65,3.15,.3,.18,8,(x,y));taper(v,i,3.15,3.85,.28,0,8,(x,y))
    taper(v,i,.7,2.55,.42,.3,10);taper(v,i,2.55,4.5,.55,0,8)
def four_gates_lantern(v,i):
    taper(v,i,0,2.8,.12,.09,8);taper(v,i,2.75,3.0,.42,.34,8)
    for x in (-.28,.28):
        for y in (-.28,.28): box(v,i,(x,y,3.45),(.07,.07,.9))
    box(v,i,(0,0,3.05),(.68,.68,.12));box(v,i,(0,0,3.85),(.72,.72,.12))
    taper(v,i,3.9,4.35,.58,0,8)
def four_gates_townhouse(v,i):
    # A compact, manifold-friendly ward building assembled from broad masses.
    box(v,i,(0,0,1.55),(4.8,3.5,3.1));box(v,i,(0,-1.62,2.0),(2.0,.35,2.5))
    taper(v,i,3.1,4.75,3.25,.18,4)
    for x in (-1.45,0,1.45): box(v,i,(x,-1.82,2.15),(.55,.18,.85))
    taper(v,i,4.65,5.45,.18,0,8,(1.5,0))
def four_gates_market_hall(v,i):
    box(v,i,(0,0,1.35),(6.4,4.2,2.7));taper(v,i,2.7,4.65,3.9,.15,4)
    for x in (-2.6,-1.3,0,1.3,2.6):
        taper(v,i,0,2.7,.16,.12,8,(x,-2.25));box(v,i,(x,-2.12,1.55),(.48,.18,.78))
    box(v,i,(0,-2.28,.45),(2.0,.25,.9));taper(v,i,4.55,5.35,.2,0,8)
def four_gates_garden_court(v,i):
    taper(v,i,0,.28,3.0,2.8,16);taper(v,i,.28,.48,2.55,2.35,16)
    for angle in range(0,360,45):
        a=math.radians(angle);x=2.0*math.cos(a);y=2.0*math.sin(a)
        taper(v,i,.45,1.7,.15,.08,7,(x,y));taper(v,i,1.2,2.4,.62,.06,8,(x,y))
    taper(v,i,.45,1.7,.22,.1,8);taper(v,i,1.55,2.1,.58,0,8)
def four_gates_field_plot(v,i):
    box(v,i,(0,0,.08),(6.2,4.4,.16))
    for x in (-2.5,-1.5,-.5,.5,1.5,2.5):
        box(v,i,(x,0,.22),(.18,4.0,.20))
    for x in (-3.2,3.2):
        for y in (-2.25,0,2.25): taper(v,i,0,.85,.09,.07,6,(x,y))
def four_gates_waterfall(v,i):
    box(v,i,(0,.25,1.75),(3.2,.35,3.5));box(v,i,(0,0,.18),(4.2,2.2,.28))
    for x in (-1.15,-.38,.38,1.15):
        face(v,i,[(x-.25,0,3.45),(x+.25,0,3.45),(x+.38,-.15,.3),(x-.38,-.15,.3)],(0,-1,0))
def four_gates_farmstead(v,i):
    box(v,i,(-1.45,0,1.05),(3.7,3.0,2.1));taper(v,i,2.1,3.55,2.45,.1,4,(-1.45,0))
    box(v,i,(2.0,.35,.8),(2.4,2.3,1.6));taper(v,i,1.6,2.65,1.65,.1,4,(2.0,.35))
    for x in (-2.4,-.6,.9,2.8): box(v,i,(x,-1.75,.55),(.14,.14,1.1))
    for z in (.25,.85): box(v,i,(.2,-1.75,z),(5.5,.12,.12))
def four_gates_beacon_tower(v,i):
    taper(v,i,0,.55,1.55,1.35,12);taper(v,i,.55,5.8,1.15,.82,12)
    for z in (1.0,3.0,5.35): taper(v,i,z,z+.22,1.3,1.3,12)
    for angle in range(0,360,60):
        a=math.radians(angle); taper(v,i,5.5,7.0,.16,.10,7,(1.05*math.cos(a),1.05*math.sin(a)))
    taper(v,i,5.7,6.2,.72,.52,8);taper(v,i,6.2,8.1,.48,0,8)
def four_gates_citadel_gatehouse(v,i):
    for x in (-3.0,3.0):
        taper(v,i,0,.7,1.55,1.35,12,(x,0));taper(v,i,.7,6.7,1.25,.95,12,(x,0))
        taper(v,i,6.55,8.0,1.45,.12,12,(x,0));taper(v,i,7.95,8.65,.11,0,8,(x,0))
    box(v,i,(0,0,5.65),(3.8,1.35,.75));box(v,i,(0,0,6.35),(4.8,1.1,.55))
    for x in (-1.8,-.9,0,.9,1.8): box(v,i,(x,0,6.95),(.42,1.15,.72))
def four_gates_summit_portal(v,i):
    taper(v,i,0,.55,3.1,2.65,12);taper(v,i,.55,.9,2.55,2.25,12)
    for x in (-2.0,2.0):
        taper(v,i,.85,5.9,.42,.28,10,(x,0));taper(v,i,5.7,7.35,.52,.08,10,(x,0))
    box(v,i,(0,0,6.0),(3.7,.72,.7));taper(v,i,6.15,8.25,2.5,.12,12)
def four_gates_plaza_monument(v,i):
    taper(v,i,0,.42,3.2,2.8,16);taper(v,i,.42,.72,2.6,2.25,16)
    for angle in (0,90,180,270):
        a=math.radians(angle); taper(v,i,.65,3.5,.25,.17,8,(1.55*math.cos(a),1.55*math.sin(a)))
    taper(v,i,.7,4.8,.52,.3,10);taper(v,i,4.8,6.6,.75,.08,8)
def four_gates_cliff_terrace(v,i):
    # Stepped masses avoid the dense overlapping rock fragments in the source GLB.
    for k,(width,depth,height) in enumerate(((7.0,4.8,1.0),(5.8,4.0,1.1),(4.4,3.2,1.0))):
        box(v,i,(0,.45*k,.5+k*.9),(width,depth,height))
    for x,y,h,r in ((-2.5,.4,3.4,.65),(2.2,.8,3.0,.55),(0,1.5,4.0,.7)):
        taper(v,i,2.0,h,r,.18,7,(x,y))
def dock(v,i):
    for x in (-1.2,-.4,.4,1.2): box(v,i,(x,0,.2),(.7,4,.28))
    for x in (-1.55,1.55):
        for y in (-1.7,1.7): taper(v,i,-.8,.55,.1,.1,7,(x,y))
def boat(v,i): taper(v,i,0,.75,1.1,.65,10);box(v,i,(0,0,.85),(1.1,2.8,.18));taper(v,i,.9,3,.08,.06,7);face(v,i,[(0,0,2.8),(0,0,1.1),(0,1.5,1.7),(0,1.5,2.8)],(1,0,0))
def crystal(v,i):
    for x,y,h,r in ((0,0,2,.35),(.42,.15,1.3,.25),(-.35,.12,1.55,.27)): taper(v,i,0,h,r,0,6,(x,y))
def observatory(v,i): taper(v,i,0,2.4,2.2,2.2,12);taper(v,i,2.4,4,2.25,0,12);box(v,i,(0,-1.8,2.8),(.35,2.8,.35))
def tent(v,i): taper(v,i,0,2.8,2.5,0,8)
def manor(v,i): box(v,i,(0,0,1.5),(6,4,3));taper(v,i,3,5,4.1,0,4);box(v,i,(-2.4,0,4),(1.1,1.1,2.2))
def stone(v,i): taper(v,i,0,3,.7,.45,7)
def tree(v,i): taper(v,i,0,3,.3,.18,8);taper(v,i,1.8,5,1.8,.1,10)
def reed(v,i):
    for x,y in ((0,0),(.18,.1),(-.16,.08),(.08,-.18)): taper(v,i,0,1.3,.035,.02,6,(x,y))
def flower(v,i): taper(v,i,0,.8,.04,.025,6);taper(v,i,.65,1.15,.38,0,8)
def pearl(v,i): taper(v,i,0,.45,.5,.35,10);taper(v,i,.45,.8,.35,.5,10)
def crate(v,i): box(v,i,(0,0,.55),(1.1,1.1,1.1))
def lighthouse(v,i): taper(v,i,0,6,1.2,.75,12);box(v,i,(0,0,6.25),(1.7,1.7,.55));taper(v,i,6.5,7.5,1.25,0,10)
def warehouse(v,i): box(v,i,(0,0,1.6),(6,4,3.2));taper(v,i,3.2,5,3.8,0,4)
def crane(v,i): box(v,i,(0,0,2.5),(.32,.32,5));box(v,i,(1.7,0,4.8),(3.7,.28,.28));box(v,i,(3.3,0,3.5),(.08,.08,2.5))
def boardwalk(v,i):
    for x in (-1.2,-.6,0,.6,1.2): box(v,i,(x,0,.35),(.5,5,.24))
    for x in (-1.5,1.5):
        for y in (-2,0,2): taper(v,i,-.7,.7,.09,.08,6,(x,y))
def stilt_house(v,i):
    for x in (-1.4,1.4):
        for y in (-1.1,1.1): taper(v,i,-1,2,.12,.1,7,(x,y))
    box(v,i,(0,0,2.2),(3.8,3,2.2));taper(v,i,3.3,4.7,2.7,0,4)
def canoe(v,i): taper(v,i,0,.55,.65,.28,10);box(v,i,(0,0,.5),(.75,3.4,.12))
def mangrove(v,i):
    taper(v,i,0,3,.32,.2,9)
    for x,y in ((.6,0),(-.5,.2),(0,.55)): taper(v,i,0,2,.08,.18,7,(x,y))
    taper(v,i,2,4.6,1.6,.08,10)
def fern(v,i): leaves(v,i,0,1.4,2.2,7)
def ruin_arch(v,i): box(v,i,(-1.4,0,1.7),(.8,1,3.4));box(v,i,(1.4,0,1.7),(.8,1,3.4));taper(v,i,2.7,4,2.1,1.65,10)
def ssarathi_temple(v,i):
    for z,s in ((.35,(7,5,.7)),(1.0,(5.8,4,.65)),(1.65,(4.6,3,.65))): box(v,i,(0,0,z),s)
    for x in (-1.6,1.6): taper(v,i,2,5,.32,.25,10,(x,0))
    taper(v,i,2,5.2,2.2,.1,12)
def ritual_pool(v,i): box(v,i,(0,0,.25),(5,4,.5));box(v,i,(0,0,.48),(4.1,3.1,.12))
def standing_stones(v,i):
    for x,y,h in ((-1.5,0,2.7),(1.5,0,2.4),(0,1.5,2.9),(0,-1.5,2.5)): taper(v,i,0,h,.38,.3,6,(x,y))
def barrow(v,i): taper(v,i,0,2.4,3.2,.3,12);box(v,i,(0,-2.5,1.05),(1.5,1.4,2.1))
def mine(v,i): box(v,i,(-1.5,0,1.5),(.45,.55,3));box(v,i,(1.5,0,1.5),(.45,.55,3));box(v,i,(0,0,2.8),(3.4,.55,.45))
def glacier(v,i):
    for x,y,h,r in ((0,0,3,1.8),(1.5,.5,2.2,1.3),(-1.4,.3,2.5,1.4)): taper(v,i,0,h,r,.2,7,(x,y))
def monastery(v,i): box(v,i,(0,0,1.4),(5,4,2.8));taper(v,i,2.8,4.5,3.2,.2,8);taper(v,i,4.3,5.8,.5,0,8)
def windmill(v,i):
    taper(v,i,0,4,1.3,.8,10);taper(v,i,4,5.2,1.4,0,8)
    for a in (0,math.pi/2):
        dx=math.cos(a)*2;dz=math.sin(a)*2;face(v,i,[(-dx,0,2.8),(-dx,0,3.2),(dx,0,5.2),(dx,0,4.8)],(0,-1,0))
def caravanserai(v,i): box(v,i,(0,0,1.5),(7,5,3));box(v,i,(0,-2.45,1.4),(2,1,2.8));taper(v,i,3,4.2,4.4,0,4)
def cairn(v,i):
    for z,r in ((.25,.8),(.75,.62),(1.2,.45),(1.55,.28)): taper(v,i,z-.25,z+.25,r,r*.8,7)
def market(v,i): box(v,i,(0,0,.9),(3,2,1.8));taper(v,i,1.8,3,2.2,0,4)
def wall(v,i): box(v,i,(0,0,1.1),(5,.65,2.2))
def stairs(v,i):
    for k in range(6): box(v,i,(0,k*.55,k*.22),(3,.58,.42))
def well(v,i): taper(v,i,0,.8,1.1,1.1,12);box(v,i,(-1.2,0,1.5),(.18,.18,2.3));box(v,i,(1.2,0,1.5),(.18,.18,2.3));box(v,i,(0,0,2.55),(2.7,.18,.18))
def shrine(v,i): box(v,i,(0,0,.35),(2.5,2,.7));taper(v,i,.7,3,.45,.28,10);taper(v,i,3,3.8,.8,0,8)
def fence(v,i):
    for x in (-2,0,2): box(v,i,(x,0,1),(.18,.2,2))
    for z in (.45,1.45): box(v,i,(0,0,z),(4.2,.16,.16))
def cave(v,i):
    box(v,i,(-1.7,0,1.5),(1.2,1.4,3));box(v,i,(1.7,0,1.5),(1.2,1.4,3));taper(v,i,2.4,4,2.5,1.9,10)
def platform(v,i): box(v,i,(0,0,3),(4,4,.35));taper(v,i,0,5,.45,.3,9);box(v,i,(0,0,4.2),(2.6,2.2,2));taper(v,i,5.2,6.2,1.8,0,8)
def fishtrap(v,i): taper(v,i,0,1,.65,.35,10);box(v,i,(0,0,.5),(1.4,.12,.12))
def fountain(v,i): taper(v,i,0,.55,2,1.8,12);taper(v,i,.5,2.4,.18,.1,10);taper(v,i,2.2,2.8,.8,0,10)
def lockgate(v,i): box(v,i,(-2,0,1.5),(.7,2.5,3));box(v,i,(2,0,1.5),(.7,2.5,3));box(v,i,(0,0,1.3),(3.4,.35,2.6))
def ropebridge(v,i):
    for y in (-2,-1.2,-.4,.4,1.2,2): box(v,i,(0,y,.15),(2.2,.45,.18))
    for x in (-1.3,1.3): box(v,i,(x,0,.8),(.08,5,.08))
def basalt_steps(v,i):
    for k in range(5): taper(v,i,0,1.2+k*.35,1.3-k*.14,.8-k*.08,6,(k*.55,0))

ASSETS={
 'mirrorhold_lake_house':(building,(213,218,207),(40,123,130)),'mirrorhold_civic_tower':(tower,(207,215,207),(32,112,126)),
 'mirrorhold_radial_bridge':(bridge,(204,208,196),(62,137,139)),'four_gates_gatehouse':(four_gates_gatehouse,(171,166,147),(43,107,110)),
 'four_gates_civic_wall':(four_gates_wall,(160,158,145),(72,111,105)),
 'four_gates_civic_tower':(four_gates_tower,(180,178,158),(53,120,119)),
 'four_gates_radial_bridge':(four_gates_bridge,(170,165,142),(52,126,132)),
 'four_gates_civic_pavilion':(four_gates_pavilion,(190,181,150),(47,116,116)),
 'four_gates_park_tree':(four_gates_tree,(79,76,51),(74,126,66)),
 'four_gates_lantern':(four_gates_lantern,(76,79,70),(213,169,72)),
 'four_gates_townhouse':(four_gates_townhouse,(169,166,151),(48,101,122)),
 'four_gates_market_hall':(four_gates_market_hall,(174,165,142),(53,103,124)),
 'four_gates_garden_court':(four_gates_garden_court,(82,104,65),(188,162,93)),
 'four_gates_field_plot':(four_gates_field_plot,(104,89,54),(148,119,57)),
 'four_gates_waterfall':(four_gates_waterfall,(52,116,124),(116,194,205)),
 'four_gates_farmstead':(four_gates_farmstead,(126,105,73),(52,92,109)),
 'four_gates_beacon_tower':(four_gates_beacon_tower,(91,96,99),(206,151,54)),
 'four_gates_citadel_gatehouse':(four_gates_citadel_gatehouse,(160,156,142),(55,113,137)),
 'four_gates_summit_portal':(four_gates_summit_portal,(64,68,76),(91,72,191)),
 'four_gates_plaza_monument':(four_gates_plaza_monument,(189,181,153),(61,132,157)),
 'four_gates_cliff_terrace':(four_gates_cliff_terrace,(84,91,78),(53,95,63)),
 'crownwater_ferry_dock':(dock,(113,83,52),(43,120,128)),'crownwater_ferry':(boat,(104,73,42),(42,131,143)),
 'glasswarden_observatory':(observatory,(101,87,112),(154,92,181)),'resonant_crystal_cluster':(crystal,(101,72,125),(191,104,230)),
 'orun_round_tent':(tent,(171,111,54),(42,131,134)),'amberwood_estate':(manor,(116,77,48),(181,103,46)),
 'four_gates_waystone':(four_gates_waystone,(103,105,103),(50,118,118)),'amberwood_tree':(tree,(101,69,40),(188,92,38)),
 'mirrorhold_market_crate':(crate,(115,77,45),(36,126,130)),
 # Whitehorn Range
 'whitehorn_glacier':(glacier,(151,196,207),(222,239,240)),'whitehorn_monastery':(monastery,(116,125,129),(187,201,202)),
 'whitehorn_mine_entrance':(mine,(91,87,82),(142,149,151)),'whitehorn_cairn':(cairn,(111,119,120),(196,211,211)),
 # Sunmane Steppe
 'sunmane_windmill':(windmill,(151,104,52),(207,159,72)),'sunmane_caravanserai':(caravanserai,(158,103,55),(61,132,131)),
 'orun_portable_shrine':(cairn,(158,105,49),(46,136,135)),'orun_seasonal_market':(market,(173,105,47),(45,132,133)),
 # Amberwood and Grey Moors
 'amberwood_ruin_arch':(ruin_arch,(114,91,69),(187,100,39)),'grey_moor_standing_stones':(standing_stones,(89,91,90),(132,139,136)),
 'grey_moor_barrow':(barrow,(72,79,68),(108,116,98)),'grey_moor_boardwalk':(boardwalk,(82,62,46),(120,96,62)),
 # Westhaven
 'westhaven_lighthouse':(lighthouse,(190,190,178),(55,108,125)),'westhaven_warehouse':(warehouse,(118,83,55),(70,103,117)),
 'westhaven_harbor_crane':(crane,(97,70,48),(146,105,62)),'westhaven_fish_market':(market,(121,80,49),(46,112,124)),
 # Verdant Stair and Ssarathi Ruins
 'verdant_giant_fern':(fern,(43,113,64),(98,168,78)),'verdant_root_bridge':(bridge,(93,66,43),(59,123,68)),
 'ssarathi_ruin_arch':(ruin_arch,(91,126,111),(50,154,132)),'ssarathi_temple':(ssarathi_temple,(78,118,103),(39,147,128)),
 'ssarathi_ritual_pool':(ritual_pool,(82,119,109),(39,135,141)),'ssarathi_archive_waystone':(stone,(78,116,106),(181,142,63)),
 # Manymouth Delta
 'manymouth_stilt_house':(stilt_house,(118,78,45),(70,133,107)),'manymouth_boardwalk':(boardwalk,(105,72,45),(55,126,102)),
 'manymouth_canoe':(canoe,(112,72,42),(54,126,108)),'manymouth_mangrove':(mangrove,(75,61,40),(47,117,70)),
 'manymouth_ferry_dock':(dock,(91,66,42),(50,119,100)),'manymouth_smuggler_crate':(crate,(93,62,39),(129,92,52)),
 # Mirrorhold and Crownwater supporting kit
 'mirrorhold_canal_wall':(wall,(197,204,194),(49,125,133)),'mirrorhold_canal_stairs':(stairs,(201,207,197),(60,133,137)),
 'mirrorhold_public_fountain':(fountain,(201,211,203),(45,134,144)),'mirrorhold_canal_lock':(lockgate,(184,193,187),(48,116,126)),
 'mirrorhold_floating_market':(market,(133,89,48),(39,128,137)),'crownwater_fishing_boat':(canoe,(105,70,42),(47,129,139)),
 'crownwater_patrol_boat':(boat,(81,71,56),(38,112,128)),'crownwater_submerged_waystone':(stone,(83,128,125),(47,155,155)),
 # Whitehorn supporting kit
 'whitehorn_rope_bridge':(ropebridge,(96,76,54),(190,211,211)),'whitehorn_carved_stairs':(stairs,(125,139,143),(202,221,224)),
 'whitehorn_shrine':(shrine,(129,142,145),(197,215,219)),'whitehorn_mine_lift':(crane,(91,81,68),(151,159,161)),
 'whitehorn_ice_cave':(cave,(126,174,188),(206,233,238)),'whitehorn_frozen_waystone':(stone,(133,177,187),(213,234,236)),
 # Amethyst supporting kit
 'amethyst_crystal_bridge':(bridge,(104,84,121),(178,104,208)),'amethyst_storm_ruin':(ruin_arch,(92,80,103),(154,96,177)),
 'glasswarden_lens_tower':(tower,(112,91,120),(182,122,193)),'glasswarden_field_station':(tent,(116,93,117),(187,125,190)),
 'amethyst_geode_cave':(cave,(94,74,112),(177,105,210)),'amethyst_levitating_shards':(crystal,(85,70,107),(199,122,232)),
 # Sunmane supporting kit
 'sunmane_well':(well,(143,94,48),(49,129,132)),'sunmane_animal_pen':(fence,(124,81,43),(181,125,60)),
 'sunmane_burial_mound':(barrow,(130,105,60),(177,142,70)),'sunmane_caravan_camp':(tent,(168,105,51),(49,133,134)),
 'orun_banner_shrine':(shrine,(167,104,48),(41,132,136)),'sunmane_dry_cave':(cave,(141,111,69),(188,151,82)),
 # Amberwood supporting kit
 'amberwood_old_bridge':(bridge,(111,82,57),(177,103,45)),'amberwood_hunting_lodge':(building,(116,74,44),(175,93,35)),
 'amberwood_hollow_tree':(cave,(95,65,40),(169,87,36)),'amberwood_orchard_fence':(fence,(105,72,44),(164,94,39)),
 'amberwood_garden_fountain':(fountain,(119,114,102),(183,102,46)),'amberwood_root_cave':(cave,(88,65,44),(141,86,41)),
 # Grey Moors supporting kit
 'grey_moor_cairn':(cairn,(86,89,87),(128,134,130)),'grey_moor_dead_tree':(tree,(64,58,49),(94,86,70)),
 'grey_moor_abandoned_cottage':(building,(91,76,61),(112,112,91)),'grey_moor_crypt_entrance':(cave,(76,80,78),(118,123,118)),
 'grey_moor_peat_fence':(fence,(75,62,48),(105,88,65)),'grey_moor_ritual_shrine':(shrine,(79,82,80),(131,134,126)),
 # Westhaven supporting kit
 'westhaven_seawall':(wall,(115,121,121),(70,103,116)),'westhaven_quay_stairs':(stairs,(120,123,119),(65,110,125)),
 'westhaven_dry_dock':(dock,(102,72,47),(55,104,119)),'westhaven_shipyard_frame':(crane,(112,77,47),(151,107,62)),
 'westhaven_lantern_tower':(tower,(121,126,123),(53,104,120)),'westhaven_sea_cave':(cave,(85,91,93),(54,104,118)),
 # Verdant Stair supporting kit
 'verdant_tree_platform':(platform,(88,67,43),(49,125,69)),'verdant_jungle_cave':(cave,(81,93,72),(51,124,71)),
 'verdant_vine_bridge':(ropebridge,(84,71,43),(55,133,72)),'verdant_cenote_stairs':(stairs,(83,105,88),(47,139,113)),
 'verdant_water_shrine':(shrine,(71,112,94),(43,144,122)),'verdant_basalt_steps':(basalt_steps,(69,91,78),(48,124,97)),
 # Ssarathi supporting kit
 'ssarathi_sunken_court':(ritual_pool,(70,112,103),(38,142,130)),'ssarathi_water_gate':(lockgate,(72,113,105),(36,143,132)),
 'ssarathi_curved_wall':(wall,(75,115,105),(43,142,125)),'ssarathi_hatchery_pool':(ritual_pool,(67,108,101),(45,151,137)),
 'ssarathi_sun_stela':(standing_stones,(74,112,104),(183,143,61)),'ssarathi_vault_entrance':(cave,(68,108,101),(39,139,126)),
 # Manymouth supporting kit
 'manymouth_fishing_trap':(fishtrap,(99,73,45),(52,124,91)),'manymouth_reed_fence':(fence,(96,77,48),(66,128,84)),
 'manymouth_flooded_cave':(cave,(73,91,76),(45,117,96)),'manymouth_hidden_dock':(dock,(88,64,42),(45,116,94)),
 'manymouth_tidal_waystone':(stone,(78,102,91),(54,139,118)),'manymouth_market_stall':(market,(111,72,43),(56,127,98))}

def tex(path,a,b):
    png(path,128,128,lambda x,y:(*(a if ((x//16+y//16)&1)==0 else b),255))

def four_gates_tex(path,a,b):
    def pixel(x,y):
        mortar=x%32<2 or y%24<2
        vein=abs(((x*7+y*11+(x*y)//17)%53)-26)<2
        grain=((x*13+y*17+(x^y)*3)%17)-8
        base=b if mortar else tuple((3*q+p)//4 for p,q in zip(a,b)) if vein else a
        return (*(max(0,min(255,channel+grain)) for channel in base),255)
    png(path,256,256,pixel)

# One inventory icon per catalogue harvestable, coloured from the same palette
# the model material uses so the icon and the world object read as one thing.
ICONS=[(entry[0],entry[5][2]) for entry in harvestables.CATALOGUE]
ICON_COLUMNS=8
ICON_ROWS=(len(ICONS)+ICON_COLUMNS-1)//ICON_COLUMNS
HARVESTABLE_ITEM_BASE=1100  # equipment owns 1000-1099
def icon_pixel(idx,x,y):
    if idx>=len(ICONS): return (0,0,0,0)
    name,c=ICONS[idx];entry=harvestables.BY_ID[name];kind=entry[2]
    base=entry[5][0]
    dx=x-32;dy=y-32;r=(dx*dx+dy*dy)**.5
    if kind in ('fibre','crop'): inside=abs(dx)<5+max(0,dy//4) and -24<dy<20
    elif kind in ('flora','herb'): inside=r<19 or (abs(dx)<4 and dy>0)
    elif kind=='crystal': inside=abs(dx)<max(3,17-abs(dy)//2) and -24<dy<20
    elif kind=='fungus': inside=(dy<0 and r<19) or (abs(dx)<6 and 0<=dy<20)
    elif kind=='aquatic': inside=abs(dx)<max(4,16-abs(dy)//3) and -22<dy<20
    elif kind=='resin': inside=r<17 and dy>-14
    elif kind=='fuel': inside=r<18 and abs(dx)+abs(dy)<26
    else: inside=r<19
    if not inside: return (0,0,0,0)
    # Shade from an upper-left key light and darken the rim so the icons read
    # as objects at inventory size instead of flat colour chips.
    lit=max(0.0,min(1.0,0.62-(dx*0.020+dy*0.024)+(1.0-min(1.0,r/22.0))*0.30))
    rim=min(1.0,max(0.0,(r-14.0)/6.0))
    col=tuple(int(b+(q-b)*(0.30+0.70*lit)) for q,b in zip(c,base))
    col=tuple(int(q*(1.0-0.42*rim)) for q in col)
    return (*(max(0,min(255,q)) for q in col),255)

def main():
    runtime=ROOT/'runtime';source=ROOT/'source-obj';manifest=[]
    harvestables.write_models(runtime,source)
    for name,(build,a,b) in ASSETS.items():
        texture=runtime/'3dobjects/nymara'/f'{name}.png'
        (four_gates_tex if name.startswith('four_gates_') else tex)(texture,a,b)
        e3d(runtime/'3dobjects/nymara'/f'{name}.e3d',texture.name,build);obj(source/f'{name}.obj',build,name,texture.name)
        manifest.append({'id':name,'model':f'3dobjects/nymara/{name}.e3d','texture':f'3dobjects/nymara/{name}.png','source':f'source-obj/{name}.obj'})
    for idx,(name,c) in enumerate(ICONS): png(runtime/f'textures/nymara/icons/{name}.png',64,64,lambda x,y,j=idx:icon_pixel(j,x,y))
    png(runtime/'textures/nymara/items_nymara.png',ICON_COLUMNS*64,ICON_ROWS*64,
        lambda x,y: icon_pixel((x//64)+(y//64)*ICON_COLUMNS,x%64,y%64))
    # Decorative ground flora replaces the old harvestable `.2d` sprites: a
    # harvest node has to be a 3D object before the client will flag it
    # harvestable, and reusing inventory icons as world sprites never looked
    # like foliage.
    defs=harvestables.write_flora(runtime)
    (runtime/'nymara_assets.json').write_text(json.dumps({'schema':2,'objects':manifest,'objects_2d':defs,
      'harvestables':[{'item_id':HARVESTABLE_ITEM_BASE+i,'image_id':85+i,'id':n,
                       'label':harvestables.BY_ID[n][1],'kind':harvestables.BY_ID[n][2],
                       'tier':harvestables.BY_ID[n][3],'regions':list(harvestables.BY_ID[n][4]),
                       'model':harvestables.model_path(n),
                       'icon':f'textures/nymara/icons/{n}.png'} for i,(n,_) in enumerate(ICONS)]},indent=2)+'\n')
    (ROOT/'provenance.json').write_text(json.dumps({'schema':1,'assets':[{'path':'runtime/3dobjects/nymara/*','source':'generate_nymara_pack.py','author':'Eloria project','license':'CC-BY-4.0','description':'Original procedural Nymara E3D models and textures'},{'path':'runtime/textures/nymara/*','source':'generate_nymara_pack.py','author':'Eloria project','license':'CC-BY-4.0','description':'Original procedural Nymara inventory icons and atlas'},{'path':'runtime/2dobjects/nymara/flora/*','source':'eloria-assets/tools/harvestables.py','author':'Eloria project','license':'CC-BY-4.0','description':'Original procedural Nymara ground-flora sprites and .2d definitions'}]},indent=2)+'\n')
    (ROOT/'README.md').write_text(f'''# Nymara native asset pack\n\nGenerated for `eloria-client` branch `feature/independent-eloria-client`.\n\n## Contents\n\n- `runtime/3dobjects/nymara/`: {len(ASSETS)} native E3D scenery models and PNG textures.\n- `runtime/3dobjects/nymara/` harvest nodes: {len(harvestables.CATALOGUE)} authored harvestable models with 256px materials.\n- `runtime/2dobjects/nymara/flora/`: {len(harvestables.FLORA)} decorative ground-flora `.2d` definitions and a shared alpha atlas.\n- `runtime/textures/nymara/icons/`: {len(ICONS)} individual 64x64 RGBA item icons.\n- `runtime/textures/nymara/items_nymara.png`: {ICON_COLUMNS*64}x{ICON_ROWS*64} icon atlas.\n- `runtime/nymara_assets.json`: stable paths and item IDs.\n- `source-obj/`: editable OBJ/MTL source for every 3D object.\n- `generate_nymara_pack.py`: deterministic regeneration source.\n\nCopy the contents of `runtime/` into the generated Eloria data directory. E3D and `.2d` files can be placed directly by the bundled map editor. The JSON catalog is intended for client/server registration.\n\nThese are functional low-poly production proxies based on the approved Nymara art direction, not automatic 3D reconstructions of the painted concept sheets. They establish names, scale, pivots, native formats, texture paths, and provenance for later art refinement.\n''')
    readme=ROOT/'README.md'
    readme.write_text(readme.read_text().replace(
        'These are functional low-poly production proxies based on the approved Nymara art direction, not automatic 3D reconstructions of the painted concept sheets. They establish names, scale, pivots, native formats, texture paths, and provenance for later art refinement.',
        'The shared regional catalog contains functional low-poly production proxies.\n'
        'The Four Gates civic wall, tower, bridge, pavilion and park tree are the first\n'
        'refined regional kit: they use intentional silhouette topology, 256px authored\n'
        'procedural materials, stable scale and pivots, native E3D output, and editable\n'
        'OBJ/MTL source. They are original interpretations of the approved art direction,\n'
        'not automatic reconstructions of the concept paintings.\n\n'
        'Harvest nodes are held to the same standard and are authored in\n'
        'eloria-assets/tools/harvestables.py, the single catalogue the models, icons,\n'
        'harvestable.lst entries and map placements all read from. Foliage nodes declare\n'
        'a transparent material so the client alpha-tests them and keeps both faces.\n'
        'See docs/harvestable-audit.md.'))
    (ROOT/'generate_nymara_pack.py').write_text(Path(__file__).read_text())
    print(f'generated {len(ASSETS)} E3D models, {len(ICONS)} icons, OBJ sources and manifests in {ROOT}')
if __name__=='__main__': main()

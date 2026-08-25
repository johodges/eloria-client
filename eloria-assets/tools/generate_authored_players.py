#!/usr/bin/env python3
"""Generate rigged Cal3D players from cleaned authored model sources."""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import shutil
import struct
import xml.etree.ElementTree as ET
import zlib

from generate_characters import BONES, VERSION, _binary_header, _binary_string, write_cal


SOURCE = Path(__file__).resolve().parents[1] / "source/player_models"
MODELS = {
    "glasswarden_female": 4, "glasswarden_male": 5,
    "ssarathi_female": 41, "ssarathi_male": 42,
}
SECTION_NAMES = ("shirt", "legs", "boots", "head")


def read_emesh(path):
    data=path.read_bytes()
    if data[:8] != b"EMSH\x01\x00\x00\x00": raise ValueError(f"invalid authored mesh: {path}")
    raw_size,compressed_size=struct.unpack_from("<II",data,8)
    raw=zlib.decompress(data[16:16+compressed_size])
    if len(raw)!=raw_size: raise ValueError(f"authored mesh size mismatch: {path}")
    vertices,faces=struct.unpack_from("<II",raw); offset=8
    positions=[struct.unpack_from("<3f",raw,offset+i*12) for i in range(vertices)]; offset+=vertices*12
    normals=[struct.unpack_from("<3f",raw,offset+i*12) for i in range(vertices)]; offset+=vertices*12
    uvs=[struct.unpack_from("<2f",raw,offset+i*8) for i in range(vertices)]; offset+=vertices*8
    triangles=[struct.unpack_from("<3I",raw,offset+i*12) for i in range(faces)]
    return positions,normals,uvs,triangles


def blend(a,b,t):
    t=max(0.,min(1.,t)); return [(a,1-t),(b,t)]


def influences(position):
    x,y,z=position; side=x>0; upper_arm=6 if side else 4; lower_arm=7 if side else 5
    hand=17 if side else 16; thigh=11 if side else 8; shin=12 if side else 9; foot=13 if side else 10
    # The source bodies are in a natural A pose. Detect arms outside the ribcage
    # and project down their shoulder-to-hand line.
    arm_limit=.19 + max(0.,z-.75)*.08
    if abs(x)>arm_limit and .55<z<1.58:
        t=max(0.,min(1.,(1.52-z)/.82))
        if t<.43: return blend(upper_arm,lower_arm,t/.43*.45)
        if t<.82: return blend(lower_arm,hand,(t-.43)/.39*.35)
        return [(hand,1.)]
    if z>1.48:
        return blend(26,3,(z-1.48)/.16)
    if z<.18: return [(foot,1.)]
    if z<.56: return blend(shin,foot,max(0.,(.25-z)/.08)) if z<.25 else [(shin,1.)]
    if z<.94: return blend(thigh,shin,max(0.,(.70-z)/.14)) if z<.70 else [(thigh,1.)]
    if z<1.08: return blend(1,2,(z-.94)/.14)
    if z<1.35: return [(2,1.)]
    return blend(2,25,(z-1.35)/.13)


def section_for_triangle(points):
    z=sum(p[2] for p in points)/3; x=sum(abs(p[0]) for p in points)/3
    if z>1.48: return "head"
    if z<.27: return "boots"
    if z<.96 and x<.25: return "legs"
    return "shirt"


def compact_section(positions,normals,uvs,faces):
    used=sorted({i for face in faces for i in face}); remap={old:new for new,old in enumerate(used)}
    vertices=[(positions[i],normals[i],uvs[i],influences(positions[i])) for i in used]
    return vertices,[tuple(remap[i] for i in face) for face in faces]


def write_mesh(path,vertices,faces):
    root=ET.Element("MESH",NUMSUBMESH="1")
    sub=ET.SubElement(root,"SUBMESH",NUMVERTICES=str(len(vertices)),NUMFACES=str(len(faces)),
                      MATERIAL="0",NUMLODSTEPS="0",NUMSPRINGS="0",NUMTEXCOORDS="1")
    for ident,(pos,norm,uv,weights) in enumerate(vertices):
        vertex=ET.SubElement(sub,"VERTEX",ID=str(ident),NUMINFLUENCES=str(len(weights)))
        ET.SubElement(vertex,"POS").text="%g %g %g"%pos
        ET.SubElement(vertex,"NORM").text="%g %g %g"%norm
        ET.SubElement(vertex,"TEXCOORD").text="%g %g"%uv
        for bone,weight in weights: ET.SubElement(vertex,"INFLUENCE",ID=str(bone)).text="%g"%weight
    for face in faces: ET.SubElement(sub,"FACE",VERTEXID="%d %d %d"%face)
    write_cal(path,"XMF",root)
    data=_binary_header("CMF"); data.extend(struct.pack("<i",1))
    data.extend(struct.pack("<6i",0,len(vertices),len(faces),0,0,1))
    for pos,norm,uv,weights in vertices:
        data.extend(struct.pack("<3f3fii2fi",*pos,*norm,-1,0,*uv,len(weights)))
        for bone,weight in weights: data.extend(struct.pack("<if",bone,weight))
    for face in faces: data.extend(struct.pack("<3i",*face))
    path.with_suffix(".cmf").write_bytes(data)


def fitted_bones(name):
    female=name.endswith("female"); ssarathi=name.startswith("ssarathi")
    width=(.94 if female else 1.05)*(1.04 if ssarathi else 1.)
    result=[]
    lateral={4,6,8,11,16,17,27,28,29,30,31,32,33,34,35,36}
    for ident,(bone,parent,pos) in enumerate(BONES):
        x,y,z=pos
        if ident in lateral: x*=width
        result.append((bone,parent,(x,y,z)))
    return tuple(result)


def skeleton(path,bones):
    children={i:[] for i in range(len(bones))}
    absolute=[]
    for i,(_,parent,pos) in enumerate(bones):
        if parent>=0: children[parent].append(i)
        base=(0.,0.,0.) if parent<0 else absolute[parent]
        absolute.append(tuple(base[q]+pos[q] for q in range(3)))
    root=ET.Element("SKELETON",NUMBONES=str(len(bones)))
    data=_binary_header("CSF"); data.extend(struct.pack("<i",len(bones)))
    for i,(name,parent,pos) in enumerate(bones):
        bone=ET.SubElement(root,"BONE",ID=str(i),NAME=name,NUMCHILD=str(len(children[i])))
        ET.SubElement(bone,"TRANSLATION").text="%g %g %g"%pos; ET.SubElement(bone,"ROTATION").text="0 0 0 1"
        ET.SubElement(bone,"LOCALTRANSLATION").text="%g %g %g"%tuple(-v for v in absolute[i]); ET.SubElement(bone,"LOCALROTATION").text="0 0 0 1"
        ET.SubElement(bone,"PARENTID").text=str(parent)
        for child in children[i]: ET.SubElement(bone,"CHILDID").text=str(child)
        data.extend(_binary_string(name)); data.extend(struct.pack("<3f4f3f4f",*pos,0.,0.,0.,1.,*tuple(-v for v in absolute[i]),0.,0.,0.,1.))
        data.extend(struct.pack("<ii",parent,len(children[i])))
        if children[i]: data.extend(struct.pack(f"<{len(children[i])}i",*children[i]))
    write_cal(path,"XSF",root); path.with_suffix(".csf").write_bytes(data)


def quaternion(axis,angle):
    values=[0.,0.,0.]; values[axis]=math.sin(angle/2); return (*values,math.cos(angle/2))


def animation(path,bones,duration,poses):
    tracks=sorted({bone for _,frame in poses for bone in frame})
    root=ET.Element("ANIMATION",DURATION=str(duration),NUMTRACKS=str(len(tracks)))
    data=_binary_header("CAF"); data.extend(struct.pack("<fi",duration,len(tracks)))
    for bone in tracks:
        track=ET.SubElement(root,"TRACK",BONEID=str(bone),NUMKEYFRAMES=str(len(poses)))
        data.extend(struct.pack("<ii",bone,len(poses)))
        for time,frame in poses:
            axis,angle=frame.get(bone,(0,0.)); rotation=quaternion(axis,angle)
            key=ET.SubElement(track,"KEYFRAME",TIME=str(time)); ET.SubElement(key,"TRANSLATION").text="%g %g %g"%bones[bone][2]
            ET.SubElement(key,"ROTATION").text="%g %g %g %g"%rotation
            data.extend(struct.pack("<f3f4f",time,*bones[bone][2],*rotation))
    write_cal(path,"XAF",root); path.with_suffix(".caf").write_bytes(data)


ANIMATIONS={
 "idle":(3.,[(0,{2:(0,-.025)}),(1.5,{2:(0,.025),1:(2,.018)}),(3.,{2:(0,-.025)})]),
 "idle2":(4.,[(0,{1:(2,-.035),4:(0,.08)}),(2.,{1:(2,.04),6:(0,.10)}),(4.,{1:(2,-.035),4:(0,.08)})]),
 "walk":(1.,[(0,{4:(0,.42),6:(0,-.42),8:(0,-.55),11:(0,.55)}),(.5,{4:(0,-.42),6:(0,.42),8:(0,.55),11:(0,-.55)}),(1.,{4:(0,.42),6:(0,-.42),8:(0,-.55),11:(0,.55)})]),
 "run":(.7,[(0,{4:(0,.72),6:(0,-.72),8:(0,-.82),11:(0,.82)}),(.35,{4:(0,-.72),6:(0,.72),8:(0,.82),11:(0,-.82)}),(.7,{4:(0,.72),6:(0,-.72),8:(0,-.82),11:(0,.82)})]),
 "combat_idle":(2.,[(0,{4:(0,-.38),6:(0,-.38),5:(0,-.30),7:(0,-.30)}),(1.,{2:(2,.04),4:(0,-.34),6:(0,-.42)}),(2.,{4:(0,-.38),6:(0,-.38),5:(0,-.30),7:(0,-.30)})]),
 "attack":(.75,[(0,{2:(2,-.12),6:(0,-.45)}),(.34,{2:(2,.38),6:(0,1.35),7:(0,.55)}),(.75,{2:(2,-.12),6:(0,-.45)})]),
 "cast":(1.2,[(0,{4:(0,-.25),6:(0,-.25)}),(.6,{4:(2,-.72),6:(2,.72),5:(0,-.55),7:(0,-.55)}),(1.2,{4:(0,-.25),6:(0,-.25)})]),
 "pain":(.5,[(0,{}),(.22,{2:(0,-.30),4:(2,-.18),6:(2,.18)}),(.5,{})]),
 "die":(1.35,[(0,{}),(.65,{1:(0,-.65),2:(0,-.55)}),(1.35,{1:(0,-1.42),2:(0,-1.10)})]),
 "sit_down":(.9,[(0,{}),(.9,{8:(0,1.28),9:(0,-1.20),11:(0,1.28),12:(0,-1.20)})]),
 "sit":(2.,[(0,{8:(0,1.28),9:(0,-1.20),11:(0,1.28),12:(0,-1.20)}),(1.,{2:(0,.04),8:(0,1.28),9:(0,-1.20),11:(0,1.28),12:(0,-1.20)}),(2.,{8:(0,1.28),9:(0,-1.20),11:(0,1.28),12:(0,-1.20)})]),
 "stand_up":(.9,[(0,{8:(0,1.28),9:(0,-1.20),11:(0,1.28),12:(0,-1.20)}),(.9,{})]),
 "harvest":(1.1,[(0,{}),(.55,{2:(0,.42),4:(0,.90),6:(0,.90)}),(1.1,{})]),
 "pick":(.85,[(0,{}),(.45,{1:(0,.45),2:(0,.52),6:(0,.35)}),(.85,{})]),
 "drop":(.7,[(0,{6:(0,.25)}),(.35,{6:(0,.85),7:(0,.35)}),(.7,{})]),
}


def png_rgba(path):
    data=path.read_bytes()
    if data[:8]!=b"\x89PNG\r\n\x1a\n": raise ValueError(f"invalid PNG: {path}")
    offset=8; payload=bytearray(); width=height=None
    while offset<len(data):
        size=struct.unpack_from(">I",data,offset)[0]; kind=data[offset+4:offset+8]; chunk=data[offset+8:offset+8+size]; offset+=12+size
        if kind==b"IHDR": width,height,depth,color,_,_,_=struct.unpack(">IIBBBBB",chunk)
        elif kind==b"IDAT": payload.extend(chunk)
        elif kind==b"IEND": break
    if depth!=8 or color!=6: raise ValueError(f"PNG must be 8-bit RGBA: {path}")
    raw=zlib.decompress(payload); stride=width*4; rows=[]; previous=bytearray(stride); at=0
    for _ in range(height):
        mode=raw[at]; at+=1; scan=bytearray(raw[at:at+stride]); at+=stride
        for x in range(stride):
            left=scan[x-4] if x>=4 else 0; up=previous[x]; ul=previous[x-4] if x>=4 else 0
            if mode==1: scan[x]=(scan[x]+left)&255
            elif mode==2: scan[x]=(scan[x]+up)&255
            elif mode==3: scan[x]=(scan[x]+((left+up)//2))&255
            elif mode==4:
                p=left+up-ul; pa=abs(p-left);pb=abs(p-up);pc=abs(p-ul);scan[x]=(scan[x]+(left if pa<=pb and pa<=pc else up if pb<=pc else ul))&255
            elif mode!=0: raise ValueError("unsupported PNG filter")
        rows.append(bytes(scan)); previous=scan
    return width,height,b"".join(rows)


def write_dds(source,path):
    width,height,rgba=png_rgba(source); levels=[]; w,h=width,height; pixels=rgba
    for _ in range(5):
        levels.append((w,h,pixels))
        if w==1 and h==1: break
        nw,nh=max(1,w//2),max(1,h//2); out=bytearray(nw*nh*4)
        for y in range(nh):
            for x in range(nw):
                samples=[]
                for dy in (0,1):
                    for dx in (0,1):
                        sx=min(w-1,x*2+dx);sy=min(h-1,y*2+dy);samples.append(pixels[(sy*w+sx)*4:(sy*w+sx+1)*4])
                for c in range(4): out[(y*nw+x)*4+c]=sum(s[c] for s in samples)//4
        w,h,pixels=nw,nh,bytes(out)
    header=[124,0x0002100F,height,width,width*4,0,len(levels)]+[0]*11+[32,0x41,0,32,0x00FF0000,0x0000FF00,0x000000FF,0xFF000000]+[0x401008,0,0,0,0]
    body=bytearray()
    for w,h,pixels in levels:
        for i in range(0,len(pixels),4): body.extend((pixels[i+2],pixels[i+1],pixels[i],pixels[i+3]))
    path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(b"DDS "+struct.pack("<31I",*header)+body)


def patch_actor_defs(path,name,actor_id,texture):
    tree=ET.parse(path); root=tree.getroot(); actor=root.find(f"actor[@id='{actor_id}']")
    if actor is None: raise ValueError(f"missing player actor {actor_id}")
    actor.find("skeleton").text=f"actors/playable/{name}.csf"
    for tag in ("shirt","legs","boots","head"):
        for part in actor.findall(tag):
            mesh=part.find("mesh")
            if mesh is not None:
                suffix=f"head_{part.attrib['id']}" if tag=="head" else tag
                mesh.text=f"actors/playable/{name}_{suffix}.cmf"
            for child in part:
                if child.tag in ("arms","torso","skin"): child.text=texture
    for tag in ("hskin","hair","eyes"):
        for part in actor.findall(tag):
            if len(part):
                for child in part: child.text=texture
            else: part.text=texture
    frames=actor.find("frames"); mapping={
      "CAL_idle":"idle","CAL_idle2":"idle2","CAL_walk":"walk","CAL_run":"run",
      "CAL_combat_idle":"combat_idle","CAL_attack_up_1":"attack","CAL_attack_down_1":"attack",
      "CAL_attack_cast":"cast","CAL_pain1":"pain","CAL_pain2":"pain","CAL_die1":"die","CAL_die2":"die",
      "CAL_idle_sit":"sit","CAL_sit_down":"sit_down","CAL_stand_up":"stand_up",
      "CAL_harvest":"harvest","CAL_pick":"pick","CAL_drop":"drop"}
    existing={child.tag:child for child in frames}
    for tag,filename in mapping.items():
        node=existing.get(tag)
        if node is None: node=ET.SubElement(frames,tag)
        kind=0 if tag in ("CAL_idle","CAL_idle2","CAL_walk","CAL_run","CAL_combat_idle","CAL_idle_sit") else 1
        node.text=f"animations/playable/{name}/{filename}.caf {kind}"
    path.write_text('<?xml version="1.0"?>\n'+ET.tostring(root,encoding="unicode")+'\n',encoding="utf-8")


def generate_model(root,name,actor_id):
    positions,normals,uvs,triangles=read_emesh(SOURCE/f"{name}.emesh")
    split={section:[] for section in SECTION_NAMES}
    for face in triangles: split[section_for_triangle([positions[i] for i in face])].append(face)
    base=root/"actors/playable"
    all_vertices=[(p,n,u,influences(p)) for p,n,u in zip(positions,normals,uvs)]
    write_mesh(base/f"{name}_body.xmf",all_vertices,triangles)
    for section in SECTION_NAMES:
        vertices,faces=compact_section(positions,normals,uvs,split[section])
        write_mesh(base/f"{name}_{section}.xmf",vertices,faces)
    # The authored source supplies one intentional head per sex; retain the
    # five protocol slots without fabricating distorted alternatives.
    for variant in range(5):
        shutil.copy2(base/f"{name}_head.xmf",base/f"{name}_head_{variant}.xmf")
        shutil.copy2(base/f"{name}_head.cmf",base/f"{name}_head_{variant}.cmf")
    bones=fitted_bones(name); skeleton(base/f"{name}.xsf",bones)
    anim_dir=root/f"animations/playable/{name}"
    for anim,(duration,poses) in ANIMATIONS.items(): animation(anim_dir/f"{anim}.xaf",bones,duration,poses)
    texture=f"actors/playable/{name}.dds"; write_dds(SOURCE/f"{name}.png",root/texture)
    patch_actor_defs(root/"actor_defs/actor_defs.xml",name,actor_id,texture)
    print(f"{name}: {len(positions)} vertices, {len(triangles)} triangles, {sum(len(v) for v in split.values())} assigned")


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("output",nargs="?",default="build/eloria-data")
    root=Path(parser.parse_args().output)
    for name,actor_id in MODELS.items(): generate_model(root,name,actor_id)


if __name__=="__main__": main()

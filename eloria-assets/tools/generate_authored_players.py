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
import json

from generate_characters import (BONES, VERSION, _binary_header, _binary_string, write_cal,
                                 HAIR, EYES, CLOTH, PANTS, BOOTS, CULTURES)


SOURCE = Path(__file__).resolve().parents[1] / "source/player_models"
MODELS = {
    "luminous_female": 0, "luminous_male": 1,
    "glasswarden_female": 4, "glasswarden_male": 5,
    "ssarathi_female": 41, "ssarathi_male": 42,
}
SECTION_NAMES = ("shirt", "legs", "boots", "head")
ATLAS_REGIONS = {
    "head": (34, 0, 32, 32), "hair": (0, 0, 34, 48),
    "eyes": (50, 32, 6, 6), "hands": (34, 32, 16, 16),
    "arms": (0, 48, 40, 40), "torso": (79, 74, 49, 54),
    "boots": (0, 88, 39, 40), "legs": (39, 88, 40, 40),
}


def read_emesh(path):
    data=path.read_bytes()
    if data[:8] not in (b"EMSH\x01\x00\x00\x00",b"EMSH\x02\x00\x00\x00"):
        raise ValueError(f"invalid authored mesh: {path}")
    weighted=data[4]==2
    raw_size,compressed_size=struct.unpack_from("<II",data,8)
    raw=zlib.decompress(data[16:16+compressed_size])
    if len(raw)!=raw_size: raise ValueError(f"authored mesh size mismatch: {path}")
    vertices,faces=struct.unpack_from("<II",raw); offset=8
    positions=[struct.unpack_from("<3f",raw,offset+i*12) for i in range(vertices)]; offset+=vertices*12
    normals=[struct.unpack_from("<3f",raw,offset+i*12) for i in range(vertices)]; offset+=vertices*12
    uvs=[struct.unpack_from("<2f",raw,offset+i*8) for i in range(vertices)]; offset+=vertices*8
    weights=None
    if weighted:
        weights=[]
        for i in range(vertices):
            values=struct.unpack_from("<4H4f",raw,offset+i*24)
            weights.append([(bone,weight) for bone,weight in zip(values[:4],values[4:]) if weight>1e-6])
        offset+=vertices*24
    triangles=[struct.unpack_from("<3I",raw,offset+i*12) for i in range(faces)]
    return positions,normals,uvs,triangles,weights


def blend(a,b,t):
    t=max(0.,min(1.,t)); return [(a,1-t),(b,t)]


def influences(position):
    x,y,z=position; side=x>0; upper_arm=6 if side else 4; lower_arm=7 if side else 5
    hand=17 if side else 16; thigh=11 if side else 8; shin=12 if side else 9; foot=13 if side else 10
    # The source bodies are in a natural A pose. Detect arms outside the ribcage
    # and project down their shoulder-to-hand line.
    # Keep hips and outer thighs out of the arm chain.  The old .19 cutoff
    # crossed the authored characters' leg silhouette around knee height and
    # bound individual trouser vertices to hand/forearm bones.
    arm_limit=.28 if z<1.00 else .22+max(0.,z-1.00)*.04
    # Back panels, coats, and shoulder ornaments can extend past the arm
    # silhouette.  Keep them on the torso rather than letting arm animation
    # pull them into long spikes.
    if y>.20 and z>1.05:
        return blend(1,2,(z-1.05)/.20)
    if (1.08<z<1.42 and -.18<y<.20 and
            arm_limit-.04<abs(x)<=arm_limit+.04):
        return blend(2,upper_arm,(abs(x)-(arm_limit-.04))/.08)
    if abs(x)>arm_limit and -.18<y<.20 and .55<z<1.58:
        if z>1.38: return blend(2,upper_arm,(1.58-z)/.20)
        if z>1.10: return [(upper_arm,1.)]
        if z>.80: return blend(upper_arm,lower_arm,(1.10-z)/.30)
        if z>.62: return blend(lower_arm,hand,(.80-z)/.18)
        return [(hand,1.)]
    if z>1.48:
        return blend(26,3,(z-1.48)/.16)
    if z<.18: return [(foot,1.)]
    if z<.30: return blend(foot,shin,(z-.18)/.12)
    if z<.56: return [(shin,1.)]
    if z<.76: return blend(shin,thigh,(z-.56)/.20)
    if z<.94:
        if z>.78 and abs(x)<.08:
            pelvis_weight=(z-.78)/.16*(1.-abs(x)/.08)
            return blend(thigh,1,pelvis_weight)
        return [(thigh,1.)]
    if z<1.08: return blend(thigh,1,(z-.94)/.14)
    if z<1.35: return [(2,1.)]
    return blend(2,25,(z-1.35)/.13)


def clean_mesh(positions,normals,uvs,triangles):
    """Validate the checked-in cleaned topology without collapsing its surface.

    The authoring importer has already clustered the scan.  Clustering it a
    second time merged opposite sides of thin garments and facial features;
    the subsequent winding filter then removed valid triangles and left holes.
    """
    out_positions=list(positions); out_uvs=list(uvs); out_normals=[]
    for normal in normals:
        length=math.sqrt(sum(value*value for value in normal)) or 1.
        out_normals.append(tuple(value/length for value in normal))
    out_faces=[]; seen=set()
    for face in triangles:
        mapped=tuple(face)
        if len(set(mapped))<3: continue
        canonical=tuple(sorted(mapped))
        if canonical in seen: continue
        a,b,c=mapped;pa,pb,pc=(out_positions[index] for index in mapped)
        ab=tuple(pb[i]-pa[i] for i in range(3));ac=tuple(pc[i]-pa[i] for i in range(3))
        cross=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
        if sum(value*value for value in cross)<=1e-20: continue
        average=tuple(sum(out_normals[index][i] for index in mapped) for i in range(3))
        if sum(cross[i]*average[i] for i in range(3))<0:
            mapped=(a,c,b); cross=tuple(-value for value in cross)
        # EL's Cal3D validation and face setup use the first corner normal,
        # rather than the averaged triangle normal.  Cyclically rotate the
        # face so the best-aligned corner is first; rotation preserves winding
        # and topology and avoids deleting tangential-but-valid source faces.
        dots=[sum(cross[i]*out_normals[index][i] for i in range(3))
              for index in mapped]
        first=max(range(3),key=dots.__getitem__)
        if dots[first]<=0.:
            raise ValueError(f"authored face normals are tangential: {mapped}")
        mapped=mapped[first:]+mapped[:first]
        seen.add(canonical); out_faces.append(mapped)
    return out_positions,out_normals,out_uvs,out_faces


def section_for_triangle(points):
    z=sum(p[2] for p in points)/3; x=sum(abs(p[0]) for p in points)/3
    if z>1.48: return "head"
    if z<.27: return "boots"
    if z<.96 and x<.25: return "legs"
    return "shirt"


def atlas_uv(role,uv):
    x,y,w,h=ATLAS_REGIONS[role]
    # Compositor rectangles use image coordinates (origin at top-left), while
    # Cal3D/OpenGL texture V grows from the bottom.  glTF UVs also address the
    # source image from its top edge, so convert both conventions here.
    return ((x+uv[0]*w)/128.,(128.-y-uv[1]*h)/128.)


def texture_role(section, points):
    """Choose one compositor region for the whole triangle.

    A Cal3D triangle must never interpolate between unrelated atlas rectangles.
    Vertices shared by triangles with different roles are duplicated below.
    """
    if section != "shirt": return section
    x=sum(abs(point[0]) for point in points)/3
    z=sum(point[2] for point in points)/3
    if x>.30 and z<.82: return "hands"
    if x>.22 and z<1.49: return "arms"
    return "torso"


def compatible_weights(left, right):
    groups=({1,2,25,26,3,27,28}, {4,5,16,18,20,29,30,32,33},
            {6,7,17,19,21,31,34,35}, {8,9,10,36}, {11,12,13})
    a={bone for bone,_ in left}; b={bone for bone,_ in right}
    return any(a & group and b & group for group in groups)


def compact_section(positions,normals,uvs,faces,section,source_weights=None):
    vertices=[]; compact_faces=[]; remap={}
    for face in faces:
        role=texture_role(section,[positions[index] for index in face]); mapped=[]
        for index in face:
            key=(index,role)
            if key not in remap:
                weights=source_weights[index] if source_weights is not None else influences(positions[index]); remap[key]=len(vertices)
                vertices.append((positions[index],normals[index],atlas_uv(role,uvs[index]),weights))
            mapped.append(remap[key])
        compact_faces.append(tuple(mapped))
    neighbors=[set() for _ in vertices]
    for face in compact_faces:
        for index in face: neighbors[index].update(other for other in face if other!=index)
    # Diffuse a small amount of weight across actual triangle adjacency.  This
    # preserves rigid regions but prevents one triangle from joining three
    # unrelated bones and exploding into a sheet during animation.
    smoothed=[]
    for index,vertex in enumerate(vertices):
        own=dict(vertex[3]); combined={bone:.65*weight for bone,weight in own.items()}
        adjacent=neighbors[index]
        if adjacent:
            compatible=[other for other in adjacent if compatible_weights(vertex[3],vertices[other][3])]
            scale=.35/len(compatible) if compatible else 0.
            for other in compatible:
                for bone,weight in vertices[other][3]: combined[bone]=combined.get(bone,0.)+scale*weight
        selected=sorted(combined.items(),key=lambda item:item[1],reverse=True)[:4]
        total=sum(weight for _,weight in selected) or 1.
        smoothed.append((*vertex[:3],[(bone,weight/total) for bone,weight in selected]))
    return smoothed,compact_faces


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
    culture_scale=(1.07 if ssarathi else 1.03 if name.startswith("glasswarden") else .98)
    width=(.94 if female else 1.05)*culture_scale
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


def write_dds(source,path,target_size=None):
    width,height,rgba=source if isinstance(source,tuple) else png_rgba(source)
    levels=[]; w,h=width,height; pixels=rgba
    if target_size is not None:
        target_width,target_height=target_size; resized=bytearray(target_width*target_height*4)
        for y in range(target_height):
            sy=min(height-1,int((y+.5)*height/target_height))
            for x in range(target_width):
                sx=min(width-1,int((x+.5)*width/target_width))
                resized[(y*target_width+x)*4:(y*target_width+x+1)*4]=rgba[(sy*width+sx)*4:(sy*width+sx+1)*4]
        width,height,rgba=target_width,target_height,bytes(resized);w,h,pixels=width,height,rgba
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


def recolor(source,target,size):
    source_width,source_height,rgba=source; width,height=size; out=bytearray(width*height*4)
    for y in range(height):
      sy=min(source_height-1,int((y+.5)*source_height/height))
      for x in range(width):
        sx=min(source_width-1,int((x+.5)*source_width/width)); source_offset=(sy*source_width+sx)*4
        offset=(y*width+x)*4; red,green,blue,alpha=rgba[source_offset:source_offset+4]
        light=(red*54+green*183+blue*19)//256
        for channel,value in enumerate(target):
            out[offset+channel]=max(0,min(255,value+(light-128)*3//4))
        out[offset+3]=alpha
    return width,height,bytes(out)


def write_luminous_variants(root,name,source):
    directory=root/"actors/playable"
    skins=(*CULTURES["luminous"],CULTURES["luminous"][1],(55,79,105),(222,224,216))
    for index,color in enumerate(skins):
        write_dds(recolor(source,color,(64,64)),directory/f"{name}_skin_{index}_hands.dds")
        write_dds(recolor(source,color,(128,128)),directory/f"{name}_skin_{index}_head.dds")
    for index,color in enumerate(HAIR): write_dds(recolor(source,color,(136,192)),directory/f"{name}_hair_{index}.dds")
    for index,color in enumerate(EYES): write_dds(recolor(source,color,(24,24)),directory/f"{name}_eyes_{index}.dds")
    for index,color in enumerate(CLOTH):
        write_dds(recolor(source,color,(160,160)),directory/f"{name}_shirt_{index}_arms.dds")
        write_dds(recolor(source,color,(196,216)),directory/f"{name}_shirt_{index}_torso.dds")
    for index,color in enumerate(PANTS): write_dds(recolor(source,color,(160,160)),directory/f"{name}_pants_{index}.dds")
    for index,color in enumerate(BOOTS): write_dds(recolor(source,color,(156,160)),directory/f"{name}_boots_{index}.dds")


def patch_actor_defs(path,name,actor_id,texture,preserve_customization=False):
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
                if not preserve_customization and child.tag in ("arms","torso","skin"):
                    role=child.tag if child.tag!="skin" else tag
                    child.text=f"actors/playable/{name}_{role}.dds"
    for tag in (() if preserve_customization else ("hskin","hair","eyes")):
        for part in actor.findall(tag):
            if len(part):
                for child in part: child.text=f"actors/playable/{name}_{child.tag}.dds"
            else: part.text=f"actors/playable/{name}_{tag}.dds"
    if name.startswith("luminous_"):
        for part in actor.findall("shirt"):
            ident=part.attrib["id"]
            part.find("arms").text=f"actors/playable/{name}_shirt_{ident}_arms.dds"
            part.find("torso").text=f"actors/playable/{name}_shirt_{ident}_torso.dds"
        for part in actor.findall("hskin"):
            ident=part.attrib["id"]
            part.find("hands").text=f"actors/playable/{name}_skin_{ident}_hands.dds"
            part.find("head").text=f"actors/playable/{name}_skin_{ident}_head.dds"
        for part in actor.findall("hair"):
            part.text=f"actors/playable/{name}_hair_{part.attrib['id']}.dds"
        for part in actor.findall("eyes"):
            part.text=f"actors/playable/{name}_eyes_{part.attrib['id']}.dds"
        for part in actor.findall("legs"):
            part.find("skin").text=f"actors/playable/{name}_pants_{part.attrib['id']}.dds"
        for part in actor.findall("boots"):
            part.find("skin").text=f"actors/playable/{name}_boots_{part.attrib['id']}.dds"
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


def read_universal_animations(path):
    data=path.read_bytes()
    if data[:8] != b"EANM\x01\0\0\0": raise ValueError(f"invalid animation source: {path}")
    raw_size=struct.unpack_from("<I",data,8)[0]; raw=zlib.decompress(data[12:])
    if len(raw)!=raw_size: raise ValueError(f"animation source size mismatch: {path}")
    return json.loads(raw)["clips"]


def imported_animation(path,bones,clip):
    tracks={int(bone):keys for bone,keys in clip["tracks"].items()}
    root=ET.Element("ANIMATION",DURATION=str(clip["duration"]),NUMTRACKS=str(len(tracks)))
    data=_binary_header("CAF"); data.extend(struct.pack("<fi",clip["duration"],len(tracks)))
    for bone,keys in sorted(tracks.items()):
        track=ET.SubElement(root,"TRACK",BONEID=str(bone),NUMKEYFRAMES=str(len(keys)))
        data.extend(struct.pack("<ii",bone,len(keys)))
        for time,rotation in keys:
            key=ET.SubElement(track,"KEYFRAME",TIME=str(time))
            ET.SubElement(key,"TRANSLATION").text="%g %g %g"%bones[bone][2]
            ET.SubElement(key,"ROTATION").text="%g %g %g %g"%tuple(rotation)
            data.extend(struct.pack("<f3f4f",time,*bones[bone][2],*rotation))
    write_cal(path,"XAF",root); path.with_suffix(".caf").write_bytes(data)


def generate_model(root,name,actor_id):
    positions,normals,uvs,triangles,source_weights=read_emesh(SOURCE/f"{name}.emesh")
    # Version imported Luminous runtime paths.  Besides making the provenance
    # explicit, this prevents an existing client/model cache from satisfying a
    # new actor definition with the legacy procedural meshes or old DDS files.
    runtime_name=f"{name}_quaternius_v2" if name.startswith("luminous_") else name
    source_vertices,source_faces=len(positions),len(triangles)
    positions,normals,uvs,triangles=clean_mesh(positions,normals,uvs,triangles)
    if len(triangles) < source_faces * .999:
        raise ValueError(f"authored topology unexpectedly lost faces: {name} "
                         f"{source_faces}->{len(triangles)}")
    split={section:[] for section in SECTION_NAMES}
    for face in triangles: split[section_for_triangle([positions[i] for i in face])].append(face)
    base=root/"actors/playable"; output_name=runtime_name
    all_vertices=[(p,n,u,source_weights[index] if source_weights is not None else influences(p))
                  for index,(p,n,u) in enumerate(zip(positions,normals,uvs))]
    write_mesh(base/f"{output_name}_body.xmf",all_vertices,triangles)
    for section in SECTION_NAMES:
        vertices,faces=compact_section(positions,normals,uvs,split[section],section,source_weights)
        write_mesh(base/f"{output_name}_{section}.xmf",vertices,faces)
    # The authored source supplies one intentional head per sex; retain the
    # five protocol slots without fabricating distorted alternatives.
    for variant in range(5):
        shutil.copy2(base/f"{output_name}_head.xmf",base/f"{output_name}_head_{variant}.xmf")
        shutil.copy2(base/f"{output_name}_head.cmf",base/f"{output_name}_head_{variant}.cmf")
    bones=fitted_bones(name); skeleton(base/f"{output_name}.xsf",bones)
    anim_dir=root/f"animations/playable/{output_name}"
    if name.startswith("luminous_"):
        clips=read_universal_animations(SOURCE/"luminous_universal.eanim")
        for anim,clip in clips.items(): imported_animation(anim_dir/f"{anim}.xaf",bones,clip)
    else:
        for anim,(duration,poses) in ANIMATIONS.items(): animation(anim_dir/f"{anim}.xaf",bones,duration,poses)
    texture=f"actors/playable/{output_name}.dds"
    # Retain the full atlas as a QA/reference artifact; runtime enhanced actors
    # consume the compositor-sized role textures below.
    source_texture=png_rgba(SOURCE/f"{name}.png")
    write_dds(source_texture,root/texture)
    for role,(_,_,width,height) in ATLAS_REGIONS.items():
        write_dds(source_texture,root/f"actors/playable/{output_name}_{role}.dds",(width*4,height*4))
    if name.startswith("luminous_"): write_luminous_variants(root,output_name,source_texture)
    patch_actor_defs(root/"actor_defs/actor_defs.xml",output_name,actor_id,texture,False)
    print(f"{name}: {source_vertices}->{len(positions)} vertices, {source_faces}->{len(triangles)} triangles, {sum(len(v) for v in split.values())} assigned")


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("output",nargs="?",default="build/eloria-data")
    root=Path(parser.parse_args().output)
    for name,actor_id in MODELS.items(): generate_model(root,name,actor_id)


if __name__=="__main__": main()

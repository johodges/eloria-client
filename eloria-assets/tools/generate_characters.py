#!/usr/bin/env python3
"""Generate an original low-poly Cal3D humanoid and core animation set."""
from __future__ import annotations
import argparse, json, math, struct
from pathlib import Path
import xml.etree.ElementTree as ET
from generate_bootstrap_pack import png

VERSION = "919"
PLAYER_ACTOR_TYPES = ((0,1),(2,3),(4,5),(37,38),(39,40),(41,42))
RACES = (
 ("luminous", "Luminous", (77,155,162), "Lake-city citizens shaped by civic duty, trade, and reflected light."),
 ("votary", "Whitehorn Votary", (139,173,188), "Mountain ascetics adapted to cold, altitude, and patient discipline."),
 ("glasswarden", "Glasswarden", (121,91,158), "Crystal engineers who study resonance, storms, and the old observatories."),
 ("orun", "Orun", (172,99,47), "Steppe riders whose camps follow the sunmane herds and seasonal roads."),
 ("greyhaven", "Greyhaven", (62,86,101), "Western sailors, shipwrights, and moorland wardens."),
 ("ssarathi", "Ssarathi", (52,116,91), "Scaled riverfolk preserving the archives and water rites of the south."),
)

BONES = (("root",-1,(0.,0.,0.)),("pelvis",0,(0.,0.,.92)),("spine",1,(0.,0.,.34)),
 ("head",2,(0.,0.,.52)),("upper_arm_l",2,(-.32,0.,.38)),("lower_arm_l",4,(-.34,0.,0.)),
 ("upper_arm_r",2,(.32,0.,.38)),("lower_arm_r",6,(.34,0.,0.)),
 ("upper_leg_l",1,(-.15,0.,-.08)),("lower_leg_l",8,(0.,0.,-.48)),("foot_l",9,(0.,.06,-.45)),
 ("upper_leg_r",1,(.15,0.,-.08)),("lower_leg_r",11,(0.,0.,-.48)),("foot_r",12,(0.,.06,-.45)),
 # Stable semantic anchors used by effects, equipment, capes and ranged combat.
 ("mouth",3,(0.,-.17,-.04)),("jaw",3,(0.,-.14,-.08)),
 ("handL",5,(-.20,0.,0.)),("handR",7,(.20,0.,0.)),
 ("weaponL",16,(0.,-.08,0.)),("weaponR",17,(0.,-.08,0.)),
 ("staffR",17,(0.,-.12,.04)),("arrow",2,(0.,.12,.18)),
 ("cape1",2,(0.,.13,.28)),("cape2",22,(0.,0.,-.30)),("cape3",23,(0.,0.,-.30)))

def write_cal(path, magic, root):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'<HEADER MAGIC="{magic}" VERSION="{VERSION}"/>\n'+ET.tostring(root,encoding="unicode")+'\n')

def _binary_header(magic):
    return bytearray(magic.encode("ascii") + b"\0" + struct.pack("<i", int(VERSION)))

def _binary_string(value):
    encoded=value.encode("utf-8")+b"\0"
    return struct.pack("<i",len(encoded))+encoded

def binary_skeleton(path):
    children={i:[] for i in range(len(BONES))}
    for i,(_,parent,_) in enumerate(BONES):
        if parent>=0: children[parent].append(i)
    absolute=[]
    for _,parent,pos in BONES:
        base=(0.,0.,0.) if parent < 0 else absolute[parent]
        absolute.append(tuple(base[j]+pos[j] for j in range(3)))
    data=_binary_header("CSF")
    data.extend(struct.pack("<i",len(BONES)))
    for i,(name,parent,pos) in enumerate(BONES):
        data.extend(_binary_string(name))
        data.extend(struct.pack("<3f4f3f4f",*pos,0.,0.,0.,1.,
                                *(-v for v in absolute[i]),0.,0.,0.,1.))
        data.extend(struct.pack("<ii",parent,len(children[i])))
        if children[i]: data.extend(struct.pack(f"<{len(children[i])}i",*children[i]))
    path.write_bytes(data)

def binary_mesh(path, vertices, faces):
    data=_binary_header("CMF")
    data.extend(struct.pack("<i",1)) # submesh count
    data.extend(struct.pack("<6i",0,len(vertices),len(faces),0,0,1))
    for pos,norm,uv,bone in vertices:
        data.extend(struct.pack("<3f3fii2fiif",*pos,*norm,-1,0,*uv,1,bone,1.0))
    for tri in faces: data.extend(struct.pack("<3i",*tri))
    path.write_bytes(data)

def binary_animation(path,duration,poses,tracks):
    data=_binary_header("CAF")
    # EL uses the classic Cal3D 0.11 binary layout: duration follows version.
    data.extend(struct.pack("<fi",duration,len(tracks)))
    for bone in tracks:
        data.extend(struct.pack("<ii",bone,len(poses)))
        for time,frame in poses:
            data.extend(struct.pack("<f3f4f",time,*BONES[bone][2],
                                    *quat_x(frame.get(bone,0.))))
    path.write_bytes(data)

def skeleton(path):
    children={i:[] for i in range(len(BONES))}
    for i,(_,p,_) in enumerate(BONES):
        if p>=0: children[p].append(i)
    absolute=[]
    for _,parent,pos in BONES:
        base=(0.,0.,0.) if parent < 0 else absolute[parent]
        absolute.append(tuple(base[j]+pos[j] for j in range(3)))
    root=ET.Element("SKELETON",NUMBONES=str(len(BONES)))
    for i,(name,parent,pos) in enumerate(BONES):
        b=ET.SubElement(root,"BONE",ID=str(i),NAME=name,NUMCHILD=str(len(children[i])))
        ET.SubElement(b,"TRANSLATION").text="%g %g %g"%pos
        ET.SubElement(b,"ROTATION").text="0 0 0 1"
        ET.SubElement(b,"LOCALTRANSLATION").text="%g %g %g"%tuple(-v for v in absolute[i])
        ET.SubElement(b,"LOCALROTATION").text="0 0 0 1"
        ET.SubElement(b,"PARENTID").text=str(parent)
        for child in children[i]: ET.SubElement(b,"CHILDID").text=str(child)
    write_cal(path,"XSF",root)
    binary_skeleton(path.with_suffix(".csf"))

def cuboid(center,size,bone,vertices,faces,uv_rect=(0.,0.,1.,1.)):
    cx,cy,cz=center; sx,sy,sz=(v/2 for v in size)
    u0,v0,u1,v1=uv_rect
    corners=[(cx+x*sx,cy+y*sy,cz+z*sz) for x,y,z in ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1))]
    quads=((0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(4,0,3,7)); normals=((0,0,-1),(0,0,1),(0,-1,0),(1,0,0),(0,1,0),(-1,0,0))
    for quad,normal in zip(quads,normals):
        base=len(vertices)
        for uv,corner in zip(((u0,v0),(u1,v0),(u1,v1),(u0,v1)),quad): vertices.append((corners[corner],normal,uv,bone))
        # EL treats counter-clockwise triangles as front-facing.
        faces.extend(((base,base+2,base+1),(base,base+3,base+2)))

def ellipsoid(center,size,bone,vertices,faces,uv_rect=(0.,0.,1.,1.),rings=7,sides=12):
    cx,cy,cz=center; sx,sy,sz=(q/2 for q in size); u0,v0,u1,v1=uv_rect
    bottom=len(vertices); vertices.append(((cx,cy,cz-sz),(0,0,-1),((u0+u1)/2,v1),bone))
    ring_ids=[]
    for ring in range(1,rings):
        theta=math.pi-math.pi*ring/rings; ids=[]
        for side in range(sides):
            phi=2*math.pi*side/sides
            nx=math.sin(theta)*math.cos(phi); ny=math.sin(theta)*math.sin(phi); nz=math.cos(theta)
            length=math.sqrt((nx/max(sx,.001))**2+(ny/max(sy,.001))**2+(nz/max(sz,.001))**2)
            normal=(nx/max(sx,.001)/length,ny/max(sy,.001)/length,nz/max(sz,.001)/length)
            uv=(u0+(u1-u0)*side/sides,v0+(v1-v0)*ring/rings)
            ids.append(len(vertices)); vertices.append(((cx+sx*nx,cy+sy*ny,cz+sz*nz),normal,uv,bone))
        ring_ids.append(ids)
    top=len(vertices); vertices.append(((cx,cy,cz+sz),(0,0,1),((u0+u1)/2,v0),bone))
    for side in range(sides):
        nxt=(side+1)%sides
        faces.append((bottom,ring_ids[0][nxt],ring_ids[0][side]))
        faces.append((top,ring_ids[-1][side],ring_ids[-1][nxt]))
    for lower,upper in zip(ring_ids,ring_ids[1:]):
        for side in range(sides):
            nxt=(side+1)%sides
            faces.extend(((lower[side],upper[nxt],upper[side]),(lower[side],lower[nxt],upper[nxt])))

RACE_SHAPES={
 "luminous":(1.00,.96,.96,.92,"civic"),
 "votary":(1.08,1.06,1.05,.96,"cold"),
 "glasswarden":(.94,1.12,1.02,1.04,"crystal"),
 "orun":(1.02,1.04,.97,.98,"rider"),
 "greyhaven":(1.04,1.12,1.08,1.06,"maritime"),
 "ssarathi":(1.08,.96,.94,1.08,"scaled"),
}

def mesh(path, section="all", variant=0, culture=None, gender=None):
    vertices=[]; faces=[]
    # UV rectangles address the fixed regions used by EL's 128x128 enhanced
    # actor atlas.  V is expressed in OpenGL coordinates (bottom to top).
    torso_uv=(79/128,0,1,54/128); arms_uv=(0,40/128,40/128,80/128)
    hands_uv=(34/128,80/128,50/128,96/128)
    head_uv=(34/128,96/128,66/128,1)
    legs_uv=(39/128,0,79/128,40/128); boots_uv=(0,0,39/128,40/128)
    # Match the proven EL player coordinate envelope.  In particular, arms are
    # down beside the torso rather than extending almost two units in a T pose.
    parts=(((0,0,1.12),(.50,.24,.60),2,torso_uv),((0,-.01,1.51),(.18,.23,.27),3,head_uv),
      ((-.27,0,1.10),(.14,.18,.42),4,arms_uv),((-.27,0,.75),(.13,.17,.34),5,hands_uv),((.27,0,1.10),(.14,.18,.42),6,arms_uv),((.27,0,.75),(.13,.17,.34),7,hands_uv),
      ((-.12,0,.70),(.18,.22,.52),8,legs_uv),((-.12,0,.28),(.17,.21,.42),9,legs_uv),((-.12,.02,.08),(.18,.30,.18),10,boots_uv),
      ((.12,0,.70),(.18,.22,.52),11,legs_uv),((.12,0,.28),(.17,.21,.42),12,legs_uv),((.12,.02,.08),(.18,.30,.18),13,boots_uv))
    if section=="head":
        head_sizes=((.18,.23,.27),(.19,.22,.26),(.17,.24,.28),(.20,.23,.25),(.18,.21,.29))
        parts=list(parts);parts[1]=((0,-.01,1.51),head_sizes[variant%len(head_sizes)],3,head_uv)
    sections={"head":(1,),"shirt":(0,2,3,4,5),"legs":(6,7,9,10),"boots":(8,11),"none":()}
    chosen=range(len(parts)) if section=="all" else sections[section]
    if culture:
        height,shoulders,hips,head_scale,feature=RACE_SHAPES[culture]
        gender_width=.94 if gender=="female" else 1.04
        for i in chosen:
            center,size,bone,uv_rect=parts[i]
            cx,cy,cz=center; sx,sy,sz=size
            width=shoulders if i in (0,2,3,4,5) else hips if i in (6,7,8,9,10,11) else head_scale
            if i==0 and gender=="female": width*=.90
            if i==1:
                head_variation=(.94,.98,1.02,1.06,1.0)[variant%5]
                sx*=head_variation; sy*=2-head_variation
            scaled_center=(cx*width*gender_width,cy,cz*height)
            scaled_size=(sx*width*gender_width,sy*(1.04 if feature in ("cold","maritime") else .96),sz*height)
            ellipsoid(scaled_center,scaled_size,bone,vertices,faces,uv_rect,7 if i!=1 else 8,12 if i!=1 else 14)
        if section in ("all","head") and feature=="scaled":
            # A low swept crest gives Ssarathi a readable silhouette without
            # changing the shared skeleton or enhanced-actor atlas contract.
            ellipsoid((0,.02,1.68*height),(.12,.18,.32),3,vertices,faces,head_uv,5,8)
        if section in ("all","shirt") and feature=="crystal":
            for side in (-1,1):
                ellipsoid((side*.32*gender_width,0,1.36*height),(.12,.17,.28),2,vertices,faces,torso_uv,5,8)
    else:
        for i in chosen:
            center,size,bone,uv_rect=parts[i]
            cuboid(center,size,bone,vertices,faces,uv_rect)
    if not vertices:
        cuboid((0,0,-100),(.001,.001,.001),0,vertices,faces)
    root=ET.Element("MESH",NUMSUBMESH="1"); sub=ET.SubElement(root,"SUBMESH",NUMVERTICES=str(len(vertices)),NUMFACES=str(len(faces)),MATERIAL="0",NUMLODSTEPS="0",NUMSPRINGS="0",NUMTEXCOORDS="1")
    for i,(pos,norm,uv,bone) in enumerate(vertices):
        v=ET.SubElement(sub,"VERTEX",ID=str(i),NUMINFLUENCES="1")
        ET.SubElement(v,"POS").text="%g %g %g"%pos; ET.SubElement(v,"NORM").text="%g %g %g"%norm; ET.SubElement(v,"TEXCOORD").text="%g %g"%uv; ET.SubElement(v,"INFLUENCE",ID=str(bone)).text="1"
    for tri in faces: ET.SubElement(sub,"FACE",VERTEXID="%d %d %d"%tri)
    write_cal(path,"XMF",root)
    binary_mesh(path.with_suffix(".cmf"),vertices,faces)

def quat_x(a): return math.sin(a/2),0.,0.,math.cos(a/2)
def animation(path,duration,poses):
    tracks=sorted({b for _,frame in poses for b in frame}); root=ET.Element("ANIMATION",DURATION=str(duration),NUMTRACKS=str(len(tracks)))
    for bone in tracks:
        tr=ET.SubElement(root,"TRACK",BONEID=str(bone),NUMKEYFRAMES=str(len(poses)))
        for time,frame in poses:
            key=ET.SubElement(tr,"KEYFRAME",TIME=str(time))
            ET.SubElement(key,"TRANSLATION").text="%g %g %g"%BONES[bone][2]
            ET.SubElement(key,"ROTATION").text="%g %g %g %g"%quat_x(frame.get(bone,0.))
    write_cal(path,"XAF",root)
    binary_animation(path.with_suffix(".caf"),duration,poses,tracks)

CULTURES={
 "luminous":((190,139,104),(224,179,139),(238,207,174)),
 "votary":((107,104,82),(161,145,108),(202,184,142)),
 "glasswarden":((116,83,69),(168,121,91),(211,167,128)),
 "orun":((126,91,74),(184,139,105),(224,188,148)),
 "greyhaven":((102,76,66),(153,111,89),(198,153,119)),
 "ssarathi":((64,112,103),(91,153,126),(139,190,151)),
}
HAIR=((24,20,22),(202,169,91),(103,66,42),(116,112,108),(142,53,40),(221,219,205),
 (50,80,142),(49,115,76),(105,67,136),(55,35,29),(184,91,70),(232,207,143),
 (169,138,87),(112,91,72),(68,67,70),(99,33,31))
EYES=((92,55,34),(55,36,28),(118,48,38),(112,177,204),(53,124,181),(35,68,121),
 (134,190,142),(55,142,92),(32,93,67),(177,142,196),(117,75,166),(212,166,55))
CLOTH=((25,31,39),(40,74,112),(91,61,44),(91,91,94),(46,94,66),(142,105,69),
 (181,91,38),(190,112,131),(98,59,116),(143,48,47),(205,198,177),(184,153,47),
 (91,65,42),(112,116,119),(151,158,162),(94,105,112),(116,88,59),(83,62,45),
 (118,104,84),(128,135,141),(163,170,175),(131,91,49))
PANTS=((29,34,42),(42,68,91),(82,57,43),(58,42,34),(91,91,91),(45,74,55),
 (126,94,67),(116,48,43),(188,183,166),(94,69,46),(128,133,137),(99,80,58))
BOOTS=((31,28,27),(83,55,39),(52,38,31),(101,76,55),(139,103,69),(151,72,31),
 (96,69,45),(106,83,58),(116,121,124),(139,145,149),(169,174,178),(132,91,48),(119,88,57))

def texture(path, base, accent, style=0):
    def pixel(x,y):
        weave=((x//8+y//8+style)%2)*8
        seam=18 if x%64 in (0,1) or y%64 in (0,1) else 0
        sigil=accent if (x-128)**2+(y-128)**2 < (20+style%4*3)**2 else base
        return tuple(max(0,min(255,c+weave+seam)) for c in sigil)+(255,)
    png(path,256,256,pixel)

def actor_texture(path, width, height, base, accent, style=0, levels=3, role="cloth"):
    """Author a role-specific BGRA material while preserving EL's fixed atlas contract."""
    header=[124,0x0002100F,height,width,width*4,0,levels]+[0]*11
    header += [32,0x41,0,32,0x00FF0000,0x0000FF00,0x000000FF,0xFF000000]
    header += [0x401008,0,0,0,0]
    data=bytearray()
    for level in range(levels):
        w=max(1,width>>level); h=max(1,height>>level)
        for y in range(h):
            for x in range(w):
                u=(x+.5)/w; v=(y+.5)/h
                grain=((x*13+y*7+style*19) % max(3,11>>level))-max(1,5>>level)
                shade=int(18*(.5-v)+6*(1-abs(2*u-1)))
                color=base; detail=grain+shade
                if role == "skin":
                    detail += int(7*(1-abs(2*u-1)))
                    if abs(v-.58)<.012 or ((u-.36)**2+(v-.42)**2)<.0008 or ((u-.64)**2+(v-.42)**2)<.0008:
                        color=accent; detail-=8
                elif role == "hair":
                    strand=max(1,6>>level)
                    detail += 13 if (x+style*3)%strand==0 else -3
                    if v>.82: detail-=int(25*(v-.82)/.18)
                elif role == "eyes":
                    dx=(u-.5)*2; dy=(v-.5)*2; rr=dx*dx+dy*dy
                    color=accent if rr>.52 else base
                    if rr<.10: color=(18,20,24)
                    if (u-.38)**2+(v-.34)**2<.018: color=(250,250,242)
                    detail=0
                elif role in ("cloth","pants"):
                    weave=((x//max(1,4>>level))+(y//max(1,4>>level)))%2
                    detail += 7 if weave else -4
                    seam_width=max(.006,1.5/w)
                    if abs(u-.5)<seam_width or abs(v-.12)<seam_width: color=accent
                    if role=="cloth" and abs(abs(u-.5)+abs(v-.52)-.28)<.015: color=accent
                elif role == "leather":
                    detail += ((x*5+y*11+style*23)%17)-8
                    if abs(u-.12)<.012 or abs(u-.88)<.012 or abs(v-.18)<.012: color=accent
                    if ((x+y+style*7)%max(5,23>>level))==0: detail-=12
                r,g,b=(max(0,min(255,c+detail)) for c in color)
                data.extend((b,g,r,255))
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(b'DDS '+struct.pack('<31I',*header)+data)

def generate_customization(root):
    for culture,skins in CULTURES.items():
        directory=root/f"actors/custom/{culture}"
        dark_blue=(55,79,105) if culture=="votary" else tuple(max(35,c-35) for c in skins[0])
        white=(222,224,216) if culture!="ssarathi" else (169,207,178)
        skin_palette=(skins[0],skins[1],skins[2],skins[1],dark_blue,white)
        for i,color in enumerate(skin_palette):
            actor_texture(directory/f"skin_{i}_hands.dds",64,64,color,(220,188,150),i,role="skin")
            actor_texture(directory/f"skin_{i}_head.dds",128,128,color,(220,188,150),i,role="skin")
        for i,color in enumerate(HAIR):actor_texture(directory/f"hair_{i}.dds",136,192,color,tuple(min(255,c+35) for c in color),i,role="hair")
        for i,color in enumerate(EYES):actor_texture(directory/f"eyes_{i}.dds",24,24,color,(235,235,220),i,role="eyes")
        for i,color in enumerate(CLOTH):
            actor_texture(directory/f"shirt_{i}_torso.dds",196,216,color,(207,151,70),i,role="cloth")
            actor_texture(directory/f"shirt_{i}_arms.dds",160,160,color,(207,151,70),i,role="cloth")
        for i,color in enumerate(PANTS):actor_texture(directory/f"pants_{i}.dds",160,160,color,(126,104,78),i,role="pants")
        for i,color in enumerate(BOOTS):actor_texture(directory/f"boots_{i}.dds",156,160,color,(176,137,87),i,role="leather")

def actor_defs(path):
    files={"CAL_walk":"walk.xaf","CAL_run":"run.xaf","CAL_idle":"idle.xaf","CAL_idle2":"idle.xaf","CAL_combat_idle":"idle.xaf","CAL_attack_up_1":"attack.xaf","CAL_attack_down_1":"attack.xaf","CAL_pain1":"pain.xaf","CAL_pain2":"pain.xaf","CAL_die1":"die.xaf","CAL_die2":"die.xaf","CAL_harvest":"harvest.xaf","CAL_pick":"harvest.xaf","CAL_drop":"harvest.xaf","CAL_idle_sit":"sit.xaf","CAL_sit_down":"sit.xaf","CAL_stand_up":"idle.xaf"}
    root=ET.Element("actors")
    for race_index,(culture,label,_,_) in enumerate(RACES):
      for gender,aid in zip(("female","male"),PLAYER_ACTOR_TYPES[race_index]):
        a=ET.SubElement(root,"actor",id=str(aid),type=f"Eloria {label} {gender.title()}",race=culture,gender=gender)
        ET.SubElement(a,"skeleton").text="actors/eloria_humanoid.csf"; ET.SubElement(a,"step_duration").text="250"
        prefix=f"actors/custom/{culture}"
        for i in range(len(CLOTH)):
            shirt=ET.SubElement(a,"shirt",id=str(i))
            for tag,value in (("arms",f"{prefix}/shirt_{i}_arms.dds"),("torso",f"{prefix}/shirt_{i}_torso.dds"),("mesh",f"actors/playable/{culture}_{gender}_shirt.cmf")):ET.SubElement(shirt,tag).text=value
        for i in range(6):
            skin=ET.SubElement(a,"hskin",id=str(i))
            ET.SubElement(skin,"hands").text=f"{prefix}/skin_{i}_hands.dds"
            ET.SubElement(skin,"head").text=f"{prefix}/skin_{i}_head.dds"
        for i in range(len(HAIR)):ET.SubElement(a,"hair",id=str(i)).text=f"{prefix}/hair_{i}.dds"
        for i in range(len(EYES)):ET.SubElement(a,"eyes",id=str(i)).text=f"{prefix}/eyes_{i}.dds"
        for i in range(len(PANTS)):
            legs=ET.SubElement(a,"legs",id=str(i));ET.SubElement(legs,"skin").text=f"{prefix}/pants_{i}.dds";ET.SubElement(legs,"mesh").text=f"actors/playable/{culture}_{gender}_legs.cmf"
        for i in range(len(BOOTS)):
            boots=ET.SubElement(a,"boots",id=str(i));ET.SubElement(boots,"skin").text=f"{prefix}/boots_{i}.dds";ET.SubElement(boots,"mesh").text=f"actors/playable/{culture}_{gender}_boots.cmf"
        for i in range(5):
            head=ET.SubElement(a,"head",id=str(i));ET.SubElement(head,"mesh").text=f"actors/playable/{culture}_{gender}_head_{i}.cmf"
        # These IDs are protocol constants, not zero-based defaults.  The client
        # indexes these exact slots while constructing the character preview.
        # Leaving only slot zero populated makes helmet/cape/shield dereference
        # uninitialised entries and crash as soon as character creation opens.
        none_ids={"neck":0,"helmet":20,"cape":30,"shield":11}
        for tag,none_id in none_ids.items():
            part=ET.SubElement(a,tag,id=str(none_id));ET.SubElement(part,"mesh").text="actors/eloria_none.cmf";ET.SubElement(part,"skin").text="actors/eloria_humanoid.png"
        # The renderer always inspects WEAPON_NONE even when no weapon mesh is
        # attached.  A skin child makes the parser allocate the weapon table;
        # omitting mesh intentionally leaves its mesh index at -1.
        weapon=ET.SubElement(a,"weapon",id="0")
        ET.SubElement(weapon,"skin").text="actors/eloria_humanoid.png"
        frames=ET.SubElement(a,"frames")
        for tag,name in files.items():
            kind=0 if tag in ("CAL_walk","CAL_run","CAL_idle","CAL_idle2","CAL_idle_sit","CAL_combat_idle") else 1
            ET.SubElement(frames,tag).text=f"animations/eloria/{Path(name).with_suffix('.caf').name} {kind}"
    for actor in root.findall("actor"):
        for tag,none_id in none_ids.items():
            if actor.find(f"{tag}[@id='{none_id}']") is None:
                raise ValueError(f"actor {actor.attrib['id']} lacks canonical {tag} none slot {none_id}")
        if actor.find("weapon[@id='0']") is None:
            raise ValueError(f"actor {actor.attrib['id']} lacks canonical unarmed slot 0")
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text('<?xml version="1.0"?>\n'+ET.tostring(root,encoding="unicode")+'\n')

def main():
    p=argparse.ArgumentParser(); p.add_argument("output",nargs="?",default="build/eloria-data"); root=Path(p.parse_args().output)
    skeleton(root/"actors/eloria_humanoid.xsf"); mesh(root/"actors/eloria_humanoid.xmf")
    for section in ("shirt","legs","boots","none"):mesh(root/f"actors/eloria_{section}.xmf",section)
    for i in range(5):mesh(root/f"actors/eloria_head_{i}.xmf","head",i)
    for culture,_,_,_ in RACES:
        for gender in ("female","male"):
            mesh(root/f"actors/playable/{culture}_{gender}_body.xmf","all",0,culture,gender)
            for section in ("shirt","legs","boots"):
                mesh(root/f"actors/playable/{culture}_{gender}_{section}.xmf",section,0,culture,gender)
            for i in range(5):
                mesh(root/f"actors/playable/{culture}_{gender}_head_{i}.xmf","head",i,culture,gender)
    png(root/"actors/eloria_humanoid.png",256,256,lambda x,y:(82+(x//32%2)*18,105+(y//32%2)*12,96,255))
    generate_customization(root)
    for slug,_,color,_ in RACES:
        png(root/f"actors/races/{slug}.png",256,256,
            lambda x,y,color=color:(min(255,color[0]+(x//32%2)*18),min(255,color[1]+(y//32%2)*12),color[2],255))
    race_catalog={"schema":1,"default":"luminous","races":[
        {"actor_types":{"female":PLAYER_ACTOR_TYPES[aid][0],"male":PLAYER_ACTOR_TYPES[aid][1]},
         "id":slug,"name":label,"description":description}
        for aid,(slug,label,_,description) in enumerate(RACES)]}
    (root/"races.json").write_text(json.dumps(race_catalog,indent=2)+"\n",encoding="utf-8")
    anims={"idle":(2.,[(0,{2:-.03}),(1,{2:.03}),(2,{2:-.03})]),"walk":(1.,[(0,{4:.5,6:-.5,8:-.55,11:.55}),(.5,{4:-.5,6:.5,8:.55,11:-.55}),(1,{4:.5,6:-.5,8:-.55,11:.55})]),"run":(.7,[(0,{4:.8,6:-.8,8:-.85,11:.85}),(.35,{4:-.8,6:.8,8:.85,11:-.85}),(.7,{4:.8,6:-.8,8:-.85,11:.85})]),"attack":(.65,[(0,{2:-.15,6:-.5}),(.3,{2:.55,6:1.5,7:.7}),(.65,{2:-.15,6:-.5})]),"pain":(.45,[(0,{}),(.2,{2:-.35,4:-.25,6:-.25}),(.45,{})]),"die":(1.2,[(0,{}),(.6,{1:-.8,2:-.8}),(1.2,{1:-1.45,2:-1.45})]),"harvest":(1.1,[(0,{}),(.55,{2:.45,4:1.,6:1.}),(1.1,{})]),"sit":(.8,[(0,{}),(.8,{8:1.35,9:-1.35,11:1.35,12:-1.35})])}
    for name,(duration,poses) in anims.items(): animation(root/f"animations/eloria/{name}.xaf",duration,poses)
    actor_defs(root/"actor_defs/actor_defs.xml")
if __name__=="__main__": main()

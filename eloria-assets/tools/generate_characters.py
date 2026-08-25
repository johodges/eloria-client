#!/usr/bin/env python3
"""Generate an original low-poly Cal3D humanoid and core animation set."""
from __future__ import annotations
import argparse, json, math, struct
from pathlib import Path
import xml.etree.ElementTree as ET
from generate_bootstrap_pack import png

VERSION = "919"
PLAYER_ACTOR_TYPES = ((0,1),(2,3),(4,5),(37,38),(39,40),(41,42),(79,80),(81,82))
RACES = (
 ("luminous", "Luminous", (77,155,162), "Lake-city citizens shaped by civic duty, trade, and reflected light."),
 ("votary", "Whitehorn Votary", (139,173,188), "Mountain ascetics adapted to cold, altitude, and patient discipline."),
 ("glasswarden", "Glasswarden", (121,91,158), "Crystal engineers who study resonance, storms, and the old observatories."),
 ("orun", "Orun", (172,99,47), "Steppe riders whose camps follow the sunmane herds and seasonal roads."),
 ("greyhaven", "Greyhaven", (62,86,101), "Western sailors, shipwrights, and moorland wardens."),
 ("ssarathi", "Ssarathi", (52,116,91), "Scaled riverfolk preserving the archives and water rites of the south."),
 ("stoneborn", "Stoneborn", (118,105,91), "Living stonefolk whose crystalline seams preserve the memory of the deep earth."),
 ("mycelari", "Mycelari", (116,137,91), "Fungal folk joined by luminous mycelial networks and the patient wisdom of the forest floor."),
)

BONES = (("root",-1,(0.,0.,0.)),("pelvis",0,(0.,0.,.92)),("spine",1,(0.,0.,.34)),
 ("head",2,(0.,0.,.52)),("upper_arm_l",2,(-.24,0.,.30)),("lower_arm_l",4,(0.,0.,-.30)),
 ("upper_arm_r",2,(.24,0.,.30)),("lower_arm_r",6,(0.,0.,-.30)),
 ("upper_leg_l",1,(-.15,0.,-.08)),("lower_leg_l",8,(0.,0.,-.48)),("foot_l",9,(0.,.06,-.45)),
 ("upper_leg_r",1,(.15,0.,-.08)),("lower_leg_r",11,(0.,0.,-.48)),("foot_r",12,(0.,.06,-.45)),
 # Stable semantic anchors used by effects, equipment, capes and ranged combat.
 ("mouth",3,(0.,-.17,-.04)),("jaw",3,(0.,-.14,-.08)),
 ("handL",5,(-.20,0.,0.)),("handR",7,(.20,0.,0.)),
 ("weaponL",16,(0.,-.08,0.)),("weaponR",17,(0.,-.08,0.)),
 ("staffR",17,(0.,-.12,.04)),("arrow",2,(0.,.12,.18)),
 ("cape1",2,(0.,.13,.28)),("cape2",22,(0.,0.,-.30)),("cape3",23,(0.,0.,-.30)),
 # Secondary deformation and attachment anchors.  Existing IDs stay stable;
 # these extend the production rig without invalidating animation/equipment.
 ("spine_upper",2,(0.,0.,.25)),("neck",25,(0.,0.,.20)),
 ("clavicle_l",25,(-.19,0.,.12)),("clavicle_r",25,(.19,0.,.12)),
 ("eye_l",3,(-.075,-.16,.035)),("eye_r",3,(.075,-.16,.035)),
 ("thumb_l",16,(-.055,-.025,0.)),("index_l",16,(-.11,-.015,0.)),
 ("thumb_r",17,(.055,-.025,0.)),("index_r",17,(.11,-.015,0.)),
 ("toe_l",10,(0.,-.17,-.01)),("toe_r",13,(0.,-.17,-.01)))

def write_cal(path, magic, root):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'<HEADER MAGIC="{magic}" VERSION="{VERSION}"/>\n'+ET.tostring(root,encoding="unicode")+'\n')

def _binary_header(magic):
    return bytearray(magic.encode("ascii") + b"\0" + struct.pack("<i", int(VERSION)))

def _binary_string(value):
    encoded=value.encode("utf-8")+b"\0"
    return struct.pack("<i",len(encoded))+encoded

def binary_skeleton(path,bones=BONES):
    children={i:[] for i in range(len(bones))}
    for i,(_,parent,_) in enumerate(bones):
        if parent>=0: children[parent].append(i)
    absolute=[]
    for _,parent,pos in bones:
        base=(0.,0.,0.) if parent < 0 else absolute[parent]
        absolute.append(tuple(base[j]+pos[j] for j in range(3)))
    data=_binary_header("CSF")
    data.extend(struct.pack("<i",len(bones)))
    for i,(name,parent,pos) in enumerate(bones):
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

def binary_animation(path,duration,poses,tracks,bones=BONES):
    data=_binary_header("CAF")
    # EL uses the classic Cal3D 0.11 binary layout: duration follows version.
    data.extend(struct.pack("<fi",duration,len(tracks)))
    for bone in tracks:
        data.extend(struct.pack("<ii",bone,len(poses)))
        for time,frame in poses:
            value=frame.get(bone,0.)
            if isinstance(value,tuple):
                axis,angle=value
                rotation=quat_axis(axis,angle)
            else:
                rotation=quat_x(value)
            data.extend(struct.pack("<f3f4f",time,*bones[bone][2],
                                    *rotation))
    path.write_bytes(data)

def skeleton(path,bones=BONES):
    children={i:[] for i in range(len(bones))}
    for i,(_,p,_) in enumerate(bones):
        if p>=0: children[p].append(i)
    absolute=[]
    for _,parent,pos in bones:
        base=(0.,0.,0.) if parent < 0 else absolute[parent]
        absolute.append(tuple(base[j]+pos[j] for j in range(3)))
    root=ET.Element("SKELETON",NUMBONES=str(len(bones)))
    for i,(name,parent,pos) in enumerate(bones):
        b=ET.SubElement(root,"BONE",ID=str(i),NAME=name,NUMCHILD=str(len(children[i])))
        ET.SubElement(b,"TRANSLATION").text="%g %g %g"%pos
        ET.SubElement(b,"ROTATION").text="0 0 0 1"
        ET.SubElement(b,"LOCALTRANSLATION").text="%g %g %g"%tuple(-v for v in absolute[i])
        ET.SubElement(b,"LOCALROTATION").text="0 0 0 1"
        ET.SubElement(b,"PARENTID").text=str(parent)
        for child in children[i]: ET.SubElement(b,"CHILDID").text=str(child)
    write_cal(path,"XSF",root)
    binary_skeleton(path.with_suffix(".csf"),bones)

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
            for triangle in ((lower[side],upper[nxt],upper[side]),(lower[side],lower[nxt],upper[nxt])):
                a,b,c=triangle; pa,na=vertices[a][0],vertices[a][1]; pb,pc=vertices[b][0],vertices[c][0]
                ab=tuple(pb[q]-pa[q] for q in range(3)); ac=tuple(pc[q]-pa[q] for q in range(3))
                cross=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
                faces.append(triangle if sum(cross[q]*na[q] for q in range(3))>0 else (a,c,b))

def profile_surface(rings,bones,vertices,faces,uv_rect=(0.,0.,1.,1.),sides=20):
    """Build one connected anatomical/clothing surface through elliptical rings."""
    # Interpolate control rings so shoulders, elbows, knees and garment tapers
    # read as smooth anatomy rather than four-sided transitions.
    controls=list(rings); control_bones=list(bones); rings=[]; bones=[]
    for index in range(len(controls)-1):
        for step in range(3):
            t=step/3
            rings.append(tuple(controls[index][q]*(1-t)+controls[index+1][q]*t for q in range(5)))
            bones.append(control_bones[index] if t<.5 else control_bones[index+1])
    rings.append(controls[-1]); bones.append(control_bones[-1])
    u0,v0,u1,v1=uv_rect; ring_ids=[]
    for index,(cx,cy,cz,rx,ry) in enumerate(rings):
        previous=rings[max(0,index-1)]; following=rings[min(len(rings)-1,index+1)]
        tangent=(following[0]-previous[0],following[1]-previous[1],following[2]-previous[2])
        length=math.sqrt(sum(q*q for q in tangent)) or 1
        tangent=tuple(q/length for q in tangent)
        reference=(0.,1.,0.) if abs(tangent[1])<.92 else (1.,0.,0.)
        e1=(reference[1]*tangent[2]-reference[2]*tangent[1],reference[2]*tangent[0]-reference[0]*tangent[2],reference[0]*tangent[1]-reference[1]*tangent[0])
        length=math.sqrt(sum(q*q for q in e1)) or 1; e1=tuple(q/length for q in e1)
        e2=(tangent[1]*e1[2]-tangent[2]*e1[1],tangent[2]*e1[0]-tangent[0]*e1[2],tangent[0]*e1[1]-tangent[1]*e1[0])
        ids=[]
        for side in range(sides):
            angle=2*math.pi*side/sides; ca,sa=math.cos(angle),math.sin(angle)
            normal=tuple(e1[q]*ca+e2[q]*sa for q in range(3))
            uv=(u0+(u1-u0)*side/sides,v0+(v1-v0)*index/max(1,len(rings)-1))
            position=tuple((cx,cy,cz)[q]+e1[q]*rx*ca+e2[q]*ry*sa for q in range(3))
            ids.append(len(vertices)); vertices.append((position,normal,uv,bones[index]))
        ring_ids.append(ids)
    for lower,upper in zip(ring_ids,ring_ids[1:]):
        for side in range(sides):
            nxt=(side+1)%sides
            for triangle in ((lower[side],upper[nxt],upper[side]),(lower[side],lower[nxt],upper[nxt])):
                a,b,c=triangle; pa,na=vertices[a][0],vertices[a][1]; pb,pc=vertices[b][0],vertices[c][0]
                ab=tuple(pb[q]-pa[q] for q in range(3)); ac=tuple(pc[q]-pa[q] for q in range(3))
                cross=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
                faces.append(triangle if sum(cross[q]*na[q] for q in range(3))>0 else (a,c,b))
    # Close both ends with correctly wound caps.
    start_tangent=tuple(rings[1][q]-rings[0][q] for q in range(3)); end_tangent=tuple(rings[-1][q]-rings[-2][q] for q in range(3))
    for ids,ring,bone,flip,v,tangent in ((ring_ids[0],rings[0],bones[0],False,v1,start_tangent),(ring_ids[-1],rings[-1],bones[-1],True,v0,end_tangent)):
        length=math.sqrt(sum(q*q for q in tangent)) or 1; direction=tuple(q/length*(1 if flip else -1) for q in tangent)
        center=len(vertices); vertices.append(((ring[0],ring[1],ring[2]),direction,((u0+u1)/2,v),bone))
        for side in range(sides):
            nxt=(side+1)%sides
            faces.append((center,ids[nxt],ids[side]) if not flip else (center,ids[side],ids[nxt]))

RACE_SHAPES={
 "luminous":(1.00,.96,.96,.92,"civic"),
 "votary":(1.08,1.06,1.05,.96,"cold"),
 "glasswarden":(.94,1.12,1.02,1.04,"crystal"),
 "orun":(1.02,1.04,.97,.98,"rider"),
 "greyhaven":(1.04,1.12,1.08,1.06,"maritime"),
 "ssarathi":(1.08,.96,.94,1.08,"scaled"),
 "stoneborn":(1.05,1.17,1.08,1.03,"stone"),
 "mycelari":(1.02,1.04,1.04,1.12,"fungal"),
}

def fitted_bones(culture,gender):
    height,shoulders,hips,head_scale,_=RACE_SHAPES[culture]
    gender_width=.94 if gender=="female" else 1.04
    shoulder_ids={4,5,6,7,16,17,18,19,20,27,28,31,32,33,34}
    hip_ids={8,9,10,11,12,13,35,36}
    head_ids={14,15,29,30}
    result=[]
    for ident,(name,parent,pos) in enumerate(BONES):
        x,y,z=pos
        if ident in shoulder_ids: x*=shoulders*gender_width
        elif ident in hip_ids: x*=hips*gender_width
        elif ident in head_ids: x*=head_scale
        z*=height
        result.append((name,parent,(x,y,z)))
    return tuple(result)

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
    parts=(((0,0,1.12),(.50,.24,.60),2,torso_uv),((0,-.01,1.62),(.18,.23,.27),3,head_uv),
      ((-.27,0,1.10),(.14,.18,.42),4,arms_uv),((-.27,0,.75),(.13,.17,.34),5,hands_uv),((.27,0,1.10),(.14,.18,.42),6,arms_uv),((.27,0,.75),(.13,.17,.34),7,hands_uv),
      ((-.12,0,.70),(.18,.22,.52),8,legs_uv),((-.12,0,.28),(.17,.21,.42),9,legs_uv),((-.12,.02,.08),(.18,.30,.18),10,boots_uv),
      ((.12,0,.70),(.18,.22,.52),11,legs_uv),((.12,0,.28),(.17,.21,.42),12,legs_uv),((.12,.02,.08),(.18,.30,.18),13,boots_uv))
    if section=="head":
        head_sizes=((.18,.23,.27),(.19,.22,.26),(.17,.24,.28),(.20,.23,.25),(.18,.21,.29))
        parts=list(parts);parts[1]=((0,-.01,1.62),head_sizes[variant%len(head_sizes)],3,head_uv)
    sections={"head":(1,),"shirt":(0,2,3,4,5),"legs":(6,7,9,10),"boots":(8,11),"none":()}
    chosen=range(len(parts)) if section=="all" else sections[section]
    if culture:
        height,shoulders,hips,head_scale,feature=RACE_SHAPES[culture]
        gender_width=.94 if gender=="female" else 1.04
        # Connected garment/anatomical shells eliminate the bead-like gaps of
        # the former one-ellipsoid-per-bone mannequin.
        if section in ("all","shirt"):
            profile_surface([(0,0,.84*height,.17*hips*gender_width,.12),(0,0,1.02*height,.255*shoulders*gender_width,.145),(0,0,1.28*height,.29*shoulders*gender_width,.16),(0,0,1.43*height,.16*shoulders*gender_width,.115)],
                            [1,2,2,25],vertices,faces,torso_uv,36)
            profile_surface([(0,0,1.39*height,.078*gender_width,.072),(0,0,1.48*height,.082*gender_width,.074),(0,0,1.55*height,.088*gender_width,.078)],
                            [26,26,26],vertices,faces,head_uv,28)
            for side,bones in ((-1,[28,4,5,16]),(1,[29,6,7,17])):
                profile_surface([(side*.20*shoulders*gender_width,0,1.39*height,.125,.13),(side*.285*shoulders*gender_width,0,1.18*height,.105,.115),(side*.285*shoulders*gender_width,-.005,.91*height,.09,.10),(side*.285*shoulders*gender_width,-.015,.72*height,.105,.12)],
                                bones,vertices,faces,arms_uv,28)
        if section in ("all","legs"):
            for side,bones in ((-1,[8,8,9,9]),(1,[11,11,12,12])):
                profile_surface([(side*.115*hips*gender_width,0,.91*height,.125,.135),(side*.12*hips*gender_width,0,.67*height,.118,.128),(side*.12*hips*gender_width,.005,.40*height,.095,.108),(side*.12*hips*gender_width,.01,.12*height,.085,.095)],
                                bones,vertices,faces,legs_uv,28)
        if section in ("all","boots"):
            for side,shaft_bones,foot_bone in ((-1,[9,10,10],10),(1,[12,13,13],13)):
                x=side*.12*hips*gender_width
                profile_surface([(x,.005,.34*height,.105,.11),(x,0,.18*height,.102,.105),(x,-.015,.085*height,.105,.105)],
                                shaft_bones,vertices,faces,boots_uv,28)
                # Horizontal foot with a constant-radius underside: center Z
                # equals vertical radius, producing a planted sole at Z=0.
                profile_surface([(x,.035,.070*height,.070*height,.105),(x,-.10,.070*height,.070*height,.115),(x,-.27,.070*height,.070*height,.105)],
                                [foot_bone]*3,vertices,faces,boots_uv,28)
        if section in ("all","head"):
            center,size,bone,uv_rect=parts[1]
            cx,cy,cz=center; sx,sy,sz=size
            ellipsoid((0,-.01,cz*height),(sx*head_scale*gender_width,sy,sz*height),bone,vertices,faces,uv_rect,26,48)
        for i in (() if section in ("all","shirt","legs","boots","head") else chosen):
            center,size,bone,uv_rect=parts[i]
            cx,cy,cz=center; sx,sy,sz=size
            width=shoulders if i in (0,2,3,4,5) else hips if i in (6,7,8,9,10,11) else head_scale
            if i==0 and gender=="female": width*=.90
            if i==1:
                head_variation=(.94,.98,1.02,1.06,1.0)[variant%5]
                sx*=head_variation; sy*=2-head_variation
            scaled_center=(cx*width*gender_width,cy,cz*height)
            scaled_size=(sx*width*gender_width,sy*(1.04 if feature in ("cold","maritime") else .96),sz*height)
            ellipsoid(scaled_center,scaled_size,bone,vertices,faces,uv_rect,10 if i!=1 else 12,18 if i!=1 else 22)
        if section in ("all","head"):
            # Keep relief inside the head silhouette. Eyes, lips and brows are
            # atlas detail; separate eye and ear spheres read as bubbles.
            z=1.62*height
            ellipsoid((0,-.137,z+.005),(.052,.055,.090*height),3,
                      vertices,faces,head_uv,6,12)
        if section in ("all","shirt"):
            # Hands and fingers give gestures a readable silhouette at close range.
            for side,bone,thumb,index in ((-1,5,32,33),(1,7,34,35)):
                ellipsoid((side*.285*shoulders*gender_width,-.02,.715*height),(.15,.19,.14),bone,vertices,faces,hands_uv,6,12)
                ellipsoid((side*.335*shoulders*gender_width,-.055,.69*height),(.07,.08,.16),thumb,vertices,faces,hands_uv,5,9)
                ellipsoid((side*.285*shoulders*gender_width,-.09,.655*height),(.055,.07,.18),index,vertices,faces,hands_uv,5,9)
        if section in ("all","head") and feature=="scaled":
            # A low swept crest gives Ssarathi a readable silhouette without
            # changing the shared skeleton or enhanced-actor atlas contract.
            ellipsoid((0,.02,1.68*height),(.12,.18,.32),3,vertices,faces,head_uv,5,8)
        if section in ("all","shirt") and feature=="crystal":
            for side in (-1,1):
                ellipsoid((side*.32*gender_width,0,1.36*height),(.12,.17,.28),2,vertices,faces,torso_uv,5,8)
        if section in ("all","shirt") and feature=="stone":
            # Broad, low-resolution plates read as hewn anatomy while keeping
            # deformation concentrated around the underlying humanoid joints.
            for side in (-1,1):
                ellipsoid((side*.25*gender_width,-.01,1.31*height),(.24,.20,.20),2,vertices,faces,torso_uv,4,7)
            ellipsoid((0,.01,1.18*height),(.46,.25,.32),2,vertices,faces,torso_uv,5,8)
        if section in ("all","head") and feature=="stone":
            for side in (-1,1):
                ellipsoid((side*.095,-.005,1.76*height),(.09,.13,.19),3,vertices,faces,head_uv,4,6)
        if section in ("all","head") and feature=="fungal":
            # Layered cap and smaller shelf growths follow the concept's wide
            # silhouette but remain on the head bone for stable animation.
            ellipsoid((0,-.005,1.78*height),(.46,.39,.13),3,vertices,faces,head_uv,6,18)
            ellipsoid((-.17,.015,1.69*height),(.18,.16,.08),3,vertices,faces,head_uv,5,12)
            ellipsoid((.18,.025,1.66*height),(.15,.14,.07),3,vertices,faces,head_uv,5,12)
        if section in ("all","shirt") and feature=="fungal":
            for side in (-1,1):
                ellipsoid((side*.27*gender_width,.035,1.31*height),(.14,.13,.07),2,vertices,faces,torso_uv,4,10)
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

def quat_axis(axis,a):
    value=[0.,0.,0.]; value[axis]=math.sin(a/2)
    return *value,math.cos(a/2)
def quat_x(a): return quat_axis(0,a)
def animation(path,duration,poses,bones=BONES):
    tracks=sorted({b for _,frame in poses for b in frame}); root=ET.Element("ANIMATION",DURATION=str(duration),NUMTRACKS=str(len(tracks)))
    for bone in tracks:
        tr=ET.SubElement(root,"TRACK",BONEID=str(bone),NUMKEYFRAMES=str(len(poses)))
        for time,frame in poses:
            key=ET.SubElement(tr,"KEYFRAME",TIME=str(time))
            ET.SubElement(key,"TRANSLATION").text="%g %g %g"%bones[bone][2]
            ET.SubElement(key,"ROTATION").text="%g %g %g %g"%quat_x(frame.get(bone,0.))
    write_cal(path,"XAF",root)
    binary_animation(path.with_suffix(".caf"),duration,poses,tracks,bones)

CULTURES={
 "luminous":((190,139,104),(224,179,139),(238,207,174)),
 "votary":((107,104,82),(161,145,108),(202,184,142)),
 "glasswarden":((116,83,69),(168,121,91),(211,167,128)),
 "orun":((126,91,74),(184,139,105),(224,188,148)),
 "greyhaven":((102,76,66),(153,111,89),(198,153,119)),
 "ssarathi":((64,112,103),(91,153,126),(139,190,151)),
 "stoneborn":((73,69,66),(116,105,91),(164,151,130)),
 "mycelari":((72,94,68),(117,139,91),(178,184,125)),
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

def actor_texture(path, width, height, base, accent, style=0, levels=3, role="cloth", motif=""):
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
                    if motif=="luminous" and (abs((u*4)%1-.5)<.025 or abs(v-.72)<.018): color=accent
                    elif motif=="votary" and abs(abs(u-.5)*1.8-(v-.22)% .34)<.025: color=accent
                    elif motif=="orun" and abs(abs(u-.5)+abs(v-.52)-(.18+.06*(style%3)))<.022: color=accent
                    elif motif=="greyhaven" and (int(v*12+style)%4==0 and (y%max(2,5>>level))<2): color=accent
                    elif motif=="glasswarden" and abs(abs(u-.5)+abs(v-.5)-.22)<.018: color=accent
                    elif motif=="ssarathi" and ((int(u*18)+int(v*22)+style)%5==0): color=accent
                    elif motif=="stoneborn" and (abs((u*7+v*5+style*.13)%1-.5)<.035): color=accent
                    elif motif=="mycelari" and (((int(u*15)+int(v*17)+style)%7==0) or (u-.5)**2+(v-.5)**2<.012): color=accent
                elif role == "leather":
                    detail += ((x*5+y*11+style*23)%17)-8
                    if abs(u-.12)<.012 or abs(u-.88)<.012 or abs(v-.18)<.012: color=accent
                    if ((x+y+style*7)%max(5,23>>level))==0: detail-=12
                r,g,b=(max(0,min(255,c+detail)) for c in color)
                data.extend((b,g,r,255))
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(b'DDS '+struct.pack('<31I',*header)+data)

def generate_customization(root):
    wardrobe={
        "luminous":((39,112,126),(214,188,111),(28,62,78),(104,76,48)),
        "votary":((126,157,176),(226,231,228),(66,78,91),(93,100,105)),
        "glasswarden":((92,61,128),(191,142,65),(55,47,72),(105,73,45)),
        "orun":((159,78,35),(219,166,72),(83,59,38),(122,73,34)),
        "greyhaven":((48,73,91),(154,174,171),(42,54,66),(89,66,47)),
        "ssarathi":((45,111,88),(184,151,70),(39,72,65),(85,68,43)),
        "stoneborn":((91,83,76),(103,184,191),(66,61,58),(72,61,51)),
        "mycelari":((91,119,65),(211,151,98),(56,77,53),(83,61,43)),
    }
    def harmonize(colors,target,amount=.38):
        return tuple(tuple(round(value*(1-amount)+target[i]*amount) for i,value in enumerate(color))
                     for color in colors)
    for culture,skins in CULTURES.items():
        directory=root/f"actors/custom/{culture}"
        cloth_accent,trim,pants_target,leather_target=wardrobe[culture]
        cloth_palette=harmonize(CLOTH,cloth_accent)
        pants_palette=harmonize(PANTS,pants_target,.32)
        boots_palette=harmonize(BOOTS,leather_target,.30)
        dark_blue=(55,79,105) if culture=="votary" else tuple(max(35,c-35) for c in skins[0])
        white=(222,224,216) if culture!="ssarathi" else (169,207,178)
        skin_palette=(skins[0],skins[1],skins[2],skins[1],dark_blue,white)
        for i,color in enumerate(skin_palette):
            actor_texture(directory/f"skin_{i}_hands.dds",64,64,color,trim,i,role="skin",motif=culture)
            actor_texture(directory/f"skin_{i}_head.dds",128,128,color,trim,i,role="skin",motif=culture)
        for i,color in enumerate(HAIR):actor_texture(directory/f"hair_{i}.dds",136,192,color,tuple(min(255,c+35) for c in color),i,role="hair",motif=culture)
        for i,color in enumerate(EYES):actor_texture(directory/f"eyes_{i}.dds",24,24,color,(235,235,220),i,role="eyes",motif=culture)
        for i,color in enumerate(cloth_palette):
            actor_texture(directory/f"shirt_{i}_torso.dds",196,216,color,trim,i,role="cloth",motif=culture)
            actor_texture(directory/f"shirt_{i}_arms.dds",160,160,color,trim,i,role="cloth",motif=culture)
        for i,color in enumerate(pants_palette):actor_texture(directory/f"pants_{i}.dds",160,160,color,trim,i,role="pants",motif=culture)
        for i,color in enumerate(boots_palette):actor_texture(directory/f"boots_{i}.dds",156,160,color,trim,i,role="leather",motif=culture)

def actor_defs(path):
    files={"CAL_walk":"walk","CAL_run":"run","CAL_idle":"idle","CAL_idle2":"idle2","CAL_combat_idle":"combat_idle","CAL_attack_up_1":"attack","CAL_attack_down_1":"attack","CAL_attack_cast":"cast","CAL_pain1":"pain","CAL_pain2":"pain","CAL_die1":"die","CAL_die2":"die","CAL_harvest":"harvest","CAL_pick":"pick","CAL_drop":"drop","CAL_idle_sit":"sit","CAL_sit_down":"sit_down","CAL_stand_up":"stand_up"}
    root=ET.Element("actors")
    for race_index,(culture,label,_,_) in enumerate(RACES):
      for gender,aid in zip(("female","male"),PLAYER_ACTOR_TYPES[race_index]):
        model=f"{culture}_{gender}"
        a=ET.SubElement(root,"actor",id=str(aid),type=f"Eloria {label} {gender.title()}",race=culture,gender=gender)
        ET.SubElement(a,"skeleton").text=f"actors/playable/{model}.csf"; ET.SubElement(a,"step_duration").text="250"
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
        for tag,animation_name in files.items():
            kind=0 if tag in ("CAL_walk","CAL_run","CAL_idle","CAL_idle2","CAL_idle_sit","CAL_combat_idle") else 1
            ET.SubElement(frames,tag).text=f"animations/playable/{model}/{animation_name}.caf {kind}"
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
    anims={"idle":(2.,[(0,{2:-.03}),(1,{2:.03}),(2,{2:-.03})]),
           "idle2":(3.,[(0,{1:-.025,4:.06}),(1.5,{1:.025,6:.08}),(3.,{1:-.025,4:.06})]),
           "combat_idle":(2.,[(0,{4:-.32,6:-.32}),(1,{2:.04,4:-.28,6:-.36}),(2.,{4:-.32,6:-.32})]),
           "walk":(1.,[(0,{4:.5,6:-.5,8:-.55,11:.55}),(.5,{4:-.5,6:.5,8:.55,11:-.55}),(1,{4:.5,6:-.5,8:-.55,11:.55})]),
           "run":(.7,[(0,{4:.8,6:-.8,8:-.85,11:.85}),(.35,{4:-.8,6:.8,8:.85,11:-.85}),(.7,{4:.8,6:-.8,8:-.85,11:.85})]),
           "attack":(.65,[(0,{2:-.15,6:-.5}),(.3,{2:.55,6:1.5,7:.7}),(.65,{2:-.15,6:-.5})]),
           "cast":(1.1,[(0,{4:-.2,6:-.2}),(.55,{4:.75,6:.75,5:-.45,7:-.45}),(1.1,{4:-.2,6:-.2})]),
           "pain":(.45,[(0,{}),(.2,{2:-.35,4:-.25,6:-.25}),(.45,{})]),
           "die":(1.2,[(0,{}),(.6,{1:-.8,2:-.8}),(1.2,{1:-1.45,2:-1.45})]),
           "harvest":(1.1,[(0,{}),(.55,{2:.45,4:1.,6:1.}),(1.1,{})]),
           "pick":(.8,[(0,{}),(.4,{1:.35,2:.48,6:.3}),(.8,{})]),
           "drop":(.7,[(0,{6:.2}),(.35,{6:.75,7:.3}),(.7,{})]),
           "sit_down":(.8,[(0,{}),(.8,{8:1.35,9:-1.35,11:1.35,12:-1.35})]),
           "sit":(2.,[(0,{8:1.35,9:-1.35,11:1.35,12:-1.35}),(1,{2:.04,8:1.35,9:-1.35,11:1.35,12:-1.35}),(2.,{8:1.35,9:-1.35,11:1.35,12:-1.35})]),
           "stand_up":(.8,[(0,{8:1.35,9:-1.35,11:1.35,12:-1.35}),(.8,{})])}
    for culture,_,_,_ in RACES:
        for gender in ("female","male"):
            model=f"{culture}_{gender}";bones=fitted_bones(culture,gender)
            skeleton(root/f"actors/playable/{model}.xsf",bones)
            for name,(duration,poses) in anims.items():
                animation(root/f"animations/playable/{model}/{name}.xaf",duration,poses,bones)
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
    for name in ("idle","walk","run","attack","pain","die","harvest","sit"):
        duration,poses=anims[name]
        animation(root/f"animations/eloria/{name}.xaf",duration,poses)
    actor_defs(root/"actor_defs/actor_defs.xml")
if __name__=="__main__": main()

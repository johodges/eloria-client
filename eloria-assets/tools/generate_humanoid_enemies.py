#!/usr/bin/env python3
"""Generate original formerly-humanoid enemies and constructs for Eloria."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from generate_bootstrap_pack import png
from generate_characters import BONES, cuboid, profile_surface, skeleton, write_cal

ACTOR_BASE = 232
ENEMIES = (
    ("bandit", "Bandit", "living", (102, 72, 50), "hood", 1.00),
    ("cultist", "Cultist", "living", (83, 48, 74), "hood", 1.00),
    ("skeleton_warrior", "Skeleton Warrior", "undead", (188, 183, 157), "bones", .96),
    ("mummy", "Mummy", "undead", (154, 139, 105), "wraps", .98),
    ("ghoul", "Ghoul", "undead", (91, 113, 78), "claws", .94),
    ("plague_zombie", "Plague Zombie", "undead", (103, 117, 82), "ragged", 1.02),
    ("lich", "Lich", "undead", (88, 112, 151), "crown", 1.06),
    ("stone_golem", "Stone Golem", "construct", (104, 103, 97), "golem", 1.24),
    ("iron_golem", "Iron Golem", "construct", (89, 96, 98), "golem", 1.28),
    ("frost_revenant", "Frost Revenant", "undead", (139, 185, 197), "spikes", 1.08),
    ("flame_wraith", "Flame Wraith", "spirit", (184, 68, 42), "wraith", 1.04),
    ("fallen_knight", "Fallen Knight", "undead", (78, 75, 73), "armor", 1.10),
)

def ellipsoid(center, size, bone, vertices, faces, rings=10, sides=18):
    """Add a closed, smoothly-normalled ellipsoid without degenerate pole faces."""
    cx,cy,cz=center; sx,sy,sz=(q/2 for q in size)
    bottom=len(vertices); vertices.append(((cx,cy,cz-sz),(0,0,-1),(.5,1),bone))
    ring_ids=[]
    for ring in range(1,rings):
        theta=math.pi-math.pi*ring/rings; ids=[]
        for side in range(sides):
            phi=2*math.pi*side/sides; nx=math.sin(theta)*math.cos(phi); ny=math.sin(theta)*math.sin(phi); nz=math.cos(theta)
            length=math.sqrt((nx/max(sx,.001))**2+(ny/max(sy,.001))**2+(nz/max(sz,.001))**2)
            normal=(nx/max(sx,.001)/length,ny/max(sy,.001)/length,nz/max(sz,.001)/length)
            ids.append(len(vertices)); vertices.append(((cx+sx*nx,cy+sy*ny,cz+sz*nz),normal,(side/sides,ring/rings),bone))
        ring_ids.append(ids)
    top=len(vertices); vertices.append(((cx,cy,cz+sz),(0,0,1),(.5,0),bone))
    first=ring_ids[0]; last=ring_ids[-1]
    for side in range(sides):
        nxt=(side+1)%sides
        faces.append((bottom,first[nxt],first[side]))
        faces.append((top,last[side],last[nxt]))
    for lower,upper in zip(ring_ids,ring_ids[1:]):
        for side in range(sides):
            nxt=(side+1)%sides
            faces.extend(((lower[side],upper[nxt],upper[side]),(lower[side],lower[nxt],upper[nxt])))

def material_pixel(base, feature):
    accent=tuple(min(255,int(c*1.32)+12) for c in base)
    dark=tuple(max(0,int(c*.52)) for c in base)
    def pixel(x,y):
        u=x/1023; v=y/1023
        weave=((x*19+y*31+(x^y)*7)%29)-14
        seam_width=3
        seams=(x%128<seam_width or y%128<seam_width)
        culture=feature.split(':')[1] if feature.startswith('nymara:') else 'luminous' if feature.startswith('civic_') else ''
        role=feature.split(':')[2] if feature.startswith('nymara:') else feature.removeprefix('civic_')
        # Layered cloth/leather/metal zones with a culture-specific border and
        # profession sigil. These remain deterministic while reading as an
        # authored costume rather than a tiled placeholder.
        leather=(v>.72) or (u<.13) or (u>.87)
        metal=role in ('guard','warrior','mounted_warden','glacier_guardian') and (.20<u<.80 and .16<v<.46)
        border=abs(u-.5)<.012 or abs(v-.12)<.010 or abs(v-.68)<.010
        sigil=((u-.5)**2+(v-.37)**2 < .0045) or (abs(u-.5)<.018 and .25<v<.49)
        if culture=='ssarathi': sigil=((int(u*18)+int(v*18))%7==0 and .22<v<.60)
        elif culture=='glasswarden': sigil=abs(abs(u-.5)+abs(v-.38)-.11)<.012
        elif culture=='orun': sigil=abs((u-.5)*1.6-(v-.38))<.012 and .25<v<.52
        color=(tuple(min(255,c+42) for c in accent) if metal else dark if leather else accent if border or sigil else base)
        detail=weave + (18 if metal and ((x//18+y//18)&1) else 0)
        if seams: detail-=22
        if leather: detail+=((x*5+y*11)%19)-9
        return (*(max(0,min(255,c+detail)) for c in color),255)
    return pixel


def enemy_mesh(path, feature, scale):
    vertices, faces = [], []
    thin = .72 if feature in ("bones", "wraith") else 1.0
    heavy = 1.35 if feature == "golem" else 1.0
    parts = (
        ((0,0,1.25),(.52*heavy,.30*heavy,.66),2), ((0,0,1.78),(.34*heavy,.32,.38),3),
        ((-.48*heavy,0,1.42),(.42*heavy,.20*heavy,.20*thin),4),
        ((-.78*heavy,0,1.42),(.34*heavy,.17*heavy,.17*thin),5),
        ((.48*heavy,0,1.42),(.42*heavy,.20*heavy,.20*thin),6),
        ((.78*heavy,0,1.42),(.34*heavy,.17*heavy,.17*thin),7),
        ((-.15,0,.68),(.22*heavy,.26*heavy,.54*thin),8), ((-.15,0,.22),(.20*heavy,.23*heavy,.48*thin),9),
        ((-.15,.09,-.03),(.22*heavy,.42*heavy,.14),10),
        ((.15,0,.68),(.22*heavy,.26*heavy,.54*thin),11), ((.15,0,.22),(.20*heavy,.23*heavy,.48*thin),12),
        ((.15,.09,-.03),(.22*heavy,.42*heavy,.14),13),
    )
    # One connected torso, arm and leg shell replaces the disconnected
    # ellipsoid mannequin while preserving the established T-pose rig.
    profile_surface([(0,0,.88*scale,.20*heavy*scale,.15*heavy*scale),(0,0,1.12*scale,.30*heavy*scale,.18*heavy*scale),(0,0,1.42*scale,.31*heavy*scale,.18*heavy*scale),(0,0,1.62*scale,.22*heavy*scale,.15*heavy*scale)],
                    [1,2,2,25],vertices,faces,sides=22)
    for side,bones in ((-1,[28,4,5,16]),(1,[29,6,7,17])):
        profile_surface([(side*.24*heavy*scale,0,1.50*scale,.14*heavy*scale,.14*scale),(side*.48*heavy*scale,0,1.42*scale,.12*heavy*scale,.12*thin*scale),(side*.76*heavy*scale,0,1.42*scale,.105*heavy*scale,.105*thin*scale),(side*.98*heavy*scale,0,1.42*scale,.11*heavy*scale,.12*scale)],bones,vertices,faces,sides=18)
    for side,bones in ((-1,[8,8,9,10]),(1,[11,11,12,13])):
        profile_surface([(side*.15*scale,0,.91*scale,.14*heavy*scale,.15*heavy*scale),(side*.15*scale,0,.65*scale,.13*heavy*scale,.14*thin*scale),(side*.15*scale,.02,.30*scale,.105*heavy*scale,.115*thin*scale),(side*.15*scale,.12,-.03*scale,.12*heavy*scale,.23*scale)],bones,vertices,faces,sides=18)
    ellipsoid((0,0,1.78*scale),(.34*heavy*scale,.32*scale,.38*scale),3,vertices,faces,12,22)
    # Eyes, nose, jaw, ears, hands and boots carry the concept silhouettes at
    # conversational camera distance instead of collapsing into one capsule.
    ellipsoid((0,-.18*scale,1.72*scale),(.22*scale,.15*scale,.20*scale),3,vertices,faces,7,14)
    ellipsoid((0,-.285*scale,1.81*scale),(.07*scale,.14*scale,.13*scale),3,vertices,faces,6,12)
    for side,hand,eye in ((-1,5,30),(1,7,31)):
        ellipsoid((side*.10*scale,-.255*scale,1.84*scale),(.045*scale,.025*scale,.038*scale),eye,vertices,faces,4,8)
        ellipsoid((side*1.00*scale,-.02*scale,1.41*scale),(.20*scale,.18*scale,.20*scale),hand,vertices,faces,6,12)
    if feature in ("hood", "crown", "armor"):
        cuboid((0,0,1.82*scale),(.48*scale,.44*scale,.48*scale),3,vertices,faces)
    if feature == "civic_official":
        ellipsoid((0,0,1.42*scale),(.82*scale,.42*scale,.42*scale),2,vertices,faces,6,12)
        ellipsoid((0,0,1.91*scale),(.43*scale,.38*scale,.25*scale),3,vertices,faces,5,10)
        for x in (-.17,0,.17):
            ellipsoid((x*scale,0,2.14*scale),(.09*scale,.09*scale,.34*scale),3,vertices,faces,5,8)
    if feature == "civic_merchant":
        ellipsoid((0,-.01*scale,1.84*scale),(.48*scale,.43*scale,.46*scale),3,vertices,faces,6,12)
        ellipsoid((-.26*scale,-.18*scale,1.03*scale),(.28*scale,.20*scale,.36*scale),2,vertices,faces,5,8)
        ellipsoid((.26*scale,-.18*scale,1.03*scale),(.28*scale,.20*scale,.36*scale),2,vertices,faces,5,8)
    if feature == "civic_guard":
        ellipsoid((0,0,1.37*scale),(.78*scale,.43*scale,.72*scale),2,vertices,faces,6,12)
        for x,bone in ((-.47,4),(.47,6)):
            ellipsoid((x*scale,0,1.57*scale),(.38*scale,.43*scale,.28*scale),bone,vertices,faces,5,10)
        ellipsoid((0,0,1.91*scale),(.43*scale,.39*scale,.34*scale),3,vertices,faces,6,12)
        ellipsoid((0,-.18*scale,2.02*scale),(.12*scale,.12*scale,.48*scale),3,vertices,faces,5,8)
    if feature == "civic_ferryman":
        ellipsoid((0,0,1.25*scale),(.70*scale,.38*scale,.66*scale),2,vertices,faces,6,12)
        cuboid((0,-.23*scale,1.07*scale),(.74*scale,.08*scale,.17*scale),2,vertices,faces)
        ellipsoid((0,0,1.90*scale),(.48*scale,.42*scale,.22*scale),3,vertices,faces,5,12)
        ellipsoid((0,0,2.04*scale),(.22*scale,.20*scale,.20*scale),3,vertices,faces,5,8)
    if feature == "civic_scholar":
        ellipsoid((0,0,1.31*scale),(.69*scale,.39*scale,.75*scale),2,vertices,faces,6,12)
        cuboid((0,-.23*scale,1.12*scale),(.72*scale,.07*scale,.08*scale),2,vertices,faces)
        for z in (.98,1.12,1.26):
            cuboid((.27*scale,-.25*scale,z*scale),(.16*scale,.09*scale,.07*scale),2,vertices,faces)
        ellipsoid((0,0,1.94*scale),(.47*scale,.42*scale,.17*scale),3,vertices,faces,5,12)
    if feature == "civic_priest":
        ellipsoid((0,0,1.33*scale),(.74*scale,.42*scale,.79*scale),2,vertices,faces,6,12)
        ellipsoid((0,-.22*scale,1.36*scale),(.34*scale,.10*scale,.46*scale),2,vertices,faces,5,10)
        ellipsoid((0,0,1.93*scale),(.45*scale,.40*scale,.31*scale),3,vertices,faces,6,12)
        for x in (-.18,.18):
            ellipsoid((x*scale,0,2.12*scale),(.08*scale,.08*scale,.31*scale),3,vertices,faces,5,8)
    if feature == "civic_civilian":
        ellipsoid((0,0,1.28*scale),(.66*scale,.37*scale,.69*scale),2,vertices,faces,6,12)
        cuboid((0,-.22*scale,.98*scale),(.68*scale,.08*scale,.12*scale),2,vertices,faces)
        ellipsoid((-.28*scale,-.18*scale,1.04*scale),(.24*scale,.17*scale,.31*scale),2,vertices,faces,5,8)
    if feature == "crown":
        for x in (-.16,0,.16): cuboid((x*scale,0,2.12*scale),(.08*scale,.08*scale,.34*scale),3,vertices,faces)
    if feature in ("claws", "ragged"):
        for x,bone in ((-.98,5),(.98,7)): cuboid((x*scale,.03,1.37*scale),(.26*scale,.12*scale,.10*scale),bone,vertices,faces)
    if feature == "wraps":
        for z in (.45,.72,1.12,1.40): cuboid((0,-.17*scale,z*scale),(.64*scale,.08*scale,.08*scale),2,vertices,faces)
    if feature == "spikes":
        for x in (-.34,0,.34): cuboid((x*scale,-.05,1.82*scale),(.10*scale,.12*scale,.55*scale),2,vertices,faces)
    if feature == "armor":
        cuboid((0,0,1.30*scale),(.78*scale,.44*scale,.76*scale),2,vertices,faces)
        cuboid((-.48*scale,0,1.55*scale),(.42*scale,.46*scale,.24*scale),4,vertices,faces)
        cuboid((.48*scale,0,1.55*scale),(.42*scale,.46*scale,.24*scale),6,vertices,faces)
    if feature == "bones":
        for z in (1.12,1.28,1.44): cuboid((0,-.18*scale,z*scale),(.56*scale,.08*scale,.06*scale),2,vertices,faces)
    if feature == "wraith":
        cuboid((0,0,.55*scale),(.72*scale,.66*scale,1.15*scale),1,vertices,faces)
    if feature in ("minotaur", "satyr", "dragon"):
        for x in (-.22,.22):
            cuboid((x*scale,0,2.12*scale),(.11*scale,.10*scale,.48*scale),3,vertices,faces)
    if feature in ("lizard", "snakeman", "gnoll", "werewolf", "dragon"):
        cuboid((0,.25*scale,1.76*scale),(.30*scale,.48*scale,.22*scale),3,vertices,faces)
    if feature in ("lizard", "snakeman", "naga", "dragon", "werewolf"):
        cuboid((0,-.46*scale,.80*scale),(.20*scale,.96*scale,.18*scale),1,vertices,faces)
    if feature == "naga":
        cuboid((0,-.10*scale,.22*scale),(.64*scale,.92*scale,.34*scale),1,vertices,faces)
        cuboid((0,-.62*scale,.16*scale),(.42*scale,.94*scale,.25*scale),1,vertices,faces)
    if feature in ("harpy", "dragon"):
        cuboid((-.70*scale,-.02,1.48*scale),(1.05*scale,.35*scale,.15*scale),2,vertices,faces)
        cuboid((.70*scale,-.02,1.48*scale),(1.05*scale,.35*scale,.15*scale),2,vertices,faces)
    if feature in ("gnoll", "werewolf", "harpy"):
        for x,bone in ((-.98,5),(.98,7)):
            cuboid((x*scale,.04,1.36*scale),(.28*scale,.14*scale,.11*scale),bone,vertices,faces)
    if feature == "vampire":
        cuboid((0,-.22*scale,1.25*scale),(1.28*scale,.12*scale,1.32*scale),2,vertices,faces)
    if feature == "hobgoblin":
        for x in (-.20,.20): cuboid((x*scale,0,2.02*scale),(.18*scale,.10*scale,.30*scale),3,vertices,faces)
    if feature == "orc":
        for x in (-.14,.14): cuboid((x*scale,.22*scale,1.72*scale),(.10*scale,.28*scale,.18*scale),3,vertices,faces)
    if feature == "satyr":
        for x in (-.15,.15): cuboid((x*scale,.13*scale,.02*scale),(.24*scale,.45*scale,.20*scale),10 if x<0 else 13,vertices,faces)
    if feature.startswith("nymara:"):
        _, culture, role = feature.split(":", 2)
        if culture == "votary":
            ellipsoid((0,-.20*scale,1.42*scale),(.76*scale,.10*scale,.82*scale),2,vertices,faces,6,12)
            for x in (-.28,.28): ellipsoid((x*scale,0,2.04*scale),(.10*scale,.10*scale,.36*scale),3,vertices,faces,5,8)
        elif culture == "glasswarden":
            for x,bone in ((-.48,4),(.48,6)):
                ellipsoid((x*scale,0,1.60*scale),(.40*scale,.36*scale,.38*scale),bone,vertices,faces,5,10)
            for x in (-.20,0,.20): cuboid((x*scale,0,2.11*scale),(.10*scale,.10*scale,.44*scale),3,vertices,faces)
        elif culture == "orun":
            cuboid((0,-.22*scale,1.15*scale),(.78*scale,.08*scale,.28*scale),2,vertices,faces)
            for x in (-.21,.21): ellipsoid((x*scale,.09*scale,.03*scale),(.28*scale,.48*scale,.22*scale),10 if x<0 else 13,vertices,faces,5,8)
        elif culture == "greyhaven":
            ellipsoid((0,0,1.92*scale),(.52*scale,.46*scale,.20*scale),3,vertices,faces,5,12)
            cuboid((0,-.23*scale,1.28*scale),(.76*scale,.08*scale,.10*scale),2,vertices,faces)
        elif culture == "ssarathi":
            for z in (1.10,1.30,1.50): ellipsoid((0,-.19*scale,z*scale),(.62*scale,.08*scale,.09*scale),2,vertices,faces,4,10)
            cuboid((0,-.43*scale,.82*scale),(.20*scale,.92*scale,.16*scale),1,vertices,faces)
        # Every profession gets a readable asymmetric badge/tool silhouette.
        code=sum((index+1)*ord(ch) for index,ch in enumerate(role))
        side=-1 if code%2 else 1
        ellipsoid((side*(.31+.004*(code%17))*scale,-.22*scale,(1.00+.003*(code%29))*scale),
                  ((.16+.0001*(code%997))*scale,.10*scale,(.23+.006*len(role))*scale),2,
                  vertices,faces,5,8)
        # Profession-specific garment layers: collars, belts, tabards, bracers
        # and shoulder pieces break the shared mannequin outline.
        ellipsoid((0,0,1.48*scale),(.76*scale,.40*scale,.18*scale),25,vertices,faces,6,14)
        cuboid((0,-.22*scale,1.08*scale),(.72*scale,.075*scale,.10*scale),2,vertices,faces)
        if role in ('guard','warrior','mounted_warden','glacier_guardian'):
            for x,bone in ((-.47,28),(.47,29)):
                ellipsoid((x*scale,0,1.57*scale),(.40*scale,.42*scale,.28*scale),bone,vertices,faces,7,14)
            cuboid((0,-.23*scale,1.35*scale),(.48*scale,.08*scale,.62*scale),2,vertices,faces)
        elif role in ('priest','lake_priest','monk','astronomer','archivist','scholar'):
            ellipsoid((0,-.22*scale,1.35*scale),(.40*scale,.10*scale,.56*scale),2,vertices,faces,7,14)
            for x in (-.14,.14): ellipsoid((x*scale,0,2.10*scale),(.075*scale,.075*scale,.28*scale),3,vertices,faces,5,10)
        else:
            for x,bone in ((-.76,4),(.76,6)):
                cuboid((x*scale,-.11*scale,1.39*scale),(.09*scale,.10*scale,.34*scale),bone,vertices,faces)
    root=ET.Element("MESH",NUMSUBMESH="1")
    sub=ET.SubElement(root,"SUBMESH",NUMVERTICES=str(len(vertices)),NUMFACES=str(len(faces)),MATERIAL="0",NUMLODSTEPS="0",NUMSPRINGS="0",NUMTEXCOORDS="1")
    for i,(pos,norm,uv,bone) in enumerate(vertices):
        v=ET.SubElement(sub,"VERTEX",ID=str(i),NUMINFLUENCES="1")
        ET.SubElement(v,"POS").text="%g %g %g"%pos
        ET.SubElement(v,"NORM").text="%g %g %g"%norm
        ET.SubElement(v,"TEXCOORD").text="%g %g"%uv
        ET.SubElement(v,"INFLUENCE",ID=str(bone)).text="1"
    for tri in faces: ET.SubElement(sub,"FACE",VERTEXID="%d %d %d"%tri)
    write_cal(path,"XMF",root)


def quat(axis, angle):
    v=[0.,0.,0.]; v[axis]=math.sin(angle/2); return (*v,math.cos(angle/2))


def animation(path,duration,poses):
    tracks=sorted({bone for _,frame in poses for bone in frame})
    root=ET.Element("ANIMATION",DURATION=str(duration),NUMTRACKS=str(len(tracks)))
    for bone in tracks:
        track=ET.SubElement(root,"TRACK",BONEID=str(bone),NUMKEYFRAMES=str(len(poses)))
        for time,frame in poses:
            axis,angle=frame.get(bone,(0,0.)); key=ET.SubElement(track,"KEYFRAME",TIME=str(time))
            ET.SubElement(key,"TRANSLATION").text="%g %g %g"%BONES[bone][2]
            ET.SubElement(key,"ROTATION").text="%g %g %g %g"%quat(axis,angle)
    write_cal(path,"XAF",root)


def append_actor_defs(path):
    tree=ET.parse(path); root=tree.getroot()
    frames={"CAL_walk":"walk.xaf","CAL_run":"run.xaf","CAL_idle":"idle.xaf","CAL_idle2":"idle.xaf","CAL_combat_idle":"combat_idle.xaf","CAL_attack_up_1":"attack.xaf","CAL_attack_down_1":"attack.xaf","CAL_pain1":"pain.xaf","CAL_pain2":"pain.xaf","CAL_die1":"die.xaf","CAL_die2":"die.xaf"}
    for index,(slug,label,family,*_) in enumerate(ENEMIES):
        actor=ET.SubElement(root,"actor",id=str(ACTOR_BASE+index),type=label,family=family)
        ET.SubElement(actor,"skeleton").text="actors/enemies/eloria_enemy_humanoid.xsf"
        ET.SubElement(actor,"mesh").text=f"actors/enemies/{slug}.xmf"
        ET.SubElement(actor,"skin").text=f"actors/enemies/{slug}.png"
        ET.SubElement(actor,"step_duration").text="260"
        frame_root=ET.SubElement(actor,"frames")
        for tag,name in frames.items():
            kind=0 if tag in ("CAL_walk","CAL_run","CAL_idle","CAL_idle2","CAL_combat_idle") else 1
            ET.SubElement(frame_root,tag).text=f"animations/enemies/{name} {kind}"
    path.write_text('<?xml version="1.0"?>\n'+ET.tostring(root,encoding="unicode")+'\n',encoding="utf-8")


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("output",nargs="?",default="build/eloria-data")
    root=Path(parser.parse_args().output)
    skeleton(root/"actors/enemies/eloria_enemy_humanoid.xsf")
    for slug,_,_,color,feature,scale in ENEMIES:
        enemy_mesh(root/f"actors/enemies/{slug}.xmf",feature,scale)
        png(root/f"actors/enemies/{slug}.png",512,512,material_pixel(color,feature))
    poses={
      "idle":(2.,[(0,{2:(0,-.04)}),(1,{2:(0,.04)}),(2,{2:(0,-.04)})]),
      "combat_idle":(1.4,[(0,{4:(0,.25),6:(0,-.25)}),(.7,{4:(0,.35),6:(0,-.35)}),(1.4,{4:(0,.25),6:(0,-.25)})]),
      "walk":(1.,[(0,{4:(0,.45),6:(0,-.45),8:(0,-.55),11:(0,.55)}),(.5,{4:(0,-.45),6:(0,.45),8:(0,.55),11:(0,-.55)}),(1,{4:(0,.45),6:(0,-.45),8:(0,-.55),11:(0,.55)})]),
      "run":(.7,[(0,{4:(0,.75),6:(0,-.75),8:(0,-.82),11:(0,.82)}),(.35,{4:(0,-.75),6:(0,.75),8:(0,.82),11:(0,-.82)}),(.7,{4:(0,.75),6:(0,-.75),8:(0,-.82),11:(0,.82)})]),
      "attack":(.68,[(0,{2:(0,-.2),6:(0,-.5)}),(.3,{2:(0,.5),6:(0,1.45),7:(0,.6)}),(.68,{2:(0,-.2),6:(0,-.5)})]),
      "cast":(1.1,[(0,{4:(2,0),6:(2,0)}),(.55,{4:(2,-1.1),6:(2,1.1),2:(0,.25)}),(1.1,{4:(2,0),6:(2,0)})]),
      "pain":(.48,[(0,{2:(0,0)}),(.2,{2:(0,-.38),4:(0,-.2),6:(0,-.2)}),(.48,{2:(0,0)})]),
      "die":(1.25,[(0,{1:(2,0)}),(.65,{1:(2,1.0),2:(0,-.6)}),(1.25,{1:(2,1.48),2:(0,-.8)})]),
    }
    for name,(duration,keys) in poses.items(): animation(root/f"animations/enemies/{name}.xaf",duration,keys)
    append_actor_defs(root/"actor_defs/actor_defs.xml")
    (root/"humanoid_enemies_eloria.json").write_text(json.dumps({"schema":1,"enemies":[{"actor_type":ACTOR_BASE+i,"id":slug,"name":label,"family":family} for i,(slug,label,family,*_) in enumerate(ENEMIES)]},indent=2)+"\n",encoding="utf-8")


if __name__=="__main__": main()

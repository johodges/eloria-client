#!/usr/bin/env python3
"""Generate original formerly-humanoid enemies and constructs for Eloria."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from generate_bootstrap_pack import png
from generate_characters import BONES, cuboid, skeleton, write_cal

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
    for center, size, bone in parts:
        cuboid(tuple(v*scale for v in center), tuple(v*scale for v in size), bone, vertices, faces)
    if feature in ("hood", "crown", "armor"):
        cuboid((0,0,1.82*scale),(.48*scale,.44*scale,.48*scale),3,vertices,faces)
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
        png(root/f"actors/enemies/{slug}.png",256,256,lambda x,y,c=color:(*(max(0,min(255,q+(((x//20)^(y//28))&1)*15)) for q in c),255))
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

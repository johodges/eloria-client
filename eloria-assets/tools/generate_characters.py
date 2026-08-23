#!/usr/bin/env python3
"""Generate an original low-poly Cal3D humanoid and core animation set."""
from __future__ import annotations
import argparse, math
from pathlib import Path
import xml.etree.ElementTree as ET
from generate_bootstrap_pack import png

VERSION = "919"
BONES = (("root",-1,(0.,0.,0.)),("pelvis",0,(0.,0.,.92)),("spine",1,(0.,0.,.34)),
 ("head",2,(0.,0.,.52)),("upper_arm_l",2,(-.32,0.,.38)),("lower_arm_l",4,(-.34,0.,0.)),
 ("upper_arm_r",2,(.32,0.,.38)),("lower_arm_r",6,(.34,0.,0.)),
 ("upper_leg_l",1,(-.15,0.,-.08)),("lower_leg_l",8,(0.,0.,-.48)),("foot_l",9,(0.,.06,-.45)),
 ("upper_leg_r",1,(.15,0.,-.08)),("lower_leg_r",11,(0.,0.,-.48)),("foot_r",12,(0.,.06,-.45)))

def write_cal(path, magic, root):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'<HEADER MAGIC="{magic}" VERSION="{VERSION}"/>\n'+ET.tostring(root,encoding="unicode")+'\n')

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
        b=ET.SubElement(root,"BONE",ID=str(i),NAME=name,NUMCHILDS=str(len(children[i])))
        ET.SubElement(b,"TRANSLATION").text="%g %g %g"%pos
        ET.SubElement(b,"ROTATION").text="0 0 0 1"
        ET.SubElement(b,"LOCALTRANSLATION").text="%g %g %g"%tuple(-v for v in absolute[i])
        ET.SubElement(b,"LOCALROTATION").text="0 0 0 1"
        ET.SubElement(b,"PARENTID").text=str(parent)
        for child in children[i]: ET.SubElement(b,"CHILDID").text=str(child)
    write_cal(path,"XSF",root)

def cuboid(center,size,bone,vertices,faces):
    cx,cy,cz=center; sx,sy,sz=(v/2 for v in size)
    corners=[(cx+x*sx,cy+y*sy,cz+z*sz) for x,y,z in ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1))]
    quads=((0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(4,0,3,7)); normals=((0,0,-1),(0,0,1),(0,-1,0),(1,0,0),(0,1,0),(-1,0,0))
    for quad,normal in zip(quads,normals):
        base=len(vertices)
        for uv,corner in zip(((0,0),(1,0),(1,1),(0,1)),quad): vertices.append((corners[corner],normal,uv,bone))
        faces.extend(((base,base+1,base+2),(base,base+2,base+3)))

def mesh(path):
    vertices=[]; faces=[]
    parts=(((0,0,1.25),(.52,.30,.66),2),((0,0,1.78),(.34,.32,.38),3),
      ((-.48,0,1.42),(.42,.20,.20),4),((-.78,0,1.42),(.34,.17,.17),5),((.48,0,1.42),(.42,.20,.20),6),((.78,0,1.42),(.34,.17,.17),7),
      ((-.15,0,.68),(.22,.26,.54),8),((-.15,0,.22),(.20,.23,.48),9),((-.15,.09,-.03),(.22,.42,.14),10),
      ((.15,0,.68),(.22,.26,.54),11),((.15,0,.22),(.20,.23,.48),12),((.15,.09,-.03),(.22,.42,.14),13))
    for p in parts: cuboid(*p,vertices,faces)
    root=ET.Element("MESH",NUMSUBMESH="1"); sub=ET.SubElement(root,"SUBMESH",NUMVERTICES=str(len(vertices)),NUMFACES=str(len(faces)),MATERIAL="0",NUMLODSTEPS="0",NUMSPRINGS="0",NUMTEXCOORDS="1")
    for i,(pos,norm,uv,bone) in enumerate(vertices):
        v=ET.SubElement(sub,"VERTEX",ID=str(i),NUMINFLUENCES="1")
        ET.SubElement(v,"POS").text="%g %g %g"%pos; ET.SubElement(v,"NORM").text="%g %g %g"%norm; ET.SubElement(v,"TEXCOORD").text="%g %g"%uv; ET.SubElement(v,"INFLUENCE",ID=str(bone)).text="1"
    for tri in faces: ET.SubElement(sub,"FACE",VERTEXID="%d %d %d"%tri)
    write_cal(path,"XMF",root)

def quat_x(a): return math.sin(a/2),0.,0.,math.cos(a/2)
def animation(path,duration,poses):
    tracks=sorted({b for _,frame in poses for b in frame}); root=ET.Element("ANIMATION",DURATION=str(duration),NUMTRACKS=str(len(tracks)))
    for bone in tracks:
        tr=ET.SubElement(root,"TRACK",BONEID=str(bone),NUMKEYFRAMES=str(len(poses)),TRANSLATIONREQUIRED="0",TRANSLATIONISDYNAMIC="0",HIGHRANGEREQUIRED="0")
        for time,frame in poses:
            key=ET.SubElement(tr,"KEYFRAME",TIME=str(time)); ET.SubElement(key,"ROTATION").text="%g %g %g %g"%quat_x(frame.get(bone,0.))
    write_cal(path,"XAF",root)

def actor_defs(path):
    files={"CAL_walk":"walk.xaf","CAL_run":"run.xaf","CAL_idle":"idle.xaf","CAL_idle2":"idle.xaf","CAL_combat_idle":"idle.xaf","CAL_attack_up_1":"attack.xaf","CAL_attack_down_1":"attack.xaf","CAL_pain1":"pain.xaf","CAL_pain2":"pain.xaf","CAL_die1":"die.xaf","CAL_die2":"die.xaf","CAL_harvest":"harvest.xaf","CAL_pick":"harvest.xaf","CAL_drop":"harvest.xaf","CAL_idle_sit":"sit.xaf","CAL_sit_down":"sit.xaf","CAL_stand_up":"idle.xaf"}
    root=ET.Element("actors")
    for aid,label in ((0,"Wanderer"),(1,"Wayfarer"),(2,"Sylvan"),(3,"Stonekin")):
        a=ET.SubElement(root,"actor",id=str(aid),type=f"Eloria {label}")
        ET.SubElement(a,"skeleton").text="actors/eloria_humanoid.xsf"; ET.SubElement(a,"mesh").text="actors/eloria_humanoid.xmf"; ET.SubElement(a,"skin").text="actors/eloria_humanoid.png"; ET.SubElement(a,"step_duration").text="250"
        frames=ET.SubElement(a,"frames")
        for tag,name in files.items(): ET.SubElement(frames,tag).text=f"animations/eloria/{name}"
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text('<?xml version="1.0"?>\n'+ET.tostring(root,encoding="unicode")+'\n')

def main():
    p=argparse.ArgumentParser(); p.add_argument("output",nargs="?",default="build/eloria-data"); root=Path(p.parse_args().output)
    skeleton(root/"actors/eloria_humanoid.xsf"); mesh(root/"actors/eloria_humanoid.xmf")
    png(root/"actors/eloria_humanoid.png",256,256,lambda x,y:(82+(x//32%2)*18,105+(y//32%2)*12,96,255))
    anims={"idle":(2.,[(0,{2:-.03}),(1,{2:.03}),(2,{2:-.03})]),"walk":(1.,[(0,{4:.5,6:-.5,8:-.55,11:.55}),(.5,{4:-.5,6:.5,8:.55,11:-.55}),(1,{4:.5,6:-.5,8:-.55,11:.55})]),"run":(.7,[(0,{4:.8,6:-.8,8:-.85,11:.85}),(.35,{4:-.8,6:.8,8:.85,11:-.85}),(.7,{4:.8,6:-.8,8:-.85,11:.85})]),"attack":(.65,[(0,{2:-.15,6:-.5}),(.3,{2:.55,6:1.5,7:.7}),(.65,{2:-.15,6:-.5})]),"pain":(.45,[(0,{}),(.2,{2:-.35,4:-.25,6:-.25}),(.45,{})]),"die":(1.2,[(0,{}),(.6,{1:-.8,2:-.8}),(1.2,{1:-1.45,2:-1.45})]),"harvest":(1.1,[(0,{}),(.55,{2:.45,4:1.,6:1.}),(1.1,{})]),"sit":(.8,[(0,{}),(.8,{8:1.35,9:-1.35,11:1.35,12:-1.35})])}
    for name,(duration,poses) in anims.items(): animation(root/f"animations/eloria/{name}.xaf",duration,poses)
    actor_defs(root/"actor_defs/actor_defs.xml")
if __name__=="__main__": main()

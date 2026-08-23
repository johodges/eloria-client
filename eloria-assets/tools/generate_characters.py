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
        b=ET.SubElement(root,"BONE",ID=str(i),NAME=name,NUMCHILD=str(len(children[i])))
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

def mesh(path, section="all", variant=0):
    vertices=[]; faces=[]
    parts=(((0,0,1.25),(.52,.30,.66),2),((0,0,1.78),(.34,.32,.38),3),
      ((-.48,0,1.42),(.42,.20,.20),4),((-.78,0,1.42),(.34,.17,.17),5),((.48,0,1.42),(.42,.20,.20),6),((.78,0,1.42),(.34,.17,.17),7),
      ((-.15,0,.68),(.22,.26,.54),8),((-.15,0,.22),(.20,.23,.48),9),((-.15,.09,-.03),(.22,.42,.14),10),
      ((.15,0,.68),(.22,.26,.54),11),((.15,0,.22),(.20,.23,.48),12),((.15,.09,-.03),(.22,.42,.14),13))
    if section=="head":
        head_sizes=((.34,.32,.38),(.36,.30,.36),(.32,.34,.40),(.38,.33,.35),(.33,.29,.42))
        parts=list(parts);parts[1]=((0,0,1.78),head_sizes[variant%len(head_sizes)],3)
    sections={"head":(1,),"shirt":(0,2,3,4,5),"legs":(6,7,9,10),"boots":(8,11),"none":()}
    chosen=range(len(parts)) if section=="all" else sections[section]
    for i in chosen: cuboid(*parts[i],vertices,faces)
    if not vertices:
        cuboid((0,0,-100),(.001,.001,.001),0,vertices,faces)
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
        tr=ET.SubElement(root,"TRACK",BONEID=str(bone),NUMKEYFRAMES=str(len(poses)))
        for time,frame in poses:
            key=ET.SubElement(tr,"KEYFRAME",TIME=str(time))
            ET.SubElement(key,"TRANSLATION").text="%g %g %g"%BONES[bone][2]
            ET.SubElement(key,"ROTATION").text="%g %g %g %g"%quat_x(frame.get(bone,0.))
    write_cal(path,"XAF",root)

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

def actor_texture(path, width, height, base, accent, style=0, levels=3):
    """Write an uncompressed BGRA DDS with the mip levels EL's actor atlas requires."""
    header=[124,0x0002100F,height,width,width*4,0,levels]+[0]*11
    header += [32,0x41,0,32,0x00FF0000,0x0000FF00,0x000000FF,0xFF000000]
    header += [0x401008,0,0,0,0]
    data=bytearray()
    for level in range(levels):
        w=max(1,width>>level); h=max(1,height>>level)
        for y in range(h):
            for x in range(w):
                weave=((x//max(1,8>>level)+y//max(1,8>>level)+style)%2)*8
                seam=18 if x%max(1,64>>level) in (0,1) or y%max(1,64>>level) in (0,1) else 0
                radius=max(1,(20+style%4*3)>>level)
                color=accent if (x-w//2)**2+(y-h//2)**2 < radius*radius else base
                r,g,b=(max(0,min(255,c+weave+seam)) for c in color)
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
            actor_texture(directory/f"skin_{i}_hands.dds",64,64,color,(220,188,150),i)
            actor_texture(directory/f"skin_{i}_head.dds",128,128,color,(220,188,150),i)
        for i,color in enumerate(HAIR):actor_texture(directory/f"hair_{i}.dds",136,192,color,tuple(min(255,c+35) for c in color),i)
        for i,color in enumerate(EYES):actor_texture(directory/f"eyes_{i}.dds",24,24,color,(235,235,220),i)
        for i,color in enumerate(CLOTH):
            actor_texture(directory/f"shirt_{i}_torso.dds",196,216,color,(207,151,70),i)
            actor_texture(directory/f"shirt_{i}_arms.dds",160,160,color,(207,151,70),i)
        for i,color in enumerate(PANTS):actor_texture(directory/f"pants_{i}.dds",160,160,color,(126,104,78),i)
        for i,color in enumerate(BOOTS):actor_texture(directory/f"boots_{i}.dds",156,160,color,(176,137,87),i)

def actor_defs(path):
    files={"CAL_walk":"walk.xaf","CAL_run":"run.xaf","CAL_idle":"idle.xaf","CAL_idle2":"idle.xaf","CAL_combat_idle":"idle.xaf","CAL_attack_up_1":"attack.xaf","CAL_attack_down_1":"attack.xaf","CAL_pain1":"pain.xaf","CAL_pain2":"pain.xaf","CAL_die1":"die.xaf","CAL_die2":"die.xaf","CAL_harvest":"harvest.xaf","CAL_pick":"harvest.xaf","CAL_drop":"harvest.xaf","CAL_idle_sit":"sit.xaf","CAL_sit_down":"sit.xaf","CAL_stand_up":"idle.xaf"}
    root=ET.Element("actors")
    for race_index,(culture,label,_,_) in enumerate(RACES):
      for gender,aid in zip(("female","male"),PLAYER_ACTOR_TYPES[race_index]):
        a=ET.SubElement(root,"actor",id=str(aid),type=f"Eloria {label} {gender.title()}",race=culture,gender=gender)
        ET.SubElement(a,"skeleton").text="actors/eloria_humanoid.xsf"; ET.SubElement(a,"step_duration").text="250"
        prefix=f"actors/custom/{culture}"
        for i in range(len(CLOTH)):
            shirt=ET.SubElement(a,"shirt",id=str(i))
            for tag,value in (("arms",f"{prefix}/shirt_{i}_arms.dds"),("torso",f"{prefix}/shirt_{i}_torso.dds"),("mesh","actors/eloria_shirt.xmf")):ET.SubElement(shirt,tag).text=value
        for i in range(6):
            skin=ET.SubElement(a,"hskin",id=str(i))
            ET.SubElement(skin,"hands").text=f"{prefix}/skin_{i}_hands.dds"
            ET.SubElement(skin,"head").text=f"{prefix}/skin_{i}_head.dds"
        for i in range(len(HAIR)):ET.SubElement(a,"hair",id=str(i)).text=f"{prefix}/hair_{i}.dds"
        for i in range(len(EYES)):ET.SubElement(a,"eyes",id=str(i)).text=f"{prefix}/eyes_{i}.dds"
        for i in range(len(PANTS)):
            legs=ET.SubElement(a,"legs",id=str(i));ET.SubElement(legs,"skin").text=f"{prefix}/pants_{i}.dds";ET.SubElement(legs,"mesh").text="actors/eloria_legs.xmf"
        for i in range(len(BOOTS)):
            boots=ET.SubElement(a,"boots",id=str(i));ET.SubElement(boots,"skin").text=f"{prefix}/boots_{i}.dds";ET.SubElement(boots,"mesh").text="actors/eloria_boots.xmf"
        for i in range(5):
            head=ET.SubElement(a,"head",id=str(i));ET.SubElement(head,"mesh").text=f"actors/eloria_head_{i}.xmf"
        for tag in ("neck","helmet","cape","shield"):
            part=ET.SubElement(a,tag,id="0");ET.SubElement(part,"mesh").text="actors/eloria_none.xmf";ET.SubElement(part,"skin").text="actors/eloria_humanoid.png"
        frames=ET.SubElement(a,"frames")
        for tag,name in files.items():
            kind=0 if tag in ("CAL_walk","CAL_run","CAL_idle","CAL_idle2","CAL_idle_sit","CAL_combat_idle") else 1
            ET.SubElement(frames,tag).text=f"animations/eloria/{name} {kind}"
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text('<?xml version="1.0"?>\n'+ET.tostring(root,encoding="unicode")+'\n')

def main():
    p=argparse.ArgumentParser(); p.add_argument("output",nargs="?",default="build/eloria-data"); root=Path(p.parse_args().output)
    skeleton(root/"actors/eloria_humanoid.xsf"); mesh(root/"actors/eloria_humanoid.xmf")
    for section in ("shirt","legs","boots","none"):mesh(root/f"actors/eloria_{section}.xmf",section)
    for i in range(5):mesh(root/f"actors/eloria_head_{i}.xmf","head",i)
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

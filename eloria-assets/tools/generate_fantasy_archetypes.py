#!/usr/bin/env python3
"""Generate original models for recognizable public-domain fantasy archetypes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from generate_bootstrap_pack import png
from generate_characters import skeleton
from generate_humanoid_enemies import enemy_mesh

ACTOR_BASE=244
ARCHETYPES=(
 ("lizard_man","Lizard Man",(75,119,70),"lizard",1.06),
 ("minotaur","Minotaur",(124,88,55),"minotaur",1.22),
 ("naga","Naga",(68,126,94),"naga",1.10),
 ("snakeman","Snakeman",(91,137,83),"snakeman",1.05),
 ("gnoll","Gnoll",(141,111,65),"gnoll",1.08),
 ("hobgoblin","Hobgoblin",(133,91,60),"hobgoblin",1.02),
 ("orc","Orc",(83,112,62),"orc",1.12),
 ("harpy","Harpy",(145,122,93),"harpy",1.02),
 ("vampire","Vampire",(91,55,67),"vampire",1.04),
 ("werewolf","Werewolf",(92,91,84),"werewolf",1.14),
 ("satyr","Satyr",(132,94,58),"satyr",1.02),
 ("dragon","Dragon",(153,64,43),"dragon",1.32),
)

def append_defs(path):
 tree=ET.parse(path); root=tree.getroot()
 frames={"CAL_walk":"walk.xaf","CAL_run":"run.xaf","CAL_idle":"idle.xaf","CAL_idle2":"idle.xaf","CAL_combat_idle":"combat_idle.xaf","CAL_attack_up_1":"attack.xaf","CAL_attack_down_1":"attack.xaf","CAL_pain1":"pain.xaf","CAL_pain2":"pain.xaf","CAL_die1":"die.xaf","CAL_die2":"die.xaf"}
 for i,(slug,label,*_) in enumerate(ARCHETYPES):
  actor=ET.SubElement(root,"actor",id=str(ACTOR_BASE+i),type=label,family="fantasy")
  ET.SubElement(actor,"skeleton").text="actors/fantasy/eloria_fantasy_humanoid.xsf"
  ET.SubElement(actor,"mesh").text=f"actors/fantasy/{slug}.xmf"
  ET.SubElement(actor,"skin").text=f"actors/fantasy/{slug}.png"
  ET.SubElement(actor,"step_duration").text="255"
  fr=ET.SubElement(actor,"frames")
  for tag,name in frames.items():
   kind=0 if tag in ("CAL_walk","CAL_run","CAL_idle","CAL_idle2","CAL_combat_idle") else 1
   ET.SubElement(fr,tag).text=f"animations/enemies/{name} {kind}"
 path.write_text('<?xml version="1.0"?>\n'+ET.tostring(root,encoding="unicode")+'\n',encoding="utf-8")

def main():
 p=argparse.ArgumentParser(); p.add_argument("output",nargs="?",default="build/eloria-data"); root=Path(p.parse_args().output)
 skeleton(root/"actors/fantasy/eloria_fantasy_humanoid.xsf")
 for slug,_,color,feature,scale in ARCHETYPES:
  enemy_mesh(root/f"actors/fantasy/{slug}.xmf",feature,scale)
  png(root/f"actors/fantasy/{slug}.png",256,256,lambda x,y,c=color:(*(max(0,min(255,q+(((x//18)^(y//22))&1)*17)) for q in c),255))
 append_defs(root/"actor_defs/actor_defs.xml")
 (root/"fantasy_archetypes_eloria.json").write_text(json.dumps({"schema":1,"archetypes":[{"actor_type":ACTOR_BASE+i,"id":slug,"name":label} for i,(slug,label,*_) in enumerate(ARCHETYPES)]},indent=2)+"\n",encoding="utf-8")

if __name__=="__main__": main()

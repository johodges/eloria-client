#!/usr/bin/env python3
"""Generate original NPC models for the independent Eloria test settlement."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import xml.etree.ElementTree as ET
from generate_bootstrap_pack import png
from generate_characters import skeleton
from generate_humanoid_enemies import enemy_mesh

BASE=256
NPCS=(("wayfinder","Wayfinder",(74,105,112),"hood"),("quartermaster","Quartermaster",(116,83,50),"armor"),("healer","Healer",(170,176,150),"wraps"),("blacksmith","Blacksmith",(91,78,68),"armor"),("harvest_tutor","Harvest Tutor",(79,119,72),"ragged"),("arcanist","Arcanist",(87,72,125),"crown"),("town_guard","Town Guard",(89,98,105),"armor"),("ferrymaster","Ferrymaster",(69,87,94),"hood"))

def main():
 p=argparse.ArgumentParser();p.add_argument("output",nargs="?",default="build/eloria-data");root=Path(p.parse_args().output)
 skeleton(root/"actors/npcs/eloria_npc_humanoid.xsf")
 tree=ET.parse(root/"actor_defs/actor_defs.xml");actors=tree.getroot()
 frames={"CAL_walk":"walk.xaf","CAL_run":"run.xaf","CAL_idle":"idle.xaf","CAL_idle2":"idle.xaf","CAL_combat_idle":"combat_idle.xaf","CAL_attack_up_1":"attack.xaf","CAL_pain1":"pain.xaf","CAL_die1":"die.xaf"}
 for i,(slug,label,color,feature) in enumerate(NPCS):
  enemy_mesh(root/f"actors/npcs/{slug}.xmf",feature,1.0)
  png(root/f"actors/npcs/{slug}.png",256,256,lambda x,y,c=color:(*(max(0,min(255,q+(((x//20)^(y//26))&1)*16)) for q in c),255))
  a=ET.SubElement(actors,"actor",id=str(BASE+i),type=label,family="npc");ET.SubElement(a,"skeleton").text="actors/npcs/eloria_npc_humanoid.xsf";ET.SubElement(a,"mesh").text=f"actors/npcs/{slug}.xmf";ET.SubElement(a,"skin").text=f"actors/npcs/{slug}.png";ET.SubElement(a,"step_duration").text="270";fr=ET.SubElement(a,"frames")
  for tag,name in frames.items():ET.SubElement(fr,tag).text=f"animations/enemies/{name}"
 (root/"actor_defs/actor_defs.xml").write_text('<?xml version="1.0"?>\n'+ET.tostring(actors,encoding="unicode")+'\n')
 (root/"npcs_eloria.json").write_text(json.dumps({"schema":1,"npcs":[{"actor_type":BASE+i,"id":s,"name":n} for i,(s,n,*_) in enumerate(NPCS)]},indent=2)+"\n")
if __name__=="__main__":main()

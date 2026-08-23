#!/usr/bin/env python3
"""Generate original projectile models and combat/spell effect atlases."""
from __future__ import annotations
import argparse,math
from pathlib import Path
from generate_bootstrap_pack import png
from generate_item_atlas import dds
from generate_scenery import e3d,texture,box,tapered,crossed_leaves

def arrow(v,i): box(v,i,(0,0,1.1),(.10,.10,2.2));tapered(v,i,2.1,2.55,.24,0,4)
def orb(v,i): tapered(v,i,0,1.0,.55,0,12);tapered(v,i,0,-1.0,.55,0,12)
def shard(v,i): tapered(v,i,-.65,.75,.35,0,6)
def spike(v,i): tapered(v,i,0,1.8,.42,0,6)
def glob(v,i): tapered(v,i,0,.85,.62,0,10)
def wisp(v,i): crossed_leaves(v,i,-.5,.8,1.0,6)
PROJECTILES={"arrow":(arrow,((115,82,47),(195,180,124))),"bolt":(arrow,((75,74,69),(174,145,79))),"fire_orb":(orb,((146,45,29),(244,122,35))),"frost_shard":(shard,((95,154,181),(196,231,239))),"stone_spike":(spike,((79,78,75),(132,126,113))),"poison_glob":(glob,((67,118,54),(139,193,72))),"healing_wisp":(wisp,((84,147,112),(190,235,164))),"portal_spark":(wisp,((101,75,159),(196,139,235)))}
SPELLS=(
 (0,"Embermend","Restore a small amount of health",5,0,(0,7),((70,1,"catalyst"),(20,1,"resonant"),(69,1,"anchor")),None),
 (1,"Farweave Mend","Restore health to a distant target",8,4,(4,0,7),((64,1,"catalyst"),(72,1,"resonant"),(67,1,"anchor")),None),
 (2,"Aegis Veil","Raise resistance to hostile magic",10,6,(5,6,8),((65,1,"catalyst"),(71,1,"resonant"),(68,1,"anchor")),1),
 (3,"Stoneward","Harden your armor for a short time",11,9,(5,3,8),((33,1,"catalyst"),(22,1,"resonant"),(68,1,"anchor")),0),
 (4,"Venom Thread","Afflict a target with lingering venom",14,12,(2,4,9),((70,1,"catalyst"),(66,2,"resonant"),(69,1,"anchor")),None),
 (5,"Blinkstep","Move instantly to a nearby visible place",15,15,(1,3,4),((64,1,"catalyst"),(21,1,"resonant"),(58,1,"anchor")),None),
 (6,"Cinder Lance","Strike a target with focused magical force",25,20,(2,6,9),((23,2,"catalyst"),(22,1,"resonant"),(67,1,"anchor")),None),
 (7,"Deep Renewal","Restore a large amount of your health",25,21,(0,7,10),((65,2,"catalyst"),(72,2,"resonant"),(69,1,"anchor")),None),
 (10,"Siphon Vitality","Steal vitality from a living target",20,27,(1,2,10),((33,2,"catalyst"),(73,2,"resonant"),(68,1,"anchor")),None),
 (14,"Mindwell Draw","Draw ethereal energy from another adventurer",20,40,(1,6,11),((64,2,"catalyst"),(71,2,"resonant"),(67,1,"anchor")),None))
SIGILS=((0,"Kindle"),(1,"Draw"),(2,"Fray"),(3,"Near"),(4,"Path"),(5,"Raise"),(6,"Arcane"),(7,"Vigor"),(8,"Ward"),(9,"Flesh"),(10,"Root"),(11,"Thought"))
def effect_pixel(x,y):
 cell=x//64+(y//64)*8;cx=x%64-32;cy=y%64-32;r=(cx*cx+cy*cy)**.5;palette=((242,92,38),(91,174,218),(191,179,145),(94,188,91),(211,76,76),(214,203,99),(144,94,205),(228,228,218));c=palette[cell%len(palette)];a=max(0,min(255,int(255*(1-r/30)))) if r<30 else 0;return (*c,a)
def main():
 p=argparse.ArgumentParser();p.add_argument("output",nargs="?",default="build/eloria-data");root=Path(p.parse_args().output)
 for name,(fn,colors) in PROJECTILES.items():
  model=root/f"3dobjects/projectiles/{name}.e3d";texture(model.with_suffix('.png'),colors);e3d(model,model.with_suffix('.png').name,fn)
 for name in ("eye_candy","eye_candy_burn","combat_effects"):
  png(root/f"textures/{name}.png",512,512,effect_pixel);dds(root/f"textures/{name}.dds",512,512,effect_pixel)
 xml=['<?xml version="1.0"?>','<missiles>']
 effects={"arrow":"none","bolt":"none","fire_orb":"fire","frost_shard":"ice","stone_spike":"explosive","poison_glob":"magic","healing_wisp":"magic","portal_spark":"magic"}
 for i,name in enumerate(PROJECTILES):
  xml.extend((f'  <missile id="{i}">',f'    <mesh>3dobjects/projectiles/{name}.e3d</mesh>','    <mesh_length>1.0</mesh_length>','    <trace_length>0.65</trace_length>','    <speed>12.0</speed>',f'    <effect>{effects[name]}</effect>','  </missile>'))
 xml.append('</missiles>');(root/"actor_defs/missile_defs.xml").parent.mkdir(parents=True,exist_ok=True);(root/"actor_defs/missile_defs.xml").write_text('\n'.join(xml)+'\n')
 spells=['<?xml version="1.0" encoding="UTF-8"?>','<Magic version="1">','  <Spell_list>']
 for sid,name,desc,mana,level,sigils,reagents,buff in SPELLS:
  spells.extend(('    <spell>',f'      <name>{name}</name>',f'      <desc>{desc}</desc>',f'      <id>{sid}</id>',f'      <group>{0 if sid in (0,1,7) else 2 if sid in (4,6,10,14) else 1}</group>',f'      <icon>{sid}</icon>',f'      <mana>{mana}</mana>',f'      <lvl skill="mag">{level}</lvl>'))
  spells.extend(f'      <sigil>{value}</sigil>' for value in sigils)
  spells.extend(f'      <reagent id="{uid}" uid="{uid}" class="{role}">{qty}</reagent>' for uid,qty,role in reagents)
  if buff is not None: spells.append(f'      <buff>{buff}</buff>')
  spells.append('    </spell>')
 spells.extend(('  </Spell_list>','  <Groups>','    <group id="0">Renewal</group>','    <group id="1">Waycraft</group>','    <group id="2">Battlecraft</group>','  </Groups>','  <Sigil_list>'))
 spells.extend(f'    <sigil id="{sid}" name="{name}">{name.casefold()}</sigil>' for sid,name in SIGILS)
 spells.extend(('  </Sigil_list>','</Magic>'))
 (root/"spells.xml").write_text('\n'.join(spells)+'\n')
 (root/"effects_eloria.lst").write_text('\n'.join(f"{i}|{n}" for i,n in enumerate(PROJECTILES))+"\n")
if __name__=="__main__":main()

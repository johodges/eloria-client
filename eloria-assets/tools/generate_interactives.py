#!/usr/bin/env python3
"""Generate original interactive props and crafting stations as native E3D."""
from __future__ import annotations
import argparse,math
from pathlib import Path
from generate_scenery import e3d,texture,box,tapered,crossed_leaves

def bag(v,i): box(v,i,(0,0,.28),(.75,.62,.55)); tapered(v,i,.48,.72,.22,.10,8)
def portal(v,i):
 box(v,i,(-1,0,1.5),(.45,.55,3));box(v,i,(1,0,1.5),(.45,.55,3));box(v,i,(0,0,2.85),(1.7,.55,.45));tapered(v,i,.15,2.65,.72,.72,12)
def heavy_door(v,i): box(v,i,(0,0,1.35),(1.55,.22,2.7));box(v,i,(0,.16,1.35),(.12,.12,2.5))
def iron_gate(v,i):
 for x in (-.75,-.25,.25,.75):box(v,i,(x,0,1.45),(.10,.18,2.9))
 for z in (.25,1.45,2.65):box(v,i,(0,0,z),(1.9,.18,.10))
def ladder(v,i):
 box(v,i,(-.42,0,1.5),(.12,.16,3));box(v,i,(.42,0,1.5),(.12,.16,3))
 for z in (.25,.65,1.05,1.45,1.85,2.25,2.65):box(v,i,(0,0,z),(.9,.14,.10))
def cave(v,i): tapered(v,i,0,3.1,2.1,.35,10);box(v,i,(0,.45,1.15),(1.65,1.0,2.3))
def boat(v,i): box(v,i,(0,0,.35),(1.8,4.0,.45));box(v,i,(-.92,0,.75),(.18,4,.8));box(v,i,(.92,0,.75),(.18,4,.8))
def chest(v,i): box(v,i,(0,0,.55),(1.45,.85,1.1));box(v,i,(0,-.46,.58),(.26,.10,.32))
def bed(v,i): box(v,i,(0,0,.5),(1.5,2.5,.35));box(v,i,(0,-1.12,.83),(1.45,.25,.65))
def chair(v,i): box(v,i,(0,0,.7),(1,1,.18));box(v,i,(0,-.43,1.35),(1,.16,1.35))
def anvil(v,i): box(v,i,(0,0,.65),(.55,.55,1.3));box(v,i,(0,0,1.35),(1.55,.65,.35))
def forge(v,i): box(v,i,(0,0,.75),(2,1.5,1.5));box(v,i,(0,-.78,1.0),(1.15,.10,.70));tapered(v,i,1.35,2.45,.32,.22,8)
def workbench(v,i): box(v,i,(0,0,1.0),(2.4,1.1,.25));
def loom(v,i): box(v,i,(-.8,0,1.4),(.14,.3,2.8));box(v,i,(.8,0,1.4),(.14,.3,2.8));box(v,i,(0,0,2.65),(1.7,.3,.14));box(v,i,(0,0,.35),(1.7,.3,.14))
def alchemy(v,i): box(v,i,(0,0,.9),(2.0,1.0,.22));
def well(v,i): tapered(v,i,0,1.1,1.15,1.15,12);box(v,i,(-1.15,0,1.8),(.15,.15,2.6));box(v,i,(1.15,0,1.8),(.15,.15,2.6));box(v,i,(0,0,2.9),(2.5,.15,.15))
def shrine(v,i): box(v,i,(0,0,.25),(2,1.5,.5));tapered(v,i,.5,2.7,.62,.38,8)
def board(v,i): box(v,i,(0,0,1.65),(2.2,.18,1.4));box(v,i,(-.75,0,.65),(.15,.15,1.3));box(v,i,(.75,0,.65),(.15,.15,1.3))
def dummy(v,i): box(v,i,(0,0,1.35),(.35,.35,2.7));box(v,i,(0,0,2.35),(1.5,.25,.22));tapered(v,i,2.45,3.0,.38,.30,8)
def brazier(v,i): tapered(v,i,0,.8,.42,.62,8);crossed_leaves(v,i,.65,1.55,.85,5)

ASSETS={"loot_bag":(bag,((109,77,49),(151,107,62))),"portal_obelisk":(portal,((65,75,91),(79,158,182))),"heavy_door":(heavy_door,((91,57,33),(139,91,48))),"iron_gate":(iron_gate,((63,67,71),(117,119,118))),"rope_ladder":(ladder,((111,78,43),(160,116,64))),"cave_entrance":(cave,((69,70,72),(105,102,96))),"rowboat":(boat,((91,60,35),(132,91,50))),"storage_chest":(chest,((104,65,35),(151,102,52))),"bed":(bed,((104,83,60),(142,126,102))),"chair":(chair,((92,61,38),(134,91,51))),"anvil":(anvil,((70,74,78),(126,129,130))),"forge":(forge,((86,69,57),(157,71,38))),"workbench":(workbench,((96,67,42),(142,100,59))),"loom":(loom,((101,73,45),(156,110,67))),"alchemy_table":(alchemy,((79,68,92),(135,90,151))),"well":(well,((91,91,87),(126,122,112))),"shrine":(shrine,((112,108,98),(178,148,78))),"notice_board":(board,((104,70,40),(155,108,62))),"training_dummy":(dummy,((112,79,46),(151,109,65))),"brazier":(brazier,((74,72,70),(230,106,42)))}
def main():
 p=argparse.ArgumentParser();p.add_argument("output",nargs="?",default="build/eloria-data");root=Path(p.parse_args().output)
 for name,(fn,colors) in ASSETS.items():
  model=root/f"3dobjects/interactives/{name}.e3d";texture(model.with_suffix('.png'),colors);e3d(model,model.with_suffix('.png').name,fn)
 (root/"interactives_eloria.lst").write_text('\n'.join(f"{i}|{n}|3dobjects/interactives/{n}.e3d" for i,n in enumerate(ASSETS))+"\n")
if __name__=="__main__":main()

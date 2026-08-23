#!/usr/bin/env python3
"""Generate an original item icon atlas and independent catalog manifest."""
from __future__ import annotations
import argparse,json,struct
from pathlib import Path
from generate_bootstrap_pack import png

ITEMS=("Gold Coins","Bread","Berries","Cooked Meat","Healing Tonic","Focus Tonic","Pickaxe","Hatchet","Needle","Mortar and Pestle","Raw Meat","Bones","Thread","Fox Fur","Bear Fur","Deer Hide","Wolf Fur","Snake Hide","Bright Feather","Small Dragon Scale","Sunleaf","Frost Reed","Copper Bloom","Ember Crystal","Slate","Wheat","Cotton","Lavender","Flax","Sage","Rosemary","Mushroom","Blue Berries","Coal","Iron Ore","Quartz","Sulfur","Magic Essence","Iron Bar","Wood Plank","Cloth Roll","Leather","Wooden Club","Iron Sword","Hunting Bow","Wooden Shield","Cloth Tunic","Leather Armor","Iron Mail","Traveler Boots","Leather Gloves","Iron Helmet","Green Cloak","Silver Pendant","Simple Ring","Arrow","Torch","Storage Token","Portal Shard","Bandage","Antidote","Mana Draught","Summoning Charm","Book of Beginnings")
COLORS=((211,166,54),(190,139,74),(81,126,80),(149,78,61),(190,69,69),(75,112,181),(91,91,96),(121,82,47),(177,177,166),(130,119,91))

def pixels(x,y):
 cell=x//32+(y//32)*16;lx=x%32;ly=y%32;c=COLORS[cell%len(COLORS)];inside=4<lx<27 and 4<ly<27;edge=inside and (lx<7 or lx>24 or ly<7 or ly>24);return (*(c if inside and not edge else ((235,205,112) if edge else (0,0,0))),255 if inside else 0)

def bmp(path,w,h,pixel):
 row=((w*4+3)//4)*4;data=bytearray()
 for y in range(h-1,-1,-1):
  line=bytearray()
  for x in range(w):
   r,g,b,a=pixel(x,y);line.extend((b,g,r,a))
  line.extend(b'\0'*(row-len(line)));data.extend(line)
 path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'BM'+struct.pack('<IHHI',54+len(data),0,0,54)+struct.pack('<IIIHHIIIIII',40,w,h,1,32,0,len(data),2835,2835,0,0)+data)

def dds(path,w,h,pixel):
 header=[124,0x0002100F,h,w,w*4,0,0]+[0]*11+[32,0x41,0,32,0x00FF0000,0x0000FF00,0x000000FF,0xFF000000]+[0x1000,0,0,0,0]
 data=bytearray()
 for y in range(h):
  for x in range(w):
   r,g,b,a=pixel(x,y);data.extend((b,g,r,a))
 path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'DDS '+struct.pack('<31I',*header)+data)

def main():
 p=argparse.ArgumentParser();p.add_argument("output",nargs="?",default="build/eloria-data");root=Path(p.parse_args().output);png(root/"textures/items1.png",512,128,pixels);bmp(root/"textures/items1.bmp",512,128,pixels);dds(root/"textures/items1.dds",512,128,pixels);(root/"items_eloria.json").write_text(json.dumps({"schema":1,"items":[{"item_id":i,"image_id":i,"name":n} for i,n in enumerate(ITEMS)]},indent=2)+"\n")
if __name__=="__main__":main()

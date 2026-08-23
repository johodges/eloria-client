#!/usr/bin/env python3
"""Generate original startup-safe fonts, cursors, fallbacks, and data stubs."""
from __future__ import annotations
import argparse,struct
from pathlib import Path
from generate_bootstrap_pack import png,panel,make_map
from generate_item_atlas import bmp,dds

def font_pixel(x,y):
 cell=x//16+(y//16)*16;lx=x%16;ly=y%16
 if cell==32:return (0,0,0,0)
 bit=((cell*1103515245+(lx//2)*97+(ly//2)*193)>>((lx+ly)%17))&1
 on=2<=lx<=13 and 2<=ly<=13 and (bit or lx in (2,13) or ly in (2,13))
 return (238,231,205,255 if on else 0)
def cursor(x,y):
 lx=x%32;ly=y%32;on=(lx<4 and ly<23) or (ly<4 and lx<16) or abs(lx-ly)<2
 return (240,188,72,255) if on else (0,0,0,0)
def e3d_fallback(path):
 # Use a generated native E3D box from the scenery tool when available.
 from generate_scenery import e3d,box
 def cube(v,i):box(v,i,(0,0,.5),(1,1,1))
 e3d(path,"badobject.png",cube);png(path.with_suffix('.png'),32,32,lambda x,y:(210,55,55,255))
def main():
 p=argparse.ArgumentParser();p.add_argument("output",nargs="?",default="build/eloria-data");root=Path(p.parse_args().output)
 for name in ("font","fontv"):
  png(root/f"textures/{name}.png",256,256,font_pixel);bmp(root/f"textures/{name}.bmp",256,256,font_pixel)
  dds(root/f"textures/{name}.dds",256,256,font_pixel)
 for name in ("cursors","cursors2"):
  png(root/f"textures/{name}.png",256,256,cursor);bmp(root/f"textures/{name}.bmp",256,256,cursor)
  dds(root/f"textures/{name}.dds",256,256,cursor)
 for name in ("buttons","book1","paper1","alphaborder","eye_candy","eye_candy_burn"):
  png(root/f"textures/{name}.png",512,512,panel);bmp(root/f"textures/{name}.bmp",512,512,panel)
  dds(root/f"textures/{name}.dds",512,512,panel)
 for name in ("gamebuttons","gamebuttons2","console","login_menu","login_back","ground_detail","sigils"):
  dds(root/f"textures/{name}.dds",512,512,panel)
 e3d_fallback(root/"3dobjects/badobject.e3d");e3d_fallback(root/"3dobjects/bag1.e3d");e3d_fallback(root/"3dobjects/portal1.e3d")
 make_map(root/"maps/nomap.elm",placements=[]);make_map(root/"maps/newcharactermap.elm",placements=[])
 stubs={"named_colours.xml":"<named_colours/>\n","emotes.xml":"<emotes/>\n","spells.xml":"<spells/>\n","weather.xml":"<weather/>\n","knowledge.xml":"<knowledge/>\n","commands.lst":"# Eloria commands\n","knowledge.lst":"# Eloria knowledge\n","mapinfo.lst":"emberhaven|Emberhaven|maps/emberhaven.elm\n","continfo.lst":"Eloria|maps/legend.png\n"}
 for name,text in stubs.items():(root/name).write_text(text)
if __name__=="__main__":main()

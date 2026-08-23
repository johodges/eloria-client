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
def sky(x,y):
 grain=(x*13+y*29+(x^y)*3)%29
 return (72+grain//3,95+grain//2,126+grain,255)
def moon(x,y):
 dx=x-256;dy=y-256;inside=dx*dx+dy*dy<150*150
 return (224,225,201,255) if inside else (13,20,37,0)
def sun(x,y):
 dx=x-256;dy=y-256;d=dx*dx+dy*dy
 return (255,220,98,255) if d<95*95 else (255,166,53,max(0,180-d//400))
def portrait(x,y):
 cell=(x//128)+(y//128)*4;lx=x%128;ly=y%128
 skin=((126+cell*17)%90+105,(83+cell*11)%65+80,(61+cell*7)%45+65,255)
 if (lx-64)**2+(ly-56)**2<34**2:return skin
 if 42<lx<86 and 84<ly<126:return (42+cell*9,61+cell*7,70+cell*11,255)
 return (24,31,38,255)
def write_text(path,text):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding="utf-8")
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
 for name in ("compass","thick_clouds","thick_clouds_detail"):
  dds(root/f"textures/{name}.dds",512,512,sky)
 dds(root/"textures/moonmap.dds",512,512,moon);dds(root/"textures/BrightSun.dds",512,512,sun)
 dds(root/"textures/portraits1.dds",512,512,portrait)
 dds(root/"maps/legend.dds",512,512,panel)
 e3d_fallback(root/"3dobjects/badobject.e3d");e3d_fallback(root/"3dobjects/bag1.e3d");e3d_fallback(root/"3dobjects/portal1.e3d")
 make_map(root/"maps/nomap.elm",placements=[]);make_map(root/"maps/newcharactermap.elm",placements=[])
 stubs={"named_colours.xml":"<named_colours/>\n","mines.xml":"<mines/>\n","emotes.xml":"<emotes/>\n","spells.xml":"<spells/>\n","weather.xml":"<weather/>\n","knowledge.xml":"<knowledge/>\n","commands.lst":"# Eloria commands\n","knowledge.lst":"# Eloria knowledge\n","servers.lst":"main main 127.0.0.1 2000\n","mapinfo.lst":"emberhaven|Emberhaven|maps/emberhaven.elm\n","continfo.lst":"Nymara|maps/legend.dds\n"}
 for name,text in stubs.items():(root/name).write_text(text)
 write_text(root/"languages/langsel.xml",'<LANGUAGE_LIST><LANG CODE="en" TEXT="English" SAVE="1" DEFAULT="1"/></LANGUAGE_LIST>\n')
 write_text(root/"languages/en/rules.xml",'''<rules>
 <title>Eloria Community Rules</title>
 <rule><short>Respect other players.</short><long>Harassment, threats, impersonation, and targeted abuse are not permitted.</long></rule>
 <rule><short>Play fairly.</short><long>Do not exploit defects, automate play, or interfere with the service or another player.</long></rule>
 <rule><short>Protect the original world.</short><long>Only submit content you have permission to share and respect Eloria's independent asset policy.</long></rule>
 <info>Rules may evolve during testing. Material changes will be announced with the server release notes.</info>
</rules>\n''')
 for name in ("console","errors","help","options","spells","stats","titles"):
  write_text(root/f"languages/en/strings/{name}.xml","<root/>\n")
 write_text(root/"languages/en/Encyclopedia/index.xml","<Encyclopedia><Category>Basics</Category></Encyclopedia>\n")
 write_text(root/"languages/en/Encyclopedia/Basics.xml",'''<Encyclopedia>
 <Page name="index"><Size>Big</Size><Text>Welcome to Eloria</Text><nl/><Size>Small</Size><Text>An original world on the continent of Nymara.</Text></Page>
 <Page name="HelpPage"><Size>Big</Size><Text>Getting Started</Text><nl/><Size>Small</Size><Text>Explore Emberhaven, speak with its residents, gather resources, and craft your first supplies.</Text></Page>
 <Page name="newskills"><Size>Big</Size><Text>Skills</Text><nl/><Size>Small</Size><Text>Skills improve through use. The testing build emphasizes gathering, crafting, combat, and magic.</Text></Page>
</Encyclopedia>\n''')
if __name__=="__main__":main()

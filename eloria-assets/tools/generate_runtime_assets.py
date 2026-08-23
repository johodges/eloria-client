#!/usr/bin/env python3
"""Generate original startup-safe fonts, cursors, fallbacks, and data stubs."""
from __future__ import annotations
import argparse,shutil,struct
from pathlib import Path
from generate_bootstrap_pack import png,panel,make_map
from generate_item_atlas import bmp,dds

def font_pixel(x,y):
 cell=x//16+(y//16)*16;lx=x%16;ly=y%16
 if cell==32:return (0,0,0,0)
 bit=((cell*1103515245+(lx//2)*97+(ly//2)*193)>>((lx+ly)%17))&1
 on=2<=lx<=13 and 2<=ly<=13 and (bit or lx in (2,13) or ly in (2,13))
 return (238,231,205,255 if on else 0)
CURSOR_COUNT, CURSOR_SIZE = 13, 16

def cursor_index(x,y):
 lx=x%CURSOR_SIZE;ly=y%CURSOR_SIZE
 outline=(lx<=ly+1 and lx<7 and ly<13) or (ly in (1,2) and lx<10)
 fill=(lx<=ly and lx<5 and 2<=ly<11) or (ly==3 and 2<=lx<8)
 return 2 if outline and not fill else 1 if fill else 0

def cursor_pixel(x,y):
 return ((255,255,255,255),(255,255,255,255),(0,0,0,255),(128,128,128,255))[cursor_index(x,y)]

def indexed_cursor_bmp(path):
 w,h=CURSOR_COUNT*CURSOR_SIZE,CURSOR_SIZE
 row=(w+3)&~3
 palette=b"\\x00\\x00\\x00\\x00"+b"\\xff\\xff\\xff\\x00"+b"\\x00\\x00\\x00\\x00"+b"\\x80\\x80\\x80\\x00"
 pixels=bytearray()
 for y in range(h-1,-1,-1):
  line=bytearray(cursor_index(x,y) for x in range(w))
  line.extend(b"\\0"*(row-w));pixels.extend(line)
 offset=14+40+len(palette)
 header=b"BM"+struct.pack("<IHHI",offset+len(pixels),0,0,offset)
 dib=struct.pack("<IIIHHIIIIII",40,w,h,1,8,0,len(pixels),2835,2835,4,4)
 path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(header+dib+palette+pixels)

def validate_cursor_bmp(path):
 data=path.read_bytes()
 if len(data)<70 or data[:2]!=b"BM":
  raise ValueError(f"{path}: invalid BMP")
 w,h,planes,bpp=struct.unpack_from("<iiHH",data,18)
 colours=struct.unpack_from("<I",data,46)[0]
 if (w,h,planes,bpp,colours)!=(CURSOR_COUNT*CURSOR_SIZE,CURSOR_SIZE,1,8,4):
  raise ValueError(f"{path}: cursor sheet must be 208x16, 8-bit, four-colour indexed BMP")
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
 for name in ("font","fontv","font2","font3","font5","font6","font7"):
  png(root/f"textures/{name}.png",256,256,font_pixel);bmp(root/f"textures/{name}.bmp",256,256,font_pixel)
  dds(root/f"textures/{name}.dds",256,256,font_pixel)
 for name in ("cursors","cursors2"):
  png(root/f"textures/{name}.png",CURSOR_COUNT*CURSOR_SIZE,CURSOR_SIZE,cursor_pixel)
  indexed_cursor_bmp(root/f"textures/{name}.bmp")
  validate_cursor_bmp(root/f"textures/{name}.bmp")
  dds(root/f"textures/{name}.dds",CURSOR_COUNT*CURSOR_SIZE,CURSOR_SIZE,cursor_pixel)
 for name in ("buttons","book1","paper1","alphaborder","eye_candy","eye_candy_burn"):
  png(root/f"textures/{name}.png",512,512,panel);bmp(root/f"textures/{name}.bmp",512,512,panel)
  dds(root/f"textures/{name}.dds",512,512,panel)
 for name in ("gamebuttons","gamebuttons2","console","login_menu","login_back","ground_detail","sigils"):
  dds(root/f"textures/{name}.dds",512,512,panel)
 for name in ("compass","thick_clouds","thick_clouds_detail"):
  dds(root/f"textures/{name}.dds",512,512,sky)
 dds(root/"textures/moonmap.dds",512,512,moon);dds(root/"textures/BrightSun.dds",512,512,sun)
 dds(root/"textures/portraits1.dds",512,512,portrait)
 bmp(root/"icon.bmp",32,32,cursor)
 dds(root/"maps/legend.dds",512,512,panel)
 e3d_fallback(root/"3dobjects/badobject.e3d");e3d_fallback(root/"3dobjects/bag1.e3d");e3d_fallback(root/"3dobjects/portal1.e3d")
 make_map(root/"maps/nomap.elm",placements=[]);make_map(root/"maps/newcharactermap.elm",placements=[])
 stubs={"el.ini":"","named_colours.xml":"<named_colours/>\n","mines.xml":"<mines/>\n","emotes.xml":"<emotes/>\n","spells.xml":"<spells/>\n","weather.xml":"<weather/>\n","knowledge.xml":"<knowledge/>\n","commands.lst":"# Eloria commands\n","knowledge.lst":"# Eloria knowledge\n","servers.lst":"main main 127.0.0.1 2000\n","mapinfo.lst":"emberhaven|Emberhaven|maps/emberhaven.elm\n","continfo.lst":"Nymara|maps/legend.dds\n"}
 for name,text in stubs.items():(root/name).write_text(text)
 write_text(root/"languages/langsel.xml",'<LANGUAGE_LIST><LANG CODE="en" TEXT="English" SAVE="1" DEFAULT="1"/></LANGUAGE_LIST>\n')
 write_text(root/"languages/en/knowledge.lst","")
 shader_dir=root/"shaders";shader_dir.mkdir(parents=True,exist_ok=True)
 legacy_fragment="void main(){ gl_FragColor=gl_Color; }\n"
 compat_vertex="#version 120\nvoid main(){ gl_Position=ftransform(); gl_FrontColor=gl_Color; gl_TexCoord[0]=gl_MultiTexCoord0; }\n"
 modern_vertex="in vec4 el_vertex;\nvoid main(){ gl_Position=el_vertex; }\n"
 modern_fragment="out vec4 eloria_colour;\nvoid main(){ eloria_colour=vec4(0.18,0.42,0.58,0.82); }\n"
 for name in ("water_fs.glsl","reflectiv_water_fs.glsl"):write_text(shader_dir/name,legacy_fragment)
 template_dir=Path(__file__).resolve().parents[2]/"shaders"
 for name in ("anim.vert","anim_depth.vert","anim_shadow.vert","anim_ghost.vert","anim_ghost_shadow.vert"):
  source=template_dir/name
  shader=source.read_text(encoding="utf-8")
  if shader.count("%d")!=2:
   raise ValueError(f"{source}: animation template must contain exactly two %d placeholders")
  shutil.copy2(source,shader_dir/name)
 write_text(shader_dir/"new_water.vert",modern_vertex);write_text(shader_dir/"new_water.frag",modern_fragment)
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

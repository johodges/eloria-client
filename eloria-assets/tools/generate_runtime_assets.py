#!/usr/bin/env python3
"""Generate original startup-safe fonts, cursors, fallbacks, and data stubs."""
from __future__ import annotations
import argparse,shutil,struct
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from generate_bootstrap_pack import png,panel,make_map
from generate_item_atlas import bmp,dds

GLYPHS={
"A":("01110","10001","10001","11111","10001","10001","10001"),"B":("11110","10001","10001","11110","10001","10001","11110"),"C":("01111","10000","10000","10000","10000","10000","01111"),"D":("11110","10001","10001","10001","10001","10001","11110"),"E":("11111","10000","10000","11110","10000","10000","11111"),"F":("11111","10000","10000","11110","10000","10000","10000"),"G":("01111","10000","10000","10111","10001","10001","01110"),"H":("10001","10001","10001","11111","10001","10001","10001"),"I":("11111","00100","00100","00100","00100","00100","11111"),"J":("00111","00010","00010","00010","10010","10010","01100"),"K":("10001","10010","10100","11000","10100","10010","10001"),"L":("10000","10000","10000","10000","10000","10000","11111"),"M":("10001","11011","10101","10101","10001","10001","10001"),"N":("10001","11001","10101","10011","10001","10001","10001"),"O":("01110","10001","10001","10001","10001","10001","01110"),"P":("11110","10001","10001","11110","10000","10000","10000"),"Q":("01110","10001","10001","10001","10101","10010","01101"),"R":("11110","10001","10001","11110","10100","10010","10001"),"S":("01111","10000","10000","01110","00001","00001","11110"),"T":("11111","00100","00100","00100","00100","00100","00100"),"U":("10001","10001","10001","10001","10001","10001","01110"),"V":("10001","10001","10001","10001","10001","01010","00100"),"W":("10001","10001","10001","10101","10101","10101","01010"),"X":("10001","10001","01010","00100","01010","10001","10001"),"Y":("10001","10001","01010","00100","00100","00100","00100"),"Z":("11111","00001","00010","00100","01000","10000","11111"),
"0":("01110","10001","10011","10101","11001","10001","01110"),"1":("00100","01100","00100","00100","00100","00100","01110"),"2":("01110","10001","00001","00010","00100","01000","11111"),"3":("11110","00001","00001","01110","00001","00001","11110"),"4":("00010","00110","01010","10010","11111","00010","00010"),"5":("11111","10000","10000","11110","00001","00001","11110"),"6":("01110","10000","10000","11110","10001","10001","01110"),"7":("11111","00001","00010","00100","01000","01000","01000"),"8":("01110","10001","10001","01110","10001","10001","01110"),"9":("01110","10001","10001","01111","00001","00001","01110"),
".":("00000","00000","00000","00000","00000","00110","00110"),",":("00000","00000","00000","00000","00110","00110","00100"),":":("00000","00110","00110","00000","00110","00110","00000"),"-":("00000","00000","00000","11111","00000","00000","00000"),"_":("00000","00000","00000","00000","00000","00000","11111"),"/":("00001","00010","00100","01000","10000","00000","00000"),"!":("00100","00100","00100","00100","00100","00000","00100"),"?":("01110","10001","00001","00010","00100","00000","00100"),"'":("00100","00100","00000","00000","00000","00000","00000"),"(":("00010","00100","01000","01000","01000","00100","00010"),")":("01000","00100","00010","00010","00010","00100","01000"),"+":("00000","00100","00100","11111","00100","00100","00000"),"=":("00000","00000","11111","00000","11111","00000","00000"),"<":("00010","00100","01000","10000","01000","00100","00010"),">":("01000","00100","00010","00001","00010","00100","01000"),"@":("01110","10001","10111","10101","10111","10000","01110")}
def font_pixel(x,y):
 # Bundled fonts use 14 glyphs per row in 18x21 cells; positions 0..94
 # correspond to ASCII 32..126 (see Font::get_position).
 pos=(x//18)+(y//21)*14
 lx=x%18;ly=y%21
 if not 0<=pos<=94:return (0,0,0,0)
 ch=chr(pos+32);g=GLYPHS.get(ch) or GLYPHS.get(ch.upper())
 if not g:return (0,0,0,0)
 gx=(lx-3)//2;gy=(ly-2)//2
 return (244,238,216,255) if 0<=gx<5 and 0<=gy<7 and g[gy][gx]=="1" else (0,0,0,0)
def ttf_font_pixels(font_path):
 atlas=Image.new("RGBA",(256,256),(0,0,0,0));draw=ImageDraw.Draw(atlas)
 font=ImageFont.truetype(str(font_path),16)
 for pos in range(95):
  ch=chr(pos+32);left=(pos%14)*18;top=(pos//14)*21
  box=draw.textbbox((0,0),ch,font=font,stroke_width=1)
  width=box[2]-box[0];height=box[3]-box[1]
  x=left+(18-width)//2-box[0];y=top+(21-height)//2-box[1]
  draw.text((x,y),ch,font=font,fill=(244,238,216,255),
            stroke_width=1,stroke_fill=(8,18,23,230))
 pixels=atlas.load()
 return lambda x,y:pixels[x,y]
CURSOR_COUNT, CURSOR_SIZE = 13, 16

def cursor_index(x,y):
 lx=x%CURSOR_SIZE;ly=y%CURSOR_SIZE
 outline=(lx<=ly+1 and lx<7 and ly<13) or (ly in (1,2) and lx<10)
 fill=(lx<=ly and lx<5 and 2<=ly<11) or (ly==3 and 2<=lx<8)
 return 2 if outline and not fill else 1 if fill else 0

def cursor_pixel(x,y):
 return ((0,0,0,0),(102,220,225,255),(218,160,68,255),(18,43,51,255))[cursor_index(x,y)]

def indexed_cursor_bmp(path):
 w,h=CURSOR_COUNT*CURSOR_SIZE,CURSOR_SIZE
 row=(w+3)&~3
 palette=bytes((0,0,0,0, 225,220,102,0, 68,160,218,0, 51,43,18,0))
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

def window_icon_bmp(source,path):
 # Use the same crest master as the executable's elc.ico.  SDL_LoadBMP does
 # not retain PNG alpha, so composite onto a reserved magenta colour that the
 # client marks transparent immediately after loading.
 icon=Image.open(source).convert("RGBA")
 icon.thumbnail((30,30),Image.Resampling.LANCZOS)
 canvas=Image.new("RGB",(32,32),(255,0,255))
 left=(32-icon.width)//2;top=(32-icon.height)//2
 canvas.paste(icon.convert("RGB"),(left,top),icon.getchannel("A"))
 path.parent.mkdir(parents=True,exist_ok=True);canvas.save(path,"BMP")

def validate_window_icon_bmp(path):
 icon=Image.open(path).convert("RGB")
 if icon.size!=(32,32):raise ValueError(f"{path}: window icon must be 32x32")
 colours=set(icon.getdata())
 if (255,0,255) not in colours or len(colours)<64:
  raise ValueError(f"{path}: window icon lacks transparent surround or crest detail")
def sky(x,y):
 grain=(x*13+y*29+(x^y)*3)%29
 return (72+grain//3,95+grain//2,126+grain,255)
def moon(x,y):
 dx=x-256;dy=y-256;inside=dx*dx+dy*dy<150*150
 return (224,225,201,255) if inside else (13,20,37,0)
def sun(x,y):
 dx=x-256;dy=y-256;d=dx*dx+dy*dy
 return (255,220,98,255) if d<95*95 else (255,166,53,max(0,180-d//400))
def clouds(x,y):
 grain=(x*17+y*31+(x^y)*7)%97
 alpha=max(24,min(210,52+grain+((x//37+y//29)%3)*22))
 return (188+grain//8,202+grain//10,216+grain//12,alpha)
def clouds_detail(x,y):
 grain=(x*43+y*19+(x^y)*11)%113
 alpha=max(12,min(176,28+grain))
 return (172+grain//10,188+grain//11,204+grain//13,alpha)
def login_background(x,y):
 t=y/511.0
 if y<330:r,g,b=int(20+38*t),int(29+34*t),int(58+38*t)
 else:r,g,b=int(13+12*(1-t)),int(31+20*(1-t)),int(43+24*(1-t))
 ridge=270+((x*37)%131)//3
 if 250<y<ridge:r,g,b=31,45,61
 glow=max(0,1-(((x-390)**2+(y-205)**2)**0.5)/175)
 r+=int(75*glow);g+=int(43*glow);b+=int(14*glow)
 if 365<x<415 and 125+abs(x-390)*2<y<285-abs(x-390):return (72+int(90*glow),174+int(60*glow),190+int(55*glow),255)
 if y>=330:
  s=max(0,1-abs(x-390)/170)*max(0,1-(y-330)/210);r+=int(35*s);g+=int(85*s);b+=int(100*s)
 return (min(255,r),min(255,g),min(255,b),255)
def login_menu_pixel(x,y):
 # Atlas regions consumed by loginwin.c.  Each control uses a complete
 # blue-black frame, warm gold bevel, and a restrained teal focus state.
 regions=((0,0,174,28,True),(0,40,170,23,False),
          (0,80,87,35,False),(0,120,87,35,True),
          (100,80,138,35,False),(100,120,138,35,True),
          (0,160,87,35,False),(0,200,87,35,True))
 for left,top,width,height,selected in regions:
  if left<=x<left+width and top<=y<top+height:
   dx=min(x-left,left+width-1-x);dy=min(y-top,top+height-1-y)
   if dx==0 or dy==0:return (20,42,49,255)
   if dx==1 or dy==1:return (218,160,68,255) if selected else (151,108,55,255)
   if dx==2 or dy==2:return (73,154,163,255) if selected else (75,91,88,255)
   depth=(y-top-3)/max(1,height-6)
   if selected:return (27+int(8*depth),68+int(12*depth),76+int(13*depth),244)
   return (15+int(7*depth),29+int(8*depth),34+int(9*depth),242)
 return (0,0,0,0)
def console_panel(x,y):
 edge=min(x,y,511-x,511-y)
 if edge<3:return (221,164,72,255)
 if edge<7:return (58,116,122,255)
 grain=((x*11+y*17+(x^y)*3)%13)-6
 glow=max(0,18-int(((x-256)**2+(y-256)**2)**.5/13))
 return (19+grain//3,40+grain//2+glow//3,47+grain+glow,245)
def portrait(x,y):
 cell=(x//128)+(y//128)*4;lx=x%128;ly=y%128
 cultures=((196,151,112),(151,167,176),(123,92,145),(183,115,61),(83,112,128),(79,139,108),(126,116,105),(125,151,91))
 accent=cultures[cell%len(cultures)];female=(cell//8)==0
 vignette=max(0,35-int(((lx-64)**2+(ly-64)**2)**.5/2));base=(12+vignette//5,28+vignette//3,34+vignette//2,255)
 if (lx-64)**2+(ly-52)**2<(29 if female else 32)**2:
  shade=max(-22,min(20,(64-lx)//2));return tuple(max(0,min(255,c+shade)) for c in accent)+(255,)
 if 37<lx<91 and 79<ly<127:
  weave=((lx//5+ly//5+cell)%2)*8;return (35+weave,78+weave,84+weave,255)
 if 43<lx<85 and 20<ly<35:return (28,25,24,255)
 if (lx-53)**2+(ly-52)**2<5 or (lx-75)**2+(ly-52)**2<5:return (74,194,205,255)
 if abs(ly-69)<2 and 55<lx<73:return (93,48,43,255)
 return base

# Runtime HUD atlases.  The client addresses these textures with the original
# 256-pixel UV contract; generating a generic 512-pixel panel here made every
# action icon, the clock, and the compass sample empty filler.
ICON_KINDS={
 0:"walk",18:"walk",7:"sit",25:"sit",8:"stand",26:"stand",
 2:"look",20:"look",15:"use",35:"use",47:"item",46:"item",
 4:"trade",22:"trade",5:"attack",23:"attack",11:"inventory",29:"inventory",
 9:"spell",27:"spell",12:"craft",32:"craft",45:"emote",44:"emote",
 19:"quest",21:"quest",36:"map",37:"map",3:"info",6:"info",
 10:"friends",24:"friends",13:"stats",33:"stats",1:"console",28:"console",
 39:"help",38:"help",14:"settings",34:"settings"}

def _line(px,py,x1,y1,x2,y2,w=1):
 dx=x2-x1;dy=y2-y1;n=max(abs(dx),abs(dy),1)
 return min((px-(x1+dx*i/n))**2+(py-(y1+dy*i/n))**2 for i in range(n+1))<=w*w

def _icon_mark(kind,x,y):
 if kind=="walk": return ((x-13)**2+(y-18)**2<28 or (8<x<20 and 20<y<25))
 if kind=="sit": return (9<x<14 and 7<y<20) or (12<x<23 and 17<y<21) or _line(x,y,13,20,9,26,2)
 if kind=="stand": return (13<x<18 and 7<y<20) or _line(x,y,15,19,9,27,2) or _line(x,y,16,19,23,27,2)
 if kind=="look": return ((x-16)**2/100+(y-16)**2/36<1 and (x-16)**2/64+(y-16)**2/18>.65) or (x-16)**2+(y-16)**2<10
 if kind in ("use","item"): return (13<x<19 and 8<y<23) or (8<x<14 and 12<y<19) or (18<x<24 and 10<y<18)
 if kind=="trade": return _line(x,y,7,13,15,20,3) or _line(x,y,25,13,16,20,3)
 if kind=="attack": return _line(x,y,8,7,24,25,2) or _line(x,y,24,7,8,25,2)
 if kind=="inventory": return 8<x<24 and 12<y<25 and not (11<x<21 and 15<y<22)
 if kind=="spell": return 7<((x-16)**2+(y-16)**2)**.5<11 or _line(x,y,16,5,16,27,1) or _line(x,y,5,16,27,16,1)
 if kind=="craft": return _line(x,y,8,24,23,8,3) or (7<x<24 and 22<y<27)
 if kind=="emote": return (x-16)**2/90+(y-16)**2/110<1 and ((x-12)**2+(y-13)**2<2 or (x-20)**2+(y-13)**2<2 or (12<x<20 and 20<y<22))
 if kind=="quest": return 9<x<23 and 6<y<26 and not (12<x<20 and 9<y<23)
 if kind=="map": return _line(x,y,8,7,8,25,2) or _line(x,y,16,6,16,24,2) or _line(x,y,24,7,24,25,2) or _line(x,y,8,7,16,6,1) or _line(x,y,16,24,24,25,1)
 if kind=="info": return (x-16)**2+(y-10)**2<7 or (14<x<18 and 14<y<25)
 if kind=="friends": return (x-11)**2+(y-12)**2<20 or (x-21)**2+(y-12)**2<20 or (6<x<26 and 18<y<25)
 if kind=="stats": return (7<x<11 and 18<y<26) or (13<x<18 and 13<y<26) or (20<x<25 and 7<y<26)
 if kind=="console": return 6<x<26 and 7<y<23 and not (9<x<23 and 10<y<19) or _line(x,y,11,22,8,27,2)
 if kind=="help": return (7<((x-16)**2+(y-16)**2)**.5<11) and (y<20) or (14<x<18 and 22<y<26)
 if kind=="settings": return 7<((x-16)**2+(y-16)**2)**.5<11 or (x-16)**2+(y-16)**2<16
 return False

def gamebuttons_pixel(x,y):
 cell=(x//32)+(y//32)*8;lx=x%32;ly=y%32;kind=ICON_KINDS.get(cell)
 hi=cell in {18,25,26,20,35,46,22,23,29,27,32,44,21,37,6,24,33,28,38,34}
 border=lx in (1,2,29,30) or ly in (1,2,29,30)
 if border:return (198,132,55,255) if hi else (51,91,96,255)
 if _icon_mark(kind,lx,ly):return (111,231,240,255) if hi else (208,178,103,255)
 return (10,24,29,235) if 2<lx<29 and 2<ly<29 else (0,0,0,0)

def hud_pixel(x,y):
 # Compass and clock occupy exact legacy UV rectangles.
 if 32<=x<=95 and 193<=y<=255:
  dx=x-63.5;dy=y-224;d=(dx*dx+dy*dy)**.5
  if 27<d<31:return (199,137,70,255)
  if d<27 and (abs(dx)<1.3 or abs(dy)<1.3):return (91,181,185,255)
  if d<27:return (13,31,37,235)
 if 4<=x<=14 and 201<=y<=247:
  return (116,235,240,255) if abs(x-9)<=2 and y<241 else (0,0,0,0)
 if 0<=x<=63 and 128<=y<=191:
  dx=x-31.5;dy=y-159.5;d=(dx*dx+dy*dy)**.5
  if 27<d<31:return (199,137,70,255)
  if d<27 and (int((__import__('math').atan2(dy,dx)+3.2)*12/6.4)%3==0 and d>21):return (111,220,225,255)
  if d<27:return (13,31,37,235)
 if 21<=x<=31 and 193<=y<=223:return (235,185,82,255) if abs(x-26)<=2 else (0,0,0,0)
 if 64<=x<=127 and 128<=y<=191:
  dx=x-95.5;dy=y-159.5
  if dx*dx+dy*dy<720:return (101,211,218,255) if abs(dx)<6 or abs(dy)<6 else (18,46,53,245)
 if x>=192:return (26,39,42,245) if x<252 else (199,137,70,255)
 if 144<=x<=191:return (26,39,42,245) if y<252 else (199,137,70,255)
 return (0,0,0,0)
def write_text(path,text):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding="utf-8")
def e3d_fallback(path):
 # Use a generated native E3D box from the scenery tool when available.
 from generate_scenery import e3d,box
 def cube(v,i):box(v,i,(0,0,.5),(1,1,1))
 kind=path.stem
 def material(x,y):
  edge=x<3 or y<3 or x>28 or y>28
  if kind=="bag1":
   seam=abs(x-16)<2 or abs(y-16)<2;return (207,151,65,255) if seam or edge else (91+(x*y)%18,57,36,255)
  if kind=="portal1":
   ring=70<((x-16)**2+(y-16)**2)<130;return (216,158,66,255) if edge else (74,213,221,255) if ring else (18,45,57,235)
  cross=abs(x-y)<3 or abs(x+y-31)<3;return (238,174,69,255) if edge else (196,48,61,255) if cross else (33,42,46,255)
 texture=path.with_suffix('.png');e3d(path,texture.name,cube);png(texture,32,32,material)
def main():
 p=argparse.ArgumentParser();p.add_argument("output",nargs="?",default="build/eloria-data");root=Path(p.parse_args().output)
 bundled_font=Path(__file__).resolve().parents[1]/"fonts/EloriaSans-Regular.ttf"
 if not bundled_font.is_file():raise FileNotFoundError(f"Missing bundled font: {bundled_font}")
 fallback_font_pixel=ttf_font_pixels(bundled_font)
 for name in ("font","fontv","font2","font3","font5","font6","font7"):
  png(root/f"textures/{name}.png",256,256,fallback_font_pixel);bmp(root/f"textures/{name}.bmp",256,256,fallback_font_pixel)
  dds(root/f"textures/{name}.dds",256,256,fallback_font_pixel)
 (root/"fonts").mkdir(parents=True,exist_ok=True);shutil.copy2(bundled_font,root/"fonts/EloriaSans-Regular.ttf")
 for name in ("cursors","cursors2"):
  png(root/f"textures/{name}.png",CURSOR_COUNT*CURSOR_SIZE,CURSOR_SIZE,cursor_pixel)
  indexed_cursor_bmp(root/f"textures/{name}.bmp")
  validate_cursor_bmp(root/f"textures/{name}.bmp")
  dds(root/f"textures/{name}.dds",CURSOR_COUNT*CURSOR_SIZE,CURSOR_SIZE,cursor_pixel)
 for name in ("buttons","book1","paper1","alphaborder","eye_candy","eye_candy_burn"):
  png(root/f"textures/{name}.png",512,512,panel);bmp(root/f"textures/{name}.bmp",512,512,panel)
  dds(root/f"textures/{name}.dds",512,512,panel)
 # Keep the authored action art byte-for-byte identical to the reviewed atlas.
 # Reconstructing these cells procedurally produced readable but visibly
 # different placeholder glyphs.
 bundled_buttons=Path(__file__).resolve().parents[1]/"ui/gamebuttons.dds"
 if not bundled_buttons.is_file():raise FileNotFoundError(f"Missing authored HUD atlas: {bundled_buttons}")
 (root/"textures").mkdir(parents=True,exist_ok=True)
 shutil.copy2(bundled_buttons,root/"textures/gamebuttons.dds")
 bundled_hud=Path(__file__).resolve().parents[1]/"ui/gamebuttons2.dds"
 bundled_compass=Path(__file__).resolve().parents[1]/"ui/compass.dds"
 branding=Path(__file__).resolve().parents[1]/"ui/branding"
 bundled_login=branding/"eloria_login_background.dds"
 bundled_logo=branding/"eloria_logo_master.dds"
 bundled_crest=branding/"eloria_crest.dds"
 for source,name in ((bundled_hud,"gamebuttons2.dds"),(bundled_compass,"compass.dds"),
                     (bundled_login,"login_back.dds"),(bundled_logo,"eloria_logo.dds"),
                     (bundled_crest,"eloria_crest.dds")):
  if not source.is_file():raise FileNotFoundError(f"Missing authored HUD atlas: {source}")
  shutil.copy2(source,root/"textures"/name)
 dds(root/"textures/console.dds",512,512,console_panel)
 dds(root/"textures/ground_detail.dds",512,512,panel)
 authored=Path(__file__).resolve().parents[1]/"ui/generated"
 shutil.copy2(authored/"magic/sigils.dds",root/"textures/sigils.dds")
 dds(root/"textures/login_menu.dds",256,256,login_menu_pixel)
 # The minimap compass was installed with the authored HUD assets above.
 # Keep startup sky textures in the uncompressed BGRA DDS layout supported by
 # the legacy loader.  Modern DXT5 output corrupts its heap on Windows.
 for name,pixel in (("moonmap",moon),("BrightSun",sun),
                    ("thick_clouds",clouds),("thick_clouds_detail",clouds_detail)):
  dds(root/f"textures/{name}.dds",512,512,pixel)
 shutil.copy2(authored/"portraits/portraits1.dds",root/"textures/portraits1.dds")
 window_icon_master=Path(__file__).resolve().parents[2]/"elc.png"
 if not window_icon_master.is_file():raise FileNotFoundError(f"Missing Eloria window icon: {window_icon_master}")
 window_icon_bmp(window_icon_master,root/"icon.bmp")
 validate_window_icon_bmp(root/"icon.bmp")
 legend_target=root/"maps/legend.dds";legend_target.parent.mkdir(parents=True,exist_ok=True)
 shutil.copy2(authored/"maps/legend.dds",legend_target)
 e3d_fallback(root/"3dobjects/badobject.e3d");e3d_fallback(root/"3dobjects/bag1.e3d");e3d_fallback(root/"3dobjects/portal1.e3d")
 make_map(root/"maps/nomap.elm",placements=[])
 preview_map=root/"maps/newcharactermap.elm"
 # Present the actor on an original Eloria ground tile at z=0.  Keep scenery
 # outside the immediate camera/actor corridor so it provides context without
 # obscuring customization choices.
 preview_scenery=[
  ("3dobjects/scenery/lantern.e3d",14,72,0,0),
  ("3dobjects/scenery/lantern.e3d",29,72,0,0),
  ("3dobjects/scenery/alder_tree.e3d",9,87,0,20),
  ("3dobjects/scenery/highland_pine.e3d",34,88,0,-20),
  ("3dobjects/scenery/boulder.e3d",11,68,0,15),
  ("3dobjects/scenery/boulder.e3d",32,68,0,-15),
 ]
 make_map(preview_map,placements=preview_scenery,tile_id=0,height_value=11,
  ambient=(1.02,1.02,1.02),lights=[(21.5,78.0,3.0,4.0,4.0,4.0)])
 preview_data=preview_map.read_bytes()
 preview_width,preview_height,_,preview_height_offset=struct.unpack_from("<4i",preview_data,4)
 preview_x,preview_y=43,156
 if not (preview_x < preview_width*6 and preview_y < preview_height*6):
  raise ValueError("new-character preview coordinate lies outside generated map")
 preview_height_byte=preview_data[preview_height_offset+preview_y*preview_width*6+preview_x]
 if (preview_height_byte & 0x3F) != 11:
  raise ValueError("new-character preview camera datum must be height 11")
 preview_tile_offset=struct.unpack_from("<i",preview_data,12)[0]
 preview_tile=preview_data[preview_tile_offset+(preview_y//6)*preview_width+preview_x//6]
 if preview_tile != 0:
  raise ValueError("new-character preview must use visible Eloria terrain")
 stubs={"el.ini":"#language = en\n#use_ttf = 1\n#ui_font = EloriaSans-Regular.ttf\n#name_font = EloriaSans-Regular.ttf\n#chat_font = EloriaSans-Regular.ttf\n#note_font = EloriaSans-Regular.ttf\n#book_font = EloriaSans-Regular.ttf\n#rules_font = EloriaSans-Regular.ttf\n#encyclopedia_font = EloriaSans-Regular.ttf\n#def_ui_font = 20(EloriaSans-Regular.ttf)\n#def_name_font = 20(EloriaSans-Regular.ttf)\n#def_chat_font = 20(EloriaSans-Regular.ttf)\n#def_note_font = 20(EloriaSans-Regular.ttf)\n#def_book_font = 20(EloriaSans-Regular.ttf)\n#def_rules_font = 20(EloriaSans-Regular.ttf)\n#def_encyclopedia_font = 20(EloriaSans-Regular.ttf)\n","named_colours.xml":"<named_colours/>\n","mines.xml":"<mines/>\n","emotes.xml":"<emotes/>\n","spells.xml":"<spells/>\n","weather.xml":"<weather/>\n","knowledge.xml":"<Knowledge_Books/>\n","extentions.xml":"<extentions/>\n","commands.lst":"# Eloria commands\n","knowledge.lst":"# Eloria knowledge\n","servers.lst":"main main 127.0.0.1 2000\n","mapinfo.lst":"Nymara 0 0 512 512 ./maps/emberhaven.elm\n","continfo.lst":"Nymara maps/legend.dds\n"}
 for name,text in stubs.items():(root/name).write_text(text)
 write_text(root/"languages/langsel.xml",'<LANGUAGE_LIST><LANG CODE="en" TEXT="English" SAVE="1" DEFAULT="1"/></LANGUAGE_LIST>\n')
 write_text(root/"languages/en/knowledge.lst","")
 write_text(root/"skybox/skybox_defs.xml",'''<?xml version="1.0"?>
<skybox>
 <properties><clouds show="false"/><sun show="true"/><moons show="false"/><stars show="true"/></properties>
 <clouds reset="true"><color t="0" r="0.30" g="0.34" b="0.42"/></clouds>
 <clouds_detail reset="true"><color t="0" r="0.18" g="0.22" b="0.30"/></clouds_detail>
 <clouds_sunny reset="true"><color t="0" r="0.48" g="0.48" b="0.50"/></clouds_sunny>
 <clouds_detail_sunny reset="true"><color t="0" r="0.30" g="0.30" b="0.34"/></clouds_detail_sunny>
 <clouds_rainy reset="true"><color t="0" r="0.22" g="0.25" b="0.28"/></clouds_rainy>
 <clouds_detail_rainy reset="true"><color t="0" r="0.12" g="0.14" b="0.17"/></clouds_detail_rainy>
 <sky1 reset="true"><color t="0" r="0.04" g="0.07" b="0.16"/><color t="180" r="0.20" g="0.38" b="0.55"/></sky1>
 <sky2 reset="true"><color t="0" r="0.08" g="0.10" b="0.22"/><color t="180" r="0.34" g="0.27" b="0.42"/></sky2>
 <sky3 reset="true"><color t="0" r="0.10" g="0.13" b="0.25"/><color t="180" r="0.46" g="0.34" b="0.42"/></sky3>
 <sky4 reset="true"><color t="0" r="0.06" g="0.09" b="0.18"/><color t="180" r="0.24" g="0.34" b="0.44"/></sky4>
 <sky5 reset="true"><color t="0" r="0.03" g="0.05" b="0.12"/><color t="180" r="0.15" g="0.25" b="0.36"/></sky5>
 <sky1_sunny reset="true"><color t="0" r="0.10" g="0.12" b="0.20"/><color t="180" r="0.48" g="0.50" b="0.58"/></sky1_sunny>
 <sky2_sunny reset="true"><color t="0" r="0.12" g="0.15" b="0.25"/><color t="180" r="0.54" g="0.48" b="0.58"/></sky2_sunny>
 <sky3_sunny reset="true"><color t="0" r="0.14" g="0.18" b="0.30"/><color t="180" r="0.62" g="0.52" b="0.56"/></sky3_sunny>
 <sky4_sunny reset="true"><color t="0" r="0.10" g="0.14" b="0.24"/><color t="180" r="0.48" g="0.52" b="0.62"/></sky4_sunny>
 <sky5_sunny reset="true"><color t="0" r="0.06" g="0.09" b="0.18"/><color t="180" r="0.36" g="0.44" b="0.56"/></sky5_sunny>
 <sun reset="true"><color t="0" r="0.95" g="0.68" b="0.35"/><color t="180" r="1.0" g="0.88" b="0.62"/></sun>
 <fog reset="true"><color t="0" r="0.04" g="0.07" b="0.12" a="0.01"/><color t="180" r="0.20" g="0.28" b="0.34" a="0.005"/></fog>
 <fog_sunny reset="true"><color t="0" r="0.08" g="0.10" b="0.16" a="0.01"/><color t="180" r="0.42" g="0.44" b="0.50" a="0.005"/></fog_sunny>
 <fog_rainy reset="true"><color t="0" r="0.05" g="0.07" b="0.10" a="0.02"/><color t="180" r="0.22" g="0.25" b="0.28" a="0.015"/></fog_rainy>
 <light_ambient reset="true"><color t="0" r="0.16" g="0.18" b="0.28"/><color t="180" r="0.54" g="0.55" b="0.62"/></light_ambient>
 <light_diffuse reset="true"><color t="0" r="0.22" g="0.24" b="0.35"/><color t="180" r="0.85" g="0.78" b="0.68"/></light_diffuse>
 <light_ambient_rainy reset="true"><color t="0" r="0.12" g="0.14" b="0.20"/><color t="180" r="0.38" g="0.40" b="0.46"/></light_ambient_rainy>
 <light_diffuse_rainy reset="true"><color t="0" r="0.16" g="0.18" b="0.24"/><color t="180" r="0.58" g="0.56" b="0.52"/></light_diffuse_rainy>
</skybox>
''')
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
 <info><short>Testing notice</short><long>Rules may evolve during testing. Material changes will be announced with the server release notes.</long></info>
</rules>\n''')
 for name in ("console","errors","help","options","spells","stats","titles"):
  write_text(root/f"languages/en/strings/{name}.xml","<root/>\n")
 write_text(root/"languages/en/strings/channels.xml",'''<CHANNELS>
 <label index="0" name="Channel %d">Joined channel %d</label>
 <label index="1" name="Guild">Your guild's chat channel.</label>
 <label index="2" name="All">Display chat from all active channels.</label>
 <label index="3" name="None">Messages not associated with a channel.</label>
 <label index="4" name="Options">Select and configure chat channels.</label>
 <label index="5" name="History">Review earlier chat messages.</label>
 <label index="6" name="Local">Chat with players in your local area.</label>
 <label index="7" name="PMs">Private messages.</label>
 <label index="8" name="Guild Messages">Guild-wide messages.</label>
 <label index="9" name="Server">Messages from the Nymara server.</label>
 <label index="10" name="Moderation">Moderator chat.</label>
 <channel number="1" name="Noob">New-player questions, guidance, and introductions.</channel>
 <channel number="2" name="General">Nymara-wide conversation and community discussion.</channel>
 <channel number="3" name="Market">Trading, services, price checks, and crafting requests.</channel>
 <channel number="4" name="Invasions">Invasion sightings, warnings, and defensive coordination.</channel>
</CHANNELS>\n''')
 races={"human":("Luminari","Lantern-city stewards who preserve memory in crystal and song."),"elf":("Votari","Mistwood wayfinders bound to living paths and ancient promises."),"dwarf":("Glasswardens","Forge-clans who shape star-glass beneath Nymara's ridges."),"gnome":("Orun","Ingenious tidefolk who build compact wonders from shell and brass."),"orchan":("Greyhaven","Storm-tested frontier clans known for endurance and mutual oath."),"draegoni":("Ssarathi","Scaled heirs of the ember marshes, attuned to heat and old magic.")}
 for filename,(title,description) in races.items():
  write_text(root/f"languages/en/books/races/{filename}.xml",f'<book title="{title}"><title>{title}</title><nl/><text>{description}</text><nl/><text>Choose this culture to begin your story in Nymara.</text></book>\n')
 write_text(root/"languages/en/Encyclopedia/index.xml","<Encyclopedia><Category>Basics</Category></Encyclopedia>\n")
 write_text(root/"languages/en/Encyclopedia/Basics.xml",'''<Encyclopedia>
 <Page name="index"><Size>Big</Size><Text>Welcome to Eloria</Text><nl/><Size>Small</Size><Text>An original world on the continent of Nymara.</Text></Page>
 <Page name="HelpPage"><Size>Big</Size><Text>Getting Started</Text><nl/><Size>Small</Size><Text>Explore Emberhaven, speak with its residents, gather resources, and craft your first supplies.</Text></Page>
 <Page name="newskills"><Size>Big</Size><Text>Skills</Text><nl/><Size>Small</Size><Text>Skills improve through use. The testing build emphasizes gathering, crafting, combat, and magic.</Text></Page>
</Encyclopedia>\n''')
if __name__=="__main__":main()

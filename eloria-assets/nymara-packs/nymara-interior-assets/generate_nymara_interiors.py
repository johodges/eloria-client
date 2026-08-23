#!/usr/bin/env python3
"""Generate native Nymara interior modules from the approved concept families."""
from pathlib import Path
import json
import generate_nymara_pack as base

ROOT=Path(__file__).resolve().parent/'nymara-interior-assets'

def floor(v,i): base.box(v,i,(0,0,.1),(6,6,.2))
def wall_plain(v,i): base.box(v,i,(0,0,1.5),(6,.3,3))
def wall_window(v,i):
    base.box(v,i,(-2,0,1.5),(2,.3,3));base.box(v,i,(2,0,1.5),(2,.3,3));base.box(v,i,(0,0,.35),(2,.3,.7));base.box(v,i,(0,0,2.65),(2,.3,.7))
def arch(v,i): base.box(v,i,(-1.7,0,1.6),(.8,.6,3.2));base.box(v,i,(1.7,0,1.6),(.8,.6,3.2));base.taper(v,i,2.4,3.8,2.1,1.65,10)
def column(v,i): base.taper(v,i,0,3,.34,.28,10);base.taper(v,i,0,.25,.55,.48,10);base.taper(v,i,2.75,3,.48,.55,10)
def door(v,i): base.box(v,i,(0,0,1.35),(1.7,.22,2.7));base.taper(v,i,2.7,3.25,1.0,0,8)
def table(v,i):
    base.box(v,i,(0,0,1.05),(3,1.5,.18))
    for x in (-1.25,1.25):
        for y in (-.55,.55): base.box(v,i,(x,y,.52),(.18,.18,1.05))
def chair(v,i): base.box(v,i,(0,0,.65),(1,1,.15));base.box(v,i,(0,.43,1.3),(1,.15,1.4));base.box(v,i,(-.38,-.35,.3),(.12,.12,.6));base.box(v,i,(.38,-.35,.3),(.12,.12,.6))
def shelf(v,i):
    for z in (.2,1.2,2.2,3.2): base.box(v,i,(0,0,z),(3,.65,.16))
    for x in (-1.4,1.4): base.box(v,i,(x,0,1.7),(.16,.65,3.4))
def bed(v,i): base.box(v,i,(0,0,.55),(2.2,3.8,.55));base.box(v,i,(0,1.6,1.2),(2.2,.3,1.8))
def counter(v,i): base.box(v,i,(0,0,.75),(4,1.1,1.5));base.box(v,i,(0,0,1.55),(4.3,1.3,.16))
def brazier(v,i): base.taper(v,i,.7,1.25,.65,.85,10);base.taper(v,i,0,.75,.16,.12,8);base.taper(v,i,1.2,2,.6,0,8)
def altar(v,i): base.box(v,i,(0,0,.65),(3,1.8,1.3));base.taper(v,i,1.3,2.8,.5,0,8)
def bookcase(v,i): shelf(v,i)
def barrel(v,i): base.taper(v,i,0,1.4,.55,.48,12);base.taper(v,i,.45,.95,.58,.58,12)
def crate_stack(v,i): base.box(v,i,(-.6,0,.55),(1.1,1.1,1.1));base.box(v,i,(.6,.1,.55),(1.1,1.1,1.1));base.box(v,i,(0,0,1.65),(1.1,1.1,1.1))
def lab(v,i): table(v,i);base.taper(v,i,1.15,2.1,.35,.18,10,(-.7,0));base.taper(v,i,1.15,2.35,.28,.08,10,(.55,.1))
def lens(v,i): base.taper(v,i,0,2.6,.16,.12,8);base.taper(v,i,2.1,3.3,1.1,.2,12)
def mine_support(v,i): base.box(v,i,(-1.7,0,1.6),(.35,.5,3.2));base.box(v,i,(1.7,0,1.6),(.35,.5,3.2));base.box(v,i,(0,0,3.05),(3.7,.5,.35))
def tomb(v,i): base.box(v,i,(0,0,.55),(3.2,1.7,1.1));base.taper(v,i,1.1,1.65,1.7,.6,8)
def sarcophagus(v,i): tomb(v,i)
def water_channel(v,i): base.box(v,i,(0,0,.18),(6,2.2,.36));base.box(v,i,(0,0,.38),(5.4,1.5,.12))
def hatchery(v,i): base.ritual_pool(v,i);base.taper(v,i,.5,1.1,.45,0,10,(-1,0));base.taper(v,i,.5,1.1,.45,0,10,(1,0))
def trap(v,i):
    for x in (-1.5,-.75,0,.75,1.5): base.taper(v,i,0,1.2,.16,0,5,(x,0))
def statue(v,i): base.box(v,i,(0,0,.25),(1.5,1.5,.5));base.taper(v,i,.5,2.4,.45,.3,10);base.taper(v,i,2.4,3.1,.52,.25,10)
def tent_interior(v,i): base.taper(v,i,0,3,3,0,8);base.floor(v,i) if hasattr(base,'floor') else base.box(v,i,(0,0,.08),(5,5,.16))

KITS={
 'mirrorhold':(('pale_floor',floor),('canal_wall',wall_plain),('arched_wall',arch),('window_wall',wall_window),('civic_column',column),('turquoise_door',door),('council_table',table),('civic_chair',chair)),
 'crownwater':(('drowned_floor',floor),('underwater_wall',wall_plain),('submerged_arch',arch),('water_channel',water_channel),('drowned_statue',statue),('shell_altar',altar)),
 'maritime':(('warehouse_floor',floor),('warehouse_wall',wall_plain),('cargo_shelf',shelf),('merchant_counter',counter),('barrel_stack',barrel),('cargo_crates',crate_stack)),
 'orun':(('felt_floor',floor),('tent_shell',tent_interior),('low_table',table),('camp_chair',chair),('portable_altar',altar),('supply_crates',crate_stack)),
 'whitehorn':(('monastery_floor',floor),('monastery_wall',wall_plain),('ice_arch',arch),('prayer_column',column),('mine_support',mine_support),('glacier_altar',altar)),
 'glasswarden':(('laboratory_floor',floor),('brass_wall',wall_window),('experiment_table',lab),('observatory_lens',lens),('crystal_brazier',brazier),('archive_shelf',bookcase)),
 'amberwood':(('manor_floor',floor),('manor_wall',wall_window),('estate_door',door),('estate_bed',bed),('banquet_table',table),('overgrown_statue',statue)),
 'grey_moor':(('crypt_floor',floor),('crypt_wall',wall_plain),('barrow_arch',arch),('sarcophagus',sarcophagus),('ritual_altar',altar),('spike_trap',trap)),
 'verdant':(('cenote_floor',floor),('root_wall',wall_plain),('jungle_arch',arch),('ritual_pool',water_channel),('vine_altar',altar),('root_statue',statue)),
 'ssarathi':(('scaled_floor',floor),('curved_wall',wall_window),('water_arch',arch),('hatchery_pool',hatchery),('archive_shelf',bookcase),('royal_statue',statue),('water_door',door),('vault_trap',trap)),
 'manymouth':(('flooded_floor',floor),('stilt_wall',wall_window),('boardwalk_section',base.boardwalk),('smuggler_shelf',shelf),('fishing_crates',crate_stack),('flood_channel',water_channel))}

PALE=((202,211,205),(49,126,134)); COLORS={'mirrorhold':PALE,'crownwater':((80,125,126),(42,154,155)),'maritime':((111,79,51),(55,106,120)),'orun':((170,108,53),(47,132,133)),'whitehorn':((150,178,184),(213,231,233)),'glasswarden':((108,88,118),(181,112,200)),'amberwood':((112,76,48),(181,99,41)),'grey_moor':((75,79,76),(121,126,118)),'verdant':((66,112,79),(46,142,103)),'ssarathi':((72,113,103),(40,148,132)),'manymouth':((92,69,45),(54,126,99))}

def main():
    runtime=ROOT/'runtime';source=ROOT/'source-obj';entries=[]
    for kit,assets in KITS.items():
        a,b=COLORS[kit]
        for short,builder in assets:
            name=f'{kit}_{short}';tex=runtime/'3dobjects/nymara/interiors'/f'{name}.png'
            base.tex(tex,a,b);base.e3d(runtime/'3dobjects/nymara/interiors'/f'{name}.e3d',tex.name,builder);base.obj(source/f'{name}.obj',builder,name,tex.name)
            # Correct OBJ texture path for the extra interiors directory depth.
            (source/f'{name}.mtl').write_text(f'newmtl {name}\nKd 1 1 1\nmap_Kd ../runtime/3dobjects/nymara/interiors/{tex.name}\n')
            entries.append({'id':name,'kit':kit,'model':f'3dobjects/nymara/interiors/{name}.e3d','texture':f'3dobjects/nymara/interiors/{name}.png','source':f'source-obj/{name}.obj'})
    (runtime/'nymara_interiors.json').write_text(json.dumps({'schema':1,'modules':entries,'landmark_dungeons':['drowned_crown','whitehorn_glacier_temple','resonant_vault','amberwood_estate','grey_moor_barrows','ssarathi_royal_archive','manymouth_flooded_labyrinth']},indent=2)+'\n')
    (ROOT/'provenance.json').write_text(json.dumps({'schema':1,'assets':[{'path':'runtime/3dobjects/nymara/interiors/*','source':'generate_nymara_interiors.py','author':'Eloria project','license':'CC-BY-4.0','description':'Original procedural Nymara modular interiors'}]},indent=2)+'\n')
    (ROOT/'README.md').write_text(f'''# Nymara interior asset pack\n\n{len(entries)} native E3D modules across {len(KITS)} reusable interior kits, with PNG textures and editable OBJ/MTL sources. Copy `runtime/` over the generated Eloria data directory. Use `nymara_interiors.json` for stable paths and kit membership. Modules cover the seven approved landmark dungeons as reusable construction pieces; finished ELM room layouts remain map-authoring work.\n''')
    (ROOT/'generate_nymara_interiors.py').write_text(Path(__file__).read_text())
    print(f'generated {len(entries)} native interior modules')
if __name__=='__main__': main()

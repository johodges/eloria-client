#!/usr/bin/env python3
"""Generate the original Nymara actors, creatures, equipment, effects and maps.

All geometry and pixels are deterministic procedural production proxies.  No
Eternal Lands binary-data input is read or required.
"""
from __future__ import annotations
import argparse, json, math, shutil, struct, zlib
from pathlib import Path
import xml.etree.ElementTree as ET

from generate_bootstrap_pack import png, make_map
from generate_characters import skeleton as humanoid_skeleton
from generate_humanoid_enemies import enemy_mesh, material_pixel
from generate_creatures import skeleton as creature_skeleton, creature_mesh, creature_material
from generate_scenery import e3d, texture, box, tapered, crossed_leaves

NPC_BASE, CREATURE_BASE, ITEM_BASE = 300, 400, 1000

CULTURES = {
 "luminous": ((77,155,162), (213,205,168), ["official","guard","merchant","ferryman","scholar","lake_priest","civilian"]),
 "votary": ((139,173,188), (210,218,215), ["monk","mountaineer","miner","glacier_guardian"]),
 "glasswarden": ((121,91,158), (185,137,67), ["engineer","astronomer","researcher","guard"]),
 "orun": ((172,99,47), (54,137,142), ["rider","scout","elder","camp_resident","mounted_warden"]),
 "greyhaven": ((62,86,101), (157,135,91), ["sailor","fisher","shipwright","merchant","militia","councilor"]),
 "ssarathi": ((52,116,91), (181,153,76), ["civilian","priest","archivist","warrior","sun_ceremonial"]),
}

CREATURES = [
 ("crownwater","mirrorfin_otter","Mirrorfin Otter",(.62,1.10,.52),(.38,.42,.34),"whiskers"),
 ("crownwater","reedhorn_stag","Reedhorn Stag",(.90,1.52,.90),(.48,.54,.48),"antlers"),
 ("crownwater","gate_turtle","Four Gates Turtle",(1.12,1.28,.54),(.48,.42,.30),"shell"),
 ("crownwater","lakeglass_drake","Lakeglass Drake",(.96,1.60,.75),(.55,.60,.48),"wings"),
 ("whitehorn","snowcrest_hare","Snowcrest Hare",(.55,.84,.48),(.36,.36,.34),"long_ears"),
 ("whitehorn","glacier_ram","Glacier Ram",(.90,1.32,.82),(.52,.52,.46),"great_horns"),
 ("whitehorn","iceback_ursid","Iceback Ursid",(1.18,1.48,.96),(.68,.60,.62),"ice_spikes"),
 ("whitehorn","rimeclaw","Rimeclaw",(.92,1.45,.78),(.55,.60,.50),"saber_fangs"),
 ("amethyst","crystal_mite","Crystal Mite",(1.10,1.05,.42),(.55,.42,.34),"spikes"),
 ("amethyst","resonant_hound","Resonant Hound",(.88,1.43,.72),(.52,.56,.47),"back_ridge"),
 ("amethyst","stormglass_grazer","Stormglass Grazer",(.88,1.48,.84),(.48,.52,.44),"horns"),
 ("amethyst","prism_wyrm","Prism Wyrm",(.78,1.74,.68),(.44,.64,.42),"wings"),
 ("sunmane","dunrunner","Dunrunner",(.76,1.38,.76),(.45,.48,.43),"tufted_ears"),
 ("sunmane","steppe_aurochs","Steppe Aurochs",(1.20,1.70,.98),(.66,.62,.58),"great_horns"),
 ("sunmane","sunmane_cat","Sunmane Cat",(.84,1.42,.68),(.47,.55,.43),"saber_fangs"),
 ("sunmane","dustscale_drake","Dustscale Drake",(.98,1.72,.76),(.56,.64,.48),"wings"),
 ("ambergrey","amberhart","Amberhart",(.90,1.52,.90),(.48,.54,.46),"broad_antlers"),
 ("ambergrey","rootback_boar","Rootback Boar",(1.02,1.44,.72),(.60,.56,.50),"tusks"),
 ("ambergrey","moor_wisp_hound","Moor Wisp Hound",(.86,1.42,.70),(.50,.55,.46),"twin_tail"),
 ("ambergrey","barrow_quillbeast","Barrow Quillbeast",(1.10,1.48,.82),(.62,.58,.54),"quills"),
 ("verdant","canopy_glider","Canopy Glider",(.74,1.18,.55),(.42,.48,.38),"wings"),
 ("verdant","cenote_toader","Cenote Toader",(1.12,1.02,.46),(.62,.46,.36),"eyes"),
 ("verdant","scalevine_stalker","Scalevine Stalker",(.88,1.45,.72),(.50,.56,.46),"back_ridge"),
 ("verdant","sunscale_basilisk","Sunscale Basilisk",(1.04,1.72,.74),(.56,.62,.48),"nose_horn"),
 ("manymouth","mangrove_crab","Mangrove Crab",(1.18,1.10,.40),(.58,.44,.34),"spikes"),
 ("manymouth","mudskipper_beast","Mudskipper Beast",(.98,1.30,.52),(.54,.48,.38),"eyes"),
 ("manymouth","delta_crocodile","Delta Crocodile",(1.12,1.92,.58),(.58,.70,.42),"back_ridge"),
 ("manymouth","floodmaw","Floodmaw",(1.22,1.72,.92),(.68,.66,.60),"fangs"),
]

EQUIPMENT = []
for culture, names in {
 "luminous":["civic_blade","lakeguard_spear","mirror_shield","ceremonial_mail","civic_mantle","ferry_hook"],
 "votary":["ice_pick","glacier_staff","rime_shield","votary_mail","snow_mantle","silver_charm"],
 "glasswarden":["crystal_sabre","brass_hammer","lens_focus","prism_armor","observer_mantle","astrolabe"],
 "orun":["rider_sabre","steppe_bow","hide_shield","riding_leathers","wind_mantle","horse_tack"],
 "greyhaven":["naval_cutlass","boarding_pike","tide_shield","harbor_mail","storm_cape","shipwright_adze"],
 "ssarathi":["curved_blade","sun_spear","scale_shield","channel_armor","ritual_mantle","water_focus"],
}.items():
 for name in names: EQUIPMENT.append((culture,name))

REGIONS = ["mirrorhold","crownwater","four_gates","whitehorn_range","amethyst_barrens","sunmane_steppe","amberwood","grey_moors","westhaven","verdant_stair","ssarathi_ruins","manymouth_delta"]
DUNGEONS = ["drowned_crown","whitehorn_glacier_temple","resonant_vault","amberwood_estate","grey_moor_barrows","ssarathi_royal_archive","manymouth_flooded_labyrinth"]

REGION_HARVESTS = {
 "mirrorhold":["mirror_reed","crownwater_pearl","deep_lake_clay","delta_lotus"],
 "crownwater":["crownwater_pearl","mirror_reed","deep_lake_clay","glacier_salt"],
 "four_gates":["resonant_crystal","stormglass_shard","mirror_reed","sunmane_seed"],
 "whitehorn_range":["glacier_salt","whitehorn_silverleaf","resonant_crystal","stormglass_shard"],
 "amethyst_barrens":["resonant_crystal","stormglass_shard","voltaic_geode","deep_lake_clay"],
 "sunmane_steppe":["sunmane_seed","amber_resin","voltaic_geode","stormglass_shard"],
 "amberwood":["amber_resin","ghost_orchid","moor_peat","sunmane_seed"],
 "grey_moors":["moor_peat","ghost_orchid","amber_resin","mangrove_sap"],
 "westhaven":["mangrove_sap","moor_peat","deep_lake_clay","delta_lotus"],
 "verdant_stair":["verdant_venom_bulb","ghost_orchid","ssarathi_scale_moss","delta_lotus"],
 "ssarathi_ruins":["ssarathi_scale_moss","verdant_venom_bulb","delta_lotus","voltaic_geode"],
 "manymouth_delta":["delta_lotus","mangrove_sap","deep_lake_clay","crownwater_pearl"],
}

REGION_ART = {
 "mirrorhold":{"palette":((47,70,73),(92,111,104),(174,151,92)),"objects":["glasswarden_observatory","glasswarden_lens_tower","glasswarden_field_station","mirrorhold_civic_tower","mirrorhold_canal_wall","mirrorhold_radial_bridge","mirrorhold_public_fountain"],"water":True,"ambient":(.48,.55,.60)},
 "crownwater":{"palette":((36,125,145),(221,217,180),(42,87,91)),"objects":["crownwater_ferry_dock","crownwater_fishing_boat","crownwater_patrol_boat","crownwater_submerged_waystone","mirrorhold_radial_bridge","mirrorhold_public_fountain"],"water":True,"ambient":(.62,.68,.70)},
 "four_gates":{"palette":((75,104,78),(172,162,126),(53,112,119)),"objects":["four_gates_gatehouse","four_gates_waystone","mirrorhold_radial_bridge","mirrorhold_civic_tower","mirrorhold_public_fountain","glasswarden_field_station"],"water":True,"ambient":(.58,.61,.58)},
 "whitehorn_range":{"palette":((183,211,219),(65,78,83),(222,229,221)),"objects":["whitehorn_glacier","whitehorn_monastery","whitehorn_rope_bridge","whitehorn_shrine","whitehorn_cairn","whitehorn_ice_cave","whitehorn_mine_entrance"],"water":False,"ambient":(.67,.72,.76)},
 "amethyst_barrens":{"palette":((110,72,139),(184,132,194),(122,99,65)),"objects":["glasswarden_observatory","amethyst_crystal_bridge","amethyst_geode_cave","amethyst_levitating_shards","amethyst_storm_ruin","resonant_crystal_cluster"],"water":False,"ambient":(.54,.49,.62)},
 "sunmane_steppe":{"palette":((171,126,56),(208,177,101),(130,70,38)),"objects":["orun_round_tent","orun_seasonal_market","orun_banner_shrine","sunmane_caravanserai","sunmane_windmill","sunmane_well","sunmane_animal_pen","sunmane_burial_mound"],"water":False,"ambient":(.68,.61,.48)},
 "amberwood":{"palette":((119,72,35),(190,109,39),(65,91,55)),"objects":["amberwood_estate","amberwood_hunting_lodge","amberwood_hollow_tree","amberwood_old_bridge","amberwood_tree","amberwood_ruin_arch","amberwood_garden_fountain"],"water":False,"ambient":(.55,.48,.38)},
 "grey_moors":{"palette":((72,77,68),(105,83,108),(48,57,55)),"objects":["grey_moor_barrow","grey_moor_standing_stones","grey_moor_boardwalk","grey_moor_crypt_entrance","grey_moor_abandoned_cottage","grey_moor_dead_tree","grey_moor_ritual_shrine"],"water":True,"ambient":(.43,.46,.48)},
 "westhaven":{"palette":((40,94,111),(130,84,55),(87,91,89)),"objects":["westhaven_lighthouse","westhaven_warehouse","westhaven_dry_dock","westhaven_harbor_crane","westhaven_shipyard_frame","westhaven_fish_market","westhaven_seawall"],"water":True,"ambient":(.52,.57,.60)},
 "verdant_stair":{"palette":((42,105,66),(91,145,85),(44,92,101)),"objects":["verdant_basalt_steps","verdant_cenote_stairs","verdant_root_bridge","verdant_vine_bridge","verdant_tree_platform","verdant_water_shrine","verdant_giant_fern"],"water":True,"ambient":(.48,.60,.50)},
 "ssarathi_ruins":{"palette":((42,91,68),(151,126,57),(38,111,108)),"objects":["ssarathi_temple","ssarathi_vault_entrance","ssarathi_water_gate","ssarathi_sunken_court","ssarathi_ritual_pool","ssarathi_sun_stela","ssarathi_ruin_arch"],"water":True,"ambient":(.47,.57,.48)},
 "manymouth_delta":{"palette":((36,105,91),(117,112,56),(42,71,58)),"objects":["manymouth_stilt_house","manymouth_boardwalk","manymouth_ferry_dock","manymouth_hidden_dock","manymouth_mangrove","manymouth_market_stall","manymouth_flooded_cave"],"water":True,"ambient":(.48,.57,.52)},
}

INTERIOR_KITS = {
 "drowned_crown":["crownwater_drowned_floor","crownwater_underwater_wall","crownwater_submerged_arch","crownwater_shell_altar","crownwater_drowned_statue","crownwater_water_channel"],
 "whitehorn_glacier_temple":["whitehorn_monastery_floor","whitehorn_monastery_wall","whitehorn_ice_arch","whitehorn_glacier_altar","whitehorn_prayer_column","whitehorn_mine_support"],
 "resonant_vault":["glasswarden_laboratory_floor","glasswarden_brass_wall","glasswarden_archive_shelf","glasswarden_crystal_brazier","glasswarden_experiment_table","glasswarden_observatory_lens"],
 "amberwood_estate":["amberwood_manor_floor","amberwood_manor_wall","amberwood_estate_door","amberwood_banquet_table","amberwood_estate_bed","amberwood_overgrown_statue"],
 "grey_moor_barrows":["grey_moor_crypt_floor","grey_moor_crypt_wall","grey_moor_barrow_arch","grey_moor_ritual_altar","grey_moor_sarcophagus","grey_moor_spike_trap"],
 "ssarathi_royal_archive":["ssarathi_scaled_floor","ssarathi_curved_wall","ssarathi_water_arch","ssarathi_archive_shelf","ssarathi_royal_statue","ssarathi_vault_trap"],
 "manymouth_flooded_labyrinth":["manymouth_flooded_floor","manymouth_stilt_wall","manymouth_boardwalk_section","manymouth_flood_channel","manymouth_smuggler_shelf","manymouth_fishing_crates"],
}

def dds_mipped(path, width, height, pixel, levels=4):
 path.parent.mkdir(parents=True,exist_ok=True)
 header=[124,0x0002100F,width and height,width,width*4,0,levels]+[0]*11+[32,0x41,0,32,0x00FF0000,0x0000FF00,0x000000FF,0xFF000000]+[0x401008,0,0,0,0]
 header[2]=height
 payload=bytearray()
 for level in range(levels):
  w=max(1,width>>level); h=max(1,height>>level); scale=1<<level
  for y in range(h):
   for x in range(w):
    r,g,b,a=pixel(min(width-1,x*scale),min(height-1,y*scale)); payload.extend((b,g,r,a))
 path.write_bytes(b'DDS '+struct.pack('<31I',*header)+payload)

def png_pixels(path):
 data=path.read_bytes()
 if data[:8] != b'\x89PNG\r\n\x1a\n': raise ValueError(f"invalid concept PNG: {path}")
 pos=8; compressed=bytearray(); width=height=depth=color=None
 while pos < len(data):
  size=struct.unpack_from('>I',data,pos)[0]; kind=data[pos+4:pos+8]; chunk=data[pos+8:pos+8+size]; pos+=12+size
  if kind==b'IHDR': width,height,depth,color,_,_,_=struct.unpack('>IIBBBBB',chunk)
  elif kind==b'IDAT': compressed.extend(chunk)
  elif kind==b'IEND': break
 if depth!=8 or color not in (2,6): raise ValueError(f"unsupported concept PNG layout: {path}")
 channels=3 if color==2 else 4; stride=width*channels; raw=zlib.decompress(bytes(compressed)); rows=[]; prior=bytearray(stride); cursor=0
 for _ in range(height):
  mode=raw[cursor]; cursor+=1; scan=bytearray(raw[cursor:cursor+stride]); cursor+=stride
  for i in range(stride):
   left=scan[i-channels] if i>=channels else 0; up=prior[i]; upper_left=prior[i-channels] if i>=channels else 0
   if mode==1: scan[i]=(scan[i]+left)&255
   elif mode==2: scan[i]=(scan[i]+up)&255
   elif mode==3: scan[i]=(scan[i]+((left+up)//2))&255
   elif mode==4:
    p=left+up-upper_left; pa=abs(p-left); pb=abs(p-up); pc=abs(p-upper_left)
    scan[i]=(scan[i]+(left if pa<=pb and pa<=pc else up if pb<=pc else upper_left))&255
   elif mode!=0: raise ValueError(f"unsupported PNG filter {mode}: {path}")
  rows.append(bytes(scan)); prior=scan
 def sample(x,y):
  i=x*channels; row=rows[y]
  return (row[i],row[i+1],row[i+2],row[i+3] if channels==4 else 255)
 return width,height,sample

def concept_dds(source, target):
 width,height,sample=png_pixels(source); side=min(width,height); ox=(width-side)//2; oy=(height-side)//2
 dds_mipped(target,512,512,lambda x,y:sample(ox+x*side//512,oy+y*side//512))

def region_noise(name, x, y):
 seed=sum((i+1)*ord(c) for i,c in enumerate(name))
 return ((x*37+y*61+seed+(x*y*13))%29)-14

def region_tile(profile, name, x, y):
 cx,cy=15.5,15.5; radial=math.hypot(x-cx,y-cy)
 road=(abs(y-16)<=1 or abs(x-16)<=1 or abs(y-x)<=1)
 water=profile['water'] and (radial>14 or (name in ('crownwater','manymouth_delta') and ((x*3+y*5)%17)<4))
 return 3 if water else 2 if road else 1 if radial>12 else 0

def region_height(profile, name, x, y):
 # Height byte low six bits are the signed map datum plus 11. Keep arrivals and
 # portal corridors at z=0 while sculpting distant terrain in broad terraces.
 if abs(x-58)<=8 and abs(y-58)<=8: return 11
 if abs(y-58)<=3 or abs(x-58)<=3: return 11
 edge=min(x,y,191-x,191-y)
 ridge=max(0,(35-edge)//7)
 if name in ('whitehorn_range','mirrorhold'): ridge+=int(max(0,y-105)/18)
 elif name in ('verdant_stair','ssarathi_ruins'): ridge+=((x//24+y//24)%3)
 elif name in ('crownwater','manymouth_delta'): ridge=max(0,ridge-2)
 return max(6,min(28,11+ridge+region_noise(name,x//6,y//6)//9))

def four_gates_tile(x,y):
 # Four Gates is composed around the protected start plaza at actor (58,58),
 # not the geometric centre of the 192x192 collision field.  The inner city
 # occupies a fortified island with four dry causeways crossing its river.
 cx=cy=58/6; radius=math.hypot(x-cx,y-cy)
 causeway=abs(x-cx)<=1.0 or abs(y-cy)<=1.0
 ring_road=3.6<=radius<=4.7
 if 7.0<radius<10.2 and not causeway: return 7
 if causeway or ring_road: return 6
 return 4 if radius<7.0 else 5

def four_gates_height(x,y):
 # Keep the civic island, gates, portals and radial roads at the shared z=0
 # datum.  Distant uplands rise in broad, walkable terraces.
 radius=math.hypot(x-58,y-58)
 if radius<=52 or abs(x-58)<=4 or abs(y-58)<=4: return 11
 return max(11,min(19,11+int((radius-52)//18)+region_noise('four_gates',x//8,y//8)//10))

def mirrorhold_tile(x,y):
 cx=58/6; lake_y=91/6
 lake=math.hypot(x-cx,(y-lake_y)*1.18)<4.8 or (7<x<12 and 11<y<19)
 road=abs(x-cx)<=.7 or abs(y-cx)<=.7 or abs(x-y-2.7)<=.7 or abs(x+y-22)<=.7
 citadel=math.hypot(x-cx,y-6)<3.7
 return 3 if lake else 2 if road else 0 if citadel else 1

def mirrorhold_height(x,y):
 if abs(x-58)<=3 or abs(y-58)<=3: return 11
 lake=math.hypot(x-58,(y-91)*1.18)<28
 if lake: return 6
 citadel=max(0,24-int(math.hypot(x-58,y-36)))
 ridge=max(0,(18-min(x,y,191-x,191-y))//4)
 return max(8,min(29,11+citadel//3+ridge+region_noise('mirrorhold',x//7,y//7)//8))

def crownwater_tile(x,y):
 cx=cy=58/6; radius=math.hypot(x-cx,y-cy)
 causeway=abs(x-cx)<=.65 or abs(y-cy)<=.65 or abs((x-cx)-(y-cy))<=.55
 satellites=any(math.hypot(x-sx,y-sy)<1.7 for sx,sy in
                ((4.8,5.0),(14.6,5.2),(4.6,14.4),(14.7,14.5),(9.7,17.5)))
 if causeway and radius<10: return 2
 if radius<4.6: return 0
 if satellites: return 1
 return 3

def crownwater_height(x,y):
 if abs(x-58)<=4 or abs(y-58)<=4: return 11
 central=math.hypot(x-58,y-58)<29
 satellites=any(math.hypot(x-sx,y-sy)<11 for sx,sy in
                ((29,30),(88,31),(28,87),(88,87),(58,106)))
 return 11 if central or satellites else 6

def whitehorn_tile(x,y):
 cx=58/6
 glacier=abs(x-cx)<2.2 and 3<y<17
 road=abs(x-cx)<.7 or abs(x+y-19.5)<.65
 rock=min(x,y,31-x,31-y)<4 or ((x*5+y*7)%13)<3
 return 3 if glacier else 2 if road else 1 if rock else 0

def whitehorn_height(x,y):
 if abs(x-58)<=4 or abs(y-58)<=3: return 11
 glacier=abs(x-58)<14 and 24<y<112
 edge=min(x,y,191-x,191-y)
 peak=max(0,(48-edge)//5)+max(0,(y-100)//14)
 return max(8,min(31,(8 if glacier else 11)+peak+region_noise('whitehorn_range',x//7,y//7)//7))

def amethyst_tile(x,y):
 cx=cy=58/6
 basin=math.hypot((x-cx)*.90,(y-cy)*1.08)<6.2
 storm_road=abs(x-cx)<.72 or abs(y-cy)<.72 or abs((x-cx)+(y-cy))<.62
 crystal_field=((x*7+y*11)%19)<5 or math.hypot(x-24,y-8)<3.4
 return 2 if storm_road else 0 if basin else 3 if crystal_field else 1

def amethyst_height(x,y):
 if abs(x-58)<=4 or abs(y-58)<=3: return 11
 basin=max(0,28-int(math.hypot(x-58,y-58)))
 rim=max(0,(34-min(x,y,191-x,191-y))//5)
 storm_shelf=max(0,(x+y-214)//18)
 return max(7,min(29,11-basin//7+rim+storm_shelf+
                   region_noise('amethyst_barrens',x//7,y//7)//8))

def sunmane_tile(x,y):
 cx=cy=58/6
 road=abs(x-cx)<.72 or abs(y-cy)<.72 or abs((x-cx)-(y-cy))<.62
 camp=any(math.hypot(x-sx,y-sy)<2.25 for sx,sy in
          ((6.0,6.0),(13.4,5.8),(5.8,13.5),(13.7,13.4)))
 dry_grass=((x*5+y*9)%17)<7
 return 2 if road else 0 if camp else 3 if dry_grass else 1

def sunmane_height(x,y):
 if abs(x-58)<=4 or abs(y-58)<=3: return 11
 edge=min(x,y,191-x,191-y)
 mesa=max(0,(31-edge)//7)
 rolling=((x//22+y//18)%4)-1
 return max(8,min(24,11+mesa+rolling+
                   region_noise('sunmane_steppe',x//8,y//8)//9))

def amberwood_tile(x,y):
 cx=cy=58/6
 estate=math.hypot((x-cx)*1.1,(y-cy)*.9)<3.7
 road=abs(x-cx)<.65 or abs(y-cy)<.65 or abs((x-cx)+(y-cy))<.58
 old_growth=((x*7+y*5)%13)<6 or min(x,y,31-x,31-y)<4
 return 2 if road else 0 if estate else 3 if old_growth else 1

def amberwood_height(x,y):
 if abs(x-58)<=4 or abs(y-58)<=3: return 11
 edge=min(x,y,191-x,191-y)
 wooded_rise=max(0,(38-edge)//8)
 ridge=max(0,(y-110)//20)
 return max(8,min(25,11+wooded_rise+ridge+
                   region_noise('amberwood',x//7,y//7)//9))

def grey_moors_tile(x,y):
 cx=cy=58/6
 causeway=abs(x-cx)<.68 or abs(y-cy)<.68 or abs((x-cx)-(y-cy))<.55
 bog=(math.sin(x*.78)+math.cos(y*.64)>0.45) and not causeway
 barrow=any(math.hypot(x-sx,y-sy)<1.7 for sx,sy in
            ((5.2,5.0),(14.1,5.2),(5.0,14.2),(14.3,14.0)))
 return 2 if causeway else 0 if barrow else 3 if bog else 1

def grey_moors_height(x,y):
 if abs(x-58)<=4 or abs(y-58)<=3: return 11
 bog=(math.sin(x*.13)+math.cos(y*.11)>0.5)
 edge=min(x,y,191-x,191-y)
 rise=max(0,(28-edge)//7)
 return max(7,min(21,(8 if bog else 11)+rise+
                   region_noise('grey_moors',x//8,y//8)//10))

def westhaven_tile(x,y):
 cx=58/6
 sea=y>17 or (y>13 and (x<5 or x>15))
 quay=(15<=y<=17) or abs(x-cx)<.65 or abs(y-10)<.65
 harbor=sea and (5<=x<=15 and y<23)
 return 2 if quay else 3 if harbor else 0 if sea else 1

def westhaven_height(x,y):
 if abs(x-58)<=4 or abs(y-58)<=3: return 11
 sea=y>102 or (y>78 and (x<30 or x>90))
 bluff=max(0,(70-y)//18)+max(0,(24-min(x,191-x))//6)
 return 6 if sea else max(9,min(23,11+bluff+
              region_noise('westhaven',x//8,y//8)//10))

def verdant_tile(x,y):
 cx=58/6
 river=abs(x-cx-1.8*math.sin(y*.45))<1.15
 stair=abs(x-cx)<.65 or abs((x-cx)+(y-12))<.58
 cenote=any(math.hypot(x-sx,y-sy)<1.8 for sx,sy in
            ((5.0,6.0),(14.5,7.0),(5.5,14.0),(14.0,15.0)))
 return 3 if river or cenote else 2 if stair else 0 if y<12 else 1

def verdant_height(x,y):
 if abs(x-58)<=4 or abs(y-58)<=3: return 11
 terrace=max(0,(118-y)//18)
 ravine=max(0,18-int(abs(x-58-10*math.sin(y*.07))))//5
 return max(7,min(29,11+terrace-ravine+
                   region_noise('verdant_stair',x//7,y//7)//9))

def ssarathi_tile(x,y):
 cx=cy=58/6
 channel=abs(x-cx)<1.0 or abs(y-cy)<.7
 pools=any(math.hypot(x-sx,y-sy)<2.0 for sx,sy in
           ((5.2,5.3),(14.4,5.4),(5.0,14.2),(14.5,14.3)))
 temple=math.hypot(x-cx,y-5.0)<3.4
 return 3 if pools else 2 if channel else 0 if temple else 1

def ssarathi_height(x,y):
 if abs(x-58)<=4 or abs(y-58)<=3: return 11
 pool=any(math.hypot(x-sx,y-sy)<13 for sx,sy in
          ((31,32),(86,32),(30,86),(87,86)))
 temple=max(0,28-int(math.hypot(x-58,y-30)))//5
 return 7 if pool else max(9,min(26,11+temple+
              region_noise('ssarathi_ruins',x//7,y//7)//9))

def manymouth_tile(x,y):
 cx=58/6
 main_channel=abs(x-cx-2.2*math.sin(y*.38))<1.45
 distributary=abs((x-cx)+(y-13))<.75 or abs((x-cx)-(y-13))<.75
 boardwalk=abs(y-cx)<.62 or abs(x-cx)<.58
 return 2 if boardwalk else 3 if main_channel or distributary else 0 if y>17 else 1

def manymouth_height(x,y):
 if abs(x-58)<=4 or abs(y-58)<=3: return 11
 channel=abs(x-58-13*math.sin(y*.065))<10 or \
         abs((x-58)+(y-78))<7 or abs((x-58)-(y-78))<7
 levee=max(0,(25-min(x,y,191-x,191-y))//7)
 return 6 if channel else max(8,min(19,10+levee+
              region_noise('manymouth_delta',x//9,y//9)//11))

def four_gates_terrain_pixel(kind):
 def pixel(x,y):
  grain=((x*17+y*29+(x^y)*5)%23)-11
  if kind=='civic_stone':
   joint=x%48<3 or y%32<3; base=(112,113,99) if joint else (157,151,126)
   if abs(((x*5+y*7)%61)-30)<2: base=(181,172,139)
  elif kind=='highland_grass':
   blade=((x*3+y*11)%37)<3; base=(91,112,69) if blade else (66,91,61)
  elif kind=='ceremonial_road':
   joint=x%32<2 or (y+(x//32)*7)%40<2; base=(118,108,86) if joint else (187,162,108)
  else:
   ripple=abs(((x*3+y*5)%47)-23)<3; base=(84,174,184) if ripple else (38,128,149)
   grain//=2
  return (*(max(0,min(255,channel+grain)) for channel in base),255)
 return pixel

MAP_FONT={
 'A':('01110','10001','10001','11111','10001','10001','10001'),
 'C':('01111','10000','10000','10000','10000','10000','01111'),
 'E':('11111','10000','10000','11110','10000','10000','11111'),
 'F':('11111','10000','10000','11110','10000','10000','10000'),
 'G':('01111','10000','10000','10111','10001','10001','01111'),
 'H':('10001','10001','10001','11111','10001','10001','10001'),
 'L':('10000','10000','10000','10000','10000','10000','11111'),
 'N':('10001','11001','10101','10011','10001','10001','10001'),
 'O':('01110','10001','10001','10001','10001','10001','01110'),
 'P':('11110','10001','10001','11110','10000','10000','10000'),
 'R':('11110','10001','10001','11110','10100','10010','10001'),
 'S':('01111','10000','10000','01110','00001','00001','11110'),
 'T':('11111','00100','00100','00100','00100','00100','00100'),
 'U':('10001','10001','10001','10001','10001','10001','01110'),
 'W':('10001','10001','10001','10101','10101','10101','01010'),
 'Z':('11111','00001','00010','00100','01000','10000','11111'),
}

def map_label_pixel(text,x,y,left,top,scale=2):
 if y<top or y>=top+7*scale: return False
 cursor=left
 for character in text:
  if character==' ':
   cursor+=3*scale
   continue
  glyph=MAP_FONT[character]
  if cursor<=x<cursor+5*scale:
   return glyph[(y-top)//scale][(x-cursor)//scale]=='1'
  cursor+=6*scale
 return False

def four_gates_cartography_pixel(x,y):
 # Stylised survey map matching the ELM composition: outer highlands, the
 # circular civic island, four water crossings and concentric districts.
 cx=cy=155; radius=math.hypot(x-cx,y-cy)
 causeway=abs(x-cx)<10 or abs(y-cy)<10
 if 116<radius<158 and not causeway:
  color=(38,132,151)
  if (x+y)%37<3: color=(83,184,192)
 elif radius<116:
  color=(101,126,79) if radius>72 else (154,143,99)
 else:
  color=(65,91,61) if ((x//18+y//18)&1) else (75,103,68)
 if causeway and radius<178: color=(190,166,105)
 if 58<radius<66: color=(207,187,128)
 if radius<25: color=(188,174,127)
 # Fortified ring and the four monumental gate symbols.
 if 106<radius<111: color=(81,85,77)
 for gx,gy in ((155,44),(155,266),(44,155),(266,155)):
  if abs(x-gx)<9 and abs(y-gy)<13: color=(218,193,126)
 # Civic blocks are deliberately arranged in concentric districts.
 for angle in range(0,360,30):
  bx=int(cx+82*math.cos(math.radians(angle))); by=int(cy+82*math.sin(math.radians(angle)))
  if abs(x-bx)<5 and abs(y-by)<4: color=(65,72,68)
 labels=(("FOUR GATES",318,42,2),("NORTH GATE",318,82,1),
         ("CENTRAL PLAZA",318,112,1),("EAST GATE",318,142,1),
         ("SOUTH GATE",318,172,1),("WEST GATE",318,202,1))
 if any(map_label_pixel(text,x,y,left,top,scale) for text,left,top,scale in labels):
  color=(238,224,179)
 # Legend strokes tie labels to the same visual language as roads and water.
 if 315<x<492 and 28<y<224 and (x in (315,492) or y in (28,224)): color=(116,101,72)
 return (*color,255)

def four_gates_placements():
 placements=[]
 # Four cardinal gate complexes and paired bridge spans across the river.
 for x,y,rotation in ((58,16,0),(58,104,180),(16,58,90),(104,58,270)):
  placements.append(("3dobjects/nymara/four_gates_gatehouse.e3d",x,y,0,rotation))
 for x,y,rotation in ((58,27,0),(58,89,0),(27,58,90),(89,58,90)):
  placements.append(("3dobjects/nymara/four_gates_radial_bridge.e3d",x,y,0,rotation))
 # Segmented civic wall reads as an octagonal fortified island while leaving
 # wide openings at each travel axis.
 wall_segments=((34,34,45),(46,27,15),(70,27,345),(82,34,315),
                (89,46,285),(89,70,255),(82,82,225),(70,89,195),
                (46,89,165),(34,82,135),(27,70,105),(27,46,75))
 for x,y,rotation in wall_segments:
  placements.append(("3dobjects/nymara/four_gates_civic_wall.e3d",x,y,0,rotation))
 # Eight civic towers establish the skyline and frame the cardinal districts.
 for j,(x,y) in enumerate(((40,40),(58,35),(76,40),(81,58),(76,76),(58,81),(40,76),(35,58))):
  placements.append(("3dobjects/nymara/four_gates_civic_tower.e3d",x,y,0,j*45))
 # Concentric plazas, ward waystones, public fountains and service pavilions.
 placements.append(("3dobjects/nymara/four_gates_waystone.e3d",58,64,0,0))
 for j,(x,y) in enumerate(((58,48),(68,58),(58,68),(48,58))):
  placements.append(("3dobjects/nymara/mirrorhold_public_fountain.e3d",x,y,0,j*90))
 for j,(x,y) in enumerate(((45,48),(71,48),(45,68),(71,68),(50,42),(66,42),(50,74),(66,74))):
  placements.append(("3dobjects/nymara/four_gates_civic_pavilion.e3d",x,y,0,(j%4)*90))
 # Original vegetation softens the monumental stonework and marks the outer
 # park belt visible in the concept rendering.
 for j,(x,y) in enumerate(((32,22),(44,20),(72,20),(84,22),(94,32),(96,44),
                           (96,72),(94,84),(84,94),(72,96),(44,96),(32,94),
                           (22,84),(20,72),(20,44),(22,32))):
  placements.append(("3dobjects/nymara/four_gates_park_tree.e3d",x,y,0,(j*29)%360))
 for j,(x,y) in enumerate(((42,52),(42,64),(52,42),(64,42),(74,52),(74,64),
                           (52,74),(64,74),(34,58),(82,58),(58,34),(58,82))):
  placements.append(("3dobjects/nymara/four_gates_lantern.e3d",x,y,0,(j*30)%360))
 return placements

def mirrorhold_placements():
 p=[]
 # High observatory-citadel and its four lens towers.
 p.append(("3dobjects/nymara/glasswarden_observatory.e3d",58,34,0,180))
 for j,(x,y) in enumerate(((42,34),(74,34),(50,48),(66,48))):
  p.append(("3dobjects/nymara/glasswarden_lens_tower.e3d",x,y,0,j*90))
 for j,(x,y) in enumerate(((34,44),(82,44),(34,68),(82,68),(46,76),(70,76),(42,98),(74,98))):
  p.append(("3dobjects/nymara/mirrorhold_civic_tower.e3d",x,y,0,j*45))
 # Terraced canal walls define the descent from citadel to lower lake.
 for j,(x,y,r) in enumerate(((30,54,90),(86,54,270),(30,72,90),(86,72,270),
                              (36,84,45),(80,84,315),(40,104,0),(56,108,0),(72,104,0))):
  p.append(("3dobjects/nymara/mirrorhold_canal_wall.e3d",x,y,0,r))
 # Bridges make the lower water district readable and traversable.
 for j,(x,y,r) in enumerate(((58,74,0),(44,86,45),(72,86,315),(46,100,90),(70,100,90),(58,112,0))):
  p.append(("3dobjects/nymara/mirrorhold_radial_bridge.e3d",x,y,0,r))
 for j,(x,y) in enumerate(((42,58),(74,58),(58,46),(58,66),(38,92),(78,92))):
  p.append(("3dobjects/nymara/mirrorhold_public_fountain.e3d",x,y,0,j*60))
 for j,(x,y) in enumerate(((30,34),(86,34),(26,62),(90,62),(30,96),(86,96),(50,118),(66,118))):
  p.append(("3dobjects/nymara/glasswarden_field_station.e3d",x,y,0,j*47))
 return p

def crownwater_placements():
 p=[]
 # Pale central island capital, ringed by civic towers and fountains.
 for j,(x,y) in enumerate(((42,42),(74,42),(42,74),(74,74),(58,36),(36,58),(80,58),(58,80))):
  p.append(("3dobjects/nymara/mirrorhold_civic_tower.e3d",x,y,0,j*45))
 for j,(x,y) in enumerate(((48,48),(68,48),(48,68),(68,68),(58,44),(44,58),(72,58),(58,72))):
  p.append(("3dobjects/nymara/mirrorhold_public_fountain.e3d",x,y,0,j*45))
 # Four ferry approaches and an outer southern island route.
 for j,(x,y,r) in enumerate(((58,24,90),(24,58,0),(92,58,0),(58,92,90),(58,110,90),(36,36,45),(80,36,315),(36,80,315),(80,80,45))):
  p.append(("3dobjects/nymara/mirrorhold_radial_bridge.e3d",x,y,0,r))
 for j,(x,y,r) in enumerate(((30,30,45),(86,30,315),(28,86,315),(88,86,45),(58,106,0),(20,58,90),(98,58,270))):
  p.append(("3dobjects/nymara/crownwater_ferry_dock.e3d",x,y,0,r))
 for j,(x,y,r) in enumerate(((22,40,25),(96,40,335),(24,76,155),(94,78,205),(46,104,20),(72,106,340))):
  p.append(("3dobjects/nymara/crownwater_fishing_boat.e3d",x,y,0,r))
 for j,(x,y,r) in enumerate(((34,20,0),(82,22,180),(18,62,90),(100,64,270))):
  p.append(("3dobjects/nymara/crownwater_patrol_boat.e3d",x,y,0,r))
 for j,(x,y) in enumerate(((28,46),(88,46),(30,70),(86,70),(46,90),(70,90))):
  p.append(("3dobjects/nymara/crownwater_submerged_waystone.e3d",x,y,0,j*60))
 for j,(x,y) in enumerate(((32,26),(84,26),(26,84),(90,84),(48,108),(68,108))):
  p.append(("3dobjects/nymara/mirrorhold_lake_house.e3d",x,y,0,j*60))
 return p

def whitehorn_placements():
 p=[]
 p.append(("3dobjects/nymara/whitehorn_monastery.e3d",58,28,0,180))
 for j,(x,y,r) in enumerate(((58,42,0),(52,54,15),(64,66,345),(54,78,10),(62,90,350),(58,102,0))):
  p.append(("3dobjects/nymara/whitehorn_glacier.e3d",x,y,0,r))
 for j,(x,y,r) in enumerate(((58,50,90),(46,64,20),(70,72,160),(48,88,25),(68,98,155))):
  p.append(("3dobjects/nymara/whitehorn_rope_bridge.e3d",x,y,0,r))
 for j,(x,y) in enumerate(((42,38),(74,38),(38,62),(78,62),(42,92),(74,92))):
  p.append(("3dobjects/nymara/whitehorn_shrine.e3d",x,y,0,j*60))
 for j,(x,y) in enumerate(((30,32),(86,34),(26,54),(90,54),(30,78),(86,80),(36,104),(80,104),(48,116),(68,116))):
  p.append(("3dobjects/nymara/whitehorn_cairn.e3d",x,y,0,j*37))
 for j,(x,y,r) in enumerate(((24,74,90),(92,76,270),(34,112,45),(82,112,315))):
  p.append(("3dobjects/nymara/whitehorn_ice_cave.e3d",x,y,0,r))
 for j,(x,y,r) in enumerate(((26,42,90),(90,44,270),(58,118,180))):
  p.append(("3dobjects/nymara/whitehorn_mine_entrance.e3d",x,y,0,r))
 return p

def amethyst_placements():
 p=[]
 # The observatory anchors the sheltered resonant basin from the concept.
 p.append(("3dobjects/nymara/glasswarden_observatory.e3d",58,34,0,180))
 for j,(x,y,r) in enumerate(((42,38,20),(74,38,340),(34,56,70),(82,56,290),
                              (38,82,120),(78,82,240),(58,102,180))):
  p.append(("3dobjects/nymara/amethyst_crystal_bridge.e3d",x,y,0,r))
 for j,(x,y,r) in enumerate(((24,34,75),(92,34,285),(22,78,95),(94,78,265))):
  p.append(("3dobjects/nymara/amethyst_geode_cave.e3d",x,y,0,r))
 for j,(x,y) in enumerate(((32,24),(84,24),(26,52),(90,52),(30,94),(86,94),
                            (46,112),(70,112))):
  p.append(("3dobjects/nymara/amethyst_levitating_shards.e3d",x,y,0,j*43))
 for j,(x,y) in enumerate(((40,54),(76,54),(34,72),(82,72),(48,92),(68,92))):
  p.append(("3dobjects/nymara/amethyst_storm_ruin.e3d",x,y,0,j*60))
 for j,(x,y) in enumerate(((48,42),(68,42),(42,64),(74,64),(50,78),(66,78),
                            (30,106),(86,106),(22,62),(94,62))):
  p.append(("3dobjects/nymara/resonant_crystal_cluster.e3d",x,y,0,j*37))
 for j,(x,y) in enumerate(((46,30),(70,30),(32,64),(84,64),(40,100),(76,100))):
  p.append(("3dobjects/nymara/glasswarden_field_station.e3d",x,y,0,j*60))
 return p

def sunmane_placements():
 p=[]
 # Four clan camps frame a shared market and caravan crossroads.
 for j,(x,y) in enumerate(((36,36),(80,36),(36,80),(80,80),(48,30),(68,30),
                            (30,48),(86,48),(30,68),(86,68),(48,86),(68,86))):
  p.append(("3dobjects/nymara/orun_round_tent.e3d",x,y,0,j*31))
 for j,(x,y) in enumerate(((48,48),(68,48),(48,68),(68,68))):
  p.append(("3dobjects/nymara/orun_seasonal_market.e3d",x,y,0,j*90))
 for j,(x,y) in enumerate(((58,34),(82,58),(58,82),(34,58),(42,42),(74,42),
                            (42,74),(74,74))):
  p.append(("3dobjects/nymara/orun_banner_shrine.e3d",x,y,0,j*45))
 for j,(x,y,r) in enumerate(((58,24,180),(24,58,90),(92,58,270),(58,94,0))):
  p.append(("3dobjects/nymara/sunmane_caravanserai.e3d",x,y,0,r))
 for j,(x,y) in enumerate(((22,34),(94,34),(22,82),(94,82),(40,104),(76,104))):
  p.append(("3dobjects/nymara/sunmane_windmill.e3d",x,y,0,j*60))
 for j,(x,y) in enumerate(((58,44),(44,58),(72,58),(58,72))):
  p.append(("3dobjects/nymara/sunmane_well.e3d",x,y,0,j*90))
 for j,(x,y,r) in enumerate(((26,26,45),(90,26,315),(26,90,135),(90,90,225),
                              (48,108,0),(68,108,0))):
  p.append(("3dobjects/nymara/sunmane_animal_pen.e3d",x,y,0,r))
 for j,(x,y) in enumerate(((18,48),(98,48),(18,72),(98,72),(34,108),(82,108))):
  p.append(("3dobjects/nymara/sunmane_burial_mound.e3d",x,y,0,j*60))
 return p

def amberwood_placements():
 p=[]
 p.append(("3dobjects/nymara/amberwood_estate.e3d",58,42,0,180))
 for j,(x,y) in enumerate(((34,34),(82,34),(28,64),(88,64),(38,94),(78,94))):
  p.append(("3dobjects/nymara/amberwood_hunting_lodge.e3d",x,y,0,j*60))
 for j,(x,y) in enumerate(((24,24),(92,24),(20,52),(96,52),(24,84),(92,84),
                            (34,108),(82,108))):
  p.append(("3dobjects/nymara/amberwood_hollow_tree.e3d",x,y,0,j*43))
 for j,(x,y,r) in enumerate(((58,30,90),(30,58,0),(86,58,0),(58,88,90))):
  p.append(("3dobjects/nymara/amberwood_old_bridge.e3d",x,y,0,r))
 for j,(x,y) in enumerate(((30,30),(46,26),(70,26),(86,30),(22,42),(94,42),
                            (22,74),(94,74),(30,98),(46,106),(70,106),(86,98),
                            (38,50),(78,50),(38,78),(78,78))):
  p.append(("3dobjects/nymara/amberwood_tree.e3d",x,y,0,j*29))
 for j,(x,y,r) in enumerate(((42,38,45),(74,38,315),(34,72,90),(82,72,270),
                              (46,96,30),(70,96,330))):
  p.append(("3dobjects/nymara/amberwood_ruin_arch.e3d",x,y,0,r))
 for j,(x,y) in enumerate(((48,48),(68,48),(48,68),(68,68))):
  p.append(("3dobjects/nymara/amberwood_garden_fountain.e3d",x,y,0,j*90))
 return p

def grey_moors_placements():
 p=[]
 for j,(x,y) in enumerate(((34,34),(82,34),(30,82),(86,82),(48,104),(68,104))):
  p.append(("3dobjects/nymara/grey_moor_barrow.e3d",x,y,0,j*60))
 for j,(x,y) in enumerate(((44,28),(72,28),(28,52),(88,52),(38,72),(78,72),
                            (38,96),(78,96))):
  p.append(("3dobjects/nymara/grey_moor_standing_stones.e3d",x,y,0,j*45))
 for j,(x,y,r) in enumerate(((58,30,90),(30,58,0),(86,58,0),(58,86,90),
                              (42,44,45),(74,44,315),(42,74,315),(74,74,45))):
  p.append(("3dobjects/nymara/grey_moor_boardwalk.e3d",x,y,0,r))
 for j,(x,y,r) in enumerate(((26,34,75),(90,34,285),(24,86,105),(92,86,255))):
  p.append(("3dobjects/nymara/grey_moor_crypt_entrance.e3d",x,y,0,r))
 for j,(x,y) in enumerate(((22,50),(94,50),(22,72),(94,72),(40,112),(76,112))):
  p.append(("3dobjects/nymara/grey_moor_abandoned_cottage.e3d",x,y,0,j*60))
 for j,(x,y) in enumerate(((24,24),(92,24),(18,62),(98,62),(28,100),(88,100),
                            (46,92),(70,92),(34,66),(82,66))):
  p.append(("3dobjects/nymara/grey_moor_dead_tree.e3d",x,y,0,j*37))
 for j,(x,y) in enumerate(((48,48),(68,48),(48,68),(68,68),(58,98))):
  p.append(("3dobjects/nymara/grey_moor_ritual_shrine.e3d",x,y,0,j*72))
 return p

def westhaven_placements():
 p=[]
 p.append(("3dobjects/nymara/westhaven_lighthouse.e3d",24,34,0,90))
 for j,(x,y) in enumerate(((38,38),(54,38),(70,38),(86,38),(42,54),(58,54),(74,54),(90,54))):
  p.append(("3dobjects/nymara/westhaven_warehouse.e3d",x,y,0,j*45))
 for j,(x,y,r) in enumerate(((34,78,0),(58,78,0),(82,78,0),(46,94,0),(70,94,0))):
  p.append(("3dobjects/nymara/westhaven_dry_dock.e3d",x,y,0,r))
 for j,(x,y) in enumerate(((30,66),(46,66),(62,66),(78,66),(94,66),(42,88),(74,88))):
  p.append(("3dobjects/nymara/westhaven_harbor_crane.e3d",x,y,0,j*51))
 for j,(x,y,r) in enumerate(((38,104,0),(58,106,0),(78,104,0),(28,92,20),(88,92,340))):
  p.append(("3dobjects/nymara/westhaven_shipyard_frame.e3d",x,y,0,r))
 for j,(x,y) in enumerate(((42,46),(58,46),(74,46),(50,58),(66,58),(82,58))):
  p.append(("3dobjects/nymara/westhaven_fish_market.e3d",x,y,0,j*60))
 for j,(x,y,r) in enumerate(((22,74,90),(22,90,90),(94,74,270),(94,90,270),
                              (30,112,0),(46,112,0),(62,112,0),(78,112,0),(94,112,0))):
  p.append(("3dobjects/nymara/westhaven_seawall.e3d",x,y,0,r))
 return p

def verdant_placements():
 p=[]
 for j,(x,y,r) in enumerate(((58,24,0),(58,38,0),(52,52,15),(64,66,345),
                              (50,80,10),(66,94,350),(58,108,0))):
  p.append(("3dobjects/nymara/verdant_basalt_steps.e3d",x,y,0,r))
 for j,(x,y) in enumerate(((30,34),(86,38),(26,78),(90,82))):
  p.append(("3dobjects/nymara/verdant_cenote_stairs.e3d",x,y,0,j*90))
 for j,(x,y,r) in enumerate(((42,42,45),(74,44,315),(38,70,30),(78,72,330),
                              (44,98,20),(72,100,340))):
  p.append(("3dobjects/nymara/verdant_root_bridge.e3d",x,y,0,r))
 for j,(x,y,r) in enumerate(((28,54,75),(88,56,285),(32,92,110),(84,94,250),
                              (58,84,90))):
  p.append(("3dobjects/nymara/verdant_vine_bridge.e3d",x,y,0,r))
 for j,(x,y) in enumerate(((34,26),(82,28),(24,64),(92,66),(36,108),(80,110))):
  p.append(("3dobjects/nymara/verdant_tree_platform.e3d",x,y,0,j*60))
 for j,(x,y) in enumerate(((48,48),(68,48),(44,76),(72,76),(58,100))):
  p.append(("3dobjects/nymara/verdant_water_shrine.e3d",x,y,0,j*72))
 for j,(x,y) in enumerate(((22,28),(94,28),(18,48),(98,48),(20,86),(96,86),
                            (28,112),(88,112),(40,62),(76,62),(42,90),(74,90))):
  p.append(("3dobjects/nymara/verdant_giant_fern.e3d",x,y,0,j*31))
 return p

def ssarathi_placements():
 p=[]
 p.append(("3dobjects/nymara/ssarathi_temple.e3d",58,28,0,180))
 for j,(x,y,r) in enumerate(((28,34,75),(88,34,285),(24,82,105),(92,82,255))):
  p.append(("3dobjects/nymara/ssarathi_vault_entrance.e3d",x,y,0,r))
 for j,(x,y,r) in enumerate(((58,42,0),(42,58,90),(74,58,90),(58,78,0),
                              (34,46,45),(82,46,315))):
  p.append(("3dobjects/nymara/ssarathi_water_gate.e3d",x,y,0,r))
 for j,(x,y) in enumerate(((32,32),(84,32),(30,84),(86,84),(46,100),(70,100))):
  p.append(("3dobjects/nymara/ssarathi_sunken_court.e3d",x,y,0,j*60))
 for j,(x,y) in enumerate(((48,48),(68,48),(42,72),(74,72),(58,92))):
  p.append(("3dobjects/nymara/ssarathi_ritual_pool.e3d",x,y,0,j*72))
 for j,(x,y) in enumerate(((40,34),(76,34),(28,62),(88,62),(38,92),(78,92),
                            (50,110),(66,110))):
  p.append(("3dobjects/nymara/ssarathi_sun_stela.e3d",x,y,0,j*45))
 for j,(x,y,r) in enumerate(((46,38,45),(70,38,315),(34,68,90),(82,68,270),
                              (42,102,30),(74,102,330))):
  p.append(("3dobjects/nymara/ssarathi_ruin_arch.e3d",x,y,0,r))
 return p

def manymouth_placements():
 p=[]
 for j,(x,y) in enumerate(((38,34),(58,32),(78,36),(32,58),(54,56),(78,60),
                            (38,82),(60,80),(82,86),(48,104),(72,106))):
  p.append(("3dobjects/nymara/manymouth_stilt_house.e3d",x,y,0,j*33))
 for j,(x,y,r) in enumerate(((58,42,90),(42,58,0),(70,58,0),(58,74,90),
                              (34,46,45),(82,48,315),(38,72,315),(78,76,45),
                              (50,94,20),(70,96,340))):
  p.append(("3dobjects/nymara/manymouth_boardwalk.e3d",x,y,0,r))
 for j,(x,y,r) in enumerate(((28,38,75),(88,40,285),(24,74,105),(92,78,255),
                              (58,112,180))):
  p.append(("3dobjects/nymara/manymouth_ferry_dock.e3d",x,y,0,r))
 for j,(x,y,r) in enumerate(((30,92,110),(86,94,250),(42,112,160),(76,114,200))):
  p.append(("3dobjects/nymara/manymouth_hidden_dock.e3d",x,y,0,r))
 for j,(x,y) in enumerate(((22,28),(94,28),(18,54),(98,54),(20,88),(96,88),
                            (28,108),(88,108),(42,44),(74,44),(34,68),(82,68))):
  p.append(("3dobjects/nymara/manymouth_mangrove.e3d",x,y,0,j*31))
 for j,(x,y) in enumerate(((46,48),(66,48),(46,68),(66,68),(56,86),(76,88))):
  p.append(("3dobjects/nymara/manymouth_market_stall.e3d",x,y,0,j*60))
 for j,(x,y,r) in enumerate(((26,60,90),(90,62,270),(34,100,120),(82,102,240))):
  p.append(("3dobjects/nymara/manymouth_flooded_cave.e3d",x,y,0,r))
 return p

def drowned_crown_placements():
 # A ceremonial submerged processional: the safe arrival vestibule at (58,10)
 # opens into twin water galleries, a statue court, and the crown altar.
 p=[]
 for x,y in ((34,22),(58,22),(82,22),(34,46),(58,46),(82,46),
             (34,70),(58,70),(82,70),(34,94),(58,94),(82,94)):
  p.append(("3dobjects/nymara/interiors/crownwater_drowned_floor.e3d",x,y,0,0))
 for x,y,r in ((24,22,90),(24,40,90),(24,58,90),(24,76,90),(24,94,90),
               (92,22,270),(92,40,270),(92,58,270),(92,76,270),(92,94,270),
               (34,106,180),(50,106,180),(66,106,180),(82,106,180)):
  p.append(("3dobjects/nymara/interiors/crownwater_underwater_wall.e3d",x,y,0,r))
 for x,y,r in ((46,34,90),(70,34,90),(46,58,90),(70,58,90),(46,82,90),(70,82,90)):
  p.append(("3dobjects/nymara/interiors/crownwater_submerged_arch.e3d",x,y,0,r))
 for x,y,r in ((36,34,0),(58,34,0),(80,34,0),(36,58,0),(80,58,0),
               (36,82,0),(58,82,0),(80,82,0)):
  p.append(("3dobjects/nymara/interiors/crownwater_water_channel.e3d",x,y,0,r))
 for x,y,r in ((34,58,45),(82,58,315),(42,92,20),(74,92,340)):
  p.append(("3dobjects/nymara/interiors/crownwater_drowned_statue.e3d",x,y,0,r))
 p.append(("3dobjects/nymara/interiors/crownwater_shell_altar.e3d",58,94,0,180))
 return p

def whitehorn_temple_placements():
 # A sheltered monastery nave rises through prayer bays into the glacier
 # sanctuary. The southern arrival remains broad enough for party entry.
 p=[]
 for x,y in ((34,22),(58,22),(82,22),(34,46),(58,46),(82,46),
             (34,70),(58,70),(82,70),(34,94),(58,94),(82,94)):
  p.append(("3dobjects/nymara/interiors/whitehorn_monastery_floor.e3d",x,y,0,0))
 for x,y,r in ((24,22,90),(24,40,90),(24,58,90),(24,76,90),(24,94,90),
               (92,22,270),(92,40,270),(92,58,270),(92,76,270),(92,94,270),
               (34,106,180),(50,106,180),(66,106,180),(82,106,180)):
  p.append(("3dobjects/nymara/interiors/whitehorn_monastery_wall.e3d",x,y,0,r))
 for x,y,r in ((46,34,90),(70,34,90),(46,58,90),(70,58,90),(46,82,90),(70,82,90)):
  p.append(("3dobjects/nymara/interiors/whitehorn_ice_arch.e3d",x,y,0,r))
 for x,y in ((34,42),(82,42),(34,62),(82,62),(34,82),(82,82),(46,94),(70,94)):
  p.append(("3dobjects/nymara/interiors/whitehorn_prayer_column.e3d",x,y,0,0))
 for x,y,r in ((34,30,0),(82,30,0),(34,94,0),(82,94,0)):
  p.append(("3dobjects/nymara/interiors/whitehorn_mine_support.e3d",x,y,0,r))
 p.append(("3dobjects/nymara/interiors/whitehorn_glacier_altar.e3d",58,94,0,180))
 return p

def resonant_vault_placements():
 # Brass-walled research galleries surround a resonant lens chamber. Tables
 # and shelves form readable work zones without blocking the central route.
 p=[]
 for x,y in ((34,22),(58,22),(82,22),(34,46),(58,46),(82,46),
             (34,70),(58,70),(82,70),(34,94),(58,94),(82,94)):
  p.append(("3dobjects/nymara/interiors/glasswarden_laboratory_floor.e3d",x,y,0,0))
 for x,y,r in ((24,22,90),(24,40,90),(24,58,90),(24,76,90),(24,94,90),
               (92,22,270),(92,40,270),(92,58,270),(92,76,270),(92,94,270),
               (34,106,180),(50,106,180),(66,106,180),(82,106,180)):
  p.append(("3dobjects/nymara/interiors/glasswarden_brass_wall.e3d",x,y,0,r))
 for x,y,r in ((34,40,0),(82,40,180),(34,62,0),(82,62,180),(42,86,0),(74,86,180)):
  p.append(("3dobjects/nymara/interiors/glasswarden_experiment_table.e3d",x,y,0,r))
 for x,y,r in ((28,32,90),(88,32,270),(28,54,90),(88,54,270),(28,78,90),(88,78,270)):
  p.append(("3dobjects/nymara/interiors/glasswarden_archive_shelf.e3d",x,y,0,r))
 for x,y in ((42,32),(74,32),(42,56),(74,56),(42,80),(74,80),(48,96),(68,96)):
  p.append(("3dobjects/nymara/interiors/glasswarden_crystal_brazier.e3d",x,y,0,0))
 p.append(("3dobjects/nymara/interiors/glasswarden_observatory_lens.e3d",58,92,0,180))
 return p

def amberwood_estate_placements():
 # A formal entry and banquet hall branch into residential chambers before an
 # overgrown memorial court, keeping the main north-south route legible.
 p=[]
 for x,y in ((34,22),(58,22),(82,22),(34,46),(58,46),(82,46),
             (34,70),(58,70),(82,70),(34,94),(58,94),(82,94)):
  p.append(("3dobjects/nymara/interiors/amberwood_manor_floor.e3d",x,y,0,0))
 for x,y,r in ((24,22,90),(24,40,90),(24,58,90),(24,76,90),(24,94,90),
               (92,22,270),(92,40,270),(92,58,270),(92,76,270),(92,94,270),
               (34,106,180),(50,106,180),(66,106,180),(82,106,180)):
  p.append(("3dobjects/nymara/interiors/amberwood_manor_wall.e3d",x,y,0,r))
 for x,y,r in ((46,34,90),(70,34,90),(46,58,90),(70,58,90),(46,82,90),(70,82,90)):
  p.append(("3dobjects/nymara/interiors/amberwood_estate_door.e3d",x,y,0,r))
 for x,y,r in ((36,48,0),(80,48,180),(36,70,0),(80,70,180)):
  p.append(("3dobjects/nymara/interiors/amberwood_banquet_table.e3d",x,y,0,r))
 for x,y,r in ((32,30,90),(84,30,270),(32,84,90),(84,84,270),(44,94,0),(72,94,180)):
  p.append(("3dobjects/nymara/interiors/amberwood_estate_bed.e3d",x,y,0,r))
 for x,y,r in ((34,60,45),(82,60,315),(42,96,20),(74,96,340)):
  p.append(("3dobjects/nymara/interiors/amberwood_overgrown_statue.e3d",x,y,0,r))
 return p

def grey_moor_barrows_placements():
 p=[]
 for x,y in ((34,22),(58,22),(82,22),(34,46),(58,46),(82,46),
             (34,70),(58,70),(82,70),(34,94),(58,94),(82,94)):
  p.append(("3dobjects/nymara/interiors/grey_moor_crypt_floor.e3d",x,y,0,0))
 for x,y,r in ((24,22,90),(24,40,90),(24,58,90),(24,76,90),(24,94,90),
               (92,22,270),(92,40,270),(92,58,270),(92,76,270),(92,94,270),
               (34,106,180),(50,106,180),(66,106,180),(82,106,180)):
  p.append(("3dobjects/nymara/interiors/grey_moor_crypt_wall.e3d",x,y,0,r))
 for x,y,r in ((46,34,90),(70,34,90),(46,58,90),(70,58,90),(46,82,90),(70,82,90)):
  p.append(("3dobjects/nymara/interiors/grey_moor_barrow_arch.e3d",x,y,0,r))
 for x,y,r in ((32,40,0),(84,40,180),(32,62,0),(84,62,180),(40,88,0),(76,88,180),(40,98,0),(76,98,180)):
  p.append(("3dobjects/nymara/interiors/grey_moor_sarcophagus.e3d",x,y,0,r))
 for x,y,r in ((42,50,0),(74,50,180),(42,74,0),(74,74,180)):
  p.append(("3dobjects/nymara/interiors/grey_moor_spike_trap.e3d",x,y,0,r))
 p.append(("3dobjects/nymara/interiors/grey_moor_ritual_altar.e3d",58,94,0,180))
 return p

def ssarathi_archive_placements():
 p=[]
 for x,y in ((34,22),(58,22),(82,22),(34,46),(58,46),(82,46),
             (34,70),(58,70),(82,70),(34,94),(58,94),(82,94)):
  p.append(("3dobjects/nymara/interiors/ssarathi_scaled_floor.e3d",x,y,0,0))
 for x,y,r in ((24,22,90),(24,40,90),(24,58,90),(24,76,90),(24,94,90),
               (92,22,270),(92,40,270),(92,58,270),(92,76,270),(92,94,270),
               (34,106,180),(50,106,180),(66,106,180),(82,106,180)):
  p.append(("3dobjects/nymara/interiors/ssarathi_curved_wall.e3d",x,y,0,r))
 for x,y,r in ((46,34,90),(70,34,90),(46,58,90),(70,58,90),(46,82,90),(70,82,90)):
  p.append(("3dobjects/nymara/interiors/ssarathi_water_arch.e3d",x,y,0,r))
 for x,y,r in ((30,36,90),(86,36,270),(30,56,90),(86,56,270),(30,78,90),(86,78,270),(42,94,0),(74,94,180)):
  p.append(("3dobjects/nymara/interiors/ssarathi_archive_shelf.e3d",x,y,0,r))
 for x,y,r in ((38,62,30),(78,62,330),(44,88,15),(72,88,345)):
  p.append(("3dobjects/nymara/interiors/ssarathi_royal_statue.e3d",x,y,0,r))
 for x,y,r in ((42,46,0),(74,46,180),(42,72,0),(74,72,180)):
  p.append(("3dobjects/nymara/interiors/ssarathi_vault_trap.e3d",x,y,0,r))
 return p

def manymouth_labyrinth_placements():
 p=[]
 for x,y in ((34,22),(58,22),(82,22),(34,46),(58,46),(82,46),
             (34,70),(58,70),(82,70),(34,94),(58,94),(82,94)):
  p.append(("3dobjects/nymara/interiors/manymouth_flooded_floor.e3d",x,y,0,0))
 for x,y,r in ((24,22,90),(24,40,90),(24,58,90),(24,76,90),(24,94,90),
               (92,22,270),(92,40,270),(92,58,270),(92,76,270),(92,94,270),
               (34,106,180),(50,106,180),(66,106,180),(82,106,180)):
  p.append(("3dobjects/nymara/interiors/manymouth_stilt_wall.e3d",x,y,0,r))
 for x,y,r in ((58,24,0),(46,36,90),(70,36,90),(34,50,0),(58,50,0),
               (82,50,0),(46,66,90),(70,66,90),(46,86,0),(70,86,0)):
  p.append(("3dobjects/nymara/interiors/manymouth_boardwalk_section.e3d",x,y,0,r))
 for x,y,r in ((34,34,0),(82,34,0),(34,58,0),(82,58,0),(34,82,0),(58,82,0),(82,82,0),(58,96,0)):
  p.append(("3dobjects/nymara/interiors/manymouth_flood_channel.e3d",x,y,0,r))
 for x,y,r in ((28,38,90),(88,38,270),(28,64,90),(88,64,270),(36,94,0),(80,94,180)):
  p.append(("3dobjects/nymara/interiors/manymouth_smuggler_shelf.e3d",x,y,0,r))
 for x,y,r in ((38,44,0),(78,44,180),(38,72,0),(78,72,180),(46,98,0),(70,98,180)):
  p.append(("3dobjects/nymara/interiors/manymouth_fishing_crates.e3d",x,y,0,r))
 return p

def cartography_pixel(name, profile):
 a,b,accent=profile['palette']
 def pixel(x,y):
  tx=x*32//512; ty=y*32//512
  tile=region_tile(profile,name,tx,ty)
  base=(34,119,139) if tile==3 else (186,159,103) if tile==2 else b if tile==1 else a
  grain=region_noise(name,x//3,y//3)//3
  r,g,bl=(max(0,min(255,c+grain)) for c in base)
  # Roads, border gates, central settlement, water highlights and landmark.
  if abs(x-256)<5 or abs(y-256)<5: r,g,bl=accent
  if (x-256)**2+(y-256)**2<58**2: r,g,bl=tuple(min(255,int(c*1.18)) for c in accent)
  if (x in range(18,35) or x in range(477,494)) and abs(y-256)<28: r,g,bl=(225,199,128)
  if profile['water'] and ((x+y)%41==0) and tile==3: r,g,bl=(101,196,202)
  return r,g,bl,255
 return pixel

def checker(c1,c2):
 return lambda x,y: (*((c1 if ((x//24)^(y//24))&1 else c2)),255)

def append_actor(root, aid, label, family, skel, mesh, skin, anim_dir, radius, scale, bounds, special=False):
 a=ET.SubElement(root,"actor",id=str(aid),type=label,family=family,collision_radius=str(radius),scale=str(scale),bounds=" ".join(map(str,bounds)))
 ET.SubElement(a,"skeleton").text=skel; ET.SubElement(a,"mesh").text=mesh; ET.SubElement(a,"skin").text=skin; ET.SubElement(a,"step_duration").text="260"
 frames=ET.SubElement(a,"frames")
 mapping={"CAL_idle":"idle.xaf","CAL_idle2":"idle2.xaf","CAL_walk":"walk.xaf","CAL_run":"run.xaf","CAL_idle_sit":"sit.xaf","CAL_sit_down":"sit_down.xaf","CAL_stand_up":"stand_up.xaf","CAL_combat_idle":"combat_idle.xaf","CAL_attack_up_1":"attack.xaf","CAL_attack_down_1":"attack.xaf","CAL_attack_cast":"cast.xaf","CAL_pain1":"pain.xaf","CAL_pain2":"pain.xaf","CAL_die1":"die.xaf","CAL_die2":"die.xaf","CAL_harvest":"harvest.xaf","CAL_pick":"pick.xaf","CAL_drop":"drop.xaf"}
 if special: mapping["CAL_attack_up_2"]="special.xaf"
 for tag,f in mapping.items():
  kind=0 if tag in ("CAL_idle","CAL_idle2","CAL_walk","CAL_run","CAL_idle_sit","CAL_combat_idle") else 1
  ET.SubElement(frames,tag).text=f"{anim_dir}/{f} {kind}"

def copy_aliases(root, srcdir, names):
 for name,src in names.items():
  dst=root/srcdir/name; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(root/srcdir/src,dst)

def generate_npcs(root, actors):
 base=root/"actors/nymara/npcs"; humanoid_skeleton(base/"nymara_humanoid.xsf")
 aliases={"idle.xaf":"../../enemies/idle.xaf","idle2.xaf":"../../enemies/idle.xaf","walk.xaf":"../../enemies/walk.xaf","run.xaf":"../../enemies/run.xaf","sit.xaf":"../../eloria/sit.xaf","sit_down.xaf":"../../eloria/sit.xaf","stand_up.xaf":"../../eloria/idle.xaf","combat_idle.xaf":"../../enemies/combat_idle.xaf","attack.xaf":"../../enemies/attack.xaf","cast.xaf":"../../enemies/cast.xaf","pain.xaf":"../../enemies/pain.xaf","die.xaf":"../../enemies/die.xaf","harvest.xaf":"../../eloria/harvest.xaf","pick.xaf":"../../eloria/harvest.xaf","drop.xaf":"../../eloria/harvest.xaf","wave.xaf":"../../enemies/cast.xaf","bow.xaf":"../../eloria/harvest.xaf"}
 copy_aliases(root,"animations/nymara/humanoid",aliases)
 out=[]; aid=NPC_BASE
 for culture,(primary,accent,roles) in CULTURES.items():
  for variant in ("f","m"):
   for role in roles:
    slug=f"{culture}_{role}_{variant}"
    if slug in ('luminous_official_f','luminous_official_m'): feature='civic_official'
    elif slug in ('luminous_merchant_f','luminous_merchant_m'): feature='civic_merchant'
    elif slug in ('luminous_guard_f','luminous_guard_m'): feature='civic_guard'
    elif slug in ('luminous_ferryman_f','luminous_ferryman_m'): feature='civic_ferryman'
    elif slug in ('luminous_scholar_f','luminous_scholar_m'): feature='civic_scholar'
    elif slug in ('luminous_lake_priest_f','luminous_lake_priest_m'): feature='civic_priest'
    elif slug in ('luminous_civilian_f','luminous_civilian_m'): feature='civic_civilian'
    else: feature=f"nymara:{culture}:{role}"
    enemy_mesh(base/f"{slug}.xmf",feature,.96 if variant=="f" else 1.0)
    png(base/f"{slug}.png",512,512,material_pixel(primary,feature)); png(root/f"portraits/nymara/npcs/{slug}.png",256,256,material_pixel(accent,feature))
    append_actor(actors,aid,slug.replace('_',' ').title(),"nymara_npc","actors/nymara/npcs/nymara_humanoid.xsf",f"actors/nymara/npcs/{slug}.xmf",f"actors/nymara/npcs/{slug}.png","animations/nymara/humanoid",.42,.96 if variant=='f' else 1.0,(-.55,-.35,0,.55,.35,2.05))
    out.append({"actor_type":aid,"id":slug,"culture":culture,"role":role,"variant":variant,"portrait":f"portraits/nymara/npcs/{slug}.png","collision_radius":.42,"scale":.96 if variant=='f' else 1.0}); aid+=1
 (root/"nymara_npcs.json").write_text(json.dumps({"schema":1,"npcs":out},indent=2)+"\n")
 return out

def generate_creatures(root, actors):
 base=root/"actors/nymara/creatures"; creature_skeleton(base/"nymara_creature.xsf")
 aliases={"idle.xaf":"idle.xaf","idle2.xaf":"idle.xaf","walk.xaf":"walk.xaf","run.xaf":"run.xaf","sit.xaf":"idle.xaf","sit_down.xaf":"idle.xaf","stand_up.xaf":"idle.xaf","combat_idle.xaf":"idle.xaf","attack.xaf":"attack.xaf","cast.xaf":"attack.xaf","pain.xaf":"pain.xaf","die.xaf":"die.xaf","harvest.xaf":"attack.xaf","pick.xaf":"attack.xaf","drop.xaf":"attack.xaf","wave.xaf":"attack.xaf","bow.xaf":"idle.xaf","special.xaf":"attack.xaf"}
 copy_aliases(root,"animations/nymara/creatures",{k:f"../../creatures/{v}" for k,v in aliases.items()})
 palette=[(64,132,145),(181,205,214),(126,88,161),(187,120,51),(113,83,54),(55,126,79),(85,105,73)]
 out=[]
 for i,(region,slug,label,body,head,feature) in enumerate(CREATURES):
  aid=CREATURE_BASE+i; creature_mesh(base/f"{slug}.xmf",body,head,feature); c=palette[i%len(palette)]; c2=tuple(min(255,x+55) for x in c)
  png(base/f"{slug}.png",512,512,creature_material(c,feature)); png(root/f"portraits/nymara/creatures/{slug}.png",256,256,creature_material(c2,feature))
  radius=round(max(body[0],body[1])*.42,2); bounds=(-body[0]/2,-body[1]/2,0,body[0]/2,body[1]/2,1.6)
  append_actor(actors,aid,label,"nymara_creature","actors/nymara/creatures/nymara_creature.xsf",f"actors/nymara/creatures/{slug}.xmf",f"actors/nymara/creatures/{slug}.png","animations/nymara/creatures",radius,1.0,bounds,True)
  out.append({"actor_type":aid,"id":slug,"name":label,"region":region,"portrait":f"portraits/nymara/creatures/{slug}.png","collision_radius":radius,"bounds":bounds,"sound_events":{x:f"nymara.{slug}.{x}" for x in ("idle","attack","pain","death")},"drop_table_hook":f"drops.nymara.{slug}","summoning_hook":f"summon.nymara.{slug}"})
 (root/"nymara_creatures.json").write_text(json.dumps({"schema":1,"creatures":out},indent=2)+"\n"); return out

def equipment_shape(kind):
 def build(v,i):
  if kind=='civic_blade':
   tapered(v,i,0,.42,.11,.09,10); box(v,i,(0,0,.48),(.72,.16,.13)); tapered(v,i,.52,2.55,.18,.08,8); tapered(v,i,2.55,2.92,.12,0,8)
  elif kind=='lakeguard_spear':
   tapered(v,i,0,2.85,.065,.055,10); tapered(v,i,2.82,3.45,.24,0,8); tapered(v,i,.15,.42,.16,.07,8)
  elif kind=='mirror_shield':
   tapered(v,i,0,1.75,.78,.74,16); tapered(v,i,.08,1.67,.64,.61,16); tapered(v,i,.55,1.2,.28,.18,12); box(v,i,(0,.10,.88),(.16,.18,1.42))
  elif kind=='ceremonial_mail':
   box(v,i,(0,0,1.25),(.76,.38,.82)); tapered(v,i,.72,1.72,.48,.39,12); box(v,i,(-.46,0,1.42),(.26,.42,.32)); box(v,i,(.46,0,1.42),(.26,.42,.32));
   for z in (.76,.94,1.12,1.30,1.48): box(v,i,(0,-.21,z),(.72,.06,.065))
  elif kind=='civic_mantle':
   box(v,i,(0,.13,1.26),(.86,.08,1.72)); tapered(v,i,.34,2.18,.51,.42,12); box(v,i,(-.39,.12,1.25),(.12,.10,1.55)); box(v,i,(.39,.12,1.25),(.12,.10,1.55))
  elif kind=='ferry_hook':
   tapered(v,i,0,2.55,.075,.06,10); tapered(v,i,2.45,2.88,.24,.10,10,center=(.10,0)); tapered(v,i,2.70,3.06,.18,.04,8,center=(.28,0)); box(v,i,(0,0,.28),(.28,.16,.16))
  elif any(x in kind for x in ("blade","sabre","cutlass")):
   tapered(v,i,0,.38,.11,.09,10); box(v,i,(0,0,.44),(.62,.15,.12)); tapered(v,i,.50,2.38,.16,.07,8); tapered(v,i,2.38,2.72,.10,0,6)
  elif any(x in kind for x in ("spear","pike","staff")):
   tapered(v,i,0,2.82,.065,.05,10); tapered(v,i,2.78,3.34,.25,0,8); tapered(v,i,.12,.40,.14,.07,8)
  elif "bow" in kind:
   for z,w in ((.34,.36),(.86,.52),(1.38,.36)): box(v,i,(0,0,z),(w,.08,.46))
   box(v,i,(0,.02,.86),(.05,.04,1.52)); tapered(v,i,.65,1.08,.12,.08,8)
  elif any(x in kind for x in ("hammer","pick","adze")):
   tapered(v,i,0,2.20,.075,.06,10); box(v,i,(0,0,2.24),(.72,.28,.25)); tapered(v,i,2.20,2.62,.22,.04,8,center=(.28,0))
  elif "shield" in kind:
   tapered(v,i,0,1.72,.76,.68,16); tapered(v,i,.10,1.62,.61,.54,16); box(v,i,(0,.12,.86),(.14,.16,1.45)); tapered(v,i,.55,1.20,.24,.15,10)
  elif any(x in kind for x in ("mail","armor","leathers")):
   box(v,i,(0,0,1.24),(.70,.36,.82)); tapered(v,i,.70,1.72,.46,.36,12)
   for z in (.78,.98,1.18,1.38): box(v,i,(0,-.20,z),(.66,.055,.06))
  elif any(x in kind for x in ("cape","mantle")):
   tapered(v,i,.32,2.08,.49,.40,12,center=(0,.13)); box(v,i,(-.39,.13,1.18),(.11,.08,1.45)); box(v,i,(.39,.13,1.18),(.11,.08,1.45))
  else:
   tapered(v,i,0,1.30,.27,.20,10); tapered(v,i,1.20,1.74,.31,0,8); box(v,i,(0,.10,.62),(.20,.16,.86))
  # A deterministic maker's gem prevents distinct configured items sharing geometry.
  code=sum((n+1)*ord(ch) for n,ch in enumerate(kind))
  tapered(v,i,.42+.0001*(code%701),.66+.0001*(code%701),.09+.0001*(code%89),0,8,
          center=((-.18 if code%2 else .18),-.12))
 return build

def generate_equipment(root):
 out=[]; colors={"luminous":((66,151,160),(208,193,132)),"votary":((158,190,204),(222,230,229)),"glasswarden":((113,76,151),(190,142,67)),"orun":((167,91,43),(46,137,143)),"greyhaven":((55,78,93),(151,127,82)),"ssarathi":((47,112,77),(184,151,67))}
 for i,(culture,name) in enumerate(EQUIPMENT):
  iid=ITEM_BASE+i; model=root/f"3dobjects/nymara/equipment/{culture}/{name}.e3d"; texture(model.with_suffix('.png'),colors[culture]); e3d(model,model.with_suffix('.png').name,equipment_shape(name))
  png(root/f"textures/nymara/items/{name}.png",64,64,lambda x,y,c=colors[culture]: (*c[0],max(0,255-int(math.hypot(x-32,y-32)*7))) if math.hypot(x-32,y-32)<30 else (0,0,0,0))
  slot="weapon" if any(x in name for x in ("blade","sabre","cutlass","spear","pike","bow","hammer","pick","adze","staff","hook")) else "shield" if "shield" in name else "body" if any(x in name for x in ("mail","armor","leathers")) else "cape" if any(x in name for x in ("cape","mantle")) else "neck"
  out.append({"item_id":iid,"id":name,"name":name.replace('_',' ').title(),"culture":culture,"slot":slot,"model":f"3dobjects/nymara/equipment/{culture}/{name}.e3d","icon":f"textures/nymara/items/{name}.png","attachment_bone":"lower_arm_r" if slot=='weapon' else "lower_arm_l" if slot=='shield' else "spine","compatible_actor_family":"nymara_npc","unique_instance":slot in ("weapon","shield","body","cape")})
 (root/"nymara_equipment.json").write_text(json.dumps({"schema":1,"items":out},indent=2)+"\n"); return out

def generate_interactives_effects(root):
 names=["canal_lock_door","lake_gate","ferry_winch","ferry_ramp","water_wheel","ssarathi_sluice","crystal_console","crystal_discharge_pylon","region_waygate","thin_ice_marker","bog_gas_vent","stormglass_rod","waterfall_emitter","spray_emitter","canal_current_marker","harvest_available_marker","harvest_depleted_marker","landmark_light","dungeon_lock","archive_lift"]
 def prop(v,i): box(v,i,(0,0,.8),(1.2,.55,1.6)); tapered(v,i,1.55,2.35,.45,.12,8)
 out=[]
 for j,n in enumerate(names):
  path=root/f"3dobjects/nymara/interactives/{n}.e3d"; texture(path.with_suffix('.png'),((58+7*j%90,91+11*j%90,105+13*j%100),(172,142,75))); e3d(path,path.with_suffix('.png').name,prop); out.append({"interactive_id":2000+j,"id":n,"model":f"3dobjects/nymara/interactives/{n}.e3d","states":["idle","active"]})
 particles=["ferry_wake","waterfall","spray","bog_gas","thin_ice_crack","crystal_storm","portal","crystal_discharge","spell_water","spell_sun","impact_scale","landmark_glow"]
 for k,n in enumerate(particles): png(root/f"textures/nymara/effects/{n}.png",128,128,lambda x,y,k=k:(60+13*k%180,120+17*k%130,180+7*k%70,max(0,255-int(math.hypot(x-64,y-64)*4))))
 projectiles=["canal_bolt","sun_disc","crystal_shard","water_orb","scale_dart","storm_spark"]
 for k,n in enumerate(projectiles):
  path=root/f"3dobjects/nymara/projectiles/{n}.e3d"; texture(path.with_suffix('.png'),((54+20*k,113+9*k,176),(210,184,95))); e3d(path,path.with_suffix('.png').name,lambda v,i:tapered(v,i,-.6,.8,.28,0,6))
 manifest={"schema":1,"interactives":out,"particles":[{"effect_id":2100+i,"id":n,"atlas":f"textures/nymara/effects/{n}.png"} for i,n in enumerate(particles)],"missiles":[{"missile_id":2200+i,"id":n,"mesh":f"3dobjects/nymara/projectiles/{n}.e3d","speed":12.0,"effect":particles[i%len(particles)]} for i,n in enumerate(projectiles)]}
 (root/"nymara_effects_interactives.json").write_text(json.dumps(manifest,indent=2)+"\n"); return manifest

def generate_maps(root):
 # Stable object IDs belong to the manifest, while ELM records carry native paths.
 allmaps=REGIONS+DUNGEONS; regions=[]; connections=[]
 tile_palettes=(((71,103,72),(93,119,78)),((91,104,77),(118,126,88)),
                ((151,126,83),(179,153,103)),((38,105,126),(61,145,157)))
 for tile_id,(base,accent) in enumerate(tile_palettes):
  png(root/f"3dobjects/tile{tile_id}.png",256,256,
      lambda x,y,a=base,b=accent:(*(a if ((x//32+y//32)&1)==0 else b),255))
 for tile_id,kind in enumerate(('civic_stone','highland_grass','ceremonial_road','water'),4):
  png(root/f"3dobjects/tile{tile_id}.png",256,256,four_gates_terrain_pixel(kind))
 nymara3d=root/"3dobjects/nymara"
 interior=[p for p in (nymara3d/"interiors").rglob("*.e3d")]
 exterior=[p for p in nymara3d.glob("*.e3d")]
 harvest_manifest=[]
 harvestables=sorted({resource for resources in REGION_HARVESTS.values() for resource in resources})
 for resource_index,resource in enumerate(harvestables):
  path=root/f"3dobjects/nymara/{resource}.e3d"
  color=((55+resource_index*23)%150+55,(79+resource_index*31)%130+65,(91+resource_index*17)%120+70)
  accent=tuple(min(255,c+65) for c in color)
  texture(path.with_suffix('.png'),(color,accent))
  def harvest_shape(vertices,indices,name=resource):
   if name=='mirror_reed':
    for x,y,height in ((0,0,1.5),(.18,.08,1.2),(-.18,.06,1.35),(.10,-.16,1.05),(-.12,-.15,1.18)):
     tapered(vertices,indices,0,height,.035,.018,7,center=(x,y))
    crossed_leaves(vertices,indices,.18,1.12,.82,6)
   elif name in ('resonant_crystal','stormglass_shard'):
    for x,y,height,radius in ((0,0,1.5,.28),(.34,.12,1.0,.20),(-.31,.10,1.18,.22),(.12,-.30,.82,.18),(-.18,-.25,.72,.16)):
     tapered(vertices,indices,0,height,radius,0,8,center=(x,y))
   elif name=='sunmane_seed':
    tapered(vertices,indices,0,1.25,.055,.025,8)
    crossed_leaves(vertices,indices,.10,.95,.68,5)
    for x,y,z in ((.20,0,.88),(-.18,.04,.98),(.12,-.16,1.10),(-.10,-.15,.78)):
     tapered(vertices,indices,z-.15,z+.18,.14,.06,8,center=(x,y))
   elif any(word in name for word in ("reed","orchid","lotus","moss","bulb","silverleaf")):
    crossed_leaves(vertices,indices,0,1.15,.72,4)
   elif any(word in name for word in ("crystal","shard","geode","salt","pearl")):
    tapered(vertices,indices,0,1.05,.42,.08,7)
    tapered(vertices,indices,0,.72,.28,.04,6,center=(.35,.08))
   else:
    box(vertices,indices,(0,0,.25),(.72,.62,.50))
    tapered(vertices,indices,.42,.88,.25,.06,7)
  e3d(path,path.with_suffix('.png').name,harvest_shape)
 mapinfo=[]
 concept_root=Path(__file__).resolve().parents[1]/"concepts/nymara-regions"
 for idx,name in enumerate(allmaps):
  pool=interior if name in DUNGEONS else exterior
  profile=REGION_ART.get(name,REGION_ART[REGIONS[idx%len(REGIONS)]])
  picks=[pool[(idx*5+j)%len(pool)] for j in range(min(12,len(pool)))]
  placements=[]
  if name == 'four_gates':
   placements=four_gates_placements()
  elif name == 'mirrorhold':
   placements=mirrorhold_placements()
  elif name == 'crownwater':
   placements=crownwater_placements()
  elif name == 'whitehorn_range':
   placements=whitehorn_placements()
  elif name == 'amethyst_barrens':
   placements=amethyst_placements()
  elif name == 'sunmane_steppe':
   placements=sunmane_placements()
  elif name == 'amberwood':
   placements=amberwood_placements()
  elif name == 'grey_moors':
   placements=grey_moors_placements()
  elif name == 'westhaven':
   placements=westhaven_placements()
  elif name == 'verdant_stair':
   placements=verdant_placements()
  elif name == 'ssarathi_ruins':
   placements=ssarathi_placements()
  elif name == 'manymouth_delta':
   placements=manymouth_placements()
  elif name in REGIONS:
   raise ValueError(f"exterior region lacks an authored composition: {name}")
  elif name == 'drowned_crown':
   placements=drowned_crown_placements()
  elif name == 'whitehorn_glacier_temple':
   placements=whitehorn_temple_placements()
  elif name == 'resonant_vault':
   placements=resonant_vault_placements()
  elif name == 'amberwood_estate':
   placements=amberwood_estate_placements()
  elif name == 'grey_moor_barrows':
   placements=grey_moor_barrows_placements()
  elif name == 'ssarathi_royal_archive':
   placements=ssarathi_archive_placements()
  elif name == 'manymouth_flooded_labyrinth':
   placements=manymouth_labyrinth_placements()
  else:
   kit=INTERIOR_KITS[name]
   # Three connected chambers: arrival hall, cultural focal room, and deep
   # objective room. Walls leave wide collision-safe door openings.
   placements=[]
   for j,(x,y,rot) in enumerate(((28,24,0),(44,24,0),(72,24,0),(88,24,0),(28,92,180),(44,92,180),(72,92,180),(88,92,180),
                                  (22,40,90),(22,58,90),(22,78,90),(94,40,270),(94,58,270),(94,78,270),
                                  (48,46,90),(48,70,90),(68,46,90),(68,70,90))):
    placements.append((f"3dobjects/nymara/interiors/{kit[1]}.e3d",x,y,0,rot))
   for j,(x,y) in enumerate(((34,34),(82,34),(34,82),(82,82),(58,40),(58,58),(58,78),(42,58),(74,58))):
    asset=kit[2+j%(len(kit)-2)]
    placements.append((f"3dobjects/nymara/interiors/{asset}.e3d",x,y,0,(j*45)%360))
  if name in REGION_HARVESTS:
   for offset,resource in enumerate(REGION_HARVESTS[name]):
    x,y=((26,82),(48,84),(78,82),(98,76))[offset]
    placements.append((f"3dobjects/nymara/{resource}.e3d",x,y,0,(offset*41)%360))
    harvest_manifest.append({"map_id":name,"object_id":8+offset,"x":x,"y":y,"resource":resource})
  else:
   placements += [(str(pool[(idx*5+8+j)%len(pool)].relative_to(root)).replace('\\','/'),26+j*22,82,0,j*41) for j in range(4)]
  placements += [
   ("3dobjects/nymara/interactives/region_waygate.e3d",6,58,0,90),
   ("3dobjects/nymara/interactives/region_waygate.e3d",110,58,0,270),
   ("3dobjects/nymara/interactives/region_waygate.e3d",58,100,0,180),
   ("3dobjects/nymara/interactives/crystal_console.e3d",60,62,0,0),
   ("3dobjects/nymara/interactives/archive_lift.e3d",64,62,0,0),
   ("3dobjects/nymara/interactives/stormglass_rod.e3d",68,62,0,0)]
  lights=[(58,58,4,1.25,1.02,.72),(6,58,3,.35,.70,.78),(110,58,3,.35,.70,.78),(58,100,3,.48,.64,.78)]
  if name=='four_gates':
   lights += [(x,y,3.5,1.08,.72,.31) for x,y in
              ((42,52),(42,64),(52,42),(64,42),(74,52),(74,64),
               (52,74),(64,74),(34,58),(82,58),(58,34),(58,82))]
  elif name=='mirrorhold':
   lights += [(x,y,4.2,.42,.68,.92) for x,y in
              ((58,34),(42,34),(74,34),(50,48),(66,48),(42,58),(74,58),(38,92),(78,92))]
  elif name=='crownwater':
   lights += [(x,y,3.5,.88,.77,.38) for x,y in
              ((42,42),(74,42),(42,74),(74,74),(58,36),(36,58),(80,58),(58,80))]
  elif name=='whitehorn_range':
   lights += [(x,y,3.2,.52,.72,.94) for x,y in
              ((58,28),(42,38),(74,38),(38,62),(78,62),(42,92),(74,92),(58,102))]
  elif name=='amethyst_barrens':
   lights += [(x,y,3.8,.72,.36,.96) for x,y in
              ((58,34),(42,38),(74,38),(34,56),(82,56),(38,82),(78,82),(58,102))]
  elif name=='sunmane_steppe':
   lights += [(x,y,3.2,1.00,.58,.24) for x,y in
              ((48,48),(68,48),(48,68),(68,68),(58,34),(82,58),(58,82),(34,58))]
  elif name=='amberwood':
   lights += [(x,y,3.0,.96,.42,.16) for x,y in
              ((58,42),(48,48),(68,48),(48,68),(68,68),(34,34),(82,34),(58,88))]
  elif name=='grey_moors':
   lights += [(x,y,2.6,.42,.46,.62) for x,y in
              ((34,34),(82,34),(30,82),(86,82),(48,104),(68,104),(48,48),(68,68))]
  elif name=='westhaven':
   lights += [(x,y,3.4,.86,.68,.36) for x,y in
              ((24,34),(38,38),(54,38),(70,38),(86,38),(30,66),(62,66),(94,66))]
  elif name=='verdant_stair':
   lights += [(x,y,3.0,.28,.74,.52) for x,y in
              ((48,48),(68,48),(44,76),(72,76),(58,100),(30,34),(86,38),(58,24))]
  elif name=='ssarathi_ruins':
   lights += [(x,y,3.0,.25,.74,.62) for x,y in
              ((58,28),(48,48),(68,48),(42,72),(74,72),(58,92),(32,32),(84,32))]
  elif name=='manymouth_delta':
   lights += [(x,y,2.8,.32,.66,.45) for x,y in
              ((38,34),(58,32),(78,36),(32,58),(54,56),(78,60),(38,82),(60,80))]
  elif name=='drowned_crown':
   lights += [(x,y,2.7,.24,.70,.78) for x,y in
              ((34,34),(58,34),(82,34),(34,58),(82,58),(34,82),(58,82),(82,82))]
  elif name=='whitehorn_glacier_temple':
   lights += [(x,y,3.1,.56,.78,.92) for x,y in
              ((34,34),(58,34),(82,34),(34,58),(82,58),(34,82),(58,82),(82,82))]
  elif name=='resonant_vault':
   lights += [(x,y,3.0,.58,.34,.88) for x,y in
              ((42,32),(74,32),(42,56),(74,56),(42,80),(74,80),(48,96),(68,96))]
  elif name=='amberwood_estate':
   lights += [(x,y,2.8,.92,.48,.20) for x,y in
              ((34,34),(58,34),(82,34),(34,58),(82,58),(34,82),(58,82),(82,82))]
  elif name=='grey_moor_barrows':
   lights += [(x,y,2.5,.34,.46,.48) for x,y in
              ((34,34),(58,34),(82,34),(34,58),(82,58),(34,82),(58,82),(82,82))]
  elif name=='ssarathi_royal_archive':
   lights += [(x,y,2.8,.28,.72,.58) for x,y in
              ((34,34),(58,34),(82,34),(34,58),(82,58),(34,82),(58,82),(82,82))]
  elif name=='manymouth_flooded_labyrinth':
   lights += [(x,y,2.6,.24,.58,.48) for x,y in
              ((34,34),(58,34),(82,34),(34,58),(82,58),(34,82),(58,82),(82,82))]
  tile_function=(four_gates_tile if name=='four_gates' else mirrorhold_tile if name=='mirrorhold' else crownwater_tile if name=='crownwater' else whitehorn_tile if name=='whitehorn_range' else amethyst_tile if name=='amethyst_barrens' else sunmane_tile if name=='sunmane_steppe' else amberwood_tile if name=='amberwood' else grey_moors_tile if name=='grey_moors' else westhaven_tile if name=='westhaven' else verdant_tile if name=='verdant_stair' else ssarathi_tile if name=='ssarathi_ruins' else manymouth_tile if name=='manymouth_delta'
                 else lambda x,y,p=profile,n=name:region_tile(p,n,x,y))
  height_function=(four_gates_height if name=='four_gates' else mirrorhold_height if name=='mirrorhold' else crownwater_height if name=='crownwater' else whitehorn_height if name=='whitehorn_range' else amethyst_height if name=='amethyst_barrens' else sunmane_height if name=='sunmane_steppe' else amberwood_height if name=='amberwood' else grey_moors_height if name=='grey_moors' else westhaven_height if name=='westhaven' else verdant_height if name=='verdant_stair' else ssarathi_height if name=='ssarathi_ruins' else manymouth_height if name=='manymouth_delta'
                   else lambda x,y,p=profile,n=name:region_height(p,n,x,y))
  make_map(root/f"maps/nymara/{name}.elm",width=32,height=32,placements=placements,
   ambient=profile['ambient'],lights=lights,
   tile_at=tile_function,height_at=height_function)
  concept=concept_root/f"{name}_region_concept.png"
  if name == 'four_gates': dds_mipped(root/f"maps/nymara/{name}.dds",512,512,four_gates_cartography_pixel)
  elif concept.is_file(): concept_dds(concept,root/f"maps/nymara/{name}.dds")
  else: dds_mipped(root/f"maps/nymara/{name}.dds",512,512,cartography_pixel(name,profile))
  mapinfo.append(f"{name}|{name.replace('_',' ').title()}|maps/nymara/{name}.elm|maps/nymara/{name}.dds")
  regions.append({"id":name,"title":name.replace('_',' ').title(),"map":f"maps/nymara/{name}.elm","arrival":[58,58],"npc_hook":f"npcs.nymara.{name}","spawn_hook":f"spawns.nymara.{name}","hazard_hook":f"hazards.nymara.{name}","harvest_hook":f"harvest.nymara.{name}"})
 for a,b in zip(REGIONS,REGIONS[1:]): connections.append({"from":a,"to":b,"from_xy":[110,58],"to_xy":[6,58],"type":"walk"})
 for d in DUNGEONS: connections.append({"from":REGIONS[DUNGEONS.index(d)%len(REGIONS)],"to":d,"from_xy":[58,100],"to_xy":[58,10],"type":"entrance"})
 data={"schema":1,"regions":regions,"connections":connections,"ferries":[{"from":"crownwater","to":"four_gates","service":"crownwater_ferry"},{"from":"manymouth_delta","to":"westhaven","service":"delta_ferry"}]}
 (root/"nymara_regions_connections.json").write_text(json.dumps(data,indent=2)+"\n")
 (root/"nymara_harvesting.json").write_text(json.dumps({"schema":1,"nodes":harvest_manifest},indent=2)+"\n")
 bootstrap=("emberhaven","glasswind","frostmere","mirefen","verdant_reach","cinder_wastes")
 configured=[f"{n}|{n.replace('_',' ').title()}|maps/{n}.elm|maps/legend.dds" for n in bootstrap]
 configured += mapinfo
 configured += ["nomap|No Map|maps/nomap.elm|maps/legend.dds",
                "newcharactermap|Character Preview|maps/newcharactermap.elm|maps/legend.dds"]
 (root/"mapinfo.lst").write_text("\n".join(configured)+"\n")
 # The overview is deliberately generated from the same regional palettes so
 # it remains reproducible while matching every local map's visual language.
 def continent(x,y):
  col=min(3,x*4//512); row=min(2,y*3//512); n=REGIONS[row*4+col]; p=REGION_ART[n]
  lx=(x%128)*4; ly=(y%171)*3
  return cartography_pixel(n,p)(lx,ly)
 master=concept_root/"nymara_continent_master_concept.png"
 if master.is_file(): concept_dds(master,root/"maps/nymara_continent.dds")
 else: dds_mipped(root/"maps/nymara_continent.dds",512,512,continent)
 (root/"continfo.lst").write_text("Nymara|maps/nymara_continent.dds\n")
 return data

def merge_existing(root, source):
 # Preserve the handoff pack's registered runtime paths verbatim.
 for pack in ("nymara-client-assets", "nymara-interior-assets"):
  runtime=source/pack/"runtime"
  for child in runtime.iterdir():
   if child.is_dir(): shutil.copytree(child,root/child.name,dirs_exist_ok=True)
   else: shutil.copy2(child,root/child.name)
 # Normalize legacy handoff materials to the production 256px contract.  The
 # native source remains in the pack; this prevents mixed texel density at run time.
 for path in (root/"3dobjects/nymara").rglob("*.png"):
  width,height,sample=png_pixels(path)
  if (width,height)!=(256,256):
   png(path,256,256,lambda x,y,w=width,h=height,s=sample:s(min(w-1,x*w//256),min(h-1,y*h//256)))

def main():
 p=argparse.ArgumentParser(); p.add_argument("output",nargs="?",default="build/eloria-data"); p.add_argument("--handoff-root",default=None); a=p.parse_args(); root=Path(a.output)
 source=Path(a.handoff_root) if a.handoff_root else Path(__file__).resolve().parents[1]/"nymara-packs"
 merge_existing(root,source)
 actor_file=root/"actor_defs/actor_defs.xml"; actors=ET.parse(actor_file).getroot()
 for old in list(actors.findall("actor")):
  if 300 <= int(old.attrib.get("id", "-1")) < 500: actors.remove(old)
 npcs=generate_npcs(root,actors); creatures=generate_creatures(root,actors); equipment=generate_equipment(root); effects=generate_interactives_effects(root); regions=generate_maps(root)
 actor_file.write_text('<?xml version="1.0"?>\n'+ET.tostring(actors,encoding="unicode")+'\n')
 allocation={"schema":1,"frozen":True,"actor_ranges":{"nymara_npcs":[NPC_BASE,NPC_BASE+len(npcs)-1],"nymara_creatures":[CREATURE_BASE,CREATURE_BASE+len(creatures)-1]},"item_ranges":{"nymara_equipment":[ITEM_BASE,ITEM_BASE+len(equipment)-1]},"interactive_ranges":{"nymara_interactives":[2000,2000+len(effects['interactives'])-1]},"effect_ranges":{"nymara_particles":[2100,2100+len(effects['particles'])-1]},"missile_ranges":{"nymara_projectiles":[2200,2200+len(effects['missiles'])-1]}}
 (root/"nymara_id_allocations.json").write_text(json.dumps(allocation,indent=2)+"\n")
 manifest={"schema":1,"name":"Nymara complete independent client pack","license":"CC-BY-4.0","contains_eternal_lands_binary_data":False,"counts":{"npcs":len(npcs),"creatures":len(creatures),"equipment":len(equipment),"interactives":len(effects['interactives']),"particles":len(effects['particles']),"projectiles":len(effects['missiles']),"regions":len(REGIONS),"dungeons":len(DUNGEONS)},"generators":["eloria-assets/tools/generate_nymara_complete.py"],"functional_proxy":True}
 (root/"NYMARA_MANIFEST.json").write_text(json.dumps(manifest,indent=2)+"\n")
 catalog={"schema":1,"objects":[{"object_id":5000+i,"label":q.stem.replace('_',' ').title(),"path":str(q.relative_to(root)).replace('\\','/'),"category":"Nymara/Interiors" if "/interiors/" in str(q).replace('\\','/') else "Nymara/Equipment" if "/equipment/" in str(q).replace('\\','/') else "Nymara/World"} for i,q in enumerate(sorted((root/"3dobjects/nymara").rglob("*.e3d")))],"maps":[{"label":q.stem.replace('_',' ').title(),"path":str(q.relative_to(root)).replace('\\','/')} for q in sorted((root/"maps/nymara").glob("*.elm"))]}
 (root/"nymara_map_editor_catalog.json").write_text(json.dumps(catalog,indent=2)+"\n")

if __name__=="__main__": main()

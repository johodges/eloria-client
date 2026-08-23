#!/usr/bin/env python3
"""Generate the original Nymara actors, creatures, equipment, effects and maps.

All geometry and pixels are deterministic procedural production proxies.  No
Eternal Lands binary-data input is read or required.
"""
from __future__ import annotations
import argparse, json, math, shutil
from pathlib import Path
import xml.etree.ElementTree as ET

from generate_bootstrap_pack import png, make_map
from generate_characters import skeleton as humanoid_skeleton
from generate_humanoid_enemies import enemy_mesh
from generate_creatures import skeleton as creature_skeleton, creature_mesh
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
    slug=f"{culture}_{role}_{variant}"; feature="armor" if any(x in role for x in ("guard","warrior","militia","guardian")) else "crown" if any(x in role for x in ("priest","official","council","elder")) else "hood"
    enemy_mesh(base/f"{slug}.xmf",feature,.96 if variant=="f" else 1.0)
    png(base/f"{slug}.png",256,256,checker(primary,accent)); png(root/f"portraits/nymara/npcs/{slug}.png",128,128,checker(accent,primary))
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
  png(base/f"{slug}.png",256,256,checker(c,c2)); png(root/f"portraits/nymara/creatures/{slug}.png",128,128,checker(c2,c))
  radius=round(max(body[0],body[1])*.42,2); bounds=(-body[0]/2,-body[1]/2,0,body[0]/2,body[1]/2,1.6)
  append_actor(actors,aid,label,"nymara_creature","actors/nymara/creatures/nymara_creature.xsf",f"actors/nymara/creatures/{slug}.xmf",f"actors/nymara/creatures/{slug}.png","animations/nymara/creatures",radius,1.0,bounds,True)
  out.append({"actor_type":aid,"id":slug,"name":label,"region":region,"portrait":f"portraits/nymara/creatures/{slug}.png","collision_radius":radius,"bounds":bounds,"sound_events":{x:f"nymara.{slug}.{x}" for x in ("idle","attack","pain","death")},"drop_table_hook":f"drops.nymara.{slug}","summoning_hook":f"summon.nymara.{slug}"})
 (root/"nymara_creatures.json").write_text(json.dumps({"schema":1,"creatures":out},indent=2)+"\n"); return out

def equipment_shape(kind):
 def build(v,i):
  if any(x in kind for x in ("blade","sabre","cutlass")): box(v,i,(0,0,1.1),(.13,.10,2.2)); tapered(v,i,2.1,2.65,.18,0,4)
  elif any(x in kind for x in ("spear","pike","staff","focus")): box(v,i,(0,0,1.5),(.10,.10,3)); tapered(v,i,2.9,3.35,.28,0,6)
  elif "shield" in kind: tapered(v,i,0,1.6,.72,.72,12); box(v,i,(0,.12,.8),(.12,.15,1.6))
  elif any(x in kind for x in ("mail","armor","leathers")): box(v,i,(0,0,1.25),(.62,.32,.78)); box(v,i,(0,0,.78),(.54,.30,.34))
  elif any(x in kind for x in ("cape","mantle")): box(v,i,(0,.16,1.15),(.72,.08,1.65))
  else: box(v,i,(0,0,.65),(.35,.22,1.3)); tapered(v,i,1.25,1.65,.28,0,6)
 return build

def generate_equipment(root):
 out=[]; colors={"luminous":((66,151,160),(208,193,132)),"votary":((158,190,204),(222,230,229)),"glasswarden":((113,76,151),(190,142,67)),"orun":((167,91,43),(46,137,143)),"greyhaven":((55,78,93),(151,127,82)),"ssarathi":((47,112,77),(184,151,67))}
 for i,(culture,name) in enumerate(EQUIPMENT):
  iid=ITEM_BASE+i; model=root/f"3dobjects/nymara/equipment/{culture}/{name}.e3d"; texture(model.with_suffix('.png'),colors[culture]); e3d(model,model.with_suffix('.png').name,equipment_shape(name))
  png(root/f"textures/nymara/items/{name}.png",64,64,lambda x,y,c=colors[culture]: (*c[0],max(0,255-int(math.hypot(x-32,y-32)*7))) if math.hypot(x-32,y-32)<30 else (0,0,0,0))
  slot="weapon" if any(x in name for x in ("blade","sabre","cutlass","spear","pike","bow","hammer","pick","adze","staff")) else "shield" if "shield" in name else "body" if any(x in name for x in ("mail","armor","leathers")) else "cape" if any(x in name for x in ("cape","mantle")) else "neck"
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
   if any(word in name for word in ("reed","orchid","lotus","moss","bulb","silverleaf")):
    crossed_leaves(vertices,indices,0,1.15,.72,4)
   elif any(word in name for word in ("crystal","shard","geode","salt","pearl")):
    tapered(vertices,indices,0,1.05,.42,.08,7)
    tapered(vertices,indices,0,.72,.28,.04,6,center=(.35,.08))
   else:
    box(vertices,indices,(0,0,.25),(.72,.62,.50))
    tapered(vertices,indices,.42,.88,.25,.06,7)
  e3d(path,path.with_suffix('.png').name,harvest_shape)
 for idx,name in enumerate(allmaps):
  pool=interior if name in DUNGEONS else exterior; picks=[pool[(idx*5+j)%len(pool)] for j in range(min(8,len(pool)))]
  placements=[(str(p.relative_to(root)).replace('\\','/'),24+(j%4)*22,26+(j//4)*22,0,(j*37)%360) for j,p in enumerate(picks)]
  if name in REGION_HARVESTS:
   for offset,resource in enumerate(REGION_HARVESTS[name]):
    x,y=((26,82),(48,84),(78,82),(98,76))[offset]
    placements.append((f"3dobjects/nymara/{resource}.e3d",x,y,0,(offset*41)%360))
    harvest_manifest.append({"map_id":name,"object_id":8+offset,"x":x,"y":y,"resource":resource})
  else:
   placements += [(str(pool[(idx*5+8+j)%len(pool)].relative_to(root)).replace('\\','/'),26+j*22,82,0,j*41) for j in range(4)]
  placements += [
   ("3dobjects/nymara/interactives/region_waygate.e3d",58,58,0,0),
   ("3dobjects/nymara/interactives/crystal_console.e3d",60,62,0,0),
   ("3dobjects/nymara/interactives/archive_lift.e3d",64,62,0,0),
   ("3dobjects/nymara/interactives/stormglass_rod.e3d",68,62,0,0)]
  make_map(root/f"maps/nymara/{name}.elm",width=32,height=32,tile_id=0,placements=placements,ambient=(.50,.58,.61))
  regions.append({"id":name,"title":name.replace('_',' ').title(),"map":f"maps/nymara/{name}.elm","arrival":[58,58],"npc_hook":f"npcs.nymara.{name}","spawn_hook":f"spawns.nymara.{name}","hazard_hook":f"hazards.nymara.{name}","harvest_hook":f"harvest.nymara.{name}"})
 for a,b in zip(REGIONS,REGIONS[1:]): connections.append({"from":a,"to":b,"from_xy":[110,58],"to_xy":[6,58],"type":"walk"})
 for d in DUNGEONS: connections.append({"from":REGIONS[DUNGEONS.index(d)%len(REGIONS)],"to":d,"from_xy":[58,100],"to_xy":[58,10],"type":"entrance"})
 data={"schema":1,"regions":regions,"connections":connections,"ferries":[{"from":"crownwater","to":"four_gates","service":"crownwater_ferry"},{"from":"manymouth_delta","to":"westhaven","service":"delta_ferry"}]}
 (root/"nymara_regions_connections.json").write_text(json.dumps(data,indent=2)+"\n")
 (root/"nymara_harvesting.json").write_text(json.dumps({"schema":1,"nodes":harvest_manifest},indent=2)+"\n")
 return data

def merge_existing(root, source):
 # Preserve the handoff pack's registered runtime paths verbatim.
 for pack in ("nymara-client-assets", "nymara-interior-assets"):
  runtime=source/pack/"runtime"
  for child in runtime.iterdir():
   if child.is_dir(): shutil.copytree(child,root/child.name,dirs_exist_ok=True)
   else: shutil.copy2(child,root/child.name)

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

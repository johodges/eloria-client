#!/usr/bin/env python3
"""Structural and reference validator for generated Nymara client data."""
from __future__ import annotations
import argparse, json, struct, sys
from pathlib import Path
import xml.etree.ElementTree as ET

SUPPORTED_FRAMES = {
 "CAL_walk","CAL_run","CAL_die1","CAL_die2","CAL_pain1","CAL_pain2",
 "CAL_pick","CAL_drop","CAL_idle","CAL_idle2","CAL_idle_sit","CAL_harvest",
 "CAL_attack_cast","CAL_sit_down","CAL_stand_up","CAL_in_combat",
 "CAL_out_combat","CAL_combat_idle",
 *{f"CAL_attack_up_{i}" for i in range(1,11)},
 *{f"CAL_attack_down_{i}" for i in range(1,11)},
}

def main():
 p=argparse.ArgumentParser(); p.add_argument("root",nargs="?",default="build/eloria-data"); p.add_argument("--report",default=None); a=p.parse_args(); root=Path(a.root)
 errors=[]; checks={"xml":0,"json":0,"png":0,"e3d":0,"elm":0,"references":0,"ids":0}
 def err(path,msg): errors.append(f"{path}: {msg}")
 for f in root.rglob("*.xml"):
  try: ET.parse(f); checks["xml"]+=1
  except Exception as e: err(f,e)
 for f in root.rglob("*.json"):
  try: json.loads(f.read_text()); checks["json"]+=1
  except Exception as e: err(f,e)
 for f in root.rglob("*.png"):
  b=f.read_bytes()[:24]
  if len(b)<24 or b[:8]!=b"\x89PNG\r\n\x1a\n": err(f,"invalid PNG signature/header")
  else:
   w,h=struct.unpack(">II",b[16:24]); checks["png"]+=1
   if not w or not h: err(f,"zero dimensions")
 for f in (root/"3dobjects/nymara").rglob("*.e3d"):
  if f.read_bytes()[:4]!=b"e3dx": err(f,"invalid E3D magic")
  else: checks["e3d"]+=1
 for f in (root/"maps/nymara").glob("*.elm"):
  b=f.read_bytes()
  if len(b)<120 or b[:4]!=b"elmf": err(f,"invalid ELM header")
  else:
   w,h=struct.unpack_from("<2i",b,4); checks["elm"]+=1
   if not w or not h: err(f,"zero map dimensions")
 actors=ET.parse(root/"actor_defs/actor_defs.xml").getroot(); ids=[]
 for ael in actors.findall("actor"):
  aid=int(ael.attrib["id"]); ids.append(aid)
  if 300<=aid<500:
   for tag in ("skeleton","mesh","skin"):
    q=root/(ael.findtext(tag) or "")
    if not q.is_file(): err(q,f"missing actor {aid} {tag}")
    else: checks["references"]+=1
   for fr in ael.findall("./frames/*"):
    if fr.tag not in SUPPORTED_FRAMES and not fr.tag.casefold().startswith("cal_emote"):
     err(actor_file,f"unsupported frame tag {fr.tag} for actor {aid}")
    q=root/(fr.text or "")
    if not q.is_file(): err(q,f"missing animation for actor {aid}")
    else: checks["references"]+=1
 if len(ids)!=len(set(ids)): err("actor_defs.xml","duplicate actor IDs")
 allocation=json.loads((root/"nymara_id_allocations.json").read_text())
 ranges=[]
 for group in allocation.values():
  if isinstance(group,dict): ranges.extend(tuple(v) for v in group.values() if isinstance(v,list) and len(v)==2)
 for i,x in enumerate(ranges):
  for y in ranges[i+1:]:
   if max(x[0],y[0])<=min(x[1],y[1]): err("nymara_id_allocations.json",f"overlap {x} {y}")
 checks["ids"]=sum(b-a+1 for a,b in ranges)
 expected=json.loads((root/"NYMARA_MANIFEST.json").read_text())["counts"]
 actual={"npcs":len(json.loads((root/"nymara_npcs.json").read_text())["npcs"]),"creatures":len(json.loads((root/"nymara_creatures.json").read_text())["creatures"]),"equipment":len(json.loads((root/"nymara_equipment.json").read_text())["items"]),"regions":len([x for x in (root/"maps/nymara").glob("*.elm") if x.stem not in {"drowned_crown","whitehorn_glacier_temple","resonant_vault","amberwood_estate","grey_moor_barrows","ssarathi_royal_archive","manymouth_flooded_labyrinth"}]),"dungeons":len([x for x in (root/"maps/nymara").glob("*.elm") if x.stem in {"drowned_crown","whitehorn_glacier_temple","resonant_vault","amberwood_estate","grey_moor_barrows","ssarathi_royal_archive","manymouth_flooded_labyrinth"}])}
 for k,v in actual.items():
  if expected[k]!=v: err("NYMARA_MANIFEST.json",f"{k}: expected {expected[k]}, got {v}")
 report={"schema":1,"passed":not errors,"checks":checks,"counts":expected,"errors":errors,"limitations":["Procedural low-poly actors, creatures, equipment, effects, and maps are functional production proxies.","Actual OpenGL client render validation was not available in this container.","Windows runtime validation remains required."]}
 out=Path(a.report) if a.report else root/"NYMARA_VALIDATION_REPORT.json"; out.write_text(json.dumps(report,indent=2)+"\n")
 print(json.dumps(report,indent=2)); return 0 if not errors else 1
if __name__=="__main__": raise SystemExit(main())

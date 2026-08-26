#!/usr/bin/env python3
"""Generate the tiny CC0/public-domain-equivalent loader test fixture."""
import json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/"tests/fixtures/world_package"
def pad(b,fill=b"\0"): return b+fill*((4-len(b)%4)%4)
def main():
 ROOT.mkdir(parents=True,exist_ok=True)
 # Plane plus upright alpha-masked triangle. The plane mesh is instanced twice.
 positions=[(-1,0,-1),(1,0,-1),(1,0,1),(-1,0,1),(0,0,0),(0,2,0),(1,0,0)]
 normals=[(0,1,0)]*4+[(0,0,1)]*3
 uvs=[(0,0),(1,0),(1,1),(0,1),(0,0),(0.5,1),(1,0)]
 colors=[(0.7,0.9,0.7,1)]*4+[(1,1,1,0.7)]*3
 indices=[0,1,2,0,2,3,4,5,6]
 blob=b"".join(struct.pack("<3f",*v) for v in positions)
 offsets=[0];blob=pad(blob);offsets.append(len(blob));blob+=b"".join(struct.pack("<3f",*v) for v in normals)
 blob=pad(blob);offsets.append(len(blob));blob+=b"".join(struct.pack("<2f",*v) for v in uvs)
 blob=pad(blob);offsets.append(len(blob));blob+=b"".join(struct.pack("<4f",*v) for v in colors)
 blob=pad(blob);offsets.append(len(blob));blob+=struct.pack("<9H",*indices);blob=pad(blob)
 views=[{"buffer":0,"byteOffset":offsets[0],"byteLength":len(positions)*12},{"buffer":0,"byteOffset":offsets[1],"byteLength":len(normals)*12},{"buffer":0,"byteOffset":offsets[2],"byteLength":len(uvs)*8},{"buffer":0,"byteOffset":offsets[3],"byteLength":len(colors)*16},{"buffer":0,"byteOffset":offsets[4],"byteLength":18}]
 acc=[{"bufferView":0,"componentType":5126,"count":7,"type":"VEC3"},{"bufferView":1,"componentType":5126,"count":7,"type":"VEC3"},{"bufferView":2,"componentType":5126,"count":7,"type":"VEC2"},{"bufferView":3,"componentType":5126,"count":7,"type":"VEC4"},{"bufferView":4,"componentType":5123,"count":6,"type":"SCALAR","byteOffset":0},{"bufferView":4,"componentType":5123,"count":3,"type":"SCALAR","byteOffset":12}]
 attrs={"POSITION":0,"NORMAL":1,"TEXCOORD_0":2,"COLOR_0":3}
 gltf={"asset":{"version":"2.0","generator":"Eloria fixture generator"},"buffers":[{"byteLength":len(blob)}],"bufferViews":views,"accessors":acc,
  "materials":[{"name":"ground","pbrMetallicRoughness":{"baseColorFactor":[0.6,0.8,0.6,1]}},{"name":"marker","alphaMode":"MASK","alphaCutoff":0.5,"doubleSided":True,"pbrMetallicRoughness":{"baseColorFactor":[0.3,0.8,1,0.7]}}],
  "meshes":[{"name":"ground","primitives":[{"attributes":attrs,"indices":4,"material":0}]},{"name":"marker","primitives":[{"attributes":attrs,"indices":5,"material":1}]}],
  "nodes":[{"name":"root","translation":[4,0,-5],"children":[1,2,3]},{"name":"ground_a","mesh":0},{"name":"ground_b","mesh":0,"translation":[2,0,0]},{"name":"nested","translation":[0,0,-2],"children":[4]},{"name":"marker","mesh":1,"translation":[0,0,1]}],"scenes":[{"nodes":[0]}],"scene":0}
 js=pad(json.dumps(gltf,separators=(",",":")).encode(),b" ")
 (ROOT/"world.glb").write_bytes(struct.pack("<III",0x46546C67,2,12+8+len(js)+8+len(blob))+struct.pack("<II",len(js),0x4E4F534A)+js+struct.pack("<II",len(blob),0x004E4942)+blob)
 (ROOT/"collision.bin").write_bytes(b"EWCG"+struct.pack("<HHII",1,0,12,12)+bytes([1]*144))
 manifest={"format":"eloria-world","version":1,"id":"fixture","display_name":"Portable World Fixture","scene":"world.glb","collision":"collision.bin","collision_width":12,"collision_height":12,
  "coordinates":{"units_per_meter":1,"up_axis":"Y","forward_axis":"-Z","origin":[0,0,0]},"bounds":{"minimum":[0,-1,0],"maximum":[6,3,6]},"environment":{"ambient_color":[0.6,0.65,0.75],"ambient_intensity":1},
  "player_starts":[{"id":"default","position":[4,0,-5],"rotation_degrees":0}],"portals":[{"id":"fixture_exit","position":[4,0,-7]}],"harvestables":[],"npc_markers":[],"spawn_markers":[],"regions":[]}
 (ROOT/"world.json").write_text(json.dumps(manifest,indent=2)+"\n")
if __name__=="__main__":main()

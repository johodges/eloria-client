import importlib.machinery, importlib.util, json, struct, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
loader=importlib.machinery.SourceFileLoader("validator",str(ROOT/"tools/eloria-map-validate"))
spec=importlib.util.spec_from_loader(loader.name,loader); validator=importlib.util.module_from_spec(spec);loader.exec_module(validator)
def package(root,version=1,scene=True,collision=True,path="world.glb"):
    manifest={"format":"eloria-world","version":version,"id":"fixture","scene":path,"collision":"collision.bin",
      "bounds":{"minimum":[0,0,0],"maximum":[3,1,3]},"collision_width":6,"collision_height":6,
      "coordinates":{"units_per_meter":1,"up_axis":"Y","forward_axis":"-Z","origin":[0,0,0]},
      "player_starts":[{"id":"default","position":[1,0,-2]}],"portals":[{"id":"exit","position":[2,0,-1]}]}
    (root/"world.json").write_text(json.dumps(manifest))
    if scene:
        doc=json.dumps({"asset":{"version":"2.0"},"buffers":[{"byteLength":36}],"bufferViews":[{"buffer":0,"byteOffset":0,"byteLength":36}],"accessors":[{"bufferView":0,"componentType":5126,"count":3,"type":"VEC3"}],"meshes":[{"primitives":[{"attributes":{"POSITION":0}}]}],"nodes":[{"mesh":0},{"mesh":0}],"scenes":[{"nodes":[0,1]}],"scene":0}).encode()
        doc+=b" " * ((4-len(doc)%4)%4)
        binary=bytes(36);(root/"world.glb").write_bytes(struct.pack("<III",0x46546C67,2,28+len(doc)+len(binary))+struct.pack("<II",len(doc),0x4E4F534A)+doc+struct.pack("<II",len(binary),0x004E4942)+binary)
    if collision:(root/"collision.bin").write_bytes(b"EWCG"+struct.pack("<HHII",1,0,6,6)+bytes(36))
    return root/"world.json"
def minimap(root,mips=4):
    width=height=512;header=[124,0x0002100F,height,width,width*4,0,mips]+[0]*11+[32,0x41,0,32,0x00FF0000,0x0000FF00,0x000000FF,0xFF000000]+[0x401008,0,0,0,0]
    payload=bytes(sum(max(1,width>>level)*max(1,height>>level)*4 for level in range(mips)))
    (root/"map.dds").write_bytes(b"DDS "+struct.pack("<31I",*header)+payload)
class Validation(unittest.TestCase):
    def test_minimal_and_reused_mesh(self):
        with tempfile.TemporaryDirectory() as d:
            data,glb,w,h=validator.validate(package(Path(d)));self.assertEqual((w,h),(6,6));self.assertEqual(len(glb["nodes"]),2)
    def test_missing_glb(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(validator.Invalid,"missing"):validator.validate(package(Path(d),scene=False))
    def test_bad_json(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"world.json";p.write_text("{")
            with self.assertRaisesRegex(validator.Invalid,"invalid JSON"):validator.validate(p)
    def test_unsupported_version(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(validator.Invalid,"unsupported"):validator.validate(package(Path(d),version=2))
    def test_path_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(validator.Invalid,"unsafe"):validator.validate(package(Path(d),path="../world.glb"))
    def test_collision_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            p=package(Path(d));(Path(d)/"collision.bin").write_bytes(b"EWCG"+struct.pack("<HHII",1,0,12,6)+bytes(72))
            with self.assertRaisesRegex(validator.Invalid,"mismatch"):validator.validate(p)
    def test_invalid_accessor_range(self):
        with tempfile.TemporaryDirectory() as d:
            p=package(Path(d)); raw=(Path(d)/"world.glb").read_bytes(); raw=raw.replace(b'"byteLength": 36',b'"byteLength": 99',1); (Path(d)/"world.glb").write_bytes(raw)
            with self.assertRaisesRegex(validator.Invalid,"range|buffer"):validator.validate(p)
    def test_coordinate_examples(self):
        def convert(p,u,o):return(o[0]+p[0]/u,o[1]-p[2]/u,o[2]+p[1]/u)
        self.assertEqual(convert((4,2,-8),2,(10,20,30)),(12,24,31))
    def test_four_mip_minimap(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=package(root);minimap(root);data=json.loads(p.read_text());data["minimap"]="map.dds";p.write_text(json.dumps(data));validator.validate(p)
            minimap(root,mips=3)
            with self.assertRaisesRegex(validator.Invalid,"four mip"):validator.validate(p)
    def test_waterfall_nodes_must_exist(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=package(root);data=json.loads(p.read_text());data["effects"]={"waterfalls":[{"id":"falls","position":[0,0,0],"channel_node":"missing","pool_node":"missing","foam_node":"missing","mist_node":"missing"}]};p.write_text(json.dumps(data))
            with self.assertRaisesRegex(validator.Invalid,"missing GLB node"):validator.validate(p)
    def test_external_scene_image_must_exist(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=package(root);raw=(root/"world.glb").read_bytes();jl=struct.unpack_from("<I",raw,12)[0];doc=json.loads(raw[20:20+jl]);doc["images"]=[{"uri":"textures/missing.png"}];jb=json.dumps(doc).encode();jb+=b" "*((-len(jb))%4);binary=raw[20+jl+8:];(root/"world.glb").write_bytes(struct.pack("<III",0x46546C67,2,28+len(jb)+len(binary))+struct.pack("<II",len(jb),0x4E4F534A)+jb+struct.pack("<II",len(binary),0x004E4942)+binary)
            with self.assertRaisesRegex(validator.Invalid,"referenced image is missing"):validator.validate(p)
if __name__=="__main__":unittest.main()

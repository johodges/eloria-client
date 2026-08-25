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
        doc=json.dumps({"asset":{"version":"2.0"},"meshes":[{"primitives":[{"attributes":{"POSITION":0}}]}],"nodes":[{"mesh":0},{"mesh":0}],"scenes":[{"nodes":[0,1]}],"scene":0}).encode()
        doc+=b" " * ((4-len(doc)%4)%4)
        (root/"world.glb").write_bytes(struct.pack("<III",0x46546C67,2,20+len(doc))+struct.pack("<II",len(doc),0x4E4F534A)+doc)
    if collision:(root/"collision.bin").write_bytes(b"EWCG"+struct.pack("<HHII",1,0,6,6)+bytes(36))
    return root/"world.json"
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
    def test_coordinate_examples(self):
        def convert(p,u,o):return(o[0]+p[0]/u,o[1]-p[2]/u,o[2]+p[1]/u)
        self.assertEqual(convert((4,2,-8),2,(10,20,30)),(12,24,31))
if __name__=="__main__":unittest.main()

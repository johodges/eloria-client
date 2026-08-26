import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WorldRuntimeContracts(unittest.TestCase):
    def test_portable_minimap_does_not_use_handle_truthiness(self):
        source = (ROOT / "minimap.c").read_text(encoding="utf-8")
        self.assertIn("static int minimap_texture_available = 0;", source)
        self.assertIn("if (!minimap_texture_available)", source)
        self.assertNotIn("if(!minimap_texture) \n\t{", source)

    def test_glb_binding_is_not_shared_with_hud_texture_state(self):
        source = (ROOT / "world_glb_renderer.cpp").read_text(encoding="utf-8")
        self.assertIn("bind_texture_unbuffered(p.tex)", source)
        self.assertNotIn("bind_texture(p.tex)", source)
        self.assertIn("last_texture=-1", source)

    def test_reported_spawn_neighbourhood_is_walkable(self):
        script = ROOT / "eloria-assets/tools/package_four_gates_world.py"
        spec = importlib.util.spec_from_file_location("four_gates_package", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        metadata = json.loads(module.METADATA.read_text(encoding="utf-8"))
        obstacles = [
            obstacle for obstacle in metadata["navigation"]["navmesh"]["obstacles"]
            if "Window" not in obstacle["node"]
        ]
        for center in ((763, 688), (768, 717)):
            with self.subTest(center=center):
                for y in range(center[1] - 2, center[1] + 3):
                    for x in range(center[0] - 2, center[0] + 3):
                        source_x, source_z = module.source_xz(x, y)
                        height = module.walkable_height(source_x, source_z, obstacles)
                        self.assertGreater(module.encode_height(height), 0)


if __name__ == "__main__":
    unittest.main()

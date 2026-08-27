import importlib.util
import json
import struct
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


    def test_packaged_winding_agrees_with_authored_normals(self):
        script = ROOT / "eloria-assets/tools/package_four_gates_world.py"
        spec = importlib.util.spec_from_file_location("four_gates_winding", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        raw = module.correct_winding_indices(module.SOURCE.read_bytes())
        json_length = struct.unpack_from("<I", raw, 12)[0]
        document = json.loads(raw[20:20 + json_length])
        binary_offset = 20 + json_length + 8

        widths = {5121: 1, 5123: 2, 5125: 4, 5126: 4}
        counts = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}

        def accessor(index):
            item = document["accessors"][index]
            view = document["bufferViews"][item["bufferView"]]
            width = widths[item["componentType"]]
            stride = view.get("byteStride", width * counts[item["type"]])
            start = binary_offset + view.get("byteOffset", 0) + item.get("byteOffset", 0)
            return item, start, stride

        def vector(index, element):
            _, start, stride = accessor(index)
            return struct.unpack_from("<3f", raw, start + element * stride)

        def index_value(index, element):
            item, start, stride = accessor(index)
            fmt = {5121: "B", 5123: "H", 5125: "I"}[item["componentType"]]
            return struct.unpack_from("<" + fmt, raw, start + element * stride)[0]

        for mesh in document["meshes"]:
            for primitive in mesh["primitives"]:
                if "indices" not in primitive or "NORMAL" not in primitive["attributes"]:
                    continue
                index_accessor = primitive["indices"]
                position_accessor = primitive["attributes"]["POSITION"]
                normal_accessor = primitive["attributes"]["NORMAL"]
                score = 0
                for triangle in range(0, document["accessors"][index_accessor]["count"], 3):
                    indices = [index_value(index_accessor, triangle + offset) for offset in range(3)]
                    a, b, point_c = [vector(position_accessor, index) for index in indices]
                    normal = vector(normal_accessor, indices[0])
                    u = [b[axis] - a[axis] for axis in range(3)]
                    v = [point_c[axis] - a[axis] for axis in range(3)]
                    cross = (
                        u[1] * v[2] - u[2] * v[1],
                        u[2] * v[0] - u[0] * v[2],
                        u[0] * v[1] - u[1] * v[0],
                    )
                    dot = sum(cross[axis] * normal[axis] for axis in range(3))
                    score += (dot > 1e-8) - (dot < -1e-8)
                self.assertGreaterEqual(score, 0, mesh.get("name", "<unnamed>"))


if __name__ == "__main__":
    unittest.main()

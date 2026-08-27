#!/usr/bin/env python3
"""Final concept-art visual pass for Four Gates.

This step is intentionally deterministic.  It adds the alpine skyline visible
in the canonical references and records the 0.7 material/geometry contract
after all earlier authored-map passes have completed.
"""

import json
import math
import random
import struct
from pathlib import Path


PACKAGE = Path("four-gates-city-package")
GLB = PACKAGE / "four-gates-city.glb"
raw = GLB.read_bytes()
json_length = struct.unpack_from("<I", raw, 12)[0]
document = json.loads(raw[20:20 + json_length])
binary_offset = 20 + json_length
binary_length = struct.unpack_from("<I", raw, binary_offset)[0]
binary = raw[binary_offset + 8:binary_offset + 8 + binary_length]

nodes = document["nodes"]
node_ids = {node.get("name"): index for index, node in enumerate(nodes)}
mesh_ids = {mesh["name"]: index for index, mesh in enumerate(document["meshes"])}
material_ids = {material["name"]: index for index, material in enumerate(document["materials"])}


def clone_mesh(name, prototype, material):
    if name in mesh_ids:
        return
    source = document["meshes"][mesh_ids[prototype]]
    primitive = dict(source["primitives"][0])
    primitive["attributes"] = dict(source["primitives"][0]["attributes"])
    primitive["material"] = material_ids[material]
    document["meshes"].append({"name": name, "primitives": [primitive]})
    mesh_ids[name] = len(document["meshes"]) - 1


clone_mesh("cone_rock", "cone_roof", "rock")
clone_mesh("cone_snow", "cone_roof", "snow")


def add(name, parent, mesh, position, scale, extras=None):
    item = {
        "name": name,
        "mesh": mesh_ids[mesh],
        "translation": [float(value) for value in position],
        "scale": [float(value) for value in scale],
    }
    if extras:
        item["extras"] = extras
    nodes.append(item)
    nodes[node_ids[parent]].setdefault("children", []).append(len(nodes) - 1)
    return len(nodes) - 1


# A layered, uneven ring of distant peaks gives every gameplay camera the
# snowy mountain horizon shown in the paintings without adding collision.
random.seed(407)
mountain_nodes = []
for index in range(28):
    angle = math.tau * index / 28 + random.uniform(-0.055, 0.055)
    radius = random.uniform(650.0, 780.0)
    x, z = radius * math.sin(angle), radius * math.cos(angle)
    height = random.uniform(150.0, 285.0)
    width = random.uniform(80.0, 145.0)
    rock_name = f"Mountain_Peak_{index:02}"
    add(rock_name, "Terrain", "cone_rock", (x, -28.0 + height * 0.5, z),
        (width, height, width * random.uniform(.78, 1.14)),
        {"visualOnly": True, "terrainRole": "alpine-skyline", "lod": "LOD2"})
    cap_height = height * random.uniform(.24, .34)
    cap_name = f"Mountain_Snowcap_{index:02}"
    add(cap_name, "Terrain", "cone_snow", (x, -28.0 + height - cap_height * .48, z),
        (width * .48, cap_height, width * .48),
        {"visualOnly": True, "terrainRole": "snowcap", "lod": "LOD2"})
    mountain_nodes.extend((rock_name, cap_name))


# Evergreen clusters break up the bare shore silhouette while leaving every
# cardinal bridge and gate approach visibly clear.
evergreen_nodes = []
for index in range(56):
    angle = math.tau * index / 56 + random.uniform(-.035, .035)
    if min(abs((angle - cardinal + math.pi) % math.tau - math.pi)
           for cardinal in (0, math.pi / 2, math.pi, math.pi * 1.5)) < .11:
        continue
    radius = random.uniform(470.0, 590.0)
    x, z = radius * math.sin(angle), radius * math.cos(angle)
    height = random.uniform(25.0, 54.0)
    name = f"Outer_Evergreen_{index:02}"
    add(name, "Vegetation", "cone_vegetation", (x, 5.0 + height * .5, z),
        (height * .34, height, height * .34),
        {"visualOnly": True, "terrainRole": "outer-forest", "lod": "LOD1"})
    evergreen_nodes.append(name)


document["asset"]["generator"] = "Eloria Four Gates concept-art visual pass 0.7"
while len(binary) % 4:
    binary += b"\0"
document["buffers"][0]["byteLength"] = len(binary)
encoded = json.dumps(document, separators=(",", ":")).encode()
encoded += b" " * ((-len(encoded)) % 4)
GLB.write_bytes(
    struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(encoded) + 8 + len(binary))
    + struct.pack("<I4s", len(encoded), b"JSON") + encoded
    + struct.pack("<I4s", len(binary), b"BIN\0") + binary
)

metadata_path = PACKAGE / "four-gates-city.json"
metadata = json.loads(metadata_path.read_text())
metadata["assetVersion"] = "0.7.0"
metadata["visualDirection"] = {
    "reference": "canonical-four-gates-concept-art",
    "palette": ["warm limestone", "charcoal slate", "aged gold", "sapphire", "turquoise", "alpine green"],
    "materialAtlas": "concept-derived-4x4-pbr-basecolor",
    "landmarkAtlas": "concept-derived-2x2-pbr-basecolor",
    "alpineSkylineNodes": mountain_nodes,
    "outerEvergreenNodes": evergreen_nodes,
}
metadata["knownLimitations"] = [
    value for value in metadata["knownLimitations"]
    if "bespoke district UVs" not in value.lower()
]
metadata["knownLimitations"].append(
    "General district assets use modular atlas UVs; hero façades and roofs should receive bespoke unwraps in a later close-detail pass."
)
metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")

print(json.dumps({
    "assetVersion": metadata["assetVersion"],
    "nodes": len(nodes),
    "mountainNodes": len(mountain_nodes),
    "outerEvergreenNodes": len(evergreen_nodes),
    "glbBytes": GLB.stat().st_size,
}, indent=2))

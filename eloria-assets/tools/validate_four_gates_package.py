#!/usr/bin/env python3
"""Fail fast on truncated or internally inconsistent Four Gates GLB deliveries."""

import json
import struct
from pathlib import Path

from PIL import Image


PACKAGE = Path(__file__).resolve().parents[1] / "maps" / "four-gates-city"


def read_glb(path):
    raw = path.read_bytes()
    if len(raw) < 20 or raw[:4] != b"glTF":
        raise ValueError(f"{path.name}: missing glTF header")
    version, declared = struct.unpack_from("<II", raw, 4)
    if version != 2 or declared != len(raw):
        raise ValueError(f"{path.name}: declared {declared} bytes, actual {len(raw)}")
    json_len, json_type = struct.unpack_from("<I4s", raw, 12)
    if json_type != b"JSON" or 20 + json_len + 8 > len(raw):
        raise ValueError(f"{path.name}: invalid JSON chunk")
    document = json.loads(raw[20:20 + json_len])
    binary_offset = 20 + json_len
    binary_len, binary_type = struct.unpack_from("<I4s", raw, binary_offset)
    binary = raw[binary_offset + 8:]
    if binary_type != b"BIN\0" or binary_len != len(binary):
        raise ValueError(f"{path.name}: binary chunk length mismatch")
    if document["buffers"][0]["byteLength"] != binary_len:
        raise ValueError(f"{path.name}: buffer declaration mismatch")
    for index, view in enumerate(document.get("bufferViews", [])):
        end = view.get("byteOffset", 0) + view["byteLength"]
        if end > binary_len:
            raise ValueError(f"{path.name}: bufferView {index} exceeds binary chunk")
    names = [node.get("name") for node in document.get("nodes", []) if node.get("name")]
    if len(names) != len(set(names)):
        raise ValueError(f"{path.name}: duplicate node names")
    for index, image in enumerate(document.get("images", [])):
        view = document["bufferViews"][image["bufferView"]]
        start = view.get("byteOffset", 0)
        from io import BytesIO
        decoded = Image.open(BytesIO(binary[start:start + view["byteLength"]]))
        decoded.load()
    return document


def collect_node_references(value, key=None):
    if isinstance(value, dict):
        for child_key, child in value.items():
            yield from collect_node_references(child, child_key)
    elif isinstance(value, list):
        for child in value:
            yield from collect_node_references(child, key)
    elif isinstance(value, str) and key in {"node", "targetNode", "cityTerraceNode", "shorelineNode"}:
        yield value


def validate_pair(glb_name, json_name):
    document = read_glb(PACKAGE / glb_name)
    metadata = json.loads((PACKAGE / json_name).read_text())
    if metadata["asset"]["glb"] != glb_name:
        raise ValueError(f"{json_name}: asset.glb does not name {glb_name}")
    nodes = {node.get("name") for node in document.get("nodes", [])}
    missing = sorted(set(collect_node_references(metadata)) - nodes)
    if missing:
        raise ValueError(f"{json_name}: missing GLB nodes: {', '.join(missing[:12])}")
    return len(document["nodes"]), len(document["meshes"])


def main():
    lod1 = validate_pair("four-gates-city.glb", "four-gates-city.json")
    lod2 = validate_pair("four-gates-city-lod2.glb", "four-gates-city-lod2.json")
    print(f"Four Gates package valid: LOD1 {lod1[0]} nodes/{lod1[1]} meshes; LOD2 {lod2[0]} nodes/{lod2[1]} meshes")


if __name__ == "__main__":
    main()

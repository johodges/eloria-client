#!/usr/bin/env python3
"""Validate the generated harvestable layer of an Eloria data pack.

Checks the things that were silently wrong before the harvestable catalogue
existed:

* `harvestable.lst` holds lowercase basenames, because `is_harvestable()`
  binary-searches it with an exact strcmp against the object file's basename;
* every harvestable placed in a map is in that list and has a model on disk;
* every model is inside the fidelity band the surrounding landmark kit uses,
  and foliage models declare a transparent material so the client alpha-tests
  them and stops culling their back faces;
* nodes are actually spread across each region instead of stacked on a handful
  of shared coordinates;
* every region offers harvest work, and the decorative `.2d` ground flora the
  maps reference exists.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

MIN_TRIANGLES = 90
MAX_TRIANGLES = 420
MIN_NODES_PER_REGION = 8
MIN_SPREAD_CELLS = 6


def read_e3d(path: Path) -> dict:
    data = path.read_bytes()
    if data[:4] != b"e3dx":
        raise ValueError(f"{path}: not an E3D file")
    (vertex_no, vertex_size, _vo, index_no, index_size, _io,
     material_no, material_size, material_offset) = struct.unpack_from(
        "<9i", data, 28)
    options = struct.unpack_from("<i", data, material_offset)[0]
    texture = struct.unpack_from("<128s", data, material_offset + 4)[0]
    return {
        "vertices": vertex_no, "triangles": index_no // 3,
        "materials": material_no, "transparent": options != 0,
        "texture": texture.split(b"\0", 1)[0].decode(),
        "vertex_size": vertex_size, "index_size": index_size,
        "material_size": material_size,
    }


def png_size(path: Path) -> tuple:
    return struct.unpack_from(">II", path.read_bytes(), 16)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default="build/eloria-data")
    args = parser.parse_args()
    root = Path(args.root)
    errors: list = []
    warnings: list = []

    manifest_path = root / "nymara_harvesting.json"
    if not manifest_path.is_file():
        print(f"missing {manifest_path}", file=sys.stderr)
        return 1
    manifest = json.loads(manifest_path.read_text())

    listed = [line.strip() for line in
              (root / "harvestable.lst").read_text().splitlines()
              if line.strip()]
    for entry in listed:
        if entry != entry.lower():
            errors.append(f"harvestable.lst entry is not lowercase: {entry}")
        if "/" in entry or "\\" in entry:
            errors.append(
                f"harvestable.lst entry is a path, not a basename: {entry}")
    if listed != sorted(listed):
        warnings.append("harvestable.lst is not sorted")

    catalogue = {record["id"]: record for record in manifest["catalogue"]}
    for record in manifest["catalogue"]:
        model = root / record["model"]
        if not model.is_file():
            errors.append(f"missing model {record['model']}")
            continue
        info = read_e3d(model)
        if not MIN_TRIANGLES <= info["triangles"] <= MAX_TRIANGLES:
            errors.append(
                f"{record['id']}: {info['triangles']} triangles is outside the "
                f"{MIN_TRIANGLES}-{MAX_TRIANGLES} fidelity band")
        if record["alpha_tested"] != info["transparent"]:
            errors.append(
                f"{record['id']}: material transparency flag does not match "
                "the catalogue; foliage must be alpha tested so the client "
                "keeps both faces")
        texture = model.with_name(info["texture"])
        if not texture.is_file():
            errors.append(f"{record['id']}: missing material {info['texture']}")
        elif png_size(texture) != (256, 256):
            errors.append(
                f"{record['id']}: material is {png_size(texture)}, the "
                "production contract is 256x256")
        if f"{record['id']}.e3d" not in listed:
            errors.append(
                f"{record['id']}: placed model is absent from harvestable.lst")

    by_map: dict = {}
    for node in manifest["nodes"]:
        by_map.setdefault(node["map_id"], []).append(node)
        if node["resource"] not in catalogue:
            errors.append(
                f"{node['map_id']}: node references unknown resource "
                f"{node['resource']}")
        if not (root / node["model"]).is_file():
            errors.append(f"{node['map_id']}: missing model {node['model']}")

    for map_id, nodes in sorted(by_map.items()):
        if len(nodes) < MIN_NODES_PER_REGION:
            errors.append(
                f"{map_id}: only {len(nodes)} harvest nodes")
        positions = {(node["x"], node["y"]) for node in nodes}
        if len(positions) != len(nodes):
            errors.append(f"{map_id}: harvest nodes share coordinates")
        for index, first in enumerate(nodes):
            for second in nodes[index + 1:]:
                if (abs(first["x"] - second["x"]) < MIN_SPREAD_CELLS
                        and abs(first["y"] - second["y"]) < MIN_SPREAD_CELLS):
                    warnings.append(
                        f"{map_id}: {first['resource']} and "
                        f"{second['resource']} are less than "
                        f"{MIN_SPREAD_CELLS} cells apart")
        if len({node["resource"] for node in nodes}) < 4:
            errors.append(f"{map_id}: fewer than four distinct resources")

    flora = manifest.get("ground_flora", {})
    for definition in flora.get("definitions", []):
        path = root / definition["definition"]
        if not path.is_file():
            errors.append(f"missing flora definition {definition['definition']}")
            continue
        body = path.read_text()
        atlas = [line.split(":", 1)[1].strip() for line in body.splitlines()
                 if line.startswith("texture:")]
        if not atlas or not (path.parent / atlas[0]).is_file():
            errors.append(f"{definition['id']}: missing flora atlas")
    empty = [entry["map_id"] for entry in flora.get("maps", [])
             if entry["sprites"] == 0]
    if empty:
        warnings.append("regions without ground flora: " + ", ".join(empty))

    report = {
        "harvestables": len(catalogue),
        "nodes": len(manifest["nodes"]),
        "regions": len(by_map),
        "nodes_per_region": {k: len(v) for k, v in sorted(by_map.items())},
        "triangles": {k: v["triangles"] for k, v in sorted(catalogue.items())},
        "ground_flora_sprites": sum(entry["sprites"]
                                    for entry in flora.get("maps", [])),
        "warnings": warnings,
        "errors": errors,
    }
    print(json.dumps(report, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

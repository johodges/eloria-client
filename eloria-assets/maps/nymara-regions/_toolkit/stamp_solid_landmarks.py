#!/usr/bin/env python3
"""Block the ground a solid landmark stands on in a region's walk grid.

The region builders block a placed structure with a circle inscribed in its
bounds. That is right for a tree or a boulder and wrong for a hall: the
circle leaves the ends of a long building and the corners of a square one
walkable, so a player could walk into the customs hall's east end and an
NPC posted at a tower's door stood inside the tower. This reads the
package's own GLB, measures each landmark of a solid kind (`building`,
`tower`) by the bounds of the parts of it that stand on the ground - roofs
overhang and float above - and blocks that box, plus a margin, in the
package's `collision.bin`. What it stamped is recorded under
`collision.stampedLandmarks` in `world.json`, so running it twice changes
nothing, and a server sync that follows sees the box.

    python _toolkit/stamp_solid_landmarks.py <region> [<region> ...]
    python _toolkit/stamp_solid_landmarks.py --all

Run it after a region build: the build writes `collision.bin` from the
circles again. Then `tools/sync_authored_collision.py` on the server side,
which opens each door tile and cuts its approach, so a building's door
stays a door.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOLID = ("building", "tower")
MARGIN = 0.5            # metres round the walls that nobody should stand on either
GROUNDED = 1.2          # a part whose lowest point is within this of the lowest part stands on the ground
HEADER = struct.Struct("<4sHHII")
CELL = 0.5


def glb_document(path: Path) -> dict:
    raw = path.read_bytes()
    chunk_length = struct.unpack_from("<II", raw, 12)[0]
    return json.loads(raw[20:20 + chunk_length].decode("utf-8"))


def matrix_of(node: dict) -> np.ndarray:
    if "matrix" in node:
        return np.array(node["matrix"], dtype=float).reshape(4, 4).T
    t = np.array(node.get("translation", [0, 0, 0]), dtype=float)
    s = np.array(node.get("scale", [1, 1, 1]), dtype=float)
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    r = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    m = np.eye(4)
    m[:3, :3] = r * s
    m[:3, 3] = t
    return m


def ground_boxes(doc: dict) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Node name -> world-space (low, high) of the primitives under a landmark
    node that stand on the ground, from the accessors' own bounds."""
    nodes = doc["nodes"]
    parents = {}
    for index, node in enumerate(nodes):
        for child in node.get("children", []):
            parents[child] = index

    def world(index: int) -> np.ndarray:
        m = matrix_of(nodes[index])
        while index in parents:
            index = parents[index]
            m = matrix_of(nodes[index]) @ m
        return m

    def subtree(index: int):
        yield index
        for child in nodes[index].get("children", []):
            yield from subtree(child)

    out = {}
    for index, node in enumerate(nodes):
        name = node.get("name", "")
        if not name.startswith("Landmark_"):
            continue
        parts = []
        for sub in subtree(index):
            mesh = nodes[sub].get("mesh")
            if mesh is None:
                continue
            m = world(sub)
            for prim in doc["meshes"][mesh]["primitives"]:
                acc = doc["accessors"][prim["attributes"]["POSITION"]]
                low, high = np.array(acc["min"], dtype=float), np.array(acc["max"], dtype=float)
                corners = np.array([[x, y, z, 1.0] for x in (low[0], high[0]) for y in (low[1], high[1])
                                    for z in (low[2], high[2])])
                points = (m @ corners.T).T[:, :3]
                parts.append((points.min(axis=0), points.max(axis=0)))
        if not parts:
            continue
        floor = min(low[1] for low, _ in parts)
        grounded = [(low, high) for low, high in parts if low[1] <= floor + GROUNDED]
        out[name] = (np.min([low for low, _ in grounded], axis=0), np.max([high for _, high in grounded], axis=0))
    return out


def stamp(region: Path) -> int:
    manifest_path = region / "world.json"
    # newline="" keeps the file's own line endings in `text`, so they can be put back
    with open(manifest_path, encoding="utf-8", newline="") as handle:
        text = handle.read()
    manifest = json.loads(text)
    previous = {entry["id"]: entry for entry in (manifest.get("collision") or {}).get("stampedLandmarks", [])}
    collision = manifest.get("collision") or {}
    binary = region / collision.get("binary", "collision.bin")
    if not binary.is_file() or not (region / "world.glb").is_file():
        print(f"[stamp] {region.name}: no collision.bin or world.glb; skipped")
        return 0
    raw = bytearray(binary.read_bytes())
    magic, version, flags, width, height = HEADER.unpack_from(raw, 0)
    if magic != b"EWCG" or collision.get("cellMetres", CELL) != CELL:
        print(f"[stamp] {region.name}: not a half-metre EWCG grid; skipped")
        return 0
    grid = np.frombuffer(raw, dtype=np.uint8, offset=HEADER.size).reshape(height, width).copy()
    ox, oz = manifest["coordinateTransform"]["serverOrigin"]
    boxes = ground_boxes(glb_document(region / "world.glb"))
    stamped = []
    blocked = 0
    for landmark in manifest.get("landmarks", []):
        kind = landmark.get("type", landmark.get("kind"))
        node = landmark.get("node", "")
        if kind not in SOLID or node not in boxes:
            continue
        low, high = boxes[node]
        # cell (cx, cz) is centred on (-ox + 0.5 cx + 0.25, oz - 0.5 cz - 0.25)
        c0 = int(np.ceil((low[0] - MARGIN + ox) / CELL - 0.5))
        c1 = int(np.floor((high[0] + MARGIN + ox) / CELL - 0.5))
        r0 = int(np.ceil((oz - high[2] - MARGIN) / CELL - 0.5))
        r1 = int(np.floor((oz - low[2] + MARGIN) / CELL - 0.5))
        c0, c1 = max(c0, 0), min(c1, width - 1)
        r0, r1 = max(r0, 0), min(r1, height - 1)
        if c1 < c0 or r1 < r0:
            continue
        patch = grid[r0:r1 + 1, c0:c1 + 1]
        newly = int((patch != 0).sum())
        patch[:] = 0
        blocked += newly
        # a second run finds the box already blocked; the record keeps what the first run took
        newly = max(newly, int(previous.get(landmark["id"], {}).get("cellsBlocked", 0)))
        stamped.append({"id": landmark["id"], "node": node, "type": kind,
                        "box": [round(float(low[0]), 2), round(float(low[2]), 2),
                                round(float(high[0]), 2), round(float(high[2]), 2)],
                        "marginMetres": MARGIN, "cellsBlocked": newly})
        print(f"[stamp] {region.name}: {landmark['id']} ({kind}) x {low[0]:.1f}..{high[0]:.1f} "
              f"z {low[2]:.1f}..{high[2]:.1f}: {newly} cells were walkable")
    if not stamped:
        print(f"[stamp] {region.name}: no solid landmarks")
        return 0
    raw[HEADER.size:HEADER.size + width * height] = grid.tobytes()
    binary.write_bytes(bytes(raw))
    walkable = int((grid != 0).sum())
    collision["walkableCells"] = walkable
    collision["walkableFraction"] = round(walkable / grid.size, 4)
    collision["stampedLandmarks"] = stamped
    manifest["collision"] = collision
    # Rewrite the manifest as it was formatted: its indent and its line ending.
    lines = text.splitlines()
    indent = (len(lines[1]) - len(lines[1].lstrip(" "))) if len(lines) > 1 else 2
    newline = "\r\n" if "\r\n" in text else "\n"
    manifest_path.write_text(json.dumps(manifest, indent=indent or 2, ensure_ascii=False) + "\n",
                             encoding="utf-8", newline=newline)
    print(f"[stamp] {region.name}: {len(stamped)} landmarks, {blocked} cells blocked; "
          f"{walkable} walkable cells remain")
    return blocked


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    if args == ["--all"]:
        regions = sorted(p.parent for p in ROOT.glob("*/world.json") if (p.parent / "world.glb").is_file())
    else:
        regions = [ROOT / name for name in args]
    for region in regions:
        stamp(region)
    return 0


if __name__ == "__main__":
    sys.exit(main())

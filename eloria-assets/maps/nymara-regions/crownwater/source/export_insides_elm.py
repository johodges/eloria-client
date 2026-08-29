#!/usr/bin/env python3
"""Write the server-side ELM for the Crownwater insides map.

The four insides share one map with blackspace between them, so the server needs
one collision map for the lot. This reads the package's own `collision.bin` -
the half-metre grid the client already agrees with - and downsamples it to the
one-metre ELM height map, so the two cannot drift apart.

Height bytes follow the convention the client uses:

    elevation_metres = height_byte * 0.2 - 2.2

and zero means blocked, which is what the blackspace between sections is.

Structured after `amethyst_barrens/source/export_insides_elm.py`, which
established this pattern in the repository. Kept region-side rather than shared
because a cross-region import would make one region's build depend on another's
source tree; if a third region needs it, it belongs in `_toolkit/`.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

import numpy as np

TILE_SIZE = 6
HEADER_SIZE = 124


def write_elm(path: Path, template: Path, heights: np.ndarray) -> int:
    cells = heights.shape[0]
    tiles = cells // TILE_SIZE
    raw = bytearray(template.read_bytes())
    if raw[:4] != b"elmf":
        raise SystemExit(f"template is not an ELM: {template}")

    tile_map = bytes(tiles * tiles)
    height_map = heights.astype(np.uint8).tobytes()
    tile_offset = HEADER_SIZE
    height_offset = tile_offset + len(tile_map)

    header = bytearray(HEADER_SIZE)
    header[:4] = b"elmf"
    struct.pack_into("<10i", header, 4,
                     tiles, tiles, tile_offset, height_offset,
                     0, 0, height_offset + len(height_map),
                     128, 0, height_offset + len(height_map))
    out = bytes(header) + tile_map + height_map
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out)
    return len(out)


def main() -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--package",
                    default=str(here.parents[1] / "interiors" / "crownwater_insides"))
    ap.add_argument("--out",
                    default=str(here.parents[1] / "source-elm" / "drowned_crown.elm"))
    ap.add_argument("--template",
                    default=str(here.parents[1] / "source-elm" / "drowned_crown.elm"))
    ap.add_argument("--tiles", type=int, default=64)
    args = ap.parse_args()

    package = Path(args.package)
    manifest = json.loads((package / "world.json").read_text(encoding="utf-8"))
    collision = manifest["collision"]
    payload = (package / collision["binary"]).read_bytes()
    _, _, _, width, height = struct.unpack("<4sHHII", payload[:16])
    grid = np.frombuffer(payload, dtype=np.uint8, offset=16).reshape(height, width)

    # half-metre grid -> one-metre cells
    step = int(round(1.0 / collision["cellMetres"]))
    coarse = grid[::step, ::step]

    cells = args.tiles * TILE_SIZE
    if coarse.shape[0] > cells or coarse.shape[1] > cells:
        raise SystemExit(
            f"insides map is {coarse.shape[1]}x{coarse.shape[0]} cells, which "
            f"does not fit {cells}x{cells}; raise --tiles")
    padded = np.zeros((cells, cells), dtype=np.uint8)
    padded[:coarse.shape[0], :coarse.shape[1]] = coarse

    size = write_elm(Path(args.out), Path(args.template), padded)
    walkable = float((padded > 0).mean())
    print(f"[elm] {args.out} {size} bytes, {args.tiles}x{args.tiles} tiles, "
          f"{cells}x{cells} height cells")
    print(f"[elm] {walkable * 100:.1f}% walkable, {(1.0 - walkable) * 100:.1f}% "
          f"blocked (the blackspace between sections, and the rock around each)")
    # Server tiles, from the collision grid's own origin rather than guessed.
    # The grid's origin is [x0, z1]: column = (x - x0), row = (z1 - z), both in
    # one-metre cells after the downsample.
    origin = collision.get("originMetres", [0.0, 0.0])
    for section in manifest.get("sections", []):
        ax, _, az = section["arrival"]
        tile_x = int(round(ax - origin[0]))
        tile_y = int(round(origin[1] - az))
        blocked = padded[tile_y, tile_x] == 0 if (
            0 <= tile_y < cells and 0 <= tile_x < cells) else True
        section["serverTile"] = [tile_x, tile_y]
        print(f"[elm] {section['id']:<16} server tile ({tile_x:>3}, {tile_y:>3})"
              f"  spawn {section['spawn']}"
              f"{'   *** ON A BLOCKED CELL ***' if blocked else ''}")
    # Write the tiles back so maps.txt and the manifest cannot disagree.
    (package / "world.json").write_text(
        json.dumps(manifest, indent=2) + chr(10), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

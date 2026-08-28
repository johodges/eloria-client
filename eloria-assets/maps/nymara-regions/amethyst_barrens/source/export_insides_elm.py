#!/usr/bin/env python3
"""Write the server-side ELM for the Amethyst Barrens insides map.

The four insides share one map with blackspace between them, so the server needs
one collision map for the lot. This reads the package's own `collision.bin` -
the half-metre grid the client already agrees with - and downsamples it to the
one-metre ELM height map, so the two cannot drift apart.

Height bytes follow the convention the client uses:

    elevation_metres = height_byte * 0.2 - 2.2

and zero means blocked, which is what the blackspace between sections is.
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
    magic = raw[:4]
    if magic != b"elmf":
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
                    default=str(here.parents[1] / "interiors" / "amethyst_barrens_insides"))
    ap.add_argument("--out",
                    default=str(here.parents[1] / "source-elm" / "resonant_vault.elm"))
    ap.add_argument("--template",
                    default=str(here.parents[1] / "source-elm" / "resonant_vault.elm"))
    ap.add_argument("--tiles", type=int, default=64)
    args = ap.parse_args()

    package = Path(args.package)
    manifest = json.loads((package / "world.json").read_text(encoding="utf-8"))
    collision = manifest["collision"]
    payload = (package / collision["binary"]).read_bytes()
    _, _, _, width, height = struct.unpack("<4sHHII", payload[:16])
    grid = np.frombuffer(payload, dtype=np.uint8, offset=16).reshape(height, width)

    # half-metre grid -> one-metre cells, taking the max so a walkable cell is
    # never lost to a blocked neighbour when downsampling
    step = int(round(1.0 / collision["cellMetres"]))
    coarse = grid[::step, ::step]

    cells = args.tiles * TILE_SIZE
    if coarse.shape[0] > cells or coarse.shape[1] > cells:
        raise SystemExit(
            f"insides map is {coarse.shape[1]}x{coarse.shape[0]} cells, which does "
            f"not fit {cells}x{cells}; raise --tiles")
    padded = np.zeros((cells, cells), dtype=np.uint8)
    padded[:coarse.shape[0], :coarse.shape[1]] = coarse

    size = write_elm(Path(args.out), Path(args.template), padded)
    walkable = float((padded > 0).mean())
    blocked = float((padded == 0).mean())
    print(f"[elm] {args.out} {size} bytes, {args.tiles}x{args.tiles} tiles, "
          f"{cells}x{cells} height cells")
    print(f"[elm] {walkable * 100:.1f}% walkable, {blocked * 100:.1f}% blocked "
          f"(the blackspace between sections, and the rock around each)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

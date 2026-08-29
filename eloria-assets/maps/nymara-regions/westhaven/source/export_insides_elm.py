#!/usr/bin/env python3
"""Write the server-side ELM for the Westhaven insides map.

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
                    default=str(here.parents[1] / "interiors" / "westhaven_insides"))
    ap.add_argument("--out",
                    default=str(here.parents[1] / "source-elm" / "westhaven_insides.elm"))
    ap.add_argument("--template",
                    default=str(here.parents[1] / "source-elm" / "westhaven.elm"))
    ap.add_argument("--tiles", type=int, default=64)
    args = ap.parse_args()

    package = Path(args.package)
    manifest = json.loads((package / "world.json").read_text(encoding="utf-8"))
    collision = manifest["collision"]
    payload = (package / collision["binary"]).read_bytes()
    _, _, _, width, height = struct.unpack("<4sHHII", payload[:16])
    grid = np.frombuffer(payload, dtype=np.uint8, offset=16).reshape(height, width)

    # Half-metre grid -> one-metre cells, taking the max over each block so a
    # walkable cell is never lost to a blocked neighbour.
    #
    # This used to say that and then write `grid[::step, ::step]`, which is a
    # stride *sample*, not a max: whether a one-metre cell came out walkable
    # depended on which of its four half-metre cells happened to be sampled.
    # Three of Westhaven's four arrival tiles landed on blocked cells that way,
    # and an arrival on a blocked tile is a player who cannot move after using
    # the door. The same line is in `amethyst_barrens/source/export_insides_elm.py`.
    step = int(round(1.0 / collision["cellMetres"]))
    rows = (grid.shape[0] // step) * step
    cols = (grid.shape[1] // step) * step
    coarse = grid[:rows, :cols].reshape(
        rows // step, step, cols // step, step).max(axis=(1, 3))

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

    # The server arrival tile for each door, derived rather than counted by
    # hand: the manifest's serverOrigin is what the client uses, so the server
    # table has to agree with it or a player arrives somewhere else entirely.
    origin = manifest["coordinateTransform"]["serverOrigin"]
    print("[elm] server arrival tiles (for eloria-server ARRIVAL_TILES):")
    for spawn in manifest["spawnPoints"]:
        x, _, z = spawn["position"]
        # coordinate_adapter.gd: godot_x = server_x - serverOrigin.x and
        # godot_z = -(server_y - serverOrigin.y), so inverting gives
        # server_x = godot_x + serverOrigin.x. Subtracting it instead put every
        # arrival ten tiles east of where the client puts it, which read as
        # three of the four landing on blackspace.
        tile = (int(round(x + origin[0])), int(round(origin[1] - z)))
        cell = padded[tile[1], tile[0]] if (0 <= tile[1] < cells
                                            and 0 <= tile[0] < cells) else 0
        print(f"       {spawn['id']:<24} {tile}  "
              f"{'walkable' if cell else 'BLOCKED'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

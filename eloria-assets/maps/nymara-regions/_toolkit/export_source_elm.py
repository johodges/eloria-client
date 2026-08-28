#!/usr/bin/env python3
"""Write the server-side ELM for the enlarged Amberwood.

The region is authored at 64x64 ELM tiles (384 height cells) so it can keep one
metre per tile at twice its original extent. This writes that map with real
elevation and walkability instead of the flat placeholder the region shipped
with, using the same terrain the runtime GLB is built from.

Height bytes follow the Eternal Lands convention the client already uses:

    elevation_metres = height_byte * 0.2 - 2.2

and zero means blocked. The tile map is left on tile 0 throughout, exactly as
the existing `amberwood.elm` does; the server's own tile set is not this build's
to choose.
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import regionpaths
from amberwood import region as REG

HEADER_BYTES = 120
TILE_SIZE = 6  # height cells per ELM tile, per axis


def write_elm(path: Path, template: Path, heights: np.ndarray) -> int:
    tiles_x = heights.shape[1] // TILE_SIZE
    tiles_y = heights.shape[0] // TILE_SIZE
    header = bytearray(template.read_bytes()[:HEADER_BYTES])

    tile_map_offset = HEADER_BYTES
    tile_map_size = tiles_x * tiles_y
    height_map_offset = tile_map_offset + tile_map_size
    height_map_size = heights.size
    end = height_map_offset + height_map_size

    struct.pack_into("<ii", header, 4, tiles_x, tiles_y)
    struct.pack_into("<ii", header, 12, tile_map_offset, height_map_offset)
    # obj_3d / obj_2d / lights / particles: keep the struct sizes, zero the
    # counts, and point every offset at the end of the file
    struct.pack_into("<iii", header, 20, 144, 0, end)      # obj_3d
    struct.pack_into("<iii", header, 32, 128, 0, end)      # obj_2d
    struct.pack_into("<iii", header, 44, 32, 0, end)       # lights
    struct.pack_into("<iii", header, 72, 32, 0, end)       # particles

    payload = bytes(header) + bytes(tile_map_size) + heights.astype(np.uint8).tobytes()
    path.write_bytes(payload)
    return len(payload)


def load_region_build(package: Path):
    """Import the region's own build module for its collision encoding.

    The ELM is written from the same collision grid the GLB ships, so this has
    to come from the region's build script rather than the toolkit.
    """
    import importlib.util

    source = regionpaths.region_source(package)
    candidates = sorted(source.glob("build_*.py"))
    candidates = [c for c in candidates if c.stem != "build_interiors"]
    if len(candidates) != 1:
        raise SystemExit(
            f"expected exactly one build_*.py in {source}, found "
            f"{[c.name for c in candidates]}; pass --build-module")
    sys.path.insert(0, str(source))
    spec = importlib.util.spec_from_file_location(candidates[0].stem,
                                                  candidates[0])
    module = importlib.util.module_from_spec(spec)
    sys.modules[candidates[0].stem] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--template", default=None)
    args = parser.parse_args()
    package = regionpaths.package_root(args.package)
    source_elm = regionpaths.REGIONS / "source-elm"
    out = Path(args.out) if args.out else source_elm / f"{package.name}.elm"
    template = (Path(args.template) if args.template
                else source_elm / f"{package.name}.elm")

    build_module = load_region_build(package)
    COLLISION_HEIGHT_ORIGIN = build_module.COLLISION_HEIGHT_ORIGIN
    COLLISION_HEIGHT_STEP = build_module.COLLISION_HEIGHT_STEP
    build_collision = build_module.build_collision

    build = build_module.build_region()
    payload, width, height, stats = build_collision(build)
    grid = np.frombuffer(payload, dtype=np.uint8, offset=16).reshape(height, width)

    # the collision grid is half-metre; the ELM height map is one cell per tile
    # sixth, i.e. the same spacing as the server's movement grid
    cells = REG.SERVER_CELLS
    step = max(1, width // cells)
    heights = grid[::step, ::step][:cells, :cells]
    if heights.shape != (cells, cells):
        padded = np.zeros((cells, cells), dtype=np.uint8)
        padded[:heights.shape[0], :heights.shape[1]] = heights
        heights = padded

    size = write_elm(out, template, heights)
    walkable = float((heights > 0).mean())
    print(f"[elm] {out} {size} bytes, {cells // TILE_SIZE}x{cells // TILE_SIZE} tiles, "
          f"{cells}x{cells} height cells, {walkable * 100:.1f}% walkable")
    print(f"[elm] elevation = byte * {COLLISION_HEIGHT_STEP} "
          f"{COLLISION_HEIGHT_ORIGIN:+.1f} m, zero means blocked")
    return 0


if __name__ == "__main__":
    sys.exit(main())

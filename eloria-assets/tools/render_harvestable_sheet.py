#!/usr/bin/env python3
"""Render a deterministic shaded contact sheet of the harvestable models.

Reads the E3D files the harvestable catalogue produces and draws each one from
a fixed three-quarter camera so the silhouettes can be compared against the
regional landmark kit at review time.
"""
from __future__ import annotations

import argparse
import struct
from pathlib import Path

from generate_bootstrap_pack import png

BACKGROUND = (22, 25, 28)
PANEL = (30, 34, 38)


def read_mesh(path: Path) -> tuple:
    data = path.read_bytes()
    if data[:4] != b"e3dx":
        raise ValueError(f"not an E3D mesh: {path}")
    (vertex_no, vertex_size, vertex_offset,
     index_no, index_size, index_offset) = struct.unpack_from("<6i", data, 28)
    if vertex_size != 32 or index_size != 2:
        raise ValueError(f"unsupported E3D layout: {path}")
    vertices = [struct.unpack_from("<8f", data, vertex_offset + i * vertex_size)
                for i in range(vertex_no)]
    indices = struct.unpack_from(f"<{index_no}H", data, index_offset)
    return vertices, indices


def draw(path: Path, size: int, tint: tuple) -> list:
    vertices, indices = read_mesh(path)
    positions = [(v[5], v[6], v[7]) for v in vertices]
    normals = [(v[2], v[3], v[4]) for v in vertices]
    flat = [((x - y) * 0.7071, z * 0.90 - (x + y) * 0.35)
            for x, y, z in positions]
    min_x = min(a for a, _ in flat)
    max_x = max(a for a, _ in flat)
    min_y = min(b for _, b in flat)
    max_y = max(b for _, b in flat)
    scale = min((size - 18) / max(0.01, max_x - min_x),
                (size - 18) / max(0.01, max_y - min_y))
    screen = [(9 + (a - min_x) * scale, size - 9 - (b - min_y) * scale)
              for a, b in flat]
    pixels = [[PANEL] * size for _ in range(size)]
    depth = [[1e9] * size for _ in range(size)]
    faces = sorted(
        (
            (sum(positions[indices[k + o]][0] + positions[indices[k + o]][1]
                 for o in range(3)) / 3.0, k)
            for k in range(0, len(indices), 3)
        ), key=lambda item: -item[0])
    for far, k in faces:
        a, b, c = (screen[indices[k + o]] for o in range(3))
        nx, ny, nz = normals[indices[k]]
        light = max(0.20, min(1.0, 0.34 + 0.66 * max(0.0, nx * 0.38 + ny * 0.28
                                                     + nz * 0.88)))
        colour = tuple(min(255, int(30 + channel * light)) for channel in tint)
        area = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(area) < 1e-9:
            continue
        x0 = max(0, int(min(a[0], b[0], c[0])))
        x1 = min(size - 1, int(max(a[0], b[0], c[0])) + 1)
        y0 = max(0, int(min(a[1], b[1], c[1])))
        y1 = min(size - 1, int(max(a[1], b[1], c[1])) + 1)
        for py in range(y0, y1 + 1):
            for px in range(x0, x1 + 1):
                w0 = ((b[1] - c[1]) * (px - c[0])
                      + (c[0] - b[0]) * (py - c[1])) / area
                w1 = ((c[1] - a[1]) * (px - c[0])
                      + (a[0] - c[0]) * (py - c[1])) / area
                if w0 < -0.002 or w1 < -0.002 or w0 + w1 > 1.002:
                    continue
                if far < depth[py][px]:
                    depth[py][px] = far
                    pixels[py][px] = colour
    return pixels


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default="build/eloria-data")
    parser.add_argument("--output", default=None)
    parser.add_argument("--cell", type=int, default=192)
    parser.add_argument("--columns", type=int, default=8)
    args = parser.parse_args()

    import harvestables
    root = Path(args.root)
    output = Path(args.output) if args.output else root / "harvestables_qa.png"
    entries = [entry for entry in harvestables.CATALOGUE
               if (root / harvestables.model_path(entry[0])).is_file()]
    if not entries:
        print(f"no harvestable models under {root}")
        return 1
    rows = (len(entries) + args.columns - 1) // args.columns
    width = args.columns * args.cell
    height = rows * args.cell
    sheet = [[BACKGROUND] * width for _ in range(height)]
    for index, entry in enumerate(entries):
        tile = draw(root / harvestables.model_path(entry[0]), args.cell - 6,
                    entry[5][1])
        ox = (index % args.columns) * args.cell + 3
        oy = (index // args.columns) * args.cell + 3
        for y, row in enumerate(tile):
            for x, colour in enumerate(row):
                sheet[oy + y][ox + x] = colour
    png(output, width, height,
        lambda x, y: (*sheet[y][x], 255))
    print(f"{output}: {len(entries)} harvestables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

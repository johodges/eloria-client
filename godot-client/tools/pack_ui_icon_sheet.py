#!/usr/bin/env python3
"""Pack a generated contact sheet into a fixed-size UI atlas.

Each source cell is cropped and resized independently.  Keeping the resampling
inside cell boundaries prevents a bright frame or symbol from bleeding into a
neighbouring icon when the source sheet is reduced to runtime resolution.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from PIL import Image


def cell_bounds(length: int, grid: int, index: int) -> tuple[int, int]:
    return round(index * length / grid), round((index + 1) * length / grid)


def pack(source: Image.Image, source_grid: int, destination_grid: int,
         cell_size: int, count: int, canvas_size: int) -> Image.Image:
    atlas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    for index in range(count):
        source_row, source_column = divmod(index, source_grid)
        left, right = cell_bounds(source.width, source_grid, source_column)
        top, bottom = cell_bounds(source.height, source_grid, source_row)
        icon = source.crop((left, top, right, bottom)).resize(
            (cell_size, cell_size), Image.Resampling.LANCZOS)
        destination_row, destination_column = divmod(index, destination_grid)
        atlas.alpha_composite(icon, (destination_column * cell_size,
                                      destination_row * cell_size))
    return atlas


def write_dds(path: Path, image: Image.Image) -> None:
    """Write the uncompressed BGRA DDS format consumed by the legacy client."""
    rgba = image.convert("RGBA")
    width, height = rgba.size
    header = [124, 0x0002100F, height, width, width * 4, 0, 0]
    header += [0] * 11
    header += [32, 0x41, 0, 32, 0x00FF0000, 0x0000FF00,
               0x000000FF, 0xFF000000]
    header += [0x1000, 0, 0, 0, 0]
    source_pixels = rgba.load()
    pixels = bytearray()
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = source_pixels[x, y]
            pixels.extend((blue, green, red, alpha))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"DDS " + struct.pack("<31I", *header) + pixels)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--source-grid", type=int, required=True)
    parser.add_argument("--destination-grid", type=int, required=True)
    parser.add_argument("--cell-size", type=int, required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--canvas-size", type=int, default=256)
    parser.add_argument("--dds", type=Path)
    args = parser.parse_args()

    source = Image.open(args.source).convert("RGBA")
    atlas = pack(source, args.source_grid, args.destination_grid,
                 args.cell_size, args.count, args.canvas_size)
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(args.destination, optimize=True)
    if args.dds is not None:
        write_dds(args.dds, atlas)


if __name__ == "__main__":
    main()

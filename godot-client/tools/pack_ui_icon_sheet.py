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


def spans(occupied: list[bool]) -> list[tuple[int, int]]:
    """The runs of True in `occupied`, as inclusive-exclusive bounds."""
    found: list[tuple[int, int]] = []
    start: int | None = None
    for index, filled in enumerate(occupied):
        if filled and start is None:
            start = index
        elif not filled and start is not None:
            found.append((start, index))
            start = None
    if start is not None:
        found.append((start, len(occupied)))
    return found


def detect_tiles(source: Image.Image,
                 threshold: int = 28) -> list[tuple[int, int, int, int]]:
    """Find the sheet's tiles rather than assuming they fill an even grid.

    A generated contact sheet is only approximately ruled: the sheet these
    were drawn from put its rows on a tighter pitch than its columns, so
    slicing it into equal cells cut nine pixels off the top of the bottom row
    and left a band of backing below it. Every icon in that row would have sat
    low in its cell by a pixel once reduced, which is exactly the kind of
    thing nobody sees until the whole set is in front of them.

    The tiles are opaque and the backing between them is not, so the columns
    and rows the tiles occupy can simply be read off. Tiles are returned in
    reading order for however many rows and columns were found; a short final
    row is fine, and the cells it does not reach are skipped.
    """
    pixels = source.convert("RGB").load()
    width, height = source.size
    lit_column = [False] * width
    lit_row = [False] * height
    for y in range(height):
        for x in range(width):
            red, green, blue = pixels[x, y]
            if max(red, green, blue) > threshold:
                lit_column[x] = True
                lit_row[y] = True
    columns, rows = spans(lit_column), spans(lit_row)
    return [(left, top, right, bottom)
            for top, bottom in rows for left, right in columns]


def pack(source: Image.Image, source_grid: int, destination_grid: int,
         cell_size: int, count: int, canvas_size: int,
         detect: bool = False, start_index: int = 0,
         base: Image.Image | None = None) -> Image.Image:
    atlas = base if base is not None else Image.new(
        "RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    tiles = detect_tiles(source) if detect else None
    if tiles is not None and len(tiles) < count:
        raise SystemExit("found %d tiles in the sheet, needed %d"
                         % (len(tiles), count))
    for index in range(count):
        if tiles is not None:
            box = tiles[index]
        else:
            source_row, source_column = divmod(index, source_grid)
            left, right = cell_bounds(source.width, source_grid, source_column)
            top, bottom = cell_bounds(source.height, source_grid, source_row)
            box = (left, top, right, bottom)
        icon = source.crop(box).resize(
            (cell_size, cell_size), Image.Resampling.LANCZOS)
        destination_row, destination_column = divmod(start_index + index,
                                                     destination_grid)
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
    parser.add_argument("--source-grid", type=int, default=0,
                        help="cells per side of the source sheet; ignored "
                             "with --detect")
    parser.add_argument("--destination-grid", type=int, required=True)
    parser.add_argument("--cell-size", type=int, required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--canvas-size", type=int, default=256)
    parser.add_argument(
        "--start-index", type=int, default=0,
        help="place the first icon at this cell rather than at the start, so "
             "a second sheet can be added to an atlas without redrawing the "
             "first; the existing atlas is read back and added to")
    parser.add_argument(
        "--detect", action="store_true",
        help="find the sheet's tiles instead of assuming an even grid, for a "
             "generated sheet whose rows and columns are only approximately "
             "ruled")
    parser.add_argument("--dds", type=Path)
    args = parser.parse_args()

    source = Image.open(args.source).convert("RGBA")
    # Adding to an atlas means starting from it. Starting from a blank canvas
    # would silently drop every icon already in it.
    base = None
    if args.start_index and args.destination.exists():
        base = Image.open(args.destination).convert("RGBA")
    atlas = pack(source, args.source_grid, args.destination_grid,
                 args.cell_size, args.count, args.canvas_size, args.detect,
                 args.start_index, base)
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(args.destination, optimize=True)
    if args.dds is not None:
        write_dds(args.dds, atlas)


if __name__ == "__main__":
    main()

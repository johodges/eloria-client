#!/usr/bin/env python3
"""Generate original Eloria bootstrap assets without external source material."""

from __future__ import annotations

import argparse
import binascii
import json
from pathlib import Path
import struct
import zlib


def png(path: Path, width: int, height: int, pixel) -> None:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF))

    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            rows.extend(pixel(x, y))
    data = b"\x89PNG\r\n\x1a\n"
    data += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    data += chunk(b"IDAT", zlib.compress(bytes(rows), 9))
    data += chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def ground(x: int, y: int) -> tuple[int, int, int, int]:
    grain = ((x * 17 + y * 31 + (x ^ y) * 7) % 23) - 11
    path = abs(x - y) < 5 or abs((x + y) - 127) < 4
    base = (104, 100, 73) if path else (62, 91, 68)
    return (*(max(0, min(255, c + grain)) for c in base), 255)


def panel(x: int, y: int) -> tuple[int, int, int, int]:
    border = x < 5 or y < 5 or x >= 507 or y >= 507
    grid = x % 64 < 2 or y % 64 < 2
    if border:
        return 202, 125, 54, 255
    if grid:
        return 77, 60, 47, 255
    return 35, 43, 42, 255


def make_map(path: Path, width: int = 32, height: int = 32) -> None:
    """Write an object-free ELM with a fully walkable height field."""
    header_size = 120
    tiles = bytes([0]) * (width * height)
    heights = bytes([11]) * (width * height * 36)
    height_offset = header_size + len(tiles)
    object_offset = height_offset + len(heights)
    # ELM map_header: magic, 12 ints, four bytes, 3 floats, then 12 ints.
    ints_a = [width, height, header_size, height_offset,
              144, 0, object_offset, 128, 0, object_offset,
              40, 0, object_offset]
    header = bytearray(b"elmf")
    header.extend(struct.pack("<13i", *ints_a))
    header.extend(bytes([0, 1, 0, 0]))
    header.extend(struct.pack("<3f", 0.55, 0.58, 0.62))
    header.extend(struct.pack("<12i", 104, 0, object_offset, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    if len(header) != header_size:
        raise AssertionError(f"unexpected ELM header size: {len(header)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + tiles + heights)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", default="build/eloria-data")
    args = parser.parse_args()
    root = Path(args.output)
    png(root / "3dobjects/tile0.png", 128, 128, ground)
    for name in ("gamebuttons", "gamebuttons2", "console", "login_menu",
                 "login_back", "ground_detail", "items1", "sigils"):
        png(root / f"textures/{name}.png", 512, 512, panel)
    png(root / "maps/legend.png", 512, 512, panel)
    make_map(root / "maps/emberhaven.elm")
    (root / "servers.lst").write_text(
        "main eloria 127.0.0.1 2000 plain Eloria local server\n", encoding="utf-8")
    (root / "harvestable.lst").write_text("", encoding="utf-8")
    (root / "entrable.lst").write_text("", encoding="utf-8")
    (root / "ASSET_MANIFEST.json").write_text(json.dumps({
        "name": "Eloria bootstrap data",
        "license": "CC-BY-4.0",
        "generator": "eloria-assets/tools/generate_bootstrap_pack.py",
        "contains_eternal_lands_binary_data": False
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

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
    edge=min(x,y,511-x,511-y)
    corner=(x<34 and y<34) or (x>477 and y<34) or (x<34 and y>477) or (x>477 and y>477)
    if edge<3:return 221,164,72,255
    if edge<7:return 58,116,122,255
    if corner and (abs((x%478)-(y%478))<4 or abs((x%478)+(y%478)-32)<4):return 196,135,52,255
    grain=((x*11+y*17+(x^y)*3)%13)-6
    glow=max(0,18-int(((x-256)**2+(y-256)**2)**.5/13))
    return 19+grain//3,40+grain//2+glow//3,47+grain+glow,245


def make_map(path: Path, width: int = 32, height: int = 32, *,
             tile_id: int = 0, placements=None,
             ambient=(0.55, 0.58, 0.62), height_value: int = 11,
             lights=None, tile_at=None, height_at=None, objects_2d=None,
             placement_scale: float = 0.5) -> None:
    """Write an original ELM settlement with a fully walkable height field.

    Placement and light coordinates are authored in height-map cells, the same
    grid the tile and height callbacks and the server tile coordinates use.
    ELM object records store world units instead, and the client's own
    conversion is `world = 0.5 * cell` (map.c), so `placement_scale` converts
    them on write.  Writing cell coordinates straight into the record put
    every object at twice its intended distance from the map origin, which
    pushed most of a 32x32 map's content off the 96x96 unit terrain.
    """
    # map_header is 124 bytes in the current client.  The final reserved word
    # is still part of the on-disk structure even though it has no semantics.
    header_size = 124
    tiles = bytes((tile_at(x, y) if tile_at else tile_id)
                  for y in range(height) for x in range(width))
    if not 0 <= height_value <= 255:
        raise ValueError("height_value must fit in one ELM height byte")
    heights = bytes((height_at(x, y) if height_at else height_value)
                    for y in range(height * 6) for x in range(width * 6))
    height_offset = header_size + len(tiles)
    object_offset = height_offset + len(heights)
    default_placements = [
        ("3dobjects/scenery/cottage.e3d", 42, 42, 0, 0),
        ("3dobjects/scenery/cottage.e3d", 54, 45, 0, 90),
        ("3dobjects/scenery/dock.e3d", 78, 42, 0, 90),
        ("3dobjects/scenery/signpost.e3d", 61, 54, 0, 15),
        ("3dobjects/scenery/lantern.e3d", 58, 51, 0, 0),
        ("3dobjects/scenery/lantern.e3d", 66, 57, 0, 0),
        ("3dobjects/scenery/alder_tree.e3d", 35, 55, 0, 0),
        ("3dobjects/scenery/alder_tree.e3d", 72, 65, 0, 35),
        ("3dobjects/scenery/highland_pine.e3d", 28, 68, 0, 0),
        ("3dobjects/scenery/highland_pine.e3d", 84, 73, 0, 20),
        ("3dobjects/scenery/boulder.e3d", 91, 61, 0, 0),
        ("3dobjects/harvestables/sunleaf.e3d", 48, 66, 0, 0),
        ("3dobjects/harvestables/frost_reed.e3d", 75, 48, 0, 0),
        ("3dobjects/harvestables/copper_bloom.e3d", 55, 72, 0, 0),
        ("3dobjects/harvestables/ember_crystal.e3d", 88, 82, 0, 0),
        ("3dobjects/harvestables/slate_outcrop.e3d", 31, 82, 0, 0),
        ("3dobjects/interactives/portal_obelisk.e3d", 94, 58, 0, 90),
        ("3dobjects/interactives/storage_chest.e3d", 52, 58, 0, 0),
        ("3dobjects/interactives/forge.e3d", 70, 54, 0, 0),
        ("3dobjects/interactives/anvil.e3d", 68, 55, 0, 0),
        ("3dobjects/interactives/workbench.e3d", 66, 53, 0, 90),
        ("3dobjects/interactives/alchemy_table.e3d", 63, 53, 0, 90),
        ("3dobjects/interactives/training_dummy.e3d", 42, 78, 0, 0),
        ("3dobjects/interactives/notice_board.e3d", 58, 62, 0, 0),
        ("3dobjects/interactives/well.e3d", 61, 61, 0, 0),
        ("3dobjects/interactives/brazier.e3d", 72, 54, 0, 0),
    ]
    placements = default_placements if placements is None else placements
    records = bytearray()
    for filename, x, y, z, rotation in placements:
        encoded = filename.encode()[:79] + b"\0"
        records.extend(struct.pack("<80s6fBB2x4f20s", encoded.ljust(80, b"\0"),
            x * placement_scale, y * placement_scale, z, 0.0, 0.0, rotation,
            0, 0, 1.0, 1.0, 1.0, 1.0, b""))
    objects_end = object_offset + len(records)
    objects_2d = [] if objects_2d is None else objects_2d
    records_2d = bytearray()
    for filename, x, y, z, rotation in objects_2d:
        encoded = filename.encode()[:79] + b"\0"
        records_2d.extend(struct.pack("<80s6f24s", encoded.ljust(80, b"\0"),
            x * placement_scale, y * placement_scale, z, 0.0, 0.0, rotation,
            b""))
    objects_2d_end = objects_end + len(records_2d)
    lights = [] if lights is None else lights
    light_records = bytearray()
    for x, y, z, red, green, blue in lights:
        light_records.extend(struct.pack(
            "<7f12s", x * placement_scale, y * placement_scale, z,
            red, green, blue, 0.0, b""))
    lights_offset = objects_2d_end
    particles_offset = lights_offset + len(light_records)
    # ELM map_header: magic, 13 ints, four bytes, 3 floats, then 13 ints.
    ints_a = [width, height, header_size, height_offset,
              144, len(placements), object_offset,
              128, len(objects_2d), objects_end,
              40, len(lights), lights_offset]
    header = bytearray(b"elmf")
    header.extend(struct.pack("<13i", *ints_a))
    header.extend(bytes([0, 1, 0, 0]))
    header.extend(struct.pack("<3f", *ambient))
    header.extend(struct.pack("<13i", 104, 0, particles_offset,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    if len(header) != header_size:
        raise AssertionError(f"unexpected ELM header size: {len(header)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + tiles + heights + records + records_2d
                     + light_records)


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
    # cursors.c binary-searches these lists with an exact strcmp against the
    # lowercased *basename* of the object file (3d_objects.c), so relative
    # paths never match and leave the world unharvestable and unentrable.
    # generate_nymara_complete.py rewrites harvestable.lst with the full
    # Nymara catalogue once the region models exist.
    (root / "harvestable.lst").write_text("\n".join(sorted([
        "sunleaf.e3d",
        "frost_reed.e3d",
        "copper_bloom.e3d",
        "ember_crystal.e3d",
        "slate_outcrop.e3d",
    ])) + "\n", encoding="utf-8")
    (root / "entrable.lst").write_text("\n".join(sorted([
        "portal_obelisk.e3d",
        "storage_chest.e3d",
        "forge.e3d",
        "anvil.e3d",
        "workbench.e3d",
        "alchemy_table.e3d",
        "notice_board.e3d",
        "well.e3d",
    ])) + "\n", encoding="utf-8")
    (root / "ASSET_MANIFEST.json").write_text(json.dumps({
        "name": "Eloria bootstrap data",
        "license": "CC-BY-4.0",
        "generator": "eloria-assets/tools/generate_bootstrap_pack.py",
        "contains_eternal_lands_binary_data": False
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

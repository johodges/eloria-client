#!/usr/bin/env python3
"""Render a deterministic overhead QA image from a generated ELM map."""
from __future__ import annotations

import argparse
from pathlib import Path
import struct

from generate_bootstrap_pack import png


COLORS = {
    0: (112, 129, 82),
    1: (68, 94, 62),
    2: (194, 166, 103),
    3: (42, 137, 154),
    4: (157, 151, 126),
    5: (66, 91, 61),
    6: (187, 162, 108),
    7: (38, 128, 149),
}

REGIONAL_COLORS = {
    "amethyst_barrens": {
        0: (103, 73, 126), 1: (114, 91, 65),
        2: (182, 132, 194), 3: (139, 91, 164),
    },
    "sunmane_steppe": {
        0: (193, 151, 72), 1: (150, 105, 48),
        2: (211, 177, 99), 3: (120, 79, 38),
    },
    "amberwood": {
        0: (151, 91, 39), 1: (115, 71, 34),
        2: (184, 119, 55), 3: (65, 91, 55),
    },
    "grey_moors": {
        0: (92, 78, 96), 1: (69, 75, 66),
        2: (125, 109, 78), 3: (48, 67, 65),
    },
    "westhaven": {
        0: (33, 101, 122), 1: (83, 89, 83),
        2: (146, 113, 75), 3: (44, 127, 145),
    },
    "verdant_stair": {
        0: (52, 116, 67), 1: (34, 88, 56),
        2: (112, 103, 72), 3: (40, 117, 120),
    },
    "ssarathi_ruins": {
        0: (151, 126, 57), 1: (43, 94, 68),
        2: (112, 105, 69), 3: (38, 121, 116),
    },
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("map", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = args.map.read_bytes()
    width, height, tile_offset, height_offset = struct.unpack_from("<4i", data, 4)
    obj_size, obj_count, obj_offset = struct.unpack_from("<3i", data, 20)
    if data[:4] != b"elmf" or tile_offset != 124 or obj_size != 144:
        raise ValueError(f"unsupported ELM contract: {args.map}")
    tiles = data[tile_offset:height_offset]
    objects = []
    for index in range(obj_count):
        offset = obj_offset + index * obj_size
        name = struct.unpack_from("<80s", data, offset)[0].split(b"\0", 1)[0].decode()
        x, y = struct.unpack_from("<2f", data, offset + 80)
        objects.append((name, x / (width * 6) * 512, y / (height * 6) * 512))
    colors = REGIONAL_COLORS.get(args.map.stem, COLORS)

    def pixel(x: int, y: int):
        tile_x = min(width - 1, x * width // 512)
        tile_y = min(height - 1, y * height // 512)
        base = colors.get(tiles[tile_y * width + tile_x], (125, 70, 125))
        grain = ((x * 7 + y * 11) % 9) - 4
        color = tuple(max(0, min(255, channel + grain)) for channel in base)
        for name, object_x, object_y in objects:
            distance = (x - object_x) ** 2 + (y - object_y) ** 2
            if distance <= 16:
                if "gatehouse" in name:
                    color = (238, 204, 118)
                elif "bridge" in name:
                    color = (220, 188, 121)
                elif "tower" in name:
                    color = (222, 225, 205)
                elif "tree" in name:
                    color = (48, 91, 48)
                else:
                    color = (151, 116, 80)
        # Authoritative new-character spawn crosshair.
        spawn_x = 58 / (width * 6) * 512
        spawn_y = 58 / (height * 6) * 512
        if abs(x - spawn_x) <= 7 and abs(y - spawn_y) <= 1 \
                or abs(y - spawn_y) <= 7 and abs(x - spawn_x) <= 1:
            color = (255, 246, 185)
        return (*color, 255)

    png(args.output, 512, 512, pixel)


if __name__ == "__main__":
    main()

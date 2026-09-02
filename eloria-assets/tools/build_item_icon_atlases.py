#!/usr/bin/env python3
"""Pack the generated armour set's icons into the runtime item atlases.

Added 2026-09-02 for Eloria Client.

``import_generated_equipment`` defines the sixty wearables and gives each an
``image_id``; this is the other half of that contract, the one that makes
those ids resolve to pixels.  The icons themselves are rendered from the same
meshes by ``generate_models/equipment_icons`` (a sibling of this repository),
one 50px cell per piece, already framed like the painted set.  Everything
that knows the atlas shape is written here so it cannot drift apart --

  the pixels    godot-client/assets/ui/items/items5-8.png -- the blank tail
                of items5 takes the first seven, three new sheets the rest
  the sources   eloria-assets/ui/items/items5-8.dds, which the atlas test
                holds the shipped PNGs to
  the registry  godot-client/data/items/atlases.json
  the layout    eloria-assets/ui/items/atlas_layout.json

Ids are ``FIRST_IMAGE_ID + roster index`` in the fixed roster order, which
keeps the painted range contiguous: imageCount moves 118 -> 178 with no gap,
so ItemAtlas's painted-prefix contract and the fallback behaviour for
everything at 178 and above both hold.

  python build_item_icon_atlases.py            write everything
  python build_item_icon_atlases.py --dry-run  say what would change
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

import import_generated_equipment as ige

HERE = Path(__file__).resolve().parent
CLIENT = HERE.parent.parent / "godot-client"
ICONS = ige.PROJECT / "generate_models" / "equipment_icons" / "out" / "icons"
ATLAS_PNGS = CLIENT / "assets/ui/items"
ATLAS_CONFIG = CLIENT / "data/items/atlases.json"
ATLAS_DDS = HERE.parent / "ui/items"
LAYOUT = ATLAS_DDS / "atlas_layout.json"

CELL = 50
COLUMNS = 5
PER_ATLAS = 25
CANVAS = 256


def atlas_name(index: int) -> str:
    return "items%d.png" % (index + 1)


def read_atlas(index: int) -> Image.Image:
    path = ATLAS_PNGS / atlas_name(index)
    if path.exists():
        return Image.open(path).convert("RGBA")
    return Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))


def write_dds(index: int, image: Image.Image) -> Path:
    """The authored twin of a shipped atlas: plain 32-bit BGRA under the
    128-byte header every existing items*.dds carries (same size, same
    format), which is also exactly what the atlas test's reader assumes."""
    header = (ATLAS_DDS / "items1.dds").read_bytes()[:128]
    pixels = image.tobytes()
    bgra = bytearray(len(pixels))
    bgra[0::4] = pixels[2::4]
    bgra[1::4] = pixels[1::4]
    bgra[2::4] = pixels[0::4]
    bgra[3::4] = pixels[3::4]
    target = ATLAS_DDS / ("items%d.dds" % (index + 1))
    target.write_bytes(header + bytes(bgra))
    return target


def config_text(atlas_count: int, image_count: int) -> str:
    paths = ",\n".join('    "res://assets/ui/items/%s"' % atlas_name(i)
                       for i in range(atlas_count))
    return ("{\n"
            '  "cellSize": [50, 50],\n'
            '  "columns": 5,\n'
            '  "imagesPerAtlas": 25,\n'
            '  "imageCount": %d,\n'
            '  "fallbackImageId": 117,\n'
            '  "aliases": {\n'
            '    "397": 41,\n'
            '    "460": 49\n'
            "  },\n"
            '  "atlases": [\n%s\n  ]\n'
            "}\n" % (image_count, paths))


def main() -> int:
    ap = argparse.ArgumentParser(
        description="pack the generated set's rendered icons into the atlases")
    ap.add_argument("--icons", type=Path, default=ICONS,
                    help="directory of 50px per-piece icons")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pieces = ige.roster()
    missing = [p.slug for p in pieces
               if not (args.icons / (p.source.stem + ".png")).exists()]
    if missing:
        print("no rendered icon for: %s" % ", ".join(missing), file=sys.stderr)
        print("(render them with generate_models/equipment_icons/make_icons.py)",
              file=sys.stderr)
        return 2

    image_count = max(p.image_id for p in pieces) + 1
    atlas_count = (image_count + PER_ATLAS - 1) // PER_ATLAS
    touched = sorted({p.image_id // PER_ATLAS for p in pieces})
    print("%d icons -> ids %d-%d across %s, imageCount %d"
          % (len(pieces), min(p.image_id for p in pieces),
             image_count - 1, ", ".join(atlas_name(i) for i in touched),
             image_count))
    if args.dry_run:
        print("nothing written (--dry-run)")
        return 0

    atlases = {index: read_atlas(index) for index in touched}
    for piece in pieces:
        icon = Image.open(args.icons / (piece.source.stem + ".png"))
        icon = icon.convert("RGBA")
        if icon.size != (CELL, CELL):
            icon = icon.resize((CELL, CELL), Image.LANCZOS)
        row, column = divmod(piece.image_id % PER_ATLAS, COLUMNS)
        atlases[piece.image_id // PER_ATLAS].paste(
            icon, (column * CELL, row * CELL))

    for index, image in sorted(atlases.items()):
        target = ATLAS_PNGS / atlas_name(index)
        image.save(target)
        print("wrote %s" % target)
        print("wrote %s" % write_dds(index, image))

    ATLAS_CONFIG.write_text(config_text(atlas_count, image_count),
                            encoding="utf-8")
    print("wrote %s" % ATLAS_CONFIG)

    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
    layout["imageCount"] = image_count
    layout["rowOffsets"] = [0] * atlas_count
    layout["note"] = (
        "Rows each atlas sits below the grid ItemAtlas samples. IDs 100-116 "
        "mirror the Nymara resource image IDs emitted by eloria-server; 117 "
        "is the dedicated unknown-item fallback; 118-%d are the generated "
        "armour set's per-piece renders, assigned in the "
        "import_generated_equipment roster order." % (image_count - 1))
    LAYOUT.write_text(json.dumps(layout, indent=1) + "\n", encoding="utf-8")
    print("wrote %s" % LAYOUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())

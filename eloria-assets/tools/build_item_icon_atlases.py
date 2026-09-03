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
  the registry  godot-client/data/items/atlases.json
  the layout    godot-client/data/items/atlas_layout.json

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
import import_generated_weapons as igw
import potion_icons

HERE = Path(__file__).resolve().parent
CLIENT = HERE.parent.parent / "godot-client"
ICONS = ige.PROJECT / "generate_models" / "equipment_icons" / "out" / "icons"
WEAPON_ICONS = (ige.PROJECT / "generate_models" / "weapon_icons"
                / "out" / "icons")
ATLAS_PNGS = CLIENT / "assets/ui/items"
ATLAS_CONFIG = CLIENT / "data/items/atlases.json"
LAYOUT = CLIENT / "data/items/atlas_layout.json"

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
                    help="directory of 50px per-piece armour icons")
    ap.add_argument("--weapon-icons", type=Path, default=WEAPON_ICONS,
                    help="the same for the weapon and shield set")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # All three generated sets, armour first.  Their image ids are handed out
    # from a single run of numbers -- the armour from 118, the weapons from
    # 374, the potion shelf from 480 -- so the painted prefix stays contiguous
    # and one atlas series carries everything.  Packing them separately would
    # leave a hole at whichever boundary the shorter set stopped at.
    # Each rendered set carries its own icon directory; the potions have no
    # meshes and are painted here instead of read from disk.
    pieces, icon_of = [], {}
    for roster, icons in ((ige.roster(), args.icons),
                          (igw.roster(), args.weapon_icons)):
        for piece in roster:
            pieces.append(piece)
            icon_of[piece.image_id] = icons / (piece.source.stem + ".png")

    missing = [p.slug for p in pieces if not icon_of[p.image_id].exists()]
    if missing:
        print("no rendered icon for: %s" % ", ".join(missing), file=sys.stderr)
        print("(render them with make_icons.py in the matching "
              "generate_models/*_icons directory)",
              file=sys.stderr)
        return 2

    potions = potion_icons.roster()
    pieces.extend(potions)

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
        if piece.image_id in icon_of:
            icon = Image.open(icon_of[piece.image_id]).convert("RGBA")
            if icon.size != (CELL, CELL):
                icon = icon.resize((CELL, CELL), Image.LANCZOS)
        else:
            icon = potion_icons.paint(piece)
        row, column = divmod(piece.image_id % PER_ATLAS, COLUMNS)
        atlases[piece.image_id // PER_ATLAS].paste(
            icon, (column * CELL, row * CELL))

    for index, image in sorted(atlases.items()):
        target = ATLAS_PNGS / atlas_name(index)
        image.save(target)
        print("wrote %s" % target)

    ATLAS_CONFIG.write_text(config_text(atlas_count, image_count),
                            encoding="utf-8")
    print("wrote %s" % ATLAS_CONFIG)

    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
    layout["imageCount"] = image_count
    layout["rowOffsets"] = [0] * atlas_count
    layout["note"] = (
        "Rows each atlas sits below the grid ItemAtlas samples. IDs 100-116 "
        "mirror the Nymara resource image IDs emitted by eloria-server; 117 "
        "is the dedicated unknown-item fallback; 118 up are the generated "
        "sets' per-piece icons -- armour from 118 and weapons from 374 in "
        "their import roster orders, the painted potion shelf from %d "
        "(potion_icons roster order) -- ending at %d."
        % (potion_icons.FIRST_IMAGE_ID, image_count - 1))
    LAYOUT.write_text(json.dumps(layout, indent=1) + "\n", encoding="utf-8")
    print("wrote %s" % LAYOUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Take the generated armour set into the client and the server, in one pass.

Added 2026-09-01 for Eloria Client.

``conform_equipment`` turns one generated mesh into one wearable GLB.  This is
the other half: which sixty meshes, what each of them is, where its geometry
lands, and the two halves of the definition that make it a thing a player can
own.  A wearable is not one record but four, joined only by the item's name --

  the mesh          godot-client/assets/actors/native/equipment/<slug>.glb
  the client entry  godot-client/data/actors/equipment.json, models["part:id"]
  the server item   dev-server/config/eloria/items.txt, an [item] block
  the server visual dev-server/eloria/items.py, EQUIPMENT_VISUAL_OVERRIDES

-- and a set added to one side and not the other is either armour that draws
nothing or geometry nobody can wear.  All four are written here so they cannot
drift apart.

  python import_generated_equipment.py                 build and write
  python import_generated_equipment.py --dry-run       say what would change
  python import_generated_equipment.py --sheet arcane_ethereal

Idempotent.  The server blocks are fenced by markers and rewritten whole; the
client entries are merged into the registry by key, so the authored models
around them are left alone rather than regenerated.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import conform_equipment as ce
import equipment_authoring as ea

HERE = Path(__file__).resolve().parent
CLIENT = HERE.parent.parent / "godot-client"
PROJECT = HERE.parent.parent.parent
SERVER = PROJECT / "dev-server"
GENERATED = PROJECT / "generate_models" / "meshy-armor-individual-glb"

EQUIPMENT = CLIENT / "assets/actors/native/equipment"
REGISTRY = CLIENT / "data/actors/equipment.json"

OPEN_ITEMS = "# --- generated armour set (tools/import_generated_equipment.py) ---"
CLOSE_ITEMS = "# --- end generated armour set ---"
OPEN_PY = "    # --- generated armour set (eloria-assets/tools/import_generated_equipment.py) ---"
CLOSE_PY = "    # --- end generated armour set ---"

#: Where the catalogue starts.  1274 is the first id after the shipped items,
#: and the icon contract in tests/test_item_icon_contract.py stops at 1272, so
#: nothing here is inside a range that test pins.
FIRST_ITEM_ID = 1274

#: What a piece of each finish is worth, as (emu, armour low/high, defense).
#: The ladder is the one tools/sync_torso_items.py already established for the
#: torso designs, so a generated piece is worth what an authored one of the
#: same material is worth.
FINISH_STATS = {
    "cloth": (4, (0, 2), 0),
    "leather": (8, (2, 8), -1),
    "mail": (14, (3, 12), -2),
    "plate": (18, (4, 16), -3),
}

#: Where the set's inventory icons start.  Each piece gets its own icon --
#: rendered from its mesh by generate_models/equipment_icons and packed into
#: the runtime atlases by tools/build_item_icon_atlases.py, which assigns ids
#: in this same roster order.  118 is the first cell after the shipped painted
#: range: the blank tail of items5.png takes seven, items6-8.png the rest, so
#: the painted prefix stays contiguous and imageCount moves 118 -> 178.
FIRST_IMAGE_ID = 118

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]

#: One row per concept sheet: the stem it generated under, what the pieces are,
#: and where their visual ids begin.  The ranges start above every id the
#: registry already uses (helmet 108, legs 170, body 183, boots 191) and stay
#: inside a byte, which is all ACTOR_WEAR_ITEM gives a visual.
SHEETS = [
    ("Amberwood_Woodland_Armor_Concept_Sheet", "Amberwood Woodland Cuirass",
     "amberwood_woodland_cuirass", "cuirass", 5, 184, "leather"),
    ("Amberwood_Woodland_Legwear_Concept_Sheet", "Amberwood Woodland Legguards",
     "amberwood_woodland_legguards", "legs", 4, 171, "leather"),
    ("Arcane_Fantasy_Boots_Concept_Sheet", "Arcane Fantasy Boots",
     "arcane_fantasy_boots", "boots", 6, 192, "leather"),
    ("Arcane_ethereal_headgear_design_sheet", "Arcane Ethereal Circlet",
     "arcane_ethereal_circlet", "circlet", 3, 109, "cloth"),
    ("Eight_amberwood_forest_headgear_designs", "Amberwood Forest Helm",
     "amberwood_forest_helm", "helm", 3, 117, "mail"),
    ("Eight_amberwood_woodland_boot_designs", "Amberwood Woodland Boots",
     "amberwood_woodland_boots", "boots", 6, 200, "leather"),
    ("Eight_arcane_leg_armor_designs", "Arcane Leg Armor",
     "arcane_leg_armor", "legs", 4, 179, "plate"),
    ("Eight_ceremonial_knight_leg_armor_designs", "Ceremonial Knight Greaves",
     "ceremonial_knight_greaves", "legs", 4, 187, "plate"),
    # The rest of the concept art, appended rather than inserted: `roster`
    # hands out item ids in this order, so a row added anywhere but the end
    # would renumber every piece below it and break the names the server
    # already ships.  Ceremonial above is the one sheet that was cut mid-way by
    # a --limit, and it simply grows from four pieces to eight -- the four it
    # has keep their numerals and visuals because the sources sort before the
    # new ones.
    #
    # Visual ranges continue above what each part already uses (helmet 124,
    # legs 190, body 191, boots 207) and stay inside a byte, which is all
    # ACTOR_WEAR_ITEM carries.  Legs is the tight one: it ends at 250 with five
    # spare, so another leg sheet after this needs the range reclaimed rather
    # than extended.
    ("Eight_Legendary_Helms_of_Eloria", "Legendary Eloria Helm",
     "legendary_eloria_helm", "helm", 3, 125, "plate"),
    ("Eight_grounded_militia_helmet_designs", "Militia Helmet",
     "militia_helmet", "helm", 3, 133, "mail"),
    ("Refined_knightly_headgear_concept_sheet", "Knightly Headgear",
     "knightly_headgear", "helm", 3, 141, "mail"),
    ("Eight_frontier_hats_concept_sheet", "Frontier Hat",
     "frontier_hat", "hood", 3, 149, "cloth"),
    ("Eight_leather_adventurer_headwear_designs", "Adventurer Headwear",
     "adventurer_headwear", "hood", 3, 157, "leather"),
    ("Sunmane_Steppe_Headgear_Collection", "Sunmane Steppe Headgear",
     "sunmane_steppe_headgear", "hood", 3, 165, "leather"),

    ("Eight_legendary_hero_armor_designs", "Legendary Hero Cuirass",
     "legendary_hero_cuirass", "cuirass", 5, 192, "plate"),
    ("Eight_refined_knightly_torso_armor_designs", "Knightly Torso Armor",
     "knightly_torso_armor", "cuirass", 5, 200, "mail"),
    ("Militia_torso_armor_concept_sheet", "Militia Torso Armor",
     "militia_torso_armor", "cuirass", 5, 208, "mail"),
    ("Eloria_Arcane_Armor_Design_Sheet", "Eloria Arcane Armor",
     "eloria_arcane_armor", "cuirass", 5, 216, "plate"),
    ("Eight_leather_ranger_torso_designs", "Leather Ranger Torso",
     "leather_ranger_torso", "cuirass", 5, 224, "leather"),
    ("Eight_Eloria_frontier_shirt_designs", "Eloria Frontier Shirt",
     "eloria_frontier_shirt", "shirt", 5, 232, "cloth"),
    ("Sunmane_Steppe_Shirts_and_Armor", "Sunmane Steppe Shirt",
     "sunmane_steppe_shirt", "shirt", 5, 240, "cloth"),

    ("Eight_legendary_fantasy_leg_armor_designs", "Legendary Leg Armor",
     "legendary_leg_armor", "legs", 4, 195, "plate"),
    ("Eight_Refined_Knightly_Greave_Designs", "Knightly Greaves",
     "knightly_greaves", "legs", 4, 203, "mail"),
    ("Eight_medieval_militia_greaves", "Militia Greaves",
     "militia_greaves", "legs", 4, 211, "mail"),
    ("Eloria_Militia_Leg_Armor_Variants", "Militia Leg Armor",
     "militia_leg_armor", "legs", 4, 219, "mail"),
    ("Eight_rugged_ranger_legwear_designs", "Rugged Ranger Legwear",
     "rugged_ranger_legwear", "legs", 4, 227, "leather"),
    ("Sunmane_Steppe_Legwear_Concept_Sheet", "Sunmane Steppe Legwear",
     "sunmane_steppe_legwear", "legs", 4, 235, "leather"),
    ("Eight_Humble_Frontier_Pants_Designs", "Humble Frontier Pants",
     "humble_frontier_pants", "pants", 4, 243, "cloth"),

    ("Legendary_Eloria_Fantasy_Boots_Concept_Sheet", "Legendary Eloria Boots",
     "legendary_eloria_boots", "boots", 6, 208, "plate"),
    ("Eight_Sunmane_Steppe_Boot_Designs", "Sunmane Steppe Boots",
     "sunmane_steppe_boots", "boots", 6, 216, "leather"),
    ("Eight_frontier_boot_designs", "Frontier Boots",
     "frontier_boots", "boots", 6, 224, "leather"),
    ("Eight_leather_adventurer_boot_designs", "Leather Adventurer Boots",
     "leather_adventurer_boots", "boots", 6, 232, "leather"),
]


class Piece:
    __slots__ = ("source", "slug", "name", "kind", "part", "visual", "finish",
                 "item_id", "image_id")

    def __init__(self, source, slug, name, kind, part, visual, finish,
                 item_id, image_id):
        self.source, self.slug, self.name = source, slug, name
        self.kind, self.part, self.visual = kind, part, visual
        self.finish, self.item_id, self.image_id = finish, item_id, image_id


def roster() -> list[Piece]:
    """Every generated piece, in a fixed order so ids never move."""
    pieces: list[Piece] = []
    item_id = FIRST_ITEM_ID
    for stem, label, slug, kind, part, first_visual, finish in SHEETS:
        sources = sorted(GENERATED.glob(stem + "__*.glb"))
        # Only sources that have been through the preprocessing pass (which
        # leaves the raw meshy export beside them as ``.glb.orig``): a raw
        # drop-in would otherwise be swept into the roster the moment it
        # lands, defining items whose icons and compressed textures do not
        # exist yet.
        ready = [s for s in sources
                 if s.with_name(s.name + ".orig").exists()]
        for skipped in (s for s in sources if s not in ready):
            print("  %s has no .orig sibling (unprocessed) -- skipped"
                  % skipped.name)
        for index, source in enumerate(ready):
            if index >= len(ROMAN):
                print("  more than %d in %s, skipping %s"
                      % (len(ROMAN), stem, source.name))
                continue
            pieces.append(Piece(
                source, "%s_%02d" % (slug, index + 1),
                "%s %s" % (label, ROMAN[index]), kind, part,
                first_visual + index, finish, item_id,
                FIRST_IMAGE_ID + (item_id - FIRST_ITEM_ID)))
            item_id += 1
    return pieces


def item_block(piece: Piece) -> str:
    emu, (low, high), defense = FINISH_STATS[piece.finish]
    slot = {3: "head", 4: "legs", 5: "body", 6: "feet"}[piece.part]
    lines = ["", "[item]",
             "name: %s" % piece.name,
             "item_id: %d" % piece.item_id,
             "image_id: %d" % piece.image_id,
             "emu: %d" % emu,
             "flags: 2",
             "category: Armor",
             "description: Generated from the %s concept sheet."
             % piece.source.stem.split("__")[0].replace("_", " ").strip(),
             "equip_type: %s" % slot,
             "armor: %d/%d" % (low, high)]
    if defense:
        lines.append("defense: %d" % defense)
    lines.append("[/item]")
    return "\n".join(lines)


def fence(text: str, opener: str, closer: str, body: str) -> str:
    """Replace a marked block, or add one at the end if there is none yet."""
    block = "%s\n%s\n%s" % (opener, body, closer)
    pattern = re.compile("%s.*?%s" % (re.escape(opener), re.escape(closer)),
                         re.S)
    if pattern.search(text):
        return pattern.sub(lambda _: block, text, count=1)
    return text.rstrip("\n") + "\n\n" + block + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="build the generated armour set and define it on both sides")
    ap.add_argument("--race", default="luminous_male")
    ap.add_argument("--sheet", default=None,
                    help="only pieces whose slug starts with this")
    ap.add_argument("--server", type=Path, default=SERVER,
                    help="dev-server checkout to write the item definitions "
                         "into (a worktree, say); default the sibling one")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-build", action="store_true",
                    help="rewrite the definitions without rebuilding meshes")
    ap.add_argument("--meshes-only", action="store_true",
                    help="rebuild meshes and leave every definition alone: "
                         "the item stats belong to whoever balances them, and "
                         "a refit has no business restating them")
    args = ap.parse_args()
    items_path = args.server / "config/eloria/items.txt"
    items_py_path = args.server / "eloria/items.py"

    if not GENERATED.is_dir():
        print("no generated meshes at %s" % GENERATED)
        return 2
    pieces = [p for p in roster()
              if not args.sheet or p.slug.startswith(args.sheet)]
    if not pieces:
        print("nothing matched")
        return 2

    by_part: dict[int, int] = {}
    for piece in pieces:
        by_part[piece.part] = by_part.get(piece.part, 0) + 1
    print("%d piece(s): %s" % (len(pieces), ", ".join(
        "part %d x%d" % (part, count) for part, count in sorted(by_part.items()))))
    if args.dry_run:
        for piece in pieces:
            print("  %-34s %-9s part %d visual %-4d item %d icon %d"
                  % (piece.slug, piece.kind, piece.part, piece.visual,
                     piece.item_id, piece.image_id))
        print("\nnothing written (--dry-run)")
        return 0

    race_path = ce.RACES / ("%s.glb" % args.race)
    rig = ea.load_rig(race_path, ce.BODY_MESH)
    built, failed = 0, 0
    if not args.skip_build:
        EQUIPMENT.mkdir(parents=True, exist_ok=True)
        for piece in pieces:
            target = EQUIPMENT / ("%s.glb" % piece.slug)
            try:
                info = ce.build(piece.source, target, rig, piece.kind,
                                piece.name, race_path=race_path)
            except Exception as exc:                    # noqa: BLE001
                print("  FAILED %-32s %s" % (piece.slug, exc))
                failed += 1
                continue
            built += 1
            posed = []
            for step in info.get("repose", []):
                if step.get("applied"):
                    posed.append("%s %+.0f" % (step["limb"].split("_")[0][0]
                                               + step["limb"][-1],
                                               step.get("poseDeg", 0.0)))
            print("  %-34s %-7s %5d verts  %.2f MB  %s"
                  % (piece.slug, info.get("attach", "skinned"),
                     info["vertices"], info["bytes"] / 1e6,
                     "pose " + " ".join(posed) if posed else ""))

    if args.meshes_only:
        print("\nmeshes only: %d built, %d failed -- registry, items and "
              "visuals left untouched" % (built, failed))
        return 0 if failed == 0 else 1

    # Definitions always cover the WHOLE roster: --sheet narrows which
    # meshes rebuild, but the fences are rewritten whole, and writing them
    # from the filtered list silently drops every other piece's item.
    everyone = roster()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    for piece in everyone:
        entry = {"scene": "res://assets/actors/native/equipment/%s.glb"
                          % piece.slug,
                 "name": piece.name}
        if piece.kind in ea.GARMENT_KINDS:
            entry["attach"] = "skinned"
            entry["skinRegion"] = ea.garment_region(piece.kind)
            entry["kind"] = piece.kind
            entry["authoredFor"] = args.race
        else:
            entry["attach"] = "socket"
            if piece.part == 3:
                entry["hides"] = list(ea.PARTS[3]["hides"])
        registry["models"]["%d:%d" % (piece.part, piece.visual)] = entry
    REGISTRY.write_text(json.dumps(registry, indent=2) + "\n",
                        encoding="utf-8")

    items = items_path.read_text(encoding="utf-8")
    body = "\n".join(item_block(piece) for piece in everyone).lstrip("\n")
    items_path.write_text(fence(items, OPEN_ITEMS, CLOSE_ITEMS, body),
                          encoding="utf-8")

    source = items_py_path.read_text(encoding="utf-8")
    rows = "\n".join('    "%s": (%d, %d),'
                     % (piece.name.casefold(), piece.part, piece.visual)
                     for piece in everyone)
    if OPEN_PY in source:
        source = fence(source, OPEN_PY, CLOSE_PY, rows)
    else:
        # Into the override table itself, immediately before it closes.
        marker = '    "spauldered breastplate": (5, 183),\n}'
        if marker not in source:
            print("could not find the end of EQUIPMENT_VISUAL_OVERRIDES")
            return 2
        source = source.replace(
            marker,
            '    "spauldered breastplate": (5, 183),\n%s\n%s\n%s\n}'
            % (OPEN_PY, rows, CLOSE_PY), 1)
    items_py_path.write_text(source, encoding="utf-8")

    print("\n%d built, %d failed" % (built, failed))
    print("  meshes   %s" % EQUIPMENT)
    print("  registry %s" % REGISTRY)
    print("  items    %s" % items_path)
    print("  visuals  %s" % items_py_path)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

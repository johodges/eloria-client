#!/usr/bin/env python3
"""Generate Eloria's original biome regions and machine-readable node catalog."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from generate_bootstrap_pack import make_map, png


def tile(colors):
    def pixel(x, y):
        noise = ((x * 19 + y * 37 + (x ^ y) * 5) % 19) - 9
        base = colors[((x // 24) + (y // 24)) % len(colors)]
        return (*(max(0, min(255, c + noise)) for c in base), 255)
    return pixel


def p(model, x, y, rotation=0, resource=None):
    return {"model": model, "x": x, "y": y, "rotation": rotation,
            "resource": resource}


REGIONS = {
    "glasswind": {
        "title": "Glasswind Expanse", "tile": ((166, 137, 78), (139, 112, 68)),
        "ambient": (.72, .61, .45),
        "objects": [
            p("biomes/desert/palm", 34, 68), p("biomes/desert/cactus", 71, 39),
            p("biomes/desert/dead_tree", 84, 75, 20), p("biomes/desert/dune_grass", 43, 83),
            p("architecture/stone_wall", 50, 52), p("architecture/gate_arch", 58, 52),
            p("architecture/stone_tower", 68, 54),
            p("harvestables/sage", 39, 72, resource="Sage"),
            p("harvestables/rosemary", 75, 67, resource="Rosemary"),
            p("harvestables/sulfur", 88, 62, resource="Sulfur"),
            p("harvestables/quartz", 29, 49, resource="Quartz")],
    },
    "frostmere": {
        "title": "Frostmere Shelf", "tile": ((176, 195, 196), (128, 154, 160)),
        "ambient": (.58, .67, .72),
        "objects": [
            p("biomes/snow/snow_pine", 31, 43), p("biomes/snow/snow_pine", 79, 73, 25),
            p("biomes/snow/ice_boulder", 67, 37), p("architecture/stone_tower", 51, 58),
            p("architecture/castle_battlement", 59, 58), p("architecture/stone_wall", 67, 58),
            p("harvestables/frost_reed", 38, 69, resource="Frost Reed"),
            p("harvestables/flax", 73, 76, resource="Flax"),
            p("harvestables/iron_ore", 83, 47, resource="Iron Ore"),
            p("harvestables/slate_outcrop", 27, 78, resource="Slate")],
    },
    "mirefen": {
        "title": "Mirefen Basin", "tile": ((55, 78, 62), (72, 85, 58)),
        "ambient": (.39, .48, .43),
        "objects": [
            p("biomes/swamp/cypress", 34, 44), p("biomes/swamp/cypress", 76, 71, 30),
            p("scenery/dock", 58, 48, 90), p("architecture/bridge_segment", 58, 62),
            p("scenery/lantern", 53, 55), p("scenery/lantern", 64, 55),
            p("harvestables/mushroom", 42, 71, resource="Mushroom"),
            p("harvestables/blueberries", 73, 45, resource="Blue Berries"),
            p("harvestables/cotton", 82, 79, resource="Cotton"),
            p("harvestables/copper_bloom", 29, 79, resource="Copper Bloom")],
    },
    "verdant_reach": {
        "title": "Verdant Reach", "tile": ((48, 104, 61), (65, 119, 66)),
        "ambient": (.48, .64, .49),
        "objects": [
            p("biomes/tropical/giant_fern", 31, 38), p("biomes/tropical/giant_fern", 81, 71, 20),
            p("scenery/alder_tree", 38, 76), p("scenery/cottage", 58, 54),
            p("architecture/timber_wall", 49, 60), p("architecture/roof_section", 67, 55),
            p("harvestables/sunleaf", 39, 67, resource="Sunleaf"),
            p("harvestables/lavender", 73, 68, resource="Lavender"),
            p("harvestables/wheat", 80, 45, resource="Wheat"),
            p("harvestables/rosemary", 27, 52, resource="Rosemary")],
    },
    "cinder_wastes": {
        "title": "Cinder Wastes", "tile": ((61, 53, 50), (91, 57, 43)),
        "ambient": (.58, .38, .31),
        "objects": [
            p("biomes/volcanic/basalt_spire", 33, 41), p("biomes/volcanic/lava_rock", 78, 71),
            p("architecture/stone_wall", 48, 55), p("architecture/gate_arch", 58, 55),
            p("architecture/column", 68, 55), p("scenery/lantern", 58, 62),
            p("harvestables/ember_crystal", 39, 72, resource="Ember Crystal"),
            p("harvestables/coal", 76, 78, resource="Coal"),
            p("harvestables/sulfur", 84, 47, resource="Sulfur"),
            p("harvestables/slate_outcrop", 28, 78, resource="Slate")],
    },
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", default="build/eloria-data")
    root = Path(parser.parse_args().output)
    catalog = {"schema": 1, "regions": []}
    for tile_id, (map_id, spec) in enumerate(REGIONS.items(), 1):
        png(root / f"3dobjects/tile{tile_id}.png", 128, 128, tile(spec["tile"]))
        objects = spec["objects"]
        placements = [(f"3dobjects/{o['model']}.e3d", o["x"], o["y"], 0,
                       o["rotation"]) for o in objects]
        make_map(root / f"maps/{map_id}.elm", tile_id=tile_id,
                 placements=placements, ambient=spec["ambient"])
        catalog["regions"].append({
            "id": map_id, "title": spec["title"], "map": f"maps/{map_id}.elm",
            "arrival": [58, 58],
            "harvest_nodes": [{"object_id": index, "x": o["x"], "y": o["y"],
                               "resource": o["resource"]}
                              for index, o in enumerate(objects) if o["resource"]]})
    (root / "regions_eloria.json").write_text(json.dumps(catalog, indent=2) + "\n",
                                               encoding="utf-8")


if __name__ == "__main__":
    main()

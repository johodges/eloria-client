#!/usr/bin/env python3
"""Generate original icons and landmark props for Nymara specialty events."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from generate_bootstrap_pack import png
from generate_scenery import box, crossed_leaves, e3d, tapered

EVENTS = {
    "world_boss": ((184, 58, 48), "Obsidian World-Boss Standard"),
    "caravan": ((207, 145, 62), "Sunroad Caravan Beacon"),
    "harvest_surge": ((84, 157, 91), "Verdant Harvest Shrine"),
    "arcane_instability": ((117, 92, 202), "Unstable Arcane Prism"),
    "relic_expedition": ((205, 178, 91), "Expedition Relic Plinth"),
    "construction": ((172, 112, 62), "Community Construction Frame"),
    "merchant_fair": ((222, 104, 139), "Merchant Fair Pavilion"),
    "migration": ((82, 158, 179), "Migration Waystone"),
    "control_points": ((214, 89, 64), "Contested Control Standard"),
    "cataclysm": ((214, 91, 37), "Cataclysm Vent"),
    "bounty_season": ((117, 165, 71), "Bounty Hunter Totem"),
    "shifting_labyrinth": ((73, 173, 181), "Labyrinth Gate"),
}

def icon_pixel(accent):
    def pixel(x, y):
        dx, dy = x - 32, y - 32
        ring = 19 * 19 < dx * dx + dy * dy < 27 * 27
        rune = abs(dx) < 4 or abs(dy) < 4 or abs(abs(dx) - abs(dy)) < 3
        if ring or (rune and dx * dx + dy * dy < 18 * 18): return (*accent, 255)
        return (13, 24, 31, 235 if dx * dx + dy * dy < 30 * 30 else 0)
    return pixel

def prop(index):
    def build(v, i):
        style = index % 6
        if style == 0:
            tapered(v, i, 0, 3.4, .46, .26, 8); tapered(v, i, 2.7, 4.5, 1.25, 0, 6)
        elif style == 1:
            box(v, i, (0, 0, .35), (3.2, 1.7, .7)); box(v, i, (0, 0, 1.15), (2.1, 1.2, .9)); tapered(v, i, 1.5, 2.5, .7, 0, 6)
        elif style == 2:
            crossed_leaves(v, i, 0, 2.0, 2.2, 6); tapered(v, i, 0, 2.8, .22, .08, 8)
        elif style == 3:
            for x, y, h in ((0, 0, 3.6), (.7, .15, 2.5), (-.65, .2, 2.8)):
                tapered(v, i, 0, h, .38, 0, 5, (x, y))
        elif style == 4:
            box(v, i, (0, 0, .45), (2.5, 2.0, .9)); tapered(v, i, .9, 3.2, .8, .34, 8)
        else:
            box(v, i, (-1.15, 0, 1.8), (.5, .7, 3.6)); box(v, i, (1.15, 0, 1.8), (.5, .7, 3.6)); box(v, i, (0, 0, 3.3), (2.8, .7, .5))
    return build

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", default="build/eloria-data")
    root = Path(parser.parse_args().output)
    manifest = []
    for index, (key, (accent, title)) in enumerate(EVENTS.items()):
        icon = root / "textures" / "events" / f"{key}.png"
        model = root / "3dobjects" / "events" / f"{key}.e3d"
        texture = model.with_suffix(".png")
        png(icon, 64, 64, icon_pixel(accent))
        png(texture, 128, 128, lambda x, y, c=accent: (*tuple(max(0, min(255, q + (18 if (x//16+y//16)%2 else -12))) for q in c), 255))
        e3d(model, texture.name, prop(index))
        manifest.append({"key": key, "title": title,
                         "icon": f"textures/events/{key}.png",
                         "prop": f"3dobjects/events/{key}.e3d"})
    (root / "special_event_assets.json").write_text(
        json.dumps({"version": 1, "events": manifest}, indent=2) + "\n",
        encoding="utf-8")

if __name__ == "__main__": main()

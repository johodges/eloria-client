#!/usr/bin/env python3
"""Join the continent graph to the packages and write the server's portal table.

    python eloria-assets/tools/continent_portals.py --server ../dev-server \
        --maps <dir generate_nymara_maps.py wrote to> [--apply]

`maps/nymara-regions/region-connections.json` says which region touches which
and by which portal id. Each region package's `world.json` says where that
portal stands and which server tile it is, and it says the same of every door
into the region's insides. The insides package says where each door's arrival
is. The server's generated maps say which tiles a player can stand on. This
puts them together:

* every declared link resolves to a portal on both ends, or it is an error;
* each direction becomes one `portal | map | x | y | dest | ax | ay` line,
  the trigger on the source portal's tile and the arrival two tiles in from
  the destination portal's tile, on ground the destination map lets a player
  stand on (the arrival is walked inward until it is);
* every door a region declares into its insides map becomes a pair: the
  region's door tile lands on the insides arrival for that door, and that
  arrival tile (where the insides package puts its return portal) lands two
  tiles from the door outside;
* `--apply` rewrites the block of `config/eloria/maps.txt` between its two
  markers and leaves every other line - bootstrap maps, Sunmane's caves,
  comments - exactly as it was.

Crownwater's quays serve several routes each, so a quay may carry a second
portal a few tiles along the dock; the graph names those with a suffix and the
package declares them as separate portals on separate tiles.

Sunmane's caves are not generated here: their tiles are a tested contract in
`tests/test_nymara_maps.py` and stay in the hand-written block below this one.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1]
REGIONS = ASSETS / "maps" / "nymara-regions"
INTERIORS = REGIONS / "interiors"
GRAPH = REGIONS / "region-connections.json"
PACKAGES = {"four_gates": ASSETS / "maps" / "four-gates"}

# region -> (insides package directory, the map id the server serves it as)
INSIDES = {
    "amethyst_barrens": ("amethyst_barrens_insides", "resonant_vault"),
    "grey_moors": ("grey_moors_insides", "grey_moor_barrows"),
    "westhaven": ("westhaven_insides", "westhaven_insides"),
    "verdant_stair": ("verdant_stair_insides", "verdant_stair_insides"),
    "manymouth_delta": ("manymouth_delta_insides", "manymouth_flooded_labyrinth"),
    "whitehorn_range": ("whitehorn_insides", "whitehorn_glacier_temple"),
    "ssarathi_ruins": ("ssarathi_insides", "ssarathi_royal_archive"),
    "crownwater": ("crownwater_insides", "drowned_crown"),
    "mirrorhold": ("mirrorhold_interiors", "mirrorhold_interiors"),
    # Amberwood's four interiors are separate client packages composed onto
    # one server map; `amberwood_insides/world.json` records where each one's
    # tile origin lands on the composed grid.
    "amberwood": ("amberwood_insides", "amberwood_estate"),
}

BEGIN = "# --- Nymara exterior crossings: written by eloria-assets/tools/continent_portals.py ---"
END = "# --- end of the exterior crossings ---"


def package_dir(region: str) -> Path:
    return PACKAGES.get(region, REGIONS / region)


def read_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def to_tile(position, transform) -> tuple[int, int]:
    origin = transform["serverOrigin"]
    metres = float(transform.get("metresPerTile", 1.0))
    x, _, z = position
    return int(round(x / metres + origin[0])), int(round(origin[1] - z / metres))


def load_portals(region: str) -> dict[str, dict]:
    manifest = read_manifest(package_dir(region) / "world.json")
    transform = manifest["coordinateTransform"]
    out = {}
    entries = list(manifest.get("portals", []))
    # Sunmane declares its transitions among its interactives
    entries += [e for e in manifest.get("interactives", []) if e.get("kind") == "portal"]
    for entry in entries:
        if "id" not in entry:
            continue
        tile = entry.get("serverTile")
        if tile is None and entry.get("position"):
            tile = to_tile(entry["position"], transform)
        if tile is None:
            continue
        out[entry["id"]] = {"tile": (int(tile[0]), int(tile[1])),
                            "name": entry.get("name") or entry.get("label") or entry["id"],
                            "destination": entry.get("destinationMap") or entry.get("destination"),
                            "spawn": entry.get("destinationSpawn")}
    return out


def load_arrivals(package: str) -> dict[str, tuple[int, int]]:
    """Spawn id -> server tile, for an insides package."""
    manifest = read_manifest(INTERIORS / package / "world.json")
    transform = manifest["coordinateTransform"]
    return {s["id"]: to_tile(s["position"], transform) for s in manifest.get("spawnPoints", [])}


def load_composed_arrivals(package: str) -> dict[str, dict[str, tuple[int, int]]]:
    """Amberwood: per sub-package, spawn id -> tile on the composed map."""
    manifest = read_manifest(INTERIORS / package / "world.json")
    out = {}
    for section in manifest.get("sections", []):
        sub = section["package"]
        base = section["serverTile"]
        sub_manifest = read_manifest(INTERIORS / sub / "world.json")
        transform = sub_manifest["coordinateTransform"]
        out[sub] = {}
        for spawn in sub_manifest.get("spawnPoints", []):
            tx, ty = to_tile(spawn["position"], transform)
            out[sub][spawn["id"]] = (int(base[0]) + tx, int(base[1]) + ty)
    return out


def load_collision(server: Path, maps_dir: Path, map_id: str):
    sys.path.insert(0, str(server))
    from eloria.collision import load_elm_collision, with_step_mask
    from eloria.maps import load_maps
    maps, _ = load_maps(str(server / "config" / "eloria" / "maps.txt"))
    return with_step_mask(load_elm_collision(maps_dir / maps[map_id].file), 2)


def arrival_tile(collision, tile, inward, minimum: int = 2, limit: int = 12):
    """The first walkable tile at least `minimum` steps in from the portal."""
    x, y = tile
    dx, dy = inward
    for step in range(minimum, limit + 1):
        ax, ay = x + dx * step, y + dy * step
        if collision.walkable(ax, ay):
            return ax, ay
        # a step to either side, for a portal on a diagonal road
        for sx, sy in ((dy, -dx), (-dy, dx)):
            if collision.walkable(ax + sx, ay + sy):
                return ax + sx, ay + sy
    return None


def nearest_open(collision, tile, minimum: int = 0, limit: int = 4):
    """The nearest walkable tile between `minimum` and `limit` steps out."""
    x, y = tile
    for radius in range(minimum, limit + 1):
        ring = []
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if max(abs(dx), abs(dy)) == radius:
                    ring.append((x + dx, y + dy))
        # closest to the tile first, then a stable order
        ring.sort(key=lambda t: ((t[0] - x) ** 2 + (t[1] - y) ** 2, t))
        for candidate in ring:
            if collision.walkable(*candidate):
                return candidate
    return None


def inward_direction(tile, cells: int) -> tuple[int, int]:
    """Towards the map's centre, along whichever axis the portal is nearest an edge."""
    x, y = tile
    centre = cells / 2.0
    if min(x, cells - x) <= min(y, cells - y):
        return (1 if x < centre else -1), 0
    return 0, (1 if y < centre else -1)


def exterior_lines(graph, portals, collisions, load, errors) -> tuple[list[str], int]:
    lines = ["# One line per direction of every link in region-connections.json. The",
             "# trigger is the package's portal tile; the arrival is the first tile a",
             "# player can stand on, two or more tiles in from the far portal, so a",
             "# crossing never lands anyone back on the tile that sent them.", ""]
    written = 0
    for link in graph["connections"]:
        pairs = ((link["from"], link["from_portal"], link["to"], link["to_portal"]),
                 (link["to"], link["to_portal"], link["from"], link["from_portal"]))
        lines.append(f"# {link['from']} <-> {link['to']} ({link['type']}): {link.get('note', '')}")
        for source, source_portal, destination, destination_portal in pairs:
            for region in (source, destination):
                if region not in portals:
                    portals[region] = load_portals(region)
                    collisions[region] = load(region)
            if source_portal not in portals[source]:
                errors.append(f"{source} has no portal {source_portal!r}")
                continue
            if destination_portal not in portals[destination]:
                errors.append(f"{destination} has no portal {destination_portal!r}")
                continue
            trigger = portals[source][source_portal]["tile"]
            far = portals[destination][destination_portal]["tile"]
            if not collisions[source].walkable(*trigger):
                errors.append(f"{source} portal {source_portal} trigger {trigger} is not walkable")
            arrival = arrival_tile(collisions[destination], far,
                                   inward_direction(far, collisions[destination].width))
            if arrival is None:
                errors.append(f"{destination} portal {destination_portal} at {far}: no walkable arrival")
                continue
            lines.append(f"portal | {source} | {trigger[0]} | {trigger[1]} | {destination} | "
                         f"{arrival[0]} | {arrival[1]}")
            written += 1
        lines.append("")
    return lines, written


def interior_lines(portals, collisions, load, errors) -> tuple[list[str], int]:
    lines = ["# --- the doors: one pair per door a region declares into its insides map ---",
             "# The region's door tile lands on the insides arrival the door names, and",
             "# that arrival tile - where the insides package puts its return portal -",
             "# lands two tiles from the door outside. Combined insides maps carry every",
             "# section of a region on one map; which section you get is which door you",
             "# used.", ""]
    written = 0
    for region, (package, map_id) in INSIDES.items():
        if region not in portals:
            portals[region] = load_portals(region)
            collisions[region] = load(region)
        if map_id not in collisions:
            collisions[map_id] = load(map_id)
        composed = None
        arrivals = None
        if region == "amberwood":
            composed = load_composed_arrivals(package)
        else:
            arrivals = load_arrivals(package)
        accepted = {map_id, package} | (set(composed) if composed else set())
        doors = [(pid, p) for pid, p in portals[region].items() if p["destination"] in accepted]
        lines.append(f"# {region} <-> {map_id} ({len(doors)} doors)")
        for door_id, door in sorted(doors):
            spawn = door["spawn"] or "default"
            table = composed[door["destination"]] if composed else arrivals
            if spawn not in table:
                errors.append(f"{region} door {door_id}: insides has no arrival {spawn!r}")
                continue
            inside = table[spawn]
            if not collisions[map_id].walkable(*inside):
                moved = nearest_open(collisions[map_id], inside, 1, 2)
                if moved is None:
                    errors.append(f"{map_id} arrival {spawn} at {inside} is not walkable")
                    continue
                inside = moved
            trigger = door["tile"]
            if not collisions[region].walkable(*trigger):
                moved = nearest_open(collisions[region], trigger, 1, 2)
                if moved is None:
                    errors.append(f"{region} door {door_id} at {trigger} is not walkable")
                    continue
                trigger = moved
            outside = nearest_open(collisions[region], trigger, 2, 5)
            if outside is None:
                errors.append(f"{region} door {door_id}: no open ground within five tiles")
                continue
            lines.append(f"portal | {region} | {trigger[0]} | {trigger[1]} | {map_id} | "
                         f"{inside[0]} | {inside[1]}")
            lines.append(f"portal | {map_id} | {inside[0]} | {inside[1]} | {region} | "
                         f"{outside[0]} | {outside[1]}")
            written += 2
        lines.append("")
    return lines, written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("--maps", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    portals: dict[str, dict] = {}
    collisions: dict[str, object] = {}
    errors: list[str] = []

    def load(map_id: str):
        return load_collision(args.server, args.maps, map_id)

    lines = [BEGIN]
    outside, crossings = exterior_lines(graph, portals, collisions, load, errors)
    inside, doors = interior_lines(portals, collisions, load, errors)
    lines += outside + inside + [END]
    for error in errors:
        print("ERROR", error)
    print(f"{crossings} crossing lines from {len(graph['connections'])} links, {doors} door lines")
    if errors:
        return 1
    block = "\n".join(lines)
    maps_txt = args.server / "config" / "eloria" / "maps.txt"
    text = maps_txt.read_text(encoding="utf-8")
    if BEGIN in text and END in text:
        head = text[:text.index(BEGIN)]
        tail = text[text.index(END) + len(END):]
        new_text = head + block + tail
    else:
        new_text = text.rstrip("\n") + "\n\n" + block + "\n"
    if args.apply:
        maps_txt.write_text(new_text, encoding="utf-8", newline="\n")
        print(f"wrote {maps_txt}")
    else:
        print(block)
    return 0


if __name__ == "__main__":
    sys.exit(main())

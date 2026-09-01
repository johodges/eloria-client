#!/usr/bin/env python3
"""Move a package's server-authority markers to where the server puts them.

A map package declares its harvest nodes and NPC markers twice: a `position`
in metres, which is where the client draws the thing, and a `serverTile`,
which is the tile the server runs it on. Entries marked `"authority":
"server"` say outright which of the two decides.

They can disagree. Some of these were authored on tiles the package's own walk
grid blocks - a harvest node a few tiles inside a building - so when the server
started enforcing that collision the node had to move, and the model it is
drawn as stayed behind. The four Four Gates harvestables were fixed this way
before, by hand, and `test_the_four_gates_harvestables_are_where_the_server_puts_them`
was written to hold the two together; this does the same for the rest.

    python eloria-assets/tools/sync_package_content.py [--manifest <path>] [--apply]

The manifest is the server's `config/eloria/client_content_manifest.json`,
which `dev-server/tools/relocate_map_content.py` keeps current. Position moves
with the tile: the horizontal part is exact, and the vertical part follows the
package's own terrain over the distance moved, so a node keeps whatever height
above the ground it was authored with.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent
REPO = ASSETS.parent


def four_gates_terrain():
    sys.path.insert(0, str(HERE / "four_gates"))
    import terrain

    field = terrain.TerrainField()
    return lambda x, z: float(np.ravel(field.height(np.array([x]), np.array([z])))[0])


def amberwood_terrain():
    sys.path.insert(0, str(ASSETS / "maps" / "nymara-regions" / "_toolkit"))
    from amberwood import region

    field = region.build_terrain(20260827)
    return lambda x, z: float(np.ravel(field.height_at(np.array([x]), np.array([z])))[0])


# package directory -> (manifest keys it answers, terrain factory)
def sunmane_terrain():
    sys.path.insert(0, str(HERE / "sunmane"))
    import terrain

    landform = terrain.build()
    return lambda x, z: float(np.ravel(landform.sample(
        np.array([x]), np.array([z])))[0])


class Section:
    """One list of markers in a package manifest, and the key it answers.

    `path` walks into the manifest, because a package may declare its markers
    at the top level or nested - Sunmane keeps its under `runtimePopulation` -
    and `position` names the field the placement lives in, which is `position`
    for a point and `center` for something with an extent.
    """

    def __init__(self, manifest_key, path, tile="serverTile", position="position"):
        self.manifest_key = manifest_key
        self.path = path
        self.tile = tile
        self.position = position

    def entries(self, data: dict):
        node = data
        for step in self.path:
            node = node.get(step) if isinstance(node, dict) else None
            if node is None:
                return ()
        return node if isinstance(node, list) else ()


# The markers each package holds that the server decides the tile for. The
# server's content manifest is the list; these say where the package keeps its
# own copy of it.
PACKAGES = {
    "four-gates": (
        [Section("four_gates_harvestables", ("harvestables",))],
        four_gates_terrain,
    ),
    "nymara-regions/amberwood": (
        [Section("amberwood_harvestables", ("harvestables",)),
         Section("amberwood_npcs", ("npcMarkers",), tile="server_tile")],
        amberwood_terrain,
    ),
    "nymara-regions/sunmane_steppe": (
        [Section("sunmane_npcs", ("runtimePopulation", "npcs")),
         Section("sunmane_resources", ("runtimePopulation", "resources"),
                 position="center")],
        sunmane_terrain,
    ),
}


def wanted_tiles(manifest: dict, section: "Section") -> dict[str, tuple[int, int]]:
    """The server's tile for every marker this section is answerable for."""
    out = {}
    for entry in manifest.get(section.manifest_key, ()):
        tile = entry.get(section.tile) or entry.get("serverTile")
        if entry.get("id") and tile and len(tile) == 2:
            out[entry["id"]] = (int(tile[0]), int(tile[1]))
    return out


def sync(package: Path, sections, terrain, manifest: dict, moves: list) -> str | None:
    path = package / "world.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    transform = data["coordinateTransform"]
    origin_x, origin_y = transform["serverOrigin"]
    metres = transform["metresPerTile"]

    ground = None
    changed = False
    for section in sections:
        wanted = wanted_tiles(manifest, section)
        for entry in section.entries(data):
            tile = wanted.get(entry.get("id"))
            if tile is None or list(tile) == list(entry.get("serverTile", ())):
                continue
            placement = entry.get(section.position)
            if not placement or len(placement) != 3:
                continue
            old_x, old_y, old_z = placement
            new_x = (tile[0] - origin_x) * metres
            # invertServerY: the server's y runs north to south.
            new_z = -(tile[1] - origin_y) * metres
            if ground is None:
                ground = terrain()
            # Keep whatever the marker was authored to stand above the ground,
            # and let the ground itself carry it to the new tile.
            rise = ground(new_x, new_z) - ground(old_x, old_z)
            entry[section.position] = [round(new_x, 2), round(old_y + rise, 2),
                                       round(new_z, 2)]
            entry["serverTile"] = [tile[0], tile[1]]
            moves.append((package.name, entry["id"], (old_x, old_z), (new_x, new_z)))
            changed = True
    return json.dumps(data, indent=2) + "\n" if changed else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=None,
                        help="the server's config/eloria/client_content_manifest.json")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    path = Path(args.manifest) if args.manifest else (
        REPO.parent / "dev-server" / "config" / "eloria" / "client_content_manifest.json")
    if not path.is_file():
        print(f"cannot find the server content manifest at {path}; pass --manifest",
              file=sys.stderr)
        return 1
    manifest = json.loads(path.read_text(encoding="utf-8"))

    moves: list = []
    written = {}
    for relative, (sections, terrain) in PACKAGES.items():
        package = ASSETS / "maps" / relative
        text = sync(package, sections, terrain, manifest, moves)
        if text is not None:
            written[package / "world.json"] = text

    for name, marker, old, new in moves:
        distance = max(abs(new[0] - old[0]), abs(new[1] - old[1]))
        print(f"[move] {name:12s} {marker:24s} "
              f"({old[0]:8.2f}, {old[1]:8.2f}) -> ({new[0]:8.2f}, {new[1]:8.2f})"
              f"  {distance:5.1f} m")
    print(f"[done] {len(moves)} markers on {len(written)} packages")
    if not args.apply:
        print("[dry ] nothing written; pass --apply to rewrite the packages")
        return 0
    for target, text in written.items():
        target.write_text(text, encoding="utf-8")
        print(f"[write] {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

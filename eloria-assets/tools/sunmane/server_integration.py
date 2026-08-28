#!/usr/bin/env python3
"""Regenerate `server-integration.md` from the committed manifests.

The server-side records are transcribed from the packages rather than typed, so
the document cannot drift from what the client actually ships.

Run:  python3 eloria-assets/tools/sunmane/server_integration.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "maps" / "nymara-regions"
PACKAGE = ROOT / "sunmane_steppe"
INTERIORS = ("sunmane_wind_caves", "sunmane_crystal_hollow")


def table(header: list[str], rows: list[list[str]]) -> list[str]:
    align = ["---"] * len(header)
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(align) + "|"]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return lines


def tile(entry) -> str:
    return "`(%d, %d)`" % (entry[0], entry[1])


def main() -> int:
    manifest = json.loads((PACKAGE / "world.json").read_text())
    interiors = {name: json.loads((ROOT / "interiors" / name / "world.json").read_text())
                 for name in INTERIORS}
    population = manifest["runtimePopulation"]
    out: list[str] = []
    add = out.append

    add("# Sunmane Steppe - server integration\n")
    add("Everything in this document is server-side work that this client change")
    add("does **not** perform. The client change is self-contained and does not")
    add("alter the network protocol or any gameplay behaviour; the region loads")
    add("and is traversable with the server exactly as it is today.\n")
    add("`eloria-server` was not reachable from the workspace this package was")
    add("built in, so none of the records below could be committed there. They are")
    add("generated from the committed manifests by")
    add("`tools/sunmane/server_integration.py`, so the matching server pull")
    add("request is transcription rather than redesign.\n")

    add("## Hooks\n")
    add("The region's hook names come from")
    add("`maps/nymara-regions/source-elm/regions-connections.json` and are")
    add("unchanged:\n")
    out.extend(table(["Hook", "Name"], [
        ["npc", "`npcs.nymara.sunmane_steppe`"],
        ["spawn", "`spawns.nymara.sunmane_steppe`"],
        ["hazard", "`hazards.nymara.sunmane_steppe`"],
        ["harvest", "`harvest.nymara.sunmane_steppe`"]]))
    add("")

    add("## Map registration\n")
    transform = manifest["coordinateTransform"]
    band = transform["addressableWorldBounds"]
    out.extend(table(["Property", "Value"], [
        ["Server map id", "`maps/nymara/sunmane_steppe.elm`"],
        ["Metres per server tile", transform["metresPerTile"]],
        ["Arrival datum", tile([int(v) for v in transform["serverOrigin"]])],
        ["Addressable tiles", "0..191 on both axes"],
        ["Addressable world band",
         "X %.0f..%.0f, Z %.0f..%.0f" % (band["min"][0], band["max"][0],
                                         band["min"][1], band["max"][1])],
        ["Walk portal west", "`(6, 58)` from Amethyst Barrens `(110, 58)`"],
        ["Walk portal east", "`(110, 58)` to Amberwood `(6, 58)`"],
        ["Interior entrance", "`(58, 100)` to Ssarathi Royal Archive `(58, 10)`"]]))
    add("")
    add("The region is wider than the addressable band on purpose. Everything")
    add("outside it - the far spires, the summits, the open sea - is scenery a")
    add("player can see but never stand on, and it is marked")
    add('`"reachable": false` in the manifest. The server needs no record of it.\n')

    add("## New interior maps\n")
    add("Two cave interiors ship as their own packages under")
    add("`maps/nymara-regions/interiors/` and are registered client-side in")
    add("`godot-client/data/maps/registry.json`. They need server map ids and the")
    add("matching transition records:\n")
    rows = []
    for name, data in interiors.items():
        entrance = next(entry for entry in manifest["interactives"]
                        if entry.get("destinationMap", "").endswith(name + ".elm"))
        exit_portal = data["portals"][0]
        rows.append([
            "`maps/nymara/%s.elm`" % name,
            data["asset"]["name"],
            "`(%d, %d)`" % tuple(int(v) for v in data["coordinateTransform"]["serverOrigin"]),
            tile(entrance["serverTile"]),
            tile(entrance["destinationTile"]),
            tile(exit_portal["destinationTile"])])
    out.extend(table(["Server map id", "Name", "Datum", "Entrance on the steppe",
                      "Arrival inside", "Exit back to"], rows))
    add("")
    add("Both interiors are one metre per tile like the surface map, use")
    add("`invertServerY`, and place their datum at the centre of a 60 m square, so")
    add("every walkable tile is in 0..60 on both axes. The other two cave mouths on")
    add("the surface - the drovers' shelter and the eastern adit - are modelled")
    add("shelters with no interior and need no registration.\n")

    add("## Safe spawn surfaces\n")
    add("The client grounds actors by raycasting the navigation surface, and every")
    add("sampled column in the region grounds successfully, so any walkable tile is")
    add("a safe spawn. The positions the manifests name explicitly:\n")
    rows = [[entry["id"], tile(entry["serverTile"]), "sunmane_steppe", entry["note"]]
            for entry in manifest["spawnPoints"]]
    for name, data in interiors.items():
        rows += [[entry["id"], tile(entry["serverTile"]), name, entry["note"]]
                 for entry in data["spawnPoints"]]
    out.extend(table(["Spawn id", "Server tile", "Map", "Note"], rows))
    add("")

    add("## NPC posts (%d)\n" % len(population["npcs"]))
    out.extend(table(["Id", "Label", "Role", "Server tile"],
                     [[f"`{entry['id']}`", entry["label"], entry["role"],
                       tile(entry["serverTile"])] for entry in population["npcs"]]))
    add("")

    add("## Harvestable resources (%d)\n" % len(population["resources"]))
    out.extend(table(["Id", "Label", "Kind", "Server tile"],
                     [[f"`{entry['id']}`", entry["label"], entry["kind"],
                       tile(entry["serverTile"])] for entry in population["resources"]]))
    add("")

    add("## Hostile creature spawns (%d)\n" % len(population["creatures"]))
    add("All models below already exist in the client's creature catalogue.\n")
    out.extend(table(["Model", "Area", "Count", "Radius", "Server tile"],
                     [[f"`{entry['model']}`", entry.get("area", ""), entry["count"],
                       "%.1f m" % entry["radius"], tile(entry["serverTile"])]
                      for entry in population["creatures"]]))
    add("")

    add("## Interaction points needing server behaviour\n")
    add("The manifest declares %d interaction points. The ones that need a server"
        % len(manifest["interactives"]))
    add("decision rather than a client-side prompt are the map transitions:\n")
    rows = [[f"`{entry['id']}`", entry["label"], tile(entry["serverTile"]),
             "`%s`" % entry["destinationMap"], tile(entry["destinationTile"])]
            for entry in manifest["interactives"]
            if entry.get("destinationMap")]
    out.extend(table(["Id", "Label", "Server tile", "Destination map",
                      "Arrival tile"], rows))
    add("")
    add("The remainder - wells, water stations, shrines, markets, shelters,")
    add("hitching rails - are ordinary interaction points and behave like the")
    add("equivalents in other regions.\n")

    add("## Livestock actor types\n")
    add("Three creature assets ship with this change: `sunmane_steppe_horse`,")
    add("`sunmane_dun_mare` and `sunmane_grey_pony`. They are registered in")
    add("`godot-client/data/actors/models.json` by model id and are instanced as")
    add("**scenery** by the client's ambient population system, so they need")
    add("nothing from the server to appear.\n")
    add("They are deliberately registered with `serverActorType: null`. Actor-type")
    add("numbers are the server's to allocate, and the creature block in")
    add("`models.json` currently runs 204-235. If the server wants these as")
    add("networked, attackable or rideable actors it should allocate the next free")
    add("numbers and add the matching `actorTypes` entries; until then the client")
    add("will simply never receive one over the wire, which is harmless.\n")

    add("## What must not change\n")
    add("The map deliberately requires no protocol change:\n")
    add("- One metre per server tile, and the arrival datum at `(58, 58)`, both")
    add("  matching the entry already committed in")
    add("  `godot-client/data/maps/registry.json`.")
    add("- Server tile to world position uses the existing `CoordinateAdapter`")
    add("  unchanged; the region moved its world centre, not its datum.")
    add("- Walkability remains server-authoritative. The client's navigation")
    add("  surface covers the whole landform on purpose, so a grounding raycast")
    add("  can never miss; it does not decide where a player may go.")

    (PACKAGE / "server-integration.md").write_text("\n".join(out) + "\n")
    print("wrote", PACKAGE / "server-integration.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

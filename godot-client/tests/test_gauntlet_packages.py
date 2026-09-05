"""The gauntlet packages and their registry entries hold together.

A gauntlet map is one linear route: a staging hall, seven legs each behind a
barred way, and a vault. The manifest's `gauntlet` block is what the server
tool reads, so its tiles have to be inside the map, every gate has to carry
the tile a player stands on and the tile beyond its cut, and the registry has
to know the map and its copies or the client cannot place anyone on them.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INTERIORS = ROOT / "eloria-assets" / "maps" / "nymara-regions" / "interiors"
REGISTRY = ROOT / "godot-client" / "data" / "maps" / "registry.json"
THEMES = ("amberwood_gauntlet", "whitehorn_gauntlet", "ssarathi_gauntlet", "grey_moors_gauntlet",
          "crownwater_gauntlet", "sunmane_gauntlet", "amethyst_gauntlet", "manymouth_gauntlet")
TILES = 384


class GauntletPackages(unittest.TestCase):
    def manifest(self, theme):
        return json.loads((INTERIORS / theme / "world.json").read_text(encoding="utf-8"))

    def test_every_route_has_seven_legs_a_fork_and_a_court(self):
        for theme in THEMES:
            g = self.manifest(theme)["gauntlet"]
            kinds = [leg["kind"] for leg in g["legs"]]
            self.assertEqual(len(kinds), 7, theme)
            self.assertEqual(kinds[-1], "court", theme)
            self.assertEqual(kinds.count("fork"), 1, theme)
            self.assertTrue({"hall", "cavern", "bridge", "stair"} <= set(kinds), theme)

    def test_every_gate_and_tile_is_inside_the_map(self):
        for theme in THEMES:
            g = self.manifest(theme)["gauntlet"]
            tiles = [g["staging"]["arrivalTile"], g["vault"]["spotTile"], g["vault"]["cache"]["serverTile"],
                     g["staging"]["exit"]["serverTile"], g["vault"]["exit"]["serverTile"]]
            gates = []
            for leg in g["legs"]:
                gates.append(leg["gate"])
                gates.extend(branch["gate"] for branch in leg.get("branches", []))
                tiles.extend(leg["spawnTiles"])
                if "bossTile" in leg:
                    tiles.append(leg["bossTile"])
            for gate in gates:
                self.assertIn("objectId", gate)
                tiles.append(gate["tile"])
                tiles.append(gate["beyondTile"])
                self.assertNotEqual(gate["tile"], gate["beyondTile"])
            for x, y in tiles:
                self.assertTrue(0 <= x < TILES and 0 <= y < TILES, (theme, x, y))
            ids = [gate["objectId"] for gate in gates]
            self.assertEqual(len(ids), len(set(ids)), theme)

    def test_the_registry_knows_each_route_and_its_copies(self):
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))["maps"]
        for theme in THEMES:
            entry = registry[theme]
            self.assertTrue(entry.get("gauntlet"), theme)
            self.assertEqual(entry["manifest"],
                             f"res://../eloria-assets/maps/nymara-regions/interiors/{theme}/world.json")
            transform = self.manifest(theme)["coordinateTransform"]
            self.assertEqual(entry["coordinateTransform"]["serverOrigin"], transform["serverOrigin"])
            for copy in (f"{theme}_2", f"{theme}_3"):
                self.assertEqual(registry[copy], {"alias": theme}, copy)

    def test_the_route_reads_as_one_walk_from_the_arrival(self):
        """The staging arrival and the vault stand at opposite ends of the map,
        so the road really runs the length of it."""
        for theme in THEMES:
            g = self.manifest(theme)["gauntlet"]
            start_y = g["staging"]["arrivalTile"][1]
            end_y = g["vault"]["spotTile"][1]
            self.assertGreater(abs(start_y - end_y), 300, theme)


if __name__ == "__main__":
    unittest.main()

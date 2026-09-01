"""A server-authority marker is drawn where the server runs it.

Harvest nodes and NPC markers are declared twice in a package manifest: a
`position` in metres, which is where the client draws the model, and a
`serverTile`, which is the tile the server runs the node on. An entry marked
`"authority": "server"` says which of the two decides.

They drifted once. Several nodes were authored on tiles their own package's
walk grid blocks, so when the server began enforcing that collision the node
moved and the model stayed behind, leaving a harvestable you could see but not
reach. `eloria-assets/tools/sync_package_content.py` moves the models onto the
server's tiles; this holds them there.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = (
    "four-gates",
    "nymara-regions/amberwood",
)
SECTIONS = ("harvestables", "npcMarkers", "interactives")


class PackageContentPlacement(unittest.TestCase):
    def test_server_authority_markers_stand_on_the_tile_they_declare(self):
        checked = 0
        for relative in PACKAGES:
            path = ROOT / "eloria-assets" / "maps" / relative / "world.json"
            if not path.is_file():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            transform = data["coordinateTransform"]
            origin_x, origin_y = transform["serverOrigin"]
            metres = transform["metresPerTile"]
            for section in SECTIONS:
                for entry in data.get(section, ()):
                    if entry.get("authority") != "server":
                        continue
                    tile = entry.get("serverTile")
                    position = entry.get("position")
                    if not tile or not position:
                        continue
                    # invertServerY: the server's y runs north to south.
                    rounded = [round(position[0] / metres + origin_x),
                               round(origin_y - position[2] / metres)]
                    self.assertEqual(
                        rounded, list(tile),
                        f"{relative} {section} {entry.get('id')} is drawn at "
                        f"{position[0]}, {position[2]} - tile {rounded} - but "
                        f"declares tile {tile}")
                    checked += 1
        self.assertGreater(checked, 40)


if __name__ == "__main__":
    unittest.main()

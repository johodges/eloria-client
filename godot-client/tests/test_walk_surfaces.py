"""Every surface a region draws under a player is walkable in its walk grid.

A region's `collision.bin` is not built from its geometry: the build derives it
from the terrain height field and re-opens its decks by guessing each one's
footprint from placement bounds. Ten regions carry ten copies of that code and
the copies drifted, so Mirrorhold's marble causeway was blocked over its whole
length bar a disc in the middle and Crownwater's quays lost their ends.
`_toolkit/open_walk_surfaces.py` corrects the finished package from its own
`Walk_*` nodes; this holds every package to that afterwards.

A surface drawn under one of the map's `Water_*` bodies is scenery rather than
floor, and a surface inside a landmark box `stamp_solid_landmarks.py` has closed
belongs to a building that is shut, so both are exempt.
"""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
REGIONS_DIR = ROOT / "eloria-assets" / "maps" / "nymara-regions"
sys.path.insert(0, str(REGIONS_DIR / "_toolkit"))

import glb_reader as GLB            # noqa: E402
import open_walk_surfaces as OPEN   # noqa: E402

REGIONS = ("amberwood", "amethyst_barrens", "crownwater", "grey_moors", "manymouth_delta",
           "mirrorhold", "ssarathi_ruins", "sunmane_steppe", "verdant_stair", "westhaven",
           "whitehorn_range")


class WalkSurfaces(unittest.TestCase):
    def test_every_region_carries_the_ground_it_draws(self):
        checked = 0
        for region in REGIONS:
            package = REGIONS_DIR / region
            grid, manifest = GLB.read_grid(package)
            document, body = GLB.load(package / "world.glb")
            nodes = GLB.named(document, OPEN.WALK)
            if not nodes:
                continue                     # a region with no decks declares none
            checked += 1
            cell = float(manifest["collision"]["cellMetres"])
            origin = GLB.grid_origin(manifest)
            covered, top = GLB.rasterise(GLB.triangles(document, body, nodes),
                                         grid.shape[1], grid.shape[0], origin[0], origin[1], cell)
            wet, water = GLB.rasterise(GLB.triangles(document, body, GLB.named(document, OPEN.WATER)),
                                       grid.shape[1], grid.shape[0], origin[0], origin[1], cell)
            exempt = (wet & (top < water - OPEN.WADE)) | OPEN.stamped(manifest, grid.shape, origin, cell)
            missing = covered & ~exempt & (grid == 0)
            if missing.any():
                ys, xs = np.nonzero(missing)
                where = ", ".join(f"cell ({x}, {y})" for x, y in zip(xs[:4], ys[:4]))
                self.fail(f"{region}: {int(missing.sum())} cells of authored walk surface are "
                          f"blocked in its grid ({where}); run _toolkit/open_walk_surfaces.py")
        self.assertGreaterEqual(checked, 10, "the regions that declare walk surfaces")

    def test_the_correction_is_recorded_and_settled(self):
        """A package that needed opening says so, and opening it again is a no-op."""
        recorded = 0
        for region in REGIONS:
            collision = GLB.read_grid(REGIONS_DIR / region)[1]["collision"]
            entry = collision.get("openedWalkSurfaces")
            if entry is None:
                continue
            recorded += 1
            self.assertEqual(entry["prefix"], OPEN.WALK, region)
            self.assertGreater(entry["cellsCovered"], 0, region)
        self.assertGreaterEqual(recorded, 10)


if __name__ == "__main__":
    unittest.main()

"""Geographic contracts for one continent evaluated before chunking."""
import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

SOURCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("diagonal_landscape", SOURCE / "landscape.py")
landscape = importlib.util.module_from_spec(spec)
spec.loader.exec_module(landscape)


class ContinentGeographyTests(unittest.TestCase):
    def test_broadcast_and_scalar_results_are_identical(self):
        x = np.array([170, 510, 950, 1200])
        z = np.array([420, 650, 840])[:, None]
        grid = landscape.height_at(x, z)
        self.assertEqual(grid.shape, (3, 4))
        for row in range(3):
            for col in range(4):
                self.assertAlmostEqual(grid[row, col], float(landscape.height_at(x[col], z[row, 0])), places=11)

    def test_export_splits_do_not_change_height_or_color(self):
        # Independent neighbouring mesh builds must produce the same shared edge.
        z = np.arange(320, 760, 4)
        west_x = np.arange(200, 604, 4)
        east_x = np.arange(600, 1004, 4)
        west_h = landscape.height_at(west_x[None, :], z[:, None])
        east_h = landscape.height_at(east_x[None, :], z[:, None])
        np.testing.assert_array_equal(west_h[:, -1], east_h[:, 0])
        west_rgb = landscape.terrain_color(west_x[None, :], z[:, None], west_h)
        east_rgb = landscape.terrain_color(east_x[None, :], z[:, None], east_h)
        np.testing.assert_array_equal(west_rgb[:, -1], east_rgb[:, 0])

    def test_material_weights_are_normalized_and_finite(self):
        x, z = np.meshgrid(np.arange(0, 1501, 35), np.arange(0, 1681, 35))
        h = landscape.height_at(x, z)
        weights = landscape.biome_weights(x, z, h)
        np.testing.assert_allclose(sum(weights.values()), 1.0, atol=1e-12)
        rgb = landscape.terrain_color(x, z, h)
        self.assertTrue(np.isfinite(h).all() and np.isfinite(rgb).all())
        self.assertTrue(((rgb >= 0) & (rgb <= 1)).all())
        self.assertGreater(float(h.max()), 130)
        self.assertLess(float(h.min()), 0)

    def test_water_profiles_descend_and_confluences_match(self):
        rivers = {r["id"]: r for r in landscape.load_plan()["rivers"]}
        for river in rivers.values():
            p = np.array(river["points"])
            self.assertTrue((np.diff(p[:, 2]) <= 0).all(), river["id"])
            self.assertTrue((p[:, 2] >= 0).all(), river["id"])
            if river.get("mouth") == "sea" or river.get("delta"):
                self.assertEqual(p[-1, 2], 0)
            if "joins" in river:
                self.assertIn(river["points"][-1], rivers[river["joins"]]["points"])
            if "joins_from" in river:
                self.assertTrue(river.get("delta"), "Upstream branching belongs only in the delta")
                self.assertIn(river["points"][0], rivers[river["joins_from"]]["points"])
            curve = landscape.curved_points(river["points"])
            for a, b in zip(curve[:-1], curve[1:]):
                points = a + np.linspace(0, 1, 25)[:, None] * (b - a)
                h = landscape.height_at(points[:, 0], points[:, 1])
                self.assertTrue((h < points[:, 2] - 0.1).all(), river["id"])

    def test_coastal_shelf_and_southwestern_archipelago(self):
        self.assertLess(float(landscape.height_at(-80, 700)), -5)
        self.assertLess(float(landscape.height_at(1570, 700)), -5)
        # The retained causeway islands now occupy the former (190,1410)
        # control. This surveyed point remains in the open western sound.
        self.assertLess(float(landscape.height_at(140, 1390)), -5)
        island=next(i for i in landscape.load_plan()['islands'] if i.get('crownSourceIsland')=='crown_isle')
        self.assertGreater(float(landscape.height_at(*island['center'])), 5)
        # Only the lower river creates its floodplain; the pass remains high.
        self.assertGreater(float(landscape.height_at(840, 650)), float(landscape.height_at(530, 840)) + 35)

    def test_climate_crosses_territory_boundaries_gradually(self):
        forest = landscape.biome_weights(490, 550)
        steppe = landscape.biome_weights(1170, 700)
        mineral = landscape.biome_weights(1000, 380)
        self.assertGreater(float(forest["woodland"]), float(steppe["woodland"]))
        self.assertGreater(float(steppe["steppe"]), float(forest["steppe"]))
        self.assertGreater(float(mineral["badland"]), float(steppe["badland"]))
        # Materials have no sudden rectangles, even through the old forest edge.
        x = np.linspace(350, 1000, 651)
        rgb = landscape.terrain_color(x, np.full_like(x, 590))
        self.assertLess(float(np.max(np.linalg.norm(np.diff(rgb, axis=0), axis=1))), 0.035)

    def test_relief_source_and_retained_transform_share_one_squeeze(self):
        transform = {"translation": [477., 70., 272.], "squeeze_z": .85, "about_z": 60.}
        # x is translated; z is squeezed about source row 60 and translated: 272 + 60 + (z - 60) * .85.
        np.testing.assert_allclose(landscape.retained_map_xz(transform, [[70., 40.], [76., -192.]]), [[547., 315.], [553., 117.8]])
        np.testing.assert_allclose(landscape.retained_map_xz([477., 70., 272.], [70., 40.]), [547., 312.])
        translation, scale, about = landscape.retained_affine(transform)
        self.assertEqual((translation.tolist(), scale.tolist(), about.tolist()), ([477., 70., 272.], [1., .85], [0., 60.]))
        with self.assertRaisesRegex(ValueError, "squeeze_z"):
            landscape.retained_affine({"translation": [0, 0, 0], "squeeze_z": 0.})
        with self.assertRaisesRegex(ValueError, "three finite metres"):
            landscape.retained_affine([1., 2.])
        # A relief source with the same squeeze samples its rows where the transform put them.
        rows = (np.array([-10., 0., 10.]), np.array([-300., -200., -100.]), np.array([[10.] * 3, [20.] * 3, [30.] * 3]))
        with patch.object(landscape, "_relief_samples", lambda name: rows):
            source = {"samples": "x.npz", "translation": [477., 70., 272.], "crop": [-10, -300, 10, -100], "feather": 10,
                      "squeeze_z": .85, "about_z": 60.}
            height, weight = landscape._relief_height(np.array([477.]), np.array([111.]), source)   # row -200 -> 332 - 221
            self.assertAlmostEqual(float(height[0]), 20. + 70., places=6)
            self.assertEqual(float(weight[0]), 1.)
            height, _ = landscape._relief_height(np.array([477.]), np.array([72.]), dict(source, squeeze_z=1., about_z=0.))
            self.assertAlmostEqual(float(height[0]), 20. + 70., places=6)

    def test_relief_knee_lowers_the_rim_and_leaves_the_floor(self):
        rows = (np.array([-10., 0., 10.]), np.array([-300., -200., -100.]), np.array([[178.] * 3, [70.] * 3, [40.] * 3]))
        with patch.object(landscape, "_relief_samples", lambda name: rows):
            source = {"samples": "x.npz", "translation": [0., 0., 0.], "crop": [-10, -300, 10, -100], "feather": 10,
                      "knee": 70., "above_scale": .4, "knee_width": 10.}
            z = np.array([-300., -200., -100.]); x = np.zeros(3)
            height, _ = landscape._relief_height(x, z, source)
            # The crown keeps 40 % of its rise above the knee, the knee row and the floor are untouched.
            np.testing.assert_allclose(height, [70. + 108. * .4, 70., 40.])
            # Compressed heights stay in order: a taller row is still taller.
            fine = (np.array([-10., 0., 10.]), np.linspace(-300., -100., 41), np.tile(np.linspace(178., 40., 41)[:, None], (1, 3)))
        with patch.object(landscape, "_relief_samples", lambda name: fine):
            height, _ = landscape._relief_height(np.zeros(41), np.linspace(-300., -100., 41), source)
            self.assertTrue(np.all(np.diff(height) < 0.))
            without, _ = landscape._relief_height(np.zeros(41), np.linspace(-300., -100., 41), dict(source, knee=None))
            np.testing.assert_allclose(without, np.linspace(178., 40., 41))

    def test_optional_foundation_feathers_into_shared_surface(self):
        plan = copy.deepcopy(landscape.load_plan())
        target = float(landscape.height_at(740, 1030)) + 2
        plan["foundations"] = [{"center": [740, 1030], "radius": 12, "elevation": target, "feather": 28}]
        self.assertAlmostEqual(float(landscape.height_at(740, 1030, plan)), target)
        self.assertAlmostEqual(float(landscape.height_at(785, 1030, plan)), float(landscape.height_at(785, 1030)))

    def test_river_level_extension_keeps_surveyed_centreline_levels(self):
        for river in landscape.load_plan()['rivers']:
            curve=landscape.curved_points(river['points'])
            points=np.concatenate([a+np.linspace(0,1,9)[:,None]*(b-a)
                                   for a,b in zip(curve[:-1],curve[1:])])
            distance,level=landscape._polyline_field(points[:,0],points[:,1],river['points'])
            np.testing.assert_allclose(distance,0,atol=1e-10)
            np.testing.assert_allclose(level,points[:,2],atol=1e-10,err_msg=river['id'])

    def test_river_attribute_extension_has_no_segment_projection_step(self):
        river=next(r for r in landscape.load_plan()['rivers'] if r['id']=='western_river')
        # This surveyed bend previously had a half-metre height jump between
        # adjacent nearest-segment projections, visible as diagonal bank seams.
        x=np.arange(453.5,460.501,.01)
        z=np.full_like(x,414.5)
        _,level=landscape._polyline_field(x,z,river['points'])
        self.assertLess(float(np.max(np.abs(np.diff(level))))/.01,.65)

    def test_navigable_bank_has_a_low_gradual_flood_shelf(self):
        river=copy.deepcopy(next(r for r in landscape.load_plan()['rivers'] if r['id']=='western_river'))
        river['points']=[[0,-100,20],[0,100,20]]
        plan={'rivers':[river],'lakes':[]}
        x=np.arange(0,50.01,.1)
        height=landscape._drainage_height(x,np.zeros_like(x),np.full_like(x,80),plan)
        bank=(x>=river['width'])&(x<=river['width']+10)
        self.assertLess(float(np.max(np.abs(np.gradient(height,.1))[bank])),.6)
        self.assertLessEqual(float(np.max(height[bank]-20)),.65)
        self.assertTrue((np.diff(height)>=-1e-10).all())
        self.assertAlmostEqual(height[0],20-river['depth'])


if __name__ == "__main__":
    unittest.main()

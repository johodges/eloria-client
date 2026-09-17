"""Reach links: authored ground written onto the finished composition."""
import types
import unittest

import numpy as np

import landscape as L
import reach_links as R


def world(plan, size=(41, 61), cell=2.):
    rows, cols = size
    x = np.arange(cols) * cell
    z = np.arange(rows) * cell
    gx, gz = np.meshgrid(x, z)
    return types.SimpleNamespace(plan=plan, gx=gx, gz=gz, height=10. + gx * .8)


RAMP = {'id': 'link', 'name': 'a link up the slope', 'op': 'ramp', 'shape': {'polyline': {'points': [[20., 40.], [80., 40.]], 'width': 8.}},
        'heights': [26., 50.], 'feather': 6., 'strength': 1}


class ValidationTests(unittest.TestCase):
    def test_absent_or_empty_links_are_valid(self):
        self.assertEqual(R.validate_reach_links({}), [])
        self.assertEqual(R.validate_reach_links({'reach_links': []}), [])

    def test_links_use_the_terrain_edit_schema_and_say_reach_link(self):
        self.assertEqual(R.validate_reach_links({'reach_links': [RAMP], 'bounds': [0, 0, 200, 200]}), [])
        broken = dict(RAMP, heights=[26.])
        problems = R.validate_reach_links({'reach_links': [broken], 'bounds': [0, 0, 200, 200]})
        self.assertTrue(problems and all('reach link' in p for p in problems), problems)
        self.assertEqual(R.validate_reach_links({'reach_links': {'id': 'x'}}), ["'reach_links' must be a list of links"])


class ApplyTests(unittest.TestCase):
    def test_links_blend_the_finished_ground_as_terrain_edits_do(self):
        w = world({'reach_links': [RAMP]})
        expected = L._terrain_edit_height(w.gx, w.gz, w.height.copy(), {'terrain_edits': [RAMP]})
        report = R.apply_reach_links(w)
        np.testing.assert_array_equal(w.height, expected)
        # On the line the ground is the ramp's own surface, off the feather it is untouched.
        self.assertAlmostEqual(float(w.height[20, 25]), 26. + 24. * (50. - 20.) / 60., places=9)
        self.assertEqual(float(w.height[0, 0]), 10.)
        self.assertEqual(report['links'], 1)
        self.assertGreater(report['changedCells'], 0)
        self.assertEqual(w.reach_links, report)

    def test_no_links_leave_the_ground_alone(self):
        w = world({})
        before = w.height.copy()
        self.assertEqual(R.apply_reach_links(w), {'links': 0, 'perLink': []})
        np.testing.assert_array_equal(w.height, before)

    def test_a_link_reaching_a_river_centreline_is_refused(self):
        plan = {'reach_links': [RAMP], 'rivers': [{'id': 'brook', 'points': [[50., 30.], [50., 50.]]}]}
        with self.assertRaisesRegex(ValueError, "'link' reaches river centrelines"):
            R.apply_reach_links(world(plan))
        clear = {'reach_links': [RAMP], 'rivers': [{'id': 'brook', 'points': [[50., 70.], [60., 80.]]}]}
        R.apply_reach_links(world(clear))

    def test_a_link_moving_the_ground_under_a_rigid_compound_member_is_refused(self):
        member = {'region': 'test', 'node': 'Hall', 'assembly': 'test.hall', 'low': [44., 0., 45.], 'high': [50., 6., 52.]}
        content = types.SimpleNamespace(objects=[member])
        with self.assertRaisesRegex(ValueError, 'rigid compound members'):
            R.apply_reach_links(world({'reach_links': [RAMP]}), content)
        # A loose placement is regrounded afterwards, so it does not stop the link.
        loose = dict(member, assembly=None)
        R.apply_reach_links(world({'reach_links': [RAMP]}), types.SimpleNamespace(objects=[loose]))
        # Nor does a member whose ground the link moves within the tolerance: a ramp that follows the ground there.
        w = world({})
        gentle = dict(RAMP, heights=[10. + 20. * .8, 10. + 80. * .8])
        w.plan = {'reach_links': [gentle]}
        R.apply_reach_links(w, content)

    def test_a_tree_member_is_judged_at_its_trunk_not_its_canopy(self):
        # A giant tree whose canopy box spans the link but whose trunk stands 20 m clear of it.
        tree = {'region': 'test', 'node': 'Giant', 'kind': 'tree', 'assembly': 'test.village',
                'low': [30., 0., 20.], 'high': [70., 30., 60.], 'sourcePivot': [0., 0., 0.], 'shift': [50., 0., 62.]}
        R.apply_reach_links(world({'reach_links': [RAMP]}), types.SimpleNamespace(objects=[tree]))
        standing = dict(tree, shift=[50., 0., 40.])
        with self.assertRaisesRegex(ValueError, 'rigid compound members'):
            R.apply_reach_links(world({'reach_links': [RAMP]}), types.SimpleNamespace(objects=[standing]))

    def test_invalid_links_are_refused_before_the_ground_changes(self):
        w = world({'reach_links': [dict(RAMP, op='smooth')]})
        before = w.height.copy()
        with self.assertRaisesRegex(ValueError, 'Reach links'):
            R.apply_reach_links(w)
        np.testing.assert_array_equal(w.height, before)


if __name__ == '__main__':
    unittest.main()

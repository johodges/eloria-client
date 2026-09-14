import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_export import crossing_ends
from build_continent import crossing_local


class CrossingEndsTests(unittest.TestCase):
    def test_ends_lie_one_cell_inside_each_end_of_the_floor(self):
        # A diagonal floor of twelve one-metre cells, two cells wide.
        centers = [(x + .5, x * .5 + .5 + w) for x in range(12) for w in (0, 1)]
        owners = [3] * len(centers)
        owner, ends = crossing_ends(centers, owners, lambda x, z: 10 + .1 * x)
        self.assertEqual(owner, 3)
        xs = sorted(e[0] for e in ends)
        # One full cell inside each end, on the centreline of the two-cell width.
        self.assertTrue(1.0 <= xs[0] <= 2.5, xs); self.assertTrue(9.5 <= xs[1] <= 11.0, xs)
        for x, y, z in ends:
            self.assertIn((x, z), centers)          # an actual floor cell, never an interpolated point
            self.assertAlmostEqual(y, 10 + .1 * x)

    def test_floors_whose_ends_lie_in_different_territories_are_not_declared(self):
        centers = [(x + .5, .5) for x in range(10)]
        owners = [0] * 5 + [1] * 5
        self.assertIsNone(crossing_ends(centers, owners, lambda x, z: 0.0))

    def test_short_floors_are_not_declared(self):
        self.assertIsNone(crossing_ends([(0.5, 0.5), (1.5, 0.5)], [0, 0], lambda x, z: 0.0))


class CrossingLocalTests(unittest.TestCase):
    def test_package_point_rounds_to_the_containing_tile_under_the_server_rule(self):
        center = np.array([530., 840.]); origin = [310, 164]
        for global_point in ([549.5, 22.3, 888.5], [549.9, 22.3, 888.1], [550.0, 22.3, 889.0]):
            x, y, z = crossing_local(global_point, center, origin)
            self.assertAlmostEqual(y, 22.3)
            local_x, local_z = global_point[0] - 530., global_point[2] - 840.
            expected = (int(np.floor(local_x + origin[0])), int(np.floor(origin[1] - local_z)))
            served = (int(round(origin[0] + x)), int(round(origin[1] - z)))
            self.assertEqual(served, expected)
            self.assertLess(abs(x - local_x), 1.0); self.assertLess(abs(z - local_z), 1.0)


if __name__ == '__main__':
    unittest.main()

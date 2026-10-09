"""The quarry approach rounds the north tower without relaxing other slopes."""
import json
from pathlib import Path
import sys
import unittest

import numpy as np

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
import collision_export as C
from refresh_north_gate_approach import refresh


class NorthGateApproachTests(unittest.TestCase):
    def test_only_the_surveyed_four_gates_apron_gets_the_walking_grade(self):
        x = np.array([-25., -23., -10., -6., -10.])
        z = np.array([-114., -114., -114., -114., -120.])
        np.testing.assert_allclose(C.terrain_grade_limit('four_gates', x, z), [.65, .8, .8, .65, .65])
        np.testing.assert_allclose(C.terrain_grade_limit('amberwood', x, z), [.65]*5)
        # A genuine cliff stays blocked even inside the approach.
        self.assertFalse(bool((1.2 <= C.terrain_grade_limit('four_gates', np.array([-15.]), np.array([-114.])))[0]))

    def test_published_apron_has_already_been_refreshed_from_the_actual_geometry(self):
        package = SOURCE.parents[1] / 'four-gates'
        self.assertEqual(refresh(package)['openedHalfCells'], 0)
        manifest = json.loads((package/'world.json').read_text())
        self.assertEqual(manifest['collision']['terrainGradeApproaches'][0]['maximumGrade'], .8)


if __name__ == '__main__':
    unittest.main()

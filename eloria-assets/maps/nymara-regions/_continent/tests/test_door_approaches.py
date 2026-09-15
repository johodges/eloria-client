import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import door_approaches as D

DOOR = np.array([1207.01, 1181.42])


def world(owner=0, height=7.5, wet=False):
    x = np.arange(0., 2000., 2.); z = np.arange(0., 2000., 2.)
    mask = np.full((len(z), len(x)), wet, bool)
    return SimpleNamespace(ids=['verdant_stair', 'mirrorhold'], x=x, z=z, x0=0., z0=0., water={'mask': mask},
                           owner_at=lambda px, pz: owner, height_at=lambda px, pz: height)


class DoorApproachTests(unittest.TestCase):
    def test_the_shrine_road_ends_on_dry_ground_north_of_the_pavilion(self):
        w = world(); content = SimpleNamespace()
        report = D.prepare_door_approaches(w, content)
        end = content.door_road_ends[('verdant_stair', 'nine-lost-door')]
        self.assertEqual(end.tolist(), [1206.5, 1175.5])
        self.assertLess(end[1], DOOR[1])                    # north of the door (smaller z)
        self.assertLess(np.linalg.norm(end - DOOR), D.MAXIMUM_DOOR_DISTANCE_METRES)
        self.assertEqual(report['roadEnds'], {'verdant_stair:nine-lost-door': [1206.5, 1175.5]})
        self.assertIs(w.door_approaches, report)
        self.assertTrue(np.array_equal(D.door_road_end(content, 'verdant_stair', 'nine-lost-door', DOOR), end))

    def test_a_server_portal_beside_the_pinned_door_shares_its_road_end(self):
        content = SimpleNamespace(door_road_ends={('verdant_stair', 'nine-lost-door'): np.array([1206.5, 1175.5])})
        shrine = np.array([1207.3, 1181.2])                   # maps.txt portal line 349, the same shrine door
        self.assertEqual(D.door_road_end_near(content, 'verdant_stair', shrine).tolist(), [1206.5, 1175.5])
        far = np.array([1300., 1300.])
        self.assertTrue(np.array_equal(D.door_road_end_near(content, 'verdant_stair', far), far))
        self.assertTrue(np.array_equal(D.door_road_end_near(content, 'mirrorhold', shrine), shrine))
        self.assertTrue(np.array_equal(D.door_road_end_near(SimpleNamespace(), 'verdant_stair', shrine), shrine))

    def test_a_server_only_portal_with_its_own_pin_is_routed_to_it_not_to_the_neighbouring_door(self):
        content = SimpleNamespace(door_road_ends={('amberwood', 'gate-undercroft-stair'): np.array([616.5, 589.5])},
                                  server_road_ends={('amberwood', 'amberwood', 'amberwood_estate'): np.array([600., 590.])})
        estate = np.array([608., 590.])
        # The estate door is 8.5 m from the undercroft pin and would share it by distance; its own pin wins.
        self.assertEqual(D.server_road_end(content, 'amberwood', estate, 'amberwood', 'amberwood_estate').tolist(), [600., 590.])
        self.assertIsNone(D.server_road_end(content, 'amberwood', estate, 'amberwood', 'amberwood_secrets'))
        self.assertEqual(D.door_road_end_near(content, 'amberwood', estate).tolist(), [616.5, 589.5])
        # Another entrance to the same map, out of the pin's reach, keeps the default handling.
        self.assertIsNone(D.server_road_end(content, 'amberwood', np.array([640., 590.]), 'amberwood', 'amberwood_estate'))

    def test_doors_without_a_pin_keep_their_own_point(self):
        content = SimpleNamespace(door_road_ends={})
        self.assertTrue(np.array_equal(D.door_road_end(content, 'verdant_stair', 'other-door', DOOR), DOOR))
        self.assertTrue(np.array_equal(D.door_road_end(SimpleNamespace(), 'verdant_stair', 'nine-lost-door', DOOR), DOOR))

    def test_pins_outside_the_territory_under_water_or_far_from_the_door_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'outside its territory'):
            D.prepare_door_approaches(world(owner=1), SimpleNamespace())
        with self.assertRaisesRegex(ValueError, 'not dry ground'):
            D.prepare_door_approaches(world(height=.2), SimpleNamespace())
        with self.assertRaisesRegex(ValueError, 'stands in water'):
            D.prepare_door_approaches(world(wet=True), SimpleNamespace())
        content = SimpleNamespace(door_road_ends={('verdant_stair', 'nine-lost-door'): np.array([1206.5, 1175.5])})
        with self.assertRaisesRegex(ValueError, 'further than'):
            D.door_road_end(content, 'verdant_stair', 'nine-lost-door', DOOR + [0., 20.])

    def test_other_territories_are_untouched(self):
        w = SimpleNamespace(ids=['mirrorhold']); content = SimpleNamespace()
        self.assertEqual(D.prepare_door_approaches(w, content)['roadEnds'], {})
        self.assertEqual(content.door_road_ends, {})


if __name__ == '__main__':
    unittest.main()

"""A seam is crossed wherever both maps can be stood on, not only at its gate."""
from pathlib import Path
import sys
import unittest

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import crossings as C
import collision_export as CE
from test_partition_pipeline import FlatWorld

GATED = ('east--west',)
SHIPPED = C.GATED_SEAMS


def served(west=None, east=None):
    """Two all-walkable served grids, or the ones given."""
    return {'west': np.ones((48, 48), bool) if west is None else west,
            'east': np.ones((48, 48), bool) if east is None else east}


class SeamLaneTests(unittest.TestCase):
    def setUp(self):
        self.world = FlatWorld()
        self.link = self.world.connections[0]

    def lanes(self, grids, side=0):
        return C.crossing_lanes(self.world, self.link, side, grids)

    def test_every_tile_of_the_border_both_maps_can_stand_on_is_a_lane(self):
        lanes = self.lanes(served())
        self.assertGreater(len(lanes), 20, 'a twenty-metre border offers more than a gate')
        for lane in lanes:
            departure = C.global_tile(self.world, 'west', lane['tile'])
            arrival = C.global_tile(self.world, 'west', lane['arrival'])
            # Stood on the neighbour's first tile across the boundary, with this
            # territory's own ground one step behind it.
            self.assertAlmostEqual(float(departure[0]), 20.5)
            self.assertAlmostEqual(float(arrival[0]), 19.5)
            self.assertEqual(max(abs(lane['tile'][0] - lane['arrival'][0]),
                                 abs(lane['tile'][1] - lane['arrival'][1])), 1)
        self.assertEqual(len({tuple(lane['tile']) for lane in lanes}), len(lanes))

    def test_a_lane_needs_the_ground_on_both_sides_of_it(self):
        self.assertEqual(self.lanes(served(east=np.zeros((48, 48), bool))), [],
                         'ground the neighbour refuses is no crossing')
        self.assertEqual(self.lanes(served(west=np.zeros((48, 48), bool))), [],
                         'ground this map refuses is no crossing either')
        # One blocked tile on the far side closes its lane and no other.
        east = np.ones((48, 48), bool)
        whole = {tuple(lane['tile']) for lane in self.lanes(served())}
        closed = sorted(whole)[3]
        far = C.tiles_at(self.world, 'east', *C.global_tile(self.world, 'west', list(closed)))
        east[int(far[1]), int(far[0])] = False
        self.assertEqual({tuple(lane['tile']) for lane in self.lanes(served(east=east))},
                         whole - {closed})

    def test_the_two_sides_of_a_seam_name_the_same_ground(self):
        west = {tuple(C.global_tile(self.world, 'west', lane['tile']).round(3))
                for lane in self.lanes(served())}
        east = {tuple(C.global_tile(self.world, 'east', lane['arrival']).round(3))
                for lane in self.lanes(served(), side=1)}
        self.assertEqual(west, east, 'what one map departs from is what the other arrives at')

    def test_a_widened_seam_keeps_the_lanes_of_the_gate_it_had(self):
        world = self.world
        C.prepare_contracts(world)
        connections = world.publication_connections
        gate = [[tuple(lane['tile']) for lane in end['lanes']] for end in connections[0]['ends']]
        report = C.widen_seams(world, connections, served(), gated=())
        self.assertEqual([end['gateLanes'] for end in report[0]['ends']], [7, 7])
        for side, end in enumerate(connections[0]['ends']):
            tiles = [tuple(lane['tile']) for lane in end['lanes']]
            self.assertGreater(len(tiles), 7, 'the seam gained the rest of its border')
            self.assertEqual(len(set(tiles)), len(tiles), 'no lane is declared twice')
            self.assertTrue(set(gate[side]) <= set(tiles), 'the gate survives the widening')
            self.assertEqual(tiles, sorted(tiles, key=lambda t: (t[1], t[0])))

    def test_no_cell_is_a_departure_of_both_maps_where_the_border_steps_by_the_gate(self):
        world = self.world
        # The border steps two metres east for one metre of its length beside the
        # anchor, so one of the seven offsets of the west gate lands on west ground.
        def owner_at(x, z):
            x, z = np.broadcast_arrays(np.asarray(x, float), np.asarray(z, float))
            step = (x < 22) & (z >= 10) & (z < 11)
            return ((x >= 20) & ~step).astype(int)
        world.owner_at = owner_at
        C.prepare_contracts(world)
        connections = world.publication_connections
        report = C.widen_seams(world, connections, served(), gated=())
        self.assertEqual([end['gateLanesInside'] for end in report[0]['ends']], [1, 0])
        west, east = connections[0]['ends']
        for end in (west, east):
            for lane in end['lanes']:
                self.assertTrue(C.departs_outward(world, end['region'], lane), end['region'])
        cells = [{tuple(C.global_tile(world, end['region'], lane['tile']).round(3)) for lane in end['lanes']}
                 for end in (west, east)]
        self.assertFalse(cells[0] & cells[1], 'an arrival would trigger the crossing back at once')
        # Each end's own crossing - where a walker to the neighbour is sent - is one of its lanes.
        for end in (west, east):
            self.assertIn(end['tile'], [lane['tile'] for lane in end['lanes']])

    def test_an_end_whose_middle_lane_is_dropped_is_reseated_on_the_nearest_lane(self):
        world = self.world
        def owner_at(x, z):
            x, z = np.broadcast_arrays(np.asarray(x, float), np.asarray(z, float))
            return ((x >= 20) & ~((x < 22) & (z >= 9) & (z < 12))).astype(int)
        world.owner_at = owner_at
        C.prepare_contracts(world)
        west = world.publication_connections[0]['ends'][0]
        middle = list(west['tile'])
        C.widen_seams(world, world.publication_connections, served(), gated=())
        self.assertNotEqual(west['tile'], middle, 'the middle lane stood on west ground and was dropped')
        self.assertIn(west['tile'], [lane['tile'] for lane in west['lanes']])
        point = C.global_tile(world, 'west', west['tile'])
        self.assertEqual(west['position'][0], float(point[0] - 10))
        self.assertEqual(west['position'][2], float(point[1] - 10))

    def test_a_gated_seam_keeps_its_gate_alone(self):
        world = self.world
        C.prepare_contracts(world)
        connections = world.publication_connections
        self.assertEqual(C.widen_seams(world, connections, served(), gated=GATED), [])
        self.assertEqual([len(end['lanes']) for end in connections[0]['ends']], [7, 7])


class SeamCollarTests(unittest.TestCase):
    def collar(self, gated):
        world = FlatWorld()
        C.GATED_SEAMS = gated
        try:
            gx, gz = np.meshgrid(np.arange(14.25, 26., .5), np.arange(4.25, 16., .5))
            return CE.seam_collar(world, 'west', gx, gz), gx, gz
        finally:
            C.GATED_SEAMS = SHIPPED

    def test_the_collar_is_one_tile_of_the_neighbour_and_only_for_an_open_seam(self):
        collar, gx, _ = self.collar(())
        self.assertTrue(collar.any(), 'a widened seam opens the first tile across its border')
        opened = gx[collar]
        self.assertGreaterEqual(opened.min(), 20., 'the collar is the neighbour\'s ground, never our own')
        self.assertLessEqual(opened.max(), 21., 'and only the first tile of it')

    def test_a_gated_seam_has_no_collar(self):
        collar, _, _ = self.collar(GATED)
        self.assertFalse(collar.any())


class HeightScaleTests(unittest.TestCase):
    def test_the_collar_cannot_stretch_a_territory_s_height_scale(self):
        heights = np.array([[0., 10., 30.], [5., 40., 200.]])
        own = np.array([[True, True, True], [True, False, False]])
        collar = ~own
        grid, encoding = CE.encode_heights(heights, own | collar, basis=own)
        plain, plain_encoding = CE.encode_heights(heights, own)
        self.assertEqual(encoding, plain_encoding, "the scale is the territory's own")
        self.assertTrue((grid[own] == plain[own]).all(), 'its own ground encodes exactly as before')
        self.assertNotEqual(grid[1, 1], 0, 'neighbouring ground the scale can express is opened')
        self.assertEqual(grid[1, 2], 0, 'ground beyond the scale is left closed, never clamped to its top step')

    def test_a_territory_with_no_collar_keeps_its_scale(self):
        heights = np.array([[0., 10.], [30., 5.]])
        walkable = np.ones((2, 2), bool)
        self.assertEqual(CE.encode_heights(heights, walkable, basis=walkable)[1],
                         CE.encode_heights(heights, walkable)[1])


if __name__ == '__main__':
    unittest.main()

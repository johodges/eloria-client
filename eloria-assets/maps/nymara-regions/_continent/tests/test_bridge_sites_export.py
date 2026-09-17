"""A bridge deck is its site span plus landings of at most 6 m; piers stand only under the span; designed decks are named."""
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest

import numpy as np
from scipy.ndimage import label

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bridge_export as B
import landscape as L
import scene_io as S


def crossing(level=0.):
    """A 12 m river along z at x 18..30 (deep), dry banks at 2 m, one claimed site square across it at z 20."""
    w = SimpleNamespace(x0=0., z0=0., x1=60., z1=40., ids=['west', 'east'], connections=[], plan={})
    w.height_at = lambda x, z: np.where((np.asarray(x) >= 18) & (np.asarray(x) <= 30), -2., 2.) + np.asarray(z) * 0
    w.owner_at = lambda x, z: np.where(np.asarray(x) < 24, 0, 1) + np.asarray(z, dtype=int) * 0
    w.roads = [{'id': 'seam', 'width': 3., 'points': [[2, 2, 20], [58, 2, 20]]}]
    w.crossing_sites = [{'id': 4, 'key': 'main@20', 'river': 'main', 'wetEdges': [[18., 20.], [30., 20.]],
                         'routeLandings': [[9., 20.], [39., 20.]]}]
    w.crossing_site_roads = {4: {'seam'}}
    return w


def water(x, z, *, height, plan):
    wet = (np.asarray(x) >= 18) & (np.asarray(x) <= 30)
    return {'mask': wet, 'depth': np.where(wet, 2., 0.), 'surface': np.zeros(np.shape(height)), 'river_mask': wet}


class SiteDeckTests(unittest.TestCase):
    def test_the_deck_is_the_span_plus_landings_of_at_most_six_metres(self):
        w = crossing()
        field = B.common_surface(w, water_fields=water)
        columns = np.flatnonzero(field['mask'].any(axis=0))
        self.assertGreaterEqual(columns.min(), 18 - 6); self.assertLessEqual(columns.max() + 1, 30 + 6)
        self.assertEqual([d['sites'] for d in field['decks']], [[4]])
        self.assertEqual(field['decks'][0]['component'], 5)               # named by its site (id + 1)
        self.assertEqual(field['riverWaterOutsideSites']['cells'], 0)
        self.assertLessEqual(field['decks'][0]['maximumDryLiftMetres'], L.CROSSING_POLICY_DEFAULTS['deck_lift_metres'])

    def test_piers_stand_only_over_the_water(self):
        w = crossing()
        with tempfile.TemporaryDirectory() as temporary:
            parts = B.build_bridges(w, Path(temporary) / 'bridges.glb', water_fields=water)
        piers = [p for p in parts if p['node'].startswith('BridgeUnionPier_')]
        self.assertTrue(piers)
        for pier in piers:
            low, high = pier['bounds']
            x = float((low[0] + high[0]) * .5)
            self.assertTrue(18 <= x <= 30, x)
        floors = {p['node'] for p in parts if p['node'].startswith('Walk_ContinentalBridgeUnion_')}
        self.assertEqual(floors, {'Walk_ContinentalBridgeUnion_005_west', 'Walk_ContinentalBridgeUnion_005_east'})

    def test_a_site_deck_in_two_pieces_emits_one_floor_per_territory(self):
        # Two narrow roads cross the same site 6 m apart: their deck cells never touch, so the site's deck is two
        # components that both take the site's number; the export merges them into one node per territory.
        w = crossing()
        w.roads = [{'id': 'north', 'width': 1., 'points': [[2, 2, 17], [58, 2, 17]]},
                   {'id': 'south', 'width': 1., 'points': [[2, 2, 23], [58, 2, 23]]}]
        field = B.common_surface(w, water_fields=water)
        self.assertEqual([d['component'] for d in field['decks']], [5, 5])
        with tempfile.TemporaryDirectory() as temporary:
            parts = B.build_bridges(w, Path(temporary) / 'bridges.glb', water_fields=water)
        names = [p['node'] for p in parts]
        self.assertEqual(len(names), len(set(names)))
        floors = [p for p in parts if p['node'].startswith('Walk_ContinentalBridgeUnion_')]
        self.assertEqual(sorted(p['node'] for p in floors), ['Walk_ContinentalBridgeUnion_005_east', 'Walk_ContinentalBridgeUnion_005_west'])
        for part in floors:
            low, high = part['bounds']
            self.assertLess(float(low[2]), 18.); self.assertGreater(float(high[2]), 22.)   # both pieces in one node

    def test_a_long_approach_is_ground_not_deck(self):
        # A road that stays on its bank for 20 m past the water gets no deck beyond the six-metre landing.
        w = crossing()
        w.roads = [{'id': 'seam', 'width': 3., 'points': [[2, 2, 20], [58, 2, 20]]},
                   {'id': 'bank', 'width': 2., 'points': [[40, 2, 5], [40, 2, 35]]}]
        field = B.common_surface(w, water_fields=water)
        self.assertFalse(field['mask'][:, 37:].any())

    def test_deep_water_away_from_every_site_gets_the_same_short_deck_and_river_water_is_reported(self):
        w = crossing(); w.crossing_sites = []
        field = B.common_surface(w, water_fields=water)
        columns = np.flatnonzero(field['mask'].any(axis=0))
        self.assertGreaterEqual(columns.min(), 12); self.assertLessEqual(columns.max() + 1, 36)
        self.assertGreaterEqual(field['decks'][0]['component'], 500)
        self.assertGreater(field['riverWaterOutsideSites']['cells'], 0)

    def test_a_landing_trim_never_leaves_a_deck_in_pieces(self):
        # The east bank's first dry metre lies at the water line and the bank then rises 2 m in a metre: the deck,
        # held over the water, lifts about 1.5 m over that metre, so the trim cuts the landing's first dry column
        # across the whole road. The landing cells beyond the cut would be a floor of their own (the Amberwater
        # crossing at the Amberwood hub was split [104, 36] this way): they go with the cut, and the report says
        # where a bank ended a landing.
        w = crossing()
        w.height_at = lambda x, z: np.select([(np.asarray(x) >= 18) & (np.asarray(x) <= 30), (np.asarray(x) > 30) & (np.asarray(x) < 32)],
                                             [-2., 0.], 2.) + np.asarray(z) * 0
        field = B.common_surface(w, water_fields=water)
        self.assertEqual([d['sites'] for d in field['decks']], [[4]])
        _, pieces = label(field['mask'], structure=B.CROSS)
        self.assertEqual(pieces, 1)
        self.assertFalse(field['mask'][:, 31:].any())                  # nothing of the east landing beyond its cut
        self.assertTrue(field['mask'][:, 12:18].any())                 # the west landing, which fits, stays
        self.assertGreater(field['cutOffLandingCells'], 0)
        self.assertTrue(any(abs(x - 31.5) <= 1 and abs(z - 20) <= 2 for x, z in field['cutOffLandingBanks']))

    def test_a_landing_cut_keeps_every_piece_still_joined_to_the_water(self):
        mask = np.ones((3, 6), bool)
        dry = np.zeros((3, 6), bool); dry[:, 2:] = True               # columns 0-1 stand over the water
        cut = np.zeros((3, 6), bool); cut[:, 3] = True                # a full-width cut in the landing
        removed = B.landing_cut(mask, cut, dry)
        self.assertTrue(removed[:, 3:].all()); self.assertFalse(removed[:, :3].any())
        cut[:, 3] = False; cut[0, 3] = True                           # a partial cut parts nothing
        self.assertEqual(B.landing_cut(mask, cut, dry).tolist(), cut.tolist())

    def test_the_retired_apron_keys_are_refused(self):
        for key in ('bridge_approach_aprons', 'bridge_approach_connections'):
            w = crossing(); w.plan = {key: {'west': 96.}}
            with self.assertRaisesRegex(ValueError, 'retired by the roads pass'):
                B.common_surface(w, water_fields=water)


class DesignedDeckTests(unittest.TestCase):
    PLAN = {'designed_decks': [
        {'name': 'Walk_Amber_RootRamp', 'module': 'amberwood_access', 'note': 'the ramp onto the Motherroot plateau'},
        {'name': 'Walk_Manymouth_Village_*', 'module': 'manymouth_village_streets', 'note': 'village streets on piles'}]}

    def test_designed_decks_are_named_exactly_or_by_family_and_by_their_module(self):
        self.assertEqual(L.validate_designed_decks(self.PLAN), [])
        self.assertEqual(L.designed_deck_entry(self.PLAN, 'Walk_Manymouth_Village_town')['module'], 'manymouth_village_streets')
        self.assertIsNone(L.designed_deck_entry(self.PLAN, 'Walk_Amber_RootRampExtension'))
        L.require_designed_deck(self.PLAN, 'Walk_Amber_RootRamp', 'amberwood_access')
        with self.assertRaisesRegex(ValueError, 'does not name'):
            L.require_designed_deck(self.PLAN, 'Walk_Amber_CanopyBridge', 'amberwood_access')
        with self.assertRaisesRegex(ValueError, "under 'amberwood_access'"):
            L.require_designed_deck(self.PLAN, 'Walk_Amber_RootRamp', 'manymouth_access')
        # A plan that predates the rule carries no list and refuses nothing.
        self.assertIsNone(L.require_designed_deck({}, 'Walk_Anything', 'any_module'))

    def test_invalid_lists_are_reported(self):
        bad = {'designed_decks': [{'name': 'Walk_*_Deck', 'module': 'x', 'note': 'y'}, {'name': 'Walk_A', 'module': '', 'note': 'y'},
                                  {'name': 'Walk_A', 'module': 'x', 'note': 'y', 'height': 3}]}
        problems = L.validate_designed_decks(bad)
        self.assertTrue(any("ending in one '*'" in p for p in problems))
        self.assertTrue(any("needs a non-empty string 'module'" in p for p in problems))
        self.assertTrue(any('listed twice' in p for p in problems))
        self.assertTrue(any('unknown key' in p for p in problems))

    def test_the_plan_names_every_support_module_deck(self):
        plan = L.load_plan()
        self.assertEqual(L.validate_designed_decks(plan), [])
        self.assertNotIn('bridge_approach_aprons', plan)
        self.assertNotIn('bridge_approach_connections', plan)
        for name, module in (('Walk_Amber_MarketCanopyStair', 'amberwood_access'), ('Walk_Amber_RootRamp', 'amberwood_access'),
                             ('Walk_Manymouth_FishingBoardwalk', 'manymouth_access'), ('Walk_Manymouth_PaddyStreet', 'manymouth_access'),
                             ('Walk_Manymouth_Village_town', 'manymouth_village_streets'), ('Walk_Mirror_BankRamp_Quay', 'mirror_access_geometry'),
                             ('Walk_FerryQuay_westhaven_00', 'ferry_export'), ('Landmark_boardwalk_bog', 'grey_crossings')):
            L.require_designed_deck(plan, name, module)


if __name__ == '__main__':
    unittest.main()

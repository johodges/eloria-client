"""Coordinate publication must preserve identities and be repeatable."""
import json
from pathlib import Path
import sqlite3
import struct
import tempfile
import unittest

import publish_continent_geography as P


def maps():
    return {'four_gates': {'nativeServerOrigin': [6, 6], 'serverOrigin': [12, 18],
                           'serverCells': [24, 24], 'delta': [6, 12],
                           'translation': [100, -19, 200], 'arrival': [13, 19]},
            'westhaven': {'nativeServerOrigin': [12, 12], 'serverOrigin': [12, 12],
                          'serverCells': [24, 24], 'delta': [0, 0],
                          'translation': [0, 0, 0], 'arrival': [5, 6]}}


class PublicationTests(unittest.TestCase):
    def test_profile_shifts_both_portal_shapes_without_changing_ids_or_dialogue(self):
        text = ('# retain this header\r\n'
                'portal | four_gates | 7 | 8 | room | 9 | 10\r\n'
                'portal | room | 509 | 2 | 3 | four_gates | 7 | 8\r\n'
                'map | four_gates | Four Gates | maps/four_gates.elm | FG\r\n')
        result, count = P.rewrite_profile(text, P.RULES['maps.txt'], maps())
        self.assertEqual(count, 2)
        self.assertIn('four_gates | 13 | 20 | room | 9 | 10', result)
        self.assertIn('room | 509 | 2 | 3 | four_gates | 13 | 20', result)
        self.assertEqual(result.count('\r\n'), 4)
        self.assertTrue(result.endswith('maps/four_gates.elm | FG\r\n'))
        npc = 'npc | Ilyon | four_gates | 7 | 8 | shop_99 | story stays\n'
        self.assertIn('shop_99 | story stays', P.rewrite_profile(npc, P.RULES['npcs.txt'], maps())[0])
        west = 'npc | Warden | westhaven | 7 | 8 | shop_99\n'
        self.assertEqual(P.rewrite_profile(west, P.RULES['npcs.txt'], maps()), (west, 0))

    def test_definition_returns_and_monsters_follow_their_own_maps(self):
        text = ('map_id: maps/room.elm\nentry_x: 2\nentry_y: 3\n'
                'exit_map: four_gates\nexit_x: 7\nexit_y: 8\n'
                'map_id: maps/four_gates.elm.gz\ntype: river_otter\nx_pos: 9\ny_pos: 10\n'
                'map_id: maps/westhaven.elm\ntype: old_species\nx_pos: 11\ny_pos: 12\n')
        result, count = P.rewrite_definition(text, maps())
        self.assertEqual(count, 4)
        self.assertIn('entry_x: 2\nentry_y: 3', result)
        self.assertIn('exit_x: 13\nexit_y: 20', result)
        self.assertIn('type: river_otter\nx_pos: 15\ny_pos: 22', result)
        self.assertTrue(result.endswith('type: old_species\nx_pos: 11\ny_pos: 12\n'))

    def test_interior_return_marker_uses_destination_frame(self):
        record = {'id': 'room', 'arrival': [2, 3], 'exit': {'serverTile': [4, 5],
                  'destinationMap': 'four_gates', 'destinationTile': [7, 8], 'position': [1, 2, 3]}}
        shifted = P.shift_markers(record, 'room', maps())
        self.assertEqual(shifted['arrival'], [2, 3])
        self.assertEqual(shifted['exit']['serverTile'], [4, 5])
        self.assertEqual(shifted['exit']['destinationTile'], [13, 20])
        self.assertEqual(shifted['exit']['position'], [1, 2, 3])

    def test_native_mapping_uses_both_axes_before_padding(self):
        spec = maps()
        spec['four_gates']['_native_mapper'] = lambda point: [point[0] + point[1], point[1] * 2]
        text = 'map_id: room\nexit_map: four_gates\nexit_x: 7\nexit_y: 8\n'
        result, count = P.rewrite_definition(text, spec)
        self.assertEqual(count, 2)
        self.assertTrue(result.endswith('exit_x: 21\nexit_y: 28\n'))
        self.assertEqual(P.shifted([7, 8], 'four_gates', spec), [21, 28])

    def test_serialized_native_field_maps_and_extrapolates_old_world_coordinates(self):
        data = {'legacyOrigin': [174, 174], 'nativeOrigin': [138, 120],
                'axes': {'x': {'old': [-174, 0, 402], 'new': [-138, 0, 342]},
                         'z': {'old': [-402, 0, 174], 'new': [-276, 0, 120]}}}
        convert = P.native_mapper(data, [194, 183])
        self.assertEqual(convert([194, 183]), [138, 120])
        self.assertEqual(convert([596, 585]), [480, 396])
        self.assertAlmostEqual(P.map_axis(804, data['axes']['x']), 684)
        data['axes']['x']['new'] = [0, 0, 342]
        with self.assertRaisesRegex(ValueError, 'strictly monotone'):
            P.native_mapper(data, [174, 174])

    def test_native_compact_save_reset_is_once_then_padding_preserves_later_travel(self):
        spec = maps()
        spec['four_gates']['nativeRevision'] = 'native-compact-v1'
        namespace = {}
        exec(P.runtime_migration_source(spec), namespace)
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE global_state(key TEXT PRIMARY KEY,value TEXT)')
        db.execute('CREATE TABLE characters(username TEXT,map_id TEXT,x INTEGER,y INTEGER,quest_state TEXT,inventory TEXT)')
        quest = '{"quest":7,"daily_positions":"four_gates:7:8"}'
        db.execute('INSERT INTO characters VALUES (?,?,?,?,?,?)', ('resident', 'four_gates', 7, 8, quest, '{"Coin":42}'))
        namespace['migrate'](db)
        row = db.execute('SELECT x,y,quest_state,inventory FROM characters').fetchone()
        self.assertEqual(row, (13, 19, quest, '{"Coin":42}'))
        db.execute('UPDATE characters SET x=15,y=20')
        namespace['migrate'](db)
        self.assertEqual(db.execute('SELECT x,y FROM characters').fetchone(), (15, 20))
        namespace['MAPS']['four_gates']['serverOrigin'] = [13, 18]
        namespace['migrate'](db)
        self.assertEqual(db.execute('SELECT x,y FROM characters').fetchone(), (16, 20))
        db.close()

    def test_quest_stages_shift_visit_coordinates_without_reward_changes(self):
        text = ('key: unchanged_quest\n[stage]\nkind: visit\nmap: four_gates\nx: 7\ny: 8\n'
                'xp: overall=400\n[/stage]\n[stage]\nkind: talk\nx: 0\ny: 0\n[/stage]\n')
        result, count = P.rewrite_definition(text, maps())
        self.assertEqual(count, 2)
        self.assertIn('key: unchanged_quest', result)
        self.assertIn('x: 13\ny: 20\nxp: overall=400', result)
        self.assertTrue(result.endswith('kind: talk\nx: 0\ny: 0\n[/stage]\n'))

    def test_approved_visit_override_preserves_other_quests_and_rewards(self):
        text = ('[quest]\nkey: whitehorn_tag\nreward_gold: 350\n[stage]\nkind: visit\n'
                'map: whitehorn_range\nx: 528\ny: 368\nobjective: East of the cascade\nxp: overall=400\n'
                '[/stage]\n[/quest]\n[quest]\nkey: other\n[stage]\nkind: visit\nmap: whitehorn_range\nx: 2\ny: 3\n[/stage]\n[/quest]\n')
        result = P.quest_visit(text, 'whitehorn_tag', 'whitehorn_range', [369, 313])
        self.assertIn('x: 369\ny: 313\nobjective: East of the cascade\nxp: overall=400', result)
        self.assertIn('reward_gold: 350', result)
        self.assertTrue(result.endswith('map: whitehorn_range\nx: 2\ny: 3\n[/stage]\n[/quest]\n'))

    def test_source_edits_keep_gameplay_values_and_ignore_kill_sentinels(self):
        daily = ('# ünicode stays\nTASKS = (DailyTask("Sage","harvest","Seed",18,"four_gates",7,8,38,220),\n'
                 'DailyTask("Sage","kill","Otter",8,"four_gates",0,0,105,300))\n')
        result = P.rewrite_python(daily, 'daily', maps())
        self.assertIn('"Seed",18,"four_gates",13,20,38,220', result)
        self.assertIn('"Otter",8,"four_gates",0,0,105,300', result)
        arena = 'ZONES = (PKZone("four_gates",1,2,5,6,40,True), PKZone("westhaven",1,2,5,6,60,True))\n'
        result = P.rewrite_python(arena, 'pk', maps())
        self.assertIn('"four_gates",7,14,11,18,40,True', result)
        self.assertIn('"westhaven",1,2,5,6,60,True', result)

    def test_saved_characters_translate_once_preserving_progress_and_later_travel(self):
        namespace = {}
        exec(P.runtime_migration_source(maps()), namespace)
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE global_state(key TEXT PRIMARY KEY,value TEXT)')
        db.execute('CREATE TABLE characters(username TEXT PRIMARY KEY,map_id TEXT,x INTEGER,y INTEGER,quest_state TEXT,inventory TEXT)')
        quest = json.dumps({'quest': 7, 'daily_positions': 'four_gates:7:8,westhaven:1:2'})
        db.executemany('INSERT INTO characters VALUES (?,?,?,?,?,?)', [
            ('resident', 'four_gates', 7, 8, quest, '{"Coin":42}'),
            ('invalid', 'four_gates', 900, 900, '{}', '{}'),
            ('outside', 'room', 2, 3, '{}', '{}'),
            ('no_shift', 'westhaven', 5, 6, '{}', '{}')])
        namespace['migrate'](db)
        row = db.execute('SELECT x,y,quest_state,inventory FROM characters WHERE username="resident"').fetchone()
        self.assertEqual(row[:2], (13, 20))
        self.assertEqual(row[3], '{"Coin":42}')
        self.assertEqual(json.loads(row[2]), {'quest': 7, 'daily_positions': 'four_gates:13:20,westhaven:1:2'})
        self.assertEqual(db.execute('SELECT x,y FROM characters WHERE username="invalid"').fetchone(), (13, 19))
        self.assertEqual(db.execute('SELECT x,y FROM characters WHERE username="outside"').fetchone(), (2, 3))
        self.assertEqual(db.execute('SELECT x,y FROM characters WHERE username="no_shift"').fetchone(), (5, 6))
        db.execute('UPDATE characters SET x=14,y=21 WHERE username="resident"')
        namespace['migrate'](db)
        self.assertEqual(db.execute('SELECT x,y FROM characters WHERE username="resident"').fetchone(), (14, 21))
        # A later revision moves from the recorded origin, never from baseline again.
        namespace['MAPS']['four_gates']['serverOrigin'] = [13, 18]
        namespace['migrate'](db)
        self.assertEqual(db.execute('SELECT x,y FROM characters WHERE username="resident"').fetchone(), (15, 21))
        db.close()

    def test_invalid_grid_and_fractional_shift_fail_before_publication(self):
        data = self.geography()
        data['regions']['four_gates']['serverCells'] = [23, 24]
        with self.assertRaisesRegex(ValueError, 'divisible by six'):
            P.contracts(data, {})
        data = self.geography()
        data['regions']['four_gates']['serverOrigin'] = [12.5, 18]
        with self.assertRaisesRegex(ValueError, 'must be integers'):
            P.contracts(data, {})

    @staticmethod
    def geography():
        return {'schema': 1, 'geometryMode': 'continent-owned-v1', 'regions': {
            'four_gates': {'nativeServerOrigin': [6, 6], 'serverOrigin': [12, 18],
                           'serverCells': [24, 24], 'serverTileShift': [6, 12], 'translation': [100, -19, 200]}}}

    def fixture(self, root):
        client, server = root / 'client', root / 'server'
        def put(path, text):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
        profile = server / 'config/eloria'
        for filename in P.RULES:
            put(profile / filename, '# untouched\n')
        put(profile / 'npcs.txt', 'npc | Ilyon | four_gates | 7 | 8 | shop42\n')
        put(profile / 'maps.txt', 'portal | room | 509 | 2 | 3 | four_gates | 7 | 8\n')
        put(profile / 'client_content_manifest.json', json.dumps({'maps': [{'id': 'four_gates', 'arrival': [7, 7], 'server_cells': 12}]}))
        put(server / 'tools/generate_nymara_maps.py', 'FOUR_GATES_TILES_WIDE=2\nMAP_TILES_WIDE_BY_NAME={"four_gates":2}\nARRIVAL_TILES={"four_gates":(7,7)}\n')
        put(server / 'eloria/map_layout.py', 'FOUR_GATES_ARRIVAL=(7,7)\nCOASTAL_ARRIVALS={"four_gates":FOUR_GATES_ARRIVAL}\nSOUTHERN_ARRIVALS={}\n')
        put(server / 'eloria/world.py', 'TUTORIAL_ROUTE_MARKERS=((7,8),)\nTUTORIAL_HARVESTS=(("Seed",7,8,2),)\n')
        put(server / 'eloria/walkthrough.py', 'PLAZA=(7,8)\n')
        put(server / 'eloria/pk.py', 'ZONES=(PKZone("four_gates",1,2,5,6,40,True),)\n')
        put(server / 'eloria/daily_quests.py', 'TASKS=(DailyTask("Sage","harvest","Seed",18,"four_gates",7,8,38,220),)\n')
        put(server / 'eloria/database.py', 'class Database:\n    def init(self):\n'
            '        migration = "coastal_landscapes_396_v1"\n'
            '        self.migrate_experience_curve()\n')
        put(client / 'godot-client/data/maps/registry.json', json.dumps({'maps': {'four_gates': {'manifest': 'keep-path', 'coordinateTransform': {}}}}))
        package = P.package(client, 'four_gates')
        put(package / 'world.json', json.dumps({'asset': {'serverCells': 24},
            'continentGeography': {'geographySha256': P.digest(json.dumps(self.geography()).encode('utf-8'))},
            'coordinateTransform': {'serverOrigin': [12, 18], 'serverCells': [24, 24]}}))
        (package / 'collision.bin').write_bytes(struct.pack('<4sHHII', b'EWCG', 2, 0, 48, 48) + bytes(48*48))
        geo = client / 'geography.json'
        put(geo, json.dumps(self.geography()))
        return client, server, geo

    def test_full_plan_dry_run_repeat_and_changed_input_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            client, server, geo = self.fixture(Path(tmp))
            npc = server / 'config/eloria/npcs.txt'
            original = npc.read_bytes()
            before, pending, report = P.plan(client, server, geo, True)
            self.assertEqual(npc.read_bytes(), original)
            self.assertTrue(report['packageChecks'][0]['expandedPackageReady'])
            self.assertEqual(report['maps']['four_gates']['arrival'], [13, 19])
            P.apply_plan(before, pending)
            self.assertIn('13 | 20 | shop42', npc.read_text())
            database = (server / 'eloria/database.py').read_text()
            self.assertLess(database.index('migrate_continent_geography(self.db)'),
                            database.index('migration = "coastal_landscapes_396_v1"'))
            self.assertEqual(P.plan(client, server, geo, True)[1], {})
            npc.write_bytes(b'# concurrent change\n')
            with self.assertRaisesRegex(ValueError, 'changed during planning'):
                P.apply_plan(before, pending)

    def test_full_native_publication_requires_audit_and_maps_only_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            client, server, geo = self.fixture(Path(tmp))
            migration = {'revision': 'compact-v1', 'ready': False,
                'legacyOrigin': [6, 6], 'nativeOrigin': [6, 6], 'legacyCells': 24, 'nativeCells': 24,
                'nativeArrival': [7, 7], 'axes': {'x': {'old': [-6, 6], 'new': [-6, 3]},
                                                'z': {'old': [-6, 6], 'new': [-6, 3]}}}
            path = P.package(client, 'four_gates') / 'source/continent-migration.json'
            path.parent.mkdir()
            path.write_bytes(P.json_bytes(migration))
            with self.assertRaisesRegex(ValueError, 'physical route audit'):
                P.plan(client, server, geo, True)
            migration['ready'] = True
            path.write_bytes(P.json_bytes(migration))
            before, pending, report = P.plan(client, server, geo, True)
            self.assertTrue(report['maps']['four_gates']['nativeMappingApplied'])
            P.apply_plan(before, pending)
            npc = (server / 'config/eloria/npcs.txt').read_text()
            self.assertIn('11 | 21 | shop42', npc)
            self.assertEqual(P.plan(client, server, geo, True)[1], {})

    def test_all_twelve_exteriors_suppress_generic_portals_without_changing_room_markers(self):
        regions = ('four_gates', 'mirrorhold', 'crownwater', 'whitehorn_range',
                   'amethyst_barrens', 'sunmane_steppe', 'amberwood', 'grey_moors',
                   'westhaven', 'verdant_stair', 'ssarathi_ruins', 'manymouth_delta')
        with tempfile.TemporaryDirectory() as tmp:
            client, server, geo = self.fixture(Path(tmp))
            geography = self.geography()
            registry_path = client / 'godot-client/data/maps/registry.json'
            registry = json.loads(registry_path.read_text())
            preserved = {'manymouth_flooded_labyrinth': {'manifest': 'ordinary-room',
                           'interiorOf': 'manymouth_delta', 'landscapeTransitions': False},
                         'manymouth_delta_secrets': {'manifest': 'secret-room',
                           'secretOf': 'manymouth_delta', 'markerStyle': 'interactive'}}
            registry['maps'].update(preserved)
            for region in regions[1:]:
                geography['regions'][region] = {
                    'nativeServerOrigin': [6, 6], 'serverOrigin': [6, 6],
                    'serverCells': [24, 24], 'serverTileShift': [0, 0],
                    'translation': [0, 0, 0]}
                registry['maps'][region] = {'manifest': region + '/world.json'}
            geo.write_bytes(P.json_bytes(geography))
            registry_path.write_bytes(P.json_bytes(registry))
            generator = server / 'tools/generate_nymara_maps.py'
            generator.write_text('FOUR_GATES_TILES_WIDE=2\nMAP_TILES_WIDE_BY_NAME='
                                 + repr({r: 2 if r == 'four_gates' else 4 for r in regions})
                                 + '\nARRIVAL_TILES=' + repr({r: (7, 7) for r in regions}) + '\n')
            for region, spec in geography['regions'].items():
                root = P.package(client, region)
                root.mkdir(parents=True, exist_ok=True)
                (root / 'world.json').write_bytes(P.json_bytes({
                    'coordinateTransform': {'serverOrigin': spec['serverOrigin'],
                                            'serverCells': spec['serverCells']},
                    'continentGeography': {'geographySha256': P.digest(geo.read_bytes())}}))
                (root / 'collision.bin').write_bytes(
                    struct.pack('<4sHHII', b'EWCG', 2, 0, 48, 48) + bytes(48 * 48))
            migration = P.package(client, 'manymouth_delta') / 'source/continent-migration.json'
            migration.parent.mkdir()
            migration.write_bytes(P.json_bytes({'revision': 'registry-fixture-v1', 'ready': True,
                'legacyOrigin': [6, 6], 'nativeOrigin': [6, 6], 'legacyCells': 24, 'nativeCells': 24,
                'nativeArrival': [7, 7], 'axes': {
                    axis: {'old': [-6, 18], 'new': [-6, 18]} for axis in ('x', 'z')}}))
            before, pending, report = P.plan(client, server, geo, True)
            result = json.loads(pending[registry_path])['maps']
            self.assertEqual(len(report['packageChecks']), 12)
            for region in regions:
                with self.subTest(region=region):
                    self.assertIs(result[region]['landscapeTransitions'], True)
                    self.assertEqual(result[region]['manifest'], registry['maps'][region]['manifest'])
            for region, entry in preserved.items():
                self.assertEqual(result[region], entry)
            P.apply_plan(before, pending)
            self.assertEqual(P.plan(client, server, geo, True)[1], {})

    def test_existing_late_save_hook_moves_before_current_safe_arrivals_once(self):
        for newline in ('\n', '\r\n'):
            with self.subTest(newline=newline):
                source = ('class Database:\n    def init(self):\n'
                          '        migration = "coastal_landscapes_396_v1"\n'
                          '        self.reset_coastal_arrivals()\n'
                          '        from .continent_geography import migrate as migrate_continent_geography\n'
                          '        migrate_continent_geography(self.db)\n'
                          '        self.migrate_experience_curve()\n').replace('\n', newline)
                result = P.install_geography_hook(source)
                self.assertEqual(result.count('migrate_continent_geography(self.db)'), 1)
                self.assertLess(result.index('migrate_continent_geography(self.db)'),
                                result.index('self.reset_coastal_arrivals()'))
                self.assertEqual(P.install_geography_hook(result), result)
                if newline == '\r\n':
                    self.assertNotIn('\n', result.replace('\r\n', ''))

    def test_missing_safe_arrival_slot_fails_before_source_publication(self):
        with self.assertRaisesRegex(ValueError, 'before coastal safe arrivals'):
            P.install_geography_hook('class Database:\n    def init(self):\n        self.migrate_experience_curve()\n')

    def test_unexpanded_package_is_only_plannable_not_applicable(self):
        with tempfile.TemporaryDirectory() as tmp:
            client, server, geo = self.fixture(Path(tmp))
            (P.package(client, 'four_gates') / 'collision.bin').write_bytes(struct.pack('<4sHHII', b'EWCG', 2, 0, 24, 24))
            self.assertFalse(P.plan(client, server, geo)[2]['packageChecks'][0]['expandedPackageReady'])
            with self.assertRaisesRegex(ValueError, 'not ready'):
                P.plan(client, server, geo, True)


if __name__ == '__main__':
    unittest.main()

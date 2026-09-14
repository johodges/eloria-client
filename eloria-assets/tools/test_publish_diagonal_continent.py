"""Named territories receive one shared continent without corrupting contracts."""
import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest

import publish_diagonal_continent as P


def specs():
    return {name: {'serverOrigin': [12, 12], 'previousServerOrigin': [6, 6],
        'serverCells': [24, 24], 'arrival': [12, 12], 'translation': [x, 0, 0],
        'terrainRevision': 'diagonal-spine-v1', 'contentTransform': {
            'scale': 1, 'sourceCenter': [0, 0], 'targetCenter': [0, 0]},
        'tilePositions': {}, 'contentPositions': {}}
        for name, x in [('four_gates', 0), ('westhaven', 20)]}


def connections():
    return [{'id': 'trade-road', 'type': 'land', 'ends': [
        {'region': name, 'portal': portal, 'tile': [x, 12], 'arrival': [ax, 12],
         'lanes': [{'tile': [x, y], 'arrival': [ax, y]} for y in range(9, 16)],
         'frame': {'anchor': [anchor, 0, 0], 'outward': [out, 0], 'geometryMode': 'continent-chunks-v1'}}
        for name, portal, x, ax, anchor, out in [('four_gates', 'west', 22, 21, 10, 1),
                                               ('westhaven', 'east', 1, 2, -10, -1)]]}]


class PublicationTests(unittest.TestCase):
    def test_server_placement_contract_retains_original_semantics_on_republication(self):
        regions = specs()
        spec = regions['four_gates']
        spec.update(baselineServerOrigin=[3, 4], baselineTilePositions={'5:6': [14, 15]},
                    baselineContentTransform={'scale': .78, 'sourceCenter': [1, 2], 'targetCenter': [0, 0]},
                    contentPositions={'npcs': {'Bob': [14, 15]}},
                    portalPositions={'door': {'oldTile': [9, 10], 'tile': [17, 18]}})
        spec['tilePositions'] = {'9:10': [14, 15]}
        contract = P.placement_contracts(regions)['four_gates']
        self.assertEqual(contract['baselineServerOrigin'], [3, 4])
        self.assertEqual(contract['baselineTilePositions'], {'5:6': [14, 15]})
        self.assertEqual(contract['contentPositions']['npcs']['Bob'], [14, 15])
        self.assertEqual(contract['portalPositions']['door']['tile'], [17, 18])
        contract['baselineTilePositions']['5:6'][0] = 99
        self.assertEqual(spec['baselineTilePositions']['5:6'], [14, 15])

    def test_scale_uses_cell_centres_and_exact_remaps_win(self):
        spec = specs()['four_gates']
        self.assertEqual(P.transform_tile([7, 8], spec), [13, 14])
        spec['contentTransform']['scale'] = .5
        self.assertEqual(P.transform_tile([7, 8], spec), [12, 13])
        spec['tilePositions']['7:8'] = [4, 5]
        self.assertEqual(P.transform_tile([7, 8], spec), [4, 5])

    def test_lane_order_does_not_change_global_position(self):
        links = connections()
        links[0]['ends'][1]['lanes'].reverse()
        text, rows = P.connection_rows(links, specs())
        self.assertEqual(len(rows), 14)
        self.assertEqual(text.count('portal |'), 14)
        for source, x, y, dest, ax, ay in rows:
            self.assertEqual(P.world_point(source, [x, y], specs()), P.world_point(dest, [ax, ay], specs()))

    def test_bad_lane_match_and_bounce_fail(self):
        links = connections()
        links[0]['ends'][1]['lanes'][0]['arrival'][0] += 1
        with self.assertRaisesRegex(ValueError, 'no arrival at the same global'):
            P.connection_rows(links, specs())
        links = connections()
        links[0]['ends'][0]['lanes'][0]['tile'] = links[0]['ends'][0]['lanes'][0]['arrival']
        links[0]['ends'][1]['lanes'][0]['arrival'] = links[0]['ends'][1]['lanes'][0]['tile']
        with self.assertRaisesRegex(ValueError, 'immediately triggers'):
            P.connection_rows(links, specs())

    def test_three_ferries_publish_six_distinct_docks_without_becoming_walk_links(self):
        regions = {name: copy.deepcopy(specs()['four_gates']) for name in (
            'crownwater', 'westhaven', 'manymouth_delta', 'ssarathi_ruins')}
        ferries = []
        for index, shore in enumerate(('westhaven', 'manymouth_delta', 'ssarathi_ruins')):
            ferries.append({'id': 'crownwater--' + shore, 'type': 'ferry', 'ends': [
                {'region': 'crownwater', 'portal': 'ferry-to-' + shore,
                 'tile': [20, 5 + index*5], 'arrival': [16, 5 + index*5]},
                {'region': shore, 'portal': 'ferry-to-crownwater', 'tile': [10, 9], 'arrival': [6, 9]}]})
        emitted, rows = P.connection_rows(ferries, regions)
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(len(line.split('|')) == 7 for line in emitted.splitlines() if line.startswith('portal')))
        for index, shore in enumerate(('westhaven', 'manymouth_delta', 'ssarathi_ruins')):
            self.assertIn(('crownwater', 20, 5 + index*5, shore, 6, 9), rows)
            self.assertIn((shore, 10, 9, 'crownwater', 16, 5 + index*5), rows)
        graph, stream = P.connection_manifests({'revision': 'diagonal-spine-v1', 'connections': ferries}, {}, regions)
        self.assertEqual(len(graph['connections']), 3)
        self.assertEqual(stream['connections'], [])
        ferries[1]['ends'][0]['tile'] = list(ferries[0]['ends'][0]['tile'])
        with self.assertRaisesRegex(ValueError, 'duplicate exterior departure'):
            P.connection_rows(ferries, regions)

    def test_explicit_spawn_ordinal_preserves_species_and_order(self):
        regions = specs()
        regions['four_gates']['contentPositions']['spawns'] = {'1': [18, 19]}
        text = 'spawn | four_gates | otter | 7 | 8\nspawn | four_gates | otter | 8 | 8\n'
        moved, count = P.rewrite_content(text, 'spawns.txt', regions, False)
        self.assertEqual(moved, 'spawn | four_gates | otter | 13 | 14\nspawn | four_gates | otter | 18 | 19\n')
        self.assertEqual(count, {'four_gates': 2})
        self.assertEqual(regions['four_gates']['tilePositions']['8:8'], [18, 19])

    def test_only_declared_obsolete_portal_posts_can_be_removed(self):
        regions = specs()
        regions['four_gates']['removedInteractiveIds'] = ['20']
        regions['four_gates']['contentPositions']['interactives'] = {'20': [18, 19]}
        text = 'four_gates | 20 | 7 | 8 | portal | maps.txt | Old road\n'
        moved, _ = P.rewrite_content(text, 'interactives.txt', regions, False)
        self.assertEqual(moved, '')
        moved, _ = P.rewrite_content(moved, 'interactives.txt', regions, True)
        self.assertEqual(moved, '')
        with self.assertRaisesRegex(ValueError, 'only obsolete generic portal'):
            P.rewrite_content(text.replace('portal | maps.txt', 'storage | shared'), 'interactives.txt', regions, False)

    def test_mistyped_explicit_identity_does_not_silently_fall_back(self):
        regions = specs()
        regions['four_gates']['contentPositions']['npcs'] = {'Bbo': [18, 19]}
        with self.assertRaisesRegex(ValueError, 'identities absent from the source profile'):
            P.rewrite_content('npc | Bob | four_gates | 7 | 8 | dialogue\n', 'npcs.txt', regions, False)

    def test_replacement_keeps_doors_and_unrelated_connections(self):
        text = ('portal | four_gates | 1 | 2 | westhaven | 3 | 4\n'
                'portal | four_gates | 500 | 7 | 8 | room | 2 | 3\n'
                'portal | room | 2 | 3 | four_gates | 6 | 7\n'
                'portal | emberhaven | 1 | 2 | underworld | 3 | 4\n')
        moved, _ = P.replace_crossings(text, connections(), specs())
        self.assertNotIn('four_gates | 1 | 2 | westhaven', moved)
        self.assertIn('four_gates | 500 | 7 | 8 | room', moved)
        self.assertIn('room | 2 | 3 | four_gates | 6 | 7', moved)
        self.assertIn('emberhaven | 1 | 2 | underworld', moved)
        again, _ = P.replace_crossings(moved, connections(), specs())
        self.assertEqual(moved, again)

    def test_collision_rejects_one_blocked_half_metre_sample(self):
        regions = specs()
        blob = struct.pack('<4sHHII', b'EWCG', 2, 0, 48, 48) + bytes([10]) * (48 * 48)
        blobs = {name: blob for name in regions}
        self.assertEqual(P.validate_standing_points(regions, blobs, {}, []), 2)
        damaged = bytearray(blob)
        damaged[16 + 24 * 48 + 25] = 0
        blobs['four_gates'] = damaged
        with self.assertRaisesRegex(ValueError, 'blocked by the authored collision'):
            P.validate_standing_points(regions, blobs, {}, [])

    def fixture(self, root):
        client, server = root / 'client', root / 'server'
        def put(path, value):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value if isinstance(value, bytes) else (value if isinstance(value, str) else json.dumps(value)).encode())
        pub_path = client / 'eloria-assets/maps/nymara-regions/_continent/publication.json'
        master = pub_path.parent / 'continent.glb'
        put(master, b'test-master-bytes')
        publication = {'schema': 1, 'revision': 'diagonal-spine-v1', 'masterPath': 'continent.glb',
                       'masterSha256': P.shared.digest(master.read_bytes()), 'regions': specs(), 'connections': connections()}
        registry = {'maps': {}}
        for name, spec in publication['regions'].items():
            base = client / f'eloria-assets/maps/{name}'
            put(base / 'world.json', {'coordinateTransform': {'serverOrigin': [12, 12], 'serverCells': [24, 24]},
                                     'collision': {'authoredSurfaceExport': True, 'gridAlignment': 'tile-centres-v1'}})
            put(base / 'collision.bin', struct.pack('<4sHHII', b'EWCG', 2, 0, 48, 48) + bytes([10]) * (48 * 48))
            spec.update(worldManifestPath=str(base / 'world.json'), collisionPath=str(base / 'collision.bin'))
            registry['maps'][name] = {'manifest': f'res://../eloria-assets/maps/{name}/world.json'}
        registry['maps']['room'] = {'manifest': 'res://../eloria-assets/maps/room/world.json', 'interiorOf': 'four_gates'}
        put(client / 'eloria-assets/maps/room/world.json', {'arrival': [2, 3], 'exit': {
            'serverTile': [2, 3], 'destinationMap': 'four_gates', 'destinationTile': [7, 8]}})
        put(client / 'godot-client/data/maps/registry.json', registry)
        put(pub_path, publication)
        profile = server / 'config/eloria'
        put(profile / 'client_content_manifest.json', {'maps': [{'id': name, 'arrival': [6, 6], 'server_cells': 12}
            for name in ('four_gates', 'westhaven', 'room')], 'continentGeography': {'regions': {
                name: {'serverOrigin': [6, 6], 'nativeServerOrigin': [6, 6]} for name in specs()}}})
        for filename in P.shared.RULES:
            put(profile / filename, '')
        put(profile / 'npcs.txt', 'npc | Bob | four_gates | 7 | 8 | dialogue | Keep the prose\n')
        put(profile / 'maps.txt', 'map | four_gates | Four Gates | maps/four_gates.elm | FG\n'
            'map | westhaven | Westhaven | maps/westhaven.elm | WH\nmap | room | Room | maps/room.elm | RM\n'
            'portal | room | 2 | 3 | four_gates | 7 | 8\nportal | four_gates | 7 | 9 | room | 2 | 3\n')
        put(server / 'tools/generate_nymara_maps.py', 'FOUR_GATES_TILES_WIDE=2\nMAP_TILES_WIDE_BY_NAME={"four_gates":2,"westhaven":2}\nARRIVAL_TILES={"four_gates":(6,6),"westhaven":(6,6)}\n')
        put(server / 'eloria/map_layout.py', 'FOUR_GATES_ARRIVAL=(6,6)\nCOASTAL_ARRIVALS={"four_gates":FOUR_GATES_ARRIVAL,"westhaven":(6,6)}\nSOUTHERN_ARRIVALS={}\n')
        put(server / 'eloria/world.py', 'TUTORIAL_ROUTE_MARKERS=((7,8),(8,9))\nTUTORIAL_HARVESTS=(("Reed",7,8,9),)\n')
        put(server / 'eloria/walkthrough.py', 'PLAZA=(6,6)\n')
        put(server / 'eloria/daily_quests.py', 'TASKS=(DailyTask("Sage","harvest","Seed",18,"four_gates",7,8,38,220),)\n')
        put(server / 'eloria/pk.py', 'ZONES=(PKZone("four_gates",1,2,5,6,40,True),)\n')
        put(server / 'eloria/database.py', 'class Database:\n    def migrate(self):\n        migration = "coastal_landscapes_396_v1"\n')
        return client, server, pub_path

    def test_plan_is_read_only_and_apply_is_repeatable_preserving_room_local_tiles(self):
        with tempfile.TemporaryDirectory() as folder:
            client, server, publication = self.fixture(Path(folder))
            npc = server / 'config/eloria/npcs.txt'
            original = npc.read_bytes()
            before, pending, report = P.plan(client, server, publication)
            self.assertEqual(npc.read_bytes(), original)
            self.assertEqual(report['exteriorPortalLanes'], 14)
            self.assertIn(b'13 | 14 | dialogue | Keep the prose', pending[npc])
            manifest = json.loads(pending[server / 'config/eloria/client_content_manifest.json'])
            self.assertEqual(manifest['diagonalContinent']['placements']['four_gates']['baselineTilePositions']['7:8'], [13, 14])
            P.shared.apply_plan(before, pending)
            room = P.read_json(client / 'eloria-assets/maps/room/world.json')
            self.assertEqual(room['arrival'], [2, 3])
            self.assertEqual(room['exit']['serverTile'], [2, 3])
            self.assertEqual(room['exit']['destinationTile'], [13, 14])
            before, pending, report = P.plan(client, server, publication)
            self.assertTrue(report['repeatedPublication'])
            self.assertEqual(pending, {})

    def test_changed_publication_requires_explicit_current_source(self):
        with tempfile.TemporaryDirectory() as folder:
            client, server, path = self.fixture(Path(folder))
            before, pending, _ = P.plan(client, server, path)
            P.shared.apply_plan(before, pending)
            data = P.read_json(path)
            data['revision'] = 'diagonal-spine-v2'
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'sourcePublicationSha256'):
                P.plan(client, server, path)


if __name__ == '__main__':
    unittest.main()

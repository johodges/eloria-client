"""Contract placement tests use synthetic ground, never a live server profile."""
import importlib.util
import copy
import json
from pathlib import Path
import sys
import types
import unittest
import tempfile
from unittest import mock
import struct

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import export_contracts as E
import content as C
import landscape as L


class Sources:
    @staticmethod
    def reachable_from(grid, start, limit):
        # Small independent 4-neighbour flood is sufficient for the fixtures.
        result = np.zeros_like(grid, dtype=bool)
        x, y = start
        if not (0 <= x < grid.shape[1] and 0 <= y < grid.shape[0]) or not grid[y, x]:
            return result
        pending = [(x, y)]; result[y, x] = True
        for x, y in pending:
            for nx, ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if 0 <= nx < grid.shape[1] and 0 <= ny < grid.shape[0] and not result[ny,nx] and grid[ny,nx] and abs(int(grid[y,x])-int(grid[ny,nx])) <= limit:
                    result[ny,nx] = True; pending.append((nx,ny))
        return result


def placement(grid=None, preferred=None, hub=None):
    grid = np.ones((30, 30), dtype=np.uint8) if grid is None else grid
    template = {'coordinateTransform': {'serverOrigin': [15, 15]}}
    world = types.SimpleNamespace(regions={'test': {'center': [100, 200]}})
    if hub is not None:world.hub=lambda region:np.asarray(hub,float)
    content = types.SimpleNamespace(templates={'test': template},
        mapped_point=lambda region, point, node=None, landmark=None: np.array(point)+[100, 10, 200])
    spec = {'serverOrigin': [15,15], 'previousServerOrigin': [15,15], 'tilePositions': {},
            'portalPositions': {}, 'arrival': [15,15]}
    report = {'placements': [], 'failures': [], 'regions': {'test': {}}}
    collision = {'heights': np.full((60,60),10,dtype=np.float32)}
    p = E.RegionPlacement(world, content, 'test', spec, collision, grid, Sources, report)
    p.connect_hub([15,15],preferred)
    return p


class ServedProfileTests(unittest.TestCase):
    def test_build_regenerated_invasion_file_is_accepted_only_when_its_own_check_passes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); server = root/'server'; baseline = root/'baseline'
            relative = 'config/eloria/spawn_groups/invasion/invasion_nymara.def'
            for base, text in ((baseline, 'old waves'), (server, 'regenerated waves')):
                (base/relative).parent.mkdir(parents=True); (base/relative).write_text(text)
            (server/'tools').mkdir(); tool = server/'tools/generate_nymara_invasion_spawns.py'
            tool.write_text('import sys; sys.exit(0)')
            certificate = {'files': {relative: 'x'}}; previous = {'regions': {}, 'connections': []}
            shared = types.SimpleNamespace(RULES={}, rewrite_definition=lambda text, mappings: (text, None))
            publisher = types.SimpleNamespace(CONTENT={}, transform_tile=None)
            E.verify_current_profile(server, baseline, certificate, previous, shared, publisher)
            tool.write_text('import sys; sys.exit(1)')
            with self.assertRaisesRegex(ValueError, 'deterministic regeneration'):
                E.verify_current_profile(server, baseline, certificate, previous, shared, publisher)
            # Any other edited authored file is still rejected, even when the regenerator agrees.
            tool.write_text('import sys; sys.exit(0)')
            other = 'config/eloria/spawn_groups/invasion/bosses.def'
            (baseline/other).write_text('a'); (server/other).write_text('b'); certificate['files'][other] = 'y'
            with self.assertRaisesRegex(ValueError, 'beyond the previous coordinated publication'):
                E.verify_current_profile(server, baseline, certificate, previous, shared, publisher)


    def test_a_coordinate_padded_by_an_earlier_publication_is_not_a_content_edit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); server = root/'server'; baseline = root/'baseline'
            relative = 'config/eloria/harvesting.txt'
            (baseline/relative).parent.mkdir(parents=True); (server/relative).parent.mkdir(parents=True)
            (baseline/relative).write_text('node | four_gates | 2506 | 240 | 110 | Sage\n')
            # The tenth publication padded 79 to the width of 110; the eleventh rewrote that text in place.
            (server/relative).write_text('node | four_gates | 2506 | 329 |  115 | Sage\n')
            certificate = {'files': {relative: 'x'}}; previous = {'regions': {}, 'connections': []}
            shared = types.SimpleNamespace(RULES={}, rewrite_definition=lambda text, mappings: (text, None))
            publisher = types.SimpleNamespace(CONTENT={'harvesting.txt': None}, transform_tile=None,
                rewrite_content=lambda text, name, specs, flag: ('node | four_gates | 2506 | 329 | 115 | Sage\n', None))
            E.verify_current_profile(server, baseline, certificate, previous, shared, publisher)
            (server/relative).write_text('node | four_gates | 2506 | 329 |  116 | Sage\n')
            with self.assertRaisesRegex(ValueError, 'beyond the previous coordinated publication'):
                E.verify_current_profile(server, baseline, certificate, previous, shared, publisher)


class StaticBodyTests(unittest.TestCase):
    def test_a_static_body_never_seals_a_pocket_and_withdraws_only_its_own_tile(self):
        grid = np.ones((30, 30), dtype=np.uint8); grid[:, 20] = 0; grid[10, 20] = 1  # one-tile mouth at (20, 10)
        p = placement(grid)
        before = p.reachable.copy(); self.assertTrue(before[15, 25], 'the pocket is hub-connected through its mouth')
        tile = p.place([20, 10], 'npcs.txt:1:Guard', 12, reserve=True, identity='Guard', body=True)
        self.assertEqual(tile, [19, 9])
        self.assertTrue(p.reachable[15, 25], 'the pocket stays connected'); self.assertFalse(p.reachable[9, 19])
        self.assertEqual(int(before.sum()) - int(p.reachable.sum()), 1)
        rejected = [row['rejectedTile'] for row in p.report['regions']['test']['bodyRelocations']]
        self.assertEqual(rejected, [[20, 10], [19, 10], [21, 10]], 'the mouth and both tiles that guard it are rejected in distance order')
        self.assertEqual(p.records[-1]['tile'], [19, 9]); self.assertIn((19, 9), p.bodies)
        # Open ground keeps the exact expected tile and loses exactly that tile.
        p = placement(); before = p.reachable.copy()
        self.assertEqual(p.place([5, 5], 'npcs.txt:2:Reeve', 12, reserve=True, identity='Reeve', body=True), [5, 5])
        self.assertEqual(int(before.sum()) - int(p.reachable.sum()), 1)
        self.assertNotIn('bodyRelocations', p.report['regions']['test'])


class PlacementTests(unittest.TestCase):
    def test_named_actor_relocation_does_not_move_other_content_on_the_old_tile(self):
        p = placement()
        p.content.authored_actor_points = {('test','Quay Master Belen Tarr'): [103.5,19.,201.5]}
        np.testing.assert_array_equal(p.expected([12,17],identity='Quay Master Belen Tarr'),[18,13])
        np.testing.assert_array_equal(p.expected([12,17],identity='Other NPC'),[12,17])
        np.testing.assert_array_equal(p.expected([12,17]),[12,17])

    def test_explicit_relocated_door_and_return_use_exact_semantic_overrides(self):
        p = placement()
        p.content.authored_server_points = {('test', (12, 17)): np.array([103.5, 19., 201.5]),
                                           ('test', (12, 19)): np.array([102.5, 18.9, 202.5])}
        p.entry_by_identity['door'] = {'node': 'FormerDoor'}
        with mock.patch.object(p.content, 'mapped_point', side_effect=AssertionError('stale architectural mapping')):
            np.testing.assert_array_equal(p.expected([12, 17], identity='door'), [18, 13])
            np.testing.assert_array_equal(p.expected([12, 19]), [17, 12])
        # Adjacent coordinates and another region's override remain ordinary.
        p.content.authored_server_points[('neighbour', (13, 17))] = [900, 10, 900]
        np.testing.assert_array_equal(p.expected([13, 17]), [13, 17])

    def test_invalid_authored_semantic_position_is_not_silently_remapped(self):
        p = placement()
        p.content.authored_server_points = {('test', (12, 17)): [float('nan'), 1, 2]}
        with self.assertRaisesRegex(ValueError, 'invalid authored semantic position'):
            p.expected([12, 17])

    def test_parent_and_child_revision_metadata_agree_without_early_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);child_path = root/'chunks/00_01/world.json'
            child_path.parent.mkdir(parents=True)
            child_path.write_text('{"terrainRevision":"old","asset":{"glb":"world.glb"},"coordinateTransform":{"walkingHeight":1.0,"serverOrigin":[2,4]}}')
            original = child_path.read_bytes()
            collision = root/'collision.bin';collision.write_bytes(b'collision')
            manifest = {'terrainRevision': 'old', 'coordinateTransform': {'walkingHeight': 2.5, 'serverOrigin': [2, 4]},
                        'streamingChunks': {'chunks': [{'manifest': 'chunks/00_01/world.json'}]}}
            spec = {'terrainRevision': 'diagonal-spine-v1:'+'a'*64, 'collisionPath': str(collision)}
            children = E.revision_metadata(root/'world.json', manifest, spec, 'b'*64)
            self.assertEqual(child_path.read_bytes(), original)
            self.assertEqual(manifest['terrainRevision'], spec['terrainRevision'])
            self.assertEqual(manifest['streamingChunks']['terrainRevision'], spec['terrainRevision'])
            self.assertEqual(children[0][1]['terrainRevision'], spec['terrainRevision'])
            self.assertEqual(children[0][1]['continentPublication'], manifest['continentPublication'])
            self.assertEqual(children[0][1]['asset']['glb'], 'world.glb')
            # Contracts refine the arrival walking height after export; chunks follow the parent frame exactly.
            self.assertEqual(children[0][1]['coordinateTransform'], manifest['coordinateTransform'])
            self.assertIsNot(children[0][1]['coordinateTransform'], manifest['coordinateTransform'])

    def test_terrain_revision_is_stable_but_tracks_geometry_collision_and_occupancy(self):
        with tempfile.TemporaryDirectory() as folder:
            collision_path = Path(folder)/'collision.bin'
            collision_path.write_bytes(b'original exact collision')
            spec = {'serverOrigin': [15,15], 'serverCells': [30,30], 'translation': [100,0,200],
                    'arrival': [15,15], 'contentPositions': {'npcs': {'Nesh': [16,15]}},
                    'collisionPath': str(collision_path)}
            collision = {'collision': {'sourceGlbSha256': 'a'*64, 'heightEncoding': {'origin': 0, 'step': .2}}}
            grid = np.full((30,30),10,np.uint8)
            original = E.terrain_revision(spec, collision, grid)
            self.assertRegex(original, r'^diagonal-spine-v1:[a-f0-9]{64}$')
            same = dict(reversed(list(spec.items())))
            same.update(previousServerOrigin=[2,3], sourcePublicationSha256='republication', baselineTilePositions={'1:2':[3,4]})
            self.assertEqual(original, E.terrain_revision(same, collision, np.asfortranarray(grid)))
            changed = copy.deepcopy(collision);changed['collision']['sourceGlbSha256'] = 'b'*64
            self.assertNotEqual(original, E.terrain_revision(spec, changed, grid))
            changed = copy.deepcopy(spec);changed['contentPositions']['npcs']['Nesh'] = [17,15]
            self.assertNotEqual(original, E.terrain_revision(changed, collision, grid))
            changed_grid = grid.copy();changed_grid[15,18] = 0
            self.assertNotEqual(original, E.terrain_revision(spec, collision, changed_grid))
            collision_path.write_bytes(b'revised half-cell collision')
            self.assertNotEqual(original, E.terrain_revision(spec, collision, grid))

    def test_arrival_uses_real_main_ground_near_isolated_upper_floor(self):
        grid=np.ones((30,30),np.uint8);grid[14:16,14:16]=25
        p=placement(grid,preferred=grid==1)
        self.assertEqual(int(p.reachable.sum()),896)
        self.assertLess(p.report['regions']['test']['arrivalSelection']['displacementMetres'],2)
        self.assertFalse(p.report['failures'])

    def test_inhabited_hub_uses_unchanged_geographic_server_frame(self):
        grid=np.zeros((30,30),np.uint8);grid[:8,:9]=1;grid[14:16,14:16]=1
        preferred=np.zeros_like(grid,bool);preferred[:8,:9]=True
        p=placement(grid,preferred,hub=[89.5,211.5])
        self.assertEqual(p.spec['arrival'],[4,3])
        self.assertEqual(p.report['regions']['test']['arrivalSelection']['displacementMetres'],0)
        self.assertEqual(int(p.reachable.sum()),72)
        self.assertEqual(p.world.regions['test']['center'],[100,200])
        self.assertEqual(p.spec['serverOrigin'],[15,15])
        np.testing.assert_array_equal(p.expected([15,15]),[15,15])
        self.assertFalse(p.report['failures'])

    def test_inhabited_hub_keeps_twelve_metre_arrival_budget(self):
        grid=np.zeros((30,30),np.uint8);grid[:8,:9]=1
        p=placement(grid,grid!=0,hub=[115,185])
        self.assertFalse(p.reachable.any())
        self.assertEqual(p.report['failures'][0]['maximumDisplacementMetres'],12)
        self.assertIn('within 12 m',p.report['failures'][0]['reason'])

    def test_actual_world_hub_preserves_seed_and_default_for_other_regions(self):
        from world_layout import World
        world=World.__new__(World)
        world.plan={'inhabited_hubs':{'mirrorhold':[773.5,802.5]}}
        world.regions={'mirrorhold':{'center':[840,650]},'other':{'center':[100,200]}}
        np.testing.assert_array_equal(world.hub('mirrorhold'),[773.5,802.5])
        np.testing.assert_array_equal(world.hub('other'),[100,200])
        self.assertEqual(world.regions['mirrorhold']['center'],[840,650])

    def test_fold_requires_each_of_four_actual_subcells(self):
        class Transform:
            def __init__(self, **kwargs): self.__dict__.update(kwargs)
        sources = types.SimpleNamespace(GridTransform=Transform, requantise=lambda g,t:g.astype(np.int32))
        sync = types.SimpleNamespace(choose_stage=lambda g:(1,g!=0,{}),rescale=lambda g,f:g.astype(np.uint8))
        for dy, dx in ((0,0),(0,1),(1,0),(1,1)):
            grid = np.full((8,8),7,dtype=np.uint8)
            grid[2+dy,4+dx] = 0
            result, _, _, _ = E.fold_server_grid({'grid': grid, 'collision': {'heightEncoding': {'origin':0,'step':.2}}},sources,sync)
            self.assertEqual(result[1,2],0)
            self.assertEqual(int((result==0).sum()),1)

    def test_half_cell_coordinates_round_trip(self):
        p=placement()
        np.testing.assert_array_equal(p.expected([8,20]),[8,20])
        self.assertEqual(p.local_position([8,20]),[-6.5,10.,-5.5])

    def test_doors_cannot_jump_to_a_disconnected_island(self):
        grid=np.ones((30,30),dtype=np.uint8);grid[:,19]=0
        p=placement(grid)
        self.assertIsNone(p.place([25,15],'isolated doorway',5))
        self.assertEqual(len(p.report['failures']),1)
        self.assertNotIn('25:15',p.spec['tilePositions'])

    def test_a_nearby_door_is_resolved_once_for_bound_interactive(self):
        p=placement();p.grid[4,4]=0;p.reachable[4,4]=False
        first=p.place([4,4],'door',5,reserve=True)
        second=p.place([4,4],'interactive',12,reserve=True)
        self.assertEqual(first,second)
        self.assertEqual(p.spec['tilePositions']['4:4'],first)
        self.assertFalse(p.report['failures'])

    def test_even_creature_footprint_leans_positive(self):
        p=placement();p.reachable[6,7]=False
        self.assertFalse(p.valid((6,6),(2,1)))
        self.assertTrue(p.valid((5,6),(2,1)))

    def test_storage_body_cannot_cut_the_only_door_route(self):
        grid=np.zeros((30,30),dtype=np.uint8);grid[10:20,2:18]=1;grid[14,18:28]=1
        p=placement(grid)
        p.check_fixed([26,14],'door')
        self.assertFalse(p.report['failures'])
        p.stamp_storage([[21,14]])
        self.assertTrue(any('fixed route' in e['record'] for e in p.report['failures']))
        self.assertFalse(p.reachable[14,26])

    def test_map_records_preserve_interior_local_coordinates(self):
        p=placement();p.reserved[:]=False
        text='portal | test | 4 | 5 | room | 91 | 92\nportal | room | 93 | 94 | test | 6 | 7\nportal | test | 28 | 15 | other | 1 | 15\n'
        other=placement();other.region='other'
        E.place_doors(text,{'test':p,'other':other},[])
        self.assertEqual(set(p.spec['tilePositions']),{'15:15','4:5','6:7'})
        self.assertNotIn('91:92',p.spec['tilePositions'])
        self.assertNotIn('28:15',p.spec['tilePositions'])

    def test_marker_update_keeps_target_room_and_uses_final_floor(self):
        p=placement();p.content.templates['test']['portals']=[{'id':'door','serverTile':[4,5],'targetMap':'room','destinationTile':[91,92]}]
        p.spec['tilePositions']['4:5']=[6,7]
        manifest={'portals':[{'id':'door','serverTile':[4,5],'position':[1,2,3],'targetMap':'room','destinationTile':[91,92]}], 'coordinateTransform': {}}
        E.update_markers(p,manifest)
        self.assertEqual(manifest['portals'][0]['position'],[-8.5,10.,7.5])
        self.assertEqual(manifest['portals'][0]['destinationTile'],[91,92])
        self.assertEqual(manifest['spawnPoints'][0]['serverTile'],p.spec['arrival'])

    def test_reexport_maps_current_tiles_through_original_baseline(self):
        first={'regions':{'test':{'tilePositions':{'4:5':[14,15],'6:7':[16,17]},
            'previousServerOrigin':[15,15],'serverOrigin':[25,25],
            'contentTransform':{'scale':.78,'sourceCenter':[0,0],'targetCenter':[0,0]},
            'removedInteractiveIds':['20'],'portalPositions':{'door':{'oldTile':[4,5],'tile':[14,15]}}}}}
        E.rebase_publication(first,None)
        second={'regions':{'test':{'tilePositions':{'4:5':[24,25],'6:7':[26,27]},
            'previousServerOrigin':[15,15],'serverOrigin':[35,35],
            'contentTransform':{'scale':.78,'sourceCenter':[0,0],'targetCenter':[0,0]},
            'removedInteractiveIds':['20'],'portalPositions':{'door':{'oldTile':[4,5],'tile':[24,25]}}}}}
        E.rebase_publication(second,first)
        spec=second['regions']['test']
        self.assertEqual(spec['tilePositions'],{'14:15':[24,25],'16:17':[26,27]})
        self.assertEqual(spec['baselineTilePositions'],{'4:5':[24,25],'6:7':[26,27]})
        self.assertEqual(spec['previousServerOrigin'],[25,25])
        self.assertEqual(spec['portalPositions']['door']['oldTile'],[14,15])
        self.assertEqual(spec['removedInteractiveIds'],[])
        self.assertEqual(spec['baselineRemovedInteractiveIds'],['20'])

    def test_reexport_rejects_ambiguous_previously_collapsed_points(self):
        prior={'regions':{'test':{'baselineTilePositions':{'4:5':[14,15],'6:7':[14,15]},'serverOrigin':[25,25]}}}
        new={'regions':{'test':{'tilePositions':{'4:5':[24,25],'6:7':[26,27]},
            'previousServerOrigin':[15,15],'serverOrigin':[35,35],
            'contentTransform':{},'removedInteractiveIds':[],'portalPositions':{}}}}
        with self.assertRaisesRegex(ValueError,'collapsed'):
            E.rebase_publication(new,prior)

    def test_a_record_the_baseline_gained_is_rebased_from_its_content_transform_estimate(self):
        # The previous publication never placed 6:7; the reconciled profile serves it at that
        # publication's content transform of the original cell (16,17), where the rewrite finds it.
        prior={'regions':{'test':{'baselineTilePositions':{'4:5':[14,15]},'serverOrigin':[25,25],'baselineServerOrigin':[15,15],
            'baselineContentTransform':{'sourceCenter':[0,0],'targetCenter':[0,0],'scale':1}}}}
        new={'regions':{'test':{'tilePositions':{'4:5':[24,25],'6:7':[26,27]},
            'previousServerOrigin':[15,15],'serverOrigin':[35,35],
            'contentTransform':{},'removedInteractiveIds':[],'portalPositions':{}}}}
        E.rebase_publication(new,prior)
        spec=new['regions']['test']
        self.assertEqual(spec['tilePositions'],{'14:15':[24,25],'16:17':[26,27]})
        self.assertEqual(spec['estimatedSourceTiles'],['6:7'])
        self.assertEqual(spec['baselineTilePositions'],{'4:5':[24,25],'6:7':[26,27]})

    def test_published_server_without_baseline_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'config/eloria/client_content_manifest.json';path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'diagonalContinent':{'publicationSha256':'a'*64}}))
            with self.assertRaisesRegex(ValueError,'already uses diagonal'):
                E.frozen_profile(root,types.SimpleNamespace(RULES={}),root/'baseline')

    def test_snapshot_rejects_original_coordinate_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'config/eloria/client_content_manifest.json';path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'maps':[]}))
            npc=root/'config/eloria/npcs.txt';npc.write_text('npc | Keeper | test | 4 | 5')
            baseline,_,_=E.frozen_profile(root,types.SimpleNamespace(RULES={'npcs.txt':[]}),root/'baseline')
            (baseline/'config/eloria/npcs.txt').write_text('npc | Keeper | test | 99 | 99')
            with self.assertRaisesRegex(ValueError,'Immutable baseline changed'):
                E.frozen_profile(root,types.SimpleNamespace(RULES={'npcs.txt':[]}),root/'baseline')


class ExportTests(unittest.TestCase):
    def test_collision_cache_reuses_only_identical_geometry_and_world_fields(self):
        import collision_export
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);glb=root/'world.glb';glb.write_bytes(b'synthetic geometry')
            for name in ('collision_export.py','world_layout.py','terrain_export.py','landscape.py','crossings.py'):(root/name).write_text('source')
            world=types.SimpleNamespace(ids=['test'],regions={'test':{'center':[0,0]}},connections=[],
                address=lambda r:([2,2],[4,4]),height=np.ones((3,3)),owner=np.zeros((2,2),np.uint8),
                water={'mask':np.zeros((3,3),bool),'surface':np.zeros((3,3))},x0=0,z0=0,x1=4,z1=4)
            manifest={'collision':{'nodeNames':['wall']},'navigation':{'surfaceNodePrefixes':['Walk_']}}
            result={'grid':np.ones((8,8),np.uint8),'heights':np.ones((8,8),np.float32),
                    'walkable':np.ones((8,8),bool),'collision':{'authoredSurfaceExport':True}}
            with mock.patch.object(E,'HERE',root),mock.patch.object(collision_export,'export_collision',return_value=result) as raster:
                E.cached_collision(world,'test',manifest,glb,root/'collision.bin',root,E.collision_world_digest(world))
                reread=E.cached_collision(world,'test',manifest,glb,root/'collision.bin',root,E.collision_world_digest(world))
                self.assertEqual(raster.call_count,1)
                np.testing.assert_array_equal(reread['heights'],result['heights'])
                world.water['mask'][1,1]=True
                E.cached_collision(world,'test',manifest,glb,root/'collision.bin',root,E.collision_world_digest(world))
                self.assertEqual(raster.call_count,2)
                glb.write_bytes(b'changed structural mesh')
                E.cached_collision(world,'test',manifest,glb,root/'collision.bin',root,E.collision_world_digest(world))
                self.assertEqual(raster.call_count,3)
                (root/'terrain_export.py').write_text('changed physical shoreline')
                E.cached_collision(world,'test',manifest,glb,root/'collision.bin',root,E.collision_world_digest(world))
                self.assertEqual(raster.call_count,4)
                world.plan={'sea_level':1.,'rivers':[],'lakes':[]}
                E.cached_collision(world,'test',manifest,glb,root/'collision.bin',root,E.collision_world_digest(world))
                self.assertEqual(raster.call_count,5)

    def fixture(self, root, doorway=False):
        sys.path.insert(0,str(E.TOOLS))
        import publish_continent_geography as shared
        import publish_diagonal_continent as publisher
        profile=root/'config/eloria';profile.mkdir(parents=True)
        for name in shared.RULES:
            (profile/name).write_text('')
        (profile/'creatures.txt').write_text('')
        if doorway:
            (profile/'maps.txt').write_text('portal | test | 25 | 15 | room | 4 | 5\n')
        source={'maps':[{'id':'test','arrival':[15,15]}],
                'continentGeography':{'regions':{'test':{'serverOrigin':[15,15]}}}}
        E.write_json(profile/'client_content_manifest.json',source)
        files={p.relative_to(root).as_posix():E.sha(p) for p in profile.iterdir()}
        baseline=root/'snapshot.json';E.write_json(baseline,{'files':files})
        manifest={'asset':{'glb':'world.glb'},'coordinateTransform':{'serverOrigin':[15,15],'serverCells':[30,30]}}
        package=root/'client/test';package.mkdir(parents=True)
        E.write_json(package/'world.json',manifest)
        output=root/'output';output.mkdir()
        (output/'continent.glb').write_bytes(b'synthetic-master')
        E.write_json(output/'export.json',{'masterPath':str(output/'continent.glb'),'masterSha256':E.sha(output/'continent.glb'),
            'regions':{'test':{'world':str(package/'world.json')}}})
        half=np.ones((60,60),dtype=np.uint8)
        if doorway:half[:,38:40]=0
        (package/'collision.bin').write_bytes(struct.pack('<4sHHII',b'EWCG',2,0,60,60)+half.tobytes())
        # The contracts stage declares crossings from the package's own floors; this one has none.
        sys.path.insert(0,str(HERE.parent/'_toolkit'))
        from amberwood import gltf as G
        G.GltfBuilder().write_glb(str(package/'world.glb'))
        collision={'grid':half,'heights':np.full((60,60),10,np.float32),
                   'collision':{'sourceGlbSha256':'a'*64,'heightEncoding':{'origin':9.8,'step':.2},'gridAlignment':'tile-centres-v1','authoredSurfaceExport':True}}
        world=types.SimpleNamespace(ids=['test'],regions={'test':{'center':[0,0]}},publication_connections=[],
            collision_exports={'test':collision},address=lambda r:([15,15],[30,30]))
        content=types.SimpleNamespace(templates={'test':copy.deepcopy(manifest)},scales={'test':1},source_centers={'test':[0,0]},
            transforms={'test':None},world=world,mapped_point=lambda r,p,node=None,landmark=None:np.array(p,float))
        # The published contentTransform is read off Content's own mapping; here it is the identity.
        content.mapped_xz=lambda region,points:C.Content.mapped_xz(content,region,points)
        class Transform:
            def __init__(self,**kwargs):self.__dict__.update(kwargs)
        sources=types.SimpleNamespace(GridTransform=Transform,requantise=lambda g,t:g.astype(np.int32),reachable_from=Sources.reachable_from)
        sync=types.SimpleNamespace(choose_stage=lambda g:(1,g!=0,{}),rescale=lambda g,f:g.astype(np.uint8),CLIMB_LIMIT=2)
        modules={'collision_sources':sources,'sync_authored_collision':sync,'publish_continent_geography':shared,
                 'publish_diagonal_continent':publisher,'eloria.creatures':types.SimpleNamespace(load_creatures=lambda p:{})}
        patches=[mock.patch.object(E,'HERE',root/'authored'),mock.patch.object(E,'server_modules',return_value=modules),
                 mock.patch.object(E,'frozen_profile',return_value=(root,{'files':files},source)),
                 mock.patch.object(E,'freeze_return_targets',return_value=[])]
        return world,content,{'test':manifest},output,patches

    def test_complete_export_installs_matching_manifest_and_hash_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            world,content,manifests,output,patches=self.fixture(root)
            with patches[0],patches[1],patches[2],patches[3]:
                publication=E.export_contracts(world,content,manifests,output,root)
            self.assertTrue((output/'publication.json').exists())
            spec=publication['regions']['test']
            self.assertRegex(spec['terrainRevision'], r'^diagonal-spine-v1:[a-f0-9]{64}$')
            self.assertEqual(manifests['test']['terrainRevision'], spec['terrainRevision'])
            self.assertEqual(manifests['test']['continentPublication']['terrainRevision'], spec['terrainRevision'])
            self.assertIn('baselineTilePositions',spec)
            self.assertEqual(spec['tileHeights'][E.key(spec['arrival'])],10)
            self.assertEqual(manifests['test']['spawnPoints'][0]['serverTile'],spec['arrival'])
            history=root/'authored/publication-history'/f'{E.sha(output/"publication.json")}.json'
            self.assertEqual(history.read_bytes(),(output/'publication.json').read_bytes())

    def test_disconnected_door_writes_diagnostic_and_no_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            world,content,manifests,output,patches=self.fixture(root,doorway=True)
            before=copy.deepcopy(manifests)
            with patches[0],patches[1],patches[2],patches[3]:
                with self.assertRaises(E.PlacementError):
                    E.export_contracts(world,content,manifests,output,root)
            self.assertFalse((output/'publication.json').exists())
            self.assertEqual(manifests,before)
            report=json.loads((output/'contract-placement-report.json').read_text())
            self.assertFalse(report['ready'])
            self.assertIn('maps.txt',report['failures'][0]['record'])


if __name__=='__main__': unittest.main()

class ServedTileContinuityTests(unittest.TestCase):
    # Tiles away from the hub at (15,15), whose surroundings connect_hub reserves.
    def previous(self, tile, old='5:5'):
        return {'regions': {'test': {'baselineTilePositions': {old: list(tile)}}}}

    def test_a_point_keeps_its_previously_served_tile_within_budget(self):
        p = placement(); p.previous = self.previous([7, 7])
        self.assertEqual(p.place([5, 5], 'spawn', 5), [7, 7])
        self.assertEqual(p.records[-1]['tile'], [7, 7])

    def test_a_blocked_or_distant_served_tile_falls_back_to_the_nearest_standing_point(self):
        grid = np.ones((30, 30), dtype=np.uint8); grid[7, 7] = 0
        p = placement(grid); p.previous = self.previous([7, 7])
        self.assertEqual(p.place([5, 5], 'spawn', 5), [5, 5])
        p = placement(); p.previous = self.previous([20, 5])
        self.assertEqual(p.place([5, 5], 'spawn', 5), [5, 5])

    def test_two_points_that_shared_a_served_tile_keep_sharing_it(self):
        p = placement(); p.previous = {'regions': {'test': {'baselineTilePositions': {'5:5': [7, 7], '6:5': [7, 7]}}}}
        self.assertEqual(p.place([5, 5], 'invasion a', 5), [7, 7])
        self.assertEqual(p.place([6, 5], 'invasion b', 5), [7, 7])

    def test_a_reserved_served_tile_is_not_reused_and_bodies_ignore_continuity(self):
        p = placement(); p.previous = self.previous([7, 7]); p.reserve([7, 7])
        self.assertEqual(p.place([5, 5], 'spawn', 5), [5, 5])
        p = placement(); p.previous = self.previous([7, 7])
        self.assertEqual(p.place([5, 5], 'npc', 5, body=True), [5, 5])

    def test_points_that_lose_their_shared_served_tile_move_together(self):
        p = placement(); p.previous = {'regions': {'test': {'baselineTilePositions': {'5:5': [7, 7], '6:5': [7, 7]}}}}
        p.reserve([7, 7])   # taken this publication by a reserving record
        first = p.place([5, 5], 'invasion a', 5)
        self.assertNotEqual(first, [7, 7])
        p.reserve(first)    # even if something reserves the new tile meanwhile
        self.assertEqual(p.place([6, 5], 'invasion b', 5), first)
class ContentTransformTests(unittest.TestCase):
    """The published source-frame mapping, carried by Content's own mapped_xz."""

    PROBES = [[12., -7.], [-30., 45.], [210., 180.]]
    TURNED = {'translation': [760., 0., 640.], 'about_x': 40., 'about_z': -60.,
              'yaw_degrees': -34., 'squeeze_x': .92, 'squeeze_z': .74}

    def content(self, transform, source_center=(40., -60.), scale=.78, center=(900., 500.)):
        """A stand-in seated exactly as Content.load seats a territory, with Content's own mapped_xz."""
        fake = types.SimpleNamespace(transforms={'test': transform}, source_centers={}, scales={},
            world=types.SimpleNamespace(regions={'test': {'center': list(center)}}))
        fake.mapped_xz = lambda region, points: C.Content.mapped_xz(fake, region, points)
        if transform is None:
            fake.source_centers['test'], fake.scales['test'] = np.asarray(source_center, float), scale
        else:
            fake.source_centers['test'], fake.scales['test'] = C.retained_source_center(transform, center)
        return fake

    def mapped(self, published, points):
        """The published affine read as the contract states it: continent metres from source metres."""
        a, b, c, d, e, f = published['affine']
        points = np.asarray(points, float)
        return np.c_[a * points[:, 0] + b * points[:, 1] + e, c * points[:, 0] + d * points[:, 1] + f]

    def test_a_territory_on_the_centre_and_scale_rule_keeps_its_published_fields(self):
        content = self.content(None)
        published = E.content_transform(content, 'test')
        self.assertEqual(published['scale'], .78)
        self.assertEqual(published['sourceCenter'], [40., -60.])
        self.assertEqual(published['targetCenter'], [0, 0])
        self.assertNotIn('yawDegrees', published)
        self.assertNotIn('squeeze', published)
        np.testing.assert_allclose(published['affine'], [.78, 0., 0., .78, 900. - 40. * .78, 500. + 60. * .78], atol=1e-9)
        np.testing.assert_allclose(self.mapped(published, self.PROBES), content.mapped_xz('test', self.PROBES), atol=1e-7)

    def test_a_rigid_translation_keeps_the_old_fields_and_publishes_an_identity_affine(self):
        transform = [760., 0., 640.]
        published = E.content_transform(self.content(transform), 'test')
        self.assertEqual(published['scale'], 1.)
        np.testing.assert_allclose(published['sourceCenter'], [140., -140.])
        np.testing.assert_allclose(published['affine'], [1., 0., 0., 1., 760., 640.], atol=1e-9)
        self.assertNotIn('yawDegrees', published)
        self.assertNotIn('squeeze', published)
        np.testing.assert_allclose(self.mapped(published, self.PROBES), L.retained_map_xz(transform, self.PROBES), atol=1e-7)

    def test_a_turned_and_squeezed_territory_publishes_the_exact_affine_and_no_scalar(self):
        content = self.content(self.TURNED)
        # The old line asked float() of a two-axis scale, which is the TypeError this replaces.
        with self.assertRaises(TypeError):
            float(content.scales['test'])
        published = E.content_transform(content, 'test')
        self.assertIsNone(published['scale'])
        self.assertEqual(published['yawDegrees'], -34.)
        self.assertEqual(published['squeeze'], [.92, .74])
        self.assertEqual(len(published['sourceCenter']), 2)
        self.assertTrue(all(np.isfinite(published['affine'])))
        np.testing.assert_allclose(self.mapped(published, self.PROBES), L.retained_map_xz(self.TURNED, self.PROBES), atol=1e-7)
        self.assertEqual(json.loads(json.dumps(published)), published)

    def test_a_squeeze_without_a_turn_is_still_no_single_scale(self):
        transform = {'translation': [760., 0., 640.], 'about_z': -60., 'squeeze_z': .74}
        published = E.content_transform(self.content(transform), 'test')
        self.assertIsNone(published['scale'])
        self.assertEqual(published['squeeze'], [1., .74])
        self.assertEqual(published['yawDegrees'], 0.)
        a, b, c, d = published['affine'][:4]
        np.testing.assert_allclose([a, b, c, d], [1., 0., 0., .74], atol=1e-9)
        np.testing.assert_allclose(self.mapped(published, self.PROBES), L.retained_map_xz(transform, self.PROBES), atol=1e-7)

    def test_the_rebase_estimate_of_a_turned_territory_reads_its_published_affine(self):
        # A record the baseline gained after a publication that turned its territory is served where that
        # publication's exact mapping put its original cell: continent metres less the territory's centre.
        published = E.content_transform(self.content(self.TURNED), 'test')
        self.assertIsNone(published['scale'])
        prior = {'serverOrigin': [400, 300], 'baselineServerOrigin': [120, 120], 'translation': [900., 0., 500.],
                 'baselineContentTransform': published}
        for old in ([130, 110], [250, 40], [90, 300]):
            source = [old[0] + .5 - 120, 120 - old[1] - .5]
            x, z = np.asarray(L.retained_map_xz(self.TURNED, [source]), float).reshape(2)
            expected = [int(np.floor(x - 900. + 400)), int(np.floor(300 - (z - 500.)))]
            self.assertEqual(E.estimated_served_tile(f'{old[0]}:{old[1]}', prior), expected)

    def test_a_uniform_squeeze_keeps_the_number_the_old_rule_reads(self):
        transform = {'translation': [760., 0., 640.], 'about_x': 40., 'about_z': -60., 'squeeze_x': .8, 'squeeze_z': .8}
        published = E.content_transform(self.content(transform), 'test')
        self.assertEqual(published['scale'], .8)
        # The old fields and the affine name the same ground: the affine is absolute continent
        # metres, the old rule is relative to the territory's centre.
        source = np.asarray(published['sourceCenter'], float)
        old = (np.asarray(self.PROBES, float) - source) * published['scale'] + [900., 500.]
        np.testing.assert_allclose(old, self.mapped(published, self.PROBES), atol=1e-7)
        np.testing.assert_allclose(old, L.retained_map_xz(transform, self.PROBES), atol=1e-7)

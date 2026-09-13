"""Run with ELORIA_PROOF_SERVER pointing at the paired server checkout.

The production World pathfinder, ELM loader and storage collision participate;
no server process or database is constructed.
"""
import os
import itertools
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest

import generate_continent_walk_proof as P


class ClickFramingTests(unittest.TestCase):
    def test_only_raised_manymouth_to_grey_target_uses_wider_camera(self):
        # Exercise fixture emission only; the full occupied path audit remains
        # a separate required gate and is not replaced by this framing test.
        generator = P.Generator.__new__(P.Generator)
        portal = SimpleNamespace(x=20, y=401, destination_x=403, destination_y=5)
        generator.sorted_lanes = lambda a, b: [portal] * 7
        requests = []
        generator.audit = SimpleNamespace(exact_path=lambda *args, **kwargs:
                                         requests.append((args, kwargs)))
        link = {'id': 'manymouth_delta--grey_moors'}
        many = {'map': 'manymouth_delta', 'frame': {'outward': [-1, 0]}}
        grey = {'map': 'grey_moors', 'frame': {'outward': [1, 0]}}
        route = generator.click_route(link, many, grey, 12)
        identity = 'manymouth_delta--grey_moors-manymouth_delta-click-12'
        self.assertEqual(route, {'id': identity, 'map': 'manymouth_delta',
            'start': [28, 401], 'startTolerance': 0, 'yaw': 90.0, 'distance': 40,
            'walkTimeout': 60, 'steps': [{'tile': [391, 5], 'destination': 'grey_moors',
                'clickNeighbor': True, 'label': 'exact visible resident target',
                'capture': identity}]})
        self.assertEqual(requests, [
            (('manymouth_delta', (28, 401), (20, 401)), {'allowed': [(20, 401)]}),
            (('grey_moors', (403, 5), (391, 5)), {})])
        self.assertEqual(generator.click_route(link, many, grey, 2)['distance'], 32)
        self.assertEqual(generator.click_route(link, grey, many, 12)['distance'], 32)
        self.assertEqual(generator.click_route({'id': 'another-road'}, many, grey, 12)['distance'], 32)


@unittest.skipUnless(os.environ.get('ELORIA_PROOF_SERVER'), 'Set ELORIA_PROOF_SERVER to run paired path regressions')
class PathProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.R=P.runtime(Path(os.environ['ELORIA_PROOF_SERVER']))

    def world(self,width=100,height=100):
        w=self.R['world'].World.__new__(self.R['world'].World)
        w.settings=SimpleNamespace(max_walk_height_change=2,portal_activation_distance=8)
        w.maps={}
        w.collision_maps={name:self.R['collision'].with_step_mask(
            self.R['collision'].CollisionMap(width,height,bytes([10])*(width*height)),2) for name in ('a','b')}
        w.sessions,w.animals,w.animals_by_map=[],{},{}
        w.npcs={};w._footprint_collision={}
        return w

    def portal(self,source,x,y,destination,dx,dy):
        return self.R['maps'].Portal(source,x,y,destination,dx,dy)

    def test_waypoints_avoid_incidental_door_on_real_unmodified_paths(self):
        world=self.world(24,12)
        door=self.portal('a',10,5,'b',3,3)
        audit=P.WalkAudit(world,[door])
        with self.assertRaisesRegex(P.AuditError,'unintended portal'):
            audit.exact_path('a',(2,5),(20,5))
        steps=audit.movement('a',(2,5),(20,5),'public street')
        self.assertGreater(len(steps),1)
        current=(2,5)
        for step in steps:
            target=tuple(step['tile'])
            actual=world.find_path('a',current,target,world.blocking_tiles('a'))
            self.assertEqual(actual[-1],target)
            self.assertNotIn((10,5),actual)
            current=target
        self.assertEqual(current,(20,5))
        self.assertTrue(all(not leg['syntheticBlockers'] for leg in audit.legs))

    def test_long_route_splits_before_server_512_step_limit(self):
        world=self.world(600,12)
        audit=P.WalkAudit(world,[],max_leg=64)
        with self.assertRaisesRegex(P.AuditError,'512-step'):
            audit.exact_path('a',(1,5),(590,5))
        steps=audit.movement('a',(1,5),(590,5),'long road')
        self.assertEqual(steps[-1]['tile'],[590,5])
        self.assertTrue(all(leg['steps']<=64 for leg in audit.legs))
        self.assertTrue(all(step['walkTimeout']>=20 for step in steps))

    def test_direct_request_measures_truncation_without_repairing_it(self):
        world=self.world(600,12)
        method=type(world).find_path
        audit=P.WalkAudit(world,[],max_leg=64)
        result=audit.one_request('a',(1,5),(590,5),'one user click')
        self.assertEqual(result['requestedSteps'],589)
        self.assertEqual(result['returnedSteps'],512)
        self.assertEqual(result['waypointsAdded'],0)
        self.assertTrue(result['diagnosticUncappedMeasurement'])
        self.assertFalse(result['passes'])
        self.assertIs(type(world).find_path,method)
        self.assertEqual(len(world.find_path('a',(1,5),(590,5),set())),512)
        continued=audit.renewed_intent('a',(1,5),(590,5))
        self.assertTrue(continued['passes'])
        self.assertEqual(continued['renewals'],1)
        self.assertEqual(continued['executedSteps'],589)
        self.assertEqual(continued['fixtureWaypoints'],0)
        self.assertTrue(all(s['requestedTarget']==[590,5] for s in continued['segments']))
        self.assertFalse(audit.renewed_intent('a',(1,5),(590,5),maximum_renewals=0)['passes'])

    def test_visual_shore_route_follows_actual_bfs_and_exposes_incidental_door(self):
        world=self.world()
        world.collision_maps['c']=world.collision_maps['a']
        def end(region,x):
            return {'map':region,'position':[x+.5,0,-50.5],
                    'coordinateTransform':{'serverOrigin':[0,0],'invertServerY':True}}
        links=[{'id':'a-b','seamless':True,'ends':[end('a',82),end('b',8)]},
               {'id':'b-c','seamless':True,'ends':[end('b',82),end('c',8)]}]
        portals=[self.portal('a',82,50,'b',10,50),self.portal('b',8,50,'a',80,50),
                 self.portal('b',82,50,'c',10,50),self.portal('c',8,50,'b',80,50),
                 self.portal('b',45,50,'room',3,3)]
        g=P.Generator.__new__(P.Generator)
        g.links,g.portals,g.world=links,portals,world
        g.visual_links=[{'id':'shore-a-c','ends':[{'map':'a'},{'map':'c'}]}]
        g.specs={'a':{},'b':{},'c':{}}
        g.audit=P.WalkAudit(world,portals,max_leg=2)
        g.errors=[]
        routes=g.visual_road_requests()
        self.assertEqual([r['maps'] for r in routes],[['a','b','c'],['c','b','a']])
        self.assertEqual(len(g.audit.requests),2)
        self.assertEqual(len(g.errors),2)
        for item in g.audit.requests:
            self.assertEqual(item['requestedSteps'],72)
            self.assertEqual(item['unintendedPortals'],[[45,50]])
            self.assertEqual(item['waypointsAdded'],0)
            self.assertFalse(item['syntheticBlockers'])
            self.assertFalse(item['passes'])
        self.assertEqual(g.audit.legs,[])  # The fixture waypoint limit is irrelevant here.

    def test_actual_elm_storage_body_and_npc_occupancy_reject_false_standing_points(self):
        world=self.world(12,12)
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'a.elm'
            path.write_bytes(struct.pack('<4sIIII',b'elmf',2,2,0,20)+bytes([10])*144)
            floor=self.R['collision'].load_elm_collision(path)
        world.collision_maps['a']=self.R['collision'].with_storage_collision(floor,[(6,6)])
        npc=SimpleNamespace(x=3,y=3)
        world.npcs={1:(npc,'a',0,())}
        audit=P.WalkAudit(world,[])
        for target in ((5,5),(7,7),(3,3)):
            with self.assertRaisesRegex(P.AuditError,'occupied standing'):
                audit.exact_path('a',(1,1),target)
        target=audit.approach('a',(1,1),(6,6),radius=4)
        self.assertTrue(audit.standing('a',target))
        self.assertLessEqual(max(abs(target[0]-6),abs(target[1]-6)),4)

    def test_inventory_flood_matches_staged_height_and_diagonal_rules(self):
        world=self.world(6,6)
        for masked in (False,True):
            for side in (71,80):
                raw=bytearray(36)
                for x,y,height in ((1,1,70),(2,1,side),(1,2,80),(2,2,70)):
                    raw[y*6+x]=height
                collision=self.R['collision'].CollisionMap(6,6,bytes(raw))
                world.collision_maps['a']=(self.R['collision'].with_step_mask(collision,2) if masked else collision)
                flood=P.AccessFlood(world,'a',(1,1))
                path=world.find_path('a',(1,1),(2,2),set())
                self.assertEqual(flood.reachable((2,2)),bool(path and path[-1]==(2,2)))
                self.assertEqual(flood.reachable((2,2)),side==71)
                if side==71:self.assertEqual(flood.steps[2*6+2],2)  # The diagonal itself cuts a high corner.

    def test_all_content_inventory_reports_islands_and_runtime_approaches_separately(self):
        world=self.world(30,12)
        raw=bytearray(360)
        for x in range(1,29):raw[5*30+x]=10
        world.collision_maps['a']=self.R['collision'].with_step_mask(
            self.R['collision'].CollisionMap(30,12,bytes(raw)),2)
        npc=SimpleNamespace(x=4,y=5,name='Guide')
        world.npcs={1:(npc,'a',0,())}
        # A nearby guide can be spoken to; his body blocks the narrow route.
        g=P.Generator.__new__(P.Generator)
        g.world,g.specs=world,{'a':{'arrival':[1,5]}}
        g.audit=P.WalkAudit(world,[])
        g.interactives={1:SimpleNamespace(map_id='a',object_id=1,role='information',x=3,y=5)}
        g.resources={2:SimpleNamespace(map_id='a',object_id=2,resource='Pearl',x=12,y=5)}
        g.spawns=[SimpleNamespace(map_id='a',creature='crab',x=18,y=5)]
        report=g.content_inventory()
        self.assertFalse(report['allAccessible'])
        self.assertEqual(report['counts'],{'npc':1,'interactive':1,'resource':1,'spawn':1})
        self.assertTrue(report['regions']['a']['entries'][0]['accessible'])
        self.assertTrue(all(i['reason']=='static NPC bodies block the approach' for i in report['issues']))
        world.npcs={}
        g.audit=P.WalkAudit(world,[self.portal('a',7,5,'room',3,3)])
        report=g.content_inventory()
        self.assertTrue(all(i['reason']=='access requires crossing an automatic portal' for i in report['issues']))
        raw[5*30+7]=0
        world.collision_maps['a']=self.R['collision'].with_step_mask(
            self.R['collision'].CollisionMap(30,12,bytes(raw)),2)
        report=g.content_inventory()
        self.assertTrue(all('no primary-arrival geometry connection' in i['reason'] for i in report['issues']))
        self.assertTrue(all(i['nearestReachable']['tile']==[6,5] for i in report['issues']))
        self.assertTrue(all(i['inheritance'].startswith('unverified') for i in report['issues']))

    def test_actual_package_digest_and_lod_metadata_are_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);manifest=root/'world.json'
            data={'asset':{'glb':'world.glb','serverCells':12},'coordinateTransform':{'serverOrigin':[0,0]},
                  'collision':{'binary':'collision.bin'},'runtimePopulation':{'npcs':[]}}
            manifest.write_text(json.dumps(data),encoding='utf-8')
            (root/'world.glb').write_bytes(b'actual main mesh bytes');(root/'collision.bin').write_bytes(b'collision bytes')
            g=P.Generator.__new__(P.Generator)
            g.inputs={};g.members={'a':{'path':manifest,'canonical':'a','owner':'a'}}
            g.registry={'a':{'coordinateTransform':{'serverOrigin':[0,0],'origin':[0,0,0]}}}
            g.world=self.world(12,12);g.portals=[]
            g.manifest={'maps':[{'id':'a','server_cells':12,'portals':[],'packageSha256':P.digest_for(manifest)}]}
            self.assertTrue(g.publication_integrity()['passed'])
            g.inputs={};g.manifest['maps'][0]['packageSha256']='a'*64
            with self.assertRaisesRegex(P.AuditError,'actual package bytes'):g.publication_integrity()
            g.inputs={};g.manifest['maps'][0]['packageSha256']=P.digest_for(manifest)
            (root/'world-lod2.glb').write_bytes(b'LOD mesh bytes')
            lod=dict(data,asset={'glb':'world-lod2.glb','serverCells':12},runtimePopulation={'npcs':[{'id':99}]})
            (root/'world-lod2.json').write_text(json.dumps(lod),encoding='utf-8')
            with self.assertRaisesRegex(P.AuditError,'stale LOD runtimePopulation'):g.publication_integrity()
            g.inputs={};lod['runtimePopulation']=data['runtimePopulation']
            (root/'world-lod2.json').write_text(json.dumps(lod),encoding='utf-8')
            self.assertEqual(g.publication_integrity()['lodManifestsChecked'],1)
            (root/'world.glb').write_bytes(b'changed mesh during audit')
            with self.assertRaisesRegex(P.AuditError,'changed between reads'):g.publication_integrity()

    def test_all24_published_pairs_require_exact_finite_edge_coverage(self):
        g=P.Generator.__new__(P.Generator)
        names=[str(i) for i in range(12)]
        g.specs={n:{'translation':[int(n)*100,0,0],'serverOrigin':[0,0]} for n in names}
        segments=[];links=[]
        for index,pair in enumerate(list(itertools.combinations(names,2))[:24]):
            lines=[[[index*7,0],[index*7,2]],[[index*7,4],[index*7,6]]]
            segments.extend({'regions':list(pair),'start':line[0],'end':line[1]} for line in lines)
            ends=[]
            for name in pair:
                x=g.specs[name]['translation'][0]
                ends.append({'map':name,'coordinateTransform':{'serverOrigin':[0,0]},
                    'frame':{'geometryMode':'continent-owned-v1','anchor':[index*7-x,0,3]},
                    'preloadEdges':[[[p[0]-x,p[1]] for p in line] for line in lines]})
            links.append({'id':'-'.join(pair),'ends':ends,'visualOnly':index>=17})
        g.geography={'boundaryHeightField':{'segments':segments}}
        g.links,g.visual_links=links[:17],links[17:]
        self.assertEqual(g.graph_integrity()['physicalPairs'],24)
        end=g.visual_links[-1]['ends'][0]
        end['preloadEdges']=[[end['preloadEdges'][0][0],end['preloadEdges'][1][1]]]
        with self.assertRaisesRegex(P.AuditError,'finite preload edges differ'):g.graph_integrity()
        with self.assertRaises(P.AuditError):P.finite_span_union([[[0,0],[float('inf'),1]]])

    def test_family_sections_use_actual_incoming_arrivals_and_never_seed_their_exits(self):
        world=self.world(30,12);raw=bytearray(360)
        for x in list(range(2,6))+list(range(20,24)):raw[5*30+x]=10
        world.collision_maps['b']=self.R['collision'].with_step_mask(self.R['collision'].CollisionMap(30,12,bytes(raw)),2)
        portals=[self.portal('a',3,5,'b',2,5),self.portal('b',5,5,'a',4,5),
                 self.portal('a',10,5,'b',20,5),self.portal('b',23,5,'a',11,5)]
        g=P.Generator.__new__(P.Generator)
        g.world,g.members,g.specs=world,{'a':{},'b':{}},{'a':{'arrival':[1,5]}}
        g.manifest={'maps':[{'id':'a','arrival':[1,5]},{'id':'b','arrival':[2,5]}]}
        g.portals=portals;g.audit=P.WalkAudit(world,portals);g.errors=[]
        self.assertTrue(g.family_portal_access()['passed'])
        g.portals=[p for p in portals if not (p.source=='a' and p.x==10)]
        g.audit=P.WalkAudit(world,g.portals);g.errors=[]
        report=g.family_portal_access()
        self.assertFalse(report['passed'])
        self.assertTrue(any(i.get('tile')==[23,5] and 'disconnected' in i['reason'] for i in report['issues']))
        g.portals=portals;world.npcs={1:(SimpleNamespace(x=2,y=5),'b',0,())}
        g.audit=P.WalkAudit(world,portals);g.errors=[]
        report=g.family_portal_access()
        self.assertTrue(any(i.get('tile')==[2,5] and 'arrival' in i['reason'] for i in report['issues']))

    def test_arrival_on_return_portal_can_depart_but_cannot_cross_another_exit(self):
        world=self.world(20,12)
        doors=[self.portal('b',3,5,'a',3,5),self.portal('b',5,5,'a',8,5)]
        audit=P.WalkAudit(world,doors)
        departure=audit.arrival_departure('b',(3,5))
        self.assertIsNotNone(departure)
        self.assertEqual(audit.exact_path('b',(3,5),departure),[departure])
        with self.assertRaisesRegex(P.AuditError,'unintended portal'):
            audit.exact_path('b',(3,5),(8,5))
        flood=P.AccessFlood(world,'b',(3,5),terminals=audit.automatic['b'],arrival_departure=True)
        self.assertTrue(flood.reachable(departure))
        self.assertFalse(flood.reachable((5,5)))
        # Pin the production contract: arrivals do not trigger an automatic
        # exit until a subsequent move has executed a step.
        import inspect
        self.assertNotIn('check_portal(',inspect.getsource(type(world).change_map))
        self.assertIn('await self.check_portal(session)',inspect.getsource(type(world).move))
        world.npcs={1:(SimpleNamespace(x=3,y=5),'b',0,())}
        self.assertIsNone(audit.arrival_departure('b',(3,5)))

    def test_family_does_not_seed_room_from_an_unreachable_incoming_door(self):
        world=self.world(30,12)
        raw=bytearray(world.collision_maps['a'].heights)
        for y in range(12):raw[y*30+15]=0
        world.collision_maps['a']=self.R['collision'].with_step_mask(self.R['collision'].CollisionMap(30,12,bytes(raw)),2)
        portals=[self.portal('a',23,5,'b',3,5),self.portal('b',3,5,'a',23,5)]
        g=P.Generator.__new__(P.Generator)
        g.world,g.members,g.specs=world,{'a':{},'b':{}},{'a':{}}
        g.manifest={'maps':[{'id':'a','arrival':[2,5]},{'id':'b','arrival':[3,5]}]}
        g.portals=portals;g.audit=P.WalkAudit(world,portals);g.errors=[]
        report=g.family_portal_access()
        self.assertFalse(report['passed'])
        self.assertFalse(any(p['map']=='b' for p in report['entryProvenance']))
        self.assertTrue(any(i['map']=='b' and 'disconnected' in i['reason'] for i in report['issues']))

    def test_outbound_family_portal_requires_real_destination_floor_and_departure(self):
        world=self.world(20,12)
        world.maps={'a':SimpleNamespace(file='a.elm'),'b':SimpleNamespace(file='b.elm')}
        g=P.Generator.__new__(P.Generator)
        g.world,g.members,g.specs=world,{'a':{}},{'a':{}}
        g.manifest={'maps':[{'id':'a','arrival':[2,5]}]}
        g.portals=[self.portal('a',10,5,'b',3,5),self.portal('b',5,5,'a',10,5)]
        g.audit=P.WalkAudit(world,g.portals);g.errors=[]
        report=g.family_portal_access()
        self.assertTrue(report['passed'])
        self.assertEqual(report['mapCount'],1)
        self.assertFalse(report['portalChecks'][0]['destinationInServedFamily'])
        self.assertEqual(report['portalChecks'][0]['externalBoundary']['steps'],2)
        world.npcs={1:(SimpleNamespace(x=5,y=5),'b',0,())};g.errors=[]
        self.assertFalse(g.family_portal_access()['passed'])
        world.npcs={};g.audit=P.WalkAudit(world,g.portals)
        world.collision_maps['b']=self.R['collision'].with_storage_collision(world.collision_maps['b'],[(5,5)])
        self.assertFalse(g.family_portal_access()['passed'])
        del world.collision_maps['b'];g.errors=[]
        self.assertFalse(g.family_portal_access()['passed'])

    def test_instance_entry_needs_reachable_keeper_and_waystone_uses_actual_range_contract(self):
        world=self.world(30,12)
        # The decorative return stone is an isolated floor tile. Its valid
        # interaction approach belongs to the genuine instance entry floor.
        raw=bytearray(360)
        for y in range(2,9):
            for x in range(2,9):raw[y*30+x]=10
        raw[5*30+11]=10
        world.collision_maps['b']=self.R['collision'].with_step_mask(self.R['collision'].CollisionMap(30,12,bytes(raw)),2)
        portal=self.portal('b',11,5,'a',3,5)
        g=P.Generator.__new__(P.Generator)
        g.world,g.members,g.specs=world,{'a':{},'b':{}},{'a':{}}
        g.manifest={'maps':[{'id':'a','arrival':[2,5]},{'id':'b','arrival':[3,5]}]}
        g.portals=[portal];g.audit=P.WalkAudit(world,g.portals);g.errors=[]
        g.interactives={('b',None):SimpleNamespace(role='waystone',x=11,y=5)}
        g.instance_entries=[{'definition':'real.def','keeper':'Keeper','source':'a','keeperTile':[5,5],
                             'destination':'b','arrival':[3,5],'exitMap':'a','exitTile':[3,5]}]
        report=g.family_portal_access()
        self.assertTrue(report['passed'])
        self.assertEqual(report['portalChecks'][0]['sourceApproach'],[8,5])
        self.assertTrue(any(e['via']=='reachable instance keeper' for e in report['entryProvenance']))
        g.instance_entries[0]['exitTile']=[4,5];g.errors=[]
        self.assertFalse(g.family_portal_access()['passed'])
        g.instance_entries[0]['exitTile']=[3,5]
        raw=bytearray(world.collision_maps['a'].heights)
        for y in range(12):raw[y*30+10]=0
        world.collision_maps['a']=self.R['collision'].with_step_mask(self.R['collision'].CollisionMap(30,12,bytes(raw)),2)
        g.instance_entries[0]['keeperTile']=[20,5];g.errors=[]
        report=g.family_portal_access()
        self.assertFalse(report['passed'])
        self.assertFalse(any(e['map']=='b' for e in report['entryProvenance']))

    def test_authored_curve_merge_and_lane_cannot_fall_back_to_obstructed_straight_strip(self):
        frame={'id':'a--b','anchor':[81.5,0,-50.5],'outward':[1,0]}
        contract={'schemaVersion':1,'direction':'inland-to-seam','stationHeight':'bed',
                  'laneHalfWidth':3,'physicalHalfWidth':4.25,'commonBoundaryLength':3,'walkingBias':.03,
                  'collarStartIndex':0,'stations':[[36.5,0,-50.5],[45.5,0,-60.5],
                  [65.5,0,-60.5],[76.5,0,-50.5],[81.5,0,-50.5]]}
        package={'streamingBorders':[dict(frame,approachCenterline=contract)]}
        merged=P.Generator.approach_frame(frame,package,'registry-pair-id')
        self.assertNotIn('approachCenterline',frame)
        self.assertEqual(merged['approachCenterline'],contract)
        with self.assertRaisesRegex(P.AuditError,'anchor differs'):
            P.Generator.approach_frame(dict(frame,anchor=[82,0,-50.5]),package,'a--b')
        world=self.world();raw=bytearray(world.collision_maps['a'].heights)
        for x in range(50,62):
            for y in range(46,55):raw[y*100+x]=0
        world.collision_maps['a']=self.R['collision'].with_step_mask(self.R['collision'].CollisionMap(100,100,bytes(raw)),2)
        portals=[]
        for offset in range(-3,4):
            portals.extend([self.portal('a',82,50+offset,'b',10,50+offset),
                            self.portal('b',8,50+offset,'a',80,50+offset)])
        g=P.Generator.__new__(P.Generator)
        g.world,g.portals=world,portals;g.audit=P.WalkAudit(world,portals)
        g.links=[{'id':'a--b','ends':[{'map':'a','frame':merged,'coordinateTransform':{'serverOrigin':[0,0]}},
                                    {'map':'b','frame':{'outward':[-1,0]}}]}]
        g.errors,g.lanes=[],[];g.borders()
        self.assertEqual(g.errors,[])
        self.assertEqual(sum(l['authoredCurve'] for l in g.lanes),7)
        g.links[0]['ends'][0]['frame']=frame;g.errors=[];g.lanes=[];g.borders()
        self.assertTrue(any('blocked receiving strip' in e['error'] for e in g.errors))

    def test_four_service_plan_preserves_three_objects_and_real_tutorial_conversation(self):
        world=self.world(40,16);world.collision_maps['four_gates']=world.collision_maps['a']
        world.npcs={9:(SimpleNamespace(name='Wayfinder Nesh',x=24,y=6),'four_gates',0,())}
        world.npc_roles={9:'tutorial'}
        g=P.Generator.__new__(P.Generator)
        g.world=world;g.specs={'four_gates':{'arrival':[2,6]}}
        g.members={'four_gates':{'path':Path('unused.json')}}
        plan=[{'role':r} for r in ('information','storage','crafting_station')]
        g.json_input=lambda path:{'contentLayout':{'services':plan}}
        g.interactives={i:SimpleNamespace(map_id='four_gates',object_id=i,role=row['role'],x=6+i*5,y=6,text='Actual service')
                        for i,row in enumerate(plan)}
        g.resources={1:SimpleNamespace(map_id='four_gates',object_id=77,resource='Copper',x=30,y=6)}
        g.audit=P.WalkAudit(world,[]);g.coverage={}
        route=g.services('four_gates')
        self.assertEqual([s['useObject'] for s in route['steps'] if 'useObject' in s],[0,1,2])
        conversation=next(s for s in route['steps'] if 'useNpc' in s)
        self.assertEqual(conversation['useNpc'],'Wayfinder Nesh')
        self.assertEqual(conversation['expectDialogueText'],'You already know how to find your feet.')
        self.assertEqual([r['role'] for r in g.coverage['four_gates']['services']],
                         ['information','storage','crafting_station','training'])
        world.npc_roles[9]='dialogue'
        with self.assertRaisesRegex(P.AuditError,'actual Wayfinder Nesh'):g.services('four_gates')
        plan.pop()
        with self.assertRaisesRegex(P.AuditError,'omits a core service'):g.services('four_gates')

    def test_all_seven_reciprocal_lanes_and_distinct_click_targets(self):
        world=self.world()
        portals=[]
        for offset in range(-3,4):
            portals.extend([self.portal('a',82,50+offset,'b',10,50+offset),
                            self.portal('b',8,50+offset,'a',80,50+offset)])
        g=P.Generator.__new__(P.Generator)
        g.world,g.portals=world,portals
        g.audit=P.WalkAudit(world,portals)
        g.links=[{'id':'a--b','ends':[{'map':'a','frame':{'outward':[1,0]}},
                                     {'map':'b','frame':{'outward':[-1,0]}}]}]
        g.errors,g.lanes=[],[]
        centre,shoulders,clicks=g.borders()
        self.assertEqual(g.errors,[])
        self.assertEqual(len(g.lanes),14)
        self.assertEqual((len(centre),len(shoulders),len(clicks)),(1,2,4))
        self.assertEqual([s['destination'] for s in centre[0]['steps'] if 'destination' in s],['b','a'])
        far=[r['steps'][0]['tile'] for r in clicks if r['map']=='a']
        self.assertEqual(far,[[12,50],[22,50]])
        self.assertTrue(all(r['steps'][0]['clickNeighbor'] for r in clicks))

    def test_lane_failure_cannot_be_hidden_by_a_path_detour(self):
        world=self.world()
        portals=[self.portal('a',82,50+i,'b',10,50+i) for i in range(-3,4)]
        portals += [self.portal('b',8,50+i,'a',80,50+i) for i in range(-3,4)]
        raw=bytearray(world.collision_maps['a'].heights);raw[47*100+60]=0
        world.collision_maps['a']=self.R['collision'].CollisionMap(100,100,bytes(raw))
        g=P.Generator.__new__(P.Generator)
        g.world,g.portals=world,portals;g.audit=P.WalkAudit(world,portals)
        g.links=[{'id':'a--b','ends':[{'map':'a','frame':{'outward':[1,0]}},
                                     {'map':'b','frame':{'outward':[-1,0]}}]}]
        g.errors,g.lanes=[],[]
        g.borders()
        self.assertTrue(any('blocked receiving strip' in e['error'] for e in g.errors))


if __name__=='__main__':unittest.main()

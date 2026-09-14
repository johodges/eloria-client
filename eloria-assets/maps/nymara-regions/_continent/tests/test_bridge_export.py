"""Read actual exported deck faces: overlap cannot pass as two good ribbons."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bridge_export as B
import scene_io as S


def world():
    w=SimpleNamespace(x0=0.,z0=0.,x1=48.,z1=40.,ids=['west','east'],plan={},connections=[
        {'id':'west--east','type':'walk','regions':['west','east'],'anchor':[24,20],'normal':[1,0]}])
    w.height_at=lambda x,z:np.where((np.asarray(x)>=18)&(np.asarray(x)<=30),-2.,2.)+np.asarray(z)*0
    w.owner_at=lambda x,z:np.where(np.asarray(x)<24,0,1)+np.asarray(z,dtype=int)*0
    w.roads=[{'id':'out','width':3.,'points':[[4,900,20],[44,-900,20]]},
             {'id':'back','width':3.,'points':[[44,777,20],[4,-777,20]]}]
    return w


def water(x,z,*,height,plan):
    wet=(np.asarray(x)>=18)&(np.asarray(x)<=30)
    return {'mask':wet,'depth':np.where(wet,2.,0.),'surface':np.zeros(np.shape(height))}


class BridgeUnionTests(unittest.TestCase):
    def test_encoded_pier_cap_stays_under_entire_sloping_floor(self):
        x,z=1000.5,1400.5
        positions=np.array([[x-1,0,z-1],[x+1,0,z-1],[x-1,0,z+1],[x+1,0,z+1]])
        positions[:,1]=82.+.44*(positions[:,0]-x)+.44*(positions[:,2]-z)
        faces=positions[[[0,2,1],[1,2,3]]].astype(np.float32).astype(float)
        minimum=B.pier_floor_minimum(faces,x,z)
        self.assertLess(minimum,82.-.3,'The low footprint corner must govern the cap')
        w=SimpleNamespace(height_at=lambda x,z:70.)
        mesh=B.pier_mesh(w,faces,x,z)
        self.assertIsNotNone(mesh)
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'pier.glb';builder=B.G.GltfBuilder()
            builder.add_material(B.G.Material('bridge_stone'))
            builder.add_mesh('pier',mesh,with_tangents=False);builder.add_node(B.G.Node('pier',mesh='pier'))
            builder.write_glb(str(path));doc,body=S.GR.load(path)
            actual=S.GR.triangles(doc,body,[0])
        self.assertLessEqual(float(actual[:,:,1].max()),minimum-.12)
        self.assertGreater(float(actual[:,:,1].max()),81.,'A real visible support must remain')

    def test_pier_minimum_includes_internal_floor_break_and_rejects_partial_support(self):
        p=np.array([[-1.,2.,-1.],[1.,2.,-1.],[1.,2.,1.],[-1.,2.,1.],[0.,1.7,0.]])
        faces=p[[[0,4,1],[1,4,2],[2,4,3],[3,4,0]]].astype(np.float32).astype(float)
        self.assertAlmostEqual(B.pier_floor_minimum(faces,.2,.1),float(np.float32(1.7)),places=6)
        self.assertIsNone(B.pier_floor_minimum(faces,.9,.9),
                          'A pier footprint outside the emitted deck cannot use an invisible extrapolated plane')
        w=SimpleNamespace(height_at=lambda x,z:-2.)
        support,fit=B.fit_pier(w,faces,.9,.9)
        self.assertIsNotNone(support)
        self.assertGreater(fit['shiftMetres'],0)
        self.assertLessEqual(fit['shiftMetres'],1.2)
        self.assertIsNotNone(B.pier_floor_minimum(faces,*fit['position']))
        _,same=B.fit_pier(w,faces,.9,.9)
        self.assertEqual(fit,same,'Edge support fitting must be deterministic')

    def test_opposing_duplicate_roads_export_one_floor_and_identical_thresholds(self):
        w=world();samples=w.height_at(np.arange(48.),20).copy()
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'bridges.glb';parts=B.build_bridges(w,path,water_fields=water)
            doc,body=S.GR.load(path)
            ids=[i for i,n in enumerate(doc['nodes']) if n.get('name','').startswith('Walk_ContinentalBridgeUnion_')]
            triangles=S.GR.triangles(doc,body,ids)
            centres=triangles[:,:,[0,2]].mean(axis=1)
            keys=np.round(centres,6)
            self.assertEqual(len(keys),len(np.unique(keys,axis=0)))
            self.assertEqual(len(triangles),w.bridge_report['visibleTriangles'])
            # The conservative solving grid is wider than the authored road.
            self.assertAlmostEqual(triangles[:,:,2].min(),17.)
            self.assertAlmostEqual(triangles[:,:,2].max(),23.)
            np.testing.assert_allclose(triangles[:,:,1],2.025,atol=1e-7)
            self.assertEqual({p['region'] for p in parts if p['node'].startswith('Walk_ContinentalBridgeUnion_')},{'west','east'})
            for i in ids:
                mesh=S.GR.triangles(doc,body,[i]);x=mesh[:,:,0]
                if doc['nodes'][i]['name'].endswith('_west'):self.assertLessEqual(x.max(),24)
                else:self.assertGreaterEqual(x.min(),24)
            thresholds=[i for i,n in enumerate(doc['nodes']) if n.get('name','').startswith('Walk__StreamThreshold_')]
            for i in thresholds:
                mesh=S.GR.triangles(doc,body,[i])
                np.testing.assert_allclose(mesh[:,:,1],B.surface_at(w,mesh[:,:,0],mesh[:,:,2]),atol=1e-6)
        np.testing.assert_array_equal(samples,w.height_at(np.arange(48.),20))

    def test_diagonal_capsule_has_smooth_exact_width_and_conserved_area(self):
        w=world();a=np.array([8.,8.]);b=np.array([40.,32.]);radius=3.
        w.roads=[{'width':radius,'points':[[*a[:1],0,a[1]],[b[0],0,b[1]]]},
                 {'width':radius,'points':[[b[0],80,b[1]],[a[0],-80,a[1]]]}]
        outline=B.RoadOutline(w)
        component={'slice':(slice(0,40),slice(0,48)),'cells':np.ones((40,48),bool),
                   'height':np.full((41,49),2.025),'outline':outline}
        mesh,owners=B.deck_mesh(w,component);triangles=mesh.positions[mesh.indices.reshape(-1,3)]
        area=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])[:,1]*.5
        cap_area=B.CAP_ARC_STEPS*radius**2*np.sin(np.pi/B.CAP_ARC_STEPS)
        self.assertAlmostEqual(float(area.sum()),2*radius*np.linalg.norm(b-a)+cap_area,places=6)
        self.assertTrue((area>0).all())
        # A diagonal shoulder has fractional coordinates, not a staircase.
        p=mesh.positions[:,[0,2]]
        self.assertGreater(np.count_nonzero((np.abs(p[:,0]-np.round(p[:,0]))>.02)&
                                            (np.abs(p[:,1]-np.round(p[:,1]))>.02)),30)
        for owner in (0,1):
            x=triangles[owners==owner,:,0]
            self.assertTrue((x<=24+1e-9).all() if owner==0 else (x>=24-1e-9).all())

    def test_nonconvex_capsule_union_covers_every_road_point_once(self):
        w=world();w.roads=[{'width':3.,'points':[[6,0,7],[41,0,33]]},
                           {'width':3.,'points':[[7,0,30],[42,0,10]]}]
        outline=B.RoadOutline(w)
        component={'slice':(slice(0,40),slice(0,48)),'cells':np.ones((40,48),bool),
                   'height':np.full((41,49),2.025),'outline':outline}
        mesh,_=B.deck_mesh(w,component);triangles=mesh.positions[mesh.indices.reshape(-1,3)][:,:,[0,2]]
        points=np.random.default_rng(129).uniform([0,0],[48,40],(2500,2));coverage=np.zeros(len(points),int)
        for triangle in triangles:
            a,b,c=triangle
            edge1=b-a;edge2=c-a;delta=points-a
            determinant=edge1[0]*edge2[1]-edge1[1]*edge2[0]
            u=(delta[:,0]*edge2[1]-delta[:,1]*edge2[0])/determinant
            v=(edge1[0]*delta[:,1]-edge1[1]*delta[:,0])/determinant
            coverage+=(u>=0)&(v>=0)&(u+v<=1)
        self.assertLessEqual(int(coverage.max()),1,'Overlapping source ribbons survived the union')
        np.testing.assert_array_equal(coverage==1,outline.contains(points[:,0],points[:,1]))
        # Independently check actual authored capsule widths away from cap approximation.
        distance=np.full(len(points),np.inf)
        for road in w.roads:
            a,b=np.asarray(road['points'])[:,[0,2]];delta=b-a
            t=np.clip(np.sum((points-a)*delta,axis=1)/np.dot(delta,delta),0,1)
            distance=np.minimum(distance,np.linalg.norm(points-a-t[:,None]*delta,axis=1))
        self.assertTrue((coverage[distance<2.97]==1).all())
        self.assertTrue((coverage[distance>3.001]==0).all())

    def test_visible_timber_edges_stay_below_floor_and_out_of_bank_joins(self):
        w=world()
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'bridges.glb';B.build_bridges(w,path,water_fields=water)
            doc,body=S.GR.load(path)
            timber=[i for i,n in enumerate(doc['nodes']) if n.get('name','').startswith('BridgeUnionTimberEdge_')]
            self.assertTrue(timber)
            triangles=S.GR.triangles(doc,body,timber)
            self.assertAlmostEqual(triangles[:,:,1].max(),2.025,places=6)
            self.assertAlmostEqual(triangles[:,:,1].min(),2.025-.32,places=6)
            self.assertTrue(np.isin(triangles[:,:,2],[17.,23.]).all())
            materials={m['name']:m for m in doc['materials']}
            self.assertIn('baseColorTexture',materials['bridge_timber']['pbrMetallicRoughness'])
            self.assertTrue(doc['images'][0].get('bufferView') is not None)
        # Grid-only cells outside the clipped shoulder cannot report an invisible elevated floor.
        self.assertAlmostEqual(float(B.surface_at(w,24,23.5)),-2.)

    def test_nearly_coincident_caps_export_stable_float32_faces_at_continent_scale(self):
        w=world();w.x0=1000.;w.z0=1300.;w.x1=1048.;w.z1=1340.
        w.owner_at=lambda x,z:np.where(np.asarray(x)<1024,0,1)+np.asarray(z,dtype=int)*0
        w.roads=[{'width':3.,'points':[[1006,0,1307],[1041,0,1333]]},
                 {'width':3.00000005,'points':[[1006.000003,0,1307.000004],[1041,0,1333]]}]
        gx,gz=np.meshgrid(np.arange(49),np.arange(41))
        component={'slice':(slice(0,40),slice(0,48)),'cells':np.ones((40,48),bool),
                   'height':80.+.44*gx+.44*gz,'outline':B.RoadOutline(w)}
        mesh,_=B.deck_mesh(w,component)
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'floor.glb';builder=B.G.GltfBuilder()
            builder.add_material(B.G.Material('bridge_timber'))
            builder.add_mesh('floor',mesh,with_tangents=False);builder.add_node(B.G.Node('floor',mesh='floor'))
            builder.write_glb(str(path));doc,body=S.GR.load(path)
            triangles=S.GR.triangles(doc,body,[0])
        normal=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
        self.assertTrue((normal[:,1]>0).all())
        self.assertLessEqual(float(np.max(np.hypot(normal[:,0],normal[:,2])/normal[:,1])),.65)
        self.assertLess(component['precisionCleanupArea'],.001)

    def test_thin_continent_edge_uses_encoded_xz_before_lifting_onto_floor(self):
        # Regression from the fifth export: a ~2.44 cm² shoulder face is large
        # enough to retain, but independent XYZ rounding makes its grade .659.
        w=world();w.x0=329.;w.z0=1428.
        gradient=.64/np.sqrt(2)
        component={'slice':(slice(0,1),slice(0,1)),'cells':np.ones((1,1),bool),
                   'height':np.array([[1.8-gradient,1.8],[1.8,1.8+gradient]])}
        xz=np.array([[329.,1429.],[330.,1429.],[329.001,1428.99949]])
        original=np.c_[xz[:,0],1.8+(xz-[329.,1429.])@np.array([gradient,gradient]),xz[:,1]]
        independent=original.astype(np.float32).astype(float)
        normal=np.cross(independent[1]-independent[0],independent[2]-independent[0])
        self.assertGreater(np.hypot(normal[0],normal[2])/normal[1],.65)
        self.assertGreater(normal[1]*.5,1e-4,'Regression must not qualify for tiny-face deletion')
        positions=B.encoded_floor_vertices(w,component,xz)
        mesh=B.M.Mesh(positions=positions,normals=np.tile([0.,1.,0.],(3,1)),
                      uvs=positions[:,[0,2]],indices=np.array([0,1,2]),material='bridge_timber')
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'floor.glb';builder=B.G.GltfBuilder()
            builder.add_material(B.G.Material('bridge_timber'))
            builder.add_mesh('floor',mesh,with_tangents=False);builder.add_node(B.G.Node('floor',mesh='floor'))
            builder.write_glb(str(path));doc,body=S.GR.load(path)
            triangles=S.GR.triangles(doc,body,[0])
        self.assertEqual(len(triangles),1,'The thin floor must remain present')
        normal=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])[0]
        self.assertGreater(normal[1],0)
        self.assertLessEqual(np.hypot(normal[0],normal[2])/normal[1],.65)
        expected=1.8+(positions[:,[0,2]]-[329.,1429.])@np.array([gradient,gradient])
        np.testing.assert_allclose(positions[:,1],expected,atol=1e-7)

    def test_conservative_invisible_shoulder_cannot_create_a_bridge_beside_water(self):
        w=world();w.height_at=lambda x,z:np.where(np.asarray(z)>=23.5,-2.,2.)+np.asarray(x)*0
        def beside(x,z,*,height,plan):
            mask=np.asarray(z)>=23.5
            return {'mask':mask,'depth':np.where(mask,2.,0.),'surface':np.asarray(height)*0}
        field=B.common_surface(w,water_fields=beside)
        self.assertEqual(field['components'],[])
        self.assertFalse(field['mask'].any())

    def test_readback_outline_vertices_use_the_visible_floor_after_float32_rounding(self):
        w=world();w.x0=1000.;w.z0=1300.;w.x1=1048.;w.z1=1340.;w.connections=[]
        w.owner_at=lambda x,z:np.where(np.asarray(x)<1024,0,1)+np.asarray(z,dtype=int)*0
        w.height_at=lambda x,z:np.where((np.asarray(x)>=1018)&(np.asarray(x)<=1030),-20.,2.)+np.asarray(z)*0
        w.roads=[{'width':3.,'points':[[1004,0,1304],[1044,0,1336]]}]
        def river(x,z,*,height,plan):
            mask=(np.asarray(x)>=1018)&(np.asarray(x)<=1030)
            return {'mask':mask,'depth':np.where(mask,20.,0.),'surface':np.asarray(height)*0}
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'bridges.glb';B.build_bridges(w,path,water_fields=river)
            doc,body=S.GR.load(path)
            ids=[i for i,n in enumerate(doc['nodes']) if n.get('name','').startswith('Walk_ContinentalBridgeUnion_')]
            vertices=S.GR.triangles(doc,body,ids).reshape(-1,3)
        np.testing.assert_allclose(B.surface_at(w,vertices[:,0],vertices[:,2]),vertices[:,1],atol=1e-5)

    def test_road_order_and_artificial_old_profiles_do_not_change_the_deck(self):
        first=world();second=world();second.roads.reverse()
        for r in second.roads:
            for p in r['points']:p[1]*=-100
        a=B.common_surface(first,water_fields=water);b=B.common_surface(second,water_fields=water)
        np.testing.assert_array_equal(a['mask'],b['mask'])
        np.testing.assert_allclose(a['height'],b['height'],equal_nan=True)

    def test_crossing_roads_share_one_junction_with_bounded_actual_triangle_slopes(self):
        w=world();w.roads.append({'id':'north-south','width':3.,'points':[[24,0,4],[24,0,36]]})
        # A cross-channel has real dry banks on all approaches.
        w.height_at=lambda x,z:np.where((np.abs(np.asarray(x)-24)<5)&(np.abs(np.asarray(z)-20)<5),-2.,2.)+np.asarray(z)*.02
        def wet(x,z,*,height,plan):
            mask=(np.abs(np.asarray(x)-24)<5)&(np.abs(np.asarray(z)-20)<5)
            return {'mask':mask,'depth':np.where(mask,2.,0.),'surface':np.asarray(height)*0}
        field=B.common_surface(w,water_fields=wet)
        self.assertEqual(len(field['components']),1)
        mesh,_=B.deck_mesh(w,field['components'][0]);t=mesh.positions[mesh.indices.reshape(-1,3)]
        normal=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0])
        self.assertTrue((normal[:,1]>0).all())
        self.assertLessEqual(float(np.max(np.hypot(normal[:,0],normal[:,2])/normal[:,1])),.650001)
        self.assertLessEqual(field['maximumBankError'],.12)

    def test_supports_extend_down_to_the_actual_bed(self):
        w=world()
        with tempfile.TemporaryDirectory() as temporary:
            parts=B.build_bridges(w,Path(temporary)/'bridges.glb',water_fields=water)
            piers=[p for p in parts if p['node'].startswith('BridgeUnionPier_')]
            self.assertTrue(piers)
            for p in piers:
                low,high=p['bounds'];x,z=((low+high)*.5)[[0,2]]
                self.assertAlmostEqual(low[1],float(w.height_at(x,z))-.06,places=6)
                self.assertAlmostEqual(high[1],float(B.surface_at(w,x,z))-.12,places=6)

    def test_unfittable_banks_fail_without_mutating_the_world(self):
        w=world();w.height_at=lambda x,z:np.where(np.asarray(x)>24,80.,-2.)+np.asarray(z)*0
        before=w.height_at(np.arange(48.),20).copy()
        with self.assertRaisesRegex(ValueError,'cannot fit|actual dry bank'):
            B.common_surface(w,water_fields=water,maximum_extension=0)
        np.testing.assert_array_equal(before,w.height_at(np.arange(48.),20))


if __name__=='__main__':unittest.main()

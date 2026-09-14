"""A connected compound must retain actual spacing, grade and quiet water."""
import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import assemblies as A


def ground(x,z):
    x,z=np.broadcast_arrays(np.asarray(x,float),np.asarray(z,float))
    return 31.+x*.01+z*.02


class AssembliesTests(unittest.TestCase):
    def test_compressed_anchor_does_not_compress_full_size_components(self):
        p=[{'node':'Plaza_Monument','kind':'landmark','position':[0,31,0]},
           {'node':'Plaza_Fountain_0','kind':'prop','position':[25,31,25]}]
        b={'Plaza_Monument':([-10,31,-10],[10,91,10]),'Plaza_Fountain_0':([23,31,23],[27,34,27])}
        a=A.build_assemblies('four_gates',p,b,ground)['four_gates.civic']
        shift=a.shift_to(lambda q:q*.78+[530,840],lambda x,z:20.)
        actual=np.array([row['position'] for row in p])+shift
        np.testing.assert_allclose(actual[1]-actual[0],[25,0,25])
        self.assertEqual(actual[0,1],20.)
        self.assertEqual(a.reference_y,31.)

    def test_arcade_quarters_and_small_street_details_share_the_civic_group(self):
        for name,kind in [('Plaza_Arcade_0','landmark'),('Plaza_Monument_Crystal','landmark'),
                          ('Goods_four-gates-reedworks','small_dressing'),('City_Wall_02','wall')]:
            self.assertEqual(A.placement_group('four_gates',{'node':name,'kind':kind}), 'four_gates.civic')
        self.assertIsNone(A.placement_group('four_gates',{'node':'Tree_plaza_1','kind':'tree'}))

    def test_water_city_uses_one_sea_datum_and_does_not_fill_spans(self):
        p=[{'node':'Landmark_Pavilion_pavilion_west','kind':'landmark'},
           {'node':'Causeway_ring_west_east','kind':'landmark'},
           {'node':'Landmark_Cathedral','kind':'landmark'}]
        b={p[0]['node']:([0,4,0],[4,10,4]),p[1]['node']:([4,-8,0],[96,5,4]),p[2]['node']:([96,14,0],[100,50,4])}
        a=A.build_assemblies('crownwater',p,b,ground)['crownwater.causeway-city']
        shift=a.shift_to(lambda q:q+[300,1200],lambda x,z:120.,water_level=0.)
        self.assertEqual(shift[1],0.)
        target,weight=a.sample_foundation([302,350,398],[1202]*3,shift,ground)
        np.testing.assert_allclose(weight,[1,0,1])
        self.assertEqual(a.reference_y,0.)
        self.assertEqual(len(a.footprints),2)

    def test_baked_zero_origin_porches_follow_their_house_and_actual_bounds(self):
        p=[{'node':'town_house_00','kind':'building','position':[38,2.2,-25]},
           {'node':'town_porch_00','kind':'structure','position':[0,0,0]}]
        b={p[0]['node']:([35,-1,-28],[41,8,-22]),p[1]['node']:([33,2.15,-29],[38,2.25,-24])}
        a=A.build_assemblies('manymouth_delta',p,b,ground)['manymouth_delta.boardwalk-town']
        np.testing.assert_allclose(a.bounds,[[33,-1,-29],[41,8,-22]])
        self.assertEqual(set(a.nodes),{'town_house_00','town_porch_00'})
        self.assertNotEqual(A.placement_group('manymouth_delta',{'node':'east_hamlet_porch_00'}),a.id)

    def test_fortress_roof_height_is_never_used_as_the_ground_datum(self):
        p=[{'node':'Landmark_Orrery','kind':'landmark','position':[99.7,134.35,-216.6]},
           {'node':'Landmark_CitadelCourt','kind':'landmark','position':[99.7,98,-138.6]}]
        b={p[0]['node']:([90,124,-225],[110,150,-205]),p[1]['node']:([60,97,-170],[140,120,-105])}
        a=A.build_assemblies('mirrorhold',p,b,lambda x,z:98.)['mirrorhold.city']
        shift=a.shift_to(lambda q:q+[740,790],lambda x,z:70.)
        self.assertEqual(shift[1],-28.)
        self.assertEqual(np.diff(np.array([134.35,98])+shift[1])[0],98-134.35)

    def test_regrounding_preserves_existing_mapping_references_and_fails_on_tearing(self):
        objects=[{'shift':np.array([20.,-10,50]),'low':np.zeros(3),'high':np.ones(3),'targetGround':20.} for _ in range(2)]
        mapped=objects[0]['shift'];bounds=objects[0]['low']
        A.apply_group_delta(objects,[0,2,0]);A.assert_rigid(objects)
        np.testing.assert_allclose(mapped,[20,-8,50]);np.testing.assert_allclose(bounds,[0,2,0])
        objects[1]['shift'][1]+=.01
        with self.assertRaisesRegex(ValueError,'independent component'):A.assert_rigid(objects)

    def test_local_foundation_retains_grade_and_leaves_distant_wilderness_untouched(self):
        p=[{'node':'Building_CliffHouse_0','kind':'building'}];b={p[0]['node']:([0,0,0],[8,10,8])}
        a=A.build_assemblies('mirrorhold',p,b,ground)['mirrorhold.city']
        shift=np.array([100.,5,200.])
        y,w=a.sample_foundation([102,106,200],[202,206,300],shift,ground)
        self.assertAlmostEqual(y[1]-y[0],.12)
        np.testing.assert_allclose(w,[1,1,0])

    def test_fortress_harbour_and_cliff_streets_cannot_drift_into_one_another(self):
        members=['Landmark_Orrery','Landmark_Quay','Building_CliffHouse_10','Landmark_Retaining_1','Prop_Signpost_0']
        self.assertEqual({A.placement_group('mirrorhold',{'node':name,'kind':'landmark'}) for name in members},{'mirrorhold.city'})

    def test_canopy_village_keeps_support_trees_without_crown_sized_ground_pads(self):
        for kind,suffix in (('tree','Wood'),('foliage','Canopy')):
            p={'node':'Landmark_Giant_3_'+suffix,'kind':kind}
            self.assertEqual(A.placement_group('amberwood',p),'amberwood.canopy-village')
            self.assertFalse(A.supports_ground(p))
        for name in ('Landmark_CanopyPlatform_4','Landmark_CanopyWalkway_3'):
            self.assertFalse(A.supports_ground({'node':name,'kind':'landmark'}))

    def test_city_streets_share_the_building_support_without_exporting_a_rectangle(self):
        p=[{'node':'Building_CliffHouse_'+str(i),'kind':'building'} for i in range(3)]
        b={p[0]['node']:([0,0,0],[8,10,8]),p[1]['node']:([100,0,0],[108,10,8]),
           p[2]['node']:([0,0,100],[8,10,108])}
        a=A.build_assemblies('mirrorhold',p,b,ground)['mirrorhold.city']
        y,w=a.sample_foundation([30,110,250],[30,110,250],np.zeros(3),ground,feather=30.)
        self.assertEqual(w[0],1.,'The empty street between houses needs continuous support')
        self.assertEqual(w[1],0.,'The uninhabited corner of the bounding rectangle is not imported')
        self.assertEqual(w[2],0.)
        self.assertAlmostEqual(y[0],31.9)

    def test_ruin_courts_gate_and_culvert_keep_the_original_temple_spacing(self):
        names=('Temple_Ssarathi','Temple_VaultPortal','Colonnade_ritual_plaza',
               'Colonnade_lily_court','Secret_ruins_culvert_mouth','WaterGate','SerpentColumn_0_1')
        self.assertEqual({A.placement_group('ssarathi_ruins',{'node':name,'kind':'landmark'}) for name in names},
                         {'ssarathi_ruins.ruin-city'})
        self.assertIsNone(A.placement_group('ssarathi_ruins',{'node':'Jungle_0','kind':'tree'}))
        self.assertEqual(A.placement_group('ssarathi_ruins',{'node':'Secret_ruins_temple_focus','kind':'prop'}),
                         'ssarathi_ruins.temple-focus')

    def test_steppe_encampment_preserves_the_lane_between_pavilion_and_hall(self):
        names=('Structure_Palisade','Encampment_Pavilion_00','Encampment_Cart_00',
               'Landmark_sunmane_great_hall','Landmark_sunmane_secret_steppe-hall-vault')
        self.assertEqual({A.placement_group('sunmane_steppe',{'node':n,'kind':'prop'}) for n in names},
                         {'sunmane_steppe.encampment'})
        self.assertIsNone(A.placement_group('sunmane_steppe',{'node':'Landmark_orun_banner_shrine_00','kind':'landmark'}))

    def test_city_apron_does_not_import_the_old_mountain_beyond_actual_support(self):
        p=[{'node':'Building_CliffHouse_'+str(i),'kind':'building'} for i in range(2)]
        b={p[0]['node']:([0,0,0],[8,10,8]),p[1]['node']:([20,0,0],[28,10,8])}
        a=A.build_assemblies('mirrorhold',p,b,ground)['mirrorhold.city']
        # The old mountain outside the western city edge is much higher than
        # the city. Its slope must not become an unrelated exterior mound.
        survey=lambda x,z:50.+np.maximum(-np.asarray(x),0.)*3.
        x=np.array([-50.,-33.5,-17.5,-1.5,10.,20.])
        y,w=a.sample_foundation(x,np.full_like(x,4),np.zeros(3),survey,feather=32.)
        np.testing.assert_allclose(y[:4],54.5)
        np.testing.assert_allclose(w,[0,0,.5,1,1,1])
        self.assertEqual(y[4],50.,'The shared street keeps its actual source survey')

    def test_city_apron_uses_euclidean_corner_distance_and_a_smooth_boundary(self):
        p=[{'node':'Building_CliffHouse_'+str(i),'kind':'building'} for i in range(2)]
        b={p[0]['node']:([0,0,0],[8,10,8]),p[1]['node']:([20,0,0],[28,10,8])}
        a=A.build_assemblies('mirrorhold',p,b,ground)['mirrorhold.city']
        _,w=a.sample_foundation([-25.5,-1.5,-1.5001],[33.5,4,4],np.zeros(3),ground,feather=32.)
        self.assertEqual(w[0],0.,'A square 24m corner offset is more than32m from the actual city')
        self.assertEqual(w[1],1.)
        self.assertLess(abs(w[2]-w[1]),1e-9)


if __name__=='__main__':unittest.main()

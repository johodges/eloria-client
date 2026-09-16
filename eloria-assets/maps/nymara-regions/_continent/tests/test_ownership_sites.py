"""Extra ownership sites: a territory owns the ground nearest any of them, not only its centre."""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import landscape as L
import world_layout as W

# The smallest plan World can be built from: two territories on 40 by 40 metres of
# inland ground, no ridges, islands, rivers or lakes, and a coastline far offshore.
PLAN={'name':'ownership probe','seed':7,'sea_level':0.,'bounds':[0,0,40,40],
    'coastline':[[-400,-400],[440,-400],[440,440],[-400,440]],
    'ridges':[],'islands':[],'rivers':[],'lakes':[],
    'regions':[{'id':'west','center':[10,20]},{'id':'east','center':[30,20]}]}
TAIL=[30.,36.]   # A second Westhaven-style site in the far corner of its neighbour.


class OwnershipSiteTests(unittest.TestCase):
    def world(self,**extra):
        return W.World(dict(PLAN,**extra))

    def cell_centres(self,world):
        return np.meshgrid(world.x[:-1]+W.CELL*.5,world.z[:-1]+W.CELL*.5)

    def test_a_second_site_takes_the_ground_nearest_it_and_no_other_ground(self):
        plain=self.world();world=self.world(ownership_sites={'west':[TAIL]})
        west,east=world.ids.index('west'),world.ids.index('east')
        cx,cz=self.cell_centres(world)
        # Two regions, so each cell falls to whichever site is nearest; the scoring loop
        # leaves a tie with the earlier region, which is how the plain world is scored too.
        to_centre=(cx-10)**2+(cz-20)**2;to_tail=(cx-TAIL[0])**2+(cz-TAIL[1])**2
        to_east=(cx-30)**2+(cz-20)**2
        np.testing.assert_array_equal(plain.owner,np.where(to_east<to_centre,east,west))
        np.testing.assert_array_equal(world.owner,np.where(to_east<np.minimum(to_centre,to_tail),east,west))
        changed=world.owner!=plain.owner
        self.assertTrue(changed.any())
        # Everything that changed hands went to the region that declared the site, and only
        # where that site is nearer than the centre that held the ground before.
        self.assertEqual(set(world.owner[changed].tolist()),{west})
        self.assertTrue((to_tail<to_east)[changed].all())
        self.assertFalse(changed[to_tail>=to_east].any())
        # Ground nearest either centre is untouched, including the far side of the site.
        for x,z in ((5.,5.),(15.,35.),(31.,5.),(39.,19.),(19.,29.)):
            self.assertEqual(int(world.owner_at(x,z)),int(plain.owner_at(x,z)))

    def test_owner_at_agrees_with_the_grid_over_the_new_ground(self):
        plain=self.world();world=self.world(ownership_sites={'west':[TAIL]})
        west,east=world.ids.index('west'),world.ids.index('east')
        for x,z in ((31.,35.),(39.,39.),(21.,29.),(31.,27.),(25.,15.),(1.,1.)):
            self.assertEqual(int(world.owner_at(x,z)),int(world.owner[int(z/W.CELL),int(x/W.CELL)]),(x,z))
        self.assertEqual(int(world.owner_at(*TAIL)),west)
        self.assertEqual(int(plain.owner_at(*TAIL)),east)
        # Outside the world nobody owns anything, sites or no sites.
        self.assertEqual(int(world.owner_at(-1.,20.)),-1)

    def test_the_tail_is_part_of_the_regions_polygon_and_its_address(self):
        plain=self.world();world=self.world(ownership_sites={'west':[TAIL]})
        polygon=np.array(world.polygons['west'])
        self.assertTrue(bool(L._polygon_inside(np.array(TAIL[0]),np.array(TAIL[1]),polygon)))
        self.assertFalse(bool(L._polygon_inside(np.array(TAIL[0]),np.array(TAIL[1]),np.array(plain.polygons['west']))))
        # The traced boundary now reaches the eastern world edge; the plain one stops at 20 m.
        np.testing.assert_allclose(world.bounds('west')[1],[40.,40.])
        np.testing.assert_allclose(plain.bounds('west')[1],[20.,40.])
        np.testing.assert_allclose(world.bounds('east')[1],[40.,28.])
        # Its map address still covers the whole territory, tail included.
        origin,cells=world.address('west');centre=world.centers[world.ids.index('west')]
        low,high=world.bounds('west')
        self.assertTrue(origin[0]>=centre[0]-low[0] and cells[0]>=high[0]-low[0])

    def test_a_site_must_name_a_region_of_this_plan_and_stand_inside_its_bounds(self):
        with self.assertRaisesRegex(ValueError,"no region 'north'"):
            self.world(ownership_sites={'north':[[10.,10.]]})
        with self.assertRaisesRegex(ValueError,'outside the plan bounds'):
            self.world(ownership_sites={'west':[TAIL,[41.,10.]]})
        # The constructor reads exactly this helper; a plan with no sites declares none.
        self.assertEqual(W.ownership_sites(PLAN,['west','east']),{})
        np.testing.assert_allclose(W.ownership_sites(dict(PLAN,ownership_sites={'east':[TAIL]}),
            ['west','east'])['east'],[TAIL])


if __name__=='__main__':
    unittest.main()

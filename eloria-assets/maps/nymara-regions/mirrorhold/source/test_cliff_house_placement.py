"""Focused source regression for repaired cliff-house datums and supports."""
from pathlib import Path
import sys
import unittest

PACKAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PACKAGE.parent/'_toolkit'))
import landscape_plan as P
import landmarks as L


class CliffHousePlacements(unittest.TestCase):
    def test_foundations_match_the_existing_wall_footprint(self):
        for spec in P.HOUSE_MASONRY_FOUNDATIONS:
            with self.subTest(node=spec['node']):
                mesh=P._house_foundation_mesh(spec)
                low,high=mesh.bounds()
                self.assertAlmostEqual(high[1],0.,delta=1e-9)
                self.assertAlmostEqual(low[1],-spec['height'],delta=1e-9)
                self.assertAlmostEqual(high[0]-low[0],spec['width'],delta=1e-6)
                self.assertAlmostEqual(high[2]-low[2],spec['depth'],delta=1e-6)
                variant=spec['variant']
                wall_width=(4.4+variant*.6)*P.REG.LOCAL
                wall_depth=(5+(variant%2)*.8)*P.REG.LOCAL
                house=L.cliff_house(width=wall_width,depth=wall_depth,
                                    storeys=2+variant%3)
                wall=next(part for part in house.parts if part.material==L.ASHLAR)
                wall_low,wall_high=wall.bounds()
                self.assertAlmostEqual(high[0]-low[0],wall_high[0]-wall_low[0],delta=1e-6)
                self.assertAlmostEqual(high[2]-low[2],wall_high[2]-wall_low[2],delta=1e-6)

    def test_every_exposed_lift_has_a_plinth_at_the_same_datum(self):
        foundations={spec['house']:spec for spec in P.HOUSE_MASONRY_FOUNDATIONS}
        for repair in P.HOUSE_DATUM_REPAIRS:
            with self.subTest(node=repair['node']):
                if repair['node']=='Building_CliffHouse_4':
                    self.assertNotIn(repair['node'],foundations)
                else:
                    self.assertAlmostEqual(foundations[repair['node']]['base'],repair['base'])

    def test_canal_edge_house_moves_with_its_shorter_support(self):
        move=next(spec for spec in P.HOUSE_POSITION_REPAIRS
                  if spec['node']=='Building_lower-terrace_1')
        support=next(spec for spec in P.HOUSE_MASONRY_FOUNDATIONS
                     if spec['house']=='Building_lower-terrace_1')
        self.assertEqual((move['x'],move['z'],move['base']),
                         (support['x'],support['z'],support['base']))
        self.assertLessEqual(support['height'],1.9)

if __name__=='__main__':unittest.main()

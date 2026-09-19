"""Focused regression for replacing the eight detached display-water pieces."""
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

PACKAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PACKAGE.parent/'_toolkit'))
from amberwood import mesh as M
import landscape_plan as P
import region as REG


class WaterworksReplacement(unittest.TestCase):
    def test_three_catchments_descend_and_join_the_lake(self):
        streams=P.WATERWORK_STREAMS
        self.assertEqual(set(streams),{'upper_cascade','canal_west','canal_east'})
        self.assertEqual(sum(len(points)-1 for points in streams.values()),9)
        self.assertEqual(streams['upper_cascade'][-1],streams['canal_west'][0])
        for name,points in streams.items():
            with self.subTest(stream=name):
                self.assertTrue(all(a[1]>b[1] for a,b in zip(points,points[1:])))
        for name in ('canal_west','canal_east'):
            with self.subTest(outfall=name):
                self.assertAlmostEqual(streams[name][-1][1]-REG.LAKE_LEVEL,.12)

    def test_retirement_set_is_exactly_the_eight_legacy_pieces(self):
        self.assertEqual(P.OBSOLETE_WATERWORK_NODES,
            {f'Landmark_Channel_{i}' for i in range(5)}|
            {f'Landmark_Fall_{i}' for i in range(3)})

    def test_retirement_refuses_to_run_before_replacement_exists(self):
        build=SimpleNamespace(water_meshes={},authored_streams=[],placements=[])
        with self.assertRaisesRegex(AssertionError,'three-catchment'):
            P._retire_obsolete_waterworks(build)

    def test_retirement_preserves_routes_and_active_water(self):
        canal=M.box((1,.02,1),material='water_stream')
        sentinel=SimpleNamespace(node='Landmark_MeltwaterBridge_1')
        obsolete=[SimpleNamespace(node=name) for name in P.OBSOLETE_WATERWORK_NODES]
        build=SimpleNamespace(
            water_meshes={'Water_Canal':canal,'Water_Lake':canal},
            authored_streams=[{'id':name,'waypoints':points}
                              for name,points in P.WATERWORK_STREAMS.items()],
            placements=obsolete+[sentinel])
        P._retire_obsolete_waterworks(build)
        self.assertEqual(build.placements,[sentinel])
        self.assertIn('Water_Canal',build.water_meshes)
        self.assertIn('Water_Lake',build.water_meshes)


if __name__=='__main__':unittest.main()

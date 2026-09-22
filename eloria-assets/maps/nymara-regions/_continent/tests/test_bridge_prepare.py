from pathlib import Path
from types import ModuleType,SimpleNamespace
import sys
import unittest
from unittest.mock import patch


HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import bridge_prepare as P
import build_continent as B


class BridgePreparationTests(unittest.TestCase):
    def test_claimed_river_fit_runs_with_current_world_and_content(self):
        calls=[];world=SimpleNamespace();content=object()
        bridges=ModuleType('bridge_export')
        bridges.fit_claimed_sites=lambda actual,content=None:(calls.append(('river-fit',actual,content)) or {'selectedSiteIds':[3,7]})
        with patch.dict(sys.modules,{'bridge_export':bridges}):
            report=P.prepare_bridges(world,content)
        self.assertEqual(calls,[('river-fit',world,content)])
        self.assertEqual(report,{'claimedRiverFit':{'count':2,'siteIds':(3,7)}})

    def test_coordinator_is_a_composition_shaping_source(self):
        self.assertIn('bridge_prepare.py',B.SHAPING_SOURCES)


if __name__=='__main__':unittest.main()

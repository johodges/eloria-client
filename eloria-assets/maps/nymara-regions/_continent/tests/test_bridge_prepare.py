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
    def test_default_component502_selection_does_not_apply_component501_edit(self):
        calls=[];world=SimpleNamespace();content=object()
        records=(SimpleNamespace(claim_id='coast-502'),)
        sea=ModuleType('sea_crossings');bridges=ModuleType('bridge_export');coast=ModuleType('coastal_bridge_export')
        sea.COMPONENT501_ROAD='coast-501';sea.DEFAULT_SELECTED_COASTAL_ROADS=('coast-502',)
        sea._selected_coastal_roads=lambda values:tuple(values)
        sea.apply_coastal_road_edits=lambda actual:(_ for _ in ()).throw(
            AssertionError('component 501 edit ran during the component 502 release'))
        bridges.fit_claimed_sites=lambda actual,content=None:(calls.append(('river-fit',actual,content)) or {'selectedSiteIds':[3,7]})
        inventory={'looseWetCellIndices':(4,5,8),'components':()}
        bridges.loose_crossing_inventory=lambda actual:(calls.append(('inventory',actual)) or inventory)
        sea.prepare_coastal_claims=lambda actual,content=None,inventory=None,selected_road_ids=None:(
            calls.append(('coastal-fit',actual,content,inventory,selected_road_ids)) or records)
        registry={'mode':'selected-with-legacy-fallback','authorityLooseWetCellIndices':(4,5,8),
                  'prepared':({'looseWetCells':(4,5)},),'fallbackLooseWetCellIndices':(8,)}
        coast.build_selected_inventory=lambda actual,actual_records:(
            calls.append(('registry',actual,actual_records)) or registry)
        with patch.dict(sys.modules,{'sea_crossings':sea,'bridge_export':bridges,
                                     'coastal_bridge_export':coast}):
            report=P.prepare_bridges(world,content)
        self.assertEqual([call[0] for call in calls],
                         ['river-fit','inventory','coastal-fit','registry'])
        self.assertIs(calls[0][1],world);self.assertIs(calls[0][2],content);self.assertIs(calls[2][2],content)
        self.assertIs(calls[2][3],inventory);self.assertEqual(calls[2][4],('coast-502',))
        self.assertEqual(world.claimed_coastal_records,records)
        self.assertIs(world.claimed_coastal_inventory,registry)
        self.assertEqual(report,{'coastalRoadEdits':{'count':0,'roadIds':()},
                                 'claimedRiverFit':{'count':2,'siteIds':(3,7)},
                                 'coastalClaims':{'count':1,'claimIds':('coast-502',),
                                     'selectedRoadIds':('coast-502',),
                                     'mode':'selected-with-legacy-fallback','authorityWetCells':3,
                                     'preparedWetCells':2,'fallbackWetCells':1}})

    def test_component501_edit_is_gated_by_explicit_selection(self):
        world=SimpleNamespace();calls=[]
        sea=ModuleType('sea_crossings');bridges=ModuleType('bridge_export');coast=ModuleType('coastal_bridge_export')
        sea.COMPONENT501_ROAD='coast-501';sea.DEFAULT_SELECTED_COASTAL_ROADS=('coast-502',)
        sea._selected_coastal_roads=lambda values:tuple(values)
        sea.apply_coastal_road_edits=lambda actual:(calls.append('edit') or (SimpleNamespace(road_id='coast-501'),))
        bridges.fit_claimed_sites=lambda actual,content=None:{'selectedSiteIds':[]}
        inventory={'looseWetCellIndices':(),'components':()}
        bridges.loose_crossing_inventory=lambda actual:inventory
        record=SimpleNamespace(claim_id='coastal-501')
        sea.prepare_coastal_claims=lambda *args,**kwargs:(record,)
        registry={'mode':'selected-with-legacy-fallback','authorityLooseWetCellIndices':(),
                  'prepared':(),'fallbackLooseWetCellIndices':()}
        coast.build_selected_inventory=lambda actual,records:registry
        with patch.dict(sys.modules,{'sea_crossings':sea,'bridge_export':bridges,
                                     'coastal_bridge_export':coast}):
            report=P.prepare_bridges(world,object(),selected_coastal_road_ids=('coast-501',))
        self.assertEqual(calls,['edit'])
        self.assertEqual(report['coastalRoadEdits']['roadIds'],('coast-501',))
        self.assertEqual(report['coastalClaims']['selectedRoadIds'],('coast-501',))

    def test_coordinator_is_a_composition_shaping_source(self):
        self.assertIn('bridge_prepare.py',B.SHAPING_SOURCES)


if __name__=='__main__':unittest.main()

"""Authored bank aprons extend the same visible union in only their region."""
from pathlib import Path
import sys
import numpy as np
import pytest
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent))
from test_bridge_export import world,water
import bridge_export as B


def test_regional_apron_extends_only_selected_bank_and_preserves_terrain():
    original=world();baseline=B.common_surface(original,water_fields=water)
    revised=world();revised.plan={'bridge_approach_aprons':{'west':14}}
    sampled=revised.height_at(np.arange(49.),20).copy()
    field=B.common_surface(revised,water_fields=water)
    assert field['approachCoverage']['west']['additionalCells']>0
    np.testing.assert_array_equal(field['mask'][:,24:],baseline['mask'][:,24:])
    assert np.all(field['mask']>=baseline['mask'])
    assert field['maximumBankError']<=.12
    np.testing.assert_array_equal(sampled,revised.height_at(np.arange(49.),20))
    for component in field['components']:
        mesh,_=B.deck_mesh(revised,component);faces=mesh.positions[mesh.indices.reshape(-1,3)]
        normal=np.cross(faces[:,1]-faces[:,0],faces[:,2]-faces[:,0])
        assert np.all(normal[:,1]>0)
        assert np.max(np.hypot(normal[:,0],normal[:,2])/normal[:,1])<=.65
        assert np.min(faces[:,:,2])>=17 and np.max(faces[:,:,2])<=23


@pytest.mark.parametrize('setting',[{'west':5},{'west':97},{'absent':42},{'west':float('nan')}])
def test_invalid_apron_configuration_fails(setting):
    revised=world();revised.plan={'bridge_approach_aprons':setting}
    with pytest.raises(ValueError,match='known region and 6..96'):
        B.common_surface(revised,water_fields=water)


def test_connection_apron_reaches_both_banks_without_other_road_growth():
    original=world()
    original.roads[0]['id']='west--east-west';original.roads[1]['id']='west--east-east'
    original.roads.append({'id':'unrelated','width':2.,'points':[[4,0,5],[44,0,5]]})
    baseline=B.common_surface(original,water_fields=water)
    original.plan={'bridge_approach_connections':{'west--east':18}}
    sampled=original.height_at(np.arange(49.),20).copy()
    actual=B.common_surface(original,water_fields=water)
    assert actual['connectionApproachCoverage']['west--east']['additionalCells']>0
    # Only the selected named road family grows; a separate crossing retains
    # its original physical extent on both sides of the same river.
    np.testing.assert_array_equal(actual['mask'][:9],baseline['mask'][:9])
    assert (actual['mask'][15:25,:18]&~baseline['mask'][15:25,:18]).any()
    assert (actual['mask'][15:25,31:]&~baseline['mask'][15:25,31:]).any()
    np.testing.assert_array_equal(original.height_at(np.arange(49.),20),sampled)
    assert actual['maximumBankError']<=.12


@pytest.mark.parametrize('setting',[{'absent':42},{'west--east':5},{'west--east':float('nan')}])
def test_invalid_connection_apron_configuration_fails(setting):
    revised=world();revised.roads[0]['id']='west--east-west'
    revised.plan={'bridge_approach_connections':setting}
    with pytest.raises(ValueError,match='known walking connection'):
        B.common_surface(revised,water_fields=water)

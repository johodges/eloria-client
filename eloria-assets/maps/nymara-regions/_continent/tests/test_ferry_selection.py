"""Geometric ferry candidate selection must leave the composed world unchanged."""
from pathlib import Path
import copy
import sys

import numpy as np
import pytest

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import build_continent as B
import ferry_export as F
from world_layout import World


class Coast:
    ids=['port']
    prepare_quay_court=World.prepare_quay_court
    hub=World.hub

    def __init__(self,extent=48):
        self.plan={}
        self.x=np.arange(0.,42.,2.);self.z=np.arange(0.,extent+2.,2.)
        self.gx,self.gz=np.meshgrid(self.x,self.z)
        self.height=np.where(self.gx>=20.,-2.,1.)
        self.owner=np.zeros((len(self.z)-1,len(self.x)-1),int)
        self.obstacles=np.zeros_like(self.height,bool)
        self.ferry_exclusion=np.zeros_like(self.height,bool)
        self.water={'sea_mask':self.gx>=20.,'mask':self.gx>=20.}
        self.regions={'port':{'center':[16.,extent//2//2*2.]}}
        self.quay_contacts=[]

    def height_at(self,x,z):
        return self.height[int(z/2),int(x/2)]


def test_rejects_first_unbuildable_site_uses_separated_candidate_and_rolls_back(monkeypatch):
    world=Coast();original=world.height;before=original.copy();calls=[]
    world.quay_contacts=[{'center':[0.,0.],'elevation':2.}]
    saved=copy.deepcopy(world.quay_contacts)
    def fit(candidate_world,point,region):
        calls.append(np.array(point))
        assert region=='port'
        assert len(candidate_world.quay_contacts)==len(saved)+1
        assert candidate_world.height is not original
        assert candidate_world.height_at(*point)>=1.8
        if len(calls)==1:raise ValueError('bank is dry but whole mooring does not fit')
        return {'minimumBoatDepth':1.4,'contactError':.025}
    monkeypatch.setattr(F,'fit_landing',fit)
    result=B.ferry_landing(world,'port',[40.,24.])
    assert len(calls)==2 and np.array_equal(result,calls[1])
    assert np.linalg.norm(calls[1]-calls[0])>=6
    assert world.height is original and np.array_equal(original,before)
    assert world.quay_contacts==saved
    assert world.ferry_selection==[{'region':'port','position':result.tolist(),
        'candidatesTried':2,'mooringDepth':1.4,'contactError':.025}]


def test_existing_berths_and_retained_causeways_are_excluded_before_fit(monkeypatch):
    world=Coast(100);world.quay_contacts=[{'center':[16.,50.],'elevation':1.8}]
    world.ferry_exclusion=world.gz>50.
    calls=[]
    def fit(candidate_world,point,region):
        calls.append(np.array(point))
        assert np.linalg.norm(point-[16.,50.])>=20.
        assert point[1]<=50.
        return {'minimumBoatDepth':1.,'contactError':.02}
    monkeypatch.setattr(F,'fit_landing',fit)
    result=B.ferry_landing(world,'port',[40.,50.])
    assert len(calls)==1
    assert np.linalg.norm(result-[16.,50.])>=20
    assert len(world.quay_contacts)==1


def test_all_failed_candidates_are_bounded_and_restore_world(monkeypatch):
    world=Coast(1000);original=world.height;before=original.copy();calls=[]
    def reject(candidate_world,point,region):
        assert len(candidate_world.quay_contacts)==1
        calls.append(np.array(point))
        raise ValueError('no space for complete hull')
    monkeypatch.setattr(F,'fit_landing',reject)
    with pytest.raises(ValueError,match='none of 64 ranked shoreline sites'):
        B.ferry_landing(world,'port',[40.,500.])
    assert len(calls)==64
    distance=np.linalg.norm(np.array(calls)[:,None,:]-np.array(calls)[None,:,:],axis=2)
    assert np.min(distance+np.eye(len(calls))*10000)>=6.
    assert world.height is original and np.array_equal(original,before)
    assert world.quay_contacts==[] and not hasattr(world,'ferry_selection')


def test_unexpected_geometry_error_rolls_back_without_concealing_it(monkeypatch):
    world=Coast();original=world.height;before=original.copy()
    def broken(candidate_world,point,region):
        raise RuntimeError('malformed source geometry')
    monkeypatch.setattr(F,'fit_landing',broken)
    with pytest.raises(RuntimeError,match='malformed source geometry'):
        B.ferry_landing(world,'port',[40.,24.])
    assert world.height is original and np.array_equal(original,before)
    assert world.quay_contacts==[] and not hasattr(world,'ferry_selection')


def test_no_coast_does_not_trial_any_geometry(monkeypatch):
    world=Coast();world.obstacles[:]=True
    def unexpected(*args):raise AssertionError('no coast must not call the fitter')
    monkeypatch.setattr(F,'fit_landing',unexpected)
    with pytest.raises(ValueError,match='no coast for ferry landing'):
        B.ferry_landing(world,'port',[40.,24.])
    assert world.quay_contacts==[]

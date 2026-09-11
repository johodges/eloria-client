"""A shop's entry, arrival, exit and exterior return remain distinct and usable."""
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'eloria-assets/tools'))
import continent_portals as C


@pytest.fixture
def shop(monkeypatch):
    doors = {'lantern-door': {'destination': 'four-gates-lantern-row',
                            'spawn': 'arrival', 'tile': (160, 120)}}
    outside = {'coordinateTransform': {'serverOrigin': [198, 198]}}
    room = {'asset': {'interior': True},
            'coordinateTransform': {'serverOrigin': [18, 18]},
            'spawnPoints': [{'id': 'arrival', 'position': [0, 0, 5.3]}],
            'portals': [{'id': 'exit', 'position': [0, 0, 6.6],
                         'targetPosition': [-38, 31, 74]}]}
    monkeypatch.setattr(C, 'load_portals', lambda region: doors)
    monkeypatch.setattr(C, 'read_manifest', lambda path:
                        outside if path.parent.name == 'four-gates' else room)
    return room


def test_publishes_explicit_exit_and_return_without_arrival_bounce(shop):
    errors = []
    lines, count = C.standalone_interior_lines({}, {},
        lambda _: SimpleNamespace(walkable=lambda x, y: True), errors, 'four_gates')
    assert errors == []
    assert count == 2
    assert lines[1:] == [
        'portal | four_gates | 160 | 120 | four-gates-lantern-row | 18 | 13',
        'portal | four-gates-lantern-row | 18 | 11 | four_gates | 160 | 124']


def test_blocked_door_fails_without_silently_relocating_it(shop):
    errors = []
    _, count = C.standalone_interior_lines({}, {}, lambda _: SimpleNamespace(
        walkable=lambda x, y: (x, y) != (18, 11)), errors, 'four_gates')
    assert count == 0
    assert errors == ['lantern-door: blocked exit four-gates-lantern-row (18, 11)']


def test_arrival_on_exit_is_rejected(shop):
    shop['spawnPoints'][0]['position'] = shop['portals'][0]['position']
    errors = []
    _, count = C.standalone_interior_lines({}, {},
        lambda _: SimpleNamespace(walkable=lambda x, y: True), errors, 'four_gates')
    assert count == 0
    assert errors == ['lantern-door: arrival overlaps its return trigger']


def test_unrelated_region_does_not_load_or_rewrite_shop_routes():
    def forbidden(_):
        raise AssertionError('Unrelated region loaded a Four Gates room')
    assert C.standalone_interior_lines({}, {}, forbidden, [], 'westhaven') == ([], 0)

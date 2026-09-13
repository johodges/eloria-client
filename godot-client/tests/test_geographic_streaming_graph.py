"""Physical adjacency supplements the travel graph without inventing crossings."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'eloria-assets/tools'))
from build_exterior_streaming import physical_edges


def test_shared_profile_samples_merge_without_bridging_real_gaps():
    data = {'boundaryHeightField': {'segments': [
        {'regions': ['a','b'], 'start': [5,0], 'end': [5,2]},
        {'regions': ['b','a'], 'start': [5,4], 'end': [5,2]},
        {'regions': ['a','b'], 'start': [5,6], 'end': [5,8]},
        {'regions': ['a','b'], 'start': [5,8], 'end': [9,8]},
    ]}}
    assert physical_edges(data) == {('a','b'): [
        [[5,8],[9,8]], [[5,0],[5,4]], [[5,6],[5,8]]
    ]}

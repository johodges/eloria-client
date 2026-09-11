"""Height warnings compare adjacent tiles without wrapping opposite shores."""
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] /
                     'eloria-assets/maps/nymara-regions/_toolkit'))
from verify_runtime import adjacent_jumps


def test_gradual_slopes_do_not_join_opposite_map_edges():
    rows, columns = np.mgrid[:12, :12]
    heights = (rows + columns).astype(float)
    assert adjacent_jumps(heights, np.ones_like(heights, bool)) == []


def test_real_jumps_remain_visible_and_inaccessible_tiles_are_ignored():
    heights = np.array([[0., 10., 20.], [0., 0., 20.]])
    reachable = np.array([[True, True, False], [True, True, False]])
    assert set(adjacent_jumps(heights, reachable)) == {(0, 0, 10.), (1, 0, 10.)}

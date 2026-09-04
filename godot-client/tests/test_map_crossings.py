#!/usr/bin/env python3
"""A bridge has to carry walkable cells for its whole length.

The server walks a player over `collision.bin`, and a region declares its
crossings as `type: bridge` landmarks. If the walk grid does not put a
continuous walkable run under a deck, the bridge is scenery: the client draws
it, the client will even ground an actor on it, and the server will not let
anyone step onto it.

Whitehorn Range shipped that way. Its walk grid gave a 34 x 1.9 m rope bridge a
disc of the *smaller* half-extent - 1.6 m of walkable cells over the middle of a
22 m chasm, unreachable from either bank - so the only two crossings of the
gorge were a 900 m walk apart in a map that looked like it had them 40 m apart.
"""
from __future__ import annotations

from collections import deque
import json
from pathlib import Path
import struct
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
REGIONS = ROOT / "eloria-assets" / "maps" / "nymara-regions"

GLB_MAGIC = b"glTF"
CHUNK_JSON = 0x4E4F534A

# How far past a deck's ends to stand while asking whether the two sides are
# joined, and how much walking - as a multiple of the deck - counts as having
# crossed on the bridge rather than around it.
LANDING_MARGIN = 2.0
CROSSING_FACTOR = 4.0

# Regions whose crossings have been walked through and verified against this
# probe. It is not every region on purpose: the probe steps off a deck along
# the world axes, which only reads a crossing correctly when the deck runs
# along one, and only Whitehorn has been checked. Verdant Stair's
# `root-crossing`, `rope-crossing-low` and `vine-bridge-north` fail this probe
# as it stands; whether that is three broken crossings or three decks the probe
# steps off sideways has not been established. Widen the set once it has.
VERIFIED_REGIONS = ("whitehorn_range",)


def read_document(path: Path) -> dict:
    data = path.read_bytes()
    offset = 12
    while offset < len(data):
        length, kind = struct.unpack("<II", data[offset:offset + 8])
        if kind == CHUNK_JSON:
            return json.loads(data[offset + 8:offset + 8 + length])
        offset += 8 + length
    raise ValueError(f"{path} has no JSON chunk")


def walk_deck_lengths(document: dict) -> dict[str, float]:
    """Landmark node name -> the longer horizontal extent of its walk mesh.

    Taken from the mesh's own accessor bounds, so it is the deck's length
    whichever way the node is turned.
    """
    accessors = document.get("accessors", [])
    meshes = document.get("meshes", [])
    lengths: dict[str, float] = {}
    # The walk prefix is on the node, not on the mesh: the exporter splits a
    # landmark into per-material meshes and hangs the deck off a `Walk_` node.
    for node in document.get("nodes", []):
        name = node.get("name", "")
        index = node.get("mesh")
        if not name.startswith("Walk_") or index is None:
            continue
        scale = node.get("scale", [1.0, 1.0, 1.0])
        longest = 0.0
        for primitive in meshes[index].get("primitives", []):
            position = primitive.get("attributes", {}).get("POSITION")
            if position is None:
                continue
            low = accessors[position]["min"]
            high = accessors[position]["max"]
            longest = max(longest, (high[0] - low[0]) * abs(scale[0]),
                          (high[2] - low[2]) * abs(scale[2]))
        # `Walk_<node>__<material>` - recover the node the landmark names.
        stem = name[len("Walk_"):].rsplit("__", 1)[0]
        lengths[stem] = max(lengths.get(stem, 0.0), longest)
    return lengths


def load_grid(path: Path) -> np.ndarray:
    data = path.read_bytes()
    _, _, _, width, height = struct.unpack("<4sHHII", data[:16])
    return np.frombuffer(data, dtype=np.uint8, offset=16).reshape(height, width)


def walk_distance(grid: np.ndarray, start: tuple[int, int],
                  goal: tuple[int, int], budget: int) -> int:
    """Cells walked from `start` to `goal`, or -1 if not joined inside `budget`.

    The search is held to a window around the pair, so a bridge whose banks are
    only joined by a walk right round the obstacle reads as not joined - which
    is the whole question a crossing answers.
    """
    height, width = grid.shape
    top = max(0, min(start[0], goal[0]) - budget)
    bottom = min(height - 1, max(start[0], goal[0]) + budget)
    left = max(0, min(start[1], goal[1]) - budget)
    right = min(width - 1, max(start[1], goal[1]) + budget)
    seen = {start}
    frontier = deque([(start, 0)])
    while frontier:
        (row, column), steps = frontier.popleft()
        if (row, column) == goal:
            return steps
        if steps >= budget:
            continue
        for delta_row, delta_column in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            neighbour = (row + delta_row, column + delta_column)
            if not (top <= neighbour[0] <= bottom and left <= neighbour[1] <= right):
                continue
            if neighbour in seen or not grid[neighbour]:
                continue
            seen.add(neighbour)
            frontier.append((neighbour, steps + 1))
    return -1


def packages() -> list[Path]:
    return sorted(REGIONS / region / "world.json" for region in VERIFIED_REGIONS
                  if (REGIONS / region / "collision.bin").exists())


class MapCrossings(unittest.TestCase):
    def test_regions_are_present(self) -> None:
        self.assertEqual(len(packages()), len(VERIFIED_REGIONS),
                         "the verified region packages should be checked out")

    def test_every_bridge_joins_its_two_sides(self) -> None:
        offenders: list[str] = []
        checked = 0
        for manifest_path in packages():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            bridges = [landmark for landmark in manifest.get("landmarks", [])
                       if landmark.get("type") == "bridge"]
            if not bridges:
                continue
            transform = manifest["coordinateTransform"]
            origin_x, origin_z = transform["serverOrigin"]
            cell = float(manifest["collision"].get("cellMetres", 0.5))
            grid = load_grid(manifest_path.parent / "collision.bin")
            decks = walk_deck_lengths(read_document(manifest_path.parent / "world.glb"))
            for bridge in bridges:
                deck = decks.get(str(bridge.get("node", "")), 0.0)
                if deck <= 0.0:
                    continue
                x, _, z = bridge["position"]
                column = int(round((x + origin_x) / cell - 0.5))
                row = int(round((origin_z - z) / cell - 0.5))
                if not (0 <= row < grid.shape[0] and 0 <= column < grid.shape[1]):
                    continue
                reach = int(round((deck * 0.5 + LANDING_MARGIN) / cell))
                budget = int(round(deck * CROSSING_FACTOR / cell))
                # The deck runs along one axis or the other; whichever pair of
                # landings is walkable is the one the bridge serves.
                walked: list[int] = []
                for axis in (0, 1):
                    near = (row, column - reach) if axis else (row - reach, column)
                    far = (row, column + reach) if axis else (row + reach, column)
                    if not (0 <= min(near[0], far[0]) and
                            max(near[0], far[0]) < grid.shape[0] and
                            0 <= min(near[1], far[1]) and
                            max(near[1], far[1]) < grid.shape[1]):
                        continue
                    if not (grid[near] and grid[far]):
                        continue
                    walked.append(walk_distance(grid, near, far, budget))
                checked += 1
                if not walked:
                    # Neither pair of landings is walkable ground. For a region
                    # in VERIFIED_REGIONS that is the failure itself: a deck
                    # whose ends stand on cells the server refuses is a deck
                    # nobody can step onto.
                    offenders.append(
                        "%s: %s has a %.0f m deck and neither end lands on "
                        "walkable ground" % (
                            manifest_path.parent.name, bridge["id"], deck))
                    continue
                if max(walked) < 0:
                    offenders.append(
                        "%s: %s has a %.0f m deck, and its two landings are not "
                        "joined inside %.0f m of walking" % (
                            manifest_path.parent.name, bridge["id"], deck,
                            deck * CROSSING_FACTOR))
        self.assertGreater(checked, 0, "no bridge landmarks were checked")
        self.assertEqual(offenders, [], "every bridge must join its two sides")


if __name__ == "__main__":
    unittest.main(verbosity=2)

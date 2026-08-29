#!/usr/bin/env python3
"""The registry contract that lets one garment fit sixteen different bodies.

Garments are authored on one reference rig and worn by every race.  Two
mechanisms make that work, and both live in ``data/actors/equipment.json``:

* ``bodyGirth`` - how far each race's body stands off each bone.  The runtime
  divides the wearer's numbers by the numbers of the rig a piece was authored
  on and lets the garment out by the difference, which is what allows the
  authored mesh to be cut close instead of sized for the broadest race.
* ``fitGroups`` and per-model ``variants`` - the escape hatch for a build that
  cannot be reached by resizing at all, such as a digitigrade leg.  Those races
  wear a copy of the piece authored on their own rig.

A break in either one is silent in the editor and obvious on a player, so the
shape of the data is checked here rather than discovered in a screenshot.
"""
from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CLIENT = ROOT / "godot-client"
EQUIPMENT = CLIENT / "data" / "actors" / "equipment.json"
RACES = CLIENT / "assets" / "actors" / "native" / "races"

# Bones a garment can be bound to.  Every race has to be measured around all of
# them or the runtime has nothing to compare a wearer against.
REQUIRED_GIRTH_BONES = {
    "pelvis", "spine_01", "spine_02", "spine_03",
    "clavicle_l", "clavicle_r", "upperarm_l", "upperarm_r",
    "thigh_l", "thigh_r", "calf_l", "calf_r", "foot_l", "foot_r",
}


def scene_path(res_path: str) -> Path:
    return CLIENT / res_path.removeprefix("res://")


class EquipmentFitTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(EQUIPMENT.read_text())
        cls.models = cls.registry["models"]
        cls.girth = cls.registry.get("bodyGirth", {})
        cls.groups = cls.registry.get("fitGroups", {})
        cls.races = sorted(path.stem for path in RACES.glob("*.glb"))

    def test_every_race_is_measured(self) -> None:
        self.assertTrue(self.races, "no race GLBs to measure")
        for race in self.races:
            self.assertIn(race, self.girth, f"{race} has no body measurements")
            missing = REQUIRED_GIRTH_BONES - set(self.girth[race])
            self.assertEqual(missing, set(), f"{race} is unmeasured around {missing}")
            for bone, radius in self.girth[race].items():
                self.assertGreater(float(radius), 0.0,
                                   f"{race}/{bone} measures no body at all")

    def test_measurements_are_plausible(self) -> None:
        # A ratio outside this range is a measurement bug, not a body: the
        # runtime clamps at 2.0, so anything near it would silently lose fit.
        reference = self.girth.get("luminous_male", {})
        self.assertTrue(reference, "the reference rig is unmeasured")
        for race in self.races:
            for bone, radius in self.girth[race].items():
                base = float(reference.get(bone, 0.0))
                if base <= 0.0:
                    continue
                ratio = float(radius) / base
                self.assertGreater(ratio, 0.4, f"{race}/{bone} ratio {ratio:.2f}")
                self.assertLess(ratio, 2.0, f"{race}/{bone} ratio {ratio:.2f}")

    def test_skinned_models_name_the_rig_they_were_authored_on(self) -> None:
        for key, model in self.models.items():
            if model.get("attach") != "skinned":
                continue
            author = model.get("authoredFor", "")
            self.assertTrue(author, f"{key} does not say what body it fits")
            self.assertIn(author, self.girth,
                          f"{key} was authored for the unmeasured rig {author}")

    def test_fit_group_races_exist(self) -> None:
        for race, group in self.groups.items():
            self.assertIn(race, self.races, f"fit group {group} names no race {race}")

    def test_variants_are_present_and_authored_on_their_own_rig(self) -> None:
        seen_groups: set[str] = set()
        for key, model in self.models.items():
            for group, variant in (model.get("variants") or {}).items():
                seen_groups.add(group)
                self.assertIn(group, set(self.groups.values()),
                              f"{key} offers variant {group} that no race wears")
                path = scene_path(str(variant.get("scene", "")))
                self.assertTrue(path.is_file(), f"{key} variant {group}: {path} missing")
                author = str(variant.get("authoredFor", ""))
                self.assertIn(author, self.girth,
                              f"{key} variant {group} names unmeasured rig {author}")
                self.assertEqual(self.groups.get(author), group,
                                 f"{key} variant {group} is authored on {author},"
                                 " which is not a member of that group")
        self.assertEqual(seen_groups, set(self.groups.values()),
                         "a fit group exists that no garment offers a variant for")

    def test_every_group_member_can_reach_its_variants(self) -> None:
        # A race in a group must find a variant for every piece the group
        # declares, otherwise it silently falls back to the reference garment.
        by_group: dict[str, set[str]] = {}
        for model in self.models.values():
            for group, variant in (model.get("variants") or {}).items():
                by_group.setdefault(group, set()).add(str(variant["scene"]))
        for group, scenes in by_group.items():
            self.assertTrue(scenes, f"fit group {group} has no variants")
            for scene in scenes:
                self.assertTrue(scene_path(scene).is_file(), f"{scene} missing")


class GarmentWindingTest(unittest.TestCase):
    """Every closed garment shell has to face outwards.

    A loft's winding follows the order of its rings, and it is easy to build a
    shell the wrong way round without noticing: the renderer culls back faces,
    so an inside-out garment does not disappear, it goes *transparent from the
    near side* and shows whatever is behind it.  That is how a closed boot came
    to look like an open-toed sandal with the wearer's foot inside it.

    The check is the divergence theorem: summed about its own centroid, a closed
    shell wound outwards encloses positive volume.  Capes are sheets and gloves
    have an open cuff, so neither encloses anything and both are excluded.
    """

    OPEN_REGIONS = {"cape", "hands"}

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(EQUIPMENT.read_text())

    def _scenes(self):
        for model in self.registry["models"].values():
            if model.get("attach") != "skinned":
                continue
            region = str(model.get("skinRegion", ""))
            if region in self.OPEN_REGIONS:
                continue
            yield scene_path(str(model["scene"]))
            for variant in (model.get("variants") or {}).values():
                yield scene_path(str(variant["scene"]))

    def test_closed_garments_are_wound_outwards(self) -> None:
        try:
            import numpy as np
        except ImportError:  # pragma: no cover - numpy is a build requirement
            self.skipTest("numpy is required to read garment geometry")
        seen = 0
        for path in sorted(set(self._scenes())):
            self.assertTrue(path.is_file(), f"{path} missing")
            volume = 0.0
            for points, triangles in _mesh_primitives(path):
                middle = points.mean(axis=0)
                local = points - middle
                volume += float(np.einsum(
                    "ij,ij->i", local[triangles[:, 0]],
                    np.cross(local[triangles[:, 1]],
                             local[triangles[:, 2]])).sum() / 6.0)
            seen += 1
            self.assertGreater(volume, 0.0,
                               f"{path.name} is wound inside out")
        self.assertGreater(seen, 10, "no closed garments were checked")


def _mesh_primitives(path: Path):
    """POSITION and index arrays of every primitive in a GLB."""
    import struct
    import numpy as np

    raw = path.read_bytes()
    json_size = struct.unpack_from("<I", raw, 12)[0]
    document = json.loads(raw[20:20 + json_size])
    offset = 20 + json_size
    binary_size = struct.unpack_from("<I", raw, offset)[0]
    binary = raw[offset + 8:offset + 8 + binary_size]
    dtypes = {5120: "i1", 5121: "u1", 5122: "<i2", 5123: "<u2",
              5125: "<u4", 5126: "<f4"}
    widths = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}

    def read(index: int) -> "np.ndarray":
        spec = document["accessors"][index]
        view = document["bufferViews"][spec["bufferView"]]
        dtype = np.dtype(dtypes[spec["componentType"]])
        width = widths[spec["type"]]
        start = view.get("byteOffset", 0) + spec.get("byteOffset", 0)
        stride = view.get("byteStride", dtype.itemsize * width)
        shape = (spec["count"],) if width == 1 else (spec["count"], width)
        strides = (stride,) if width == 1 else (stride, dtype.itemsize)
        return np.ndarray(shape, dtype=dtype, buffer=binary, offset=start,
                          strides=strides).copy()

    for mesh in document.get("meshes", []):
        for primitive in mesh["primitives"]:
            yield (read(primitive["attributes"]["POSITION"]).astype(float),
                   read(primitive["indices"]).astype(np.int64).reshape(-1, 3))


if __name__ == "__main__":
    unittest.main(verbosity=2)

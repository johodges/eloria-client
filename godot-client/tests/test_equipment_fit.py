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

    @staticmethod
    def _named(groups) -> list[str]:
        """A race's fit groups, whether the registry names one or several."""
        return [groups] if isinstance(groups, str) else list(groups)

    def _all_groups(self) -> set[str]:
        return {group for value in self.groups.values()
                for group in self._named(value)}

    def _members(self, group: str) -> set[str]:
        return {race for race, value in self.groups.items()
                if group in self._named(value)}

    def test_fit_group_races_exist(self) -> None:
        for race, value in self.groups.items():
            self.assertIn(race, self.races,
                          f"fit groups {self._named(value)} name no race {race}")
            self.assertTrue(self._named(value),
                            f"{race} is listed with no fit group at all")

    def test_variants_are_present_and_authored_on_their_own_rig(self) -> None:
        seen_groups: set[str] = set()
        for key, model in self.models.items():
            for group, variant in (model.get("variants") or {}).items():
                seen_groups.add(group)
                self.assertIn(group, self._all_groups(),
                              f"{key} offers variant {group} that no race wears")
                path = scene_path(str(variant.get("scene", "")))
                self.assertTrue(path.is_file(), f"{key} variant {group}: {path} missing")
                author = str(variant.get("authoredFor", ""))
                self.assertIn(author, self.girth,
                              f"{key} variant {group} names unmeasured rig {author}")
                self.assertIn(author, self._members(group),
                              f"{key} variant {group} is authored on {author},"
                              " which is not a member of that group")
        self.assertEqual(seen_groups, self._all_groups(),
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


class FootgearGroundTest(unittest.TestCase):
    """Footwear stands where the bare foot stands, near enough.

    The actor is placed on the ground by its body, not by what it is wearing,
    so anything a boot puts below the wearer's own sole is boot under the
    floor.  The shell this replaces hung three centimetres of heel down there,
    and because its sole was swept along each ring's own axis rather than in
    world space it arrived in disconnected pieces - parts of it floating above
    the toes while the back of it sank - which is what made the heel look lower
    than the foot it was on.

    What is checked here is how far the lowest point of a boot sits below the
    wearer's own sole, which is the half of it a number can settle.  Whether
    the sole arrives in one piece is a question about the shell's topology and
    is left to the authoring tool that builds it.
    """

    #: How far below the wearer's own sole a boot may reach, in metres. The
    #: shell this replaces reached 30 mm on a plantigrade foot and 36 on a
    #: digitigrade one; the authored sole now stands 4 mm proud of the plane
    #: the bare foot stands on.
    MAX_SINK = .008

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(EQUIPMENT.read_text())

    def _footgear(self):
        """Every footgear scene, with the rig it was authored on."""
        for model in self.registry["models"].values():
            if model.get("attach") != "skinned":
                continue
            if str(model.get("skinRegion", "")) != "boots":
                continue
            yield scene_path(str(model["scene"])), str(model.get("authoredFor", ""))
            for variant in (model.get("variants") or {}).values():
                yield (scene_path(str(variant["scene"])),
                       str(variant.get("authoredFor", "")))

    def test_footgear_stands_on_the_wearers_own_sole(self) -> None:
        try:
            import numpy as np
        except ImportError:  # pragma: no cover - numpy is a build requirement
            self.skipTest("numpy is required to read garment geometry")
        soles: dict[str, float] = {}
        seen = 0
        for path, rig in sorted(set(self._footgear())):
            self.assertTrue(path.is_file(), f"{path} missing")
            self.assertTrue(rig, f"{path.name} does not name the rig it fits")
            body = RACES / f"{rig}.glb"
            self.assertTrue(body.is_file(), f"{body} missing")
            if rig not in soles:
                lowest = min(points[:, 1].min()
                             for points, _ in _mesh_primitives(body))
                soles[rig] = float(lowest)
            boot = np.concatenate([points for points, _ in _mesh_primitives(path)])
            sink = soles[rig] - float(boot[:, 1].min())
            self.assertLessEqual(
                sink, self.MAX_SINK,
                f"{path.name} reaches {sink * 1000:.1f} mm below the sole of "
                f"{rig}, which puts it through the floor the actor stands on")
            seen += 1
        self.assertGreater(seen, 10, "no footgear was checked")


class LegwearSeamTest(unittest.TestCase):
    """A leg garment closes at three seams and leaves the boot the fourth.

    The pattern is ``FootgearGroundTest``'s: settle by measurement the half of
    the question a number can settle, and leave topology to the tool that
    builds it.  What a number settles here is where the garment's two horizontal
    edges are, because both are contracts with something else.

    The hem is a contract with the footwear brief.  The datum both briefs are
    cut against puts the boot cuff's top edge at world Y 0.320 on
    ``luminous_male`` and requires at least 80 mm of overlap below the highest
    trouser hem, so a hem that creeps down is a trouser that stops tucking in
    and a hem that creeps up is a strip of bare shin above the boot.  Neither is
    visible in the editor and both are obvious on a player.

    The waist is a contract with the torso garment, which spans Y 1.022-1.550.
    The trousers have to reach up into that band far enough to overlap it, and -
    since our user's ruling is that the legs carry the belt - the waistband has
    to be the outermost thing at that height rather than hidden under a shirt.
    """

    #: World Y on the reference rig.  Soft trousers tuck deeper than plate.
    HEM = {"pants": (.130, .160), "legs": (.166, .196), "kilt": (.130, .160)}
    #: The lowest the top of a leg garment may sit.  The torso hem is at 1.022.
    MIN_WAIST_TOP = 1.060
    #: Structural shells: the closed hip shell and the two closed leg tubes.
    STRUCTURAL_SHELLS = 3

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(EQUIPMENT.read_text())

    def _legwear(self):
        """Every leg garment authored on the reference rig."""
        for key, model in self.registry["models"].items():
            if not key.startswith("4:") or model.get("attach") != "skinned":
                continue
            if str(model.get("authoredFor", "")) != "luminous_male":
                continue
            yield key, scene_path(str(model["scene"])), str(model.get("kind", ""))

    def test_hems_and_waists_meet_the_seams_they_are_cut_against(self) -> None:
        try:
            import numpy as np
        except ImportError:  # pragma: no cover - numpy is a build requirement
            self.skipTest("numpy is required to read garment geometry")
        seen = 0
        for key, path, kind in sorted(set(self._legwear())):
            self.assertTrue(path.is_file(), f"{path} missing")
            points = np.concatenate([p for p, _ in _mesh_primitives(path)])
            low, high = float(points[:, 1].min()), float(points[:, 1].max())
            bounds = self.HEM.get(kind)
            if bounds is None:
                continue
            self.assertGreaterEqual(
                low, bounds[0],
                f"{key} ({kind}) hems at Y {low:.4f}, below {bounds[0]:.3f} - "
                f"it hangs past the boot it is meant to tuck into")
            self.assertLessEqual(
                low, bounds[1],
                f"{key} ({kind}) hems at Y {low:.4f}, above {bounds[1]:.3f} - "
                f"that is bare shin between the trouser and the boot cuff")
            self.assertGreaterEqual(
                high, self.MIN_WAIST_TOP,
                f"{key} tops out at Y {high:.4f}; the shirt hem is at 1.022 and "
                f"the waistband has to overlap it, not meet it")
            seen += 1
        self.assertGreater(seen, 50, "no leg garments were checked")

    def test_the_shell_and_both_leg_tubes_are_closed(self) -> None:
        """The seat is closed by a closed shell or it is not closed at all.

        An open tube encloses nothing.  The shell this replaces was capped at
        the top only, so it answered for no part of the body and coverage over
        the seat rested entirely on two leg tubes that never meet across the
        middle - which is precisely the bare band across the backside.  Three
        closed components is the shape that fixes it, and it is worth asserting
        because capping is one keyword and losing it is silent.
        """
        try:
            import numpy as np
        except ImportError:  # pragma: no cover - numpy is a build requirement
            self.skipTest("numpy is required to read garment geometry")
        seen = 0
        for key, path, _kind in sorted(set(self._legwear())):
            closed = _closed_component_count(path)
            self.assertGreaterEqual(
                closed, self.STRUCTURAL_SHELLS,
                f"{key} has {closed} closed shells, fewer than the hip shell "
                f"and two leg tubes the garment is built from")
            seen += 1
        self.assertGreater(seen, 50, "no leg garments were checked")


def _closed_component_count(path: Path) -> int:
    """How many watertight pieces a mesh is made of, welded by position."""
    import numpy as np

    total = 0
    for points, triangles in _mesh_primitives(path):
        keys = np.round(points, 5)
        _, index = np.unique(keys, axis=0, return_inverse=True)
        welded = index[triangles]
        parent = np.arange(welded.max() + 1)

        def find(node: int) -> int:
            while parent[node] != node:
                parent[node] = parent[parent[node]]
                node = parent[node]
            return node

        for a, b, c in welded:
            for x, y in ((a, b), (b, c)):
                ra, rb = find(int(x)), find(int(y))
                if ra != rb:
                    parent[ra] = rb
        groups: dict[int, list] = {}
        for triangle in welded:
            groups.setdefault(find(int(triangle[0])), []).append(triangle)
        for faces in groups.values():
            edges: dict[tuple, int] = {}
            for a, b, c in faces:
                for x, y in ((a, b), (b, c), (c, a)):
                    edges[(min(x, y), max(x, y))] = edges.get(
                        (min(x, y), max(x, y)), 0) + 1
            if all(count == 2 for count in edges.values()):
                total += 1
    return total


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

#!/usr/bin/env python3
"""The registry contract for the things an actor holds rather than wears.

A prop is not skinned to the body: it hangs off a hand bone through a socket,
and the mesh is authored to one convention so that one socket can hold eighty
different weapons -- long axis up, business end at +Y, and **the grip on the
origin**.  The last of those is what this checks, because it is the one a
bounding box gets wrong: a sickle, a saber or a scythe carries a curved head
far out to one side, so centring the whole piece puts the haft that far out
from under the hand and the weapon rides beside the fist instead of in it.

The other half is the second hand.  Part 1 is the left hand, not "the shield":
since Two Handed Wielding opened it, a one-handed weapon has a second visual
in a bank of its own that draws the same mesh from ``hand_l``.  A number in
that bank has to mean exactly one thing, so it must not also be a shield.
"""
from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CLIENT = ROOT / "godot-client"
EQUIPMENT = CLIENT / "data" / "actors" / "equipment.json"

#: Where the off-hand weapon visuals start, mirroring the server's own
#: ``OFFHAND_VISUAL_FIRST``.  Shields sit below it and never reach it.
OFFHAND_VISUAL_FIRST = 160

#: How far a grip may sit from the socket it is held by, in metres.  A hand is
#: about 90 mm across, so anything past a centimetre is visible and anything
#: past four is the weapon hanging beside the fist.  The whole generated set
#: lands inside 4 mm; the number is loose enough that a re-export which shifts
#: a haft by a millimetre is not a failure.
MAX_GRIP_OFFSET = .010


def scene_path(res_path: str) -> Path:
    return CLIENT / res_path.removeprefix("res://")


class HeldPropTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.models = json.loads(EQUIPMENT.read_text())["models"]

    def _held(self):
        """Every model an actor holds in a hand, with the bone it hangs off."""
        for key, model in self.models.items():
            part, _, visual = key.partition(":")
            if part not in {"0", "1"} or model.get("attach") == "skinned":
                continue
            bone = str((model.get("socket") or {}).get("bone", ""))
            yield int(part), int(visual), bone, model

    def test_every_held_model_names_a_hand(self) -> None:
        seen = 0
        for part, visual, bone, model in self._held():
            expected = "hand_r" if part == 0 else "hand_l"
            self.assertEqual(bone, expected,
                             f"{part}:{visual} ({model.get('name')}) hangs off "
                             f"{bone!r} rather than {expected!r}")
            self.assertTrue(scene_path(str(model["scene"])).is_file(),
                            f"{part}:{visual} has no mesh")
            seen += 1
        self.assertGreater(seen, 50, "no held props were checked")

    def test_a_grip_sits_on_the_socket_that_holds_it(self) -> None:
        try:
            import numpy as np
        except ImportError:  # pragma: no cover - numpy is a build requirement
            self.skipTest("numpy is required to read prop geometry")
        from test_equipment_fit import _mesh_primitives

        seen = 0
        for part, visual, _bone, model in self._held():
            if part == 1 and visual < OFFHAND_VISUAL_FIRST:
                continue  # a shield is strapped across its middle, not gripped
            path = scene_path(str(model["scene"]))
            points = np.concatenate([p for p, _ in _mesh_primitives(path)])
            span = float(points[:, 1].max() - points[:, 1].min())
            self.assertGreater(span, .1, f"{path.name} is not stood up along Y")
            near = _grip_band(points, span)
            for axis, way in ((0, "across"), (2, "through")):
                middle = float(near[:, axis].max() + near[:, axis].min()) / 2.
                self.assertLessEqual(
                    abs(middle), MAX_GRIP_OFFSET,
                    f"{path.name} grips {abs(middle) * 1000:.0f} mm {way} the "
                    f"socket, so it is held beside the hand rather than in it")
            seen += 1
        self.assertGreater(seen, 50, "no grips were checked")

    def test_the_off_hand_bank_is_the_weapons_and_only_the_weapons(self) -> None:
        offhand = {visual: model for part, visual, _b, model in self._held()
                   if part == 1 and visual >= OFFHAND_VISUAL_FIRST}
        shields = {visual for part, visual, _b, model in self._held()
                   if part == 1 and visual < OFFHAND_VISUAL_FIRST}
        self.assertTrue(offhand, "no weapon can be held in the left hand")
        self.assertTrue(shields, "no shields are registered")
        self.assertLess(max(shields), OFFHAND_VISUAL_FIRST,
                        "a shield has reached into the off-hand bank")
        self.assertLessEqual(max(offhand), 255,
                             "an off-hand visual will not fit in the byte the "
                             "enhanced-actor packet carries a part in")

    def test_each_off_hand_weapon_is_the_right_hand_one_moved_over(self) -> None:
        """The same mesh, from the other bone.  Deriving the id from the
        weapon's own means the pair can never drift apart, and it is what lets
        the server name a left-handed visual without a table of its own."""
        weapons = {visual: model for part, visual, _b, model in self._held()
                   if part == 0}
        first_weapon = min(weapons)
        seen = 0
        for part, visual, _bone, model in self._held():
            if part != 1 or visual < OFFHAND_VISUAL_FIRST:
                continue
            twin = visual - OFFHAND_VISUAL_FIRST + first_weapon
            self.assertIn(twin, weapons,
                          f"1:{visual} answers to no right-handed weapon")
            self.assertEqual(model["scene"], weapons[twin]["scene"],
                             f"1:{visual} draws a different mesh from 0:{twin}")
            seen += 1
        self.assertGreater(seen, 20, "no off-hand weapons were checked")


def _grip_band(points, span: float):
    """The vertices near the socket, widening until there are enough to read."""
    import numpy as np

    band = .05 * span
    while True:
        near = points[np.abs(points[:, 1]) <= band]
        if len(near) >= 24 or band >= .25 * span:
            return near if len(near) else points
        band *= 1.6


if __name__ == "__main__":
    unittest.main(verbosity=2)

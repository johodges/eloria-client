#!/usr/bin/env python3
"""Structural checks for the clean Nymara GLB asset library."""
from __future__ import annotations

import json
from pathlib import Path
import struct
import unittest


ROOT = Path(__file__).resolve().parents[2]
CLIENT = ROOT / "godot-client"


def glb_document(path: Path) -> dict:
    raw = path.read_bytes()
    if raw[:4] != b"glTF":
        raise AssertionError(f"invalid GLB magic: {path}")
    version, total = struct.unpack_from("<II", raw, 4)
    if version != 2 or total != len(raw):
        raise AssertionError(f"invalid GLB header: {path}")
    size, kind = struct.unpack_from("<II", raw, 12)
    if kind != 0x4E4F534A:
        raise AssertionError(f"missing GLB JSON chunk: {path}")
    return json.loads(raw[20:20 + size])


class NativeGlbAssetsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads((CLIENT / "data/actors/native_asset_catalog.json").read_text())
        cls.models = json.loads((CLIENT / "data/actors/models.json").read_text())
        cls.equipment = json.loads((CLIENT / "data/actors/equipment.json").read_text())

    def test_catalog_is_complete(self) -> None:
        self.assertEqual(14, len(self.catalog["races"]))
        self.assertEqual(32, len(self.catalog["creatures"]))
        self.assertEqual(63, len(self.catalog["equipment"]))
        self.assertEqual(109, self.catalog["validation"]["files"])

    def test_player_rigs_preserve_current_skeleton_and_budget(self) -> None:
        for model_id, entry in self.catalog["races"].items():
            with self.subTest(model=model_id):
                self.assertEqual(65, entry["joints"])
                self.assertGreaterEqual(entry["vertices"], 8_400)
                self.assertLess(entry["vertices"], 10_500)
                document = glb_document(ROOT / entry["path"])
                self.assertEqual(65, len(document["skins"][0]["joints"]))
                self.assertGreaterEqual(len(document["meshes"]), 4)

    def test_creatures_have_new_rigs_and_embedded_clips(self) -> None:
        expected_actor_types = set(range(204, 236))
        actual_actor_types = {entry["actor_type"] for entry in self.catalog["creatures"].values()}
        self.assertEqual(expected_actor_types, actual_actor_types)
        for slug, entry in self.catalog["creatures"].items():
            with self.subTest(creature=slug):
                document = glb_document(ROOT / entry["path"])
                self.assertEqual(21, len(document["skins"][0]["joints"]))
                self.assertEqual(7, len(document["animations"]))
                self.assertEqual(slug, self.models["actorTypes"][str(entry["actor_type"])])

    def test_every_equipment_visual_is_registered(self) -> None:
        expected = {f"{entry['part']}:{entry['visual']}"
                    for entry in self.catalog["equipment"].values()}
        self.assertEqual(expected, set(self.equipment["models"]))
        for entry in self.catalog["equipment"].values():
            glb_document(ROOT / entry["path"])

    def test_every_playable_actor_type_has_creation_option(self) -> None:
        options = self.models["creationOptions"]
        self.assertEqual(16, len(options))
        for option in options:
            actor_type = str(option["actorType"])
            self.assertEqual(option["model"], self.models["actorTypes"][actor_type])
            self.assertIn(option["model"], self.models["models"])

    def test_concept_npc_roster_uses_player_models_and_native_gear(self) -> None:
        self.assertEqual(62, len(self.models["npcLooks"]))
        for actor_type, look in self.models["npcLooks"].items():
            with self.subTest(actor_type=actor_type):
                self.assertEqual(look["model"], self.models["actorTypes"][actor_type])
                self.assertIn(look["model"], self.models["models"])
                for part, visual in look["equipmentVisuals"].items():
                    self.assertIn(f"{part}:{visual}", self.equipment["models"])


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Structural checks for the clean Nymara GLB asset library."""
from __future__ import annotations

import json
from pathlib import Path
import struct
import unittest


ROOT = Path(__file__).resolve().parents[2]
CLIENT = ROOT / "godot-client"

NYMARA_INVASION_MODELS = {
    400: ("mirrorfin_otter", "river_otter"),
    401: ("reedhorn_stag", "elk"),
    402: ("gate_turtle", "desert_tortoise"),
    403: ("lakeglass_drake", "sunscale_drake"),
    404: ("snowcrest_hare", "snow_hare"),
    405: ("glacier_ram", "thunder_ram"),
    406: ("iceback_ursid", "ice_bear"),
    407: ("rimeclaw", "frost_tiger"),
    408: ("crystal_mite", "ash_crawler"),
    409: ("resonant_hound", "dire_wolf"),
    410: ("stormglass_grazer", "armored_rhino"),
    411: ("prism_wyrm", "giant_komodo"),
    412: ("dunrunner", "emberfox"),
    413: ("steppe_aurochs", "ridgehorn"),
    414: ("sunmane_cat", "saber_tooth_cat"),
    415: ("dustscale_drake", "fire_salamander"),
    416: ("amberhart", "moose"),
    417: ("rootback_boar", "mossback_boar"),
    418: ("moor_wisp_hound", "frost_maw"),
    419: ("barrow_quillbeast", "porcupine"),
    420: ("canopy_glider", "two_tailed_fox"),
    421: ("cenote_toader", "miretoad"),
    422: ("scalevine_stalker", "giant_komodo"),
    423: ("sunscale_basilisk", "sunscale_drake"),
    424: ("mangrove_crab", "bog_lurker"),
    425: ("mudskipper_beast", "miretoad"),
    426: ("delta_crocodile", "giant_crocodile"),
    427: ("floodmaw", "giant_crocodile"),
}


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
        self.assertEqual(16, len(self.catalog["races"]))
        self.assertEqual(8, len(self.catalog["hair"]))
        self.assertEqual(32, len(self.catalog["creatures"]))
        self.assertEqual(66, len(self.catalog["equipment"]))
        # The three ambient Sunmane horses are real files under the native
        # asset tree and are validated with everything else.
        self.assertEqual(126, self.catalog["validation"]["files"])

    def test_ambient_creatures_are_scenery_only(self) -> None:
        """Ambient livestock are client scenery and must not claim actor types.

        Actor-type allocation belongs to the server. An ambient model that
        carried one could collide with a real creature id, so the catalogue
        keeps them in their own section and the roster count above stays exact.
        """
        ambient = self.catalog.get("ambientCreatures", {})
        self.assertTrue(ambient, "ambient creature section is present")
        for slug, entry in ambient.items():
            with self.subTest(model=slug):
                self.assertNotIn("actor_type", entry)
                self.assertIn(slug, self.models["models"])
                self.assertIsNone(self.models["models"][slug]["serverActorType"])
                self.assertNotIn(slug, set(self.models["actorTypes"].values()))
                path = ROOT / entry["path"]
                self.assertTrue(path.is_file(), entry["path"])
                document = glb_document(path)
                self.assertEqual(
                    7, len(document.get("animations", [])),
                    "ambient creatures carry the shared creature action set")
                self.assertEqual(21, len(document["skins"][0]["joints"]))

    def test_player_rigs_preserve_current_skeleton_and_budget(self) -> None:
        for model_id, entry in self.catalog["races"].items():
            with self.subTest(model=model_id):
                self.assertEqual(65, entry["joints"])
                self.assertEqual("skinned", entry["wardrobe"])
                self.assertEqual("retargeted", entry["anatomy"])
                self.assertGreaterEqual(entry["vertices"], 13_500)
                # The race features (a Ssarathi tail and claws, Stoneborn
                # plating, a gilled Mycelari cap) are what sits above the
                # 13.5k shared body; the ceiling keeps them from growing
                # without anyone noticing.
                self.assertLess(entry["vertices"], 15_750)
                document = glb_document(ROOT / entry["path"])
                self.assertEqual(65, len(document["skins"][0]["joints"]))
                mesh_names = {mesh["name"] for mesh in document["meshes"]}
                self.assertTrue({"Eyebrows", "Eyes", "Body", "Wardrobe_Shirt",
                                 "Wardrobe_Pants", "Wardrobe_Boots"} <= mesh_names)

    def test_race_rigs_stand_on_the_same_ground_plane(self) -> None:
        """Retargeting must not lift or sink a race relative to the floor.

        The shared animation library writes pelvis translation directly, so a
        race whose legs got longer would keep the reference hip height and push
        its feet through the ground.  Every race therefore has to come out of
        the builder with the same hip and ground heights; only the division of
        the leg between them is allowed to differ.
        """
        by_gender: dict[str, set[tuple[float, float]]] = {}
        for model_id, entry in self.catalog["races"].items():
            gender = model_id.rsplit("_", 1)[1]
            by_gender.setdefault(gender, set()).add(
                (entry["hipHeight"], entry["groundHeight"]))
        for gender, heights in by_gender.items():
            with self.subTest(gender=gender):
                self.assertEqual(1, len(heights), heights)

    def test_races_have_distinct_bodies(self) -> None:
        """Eight races must not ship as one silhouette in eight colours."""
        catalog = self.catalog["races"]
        for gender in ("female", "male"):
            with self.subTest(gender=gender):
                signatures = {
                    model_id: (entry["legChainScale"], entry["stature"],
                               entry["vertices"])
                    for model_id, entry in catalog.items()
                    if model_id.rsplit("_", 1)[1] == gender}
                self.assertEqual(8, len(signatures))
                self.assertGreaterEqual(
                    len(set(signatures.values())), 8,
                    "every race body differs from every other")
        # Stature reaches the client through the model registry, because the
        # rig itself has to keep the reference hip height.
        for model_id, entry in catalog.items():
            with self.subTest(model=model_id):
                self.assertAlmostEqual(
                    entry["stature"],
                    self.models["models"][model_id]["import"]["scale"], places=4)

    def test_race_rigs_keep_the_shared_animation_contract(self) -> None:
        """Rest rotations stay as authored so the shared clips still apply.

        Anatomy lives in the joint offsets, never in rest rotations: glTF
        rotation tracks are absolute, so anything stored in a rest rotation is
        overwritten the instant a clip plays.  Guard that by checking every
        race rig carries the same rest rotations as the Luminous reference and
        differs only in translation.
        """
        # The male and female source rigs are different files, so the
        # comparison is per gender.
        for gender in ("female", "male"):
            reference = None
            for model_id, entry in sorted(self.catalog["races"].items()):
                if model_id.rsplit("_", 1)[1] != gender:
                    continue
                document = glb_document(ROOT / entry["path"])
                joints = document["skins"][0]["joints"]
                names = [document["nodes"][node].get("name") for node in joints]
                rotations = [tuple(round(value, 6) for value in
                                   document["nodes"][node].get("rotation", (0, 0, 0, 1)))
                             for node in joints]
                translations = [tuple(round(value, 6) for value in
                                      document["nodes"][node].get("translation", (0, 0, 0)))
                                for node in joints]
                if reference is None:
                    reference = (names, rotations, translations)
                    continue
                with self.subTest(model=model_id):
                    self.assertEqual(reference[0], names)
                    self.assertEqual(reference[1], rotations,
                                     "rest rotations stay as the clips expect")
                    self.assertNotEqual(reference[2], translations,
                                        "races differ in bone offsets")

    def test_native_hair_is_authored_geometry_in_head_local_space(self) -> None:
        for hair_id, entry in self.catalog["hair"].items():
            with self.subTest(hair=hair_id):
                document = glb_document(ROOT / entry["path"])
                self.assertEqual([], document.get("skins", []))
                self.assertGreater(entry["vertices"], 400)
                self.assertLess(entry["bounds"]["min"][1], .12)
                self.assertLess(entry["bounds"]["max"][1], .31)

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

    def test_nymara_invasion_actor_types_resolve_to_native_models(self) -> None:
        self.assertEqual(set(range(400, 428)), set(NYMARA_INVASION_MODELS))
        for actor_type, (creature_type, model_id) in NYMARA_INVASION_MODELS.items():
            with self.subTest(actor_type=actor_type, creature=creature_type):
                self.assertEqual(model_id, self.models["actorTypes"][str(actor_type)])
                model = self.models["models"][model_id]
                scene = CLIENT / model["scene"].removeprefix("res://")
                document = glb_document(scene)
                self.assertTrue(document.get("meshes"), model_id)
                self.assertTrue(document.get("animations"), model_id)

    def test_every_equipment_visual_is_registered(self) -> None:
        expected = {f"{entry['part']}:{entry['visual']}"
                    for entry in self.catalog["equipment"].values()}
        self.assertEqual(expected, set(self.equipment["models"]))
        for entry in self.catalog["equipment"].values():
            glb_document(ROOT / entry["path"])

    def test_legacy_guard_visuals_alias_to_native_models(self) -> None:
        expected = {
            "0:11": "0:112",
            "1:5": "1:105",
            "2:11": "2:105",
        }
        self.assertEqual(expected, self.equipment["aliases"])
        for native_visual in expected.values():
            self.assertIn(native_visual, self.equipment["models"])

    def test_every_playable_actor_type_has_creation_option(self) -> None:
        options = self.models["creationOptions"]
        self.assertEqual(16, len(options))
        for option in options:
            actor_type = str(option["actorType"])
            self.assertEqual(option["model"], self.models["actorTypes"][actor_type])
            self.assertIn(option["model"], self.models["models"])

    def test_model_resources_stay_inside_godot_project(self) -> None:
        for model_id, entry in self.models["models"].items():
            with self.subTest(model=model_id):
                for field in ("scene", "animationLibrary", "animationMap"):
                    resource = entry.get(field)
                    if not resource:
                        continue
                    self.assertTrue(resource.startswith("res://"), resource)
                    relative = resource.removeprefix("res://")
                    self.assertNotIn("..", Path(relative).parts, resource)
                    path = CLIENT / relative
                    self.assertTrue(path.is_file(), resource)
                    if path.suffix == ".gltf":
                        document = json.loads(path.read_text())
                        for dependency in [
                            *(buffer["uri"] for buffer in document.get("buffers", []) if "uri" in buffer),
                            *(image["uri"] for image in document.get("images", []) if "uri" in image),
                        ]:
                            self.assertTrue((path.parent / dependency).is_file(), dependency)
                for resource in entry.get("hairStyles", []):
                    self.assertTrue(resource.startswith("res://"), resource)
                    self.assertTrue((CLIENT / resource.removeprefix("res://")).is_file(), resource)

    def test_runtime_does_not_synthesize_placeholder_hair(self) -> None:
        source = (CLIENT / "src/actors/replicated_actor_3d.gd").read_text()
        self.assertNotIn("func _hair_piece", source)
        self.assertIn('native_hair.name = "NativeHair"', source)
        self.assertIn('model_config.get("hairStyles"', source)

    def test_character_preview_uses_player_model_registry(self) -> None:
        source = (CLIENT / "src/app/main.gd").read_text()
        start = source.index("func _refresh_creation_preview()")
        end = source.index("func _on_login_pressed()", start)
        preview = source[start:end]
        self.assertIn('"kind": 1', preview)
        for option in self.models["creationOptions"]:
            self.assertEqual(
                option["model"],
                self.models["actorTypes"][str(option["actorType"])])

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

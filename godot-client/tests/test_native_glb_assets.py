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
        self.assertEqual(123, self.catalog["validation"]["files"])

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
                self.assertGreaterEqual(entry["vertices"], 13_500)
                self.assertLess(entry["vertices"], 14_500)
                document = glb_document(ROOT / entry["path"])
                self.assertEqual(65, len(document["skins"][0]["joints"]))
                mesh_names = {mesh["name"] for mesh in document["meshes"]}
                self.assertTrue({"Eyebrows", "Eyes", "Body", "Wardrobe_Shirt",
                                 "Wardrobe_Pants", "Wardrobe_Boots"} <= mesh_names)

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

    def test_equipment_registry_is_schema_three(self) -> None:
        """Sockets and skinned garments replace the identity bone parenting.

        Schema 2 attached every piece to a raw bone with an identity transform.
        Bone rest bases are not axis aligned, so that alone put weapons through
        the actor sideways; the registry now has to carry a socket per rigid
        part and a skin region per garment.
        """
        self.assertEqual(3, self.equipment["schemaVersion"])
        rig = glb_document(CLIENT / "assets/actors/native/races/luminous_male.glb")
        joints = {rig["nodes"][node].get("name", "")
                  for node in rig["skins"][0]["joints"]}
        head = next(node for node in rig["nodes"] if node.get("name") == "Head")
        self.assertIn("canonicalHeadRestY", self.equipment)
        self.assertGreater(float(self.equipment["canonicalHeadRestY"]), 1.0)
        for part, socket in self.equipment["sockets"].items():
            with self.subTest(part=part):
                self.assertIn(socket["bone"], joints)
                self.assertEqual(3, len(socket["offset"]))
                self.assertEqual(3, len(socket["rotationDegrees"]))
        for region, bones in self.equipment["skinRegions"].items():
            with self.subTest(region=region):
                self.assertTrue(bones)
                self.assertTrue(set(bones) <= joints)
        del head

    def test_boots_follow_both_feet(self) -> None:
        """Boots used to hang off the pelvis, which parked them at the hips."""
        self.assertEqual("feet", self.equipment["parts"]["6"]["attachment"])
        feet = self.models["models"]["luminous_male"]["attachments"]["feet"]
        self.assertEqual(["foot_l", "foot_r"], feet)

    def test_socketed_props_and_skinned_garments_are_declared(self) -> None:
        garment_parts = {2, 4, 5, 6}
        for key, model in self.equipment["models"].items():
            part = int(key.split(":")[0])
            with self.subTest(model=key):
                if part in garment_parts:
                    self.assertEqual("skinned", model["attach"])
                    self.assertIn(model["skinRegion"], self.equipment["skinRegions"])
                else:
                    self.assertEqual("socket", model["attach"])
                    socket = model.get("socket") or self.equipment["sockets"][str(part)]
                    self.assertTrue(socket["bone"])

    def test_garments_ship_skinned_to_the_shared_rig(self) -> None:
        """A garment bolted to one bone cannot bend; these carry skin weights."""
        rig = glb_document(CLIENT / "assets/actors/native/races/luminous_male.glb")
        expected = [rig["nodes"][node].get("name", "")
                    for node in rig["skins"][0]["joints"]]
        garment_parts = {2, 4, 5, 6}
        checked = 0
        for entry in self.catalog["equipment"].values():
            if entry["part"] not in garment_parts:
                self.assertEqual("socket", entry["attach"])
                continue
            with self.subTest(equipment=entry["id"]):
                self.assertEqual("skinned", entry["attach"])
                document = glb_document(ROOT / entry["path"])
                skin = document["skins"][0]
                names = [document["nodes"][node].get("name", "")
                         for node in skin["joints"]]
                self.assertEqual(expected, names)
                for mesh in document["meshes"]:
                    for primitive in mesh["primitives"]:
                        self.assertIn("JOINTS_0", primitive["attributes"])
                        self.assertIn("WEIGHTS_0", primitive["attributes"])
                checked += 1
        self.assertEqual(31, checked)

    def test_equipment_hides_name_real_body_surfaces(self) -> None:
        """A hide that names nothing would silently fail to cover anything."""
        rig = glb_document(CLIENT / "assets/actors/native/races/luminous_male.glb")
        surfaces = {mesh.get("name", "").lower() for mesh in rig["meshes"]}
        surfaces.add("hair")
        for part, config in self.equipment["parts"].items():
            for surface in config.get("hides", []):
                with self.subTest(part=part, surface=surface):
                    self.assertIn(surface, surfaces)
        for key, model in self.equipment["models"].items():
            for surface in model.get("hides", []):
                with self.subTest(model=key, surface=surface):
                    self.assertIn(surface, surfaces)
        self.assertEqual(["wardrobe_shirt", "wardrobe_shirt_trim"],
                         self.equipment["parts"]["5"]["hides"])

    def test_equipment_is_authored_at_body_scale(self) -> None:
        """The first pass shipped helmets and amulets at three to five times
        body scale, which swallowed the actor wearing them."""
        limits = {0: (.55, 2.00), 1: (.35, .95), 2: (.80, 1.60), 3: (.18, .60),
                  4: (.60, 1.30), 5: (.45, 1.60), 6: (.30, .70), 7: (.10, .40)}
        for entry in self.catalog["equipment"].values():
            document = glb_document(ROOT / entry["path"])
            extents = []
            for accessor in document["accessors"]:
                if "min" in accessor and len(accessor["min"]) == 3:
                    extents.append(max(high - low for low, high
                                       in zip(accessor["min"], accessor["max"])))
            low, high = limits[entry["part"]]
            with self.subTest(equipment=entry["id"]):
                self.assertTrue(extents, entry["id"])
                self.assertGreaterEqual(max(extents), low)
                self.assertLessEqual(max(extents), high)

    def test_equipment_carries_material_detail(self) -> None:
        """Equipment shipped untextured beside a body with fifteen maps."""
        for entry in self.catalog["equipment"].values():
            document = glb_document(ROOT / entry["path"])
            with self.subTest(equipment=entry["id"]):
                self.assertGreaterEqual(len(document.get("materials", [])), 2)
                self.assertTrue(document.get("images"))
                for material in document["materials"]:
                    self.assertIn("normalTexture", material)
                self.assertGreaterEqual(entry["triangles"], 240)

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

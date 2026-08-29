#!/usr/bin/env python3
"""Structural checks for the clean Nymara GLB asset library."""
from __future__ import annotations

import json
from pathlib import Path
import struct
import sys
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


def glb_chunks(path: Path) -> tuple[dict, bytes]:
    """The JSON document and the binary chunk of a GLB."""
    raw = path.read_bytes()
    size, _ = struct.unpack_from("<II", raw, 12)
    offset = 20 + size
    length, _ = struct.unpack_from("<II", raw, offset)
    return json.loads(raw[20:20 + size]), raw[offset + 8:offset + 8 + length]


def body_bounds(path: Path) -> tuple[float, float, float]:
    """(min y, lowest vertex, z extent) of a race GLB's Body mesh.

    Taken from the POSITION accessor's declared bounds, so this needs no
    binary decoding.
    """
    document = glb_document(path)
    mesh = next(m for m in document["meshes"] if m["name"] == "Body")
    spec = document["accessors"][mesh["primitives"][0]["attributes"]["POSITION"]]
    return spec["max"][1], spec["min"][1], spec["max"][2] - spec["min"][2]


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


def bone_translations(path: Path) -> dict[str, list[float]]:
    """Every skinned bone's rest translation, by name."""
    document = glb_document(path)
    return {document["nodes"][joint].get("name"):
            document["nodes"][joint].get("translation") or [0.0, 0.0, 0.0]
            for joint in document["skins"][0]["joints"]}


class NativeGlbAssetsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads((CLIENT / "data/actors/native_asset_catalog.json").read_text())
        cls.models = json.loads((CLIENT / "data/actors/models.json").read_text())
        cls.equipment = json.loads((CLIENT / "data/actors/equipment.json").read_text())

    def test_catalog_is_complete(self) -> None:
        # Eight retargeted races plus the from-scratch Human, two builds each.
        self.assertEqual(18, len(self.catalog["races"]))
        self.assertEqual(8, len(self.catalog["hair"]))
        # 32 first-pass creatures plus the wider concept-art roster.
        sys.path.insert(0, str(ROOT / "eloria-assets" / "tools"))
        import creature_roster
        self.assertEqual(32 + len(creature_roster.ROSTER),
                         len(self.catalog["creatures"]))
        self.assertEqual(66, len(self.catalog["equipment"]))
        # The generic tier claims the legacy visual-id space with one authored
        # mesh per material ladder rather than one per id.
        self.assertEqual(43, len(self.catalog["genericEquipment"]))
        # Compare against what is actually on disk instead of a fixed number:
        # the catalogue's count had drifted stale when the ambient livestock
        # were added by a second generator without refreshing this block.
        on_disk = len(list((CLIENT / "assets/actors/native").rglob("*.glb")))
        self.assertEqual(on_disk, self.catalog["validation"]["files"])
        # The catalogue records POSIX-form paths on every platform, so compare
        # in that form: str() on a Windows path yields backslashes and made
        # this assertion fail on Windows builds alone.
        self.assertEqual(sorted(self.catalog["validation"]["results"]),
                         sorted(path.relative_to(ROOT).as_posix()
                                for path in (CLIENT / "assets/actors/native").rglob("*.glb")))

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
                ambient_bones = [document["nodes"][j].get("name")
                                 for j in document["skins"][0]["joints"]]
                for required in ("root", "body", "neck", "head"):
                    self.assertIn(required, ambient_bones)

    def test_player_rigs_share_one_skeleton_and_budget(self) -> None:
        """The sixteen races carry one rig, and no body rides a cape bone.

        This used to assert a joint count of 65.  The count was never the
        invariant: nothing in the client indexes a joint positionally -- every
        lookup is `find_bone` or `add_named_bind` by name -- and freezing it
        blocked the cape chains the cloth solver drives.  What has to hold is
        that the rigs are *one* rig, so the shared animation library and every
        skinned garment mean the same thing on all of them.
        """
        skeletons: dict[str, tuple] = {}
        for model_id, entry in self.catalog["races"].items():
            with self.subTest(model=model_id):
                self.assertEqual("skinned", entry["wardrobe"])
                # "retargeted" is the shared base body re-proportioned;
                # "authored" is a race whose geometry was built from nothing.
                # What has to hold is that the race says which it is, because
                # the two are fitted and reviewed differently.
                self.assertIn(entry["anatomy"], {"retargeted", "authored"})
                self.assertGreaterEqual(entry["vertices"], 13_500)
                # The race features (a Ssarathi tail and claws, Stoneborn
                # plating, a gilled Mycelari cap) are what sits above the
                # 13.5k shared body; the ceiling keeps them from growing
                # without anyone noticing.
                self.assertLess(entry["vertices"], 15_750)
                document = glb_document(ROOT / entry["path"])
                joints = document["skins"][0]["joints"]
                self.assertEqual(entry["joints"], len(joints))
                skeletons[model_id] = tuple(
                    document["nodes"][node].get("name") for node in joints)
                mesh_names = {mesh["name"] for mesh in document["meshes"]}
                self.assertTrue({"Eyebrows", "Eyes", "Body", "Wardrobe_Shirt",
                                 "Wardrobe_Pants", "Wardrobe_Boots"} <= mesh_names)
        self.assertEqual(1, len(set(skeletons.values())),
                         "every race has to carry the same skeleton")
        names = list(next(iter(skeletons.values())))
        # The chains the cloth solver owns.  No clip in the shared library
        # names one, which is what makes them safe for a solver to drive.
        for chain in ("l", "c", "r"):
            self.assertEqual(
                [f"cape_{chain}_{link:02d}" for link in range(1, 5)],
                [name for name in names if name.startswith(f"cape_{chain}_")])
        # A cape bone may never move the body: it is driven by a solver, not
        # by a clip, so anything skinned to it would jitter free of the rig.
        first_cape = min(index for index, name in enumerate(names)
                         if name.startswith("cape_"))
        for model_id, entry in self.catalog["races"].items():
            document, binary = glb_chunks(ROOT / entry["path"])
            for mesh in document["meshes"]:
                if mesh["name"].startswith("Integrated_"):
                    continue
                for primitive in mesh["primitives"]:
                    spec = document["accessors"][primitive["attributes"]["JOINTS_0"]]
                    view = document["bufferViews"][spec["bufferView"]]
                    start = view.get("byteOffset", 0) + spec.get("byteOffset", 0)
                    width = 2 if spec["componentType"] == 5123 else 1
                    raw = binary[start:start + spec["count"] * 4 * width]
                    highest = max(int.from_bytes(raw[i:i + width], "little")
                                  for i in range(0, len(raw), width))
                    with self.subTest(model=model_id, mesh=mesh["name"]):
                        self.assertLess(highest, first_cape)

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
                self.assertEqual(9, len(signatures))
                self.assertGreaterEqual(
                    len(set(signatures.values())), 9,
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

    def test_race_features_carry_material_detail(self) -> None:
        """Race features shipped flat beside a body with fifteen maps.

        The integrated feature and accent materials were the only ones on a
        player carrying no textures at all -- a base colour factor next to a
        body with albedo, normal and metallic-roughness maps -- which is what
        made scale, stone and fungus read as plastic under real lighting.
        """
        for model_id, entry in self.catalog["races"].items():
            if entry["feature"] == "none":
                continue
            document = glb_document(ROOT / entry["path"])
            integrated = [material for material in document["materials"]
                          if "Integrated" in material["name"]]
            self.assertEqual(2, len(integrated), model_id)
            for material in integrated:
                with self.subTest(model=model_id, material=material["name"]):
                    pbr = material["pbrMetallicRoughness"]
                    self.assertIn("baseColorTexture", pbr)
                    self.assertIn("metallicRoughnessTexture", pbr)
                    self.assertIn("normalTexture", material)
                    # With maps supplied the factors must not scale them too.
                    self.assertEqual(1.0, pbr["metallicFactor"])
                    self.assertEqual(1.0, pbr["roughnessFactor"])

    def test_wardrobe_carries_material_detail(self) -> None:
        """The default wardrobe answers a light like cloth, leather and metal.

        Every garment material had an albedo and nothing else, so all three
        responded to a light identically, and the metal trim -- a flat
        metallic factor with no roughness break anywhere -- blew out into a
        solid highlight wherever it caught the key.
        """
        for model_id, entry in self.catalog["races"].items():
            document = glb_document(ROOT / entry["path"])
            garments = [material for material in document["materials"]
                        if any(part in material["name"] for part in
                               ("Shirt", "Pants", "Boots", "Headwear"))]
            self.assertTrue(garments, model_id)
            for material in garments:
                with self.subTest(model=model_id, material=material["name"]):
                    self.assertIn("normalTexture", material)
                    self.assertIn("metallicRoughnessTexture",
                                  material["pbrMetallicRoughness"])

    def test_human_cultures_are_not_one_physique(self) -> None:
        """More than one base body is in use across the five human cultures.

        Every rig used to derive from the one Quaternius "Superhero" mesh, so
        the human cultures differed in stature and tint but were the same
        heroic build underneath.
        """
        human = {"luminous", "votary", "glasswarden", "orun", "greyhaven",
                 "human"}
        bases = {model_id: entry["baseBody"]
                 for model_id, entry in self.catalog["races"].items()
                 if model_id.rsplit("_", 1)[0] in human}
        self.assertEqual(12, len(bases))
        self.assertGreaterEqual(len(set(bases.values())), 3, bases)
        for gender in ("female", "male"):
            self.assertEqual("slim", bases[f"glasswarden_{gender}"])
            self.assertEqual("heroic", bases[f"luminous_{gender}"])
            # The scratch-built race shares no geometry with the others at all.
            self.assertEqual("human-scratch", bases[f"human_{gender}"])

    def test_slim_base_body_is_a_reproportioning_not_a_scale(self) -> None:
        """The slim body thins different places by different amounts.

        A uniform shrink would be a smaller heroic body, which is what the
        `girth` multiplier it replaced could express and the reason it was
        replaced.  The builder publishes a measured girth per joint for the
        equipment fitter, so the shape of the change is checkable directly.
        """
        girth = self.equipment["bodyGirth"]
        for gender in ("female", "male"):
            reference = girth[f"luminous_{gender}"]
            slim = girth[f"glasswarden_{gender}"]
            reductions = {}
            for joint in ("spine_02", "spine_03", "clavicle_l", "upperarm_l",
                          "lowerarm_l", "thigh_l", "calf_l", "pelvis"):
                with self.subTest(gender=gender, joint=joint):
                    self.assertLess(slim[joint], reference[joint])
                reductions[joint] = 1. - slim[joint] / reference[joint]
            with self.subTest(gender=gender):
                # The arm loses far more than the pelvis does: mass comes off
                # the chest and limbs, not off the whole body evenly.
                self.assertGreater(reductions["upperarm_l"],
                                   reductions["pelvis"] * 1.5)

    def test_slim_base_body_keeps_the_reference_ground_plane(self) -> None:
        """The slim body scales across the bones, never along them.

        Garment cuts are chosen at absolute heights and the leg chain is
        solved to a fixed ground contact, so a base body that shortened or
        lifted the mesh would move a hem or float the feet.  The foot is left
        out of the field entirely and the lowest vertex has to prove it.
        """
        for gender in ("female", "male"):
            reference = body_bounds(ROOT / self.catalog["races"]
                                    [f"luminous_{gender}"]["path"])
            slim = body_bounds(ROOT / self.catalog["races"]
                               [f"glasswarden_{gender}"]["path"])
            with self.subTest(gender=gender):
                self.assertAlmostEqual(reference[1], slim[1], places=3)

    def test_race_eyes_are_not_all_the_human_one(self) -> None:
        """A round mammalian pupil sat inside a reptile muzzle on every race."""
        eyes = {}
        for model_id, entry in self.catalog["races"].items():
            document, binary = glb_chunks(ROOT / entry["path"])
            material = next(m for m in document["materials"]
                            if m["name"].endswith(" Eyes"))
            index = material["pbrMetallicRoughness"]["baseColorTexture"]["index"]
            image = document["images"][document["textures"][index]["source"]]
            view = document["bufferViews"][image["bufferView"]]
            start = view.get("byteOffset", 0)
            eyes[model_id] = binary[start:start + view["byteLength"]]
        for gender in ("female", "male"):
            human = eyes[f"luminous_{gender}"]
            for race in ("ssarathi", "stoneborn", "mycelari"):
                with self.subTest(model=f"{race}_{gender}"):
                    self.assertNotEqual(human, eyes[f"{race}_{gender}"])
            # The human cultures still share one eye, so this stays a race
            # treatment rather than sixteen unrelated textures.
            self.assertEqual(human, eyes[f"greyhaven_{gender}"])

    def test_optional_headwear_skips_races_it_would_intersect(self) -> None:
        """Headwear is cut from the scalp, so it clips a race's own head.

        A Mycelari cap has nowhere to put a hat, and a skullcap runs through
        Votary horns and the Ssarathi crest.
        """
        expected = {"luminous": {"Wardrobe_Head_Band", "Wardrobe_Head_Cap"},
                    "orun": {"Wardrobe_Head_Band", "Wardrobe_Head_Cap"},
                    "greyhaven": {"Wardrobe_Head_Band", "Wardrobe_Head_Cap"},
                    "votary": {"Wardrobe_Head_Band"},
                    "glasswarden": {"Wardrobe_Head_Cap"},
                    "ssarathi": set(), "stoneborn": set(), "mycelari": set(),
                    "human": {"Wardrobe_Head_Band", "Wardrobe_Head_Cap"}}
        for model_id, entry in self.catalog["races"].items():
            race = model_id.rsplit("_", 1)[0]
            document = glb_document(ROOT / entry["path"])
            present = {mesh["name"] for mesh in document["meshes"]
                       if mesh["name"].startswith("Wardrobe_Head_")}
            with self.subTest(model=model_id):
                self.assertEqual(expected[race], present)

    def test_native_hair_is_authored_geometry_in_head_local_space(self) -> None:
        for hair_id, entry in self.catalog["hair"].items():
            with self.subTest(hair=hair_id):
                document = glb_document(ROOT / entry["path"])
                self.assertEqual([], document.get("skins", []))
                self.assertGreater(entry["vertices"], 400)
                self.assertLess(entry["bounds"]["min"][1], .12)
                self.assertLess(entry["bounds"]["max"][1], .31)

    def test_creatures_have_new_rigs_and_embedded_clips(self) -> None:
        """Assert the runtime rig contract rather than a fixed bone count.

        The bone count is an authoring detail and grew when the creatures were
        rebuilt with articulated tails and a chest bone.  What the client
        actually depends on is the attachment bone names, a single root, and
        the exact clip names named by data/animations/creature.json - so those
        are what this test pins.
        """
        sys.path.insert(0, str(ROOT / "eloria-assets" / "tools"))
        import creature_roster
        # The concept-art roster occupies one contiguous block after every
        # range already in models.json; the server adopts these ids.
        expected_actor_types = set(range(204, 236)) | set(
            range(428, 428 + len(creature_roster.ROSTER)))
        actual_actor_types = {entry["actor_type"] for entry in self.catalog["creatures"].values()}
        self.assertEqual(expected_actor_types, actual_actor_types)
        animation_map = json.loads(
            (CLIENT / "data/animations/creature.json").read_text())
        required_clips = set(animation_map["actions"].values())
        for slug, entry in self.catalog["creatures"].items():
            with self.subTest(creature=slug):
                document = glb_document(ROOT / entry["path"])
                skin = document["skins"][0]
                bone_names = [document["nodes"][j].get("name") for j in skin["joints"]]
                self.assertEqual(len(bone_names), len(set(bone_names)),
                                 "bone names are unique")
                for required in ("root", "body", "neck", "head", "jaw"):
                    self.assertIn(required, bone_names)
                self.assertLessEqual(len(skin["joints"]), 64,
                                     "creature rigs stay within a sane bone budget")
                parented = {c for node in document["nodes"]
                            for c in node.get("children", [])}
                roots = [j for j in skin["joints"] if j not in parented]
                self.assertEqual(1, len(roots), "exactly one root bone")
                clips = {a["name"] for a in document["animations"]}
                self.assertTrue(required_clips.issubset(clips),
                                f"missing {sorted(required_clips - clips)}")
                self.assertEqual(slug, self.models["actorTypes"][str(entry["actor_type"])])

    def test_creature_glbs_pass_structural_validation(self) -> None:
        """Skinning, grounding and animation checks over the checked-in GLBs."""
        try:
            import numpy  # noqa: F401
        except ImportError:  # pragma: no cover - environment without numpy
            self.skipTest("numpy is required for skinned animation validation")
        sys.path.insert(0, str(ROOT / "eloria-assets" / "tools"))
        import validate_creature_glbs as validator

        animation_map = json.loads(
            (CLIENT / "data/animations/creature.json").read_text())
        required_clips = sorted(set(animation_map["actions"].values()))
        attachments = sorted({bone for model in self.models["models"].values()
                              if str(model.get("animationMap", "")).endswith("creature.json")
                              for bone in model.get("attachments", {}).values()})
        entries = dict(self.catalog["creatures"])
        entries.update(self.catalog.get("ambientCreatures", {}))
        for slug, entry in entries.items():
            with self.subTest(creature=slug):
                path = ROOT / entry["path"]
                document, binary = validator.read_glb(path)
                problems, _ = validator.check(document, binary, path,
                                              required_clips, attachments,
                                              bool(entry.get("hovers")))
                self.assertEqual([], problems)

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
        for entry in self.catalog["genericEquipment"].values():
            expected |= {f"{entry['part']}:{visual}" for visual in entry["visuals"]}
        self.assertEqual(expected, set(self.equipment["models"]))
        for entry in self._all_equipment():
            glb_document(ROOT / entry["path"])

    def _all_equipment(self):
        return list(self.catalog["equipment"].values()) + list(
            self.catalog["genericEquipment"].values())

    def test_legacy_visual_ids_render_as_themselves(self) -> None:
        """The alias table existed only because the legacy tier had no models.

        Weapon 11, shield 5 and cape 11 were redirected to Four Gates guard gear.
        They are STAFF_4, SHIELD_BRONZE and CAPE_GOLD, so with the generic tier
        authored an alias would hijack three ids every actor can legitimately
        wear. Bespoke NPC gear comes from npcLooks, which names native ids.
        """
        self.assertEqual({}, self.equipment["aliases"])
        for legacy in ("0:11", "1:5", "2:11"):
            self.assertIn(legacy, self.equipment["models"])
        for native in ("0:112", "1:105", "2:105"):
            self.assertIn(native, self.equipment["models"])
        guard_look = self.models["npcLooks"]["301"]["equipmentVisuals"]
        self.assertEqual({"0": 112, "1": 105, "2": 105}, guard_look)

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
                # Gloves are worn on the weapon part but cover both hands, so
                # attachment is declared per model, not inferred from the part.
                if part in garment_parts:
                    self.assertEqual("skinned", model["attach"])
                if model["attach"] == "skinned":
                    self.assertIn(model["skinRegion"], self.equipment["skinRegions"])
                else:
                    socket = model.get("socket") or self.equipment["sockets"][str(part)]
                    self.assertTrue(socket["bone"])

    def test_garments_ship_skinned_to_the_shared_rig(self) -> None:
        """A garment bolted to one bone cannot bend; these carry skin weights."""
        rig = glb_document(CLIENT / "assets/actors/native/races/luminous_male.glb")
        expected = [rig["nodes"][node].get("name", "")
                    for node in rig["skins"][0]["joints"]]
        checked = 0
        for entry in self._all_equipment():
            if entry["attach"] != "skinned":
                continue
            with self.subTest(equipment=entry["id"]):
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
        self.assertEqual(47, checked)

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
        for entry in self._all_equipment():
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
        for entry in self._all_equipment():
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

    def test_every_rig_declares_the_correction_its_facing_needs(self) -> None:
        """A model's forward-axis correction must match how its rig is built.

        The two families are authored facing opposite ways.  The race rigs
        look down +Z, at the creation-preview camera, so their visual root
        needs a half turn onto Godot's -Z forward.  The creature rigs are
        built muzzle-first down -Z and already face that way, so the same
        half turn would spin every creature round and walk it backwards --
        which is exactly what a blanket 180 default did to all 175 of them.

        Neither family may rely on that default, so the direction is read
        back off the rig itself: a cape hangs behind a race, and a jaw sits
        in front of a creature.
        """
        for model_id, entry in self.models["models"].items():
            scene = entry["scene"].removeprefix("res://")
            with self.subTest(model=model_id):
                bones = bone_translations(CLIENT / scene)
                if "/races/" in scene:
                    # The cape hangs off the back, so the back is whichever
                    # way its anchor points and the face is the other way.
                    facing = -bones["cape_c_01"][2]
                else:
                    facing = bones["jaw"][2]
                self.assertNotEqual(0.0, facing, "the rig states a facing")
                correction = entry["import"]["forwardAxisCorrectionDegreesY"]
                self.assertEqual(180 if facing > 0 else 0, correction,
                                 "a rig already facing -Z must not be turned")

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

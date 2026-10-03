#!/usr/bin/env python3
"""The models the client stands on server-declared world objects.

Added 2026-08-29 for Eloria Client.

`ELORIA_MAP_OBJECTS` names a harvest node by its resource label and an
interactive by the label the server derives from its role, and nothing else.
Those two strings are therefore the whole contract between the two repositories
for what a world object looks like, and a resource whose label the registry
does not carry falls back to a bare ring on the ground - which is what the
whole harvestable layer did before the registry existed.

This reads the registry the asset generator writes, checks every model file it
names is a real GLB, and checks the server's own harvesting profile and
interactive table resolve through it. The server repository is optional: the
model-side checks run either way, and the two cross-repository checks skip with
a message rather than failing when it is not checked out beside the client.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CLIENT = Path(__file__).resolve().parents[1]
REGISTRY = CLIENT / "data/world/objects.json"
TOOLS = CLIENT.parent / "eloria-assets" / "tools"
GENERATOR = TOOLS / "build_native_world_object_glbs.py"
# The imported-model table and the bands it is held to. Imported once, here,
# so every check below reads the same table the generator writes from.
sys.path.insert(0, str(TOOLS))
import imported_world_objects as imported  # noqa: E402
# The server repository beside this one. The main checkouts are `eloria-client`
# and `eloria-server`, but a feature is usually worked in a pair of worktrees
# named `<something>` and `<something>-server`, and this test was silently
# reading the main checkout from whatever branch it happened to be on - so a
# rename made in the pair looked like a client that had lost its models.
NEIGHBOURS = CLIENT.parents[1]
SERVER_CANDIDATES = (NEIGHBOURS / (CLIENT.parents[0].name + "-server"),
                     NEIGHBOURS / "eloria-server")
# The interactive roles the server can state. `map_object_entries` sends
# `role.replace("_", " ").title()`, so this is the label as well as the role.
ROLE_LABEL = re.compile(r"^[a-z_]+$")


def server_root() -> Path | None:
    configured = os.environ.get("ELORIA_SERVER_ROOT")
    if configured:
        root = Path(configured).resolve()
        if not (root / "config/eloria/harvesting.txt").is_file():
            raise ValueError(f"ELORIA_SERVER_ROOT is not an Eloria server: {root}")
        return root
    for candidate in SERVER_CANDIDATES:
        if (candidate / "config/eloria/harvesting.txt").is_file():
            return candidate
    return None


def glb_triangle_count(path: Path) -> int:
    """Triangles the GLB's default scene draws.

    The generator's own count, so the registry and this check cannot define a
    triangle differently (a mesh instanced twice, a primitive with no index
    list) and disagree about a model neither got wrong.
    """
    return imported.triangle_count(path)


class WorldObjectModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        cls.harvestables = cls.registry["harvestables"]
        cls.interactives = cls.registry["interactives"]

    def test_every_declared_model_is_a_real_glb(self) -> None:
        for section in (self.harvestables, self.interactives):
            for model_id, entry in section["models"].items():
                with self.subTest(model=model_id):
                    scene = entry["scene"]
                    self.assertTrue(scene.startswith("res://"), scene)
                    path = CLIENT / scene.removeprefix("res://")
                    self.assertTrue(path.is_file(), f"{scene} is missing")
                    self.assertEqual(entry["triangles"],
                                     glb_triangle_count(path))

    def test_models_stay_inside_the_authored_triangle_band(self) -> None:
        """The band the surrounding regional landmark kit occupies.

        A node the player walks up to and stares at through a harvest loop is
        held to the refined kit's budget, not to the placeholder budget the
        bootstrap scenery was built at. A modelled node imported from the
        reviewed kits has the wider band the owner set for them, and only a
        model the imported table lists may use it.
        """
        listed = {row.model_id for row in imported.IMPORTED_HARVESTABLES}
        for section in (self.harvestables, self.interactives):
            for model_id, entry in section["models"].items():
                with self.subTest(model=model_id):
                    wide = section is self.harvestables and model_id in listed
                    low, high = (imported.IMPORTED_TRIANGLE_BAND if wide
                                 else imported.PROCEDURAL_TRIANGLE_BAND)
                    self.assertGreaterEqual(entry["triangles"], low)
                    self.assertLessEqual(entry["triangles"], high)

    def test_the_imported_band_is_the_one_the_owner_set(self) -> None:
        """About 2,600 triangles for imported nodes (2026-10-02, item 17)."""
        self.assertEqual(imported.IMPORTED_TRIANGLE_BAND, (90, 2600))
        self.assertEqual(imported.PROCEDURAL_TRIANGLE_BAND, (90, 424))

    def test_imported_models_are_exactly_the_imported_table(self) -> None:
        """Each imported entry is the table's row, measured off its own file.

        A model claiming `imported` without a row would take the wide band on
        its own say-so, and a GLB swapped in without regenerating the registry
        would draw something other than what the registry measured.
        """
        claimed = {model_id for model_id, entry in self.harvestables["models"].items()
                   if entry.get("imported")}
        rows = {row.model_id: row for row in imported.IMPORTED_HARVESTABLES}
        self.assertEqual(claimed, set(rows))
        for model_id, row in rows.items():
            with self.subTest(model=model_id):
                entry = self.harvestables["models"][model_id]
                path = CLIENT / entry["scene"].removeprefix("res://")
                measured = imported.measure_glb(path)
                for key, value in measured.items():
                    self.assertEqual(entry[key], value, key)
                self.assertEqual((entry["label"], entry["kind"], entry["tier"]),
                                 (row.label, row.kind, row.tier))
                answered = self.harvestables["resources"].get(row.label)
                if row.answers_label:
                    self.assertEqual(answered, model_id,
                                     f"{row.label} should resolve to {model_id}")
                else:
                    self.assertNotEqual(answered, model_id,
                                        f"{row.label} is not swapped to {model_id} yet")

    def test_a_swapped_label_keeps_the_model_it_replaced(self) -> None:
        """The procedural model a swap displaces stays registered and on disk.

        Map packages bake that geometry into their own scenery, and undoing the
        swap is the row's flag plus a regeneration.
        """
        for model_id, entry in self.harvestables["models"].items():
            if "replaces" not in entry:
                continue
            with self.subTest(model=model_id):
                replaced = entry["replaces"]
                self.assertIn(replaced, self.harvestables["models"])
                self.assertFalse(self.harvestables["models"][replaced].get("imported"))
                self.assertEqual(self.harvestables["models"][replaced]["label"],
                                 entry["label"])

    def test_imported_models_are_graded_to_the_procedural_kit(self) -> None:
        """No imported node draws far brighter, or darker, than its peer.

        Every procedural node multiplies its texture by a palette colour; a
        model textured elsewhere has none until it is graded, and the first
        Meshy nodes drew 2-4 times brighter than the models they replaced -
        chalk-white flint, white sage - which only the in-game shots showed.
        Each row names the procedural model it was graded against, and its
        mean surface albedo must stay inside the table's band of that one's.
        """
        try:
            import PIL  # noqa: F401
        except ImportError:
            self.skipTest("Pillow is needed to decode the textures")
        models = self.harvestables["models"]
        low, high = imported.GRADE_RATIO_BAND
        for row in imported.IMPORTED_HARVESTABLES:
            with self.subTest(model=row.model_id):
                self.assertIn(row.graded_against, models)
                self.assertFalse(models[row.graded_against].get("imported"))
                peer = imported.surface_albedo(
                    CLIENT / models[row.graded_against]["scene"].removeprefix("res://"))
                own = imported.surface_albedo(
                    CLIENT / models[row.model_id]["scene"].removeprefix("res://"))
                self.assertGreaterEqual(own / peer, low, f"{own:.3f} against {peer:.3f}")
                self.assertLessEqual(own / peer, high, f"{own:.3f} against {peer:.3f}")

    def test_regenerating_the_registry_keeps_the_imported_models(self) -> None:
        """The generator writes the registry whole; this is what it writes.

        Run it into a scratch client that holds only the imported GLBs, and the
        registry it writes must be the committed one - imported nodes, swapped
        labels and all. Before the imported table existed a regeneration
        silently dropped every model it had not authored itself.
        """
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            for row in imported.IMPORTED_HARVESTABLES:
                source = CLIENT / "assets/world/harvestables" / f"{row.model_id}.glb"
                target = root / "assets/world/harvestables" / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            result = subprocess.run(
                [sys.executable, str(GENERATOR), "--client", str(root)],
                capture_output=True, text=True)
            # The generator's own message says why it stopped (a GLB missing,
            # a band or a shadowed id); a bare exit status would not.
            self.assertEqual(result.returncode, 0, result.stderr)
            written = json.loads((root / "data/world/objects.json").read_text(
                encoding="utf-8"))
        self.assertEqual(written, self.registry)

    def test_models_stand_at_a_human_scale(self) -> None:
        """Metres, not tile units: a reed bed reaches a person's waist."""
        for model_id, entry in self.harvestables["models"].items():
            with self.subTest(model=model_id):
                self.assertGreater(entry["height"], 0.1)
                self.assertLess(entry["height"], 2.0)
        for model_id, entry in self.interactives["models"].items():
            with self.subTest(model=model_id):
                self.assertGreater(entry["height"], 0.5)
                self.assertLess(entry["height"], 4.0)

    def test_every_label_resolves_to_a_declared_model(self) -> None:
        for section, key in ((self.harvestables, "resources"),
                             (self.interactives, "roles")):
            for label, model_id in section[key].items():
                with self.subTest(label=label):
                    self.assertIn(model_id, section["models"])

    def test_every_server_resource_has_a_model(self) -> None:
        root = server_root()
        if root is None:
            self.skipTest("eloria-server is not checked out beside the client")
        resources = [
            line.split("|")[1].strip()
            for line in (root / "config/eloria/harvesting.txt").read_text(
                encoding="utf-8").splitlines()
            if line.startswith("resource")]
        self.assertTrue(resources)
        for resource in resources:
            with self.subTest(resource=resource):
                self.assertIn(resource, self.harvestables["resources"])

    def test_every_server_interactive_role_has_a_model(self) -> None:
        root = server_root()
        if root is None:
            self.skipTest("eloria-server is not checked out beside the client")
        roles = set()
        for line in (root / "config/eloria/interactives.txt").read_text(
                encoding="utf-8").splitlines():
            if line.startswith("#") or "|" not in line:
                continue
            role = line.split("|")[4].strip()
            self.assertRegex(role, ROLE_LABEL)
            roles.add(role.replace("_", " ").title())
        self.assertTrue(roles)
        # A role is answered either by a prop in this registry or by the map
        # package: the secrets are authored into the region mesh as `Secret_*`
        # nodes on the tile the server states, so the client stands nothing on
        # one and draws no ring under it.
        authored = self.interactives.get("mapAuthored", {})
        for label in sorted(roles):
            with self.subTest(role=label):
                self.assertIn(label, set(self.interactives["roles"]) | set(authored))

    def test_a_map_authored_role_has_no_prop_of_its_own(self) -> None:
        """The two ways of answering a role are exclusive.

        A role in both would draw the client's prop on top of the map's, which
        is the failure this whole registry exists to stop.
        """
        authored = self.interactives.get("mapAuthored", {})
        self.assertTrue(authored, "at least the secrets are map-authored")
        self.assertFalse(set(authored) & set(self.interactives["roles"]))
        for label, role in authored.items():
            with self.subTest(role=label):
                self.assertRegex(role, ROLE_LABEL)
                self.assertEqual(role.replace("_", " ").title(), label)
                self.assertNotIn(role, self.interactives["models"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

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
import re
import struct
import unittest
from pathlib import Path

CLIENT = Path(__file__).resolve().parents[1]
REGISTRY = CLIENT / "data/world/objects.json"
SERVER_ROOTS = (
    CLIENT.parents[1] / "eloria-server",
    CLIENT.parents[1] / "wt-actorviz-server",
)
# The interactive roles the server can state. `map_object_entries` sends
# `role.replace("_", " ").title()`, so this is the label as well as the role.
ROLE_LABEL = re.compile(r"^[a-z_]+$")


def server_root() -> Path | None:
    for candidate in SERVER_ROOTS:
        if (candidate / "config/eloria/harvesting.txt").is_file():
            return candidate
    return None


def glb_triangle_count(path: Path) -> int:
    """Parse the GLB header and JSON chunk far enough to count triangles."""
    raw = path.read_bytes()
    magic, version, _total = struct.unpack_from("<4sII", raw)
    assert magic == b"glTF" and version == 2, path
    length, kind = struct.unpack_from("<II", raw, 12)
    assert kind == 0x4E4F534A, f"{path}: first chunk is not JSON"
    document = json.loads(raw[20:20 + length].decode("utf-8"))
    triangles = 0
    for mesh in document["meshes"]:
        for primitive in mesh["primitives"]:
            accessor = document["accessors"][primitive["indices"]]
            triangles += accessor["count"] // 3
    return triangles


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
        bootstrap scenery was built at.
        """
        for section in (self.harvestables, self.interactives):
            for model_id, entry in section["models"].items():
                with self.subTest(model=model_id):
                    self.assertGreaterEqual(entry["triangles"], 90)
                    self.assertLessEqual(entry["triangles"], 424)

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
        for label in sorted(roles):
            with self.subTest(role=label):
                self.assertIn(label, self.interactives["roles"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""The package-time sidecar tool (tools/build_vram_textures.py) and the rule
that the client never compresses a texture itself.

    python3 godot-client/tests/test_build_vram_textures.py -v

The recipe, schema and committed-fixture cases are pure Python. The encode
cases run the tool for real against a copy of tests/fixtures/vram, which needs
the Godot 4.7.2 editor binary (ELORIA_GODOT, the checkout's copy, or `godot`
on PATH) plus numpy and Pillow; without them they skip and say why.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
CLIENT = TESTS.parent
TOOL = CLIENT / "tools" / "build_vram_textures.py"
FIXTURE = TESTS / "fixtures" / "vram"
SIDECARS = FIXTURE / "shared-assets" / "vram"
sys.path.insert(0, str(CLIENT / "tools"))

import build_vram_textures as tool  # noqa: E402


def _godot() -> Path | None:
    try:
        return tool.find_godot(None)
    except tool.BuildError:
        return None


def _imaging() -> str:
    try:
        import numpy  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError as error:
        return str(error)
    return ""


GODOT = _godot()
SKIP_ENCODE = ("no Godot 4.7.2 editor binary (set ELORIA_GODOT)" if GODOT is None
               else (f"numpy/Pillow missing: {_imaging()}" if _imaging() else ""))
FIXTURE_SHAS = set(json.loads((FIXTURE / "world.json").read_text(encoding="utf-8"))["externalResources"].values())


def _run_tool(maps: Path, cache: Path, *extra: str) -> tuple[int, dict, str]:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    if GODOT is not None:
        env["ELORIA_GODOT"] = str(GODOT)
    result = subprocess.run([sys.executable, str(TOOL), "--maps", str(maps), "--cache", str(cache),
                             "--procs", "2", *extra], capture_output=True, text=True, env=env, timeout=900)
    text = result.stdout
    start = text.find("\n{")
    summary = json.loads(text[start:]) if result.returncode == 0 and start >= 0 else {}
    return result.returncode, summary, text + result.stderr


class NoRuntimeCompression(unittest.TestCase):
    """The shipped export template has no BC encoder: Image.compress returns
    ERR_UNAVAILABLE there, so a runtime call would pass every editor-binary
    test and do nothing in the game. Compression belongs to the package tool."""

    def test_client_scripts_never_compress(self):
        pattern = re.compile(r"\.compress\(|compress_from_channels\(")
        offenders = []
        for path in sorted((CLIENT / "src").rglob("*.gd")):
            for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if pattern.search(line.split("#", 1)[0]):
                    offenders.append(f"{path.relative_to(CLIENT).as_posix()}:{number}")
        self.assertEqual(offenders, [], "client code compresses at runtime")


class Recipes(unittest.TestCase):
    def _recipe(self, roles, alpha=False):
        record = {"roles": set(roles), "path": FIXTURE / "world.json"}
        original = tool.alpha_used
        tool.alpha_used = lambda _path: alpha
        try:
            return tool.recipe_for(record)
        finally:
            tool.alpha_used = original

    def test_recipe_per_role(self):
        self.assertEqual(self._recipe({("base", "OPAQUE")}), ("base", ""))
        self.assertEqual(self._recipe({("emissive", "OPAQUE"), ("base", "OPAQUE")}), ("base", ""))
        self.assertEqual(self._recipe({("base", "MASK")}, alpha=True), ("base_alpha", ""))
        self.assertEqual(self._recipe({("base", "BLEND")}, alpha=True), ("base_alpha", ""))
        self.assertEqual(self._recipe({("base", "MASK")}, alpha=False), ("base", ""),
                         "a cutout whose alpha is all opaque needs no alpha channel")
        self.assertEqual(self._recipe({("base", "OPAQUE")}, alpha=True), ("base", ""),
                         "an opaque material never samples alpha")
        self.assertEqual(self._recipe({("orm", "OPAQUE"), ("occlusion", "OPAQUE")}), ("orm", ""))
        self.assertEqual(self._recipe({("normal", "MASK")}), ("normal", ""))

    def test_role_names_are_the_clients(self):
        # vram_textures.gd SLOT_ROLES / image_roles name them the same way.
        self.assertEqual(tool.role_names({("base", "OPAQUE"), ("emissive", "MASK")}), ["base", "emissive"])
        self.assertEqual(tool.role_names({("base", "MASK"), ("base", "BLEND")}), ["base_cutout"])
        self.assertEqual(tool.role_names({("base", "OPAQUE"), ("base", "MASK")}), ["base", "base_cutout"])
        self.assertEqual(tool.role_names({("orm", "OPAQUE"), ("occlusion", "MASK")}), ["occlusion", "orm"])

    def test_conflicts_and_unused_are_excluded(self):
        self.assertEqual(self._recipe({("base", "OPAQUE"), ("normal", "OPAQUE")}),
                         (None, "role_conflict: base+normal"))
        self.assertEqual(self._recipe({("orm", "OPAQUE"), ("base", "OPAQUE")}),
                         (None, "role_conflict: base+orm"))
        self.assertEqual(self._recipe(set()), (None, "no_material_role"))

    def test_fixture_inventory_names_every_role(self):
        found = tool.inventory([FIXTURE])
        self.assertEqual(set(found), FIXTURE_SHAS)
        roles = {sha: {role for role, _ in record["roles"]} for sha, record in found.items()}
        self.assertIn({"orm", "occlusion"}, roles.values())
        self.assertIn({"base", "normal"}, roles.values())
        self.assertIn(set(), roles.values())


class CommittedFixture(unittest.TestCase):
    """The sidecars committed beside the fixture are what the client tests load."""

    def setUp(self):
        self.index = json.loads((SIDECARS / "index.json").read_text(encoding="utf-8"))

    def test_index_schema(self):
        self.assertEqual(self.index["schema"], tool.SCHEMA)
        self.assertEqual(self.index["recipeVersion"], tool.RECIPE_VERSION)
        self.assertEqual(set(self.index["images"]) | set(self.index["excluded"]), FIXTURE_SHAS)
        self.assertEqual({entry["recipe"] for entry in self.index["images"].values()},
                         {"base", "base_alpha", "orm", "normal"})
        for entry in self.index["images"].values():
            self.assertEqual(set(entry), {"file", "recipe", "format", "width", "height", "mipmaps",
                                          "gpuBytes", "rawBytes", "fileBytes", "sha256", "roles"})
            self.assertEqual(entry["format"], tool.FORMAT_OF[entry["recipe"]])
            self.assertEqual(entry["mipmaps"], 6, "64 px carries its whole chain")
        # The roles each encode was chosen for, as the fixture's materials use them.
        self.assertEqual({e["recipe"]: e["roles"] for e in self.index["images"].values()},
                         {"base": ["base"], "base_alpha": ["base_cutout"], "normal": ["normal"],
                          "orm": ["occlusion", "orm"]})

    def test_exclusions_have_reasons(self):
        reasons = sorted(self.index["excluded"].values())
        self.assertEqual(reasons, ["no_material_role", "role_conflict: base+normal", "size_not_multiple_of_4"])

    def test_sidecar_header_and_hash(self):
        for sha, entry in self.index["images"].items():
            data = (SIDECARS / entry["file"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"], entry["file"])
            self.assertEqual(len(data), entry["fileBytes"])
            magic, raw, flags, reserved = tool.HEADER.unpack_from(data)
            self.assertEqual((magic, raw, flags, reserved), (b"EVT1", entry["rawBytes"], tool.FLAG_ZSTD, 0))
            self.assertEqual(data[16:20], b"\x28\xb5\x2f\xfd", "the body is one zstd frame")
            self.assertTrue(entry["file"].startswith(sha))


@unittest.skipIf(SKIP_ENCODE, SKIP_ENCODE or "")
class Build(unittest.TestCase):
    """Runs the tool against a scratch copy of the fixture."""

    @classmethod
    def setUpClass(cls):
        cls.scratch = Path(tempfile.mkdtemp(prefix="vram-build-test-"))
        cls.maps = cls.scratch / "maps"
        shutil.copytree(FIXTURE, cls.maps, ignore=shutil.ignore_patterns("vram", "*.py"))
        cls.cache = cls.scratch / "cache"
        cls.code, cls.summary, cls.output = _run_tool(cls.maps, cls.cache)
        cls.out = cls.maps / "shared-assets" / "vram"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.scratch, ignore_errors=True)

    def _index(self, directory: Path | None = None) -> dict:
        return json.loads(((directory or self.out) / "index.json").read_text(encoding="utf-8"))

    def test_build_matches_the_committed_index(self):
        self.assertEqual(self.code, 0, self.output[-2000:])
        built = self._index()
        committed = json.loads((SIDECARS / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(built["excluded"], committed["excluded"])
        fields = ("file", "recipe", "format", "width", "height", "mipmaps", "gpuBytes", "rawBytes", "roles")
        self.assertEqual({sha: {k: e[k] for k in fields} for sha, e in built["images"].items()},
                         {sha: {k: e[k] for k in fields} for sha, e in committed["images"].items()})
        self.assertEqual(sorted(p.name for p in self.out.glob("*.evt")),
                         sorted(e["file"] for e in built["images"].values()))

    def test_bc1_and_bc5_are_byte_deterministic(self):
        second = self.scratch / "second"
        shutil.copytree(self.maps, second, ignore=shutil.ignore_patterns("vram"))
        code, _, output = _run_tool(second, self.scratch / "cache-second")
        self.assertEqual(code, 0, output[-2000:])
        again = self._index(second / "shared-assets" / "vram")
        for sha, entry in self._index()["images"].items():
            if entry["format"] in ("bc1", "bc5"):
                self.assertEqual(again["images"][sha]["sha256"], entry["sha256"], entry["file"])

    def test_cache_reuse_and_prune(self):
        maps = self.scratch / "prune"
        shutil.copytree(self.maps, maps, ignore=shutil.ignore_patterns("vram"))
        cache = self.scratch / "cache-prune"
        code, first, output = _run_tool(maps, cache)
        self.assertEqual(code, 0, output[-2000:])
        code, again, output = _run_tool(maps, cache)
        self.assertEqual((code, again["encoded"], again["cached"]), (0, 0, first["encoded"]),
                         "a second run encodes nothing")
        # Drop the normal map from the package: its cache entry and its
        # sidecar go stale and are removed.
        manifest_path = maps / "world.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        normal = next(sha for sha, e in self._index()["images"].items() if e["recipe"] == "normal")
        manifest["externalResources"] = {u: s for u, s in manifest["externalResources"].items() if s != normal}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        code, pruned, output = _run_tool(maps, cache)
        self.assertEqual(code, 0, output[-2000:])
        self.assertEqual(pruned["pruned"], 1)
        self.assertFalse(any(cache.glob(normal + ".*")))
        directory = next(iter(pruned["directories"].values()))
        self.assertEqual(directory["staleRemoved"], 1)
        self.assertNotIn(normal, self._index(maps / "shared-assets" / "vram")["images"])

    def test_quality_floor_excludes(self):
        maps = self.scratch / "floors"
        shutil.copytree(self.maps, maps, ignore=shutil.ignore_patterns("vram"))
        # Same cache: the verdict is re-taken from the recorded numbers.
        code, _, output = _run_tool(maps, self.cache, "--no-prune", "--floors",
                                    json.dumps({"base_psnr": 99.0, "normal_mean_deg": 0.0}))
        self.assertEqual(code, 0, output[-2000:])
        out = maps / "shared-assets" / "vram"
        index = self._index(out)
        report = json.loads((out / "report.json").read_text(encoding="utf-8"))
        failed = {sha for sha, e in report.items() if e["recipe"] in ("base", "base_alpha", "normal")}
        self.assertEqual(len(failed), 3)
        self.assertTrue(all(index["excluded"][sha].startswith("quality:") for sha in failed),
                        {sha: index["excluded"].get(sha) for sha in failed})
        self.assertEqual({e["recipe"] for e in index["images"].values()}, {"orm"})

    def test_orm_below_the_bc1_floor_gets_a_bc7_second_chance(self):
        maps = self.scratch / "orm"
        shutil.copytree(self.maps, maps, ignore=shutil.ignore_patterns("vram"))
        report = json.loads((self.out / "report.json").read_text(encoding="utf-8"))
        orm = next(sha for sha, e in report.items() if e["recipe"] == "orm")
        bc1_floor = min(report[orm]["psnr_rgb"]) + 0.5  # just above what BC1 kept
        code, summary, output = _run_tool(maps, self.cache, "--no-prune", "--floors",
                                          json.dumps({"orm_psnr": bc1_floor}))
        self.assertEqual(code, 0, output[-2000:])
        index = self._index(maps / "shared-assets" / "vram")
        entry = index["images"].get(orm, {})
        self.assertEqual((entry.get("recipe"), entry.get("format")), ("orm_bc7", "bc7"),
                         index["excluded"].get(orm))
        code, _, output = _run_tool(maps, self.cache, "--no-prune", "--floors", json.dumps({"orm_psnr": 99.0}))
        self.assertEqual(code, 0, output[-2000:])
        reason = self._index(maps / "shared-assets" / "vram")["excluded"].get(orm, "")
        self.assertTrue(reason.startswith("quality: channel psnr"), reason)

    def test_cache_inside_a_worktree_must_be_ignored(self):
        repo = self.scratch / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        code, _, output = _run_tool(self.maps, repo / "cache", "--no-prune")
        self.assertEqual(code, 1)
        self.assertIn("not ignored", output)


if __name__ == "__main__":
    unittest.main()

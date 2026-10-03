#!/usr/bin/env python3
"""The packager stages and checks the VRAM texture sidecars
(tools/package_client.py stage_vram_textures / check_vram_textures).

    python3 godot-client/tests/test_package_vram.py -v

The check cases run on a scratch stage holding a copy of tests/fixtures/vram
with its committed sidecars. The staging case runs the real tool, which needs
the Godot 4.7.2 editor binary plus numpy and Pillow; without them it skips.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
CLIENT = TESTS.parent
FIXTURE = TESTS / "fixtures" / "vram"
sys.path.insert(0, str(CLIENT / "tools"))
sys.path.insert(0, str(TESTS))

import package_client as packager  # noqa: E402
from test_build_vram_textures import GODOT, SKIP_ENCODE  # noqa: E402

MAP = Path("eloria-assets") / "maps" / "vram_fixture"


class Check(unittest.TestCase):
    def setUp(self):
        self.stage = Path(tempfile.mkdtemp(prefix="vram-package-check-"))
        shutil.copytree(FIXTURE, self.stage / MAP, ignore=shutil.ignore_patterns("*.py", "report.json"))
        self.vram = self.stage / MAP / "shared-assets" / "vram"
        self.index = json.loads((self.vram / "index.json").read_text(encoding="utf-8"))

    def tearDown(self):
        shutil.rmtree(self.stage, ignore_errors=True)

    def _write_index(self):
        (self.vram / "index.json").write_text(json.dumps(self.index), encoding="utf-8")

    def test_committed_fixture_passes(self):
        packager.check_vram_textures(self.stage)

    def test_a_changed_sidecar_fails(self):
        entry = next(iter(self.index["images"].values()))
        path = self.vram / entry["file"]
        data = bytearray(path.read_bytes())
        data[-1] ^= 0xFF
        path.write_bytes(bytes(data))
        with self.assertRaisesRegex(packager.PackageError, "sha256 differs"):
            packager.check_vram_textures(self.stage)

    def test_an_image_without_sidecar_or_reason_fails(self):
        sha = next(iter(self.index["images"]))
        del self.index["images"][sha]
        self._write_index()
        with self.assertRaisesRegex(packager.PackageError, "no sidecar and no exclusion reason"):
            packager.check_vram_textures(self.stage)

    def test_a_missing_sidecar_fails(self):
        entry = next(iter(self.index["images"].values()))
        (self.vram / entry["file"]).unlink()
        with self.assertRaisesRegex(packager.PackageError, "listed in the index but missing"):
            packager.check_vram_textures(self.stage)

    def test_a_stray_file_fails(self):
        (self.vram / "report.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(packager.PackageError, "not named by the index"):
            packager.check_vram_textures(self.stage)

    def test_an_unstaged_external_image_fails(self):
        manifest = json.loads((self.stage / MAP / "world.json").read_text(encoding="utf-8"))
        uri = next(iter(manifest["externalResources"]))
        (self.stage / MAP / uri).unlink()
        with self.assertRaisesRegex(packager.PackageError, "is not in the package"):
            packager.check_vram_textures(self.stage)

    def test_no_index_at_all_fails(self):
        shutil.rmtree(self.vram)
        with self.assertRaisesRegex(packager.PackageError, "no sidecar and no exclusion reason"):
            packager.check_vram_textures(self.stage)


class StageExternalResources(unittest.TestCase):
    """externalResources names its files as keys, relative to the GLB: the
    continent's shared images live outside every package folder and used to
    be left out of the package, so every chunk failed its resource check."""

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="vram-package-stage-ext-"))
        chunk = self.repo / "eloria-assets" / "maps" / "region" / "chunks" / "a"
        shared = self.repo / "eloria-assets" / "maps" / "_continent" / "shared-assets"
        chunk.mkdir(parents=True)
        shared.mkdir(parents=True)
        (shared / "abc.png").write_bytes(b"\x89PNG fixture")
        (chunk / "world.glb").write_bytes(b"glTF")
        self.manifest = {"asset": {"glb": "world.glb"},
                         "externalResources": {"../../../_continent/shared-assets/abc.png": "0" * 64}}
        (chunk / "world.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        git = ["git", "-C", str(self.repo), "-c", "user.name=test", "-c", "user.email=test@example.invalid"]
        subprocess.run(git[:3] + ["init", "-q"], check=True)
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "fixture"], check=True)
        self.stage = self.repo.parent / (self.repo.name + "-stage")

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)
        shutil.rmtree(self.stage, ignore_errors=True)

    def test_shared_images_are_staged(self):
        packager.stage_eloria_assets(self.repo, self.stage)
        self.assertTrue((self.stage / "eloria-assets/maps/_continent/shared-assets/abc.png").is_file())
        self.assertTrue((self.stage / "eloria-assets/maps/region/chunks/a/world.glb").is_file())

    def test_an_untracked_external_image_fails_the_stage(self):
        chunk = self.repo / "eloria-assets" / "maps" / "region" / "chunks" / "a"
        self.manifest["externalResources"]["../../../_continent/shared-assets/missing.png"] = "1" * 64
        (chunk / "world.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=test", "-c", "user.email=test@example.invalid",
                        "commit", "-q", "-am", "missing"], check=True)
        with self.assertRaisesRegex(packager.PackageError, "externalResources -> .*missing.png is not in the commit"):
            packager.stage_eloria_assets(self.repo, self.stage)


class SelfTestLine(unittest.TestCase):
    def test_packager_and_client_agree_on_the_line(self):
        client = (CLIENT / "src" / "world" / "vram_textures.gd").read_text(encoding="utf-8")
        self.assertIn(packager.VRAM_SELF_TEST_OK, client)
        self.assertIn("ELORIA_VRAM_SELF_TEST", client)


@unittest.skipIf(SKIP_ENCODE, SKIP_ENCODE or "")
class Stage(unittest.TestCase):
    def test_stage_builds_checks_and_ships_only_index_and_sidecars(self):
        scratch = Path(tempfile.mkdtemp(prefix="vram-package-stage-"))
        try:
            build = scratch / "build"
            stage = scratch / "stage"
            logs = scratch / "logs"
            logs.mkdir()
            shutil.copytree(FIXTURE, build / MAP, ignore=shutil.ignore_patterns("vram", "*.py"))
            shutil.copytree(build / MAP, stage / MAP)
            staged = packager.stage_vram_textures(build, stage, GODOT, scratch / "cache", logs,
                                                  tool=CLIENT / "tools" / "build_vram_textures.py")
            vram = stage / MAP / "shared-assets" / "vram"
            self.assertEqual(sorted(p.suffix for p in vram.iterdir()), [".evt"] * 4 + [".json"])
            self.assertEqual(staged["files"], 5)
            self.assertTrue(any(logs.glob("vram-report-*.json")), "the quality report goes to the logs")
            self.assertFalse((build / MAP / "shared-assets" / "vram").exists(),
                             "nothing is written into the build worktree")
            packager.check_vram_textures(stage)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

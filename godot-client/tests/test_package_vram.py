#!/usr/bin/env python3
"""The packager stages and checks the VRAM texture sidecars
(tools/package_client.py stage_vram_textures / check_vram_textures).

    python3 godot-client/tests/test_package_vram.py -v

The check cases run on a scratch stage holding a copy of tests/fixtures/vram
with its committed sidecars. The staging case runs the real tool, which needs
the Godot 4.7.2 editor binary plus numpy and Pillow; without them it skips.

StageCommittedMaps walks this checkout's committed maps the way the packager
does, so a manifest naming a file that is not in the commit fails here in
seconds instead of after the packager's half-hour import and export. CI runs
it twice: with the rest of this file in the protocol-tests job, and on its own
as the package-map-walk job, which no failing protocol-tests step can skip. It
runs git in the checkout, so protocol-tests first marks the checkout a safe
directory: in that job's container git runs as root, the runner owns the
checkout, and git refuses a repository someone else owns.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TESTS = Path(__file__).resolve().parent
CLIENT = TESTS.parent
CHECKOUT = CLIENT.parent
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


def _git(*args: str, data: bytes | None = None) -> bytes:
    result = subprocess.run(["git", *args], cwd=CHECKOUT, input=data, capture_output=True)
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed in {CHECKOUT}:\n"
                             + result.stderr.decode("utf-8", errors="replace"))
    return result.stdout


def _batch_contents(output: bytes):
    """The object contents in `git cat-file --batch` output, in request order."""
    at = 0
    while at < len(output):
        end = output.index(b"\n", at)
        header = output[at:end].split()
        if len(header) != 3:
            raise AssertionError(f"git cat-file --batch: {output[at:end]!r}")
        size = int(header[2])
        yield output[end + 1:end + 1 + size]
        at = end + 1 + size + 1


@unittest.skipUnless((CHECKOUT / ".git").exists(), "needs the client's git checkout")
class StageCommittedMaps(unittest.TestCase):
    """The packager's map walk over this checkout's committed maps: every file a
    shipped manifest names must be in the commit. The packager itself runs this
    walk only after its half-hour import and export.

    396 legacy chunk manifests once stopped it there: each carried a copy of its
    territory's minimap block, naming a chunks/<x>_<z>/minimap.webp that no tool
    writes and nothing reads (the client frames and draws the map from the
    territory's own block and picture)."""

    @classmethod
    def setUpClass(cls):
        # packager.tracked() would fail with a bare CalledProcessError; say why
        # git cannot read the checkout (in a CI container: dubious ownership).
        _git("rev-parse", "--verify", "-q", "HEAD")

    def test_chunk_manifests_carry_no_minimap_block(self):
        # build_continent.py export_geometry still copies the block into each
        # chunk: pop "minimap" there at the next geometry export, when the
        # certificates that pin that file are re-issued anyway. Do not commit
        # pictures beside the chunks instead.
        # Read from the index, so a sparse checkout still checks every chunk.
        listing = _git("ls-files", "-s", "-z", "--", "eloria-assets/maps").decode("utf-8")
        chunks = [(meta.split()[1], path) for meta, path in (line.split("\t", 1) for line in listing.split("\0") if line)
                  if path.endswith("/world.json") and path.split("/")[-3] == "chunks"]
        self.assertTrue(chunks, "the checkout has no chunk manifests")
        blobs = _git("cat-file", "--batch", data="".join(f"{sha}\n" for sha, _ in chunks).encode("ascii"))
        carrying = [path for (_, path), text in zip(chunks, _batch_contents(blobs)) if "minimap" in json.loads(text)]
        self.assertEqual(carrying[:5], [], f"{len(carrying)} chunk manifests copy their territory's minimap block")

    def test_every_file_a_shipped_manifest_names_is_committed(self):
        manifests = [path for path in packager.tracked(CHECKOUT, "eloria-assets/maps") if path.endswith("/world.json")]
        absent = [path for path in manifests if not (CHECKOUT / path).is_file()]
        if absent:
            # The walk skips a manifest it cannot read, so it would pass here
            # without checking it.
            self.skipTest(f"{len(absent)} map manifests are not checked out (a sparse checkout?), e.g. {absent[0]}")
        registry = json.loads((CLIENT / "data" / "maps" / "registry.json").read_text(encoding="utf-8"))
        stage = Path(tempfile.mkdtemp(prefix="package-committed-maps-"))
        staged: set[str] = set()

        def copy_file(source: Path, target: Path) -> int:
            staged.add(target.relative_to(stage).as_posix())
            return 0

        try:
            with mock.patch.object(packager, "copy_file", copy_file), mock.patch.object(packager, "log"):
                packager.stage_eloria_assets(CHECKOUT, stage)
        except packager.PackageError as error:
            self.fail(str(error))
        finally:
            shutil.rmtree(stage, ignore_errors=True)
        # A walk that read nothing would pass as well: every map manifest the
        # registry names must have been staged.
        named = {match.group(1) for entry in registry.get("maps", {}).values() if isinstance(entry, dict)
                 for match in [packager.ASSET_REF.search(str(entry.get("manifest", "")))] if match}
        self.assertTrue(named, "the registry names no map manifests")
        self.assertEqual(sorted(named - staged)[:5], [], f"{len(named - staged)} registry manifests were not staged")


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

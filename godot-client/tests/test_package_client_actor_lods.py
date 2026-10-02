"""Packaging contract for imported actor LODs and loose raw fallbacks."""
import importlib.util
from pathlib import Path
import sys

import pytest


SOURCE = Path(__file__).resolve().parents[1] / "tools" / "package_client.py"
SPEC = importlib.util.spec_from_file_location("package_client_actor_lods", SOURCE)
package = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = package
SPEC.loader.exec_module(package)


def _write_actor_import(project: Path, *, lods: bool = True, artifact: bool = True) -> None:
    source = project / "assets/actors/native/races/hero.glb"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"glTF")
    imported = project / ".godot/imported/hero.glb-test.scn"
    imported.parent.mkdir(parents=True)
    if artifact:
        imported.write_bytes(b"RSRC imported scene")
    source.with_name(source.name + ".import").write_text(
        "[remap]\n\n"
        'type="PackedScene"\n'
        'path="res://.godot/imported/hero.glb-test.scn"\n\n'
        "[params]\n\n"
        f"meshes/generate_lods={'true' if lods else 'false'}\n",
        encoding="utf-8",
    )


def test_export_presets_pack_actor_resources_for_resource_loader():
    actor_exclusions = [
        line for line in package.EXPORT_PRESETS.splitlines()
        if line.startswith("exclude_filter=") and "assets/actors" in line
    ]
    assert not actor_exclusions
    assert package.EXPORT_PRESETS.count('export_filter="all_resources"') == 2


def test_prepare_build_tree_removes_stale_actor_gdignore(tmp_path, monkeypatch):
    build = tmp_path / "client-src"
    (build / ".git").mkdir(parents=True)
    barrier = build / "godot-client/assets/actors/.gdignore"
    barrier.parent.mkdir(parents=True)
    barrier.write_text("", encoding="utf-8")
    monkeypatch.setattr(package, "git", lambda *_args, **_kwargs: "")

    project = package.prepare_build_tree(build, "a" * 40)

    assert project == build / "godot-client"
    assert not barrier.exists()
    assert "assets/actors" not in (project / "export_presets.cfg").read_text()


def test_actor_import_check_accepts_generated_lod_packed_scene(tmp_path):
    _write_actor_import(tmp_path)
    package.check_actor_imports(tmp_path)


def test_packaging_stops_before_export_when_actor_lod_imports_are_absent(
        tmp_path, monkeypatch):
    project = tmp_path / "client-src/godot-client"
    project.mkdir(parents=True)
    monkeypatch.setattr(sys, "argv", [
        str(SOURCE), "--no-fetch", "--no-zip", "--no-smoke",
        "--build-dir", str(tmp_path / "client-src"),
        "--out", str(tmp_path / "dist"),
    ])
    monkeypatch.setattr(package, "find_godot", lambda _explicit: tmp_path / "godot.exe")
    monkeypatch.setattr(package, "git", lambda *_args, **_kwargs: "a" * 40 + "\n")
    monkeypatch.setattr(package, "prepare_build_tree", lambda *_args: project)
    monkeypatch.setattr(package, "import_project", lambda *_args: None)
    monkeypatch.setattr(
        package, "check_actor_imports",
        lambda _project: (_ for _ in ()).throw(package.PackageError("actor LOD imports are incomplete")),
    )
    monkeypatch.setattr(
        package, "export_project",
        lambda *_args: pytest.fail("export must not run without actor LOD imports"),
    )

    assert package.main() == 1


@pytest.mark.parametrize("lods,artifact", [(False, True), (True, False)])
def test_actor_import_check_rejects_missing_packaged_lod_inputs(tmp_path, lods, artifact):
    _write_actor_import(tmp_path, lods=lods, artifact=artifact)
    with pytest.raises(package.PackageError, match="actor LOD imports are incomplete"):
        package.check_actor_imports(tmp_path)


def test_loose_actor_glb_is_still_staged_for_metadata_and_raw_fallback(tmp_path, monkeypatch):
    build = tmp_path / "build"
    app = tmp_path / "app"
    relative = "godot-client/assets/actors/native/races/hero.glb"
    source = build / relative
    source.parent.mkdir(parents=True)
    source.write_bytes(b"raw actor glb")
    monkeypatch.setattr(package, "tracked", lambda *_args: [relative])

    package.stage_loose_client_files(build, app)

    assert (app / "assets/actors/native/races/hero.glb").read_bytes() == b"raw actor glb"

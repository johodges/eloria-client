"""The reviewed class-equipment fit stays pinned and cannot be double-baked."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "eloria-assets/tools"
sys.path.insert(0, str(TOOLS))

import revise_class_equipment_fit as revision
import torso_remap


def _manifest() -> dict:
    return json.loads(revision.DEFAULT_MANIFEST.read_text(encoding="utf-8"))


def test_manifest_roster_and_installed_outputs_are_exact():
    manifest = _manifest()
    assert manifest["shoulderRevision"] == {
        "profileVersion": 2,
        "lockTravel": torso_remap.SLEEVE_PROFILE_LOCK_T,
        "backingClearanceMeters": torso_remap.SLEEVE_BACKING_CLEARANCE,
        "geometryStrategy":
            "fresh-reference-geometry-pinned-production-textures",
        "sourceTriangles": 122093,
        "outputTriangles": 113273,
        "drawCountPerAsset": 2,
        "maximumPerAssetTriangleIncreasePercent": 2.0,
        "classes": {
            "vanguard": "militia_torso_armor_02",
            "ranger": "leather_ranger_torso_02",
            "arcanist": "eloria_arcane_armor_01",
            "warden": "amberwood_woodland_cuirass_06",
        },
    }
    assert len(manifest["sourceGitCommit"]) == 40
    assert len(manifest["anatomyGitCommit"]) == 40
    assert set(manifest["anatomy"]) == {
        race + ".glb" for race in revision.RACES}
    assert set(manifest["authoringSource"]) == set(revision.TORSOS.values())
    slugs = (set(revision.TORSOS.values()) | set(revision.LEGS.values())
             | set(revision.BOOTS.values()))
    expected = {
        revision.asset_key(race, slug)
        for race in revision.RACES for slug in slugs
    }
    expected_references = {
        revision.asset_key(race, slug)
        for race in revision.RACES for slug in revision.TORSOS.values()
    }
    assert set(manifest["source"]) == expected
    assert set(manifest["output"]) == expected
    assert set(manifest["reference"]) == expected_references
    assert set(manifest["rig"]) == {race + ".glb" for race in revision.RACES}
    installed_paths = []
    output_triangles = 0
    for relative, expected_hash in manifest["output"].items():
        installed = (ROOT / "godot-client/assets/actors/native/equipment"
                     / Path(relative))
        assert revision.digest(installed) == expected_hash, relative
        installed_paths.append(installed)
        if relative.endswith(tuple(
                slug + ".glb" for slug in revision.TORSOS.values())):
            document, _ = revision.ea.read_glb(installed)
            draws = sum(len(mesh["primitives"])
                        for mesh in document["meshes"])
            assert draws == manifest["shoulderRevision"]["drawCountPerAsset"]
            output_triangles += sum(
                document["accessors"][primitive["indices"]]["count"] // 3
                for mesh in document["meshes"]
                for primitive in mesh["primitives"])
    assert output_triangles == manifest["shoulderRevision"]["outputTriangles"]
    assert output_triangles < manifest["shoulderRevision"]["sourceTriangles"]
    resources = revision.validate_resources(installed_paths)
    assert resources
    assert all(len(value) == 64 for value in resources.values())


def test_installed_outputs_are_rejected_as_a_second_pass_source():
    production = ROOT / "godot-client/assets/actors/native/equipment"
    # Hash validation precedes reference loading and output creation. The
    # installed revision therefore cannot masquerade as its own baseline.
    with pytest.raises(ValueError, match="Packed baseline hash mismatch"):
        revision.validate_inputs(production, ROOT, _manifest())


def test_external_paths_are_reportable(monkeypatch):
    monkeypatch.setattr(revision, "ROOT", Path("/class-equipment-repo"))
    external = Path("/class-equipment-external/baseline.glb")
    assert revision.display_path(external) == str(external.resolve())

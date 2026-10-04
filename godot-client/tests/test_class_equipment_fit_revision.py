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


CUFF_MANIFEST = ROOT / "eloria-assets/qa/luminous-female-cuff-fit.json"
CUFF_CONSUMED_OUTPUTS = {
    "variants/luminous_female/arcane_leg_armor_01.glb": "arcanistLegs",
    "variants/luminous_female/arcane_fantasy_boots_01.glb": "arcanistBoots",
}
WARDED_BOOT_MANIFEST = (
    ROOT / "eloria-assets/qa/canonical-warded-boots-fit.json")
WARDED_BOOT_CONSUMED_OUTPUTS = {"arcane_fantasy_boots_01.glb"}


def _manifest() -> dict:
    return json.loads(revision.DEFAULT_MANIFEST.read_text(encoding="utf-8"))


def test_manifest_roster_and_installed_outputs_are_exact():
    manifest = _manifest()
    cuff_manifest = json.loads(CUFF_MANIFEST.read_text(encoding="utf-8"))
    warded_boot_manifest = json.loads(
        WARDED_BOOT_MANIFEST.read_text(encoding="utf-8"))
    assert cuff_manifest["status"] == "installed-production"
    assert warded_boot_manifest["status"] == "installed-production"
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
        if relative in CUFF_CONSUMED_OUTPUTS:
            cuff_key = CUFF_CONSUMED_OUTPUTS[relative]
            cuff_input = cuff_manifest["inputs"][cuff_key]
            assert cuff_input["sourceSHA256"] == expected_hash, relative
            provenance = cuff_input["provenance"]
            assert provenance == {
                "kind": "producer-manifest-output",
                "manifest": "eloria-assets/qa/class-equipment-fit-baseline.json",
                "section": "output",
                "key": relative,
            }
        elif relative in WARDED_BOOT_CONSUMED_OUTPUTS:
            source = warded_boot_manifest["source"]
            assert source["sha256"] == expected_hash, relative
            assert source["provenance"] == {
                "kind": "producer-manifest-output",
                "manifest": "eloria-assets/qa/class-equipment-fit-baseline.json",
                "section": "output",
                "key": relative,
            }
            output = warded_boot_manifest["output"]
            assert output["path"] == (
                "godot-client/assets/actors/native/equipment/" + relative)
            assert revision.digest(installed) == output["sha256"], relative
        else:
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

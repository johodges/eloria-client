"""Regression coverage for the installed Luminous-female cuff pass."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "eloria-assets/tools"
sys.path.insert(0, str(TOOLS))

import author_luminous_cuff_fit as cuff
from verify_shared_player_bodies import GEOMETRY_FIELDS, signatures


MANIFEST = cuff.DEFAULT_MANIFEST
DERIVED_MANIFEST = (
    ROOT / "eloria-assets/qa/luminous-female-cuff-derived-propagation.json")
CLASS_MANIFEST = ROOT / "eloria-assets/qa/class-equipment-fit-baseline.json"
EQUIPMENT = ROOT / "godot-client/data/actors/equipment.json"
CATALOG = ROOT / "godot-client/data/actors/native_asset_catalog.json"
MODELS = ROOT / "godot-client/data/actors/models.json"
FACE_MASKS = ROOT / "godot-client/assets/actors/native/face_masks/manifest.json"
INSTALLED = {
    "body": ROOT / "godot-client/assets/actors/native/races/luminous_female.glb",
    "arcanistLegs": (
        ROOT / "godot-client/assets/actors/native/equipment/variants/"
        "luminous_female/arcane_leg_armor_01.glb"),
    "arcanistBoots": (
        ROOT / "godot-client/assets/actors/native/equipment/variants/"
        "luminous_female/arcane_fantasy_boots_01.glb"),
    "rangerLegs": (
        ROOT / "godot-client/assets/actors/native/equipment/variants/"
        "luminous_female/rugged_ranger_legwear_04.glb"),
    "rangerBoots": (
        ROOT / "godot-client/assets/actors/native/equipment/variants/"
        "luminous_female/frontier_boots_01.glb"),
}


def _manifest() -> dict:
    return cuff.load_manifest(MANIFEST)


def _semantic_spec(reviewed: dict, key: str) -> dict:
    if key in ("body", "rangerLegs", "rangerBoots"):
        return reviewed[key]["semanticMeshes"]
    mesh_name = {
        "arcanistLegs": "Warded Legguards",
        "arcanistBoots": "Warded Boots",
    }[key]
    return {mesh_name: reviewed[key]["semanticMesh"]}


def _primary_geometry_signature(path: Path, mesh_name: str):
    document, binary = cuff.ea.read_glb(path)
    primitive = cuff.named_mesh(document, mesh_name)["primitives"][0]
    arrays = {
        name: cuff.ea.accessor_array(document, binary, accessor)
        for name, accessor in primitive["attributes"].items()
    }
    faces = cuff.ea.accessor_array(
        document, binary, primitive["indices"]).astype(int).reshape(-1, 3)
    return signatures(arrays, faces, GEOMETRY_FIELDS)


def test_manifest_preserves_historical_inputs_and_zero_runtime_cost():
    manifest = _manifest()
    assert manifest["schema"] == "eloria-luminous-female-cuff-fit-v2"
    assert manifest["status"] == "installed-production"
    assert manifest["authority"]["sourceSHA256"] == (
        "39a4dbc151d6f04813fa843803ef5e8c71eca61e59b700d9c876274a9c7f9d66")
    assert manifest["authority"]["hiddenOverlapRangeMm"] == pytest.approx(
        [1.93677412328858, 4.89287166927216], abs=1e-12)
    assert manifest["contract"] == {
        "selectedHiddenOverlapMm": 3.0,
        "arcanistRadialInsetMm": 1.5,
        "openHiddenBoundary": True,
        "capTriangles": 0,
        "maximumInfluences": 4,
        "additionalDraws": 0,
        "additionalMaterials": 0,
        "additionalBones": 0,
        "perFrameOperations": 0,
    }
    installation = manifest["installation"]
    assert installation["mode"] == "reviewed-byte-copy"
    assert installation["inputsAreHistorical"] is True
    assert installation["productionConfigChanged"] is False
    evidence = manifest["authoringEvidence"]
    assert evidence["deterministicRuns"] == 2
    assert evidence["byteIdentical"] is True
    verifier_text = (ROOT / evidence["toolPath"]).read_text(encoding="utf-8")
    verifier_text = verifier_text.replace("\r\n", "\n").replace("\r", "\n")
    verifier_hash = hashlib.sha256(verifier_text.encode("utf-8")).hexdigest()
    assert verifier_hash == evidence["verifierToolCanonicalLfSHA256"]
    assert evidence["producerToolGitCommit"] == (
        "5d856c982c81889e19c2ecccb1d811303f37a7f6")
    assert evidence["producerToolGitBlob"] == (
        "fa5bf59cb1560fa66549bc9a4752695c7e017c1d")
    assert evidence["producerToolSHA256"] == (
        "61e783a8ccb531f3f143d19ecb5d5222348e72340a1036c8b5aac579b1b1e3e2")

    inputs = manifest["inputs"]
    snapshot = "dc2839be93d7b87b62ba665f103f4b7207828d81"
    git_sources = {
        "body": "01b08fe18c8d0b5f7fd38555a75b6e5682d69500",
        "rangerLegs": "0e378eb9c3edb803761f556ccb782cc781009315",
        "rangerBoots": "d38c00b92212a0de61db28e8dd06d4da14fb7f5a",
    }
    for key, blob_oid in git_sources.items():
        provenance = inputs[key]["provenance"]
        assert provenance["kind"] == "git-tree-snapshot"
        assert provenance["commit"] == snapshot
        assert provenance["blobOID"] == blob_oid
        assert provenance["path"] == inputs[key]["pathAtCapture"]

    class_manifest = json.loads(CLASS_MANIFEST.read_text(encoding="utf-8"))
    for key in ("arcanistLegs", "arcanistBoots"):
        source = inputs[key]
        provenance = source["provenance"]
        assert provenance["kind"] == "producer-manifest-output"
        assert provenance["manifest"] == (
            "eloria-assets/qa/class-equipment-fit-baseline.json")
        assert provenance["section"] == "output"
        assert class_manifest[provenance["section"]][provenance["key"]] == (
            source["sourceSHA256"])

    assert cuff.digest(EQUIPMENT) == (
        inputs["equipmentConfig"]["sourceSHA256"])


def test_installed_outputs_match_reviewed_hashes_and_semantic_contracts():
    manifest = _manifest()
    mappings = manifest["installation"]["mappings"]
    assert len(mappings) == len(INSTALLED) == 5
    assert {item["inputKey"] for item in mappings} == set(INSTALLED)
    assert {item["reviewedOutputKey"] for item in mappings} == set(INSTALLED)
    assert len({item["targetPath"] for item in mappings}) == len(INSTALLED)

    reviewed = manifest["reviewedOutputs"]
    for mapping in mappings:
        key = mapping["inputKey"]
        assert mapping["reviewedOutputKey"] == key
        installed = ROOT / mapping["targetPath"]
        assert installed == INSTALLED[key]
        assert cuff.digest(installed) == reviewed[key]["outputSHA256"]
        expected = _semantic_spec(reviewed, key)
        actual = cuff.semantic_mesh_contracts(installed, expected)
        cuff._require_semantic_contracts(
            actual, expected, f"Installed {key}")

    assert reviewed["body"]["geometry"] == {
        "sourceVertices": 4828,
        "outputVertices": 4601,
        "sourceTriangles": 6733,
        "outputTriangles": 6432,
        "boundaryEdges": 114,
        "boundaryVertices": 124,
    }
    assert reviewed["arcanistLegs"]["geometry"]["boundaryEdges"] == 36
    assert reviewed["rangerLegs"]["geometry"]["visibleBreeches"][
        "boundaryVertices"] == 70
    assert reviewed["rangerLegs"]["geometry"]["pairedLegBacking"][
        "boundaryVertices"] == 327
    assert reviewed["rangerBoots"]["geometry"]["pairedBootBacking"][
        "boundaryVertices"] == 215
    assert reviewed["rangerBoots"]["removedComponentLabels"] == []


def test_installed_body_metadata_tracks_the_installed_bytes():
    installed_hash = cuff.digest(INSTALLED["body"])
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    race = catalog["races"]["luminous_female"]
    assert race["sha256"] == installed_hash
    assert race["vertices"] == 24684
    assert race["triangles"] == 35449
    models = json.loads(MODELS.read_text(encoding="utf-8"))
    assert models["models"]["luminous_female"]["skinPalette"][
        "sourceSHA256"] == installed_hash
    masks = json.loads(FACE_MASKS.read_text(encoding="utf-8"))
    assert masks["luminous_female"]["modelSHA256"] == installed_hash


def test_derived_female_cuffs_preserve_shared_body_and_cultural_surfaces():
    propagation = json.loads(DERIVED_MANIFEST.read_text(encoding="utf-8"))
    assert propagation["schema"] == (
        "eloria-luminous-female-cuff-derived-propagation-v1")
    assert propagation["status"] == "installed-production"
    expected_races = {
        "glasswarden_female", "greyhaven_female", "mycelari_female",
        "orun_female", "ssarathi_female", "stoneborn_female",
        "votary_female",
    }
    assert set(propagation["assets"]) == expected_races
    contract = propagation["contract"]
    assert contract["selectedHiddenOverlapMm"] == 3.0
    assert contract["openHiddenBoundary"] is True
    assert contract["capTriangles"] == 0
    assert contract["preserveAdditionalPantsPrimitives"] is True
    assert [contract[name] for name in (
        "additionalDraws", "additionalMaterials", "additionalBones",
        "perFrameOperations")] == [0, 0, 0, 0]

    evidence = propagation["authoringEvidence"]
    tool_text = (ROOT / evidence["toolPath"]).read_text(encoding="utf-8")
    tool_text = tool_text.replace("\r\n", "\n").replace("\r", "\n")
    assert hashlib.sha256(tool_text.encode("utf-8")).hexdigest() == (
        evidence["toolCanonicalLfSHA256"])
    assert evidence["deterministicRuns"] == 2
    assert evidence["byteIdentical"] is True

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))["races"]
    models = json.loads(MODELS.read_text(encoding="utf-8"))["models"]
    masks = json.loads(FACE_MASKS.read_text(encoding="utf-8"))
    template_lineage_hash = propagation["template"]["historicalSourceSHA256"]
    embedded_template_lineage_hash = propagation["template"][
        "embeddedTemplateSHA256"]
    assert propagation["template"]["catalogTemplateSHA256Semantics"] == (
        "pre-cuff assembled Luminous template lineage used by the derived "
        "head builds; the installed cuffed template is installedSHA256")
    assert propagation["template"]["embeddedTemplateSHA256Semantics"] == (
        "original body-donor lineage retained in "
        "asset.extras.sharedBodyShape by the derived head builds")
    reference_pants = _primary_geometry_signature(
        INSTALLED["body"], "wardrobe_pants")
    reference_boots = _primary_geometry_signature(
        INSTALLED["body"], "wardrobe_boots")
    for slug, spec in propagation["assets"].items():
        path = ROOT / spec["path"]
        assert cuff.digest(path) == spec["outputSHA256"]
        assert spec["sourceSHA256"] != spec["outputSHA256"]
        document, binary = cuff.ea.read_glb(path)
        pants = cuff.semantic_mesh_contract(
            document, binary, "wardrobe_pants", primitive_index=0)
        boots = cuff.semantic_mesh_contract(
            document, binary, "wardrobe_boots", primitive_index=0)
        assert pants["sha256"] == spec["outputPantsSemanticSHA256"]
        assert boots["sha256"] == spec["bootsSemanticSHA256"]
        pants_mesh = cuff.named_mesh(document, "wardrobe_pants")
        extras = [
            cuff.semantic_mesh_contract(
                document, binary, "wardrobe_pants", primitive_index=index)[
                    "sha256"]
            for index in range(1, len(pants_mesh["primitives"]))
        ]
        assert extras == spec["preservedAdditionalPantsPrimitiveSHA256"]
        assert _primary_geometry_signature(
            path, "wardrobe_pants") == reference_pants
        assert _primary_geometry_signature(
            path, "wardrobe_boots") == reference_boots
        assert sum(len(mesh["primitives"])
                   for mesh in document["meshes"]) == spec["draws"]
        assert len(document.get("materials", [])) == spec["materials"]
        assert len(document["skins"][0]["joints"]) == spec["joints"]
        assert document["asset"]["extras"]["sharedBodyShape"][
            "templateSHA256"] == embedded_template_lineage_hash
        assert catalog[slug]["sha256"] == spec["outputSHA256"]
        assert catalog[slug]["vertices"] == spec["outputVertices"]
        assert catalog[slug]["triangles"] == spec["outputTriangles"]
        assert catalog[slug]["sharedBodyShape"][
            "templateSHA256"] == template_lineage_hash
        assert models[slug]["skinPalette"][
            "sourceSHA256"] == spec["outputSHA256"]
        assert masks[slug]["modelSHA256"] == spec["outputSHA256"]

    ssarathi = propagation["assets"]["ssarathi_female"]
    assert ssarathi["preservedAdditionalPantsPrimitiveSHA256"] == [
        "20f6b1e70a111b817a00e2aa2b645d4238623da7c9490a5fa115398535e95465"
    ]


def test_historical_body_provenance_is_valid_without_baseline_binary():
    body_spec = _manifest()["inputs"]["body"]
    asset_hash = "a" * 64
    provenance = {
        "schema": "eloria-canonical-body-provenance-v1",
        "canonicalRace": "luminous_female",
        "assetSHA256": asset_hash,
        "canonicalSourceSHA256": body_spec["acceptedSourceSHA256"][0],
        "producer": "test neck-only authoring fixture",
        "inheritedSemanticMeshes": {
            name: value["sha256"]
            for name, value in body_spec["semanticMeshes"].items()
        },
    }
    cuff.validate_body_provenance_record(
        provenance, body_spec, actual_hash=asset_hash)
    invalid = copy.deepcopy(provenance)
    invalid["inheritedSemanticMeshes"]["wardrobe_pants"] = "0" * 64
    with pytest.raises(ValueError, match="surface roster changed"):
        cuff.validate_body_provenance_record(
            invalid, body_spec, actual_hash=asset_hash)


def test_installed_outputs_are_rejected_as_second_pass_sources():
    inputs = _manifest()["inputs"]
    with pytest.raises(ValueError, match="Body semantic surface"):
        cuff.validate_body_source(INSTALLED["body"], inputs["body"])
    with pytest.raises(ValueError, match="Arcanist legs SHA-256 changed"):
        cuff.validate_pinned_source(
            INSTALLED["arcanistLegs"], inputs["arcanistLegs"],
            "Arcanist legs")
    with pytest.raises(ValueError, match="Arcanist boots SHA-256 changed"):
        cuff.validate_pinned_source(
            INSTALLED["arcanistBoots"], inputs["arcanistBoots"],
            "Arcanist boots")
    with pytest.raises(ValueError, match="Ranger legs SHA-256 changed"):
        cuff.validate_pinned_asset(
            INSTALLED["rangerLegs"], inputs["rangerLegs"], "Ranger legs")
    with pytest.raises(ValueError, match="Ranger boots SHA-256 changed"):
        cuff.validate_pinned_asset(
            INSTALLED["rangerBoots"], inputs["rangerBoots"], "Ranger boots")


def test_authoring_refuses_a_production_output_path():
    prospective = (ROOT / "godot-client/assets/actors/native/races/"
                   "cuff-fit-output")
    with pytest.raises(ValueError, match="Refusing production output"):
        cuff.validate_output_path(prospective)

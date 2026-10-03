"""Regression coverage for the reviewed Luminous-female cuff authoring pass."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "eloria-assets/tools"
sys.path.insert(0, str(TOOLS))

import author_luminous_cuff_fit as cuff


MANIFEST = cuff.DEFAULT_MANIFEST
BODY = ROOT / "godot-client/assets/actors/native/races/luminous_female.glb"
LEGS = (ROOT / "godot-client/assets/actors/native/equipment/variants/"
        "luminous_female/arcane_leg_armor_01.glb")
BOOTS = (ROOT / "godot-client/assets/actors/native/equipment/variants/"
         "luminous_female/arcane_fantasy_boots_01.glb")
RANGER_LEGS = (ROOT / "godot-client/assets/actors/native/equipment/variants/"
               "luminous_female/rugged_ranger_legwear_04.glb")
RANGER_BOOTS = (ROOT / "godot-client/assets/actors/native/equipment/variants/"
                "luminous_female/frontier_boots_01.glb")
EQUIPMENT = ROOT / "godot-client/data/actors/equipment.json"


def _manifest() -> dict:
    return cuff.load_manifest(MANIFEST)


def test_manifest_pins_reviewed_sources_and_zero_runtime_cost():
    manifest = _manifest()
    contract = manifest["contract"]
    assert manifest["status"].endswith("production-install-deferred")
    assert manifest["authority"]["sourceSHA256"] == (
        "39a4dbc151d6f04813fa843803ef5e8c71eca61e59b700d9c876274a9c7f9d66")
    assert manifest["authority"]["hiddenOverlapRangeMm"] == pytest.approx(
        [1.93677412328858, 4.89287166927216], abs=1e-12)
    assert contract == {
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
    body = cuff.validate_body_source(BODY, manifest["inputs"]["body"])
    assert body["validationRoute"] == "manifest-pinned-source"
    cuff.validate_pinned_source(
        LEGS, manifest["inputs"]["arcanistLegs"], "Arcanist legs")
    cuff.validate_pinned_source(
        BOOTS, manifest["inputs"]["arcanistBoots"], "Arcanist boots")
    cuff.validate_pinned_asset(
        RANGER_LEGS, manifest["inputs"]["rangerLegs"], "Ranger legs")
    cuff.validate_pinned_asset(
        RANGER_BOOTS, manifest["inputs"]["rangerBoots"], "Ranger boots")
    assert cuff.digest(EQUIPMENT) == (
        manifest["inputs"]["equipmentConfig"]["sourceSHA256"])


def test_final_body_requires_expected_hash_or_canonical_provenance(tmp_path: Path):
    manifest = _manifest()
    body_spec = manifest["inputs"]["body"]
    document, binary = cuff.ea.read_glb(BODY)
    revised = copy.deepcopy(document)
    revised["extras"] = {"qa": "neck-only-derivative-fixture"}
    candidate = tmp_path / "neck_only_candidate.glb"
    cuff.write_glb(revised, binary, candidate)
    assert cuff.digest(candidate) != cuff.digest(BODY)
    with pytest.raises(ValueError, match="Unpinned body"):
        cuff.validate_body_source(candidate, body_spec)
    expected = cuff.validate_body_source(
        candidate, body_spec, expected_sha256=cuff.digest(candidate))
    assert expected["validationRoute"] == "caller-expected-sha256"
    provenance = {
        "schema": "eloria-canonical-body-provenance-v1",
        "canonicalRace": "luminous_female",
        "assetSHA256": cuff.digest(candidate),
        "canonicalSourceSHA256": body_spec["acceptedSourceSHA256"][0],
        "producer": "test neck-only authoring fixture",
        "inheritedSemanticMeshes": {
            name: value["sha256"]
            for name, value in body_spec["semanticMeshes"].items()
        },
    }
    provenance_path = tmp_path / "neck_only_candidate.provenance.json"
    provenance_path.write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    validated = cuff.validate_body_source(
        candidate, body_spec, provenance_path=provenance_path)
    assert validated["validationRoute"] == "explicit-canonical-provenance"
    transplanted = tmp_path / "neck_only_candidate_with_cuff.glb"
    report = cuff.clipped_copy(
        candidate, transplanted, "wardrobe_pants", candidate,
        "wardrobe_boots")
    cuff.validate_clip_contract(
        report, manifest["contract"], boot_interior=False)
    expected_output = manifest["reviewedOutputs"]["body"]["semanticMeshes"]
    actual_output = cuff.semantic_mesh_contracts(
        transplanted, expected_output)
    cuff._require_semantic_contracts(
        actual_output, expected_output, "Transplanted body")
    provenance["inheritedSemanticMeshes"]["wardrobe_pants"] = "0" * 64
    provenance_path.write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="surface roster changed"):
        cuff.validate_body_source(
            candidate, body_spec, provenance_path=provenance_path)


def test_reviewed_authoring_is_deterministic_and_geometry_safe(tmp_path: Path):
    manifest = _manifest()
    first = tmp_path / "first"
    second = tmp_path / "second"
    outputs = []
    for root in (first, second):
        body_target = root / "races/luminous_female.glb"
        legs_target = (root / "equipment/variants/luminous_female/"
                       "arcane_leg_armor_01.glb")
        boots_target = (root / "equipment/variants/luminous_female/"
                        "arcane_fantasy_boots_01.glb")
        ranger_legs_target = (root / "equipment/variants/luminous_female/"
                              "rugged_ranger_legwear_04.glb")
        ranger_boots_target = (root / "equipment/variants/luminous_female/"
                               "frontier_boots_01.glb")
        body_report = cuff.clipped_copy(
            BODY, body_target, "wardrobe_pants", BODY, "wardrobe_boots")
        legs_report = cuff.clipped_copy(
            LEGS, legs_target, "Warded Legguards", BOOTS, "Warded Boots",
            restrict_to_boot_interior=True)
        boots_report = cuff.pruned_arcanist_boot_copy(BOOTS, boots_target)
        ranger_report = cuff.ranger_cuffed_copies(
            RANGER_LEGS, RANGER_BOOTS,
            ranger_legs_target, ranger_boots_target)
        cuff.validate_clip_contract(
            body_report, manifest["contract"], boot_interior=False)
        cuff.validate_clip_contract(
            legs_report, manifest["contract"], boot_interior=True)
        cuff.validate_ranger_contract(ranger_report, manifest["contract"])
        outputs.append((body_target, legs_target, boots_target,
                        ranger_legs_target, ranger_boots_target,
                        body_report, legs_report, boots_report,
                        ranger_report))
    for left, right in zip(outputs[0][:5], outputs[1][:5]):
        assert cuff.digest(left) == cuff.digest(right)
    (body_target, legs_target, boots_target,
     ranger_legs_target, ranger_boots_target,
     body_report, legs_report, boots_report, ranger_report) = outputs[0]
    validated_body = cuff.validate_body_source(
        BODY, manifest["inputs"]["body"])
    result = cuff.validate_reviewed_outputs(
        validated_body, body_target, legs_target, boots_target,
        ranger_legs_target, ranger_boots_target, manifest)
    assert result["bodyExactReviewedBytes"] is True
    assert body_report["clip"]["capTriangles"] == 0
    assert body_report["clip"]["openBoundaryAudit"]["boundaryEdges"] == 114
    assert legs_report["clip"]["openBoundaryAudit"]["boundaryEdges"] == 36
    assert legs_report["clip"]["radialHiddenInsetMm"] == pytest.approx(
        [1.5, 1.5], abs=2e-6)
    assert boots_report["removedComponentLabels"] == [413, 834]
    assert boots_report["degenerateTriangles"] == 0
    ranger_legs = ranger_report["legs"]["clips"]
    assert ranger_report["authority"]["sides"]["left"]["cuffY98M"] == pytest.approx(
        .22885115444660187, abs=1e-12)
    assert ranger_report["authority"]["sides"]["right"]["cuffY98M"] == pytest.approx(
        .2259984165430069, abs=1e-12)
    assert ranger_legs["Sidelace Breeches"]["openBoundaryAudit"][
        "boundaryVertices"] == 70
    assert ranger_legs["GeneratedLegBackingWithBoots"]["openBoundaryAudit"][
        "boundaryVertices"] == 327
    assert ranger_report["boots"]["clip"]["openBoundaryAudit"][
        "boundaryVertices"] == 215
    assert ranger_report["boots"]["componentDisposition"][
        "componentCount"] == 10
    assert ranger_report["boots"]["componentDisposition"][
        "removedComponentLabels"] == []
    assert ranger_report["boots"]["visibleMeshSource"] == (
        ranger_report["boots"]["visibleMeshOutput"])


def test_authoring_refuses_a_production_output_path():
    prospective = (ROOT / "godot-client/assets/actors/native/races/"
                   "cuff-fit-output")
    with pytest.raises(ValueError, match="Refusing production output"):
        cuff.validate_output_path(prospective)

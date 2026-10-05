"""Static provenance checks for the coverage-active Orun neck mask."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "eloria-assets/tools"))

import verify_orun_neck_apron_mask as verifier  # noqa: E402


ASSET = ROOT / "godot-client/assets/actors/native/races/orun_male.glb"
MANIFEST = ROOT / "eloria-assets/qa/orun-male-neck-apron-mask.json"


def test_pristine_asset_and_runtime_registry_match_reviewed_manifest():
    report = verifier.verify(ROOT, MANIFEST)
    assert report == {
        "assetSHA256": (
            "9044aebf2ea13cf82a9bdb40641481115e25521ec02e8a78df760a9b01299fd8"
        ),
        "profile": {
            "id": "orun-male-rear-neck-v1",
            "version": 1,
            "sourceSHA256": (
                "9044aebf2ea13cf82a9bdb40641481115e25521ec02e8a78df760a9b01299fd8"
            ),
        },
        "maskedFaceCount": 88,
        "unmatchedEdges": 0,
        "unmatchedCopies": 0,
        "runtimeSurfaceFingerprintSHA256": (
            "580ab6ee1d57c3cc98369636e872556bbe2a6e1d290c86270c31fcf985dd5446"
        ),
        "rawRuntimeSurfaceFingerprintSHA256": (
            "adadf7459870edb2824a2010e68656f7272c382d76621c216594cba95dedf07b"
        ),
        "permanentAssetMutation": False,
    }


def test_rejected_permanent_candidate_is_not_installed():
    manifest = verifier.load_manifest(MANIFEST)
    installed = hashlib.sha256(ASSET.read_bytes()).hexdigest()
    assert installed == manifest["sourceSHA256"]
    assert installed != manifest["rejectedPermanentCandidate"]["sha256"]
    assert manifest["permanentAssetMutation"] is False
    assert "bare and unequipped" in manifest[
        "rejectedPermanentCandidate"]["reason"]


def test_runtime_parser_scopes_values_to_reviewed_profile():
    manifest = verifier.load_manifest(MANIFEST)
    source = '''
const PROFILE_REGISTRY := {
    "decoy-profile": {
        "id": "decoy-profile",
        "version": 99,
        "rearFaceMasks": [{
            "surface": 99,
            "sourceRole": "decoy",
            "baseFaceCount": 999,
            "expectedVertexCount": 999,
            "expectedIndexCount": 999,
            "surfaceFingerprintSHA256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "rawSurfaceFingerprintSHA256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "faces": [999],
        }],
    },
    "orun-male-rear-neck-v1": {
        "id": "orun-male-rear-neck-v1",
        "version": 1,
        "rearFaceMasks": [{
            "surface": 3,
            "sourceRole": "shared_neck",
            "baseFaceCount": 567,
            "expectedVertexCount": 1701,
            "expectedIndexCount": 1701,
            "surfaceFingerprintSHA256": "580ab6ee1d57c3cc98369636e872556bbe2a6e1d290c86270c31fcf985dd5446",
            "rawSurfaceFingerprintSHA256": "adadf7459870edb2824a2010e68656f7272c382d76621c216594cba95dedf07b",
            "faces": [0, 14, 546],
        }],
    },
}
'''
    assert verifier._runtime_registry(source, manifest) == {
        "id": "orun-male-rear-neck-v1",
        "version": 1,
        "surface": 3,
        "vertexCount": 1701,
        "indexCount": 1701,
        "baseFaceCount": 567,
        "surfaceFingerprintSHA256": (
            "580ab6ee1d57c3cc98369636e872556bbe2a6e1d290c86270c31fcf985dd5446"
        ),
        "rawSurfaceFingerprintSHA256": (
            "adadf7459870edb2824a2010e68656f7272c382d76621c216594cba95dedf07b"
        ),
        "faces": [0, 14, 546],
    }


def test_runtime_parser_rejects_duplicate_reviewed_profile():
    manifest = verifier.load_manifest(MANIFEST)
    runtime = (ROOT / "godot-client/src/actors/torso_body_cover.gd").read_text(
        encoding="utf-8")
    profile = verifier._profile_container(
        runtime, manifest["profile"]["id"])
    duplicate = runtime.replace(
        "const PROFILE_REGISTRY := {",
        'const PROFILE_REGISTRY := {\n\t"orun-male-rear-neck-v1": ' + profile + ",",
        1)
    with pytest.raises(ValueError, match="exactly one registry entry"):
        verifier._runtime_registry(duplicate, manifest)


def test_manifest_face_and_selector_drift_fail_closed(tmp_path):
    manifest = verifier.load_manifest(MANIFEST)
    bad_faces = copy.deepcopy(manifest)
    bad_faces["maskedFaces"][0] = bad_faces["maskedFaces"][1]
    bad_path = tmp_path / "bad-faces.json"
    bad_path.write_text(json.dumps(bad_faces), encoding="utf-8")
    with pytest.raises(ValueError, match="sorted and unique"):
        verifier.load_manifest(bad_path)

    bad_selector = copy.deepcopy(manifest)
    bad_selector["profile"]["id"] = "unreviewed"
    selector_path = tmp_path / "bad-selector.json"
    selector_path.write_text(json.dumps(bad_selector), encoding="utf-8")
    with pytest.raises(ValueError, match="compact profile"):
        verifier.verify(ROOT, selector_path)

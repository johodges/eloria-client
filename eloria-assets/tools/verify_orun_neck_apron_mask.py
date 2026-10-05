"""Verify the coverage-active Orun rear-neck mask contract.

The reviewed face set is not baked into ``orun_male.glb``.  A permanent index
rewrite passed equipped screenshots but opened the neck when the torso was
unequipped.  Production therefore keeps the pristine, closed GLB and applies
the reviewed rows only to TorsoBodyCover's cached covered mesh.

This verifier pins the pristine asset, GLB primitive/face order, compact model
selector, single runtime registry and dependent metadata.  It is read-only.

The runtime registry carries two surface fingerprints: the editor's imported
scene and the raw GLTFDocument parse an exported client uses.  Both list the
same faces in the same order (``runtimeRoutes`` in the manifest), so one face
list serves both.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "eloria-assets/tools"))

import equipment_authoring as ea  # noqa: E402
from verify_shared_player_bodies import neck_join_checks, primitives  # noqa: E402

DEFAULT_MANIFEST = ROOT / "eloria-assets/qa/orun-male-neck-apron-mask.json"
MODELS = ROOT / "godot-client/data/actors/models.json"
CATALOG = ROOT / "godot-client/data/actors/native_asset_catalog.json"
FACE_MASKS = ROOT / "godot-client/assets/actors/native/face_masks/manifest.json"
RUNTIME = ROOT / "godot-client/src/actors/torso_body_cover.gd"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    faces = manifest.get("maskedFaces", [])
    triangles = manifest.get("sourceTriangles", [])
    if manifest.get("version") != 2:
        raise ValueError("unsupported Orun neck-apron mask manifest version")
    if manifest.get("race") != "orun_male":
        raise ValueError("manifest is not for orun_male")
    if manifest.get("installMode") != "coverage-active-runtime-index-filter":
        raise ValueError("manifest no longer describes the runtime-only mask")
    if manifest.get("permanentAssetMutation") is not False:
        raise ValueError("permanent Orun asset mutation is forbidden")
    if len(faces) != manifest.get("maskedFaceCount") or len(faces) != len(triangles):
        raise ValueError("manifest face/triangle counts disagree")
    if faces != sorted(set(faces)):
        raise ValueError("manifest faces must be sorted and unique")
    if any(triangle != [face * 3, face * 3 + 1, face * 3 + 2]
           for face, triangle in zip(faces, triangles)):
        raise ValueError("manifest source triangle rows drifted")
    return manifest


def _balanced_container(source: str, start: int, opener: str,
                        closer: str) -> str:
    """Return one balanced GDScript container, ignoring strings/comments."""
    if start >= len(source) or source[start] != opener:
        raise ValueError(f"expected {opener!r} at runtime registry container")
    depth = 0
    quoted = False
    escaped = False
    comment = False
    for offset in range(start, len(source)):
        character = source[offset]
        if comment:
            if character == "\n":
                comment = False
            continue
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
            continue
        if character == "#":
            comment = True
        elif character == '"':
            quoted = True
        elif character == opener:
            depth += 1
        elif character == closer:
            depth -= 1
            if depth == 0:
                return source[start:offset + 1]
    raise ValueError(f"unterminated runtime registry container {opener!r}")


def _named_container(source: str, key: str, opener: str,
                     closer: str) -> str:
    matches = list(re.finditer(
        rf'"{re.escape(key)}"\s*:\s*{re.escape(opener)}', source))
    if len(matches) != 1:
        raise ValueError(
            f"runtime key {key!r} must define exactly one {opener}{closer} container")
    return _balanced_container(source, matches[0].end() - 1, opener, closer)


def _profile_container(source: str, profile_id: str) -> str:
    # Match a dictionary key, not the identical string stored in its `id` field.
    matches = list(re.finditer(
        rf'(?m)^[ \t]*"{re.escape(profile_id)}"\s*:\s*\{{', source))
    if len(matches) != 1:
        raise ValueError(
            f"runtime profile {profile_id!r} must define exactly one registry entry")
    return _balanced_container(source, matches[0].end() - 1, "{", "}")


def _required_string(source: str, key: str) -> str:
    matches = re.findall(
        rf'"{re.escape(key)}"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"',
        source)
    if len(matches) != 1:
        raise ValueError(f"runtime key {key!r} must appear exactly once")
    return matches[0]


def _required_int(source: str, key: str) -> int:
    matches = re.findall(rf'"{re.escape(key)}"\s*:\s*(\d+)', source)
    if len(matches) != 1:
        raise ValueError(f"runtime key {key!r} must appear exactly once")
    return int(matches[0])


def _dictionary_items(container: str) -> list[str]:
    """Return top-level dictionary values from a GDScript array literal."""
    items: list[str] = []
    offset = 1
    while offset < len(container) - 1:
        match = re.search(r"\{", container[offset:])
        if not match:
            break
        start = offset + match.start()
        item = _balanced_container(container, start, "{", "}")
        items.append(item)
        offset = start + len(item)
    return items


def _runtime_registry(source: str, manifest: dict) -> dict:
    profile = manifest["profile"]
    profile_source = _profile_container(source, profile["id"])
    if _required_string(profile_source, "id") != profile["id"]:
        raise ValueError("runtime profile key/id disagree")

    masks_source = _named_container(
        profile_source, "rearFaceMasks", "[", "]")
    masks = [
        item for item in _dictionary_items(masks_source)
        if _required_int(item, "surface") == manifest["primitive"]
        and _required_string(item, "sourceRole") == manifest["sourceRole"]
    ]
    if len(masks) != 1:
        raise ValueError(
            "runtime profile must contain exactly one reviewed surface mask")
    mask_source = masks[0]
    fingerprint = _required_string(mask_source, "surfaceFingerprintSHA256")
    if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise ValueError("runtime surface fingerprint is invalid")
    raw_fingerprint = _required_string(mask_source, "rawSurfaceFingerprintSHA256")
    if not re.fullmatch(r"[0-9a-f]{64}", raw_fingerprint):
        raise ValueError("runtime raw surface fingerprint is invalid")
    faces_source = _named_container(mask_source, "faces", "[", "]")
    faces = [int(value) for value in re.findall(r"\d+", faces_source)]
    return {
        "id": profile["id"],
        "version": _required_int(profile_source, "version"),
        "surface": _required_int(mask_source, "surface"),
        "vertexCount": _required_int(mask_source, "expectedVertexCount"),
        "indexCount": _required_int(mask_source, "expectedIndexCount"),
        "baseFaceCount": _required_int(mask_source, "baseFaceCount"),
        "surfaceFingerprintSHA256": fingerprint,
        "rawSurfaceFingerprintSHA256": raw_fingerprint,
        "faces": faces,
    }


def verify(root: Path = ROOT, manifest_path: Path = DEFAULT_MANIFEST) -> dict:
    manifest = load_manifest(manifest_path)
    asset = root / manifest["asset"]
    digest = sha256(asset)
    if digest != manifest["sourceSHA256"]:
        raise ValueError(f"installed Orun asset is not pristine: {digest}")
    rejected = manifest["rejectedPermanentCandidate"]["sha256"]
    if digest == rejected:
        raise ValueError("rejected permanent Orun candidate is installed")
    if asset.stat().st_size != manifest["fileSizeBytes"]:
        raise ValueError("installed Orun asset size drifted")

    document, binary = ea.read_glb(asset)
    primitive = document["meshes"][manifest["mesh"]]["primitives"][
        manifest["primitive"]]
    if primitive.get("extras", {}).get("sourceRole") != manifest["sourceRole"]:
        raise ValueError("shared-neck primitive role drifted")
    if primitive["indices"] != manifest["indexAccessor"]:
        raise ValueError("shared-neck index accessor drifted")
    indices = ea.accessor_array(
        document, binary, primitive["indices"]).astype(int).reshape(-1, 3)
    positions = ea.accessor_array(
        document, binary, primitive["attributes"]["POSITION"])
    if len(positions) != manifest["baseVertexCount"]:
        raise ValueError("shared-neck vertex count drifted")
    if indices.size != manifest["baseIndexCount"]:
        raise ValueError("shared-neck index count drifted")
    if len(indices) != manifest["baseFaceCount"]:
        raise ValueError("shared-neck face count drifted")
    faces = np.asarray(manifest["maskedFaces"], dtype=np.int64)
    np.testing.assert_array_equal(indices[faces], manifest["sourceTriangles"])

    joins, attributes = neck_join_checks(list(primitives(document, binary)))
    if joins["unmatchedEdges"] != 0 or attributes["unmatchedCopies"] != 0:
        raise ValueError("pristine Orun neck topology is no longer closed")

    models = json.loads((root / MODELS.relative_to(ROOT)).read_text())
    owners = [(slug, entry["torsoBodyCover"])
              for slug, entry in models["models"].items()
              if "torsoBodyCover" in entry]
    expected_selector = {
        "id": manifest["profile"]["id"],
        "version": manifest["profile"]["version"],
        "sourceSHA256": manifest["sourceSHA256"],
    }
    if owners != [("orun_male", expected_selector)]:
        raise ValueError(f"Orun must be the sole compact profile owner: {owners}")
    if models["models"]["orun_male"]["scene"] != (
            "res://assets/actors/native/races/orun_male.glb"):
        raise ValueError("Orun model scene drifted")
    if models["models"]["orun_male"]["skinPalette"]["sourceSHA256"] != digest:
        raise ValueError("Orun skin-palette provenance drifted")

    catalog = json.loads((root / CATALOG.relative_to(ROOT)).read_text())
    if catalog["races"]["orun_male"]["sha256"] != digest:
        raise ValueError("Orun native-asset catalog hash drifted")
    masks = json.loads((root / FACE_MASKS.relative_to(ROOT)).read_text())
    if masks["orun_male"]["modelSHA256"] != digest:
        raise ValueError("Orun face-mask provenance drifted")

    runtime = _runtime_registry(
        (root / RUNTIME.relative_to(ROOT)).read_text(encoding="utf-8"), manifest)
    expected_runtime = {
        "id": manifest["profile"]["id"],
        "version": manifest["profile"]["version"],
        "surface": manifest["primitive"],
        "vertexCount": manifest["baseVertexCount"],
        "indexCount": manifest["baseIndexCount"],
        "baseFaceCount": manifest["baseFaceCount"],
        "surfaceFingerprintSHA256": manifest["profile"][
            "runtimeSurfaceFingerprintSHA256"],
        "rawSurfaceFingerprintSHA256": manifest["profile"][
            "rawRuntimeSurfaceFingerprintSHA256"],
        "faces": manifest["maskedFaces"],
    }
    if runtime != expected_runtime:
        raise ValueError("runtime registry and reviewed manifest disagree")
    return {
        "assetSHA256": digest,
        "profile": expected_selector,
        "maskedFaceCount": len(faces),
        "unmatchedEdges": joins["unmatchedEdges"],
        "unmatchedCopies": attributes["unmatchedCopies"],
        "runtimeSurfaceFingerprintSHA256": runtime[
            "surfaceFingerprintSHA256"],
        "rawRuntimeSurfaceFingerprintSHA256": runtime[
            "rawSurfaceFingerprintSHA256"],
        "permanentAssetMutation": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    print(json.dumps(verify(args.root, args.manifest), indent=2))


if __name__ == "__main__":
    main()

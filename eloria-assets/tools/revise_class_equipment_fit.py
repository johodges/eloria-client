#!/usr/bin/env python3
"""Bake the reviewed class silhouette and cuff fit into packed equipment.

The regular canonical fitter is the source of the revised torso geometry.
Torso finalization publishes that fresh, lower-cost geometry while retaining
the pinned production material slots and external image resources; draw count
stays fixed. It also moves only the generated leg/boot backing to the shared
cuff seam when a non-torso-only rebuild is explicitly requested.

Outputs are always written to a fresh review directory; installation remains
an explicit, separately reviewed copy operation.

    python revise_class_equipment_fit.py \
        --source <unmodified-packed-equipment> \
        --reference <fresh-refit-equipment> --output <fresh-review-directory>

``--source`` must be the reviewed packed baseline, not an output from an
earlier run.  The checked manifest validates every source, torso reference,
rig, and expected output hash before anything is accepted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import struct
from pathlib import Path

import numpy as np

import conform_equipment as ce
import equipment_authoring as ea
import limb_head_remap
import torso_remap


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "eloria-assets/qa/class-equipment-fit-baseline.json"
TORSOS = {
    "5:209": "militia_torso_armor_02",
    "5:225": "leather_ranger_torso_02",
    "5:216": "eloria_arcane_armor_01",
    "5:189": "amberwood_woodland_cuirass_06",
}
LEGS = {
    "4:179": "arcane_leg_armor_01",
}
BOOTS = {
    "6:192": "arcane_fantasy_boots_01",
}
RACES = ("luminous_male", "luminous_female")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def asset(base: Path, race: str, slug: str) -> Path:
    folder = base if race == "luminous_male" else base / "variants/luminous_female"
    return folder / f"{slug}.glb"


def asset_key(race: str, slug: str) -> str:
    prefix = "" if race == "luminous_male" else "variants/luminous_female/"
    return prefix + slug + ".glb"


def display_path(path: Path) -> str:
    resolved = path.resolve()
    return (resolved.relative_to(ROOT).as_posix()
            if resolved.is_relative_to(ROOT) else str(resolved))


def named_mesh(document: dict, name: str) -> dict:
    matches = [entry for entry in document["meshes"] if entry["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"Expected one {name!r} mesh, found {len(matches)}")
    return matches[0]


def arm_share(document: dict, binary: bytes, primitive: dict) -> np.ndarray:
    """Return each packed vertex's left/right shoulder-to-hand influence."""
    attributes = primitive["attributes"]
    joints = ea.accessor_array(document, binary, attributes["JOINTS_0"])
    weights = ea.accessor_array(document, binary, attributes["WEIGHTS_0"])
    skin_nodes = document["skins"][0]["joints"]
    names = [document["nodes"][node].get("name", "") for node in skin_nodes]
    result = np.zeros((len(joints), 2), dtype=float)
    for column, side in enumerate(("l", "r")):
        indices = [names.index(name) for name in (
            f"clavicle_{side}", f"upperarm_{side}",
            f"lowerarm_{side}", f"hand_{side}") if name in names]
        result[:, column] = np.where(
            np.isin(joints, indices), weights, 0.).sum(axis=1)
    return result


def locked_arm_rows(points: np.ndarray, rig, share: np.ndarray,
                    locked_from: float) -> np.ndarray:
    """Rows whose canonical arm travel belongs to the immutable cuff tail."""
    result = np.zeros(len(points), dtype=bool)
    for column, side in enumerate(("l", "r")):
        own = share[:, column] > .5
        root = rig.origin("upperarm_" + side)
        axis = rig.origin("hand_" + side) - root
        travel = (points - root) @ axis / float(axis @ axis)
        result |= own & (travel >= locked_from)
    return result


def validate_torso_correspondence(source: Path, reference: Path) -> None:
    """Prove the fresh refit's vertex domain matches the packed baseline.

    The remapper may remove different sleeve-seam faces, so its index chain is
    intentionally not copied. Every vertex-domain attribute other than the
    revised POSITION/NORMAL pair must nevertheless retain its semantic and
    shape. UVs and all non-skin vertex attributes remain exact. The fresh
    canonical fitter may legitimately requantize a few skin weights, but the
    checked reference hash pins that reviewed mapping and those weights are
    never copied into the packed output.
    """
    document, binary = ea.read_glb(source)
    candidate, candidate_binary = ea.read_glb(reference)
    if ([entry["name"] for entry in document["meshes"]]
            != [entry["name"] for entry in candidate["meshes"]]):
        raise ValueError(f"Mesh sequence differs: {source}")
    original_mesh, revised_mesh = document["meshes"][0], candidate["meshes"][0]
    if len(original_mesh["primitives"]) != len(revised_mesh["primitives"]):
        raise ValueError(f"Visible primitive count differs: {source}")
    for primitive_index, (before, after) in enumerate(zip(
            original_mesh["primitives"], revised_mesh["primitives"])):
        before_meta = {key: value for key, value in before.items()
                       if key not in {"attributes", "indices"}}
        after_meta = {key: value for key, value in after.items()
                      if key not in {"attributes", "indices"}}
        if before_meta != after_meta:
            raise ValueError(
                f"Primitive metadata differs at {source}:{primitive_index}")
        before_attributes = before["attributes"]
        after_attributes = after["attributes"]
        if set(before_attributes) != set(after_attributes):
            raise ValueError(
                f"Attribute semantics differ at {source}:{primitive_index}")
        for semantic in before_attributes:
            if semantic in {"POSITION", "NORMAL"}:
                continue
            before_values = ea.accessor_array(
                document, binary, before_attributes[semantic])
            after_values = ea.accessor_array(
                candidate, candidate_binary, after_attributes[semantic])
            if before_values.shape != after_values.shape:
                raise ValueError(
                    f"{semantic} shape differs at {source}:{primitive_index}")
            if (semantic not in {"JOINTS_0", "WEIGHTS_0"}
                    and not np.array_equal(before_values, after_values)):
                raise ValueError(
                    f"{semantic} vertex correspondence differs at "
                    f"{source}:{primitive_index}")
        before_positions = ea.accessor_array(
            document, binary, before_attributes["POSITION"])
        after_positions = ea.accessor_array(
            candidate, candidate_binary, after_attributes["POSITION"])
        if before_positions.shape != after_positions.shape:
            raise ValueError(
                f"POSITION count differs at {source}:{primitive_index}")


def validate_resources(paths: list[Path]) -> dict[str, str]:
    """Pin every external packed texture by its content-addressed filename."""
    resources = {}
    for source in paths:
        document, _ = ea.read_glb(source)
        for image in document.get("images", []):
            if "uri" not in image or "bufferView" in image:
                raise ValueError(f"Expected external packed image resource: {source}")
            resource = (source.parent / image["uri"]).resolve()
            match = re.fullmatch(
                r"canonical_([0-9a-f]{64})\.[A-Za-z0-9]+", resource.name)
            if not match or not resource.is_file():
                raise ValueError(f"Missing or non-content-addressed image: {resource}")
            actual = digest(resource)
            if actual != match.group(1):
                raise ValueError(f"Content-addressed image hash mismatch: {resource}")
            resources[display_path(resource)] = actual
    return dict(sorted(resources.items()))


def validate_inputs(source_root: Path, reference_root: Path,
                    manifest: dict, validate_reference_hashes: bool = True
                    ) -> tuple[dict[str, str], dict[str, str]]:
    if manifest.get("version") != 1:
        raise ValueError("Unsupported class-equipment fit manifest version")
    all_slugs = set(TORSOS.values()) | set(LEGS.values()) | set(BOOTS.values())
    source_keys = {asset_key(race, slug) for race in RACES for slug in all_slugs}
    reference_keys = {
        asset_key(race, slug) for race in RACES for slug in TORSOS.values()}
    rig_keys = {race + ".glb" for race in RACES}
    for section, expected in (("source", source_keys),
                              ("reference", reference_keys),
                              ("output", source_keys),
                              ("rig", rig_keys)):
        actual = set(manifest.get(section, {}))
        if actual != expected:
            raise ValueError(
                f"Manifest {section} roster differs; missing "
                f"{sorted(expected - actual)}, extra {sorted(actual - expected)}")
    source_paths = []
    for key in sorted(source_keys):
        path = source_root / Path(key)
        if not path.is_file() or digest(path) != manifest["source"][key]:
            raise ValueError(f"Packed baseline hash mismatch: {path}")
        source_paths.append(path)
    resource_hashes = validate_resources(source_paths)
    for key in sorted(reference_keys):
        path = reference_root / Path(key)
        if (not path.is_file()
                or (validate_reference_hashes
                    and digest(path) != manifest["reference"][key])):
            raise ValueError(f"Torso reference hash mismatch: {path}")
    rig_hashes = {}
    for race in RACES:
        path = ce.RACES / f"{race}.glb"
        rig_hashes[race] = digest(path)
        if rig_hashes[race] != manifest["rig"][path.name]:
            raise ValueError(f"Canonical rig hash mismatch: {path}")
    for race in RACES:
        for slug in TORSOS.values():
            validate_torso_correspondence(
                asset(source_root, race, slug),
                asset(reference_root, race, slug))
    return rig_hashes, resource_hashes


def copy_resources(source: Path, target: Path, output: Path) -> list[str]:
    """Copy the packed asset's existing external images beside a candidate."""
    document, _ = ea.read_glb(source)
    copied = []
    for image in document.get("images", []):
        if "uri" not in image or "bufferView" in image:
            raise ValueError(f"Expected existing external image resources: {source}")
        old = (source.parent / image["uri"]).resolve()
        new = (target.parent / image["uri"]).resolve()
        if not new.is_relative_to(output.resolve()):
            raise ValueError(f"Image resource escapes review output: {new}")
        new.parent.mkdir(parents=True, exist_ok=True)
        if new.exists():
            if new.read_bytes() != old.read_bytes():
                raise ValueError(f"Shared image collision: {new}")
        else:
            shutil.copyfile(old, new)
        copied.append(new.relative_to(output).as_posix())
    return copied


def write_external_glb(document: dict, binary: bytes, target: Path) -> None:
    """Write one deterministic GLB while retaining external image URIs."""
    encoded = json.dumps(document, separators=(",", ":")).encode("utf-8")
    encoded += b" " * (-len(encoded) % 4)
    binary += b"\0" * (-len(binary) % 4)
    total = 12 + 8 + len(encoded) + 8 + len(binary)
    payload = (struct.pack("<4sII", b"glTF", 2, total)
               + struct.pack("<II", len(encoded), 0x4E4F534A) + encoded
               + struct.pack("<II", len(binary), 0x004E4942) + binary)
    target.write_bytes(payload)


def rebuilt_torso_candidate(source: Path, reference: Path,
                            target: Path) -> dict:
    """Publish freshly authored geometry with pinned production textures.

    The generated backing in the fresh reference has intentionally different,
    smaller topology, so it cannot be copied through the legacy fixed-accessor
    path.  Materials, samplers, texture slots, skin/draw count, and external
    production image resources remain pinned; only the rebuilt geometry and
    its matching skin arrays come from the reviewed reference.
    """
    document, source_binary = ea.read_glb(source)
    candidate, candidate_binary = ea.read_glb(reference)
    if ([mesh["name"] for mesh in document["meshes"]]
            != [mesh["name"] for mesh in candidate["meshes"]]):
        raise ValueError(f"Mesh sequence differs: {source}")
    if [len(mesh["primitives"]) for mesh in document["meshes"]] != [
            len(mesh["primitives"]) for mesh in candidate["meshes"]]:
        raise ValueError(f"Draw count differs: {source}")
    for key in ("materials", "textures", "samplers"):
        if document.get(key) != candidate.get(key):
            raise ValueError(f"Packed {key} contract differs: {source}")
    if len(document.get("images", [])) != len(candidate.get("images", [])):
        raise ValueError(f"Packed image-slot count differs: {source}")
    source_triangles = sum(
        document["accessors"][primitive["indices"]]["count"] // 3
        for mesh in document["meshes"] for primitive in mesh["primitives"])
    rebuilt_triangles = sum(
        candidate["accessors"][primitive["indices"]]["count"] // 3
        for mesh in candidate["meshes"] for primitive in mesh["primitives"])
    if rebuilt_triangles > source_triangles * 1.02:
        raise ValueError(
            f"Rebuilt torso exceeds the two-percent per-piece triangle cap: "
            f"{source_triangles} -> "
            f"{rebuilt_triangles}")
    # Retain the exact production texture encoding and content-addressed URIs.
    candidate["images"] = document["images"]
    candidate["materials"] = document["materials"]
    candidate["textures"] = document["textures"]
    candidate["samplers"] = document["samplers"]
    write_external_glb(candidate, candidate_binary, target)
    return {
        "strategy": "fresh-reference-geometry-pinned-production-textures",
        "drawCount": sum(len(mesh["primitives"])
                         for mesh in candidate["meshes"]),
        "sourceTriangles": source_triangles,
        "outputTriangles": rebuilt_triangles,
        "triangleDelta": rebuilt_triangles - source_triangles,
        "documentPreserved": False,
        "changedBytes": abs(target.stat().st_size - source.stat().st_size),
        "sourceBinaryBytes": len(source_binary),
    }


def torso_candidate(source: Path, reference: Path, target: Path,
                    rig, slug: str) -> dict:
    """Transfer a fresh fitter result into an existing packed torso."""
    document, binary = ea.read_glb(source)
    candidate, candidate_binary = ea.read_glb(reference)
    if ([entry["name"] for entry in document["meshes"]]
            != [entry["name"] for entry in candidate["meshes"]]):
        raise ValueError(f"Mesh sequence differs: {source}")
    original_mesh, revised_mesh = document["meshes"][0], candidate["meshes"][0]
    if len(original_mesh["primitives"]) != len(revised_mesh["primitives"]):
        raise ValueError(f"Visible primitive count differs: {source}")

    updates = {}
    normal_reports = []
    orientation_reports = []
    limiter_reports = []
    visible_faces_by_side = [[], []]
    for before, after in zip(original_mesh["primitives"], revised_mesh["primitives"]):
        before_uv = ea.accessor_array(
            document, binary, before["attributes"]["TEXCOORD_0"])
        after_uv = ea.accessor_array(
            candidate, candidate_binary, after["attributes"]["TEXCOORD_0"])
        if not np.array_equal(before_uv, after_uv):
            raise ValueError(f"Visible source vertex order differs: {source}")

        position = before["attributes"]["POSITION"]
        replacement = ea.accessor_array(
            candidate, candidate_binary, after["attributes"]["POSITION"]).copy()
        original = ea.accessor_array(document, binary, position)
        if replacement.shape != original.shape:
            raise ValueError(f"Visible POSITION count differs: {source}")
        # JSON is intentionally retained byte-for-byte, including bounds.
        spec = document["accessors"][position]
        replacement = np.clip(
            replacement, np.asarray(spec["min"]), np.asarray(spec["max"]))
        triangles = ea.accessor_array(
            document, binary, before["indices"]).reshape(-1, 3)
        share = arm_share(document, binary, before)
        replacement, limiter = torso_remap.constrain_deformation_orientation(
            original, replacement, triangles)
        for column in range(2):
            arm_faces = share[triangles, column].max(axis=1) > .25
            if arm_faces.any():
                visible_faces_by_side[column].append(
                    replacement[triangles[arm_faces]])
        limiter_reports.append(limiter)
        orientation_reports.append(torso_remap.require_safe_deformation(
            original, replacement, triangles))
        updates[position] = replacement

        normal = before["attributes"]["NORMAL"]
        revised_normals, normal_report = (
            torso_remap.transport_normals_across_deformation(
                original, replacement,
                ea.accessor_array(document, binary, normal), triangles))
        updates[normal] = revised_normals
        normal_reports.append(normal_report)

    visible_faces_by_side = [
        (np.concatenate(parts, axis=0)
         if parts else np.empty((0, 3, 3), dtype=float))
        for parts in visible_faces_by_side]
    backing_reports = []
    backing = named_mesh(document, "GeneratedArmorBacking")
    profile = torso_remap.PACKED_BACKING_RELATIVE_PROFILES[slug]
    for primitive in backing["primitives"]:
        position = primitive["attributes"]["POSITION"]
        normal = primitive["attributes"]["NORMAL"]
        original = ea.accessor_array(document, binary, position)
        replacement = original.astype(float).copy()
        share = arm_share(document, binary, primitive)
        locked = locked_arm_rows(
            original, rig, share, torso_remap.SLEEVE_PROFILE_LOCK_T)
        fit = torso_remap.tighten_arm_silhouette(
            replacement, rig, share, np.full(len(replacement), -1, dtype=int),
            radial_scale=profile, cap_inset=0.,
            locked_from=torso_remap.SLEEVE_PROFILE_LOCK_T)
        triangles = ea.accessor_array(
            document, binary, primitive["indices"]).reshape(-1, 3)
        clearance = torso_remap.seat_arm_backing_inside_visible(
            replacement, rig, share, visible_faces_by_side,
            triangles=triangles)
        if not np.array_equal(replacement[locked], original[locked]):
            raise ValueError(f"Backing cuff lock moved before safety gate: {source}")
        replacement, limiter = torso_remap.constrain_deformation_orientation(
            original, replacement, triangles)
        if not np.array_equal(replacement[locked], original[locked]):
            raise ValueError(f"Backing cuff lock moved in safety gate: {source}")
        orientation = torso_remap.require_safe_deformation(
            original, replacement, triangles)
        final_clearance = torso_remap.seat_arm_backing_inside_visible(
            replacement.copy(), rig, share, visible_faces_by_side,
            enforce=False)
        revised_normals, normal_report = (
            torso_remap.transport_normals_across_deformation(
                original, replacement,
                ea.accessor_array(document, binary, normal), triangles))
        # The lock is a packed-data contract as well as a silhouette contract.
        authored_normals = ea.accessor_array(document, binary, normal)
        revised_normals[locked] = authored_normals[locked]
        updates[position] = replacement
        updates[normal] = revised_normals
        backing_reports.append({
            "fit": fit,
            "clearance": clearance,
            "finalClearance": final_clearance,
            "lockedRows": int(locked.sum()),
            "orientation": orientation,
            "orientationLimiter": limiter,
            "normalTransport": normal_report,
        })

    report = torso_remap.position_only_revision(source, target, updates)
    report.update({
        "normalTransport": normal_reports,
        "orientation": orientation_reports,
        "orientationLimiter": limiter_reports,
        "backingFit": backing_reports,
    })
    return report


def cuff_candidate(source: Path, target: Path, rig, kind: str) -> dict:
    """Move only a generated alternate lining to the shared cuff seam."""
    document, binary = ea.read_glb(source)
    if kind == "legs":
        alternate = named_mesh(document, "GeneratedLegBackingWithBoots")
        keep_above = True
    elif kind == "boots":
        alternate = named_mesh(document, "GeneratedBootBackingWithLegs")
        keep_above = False
    else:
        raise ValueError(f"Unsupported cuff kind: {kind}")
    seam = limb_head_remap.FITTED_BOOT_CUFF_SEAM * rig.fit_scale

    updates = {}
    normal_reports = []
    orientation_reports = []
    limiter_reports = []
    for primitive in alternate["primitives"]:
        position = primitive["attributes"]["POSITION"]
        original = ea.accessor_array(document, binary, position)
        replacement = limb_head_remap.compress_cuff_band(
            original, seam, keep_above)
        triangles = ea.accessor_array(
            document, binary, primitive["indices"]).reshape(-1, 3)
        replacement, limiter = torso_remap.constrain_deformation_orientation(
            original, replacement, triangles)
        limiter_reports.append(limiter)
        orientation_reports.append(torso_remap.require_safe_deformation(
            original, replacement, triangles))
        updates[position] = replacement

        normal = primitive["attributes"]["NORMAL"]
        revised_normals, normal_report = (
            torso_remap.transport_normals_across_deformation(
                original, replacement,
                ea.accessor_array(document, binary, normal), triangles))
        updates[normal] = revised_normals
        normal_reports.append(normal_report)

    report = torso_remap.position_only_revision(source, target, updates)
    report.update({
        "seam": seam,
        "keepAbove": keep_above,
        "normalTransport": normal_reports,
        "orientation": orientation_reports,
        "orientationLimiter": limiter_reports,
    })
    return report


def build(source_root: Path, reference_root: Path, output: Path,
          manifest: dict, kinds=("torso", "legs", "boots"),
          enforce_reference_hashes: bool = True,
          enforce_output_hashes: bool = True) -> tuple[
              list[dict], dict[str, str], dict[str, str]]:
    if output.exists():
        raise FileExistsError(f"Use a fresh review output: {output}")
    # Complete provenance and correspondence validation happens before the
    # output directory is created, so a bad external input cannot leave a
    # plausible-looking partial candidate tree.
    rig_hashes, resource_hashes = validate_inputs(
        source_root, reference_root, manifest, enforce_reference_hashes)
    output.mkdir(parents=True)
    records = []
    for race in RACES:
        rig = ea.load_rig(ce.RACES / f"{race}.glb", ce.BODY_MESH)
        for kind, roster in (("torso", TORSOS), ("legs", LEGS), ("boots", BOOTS)):
            if kind not in kinds:
                continue
            for key, slug in roster.items():
                source = asset(source_root, race, slug)
                target = asset(output, race, slug)
                target.parent.mkdir(parents=True, exist_ok=True)
                if kind == "torso":
                    reference = asset(reference_root, race, slug)
                    report = rebuilt_torso_candidate(
                        source, reference, target)
                    report["referenceSHA256"] = digest(reference)
                else:
                    report = cuff_candidate(source, target, rig, kind)
                key_path = asset_key(race, slug)
                output_hash = digest(target)
                if (enforce_output_hashes
                        and output_hash != manifest["output"][key_path]):
                    raise ValueError(
                        f"Reviewed output hash mismatch for {key_path}: "
                        f"{output_hash}")
                report.update({
                    "race": race,
                    "kind": kind,
                    "key": key,
                    "slug": slug,
                    "source": display_path(source),
                    "sourceSHA256": digest(source),
                    "rigSHA256": rig_hashes[race],
                    "outputSHA256": output_hash,
                    "resources": copy_resources(source, target, output),
                })
                records.append(report)
                print(f"{race:<16} {kind:<6} {slug}", flush=True)
    torso_records = [record for record in records if record["kind"] == "torso"]
    if (torso_records and sum(record["outputTriangles"] for record in torso_records)
            > sum(record["sourceTriangles"] for record in torso_records)):
        raise ValueError("Rebuilt torso set increases aggregate triangle cost")
    return records, rig_hashes, resource_hashes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True,
                        help="unmodified reviewed packed equipment root")
    parser.add_argument("--reference", type=Path, required=True,
                        help="fresh canonical refit root used for torso positions")
    parser.add_argument("--output", type=Path, required=True,
                        help="fresh review directory; never installs automatically")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST,
                        help="checked baseline/reference/rig/output SHA-256 manifest")
    parser.add_argument("--torsos-only", action="store_true",
                        help="build the eight torso outputs; leave legs/boots untouched")
    parser.add_argument("--refresh-hashes", action="store_true",
                        help="permit new reviewed reference/output hashes for manifest refresh")
    arguments = parser.parse_args()

    manifest_path = arguments.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records, rig_hashes, resource_hashes = build(
        arguments.source.resolve(), arguments.reference.resolve(),
        arguments.output.resolve(), manifest,
        kinds=(("torso",) if arguments.torsos_only
               else ("torso", "legs", "boots")),
        enforce_reference_hashes=not arguments.refresh_hashes,
        enforce_output_hashes=not arguments.refresh_hashes)
    report = arguments.output.resolve() / "fit-revision-report.json"
    tool_paths = [Path(__file__), Path(torso_remap.__file__),
                  Path(limb_head_remap.__file__), Path(ea.__file__), Path(ce.__file__)]
    report_value = {
        "manifest": display_path(manifest_path),
        "manifestSHA256": digest(manifest_path),
        "sourceRoot": display_path(arguments.source),
        "referenceRoot": display_path(arguments.reference),
        "rigSHA256": rig_hashes,
        "resourceSHA256": resource_hashes,
        "toolSHA256": {path.name: digest(path) for path in tool_paths},
        "assets": records,
    }
    report.write_text(json.dumps(report_value, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "assets": len(records),
        "changedBytes": sum(record["changedBytes"] for record in records),
        "output": str(arguments.output.resolve()),
        "report": str(report),
    }, indent=2))


if __name__ == "__main__":
    main()

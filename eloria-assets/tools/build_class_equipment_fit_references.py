#!/usr/bin/env python3
"""Rebuild the eight pinned torso references used by the class-fit finalizer.

Extract the two anatomy GLBs from the manifest's ``anatomyGitCommit`` first,
then provide the directory that contains them. The existing reviewed authoring
sources are read locally; this tool does not call Meshy or spend credits.

    python build_class_equipment_fit_references.py \
        --anatomy <extracted-races-directory> --output <fresh-stage>

The packed reference root printed on success can be passed directly to
``revise_class_equipment_fit.py --reference``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import conform_equipment as ce
import equipment_authoring as ea
import import_generated_equipment as batch
import pack_canonical_equipment as pack
import revise_class_equipment_fit as revision
import torso_remap


ROOT = Path(__file__).resolve().parents[2]
RACES = revision.RACES
SLUGS = set(revision.TORSOS.values())


def validate_inputs(anatomy: Path, manifest: dict) -> dict:
    if manifest.get("version") != 1:
        raise ValueError("Unsupported class-equipment fit manifest version")
    if set(manifest.get("anatomy", {})) != {race + ".glb" for race in RACES}:
        raise ValueError("Manifest anatomy roster differs")
    anatomy_hashes = {}
    for race in RACES:
        path = anatomy / f"{race}.glb"
        anatomy_hashes[race] = revision.digest(path)
        if anatomy_hashes[race] != manifest["anatomy"][path.name]:
            raise ValueError(f"Anatomy hash mismatch: {path}")

    pieces = {piece.slug: piece for piece in batch.roster()
              if piece.slug in SLUGS}
    if set(pieces) != SLUGS:
        raise ValueError(f"Missing torso authoring sources: {sorted(SLUGS - set(pieces))}")
    if set(manifest.get("authoringSource", {})) != SLUGS:
        raise ValueError("Manifest authoring-source roster differs")
    for slug, piece in pieces.items():
        spec = manifest["authoringSource"][slug]
        expected_path = (ROOT.parent / spec["path"]).resolve()
        if piece.source.resolve() != expected_path:
            raise ValueError(
                f"Authoring source path differs for {slug}: {piece.source}")
        if revision.digest(piece.source) != spec["sha256"]:
            raise ValueError(f"Authoring source hash mismatch: {piece.source}")
    return {"anatomySHA256": anatomy_hashes, "pieces": pieces}


def build(anatomy: Path, output: Path, manifest: dict,
          enforce_output_hashes: bool = True) -> list[dict]:
    if output.exists():
        raise FileExistsError(f"Use a fresh reference stage: {output}")
    inputs = validate_inputs(anatomy, manifest)
    output.mkdir(parents=True)
    raw_root = output / "raw"
    reports = []
    for race in RACES:
        rig = ea.load_rig(anatomy / f"{race}.glb", ce.BODY_MESH)
        for slug in sorted(SLUGS):
            piece = inputs["pieces"][slug]
            raw = raw_root / race / f"{slug}.glb"
            report = torso_remap.build(
                piece.source, raw, rig, piece.kind, piece.name,
                anatomy_reference=rig)
            relative = pack.PREFIX / (
                f"{slug}.glb" if race == "luminous_male"
                else f"variants/luminous_female/{slug}.glb")
            pack.pack_glb(raw, relative, output)
            target = output / relative
            pack.validate(target, race)
            key = revision.asset_key(race, slug)
            target_hash = revision.digest(target)
            if (enforce_output_hashes
                    and target_hash != manifest["reference"][key]):
                raise ValueError(
                    f"Pinned torso-reference hash mismatch for {key}: {target_hash}")
            report.update({
                "race": race,
                "slug": slug,
                "authoringSource": revision.display_path(piece.source),
                "authoringSourceSHA256": revision.digest(piece.source),
                "anatomySHA256": inputs["anatomySHA256"][race],
                "output": target.relative_to(output).as_posix(),
                "outputSHA256": target_hash,
            })
            reports.append(report)
            print(f"{race:<16} {slug}", flush=True)
    return reports


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anatomy", type=Path, required=True,
                        help="directory containing the two pinned anatomy GLBs")
    parser.add_argument("--output", type=Path, required=True,
                        help="fresh reference stage")
    parser.add_argument("--manifest", type=Path,
                        default=revision.DEFAULT_MANIFEST)
    parser.add_argument("--refresh-hashes", action="store_true",
                        help="permit new reviewed reference hashes for manifest refresh")
    arguments = parser.parse_args()

    manifest_path = arguments.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    reports = build(
        arguments.anatomy.resolve(), arguments.output.resolve(), manifest,
        enforce_output_hashes=not arguments.refresh_hashes)
    report_path = arguments.output.resolve() / "reference-build-report.json"
    report_path.write_text(json.dumps({
        "manifest": revision.display_path(manifest_path),
        "manifestSHA256": revision.digest(manifest_path),
        "anatomyGitCommit": manifest["anatomyGitCommit"],
        "assets": reports,
    }, indent=2) + "\n", encoding="utf-8")
    reference_root = arguments.output.resolve() / pack.PREFIX
    print(json.dumps({
        "assets": len(reports),
        "referenceRoot": str(reference_root),
        "report": str(report_path),
    }, indent=2))


if __name__ == "__main__":
    main()

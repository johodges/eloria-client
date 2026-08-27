#!/usr/bin/env python3
"""Validate Nymara regional source fidelity and concept-board coverage."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct

import numpy as np
from PIL import Image

from build_nymara_region_maps import INTERIORS, MAP_ROOT, REGIONS, SOURCE_ROOT


def glb_document(path: Path) -> dict:
    raw = path.read_bytes()
    if raw[:4] != b"glTF":
        raise ValueError("invalid GLB magic")
    version, total = struct.unpack_from("<II", raw, 4)
    if version != 2 or total != len(raw):
        raise ValueError("invalid GLB header")
    length, kind = struct.unpack_from("<II", raw, 12)
    if kind != 0x4E4F534A:
        raise ValueError("missing GLB JSON chunk")
    return json.loads(raw[20:20 + length])


def difference_hash(image: Image.Image) -> np.ndarray:
    sample = np.asarray(image.convert("L").resize((9, 8), Image.Resampling.LANCZOS))
    return (sample[:, 1:] > sample[:, :-1]).reshape(-1)


def validate_board(path: Path) -> dict:
    image = Image.open(path).convert("RGB")
    width, height = image.size
    if width < 1700 or height < 700:
        raise ValueError(f"detail board is below production review size: {image.size}")
    hashes = []
    variances = []
    for row in range(2):
        for column in range(5):
            panel = image.crop((round(column * width / 5), round(row * height / 2),
                                round((column + 1) * width / 5), round((row + 1) * height / 2)))
            hashes.append(difference_hash(panel))
            variances.append(float(np.asarray(panel.resize((64, 64))).var()))
    distances = [int(np.count_nonzero(hashes[a] != hashes[b]))
                 for a in range(10) for b in range(a + 1, 10)]
    if min(variances) < 120 or min(distances) < 3:
        raise ValueError("detail board contains a blank or duplicated perspective")
    return {"dimensions": [width, height], "panels": 10,
            "minimumPanelVariance": round(min(variances), 2),
            "minimumPairDistance": min(distances)}


def validate_region(slug: str) -> dict:
    directory = MAP_ROOT / slug
    errors = []
    manifest = {}
    document = {}
    board = {}
    try:
        manifest = json.loads((directory / "world.json").read_text())
    except Exception as error:
        errors.append(f"manifest: {error}")
    try:
        document = glb_document(directory / "world.glb")
    except Exception as error:
        errors.append(f"glb: {error}")
    board_path = directory / "references" / "00-concept-detail-board.png"
    board_status = manifest.get("conceptArt", {}).get("detailBoardStatus", "complete")
    if board_status == "regeneration-required":
        if board_path.exists():
            errors.append("concept board is present while marked regeneration-required")
    else:
        try:
            board = validate_board(board_path)
        except Exception as error:
            errors.append(f"concept board: {error}")

    node_names = {str(node.get("name", "")) for node in document.get("nodes", [])}
    if "Terrain_ELM_Authority" not in node_names:
        errors.append("GLB does not contain ELM-authority terrain")
    source = SOURCE_ROOT / f"{slug}.elm"
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else ""
    if source_hash != manifest.get("source", {}).get("sha256"):
        errors.append("manifest source hash does not match checked-in ELM")
    concept = manifest.get("conceptArt", {})
    checkpoints = concept.get("checkpoints", [])
    if concept.get("viewCount") != 10 or concept.get("panelGrid") != [5, 2] or len(checkpoints) != 10:
        errors.append("concept board does not declare exactly ten 5x2 checkpoints")
    evidence_matches = 0
    for checkpoint in checkpoints:
        evidence = checkpoint.get("evidenceNodes", [])
        if not evidence or any(node not in node_names for node in evidence):
            errors.append(f"panel {checkpoint.get('panel')} evidence node is absent from GLB")
        else:
            evidence_matches += 1
    if len(manifest.get("landmarks", [])) < 6:
        errors.append("fewer than six authored landmark instances")
    textures = {}
    for texture in ("region-basecolor.png", "region-normal.png", "region-orm.png"):
        path = directory / "textures" / texture
        try:
            image = Image.open(path)
            textures[texture] = list(image.size)
            if image.size != (512, 512):
                errors.append(f"{texture} is not 512x512")
        except Exception as error:
            errors.append(f"{texture}: {error}")
    primitives = sum(len(mesh.get("primitives", [])) for mesh in document.get("meshes", []))
    if primitives < 5:
        errors.append("GLB has insufficient terrain/landmark mesh coverage")
    return {"id": slug, "passed": not errors, "errors": errors,
            "sourceElmSha256": source_hash, "conceptBoard": board,
            "conceptBoardStatus": board_status, "conceptEvidenceMatches": evidence_matches,
            "glb": {"nodes": len(node_names), "meshes": len(document.get("meshes", [])),
                    "primitives": primitives}, "textures": textures}


def validate_interior(slug: str) -> dict:
    directory = MAP_ROOT / "interiors" / slug
    errors = []
    concept = {}
    board = {}
    try:
        concept = json.loads((directory / "concept.json").read_text())
    except Exception as error:
        errors.append(f"concept manifest: {error}")
    board_path = directory / "references" / "00-concept-detail-board.png"
    board_status = concept.get("conceptArt", {}).get("detailBoardStatus", "complete")
    if board_status == "regeneration-required":
        if board_path.exists():
            errors.append("concept board is present while marked regeneration-required")
    else:
        try:
            board = validate_board(board_path)
        except Exception as error:
            errors.append(f"concept board: {error}")
    source = SOURCE_ROOT / f"{slug}.elm"
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else ""
    if source_hash != concept.get("source", {}).get("sha256"):
        errors.append("concept source hash does not match checked-in ELM")
    art = concept.get("conceptArt", {})
    if art.get("viewCount") != 10 or art.get("panelGrid") != [5, 2] or len(art.get("subjects", [])) != 10:
        errors.append("interior concept does not declare exactly ten 5x2 perspectives")
    return {"id": slug, "passed": not errors, "errors": errors,
            "sourceElmSha256": source_hash, "conceptBoard": board,
            "conceptBoardStatus": board_status,
            "productionStatus": concept.get("status", "missing")}


def main() -> int:
    regions = [validate_region(slug) for slug in REGIONS]
    interiors = [validate_interior(slug) for slug in INTERIORS]
    report = {"schemaVersion": 1,
              "passed": all(item["passed"] for item in regions + interiors),
              "summary": {"maps": len(regions) + len(interiors), "productionRegions": len(regions),
                          "conceptPerspectives": sum(item.get("conceptBoard", {}).get("panels", 0)
                                                     for item in regions + interiors),
                          "conceptEvidenceMatches": sum(region["conceptEvidenceMatches"] for region in regions),
                          "conceptBoardsRegenerationRequired": sum(
                              item.get("conceptBoardStatus") == "regeneration-required"
                              for item in regions + interiors),
                          "sourceElmHashesMatched": sum(not any("source hash" in error
                              for error in item["errors"]) for item in regions + interiors)},
              "regions": regions, "interiors": interiors,
              "scope": "Production terrain, traversal, PBR materials, and landmark silhouettes. Corrupt PR156 concept PNGs are excluded and explicitly require regeneration; hero geometry and final set dressing remain in progress."}
    (MAP_ROOT / "validation-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], **report["summary"]}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

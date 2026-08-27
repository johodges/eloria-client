#!/usr/bin/env python3
"""Exclude corrupt PR156 concept PNGs while preserving truthful production metadata."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path("eloria-assets/maps/nymara-regions")
BUILDER = Path("eloria-assets/tools/build_nymara_region_maps.py")
VALIDATOR = Path("eloria-assets/tools/validate_nymara_region_maps.py")

boards = sorted(ROOT.glob("**/references/00-concept-detail-board.png"))
if len(boards) != 18:
    raise SystemExit(f"expected 18 PR156 concept boards, found {len(boards)}")
for board in boards:
    board.unlink()
    print("excluded corrupt concept board", board)

for path in sorted(ROOT.glob("*/world.json")) + sorted(ROOT.glob("interiors/*/concept.json")):
    data = json.loads(path.read_text())
    art = data.setdefault("conceptArt", {})
    art.pop("detailBoard", None)
    art["detailBoardStatus"] = "regeneration-required"
    path.write_text(json.dumps(data, indent=2) + "\n")

manifest_path = ROOT / "concept-generation-manifest.json"
manifest = json.loads(manifest_path.read_text())
for entry in manifest.get("maps", []):
    entry.pop("detailBoard", None)
    entry["detailBoardStatus"] = "regeneration-required"
manifest["boardStatus"] = "regeneration-required"
manifest["boardStatusReason"] = (
    "The generated PR156 PNG streams were truncated/corrupt and were excluded during integration. "
    "The 180 panel subjects and prompt specification remain the regeneration authority."
)
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

index_path = ROOT / "production-index.json"
index = json.loads(index_path.read_text())
totals = index.setdefault("totals", {})
totals["conceptBoardsValid"] = 0
totals["conceptBoardStatus"] = "regeneration-required"
index_path.write_text(json.dumps(index, indent=2) + "\n")

root_readme = ROOT / "README.md"
root_readme.write_text("""# Nymara regional production maps

This package covers all eighteen supplied maps beyond Four Gates. It defines 180 detailed concept-perspective briefs and preserves the source ELM authority. The generated PR156 detail-board PNG streams were corrupt, so those review images are intentionally excluded and marked for regeneration instead of being shipped as damaged assets. The Godot-native production pass is active for the eleven exteriors; the seven interiors retain their ten-view subject specifications and preserved ELM sources for the next geometry tranche.

## Scope

- 18 maps with five-by-two concept checkpoint/subject specifications
- 180 planned close perspectives; the 110 exterior views have per-panel production checkpoints
- 18 source ELM SHA-256 matches
- 615 landmark instances in the current terrain/landmark/material pass
- 33 original 512×512 textures: base color, normal, and ORM for every region
- Godot registry entries for canonical `maps/nymara/*.elm`, bare IDs, and filename aliases
- Concept detail-board status: `regeneration-required` (corrupt PNGs excluded during integration)

The generated GLBs are production starters, not final art. Terrain, routes, water masks, arrival coordinates, material language, and landmark silhouettes are implemented. Hero landmark geometry, final foliage/prop density, lighting polish, per-map performance LODs, and replacement concept boards remain in progress.

## Rebuild and verify

```sh
python3 eloria-assets/tools/build_nymara_region_maps.py
python3 eloria-assets/tools/validate_nymara_region_maps.py
python3 eloria-assets/tools/render_nymara_region_maps.py \\
  eloria-assets/maps/nymara-regions/*/world.glb \\
  --columns 4 \\
  --output eloria-assets/maps/nymara-regions/production-preview-contact-sheet.png
```

See `concept-generation-manifest.json` for the board prompt pattern and all 180 panel subjects. See `validation-report.json` for source hashes, GLB structure, texture dimensions, concept-board regeneration status, and exterior checkpoint evidence coverage.
""")

for readme in ROOT.glob("*/README.md"):
    text = readme.read_text()
    text = text.replace(
        "The ten-panel board in `references/00-concept-detail-board.png` is the visual authority for the next modeling pass.",
        "The ten checkpoint subjects in `world.json` remain the visual-production brief. The invalid generated detail-board PNG was excluded and must be regenerated before visual review.",
    )
    readme.write_text(text)
for readme in ROOT.glob("interiors/*/README.md"):
    text = readme.read_text()
    text = text.replace(
        "Ten production perspectives are complete. ",
        "Ten production perspective subjects are defined. The invalid generated detail-board PNG was excluded and must be regenerated. ",
    )
    readme.write_text(text)

builder = BUILDER.read_text()
builder = builder.replace(
    '"detailBoard": "references/00-concept-detail-board.png",\n                       "panelGrid": [5, 2],',
    '"detailBoardStatus": "regeneration-required",\n                       "panelGrid": [5, 2],',
)
builder = builder.replace(
    '"detailBoard": "references/00-concept-detail-board.png",\n                   "panelGrid": [5, 2],',
    '"detailBoardStatus": "regeneration-required",\n                   "panelGrid": [5, 2],',
)
builder = builder.replace(
    '"The ten-panel board in `references/00-concept-detail-board.png` is the visual authority for the next modeling pass.\\n\\n- Source topology',
    '"The ten checkpoint subjects in `world.json` remain the visual-production brief. The detail board must be regenerated before visual review.\\n\\n- Source topology',
)
builder = builder.replace(
    'f"# {config[\'title\']} concept package\\n\\nTen production perspectives are complete. "',
    'f"# {config[\'title\']} concept package\\n\\nTen production perspective subjects are defined; the detail board must be regenerated. "',
)
builder = builder.replace(
    '"detailBoard": f"{slug}/references/00-concept-detail-board.png",\n                     "panelGrid": [5, 2],',
    '"detailBoardStatus": "regeneration-required",\n                     "panelGrid": [5, 2],',
)
builder = builder.replace(
    '"detailBoard": f"interiors/{slug}/references/00-concept-detail-board.png",\n                     "panelGrid": [5, 2],',
    '"detailBoardStatus": "regeneration-required",\n                     "panelGrid": [5, 2],',
)
BUILDER.write_text(builder)

validator = VALIDATOR.read_text()
region_old = '''    try:\n        board = validate_board(directory / "references" / "00-concept-detail-board.png")\n    except Exception as error:\n        errors.append(f"concept board: {error}")\n'''
region_new = '''    board_path = directory / "references" / "00-concept-detail-board.png"\n    board_status = manifest.get("conceptArt", {}).get("detailBoardStatus", "complete")\n    if board_status == "regeneration-required":\n        if board_path.exists():\n            errors.append("concept board is present while marked regeneration-required")\n    else:\n        try:\n            board = validate_board(board_path)\n        except Exception as error:\n            errors.append(f"concept board: {error}")\n'''
if region_old not in validator:
    raise SystemExit("region concept-board validator marker missing")
validator = validator.replace(region_old, region_new, 1)
interior_old = '''    try:\n        board = validate_board(directory / "references" / "00-concept-detail-board.png")\n    except Exception as error:\n        errors.append(f"concept board: {error}")\n'''
interior_new = '''    board_path = directory / "references" / "00-concept-detail-board.png"\n    board_status = concept.get("conceptArt", {}).get("detailBoardStatus", "complete")\n    if board_status == "regeneration-required":\n        if board_path.exists():\n            errors.append("concept board is present while marked regeneration-required")\n    else:\n        try:\n            board = validate_board(board_path)\n        except Exception as error:\n            errors.append(f"concept board: {error}")\n'''
if interior_old not in validator:
    raise SystemExit("interior concept-board validator marker missing")
validator = validator.replace(interior_old, interior_new, 1)
validator = validator.replace(
    '"sourceElmSha256": source_hash, "conceptBoard": board,\n            "conceptEvidenceMatches": evidence_matches,',
    '"sourceElmSha256": source_hash, "conceptBoard": board,\n            "conceptBoardStatus": board_status, "conceptEvidenceMatches": evidence_matches,',
    1,
)
validator = validator.replace(
    '"sourceElmSha256": source_hash, "conceptBoard": board,\n            "productionStatus": concept.get("status", "missing")}',
    '"sourceElmSha256": source_hash, "conceptBoard": board,\n            "conceptBoardStatus": board_status,\n            "productionStatus": concept.get("status", "missing")}',
    1,
)
validator = validator.replace(
    '"conceptEvidenceMatches": sum(region["conceptEvidenceMatches"] for region in regions),\n                          "sourceElmHashesMatched":',
    '"conceptEvidenceMatches": sum(region["conceptEvidenceMatches"] for region in regions),\n                          "conceptBoardsRegenerationRequired": sum(\n                              item.get("conceptBoardStatus") == "regeneration-required"\n                              for item in regions + interiors),\n                          "sourceElmHashesMatched":',
    1,
)
validator = validator.replace(
    '"scope": "Production terrain, traversal, PBR materials, and landmark silhouettes. Hero geometry and final set dressing remain in progress."}',
    '"scope": "Production terrain, traversal, PBR materials, and landmark silhouettes. Corrupt PR156 concept PNGs are excluded and explicitly require regeneration; hero geometry and final set dressing remain in progress."}',
    1,
)
VALIDATOR.write_text(validator)

print("sanitized PR156 concept-board metadata; 18 corrupt PNGs excluded")

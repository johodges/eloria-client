# Nymara regional production maps

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
python3 eloria-assets/tools/render_nymara_region_maps.py \
  eloria-assets/maps/nymara-regions/*/world.glb \
  --columns 4 \
  --output eloria-assets/maps/nymara-regions/production-preview-contact-sheet.png
```

See `concept-generation-manifest.json` for the board prompt pattern and all 180 panel subjects. See `validation-report.json` for source hashes, GLB structure, texture dimensions, concept-board regeneration status, and exterior checkpoint evidence coverage.

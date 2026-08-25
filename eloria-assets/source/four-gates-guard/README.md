# Four Gates Guard authored source

This directory contains a compact, reproducible derivative of the
user-supplied `four_gates_guard.glb`. The original GLB was a static two-million
triangle mesh with an embedded 8192px painted material, no skin, and no
animation tracks. It is intentionally not duplicated in Git.

- `guard_mesh.npz` stores the decimated geometry, UVs, client skeleton weights,
  and body-slot partition.
- `guard_atlas.webp` stores the resized 2048px base-colour atlas.
- `SOURCE.json` records the original SHA-256 and conversion statistics.

Regenerate these sources from the supplied GLB with:

```bash
python3 eloria-assets/tools/import_four_gates_guard_glb.py \
  four_gates_guard.glb eloria-assets/source/four-gates-guard
```

The runtime neutral-pose Cal3D body, detachable spear/shield/cape, DDS texture,
and complete animation set are produced by `generate_four_gates_guard.py` as
part of `generate_all_assets.py`.

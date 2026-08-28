# Amberwood region source

The shared authoring toolkit now lives in `../../_toolkit/` and is documented
there. What remains here is Amberwood's own map: the composition, the placement
passes, its camera set, and its build entry points.

| File | Purpose |
| --- | --- |
| `build_amberwood.py` | Builds the whole runtime package: `world.glb`, `world.json`, `collision.bin`, `minimap.webp`, the validator report and the performance summary. Deterministic for a given seed. |
| `build_interiors.py` | Builds Amberwood's four interior packages. |
| `views.py` | `VIEWS` (the comparison camera set) and `PANELS` (detail-board panel to capture mapping). Region data, read by the toolkit's `capture_views.py` and `make_comparison.py`. |
| `preview_interior.py` | Interior preview harness. |

Amberwood's composition and placement modules (`region.py`, `populate.py`,
`interiors.py`) still sit inside the shared package for now; they are the
region-specific half of it and are the obvious next thing to separate.

```sh
make -C ../../_toolkit/native        # preview rasteriser; not needed for the package
python3 build_amberwood.py
python3 ../../_toolkit/verify_runtime.py --package ..
python3 ../../_toolkit/validate_gltf.py ../world.glb
```

## Reproducibility

A cache-cold rebuild reproduces every artefact byte-for-byte. Two things make
that true and are easy to break:

- name-derived seeds must use `noise.stable_hash()`, never the built-in
  `hash()`, which is salted per interpreter run;
- the texture cache in `preview.py` is keyed by a digest of `textures.py` and
  `materials.py`, so editing a recipe invalidates it. Before this was keyed, a
  stale cache silently shipped textures that no longer matched the source.

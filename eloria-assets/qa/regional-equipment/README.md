# Regional equipment topology QA

This stage replaces the remaining generic cuboid equipment profiles across all six
Nymara cultures. The comparison sheet is rendered directly from representative generated
E3D files and covers a blade, armor, shield, bow, tool, and polearm.

All 36 item IDs, canonical slots, attachment bones, culture assignments, material paths,
and icon paths remain unchanged. Validation enforces roster completeness, a topology floor,
256x256 materials, 64x64 icons, correct attachment semantics, and unique geometry payloads.
GPU-backed equipped-character captures remain pending.

```sh
python3 eloria-assets/tools/generate_all_assets.py build/eloria-data
python3 eloria-assets/tools/validate_generated_assets.py build/eloria-data
```

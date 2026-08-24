# Verdant Stair regional QA

Verdant Stair now follows the concept's vertical jungle-city traversal. A
stepped basalt route climbs through the central ravine, branching across root
and vine bridges to cenote descents, tree platforms, water shrines, and dense
giant-fern zones beside a winding river.

The layout includes seven basalt stair modules, four cenote stairs, six root
bridges, five vine bridges, six tree platforms, five water shrines, and twelve
giant ferns. Eight green landmark lights supplement the four transition lights.
Dedicated terrain separates upper and lower jungle, paths, and water while
terraced relief preserves the clear `(58,58)` arrival datum.

```sh
python3 eloria-assets/tools/generate_all_assets.py build/eloria-data
python3 eloria-assets/tools/validate_generated_assets.py build/eloria-data
```

Validation asserts exact landmark counts, dependency resolution, scenery and
lighting density, all four terrain classes, elevation variation, and arrival
clearance. Shaded client and map-editor captures remain pending a GPU-capable
session.

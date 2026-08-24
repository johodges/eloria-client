# Westhaven regional QA

Westhaven now follows the concept's fortified maritime city. The lighthouse
marks the western headland above a warehouse and fish-market district, while
crane-lined quays, dry docks, shipyard frames, seawalls, and sheltered harbor
water define the working waterfront and southern approaches.

The layout includes one lighthouse, eight warehouses, five dry docks, seven
harbor cranes, five shipyard frames, six fish markets, and nine seawall
sections. Eight warm harbor lights supplement the four transition lights.
Dedicated terrain separates open sea, urban ground, quays, and harbor water,
with coastal depth variation and a clear `(58,58)` arrival datum.

```sh
python3 eloria-assets/tools/generate_all_assets.py build/eloria-data
python3 eloria-assets/tools/validate_generated_assets.py build/eloria-data
```

Validation asserts exact landmark counts, dependency resolution, scenery and
lighting density, all four terrain classes, water depth, and arrival clearance.
Shaded client and map-editor captures remain pending a GPU-capable session.

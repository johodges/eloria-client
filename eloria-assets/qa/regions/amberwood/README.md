# Amberwood regional QA

Amberwood now follows the concept's dense autumn estate forest. The noble
estate anchors the northern grove, while hunting lodges, hollow old-growth
trees, bridges, ruin arches, garden fountains, and a wooded perimeter create
layered paths through the inhabited and overgrown districts.

The layout includes one estate, six hunting lodges, eight hollow trees, four
old bridges, sixteen forest trees, six ruin arches, and four garden fountains.
Eight warm landmark lights supplement the four transition lights. Dedicated
terrain separates the estate grounds, forest floor, paths, and old-growth belt
while preserving the clear `(58,58)` arrival datum.

```sh
python3 eloria-assets/tools/generate_all_assets.py build/eloria-data
python3 eloria-assets/tools/validate_generated_assets.py build/eloria-data
```

Validation asserts exact landmark counts, dependency resolution, scenery and
lighting density, all four terrain classes, elevation variation, and arrival
clearance. The regional QA renderer now uses map-specific palettes so forest
and grass terrain classes are not misrepresented as water. Shaded client and
map-editor captures remain pending a GPU-capable session.

# Amethyst Barrens regional QA

Amethyst Barrens now follows the concept's storm-scoured crystal basin. A
Glasswarden observatory overlooks the protected arrival basin, while crystal
bridges connect the main travel axes to geode caves, levitating shard fields,
storm ruins, resonant crystal clusters, and six field stations.

The layout includes one observatory, seven crystal bridges, four geode caves,
eight levitating-shard groups, six storm ruins, ten resonant clusters, and six
field stations. Eight violet landmark lights supplement the four transition
lights. Dedicated terrain separates the basin floor, rocky barrens, resonant
roads, and crystal fields while preserving the clear `(58,58)` arrival datum.

```sh
python3 eloria-assets/tools/generate_all_assets.py build/eloria-data
python3 eloria-assets/tools/validate_generated_assets.py build/eloria-data
```

Validation asserts exact landmark counts, dependency resolution, scenery and
lighting density, all four terrain classes, elevation variation, and arrival
clearance. The committed QA set includes the regional overhead, concept
comparison, and representative landmark topology. Shaded client and map-editor
captures remain pending a GPU-capable session.

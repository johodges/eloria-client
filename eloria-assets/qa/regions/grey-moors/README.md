# Grey Moors regional QA

Grey Moors now follows the concept's bleak barrow landscape. Raised burial
islands and standing-stone courts are linked by boardwalks and causeways across
the bog, with crypt entrances, abandoned cottages, dead trees, and ritual
shrines establishing distinct exploration routes and silhouettes.

The layout includes six barrows, eight standing-stone groups, eight boardwalks,
four crypt entrances, six cottages, ten dead trees, and five ritual shrines.
Eight cold landmark lights supplement the four transition lights. Dedicated
terrain separates barrow ground, open moor, causeways, and bog while preserving
the clear `(58,58)` arrival datum.

```sh
python3 eloria-assets/tools/generate_all_assets.py build/eloria-data
python3 eloria-assets/tools/validate_generated_assets.py build/eloria-data
```

Validation asserts exact landmark counts, dependency resolution, scenery and
lighting density, all four terrain classes, bog depth variation, and arrival
clearance. Shaded client and map-editor captures remain pending a GPU-capable
session.

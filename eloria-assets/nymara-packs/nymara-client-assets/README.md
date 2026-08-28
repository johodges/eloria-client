# Nymara native asset pack

Generated for `eloria-client` branch `feature/independent-eloria-client`.

## Contents

- `runtime/3dobjects/nymara/`: 120 native E3D scenery models and PNG textures.
- `runtime/3dobjects/nymara/` harvest nodes: 32 authored harvestable models with 256px materials.
- `runtime/2dobjects/nymara/flora/`: 16 decorative ground-flora `.2d` definitions and a shared alpha atlas.
- `runtime/textures/nymara/icons/`: 32 individual 64x64 RGBA item icons.
- `runtime/textures/nymara/items_nymara.png`: 512x256 icon atlas.
- `runtime/nymara_assets.json`: stable paths and item IDs.
- `source-obj/`: editable OBJ/MTL source for every 3D object.
- `generate_nymara_pack.py`: deterministic regeneration source.

Copy the contents of `runtime/` into the generated Eloria data directory. E3D and `.2d` files can be placed directly by the bundled map editor. The JSON catalog is intended for client/server registration.

The shared regional catalog contains functional low-poly production proxies.
The Four Gates civic wall, tower, bridge, pavilion and park tree are the first
refined regional kit: they use intentional silhouette topology, 256px authored
procedural materials, stable scale and pivots, native E3D output, and editable
OBJ/MTL source. They are original interpretations of the approved art direction,
not automatic reconstructions of the concept paintings.

Harvest nodes are held to the same standard and are authored in
eloria-assets/tools/harvestables.py, the single catalogue the models, icons,
harvestable.lst entries and map placements all read from. Foliage nodes declare
a transparent material so the client alpha-tests them and keeps both faces.
See docs/harvestable-audit.md.

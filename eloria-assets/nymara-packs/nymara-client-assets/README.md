# Nymara native asset pack

Generated for `eloria-client` branch `feature/independent-eloria-client`.

## Contents

- `runtime/3dobjects/nymara/`: 127 native E3D models and PNG textures.
- `runtime/2dobjects/nymara/`: 16 native `.2d` definitions and shared RGBA atlas.
- `runtime/textures/nymara/icons/`: 16 individual 64x64 RGBA item icons.
- `runtime/textures/nymara/items_nymara.png`: 512x128 icon atlas.
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

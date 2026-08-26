# Luminous animated GLB runtime

Luminous female (actor type 0) and male (actor type 1) are rendered from
`actors/playable/luminous_<sex>_quaternius_v2.glb`. Other actors continue to
use the existing Cal3D path. The GLBs are self-contained glTF 2.0 binaries with
one indexed triangle mesh, UVs, normals, four joint influences per vertex, a
37-joint skin, Eloria actor-atlas UVs, and named animation clips.

The source character meshes are Quaternius Universal Base Characters and the
source animations are the Quaternius Universal Animation Library (CC0-1.0).
The original distribution archives are authoring inputs and are not needed to
build or run the client. The derived runtime GLBs are checked in under
`eloria-assets/source/player_models/runtime`; the standard asset generator
copies them into the data directory without converting them.

## Client action mapping

| Client action | GLB clip |
| --- | --- |
| standing, alternate standing | `idle`, `idle2` |
| walking, running | `walk`, `run` |
| combat stance and held combat stance | `combat_idle` |
| melee/ranged and held attack frames | `attack` |
| spell attack | `cast` |
| pain, death | `pain`, `die` |
| sit transition, seated idle, stand transition | `sit_down`, `sit`, `stand_up` |
| harvest, pick up, drop | `harvest`, `pick`, `drop` |

Animation time remains driven by the existing actor command lifecycle, so
movement duration scaling and server protocol behavior are unchanged. The GLB
runtime samples rotations from the selected named clip and CPU-skins a shared
source mesh per visible instance. Existing actor texture composition remains
active, preserving skin, clothing, hair, and eye colour choices.

## Limitations

This first character path supports rotation animation tracks, linear
interpolation, one skin, four weights per vertex, and unsigned 16/32-bit
indices. It intentionally retains Cal3D state for attachments and unsupported
emotes. Morph targets, animation translation/scale channels, PBR normal and
roughness maps, and GLB-driven equipment attachments are not yet rendered.

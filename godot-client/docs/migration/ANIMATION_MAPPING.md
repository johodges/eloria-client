# Native character and animation runtime

Playable characters are instantiated directly from their original GLB with GLTFDocument. The generated hierarchy, skins, skeletons, materials, morphs, and animations are retained. ReplicatedActor3D applies only an outer scale/orientation adapter and never rebuilds bones or meshes.

Animation selection is explicit data: gameplay action to exact clip name, and server command to gameplay action. Substring guessing is prohibited. Root motion never controls replicated actor position.

## Current asset gate

At the audited develop revision, the repository has Universal_Animation_Library.glb plus male/female body glTF, bin, and texture files. The original luminous male and female playable GLBs are not present at a repository path. Registry entries therefore remain deliberately empty and marked blocked. Put the supplied original GLBs at stable repository/LFS paths and fill only registry paths, exact clip names, and attachment bone names. Do not convert them.

## Validation required

1. Load the native GLB.
2. Confirm one Skeleton3D and expected skinned meshes.
3. Cycle every mapped clip and report missing clips.
4. Draw skeleton and attachment locators.
5. Verify bind pose, scale, orientation, transparency, textures, and root motion.
6. Test male and female independently.

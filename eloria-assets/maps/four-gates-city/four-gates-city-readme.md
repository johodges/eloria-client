# Four Gates City GLB + JSON package

Production-oriented textured environment derived from the supplied Four Gates references. The square aerial controls layout; perspective images inform silhouettes and materials.

## Scene conventions

- Meters, right-handed, +Y up, -Z north, origin at the central plaza.
- Defensive-ring diameter: 720 m. Walking plateau: Y=30 m. Water: Y=-2 m. Lowest useful terrain: Y=-40 m.
- Named hierarchy, interaction parts, collision proxies, markers, PBR materials, and stable JSON identifiers are included.

## Loading

Load `four-gates-city.glb` with any glTF 2.0 loader, then parse `four-gates-city.json`. Resolve metadata `node` fields by exact GLB node name. The loader must support `KHR_texture_transform` for atlas selection. Unknown extras and JSON extensions should be ignored safely.

## Materials and effects

The package uses 15 shared metallic-roughness materials and three embedded 1024×1024 PNG atlases: base color, tangent-space normal, and packed ORM (`R=occlusion`, `G=roughness`, `B=metallic`). Source and derived maps are also included under `textures/`. Water, waterfall sheets, and blue-energy pulses retain optional client-effect metadata.

## LOD, collision, navigation

The GLB is gameplay-distance LOD1. Low-poly `COLLISION_*` nodes are separate. LOD0 and LOD2 should remain sibling GLBs using stable names until the loader's LOD policy is fixed. Navigation comprises stable walkable groups and human-readable paths rather than a baked navmesh.

## Reference coverage

`references/` contains 20 indexed verification views and a generated four-panel architecture reference sheet.

## Known limitations

This is a textured gameplay LOD1 environment, not a hand-authored cinematic LOD0. Landmark-specific unwraps and ornament, true arch topology, authored LOD0/LOD2, baked navmesh, animation clips, mist particles, and final vegetation remain follow-up work.

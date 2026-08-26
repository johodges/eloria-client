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

The main GLB contains gameplay-distance LOD1 plus `_LOD0` landmark overlays. `four-gates-city-lod2.glb` is a reduced-node distant sibling with 557 active nodes, no animations, and no close-detail overlays. Low-poly `COLLISION_*` nodes remain separate. Navigation includes ten conservative convex walkable polygons, monument and wall exclusions, agent dimensions, and an off-mesh sanctuary link.

## Animation

Seven optional standard glTF clips are embedded: five portcullis open/close clips and pulse clips for the sanctuary beacon and plaza crystal. Static initial transforms remain correct when animation is ignored.

## Reference coverage

`references/` contains 20 indexed verification views and a generated four-panel architecture reference sheet.

## Known limitations

This is a textured gameplay environment with landmark LOD0 overlays and an authored reduced-node LOD2 sibling, not a hand-authored cinematic city. Landmark-specific UV unwraps, final per-building navigation blockers, mist particles, and bespoke vegetation remain follow-up work.

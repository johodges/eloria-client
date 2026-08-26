# Four Gates City GLB + JSON package

Production-oriented textured environment derived from the supplied Four Gates references. The square aerial controls layout; perspective images inform silhouettes and materials.

## Scene conventions

- Meters, right-handed, +Y up, -Z north, origin at the central plaza.
- Defensive-ring diameter: 720 m. Walking plateau: Y=30 m. Water: Y=-2 m. Lowest useful terrain: Y=-40 m.
- Named hierarchy, interaction parts, collision proxies, markers, PBR materials, and stable JSON identifiers are included.

## Loading

Load `four-gates-city.glb` with any glTF 2.0 loader, then parse `four-gates-city.json`. Resolve metadata `node` fields by exact GLB node name. The loader must support `KHR_texture_transform` for atlas selection. Unknown extras and JSON extensions should be ignored safely.

## Materials and effects

The package uses 19 metallic-roughness materials. A three-map citywide atlas covers general assets, while a dedicated four-map landmark family provides base color, tangent normal, packed ORM, and emissive detail for monumental stone, bronze trim, foundations, and blue-energy inlays. Source and derived maps are included under `textures/`.

## LOD, collision, navigation

The main GLB contains gameplay-distance LOD1 plus `_LOD0` landmark overlays. `four-gates-city-lod2.glb` is a reduced-node distant sibling with 557 active nodes, no animations, and no close-detail overlays. Low-poly `COLLISION_*` nodes remain separate. Navigation includes ten conservative convex walkable polygons, monument and wall exclusions, agent dimensions, and an off-mesh sanctuary link.

## Animation

Seven optional standard glTF clips are embedded: five portcullis open/close clips and pulse clips for the sanctuary beacon and plaza crystal. Static initial transforms remain correct when animation is ignored.

## Reference coverage

`references/` contains 20 indexed verification views and a generated four-panel architecture reference sheet.

## Known limitations

This is a textured gameplay environment with authored modular landmark geometry, landmark UVs, building blockers, and a reduced-node LOD2 sibling. Remaining work is primarily bespoke district UVs, complete terrain sculpting, mist/water shaders, higher-density ornament, and bespoke vegetation.

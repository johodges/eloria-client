# Four Gates City GLB + JSON package

+Production-oriented procedural first pass derived from the supplied Four Gates references. The square aerial is authoritative for layout; perspective images inform silhouettes and materials.
+
+## Scene conventions
+
+- Meters, right-handed, +Y up, -Z north, origin at the central plaza.
+- Defensive-ring diameter: 720 m. Walking plateau: Y=30 m. Water: Y=-2 m. Lowest useful terrain: Y=-40 m.
+- Named hierarchy, interaction parts, collision proxies, markers, PBR metallic-roughness materials, and stable JSON identifiers are included.
+
+## Loading
+
+Load `four-gates-city.glb` with any glTF 2.0 loader, then parse `four-gates-city.json`. Resolve metadata `node` fields by exact GLB node name. Use JSON coordinate values unchanged. Missing custom effects must degrade to static geometry and emissive materials.
+
+## Materials and effects
+
+The first pass uses 15 shared constant-factor PBR materials; no external textures or proprietary shaders. Water, waterfall sheets, and blue-energy pulses carry JSON effect descriptions for optional client shaders. This intentionally avoids assuming texture-compression support.
+
+## LOD, collision, navigation
+
+The GLB is gameplay-distance LOD1. Low-poly `COLLISION_*` nodes are separate. LOD0 and LOD2 should be sibling GLBs using stable names (`*_LOD0`, `*_LOD2`) until the loader's LOD extension policy is fixed. Navigation comprises stable walkable geometry groups plus human-readable paths; it is not a baked navmesh.
+
+## Reference coverage
+
+`references/` contains 20 indexed verification views matching the requested coverage. They are blockout renders for connection and scale verification, not texture-fidelity beauty renders. The generated four-panel architecture sheet is `references/00-generated-architecture-reference.png`.
+
+## Loader assumptions
+
+The loader must support glTF 2.0 node transforms, indexed triangle primitives, shared materials, alpha blending, emissive factors, extras, and exact node-name lookup. It should ignore unknown extras and JSON extensions safely.
+
+## Known limitations
+
+This is a coherent production blockout, not a final hand-authored AAA city. UV texture atlases, bespoke ornament, true arches, authored LOD0/LOD2, baked navmesh, animation clips, mist particles, and final vegetation are deferred. See JSON and validation report for the complete list.
+
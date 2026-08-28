# Four Gates map change log

## 1.0.0 — production GLB package

First authored production pass, replacing the `four-gates-city` graybox
(4,538 unique triangles of untextured primitives).

- New self-contained authoring pipeline under `eloria-assets/tools/four_gates/`:
  a core-only glTF 2.0 writer, an indexed mesh toolkit, procedural PBR material
  synthesis, modular kits, landmark assemblies, an analytic terrain field and a
  deterministic city layout.
- Sculpted terrain: flat civic plateau, battered cliff, continuous turquoise
  water ring, four causeway crossings, outer highland rim, alpine skyline and a
  northern massif carrying the sanctuary shelf. Terrain surfacing is driven by
  height **and slope**, so steep ground reads as rock everywhere.
- 29 original tileable PBR material sets (base colour, tangent normal, packed
  ORM; emissive for the sapphire crystal).
- Landmarks: five twin-drum gatehouses with animated portcullises, 40 curtain
  wall bays and 8 drum towers, four arched bridges, the plaza mandala and
  crystal-crowned monument, four arcaded porticos, and the northern sanctuary
  with a ceremonial stair, glowing portal and beacon.
- 346 district buildings across four kits with authored variation, plus market
  squares, farm plots, docks, cranes, street furniture and ~850 planted trees.
- Manifest-driven environment (sky, sun, ambient, fog, tonemap, water) applied
  by a new `WorldEnvironmentApplier`, so the map ships with its art direction.
- Collision proxies inset inside their parent geometry (never visible), a
  navigation surface prefix contract, and 28 convex navigation polygons.
- Khronos glTF-Validator: **0 errors, 0 warnings**.

### Defects found and fixed during this pass

These were caught by the validator, the independent viewer and the client:

- glTF index accessors declared a third of their true element count, so only
  one triangle in three would have been drawn by any conformant loader.
- Flat-shaded normals were computed against stale indices after vertex
  duplication, giving null normals on hard-surface geometry.
- Ground, ring, strip and polar surfaces were wound clockwise, so every terrain
  and road surface faced downward.
- Bridge arches sprang above the deck and occluded the whole crossing.
- The bridge deck slab and its fascia were exactly coincident, producing
  z-fighting bands across the causeway.

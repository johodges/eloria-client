# Sunmane Steppe modelling assumptions

Recorded so a reviewer can tell a deliberate choice from an oversight.

## Coordinates and scale

- One metre per server tile, matching the entry already committed in
  `godot-client/data/maps/registry.json` and every sibling Nymara region. The
  source ELM's height grid is 192 x 192; the authored region is a 208 m square
  centred on the arrival datum, which contains every connection point in
  `maps/nymara-regions/source-elm/regions-connections.json` with room for a
  natural rim beyond them.
- The datum `(58, 58)` sits on the ceremonial crossroads inside the palisade,
  so an arriving player lands in the settlement rather than outside it.
- Travel distances: about 180 m of open steppe across the playable area, so
  crossing the region on foot is under a minute at normal walking speed.

## Grounding

- Every terrain chunk carries the `Terrain_` prefix, so the client's
  navigation-surface layer covers the whole landform, including the shallow
  shelf below sea level and a skirt that extends past the declared bounds.
  A grounding raycast can therefore never miss and fall back to
  `walkingHeight`, which is the failure that drops an actor under the map.
- `walkingHeight` is nevertheless set to the arrival plateau rather than zero,
  so even a miss would place an actor above the landform rather than inside it.
- Water is not walkable by construction, but it is still covered by the
  navigation surface. Movement is server-authoritative - the client only
  converts a picked point to a server tile - so making the surface continuous
  is the safe choice and does not grant sea access by itself.

## Structures on terrain

- Anything with a real footprint gets a levelled building pad in the
  heightfield, with a graded skirt. Without pads a wide structure has to be
  sunk to the lowest point under it, which buried the central hall by 2.2 m in
  an earlier pass.
- Pads are applied before the stream, waterholes and road corridors are cut, so
  water and routes are carved into levelled ground rather than filled in by it.

## Materials

- Nine tileable PBR families with world-scale UVs, rather than one atlas with
  baked UVs. World-scale UVs keep texel density uniform across terrain,
  architecture and props without per-asset bookkeeping, and tiling families
  avoid the mip bleed an atlas suffers at distance.
- The four described terrain classes tint one shared ground detail map through
  material base-colour factors. That keeps a single texel density and avoids
  splat seams; glTF clamps `baseColorFactor` to 0..1, so the ground map is
  authored bright and tinted down.
- Only core glTF 2.0 is emitted. No extensions are used, so the client's stock
  `GLTFDocument` needs no change.

## Tangents

- Tangents are emitted for exactly the primitives whose material carries a
  normal map. Emitting them everywhere wasted about a fifth of the package on
  data no renderer reads; omitting them where a normal map exists makes the
  tangent frame renderer-dependent and the Khronos validator warns about
  portability. Deciding per primitive satisfies both, and the package validates
  with zero warnings.

## Roads

- The caravan roads are terrain, not an overlaid surface: the landform grades a
  corridor and classifies it as `caravan_road`. There is therefore no road
  decal to z-fight with the ground. Roads are dressed with wayposts, pennants
  and kerb stones instead.
- The one authored ground overlay is the crossroads plaza, lifted 0.11 m and
  following the heightfield, on flat pad ground where that clearance is safe.

## Population

- Livestock are scenery, not networked actors: no actor id, no collision, and
  deliberately not baked into the world mesh, where they would have become part
  of the collision surface. They are declared in the manifest and instanced by
  `AmbientPopulation` at runtime.
- NPCs, harvestables and hostile creature spawns are the server's to own. They
  are recorded under `runtimePopulation` with the hooks from
  `regions-connections.json` so the server profile has an exact list.
- The horses are new assets. The shared creature generator builds every animal
  from the same sphere-and-cylinder blank, which cannot produce a horse, so the
  geometry is authored to equine proportions on the same rig, with the same
  joint names, animation names and attachment points the client already
  expects.

## Known simplifications

- Grass is opaque tapered blade geometry rather than alpha cards, so there is no
  alpha sorting cost and no cutout artefacts, at the price of a sparser sward
  than a painted concept implies.
- Ambient animals do not wander; they idle in place with offset animation
  phases. Movement belongs to the server-driven actor path.
- Human inhabitants are not placed by the client. The concept art's crowds are
  server-owned NPCs, listed in `runtimePopulation.npcs`.

# Change log

## 0.4.0 — 2026-08-26

- Added district-specific civic halls, arcades, cupolas, residences, courtyards, farmhouses, granaries, irrigation channels, docks, and cranes.
- Added ring-road lamps and banners plus deterministic tree/trunk population outside principal routes.
- Expanded navigation from five principal polygons to ten principal and district walkable polygons with monument and wall exclusions.
- Added `four-gates-city-lod2.glb` and companion JSON; LOD2 reduces active nodes from 1,319 to 557 and removes animation and close-detail overlays.

## 0.3.0 — 2026-08-25

- Added thick pointed arch-ring and bronze-trim meshes to all five traversable gate structures.
- Added layered buttresses, finials, façade beacons, twelve sanctuary spires, and three plaza stair rings.
- Added five standard glTF portcullis clips and two energy-pulse clips with sensible static initial transforms.
- Added an inline principal-route convex navmesh with agent dimensions, slope limits, and a sanctuary off-mesh link.
- Replaced placeholder LOD notes with explicit suffix, screen-coverage, and fallback metadata.

## 0.2.0 — 2026-08-25

- Embedded 1024×1024 base-color, tangent-normal, and packed ORM atlases.
- Added normals and UVs to every reusable visible primitive using `KHR_texture_transform` atlas addressing.
- Added 239 detail nodes covering battlements, bridge parapets and piers, plaza furniture and lighting, market stalls, and farm fences.
- Preserved every loader-facing landmark, collision, navigation, interaction, and marker identifier.

## 0.1.0 — 2026-08-25

- Established canonical 720 m radial plan and elevation conventions.
- Added hierarchical LOD1 city, terrain, water, four gates, four bridges, plaza, sanctuary, districts, walls, effects, collision, navigation, and markers.
- Added versioned loader metadata and 20-view reference coverage.

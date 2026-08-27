# Validation report

Validated 2026-08-27 for asset version 0.7.0.

## Passed

- LOD1 GLB header is `glTF`, version 2; declared and actual length both 9,156,172 bytes.
- LOD2 GLB header is `glTF`, version 2; declared and actual length both 2,325,380 bytes.
- JSON parses successfully and names `four-gates-city.glb` exactly.
- LOD1 contains 1,483 unique named nodes; compact LOD2 contains 663.
- Every landmark, district, gate, portcullis, bridge, collision, and navigation node referenced by JSON exists exactly in the GLB.
- All primitives use indexed triangles with float32 positions and uint32 indices.
- Materials use glTF metallic-roughness, alpha blending, emissive factors, and standard `KHR_texture_transform`; no proprietary extensions or broken external texture paths exist.
- Seven PNG maps are embedded: the citywide base-color/normal/ORM atlas and landmark base-color/normal/ORM/emissive family.
- Every visible primitive provides `POSITION`, `NORMAL`, and `TEXCOORD_0` attributes.
- Every normal-mapped primitive also provides a portable `TANGENT` attribute.
- Seven standard glTF animation clips reference existing nodes and valid translation or scale channels.
- Ten principal/district convex navmesh polygons, two exclusions, and one sanctuary off-mesh link use documented asset coordinates.
- Seventy major-building obstacles provide conservative navigation blockers.
- Eight water channels, plunge pools, foam surfaces, and mist locators are present with stable programmatic names and loader metadata.
- LOD2 retains only referenced meshes, materials, textures, images, accessors, and buffer views; embedded overview textures are capped at 512 px.
- Scene root, coordinate system, units, origin, bounds, gate approaches, spawns, paths, and camera targets are explicit.
- Collision proxies are separate from visible meshes and align by construction.
- Static transforms remain coherent when animation and custom effects are disabled.
- Twenty requested verification cameras/renders and one generated architectural reference sheet are included.
- The portable 1536×1536 collision grid contains both blocked and walkable terrain, preserves all four causeways, blocks the central monument, water channels, and final building footprints, and keeps all required gameplay anchors walkable.
- The portable manifest contains four portals, six NPC markers, three creature spawn zones, four harvestables, five gameplay regions, and eight waterfall effect stacks whose node names resolve in the GLB.
- `four_gates.dds` is a client-readable 512×512 uncompressed BGRA DDS with exactly four mip levels.

## Independent-validator/viewer status

The package passed local binary/container and cross-reference validation. Khronos glTF Validator was run against both assets: LOD1 reports 0 errors, 0 warnings, 3 informational messages; LOD2 reports 0 errors, 0 warnings, 3 informational messages. Machine-readable reports are checked in beside the GLBs.

Pull requests that change Four Gates now run an independent Godot/Xvfb render and upload aerial and gameplay screenshots. Blender, Babylon.js Sandbox, or Don McCurdy's glTF Viewer inspection remains recommended before tagging 1.0.0.

## Release-gate limitations

- Major gate towers, domes, bridge arches, and cliffs now use authored modular topology and UVs.
- Bespoke district UVs, higher-density landmark ornament, bespoke vegetation, and custom water/mist/energy shaders remain future work.

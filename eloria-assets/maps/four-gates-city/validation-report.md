# Validation report

Validated 2026-08-26 for asset version 0.6.0.

## Passed

- LOD1 GLB header is `glTF`, version 2; declared and actual length both 9,265,616 bytes.
- LOD2 GLB header is `glTF`, version 2; declared and actual length both 2,327,160 bytes.
- JSON parses successfully and names `four-gates-city.glb` exactly.
- LOD1 contains 1,378 unique named nodes; compact LOD2 contains 558.
- Every landmark, district, gate, portcullis, bridge, collision, and navigation node referenced by JSON exists exactly in the GLB.
- All primitives use indexed triangles with float32 positions and uint32 indices.
- Materials use glTF metallic-roughness, alpha blending, emissive factors, and standard `KHR_texture_transform`; no proprietary extensions or broken external texture paths exist.
- Seven PNG maps are embedded: the citywide base-color/normal/ORM atlas and landmark base-color/normal/ORM/emissive family.
- Every visible primitive provides `POSITION`, `NORMAL`, and `TEXCOORD_0` attributes.
- Seven standard glTF animation clips reference existing nodes and valid translation or scale channels.
- Ten principal/district convex navmesh polygons, two exclusions, and one sanctuary off-mesh link use documented asset coordinates.
- Seventy major-building obstacles provide conservative navigation blockers.
- Eight water channels, plunge pools, foam surfaces, and mist locators are present with stable programmatic names and loader metadata.
- LOD2 retains only referenced meshes, materials, textures, images, accessors, and buffer views; embedded overview textures are capped at 512 px.
- Scene root, coordinate system, units, origin, bounds, gate approaches, spawns, paths, and camera targets are explicit.
- Collision proxies are separate from visible meshes and align by construction.
- Static transforms remain coherent when animation and custom effects are disabled.
- Twenty requested verification cameras/renders and one generated architectural reference sheet are included.

## Independent-validator/viewer status

The package passed the local binary/container and cross-reference validation above. The Khronos npm validator library was not available as an executable in this restricted workspace, and no independent interactive glTF viewer was available. Consequently, Khronos validator and viewer-open checks remain release-gate items rather than being falsely reported as passed. Recommended commands:

```text
gltf-validator -i four-gates-city.glb -o gltf-validator-report.json
```

Open the GLB in Blender, Babylon.js Sandbox, or Don McCurdy's glTF Viewer and confirm material appearance, culling, and camera framing before tagging 1.0.0.

## Release-gate limitations

- Major gate towers, domes, bridge arches, and cliffs now use authored modular topology and UVs.
- Bespoke district UVs, higher-density landmark ornament, bespoke vegetation, and custom water/mist/energy shaders remain future work.

# Validation report

Validated 2026-08-25.

## Passed

- GLB header is `glTF`, version 2; declared and actual length both 77,344 bytes.
- JSON parses successfully and names `four-gates-city.glb` exactly.
- 395 unique named nodes are present.
- Every landmark, district, gate, portcullis, bridge, collision, and navigation node referenced by JSON exists exactly in the GLB.
- All primitives use indexed triangles with float32 positions and uint32 indices.
- Materials use core glTF metallic-roughness, alpha blending, and emissive factors only; no proprietary extensions or external texture paths exist.
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

- This is an LOD1 production blockout with shared constant-factor PBR materials, not a final texture-authored LOD0 environment.
- UV atlases, bespoke ornament, authored LOD0/LOD2, baked navmesh, and effect shaders remain future work.

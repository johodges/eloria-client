# Portable GLB + JSON world packages

Status: format version 1. The ELM loader remains the default for explicit
`.elm` filenames. An extensionless server map ID `foo` resolves
deterministically to `maps/foo/world.json` when present, otherwise
`maps/foo.elm`. A present but invalid package is a hard error and never
falls back. An explicit JSON filename selects only the package loader.

## Layout and validation

```
maps/foo/world.json
maps/foo/world.glb
maps/foo/collision.bin
maps/foo/minimap.webp       # optional
```

Companion names may be changed in the manifest. They are UTF-8 relative paths;
absolute paths, backslashes, empty components, `.`, and `..` are rejected.
Run `tools/eloria-map-validate maps/foo/world.json --stats`.

The checked-in [schema](world-package-v1.schema.json) is the normative field
reference. Unknown fields are ignored for forward compatibility. NPC, spawn,
harvestable and portal entries are editor/visual alignment metadata only;
the server remains authoritative for gameplay state.

## Coordinates

glTF and manifest positions are right-handed, metres, Y-up and -Z-forward.
Eloria is Z-up and +Y-forward. Conversion is centralized as:
`(x,y,z) -> (origin.x+x/u, origin.y-z/u, origin.z+y/u)`, where `u` is
`units_per_meter`. Collision is the existing half-metre server grid.

## Collision binary

All integers are little-endian: `EWCG` magic, uint16 version (1), uint16
flags (0), uint32 width, uint32 height, then exactly width*height bytes.
Each byte is the existing signed height/walkability value; 127 is blocked.
Dimensions must be positive multiples of six because an ELM tile is a 6x6
set of half-metre movement cells.

## Supported GLB subset and Blender

Version 1 validates GLB 2.0, embedded buffers, triangle primitives and
POSITION. It rejects required extensions and non-triangle primitives.
The runtime integration currently establishes package selection, safe
validation, environment state, coordinate conversion, collision/pathfinding
data and deterministic cleanup. Static mesh GPU/material translation is the
next implementation stage; packages are not yet visually rendered.

In Blender export **glTF 2.0**, format **GLB**, +Y Up, meshes and materials,
normals, UVs, vertex colors as needed, and applied transforms unless node
instancing is intentional. Use PNG/JPEG images, avoid Draco/meshopt and
animation for v1, and triangulate before export.

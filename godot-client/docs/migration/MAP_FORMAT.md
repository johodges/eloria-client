# GLB world runtime

The runtime loads every world through `WorldLoader`: JSON validation, native Godot glTF scene generation, declared collision, then gameplay systems. Four Gates has no engine special case.

## Package

A package contains `map.glb` and a sibling JSON manifest matching `world-manifest-1.schema.json`. GLB owns visual hierarchy, meshes, materials, skins, and authored animation. JSON owns stable gameplay identifiers and metadata.

During repository development, the Godot project is a sibling of `eloria-assets`. Call the loader with an absolute path produced from:

```gdscript
ProjectSettings.globalize_path("res://../eloria-assets/maps/four-gates-city/four-gates-city.json")
```

Export packaging must copy approved world packages into the exported content directory without rewriting the GLB.

## Coordinates

Godot is Y-up, metres, right-handed, north = -Z. Server `(x, y)` tiles map to Godot `(x * metresPerTile, elevation, -y * metresPerTile) + origin`. Conversion is exclusively owned by `CoordinateAdapter`.

The existing Four Gates manifest does not yet contain `coordinateTransform`. Until content adds it, the loader emits a warning and uses one metre per server tile, asset origin, and inverted server Y. This fallback is not considered final coordinate verification.

## Collision and navigation

Collision node names are resolved recursively and receive trimesh static bodies. This is appropriate for static authored structures; frequently updated or simple props must use primitive collision declarations in a subsequent schema revision. Navigation metadata remains separate and will be used to construct/bake `NavigationRegion3D`; visual meshes are never implicitly considered walkable.

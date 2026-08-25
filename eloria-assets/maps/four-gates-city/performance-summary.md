# Performance summary

```json
{
  "nodes": 395,
  "meshes": 19,
  "materials": 15,
  "animations": 0,
  "textures": 0,
  "textureMemoryBytes": 0,
  "glbBytes": 77344,
  "estimatedTriangles": 652
}
```

Recommended budgets: desktop LOD1 under 1.5M visible triangles and 512 MiB textures; mobile LOD1 under 350k visible triangles and 192 MiB textures. This procedural package is substantially below both geometry budgets and contains no textures.

# Performance summary

```json
{
  "nodes": 634,
  "meshes": 22,
  "materials": 15,
  "animations": 0,
  "textures": 3,
  "textureMemoryBytes": 12582912,
  "glbBytes": 4470960,
  "estimatedTriangles": 652
}
```

Recommended budgets: desktop LOD1 under 1.5M visible triangles and 512 MiB textures; mobile LOD1 under 350k visible triangles and 192 MiB textures. The three GPU atlases total approximately 12 MiB uncompressed.

# Performance summary

```json
{
  "nodes": 1345,
  "meshes": 32,
  "materials": 19,
  "animations": 7,
  "textures": 7,
  "textureMemoryBytes": 29360128,
  "glbBytes": 9197000,
  "lod2Nodes": 557,
  "lod2GlbBytes": 9082832,
  "uniqueMeshTriangles": 2682
}
```

Recommended budgets: desktop LOD1 under 1.5M visible triangles and 512 MiB textures; mobile LOD1 under 350k visible triangles and 192 MiB textures. The three GPU atlases total approximately 12 MiB uncompressed.

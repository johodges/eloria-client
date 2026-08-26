# Performance summary

```json
{
  "nodes": 1378,
  "meshes": 37,
  "materials": 19,
  "animations": 7,
  "textures": 7,
  "textureMemoryBytes": 29360128,
  "glbBytes": 497656,
  "lod2Nodes": 558,
  "lod2Meshes": 23,
  "lod2Materials": 16,
  "lod2TextureMaxResolution": 512,
  "lod2GlbBytes": 316984,
  "lod2SizeReductionPercent": 36.3,
  "uniqueMeshTriangles": 4310,
  "lod2UniqueMeshTriangles": 3544
}
```

Recommended budgets: desktop LOD1 under 1.5M visible triangles and 512 MiB textures; mobile LOD1 under 350k visible triangles and 192 MiB textures. The seven LOD1 embedded maps total approximately 28 MiB uncompressed. LOD2 embeds six resource-pruned maps capped at 512 px and is 36.3% smaller on disk than LOD1.

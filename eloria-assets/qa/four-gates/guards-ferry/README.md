# Four Gates guard and ferry-service QA

This stage gives the female and male Luminous guards (actor IDs 301 and 308)
layered civic armor, shoulder protection, helmets, and crests. Female and male
ferrymen (actor IDs 303 and 310) receive working belts and civic service caps.

The actor IDs, mesh paths, humanoid skeleton, material dimensions, collision
bounds, and animation mappings remain unchanged. The composite wireframe shows
guards on the top row and ferrymen on the bottom row, female then male.

```sh
python3 eloria-assets/tools/generate_nymara_complete.py build/eloria-data
python3 eloria-assets/tools/validate_generated_assets.py build/eloria-data
```

Generated guard meshes contain 1,130 vertices each; ferryman meshes contain
1,058 vertices each. Shaded in-client captures remain pending a GPU-capable
client session.

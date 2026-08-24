# Regional NPC silhouette QA

This sheet compares representative female NPC meshes from all six Nymara cultures.
The stage preserves frozen actor types, the semantic humanoid skeleton, material paths,
animation paths, scale, and collision metadata while replacing the five non-Luminous
cultures' generic hood/crown/armor variants with region-specific silhouettes.

The clean generated roster is validated for complete actor references, all six cultures,
a 950-vertex minimum, valid Cal3D geometry and influences, and a unique mesh payload for
every NPC record. The comparison image was rendered directly from the generated XMF files
with `render_cal3d_wireframe.py`. GPU-backed shaded client captures remain pending.

```sh
python3 eloria-assets/tools/generate_all_assets.py build/eloria-data
python3 eloria-assets/tools/validate_generated_assets.py build/eloria-data
```

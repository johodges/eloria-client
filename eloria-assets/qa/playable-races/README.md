# Playable race mesh QA

This stage replaces the single cuboid section-mesh set shared by all playable
characters with distinct rounded Cal3D meshes for every supported race and
gender. Actor IDs, the humanoid skeleton, semantic anchors, customization
categories, DDS dimensions, and compositor contracts remain unchanged.

Generated runtime coverage:

- twelve distinct race/gender body silhouettes;
- race/gender-specific shirt, legs, and boots section meshes;
- five race/gender-specific head meshes per playable actor;
- 108 authored runtime section meshes plus twelve complete QA body meshes;
- all 654 existing customization DDS files with three mip levels.

The silhouettes encode culture-specific height, shoulder, hip, head, and
material-profile proportions. Glasswardens gain crystal shoulder forms and
Ssarthi gain a swept head crest without changing attachment anchors.

```sh
python3 eloria-assets/tools/generate_all_assets.py build/eloria-data
python3 eloria-assets/tools/validate_generated_assets.py build/eloria-data
```

Validation asserts the frozen actor IDs, race/gender metadata, complete section
mesh references, topology floors, valid Cal3D geometry, normalized influences,
and twelve unique body-mesh digests. Shaded character-creation and equipment
switching captures remain pending a GPU-capable session.

# Luminous source models — 8 September 2026

The male and female Luminous player models now use reduced versions of the
approved original T-pose geometry. The Meshy rigged derivatives donate weights;
their reduced faces and collars are not used as the visual base.

| Model | Original triangles | Shipped triangles, including headwear | Joints |
| --- | ---: | ---: | ---: |
| Male | 1,937,266 | 35,158 | 77 |
| Female | 1,913,902 | 35,750 | 77 |

The models retain the source face, neck, collar, shoulders and clothing silhouette.
The female reduction reserves separate budgets for the head and eye region.
Original normals are transferred through the source UVs after reduction. No
procedural face morph, reconstructed neck, sleeve narrowing or global normal
smoothing is applied. Upper-trouser weights are smoothed across welded copies,
with opposite-leg influences constrained below the pelvis.

Seven independently editable RGBA textures per sex are in
`godot-client/assets/actors/native/race_textures/luminous_{male,female}`:
body, eyes, eyebrows, scalp, shirt, pants and boots. The alpha channel identifies
the group. Clothing also has neutral tint textures used by the runtime; the
original RGB crops are retained for editing. Each skin group samples its own
crop and maps into the shared face mask using its recorded UV scale and offset.
Skin, iris, brow, garment and hair appearance controls remain available.

The three existing hairstyles are fitted to each new skull. Band and cap meshes
follow Head. The original source neck replaces the previous rebaked neck join.
Equipment retains its original author measurements in `authoredBodyGirth` and
`authoredFootAnchor`; `refittedBodies` identifies these two replacement wearers.
Other races retain their existing geometry and equipment fitting behavior.

## Reproduction

Run authoring processes on at most eight logical CPUs. Set process affinity to
mask 255 on Windows and set OMP, OpenBLAS, MKL and NumExpr thread limits to eight;
run Blender with `--threads 8`.

Source inputs live outside the client repository at
`generate_models/eloria-races-meshy/luminous_human_{male,female}_tpose.glb`.
The original SHA-256 values are recorded in the shipped asset catalog. Keep
these inputs immutable. The corresponding `_tpose_rigged.glb` files are donors.

1. `prepare_luminous_source.py` splits the original into seven texture groups
   and validates every triangle, position, normal, UV crop and decoded RGB pixel.
2. `reduce_luminous_source_blender.py` welds duplicate positions while retaining
   UV loops, then reduces the mesh. Use `--protect-face` for the female source.
3. `rig_luminous_source.py` restores source normals, transfers donor weights and
   fits the canonical Rest_Pose with `preserve_source_shape=True`.
4. Split the reduced and canonical results with `prepare_luminous_source.py`,
   reusing reduced triangle labels for the canonical model.
5. `integrate_luminous_sources.py --workspace <workspace> --client-root <checkout>`
   installs the reviewed `work-output/luminous-source-base/rigged` and
   `work-output/luminous-female-source-base/rigged` candidates. It writes texture
   crops, masks, hair, headwear, equipment measurements and asset records.

## Verification

- Independent comparison with both reviewed candidates: all seven groups retain
  their triangle indices, positions, normals, UVs and original texture RGB.
- Canonical rest pose and inverse binds match; each body replays 613 samples
  across Idle_Subtle, Walk, Run_Female and Fighting_Idle without verifier errors
  or warnings.
- All sixteen characters: 1,920 skin/eye combinations, 14,249 runtime assertions;
  equipment fitting, sockets, clothing and restore cycles: 23,162 assertions.
- Face-mask landmark, hair/collar, equipment-registry and native race geometry
  regressions pass. Source-replacement tests check the actual new geometry;
  shared-body tests continue checking the other fourteen characters.
- Actual client renders reviewed from front, side and back, with dark skin,
  hair, headwear, running poses and a complete equipped outfit. Artifacts and
  detailed verification records are in `work-output/luminous-install` in the
  authoring workspace. These are a source-preserving baseline; small source
  folds and facets remain visible at close range.

The initial clean Godot import also reports existing PNG-decoding problems on
unrelated equipment files. The selected outfit loads and renders through the
client's existing direct-image fallback. Runtime tests report only the sandbox's
unavailable user log/cache and system certificate store; no script errors.

# Source-based race heads — 2026-09-08

The fourteen remaining race/sex heads now use the original high-resolution
Meshy `*_tpose.glb` artwork on the approved same-sex Luminous body. Votary
sources use the `whitehorn_votary_*` prefix. The rigged derivatives supply
the anatomical head anchor; they do not supply the new head geometry.

Regional reduction retains separate neck, cranium, and facial-detail budgets.
Original UVs, painted textures, and sampled source normals survive. Horns,
crystals, ears, scales, and facial markings remain part of the source head.
Existing Ssarathi tails are retained. Source filenames and SHA-256 hashes are
embedded in each GLB and recorded in the asset catalog.

The neck connection preserves the approved body below a narrow neck plane.
Joined boundary copies have matching positions, normals, and skin weights.
Clothing, hands, legs, groin, and back geometry retain the approved body's
attributes. Skin colors match the race; face masks are baked into the new
source UV atlas. Retired external neck masks are no longer applied.

All four authored hairstyles are refitted. Votary, Stoneborn, and male
Glasswarden hair uses a smooth cranial fitting surface so protrusions remain
exposed. Equipment uses refreshed body girth and foot measurements while
retaining its original authoring measurements. Open headwear measurements
recognize skinned hair and omit the unused bald slot.

Each complete model has about 40,500–51,100 triangles, including the optional
tail, and fewer than 40,000 vertices. The head-detail budget raises the total
triangle allowance to 50,000 before the tail. Unused material resources are
removed without changing rendered attributes or texture bytes; packaged GLBs
are about 11–19 MB.

Validation includes 36 geometry/equipment tests with 96 subtests, 12 native
asset tests with 1,572 subtests, the actual creation controls and independent
hair combinations, and front/head, hairstyle, equipped, and rear renders of
all 16 characters. The broader protocol suite retains the two pre-existing
capability/facing failures documented in `idle-pose-and-customization.md`.

Rebuild in a fresh scratch directory with
`build_high_resolution_race_heads.py`, then install reviewed candidates with
`install_high_resolution_race_heads.py`. Both accept explicit source/workspace
paths. The builder restricts itself and its children to CPUs 0–7 and passes
eight threads to Blender. This review used `work-output/race-heads/final`;
the final neck exports are named `compact-body.glb` (`--body-name` selects
them). Renders and preservation/packing reports are in
`work-output/race-heads` outside the checkout.

# Creature production QA

The thirty-two native Nymara creatures were rebuilt from the concept art to
production anatomy. The previous pass assembled every creature from three
stacked ellipsoids and four straight cylinders on a shared twenty-one bone
rig, with no textures on thirty-two of the thirty-five creature GLBs, so a
fox, a toad and a tortoise differed only in colour and blob proportions.

Each creature is now authored from a body plan in
`eloria-assets/tools/creature_anatomy.py`: a swept elliptical torso with real
chest, waist and haunch shaping; a shaped skull with muzzle, hinged jaw, ears,
eyes and nose; limbs tapered through credible knee, hock and ankle pivots down
to grounded feet with claws or cloven hooves; tapering tail chains; and the
horns, antlers, tusks, shells, quills, dorsal scutes and wing membranes that
distinguish one archetype from the next. Ten body plans cover canid, felid,
sabre-cat, ursine, suid, cervid, sprawling reptile, mustelid, lagomorph,
anuran, chelonian and drake anatomy.

Skinning is smooth multi-bone rather than rigid one-bone binding: weights come
from an inverse-distance blend over a curated candidate set per body part, so
shoulders, hips and necks deform without a rear paw pulling on the jaw. The
rig grew to twenty-four bones, adding a chest bone and a four-segment tail.
Bone *names* are unchanged where the runtime depends on them —
`godot-client/data/actors/models.json` binds attachment points to `head`,
`body` and `neck`.

All seven clips named by `godot-client/data/animations/creature.json`
(`Idle_A`, `Walk`, `Jog`, `Fighting_Idle`, `Sword_Attack`, `Hit_Chest`,
`Death_A`) are authored per body plan, with walk and trot gaits, a coiled
lunge-and-bite attack whose contact lands near 55% of the clip, and a death
that topples onto the flank and stays there. Locomotion is in place: the root
never translates horizontally, because the client drives world position.

## Files

- `creature_concept_comparison.png` — bind-pose renders of the checked-in GLBs
  beside the concept-art cell each creature was authored against.
- `creature_concept_comparison.json` — machine-readable pairing of creature
  slug, GLB path, concept sheet and grid cell.

## Reproducing

```
python3 eloria-assets/tools/build_native_nymara_glbs.py
python3 eloria-assets/tools/sunmane/creatures.py
python3 eloria-assets/tools/validate_creature_glbs.py \
    --catalog godot-client/data/actors/native_asset_catalog.json \
    --models godot-client/data/actors/models.json \
    --animations godot-client/data/animations/creature.json
python3 eloria-assets/tools/render_creature_qa.py <glb...> --output sheet.png
```

The build is deterministic: texture seeding uses `zlib.crc32`, not the
per-process-salted built-in `hash`, so rebuilding reproduces every GLB byte
for byte.

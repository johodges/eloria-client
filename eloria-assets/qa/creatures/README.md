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


## The wider concept-art roster

A second pass added **139 creatures** covering every distinct design across the
sixteen concept sheets. Those sheets hold 192 cells, but they are not 192
subjects: `47a41963`/`4dc46727` are alternate renders of one Amethyst Barrens
roster, `93197c59`/`1e840e1e` likewise for Sunmane Steppe, and the three
Amberwood sheets repeat many of each other's subjects. `creature_roster.py`
records one model per distinct design and maps every duplicate cell onto the
model that already covers it, so all 192 cells resolve while nothing is built
twice.

Creatures not already named by the repository were named from their design and
the locale of their sheet - Amethyst Scorpion, Lanternwyrm, Barrow Sovereign,
Reedmask Stalker, Mirrorhold Siren, Bramble Stag and so on.

### Skeleton families

The quadruped rig cannot express most of the new roster, so seven further
families were added in `creature_families.py`, each with its own rest
skeleton, geometry and gaits:

| Family | Creatures | Notes |
| --- | --- | --- |
| quadruped | 72 | extended with bovine, equine, pinniped and gryphon plans |
| biped | 47 | warrior, knight, monarch, mage, revenant, golem, construct, brute, primate, treant, duelist |
| amorphous | 14 | wisps, shard swarms, sprites, vortices, tentacled horrors - these hover |
| serpent | 10 | nine-segment coil chain; snake, sea serpent, eel, wyrm, hydra, naga |
| avian | 10 | folded wings at rest; wader, seabird, songbird, raptor, owl, harpy |
| arachnid | 7 | eight legs on three segments; spider, scorpion, crab |
| insect | 6 | six legs, elytra or membrane wings; beetle, moth, mantis |
| fish | 5 | swimming gait; pike, billfish, ray, armoured, axolotl |

Every family keeps the same runtime contract: bones named `root`, `body`,
`neck` and `head`, one root, at most four influences per vertex, and the seven
clip names in `data/animations/creature.json`.

### Actor types

The roster occupies **428-566**, one contiguous block after every range already
present in `models.json` (which ended at 427). Actor-type allocation belongs to
`eloria-server`; these ids are reserved client-side for the server to adopt.

### Grounding and hovering

Rest poses are settled so no creature starts below the floor, and every clip is
ground-clamped. Wisps, swarms and elementals are marked `hovers` in the
catalogue: they legitimately never touch `y = 0`, and the validator checks them
for floor penetration rather than contact.

### Files

- `roster_concept_comparison.png` / `.json` - each new creature beside the
  concept figure it was authored from. Concept crops use the true figure bounds
  found by `concept_sheet_index.py` rather than a uniform grid, because the
  subjects are not evenly sized or spaced and a fixed grid clips wings,
  antlers and tails.


## Surface fidelity

The first two passes shipped a single 256px **luminance** map per creature that
only modulated a flat base colour, so every fox, golem and serpent carried the
same grey grain and no surface relief at all.

`creature_surfaces.py` replaces that for the whole library - the original
thirty-two included - with, per creature:

* a **full-colour 256px albedo** that bakes the creature's own palette into the
  pattern, so `base` carries the body and `accent` tints markings, plates, moss
  and rime;
* a **192px tangent-space normal map** derived from the *same* height field, so
  the relief lines up with the pattern rather than fighting it;
* a **160px keratin pair** for horn, antler, hoof, quill and armour trim.

Twenty-six surface kinds are authored - fur, pelt, coat, fleece, bristle,
quill, hide, scale, fishscale, scute, shell, chitin, feather, warty, stone,
moss, barnacle, bark, metal, crystal, ice, cloth, slick, water, energy and dust
- each with its own height construction, plus per-creature markings (stripes,
rosettes, dapples, speckles, bands, blazes).

Because the albedo now carries the colour, the base-colour factor stays white
so the palette is not applied twice; the underside shares the grain and tints
with a factor instead of carrying a second map. The validator fails any
creature whose materials lack a colour texture or a normal map, and any
material that is magenta.

The ambient livestock were brought in line too: their generator previously
skipped normal maps on the grounds that livestock never cover enough screen to
pay for them, which left them the only untextured-relief creatures in the
library.

## Humanoid fidelity

The biped rig grew from 22 to 27 bones - a **waist** so the torso bends instead
of pivoting at the hips, **cloak** bones that carry capes and robes, and
**prop** bones in each hand so a staff or greatsword tracks the grip rather
than floating beside it.

Eleven shared body plans were not enough to tell forty-seven humanoids apart,
so `BIPED_DETAIL` overrides the plan per creature. Each one now carries what
the concept art gives it: crowns, helms with visors and crests, hoods, wide
duelling hats, tricorns, conical straw hats, masks, antlers, branch crowns,
thorn collars, crystal shards, orrery rings, cairn stacks, mill yokes and
waterwheels; and staves, sceptres, swords, greatswords, cutlasses, rapiers,
spears, tridents, halberds, axes, sickles, hooks, lantern staves, books, kite
and round shields. Geometry per humanoid roughly doubled, from about 1,950
triangles to about 4,100.


## Elementals

The fourteen amorphous creatures were the weakest group in the library: one
"core plus tendrils" rig gave every wisp, swarm, jellyfish and water nymph the
same silhouette - a ball standing on legs. None of them have a skeleton in the
concept art at all, so the family now carries **eight distinct forms**:

| Form | Creatures | Shape |
| --- | --- | --- |
| swarm | shardling, mirrorwing | no body; a cloud of angular shards or winged motes around a lit core |
| spectre | barrens, moorlight, ember wisps | a rising plume trailing streamers, with floating orbs |
| jelly | medusa tidepriest | a domed bell with a scalloped rim and a tentacle curtain |
| kraken | gilded devourer, mirefather leviathan | a heavy mass with a toothed maw and radial tentacles |
| nymph | springfly, verdant naiad, shardbound archivist | torso, head and arms dissolving into a turning skirt |
| ooze | lanternwake sprite | a settled translucent mound with salvage suspended inside |
| vortex | sluice elemental | curling arms sweeping out of a turning column |
| lance | tidelance construct | a ringed brass lance trailing a plume |

Streamers carry a travelling wave down each chain rather than swinging
rigidly, swarms and vortices turn on the spot, and the attack coils every
strand back before lashing them forward together.

Materials matter as much as shape here. Elementals are authored with
**alpha-blended translucency and an emissive glow** taken from the plan, and
their shards, orbs and props take the creature's own palette rather than the
bone-white keratin used for horn - which is what had turned every crystal
swarm grey. The lanternwake sprite's lantern, mill wheel and plank are only
visible because the slime around them is translucent.

`render_creature_qa.py` was taught to blend: opaque geometry draws first with
depth writes, then transparent surfaces back to front, and emissive is added
after shading. Without that these creatures could not be judged at all.


## Concept fidelity pass

Three systemic problems were keeping the library from reading like the
artwork, and none of them were fixable one creature at a time.

**Palettes were being invented, not sampled.** The first sampling pass kept
only the lit half of each concept figure, clustered it, and then pushed
saturation and value up independently per channel. Concept art is warm-lit, so
that pipeline drove almost every creature to the same handful of hues: a brown
bear and a grey-green troll both came out gold with one channel pinned at 238.
`extract_concept_palettes.py` now takes the median of the figure's *mid-tone*
band -- highlight and cast shadow both lie about a creature's own colour --
and lifts it toward an albedo value by a single factor across all three
channels, so the hue survives the lift. `apply_concept_palettes.py` bakes the
result into `creature_roster.py` and the legacy table, so a palette pass is
reproducible rather than hand-applied.

**Growth was scattered, not placed.** Moss, bramble, crystal and barnacles
were sampled with a world-space direction whose horizontal component was
always full magnitude. That works by accident on a quadruped, whose spine is
horizontal, and fails completely on a biped, whose spine is vertical: every
tuft pointed along the trunk axis and ended up inside the torso, which is why
moss trolls came out bald and mossy bears came out as uniform bushes. Growth
now rides the surface normal of the tube around the local spine direction,
biased toward its ridge; moss and vine hang with gravity, fungus caps turn to
face the sky, and only the mineral growths spike outward. Upright bodies also
expose their shoulders and arms to growth, and it stops at the collar so it
never buries the face.

**Creatures sharing a body plan were the same model twice.** Forty-seven
humanoids came from eleven plans and forty quadrupeds from twelve, so a wolf
and a hyena differed only in colour. `concept_proportions.py` measures each
segmented concept figure -- how lanky, how top-heavy, how solid, how tapered
it is *relative to the other creatures on its plan* -- and those four ratios
drive damped multipliers on the plan's heights, girths, shoulder and hip
widths, limb lengths and skull size. The silhouettes now diverge from the
artwork rather than from invention, and the ratios are clamped so a single odd
crop nudges a model without deforming it.

Alongside those: moth wings gained camber, veins and eyespots instead of
drawing as one flat plate; crystal growth erupts in a spread of unequal shards
rather than a tidy one-sided comb; bramble grows as a studded runner rather
than a fan of quills; and the wisps' plumes twist as they rise, throw flame
tongues, and let draped strands fall instead of stalling at the horizontal.

`build_creature_qa_sheets.py` regenerates all three comparison sheets and
their manifests, so the QA evidence in this directory can be rebuilt from the
checked-in GLBs rather than reconstructed by hand:

```
ELORIA_CONCEPT_DIR=/path/to/sheets \
    python3 eloria-assets/tools/concept_sheet_index.py
ELORIA_CONCEPT_DIR=/path/to/sheets \
    python3 eloria-assets/tools/extract_concept_palettes.py
ELORIA_CONCEPT_DIR=/path/to/sheets \
    python3 eloria-assets/tools/concept_proportions.py
python3 eloria-assets/tools/apply_concept_palettes.py
ELORIA_CONCEPT_DIR=/path/to/sheets \
    python3 eloria-assets/tools/build_creature_qa_sheets.py
```

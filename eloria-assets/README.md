# Eloria independent data pack

This directory contains source and tooling for an original Eloria client data
pack. It must not contain files extracted from an Eternal Lands installation,
release archive, website, or other Binary Data distribution.

Generate the bootstrap pack with:

```bash
python3 eloria-assets/tools/generate_all_assets.py build/eloria-data
```

Normal CMake builds generate this same directory automatically. The generated
data target tracks the asset tools and authored sources, so pulling a revision
with changed player models cannot leave legacy meshes in `build/eloria-data`.
Use `-DGENERATE_ELORIA_DATA=Off` only when intentionally managing a separate
runtime data directory yourself.

The wrapper runs independent generator pipelines in parallel, waits for each
dependency wave, then runs effects, the complete Nymara blocker, provenance,
and validation. Control concurrency with `--jobs` (for example `--jobs 4`).
Use `--dry-run` to inspect the schedule without writing files.

The equivalent manual sequence is:

```bash
python3 eloria-assets/tools/generate_bootstrap_pack.py
python3 eloria-assets/tools/generate_characters.py
python3 eloria-assets/tools/generate_humanoid_enemies.py
python3 eloria-assets/tools/generate_fantasy_archetypes.py
python3 eloria-assets/tools/generate_npcs.py
python3 eloria-assets/tools/generate_creatures.py
python3 eloria-assets/tools/generate_scenery.py
python3 eloria-assets/tools/generate_interactives.py
python3 eloria-assets/tools/generate_regions.py
python3 eloria-assets/tools/generate_item_atlas.py
python3 eloria-assets/tools/generate_runtime_assets.py
python3 eloria-assets/tools/generate_effects.py
python3 eloria-assets/tools/generate_nymara_complete.py build/eloria-data
python3 eloria-assets/tools/check_provenance.py
```

The complete sequence produces 25 playable ELM maps plus `nomap.elm` and
`newcharactermap.elm`. If only eight ELM files exist, run the Nymara generator
command above to add the twelve Nymara exteriors and seven interiors.

The bootstrap includes Emberhaven plus five original biome regions. Region maps
carry native ELM object IDs and emit `regions_eloria.json`, allowing the server
to bind harvesting rules to exactly the models placed in each generated map.

The character generator produces an original low-poly humanoid, fourteen-bone
skeleton, four actor definitions, and idle, walk, run, attack, pain, death,
harvest, and sitting animations in Cal3D XML source formats.

The luminous player actors replace their procedural body with CC0 Quaternius
male and female base geometry. Their supported client actions use retargeted
Universal Animation Library clips, while the existing Eloria customization
contract continues to expose 16 hair colors, 12 eye colors, and 6 skin colors.

The creature generator produces sixteen animals and sixteen monsters with original
silhouettes, textures, a thirteen-bone quadruped rig, and shared idle, walk,
run, attack, pain, and death animation clips. Actor IDs 200-207 are reserved
for the first independent creature set; the expanded roster continues through
actor ID 231. Familiar real-world names describe only newly generated assets.

The humanoid-enemy generator adds twelve original living, undead, spirit, and
construct enemies using actor IDs 232-243. They share a dedicated humanoid rig
and idle, combat-idle, walk, run, attack, cast, pain, and death animations.

The fantasy-archetype generator adds twelve recognizable but independently
modeled enemies using actor IDs 244-255: lizard man, minotaur, naga, snakeman,
gnoll, hobgoblin, orc, harpy, vampire, werewolf, satyr, and dragon.

The testing-runtime stage adds eight original NPC models, a fresh 64-item icon
atlas, startup fonts and cursors, fallback objects and maps, and independent
configuration stubs. These assets are intended for functional testing and will
need an art-direction pass before a production release.

The interaction-and-effects stage adds twenty world props and crafting stations,
eight projectile models, three particle atlases, a parser-compatible missile
manifest, and ten original spells. Spell reagents use independently designed
catalyst, resonant, and anchor roles; four rechargeable focuses substitute an
Attunement Charge for the anchor. Four 25-icon atlases cover the 85-item catalog.

The scenery generator produces 43 native E3D assets: general scenery, nine
modular architecture pieces, ten biome-specific objects, and seventeen
original harvestables, including Stormglass, Moon Salt, and Grave Moss nodes.
Real-world resource names are used only with original
geometry, textures, placement, descriptions, and future balance data.

The region generator adds desert, snow, swamp, tropical, and volcanic maps,
each with a small modular landmark and four biome-appropriate resource nodes.

# Eloria independent data pack

This directory contains source and tooling for an original Eloria client data
pack. It must not contain files extracted from an Eternal Lands installation,
release archive, website, or other Binary Data distribution.

Generate the bootstrap pack with:

```bash
python3 eloria-assets/tools/generate_bootstrap_pack.py
python3 eloria-assets/tools/generate_characters.py
python3 eloria-assets/tools/generate_humanoid_enemies.py
python3 eloria-assets/tools/generate_creatures.py
python3 eloria-assets/tools/generate_scenery.py
python3 eloria-assets/tools/generate_regions.py
python3 eloria-assets/tools/check_provenance.py
```

The bootstrap includes Emberhaven plus five original biome regions. Region maps
carry native ELM object IDs and emit `regions_eloria.json`, allowing the server
to bind harvesting rules to exactly the models placed in each generated map.

The character generator produces an original low-poly humanoid, fourteen-bone
skeleton, four actor definitions, and idle, walk, run, attack, pain, death,
harvest, and sitting animations in Cal3D XML source formats.

The creature generator produces sixteen animals and sixteen monsters with original
silhouettes, textures, a thirteen-bone quadruped rig, and shared idle, walk,
run, attack, pain, and death animation clips. Actor IDs 200-207 are reserved
for the first independent creature set; the expanded roster continues through
actor ID 231. Familiar real-world names describe only newly generated assets.

The humanoid-enemy generator adds twelve original living, undead, spirit, and
construct enemies using actor IDs 232-243. They share a dedicated humanoid rig
and idle, combat-idle, walk, run, attack, cast, pain, and death animations.

The scenery generator produces 43 native E3D assets: general scenery, nine
modular architecture pieces, ten biome-specific objects, and seventeen
original harvestables. Real-world resource names are used only with original
geometry, textures, placement, descriptions, and future balance data.

The region generator adds desert, snow, swamp, tropical, and volcanic maps,
each with a small modular landmark and four biome-appropriate resource nodes.

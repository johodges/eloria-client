# Eloria independent data pack

This directory contains source and tooling for an original Eloria client data
pack. It must not contain files extracted from an Eternal Lands installation,
release archive, website, or other Binary Data distribution.

Generate the bootstrap pack with:

```bash
python3 eloria-assets/tools/generate_bootstrap_pack.py
python3 eloria-assets/tools/generate_characters.py
python3 eloria-assets/tools/generate_scenery.py
python3 eloria-assets/tools/check_provenance.py
```

The first milestone intentionally generates a small, object-free island named
Emberhaven and placeholder UI sheets. It establishes a legally independent,
reproducible baseline; character models, production UI sheets, sounds, and
scenery still require original implementations before a public binary release.

The character generator produces an original low-poly humanoid, fourteen-bone
skeleton, four actor definitions, and idle, walk, run, attack, pain, death,
harvest, and sitting animations in Cal3D XML source formats.

The scenery generator produces 43 native E3D assets: general scenery, nine
modular architecture pieces, ten biome-specific objects, and seventeen
original harvestables. Real-world resource names are used only with original
geometry, textures, placement, descriptions, and future balance data.

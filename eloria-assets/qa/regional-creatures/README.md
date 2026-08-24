# Regional creature family QA

The comparison sheet renders one representative generated XMF from each creature territory:
Crownwater, Whitehorn, Amethyst, Sunmane, Amber/Grey, Verdant, and Manymouth. Territory-
derived palettes now reinforce the regional concepts while per-species variation and surface
features preserve individual readability.

All 28 actor types remain above 255 and retain their creature skeleton, animations, collision
bounds, sound events, drops, and summoning hooks. Validation freezes every actor reference,
requires all seven regional families, checks 512x512 materials and topology floors, and rejects
duplicate mesh payloads. GPU-backed shaded creature and packet-path captures remain pending.

```sh
python3 eloria-assets/tools/generate_all_assets.py build/eloria-data
python3 eloria-assets/tools/validate_generated_assets.py build/eloria-data
```

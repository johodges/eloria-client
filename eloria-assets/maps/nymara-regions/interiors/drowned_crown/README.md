# The Drowned Crown

The older palace beneath The Crown Basilica, half taken by the lagoon. Reached
from the `basilica-undercroft` portal on the Crownwater region map.

Built from `crownwater/source/interiors_crownwater.py`. This is the only
Crownwater interior whose programme was given rather than invented: every one of
the ten subjects in `concept.json` - flooded vestibule, water galleries,
submerged arch, shell altar, statue court, water channel, collapsed dome, air
pocket, objective hall, and the limestone/shell/brass material study - is an
authored space or the material of one.

| | |
|---|---|
| Triangles | 25,334 |
| GLB | 5.24 MB |
| Walkable cells | 17,100, **0** without a surface under them |
| glTF validator | 0 errors |
| Client frames | 8, in `references/captures/` - real, not offline previews |

The water line is held flat at y = -6.05 throughout and the floors step down
beneath it, so the wading deepens as you go in until the collapsed dome lets the
light and the air back.

**Its detail board is truncated** (786,446 bytes, the same defect as fifteen of
the seventeen region boards), so there is no panel comparison for it. The
subjects were worked from `concept.json`'s written list.

**Its server portal is contested**: this file's `concept.json` declares
`parentRegion: crownwater`, while `eloria-server`'s `config/eloria/maps.txt`
links it to `mirrorhold`. Those lines are deliberately left untouched. See
`../CROWNWATER_INTERIORS.md`.

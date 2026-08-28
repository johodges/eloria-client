# Resonant Vault

The Amethyst Barrens interior beneath the Glasswarden Observatory. The ten
concept perspectives in `concept.json` are now built: this directory holds the
runtime package, not just the brief.

    world.glb                 self-contained glTF 2.0, 82,360 triangles, 6.68 MB
    world.json                interior manifest
    collision.bin             half-metre walkability grid (EWCG v1), 18,876 cells
    world.glb.validator.json  0 errors, 0 warnings
    verification-report.json  0 errors
    references/
      00-concept-detail-board.png    the ten-panel brief (TRUNCATED on disk, see below)
      00-checkpoint-contact-sheet.png  all ten subjects, offline rasteriser
      captures/                      the same ten as individual frames, plus index.json
      client-captures/               the same ten through the real WorldLoader

Built by `../../amethyst_barrens/source/build_interiors.py`. See
`../AMETHYST_BARRENS_INTERIORS.md` for the set of four and what is not verified.

The detail board in `references/` is truncated to 786,444 bytes and only its
first rows decode - the same cut that affects nine of the eleven region boards.
The intact board was supplied separately and is what this interior was authored
from; it has not been committed here because it was not supplied as a file in
this package.

`eloria-server`'s map table routes `resonant_vault` to and from `four_gates`.
This package and the region manifest both assume Amethyst Barrens above. The
server is authoritative, so that needs reconciling.

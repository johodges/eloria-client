# Eloria Client modifications

Eloria Client is an independent modified version of the Eternal Lands Official
Client source code. It is not affiliated with or endorsed by Eternal Lands,
Radu Privantu, or Maura Privantu.

The client source and modifications remain available under the Eternal Lands
Client Public License 1.0 in `eternal_lands_license.txt`. No official Eternal
Lands Binary Data is included in the Eloria data pack.

## 2026-08-22

- Added independent Eloria product branding and project links.
- Disabled the official Eternal Lands web-update endpoint.
- Added a reproducible generator for an original bootstrap data pack and map.
- Added asset provenance and compliance checks.
- Added a single Eloria server profile targeting TCP port 2000.
- Added command 247 for 16-bit actor types while retaining legacy actor packets.
- Expanded the actor registry to 1024 entries and made attachments sparse.

## 2026-08-23

- Extended spell-cast packets with an optional one-byte power selection.
- Added power display and right-click adjustment to the spell window.
- Added user-configurable `#K_SPELLPOWERUP` and `#K_SPELLPOWERDOWN` hotkeys.
- Preserved server-side per-effect preferences whenever the client has no explicit override.
- Replaced the generic essence economy with catalyst, resonant, and anchor materials.
- Added four item atlases for original magical materials, focuses, charges, and Echoes.

## 2026-08-28

- Rebuilt equipment attachment on character-space sockets solved from the rig,
  replacing identity parenting that put every weapon sideways through the actor.
- Skinned capes, leg armour, body armour and boots to the shared 65-joint rig so
  worn equipment deforms with every clip instead of riding one bone.
- Reauthored all 66 equipment GLBs against the measured body silhouette at body
  scale, with PBR base-colour and normal maps and roughly five times the mesh
  density of the previous primitives.
- Moved the boots part from the pelvis to both feet and the cape behind the
  actor rather than in front of it.
- Added a rig fit scale so one authored asset fits every race and both body
  variants.
- Realigned the item icon atlases to the grid the client samples, restored the
  icons that the placeholder block had truncated, repainted the sixteen Nymara
  material icons, and added an explicit unknown-item glyph.
- Authored a generic equipment tier claiming the legacy visual-id space
  directly: 155 ids across seven parts, served by 43 meshes under a runtime
  tint, so the craftable economy has geometry instead of drawing nothing.
- Added great sword, battle axe, cutlass, rapier, club, quiver and glove
  shapes, and enchanted-metal finishes for the elemental weapon ladders.
- Corrected sRGB palettes being written into glTF's linear colour factors,
  which had untextured equipment surfaces rendering about forty percent bright;
  creature, race, and hair rebuilds remain separate asset work.
- Removed the three visual-id aliases, which now collide with real generic ids,
  and made an authored NPC look outrank the server's appearance bytes.
- Cached parsed equipment geometry and rebound skins per model.
- Audited the harvestable layer and recorded the findings in `docs/harvestable-audit.md`.
- Added `eloria-assets/tools/harvestables.py` as the single harvestable catalogue.
- Rebuilt every harvest node model at the fidelity of the surrounding landmark kit.
- Gave foliage harvestables alpha-tested, double-sided materials.
- Added sixteen general-purpose harvestables covering the everyday crafting economy.
- Wrote `harvestable.lst` and `entrable.lst` as the lowercase basenames the client looks up.
- Scattered harvest nodes across each region instead of repeating four fixed coordinates.
- Wrote ELM object and light coordinates in world units instead of height-map cells.
- Added decorative 2D ground flora and the map writer support the client already had.
- Moved harvestable item ids out of the equipment range and added `validate_harvestables.py`.

Every later modification to an upstream source file must carry a prominent
dated notice as required by section 3(c) of the client license.

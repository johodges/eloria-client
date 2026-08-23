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

Every later modification to an upstream source file must carry a prominent
dated notice as required by section 3(c) of the client license.

# The Last Lantern: native client integration

Lantern Reach is now an opening adventure in the main Godot client and the
matching `dev-server` checkout. New characters enter a private island, complete
28 server-owned objectives across eight scenes, and sail into Four Gates with
their actual inventory, equipment and storage. The final objective is a real
conversation with Gate Warden Ilyon.

Run `prototypes/last-lantern/play.cmd`, click Connect, then New Character. The
launcher prepares local terrain, starts a loopback server on port 2008 and runs
`godot-client/project.godot`. It uses normal gameplay timings and a separate
`.local/native/characters.sqlite3` database. Closing the client stops its local
server. `-Fresh` creates another profile; it does not erase existing characters.
Existing characters on a matching server can opt in once with `#tutorial lantern`.
The original prototype's `project.godot` remains available for design reference.

## What is integrated

| Lesson | Native control | Completion evidence |
| --- | --- | --- |
| Movement | Ground clicks, camera drag/zoom | Server position reaches the displayed marker |
| NPCs | NPC dialogue options | Caldus accepts the request and grants ordinary inventory items |
| Map | Tab or Map toolbar button | Map window actually opens |
| Harvesting | Click Reed / Quartz in the viewport | Successful server harvests; tools and capacity apply |
| Storage | Category, item, quantity, Deposit / Withdraw | Inventory and storage transfers succeed |
| Manufacturing | Torch recipe, quantity 1, Mix Now | The normal recipe produces a real Torch |
| Equipment | Inventory double-click or drag | Sword and shield occupy real equipment slots |
| Combat | Click the otter | Normal combat resolves its defeat |
| Loot | Ground bag, Get All / auto-gather | Real drops reach inventory |
| Food | Double-click Bread | An actual meal is consumed and food reaches 35 |
| Character growth | Statistics, Character, attribute +, confirmation | A pickpoint is spent by the server |
| Repair | Click the housing | Three Reed and one Quartz are consumed |
| Beacon | Click the housing while carrying the crafted Torch | The server lights the beacon and opens the return stair |
| Trading | Merchant Buy / Sell mode, item, quantity, Trade | Real meat sale and Bread purchase succeed |
| Departure | Boarding point and native confirmation | Character changes to Four Gates; Ilyon completes the quest |

The guide highlights the existing control relevant to the current lesson. It
uses the native manufacturing side pane, fits beside storage and merchant
windows, and leaves the world clickable. Storage's inventory column now uses
server-provided item names, allowing instructions to identify Reed unambiguously.
The wooden shield's embedded JPEG is correctly labelled in its GLB metadata.

## State and map ownership

- `dev-server/eloria/lantern.py` defines the sequence and listens to ordinary
  gameplay outcomes. `last_lantern` and `lantern_*` quest fields are persisted
  with the character. The client cannot grant items or advance gameplay lessons.
- Capability `lantern_tutorial_v1` enables server packet 207, a validated JSON
  guide snapshot. Client packet 203 accepts only map-opened, skip-request and
  refresh actions. Skip and sailing use the existing popup protocol.
- `eloria-assets/maps/lantern-reach/` is registered as `lantern_reach`. Its native
  world loader, actors, resource objects, picking, markers and equipment remain
  in charge of presentation. `lantern_scene.gd` adds water, gates, lights and boat
  motion; it contains no local quest simulation.
- The server clones the template for each owner. Other characters cannot enter
  that copy. Gate collision is reconstructed from saved facts, using the authored
  120 × 120 grid in `config/eloria/lantern_reach.json`.
- Object IDs and approach tiles come from the authored layout. Loot markers use
  the actual bag location. Arrival checks use the marker's approach coordinate.
- The optional manifest `asset.mapBounds` frames the playable island on the
  full map, while `asset.bounds` still describes its large ocean backdrop.

Reconnect restores the stage, gates and belongings. Supplies held in inventory,
equipment, storage or a dropped bag are not duplicated. Caldus and the bench
recover missing essentials after loss or crafting failure. A novice defeat keeps
the kit and resets the otter; a defeated otter does not respawn. Global days that
prohibit harvesting, mixing, food or combat cannot block the private rescue.

The causeway encounter is a level-1 Mirrorfin Otter named "Storm-frightened
otter", rendered with the updated `river_otter.glb` model (actor type 400).
It keeps the novice combat stats and guaranteed Raw Meat drop for the trading
lesson. The internal `lantern_boar` species and `boar` marker IDs remain stable
for the existing encounter hooks and authored target references.

The template is intentionally absent from the public portal and invasion graphs
and from required public exploration totals. Existing quest progress is preserved
when a character opts in; the old opening walkthrough is suppressed for new
characters that finish or skip this opening adventure.

## Verification

Verified locally on 2026-09-09: **2,112 server tests and 498 subtests pass**;
the complete 28-objective rendered native-client playthrough passes, including
Four Gates and Ilyon; all 25 tutorial protocol checks and the storage regression
checks pass. The rendered run also verifies real object picking and that the
highlighted Mix Now button and manufacturing window remain on screen. A separate
rendered map check passes with the island framing and smaller marker discs.

- `dev-server/tests/test_lantern.py`: complete real-handler playthroughs with and
  without auto-gather and early equipment, persistence, private-copy isolation,
  defeat, crafting recovery, lost loot, older-character opt-in and marker arrivals.
- `godot-client/tests/integration/rendered_lantern.gd`: creates a real character
  over a loopback connection, uses native UI callbacks and viewport picking,
  completes the entire rescue, and captures each lesson window. Craft failures
  are recovered through the actual cache and manufacturing controls.
- `godot-client/tests/test_lantern_protocol.gd`: 25 packet validation checks.
- `godot-client/tests/test_storage_organizer.gd`: native storage regression checks.
- The launcher was exercised with the real server and a headless client; local
  terrain preparation and server shutdown completed successfully.

The broader client protocol test currently has two existing failures: the missing
`magic_book_v2` capability fixture and a walk/run facing assertion. Both also
reproduce using the repository's HEAD protocol and HEAD test, independently of
these tutorial changes. Dedicated tutorial and storage checks pass.

Client and server changes must be installed together. This implementation has
been tested locally; this work does not deploy or push a live server.

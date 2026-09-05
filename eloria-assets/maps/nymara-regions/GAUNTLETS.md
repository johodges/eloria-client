# The gauntlets

Eight instanced routes, one per region theme, run by a party from a keeper
NPC standing in that region. Each is a linear road under the region: a
staging hall, seven legs each behind a barred way, a fork where the party
picks one of two ways, a boss court, and a vault with the reward cache and
the waystone home. The maps come from `_toolkit/gauntlets/` (designs, rooms,
composer); the server side is written from the same designs by the server's
`tools/author_gauntlets.py`.

| route | region | keeper | bands (a/d) | boss |
|---|---|---|---|---|
| The Resin Road | Amberwood | Old Pyke, at the charcoal camp | 8-30, 24-55 | the Boar King |
| The Ice Stair | Whitehorn Range | Hesk Varne, at the mine | 10-35, 28-65 | the Rime Matriarch |
| The Coil Causeway | Ssarathi Ruins | Ssethis the Doorkeeper, at the south water gate | 20-50, 40-80 | the Sunscale Sovereign |
| The Barrow Run | Grey Moors | Widow Carrow, at the breached barrows | 8-30, 25-60 | the Barrow Reeve |
| The Drowned Arcades | Crownwater | Tollmaster Quent, at the customs hall | 5-30, 24-55 | the Bell Warden |
| The Red Canyon | Sunmane Steppe | Rider Anse, at the east gate | 1-25, 20-50 | Duskmane |
| The Resonant Cut | Amethyst Barrens | Grinder Vell, at the geode cave | 5-30, 25-65 | the Songstone Tyrant |
| The Bund Run | Manymouth Delta | Bund Warden Ilse, at the paddy watchtower | 8-30, 30-70 | the Bund Tyrant |

The lower band of each road ends on a bigger, named one of an ordinary
species (an inline boss); the upper band ends on a boss that is its own
creature (`boss: 1` in `creatures.txt`, a fight in `bosses.def`: it heals on
the blow and calls its region up out of the ground in three stages).

## How a run works

- **Starting.** The party leader talks to the keeper (NPC role `instance`).
  The menu lists the keeper's roads and bands; everyone in the leader's
  party standing within eight tiles goes in together, onto the first copy of
  the map that no party holds (three copies per route, so three parties can
  run the same road at once). Each member must be inside the band's a/d
  bracket and off cooldown (`cooldown_hours`, per route). Solo is allowed.
- **Gates.** Every leg starts behind a barred way: a cut in the floor wider
  than two tiles with a gate prop across it. Using the gate (a `gate`
  interactive bound to a same-map portal) steps you through when the leg
  behind it is quiet; before that it tells you so. The first gate opens as
  the run begins.
- **Waves.** A leg's wave lands when the first participant steps into its
  room (`trigger: enter`), or the moment its gate opens (`at_gate`). Three
  variants exist per leg per band, generated from the band's roster; one is
  picked per run. `advance: cleared` opens the next gate when everything is
  dead; `time:N` opens it N seconds after the wave lands whether or not it
  is dead, which is what the bridges do - you can run them.
- **The fork.** Both branch gates open when the hub is quiet. The first
  branch gate a participant uses is the party's choice; the other seals.
  The gate after the fork opens when the chosen branch is quiet.
- **The court.** The adds land first and the boss is on the floor at once.
  When it falls its horde disperses, the run is recorded (the `instances_done`
  counter, and a best time per route in the character's quest state), and
  the cache in the vault opens once for each participant.
- **Leaving.** The waystones in the staging hall and the vault take you
  home to the keeper's side. Dying on the road wakes you there too. Time
  running out, or ninety seconds with nobody on the map, ends the run and
  frees the copy.
- **Mutators.** Rolled per run and announced at the first gate: `frenzy`
  (creatures at 125% health), `hunted` (every room is full when you reach
  it), `bounty` (the cache rolls twice), `swift` (a quarter less time),
  or none.

## Files

Client: `interiors/<route>/` packages (`world.glb`, `world.json` with a
`gauntlet` block, `collision.bin`), `server-collision/<route>.bin`, and
registry entries for each route and its copies (`_2`, `_3` alias the
route). Server: `config/eloria/instances/<route>_<band>.def` (the
`[instance]` header carries `keeper`, `copies`, `exit_map`, the cache and
waystone objects and the mutator table; each `[leg]` carries its gate,
trigger, advance, bounds and `[variant]` groups; a fork's `[branch]` blocks
are legs of their own), `spawn_groups/invasion/gauntlets_nymara.def` (the
waves and courts), and marked blocks in `maps.txt` (map lines, gate and exit
portals), `interactives.txt`, `harvesting.txt` (the bonus nodes),
`drops.txt` (cache tables, boss drops), `npcs.txt` and `npc_dialogue.txt`
(the keepers). The runtime is `eloria/gauntlets.py`.

## Rebuilding

```sh
cd eloria-assets/maps/nymara-regions && python _toolkit/gauntlets/build.py <region>
# server side
python tools/author_gauntlets.py --client <client repo> --apply
python tools/sync_authored_collision.py --client <eloria-assets/maps>
python tools/generate_nymara_maps.py <maps dir>
```

A design change (`_toolkit/gauntlets/designs.py`) is a rebuild of that
route's package followed by the authoring tool; the waves are regenerated
deterministically from the roster, so nothing else has to be edited.

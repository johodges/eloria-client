# Migration traceability matrix

Status: NOT_STARTED, FOUNDATION, IMPLEMENTED, VERIFIED, BLOCKED.

| Legacy feature | Source | Godot target | Test/evidence | Status |
|---|---|---|---|---|
| TCP framing | client connection; server protocol.py | network/protocol.gd | byte fixtures + fragmented/combined reads | FOUNDATION |
| Configurable endpoint | servers.c | responsive login scene/config | rendered CI connected to `18.235.240.60:2000` through the real login/creation UI | VERIFIED |
| Login | loginwin.c; LOG_IN | auth/network | disposable character creation and subsequent login against the development server; credentials redacted | VERIFIED |
| Actor spawn/update/remove | multiplayer.c; server actor packets/commands | state/actors | actor packet + command-step fixtures; rendered two-client native spawn, authoritative movement, ray selection, and disconnect cleanup | VERIFIED |
| NPC activation/dialogue | gamewin.c; server protocol/world | protocol/state/dialogue UI | byte/decode fixtures plus local unmodified-server enhanced NPC, activation, reply, and close; development Four Gates rendered dialogue remains pending | IMPLEMENTED |
| Chat send/receive + PM | legacy `text.c`, `chat.c`, `pm_log.c`; server `protocol.py`, `server.py`, `world.py` | exact RAW_TEXT/SEND_PM codecs, channel state, safe lower-left presentation | exact bytes and channel/color/UTF-8 fixtures; local PM contract; rendered bidirectional development-server local chat and unobscured lower-left UI | VERIFIED |
| Title/login artwork | generated Eloria branding DDS | portable PNG copies + responsive themed login/creation | 1280x720 bounds fixture covers login and creation action rows; user screenshot comparison | IMPLEMENTED |
| GLB map + JSON | GLB runtime/map.c | world/map loader | `four_gates` alias fixture, headless attach, and rendered development-server Four Gates capture | VERIFIED |
| Native luminous models | actor GLB runtime/assets | actor presentation | rendered female luminous GLB with three visible native meshes and no fallback | VERIFIED |
| Movement reconciliation | client movement/server authority | controller/state | rendered real-server MOVE_TO changed authoritative tile `(768,480)` to `(773,481)`; actor yaw and camera followed | VERIFIED |
| Sit/stand | legacy `gamewin.c`, `keys.c`, `multiplayer.c`, `client_serv.h`; server `protocol.py`, `server.py`, `world.py` | exact desired-state codec, actor reducer, native transition/rest animation state | exact `07 02 00 01` / `07 02 00 00` fixtures; rendered real-server explicit sit/stand and automatic stand-on-move | VERIFIED |
| Core HUD/chat | `hud.c`, `hud_misc_window.c`, `gamebuttons*.dds` | ui/hud | lower action/window rail; right stats and item/spell quickbar; unsupported windows visibly disabled | IMPLEMENTED |
| Inventory | `items.c`, `items.h`, `hud_quickbar_window.c`; server `protocol.py`, `world.py`, `items.py` | protocol/state/inventory UI | exact snapshot/update/remove/use/move/cooldown fixtures; two-click placement; rendered real-server 3-item snapshot with 3/3 visible icons and quantities | VERIFIED |
| Equipment | `items.c`, `items.h`; server `protocol.py`, `world.py`, `items.py` | equipment slots and actor attachment presentation | exact wear-slot/move fixtures; rendered real-server spear equip/unwear, slot reconciliation, actor visual, skeleton fallback, and cleanup; data-driven aliases resolve legacy guard visuals `0:11`, `1:5`, and `2:11` to native visuals `0:112`, `1:105`, and `2:105`; rendered native verification remains pending | IMPLEMENTED |
| Character statistics | legacy statistics/HUD code; server `protocol.py`, `stats.py`, `world.py` | authoritative reducer, resource rail, statistics window | rendered real-server health, ether, food, carry, attributes, and skills; visually inspected non-overlapping 1280x720 window | VERIFIED |
| Item quickbar | `hud_quickbar_window.c`; server inventory state | first eight authoritative inventory positions | rendered real-server 3/3 populated quick items with visible icons and quantities | VERIFIED |
| Combat | `gamewin.c`, actor command handling; server `protocol.py`, `server.py`, `world.py` | selected-target attack action, health/combat/death replication | exact attack/damage/heal fixtures; local server approach, facing, enter-combat, and attack commands | IMPLEMENTED |
| Player trade | legacy `trade.c`, `items.c`, `multiplayer.c`; server `protocol.py`, `server.py`, `world.py` | exact codecs, reducer, selected-player action, three-column offer window, per-slot inventory/storage destinations | exact request/offer/remove/inspect/two-phase accept/reject/exit/destination fixtures; reducer cleanup; local two-client TCP request, offer, restoration, cancel, and completion verified | IMPLEMENTED |
| Storage | legacy `storage.c`, `multiplayer.c`; server `protocol.py`, `server.py`, `world.py`, storage NPC dialogue | exact codecs, reducer, category/stored/inventory window | exact category/deposit/withdraw/inspect fixtures; local TCP NPC activation, open, category selection, deposit, inspect, withdrawal, and inventory restoration | IMPLEMENTED |
| Ground bags | legacy `bags.c`, `bags.h`, `gamewin.c`, `multiplayer.c`; server `protocol.py`, `server.py`, `world.py` | exact codecs, map-scoped reducer, pickable grounded marker, contents/inventory window | exact create/list/inspect/item/remove/close/destroy fixtures; local TCP drop, create, open, partial pickup, close/reopen, final pickup, destroy, and inventory restoration | IMPLEMENTED |
| Knowledge/books | legacy `knowledge.c`, `knowledge.h`, `multiplayer.c`; server `knowledge.py`, `protocol.py`, `server.py`, `world.py`, `config/items.txt`, `config/books.txt` | hashed data-driven catalog, ownership reducer, inspection window | exact bitset/new/index/text fixtures and UI bounds; local TCP fresh-character 49-byte ownership bitset and first/last catalog inspection | IMPLEMENTED |
| Magic | `spells.c`, `hud_quickspells_window.c`; server `magic.py`, `protocol.py`, `world.py`, `config/spells.xml` | exact cast codec, sigil/result/buff state, separate spell quick slots | cast/sigil/result/availability fixtures; live owned-spell success pending | IMPLEMENTED |
| Manufacturing | legacy `manufacture.c`, `manufacture.h`, `items.c`, `multiplayer.c`, `client_serv.h`; server `recipes.py`, `knowledge.py`, `protocol.py`, `server.py`, `world.py`, `config/recipes.txt`, `config/items.txt`, `config/books.txt` | exact codec, hashed 389-recipe catalog, authoritative inventory-slot resolver, filter/detail/action window | exact packet/catalog/availability/UI bounds fixtures; local TCP exact-selection rejection plus successful Fire Essence mix with raw-text, inventory, item-text, and partial-stat responses | IMPLEMENTED |
| Harvesting | respective modules; server harvest-node manifests | reducer/window and world-object selection | action/result traces; Four Gates harvest object IDs unavailable | NOT_STARTED |
| Quest journal | legacy `questlog.c`, `quest_journal.c`, `multiplayer.c`, server command 224 contract | server-owned journal reducer/window | legacy decoder is audited, but the unmodified server does not emit command 224 or another complete journal snapshot; dialogue inference is intentionally rejected | BLOCKED |
| Hotkeys/settings | keys.c/elconfig.c | InputMap/settings | viewport routing fixture verifies rotate/pan/zoom; live click-to-move recheck pending | FOUNDATION |

## Rendered development-server evidence gate

`tests/integration/rendered_server_session.gd` drives the real login and character-creation UI against the authorized development endpoint from an opt-in Xvfb GitHub Actions job. It generates a disposable name and strong password in memory, never prints either value, and records credentials only as `REDACTED`.

The gate fails unless it proves all of the following before uploading evidence:

- the server supplied a map ID, local actor ID, spawn DTO, and authoritative tile;
- the local actor has a visible native luminous GLB with at least three meshes and no missing-model fallback;
- a navigation-surface ray exists below the spawn and the actor foot agrees with it;
- the actor is in front of and within the gameplay camera frame;
- right-drag rotation, middle-drag pan, and wheel zoom change their respective
  camera state while the actor remains in frame, then restore actor follow;
- the white player marker follows the actor and both map cameras include its layer;
- a left-click routed through the gameplay viewport produces a server actor-tile update;
- a second real connection creates and logs in a disposable player without
  persisting credentials, and the primary client receives its authoritative
  spawn, movement, and disconnect;
- the remote player uses a visible native luminous model, can be selected by a
  world-space ray, and is removed from both state and presentation after its
  connection closes;
- chat submitted through the primary lower-left UI reaches the second real
  client, and chat sent by the second client is decoded and presented by the
  primary reducer/UI;
- the authoritative inventory and statistics snapshots are non-empty, the
  inventory and statistics windows fit within 1280x720 without covering the
  fixed resource rail, and every item has a native or explicitly disclosed
  independent-Eloria substitute icon plus its quantity; character values, item
  quick slots, and all configured spell quick slots are presented from that
  state;
- selecting every real backpack item sends `LOOK_AT_INVENTORY_ITEM`, receives
  its authoritative description, and presents the selected description in the
  inventory window;
- equipping the real guard spear moves it into wear slot 36, applies the
  server-broadcast actor visual to the native skeleton through a visible
  development fallback, and unequipping restores inventory and clears it;
- each 1280×720 capture contains rendered color variation rather than a dummy frame.

The artifact contains default, rotated, panned, zoomed, full-map, and
post-movement PNGs, selected-remote-player, chat, inventory, and statistics
PNGs plus an equipped-fallback PNG, and sanitized session, camera-state,
movement, remote-actor, chat, inventory/statistics, and equipment JSON. A
passing structural assertion is still classified separately from human visual
inspection of those PNGs.

### Verified evidence: workflow run 33068336019

The opt-in rendered job passed against the development server on commit
`52f365a08b6f4ec274f165d107f6185f38532a7c`. Its uploaded artifact is
`rendered-server-session` (artifact ID `9644708960`). Human inspection of the
1280×720 captures confirmed the native local actor on the rendered terrain,
the lower/right HUD rails, a populated unobscured minimap, a visible white
player marker on the minimap and Tab map, and continuous camera follow after
movement.

Sanitized runtime values:

- server map ID: `four_gates`;
- local actor ID: `120`;
- authoritative spawn tile: `(768,480)`;
- converted/final actor position: `(178.8372,34.14781,-44.88372)`;
- navigation hit: `(178.8372,34.12781,-44.88372)` on
  `Terrain_City_Plateau_WalkSurfaceCollision`;
- native model: three visible meshes, native glTF hierarchy retained, no
  development fallback;
- camera: pitch `-60` degrees, distance `26`, FOV `50`, actor projected height
  `28.0842` pixels;
- MOVE_TO redacted-safe bytes: `01 05 00 05 03 e1 01`, target tile `(773,481)`;
- authoritative result: local actor reached `(773,481)`, faced movement at yaw
  `-0.785398`, and remained the camera focus.

The job is commit-message opt-in (`[rendered-integration]`) because every run
creates a disposable server character. Ordinary pull-request updates only run
the deterministic headless suite.

### Verified camera-state evidence: workflow run 33068947381

Commit `2ee71b536e525120cb1237334ce390c721cbbd8a` passed both the
headless protocol job and the opt-in real-server rendered job. Artifact
`9645038330` adds human-inspected rotated, panned, and zoomed 1280×720 frames
plus sanitized `camera-states.json`:

- rotation: yaw `0 -> -30` degrees and pitch `-60 -> -56` degrees;
- intentional pan: `(0,0,0) -> (5.799599,0,1.186798)`;
- zoom: distance `26 -> 18.5`;
- the native actor remained inside the gameplay camera in every state;
- restoring the default camera reset pan, re-established actor focus, and the
  subsequent real MOVE_TO still reconciled `(768,480) -> (773,481)` with actor
  yaw `-0.785398`.

All camera-state PNGs were visually inspected. Rotation, pan, zoom, the HUD,
the populated minimap, and the white minimap marker rendered in every frame;
the zoomed frame made the native actor substantially easier to read.

### Verified sit/stand evidence: workflow run 33069841631

Commit `f677c789fa05f51ae8f25657c5e7872b5cee5724` passed both jobs.
Artifact `9645336657` records local actor ID `122` and contains visually
inspected seated and standing-after-move frames. The real server accepted
desired-state packets `07 02 00 01` (sit) and `07 02 00 00` (stand), then
broadcast commands 13 and 14 through the normal actor reducer.

The native animation now progresses from `Sitting_Enter` to the explicit
`seated_idle` action and from `Sitting_Exit` back to `idle`. A second sit
followed by MOVE_TO proved server-driven automatic standing: the actor moved
from `(773,481)` to `(774,481)`, finished in `walk`, and did not retain a stale
seated pose. Credentials remained `REDACTED` in every artifact file.

### Verified remote-player evidence: workflow run 33073030852

Commit `7b5b6b1bbfa376d879d4966a1286c7882edde5ce` passed the strict
headless job and the opt-in rendered development-server job. Artifact
`9646673225` contains the sanitized remote actor diagnostics and the visually
inspected 1280×720 selected-player frame.

The helper connection created and logged in a second disposable character with
credentials retained only in memory. The primary client received remote actor
ID `124` as enhanced player kind `1`, preserved the native luminous glTF model
with three visible native meshes and no missing-model fallback, applied the
authoritative movement from `(767,479)` to `(763,479)`, and selected the remote
collision capsule through the gameplay camera ray. The selected actor's gold
ring and both native players are visible on the authored terrain in the capture.
Closing the helper connection removed actor `124` from both authoritative state
and the rendered actor-node map.

The same real-server actor snapshot contained no kind-`2` NPCs in the Four
Gates visibility set. This is recorded as a development-server/map population
limitation; it is not treated as evidence that rendered NPC activation or live
dialogue works.

### Verified bidirectional chat evidence: workflow run 33076142698

Commit `0f2798b127d269adac081c590bdd6d4d59862d29` passed the strict
headless job and the opt-in rendered development-server job. Artifact
`9647992715` records two distinct channel-`0` messages delivered through the
real server: the primary client submitted its marker through the normal chat UI
and the helper received it, then the helper sent its marker and the primary
reducer/UI received it.

Human inspection of `world-chat.png` confirmed that both sender-prefixed lines
and the chat entry are readable in the lower-left area, fully above the opaque
lower HUD rail. The first rendered attempt exposed the overlap and was not
accepted as visual evidence; the final layout reserves separate anchored bands
for history, entry, and the lower action rail. `chat.json` and the session log
contain `credentials: REDACTED`.

### Verified inventory, statistics, and equipment evidence: workflow run 33082783309

Commit `d9a8932415a8087f17c8171f44e3645d4d589f44` passed the strict
headless job and the opt-in rendered development-server job. Artifact
`9650864916` contains sanitized `inventory-stats.json` and `equipment.json`
plus human-inspected 1280x720 inventory, statistics, and equipped-fallback
captures.

The authoritative fresh-character snapshot contained three backpack entries
at slots 0 through 2 with image IDs `114`, `397`, and `460`, each at quantity
one. Real item-inspection responses identified them as Four Gates Guard Spear,
Guard Shield, and Guard Cape respectively, and each alias is pinned to matching
independent weapon, shield, or cloak artwork. All three inventory buttons and
all three corresponding item quick slots held visible icons and quantities.
The independent asset pack does not bundle the complete legacy Eternal Lands
item atlas range, so the registry resolves
those observed IDs through explicit data-driven Eloria substitutes and uses a
disclosed generic Eloria fallback for other unbundled IDs; tooltips retain the
authoritative legacy image ID instead of pretending the substitute is exact.

The server supplied health `20/20`, ether `32/32`, food `45`, carried/capacity
`20/80`, all six base attributes at `4`, and the complete skill snapshot. The
resource rail and statistics window presented those values. Human inspection
confirmed the inventory window fits above the lower HUD, the item and spell
quickbars remain readable, and the shifted statistics window no longer covers
the fixed resource rail. All six configured spell slots exposed availability
state. The fresh character had zero equipped items, so this run is not evidence
for a native equipment model. Artifact credentials remain `REDACTED`.

The same run selected the guard spear through the inventory UI and sent
`MOVE_INVENTORY_ITEM(20)` as `source_slot:u8 | destination_slot:u8`, moving
slot `0` to generic wear slot `36`. The server returned the authoritative
inventory/statistics snapshots and broadcast weapon part `0`, visual `112`.
The local luminous actor retained its native skeleton and created one visible
development fallback on the configured right-hand attachment. Human inspection
of `world-equipment-fallback.png` confirmed the bright fallback is visible on
the zoomed actor. Reversing the UI action moved slot `36` back to `0`, consumed
the server unwear update, removed the fallback node, and restored all three
backpack items. `equipment.json` records native count `0` and fallback count
`1 -> 0`; `data/actors/equipment.json` still contains no native GLB model
mappings, so this is explicit fallback evidence rather than native equipment
completion.

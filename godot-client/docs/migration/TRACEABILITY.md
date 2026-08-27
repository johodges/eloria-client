# Migration traceability matrix

Status: NOT_STARTED, FOUNDATION, IMPLEMENTED, VERIFIED, BLOCKED.

| Legacy feature | Source | Godot target | Test/evidence | Status |
|---|---|---|---|---|
| TCP framing | client connection; server protocol.py | network/protocol.gd | byte fixtures + fragmented/combined reads | FOUNDATION |
| Configurable endpoint | servers.c | responsive login scene/config | rendered CI connected to `18.235.240.60:2000` through the real login/creation UI | VERIFIED |
| Login | loginwin.c; LOG_IN | auth/network | disposable character creation and subsequent login against the development server; credentials redacted | VERIFIED |
| Actor spawn/update/remove | multiplayer.c; server actor packets/commands | state/actors | actor packet + command-step fixtures | IMPLEMENTED |
| NPC activation/dialogue | gamewin.c; server protocol/world | protocol/state/dialogue UI | byte + decode fixtures; runtime pending | IMPLEMENTED |
| Chat send/receive + PM | legacy `text.c`, `chat.c`, `pm_log.c`; server `protocol.py`, `server.py`, `world.py` | exact RAW_TEXT/SEND_PM codecs, channel state, safe lower-left presentation | exact bytes and channel/color/UTF-8 fixtures; two-client local TCP delivery, sender acknowledgement, reply-last, and offline-recipient rejection | IMPLEMENTED |
| Title/login artwork | generated Eloria branding DDS | portable PNG copies + responsive themed login/creation | 1280x720 bounds fixture covers login and creation action rows; user screenshot comparison | IMPLEMENTED |
| GLB map + JSON | GLB runtime/map.c | world/map loader | `four_gates` alias fixture, headless attach, and rendered development-server Four Gates capture | VERIFIED |
| Native luminous models | actor GLB runtime/assets | actor presentation | rendered female luminous GLB with three visible native meshes and no fallback | VERIFIED |
| Movement reconciliation | client movement/server authority | controller/state | rendered real-server MOVE_TO changed authoritative tile `(768,480)` to `(773,481)`; actor yaw and camera followed | VERIFIED |
| Core HUD/chat | `hud.c`, `hud_misc_window.c`, `gamebuttons*.dds` | ui/hud | lower action/window rail; right stats and item/spell quickbar; unsupported windows visibly disabled | IMPLEMENTED |
| Inventory/equipment | `items.c`, `items.h`, `hud_quickbar_window.c`; server `protocol.py`, `world.py`, `items.py` | protocol/state/inventory/equipment UI and actor presentation | exact snapshot/update/remove/use/move/cooldown/wear fixtures; two-click backpack/wear placement; local TCP count-0 snapshot; native item atlases visually inspected; populated live render pending | IMPLEMENTED |
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
- the white player marker follows the actor and both map cameras include its layer;
- a left-click routed through the gameplay viewport produces a server actor-tile update;
- each 1280×720 capture contains rendered color variation rather than a dummy frame.

The artifact contains default-world, full-map, and post-movement PNGs plus sanitized session and movement JSON. A passing structural assertion is still classified separately from human visual inspection of those PNGs.

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

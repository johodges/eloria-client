# Migration traceability matrix

Status: NOT_STARTED, FOUNDATION, IMPLEMENTED, VERIFIED, BLOCKED.

| Legacy feature | Source | Godot target | Test/evidence | Status |
|---|---|---|---|---|
| TCP framing | client connection; server protocol.py | network/protocol.gd | byte fixtures + fragmented/combined reads | FOUNDATION |
| Configurable endpoint | servers.c | responsive login scene/config | 18.235.240.60:2000 default; socket test blocked by executor network policy | IMPLEMENTED |
| Login | loginwin.c; LOG_IN | auth/network | real server capture | FOUNDATION |
| Actor spawn/update/remove | multiplayer.c; server actor packets/commands | state/actors | actor packet + command-step fixtures | IMPLEMENTED |
| NPC activation/dialogue | gamewin.c; server protocol/world | protocol/state/dialogue UI | byte + decode fixtures; runtime pending | IMPLEMENTED |
| Chat send/receive | chat.c; server RAW_TEXT | protocol/state/chat UI | byte + decode fixtures; runtime pending | IMPLEMENTED |
| Title/login artwork | generated Eloria branding DDS | portable PNG copies + responsive themed login/creation | 1280x720 bounds fixture covers login and creation action rows; user screenshot comparison | IMPLEMENTED |
| GLB map + JSON | GLB runtime/map.c | world/map loader | `four_gates` production alias fixture; headless GLB scene attach; visual recheck pending | IMPLEMENTED |
| Native luminous models | actor GLB runtime/assets | actor presentation | byte/source validation; render pending | FOUNDATION |
| Movement reconciliation | client movement/server authority | controller/state | real MOVE_TO wiring; server X/Z plus navigation-sampled presentation Y; live verification pending | FOUNDATION |
| Core HUD/chat | `hud.c`, `hud_misc_window.c`, `gamebuttons*.dds` | ui/hud | lower action/window rail; right stats and item/spell quickbar; unsupported windows visibly disabled | IMPLEMENTED |
| Inventory/equipment | `items.c`, `items.h`, `hud_quickbar_window.c`; server `protocol.py`, `world.py`, `items.py` | protocol/state/inventory/equipment UI and actor presentation | exact snapshot/update/remove/use/move/cooldown/wear fixtures; local TCP count-0 snapshot; native item atlases visually inspected; populated live render pending | IMPLEMENTED |
| Combat | actor commands/combat HUD | gameplay/ui | server combat trace | NOT_STARTED |
| NPC/storage/trade | respective modules | reducers/windows | packet and integration tests | NOT_STARTED |
| Magic/crafting/harvest | respective modules | reducers/windows | action/result traces | NOT_STARTED |
| Hotkeys/settings | keys.c/elconfig.c | InputMap/settings | viewport routing fixture verifies rotate/pan/zoom; live click-to-move recheck pending | FOUNDATION |

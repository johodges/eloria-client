# Migration traceability matrix

Status: NOT_STARTED, FOUNDATION, IMPLEMENTED, VERIFIED, BLOCKED.

| Legacy feature | Source | Godot target | Test/evidence | Status |
|---|---|---|---|---|
| TCP framing | client connection; server protocol.py | network/protocol.gd | byte fixtures + fragmented/combined reads | FOUNDATION |
| Configurable endpoint | servers.c | login scene/config | manual dev connection | FOUNDATION |
| Login | loginwin.c; LOG_IN | auth/network | real server capture | FOUNDATION |
| Actor spawn/update/remove | multiplayer.c; protocol.py | state/actors | actor packet fixtures | FOUNDATION |
| GLB map + JSON | GLB runtime/map.c | world/map loader | schema + loader; runtime pending | FOUNDATION |
| Native luminous models | actor GLB runtime/assets | actor presentation | byte/source validation; render pending | FOUNDATION |
| Movement reconciliation | client movement/server authority | controller/state | dual-client comparison | NOT_STARTED |
| Core HUD/chat | hud/interface/chat | ui/hud | chat reducer fixture; HUD pending | FOUNDATION |
| Inventory/equipment | items.c | state/ui | mutation fixtures | NOT_STARTED |
| Combat | actor commands/combat HUD | gameplay/ui | server combat trace | NOT_STARTED |
| NPC/storage/trade | respective modules | reducers/windows | packet and integration tests | NOT_STARTED |
| Magic/crafting/harvest | respective modules | reducers/windows | action/result traces | NOT_STARTED |
| Hotkeys/settings | keys.c/elconfig.c | InputMap/settings | conflict/persistence tests | NOT_STARTED |

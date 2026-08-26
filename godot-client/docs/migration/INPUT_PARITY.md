# Input parity baseline

The complete legacy `keys.c` audit is in progress. Names below are stable Godot actions; exact defaults must be copied only after resolving platform conditionals.

| Legacy behavior | Context | Godot action | Rebindable |
|---|---|---|---|
| Ground click / move | world | world_move | yes |
| Run modifier / run-to | world | world_run | yes |
| Rotate camera | world | camera_rotate | yes |
| Zoom | world | camera_zoom_in/out | yes |
| Select / context action | world | select / interact | yes |
| Attack | world | attack | yes |
| Focus chat / submit | HUD | chat_focus / chat_submit | yes |
| Full map | HUD | toggle_map | yes |
| Inventory | HUD | toggle_inventory | yes |
| Magic | HUD | toggle_magic | yes |
| Manufacture | HUD | toggle_manufacture | yes |
| Escape / cancel | global | cancel | yes |
| Sit / stand (Alt+S) | world | toggle_sit | yes |
| Screenshot | global | screenshot | yes |
| Fullscreen | global | toggle_fullscreen | yes |

World input must be suppressed when a Control consumes the pointer event. Debug bindings exist only in development builds.

## Implemented gameplay shell controls

| Gesture | Result |
|---|---|
| Left click on world | Convert Godot ground point to server tile and send MOVE_TO |
| Shift + left click | Send RUN_TO |
| Right-button drag | Orbit yaw and pitch |
| Middle-button drag | Pan focus offset |
| Mouse wheel | Zoom with configured limits |
| Tab | Toggle full map using the minimap render |
| Alt+S | Send the authoritative desired sit/stand state |
| T / Enter | Focus chat; Enter submits RAW_TEXT |
| Click NPC | Select actor and send TOUCH_PLAYER |

All world gestures are handled only after Control nodes decline the event, preventing HUD click-through.

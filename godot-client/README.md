# Eloria Godot Client

Production migration foundation for the legacy Eloria client, compatible with the existing server.

## Engine and language

- Godot **4.7.2-stable** (pinned; do not use 4.8 development snapshots).
- Typed GDScript is the primary language. It keeps deployment simple while allowing native Godot scenes and resources.
- Rendering starts with Compatibility mode to maximize Windows/Linux coverage; Forward+ will be profiled before becoming the default.

## Run

Windows: install Godot 4.7.2, open `godot-client/project.godot`, and press F6/F5.

Linux:

```sh
godot --editor --path godot-client
godot --path godot-client
```

The initial screen connects over real TCP and sends the server's real `LOG_IN` frame. Use a development server only.

## Default controls

- `W`/`S`: move forward/backward relative to facing. `A`/`D`: strafe without turning; combine keys for diagonal movement and hold Shift to run.
- `Q`/`E`: turn the local character. `Space`: recenter the viewport on your character.
- `Ctrl+I`: toggle inventory. Drag its title bar to move it and its lower-right grip to scale the whole window proportionally. Right-click Sto All or Drop All to protect individual edge rows/columns; Get All opens and empties the ground bag on your tile subject to server slot/load validation.
- `Tab`: toggle the full map. `Alt+M`: toggle the minimap; drag its thick compass border and right-click it for north-up, player-up, or viewport-up orientation.
- `T`: focus chat; `Esc`: dismiss it. Backtick/tilde toggles full chat history.
- `Alt+A`: attack the selected target. `Alt+S`: sit or stand.
- The Eternal Lands window keys: `Ctrl+S` spells, `Ctrl+M` manufacture, `Ctrl+J` emotes, `Ctrl+G` quest journal, `Ctrl+B` buddies, `Ctrl+A` stats, `Ctrl+T` ranging, `Ctrl+H` help, `Ctrl+N` notepad, `Ctrl+O` options, `Ctrl+L` mail, `Ctrl+E` encyclopedia. All rebindable in Settings → Controls.
- Every window moves by its title bar, and stays inside the viewport and clear of the right rail. The inventory and ground bag also scale from their lower-right grip and remember where they were left.
- A HUD icon is drawn in colour whenever its action is available and greyed only when it is not; an open window is marked by the lit frame around its icon. The sit icon becomes the stand icon while you are seated.
- The right rail carries the legacy misc-window column: skill rows (click one to watch it on the experience bar), the countdown/stopwatch timer (click to start/stop, Shift+click for stopwatch, wheel to set), the knowledge bar, the digital and analog clocks, and the compass. The settings window's HUD tab shows or hides each, plus the FPS readout and the S H P M R G A indicator letters.

## Test

```sh
godot --headless --path godot-client --script res://tests/test_protocol.gd
```

The protocol test includes byte fixtures for framing, movement, fragmented headers, combined packets, and invalid lengths.

## Security

Password-containing frames are marked sensitive and never printed. The protocol inspector must preserve this redaction contract.

## Status

This milestone is an executable foundation, not parity completion. See `docs/migration/` for discovery, protocol, risks, and traceability.

## Validation scenes

Open and run these scenes in Godot 4.7.2:

- `src/dev/model_validation.tscn`: switches luminous male/female, retargets the native 162-clip animation GLB, cycles mapped clips, and rotates lighting.
- `src/dev/world_validation.tscn`: loads Four Gates through the production `WorldLoader`, including manifest validation and declared collision.

A PASS label is evidence of source/runtime loading only. Record screenshots and review skeletons, materials, attachments, navigation, and coordinate placement before changing traceability to VERIFIED.

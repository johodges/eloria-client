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

- `W`, `A`, `S`, `D`: walk while a text entry is not active; hold Shift to run.
- `Q` / `E`: turn the local character left or right.
- `Ctrl+I`: toggle inventory; right-click Sto All or Drop All to protect individual edge rows/columns.
- `Tab`: toggle the full map. `Alt+M`: toggle the minimap; drag its compass border and right-click it for north-up/player-up orientation.
- `T`: focus chat; `Esc`: dismiss it. Backtick/tilde toggles full chat history.
- `Alt+A`: attack the selected target. `Alt+S`: sit or stand.

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

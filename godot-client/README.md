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

## Test

```sh
godot --headless --path godot-client --script res://tests/test_protocol.gd
```

The protocol test includes byte fixtures for framing, movement, fragmented headers, combined packets, and invalid lengths.

## Security

Password-containing frames are marked sensitive and never printed. The protocol inspector must preserve this redaction contract.

## Status

This milestone is an executable foundation, not parity completion. See `docs/migration/` for discovery, protocol, risks, and traceability.

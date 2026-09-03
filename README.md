# Eloria Client

The Godot 4.7 client for Eloria, and the asset sources it is built from.

Eloria began as a fork of the Eternal Lands C client. That client, and every
Eternal Lands file format and data pack it loaded, were removed on 2026-09-03;
see [ELORIA_MODIFICATIONS.md](ELORIA_MODIFICATIONS.md) for the full record and
`eternal_lands_license.txt` for the licence the fork was published under. Eloria
is not affiliated with or endorsed by Eternal Lands.

## Layout

| path              | what it is                                                        |
|-------------------|-------------------------------------------------------------------|
| `godot-client/`   | the client. A Godot 4.7 project; open it with the project root at `godot-client`. |
| `eloria-assets/`  | asset sources: map packages, concept art, QA renders, and the tools that build them. |
| `tools/`          | shared build tools that are not part of either tree.               |
| `tests/`          | Python contracts over the shared assets. `python3 -m pytest tests`. |
| `docs/`           | audits and format notes.                                          |

The client reads a few asset sources in place through `res://../eloria-assets/`,
so the two directories are checked out together and move together.

## Running

```bash
godot --path godot-client
```

The client needs `eloria-server` on TCP 2000. Point it at one with the login
screen's server field, or `--server`.

## Tests

```bash
python3 -m pytest tests
python3 eloria-assets/tools/check_provenance.py
godot --headless --path godot-client --script res://tests/test_protocol.gd
```

`check_provenance.py` fails if an Eternal Lands map name or engine file format
(`.elm`, `.e3d`, Cal3D, `.dds`, `.bmp`) appears anywhere in the tree. The
`Godot Client` workflow runs the full suite, including the headless render
checks, on every pull request.

## Maps

A map is a GLB scene, a `world.json` manifest and a `collision.bin` walk grid
under `eloria-assets/maps/`. `godot-client/data/maps/registry.json` binds each
**Eloria map id** — `four_gates`, `westhaven` — to its manifest and to the
coordinate transform that puts the server's tiles on the authored geometry.

eloria-server sends that id. It used to send the path of an Eternal Lands map
file instead; `MapRegistry.normalize_server_map_id` still reduces a path-shaped
name to its id, as tolerance for an older server rather than as a contract.
`tests/test_protocol.gd` holds every registry key to a bare id, and the server
holds the other half in its `tests/test_client_content_sync.py`.

Server walk grids for the composed interior maps live in
`eloria-assets/maps/nymara-regions/server-collision/`; see that directory's
README for the format and for how eloria-server reads them.

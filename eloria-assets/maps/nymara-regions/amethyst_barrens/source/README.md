# Amethyst Barrens source

Three region-specific modules plus one build script. Everything else is imported
from the shared toolkit at `../../_toolkit/`, which is not copied here.

| File | What it owns |
| --- | --- |
| `region.py` | extent, scale, anchors, routes, watercourses, terrain sculpting, surface painting |
| `populate.py` | the landmark kit and every placement pass |
| `views.py` | the camera set, the panel mapping, and this region's capture lighting |
| `build_amethyst.py` | the build: GLB, manifest, collision, minimap, validation |

## Build

```bash
python build_amethyst.py                 # full package
python build_amethyst.py --skip-lod2 --skip-minimap   # fast iteration
```

Deterministic: two independent processes produce byte-identical `world.glb`,
`world.json`, `collision.bin` and `minimap.webp`.

Runtime startup never depends on running this. The package is the committed
artefacts.

## Then

```bash
cd ..
PYTHONPATH=../_toolkit python ../_toolkit/validate_gltf.py world.glb
PYTHONPATH=../_toolkit python ../_toolkit/verify_runtime.py --report verification-report.json
PYTHONPATH=../_toolkit python ../_toolkit/capture_views.py
PYTHONPATH=../_toolkit python ../_toolkit/make_comparison.py
PYTHONPATH=../_toolkit python ../_toolkit/export_server_collision.py --out ../server-collision/amethyst_barrens.bin
```

## Real client frames

`references/captures/` is the offline rasteriser and is *not* the client.
For engine frames, from a Godot 4.7.2 binary:

```bash
godot --path ../../../../godot-client --headless --import   # once, or class_name lookups fail
godot --path ../../../../godot-client       --script ../../_toolkit/godot_capture.gd --resolution 1280x800 --       --package=<abs path to this package> --out=<abs path to client-captures>
```

The harness loads `world.json` through the client's own
`WorldLoader.load_world()` and takes its camera set from
`references/captures/index.json`, so the client frames line up one-for-one with
the offline previews they are compared against. Run `capture_views.py` first.

## Material set

`build_amethyst.py` pins `MATERIALS` and passes `only=` when registering glTF
materials, so this package embeds the 13 materials it uses rather than all 56
in the shared table. Adding a kit piece that introduces a new material means
adding its name there; an unpinned material is a `KeyError` at export rather
than a silent omission.

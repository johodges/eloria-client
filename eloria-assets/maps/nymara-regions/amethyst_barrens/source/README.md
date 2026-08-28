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
PYTHONPATH=../_toolkit python ../_toolkit/export_source_elm.py --out ../source-elm/amethyst_barrens.elm
```

## Real client frames

`references/captures/` is the offline rasteriser and is *not* the client.
For engine frames, from a Godot 4.7.2 binary:

```bash
godot --path ../../../../godot-client --headless --import     # once, or class_name lookups fail
godot --path ../../../../godot-client --script ../../_toolkit/godot_capture.gd \
      -- <abs path to world.json> <abs out dir> <abs shots.json>
```

`shots.json` is a list of `{id, eye, target, fov, width, height}` in absolute
metres. The caller resolves ground-relative camera heights, because it has the
terrain and the harness does not.

## Material set

`build_amethyst.py` pins `MATERIALS` and passes `only=` when registering glTF
materials, so this package embeds the 13 materials it uses rather than all 46
in the shared table. Adding a kit piece that introduces a new material means
adding its name there; an unpinned material is a `KeyError` at export rather
than a silent omission.

# Amethyst Barrens source

Region-specific authoring and review modules. Shared primitives are imported
from the shared toolkit at `../../_toolkit/`, which is not copied here.

| File | What it owns |
| --- | --- |
| `region.py` | extent, scale, anchors, routes, watercourses, terrain sculpting, surface painting |
| `populate.py` | the landmark kit and every placement pass |
| `views.py` | the camera set, the panel mapping, and this region's capture lighting |
| `build_amethyst.py` | the build: GLB, manifest, collision, minimap, validation |
| `landscape_plan.py` | 384m survey, inhabited outpost, road grading, ecological placement and reciprocal borders |
| `rebuild_landscape.py` | sequential exterior build, geometry height correction, open decks and solid footprints |
| `migrate_compact_server.py` | revision-guarded server coordinate migration; preview by default |
| `review_landscape.py` | stable IDs, retained node references and conservative portal tile checks |
| `review_border_lanes.py` | all seven trigger/arrival lanes and 40m approaches in final client and served collision |
| `write_walk_fixture.py` | short service, resource, habitat and all-door routes for the real server walker |
| `write_review.py` | annotated raw gameplay-camera comparison and geometry-derived overview |

## Build

```bash
python rebuild_landscape.py --verify     # complete corrected package
python build_amethyst.py --skip-lod2 --skip-minimap   # fast iteration
```

The seeded build also reads shared reciprocal border definitions and receiving
sources; keep their revision fixed to reproduce the published package.

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

The current inhabited landscape's raw before/after frames and precise camera
specifications are under `work-output/northern-rollout/amethyst_barrens`.
Use `godot-client/tests/integration/rendered_landscape_survey.gd` for the complete
gameplay-camera rig, traveller and HUD. The integrated server walker consumes
the generated `walk-routes.json`. The older capture workflow below remains
available for concept review.

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
materials, so this package embeds its selected palette and the reciprocal border
materials. Adding a kit piece that introduces a new material means
adding its name there; an unpinned material is a `KeyError` at export rather
than a silent omission.

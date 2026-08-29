#!/usr/bin/env python3
"""Capture the Amberwood comparison views from the finished geometry.

The camera list mirrors the ten close-up reference panels plus the aerial
overview, every remaining checklist landmark, the movement and collision test
locations, and a golden-hour pass.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import preview
from amberwood import render as RENDER

import regionpaths

HERE = Path(__file__).resolve().parent
PACKAGE = regionpaths.package_root()
CAPTURES = PACKAGE / "references" / "captures"
_REGION_VIEWS = regionpaths.load_region_views(PACKAGE)
VIEWS = _REGION_VIEWS.VIEWS
# The plan and the build script belong to the region, not to the toolkit.
REG = regionpaths.load_region_plan(PACKAGE)
_REGION_BUILD = regionpaths.load_region_build(PACKAGE)
build_region = _REGION_BUILD.build_region


def _resolved_views() -> dict:
    """The build's own resolved camera table, keyed by view id.

    `views.py` is written in design space with ground-relative heights, and two
    different pieces of code turned that into world space: this script, and the
    region build's `write_camera_views`. They did not agree. The build resolves
    a `deck` camera by snapping it to the walk surface under it, which is the
    only way to stand on a bridge or a quay; this script only ever knew about
    ground-relative heights and additionally nudged every eye below 20 m up to
    33 m sideways looking for standing room.

    The consequence was silent and bad: a region could author a camera on a
    walkway, see it resolved correctly into `camera-views.json`, and still get
    captures shot from somewhere else entirely - and because `godot_capture.gd`
    reads *this* script's index, the real client frames inherited the wrong
    framing too. Manymouth's macro camera was authored 2 m from its subject and
    photographed the village rooftops 30 m away.

    So the build's table wins where it exists. One resolution, three consumers.
    """
    path = PACKAGE / "camera-views.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    return {str(v.get("id", "")): v for v in data.get("views", [])}


def _region_texture_sets():
    """The shared texture table, extended with the region's own recipes.

    A region that adds materials registers them at build time by appending to
    `materials.SPECS` in memory - the pattern Crownwater established so that
    concurrent region work does not have to edit the shared table. That
    registration happens inside the region's `main()`, which this script never
    calls, so without a hook every region-specific material resolves to index 0
    (`bark_oak`) in the preview renderer and the captures silently show the
    wrong surface everywhere.

    Manymouth found this the obvious way: its water, decking, silt, sand and
    paddy all came back as bark, so a delta rendered as a dry sand flat with no
    water in it at all. A region opts in by exposing
    `register_materials(sets) -> sets` from its build module.
    """
    sets = preview.texture_sets()
    hook = getattr(_REGION_BUILD, "register_materials", None)
    if hook is not None:
        sets = hook(sets)
    return sets

# A region may override the capture lighting from its own `views.py`. The
# presets below are Amberwood's warm afternoon sun, which is wrong for a region
# under permanent storm - and the captures are the only visual evidence a
# reviewer has. Two spellings are accepted, a single LIGHTING dict or a pair of
# DAY_LIGHTING / GOLDEN_LIGHTING constants, because both are in use.
REGION_LIGHTING = dict(getattr(_REGION_VIEWS, "LIGHTING", {}) or {})
if getattr(_REGION_VIEWS, "DAY_LIGHTING", None) is not None:
    REGION_LIGHTING.setdefault("day", _REGION_VIEWS.DAY_LIGHTING)
if getattr(_REGION_VIEWS, "GOLDEN_LIGHTING", None) is not None:
    REGION_LIGHTING.setdefault("golden", _REGION_VIEWS.GOLDEN_LIGHTING)

DAY = RENDER.Lighting(sun_direction=(-0.46, 0.50, 0.73),
                      sun_color=(1.22, 0.94, 0.60),
                      sky_color=(0.22, 0.30, 0.42),
                      ground_color=(0.08, 0.06, 0.04),
                      fog_color=(0.38, 0.37, 0.35),
                      fog_density=0.00070, fog_height_falloff=0.0030,
                      ambient_strength=0.30, shadow_strength=0.90,
                      exposure=1.15, saturation=1.30,
                      sky_zenith=(0.15, 0.25, 0.42), sky_horizon=(0.58, 0.56, 0.50))

GOLDEN = RENDER.Lighting(sun_direction=(-0.86, 0.19, 0.47),
                         sun_color=(1.55, 0.90, 0.44),
                         sky_color=(0.30, 0.26, 0.26),
                         ground_color=(0.10, 0.07, 0.04),
                         fog_color=(0.55, 0.42, 0.29),
                         fog_density=0.0021, fog_height_falloff=0.0045,
                         ambient_strength=0.34, shadow_strength=0.88,
                         exposure=1.10, saturation=1.32,
                         sky_zenith=(0.20, 0.24, 0.40), sky_horizon=(0.86, 0.60, 0.34))

# Per-region lighting. The presets above are tuned for Amberwood's warm autumn
# forest; a snow region under that sun renders brown. A region may override any
# Lighting field by declaring DAY_LIGHTING / GOLDEN_LIGHTING dicts in its
# views.py. Regions that declare neither keep the presets exactly as they were.
_VIEWS_MODULE = regionpaths.load_region_views(PACKAGE)
_day_overrides = getattr(_VIEWS_MODULE, "DAY_LIGHTING", None)
if _day_overrides:
    DAY = RENDER.Lighting(**{**vars(DAY), **_day_overrides})
_golden_overrides = getattr(_VIEWS_MODULE, "GOLDEN_LIGHTING", None)
if _golden_overrides:
    GOLDEN = RENDER.Lighting(**{**vars(GOLDEN), **_golden_overrides})

# Each view is (id, panel, (eye_x, eye_z), eye_height_above_ground,
#               (target_x, target_z), target_height_above_ground,
#               fov, (width, height), shadow_radius, lighting)
# Heights are relative to the terrain so every camera sits where a player's eye
# would, and no camera can end up underground when the terrain is re-sculpted.


def _free_camera(scene, terrain, eye, target, fov, minimum=None):
    """Place the camera where the shot is actually open.

    A camera that ends up inside a trunk, under an eave or walled in by canopy
    makes a useless comparison shot, and hand-tuning thirty of them by eye is how
    those mistakes get shipped. This renders a small depth-only frame for a set
    of candidate positions and keeps the one where most of the frame sits at, or
    beyond, the intended subject distance.
    """
    import numpy as np
    eye = np.asarray(eye, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    axis = eye - target
    distance = float(np.linalg.norm(axis))
    if distance < 1e-6:
        return tuple(eye)
    axis = axis / distance
    side = np.cross(axis, np.array([0.0, 1.0, 0.0]))
    if np.linalg.norm(side) < 1e-6:
        side = np.array([1.0, 0.0, 0.0])
    side = side / np.linalg.norm(side)
    threshold = minimum if minimum is not None else distance * 0.55

    def score(candidate):
        probe = scene.probe(tuple(candidate), tuple(target), fov)
        depth = probe.get("depth")
        if depth is None:
            return 3.0
        frame = depth.reshape(56, 80)
        open_fraction = float(((depth > threshold) | (depth > 1e28)).mean())
        # the middle of the frame is where the subject is: if something is in
        # front of it the shot is of the wrong thing, however open the rest is
        centre = frame[22:34, 30:50]
        reach = float(np.median(centre))
        distance_now = float(np.linalg.norm(np.asarray(candidate) - target))
        sight = 1.0 if reach > distance_now * 0.72 else 0.0
        return sight * 2.0 + open_fraction - probe["near_fraction"] * 0.6

    best = (-1.0, tuple(eye))
    scale = REG.SCALE
    for back in (0.0, 2.0 * scale, 4.0 * scale, 7.0 * scale, 10.0 * scale,
                 14.0 * scale, 19.0 * scale):
        for lateral in (0.0, -3.0 * scale, 3.0 * scale, -6.0 * scale, 6.0 * scale,
                        -9.0 * scale, 9.0 * scale):
            for lift in (0.0, 1.5, 3.5, 6.0, 9.0, 13.0):
                candidate = eye + axis * back + side * lateral \
                    + np.array([0.0, lift, 0.0])
                floor = float(terrain.height_at(candidate[0], candidate[2]))
                if candidate[1] < floor + 1.2:
                    candidate[1] = floor + 1.7
                value = score(candidate)
                if value > best[0]:
                    best = (value, tuple(candidate))
                if value > 2.80:
                    return tuple(candidate)
    return best[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", default=None)
    parser.add_argument("--out", default=str(CAPTURES))
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    sets = _region_texture_sets()
    RESOLVED = _resolved_views()
    if RESOLVED:
        print(f"[views] using the build's resolved camera table "
              f"({len(RESOLVED)} views) from camera-views.json")
    build = build_region()
    scene = preview.scene_from_build(build, sets)
    print(f"[scene] {scene.triangle_count()} triangles")

    terrain = build.terrain

    # Occupancy of everything solid, so a camera is never placed inside a trunk,
    # a wall or a prop. Radii are the instance's own footprint.
    import numpy as np
    solid_xz = []
    solid_r = []
    for placement in build.placements:
        if placement.kind in ("undergrowth", "leafdrift", "mushrooms", "foliage"):
            continue
        item = build.meshes[placement.mesh]
        low, high = item.bounds()
        footprint = float(max(abs(low[0]), abs(high[0]), abs(low[2]),
                              abs(high[2]))) * placement.scale
        factor = 0.22 if placement.kind == "tree" else 0.85
        solid_xz.append((placement.position[0], placement.position[2]))
        solid_r.append(min(max(footprint * factor, 0.35), 14.0))
    solid_xz = np.asarray(solid_xz) if solid_xz else np.zeros((0, 2))
    solid_r = np.asarray(solid_r) if len(solid_r) else np.zeros(0)

    def clearance(x, z):
        if solid_xz.shape[0] == 0:
            return 99.0
        d = np.hypot(solid_xz[:, 0] - x, solid_xz[:, 1] - z) - solid_r
        return float(d.min())

    def find_clear(xz, minimum=1.6, reach=11.0):
        minimum = minimum * REG.SCALE
        """Nudge a camera to the nearest spot with real standing room."""
        best = (clearance(*xz), xz)
        if best[0] >= minimum:
            return xz
        for radius in np.arange(1.0, reach, 0.8) * REG.SCALE:
            for k in range(16):
                angle = math.pi * 2.0 * k / 16
                cx = xz[0] + math.cos(angle) * radius
                cz = xz[1] + math.sin(angle) * radius
                sea_level = getattr(REG, "SEA_LEVEL", None)
                if sea_level is not None                         and terrain.height_at(cx, cz) < sea_level + 0.3:
                    continue
                value = clearance(cx, cz)
                if value > best[0]:
                    best = (value, (cx, cz))
                if value >= minimum:
                    return (cx, cz)
        return best[1]

    def ground(xz, above):
        return (float(xz[0]), float(terrain.height_at(xz[0], xz[1])) + above,
                float(xz[1]))

    # The view table is written in the original 192 m design space, the same
    # space the region plan uses, so it scales with the region.
    scale = REG.SCALE

    index = []
    for (name, panel, eye_xz, eye_h, target_xz, target_h, fov, size,
         radius, mode) in VIEWS:
        if args.only and not any(token in name for token in args.only):
            continue
        eye_xz = (eye_xz[0] * scale, eye_xz[1] * scale)
        target_xz = (target_xz[0] * scale, target_xz[1] * scale)
        radius = radius * scale
        if eye_h > 40.0:
            eye_h = eye_h * scale
        t0 = time.time()
        lighting = REGION_LIGHTING.get(mode, GOLDEN if mode == "golden" else DAY)
        if panel == "aerial":
            # a 576 m region seen from 500 m up is far enough away that the
            # normal ground-level haze would swallow the far half of it
            base = REGION_LIGHTING.get("day", DAY)
            lighting = RENDER.Lighting(**{**vars(base), "fog_density": 0.00022,
                                          "fog_height_falloff": 0.0016})
        # A trailing "!" on the mode pins the eye exactly where the region put
        # it. `find_clear` searches up to 11 design metres - 33 world metres -
        # for standing room, which is right for a wide shot placed by hand in a
        # forest and fatal for any close framing: Manymouth's macro camera was
        # authored 2 m from its subject and came back 30 m away and 15 m up,
        # looking over the rooftops of the village it was standing in. A region
        # that has chosen an exact viewpoint needs a way to say so.
        pinned = mode.endswith("!")
        if pinned:
            mode = mode[:-1]
            lighting = REGION_LIGHTING.get(mode,
                                           GOLDEN if mode == "golden" else DAY)
        resolved = RESOLVED.get(name)
        if resolved and len(resolved.get("position", [])) == 3                 and len(resolved.get("target", [])) == 3:
            eye = tuple(float(v) for v in resolved["position"])
            target = tuple(float(v) for v in resolved["target"])
        else:
            placed_eye = eye_xz if (pinned or eye_h > 20.0)                 else find_clear(eye_xz)
            eye = ground(placed_eye, eye_h)
            target = ground(target_xz, target_h)
        if abs(eye[0] - target[0]) < 0.05 and abs(eye[2] - target[2]) < 0.05:
            target = (target[0] + 0.4, target[1], target[2] + 0.4)
        if eye_h < 40.0:
            eye = _free_camera(scene, terrain, eye, target, fov)
        centre = ((eye[0] + target[0]) * 0.5, target[1], (eye[2] + target[2]) * 0.5)
        image = scene.render(eye=eye, target=target, width=size[0], height=size[1],
                             fov=fov, lighting=lighting, shadows=True,
                             shadow_size=2560 if radius > 60 else 2048,
                             shadow_center=centre, shadow_radius=radius,
                             far=1400.0)
        path = out / f"{name}.png"
        image.save(path)
        index.append({"id": name, "panel": panel, "file": path.name,
                      "eye": [round(v, 2) for v in eye],
                      "target": [round(v, 2) for v in target],
                      "fieldOfViewDegrees": fov, "lighting": mode})
        print(f"  {name:26} {time.time() - t0:5.1f}s -> {path.name}")

    # Merge rather than overwrite: with --only, writing just the rendered
    # views silently drops every other entry, and this index is what the
    # comparison sheets and the Godot capture read.
    index_path = out / "index.json"
    if index_path.exists():
        try:
            previous = json.loads(index_path.read_text())
        except (ValueError, OSError):
            previous = []
        if isinstance(previous, list):
            fresh = {entry["id"] for entry in index}
            order = [view[0] for view in VIEWS]
            merged = [e for e in previous
                      if isinstance(e, dict) and e.get("id") not in fresh]
            merged.extend(index)
            merged.sort(key=lambda e: order.index(e["id"])
                        if e.get("id") in order else len(order))
            index = merged
    index_path.write_text(json.dumps(index, indent=2) + chr(10))
    return 0


if __name__ == "__main__":
    sys.exit(main())

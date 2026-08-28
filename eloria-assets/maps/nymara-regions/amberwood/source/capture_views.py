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
from amberwood import region as REG
from build_amberwood import build_region

HERE = Path(__file__).resolve().parent
CAPTURES = HERE.parent / "references" / "captures"

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

A = REG.ANCHORS


def _v(anchor, dy=0.0, dx=0.0, dz=0.0):
    return (anchor[0] + dx, dy, anchor[1] + dz)


# Each view is (id, panel, (eye_x, eye_z), eye_height_above_ground,
#               (target_x, target_z), target_height_above_ground,
#               fov, (width, height), shadow_radius, lighting)
# Heights are relative to the terrain so every camera sits where a player's eye
# would, and no camera can end up underground when the terrain is re-sculpted.
VIEWS = [
    ("00-aerial-overview", "aerial", (-118, 168), 168.0, (52, -54), 0.0, 44,
     (1400, 900), 190, "day"),
    ("01-forest-road", 1, (2.0, -6.0), 1.7, (24.0, -22.0), 3.0, 60, (1180, 760), 46, "day"),
    ("02-moot-hall", 2, (8.0, -50.0), 4.0, (-4.0, -64.0), 8.0, 52, (1180, 900), 40, "day"),
    ("03-forest-lodge", 3, (-8.0, 18.0), 2.6, (-15.0, 7.0), 4.0, 56, (1180, 800), 28, "day"),
    ("04-hollow-tree", 4, (-16.0, -78.0), 3.0, (-26.0, -86.0), 7.0, 58, (1080, 920), 32, "day"),
    ("05-high-bridge", 5, (48.0, -52.0), 6.0, (40.0, -66.0), 7.0, 54, (1180, 780), 40, "day"),
    ("06-root-arch", 6, (-26.0, -24.0), 2.6, (-16.0, -34.0), 3.6, 55, (1080, 880), 24, "day"),
    ("07-garden-terrace", 7, (52.0, 30.0), 4.0, (52.0, 8.0), 3.6, 54, (1180, 820), 38, "day"),
    ("08-canopy-amber", 8, (29.0, -64.0), 12.2, (22.0, -70.0), 11.8, 62, (1080, 880), 24, "day"),
    ("09-high-overlook", 9, (76.0, -60.0), 6.0, (12.0, -62.0), 20.0, 50, (1400, 800), 130, "day"),
    ("10-material-study", 10, (6.4, -45.4), 1.2, (4.4, -49.0), 0.9, 40, (1080, 880), 14, "day"),
    ("11-great-arch", None, (58.0, -2.0), 7.0, (58.0, -34.0), 9.0, 48, (1280, 880), 48, "day"),
    ("12-harbour", None, (-44.0, 24.0), 9.0, (-28.0, 6.0), 2.0, 54, (1280, 780), 44, "day"),
    ("13-great-tree", None, (48.0, -76.0), 4.0, (26.0, -88.0), 16.0, 50, (1080, 920), 44, "day"),
    ("14-market", None, (-12.0, -38.0), 4.6, (4.0, -50.0), 3.0, 55, (1280, 780), 30, "day"),
    ("15-forest-gate", None, (74.0, -14.0), 2.4, (74.0, -30.0), 3.6, 54, (1080, 820), 26, "day"),
    ("16-timber-yard", None, (54.0, 48.0), 5.0, (72.0, 34.0), 2.5, 54, (1280, 780), 38, "day"),
    ("17-ash-transition", None, (84.0, -4.0), 5.0, (116.0, -18.0), 2.0, 54, (1280, 780), 70, "day"),
    ("18-watchtower", None, (72.0, -54.0), 4.0, (86.0, -70.0), 8.0, 52, (1080, 880), 38, "day"),
    ("19-coast-waterfall", None, (-34.0, -10.0), 8.0, (-17.5, -22.0), 3.0, 54,
     (1280, 780), 40, "day"),
    ("20-north-gate", None, (24.0, -90.0), 3.0, (24.0, -104.0), 6.0, 54, (1080, 820), 30, "day"),
    ("21-hill-hamlet", None, (90.0, 46.0), 5.0, (108.0, 30.0), 3.0, 54, (1280, 780), 38, "day"),
    ("22-mill-pool", None, (-18.0, -32.0), 3.4, (-2.0, -44.0), 1.5, 56, (1180, 780), 32, "day"),
    ("23-old-bridge", None, (-2.0, -36.0), 3.0, (10.0, -44.0), 4.0, 55, (1080, 820), 28, "day"),
    ("24-canopy-walkway", None, (14.0, -80.0), 13.5, (24.0, -70.0), 12.0, 58,
     (1180, 780), 36, "day"),
    ("30-spawn-grounding", None, (-10.0, 10.0), 2.4, (4.0, -6.0), 1.6, 58, (1180, 780), 32, "day"),
    ("31-arch-stair", None, (66.0, -14.0), 2.2, (58.0, -30.0), 5.0, 56, (1180, 780), 30, "day"),
    ("32-shore-walk", None, (-38.0, 18.0), 3.0, (-26.0, 6.0), 1.2, 56, (1180, 780), 34, "day"),
    ("33-ravine-edge", None, (30.0, -54.0), 3.0, (44.0, -72.0), 2.0, 56, (1180, 780), 40, "day"),
    ("25-forest-lake", None, (-6.0, -72.0), 4.0, (-15.0, -85.0), 1.0, 55,
     (1280, 780), 40, "day"),
    ("26-west-cove", None, (-30.0, -50.0), 6.0, (-42.0, -60.0), 1.0, 55,
     (1280, 780), 40, "day"),
    ("27-north-hamlet", None, (20.0, -110.0), 4.0, (30.0, -118.0), 3.0, 55,
     (1280, 780), 36, "day"),
    ("28-quarry", None, (62.0, 44.0), 5.0, (75.0, 52.0), 2.0, 55, (1280, 780), 36, "day"),
    ("29-old-battle", None, (100.0, -48.0), 4.0, (115.0, -40.0), 2.0, 55,
     (1280, 780), 44, "day"),
    ("34-ridge-bridge", None, (40.0, -94.0), 5.0, (52.0, -100.0), 6.0, 54,
     (1180, 780), 38, "day"),
    ("40-golden-settlement", None, (-18.0, -36.0), 7.0, (12.0, -60.0), 6.0, 50,
     (1400, 820), 70, "golden"),
    ("41-golden-arch", None, (30.0, -18.0), 5.0, (58.0, -34.0), 10.0, 50,
     (1400, 820), 56, "golden"),
    ("42-golden-coast", None, (-8.0, 26.0), 11.0, (-40.0, 2.0), 1.0, 52,
     (1400, 820), 70, "golden"),
]


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
    import amberwood.region as _reg
    scale = _reg.SCALE
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

    sets = preview.texture_sets()
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
                if terrain.height_at(cx, cz) < REG.SEA_LEVEL + 0.3:
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
        lighting = GOLDEN if mode == "golden" else DAY
        if panel == "aerial":
            # a 576 m region seen from 500 m up is far enough away that the
            # normal ground-level haze would swallow the far half of it
            lighting = RENDER.Lighting(**{**vars(DAY), "fog_density": 0.00022,
                                          "fog_height_falloff": 0.0016})
        placed_eye = eye_xz if eye_h > 20.0 else find_clear(eye_xz)
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

    (out / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

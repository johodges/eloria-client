#!/usr/bin/env python3
"""Bootstrap the continent-v2 island-group territories (sw_isle, tollholms, gull_skerries) from the 8 km Meshy
terrain products.

Continent v2 is rebuilt from the Meshy "Isles of Enchantment" model at 8,000 m east-west (4,667.93 m per
model unit, uniform). None of the existing importers can start a territory that has no published
composition, so this tool writes the editor-side skeletons directly:

- eloria-assets/maps/continent-v2/_continent_v2/continent-v2-plan.json  (the v2 macro plan; nothing old reads it)
- eloria-assets/maps/continent-v2/<id>/world.json                       (stub manifest: frame, ownership, environment)
- godot-client/world_authoring/continent-v2/territories.json            (a separate v2 territory catalog)
- godot-client/world_authoring/continent-v2/viewer/<id>_view.tscn       (viewer wrapper: sky, sun, sea plane, island)
- godot-client/world_authoring/continent-v2/viewer/isles_view.tscn      (the three territories together)
- godot-client/world_authoring/regions/<id>/                            (scene, spec, base heights/colours,
  provenance, README)

The island group is three maps (owner decisions D2a-D2c, 2026-10-02; review/adjacent_map_design.md): sw_isle owns
the 2,038 m window over the main island, The Tollholms (`tollholms`) the SE islet, the east islet's east part and the
outer east pier, The Gull Skerries (`gull_skerries`) the south tip, its islets and the west cliff strip. sw_isle's
terrain grid covers the whole group and is the frame every conditioning rule below works in; the other two
territories take byte crops of its base, so the vertices two neighbours share are bit-identical by construction.
`--check` also runs the cross-territory checks of continent_v2_territories.py (ownership, shared seam vertices,
mirrored seam patches); godot-client/tests/test_continent_v2_territories.py runs them too.

The shared catalog (world_authoring/territories.json) and the old continent plan are not touched: two tests
pin exactly twelve territories, and the old plan path is hard-coded across the composer.

Terrain. The base is the 8 km island product (source-data/sw_island/heightfield_sw_2m.npy, 2 m cells,
350 m continent peak) with the approved-road corridors put back to the pre-road ground
(source-data/sw8_ground_after_pads_before_roads_2m.npy) where the editor's sculpt layer can grade them: the
roads are authored in the editor and their earthworks go in the sculpt layer. The sculpt tool writes at full
weight only 8 m or more inside the ownership window (a 4 m locked band and a 4 m fade), so outside that the
base keeps the product's own graded corridors: there the roads lie on graded ground instead of the bare
pre-road ground (slice-1 review). Vertices sit exactly on the product's cell centres (continent
x = 201 + 2i, z = 6061 + 2j), so no sample is interpolated.

Base colours are the Meshy albedo (sw8_alb2.npy) on the same cells, stored linear (as glTF vertex
colours are) in RGBA8.

Usage (from the checkout root or anywhere):
  python godot-client/tools/bootstrap_continent_v2_territory.py --source-data <work-output/continent-v2/source-data>
      --meshy-glb <Meshy_AI_..._texture.glb> --concept <full_continent.png>
      --approved-routes <work-output/continent-v2/review/routes.json> [--check]
--check rewrites nothing and fails when any output differs from what the inputs give, or when a
cross-territory check fails. A territory's scene and README are written only by its first bootstrap; after that
they belong to the editor and to hand edits.

Once a territory is served (its client package ships a served grid, or its registry row is continent-v2-served), its
frame is frozen: both modes refuse, before writing anything, a bootstrap that would move its server origin, its size
or its continent translation (continent_v2_territories.served_frame_problems). Saved characters stand on its tiles,
so such a move needs a position migration on the server first.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

# sw_isle frames the whole island group: its terrain grid covers the group and every conditioning rule works in its
# local frame (its OWNERSHIP decides the SCULPT_MARGIN corridor rule, its terrain window the pocket and shaft
# filters), so the group array stays byte-identical to the base sw_isle's sculpt layer is bound to. The other
# territories (TERRITORIES below) take byte crops of that array.
REGION_ID = "sw_isle"
LABEL = "Landfall"
ROOT_NAME = "SouthWestIsle"
PLAN_SCHEMA = "eloria-continent-v2-plan-v0"
U_M = 4667.9267244824205
EXTENT = [8000.0, 8877.3]
SEA_MODEL_Y = -0.074
VERTICAL = {"A": 259.0078328433769, "u0": 259.0078328433769, "peakMetres": 350.0, "gainAtSea": 1.0}
TRANSLATION = [1418.0, 0.0, 7270.0]
# Recipe decision D2: the largest 2,038 m server window over the main island (2,080 x 2,334 m does not fit
# one 2,048-tile map). Owner decision D2b (2026-10-02): the window moved 30 m north (z 6251-8289 before) so it owns
# the north beach; the land south of z 8259 belongs to gull_skerries and the land east of x 2437 to tollholms. The
# move changes no base vertex: no road corridor cell changes its SCULPT_MARGIN status (adjacent-map design s. 11).
OWNERSHIP = [[399.0, 6221.0], [2437.0, 6221.0], [2437.0, 8259.0], [399.0, 8259.0]]
CELL = 2.0
# The sculpt tool locks 2 cells inside the ownership edge and fades over 2 more (terrain_sculpt_tool.boundary_fields):
# it writes at full weight only this far inside the window.
SCULPT_MARGIN = 8.0
# Product grid: 1550 x 1360 cells, cell (r, c) centre at (201 + 2c, 6061 + 2r).
PRODUCT_X0, PRODUCT_Z0 = 201.0, 6061.0
# Terrain window: the island group (x 358-3128, z 6222-8618) plus about 60 m of sea.
COL0, ROW0, WIDTH, HEIGHT = 49, 51, 1446, 1259
APPROVED_ROUTES = ["R26", "R27", "R28", "R29", "R30", "R31", "R32", "R33", "R41", "R42"]
APPROVED_DECKS = ["B12", "B13", "B14", "B15", "B22", "B23", "B24", "B25"]
PLAZA = (975.0, 7391.0)
KEEP = (1082.8, 7333.5)
# A cropped territory's terrain grid is its ownership polygon's bounding box plus this much, clipped to the group
# grid (the authority ring needs 2 m; the rest is sea and shore to look at and to dress).
CROP_MARGIN = 60.0

# The island group's maps (owner decisions D2a-D2c, 2026-10-02; review/adjacent_map_design.md s. 2 and 9, design.json
# territories and markers). Polygon vertices lie on odd continent metres, the v2 vertex lattice. Marker y values are
# the design's (deck tops, road levels, the square); a None y is the base height at that vertex.
TERRITORIES = [
    {"id": REGION_ID, "label": LABEL, "root": ROOT_NAME, "translation": TRANSLATION, "ownership": OWNERSHIP,
     "crop": False,
     "role": "the landing island (arrival, #beam and respawn hub on the castle-town plaza): the 2,038 m window over "
             "the main island; its terrain grid covers the whole island group",
     "viewer": {"root": "SouthWestIsleView", "bookmark": "CastleBookmark", "seaTint": "sea-tint.png"}},
    {"id": "tollholms", "label": "The Tollholms", "root": "Tollholms", "translation": [2800.0, 0.0, 7398.0],
     "ownership": [[2437.0, 6453.0], [2517.0, 6499.0], [2637.0, 6511.0], [2717.0, 6547.0], [2797.0, 6627.0],
                   [2877.0, 6713.0], [2957.0, 6797.0], [3037.0, 6863.0], [3161.0, 6959.0], [3161.0, 8343.0],
                   [2437.0, 8343.0]],
     "crop": True,
     "role": "the second map (D2a): the SE islet with the village Tollholm, Ringholm (the east islet east of x 2437) "
             "and the outer east pier (the Toll Tower N11, B15 and the N14 ferry berth); its north-east edge follows "
             "the midline of the strait to the mainland",
     "viewer": {"root": "TollholmsView", "bookmark": "TollholmBookmark", "seaTint": "tollholms-sea-tint.png",
                "target": (2815.0, 54.25, 8019.0)},
     "markers": [
         # The hub and the village landmark stand on the square's open paving beside the map start: the square's
         # centre is the well, a solid (review 2026-10-03).
         {"id": "th-hub-tollholm-square", "kind": "runtime_point", "parent": "RuntimePoints/TerritoryPoints",
          "at": (2815.0, 54.25, 8012.5), "label": "Tollholm square (territory hub)",
          "extras": {"role": "territory-hub"}},
         {"id": "th-ferry-berth-east", "kind": "runtime_point", "parent": "RuntimePoints/TerritoryPoints",
          "at": (2600.0, 2.5, 7327.8), "label": "East ferry berth (N14)",   # on B15's deck centreline
          "extras": {"role": "ferry-berth", "to": "mainland pier B16 (future ferry)",
                     "status": "inactive until the v2 mainland map exists; not the new-player exit (review "
                               "2026-10-02: that is sw_isle's runtime-ferry-n10)"}},
         {"id": "landmark-th-tollholm", "kind": "landmark", "parent": "Landmarks", "at": (2815.0, 54.25, 8012.5),
          "label": "Tollholm", "extras": {"replaces": "sw_isle landmark-sw-se-islet-village (2740.0, 8026.7)"}},
         {"id": "landmark-th-east-pier-tower", "kind": "landmark", "parent": "Landmarks",
          "at": (2503.3, 2.5, 7332.0), "label": "Toll Tower (east pier)",
          "extras": {"replaces": "sw_isle landmark-sw-east-pier-tower (2503.3, 7332.0)", "decks": ["B15", "B25"]}},
         {"id": "landmark-th-ringholm", "kind": "landmark", "parent": "Landmarks", "at": (2471.0, 92.21, 6851.0),
          "label": "Ringholm tower", "extras": {"replaces": "sw_isle landmark-sw-east-islet (2466.7, 6850.0)"}},
         {"id": "landmark-th-spindle-hill", "kind": "landmark", "parent": "Landmarks",
          "at": (2621.0, 193.99, 8061.0), "label": "Spindle Hill summit",
          "extras": {"note": "the summit path (r42-cone-way) is built later (owner 2026-10-02)"}},
         {"id": "landmark-th-overlook", "kind": "landmark", "parent": "Landmarks", "at": (2452.6, 64.5, 7998.0),
          "label": "Knob overlook (R42)"},
         {"id": "landmark-th-lagoon-quay", "kind": "landmark", "parent": "Landmarks", "at": (2809.0, 1.91, 8087.0),
          "label": "Lagoon quay (L21 inlet)"},
     ],
     "patches": ["seam-mole-knob", "seam-mole-pier"]},
    {"id": "gull_skerries", "label": "The Gull Skerries", "root": "GullSkerries", "translation": [896.0, 0.0, 7876.0],
     "ownership": [[329.0, 7101.0], [399.0, 7101.0], [399.0, 8259.0], [1461.0, 8259.0], [1461.0, 8651.0],
                   [329.0, 8651.0]],
     "crop": True,
     "role": "the third map (D2c): the south tip, its two islets and the west cliff strip, which no window that "
             "holds the SE islet can reach",
     "viewer": {"root": "GullSkerriesView", "bookmark": "SouthTipBookmark", "seaTint": "gull_skerries-sea-tint.png",
                "target": (1189.0, None, 8285.0)},
     "markers": [
         {"id": "gs-hub-south-plateau", "kind": "runtime_point", "parent": "RuntimePoints/TerritoryPoints",
          "at": (1183.0, None, 8273.0), "label": "South plateau (territory hub)",
          "extras": {"role": "territory-hub",
                     "note": "open ground on the south plateau beside the map start, 14 m inside the open seam with "
                             "sw_isle and 9 m or more from every tree (review 2026-10-03: the first spot, 26 m in, "
                             "stood 5 m from a broadleaf trunk the start shared)"}},
     ]},
]
TERRITORY = {record["id"]: record for record in TERRITORIES}

# Seam moles: a rectangular Set patch declared identically (continent rectangle, height, feather 0) in both scenes
# so the walk crosses the border on land; edges on even continent metres, so every vertex is wholly in or out
# (adjacent-map design s. 3). sw_isle declared both in task A1; a first tollholms bootstrap declares them too.
MOLES = [
    {"id": "seam-mole-knob", "between": ["sw_isle", "tollholms"], "x": [2410.0, 2452.0], "z": [7926.0, 7938.0],
     "heightMetres": 2.5,
     "note": "R42 at the knob's north foot: sw_isle's knob quay lands on its west end, tollholms' r42-strand leaves "
             "its east end onto the gully beach"},
    {"id": "seam-mole-pier", "between": ["sw_isle", "tollholms"], "x": [2420.0, 2448.0], "z": [7314.0, 7356.0],
     "heightMetres": 2.0,
     "note": "the east pier at the headland tip: sw_isle's R33 quay and B25 harbour legs land on its west part, "
             "tollholms' tower pier leaves its east part"},
]
MOLE = {record["id"]: record for record in MOLES}
OPEN_SEAMS = [
    {"between": ["sw_isle", "tollholms"], "edge": {"x": 2437.0, "z": [6453.0, 8259.0]},
     "walkableRuns": [{"z": [6681.0, 6687.0], "heightMetres": [82.32, 85.57]},
                      {"z": [6703.0, 6795.0], "heightMetres": [89.84, 92.63]},
                      {"z": [6803.0, 6941.0], "heightMetres": [81.46, 87.91]}],
     "note": "the Ringholm plateau; R32 crosses at (2437.2, 87.41, 6815.9) on the product's graded corridor"},
    {"between": ["sw_isle", "gull_skerries"], "edge": {"z": 8259.0, "x": [399.0, 1461.0]},
     "walkableRuns": [{"x": [1093.0, 1103.0], "heightMetres": [126.15, 127.03]},
                      {"x": [1111.0, 1323.0], "heightMetres": [121.04, 133.97]}],
     "note": "the south plateau, roadless"},
    {"between": ["sw_isle", "gull_skerries"], "edge": {"x": 399.0, "z": [7101.0, 8259.0]},
     "walkableRuns": [], "note": "the west cliff strip: scenery, no lanes"},
]

CHECKOUT = Path(__file__).resolve().parents[2]
CLIENT = CHECKOUT / "godot-client"
V2_DIR = CLIENT / "world_authoring" / "continent-v2"
ASSET_DIR = CHECKOUT / "eloria-assets" / "maps" / "continent-v2"
PLAN_PATH = ASSET_DIR / "_continent_v2" / "continent-v2-plan.json"


def region_dir(territory: dict) -> Path:
    return CLIENT / "world_authoring" / "regions" / territory["id"]


def manifest_path(territory: dict) -> Path:
    return ASSET_DIR / territory["id"] / "world.json"


def crop_window(territory: dict) -> tuple[int, int, int, int]:
    """(row0, col0, rows, cols) of the territory's terrain grid inside the group grid."""
    if not territory["crop"]:
        return 0, 0, HEIGHT, WIDTH
    poly = np.asarray(territory["ownership"], float)
    first = np.array([PRODUCT_X0 + CELL * COL0, PRODUCT_Z0 + CELL * ROW0])
    lo = np.maximum(np.floor((poly.min(0) - CROP_MARGIN - first) / CELL), 0).astype(int)
    hi = np.minimum(np.ceil((poly.max(0) + CROP_MARGIN - first) / CELL), [WIDTH - 1, HEIGHT - 1]).astype(int)
    return int(lo[1]), int(lo[0]), int(hi[1] - lo[1] + 1), int(hi[0] - lo[0] + 1)


def first_vertex(territory: dict) -> tuple[float, float]:
    """Continent x, z of the territory's terrain vertex (0, 0)."""
    row0, col0, _, _ = crop_window(territory)
    return PRODUCT_X0 + CELL * (COL0 + col0), PRODUCT_Z0 + CELL * (ROW0 + row0)


def terrain_origin(territory: dict) -> list[float]:
    x, z = first_vertex(territory)
    return [x - territory["translation"][0], z - territory["translation"][2]]


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def json_text(value) -> str:
    return json.dumps(value, indent=1, ensure_ascii=False, allow_nan=False) + "\n"


def clean(value):
    """NaN-free copy for JSON (the review routes carry NaN medians)."""
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean(item) for item in value]
    return value


def gd(value: float) -> str:
    if abs(value) < 5e-13:
        value = 0.0
    text = format(float(value), ".12g")
    return text


def ownership_sha(polygon: list) -> str:
    # territory_catalog.gd: JSON.stringify(_polygon_array(polygon)).sha256_text(), floats.
    text = "[" + ",".join("[%s,%s]" % (repr(float(x)), repr(float(z))) for x, z in polygon) + "]"
    return sha_bytes(text.encode("utf-8"))


def server_frame(polygon: list, translation: list) -> dict:
    poly = np.asarray(polygon, float)
    lo, hi = poly.min(0), poly.max(0)
    centre = np.array([translation[0], translation[2]])
    local_lo = np.floor(lo - centre) - 4
    local_hi = np.ceil(hi - centre) + 4
    cells = int(math.ceil(max(local_hi - local_lo) / 6) * 6)
    origin = [int(-local_lo[0]), int(local_hi[1])]
    if cells > 2048:
        raise SystemExit("ownership window exceeds a 2,048-tile server map")
    return {"origin": origin, "cells": [cells, cells], "collisionOriginMetres": [float(-origin[0]), float(origin[1])]}


def srgb_to_linear(values: np.ndarray) -> np.ndarray:
    c = values.astype(np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


# pad holes levelled by heights.padHoles also adopt the water-hued texels this many cells round them (colours)
ADOPT_HALO_CELLS = 3


def condition_colors(albedo: np.ndarray, heights: np.ndarray, classes: np.ndarray, water_surface: np.ndarray,
                     params: dict, cut: np.ndarray | None = None,
                     adopt: np.ndarray | None = None) -> tuple[np.ndarray, dict]:
    """Linear albedo (0-1) of the product grid with the product's two colour artefacts repaired (polish fix plan P1).

    - Off-plate cells: the Meshy texture does not cover them and the product gave them albedo 0, which draws black
      shards where the bicubic upsampling lifted them over the sea. Cells at or above 0 m take the nearest covered
      dry texel; cells below 0 m the nearest covered sea texel, darkened towards the seabed colour with depth.
    - Water paint on dry walls: the product cut every painted lake and river cell down to its level, so the Meshy
      water paint now colours walls that stand above the water. Water-hued cells within the given distance of
      inland water that stand more than the given height over the local water level (and over the sea) take the
      nearest covered dry, non-water-hued texel; on faces steeper than the given grade it is pulled towards rock
      grey at the texel's own luminance.
    - Adopted cells (`adopt`: the pad holes the height conditioning levelled with their pad): the final colour of
      the nearest painted-land cell outside them, so a filled crevice reads as the court and lawn round it rather
      than as the Meshy river paint it was cut into.
    `heights` decide above or below sea: the conditioned base, with the sculpt layer's effective heights where
    the snapshot has them."""
    from scipy import ndimage

    p = params["colors"]
    linear = srgb_to_linear(albedo)
    uncovered = (albedo == 0).all(-1)
    dry = ~uncovered & (classes == 1)
    sea = ~uncovered & (classes == 0)
    _, near_dry = ndimage.distance_transform_edt(~dry, return_indices=True)
    _, near_sea = ndimage.distance_transform_edt(~sea, return_indices=True)
    out = linear.copy()
    above = uncovered & (heights >= 0.0)
    below = uncovered & (heights < 0.0)
    out[above] = linear[near_dry[0][above], near_dry[1][above]]
    seabed = np.asarray(p["seabedLinear"], np.float64) / 255.0
    t = np.clip(-heights / p["seabedDepthMetres"], 0.0, 1.0)[..., None]
    lerped = linear[near_sea[0], near_sea[1]] * (1.0 - t) + seabed * t
    out[below] = lerped[below]
    # water paint on dry walls
    hue = (linear[..., 2] > linear[..., 0] + p["waterHue"]["blueOverRed"]) & (linear[..., 1] > linear[..., 0])
    inland = (classes == 2) | (classes == 3)
    near_inland = ndimage.distance_transform_edt(~inland) * CELL <= p["wallsWithinMetresOfInlandWater"]
    # Wet: a painted water cell at most wallAboveWaterMetres over its own water surface, or anything under the
    # sea. (A local maximum of the water surface, the first draft, kept the walls between the product's stepped
    # beds teal: within 10 m of a wall foot there is often a terrace pool tens of metres higher.)
    own_level = np.where(classes >= 2, np.nan_to_num(water_surface, nan=-np.inf), -np.inf)
    wet = (heights <= np.maximum(own_level, 0.0) + p["wallAboveWaterMetres"])
    # A wet cell at the foot or the brink of a wall (a 4-neighbour more than wallStepMetres away in height) colours
    # the wall face too: vertex colours interpolate across the 2 m triangle that spans the drop.
    h64 = heights.astype(np.float64)
    step = np.zeros(h64.shape)
    for axis in (0, 1):
        jump = np.abs(np.diff(h64, axis=axis))
        lead = [slice(None)] * 2
        tail = [slice(None)] * 2
        lead[axis] = slice(0, -1)
        tail[axis] = slice(1, None)
        step[tuple(lead)] = np.maximum(step[tuple(lead)], jump)
        step[tuple(tail)] = np.maximum(step[tuple(tail)], jump)
    walls = near_inland & ~uncovered & hue & (~wet | (step > p["wallStepMetres"]))
    source = ~uncovered & (classes == 1) & ~hue
    _, near_src = ndimage.distance_transform_edt(~source, return_indices=True)
    out[walls] = linear[near_src[0][walls], near_src[1][walls]]
    gz, gx = np.gradient(heights.astype(np.float64), CELL)
    steep = walls & (np.hypot(gx, gz) > p["rockGreyAboveGrade"])
    rock = np.asarray(p["rockGreyLinear"], np.float64)
    luminance = out[..., :3] @ np.array([0.2126, 0.7152, 0.0722])
    grey = rock[None, :] * (luminance[steep] / float(rock @ np.array([0.2126, 0.7152, 0.0722])))[:, None]
    out[steep] = out[steep] * (1.0 - p["rockGreyMix"]) + grey * p["rockGreyMix"]
    # faces the height conditioning cut open (the L12 gorge's slope limit): the Meshy texel there is the top of the
    # ground that was removed, so steep cut faces are pulled towards rock grey the same way
    faces = np.zeros(heights.shape, bool)
    if cut is not None and "cutFaces" in p:
        cf = p["cutFaces"]
        faces = (cut >= cf["minCutMetres"]) & (np.hypot(gx, gz) > cf["aboveGrade"]) & ~steep
        lum = out[..., :3] @ np.array([0.2126, 0.7152, 0.0722])
        grey_faces = rock[None, :] * (lum[faces] / float(rock @ np.array([0.2126, 0.7152, 0.0722])))[:, None]
        out[faces] = out[faces] * (1.0 - p["rockGreyMix"]) + grey_faces * p["rockGreyMix"]
    window = (slice(ROW0, ROW0 + HEIGHT), slice(COL0, COL0 + WIDTH))
    stats = {"uncoveredFilledAboveSea": int(above[window].sum()), "uncoveredFilledBelowSea": int(below[window].sum()),
             "waterPaintOnDryReplaced": int(walls[window].sum()),
             "waterPaintOnDryPulledToRockGrey": int(steep[window].sum()),
             "cutFacesPulledToRockGrey": int(faces[window].sum()),
             "countedOn": "the terrain window's vertices"}
    if "grade" in p:
        out, stats["grade"] = grade_colors(np.clip(out, 0.0, 1.0), heights, classes, p["grade"], window)
    if "sand" in p:
        out, stats["sand"] = sand_colors(np.clip(out, 0.0, 1.0), heights, classes, p["sand"], window)
    if adopt is not None and adopt.any():
        # the Meshy river paint spills a cell or two past the painted river cells: water-hued texels within
        # ADOPT_HALO_CELLS of a levelled hole are adopted with it; donors are painted land that is not water-hued
        final = np.clip(out, 0.0, 1.0)
        # teal-greens count too (blue over red at all): the river paint's edge texels are blue-green, not blue
        hued = (final[..., 2] > final[..., 0]) & (final[..., 1] > final[..., 0])
        zone = adopt | (ndimage.binary_dilation(adopt, structure=np.ones((3, 3), bool),
                                                iterations=ADOPT_HALO_CELLS) & hued)
        donor = (classes == 1) & ~zone & ~hued & ~uncovered
        _, near_donor = ndimage.distance_transform_edt(~donor, return_indices=True)
        out[zone] = out[near_donor[0][zone], near_donor[1][zone]]
        stats["adoptedFromNearestLand"] = int(zone[window].sum())
    return np.clip(out, 0.0, 1.0), stats


def linear_to_srgb(values: np.ndarray) -> np.ndarray:
    c = np.clip(values, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1.0 / 2.4) - 0.055)


def smoothstep(edge0: float, edge1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def grade_colors(linear: np.ndarray, heights: np.ndarray, classes: np.ndarray, g: dict,
                 window: tuple) -> tuple[np.ndarray, dict]:
    """A colour grade of the land's pale Meshy albedo towards the concept's ground (polish fix stage, visual review
    D1: about a quarter of the land rendered as snow-white smear at every camera). Pale texels (sRGB luminance over
    pale.luminance, saturation under pale.saturation, eased by smoothsteps) on land are pulled, by strength, towards
    a target: on slopes up to the rock grade a mix of lawn green and dry meadow chosen by a smooth fixed-seed noise
    and by height; on faces past the rock grade mid rock grey; the texel's own luminance against its 3-cell
    neighbourhood is kept as a factor, so the Meshy detail survives. Beaches (within beach.withinMetresOfSea of the
    sea, under beach.belowMetres, flatter than beach.belowGrade) keep their sand. Water cells and the sea floor are
    untouched."""
    from scipy import ndimage

    srgb = linear_to_srgb(linear)
    lum = srgb @ np.array([0.2126, 0.7152, 0.0722])
    hi, lo = srgb.max(-1), srgb.min(-1)
    sat = (hi - lo) / np.maximum(hi, 1e-6)
    pale = g["pale"]
    w_pale = smoothstep(pale["luminance"][0], pale["luminance"][1], lum) *         (1.0 - smoothstep(pale["saturation"][0], pale["saturation"][1], sat))
    h = heights.astype(np.float64)
    gz, gx = np.gradient(h, CELL)
    grade = np.hypot(gx, gz)
    sea = (classes == 0) | (h < 0.0)
    dsea = ndimage.distance_transform_edt(~sea) * CELL
    b = g["beach"]
    beach = (1.0 - smoothstep(b["withinMetresOfSea"][0], b["withinMetresOfSea"][1], dsea)) *         (1.0 - smoothstep(b["belowMetres"][0], b["belowMetres"][1], h)) *         (1.0 - smoothstep(b["belowGrade"][0], b["belowGrade"][1], grade))
    rock = smoothstep(g["rockGrade"][0], g["rockGrade"][1], grade)
    rng = np.random.default_rng(g["noiseSeed"])
    noise = ndimage.gaussian_filter(rng.standard_normal(h.shape), g["noiseSigmaCells"])
    noise /= max(float(np.abs(noise).max()), 1e-9)
    meadow = np.clip(g["meadowBase"] + g["meadowNoise"] * noise +
                     g["meadowPerMetre"] * np.clip(h - g["meadowFromMetres"], 0.0, None), 0.0, 1.0)
    lawn = np.asarray(g["lawnSrgb"], np.float64) / 255.0
    dry = np.asarray(g["meadowSrgb"], np.float64) / 255.0
    grey = np.asarray(g["rockSrgb"], np.float64) / 255.0
    veg = lawn[None, None, :] * (1.0 - meadow[..., None]) + dry[None, None, :] * meadow[..., None]
    target = veg * (1.0 - rock[..., None]) + grey[None, None, :] * rock[..., None]
    local = ndimage.gaussian_filter(lum, g["detailSigmaCells"])
    detail = np.clip(lum / np.maximum(local, 1e-4), g["detailClamp"][0], g["detailClamp"][1])
    target = np.clip(target * detail[..., None], 0.0, 1.0)
    land = (classes == 1) & (h >= g["landAboveMetres"])
    weight = np.where(land, w_pale * (1.0 - beach) * g["strength"], 0.0)
    graded = srgb * (1.0 - weight[..., None]) + target * weight[..., None]
    out = srgb_to_linear(np.clip(graded, 0.0, 1.0) * 255.0)
    in_window = np.zeros(h.shape, bool)
    in_window[window] = True
    land_w = land & in_window
    pale_before = land_w & (lum > pale["luminance"][1]) & (sat < pale["saturation"][0])
    g_lum = np.clip(graded, 0, 1) @ np.array([0.2126, 0.7152, 0.0722])
    g_hi, g_lo = graded.max(-1), graded.min(-1)
    g_sat = (g_hi - g_lo) / np.maximum(g_hi, 1e-6)
    pale_after = land_w & (g_lum > pale["luminance"][1]) & (g_sat < pale["saturation"][0])
    stats = {"landVertices": int(land_w.sum()),
             "paleShareBefore": round(float(pale_before.sum() / max(land_w.sum(), 1)), 4),
             "paleShareAfter": round(float(pale_after.sum() / max(land_w.sum(), 1)), 4),
             "gradedVerticesOver0.25": int((land_w & (weight > 0.25)).sum()),
             "meanWeightOnLand": round(float(weight[land_w].mean()), 4),
             "countedOn": "the terrain window's land vertices (painted land at or above landAboveMetres)"}
    return out, stats


def sand_colors(linear: np.ndarray, heights: np.ndarray, classes: np.ndarray, s: dict,
                window: tuple) -> tuple[np.ndarray, dict]:
    """Beach sand (game-look fix stage, review D3: the beaches rendered grey-white, the cove's band almost snow, where
    the concept paints gold sand). The colour grade keeps beaches as they are, and the Meshy texels there are its surf
    paint and pale grey shore (beach band median sRGB 147/153/144, the cove 177/187/189). Dry cells near the sea, low
    and flat (the grade's beach weight: within withinMetresOfSea of ground under 0 m, under belowMetres, flatter than
    belowGrade, each eased by a smoothstep) whose texel is grey or pale (saturation under unsaturated, smoothstepped)
    are pulled by strength towards sandSrgb, keeping each texel's luminance against its detailSigmaCells
    neighbourhood (clamped to detailClamp), so the shore's own mottling stays. Sea is told by height alone (ground
    under 0 m), so dry cells the painted classes call sea (a smoothed shore outline) get sand too; inland water
    (classes 2, 3), ground under landAboveMetres and green vegetation (saturated) are untouched."""
    from scipy import ndimage

    srgb = linear_to_srgb(linear)
    lum = srgb @ np.array([0.2126, 0.7152, 0.0722])
    hi, lo = srgb.max(-1), srgb.min(-1)
    sat = (hi - lo) / np.maximum(hi, 1e-6)
    h = heights.astype(np.float64)
    gz, gx = np.gradient(h, CELL)
    grade = np.hypot(gx, gz)
    dsea = ndimage.distance_transform_edt(~(h < 0.0)) * CELL
    beach = (1.0 - smoothstep(s["withinMetresOfSea"][0], s["withinMetresOfSea"][1], dsea)) *         (1.0 - smoothstep(s["belowMetres"][0], s["belowMetres"][1], h)) *         (1.0 - smoothstep(s["belowGrade"][0], s["belowGrade"][1], grade))
    grey = 1.0 - smoothstep(s["unsaturated"][0], s["unsaturated"][1], sat)
    land = (h >= s["landAboveMetres"]) & (classes != 2) & (classes != 3)
    weight = np.where(land, beach * grey * s["strength"], 0.0)
    local = ndimage.gaussian_filter(lum, s["detailSigmaCells"])
    detail = np.clip(lum / np.maximum(local, 1e-4), s["detailClamp"][0], s["detailClamp"][1])
    target = np.clip((np.asarray(s["sandSrgb"], np.float64) / 255.0)[None, None, :] * detail[..., None], 0.0, 1.0)
    graded = srgb * (1.0 - weight[..., None]) + target * weight[..., None]
    out = srgb_to_linear(np.clip(graded, 0.0, 1.0) * 255.0)
    in_window = np.zeros(h.shape, bool)
    in_window[window] = True
    touched = in_window & (weight > 0.25)
    g = np.clip(graded, 0.0, 1.0)
    stats = {"verticesOver0.25": int(touched.sum()),
             "meanWeightOnBeach": round(float(weight[in_window & land & (beach > 0.5)].mean()), 4)
             if (in_window & land & (beach > 0.5)).any() else 0.0,
             "medianSrgbBefore": [int(round(v * 255)) for v in np.median(srgb[touched], axis=0)] if touched.any()
             else [],
             "medianSrgbAfter": [int(round(v * 255)) for v in np.median(g[touched], axis=0)] if touched.any() else [],
             "countedOn": "the terrain window's vertices whose sand weight is over 0.25"}
    return out, stats


def protection_mask(source: Path, corridors: np.ndarray, params: dict) -> tuple[np.ndarray, np.ndarray]:
    """Cells the height conditioning never changes (fix plan mask P): every sculpt-indexed cell (road earthworks,
    the town ramp), the road corridors grown by two cells, the castle compound and town pads, the north-tower pad and
    the lighthouse pads, so road, town and deck heights stay exactly as authored. Also returns the same mask without
    the two-cell corridor margin: the pocket fill may raise margin cells (pits below the sea beside a road on the
    L12 shore), never a corridor or sculpt-indexed cell."""
    from scipy import ndimage

    work = source / "work"
    hard = np.load(work / "sw8_sculpt_cells2.npy").astype(bool) | corridors
    for name in ("sw8_compound2", "sw8_town2", "sw8_ntpad2", "sw8_lh2"):
        hard |= np.load(work / f"{name}.npy").astype(bool)
    margin = ndimage.binary_dilation(corridors, iterations=params["heights"]["protectionCorridorDilationCells"])
    return hard | margin, hard


def condition_heights(base: np.ndarray, uncovered: np.ndarray, protect: np.ndarray, hard: np.ndarray,
                      params: dict, classes: np.ndarray | None = None, keep: np.ndarray | None = None,
                      deck: np.ndarray | None = None, water: dict | None = None,
                      water_surface: np.ndarray | None = None, sculpt_effective: np.ndarray | None = None,
                      roadline: np.ndarray | None = None, pads: np.ndarray | None = None,
                      roads: np.ndarray | None = None,
                      lighthouse: np.ndarray | None = None) -> tuple[np.ndarray, dict]:
    """The product heights with two of its artefacts repaired (polish fix plan P2), never on protected cells.

    - Off-plate ring: the bicubic upsampling overshot the 33 m step at the edge of the Meshy plate into a +1 to
      +7 m ridge a few metres off every coast, and the product wrote it over its -0.5 m sea clamp. Off-plate cells
      within bandMetres of the plate are lowered to the nearest off-plate cell beyond the band and to ceilingMetres
      at most; none is raised.
    - High-rim inland pockets: inland river nodes without a level became level 0 and the upsampling turned them
      into shafts 10-31 m below the sea inside rims 47-148 m high. Every below-sea component that does not reach
      the grid edge and whose rim median stands over rimP50MinMetres is raised to the 10th percentile of its rim,
      the floor blended into the rim by a small Gaussian (pocket cells only; never lowered). Low-rim pockets (the
      west creek mouth, the SE lagoon) are real water at sea level and stay. Pocket cells in the corridor margin
      are filled too (17 lake cells 10-12 m under the sea beside the L12 shore road at 47-49 m): the fill stays
      below the road, and no corridor or sculpt-indexed cell changes."""
    from scipy import ndimage

    rule = params["heights"]
    h = base.astype(np.float64).copy()
    ring = rule["offPlateRing"]
    distance = ndimage.distance_transform_edt(uncovered) * CELL
    band = uncovered & (distance <= ring["bandMetres"]) & ~protect
    beyond = uncovered & (distance > ring["bandMetres"])
    _, nearest = ndimage.distance_transform_edt(~beyond, return_indices=True)
    shelf = h[nearest[0], nearest[1]]
    lowered = np.minimum(np.minimum(h, shelf), ring["ceilingMetres"])
    ring_moved = band & (lowered < h)
    ring_drop = (h - lowered)[ring_moved]
    h[band] = lowered[band]

    pockets_rule = rule["inlandPockets"]
    labels, count = ndimage.label(h < 0.0, structure=np.ones((3, 3), bool))
    edge = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]])).tolist())
    filled = h.copy()
    pocket_mask = np.zeros(h.shape, bool)
    pockets = []
    for label in range(1, count + 1):
        if label in edge:
            continue
        cells = labels == label
        if not cells[ROW0:ROW0 + HEIGHT, COL0:COL0 + WIDTH].any():
            continue  # outside the terrain window: never written
        rim = ndimage.binary_dilation(cells, iterations=pockets_rule["rimCells"]) & ~cells
        p10, p50 = np.percentile(h[rim], [pockets_rule["fillToRimPercentile"], 50])
        if p50 <= pockets_rule["rimP50MinMetres"]:
            continue
        target = cells & ~hard
        filled[target] = np.maximum(h[target], p10)
        pocket_mask |= target
        rows, cols = np.nonzero(cells)
        pockets.append({"cells": int(cells.sum()), "protectedCells": int((cells & hard).sum()),
                        "corridorMarginCellsFilled": int((cells & protect & ~hard).sum()),
                        "continentX": [PRODUCT_X0 + CELL * int(cols.min()), PRODUCT_X0 + CELL * int(cols.max())],
                        "continentZ": [PRODUCT_Z0 + CELL * int(rows.min()), PRODUCT_Z0 + CELL * int(rows.max())],
                        "minMetres": round(float(h[cells].min()), 2), "rimP10Metres": round(float(p10), 2),
                        "rimP50Metres": round(float(p50), 2)})
    blended = ndimage.gaussian_filter(filled, pockets_rule["blendSigmaCells"])
    filled[pocket_mask] = np.maximum(filled[pocket_mask], blended[pocket_mask])
    rise = (filled - h)[pocket_mask]
    h[pocket_mask] = filled[pocket_mask]
    stats = {
        "offPlateRing": {"cellsLowered": int(ring_moved.sum()),
                         "maxDropMetres": round(float(ring_drop.max()), 3) if ring_drop.size else 0.0,
                         "highestOffPlateCellMetres": round(float(h[uncovered].max()), 3),
                         "protectedOffPlateCellsAbove0": int((uncovered & protect & (h > 0)).sum())},
        "inlandPockets": {"filled": pockets, "cellsRaised": int((rise > 0).sum()),
                          "maxRiseMetres": round(float(rise.max()), 3) if rise.size else 0.0},
        "countedOn": "the product grid (1360 x 1550 cells)",
    }
    if "inlandShafts" in rule:
        h, stats["inlandShafts"] = inland_shafts(h, classes, water_surface, hard, rule)
    if "padHoles" in rule:
        h, stats["padHoles"] = pad_holes(h, hard, pads, rule["padHoles"])
    if "coastBand" in rule:
        h, stats["coastBand"] = coast_band(h, classes, protect | (keep > 0), rule["coastBand"])
    if "gorge" in rule:
        release = rule["gorge"].get("release")
        if release is None:
            h, stats["gorge"] = gorge(h, classes, protect, hard, keep, deck, water, water_surface, rule["gorge"])
        else:
            h, stats["gorge"] = gorge_with_release(h, classes, protect, hard, keep, deck, water, water_surface,
                                                   rule["gorge"], sculpt_effective, roadline, pads)
    if "finBanks" in rule:
        h, stats["finBanks"] = fin_banks(h, protect | (keep > 0), rule["finBanks"], rule["gorge"]["stream"]["points"])
    if "padShore" in rule:
        h, stats["padShore"] = pad_shore(h, classes, protect, lighthouse, roads, keep, rule["padShore"])
    return h.astype(np.float32), stats


def pad_shore(h: np.ndarray, classes: np.ndarray, protect: np.ndarray, pads: np.ndarray, roads: np.ndarray,
              keep: np.ndarray, rule: dict) -> tuple[np.ndarray, dict]:
    """A shelving beach round the SE lighthouse pad (game-look fix stage, owner decision 2026-10-02: "smooth the SE
    peninsula shore: outline + shelving beach"). The island product lifted the peninsula to a flat 2.5 m pad cut on
    the painted per-cell shoreline, so the pad ends in a 2.8 m vertical step that draws the coast as a staircase of
    white sheets. Inside each box: the painted land is smoothed into an outline (a Gaussian of smoothSigmaCells over
    the land mask, cut at 0.5) and, within beachWidthMetres inside that outline, the ground falls on a smoothstep
    from its own height to toeMetres at the outline, so the flat top ends on a smooth curve and the shore shelves into
    the sea, never falling away from a kept cell steeper than keepSlope; under water the sea keeps at most
    -(seaShoreMetres + seaGrade d) out to seaWithinMetres (0: the coast band's shelf stays as it is). Only lowered
    on land and only deepened at sea. The painted classes are re-asserted (land at minLandMetres or more, sea at
    maxSeaMetres or less), so the coastline keeps its sign. The lighthouse pad itself is released, but never a road
    corridor with its margin or a sculpt-indexed cell (`roads`), the keep flags (built footprints, deck ground, deck
    landings), the other pads, or a keepRects rectangle [x, z, length, width, yaw degrees] or keepCircles circle
    [x, z, r] (the quay and the N10 court, the solid kit pieces on the pad)."""
    from scipy import ndimage

    out = h.astype(np.float64).copy()
    all_stats = []
    for bx in rule["boxes"]:
        rows, cols = gorge_box({"boxLocal": bx["boxLocal"]})
        H = out[rows, cols].copy()
        H0 = H.copy()
        X, Z = product_local_xz(rows, cols)
        land = classes[rows, cols] == 1
        sea = classes[rows, cols] == 0
        fixed = (protect[rows, cols] & ~pads[rows, cols]) | roads[rows, cols] | (keep[rows, cols] > 0)
        for x, z, length, width, yaw in rule.get("keepRects", []):
            a = math.radians(yaw)
            u = (X - x) * math.cos(a) - (Z - z) * math.sin(a)
            v = (X - x) * math.sin(a) + (Z - z) * math.cos(a)
            fixed |= (np.abs(u) <= length / 2) & (np.abs(v) <= width / 2)
        for x, z, r in rule.get("keepCircles", []):
            fixed |= np.hypot(X - x, Z - z) <= r
        field = ndimage.gaussian_filter(land.astype(np.float64), rule["smoothSigmaCells"])
        wobble = rule.get("outlineNoise")
        if wobble:
            # a gentle fixed-seed wobble (amplitude at the noise's extreme, under 0.5): it never flips a cell the
            # smoothed land mask holds at 0 or 1, only moves the outline a cell or so within its blur, so the
            # smoothed edge does not run as a ruler line
            noise = ndimage.gaussian_filter(np.random.default_rng(int(wobble["seed"])).standard_normal(field.shape),
                                            wobble["sigmaCells"])
            field = field + wobble["amplitude"] * noise / max(float(np.abs(noise).max()), 1e-9)
        smooth = field >= 0.5
        d_in = (ndimage.distance_transform_edt(smooth) - 0.5) * CELL
        d_out = (ndimage.distance_transform_edt(~smooth) - 0.5) * CELL
        width = rule["beachWidthMetres"]
        t = np.clip(d_in / width, 0.0, 1.0)
        ease = t * t * (3.0 - 2.0 * t)
        beach = rule["toeMetres"] + (H0 - rule["toeMetres"]) * ease
        band = land & ~fixed & (d_in < width) & (H0 > rule["toeMetres"])
        H[band] = np.minimum(H0, beach)[band]
        # the beach falls away from every cell it keeps (the quay, the N10 court, the road corridors, the kept
        # pieces) no steeper than keepSlope, so a kept cell stands on a bank, never on a step
        slope = rule["keepSlope"]
        support = np.where(fixed, H0, -np.inf)
        for _ in range(int(math.ceil(3.0 / (slope * CELL))) + 2):
            sp = np.pad(support, 1, mode="constant", constant_values=-np.inf)
            support = np.maximum.reduce([
                support, sp[1:-1, :-2] - slope * CELL, sp[1:-1, 2:] - slope * CELL,
                sp[:-2, 1:-1] - slope * CELL, sp[2:, 1:-1] - slope * CELL,
                sp[:-2, :-2] - slope * CELL * math.sqrt(2.0), sp[:-2, 2:] - slope * CELL * math.sqrt(2.0),
                sp[2:, :-2] - slope * CELL * math.sqrt(2.0), sp[2:, 2:] - slope * CELL * math.sqrt(2.0)])
        H[band] = np.minimum(H0, np.maximum(H, support))[band]
        shelf = -(rule["seaShoreMetres"] + rule["seaGrade"] * np.maximum(d_out, 0.0))
        wet = sea & ~fixed & (d_out <= rule["seaWithinMetres"])
        H[wet] = np.minimum(H[wet], shelf[wet])
        land_now, sea_now = land, sea
        edge = np.zeros(H.shape, bool)
        if rule.get("outlineSign"):
            # the coast follows the smoothed outline, not the painted per-cell classes (whose 2 m teeth the first
            # rule kept): painted land outside it becomes sea, painted sea inside it land, never a kept cell, nor
            # a cell whose kept neighbour's bank (keepSlope) still stands over the sea there
            to_sea = land & ~smooth & ~fixed & (support <= 0.0)
            to_land = sea & smooth & ~fixed
            land_now = (land & ~to_sea) | to_land
            sea_now = (sea & ~to_land) | to_sea
            # and the ground at the waterline follows the outline's signed distance (from the smooth field: its
            # offset from 0.5 over its gradient), toeMetres x sd / waterlineMetres, so the rendered 0 m line is
            # interpolated along the curve between the 2 m vertices instead of zig-zagging across every cell whose
            # sign flips (a +-minLand / maxSea step draws the per-cell staircase whatever the outline's shape)
            fy, fx = np.gradient(field)
            sd = (field - 0.5) / np.maximum(np.hypot(fx, fy), 1e-3) * CELL
            w0 = float(rule.get("waterlineMetres", 2.0))
            agrees = (land_now & smooth) | (sea_now & ~smooth)
            edge = agrees & ~fixed & (np.abs(sd) <= w0)
            profile = rule["toeMetres"] * np.clip(sd / w0, -1.0, 1.0)
            H = np.where(edge & land_now, np.clip(np.minimum(H, profile), 0.02, None), H)
            H = np.where(edge & sea_now, np.minimum(H, np.minimum(profile, -0.02)), H)
        H = np.where(land_now & ~fixed & ~edge, np.maximum(H, rule["minLandMetres"]), H)
        H = np.where(sea_now & ~fixed & ~edge, np.minimum(H, rule["maxSeaMetres"]), H)
        out[rows, cols] = H

        def waterline_edges(dry):
            return int((dry[:, 1:] != dry[:, :-1]).sum() + (dry[1:, :] != dry[:-1, :]).sum())
        change = H - H0
        moved = np.abs(change) > 0.05
        lowered_land = land & (change < -0.05)
        all_stats.append({"boxLocal": bx["boxLocal"], "note": bx.get("note", ""),
                          "landCellsLowered": int(lowered_land.sum()),
                          "landAreaLoweredM2": int(lowered_land.sum() * CELL * CELL),
                          "landMaxLoweredMetres": round(float(-change[land].min()), 3) if land.any() else 0.0,
                          "landVolumeCutM3": round(float(np.clip(-change, 0, None)[land].sum() * CELL * CELL), 1),
                          "seaCellsDeepened": int((sea & (change < -0.05)).sum()),
                          "seaMaxDeepenedMetres": round(float(-change[sea].min()), 3) if sea.any() else 0.0,
                          "fixedCellsInBand": int((fixed & land & (d_in < width)).sum()),
                          "fixedCellsChanged": int((fixed & moved).sum()),
                          "outlineSign": bool(rule.get("outlineSign", False)),
                          "landToSeaCells": int((land & ~land_now).sum()),
                          "seaToLandCells": int((sea & land_now).sum()),
                          "waterlineProfileCells": int(edge.sum()),
                          "waterlineEdgesBefore": waterline_edges(H0 >= 0.0),
                          "waterlineEdgesAfter": waterline_edges(H >= 0.0)})
    return out, {"boxes": all_stats}


def fin_banks(h: np.ndarray, fixed: np.ndarray, rule: dict, stream_points: list) -> tuple[np.ndarray, dict]:
    """A talus bank under the gorge-mouth fins (game-look fix stage, owner decision 2026-10-02: "clad the gorge-mouth
    knife fins, with a slight bank widening into the inlet"). The L12 outlet stream runs at 45-47 m on a bank 3-11 m
    thick whose inlet side drops straight to the sea-level inlet (cove C04): seen from the inlet it is a pale blade
    45 m high. Lowering it would leave the stream over a 45 m drop, so the bank is widened instead: inside boxLocal,
    sea-level inlet cells (under seaLevelBelowMetres, joined to the open sea) within reach of a fin (ground at
    finAboveMetres or more within finStreamWithinMetres of the outlet stream's line, heights.gorge.stream: the
    stream's own bank, not the inlet's other walls) are raised to a talus, toeMetres + grade x (W - d) at d metres from the cliff and at most
    apronTopMetres, where the toe distance W is widenMetres but never more than keepOpenShare of the inlet's local
    half-width (the largest distance to dry ground within halfWidthWindowMetres), so the inlet keeps open water down
    its middle; under water the talus runs on at the same grade until it meets the bed. Cells are only raised, never
    a protected or kept cell, and never within a plungePools circle (the waterfall's foot stays water). The cliff
    above the talus and the stream's bank are unchanged; rock kit pieces clad the face (the editor scene)."""
    from scipy import ndimage

    rows, cols = gorge_box(rule)
    H = h[rows, cols].astype(np.float64).copy()
    H0 = H.copy()
    F = fixed[rows, cols]
    X, Z = product_local_xz(rows, cols)
    low = H < rule["seaLevelBelowMetres"]
    labels, _ = ndimage.label(low, structure=np.ones((3, 3), bool))
    # the open sea: the low component that reaches the box's seaward edges (rule seaEdges: any of "north", "south",
    # "east", "west")
    edge_cells = np.zeros(H.shape, bool)
    for side in rule["seaEdges"]:
        if side == "north":
            edge_cells[0, :] = True
        elif side == "south":
            edge_cells[-1, :] = True
        elif side == "west":
            edge_cells[:, 0] = True
        elif side == "east":
            edge_cells[:, -1] = True
    open_ids = np.unique(labels[edge_cells & low])
    inlet = np.isin(labels, open_ids[open_ids > 0])
    stream = np.asarray(stream_points, float)[:, :2]
    d_stream = np.full(H.shape, np.inf)
    for a, b in zip(stream[:-1], stream[1:]):
        seg = b - a
        t = np.clip(((X - a[0]) * seg[0] + (Z - a[1]) * seg[1]) / max(float(seg @ seg), 1e-9), 0.0, 1.0)
        d_stream = np.minimum(d_stream, np.hypot(X - (a[0] + t * seg[0]), Z - (a[1] + t * seg[1])))
    cliff = (H >= rule["finAboveMetres"]) & (d_stream <= rule["finStreamWithinMetres"])
    d_cliff = ndimage.distance_transform_edt(~cliff) * CELL
    d_dry = ndimage.distance_transform_edt(inlet) * CELL
    window = int(round(rule["halfWidthWindowMetres"] / CELL))
    half_width = ndimage.maximum_filter(np.where(inlet, d_dry, 0.0), size=2 * window + 1)
    reach = np.minimum(rule["widenMetres"], rule["keepOpenShare"] * half_width)
    talus = np.minimum(rule["apronTopMetres"], rule["toeMetres"] + rule["grade"] * (reach - d_cliff))
    plunge = np.zeros(H.shape, bool)
    for px, pz, pr in rule["plungePools"]:
        plunge |= np.hypot(X - px, Z - pz) <= pr
    raise_ = inlet & ~F & ~plunge & (talus > H) & (d_cliff <= reach + rule["underwaterRunMetres"])
    H[raise_] = talus[raise_]
    out = h.astype(np.float64).copy()
    out[rows, cols] = H
    change = H - H0
    dry_new = raise_ & (H >= 0.0)
    return out, {"boxLocal": rule["boxLocal"], "inletCells": int(inlet.sum()), "raisedCells": int(raise_.sum()),
                 "newDryCells": int(dry_new.sum()), "newDryAreaM2": int(dry_new.sum() * CELL * CELL),
                 "maxRaiseMetres": round(float(change.max()), 2) if raise_.any() else 0.0,
                 "fillVolumeM3": round(float(change[raise_].sum() * CELL * CELL), 1),
                 "toeDistanceMetres": [round(float(reach[raise_].min()), 2), round(float(reach[raise_].max()), 2)]
                 if raise_.any() else [],
                 "finCells": int(cliff.sum()),
                 "inletCellsLeftUnder0": int((inlet & (H < 0.0)).sum())}


def gorge_box(rule: dict) -> tuple[slice, slice]:
    bx = rule["boxLocal"]
    c0 = int(math.floor((bx[0] + TRANSLATION[0] - PRODUCT_X0) / CELL))
    c1 = int(math.ceil((bx[1] + TRANSLATION[0] - PRODUCT_X0) / CELL)) + 1
    r0 = int(math.floor((bx[2] + TRANSLATION[2] - PRODUCT_Z0) / CELL))
    r1 = int(math.ceil((bx[3] + TRANSLATION[2] - PRODUCT_Z0) / CELL)) + 1
    return slice(r0, r1), slice(c0, c1)


def inland_shafts(h: np.ndarray, classes: np.ndarray, water_surface: np.ndarray, hard: np.ndarray,
                  rule: dict) -> tuple[np.ndarray, dict]:
    """Inland shafts above the sea (polish fix stage, 2026-10-02): the product's river nodes without a level became
    level 0 and their painted cells were cut down towards it, so a brook high on the island ends in a shaft tens of
    metres deep (R132 beside the castle brook: floor 16 m inside a 145-156 m rim). The inland-pocket rule only sees
    pits below the sea. Here every component of painted lake or river cells whose product level is 0 (sw8_wsurf2),
    within withinMetres of a painted water cell with a real level of minLevelMetres or more and more than
    minDepthMetres under that level, is filled to its spill height (morphological reconstruction: the lowest rim
    it would overflow), and no lower than bedBelowLevelMetres under the nearest painted level (so the brook that
    runs into it does not end over a drop), with a 1-cell Gaussian blend, cells only raised; never a protected cell, never inside the
    gorge box (the gorge rule fills its own), never in an ownerCallKeepLocal box (the north-court crevice, an open
    owner call)."""
    from scipy import ndimage

    p = rule["inlandShafts"]
    painted = (classes == 2) | (classes == 3)
    finite = np.isfinite(water_surface)
    zero = painted & finite & (water_surface == 0)
    valid = painted & finite & (water_surface >= p["minLevelMetres"])
    dist, idx = ndimage.distance_transform_edt(~valid, return_indices=True)
    near_level = water_surface[idx[0], idx[1]]
    cand = zero & ~hard & (dist * CELL <= p["withinMetres"]) & (h < near_level - p["minDepthMetres"]) & \
        (h > p["aboveMetres"])
    excluded = np.zeros(h.shape, bool)
    if "gorge" in rule:
        excluded[gorge_box(rule["gorge"])] = True
    for bx in p.get("ownerCallKeepLocal", []):
        rows, cols = gorge_box({"boxLocal": bx["boxLocal"]})
        excluded[rows, cols] = True
    cand &= ~excluded
    labels, count = ndimage.label(cand, structure=np.ones((3, 3), bool))
    out = h.astype(np.float64).copy()
    filled_mask = np.zeros(h.shape, bool)
    shafts = []
    for label in range(1, count + 1):
        cells = labels == label
        if not cells[ROW0:ROW0 + HEIGHT, COL0:COL0 + WIDTH].any():
            continue
        rows, cols = np.nonzero(cells)
        pad = p["windowPadCells"]
        r0, r1 = max(rows.min() - pad, 0), min(rows.max() + pad + 1, h.shape[0])
        c0, c1 = max(cols.min() - pad, 0), min(cols.max() + pad + 1, h.shape[1])
        win = out[r0:r1, c0:c1].copy()
        # depression filling (reconstruction by erosion): the marker starts at the ground on the window's border
        # and +inf inside, and sinks to the lowest overflow path; the shaft's depression is the part of the window
        # it raises that touches the shaft's painted cells (unpainted pit cells included), never a protected cell
        marker = np.full(win.shape, np.inf)
        marker[0, :], marker[-1, :], marker[:, 0], marker[:, -1] = win[0, :], win[-1, :], win[:, 0], win[:, -1]
        for _ in range(4 * (r1 - r0 + c1 - c0)):
            eroded = ndimage.grey_erosion(marker, footprint=np.ones((3, 3), bool), mode="nearest")
            nxt = np.maximum(win, np.minimum(marker, eroded))
            if np.array_equal(nxt, marker):
                break
            marker = nxt
        raised_here = marker > win + 0.05
        dep_labels, _ = ndimage.label(raised_here, structure=np.ones((3, 3), bool))
        keep_ids = np.unique(dep_labels[cells[r0:r1, c0:c1] & raised_here])
        depression = np.isin(dep_labels, keep_ids[keep_ids > 0]) & ~hard[r0:r1, c0:c1]
        if not depression.any():
            continue
        # the basin's floor meets the brook that runs into it: no lower than bedBelowLevelMetres under the nearest
        # painted water level (the castle brook ends at 147.2 m over a spill of 144.6 m)
        spill = np.maximum(marker, near_level[r0:r1, c0:c1] - p["bedBelowLevelMetres"])
        rise = np.where(depression, spill - win, 0.0)
        out[r0:r1, c0:c1] = np.where(depression, spill, win)
        full = np.zeros(h.shape, bool)
        full[r0:r1, c0:c1] = depression
        filled_mask |= full
        shafts.append({"paintedCells": int(cells.sum()), "filledCells": int(depression.sum()),
                       "continentX": [PRODUCT_X0 + CELL * int(cols.min()), PRODUCT_X0 + CELL * int(cols.max())],
                       "continentZ": [PRODUCT_Z0 + CELL * int(rows.min()), PRODUCT_Z0 + CELL * int(rows.max())],
                       "minMetres": round(float(win[depression].min()), 2),
                       "spillMetres": round(float(spill[depression].max()), 2),
                       "nearestLevelMetres": round(float(near_level[cells].max()), 2),
                       "maxRiseMetres": round(float(rise.max()), 2)})
    blended = ndimage.gaussian_filter(out, p["blendSigmaCells"])
    out[filled_mask] = np.maximum(out[filled_mask], blended[filled_mask])
    raised = filled_mask & (out > h + 1e-6)
    return out, {"filled": shafts, "cellsRaised": int(raised.sum()),
                 "fillVolumeM3": round(float((out - h)[raised].sum() * CELL * CELL), 1)}


def pad_holes(h: np.ndarray, hard: np.ndarray, pads: np.ndarray, rule: dict) -> tuple[np.ndarray, dict]:
    """Holes in a protected pad levelled with it (game-look fix stage, owner decision 2026-10-02: "fill the
    north-tower crevice level with its court"). Inside each boxLocal box, the cells the pad masks (compound, town,
    north-tower and lighthouse pads) enclose but do not cover, and that are not otherwise protected, are set to the
    median height of the pad cells round them. The north-court crevice is such a hole: 84 painted river cells cut
    1.7-94 m into the 87.01 m court, which the inland-shaft fill alone would leave 1-7 m proud of the court in
    places (its Gaussian blend only raises)."""
    from scipy import ndimage

    out = h.astype(np.float64).copy()
    holes_stats = []
    every = np.zeros(h.shape, bool)
    for bx in rule["boxes"]:
        rows, cols = gorge_box({"boxLocal": bx["boxLocal"]})
        box = np.zeros(h.shape, bool)
        box[rows, cols] = True
        inside = pads & box
        holes = ndimage.binary_fill_holes(inside) & ~pads & box & ~hard
        if not holes.any():
            holes_stats.append({"boxLocal": bx["boxLocal"], "cells": 0})
            continue
        rim = ndimage.binary_dilation(holes, structure=np.ones((3, 3), bool), iterations=2) & pads
        level = float(np.median(h[rim]))
        change = level - out[holes]
        out[holes] = level
        every |= holes
        r, c = np.nonzero(holes)
        holes_stats.append({"boxLocal": bx["boxLocal"], "cells": int(holes.sum()), "levelMetres": round(level, 3),
                            "beforeMetres": [round(float(h[holes].min()), 2), round(float(h[holes].max()), 2)],
                            "raisedCells": int((change > 1e-6).sum()), "loweredCells": int((change < -1e-6).sum()),
                            "fillVolumeM3": round(float(np.clip(change, 0, None).sum() * CELL * CELL), 1),
                            "cutVolumeM3": round(float(np.clip(-change, 0, None).sum() * CELL * CELL), 1),
                            "continentX": [PRODUCT_X0 + CELL * int(c.min()), PRODUCT_X0 + CELL * int(c.max())],
                            "continentZ": [PRODUCT_Z0 + CELL * int(r.min()), PRODUCT_Z0 + CELL * int(r.max())]})
    # the mask rides along (popped by terrain_arrays) so the colour conditioning recolours the levelled cells
    return out, {"holes": holes_stats, "_mask": every}


def gorge_with_release(h: np.ndarray, classes: np.ndarray, protect: np.ndarray, hard: np.ndarray, keep: np.ndarray,
                       deck: np.ndarray, water: dict, water_surface: np.ndarray, rule: dict,
                       sculpt_effective: np.ndarray, roadline: np.ndarray, pads: np.ndarray) -> tuple[np.ndarray, dict]:
    """The gorge rule with the protection released on road-corridor cells that are not road (polish fix stage,
    2026-10-02). The approved gorge cut the mesa round the R28 corridor and B12, and the corridor cells it may not
    touch were left as terrain spires up to 104 m high, 14-20 m from the B12 decks (58-66 m) and one inside the
    l12-b ellipse. A first pass finds the ground the gorge cuts; a protected cell in the gorge box is released
    when it stands more than release.aboveRoadMetres over the nearest approved road centreline (sw8_roadline2:
    the check bake's road lines; or a deck within deckWithinMetres), lies more than release.roadDistanceMetres
    from that centreline, is not compound, town or pad ground, and belongs to a connected run of such cells within
    exposedWithinCells of ground the first pass cut by more than exposedCutMetres. A second pass then runs with
    those cells released. Sculpt-indexed released cells are graded on their effective height (base plus the
    sculpt layer's delta, sw8_sculpt_eff2 minus the product base) and the delta is taken back off, so the sculpt
    layer itself is unchanged and its rebound result is the graded height."""
    from scipy import ndimage

    rel = rule["release"]
    first, first_stats = gorge(h, classes, protect, hard, keep, deck, water, water_surface, rule)
    cut1 = first - h.astype(np.float64)
    rows, cols = gorge_box(rule)
    box = np.zeros(h.shape, bool)
    box[rows, cols] = True
    finite = np.isfinite(sculpt_effective)
    delta = np.where(finite, sculpt_effective - h, 0.0)
    eff = h + delta
    deck_cells = np.isfinite(deck)
    deck_dist, deck_idx = ndimage.distance_transform_edt(~deck_cells, return_indices=True)
    deck_near = np.where(deck_dist * CELL <= rel["deckWithinMetres"], deck[deck_idx[0], deck_idx[1]], np.nan)
    ref = np.fmax(roadline[0], deck_near)
    with np.errstate(invalid="ignore"):
        tall = np.isfinite(ref) & (eff > ref + rel["aboveRoadMetres"])
    cand = box & protect & ~pads & tall & (roadline[1] > rel["roadDistanceMetres"])
    exposed = box & ~protect & (cut1 < -rel["exposedCutMetres"])
    near_exposed = ndimage.binary_dilation(exposed, structure=np.ones((3, 3), bool),
                                           iterations=rel["exposedWithinCells"])
    labels, _ = ndimage.label(cand, structure=np.ones((3, 3), bool))
    seeded = np.unique(labels[cand & near_exposed])
    released = np.isin(labels, seeded[seeded > 0])
    h_in = np.where(released, eff, h)
    second, stats = gorge(h_in, classes, protect & ~released, hard & ~released, keep, deck, water, water_surface, rule)
    out = np.where(released, second - delta, second)
    change = second - h_in
    sculpt_released = released & finite
    lr, lc = np.nonzero(released)
    stats["release"] = {
        "releasedCells": int(released.sum()), "releasedSculptIndexedCells": int(sculpt_released.sum()),
        "releasedCorridorCells": int((released & ~finite).sum()),
        "releasedCellsCut": int((released & (change < -0.05)).sum()),
        "releasedMaxCutMetres": round(float(-change[released].min()), 3) if released.any() else 0.0,
        "releasedTopBeforeMetres": round(float(eff[released].max()), 2) if released.any() else 0.0,
        "releasedTopAfterMetres": round(float(second[released].max()), 2) if released.any() else 0.0,
        "sculptIndexedEffectiveChangeMetres": [round(float(change[sculpt_released].min()), 3),
                                               round(float(change[sculpt_released].max()), 3)]
        if sculpt_released.any() else [0.0, 0.0],
        "continentX": [PRODUCT_X0 + CELL * int(lc.min()), PRODUCT_X0 + CELL * int(lc.max())] if released.any() else [],
        "continentZ": [PRODUCT_Z0 + CELL * int(lr.min()), PRODUCT_Z0 + CELL * int(lr.max())] if released.any() else [],
        "firstPassCutCells": first_stats["cutCells"]}
    return out, stats


def product_local_xz(rows: slice, cols: slice) -> tuple[np.ndarray, np.ndarray]:
    """Territory-local x, z of the product cells in rows x cols."""
    x = PRODUCT_X0 + CELL * np.arange(cols.start, cols.stop) - TRANSLATION[0]
    z = PRODUCT_Z0 + CELL * np.arange(rows.start, rows.stop) - TRANSLATION[2]
    return np.meshgrid(x, z)


def coast_band(h: np.ndarray, classes: np.ndarray, fixed: np.ndarray, rule: dict) -> tuple[np.ndarray, dict]:
    """The owner-approved coast band (polish fix plan P4a), on the product heights after the ring and pockets.

    The product clamped each painted cell on its own (sea to -0.5 m or lower, land lifted to a flat +0.5 m), so the
    painted shoreline became a 2 m staircase with white +0.5 m sheets, and under the sea the Meshy plate keeps its
    rim trench (the "moat", down to -47 m at the plate's edge). Here, from the painted shoreline:
    - sea: a shelving seabed, -(shore + grade d (1 + deepening d)) at d metres out, no deeper than floorMetres: the
      seabed itself within exactWithinMetres of the shore, a floor beyond it, so the moat and every other cell
      deeper than the profile is filled to it (the owner's decision) and the product's shallower off-plate shelf
      stays;
    - low land (under lowLandBelowMetres, within lowLandWithinMetres of the shore water: the sea and the sea-level
      creek mouths and coves joined to it): cut to a beach ramp ramp0 + rampGrade d where it stands higher, and
      lifted to floor0 + floorGrade d where it lies lower, except at a cliff foot (within cliffFootCells of ground at
      belowMetres or more); cells on the product's flat lift (productLiftMetres) take a beach slope
      ramp0 + beachGrade d;
    - a Gaussian of smoothSigmaCells over the band (smoothWithinMetres either side), leaving out cliffs (land within
      2 cells of ground at cliffMetres or more) and land at lowLandBelowMetres or more;
    - then the painted classes are re-asserted (dry at minLandMetres or more, sea at maxSeaMetres or less), so the
      coastline keeps its sign. Rivers, lakes, `fixed` cells and painted-sea cells above seaUpToMetres (the P2
      pocket fills) are never changed."""
    from scipy import ndimage

    painted_sea = classes == 0
    # the open sea: painted-sea cells at or under seaUpToMetres (the high-rim pockets the P2 fill raised are painted
    # sea too, and stay as filled)
    sea = painted_sea & (h <= rule["seaUpToMetres"])
    inland = (classes == 2) | (classes == 3)
    # shore water: the sea, and lake or river cells at sea level joined to it (creek mouths, coves)
    low_labels, _ = ndimage.label(sea | (inland & (h < rule["seaLevelWaterBelowMetres"])),
                                  structure=np.ones((3, 3), bool))
    shore_water = np.isin(low_labels, np.unique(low_labels[sea & (low_labels > 0)])) & (low_labels > 0)
    land = ~shore_water
    dl = (ndimage.distance_transform_edt(land) - 0.5) * CELL
    ds = (ndimage.distance_transform_edt(~shore_water) - 0.5) * CELL
    ds = np.where(sea, (ndimage.distance_transform_edt(sea) - 0.5) * CELL, ds)
    s = rule["seabed"]
    g = h.astype(np.float64).copy()
    profile = -(s["shoreMetres"] + s["grade"] * ds * (1.0 + s["deepening"] * ds))
    profile = np.maximum(profile, s["floorMetres"])
    seabed = sea & ~fixed
    moat_before = seabed & (g < s["floorMetres"] - 1.0)
    # within exactWithinMetres of the shore the seabed is the profile; beyond it the profile is a floor only (the moat
    # and anything else deeper is filled to it; the product's shallower off-plate shelf stays)
    exact = seabed & (ds <= s["exactWithinMetres"])
    g[exact] = profile[exact]
    g[seabed & ~exact] = np.maximum(g, profile)[seabed & ~exact]
    lw = rule["lowLand"]
    low = land & ~inland & ~painted_sea & ~fixed & (dl <= lw["withinMetres"]) & (h < lw["belowMetres"])
    # a cliff foot (within cliffFootCells of ground at belowMetres or more) keeps its height: cutting it to the
    # ramp would stand a new wall against the cliff
    foot = ndimage.maximum_filter(np.where(land & ~painted_sea, h, -1e9), size=2 * lw["cliffFootCells"] + 1) >=         lw["belowMetres"]
    ramp = lw["ramp0"] + lw["rampGrade"] * dl
    lift = lw["floor0"] + lw["floorGrade"] * dl
    shaped = low & ~foot
    g[shaped] = np.maximum(np.minimum(g, ramp), lift)[shaped]
    # the product's flat +0.5 m lift (painted land over a Meshy plate lower than that) becomes a beach slope
    lifted = low & (np.abs(h - lw["productLiftMetres"]) < 0.005)
    g[lifted] = np.minimum(lw["ramp0"] + lw["beachGrade"] * dl, ramp)[lifted]
    sm = rule["smooth"]
    tall = ndimage.maximum_filter(np.where(land, h, -1e9), size=5) >= sm["cliffMetres"]
    band = (np.where(land, dl, ds) <= sm["withinMetres"]) & ~fixed & ~inland & (h < lw["belowMetres"]) & ~tall &         (sea | (classes == 1))
    blurred = ndimage.gaussian_filter(g, sm["sigmaCells"])
    g[band] = blurred[band]
    g = np.where(classes == 1, np.maximum(g, rule["minLandMetres"]), g)
    g = np.where(sea, np.minimum(g, rule["maxSeaMetres"]), g)
    g = np.where(fixed | inland, h, g)
    change = g - h
    window = (slice(ROW0, ROW0 + HEIGHT), slice(COL0, COL0 + WIDTH))
    dry_moved = (classes == 1) & (np.abs(change) > 0.5)
    stats = {"seaCellsSet": int(seabed[window].sum()),
             "moatCellsFilled": int(moat_before[window].sum()),
             "seaCellsRaisedOver0p5m": int((sea & (change > 0.5))[window].sum()),
             "seaCellsLoweredOver0p5m": int((sea & (change < -0.5))[window].sum()),
             "seaVolumeRaisedM3": round(float((np.clip(change, 0, None) * sea)[window].sum() * CELL * CELL), 1),
             "seaVolumeLoweredM3": round(float((np.clip(-change, 0, None) * sea)[window].sum() * CELL * CELL), 1),
             "dryCellsMovedOver0p5m": int(dry_moved[window].sum()),
             "dryAreaMovedOver0p5mM2": int(dry_moved[window].sum() * CELL * CELL),
             "dryMaxLoweredMetres": round(float(-change[window][(classes == 1)[window]].min()), 3),
             "dryMaxRaisedMetres": round(float(change[window][(classes == 1)[window]].max()), 3),
             "dryVolumeCutM3": round(float((np.clip(-change, 0, None) * (classes == 1))[window].sum() * CELL * CELL), 1),
             "dryVolumeFilledM3": round(float((np.clip(change, 0, None) * (classes == 1))[window].sum() * CELL * CELL), 1),
             "smoothedCells": int(band[window].sum()), "lowLandCells": int(low[window].sum()),
             "lowLandCliffFootCellsKept": int((low & foot)[window].sum()),
             "productLiftCellsSloped": int(lifted[window].sum()),
             "countedOn": "the terrain window's vertices"}
    return g, stats


def slope_cell(rule: dict) -> float:
    return rule["slope"] * CELL


def slope_diag(rule: dict) -> float:
    return rule["slope"] * CELL * math.sqrt(2.0)


def gorge(h: np.ndarray, classes: np.ndarray, protect: np.ndarray, hard: np.ndarray, keep: np.ndarray, deck: np.ndarray,
          water: dict, water_surface: np.ndarray, rule: dict) -> tuple[np.ndarray, dict]:
    """The owner-approved clean graded gorge for the L12 outlet (polish fix plan P4b). L12 stays at its level.

    The product cut every painted lake and river cell straight down to the level of its nearest river node, so the
    outlet (R093 then R070 to cove C04) became slots 40-70 m deep in the NE mesa, stepped at 84 / 78 / 58 m, with
    fins of uncarved mesa between them, while R093 sits 2 m under the lake bed. Inside the box:
    - lake reach: R093's painted river cells (within reachWithinMetres of its line, reachFromMetres to
      reachUpToMetres high: the product's bed 2 m under the lake's) join the lake bed;
    - channel: the cells within channelHalfWidthMetres of R070 (and runOutMetres past its end, while the ground is no
      more than a metre under the floor; never more than channelFillUpToMetres under it, so the cliff into the
      sea-level water beside it stays) get one monotonic floor, from the lake bed at R070's start down to
      lipFloorMetres at the lip above the cove; past it the ground drops to the cove (the waterfall);
    - the lake and the other inland water (R075, the east pools) get a bed bedDepthMetres under their own water
      surface (sw8_wsurf2; the lake's level where the product left a river cell at level 0) where the product's
      pits lie lower, the corridor margin included as for the pocket fill (never a corridor or sculpt cell); low
      cells joined to the painted sea are sea-level water, not pits; painted water cells standing more than
      aboveSurfaceMetres over their surface are uncarved fins and are cut like land;
    - holes the product left in the outlet's painted cells beside the floor (not joined to the sea-level water)
      are filled to a bank over the nearest water;
    - inland water bed outside every authored water region of the box (waterEllipses) and outside the outlet
      stream's ribbon (stream: the river path's points [x, z, half width], its bed kept only edgeMetres inside the
      ribbon's edge; the channel's floor likewise, short of the lip) becomes ground bankAboveSurfaceMetres over its
      water, so no dry bed lies a metre under the water beside it and the ribbon's edges lie over bank;
    - a lip berm: lake, reach and channel cells at the brink of a drop (a non-water neighbour more than
      brinkDropMetres under their water surface) are raised bermAboveSurfaceMetres over it, except within
      lipWidthMetres of the lip, so the water meets a bank and spills only at the lip;
    - a cut-only slope limit of slope (rise per metre, 8-neighbour) on every cell within withinMetres of the water
      (the lake, the reach, the channel and the other inland water at minWaterMetres or more), measured from the
      water and the zone only (the sea, sea-level water and the protection never pull a cell down), never below
      bankAboveSurfaceMetres over the nearest water's surface (the water meets a bank) and never below a bank
      falling away at the same slope from what is kept, never on the
      protection P, built footprints or deck landings (keep bits 1 and 4); under a deck strip the ground is also cut
      to the deck minus deckClearanceMetres. Sea-level water (the cove, the painted river cells the product cut to
      the sea) is neither a source nor cut."""
    from scipy import ndimage

    bx = rule["boxLocal"]
    c0 = int(math.floor((bx[0] + TRANSLATION[0] - PRODUCT_X0) / CELL))
    c1 = int(math.ceil((bx[1] + TRANSLATION[0] - PRODUCT_X0) / CELL)) + 1
    r0 = int(math.floor((bx[2] + TRANSLATION[2] - PRODUCT_Z0) / CELL))
    r1 = int(math.ceil((bx[3] + TRANSLATION[2] - PRODUCT_Z0) / CELL)) + 1
    rows, cols = slice(r0, r1), slice(c0, c1)
    X, Z = product_local_xz(rows, cols)
    H = h[rows, cols].astype(np.float64).copy()
    H0 = H.copy()
    cl = classes[rows, cols]
    P = protect[rows, cols]
    HARD = hard[rows, cols]
    K = keep[rows, cols]
    D = deck[rows, cols]
    W = water_surface
    floor_min = rule["minWaterMetres"]
    features = {f["properties"]["id"]: f for f in water["features"]}

    def line(fid):
        pts = np.array(features[fid]["geometry"]["coordinates"], float)[:, :2]
        return pts - np.array([TRANSLATION[0], TRANSLATION[2]])

    def project(pts):
        """Distance to the polyline and the arc length of the nearest point, per cell."""
        best = np.full(X.shape, np.inf)
        arc = np.zeros(X.shape)
        run = 0.0
        for a, b in zip(pts[:-1], pts[1:]):
            d = b - a
            ln = float(np.hypot(*d))
            t = np.clip(((X - a[0]) * d[0] + (Z - a[1]) * d[1]) / (ln * ln), 0.0, 1.0)
            dist = np.hypot(X - (a[0] + t * d[0]), Z - (a[1] + t * d[1]))
            closer = dist < best
            best = np.where(closer, dist, best)
            arc = np.where(closer, run + t * ln, arc)
            run += ln
        return best, arc, run

    bed, level = rule["lakeBedMetres"], rule["lakeLevelMetres"]
    reach_line = line(rule["reachFeature"])
    channel_line = line(rule["channelFeature"])
    d_reach, _, _ = project(reach_line)
    reach = (cl == 2) & (d_reach <= rule["reachWithinMetres"]) & (H >= rule["reachFromMetres"]) &         (H <= rule["reachUpToMetres"])
    # the channel line, extended past its last point by runOutMetres
    tail = channel_line[-1] - channel_line[-2]
    tail /= np.hypot(*tail)
    extended = np.vstack([channel_line, channel_line[-1] + tail * rule["runOutMetres"]])
    d_ch, s_ch, total = project(extended)
    lip_s = total - rule["runOutMetres"]
    floor = bed - (bed - rule["lipFloorMetres"]) * np.clip(s_ch / lip_s, 0.0, 1.0)
    channel = (d_ch <= rule["channelHalfWidthMetres"]) & (cl != 0) & (H >= floor_min) & ~P & ~((K & 5) > 0)
    channel &= (H >= floor - rule["channelFillUpToMetres"]) & ((s_ch <= lip_s) | (H >= floor - 1.0))
    H[reach & ~P] = bed
    H[channel] = floor[channel]
    # sea-level water: low cells (under minWaterMetres) connected to the painted sea; any other low lake or river
    # cell is a product pit
    low_labels, _ = ndimage.label(H < floor_min, structure=np.ones((3, 3), bool))
    sea_level = np.isin(low_labels, np.unique(low_labels[(cl == 0) & (low_labels > 0)]))
    inland_water = ((cl == 2) | (cl == 3)) & ~sea_level
    # the lake and the other inland water sit on a bed bedDepthMetres under their own water surface: product pits
    # under them (cut to a river node's level) are filled to it, so they do not seed a crater
    surface = W[rows, cols].astype(np.float64)
    # an inland river cell whose product level is 0 (cond8's missing node level) belongs to the lake's network
    surface = np.where(np.isfinite(surface) & (surface >= floor_min), surface, level)
    d_out = np.minimum(d_reach, d_ch)
    pit = inland_water & ~reach & ~channel & ~HARD & ~((K & 5) > 0) & (H < surface - rule["bedDepthMetres"]) &         ((cl == 3) | (d_out > rule["otherWaterBeyondMetres"]))
    H[pit] = (surface - rule["bedDepthMetres"])[pit]
    # inland water bed outside every water region of the box (rule waterEllipses: the authored lake and pool
    # ellipses, [x, z, rx, rz]; and the outlet stream's ribbon) would be dry bed a metre under the water beside it:
    # it becomes ground bankAboveSurfaceMetres over that water instead
    covered = np.zeros(H.shape, bool)
    for ex, ez, erx, erz in rule["waterEllipses"]:
        covered |= ((X - ex) / erx) ** 2 + ((Z - ez) / erz) ** 2 <= 1.0
    # the outlet stream (the river path drawn down the gorge, rule stream.points [x, z, half width, surface]) keeps
    # its bed only stream.edgeMetres inside its ribbon's edge (and at least stream.minWetMetres either side of its
    # line, so the 2 m grid always holds a wet cell), so the ribbon's edges lie over bank, never over bed;
    # inside that, ground the slope limit's banks left up to aboveSurfaceMetres over the stream (between R093's
    # painted cells and R070's start) is its bed too, so the stream never runs under ground
    stream = np.array(rule["stream"]["points"], float)
    d_st, s_st, _ = project(stream[:, :2])
    stream_arc = np.r_[0.0, np.cumsum(np.hypot(np.diff(stream[:, 0]), np.diff(stream[:, 1])))]
    stream_wet = d_st <= np.maximum(np.interp(s_st, stream_arc, stream[:, 2]) - rule["stream"]["edgeMetres"],
                                    rule["stream"]["minWetMetres"])
    stream_surface = np.interp(s_st, stream_arc, stream[:, 3])
    stream_bed = stream_wet & ~channel & ~P & ~HARD & ~((K & 5) > 0) & (cl != 0) & ~sea_level & \
        (H > stream_surface - rule["bedDepthMetres"]) & (H <= stream_surface + rule["aboveSurfaceMetres"])
    H[stream_bed] = (stream_surface - rule["bedDepthMetres"])[stream_bed]
    reach |= stream_bed
    covered |= stream_wet
    bed_like = reach | pit | ((cl == 3) & inland_water & (H <= level + rule["aboveSurfaceMetres"])) |         ((cl == 2) & inland_water & (d_out > rule["otherWaterBeyondMetres"]) &
         (H <= surface + rule["aboveSurfaceMetres"]))
    dried = bed_like & ~covered & ~channel & ~HARD & ~((K & 5) > 0)
    H[dried] = (np.where(reach, level, surface) + rule["bankAboveSurfaceMetres"])[dried]
    # the channel's floor outside the stream's wet ribbon (short of the lip, where the water spills at the
    # channel's full width) is a bank over the stream's surface too
    channel_dry = channel & ~stream_wet & (s_ch <= lip_s - rule["lipWidthMetres"])
    H[channel_dry] = (floor + rule["bedDepthMetres"] + rule["bankAboveSurfaceMetres"])[channel_dry]
    channel &= ~channel_dry
    dried |= channel_dry
    reach &= ~dried
    # open edges (polish fix stage): low ground outside every water region and the stream's ribbon, in a hollow
    # that touches a water region's wet cells and lies between openEdgeFill.minDepthMetres and maxDepthMetres under
    # the lake's level, is raised to a bank bankAboveSurfaceMetres over it, so no lake edge ends in the air over it (bake_sim
    # found l12-b's and l12-a's ellipses ending over the old terrace floor at 45 m)
    open_fill = np.zeros(H.shape, bool)
    if "openEdgeFill" in rule:
        oe = rule["openEdgeFill"]
        wet_cov = covered & (H < level)
        low = ~covered & ~channel & ~P & ~HARD & ~((K & 5) > 0) & ~sea_level & (cl != 0) & \
            (H < level - oe["minDepthMetres"]) & (H > level - oe["maxDepthMetres"])
        low_labels, _ = ndimage.label(low, structure=np.ones((3, 3), bool))
        touching_water = np.unique(low_labels[low & ndimage.binary_dilation(wet_cov, structure=np.ones((3, 3), bool))])
        open_fill = np.isin(low_labels, touching_water[touching_water > 0])
        H[open_fill] = level + rule["bankAboveSurfaceMetres"]
        dried |= open_fill
    # painted lake and river cells standing more than aboveSurfaceMetres over their own surface are uncarved ground
    # (fins): not sources, the slope limit cuts them
    wet = H <= surface + rule["aboveSurfaceMetres"]
    lake = inland_water & (cl == 3) & wet
    other = inland_water & (cl == 2) & wet & (d_out > rule["otherWaterBeyondMetres"])
    seeds = lake | reach | channel | other | dried
    dist, nearest = ndimage.distance_transform_edt(~seeds, return_indices=True)
    dist *= CELL
    # holes the product cut in the outlet's painted cells beside the floor (inland water cells sunk more than
    # brinkDropMetres under the nearest water's surface, in a component that does not reach the sea-level water)
    # are filled to a bank bankAboveSurfaceMetres over that water; sunk cells joined to the sea-level water are the
    # cliff faces and stay. They are filled before the lip berm, so a hole the fill closes never reads as a brink.
    near_surface = np.where(channel, floor + rule["bedDepthMetres"], np.where(other, surface, level))[
        nearest[0], nearest[1]]
    sunk = inland_water & ~seeds & ~sea_level & (H < near_surface - rule["brinkDropMetres"]) & ~HARD & \
        ~((K & 5) > 0) & (dist <= rule["withinMetres"])
    sunk_labels, sunk_count = ndimage.label(sunk, structure=np.ones((3, 3), bool))
    touching = np.unique(sunk_labels[ndimage.binary_dilation(sea_level, structure=np.ones((3, 3), bool)) &
                                     (sunk_labels > 0)])
    holes = sunk & ~np.isin(sunk_labels, touching)
    H[holes] = (near_surface + rule["bankAboveSurfaceMetres"])[holes]
    H0 = np.where(holes, H, H0)
    # a lip berm: where the lake, the reach or the channel (short of the lip itself) stands at the brink of a drop
    # (a neighbour that is not water lying more than brinkDropMetres under its water surface: the sea-level inlet,
    # its cliff), the edge cell is raised bermAboveSurfaceMetres over that surface, so the water meets a bank there
    # and spills only at the lip
    wsurf = np.where(channel, floor + rule["bedDepthMetres"], level)
    water_now = (reach | channel | ((cl == 3) & inland_water & (H <= level + rule["aboveSurfaceMetres"]))) & ~dried
    Hn = np.pad(np.where(water_now, np.inf, H), 1, mode="edge")
    lowest = np.minimum.reduce([Hn[1:-1, :-2], Hn[1:-1, 2:], Hn[:-2, 1:-1], Hn[2:, 1:-1],
                                Hn[:-2, :-2], Hn[:-2, 2:], Hn[2:, :-2], Hn[2:, 2:]])
    berm = water_now & (lowest < wsurf - rule["brinkDropMetres"]) & ~HARD & ~((K & 5) > 0) &         ~(channel & (s_ch > lip_s - rule["lipWidthMetres"]))
    H[berm] = (wsurf + rule["bermAboveSurfaceMetres"])[berm]
    berm |= dried
    seeds = lake | reach | channel | other | berm
    dist, nearest = ndimage.distance_transform_edt(~seeds, return_indices=True)
    dist *= CELL
    # the limit never cuts a cell below its nearest water's surface plus bankAboveSurfaceMetres: the water meets a
    # bank everywhere (no new notch under the water's level, no lake edge over dry bed)
    seed_surface = np.where(channel, floor + rule["bedDepthMetres"],
                            np.where(berm, H, np.where(other, surface, level)))
    cut_floor = np.minimum(H0, seed_surface[nearest[0], nearest[1]] + rule["bankAboveSurfaceMetres"])
    zone = (dist <= rule["withinMetres"]) & ~seeds & ~P & ~((K & 5) > 0) & (cl != 0) & ~sea_level
    under_deck = zone & np.isfinite(D)
    H[under_deck] = np.minimum(H[under_deck], D[under_deck] - rule["deckClearanceMetres"])
    slope = rule["slope"]
    diag = CELL * math.sqrt(2.0)
    # the limit is measured from the water and the zone only: sea-level water, the sea, the protection and the
    # land beyond the zone never pull a cell down
    source = seeds | zone
    # and it never undermines what is kept: the ground falls away from the protection P, built footprints and deck
    # landings no steeper than the same slope (a road on the mesa rim keeps a bank instead of standing on a pillar)
    held = P | ((K & 5) > 0)
    support = np.where(held, H, -np.inf)
    for _ in range(400):
        Sp = np.pad(support, 1, mode="constant", constant_values=-np.inf)
        grown = np.maximum.reduce([
            support, Sp[1:-1, :-2] - slope_cell(rule), Sp[1:-1, 2:] - slope_cell(rule),
            Sp[:-2, 1:-1] - slope_cell(rule), Sp[2:, 1:-1] - slope_cell(rule),
            Sp[:-2, :-2] - slope_diag(rule), Sp[:-2, 2:] - slope_diag(rule),
            Sp[2:, :-2] - slope_diag(rule), Sp[2:, 2:] - slope_diag(rule)])
        if float(np.max(np.where(np.isfinite(grown), grown, 0) - np.where(np.isfinite(support), support, 0))) < 1e-4                 and np.array_equal(np.isfinite(grown), np.isfinite(support)):
            support = grown
            break
        support = grown
    cut_floor = np.maximum(cut_floor, np.minimum(H0, support))
    iterations = 0
    for iterations in range(1, 2001):
        Hp = np.pad(np.where(source, H, np.inf), 1, mode="constant", constant_values=np.inf)
        limit = np.minimum.reduce([
            Hp[1:-1, :-2] + slope * CELL, Hp[1:-1, 2:] + slope * CELL,
            Hp[:-2, 1:-1] + slope * CELL, Hp[2:, 1:-1] + slope * CELL,
            Hp[:-2, :-2] + slope * diag, Hp[:-2, 2:] + slope * diag,
            Hp[2:, :-2] + slope * diag, Hp[2:, 2:] + slope * diag])
        new = np.where(zone, np.maximum(np.minimum(H, limit), cut_floor), H)
        if float(np.max(H - new)) < 1e-4:
            H = new
            break
        H = new
    change = H - H0
    out = h.astype(np.float64).copy()
    out[rows, cols] = H
    stats = {"boxLocal": bx, "lakeReachCells": int(reach.sum()), "channelCells": int(channel.sum()),
             "channelFloorMetres": [round(float(floor[channel].max()), 3), round(float(floor[channel].min()), 3)]
             if channel.any() else [],
             "slopeZoneCells": int(zone.sum()), "underDeckCells": int(under_deck.sum()),
             "cellsHeldByBanks": int((zone & (H <= cut_floor + 1e-6) & (cut_floor > H0 - 1e9) & (H < H0 - 0.05)).sum()),
             "iterations": iterations,
             "cutCells": int((change < -0.05).sum()), "cutAreaM2": int((change < -0.05).sum() * CELL * CELL),
             "cutVolumeM3": round(float(-change[change < 0].sum() * CELL * CELL), 1),
             "maxCutMetres": round(float(-change.min()), 3),
             "pitCellsFilledToBed": int(pit.sum()),
             "lipBermCells": int((berm & ~dried).sum()),
             "bedOutsideWaterRegionsDried": int((dried & ~channel_dry).sum()),
             "channelFloorOutsideStreamBanked": int(channel_dry.sum()),
             "streamBedCellsCut": int(stream_bed.sum()),
             "outletHoleCellsFilled": int(holes.sum()),
             "openEdgeCellsFilled": int(open_fill.sum()),
             "filledCells": int((change > 0.05).sum()),
             "fillVolumeM3": round(float(change[change > 0].sum() * CELL * CELL), 1),
             "maxFillMetres": round(float(change.max()), 3),
             "hardProtectedCellsChanged": int(((np.abs(change) > 0) & HARD).sum()),
             "corridorMarginCellsFilled": int(((np.abs(change) > 0) & P & ~HARD).sum()),
             "seaLevelCells": int(sea_level.sum()),
             "keptCellsChanged": int(((np.abs(change) > 0) & ((K & 5) > 0)).sum())}
    return out, stats


def terrain_arrays(source: Path) -> tuple[np.ndarray, np.ndarray, dict]:
    final = np.load(source / "sw_island" / "heightfield_sw_2m.npy").astype(np.float32)
    pre_road = np.load(source / "sw8_ground_after_pads_before_roads_2m.npy").astype(np.float32)
    corridors = np.load(source / "work" / "sw8_corr2.npy").astype(bool)
    albedo = np.load(source / "work" / "sw8_alb2.npy")
    classes = np.load(source / "work" / "sw8_cls2.npy")
    water_surface = np.load(source / "work" / "sw8_wsurf2.npy")
    sculpt_effective = np.load(source / "work" / "sw8_sculpt_eff2.npy")
    params = json.loads((source / "work" / "sw8_condition.json").read_text(encoding="utf-8"))
    if final.shape != (1360, 1550) or pre_road.shape != final.shape or corridors.shape != final.shape or \
            albedo.shape != final.shape + (3,) or classes.shape != final.shape or \
            water_surface.shape != final.shape or sculpt_effective.shape != final.shape:
        raise SystemExit("unexpected island product shapes")
    cx = PRODUCT_X0 + CELL * np.arange(final.shape[1])
    cz = PRODUCT_Z0 + CELL * np.arange(final.shape[0])
    own = np.asarray(OWNERSHIP)
    dx = np.minimum(cx - own[:, 0].min(), own[:, 0].max() - cx)
    dz = np.minimum(cz - own[:, 1].min(), own[:, 1].max() - cz)
    sculptable = (dz[:, None] >= SCULPT_MARGIN) & (dx[None, :] >= SCULPT_MARGIN)
    product_base = np.where(corridors & sculptable, pre_road, final).astype(np.float32)
    protect, hard = protection_mask(source, corridors, params)
    keep = deck = water = None
    if "coastBand" in params["heights"] or "gorge" in params["heights"]:
        keep = np.load(source / "work" / "sw8_keep4_2.npy")
        deck = np.load(source / "work" / "sw8_deck2.npy")
        water = json.loads((source / "sw_island" / "water.json").read_text(encoding="utf-8"))
        if keep.shape != final.shape or deck.shape != final.shape:
            raise SystemExit("unexpected keep / deck shapes")
    roadline = pads = None
    if "release" in params["heights"].get("gorge", {}):
        roadline = np.load(source / "work" / "sw8_roadline2.npy")
        if roadline.shape != (2,) + final.shape:
            raise SystemExit("unexpected road-line shape")
    if "release" in params["heights"].get("gorge", {}) or "padHoles" in params["heights"]:
        pads = np.zeros(final.shape, bool)
        for name in ("sw8_compound2", "sw8_town2", "sw8_ntpad2", "sw8_lh2"):
            pads |= np.load(source / "work" / f"{name}.npy").astype(bool)
    roads = lighthouse = None
    if "padShore" in params["heights"]:
        # the shore rule releases the lighthouse pads only: the roads (sculpt-indexed cells, the corridors with their
        # margin) and the other pads stay fixed
        from scipy import ndimage
        lighthouse = np.load(source / "work" / "sw8_lh2.npy").astype(bool)
        roads = np.load(source / "work" / "sw8_sculpt_cells2.npy").astype(bool) | ndimage.binary_dilation(
            corridors, iterations=params["heights"]["protectionCorridorDilationCells"])
    base, height_stats = condition_heights(product_base, (albedo == 0).all(-1), protect, hard, params, classes, keep,
                                           deck, water, water_surface, sculpt_effective, roadline, pads, roads,
                                           lighthouse)
    adopt = height_stats.get("padHoles", {}).pop("_mask", None)
    conditioned_cells = base != product_base
    window = (slice(ROW0, ROW0 + HEIGHT), slice(COL0, COL0 + WIDTH))
    heights = np.ascontiguousarray(base[window]).astype("<f4")
    if not np.isfinite(heights).all():
        raise SystemExit("non-finite base height")
    # the sculpt layer keeps its deltas over a rebound base: where the conditioning moved a sculpt-indexed cell
    # (only the gorge's released corridor cells), its effective height moves with the base
    colour_heights = np.where(np.isfinite(sculpt_effective),
                              sculpt_effective + (base.astype(np.float64) - product_base.astype(np.float64)), base)
    conditioned, colour_stats = condition_colors(albedo, colour_heights, classes, water_surface, params,
                                                 product_base.astype(np.float64) - base.astype(np.float64), adopt)
    linear = np.clip(np.rint(conditioned[window] * 255.0), 0, 255).astype(np.uint8)
    colors = np.empty((HEIGHT, WIDTH, 4), np.uint8)
    colors[..., :3] = linear
    colors[..., 3] = 255
    stats = {
        "corridorCellsRestoredToPreRoadGround": int((corridors & sculptable)[window].sum()),
        "corridorCellsKeptGradedOutsideTheSculptLayer": int((corridors & ~sculptable)[window].sum()),
        "heightRangeMetres": [round(float(heights.min()), 3), round(float(heights.max()), 3)],
        "differenceFromProductOutsideCorridorsAndConditioningMetres":
            float(np.abs((base - final)[~corridors & ~conditioned_cells]).max()),
        "differenceFromProductOutsideTheSculptLayerAndConditioningMetres":
            float(np.abs((base - final)[~sculptable & ~conditioned_cells]).max()),
        "conditionedCellsInWindow": int(conditioned_cells[window].sum()),
        "conditionedProtectedCells": int((conditioned_cells & hard).sum()),
        "conditionedCorridorMarginCells": int((conditioned_cells & protect & ~hard).sum()),
        "conditioning": height_stats,
        "colors": colour_stats,
    }
    return heights, colors, stats


def approved_records(review_routes: Path) -> tuple[list, list]:
    source = json.loads(review_routes.read_text(encoding="utf-8"))
    features = {f["properties"]["id"]: f for f in source["features"]}
    routes, decks = [], []
    for identity in APPROVED_ROUTES + APPROVED_DECKS:
        feature = features[identity]
        properties = clean(feature["properties"])
        polyline = [[round(x / 3.0, 2), round(z / 3.0, 2)] for x, z in feature["geometry"]["coordinates"]]
        record = {"id": identity, "type": properties["type"], "approvedPolyline": polyline,
                  "studyLengthMetres24km": properties.get("length_m")}
        if identity.startswith("R"):
            record["widthMetres"] = 6.0 if properties["type"] == "road_inferred" else 8.0
            routes.append(record)
        else:
            record["widthMetres"] = {"bridge": 10.0, "causeway": 12.0, "pier": 8.0}[properties["type"]]
            record["source"] = properties.get("source")
            decks.append(record)
    return routes, decks


# Owner decisions the plan records (2026-10-01/02; review/island_content_plan.md s. 5: "accept all recommendations").
DECISIONS = [
    "D2a (owner 2026-10-02): The Tollholms (tollholms) is the second map: the SE islet with the village Tollholm, "
    "Ringholm (the east islet east of x 2437) and the outer east pier with the Toll Tower, B15 and the N14 ferry berth",
    "D2b (owner 2026-10-02): sw_isle's window moved 30 m north to z 6221-8259 so it owns the north beach; its served "
    "origin is (1023, 993)",
    "D2c (owner 2026-10-02): The Gull Skerries (gull_skerries) is a third map: the south tip, its two islets and the "
    "west cliff strip",
    "R42 reroute (owner 2026-10-02): B24 re-levelled to 2.5 m, the knob quay QK1/QK2 and seam-mole-knob in sw_isle; "
    "r42-strand (566 m) from the mole to Tollholm square in tollholms; the approved R42 middle kept as r42-overlook",
    "B25 legs (owner 2026-10-02): the harbour legs run 18-20 m west of the drawn line (x 2423) so the harbour stays in "
    "sw_isle; seam-mole-pier joins it to tollholms' tower pier",
    "seam moles (owner 2026-10-02): seam-mole-knob and seam-mole-pier, each a Set terrain patch declared identically "
    "in sw_isle and tollholms",
    "L21 (owner default 2026-10-01; talus owner 2026-10-02): a sea inlet (below sea level, the sea plane fills it; no "
    "water region), with a fill-only talus at grade 2.0 against its vertical walls in tollholms' sculpt layer",
    "landing (owner 2026-10-02): the castle-town plaza is the arrival, #beam and respawn hub",
    "hamlets (owner default 2026-10-01): both stay",
    "names (owner 2026-10-02): The Tollholms, Tollholm, Ringholm, Spindle Hill, the Toll Tower, The Gull Skerries",
    "exit ferry (owner 2026-10-02): the N10 quay ship in sw_isle (runtime-ferry-n10) is the new-player exit, to "
    "Crownwater until the v2 mainland exists; tollholms' th-ferry-berth-east waits for the mainland",
]
OPEN_DECISIONS = [
    "Spindle Hill summit path (r42-cone-way, tollholms): later (owner 2026-10-02)",
    "the home migration (landing, #beam and respawn on the server) needs the owner's explicit go",
    "a future mainland map borders sw_isle's north-east corner (a mainland sliver lies inside sw_isle's window) and "
    "tollholms' strait edge",
]
FEATURE_NOTES = {
    "R32": "cut at the Ringholm seam: sw_isle's r32-1 ends at x 2436, tollholms' r32-east continues 54 m to the "
           "Ringholm court (2471, 92.2, 6851)",
    "R42": "rerouted (owner 2026-10-02): the drawn cliff route over the knob is replaced by B24 at 2.5 m, the knob "
           "quay and seam-mole-knob (sw_isle) and r42-strand (tollholms); the drawn middle is kept as r42-overlook; its "
           "Spindle Hill end (r42-cone-way) is later",
    "B15": "in tollholms (th-b15, 2.5 m) from the Toll Tower platform",
    "B24": "re-levelled flat at 2.5 m; it ends on the knob quay (sw_isle)",
    "B25": "the harbour (arms and legs at x 2423) stays in sw_isle; the drawn spine east of x 2437 is dropped; the "
           "tower pier (th-pier-north/-south) is tollholms'",
}
OWNERSHIP_NOTES = {
    "sw_isle": "recipe decision D2: the main island is 2,080 x 2,334 m, larger than one 2,048-tile map; this is the "
               "largest window over it, moved 30 m north by D2b so it owns the north beach. East of x 2437 is "
               "tollholms', south of z 8259 and west of x 399 gull_skerries'",
    "tollholms": "D2a: the SE islet, Ringholm and the outer east pier; the west edge is sw_isle's x 2437, the "
                 "north-east edge the midline of the strait to the mainland (narrowest 111.6 m at (2913, 6833))",
    "gull_skerries": "D2c: the south tip, islet 8 and the west cliff strip; an L round sw_isle's south-west corner",
}


def owner_of(x: float, z: float) -> str | None:
    from continent_v2_territories import classify

    for record in TERRITORIES:
        if classify(x, z, record["ownership"]) > 0:
            return record["id"]
    return None


def territory_runs(polyline: list) -> list:
    """Contiguous runs of polyline points by the territory that owns them (None: no map, open sea)."""
    runs = []
    for index, (x, z) in enumerate(polyline):
        owner = owner_of(x, z)
        if runs and runs[-1]["territory"] == owner:
            runs[-1]["points"][1] = index
        else:
            runs.append({"territory": owner, "points": [index, index]})
    return runs


def plan_document(args, outputs: dict, source_manifest_sha: str) -> dict:
    routes, decks = approved_records(args.approved_routes)
    for record in routes + decks:
        record["byTerritory"] = territory_runs(record["approvedPolyline"])
        if record["id"] in FEATURE_NOTES:
            record["note"] = FEATURE_NOTES[record["id"]]
    water = json.loads((args.source_data / "sw_island" / "water.json").read_text(encoding="utf-8"))
    landmarks = json.loads((args.source_data / "sw_island" / "landmarks.json").read_text(encoding="utf-8"))
    lakes = [clean(f) for f in water["features"] if f["properties"]["id"] in ("L12", "L21")]
    for lake in lakes:
        ring = np.asarray(lake["geometry"]["coordinates"][0], float)
        lake["properties"]["territory"] = owner_of(*ring[:-1].mean(0))
        if lake["properties"]["id"] == "L21":
            lake["properties"]["decision"] = ("sea inlet (owner default 2026-10-01): below sea level, the sea plane "
                                              "fills it and no water region is drawn; a fill-only talus at grade 2.0 "
                                              "against its walls (owner 2026-10-02)")
    streams = [clean(f) for f in water["features"] if f["properties"].get("kind") == "river"]
    rehomed = {"east_pier_tower": "landmark-th-east-pier-tower", "se_islet_village": "landmark-th-tollholm",
               "east_islet": "landmark-th-ringholm"}
    marks = clean(landmarks["landmarks"])
    for mark in marks:
        mark["territory"] = owner_of(mark["x"], mark["z"])
        if mark["id"] in rehomed:
            mark["marker"] = rehomed[mark["id"]]
    territories = []
    for record in TERRITORIES:
        out = outputs[record["id"]]
        row0, col0, rows, cols = crop_window(record)
        terrain = {"origin": terrain_origin(record), "cellMetres": CELL, "vertices": [cols, rows],
                   "baseHeightsSha256": out["heightsSha"], "baseColorsSha256": out["colorsSha"]}
        if record["crop"]:
            terrain["cropOf"] = {"territory": REGION_ID, "row0": row0, "col0": col0, "rows": rows, "cols": cols}
        territories.append({
            "id": record["id"],
            "label": record["label"],
            "role": record["role"],
            "translation": record["translation"],
            "ownershipPolygon": record["ownership"],
            "ownershipNote": OWNERSHIP_NOTES[record["id"]],
            "server": out["server"],
            "terrain": terrain,
            "scenePath": f"godot-client/world_authoring/regions/{record['id']}/{record['id']}.tscn",
        })
    return {
        "schema": PLAN_SCHEMA,
        "name": "Continent v2: Isles of Enchantment at 8 km",
        "status": "draft: the south-west island group in three maps (sw_isle built; tollholms and gull_skerries "
                  "bootstrapped); the rest of the continent not yet planned",
        "frame": {
            "bounds": [0.0, 0.0, EXTENT[0], EXTENT[1]],
            "units": "metres",
            "axes": "x east, z south, y up; origin = north-west corner of the Meshy model bounds",
            "metresPerModelUnit": U_M,
            "seaLevel": 0.0,
            "seaModelY": SEA_MODEL_Y,
        },
        "vertical": dict(VERTICAL, curve="h = A ln(1 + u/u0) for u >= 0, h = (A/u0) u below sea; "
                                             "u = (model Y - sea model Y) x metresPerModelUnit"),
        "sources": {
            "meshyGlb": {"name": args.meshy_glb.name, "sha256": sha_file(args.meshy_glb)},
            "concept": {"name": args.concept.name, "sha256": sha_file(args.concept)},
            "approvedRoutes": {"path": "work-output/continent-v2/review/routes.json",
                               "sha256": sha_file(args.approved_routes),
                               "note": "extracted at the 24 km study scale; coordinates here are x 1/3"},
            "sourceData": {"path": "work-output/continent-v2/source-data/source-manifest.json",
                           "sha256": source_manifest_sha},
            "adjacentMapDesign": {"path": "work-output/continent-v2/review/adjacent_map_design.md"},
        },
        "territories": territories,
        "seams": {
            "rule": "decks never cross a border; every crossing is on land: an open land seam, or a seam mole (a "
                    "rectangular Set terrain patch declared identically in both scenes). The shared vertices (each "
                    "side's owned vertices plus one ring) keep the same base bytes (crops of one array), no sculpt "
                    "delta and the same patches on both sides; godot-client/tools/continent_v2_territories.py checks it",
            "moles": MOLES,
            "openSeams": OPEN_SEAMS,
        },
        "approvedRoutes": routes,
        "approvedDecks": decks,
        "approval": "owner, 2026-10-01: R26-R33, R41, R42, B12-B15, B22-B25 approved as drawn; 2026-10-02: the R42 "
                    "reroute and the B25 leg shift (see notes)",
        "water": {"seaLevel": 0.0, "lakes": lakes, "streams": streams,
                  "note": "the sea is the 0 m level of the base; sea channels and coves are terrain below it"},
        "landmarks": marks,
        "decisions": DECISIONS,
        "openDecisions": OPEN_DECISIONS,
    }


def gd_value(value) -> str:
    """Godot's text form of a JSON-like value (dictionary keys sorted, as the editor's saves leave them here)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return gd(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(gd_value(item) for item in value) + "]"
    if isinstance(value, dict):
        if not value:
            return "{}"
        return "{\n" + ",\n".join(f"{json.dumps(key)}: {gd_value(value[key])}" for key in sorted(value)) + "\n}"
    raise TypeError(value)


def marker_y(territory: dict, heights: np.ndarray, x: float, y, z: float) -> float:
    """The marker's height: as given, or the base height at its vertex (it must lie on one)."""
    if y is not None:
        return float(y)
    fx, fz = first_vertex(territory)
    col, row = (x - fx) / CELL, (z - fz) / CELL
    if col != int(col) or row != int(row):
        raise SystemExit(f"{territory['id']}: marker at ({x}, {z}) is not on a terrain vertex")
    return round(float(heights[int(row), int(col)]), 3)


def scene_text(territory: dict, server: dict, polygon_sha: str, heights: np.ndarray, plaza_height: float) -> str:
    """The first-bootstrap scene. sw_isle's carries the arrival spawn on the plaza; the other territories have no
    default spawn, a territory-hub runtime point, their landmark and runtime markers and, where they border a seam
    mole, its patch."""
    region = territory["id"]
    translation = territory["translation"]
    origin = terrain_origin(territory)
    row0, col0, rows, cols = crop_window(territory)
    patches = territory.get("patches", [])
    lines = [
        "[gd_scene format=3]",
        "",
        '[ext_resource type="Script" path="res://src/dev/map_authoring_region/region_control.gd" id="region"]',
        '[ext_resource type="Script" path="res://src/dev/map_authoring_region/terrain_control.gd" id="terrain"]',
        '[ext_resource type="Script" path="res://src/dev/map_authoring_region/gameplay_marker.gd" id="marker"]',
        '[ext_resource type="Script" path="res://src/dev/map_authoring_pilot/style/map_authoring_surface.gd" id="surface"]',
        '[ext_resource type="Texture2D" path="res://src/dev/map_authoring_pilot/style/textures/ground-normal.png" id="ground_normal"]',
        '[ext_resource type="Texture2D" path="res://src/dev/map_authoring_pilot/style/textures/terrain-detail-luma.png" id="ground_detail"]',
        '[ext_resource type="Texture2D" path="res://src/dev/map_authoring_pilot/style/textures/terrain-detail-normal.png" id="ground_detail_normal"]',
    ]
    if patches:
        lines.append('[ext_resource type="Script" path="res://src/dev/map_authoring_region/terrain_patch.gd" id="patch"]')
    lines += [
        "",
        # The base surface lives in the scene (local to scene, as the editor saves it): a separate .tres was
        # inlined by the first editor save and left behind unreferenced. The Meshy colours are vertex colours, one
        # per 2 m; a luminance-only detail tile and its relief's normal map (6 m repeat on the 0.17 preview UV, the
        # game-look fix stage's second recipe, editor-pass/polish/g4/make_ground_detail.py) add ground texture at
        # the game camera, with linear-filtered anisotropic mipmaps (polish fix plan P3b).
        '[sub_resource type="StandardMaterial3D" id="StandardMaterial3D_meshy"]',
        "cull_mode = 2",
        "vertex_color_use_as_albedo = true",
        'albedo_texture = ExtResource("ground_detail")',
        "roughness = 1.0",
        "normal_enabled = true",
        "normal_scale = 0.8",
        'normal_texture = ExtResource("ground_detail_normal")',
        "uv1_scale = Vector3(0.98039216, 0.98039216, 1)",
        "texture_filter = 5",
        "",
        '[sub_resource type="Resource" id="Resource_ground"]',
        "resource_local_to_scene = true",
        'script = ExtResource("surface")',
        'texture_preset = "Custom"',
        "rotation_degrees = 0.0",
        'source_material = SubResource("StandardMaterial3D_meshy")',
        "",
        f'[node name="{territory["root"]}" type="Node3D" groups=["map_authoring_region"]]',
        'script = ExtResource("region")',
        f'region_id = "{region}"',
        f"continent_translation = Vector3({gd(translation[0])}, {gd(translation[1])}, {gd(translation[2])})",
        f"server_origin = Vector2i({server['origin'][0]}, {server['origin'][1]})",
        f"server_cells = Vector2i({server['cells'][0]}, {server['cells'][1]})",
        f"collision_origin_metres = Vector2({gd(server['collisionOriginMetres'][0])}, {gd(server['collisionOriginMetres'][1])})",
        f'ownership_polygon_sha256 = "{polygon_sha}"',
        f'export_directory = "res://../eloria-assets/maps/continent-v2/{region}/authoring"',
        "",
        '[node name="Terrain" type="Node3D" parent="."]',
        'script = ExtResource("terrain")',
        f"origin = Vector2({gd(origin[0])}, {gd(origin[1])})",
        f"grid_size = Vector2i({cols}, {rows})",
        f'base_heights_path = "res://world_authoring/regions/{region}/base-heights.f32le"',
        f'base_colors_path = "res://world_authoring/regions/{region}/base-colors.rgba8"',
        'base_surface = SubResource("Resource_ground")',
        "preview_uv_metres_inverse = 0.17",
        "",
        '[node name="Patches" type="Node3D" parent="Terrain"]',
        "",
    ]
    for patch_id in patches:
        mole = MOLE[patch_id]
        centre = ((mole["x"][0] + mole["x"][1]) / 2 - translation[0], (mole["z"][0] + mole["z"][1]) / 2 - translation[2])
        lines += [f'[node name="{patch_id}" type="Marker3D" parent="Terrain/Patches"]',
                  f"transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, {gd(centre[0])}, {gd(mole['heightMetres'])}, "
                  f"{gd(centre[1])})",
                  'script = ExtResource("patch")',
                  f'patch_id = "{patch_id}"',
                  "shape = 1",
                  "operation = 1",
                  f"size = Vector2({gd(mole['x'][1] - mole['x'][0])}, {gd(mole['z'][1] - mole['z'][0])})",
                  "feather = 0.0",
                  ""]
    lines += [
        '[node name="Ground" type="Node3D" parent="."]',
        "",
        '[node name="Regions" type="Node3D" parent="Ground"]',
        "",
    ]
    for name in ["Roads", "Rivers", "WaterRegions", "Bridges", "AuthoredAssets", "Gameplay"]:
        lines += [f'[node name="{name}" type="Node3D" parent="."]', ""]
    lines += ['[node name="Spawns" type="Node3D" parent="Gameplay"]', ""]
    if not territory["crop"]:
        spawn = (PLAZA[0] - translation[0], plaza_height, PLAZA[1] - translation[2])
        facing = np.array([KEEP[0] - PLAZA[0], 0.0, KEEP[1] - PLAZA[1]])
        facing /= np.linalg.norm(facing)
        lines += ['[node name="sw-isle-arrival" type="Marker3D" parent="Gameplay/Spawns"]',
                  f"transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, {gd(spawn[0])}, {gd(round(spawn[1], 3))}, {gd(spawn[2])})",
                  "gizmo_extents = 0.8",
                  'script = ExtResource("marker")',
                  'record_id = "sw-isle-arrival"',
                  'kind = "spawn"',
                  'label = "Castle-town plaza (arrival)"',
                  "default_spawn = true",
                  f"facing = Vector3({gd(round(facing[0], 6))}, 0, {gd(round(facing[2], 6))})",
                  "extras = {",
                  '"note": "proposed landing / #beam / respawn hub on the castle-town plaza (owner to confirm)"',
                  "}", ""]
    for name in ["Portals", "Interactives", "Landmarks", "Harvestables", "NpcMarkers", "AmbientPopulation",
                 "RuntimePoints"]:
        lines += [f'[node name="{name}" type="Node3D" parent="Gameplay"]', ""]
    lines += ['[node name="TerritoryPoints" type="Node3D" parent="Gameplay/RuntimePoints"]', ""]
    from continent_v2_territories import classify

    for marker in territory.get("markers", []):
        x, y, z = marker["at"]
        y = marker_y(territory, heights, x, y, z)
        extras = dict(marker.get("extras", {}))
        extras["insideOwnership"] = bool(classify(x, z, territory["ownership"]) == 1)
        if not extras["insideOwnership"]:
            raise SystemExit(f"{region}: marker {marker['id']} is not inside the ownership polygon")
        lines += [f'[node name="{marker["id"]}" type="Marker3D" parent="Gameplay/{marker["parent"]}"]',
                  f"transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, {gd(round(x - translation[0], 6))}, "
                  f"{gd(round(y, 6))}, {gd(round(z - translation[2], 6))})",
                  "gizmo_extents = 0.8",
                  'script = ExtResource("marker")',
                  f'record_id = "{marker["id"]}"']
        if marker["kind"] != "landmark":
            lines.append(f'kind = "{marker["kind"]}"')
        lines += [f"label = {json.dumps(marker['label'], ensure_ascii=False)}",
                  f"extras = {gd_value(extras)}", ""]
    lines += ['[node name="GeneratedPreview" type="Node3D" parent="."]', ""]
    return "\n".join(lines)


def transform_text(basis: np.ndarray, origin: np.ndarray) -> str:
    """Godot Transform3D text: the basis matrix row by row (its columns are the axes), then the origin."""
    values = [basis[0, 0], basis[0, 1], basis[0, 2], basis[1, 0], basis[1, 1], basis[1, 2],
              basis[2, 0], basis[2, 1], basis[2, 2], origin[0], origin[1], origin[2]]
    return "Transform3D(" + ", ".join(gd(round(float(v), 6)) for v in values) + ")"


VIEWER_HEAD = """[sub_resource type="ProceduralSkyMaterial" id="ProceduralSkyMaterial_view"]
sky_top_color = Color(0.3, 0.5, 0.76, 1)
sky_horizon_color = Color(0.74, 0.8, 0.84, 1)
ground_bottom_color = Color(0.18, 0.26, 0.3, 1)
ground_horizon_color = Color(0.62, 0.68, 0.7, 1)

[sub_resource type="Sky" id="Sky_view"]
sky_material = SubResource("ProceduralSkyMaterial_view")

[sub_resource type="Environment" id="Environment_view"]
background_mode = 2
sky = SubResource("Sky_view")
ambient_light_source = 3
ambient_light_energy = 0.55
tonemap_mode = 2
tonemap_exposure = 0.9
fog_enabled = true
fog_light_color = Color(0.74, 0.79, 0.82, 1)
fog_density = 0.000035
fog_sky_affect = 0.2

[sub_resource type="StandardMaterial3D" id="StandardMaterial3D_sea"]
albedo_texture = ExtResource("sea_tint")
metallic_specular = 0.25
roughness = 0.55
uv1_scale = Vector3({uv_scale_x}, {uv_scale_y}, 1)
uv1_offset = Vector3({uv_offset_x}, {uv_offset_y}, 0)
texture_repeat = false

[sub_resource type="StandardMaterial3D" id="StandardMaterial3D_sea_qa"]
transparency = 1
albedo_color = Color(0.07, 0.25, 0.32, 0.86)
metallic_specular = 0.25
roughness = 0.55

[sub_resource type="StandardMaterial3D" id="StandardMaterial3D_seabed"]
albedo_color = Color(0.05, 0.16, 0.21, 1)
roughness = 1.0

[sub_resource type="PlaneMesh" id="PlaneMesh_seabed"]
material = SubResource("StandardMaterial3D_seabed")
size = Vector2(20000, 20000)

[sub_resource type="PlaneMesh" id="PlaneMesh_sea"]
material = SubResource("StandardMaterial3D_sea")
size = Vector2(20000, 20000)

[sub_resource type="PlaneMesh" id="PlaneMesh_sea_qa"]
material = SubResource("StandardMaterial3D_sea_qa")
size = Vector2(20000, 20000)

[node name="{root}" type="Node3D"]

[node name="WorldEnvironment" type="WorldEnvironment" parent="."]
environment = SubResource("Environment_view")

[node name="Sun" type="DirectionalLight3D" parent="."]
transform = {sun}
light_color = Color(1, 0.96, 0.88, 1)
light_energy = 1.2
shadow_enabled = true
directional_shadow_max_distance = 1800.0

[node name="Sea" type="MeshInstance3D" parent="."]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, {sea_x}, 0, {sea_z})
cast_shadow = 0
mesh = SubResource("PlaneMesh_sea")

[node name="SeaTranslucentQA" type="MeshInstance3D" parent="."]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, {sea_x}, 0, {sea_z})
visible = false
cast_shadow = 0
mesh = SubResource("PlaneMesh_sea_qa")

[node name="Seabed" type="MeshInstance3D" parent="."]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, {sea_x}, -48, {sea_z})
cast_shadow = 0
mesh = SubResource("PlaneMesh_seabed")
"""


def look_at(eye: np.ndarray, target: np.ndarray) -> str:
    forward = target - eye
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, [0.0, 1.0, 0.0])
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    return transform_text(np.stack([right, up, -forward], axis=1), eye)  # columns x, y, z


def sun_text() -> str:
    # Sun from the north-west (the cartographic hillshade direction), about 48 degrees up.
    travel = np.array([0.5, -0.78, 0.42])
    travel /= np.linalg.norm(travel)
    sun_right = np.cross(travel, [0.0, 1.0, 0.0])
    sun_right /= np.linalg.norm(sun_right)
    sun_up = np.cross(sun_right, travel)
    return transform_text(np.stack([sun_right, sun_up, -travel], axis=1), np.array([0.0, 400.0, 0.0]))


def sea_centre(territory: dict) -> tuple[float, float]:
    """Continent centre of a viewer's sea plane: the island group's for sw_isle (as slice 1 placed it), the terrain
    crop's for the others."""
    if not territory["crop"]:
        return (358 + 3128) / 2, (6222 + 8618) / 2
    fx, fz = first_vertex(territory)
    _, _, rows, cols = crop_window(territory)
    return fx + CELL * (cols - 1) / 2, fz + CELL * (rows - 1) / 2


def viewer_head(territory: dict, root: str, frame_translation: list) -> str:
    """Resources and the sky, sun and sea nodes of a viewer wrapper, in the frame of `frame_translation`."""
    uv_scale, uv_offset = sea_uv(territory)
    cx, cz = sea_centre(territory)
    return VIEWER_HEAD.format(uv_scale_x=gd(uv_scale[0]), uv_scale_y=gd(uv_scale[1]), uv_offset_x=gd(uv_offset[0]),
                              uv_offset_y=gd(uv_offset[1]), root=root, sun=sun_text(),
                              sea_x=gd(cx - frame_translation[0]), sea_z=gd(cz - frame_translation[2]))


def viewer_text(territory: dict, target_height: float) -> str:
    """The owner's viewer wrapper. The sea is opaque, as the game's continent_water shader draws it (polish fix plan
    P3c): the old translucent sea (alpha 0.86) showed the product's underwater shelves and skirts that no player
    sees. SeaTranslucentQA keeps that sea, hidden, for seabed QA captures (swap the two nodes' visibility). The sea
    samples the territory's sea tint (sea_tint_png): turquoise shallows fading to navy by depth (polish visual D20).
    The camera bookmark looks at the castle (sw_isle) or the territory's hub from 900 m south-east, 520 m up."""
    viewer = territory["viewer"]
    translation = territory["translation"]
    if territory["crop"]:
        target = np.array([viewer["target"][0] - translation[0], target_height, viewer["target"][2] - translation[2]])
    else:
        target = np.array([KEEP[0] - translation[0], target_height, KEEP[1] - translation[2]])
    camera = look_at(target + np.array([640.0, 520.0, 640.0]), target)
    region = territory["id"]
    return (f'[gd_scene format=3]\n\n'
            f'[ext_resource type="PackedScene" path="res://world_authoring/regions/{region}/{region}.tscn" id="island"]\n'
            f'[ext_resource type="Texture2D" path="res://world_authoring/continent-v2/viewer/{viewer["seaTint"]}" '
            f'id="sea_tint"]\n\n'
            + viewer_head(territory, viewer["root"], translation) +
            f'\n[node name="{territory["root"]}" parent="." instance=ExtResource("island")]\n\n'
            f'[node name="{viewer["bookmark"]}" type="Camera3D" parent="."]\n'
            f"transform = {camera}\nfov = 50.0\nfar = 9000.0\n")


def isles_viewer_text() -> str:
    """All three territories in sw_isle's frame, with the group's sea. sw_isle's terrain grid covers the whole group
    and the other two are byte crops of its base, so each map's preview is clipped (terrain_control's viewer-only
    preview_clip_inside / preview_clip_outside, continent polygons): a cropped map draws only the cells inside its
    own ownership polygon, with its own sculpt, patches and ground regions, and sw_isle draws every other cell of the
    grid (its own land and the sea round the group). Polygon vertices lie on the vertex lattice, so every cell is
    wholly one map's and the shared border vertices (bit-identical) close the seams. Review 2026-10-03: with the
    neighbours' previews switched off, their pieces stood on sw_isle's unedited copy of their ground."""
    group = TERRITORY[REGION_ID]
    target = np.array([(358 + 3128) / 2 - TRANSLATION[0], 0.0, (6222 + 8618) / 2 - TRANSLATION[2]])
    camera = look_at(target + np.array([1500.0, 2300.0, 1700.0]), target)
    lines = ['[gd_scene format=3]', '']
    for record in TERRITORIES:
        lines.append(f'[ext_resource type="PackedScene" path="res://world_authoring/regions/{record["id"]}/'
                     f'{record["id"]}.tscn" id="{record["id"]}"]')
    lines.append('[ext_resource type="Texture2D" path="res://world_authoring/continent-v2/viewer/sea-tint.png" '
                 'id="sea_tint"]')
    text = "\n".join(lines) + "\n\n" + viewer_head(group, "IslesView", TRANSLATION) + "\n"
    for record in TERRITORIES:
        offset = [record["translation"][i] - TRANSLATION[i] for i in range(3)]
        text += f'[node name="{record["root"]}" parent="." instance=ExtResource("{record["id"]}")]\n'
        if any(offset):
            text += (f"transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, {gd(offset[0])}, {gd(offset[1])}, "
                     f"{gd(offset[2])})\n")
        text += "\n"
    def polygon(record: dict) -> str:
        return "PackedVector2Array(" + ", ".join(f"{gd(x)}, {gd(z)}" for x, z in record["ownership"]) + ")"

    crops = [record for record in TERRITORIES if record["crop"]]
    text += (f'[node name="Terrain" parent="{group["root"]}"]\n'
             f'preview_clip_outside = Array[PackedVector2Array]([{", ".join(polygon(r) for r in crops)}])\n\n')
    for record in crops:
        text += f'[node name="Terrain" parent="{record["root"]}"]\npreview_clip_inside = {polygon(record)}\n\n'
    text += (f'[node name="IslesBookmark" type="Camera3D" parent="."]\n'
             f"transform = {camera}\nfov = 50.0\nfar = 9000.0\n")
    for record in TERRITORIES:
        text += f'\n[editable path="{record["root"]}"]\n'
    return text


SEA_TINT = {"shallowSrgb": (0.27, 0.62, 0.6), "midSrgb": (0.13, 0.42, 0.47), "deepSrgb": (0.07, 0.25, 0.32),
            "midDepthMetres": 3.0, "deepDepthMetres": 14.0, "closeCells": 15, "blurCells": 4.0}


def sea_tint_rgb(heights: np.ndarray) -> np.ndarray:
    """The viewer sea's sRGB colour per vertex of the group grid (polish visual D20): turquoise over the shallows,
    teal at SEA_TINT midDepthMetres, the old opaque navy from deepDepthMetres down (the depth is the conditioned base
    under the sea surface at 0 m, trenches closed and blurred; land vertices take the shallow colour, the terrain
    hides them). Computed once on the group grid; a cropped territory's tint is the same pixels."""
    from scipy import ndimage

    # narrow seabed trenches (the deck strips and built footprints the coast band kept, the off-plate steps) are
    # closed first, so the tint follows the shelf, not the trenches; then a blur of blurCells
    closed = ndimage.grey_closing(heights.astype(np.float64), size=(SEA_TINT["closeCells"], SEA_TINT["closeCells"]))
    depth = ndimage.gaussian_filter(np.clip(-closed, 0.0, None), SEA_TINT["blurCells"])
    shallow, mid, deep = (np.asarray(SEA_TINT[k], np.float64) for k in ("shallowSrgb", "midSrgb", "deepSrgb"))
    t1 = np.clip(depth / SEA_TINT["midDepthMetres"], 0.0, 1.0)[..., None]
    t2 = np.clip((depth - SEA_TINT["midDepthMetres"]) /
                 (SEA_TINT["deepDepthMetres"] - SEA_TINT["midDepthMetres"]), 0.0, 1.0)[..., None]
    return np.where(depth[..., None] <= SEA_TINT["midDepthMetres"], shallow * (1 - t1) + mid * t1,
                    mid * (1 - t2) + deep * t2)


def sea_tint_png(rgb: np.ndarray) -> bytes:
    """An sRGB PNG (zlib only) of a sea tint. The border pixels are deep navy, which the material's clamp continues
    past the grid."""
    import struct
    import zlib

    rgb = rgb.copy()
    deep = np.asarray(SEA_TINT["deepSrgb"], np.float64)
    rgb[0, :], rgb[-1, :], rgb[:, 0], rgb[:, -1] = deep, deep, deep, deep
    pixels = np.clip(np.rint(rgb * 255.0), 0, 255).astype(np.uint8)
    raw = b"".join(b"\x00" + row.tobytes() for row in pixels)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", pixels.shape[1], pixels.shape[0], 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 9)) +
            chunk(b"IEND", b""))


def sea_uv(territory: dict) -> tuple[tuple[float, float], tuple[float, float]]:
    """uv1 scale and offset that map a viewer Sea plane (20,000 m, centred on sea_centre; PlaneMesh UV u along +x,
    v along +z) onto the territory's terrain vertex lattice (its sea tint's pixels)."""
    centre = sea_centre(territory)
    first = first_vertex(territory)
    _, _, rows, cols = crop_window(territory)
    span = (CELL * cols, CELL * rows)
    scale = (20000.0 / span[0], 20000.0 / span[1])
    offset = ((centre[0] - 10000.0 - first[0] + CELL / 2) / span[0], (centre[1] - 10000.0 - first[1] + CELL / 2) / span[1])
    return scale, offset


def published_manifest_resource(region: str) -> str:
    """The territory's published package (`_continent_v2/publish_client.py` writes it; the registry row names it)."""
    return f"res://../eloria-assets/maps/continent-v2/{region}/client/world.json"


def catalog_text() -> str:
    # entries sorted by label: the composer's catalog loader (authoring_catalog.load_catalog) refuses any other order,
    # so the client publisher could not read the catalog once it held three maps (task A3).
    # manifestPath is this tool's stub (frame, ownership, environment): the territory catalog and the composer read the
    # territory from it. publishedManifestPath is the client package: the editor's walker, published walk overlay and
    # published minimap read the served grid, collision and minimap from it (serve plan CV9), since the stub never
    # carries them. Legacy catalog entries have no publishedManifestPath: their manifest is their package.
    return json_text({"schema": "eloria-map-authoring-territories-v1", "entries": [{
        "id": record["id"], "label": record["label"],
        "manifestPath": f"res://../eloria-assets/maps/continent-v2/{record['id']}/world.json",
        "publishedManifestPath": published_manifest_resource(record["id"]),
        "scenePath": f"res://world_authoring/regions/{record['id']}/{record['id']}.tscn",
        "authoringSpecPath": f"res://world_authoring/regions/{record['id']}/region-authoring-spec.json"}
        for record in sorted(TERRITORIES, key=lambda record: record["label"].casefold())]})


def manifest_text(territory: dict, server: dict) -> str:
    # The isle's lighting is Crownwater's lagoon (game-look fix stage, review D4): Westhaven's pale horizon and grey-
    # green fog, which the first stub copied, washed every far view to a cream haze where the concept's distance is
    # blue (haze hue 39, saturation 0.10 at the causeway against Oldcraft's far hills at 199-206).
    crownwater = json.loads((CHECKOUT / "eloria-assets/maps/nymara-regions/crownwater/world.json").read_text(
        encoding="utf-8"))
    # Lighting only: Crownwater's presentation (gull, spray and banner zones) and ambient-audio zones name places in
    # Crownwater and would put them at meaningless spots on the isle.
    environment = {key: value for key, value in crownwater["environment"].items()
                   if key not in ("presentation", "zones")}
    return json_text({
        "schemaVersion": 1,
        "asset": {"id": territory["id"], "name": territory["label"], "glb": "world.glb", "units": "meters",
                  "seaLevel": 0.0},
        "productionStatus": "editor source only: not composed, not published, no server map",
        "continentGeography": {"revision": "continent-v2-draft-1", "translation": territory["translation"],
                               "ownershipPolygon": territory["ownership"], "geometryMode": "continent-v2-editor-source"},
        "server": server,
        "environment": environment,
        "environmentNote": "sky, sun, ambient, fog, variants and water tint copied from crownwater/world.json (the "
                           "lagoon's blue horizon and fog; Westhaven's pale ones read as a cream haze in the game "
                           "client); no presentation or audio zones until the isle authors its own",
    })


def spec_text(territory: dict, server: dict, plan_sha: str) -> str:
    region = territory["id"]
    _, _, rows, cols = crop_window(territory)
    return json_text({
        "schema": "eloria-region-authoring-spec-v1",
        "regionId": region,
        "label": territory["label"],
        "adapter": "continent-v2-meshy-v1",
        "paths": {"scene": f"godot-client/world_authoring/regions/{region}/{region}.tscn",
                  "manifest": f"eloria-assets/maps/continent-v2/{region}/world.json",
                  "snapshot": f"eloria-assets/maps/continent-v2/{region}/authoring/continent-authoring.json"},
        "inputs": {"baseHeights": f"godot-client/world_authoring/regions/{region}/base-heights.f32le",
                   "baseColors": f"godot-client/world_authoring/regions/{region}/base-colors.rgba8"},
        "continentTranslation": territory["translation"],
        "server": server,
        "terrain": {"origin": terrain_origin(territory), "cellMetres": CELL, "vertices": [cols, rows]},
        "authority": {"ownedRouteIds": [], "requiredRouteIds": [], "ownedPlanFeatureIds": [],
                      "ownedFerryConnectionIds": []},
        "gameplay": {"runtimeBindingCount": 0, "runtimePointCount": 0, "existingMarkerBindingCount": 0},
        "continentV2": {"planPath": "eloria-assets/maps/continent-v2/_continent_v2/continent-v2-plan.json",
                        "planSha256": plan_sha, "vertical": VERTICAL},
    })


def provenance_text(args, heights_sha: str, colors_sha: str, stats: dict, source_manifest_sha: str) -> str:
    inputs = {}
    heights_rules = json.loads((args.source_data / "work" / "sw8_condition.json").read_text(encoding="utf-8"))["heights"]
    p4 = "coastBand" in heights_rules or "gorge" in heights_rules
    for relative in ["sw_island/heightfield_sw_2m.npy", "sw8_ground_after_pads_before_roads_2m.npy",
                     "work/sw8_corr2.npy", "work/sw8_alb2.npy", "work/sw8_cls2.npy", "work/sw8_wsurf2.npy",
                     "work/sw8_sculpt_eff2.npy", "work/sw8_condition.json"] +             (["work/sw8_keep4_2.npy", "work/sw8_deck2.npy", "sw_island/water.json"] if p4 else []):
        inputs[relative] = sha_file(args.source_data / relative)
    p4_rules = []
    if "coastBand" in heights_rules:
        p4_rules.append(
            "5 coast band (owner 2026-10-02): from the painted shoreline the open sea shelves as "
            "heights.coastBand.seabed (the profile itself within exactWithinMetres, a floor beyond it: the Meshy "
            "plate's rim trench and anything deeper is filled to it, the shallower off-plate shelf stays); low land "
            "near the shore water ramps up from the waterline (cliff feet kept), the product's flat +0.5 m lift "
            "becomes a beach slope; a light blur; the painted classes re-asserted (coast sign kept); never on P, "
            "the keep flags (sw8_keep4_2: built footprints, deck ground, deck landings), rivers or lakes")
    if "gorge" in heights_rules:
        p4_rules.append(
            "6 L12 gorge (owner 2026-10-02): L12 stays at its level; R093's bed joins the lake bed; R070 gets one "
            "monotonic floor from the lake bed to heights.gorge.lipFloorMetres at the lip over cove C04 (the "
            "waterfall); pits under the lake and the other inland water filled to a bed under their surface; a "
            "cut-only slope limit of heights.gorge.slope within withinMetres of the water, measured from the water "
            "and never below its bed, never on P, built footprints or deck landings; under a deck strip the ground "
            "is cut to the deck minus deckClearanceMetres")
    if "inlandShafts" in heights_rules:
        p4_rules.append(
            "7 inland shafts (polish fix stage): painted lake or river cells whose product level is 0, above the sea "
            "and more than heights.inlandShafts.minDepthMetres under the nearest real level, filled to their spill "
            "height (depression filling) and no lower than bedBelowLevelMetres under that level; the "
            "ownerCallKeepLocal boxes, if any, excluded")
    if "padHoles" in heights_rules:
        p4_rules.append(
            "9 pad holes (game-look fix stage, owner 2026-10-02): inside each heights.padHoles box, cells a "
            "protected pad encloses but does not cover (the north-court crevice) are set to the median height "
            "of the pad round them, so the court is level")
    if "finBanks" in heights_rules:
        p4_rules.append(
            "10 gorge-mouth fin banks (game-look fix stage, owner 2026-10-02): inside heights.finBanks.boxLocal, "
            "sea-level inlet cells within reach of the outlet stream's bank (ground at finAboveMetres or more within "
            "finStreamWithinMetres of the stream line) raised to a talus toeMetres + grade x (W - d), at most "
            "apronTopMetres, W = min(widenMetres, keepOpenShare x the inlet's local half-width); only raised, never "
            "P or the keep flags, never in a plungePools circle")
    if "padShore" in heights_rules:
        p4_rules.append(
            "11 SE peninsula shore (game-look fix stage, owner 2026-10-02): inside each heights.padShore box, the "
            "painted land smoothed into an outline (Gaussian of smoothSigmaCells, cut at 0.5); within "
            "beachWidthMetres inside it the ground falls on a smoothstep to toeMetres at the outline (only "
            "lowered), the sea near it at most -(seaShoreMetres + seaGrade d); with outlineSign (fix:game-look) the "
            "coast sign follows the outline (wobbled by outlineNoise) outside the kept cells and their banks, else "
            "the painted classes are re-asserted; "
            "the lighthouse pad released, never the road corridors with their margin, sculpt-indexed cells, the keep "
            "flags, the other pads, keepRects or keepCircles")
    if "release" in heights_rules.get("gorge", {}):
        p4_rules.append(
            "8 gorge protection release (polish fix stage): protected cells in the gorge box more than "
            "heights.gorge.release.aboveRoadMetres over the nearest approved road line (sw8_roadline2) or deck and "
            "more than roadDistanceMetres from it, beside ground the gorge cut, are graded by the gorge rule "
            "(sculpt-indexed ones on their effective height, the layer's deltas kept); hollows 1-4 m under the "
            "lake that touch its water are raised to the bank (heights.gorge.openEdgeFill)")
    colour_rules = []
    colors_params = json.loads((args.source_data / "work" / "sw8_condition.json").read_text(encoding="utf-8"))["colors"]
    if "grade" in colors_params:
        colour_rules.append(
            "colour grade (polish fix stage): pale land texels (sRGB luminance over colors.grade.pale.luminance, "
            "saturation under pale.saturation, smoothstepped) pulled by strength towards lawn green and dry meadow "
            "(fixed-seed noise and height) or, past rockGrade, mid rock grey, keeping each texel's luminance "
            "against its 3-cell neighbourhood; beaches (near the sea, low, flat) keep their sand")
    if "sand" in colors_params:
        colour_rules.append(
            "beach sand (game-look fix stage, review D3): dry cells near ground under 0 m, low and flat "
            "(colors.sand's beach weight), whose texel is grey or pale (saturation under colors.sand.unsaturated), "
            "pulled by strength towards sandSrgb, keeping each texel's luminance against its neighbourhood; inland "
            "water and green vegetation untouched")
    return json_text({
        "schema": "eloria-continent-v2-terrain-provenance-v1",
        "regionId": REGION_ID,
        "sourceData": {"manifest": "work-output/continent-v2/source-data/source-manifest.json",
                       "manifestSha256": source_manifest_sha, "inputs": inputs},
        "frame": {"continentTranslation": TRANSLATION, "cellMetres": CELL,
                  "vertices": [WIDTH, HEIGHT],
                  "firstVertexContinent": [PRODUCT_X0 + 2 * COL0, PRODUCT_Z0 + 2 * ROW0],
                  "lattice": "vertex (i, j) is the island product's cell centre (201 + 2 (i + 49), 6061 + 2 (j + 51)); "
                             "no resampling"},
        "vertical": VERTICAL,
        "heights": {"file": "base-heights.f32le", "encoding": "float32 little-endian, row-major, x fastest",
                    "sha256": heights_sha,
                    "rule": "the island product heightfield (350 m continent peak; castle-town, north-tower and "
                            "lighthouse pads; pits filled; band-limited detail) with every approved-road corridor "
                            "cell (sw8_corr2) the sculpt layer writes at full weight (8 m or more inside the "
                            "ownership window) put back to the ground after the pads and before the roads: the "
                            "approved roads are authored in the editor and their earthworks go in the sculpt "
                            "layer; outside that the product's graded corridors stay in the base",
                    "rules": [
                        "1 product: heightfield_sw_2m",
                        "2 corridors restored: sw8_corr2 cells the sculpt layer writes at full weight take the "
                        "pre-road ground",
                        "3 off-plate ring clamped: off-plate cells within heights.offPlateRing.bandMetres of the "
                        "Meshy plate lowered to the nearest off-plate cell beyond the band and to "
                        "heights.offPlateRing.ceilingMetres at most (sw8_condition.json)",
                        "4 high-rim inland pockets filled: below-sea components that do not reach the grid edge, "
                        "rim median over heights.inlandPockets.rimP50MinMetres, raised to their rim p10 with a "
                        "1-cell Gaussian blend (pocket cells only)",
                        "3 and 4 never change a protected cell: sw8_sculpt_cells2 | corridors | compound | "
                        "town | north-tower pad | lighthouse pads; 3 also spares the corridors' 2-cell margin, 4 "
                        "fills pocket cells in it; the sculpt layer is rebound to the new base "
                        "(editor-pass/rebind_sculpt_layer.gd)"] + p4_rules,
                    "stats": {key: value for key, value in stats.items() if key != "colors"}},
        "colors": {"file": "base-colors.rgba8", "encoding": "RGBA8, linear (sRGB albedo decoded), alpha 255",
                   "sha256": colors_sha, "source": "Meshy texture albedo rasterised on the same 2 m cells",
                   "rules": [
                       "off-plate cells (no Meshy texture; albedo 0 in the product): at or above 0 m the nearest "
                       "covered dry texel, below 0 m the nearest covered sea texel darkened towards "
                       "colors.seabedLinear over colors.seabedDepthMetres of depth (sw8_condition.json)",
                       "water paint on dry walls: water-hued texels within colors.wallsWithinMetresOfInlandWater of "
                       "a lake or river cell that are not wet (a painted lake or river cell at most "
                       "colors.wallAboveWaterMetres over its own water surface, or anything at most that over the "
                       "sea), and wet ones at the foot or brink of a drop of more than colors.wallStepMetres to a "
                       "neighbour (their colour spans the wall face), take the nearest covered dry, non-water-hued "
                       "texel; on faces steeper than colors.rockGreyAboveGrade pulled towards rock grey at the "
                       "texel's luminance",
                       "faces the height conditioning cut open by colors.cutFaces.minCutMetres or more and "
                       "steeper than colors.cutFaces.aboveGrade (the L12 gorge's laid-back walls) are pulled "
                       "towards rock grey the same way",
                       "above or below sea is read on the conditioned base heights, with the sculpt layer's "
                       "effective heights where sw8_sculpt_eff2 has them (the road earthworks at 4394ade5c)"]
                   + colour_rules,
                   "stats": stats.get("colors", {})},
        "tool": "godot-client/tools/bootstrap_continent_v2_territory.py",
    })


def crop_provenance_text(territory: dict, heights: np.ndarray, heights_sha: str, colors_sha: str, group: dict,
                         source_manifest_sha: str) -> str:
    row0, col0, rows, cols = crop_window(territory)
    region = territory["id"]
    return json_text({
        "schema": "eloria-continent-v2-terrain-provenance-v1",
        "regionId": region,
        "sourceData": {"manifest": "work-output/continent-v2/source-data/source-manifest.json",
                       "manifestSha256": source_manifest_sha,
                       "inputs": f"as {REGION_ID}'s terrain-provenance.json"},
        "crop": {"parent": REGION_ID, "row0": row0, "col0": col0, "rows": rows, "cols": cols,
                 "parentBaseHeightsSha256": group["heightsSha"], "parentBaseColorsSha256": group["colorsSha"],
                 "why": "the island group's three maps share one conditioned base (adjacent-map design s. 2 and 4): "
                        "a crop of it keeps every vertex this territory shares with sw_isle bit-identical, and "
                        "changes nothing in sw_isle's base, so its sculpt layer stays bound"},
        "frame": {"continentTranslation": territory["translation"], "cellMetres": CELL, "vertices": [cols, rows],
                  "firstVertexContinent": list(first_vertex(territory)),
                  "lattice": f"vertex (i, j) is {REGION_ID}'s base vertex (i + {col0}, j + {row0}), the island "
                             f"product's cell centre (201 + 2 (i + {COL0 + col0}), 6061 + 2 (j + {ROW0 + row0})); "
                             "no resampling"},
        "vertical": VERTICAL,
        "heights": {"file": "base-heights.f32le", "encoding": "float32 little-endian, row-major, x fastest",
                    "sha256": heights_sha,
                    "rule": f"a byte crop of {REGION_ID}'s base-heights.f32le (the conditioned 8 km island product "
                            f"over the whole group grid; {REGION_ID}'s terrain-provenance.json has the inputs and "
                            "the rules). This territory's own terrain fixes go in its sculpt layer, patches and "
                            "paths, never into this file",
                    "stats": {"heightRangeMetres": [round(float(heights.min()), 3), round(float(heights.max()), 3)]}},
        "colors": {"file": "base-colors.rgba8", "encoding": "RGBA8, linear (sRGB albedo decoded), alpha 255",
                   "sha256": colors_sha, "rule": f"a byte crop of {REGION_ID}'s base-colors.rgba8"},
        "tool": "godot-client/tools/bootstrap_continent_v2_territory.py",
    })


README = """# Landfall (`sw_isle`), continent v2

The landing island of continent v2: new players arrive here, `#beam` brings them here and they respawn here
after death. It is built from the Meshy "Isles of Enchantment" model at 8,000 m east-west, whose roads,
rivers and topography are authoritative.

- `sw_isle.tscn`: the authored territory scene. Open it in the editor: on this branch `project.godot` sets
  `map_authoring/territory_catalog_path` to the v2 catalog, so the Territories dock binds the ownership
  window and the sculpt, heightmap-import, ground and plateau tools work as for any territory.
- `../../continent-v2/viewer/sw_isle_view.tscn`: the same scene with a sky, a sun and the sea.
- `base-heights.f32le`, `base-colors.rgba8`: the map-team base, written once by
  `godot-client/tools/bootstrap_continent_v2_territory.py` from the 8 km island products
  (`terrain-provenance.json` has the inputs, hashes and rules). Later edits go in patches, paths and the
  sculpt layer, never into these files. The road earthworks are in the sculpt layer inside the window; outside
  it, where the sculpt tool cannot write, the base keeps the product's graded road corridors.
- `region-authoring-spec.json`: frame and server address. The territory is registered only in the v2
  catalog, `world_authoring/continent-v2/territories.json`; the shared twelve-territory catalog does not
  list it, and on this branch the editor reads the v2 catalog instead of the shared one.

The ownership window (x 399-2437, z 6221-8259 in continent metres) is the largest single 2,048-tile server
map over the main island, which is 2,080 x 2,334 m. The terrain grid covers the whole island group so the
east islet, the SE islet village and the east pier are visible; they belong to the neighbouring maps The
Tollholms (east of x 2437) and The Gull Skerries (south of z 8259), decisions D2a-D2c.
"""


def crop_readme(territory: dict, server: dict) -> str:
    """A cropped territory's first README (wrapped at 116 columns, as the repository's READMEs are)."""
    import textwrap

    row0, col0, rows, cols = crop_window(territory)
    region = territory["id"]
    role = territory["role"]
    patches = territory.get("patches", [])
    moles = (", and the seam moles " + " and ".join(f"`Terrain/Patches/{p}`" for p in patches)) if patches else ""
    paragraphs = [
        f"# {territory['label']} (`{region}`), continent v2",
        role[0].upper() + role[1:] + ".",
        [f"`{region}.tscn`: the authored territory scene. Its first bootstrap wrote the frame, the ownership sha, the "
         f"territory hub and the other markers{moles}; from here on it is the editor's. On this branch the editor "
         "reads the v2 catalog (`world_authoring/continent-v2/territories.json`), which lists the three island-group "
         "maps.",
         f"`../../continent-v2/viewer/{region}_view.tscn`: the scene with a sky, a sun and the sea; "
         "`../../continent-v2/viewer/isles_view.tscn` shows the three territories together.",
         f"`base-heights.f32le`, `base-colors.rgba8`: a byte crop of sw_isle's base (rows {row0}-{row0 + rows - 1}, "
         f"columns {col0}-{col0 + cols - 1} of its {WIDTH} x {HEIGHT} grid; `terrain-provenance.json`). sw_isle's "
         "grid covers the whole island group, so the vertices this territory shares with sw_isle hold the same bytes "
         "on both sides. Never edit these files: this territory's own terrain fixes go in its sculpt layer, patches "
         "and paths. The sculpt tool locks 4 m inside the ownership polygon and fades over 4 more, so nothing it "
         "writes reaches a shared vertex.",
         f"`region-authoring-spec.json`: frame and server address (origin ({server['origin'][0]}, "
         f"{server['origin'][1]}), {server['cells'][0]} tiles)."],
        "Ownership polygon (continent metres): " +
        ", ".join(f"({x:.0f}, {z:.0f})" for x, z in territory["ownership"]) + ". The seams with sw_isle are listed in "
        "the v2 plan (`eloria-assets/maps/continent-v2/_continent_v2/continent-v2-plan.json`, `seams`): decks never "
        "cross a border; the walk crosses on open land seams or on seam moles, rectangular Set patches declared "
        "identically in both scenes. `godot-client/tools/continent_v2_territories.py` (and "
        "`godot-client/tests/test_continent_v2_territories.py`) checks that the shared vertices keep the same base "
        "bytes, no sculpt delta and the same patches on both sides, that the polygons do not overlap and that no "
        "island land is left unowned.",
        "The bootstrap writes this README only when it is missing; it is maintained by hand.",
    ]
    blocks = []
    for paragraph in paragraphs:
        if isinstance(paragraph, list):
            blocks.append("\n".join(textwrap.fill(item, 116, initial_indent="- ", subsequent_indent="  ",
                                                  break_on_hyphens=False) for item in paragraph))
        elif paragraph.startswith("#"):
            blocks.append(paragraph)
        else:
            blocks.append(textwrap.fill(paragraph, 116, break_on_hyphens=False))
    return "\n\n".join(blocks) + "\n"


def write(path: Path, data: bytes, check: bool, changed: list) -> None:
    if path.exists() and path.read_bytes() == data:
        return
    changed.append(str(path.relative_to(CHECKOUT)))
    if not check:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-data", type=Path, required=True)
    parser.add_argument("--meshy-glb", type=Path, required=True)
    parser.add_argument("--concept", type=Path, required=True)
    parser.add_argument("--approved-routes", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source_manifest_sha = sha_file(args.source_data / "source-manifest.json")
    manifest = json.loads((args.source_data / "source-manifest.json").read_text(encoding="utf-8"))
    for relative, record in manifest["files"].items():
        if sha_file(args.source_data / relative) != record["sha256"]:
            raise SystemExit(f"source-data file changed since its manifest: {relative}")
    # The group arrays: sw_isle's grid over the whole island group, computed once.
    heights, colors, stats = terrain_arrays(args.source_data)
    heights = heights.reshape(HEIGHT, WIDTH)
    tint = sea_tint_rgb(heights)
    # The plaza is on the level castle-town pad.
    col = int(round((PLAZA[0] - PRODUCT_X0) / CELL)) - COL0
    row = int(round((PLAZA[1] - PRODUCT_Z0) / CELL)) - ROW0
    plaza_height = float(heights[row, col])
    outputs = {}
    for territory in TERRITORIES:
        row0, col0, rows, cols = crop_window(territory)
        window = (slice(row0, row0 + rows), slice(col0, col0 + cols))
        crop_heights = np.ascontiguousarray(heights[window]).astype("<f4")
        crop_colors = np.ascontiguousarray(colors[window])
        heights_bytes, colors_bytes = crop_heights.tobytes(), crop_colors.tobytes()
        outputs[territory["id"]] = {
            "heights": crop_heights, "heightsBytes": heights_bytes, "colorsBytes": colors_bytes,
            "heightsSha": sha_bytes(heights_bytes), "colorsSha": sha_bytes(colors_bytes),
            "tint": tint[window], "server": server_frame(territory["ownership"], territory["translation"]),
            "polygonSha": ownership_sha(territory["ownership"])}
    group = outputs[REGION_ID]
    # A served territory's frame is frozen (serve plan CV9): saved characters stand on its tiles and the server's
    # lanes, landings and homes are written in it, so moving its origin, size or continent translation needs a
    # position migration on the server, which this tool does not do. Refused before anything is written, in both
    # modes.
    from continent_v2_territories import served_frame_problems

    moved = served_frame_problems({territory["id"]: {
        "origin": outputs[territory["id"]]["server"]["origin"], "cells": outputs[territory["id"]]["server"]["cells"],
        "translation": territory["translation"]} for territory in TERRITORIES})
    if moved:
        print("REFUSED: a served territory's frame would move: " + "; ".join(moved), file=sys.stderr)
        return 1
    plan = plan_document(args, outputs, source_manifest_sha)
    plan_bytes = json_text(plan).encode("utf-8")
    plan_sha = sha_bytes(plan_bytes)
    changed: list = []
    write(PLAN_PATH, plan_bytes, args.check, changed)
    write(PLAN_PATH.parent / "README.md", (
        "# Continent v2 plan\n\n`continent-v2-plan.json` is the macro plan of continent v2, rebuilt from the Meshy "
        "model at 8,000 m east-west. It holds the frame, the vertical curve, the source digests, the territories "
        "(the island group's three maps so far: `sw_isle`, `tollholms` and `gull_skerries`), their seams, the "
        "owner-approved routes and decks (with the territory each stretch lies in), the island water, the landmarks "
        "and the owner's decisions.\n\n"
        "Nothing in the twelve-territory pipeline reads it: `landscape.py`, `ownership_contract.py` and the "
        "editor hard-code `nymara-regions/_continent/diagonal-plan.json`. It is written by "
        "`godot-client/tools/bootstrap_continent_v2_territory.py`.\n").encode("utf-8"), args.check, changed)
    write(V2_DIR / "territories.json", catalog_text().encode("utf-8"), args.check, changed)
    for territory in TERRITORIES:
        region = territory["id"]
        out = outputs[region]
        directory = region_dir(territory)
        target = territory["viewer"].get("target")
        target_height = plaza_height if not territory["crop"] else marker_y(territory, out["heights"], *target)
        write(manifest_path(territory), manifest_text(territory, out["server"]).encode("utf-8"), args.check, changed)
        write(V2_DIR / "viewer" / f"{region}_view.tscn", viewer_text(territory, target_height).encode("utf-8"),
              args.check, changed)
        write(V2_DIR / "viewer" / territory["viewer"]["seaTint"], sea_tint_png(out["tint"]), args.check, changed)
        write(directory / "base-heights.f32le", out["heightsBytes"], args.check, changed)
        write(directory / "base-colors.rgba8", out["colorsBytes"], args.check, changed)
        write(directory / "region-authoring-spec.json", spec_text(territory, out["server"], plan_sha).encode("utf-8"),
              args.check, changed)
        if territory["crop"]:
            provenance = crop_provenance_text(territory, out["heights"], out["heightsSha"], out["colorsSha"], group,
                                              source_manifest_sha)
        else:
            provenance = provenance_text(args, out["heightsSha"], out["colorsSha"], stats, source_manifest_sha)
        write(directory / "terrain-provenance.json", provenance.encode("utf-8"), args.check, changed)
        readme_path = directory / "README.md"
        if not readme_path.exists():
            # Like the scene, the README is maintained by hand after the first bootstrap (the kit, the seating fixes
            # and the terrain conditioning are documented there), so only a first bootstrap writes it.
            text = README if not territory["crop"] else crop_readme(territory, out["server"])
            write(readme_path, text.encode("utf-8"), args.check, changed)
        scene_path = directory / f"{region}.tscn"
        if not scene_path.exists() or args.check:
            # The scene is the editor's from here on: only a first bootstrap writes it.
            write(scene_path, scene_text(territory, out["server"], out["polygonSha"], out["heights"],
                                         plaza_height).encode("utf-8"), args.check,
                  changed if not scene_path.exists() else [])
    write(V2_DIR / "viewer" / "isles_view.tscn", isles_viewer_text().encode("utf-8"), args.check, changed)
    summary = {"territories": {
        territory["id"]: {"server": outputs[territory["id"]]["server"],
                          "ownershipPolygonSha256": outputs[territory["id"]]["polygonSha"],
                          "terrainOrigin": terrain_origin(territory), "cropOfGroupGrid": list(crop_window(territory)),
                          "baseHeightsSha256": outputs[territory["id"]]["heightsSha"],
                          "baseColorsSha256": outputs[territory["id"]]["colorsSha"]}
        for territory in TERRITORIES},
        "plazaHeight": round(plaza_height, 3), "stats": stats, "changed": changed}
    problems: list = []
    if not args.check or not changed:
        # The cross-territory checks read the outputs on disk: after a write, or when --check found them current.
        from continent_v2_territories import check_all

        problems, summary["territoryChecks"] = check_all(V2_DIR / "territories.json")
        summary["territoryProblems"] = problems
    print(json.dumps(summary, indent=1))
    if args.check and changed:
        print("CHECK FAILED: outputs differ from the inputs", file=sys.stderr)
        return 1
    if problems:
        print("CHECK FAILED: cross-territory checks: " + "; ".join(problems), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

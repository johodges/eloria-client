"""Sunmane Steppe terrain: heightfield, coastline, mesas and terrain classes.

The region is a 208 m square centred on the server arrival datum (58, 58),
which the client's coordinate adapter maps to Godot (0, 0) at one metre per
tile.  North is -Z.

Composition follows the aerial overview: a broad sunlit grassland carrying the
fortified encampment on a low central rise, flat-topped mesas along the north
and east, a rugged coastline with two bays on the west and south-west, and a
stream chain feeding waterholes across the open steppe.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from noise import fbm, normalise

HALF_EXTENT = 104.0          # metres from the datum to the world edge
CELL = 1.3                   # heightfield spacing in metres (161 x 161)
SEA_LEVEL = 0.0
BEACH_LEVEL = 0.9

# Terrain classes, in the order the region description lists them.
CLASS_CLEARING = 0           # packed earth inside the clan camps
CLASS_STEPPE = 1             # open grazing steppe
CLASS_ROAD = 2               # caravan roads and riding trails
CLASS_DRY_GRASS = 3          # sun-bleached dry grass and crop ground
CLASS_ROCK = 4               # mesa tops, cliffs and shore rock
CLASS_SAND = 5               # beaches and dry stream beds

CLASS_NAMES = {
    CLASS_CLEARING: "clan_clearing",
    CLASS_STEPPE: "open_steppe",
    CLASS_ROAD: "caravan_road",
    CLASS_DRY_GRASS: "dry_grass",
    CLASS_ROCK: "shore_rock",
    CLASS_SAND: "beach_sand",
}

# Base-colour multipliers applied to the shared ground detail map so each class
# reads distinctly while sharing one texture and one texel density.
# glTF requires baseColorFactor in 0..1, so the ground detail map is authored a
# little brighter than final and every class sits at or below unity here.
CLASS_TINT = {
    CLASS_CLEARING: (0.80, 0.68, 0.48, 1.0),
    CLASS_STEPPE: (0.88, 0.82, 0.50, 1.0),
    CLASS_ROAD: (0.92, 0.74, 0.48, 1.0),
    CLASS_DRY_GRASS: (1.00, 0.90, 0.48, 1.0),
    CLASS_ROCK: (0.76, 0.65, 0.50, 1.0),
    CLASS_SAND: (0.98, 0.90, 0.74, 1.0),
}


def _smoothstep(edge0: float, edge1: float, value: np.ndarray) -> np.ndarray:
    t = np.clip((value - edge0) / max(edge1 - edge0, 1e-9), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _falloff(distance: np.ndarray, inner: float, outer: float) -> np.ndarray:
    """1 inside `inner`, smoothly to 0 by `outer`."""
    return 1.0 - _smoothstep(inner, outer, distance)


@dataclass
class Landform:
    """Sampled terrain: heights, per-vertex class and derived masks."""
    x: np.ndarray                 # (n,) world X coordinates
    z: np.ndarray                 # (n,) world Z coordinates
    height: np.ndarray            # (n, n) elevation
    classes: np.ndarray           # (n, n) terrain class index
    water: np.ndarray             # (n, n) True where sea or pond covers ground

    def sample(self, world_x, world_z) -> np.ndarray:
        """Bilinear height lookup in world space."""
        fx = np.clip((np.asarray(world_x, dtype="float64") + HALF_EXTENT) / CELL,
                     0.0, len(self.x) - 1.001)
        fz = np.clip((np.asarray(world_z, dtype="float64") + HALF_EXTENT) / CELL,
                     0.0, len(self.z) - 1.001)
        x0, z0 = fx.astype(int), fz.astype(int)
        tx, tz = fx - x0, fz - z0
        h00 = self.height[z0, x0]
        h10 = self.height[z0, x0 + 1]
        h01 = self.height[z0 + 1, x0]
        h11 = self.height[z0 + 1, x0 + 1]
        return (h00 * (1 - tx) * (1 - tz) + h10 * tx * (1 - tz)
                + h01 * (1 - tx) * tz + h11 * tx * tz)

    def height_at(self, world_x: float, world_z: float) -> float:
        return float(self.sample(world_x, world_z))

    def class_at(self, world_x: float, world_z: float) -> int:
        ix = int(np.clip((world_x + HALF_EXTENT) / CELL, 0, len(self.x) - 1))
        iz = int(np.clip((world_z + HALF_EXTENT) / CELL, 0, len(self.z) - 1))
        return int(self.classes[iz, ix])


# --------------------------------------------------------------------- routes
# Caravan roads radiating from the ceremonial crossroads at the datum. Each is
# a polyline in world XZ; the settlement ring road closes around the palisade.
CAMP_CENTER = (0.0, 0.0)
CAMP_RADIUS = 30.0

ROADS = {
    "west_caravan": [(0, 0), (-16, -2), (-32, -1), (-52, 0), (-70, 2), (-84, 6)],
    "east_caravan": [(0, 0), (18, 1), (34, 0), (52, 0), (72, -3), (90, -6)],
    "north_barrow": [(0, 0), (-2, -16), (-1, -30), (0, -42), (2, -58), (4, -74)],
    "south_shore": [(0, 0), (3, 16), (4, 32), (2, 50), (-4, 66), (-14, 80)],
    "northwest_pasture": [(0, 0), (-14, -12), (-28, -24), (-40, -36), (-50, -46)],
    "southeast_mill": [(0, 0), (14, 13), (28, 26), (42, 38), (54, 48)],
    "northeast_watch": [(0, 0), (16, -12), (32, -24), (46, -34), (58, -44)],
    "southwest_cove": [(0, 0), (-14, 12), (-30, 24), (-46, 36), (-62, 46), (-74, 54)],
}

# Crop and pasture blocks: (centre x, centre z, half extent x, half extent z).
FIELDS = ((34.0, 30.0, 15.0, 11.0), (-34.0, -46.0, 13.0, 10.0),
          (52.0, 44.0, 12.0, 9.0), (-52.0, 22.0, 11.0, 9.0),
          (22.0, -58.0, 12.0, 9.0))

# The four Orun clan camps ring the shared market at the ceremonial crossroads.
CAMP_CLEARINGS = ((-30.0, -40.0, 12.5), (46.0, -26.0, 11.5),
                  (64.0, 20.0, 11.5), (-40.0, 34.0, 11.5))

ROAD_WIDTH = 5.0
TRAIL_WIDTH = 2.6

# Secondary riding trails linking outlying sites to the road network.
TRAILS = {
    "mill_ridge": [(44, 40), (58, 30), (68, 18), (72, 4)],
    "well_loop": [(-32, -1), (-38, 14), (-34, 30), (-20, 38), (-4, 40)],
    "pen_loop": [(34, 0), (44, -12), (52, -22), (62, -26)],
    "stone_circle": [(-28, -24), (-40, -20), (-50, -14), (-58, -8)],
    "dock_spur": [(-62, 46), (-70, 40), (-78, 36)],
    "east_camp": [(52, 0), (62, 10), (70, 22)],
    "north_camp": [(-1, -30), (-14, -36), (-26, -44)],
}


def _polyline_distance(px: np.ndarray, pz: np.ndarray, path) -> np.ndarray:
    """Distance from every grid point to a polyline."""
    best = np.full(px.shape, 1e9)
    for index in range(len(path) - 1):
        ax, az = path[index]
        bx, bz = path[index + 1]
        dx, dz = bx - ax, bz - az
        length_squared = dx * dx + dz * dz
        if length_squared < 1e-9:
            continue
        t = np.clip(((px - ax) * dx + (pz - az) * dz) / length_squared, 0.0, 1.0)
        best = np.minimum(best, np.hypot(px - (ax + t * dx), pz - (az + t * dz)))
    return best


def _warp(gx, gz, field, amount: float):
    """Domain-warp a coordinate pair so stamped shapes lose their machined edges."""
    return gx + (field[0] - 0.5) * amount, gz + (field[1] - 0.5) * amount


def _blob_distance(gx, gz, cx, cz, radius, lobes, phase, roughness):
    """Distance to an irregular closed shape, normalised so 1.0 is its edge."""
    dx, dz = gx - cx, gz - cz
    distance = np.hypot(dx, dz)
    angle = np.arctan2(dz, dx)
    modulation = 1.0
    for index, (harmonic, weight) in enumerate(lobes):
        modulation = modulation + weight * np.sin(harmonic * angle + phase * (index + 1))
    modulation = modulation + roughness
    return distance / np.maximum(radius * modulation, 1e-6)


def build(seed: int = 20260827, pads=()) -> Landform:
    """Sculpt the region heightfield and assign terrain classes."""
    count = int(HALF_EXTENT * 2 / CELL) + 1
    axis = np.linspace(-HALF_EXTENT, HALF_EXTENT, count)
    gx, gz = np.meshgrid(axis, axis)                 # gz varies down the rows

    detail = int(2 ** math.ceil(math.log2(count)))

    def noise(period: int, octaves: int, offset: int) -> np.ndarray:
        field = fbm(detail, period, octaves, np.random.default_rng(seed + offset))
        return field[:count, :count]

    # Two warp fields reused throughout so every stamped landform inherits the
    # same organic distortion instead of reading as a stencil.
    warp_a = (noise(6, 4, 101), noise(6, 4, 102))
    warp_b = (noise(14, 4, 103), noise(14, 4, 104))
    wx, wz = _warp(gx, gz, warp_a, 26.0)
    fx, fz = _warp(gx, gz, warp_b, 9.0)

    # --- rolling steppe base -------------------------------------------
    height = 4.0 + noise(4, 5, 1) * 7.0 + noise(11, 4, 2) * 2.4 + noise(27, 3, 3) * 0.9
    # Long shallow swales so the grassland is not a pancake.
    height += np.sin(gx * 0.032 + gz * 0.018 + 0.7) * 1.9
    height += np.cos(gz * 0.041 - gx * 0.012) * 1.4

    # --- low central rise carrying the encampment ----------------------
    camp_distance = np.hypot(gx - CAMP_CENTER[0], gz - CAMP_CENTER[1])
    warped_camp = np.hypot(wx - CAMP_CENTER[0], wz - CAMP_CENTER[1])
    height += 3.8 * _falloff(warped_camp, 28.0, 68.0)
    plateau = _falloff(camp_distance, 24.0, 33.0)
    height = height * (1.0 - plateau) + 9.6 * plateau

    # --- northern and eastern mesas -------------------------------------
    # (x, z, radius, cap fraction, top height, lobe set, phase)
    mesas = (
        (-20.0, -80.0, 27.0, 0.56, 25.5, ((3, 0.16), (5, 0.09), (7, 0.05)), 0.4),
        (18.0, -90.0, 21.0, 0.52, 22.5, ((3, 0.19), (4, 0.11), (8, 0.06)), 2.1),
        (60.0, -68.0, 19.0, 0.50, 21.5, ((2, 0.21), (5, 0.10), (9, 0.05)), 4.3),
        (-64.0, -62.0, 16.0, 0.48, 19.0, ((3, 0.17), (6, 0.12)), 1.2),
        (78.0, -14.0, 17.0, 0.44, 18.5, ((2, 0.24), (5, 0.12)), 3.0),
        (80.0, 30.0, 15.0, 0.42, 16.5, ((3, 0.20), (7, 0.09)), 5.4),
        (68.0, 64.0, 14.0, 0.40, 15.0, ((2, 0.22), (6, 0.10)), 0.9),
    )
    rock_stamp = np.zeros_like(height)
    for mx, mz, radius, inner, top, lobes, phase in mesas:
        roughness = (noise(19, 3, int(abs(mx) + abs(mz)) % 40 + 30) - 0.5) * 0.22
        normalised = _blob_distance(fx, fz, mx, mz, radius, lobes, phase, roughness)
        crown = top + noise(29, 3, 7) * 1.3
        # A mesa is a flat cap, a near-vertical cliff band, then a talus apron -
        # not a smooth dome. Building the profile explicitly is what gives the
        # silhouette the concept's hard eroded edge.
        cap = _falloff(normalised, inner, inner + 0.06)
        cliff = _falloff(normalised, inner + 0.06, 1.0)
        talus = _falloff(normalised, 1.0, 1.62)
        # Stepped benches so the cliff face reads as bedded strata in profile.
        benches = np.clip(normalised - inner, 0.0, 1.0) / max(1.0 - inner, 1e-6)
        stepping = (np.floor(benches * 4.0) + _smoothstep(0.55, 0.95,
                                                          (benches * 4.0) % 1.0)) / 4.0
        cliff_height = crown - (crown - height) * stepping
        profile = np.where(cap > 0.5, crown,
                           np.where(cliff > 0.02,
                                    height + (cliff_height - height) * cliff,
                                    height))
        blend = np.maximum(cap, cliff)
        height = height * (1.0 - blend) + profile * blend
        # Talus fan of shed material around the foot.
        height += (crown - height) * 0.22 * talus * (1.0 - blend)
        rock_stamp = np.maximum(rock_stamp, _falloff(normalised, 1.05, 1.5))

    # --- isolated formations and standing-stone knolls ------------------
    for kx, kz, radius, rise, lobes, phase in (
            (-44.0, -18.0, 10.0, 4.6, ((3, 0.22), (5, 0.12)), 1.1),
            (26.0, 44.0, 9.0, 3.8, ((2, 0.26), (6, 0.10)), 3.7),
            (-70.0, 12.0, 8.0, 3.2, ((3, 0.20), (7, 0.11)), 5.1),
            (46.0, -52.0, 9.0, 4.1, ((2, 0.24), (5, 0.13)), 2.6)):
        normalised = _blob_distance(fx, fz, kx, kz, radius, lobes, phase, 0.0)
        height += rise * _falloff(normalised, 0.35, 1.0)
        rock_stamp = np.maximum(rock_stamp, _falloff(normalised, 0.55, 0.95) * 0.8)

    # --- coastline: western bays and a south-western sound ---------------
    coast_noise = noise(7, 5, 11)
    shore = (-76.0 - 10.0 * np.sin(gz * 0.048 + 0.6) - 7.0 * np.cos(gz * 0.019 + 1.3)
             + (coast_noise - 0.5) * 26.0)
    for bx, bz, radius, depth in ((-90.0, -58.0, 44.0, 16.0), (-84.0, 58.0, 50.0, 22.0),
                                  (-92.0, 8.0, 26.0, 9.0)):
        shore = shore - depth * _falloff(np.hypot(fx - bx, fz - bz), radius * 0.25, radius)
    into_sea = _smoothstep(0.0, 14.0, shore - fx)

    # Southern shore sweeping round the south-west and a south-eastern inlet.
    south_shore = (78.0 + 9.0 * np.sin(gx * 0.041 + 2.1) + (noise(9, 4, 12) - 0.5) * 18.0
                   - 16.0 * _falloff(np.hypot(fx - 82.0, fz - 96.0), 12.0, 44.0))
    into_sea = np.maximum(into_sea, _smoothstep(0.0, 14.0, fz - south_shore))
    seabed = -5.5 - 6.0 * into_sea
    height = height * (1.0 - into_sea) + seabed * into_sea

    # --- coastal cliffs, headlands and sea stacks ------------------------
    coastal = _falloff(np.abs(shore - fx), 2.0, 14.0) * (1.0 - into_sea)
    headland = _falloff(np.hypot(fx + 84.0, fz - 2.0), 10.0, 32.0)
    height += 10.5 * coastal * (0.40 + 0.60 * headland)
    rock_stamp = np.maximum(rock_stamp, coastal)
    for sx, sz, radius, top in ((-88.0, -34.0, 4.0, 9.0), (-93.0, 24.0, 3.4, 7.5),
                                (-86.0, 70.0, 3.8, 8.5), (66.0, 92.0, 4.2, 8.0)):
        stack = _falloff(np.hypot(gx - sx, gz - sz), radius * 0.5, radius)
        height = np.maximum(height, height * (1.0 - stack) + top * stack)
        rock_stamp = np.maximum(rock_stamp, stack)

    # --- world rim: a ragged ring of highland, not a square wall ---------
    rim_distance = np.maximum(np.abs(gx), np.abs(gz))
    ragged = (noise(7, 3, 41) - 0.5) * 7.0 + (noise(19, 3, 42) - 0.5) * 3.0
    rim = _smoothstep(88.0, 101.0, rim_distance + ragged)
    # A ridge line rather than a plateau, so the barrier reads as landscape.
    ridge = 0.70 + 0.30 * np.sin(np.arctan2(gz, gx) * 3.0 + noise(5, 3, 43) * 4.0)
    height += 26.0 * rim * ridge * (1.0 - into_sea)
    height -= 9.0 * rim * into_sea
    rock_stamp = np.maximum(rock_stamp, _smoothstep(0.35, 0.85, rim) * (1.0 - into_sea))

    # --- building pads ---------------------------------------------------
    # Structures are authored flat-bottomed, so the ground under each one is
    # levelled to its centre height with a graded skirt. Without this a wide
    # footprint has to be sunk to its lowest corner and the building buries
    # itself in the slope.
    for pad_x, pad_z, pad_radius in pads:
        column = int(np.clip((pad_x + HALF_EXTENT) / CELL, 0, count - 1))
        row = int(np.clip((pad_z + HALF_EXTENT) / CELL, 0, count - 1))
        target = float(height[row, column])
        distance = np.hypot(gx - pad_x, gz - pad_z)
        core = _falloff(distance, pad_radius * 0.92, pad_radius * 1.05)
        skirt = _falloff(distance, pad_radius * 1.05, pad_radius * 2.1)
        blended = np.maximum(core, skirt * 0.72)
        height = height * (1.0 - blended) + target * blended

    # --- stream chain and waterholes ------------------------------------
    stream = [(-10, -74), (-8, -58), (-2, -44), (4, -32), (-6, -24), (-22, -14),
              (-34, 2), (-44, 16), (-56, 28), (-66, 42), (-74, 54)]
    stream_distance = _polyline_distance(fx, fz, stream)
    channel = _falloff(stream_distance, 1.2, 6.0) * (1.0 - into_sea)
    height -= 2.8 * channel
    ponds = ((-8.5, -58.0, 7.0, ((3, 0.26), (5, 0.14)), 1.4),
             (3.0, -30.5, 5.8, ((2, 0.30), (6, 0.12)), 3.2),
             (-58.0, 30.0, 6.4, ((3, 0.24), (7, 0.10)), 5.0),
             (-46.0, 40.0, 7.6, ((2, 0.28), (5, 0.15)), 0.6),
             (48.0, -30.0, 5.4, ((3, 0.22), (6, 0.13)), 2.4),
             (36.0, 52.0, 6.0, ((2, 0.26), (7, 0.11)), 4.1))
    pond_mask = np.zeros_like(height)
    for px, pz, radius, lobes, phase in ponds:
        normalised = _blob_distance(fx, fz, px, pz, radius, lobes, phase, 0.0)
        bowl = _falloff(normalised, 0.3, 1.0)
        height -= 3.2 * bowl
        pond_mask = np.maximum(pond_mask, bowl)

    # --- roads and trails cut a graded corridor -------------------------
    road_mask = np.zeros_like(height)
    for path in ROADS.values():
        road_mask = np.maximum(road_mask, _falloff(
            _polyline_distance(gx, gz, path), ROAD_WIDTH * 0.5, ROAD_WIDTH * 0.5 + 3.0))
    trail_mask = np.zeros_like(height)
    for path in TRAILS.values():
        trail_mask = np.maximum(trail_mask, _falloff(
            _polyline_distance(gx, gz, path), TRAIL_WIDTH * 0.5, TRAIL_WIDTH * 0.5 + 2.4))
    combined_route = np.maximum(road_mask, trail_mask * 0.75)
    smoothed = height.copy()
    for _ in range(7):
        smoothed = (smoothed * 0.2
                    + np.roll(smoothed, 1, 0) * 0.2 + np.roll(smoothed, -1, 0) * 0.2
                    + np.roll(smoothed, 1, 1) * 0.2 + np.roll(smoothed, -1, 1) * 0.2)
    height = height * (1.0 - combined_route * 0.88) + smoothed * (combined_route * 0.88)

    # --- crop and pasture blocks ----------------------------------------
    field_mask = np.zeros_like(height)
    for cx, cz, half_x, half_z in FIELDS:
        block = (_falloff(np.abs(fx - cx), half_x - 3.0, half_x)
                 * _falloff(np.abs(fz - cz), half_z - 3.0, half_z))
        field_mask = np.maximum(field_mask, block)
        height = height * (1.0 - block * 0.65) + smoothed * (block * 0.65)

    water = (height < SEA_LEVEL) | (pond_mask > 0.5)

    # --- terrain classification ------------------------------------------
    classes = np.full(height.shape, CLASS_STEPPE, dtype="int8")
    dry = noise(6, 4, 21)
    classes[dry > 0.60] = CLASS_DRY_GRASS
    classes[field_mask > 0.4] = CLASS_DRY_GRASS
    slope = _slope(height)
    classes[(rock_stamp > 0.62) | (slope > 1.15)] = CLASS_ROCK
    classes[camp_distance < 25.0] = CLASS_CLEARING
    for cx, cz, radius in CAMP_CLEARINGS:
        classes[np.hypot(gx - cx, gz - cz) < radius] = CLASS_CLEARING
    classes[trail_mask > 0.5] = CLASS_ROAD
    classes[road_mask > 0.45] = CLASS_ROAD
    beach = (height > SEA_LEVEL - 0.5) & (height < BEACH_LEVEL + 1.4) & (into_sea > 0.03)
    classes[beach] = CLASS_SAND
    classes[height < SEA_LEVEL - 0.2] = CLASS_SAND

    return Landform(axis, axis, height.astype("float32"), classes, water)


def _slope(height: np.ndarray) -> np.ndarray:
    dx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) / (2.0 * CELL)
    dz = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) / (2.0 * CELL)
    return np.hypot(dx, dz)


def slope_field(landform: Landform) -> np.ndarray:
    return _slope(landform.height)

"""One deterministic continental surface; territory borders never enter the field.

Coordinates are global metres, x east / z south / y up. All sampling functions
broadcast NumPy inputs, including scalars. River profiles carry surveyed downhill
water levels; broad valley shoulders are cut first and channel beds last. This is
an authored geographic model, not an erosion or atmospheric simulation.
"""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path

import numpy as np

PLAN_PATH = Path(__file__).with_name("diagonal-plan.json")
# Artist-facing sRGB swatches; converted to linear reflectance at export.
BIOME_COLORS = {
    "grassland": (0.39, 0.47, 0.25),
    "woodland": (0.34, 0.41, 0.20),
    "heath": (0.37, 0.39, 0.30),
    "steppe": (0.60, 0.55, 0.33),
    "badland": (0.53, 0.47, 0.41),
    "wetland": (0.31, 0.40, 0.27),
    "limestone": (0.46, 0.50, 0.35),
    "rock": (0.48, 0.49, 0.45),
    "snow": (0.84, 0.87, 0.85),
    "sand": (0.64, 0.59, 0.44),
}


@lru_cache(maxsize=1)
def load_plan():
    """Read the authored plan. Treat the cached result as immutable."""
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def _coords(x, z):
    return np.broadcast_arrays(np.asarray(x, dtype=np.float64), np.asarray(z, dtype=np.float64))


def smoothstep(low, high, value):
    t = np.clip((np.asarray(value) - low) / (high - low), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _hash(ix, iz, seed):
    # Unsigned arithmetic is deliberate; masking avoids platform-sized integers.
    with np.errstate(over="ignore"):
        h = ix.astype(np.uint64) * np.uint64(374761393)
        h = h + iz.astype(np.uint64) * np.uint64(668265263) + np.uint64(seed * 2654435761)
        h = (h ^ (h >> np.uint64(13))) * np.uint64(1274126177)
        h = h ^ (h >> np.uint64(16))
    return (h & np.uint64(0xFFFFFF)).astype(np.float64) / 16777215.0


def _noise(x, z, scale, seed):
    x, z = x / scale, z / scale
    ix, iz = np.floor(x), np.floor(z)
    tx, tz = x - ix, z - iz
    tx = tx * tx * tx * (tx * (tx * 6 - 15) + 10)
    tz = tz * tz * tz * (tz * (tz * 6 - 15) + 10)
    a = _hash(ix, iz, seed) * (1 - tx) + _hash(ix + 1, iz, seed) * tx
    b = _hash(ix, iz + 1, seed) * (1 - tx) + _hash(ix + 1, iz + 1, seed) * tx
    return (a * (1 - tz) + b * tz) * 2 - 1


@lru_cache(maxsize=64)
def _curved_points(points, closed=False):
    """Catmull-Rom horizontal curves; attributes remain monotone between controls."""
    p = np.asarray(points, dtype=np.float64)
    out = []
    count = len(p) if closed else len(p) - 1
    for i in range(count):
        a, b = p[i], p[(i + 1) % len(p)]
        before = p[(i - 1) % len(p)] if closed or i else a * 2 - b
        after = p[(i + 2) % len(p)] if closed or i + 2 < len(p) else b * 2 - a
        for t in np.arange(6, dtype=float) / 6:
            position = 0.5 * ((2 * a[:2]) + (-before[:2] + b[:2]) * t
                              + (2 * before[:2] - 5 * a[:2] + 4 * b[:2] - after[:2]) * t * t
                              + (-before[:2] + 3 * a[:2] - 3 * b[:2] + after[:2]) * t * t * t)
            out.append(np.concatenate((position, a[2:] + t * (b[2:] - a[2:]))))
    out.append(p[0] if closed else p[-1])
    return np.asarray(out)


def curved_points(points, closed=False):
    """Sampled authored curves, also shared by the water and road exporters."""
    return _curved_points(tuple(tuple(p) for p in points), closed)


def _polyline_field(x, z, points):
    """Distance to line and linearly interpolated point attributes at nearest point."""
    points = curved_points(points)
    closest = np.full(x.shape, np.inf)
    nearest = np.zeros(x.shape, dtype=int)
    attrs = [np.zeros(x.shape, dtype=np.float64) for _ in range(points.shape[1] - 2)]
    for segment, (a, b) in enumerate(zip(points[:-1], points[1:])):
        dx, dz = b[0] - a[0], b[1] - a[1]
        t = np.clip(((x - a[0]) * dx + (z - a[1]) * dz) / max(dx * dx + dz * dz, 1e-9), 0, 1)
        d2 = (x - a[0] - t * dx) ** 2 + (z - a[1] - t * dz) ** 2
        use = d2 < closest
        closest = np.minimum(closest, d2)
        nearest = np.where(use, segment, nearest)
        for i in range(len(attrs)):
            attrs[i] = np.where(use, a[i + 2] + t * (b[i + 2] - a[i + 2]), attrs[i])
    # Extend the surveyed attributes smoothly across a bend. Choosing only
    # the nearest straight segment otherwise introduces small diagonal steps
    # in bank elevation even when the river's centreline is continuous. The
    # blend tends to zero on that centreline, preserving its hydraulic levels.
    bandwidth = np.maximum(closest * .12, 1e-12)
    sums = [np.zeros_like(value) for value in attrs]
    weights = np.zeros_like(closest)
    for offset in (-2, -1, 0, 1, 2):
        index = nearest + offset
        valid = (index >= 0) & (index < len(points) - 1)
        index = np.clip(index, 0, len(points) - 2)
        a, b = points[index], points[index + 1]
        dx, dz = b[..., 0] - a[..., 0], b[..., 1] - a[..., 1]
        projected = ((x-a[..., 0])*dx+(z-a[..., 1])*dz)/np.maximum(dx*dx+dz*dz, 1e-9)
        t = np.clip(projected, 0, 1)
        d2 = (x-a[..., 0]-t*dx)**2+(z-a[..., 1]-t*dz)**2
        weight = np.exp(-np.maximum(0, d2-closest)/bandwidth) * valid
        weights += weight
        # Local tangent extrapolation keeps a straight downhill reach planar;
        # clamping each tiny segment would introduce a repeated stair profile.
        attribute_t = np.where(index == 0, np.maximum(0, projected), projected)
        attribute_t = np.where(index == len(points)-2, np.minimum(1, attribute_t), attribute_t)
        for i in range(len(attrs)):
            sums[i] += weight * (a[..., i+2]+attribute_t*(b[..., i+2]-a[..., i+2]))
    attrs = [value / weights for value in sums]
    return (np.sqrt(closest), *attrs)


def coastline_distance(x, z, plan=None):
    """Signed distance to mainland coast, positive inland; islands are separate."""
    plan = load_plan() if plan is None else plan
    x, z = _coords(x, z)
    points = curved_points(plan["coastline"], closed=True)[:-1]
    inside = np.zeros(x.shape, dtype=bool)
    minimum = np.full(x.shape, np.inf)
    for a, b in zip(points, np.roll(points, -1, axis=0)):
        dx, dz = b - a
        t = np.clip(((x - a[0]) * dx + (z - a[1]) * dz) / (dx * dx + dz * dz), 0, 1)
        minimum = np.minimum(minimum, (x - a[0] - dx * t) ** 2 + (z - a[1] - dz * t) ** 2)
        if abs(dz) > 1e-12:
            crosses = ((a[1] > z) != (b[1] > z)) & (x < a[0] + (z - a[1]) * dx / dz)
            inside ^= crosses
    # Broad low-amplitude irregularity avoids a visibly polygonal shoreline.
    irregularity = 6.5 * _noise(x, z, 82, plan["seed"] + 41)
    return np.sqrt(minimum) * np.where(inside, 1.0, -1.0) + irregularity


def _ellipse_distance(x, z, shape):
    dx, dz = x - shape["center"][0], z - shape["center"][1]
    angle = shape.get("angle", 0)
    u = dx * np.cos(angle) + dz * np.sin(angle)
    v = -dx * np.sin(angle) + dz * np.cos(angle)
    rx, rz = shape["radii"]
    return np.sqrt((u / rx) ** 2 + (v / rz) ** 2)


def _natural_height(x, z, plan):
    coast = coastline_distance(x, z, plan)
    inland = smoothstep(-8, 100, coast)
    # Shelf and shore profile meet sea level continuously, with no rectangular base.
    h = 23 * np.tanh(coast / 94)
    h += inland * (3.2 * _noise(x, z, 235, plan["seed"]) + 1.1 * _noise(x, z, 67, plan["seed"] + 1))
    for ridge in plan["ridges"]:
        # Integrating overlapping segments produces a continuous ridge without
        # the diagonal attribute discontinuities of nearest-segment projection.
        p = curved_points(ridge["points"])
        chain = np.zeros_like(h)
        for a, b in zip(p[:-1], p[1:]):
            mid = (a + b) * 0.5
            ds = np.hypot(b[0] - a[0], b[1] - a[1])
            distance2 = (x - mid[0]) ** 2 + (z - mid[1]) ** 2
            height, width = mid[2], mid[3]
            crest = np.exp(-distance2 / width ** 2) / width
            shoulder_width = width * ridge["foothill_width"]
            shoulder = np.exp(-distance2 / shoulder_width ** 2) / shoulder_width
            chain += height * ds / np.sqrt(np.pi) * (crest + ridge["foothill_height"] * shoulder)
        long_variation = 1 + 0.08 * _noise(x, z, 130, plan["seed"] + 9)
        h += inland * chain * long_variation
    # A basin floor leading to the delta, with a broad upper shoulder.
    floodplain = np.exp(-(((x - 510) / 340) ** 2 + ((z - 1075) / 235) ** 2))
    h = h * (1 - floodplain * 0.66)
    # Islands rise from the same shelf. Smooth ellipses are warped at landscape scale.
    for island in plan["islands"]:
        r = _ellipse_distance(x, z, island) + 0.12 * _noise(x, z, 47, plan["seed"] + 51)
        island_h = island["height"] * (1 - r * r)
        h = np.maximum(h, island_h)
    return h


def _drainage_height(x, z, h, plan):
    # First grade valleys, then cut beds. Doing this in two passes prevents a
    # tributary shoulder from filling its receiving river at a confluence.
    fields = []
    for river in plan["rivers"]:
        distance, level = _polyline_field(x, z, river["points"])
        width, valley = river["width"], river["valley_width"]
        blend = 1 - smoothstep(width, valley, distance)
        valley_target = level + river["bank_height"] + 0.035 * distance
        h = np.minimum(h, h * (1 - blend) + valley_target * blend)
        fields.append((river, distance, level))
    for river, distance, level in fields:
        width = river["width"]
        # A low bank shelf gives a river somewhere to flood before its valley
        # rises. The former narrow bed blend climbed straight into the four-
        # metre valley shoulder, making the two banks read as parallel walls.
        # Centreline levels/depth and the authored drainage remain unchanged.
        shelf = river.get("bank_shelf_width", max(10.0, width * 1.5))
        shelf_height = min(river["bank_height"], river.get("bank_shelf_height", 0.65))
        terrace_end = width + shelf
        join = max(18.0, width * 1.5)
        bed = level - river["depth"] * (1 - smoothstep(0, width, distance))
        bank = level + shelf_height * smoothstep(width, terrace_end, distance)
        profile = np.where(distance <= width, bed, bank)
        blend = 1 - smoothstep(terrace_end, terrace_end + join, distance)
        h = h * (1 - blend) + np.minimum(h, profile) * blend
    for lake in plan.get("lakes", []):
        r = _ellipse_distance(x, z, lake)
        blend = 1 - smoothstep(0.8, 1.55, r)
        bed = lake["level"] - lake["depth"] * (1 - smoothstep(0, 1.3, r))
        h = h * (1 - blend) + np.minimum(h, bed) * blend
    return h


def retained_affine(transform):
    """A retained transform as (translation[3], scale_xz[2], about_xz[2]): a list is one rigid translation of the
    whole source layout; a dict carries 'translation' and may squeeze the layout north-south ('squeeze_z', a factor
    in (0, 1], about the source row 'about_z'), so a source whose crown would stand beyond the world's edge at
    full length keeps its crown inside it. Optional 'datum': 'ground' stands each compound on the composed relief."""
    if isinstance(transform, dict):
        translation = np.asarray(transform["translation"], float)
        scale = np.array([1.0, float(transform.get("squeeze_z", 1.0))])
        about = np.array([0.0, float(transform.get("about_z", 0.0))])
    else:
        translation = np.asarray(transform, float); scale = np.ones(2); about = np.zeros(2)
    if translation.shape != (3,) or not np.isfinite(translation).all():
        raise ValueError("retained transform: the translation must contain three finite metres")
    if not 0.0 < scale[1] <= 1.0:
        raise ValueError("retained transform: squeeze_z must lie in (0, 1]")
    return translation, scale, about


def retained_map_xz(transform, points):
    """Source-frame xz points carried to continent metres by a retained transform."""
    translation, scale, about = retained_affine(transform)
    return translation[[0, 2]] + about + (np.asarray(points, float) - about) * scale


@lru_cache(maxsize=4)
def _relief_samples(name):
    data = np.load(PLAN_PATH.with_name(name) if "/" not in name else PLAN_PATH.parent / name)
    return (np.asarray(data["x"], float), np.asarray(data["z"], float), np.asarray(data["height"], float))


def _relief_height(x, z, source):
    """(height, weight) of a sampled relief source at global x, z: bilinear inside its crop, whole there, and
    beyond the crop's edge the edge's own height continues as a shoulder fading out over ``feather`` metres."""
    sx, sz, sh = _relief_samples(source["samples"])
    tx, ty, tz = source["translation"]
    # The same north-south squeeze the territory's retained transform carries,
    # so the relief stands under the layout it was surveyed with.
    squeeze = float(source.get("squeeze_z", 1.0)); about = float(source.get("about_z", 0.0))
    lx, lz = x - tx, about + (z - tz - about) / squeeze
    x0, z0, x1, z1 = source.get("crop", [sx[0], sz[0], sx[-1], sz[-1]])
    # Distance outside the crop rectangle (Euclidean, so the shoulder rounds the corners).
    outside = np.hypot(np.maximum(np.maximum(x0 - lx, lx - x1), 0.0), np.maximum(np.maximum(z0 - lz, lz - z1), 0.0))
    weight = 1.0 - smoothstep(0.0, float(source.get("feather", 40.0)), outside)
    cx = np.clip(lx, max(x0, sx[0]), min(x1, sx[-1])); cz = np.clip(lz, max(z0, sz[0]), min(z1, sz[-1]))
    ix = np.clip(np.searchsorted(sx, cx) - 1, 0, len(sx) - 2); iz = np.clip(np.searchsorted(sz, cz) - 1, 0, len(sz) - 2)
    fx = (cx - sx[ix]) / (sx[ix + 1] - sx[ix]); fz = (cz - sz[iz]) / (sz[iz + 1] - sz[iz])
    h = (sh[iz, ix] * (1 - fx) * (1 - fz) + sh[iz, ix + 1] * fx * (1 - fz)
         + sh[iz + 1, ix] * (1 - fx) * fz + sh[iz + 1, ix + 1] * fx * fz)
    # Vertical exaggeration about a pivot in the source's own heights: the
    # base (a gate court) keeps its level while the relief above it grows.
    pivot = float(source.get("pivot", 0.0))
    h = pivot + (h - pivot) * float(source.get("scale", 1.0))
    return h + ty, weight


def height_at(x, z, plan=None):
    """Evaluate the shared ground height without reference to territory ownership."""
    plan = load_plan() if plan is None else plan
    x, z = _coords(x, z)
    h = _drainage_height(x, z, _natural_height(x, z, plan), plan)
    # Legacy relief sources: a territory's old map relief placed by its retained
    # transform replaces the plan landform inside a crop that leaves the old
    # map's edge walls out, feathered at the crop's edge and damped by the coast.
    for source in plan.get("relief_sources", []):
        relief, weight = _relief_height(x, z, source)
        weight = weight * smoothstep(-8, float(source.get("coast_feather", 60.0)), coastline_distance(x, z, plan))
        h = h * (1 - weight) + relief * weight
    # Dry basins (cirques, corries, hanging hollows): an ellipse carved into
    # the crest after drainage, its floor rising as a shallow bowl toward the
    # rim and feathered over it; no water stands in it.
    for basin in plan.get("basins", []):
        r = _ellipse_distance(x, z, basin)
        blend = 1 - smoothstep(basin.get("rim", 0.85), basin.get("feather", 1.5), r)
        floor = basin["floor"] + basin.get("bowl", 6.0) * np.clip(r, 0, 1.5) ** 2
        h = h * (1 - blend) + np.minimum(h, floor) * blend
    for pad in plan.get("foundations", []):
        distance = np.hypot(x - pad["center"][0], z - pad["center"][1])
        blend = 1 - smoothstep(pad["radius"], pad["radius"] + pad.get("feather", 24), distance)
        h = h * (1 - blend) + pad["elevation"] * blend
    return h


def water_fields(x=None, z=None, height=None, plan=None):
    """Return water definitions, or sampled mask/surface/depth and river distance.

    Calling without coordinates returns the plan's rivers, lakes and sea level.
    ``surface`` is sea level outside channels; ``mask`` decides where to render.
    River widths in the plan are half-widths, measured from the centreline.
    """
    plan = load_plan() if plan is None else plan
    if x is None and z is None:
        return {key: plan[key] for key in ("rivers", "lakes", "sea_level")}
    if x is None or z is None:
        raise ValueError("Supply both x and z, or neither.")
    x, z = _coords(x, z)
    h = height_at(x, z, plan) if height is None else np.broadcast_to(height, x.shape)
    level = np.full(x.shape, float(plan["sea_level"]))
    river_mask = np.zeros(x.shape, dtype=bool)
    minimum = np.full(x.shape, np.inf)
    for river in plan["rivers"]:
        distance, profile = _polyline_field(x, z, river["points"])
        in_channel = distance <= river["width"]
        level = np.maximum(level, np.where(in_channel, profile, plan["sea_level"]))
        river_mask |= in_channel
        minimum = np.minimum(minimum, distance)
    for lake in plan.get("lakes", []):
        in_lake = _ellipse_distance(x, z, lake) <= 1.0
        level = np.maximum(level, np.where(in_lake, lake["level"], plan["sea_level"]))
        river_mask |= in_lake
    mask = h < level - 0.015
    return {"mask": mask, "surface": level, "depth": np.maximum(0, level - h),
            "river_mask": river_mask & mask, "sea_mask": (h < plan["sea_level"] - 0.015) & ~river_mask,
            "river_distance": minimum}


def biome_weights(x, z, height=None, plan=None):
    """Smooth material/plant community weights; no named-region boundary masks."""
    plan = load_plan() if plan is None else plan
    x, z = _coords(x, z)
    h = height_at(x, z, plan) if height is None else np.broadcast_to(height, x.shape)
    wobble = 21 * _noise(x, z, 128, plan["seed"] + 67)
    # The dry lee is east of the spine. Southern maritime warmth closes that
    # rain shadow gradually before the limestone coast.
    spine_x = 390 + z * 0.57
    dry = smoothstep(-45, 270, x - spine_x + wobble) * (1 - smoothstep(820, 1260, z))
    warm = smoothstep(700, 1430, z + wobble)
    cold = 1 - smoothstep(95, 610, z)
    woodland = np.exp(-(((x - 475 + wobble) / 300) ** 2 + ((z - 580) / 285) ** 2))
    moor = np.exp(-(((x - 210) / 250) ** 2 + ((z - 440 + wobble) / 330) ** 2))
    mineral = np.exp(-(((x - 980) / 255) ** 2 + ((z - 390 + wobble) / 235) ** 2)) * dry
    water = water_fields(x, z, height=h, plan=plan)
    damp = (1 - smoothstep(9, 67, water["river_distance"])) * (1 - smoothstep(22, 85, h))
    delta = np.exp(-(((x - 510) / 250) ** 2 + ((z - 1140) / 235) ** 2))
    limestone = warm * smoothstep(740, 1170, x) * smoothstep(15, 95, h)
    snowline = 131 + smoothstep(250, 850, z) * 82
    snow = smoothstep(snowline - 9, snowline + 16, h + _noise(x, z, 70, plan["seed"] + 71) * 4)
    rock = smoothstep(67, 142, h) * (1 - snow)
    sand = (1 - smoothstep(1.0, 8.5, h)) * (1 - smoothstep(35, 105, water["river_distance"])) * 0.5
    sand = np.maximum(sand, (1 - smoothstep(0.4, 7.0, h)) * 0.8)
    scores = {
        "grassland": np.full(x.shape, 0.70) * (1 - dry * 0.4),
        "woodland": woodland * 1.9 * (1 - dry) + warm * (1 - dry) * 0.68,
        "heath": moor * 1.6 * (0.7 + 0.3 * cold),
        "steppe": dry * 2.3 * (1 - mineral * 0.4),
        "badland": mineral * 2.4,
        "wetland": (damp * 1.5 + delta * 0.6) * (1 - dry * 0.6),
        "limestone": limestone * 1.5,
        "rock": rock * 2.0,
        "snow": snow * 20.0,
        "sand": sand,
    }
    total = np.sum(np.stack(list(scores.values()), axis=-1), axis=-1)
    return {name: value / total for name, value in scores.items()}


def terrain_color(x, z, height=None, plan=None):
    """Linear RGB vertex colours in [0, 1], with broad restrained soil variation."""
    plan = load_plan() if plan is None else plan
    x, z = _coords(x, z)
    weights = biome_weights(x, z, height=height, plan=plan)
    rgb = sum(weights[name][..., None] * np.asarray(color)**2.2 for name, color in BIOME_COLORS.items())
    variation = 1 + 0.047 * _noise(x, z, 39, plan["seed"] + 81) + 0.022 * _noise(x, z, 13, plan["seed"] + 82)
    return np.clip(rgb * variation[..., None], 0, 1)


def vegetation_fields(x, z, height=None, plan=None):
    """Reusable regional ecology controls for deterministic object scattering."""
    plan = load_plan() if plan is None else plan
    x, z = _coords(x, z)
    h = height_at(x, z, plan) if height is None else np.broadcast_to(height, x.shape)
    weights = biome_weights(x, z, height=h, plan=plan)
    water = water_fields(x, z, height=h, plan=plan)
    grove = 0.35 + 0.65 * smoothstep(-0.4, 0.6, _noise(x, z, 49, plan["seed"] + 92))
    density = (weights["woodland"] * 1.45 + weights["wetland"] * 0.35 + weights["limestone"] * 0.55) * grove
    density *= 1 - smoothstep(105, 157, h)
    density = np.where(water["mask"] | (h < 0.7), 0.0, np.clip(density, 0, 0.8))
    return {"tree_density": density, "wetness": weights["wetland"],
            "deciduous": weights["woodland"], "conifer": weights["rock"] * (1 - weights["snow"]),
            "dryness": weights["steppe"] + weights["badland"]}

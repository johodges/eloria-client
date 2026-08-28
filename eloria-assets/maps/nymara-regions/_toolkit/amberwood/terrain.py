"""Sculpted terrain for Amberwood.

The heightfield is authored with explicit shaping operators - ridges, basins,
carved watercourses, graded roads, coastal shelves - rather than left as raw
noise, so the aerial composition of the concept survives into the runtime mesh.
Surface material is assigned per grid cell, and the mesh is emitted as one
watertight sub-mesh per material: adjacent sub-meshes share identical vertex
positions, so the terrain has material variety with no cracks and no overlap.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import mesh as M
from . import noise as N

# surface classes
FOREST = 0
PATH = 1
PAVING = 2
SHORE = 3
ROCK = 4
SCORCHED = 5
MEADOW = 6
SNOW = 7
ICE = 8
MARBLE = 9
TURF = 10

SURFACE_NAMES = {
    FOREST: "ForestFloor", PATH: "Trail", PAVING: "Paving", SHORE: "Shore",
    ROCK: "Rock", SCORCHED: "Ash", MEADOW: "Meadow",
    SNOW: "Snow", ICE: "Ice", MARBLE: "Marble", TURF: "AlpineTurf",
}
SURFACE_MATERIALS = {
    FOREST: "forest_floor", PATH: "leaf_path", PAVING: "cobble_paving",
    SHORE: "shore_shingle", ROCK: "cliff_rock", SCORCHED: "scorched_ground",
    MEADOW: "meadow_grass",
    SNOW: "snow_pack", ICE: "glacier_ice", MARBLE: "veined_marble",
    TURF: "alpine_turf",
}


def _smoothstep(edge0: float, edge1: float, x: np.ndarray) -> np.ndarray:
    """Smoothstep that also works when edge1 < edge0 (a descending ramp)."""
    span = edge1 - edge0
    if abs(span) < 1e-9:
        span = 1e-9 if span >= 0 else -1e-9
    t = np.clip((x - edge0) / span, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _polyline_distance(px: np.ndarray, pz: np.ndarray,
                       points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Distance from each sample to a polyline, plus the arc-length parameter."""
    best = np.full(px.shape, 1e9)
    best_t = np.zeros(px.shape)
    lengths = np.concatenate([[0.0], np.cumsum(
        np.linalg.norm(np.diff(points, axis=0), axis=1))])
    total = max(lengths[-1], 1e-9)
    for i in range(points.shape[0] - 1):
        a = points[i]
        b = points[i + 1]
        ab = b - a
        denominator = float(np.dot(ab, ab))
        if denominator < 1e-12:
            continue
        t = ((px - a[0]) * ab[0] + (pz - a[1]) * ab[1]) / denominator
        t = np.clip(t, 0.0, 1.0)
        cx = a[0] + ab[0] * t
        cz = a[1] + ab[1] * t
        d = np.hypot(px - cx, pz - cz)
        closer = d < best
        best = np.where(closer, d, best)
        best_t = np.where(closer, (lengths[i] + t * math.hypot(*ab)) / total, best_t)
    return best, best_t


@dataclass
class Terrain:
    x0: float
    z0: float
    size_x: float
    size_z: float
    cell: float = 1.0

    def __post_init__(self) -> None:
        self.cols = int(round(self.size_x / self.cell)) + 1
        self.rows = int(round(self.size_z / self.cell)) + 1
        self.xs = self.x0 + np.arange(self.cols) * self.cell
        self.zs = self.z0 + np.arange(self.rows) * self.cell
        self.gx, self.gz = np.meshgrid(self.xs, self.zs)
        self.height = np.zeros((self.rows, self.cols))
        self.surface = np.full((self.rows, self.cols), FOREST, dtype=np.int32)
        self.water_depth = np.zeros((self.rows, self.cols))
        self.tree_block = np.zeros((self.rows, self.cols), dtype=bool)
        self.wet = np.zeros((self.rows, self.cols))

    # -- shaping ----------------------------------------------------------
    def base_noise(self, amplitude: float, frequency: float, seed: int,
                   octaves: int = 5, warp: float = 0.0) -> None:
        u = self.gx * frequency
        v = self.gz * frequency
        field = N.warped_fbm(u, v, warp=warp, octaves=octaves, seed=seed) if warp > 0 \
            else N.fbm(u, v, octaves=octaves, seed=seed)
        self.height += (field - 0.5) * 2.0 * amplitude

    def add_slope(self, direction: tuple[float, float], gain: float,
                  origin: tuple[float, float] = (0.0, 0.0)) -> None:
        d = np.asarray(direction, dtype=np.float64)
        d /= max(np.linalg.norm(d), 1e-9)
        self.height += ((self.gx - origin[0]) * d[0] + (self.gz - origin[1]) * d[1]) * gain

    def add_dome(self, center: tuple[float, float], radius: float, height: float,
                 power: float = 2.0, noise_seed: int | None = None,
                 noise_amount: float = 0.0) -> None:
        d = np.hypot(self.gx - center[0], self.gz - center[1])
        if noise_seed is not None and noise_amount > 0.0:
            d = d + (N.fbm(self.gx * 0.05, self.gz * 0.05, seed=noise_seed) - 0.5) \
                * 2.0 * noise_amount * radius
        falloff = np.clip(1.0 - d / max(radius, 1e-6), 0.0, 1.0) ** power
        self.height += falloff * height

    def add_ridge(self, points, height: float, width: float, seed: int = 0,
                  roughness: float = 0.35, power: float = 1.6) -> None:
        points = np.asarray(points, dtype=np.float64)
        d, t = _polyline_distance(self.gx, self.gz, points)
        wobble = (N.fbm(self.gx * 0.045, self.gz * 0.045, seed=seed) - 0.5) * 2.0
        effective = width * (1.0 + roughness * wobble)
        profile = np.clip(1.0 - d / np.maximum(effective, 1e-6), 0.0, 1.0) ** power
        crest = 0.72 + 0.42 * N.fbm(t * 9.0, t * 3.0, seed=seed + 5)
        self.height += profile * height * crest

    def carve_channel(self, points, width: float, depth: float, bank: float = 2.4,
                      seed: int = 0, floor_height=None) -> np.ndarray:
        """Cut a watercourse. Returns the channel mask (1 at the thalweg)."""
        points = np.asarray(points, dtype=np.float64)
        d, t = _polyline_distance(self.gx, self.gz, points)
        wobble = (N.fbm(self.gx * 0.09, self.gz * 0.09, seed=seed) - 0.5) * 2.0
        effective = width * (1.0 + 0.30 * wobble)
        core = np.clip(1.0 - d / np.maximum(effective, 1e-6), 0.0, 1.0)
        outer = np.clip(1.0 - d / np.maximum(effective * bank, 1e-6), 0.0, 1.0)
        cut = core ** 0.8 * depth + (outer ** 2.4) * depth * 0.45
        if floor_height is not None:
            target = np.interp(t, np.linspace(0.0, 1.0, len(floor_height)), floor_height)
            blend = core ** 0.7
            self.height = self.height * (1.0 - blend) + target * blend
        else:
            self.height -= cut
        return core

    def grade_path(self, points, width: float, heights=None, shoulder: float = 2.2,
                   surface: int = PATH, seed: int = 0,
                   flatten: float = 0.9) -> np.ndarray:
        """Grade a road or trail: level the corridor and mark its surface class."""
        points = np.asarray(points, dtype=np.float64)
        d, t = _polyline_distance(self.gx, self.gz, points)
        wobble = (N.fbm(self.gx * 0.11, self.gz * 0.11, seed=seed) - 0.5) * 2.0
        effective = width * (1.0 + 0.22 * wobble)
        core = np.clip(1.0 - d / np.maximum(effective, 1e-6), 0.0, 1.0)
        outer = np.clip(1.0 - d / np.maximum(effective * shoulder, 1e-6), 0.0, 1.0)
        if heights is not None:
            target = np.interp(t, np.linspace(0.0, 1.0, len(heights)), heights)
        else:
            target = self._smoothed_along(points, d, t)
        blend = np.clip(core ** 0.55 * flatten + outer ** 3.0 * 0.35, 0.0, 1.0)
        self.height = self.height * (1.0 - blend) + target * blend
        mask = core > 0.32
        self.surface = np.where(mask, surface, self.surface)
        self.tree_block |= outer > 0.22
        return core

    def _smoothed_along(self, points: np.ndarray, d: np.ndarray, t: np.ndarray) -> np.ndarray:
        """Sample existing height along the polyline and smooth it into a grade."""
        samples = []
        lengths = np.concatenate([[0.0], np.cumsum(
            np.linalg.norm(np.diff(points, axis=0), axis=1))])
        total = max(lengths[-1], 1e-9)
        count = 48
        for i in range(count):
            s = i / (count - 1) * total
            index = int(np.searchsorted(lengths, s, side="right") - 1)
            index = min(max(index, 0), points.shape[0] - 2)
            span = max(lengths[index + 1] - lengths[index], 1e-9)
            local = (s - lengths[index]) / span
            p = points[index] + (points[index + 1] - points[index]) * local
            samples.append(self.height_at(p[0], p[1]))
        samples = np.asarray(samples)
        kernel = np.ones(9) / 9.0
        padded = np.pad(samples, (4, 4), mode="edge")
        smoothed = np.convolve(padded, kernel, mode="valid")
        return np.interp(t, np.linspace(0.0, 1.0, count), smoothed)

    def plateau(self, center: tuple[float, float], radius: float, height: float,
                edge: float = 6.0, surface: int | None = None,
                seed: int = 0, irregular: float = 0.18) -> np.ndarray:
        d = np.hypot(self.gx - center[0], self.gz - center[1])
        if irregular > 0.0:
            d = d * (1.0 + irregular * (N.fbm(self.gx * 0.07, self.gz * 0.07,
                                              seed=seed) - 0.5) * 2.0)
        blend = 1.0 - _smoothstep(radius - edge, radius + edge, d)
        self.height = self.height * (1.0 - blend) + height * blend
        if surface is not None:
            self.surface = np.where(blend > 0.55, surface, self.surface)
        return blend

    def terrace(self, center: tuple[float, float], radius: float, height: float,
                surface: int | None = None) -> None:
        """Hard-edged terrace with a retaining lip - reads as built, not eroded."""
        d = np.hypot(self.gx - center[0], self.gz - center[1])
        inside = d < radius
        self.height = np.where(inside, height, self.height)
        if surface is not None:
            self.surface = np.where(inside, surface, self.surface)
        self.tree_block |= d < radius + 1.5

    def rect_terrace(self, center: tuple[float, float], half_x: float, half_z: float,
                     height: float, rotation: float = 0.0,
                     surface: int | None = None) -> None:
        dx = self.gx - center[0]
        dz = self.gz - center[1]
        c, s = math.cos(-rotation), math.sin(-rotation)
        rx = dx * c - dz * s
        rz = dx * s + dz * c
        inside = (np.abs(rx) <= half_x) & (np.abs(rz) <= half_z)
        self.height = np.where(inside, height, self.height)
        if surface is not None:
            self.surface = np.where(inside, surface, self.surface)
        self.tree_block |= (np.abs(rx) <= half_x + 1.5) & (np.abs(rz) <= half_z + 1.5)

    def sea_shelf(self, shore_x, depth: float = 14.0, slope: float = 0.22) -> None:
        """Push everything west of the shoreline below sea level."""
        shore = shore_x(self.gz) if callable(shore_x) else np.full(self.gz.shape, shore_x)
        offshore = np.clip(shore - self.gx, 0.0, None)
        self.height = np.where(
            self.gx < shore,
            np.minimum(self.height, -offshore * slope * (1.0 + offshore * 0.012)),
            self.height)
        self.height = np.maximum(self.height, -depth)

    def clamp_edges(self, margin: float, wall_height: float,
                    sides: tuple[str, ...] = ("west", "east", "north", "south")) -> None:
        """Raise a rim outside the playable footprint so nothing reaches a void.

        Sides can be omitted where another natural boundary already closes the
        world - Amberwood leaves the west open because the sea closes it.
        """
        rim = np.zeros_like(self.height)
        if "west" in sides:
            rim = np.maximum(rim, _smoothstep(self.x0 + margin, self.x0, self.gx))
        if "east" in sides:
            rim = np.maximum(rim, _smoothstep(self.x0 + self.size_x - margin,
                                              self.x0 + self.size_x, self.gx))
        if "south" in sides:
            rim = np.maximum(rim, _smoothstep(self.z0 + self.size_z - margin,
                                              self.z0 + self.size_z, self.gz))
        if "north" in sides:
            rim = np.maximum(rim, _smoothstep(self.z0 + margin, self.z0, self.gz))
        self.height += rim * wall_height

    def smooth(self, iterations: int = 1, weight: float = 0.5,
               mask: np.ndarray | None = None) -> None:
        for _ in range(iterations):
            padded = np.pad(self.height, 1, mode="edge")
            average = (padded[:-2, 1:-1] + padded[2:, 1:-1]
                       + padded[1:-1, :-2] + padded[1:-1, 2:]) * 0.25
            blended = self.height * (1.0 - weight) + average * weight
            self.height = np.where(mask, blended, self.height) if mask is not None else blended

    def erode(self, iterations: int = 24, strength: float = 0.35) -> None:
        """Cheap thermal erosion: shed material off slopes steeper than repose."""
        for _ in range(iterations):
            padded = np.pad(self.height, 1, mode="edge")
            deltas = [padded[:-2, 1:-1], padded[2:, 1:-1], padded[1:-1, :-2], padded[1:-1, 2:]]
            total = np.zeros_like(self.height)
            for neighbour in deltas:
                difference = self.height - neighbour
                total += np.clip(difference - self.cell * 0.9, 0.0, None)
            self.height -= total * strength * 0.25

    # -- queries ----------------------------------------------------------
    def height_at(self, x, z):
        fx = np.clip((np.asarray(x, dtype=np.float64) - self.x0) / self.cell,
                     0, self.cols - 1.001)
        fz = np.clip((np.asarray(z, dtype=np.float64) - self.z0) / self.cell,
                     0, self.rows - 1.001)
        x0 = fx.astype(int) if np.ndim(fx) else int(fx)
        z0 = fz.astype(int) if np.ndim(fz) else int(fz)
        tx = fx - x0
        tz = fz - z0
        h00 = self.height[z0, x0]
        h10 = self.height[z0, x0 + 1]
        h01 = self.height[z0 + 1, x0]
        h11 = self.height[z0 + 1, x0 + 1]
        return (h00 * (1 - tx) * (1 - tz) + h10 * tx * (1 - tz)
                + h01 * (1 - tx) * tz + h11 * tx * tz)

    def slope_at(self, x, z):
        eps = self.cell
        dx = self.height_at(np.asarray(x) + eps, z) - self.height_at(np.asarray(x) - eps, z)
        dz = self.height_at(x, np.asarray(z) + eps) - self.height_at(x, np.asarray(z) - eps)
        return np.hypot(dx, dz) / (2.0 * eps)

    def surface_at(self, x, z) -> np.ndarray:
        cx = np.clip(np.round((np.asarray(x) - self.x0) / self.cell).astype(int),
                     0, self.cols - 1)
        cz = np.clip(np.round((np.asarray(z) - self.z0) / self.cell).astype(int),
                     0, self.rows - 1)
        return self.surface[cz, cx]

    def blocked_at(self, x, z) -> np.ndarray:
        cx = np.clip(np.round((np.asarray(x) - self.x0) / self.cell).astype(int),
                     0, self.cols - 1)
        cz = np.clip(np.round((np.asarray(z) - self.z0) / self.cell).astype(int),
                     0, self.rows - 1)
        return self.tree_block[cz, cx]

    def mark_blocked_disc(self, center, radius: float) -> None:
        d = np.hypot(self.gx - center[0], self.gz - center[1])
        self.tree_block |= d < radius

    def assign_surface_by_rule(self, sea_level: float = 0.0) -> None:
        """Rock on steep ground, shore near the water line, keeping authored classes."""
        gradient_z, gradient_x = np.gradient(self.height, self.cell)
        slope = np.hypot(gradient_x, gradient_z)
        authored = np.isin(self.surface, [PATH, PAVING, SCORCHED, MEADOW])
        rocky = (slope > 1.05) & ~authored
        self.surface = np.where(rocky, ROCK, self.surface)
        shore_band = (self.height < sea_level + 1.6) & (self.height > sea_level - 6.0) \
            & ~authored
        noise = N.fbm(self.gx * 0.22, self.gz * 0.22, seed=4242)
        self.surface = np.where(shore_band & (noise > 0.34), SHORE, self.surface)
        self.surface = np.where(self.height < sea_level - 1.0, SHORE, self.surface)

    def dither_boundaries(self, seed: int = 99, amount: float = 0.55) -> None:
        """Break straight material borders into an organic edge."""
        noise = N.fbm(self.gx * 0.55, self.gz * 0.55, seed=seed)
        padded = np.pad(self.surface, 1, mode="edge")
        neighbours = np.stack([padded[:-2, 1:-1], padded[2:, 1:-1],
                               padded[1:-1, :-2], padded[1:-1, 2:]])
        different = neighbours != self.surface[None, :, :]
        boundary = different.any(axis=0)
        pick = np.where(noise > 1.0 - amount * 0.5, 1, 0)
        candidate = np.where(pick > 0, neighbours[0], neighbours[3])
        swap = boundary & (noise > 0.62)
        # never dither a built surface away from a road or courtyard
        protect = np.isin(self.surface, [PAVING])
        self.surface = np.where(swap & ~protect, candidate, self.surface)

    # -- export -----------------------------------------------------------
    def build_meshes(self, uv_scale: float = 0.30,
                     name_prefix: str = "Terrain_",
                     materials: dict[int, str] | None = None) -> dict[str, M.Mesh]:
        """One sub-mesh per surface class; shared vertices means no cracks.

        `materials` overrides the surface-class to material mapping for regions
        whose ground is not Amberwood's. A snow region's PATH is not a leaf
        path, and the class itself is what the terrain operators speak in.
        """
        table = dict(SURFACE_MATERIALS)
        if materials:
            table.update(materials)
        out: dict[str, M.Mesh] = {}
        for surface_id, label in SURFACE_NAMES.items():
            cells = self.surface == surface_id
            if not cells.any():
                continue
            # a cell mask on the vertex grid: keep vertices of kept cells
            vertex_mask = np.zeros((self.rows, self.cols), dtype=bool)
            vertex_mask[:-1, :-1] |= cells[:-1, :-1]
            vertex_mask[1:, :-1] |= cells[:-1, :-1]
            vertex_mask[:-1, 1:] |= cells[:-1, :-1]
            vertex_mask[1:, 1:] |= cells[:-1, :-1]
            piece = M.heightfield(self.height, self.x0, self.z0, self.cell,
                                  uv_scale=uv_scale,
                                  material=table[surface_id],
                                  mask=vertex_mask)
            piece = _compact(piece)
            if piece.triangle_count == 0:
                continue
            piece.recompute_normals(180.0)
            out[f"{name_prefix}{label}"] = piece
        return out


def _compact(mesh: M.Mesh) -> M.Mesh:
    """Drop vertices no triangle references."""
    if mesh.triangle_count == 0:
        return M.Mesh(material=mesh.material)
    used = np.unique(mesh.indices)
    remap = np.full(mesh.vertex_count, -1, dtype=np.int64)
    remap[used] = np.arange(used.shape[0])
    return M.Mesh(mesh.positions[used], mesh.normals[used], mesh.uvs[used],
                  None if mesh.colors is None else mesh.colors[used],
                  remap[mesh.indices], mesh.material)


def water_plane(terrain: Terrain, level: float, x0: float, z0: float, x1: float, z1: float,
                material: str = "water_sea", cell: float = 4.0,
                only_below: bool = True, margin: float = 0.35,
                outside_is_water: bool = False) -> M.Mesh:
    """Water surface clipped to where the terrain is actually below the level.

    `outside_is_water` keeps the surface where the sample falls outside the
    terrain grid, so the open sea can run past the authored coast to a horizon.
    """
    cols = max(int(round((x1 - x0) / cell)) + 1, 2)
    rows = max(int(round((z1 - z0) / cell)) + 1, 2)
    xs = np.linspace(x0, x1, cols)
    zs = np.linspace(z0, z1, rows)
    gx, gz = np.meshgrid(xs, zs)
    heights = np.full((rows, cols), level)
    mask = None
    if only_below:
        ground = terrain.height_at(gx, gz)
        mask = ground < level - margin
        if outside_is_water:
            outside = ((gx < terrain.x0 + 1.0) | (gx > terrain.x0 + terrain.size_x - 1.0)
                       | (gz < terrain.z0 + 1.0) | (gz > terrain.z0 + terrain.size_z - 1.0))
            mask = mask | outside
    piece = M.heightfield(heights, x0, z0, cell, uv_scale=0.09, material=material, mask=mask)
    piece = _compact(piece)
    if piece.triangle_count:
        piece.uvs = np.stack([piece.positions[:, 0] * 0.09, piece.positions[:, 2] * 0.09],
                             axis=-1)
        piece.recompute_normals(180.0)
    return piece


def backdrop(terrain: Terrain, reach: float = 150.0, cell: float = 7.0,
             seed: int = 4242, material: str = "cliff_rock",
             sea_level: float = 0.0) -> M.Mesh:
    """Coarse distant land beyond the authored terrain.

    The playable region is closed by mountain walls and by the sea; this ring
    gives those walls something to stand in front of, so an aerial or a hilltop
    view sees continuing country instead of a cut edge and empty sky. Its inner
    boundary samples the authored terrain's own edge height, so the two meet
    without a seam. It is not a walk surface and is never reachable.
    """
    x0 = terrain.x0 - reach
    z0 = terrain.z0 - reach
    x1 = terrain.x0 + terrain.size_x + reach
    z1 = terrain.z0 + terrain.size_z + reach
    cols = int((x1 - x0) / cell) + 1
    rows = int((z1 - z0) / cell) + 1
    xs = x0 + np.arange(cols) * cell
    zs = z0 + np.arange(rows) * cell
    gx, gz = np.meshgrid(xs, zs)

    inner_x1 = terrain.x0 + terrain.size_x
    inner_z1 = terrain.z0 + terrain.size_z
    dx = np.maximum(np.maximum(terrain.x0 - gx, gx - inner_x1), 0.0)
    dz = np.maximum(np.maximum(terrain.z0 - gz, gz - inner_z1), 0.0)
    outside = np.hypot(dx, dz)

    # nearest point on the authored terrain, clamped just inside its border
    near_x = np.clip(gx, terrain.x0 + 0.5, inner_x1 - 0.5)
    near_z = np.clip(gz, terrain.z0 + 0.5, inner_z1 - 0.5)
    edge_height = terrain.height_at(near_x, near_z)

    ridge = N.ridged(gx * 0.011, gz * 0.011, octaves=5, seed=seed)
    rough = N.fbm(gx * 0.030, gz * 0.030, octaves=4, seed=seed + 11)
    distant = 22.0 + ridge * 56.0 + rough * 12.0
    west = np.clip((terrain.x0 + 20.0 - gx) / 70.0, 0.0, 1.0)
    distant = distant * (1.0 - west) - 26.0 * west

    blend = 1.0 - np.exp(-outside / 42.0)
    height = edge_height * (1.0 - blend) + distant * blend
    # tuck the shared border a little under the authored terrain so the two
    # surfaces overlap instead of leaving a hairline of sky between them
    height -= 1.1 * np.exp(-outside / 9.0)

    mask = outside > -cell * 2.2
    piece = M.heightfield(height, x0, z0, cell, uv_scale=0.05, material=material,
                          mask=mask)
    piece = _compact(piece)
    if piece.triangle_count:
        piece.recompute_normals(180.0)
    return piece

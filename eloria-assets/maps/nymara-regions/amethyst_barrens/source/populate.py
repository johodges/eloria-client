"""Placement passes for Amethyst Barrens.

Terrain first: this module starts with water only, so the grounding contract can
be proved on bare terrain before any detail work goes in, as the region
production guide requires. The landmark, station and crystal passes are filled
in on top of a verified surface.
"""
from __future__ import annotations

import math

import numpy as np

from amberwood import mesh as M
from amberwood import noise as N
from amberwood import terrain as TER

import region as REG


# --------------------------------------------------------------------------
def build_water(build: REG.RegionBuild) -> None:
    """The two sea corners and the resonant river."""
    t = build.terrain

    # One sea surface over the whole footprint, clipped to where the ground is
    # actually below sea level, so both the north-east bay and the south-east
    # inlet are covered by a single plane and the open water runs to the horizon.
    build.water_meshes["Water_Sea"] = TER.water_plane(
        t, REG.SEA_LEVEL,
        t.x0, t.z0, t.x0 + t.size_x, t.z0 + t.size_z,
        material="water_sea", cell=6.0, only_below=True, margin=0.30,
        outside_is_water=True)

    # The river gets its own ribbon: the channel is carved into the terrain, and
    # the surface follows the carved bed rather than a single level.
    points = REG.STREAMS["resonant_river"]
    build.water_meshes["Water_RiverResonant"] = _river_ribbon(
        t, points, width=5.2 * REG.SCALE, material="water_stream")
    build.water_meshes["Water_RiverBeck"] = _river_ribbon(
        t, REG.STREAMS["mountain_beck"], width=3.4 * REG.SCALE,
        material="water_stream")


def _river_ribbon(t: TER.Terrain, points: np.ndarray, width: float,
                  material: str, drop: float = 0.35) -> M.Mesh:
    """A water strip that follows a carved channel down its own gradient.

    Sampled along the polyline rather than laid flat: the river falls about
    eight metres from the northern mountains to the sea, and a flat plane over
    it would either float at the top or vanish at the bottom.
    """
    mesh = M.Mesh(material=material)
    if len(points) < 2:
        return mesh

    # resample the polyline at a fixed spacing so the ribbon is evenly tessellated
    segments = np.diff(points, axis=0)
    lengths = np.hypot(segments[:, 0], segments[:, 1])
    total = float(lengths.sum())
    if total <= 0.0:
        return mesh
    step = 6.0
    count = max(int(total / step), 2)
    distances = np.linspace(0.0, total, count + 1)
    cumulative = np.concatenate([[0.0], np.cumsum(lengths)])
    xs = np.interp(distances, cumulative, points[:, 0])
    zs = np.interp(distances, cumulative, points[:, 1])

    # the surface sits a little below the carved bed's shoulders
    bed = t.height_at(xs, zs)
    # monotonic downstream: a river does not run uphill, and the eroded bed can
    # wobble by a few centimetres either way
    surface = np.minimum.accumulate(bed) - drop

    tangent_x = np.gradient(xs)
    tangent_z = np.gradient(zs)
    norm = np.hypot(tangent_x, tangent_z)
    norm[norm < 1e-6] = 1.0
    nx = -tangent_z / norm
    nz = tangent_x / norm

    half = width * 0.5
    left = np.stack([xs + nx * half, surface, zs + nz * half], axis=-1)
    right = np.stack([xs - nx * half, surface, zs - nz * half], axis=-1)

    positions = np.empty((len(xs) * 2, 3), dtype=np.float64)
    positions[0::2] = left
    positions[1::2] = right
    uvs = np.zeros((len(positions), 2), dtype=np.float64)
    uvs[:, 0] = positions[:, 0] * 0.09
    uvs[:, 1] = positions[:, 2] * 0.09
    normals = np.tile(np.array([0.0, 1.0, 0.0]), (len(positions), 1))

    indices = []
    for i in range(len(xs) - 1):
        a, b, c, d = i * 2, i * 2 + 1, i * 2 + 2, i * 2 + 3
        indices.extend([a, c, b, b, c, d])

    mesh.positions = positions
    mesh.normals = normals
    mesh.uvs = uvs
    mesh.indices = np.asarray(indices, dtype=np.int64)
    return mesh


# --------------------------------------------------------------------------
# Placement passes. Terrain milestone: no geometry yet.
# --------------------------------------------------------------------------
def populate_landmarks(build: REG.RegionBuild, seed: int, lod: str | None = None) -> None:
    return None


def populate_stations(build: REG.RegionBuild, seed: int, lod: str | None = None) -> None:
    return None


def populate_crystal(build: REG.RegionBuild, seed: int, lod: str | None = None) -> None:
    return None


def populate_ground_detail(build: REG.RegionBuild, seed: int) -> None:
    return None

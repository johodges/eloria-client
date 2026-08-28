#!/usr/bin/env python3
"""Geometry orientation regression tests for the Four Gates toolkit.

glTF front faces are counter-clockwise and Godot culls back faces, so geometry
wound the wrong way renders inside-out: the outward faces are culled and the
viewer looks straight through the wall at the interior of the far side. The
silhouette is unchanged, which is why it survives a casual visual review.

These tests assert the invariant directly:

  * every closed primitive has a positive signed volume (outward winding),
  * every convex closed primitive has no face whose normal points at its own
    centroid,
  * every ground surface has normals pointing +Y,
  * the authored NORMAL attribute agrees with the winding.

Run: python3 eloria-assets/tools/four_gates/test_geometry.py
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import meshlib as M  # noqa: E402


def signed_volume(geo) -> float:
    p = geo.v[geo.f].astype(np.float64)
    return float(np.einsum("ij,ij->i", p[:, 0], np.cross(p[:, 1], p[:, 2])).sum() / 6.0)


def inward_faces(geo) -> int:
    p = geo.v[geo.f].astype(np.float64)
    centres = p.mean(axis=1)
    centroid = geo.v.mean(axis=0)
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    lengths = np.linalg.norm(n, axis=1, keepdims=True)
    lengths[lengths == 0] = 1.0
    n = n / lengths
    return int((np.einsum("ij,ij->i", n, centres - centroid) <= 0).sum())


def normals_match_winding(geo) -> float:
    """Worst-case agreement between the authored NORMAL and the face winding.

    Smooth-shaded primitives average their vertex normals across neighbouring
    faces, so an exact match is not expected; what must never happen is a
    normal pointing into the opposite hemisphere from its winding, which is the
    signature of an inside-out surface.
    """
    p = geo.v[geo.f]
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    lengths = np.linalg.norm(n, axis=1, keepdims=True)
    lengths[lengths == 0] = 1.0
    n = n / lengths
    per_vertex = np.stack([
        np.einsum("ij,ij->i", n, geo.n[geo.f[:, k]]) for k in range(3)], axis=1)
    return float(per_vertex.min())


CLOSED = {
    "box": lambda: M.box(4, 3, 5),
    "box_corner": lambda: M.box(4, 3, 5, origin="corner"),
    "tapered_box": lambda: M.tapered_box(4, 5, 3, 4, 6),
    "cylinder": lambda: M.cylinder(2, 5, 16),
    "cylinder_tapered": lambda: M.cylinder(2, 5, 16, top_radius=1.2),
    "cone": lambda: M.cone(2, 4, 12),
    "pyramid": lambda: M.pyramid(3, 3, 4),
    "gable_roof_x": lambda: M.gable_roof(6, 8, 3),
    "gable_roof_z": lambda: M.gable_roof(6, 8, 3, ridge_along_x=False),
    "hip_roof": lambda: M.hip_roof(6, 8, 3),
    "prism": lambda: M.prism([(0, 0), (3, 0), (3, 3), (0, 3)], 4),
    "arch_ring": lambda: M.arch_ring(4, 6, 3, 0.0, math.pi, 10),
    "revolve": lambda: M.revolve([(0, 0), (1.2, 1), (0.8, 3), (0, 4)], 12),
    "icosphere": lambda: M.icosphere(2, 2),
    "stairs": lambda: M.stairs(6, 3, 8, 10),
    "ramp": lambda: M.ramp(4, 8, 3),
    "torus_arc": lambda: M.torus_arc(4, 0.5, 0.0, math.tau, 24, 8),
}

# convex shapes additionally allow the stricter per-face centroid test
CONVEX = {"box", "box_corner", "tapered_box", "cylinder", "cylinder_tapered",
          "cone", "pyramid", "prism", "icosphere", "ramp"}

SURFACES = {
    "plane": lambda: M.plane(100, 100, 0, 4.0, 0.0, 8),
    "grid_surface": lambda: M.grid_surface(
        -50, 50, -50, 50, 8, 8, lambda X, Z: 3 * np.sin(X * 0.05)),
    "polar_surface": lambda: M.polar_surface(
        np.linspace(10, 200, 20), 48, lambda X, Z: np.full_like(X, 5.0)),
    "ring_band": lambda: M.ring_band(10, 20, 32, lambda x, z: 0.0),
    "quad_strip_z": lambda: M.quad_strip([(0, 0), (0, 50), (0, 100)], 10,
                                         lambda x, z: 0.0),
    "quad_strip_x": lambda: M.quad_strip([(0, 0), (50, 0), (100, 0)], 10,
                                         lambda x, z: 0.0),
}


def main() -> int:
    failures = []
    print("closed primitives -- signed volume must be positive")
    for name, factory in CLOSED.items():
        geo = factory()
        volume = signed_volume(geo)
        note = ""
        if volume <= 0.0:
            failures.append(f"{name}: inside-out (signed volume {volume:.2f})")
        if name in CONVEX:
            bad = inward_faces(geo)
            note = f" inward_faces={bad}"
            if bad:
                failures.append(f"{name}: {bad} face(s) point inward")
        agree = normals_match_winding(geo)
        if agree <= 0.0:
            failures.append(
                f"{name}: NORMAL points opposite its winding (worst dot {agree:.3f})")
        print(f"  {name:18s} volume={volume:10.2f}{note}")

    print("\nground surfaces -- normals must point +Y")
    for name, factory in SURFACES.items():
        geo = factory()
        mean_y = float(geo.n[:, 1].mean())
        if mean_y < 0.9:
            failures.append(f"{name}: surface normals point away from +Y ({mean_y:.3f})")
        print(f"  {name:18s} mean normal Y={mean_y:6.3f}")

    print()
    if failures:
        for failure in failures:
            print("FAIL:", failure)
        print(f"\n{len(failures)} geometry orientation failure(s)")
        return 1
    print("PASS: all primitives are wound outward and all surfaces face +Y")
    return 0


if __name__ == "__main__":
    sys.exit(main())

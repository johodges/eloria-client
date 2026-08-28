#!/usr/bin/env python3
"""Canonical Nymara harvestable catalogue: geometry, materials and lists.

This module is the single source of truth for every harvestable resource in
the world.  Before it existed the client carried three disjoint harvestable
vocabularies (the legacy Emberhaven scenery set, the Nymara region set placed
by the map generator, and the icon/2D set shipped in the client asset pack),
and none of them agreed with the names the client's `harvestable.lst` lookup
actually needs.

Fidelity contract
-----------------
Harvest nodes are props the player walks up to and stares at while the harvest
animation loops, so they are authored to the same standard as the refined
regional kit rather than to the placeholder standard they had before:

* intentional silhouette topology in the 90-320 triangle band, which is the
  band the surrounding regional landmark kit occupies (12-424 triangles, with
  the refined Four Gates civic kit at 224-424);
* one authored 256x256 RGBA material per resource, quartered into stalk,
  blade, bloom and bed regions so faces sample matching texel density instead
  of stretching a single checker over every surface;
* foliage models declare a transparent material, which is what makes the
  client enable alpha test and disable back-face culling for them
  (`3d_objects.c`), so leaf cards read as foliage and stay visible from every
  camera angle instead of being culled away from behind;
* stable pivots: every model sits on z=0 and is centred on the node position.
"""
from __future__ import annotations

import math
import struct
from pathlib import Path

from generate_bootstrap_pack import png

MODEL_DIR = "3dobjects/nymara"
TEXTURE_SIZE = 256

# Quadrants of the shared per-resource material.
UV_STALK = (0.02, 0.02, 0.48, 0.48)
UV_BLADE = (0.52, 0.02, 0.98, 0.48)
UV_BLOOM = (0.02, 0.52, 0.48, 0.98)
UV_BED = (0.52, 0.52, 0.98, 0.98)


# --------------------------------------------------------------------------
# geometry primitives (uv aware; the shared scenery helpers are uv-agnostic)
# --------------------------------------------------------------------------

def quad(vertices, indices, points, normal, uv):
    u0, v0, u1, v1 = uv
    corners = ((u0, v1), (u1, v1), (u1, v0), (u0, v0))
    base = len(vertices)
    for (x, y, z), (u, v) in zip(points, corners):
        vertices.append((u, v, *normal, x, y, z))
    indices.extend((base, base + 1, base + 2, base, base + 2, base + 3))


def prism(vertices, indices, z0, z1, r0, r1, sides, center=(0.0, 0.0),
          uv=UV_STALK, lean=(0.0, 0.0)):
    """A tapered prism; `lean` offsets the top ring for organic silhouettes."""
    cx, cy = center
    lx, ly = lean
    for i in range(sides):
        a = 2 * math.pi * i / sides
        b = 2 * math.pi * (i + 1) / sides
        m = (a + b) / 2
        quad(vertices, indices, [
            (cx + r0 * math.cos(a), cy + r0 * math.sin(a), z0),
            (cx + r0 * math.cos(b), cy + r0 * math.sin(b), z0),
            (cx + lx + r1 * math.cos(b), cy + ly + r1 * math.sin(b), z1),
            (cx + lx + r1 * math.cos(a), cy + ly + r1 * math.sin(a), z1),
        ], (math.cos(m), math.sin(m), 0.0), uv)


def cap(vertices, indices, z, radius, sides, center=(0.0, 0.0), uv=UV_BLOOM,
        normal=(0.0, 0.0, 1.0)):
    cx, cy = center
    for i in range(sides):
        a = 2 * math.pi * i / sides
        b = 2 * math.pi * (i + 1) / sides
        quad(vertices, indices, [
            (cx, cy, z),
            (cx + radius * math.cos(a), cy + radius * math.sin(a), z),
            (cx + radius * math.cos(b), cy + radius * math.sin(b), z),
            (cx, cy, z),
        ], normal, uv)


def blade(vertices, indices, base_xy, angle, length, width, rise, droop,
          uv=UV_BLADE, segments=2):
    """An arching leaf card built from `segments` quads so it silhouettes."""
    cx, cy = base_xy
    dx, dy = math.cos(angle), math.sin(angle)
    nx, ny = -dy, dx
    z = 0.0
    reach = 0.0
    for s in range(segments):
        t0 = s / segments
        t1 = (s + 1) / segments
        z0 = rise * math.sin(math.pi * t0 / 2) - droop * t0 * t0
        z1 = rise * math.sin(math.pi * t1 / 2) - droop * t1 * t1
        r0 = length * t0
        r1 = length * t1
        w0 = width * (1.0 - 0.55 * t0)
        w1 = width * (1.0 - 0.55 * t1)
        v0 = uv[1] + (uv[3] - uv[1]) * t0
        v1 = uv[1] + (uv[3] - uv[1]) * t1
        quad(vertices, indices, [
            (cx + dx * r0 - nx * w0 / 2, cy + dy * r0 - ny * w0 / 2, z0),
            (cx + dx * r0 + nx * w0 / 2, cy + dy * r0 + ny * w0 / 2, z0),
            (cx + dx * r1 + nx * w1 / 2, cy + dy * r1 + ny * w1 / 2, z1),
            (cx + dx * r1 - nx * w1 / 2, cy + dy * r1 - ny * w1 / 2, z1),
        ], (nx * 0.35, ny * 0.35, 0.87), (uv[0], v0, uv[2], v1))
        z, reach = z1, r1
    return (cx + dx * reach, cy + dy * reach, z)


def shard(vertices, indices, center, height, radius, sides, tilt=0.0,
          uv=UV_BLOOM):
    """A faceted crystal: a short prism body closed by a leaning point."""
    cx, cy = center
    lean = (math.cos(tilt) * height * 0.18, math.sin(tilt) * height * 0.18)
    prism(vertices, indices, 0.0, height * 0.62, radius, radius * 0.78, sides,
          center, uv, lean=(lean[0] * 0.4, lean[1] * 0.4))
    tx, ty = cx + lean[0], cy + lean[1]
    for i in range(sides):
        a = 2 * math.pi * i / sides
        b = 2 * math.pi * (i + 1) / sides
        m = (a + b) / 2
        px = cx + lean[0] * 0.4
        py = cy + lean[1] * 0.4
        r = radius * 0.78
        quad(vertices, indices, [
            (px + r * math.cos(a), py + r * math.sin(a), height * 0.62),
            (px + r * math.cos(b), py + r * math.sin(b), height * 0.62),
            (tx, ty, height),
            (tx, ty, height),
        ], (math.cos(m) * 0.7, math.sin(m) * 0.7, 0.7), uv)


def cobble(vertices, indices, center, radius, height, sides=6, uv=UV_BED,
           seed=0, z0=0.0):
    """An irregular boulder/nodule; radii wobble deterministically."""
    cx, cy = center
    lower = []
    upper = []
    for i in range(sides):
        a = 2 * math.pi * i / sides
        wob = 0.78 + 0.28 * (((i * 7 + seed * 13) % 11) / 10.0)
        lower.append((cx + radius * wob * math.cos(a),
                      cy + radius * wob * math.sin(a), z0))
        upper.append((cx + radius * wob * 0.58 * math.cos(a),
                      cy + radius * wob * 0.58 * math.sin(a),
                      z0 + height * (0.72 + 0.28
                                     * (((i * 5 + seed) % 7) / 6.0))))
    for i in range(sides):
        j = (i + 1) % sides
        m = 2 * math.pi * (i + 0.5) / sides
        quad(vertices, indices, [lower[i], lower[j], upper[j], upper[i]],
             (math.cos(m), math.sin(m), 0.32), uv)
    for i in range(1, sides - 1):
        quad(vertices, indices, [upper[0], upper[i], upper[i + 1], upper[0]],
             (0.0, 0.0, 1.0), uv)


def bed(vertices, indices, radius, thickness, sides=8, uv=UV_BED):
    """The disturbed ground ring every node sits in, so it reads as a site."""
    prism(vertices, indices, 0.0, thickness, radius, radius * 0.86, sides,
          uv=uv)
    cap(vertices, indices, thickness, radius * 0.86, sides, uv=uv)


# --------------------------------------------------------------------------
# archetype builders
# --------------------------------------------------------------------------

def stalk_cluster(stems=7, height=1.35, head=0.0, leaves=5, spread=0.30,
                  head_sides=6):
    """Grain, reed and fibre crops: a sheaf of stalks with blades and heads."""
    def build(v, i):
        bed(v, i, spread + 0.14, 0.045)
        for s in range(stems):
            a = 2 * math.pi * s / stems + 0.4
            r = spread * (0.30 + 0.70 * ((s * 5 % 7) / 6.0))
            cx, cy = r * math.cos(a), r * math.sin(a)
            h = height * (0.78 + 0.22 * ((s * 3 % 5) / 4.0))
            prism(v, i, 0.04, h, 0.042, 0.022, 5, (cx, cy), UV_STALK,
                  lean=(math.cos(a) * h * 0.10, math.sin(a) * h * 0.10))
            if head > 0:
                tx = cx + math.cos(a) * h * 0.10
                ty = cy + math.sin(a) * h * 0.10
                prism(v, i, h - head, h + head * 0.35, 0.075, 0.016,
                      head_sides, (tx, ty), UV_BLOOM)
        for l in range(leaves):
            a = 2 * math.pi * l / leaves + 0.9
            blade(v, i, (0.06 * math.cos(a), 0.06 * math.sin(a)), a,
                  height * 0.72, 0.16, height * 0.58, height * 0.34)
    return build, True


def leafy_herb(rosette=6, height=0.72, blooms=3, bloom_height=0.0,
               berry=False):
    """Herbs, sages and thistles: a ground rosette with a flowering spike."""
    def build(v, i):
        bed(v, i, 0.28, 0.045)
        for l in range(rosette):
            a = 2 * math.pi * l / rosette + 0.3
            blade(v, i, (0.05 * math.cos(a), 0.05 * math.sin(a)), a,
                  height * 0.95, 0.20, height * 0.42, height * 0.30)
        for b in range(blooms):
            a = 2 * math.pi * b / blooms
            cx, cy = 0.10 * math.cos(a), 0.10 * math.sin(a)
            top = height * (0.90 + 0.25 * (b % 2))
            prism(v, i, 0.04, top, 0.045, 0.028, 5, (cx, cy), UV_STALK)
            if berry:
                for k in range(3):
                    ka = a + 1.1 * k
                    cobble(v, i, (cx + 0.11 * math.cos(ka),
                                  cy + 0.11 * math.sin(ka)), 0.11, 0.17, 5,
                           UV_BLOOM, seed=b * 3 + k,
                           z0=top * (0.52 + 0.20 * k))
            else:
                prism(v, i, top - bloom_height, top + bloom_height * 0.4,
                      0.115, 0.03, 6, (cx, cy), UV_BLOOM)
    return build, True


def bloom_flower(petals=6, stem=0.95, petal_length=0.34, pads=0, leaves=4,
                 buds=2):
    """Orchids, lotuses and other single-bloom flora."""
    def build(v, i):
        bed(v, i, 0.26, 0.04)
        for l in range(leaves):
            a = 2 * math.pi * l / leaves + 1.3
            blade(v, i, (0.07 * math.cos(a), 0.07 * math.sin(a)), a,
                  0.54, 0.19, 0.34, 0.22)
        for b in range(buds):
            a = 2 * math.pi * b / max(1, buds) + 2.1
            cx, cy = 0.11 * math.cos(a), 0.11 * math.sin(a)
            top = stem * (0.52 + 0.16 * b)
            prism(v, i, 0.04, top, 0.024, 0.018, 5, (cx, cy), UV_STALK)
            prism(v, i, top, top + 0.12, 0.055, 0.02, 5, (cx, cy), UV_BLOOM)
        for p in range(pads):
            a = 2 * math.pi * p / pads + 0.5
            blade(v, i, (0.16 * math.cos(a), 0.16 * math.sin(a)), a,
                  0.46, 0.34, 0.06, 0.04)
        prism(v, i, 0.04, stem, 0.045, 0.030, 6, uv=UV_STALK)
        for p in range(petals):
            a = 2 * math.pi * p / petals
            blade(v, i, (0.03 * math.cos(a), 0.03 * math.sin(a)), a,
                  petal_length, 0.17, stem + 0.16, 0.10, uv=UV_BLOOM,
                  segments=2)
        cap(v, i, stem + 0.05, 0.075, 6, uv=UV_BLOOM)
    return build, True


def swollen_bulb(lobes=4, height=0.70, leaves=5, vents=0):
    """Venom bulbs, tubers and boll fibre: a fat body under leaf cover."""
    def build(v, i):
        bed(v, i, 0.30, 0.045)
        for l in range(lobes):
            a = 2 * math.pi * l / lobes + 0.4
            cx, cy = 0.20 * math.cos(a), 0.20 * math.sin(a)
            h = height * (0.80 + 0.20 * (l % 3) / 2.0)
            prism(v, i, 0.05, h * 0.34, 0.13, 0.27, 7, (cx, cy), UV_BLOOM)
            prism(v, i, h * 0.34, h * 0.80, 0.27, 0.22, 7, (cx, cy), UV_BLOOM)
            prism(v, i, h * 0.80, h, 0.22, 0.05, 7, (cx, cy), UV_BLOOM)
        for l in range(leaves):
            a = 2 * math.pi * l / leaves + 1.1
            blade(v, i, (0.10 * math.cos(a), 0.10 * math.sin(a)), a,
                  0.62, 0.24, height * 0.72, 0.34)
        for s in range(vents):
            a = 2 * math.pi * s / vents
            prism(v, i, height * 0.8, height * 1.25, 0.030, 0.016, 5,
                  (0.10 * math.cos(a), 0.10 * math.sin(a)), UV_STALK)
    return build, True


def fungus_ring(caps=5, height=0.46):
    """Cap fungi in a small ring with a shared litter bed."""
    def build(v, i):
        bed(v, i, 0.28, 0.045)
        for c in range(caps):
            a = 2 * math.pi * c / caps + 0.2
            r = 0.10 + 0.14 * ((c * 3 % 5) / 4.0)
            cx, cy = r * math.cos(a), r * math.sin(a)
            h = height * (0.70 + 0.30 * ((c * 5 % 4) / 3.0))
            prism(v, i, 0.04, h * 0.68, 0.075, 0.058, 6, (cx, cy), UV_STALK)
            prism(v, i, h * 0.62, h * 0.88, 0.085, 0.22, 8, (cx, cy), UV_BLOOM)
            prism(v, i, h * 0.88, h, 0.22, 0.11, 8, (cx, cy), UV_BLOOM)
            cap(v, i, h, 0.11, 8, (cx, cy), UV_BLOOM)
    return build, True


def ribbon_weed(ribbons=6, height=1.15):
    """Kelp and river weed: a holdfast with long trailing ribbons."""
    def build(v, i):
        bed(v, i, 0.26, 0.045)
        cobble(v, i, (0.0, 0.0), 0.24, 0.26, 6, UV_BED, seed=3)
        cobble(v, i, (0.20, -0.14), 0.16, 0.14, 5, UV_BED, seed=6)
        for r in range(ribbons):
            a = 2 * math.pi * r / ribbons + 0.35
            blade(v, i, (0.12 * math.cos(a), 0.12 * math.sin(a)), a,
                  height * 0.80, 0.22, height, height * 0.42, segments=3)
    return build, True


def resin_flow(drips=5, trunk=1.45):
    """Amber resin and mangrove sap: a bark face with hardened runs."""
    def build(v, i):
        bed(v, i, 0.34, 0.045)
        prism(v, i, 0.04, trunk, 0.32, 0.25, 7, uv=UV_STALK)
        prism(v, i, trunk * 0.45, trunk * 0.95, 0.34, 0.10, 6, (0.20, 0.06),
              UV_STALK)
        for d in range(drips):
            a = 2 * math.pi * d / drips + 0.25
            cx, cy = 0.27 * math.cos(a), 0.27 * math.sin(a)
            top = trunk * (0.40 + 0.40 * ((d * 3 % 5) / 4.0))
            prism(v, i, top * 0.35, top, 0.075, 0.115, 5, (cx, cy), UV_BLOOM)
            prism(v, i, top * 0.18, top * 0.35, 0.115, 0.035, 5, (cx, cy),
                  UV_BLOOM)
        for l in range(3):
            a = 2 * math.pi * l / 3 + 0.8
            blade(v, i, (0.24 * math.cos(a), 0.24 * math.sin(a)), a,
                  0.52, 0.26, trunk * 0.92, 0.30)
    return build, True


def mineral_seam(nodes=5, spoil=3, radius=0.52, style="bank", sides=6):
    """Clay, peat, coal, flint and bog iron.

    `style` picks the site's shape so the eight mineral resources do not all
    read as the same mound: `bank` is a cut face with the seam exposed on top,
    `pit` is a dug hollow with a raised rim, and `scatter` is loose surface
    material with no bank at all.  `sides` controls how angular the nodules
    are, which separates flint and coal from clay and bog iron.
    """
    def build(v, i):
        bed(v, i, radius + 0.08, 0.05)
        if style == "bank":
            prism(v, i, 0.05, 0.46, radius, radius * 0.66, 7, uv=UV_BED)
            cap(v, i, 0.46, radius * 0.66, 7, uv=UV_BED)
            base = 0.0
        elif style == "pit":
            prism(v, i, 0.05, 0.34, radius, radius * 1.02, 8, uv=UV_BED)
            prism(v, i, 0.34, 0.12, radius * 1.02, radius * 0.56, 8,
                  uv=UV_BED)
            cap(v, i, 0.12, radius * 0.56, 8, uv=UV_BED)
            base = 0.10
        else:
            cap(v, i, 0.06, radius, 8, uv=UV_BED)
            base = 0.02
        for n in range(nodes):
            a = 2 * math.pi * n / nodes + 0.3
            spread = 0.32 if style == "bank" else 0.52
            r = radius * (spread + 0.42 * ((n * 5 % 4) / 3.0))
            cobble(v, i, (r * math.cos(a), r * math.sin(a)),
                   0.17 + 0.05 * (n % 3), 0.52 + 0.14 * (n % 2), sides,
                   UV_BLOOM, seed=n, z0=base)
        for s in range(spoil):
            a = 2 * math.pi * s / spoil + 1.2
            cobble(v, i, ((radius + 0.20) * math.cos(a),
                          (radius + 0.20) * math.sin(a)),
                   0.13, 0.14, 5, UV_STALK, seed=s + 7)
    return build, False


def crystal_cluster(points=5, height=1.05, radius=0.20, geode=False):
    """Resonant, stormglass, quartz and geode nodes."""
    def build(v, i):
        bed(v, i, 0.30, 0.045)
        if geode:
            prism(v, i, 0.05, 0.46, 0.44, 0.36, 8, uv=UV_BED)
            cap(v, i, 0.46, 0.36, 8, uv=UV_BED)
        for p in range(points):
            a = 2 * math.pi * p / points + 0.4
            r = 0.10 + 0.20 * ((p * 3 % 5) / 4.0)
            h = height * (0.55 + 0.45 * ((p * 7 % 6) / 5.0))
            shard(v, i, (r * math.cos(a), r * math.sin(a)), h,
                  radius * (0.62 + 0.38 * ((p * 5 % 4) / 3.0)), 6,
                  tilt=a + 0.6)
        shard(v, i, (0.0, 0.0), height * 1.10, radius, 6, tilt=0.2)
    return build, False


def shell_bed(shells=5, height=0.26):
    """Pearl and shell beds: opened shells half sunk in a sand bar."""
    def build(v, i):
        bed(v, i, 0.38, 0.05)
        for s in range(shells):
            a = 2 * math.pi * s / shells + 0.5
            r = 0.16 + 0.14 * ((s * 3 % 4) / 3.0)
            cx, cy = r * math.cos(a), r * math.sin(a)
            lift = height * (0.85 + 0.35 * ((s * 5 % 3) / 2.0))
            prism(v, i, 0.05, lift * 0.55, 0.13, 0.26, 7, (cx, cy), UV_BLOOM)
            prism(v, i, lift * 0.55, lift, 0.26, 0.16, 7, (cx, cy), UV_BLOOM)
            prism(v, i, lift, lift + 0.16, 0.16, 0.05, 7, (cx, cy), UV_BLOOM)
        cobble(v, i, (0.0, 0.0), 0.15, 0.26, 6, UV_STALK, seed=2)
    return build, False


def salt_pan(plates=6, height=0.52):
    """Evaporite crusts: overlapping plates lifting off a shallow pan."""
    def build(v, i):
        bed(v, i, 0.44, 0.05)
        for p in range(plates):
            a = 2 * math.pi * p / plates + 0.3
            r = 0.16 + 0.14 * ((p * 5 % 3) / 2.0)
            cx, cy = r * math.cos(a), r * math.sin(a)
            h = height * (0.70 + 0.50 * ((p * 3 % 5) / 4.0))
            prism(v, i, 0.05, h, 0.24, 0.20, 5, (cx, cy), UV_BLOOM,
                  lean=(math.cos(a) * h * 0.42, math.sin(a) * h * 0.42))
            cap(v, i, h, 0.20, 5,
                (cx + math.cos(a) * h * 0.42, cy + math.sin(a) * h * 0.42),
                UV_BLOOM)
    return build, False


def moss_mat(patches=6, stones=3):
    """Scale moss and lichen: low cards over damp stones."""
    def build(v, i):
        bed(v, i, 0.34, 0.04)
        for s in range(stones):
            a = 2 * math.pi * s / stones + 0.4
            cobble(v, i, (0.22 * math.cos(a), 0.22 * math.sin(a)),
                   0.20, 0.22, 6, UV_BED, seed=s + 4)
        for p in range(patches):
            a = 2 * math.pi * p / patches + 0.7
            blade(v, i, (0.14 * math.cos(a), 0.14 * math.sin(a)), a,
                  0.38, 0.30, 0.30, 0.16, segments=2)
    return build, True


# --------------------------------------------------------------------------
# catalogue
# --------------------------------------------------------------------------
# id, label, kind, tier, regions, (base, accent, bloom), archetype
CATALOGUE = (
    # --- signature regional resources -------------------------------------
    ("mirror_reed", "Mirror Reed", "fibre", "common",
     ("mirrorhold", "crownwater", "four_gates"),
     ((44, 116, 101), (107, 190, 165), (196, 226, 214)),
     stalk_cluster(stems=8, height=1.55, head=0.16, leaves=6, spread=0.26)),
    ("crownwater_pearl", "Crownwater Pearl", "aquatic", "rare",
     ("crownwater", "mirrorhold", "manymouth_delta"),
     ((132, 146, 140), (206, 219, 210), (238, 240, 231)),
     shell_bed(shells=5)),
    ("deep_lake_clay", "Deep Lake Clay", "mineral", "common",
     ("mirrorhold", "crownwater", "westhaven", "manymouth_delta",
      "amethyst_barrens"),
     ((101, 77, 62), (140, 108, 84), (63, 122, 128)),
     mineral_seam(nodes=6, spoil=3, radius=0.56, style="pit", sides=7)),
    ("delta_lotus", "Delta Lotus", "flora", "uncommon",
     ("manymouth_delta", "verdant_stair", "ssarathi_ruins", "westhaven",
      "mirrorhold"),
     ((57, 117, 75), (110, 168, 108), (210, 112, 150)),
     bloom_flower(petals=8, stem=0.78, petal_length=0.30, pads=5, leaves=3)),
    ("ghost_orchid", "Ghost Orchid", "flora", "rare",
     ("amberwood", "grey_moors", "verdant_stair"),
     ((94, 91, 113), (146, 143, 168), (222, 213, 240)),
     bloom_flower(petals=7, stem=1.05, petal_length=0.36, leaves=4, buds=3)),
    ("glacier_salt", "Glacier Salt", "mineral", "common",
     ("whitehorn_range", "crownwater", "westhaven"),
     ((152, 168, 178), (202, 227, 231), (238, 246, 248)),
     salt_pan(plates=7)),
    ("mangrove_sap", "Mangrove Sap", "resin", "uncommon",
     ("manymouth_delta", "westhaven", "grey_moors"),
     ((75, 61, 40), (118, 96, 60), (146, 178, 96)),
     resin_flow(drips=5, trunk=1.35)),
    ("moor_peat", "Moor Peat", "fuel", "common",
     ("grey_moors", "amberwood", "westhaven", "whitehorn_range"),
     ((66, 56, 46), (99, 84, 68), (48, 62, 50)),
     mineral_seam(nodes=4, spoil=4, radius=0.62, style="bank", sides=4)),
    ("resonant_crystal", "Resonant Crystal", "crystal", "rare",
     ("amethyst_barrens", "four_gates", "whitehorn_range"),
     ((101, 72, 125), (156, 118, 186), (206, 140, 240)),
     crystal_cluster(points=6, height=1.30, radius=0.22)),
    ("ssarathi_scale_moss", "Ssarathi Scale Moss", "flora", "uncommon",
     ("ssarathi_ruins", "verdant_stair", "manymouth_delta"),
     ((49, 96, 79), (79, 141, 112), (142, 196, 150)),
     moss_mat(patches=7, stones=3)),
    ("stormglass_shard", "Stormglass Shard", "crystal", "uncommon",
     ("amethyst_barrens", "sunmane_steppe", "whitehorn_range", "four_gates"),
     ((78, 83, 119), (122, 130, 178), (176, 190, 240)),
     crystal_cluster(points=5, height=1.05, radius=0.19)),
    ("sunmane_seed", "Sunmane Seed", "crop", "common",
     ("sunmane_steppe", "amberwood", "four_gates"),
     ((124, 104, 52), (194, 157, 72), (226, 199, 118)),
     stalk_cluster(stems=9, height=1.30, head=0.20, leaves=5, spread=0.30)),
    ("verdant_venom_bulb", "Verdant Venom Bulb", "flora", "rare",
     ("verdant_stair", "ssarathi_ruins", "manymouth_delta"),
     ((44, 92, 56), (91, 171, 71), (176, 208, 90)),
     swollen_bulb(lobes=4, height=0.78, leaves=6, vents=3)),
    ("voltaic_geode", "Voltaic Geode", "crystal", "rare",
     ("amethyst_barrens", "sunmane_steppe", "ssarathi_ruins"),
     ((84, 76, 108), (132, 115, 198), (196, 176, 246)),
     crystal_cluster(points=5, height=0.86, radius=0.17, geode=True)),
    ("whitehorn_silverleaf", "Whitehorn Silverleaf", "herb", "uncommon",
     ("whitehorn_range", "amethyst_barrens", "grey_moors"),
     ((102, 137, 118), (167, 207, 185), (222, 236, 232)),
     leafy_herb(rosette=7, height=0.84, blooms=3, bloom_height=0.12)),
    ("amber_resin", "Amber Resin", "resin", "uncommon",
     ("amberwood", "sunmane_steppe", "grey_moors"),
     ((101, 69, 40), (150, 104, 58), (213, 116, 47)),
     resin_flow(drips=6, trunk=1.55)),

    # --- general world resources -----------------------------------------
    # These fill out the everyday crafting economy so that every region has
    # ordinary work to do alongside its signature rarity.
    ("wayside_sage", "Wayside Sage", "herb", "common",
     ("four_gates", "mirrorhold", "crownwater", "amberwood", "grey_moors",
      "westhaven", "sunmane_steppe", "verdant_stair"),
     ((82, 111, 82), (139, 155, 117), (186, 198, 152)),
     leafy_herb(rosette=6, height=0.66, blooms=3, bloom_height=0.10)),
    ("steppe_wheat", "Steppe Wheat", "crop", "common",
     ("sunmane_steppe", "amberwood", "four_gates", "westhaven"),
     ((117, 105, 48), (196, 172, 88), (232, 208, 128)),
     stalk_cluster(stems=10, height=1.42, head=0.24, leaves=4, spread=0.32)),
    ("riverflax", "Riverflax", "fibre", "common",
     ("crownwater", "mirrorhold", "manymouth_delta", "four_gates"),
     ((73, 111, 67), (118, 158, 104), (104, 143, 184)),
     stalk_cluster(stems=8, height=1.18, head=0.10, leaves=5, spread=0.24)),
    ("moorcotton", "Moorcotton", "fibre", "common",
     ("grey_moors", "westhaven", "amberwood"),
     ((72, 96, 68), (118, 140, 104), (226, 222, 202)),
     swollen_bulb(lobes=5, height=0.62, leaves=5)),
    ("hearthroot", "Hearthroot", "crop", "common",
     ("amberwood", "verdant_stair", "grey_moors", "mirrorhold"),
     ((88, 68, 44), (134, 100, 62), (176, 128, 74)),
     swollen_bulb(lobes=3, height=0.54, leaves=6)),
    ("barrow_bramble", "Barrow Bramble", "flora", "common",
     ("grey_moors", "amberwood", "whitehorn_range"),
     ((58, 74, 54), (96, 118, 82), (74, 62, 118)),
     leafy_herb(rosette=6, height=0.80, blooms=4, berry=True)),
    ("lantern_cap", "Lantern Cap", "fungus", "uncommon",
     ("verdant_stair", "ssarathi_ruins", "manymouth_delta",
      "amethyst_barrens", "whitehorn_range"),
     ((92, 84, 70), (140, 128, 102), (236, 196, 108)),
     fungus_ring(caps=6, height=0.52)),
    ("tidewrack_kelp", "Tidewrack Kelp", "aquatic", "common",
     ("westhaven", "crownwater", "manymouth_delta", "mirrorhold"),
     ((52, 70, 58), (86, 112, 78), (142, 158, 84)),
     ribbon_weed(ribbons=9, height=1.25)),
    ("shorebank_shell", "Shorebank Shell", "mineral", "common",
     ("westhaven", "manymouth_delta", "crownwater"),
     ((146, 138, 120), (198, 190, 168), (232, 226, 208)),
     shell_bed(shells=6, height=0.22)),
    ("verdigris_bloom", "Verdigris Bloom", "mineral", "uncommon",
     ("whitehorn_range", "amethyst_barrens", "sunmane_steppe"),
     ((72, 84, 78), (110, 128, 112), (86, 168, 142)),
     mineral_seam(nodes=5, spoil=3, radius=0.50, style="scatter", sides=7)),
    ("bogiron_nodule", "Bog Iron Nodule", "mineral", "common",
     ("grey_moors", "westhaven", "manymouth_delta", "amberwood"),
     ((70, 62, 54), (108, 92, 76), (146, 105, 76)),
     mineral_seam(nodes=6, spoil=2, radius=0.48, style="scatter", sides=8)),
    ("emberseam_coal", "Emberseam Coal", "fuel", "common",
     ("whitehorn_range", "amethyst_barrens", "sunmane_steppe", "grey_moors"),
     ((40, 40, 42), (68, 68, 72), (128, 74, 52)),
     mineral_seam(nodes=5, spoil=4, radius=0.54, style="bank", sides=5)),
    ("pale_quartz", "Pale Quartz", "crystal", "common",
     ("whitehorn_range", "amethyst_barrens", "verdant_stair", "four_gates"),
     ((132, 132, 130), (186, 184, 178), (232, 228, 220)),
     crystal_cluster(points=4, height=0.78, radius=0.18)),
    ("sunstone_flint", "Sunstone Flint", "mineral", "common",
     ("sunmane_steppe", "whitehorn_range", "grey_moors", "ssarathi_ruins"),
     ((96, 84, 66), (140, 122, 92), (204, 152, 78)),
     mineral_seam(nodes=6, spoil=3, radius=0.46, style="pit", sides=5)),
    ("indigo_thistle", "Indigo Thistle", "herb", "uncommon",
     ("mirrorhold", "sunmane_steppe", "grey_moors", "amethyst_barrens"),
     ((66, 88, 74), (104, 128, 100), (78, 84, 168)),
     leafy_herb(rosette=7, height=0.88, blooms=3, bloom_height=0.16)),
    ("cenote_watercress", "Cenote Watercress", "flora", "common",
     ("verdant_stair", "ssarathi_ruins", "crownwater", "manymouth_delta"),
     ((46, 100, 82), (86, 152, 118), (168, 206, 152)),
     ribbon_weed(ribbons=8, height=0.72)),
)

BY_ID = {entry[0]: entry for entry in CATALOGUE}
IDS = tuple(entry[0] for entry in CATALOGUE)

# Legacy Emberhaven bootstrap harvestables produced by generate_scenery.py.
# They stay in the world and therefore have to stay in harvestable.lst.
LEGACY_IDS = (
    "sunleaf", "frost_reed", "copper_bloom", "ember_crystal", "slate_outcrop",
    "wheat", "cotton", "lavender", "flax", "sage", "rosemary", "mushroom",
    "grave_moss", "blueberries", "coal", "iron_ore", "stormglass",
    "moon_salt", "quartz", "sulfur",
)

RESPAWN_SECONDS = {"common": 60, "uncommon": 105, "rare": 165}
NODES_PER_REGION = {"common": 3, "uncommon": 2, "rare": 2}


def region_resources(region: str) -> tuple:
    """Every catalogue id that belongs in `region`, in catalogue order."""
    return tuple(entry[0] for entry in CATALOGUE if region in entry[4])


def model_path(resource_id: str) -> str:
    return f"{MODEL_DIR}/{resource_id}.e3d"


def harvest_list_entries() -> list:
    """Basenames for harvestable.lst.

    `is_harvestable()` in cursors.c binary-searches the loaded list with an
    exact strcmp against the *basename* of the object file (3d_objects.c
    lowercases the name first), so the list must hold lowercase basenames.
    Full relative paths, which is what the generators used to write, never
    match and leave every object in the world unharvestable.
    """
    names = sorted({f"{i}.e3d" for i in IDS} | {f"{i}.e3d" for i in LEGACY_IDS})
    return names


def write_harvest_list(root: Path) -> list:
    entries = harvest_list_entries()
    (root / "harvestable.lst").write_text("\n".join(entries) + "\n",
                                          encoding="utf-8")
    return entries


# --------------------------------------------------------------------------
# materials
# --------------------------------------------------------------------------

def material_pixel(base, accent, bloom):
    """Four authored quadrants sharing one 256x256 RGBA material.

    Quadrant layout matches the UV constants above: stalk (top left), blade
    (top right, alpha cut to a leaf silhouette), bloom/facet (bottom left) and
    bed/ground (bottom right).
    """
    half = TEXTURE_SIZE // 2

    def mix(a, b, t):
        return tuple(int(p + (q - p) * t) for p, q in zip(a, b))

    def pixel(x, y):
        u = x % half
        v = y % half
        grain = ((x * 23 + y * 41 + (x ^ y) * 5) % 29) - 14
        if x < half and y < half:            # stalk: vertical fibre
            fibre = math.sin(u * 0.9) * 0.5 + math.sin(u * 0.31 + v * 0.05)
            col = mix(base, accent, 0.28 + 0.22 * (fibre > 0.2))
            node = 0.35 if (v % 42) < 3 else 0.0
            col = mix(col, base, node)
            return (*(max(0, min(255, c + grain // 2)) for c in col), 255)
        if x >= half and y < half:           # blade: alpha leaf silhouette
            t = v / half
            width = 0.5 * math.sin(math.pi * min(1.0, t * 1.04)) ** 0.65
            d = abs(u / half - 0.5)
            if d > width:
                return (0, 0, 0, 0)
            edge = 1.0 - d / max(width, 1e-4)
            vein = abs(u / half - 0.5) < 0.035
            col = mix(base, accent, 0.30 + 0.55 * edge)
            if vein:
                col = mix(col, base, 0.55)
            return (*(max(0, min(255, c + grain // 3)) for c in col), 255)
        if x < half and y >= half:           # bloom / crystal facet
            r = math.hypot(u - half / 2, v - half / 2) / (half / 2)
            facet = ((u // 14 + v // 11) % 2) * 0.16
            col = mix(bloom, accent, min(1.0, r * 0.72) + facet)
            return (*(max(0, min(255, c + grain // 2)) for c in col), 255)
        mottle = (math.sin(u * 0.13) + math.cos(v * 0.17)
                  + math.sin((u + v) * 0.07)) / 3.0
        col = mix(base, accent, 0.18 + 0.30 * (mottle > 0.05))
        col = tuple(int(c * 0.86) for c in col)
        return (*(max(0, min(255, c + grain)) for c in col), 255)

    return pixel


# --------------------------------------------------------------------------
# E3D output
# --------------------------------------------------------------------------

def write_e3d(path: Path, texture_name: str, build, transparent: bool) -> tuple:
    """Write a single-material E3D.

    `options` is the material transparency flag.  3d_objects.c turns a
    non-zero value into GL_ALPHA_TEST plus a disabled GL_CULL_FACE, which is
    exactly what foliage cards need; solid mineral nodes stay opaque so they
    keep back-face culling and the cheaper solid draw path.
    """
    vertices: list = []
    indices: list = []
    build(vertices, indices)
    if len(vertices) > 65535:
        raise ValueError(f"{path.name}: too many vertices for 16-bit indices")
    vertex_data = b"".join(struct.pack("<8f", *v) for v in vertices)
    index_data = struct.pack("<" + "H" * len(indices), *indices)
    mn = [min(v[5 + i] for v in vertices) for i in range(3)]
    mx = [max(v[5 + i] for v in vertices) for i in range(3)]
    name = texture_name.encode()[:127] + b"\0"
    material = struct.pack("<i128s6f4i", 1 if transparent else 0,
                           name.ljust(128, b"\0"), *mn, *mx,
                           min(indices), max(indices), 0, len(indices))
    elc_size = 28
    vertex_offset = elc_size + 40
    index_offset = vertex_offset + len(vertex_data)
    material_offset = index_offset + len(index_data)
    header = struct.pack("<9i4B", len(vertices), 32, vertex_offset,
                         len(indices), 2, index_offset, 1, 172,
                         material_offset, 1, 0x10, 0, 0)
    payload = header + vertex_data + index_data + material
    import hashlib
    elc = struct.pack("<4s4s16si", b"e3dx", bytes((1, 1, 0, 0)),
                      hashlib.md5(payload).digest(), elc_size)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(elc + payload)
    return len(vertices), len(indices) // 3


def write_obj(path: Path, build, material_name: str, texture: str) -> None:
    vertices: list = []
    indices: list = []
    build(vertices, indices)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = [f"mtllib {path.stem}.mtl", f"usemtl {material_name}"]
    out += [f"v {v[5]:.5f} {v[6]:.5f} {v[7]:.5f}" for v in vertices]
    out += [f"vt {v[0]:.5f} {1 - v[1]:.5f}" for v in vertices]
    out += [f"vn {v[2]:.5f} {v[3]:.5f} {v[4]:.5f}" for v in vertices]
    out += [
        "f " + " ".join(f"{indices[k + o] + 1}/{indices[k + o] + 1}/"
                        f"{indices[k + o] + 1}" for o in range(3))
        for k in range(0, len(indices), 3)
    ]
    path.write_text("\n".join(out) + "\n")
    path.with_suffix(".mtl").write_text(
        f"newmtl {material_name}\nKd 1 1 1\nd 1\nmap_Kd {texture}\n"
        f"map_d {texture}\n")


def write_models(root: Path, obj_source: Path | None = None) -> list:
    """Write every catalogue model, material and (optionally) OBJ source."""
    records = []
    for entry in CATALOGUE:
        rid, label, kind, tier, regions, colors, (build, foliage) = entry
        model = root / MODEL_DIR / f"{rid}.e3d"
        texture = model.with_suffix(".png")
        png(texture, TEXTURE_SIZE, TEXTURE_SIZE, material_pixel(*colors))
        vertex_count, triangles = write_e3d(model, texture.name, build,
                                            foliage)
        if obj_source is not None:
            write_obj(obj_source / f"{rid}.obj", build, rid, texture.name)
        records.append({
            "id": rid, "label": label, "kind": kind, "tier": tier,
            "regions": list(regions),
            "model": model_path(rid),
            "texture": f"{MODEL_DIR}/{rid}.png",
            "alpha_tested": foliage,
            "vertices": vertex_count, "triangles": triangles,
            "respawn_seconds": RESPAWN_SECONDS[tier],
        })
    return records


# --------------------------------------------------------------------------
# decorative ground flora (2D sprites)
# --------------------------------------------------------------------------
# The client has always supported 2D map objects (`obj_2d_io` in io/map_io.h,
# `.2d` definitions in 2d_objects.c) and the generated maps never used them:
# every ELM was written with obj_2d_no == 0.  Ground flora is what that system
# is for, and it costs one alpha-tested quad per instance, so the regions get
# undergrowth without spending landmark budget on it.

FLORA_ATLAS = "nymara_flora.png"
FLORA_DIR = "2dobjects/nymara/flora"
FLORA_CELL = 64
FLORA_COLUMNS = 4

# id, kind, sprite family, (base, tip), size (x, y)
FLORA = (
    ("grass_tuft", "plant", "blades", ((70, 104, 62), (140, 168, 96)), (1.1, 0.8)),
    ("tall_grass", "plant", "blades", ((78, 108, 60), (168, 186, 104)), (1.3, 1.5)),
    ("fern_frond", "plant", "frond", ((42, 92, 58), (96, 150, 84)), (1.4, 1.2)),
    ("wildflower", "plant", "flower", ((74, 108, 66), (214, 176, 96)), (0.9, 0.9)),
    ("reed_tuft", "plant", "blades", ((58, 106, 92), (128, 178, 150)), (1.0, 1.7)),
    ("heather", "plant", "flower", ((72, 82, 66), (150, 118, 168)), (1.0, 0.7)),
    ("dry_brush", "plant", "brush", ((116, 98, 58), (170, 148, 88)), (1.3, 0.9)),
    ("snow_tuft", "plant", "blades", ((122, 140, 142), (206, 224, 226)), (1.0, 0.6)),
    ("jungle_frond", "plant", "frond", ((36, 88, 52), (86, 152, 74)), (1.8, 1.6)),
    ("cattail", "plant", "cattail", ((62, 100, 74), (128, 96, 58)), (0.8, 1.9)),
    ("saltgrass", "plant", "blades", ((124, 128, 96), (188, 190, 150)), (1.1, 0.9)),
    ("thistle_tuft", "plant", "flower", ((70, 88, 72), (108, 112, 176)), (0.9, 1.0)),
    ("lily_pad", "ground", "disc", ((44, 100, 66), (104, 154, 96)), (1.6, 1.6)),
    ("moss_patch", "ground", "patch", ((48, 84, 60), (98, 138, 88)), (1.8, 1.8)),
    ("pebbles", "ground", "patch", ((88, 86, 80), (146, 142, 132)), (1.4, 1.4)),
    ("crystal_grit", "ground", "patch", ((92, 78, 116), (168, 138, 208)), (1.4, 1.4)),
)

REGION_FLORA = {
    "four_gates": ("grass_tuft", "tall_grass", "wildflower", "moss_patch",
                   "pebbles"),
    "mirrorhold": ("reed_tuft", "grass_tuft", "lily_pad", "moss_patch",
                   "wildflower"),
    "crownwater": ("reed_tuft", "cattail", "lily_pad", "grass_tuft",
                   "pebbles"),
    "whitehorn_range": ("snow_tuft", "pebbles", "moss_patch", "heather"),
    "amethyst_barrens": ("dry_brush", "crystal_grit", "pebbles",
                         "thistle_tuft"),
    "sunmane_steppe": ("saltgrass", "dry_brush", "tall_grass", "thistle_tuft",
                       "pebbles"),
    "amberwood": ("grass_tuft", "fern_frond", "wildflower", "moss_patch",
                  "tall_grass"),
    "grey_moors": ("heather", "moss_patch", "tall_grass", "thistle_tuft",
                   "pebbles"),
    "westhaven": ("saltgrass", "grass_tuft", "pebbles", "wildflower"),
    "verdant_stair": ("jungle_frond", "fern_frond", "moss_patch",
                      "wildflower", "lily_pad"),
    "ssarathi_ruins": ("fern_frond", "moss_patch", "jungle_frond", "pebbles"),
    "manymouth_delta": ("cattail", "reed_tuft", "lily_pad", "jungle_frond",
                        "moss_patch"),
}


def flora_pixel(index):
    """One 64x64 alpha sprite per flora entry inside the shared atlas."""
    _, _, family, (base, tip), _ = FLORA[index]

    def mix(a, b, t):
        t = max(0.0, min(1.0, t))
        return tuple(int(p + (q - p) * t) for p, q in zip(a, b))

    def pixel(x, y):
        u = (x + 0.5) / FLORA_CELL
        v = (y + 0.5) / FLORA_CELL
        up = 1.0 - v                      # 0 at the ground, 1 at the top
        grain = ((x * 29 + y * 17 + (x ^ y) * 3) % 21) - 10
        inside = False
        shade = up
        if family == "blades":
            for k in range(5):
                cx = 0.16 + 0.17 * k
                lean = 0.13 * math.sin(k * 2.1)
                axis = cx + lean * up
                width = 0.036 * (1.0 - 0.85 * up)
                if abs(u - axis) < width and up < 0.55 + 0.42 * math.sin(k):
                    inside = True
        elif family == "frond":
            spine = 0.5 + 0.09 * math.sin(up * 2.6)
            d = u - spine
            if abs(d) < 0.024 and up < 0.94:
                inside = True
            for k in range(9):
                t = 0.06 + 0.098 * k
                envelope = 0.44 * math.sin(math.pi * min(1.0, (t + 0.06) * 1.02))
                for side in (-1, 1):
                    if side * d < 0 or abs(d) > envelope:
                        continue
                    lift = t + 0.34 * abs(d)
                    if abs(up - lift) < 0.030 + 0.030 * (1 - abs(d) / max(envelope, 1e-4)):
                        inside = True
                        shade = 0.35 + 0.65 * (1 - abs(d) / max(envelope, 1e-4))
        elif family == "flower":
            if abs(u - 0.5 - 0.04 * up) < 0.022 and up < 0.70:
                inside = True
                shade = 0.15
            for k in range(2):
                a = 0.9 + 1.4 * k
                lx = 0.5 + math.cos(a) * 0.16
                ly = 0.22 + 0.12 * k
                if math.hypot((u - lx) / 0.13, (up - ly) / 0.055) < 1.0:
                    inside = True
                    shade = 0.25
            head = (0.5 + 0.04 * 0.78, 0.78)
            for k in range(6):
                a = 2 * math.pi * k / 6 + 0.3
                px = head[0] + math.cos(a) * 0.135
                py = head[1] + math.sin(a) * 0.135
                du = (u - px) * math.cos(a) + (up - py) * math.sin(a)
                dv = -(u - px) * math.sin(a) + (up - py) * math.cos(a)
                if math.hypot(du / 0.115, dv / 0.062) < 1.0:
                    inside = True
                    shade = 0.92
            if math.hypot(u - head[0], up - head[1]) < 0.070:
                inside = True
                shade = 0.55
        elif family == "brush":
            for k in range(11):
                a = math.pi / 2 + (k - 5) * 0.17
                r = math.hypot(u - 0.5, up)
                if r < 0.02:
                    continue
                ang = math.atan2(up, u - 0.5)
                reach = 0.40 + 0.16 * math.cos((k - 5) * 0.5)
                if abs(ang - a) < 0.030 + 0.020 * (1 - r / reach) and r < reach:
                    inside = True
                    shade = 0.30 + 0.70 * (r / reach)
                if abs(r - reach) < 0.035 and abs(ang - a) < 0.055 and k % 3 == 1:
                    inside = True
                    shade = 1.0
        elif family == "cattail":
            if abs(u - 0.5) < 0.026 and up < 0.96:
                inside = True
            if abs(u - 0.5) < 0.085 and 0.62 < up < 0.90:
                inside = True
                shade = 0.2
            for k in range(3):
                axis = 0.5 + (k - 1) * 0.14
                if abs(u - axis) < 0.03 and up < 0.55:
                    inside = True
        elif family == "disc":
            d = math.hypot(u - 0.5, v - 0.5)
            notch = math.atan2(v - 0.5, u - 0.5)
            if d < 0.44 and not (abs(notch) < 0.10 and d > 0.06):
                inside = True
                shade = 1.0 - d
        else:                              # patch
            d = math.hypot(u - 0.5, v - 0.5)
            wobble = 0.36 + 0.08 * math.sin(math.atan2(v - 0.5, u - 0.5) * 5)
            if d < wobble:
                inside = True
                shade = 1.0 - d * 1.4
        if not inside:
            return (0, 0, 0, 0)
        col = mix(base, tip, shade)
        return (*(max(0, min(255, c + grain // 2)) for c in col), 255)

    return pixel


def write_flora(root: Path) -> list:
    """Write the flora atlas and one `.2d` definition per sprite."""
    rows = (len(FLORA) + FLORA_COLUMNS - 1) // FLORA_COLUMNS
    width = FLORA_COLUMNS * FLORA_CELL
    height = rows * FLORA_CELL

    def atlas(x, y):
        index = (x // FLORA_CELL) + (y // FLORA_CELL) * FLORA_COLUMNS
        if index >= len(FLORA):
            return (0, 0, 0, 0)
        return flora_pixel(index)(x % FLORA_CELL, y % FLORA_CELL)

    directory = root / FLORA_DIR
    directory.mkdir(parents=True, exist_ok=True)
    png(directory / FLORA_ATLAS, width, height, atlas)
    records = []
    for index, (fid, kind, _family, _colors, (sx, sy)) in enumerate(FLORA):
        u0 = (index % FLORA_COLUMNS) * FLORA_CELL
        v0 = (index // FLORA_COLUMNS) * FLORA_CELL
        (directory / f"{fid}.2d").write_text(
            f"file_x_len: {width}\n"
            f"file_y_len: {height}\n"
            f"u_start: {u0}\n"
            f"u_end: {u0 + FLORA_CELL}\n"
            f"v_start: {v0}\n"
            f"v_end: {v0 + FLORA_CELL}\n"
            f"x_size: {sx}\n"
            f"y_size: {sy}\n"
            "alpha_test: 0.22\n"
            f"texture: {FLORA_ATLAS}\n"
            f"type: {kind}\n")
        records.append({"id": fid, "kind": kind,
                        "definition": f"{FLORA_DIR}/{fid}.2d"})
    return records


def flora_for(region: str) -> tuple:
    return REGION_FLORA.get(region, ("grass_tuft", "wildflower", "moss_patch"))


if __name__ == "__main__":
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", default="build/eloria-data")
    parser.add_argument("--obj-source", default=None)
    args = parser.parse_args()
    out = Path(args.output)
    records = write_models(out, Path(args.obj_source) if args.obj_source
                           else None)
    write_flora(out)
    write_harvest_list(out)
    print(json.dumps({"harvestables": len(records),
                      "triangles": {r["id"]: r["triangles"] for r in records}},
                     indent=2))

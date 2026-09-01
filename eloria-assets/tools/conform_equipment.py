#!/usr/bin/env python3
"""Fit a generated equipment mesh onto the shared body rig and skin it.

Added 2026-09-01 for Eloria Client.

``equipment_authoring`` lofts garments from the measured body, so every torso
piece it makes is already a shell around the wearer and already skinned.  A
mesh that arrives from an image-to-3D generator is none of those things: it is
a static island, normalised into a unit cube, with no joints, no weights and no
relationship to the body it is supposed to be worn on.  The client will not
attach it -- ``attach: "skinned"`` needs ``JOINTS_0``/``WEIGHTS_0`` against the
77-joint rig -- and even as a rigid prop it would be roughly four times the
size of the actor.

This closes that gap, and the useful discovery is how little it takes.  A
generated armour piece is already garment-shaped -- the cuirass this was
written against arrives with a collar, a laced front, spiked pauldrons, a belt
and a tasset skirt, all in the right relation to each other.  It does not need
to be conformed to the body.  It needs to be put in the right place at the
right size and bound to the skeleton:

  seat    uniform scale and translate, matching the piece's height to the body
          region it covers.  Uniform because the proportions are the design,
          and the design is the reason to import the mesh at all.
  skin    ``Rig.weights_for``, which hands each vertex the blend of the body
          surface nearest it.  That is what keeps cloth and skin bending as
          one; solving from bone distance instead lets a knee come through a
          trouser the moment it bends.

Two deforming fits are kept behind ``--fit`` for pieces that need rescuing, and
both are worse than leaving the mesh alone.  ``push`` moves every buried vertex
out to the measured skin, which is what a lofted open shell wants -- run on an
imported *solid* it drives the inner surface through the outer one and returns
a shredded coat with the pauldrons flung off sideways.  ``grow`` scales the
whole piece up until the body is inside it, which keeps the design intact but
has no reliable stopping rule: parity enclosure never passes, because a
generated garment is dozens of disjoint solids and no single closed component
holds a torso, and the radial fallback compares the body's shoulders against
the garment's collar at the top slice and oversizes everything.  Reach for
them only with a render open.

  python conform_equipment.py in.glb -o out.glb --kind cuirass
  python conform_equipment.py sourcedir -o outdir --kind boots --race luminous_male
  python conform_equipment.py in.glb -o out.glb --kind legs --report fit.json

The baked texture the generator produced is carried through as the base colour
map, rather than the palette-and-detail-map materials the authored pieces use:
the art is the reason to import the mesh at all.

Exits non-zero if a piece could not be fitted.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

import equipment_authoring as ea
import garment_fit as gf

HERE = Path(__file__).resolve().parent
CLIENT = HERE.parent.parent / "godot-client"
RACES = CLIENT / "assets/actors/native/races"

# The race bodies were rebuilt onto the client rig in 74265e58 and the mesh
# came back named `char1`; `load_rig` still defaults to ("Body",), so it has to
# be told.  Passing None takes every skinned mesh in the file, which is what
# these single-mesh race GLBs want.
BODY_MESH = None

#: How each region's silhouette is measured, mirroring what the lofted shells
#: do rather than inventing a second rule.
#:
#: The bones here are NOT the region's skinning bones.  ``GARMENT_SKIN["torso"]``
#: carries the upper arms, because a vertex at the shoulder of a cuirass should
#: be weighted to the arm that moves it -- but measuring the body against that
#: set reports the half-width out to the elbows, and a chest piece pushed out to
#: that is a barrel with the arms inside it.  ``torso_rings`` measures against
#: ``TORSO_BONES``, which stops at the clavicles, and so does this.
#:
#: ``vertical`` measures about the world upright through the body centre, the
#: axis ``torso_rings`` uses.  ``sides`` splits the mesh at x=0 and measures
#: each half against its own limb, because trousers are two tubes and a right
#: leg sized against the left one is sized against thin air.
MEASURE = {
    "torso": {"mode": "vertical", "bones": ea.TORSO_BONES},
    "skirt": {"mode": "vertical",
              "bones": ea.TORSO_BONES + ["thigh_l", "thigh_r"]},
    "legs": {"mode": "sides", "axis": ("thigh_%s", "calf_%s"),
             "bones": ("thigh_%s", "calf_%s")},
    "boots": {"mode": "sides", "axis": ("calf_%s", "ball_%s"),
              "bones": ("calf_%s", "foot_%s", "ball_%s")},
}

#: How far outside the skin a fitted vertex is parked, in metres.  The authored
#: shells sit at 11 mm; matching that keeps an imported piece from reading as
#: baggier than the set it joins.
CLEARANCE = 0.011

#: How much wider than the body's own box a seated piece is allowed to sit, as
#: a fraction.  Six per cent is a garment worn over a body rather than sprayed
#: onto one, and it is what keeps the shell clear of the skin once a limb bends.
SLACK = 0.06

#: Bounds on that draw-in.  A piece is never taken below three quarters -- past
#: that the design is being restyled rather than fitted, and a pauldron that was
#: drawn proud stops reading as one.  Letting out is capped nearer to 1: a piece
#: that has to grow much at all was misread, and a render will show it.
TIGHTEST, LOOSEST = 0.75, 1.15

#: Where each kind of garment sits on the reference body, as world Y at
#: ``fit_scale`` 1.  The torso pair is the module's own hem and collar; the limb
#: pairs are measured off the authored ranger set, which is the reference these
#: pieces are joining -- amberwood_ranger_legs spans 0.184..1.088 and
#: amberwood_ranger_boots -0.013..0.320.  A region with no entry falls back to
#: the extent of the body it is weighted against.
SPAN = {
    "torso": (ea.TORSO_HEM, ea.COLLAR_TOP),
    "legs": (0.184, 1.088),
    "boots": (-0.013, 0.320),
}


#: Headwear and the rest of the socket-attached kinds.  A socket piece is a
#: plain static mesh -- ``amberwood_ranger_hood.glb`` is one node with no skin,
#: exactly the shape a generated mesh already arrives in -- so nothing has to be
#: bound for these.  What they need is the other thing a generated mesh lacks:
#: to be the size of a head, and to be authored about the socket rather than
#: about the world, because the runtime hangs them off a bone and the mesh has
#: to be drawn where that bone will put it.
SOCKET_KIND = {
    "helm": {"part": 3, "bones": ["Head"], "clearance": .014},
    "hood": {"part": 3, "bones": ["Head"], "clearance": .018},
    "circlet": {"part": 3, "bones": ["Head"], "clearance": .010},
}


class Imported:
    """A ``Surface``-shaped view of a mesh that came from a file.

    ``build_equipment_piece`` takes a caller-supplied surface -- the footwear
    catalogue already does that -- and only needs three things from it, so this
    supplies exactly those rather than pretending to be the full builder.
    """

    def __init__(self, positions, normals, uvs, indices):
        self.positions = np.asarray(positions, dtype=np.float64)
        self.normals = np.asarray(normals, dtype=np.float64)
        self.uvs = np.asarray(uvs, dtype=np.float64)
        self.indices = np.asarray(indices, dtype=np.uint32).reshape(-1)
        self.pins = [[], [], []]

    def scope_array(self, material: int, count: int) -> np.ndarray:
        # One scope for the whole piece: an imported mesh carries no record of
        # which part of it is a sole and which is a shaft.
        return np.asarray([""] * count, dtype=object)

    def arrays(self):
        empty = (np.zeros((0, 3), "float32"), np.zeros((0, 3), "float32"),
                 np.zeros((0, 2), "float32"), np.zeros(0, "uint32"))
        return [(self.positions, self.normals, self.uvs, self.indices),
                empty, empty]


def read_source(path: Path) -> tuple[Imported, bytes | None]:
    """Positions, normals, UVs and indices of a GLB, plus its base colour PNG."""
    document, binary = ea.read_glb(path)
    matrices = ea.global_matrices(document)
    positions, normals, uvs, indices = [], [], [], []
    base = 0
    for index, node in enumerate(document.get("nodes", [])):
        if "mesh" not in node:
            continue
        matrix = matrices[index]
        for primitive in document["meshes"][node["mesh"]]["primitives"]:
            attributes = primitive["attributes"]
            points = ea.accessor_array(document, binary, attributes["POSITION"])
            points = points @ matrix[:3, :3].T + matrix[:3, 3]
            if "NORMAL" in attributes:
                normal = ea.accessor_array(document, binary, attributes["NORMAL"])
                normal = normal @ np.linalg.inv(matrix[:3, :3]).T
            else:
                normal = np.tile([0., 1., 0.], (len(points), 1))
            if "TEXCOORD_0" in attributes:
                uv = ea.accessor_array(document, binary, attributes["TEXCOORD_0"])
            else:
                uv = np.zeros((len(points), 2))
            triangles = ea.accessor_array(
                document, binary, primitive["indices"]).reshape(-1)
            positions.append(np.asarray(points, dtype=np.float64))
            normals.append(np.asarray(normal, dtype=np.float64))
            uvs.append(np.asarray(uv, dtype=np.float64)[:, :2])
            indices.append(np.asarray(triangles, dtype=np.int64) + base)
            base += len(points)
    if not positions:
        raise ValueError(f"no mesh in {path.name}")

    png = None
    images = document.get("images", [])
    if images:
        view = document["bufferViews"][images[0]["bufferView"]]
        start = view.get("byteOffset", 0)
        png = bytes(binary[start:start + view["byteLength"]])

    return Imported(np.vstack(positions), np.vstack(normals),
                    np.vstack(uvs), np.concatenate(indices)), png


def measure_bones(region: str, side: str = "l") -> list[str]:
    spec = MEASURE[region]
    if spec["mode"] == "vertical":
        return list(spec["bones"])
    return [name % side for name in spec["bones"]]


def region_points(rig: ea.Rig, region: str) -> np.ndarray:
    """The body this region is sized against -- both limbs, for a limb region."""
    spec = MEASURE[region]
    if spec["mode"] == "vertical":
        return rig._region(measure_bones(region))
    return np.vstack([rig._region(measure_bones(region, side))
                      for side in ("l", "r")])


def cast(origin: np.ndarray, direction: np.ndarray,
         verts: np.ndarray) -> tuple[float, int]:
    """Nearest forward hit along a ray, and how many times it crosses at all.

    ``garment_fit._crossings`` answers the parity question for many origins at
    once and throws the distances away; this is the other half of it -- one
    origin, and the distance to the first surface it meets.  Same
    Moller-Trumbore arrangement and the same epsilons, so the two agree about
    what counts as a hit.

    The crossing count comes back with it because it is the check that the ray
    started somewhere meaningful: an origin inside a closed shell crosses it an
    odd number of times, and a measurement taken from outside the garment would
    otherwise report the outer surface as though it were the lining.
    """
    corner = verts[:, 0]
    edge1 = verts[:, 1] - corner
    edge2 = verts[:, 2] - corner
    pvec = np.cross(direction, edge2)
    det = np.einsum("ij,ij->i", edge1, pvec)
    live = np.abs(det) > 1e-12
    if not live.any():
        return math.inf, 0
    corner, edge1, edge2 = corner[live], edge1[live], edge2[live]
    inv = 1.0 / det[live]
    tvec = origin - corner
    u = np.einsum("mj,mj->m", tvec, pvec[live]) * inv
    qvec = np.cross(tvec, edge1)
    v = (qvec @ direction) * inv
    distance = np.einsum("mj,mj->m", qvec, edge2) * inv
    hit = (u >= 0.) & (v >= 0.) & (u + v <= 1.) & (distance > 1e-7)
    if not hit.any():
        return math.inf, 0
    return float(distance[hit].min()), int(hit.sum())


def hug_profile(shell: np.ndarray, skin: np.ndarray, axis: np.ndarray,
                clearance: float = CLEARANCE, rows: int = 12,
                sectors: int = 12,
                verts: np.ndarray | None = None
                ) -> tuple[np.ndarray, np.ndarray]:
    """How much to take the piece in or let it out, height by height.

    One factor for the whole garment cannot serve a waist and an ankle at the
    same time: the trouser that is half again too wide at the cuff is barely
    clear of the thigh, and a single number either pinches the thigh or leaves
    the cuff flapping.  So each height band gets its own, measured where the
    band actually is, and a vertex takes the factor interpolated at its height.

    Within a band the rule is the same one a single factor used: in each
    angular sector the garment has surface in, its innermost surface has to
    clear the furthest skin.  Bands are smoothed along the height afterwards,
    because a profile that steps between neighbouring bands puts a crease
    around the leg.
    """
    low, high = float(skin[:, 1].min()), float(skin[:, 1].max())
    centres = low + (high - low) * (np.arange(rows) + .5) / rows
    factors = np.ones(rows)
    for row in range(rows):
        band_lo = low + (high - low) * row / rows
        band_hi = low + (high - low) * (row + 1) / rows
        in_skin = skin[(skin[:, 1] >= band_lo) & (skin[:, 1] < band_hi)]
        if len(in_skin) < 3:
            factors[row] = np.nan          # no skin here to be answerable for
            continue
        skin_a = np.arctan2(in_skin[:, 2] - axis[1], in_skin[:, 0] - axis[0])
        skin_r = np.linalg.norm(in_skin[:, [0, 2]] - axis, axis=1)
        height = float((band_lo + band_hi) / 2.)
        origin = np.array([axis[0], height, axis[1]])
        # Only the triangles this band could contain, so each ray is cast at a
        # few hundred rather than a few thousand.
        near = verts[(verts[:, :, 1].min(axis=1) <= band_hi + .02)
                     & (verts[:, :, 1].max(axis=1) >= band_lo - .02)]
        if not len(near):
            factors[row] = np.nan
            continue
        want = 1.0
        measured = 0
        for sector in range(sectors):
            angle = 2 * np.pi * (sector + .5) / sectors
            direction = np.array([math.cos(angle), 0., math.sin(angle)])
            inner, crossings = cast(origin, direction, near)
            # Even means the ray started outside this garment, so the surface
            # it met is the outside of it and says nothing about the lining.
            if not np.isfinite(inner) or crossings % 2 == 0:
                continue
            lo = angle - np.pi / sectors
            here = (np.mod(skin_a - lo, 2 * np.pi) < 2 * np.pi / sectors)
            if here.sum() < 2:
                continue
            outer = float(np.percentile(skin_r[here], 92.))
            want = max(want, (outer + clearance) / max(inner, 1e-6))
            measured += 1
        factors[row] = want if measured else np.nan
    if np.isnan(factors).all():
        return centres, np.ones(rows)
    # Carry the nearest measured band into the ones that had nothing in them,
    # so a cuff below the last skin keeps the profile of the leg above it.
    good = ~np.isnan(factors)
    factors = np.interp(centres, centres[good], factors[good])
    smoothed = factors.copy()
    for _ in range(2):
        smoothed = np.convolve(np.pad(smoothed, 1, mode="edge"),
                               [1 / 3., 1 / 3., 1 / 3.], mode="valid")
    return centres, np.clip(smoothed, TIGHTEST, LOOSEST)


def hug_factor(points: np.ndarray, rig: ea.Rig, region: str,
               clearance: float = CLEARANCE, rows: int = 10,
               sectors: int = 12) -> float:
    """Smallest horizontal scale that still keeps the skin inside the garment.

    Measured against the garment's *innermost* surface in each direction, not
    against its bounding box.  The box is set by whatever sticks out furthest --
    a knee pad, a strap, a pauldron -- and on this legwear it reads half again
    too wide while the trouser tube itself is barely clear of the thigh.  Taking
    the piece in by that ratio drags the tube inside the leg and the body walks
    out through the front of its own trousers.

    So each height band is cut into sectors, and in every sector that the
    garment actually has surface in, the nearest garment vertex has to stay
    outside the furthest skin vertex.  Sectors it has no surface in are its
    openings -- a boot's collar, a sleeve's cuff -- and nothing can be said
    about those from here.
    """
    groups = []
    if MEASURE[region]["mode"] == "vertical":
        groups.append((points, rig._region(measure_bones(region))))
    else:
        for side in ("l", "r"):
            own = points[:, 0] >= 0 if side == "l" else points[:, 0] < 0
            groups.append((points[own], rig._region(measure_bones(region, side))))

    needed = 0.0
    for shell, skin in groups:
        if len(shell) < 8 or len(skin) < 8:
            continue
        # About this group's own upright: for a pair, each leg answers to the
        # limb it is worn on rather than to the midline between them.
        axis = np.array([float(np.median(skin[:, 0])), float(np.median(skin[:, 2]))])
        low, high = float(skin[:, 1].min()), float(skin[:, 1].max())
        for row in range(rows):
            band_lo = low + (high - low) * row / rows
            band_hi = low + (high - low) * (row + 1) / rows
            in_skin = skin[(skin[:, 1] >= band_lo) & (skin[:, 1] < band_hi)]
            in_shell = shell[(shell[:, 1] >= band_lo) & (shell[:, 1] < band_hi)]
            if len(in_skin) < 3 or len(in_shell) < 3:
                continue
            skin_a = np.arctan2(in_skin[:, 2] - axis[1], in_skin[:, 0] - axis[0])
            shell_a = np.arctan2(in_shell[:, 2] - axis[1], in_shell[:, 0] - axis[0])
            skin_r = np.linalg.norm(in_skin[:, [0, 2]] - axis, axis=1)
            shell_r = np.linalg.norm(in_shell[:, [0, 2]] - axis, axis=1)
            for sector in range(sectors):
                lo = -np.pi + 2 * np.pi * sector / sectors
                hi = -np.pi + 2 * np.pi * (sector + 1) / sectors
                here_skin = (skin_a >= lo) & (skin_a < hi)
                here_shell = (shell_a >= lo) & (shell_a < hi)
                if here_skin.sum() < 2 or here_shell.sum() < 2:
                    continue
                inner = float(np.percentile(shell_r[here_shell], 12.))
                outer = float(np.percentile(skin_r[here_skin], 92.))
                if inner > 1e-6:
                    needed = max(needed, (outer + clearance) / inner)
    if needed <= 0.:
        return 1.0
    return float(np.clip(needed, TIGHTEST, LOOSEST))


def lateral_profile(skin: np.ndarray, pivot: np.ndarray,
                    verts: np.ndarray, rows: int = 12
                    ) -> tuple[np.ndarray, np.ndarray]:
    """How far each height of one limb's garment misses that limb by.

    The fault a girth scale cannot touch.  Seated on height alone, this legwear
    puts each trouser leg 80 mm outboard of the thigh inside it: cast a ray at
    mid-thigh and the outboard side has 190 mm of room while the inboard wall
    is at 47 mm, well inside the 80 mm leg.  Scaling the band cannot mend that
    -- widening to clear the inboard side doubles an outboard gap that was
    already too big.  The garment is not the wrong size, it is in the wrong
    place, and the answer is to move it.

    Measured band by band and applied by interpolation rather than as one rigid
    shift, so a joined garment does not tear: the offset dies away over the
    height where the two legs merge into a seat, because up there the garment
    is a single tube already centred on the body and the measurement says so.
    """
    low, high = float(skin[:, 1].min()), float(skin[:, 1].max())
    centres = low + (high - low) * (np.arange(rows) + .5) / rows
    offsets = np.full((rows, 2), np.nan)
    for row in range(rows):
        band_lo = low + (high - low) * row / rows
        band_hi = low + (high - low) * (row + 1) / rows
        in_skin = skin[(skin[:, 1] >= band_lo) & (skin[:, 1] < band_hi)]
        if len(in_skin) < 4:
            continue
        height = float((band_lo + band_hi) / 2.)
        origin = np.array([pivot[0], height, pivot[1]])
        near = verts[(verts[:, :, 1].min(axis=1) <= band_hi + .02)
                     & (verts[:, :, 1].max(axis=1) >= band_lo - .02)]
        if not len(near):
            continue
        # Where the wall is on each side, found by ray rather than inferred
        # from the spread of vertices.  That distinction is the whole point:
        # a percentile of vertex position is pulled outboard by every strap and
        # knee pad hanging off the design, so a centre computed that way sits
        # outboard of the real garment and the correction overshoots inboard --
        # which is a trouser pulled tight against the leg it should hang from.
        # A ray finds the body-facing surface and ignores the decoration.
        for index, axis in enumerate((0, 2)):
            reach = []
            for sign in (1., -1.):
                direction = np.zeros(3)
                direction[axis] = sign
                distance, crossings = cast(origin, direction, near)
                reach.append(distance if (np.isfinite(distance)
                                          and crossings % 2 == 1) else None)
            if reach[0] is None or reach[1] is None:
                continue
            # Centre the lining on the limb: half the difference between the
            # two walls is how far off it currently sits.
            offsets[row, index] = -(reach[0] - reach[1]) / 2.
    # Per column: a band can find its walls on one axis and not the other -- a
    # boot at ankle height is bounded left and right and open front to back --
    # and a mask taken from one axis carries the other's gaps through the
    # interpolation as NaN, which reaches the skin weights as a bad cast.
    for index in (0, 1):
        good = ~np.isnan(offsets[:, index])
        if not good.any():
            offsets[:, index] = 0.
            continue
        offsets[:, index] = np.interp(centres, centres[good],
                                      offsets[good, index])
    for _ in range(3):
        offsets = np.stack([np.convolve(np.pad(offsets[:, i], 1, mode="edge"),
                                        [1 / 3., 1 / 3., 1 / 3.], mode="valid")
                            for i in (0, 1)], axis=1)
    return centres, offsets


def group_masks(points: np.ndarray, region: str):
    """Which vertices answer to which body, as (mask, measuring bones) pairs."""
    if MEASURE[region]["mode"] == "vertical":
        return [(np.ones(len(points), dtype=bool), measure_bones(region))]
    return [(points[:, 0] >= 0, measure_bones(region, "l")),
            (points[:, 0] < 0, measure_bones(region, "r"))]


def halves_are_separate(points: np.ndarray, triangles: np.ndarray) -> bool:
    """True when nothing joins the left of the piece to the right.

    A pair of boots is two solids and each may be moved onto its own foot.
    Trousers are one, and moving half of them opens a hole.
    """
    if triangles is None or not len(triangles):
        return False
    spanning = 0
    for shell in gf.components(points, triangles):
        used = shell.points[np.unique(shell.triangles)]
        if not len(used):
            continue
        # A component with material on both sides of the midline is the thing
        # that joins them, so the piece is one garment and cannot be split.
        if used[:, 0].min() < -.02 and used[:, 0].max() > .02:
            spanning += 1
    return spanning == 0


def seat(points: np.ndarray, rig: ea.Rig, region: str,
         triangles: np.ndarray | None = None,
         taper: bool = False) -> np.ndarray:
    """Uniform scale and translate so the piece occupies the garment's span.

    Sized to where the garment goes, not to the whole region it is weighted
    against.  ``torso`` reaches the pelvis, but a cuirass hangs from the hem at
    ``TORSO_HEM`` -- seated against the region it would be stretched a third
    again too tall and worn as a dress.
    """
    body = region_points(rig, region)
    span = SPAN.get(region)
    # Every garment is anchored to the span the authored set uses, because
    # where a piece ends is load-bearing on both axes.  On the limbs the legs
    # region runs down through the foot bones, and a trouser stretched to fill
    # it hems on the floor past the boot it tucks into.  On the torso the
    # region reaches the pelvis, and a cuirass stretched to fill it hangs 26 cm
    # below an authored one, over the hips and into the legs slot: nearly half
    # its vertices come out weighted to `pelvis` where an authored chest piece
    # is weighted to the spine, so it rides the hips instead of the chest.
    if span is not None:
        low, high = (value * rig.fit_scale for value in span)
    else:
        low, high = float(body[:, 1].min()), float(body[:, 1].max())

    extent = points.max(axis=0) - points.min(axis=0)
    # Height is the honest axis to scale on: a piece drawn front-on is as tall
    # as what it covers, while its depth is whatever the generator inferred
    # from the single view it was given.
    scale = (high - low) / max(float(extent[1]), 1e-9)

    # Girth is scaled separately from height, and only for the limb garments.
    # One uniform number cannot serve both: a trouser tall enough to reach the
    # floor is wide enough to hang off the leg, and one cut to hem at 0.184 for
    # the boot to swallow is 18 per cent narrower with it and disappears inside
    # the thigh.  Height answers to the authored span because the seam tests
    # measure where a hem lands; girth answers to the body region, which is
    # what put the trousers around the legs in the first place.  Vertical
    # against horizontal keeps the plan view of the design intact -- the piece
    # is made longer or shorter, never skewed.
    girth = scale
    if span is not None:
        body_span = float(body[:, 1].max()) - float(body[:, 1].min())
        girth = body_span / max(float(extent[1]), 1e-9)

    seated = (points - (points.max(axis=0) + points.min(axis=0)) / 2.)
    seated[:, 1] *= scale
    seated[:, 0] *= girth
    seated[:, 2] *= girth
    centre = (body.max(axis=0) + body.min(axis=0)) / 2.
    seated[:, 0] += centre[0]
    seated[:, 2] += centre[2]
    seated[:, 1] += (low + high) / 2.

    # Then sit each half of a pair on the limb it is worn on.  Sized on height
    # alone the trouser legs seat 80 mm outboard of the thighs and the boots 60
    # mm, because the generator draws a wider stance than the rig stands in, and
    # that splay is what the shins graze their way out through.
    #
    # Only when the halves are separate solids.  A rigid shift of one leg of a
    # joined garment tears it at the crotch, and the alternative -- taking the
    # whole piece in about the midline until the splay closes -- was measured
    # and is worse: the bounding box it would be scaled by is set by whatever
    # sticks out furthest, so on this legwear (knee pads, straps) it reads half
    # again too wide while the tube is barely clear of the thigh, and drawing it
    # in by that ratio pulls the trousers inside the leg.
    # Put each half of a pair over the limb it is worn on.  Rigid, and only
    # when the halves are separate solids: shifting half of a joined garment
    # opens a hole at the crotch.
    if MEASURE[region]["mode"] == "sides" and halves_are_separate(seated,
                                                                 triangles):
        for side in ("l", "r"):
            own = seated[:, 0] >= 0 if side == "l" else seated[:, 0] < 0
            if own.sum() < 8:
                continue
            limb = rig._region(measure_bones(region, side))
            half = seated[own]
            for axis in (0, 2):
                shift = ((limb[:, axis].max() + limb[:, axis].min()) / 2.
                         - (half[:, axis].max() + half[:, axis].min()) / 2.)
                seated[own, axis] += shift

    # Per-height placement and girth.  Both off by default; see the note above
    # `lateral_profile` for why the measurement is not trustworthy yet.
    if taper:
        for own, bones in group_masks(seated, region):
            if own.sum() < 8:
                continue
            skin = rig._region(bones)
            pivot = np.array([float(np.median(skin[:, 0])),
                              float(np.median(skin[:, 2]))])
            heights, offsets = lateral_profile(skin, pivot,
                                               seated[triangles])
            block = seated[own]
            for index, axis in enumerate((0, 2)):
                block[:, axis] += np.interp(block[:, 1], heights,
                                            offsets[:, index])
            seated[own] = block

    # Girth, band by band -- off unless asked for.  The idea is right and is
    # what the runtime itself does through `bodyGirth`: one factor cannot serve
    # a waist and an ankle, so each height should get its own.  With the piece
    # centred the ray cast finds a real lining to measure against, but the two
    # sides of a band still disagree by more than one scale can express, so it
    # stays opt-in until it is measured against a fuller set of designs.
    if taper:
        for own, bones in group_masks(seated, region):
            if own.sum() < 8:
                continue
            skin = rig._region(bones)
            pivot = np.array([float(np.median(skin[:, 0])),
                              float(np.median(skin[:, 2]))])
            heights, factors = hug_profile(
                seated[own], skin, pivot, verts=seated[triangles])
            scale = np.interp(seated[own, 1], heights, factors)
            block = seated[own]
            for index, axis in enumerate((0, 2)):
                block[:, axis] = ((block[:, axis] - pivot[index]) * scale
                                  + pivot[index])
            seated[own] = block
    return seated


def _push_axis(points: np.ndarray, indices: np.ndarray, rig: ea.Rig,
               axis_start: np.ndarray, axis_end: np.ndarray, bones: list[str],
               clearance: float, moved: np.ndarray) -> int:
    """Push one group of vertices out to the body measured about one axis."""
    axis = axis_end - axis_start
    length = float(np.linalg.norm(axis))
    if length < 1e-6 or not len(indices):
        return 0
    axis = axis / length
    reference = (np.array([0., 1., 0.]) if abs(axis[1]) < .8
                 else np.array([0., 0., 1.]))
    right = np.cross(axis, reference)
    right /= np.linalg.norm(right)
    forward = np.cross(right, axis)

    pushed = 0
    for index in indices:
        offset = points[index] - axis_start
        along = float(offset @ axis)
        radial = offset - along * axis
        distance = float(np.linalg.norm(radial))
        if distance < 1e-6:
            continue
        angle = math.atan2(float(radial @ forward), float(radial @ right))
        radius = rig.surface_radius(axis_start, axis_end, along / length, angle,
                                    bones=bones, slab=.05, default=.0)
        want = radius + clearance
        if radius > 0. and distance < want:
            moved[index] = points[index] + radial / distance * (want - distance)
            pushed += 1
    return pushed


def grow_clear(points: np.ndarray, triangles: np.ndarray, rig: ea.Rig,
               region: str, clearance: float = CLEARANCE,
               limit: float = 1.35) -> tuple[np.ndarray, float]:
    """Scale the piece up about its own centre until the body fits inside it.

    The alternative -- moving each buried vertex out to the skin -- is what a
    lofted shell can afford and an imported mesh cannot.  A generated garment
    is a closed solid: it has an inner surface as well as an outer one, and
    pushing the inner surface out to the body drives it through the outer one.
    The cuirass that comes back is shredded, with the pauldrons flung out
    sideways as loose slabs.  Growing the whole piece keeps every relation in
    the design intact and only costs a garment that reads slightly loose.
    """
    spec = MEASURE[region]
    if spec["mode"] == "vertical":
        groups = [(np.arange(len(points)), measure_bones(region), None)]
    else:
        groups = []
        for side in ("l", "r"):
            own = np.flatnonzero(points[:, 0] >= 0 if side == "l"
                                 else points[:, 0] < 0)
            groups.append((own, measure_bones(region, side), side))

    body = np.vstack([rig._region(bones) for _i, bones, _s in groups])
    centre = (points.max(axis=0) + points.min(axis=0)) / 2.
    # Only the skin the piece covers: a cuirass is not answerable for an ankle,
    # and counting one would grow it forever.
    span = SPAN.get(region)
    if span is not None:
        low, high = (value * rig.fit_scale for value in span)
        body = body[(body[:, 1] >= low) & (body[:, 1] <= high)]
    if not len(body):
        return points, 1.0

    # Compared in horizontal slices about the piece's own upright.  Parity
    # enclosure would be the better question -- is the body *inside* the shell --
    # but a generated garment is dozens of disjoint solids (plates, laces,
    # buckles) and no single closed component contains a torso, so the test can
    # never pass and every piece saturates at the limit.
    axis = np.array([centre[0], centre[2]])
    needed = 1.0
    for step in range(14):
        height = float(body[:, 1].min()) + (
            float(body[:, 1].max()) - float(body[:, 1].min())) * (step + .5) / 14.
        band = (float(body[:, 1].max()) - float(body[:, 1].min())) / 28. + .01
        skin = body[np.abs(body[:, 1] - height) <= band]
        shell = points[np.abs(points[:, 1] - height) <= band]
        if len(skin) < 4 or len(shell) < 4:
            continue
        skin_r = float(np.percentile(
            np.linalg.norm(skin[:, [0, 2]] - axis, axis=1), 96.))
        shell_r = float(np.percentile(
            np.linalg.norm(shell[:, [0, 2]] - axis, axis=1), 96.))
        if shell_r > 1e-6:
            needed = max(needed, (skin_r + clearance) / shell_r)
    scale = float(min(needed, limit))
    return (points - centre) * scale + centre, scale


def clear_body(points: np.ndarray, rig: ea.Rig, region: str,
               clearance: float = CLEARANCE) -> tuple[np.ndarray, int]:
    """Push vertices that sit inside the skin out to the measured surface.

    Kept for open shells, where it is the right tool; ``grow_clear`` is the
    default because imported solids are not open shells.
    """
    spec = MEASURE[region]
    moved = np.array(points, dtype=np.float64)
    if spec["mode"] == "vertical":
        body = region_points(rig, region)
        # The upright through the body centre, spanning what the region covers:
        # the axis `torso_rings` measures its own shells about.
        centre = (body.max(axis=0) + body.min(axis=0)) / 2.
        start = np.array([centre[0], float(body[:, 1].min()), centre[2]])
        end = np.array([centre[0], float(body[:, 1].max()), centre[2]])
        pushed = _push_axis(points, np.arange(len(points)), rig, start, end,
                            measure_bones(region), clearance, moved)
        return moved, pushed

    pushed = 0
    for side in ("l", "r"):
        bones = measure_bones(region, side)
        start = rig.origin(spec["axis"][0] % side)
        end = rig.origin(spec["axis"][1] % side)
        # Split at the body midline: each half belongs to the limb on its side.
        own = np.flatnonzero(points[:, 0] >= 0 if side == "l"
                             else points[:, 0] < 0)
        pushed += _push_axis(points, own, rig, start, end, bones, clearance,
                             moved)
    return moved, pushed


def textured_material(glb: ea.EquipmentGLB, name: str, png: bytes | None,
                      colour=(190, 185, 178)) -> int:
    """Base colour straight off the generated map, when there is one."""
    pbr = {"baseColorFactor": ea.srgb_to_linear(colour) + [1.],
           "metallicFactor": 0.0, "roughnessFactor": 0.72}
    if png is not None:
        pbr["baseColorFactor"] = [1., 1., 1., 1.]
        pbr["baseColorTexture"] = {"index": glb.texture(png)}
    glb.doc["materials"].append(
        {"name": name, "pbrMetallicRoughness": pbr, "doubleSided": False})
    return len(glb.doc["materials"]) - 1


def socket_origin(rig: ea.Rig, part: int) -> np.ndarray:
    """Where the runtime will hang this part, in world space."""
    socket = ea.build_sockets(rig).get(part)
    origin = rig.origin(socket.bone if socket else "Head")
    offset = np.asarray(getattr(socket, "offset", (0., 0., 0.)),
                        dtype=np.float64)
    return origin + offset


def seat_socket(points: np.ndarray, rig: ea.Rig, kind: str) -> np.ndarray:
    """Size a socket piece to what it is worn on and centre it on the socket.

    Authored about the socket, not about the world: the runtime attaches the
    scene to a bone and applies the socket's own offset, so a mesh drawn at the
    head's world height would be lifted by that height again and worn as a
    hat above the hat.  The reference pieces confirm the convention --
    ``amberwood_ranger_hood`` is centred within 9 mm of its own origin.
    """
    spec = SOCKET_KIND[kind]
    head = rig._region(spec["bones"])
    span = head.max(axis=0) - head.min(axis=0)
    extent = points.max(axis=0) - points.min(axis=0)
    # Enclose the head on its widest axis rather than matching height: a helm
    # is a shell around a skull, and sizing it by height alone leaves a tall
    # crest pulling the whole piece down inside the face.
    scale = max((span[axis] + 2 * spec["clearance"]) / max(float(extent[axis]),
                                                           1e-9)
                for axis in (0, 2))
    seated = (points - (points.max(axis=0) + points.min(axis=0)) / 2.) * scale
    centre = (head.max(axis=0) + head.min(axis=0)) / 2.
    return seated + (centre - socket_origin(rig, spec["part"]))


def build_socket(source: Path, out: Path, rig: ea.Rig, kind: str,
                 label: str) -> dict:
    """Size and place one socket piece, and write it unskinned."""
    surface, png = read_source(source)
    before = surface.positions.copy()
    surface.positions = seat_socket(surface.positions, rig, kind)

    glb = ea.EquipmentGLB(generator="Eloria conform_equipment")
    material = textured_material(glb, "%s Base" % label, png)
    positions, normals, uvs, indices = surface.arrays()[0]
    primitive = glb.primitive(positions, normals, uvs, indices, material)
    glb.mesh(label, [primitive])
    glb.write(out)

    span_before = before.max(axis=0) - before.min(axis=0)
    span_after = surface.positions.max(axis=0) - surface.positions.min(axis=0)
    return {"source": source.name, "out": out.name, "kind": kind,
            "region": "", "attach": "socket",
            "vertices": int(len(positions)),
            "triangles": int(len(indices) // 3), "joints": 0,
            "scale": round(float(span_after[1] / max(span_before[1], 1e-9)), 4),
            "spanBefore": [round(float(v), 3) for v in span_before],
            "spanAfter": [round(float(v), 3) for v in span_after],
            "fit": "socket", "grew": 1.0, "pushedOut": 0,
            "textured": png is not None, "bytes": out.stat().st_size}


def build(source: Path, out: Path, rig: ea.Rig, kind: str, label: str,
          clearance: float = CLEARANCE, fit: str = "seat",
          taper: bool = False) -> dict:
    """Fit one generated mesh to the rig and write it as a skinned piece."""
    if kind in SOCKET_KIND:
        return build_socket(source, out, rig, kind, label)
    if kind not in ea.GARMENT_KINDS:
        raise ValueError("%s is neither a garment kind (%s) nor a socket kind "
                         "(%s)" % (kind, ", ".join(sorted(ea.GARMENT_KINDS)),
                                   ", ".join(sorted(SOCKET_KIND))))
    region = ea.garment_region(kind)
    if region not in MEASURE:
        raise ValueError(f"no measuring rule for region {region!r}; "
                         f"known: {sorted(MEASURE)}")

    surface, png = read_source(source)
    before = surface.positions.copy()
    seated = seat(surface.positions, rig, region,
                  surface.indices.reshape(-1, 3), taper)
    if fit == "push":
        fitted, pushed = clear_body(seated, rig, region, clearance)
        grown = 1.0
    elif fit == "grow":
        fitted, grown = grow_clear(
            seated, surface.indices.reshape(-1, 3), rig, region,
            clearance)
        pushed = 0
    else:
        fitted, grown, pushed = seated, 1.0, 0
    surface.positions = fitted

    glb = ea.EquipmentGLB(generator="Eloria conform_equipment")
    material = textured_material(glb, f"{label} Base", png)
    glb.skeleton(rig)
    positions, normals, uvs, indices = surface.arrays()[0]
    joints, weights = ea.Rig.weights_for(
        rig, positions.astype(np.float64), list(ea.GARMENT_SKIN[region]))
    primitive = glb.primitive(positions, normals, uvs, indices, material,
                              joints=joints, weights=weights)
    glb.mesh(label, [primitive], skin=0)
    glb.write(out)

    span_before = (before.max(axis=0) - before.min(axis=0))
    span_after = (fitted.max(axis=0) - fitted.min(axis=0))
    return {"source": source.name, "out": out.name, "kind": kind,
            "region": region, "vertices": int(len(positions)),
            "triangles": int(len(indices) // 3),
            "joints": len(rig.joint_names),
            "scale": round(float(span_after[1] / max(span_before[1], 1e-9)), 4),
            "spanBefore": [round(float(v), 3) for v in span_before],
            "spanAfter": [round(float(v), 3) for v in span_after],
            "fit": fit, "grew": round(float(grown), 4),
            "pushedOut": pushed, "textured": png is not None,
            "bytes": out.stat().st_size}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="fit a generated equipment mesh to the body rig and skin it")
    ap.add_argument("input", nargs="+", help="GLB files or directories")
    ap.add_argument("-o", "--output", required=True,
                    help="output file (one input) or directory")
    ap.add_argument("--kind", required=True,
                    help="garment kind (%s) or socket kind (%s)"
                         % (", ".join(sorted(ea.GARMENT_KINDS)),
                            ", ".join(sorted(SOCKET_KIND))))
    ap.add_argument("--race", default="luminous_male",
                    help="race rig to author against (default luminous_male)")
    ap.add_argument("--races-dir", default=str(RACES))
    ap.add_argument("--clearance", type=float, default=CLEARANCE, metavar="M",
                    help="metres to hold off the skin (default %.3f)" % CLEARANCE)
    ap.add_argument("--fit", default="seat",
                    choices=("seat", "grow", "push"),
                    help="seat places the mesh and leaves it alone, which is "
                         "what a generated garment wants; grow and push deform "
                         "it to the body and are escape hatches -- see the "
                         "module docstring before using either")
    ap.add_argument("--taper", action="store_true",
                    help="scale girth per height band instead of once for the "
                         "whole piece.  Experimental: the band measurement "
                         "saturates on multi-shell solids -- see the comment "
                         "in seat() before trusting it")
    ap.add_argument("--pattern", default="*.glb")
    ap.add_argument("--report", default=None, help="write fit measurements here")
    args = ap.parse_args()

    sources: list[Path] = []
    for raw in args.input:
        path = Path(raw).expanduser()
        if path.is_dir():
            sources += sorted(p for p in path.glob(args.pattern) if p.is_file())
        elif path.is_file():
            sources.append(path)
        else:
            print("no such file or directory: %s" % path)
            return 2
    if not sources:
        print("nothing to fit")
        return 2

    race_path = Path(args.races_dir) / f"{args.race}.glb"
    if not race_path.exists():
        print("no such race rig: %s" % race_path)
        return 2
    rig = ea.load_rig(race_path, BODY_MESH)

    out = Path(args.output).expanduser()
    many = len(sources) > 1 or out.is_dir() or not out.suffix
    if many:
        out.mkdir(parents=True, exist_ok=True)

    rows, failed = [], 0
    for source in sources:
        target = (out / (source.stem + ".glb")) if many else out
        label = source.stem.replace("_", " ")[:48]
        try:
            info = build(source, target, rig, args.kind, label,
                         args.clearance, args.fit, args.taper)
        except Exception as exc:
            print("  FAILED %-44s %s" % (source.stem[:44], exc))
            failed += 1
            continue
        rows.append(info)
        print("  %-44s %-7s x%.3f  %d verts  %.2f MB"
              % (source.stem[:44], info.get("attach", "skinned"),
                 info["scale"], info["vertices"], info["bytes"] / 1e6))

    print("\n%d fitted, %d failed, authored against %s"
          % (len(rows), failed, args.race))
    if args.report and rows:
        Path(args.report).write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print("report: %s" % args.report)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

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
  repose  carry each limb of the garment from the pose the concept was drawn
          in -- arms dropped, feet a stance apart -- onto the rig's rest pose.
          Found with the ray caster from the limb's own bone axis, never from
          percentiles of the garment's point cloud; see ``repose``.  Without
          this a sleeved piece is wearable but wrong everywhere that moves:
          its sleeves inherit chest weights from wherever they hang, and in
          the running client they neither follow the arm nor stay on the
          chest.
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
import dataclasses
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
#: The split race bodies carry generated wardrobe extras (head band, cap)
#: that are runtime toggles, not anatomy -- measuring them would grow the
#: helm fit.  Everything that used to be the fused char1 mesh, by name.
BODY_MESH = ("char1", "body", "eyes", "hair", "wardrobe_shirt",
             "wardrobe_pants", "wardrobe_boots")

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

#: The (height, girth) factors the most recent seat() call applied, for the
#: torso's axis equalisation to read back.
LAST_SEAT_FACTORS = (1.0, 1.0)

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
#: ``lift`` is a fraction of head height added above the median-centred
#: placement, to seat headgear high like a hat rather than centred like a
#: bucket.  Helms ride up a third of the head so the brow line clears the
#: eyes; circlets and bands ride higher still to sit at the hairline.
SOCKET_SHRINK = 0.8

SOCKET_KIND = {
    "helm": {"part": 3, "bones": ["Head"], "clearance": .010, "lift": 0.12,
             "setback": 0.120},
    "hood": {"part": 3, "bones": ["Head"], "clearance": .014, "lift": 0.06,
             "setback": 0.120},
    "circlet": {"part": 3, "bones": ["Head"], "clearance": .008, "lift": 0.18,
                "setback": 0.110},
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
    global LAST_SEAT_FACTORS
    LAST_SEAT_FACTORS = (scale, girth)

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


#: Which limbs a generated piece may arrive posed around, and how far.  A
#: concept sheet draws its figure at ease -- arms dropped toward an A-pose,
#: feet a stance apart -- and the generator models the garment exactly as
#: drawn, so a sleeved cuirass arrives with its sleeves 50-60 degrees below the
#: rig's T-pose arms and legwear arrives splayed wider than the rig stands.
#: Seating cannot fix that: it is a rotation, not a size or a place.  Worn
#: as-is, the sleeves inherit whatever body surface happens to be nearest their
#: hanging position -- chest and lats -- and the moment the idle clip drops the
#: arms, the sleeve neither follows the arm nor stays on the chest.  That is
#: the "pauldrons hovering beside the upper arms" defect: the authored pose
#: showing through, not the runtime retarget.
#:
#: Per region: (pivot bone per side, how many degrees of drop/splay to search).
#: Arms only ever drop from the T and legs only ever splay outward, because
#: that is the whole space of at-ease figures; searching the other way just
#: gives noise somewhere to land.
REPOSE = {
    # 88, not the A-pose's 60: some sheets drop the arms nearly straight down,
    # and a sweep that stops short reads a 84-degree sleeve as no sleeve.
    "torso": (("upperarm_l", 88), ("upperarm_r", 88)),
    "legs": (("thigh_l", 25), ("thigh_r", 25)),
}

#: Bones a torso garment may weight beyond the region's own set.  The region
#: stops at the upper arms because a lofted piece never reaches further, but a
#: generated jacket ships full sleeves; once those lie along the arm they need
#: the forearm to bend with, or the cuff rides through the body at the first
#: elbow bend.
REPOSE_SKIN = {
    "torso": ["lowerarm_l", "lowerarm_r"],
}

#: What counts as the limb being inside the garment: the fraction of radial
#: rays, cast outward from the posed bone axis, that meet garment surface
#: within ``REPOSE_REACH`` metres.  A sleeve is a tube and surrounds its axis,
#: so an enclosed sample answers 0.75-1.0; a hip fauld hanging beside the axis
#: answers a third or less.
REPOSE_ENCLOSED = 0.55
REPOSE_REACH = 0.15


def _limb_axis_enclosure(origin: np.ndarray, axis: np.ndarray,
                         verts: np.ndarray, sectors: int = 8) -> float:
    """How surrounded one point of a limb axis is by garment surface."""
    seed = (np.array([0., 0., 1.]) if abs(axis[2]) < 0.9
            else np.array([1., 0., 0.]))
    u = np.cross(axis, seed)
    u /= max(np.linalg.norm(u), 1e-9)
    v = np.cross(axis, u)
    hits = 0
    for sector in range(sectors):
        angle = 2.0 * math.pi * (sector + 0.5) / sectors
        direction = math.cos(angle) * u + math.sin(angle) * v
        distance, _ = cast(origin, direction, verts)
        if distance <= REPOSE_REACH:
            hits += 1
    return hits / float(sectors)


def _frontal_turn(points: np.ndarray, pivot: np.ndarray,
                  angle: np.ndarray | float) -> np.ndarray:
    """Rotate points about the world-Z line through ``pivot``, per point."""
    turned = points.copy()
    cos = np.cos(angle)
    sin = np.sin(angle)
    x = points[:, 0] - pivot[0]
    y = points[:, 1] - pivot[1]
    turned[:, 0] = pivot[0] + cos * x - sin * y
    turned[:, 1] = pivot[1] + sin * x + cos * y
    return turned


def _limb_bones(rig: ea.Rig, root: str) -> set[str]:
    """The chain that rides a pivot: the bone and everything below it."""
    names = {root}
    grew = True
    while grew:
        grew = False
        for child, parent in rig.parent.items():
            if parent in names and child not in names:
                names.add(child)
                grew = True
    return names


def _weld(points: np.ndarray, triangles: np.ndarray
          ) -> tuple[np.ndarray, np.ndarray, int]:
    """Vertices welded by position, so the graph sees solids, not UV islands.

    A generated mesh splits vertices along every texture seam, which leaves
    each little patch its own island: an edge graph over the raw indices calls
    a single sleeve four hundred components.  Coincident positions are one
    point of the same solid, whatever the UVs did.
    """
    keys = np.round(points * 1e5).astype(np.int64)
    _, canon, inverse = np.unique(keys, axis=0, return_index=True,
                                  return_inverse=True)
    edges = np.sort(inverse[triangles[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2)],
                    axis=1)
    edges = np.unique(edges[edges[:, 0] != edges[:, 1]], axis=0)
    return inverse, edges, len(canon)


def _graph_smooth(values: np.ndarray, edges: np.ndarray,
                  rounds: int = 8) -> np.ndarray:
    """Average a per-vertex signal over the mesh graph."""
    degree = np.zeros(len(values))
    np.add.at(degree, edges[:, 0], 1.0)
    np.add.at(degree, edges[:, 1], 1.0)
    degree = np.maximum(degree, 1.0)
    smoothed = values.astype(np.float64).copy()
    for _ in range(rounds):
        pooled = np.zeros(len(values))
        np.add.at(pooled, edges[:, 0], smoothed[edges[:, 1]])
        np.add.at(pooled, edges[:, 1], smoothed[edges[:, 0]])
        smoothed = 0.5 * smoothed + 0.5 * pooled / degree
    return smoothed


def _components(edges: np.ndarray, count: int) -> np.ndarray:
    """Connected-component label per vertex, by union-find."""
    parent = np.arange(count)

    def find(index: int) -> int:
        root = index
        while parent[root] != root:
            root = parent[root]
        while parent[index] != root:
            parent[index], index = root, parent[index]
        return root

    for a, b in edges:
        ra, rb = find(int(a)), find(int(b))
        if ra != rb:
            parent[ra] = rb
    return np.array([find(int(index)) for index in range(count)])


def _wraps_axis(points: np.ndarray, origin: np.ndarray, axis: np.ndarray,
                reach: float, radius_cap: float = 0.13,
                sectors: int = 12) -> bool:
    """Whether a component encircles a limb axis, the way a sleeve ring does.

    A ring worn on the limb has surface most of the way around the axis and
    close to it.  A belt the axis merely passes near, or a flank plate beside
    it, fails one of the two: the belt's surface rings the torso and sits too
    far from the arm, the plate covers half a turn at most.
    """
    relative = points - origin
    travel = relative @ axis
    across = relative - np.outer(travel, axis)
    radius = np.linalg.norm(across, axis=1)
    near = (travel >= -0.05) & (travel <= reach)
    if int(near.sum()) < 12:
        return False
    if float(np.median(radius[near])) > radius_cap:
        return False
    seed = (np.array([0., 0., 1.]) if abs(axis[2]) < 0.9
            else np.array([1., 0., 0.]))
    u = np.cross(axis, seed)
    u /= max(np.linalg.norm(u), 1e-9)
    v = np.cross(axis, u)
    angles = np.arctan2(across[near] @ v, across[near] @ u)
    bins = np.unique(((angles + math.pi) / (2 * math.pi) * sectors)
                     .astype(int).clip(0, sectors - 1))
    return len(bins) >= sectors // 2


def repose(points: np.ndarray, normals: np.ndarray, rig: ea.Rig, region: str,
           triangles: np.ndarray) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """Carry each limb of the garment from its authored pose onto the rig's.

    Nothing here trusts a percentile of the garment's own point cloud -- that
    is how every earlier fit went wrong, because decorative geometry pollutes
    any such measure.  The pose is found with the ray caster instead, from the
    limb's real bone axis: drop the axis through the candidate poses and keep
    the ones the garment's surface actually surrounds.  A sleeve is a tube, so
    the arm axis that threads it is enclosed by it; a hip fauld beside the
    sleeve never surrounds the axis at any pose, and a skirt surrounds the leg
    at *every* pose, which is why a pose only counts when it beats the rig's
    own rest pose -- a piece that already encloses the rest axis is already
    wearable and is left exactly as it arrived.

    Sorting the garment into limb and trunk is then not geometric guesswork
    either: the body itself is posed into the found stance, each garment
    vertex inherits the weights of the body surface nearest it -- the same
    rule the final skinning uses, in the one configuration where sleeve wraps
    arm and fauld hugs hip unambiguously -- and the limb share of that blend
    is how far each vertex turns back onto the rig.  The turn is confined to
    the frontal plane, which is where a sheet-drawn figure's pose lives.
    """
    reports: list[dict] = []
    out = points.copy()
    turned = normals.copy()
    for pivot_bone, most_degrees in REPOSE.get(region, ()):
        start = rig.origin(pivot_bone)
        seg_start, seg_end = rig.segment(pivot_bone)
        rig_dir = seg_end - seg_start
        rig_dir /= max(np.linalg.norm(rig_dir), 1e-9)
        side = 1.0 if start[0] >= 0 else -1.0
        drop_sign = -side if region == "torso" else side
        report = {"limb": pivot_bone, "applied": False}
        reports.append(report)
        verts = out[triangles]
        # Sample points sit along the garment-covered run of the limb: past
        # the elbow for a sleeve, down the shin for a trouser leg.  The near
        # and far halves are scored apart, and the far half only ever helps:
        # a cap sleeve encloses nothing past the elbow at any pose, and
        # averaging that silence in would veto a pose the near half found.
        near_spans, far_spans = ((np.linspace(0.14, 0.28, 3),
                                  np.linspace(0.36, 0.50, 3))
                                 if region == "torso"
                                 else (np.linspace(0.15, 0.38, 3),
                                       np.linspace(0.46, 0.65, 3)))
        samples: list[tuple[int, float, float]] = []
        for degrees in range(0, most_degrees + 1, 4):
            angle = math.radians(degrees) * drop_sign
            cos, sin = math.cos(angle), math.sin(angle)
            axis = np.array([cos * rig_dir[0] - sin * rig_dir[1],
                             sin * rig_dir[0] + cos * rig_dir[1],
                             rig_dir[2]])
            near, far = (float(np.mean([
                _limb_axis_enclosure(start + reach * axis, axis, verts)
                for reach in spans])) for spans in (near_spans, far_spans))
            samples.append((degrees, near, far))
        long_limb = max(far for _, _, far in samples) >= 0.5
        curve = [(degrees, (near + far) / 2.0 if long_limb else near)
                 for degrees, near, far in samples]
        best = max(value for _, value in curve)
        at_rest = curve[0][1]
        report["enclosure"] = {"rest": round(at_rest, 2),
                               "best": round(best, 2)}
        if best < REPOSE_ENCLOSED:
            report["reason"] = "nothing surrounds this limb at any pose"
            continue
        if at_rest >= best - 0.08:
            report["reason"] = "already encloses the rest axis"
            continue
        # The band's onset, not its middle: past the true angle the axis dives
        # out of the sleeve into the flank, where hem and fauld geometry keeps
        # the score saturated, so the top edge of the band is noise while its
        # first near-max angle is the sleeve itself.
        plateau = [degrees for degrees, value in curve if value >= best - 0.02]
        chosen = math.radians(float(plateau[0])) * drop_sign
        report["poseDeg"] = round(math.degrees(chosen), 1)

        limb = _limb_bones(rig, pivot_bone)
        limb_slots = np.isin(
            rig.joints, [rig.joint_names.index(name) for name in limb
                         if name in rig.joint_names])
        share = (rig.weights * limb_slots).sum(axis=1, keepdims=True)
        posed_body = (share * _frontal_turn(rig.positions, start, chosen)
                      + (1.0 - share) * rig.positions)
        posed_rig = dataclasses.replace(rig, positions=posed_body)
        candidates = (list(ea.GARMENT_SKIN[region])
                      + REPOSE_SKIN.get(region, []))
        inherited = posed_rig._weights_from_body(out, candidates)
        if inherited is None:
            report["reason"] = "posed body offered no weights to inherit"
            continue
        joints, weights = inherited
        member = np.isin(joints, [rig.joint_names.index(name) for name in limb
                                  if name in rig.joint_names])
        blend = (weights * member).sum(axis=1)
        # A generated piece is a stack of disjoint closed solids, and a solid
        # turns whole or not at all: blending the turn per vertex smears a
        # rigid sleeve, because its inner wall lies nearer the flank than the
        # arm and inherits a different answer than its outer wall.  Each
        # component votes with its mean inherited share; only a component that
        # genuinely spans limb and trunk -- a one-piece trouser, say -- falls
        # back to the smoothed per-vertex blend, where the shear belongs.
        canon, edges, welded = _weld(out, triangles)
        pooled = np.zeros(welded)
        counts = np.zeros(welded)
        np.add.at(pooled, canon, blend)
        np.add.at(counts, canon, 1.0)
        pooled /= np.maximum(counts, 1.0)
        pooled = _graph_smooth(pooled, edges)
        labels = _components(edges, welded)
        chosen_cos = math.cos(chosen)
        chosen_sin = math.sin(chosen)
        posed_axis = np.array([
            chosen_cos * rig_dir[0] - chosen_sin * rig_dir[1],
            chosen_sin * rig_dir[0] + chosen_cos * rig_dir[1], rig_dir[2]])
        reach = 0.55 if region == "torso" else 0.75
        turn = np.zeros(welded)
        for label in np.unique(labels):
            inside = labels == label
            vote = float(pooled[inside].mean())
            if vote >= 0.7:
                turn[inside] = 1.0
            else:
                # The inherited weights under-report a sleeve ring whose
                # inner wall hugs the flank -- it can vote nearly all trunk
                # and still be worn on the arm.  Geometry settles it: a piece
                # worn *on* the limb encircles the posed axis, and a piece
                # that merely hangs beside it -- a belt the axis threads, a
                # fauld, half a chest plate -- does not.
                indexed = np.zeros(welded, dtype=bool)
                indexed[inside] = True
                verts_of = indexed[canon]
                if _wraps_axis(out[verts_of], start, posed_axis, reach):
                    turn[inside] = 1.0
        # What sits on top of the joint stays there.  A pauldron is drawn
        # draped over the shoulder crest, and it covers the crest wherever
        # the arm points; rotating it with the sleeve swings it down the
        # arm and bares the trapezius.  A component whose body lies above
        # the pivot is such a cap, and keeps its authored drape.
        caps = np.zeros(welded, dtype=bool)
        for label in np.unique(labels):
            indexed = np.zeros(welded, dtype=bool)
            indexed[labels == label] = True
            verts_of = indexed[canon]
            if not verts_of.any() or float(turn[canon][verts_of].mean()) < 0.99:
                continue
            centroid = out[verts_of].mean(axis=0)
            above = float(centroid[1] - start[1])
            outboard = abs(float(centroid[0])) - abs(float(start[0]))
            if above > 0.01 and outboard < 0.10:
                turn[indexed] = 0.0
                caps[indexed] = True
        turn = turn[canon]
        out = _frontal_turn(out, start, -chosen * turn)
        turned = _frontal_turn(turned, np.zeros(3), -chosen * turn)
        report["applied"] = True
        report["limbVertices"] = int((turn > 0.5).sum())
        report["components"] = int(len(np.unique(labels)))
        # The masks ride along so the finishing passes in build() -- seated
        # and stretched geometry -- can still tell sleeve from cap from
        # trunk without re-deriving the segmentation.
        report["sleeve"] = turn > 0.5
        report["cap"] = caps[canon]
        report["pivot"] = pivot_bone
    return out, turned, reports


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
                      colour=(190, 185, 178), double_sided: bool = False) -> int:
    """Base colour straight off the generated map, when there is one."""
    pbr = {"baseColorFactor": ea.srgb_to_linear(colour) + [1.],
           "metallicFactor": 0.0, "roughnessFactor": 0.72}
    if png is not None:
        pbr["baseColorFactor"] = [1., 1., 1., 1.]
        pbr["baseColorTexture"] = {"index": glb.texture(png)}
    glb.doc["materials"].append(
        {"name": name, "pbrMetallicRoughness": pbr,
         "doubleSided": double_sided})
    return len(glb.doc["materials"]) - 1


#: The liner's reach over the body, as world heights and a half-width: the
#: hip line up to the base of the neck, and inboard of the mid-forearm.  The
#: painted shirt lives entirely inside this band on every race body, so the
#: liner needs no opinion about which texels are shirt -- every earlier
#: attempt to classify the shirt by colour left a sliver of it bare at some
#: boundary the classifier misread: the blacked-out armpit, the shaded seam
#: rows of the collar, the last teal row under the hem.
LINER_BAND = (0.90, 1.70)
#: 0.85, not the mid-forearm: the painted body keeps a few teal texels on
#: the back of the right hand, and an idle pose hangs that hand exactly where
#: the armpit slit looks.  Lining the arm to the fingertips reads as gloves
#: and closes the last of it.
LINER_HALF_WIDTH = 0.66
LINER_LIFT = 0.008
LINER_COLOUR = (56, 47, 40)

_LINER_CACHE: dict[str, tuple | None] = {}


def shirt_liner(race_path: Path):
    """The clothed band of the body, lifted a few millimetres, to wear under
    a torso piece.

    The meshy race bodies paint their wardrobe into the body texture, so
    there is no shirt mesh for the runtime to hide when armour goes on --
    and a generated cuirass is an open design of straps and plates, so the
    teal shirt shows through every gap in it.  No amount of fitting closes
    that: the gaps are the design.  What a real wardrobe does is layer, so
    each torso piece ships an underlayer: the body's own triangles from hip
    to neck, offset out along their welded normals and carrying the body's
    own skin weights.  It deforms exactly as the body does, in every pose,
    on every rig the runtime refits to -- so whatever the armour leaves open
    shows underpadding, never the shirt.

    Returns (positions, normals, uvs, indices, joints, weights) in body
    space, or None when the body offers nothing to line.
    """
    key = str(race_path)
    if key in _LINER_CACHE:
        return _LINER_CACHE[key]
    document, binary = ea.read_glb(race_path)
    node = next((n for n in document.get("nodes", [])
                 if "mesh" in n and "skin" in n), None)
    if node is None:
        _LINER_CACHE[key] = None
        return None
    primitive = document["meshes"][node["mesh"]]["primitives"][0]
    attributes = primitive["attributes"]
    positions = ea.accessor_array(document, binary, attributes["POSITION"]).astype(np.float64)
    normals = ea.accessor_array(document, binary, attributes["NORMAL"]).astype(np.float64)
    uvs = ea.accessor_array(document, binary, attributes["TEXCOORD_0"]).astype(np.float64)
    joints = ea.accessor_array(document, binary, attributes["JOINTS_0"]).astype(np.int64)
    weights = ea.accessor_array(document, binary, attributes["WEIGHTS_0"]).astype(np.float64)
    # A split body spreads its faces over several surface primitives that
    # all share this attribute set; the liner needs the whole hide-to-neck
    # surface, so the triangles are the union of every primitive built on
    # the same positions accessor.
    triangle_sets = []
    for other in document.get("nodes", []):
        if "mesh" not in other or "skin" not in other:
            continue
        for prim_other in document["meshes"][other["mesh"]]["primitives"]:
            if (prim_other["attributes"].get("POSITION")
                    == attributes["POSITION"] and "indices" in prim_other):
                triangle_sets.append(ea.accessor_array(
                    document, binary,
                    prim_other["indices"]).astype(np.int64).reshape(-1, 3))
    triangles = np.vstack(triangle_sets)

    # The face stays bare -- the eyes are teal too, and lining them would
    # trade a shirt sliver for a masked face -- but the band runs high enough
    # to swallow the back of the collar, whose last texels ride the
    # trapezius at 1.56.
    shirt = ((positions[:, 1] > LINER_BAND[0])
             & (positions[:, 1] < LINER_BAND[1])
             & (np.abs(positions[:, 0]) < LINER_HALF_WIDTH)
             & ~((positions[:, 1] > 1.585) & (positions[:, 2] > 0.0)))
    if int(shirt.sum()) < 40:
        _LINER_CACHE[key] = None
        return None
    canon, edges, welded = _weld(positions, triangles)
    chosen = np.zeros(welded, dtype=bool)
    np.logical_or.at(chosen, canon, shirt)
    picked = chosen[canon]
    keep = picked[triangles].any(axis=1)
    used = np.unique(triangles[keep])
    remap = np.full(len(positions), -1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    base_faces = remap[triangles[keep]].reshape(-1, 3)
    base_positions = positions[used]
    base_normals = normals[used]
    base_uvs = uvs[used]
    base_joints = joints[used].astype(np.int64)
    base_weights = weights[used]
    # Subdivision was tried here -- the sagitta argument says a flat liner
    # facet can dip inside the arm's curve between vertices -- and measured
    # worse than it reasoned: splitting edges means inventing blends for the
    # midpoints, and a midpoint whose merged weights differ a hair from the
    # skin's own interpolation drifts under pose everywhere, trading two
    # stubborn pixels for fifty.  The band ships with the body's own
    # vertices, nothing more.
    positions_band = base_positions
    normals_band = base_normals
    uvs_band = base_uvs
    joints_band = base_joints
    weights_band = base_weights
    faces_band = base_faces
    # Lift along the welded normal, one direction per position: the band
    # splits its vertices along texture seams, and lifting each copy along
    # its own normal tears the liner open a millimetre at every seam.
    band_canon, band_edges, band_welded = _weld(positions_band, faces_band)
    pooled = np.zeros((band_welded, 3))
    np.add.at(pooled, band_canon, normals_band)
    pooled /= np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-9)
    lift = pooled[band_canon]
    liner_positions = positions_band + lift * LINER_LIFT
    liner_normals = normals_band.copy()
    liner_uvs = uvs_band.copy()
    liner_faces = faces_band.copy()
    liner_joints = joints_band.copy()
    liner_weights = weights_band.copy()
    # Close the rim.  A lifted shell is a tunnel over the body, and a grazing
    # ray can enter its open mouth -- at a hem, a collar, an armhole -- and
    # find the shirt on the tunnel floor.  Every boundary edge gets a skirt
    # quad tucked back under the skin, so the shell has no mouth at all.
    edge_pairs = np.sort(band_canon[faces_band[:, [0, 1, 1, 2, 2, 0]]
                                    .reshape(-1, 2)], axis=1)
    keys, counts = np.unique(edge_pairs, axis=0, return_counts=True)
    open_edges = keys[counts == 1]
    representative = np.full(band_welded, -1, dtype=np.int64)
    order = np.arange(len(positions_band))
    representative[band_canon[order[::-1]]] = order[::-1]
    rim_faces: list[list[int]] = []
    rim_of: dict[int, int] = {}
    extra_positions: list[np.ndarray] = []
    for edge in open_edges:
        corners: list[int] = []
        for canon_id in edge:
            original = int(representative[canon_id])
            if original < 0:
                break
            if canon_id not in rim_of:
                rim_of[int(canon_id)] = (len(liner_positions)
                                         + len(extra_positions))
                extra_positions.append(
                    positions_band[original] - lift[original] * 0.004)
            corners.append(original)
        if len(corners) < 2:
            continue
        top_a, top_b = corners
        low_a, low_b = (rim_of[int(canon_id)] for canon_id in edge)
        rim_faces.append([top_a, top_b, low_b])
        rim_faces.append([top_a, low_b, low_a])
    if rim_faces:
        drop = np.array([representative[int(canon_id)] for canon_id in rim_of],
                        dtype=np.int64)
        liner_positions = np.vstack([liner_positions,
                                     np.array(extra_positions)])
        liner_normals = np.vstack([liner_normals, normals_band[drop]])
        liner_uvs = np.vstack([liner_uvs, uvs_band[drop]])
        liner_joints = np.vstack([liner_joints, joints_band[drop]])
        liner_weights = np.vstack([liner_weights, weights_band[drop]])
        liner_faces = np.vstack([liner_faces, np.array(rim_faces)])
    # Under the padded shell, a coat of paint: a second copy of the band a
    # bare two millimetres off the skin.  It is alpha-blended, so it draws
    # after the opaque body and needs only to sit in front of it to win --
    # but *dead* on the skin it shares the body's exact depth, and at a
    # crease the depth-test tie is a per-pixel, per-frame coin flip that
    # flickers a needle of shirt through.  Two millimetres clears the tie
    # while staying far under the 8 mm shell, so a crease that folds the
    # shell into the arm still meets paint before skin.
    paint = (positions_band + lift * 0.002, normals_band.copy(),
             uvs_band.copy(), faces_band.reshape(-1).copy(),
             joints_band.copy(), weights_band.copy())
    # Plug the crease pockets.  Linear blend skinning folds a lifted shell
    # into the body wherever a joint closes -- the armpit once the idle
    # drops the arm, the inner elbow once it bends -- and through the
    # resulting slit a needle of shirt stays visible from exactly one
    # angle.  No lift fixes a folding offset, so a small charcoal ellipsoid
    # rides each pocket: weighted half to each side of the joint, it stays
    # centred in the crease in every pose, and anything peering in meets it.
    skin_joints = document["skins"][0]["joints"]
    joint_names = [document["nodes"][j].get("name", "") for j in skin_joints]
    matrices = ea.global_matrices(document)

    def joint_at(name):
        return (joint_names.index(name), matrices[
            skin_joints[joint_names.index(name)]][:3, 3])

    pockets = []
    for side in ("l", "r"):
        if ("upperarm_" + side not in joint_names
                or "lowerarm_" + side not in joint_names
                or "spine_02" not in joint_names):
            continue
        arm, shoulder = joint_at("upperarm_" + side)
        forearm, elbow = joint_at("lowerarm_" + side)
        spine, _ = joint_at("spine_02")
        # A third crease guards the neck-shoulder junction: once the idle
        # draws the clavicles forward, the liner folds along the top of the
        # trapezius and a patch of shirt shows through from high frontal
        # angles.
        if ("clavicle_" + side in joint_names
                and "spine_03" in joint_names):
            clav, _ = joint_at("clavicle_" + side)
            chest, _ = joint_at("spine_03")
            inboard_trap = -1.0 if shoulder[0] > 0 else 1.0
            # Placed by measurement, not eye: the failing pixels unproject to
            # rest (+/-0.081, 1.566, -0.111), the rear lip of the junction.
            pockets.append((shoulder + np.array([inboard_trap * 0.127,
                                                 0.105, -0.01]),
                            np.array([0.05, 0.045, 0.055]), clav, chest))
        inboard = -0.02 if shoulder[0] > 0 else 0.02
        # Tucked deeper than it once was: with the idle's arms hanging wider
        # and the shoulders drawn forward, the rear armpit opens up and a
        # generous ball shows behind the cap as a smooth grey bump.
        pockets.append((shoulder + np.array([inboard * 3.0, -0.065, 0.005]),
                        np.array([0.042, 0.055, 0.044]), arm, spine))
        # Behind the joint, not on it: the surface a slit ray actually
        # lands on is the triceps side of the elbow (measured by
        # intersecting the failing pixel's ray with the posed body).
        pockets.append((elbow + np.array([inboard * 0.5, -0.005, -0.028]),
                        np.array([0.04, 0.045, 0.034]), arm, forearm))
    for centre_at, radii, bone_a, bone_b in pockets:
        rings, sectors = 5, 8
        plug_positions = []
        plug_normals = []
        for ring in range(rings + 1):
            polar = math.pi * ring / rings
            for sector in range(sectors):
                azimuth = 2 * math.pi * sector / sectors
                direction = np.array([
                    math.sin(polar) * math.cos(azimuth),
                    math.cos(polar),
                    math.sin(polar) * math.sin(azimuth)])
                plug_positions.append(centre_at + direction * radii)
                plug_normals.append(direction)
        plug_faces = []
        for ring in range(rings):
            for sector in range(sectors):
                a = ring * sectors + sector
                b = ring * sectors + (sector + 1) % sectors
                c = (ring + 1) * sectors + sector
                d = (ring + 1) * sectors + (sector + 1) % sectors
                plug_faces += [[a, b, c], [b, d, c]]
        base_index = len(liner_positions)
        count = len(plug_positions)
        liner_positions = np.vstack([liner_positions, np.array(plug_positions)])
        liner_normals = np.vstack([liner_normals, np.array(plug_normals)])
        liner_uvs = np.vstack([liner_uvs, np.zeros((count, 2))])
        plug_joint_row = np.zeros((count, liner_joints.shape[1]), dtype=liner_joints.dtype)
        plug_weight_row = np.zeros((count, liner_weights.shape[1]))
        plug_joint_row[:, 0] = bone_a
        plug_joint_row[:, 1] = bone_b
        plug_weight_row[:, 0] = 0.5
        plug_weight_row[:, 1] = 0.5
        liner_joints = np.vstack([liner_joints, plug_joint_row])
        liner_weights = np.vstack([liner_weights, plug_weight_row])
        liner_faces = np.vstack([liner_faces,
                                 np.array(plug_faces) + base_index])
    liner = ((liner_positions, liner_normals, liner_uvs,
              liner_faces.reshape(-1), liner_joints, liner_weights), paint)
    _LINER_CACHE[key] = liner
    return liner


def socket_origin(rig: ea.Rig, part: int) -> np.ndarray:
    """Where the runtime will hang this part, in world space."""
    socket = ea.build_sockets(rig).get(part)
    origin = rig.origin(socket.bone if socket else "Head")
    offset = np.asarray(getattr(socket, "offset", (0., 0., 0.)),
                        dtype=np.float64)
    return origin + offset


def _align_arm_sleeves(points: np.ndarray, triangles: np.ndarray,
                       rig: ea.Rig, steps: list[dict]) -> int:
    """Rigidly turn each arm-sleeve group onto its own bone line.

    The repose corrects the shoulder angle the concept drew, but a sheet
    that poses its knight akimbo bends the FOREARM of the sleeve too --
    and a bracer bound rigidly to a straight forearm bone then juts
    across the chest at the concept's elbow angle.  Per side, the sleeve
    components are grouped by their nearest bone segment, and each group
    takes the one rotation about its pivot (shoulder for the upper group,
    elbow for the forearm group) that carries its centroid direction onto
    the bone; ring centring afterwards handles the residual translation.
    Small angles are left alone so already-straight sheets pass through
    byte-stable.  Returns how many groups turned.
    """
    inverse, edges, count = _weld(points, triangles)
    labels = _components(edges, count)[inverse]
    turned = 0
    for step in steps:
        if not step.get("applied") or "sleeve" not in step:
            continue
        side = step["limb"].rsplit("_", 1)[-1]
        try:
            shoulder = rig.origin("upperarm_" + side)
            elbow = rig.origin("lowerarm_" + side)
            wrist = rig.origin("hand_" + side)
        except (KeyError, ValueError):
            continue
        sleeve = np.asarray(step["sleeve"], dtype=bool)
        groups = {"upper": [], "fore": []}
        for label in np.unique(labels[sleeve]):
            members = labels == label
            if int((members & sleeve).sum()) * 2 < int(members.sum()):
                continue
            centre = np.median(points[members], axis=0)
            gap_upper = _segment_gap(centre, shoulder, elbow)
            gap_fore = _segment_gap(centre, elbow, wrist)
            groups["upper" if gap_upper <= gap_fore else "fore"].append(members)
        for name, pivot, tip in (("upper", shoulder, elbow),
                                 ("fore", elbow, wrist)):
            if not groups[name]:
                continue
            members = np.zeros(len(points), dtype=bool)
            for m in groups[name]:
                members |= m
            centroid = points[members].mean(axis=0)
            d0 = centroid - pivot
            d1 = tip - pivot
            n0, n1 = np.linalg.norm(d0), np.linalg.norm(d1)
            if n0 < 1e-6 or n1 < 1e-6:
                continue
            d0, d1 = d0 / n0, d1 / n1
            axis = np.cross(d0, d1)
            norm = float(np.linalg.norm(axis))
            angle = float(np.degrees(np.arccos(np.clip(np.dot(d0, d1),
                                                       -1.0, 1.0))))
            if norm < 1e-6 or angle < 4.0:
                continue
            axis /= norm
            c, s = np.cos(np.radians(angle)), np.sin(np.radians(angle))
            K = np.array([[0, -axis[2], axis[1]],
                          [axis[2], 0, -axis[0]],
                          [-axis[1], axis[0], 0]])
            R = np.eye(3) + s * K + (1 - c) * (K @ K)
            points[members] = (points[members] - pivot) @ R.T + pivot
            turned += 1
    return turned


def _segment_gap(point: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    span = b - a
    t = float(np.clip(np.dot(point - a, span)
                      / max(np.dot(span, span), 1e-12), 0.0, 1.0))
    return float(np.linalg.norm(point - (a + t * span)))


def _centre_sleeves(points: np.ndarray, triangles: np.ndarray, rig: ea.Rig,
                    steps: list[dict]) -> int:
    """Rigidly re-centre each wrapping sleeve ring on its own limb axis.

    The repose turns a sleeve down about the shoulder by the angle the sweep
    detected, and every residual error in that angle -- or forward lean the
    concept drew that a frontal turn cannot see -- lands as a translation
    that grows with distance from the pivot.  A bracer half a metre out rides
    visibly off the forearm while still swinging with it.  The fix is the
    measurement the sweep already trusts: a component that encircles the limb
    axis is worn on it, so slide it (perpendicular to the axis only -- the
    wrist clamp owns the length) until its ring centre sits on the bone.
    The median centre shrugs off a decorative fin; plates that do not wrap
    stay where the design drew them.  Returns how many rings moved.
    """
    inverse, edges, count = _weld(points, triangles)
    labels = _components(edges, count)[inverse]
    moved = 0
    for step in steps:
        if not step.get("applied") or "sleeve" not in step:
            continue
        side = step["limb"].rsplit("_", 1)[-1]
        segments = []
        for top, bottom in (("upperarm", "lowerarm"), ("lowerarm", "hand")):
            try:
                a = rig.origin("%s_%s" % (top, side))
                b = rig.origin("%s_%s" % (bottom, side))
            except (KeyError, ValueError):
                continue
            segments.append((a, b))
        if not segments:
            continue
        sleeve = np.asarray(step["sleeve"], dtype=bool)
        for label in np.unique(labels[sleeve]):
            members = labels == label
            if int((members & sleeve).sum()) * 2 < int(members.sum()):
                continue
            centre = np.median(points[members], axis=0)
            nearest = None
            for a, b in segments:
                span = b - a
                t = float(np.clip(np.dot(centre - a, span)
                                  / max(np.dot(span, span), 1e-12), 0.0, 1.0))
                on = a + t * span
                gap = float(np.linalg.norm(centre - on))
                if nearest is None or gap < nearest[0]:
                    nearest = (gap, on, a, span)
            gap, on, a, span = nearest
            axis = span / max(np.linalg.norm(span), 1e-9)
            # Ring-ness is judged about the component's OWN centre, not the
            # limb line: the very displacement being corrected can put the
            # limb axis outside the ring, where the sector test sees a gap
            # and vetoes exactly the components that need the fix.
            travel = (points[members] - centre) @ axis
            half = float(np.percentile(np.abs(travel), 95.0))
            if not _wraps_axis(points[members] - (centre - axis * half),
                               np.zeros(3), axis, 2.0 * half + 0.05):
                continue
            delta = on - centre
            delta -= axis * float(np.dot(delta, axis))
            if float(np.linalg.norm(delta)) < 0.004:
                continue
            points[members] += delta
            moved += 1
    return moved


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
    # Author at RUNTIME size: a race may carry a rest scale on the head
    # joint (adjust_race_proportions.py), which the engine applies to the
    # skinned head but not to socketed pieces -- so the piece itself must
    # be built for the scaled head.  The raw mesh verts are unscaled in
    # the file; grow them about the joint by the joint's own rest scale.
    anchor = rig.origin(spec["bones"][0])
    joint_scale = np.linalg.norm(rig.basis(spec["bones"][0]), axis=0)
    head = anchor + (head - anchor) * joint_scale
    span = head.max(axis=0) - head.min(axis=0)
    # Size to the head's widest horizontal axis, from a robust span: a helm
    # is a shell around a skull, and matching height instead lets a tall crest
    # pull the whole piece down inside the face.  The span uses the 4th-96th
    # percentile so a single spike does not inflate the scale.
    lo = np.percentile(points, 4, axis=0)
    hi = np.percentile(points, 96, axis=0)
    extent = np.maximum(hi - lo, 1e-9)
    scale = max((span[axis] + 2 * spec["clearance"]) / float(extent[axis])
                for axis in (0, 2))
    # Reviewed in game: pieces sized strictly to the skull read a fifth
    # too big -- their flares and trim inflate the visual bulk past the
    # measured span -- so every socket piece takes a flat trim.
    scale *= SOCKET_SHRINK
    seated = (points - (points.max(axis=0) + points.min(axis=0)) / 2.) * scale
    # Centre on the head's own centre by the MEDIAN of the piece, not its
    # bounding box: circlets and helms carry danglers and spikes that skew a
    # bbox centre and drag the band down over the eyes.  The head sits inside
    # the shell, riding high, and a per-kind lift seats it like a hat on the
    # crown rather than a bucket over the face.
    head_mid = 0.5 * (float(head[:, 1].min()) + float(head[:, 1].max()))
    # Centre depth on the cranium alone: the full head region includes the
    # nose and jaw, whose verts drag a median forward and wear the piece out
    # over the brow.  A skull is round above its midline, so the upper half
    # is the shell the piece actually wraps.
    crown = head[head[:, 1] >= head_mid]
    # And a per-kind setback on top of the cranium median: even centred on
    # the skull the shells kept reading worn out over the brow in game, so
    # each kind slides back a touch further.
    centre = np.array([float(np.median(head[:, 0])), 0.0,
                       float(np.median(crown[:, 2]))
                       - float(spec.get("setback", 0.0))])
    lift = float(spec.get("lift", 0.0)) * (head[:, 1].max() - head[:, 1].min())
    centre[1] = head_mid - float(np.median(seated[:, 1])) + lift
    return seated + (centre - socket_origin(rig, spec["part"]))


def build_socket(source: Path, out: Path, rig: ea.Rig, kind: str,
                 label: str) -> dict:
    """Size and place one socket piece, and write it unskinned."""
    surface, png = read_source(source)
    before = surface.positions.copy()
    surface.positions = seat_socket(surface.positions, rig, kind)
    # Socket pieces carry concept-sheet debris too, and the runtime-size
    # scale swings a buried splinter clear of the shell.
    _drop_orphan_shards(surface)

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


def _slim_to_body(points: np.ndarray, rig: ea.Rig, region: str,
                  movable: np.ndarray, target_clear: float,
                  body_points: np.ndarray | None = None,
                  centre: np.ndarray | None = None,
                  grow: bool = False) -> np.ndarray:
    """Draw a garment's trunk in toward the body until it hugs.

    A pull, never a push, and per axis: the torso is an ellipse -- wide across
    the shoulders, shallow front to back -- so a single radial factor cut to
    the wide sides drives the shallow front and back panels straight through
    the body and leaves the chest bare padding.  Each height band therefore
    gets its own x factor and z factor, each landing that side of the shell at
    the body's own half-extent plus ``target_clear`` on that axis, clamped to
    [floor, 1] so the shell only comes in, never past the body, and a real
    relief is thinned rather than erased.  Measured against the body's closed
    surface, never the garment's multi-shell point cloud.
    A limb region -- two tubes -- is slimmed a tube at a time: the caller
    passes the movable subset for one leg and the body points and centre of
    that same leg, so each trouser leg hugs its own thigh rather than a
    midline between them.
    """
    if body_points is None:
        body_points = region_points(rig, region)
    if centre is None:
        centre = np.array([float(np.median(body_points[:, 0])),
                           float(np.median(body_points[:, 2]))])
    body = body_points
    low, high = float(body[:, 1].min()), float(body[:, 1].max())
    rows = 12
    # Growing is the same banded, per-axis move in the other direction --
    # and the only body-clearing move a closed generated solid can take:
    # scaling a whole band keeps inner and outer surfaces together, where a
    # per-vertex push (clear_body) turns the inside of the shell out.
    lo_clip, hi_clip = (1.0, 1.35) if grow else (0.55, 1.0)
    floor = lo_clip
    factors = np.ones((rows, 2))
    for row in range(rows):
        lo = low + (high - low) * row / rows
        hi = low + (high - low) * (row + 1) / rows
        skin = body[(body[:, 1] >= lo) & (body[:, 1] < hi)]
        mid = (points[:, 1] >= lo) & (points[:, 1] < hi) & movable
        if len(skin) < 6 or int(mid.sum()) < 6:
            factors[row] = np.nan
            continue
        shell = points[mid]
        for index, axis in enumerate((0, 2)):
            skin_h = float(np.percentile(np.abs(skin[:, axis] - centre[index]),
                                         92.0))
            shell_h = float(np.percentile(np.abs(shell[:, axis] - centre[index]),
                                          92.0))
            factors[row, index] = (float(np.clip(
                (skin_h + target_clear) / shell_h, lo_clip, hi_clip))
                if shell_h > 1e-4 else np.nan)
    centres = low + (high - low) * (np.arange(rows) + 0.5) / rows
    out = points.copy()
    for index in range(2):
        column = factors[:, index]
        good = ~np.isnan(column)
        if not good.any():
            continue
        column = np.interp(centres, centres[good], column[good])
        for _ in range(2):
            column = np.convolve(np.pad(column, 1, mode="edge"),
                                 [1 / 3.0, 1 / 3.0, 1 / 3.0], mode="valid")
        axis = (0, 2)[index]
        scale = np.interp(out[movable, 1], centres, column)
        out[movable, axis] = ((out[movable, axis] - centre[index]) * scale
                              + centre[index])
    return out


def _flatten_bust(points: np.ndarray, rig: ea.Rig, region: str,
                  movable: np.ndarray) -> int:
    """Press the chest panel flat against the wearer.

    Several concept sheets draw their breastplates with a bust, and the
    banded slim can only SCALE a band -- a localised dome keeps its shape
    at any scale, so the male chest ends up wearing one.  Within the
    chest band, any front vertex standing prouder than the body's own
    front line plus clearance and a little plate relief is pulled
    straight back in z.  A clamp, not a scale: flat panels and trim stay
    exactly where the fit put them.
    """
    body = region_points(rig, region)
    clamped = 0
    for lo, hi in ((1.20, 1.28), (1.28, 1.36), (1.36, 1.44), (1.44, 1.50)):
        skin = body[(body[:, 1] >= lo) & (body[:, 1] < hi)]
        if len(skin) < 6:
            continue
        allowed = float(np.percentile(skin[:, 2], 98.0)) + 0.030
        band = (movable & (points[:, 1] >= lo) & (points[:, 1] < hi)
                & (points[:, 2] > allowed) & (np.abs(points[:, 0]) < 0.20))
        if band.any():
            points[band, 2] = allowed
            clamped += int(band.sum())
    return clamped


def _push_waist_out(points: np.ndarray, waist: np.ndarray, rig: ea.Rig,
                    clearance: float) -> int:
    """Push waistband vertices that sit inside the body out to the skin.

    The banded slim-and-grow levels whole rows, but a row that mixes deep
    side tassets with a shallow front panel satisfies its percentile while
    the panel stays sunk.  This is the per-vertex remainder, done the only
    way a closed solid tolerates: parity against the actual body mesh picks
    the vertices genuinely inside the skin -- the garment's own inner
    surface, lying between shell and body, is outside the body and never
    moves -- and each one rides a radial ray to just past the surface it
    was under.
    """
    faces = getattr(rig, "faces", None)
    if faces is None or not waist.any():
        return 0
    soup = rig.positions[faces]
    near = soup[(soup[:, :, 1].min(axis=1) < 1.25)
                & (soup[:, :, 1].max(axis=1) > 0.85)]
    if not len(near):
        return 0
    probe = np.array([0.2913, 0.0412, 0.9557])
    probe /= np.linalg.norm(probe)
    index = np.nonzero(waist)[0]
    inside = gf._crossings(points[index], near, probe) % 2 == 1
    moved = 0
    for vertex in index[inside]:
        point = points[vertex]
        outward = np.array([point[0], 0.0, point[2]])
        length = float(np.linalg.norm(outward))
        if length < 1e-6:
            outward = np.array([0.0, 0.0, 1.0])
        else:
            outward /= length
        distance, crossings = cast(point, outward, near)
        if np.isfinite(distance) and crossings % 2 == 1:
            points[vertex] = point + outward * (distance + clearance)
            moved += 1
    return moved


def _drop_orphan_shards(surface, max_verts: int = 60,
                        min_gap: float = 0.04) -> int:
    """Delete tiny welded fragments floating clear of the garment.

    The concept-sheet meshes ship with debris -- splinters of strap or
    spike a few dozen vertices big that happen to sit inside other
    geometry and go unnoticed until a fit change (a narrower body, a
    moved cap) leaves one hanging in the air beside the shoulder.  A
    fragment is dropped when it is small and its nearest distance to the
    rest of the garment exceeds ``min_gap``; anything touching or large
    is design, not debris.  Returns how many fragments went.
    """
    triangles = surface.indices.reshape(-1, 3)
    inverse, edges, count = _weld(surface.positions, triangles)
    labels = _components(edges, count)[inverse]
    unique, sizes = np.unique(labels, return_counts=True)
    if len(unique) < 2:
        return 0
    drop = np.zeros(len(surface.positions), dtype=bool)
    dropped = 0
    for comp, size in zip(unique, sizes):
        if size > max_verts:
            continue
        members = labels == comp
        rest = ~members
        if not rest.any():
            continue
        mine = surface.positions[members]
        others = surface.positions[rest]
        gap = np.inf
        for point in mine:
            gap = min(gap, float(np.min(
                np.linalg.norm(others - point, axis=1))))
            if gap <= min_gap:
                break
        if gap > min_gap:
            drop |= members
            dropped += 1
    if not dropped:
        return 0
    keep = ~drop
    remap = np.cumsum(keep) - 1
    face_keep = keep[triangles].all(axis=1)
    surface.positions = surface.positions[keep]
    surface.normals = surface.normals[keep]
    surface.uvs = surface.uvs[keep]
    surface.indices = remap[triangles[face_keep]].reshape(-1)
    return dropped


def _harden_plates(points: np.ndarray, triangles: np.ndarray, rig: ea.Rig,
                   steps: list[dict], joints: np.ndarray,
                   weights: np.ndarray) -> int:
    """Bind each rigid arm plate to exactly one bone, in place.

    The nearest-surface inheritance is right for the trunk, which drapes like
    the skin it covers, and wrong for plate: a bracer picks up a 0.15 share of
    the upper arm from the verts near its elbow end, and that share smears a
    sixth of every elbow bend into the plate -- in motion the cuff visibly
    trails the forearm it should be riding.  Solids turn whole or not at all
    (the repose rule), so a welded component that the repose called sleeve
    snaps to its own dominant arm bone -- but only when that bone already
    holds a clear majority, so a true elbow-spanning sleeve keeps its blend
    and its bend.  A component the repose called cap instead binds to that
    side's clavicle: a pauldron worn on the shoulder must stay capping it,
    and weighted to the upper arm it dives outboard the moment the idle
    drops the arm.  Returns how many components were hardened.
    """
    inverse, edges, count = _weld(points, triangles)
    parent = np.arange(count)

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b in edges:
        ra, rb = find(int(a)), find(int(b))
        if ra != rb:
            parent[rb] = ra
    component = np.array([find(int(i)) for i in inverse])

    sleeve = np.zeros(len(points), dtype=bool)
    cap_side = {}
    for step in steps:
        if not step.get("applied"):
            continue
        if "sleeve" in step:
            sleeve |= np.asarray(step["sleeve"], dtype=bool)
        if "cap" in step:
            side = step["limb"][-1]
            mask = cap_side.get(side, np.zeros(len(points), dtype=bool))
            cap_side[side] = mask | np.asarray(step["cap"], dtype=bool)

    arm_bones = {name % side for name in ("upperarm_%s", "lowerarm_%s",
                                          "hand_%s") for side in "lr"}
    hardened = 0
    for comp in np.unique(component):
        members = component == comp
        total = int(members.sum())
        if total < 4:
            continue
        snap_to = None
        for side, mask in cap_side.items():
            if int((members & mask).sum()) * 2 >= total:
                snap_to = rig.joint_names.index("clavicle_" + side)
                break
        if snap_to is None and int((members & sleeve).sum()) * 2 >= total:
            mass: dict[int, float] = {}
            for slot in range(joints.shape[1]):
                for j, w in zip(joints[members, slot], weights[members, slot]):
                    if w > 0:
                        mass[int(j)] = mass.get(int(j), 0.0) + float(w)
            top = max(mass, key=mass.get)
            share = mass[top] / max(sum(mass.values()), 1e-9)
            if rig.joint_names[top] in arm_bones and share >= 0.55:
                snap_to = top
        if snap_to is None:
            continue
        joints[members] = 0
        joints[members, 0] = snap_to
        weights[members] = 0.0
        weights[members, 0] = 1.0
        hardened += 1
    return hardened


def _slim_legs(points: np.ndarray, rig: ea.Rig, region: str,
               movable: np.ndarray, target_clear: float) -> np.ndarray:
    """Slim each trouser leg onto its own limb.

    The trunk slim centres on one axis, which for a two-tube region is the gap
    between the legs; run there it pinches the inner seams together.  So each
    leg is slimmed separately, split at the crotch (the pelvis x centre),
    against that side's own body points and centre.
    """
    out = points.copy()
    # Only below the hip line: the tube slim measures against the limb's own
    # points, and at waistband height those are upper-thigh verts -- far
    # shallower front-to-back than the belly the waistband actually wraps.
    # Slimmed to them, the waist panels sink inside the torso and the body's
    # painted shirt renders over the top of the trousers.
    hip_line = min(float(rig.origin("thigh_l")[1]),
                   float(rig.origin("thigh_r")[1])) - 0.01
    movable = movable & (points[:, 1] < hip_line)
    for side in ("l", "r"):
        limb = rig._region(measure_bones(region, side))
        own = ((points[:, 0] >= 0) if side == "l" else (points[:, 0] < 0)) & movable
        if int(own.sum()) < 12 or len(limb) < 12:
            continue
        centre = np.array([float(np.median(limb[:, 0])),
                           float(np.median(limb[:, 2]))])
        out = _slim_to_body(out, rig, region, own, target_clear,
                            body_points=limb, centre=centre)
    # The waist is slimmed like the tubes, but against the body it actually
    # wraps -- the skirt region's belly and hips, not the thighs.  Measured
    # against the thighs it sank inside the torso and the body's painted
    # shirt rendered over the trousers; left authored, a deep tasset flares
    # fifteen centimetres proud.  Banded, per-axis and shrink-only, so it
    # hugs the hips and can never pass inside them.
    waist = points[:, 1] >= hip_line
    if region == "legs" and int(waist.sum()) >= 6:
        out = _slim_to_body(out, rig, "skirt", waist, target_clear)
        # Grown to convergence: the row smoothing that keeps banded factors
        # from stepping dilutes an edge row's growth by about a third per
        # pass, and one pass left a centimetre of waistband inside the hip.
        for _ in range(3):
            out = _slim_to_body(out, rig, "skirt", waist, target_clear,
                                grow=True)
        _push_waist_out(out, waist, rig, 0.006)
    return out


def build(source: Path, out: Path, rig: ea.Rig, kind: str, label: str,
          clearance: float = CLEARANCE, fit: str = "seat",
          taper: bool = False, race_path: Path | None = None) -> dict:
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
    triangles = surface.indices.reshape(-1, 3)
    # Seat, repose, and -- only if a pose was actually taken out -- seat
    # again.  The first seat is provisional for a posed piece: a hanging
    # sleeve is part of the height it divides by, so its vertical scale runs
    # ~15% small, but it puts the shoulders and hips where the rig has them,
    # which is what the pose search needs.  The second pass re-derives every
    # measurement from the corrected geometry; its girth ratio re-widens the
    # piece, and that is not the accident it looks like -- it is the same
    # widening the droop denied the first pass, so sleeves squashed while
    # they hung come back out to length once they lie along the arm.  (A
    # uniform second pass was tried instead and measured worse on both
    # counts.)  A piece with no pose to correct is seated once: seat() is not
    # idempotent -- its girth-to-height ratio compounds -- and a second pass
    # over the boots flattened the pair into a half-metre disc.
    seated = seat(surface.positions, rig, region, triangles, taper)
    seated, surface.normals, posed = repose(
        seated, surface.normals, rig, region, triangles)
    if any(step.get("applied") for step in posed):
        seated = seat(seated, rig, region, triangles, taper)
    if region == "torso":
        # Equalise the axes, hung from the collar.  The seat scales height to
        # the authored span but girth to the body region, and the height's
        # denominator is a bounding box stretched by whatever strap dangles
        # lowest -- so the chest shell lands a quarter squatter than the
        # concept drew it.  The width the seat picked is right; the height is
        # brought up to the same factor -- read from the seat itself, since
        # a bounding-box comparison is confounded by the reposed sleeves --
        # the collar stays put, and the hem falls where the design's own
        # proportions put it.
        raised, widened = LAST_SEAT_FACTORS
        if widened > raised * 1.02:
            # Below the shoulder line only.  The yoke -- collar, shoulder
            # caps, sleeve tops -- is fitted to the body and must not move;
            # what reads short is the trunk, so the trunk alone stretches
            # down toward the hem.
            stretch = min(widened / raised, 1.35)
            pivot = float(rig.origin("upperarm_l")[1]) - 0.06
            below = seated[:, 1] < pivot
            seated[below, 1] = pivot - (pivot - seated[below, 1]) * stretch
        for step in posed:
            if not step.get("applied") or "sleeve" not in step:
                continue
            pivot_name = str(step.get("pivot", ""))
            shoulder = rig.origin(pivot_name)
            seg_start, seg_end = rig.segment(pivot_name)
            arm_axis = seg_end - seg_start
            arm_axis /= max(np.linalg.norm(arm_axis), 1e-9)
            # Sleeves stop at the wrist.  Every horizontal pass -- the girth
            # reseat, the design's own proportions -- conspires to run the
            # sleeve past the hand, and a cuff over the fingers reads as a
            # mistake however faithful it is to the sheet.  The sleeve set is
            # compressed along the arm about the shoulder until its far edge
            # lands on the wrist; across the arm nothing changes, so cuffs
            # keep their thickness.
            sleeve = np.asarray(step["sleeve"], dtype=bool)
            hand = rig.origin("hand_" + pivot_name[-1])
            allowed = float(np.linalg.norm(hand - shoulder)) + 0.01
            if sleeve.any():
                travel = (seated[sleeve] - shoulder) @ arm_axis
                forward = travel[travel > 0.02]
                if len(forward) >= 12:
                    furthest = float(np.percentile(forward, 98.0))
                    if furthest > allowed:
                        squeeze = allowed / furthest
                        pull = np.where(travel > 0.0,
                                        travel * (squeeze - 1.0), 0.0)
                        seated[sleeve] += np.outer(pull, arm_axis)
                        step["sleeveSqueeze"] = round(squeeze, 3)
            # And the caps climb the trapezius.  Left at their authored
            # drape they sit on the deltoid with the slope to the neck bare;
            # a pauldron is worn riding up over the shoulder, so each cap
            # slides up and inboard along that slope.
            cap = np.asarray(step["cap"], dtype=bool)
            if cap.any():
                inboard = -1.0 if shoulder[0] > 0 else 1.0
                # Grown about its own centroid first: the authored caps are
                # cut to the concept's narrow silhouette and leave the round
                # of the shoulder bare, so each spreads a quarter wider
                # before it climbs.
                centroid = seated[cap].mean(axis=0)
                seated[cap] = centroid + (seated[cap] - centroid) * 1.12
                seated[cap] += np.array([inboard * 0.018, 0.042, 0.0])
                step["capRaised"] = True
        step0 = posed[0] if posed else {}
        step0["sleeveGroupsAligned"] = _align_arm_sleeves(
            seated, surface.indices.reshape(-1, 3), rig, posed)
        step0["sleeveRingsCentred"] = _centre_sleeves(
            seated, surface.indices.reshape(-1, 3), rig, posed)
        # Slim the trunk onto the body.  The seat sizes girth from the design's
        # own depth-to-height ratio, and these are chunky plate designs, so the
        # chest shell stood 4-5 cm proud and read barrel-chested.  With the
        # body's covered region hidden under the liner there is nothing to
        # clear, so the trunk is drawn in toward the body's own vertical axis
        # until it hugs -- per height band, shrink-only, floored so a genuine
        # pauldron or breastplate relief is thinned rather than flattened, and
        # never past the body plus clearance so the shirt cannot surface.
        # Sleeves and caps are exempt: they are fitted to the limb already, and
        # a sleeve pulled to the torso axis collapses onto the arm.
        exempt = np.zeros(len(seated), dtype=bool)
        for step in posed:
            if step.get("applied"):
                exempt |= np.asarray(step.get("sleeve", np.zeros(len(seated))),
                                     dtype=bool)
                exempt |= np.asarray(step.get("cap", np.zeros(len(seated))),
                                     dtype=bool)
        seated = _slim_to_body(seated, rig, region, ~exempt,
                               clearance + 0.008)
        step0 = posed[0] if posed else {}
        step0["bustFlattened"] = _flatten_bust(seated, rig, region, ~exempt)
    elif region in ("legs", "boots"):
        # Legwear is chunky for the same reason: sized to the design's own
        # girth, it stands proud of the leg.  With the leg's own skin hidden
        # under the garment's weighting there is room to draw each tube onto
        # its thigh -- per leg, shrink-only, never inside the limb.  A little
        # more clearance than the torso: knees bend and a trouser cut dead to
        # the calf creases into it.  Boots take the same treatment against
        # calf, foot and ball -- seated to the region box they overshot the
        # foot both fore and aft -- with tighter clearance, since ankles flex
        # less than knees inside a shaft.
        seated = _slim_legs(seated, rig, region,
                            np.ones(len(seated), dtype=bool),
                            clearance + (0.02 if region == "legs" else 0.012))
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
    shards = _drop_orphan_shards(surface)

    glb = ea.EquipmentGLB(generator="Eloria conform_equipment")
    material = textured_material(glb, f"{label} Base", png)
    glb.skeleton(rig)
    positions, normals, uvs, indices = surface.arrays()[0]
    joints, weights = ea.Rig.weights_for(
        rig, positions.astype(np.float64),
        list(ea.GARMENT_SKIN[region]) + REPOSE_SKIN.get(region, []))
    plates = 0
    if region == "torso":
        plates = _harden_plates(positions, surface.indices.reshape(-1, 3),
                                rig, posed, joints, weights)
    primitives = [glb.primitive(positions, normals, uvs, indices, material,
                                joints=joints, weights=weights)]
    lined = False
    if region == "torso" and race_path is not None:
        layers = shirt_liner(race_path)
        if layers is not None:
            shell, paint = layers
            # Double sided: a lifted shell can fold at the armpit crease once
            # a pose compresses it, and a culled backface there is a pinhole
            # straight through to the shirt.
            liner_material = textured_material(glb, "%s Liner" % label, None,
                                               colour=LINER_COLOUR,
                                               double_sided=True)
            primitives.append(glb.primitive(
                shell[0], shell[1], shell[2], shell[3], liner_material,
                joints=shell[4], weights=shell[5], weight_floats=True))
            # The paint coat ships alpha-blended so it draws after the body
            # and wins their depth ties -- see shirt_liner.
            paint_material = textured_material(glb, "%s Paint" % label, None,
                                               colour=LINER_COLOUR,
                                               double_sided=True)
            glb.doc["materials"][paint_material]["alphaMode"] = "BLEND"
            primitives.append(glb.primitive(
                paint[0], paint[1], paint[2], paint[3], paint_material,
                joints=paint[4], weights=paint[5], weight_floats=True))
            lined = True
    glb.mesh(label, primitives, skin=0)
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
            "repose": [{key: value for key, value in step.items()
                        if key not in ("sleeve", "cap")}
                       for step in posed], "liner": lined,
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
                         args.clearance, args.fit, args.taper,
                         race_path=race_path)
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

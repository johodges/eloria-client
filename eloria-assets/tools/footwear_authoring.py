#!/usr/bin/env python3
"""Sixty-four boots, authored from concept art, built on the measured body.

Footwear used to be one lofted shell dressed as twenty catalogue entries.  This
builds each design as its own mesh: a base shell measured off the real foot, and
a stack of layers - plates, straps, cuffs, wraps, reliefs, ornaments - that carry
the silhouette of the sheet it came from.

Three things here are load-bearing and none of them is decoration.

**Skin scope.**  A boot is refitted per wearer by scaling each bone about *its
own origin*, and ``calf``'s origin is the knee.  A sole vertex that inherits the
body's own heel weighting - which is 31 per cent ``calf`` - is dragged 62 mm
under the floor on an Orun.  The foot shell and its sole are therefore scoped to
the foot chain and the shaft keeps the calf, so each part of the boot is
refitted against the part of the leg it sits on.

**Ground pre-compensation.**  The runtime now scales the foot chain by the
wearer's own ankle-to-sole distance (see ``soleDrop`` in the registry), which is
what lets one sole stand on sixteen different floors.  That scale can *shrink* a
boot - the female rigs are twenty per cent shorter from ankle to sole - so the
shell is measured against each cast body's foot divided by the shrink it will
receive.  Sized to the reference foot alone it would close inside a smaller one.

**Closure.**  Every element is a closed solid.  Open sheets have no inside, so
the enclosure test cannot use them and the winding test cannot check them; a
strap that is a closed band costs a few triangles and is measurable.  Winding is
settled at the end by ``face_outward``, which flips any closed component that
encloses negative volume - the failure that once made a closed boot render as an
open-toed sandal with the foot inside it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import numpy as np

from equipment_authoring import (
    MATERIAL_BASE, MATERIAL_DETAIL, MATERIAL_TRIM, Rig, Surface, limb_rings,
    smooth_profile)

# ---------------------------------------------------------------------------
# Skin scopes
# ---------------------------------------------------------------------------

#: Bones each scope is solved against.  ``boot_foot`` deliberately excludes the
#: calf: see the module docstring.
SKIN_SCOPES = {
    "boot_foot": ["foot_l", "foot_r", "ball_l", "ball_r"],
    "boot_shaft": ["calf_l", "calf_r", "foot_l", "foot_r"],
}
FOOT = "boot_foot"
SHAFT = "boot_shaft"

#: The shared boot/trouser datum, on the reference rig.  Expressed as a fraction
#: along ``calf`` from the knee because world Y does not transfer: the Ssarathi
#: ankle stands at Y 0.235 where the Luminous one stands at 0.087, so the same
#: seam sits about 145 mm higher up the world on a digitigrade leg.
CUFF_DATUM_T = 0.488          # world Y 0.320 on luminous_male
CUFF_FLOOR_T = 0.663          # world Y 0.240 - the lowest an outer boot may end
ANKLE_TOP_T = 0.966           # world Y 0.102 - the highest an inner boot may end
#: Where a shaft finishes, below the ankle and inside the foot shell.
SHAFT_ROOT_T = 1.075

#: How far the sole may stand proud of the wearer's own, in metres.  Positive is
#: above the floor; the acceptance limit is 8 mm below it.
SOLE_PROUD = .0015
SOLE_THICKNESS = .017
SHELL_CORNER = 2.6


def _squircle(phi: float) -> tuple[float, float]:
    """Unit rounded-rectangle offsets for one angle around a shell ring."""
    power = 2. / SHELL_CORNER
    across, along = math.cos(phi), math.sin(phi)
    return (math.copysign(abs(across) ** power, across),
            math.copysign(abs(along) ** power, along))


# ---------------------------------------------------------------------------
# The foot, measured
# ---------------------------------------------------------------------------

@dataclass
class FootAnatomy:
    """Everything a boot needs to know about one foot, measured off the body."""

    side: str
    ankle: np.ndarray
    ball: np.ndarray
    toe_tip: np.ndarray
    instep: np.ndarray        # unit axis, ankle -> ball
    forward: np.ndarray       # unit axis, ball -> toe
    under_arch: np.ndarray    # down, square to the instep
    under_toe: np.ndarray     # down, square to the forward axis
    lateral: np.ndarray
    arch: float
    toe_span: float
    heel_reach: float
    toe_reach: float
    ground: float
    flesh: np.ndarray


def _frame(start: np.ndarray, end: np.ndarray):
    axis = end - start
    length = float(np.linalg.norm(axis))
    axis = axis / max(length, 1e-9)
    down = np.array([0., -1., 0.])
    down = down - axis * float(down @ axis)
    if float(down @ down) < 1e-6:
        down = np.array([0., 0., -1.])
    return axis, length, down / max(np.linalg.norm(down), 1e-9)


def _foot_flesh(positions: np.ndarray, ankle: np.ndarray,
                toe_tip: np.ndarray) -> np.ndarray:
    """Body vertices belonging to one foot, scoped geometrically.

    Measured off the body rather than off the skin weights: the heel is largely
    bound to the calf, so a bone-scoped region misses exactly the part of the
    foot the back of the boot has to contain.
    """
    span = toe_tip - ankle
    length = float(np.linalg.norm(span)) or 1.0
    axis = span / length
    offsets = positions - ankle
    along = np.clip(offsets @ axis, 0.0, length)
    aside = np.linalg.norm(offsets - np.outer(along, axis), axis=1)
    same_side = np.sign(positions[:, 0]) == np.sign(ankle[0] or 1.0)
    return same_side & (aside < .085)


def measure_foot(rig: Rig, side: str) -> FootAnatomy:
    ankle = rig.origin(f"foot_{side}")
    ball = rig.origin(f"ball_{side}")
    toe_tip = rig.segment(f"ball_{side}")[1]
    instep, arch, under_arch = _frame(ankle, ball)
    forward, toe_span, under_toe = _frame(ball, toe_tip)

    picked = _foot_flesh(rig.positions, ankle, toe_tip)
    flesh = rig.positions[picked]
    span = toe_tip - ankle
    length = float(np.linalg.norm(span)) or 1.0
    axis = span / length
    along = np.clip((rig.positions - ankle) @ axis, 0.0, length)

    # How far the heel actually reaches behind the ankle, measured rather than
    # assumed: a plantigrade heel runs back nearly four tenths of the arch and a
    # digitigrade one barely two.
    heel_reach = arch * .38
    rear = rig.positions[picked & (along < length * .45)]
    if len(rear) > 16:
        behind = -((rear - ankle) @ instep)
        heel_reach = float(np.clip(np.quantile(behind, .995),
                                   arch * .16, arch * .60))
    # And the same in front: toe length varies far more between races than any
    # multiple of the last joint's span predicts.
    toe_reach = toe_span * 1.18
    front = rig.positions[picked & (along > length * .5)]
    if len(front) > 16:
        ahead = (front - ball) @ forward
        toe_reach = float(np.clip(np.quantile(ahead, .995) + .020,
                                  toe_span * .8, toe_span * 2.4))
    return FootAnatomy(
        side=side, ankle=ankle, ball=ball, toe_tip=toe_tip, instep=instep,
        forward=forward, under_arch=under_arch, under_toe=under_toe,
        lateral=np.array([1., 0., 0.]), arch=arch, toe_span=toe_span,
        heel_reach=heel_reach, toe_reach=toe_reach,
        ground=float(flesh[:, 1].min()) if len(flesh) else 0.0, flesh=flesh)


@dataclass
class Station:
    """One cross-section of the foot shell, seated on the flesh beneath it."""

    centre: np.ndarray
    down: np.ndarray
    width: float
    height: float


def _cast_bodies(rig) -> list[np.ndarray]:
    """Every body silhouette this piece has to clear, widest first."""
    primary = getattr(rig, "primary", rig)
    others = list(getattr(rig, "others", ()))
    return [primary.positions] + [other.positions for other in others]


def foot_stations(rig: Rig, foot: FootAnatomy, *, toe_lift: float = .010,
                  girth: float = 1.0, ground_shrink: float = 1.0) -> list[Station]:
    """The spine of the foot shell, sized to contain every body in the cast.

    ``ground_shrink`` is the smallest foot-chain scale the runtime will apply to
    this piece.  The shell is measured against each body's flesh *divided* by it,
    so the shrink the wearer receives still leaves the foot inside.
    """
    arch, instep, forward = foot.arch, foot.instep, foot.forward
    under_arch, under_toe = foot.under_arch, foot.under_toe
    heel = foot.ankle - instep * (foot.heel_reach + .024) + under_arch * .028
    spine = [heel,
             foot.ankle + under_arch * .038 - instep * (foot.heel_reach * .42),
             foot.ankle + instep * (arch * .46) + under_arch * .044,
             foot.ball + under_arch * .026,
             foot.ball + forward * (foot.toe_reach * .46) + under_toe * .018,
             foot.ball + forward * foot.toe_reach + under_toe * .010]
    downs = [under_arch, under_arch, under_arch, under_arch, under_toe, under_toe]
    widths = [.048, .056, .058, .054, .048, .036]
    heights = [.044, .052, .048, .042, .032, .026]

    axis = foot.toe_tip - foot.ankle
    axis = axis / max(float(np.linalg.norm(axis)), 1e-9)
    bodies = []
    for positions in _cast_bodies(rig):
        picked = _foot_flesh(positions, foot.ankle, foot.toe_tip)
        if picked.sum() > 24:
            bodies.append(positions[picked])
    if not bodies:
        bodies = [foot.flesh]

    seats, sized = [], []
    for index, (point, down, floor_w, floor_h) in enumerate(
            zip(spine, downs, widths, heights)):
        seat = float((point - foot.ankle) @ axis)
        widest = across = below = above = 0.0
        found = False
        for flesh in bodies:
            near = flesh[np.abs((flesh - foot.ankle) @ axis - seat) < .030]
            if len(near) < 8:
                continue
            found = True
            offset = near - point
            # The extremes, not a percentile: the last one per cent of a foot is
            # the joint at the base of the little toe and the point of the heel,
            # which are exactly the two places a shell sized to the rest of it
            # leaves skin showing.
            across = max(across, float(np.abs(offset @ foot.lateral).max()))
            reach = offset @ down
            below = max(below, float(reach.max()))
            above = max(above, -float(reach.min()))
        if not found:
            # Past the last toe there is no flesh left to measure.  Carry the
            # previous ring forward, tapered, rather than dropping to a floor
            # value: a tip built to a small constant left the undersides of the
            # toes below the sole meant to cap them.
            if sized:
                last_w, last_h = sized[-1]
                seats.append(point + down * float(
                    (seats[-1] - spine[index - 1]) @ down))
                sized.append((max(floor_w, last_w * .84),
                              max(floor_h, last_h * .84)))
            else:
                seats.append(point)
                sized.append((floor_w, floor_h))
            continue
        clear = .012 / max(ground_shrink, .5)
        across = across / ground_shrink + clear
        below = below / ground_shrink + clear * .9
        above = above / ground_shrink + clear * .9
        widest = max(floor_w, across) * girth
        # Recentre between the two, then take the larger half-height: the spine
        # runs under the foot, so a ring sized symmetrically about it covers the
        # sole twice over and stops short on the instep.  That gap along the top
        # of the foot is what showed skin through a boot closed everywhere else.
        seats.append(point + down * (below - above) * .5)
        sized.append((widest, max(floor_h, (below + above) * .5) * girth))
    return _seat_on_floor(rig, foot, seats, downs, sized, toe_lift)


def _seat_on_floor(rig, foot: FootAnatomy, seats, downs, sized,
                   toe_lift: float) -> list[Station]:
    """Drop each station onto the flesh directly beneath it, never below the floor.

    A station that stops above the foot leaves a slot for it to show through; one
    that runs below the floor is a boot under the ground the actor stands on.
    Reading the flesh station by station rather than assuming one sole height is
    also what keeps this honest on a digitigrade leg, where only the toes are on
    the ground and the hock is a quarter of a metre above it.
    """
    axis = foot.toe_tip - foot.ankle
    axis = axis / max(float(np.linalg.norm(axis)), 1e-9)
    flesh = foot.flesh
    floor_plane = foot.ground + SOLE_PROUD
    stations = []
    for index, (point, down, (width, height)) in enumerate(zip(seats, downs, sized)):
        drop = abs(float(down[1]))
        if drop > 1e-6:
            seat = float((point - foot.ankle) @ axis)
            under = flesh[np.abs((flesh - foot.ankle) @ axis - seat) < .045]
            target = float(under[:, 1].min()) - .005 if len(under) else foot.ground
            target = max(target, floor_plane)
            shift = (float(point[1]) - drop * height - target) / (2. * drop)
            point = point + np.array([0., -shift * drop, 0.])
            height = height + shift
        stations.append(Station(centre=point, down=down, width=width,
                                height=max(height, .004)))
    return stations


def station_ring(station: Station, foot: FootAnatomy, sides: int = 20,
                 grow: float = 0.0) -> np.ndarray:
    """A squircle cross-section, traversed so the loft faces outwards."""
    ring = np.empty((sides, 3))
    for index in range(sides):
        phi = 2 * math.pi * index / sides
        across, along = _squircle(phi)
        ring[index] = (station.centre
                       + foot.lateral * across * (station.width + grow)
                       + station.down * along * (station.height + grow))
    return ring


def resample(stations: list[Station], foot: FootAnatomy, rows: int,
             sides: int = 20, grow: float = 0.0) -> list[np.ndarray]:
    """Interpolate the station spine into a denser ring stack."""
    if rows <= len(stations):
        return [station_ring(s, foot, sides, grow) for s in stations]
    keys = np.linspace(0., 1., len(stations))
    want = np.linspace(0., 1., rows)
    centres = np.array([s.centre for s in stations])
    downs = np.array([s.down for s in stations])
    widths = np.array([s.width for s in stations])
    heights = np.array([s.height for s in stations])
    rings = []
    for travel in want:
        centre = np.array([np.interp(travel, keys, centres[:, a]) for a in range(3)])
        down = np.array([np.interp(travel, keys, downs[:, a]) for a in range(3)])
        down = down / max(float(np.linalg.norm(down)), 1e-9)
        rings.append(station_ring(
            Station(centre, down, float(np.interp(travel, keys, widths)),
                    float(np.interp(travel, keys, heights))), foot, sides, grow))
    return rings

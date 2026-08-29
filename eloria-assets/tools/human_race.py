#!/usr/bin/env python3
"""Author the Human race -- skeleton, mesh, materials -- from nothing.

Every other playable race in this repository is the one Quaternius "Superhero"
skin re-proportioned by ``build_native_nymara_glbs.retarget_bind``.  This
module is the control arm of an experiment: the same race slot, built instead
out of authored geometry, so the two can be judged side by side.

Nothing here is derived from another player model.  The skeleton's *interface*
-- joint names, joint order, parents and rest rotations -- is read from
``human_rig_contract.json``, because those three things are what the shared
animation library's absolute rotation tracks are written against and a race
that changed them would simply not animate.  Every bone offset, which is to
say all of the anatomy, is solved here from a table of human measurements.
The mesh is swept from authored profile curves, grafted limb into torso so the
surface is continuous across a shoulder, and relaxed; the textures are
synthesised from noise fields.  numpy and Pillow, nothing else.

Layout of this module:

  * ``Contract``      the shared rig interface, and the basis it fixes
  * ``Proportions``   the measurements this race is authored to
  * ``skeleton``      offsets solved against the fixed hip and ground planes
  * ``Shell``         the quad-mesh authoring kit: rings, grafts, relaxation
  * ``body``          the figure itself
  * ``weights``       skin binding
  * ``textures``      albedo, normal and metallic-roughness synthesis
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import io
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

CONTRACT_PATH = Path(__file__).resolve().parent / "human_rig_contract.json"

# Hip and ground planes are shared by every race: the clips write pelvis
# translation directly, so a race that moved either would float or sink.
# Measured off the shipped rigs and asserted again after the solve.
HIP_HEIGHT = {"female": .9318, "male": .9491}
# Uniform import scale for the whole actor, carried by the model registry
# rather than by the rig: the clips write pelvis translation directly, so a
# taller skeleton would leave the hips at the reference height with the feet
# hanging below them.  The authored mesh is already adult human height, so
# this is 1.
STATURE = 1.0
GROUND_HEIGHT = {"female": .0148, "male": .0152}

FINGERS = ("index", "middle", "ring", "pinky", "thumb")
CAPE_CHAINS = ("l", "c", "r")
CAPE_LINKS = 4


def quaternion_matrix(q) -> np.ndarray:
    x, y, z, w = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]],
        dtype=np.float64)


def matrix_quaternion(m: np.ndarray) -> list[float]:
    trace = m[0, 0] + m[1, 1] + m[2, 2]
    if trace > 0:
        s = math.sqrt(trace + 1.) * 2
        q = [(m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s,
             (m[1, 0] - m[0, 1]) / s, .25 * s]
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1. + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        q = [.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s,
             (m[2, 1] - m[1, 2]) / s]
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1. + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        q = [(m[0, 1] + m[1, 0]) / s, .25 * s, (m[1, 2] + m[2, 1]) / s,
             (m[0, 2] - m[2, 0]) / s]
    else:
        s = math.sqrt(1. + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        q = [(m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, .25 * s,
             (m[1, 0] - m[0, 1]) / s]
    return [float(v) for v in q]


class Contract:
    """The part of the rig a race may not choose: names, order, parents, basis.

    ``basis[name]`` is the joint's world rotation in the rest pose.  It falls
    out of the rest rotations alone -- rotations compose without reference to
    any translation -- which is what lets this module solve anatomy against a
    basis it did not author.
    """

    def __init__(self, gender: str, path: Path = CONTRACT_PATH):
        data = json.loads(path.read_text(encoding="utf-8"))
        self.names = [joint["name"] for joint in data["joints"]]
        self.parent = {joint["name"]: joint["parent"] for joint in data["joints"]}
        self.rotation = {name: data["restRotations"][gender][name]
                         for name in self.names}
        # Where the reference skull sits relative to its own Head joint.
        # Hairstyles and headwear are authored in that frame, so this is
        # interface in exactly the way the hip and ground planes are.
        self.head_envelope = data["headEnvelope"][gender]
        self.basis: dict[str, np.ndarray] = {}
        for name in self.names:
            local = quaternion_matrix(self.rotation[name])
            parent = self.parent[name]
            self.basis[name] = local if parent is None else self.basis[parent] @ local

    def index(self, name: str) -> int:
        return self.names.index(name)


# ---------------------------------------------------------------------------
# Proportions
#
# The measurements this race is authored to, in metres on the rest skeleton,
# read off the concept sheets: a lean, naturalistic adult rather than the
# heroic build the shared base body carries.  Bone offsets are given as
# world-space displacements from the parent joint and converted into the
# parent's own rest basis on the way in, so the numbers below can be checked
# against a figure drawing rather than against a quaternion.
#
# An in-chain bone -- one that simply continues its parent -- carries a single
# length instead, laid along the parent's rest Y axis, which is the axis the
# shared clips were authored to rotate.  That is why anatomy here is lengths
# and offsets and never a rest rotation.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Proportions:
    pelvis_depth: float          # how far behind the origin the hip joint sits
    spine: tuple                 # spine_01, spine_02, spine_03, neck_01, Head
    clavicle: tuple              # spine_03 -> clavicle, world delta (left side)
    shoulder: tuple              # clavicle -> upperarm, world delta
    upperarm: float              # shoulder -> elbow
    forearm: float               # elbow -> wrist
    palm: tuple                  # wrist -> middle knuckle, world delta
    knuckles: dict               # per finger: (root delta, phalanx lengths)
    hip: tuple                   # pelvis -> thigh, world delta
    leg: tuple                   # femur, tibia, ankle->ball (scaled to ground)
    toe: float                   # ball -> ball leaf
    girth: dict = field(default_factory=dict)


# The two sheets differ in more than size: the male figure is drawn with the
# shoulder line well outside the hip line and a flat chest, the female with a
# shorter clavicle, a higher waist, and the hip line the widest thing in the
# silhouette.  Those are the numbers that differ most below.
PROPORTIONS = {
    "male": Proportions(
        pelvis_depth=-.035,
        spine=(.124, .114, .138, .198, .084),
        clavicle=(.030, .150, .028),
        shoulder=(.166, -.030, -.058),
        upperarm=.285, forearm=.240,
        palm=(.098, -.004, .004),
        knuckles={
            "index": ((.100, .002, .034), (.044, .026, .019)),
            "middle": ((.104, .000, .011), (.048, .030, .021)),
            "ring": ((.100, -.002, -.013), (.044, .028, .020)),
            "pinky": ((.092, -.004, -.036), (.035, .021, .017)),
            "thumb": ((.032, -.016, .033), (.034, .026, .018)),
        },
        hip=(.093, .019, .006),
        leg=(.452, .437, .168), toe=.086,
        girth={"neck": .062, "chest": .164, "waist": .126, "hips": .150,
               "thigh": .088, "calf": .062, "ankle": .040, "foot": .228,
               "upperarm": .050, "wrist": .029, "head": .098, "bust": .0},
    ),
    "female": Proportions(
        pelvis_depth=-.032,
        spine=(.118, .108, .130, .190, .080),
        clavicle=(.026, .142, .026),
        shoulder=(.140, -.026, -.052),
        upperarm=.262, forearm=.222,
        palm=(.090, -.004, .004),
        knuckles={
            "index": ((.092, .002, .031), (.040, .024, .017)),
            "middle": ((.096, .000, .010), (.044, .027, .019)),
            "ring": ((.092, -.002, -.012), (.040, .025, .018)),
            "pinky": ((.084, -.004, -.033), (.032, .019, .015)),
            "thumb": ((.029, -.015, .030), (.031, .024, .016)),
        },
        hip=(.089, .017, .005),
        leg=(.450, .440, .160), toe=.080,
        girth={"neck": .053, "chest": .138, "waist": .108, "hips": .147,
               "thigh": .086, "calf": .057, "ankle": .036, "foot": .212,
               "upperarm": .043, "wrist": .025, "head": .092, "bust": .030},
    ),
}


@dataclass
class Skeleton:
    contract: Contract
    world: dict          # joint name -> world rest position
    local: dict          # joint name -> local rest translation
    leg_scale: float
    gender: str = ""

    def matrix(self, name: str) -> np.ndarray:
        out = np.eye(4)
        out[:3, :3] = self.contract.basis[name]
        out[:3, 3] = self.world[name]
        return out

    def segment(self, name: str) -> tuple[np.ndarray, np.ndarray]:
        """A bone as the pair of points a distance field can be built on."""
        children = [child for child in self.contract.names
                    if self.contract.parent[child] == name]
        start = self.world[name]
        if not children:
            return start, start
        return start, np.mean([self.world[child] for child in children], axis=0)


def _cape_offsets(gender: str) -> dict:
    """Where the three cloth chains leave spine_03, as world deltas.

    No clip in the shared library names a cape bone, so these are the race's
    to place and the cloth solver drives them at runtime.  They hang behind
    the figure, which is also how the client reads a rig's facing.
    """
    spread = .148 if gender == "male" else .136
    offsets = {}
    for chain in CAPE_CHAINS:
        side = {"l": -spread, "c": 0., "r": spread}[chain]
        offsets[f"cape_{chain}_01"] = (side, .120, -.128)
        for link in range(2, CAPE_LINKS + 1):
            offsets[f"cape_{chain}_{link:02d}"] = (0., -.290, -.020)
    return offsets


def build_skeleton(gender: str) -> Skeleton:
    """Solve every bone offset against the shared hip and ground planes."""
    contract = Contract(gender)
    p = PROPORTIONS[gender]
    basis = contract.basis
    hip_y, ground_y = HIP_HEIGHT[gender], GROUND_HEIGHT[gender]

    # The leg is authored in proportion and then scaled by one factor so the
    # ball joint lands on the shared ground plane.  A race that skipped this
    # would keep the reference hip height with its feet somewhere else.
    thigh_y = hip_y + p.hip[1]
    drop = sum(length * basis[bone][1, 1] for length, bone in
               zip(p.leg, ("thigh_l", "calf_l", "foot_l")))
    leg_scale = (ground_y - thigh_y) / drop
    femur, tibia, ankle = (length * leg_scale for length in p.leg)

    def mirror(v):
        return (-v[0], v[1], v[2])

    def same(v):
        return v

    deltas: dict[str, tuple] = {"pelvis": (0., hip_y, p.pelvis_depth)}
    lengths: dict[str, float] = {
        "spine_01": p.spine[0], "spine_02": p.spine[1], "spine_03": p.spine[2],
        "neck_01": p.spine[3], "Head": p.spine[4]}
    for side in ("l", "r"):
        flip = same if side == "l" else mirror
        deltas[f"clavicle_{side}"] = flip(p.clavicle)
        deltas[f"upperarm_{side}"] = flip(p.shoulder)
        lengths[f"lowerarm_{side}"] = p.upperarm
        lengths[f"hand_{side}"] = p.forearm
        deltas[f"thigh_{side}"] = flip(p.hip)
        lengths[f"calf_{side}"] = femur
        lengths[f"foot_{side}"] = tibia
        lengths[f"ball_{side}"] = ankle
        lengths[f"ball_leaf_{side}"] = p.toe * leg_scale
        for finger in FINGERS:
            root, bones = p.knuckles[finger]
            deltas[f"{finger}_01_{side}"] = flip(root)
            for index, length in enumerate(bones):
                lengths[f"{finger}_{index + 2:02d}_{side}"] = length
            lengths[f"{finger}_04_leaf_{side}"] = bones[-1]
    deltas.update(_cape_offsets(gender))

    world: dict[str, np.ndarray] = {}
    local: dict[str, np.ndarray] = {}
    for name in contract.names:
        parent = contract.parent[name]
        if parent is None:
            world[name] = np.zeros(3)
            local[name] = np.zeros(3)
            continue
        if name in deltas:
            delta = np.asarray(deltas[name], dtype=float)
        else:
            delta = basis[parent][:, 1] * lengths[name]
        world[name] = world[parent] + delta
        local[name] = basis[parent].T @ delta
    assert abs(world["ball_l"][1] - ground_y) < 1e-9, world["ball_l"]
    assert abs(world["pelvis"][1] - hip_y) < 1e-9, world["pelvis"]
    return Skeleton(contract, world, local, float(leg_scale), gender)


# ---------------------------------------------------------------------------
# Shell: the quad-mesh authoring kit
#
# Everything below builds one surface out of rings.  A ring is a closed loop of
# vertices; a patch is a rectangular block of them, which may or may not wrap
# in its columns.  Two operations do all the work:
#
#   bridge(a, b)   sew two equal-length loops into a band of quads
#   graft(patch, block, ring)
#                  cut a block of quads out of a patch and sew the hole's
#                  boundary to a limb's root ring
#
# The graft is what keeps an arm from being a separate cylinder pushed into a
# torso.  The two surfaces share the boundary edge, so the shoulder is one
# continuous sheet and the relaxation pass afterwards rounds it into a deltoid
# instead of leaving a crease where a primitive ended.
# ---------------------------------------------------------------------------


class Patch:
    """A rectangular block of vertex ids, optionally wrapped in its columns."""

    def __init__(self, ids: np.ndarray, wrap: bool):
        self.ids = np.asarray(ids, dtype=np.int64)
        self.wrap = bool(wrap)
        self.holes: list[tuple[int, int, int, int]] = []

    @property
    def rows(self) -> int:
        return self.ids.shape[0]

    @property
    def columns(self) -> int:
        return self.ids.shape[1]

    def _blocked(self, row: int, column: int) -> bool:
        for r0, r1, c0, c1 in self.holes:
            if r0 <= row < r1 and c0 <= column < c1:
                return True
        return False

    def quads(self):
        span = self.columns if self.wrap else self.columns - 1
        for row in range(self.rows - 1):
            for column in range(span):
                if self._blocked(row, column):
                    continue
                right = (column + 1) % self.columns
                yield (int(self.ids[row, column]), int(self.ids[row, right]),
                       int(self.ids[row + 1, right]), int(self.ids[row + 1, column]))

    def hole(self, r0: int, r1: int, c0: int, c1: int) -> list[int]:
        """Remove the quad block and return its boundary loop.

        The loop is returned in the same rotational sense the surrounding
        quads are wound in, so a limb ring bridged onto it comes out facing
        the same way as the patch it grows from.
        """
        self.holes.append((r0, r1, c0, c1))
        top = [int(self.ids[r0, c]) for c in range(c0, c1 + 1)]
        right = [int(self.ids[r, c1]) for r in range(r0 + 1, r1 + 1)]
        bottom = [int(self.ids[r1, c]) for c in range(c1 - 1, c0 - 1, -1)]
        left = [int(self.ids[r, c0]) for r in range(r1 - 1, r0, -1)]
        return top + right + bottom + left


class Shell:
    """A growing triangle mesh with per-vertex region tags."""

    def __init__(self):
        self.points: list[np.ndarray] = []
        self.region: list[str] = []
        self.uv: list[tuple[float, float]] = []
        self.tris: list[tuple[int, int, int]] = []

    def vertex(self, point, region: str, uv=(0., 0.)) -> int:
        self.points.append(np.asarray(point, dtype=np.float64))
        self.region.append(region)
        self.uv.append((float(uv[0]), float(uv[1])))
        return len(self.points) - 1

    def ring(self, points, region: str, uvs=None) -> list[int]:
        if uvs is None:
            uvs = [(index / max(len(points), 1), 0.) for index in range(len(points))]
        return [self.vertex(point, region, uv) for point, uv in zip(points, uvs)]

    def quad(self, a: int, b: int, c: int, d: int) -> None:
        self.tris.append((a, b, c))
        self.tris.append((a, c, d))

    def patch(self, rows: list[list[int]], wrap: bool) -> Patch:
        return Patch(np.asarray(rows, dtype=np.int64), wrap)

    def emit(self, patch: Patch) -> None:
        for a, b, c, d in patch.quads():
            self.quad(a, b, c, d)

    def bridge(self, lower: list[int], upper: list[int]) -> None:
        """Sew two equal-length loops.  ``upper`` is further along the sweep."""
        count = len(lower)
        assert count == len(upper), (count, len(upper))
        for index in range(count):
            nxt = (index + 1) % count
            self.quad(lower[index], lower[nxt], upper[nxt], upper[index])

    def fan(self, loop: list[int], apex: int) -> None:
        for index in range(len(loop)):
            self.tris.append((loop[index], loop[(index + 1) % len(loop)], apex))

    def arrays(self):
        return (np.stack(self.points), np.asarray(self.tris, dtype=np.int64),
                np.asarray(self.uv, dtype=np.float64), list(self.region))


def vertex_normals(points: np.ndarray, tris: np.ndarray) -> np.ndarray:
    a, b, c = points[tris[:, 0]], points[tris[:, 1]], points[tris[:, 2]]
    face = np.cross(b - a, c - a)
    normals = np.zeros_like(points)
    for column in range(3):
        np.add.at(normals, tris[:, column], face)
    length = np.linalg.norm(normals, axis=1, keepdims=True)
    return normals / np.maximum(length, 1e-12)


def enclosed_volume(points: np.ndarray, tris: np.ndarray) -> float:
    middle = points.mean(axis=0)
    local = points - middle
    return float(np.einsum("ij,ij->i", local[tris[:, 0]],
                           np.cross(local[tris[:, 1]],
                                    local[tris[:, 2]])).sum() / 6.)


def face_the_right_way(points: np.ndarray, tris: np.ndarray) -> np.ndarray:
    """Flip a closed shell that came out inside-out.

    Every piece here is built with one bridging convention, so the whole shell
    is consistently oriented and one signed-volume test settles the direction
    for all of it.  A back-facing body does not disappear, it goes transparent
    from the near side, which is a hard thing to notice in a contact sheet.
    """
    return tris if enclosed_volume(points, tris) > 0 else tris[:, ::-1].copy()


def open_edges(tris: np.ndarray) -> int:
    """Directed edges that have no opposite twin: holes and winding flips."""
    edges = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    keys = edges[:, 0].astype(np.int64) * (1 << 32) + edges[:, 1]
    twins = edges[:, 1].astype(np.int64) * (1 << 32) + edges[:, 0]
    return int((~np.isin(keys, twins)).sum())


def _adjacency(count: int, tris: np.ndarray):
    edges = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    edges = np.concatenate([edges, edges[:, ::-1]])
    order = np.lexsort((edges[:, 1], edges[:, 0]))
    edges = edges[order]
    keep = np.ones(len(edges), dtype=bool)
    keep[1:] = (edges[1:] != edges[:-1]).any(axis=1)
    edges = edges[keep]
    degree = np.bincount(edges[:, 0], minlength=count).astype(np.float64)
    return edges, np.maximum(degree, 1.)


def relax(points: np.ndarray, tris: np.ndarray, *, passes: int = 6,
          shrink: float = .48, inflate: float = -.5,
          weight: np.ndarray | None = None) -> np.ndarray:
    """Taubin smoothing: a shrink pass and an inflate pass, so volume holds.

    Plain Laplacian smoothing would round the figure away.  The alternating
    signs put the mass back, which is what turns a grafted seam into a shoulder
    without also deflating the chest.  ``weight`` scales the correction per
    vertex, so a seam can be relaxed harder than a face.
    """
    edges, degree = _adjacency(len(points), tris)
    out = points.copy()
    for step in range(passes * 2):
        factor = shrink if step % 2 == 0 else inflate
        summed = np.zeros_like(out)
        np.add.at(summed, edges[:, 0], out[edges[:, 1]])
        delta = summed / degree[:, None] - out
        if weight is not None:
            delta = delta * weight[:, None]
        out = out + factor * delta
    return out


# ---------------------------------------------------------------------------
# The figure
#
# The trunk, neck and head are one swept tube.  Its cross-section is a
# superellipse whose half width, half depth, centre and squareness are read off
# a table of measured heights -- a rib cage is not a circle and a waist is not
# a smaller rib cage -- and the table is the place to argue with the concept
# sheet.  Arms graft into the side of that tube, legs fork out of its bottom
# ring through a shared crotch, and the head above the jaw is stitched to a
# finer ring count so the face gets the vertices and the belly does not.
# ---------------------------------------------------------------------------

TRUNK_COLUMNS = 44
HEAD_COLUMNS = 72
ARM_COLUMNS = 22
PALM_COLUMNS = 26
FINGER_COLUMNS = 8
LEG_COLUMNS = 24

# (height, half width, half depth, centre z, squareness).  Squareness 2 is an
# ellipse; above it the section flattens towards a rounded rectangle, which is
# what a rib cage and a waist actually are in section.
TRUNK_PROFILE = {
    "male": (
        (.930, .158, .118, -.026, 2.5),   # fork: the two legs are still one section
        (.975, .152, .114, -.020, 2.5),   # hip
        (1.020, .142, .107, -.012, 2.4),
        (1.050, .135, .102, -.008, 2.4),
        (1.085, .128, .098, -.004, 2.4),  # waist
        (1.130, .130, .099, .001, 2.4),
        (1.190, .140, .106, .006, 2.5),   # lower ribs
        (1.260, .153, .114, .010, 2.5),   # chest
        (1.325, .162, .117, .008, 2.5),
        (1.385, .169, .110, .002, 2.4),
        (1.438, .174, .101, -.004, 2.3),  # shoulder line
        (1.478, .150, .092, -.010, 2.2),  # trapezius
        (1.505, .098, .080, -.014, 2.1),  # neck base
        (1.535, .062, .065, -.012, 2.0),
        (1.575, .059, .064, -.006, 2.0),  # neck under the jaw
        (1.604, .064, .074, -.004, 2.0),  # jaw line
        (1.634, .072, .085, -.006, 2.0),
        (1.666, .078, .090, -.010, 2.0),
        (1.700, .082, .092, -.014, 2.0),  # eye level
        (1.734, .083, .091, -.017, 2.0),
        (1.766, .078, .086, -.019, 2.0),  # forehead
        (1.796, .062, .074, -.020, 2.0),
        (1.814, .040, .050, -.020, 2.0),
        (1.822, .000, .000, -.020, 2.0),  # crown
    ),
    "female": (
        (.912, .154, .114, -.024, 2.5),   # fork
        (.952, .150, .112, -.019, 2.5),   # hip, as wide as the shoulder
        (.995, .138, .104, -.012, 2.4),
        (1.022, .128, .098, -.008, 2.4),
        (1.055, .118, .092, -.004, 2.4),  # waist, higher and narrower
        (1.100, .119, .093, .002, 2.4),
        (1.165, .127, .101, .008, 2.5),
        (1.230, .134, .108, .010, 2.5),
        (1.288, .140, .110, .008, 2.5),
        (1.343, .145, .104, .002, 2.4),
        (1.396, .148, .096, -.004, 2.3),  # shoulder line
        (1.437, .128, .088, -.010, 2.2),
        (1.463, .086, .074, -.014, 2.1),  # neck base
        (1.492, .053, .056, -.012, 2.0),
        (1.528, .051, .055, -.006, 2.0),
        (1.554, .056, .068, -.004, 2.0),  # jaw line
        (1.582, .062, .078, -.006, 2.0),
        (1.612, .067, .084, -.010, 2.0),
        (1.646, .070, .086, -.014, 2.0),  # eye level
        (1.678, .071, .085, -.017, 2.0),
        (1.710, .068, .081, -.019, 2.0),
        (1.740, .058, .070, -.020, 2.0),
        (1.758, .037, .047, -.020, 2.0),
        (1.766, .000, .000, -.020, 2.0),  # crown
    ),
}


def smooth_series(values: np.ndarray, passes: int = 3) -> np.ndarray:
    """Binomial smoothing along a swept profile, ends held.

    The profile table is a set of measurements, so it is interpolated
    linearly and then smoothed rather than fitted: a spline through hand
    written numbers overshoots at the waist and puts a bulge where the table
    says there is none.
    """
    out = np.asarray(values, dtype=np.float64).copy()
    for _ in range(passes):
        inner = (out[:-2] + 2 * out[1:-1] + out[2:]) * .25
        out[1:-1] = inner
    return out



def _profile_at(gender: str, heights: np.ndarray):
    table = np.asarray(TRUNK_PROFILE[gender], dtype=np.float64)
    columns = [np.interp(heights, table[:, 0], table[:, index])
               for index in range(1, 5)]
    return [smooth_series(column) for column in columns]



# Semantic rows of TRUNK_PROFILE, so the sculpting below can name a height
# instead of counting entries.
LANDMARK = {"fork": 0, "hip": 1, "waist": 4, "ribs": 6,
            "chest": 7, "shoulder": 10, "neck_base": 12, "jaw": 15,
            "eyes": 18, "forehead": 20, "crown": 23}


def landmarks(gender: str) -> dict:
    table = TRUNK_PROFILE[gender]
    marks = {name: table[row][0] for name, row in LANDMARK.items()}
    marks["seat"] = marks["fork"] - .035
    marks["chin"] = marks["jaw"] - .005
    marks["brow"] = marks["eyes"] + .023
    marks["nose"] = marks["chin"] + .58 * (marks["eyes"] - marks["chin"])
    marks["mouth"] = marks["chin"] + .28 * (marks["eyes"] - marks["chin"])
    marks["ear"] = marks["eyes"] - .012
    marks["face_z"] = table[LANDMARK["eyes"]][2] + table[LANDMARK["eyes"]][3]
    marks["head_x"] = table[LANDMARK["eyes"]][1]
    return marks


def _sculpt(points: np.ndarray, radial: np.ndarray, features) -> np.ndarray:
    """Add anatomical relief to a swept surface.

    Each feature is a smooth anisotropic bump pushed along a direction, gated
    by how much the surface already faces that way.  The gate is what keeps a
    brow ridge from dragging the side of the skull forward with it: a bump
    with a wide enough falloff to be smooth reaches further round the head
    than it should, and without the gate the relief slides sideways instead of
    standing proud.
    """
    out = points.copy()
    for centre, radii, direction, amount in features:
        centre = np.asarray(centre, dtype=np.float64)
        radii = np.asarray(radii, dtype=np.float64)
        direction = np.asarray(direction, dtype=np.float64)
        direction = direction / max(float(np.linalg.norm(direction)), 1e-12)
        offset = (points - centre) / radii
        falloff = np.exp(-np.einsum("ij,ij->i", offset, offset))
        gate = np.clip(radial @ direction, 0., 1.)
        out += (amount * falloff * gate)[:, None] * direction
    return out


def _surface(gender: str, y: float):
    table = np.asarray(TRUNK_PROFILE[gender], dtype=np.float64)
    return [float(np.interp(y, table[:, 0], table[:, index])) for index in range(1, 5)]


def _at(gender: str, y: float, degrees: float):
    """A point on the swept surface, by height and angle round it.

    Anatomy is placed here rather than by adding offsets to a bounding box.
    An ear guessed at "the back plane plus 46 mm" lands 46 mm inside the head
    on one gender and outside it on the other; an ear at "95 degrees round,
    at this height" lands on the surface of both.
    """
    half_width, half_depth, centre, squareness = _surface(gender, y)
    theta = math.radians(degrees)
    exponent = 2. / squareness
    sin, cos = math.sin(theta), math.cos(theta)
    return np.array([half_width * math.copysign(abs(sin) ** exponent, sin), y,
                     centre + half_depth * math.copysign(abs(cos) ** exponent, cos)])


def _out(gender: str, y: float, degrees: float):
    """The outward direction of that surface point."""
    half_width, half_depth, _, _ = _surface(gender, y)
    point = _at(gender, y, degrees)
    direction = np.array([point[0] / half_width ** 2, 0.,
                          (point[2] - _surface(gender, y)[2]) / half_depth ** 2])
    return direction / max(float(np.linalg.norm(direction)), 1e-9)



def body_features(gender: str) -> list:
    """The relief that turns a swept tube into a body.

    Each entry names a height and an angle round the figure, and the bump is
    pushed along the surface's own outward direction there unless it says
    otherwise.  Written against the landmark table, so the male and female
    figures differ where the sheets differ -- the seat, the bust and the jaw
    carry most of it -- rather than by a width multiplier over everything.
    """
    m = landmarks(gender)
    female = gender == "female"
    forward = np.array([0., 0., 1.])
    out = []

    def put(y, degrees, radii, amount, direction=None, lift=0.):
        centre = _at(gender, y, degrees)
        way = _out(gender, y, degrees) if direction is None else np.asarray(direction, float)
        if lift:
            way = way + np.array([0., lift, 0.])
        out.append((centre, radii, way, amount))

    for sign in (1, -1):
        put(m["seat"], sign * 152, (.080, .078, .085), .036 if female else .027)
        # pectoral or bust
        put(m["chest"] + (.030 if female else .036), sign * 22,
            (.052, .050, .048) if female else (.062, .036, .048),
            .042 if female else .014,
            direction=None if not female else forward, lift=-.30 if female else .05)
        put(m["shoulder"] - .050, sign * 34, (.052, .012, .044), .006, lift=.30)
        put(m["neck_base"] - .020, sign * 148, (.058, .040, .052), .013)
        put(m["waist"] - .026, sign * 74, (.048, .036, .056), .006)
        put(m["ribs"] + .030, sign * 118, (.046, .050, .046), .005)
        # face: cheekbone, the hollow under it, and the jaw corner
        put(m["eyes"] - .015, sign * 42, (.026, .019, .030), .008)
        put(m["mouth"] + .008, sign * 46, (.022, .024, .028), -.004)
        put(m["jaw"] + .016, sign * 76, (.026, .022, .030), .009 if female else .013)
        put(m["brow"], sign * 22, (.032, .012, .034), .005 if female else .009)
        put(m["eyes"], sign * 25, (.024, .014, .028), -.012)
        put(m["eyes"] - .002, sign * 24, (.014, .011, .022), .007)
        put(m["nose"] - .005, sign * 13, (.011, .009, .020), .009)
        # the ear, and the bowl inside it
        put(m["ear"] - .004, sign * 104, (.010, .026, .019), .013)
        put(m["ear"] - .004, sign * 104, (.006, .014, .011), -.007)

    put(m["chest"] + .010, 0, (.016, .058, .040), -.007)
    put(m["waist"] - .036, 0, (.011, .011, .026), -.008)
    put(m["ribs"], 180, (.015, .130, .045), -.009)
    put(m["seat"] - .012, 180, (.013, .052, .055), -.022)
    put(m["eyes"] + .046, 180, (.068, .046, .045), .011)
    # the nose, in three pieces: bridge, tip, and the septum under it
    put(m["eyes"] - .004, 0, (.011, .024, .026), .008, direction=forward)
    put(m["nose"], 0, (.012, .010, .022), .016 if female else .019,
        direction=forward, lift=-.22)
    put(m["nose"] - .011, 0, (.008, .007, .018), .006, direction=forward, lift=-.5)
    # the two lips and the line between them
    put(m["mouth"] + .013, 0, (.008, .006, .018), -.002, direction=forward)
    put(m["mouth"] + .005, 0, (.022, .007, .024), .007, direction=forward)
    put(m["mouth"] - .010, 0, (.019, .008, .024), .008, direction=forward)
    put(m["mouth"] - .002, 0, (.026, .0040, .024), -.005, direction=forward)
    put(m["chin"] + .014, 0, (.022, .018, .030), .008 if female else .013,
        direction=forward, lift=-.25)
    return out


def _unwrap(angles: np.ndarray) -> np.ndarray:
    """Make a loop of angles monotone so it can be blended toward uniform."""
    out = np.asarray(angles, dtype=np.float64).copy()
    for index in range(1, len(out)):
        while out[index] < out[index - 1]:
            out[index] += 2 * math.pi
    return out


def stitch_loops(shell: Shell, lower: list[int], lower_t, upper: list[int], upper_t):
    """Sew two loops of different lengths, walking both in parameter order.

    This is what lets the head carry seventy-two columns while the torso
    carries forty-four: a face needs the vertices and a belly does not, and
    a race that ran one ring count from the crotch to the crown would have to
    pay for the face everywhere.
    """
    na, nb = len(lower), len(upper)
    ta = list(lower_t) + [lower_t[0] + 1.]
    tb = list(upper_t) + [upper_t[0] + 1.]
    i = j = 0
    while i < na or j < nb:
        take_lower = j >= nb or (i < na and ta[i + 1] <= tb[j + 1])
        if take_lower:
            shell.tris.append((lower[i % na], lower[(i + 1) % na], upper[j % nb]))
            i += 1
        else:
            shell.tris.append((lower[i % na], upper[(j + 1) % nb], upper[j % nb]))
            j += 1


def sweep(shell: Shell, stations, columns: int, region: str,
          angles: np.ndarray | None = None) -> list[list[int]]:
    """Lay rings along a list of stations and return them.

    A station is ``(centre, right, up, half_width, half_height, squareness)``.
    Carrying the frame explicitly rather than deriving it lets the foot turn
    from a leg's horizontal section into a shoe's vertical one without the
    ring spinning on the way.
    """
    if angles is None:
        angles = np.arange(columns) * (2 * math.pi / columns)
    rings = []
    for index, (centre, right, up, half_width, half_height, squareness) in enumerate(stations):
        theta = angles[index] if angles.ndim == 2 else angles
        exponent = 2. / max(squareness, 1e-3)
        sin, cos = np.sin(theta), np.cos(theta)
        offset = (half_width * np.sign(sin) * np.abs(sin) ** exponent)[:, None] * np.asarray(right) \
            + (half_height * np.sign(cos) * np.abs(cos) ** exponent)[:, None] * np.asarray(up)
        points = np.asarray(centre)[None, :] + offset
        rings.append(shell.ring(points, region))
    return rings


def _heights(low: float, high: float, count: int, marks) -> np.ndarray:
    """Sweep heights between two planes, clustered at the named landmarks."""
    samples = np.linspace(low, high, 4096)
    density = np.ones_like(samples)
    for centre, strength, width in marks:
        density += strength * np.exp(-((samples - centre) / width) ** 2)
    cumulative = np.concatenate([[0.], np.cumsum(density[:-1] + density[1:]) * .5])
    cumulative /= cumulative[-1]
    return np.interp(np.linspace(0., 1., count), cumulative, samples)


def _face_angles(gender: str, heights: np.ndarray) -> np.ndarray:
    """Crowd the head's columns onto the face and thin them out at the back.

    Seventy-two columns spread evenly round a skull put fourteen across the
    face, which is not enough to carry a nose.  Warping the spacing costs
    nothing -- the topology is unchanged -- and roughly doubles the density
    where every feature is, at the price of a coarser occiput that nothing
    reads.
    """
    m = landmarks(gender)
    u = np.arange(HEAD_COLUMNS) / HEAD_COLUMNS
    strength = np.clip((heights - m["jaw"] + .050) / .075, 0., 1.) * .58
    strength = np.where(heights > m["forehead"],
                        np.clip((m["crown"] - heights) / .070, 0., 1.) * .58,
                        strength)
    return (2 * math.pi * u)[None, :] - strength[:, None] * np.sin(2 * math.pi * u)[None, :]


def _stations(gender: str, heights: np.ndarray):
    half_width, half_depth, centre, squareness = _profile_at(gender, heights)
    right, up = np.array([1., 0., 0.]), np.array([0., 0., 1.])
    return [((0., float(y), float(cz)), right, up, float(a), float(b), float(s))
            for y, a, b, cz, s in zip(heights, half_width, half_depth,
                                      centre, squareness)]


TRUNK_RINGS = 30
HEAD_RINGS = 40


def _trunk_and_head(shell: Shell, gender: str):
    """The one tube the whole figure hangs off, crotch to crown."""
    m = landmarks(gender)
    table = TRUNK_PROFILE[gender]
    collar = table[14][0]          # the neck, just under the jaw
    crown = table[-2][0]
    trunk_heights = _heights(
        m["fork"], collar, TRUNK_RINGS,
        [(m["hip"], .8, .055), (m["waist"], .5, .050), (m["shoulder"], 1.6, .058),
         (m["neck_base"], 1.1, .030)])
    head_heights = _heights(
        collar + .004, crown, HEAD_RINGS,
        [(m["jaw"], 1.3, .022), (m["mouth"], 1.8, .016), (m["nose"], 1.5, .016),
         (m["eyes"], 2.4, .026), (m["brow"], 1.0, .020),
         (m["forehead"], .5, .030)])
    trunk_rings = sweep(shell, _stations(gender, trunk_heights),
                        TRUNK_COLUMNS, "torso")
    head_rings = sweep(shell, _stations(gender, head_heights), HEAD_COLUMNS,
                       "head", angles=_face_angles(gender, head_heights))
    trunk = shell.patch(trunk_rings, wrap=True)
    head = shell.patch(head_rings, wrap=True)
    apex = shell.vertex((0., table[-1][0], table[-1][3]), "head")
    return {"trunk": trunk, "head": head, "apex": apex,
            "trunk_heights": trunk_heights, "head_heights": head_heights,
            "collar": collar}


ARM_RINGS = 24
PALM_RINGS = 6
FINGER_RINGS = 5

# Radius of the arm along shoulder -> wrist, as (half thickness, half depth)
# at a fraction of the way down.  The elbow narrows and the forearm swells
# again below it; a straight taper reads as a tube with a hand on the end.
ARM_TAPER = ((.00, 1.10, 1.16), (.10, 1.02, 1.06), (.24, .94, .96),
             (.40, .86, .88), (.52, .79, .81), (.62, .84, .86),
             (.76, .74, .76), (.88, .62, .66), (1.00, .50, .58))


def _arm_stations(gender: str, sk: Skeleton, side: str):
    p = PROPORTIONS[gender]
    sign = 1. if side == "l" else -1.
    shoulder = sk.world[f"upperarm_{side}"]
    wrist = sk.world[f"hand_{side}"]
    axis = np.array([sign, 0., 0.])
    up = np.array([0., 0., 1.])
    right = np.cross(axis, up)
    keys = np.asarray(ARM_TAPER)
    travel = np.linspace(.02, 1., ARM_RINGS)
    thickness = np.interp(travel, keys[:, 0], keys[:, 1]) * p.girth["upperarm"]
    depth = np.interp(travel, keys[:, 0], keys[:, 2]) * p.girth["upperarm"]
    stations = []
    for step, half_a, half_b in zip(travel, thickness, depth):
        centre = shoulder + (wrist - shoulder) * step
        stations.append((centre, right, up, float(half_a), float(half_b), 2.1))
    return stations, axis, up, right


def _palm_stations(gender: str, sk: Skeleton, side: str, axis, up, right):
    """Wrist to knuckles: a section that flattens as it widens."""
    p = PROPORTIONS[gender]
    wrist = sk.world[f"hand_{side}"]
    knuckle = wrist + np.asarray(p.palm) * np.array([1. if side == "l" else -1., 1., 1.])
    thickness = (.021, .020, .0185, .017, .015, .0125)
    breadth = (.031, .036, .040, .043, .045, .046)
    scale = 1. if gender == "male" else .90
    stations = []
    for index in range(PALM_RINGS):
        step = index / (PALM_RINGS - 1)
        centre = wrist + (knuckle - wrist) * step
        centre = centre + up * (-.002 * step)
        stations.append((centre, right, up, thickness[index] * scale,
                         breadth[index] * scale, 2.0 + 1.4 * step))
    return stations


LEG_RINGS = 26

# The foot in outline: (lower z, lower y, upper z, thickness, half width).
# z, thickness and width are in foot lengths; the lower y is in ankle heights
# above the sole, so -1 is the sole exactly and the contour is pinned to the
# ground plane the leg chain was solved to.  Thickness is measured from the
# lower point, in foot lengths rather than ankle heights, so raising the ankle
# lengthens the heel without also inflating the toe box.
FOOT_OUTLINE = (
    (-.237, -.18, .171, .072, .153),
    (-.256, -.44, .127, .141, .162),
    (-.237, -.73, .093, .219, .171),
    (-.165, -.97, .084, .273, .182),
    (-.047, -1.00, .119, .273, .194),
    (.110, -1.00, .200, .264, .201),
    (.250, -1.00, .300, .255, .205),
    (.380, -1.00, .410, .243, .204),
    (.490, -1.00, .505, .225, .198),
    (.585, -1.00, .590, .198, .186),
    (.665, -.99, .660, .153, .164),
    (.725, -.96, .712, .072, .120),
)

# (fraction from hip to ankle, half width, half depth) as multiples of the
# thigh girth.  The knee pinches and the calf swells behind it.
LEG_TAPER = ((.00, 1.02, 1.06), (.14, 1.00, 1.04), (.34, .88, .92),
             (.52, .74, .78), (.63, .64, .68), (.70, .66, .64),
             (.78, .62, .58), (.88, .53, .50), (1.00, .45, .43))


def _leg_stations(gender: str, sk: Skeleton, side: str, top: float):
    """Crotch to ankle, then the foot turning forward under it."""
    p = PROPORTIONS[gender]
    right, up = np.array([1., 0., 0.]), np.array([0., 0., 1.])
    hip = sk.world[f"thigh_{side}"]
    knee = sk.world[f"calf_{side}"]
    ankle = sk.world[f"foot_{side}"]
    sole = GROUND_HEIGHT[gender] - .0250
    keys = np.asarray(LEG_TAPER)
    heights = _heights(top, ankle[1] + .014, LEG_RINGS,
                       [(knee[1], .9, .050), (hip[1] - .05, .7, .060),
                        (ankle[1] + .06, .5, .045)])
    stations = []
    for y in heights:
        step = float(np.clip((top - y) / max(top - ankle[1], 1e-6), 0., 1.))
        if y >= knee[1]:
            blend = (top - y) / max(top - knee[1], 1e-6)
            centre = hip * (1 - blend) + knee * blend
        else:
            blend = (knee[1] - y) / max(knee[1] - ankle[1], 1e-6)
            centre = knee * (1 - blend) + ankle * blend
        centre = np.array([centre[0], y, centre[2]])
        half_a = float(np.interp(step, keys[:, 0], keys[:, 1])) * p.girth["thigh"]
        half_b = float(np.interp(step, keys[:, 0], keys[:, 2])) * p.girth["thigh"]
        stations.append((centre, right, up, half_a, half_b, 2.2))
    # The foot.  Rather than roll a ring along a curve and hope a heel
    # appears, each station is given as the two points its section spans: the
    # lower one traces the heel, the sole and the underside of the toe, the
    # upper one the front of the ankle, the instep and the top of the toe.
    # The ring's own axis is whatever joins them, so the quarter turn from a
    # horizontal ankle section to a vertical toe section falls out of the
    # outline instead of being imposed on it.
    length = p.girth["foot"]
    rise = ankle[1] - sole
    for lower_z, lower_y, upper_z, thickness, width in FOOT_OUTLINE:
        low = np.array([ankle[0], sole + rise * (1. + lower_y),
                        ankle[2] + length * lower_z])
        high = np.array([ankle[0], low[1] + length * thickness,
                         ankle[2] + length * upper_z])
        span = high - low
        reach = float(np.linalg.norm(span))
        stations.append(((low + high) * .5, right, span / max(reach, 1e-9),
                         width * length, reach * .5, 3.0))
    return stations


def _cap_angles(rows: int = 3, columns: int = 12) -> np.ndarray:
    """Where a cap's boundary slots sit around the ring, in ring angle.

    The slots are evenly spaced around a rectangle, which is not evenly spaced
    around a circle.  Handing these back lets the last palm ring be generated
    on the cap's own spacing, so the two sew together without a spiral.
    """
    slots = ([(1., 1. - 2. * c / (columns - 1)) for c in range(columns)]
             + [(0., -1.)]
             + [(-1., 1. - 2. * c / (columns - 1)) for c in range(columns - 1, -1, -1)]
             + [(0., 1.)])
    return _unwrap(np.array([math.atan2(v, u) for v, u in slots]))


def _knuckle_cap(shell: Shell, centre, right, up, axis, half_a: float,
                 half_b: float, squareness: float, region: str):
    """Close the palm with a grid the fingers can be grafted into.

    A ring cannot be capped and then branched four ways; a grid can.  The
    grid's boundary is generated on the same superellipse the last palm ring
    uses, in the same rotational order, so the two sew together one to one.
    """
    rows, columns = 3, 12
    exponent = 2. / squareness
    ids = np.zeros((rows, columns), dtype=np.int64)
    for row in range(rows):
        v = 1. - 2. * row / (rows - 1)
        for column in range(columns):
            u = 1. - 2. * column / (columns - 1)
            if row == 1 and 0 < column < columns - 1:
                offset = u * half_b * np.asarray(up)
                offset = offset + np.asarray(axis) * .006 * (1. - u * u)
            else:
                angle = math.atan2(v, u)
                sin, cos = math.sin(angle), math.cos(angle)
                offset = (half_a * math.copysign(abs(sin) ** exponent, sin)
                          * np.asarray(right)
                          + half_b * math.copysign(abs(cos) ** exponent, cos)
                          * np.asarray(up))
            ids[row, column] = shell.vertex(np.asarray(centre) + offset, region)
    perimeter = ([int(ids[0, c]) for c in range(columns)]
                 + [int(ids[1, columns - 1])]
                 + [int(ids[2, c]) for c in range(columns - 1, -1, -1)]
                 + [int(ids[1, 0])])
    return Patch(ids, wrap=False), perimeter


def _finger(shell: Shell, sk: Skeleton, side: str, finger: str, loop: list[int],
            scale: float, region: str) -> None:
    chain = [sk.world[f"{finger}_{link:02d}_{side}"] for link in (1, 2, 3)]
    chain.append(sk.world[f"{finger}_04_leaf_{side}"])
    path = np.stack(chain)
    travel = np.concatenate([[0.], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
    travel = travel / travel[-1]
    axis = path[-1] - path[0]
    axis = axis / max(float(np.linalg.norm(axis)), 1e-9)
    reference = np.array([0., 0., 1.])
    up = reference - axis * float(reference @ axis)
    up = up / max(float(np.linalg.norm(up)), 1e-9)
    right = np.cross(axis, up)
    taper = (1.06, 1.00, .94, .88, .78)
    stations = []
    for index in range(FINGER_RINGS):
        step = (index + 1) / (FINGER_RINGS + .6)
        centre = np.stack([np.interp(step, travel, path[:, axisidx])
                           for axisidx in range(3)])
        radius = scale * taper[index]
        stations.append((centre, right, up, radius, radius * 1.06, 2.2))
    rings = sweep(shell, stations, FINGER_COLUMNS, region)
    shell.bridge(loop, rings[0])
    for index in range(len(rings) - 1):
        shell.bridge(rings[index], rings[index + 1])
    apex = shell.vertex(path[-1] + axis * scale * .55, region)
    shell.fan(rings[-1], apex)


def _loop_angles(shell: Shell, loop: list[int], centre, right, up) -> np.ndarray:
    points = np.stack([shell.points[index] for index in loop]) - np.asarray(centre)
    return _unwrap(np.arctan2(points @ np.asarray(right), points @ np.asarray(up)))


def _blend_angles(measured: np.ndarray, count: int, settle: int) -> np.ndarray:
    """Ease a grafted ring's angles onto an even spacing over a few rings.

    The boundary of a hole in the torso is a rounded rectangle and an arm is
    round, so the first ring has to inherit the hole's spacing or the band
    between them shears.  A few rings later the spacing is even and the limb
    is an ordinary tube again.
    """
    columns = len(measured)
    uniform = measured[0] + np.arange(columns) * (2 * math.pi / columns)
    out = np.zeros((count, columns))
    for ring in range(count):
        blend = min(1., (ring + 1) / settle)
        blend = blend * blend * (3 - 2 * blend)
        out[ring] = measured * (1 - blend) + uniform * blend
    return out


def _build_arm(shell: Shell, gender: str, sk: Skeleton, side: str,
               trunk: Patch, rows: tuple, columns: tuple) -> None:
    stations, axis, up, right = _arm_stations(gender, sk, side)
    loop = trunk.hole(rows[0], rows[1], columns[0], columns[1])
    shoulder = sk.world[f"upperarm_{side}"]
    angles = _blend_angles(_loop_angles(shell, loop, shoulder, right, up),
                           ARM_RINGS, 5)
    rings = sweep(shell, stations, ARM_COLUMNS, f"arm_{side}", angles=angles)
    shell.bridge(loop, rings[0])
    for index in range(len(rings) - 1):
        shell.bridge(rings[index], rings[index + 1])

    # The palm's rings ease onto the cap's own angular spacing so the band
    # that closes the knuckles is not a spiral.
    cap_angles = _cap_angles()
    even = cap_angles[0] + np.arange(PALM_COLUMNS) * (2 * math.pi / PALM_COLUMNS)
    palm_angles = np.stack([
        even * (1 - t) + cap_angles * t
        for t in np.linspace(0., 1., PALM_RINGS) ** 1.5])
    palm = sweep(shell, _palm_stations(gender, sk, side, axis, up, right),
                 PALM_COLUMNS, f"hand_{side}", angles=palm_angles)
    stitch_loops(shell, rings[-1], np.arange(ARM_COLUMNS) / ARM_COLUMNS,
                 palm[0], (palm_angles[0] - palm_angles[0][0]) / (2 * math.pi))
    palm_patch = shell.patch(palm, wrap=True)
    centre, _, _, half_a, half_b, squareness = _palm_stations(
        gender, sk, side, axis, up, right)[-1]
    knuckle = np.asarray(centre) + axis * (.012 if gender == "male" else .011)
    cap, perimeter = _knuckle_cap(shell, knuckle, right, up, axis, half_a,
                                 half_b, squareness, f"hand_{side}")
    shell.bridge(palm[-1], perimeter)
    scale = .0100 if gender == "male" else .0089
    for index, finger in enumerate(("index", "middle", "ring", "pinky")):
        _finger(shell, sk, side, finger, cap.hole(0, 2, index * 3, index * 3 + 2),
                scale * (.85 if finger == "pinky" else 1.), f"hand_{side}")
    shell.emit(cap)
    # The thumb leaves the side of the palm, not its end, so it grafts into
    # the palm tube itself.
    # The thumb leaves the palm side, forward: a sixteenth of the way round
    # the ring on the left hand and the mirror of that on the right.  Reading
    # the column off the ring angle rather than guessing it is what keeps the
    # graft off the back of the hand.
    thumb_column = 1 if side == "l" else PALM_COLUMNS - 3
    _finger(shell, sk, side, "thumb",
            palm_patch.hole(1, 3, thumb_column, thumb_column + 2),
            scale * 1.15, f"hand_{side}")
    shell.emit(palm_patch)


def _fork_legs(shell: Shell, gender: str, sk: Skeleton, bottom: list[int]) -> None:
    """Split the lowest trunk ring into two legs across a shared crotch.

    The alternative -- two cylinders pushed up into a closed pelvis -- leaves
    the crotch as an intersection rather than a surface, and it is the first
    thing a walk cycle opens up.  Here the two legs share the three crotch
    vertices and half the hip ring each, so there is nothing to come apart.
    """
    table = np.asarray(TRUNK_PROFILE[gender])
    fork, _, half_depth, centre = table[0][:4]
    drop = .052 if gender == "male" else .049
    front = shell.vertex((0., fork - drop, centre + half_depth * .42), "torso")
    back = shell.vertex((0., fork - drop, centre - half_depth * .42), "torso")
    middle = shell.vertex((0., fork - drop * 1.38, centre - .006), "torso")
    half = TRUNK_COLUMNS // 2
    # Wound against the hip ring's own quads: the last trunk row traverses
    # this edge in increasing column order, so the fork's closure has to
    # traverse it the other way or the crotch is not a surface.
    shell.tris += [(bottom[0], bottom[-1], front), (bottom[1], bottom[0], front),
                   (bottom[half], bottom[half - 1], back),
                   (bottom[half + 1], bottom[half], back)]
    loops = {"l": [front] + bottom[1:half] + [back, middle],
             "r": [back] + bottom[half + 1:] + [front, middle]}
    right, up = np.array([1., 0., 0.]), np.array([0., 0., 1.])
    for side, loop in loops.items():
        assert len(loop) == LEG_COLUMNS, (side, len(loop))
        stations = _leg_stations(gender, sk, side, fork - .028)
        hip = sk.world[f"thigh_{side}"]
        angles = _blend_angles(_loop_angles(shell, loop, hip, right, up),
                               len(stations), 6)
        rings = sweep(shell, stations, LEG_COLUMNS, f"leg_{side}", angles=angles)
        shell.bridge(rings[0], loop)
        for index in range(len(rings) - 1):
            shell.bridge(rings[index + 1], rings[index])
        toe = np.stack([shell.points[index] for index in rings[-1]]).mean(axis=0)
        apex = shell.vertex(toe + np.array([0., 0., .010]), f"leg_{side}")
        shell.fan(list(reversed(rings[-1])), apex)


def seat_head(sk: Skeleton, points: np.ndarray, region: list[str]) -> np.ndarray:
    """Move the Head joint so hairstyles and headwear land on this skull.

    Hair and headwear are authored once, in Head-local space, against the
    reference skull.  This race's skull is its own shape, so measured in that
    frame it sat too high and too far back, which put a hairstyle's front edge
    behind the forehead and left the crown bare.  Head is a leaf joint, so
    moving it moves nothing but the frame those pieces hang in: the mesh does
    not shift by a millimetre.

    The forward match is made on the scalp band rather than on the whole head,
    because the frontmost point of a head is its nose and this race's nose
    projects less than the reference's.  Seating on the nose put the forehead
    three millimetres proud of a hairstyle that was cut to clear the
    reference one, and three millimetres of scalp through a hair cap is a bald
    patch with a hard edge round it.

    Returns the Head-local correction, for reporting.
    """
    skull = points[np.asarray(region) == "head"]
    head = sk.matrix("Head")
    local = (np.linalg.inv(head) @ np.c_[skull, np.ones(len(skull))].T).T[:, :3]
    want = sk.contract.head_envelope
    low, high = want["band"]
    scalp = local[(local[:, 1] > low) & (local[:, 1] < high)]
    # Three millimetres of clearance rather than a flush match: a hair cap is
    # a shell cut to the reference skull, and a scalp that meets it exactly
    # still breaks through wherever this skull curves differently.
    clearance = .003
    shift = np.array([0., float(local[:, 1].max()) - want["crown"] + clearance,
                      float(scalp[:, 2].max()) - want["front"] + clearance])
    basis = sk.contract.basis["Head"]
    sk.world["Head"] = sk.world["Head"] + basis @ shift
    parent = sk.contract.parent["Head"]
    sk.local["Head"] = sk.contract.basis[parent].T @ (
        sk.world["Head"] - sk.world[parent])
    return shift


def build_body(gender: str, sk: Skeleton) -> Shell:
    shell = Shell()
    m = landmarks(gender)
    parts = _trunk_and_head(shell, gender)
    trunk, head = parts["trunk"], parts["head"]
    heights = parts["trunk_heights"]
    row = int(np.argmin(np.abs(heights - (m["shoulder"] - .052))))
    row = min(row, TRUNK_RINGS - 7)
    for side, first in (("l", 8), ("r", 30)):
        _build_arm(shell, gender, sk, side, trunk, (row, row + 5),
                   (first, first + 6))
    shell.emit(trunk)
    trunk_top = [int(v) for v in trunk.ids[-1]]
    head_bottom = [int(v) for v in head.ids[0]]
    stitch_loops(shell, trunk_top, np.arange(TRUNK_COLUMNS) / TRUNK_COLUMNS,
                 head_bottom, np.arange(HEAD_COLUMNS) / HEAD_COLUMNS)
    shell.emit(head)
    shell.fan([int(v) for v in head.ids[-1]], parts["apex"])
    _fork_legs(shell, gender, sk, [int(v) for v in trunk.ids[0]])
    return shell


def _foot_features(gender: str, sk: Skeleton) -> list:
    """The heel, the arch and the ball, added after the foot has been swept.

    Sweeping a ring along a curve cannot put a heel behind the ankle -- the
    heel is not on the path -- so it is relief, like a brow ridge.
    """
    out = []
    for side in ("l", "r"):
        ankle = sk.world[f"foot_{side}"]
        ball = sk.world[f"ball_{side}"]
        out += [
            ((ankle[0], ankle[1] - .030, ankle[2] - .022),
             (.036, .034, .030), (0, -.35, -1), .030),
            ((ankle[0], ball[1] + .012, ankle[2] + .020),
             (.030, .020, .034), (0, 1, .2), -.008),
            ((ankle[0] * 1.18, ball[1] + .016, ball[2] - .006),
             (.020, .018, .030), (1, .1, 0), .006),
        ]
    return out


def finish_body(gender: str, sk: Skeleton, shell: Shell):
    """Relax the grafts, add the relief, then settle it once more.

    Order matters.  Relaxing first rounds the seams a graft leaves behind;
    sculpting afterwards puts the anatomy on a surface that is already smooth,
    so a brow ridge is a brow ridge rather than a brow ridge riding a crease.
    """
    points, tris, uv, region = shell.arrays()
    tris = face_the_right_way(points, tris)
    points = relax(points, tris, passes=5)
    features = body_features(gender) + _foot_features(gender, sk)
    points = _sculpt(points, vertex_normals(points, tris), features)
    points = relax(points, tris, passes=1, shrink=.30, inflate=-.32)
    # The sole is a plane, not the bottom of an ellipse.  Flattening it here
    # rather than in the sweep keeps the ring frames simple and lands every
    # race's foot on the same ground the leg chain was solved to.
    sole = GROUND_HEIGHT[gender] - .0250
    points[:, 1] = sole + .0035 * np.logaddexp(0., (points[:, 1] - sole) / .0035)
    return points, tris, uv, region


# ---------------------------------------------------------------------------
# UVs
#
# One 1024 atlas, five regions, each unwrapped cylindrically about the limb it
# belongs to.  The angular coordinate is folded rather than wrapped -- the
# left and right halves of a limb land on the same texels -- which removes the
# seam a wrapped ring always leaves down its back, at the price of a
# left-right symmetric skin.  The existing races' body texture is symmetric
# too, so nothing is lost that was there before.
# ---------------------------------------------------------------------------

UV_TILES = {
    "head": (.02, .48, .52, .99),
    "torso": (.52, .99, .52, .99),
    "leg": (.02, .48, .02, .50),
    "arm": (.52, .76, .02, .50),
    "hand": (.78, .99, .02, .50),
}


def _tent(turn: np.ndarray) -> np.ndarray:
    """Fold a full turn onto [0, 1], so the two sides share their texels."""
    folded = np.mod(turn, 1.)
    return np.where(folded <= .5, folded * 2., (1. - folded) * 2.)


def _place(tile: str, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    u0, u1, v0, v1 = UV_TILES[tile]
    return np.stack([u0 + (u1 - u0) * np.clip(u, 0., 1.),
                     1. - (v0 + (v1 - v0) * np.clip(v, 0., 1.))], axis=1)


# How hard the head's texels are crowded onto the face.  This is the same idea
# as the geometry's column warp and deliberately not the same number: the two
# only have to agree with each other, and the UV warp is applied at one
# strength everywhere on the head so a painted feature can be placed by
# inverting it once.
FACE_UV_WARP = .58


@lru_cache(maxsize=4)
def _face_warp_table(samples: int = 8192):
    turn = np.linspace(0., .5, samples)
    return turn, (2 * math.pi * turn
                  - FACE_UV_WARP * np.sin(2 * math.pi * turn)) / (2 * math.pi)


def _face_turn(turn: np.ndarray) -> np.ndarray:
    """Undo the crowding, so an angle round the head maps to its own texel."""
    reference, warped = _face_warp_table()
    return np.interp(np.abs(turn), warped, reference)


def head_uv(gender: str, y: float, degrees: float) -> tuple[float, float]:
    """Where a face landmark lands in the atlas, so it can be painted.

    Runs the same fold and the same warp the geometry's unwrap runs, so a lip
    painted at "twelve degrees round, at mouth height" lands on the lip.
    """
    collar = TRUNK_PROFILE[gender][14][0] + .004
    turn = float(_face_turn(np.array([abs(degrees) / 360.]))[0]) * 2.
    v = (y - collar) / (TRUNK_PROFILE[gender][-2][0] - collar)
    return tuple(_place("head", np.array([turn]), np.array([v]))[0])


def assign_uv(gender: str, sk: Skeleton, points: np.ndarray,
              region: list[str]) -> np.ndarray:
    """Unwrap each region about the limb axis it was swept around."""
    table = np.asarray(TRUNK_PROFILE[gender])
    tags = np.asarray(region)
    uv = np.zeros((len(points), 2))
    fork, collar, crown = table[0][0], table[14][0] + .004, table[-2][0]
    centre = np.interp(points[:, 1], table[:, 0], table[:, 3])
    turn = np.arctan2(points[:, 0], points[:, 2] - centre) / (2 * math.pi)
    for tag, low, high in (("torso", fork, collar), ("head", collar, crown)):
        pick = tags == tag
        folded = _tent(turn[pick])
        if tag == "head":
            folded = _face_turn(folded * .5) * 2.
        uv[pick] = _place(tag, folded, (points[pick, 1] - low) / (high - low))
    for side in ("l", "r"):
        shoulder = sk.world[f"upperarm_{side}"]
        wrist = sk.world[f"hand_{side}"]
        reach = abs(wrist[0] - shoulder[0])
        for tag, span in ((f"arm_{side}", "arm"), (f"hand_{side}", "hand")):
            pick = tags == tag
            if not pick.any():
                continue
            local = points[pick] - shoulder
            angle = np.arctan2(-local[:, 1] * (1 if side == "l" else -1),
                               local[:, 2]) / (2 * math.pi)
            along = np.abs(local[:, 0]) / reach
            uv[pick] = _place(span, _tent(angle),
                              along if span == "arm" else (along - 1.) / .55)
        hip = sk.world[f"thigh_{side}"]
        ankle = sk.world[f"foot_{side}"]
        pick = tags == f"leg_{side}"
        local = points[pick] - np.array([hip[0], 0., 0.])
        drop = np.clip((fork - points[pick, 1]) / (fork - ankle[1]), 0., 1.)
        angle = np.arctan2(local[:, 0] * (1 if side == "l" else -1),
                           local[:, 2] - ankle[2] * .3) / (2 * math.pi)
        toe = np.clip((points[pick, 2] - ankle[2] + .06)
                      / PROPORTIONS[gender].girth["foot"], 0., 1.)
        uv[pick] = _place("leg", _tent(angle),
                          np.where(points[pick, 1] > ankle[1],
                                   drop * .82, .82 + toe * .18))
    return uv


# Which bones a region's vertices may be bound to.  Restricting the set is
# what a distance solve cannot do on its own: a knuckle is closer to the
# neighbouring finger's bone than to its own for part of its circumference,
# and a wrist is closer to a rib than a shoulder is to an elbow.
def _bone_sets() -> dict:
    spine = ["pelvis", "spine_01", "spine_02", "spine_03", "neck_01"]
    sets = {
        "torso": spine + ["Head", "clavicle_l", "clavicle_r", "upperarm_l",
                          "upperarm_r", "thigh_l", "thigh_r"],
        "head": ["Head", "neck_01", "spine_03"],
    }
    for side in ("l", "r"):
        sets[f"arm_{side}"] = ["spine_03", f"clavicle_{side}",
                               f"upperarm_{side}", f"lowerarm_{side}",
                               f"hand_{side}"]
        sets[f"hand_{side}"] = [f"lowerarm_{side}", f"hand_{side}"] + [
            f"{finger}_{link:02d}_{side}" for finger in FINGERS
            for link in (1, 2, 3)]
        sets[f"leg_{side}"] = ["pelvis", f"thigh_{side}", f"calf_{side}",
                               f"foot_{side}", f"ball_{side}"]
    return sets


def _segment_distance(points: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    axis = b - a
    length = float(axis @ axis)
    if length < 1e-12:
        return np.linalg.norm(points - a, axis=1)
    along = np.clip(((points - a) @ axis) / length, 0., 1.)
    return np.linalg.norm(points - (a + along[:, None] * axis), axis=1)


def bind_weights(sk: Skeleton, points: np.ndarray, region: list[str],
                 falloff: float = 4.2):
    """Bind by distance to the bone segment, inside the region's own bone set.

    Four influences, normalised.  The falloff is high enough that a vertex in
    the middle of a limb is effectively rigid and low enough that a joint
    blends over a couple of centimetres, which is what keeps an elbow from
    creasing shut when the shared clips bend it.
    """
    names = sk.contract.names
    order = {name: index for index, name in enumerate(names)}
    sets = _bone_sets()
    joints = np.zeros((len(points), 4), dtype=np.uint16)
    weights = np.zeros((len(points), 4), dtype=np.float32)
    tags = np.asarray(region)
    for tag, bones in sets.items():
        pick = np.flatnonzero(tags == tag)
        if not len(pick):
            continue
        local = points[pick]
        distance = np.stack([_segment_distance(local, *sk.segment(bone))
                             for bone in bones], axis=1)
        score = 1. / np.maximum(distance, 1e-4) ** falloff
        width = min(4, len(bones))
        best = np.argsort(-score, axis=1)[:, :width]
        rows = np.arange(len(pick))[:, None]
        chosen = score[rows, best]
        chosen = chosen / chosen.sum(axis=1, keepdims=True)
        joints[np.ix_(pick, np.arange(width))] = np.asarray(
            [order[b] for b in bones], dtype=np.uint16)[best]
        weights[np.ix_(pick, np.arange(width))] = chosen
    return joints, weights


def eye_centre(gender: str, sign: int) -> tuple[np.ndarray, float]:
    """Where an eyeball sits, and how big it is.

    Placed against the socket the sculpt cut rather than against the skull, so
    the sphere sits in the hollow instead of floating in front of it or
    disappearing into the head when the face changes.
    """
    m = landmarks(gender)
    radius = .0122 if gender == "male" else .0114
    surface = _at(gender, m["eyes"], sign * 25.)
    normal = _out(gender, m["eyes"], sign * 25.)
    return surface - normal * (radius - .0058), radius


def build_eyes(gender: str, sk: Skeleton):
    """Two spheres, planar-mapped from the front so the iris paints flat."""
    shell = Shell()
    columns, rows = 18, 11
    for sign in (1, -1):
        centre, radius = eye_centre(gender, sign)
        rings = []
        for row in range(rows):
            polar = math.pi * (row + 1) / (rows + 1)
            ring = []
            for column in range(columns):
                azimuth = 2 * math.pi * column / columns
                point = centre + radius * np.array([
                    math.sin(polar) * math.sin(azimuth), math.cos(polar),
                    math.sin(polar) * math.cos(azimuth) * 1.06])
                ring.append(shell.vertex(point, "eye"))
            rings.append(ring)
        for index in range(rows - 1):
            shell.bridge(rings[index], rings[index + 1])
        shell.fan(list(reversed(rings[0])),
                  shell.vertex(centre + np.array([0., radius, 0.]), "eye"))
        shell.fan(rings[-1], shell.vertex(centre - np.array([0., radius, 0.]), "eye"))
    points, tris, _, region = shell.arrays()
    tris = face_the_right_way(points, tris)
    uv = np.zeros((len(points), 2))
    for sign in (1, -1):
        centre, radius = eye_centre(gender, sign)
        near = np.abs(points[:, 0] - centre[0]) < radius * 1.2
        uv[near, 0] = .5 + (points[near, 0] - centre[0]) / (2.6 * radius) * sign
        uv[near, 1] = .5 - (points[near, 1] - centre[1]) / (2.6 * radius)
    head = sk.contract.names.index("Head")
    joints = np.zeros((len(points), 4), dtype=np.uint16)
    joints[:, 0] = head
    weights = np.zeros((len(points), 4), dtype=np.float32)
    weights[:, 0] = 1.
    return points, tris, uv, joints, weights


def build_brows(gender: str, sk: Skeleton):
    """A lens swept along the brow ridge, arched over the eye.

    Authored as geometry rather than painted so it catches a light the way a
    hair card does; the wardrobe recolours it with the hair choice.
    """
    m = landmarks(gender)
    shell = Shell()
    stations = 13
    for sign in (1, -1):
        rings = []
        for index in range(stations):
            step = index / (stations - 1)
            degrees = sign * (9. + 30. * step)
            height = m["brow"] + .006 * math.sin(math.pi * step) - .003 * step
            centre = _at(gender, height, degrees)
            normal = _out(gender, height, degrees)
            centre = centre + normal * .0035
            thickness = (.0030 if gender == "male" else .0024) * (
                .45 + .55 * math.sin(math.pi * min(1., step * 1.15)))
            depth = .0060 * (.5 + .5 * math.sin(math.pi * step))
            along = np.array([math.cos(math.radians(degrees)) * sign, 0.,
                              -math.sin(math.radians(degrees)) * sign])
            up = np.cross(normal, along)
            ring = []
            for column in range(6):
                angle = 2 * math.pi * column / 6
                ring.append(shell.vertex(
                    centre + up * (depth * math.cos(angle))
                    + normal * (thickness * math.sin(angle)), "brow"))
            rings.append(ring)
        for index in range(stations - 1):
            shell.bridge(rings[index], rings[index + 1])
        first = np.stack([shell.points[v] for v in rings[0]]).mean(axis=0)
        last = np.stack([shell.points[v] for v in rings[-1]]).mean(axis=0)
        shell.fan(list(reversed(rings[0])), shell.vertex(first, "brow"))
        shell.fan(rings[-1], shell.vertex(last, "brow"))
    points, tris, _, _ = shell.arrays()
    tris = face_the_right_way(points, tris)
    uv = np.zeros((len(points), 2))
    uv[:, 0] = np.clip(np.abs(points[:, 0]) / .07, 0., 1.) * .9 + .05
    uv[:, 1] = np.clip((points[:, 1] - m["brow"] + .008) / .016, 0., 1.)
    head = sk.contract.names.index("Head")
    joints = np.zeros((len(points), 4), dtype=np.uint16)
    joints[:, 0] = head
    weights = np.zeros((len(points), 4), dtype=np.float32)
    weights[:, 0] = 1.
    return points, tris, uv, joints, weights


# ---------------------------------------------------------------------------
# Textures
#
# Every map here is synthesised: value noise summed over octaves for the fine
# grain, painted ellipses for the features that have to land in a known place,
# and a height field differentiated into a normal map so the same relief
# drives the albedo and the lighting.  numpy and Pillow only, and no random
# state -- the lattice is a fixed integer hash, so two runs produce the same
# bytes.
# ---------------------------------------------------------------------------


def _hash_grid(size: int, seed: int) -> np.ndarray:
    """A deterministic value field on an integer lattice, in [0, 1)."""
    y, x = np.meshgrid(np.arange(size), np.arange(size), indexing="ij")
    value = (x.astype(np.uint64) * np.uint64(374761393)
             + y.astype(np.uint64) * np.uint64(668265263)
             + np.uint64(seed) * np.uint64(2246822519))
    value ^= value >> np.uint64(13)
    value = (value * np.uint64(1274126177)) & np.uint64(0xFFFFFFFF)
    return value.astype(np.float64) / float(1 << 32)


def value_noise(size: int, cells: int, seed: int) -> np.ndarray:
    grid = _hash_grid(cells + 1, seed)
    grid[-1] = grid[0]
    grid[:, -1] = grid[:, 0]
    step = np.linspace(0., cells, size, endpoint=False)
    low = np.floor(step).astype(int)
    frac = step - low
    smooth = frac * frac * (3 - 2 * frac)
    rows = grid[low] * (1 - smooth)[:, None] + grid[low + 1] * smooth[:, None]
    return rows[:, low] * (1 - smooth)[None, :] + rows[:, low + 1] * smooth[None, :]


def fractal(size: int, octaves, seed: int) -> np.ndarray:
    total = np.zeros((size, size))
    weight = 0.
    for index, cells in enumerate(octaves):
        gain = .5 ** index
        total += gain * value_noise(size, cells, seed + index * 977)
        weight += gain
    return total / weight


def blur(field: np.ndarray, passes: int = 1) -> np.ndarray:
    """Separable [1 2 1] blur, wrapping.  Run before differentiating a height.

    Value noise carries the lattice it was built on, and a derivative finds it:
    an unblurred height field turns into a normal map that is a regular grid of
    dots, which reads as beading on a garment rather than as weave.
    """
    out = np.asarray(field, dtype=np.float64)
    for _ in range(passes):
        for axis in (0, 1):
            out = (np.roll(out, 1, axis=axis) + 2 * out
                   + np.roll(out, -1, axis=axis)) * .25
    return out


def normal_map(height: np.ndarray, strength: float = 1., smoothing: int = 1) -> np.ndarray:
    height = blur(height, smoothing)
    dx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * strength
    dy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * strength
    normal = np.stack([-dx, dy, np.ones_like(height)], axis=2)
    normal /= np.linalg.norm(normal, axis=2, keepdims=True)
    return normal * .5 + .5


def encode(array: np.ndarray) -> bytes:
    image = Image.fromarray(np.clip(array * 255., 0, 255).astype(np.uint8))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _blob(size: int, centre, radii, softness: float = .38) -> np.ndarray:
    """A soft ellipse in UV space, for painting a feature where it belongs."""
    y, x = np.meshgrid(np.linspace(0., 1., size), np.linspace(0., 1., size),
                       indexing="ij")
    distance = np.sqrt(((x - centre[0]) / max(radii[0], 1e-6)) ** 2
                       + ((y - centre[1]) / max(radii[1], 1e-6)) ** 2)
    return np.clip((1. - distance) / max(softness, 1e-3), 0., 1.)


SKIN = {"male": (225, 184, 155), "female": (231, 194, 167)}
LIP = {"male": (196, 130, 118), "female": (206, 128, 122)}
IRIS = (86, 128, 152)



def skin_maps(gender: str, size: int = 1024):
    """Albedo, normal and metallic-roughness for the body.

    The face is painted at coordinates read back out of the same unwrap the
    geometry uses, so a lip lands on the lip whichever way the head profile is
    later adjusted.  Everything else is grain: a broad mottle for blood
    colour, a fine one for pores, and a roughness break that makes the lips
    and the skin around the eye catch a light differently from a shin.
    """
    m = landmarks(gender)
    base = np.asarray(SKIN[gender], dtype=np.float64) / 255.
    mottle = fractal(size, (3, 7, 15), 11) - .5
    grain = fractal(size, (48, 110, 240), 29) - .5
    albedo = base[None, None, :] * (1. + .085 * mottle[..., None]
                                    + .030 * grain[..., None])
    albedo = albedo + np.array([.030, -.012, -.020])[None, None, :] * np.clip(
        mottle * 2.2, 0., 1.)[..., None]
    height = grain * .5 + (fractal(size, (18, 40), 43) - .5) * .18
    rough = .60 + .10 * mottle + .05 * grain

    def paint(mask, colour, mix, roughness=None, relief=0.):
        nonlocal albedo, rough, height
        blend = (mask * mix)[..., None]
        albedo = albedo * (1. - blend) + np.asarray(colour, float)[None, None, :] * blend
        if roughness is not None:
            rough = rough * (1. - mask * mix) + roughness * (mask * mix)
        if relief:
            height = height + mask * relief

    lip = np.asarray(LIP[gender], dtype=np.float64) / 255.

    def band(height, inner, outer):
        """A face feature's extent in the atlas, from the angles it spans."""
        a = head_uv(gender, height, inner)[0]
        b = head_uv(gender, height, outer)[0]
        return (a + b) * .5, abs(b - a) * .5

    def rows(height, span):
        base = head_uv(gender, height, 0.)[1]
        return base, abs(head_uv(gender, height + span, 0.)[1] - base)

    def feature(height, inner, outer, span, colour, mix, roughness=None,
                relief=0., softness=.4, drop=0.):
        u, wide = band(height, inner, outer)
        v, tall = rows(height, span)
        paint(_blob(size, (u, v + drop), (wide, tall), softness), colour, mix,
              roughness, relief)

    # brow, socket, lash line, lower lid
    feature(m["brow"] - .004, 11, 38, .008, (.46, .34, .26),
            .30 if gender == "male" else .22, softness=.55)
    feature(m["eyes"] + .005, 12, 38, .012, (.66, .49, .44), .34, softness=.6)
    feature(m["eyes"] + .002, 13, 36, .0024, (.24, .17, .15), .85,
            roughness=.40, relief=-.25, softness=.30)
    feature(m["eyes"] - .008, 14, 34, .0042, (.84, .62, .56), .30, softness=.5)
    # the sides of the nose, and the nostrils
    feature(m["nose"] + .013, 4, 15, .018, (.82, .62, .54), .22, softness=.7)
    feature(m["nose"] - .005, 7, 16, .0040, (.36, .24, .21), .58,
            roughness=.62, relief=-.30, softness=.35)
    # the two lips, the line between them, and the shadow under the lower one
    feature(m["mouth"] + .006, 0, 20, .0055, lip, .88, roughness=.32,
            relief=.06, softness=.34)
    feature(m["mouth"] - .009, 0, 18, .0062, lip * 1.04, .88, roughness=.30,
            relief=.08, softness=.34)
    feature(m["mouth"] - .001, 0, 21, .0018, lip * .42, .85, relief=-.35,
            softness=.28)
    feature(m["mouth"] - .017, 0, 15, .0045, (.78, .56, .50), .30, softness=.55)
    feature(m["eyes"] - .033, 28, 52, .024, (.94, .63, .56), .15, softness=.75)
    # the two shadows a face reads depth from: under the jaw, and the temples
    feature(m["chin"] - .004, 0, 62, .020, (.70, .53, .48), .26, softness=.85)
    feature(m["eyes"] + .004, 46, 78, .052, (.76, .58, .53), .14, softness=.9)
    if gender == "male":
        feature(m["mouth"] - .026, 0, 44, .030, (.66, .60, .58), .11, softness=.9)
    # the torso tile: a sternum shadow and two areolae
    tile = UV_TILES["torso"]
    chest_v = 1. - (tile[2] + (tile[3] - tile[2])
                    * (m["chest"] + .030 - TRUNK_PROFILE[gender][0][0])
                    / (TRUNK_PROFILE[gender][14][0] + .004 - TRUNK_PROFILE[gender][0][0]))
    for offset in (.030, -.030):
        paint(_blob(size, (tile[0] + (tile[1] - tile[0]) * (.11 + offset), chest_v),
                    (.011, .009), .6), (.78, .50, .46), .55)
    mr = np.stack([np.zeros((size, size)), np.clip(rough, .05, 1.),
                   np.zeros((size, size))], axis=2)
    return (encode(np.clip(albedo, 0., 1.)),
            encode(normal_map(height, 3.4, smoothing=2)), encode(mr))


def eye_maps(size: int = 256):
    """Sclera, limbal ring, striated iris and pupil, on the planar eye unwrap."""
    y, x = np.meshgrid(np.linspace(-1., 1., size), np.linspace(-1., 1., size),
                       indexing="ij")
    radius = np.sqrt(x * x + y * y) / .77
    angle = np.arctan2(y, x)
    veins = fractal(size, (7, 17, 40), 61) - .5
    albedo = np.ones((size, size, 3)) * np.array([.88, .87, .855])
    albedo += np.array([.10, -.03, -.03]) * np.clip(veins * 2.4, 0., 1.)[..., None]
    iris = np.asarray(IRIS, dtype=np.float64) / 255.
    strands = .5 + .5 * np.cos(angle * 34.) * np.clip(1.6 - radius * 2.9, 0., 1.)
    fibre = iris[None, None, :] * (.72 + .48 * strands[..., None])
    ring = np.clip((.50 - radius) / .07, 0., 1.)
    albedo = albedo * (1 - ring[..., None]) + fibre * ring[..., None]
    limbus = np.clip(1. - np.abs(radius - .50) / .055, 0., 1.)
    albedo *= 1. - .55 * limbus[..., None]
    pupil = np.clip((.20 - radius) / .045, 0., 1.)
    albedo *= 1. - .96 * pupil[..., None]
    rough = .16 + .10 * np.clip(radius - .50, 0., 1.)
    height = (.5 - .5 * np.clip((.50 - radius) / .10, 0., 1.)) + .04 * strands
    mr = np.stack([np.zeros((size, size)), rough, np.zeros((size, size))], axis=2)
    return (encode(np.clip(albedo, 0., 1.)), encode(normal_map(height, 1.4)),
            encode(mr))


def brow_maps(size: int = 128):
    """A neutral strand card: the client tints it with the hair choice."""
    y, x = np.meshgrid(np.linspace(0., 1., size), np.linspace(0., 1., size),
                       indexing="ij")
    strands = .5 + .5 * np.cos((x * 26. + (y - .5) * 5.) * 2 * math.pi)
    grain = fractal(size, (10, 28), 73) - .5
    value = .80 + .16 * strands + .10 * grain
    albedo = np.dstack([value, value * .985, value * .96])
    mr = np.stack([np.zeros((size, size)),
                   np.clip(.68 - .18 * strands, .05, 1.),
                   np.zeros((size, size))], axis=2)
    return (encode(np.clip(albedo, 0., 1.)),
            encode(normal_map(strands * .16 + grain * .1, 2.2)), encode(mr))


def fabric_maps(kind: str, size: int = 512):
    """Cloth, leather and metal trim, each answering a light differently."""
    y, x = np.meshgrid(np.linspace(0., 1., size), np.linspace(0., 1., size),
                       indexing="ij")
    # Deliberately coarse octaves.  Finer grain reads as fabric on a texture
    # sheet and as moire on a body, because the finest octave lands below one
    # pixel at the size an actor is actually seen at.
    grain = fractal(size, (5, 12, 26), {"cloth": 101, "leather": 137,
                                        "trim": 173}[kind])
    if kind == "cloth":
        weave = (.5 + .5 * np.cos(x * 2 * math.pi * 86.)) * \
                (.5 + .5 * np.cos(y * 2 * math.pi * 86.))
        height = weave * .55 + grain * .45
        value = .82 + .20 * height
        rough = .90 - .12 * weave
        metal = np.zeros((size, size))
        strength = 2.6
    elif kind == "leather":
        cell = fractal(size, (7, 16, 34), 149)
        height = np.clip((cell - .48) * 2.6, -.5, .5) * .55 + grain * .35
        value = .91 + .09 * (grain + height * .4)
        rough = .74 - .14 * height
        metal = np.zeros((size, size))
        strength = 2.4
    else:
        braid = .5 + .5 * np.cos((x * 7. + y * 7.) * 2 * math.pi)
        height = braid * .5 + grain * .5
        value = .84 + .18 * height
        rough = .34 + .20 * grain
        metal = np.full((size, size), .82)
        strength = 2.2
    albedo = np.dstack([value, value, value])
    mr = np.stack([np.zeros((size, size)), np.clip(rough, .05, 1.), metal], axis=2)
    return (encode(np.clip(albedo, 0., 1.)),
            encode(normal_map(height, strength, smoothing=4)), encode(mr))


# ---------------------------------------------------------------------------
# The default wardrobe
#
# Cut out of the body's own faces and lifted along its normals, so a garment
# is the shape of the wearer rather than a shell hung near it, and it carries
# the body's skin weights unchanged -- it follows all sixty-five joints
# instead of swinging off one.  The cuts follow the concept sheets: a rolled
# three-quarter sleeve, an open collar with a placket, high-waisted trousers
# over a belt, and a short buckled boot.
# ---------------------------------------------------------------------------

# How many times the fabric maps repeat across a garment's share of the body
# unwrap.  Higher reads as a finer weave until the weave falls below a pixel,
# at which point it turns into moire and the garment looks like scales.
WARDROBE_TILE = 1.9


def lift_scale(points: np.ndarray, normals: np.ndarray,
               tris: np.ndarray) -> np.ndarray:
    """How far a garment may be lifted off the skin at each vertex.

    Lifting a shell along its own normals folds it through itself wherever the
    body is concave: at the crotch the two inner thighs are pushed towards each
    other and the garment turns inside out, which renders as a hole.  A vertex
    whose neighbours sit outside its own tangent plane is in a pocket, and gets
    lifted less.
    """
    edges, degree = _adjacency(len(points), tris)
    summed = np.zeros_like(points)
    np.add.at(summed, edges[:, 0], points[edges[:, 1]])
    towards = np.einsum("ij,ij->i", summed / degree[:, None] - points, normals)
    return np.clip(1. - towards / .009, .45, 1.)


def _subset(points, normals, uv, joints, weights, faces, mask, offset,
            tile: float = WARDROBE_TILE, lift=None):
    used = np.unique(faces[mask])
    if not len(used):
        return None
    remap = np.full(len(points), -1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    reach = offset if lift is None else offset * lift[used]
    return (points[used] + normals[used] * np.asarray(reach).reshape(-1, 1),
            normals[used], uv[used] * tile,
            remap[faces[mask]].astype(np.uint32), joints[used], weights[used])


def wardrobe_masks(gender: str, sk: Skeleton, points: np.ndarray,
                   region: list[str], faces: np.ndarray) -> dict:
    m = landmarks(gender)
    tags = np.asarray(region)
    centre = points[faces].mean(axis=1)
    y, x, z = centre[:, 1], np.abs(centre[:, 0]), centre[:, 2]
    kind = tags[faces[:, 0]]
    torso = kind == "torso"
    head = kind == "head"
    arm = np.isin(kind, ["arm_l", "arm_r"])
    leg = np.isin(kind, ["leg_l", "leg_r"])
    shoulder = sk.world["upperarm_l"][0]
    wrist = sk.world["hand_l"][0]
    ankle = sk.world["foot_l"][1]
    collar = TRUNK_PROFILE[gender][14][0] + .004
    sleeve = shoulder + (wrist - shoulder) * .62
    waist = m["waist"]
    front = _at(gender, m["chest"], 0.)[2]

    shirt = ((torso & (y > waist - .085) & (y < collar - .034))
             | (arm & (x < sleeve)))
    pants = ((torso & (y < waist + .052)) | (leg & (y > ankle + .092)))
    boots = leg & (y < ankle + .155)
    masks = {"shirt": shirt, "pants": pants, "boots": boots}
    # trim: the three edges a shirt actually has, plus a belt and a boot cuff
    masks["shirt_trim"] = (
        (shirt & (y > collar - .056) & (y < collar - .032))
        | (arm & (x > sleeve - .034) & (x < sleeve))
        | (shirt & torso & (np.abs(centre[:, 0]) < .016) & (z > front * .55)
           & (y > waist + .060)))
    masks["pants_seam"] = torso & (y > waist + .006) & (y < waist + .050)
    masks["boots_trim"] = leg & (y > ankle + .100) & (y < ankle + .132)
    masks["head_band"] = head & (np.abs(y - (m["brow"] + .026)) < .009)
    masks["head_cap"] = head & (y > m["brow"] + .030)
    return masks


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

WARDROBE_COLOUR = {
    # Read off the sheets: unbleached linen, a teal indigo denim, oiled brown
    # leather, and the brass the buckles and stitching are picked out in.
    "shirt": (226, 218, 198), "pants": (62, 104, 114),
    "boots": (96, 64, 42), "trim": (198, 166, 96),
}


def _nodes_and_skin(glb, sk: Skeleton):
    """Lay the rig out as glTF nodes and return the skin index.

    The rest rotations are written straight from the contract rather than
    recovered from a matrix: they are the basis the shared clips' absolute
    rotation tracks are expressed in, and a quaternion that round-trips to a
    different sign is a different basis to a test that compares them.
    """
    glb.doc["nodes"].append({"name": "Armature"})
    armature = 0
    index_of: dict[str, int] = {}
    for name in sk.contract.names:
        node = {"name": name,
                "translation": [float(v) for v in sk.local[name]],
                "rotation": list(sk.contract.rotation[name])}
        glb.doc["nodes"].append(node)
        index_of[name] = len(glb.doc["nodes"]) - 1
        parent = sk.contract.parent[name]
        owner = armature if parent is None else index_of[parent]
        glb.doc["nodes"][owner].setdefault("children", []).append(index_of[name])
    world = np.stack([sk.matrix(name) for name in sk.contract.names])
    inverse = np.linalg.inv(world).transpose(0, 2, 1).reshape(-1, 16).astype("float32")
    glb.doc["skins"] = [{
        "name": "Armature",
        "joints": [index_of[name] for name in sk.contract.names],
        "inverseBindMatrices": glb.accessor(inverse, "MAT4"),
        "skeleton": index_of[sk.contract.names[0]]}]
    glb.doc["scenes"] = [{"nodes": [armature]}]
    glb.doc["scene"] = 0
    return armature


def build_human_player(glb_class, output: Path, gender: str, label: str = "Human") -> dict:
    """Author one Human rig, mesh, wardrobe and material set from nothing."""
    sk = build_skeleton(gender)
    body_points, faces, _, region = finish_body(gender, sk, build_body(gender, sk))
    head_shift = seat_head(sk, body_points, region)
    normals = vertex_normals(body_points, faces)
    body_uv = assign_uv(gender, sk, body_points, region)
    body_joints, body_weights = bind_weights(sk, body_points, region)

    glb = glb_class(generator="Eloria human race builder (from scratch)")
    armature = _nodes_and_skin(glb, sk)

    skin_albedo, skin_normal, skin_mr = skin_maps(gender)
    eye_albedo, eye_normal, eye_mr = eye_maps()
    brow_albedo, brow_normal, brow_mr = brow_maps()
    fabric = {kind: fabric_maps(kind) for kind in ("cloth", "leather", "trim")}
    materials = {
        "eyebrows": glb.material(
            f"{label} Eyebrows", (255, 255, 255), roughness=1.,
            texture_png=brow_albedo, normal_png=brow_normal,
            metallic_roughness_png=brow_mr, double_sided=True),
        "eyes": glb.material(
            f"{label} Eyes", (255, 255, 255), metallic=1., roughness=1.,
            texture_png=eye_albedo, normal_png=eye_normal,
            metallic_roughness_png=eye_mr, double_sided=True),
        "body": glb.material(
            f"{label} Body", (255, 255, 255), metallic=1., roughness=1.,
            texture_png=skin_albedo, normal_png=skin_normal,
            metallic_roughness_png=skin_mr, double_sided=True),
    }
    for part, kind in (("shirt", "cloth"), ("pants", "cloth"),
                       ("boots", "leather"), ("headwear", "cloth")):
        colour = WARDROBE_COLOUR.get(part, WARDROBE_COLOUR["shirt"])
        albedo, normal, mr = fabric[kind]
        materials[part] = glb.material(
            f"{label} {part.title()}", colour, metallic=1., roughness=1.,
            texture_png=albedo, normal_png=normal, metallic_roughness_png=mr)
    trim_albedo, trim_normal, trim_mr = fabric["trim"]
    for part, colour in (("shirt_trim", WARDROBE_COLOUR["trim"]),
                         ("pants_seam", WARDROBE_COLOUR["boots"]),
                         ("boots_trim", WARDROBE_COLOUR["trim"]),
                         ("headwear_trim", WARDROBE_COLOUR["trim"])):
        name = f"{label} {part.replace('_', ' ').title()}"
        materials[part] = glb.material(
            name, colour, metallic=1., roughness=1., texture_png=trim_albedo,
            normal_png=trim_normal, metallic_roughness_png=trim_mr)

    vertices = triangles = 0

    def add(name: str, points, mesh_normals, uv, indices, joints, weights,
            material: int) -> None:
        nonlocal vertices, triangles
        primitive = glb.primitive(points, mesh_normals, uv, indices, material,
                                  joints=joints, weights=weights)
        glb.mesh_node(name, [primitive], skin=0, parent=armature)
        vertices += len(points)
        triangles += indices.size // 3

    brow_points, brow_faces, brow_uv, brow_joints, brow_weights = build_brows(gender, sk)
    add("Eyebrows", brow_points, vertex_normals(brow_points, brow_faces),
        brow_uv, brow_faces, brow_joints, brow_weights, materials["eyebrows"])
    eye_points, eye_faces, eye_uv, eye_joints, eye_weights = build_eyes(gender, sk)
    add("Eyes", eye_points, vertex_normals(eye_points, eye_faces), eye_uv,
        eye_faces, eye_joints, eye_weights, materials["eyes"])
    add("Body", body_points, normals, body_uv, faces, body_joints,
        body_weights, materials["body"])

    masks = wardrobe_masks(gender, sk, body_points, region, faces)
    lift = lift_scale(body_points, normals, faces)
    pieces = (("Wardrobe_Shirt", "shirt", .008, "shirt"),
              ("Wardrobe_Shirt_Trim", "shirt_trim", .012, "shirt_trim"),
              ("Wardrobe_Pants", "pants", .009, "pants"),
              ("Wardrobe_Pants_Seam", "pants_seam", .014, "pants_seam"),
              ("Wardrobe_Boots", "boots", .013, "boots"),
              ("Wardrobe_Boots_Seam", "boots_trim", .017, "boots_trim"),
              ("Wardrobe_Head_Band", "head_band", .012, "headwear_trim"),
              ("Wardrobe_Head_Cap", "head_cap", .014, "headwear"))
    for name, mask, lift_amount, material in pieces:
        arrays = _subset(body_points, normals, body_uv, body_joints,
                         body_weights, faces, masks[mask], lift_amount,
                         lift=lift)
        if arrays is None:
            continue
        add(name, arrays[0], arrays[1], arrays[2], arrays[3], arrays[4],
            arrays[5], materials[material])

    glb.write(output)
    ground = min(float(sk.world[f"ball_leaf_{side}"][1]) for side in ("l", "r"))
    return {"vertices": vertices, "triangles": triangles,
            "joints": len(sk.contract.names), "feature": "none",
            "wardrobe": "skinned", "anatomy": "authored",
            "capeBones": len(CAPE_CHAINS) * CAPE_LINKS,
            "headSeat": [round(float(value), 5) for value in head_shift],
            "baseBody": "human-scratch",
            "stature": STATURE,
            "legChainScale": round(sk.leg_scale, 4),
            "hipHeight": round(float(sk.world["pelvis"][1]), 5),
            "groundHeight": round(ground, 5)}

from __future__ import annotations

"""Correct a hand that sits well off the wrist axis its own opposite hand
sits near, by rotating it (around the wrist) toward a shared, symmetric
target -- never by reflecting it, which would mirror the hand itself
(thumb on the wrong side) rather than just redirecting it.

The skeleton itself was already checked directly and rules out a rigging
explanation: every joint from spine_03 down to hand_l/r poses identically
(matching global bone transforms to 6 decimal places) between Orun Female
and Luminous Female, so the visibly bent arm is not a bone-rotation
difference at all. It is the mesh itself -- where the hand's own skinned
vertices sit relative to the wrist joint they are bound to -- left over
from however the source pose was corrected toward the shared rig's rest
pose during generation.

What is safe to conclude without an external "this is the one correct
hand angle" assumption: a body's own left and right hand should sit
roughly mirror-symmetric relative to their own wrists, the way the
character was presumably designed, and Luminous's own two sides do
(measured asymmetry 0.002-0.006 m, essentially noise) while a handful of
bodies do not. Checked directly across all 16 bodies (mirroring the
right side's own offset and comparing it to the left), fourteen sit
under 0.04 m -- plausibly just generation noise, since Luminous herself
is not perfectly at zero -- and two are dramatic outliers: Orun Female
at 0.081 m, matching a visibly bent arm in render, and Mycelari Female at
0.087 m. Mycelari Female is excluded here on inspection: her own
lowerarm_r has ZERO vertices for which it is the dominant skin weight
(upperarm_r's own weighting extends unusually far down her arm and wins
everywhere instead) -- a weight-painting defect, not a pose one, and
rotating hand-dominant vertices around a wrist joint that mesh never
faithfully hinges from would not fix it. That needs the rigging pipeline
itself re-examined, not a post-hoc rotation.

The fix rotates each flagged side's hand (and its whole finger chain --
fingers have their own bones, so "hand_l" alone misses them) toward the
MIDPOINT of this body's own two sides, mirrored -- not toward an
external reference like Luminous's own hand angle, which could easily
differ between body types for legitimate reasons having nothing to do
with this bug. Only the DIRECTION changes; each side's own current
distance from its wrist is preserved exactly, so this cannot make a
hand reach further or shrink it -- only re-aim it.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from split_race_surfaces import (  # noqa: E402
    CLASSES, RACES, accessor_array, overwrite_accessor,
    resmooth_shared_surfaces, read_glb, write_glb,
)

# Below this, a body's own left/right hand-offset asymmetry is treated as
# ordinary generation noise (Luminous's own two sides measure 0.002-0.006 m
# apart) rather than a real bend worth correcting.
ASYMMETRY_THRESHOLD = 0.06

SIDES = ("l", "r")
MIRROR = np.array([-1.0, 1.0, 1.0])


def bone_rest_position(document, binary, skin_index: int, joint_name: str) -> np.ndarray:
    skin = document["skins"][skin_index]
    names = [document["nodes"][j].get("name", "") for j in skin["joints"]]
    ibms = accessor_array(document, binary, skin["inverseBindMatrices"])
    row = names.index(joint_name)
    ibm = np.asarray(ibms[row], dtype=np.float64).reshape(4, 4).T
    return np.linalg.inv(ibm)[:3, 3]


def build_parent_map(document) -> dict:
    parent = {}
    for i, n in enumerate(document["nodes"]):
        for c in n.get("children", []):
            parent[c] = i
    return parent


def hand_chain_rows(document, skin_index: int, names: list, side: str) -> list:
    """Joint-row indices for hand_<side> and every finger bone beneath it
    (fingers have their own bones, so hand_l alone would leave them
    behind when the palm rotates)."""
    skin = document["skins"][skin_index]
    parent = build_parent_map(document)
    children_of = {}
    for c, p in parent.items():
        children_of.setdefault(p, []).append(c)
    root_node = skin["joints"][names.index("hand_%s" % side)]
    out_nodes = set()
    stack = [root_node]
    while stack:
        n = stack.pop()
        out_nodes.add(n)
        stack.extend(children_of.get(n, []))
    return [i for i, j in enumerate(skin["joints"]) if j in out_nodes]


def shared_attributes(document, binary):
    nodes = [n for n in document["nodes"] if n.get("name") in CLASSES and "mesh" in n]
    prims = [document["meshes"][n["mesh"]]["primitives"][0] for n in nodes]
    pos_acc = prims[0]["attributes"]["POSITION"]
    joints_acc = prims[0]["attributes"]["JOINTS_0"]
    weights_acc = prims[0]["attributes"]["WEIGHTS_0"]
    assert all(p["attributes"]["POSITION"] == pos_acc for p in prims)
    assert all(p["attributes"]["JOINTS_0"] == joints_acc for p in prims)
    assert all(p["attributes"]["WEIGHTS_0"] == weights_acc for p in prims)
    skin_index = nodes[0]["skin"]
    assert all(n["skin"] == skin_index for n in nodes)
    return pos_acc, joints_acc, weights_acc, skin_index


def hand_offset(document, binary, positions, dominant, skin_index, names, side):
    rows = hand_chain_rows(document, skin_index, names, side)
    sel = np.isin(dominant, rows)
    hand_pos = bone_rest_position(document, binary, skin_index, "hand_%s" % side)
    if not sel.any():
        return None, hand_pos, sel
    offset = positions[sel].mean(axis=0) - hand_pos
    return offset, hand_pos, sel


def rotation_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Rotation matrix taking unit vector `a` to unit vector `b` (Rodrigues)."""
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    s = np.linalg.norm(v)
    if s < 1e-9:
        return np.eye(3) if c > 0 else -np.eye(3) + 2 * np.outer(a, a)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx * ((1 - c) / (s * s))


def process(path: Path) -> str:
    document, binary = read_glb(path)
    pos_acc, joints_acc, weights_acc, skin_index = shared_attributes(document, binary)
    positions = accessor_array(document, binary, pos_acc)
    joints = accessor_array(document, binary, joints_acc).astype(np.int64)
    weights = accessor_array(document, binary, weights_acc)
    dominant = joints[np.arange(len(joints)), np.argmax(weights, axis=1)]
    skin = document["skins"][skin_index]
    names = [document["nodes"][j].get("name", "") for j in skin["joints"]]

    # A hand rotates cleanly around the wrist only if the forearm actually
    # hinges from it -- checked directly, Mycelari Female's own lowerarm_r
    # has ZERO vertices for which it is the dominant weight (upperarm_r's
    # own weighting reaches unusually far down her arm and wins instead),
    # a weight-painting defect a wrist rotation would not fix. Comparing
    # each side's own lowerarm dominant count against the OTHER side's
    # (rather than some fixed minimum) catches exactly this without
    # needing to know what a "normal" count looks like across bodies.
    lowerarm_counts = {side: int((dominant == names.index("lowerarm_%s" % side)).sum())
                       for side in SIDES}
    if min(lowerarm_counts.values()) < 0.15 * max(lowerarm_counts.values()):
        return ("lowerarm dominant-weight counts %s look asymmetric enough to be "
                "a weight-painting issue, not a pose one -- skipped" % lowerarm_counts)

    offsets, hand_positions, sels = {}, {}, {}
    for side in SIDES:
        offset, hand_pos, sel = hand_offset(document, binary, positions, dominant,
                                            skin_index, names, side)
        offsets[side], hand_positions[side], sels[side] = offset, hand_pos, sel

    if offsets["l"] is None or offsets["r"] is None:
        return "no reliable hand measurement, skipped"

    mirrored_r = offsets["r"] * MIRROR
    asymmetry = float(np.linalg.norm(offsets["l"] - mirrored_r))
    if asymmetry < ASYMMETRY_THRESHOLD:
        return "left/right asymmetry %.4f m, within normal range" % asymmetry

    target_l = (offsets["l"] + mirrored_r) / 2.0
    target = {"l": target_l, "r": target_l * MIRROR}

    new_positions = positions.copy()
    report = []
    for side in SIDES:
        current = offsets[side]
        current_len = np.linalg.norm(current)
        target_dir = target[side]
        target_len = np.linalg.norm(target_dir)
        if current_len < 1e-6 or target_len < 1e-6:
            continue
        rot = rotation_matrix(current / current_len, target_dir / target_len)
        sel = sels[side]
        v = positions[sel] - hand_positions[side]
        new_positions[sel] = hand_positions[side] + v @ rot.T
        angle_deg = np.degrees(np.arccos(np.clip(
            (current / current_len) @ (target_dir / target_len), -1, 1)))
        report.append("%s=%.1f deg" % (side, angle_deg))

    overwrite_accessor(document, binary, pos_acc, new_positions)
    resmooth_shared_surfaces(document, binary)
    write_glb(path, document, binary)
    return "asymmetry %.4f m -> rotated %s" % (asymmetry, ", ".join(report))


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(
        description="symmetrize a hand that sits well off-axis from its own opposite hand")
    ap.add_argument("races", nargs="*",
                    help="race glb stems (without .glb); default: every *_redraw body")
    args = ap.parse_args()

    races = args.races or sorted(p.stem for p in RACES.glob("*_redraw.glb"))
    for race in races:
        print("%s:" % race, process(RACES / (race + ".glb")))
    return 0


if __name__ == "__main__":
    sys.exit(main())

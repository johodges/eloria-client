from __future__ import annotations

"""Canonicalize every race body's rest-pose ROTATIONS to match Luminous's own
(gender-matched), leaving translations -- where each body's own proportions
actually live -- untouched.

tests/test_native_glb_assets.py::test_race_rigs_keep_the_shared_animation_contract
already states the intended invariant: "Anatomy lives in the joint offsets,
never in rest rotations: glTF rotation tracks are absolute, so anything
stored in a rest rotation is overwritten the instant a clip plays." Checked
directly across all 16 bodies, every joint's rest rotation already matches
its gender-matched Luminous to a few parts in a million -- ordinary
export noise -- except one real difference: ball_l/ball_r (the toe joint)
on 5 of 7 male bodies is the exact NEGATION of Luminous's own quaternion.
A quaternion and its negation rotate identically (SO(3) double-covers as
a sign pair), so this was never actually a different pose; it is an
arbitrary sign an independent export run happened to pick, but it still
fails the shared-clips contract's plain component comparison, and a
retargeted clip that does not carry its own keyframe for that one joint
would show it.

Copying a joint's rotation from Luminous is not enough on its own: the
mesh is skinned against THIS body's own inverse bind matrix, computed
for its OWN original rest rotation, so swapping in a different rotation
without also updating the IBM would visibly swing whatever geometry is
weighted to that joint (hundreds of vertices on the foot, for ball_l/r)
to a new position. The fix instead keeps the mesh exactly where it
already renders: for every joint, find the NEW inverse bind matrix that
makes (new global transform) x (new IBM) equal (old global transform) x
(old IBM) -- the same rest-pose vertex position as before, achieved
through a different, now-canonical, rotation. Verified directly on
Votary Male's ball_l (the largest discrepancy found): the resulting
vertex position changes by ~1e-17, floating-point epsilon.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from split_race_surfaces import (  # noqa: E402
    CLASSES, RACES, accessor_array, append_accessor, read_glb, write_glb,
)


def quat_to_matrix(q) -> np.ndarray:
    x, y, z, w = q
    n = x * x + y * y + z * z + w * w
    if n < 1e-12:
        return np.eye(3)
    s = 2.0 / n
    xx, yy, zz = x * x * s, y * y * s, z * z * s
    xy, xz, yz = x * y * s, x * z * s, y * z * s
    wx, wy, wz = w * x * s, w * y * s, w * z * s
    return np.array([
        [1 - (yy + zz), xy - wz, xz + wy],
        [xy + wz, 1 - (xx + zz), yz - wx],
        [xz - wy, yz + wx, 1 - (xx + yy)],
    ])


def local_trs(node) -> np.ndarray:
    t = np.array(node.get("translation", [0.0, 0.0, 0.0]), dtype=np.float64)
    r = np.array(node.get("rotation", [0.0, 0.0, 0.0, 1.0]), dtype=np.float64)
    s = np.array(node.get("scale", [1.0, 1.0, 1.0]), dtype=np.float64)
    m = np.eye(4)
    m[:3, :3] = quat_to_matrix(r) * s[None, :]
    m[:3, 3] = t
    return m


def build_parent_map(document) -> dict:
    parent = {}
    for i, n in enumerate(document["nodes"]):
        for c in n.get("children", []):
            parent[c] = i
    return parent


def global_transforms(document, joints, parent_map, rotation_override=None) -> dict:
    """{joint_node_index: 4x4 world transform}, walking up to the true scene
    root regardless of how far above the skeleton's own 'root' joint that
    is -- any ancestor above it is presumed identity-free of a rotation
    override, so multiplying through it is harmless either way."""
    cache = {}

    def compute(node_idx):
        if node_idx in cache:
            return cache[node_idx]
        node = document["nodes"][node_idx]
        if rotation_override and node_idx in rotation_override:
            node = dict(node)
            node["rotation"] = rotation_override[node_idx]
        local = local_trs(node)
        parent_idx = parent_map.get(node_idx)
        g = local if parent_idx is None else compute(parent_idx) @ local
        cache[node_idx] = g
        return g

    for j in joints:
        compute(j)
    return cache


def gender_of(race: str) -> str:
    return "female" if "female" in race else "male"


def reference_rotations(gender: str) -> dict:
    document, _ = read_glb(RACES / ("luminous_%s.glb" % gender))
    skin = document["skins"][0]
    return {document["nodes"][j].get("name", ""): document["nodes"][j].get(
        "rotation", [0.0, 0.0, 0.0, 1.0]) for j in skin["joints"]}


def sync(path: Path, reference: dict) -> str:
    document, binary = read_glb(path)
    nodes = [n for n in document["nodes"] if n.get("name") in CLASSES and "mesh" in n]
    skin_index = nodes[0]["skin"]
    assert all(n["skin"] == skin_index for n in nodes)
    skin = document["skins"][skin_index]
    joints = skin["joints"]
    names = [document["nodes"][j].get("name", "") for j in joints]
    parent_map = build_parent_map(document)

    rotation_override = {}
    changed = []
    for row, j in enumerate(joints):
        name = names[row]
        if name not in reference:
            continue
        current = document["nodes"][j].get("rotation", [0.0, 0.0, 0.0, 1.0])
        target = reference[name]
        if max(abs(a - b) for a, b in zip(current, target)) > 1e-9:
            rotation_override[j] = target
            changed.append(name)
    if not changed:
        return "already matches Luminous's rest rotations"

    g_old = global_transforms(document, joints, parent_map)
    g_new = global_transforms(document, joints, parent_map, rotation_override)

    ibms = accessor_array(document, binary, skin["inverseBindMatrices"])
    ibm_old = [np.asarray(ibms[i], dtype=np.float64).reshape(4, 4).T
              for i in range(len(joints))]
    ibm_new = np.empty((len(joints), 4, 4), dtype=np.float32)
    for i, j in enumerate(joints):
        m = np.linalg.inv(g_new[j]) @ g_old[j] @ ibm_old[i]
        ibm_new[i] = m.T

    for j in changed:
        node_idx = joints[names.index(j)]
        document["nodes"][node_idx]["rotation"] = [float(v) for v in reference[j]]
    new_acc = append_accessor(document, binary, ibm_new, 5126, "MAT4")
    skin["inverseBindMatrices"] = new_acc
    write_glb(path, document, binary)
    return "synced rotation on: %s" % ", ".join(changed)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(
        description="canonicalize race-body rest rotations to Luminous's own")
    ap.add_argument("races", nargs="*",
                    help="race glb stems (without .glb); default: every *_redraw body")
    args = ap.parse_args()

    reference = {"male": reference_rotations("male"),
                "female": reference_rotations("female")}
    races = args.races or sorted(p.stem for p in RACES.glob("*_redraw.glb"))
    for race in races:
        print("%s:" % race, sync(RACES / (race + ".glb"), reference[gender_of(race)]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

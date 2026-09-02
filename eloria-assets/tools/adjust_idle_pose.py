#!/usr/bin/env python3
"""Relax the shared idle: separate the arms, close the stance, face the feet.

Added 2026-09-02 for Eloria Client.

The client rebuilds every actor's clips at runtime from
``Universal_Animation_Library.glb``, copying keys by bone name onto a rig whose
bind pose *is* the library's ``Rest_Pose`` -- so the one place to change how
every humanoid stands at idle is the library's ``Idle_Subtle`` clip itself.
Three things were off once the generated armour went on:

  * the arms hung close enough to the torso that a fitted sleeve overlapped it,
  * the stance was a wide 31 cm at the ankles, and
  * the right foot splayed 45 degrees off forward.

This nudges exactly the six rotation channels responsible -- ``upperarm_l/r``,
``thigh_l/r``, ``foot_l/r`` -- and nothing else in the 162-clip library.  Each
of those channels owns a private output accessor (verified: referenced once,
its own bufferView), so every keyframe's quaternion is rewritten in place at
the same float32 VEC4 layout; no other clip, bone, or byte moves.

The targets are ABSOLUTE, measured by forward-kinematics on the luminous_male
rig, so the tool is idempotent: a second run measures the pose already at
target and writes the same values back.  The corrections are applied as a
world-space rotation conjugated into each bone's own frame
(``delta = G^-1 . R_world . G``), which is why a chained splay -- the foot
turned partly by the thigh and partly by the ankle -- lands facing forward
whichever joints set it.

  python adjust_idle_pose.py            adjust the library in place
  python adjust_idle_pose.py --dry-run  measure and report, write nothing
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CLIENT = HERE.parent.parent / "godot-client"
LIBRARY = CLIENT / "assets/actors/native/shared/Universal_Animation_Library.glb"
BODY = CLIENT / "assets/actors/native/races/luminous_male.glb"
CLIP = "Idle_Subtle"

#: The relaxed idle, as forward-kinematic measurements on the luminous_male
#: rig.  Arm drop is the upper arm's angle below horizontal (bigger = closer
#: to the side); the wide authored idle sat at 74, and 66 clears a fitted
#: sleeve while still reading as arms-at-rest.  The shoulder target is the
#: upper-arm joint's forward position: the authored idle holds it 4.6 cm
#: behind the body's centre line, which reads as a puffed chest with the arms
#: hanging behind the torso, so the clavicles protract until the joint sits
#: near the centre line.  The legs are not given a stance target but
#: straightened segment by segment -- the authored clip bows the right leg,
#: knee swung 4 cm out and ankle kicked 10 cm back in -- so the knee lands
#: under the hip and the ankle under the knee, in the frontal plane only (the
#: sagittal crouch is the clip's own and stays).  Feet face straight forward.
TARGET_ARM_DROP = 66.0
TARGET_SHOULDER_FORWARD = -0.045
SAMPLE_AT = 0.1


# --------------------------------------------------------------------------
# Minimal GLB read / in-place patch (numpy only, matching the asset tools)
# --------------------------------------------------------------------------
def read_glb(path: Path):
    data = bytearray(path.read_bytes())
    assert data[:4] == b"glTF", path
    length = struct.unpack_from("<I", data, 8)[0]
    off, js, bin_off, bin_len = 12, None, None, None
    while off < length:
        clen, ctype = struct.unpack_from("<I4s", data, off)
        body = data[off + 8:off + 8 + clen]
        if ctype == b"JSON":
            js = json.loads(bytes(body).decode("utf-8"))
        elif ctype == b"BIN\x00":
            bin_off, bin_len = off + 8, clen
        off += 8 + clen
    return data, js, bin_off, bin_len


def accessor_floats(js, data, bin_off, index) -> np.ndarray:
    acc = js["accessors"][index]
    bv = js["bufferViews"][acc["bufferView"]]
    ncomp = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[acc["type"]]
    assert acc["componentType"] == 5126, "expected float32"
    base = bin_off + bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride", 4 * ncomp)
    out = np.empty((acc["count"], ncomp), dtype=np.float64)
    for i in range(acc["count"]):
        out[i] = struct.unpack_from("<" + "f" * ncomp, data, base + i * stride)
    return out, base, stride, ncomp


def write_floats(data, base, stride, ncomp, values) -> None:
    for i, row in enumerate(values):
        struct.pack_into("<" + "f" * ncomp, data, base + i * stride,
                         *[float(v) for v in row])


# --------------------------------------------------------------------------
# Quaternion / kinematics helpers
# --------------------------------------------------------------------------
def quat_to_mat(q):
    x, y, z, w = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def mat_to_quat(m):
    t = np.trace(m)
    if t > 0:
        s = np.sqrt(t + 1) * 2
        q = [(m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s,
             (m[1, 0] - m[0, 1]) / s, 0.25 * s]
    else:
        i = int(np.argmax([m[0, 0], m[1, 1], m[2, 2]]))
        if i == 0:
            s = np.sqrt(1 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
            q = [0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s,
                 (m[2, 1] - m[1, 2]) / s]
        elif i == 1:
            s = np.sqrt(1 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
            q = [(m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s,
                 (m[0, 2] - m[2, 0]) / s]
        else:
            s = np.sqrt(1 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
            q = [(m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s,
                 (m[1, 0] - m[0, 1]) / s]
    q = np.array(q)
    return q / np.linalg.norm(q)


def axis_angle_quat(axis, degrees):
    axis = np.asarray(axis, dtype=np.float64)
    axis = axis / max(np.linalg.norm(axis), 1e-12)
    half = np.radians(degrees) / 2.0
    s = np.sin(half)
    return np.array([axis[0] * s, axis[1] * s, axis[2] * s, np.cos(half)])


def quat_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array([
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz])


def node_local(node):
    if "matrix" in node:
        return np.array(node["matrix"], dtype=np.float64).reshape(4, 4).T
    m = np.eye(4)
    m[:3, :3] = quat_to_mat(node.get("rotation", [0, 0, 0, 1])) @ np.diag(
        node.get("scale", [1, 1, 1]))
    m[:3, 3] = node.get("translation", [0, 0, 0])
    return m


class Skeleton:
    def __init__(self, path: Path):
        _, js, _, _ = read_glb(path)
        self.js = js
        nodes = js["nodes"]
        self.names = [n.get("name", "") for n in nodes]
        self.parent = [-1] * len(nodes)
        for i, n in enumerate(nodes):
            for c in n.get("children", []):
                self.parent[c] = i
        self.index = {name: i for i, name in enumerate(self.names)}

    def fk(self, local_rot: dict, deltas: dict) -> dict:
        glob = {}

        def local_of(j):
            name = self.names[j]
            node = self.js["nodes"][j]
            m = np.eye(4)
            if name in local_rot:
                q = local_rot[name]
                if name in deltas:
                    q = quat_mul(q, deltas[name])
                rot = quat_to_mat(q)
            else:
                rot = quat_to_mat(node.get("rotation", [0, 0, 0, 1]))
            m[:3, :3] = rot @ np.diag(node.get("scale", [1, 1, 1]))
            m[:3, 3] = node.get("translation", [0, 0, 0])
            return m

        def rec(j, parent):
            glob[j] = parent @ local_of(j)
            for c in self.js["nodes"][j].get("children", []):
                rec(c, glob[j])

        for r in [i for i, p in enumerate(self.parent) if p < 0]:
            rec(r, np.eye(4))
        return glob

    def origin(self, glob, name):
        return glob[self.index[name]][:3, 3]

    def world_delta(self, glob, bone, world_axis, degrees):
        g = glob[self.index[bone]][:3, :3]
        rw = quat_to_mat(axis_angle_quat(world_axis, degrees))
        return mat_to_quat(g.T @ rw @ g)


def sampled_idle(js, data, bin_off) -> tuple[dict, dict]:
    """Local rotation per bone at SAMPLE_AT, and the six target channels'
    (accessor, quats, base, stride, ncomp) for rewriting."""
    names = [n.get("name", "") for n in js["nodes"]]
    anim = next(a for a in js["animations"] if a.get("name") == CLIP)
    local, channels, dur = {}, {}, 0.0
    for ch in anim["channels"]:
        if ch["target"]["path"] != "rotation":
            continue
        sampler = anim["samplers"][ch["sampler"]]
        times, _, _, _ = accessor_floats(js, data, bin_off, sampler["input"])
        times = times[:, 0]
        quats, base, stride, ncomp = accessor_floats(
            js, data, bin_off, sampler["output"])
        dur = max(dur, times[-1])
        bone = names[ch["target"]["node"]]
        channels[bone] = (times, quats, base, stride, ncomp)
    t = None
    for bone, (times, quats, base, stride, ncomp) in channels.items():
        if t is None:
            t = times[-1] * SAMPLE_AT
        i = max(0, min(int(np.searchsorted(times, t, "right")) - 1,
                       len(times) - 1))
        if i + 1 < len(times) and times[i + 1] > times[i]:
            f = (t - times[i]) / (times[i + 1] - times[i])
            a, b = quats[i], quats[i + 1]
            if np.dot(a, b) < 0:
                b = -b
            q = a + (b - a) * f
            local[bone] = q / np.linalg.norm(q)
        else:
            local[bone] = quats[i]
    return local, channels


def solve_angle(measure, target, seed, lo, hi):
    """Bisection for a target on measure(angle).

    The bracket must stay inside the measure's monotone region -- a limb swung
    far enough wraps and the value climbs again, which would fool the sign
    check into clamping to the wrong end."""
    a, b = lo, hi
    fa, fb = measure(a) - target, measure(b) - target
    if fa * fb > 0:  # target outside the bracket; clamp to nearest end
        return a if abs(fa) < abs(fb) else b
    for _ in range(40):
        mid = (a + b) / 2.0
        fm = measure(mid) - target
        if abs(fm) < 1e-4:
            return mid
        if fa * fm <= 0:
            b, fb = mid, fm
        else:
            a, fa = mid, fm
    return (a + b) / 2.0


def measurements(sk: Skeleton, glob) -> dict:
    o = lambda n: sk.origin(glob, n)
    arm = o("lowerarm_l") - o("upperarm_l")
    fl, fr = o("ball_l") - o("foot_l"), o("ball_r") - o("foot_r")
    out = {
        "armDrop": float(np.degrees(np.arctan2(-arm[1], abs(arm[0])))),
        "chestTwist": float(np.degrees(np.arctan2(
            o("upperarm_l")[2] - o("upperarm_r")[2],
            o("upperarm_l")[0] - o("upperarm_r")[0]))),
        "shoulderZ": float((o("upperarm_l")[2] + o("upperarm_r")[2]) / 2.0),
        "ankleGap": float(abs(o("foot_l")[0] - o("foot_r")[0])),
        "footYawL": float(np.degrees(np.arctan2(fl[0], fl[2]))),
        "footYawR": float(np.degrees(np.arctan2(fr[0], fr[2]))),
    }
    for side in ("l", "r"):
        hip, knee, ankle = (o("thigh_" + side), o("calf_" + side),
                            o("foot_" + side))
        out["kneeDx" + side.upper()] = float(knee[0] - hip[0])
        out["ankleDx" + side.upper()] = float(ankle[0] - knee[0])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="relax the shared Idle_Subtle clip")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data, js, bin_off, _ = read_glb(LIBRARY)
    sk = Skeleton(BODY)
    local, channels = sampled_idle(js, data, bin_off)

    def report(tag, m):
        print("%s arm drop %.1f, chest twist %+.1f, shoulder z %+.3f, "
              "knee dx L%+.3f R%+.3f, ankle dx L%+.3f R%+.3f, ankle gap "
              "%.1f cm, foot yaw L %.1f R %.1f"
              % (tag, m["armDrop"], m["chestTwist"], m["shoulderZ"],
                 m["kneeDxL"], m["kneeDxR"], m["ankleDxL"], m["ankleDxR"],
                 m["ankleGap"] * 100, m["footYawL"], m["footYawR"]))
    report("before:", measurements(sk, sk.fk(local, {})))

    deltas: dict = {}
    # De-twist the chest first: the authored clip yaws the whole upper torso
    # about 18 degrees (left shoulder swung forward, right swung back), which
    # is most of why the right shoulder reads pulled behind.  spine_03 turns
    # about world up until the shoulder line is square, and neck_01 counter-
    # turns by the same world rotation so the head keeps facing where it was
    # authored (the clavicles hang off spine_03, the neck subtree does not
    # need the twist).
    def chest_twist(angle):
        d = dict(deltas)
        g = sk.fk(local, {})
        d["spine_03"] = sk.world_delta(g, "spine_03", [0, 1, 0], angle)
        return measurements(sk, sk.fk(local, d))["chestTwist"]
    twist_angle = solve_angle(chest_twist, 0.0, 12.0, -4.0, 30.0)
    g = sk.fk(local, {})
    deltas["spine_03"] = sk.world_delta(g, "spine_03", [0, 1, 0], twist_angle)
    g = sk.fk(local, deltas)
    deltas["neck_01"] = sk.world_delta(g, "neck_01", [0, 1, 0], -twist_angle)

    # Shoulders forward: each clavicle protracts (a yaw about world up -- the
    # clavicle runs along x, so a pitch about x would spin it in place) until
    # its own upper-arm joint reaches the target forward position.  Per side,
    # because a residual asymmetry survives the de-twist.
    clav_angles = {}
    for side, sign in (("l", -1.0), ("r", 1.0)):
        def one_shoulder(angle, side=side, sign=sign):
            d = dict(deltas)
            g = sk.fk(local, deltas)
            d["clavicle_" + side] = sk.world_delta(
                g, "clavicle_" + side, [0, 1, 0], sign * angle)
            return float(sk.origin(sk.fk(local, d),
                                   "upperarm_" + side)[2])
        clav_angles[side] = solve_angle(one_shoulder, TARGET_SHOULDER_FORWARD,
                                        8.0, -16.0, 32.0)
        g = sk.fk(local, deltas)
        deltas["clavicle_" + side] = sk.world_delta(
            g, "clavicle_" + side, [0, 1, 0], sign * clav_angles[side])

    # Arms: abduct both about world forward (+Z) until the drop hits target,
    # measured with the clavicles already forward.
    def arm_drop(angle):
        d = dict(deltas)
        g = sk.fk(local, deltas)
        d["upperarm_l"] = sk.world_delta(g, "upperarm_l", [0, 0, 1], angle)
        d["upperarm_r"] = sk.world_delta(g, "upperarm_r", [0, 0, 1], -angle)
        return measurements(sk, sk.fk(local, d))["armDrop"]
    arm_angle = solve_angle(arm_drop, TARGET_ARM_DROP, 8.0, -6.0, 20.0)
    g = sk.fk(local, deltas)
    deltas["upperarm_l"] = sk.world_delta(g, "upperarm_l", [0, 0, 1], arm_angle)
    deltas["upperarm_r"] = sk.world_delta(g, "upperarm_r", [0, 0, 1], -arm_angle)

    # Legs: straightened segment by segment rather than steered to a stance
    # width.  The authored clip bows a leg -- knee swung outboard, ankle
    # kicked back in -- and no single hip rotation unbends that.  The thigh
    # turns about world forward until the knee is directly below the hip in
    # the frontal plane, then the calf until the ankle is below the knee; a
    # frontal turn leaves the sagittal crouch exactly as authored.  The
    # correction angle is closed-form: the segment's own frontal lean.
    for side in ("l", "r"):
        g = sk.fk(local, deltas)
        hip = sk.origin(g, "thigh_" + side)
        knee = sk.origin(g, "calf_" + side)
        lean = -np.degrees(np.arctan2(knee[0] - hip[0], -(knee[1] - hip[1])))
        deltas["thigh_" + side] = sk.world_delta(g, "thigh_" + side,
                                                 [0, 0, 1], lean)
        g = sk.fk(local, deltas)
        knee = sk.origin(g, "calf_" + side)
        ankle = sk.origin(g, "foot_" + side)
        lean = -np.degrees(np.arctan2(ankle[0] - knee[0], -(ankle[1] - knee[1])))
        deltas["calf_" + side] = sk.world_delta(g, "calf_" + side,
                                                [0, 0, 1], lean)

    # Feet: rotate each about world up to zero its residual yaw.
    g = sk.fk(local, deltas)
    now = measurements(sk, g)
    deltas["foot_l"] = sk.world_delta(g, "foot_l", [0, 1, 0], -now["footYawL"])
    deltas["foot_r"] = sk.world_delta(g, "foot_r", [0, 1, 0], -now["footYawR"])

    report("after: ", measurements(sk, sk.fk(local, deltas)))
    print("deltas: chest de-twist %.1f deg, clavicle L%.1f R%.1f deg, arm "
          "+/-%.1f deg, legs straightened, feet to forward"
          % (twist_angle, clav_angles["l"], clav_angles["r"], arm_angle))

    if args.dry_run:
        print("\nnothing written (--dry-run)")
        return 0

    # Rewrite every keyframe of each target channel: post-multiply by its
    # delta and pack back into the same float32 slots.
    for bone, delta in deltas.items():
        _, quats, base, stride, ncomp = channels[bone]
        adjusted = np.array([quat_mul(q, delta) for q in quats])
        adjusted /= np.linalg.norm(adjusted, axis=1, keepdims=True)
        write_floats(data, base, stride, ncomp, adjusted)
    LIBRARY.write_bytes(bytes(data))
    print("\nwrote %s (%d channels, %s only)" % (LIBRARY.name, len(deltas), CLIP))
    return 0


if __name__ == "__main__":
    sys.exit(main())

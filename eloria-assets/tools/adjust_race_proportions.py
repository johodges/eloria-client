"""Reshape a race's proportions by scaling skeleton joints in place.

The luminous bodies are built to realistic proportions -- a head 0.164 m
wide on a 1.82 m frame -- while the game's look calls for the classic
stylised read: a rounder, wider head on the same body.  Rather than
resculpting the mesh, the scale rides the JOINT: a rest scale on the Head
bone reaches everything that follows the bone -- the skinned head
vertices (blending smoothly into the neck through the existing skin
weights), the hair sockets, and the helm sockets -- so the mesh, the
hair and every already-built piece of headgear stay consistent without a
rebuild.  The animation library carries no scale tracks (the Head bone
has no tracks at all), so nothing at runtime overrides the rest value.

Targets are ABSOLUTE: the tool writes the scale, not a multiplier, so
running it twice is safe and re-tuning means editing the numbers below.

Usage:
    python adjust_race_proportions.py [--race luminous_male] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import struct
import sys

import numpy as np
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
CLIENT = TOOLS.parent.parent / "godot-client"
RACES = CLIENT / "assets" / "actors" / "native" / "races"

#: Absolute rest scale per joint.  The reference head is nearly round
#: (width about 0.95 of its height) where the authored head is a narrow
#: oval (0.65), so the width leads, the depth follows halfway, and the
#: height barely moves.
JOINT_SCALE = {
    "Head": (1.35, 1.10, 1.15),
}

#: Boxy torso: the authored chest is a 1.7x superhero V (0.56 m shoulder
#: line over a 0.32 m waist); the reference reads nearer 1.3x.  The edit
#: is one smooth displacement field baked into the mesh,
#:     dx = -sign(x) * min(|x|, anchor) * (1 - s(y)),
#: so the trunk narrows inside the shoulder-joint radius while everything
#: beyond it -- deltoids, the whole hanging arm -- slides inboard rigidly
#: (arm verts use the plateau factor whatever their height, or the field
#: would shear across the arm's own thickness).  s(y) ramps from 1 at the
#: ribs to the scale across the chest, holds through the shoulder band,
#: and fades back to 1 up the neck so the throat and face stay put.  The
#: shoulder joints ride the same field: their node translations move and
#: their inverse binds are rewritten to the new rest, which keeps the
#: authored vertex data exact at rest and every rotation-only clip
#: pivoting from the new, narrower shoulders.
TORSO_TAPER = {
    "scale": 0.82,
    "rampLo": 1.20, "rampHi": 1.42,
    "fadeLo": 1.50, "fadeHi": 1.62,
}
MOVED_ROOTS = ("clavicle_l", "clavicle_r")


def _matrices(document):
    nodes = document["nodes"]
    parent = {}
    for index, node in enumerate(nodes):
        for child in node.get("children", []):
            parent[child] = index

    def local(node):
        m = np.eye(4)
        if "matrix" in node:
            return np.array(node["matrix"], dtype=np.float64).reshape(4, 4).T
        t = node.get("translation", [0, 0, 0])
        r = node.get("rotation", [0, 0, 0, 1])
        s = node.get("scale", [1, 1, 1])
        x, y, z, w = r
        rot = np.array([
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ])
        m[:3, :3] = rot @ np.diag(s)
        m[:3, 3] = t
        return m

    globals_ = [None] * len(nodes)

    def resolve(i):
        if globals_[i] is None:
            loc = local(nodes[i])
            p = parent.get(i)
            globals_[i] = loc if p is None else resolve(p) @ loc
        return globals_[i]

    for i in range(len(nodes)):
        resolve(i)
    return globals_, parent


def _field_factory(spec):
    lo, hi = spec["rampLo"], spec["rampHi"]
    flo, fhi = spec["fadeLo"], spec["fadeHi"]
    top = spec["scale"]

    def s_of_y(y):
        if y <= lo:
            return 1.0
        if y <= hi:
            t = (y - lo) / (hi - lo)
            return 1.0 + (top - 1.0) * (3 * t * t - 2 * t * t * t)
        if y <= flo:
            return top
        if y <= fhi:
            t = (y - flo) / (fhi - flo)
            return top + (1.0 - top) * (3 * t * t - 2 * t * t * t)
        return 1.0

    def dx(x, y, anchor, plateau):
        reach = min(abs(x), anchor)
        factor = plateau if abs(x) >= anchor else s_of_y(y)
        return -np.sign(x) * reach * (1.0 - factor)

    return dx


def taper_torso(document, binary) -> bool:
    spec = TORSO_TAPER
    extras = document.setdefault("asset", {}).setdefault("extras", {})
    current = float(extras.get("eloriaTorsoTaper", 1.0))
    if abs(current - spec["scale"]) < 1e-6:
        print("torso taper already %.2f -- nothing to do" % current)
        return False
    if abs(current - 1.0) > 1e-6:
        print("torso taper is %.2f, target %.2f: restore the GLB from git "
              "first (taper edits do not compose)" % (current, spec["scale"]))
        raise SystemExit(1)

    # ``binary`` still carries its 8-byte chunk header (length + BIN tag);
    # accessor offsets are relative to the payload after it.  Forgetting
    # this once scrambled every shifted vertex: reads landed 8 bytes early,
    # so the field was computed from a neighbour's Y and written over it.
    bin_len, bin_tag = struct.unpack_from("<I4s", binary, 0)
    assert bin_tag[:3] == b"BIN", bin_tag
    payload = 8

    nodes = document["nodes"]
    names = [n.get("name", "") for n in nodes]
    globals_, parent = _matrices(document)
    anchor = None
    for i, n in enumerate(names):
        if n == "upperarm_l":
            anchor = abs(float(globals_[i][0, 3]))
    assert anchor and anchor > 0.05, "no upperarm_l joint"
    dx = _field_factory(spec)

    # Every skinned primitive's positions, each accessor exactly once.
    seen = set()
    moved_verts = 0
    for node in nodes:
        if "mesh" not in node or "skin" not in node:
            continue
        for prim in document["meshes"][node["mesh"]]["primitives"]:
            acc_index = prim["attributes"]["POSITION"]
            if acc_index in seen:
                continue
            seen.add(acc_index)
            acc = document["accessors"][acc_index]
            view = document["bufferViews"][acc["bufferView"]]
            offset = (payload + view.get("byteOffset", 0)
                      + acc.get("byteOffset", 0))
            stride = view.get("byteStride", 12)
            for v in range(acc["count"]):
                at = offset + v * stride
                x, y, z = struct.unpack_from("<3f", binary, at)
                shift = dx(x, y, anchor, spec["scale"])
                if shift:
                    struct.pack_into("<3f", binary, at, x + shift, y, z)
                    moved_verts += 1

    # The clavicle subtrees ride the same field: new globals from the
    # field, locals rebuilt top-down, inverse binds rewritten to the new
    # rest (they were exact inverses of the old one).
    index_of = {n: i for i, n in enumerate(names)}
    moved = []

    def collect(i):
        moved.append(i)
        for child in nodes[i].get("children", []):
            collect(child)

    for root in MOVED_ROOTS:
        collect(index_of[root])
    new_global_t = {}
    for i in moved:
        g = globals_[i]
        x, y = float(g[0, 3]), float(g[1, 3])
        new_global_t[i] = g[:3, 3] + np.array(
            [dx(x, y, anchor, spec["scale"]), 0.0, 0.0])
    for i in moved:
        p = parent.get(i)
        parent_g = globals_[p].copy() if p is not None else np.eye(4)
        if p in new_global_t:
            parent_g[:3, 3] = new_global_t[p]
        child_g = globals_[i].copy()
        child_g[:3, 3] = new_global_t[i]
        local_new = np.linalg.inv(parent_g) @ child_g
        nodes[i]["translation"] = [round(float(v), 6)
                                   for v in local_new[:3, 3]]

    for skin in document.get("skins", []):
        acc = document["accessors"][skin["inverseBindMatrices"]]
        view = document["bufferViews"][acc["bufferView"]]
        offset = (payload + view.get("byteOffset", 0)
                  + acc.get("byteOffset", 0))
        for row, joint in enumerate(skin["joints"]):
            if joint not in new_global_t:
                continue
            g = globals_[joint].copy()
            g[:3, 3] = new_global_t[joint]
            ibm = np.linalg.inv(g)
            struct.pack_into("<16f", binary, offset + row * 64,
                             *ibm.T.reshape(-1))

    extras["eloriaTorsoTaper"] = spec["scale"]
    print("torso taper %.2f: %d vertices shifted, %d joints moved"
          % (spec["scale"], moved_verts, len(moved)))
    return True


def main() -> int:
    ap = argparse.ArgumentParser(
        description="scale skeleton joints of a race GLB in place")
    ap.add_argument("--race", default="luminous_male")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    path = RACES / ("%s.glb" % args.race)
    data = path.read_bytes()
    assert data[:4] == b"glTF", path
    json_len, json_type = struct.unpack_from("<I4s", data, 12)
    assert json_type == b"JSON", "unexpected first chunk"
    document = json.loads(data[20:20 + json_len])
    binary = bytearray(data[20 + json_len:])

    changed = []
    for name, scale in JOINT_SCALE.items():
        nodes = [n for n in document["nodes"] if n.get("name") == name]
        if len(nodes) != 1:
            print("joint %r matched %d nodes -- skipped" % (name, len(nodes)))
            continue
        before = nodes[0].get("scale", [1.0, 1.0, 1.0])
        nodes[0]["scale"] = list(scale)
        changed.append((name, before, scale))
        print("%s scale %s -> %s" % (name, [round(v, 3) for v in before],
                                     list(scale)))

    tapered = False
    if not args.dry_run:
        tapered = taper_torso(document, binary)

    if args.dry_run:
        print("\nnothing written (--dry-run)")
        return 0
    if not changed and not tapered:
        print("nothing to change")
        return 1

    payload = json.dumps(document, separators=(",", ":")).encode()
    payload += b" " * (-len(payload) % 4)
    out = bytearray(b"glTF")
    out += struct.pack("<II", 2, 12 + 8 + len(payload) + len(binary))
    out += struct.pack("<I4s", len(payload), b"JSON")
    out += payload
    out += binary
    path.write_bytes(bytes(out))
    print("\nwrote %s (%d joints scaled)" % (path.name, len(changed)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

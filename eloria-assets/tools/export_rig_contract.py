#!/usr/bin/env python3
"""Export the shared player rig's *interface* to a checked-in contract file.

A race is free to author its own anatomy, but not its own animation contract.
The shared clip library in ``Universal_Animation_Library.glb`` writes absolute
rotation tracks keyed by joint name, so three things are fixed for every
playable race and are interface rather than content:

  * the joint names,
  * the order they appear in the skin, and the parent of each,
  * the rest *rotation* of each joint -- the basis a clip's absolute rotation
    is written against,
  * where the skull sits relative to the Head joint.  Hairstyles and headwear
    are authored in Head-local space against the reference skull, so a race
    that puts its own skull somewhere else relative to that joint wears a hat
    behind its forehead.  This is the same class of shared plane as the hip
    and ground heights, and it is measured rather than asserted.

Everything else about a skeleton -- every bone offset, which is to say all of
the anatomy -- belongs to the race.  This script writes the three interface
items to ``human_rig_contract.json`` so a from-scratch race can satisfy them
without opening another race's mesh.  It is run by hand when the shared rig
changes; the contract file is what the builders read.

    python3 eloria-assets/tools/export_rig_contract.py
"""
from __future__ import annotations

import json
from pathlib import Path
import struct

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RACES = ROOT / "godot-client/assets/actors/native/races"
OUTPUT = Path(__file__).resolve().parent / "human_rig_contract.json"


def read_glb(path: Path) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    size = struct.unpack_from("<II", raw, 12)[0]
    offset = 20 + size
    length = struct.unpack_from("<II", raw, offset)[0]
    return json.loads(raw[20:20 + size]), raw[offset + 8:offset + 8 + length]


def document(path: Path) -> dict:
    return read_glb(path)[0]


def quaternion_matrix(rotation) -> np.ndarray:
    x, y, z, w = rotation
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


#: The band of the skull a hairstyle actually sits on, in Head-local metres.
#: Measuring the whole head instead would measure the nose, and a race whose
#: nose projects differently would then seat its forehead wrongly.
SCALP_BAND = (.11, .26)


def head_envelope(path: Path) -> dict:
    """The reference scalp, measured in the frame a hairstyle is authored in."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_native_nymara_glbs import read_accessor

    doc, binary = read_glb(path)
    owner = {child: index for index, node in enumerate(doc["nodes"])
             for child in node.get("children", [])}

    def world(index: int) -> np.ndarray:
        node = doc["nodes"][index]
        matrix = np.eye(4)
        matrix[:3, :3] = quaternion_matrix(node.get("rotation", [0., 0., 0., 1.]))
        matrix[:3, 3] = node.get("translation", [0., 0., 0.])
        up = owner.get(index)
        return matrix if up is None else world(up) @ matrix

    joints = doc["skins"][0]["joints"]
    names = [doc["nodes"][j].get("name") for j in joints]
    head = world(joints[names.index("Head")])
    body = next(mesh for mesh in doc["meshes"] if mesh["name"] == "Body")
    points = read_accessor(
        doc, binary, body["primitives"][0]["attributes"]["POSITION"]).astype(float)
    local = (np.linalg.inv(head) @ np.c_[points, np.ones(len(points))].T).T[:, :3]
    low, high = SCALP_BAND
    scalp = local[(local[:, 1] > low) & (local[:, 1] < high)]
    return {"band": list(SCALP_BAND),
            "crown": round(float(local[:, 1].max()), 5),
            "front": round(float(scalp[:, 2].max()), 5),
            "back": round(float(scalp[:, 2].min()), 5),
            "halfWidth": round(float(np.abs(scalp[:, 0]).max()), 5)}


def main() -> None:
    contract = {
        "note": ("Interface only: joint names, order, parents and rest "
                 "rotations, which the shared animation library's absolute "
                 "rotation tracks are written against. Bone offsets are "
                 "anatomy and are deliberately absent."),
        "source": "godot-client/assets/actors/native/races/luminous_{gender}.glb",
        "generator": "eloria-assets/tools/export_rig_contract.py",
        "joints": [], "restRotations": {}, "headEnvelope": {},
    }
    for gender in ("female", "male"):
        doc = document(RACES / f"luminous_{gender}.glb")
        joints = doc["skins"][0]["joints"]
        names = [doc["nodes"][node].get("name", "") for node in joints]
        owner = {child: index for index, node in enumerate(doc["nodes"])
                 for child in node.get("children", [])}
        parents = []
        for node in joints:
            up = owner.get(node)
            parent = doc["nodes"][up].get("name") if up is not None else None
            # The armature node the root hangs off is scene furniture, not a
            # joint; the skin's root has no parent inside the skeleton.
            parents.append(parent if parent in names else None)
        if contract["joints"]:
            assert contract["joints"] == [{"name": n, "parent": p}
                                          for n, p in zip(names, parents)]
        else:
            contract["joints"] = [{"name": n, "parent": p}
                                  for n, p in zip(names, parents)]
        contract["restRotations"][gender] = {
            name: [round(float(v), 12) for v in
                   doc["nodes"][node].get("rotation", [0., 0., 0., 1.])]
            for name, node in zip(names, joints)}
        contract["headEnvelope"][gender] = head_envelope(
            RACES / f"luminous_{gender}.glb")
    OUTPUT.write_text(json.dumps(contract, indent=1) + "\n", encoding="utf-8")
    print(f"{OUTPUT.name}: {len(contract['joints'])} joints")


if __name__ == "__main__":
    main()

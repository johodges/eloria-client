#!/usr/bin/env python3
"""Export the shared player rig's *interface* to a checked-in contract file.

A race is free to author its own anatomy, but not its own animation contract.
The shared clip library in ``Universal_Animation_Library.glb`` writes absolute
rotation tracks keyed by joint name, so three things are fixed for every
playable race and are interface rather than content:

  * the joint names,
  * the order they appear in the skin, and the parent of each,
  * the rest *rotation* of each joint -- the basis a clip's absolute rotation
    is written against.

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

ROOT = Path(__file__).resolve().parents[2]
RACES = ROOT / "godot-client/assets/actors/native/races"
OUTPUT = Path(__file__).resolve().parent / "human_rig_contract.json"


def document(path: Path) -> dict:
    raw = path.read_bytes()
    size = struct.unpack_from("<II", raw, 12)[0]
    return json.loads(raw[20:20 + size])


def main() -> None:
    contract = {
        "note": ("Interface only: joint names, order, parents and rest "
                 "rotations, which the shared animation library's absolute "
                 "rotation tracks are written against. Bone offsets are "
                 "anatomy and are deliberately absent."),
        "source": "godot-client/assets/actors/native/races/luminous_{gender}.glb",
        "generator": "eloria-assets/tools/export_rig_contract.py",
        "joints": [], "restRotations": {},
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
    OUTPUT.write_text(json.dumps(contract, indent=1) + "\n", encoding="utf-8")
    print(f"{OUTPUT.name}: {len(contract['joints'])} joints")


if __name__ == "__main__":
    main()

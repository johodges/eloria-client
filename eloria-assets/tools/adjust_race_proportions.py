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
    binary = data[20 + json_len:]

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

    if args.dry_run:
        print("\nnothing written (--dry-run)")
        return 0
    if not changed:
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

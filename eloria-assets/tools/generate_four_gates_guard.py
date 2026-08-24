#!/usr/bin/env python3
"""Build the user-supplied Four Gates guard as an animated Cal3D player preset."""
from __future__ import annotations

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image

from generate_characters import BONES, animation, binary_mesh, write_cal

SOURCE = Path(__file__).parents[1] / "source/four-gates-guard"
BODY_UV_RECT = (79 / 128, 0, 1, 54 / 128)


def write_mesh(path: Path, positions, normals, uv, faces, bones, rect) -> None:
    used = np.unique(faces)
    remap = np.full(len(positions), -1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    local_faces = remap[faces]
    u0, v0, u1, v1 = rect
    local_uv = np.column_stack((u0 + uv[used, 0] * (u1-u0), v0 + uv[used, 1] * (v1-v0)))
    vertices = [(positions[i], normals[i], local_uv[j], int(bones[i])) for j, i in enumerate(used)]

    # Correct inconsistent source winding after vertex clustering.
    oriented = []
    for tri in local_faces:
        a, b, c = map(int, tri)
        cross = np.cross(vertices[b][0] - vertices[a][0], vertices[c][0] - vertices[a][0])
        dot = np.dot(cross, vertices[a][1])
        if np.linalg.norm(cross) < 1e-10 or abs(dot) < 1e-12:
            continue
        oriented.append((a, b, c) if dot > 0 else (a, c, b))

    root = ET.Element("MESH", NUMSUBMESH="1")
    sub = ET.SubElement(root, "SUBMESH", NUMVERTICES=str(len(vertices)),
        NUMFACES=str(len(oriented)), MATERIAL="0", NUMLODSTEPS="0",
        NUMSPRINGS="0", NUMTEXCOORDS="1")
    for index, (pos, norm, texcoord, bone) in enumerate(vertices):
        vertex = ET.SubElement(sub, "VERTEX", ID=str(index), NUMINFLUENCES="1")
        ET.SubElement(vertex, "POS").text = "%.9g %.9g %.9g" % tuple(pos)
        ET.SubElement(vertex, "NORM").text = "%.9g %.9g %.9g" % tuple(norm)
        ET.SubElement(vertex, "TEXCOORD").text = "%.9g %.9g" % tuple(texcoord)
        ET.SubElement(vertex, "INFLUENCE", ID=str(bone)).text = "1"
    for tri in oriented:
        ET.SubElement(sub, "FACE", VERTEXID="%d %d %d" % tri)
    write_cal(path, "XMF", root)
    binary_mesh(path.with_suffix(".cmf"), vertices, oriented)


def write_dds(path: Path, source: Path, size: tuple[int, int]) -> None:
    """Use the established generator's uncompressed BGRA DDS contract."""
    import struct
    base = Image.open(source).convert("RGBA").resize(size, Image.Resampling.LANCZOS)
    levels = 4
    header = [124, 0x0002100F, base.height, base.width, base.width*4, 0, levels] + [0]*11
    header += [32, 0x41, 0, 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000]
    header += [0x401008, 0, 0, 0, 0]
    payload = bytearray()
    for level in range(levels):
        image = base.resize((max(1, base.width >> level), max(1, base.height >> level)), Image.Resampling.LANCZOS)
        rgba = np.asarray(image)
        payload.extend(rgba[:, :, [2, 1, 0, 3]].tobytes())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"DDS " + struct.pack("<31I", *header) + payload)


def generate_animations(root: Path) -> None:
    # Complete player lifecycle. Motions intentionally use the standard stable
    # skeleton so movement, combat and world interactions need no protocol work.
    clips = {
        "idle": (2.4, [(0,{2:-.04,4:-.15,6:.15}),(1.2,{2:.04,4:-.10,6:.10}),(2.4,{2:-.04,4:-.15,6:.15})]),
        "idle_2": (3.0, [(0,{}),(1.5,{3:.18,4:.20,6:-.20}),(3.0,{})]),
        "walk": (1.0, [(0,{4:.48,6:-.48,8:-.58,11:.58}),(.5,{4:-.48,6:.48,8:.58,11:-.58}),(1.0,{4:.48,6:-.48,8:-.58,11:.58})]),
        "run": (.68, [(0,{4:.80,6:-.80,8:-.88,11:.88}),(.34,{4:-.80,6:.80,8:.88,11:-.88}),(.68,{4:.80,6:-.80,8:-.88,11:.88})]),
        "combat_idle": (1.6, [(0,{2:-.12,4:.30,6:-.42}),(0.8,{2:.04,4:.36,6:-.35}),(1.6,{2:-.12,4:.30,6:-.42})]),
        "attack": (.72, [(0,{2:-.15,4:.25,6:-.55}),(.30,{2:.58,4:-.45,6:1.48,7:.65}),(.72,{2:-.15,4:.25,6:-.55})]),
        "cast": (1.25, [(0,{}),(.55,{2:.18,4:-1.15,6:-1.15}),(.85,{2:.30,4:-1.55,6:-1.55}),(1.25,{})]),
        "pain": (.48, [(0,{}),(.20,{1:-.18,2:-.48,4:-.32,6:-.32}),(.48,{})]),
        "death": (1.35, [(0,{}),(.65,{1:-.88,2:-.92}),(1.35,{1:-1.48,2:-1.48,8:.42,11:.42})]),
        "sit_down": (.85, [(0,{}),(.85,{8:1.30,9:-1.28,11:1.30,12:-1.28})]),
        "sit": (1.8, [(0,{8:1.30,9:-1.28,11:1.30,12:-1.28}),(.9,{2:.05,8:1.30,9:-1.28,11:1.30,12:-1.28}),(1.8,{8:1.30,9:-1.28,11:1.30,12:-1.28})]),
        "stand_up": (.85, [(0,{8:1.30,9:-1.28,11:1.30,12:-1.28}),(.85,{})]),
        "harvest": (1.1, [(0,{}),(.55,{2:.48,4:1.02,6:1.02}),(1.1,{})]),
        "pick": (.85, [(0,{}),(.42,{2:.72,4:.85,6:.85,8:.35,11:.35}),(.85,{})]),
        "drop": (.72, [(0,{}),(.35,{2:.42,6:.78}),(.72,{})]),
    }
    for name, (duration, poses) in clips.items():
        animation(root / f"animations/four_gates_guard/{name}.xaf", duration, poses)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", default="build/eloria-data")
    args = parser.parse_args()
    root = Path(args.output)
    data = np.load(SOURCE / "guard_mesh.npz")
    write_mesh(root / "actors/four_gates_guard/guard_body.xmf",
        data["positions"], data["normals"], data["uv"], data["faces"],
        data["bones"], BODY_UV_RECT)
    # Enhanced actors require source images at each slot's native dimensions;
    # feeding the compositor one 2048px image caused its white fallback.
    write_dds(root / "actors/four_gates_guard/guard_torso.dds",
        SOURCE / "guard_atlas.webp", (196, 216))
    write_dds(root / "actors/four_gates_guard/guard_arms.dds",
        SOURCE / "guard_atlas.webp", (160, 160))
    generate_animations(root)
    print(f"Generated Four Gates guard: {len(data['faces'])} triangles, 15 animations")


if __name__ == "__main__":
    main()

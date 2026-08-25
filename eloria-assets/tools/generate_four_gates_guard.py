#!/usr/bin/env python3
"""Build the user-supplied Four Gates guard as an animated Cal3D player preset."""
from __future__ import annotations

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image

from generate_characters import (BONES, animation, binary_mesh, cuboid,
                                 ellipsoid, profile_surface, write_cal)

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
        "idle": (2.4, [(0,{2:-.018}),(1.2,{2:.018}),(2.4,{2:-.018})]),
        "idle_2": (3.0, [(0,{}),(1.5,{3:.10,2:.025}),(3.0,{})]),
        "walk": (1.0, [(0,{4:.22,6:-.22,8:-.38,11:.38}),(.5,{4:-.22,6:.22,8:.38,11:-.38}),(1.0,{4:.22,6:-.22,8:-.38,11:.38})]),
        "run": (.68, [(0,{4:.48,6:-.48,8:-.62,11:.62}),(.34,{4:-.48,6:.48,8:.62,11:-.62}),(.68,{4:.48,6:-.48,8:-.62,11:.62})]),
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
    positions=list(data["positions"]); normals=list(data["normals"])
    texcoords=list(data["uv"]); bones=list(data["bones"]); faces=list(data["faces"])
    # A continuous neutral under-suit fills spaces between the original armor
    # shells, preventing the world background from showing through at joints.
    filler_vertices=[]; filler_faces=[]
    profile_surface([(0,0,.86,.18,.13),(0,0,1.10,.27,.16),(0,0,1.39,.28,.17),(0,0,1.58,.20,.13)],
        [1,2,2,25],filler_vertices,filler_faces,sides=30)
    for side,chain in ((-1,[28,4,5,16]),(1,[29,6,7,17])):
        profile_surface([(side*.22,0,1.47,.12,.12),(side*.30,0,1.27,.105,.11),
                         (side*.31,0,1.02,.095,.105),(side*.31,-.01,.78,.105,.115)],
                        chain,filler_vertices,filler_faces,sides=24)
    for side,chain in ((-1,[8,8,9,10]),(1,[11,11,12,13])):
        profile_surface([(side*.10,0,.90,.13,.14),(side*.10,0,.63,.12,.13),
                         (side*.10,.01,.30,.10,.115),(side*.10,.13,.02,.12,.22)],
                        chain,filler_vertices,filler_faces,sides=24)
    ellipsoid((0,0,1.72),(.32,.29,.36),3,filler_vertices,filler_faces,rings=12,sides=28)
    # Neutral-pose armor replaces the discarded action-pose limb shells.
    for side,upper,lower,hand in ((-1,4,5,16),(1,6,7,17)):
        ellipsoid((side*.255,0,1.43),(.28,.28,.25),upper,filler_vertices,filler_faces,rings=10,sides=24)
        ellipsoid((side*.31,-.005,1.05),(.23,.22,.34),lower,filler_vertices,filler_faces,rings=10,sides=22)
        ellipsoid((side*.31,-.015,.77),(.20,.19,.20),hand,filler_vertices,filler_faces,rings=8,sides=20)
    for side,upper,lower,foot in ((-1,8,9,10),(1,11,12,13)):
        ellipsoid((side*.10,0,.71),(.27,.28,.38),upper,filler_vertices,filler_faces,rings=10,sides=24)
        ellipsoid((side*.10,.015,.31),(.22,.24,.39),lower,filler_vertices,filler_faces,rings=10,sides=22)
        ellipsoid((side*.10,.13,.04),(.25,.39,.16),foot,filler_vertices,filler_faces,rings=8,sides=20)
    offset=len(positions)
    for pos,norm,uv,bone in filler_vertices:
        positions.append(np.asarray(pos)); normals.append(np.asarray(norm)); texcoords.append(np.asarray(uv)); bones.append(bone)
    faces.extend(tuple(offset+index for index in triangle) for triangle in filler_faces)
    write_mesh(root / "actors/four_gates_guard/guard_body.xmf",
        np.asarray(positions), np.asarray(normals), np.asarray(texcoords),
        np.asarray(faces), np.asarray(bones), BODY_UV_RECT)
    # Standalone wearable meshes use the same skeleton anchors and are only
    # attached when the server sends their protocol equipment IDs.
    equipment=[]
    spear_vertices=[]; spear_faces=[]
    profile_surface([(.31,-.01,.12,.035,.035),(.31,-.01,1.18,.035,.035),
                     (.31,-.01,2.25,.045,.045),(.31,-.01,2.52,.19,.08),
                     (.31,-.01,2.78,.015,.015)],
                    [17,17,17,17,17],spear_vertices,spear_faces,sides=18)
    equipment.append(("guard_spear",spear_vertices,spear_faces))
    shield_vertices=[]; shield_faces=[]
    ellipsoid((-.34,-.18,1.10),(.72,.10,.92),16,shield_vertices,shield_faces,rings=16,sides=34)
    ellipsoid((-.34,-.235,1.10),(.54,.06,.70),16,shield_vertices,shield_faces,rings=12,sides=28)
    cuboid((-.34,-.27,1.10),(.12,.08,.72),16,shield_vertices,shield_faces)
    equipment.append(("guard_shield",shield_vertices,shield_faces))
    cape_vertices=[]; cape_faces=[]
    profile_surface([(0,.18,.26,.38,.035),(0,.20,.72,.42,.04),(0,.19,1.18,.44,.045),(0,.14,1.55,.36,.04)],
                    [24,23,22,22],cape_vertices,cape_faces,sides=36)
    equipment.append(("guard_cape",cape_vertices,cape_faces))
    for name,vertices,triangles in equipment:
        write_mesh(root/f"actors/four_gates_guard/{name}.xmf",
            np.asarray([q[0] for q in vertices]),np.asarray([q[1] for q in vertices]),
            np.asarray([q[2] for q in vertices]),np.asarray(triangles),
            np.asarray([q[3] for q in vertices]),(0,0,1,1))
    Image.open(SOURCE/"guard_atlas.webp").convert("RGB").resize((512,512),Image.Resampling.LANCZOS).save(
        root/"actors/four_gates_guard/guard_equipment.png")
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

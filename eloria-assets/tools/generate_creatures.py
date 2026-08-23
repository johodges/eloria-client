#!/usr/bin/env python3
"""Generate original low-poly animals and monsters in Cal3D XML formats."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from generate_bootstrap_pack import png

VERSION = "919"
ACTOR_BASE = 200
BONES = (
    ("root", -1, (0., 0., 0.)), ("body", 0, (0., 0., .75)),
    ("neck", 1, (0., .62, .18)), ("head", 2, (0., .34, .08)),
    ("tail", 1, (0., -.72, .10)),
    ("front_leg_l", 1, (-.28, .43, -.22)), ("front_paw_l", 5, (0., 0., -.55)),
    ("front_leg_r", 1, (.28, .43, -.22)), ("front_paw_r", 7, (0., 0., -.55)),
    ("rear_leg_l", 1, (-.30, -.43, -.22)), ("rear_paw_l", 9, (0., 0., -.55)),
    ("rear_leg_r", 1, (.30, -.43, -.22)), ("rear_paw_r", 11, (0., 0., -.55)),
)

CREATURES = (
    ("emberfox", "Emberfox", "animal", (178, 83, 46), (.76, 1.28, .58), (.46, .52, .44), "ears"),
    ("mossback_boar", "Mossback Boar", "animal", (75, 91, 56), (1.02, 1.52, .75), (.62, .58, .55), "tusks"),
    ("ridgehorn", "Ridgehorn", "animal", (136, 119, 82), (.82, 1.45, .82), (.50, .55, .48), "horns"),
    ("miretoad", "Miretoad", "animal", (65, 117, 74), (1.12, 1.05, .48), (.66, .48, .38), "eyes"),
    ("ash_crawler", "Ash Crawler", "monster", (73, 65, 65), (1.28, 1.62, .48), (.74, .62, .42), "spikes"),
    ("frost_maw", "Frost Maw", "monster", (135, 183, 194), (.92, 1.58, .80), (.62, .72, .62), "fangs"),
    ("bog_lurker", "Bog Lurker", "monster", (60, 87, 67), (1.18, 1.45, .88), (.72, .65, .64), "spikes"),
    ("sunscale_drake", "Sunscale Drake", "monster", (191, 126, 49), (1.00, 1.72, .76), (.58, .65, .50), "wings"),
    ("red_fox", "Red Fox", "animal", (173, 72, 43), (.68, 1.18, .52), (.42, .48, .40), "ears"),
    ("snow_hare", "Snow Hare", "animal", (207, 215, 211), (.58, .88, .50), (.40, .40, .38), "long_ears"),
    ("mountain_goat", "Mountain Goat", "animal", (151, 143, 122), (.82, 1.32, .76), (.48, .50, .46), "horns"),
    ("black_bear", "Black Bear", "animal", (47, 43, 39), (1.18, 1.48, .94), (.68, .58, .62), "round_ears"),
    ("elk", "Elk", "animal", (125, 91, 57), (.90, 1.58, .92), (.50, .56, .50), "antlers"),
    ("wild_boar", "Wild Boar", "animal", (91, 76, 61), (1.02, 1.46, .74), (.62, .58, .52), "tusks"),
    ("dire_wolf", "Dire Wolf", "monster", (76, 82, 87), (.92, 1.52, .78), (.58, .64, .54), "fangs"),
    ("frost_tiger", "Frost Tiger", "monster", (174, 197, 202), (.94, 1.62, .74), (.58, .64, .52), "fangs"),
    ("giant_crocodile", "Giant Crocodile", "monster", (67, 103, 63), (1.30, 2.05, .48), (.72, .92, .38), "back_ridge"),
    ("fire_salamander", "Fire Salamander", "monster", (178, 70, 38), (.88, 1.72, .42), (.52, .72, .36), "back_ridge"),
    ("thunder_ram", "Thunder Ram", "monster", (110, 104, 91), (1.02, 1.42, .88), (.64, .58, .58), "great_horns"),
    ("giant_rat", "Giant Rat", "monster", (104, 86, 72), (.76, 1.34, .58), (.46, .60, .40), "round_ears"),
    ("raccoon", "Raccoon", "animal", (91, 91, 84), (.66, 1.08, .52), (.42, .46, .38), "round_ears"),
    ("river_otter", "River Otter", "animal", (91, 70, 50), (.62, 1.38, .46), (.38, .52, .34), "whiskers"),
    ("porcupine", "Porcupine", "animal", (104, 82, 57), (.78, 1.12, .60), (.42, .44, .36), "quills"),
    ("moose", "Moose", "animal", (91, 72, 52), (1.00, 1.68, 1.02), (.58, .62, .56), "broad_antlers"),
    ("lynx", "Lynx", "animal", (154, 127, 91), (.76, 1.24, .66), (.48, .50, .44), "tufted_ears"),
    ("desert_tortoise", "Desert Tortoise", "animal", (121, 112, 73), (1.12, 1.42, .48), (.48, .50, .34), "shell"),
    ("saber_tooth_cat", "Saber-Tooth Cat", "monster", (174, 139, 85), (1.02, 1.62, .82), (.62, .66, .54), "saber_fangs"),
    ("armored_rhino", "Armored Rhino", "monster", (105, 105, 96), (1.34, 1.82, 1.00), (.72, .72, .62), "nose_horn"),
    ("giant_komodo", "Giant Komodo", "monster", (91, 111, 66), (1.16, 2.00, .50), (.64, .84, .38), "back_ridge"),
    ("ice_bear", "Ice Bear", "monster", (185, 207, 211), (1.30, 1.62, 1.02), (.72, .66, .66), "ice_spikes"),
    ("lava_hound", "Lava Hound", "monster", (157, 57, 34), (.96, 1.56, .76), (.58, .64, .52), "fire_spikes"),
    ("two_tailed_fox", "Two-Tailed Fox", "monster", (181, 101, 47), (.78, 1.32, .62), (.48, .54, .44), "twin_tail"),
)


def write_cal(path, magic, root):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'<HEADER MAGIC="{magic}" VERSION="{VERSION}"/>\n' +
                    ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")


def skeleton(path):
    children = {i: [] for i in range(len(BONES))}
    absolute = []
    for i, (_, parent, pos) in enumerate(BONES):
        if parent >= 0:
            children[parent].append(i)
        base = (0., 0., 0.) if parent < 0 else absolute[parent]
        absolute.append(tuple(base[j] + pos[j] for j in range(3)))
    root = ET.Element("SKELETON", NUMBONES=str(len(BONES)))
    for i, (name, parent, pos) in enumerate(BONES):
        bone = ET.SubElement(root, "BONE", ID=str(i), NAME=name,
                             NUMCHILDS=str(len(children[i])))
        ET.SubElement(bone, "TRANSLATION").text = "%g %g %g" % pos
        ET.SubElement(bone, "ROTATION").text = "0 0 0 1"
        ET.SubElement(bone, "LOCALTRANSLATION").text = "%g %g %g" % tuple(-v for v in absolute[i])
        ET.SubElement(bone, "LOCALROTATION").text = "0 0 0 1"
        ET.SubElement(bone, "PARENTID").text = str(parent)
        for child in children[i]:
            ET.SubElement(bone, "CHILDID").text = str(child)
    write_cal(path, "XSF", root)


def cuboid(center, size, bone, vertices, faces):
    cx, cy, cz = center
    sx, sy, sz = (v / 2 for v in size)
    corners = [(cx+x*sx, cy+y*sy, cz+z*sz) for x, y, z in
               ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
                (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1))]
    quads = ((0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(4,0,3,7))
    normals = ((0,0,-1),(0,0,1),(0,-1,0),(1,0,0),(0,1,0),(-1,0,0))
    for quad, normal in zip(quads, normals):
        base = len(vertices)
        for uv, corner in zip(((0,0),(1,0),(1,1),(0,1)), quad):
            vertices.append((corners[corner], normal, uv, bone))
        faces.extend(((base,base+1,base+2),(base,base+2,base+3)))


def creature_mesh(path, body_size, head_size, feature):
    vertices, faces = [], []
    bx, by, bz = body_size
    hx, hy, hz = head_size
    cuboid((0, 0, .82), (bx, by, bz), 1, vertices, faces)
    cuboid((0, by*.42, 1.0), (bx*.48, by*.36, bz*.55), 2, vertices, faces)
    cuboid((0, by*.67, 1.03), (hx, hy, hz), 3, vertices, faces)
    cuboid((0, -by*.60, .91), (bx*.24, by*.55, bz*.22), 4, vertices, faces)
    for x, y, upper, lower in ((-.31,.34,5,6),(.31,.34,7,8),(-.32,-.34,9,10),(.32,-.34,11,12)):
        cuboid((x*bx, y*by, .57), (bx*.18, by*.16, bz*.72), upper, vertices, faces)
        cuboid((x*bx, y*by, .23), (bx*.20, by*.28, bz*.18), lower, vertices, faces)
    if feature in ("ears", "horns", "long_ears", "round_ears", "antlers", "great_horns", "broad_antlers", "tufted_ears"):
        height = hz * (1.35 if feature == "long_ears" else .68)
        width = hx * (.28 if feature == "round_ears" else .18)
        for x in (-hx*.30, hx*.30):
            cuboid((x, by*.68, 1.03+hz*.62), (width, hy*.16, height), 3, vertices, faces)
    if feature in ("antlers", "great_horns", "broad_antlers"):
        spread = hx * (1.55 if feature == "broad_antlers" else (1.15 if feature == "antlers" else .85))
        cuboid((-spread*.55, by*.66, 1.03+hz), (spread, hy*.14, hz*.16), 3, vertices, faces)
        cuboid((spread*.55, by*.66, 1.03+hz), (spread, hy*.14, hz*.16), 3, vertices, faces)
    if feature in ("tusks", "fangs"):
        for x in (-hx*.34, hx*.34): cuboid((x, by*.84, .91), (hx*.12, hy*.45, hz*.34), 3, vertices, faces)
    if feature == "eyes":
        for x in (-hx*.30, hx*.30): cuboid((x, by*.67, 1.03+hz*.48), (hx*.24, hy*.20, hz*.30), 3, vertices, faces)
    if feature == "spikes":
        for n in (-.35, 0, .35): cuboid((0, n*by, 1.20+bz*.38), (bx*.15, by*.12, bz*.65), 1, vertices, faces)
    if feature == "wings":
        cuboid((-bx*.70, -.05, 1.13), (bx, by*.54, bz*.12), 1, vertices, faces)
        cuboid((bx*.70, -.05, 1.13), (bx, by*.54, bz*.12), 1, vertices, faces)
    if feature == "back_ridge":
        for n in (-.38, -.12, .14, .40):
            cuboid((0, n*by, 1.06+bz*.42), (bx*.18, by*.10, bz*.42), 1, vertices, faces)
    if feature in ("quills", "ice_spikes", "fire_spikes"):
        for n in (-.42, -.22, 0, .22, .42):
            cuboid((0, n*by, 1.10+bz*.48), (bx*.12, by*.08, bz*.72), 1, vertices, faces)
    if feature == "shell":
        cuboid((0, -.04, 1.03), (bx*1.08, by*.82, bz*.74), 1, vertices, faces)
    if feature in ("saber_fangs", "nose_horn"):
        if feature == "saber_fangs":
            for x in (-hx*.30, hx*.30):
                cuboid((x, by*.84, .88), (hx*.11, hy*.28, hz*.72), 3, vertices, faces)
        else:
            cuboid((0, by*.89, 1.15), (hx*.18, hy*.68, hz*.28), 3, vertices, faces)
    if feature == "whiskers":
        for x in (-1, 1):
            cuboid((x*hx*.55, by*.78, .99), (hx*.65, hy*.08, hz*.07), 3, vertices, faces)
    if feature == "twin_tail":
        cuboid((-bx*.18, -by*.64, .96), (bx*.18, by*.65, bz*.18), 4, vertices, faces)
        cuboid((bx*.18, -by*.64, .96), (bx*.18, by*.65, bz*.18), 4, vertices, faces)
    root = ET.Element("MESH", NUMSUBMESH="1")
    sub = ET.SubElement(root, "SUBMESH", NUMVERTICES=str(len(vertices)), NUMFACES=str(len(faces)),
                        MATERIAL="0", NUMLODSTEPS="0", NUMSPRINGS="0", NUMTEXCOORDS="1")
    for i, (pos, norm, uv, bone) in enumerate(vertices):
        v = ET.SubElement(sub, "VERTEX", ID=str(i), NUMINFLUENCES="1")
        ET.SubElement(v, "POS").text = "%g %g %g" % pos
        ET.SubElement(v, "NORM").text = "%g %g %g" % norm
        ET.SubElement(v, "TEXCOORD").text = "%g %g" % uv
        ET.SubElement(v, "INFLUENCE", ID=str(bone)).text = "1"
    for tri in faces: ET.SubElement(sub, "FACE", VERTEXID="%d %d %d" % tri)
    write_cal(path, "XMF", root)


def quat(axis, angle):
    half = angle / 2
    v = [0., 0., 0.]; v[axis] = math.sin(half)
    return (*v, math.cos(half))


def animation(path, duration, poses):
    tracks = sorted({bone for _, frame in poses for bone in frame})
    root = ET.Element("ANIMATION", DURATION=str(duration), NUMTRACKS=str(len(tracks)))
    for bone in tracks:
        tr = ET.SubElement(root, "TRACK", BONEID=str(bone), NUMKEYFRAMES=str(len(poses)),
                           TRANSLATIONREQUIRED="0", TRANSLATIONISDYNAMIC="0", HIGHRANGEREQUIRED="0")
        for time, frame in poses:
            axis, angle = frame.get(bone, (0, 0.))
            key = ET.SubElement(tr, "KEYFRAME", TIME=str(time))
            ET.SubElement(key, "ROTATION").text = "%g %g %g %g" % quat(axis, angle)
    write_cal(path, "XAF", root)


def append_actor_defs(path):
    document = ET.parse(path)
    root = document.getroot()
    frames = {"CAL_walk":"walk.xaf", "CAL_run":"run.xaf", "CAL_idle":"idle.xaf",
              "CAL_idle2":"idle.xaf", "CAL_combat_idle":"idle.xaf",
              "CAL_attack_up_1":"attack.xaf", "CAL_attack_down_1":"attack.xaf",
              "CAL_pain1":"pain.xaf", "CAL_pain2":"pain.xaf",
              "CAL_die1":"die.xaf", "CAL_die2":"die.xaf"}
    for index, (slug, label, family, _, _, _, _) in enumerate(CREATURES):
        actor = ET.SubElement(root, "actor", id=str(ACTOR_BASE + index), type=label,
                              family=family)
        ET.SubElement(actor, "skeleton").text = "actors/creatures/eloria_quadruped.xsf"
        ET.SubElement(actor, "mesh").text = f"actors/creatures/{slug}.xmf"
        ET.SubElement(actor, "skin").text = f"actors/creatures/{slug}.png"
        ET.SubElement(actor, "step_duration").text = "240"
        frame_root = ET.SubElement(actor, "frames")
        for tag, filename in frames.items():
            ET.SubElement(frame_root, tag).text = f"animations/creatures/{filename}"
    path.write_text('<?xml version="1.0"?>\n' + ET.tostring(root, encoding="unicode") + "\n",
                    encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", default="build/eloria-data")
    root = Path(parser.parse_args().output)
    skeleton(root / "actors/creatures/eloria_quadruped.xsf")
    for slug, _, _, color, body, head, feature in CREATURES:
        creature_mesh(root / f"actors/creatures/{slug}.xmf", body, head, feature)
        png(root / f"actors/creatures/{slug}.png", 256, 256,
            lambda x, y, c=color: (*(max(0, min(255, q + (((x//24)^(y//24))&1)*18)) for q in c), 255))
    poses = {
        "idle": (2., [(0,{2:(0,-.04),4:(2,-.10)}),(1,{2:(0,.04),4:(2,.10)}),(2,{2:(0,-.04),4:(2,-.10)})]),
        "walk": (1., [(0,{5:(0,.55),7:(0,-.55),9:(0,-.55),11:(0,.55)}),(.5,{5:(0,-.55),7:(0,.55),9:(0,.55),11:(0,-.55)}),(1,{5:(0,.55),7:(0,-.55),9:(0,-.55),11:(0,.55)})]),
        "run": (.65, [(0,{5:(0,.85),7:(0,-.85),9:(0,-.85),11:(0,.85)}),(.325,{5:(0,-.85),7:(0,.85),9:(0,.85),11:(0,-.85)}),(.65,{5:(0,.85),7:(0,-.85),9:(0,-.85),11:(0,.85)})]),
        "attack": (.7, [(0,{2:(0,-.25)}),(.32,{2:(0,.65),3:(0,.38)}),(.7,{2:(0,-.25)})]),
        "pain": (.5, [(0,{1:(2,0)}),(.22,{1:(2,.28),2:(0,-.25)}),(.5,{1:(2,0)})]),
        "die": (1.3, [(0,{1:(2,0)}),(.7,{1:(2,1.15),2:(0,-.4)}),(1.3,{1:(2,1.48),2:(0,-.6)})]),
    }
    for name, (duration, keys) in poses.items():
        animation(root / f"animations/creatures/{name}.xaf", duration, keys)
    append_actor_defs(root / "actor_defs/actor_defs.xml")
    (root / "creatures_eloria.json").write_text(json.dumps({"schema": 1, "creatures": [
        {"actor_type": ACTOR_BASE+i, "id": slug, "name": label, "family": family}
        for i, (slug, label, family, *_rest) in enumerate(CREATURES)]}, indent=2) + "\n",
        encoding="utf-8")


if __name__ == "__main__": main()

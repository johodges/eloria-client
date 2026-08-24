#!/usr/bin/env python3
"""Validate shared runtime contracts across the complete generated data pack."""

from __future__ import annotations

import argparse
from pathlib import Path
import struct
import xml.etree.ElementTree as ET


HUMANOID_ANCHORS = {
    "root", "pelvis", "spine", "head", "mouth", "jaw", "handL",
    "handR", "weaponL", "weaponR", "staffR", "arrow", "cape1",
    "cape2", "cape3",
}
CREATURE_ANCHORS = {
    "root", "body", "head", "mouth", "jaw", "handL", "handR",
    "weaponL", "weaponR", "staffR", "arrow", "cape1", "cape2", "cape3",
}


def cal_xml(path: Path) -> ET.Element:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].startswith("<HEADER MAGIC="):
        raise ValueError(f"missing Cal3D XML header: {path}")
    return ET.fromstring("\n".join(lines[1:]))


def validate_maps(root: Path) -> None:
    maps = sorted(root.glob("maps/**/*.elm"))
    if len(maps) != 27:
        raise ValueError(f"expected 27 ELM maps, found {len(maps)}")
    for path in maps:
        data = path.read_bytes()
        if len(data) < 124 or data[:4] != b"elmf":
            raise ValueError(f"invalid ELM header: {path}")
        values = struct.unpack_from("<13i", data, 4)
        width, height, tile_offset, height_offset = values[:4]
        obj3_size, obj3_count, obj3_offset = values[4:7]
        obj2_size, obj2_count, obj2_offset = values[7:10]
        light_size, light_count, light_offset = values[10:13]
        particle_size, particle_count, particle_offset = struct.unpack_from(
            "<3i", data, 72)
        if width <= 0 or height <= 0 or tile_offset != 124:
            raise ValueError(f"invalid ELM dimensions/header size: {path}")
        if height_offset != tile_offset + width * height:
            raise ValueError(f"invalid ELM height offset: {path}")
        sections = (
            (height_offset, width * height * 36, "height map"),
            (obj3_offset, obj3_size * obj3_count, "3D objects"),
            (obj2_offset, obj2_size * obj2_count, "2D objects"),
            (light_offset, light_size * light_count, "lights"),
            (particle_offset, particle_size * particle_count, "particles"),
        )
        if (obj3_size, obj2_size, light_size, particle_size) != (144, 128, 40, 104):
            raise ValueError(f"invalid ELM record size: {path}")
        for offset, size, label in sections:
            if offset < 124 or size < 0 or offset + size > len(data):
                raise ValueError(f"invalid ELM {label} bounds: {path}")
        for index in range(obj3_count):
            record_offset = obj3_offset + index * obj3_size
            raw_name = struct.unpack_from("<80s", data, record_offset)[0]
            name = raw_name.split(b"\0", 1)[0].decode("utf-8")
            asset = root / name.removeprefix("./")
            if not asset.is_file():
                raise ValueError(f"missing ELM object {name} referenced by {path}")
        if path.name == "newcharactermap.elm":
            preview_x, preview_y = 43, 156
            tiles = data[tile_offset:height_offset]
            heights = data[height_offset:height_offset + width * height * 36]
            tile = tiles[(preview_y // 6) * width + preview_x // 6]
            raw_height = heights[preview_y * width * 6 + preview_x]
            if tile != 0 or (raw_height & 0x3f) != 11:
                raise ValueError("character preview must stand on visible z=0 terrain")
            if obj3_count < 4 or light_count < 1:
                raise ValueError("character preview scene lacks scenery or lighting")
        if path.as_posix().endswith("maps/nymara/four_gates.elm"):
            spawn_x, spawn_y = 58, 58
            tiles = data[tile_offset:height_offset]
            heights = data[height_offset:height_offset + width * height * 36]
            tile = tiles[(spawn_y // 6) * width + spawn_x // 6]
            raw_height = heights[spawn_y * width * 6 + spawn_x]
            if tile == 255 or (raw_height & 0x3f) != 11:
                raise ValueError("Four Gates start spawn must be on visible z=0 terrain")
            if obj3_count < 1:
                raise ValueError("Four Gates start map lacks scenery")


def validate_runtime_xml(root: Path) -> None:
    path = root / "extentions.xml"
    if not path.is_file() or ET.parse(path).getroot().tag != "extentions":
        raise ValueError("missing or invalid legacy extentions.xml")


def validate_skeletons(root: Path) -> None:
    skeletons = sorted(root.glob("actors/**/*.xsf"))
    if len(skeletons) != 7:
        raise ValueError(f"expected 7 generated skeletons, found {len(skeletons)}")
    for path in skeletons:
        document = cal_xml(path)
        bones = document.findall("BONE")
        names = {bone.attrib["NAME"] for bone in bones}
        required = CREATURE_ANCHORS if "creature" in path.name or "quadruped" in path.name else HUMANOID_ANCHORS
        missing = required - names
        if missing:
            raise ValueError(f"missing skeleton anchors in {path}: {sorted(missing)}")
        for bone in bones:
            if "NUMCHILDS" in bone.attrib or "NUMCHILD" not in bone.attrib:
                raise ValueError(f"invalid child-count attribute in {path}")
            if int(bone.attrib["NUMCHILD"]) != len(bone.findall("CHILDID")):
                raise ValueError(f"incorrect child count in {path}: {bone.attrib['NAME']}")


def validate_meshes(root: Path) -> None:
    meshes = sorted(root.glob("actors/**/*.xmf"))
    if not meshes:
        raise ValueError("no generated Cal3D meshes found")
    for path in meshes:
        for submesh in cal_xml(path).findall("SUBMESH"):
            vertices = {}
            normals = {}
            for vertex in submesh.findall("VERTEX"):
                ident = int(vertex.attrib["ID"])
                vertices[ident] = tuple(map(float, vertex.findtext("POS").split()))
                normals[ident] = tuple(map(float, vertex.findtext("NORM").split()))
            for face in submesh.findall("FACE"):
                a, b, c = map(int, face.attrib["VERTEXID"].split())
                ab = tuple(vertices[b][i] - vertices[a][i] for i in range(3))
                ac = tuple(vertices[c][i] - vertices[a][i] for i in range(3))
                cross = (ab[1]*ac[2] - ab[2]*ac[1],
                         ab[2]*ac[0] - ab[0]*ac[2],
                         ab[0]*ac[1] - ab[1]*ac[0])
                if sum(cross[i] * normals[a][i] for i in range(3)) <= 0.0:
                    raise ValueError(f"inward or degenerate face in {path}: {a} {b} {c}")


def expected_dds_size(name: str) -> tuple[int, int]:
    if name.startswith("eyes_"):
        return 24, 24
    if name.startswith("hair_"):
        return 136, 192
    if name.startswith("boots_"):
        return 156, 160
    if name.startswith("pants_") or "_arms" in name:
        return 160, 160
    if "_torso" in name:
        return 196, 216
    if name.startswith("skin_") and "_head" in name:
        return 128, 128
    if name.startswith("skin_") and "_hands" in name:
        return 64, 64
    raise ValueError(f"unknown customization DDS role: {name}")


def validate_customization_dds(root: Path) -> None:
    textures = sorted(root.glob("actors/custom/**/*.dds"))
    if len(textures) != 654:
        raise ValueError(f"expected 654 customization DDS files, found {len(textures)}")
    for path in textures:
        data = path.read_bytes()
        if data[:4] != b"DDS " or len(data) < 128:
            raise ValueError(f"invalid DDS header: {path}")
        header = struct.unpack_from("<31I", data, 4)
        height, width, mipmaps = header[2], header[3], header[6]
        expected_width, expected_height = expected_dds_size(path.name)
        if (width, height, mipmaps) != (expected_width, expected_height, 3):
            raise ValueError(
                f"invalid DDS layout {path}: {width}x{height}, {mipmaps} mipmaps")
        payload = sum(max(1, width >> level) * max(1, height >> level) * 4
                      for level in range(mipmaps))
        if len(data) != 128 + payload:
            raise ValueError(f"invalid DDS mip payload length: {path}")

def validate_map_dds(root: Path) -> None:
    local_maps = sorted((root / "maps/nymara").glob("*.dds"))
    if len(local_maps) != 19:
        raise ValueError(f"expected 19 Nymara local-map DDS files, found {len(local_maps)}")
    paths = local_maps + [root / "maps/nymara_continent.dds"]
    for path in paths:
        data = path.read_bytes()
        if data[:4] != b"DDS " or len(data) < 128:
            raise ValueError(f"invalid map DDS header: {path}")
        header = struct.unpack_from("<31I", data, 4)
        height, width, mipmaps = header[2], header[3], header[6]
        if (width, height, mipmaps) != (512, 512, 4):
            raise ValueError(f"invalid map DDS layout: {path}")
        expected = 128 + sum(max(1, width >> level) * max(1, height >> level) * 4
                             for level in range(mipmaps))
        if len(data) != expected:
            raise ValueError(f"invalid map DDS payload: {path}")
    entries = [line.split("|") for line in (root / "mapinfo.lst").read_text().splitlines()
               if line.strip() and not line.lstrip().startswith("#")]
    if len(entries) != 27 or any(len(entry) != 4 for entry in entries):
        raise ValueError("mapinfo.lst must contain exactly 27 complete map records")
    for _, _, elm, image in entries:
        if not (root / elm).is_file() or not (root / image).is_file():
            raise ValueError(f"mapinfo.lst references missing runtime asset: {elm} / {image}")
    continent = (root / "continfo.lst").read_text().strip().split("|")
    if continent != ["Nymara", "maps/nymara_continent.dds"]:
        raise ValueError("continfo.lst does not reference the generated Nymara overview")


def validate_animations(root: Path) -> None:
    animations = sorted(root.glob("animations/**/*.xaf"))
    if not animations:
        raise ValueError("no generated Cal3D animations found")
    for path in animations:
        document = cal_xml(path)
        for track in document.findall("TRACK"):
            frames = track.findall("KEYFRAME")
            if int(track.attrib["NUMKEYFRAMES"]) != len(frames):
                raise ValueError(f"incorrect animation keyframe count: {path}")
            if any(frame.find("TRANSLATION") is None or frame.find("ROTATION") is None
                   for frame in frames):
                raise ValueError(f"incomplete animation keyframe: {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("data_root", nargs="?", default="build/eloria-data")
    root = Path(parser.parse_args().data_root)
    validate_maps(root)
    validate_runtime_xml(root)
    validate_skeletons(root)
    validate_meshes(root)
    validate_animations(root)
    validate_customization_dds(root)
    validate_map_dds(root)
    print("Validated every generated ELM, Cal3D XML family, and customization DDS")


if __name__ == "__main__":
    main()

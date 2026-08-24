#!/usr/bin/env python3
"""Validate shared runtime contracts across the complete generated data pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
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
        object_records = []
        for index in range(obj3_count):
            record_offset = obj3_offset + index * obj3_size
            raw_name = struct.unpack_from("<80s", data, record_offset)[0]
            name = raw_name.split(b"\0", 1)[0].decode("utf-8")
            x, y, z = struct.unpack_from("<3f", data, record_offset + 80)
            object_records.append((name, x, y, z))
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
            if obj3_count < 65:
                raise ValueError("Four Gates vertical slice lacks production scenery density")
            required_landmarks = {
                "3dobjects/nymara/four_gates_gatehouse.e3d": 4,
                "3dobjects/nymara/four_gates_radial_bridge.e3d": 4,
                "3dobjects/nymara/four_gates_civic_wall.e3d": 12,
                "3dobjects/nymara/four_gates_civic_tower.e3d": 8,
                "3dobjects/nymara/four_gates_civic_pavilion.e3d": 8,
                "3dobjects/nymara/four_gates_park_tree.e3d": 16,
                "3dobjects/nymara/four_gates_lantern.e3d": 12,
                "3dobjects/nymara/four_gates_waystone.e3d": 1,
            }
            for landmark, minimum in required_landmarks.items():
                count = sum(name == landmark for name, *_ in object_records)
                if count < minimum:
                    raise ValueError(
                        f"Four Gates is missing {landmark}: expected {minimum}, found {count}")
            if any(math.hypot(x-spawn_x, y-spawn_y) < 3.0
                   for _, x, y, _ in object_records):
                raise ValueError("Four Gates start plaza is obstructed")
            if set(tiles) != {4, 5, 6, 7} or len(set(heights)) < 4:
                raise ValueError("Four Gates terrain lacks roads, water, or elevation variation")
            if light_count < 16:
                raise ValueError("Four Gates lacks its civic night-light network")
        if path.as_posix().endswith("maps/nymara/mirrorhold.elm"):
            mirror_tiles = data[tile_offset:height_offset]
            mirror_heights = data[height_offset:height_offset + width * height * 36]
            required = {
                "3dobjects/nymara/glasswarden_observatory.e3d": 1,
                "3dobjects/nymara/glasswarden_lens_tower.e3d": 4,
                "3dobjects/nymara/mirrorhold_civic_tower.e3d": 8,
                "3dobjects/nymara/mirrorhold_canal_wall.e3d": 9,
                "3dobjects/nymara/mirrorhold_radial_bridge.e3d": 6,
                "3dobjects/nymara/mirrorhold_public_fountain.e3d": 6,
                "3dobjects/nymara/glasswarden_field_station.e3d": 8,
            }
            for landmark, minimum in required.items():
                if sum(name == landmark for name, *_ in object_records) < minimum:
                    raise ValueError(f"Mirrorhold is missing {landmark}")
            if any(math.hypot(x-58, y-58) < 3.0 for _, x, y, _ in object_records):
                raise ValueError("Mirrorhold arrival plaza is obstructed")
            if obj3_count < 48 or light_count < 13:
                raise ValueError("Mirrorhold lacks authored scenery or lighting")
            if set(mirror_tiles) != {0, 1, 2, 3} or len(set(mirror_heights)) < 8:
                raise ValueError("Mirrorhold lacks lake, roads, and elevation variation")
        if path.as_posix().endswith("maps/nymara/crownwater.elm"):
            crown_tiles = data[tile_offset:height_offset]
            crown_heights = data[height_offset:height_offset + width * height * 36]
            required = {
                "3dobjects/nymara/mirrorhold_civic_tower.e3d": 8,
                "3dobjects/nymara/mirrorhold_public_fountain.e3d": 8,
                "3dobjects/nymara/mirrorhold_radial_bridge.e3d": 9,
                "3dobjects/nymara/crownwater_ferry_dock.e3d": 7,
                "3dobjects/nymara/crownwater_fishing_boat.e3d": 6,
                "3dobjects/nymara/crownwater_patrol_boat.e3d": 4,
                "3dobjects/nymara/crownwater_submerged_waystone.e3d": 6,
                "3dobjects/nymara/mirrorhold_lake_house.e3d": 6,
            }
            for landmark, minimum in required.items():
                if sum(name == landmark for name, *_ in object_records) < minimum:
                    raise ValueError(f"Crownwater is missing {landmark}")
            if any(math.hypot(x-58, y-58) < 3.0 for _, x, y, _ in object_records):
                raise ValueError("Crownwater arrival plaza is obstructed")
            if obj3_count < 62 or light_count < 12:
                raise ValueError("Crownwater lacks authored scenery or lighting")
            if set(crown_tiles) != {0, 1, 2, 3} or set(crown_heights) != {6, 11}:
                raise ValueError("Crownwater lacks islands, causeways, or water depth")
        if path.as_posix().endswith("maps/nymara/whitehorn_range.elm"):
            whitehorn_tiles = data[tile_offset:height_offset]
            whitehorn_heights = data[height_offset:height_offset + width * height * 36]
            required = {
                "3dobjects/nymara/whitehorn_monastery.e3d": 1,
                "3dobjects/nymara/whitehorn_glacier.e3d": 6,
                "3dobjects/nymara/whitehorn_rope_bridge.e3d": 5,
                "3dobjects/nymara/whitehorn_shrine.e3d": 6,
                "3dobjects/nymara/whitehorn_cairn.e3d": 10,
                "3dobjects/nymara/whitehorn_ice_cave.e3d": 4,
                "3dobjects/nymara/whitehorn_mine_entrance.e3d": 3,
            }
            for landmark, minimum in required.items():
                if sum(name == landmark for name, *_ in object_records) < minimum:
                    raise ValueError(f"Whitehorn Range is missing {landmark}")
            if any(math.hypot(x-58, y-58) < 3.0 for _, x, y, _ in object_records):
                raise ValueError("Whitehorn Range arrival is obstructed")
            if obj3_count < 45 or light_count < 12:
                raise ValueError("Whitehorn Range lacks authored scenery or lighting")
            if set(whitehorn_tiles) != {0, 1, 2, 3} or len(set(whitehorn_heights)) < 12:
                raise ValueError("Whitehorn Range lacks glacier and mountain relief")
        if path.as_posix().endswith("maps/nymara/amethyst_barrens.elm"):
            amethyst_tiles = data[tile_offset:height_offset]
            amethyst_heights = data[height_offset:height_offset + width * height * 36]
            required = {
                "3dobjects/nymara/glasswarden_observatory.e3d": 1,
                "3dobjects/nymara/amethyst_crystal_bridge.e3d": 7,
                "3dobjects/nymara/amethyst_geode_cave.e3d": 4,
                "3dobjects/nymara/amethyst_levitating_shards.e3d": 8,
                "3dobjects/nymara/amethyst_storm_ruin.e3d": 6,
                "3dobjects/nymara/resonant_crystal_cluster.e3d": 10,
                "3dobjects/nymara/glasswarden_field_station.e3d": 6,
            }
            for landmark, minimum in required.items():
                if sum(name == landmark for name, *_ in object_records) < minimum:
                    raise ValueError(f"Amethyst Barrens is missing {landmark}")
            if any(math.hypot(x-58, y-58) < 3.0 for _, x, y, _ in object_records):
                raise ValueError("Amethyst Barrens arrival is obstructed")
            if obj3_count < 50 or light_count < 12:
                raise ValueError("Amethyst Barrens lacks authored scenery or lighting")
            if set(amethyst_tiles) != {0, 1, 2, 3} or len(set(amethyst_heights)) < 10:
                raise ValueError("Amethyst Barrens lacks basin, roads, crystal fields, or relief")
        if path.as_posix().endswith("maps/nymara/sunmane_steppe.elm"):
            sunmane_tiles = data[tile_offset:height_offset]
            sunmane_heights = data[height_offset:height_offset + width * height * 36]
            required = {
                "3dobjects/nymara/orun_round_tent.e3d": 12,
                "3dobjects/nymara/orun_seasonal_market.e3d": 4,
                "3dobjects/nymara/orun_banner_shrine.e3d": 8,
                "3dobjects/nymara/sunmane_caravanserai.e3d": 4,
                "3dobjects/nymara/sunmane_windmill.e3d": 6,
                "3dobjects/nymara/sunmane_well.e3d": 4,
                "3dobjects/nymara/sunmane_animal_pen.e3d": 6,
                "3dobjects/nymara/sunmane_burial_mound.e3d": 6,
            }
            for landmark, minimum in required.items():
                if sum(name == landmark for name, *_ in object_records) < minimum:
                    raise ValueError(f"Sunmane Steppe is missing {landmark}")
            if any(math.hypot(x-58, y-58) < 3.0 for _, x, y, _ in object_records):
                raise ValueError("Sunmane Steppe arrival is obstructed")
            if obj3_count < 58 or light_count < 12:
                raise ValueError("Sunmane Steppe lacks authored scenery or lighting")
            if set(sunmane_tiles) != {0, 1, 2, 3} or len(set(sunmane_heights)) < 8:
                raise ValueError("Sunmane Steppe lacks camps, roads, grassland, or relief")
        if path.as_posix().endswith("maps/nymara/amberwood.elm"):
            amber_tiles = data[tile_offset:height_offset]
            amber_heights = data[height_offset:height_offset + width * height * 36]
            required = {
                "3dobjects/nymara/amberwood_estate.e3d": 1,
                "3dobjects/nymara/amberwood_hunting_lodge.e3d": 6,
                "3dobjects/nymara/amberwood_hollow_tree.e3d": 8,
                "3dobjects/nymara/amberwood_old_bridge.e3d": 4,
                "3dobjects/nymara/amberwood_tree.e3d": 16,
                "3dobjects/nymara/amberwood_ruin_arch.e3d": 6,
                "3dobjects/nymara/amberwood_garden_fountain.e3d": 4,
            }
            for landmark, minimum in required.items():
                if sum(name == landmark for name, *_ in object_records) < minimum:
                    raise ValueError(f"Amberwood is missing {landmark}")
            if any(math.hypot(x-58, y-58) < 3.0 for _, x, y, _ in object_records):
                raise ValueError("Amberwood arrival is obstructed")
            if obj3_count < 55 or light_count < 12:
                raise ValueError("Amberwood lacks authored scenery or lighting")
            if set(amber_tiles) != {0, 1, 2, 3} or len(set(amber_heights)) < 8:
                raise ValueError("Amberwood lacks estate, roads, old growth, or relief")
        if path.as_posix().endswith("maps/nymara/grey_moors.elm"):
            moor_tiles = data[tile_offset:height_offset]
            moor_heights = data[height_offset:height_offset + width * height * 36]
            required = {
                "3dobjects/nymara/grey_moor_barrow.e3d": 6,
                "3dobjects/nymara/grey_moor_standing_stones.e3d": 8,
                "3dobjects/nymara/grey_moor_boardwalk.e3d": 8,
                "3dobjects/nymara/grey_moor_crypt_entrance.e3d": 4,
                "3dobjects/nymara/grey_moor_abandoned_cottage.e3d": 6,
                "3dobjects/nymara/grey_moor_dead_tree.e3d": 10,
                "3dobjects/nymara/grey_moor_ritual_shrine.e3d": 5,
            }
            for landmark, minimum in required.items():
                if sum(name == landmark for name, *_ in object_records) < minimum:
                    raise ValueError(f"Grey Moors is missing {landmark}")
            if any(math.hypot(x-58, y-58) < 3.0 for _, x, y, _ in object_records):
                raise ValueError("Grey Moors arrival is obstructed")
            if obj3_count < 53 or light_count < 12:
                raise ValueError("Grey Moors lacks authored scenery or lighting")
            if set(moor_tiles) != {0, 1, 2, 3} or len(set(moor_heights)) < 8:
                raise ValueError("Grey Moors lacks barrows, causeways, bog, or relief")
        if path.as_posix().endswith("maps/nymara/drowned_crown.elm"):
            required = {
                "3dobjects/nymara/interiors/crownwater_drowned_floor.e3d": 12,
                "3dobjects/nymara/interiors/crownwater_underwater_wall.e3d": 14,
                "3dobjects/nymara/interiors/crownwater_submerged_arch.e3d": 6,
                "3dobjects/nymara/interiors/crownwater_water_channel.e3d": 8,
                "3dobjects/nymara/interiors/crownwater_drowned_statue.e3d": 4,
                "3dobjects/nymara/interiors/crownwater_shell_altar.e3d": 1,
            }
            for landmark, minimum in required.items():
                count = sum(name == landmark for name, *_ in object_records)
                if count < minimum:
                    raise ValueError(f"Drowned Crown is missing {landmark}")
            if any(math.hypot(x-58, y-10) < 4.0 for _, x, y, _ in object_records):
                raise ValueError("Drowned Crown arrival is obstructed")
            if obj3_count < 50 or light_count < 12:
                raise ValueError("Drowned Crown lacks authored scenery or lighting")
        if path.as_posix().endswith("maps/nymara/whitehorn_glacier_temple.elm"):
            required = {
                "3dobjects/nymara/interiors/whitehorn_monastery_floor.e3d": 12,
                "3dobjects/nymara/interiors/whitehorn_monastery_wall.e3d": 14,
                "3dobjects/nymara/interiors/whitehorn_ice_arch.e3d": 6,
                "3dobjects/nymara/interiors/whitehorn_prayer_column.e3d": 8,
                "3dobjects/nymara/interiors/whitehorn_mine_support.e3d": 4,
                "3dobjects/nymara/interiors/whitehorn_glacier_altar.e3d": 1,
            }
            for landmark, minimum in required.items():
                count = sum(name == landmark for name, *_ in object_records)
                if count < minimum:
                    raise ValueError(f"Whitehorn temple is missing {landmark}")
            if any(math.hypot(x-58, y-10) < 4.0 for _, x, y, _ in object_records):
                raise ValueError("Whitehorn temple arrival is obstructed")
            if obj3_count < 50 or light_count < 12:
                raise ValueError("Whitehorn temple lacks authored scenery or lighting")
        if path.as_posix().endswith("maps/nymara/resonant_vault.elm"):
            required = {
                "3dobjects/nymara/interiors/glasswarden_laboratory_floor.e3d": 12,
                "3dobjects/nymara/interiors/glasswarden_brass_wall.e3d": 14,
                "3dobjects/nymara/interiors/glasswarden_experiment_table.e3d": 6,
                "3dobjects/nymara/interiors/glasswarden_archive_shelf.e3d": 6,
                "3dobjects/nymara/interiors/glasswarden_crystal_brazier.e3d": 8,
                "3dobjects/nymara/interiors/glasswarden_observatory_lens.e3d": 1,
            }
            for landmark, minimum in required.items():
                count = sum(name == landmark for name, *_ in object_records)
                if count < minimum:
                    raise ValueError(f"Resonant Vault is missing {landmark}")
            if any(math.hypot(x-58, y-10) < 4.0 for _, x, y, _ in object_records):
                raise ValueError("Resonant Vault arrival is obstructed")
            if obj3_count < 53 or light_count < 12:
                raise ValueError("Resonant Vault lacks authored scenery or lighting")
        if path.as_posix().endswith("maps/nymara/amberwood_estate.elm"):
            required = {
                "3dobjects/nymara/interiors/amberwood_manor_floor.e3d": 12,
                "3dobjects/nymara/interiors/amberwood_manor_wall.e3d": 14,
                "3dobjects/nymara/interiors/amberwood_estate_door.e3d": 6,
                "3dobjects/nymara/interiors/amberwood_banquet_table.e3d": 4,
                "3dobjects/nymara/interiors/amberwood_estate_bed.e3d": 6,
                "3dobjects/nymara/interiors/amberwood_overgrown_statue.e3d": 4,
            }
            for landmark, minimum in required.items():
                count = sum(name == landmark for name, *_ in object_records)
                if count < minimum:
                    raise ValueError(f"Amberwood Estate is missing {landmark}")
            if any(math.hypot(x-58, y-10) < 4.0 for _, x, y, _ in object_records):
                raise ValueError("Amberwood Estate arrival is obstructed")
            if obj3_count < 52 or light_count < 12:
                raise ValueError("Amberwood Estate lacks authored scenery or lighting")
        if path.as_posix().endswith("maps/nymara/grey_moor_barrows.elm"):
            required = {
                "3dobjects/nymara/interiors/grey_moor_crypt_floor.e3d": 12,
                "3dobjects/nymara/interiors/grey_moor_crypt_wall.e3d": 14,
                "3dobjects/nymara/interiors/grey_moor_barrow_arch.e3d": 6,
                "3dobjects/nymara/interiors/grey_moor_sarcophagus.e3d": 8,
                "3dobjects/nymara/interiors/grey_moor_spike_trap.e3d": 4,
                "3dobjects/nymara/interiors/grey_moor_ritual_altar.e3d": 1,
            }
            for landmark, minimum in required.items():
                count = sum(name == landmark for name, *_ in object_records)
                if count < minimum:
                    raise ValueError(f"Grey Moor Barrows is missing {landmark}")
            if any(math.hypot(x-58, y-10) < 4.0 for _, x, y, _ in object_records):
                raise ValueError("Grey Moor Barrows arrival is obstructed")
            if obj3_count < 51 or light_count < 12:
                raise ValueError("Grey Moor Barrows lacks authored scenery or lighting")
        if path.as_posix().endswith("maps/nymara/ssarathi_royal_archive.elm"):
            required = {
                "3dobjects/nymara/interiors/ssarathi_scaled_floor.e3d": 12,
                "3dobjects/nymara/interiors/ssarathi_curved_wall.e3d": 14,
                "3dobjects/nymara/interiors/ssarathi_water_arch.e3d": 6,
                "3dobjects/nymara/interiors/ssarathi_archive_shelf.e3d": 8,
                "3dobjects/nymara/interiors/ssarathi_royal_statue.e3d": 4,
                "3dobjects/nymara/interiors/ssarathi_vault_trap.e3d": 4,
            }
            for landmark, minimum in required.items():
                count = sum(name == landmark for name, *_ in object_records)
                if count < minimum:
                    raise ValueError(f"Ssarthi Royal Archive is missing {landmark}")
            if any(math.hypot(x-58, y-10) < 4.0 for _, x, y, _ in object_records):
                raise ValueError("Ssarthi Royal Archive arrival is obstructed")
            if obj3_count < 54 or light_count < 12:
                raise ValueError("Ssarthi Royal Archive lacks authored scenery or lighting")
        if path.as_posix().endswith("maps/nymara/manymouth_flooded_labyrinth.elm"):
            required = {
                "3dobjects/nymara/interiors/manymouth_flooded_floor.e3d": 12,
                "3dobjects/nymara/interiors/manymouth_stilt_wall.e3d": 14,
                "3dobjects/nymara/interiors/manymouth_boardwalk_section.e3d": 10,
                "3dobjects/nymara/interiors/manymouth_flood_channel.e3d": 8,
                "3dobjects/nymara/interiors/manymouth_smuggler_shelf.e3d": 6,
                "3dobjects/nymara/interiors/manymouth_fishing_crates.e3d": 6,
            }
            for landmark, minimum in required.items():
                count = sum(name == landmark for name, *_ in object_records)
                if count < minimum:
                    raise ValueError(f"Manymouth Labyrinth is missing {landmark}")
            if any(math.hypot(x-58, y-10) < 4.0 for _, x, y, _ in object_records):
                raise ValueError("Manymouth Labyrinth arrival is obstructed")
            if obj3_count < 62 or light_count < 12:
                raise ValueError("Manymouth Labyrinth lacks authored scenery or lighting")


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
        vertex_total = 0
        for submesh in cal_xml(path).findall("SUBMESH"):
            vertices = {}
            normals = {}
            for vertex in submesh.findall("VERTEX"):
                ident = int(vertex.attrib["ID"])
                vertices[ident] = tuple(map(float, vertex.findtext("POS").split()))
                normals[ident] = tuple(map(float, vertex.findtext("NORM").split()))
                influences = vertex.findall("INFLUENCE")
                if not influences or int(vertex.attrib.get("NUMINFLUENCES", "-1")) != len(influences):
                    raise ValueError(f"missing or incorrect bone influences in {path}: {ident}")
                if any(int(influence.attrib["ID"]) < 0 for influence in influences):
                    raise ValueError(f"negative bone influence in {path}: {ident}")
                if abs(sum(float(influence.text) for influence in influences) - 1.0) > 1e-5:
                    raise ValueError(f"unnormalized bone influences in {path}: {ident}")
            vertex_total += len(vertices)
            for face in submesh.findall("FACE"):
                a, b, c = map(int, face.attrib["VERTEXID"].split())
                ab = tuple(vertices[b][i] - vertices[a][i] for i in range(3))
                ac = tuple(vertices[c][i] - vertices[a][i] for i in range(3))
                cross = (ab[1]*ac[2] - ab[2]*ac[1],
                         ab[2]*ac[0] - ab[0]*ac[2],
                         ab[0]*ac[1] - ab[1]*ac[0])
                if sum(cross[i] * normals[a][i] for i in range(3)) <= 0.0:
                    raise ValueError(f"inward or degenerate face in {path}: {a} {b} {c}")
        if "/nymara/" in path.as_posix() and vertex_total < 400:
            raise ValueError(f"Nymara mesh fell back to placeholder topology: {path}")
        four_gates_creatures = {
            "mirrorfin_otter.xmf": 700,
            "reedhorn_stag.xmf": 900,
            "gate_turtle.xmf": 760,
            "lakeglass_drake.xmf": 760,
        }
        if path.name in four_gates_creatures and vertex_total < four_gates_creatures[path.name]:
            raise ValueError(f"Four Gates creature fell back to generic topology: {path}")

def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError(f"invalid PNG: {path}")
    return struct.unpack_from(">II", data, 16)

def validate_nymara_textures(root: Path) -> None:
    actor_textures = sorted(root.glob("actors/nymara/**/*.png"))
    if not actor_textures:
        raise ValueError("no Nymara actor textures found")
    for path in actor_textures:
        if png_dimensions(path) != (512, 512):
            raise ValueError(f"Nymara actor texture is not 512x512: {path}")
    world_textures = sorted(root.glob("3dobjects/nymara/**/*.png"))
    for path in world_textures:
        if png_dimensions(path) != (256, 256):
            raise ValueError(f"Nymara world material is not 256x256: {path}")


def validate_four_gates_scenery(root: Path) -> None:
    minimum_vertices = {
        "four_gates_civic_wall.e3d": 240,
        "four_gates_civic_tower.e3d": 520,
        "four_gates_radial_bridge.e3d": 480,
        "four_gates_civic_pavilion.e3d": 440,
        "four_gates_park_tree.e3d": 400,
        "four_gates_gatehouse.e3d": 800,
        "four_gates_waystone.e3d": 320,
        "four_gates_lantern.e3d": 220,
        "resonant_crystal.e3d": 150,
        "stormglass_shard.e3d": 150,
        "mirror_reed.e3d": 150,
        "sunmane_seed.e3d": 170,
    }
    scenery = root / "3dobjects/nymara"
    for filename, minimum in minimum_vertices.items():
        path = scenery / filename
        data = path.read_bytes()
        if len(data) < 68 or data[:4] != b"e3dx" or data[4:8] != bytes((1, 1, 0, 0)):
            raise ValueError(f"invalid Four Gates E3D header: {path}")
        digest, offset = struct.unpack_from("<16si", data, 8)
        if offset != 28 or hashlib.md5(data[offset:]).digest() != digest:
            raise ValueError(f"invalid Four Gates E3D payload digest: {path}")
        vertices, vertex_size, vertex_offset, indices, index_size = \
            struct.unpack_from("<5i", data, offset)
        if vertices < minimum or indices < vertices or indices % 3:
            raise ValueError(f"Four Gates scenery fell back to placeholder topology: {path}")
        if vertex_size != 32 or vertex_offset != 68 or index_size != 2:
            raise ValueError(f"invalid Four Gates E3D section layout: {path}")
        if png_dimensions(path.with_suffix(".png")) != (256, 256):
            raise ValueError(f"invalid Four Gates material resolution: {path}")
    for tile_id in range(4, 8):
        path = root / f"3dobjects/tile{tile_id}.png"
        if png_dimensions(path) != (256, 256):
            raise ValueError(f"invalid Four Gates terrain material: {path}")


def validate_four_gates_npcs_equipment(root: Path) -> None:
    actors = ET.parse(root / "actor_defs/actor_defs.xml").getroot()
    expected_actors = {
        300: ("actors/nymara/npcs/luminous_official_f.xmf", 1050),
        301: ("actors/nymara/npcs/luminous_guard_f.xmf", 1120),
        302: ("actors/nymara/npcs/luminous_merchant_f.xmf", 980),
        303: ("actors/nymara/npcs/luminous_ferryman_f.xmf", 1050),
        304: ("actors/nymara/npcs/luminous_scholar_f.xmf", 1050),
        305: ("actors/nymara/npcs/luminous_lake_priest_f.xmf", 1050),
        306: ("actors/nymara/npcs/luminous_civilian_f.xmf", 980),
        307: ("actors/nymara/npcs/luminous_official_m.xmf", 1050),
        308: ("actors/nymara/npcs/luminous_guard_m.xmf", 1120),
        309: ("actors/nymara/npcs/luminous_merchant_m.xmf", 980),
        310: ("actors/nymara/npcs/luminous_ferryman_m.xmf", 1050),
        311: ("actors/nymara/npcs/luminous_scholar_m.xmf", 1050),
        312: ("actors/nymara/npcs/luminous_lake_priest_m.xmf", 1050),
        313: ("actors/nymara/npcs/luminous_civilian_m.xmf", 980),
    }
    for actor_id, (mesh_name, minimum) in expected_actors.items():
        actor = actors.find(f"actor[@id='{actor_id}']")
        if actor is None or actor.findtext("mesh") != mesh_name:
            raise ValueError(f"Four Gates NPC actor mapping changed: {actor_id}")
        vertices = sum(int(sub.attrib["NUMVERTICES"])
                       for sub in cal_xml(root / mesh_name).findall("SUBMESH"))
        if vertices < minimum:
            raise ValueError(f"Four Gates NPC fell back to generic topology: {mesh_name}")
    expected_items = {
        1000: ("civic_blade", "weapon", 120),
        1001: ("lakeguard_spear", "weapon", 100),
        1002: ("mirror_shield", "shield", 190),
        1003: ("ceremonial_mail", "body", 230),
        1004: ("civic_mantle", "cape", 110),
        1005: ("ferry_hook", "weapon", 130),
    }
    items = {item["item_id"]: item for item in
             json.loads((root / "nymara_equipment.json").read_text())["items"]}
    for item_id, (name, slot, minimum) in expected_items.items():
        item = items.get(item_id)
        if item is None or item["id"] != name or item["slot"] != slot:
            raise ValueError(f"Four Gates equipment mapping changed: {item_id}")
        path = root / item["model"]
        data = path.read_bytes()
        vertices = struct.unpack_from("<i", data, 28)[0]
        if vertices < minimum:
            raise ValueError(f"Four Gates equipment fell back to placeholder topology: {path}")
        if png_dimensions(path.with_suffix(".png")) != (256, 256):
            raise ValueError(f"invalid Four Gates equipment material: {path}")
        if png_dimensions(root / item["icon"]) != (64, 64):
            raise ValueError(f"invalid Four Gates equipment icon: {item['icon']}")


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
    validate_nymara_textures(root)
    validate_four_gates_scenery(root)
    validate_four_gates_npcs_equipment(root)
    validate_animations(root)
    validate_customization_dds(root)
    validate_map_dds(root)
    print("Validated every generated ELM, Cal3D XML family, and customization DDS")


if __name__ == "__main__":
    main()

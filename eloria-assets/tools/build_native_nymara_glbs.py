#!/usr/bin/env python3
"""Build the Godot-native Nymara actor library from clean glTF 2.0 sources.

This pipeline deliberately does not consume the legacy Cal3D humanoid or creature
generators.  Playable races retain the proven Quaternius 65-joint skin, topology,
weights, and animation bone names.  Creature meshes, rigs, and clips are authored
here from scratch.  Equipment is emitted as independent GLBs for BoneAttachment3D.
"""
from __future__ import annotations

import argparse
import copy
import io
import json
import math
from pathlib import Path
import struct
import numpy as np
from PIL import Image


COMPONENT_DTYPES = {5121: "<u1", 5122: "<i2", 5123: "<u2", 5125: "<u4", 5126: "<f4"}
COMPONENT_TYPES = {np.dtype("uint8"): 5121, np.dtype("int16"): 5122,
                   np.dtype("uint16"): 5123, np.dtype("uint32"): 5125,
                   np.dtype("float32"): 5126}
TYPE_WIDTHS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}

RACES = {
    "votary": {"label": "Whitehorn Votary", "color": (139, 173, 188),
                "accent": (226, 231, 228), "shape": (1.075, 1.035, 1.02, .97), "feature": "ears"},
    "glasswarden": {"label": "Glasswarden", "color": (121, 91, 158),
                     "accent": (103, 184, 191), "shape": (.965, 1.10, 1.03, 1.03), "feature": "crystal"},
    "orun": {"label": "Orun", "color": (172, 99, 47),
             "accent": (219, 166, 72), "shape": (1.02, 1.04, 1.01, .98), "feature": "mane"},
    "greyhaven": {"label": "Greyhaven", "color": (62, 86, 101),
                   "accent": (154, 174, 171), "shape": (1.04, 1.10, 1.08, 1.04), "feature": "brow"},
    "ssarathi": {"label": "Ssarathi", "color": (52, 116, 91),
                  "accent": (184, 151, 70), "shape": (1.075, .98, .96, 1.08), "feature": "scaled"},
    "stoneborn": {"label": "Stoneborn", "color": (118, 105, 91),
                   "accent": (103, 184, 191), "shape": (1.05, 1.16, 1.10, 1.04), "feature": "stone"},
    "mycelari": {"label": "Mycelari", "color": (116, 137, 91),
                  "accent": (211, 151, 98), "shape": (1.02, 1.04, 1.04, 1.10), "feature": "fungal"},
}
PLAYER_ACTOR_TYPES = {
    2: "votary_female", 3: "votary_male", 4: "glasswarden_female", 5: "glasswarden_male",
    37: "orun_female", 38: "orun_male", 39: "greyhaven_female", 40: "greyhaven_male",
    41: "ssarathi_female", 42: "ssarathi_male", 79: "stoneborn_female", 80: "stoneborn_male",
    81: "mycelari_female", 82: "mycelari_male",
}

CREATURES = (
    # Tuple IDs retain the authored sequence; add the four existing upstream
    # creature slots when registering against eloria-server.
    (200, "emberfox", "Emberfox", "fox", (190, 82, 37), (236, 152, 61), .82),
    (201, "mossback_boar", "Mossback Boar", "boar", (69, 91, 54), (151, 120, 58), 1.18),
    (202, "ridgehorn", "Ridgehorn", "ram", (132, 112, 77), (214, 174, 91), 1.05),
    (203, "miretoad", "Miretoad", "toad", (56, 111, 70), (160, 178, 72), 1.15),
    (204, "ash_crawler", "Ash Crawler", "lizard", (67, 62, 66), (172, 63, 54), 1.30),
    (205, "frost_maw", "Frost Maw", "wolf", (136, 183, 198), (224, 245, 247), 1.18),
    (206, "bog_lurker", "Bog Lurker", "toad", (48, 83, 65), (111, 151, 83), 1.42),
    (207, "sunscale_drake", "Sunscale Drake", "drake", (184, 117, 42), (57, 145, 141), 1.35),
    (208, "red_fox", "Red Fox", "fox", (179, 74, 41), (237, 166, 91), .74),
    (209, "snow_hare", "Snow Hare", "hare", (210, 220, 220), (134, 184, 203), .62),
    (210, "mountain_goat", "Mountain Goat", "ram", (146, 139, 121), (96, 82, 67), .92),
    (211, "black_bear", "Black Bear", "bear", (43, 39, 38), (100, 88, 68), 1.28),
    (212, "elk", "Elk", "elk", (130, 91, 54), (209, 138, 58), 1.08),
    (213, "wild_boar", "Wild Boar", "boar", (88, 73, 59), (151, 116, 72), 1.04),
    (214, "dire_wolf", "Dire Wolf", "wolf", (70, 80, 89), (132, 155, 166), 1.13),
    (215, "frost_tiger", "Frost Tiger", "cat", (174, 200, 207), (81, 132, 160), 1.14),
    (216, "giant_crocodile", "Giant Crocodile", "crocodile", (62, 101, 60), (139, 151, 62), 1.55),
    (217, "fire_salamander", "Fire Salamander", "lizard", (184, 69, 33), (245, 153, 48), 1.02),
    (218, "thunder_ram", "Thunder Ram", "ram", (102, 99, 94), (91, 160, 188), 1.24),
    (219, "giant_rat", "Giant Rat", "rat", (105, 85, 70), (179, 138, 92), .84),
    (220, "raccoon", "Raccoon", "fox", (93, 94, 90), (45, 48, 54), .72),
    (221, "river_otter", "River Otter", "otter", (94, 70, 47), (51, 111, 120), .75),
    (222, "porcupine", "Porcupine", "porcupine", (107, 82, 55), (48, 44, 38), .82),
    (223, "moose", "Moose", "elk", (91, 70, 48), (171, 133, 77), 1.28),
    (224, "lynx", "Lynx", "cat", (157, 126, 88), (71, 65, 61), .82),
    (225, "desert_tortoise", "Desert Tortoise", "tortoise", (119, 112, 73), (190, 156, 68), 1.06),
    (226, "saber_tooth_cat", "Saber-Tooth Cat", "cat", (176, 137, 82), (235, 220, 173), 1.20),
    (227, "armored_rhino", "Armored Rhino", "rhino", (104, 105, 99), (62, 118, 128), 1.48),
    (228, "giant_komodo", "Giant Komodo", "lizard", (88, 109, 63), (183, 140, 54), 1.42),
    (229, "ice_bear", "Ice Bear", "bear", (188, 210, 218), (87, 151, 190), 1.48),
    (230, "lava_hound", "Lava Hound", "wolf", (154, 55, 30), (246, 119, 38), 1.17),
    (231, "two_tailed_fox", "Two-Tailed Fox", "two_tail_fox", (183, 100, 44), (63, 151, 164), .90),
)
CREATURE_ACTOR_TYPE_OFFSET = 4

EQUIPMENT = (
    # part 0: weapons
    ("amberwood_longbow", "Amberwood Longbow", 0, 100, "bow", (74, 111, 61), (210, 145, 57)),
    ("ranger_leafblade", "Ranger Leafblade", 0, 101, "sword", (88, 116, 68), (196, 191, 139)),
    ("glasswarden_staff", "Glasswarden Resonance Staff", 0, 102, "staff", (78, 62, 121), (96, 205, 218)),
    ("glasswarden_pick", "Glasswarden Crystal Pick", 0, 103, "pick", (77, 64, 111), (130, 194, 223)),
    ("greyhaven_cutlass", "Greyhaven Cutlass", 0, 104, "sword", (49, 74, 91), (193, 198, 190)),
    ("greyhaven_harpoon", "Greyhaven Harpoon", 0, 105, "spear", (61, 79, 88), (176, 194, 188)),
    ("orun_sun_spear", "Orun Sun Spear", 0, 106, "spear", (151, 77, 34), (221, 169, 70)),
    ("ssarathi_glaive", "Ssarathi River Glaive", 0, 107, "glaive", (42, 105, 83), (188, 153, 67)),
    ("luminous_mace", "Luminous Compact Mace", 0, 108, "mace", (40, 117, 132), (214, 190, 105)),
    ("votary_ice_sword", "Votary Ice Sword", 0, 109, "sword", (112, 151, 173), (220, 240, 244)),
    ("stoneborn_hammer", "Stoneborn Memory Hammer", 0, 110, "hammer", (101, 92, 84), (84, 189, 199)),
    ("mycelari_staff", "Mycelari Spore Staff", 0, 111, "staff", (93, 113, 64), (210, 145, 91)),
    ("four_gates_guard_spear_native", "Four Gates Guardian Spear", 0, 112, "spear", (41, 116, 127), (224, 193, 103)),
    ("maritime_crossbow", "Greyhaven Maritime Crossbow", 0, 113, "crossbow", (66, 72, 76), (176, 132, 72)),
    # part 1: shields
    ("amberwood_roundshield", "Amberwood Roundshield", 1, 100, "roundshield", (83, 96, 58), (192, 124, 47)),
    ("glasswarden_shield", "Glasswarden Crystal Shield", 1, 101, "kite", (80, 63, 123), (85, 204, 216)),
    ("greyhaven_anchor_shield", "Greyhaven Anchor Shield", 1, 102, "roundshield", (46, 72, 91), (173, 187, 183)),
    ("orun_sun_shield", "Orun Sun Shield", 1, 103, "roundshield", (151, 76, 34), (219, 163, 62)),
    ("ssarathi_shell_shield", "Ssarathi Shell Shield", 1, 104, "shell", (43, 111, 89), (187, 151, 67)),
    ("four_gates_guard_shield_native", "Four Gates Guardian Shield", 1, 105, "kite", (39, 112, 124), (219, 190, 101)),
    # part 2: capes
    ("amberwood_leaf_cape", "Amberwood Leaf Cape", 2, 100, "cape", (59, 91, 49), (180, 100, 41)),
    ("glasswarden_crystal_cape", "Glasswarden Crystal Cape", 2, 101, "cape", (75, 55, 113), (88, 185, 212)),
    ("greyhaven_storm_cape", "Greyhaven Storm Cape", 2, 102, "cape", (44, 62, 76), (139, 160, 161)),
    ("orun_rider_cape", "Orun Rider Cape", 2, 103, "cape", (128, 66, 32), (206, 148, 59)),
    ("ssarathi_frond_cape", "Ssarathi Frond Cape", 2, 104, "cape", (36, 100, 79), (80, 147, 94)),
    ("four_gates_guard_cape_native", "Four Gates Guardian Cape", 2, 105, "cape", (33, 93, 109), (214, 183, 95)),
    # part 3: helmets
    ("amberwood_ranger_hood", "Amberwood Ranger Hood", 3, 100, "hood", (55, 87, 50), (143, 104, 50)),
    ("glasswarden_helm", "Glasswarden Crystal Helm", 3, 101, "helm", (75, 58, 116), (92, 202, 217)),
    ("greyhaven_helm", "Greyhaven League Helm", 3, 102, "helm", (56, 68, 76), (174, 184, 181)),
    ("orun_sunmane_helm", "Orun Sunmane Helm", 3, 103, "helm", (146, 72, 32), (218, 160, 61)),
    ("ssarathi_crest_helm", "Ssarathi Crest Helm", 3, 104, "crest", (39, 103, 82), (186, 151, 66)),
    ("luminous_circlet", "Luminous Compact Circlet", 3, 105, "circlet", (42, 124, 136), (224, 199, 111)),
    ("votary_fur_hood", "Votary Fur Hood", 3, 106, "hood", (113, 145, 164), (223, 230, 226)),
    ("stoneborn_crown", "Stoneborn Crystal Crown", 3, 107, "crest", (99, 92, 86), (92, 190, 201)),
    ("mycelari_cap", "Mycelari Spore Cap", 3, 108, "mushroom", (98, 116, 67), (208, 141, 87)),
    # part 4: legs
    ("amberwood_ranger_legs", "Amberwood Ranger Leggings", 4, 100, "legs", (64, 82, 48), (128, 83, 42)),
    ("glasswarden_greaves", "Glasswarden Crystal Greaves", 4, 101, "legs", (71, 55, 108), (89, 185, 207)),
    ("greyhaven_trousers", "Greyhaven League Trousers", 4, 102, "legs", (44, 59, 70), (121, 143, 145)),
    ("orun_rider_legs", "Orun Rider Leggings", 4, 103, "legs", (121, 64, 33), (193, 132, 57)),
    ("ssarathi_scale_legs", "Ssarathi Scale Leggings", 4, 104, "legs", (37, 93, 75), (143, 137, 67)),
    ("votary_winter_legs", "Votary Winter Leggings", 4, 105, "legs", (96, 125, 143), (211, 222, 219)),
    ("luminous_casual_pants", "Luminous Casual Pants", 4, 106, "pants", (47, 65, 83), (52, 126, 139)),
    # part 5: bodies
    ("amberwood_ranger_cuirass", "Amberwood Ranger Cuirass", 5, 100, "cuirass", (64, 91, 52), (170, 103, 43)),
    ("glasswarden_cuirass", "Glasswarden Crystal Cuirass", 5, 101, "cuirass", (76, 58, 116), (90, 195, 211)),
    ("greyhaven_coat", "Greyhaven League Coat", 5, 102, "coat", (46, 66, 80), (146, 166, 165)),
    ("orun_sun_cuirass", "Orun Sun Cuirass", 5, 103, "cuirass", (146, 72, 32), (219, 163, 64)),
    ("ssarathi_scale_cuirass", "Ssarathi Scale Cuirass", 5, 104, "cuirass", (38, 101, 81), (183, 148, 66)),
    ("luminous_turquoise_robe", "Luminous Turquoise Robe", 5, 105, "robe", (39, 118, 132), (222, 198, 110)),
    ("votary_fur_mantle", "Votary Fur Mantle", 5, 106, "coat", (104, 136, 156), (223, 231, 228)),
    ("stoneborn_plate", "Stoneborn Memory Plate", 5, 107, "cuirass", (101, 94, 86), (88, 184, 194)),
    ("mycelari_mantle", "Mycelari Spore Mantle", 5, 108, "robe", (91, 116, 66), (205, 142, 90)),
    ("four_gates_guard_cuirass", "Four Gates Guardian Cuirass", 5, 109, "cuirass", (40, 112, 125), (219, 190, 102)),
    ("luminous_short_sleeve_shirt", "Luminous Short-Sleeve Shirt", 5, 110, "shirt", (45, 125, 139), (222, 198, 110)),
    # part 6: boots
    ("amberwood_ranger_boots", "Amberwood Ranger Boots", 6, 100, "boots", (78, 55, 37), (137, 92, 46)),
    ("glasswarden_boots", "Glasswarden Crystal Boots", 6, 101, "boots", (70, 55, 104), (88, 181, 200)),
    ("greyhaven_boots", "Greyhaven League Boots", 6, 102, "boots", (47, 55, 61), (114, 126, 125)),
    ("orun_rider_boots", "Orun Rider Boots", 6, 103, "boots", (103, 58, 35), (179, 116, 53)),
    ("ssarathi_scale_boots", "Ssarathi Scale Boots", 6, 104, "boots", (39, 88, 72), (132, 126, 64)),
    ("votary_winter_boots", "Votary Winter Boots", 6, 105, "boots", (91, 112, 125), (205, 216, 213)),
    ("luminous_casual_boots", "Luminous Casual Boots", 6, 106, "boots", (64, 47, 39), (52, 126, 139)),
    # part 7: neck
    ("amberwood_amulet", "Amberwood Leaf Amulet", 7, 100, "amulet", (76, 104, 51), (211, 137, 50)),
    ("glasswarden_resonator", "Glasswarden Resonator", 7, 101, "amulet", (75, 58, 112), (89, 198, 215)),
    ("greyhaven_compass", "Greyhaven Compass", 7, 102, "amulet", (50, 73, 88), (192, 168, 91)),
    ("orun_sun_amulet", "Orun Sun Amulet", 7, 103, "amulet", (146, 73, 34), (220, 166, 66)),
    ("ssarathi_shell_amulet", "Ssarathi Shell Amulet", 7, 104, "amulet", (41, 101, 82), (186, 151, 68)),
    ("luminous_orbit_amulet", "Luminous Orbit Amulet", 7, 105, "amulet", (42, 120, 133), (222, 198, 109)),
)


def align4(value: int) -> int:
    return (value + 3) & ~3


def quat(axis: str, angle: float) -> list[float]:
    half = angle * .5
    values = {"x": [math.sin(half), 0., 0., math.cos(half)],
              "y": [0., math.sin(half), 0., math.cos(half)],
              "z": [0., 0., math.sin(half), math.cos(half)]}
    return values[axis]


class GLB:
    def __init__(self, *, generator: str = "Eloria native Nymara builder"):
        self.binary = bytearray()
        self.doc = {"asset": {"version": "2.0", "generator": generator},
                    "scene": 0, "scenes": [{"nodes": []}], "nodes": [],
                    "meshes": [], "materials": [], "bufferViews": [],
                    "accessors": [], "buffers": [{"byteLength": 0}]}

    def bytes_view(self, raw: bytes, *, target: int | None = None) -> int:
        while len(self.binary) & 3:
            self.binary.append(0)
        offset = len(self.binary)
        self.binary.extend(raw)
        view = {"buffer": 0, "byteOffset": offset, "byteLength": len(raw)}
        if target is not None:
            view["target"] = target
        self.doc["bufferViews"].append(view)
        return len(self.doc["bufferViews"]) - 1

    def accessor(self, values: np.ndarray, gltf_type: str, *, target: int | None = None,
                 normalized: bool = False, bounds: bool = False) -> int:
        values = np.ascontiguousarray(values)
        component = COMPONENT_TYPES[values.dtype]
        view = self.bytes_view(values.tobytes(), target=target)
        spec = {"bufferView": view, "componentType": component,
                "count": int(values.shape[0]), "type": gltf_type}
        if normalized:
            spec["normalized"] = True
        if bounds:
            matrix = values.reshape(len(values), -1)
            spec["min"] = [float(v) for v in matrix.min(axis=0)]
            spec["max"] = [float(v) for v in matrix.max(axis=0)]
        self.doc["accessors"].append(spec)
        return len(self.doc["accessors"]) - 1

    def material(self, name: str, color: tuple[int, int, int], *, metallic: float = 0.,
                 roughness: float = .78, emissive: tuple[int, int, int] | None = None,
                 texture_png: bytes | None = None, double_sided: bool = False) -> int:
        factor = [c / 255. for c in color] + [1.]
        pbr = {"baseColorFactor": factor, "metallicFactor": metallic,
               "roughnessFactor": roughness}
        if texture_png is not None:
            view = self.bytes_view(texture_png)
            self.doc.setdefault("images", []).append(
                {"name": name + " Atlas", "bufferView": view, "mimeType": "image/png"})
            image = len(self.doc["images"]) - 1
            self.doc.setdefault("samplers", []).append(
                {"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497})
            sampler = len(self.doc["samplers"]) - 1
            self.doc.setdefault("textures", []).append({"source": image, "sampler": sampler})
            pbr["baseColorTexture"] = {"index": len(self.doc["textures"]) - 1}
        material = {"name": name, "pbrMetallicRoughness": pbr, "doubleSided": double_sided}
        if emissive is not None:
            material["emissiveFactor"] = [c / 255. for c in emissive]
        self.doc["materials"].append(material)
        return len(self.doc["materials"]) - 1

    def primitive(self, positions: np.ndarray, normals: np.ndarray, uvs: np.ndarray,
                  indices: np.ndarray, material: int, *, joints: np.ndarray | None = None,
                  weights: np.ndarray | None = None) -> dict:
        attributes = {
            "POSITION": self.accessor(positions.astype("float32"), "VEC3", target=34962, bounds=True),
            "NORMAL": self.accessor(normals.astype("float32"), "VEC3", target=34962),
            "TEXCOORD_0": self.accessor(uvs.astype("float32"), "VEC2", target=34962),
        }
        if joints is not None and weights is not None:
            attributes["JOINTS_0"] = self.accessor(joints.astype("uint16"), "VEC4", target=34962)
            attributes["WEIGHTS_0"] = self.accessor(weights.astype("float32"), "VEC4", target=34962)
        return {"attributes": attributes,
                "indices": self.accessor(indices.astype("uint32").reshape(-1), "SCALAR", target=34963),
                "material": material, "mode": 4}

    def mesh_node(self, name: str, primitives: list[dict], *, skin: int | None = None,
                  parent: int | None = None) -> int:
        self.doc["meshes"].append({"name": name, "primitives": primitives})
        node = {"name": name, "mesh": len(self.doc["meshes"]) - 1}
        if skin is not None:
            node["skin"] = skin
        self.doc["nodes"].append(node)
        index = len(self.doc["nodes"]) - 1
        if parent is None:
            self.doc["scenes"][0]["nodes"].append(index)
        else:
            self.doc["nodes"][parent].setdefault("children", []).append(index)
        return index

    def write(self, path: Path) -> None:
        self.doc["buffers"][0]["byteLength"] = len(self.binary)
        encoded = json.dumps(self.doc, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        encoded += b" " * (align4(len(encoded)) - len(encoded))
        binary = bytes(self.binary) + b"\0" * (align4(len(self.binary)) - len(self.binary))
        total = 12 + 8 + len(encoded) + 8 + len(binary)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"glTF" + struct.pack("<II", 2, total)
                         + struct.pack("<II", len(encoded), 0x4E4F534A) + encoded
                         + struct.pack("<II", len(binary), 0x004E4942) + binary)


def read_accessor(document: dict, binary: bytes, index: int) -> np.ndarray:
    spec = document["accessors"][index]
    view = document["bufferViews"][spec["bufferView"]]
    dtype = np.dtype(COMPONENT_DTYPES[spec["componentType"]])
    width = TYPE_WIDTHS[spec["type"]]
    start = view.get("byteOffset", 0) + spec.get("byteOffset", 0)
    stride = view.get("byteStride", dtype.itemsize * width)
    shape = (spec["count"],) if width == 1 else (spec["count"], width)
    strides = (stride,) if width == 1 else (stride, dtype.itemsize)
    values = np.ndarray(shape, dtype=dtype, buffer=binary, offset=start, strides=strides).copy()
    if spec.get("normalized"):
        if np.issubdtype(dtype, np.unsignedinteger):
            values = values.astype(np.float32) / np.iinfo(dtype).max
        else:
            values = np.maximum(values.astype(np.float32) / np.iinfo(dtype).max, -1.)
    return values


def recolored_texture(path: Path, base: tuple[int, int, int], accent: tuple[int, int, int],
                      feature: str) -> bytes:
    image = Image.open(path).convert("RGBA").resize((512, 512), Image.Resampling.LANCZOS)
    source = np.asarray(image).astype(np.float32)
    luminance = (source[..., :3] * np.array([.2126, .7152, .0722])).sum(axis=2) / 255.
    shadow = np.array(base, dtype=np.float32) * .42
    highlight = np.array(base, dtype=np.float32) * .76 + np.array(accent, dtype=np.float32) * .24
    rgb = shadow[None, None, :] * (1. - luminance[..., None]) + highlight[None, None, :] * luminance[..., None]
    yy, xx = np.mgrid[0:512, 0:512]
    if feature == "scaled":
        mask = ((xx // 18 + yy // 14) % 4 == 0)[..., None]
        rgb = np.where(mask, rgb * .72 + np.array(accent) * .28, rgb)
    elif feature == "stone":
        cracks = (((xx * 7 + yy * 11) % 97) < 2)[..., None]
        rgb = np.where(cracks, np.array(accent) * .78, rgb)
    elif feature == "fungal":
        spores = (((xx * 13 + yy * 17) % 149) < 3)[..., None]
        rgb = np.where(spores, np.array(accent), rgb)
    elif feature == "crystal":
        facets = (((xx + 2 * yy) % 71) < 3)[..., None]
        rgb = np.where(facets, np.array(accent), rgb)
    out = np.dstack((np.clip(rgb, 0, 255).astype(np.uint8), source[..., 3].astype(np.uint8)))
    encoded = io.BytesIO()
    Image.fromarray(out, "RGBA").save(encoded, format="PNG", optimize=True)
    return encoded.getvalue()


def deform_player(positions: np.ndarray, bounds: tuple[np.ndarray, np.ndarray],
                  shape: tuple[float, float, float, float], gender: str) -> np.ndarray:
    low, high = bounds
    height, shoulders, hips, head = shape
    result = positions.astype(np.float32).copy()
    t = np.clip((result[:, 1] - low[1]) / max(1e-5, high[1] - low[1]), 0., 1.)
    width = np.full(len(result), 1.0)
    width = np.where(t < .48, hips, width)
    width = np.where((t >= .48) & (t < .78), shoulders, width)
    width = np.where(t >= .78, head, width)
    width *= .965 if gender == "female" else 1.025
    result[:, 0] *= width
    result[:, 2] *= .98 + (width - 1.) * .35
    result[:, 1] = low[1] + (result[:, 1] - low[1]) * height
    return result


def player_accessory(feature: str, joint_by_name: dict[str, int], color: tuple[int, int, int],
                     accent: tuple[int, int, int]):
    mesh = ShapeMesh()
    head = joint_by_name["Head"]
    spine = joint_by_name["spine_03"]
    pelvis = joint_by_name["pelvis"]
    if feature == "ears":
        # Whitehorn horns begin inside the temple silhouette.  The previous
        # shoulder-height cones began outside the head and read as floating
        # triangles once the bind pose was animated.
        mesh.cone((-.095, 1.735, .005), (-.225, 1.905, .025), .070, head, 1)
        mesh.cone((.095, 1.735, .005), (.225, 1.905, .025), .070, head, 1)
    elif feature == "crystal":
        # Keep the Glasswarden facets close to the upper back so their bases
        # intersect the torso instead of hovering beyond the shoulders.
        for x in (-.12, .12):
            mesh.cone((x, 1.535, -.035), (x * 1.28, 1.715, -.12), .060, spine, 1)
        mesh.cone((0., 1.59, -.045), (0., 1.835, -.145), .070, spine, 1)
    elif feature == "mane":
        for i in range(7):
            angle = (i - 3) * .27
            mesh.cone((0., 1.62, .06), (math.sin(angle) * .22, 1.85, .06 + math.cos(angle) * .12),
                      .055, head, 1)
    elif feature == "brow":
        # Greyhaven's former box crossed the entire skull.  Their maritime
        # identity now comes from the authored material and wearable variants.
        pass
    elif feature == "scaled":
        for y in (1.58, 1.69, 1.80):
            mesh.cone((0., y, -.06), (0., y + .10, -.20), .06, head, 1)
        # The source humanoid faces positive Z; extend the tail behind it.
        mesh.curved_tail((0., .92, -.10), (0., .22, -.64), pelvis, 0)
    elif feature == "stone":
        # A compact crown intersects the scalp; the old shoulder shards were
        # detached from the body and looked identical to missing-mesh markers.
        for x in (-.09, .09):
            mesh.cone((x, 1.735, .005), (x * 1.18, 1.925, .045), .060, head, 1)
    elif feature == "fungal":
        # One stemmed cap reads as anatomy/headwear.  Detached shoulder caps
        # were removed because their gaps were conspicuous during animation.
        mesh.cylinder((0., 1.705, .01), (0., 1.815, .01), .055, head, 0, 14)
        mesh.sphere((0., 1.835, .01), (.39, .115, .32), head, 1, 8, 20)
    return mesh.arrays()


def build_player(source_dir: Path, output: Path, race: str, gender: str) -> dict:
    config = RACES[race]
    source = source_dir / f"Superhero_{gender.title()}_FullBody.gltf"
    document = json.loads(source.read_text(encoding="utf-8"))
    binary = (source.parent / document["buffers"][0]["uri"]).read_bytes()
    glb = GLB()
    glb.doc["nodes"] = copy.deepcopy(document["nodes"])
    glb.doc["scenes"] = copy.deepcopy(document["scenes"])
    glb.doc["scene"] = document.get("scene", 0)
    for node in glb.doc["nodes"]:
        node.pop("mesh", None); node.pop("skin", None)
    skin = document["skins"][0]
    inverse = read_accessor(document, binary, skin["inverseBindMatrices"]).astype("float32")
    inverse_accessor = glb.accessor(inverse, "MAT4")
    glb.doc["skins"] = [{"name": "Armature", "joints": list(skin["joints"]),
                         "inverseBindMatrices": inverse_accessor, "skeleton": skin["joints"][0]}]
    joint_by_name = {document["nodes"][node].get("name", ""): index
                     for index, node in enumerate(skin["joints"])}
    body_primitive = document["meshes"][2]["primitives"][0]
    body_positions = read_accessor(document, binary, body_primitive["attributes"]["POSITION"])
    bounds = (body_positions.min(axis=0), body_positions.max(axis=0))
    texture_uri = document["images"][document["textures"][
        document["materials"][2]["pbrMetallicRoughness"]["baseColorTexture"]["index"]]["source"]]["uri"]
    texture = recolored_texture(source.parent / texture_uri, config["color"], config["accent"], config["feature"])
    materials = [
        glb.material(config["label"] + " Hair", tuple(max(20, c // 3) for c in config["color"]), roughness=.86),
        glb.material(config["label"] + " Eyes", config["accent"], roughness=.24, emissive=tuple(c // 5 for c in config["accent"])),
        glb.material(config["label"] + " Body", config["color"], roughness=.74, texture_png=texture),
        glb.material(config["label"] + " Silhouette", config["color"], roughness=.72),
        glb.material(config["label"] + " Accent", config["accent"], metallic=.15, roughness=.42,
                     emissive=tuple(c // 8 for c in config["accent"])),
    ]
    vertices = triangles = 0
    for mesh_index, node_index in enumerate((65, 66, 67)):
        source_primitive = document["meshes"][mesh_index]["primitives"][0]
        attrs = source_primitive["attributes"]
        positions = deform_player(read_accessor(document, binary, attrs["POSITION"]), bounds,
                                  config["shape"], gender)
        normals = read_accessor(document, binary, attrs["NORMAL"]).astype("float32")
        uvs = read_accessor(document, binary, attrs["TEXCOORD_0"]).astype("float32")
        joints = read_accessor(document, binary, attrs["JOINTS_0"]).astype("uint16")
        weights = read_accessor(document, binary, attrs["WEIGHTS_0"]).astype("float32")
        indices = read_accessor(document, binary, source_primitive["indices"]).astype("uint32")
        primitive = glb.primitive(positions, normals, uvs, indices, materials[mesh_index],
                                  joints=joints, weights=weights)
        glb.doc["meshes"].append({"name": document["meshes"][mesh_index].get("name", f"Mesh{mesh_index}"),
                                  "primitives": [primitive]})
        glb.doc["nodes"][node_index]["mesh"] = len(glb.doc["meshes"]) - 1
        glb.doc["nodes"][node_index]["skin"] = 0
        vertices += len(positions)
        triangles += len(indices) // 3
    accessory = player_accessory(config["feature"], joint_by_name, config["color"], config["accent"])
    if len(accessory[0]):
        primitives = []
        # ShapeMesh emits one consolidated primitive and material selectors as its seventh array.
        for material_index, arrays in enumerate(accessory[6]):
            if len(arrays[0]) == 0:
                continue
            primitives.append(glb.primitive(*arrays[:4], materials[3 + material_index],
                                            joints=arrays[4], weights=arrays[5]))
            vertices += len(arrays[0])
            triangles += len(arrays[3]) // 3
        glb.mesh_node(config["label"] + " Silhouette", primitives, skin=0, parent=68)
    glb.write(output)
    return {"vertices": vertices, "triangles": triangles,
            "joints": len(skin["joints"]), "feature": config["feature"]}


class ShapeMesh:
    """Small, consistently wound primitive authoring helper."""
    def __init__(self):
        self.groups = [([], [], [], [], [], []), ([], [], [], [], [], [])]

    def _append(self, positions, normals, uvs, indices, joint: int, material: int):
        p, n, t, f, j, w = self.groups[material]
        base = len(p); p.extend(positions); n.extend(normals); t.extend(uvs)
        f.extend(base + int(i) for i in indices)
        j.extend(([joint, 0, 0, 0] for _ in positions)); w.extend(([1., 0., 0., 0.] for _ in positions))

    def sphere(self, center, size, joint=0, material=0, rings=10, sides=20):
        cx, cy, cz = center; sx, sy, sz = (v * .5 for v in size)
        positions=[]; normals=[]; uvs=[]; faces=[]
        for ring in range(rings + 1):
            theta = math.pi * ring / rings
            for side in range(sides + 1):
                phi = 2 * math.pi * side / sides
                nx, ny, nz = math.sin(theta)*math.cos(phi), math.cos(theta), math.sin(theta)*math.sin(phi)
                position=(cx+sx*nx, cy+sy*ny, cz+sz*nz)
                normal=np.array((nx/max(sx,1e-4),ny/max(sy,1e-4),nz/max(sz,1e-4)))
                normal/=np.linalg.norm(normal)
                positions.append(position); normals.append(tuple(normal)); uvs.append((side/sides, ring/rings))
        for ring in range(rings):
            for side in range(sides):
                a=ring*(sides+1)+side; b=a+sides+1
                faces.extend((a,b,a+1,a+1,b,b+1))
        self._append(positions,normals,uvs,faces,joint,material)

    def box(self, center, size, joint=0, material=0):
        cx,cy,cz=center; sx,sy,sz=(v*.5 for v in size)
        corners=[(cx+x*sx,cy+y*sy,cz+z*sz) for x,y,z in
                 ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1))]
        quads=((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7))
        norms=((0,0,-1),(0,0,1),(0,-1,0),(1,0,0),(0,1,0),(-1,0,0))
        p=[];n=[];u=[];f=[]
        for quad,norm in zip(quads,norms):
            base=len(p);p.extend(corners[i] for i in quad);n.extend([norm]*4);u.extend(((0,0),(1,0),(1,1),(0,1)))
            f.extend((base,base+1,base+2,base,base+2,base+3))
        self._append(p,n,u,f,joint,material)

    def cylinder(self, start, end, radius, joint=0, material=0, sides=16):
        a=np.array(start,dtype=float); b=np.array(end,dtype=float); axis=b-a; length=np.linalg.norm(axis)
        if length < 1e-6: return
        axis/=length; ref=np.array((1.,0.,0.)) if abs(axis[0])<.85 else np.array((0.,0.,1.))
        right=np.cross(axis,ref);right/=np.linalg.norm(right);forward=np.cross(right,axis)
        p=[];n=[];u=[];f=[]
        for row,center in enumerate((a,b)):
            for side in range(sides):
                angle=2*math.pi*side/sides; normal=right*math.cos(angle)+forward*math.sin(angle)
                p.append(tuple(center+normal*radius));n.append(tuple(normal));u.append((side/sides,row))
        for side in range(sides):
            nxt=(side+1)%sides;a0=side;a1=nxt;b0=sides+side;b1=sides+nxt
            f.extend((a0,b0,a1,a1,b0,b1))
        self._append(p,n,u,f,joint,material)

    def cone(self, start, end, radius, joint=0, material=0, sides=14):
        a=np.array(start,dtype=float); b=np.array(end,dtype=float); axis=b-a; length=np.linalg.norm(axis)
        if length < 1e-6:return
        axis/=length; ref=np.array((1.,0.,0.)) if abs(axis[0])<.85 else np.array((0.,0.,1.))
        right=np.cross(axis,ref);right/=np.linalg.norm(right);forward=np.cross(right,axis)
        p=[tuple(b)];n=[tuple(axis)];u=[(.5,0)];f=[]
        for side in range(sides):
            angle=2*math.pi*side/sides; radial=right*math.cos(angle)+forward*math.sin(angle)
            normal=radial*length+axis*radius;normal/=np.linalg.norm(normal)
            p.append(tuple(a+radial*radius));n.append(tuple(normal));u.append((side/sides,1))
        for side in range(sides):f.extend((0,1+side,1+(side+1)%sides))
        self._append(p,n,u,f,joint,material)

    def curved_tail(self, start, end, joint=0, material=0):
        a=np.array(start,dtype=float); b=np.array(end,dtype=float); previous=a
        for step in range(1,7):
            t=step/6; current=a*(1-t)+b*t+np.array((0., .12*math.sin(t*math.pi), .12*math.sin(t*math.pi)))
            self.cylinder(previous,current,.09*(1-t*.72),joint,material,12);previous=current

    def arrays(self):
        consolidated=[]
        for p,n,u,f,j,w in self.groups:
            consolidated.append((np.asarray(p,dtype="float32").reshape(-1,3),
                                 np.asarray(n,dtype="float32").reshape(-1,3),
                                 np.asarray(u,dtype="float32").reshape(-1,2),
                                 np.asarray(f,dtype="uint32").reshape(-1),
                                 np.asarray(j,dtype="uint16").reshape(-1,4),
                                 np.asarray(w,dtype="float32").reshape(-1,4)))
        # Compatibility prefix retained for the player builder; the grouped arrays are item 6.
        nonempty=next((g for g in consolidated if len(g[0])),(np.empty((0,3)),)*6)
        return (*nonempty, consolidated)


CREATURE_BONES = (
    ("root", -1, (0.,0.,0.)), ("body",0,(0.,.78,0.)), ("neck",1,(0.,.22,-.36)),
    ("head",2,(0.,.18,-.24)), ("jaw",3,(0.,-.08,-.13)),
    ("tail_1",1,(0.,.02,.48)), ("tail_2",5,(0.,0.,.43)),
    ("front_leg_l",1,(-.25,-.18,-.32)), ("front_shin_l",7,(0.,-.34,0.)),
    ("front_paw_l",8,(0.,-.30,-.08)), ("front_leg_r",1,(.25,-.18,-.32)),
    ("front_shin_r",10,(0.,-.34,0.)), ("front_paw_r",11,(0.,-.30,-.08)),
    ("rear_leg_l",1,(-.27,-.13,.33)), ("rear_shin_l",13,(0.,-.38,0.)),
    ("rear_paw_l",14,(0.,-.28,-.04)), ("rear_leg_r",1,(.27,-.13,.33)),
    ("rear_shin_r",16,(0.,-.38,0.)), ("rear_paw_r",17,(0.,-.28,-.04)),
    ("wing_l",1,(-.22,.13,0.)), ("wing_r",1,(.22,.13,0.)),
)


def global_bone_positions(bones=CREATURE_BONES):
    result=[]
    for _,parent,translation in bones:
        base=np.zeros(3) if parent<0 else result[parent]
        result.append(base+np.asarray(translation,dtype=float))
    return result


def creature_geometry(archetype: str, scale: float) -> ShapeMesh:
    m=ShapeMesh(); s=scale; bones=global_bone_positions()
    body=(.72*s,.62*s,1.15*s); head=(.48*s,.44*s,.55*s)
    if archetype in {"bear","boar","rhino","porcupine"}: body=(.92*s,.78*s,1.18*s);head=(.58*s,.52*s,.60*s)
    if archetype in {"lizard","crocodile","otter","rat"}: body=(.66*s,.42*s,1.35*s);head=(.42*s,.34*s,.48*s)
    if archetype=="toad": body=(1.0*s,.48*s,.92*s);head=(.70*s,.38*s,.42*s)
    if archetype=="tortoise": body=(1.02*s,.54*s,1.18*s);head=(.34*s,.30*s,.42*s)
    m.sphere((0,.79,0),body,1,0,12,24)
    m.sphere((0,1.00,-.46*s),(.48*s,.38*s,.48*s),2,0,9,18)
    m.sphere((0,1.08,-.76*s),head,3,0,10,20)
    for side,joints,x in ((-1,(7,8,9),-.25),(1,(10,11,12),.25),(-1,(13,14,15),-.27),(1,(16,17,18),.27)):
        z=-.34 if joints[0] in (7,10) else .34
        m.cylinder((x*s,.65,z*s),(x*s,.28,z*s),.09*s,joints[0],0,12)
        m.cylinder((x*s,.28,z*s),(x*s,.06,(z-.08)*s),.075*s,joints[1],0,12)
        m.sphere((x*s,.045,(z-.15)*s),(.20*s,.10*s,.34*s),joints[2],0,6,12)
    m.cylinder((0,.82,.48*s),(0,.75,.90*s),.11*s,5,0,12)
    m.cone((0,.75,.90*s),(0,.70,1.30*s),.10*s,6,0,12)
    if archetype == "two_tail_fox":
        m.cylinder((-.08,.82,.46*s),(-.18,.77,.91*s),.09*s,5,0,12)
        m.cone((-.18,.77,.91*s),(-.30,.72,1.29*s),.085*s,6,1,12)
    if archetype in {"fox","two_tail_fox","wolf","cat","hare","rat"}:
        ear=.34*s if archetype=="hare" else .22*s
        for x in (-.15,.15):m.cone((x*s,1.23,-.76*s),(x*s,1.23+ear,-.72*s),.10*s,3,1,12)
    if archetype in {"ram","elk"}:
        for side in (-1,1):
            m.cylinder((side*.15*s,1.24,-.72*s),(side*.36*s,1.45,-.65*s),.055*s,3,1,10)
            if archetype=="elk":
                for z in (-.05,.08,.20):m.cone((side*.34*s,1.38,-.65*s+z*s),(side*.52*s,1.58,-.62*s+z*s),.045*s,3,1,8)
    if archetype in {"boar","rhino"}:
        count=2 if archetype=="boar" else 1
        for i in range(count):
            x=(-.15 if i==0 else .15)*s;m.cone((x,1.03,-.98*s),(x,1.18,-1.23*s),.055*s,3,1,10)
    if archetype in {"lizard","crocodile","drake"}:
        for z in np.linspace(-.35,.55,5):m.cone((0,1.06,z*s),(0,1.28,z*s),.055*s,1,1,8)
    if archetype=="drake":
        for side,joint in ((-1,19),(1,20)):
            m.cone((side*.20*s,1.0,0),(side*1.02*s,1.28,.14*s),.14*s,joint,1,16)
            m.cone((side*.34*s,1.02,.08*s),(side*.88*s,.92,.62*s),.12*s,joint,1,16)
    if archetype=="tortoise":m.sphere((0,1.02,.02),(1.14*s,.48*s,1.26*s),1,1,10,24)
    if archetype=="porcupine":
        for z in np.linspace(-.35,.45,7):m.cone((0,1.04,z*s),(0,1.48,z*s),.045*s,1,1,8)
    return m


def add_animation(glb: GLB, name: str, channels: dict[int, tuple[str, list[float], list[list[float]]]]) -> None:
    animation={"name":name,"samplers":[],"channels":[]}
    for node,(path,times,values) in channels.items():
        input_acc=glb.accessor(np.asarray(times,dtype="float32"),"SCALAR",bounds=True)
        width="VEC4" if path=="rotation" else "VEC3"
        output_acc=glb.accessor(np.asarray(values,dtype="float32"),width)
        animation["samplers"].append({"input":input_acc,"output":output_acc,"interpolation":"LINEAR"})
        animation["channels"].append({"sampler":len(animation["samplers"])-1,
                                      "target":{"node":node,"path":path}})
    glb.doc.setdefault("animations",[]).append(animation)


def build_creature(path: Path, actor_type: int, slug: str, label: str, archetype: str,
                   base: tuple[int,int,int], accent: tuple[int,int,int], scale: float) -> dict:
    glb=GLB();glb.doc["nodes"]=[];globals_=global_bone_positions();children={i:[] for i in range(len(CREATURE_BONES))}
    for i,(_,parent,_) in enumerate(CREATURE_BONES):
        if parent>=0:children[parent].append(i)
    for i,(name,parent,translation) in enumerate(CREATURE_BONES):
        node={"name":name,"translation":list(translation)}
        if children[i]:node["children"]=children[i]
        glb.doc["nodes"].append(node)
    glb.doc["scenes"][0]["nodes"]=[0]
    inverse=[]
    for position in globals_:
        matrix=np.eye(4,dtype="float32");matrix[:3,3]=-position;inverse.append(matrix.T.reshape(-1))
    inverse_acc=glb.accessor(np.asarray(inverse,dtype="float32"),"MAT4")
    glb.doc["skins"]=[{"name":"Nymara Creature Rig","joints":list(range(len(CREATURE_BONES))),
                       "skeleton":0,"inverseBindMatrices":inverse_acc}]
    mats=[glb.material(label+" Body",base,roughness=.82),
          glb.material(label+" Accent",accent,metallic=.08,roughness=.55,
                       emissive=tuple(c//10 for c in accent))]
    groups=creature_geometry(archetype,scale).arrays()[6];primitives=[];vertices=triangles=0
    for index,arrays in enumerate(groups):
        if not len(arrays[0]):continue
        primitives.append(glb.primitive(*arrays[:4],mats[index],joints=arrays[4],weights=arrays[5]))
        vertices+=len(arrays[0]);triangles+=len(arrays[3])//3
    glb.mesh_node(label,primitives,skin=0,parent=0)
    q=lambda axis,a:quat(axis,a)
    add_animation(glb,"Idle_A",{1:("rotation",[0,1,2],[q("z",-.025),q("z",.025),q("z",-.025)]),
                                 5:("rotation",[0,1,2],[q("y",-.10),q("y",.10),q("y",-.10)])})
    walk={7:("rotation",[0,.5,1],[q("x",.52),q("x",-.52),q("x",.52)]),
          10:("rotation",[0,.5,1],[q("x",-.52),q("x",.52),q("x",-.52)]),
          13:("rotation",[0,.5,1],[q("x",-.52),q("x",.52),q("x",-.52)]),
          16:("rotation",[0,.5,1],[q("x",.52),q("x",-.52),q("x",.52)])}
    add_animation(glb,"Walk",walk)
    run={bone:(path,[0,.35,.7],[q("x",.82 if vals[0][0]>0 else -.82),q("x",-.82 if vals[0][0]>0 else .82),q("x",.82 if vals[0][0]>0 else -.82)])
         for bone,(path,_,vals) in walk.items()}
    add_animation(glb,"Jog",run)
    add_animation(glb,"Fighting_Idle",{2:("rotation",[0,.7,1.4],[q("x",-.08),q("x",.08),q("x",-.08)])})
    add_animation(glb,"Sword_Attack",{2:("rotation",[0,.28,.65],[q("x",-.18),q("x",.55),q("x",-.18)]),
                                      4:("rotation",[0,.28,.65],[q("x",0),q("x",.42),q("x",0)])})
    add_animation(glb,"Hit_Chest",{1:("rotation",[0,.2,.48],[q("z",0),q("z",.25),q("z",0)])})
    add_animation(glb,"Death_A",{0:("rotation",[0,.7,1.3],[q("z",0),q("z",1.0),q("z",1.48)])})
    glb.write(path)
    return {"actor_type":actor_type,"id":slug,"name":label,"archetype":archetype,
            "vertices":vertices,"triangles":triangles,"joints":len(CREATURE_BONES),"animations":7}


def equipment_geometry(kind: str) -> ShapeMesh:
    m=ShapeMesh()
    if kind in {"sword","glaive"}:
        m.box((0,.40,0),(.055,.82,.035),0,0);m.box((0,-.045,0),(.32,.055,.075),0,1)
        m.cone((0,.80,0),(0,1.04,0),.07,0,1,10)
        if kind=="glaive":m.cone((0,.62,0),(.34,.90,0),.08,0,1,12)
    elif kind in {"spear","harpoon"}:
        m.cylinder((0,-.32,0),(0,1.02,0),.035,0,0,12);m.cone((0,1.02,0),(0,1.34,0),.10,0,1,12)
        if kind=="harpoon":m.cone((0,1.12,0),(.18,1.02,0),.045,0,1,10)
    elif kind in {"staff","mace","hammer","pick"}:
        m.cylinder((0,-.38,0),(0,.88,0),.04,0,0,12)
        if kind=="staff":m.sphere((0,1.02,0),(.24,.24,.24),0,1,8,16)
        elif kind=="mace":
            for axis in ((.20,1.02,0),(-.20,1.02,0),(0,1.02,.20),(0,1.02,-.20)):m.cone((0,1.02,0),axis,.08,0,1,10)
        elif kind=="hammer":m.box((0,1.00,0),(.48,.22,.22),0,1)
        else:m.cone((-.35,1.00,0),(.35,1.00,0),.11,0,1,14)
    elif kind in {"bow","crossbow"}:
        for start,end in (((0,-.55,0),(-.25,0,0)),((-.25,0,0),(0,.55,0)),((0,-.55,0),(.25,0,0)),((.25,0,0),(0,.55,0))):m.cylinder(start,end,.025,0,0,10)
        m.cylinder((0,-.55,0),(0,.55,0),.008,0,1,8)
        if kind=="crossbow":m.box((0,0,0),(.12,.65,.10),0,0)
    elif kind in {"roundshield","shell","kite"}:
        if kind=="kite":m.sphere((0,0,0),(.62,.92,.10),0,0,10,24)
        else:m.sphere((0,0,0),(.78,.78,.12),0,0,10,24)
        m.sphere((0,0,-.08),(.22,.22,.16),0,1,8,16)
    elif kind=="cape":m.box((0,-.52,.12),(.78,1.08,.045),0,0);m.box((0,-.02,.08),(.86,.09,.08),0,1)
    elif kind in {"hood","helm","crest","circlet","mushroom"}:
        m.sphere((0,0,0),(.46,.44,.43),0,0,9,18)
        if kind in {"helm","crest"}:m.cone((0,.14,.05),(0,.58,.08),.11,0,1,12)
        elif kind=="circlet":
            for a in np.linspace(0,2*math.pi,12,endpoint=False):m.sphere((math.cos(a)*.24,0,math.sin(a)*.22),(.06,.06,.06),0,1,4,8)
        elif kind=="mushroom":m.sphere((0,.24,0),(.72,.18,.62),0,1,8,20)
    elif kind in {"cuirass","coat","robe"}:
        m.sphere((0,0,0),(.72,.78,.40),0,0,10,20);m.box((0,-.30,.18),(.58,.62,.08),0,1)
        if kind=="robe":m.sphere((0,-.55,0),(.82,.62,.50),0,0,8,20)
    elif kind=="shirt":
        # A fitted torso plus upper-arm cylinders gives the Luminous base
        # outfit an unmistakable short-sleeve silhouette.
        m.sphere((0,-.02,0),(.68,.72,.38),0,0,10,20)
        m.box((0,-.30,.18),(.58,.54,.07),0,1)
        m.cylinder((-.38,.20,0),(-.43,-.10,0),.15,0,0,14)
        m.cylinder((.38,.20,0),(.43,-.10,0),.15,0,0,14)
    elif kind=="legs":
        for x in (-.15,.15):m.cylinder((x,.22,0),(x,-.58,0),.13,0,0,14);m.box((x,-.12,.08),(.30,.22,.10),0,1)
    elif kind=="pants":
        m.sphere((0,.22,0),(.58,.34,.38),0,0,8,18)
        for x in (-.15,.15):
            m.cylinder((x,.24,0),(x,-.66,0),.15,0,0,14)
            m.box((x,-.22,.08),(.31,.28,.10),0,1)
    elif kind=="boots":
        for x in (-.15,.15):m.cylinder((x,.18,0),(x,-.35,0),.14,0,0,14);m.box((x,-.36,-.09),(.30,.18,.42),0,1)
    elif kind=="amulet":
        for a in np.linspace(0,2*math.pi,16,endpoint=False):m.sphere((math.cos(a)*.18,math.sin(a)*.18,0),(.045,.045,.045),0,0,4,8)
        m.sphere((0,-.24,0),(.18,.22,.08),0,1,8,16)
    return m


def build_equipment(path: Path, slug: str, label: str, kind: str,
                    base: tuple[int,int,int], accent: tuple[int,int,int]) -> dict:
    glb=GLB();mats=[glb.material(label+" Base",base,metallic=.12,roughness=.58),
                    glb.material(label+" Trim",accent,metallic=.45,roughness=.30,
                                 emissive=tuple(c//12 for c in accent))]
    groups=equipment_geometry(kind).arrays()[6];primitives=[];vertices=triangles=0
    for i,arrays in enumerate(groups):
        if not len(arrays[0]):continue
        primitives.append(glb.primitive(*arrays[:4],mats[i]));vertices+=len(arrays[0]);triangles+=len(arrays[3])//3
    glb.mesh_node(label,primitives);glb.write(path)
    return {"id":slug,"name":label,"kind":kind,"vertices":vertices,"triangles":triangles}


def validate_glb(path: Path) -> dict:
    raw=path.read_bytes()
    if raw[:4]!=b"glTF":raise ValueError(f"invalid GLB magic: {path}")
    version,total=struct.unpack_from("<II",raw,4)
    if version!=2 or total!=len(raw):raise ValueError(f"invalid GLB header: {path}")
    json_length,json_kind=struct.unpack_from("<II",raw,12)
    if json_kind!=0x4E4F534A:raise ValueError(f"missing JSON chunk: {path}")
    doc=json.loads(raw[20:20+json_length])
    for mesh in doc.get("meshes",[]):
        for primitive in mesh.get("primitives",[]):
            if "POSITION" not in primitive.get("attributes",{}):raise ValueError(f"mesh without POSITION: {path}")
    return {"nodes":len(doc.get("nodes",[])),"meshes":len(doc.get("meshes",[])),
            "skins":len(doc.get("skins",[])),"animations":len(doc.get("animations",[]))}


def humanoid_model(scene: str) -> dict:
    return {
        "scene": scene,
        "animationLibrary": "res://../eloria-assets/source/player_models/native/Universal_Animation_Library.glb",
        "animationMap": "res://data/animations/luminous.json",
        "boneAliases": {"head": "Head"},
        "import": {"scale": 1, "rotationDegreesX": 0,
                   "rotationDegreesY": 180, "rotationDegreesZ": 0},
        "attachments": {
            "right_hand": "hand_r", "left_hand": "hand_l", "head": "Head",
            "back": "spine_03", "body": "spine_02", "pelvis": "pelvis",
            "feet": ["foot_l", "foot_r"], "neck": "neck_01",
        },
    }


def culture_loadout(culture: str, role: str = "") -> dict[str, int]:
    base = {
        "luminous": {3: 105, 5: 105, 7: 105},
        "votary": {0: 109, 3: 106, 4: 105, 5: 106, 6: 105},
        "glasswarden": {0: 102, 1: 101, 2: 101, 3: 101, 4: 101, 5: 101, 6: 101, 7: 101},
        "orun": {0: 106, 1: 103, 2: 103, 3: 103, 4: 103, 5: 103, 6: 103, 7: 103},
        "greyhaven": {0: 104, 1: 102, 2: 102, 3: 102, 4: 102, 5: 102, 6: 102, 7: 102},
        "ssarathi": {0: 107, 1: 104, 2: 104, 3: 104, 4: 104, 5: 104, 6: 104, 7: 104},
    }[culture].copy()
    if culture == "luminous" and role == "guard":
        return {0: 112, 1: 105, 2: 105, 3: 105, 5: 109, 7: 105}
    if culture == "luminous" and role == "ferryman":
        return {0: 105, 2: 102, 3: 102, 5: 102, 6: 102, 7: 102}
    if role in {"merchant", "official", "scholar", "lake_priest", "elder", "councilor"}:
        base.pop(1, None)
    if role in {"merchant", "scholar", "researcher", "astronomer"}:
        base[0] = {"luminous": 108, "glasswarden": 102,
                   "greyhaven": 113}.get(culture, base.get(0, 108))
    return base


def build_model_registry() -> dict:
    models = {
        "luminous_female": humanoid_model(
            "res://../eloria-assets/source/player_models/native/Superhero_Female_FullBody.gltf"),
        "luminous_male": humanoid_model(
            "res://../eloria-assets/source/player_models/native/Superhero_Male_FullBody.gltf"),
    }
    actor_types = {"0": "luminous_female", "1": "luminous_male"}
    creation = [
        {"actorType": 0, "model": "luminous_female", "label": "Luminous Female"},
        {"actorType": 1, "model": "luminous_male", "label": "Luminous Male"},
    ]
    for actor_type, model_id in PLAYER_ACTOR_TYPES.items():
        models[model_id] = humanoid_model(
            f"res://assets/actors/native/races/{model_id}.glb")
        actor_types[str(actor_type)] = model_id
        race, gender = model_id.rsplit("_", 1)
        creation.append({"actorType": actor_type, "model": model_id,
                         "label": f"{RACES[race]['label']} {gender.title()}"})
    for actor_type, slug, *_ in CREATURES:
        actor_type += CREATURE_ACTOR_TYPE_OFFSET
        models[slug] = {
            "scene": f"res://assets/actors/native/creatures/{slug}.glb",
            "animationLibrary": f"res://assets/actors/native/creatures/{slug}.glb",
            "animationMap": "res://data/animations/creature.json",
            "import": {"scale": 1, "rotationDegreesX": 0,
                       "rotationDegreesY": 0, "rotationDegreesZ": 0},
            "attachments": {"head": "head", "body": "body", "neck": "neck"},
        }
        actor_types[str(actor_type)] = slug

    # Humanoid enemies share player rigs and gain equipment-defined silhouettes.
    enemy_models = {
        236: "luminous_male", 237: "luminous_male", 238: "stoneborn_male",
        239: "luminous_male", 240: "luminous_male", 241: "luminous_male",
        242: "glasswarden_male", 243: "stoneborn_male", 244: "stoneborn_male",
        245: "votary_male", 246: "luminous_female", 247: "greyhaven_male",
        248: "ssarathi_male", 249: "orun_male", 250: "ssarathi_female",
        251: "ssarathi_male", 252: "orun_male", 253: "orun_male",
        254: "orun_male", 255: "luminous_female", 256: "luminous_male",
        257: "orun_male", 258: "orun_male", 259: "ssarathi_male",
    }
    actor_types.update({str(key): value for key, value in enemy_models.items()})

    npc_looks = {}
    cultures = {
        "luminous": ["official", "guard", "merchant", "ferryman", "scholar", "lake_priest", "civilian"],
        "votary": ["monk", "mountaineer", "miner", "glacier_guardian"],
        "glasswarden": ["engineer", "astronomer", "researcher", "guard"],
        "orun": ["rider", "scout", "elder", "camp_resident", "mounted_warden"],
        "greyhaven": ["sailor", "fisher", "shipwright", "merchant", "militia", "councilor"],
        "ssarathi": ["civilian", "priest", "archivist", "warrior", "sun_ceremonial"],
    }
    actor_type = 300
    for culture, roles in cultures.items():
        for gender in ("female", "male"):
            for role in roles:
                model = f"{culture}_{gender}"
                actor_types[str(actor_type)] = model
                npc_looks[str(actor_type)] = {
                    "model": model,
                    "equipmentVisuals": {str(k): v for k, v in culture_loadout(culture, role).items()},
                }
                actor_type += 1
    return {"schemaVersion": 2, "models": models, "actorTypes": actor_types,
            "creationOptions": creation, "npcLooks": npc_looks}


def build_equipment_registry() -> dict:
    parts = {
        "0": {"name": "weapon", "attachment": "right_hand", "fallback": "weapon"},
        "1": {"name": "shield", "attachment": "left_hand", "fallback": "shield"},
        "2": {"name": "cape", "attachment": "back", "fallback": "body"},
        "3": {"name": "helmet", "attachment": "head", "fallback": "head"},
        "4": {"name": "legs", "attachment": "pelvis", "fallback": "body"},
        "5": {"name": "body", "attachment": "body", "fallback": "body"},
        "6": {"name": "boots", "attachment": "pelvis", "fallback": "feet"},
        "7": {"name": "neck", "attachment": "neck", "fallback": "head"},
    }
    models = {}
    for slug, _, part, visual, *_ in EQUIPMENT:
        translation = [0, -.72, 0] if part == 6 else [0, 0, 0]
        models[f"{part}:{visual}"] = {
            "scene": f"res://assets/actors/native/equipment/{slug}.glb",
            "import": {"translation": translation, "rotationDegrees": [0, 0, 0],
                       "scale": 1},
        }
    aliases = {"0:11": "0:112", "1:5": "1:105", "2:11": "2:105"}
    return {"schemaVersion": 2, "parts": parts, "models": models,
            "aliases": aliases}


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    assets_root=Path(__file__).resolve().parents[1]
    repo_root=assets_root.parent
    parser.add_argument("--source",type=Path,default=assets_root/"source/player_models/native")
    parser.add_argument("--output",type=Path,default=repo_root/"godot-client/assets/actors/native")
    parser.add_argument("--manifest",type=Path,default=repo_root/"godot-client/data/actors/native_asset_catalog.json")
    parser.add_argument("--models",type=Path,default=repo_root/"godot-client/data/actors/models.json")
    parser.add_argument("--equipment-registry",type=Path,
                        default=repo_root/"godot-client/data/actors/equipment.json")
    args=parser.parse_args();manifest={"schemaVersion":1,"source":"nymara-concept-art-named.zip",
                                      "pipeline":"build_native_nymara_glbs.py","races":{},"creatures":{},"equipment":{}}
    for race in RACES:
        for gender in ("female","male"):
            model=f"{race}_{gender}";path=args.output/"races"/f"{model}.glb"
            manifest["races"][model]=build_player(args.source,path,race,gender)|{"path":str(path.relative_to(repo_root))}
            print("race",model,manifest["races"][model])
    for actor_type,slug,label,archetype,base,accent,scale in CREATURES:
        actor_type += CREATURE_ACTOR_TYPE_OFFSET
        path=args.output/"creatures"/f"{slug}.glb"
        manifest["creatures"][slug]=build_creature(path,actor_type,slug,label,archetype,base,accent,scale)|{"path":str(path.relative_to(repo_root))}
        print("creature",slug,manifest["creatures"][slug])
    for slug,label,part,visual,kind,base,accent in EQUIPMENT:
        path=args.output/"equipment"/f"{slug}.glb"
        manifest["equipment"][slug]=build_equipment(path,slug,label,kind,base,accent)|{
            "part":part,"visual":visual,"path":str(path.relative_to(repo_root))}
        print("equipment",slug,manifest["equipment"][slug])
    validation={str(path.relative_to(repo_root)):validate_glb(path) for path in args.output.rglob("*.glb")}
    manifest["validation"]={"files":len(validation),"results":validation}
    write_json(args.manifest, manifest)
    write_json(args.models, build_model_registry())
    write_json(args.equipment_registry, build_equipment_registry())
    print(f"validated {len(validation)} native GLBs")


if __name__=="__main__":main()

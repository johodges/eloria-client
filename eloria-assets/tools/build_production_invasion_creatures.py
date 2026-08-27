#!/usr/bin/env python3
"""Author production Godot GLBs for the Nymara invasion creature roster.

The former invasion registry reused a small library of intentionally simple
quadruped placeholders.  This module gives every server actor type from 400 to
427 its own concept-directed silhouette, embedded PBR texture set, 21-joint
creature rig, and seven runtime animation clips.  Geometry and textures are
generated from deterministic project-owned parameters; no Eternal Lands or
third-party creature mesh is consumed.

The named concept archive is a visual authority used by the optional comparison
renderer.  It is deliberately not required at build time and is not copied into
runtime assets.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
import math
from pathlib import Path
import struct

import numpy as np
from PIL import Image


COMPONENT_TYPES = {
    np.dtype("uint8"): 5121,
    np.dtype("uint16"): 5123,
    np.dtype("uint32"): 5125,
    np.dtype("float32"): 5126,
}


@dataclass(frozen=True)
class CreatureSpec:
    actor_type: int
    slug: str
    label: str
    family: str
    region: str
    concept_sheet: str
    concept_slot: tuple[int, int]
    scale: float
    base: tuple[int, int, int]
    secondary: tuple[int, int, int]
    accent: tuple[int, int, int]
    eye: tuple[int, int, int]
    pattern: str
    traits: tuple[str, ...] = ()


# Slots are zero-based columns/rows on the corresponding concept sheets.  The
# entries retain the exact server roster order so generated catalog diffs stay
# stable and reviewers can compare one actor type at a time.
INVASION_CREATURES: tuple[CreatureSpec, ...] = (
    CreatureSpec(400, "mirrorfin_otter", "Mirrorfin Otter", "otter", "Crownwater",
                 "crownwater_magical_aquatic_creatures_sheet.png", (0, 0), .90,
                 (63, 91, 101), (150, 124, 78), (63, 191, 207), (230, 185, 82),
                 "river", ("fins", "whiskers", "mirror_scales")),
    CreatureSpec(401, "reedhorn_stag", "Reedhorn Stag", "stag", "Amberwood",
                 "amberwood_forest_spirits_creatures_sheet.png", (0, 0), 1.18,
                 (126, 69, 39), (80, 52, 34), (220, 109, 40), (237, 183, 65),
                 "fur", ("branch_antlers", "leaf_mane")),
    CreatureSpec(402, "gate_turtle", "Four Gates Turtle", "turtle", "Four Gates",
                 "cross-region_natural_wildlife_sheet.png", (3, 1), 1.08,
                 (128, 92, 49), (87, 67, 43), (218, 163, 66), (235, 193, 92),
                 "shell", ("bronze_scutes", "gate_ridges")),
    CreatureSpec(403, "lakeglass_drake", "Lakeglass Drake", "drake", "Crownwater",
                 "crownwater_crystal_aquatic_creatures_sheet.png", (1, 0), 1.30,
                 (26, 126, 154), (201, 224, 209), (238, 143, 55), (255, 208, 73),
                 "scales", ("wings", "fins", "glass_spines", "whiskers")),
    CreatureSpec(404, "snowcrest_hare", "Snowcrest Hare", "hare", "Whitehorn Range",
                 "whitehorn_glacier_creatures_sheet.png", (1, 0), .72,
                 (222, 230, 229), (151, 185, 201), (73, 139, 178), (93, 173, 217),
                 "fur", ("long_ears", "ice_crest")),
    CreatureSpec(405, "glacier_ram", "Glacier Ram", "ram", "Whitehorn Range",
                 "whitehorn_glacier_creatures_sheet.png", (0, 0), 1.18,
                 (195, 207, 205), (112, 139, 153), (61, 132, 177), (112, 201, 236),
                 "fur", ("spiral_horns", "ice_crystals", "winter_mane")),
    CreatureSpec(406, "iceback_ursid", "Iceback Ursid", "bear", "Whitehorn Range",
                 "whitehorn_glacier_creatures_sheet.png", (3, 0), 1.48,
                 (206, 221, 221), (122, 159, 178), (56, 140, 192), (111, 207, 241),
                 "fur", ("ice_crystals", "heavy_mane", "claws")),
    CreatureSpec(407, "rimeclaw", "Rimeclaw", "cat", "Whitehorn Range",
                 "whitehorn_glacier_creatures_sheet.png", (2, 1), 1.14,
                 (180, 205, 213), (71, 120, 151), (50, 153, 204), (120, 222, 247),
                 "stripes", ("saber_fangs", "ice_tail", "claws")),
    CreatureSpec(408, "crystal_mite", "Crystal Mite", "mite", "Amethyst Barrens",
                 "amethyst_barrens_crystal_creatures_sheet.png", (1, 0), .88,
                 (43, 45, 69), (75, 49, 111), (111, 67, 239), (94, 207, 255),
                 "crystal", ("crystal_carapace", "six_legs", "mandibles")),
    CreatureSpec(409, "resonant_hound", "Resonant Hound", "hound", "Amethyst Barrens",
                 "amethyst_barrens_crystal_creatures_sheet.png", (0, 2), 1.20,
                 (33, 40, 65), (77, 57, 111), (94, 85, 233), (88, 212, 255),
                 "crystal", ("crystal_mane", "crystal_tail", "claws")),
    CreatureSpec(410, "stormglass_grazer", "Stormglass Grazer", "grazer", "Amethyst Barrens",
                 "amethyst_barrens_crystal_creatures_sheet.png", (3, 1), 1.42,
                 (78, 72, 80), (42, 50, 70), (100, 73, 224), (76, 209, 255),
                 "crystal", ("armored_plates", "crystal_horns", "crystal_spines")),
    CreatureSpec(411, "prism_wyrm", "Prism Wyrm", "wyrm", "Amethyst Barrens",
                 "amethyst_barrens_crystal_creatures_sheet.png", (2, 0), 1.24,
                 (42, 45, 66), (67, 55, 104), (125, 72, 239), (79, 218, 255),
                 "crystal", ("crystal_spines", "long_tail", "wings", "claws")),
    CreatureSpec(412, "dunrunner", "Dunrunner", "fox", "Sunmane Steppe",
                 "cross-region_natural_wildlife_sheet.png", (2, 0), .90,
                 (178, 102, 45), (224, 166, 86), (74, 48, 37), (232, 181, 68),
                 "fur", ("long_ears", "brush_tail")),
    CreatureSpec(413, "steppe_aurochs", "Steppe Aurochs", "aurochs", "Sunmane Steppe",
                 "cross-region_natural_wildlife_sheet.png", (1, 0), 1.38,
                 (105, 79, 55), (176, 139, 85), (65, 47, 35), (222, 170, 69),
                 "fur", ("swept_horns", "heavy_mane", "hooves")),
    CreatureSpec(414, "sunmane_cat", "Sunmane Cat", "cat", "Sunmane Steppe",
                 "cross-region_natural_wildlife_sheet.png", (2, 1), 1.12,
                 (190, 116, 47), (239, 183, 73), (79, 56, 43), (232, 186, 62),
                 "stripes", ("sun_mane", "claws", "tuft_tail")),
    CreatureSpec(415, "dustscale_drake", "Dustscale Drake", "drake", "Sunmane Steppe",
                 "crownwater_crystal_aquatic_creatures_sheet.png", (3, 0), 1.30,
                 (132, 76, 38), (198, 143, 64), (47, 137, 141), (239, 183, 60),
                 "scales", ("wings", "dust_spines", "horns")),
    CreatureSpec(416, "amberhart", "Amberhart", "stag", "Amberwood",
                 "amberwood_forest_spirits_creatures_sheet_b.png", (0, 0), 1.20,
                 (128, 69, 38), (89, 55, 34), (229, 119, 44), (238, 181, 60),
                 "fur", ("branch_antlers", "ember_leaves", "heavy_mane")),
    CreatureSpec(417, "rootback_boar", "Rootback Boar", "boar", "Amberwood",
                 "amberwood_forest_spirits_creatures_sheet_b.png", (1, 0), 1.30,
                 (75, 68, 48), (98, 84, 51), (192, 92, 37), (225, 157, 54),
                 "moss", ("root_armor", "tusks", "leaf_mane")),
    CreatureSpec(418, "moor_wisp_hound", "Moor Wisp Hound", "hound", "Grey Moors",
                 "grey_moors_spirits_creatures_sheet.png", (2, 2), 1.23,
                 (40, 57, 64), (63, 83, 89), (45, 190, 205), (126, 238, 246),
                 "spirit", ("spectral_mane", "antlers", "wisp_tail", "claws")),
    CreatureSpec(419, "barrow_quillbeast", "Barrow Quillbeast", "quillbeast", "Grey Moors",
                 "amberwood_grey_moors_creatures_transparent_sheet_a.png", (1, 1), 1.10,
                 (70, 65, 54), (115, 91, 58), (54, 165, 173), (117, 219, 222),
                 "moss", ("quills", "stone_scutes", "tusks")),
    CreatureSpec(420, "canopy_glider", "Canopy Glider", "glider", "Amberwood",
                 "amberwood_forest_spirits_creatures_sheet.png", (3, 0), .90,
                 (103, 66, 43), (195, 118, 50), (52, 120, 92), (239, 186, 63),
                 "fur", ("leaf_wings", "two_tails", "long_ears")),
    CreatureSpec(421, "cenote_toader", "Cenote Toader", "toad", "Manymouth Delta",
                 "manymouth_delta_swamp_creatures_sheet.png", (2, 0), 1.18,
                 (74, 103, 54), (190, 150, 73), (195, 79, 46), (240, 184, 56),
                 "moss", ("mushrooms", "warts", "toe_claws")),
    CreatureSpec(422, "scalevine_stalker", "Scalevine Stalker", "stalker", "Verdant Stair",
                 "verdant_ssarathi_jungle_creatures_sheet.png", (1, 1), 1.26,
                 (44, 104, 66), (188, 125, 46), (75, 191, 129), (230, 176, 57),
                 "scales", ("vine_mane", "leaf_spines", "claws", "long_tail")),
    CreatureSpec(423, "sunscale_basilisk", "Sunscale Basilisk", "basilisk", "Verdant Stair",
                 "verdant_ssarathi_jungle_creatures_sheet.png", (0, 0), 1.34,
                 (42, 127, 72), (187, 125, 39), (230, 95, 42), (244, 190, 57),
                 "scales", ("leaf_crown", "sun_spines", "fins", "long_tail")),
    CreatureSpec(424, "mangrove_crab", "Mangrove Crab", "crab", "Manymouth Delta",
                 "manymouth_delta_swamp_creatures_sheet.png", (0, 0), 1.12,
                 (83, 91, 65), (151, 65, 41), (41, 140, 123), (230, 180, 65),
                 "shell", ("moss", "giant_claws", "stalk_eyes")),
    CreatureSpec(425, "mudskipper_beast", "Mudskipper Beast", "mudskipper", "Manymouth Delta",
                 "manymouth_delta_swamp_creatures_sheet.png", (1, 2), 1.12,
                 (54, 96, 92), (147, 107, 62), (42, 187, 192), (235, 176, 61),
                 "river", ("fins", "stalk_eyes", "whiskers", "toe_claws")),
    CreatureSpec(426, "delta_crocodile", "Delta Crocodile", "crocodile", "Manymouth Delta",
                 "manymouth_delta_swamp_creatures_sheet.png", (0, 1), 1.58,
                 (50, 88, 54), (143, 121, 63), (45, 151, 139), (231, 181, 58),
                 "scales", ("moss", "dorsal_scutes", "teeth", "long_tail")),
    CreatureSpec(427, "floodmaw", "Floodmaw", "floodmaw", "Manymouth Delta",
                 "manymouth_delta_swamp_creatures_sheet.png", (3, 2), 1.76,
                 (33, 77, 76), (92, 107, 70), (43, 183, 194), (246, 157, 53),
                 "river", ("three_heads", "mangrove_roots", "fins", "teeth", "wisp_glow")),
)


def registry_entry(slug: str) -> dict:
    return {
        "scene": f"res://assets/actors/native/creatures/{slug}.glb",
        "animationLibrary": f"res://assets/actors/native/creatures/{slug}.glb",
        "animationMap": "res://data/animations/creature.json",
        "import": {"scale": 1, "rotationDegreesX": 0,
                   "rotationDegreesY": 0, "rotationDegreesZ": 0},
        "attachments": {"head": "head", "body": "body", "neck": "neck"},
    }


def _align4(value: int) -> int:
    return (value + 3) & ~3


class ProductionGLB:
    """Minimal glTF 2.0 writer with embedded metallic/roughness texture sets."""

    def __init__(self) -> None:
        self.binary = bytearray()
        self.doc = {
            "asset": {"version": "2.0", "generator": "Eloria production invasion creature builder"},
            "scene": 0,
            "scenes": [{"nodes": []}],
            "nodes": [],
            "meshes": [],
            "materials": [],
            "bufferViews": [],
            "accessors": [],
            "buffers": [{"byteLength": 0}],
        }

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
                 bounds: bool = False) -> int:
        values = np.ascontiguousarray(values)
        width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}[gltf_type]
        spec = {
            "bufferView": self.bytes_view(values.tobytes(), target=target),
            "componentType": COMPONENT_TYPES[values.dtype],
            "count": int(values.shape[0]),
            "type": gltf_type,
        }
        if bounds:
            matrix = values.reshape(len(values), width)
            spec["min"] = [float(value) for value in matrix.min(axis=0)]
            spec["max"] = [float(value) for value in matrix.max(axis=0)]
        self.doc["accessors"].append(spec)
        return len(self.doc["accessors"]) - 1

    def _texture(self, name: str, png: bytes, *, linear: bool = False) -> int:
        view = self.bytes_view(png)
        self.doc.setdefault("images", []).append(
            {"name": name, "bufferView": view, "mimeType": "image/png"})
        image = len(self.doc["images"]) - 1
        self.doc.setdefault("samplers", []).append({
            "magFilter": 9729,
            "minFilter": 9987,
            "wrapS": 10497,
            "wrapT": 10497,
        })
        sampler = len(self.doc["samplers"]) - 1
        texture = {"source": image, "sampler": sampler}
        if not linear:
            texture["name"] = name
        self.doc.setdefault("textures", []).append(texture)
        return len(self.doc["textures"]) - 1

    def material(self, name: str, color: tuple[int, int, int], *, metallic: float = 0.0,
                 roughness: float = .72, emissive: tuple[int, int, int] | None = None,
                 base_png: bytes | None = None, normal_png: bytes | None = None,
                 orm_png: bytes | None = None, emissive_png: bytes | None = None,
                 double_sided: bool = False, alpha: float = 1.0) -> int:
        factor = [component / 255.0 for component in color] + [alpha]
        pbr = {"baseColorFactor": factor, "metallicFactor": metallic,
               "roughnessFactor": roughness}
        if base_png is not None:
            pbr["baseColorTexture"] = {"index": self._texture(name + " Base Color", base_png)}
        if orm_png is not None:
            orm_texture = self._texture(name + " ORM", orm_png, linear=True)
            pbr["metallicRoughnessTexture"] = {"index": orm_texture}
        material = {"name": name, "pbrMetallicRoughness": pbr,
                    "doubleSided": double_sided}
        if normal_png is not None:
            material["normalTexture"] = {
                "index": self._texture(name + " Normal", normal_png, linear=True),
                "scale": .82,
            }
        if orm_png is not None:
            material["occlusionTexture"] = {"index": orm_texture, "strength": .70}
        if emissive is not None:
            material["emissiveFactor"] = [component / 255.0 for component in emissive]
        if emissive_png is not None:
            material["emissiveTexture"] = {
                "index": self._texture(name + " Emissive", emissive_png)
            }
        if alpha < 1.0:
            material["alphaMode"] = "BLEND"
        self.doc["materials"].append(material)
        return len(self.doc["materials"]) - 1

    def primitive(self, positions: np.ndarray, normals: np.ndarray, uvs: np.ndarray,
                  indices: np.ndarray, material: int, joints: np.ndarray,
                  weights: np.ndarray) -> dict:
        attributes = {
            "POSITION": self.accessor(positions.astype("float32"), "VEC3",
                                      target=34962, bounds=True),
            "NORMAL": self.accessor(normals.astype("float32"), "VEC3", target=34962),
            "TEXCOORD_0": self.accessor(uvs.astype("float32"), "VEC2", target=34962),
            "JOINTS_0": self.accessor(joints.astype("uint16"), "VEC4", target=34962),
            "WEIGHTS_0": self.accessor(weights.astype("float32"), "VEC4", target=34962),
        }
        return {
            "attributes": attributes,
            "indices": self.accessor(indices.astype("uint32").reshape(-1), "SCALAR",
                                     target=34963),
            "material": material,
            "mode": 4,
        }

    def write(self, path: Path) -> None:
        self.doc["buffers"][0]["byteLength"] = len(self.binary)
        raw_json = json.dumps(self.doc, separators=(",", ":")).encode("utf-8")
        raw_json += b" " * (_align4(len(raw_json)) - len(raw_json))
        raw_binary = bytes(self.binary)
        raw_binary += b"\0" * (_align4(len(raw_binary)) - len(raw_binary))
        total = 12 + 8 + len(raw_json) + 8 + len(raw_binary)
        payload = (struct.pack("<4sII", b"glTF", 2, total)
                   + struct.pack("<II", len(raw_json), 0x4E4F534A) + raw_json
                   + struct.pack("<II", len(raw_binary), 0x004E4942) + raw_binary)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)


def _png(array: np.ndarray) -> bytes:
    stream = io.BytesIO()
    Image.fromarray(np.asarray(array, dtype=np.uint8), "RGB").save(
        stream, format="PNG", optimize=True, compress_level=8)
    return stream.getvalue()


def _fractal_noise(rng: np.random.Generator, size: int) -> np.ndarray:
    """Return soft, non-periodic multiscale noise suitable for organic hides."""
    result = np.zeros((size, size), dtype=np.float32)
    weight = 1.0
    weight_sum = 0.0
    for grid in (4, 8, 16, 32, 64, 128):
        source = np.asarray(rng.random((grid, grid)) * 255.0, dtype=np.uint8)
        enlarged = Image.fromarray(source, "L").resize(
            (size, size), Image.Resampling.BICUBIC)
        result += np.asarray(enlarged, dtype=np.float32) / 255.0 * weight
        weight_sum += weight
        weight *= .52
    result /= weight_sum
    return (result - result.min()) / max(float(np.ptp(result)), 1e-6)


def _texture_set(spec: CreatureSpec, size: int = 512) -> tuple[bytes, bytes, bytes, bytes]:
    """Create deterministic base-color, tangent normal, ORM, and emissive maps."""
    seed = int.from_bytes(hashlib.sha256(spec.slug.encode("utf-8")).digest()[:8], "little")
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    u, v = x / size, y / size
    phase = rng.uniform(0.0, math.tau, 8)
    macro = _fractal_noise(rng, size)
    micro = _fractal_noise(rng, size)
    height = np.clip(macro * .72 + micro * .28, 0.0, 1.0)
    pattern = np.zeros_like(height)
    pattern_strength = .12
    pattern_color = np.asarray(spec.accent, dtype=np.float32)
    if spec.slug in {"rimeclaw", "scalevine_stalker"}:
        cells_x = u * 10.0 + macro * .42
        cells_y = v * 8.0
        row = np.floor(cells_y)
        local_x = ((cells_x + (row % 2.0) * .5) % 1.0) - .5
        local_y = (cells_y % 1.0) - .5
        radius = np.sqrt(local_x * local_x + local_y * local_y)
        rosette = np.exp(-np.square(radius - .23) * 185.0)
        center = np.exp(-np.square(radius) * 85.0) * .30
        pattern = np.clip(rosette + center + macro * .08, 0.0, 1.0)
        height = np.clip(micro * .70 + rosette * .18 + macro * .12, 0.0, 1.0)
        pattern_strength = .46 if spec.slug == "rimeclaw" else .34
        if spec.slug == "scalevine_stalker":
            pattern_color = np.asarray(spec.secondary, dtype=np.float32)
    elif spec.pattern == "fur":
        # Keep the coat direction readable without painting latitude bands on
        # every separately-authored anatomical volume.  Two softly warped,
        # very fine strand fields contribute to the normal map while broad
        # colour variation comes only from non-periodic noise.
        strands_a = .5 + .5 * np.sin((v * 138.0 + u * 2.2 + micro * 2.0) * math.tau)
        strands_b = .5 + .5 * np.sin((v * 173.0 - u * 3.1 + macro * 1.6) * math.tau)
        strands = strands_a * .55 + strands_b * .45
        pattern = np.clip(macro * .82 + micro * .18, 0.0, 1.0)
        height = np.clip(micro * .72 + strands * .14 + macro * .14, 0.0, 1.0)
        pattern_strength = .065
    elif spec.pattern == "stripes":
        stripes = np.sin((u * 7.0 + v * 1.25 + macro * .65) * math.tau)
        pattern = np.clip((stripes - .12) * 1.9, 0.0, 1.0)
        height = np.clip(micro * .72 + pattern * .18 + macro * .10, 0.0, 1.0)
        pattern_strength = .34
    elif spec.pattern == "scales":
        row = np.floor(v * 30.0)
        staggered_u = u * 25.0 + (row % 2.0) * .5
        cell_u = np.abs((staggered_u % 1.0) - .5) * 2.0
        cell_v = np.abs(((v * 30.0) % 1.0) - .46) * 2.0
        scale_cells = np.clip(1.0 - np.maximum(cell_u * .82, cell_v), 0.0, 1.0)
        pattern = np.clip(scale_cells * .72 + macro * .28, 0.0, 1.0)
        height = np.clip(micro * .28 + scale_cells * .62 + macro * .10, 0.0, 1.0)
        pattern_strength = .18
    elif spec.pattern == "crystal":
        facets = np.maximum.reduce([
            np.sin((u * 7.0 + v * 3.0) * math.tau + phase[0]),
            np.sin((u * -4.0 + v * 9.0) * math.tau + phase[1]),
            np.sin((u * 11.0 + v * -5.0) * math.tau + phase[2]),
        ])
        veins = np.exp(-np.square(facets) * 34.0)
        pattern = np.clip(veins * .62 + macro * .38, 0.0, 1.0)
        height = np.clip(np.abs(facets) * .38 + macro * .42 + micro * .20, 0.0, 1.0)
        pattern_strength = .22
    elif spec.pattern == "shell":
        rings = .5 + .5 * np.sin((np.sqrt(np.square(u - .5) * 1.5
                                               + np.square(v - .5)) * 18.0
                                  + macro * .45) * math.tau)
        scutes = (.5 + .5 * np.cos(u * math.tau * 10.0)) * (
            .5 + .5 * np.cos(v * math.tau * 8.0))
        pattern = np.clip(rings * .28 + scutes * .42 + macro * .30, 0.0, 1.0)
        height = np.clip(micro * .25 + pattern * .45 + macro * .30, 0.0, 1.0)
        pattern_strength = .16
    elif spec.pattern == "moss":
        blobs = np.clip((macro - .43) * 2.6, 0.0, 1.0)
        pattern = np.clip(blobs * .76 + micro * .24, 0.0, 1.0)
        height = np.clip(macro * .64 + micro * .36, 0.0, 1.0)
        pattern_strength = .18
    elif spec.pattern == "spirit":
        veins = .5 + .5 * np.sin((u * 3.3 + np.sin(v * math.tau * 2.2) * .35
                                  + macro * .42) * math.tau)
        pattern = np.clip((veins - .58) * 2.35 + macro * .18, 0.0, 1.0)
        height = np.clip(micro * .52 + pattern * .30 + macro * .18, 0.0, 1.0)
        pattern_strength = .24
    else:  # river skin: slick mottling and lateral luminous lines
        ripple = .5 + .5 * np.sin((u * 3.4 + v * 10.0 + macro * .48) * math.tau)
        pattern = np.clip(ripple * .32 + macro * .68, 0.0, 1.0)
        height = np.clip(micro * .58 + macro * .30 + ripple * .12, 0.0, 1.0)
        pattern_strength = .14

    base = np.asarray(spec.base, dtype=np.float32)
    secondary = np.asarray(spec.secondary, dtype=np.float32)
    accent = np.asarray(spec.accent, dtype=np.float32)
    color = (base[None, None, :] * (1.0 - macro[..., None] * .16)
             + secondary[None, None, :] * macro[..., None] * .16)
    blend = pattern[..., None] * pattern_strength
    color = color * (1.0 - blend) + pattern_color * blend
    fine = rng.normal(0.0, 1.65, (size, size, 1))
    color = np.clip(color + fine, 0.0, 255.0)

    dy, dx = np.gradient(height)
    normal = np.dstack((-dx * 1.18, -dy * 1.18, np.ones_like(height)))
    normal /= np.linalg.norm(normal, axis=2, keepdims=True)
    normal = np.clip(normal * 127.5 + 127.5, 0.0, 255.0)

    roughness = np.clip(.91 - height * .16
                        - pattern * (.24 if spec.pattern == "crystal" else .035),
                        .30, .96)
    metallic = np.clip(pattern * (.40 if spec.pattern == "crystal" else .035), 0.0, .52)
    occlusion = np.clip(.82 + height * .18, 0.0, 1.0)
    orm = np.dstack((occlusion * 255.0, roughness * 255.0, metallic * 255.0))

    magical = any(trait in spec.traits for trait in (
        "glass_spines", "ice_crystals", "crystal_carapace", "crystal_mane",
        "crystal_tail", "crystal_horns", "crystal_spines", "spectral_mane",
        "wisp_tail", "wisp_glow", "mirror_scales"))
    emissive_mask = np.clip((pattern - (.66 if magical else .96)) * 2.2, 0.0, 1.0)
    emissive = emissive_mask[..., None] * accent[None, None, :]
    return _png(color), _png(normal), _png(orm), _png(emissive)


def _surface_texture_set(
        spec: CreatureSpec, label: str,
        first: tuple[int, int, int], second: tuple[int, int, int],
        *, size: int = 256, crystalline: bool = False,
        emissive: bool = False) -> tuple[bytes, bytes, bytes, bytes]:
    """Create a dedicated PBR set for armor, underbody, and accent surfaces.

    Using the body atlas on every surface made the base coat detailed while
    antlers, scutes, membranes, and magical growths remained conspicuously
    flat.  These compact material-specific maps give every visually important
    surface independent grain, micro-normal, roughness, and optional glow.
    """
    digest = hashlib.sha256(f"{spec.slug}:{label}".encode("utf-8")).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], "little"))
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    u, v = x / size, y / size
    macro = _fractal_noise(rng, size)
    micro = _fractal_noise(rng, size)
    a = np.asarray(first, dtype=np.float32)
    b = np.asarray(second, dtype=np.float32)
    if crystalline:
        phase = rng.uniform(0.0, math.tau, 3)
        facets = np.maximum.reduce([
            np.sin((u * 5.0 + v * 2.0) * math.tau + phase[0]),
            np.sin((-u * 3.0 + v * 7.0) * math.tau + phase[1]),
            np.sin((u * 9.0 - v * 4.0) * math.tau + phase[2]),
        ])
        seams = np.exp(-np.square(facets) * 42.0)
        blend = np.clip(macro * .48 + seams * .44 + micro * .08, 0.0, 1.0)
        height = np.clip(np.abs(facets) * .42 + macro * .40 + micro * .18,
                         0.0, 1.0)
        metallic = np.clip(.12 + blend * .32, 0.0, .48)
        roughness = np.clip(.54 - blend * .24 + micro * .08, .22, .68)
    else:
        grain = .5 + .5 * np.sin((v * 96.0 + u * 4.0 + micro * 2.0) * math.tau)
        flecks = np.clip((macro - .55) * 2.3, 0.0, 1.0)
        blend = np.clip(macro * .62 + flecks * .23 + grain * .15, 0.0, 1.0)
        height = np.clip(micro * .64 + grain * .16 + macro * .20, 0.0, 1.0)
        metallic = np.clip(flecks * .06, 0.0, .08)
        roughness = np.clip(.82 - macro * .14 + micro * .05, .56, .92)
    color = a[None, None, :] * (1.0 - blend[..., None] * .28)
    color += b[None, None, :] * blend[..., None] * .28
    color += rng.normal(0.0, 1.25, (size, size, 1))
    color = np.clip(color, 0.0, 255.0)
    dy, dx = np.gradient(height)
    normal = np.dstack((-dx * 1.22, -dy * 1.22, np.ones_like(height)))
    normal /= np.linalg.norm(normal, axis=2, keepdims=True)
    normal = np.clip(normal * 127.5 + 127.5, 0.0, 255.0)
    occlusion = np.clip(.84 + height * .16, 0.0, 1.0)
    orm = np.dstack((occlusion * 255.0, roughness * 255.0,
                     metallic * 255.0))
    glow_mask = (np.clip((blend - .62) * 1.55, 0.0, 1.0)
                 if emissive else np.zeros_like(blend))
    glow = glow_mask[..., None] * b[None, None, :] * .52
    return _png(color), _png(normal), _png(orm), _png(glow)


BODY, UNDER, DETAIL, MAGIC, EYE, MEMBRANE, DARK, BONE = range(8)


def _rotation_matrix(rotation: tuple[float, float, float]) -> np.ndarray:
    x, y, z = rotation
    cx, sx = math.cos(x), math.sin(x)
    cy, sy = math.cos(y), math.sin(y)
    cz, sz = math.cos(z), math.sin(z)
    rx = np.asarray(((1, 0, 0), (0, cx, -sx), (0, sx, cx)), dtype=float)
    ry = np.asarray(((cy, 0, sy), (0, 1, 0), (-sy, 0, cy)), dtype=float)
    rz = np.asarray(((cz, -sz, 0), (sz, cz, 0), (0, 0, 1)), dtype=float)
    return rz @ ry @ rx


class CreatureMesh:
    """Smooth parametric mesh authoring with one skinned group per material."""

    def __init__(self, material_count: int = 8) -> None:
        self.groups = [([], [], [], [], [], []) for _ in range(material_count)]

    def _append(self, positions, normals, uvs, indices, joint: int, material: int,
                secondary_joint: int | None = None, secondary_weight: float = 0.0) -> None:
        p, n, t, f, j, w = self.groups[material]
        base = len(p)
        p.extend(tuple(float(value) for value in position) for position in positions)
        n.extend(tuple(float(value) for value in normal) for normal in normals)
        t.extend(tuple(float(value) for value in uv) for uv in uvs)
        f.extend(base + int(index) for index in indices)
        other = joint if secondary_joint is None else secondary_joint
        blend = max(0.0, min(1.0, secondary_weight))
        j.extend(([joint, other, 0, 0] for _ in positions))
        w.extend(([1.0 - blend, blend, 0.0, 0.0] for _ in positions))

    def ellipsoid(self, center: tuple[float, float, float],
                  radii: tuple[float, float, float], joint: int = 1,
                  material: int = BODY, *, rings: int = 18, sides: int = 32,
                  rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
                  secondary_joint: int | None = None, secondary_weight: float = 0.0) -> None:
        center_v = np.asarray(center, dtype=float)
        radius_v = np.asarray(radii, dtype=float)
        matrix = _rotation_matrix(rotation)
        positions, normals, uvs, faces = [], [], [], []
        for ring in range(rings + 1):
            theta = math.pi * ring / rings
            for side in range(sides + 1):
                phi = math.tau * side / sides
                unit = np.asarray((math.sin(theta) * math.cos(phi), math.cos(theta),
                                   math.sin(theta) * math.sin(phi)), dtype=float)
                local = radius_v * unit
                normal = unit / np.maximum(radius_v, 1e-5)
                normal = matrix @ normal
                normal /= max(float(np.linalg.norm(normal)), 1e-7)
                positions.append(center_v + matrix @ local)
                normals.append(normal)
                uvs.append((side / sides, ring / rings))
        for ring in range(rings):
            for side in range(sides):
                a = ring * (sides + 1) + side
                b = a + sides + 1
                faces.extend((a, b, a + 1, a + 1, b, b + 1))
        self._append(positions, normals, uvs, faces, joint, material,
                     secondary_joint, secondary_weight)

    def faceted_ellipsoid(
            self, center: tuple[float, float, float],
            radii: tuple[float, float, float], joint: int = 1,
            material: int = MAGIC, *, rings: int = 7, sides: int = 12,
            rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> None:
        """Flat-shaded closed crystal/scute volume with independent faces."""
        center_v = np.asarray(center, dtype=float)
        radius_v = np.asarray(radii, dtype=float)
        matrix = _rotation_matrix(rotation)
        positions: list[np.ndarray] = []
        normals: list[np.ndarray] = []
        uvs: list[tuple[float, float]] = []
        faces: list[int] = []

        def point(ring: int, side: int) -> np.ndarray:
            theta = math.pi * ring / rings
            phi = math.tau * side / sides
            unit = np.asarray((math.sin(theta) * math.cos(phi), math.cos(theta),
                               math.sin(theta) * math.sin(phi)), dtype=float)
            return center_v + matrix @ (radius_v * unit)

        def triangle(a: tuple[int, int], b: tuple[int, int],
                     c: tuple[int, int]) -> None:
            pa, pb, pc = point(*a), point(*b), point(*c)
            normal = np.cross(pb - pa, pc - pa)
            magnitude = float(np.linalg.norm(normal))
            if magnitude < 1e-9:
                return
            normal /= magnitude
            base = len(positions)
            positions.extend((pa, pb, pc))
            normals.extend((normal, normal, normal))
            uvs.extend(((a[1] / sides, a[0] / rings),
                        (b[1] / sides, b[0] / rings),
                        (c[1] / sides, c[0] / rings)))
            faces.extend((base, base + 1, base + 2))

        for ring in range(rings):
            for side in range(sides):
                triangle((ring, side), (ring + 1, side),
                         (ring, side + 1))
                triangle((ring, side + 1), (ring + 1, side),
                         (ring + 1, side + 1))
        self._append(positions, normals, uvs, faces, joint, material)

    def tube(self, points: list[tuple[float, float, float]], radii: float | list[float],
             joint: int = 1, material: int = BODY, *, sides: int = 18,
             secondary_joint: int | None = None, secondary_weight: float = 0.0) -> None:
        if len(points) < 2:
            return
        centers = [np.asarray(point, dtype=float) for point in points]
        radius_values = ([float(radii)] * len(centers) if isinstance(radii, (int, float))
                         else [float(value) for value in radii])
        positions, normals, uvs, faces = [], [], [], []
        previous_right: np.ndarray | None = None
        for row, center in enumerate(centers):
            if row == 0:
                tangent = centers[1] - center
            elif row == len(centers) - 1:
                tangent = center - centers[row - 1]
            else:
                tangent = centers[row + 1] - centers[row - 1]
            tangent /= max(float(np.linalg.norm(tangent)), 1e-7)
            reference = np.asarray((0.0, 1.0, 0.0))
            if abs(float(np.dot(tangent, reference))) > .88:
                reference = np.asarray((1.0, 0.0, 0.0))
            right = np.cross(tangent, reference)
            right /= max(float(np.linalg.norm(right)), 1e-7)
            if previous_right is not None and float(np.dot(previous_right, right)) < 0.0:
                right = -right
            forward = np.cross(right, tangent)
            previous_right = right
            for side in range(sides + 1):
                angle = math.tau * side / sides
                normal = right * math.cos(angle) + forward * math.sin(angle)
                positions.append(center + normal * radius_values[row])
                normals.append(normal)
                uvs.append((side / sides, row / max(len(centers) - 1, 1)))
        for row in range(len(centers) - 1):
            for side in range(sides):
                a = row * (sides + 1) + side
                b = a + sides + 1
                faces.extend((a, b, a + 1, a + 1, b, b + 1))
        self._append(positions, normals, uvs, faces, joint, material,
                     secondary_joint, secondary_weight)

    def spike(self, start: tuple[float, float, float], end: tuple[float, float, float],
              radius: float, joint: int = 1, material: int = DETAIL, *, sides: int = 16) -> None:
        start_v, end_v = np.asarray(start, dtype=float), np.asarray(end, dtype=float)
        midpoint = start_v * .58 + end_v * .42
        self.tube([tuple(start_v), tuple(midpoint), tuple(end_v)],
                  [radius, radius * .68, .002], joint, material, sides=sides)

    def membrane(self, points: list[tuple[float, float, float]], joint: int,
                 material: int = MEMBRANE) -> None:
        if len(points) < 3:
            return
        vertices = [np.asarray(point, dtype=float) for point in points]
        normal = np.cross(vertices[1] - vertices[0], vertices[2] - vertices[0])
        normal /= max(float(np.linalg.norm(normal)), 1e-7)
        low = np.min(np.asarray(vertices), axis=0)
        high = np.max(np.asarray(vertices), axis=0)
        span = np.maximum(high - low, 1e-5)
        uvs = [((point[0] - low[0]) / span[0], (point[2] - low[2]) / span[2])
               for point in vertices]
        faces = []
        for index in range(1, len(vertices) - 1):
            faces.extend((0, index, index + 1, 0, index + 1, index))
        self._append(vertices, [normal] * len(vertices), uvs, faces, joint, material)

    def arrays(self) -> list[tuple[np.ndarray, ...]]:
        result = []
        for positions, normals, uvs, faces, joints, weights in self.groups:
            result.append((
                np.asarray(positions, dtype="float32").reshape(-1, 3),
                np.asarray(normals, dtype="float32").reshape(-1, 3),
                np.asarray(uvs, dtype="float32").reshape(-1, 2),
                np.asarray(faces, dtype="uint32").reshape(-1),
                np.asarray(joints, dtype="uint16").reshape(-1, 4),
                np.asarray(weights, dtype="float32").reshape(-1, 4),
            ))
        return result


CREATURE_BONES = (
    ("root", -1, (0.0, 0.0, 0.0)),
    ("body", 0, (0.0, .78, 0.0)),
    ("neck", 1, (0.0, .22, -.36)),
    ("head", 2, (0.0, .18, -.24)),
    ("jaw", 3, (0.0, -.08, -.13)),
    ("tail_1", 1, (0.0, .02, .48)),
    ("tail_2", 5, (0.0, 0.0, .43)),
    ("front_leg_l", 1, (-.25, -.18, -.32)),
    ("front_shin_l", 7, (0.0, -.34, 0.0)),
    ("front_paw_l", 8, (0.0, -.30, -.08)),
    ("front_leg_r", 1, (.25, -.18, -.32)),
    ("front_shin_r", 10, (0.0, -.34, 0.0)),
    ("front_paw_r", 11, (0.0, -.30, -.08)),
    ("rear_leg_l", 1, (-.27, -.13, .33)),
    ("rear_shin_l", 13, (0.0, -.38, 0.0)),
    ("rear_paw_l", 14, (0.0, -.28, -.04)),
    ("rear_leg_r", 1, (.27, -.13, .33)),
    ("rear_shin_r", 16, (0.0, -.38, 0.0)),
    ("rear_paw_r", 17, (0.0, -.28, -.04)),
    ("wing_l", 1, (-.22, .13, 0.0)),
    ("wing_r", 1, (.22, .13, 0.0)),
)


def _global_bone_positions() -> list[np.ndarray]:
    result: list[np.ndarray] = []
    for _, parent, translation in CREATURE_BONES:
        base = np.zeros(3) if parent < 0 else result[parent]
        result.append(base + np.asarray(translation, dtype=float))
    return result


def _eye_pair(mesh: CreatureMesh, s: float, center: tuple[float, float, float],
              width: float, size: float = .045) -> None:
    """Author inset dark eyes with a restrained coloured iris.

    The first implementation used a bright full eyeball with a black dot,
    which read as a toy from the gameplay camera.  A dark almond-shaped socket
    plus a small iris preserves expression while matching the concept sheets.
    """
    for side in (-1.0, 1.0):
        mesh.ellipsoid((side * width * s, center[1] * s, center[2] * s),
                       (size * s, size * .67 * s, size * .34 * s), 3, DARK,
                       rings=9, sides=18,
                       rotation=(0.0, side * .10, side * -.08))
        mesh.ellipsoid((side * width * 1.008 * s, (center[1] + size * .02) * s,
                        (center[2] - size * .31) * s),
                       (size * .34 * s, size * .37 * s, size * .12 * s), 3, EYE,
                       rings=7, sides=14)


def _stalk_eye(mesh: CreatureMesh, s: float,
               base: tuple[float, float, float],
               tip: tuple[float, float, float], *, size: float = .072,
               joint: int = 3) -> None:
    mesh.tube([tuple(value * s for value in base),
               tuple(value * s for value in tip)],
              [.040 * s, .030 * s], joint, BODY, sides=13)
    mesh.ellipsoid(tuple(value * s for value in tip),
                   (size * s, size * .86 * s, size * .66 * s),
                   joint, DARK, rings=10, sides=18)
    mesh.ellipsoid((tip[0] * s, (tip[1] + size * .02) * s,
                    (tip[2] - size * .62) * s),
                   (size * .31 * s, size * .35 * s, size * .13 * s),
                   joint, EYE, rings=7, sides=14)


def _paw(mesh: CreatureMesh, x: float, y: float, z: float, s: float, joint: int,
         *, broad: float = 1.0, claws: bool = False, material: int = BODY) -> None:
    # A raised heel, broad pad, and separate digits avoid the old flat-disc
    # silhouette while retaining one deformable paw joint.
    mesh.ellipsoid((x * s, (y + .030 * broad) * s, (z + .025) * s),
                   (.100 * broad * s, .088 * broad * s, .175 * broad * s),
                   joint, material, rings=13, sides=24,
                   rotation=(-.12, 0.0, 0.0))
    # Digits share the hide colour; only the small terminal talon is bone.
    # Making the entire toe ivory was the largest source of the old mitten-like
    # silhouette.
    toe_material = material
    for offset in (-.048, .048):
        mesh.ellipsoid(((x + offset * broad) * s, (y + .012) * s,
                        (z - .105 * broad) * s),
                       (.052 * broad * s, .042 * broad * s,
                        .092 * broad * s), joint, toe_material,
                       rings=9, sides=17, rotation=(-.18, 0.0, 0.0))
    if claws:
        for offset in (-.052, 0.0, .052):
            mesh.spike(((x + offset * broad) * s, (y + .005) * s, (z - .16) * s),
                       ((x + offset * broad) * s, (y - .008) * s, (z - .215) * s),
                       .009 * s, joint, BONE, sides=9)


def _hoof(mesh: CreatureMesh, x: float, y: float, z: float, s: float,
          joint: int, *, broad: float = 1.0) -> None:
    """Cloven, dark keratin hoof for ungulates."""
    mesh.ellipsoid((x * s, (y + .045) * s, (z + .015) * s),
                   (.088 * broad * s, .105 * s, .125 * broad * s),
                   joint, DETAIL, rings=12, sides=22,
                   rotation=(-.08, 0.0, 0.0))
    for side in (-1.0, 1.0):
        mesh.ellipsoid(((x + side * .043 * broad) * s, (y + .012) * s,
                        (z - .080 * broad) * s),
                       (.043 * broad * s, .050 * s, .075 * broad * s),
                       joint, DETAIL, rings=9, sides=17,
                       rotation=(-.18, side * .08, 0.0))


def _fur_lock(mesh: CreatureMesh, start: tuple[float, float, float],
              control: tuple[float, float, float], end: tuple[float, float, float],
              radius: float, joint: int, material: int) -> None:
    """Curved tapered lock used for manes and silhouette fur."""
    mesh.tube([start, control, end], [radius, radius * .72, .003],
              joint, material, sides=13)


def _quadruped(mesh: CreatureMesh, spec: CreatureSpec, *, body=(.46, .34, .64),
               head=(.28, .24, .30), snout=(.19, .15, .24), leg=.58,
               stance=.30, low=False, broad_paws=1.0) -> dict[str, tuple[float, float, float]]:
    s = spec.scale
    body_y = .62 if low else .80 + max(0.0, leg - .58) * .52
    family_rise = {
        "cat": .23, "hound": .25, "fox": .24, "stalker": .23,
        "bear": .27, "boar": .22, "quillbeast": .22,
    }.get(spec.family, .31)
    head_y = body_y + (.19 if low else family_rise)
    mesh.ellipsoid((0.0, body_y * s, .04 * s), tuple(value * s for value in body),
                   1, BODY, rings=26, sides=44)
    # Overlapping shoulder and haunch masses establish real animal anatomy at
    # the silhouette instead of reading as one capsule on four posts.
    mesh.ellipsoid((0.0, (body_y + .015) * s, -.35 * s),
                   (body[0] * .96 * s, body[1] * 1.06 * s, .36 * s),
                   1, BODY, rings=20, sides=36, secondary_joint=2,
                   secondary_weight=.10)
    mesh.ellipsoid((0.0, (body_y + .01) * s, .39 * s),
                   (body[0] * 1.02 * s, body[1] * .98 * s, .38 * s),
                   1, BODY, rings=20, sides=36, secondary_joint=5,
                   secondary_weight=.08)
    mesh.ellipsoid((0.0, (body_y - .10) * s, .02 * s),
                   (body[0] * .72 * s, body[1] * .54 * s, body[2] * .78 * s),
                   1, UNDER, rings=14, sides=28)
    mesh.ellipsoid((0.0, (body_y + .06) * s, -.39 * s),
                   (body[0] * .88 * s, body[1] * .94 * s, .37 * s),
                   1, BODY, rings=18, sides=32, secondary_joint=2, secondary_weight=.18)
    mesh.tube([(0.0, (body_y + .09) * s, -.38 * s),
               (0.0, (head_y - .08) * s, -.58 * s),
               (0.0, head_y * s, -.73 * s)],
              [body[0] * .54 * s, head[0] * .78 * s, head[0] * .70 * s],
              2, BODY, sides=24, secondary_joint=3, secondary_weight=.16)
    mesh.ellipsoid((0.0, head_y * s, -.78 * s),
                   tuple(value * s for value in head), 3, BODY, rings=22, sides=40)
    mesh.ellipsoid((0.0, (head_y - .105) * s, -.90 * s),
                   (head[0] * .58 * s, head[1] * .37 * s, head[2] * .46 * s),
                   3, UNDER, rings=15, sides=28)
    mesh.ellipsoid((0.0, (head_y - .055) * s, -1.00 * s),
                   tuple(value * s for value in snout), 4, UNDER, rings=18, sides=34)
    mesh.ellipsoid((0.0, (head_y - .16) * s, -1.02 * s),
                   (snout[0] * .78 * s, snout[1] * .46 * s,
                    snout[2] * .72 * s), 4, UNDER, rings=12, sides=24)
    # A small wet nose plus paired nostrils replaces the former oversized black
    # sphere, preserving a natural muzzle in close review shots.
    mesh.ellipsoid((0.0, (head_y - .035) * s, -1.205 * s),
                   (.058 * s, .037 * s, .034 * s), 4, DARK, rings=10, sides=20)
    for side in (-1.0, 1.0):
        mesh.ellipsoid((side * .029 * s, (head_y - .021) * s, -1.237 * s),
                       (.011 * s, .008 * s, .006 * s), 4, DETAIL,
                       rings=6, sides=11)
    _eye_pair(mesh, s, (0.0, head_y + .06, -.99), head[0] * .77, size=.037)

    front_z, rear_z = -.37, .39
    upper_y = body_y - .13
    ankle_y = .16
    for x, upper_joint, lower_joint, paw_joint, z in (
        (-stance, 7, 8, 9, front_z), (stance, 10, 11, 12, front_z),
        (-stance * 1.06, 13, 14, 15, rear_z), (stance * 1.06, 16, 17, 18, rear_z),
    ):
        rear = z > 0
        knee_z = z + (.13 if rear else -.07)
        outward = math.copysign(.045, x)
        # Muscular shoulder/haunch and curved two-bone limbs create changing
        # widths at every joint, visible even at the isometric gameplay camera.
        mesh.ellipsoid((x * s, (upper_y + .02) * s, (z + (.05 if rear else 0.0)) * s),
                       ((.15 if rear else .13) * s, (.23 if rear else .20) * s,
                        (.20 if rear else .16) * s), upper_joint, BODY,
                       rings=14, sides=26,
                       rotation=(.16 if rear else -.12, 0.0, outward))
        mesh.tube([(x * s, upper_y * s, z * s),
                   ((x + outward) * s, (upper_y - leg * .28) * s,
                    (z + (.08 if rear else -.03)) * s),
                   ((x + outward * .55) * s, (upper_y - leg * .50) * s,
                    knee_z * s)],
                  [.120 * s, .105 * s, .078 * s], upper_joint, BODY, sides=22,
                  secondary_joint=lower_joint, secondary_weight=.18)
        mesh.tube([((x + outward * .55) * s, (upper_y - leg * .50) * s,
                    knee_z * s),
                   ((x - outward * .18) * s, (upper_y - leg * .74) * s,
                    (z - (.02 if rear else .08)) * s),
                   (x * s, ankle_y * s, (z - .10) * s)],
                  [.078 * s, .058 * s, .045 * s], lower_joint, BODY, sides=20,
                  secondary_joint=paw_joint, secondary_weight=.15)
        hoofed = any(trait in spec.traits for trait in ("hooves", "swept_horns",
                                                        "spiral_horns", "branch_antlers"))
        if hoofed:
            _hoof(mesh, x, .050, z - .21, s, paw_joint, broad=broad_paws)
        else:
            _paw(mesh, x, .065, z - .18, s, paw_joint, broad=broad_paws,
                 claws="claws" in spec.traits, material=BODY)
    return {"head": (0.0, head_y, -.78), "body": (0.0, body_y, .04),
            "tail": (0.0, body_y + .02, .61), "snout": (0.0, head_y - .05, -1.18)}


def _tail(mesh: CreatureMesh, s: float, start: tuple[float, float, float], *,
          length: float = 1.05, curl: float = .14, thick: float = .13,
          material: int = BODY, split: float = 0.0) -> None:
    for branch in ((-split, 1.0), (split, -1.0)) if split else ((0.0, 1.0),):
        lateral, direction = branch
        points = []
        radii = []
        for index in range(9):
            t = index / 8.0
            points.append(((lateral * t + direction * curl * math.sin(t * math.pi)) * s,
                           (start[1] + .12 * math.sin(t * math.pi)) * s,
                           (start[2] + length * t) * s))
            radii.append(thick * (1.0 - t * .82) * s)
        mesh.tube(points, radii, 5, material, sides=20,
                  secondary_joint=6, secondary_weight=.28)


def _ear(mesh: CreatureMesh, s: float, x: float, base_y: float, base_z: float,
         height: float, width: float, joint: int = 3, material: int = DETAIL) -> None:
    mesh.spike((x * s, base_y * s, base_z * s),
               ((x * 1.08) * s, (base_y + height) * s, (base_z + .03) * s),
               width * s, joint, material, sides=18)


def _leaf_ear(mesh: CreatureMesh, s: float, side: float, base_y: float,
              base_z: float, *, length: float = .27, width: float = .15,
              droop: float = 0.0) -> None:
    root = (side * .17 * s, base_y * s, base_z * s)
    tip = (side * (.17 + length) * s, (base_y + .12 - droop) * s,
           (base_z + .03) * s)
    upper = (side * (.17 + length * .42) * s, (base_y + width) * s,
             (base_z - .015) * s)
    lower = (side * (.17 + length * .42) * s, (base_y - width * .42) * s,
             (base_z + .025) * s)
    mesh.tube([root, tip], [.035 * s, .006 * s], 3, BODY, sides=12)
    mesh.membrane([root, upper, tip, lower], 3, DETAIL)


def _round_ear(mesh: CreatureMesh, s: float, side: float, base_y: float,
               base_z: float, *, radius: float = .13) -> None:
    mesh.ellipsoid((side * .19 * s, base_y * s, base_z * s),
                   (radius * s, radius * 1.08 * s, radius * .42 * s),
                   3, BODY, rings=12, sides=22, rotation=(0.0, side * .24, side * .18))
    mesh.ellipsoid((side * .195 * s, base_y * s, (base_z - .035) * s),
                   (radius * .58 * s, radius * .68 * s, radius * .16 * s),
                   3, DETAIL, rings=9, sides=17)


def _horn_curve(mesh: CreatureMesh, s: float, side: float, origin: tuple[float, float, float],
                *, sweep=.45, rise=.42, forward=.12, material=DETAIL) -> None:
    points, radii = [], []
    for index in range(8):
        t = index / 7.0
        points.append(((origin[0] + side * (sweep * t + .08 * math.sin(t * math.pi))) * s,
                       (origin[1] + rise * math.sin(t * math.pi * .72)) * s,
                       (origin[2] - forward * t + .10 * math.sin(t * math.pi)) * s))
        radii.append((.075 * (1.0 - t * .86) + .004) * s)
    mesh.tube(points, radii, 3, material, sides=18)


def _spiral_horn(mesh: CreatureMesh, s: float, side: float,
                 center: tuple[float, float, float]) -> None:
    points, radii = [], []
    for index in range(24):
        t = index / 23.0
        angle = .30 + t * math.tau * 1.42
        radius = .31 * (1.0 - t * .63)
        points.append(((center[0] + side * radius * math.cos(angle)) * s,
                       (center[1] + radius * math.sin(angle)) * s,
                       (center[2] - .18 * t + .035 * math.sin(angle * 2.0)) * s))
        radii.append((.070 * (1.0 - t * .78) + .008) * s)
    mesh.tube(points, radii, 3, MAGIC, sides=20)


def _antlers(mesh: CreatureMesh, s: float, origin_y: float, *, spectral=False) -> None:
    material = MAGIC
    for side in (-1.0, 1.0):
        trunk = []
        for index in range(12):
            t = index / 11.0
            trunk.append((side * (.13 + .29 * t + .12 * math.sin(t * math.pi)) * s,
                          (origin_y + .53 * t + .10 * math.sin(t * math.pi)) * s,
                          (-.73 + .34 * t + .04 * math.sin(t * math.pi * 2.0)) * s))
        mesh.tube(trunk, [(.058 * (1.0 - index / 12.0) + .010) * s
                          for index in range(12)], 3, material, sides=16)
        for tine, index in enumerate((2, 4, 6, 8, 10)):
            start = trunk[index]
            direction = -1.0 if tine % 2 == 0 else 1.0
            mid = (start[0] + side * (.10 + tine * .012) * s,
                   start[1] + (.12 + tine * .015) * s,
                   start[2] + direction * .07 * s)
            end = (start[0] + side * (.20 + tine * .016) * s,
                   start[1] + (.24 + tine * .018) * s,
                   start[2] + direction * .11 * s)
            mesh.tube([start, mid, end],
                      [.032 * s, .020 * s, .003 * s], 3, material, sides=12)


def _spine_row(mesh: CreatureMesh, s: float, z_start: float, z_end: float, count: int,
               y: float, height: float, *, material: int = MAGIC, joint: int = 1) -> None:
    for index, z in enumerate(np.linspace(z_start, z_end, count)):
        taper = .65 + .35 * math.sin(math.pi * index / max(count - 1, 1))
        mesh.spike((0.0, y * s, float(z) * s),
                   (0.0, (y + height * taper) * s, (float(z) + .025) * s),
                   height * .18 * s, joint, material, sides=14)


def _dorsal_plate_field(
        mesh: CreatureMesh, s: float, *, z_start: float, z_end: float,
        crest_y: float, half_width: float, rows: int, columns: int,
        crown_drop: float, end_drop: float, plate_height: float,
        material: int = DETAIL, accent_material: int | None = None,
        joint: int = 1) -> None:
    """Lay a close, contour-following field of individually faceted scutes.

    Large isolated ovals read as toy blocks from the gameplay camera.  This
    staggered field follows the body dome, overlaps its neighbours slightly,
    and varies the face angle so shell, scale, and crystal armor reads as one
    richly articulated surface.
    """
    row_spacing = (z_end - z_start) / max(rows - 1, 1)
    column_spacing = (half_width * 2.0) / max(columns - 1, 1)
    for row, z_value in enumerate(np.linspace(z_start, z_end, rows)):
        z = float(z_value)
        z_normalized = abs((row / max(rows - 1, 1)) * 2.0 - 1.0)
        edge_width = half_width * (1.0 - .09 * z_normalized)
        offset = column_spacing * .22 if row % 2 else 0.0
        for column, x_value in enumerate(np.linspace(-edge_width, edge_width, columns)):
            x = float(x_value) + offset
            if abs(x) > half_width * 1.04:
                continue
            x_normalized = abs(x) / max(half_width, 1e-5)
            y = (crest_y - crown_drop * x_normalized ** 1.65
                 - end_drop * z_normalized ** 1.45
                 + .008 * ((row + column) % 2))
            chosen = material
            if accent_material is not None and (row * 3 + column) % 7 == 0:
                chosen = accent_material
            mesh.faceted_ellipsoid(
                (x * s, y * s, z * s),
                (column_spacing * .57 * s, plate_height * s,
                 abs(row_spacing) * .58 * s),
                joint, chosen, rings=5, sides=9,
                rotation=(.035 * ((row % 3) - 1),
                          .09 * ((column % 3) - 1),
                          -.24 * x_normalized * (-1.0 if x < 0.0 else 1.0)))


def _root_armor_network(mesh: CreatureMesh, s: float, body_y: float) -> None:
    """Build layered roots, branchlets, and ember leaves over a forest hide."""
    for side in (-1.0, 1.0):
        for lane in range(3):
            points: list[tuple[float, float, float]] = []
            radii: list[float] = []
            for index, z_value in enumerate(np.linspace(-.57, .67, 9)):
                phase = index * .82 + lane * 1.37
                points.append((
                    side * (.26 + lane * .045 + .035 * math.sin(phase)) * s,
                    (body_y + .24 + lane * .035 + .045 * math.cos(phase * .83)) * s,
                    (float(z_value) + .025 * math.sin(phase * 1.3)) * s,
                ))
                radii.append((.030 - lane * .004) * (1.0 - index * .035) * s)
            mesh.tube(points, radii, 1, DETAIL, sides=12)
            for branch_index in (2, 5, 7):
                start = points[branch_index]
                direction = -1.0 if (branch_index + lane) % 2 else 1.0
                end = (
                    start[0] + side * (.13 + lane * .018) * s,
                    start[1] + (.12 + branch_index * .006) * s,
                    start[2] + direction * .13 * s,
                )
                mesh.tube([start, end], [.018 * s, .003 * s], 1, DETAIL,
                          sides=10)
                mesh.faceted_ellipsoid(
                    end, (.045 * s, .095 * s, .018 * s), 1, MAGIC,
                    rings=5, sides=8,
                    rotation=(direction * .24, 0.0, side * -.42))


def _wing(mesh: CreatureMesh, s: float, side: float, *, leafy=False) -> None:
    joint = 19 if side < 0 else 20
    root = (side * .24 * s, 1.05 * s, -.04 * s)
    elbow = (side * .92 * s, 1.38 * s, .12 * s)
    tip = (side * 1.46 * s, 1.17 * s, .37 * s)
    mesh.tube([root, elbow, tip], [.075 * s, .052 * s, .014 * s], joint, DETAIL, sides=16)
    # Four articulated digits and individually triangulated web panels avoid
    # the single kite-shaped plane of the placeholder wings.
    fingers = [
        (side * 1.29 * s, 1.00 * s, .56 * s),
        (side * 1.08 * s, .88 * s, .72 * s),
        (side * .82 * s, .78 * s, .79 * s),
        (side * .53 * s, .73 * s, .71 * s),
    ]
    roots = [elbow,
             (side * .78 * s, 1.25 * s, .13 * s),
             (side * .66 * s, 1.18 * s, .11 * s),
             (side * .54 * s, 1.12 * s, .08 * s)]
    for index, (finger_root, finger_tip) in enumerate(zip(roots, fingers)):
        mesh.tube([finger_root, finger_tip],
                  [(.050 - index * .006) * s, (.010 - index * .0015) * s],
                  joint, DETAIL, sides=max(11, 15 - index))
    mesh.membrane([root, elbow, tip, fingers[0]], joint, MEMBRANE)
    previous = fingers[0]
    for finger in fingers[1:]:
        mesh.membrane([root, previous, finger], joint, MEMBRANE)
        previous = finger
    if leafy:
        for factor in (.35, .62, .88):
            center = np.asarray(root) * (1.0 - factor) + np.asarray(tip) * factor
            mesh.spike(tuple(center),
                       tuple(center + np.asarray((side * .10, .12, -.04)) * s),
                       .035 * s, joint, MAGIC, sides=10)


def _whiskers(mesh: CreatureMesh, s: float, y: float, z: float, *, count=3) -> None:
    for side in (-1.0, 1.0):
        for index in range(count):
            lift = (index - (count - 1) * .5) * .055
            mesh.tube([(side * .12 * s, (y + lift) * s, z * s),
                       (side * .42 * s, (y + lift + .03) * s, (z - .10) * s)],
                      [.011 * s, .003 * s], 3, DETAIL, sides=8)


def _quadruped_features(mesh: CreatureMesh, spec: CreatureSpec,
                       landmarks: dict[str, tuple[float, float, float]]) -> None:
    s = spec.scale
    head_y = landmarks["head"][1]
    if "long_ears" in spec.traits:
        for side in (-1.0, 1.0):
            _ear(mesh, s, side * .15, head_y + .10, -.74,
                 .50 if spec.family == "hare" else .38, .075)
    elif spec.family in {"otter", "bear"}:
        for side in (-1.0, 1.0):
            _round_ear(mesh, s, side, head_y + .10, -.73,
                       radius=.105 if spec.family == "otter" else .13)
    elif spec.family in {"stag", "ram", "grazer", "aurochs", "boar", "quillbeast"}:
        for side in (-1.0, 1.0):
            _leaf_ear(mesh, s, side, head_y + .05, -.73,
                      length=.30 if spec.family in {"stag", "grazer"} else .23,
                      width=.13, droop=.07 if spec.family in {"boar", "quillbeast"} else 0.0)
    elif spec.family in {"fox", "cat", "hound", "stalker"}:
        for side in (-1.0, 1.0):
            _ear(mesh, s, side * .17, head_y + .10, -.75, .23, .075)
    if "branch_antlers" in spec.traits or "antlers" in spec.traits:
        _antlers(mesh, s, head_y + .11, spectral="spectral_mane" in spec.traits)
    if "spiral_horns" in spec.traits:
        for side in (-1.0, 1.0):
            _spiral_horn(mesh, s, side, (side * .27, head_y + .13, -.77))
    if "swept_horns" in spec.traits or "crystal_horns" in spec.traits:
        material = MAGIC if "crystal_horns" in spec.traits else BONE
        for side in (-1.0, 1.0):
            _horn_curve(mesh, s, side, (side * .14, head_y + .08, -.79),
                        sweep=.55, rise=.20, forward=.28, material=material)
    if "horns" in spec.traits:
        for side in (-1.0, 1.0):
            mesh.spike((side * .14 * s, (head_y + .10) * s, -.82 * s),
                       (side * .31 * s, (head_y + .38) * s, -.96 * s),
                       .07 * s, 3, BONE, sides=16)
    if "tusks" in spec.traits:
        for side in (-1.0, 1.0):
            mesh.spike((side * .17 * s, (head_y - .08) * s, -1.10 * s),
                       (side * .24 * s, (head_y + .12) * s, -1.28 * s),
                       .045 * s, 4, BONE, sides=14)
    if "saber_fangs" in spec.traits:
        for side in (-1.0, 1.0):
            mesh.spike((side * .12 * s, (head_y - .10) * s, -1.13 * s),
                       (side * .12 * s, (head_y - .245) * s, -1.17 * s),
                       .024 * s, 4, BONE, sides=13)
    if "whiskers" in spec.traits:
        _whiskers(mesh, s, head_y - .03, -1.13)
    if "sun_mane" in spec.traits:
        # The Sunmane concept has a swept, smoke-dark dorsal mane—not a radial
        # collar.  Layer the locks from crown to withers and bend them rearward.
        for row, z in enumerate(np.linspace(-.72, .08, 7)):
            y = head_y + .14 - row * .040
            for lane in (-1.0, 1.0):
                mesh.ellipsoid(
                    (lane * (.105 + row * .006) * s, y * s,
                     (float(z) + .14) * s),
                    (.115 * s, .070 * s, .255 * s), 2, DETAIL,
                    rings=12, sides=22,
                    rotation=(-.34, lane * .10, lane * .07))
        for lane in (-1.0, 0.0, 1.0):
            _fur_lock(mesh,
                      (lane * .12 * s, (head_y + .10) * s, -.83 * s),
                      (lane * .15 * s, (head_y + .20) * s, -.72 * s),
                      (lane * .18 * s, (head_y + .14) * s, -.55 * s),
                      .045 * s, 3, DETAIL)
        for index in range(7):
            lane = (index - 3) / 3.0
            _fur_lock(
                mesh,
                (lane * .20 * s, (head_y - .18) * s, -.48 * s),
                (lane * .25 * s, (head_y - .36) * s, -.41 * s),
                (lane * .27 * s, (head_y - .50 + .05 * abs(lane)) * s,
                 -.29 * s),
                .035 * s, 2, DETAIL)
    elif "heavy_mane" in spec.traits or "winter_mane" in spec.traits:
        material = MAGIC if "winter_mane" in spec.traits else DETAIL
        for ring in range(2):
            count = 12 + ring * 3
            for index in range(count):
                angle = math.tau * index / count
                x = math.cos(angle) * (.29 + ring * .035)
                y = head_y - .06 + math.sin(angle) * (.22 + ring * .030)
                z = -.58 + ring * .075
                direction = np.asarray((math.cos(angle) * (.16 + ring * .015),
                                        math.sin(angle) * (.17 + ring * .012),
                                        .10 + .025 * math.sin(index * 1.7))) * s
                start = np.asarray((x, y, z)) * s
                control = start + direction * .58 + np.asarray(
                    (0.0, .025 * math.sin(index * 2.1), .015)) * s
                end = start + direction
                _fur_lock(mesh, tuple(start), tuple(control), tuple(end),
                          (.035 + ring * .003) * s, 2, material)
        # Long chest locks are especially important for the aurochs, ram, and
        # lion concepts, whose manes hang rather than radiate as spikes.
        for index in range(9):
            side = (index - 4) / 4.0
            start = (side * .22 * s, (head_y - .20) * s, -.48 * s)
            control = (side * .27 * s, (head_y - .40 - .03 * abs(side)) * s,
                       -.43 * s)
            end = (side * .30 * s, (head_y - .58 - .04 * abs(side)) * s,
                   -.34 * s)
            _fur_lock(mesh, start, control, end, .034 * s, 2, material)
    if "leaf_mane" in spec.traits or "ember_leaves" in spec.traits or "vine_mane" in spec.traits:
        for index in range(18):
            angle = math.tau * index / 18.0
            inner_x = math.cos(angle) * .27
            inner_y = head_y - .04 + math.sin(angle) * .21
            outer_x = math.cos(angle) * .39
            outer_y = head_y - .04 + math.sin(angle) * .32
            mesh.tube([(inner_x * s, inner_y * s, -.53 * s),
                       (outer_x * s, outer_y * s, -.48 * s)],
                      [.018 * s, .006 * s], 2, MAGIC, sides=9)
            mesh.faceted_ellipsoid(
                (outer_x * s, outer_y * s, -.45 * s),
                (.070 * s, .135 * s, .024 * s), 2, MAGIC,
                rings=5, sides=8,
                rotation=(.18 * math.sin(angle), 0.0, -angle))
    if any(trait in spec.traits for trait in ("ice_crystals", "crystal_mane", "crystal_spines")):
        _spine_row(mesh, s, -.42, .48, 9, landmarks["body"][1] + .31, .27,
                   material=MAGIC)
    if "crystal_mane" in spec.traits:
        _dorsal_plate_field(
            mesh, s, z_start=-.49, z_end=.54,
            crest_y=landmarks["body"][1] + .315, half_width=.32,
            rows=8, columns=5, crown_drop=.10, end_drop=.035,
            plate_height=.037, material=MAGIC, accent_material=DETAIL)
        for index, z_value in enumerate(np.linspace(-.43, .43, 7)):
            side = -1.0 if index % 2 else 1.0
            mesh.spike(
                (side * .08 * s, (landmarks["body"][1] + .31) * s,
                 float(z_value) * s),
                (side * .22 * s,
                 (landmarks["body"][1] + .62 + .07 * math.sin(index)) * s,
                 (float(z_value) + .06) * s),
                .040 * s, 1, MAGIC, sides=13)
    if "leaf_spines" in spec.traits:
        _spine_row(mesh, s, -.48, .57, 11, landmarks["body"][1] + .25, .20,
                   material=MAGIC)
    if "root_armor" in spec.traits:
        _dorsal_plate_field(
            mesh, s, z_start=-.43, z_end=.55,
            crest_y=landmarks["body"][1] + .35, half_width=.39,
            rows=8, columns=5, crown_drop=.13, end_drop=.045,
            plate_height=.035, material=DETAIL, accent_material=MAGIC)
        _root_armor_network(mesh, s, landmarks["body"][1])
    elif "stone_scutes" in spec.traits or "armored_plates" in spec.traits:
        for row, z in enumerate(np.linspace(-.38, .48, 6)):
            for side in (-1.0, 1.0):
                mesh.faceted_ellipsoid(
                    (side * (.27 + row % 2 * .04) * s,
                     (landmarks["body"][1] + .28) * s, float(z) * s),
                    (.20 * s, .065 * s, .22 * s), 1,
                    MAGIC if "armored_plates" in spec.traits else DETAIL,
                    rings=5, sides=9, rotation=(0.0, 0.0, side * .20))
    if spec.slug == "iceback_ursid":
        # The concept's silhouette is a shaggy glacier bear carrying broken
        # ice shelves across its shoulders, not a smooth white quadruped.
        for row, z_value in enumerate(np.linspace(-.47, .48, 7)):
            for side in (-1.0, 1.0):
                mesh.faceted_ellipsoid(
                    (side * (.38 - abs(float(z_value)) * .05) * s,
                     (landmarks["body"][1] + .25 + .025 * (row % 2)) * s,
                     float(z_value) * s),
                    (.14 * s, .040 * s, .17 * s), 1, MAGIC,
                    rings=5, sides=9,
                    rotation=(0.0, side * .24, side * .22))
        for side in (-1.0, 1.0):
            for index, z_value in enumerate((-.42, -.12, .20, .47)):
                _fur_lock(
                    mesh,
                    (side * .45 * s,
                     (landmarks["body"][1] + .08) * s, z_value * s),
                    (side * .51 * s,
                     (landmarks["body"][1] + .02) * s,
                     (z_value + .07) * s),
                    (side * .56 * s,
                     (landmarks["body"][1] - .08) * s,
                     (z_value + .15) * s),
                    .024 * s, 1, BODY)
    if "quills" in spec.traits:
        for row, z in enumerate(np.linspace(-.42, .54, 10)):
            for side in (-1.0, -.45, 0.0, .45, 1.0):
                base_x = side * .34 * (1.0 - abs(float(z)) * .28)
                mesh.spike((base_x * s, (landmarks["body"][1] + .27) * s, float(z) * s),
                           ((base_x + side * .16) * s,
                            (landmarks["body"][1] + .70 - abs(side) * .06) * s,
                            (float(z) + .15) * s), .026 * s, 1, DETAIL, sides=9)
    # Small silhouette tufts around the chest, cheeks, and joints keep furred
    # species from reading as smooth primitives without inflating texture cost.
    if spec.pattern in {"fur", "stripes", "moss", "spirit"}:
        tuft_material = MAGIC if spec.pattern == "spirit" else BODY
        for side in (-1.0, 1.0):
            for index in range(5):
                angle = -.72 + index * .36
                x = side * (.27 + .04 * math.cos(angle))
                y = head_y - .10 + math.sin(angle) * .18
                _fur_lock(mesh, (x * s, y * s, -.62 * s),
                          ((x + side * .055) * s,
                           (y + math.sin(angle) * .04) * s, -.59 * s),
                          ((x + side * .10) * s,
                           (y + math.sin(angle) * .075) * s, -.54 * s),
                          .017 * s, 2, tuft_material)
        for side in (-1.0, 1.0):
            for z in (-.43, -.17, .13, .41):
                _fur_lock(mesh,
                          (side * .38 * s,
                           (landmarks["body"][1] + .08) * s, z * s),
                          (side * .43 * s,
                           (landmarks["body"][1] + .115) * s, (z + .035) * s),
                          (side * .48 * s,
                           (landmarks["body"][1] + .14) * s, (z + .075) * s),
                          .014 * s, 1, tuft_material)
        if spec.pattern == "spirit":
            for side in (-1.0, 1.0):
                for row, z_value in enumerate(np.linspace(-.46, .52, 8)):
                    start = (side * .34 * s,
                             (landmarks["body"][1] + .13) * s,
                             float(z_value) * s)
                    control = (side * (.43 + .025 * (row % 2)) * s,
                               (landmarks["body"][1] + .25) * s,
                               (float(z_value) + .07) * s)
                    end = (side * (.52 + .035 * (row % 3)) * s,
                           (landmarks["body"][1] + .34 + .03 * (row % 2)) * s,
                           (float(z_value) + .17) * s)
                    _fur_lock(mesh, start, control, end, .021 * s, 1, MAGIC)


def _body_fins(mesh: CreatureMesh, s: float, body_y: float, *, count: int = 5,
               material: int = MAGIC) -> None:
    """Add paired translucent fins without relying on engine-side billboards."""
    for index, z in enumerate(np.linspace(-.38, .48, count)):
        width = .24 + .07 * math.sin(index / max(count - 1, 1) * math.pi)
        for side in (-1.0, 1.0):
            root = (side * .28 * s, (body_y + .05) * s, float(z) * s)
            tip = (side * (.28 + width) * s,
                   (body_y + .16 + .04 * (index % 2)) * s,
                   (float(z) + .08) * s)
            rear = (side * .30 * s, (body_y - .06) * s, (float(z) + .18) * s)
            mesh.tube([root, tip], [.028 * s, .004 * s], 1, material, sides=10)
            mesh.membrane([root, tip, rear], 1, MEMBRANE)


def _quadruped_extras(mesh: CreatureMesh, spec: CreatureSpec,
                      landmarks: dict[str, tuple[float, float, float]]) -> None:
    s = spec.scale
    body_y = landmarks["body"][1]
    head_y = landmarks["head"][1]

    if "two_tails" in spec.traits:
        _tail(mesh, s, landmarks["tail"], length=1.14, curl=.25, thick=.13,
              split=.18)
    elif "brush_tail" in spec.traits:
        _tail(mesh, s, landmarks["tail"], length=1.17, curl=.23, thick=.18)
        mesh.ellipsoid((.04 * s, (body_y + .17) * s, 1.48 * s),
                       (.20 * s, .16 * s, .38 * s), 6, DETAIL,
                       rings=14, sides=24, rotation=(.18, 0.0, .08))
    elif "wisp_tail" in spec.traits:
        _tail(mesh, s, landmarks["tail"], length=1.43, curl=.31, thick=.12,
              material=MAGIC)
        for index in range(5):
            t = index / 4.0
            mesh.spike(((.10 + t * .12) * s, (body_y + .12 + t * .12) * s,
                        (1.15 + t * .22) * s),
                       ((.22 + t * .18) * s, (body_y + .38 + t * .17) * s,
                        (1.24 + t * .24) * s), .036 * s, 6, MAGIC, sides=10)
    elif spec.family == "hare":
        mesh.ellipsoid((0.0, (body_y + .12) * s, .70 * s),
                       (.18 * s, .18 * s, .19 * s), 5, DETAIL,
                       rings=13, sides=22)
    else:
        tail_length = (1.42 if "long_tail" in spec.traits else
                       1.25 if any(t in spec.traits for t in ("ice_tail", "crystal_tail"))
                       else .94)
        tail_material = MAGIC if any(t in spec.traits for t in ("ice_tail", "crystal_tail")) else BODY
        _tail(mesh, s, landmarks["tail"], length=tail_length, curl=.15,
              thick=.14 if spec.family not in {"bear", "boar", "aurochs", "grazer"} else .10,
              material=tail_material)
        if any(t in spec.traits for t in ("ice_tail", "crystal_tail")):
            for index, z in enumerate(np.linspace(.88, 1.68, 7)):
                side = -1.0 if index % 2 else 1.0
                mesh.faceted_ellipsoid(
                    (side * (.08 + index * .012) * s,
                     (body_y + .12 + .045 * math.sin(index * .9)) * s,
                     float(z) * s),
                    (.075 * s, .055 * s, .13 * s), 6, MAGIC,
                    rings=5, sides=9,
                    rotation=(.10, side * .25, side * .18))

    if "fins" in spec.traits:
        _body_fins(mesh, s, body_y, count=4)
        for side in (-1.0, 1.0):
            mesh.membrane([
                (side * .17 * s, (head_y + .06) * s, -.79 * s),
                (side * .48 * s, (head_y + .25) * s, -.67 * s),
                (side * .30 * s, (head_y - .03) * s, -.57 * s),
            ], 3, MEMBRANE)
    if "mirror_scales" in spec.traits:
        for row, z in enumerate(np.linspace(-.36, .45, 6)):
            for side in (-1.0, 1.0):
                mesh.ellipsoid((side * (.31 - abs(float(z)) * .05) * s,
                                (body_y + .10 + .04 * (row % 2)) * s,
                                float(z) * s),
                               (.10 * s, .028 * s, .13 * s), 1, MAGIC,
                               rings=7, sides=14, rotation=(0.0, side * .22, side * .20))
    if "ice_crest" in spec.traits:
        _spine_row(mesh, s, -.89, -.58, 5, head_y + .16, .22,
                   material=MAGIC, joint=3)
    if "spectral_mane" in spec.traits:
        for index in range(24):
            angle = math.tau * index / 24.0
            base = (math.cos(angle) * .30 * s,
                    (head_y + math.sin(angle) * .27) * s, -.58 * s)
            mesh.spike(base,
                       ((math.cos(angle) * .43 + math.sin(index * 2.3) * .06) * s,
                        (head_y + math.sin(angle) * .42 + .12) * s, -.42 * s),
                       .038 * s, 2, MAGIC, sides=10)
    if "leaf_wings" in spec.traits:
        _wing(mesh, s, -1.0, leafy=True)
        _wing(mesh, s, 1.0, leafy=True)
    if "tuft_tail" in spec.traits:
        for index in range(11):
            angle = math.tau * index / 11.0
            mesh.spike((math.cos(angle) * .07 * s, (body_y + .11) * s,
                        1.42 * s),
                       (math.cos(angle) * .19 * s,
                        (body_y + .11 + math.sin(angle) * .17) * s,
                        1.62 * s), .025 * s, 6, DETAIL, sides=9)
    if spec.family == "otter":
        # Crownwater scale-mail saddle, side drapes, and hanging brass charms
        # are central to the concept—not optional surface noise.
        mesh.faceted_ellipsoid((0.0, (body_y + .245) * s, .08 * s),
                               (.32 * s, .075 * s, .43 * s), 1, MAGIC,
                               rings=6, sides=12)
        for side in (-1.0, 1.0):
            mesh.membrane([
                (side * .27 * s, (body_y + .20) * s, -.27 * s),
                (side * .43 * s, (body_y + .08) * s, -.18 * s),
                (side * .42 * s, (body_y - .14) * s, .35 * s),
                (side * .26 * s, (body_y + .15) * s, .43 * s),
            ], 1, MAGIC)
            for index, z in enumerate((-.18, .03, .25)):
                mesh.tube([(side * .39 * s, (body_y - .02) * s, z * s),
                           (side * .43 * s, (body_y - .20 - index * .015) * s,
                            (z + .02) * s)],
                          [.012 * s, .006 * s], 1, DETAIL, sides=9)
                mesh.faceted_ellipsoid(
                    (side * .43 * s, (body_y - .25 - index * .015) * s,
                     (z + .02) * s),
                    (.045 * s, .052 * s, .018 * s), 1, MAGIC,
                    rings=4, sides=8)
        for z in (-.27, .35):
            for side in (-1.0, 1.0):
                mesh.faceted_ellipsoid(
                    (side * .31 * s, (body_y + .15) * s, z * s),
                    (.13 * s, .050 * s, .15 * s), 1, MAGIC,
                    rings=5, sides=9, rotation=(0.0, side * .18, side * .12))


def _feline(mesh: CreatureMesh, spec: CreatureSpec) -> dict[str, tuple[float, float, float]]:
    """Crouched, digitigrade cat anatomy for lion, rimeclaw, and stalker."""
    s = spec.scale
    body_y, head_y = .73, .91
    mesh.ellipsoid((0.0, body_y * s, .08 * s), (.35 * s, .27 * s, .84 * s),
                   1, BODY, rings=26, sides=44, rotation=(-.035, 0.0, 0.0))
    mesh.ellipsoid((0.0, (body_y + .01) * s, -.36 * s),
                   (.36 * s, .30 * s, .37 * s), 1, BODY,
                   rings=19, sides=34, secondary_joint=2, secondary_weight=.12)
    mesh.ellipsoid((0.0, (body_y - .01) * s, .45 * s),
                   (.39 * s, .31 * s, .39 * s), 1, BODY,
                   rings=20, sides=36, secondary_joint=5, secondary_weight=.12)
    mesh.ellipsoid((0.0, (body_y - .12) * s, -.02 * s),
                   (.25 * s, .12 * s, .59 * s), 1, UNDER,
                   rings=15, sides=29)
    mesh.tube([(0.0, (body_y + .08) * s, -.42 * s),
               (0.0, (head_y - .04) * s, -.59 * s),
               (0.0, head_y * s, -.72 * s)],
              [.20 * s, .17 * s, .14 * s], 2, BODY, sides=26,
              secondary_joint=3, secondary_weight=.22)
    mesh.ellipsoid((0.0, head_y * s, -.77 * s),
                   (.23 * s, .21 * s, .29 * s), 3, BODY,
                   rings=22, sides=40)
    # Paired cheek pads and a short feline muzzle retain the broad-cat face
    # without returning to the generic canine mask.
    for side in (-1.0, 1.0):
        mesh.ellipsoid((side * .105 * s, (head_y - .07) * s, -1.00 * s),
                       (.115 * s, .095 * s, .16 * s), 4, UNDER,
                       rings=14, sides=26, rotation=(0.0, side * .08, 0.0))
    mesh.ellipsoid((0.0, (head_y - .035) * s, -1.135 * s),
                   (.055 * s, .038 * s, .035 * s), 4, DARK,
                   rings=10, sides=19)
    _eye_pair(mesh, s, (0.0, head_y + .055, -.94), .18, size=.032)

    for side, joints in ((-1.0, (7, 8, 9)), (1.0, (10, 11, 12))):
        shoulder = (side * .27 * s, .72 * s, -.39 * s)
        elbow = (side * .30 * s, .39 * s, -.43 * s)
        wrist = (side * .25 * s, .15 * s, -.57 * s)
        mesh.ellipsoid(shoulder, (.13 * s, .20 * s, .16 * s),
                       joints[0], BODY, rings=14, sides=26)
        mesh.tube([shoulder, elbow, wrist], [.095 * s, .066 * s, .040 * s],
                  joints[0], BODY, sides=20,
                  secondary_joint=joints[1], secondary_weight=.24)
        _paw(mesh, side * .25, .055, -.70, s, joints[2], broad=.76,
             claws=True, material=BODY)
    for side, joints in ((-1.0, (13, 14, 15)), (1.0, (16, 17, 18))):
        hip = (side * .29 * s, .72 * s, .40 * s)
        knee = (side * .36 * s, .43 * s, .57 * s)
        hock = (side * .29 * s, .18 * s, .34 * s)
        mesh.ellipsoid(hip, (.19 * s, .24 * s, .23 * s),
                       joints[0], BODY, rings=16, sides=29)
        mesh.tube([hip, knee, hock], [.13 * s, .085 * s, .045 * s],
                  joints[0], BODY, sides=21,
                  secondary_joint=joints[1], secondary_weight=.25)
        _paw(mesh, side * .28, .055, .18, s, joints[2], broad=.84,
             claws=True, material=BODY)
    landmarks = {"head": (0.0, head_y, -.77), "body": (0.0, body_y, .08),
                 "tail": (0.0, body_y + .02, .72),
                 "snout": (0.0, head_y - .04, -1.14)}
    _quadruped_features(mesh, spec, landmarks)
    _quadruped_extras(mesh, spec, landmarks)
    return landmarks


def _reptile(mesh: CreatureMesh, spec: CreatureSpec) -> dict[str, tuple[float, float, float]]:
    s = spec.scale
    crocodilian = spec.family == "crocodile"
    grazer = spec.family == "grazer"
    slender = spec.family in {"wyrm", "stalker"}
    serpentine = spec.family == "basilisk"
    body_y = .48 if crocodilian else (.56 if grazer else .64)
    body_width = (.34 if serpentine else .46 if grazer else
                  (.42 if slender else (.61 if crocodilian else .49)))
    body_length = (1.14 if serpentine else 1.02 if grazer else
                   (1.04 if slender else (1.20 if crocodilian else .90)))
    mesh.ellipsoid((0.0, body_y * s, .06 * s),
                   (body_width * s, (.25 if crocodilian else .31) * s,
                    body_length * s), 1, BODY, rings=22, sides=40)
    mesh.ellipsoid((0.0, (body_y - .13) * s, -.02 * s),
                   (body_width * .82 * s, .15 * s, body_length * .86 * s),
                   1, UNDER, rings=15, sides=30)
    neck_y = body_y + (.13 if not crocodilian else .03)
    mesh.tube([(0.0, neck_y * s, -.53 * s),
               (0.0, (neck_y + .08) * s, -.78 * s),
               (0.0, (neck_y + .04) * s, -1.00 * s)],
              [.30 * s, .27 * s, .24 * s], 2, BODY, sides=28,
              secondary_joint=3, secondary_weight=.18)
    head_y = neck_y + .04
    mesh.ellipsoid((0.0, head_y * s, -1.05 * s),
                   ((.38 if crocodilian else .30) * s, .22 * s,
                    (.42 if crocodilian else .34) * s),
                   3, BODY, rings=18, sides=34)
    mesh.ellipsoid((0.0, (head_y - .08) * s,
                    (-1.43 if crocodilian else -1.31) * s),
                   ((.34 if crocodilian else .22) * s,
                    (.105 if crocodilian else .105) * s,
                    (.46 if crocodilian else .31) * s),
                   4, BODY, rings=17, sides=32)
    mesh.ellipsoid((0.0, (head_y - .145) * s,
                    (-1.40 if crocodilian else -1.29) * s),
                   ((.31 if crocodilian else .20) * s, .055 * s,
                    (.40 if crocodilian else .27) * s),
                   4, UNDER, rings=12, sides=26)
    _eye_pair(mesh, s, (0.0, head_y + .12, -1.18),
              .27 if crocodilian else .22, size=.039)
    for side in (-1.0, 1.0):
        mesh.ellipsoid((side * (.13 if crocodilian else .09) * s,
                        (head_y + .005) * s,
                        (-1.82 if crocodilian else -1.57) * s),
                       (.025 * s, .014 * s, .010 * s), 4, DARK,
                       rings=6, sides=11)

    stance = .42 if crocodilian else (.38 if grazer else (.29 if serpentine else .34))
    front_z, rear_z = -.49, .50
    for side, joints, z in (
        (-1.0, (7, 8, 9), front_z), (1.0, (10, 11, 12), front_z),
        (-1.0, (13, 14, 15), rear_z), (1.0, (16, 17, 18), rear_z),
    ):
        hip_x = side * stance
        elbow_x = side * (stance + (.22 if crocodilian else .15))
        mesh.tube([(hip_x * s, body_y * s, z * s),
                   (elbow_x * s, .25 * s, (z - .04) * s)],
                  [.105 * s, .075 * s], joints[0], BODY, sides=18,
                  secondary_joint=joints[1], secondary_weight=.20)
        mesh.tube([(elbow_x * s, .25 * s, (z - .04) * s),
                   ((elbow_x + side * .06) * s, .10 * s, (z - .17) * s)],
                  [.075 * s, .045 * s], joints[1], BODY, sides=16,
                  secondary_joint=joints[2], secondary_weight=.18)
        _paw(mesh, elbow_x + side * .06, .065, z - .23, s, joints[2],
             broad=.85, claws=True)

    tail_start = (0.0, body_y, .84 if not crocodilian else 1.02)
    points, radii = [], []
    tail_length = (2.05 if serpentine else 1.58 if grazer else
                   1.66 if ("long_tail" in spec.traits or crocodilian) else 1.30)
    for index in range(13):
        t = index / 12.0
        points.append((math.sin(t * math.pi) * (.31 if serpentine else .14) * s,
                       (body_y + (.18 if serpentine else .05) * math.sin(t * math.pi * 1.4)) * s,
                       (tail_start[2] + tail_length * t) * s))
        radii.append((.30 * (1.0 - t * .88) + .018) * s)
    mesh.tube(points, radii, 5, BODY, sides=24,
              secondary_joint=6, secondary_weight=.32)

    if "teeth" in spec.traits:
        for side in (-1.0, 1.0):
            for z in np.linspace(-1.72 if crocodilian else -1.53, -1.15, 8):
                mesh.spike((side * .24 * s, (head_y - .12) * s, float(z) * s),
                           (side * .24 * s, (head_y - .22) * s, (float(z) - .02) * s),
                           .018 * s, 4, BONE, sides=9)
    if "wings" in spec.traits:
        _wing(mesh, s, -1.0)
        _wing(mesh, s, 1.0)
    if "fins" in spec.traits:
        _body_fins(mesh, s, body_y, count=5)
    spine_material = MAGIC if any(t in spec.traits for t in (
        "glass_spines", "sun_spines", "crystal_spines")) else DETAIL
    if any(t in spec.traits for t in (
        "glass_spines", "dust_spines", "leaf_spines", "sun_spines",
        "crystal_spines", "dorsal_scutes")):
        if crocodilian and "dorsal_scutes" in spec.traits:
            _dorsal_plate_field(
                mesh, s, z_start=-.73, z_end=1.38,
                crest_y=body_y + .285, half_width=.39,
                rows=15, columns=5, crown_drop=.095, end_drop=.025,
                plate_height=.034, material=DETAIL,
                accent_material=BODY)
            # Smaller cheek and flank scutes bridge the armor into the limbs.
            for side in (-1.0, 1.0):
                for row, z_value in enumerate(np.linspace(-.64, .97, 11)):
                    mesh.faceted_ellipsoid(
                        (side * .49 * s,
                         (body_y + .11 + .018 * (row % 2)) * s,
                         float(z_value) * s),
                        (.095 * s, .030 * s, .12 * s), 1, BODY,
                        rings=5, sides=9,
                        rotation=(0.0, side * .32, side * .28))
        else:
            _spine_row(mesh, s, -.68, .82, 14,
                       body_y + .26, .31, material=spine_material)
    if "armored_plates" in spec.traits:
        _dorsal_plate_field(
            mesh, s, z_start=-.59, z_end=.68,
            crest_y=body_y + .325, half_width=.38,
            rows=9, columns=5, crown_drop=.105, end_drop=.035,
            plate_height=.040, material=MAGIC,
            accent_material=DETAIL)
        for index, z_value in enumerate(np.linspace(-.51, .58, 7)):
            side = -1.0 if index % 2 else 1.0
            mesh.spike(
                (side * .07 * s, (body_y + .31) * s, float(z_value) * s),
                (side * .19 * s,
                 (body_y + .68 + .08 * math.sin(index * .9)) * s,
                 (float(z_value) + .04) * s),
                .044 * s, 1, MAGIC, sides=13)
    elif "crystal_spines" in spec.traits:
        _dorsal_plate_field(
            mesh, s, z_start=-.55, z_end=.69,
            crest_y=body_y + .30, half_width=body_width * .66,
            rows=9, columns=5, crown_drop=.09, end_drop=.03,
            plate_height=.038, material=MAGIC,
            accent_material=DETAIL)
    if spec.family == "basilisk":
        _dorsal_plate_field(
            mesh, s, z_start=-.58, z_end=.76,
            crest_y=body_y + .285, half_width=.30,
            rows=10, columns=5, crown_drop=.085, end_drop=.025,
            plate_height=.026, material=BODY,
            accent_material=MAGIC)
    if "crystal_horns" in spec.traits:
        for side in (-1.0, 1.0):
            mesh.spike((side * .14 * s, (head_y + .12) * s, -1.08 * s),
                       (side * .50 * s, (head_y + .33) * s, -1.20 * s),
                       .070 * s, 3, MAGIC, sides=17)
    if "leaf_crown" in spec.traits:
        for index in range(9):
            angle = (index - 4) * .22
            root = (math.sin(angle) * .20 * s, (head_y + .14) * s, -1.04 * s)
            tip = (math.sin(angle) * .48 * s,
                   (head_y + .48 - abs(angle) * .12) * s,
                   (-1.00 + math.cos(angle) * .13) * s)
            mesh.tube([root, tip], [.028 * s, .006 * s], 3, MAGIC, sides=10)
            center = tuple(np.asarray(root) * .24 + np.asarray(tip) * .76)
            mesh.faceted_ellipsoid(
                center, (.060 * s, .145 * s, .025 * s), 3, MAGIC,
                rings=5, sides=8, rotation=(angle * .35, 0.0, -angle))
    if "vine_mane" in spec.traits:
        for side in (-1.0, 1.0):
            for index in range(7):
                z = -.72 + index * .18
                mesh.spike((side * .25 * s, (body_y + .19) * s, z * s),
                           (side * (.46 + .05 * (index % 2)) * s,
                            (body_y + .35) * s, (z + .10) * s),
                           .028 * s, 1, MAGIC, sides=10)
    if "whiskers" in spec.traits:
        _whiskers(mesh, s, head_y - .03, -1.47 if crocodilian else -1.37, count=4)
    return {"head": (0.0, head_y, -1.05), "body": (0.0, body_y, .06),
            "tail": tail_start, "snout": (0.0, head_y - .08, -1.43)}


def _upright_drake(mesh: CreatureMesh, spec: CreatureSpec) -> dict[str, tuple[float, float, float]]:
    """High-chested aquatic wyvern matching the Lakeglass concept posture."""
    s = spec.scale
    mesh.ellipsoid((0.0, 1.02 * s, .04 * s), (.42 * s, .62 * s, .48 * s),
                   1, BODY, rings=27, sides=46, rotation=(-.18, 0.0, 0.0))
    mesh.ellipsoid((0.0, .95 * s, -.30 * s), (.31 * s, .46 * s, .18 * s),
                   1, UNDER, rings=18, sides=34, rotation=(-.16, 0.0, 0.0))
    mesh.ellipsoid((0.0, .70 * s, .25 * s), (.45 * s, .34 * s, .42 * s),
                   1, BODY, rings=20, sides=38, secondary_joint=5,
                   secondary_weight=.12)
    mesh.tube([(0.0, 1.34 * s, -.16 * s),
               (0.0, 1.55 * s, -.40 * s),
               (0.0, 1.70 * s, -.64 * s)],
              [.27 * s, .23 * s, .18 * s], 2, BODY, sides=30,
              secondary_joint=3, secondary_weight=.20)
    mesh.ellipsoid((0.0, 1.73 * s, -.72 * s), (.31 * s, .25 * s, .35 * s),
                   3, BODY, rings=22, sides=40)
    mesh.ellipsoid((0.0, 1.64 * s, -1.01 * s), (.22 * s, .115 * s, .34 * s),
                   4, UNDER, rings=17, sides=32)
    mesh.ellipsoid((0.0, 1.58 * s, -.99 * s), (.20 * s, .060 * s, .30 * s),
                   4, BODY, rings=13, sides=27)
    _eye_pair(mesh, s, (0.0, 1.82, -.87), .225, size=.041)
    for side in (-1.0, 1.0):
        mesh.spike((side * .13 * s, 1.88 * s, -.66 * s),
                   (side * .34 * s, 2.15 * s, -.60 * s),
                   .060 * s, 3, MAGIC, sides=16)
        mesh.spike((side * .12 * s, 1.68 * s, -1.24 * s),
                   (side * .13 * s, 1.53 * s, -1.28 * s),
                   .022 * s, 4, BONE, sides=10)
    _whiskers(mesh, s, 1.66, -1.22, count=4)

    # Compact grasping forelimbs and long digitigrade hind legs create the
    # concept's upright silhouette without sacrificing the shared animation rig.
    for side, joints in ((-1.0, (7, 8, 9)), (1.0, (10, 11, 12))):
        shoulder = (side * .32 * s, 1.27 * s, -.18 * s)
        elbow = (side * .54 * s, .98 * s, -.39 * s)
        hand = (side * .42 * s, .78 * s, -.66 * s)
        mesh.ellipsoid(shoulder, (.14 * s, .18 * s, .15 * s), joints[0], BODY,
                       rings=13, sides=24)
        mesh.tube([shoulder, elbow, hand], [.105 * s, .072 * s, .037 * s],
                  joints[0], BODY, sides=19, secondary_joint=joints[1],
                  secondary_weight=.24)
        for finger in (-.07, 0.0, .07):
            mesh.spike(hand, ((side * .44 + finger) * s, .70 * s, -.87 * s),
                       .014 * s, joints[2], BONE, sides=9)
    for side, joints in ((-1.0, (13, 14, 15)), (1.0, (16, 17, 18))):
        hip = (side * .28 * s, .72 * s, .23 * s)
        knee = (side * .51 * s, .38 * s, .33 * s)
        ankle = (side * .29 * s, .13 * s, -.02 * s)
        mesh.ellipsoid(hip, (.22 * s, .28 * s, .24 * s), joints[0], BODY,
                       rings=15, sides=28)
        mesh.tube([hip, knee, ankle], [.155 * s, .105 * s, .055 * s],
                  joints[0], BODY, sides=22, secondary_joint=joints[1],
                  secondary_weight=.25)
        _paw(mesh, side * .30, .065, -.12, s, joints[2], broad=.92, claws=True)

    for side, joint in ((-1.0, 19), (1.0, 20)):
        root = (side * .27 * s, 1.44 * s, .02 * s)
        elbow = (side * .94 * s, 1.85 * s, .16 * s)
        tip = (side * 1.54 * s, 1.62 * s, .48 * s)
        mesh.tube([root, elbow, tip], [.080 * s, .052 * s, .012 * s],
                  joint, DETAIL, sides=18)
        fingers = [
            (side * 1.32 * s, 1.35 * s, .69 * s),
            (side * 1.06 * s, 1.16 * s, .82 * s),
            (side * .76 * s, 1.01 * s, .86 * s),
            (side * .48 * s, .97 * s, .72 * s),
        ]
        roots = [elbow,
                 (side * .78 * s, 1.68 * s, .15 * s),
                 (side * .64 * s, 1.58 * s, .11 * s),
                 (side * .50 * s, 1.51 * s, .08 * s)]
        for index, (finger_root, finger_tip) in enumerate(zip(roots, fingers)):
            mesh.tube([finger_root, finger_tip],
                      [(.052 - index * .006) * s,
                       (.010 - index * .0015) * s],
                      joint, DETAIL, sides=max(11, 16 - index))
        mesh.membrane([root, elbow, tip, fingers[0]], joint, MEMBRANE)
        previous = fingers[0]
        for finger in fingers[1:]:
            mesh.membrane([root, previous, finger], joint, MEMBRANE)
            previous = finger

    tail_points, tail_radii = [], []
    for index in range(15):
        t = index / 14.0
        tail_points.append((math.sin(t * math.pi) * .18 * s,
                            (.78 + .18 * math.sin(t * math.pi * 1.2)) * s,
                            (.38 + 2.05 * t) * s))
        tail_radii.append((.28 * (1.0 - t * .90) + .014) * s)
    mesh.tube(tail_points, tail_radii, 5, BODY, sides=26,
              secondary_joint=6, secondary_weight=.32)
    _spine_row(mesh, s, -.45, .80, 13, 1.45, .26, material=MAGIC)
    _dorsal_plate_field(
        mesh, s, z_start=-.31, z_end=.43, crest_y=1.585,
        half_width=.31, rows=7, columns=5, crown_drop=.13,
        end_drop=.045, plate_height=.025, material=BODY,
        accent_material=MAGIC)
    _body_fins(mesh, s, 1.05, count=5)
    return {"head": (0.0, 1.73, -.72), "body": (0.0, 1.02, .04),
            "tail": (0.0, .78, .38), "snout": (0.0, 1.64, -1.30)}


def _quadruped_drake(mesh: CreatureMesh, spec: CreatureSpec) -> dict[str, tuple[float, float, float]]:
    """Four-legged, long-necked dragon anatomy for Prism and Dustscale."""
    s = spec.scale
    body_y, head_y = .69, .98
    mesh.ellipsoid((0.0, body_y * s, .05 * s), (.43 * s, .33 * s, .90 * s),
                   1, BODY, rings=25, sides=44)
    mesh.ellipsoid((0.0, (body_y + .02) * s, -.40 * s),
                   (.45 * s, .37 * s, .40 * s), 1, BODY,
                   rings=20, sides=36, secondary_joint=2, secondary_weight=.12)
    mesh.ellipsoid((0.0, (body_y - .11) * s, -.02 * s),
                   (.30 * s, .15 * s, .69 * s), 1, UNDER,
                   rings=16, sides=31)
    mesh.tube([(0.0, (body_y + .11) * s, -.43 * s),
               (0.0, .91 * s, -.64 * s),
               (0.0, head_y * s, -.85 * s)],
              [.25 * s, .21 * s, .16 * s], 2, BODY, sides=28,
              secondary_joint=3, secondary_weight=.22)
    mesh.ellipsoid((0.0, head_y * s, -.94 * s),
                   (.27 * s, .21 * s, .34 * s), 3, BODY,
                   rings=20, sides=38)
    # Wedge-shaped upper/lower jaws, pronounced brow plates, and small inset
    # eyes replace the rounded salamander head used by the first pass.
    mesh.ellipsoid((0.0, (head_y - .045) * s, -1.24 * s),
                   (.205 * s, .105 * s, .36 * s), 4, BODY,
                   rings=16, sides=31)
    mesh.ellipsoid((0.0, (head_y - .145) * s, -1.21 * s),
                   (.19 * s, .052 * s, .32 * s), 4, UNDER,
                   rings=12, sides=25)
    for side in (-1.0, 1.0):
        mesh.faceted_ellipsoid(
            (side * .17 * s, (head_y + .13) * s, -1.02 * s),
            (.13 * s, .055 * s, .18 * s), 3,
            MAGIC if spec.pattern == "crystal" else DETAIL,
            rings=5, sides=9, rotation=(0.0, side * .12, side * .15))
        mesh.ellipsoid((side * .095 * s, (head_y + .005) * s, -1.58 * s),
                       (.020 * s, .012 * s, .009 * s), 4, DARK,
                       rings=6, sides=11)
    _eye_pair(mesh, s, (0.0, head_y + .095, -1.075), .205, size=.029)
    for side in (-1.0, 1.0):
        for tooth, z in enumerate(np.linspace(-1.47, -1.08, 5)):
            mesh.spike((side * .17 * s, (head_y - .115) * s, float(z) * s),
                       (side * .17 * s, (head_y - .19) * s,
                        (float(z) - .01) * s), .013 * s, 4, BONE, sides=8)
    if "horns" in spec.traits:
        for side in (-1.0, 1.0):
            mesh.spike((side * .15 * s, (head_y + .16) * s, -.92 * s),
                       (side * .37 * s, (head_y + .42) * s, -.75 * s),
                       .058 * s, 3, DETAIL, sides=15)

    for side, joints, z in (
        (-1.0, (7, 8, 9), -.39), (1.0, (10, 11, 12), -.39),
        (-1.0, (13, 14, 15), .46), (1.0, (16, 17, 18), .46),
    ):
        rear = z > 0.0
        hip = (side * .34 * s, .67 * s, z * s)
        knee = (side * .47 * s, (.37 if rear else .40) * s,
                (z + (.14 if rear else -.05)) * s)
        ankle = (side * .34 * s, .14 * s,
                 (z - (.02 if rear else .17)) * s)
        mesh.ellipsoid(hip,
                       ((.18 if rear else .15) * s, .21 * s,
                        (.21 if rear else .17) * s), joints[0], BODY,
                       rings=14, sides=27)
        mesh.tube([hip, knee, ankle],
                  [(.13 if rear else .105) * s, .078 * s, .042 * s],
                  joints[0], BODY, sides=20,
                  secondary_joint=joints[1], secondary_weight=.24)
        _paw(mesh, side * .34, .055, z - (.16 if not rear else .12),
             s, joints[2], broad=.78, claws=True, material=BODY)
    _wing(mesh, s, -1.0)
    _wing(mesh, s, 1.0)
    tail_points, tail_radii = [], []
    for index in range(15):
        t = index / 14.0
        tail_points.append((math.sin(t * math.pi) * .20 * s,
                            (body_y + .10 * math.sin(t * math.pi * 1.25)) * s,
                            (.76 + 1.92 * t) * s))
        tail_radii.append((.27 * (1.0 - t * .90) + .014) * s)
    mesh.tube(tail_points, tail_radii, 5, BODY, sides=25,
              secondary_joint=6, secondary_weight=.32)
    _spine_row(mesh, s, -.54, .90, 15, body_y + .30, .25,
               material=MAGIC if spec.pattern == "crystal" else DETAIL)
    if spec.pattern == "crystal":
        _dorsal_plate_field(
            mesh, s, z_start=-.51, z_end=.67,
            crest_y=body_y + .325, half_width=.31,
            rows=9, columns=5, crown_drop=.09, end_drop=.03,
            plate_height=.036, material=MAGIC,
            accent_material=DETAIL)
        for index, z in enumerate(np.linspace(-.50, .72, 8)):
            side = (-.07 if index % 2 else .07)
            height = .40 + .14 * math.sin(index / 7.0 * math.pi)
            mesh.spike((side * s, (body_y + .30) * s, float(z) * s),
                       ((side * 2.4) * s, (body_y + .30 + height) * s,
                       (float(z) + .05) * s),
                       (.055 + .010 * (index % 2)) * s, 1, MAGIC, sides=15)
    else:
        _dorsal_plate_field(
            mesh, s, z_start=-.51, z_end=.70,
            crest_y=body_y + .315, half_width=.31,
            rows=10, columns=5, crown_drop=.09, end_drop=.025,
            plate_height=.024, material=BODY,
            accent_material=DETAIL)
        # Dustscale's concept uses banded facial and shoulder scales as well as
        # a dorsal crest, so carry the small armor forward onto the brow.
        for side in (-1.0, 1.0):
            for index, z_value in enumerate((-1.27, -1.14, -1.01)):
                mesh.faceted_ellipsoid(
                    (side * (.12 + index * .025) * s,
                     (head_y + .125 - index * .018) * s,
                     z_value * s),
                    (.085 * s, .026 * s, .10 * s), 3, DETAIL,
                    rings=5, sides=9,
                    rotation=(0.0, side * .18, side * .20))
    return {"head": (0.0, head_y, -.94), "body": (0.0, body_y, .05),
            "tail": (0.0, body_y, .76),
            "snout": (0.0, head_y - .05, -1.58)}


def _snowcrest_hare(mesh: CreatureMesh, spec: CreatureSpec) -> dict[str, tuple[float, float, float]]:
    """Seated arctic hare with the tall, narrow concept silhouette."""
    s = spec.scale
    # Upright ribcage, pear-shaped haunches, and tucked forelegs replace the
    # canine quadruped that previously stood in for the hare.
    mesh.ellipsoid((0.0, .70 * s, .12 * s), (.31 * s, .47 * s, .42 * s),
                   1, BODY, rings=25, sides=42, rotation=(-.08, 0.0, 0.0))
    mesh.ellipsoid((0.0, .67 * s, -.18 * s), (.25 * s, .37 * s, .18 * s),
                   1, UNDER, rings=17, sides=32)
    for side, joint in ((-1.0, 13), (1.0, 16)):
        mesh.ellipsoid((side * .25 * s, .43 * s, .31 * s),
                       (.25 * s, .29 * s, .32 * s), joint, BODY,
                       rings=19, sides=34, rotation=(side * .06, 0.0, side * .10))
    mesh.tube([(0.0, .98 * s, -.12 * s), (0.0, 1.16 * s, -.31 * s)],
              [.21 * s, .18 * s], 2, BODY, sides=26,
              secondary_joint=3, secondary_weight=.22)
    mesh.ellipsoid((0.0, 1.25 * s, -.38 * s), (.25 * s, .26 * s, .28 * s),
                   3, BODY, rings=23, sides=40)
    mesh.ellipsoid((0.0, 1.18 * s, -.64 * s), (.16 * s, .11 * s, .23 * s),
                   4, UNDER, rings=16, sides=30)
    mesh.ellipsoid((0.0, 1.205 * s, -.83 * s), (.040 * s, .029 * s, .028 * s),
                   4, DARK, rings=9, sides=17)
    _eye_pair(mesh, s, (0.0, 1.34, -.55), .20, size=.032)

    # Broad translucent-blue ears have an inner-fur inset and a tapered tip.
    for side in (-1.0, 1.0):
        mesh.ellipsoid((side * .14 * s, 1.68 * s, -.27 * s),
                       (.105 * s, .43 * s, .075 * s), 3, BODY,
                       rings=18, sides=30,
                       rotation=(side * -.05, side * .05, side * -.09))
        mesh.ellipsoid((side * .142 * s, 1.69 * s, -.334 * s),
                       (.061 * s, .33 * s, .022 * s), 3, MAGIC,
                       rings=13, sides=24,
                       rotation=(side * -.05, side * .05, side * -.09))
        mesh.spike((side * .14 * s, 1.96 * s, -.27 * s),
                   (side * .13 * s, 2.13 * s, -.24 * s),
                   .065 * s, 3, BODY, sides=15)

    # Tucked forelegs and long snowshoe hind feet.
    for side, joints in ((-1.0, (7, 8, 9)), (1.0, (10, 11, 12))):
        shoulder = (side * .20 * s, .83 * s, -.25 * s)
        wrist = (side * .17 * s, .19 * s, -.48 * s)
        mesh.tube([shoulder,
                   (side * .22 * s, .48 * s, -.36 * s), wrist],
                  [.082 * s, .065 * s, .036 * s], joints[0], BODY, sides=19,
                  secondary_joint=joints[1], secondary_weight=.24)
        _paw(mesh, side * .17, .055, -.57, s, joints[2], broad=.72,
             material=BODY)
    for side, joints in ((-1.0, (13, 14, 15)), (1.0, (16, 17, 18))):
        ankle = (side * .27 * s, .12 * s, .29 * s)
        mesh.tube([(side * .25 * s, .42 * s, .29 * s), ankle],
                  [.13 * s, .055 * s], joints[1], BODY, sides=19)
        mesh.ellipsoid((side * .28 * s, .095 * s, -.03 * s),
                       (.105 * s, .070 * s, .33 * s), joints[2], BODY,
                       rings=14, sides=26, rotation=(-.10, 0.0, 0.0))
    mesh.ellipsoid((0.0, .64 * s, .54 * s), (.17 * s, .17 * s, .18 * s),
                   5, UNDER, rings=14, sides=24)
    _spine_row(mesh, s, -.50, .13, 7, 1.43, .22, material=MAGIC, joint=3)
    for side in (-1.0, 1.0):
        for index in range(4):
            angle = -.55 + index * .36
            start = (side * .21 * s, (1.23 + math.sin(angle) * .16) * s,
                     -.35 * s)
            _fur_lock(mesh, start,
                      ((side * .26) * s, (1.23 + math.sin(angle) * .20) * s,
                       -.31 * s),
                      ((side * .31) * s, (1.23 + math.sin(angle) * .24) * s,
                       -.25 * s), .015 * s, 3, BODY)
    return {"head": (0.0, 1.25, -.38), "body": (0.0, .70, .12),
            "tail": (0.0, .64, .54), "snout": (0.0, 1.18, -.83)}


def _turtle(mesh: CreatureMesh, spec: CreatureSpec) -> dict[str, tuple[float, float, float]]:
    s = spec.scale
    mesh.ellipsoid((0.0, .53 * s, .06 * s), (.79 * s, .28 * s, .97 * s),
                   1, UNDER, rings=18, sides=36)
    mesh.ellipsoid((0.0, .74 * s, .10 * s), (.88 * s, .55 * s, 1.02 * s),
                   1, BODY, rings=24, sides=42)
    # Interlocking, contour-following scutes carry the architectural bronze
    # shell pattern from the Four Gates concept all the way to the silhouette.
    _dorsal_plate_field(
        mesh, s, z_start=-.72, z_end=.76, crest_y=1.265,
        half_width=.65, rows=9, columns=7, crown_drop=.33,
        end_drop=.11, plate_height=.034, material=BODY,
        accent_material=MAGIC)
    # A faceted marginal ring gives the shell its armored, architectural edge.
    for index in range(30):
        angle = math.tau * index / 30.0
        x = math.cos(angle) * .79
        z = math.sin(angle) * .92
        mesh.faceted_ellipsoid(
            (x * s, (.73 + .035 * max(0.0, math.sin(angle))) * s, z * s),
            (.11 * s, .055 * s, .135 * s), 1,
            MAGIC if index % 7 == 0 else BODY, rings=5, sides=9,
            rotation=(0.0, -angle, math.cos(angle) * .18))
    mesh.tube([(0.0, .56 * s, -.72 * s), (0.0, .55 * s, -1.08 * s)],
              [.25 * s, .19 * s], 2, BODY, sides=24, secondary_joint=3,
              secondary_weight=.25)
    mesh.ellipsoid((0.0, .57 * s, -1.18 * s), (.28 * s, .22 * s, .34 * s),
                   3, BODY, rings=17, sides=30)
    _eye_pair(mesh, s, (0.0, .65, -1.38), .19, size=.033)
    for row, z in enumerate((-.98, -1.16, -1.32)):
        for side in (-1.0, 0.0, 1.0):
            mesh.ellipsoid((side * .17 * s, (.72 + .025 * (row % 2)) * s,
                            z * s),
                           (.075 * s, .025 * s, .075 * s), 3,
                           MAGIC if row == 1 and side == 0.0 else BODY,
                           rings=6, sides=12)
    for side, joints, z in (
        (-1.0, (7, 8, 9), -.56), (1.0, (10, 11, 12), -.56),
        (-1.0, (13, 14, 15), .56), (1.0, (16, 17, 18), .56),
    ):
        mesh.tube([(side * .54 * s, .48 * s, z * s),
                   (side * .86 * s, .23 * s, (z - .10) * s)],
                  [.16 * s, .10 * s], joints[0], BODY, sides=20,
                  secondary_joint=joints[1], secondary_weight=.22)
        _paw(mesh, side * .88, .10, z - .18, s, joints[2], broad=1.25,
             claws=True)
    mesh.spike((0.0, .53 * s, .91 * s), (0.0, .46 * s, 1.25 * s),
               .095 * s, 5, DETAIL, sides=16)
    return {"head": (0.0, .57, -1.18), "body": (0.0, .74, .10),
            "tail": (0.0, .53, .91), "snout": (0.0, .55, -1.47)}


def _arthropod(mesh: CreatureMesh, spec: CreatureSpec) -> dict[str, tuple[float, float, float]]:
    s = spec.scale
    crab = spec.family == "crab"
    body_y = .43 if crab else .50
    mesh.ellipsoid((0.0, body_y * s, .05 * s),
                   ((.72 if crab else .50) * s, .25 * s,
                    (.56 if crab else .67) * s), 1, BODY, rings=20, sides=38)
    mesh.ellipsoid((0.0, (body_y + .18) * s, .03 * s),
                   ((.65 if crab else .45) * s, .13 * s,
                    (.49 if crab else .58) * s), 1, DETAIL, rings=14, sides=30)
    if not crab:
        # A low, elongated cut jewel avoids the featureless bubble silhouette
        # while preserving the single enormous amethyst from the concept.
        mesh.faceted_ellipsoid((0.0, (body_y + .34) * s, .08 * s),
                               (.54 * s, .31 * s, .70 * s), 1, MAGIC,
                               rings=10, sides=18,
                               rotation=(-.045, 0.0, 0.0))
        _dorsal_plate_field(
            mesh, s, z_start=-.43, z_end=.49, crest_y=body_y + .66,
            half_width=.43, rows=6, columns=5, crown_drop=.12,
            end_drop=.05, plate_height=.026, material=MAGIC,
            accent_material=BODY)
        # Dark segmented prongs form the metal-like cradle around the gem.
        for row, z in enumerate(np.linspace(-.42, .43, 6)):
            for side in (-1.0, 1.0):
                mesh.faceted_ellipsoid(
                    (side * .40 * s, (body_y + .27 + .018 * (row % 2)) * s,
                     float(z) * s),
                    (.12 * s, .040 * s, .14 * s), 1, DETAIL,
                    rings=5, sides=9,
                    rotation=(0.0, side * .25, side * .22))
    else:
        _dorsal_plate_field(
            mesh, s, z_start=-.40, z_end=.43, crest_y=body_y + .34,
            half_width=.52, rows=7, columns=6, crown_drop=.11,
            end_drop=.035, plate_height=.030, material=DETAIL,
            accent_material=MAGIC)
        # Barnacle cups and low mangrove growths add a second scale of shell
        # detail instead of leaving the crab as one smooth oval.
        for index, (x, z) in enumerate((
                (-.34, -.27), (-.10, -.36), (.20, -.21), (.39, .02),
                (.15, .24), (-.20, .30), (-.43, .08), (.02, .02))):
            base_y = body_y + .35 - .05 * abs(x)
            mesh.tube([(x * s, base_y * s, z * s),
                       (x * s, (base_y + .07) * s, z * s)],
                      [.043 * s, .030 * s], 1, DETAIL, sides=11)
            mesh.faceted_ellipsoid(
                (x * s, (base_y + .075) * s, z * s),
                ((.050 + .006 * (index % 3)) * s, .025 * s,
                 (.050 + .005 * ((index + 1) % 3)) * s),
                1, MAGIC if index % 3 == 0 else DETAIL,
                rings=4, sides=8)
    leg_count = 4 if crab else 3
    joint_sets = ((7, 8, 9), (10, 11, 12), (13, 14, 15), (16, 17, 18))
    for side in (-1.0, 1.0):
        for index in range(leg_count):
            z = -.34 + index * (.68 / max(leg_count - 1, 1))
            upper, lower, paw = joint_sets[index]
            if side > 0:
                upper = {7: 10, 10: 7, 13: 16, 16: 13}[upper]
                lower += 3 if lower in (8, 14) else -3
                paw += 3 if paw in (9, 15) else -3
            hip = (side * (.43 if crab else .34) * s, body_y * s, z * s)
            knee = (side * (.82 + index * .05) * s, .28 * s, (z + .07) * s)
            foot = (side * (1.02 + index * .04) * s, .07 * s, (z - .12) * s)
            mesh.tube([hip, knee], [.085 * s, .055 * s], upper, BODY, sides=14)
            mesh.tube([knee, foot], [.055 * s, .025 * s], lower,
                      DETAIL if crab else BODY, sides=12)
            mesh.spike(foot, (foot[0] + side * .16 * s, foot[1], foot[2] - .08 * s),
                       .026 * s, paw, DETAIL, sides=9)
    eye_y = body_y + .30
    if "stalk_eyes" in spec.traits:
        for side in (-1.0, 1.0):
            _stalk_eye(mesh, s,
                       (side * .20, body_y + .15, -.43),
                       (side * .27, body_y + .42, -.58), size=.070)
    else:
        _eye_pair(mesh, s, (0.0, eye_y, -.58), .26, size=.055)
    if "giant_claws" in spec.traits:
        for side, joint in ((-1.0, 19), (1.0, 20)):
            wrist = (side * .85 * s, .42 * s, -.54 * s)
            mesh.tube([(side * .46 * s, .43 * s, -.39 * s), wrist],
                      [.12 * s, .09 * s], joint, BODY, sides=18)
            mesh.ellipsoid(wrist, (.28 * s, .17 * s, .27 * s), joint, DETAIL,
                           rings=13, sides=24)
            mesh.spike((wrist[0], wrist[1], (wrist[2] - .12 * s)),
                       (wrist[0] + side * .05 * s, wrist[1] + .08 * s,
                        wrist[2] - .43 * s), .09 * s, joint, DETAIL, sides=15)
            mesh.spike((wrist[0], wrist[1], (wrist[2] - .10 * s)),
                       (wrist[0] - side * .12 * s, wrist[1] - .06 * s,
                        wrist[2] - .37 * s), .075 * s, joint, DETAIL, sides=14)
    if "mandibles" in spec.traits:
        for side in (-1.0, 1.0):
            mesh.spike((side * .13 * s, .48 * s, -.62 * s),
                       (side * .31 * s, .34 * s, -.91 * s),
                       .055 * s, 4, DETAIL, sides=14)
    if "moss" in spec.traits:
        for index in range(15):
            angle = math.tau * index / 15.0
            mesh.spike((math.cos(angle) * .45 * s, (body_y + .29) * s,
                        math.sin(angle) * .35 * s),
                       (math.cos(angle) * .54 * s, (body_y + .45) * s,
                        math.sin(angle) * .43 * s), .025 * s, 1, MAGIC, sides=9)
    return {"head": (0.0, body_y + .12, -.46), "body": (0.0, body_y, .05),
            "tail": (0.0, body_y, .55), "snout": (0.0, body_y, -.70)}


def _amphibian(mesh: CreatureMesh, spec: CreatureSpec) -> dict[str, tuple[float, float, float]]:
    s = spec.scale
    mudskipper = spec.family == "mudskipper"
    body_y = .43
    mesh.ellipsoid((0.0, body_y * s, .10 * s),
                   ((.64 if mudskipper else .72) * s, .37 * s,
                    (.91 if mudskipper else .66) * s),
                   1, BODY, rings=23, sides=40)
    mesh.ellipsoid((0.0, .34 * s, -.10 * s),
                   ((.56 if mudskipper else .65) * s, .20 * s, .53 * s),
                   1, UNDER, rings=16, sides=32)
    head_z = -.63 if mudskipper else -.48
    mesh.ellipsoid((0.0, .55 * s, head_z * s),
                   ((.50 if mudskipper else .66) * s, .35 * s,
                    (.49 if mudskipper else .42) * s),
                   3, BODY, rings=20, sides=38)
    for side in (-1.0, 1.0):
        eye_x = side * (.30 if mudskipper else .35)
        _stalk_eye(mesh, s, (eye_x * .82, .68, head_z - .08),
                   (eye_x, .84, head_z - .15), size=.082)
    # Powerful folded rear legs and splayed toes define the silhouette.
    for side, joints in ((-1.0, (13, 14, 15)), (1.0, (16, 17, 18))):
        hip = (side * .45 * s, .45 * s, .43 * s)
        knee = (side * .78 * s, .22 * s, .64 * s)
        ankle = (side * .69 * s, .09 * s, .13 * s)
        mesh.tube([hip, knee], [.18 * s, .13 * s], joints[0], BODY, sides=20)
        mesh.tube([knee, ankle], [.13 * s, .07 * s], joints[1], BODY, sides=18)
        for toe in (-.13, 0.0, .13):
            mesh.spike(ankle, ((side * .86 + toe) * s, .04 * s, -.18 * s),
                       .032 * s, joints[2], DETAIL, sides=10)
    for side, joints in ((-1.0, (7, 8, 9)), (1.0, (10, 11, 12))):
        mesh.tube([(side * .37 * s, .39 * s, -.36 * s),
                   (side * .58 * s, .08 * s, -.55 * s)],
                  [.10 * s, .055 * s], joints[0], BODY, sides=16)
        for toe in (-.10, 0.0, .10):
            mesh.spike((side * .58 * s, .07 * s, -.55 * s),
                       ((side * .68 + toe) * s, .035 * s, -.76 * s),
                       .025 * s, joints[2], DETAIL, sides=9)
    if "warts" in spec.traits:
        for row, z in enumerate(np.linspace(-.32, .50, 7)):
            for side in (-1.0, -.45, 0.0, .45, 1.0):
                mesh.ellipsoid((side * .51 * (1.0 - abs(float(z)) * .30) * s,
                                (.72 + .05 * ((row + int(side * 2)) % 2)) * s,
                                float(z) * s),
                               (.055 * s, .035 * s, .055 * s), 1, DETAIL,
                               rings=6, sides=11)
    if "mushrooms" in spec.traits:
        for index, (x, z, height) in enumerate((
                (-.36, .14, .33), (-.19, .38, .18), (.02, .34, .27),
                (.26, .18, .20), (.35, -.12, .24), (-.26, -.16, .15),
                (.06, -.30, .16))):
            mesh.tube([(x * s, .68 * s, z * s), (x * s, (.68 + height) * s, z * s)],
                      [(.026 + .007 * (index % 3)) * s, .018 * s],
                      1, DETAIL, sides=11)
            mesh.ellipsoid((x * s, (.71 + height) * s, z * s),
                           ((.11 + .025 * (index % 3)) * s,
                            (.045 + .008 * (index % 2)) * s,
                            (.10 + .020 * ((index + 1) % 3)) * s), 1, MAGIC,
                           rings=9, sides=18)
    if "fins" in spec.traits:
        _body_fins(mesh, s, body_y + .12, count=4)
        _spine_row(mesh, s, -.10, .74, 7, .68, .24, material=MAGIC)
    if "whiskers" in spec.traits:
        _whiskers(mesh, s, .51, head_z - .40, count=4)
    return {"head": (0.0, .55, head_z), "body": (0.0, body_y, .10),
            "tail": (0.0, body_y, .74), "snout": (0.0, .49, head_z - .40)}


def _canopy_glider(mesh: CreatureMesh, spec: CreatureSpec) -> dict[str, tuple[float, float, float]]:
    """Leaf-feathered owl silhouette used by the Amberwood glider concept."""
    s = spec.scale
    mesh.ellipsoid((0.0, .87 * s, .04 * s), (.39 * s, .45 * s, .57 * s),
                   1, BODY, rings=24, sides=42, rotation=(-.12, 0.0, 0.0))
    mesh.ellipsoid((0.0, .81 * s, -.13 * s), (.31 * s, .34 * s, .40 * s),
                   1, UNDER, rings=18, sides=34)
    # Overlapping breast and mantle feathers break the spherical body into the
    # layered owl plumage shown in the Amberwood sheet.
    for row in range(5):
        count = 3 + row
        y = 1.04 - row * .115
        z = -.39 + row * .075
        for column, x in enumerate(np.linspace(-.27, .27, count)):
            mesh.faceted_ellipsoid(
                (float(x) * s, y * s, z * s),
                ((.105 - row * .006) * s, .040 * s,
                 (.16 + row * .008) * s), 1,
                UNDER if (row + column) % 3 else MAGIC,
                rings=5, sides=9,
                rotation=(-.20, float(x) * .25, float(x) * -.18))
    for row, z in enumerate(np.linspace(-.08, .45, 5)):
        for side in (-1.0, 0.0, 1.0):
            mesh.faceted_ellipsoid(
                (side * .24 * s, (1.16 - row * .065) * s, float(z) * s),
                (.13 * s, .038 * s, .18 * s), 1,
                MAGIC if (row + int(side)) % 4 == 0 else BODY,
                rings=5, sides=9,
                rotation=(0.0, side * .18, side * .14))
    mesh.ellipsoid((0.0, 1.22 * s, -.38 * s), (.40 * s, .37 * s, .34 * s),
                   3, BODY, rings=24, sides=42)
    # Layered facial disks and brows retain the owl identity at small sizes.
    for side in (-1.0, 1.0):
        mesh.ellipsoid((side * .18 * s, 1.21 * s, -.64 * s),
                       (.22 * s, .23 * s, .075 * s), 3, UNDER,
                       rings=16, sides=30, rotation=(0.0, side * .10, 0.0))
        mesh.ellipsoid((side * .18 * s, 1.24 * s, -.708 * s),
                       (.070 * s, .076 * s, .027 * s), 3, DARK,
                       rings=11, sides=21)
        mesh.ellipsoid((side * .18 * s, 1.24 * s, -.738 * s),
                       (.026 * s, .031 * s, .010 * s), 3, EYE,
                       rings=8, sides=15)
        mesh.spike((side * .10 * s, 1.40 * s, -.56 * s),
                   (side * .35 * s, 1.51 * s, -.49 * s),
                   .055 * s, 3, MAGIC, sides=13)
    mesh.spike((0.0, 1.16 * s, -.70 * s), (0.0, 1.01 * s, -.94 * s),
               .085 * s, 4, DETAIL, sides=16)

    for side, joint in ((-1.0, 19), (1.0, 20)):
        root = (side * .27 * s, 1.05 * s, -.02 * s)
        wrist = (side * 1.02 * s, 1.24 * s, .05 * s)
        tip = (side * 1.47 * s, 1.13 * s, .18 * s)
        mesh.tube([root, wrist, tip], [.10 * s, .055 * s, .012 * s],
                  joint, DETAIL, sides=18)
        mesh.membrane([root, wrist, tip,
                       (side * .54 * s, .76 * s, .45 * s)], joint, MEMBRANE)
        # Each primary feather is a tapered, overlapping leaf rather than a
        # single triangular wing plane.
        for index in range(9):
            t = index / 8.0
            feather_root = (side * (.34 + .52 * t) * s,
                            (1.05 - .11 * t) * s, (.03 + .12 * t) * s)
            feather_tip = (side * (1.26 + .30 * t) * s,
                           (.78 - .09 * t) * s, (.25 + .25 * t) * s)
            mesh.tube([feather_root, feather_tip],
                      [(.070 - .025 * t) * s, .004 * s], joint,
                      MAGIC if index % 3 == 0 else BODY, sides=12)
            mesh.ellipsoid(tuple(np.asarray(feather_root) * .38 + np.asarray(feather_tip) * .62),
                           ((.10 - .025 * t) * s, (.035 + .015 * t) * s,
                            (.35 - .08 * t) * s), joint,
                           MAGIC if index % 3 == 0 else BODY,
                           rings=10, sides=20,
                           rotation=(0.0, side * .22, side * -.12))
    for side, joints in ((-1.0, (13, 14, 15)), (1.0, (16, 17, 18))):
        mesh.tube([(side * .17 * s, .58 * s, .15 * s),
                   (side * .18 * s, .20 * s, -.02 * s)],
                  [.060 * s, .035 * s], joints[0], DETAIL, sides=14)
        for toe in (-.08, 0.0, .08):
            mesh.spike((side * .18 * s, .20 * s, -.02 * s),
                       ((side * .18 + toe) * s, .08 * s, -.27 * s),
                       .018 * s, joints[2], DETAIL, sides=9)
    for side in (-1.0, -.45, 0.0, .45, 1.0):
        mesh.spike((side * .20 * s, .76 * s, .42 * s),
                   (side * .38 * s, .56 * s, .97 * s),
                   .050 * s, 5, BODY if abs(side) < .8 else MAGIC, sides=12)
    return {"head": (0.0, 1.22, -.38), "body": (0.0, .87, .04),
            "tail": (0.0, .76, .42), "snout": (0.0, 1.10, -.78)}


def _upright_mudskipper(mesh: CreatureMesh, spec: CreatureSpec) -> dict[str, tuple[float, float, float]]:
    """Upright swamp amphibian matching the long-limbed concept silhouette."""
    s = spec.scale
    mesh.ellipsoid((0.0, .92 * s, .05 * s), (.39 * s, .62 * s, .34 * s),
                   1, BODY, rings=25, sides=42, rotation=(-.10, 0.0, 0.0))
    mesh.ellipsoid((0.0, .86 * s, -.22 * s), (.31 * s, .48 * s, .15 * s),
                   1, UNDER, rings=17, sides=32)
    mesh.tube([(0.0, 1.26 * s, -.10 * s), (0.0, 1.43 * s, -.28 * s)],
              [.27 * s, .30 * s], 2, BODY, sides=26)
    mesh.ellipsoid((0.0, 1.53 * s, -.38 * s), (.38 * s, .31 * s, .37 * s),
                   3, BODY, rings=22, sides=38)
    mesh.ellipsoid((0.0, 1.44 * s, -.72 * s), (.31 * s, .14 * s, .39 * s),
                   4, UNDER, rings=16, sides=30)
    for side in (-1.0, 1.0):
        _stalk_eye(mesh, s, (side * .20, 1.68, -.46),
                   (side * .24, 1.85, -.50), size=.073)
    for side, joints in ((-1.0, (7, 8, 9)), (1.0, (10, 11, 12))):
        shoulder = (side * .31 * s, 1.20 * s, -.07 * s)
        elbow = (side * .60 * s, .82 * s, -.22 * s)
        hand = (side * .47 * s, .45 * s, -.54 * s)
        mesh.tube([shoulder, elbow, hand], [.11 * s, .075 * s, .040 * s],
                  joints[0], BODY, sides=19)
        for finger in (-.07, 0.0, .07):
            mesh.spike(hand, ((side * .52 + finger) * s, .36 * s, -.76 * s),
                       .016 * s, joints[2], DETAIL, sides=9)
    for side, joints in ((-1.0, (13, 14, 15)), (1.0, (16, 17, 18))):
        hip = (side * .25 * s, .60 * s, .15 * s)
        knee = (side * .46 * s, .31 * s, .27 * s)
        ankle = (side * .32 * s, .10 * s, -.08 * s)
        mesh.ellipsoid(hip, (.18 * s, .24 * s, .20 * s), joints[0], BODY,
                       rings=14, sides=25)
        mesh.tube([hip, knee, ankle], [.13 * s, .085 * s, .050 * s],
                  joints[0], BODY, sides=20)
        for toe in (-.12, 0.0, .12):
            mesh.spike(ankle, ((side * .40 + toe) * s, .04 * s, -.38 * s),
                       .024 * s, joints[2], DETAIL, sides=10)
    _spine_row(mesh, s, -.05, .58, 8, 1.22, .24, material=MAGIC)
    _tail(mesh, s, (0.0, .72, .28), length=1.12, curl=.08, thick=.22)
    _whiskers(mesh, s, 1.43, -.98, count=4)
    return {"head": (0.0, 1.53, -.38), "body": (0.0, .92, .05),
            "tail": (0.0, .72, .28), "snout": (0.0, 1.44, -.90)}


def _floodmaw(mesh: CreatureMesh, spec: CreatureSpec) -> dict[str, tuple[float, float, float]]:
    s = spec.scale
    body_y = .62
    mesh.ellipsoid((0.0, body_y * s, .14 * s), (.82 * s, .50 * s, 1.20 * s),
                   1, BODY, rings=26, sides=46)
    mesh.ellipsoid((0.0, .39 * s, .02 * s), (.70 * s, .24 * s, 1.02 * s),
                   1, UNDER, rings=17, sides=34)
    # Three independently readable heads share a root mass but use separate rig zones.
    head_data = ((-1.0, -.92, 1.72, 19), (0.0, -1.32, 2.02, 3),
                 (1.0, -.92, 1.72, 20))
    for side, head_z, head_y, joint in head_data:
        neck_origin = (side * .27 * s, .78 * s, -.43 * s)
        head_center = (side * .72 * s, head_y * s, head_z * s)
        mesh.tube([neck_origin,
                   (side * .42 * s, 1.08 * s, (head_z + .40) * s),
                   (side * .62 * s, (head_y - .28) * s, (head_z + .17) * s),
                   head_center],
                  [.28 * s, .24 * s, .19 * s, .14 * s],
                  joint if side else 2, BODY, sides=28)
        mesh.ellipsoid(head_center, (.34 * s, .24 * s, .40 * s),
                       joint, BODY, rings=18, sides=32,
                       rotation=(0.0, side * .16, side * .05))
        snout = (side * .76 * s, (head_y - .10) * s, (head_z - .37) * s)
        mesh.ellipsoid(snout, (.28 * s, .12 * s, .37 * s), joint, UNDER,
                       rings=15, sides=28, rotation=(0.0, side * .16, 0.0))
        for eye_side in (-1.0, 1.0):
            eye_x = side * .70 + eye_side * .20
            mesh.ellipsoid((eye_x * s, (head_y + .13) * s, (head_z - .16) * s),
                           (.052 * s, .045 * s, .029 * s), joint, DARK,
                           rings=8, sides=15)
            mesh.ellipsoid((eye_x * s, (head_y + .133) * s,
                            (head_z - .186) * s),
                           (.017 * s, .018 * s, .008 * s), joint, EYE,
                           rings=6, sides=11)
        for crown_index, crown_z in enumerate(np.linspace(head_z - .24,
                                                           head_z + .18, 4)):
            mesh.faceted_ellipsoid(
                (side * .72 * s,
                 (head_y + .205 + .018 * (crown_index % 2)) * s,
                 float(crown_z) * s),
                (.17 * s, .035 * s, .11 * s), joint,
                MAGIC if crown_index == 1 else DETAIL,
                rings=5, sides=9,
                rotation=(0.0, side * .17, side * .12))
        for tooth in range(7):
            z = head_z - .70 + tooth * .095
            for lateral in (-1.0, 1.0):
                mesh.spike(((side * .74 + lateral * .20) * s,
                            (head_y - .12) * s, z * s),
                           ((side * .74 + lateral * .20) * s,
                            (head_y - .25) * s,
                            (z - .015) * s), .024 * s, joint, BONE, sides=10)
    # Mangrove-root legs brace the enormous body; fins and luminous dorsal growths
    # keep the aquatic concept readable even when viewed from above.
    for side, joints, z in (
        (-1.0, (7, 8, 9), -.38), (1.0, (10, 11, 12), -.38),
        (-1.0, (13, 14, 15), .55), (1.0, (16, 17, 18), .55),
    ):
        hip = (side * .58 * s, .56 * s, z * s)
        knee = (side * .92 * s, .24 * s, (z + .10) * s)
        foot = (side * 1.03 * s, .07 * s, (z - .18) * s)
        mesh.tube([hip, knee, foot], [.16 * s, .11 * s, .055 * s],
                  joints[0], BODY, sides=20)
        for root in (-.12, 0.0, .12):
            mesh.spike(foot, ((side * 1.20 + root) * s, .02 * s,
                              (z - .34 - abs(root) * .4) * s),
                       .045 * s, joints[2], DETAIL, sides=11)
    _dorsal_plate_field(
        mesh, s, z_start=-.42, z_end=.92, crest_y=1.105,
        half_width=.63, rows=10, columns=6, crown_drop=.24,
        end_drop=.055, plate_height=.035, material=DETAIL,
        accent_material=MAGIC)
    for index, z in enumerate(np.linspace(-.43, .82, 10)):
        height = .30 + .13 * math.sin(index * 1.8)
        mesh.spike((0.0, .86 * s, float(z) * s),
                   ((.10 * math.sin(index * 2.1)) * s, (1.0 + height) * s,
                    (float(z) + .10) * s), .055 * s, 1,
                   MAGIC if index % 2 else DETAIL, sides=13)
    _body_fins(mesh, s, body_y + .08, count=7)
    _tail(mesh, s, (0.0, body_y, 1.10), length=1.58, curl=.18, thick=.28,
          material=BODY)
    for side in (-1.0, 1.0):
        for index in range(5):
            z = -.42 + index * .35
            mesh.tube([(side * .50 * s, .70 * s, z * s),
                       (side * (.78 + index * .04) * s, (1.04 + index * .04) * s,
                        (z + .12) * s)],
                      [.045 * s, .014 * s], 1, DETAIL, sides=11)
    return {"head": (0.0, 2.02, -1.32), "body": (0.0, body_y, .14),
            "tail": (0.0, body_y, 1.10), "snout": (0.0, 1.92, -1.69)}


def _build_geometry(spec: CreatureSpec) -> CreatureMesh:
    mesh = CreatureMesh()
    if spec.family == "turtle":
        _turtle(mesh, spec)
        return mesh
    if spec.family == "hare":
        _snowcrest_hare(mesh, spec)
        return mesh
    if spec.family in {"mite", "crab"}:
        _arthropod(mesh, spec)
        return mesh
    if spec.family == "toad":
        _amphibian(mesh, spec)
        return mesh
    if spec.family == "mudskipper":
        _upright_mudskipper(mesh, spec)
        return mesh
    if spec.family == "glider":
        _canopy_glider(mesh, spec)
        return mesh
    if spec.family == "floodmaw":
        _floodmaw(mesh, spec)
        return mesh
    if spec.family in {"cat", "stalker"}:
        _feline(mesh, spec)
        return mesh
    if spec.slug == "lakeglass_drake":
        _upright_drake(mesh, spec)
        return mesh
    if spec.family in {"drake", "wyrm"}:
        _quadruped_drake(mesh, spec)
        return mesh
    if spec.family in {"basilisk", "crocodile", "grazer"}:
        _reptile(mesh, spec)
        return mesh

    dimensions = {
        "otter": ((.35, .24, .71), (.24, .21, .31), (.18, .12, .27), .43, .25, True, .90),
        "stag": ((.30, .25, .84), (.20, .22, .30), (.125, .095, .27), .75, .23, False, .75),
        "hare": ((.27, .27, .52), (.20, .22, .25), (.12, .09, .18), .54, .21, False, .82),
        "ram": ((.40, .34, .75), (.26, .25, .31), (.17, .13, .24), .70, .28, False, .88),
        "bear": ((.57, .43, .80), (.34, .31, .37), (.25, .18, .28), .60, .36, False, 1.13),
        "cat": ((.30, .23, .82), (.21, .20, .28), (.14, .10, .24), .70, .23, False, .78),
        "hound": ((.33, .25, .82), (.22, .21, .30), (.15, .10, .27), .70, .24, False, .80),
        "fox": ((.29, .22, .76), (.21, .20, .27), (.13, .10, .23), .66, .23, False, .76),
        "aurochs": ((.59, .46, 1.00), (.36, .32, .42), (.25, .18, .34), .55, .38, True, 1.00),
        "boar": ((.54, .38, .78), (.34, .29, .36), (.25, .18, .32), .52, .34, True, 1.06),
        "quillbeast": ((.50, .36, .75), (.31, .27, .34), (.22, .16, .29), .52, .33, True, 1.02),
        "stalker": ((.30, .23, .86), (.21, .20, .29), (.14, .10, .24), .70, .23, False, .78),
    }
    body, head, snout, leg, stance, low, paws = dimensions[spec.family]
    landmarks = _quadruped(mesh, spec, body=body, head=head, snout=snout,
                           leg=leg, stance=stance, low=low, broad_paws=paws)
    _quadruped_features(mesh, spec, landmarks)
    _quadruped_extras(mesh, spec, landmarks)
    return mesh


def _quat(axis: str, angle: float) -> list[float]:
    half = angle * .5
    values = {
        "x": [math.sin(half), 0.0, 0.0, math.cos(half)],
        "y": [0.0, math.sin(half), 0.0, math.cos(half)],
        "z": [0.0, 0.0, math.sin(half), math.cos(half)],
    }
    return values[axis]


def _add_animation(glb: ProductionGLB, name: str,
                   channels: dict[int, tuple[str, list[float], list[list[float]]]]) -> None:
    animation = {"name": name, "samplers": [], "channels": []}
    for node, (path, times, values) in channels.items():
        input_accessor = glb.accessor(np.asarray(times, dtype="float32"), "SCALAR",
                                      bounds=True)
        output_accessor = glb.accessor(np.asarray(values, dtype="float32"),
                                       "VEC4" if path == "rotation" else "VEC3")
        animation["samplers"].append({
            "input": input_accessor,
            "output": output_accessor,
            "interpolation": "LINEAR",
        })
        animation["channels"].append({
            "sampler": len(animation["samplers"]) - 1,
            "target": {"node": node, "path": path},
        })
    glb.doc.setdefault("animations", []).append(animation)


def _author_animations(glb: ProductionGLB, spec: CreatureSpec) -> None:
    pace = .82 if spec.family in {"crab", "mite", "turtle"} else 1.0
    idle_channels = {
        1: ("rotation", [0.0, 1.2, 2.4],
            [_quat("z", -.022), _quat("z", .022), _quat("z", -.022)]),
        2: ("rotation", [0.0, 1.2, 2.4],
            [_quat("x", -.025), _quat("x", .035), _quat("x", -.025)]),
        5: ("rotation", [0.0, 1.2, 2.4],
            [_quat("y", -.12), _quat("y", .12), _quat("y", -.12)]),
    }
    if "wings" in spec.traits or spec.family == "glider":
        idle_channels[19] = ("rotation", [0.0, .6, 1.2],
                             [_quat("z", -.05), _quat("z", -.16), _quat("z", -.05)])
        idle_channels[20] = ("rotation", [0.0, .6, 1.2],
                             [_quat("z", .05), _quat("z", .16), _quat("z", .05)])
    _add_animation(glb, "Idle_A", idle_channels)
    walk_angle = .48 * pace
    _add_animation(glb, "Walk", {
        7: ("rotation", [0.0, .5, 1.0], [_quat("x", walk_angle), _quat("x", -walk_angle), _quat("x", walk_angle)]),
        10: ("rotation", [0.0, .5, 1.0], [_quat("x", -walk_angle), _quat("x", walk_angle), _quat("x", -walk_angle)]),
        13: ("rotation", [0.0, .5, 1.0], [_quat("x", -walk_angle), _quat("x", walk_angle), _quat("x", -walk_angle)]),
        16: ("rotation", [0.0, .5, 1.0], [_quat("x", walk_angle), _quat("x", -walk_angle), _quat("x", walk_angle)]),
        1: ("translation", [0.0, .5, 1.0], [[0.0, .78, 0.0], [0.0, .82, 0.0], [0.0, .78, 0.0]]),
    })
    run_angle = .78 * pace
    _add_animation(glb, "Jog", {
        7: ("rotation", [0.0, .34, .68], [_quat("x", run_angle), _quat("x", -run_angle), _quat("x", run_angle)]),
        10: ("rotation", [0.0, .34, .68], [_quat("x", -run_angle), _quat("x", run_angle), _quat("x", -run_angle)]),
        13: ("rotation", [0.0, .34, .68], [_quat("x", -run_angle), _quat("x", run_angle), _quat("x", -run_angle)]),
        16: ("rotation", [0.0, .34, .68], [_quat("x", run_angle), _quat("x", -run_angle), _quat("x", run_angle)]),
        1: ("translation", [0.0, .34, .68], [[0.0, .78, 0.0], [0.0, .86, 0.0], [0.0, .78, 0.0]]),
    })
    _add_animation(glb, "Fighting_Idle", {
        2: ("rotation", [0.0, .65, 1.3], [_quat("x", -.10), _quat("x", .08), _quat("x", -.10)]),
        4: ("rotation", [0.0, .65, 1.3], [_quat("x", 0.0), _quat("x", .12), _quat("x", 0.0)]),
    })
    _add_animation(glb, "Sword_Attack", {
        2: ("rotation", [0.0, .24, .62], [_quat("x", -.20), _quat("x", .58), _quat("x", -.20)]),
        4: ("rotation", [0.0, .24, .62], [_quat("x", 0.0), _quat("x", .48), _quat("x", 0.0)]),
        19: ("rotation", [0.0, .24, .62], [_quat("z", 0.0), _quat("z", -.36), _quat("z", 0.0)]),
        20: ("rotation", [0.0, .24, .62], [_quat("z", 0.0), _quat("z", .36), _quat("z", 0.0)]),
    })
    _add_animation(glb, "Hit_Chest", {
        1: ("rotation", [0.0, .18, .46], [_quat("z", 0.0), _quat("z", .27), _quat("z", 0.0)]),
        2: ("rotation", [0.0, .18, .46], [_quat("x", 0.0), _quat("x", -.20), _quat("x", 0.0)]),
    })
    _add_animation(glb, "Death_A", {
        0: ("rotation", [0.0, .68, 1.32], [_quat("z", 0.0), _quat("z", .95), _quat("z", 1.48)]),
        2: ("rotation", [0.0, .68, 1.32], [_quat("x", 0.0), _quat("x", -.34), _quat("x", -.34)]),
    })


def build_invasion_creature(path: Path, spec: CreatureSpec) -> dict:
    """Build one self-contained, skinned, textured production creature GLB."""
    glb = ProductionGLB()
    globals_ = _global_bone_positions()
    children = {index: [] for index in range(len(CREATURE_BONES))}
    for index, (_, parent, _) in enumerate(CREATURE_BONES):
        if parent >= 0:
            children[parent].append(index)
    for index, (name, _parent, translation) in enumerate(CREATURE_BONES):
        node = {"name": name, "translation": list(translation)}
        if children[index]:
            node["children"] = children[index].copy()
        glb.doc["nodes"].append(node)
    glb.doc["scenes"][0]["nodes"] = [0]

    inverse = []
    for position in globals_:
        matrix = np.eye(4, dtype="float32")
        matrix[:3, 3] = -position
        inverse.append(matrix.T.reshape(-1))
    inverse_accessor = glb.accessor(np.asarray(inverse, dtype="float32"), "MAT4")
    glb.doc["skins"] = [{
        "name": f"{spec.label} Production Rig",
        "joints": list(range(len(CREATURE_BONES))),
        "skeleton": 0,
        "inverseBindMatrices": inverse_accessor,
    }]

    base_png, normal_png, orm_png, emissive_png = _texture_set(spec)
    magical = any(trait in spec.traits for trait in (
        "glass_spines", "ice_crystals", "crystal_carapace", "crystal_mane",
        "crystal_tail", "crystal_horns", "crystal_spines", "spectral_mane",
        "wisp_tail", "wisp_glow", "mirror_scales"))
    under_alt = tuple(int((a * .68 + b * .32)) for a, b in zip(spec.secondary, spec.base))
    detail_base = tuple(max(24, int(value * .42)) for value in spec.secondary)
    detail_alt = tuple(max(28, int(value * .36)) for value in spec.accent)
    accent_alt = tuple(int(a * .72 + b * .28)
                       for a, b in zip(spec.accent, spec.secondary))
    under_base, under_normal, under_orm, _under_glow = _surface_texture_set(
        spec, "underbody", spec.secondary, under_alt)
    detail_base_png, detail_normal, detail_orm, _detail_glow = _surface_texture_set(
        spec, "detail", detail_base, detail_alt)
    accent_base, accent_normal, accent_orm, accent_glow = _surface_texture_set(
        spec, "accent", spec.accent, accent_alt,
        size=384, crystalline=(spec.pattern == "crystal" or magical),
        emissive=magical)
    materials = [
        glb.material(f"{spec.label} Body PBR", (255, 255, 255),
                     roughness=.70, base_png=base_png, normal_png=normal_png,
                     orm_png=orm_png, emissive_png=emissive_png,
                     emissive=(tuple(max(1, value // 72) for value in spec.accent)
                               if magical else (0, 0, 0))),
        glb.material(f"{spec.label} Underbody PBR", (255, 255, 255),
                     roughness=.84, base_png=under_base,
                     normal_png=under_normal, orm_png=under_orm),
        glb.material(f"{spec.label} Horn Claw Detail PBR", (255, 255, 255),
                     metallic=.02, roughness=.68, base_png=detail_base_png,
                     normal_png=detail_normal, orm_png=detail_orm),
        glb.material(f"{spec.label} Concept Accent PBR", (255, 255, 255),
                     metallic=.10 if spec.pattern == "crystal" else .01,
                     roughness=.48,
                     base_png=accent_base, normal_png=accent_normal,
                     orm_png=accent_orm,
                     emissive_png=accent_glow if magical else None,
                     emissive=(tuple(max(1, value // 36) for value in spec.accent)
                               if magical else (0, 0, 0))),
        glb.material(f"{spec.label} Eyes",
                     tuple(max(18, int(value * .58)) for value in spec.eye),
                     roughness=.16,
                     emissive=(tuple(max(1, value // 96) for value in spec.eye)
                               if magical else (0, 0, 0))),
        glb.material(f"{spec.label} Fins and Membranes", spec.accent,
                     roughness=.52,
                     emissive=(tuple(max(1, value // 54) for value in spec.accent)
                               if magical else (0, 0, 0)),
                     double_sided=True, alpha=.78),
        glb.material(f"{spec.label} Pupils", (8, 12, 15), roughness=.24),
        glb.material(f"{spec.label} Teeth and Bone", (151, 148, 132),
                     metallic=.0, roughness=.72),
    ]

    primitives = []
    vertices = triangles = 0
    arrays_by_material = _build_geometry(spec).arrays()
    for material_index, arrays in enumerate(arrays_by_material):
        if not len(arrays[0]):
            continue
        primitives.append(glb.primitive(
            arrays[0], arrays[1], arrays[2], arrays[3], materials[material_index],
            arrays[4], arrays[5]))
        vertices += len(arrays[0])
        triangles += len(arrays[3]) // 3
    glb.doc["meshes"].append({"name": f"{spec.label} NativeModel", "primitives": primitives})
    mesh_node = len(glb.doc["nodes"])
    glb.doc["nodes"].append({
        "name": f"{spec.label} NativeModel",
        "mesh": 0,
        "skin": 0,
    })
    glb.doc["nodes"][0].setdefault("children", []).append(mesh_node)
    _author_animations(glb, spec)
    glb.write(path)
    return {
        "actor_type": spec.actor_type,
        "id": spec.slug,
        "name": spec.label,
        "family": spec.family,
        "region": spec.region,
        "conceptSheet": spec.concept_sheet,
        "conceptSlot": list(spec.concept_slot),
        "qualityTier": "production",
        "vertices": vertices,
        "triangles": triangles,
        "materials": len(materials),
        "embeddedTextures": len(glb.doc.get("images", [])),
        "joints": len(CREATURE_BONES),
        "animations": 7,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    repo_root = Path(__file__).resolve().parents[2]
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root / "godot-client/assets/actors/native/creatures",
    )
    parser.add_argument("--only", choices=[spec.slug for spec in INVASION_CREATURES])
    args = parser.parse_args()
    selected = [spec for spec in INVASION_CREATURES if not args.only or spec.slug == args.only]
    for spec in selected:
        result = build_invasion_creature(args.output / f"{spec.slug}.glb", spec)
        print(spec.slug, json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

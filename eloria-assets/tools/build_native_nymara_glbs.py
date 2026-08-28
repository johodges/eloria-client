#!/usr/bin/env python3
"""Build the Godot-native Nymara actor library from clean glTF 2.0 sources.

This pipeline deliberately does not consume the legacy Cal3D humanoid or creature
generators.  Playable races retain the proven Quaternius 65-joint skin, topology,
weights, and animation bone names.  Creature meshes, rigs, and clips are authored
here from scratch.

Modified 2026-08-28 for Eloria Client: equipment is no longer a set of primitive
blobs bolted to a bone with an identity transform.  ``equipment_authoring``
lofts wearables around the measured body silhouette and skins them to the shared
rig, and authors props against a character-space socket solved from the rig
itself, so items attach at body scale and follow every animation clip.
"""
from __future__ import annotations

import argparse
import copy
from functools import lru_cache
import io
import json
import math
from pathlib import Path
import struct
import numpy as np

import creature_anatomy as anatomy
import creature_families as families
import creature_roster as roster
import creature_surfaces as surfaces
from PIL import Image

import equipment_authoring


COMPONENT_DTYPES = {5121: "<u1", 5122: "<i2", 5123: "<u2", 5125: "<u4", 5126: "<f4"}
COMPONENT_TYPES = {np.dtype("uint8"): 5121, np.dtype("int16"): 5122,
                   np.dtype("uint16"): 5123, np.dtype("uint32"): 5125,
                   np.dtype("float32"): 5126}
TYPE_WIDTHS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}

RACES = {
    "luminous": {"label": "Luminous", "color": (196, 139, 103),
                  "accent": (48, 151, 164),
                  "feature": "none", "preserve_body": True,
                  "wardrobe": ((42, 126, 142), (42, 55, 72), (78, 55, 39),
                                (221, 190, 101))},
    "votary": {"label": "Whitehorn Votary", "color": (161, 145, 108),
                "feature_color": (205, 216, 213), "accent": (226, 231, 228),
                "feature": "horns",
                "wardrobe": ((113, 145, 164), (76, 94, 108), (79, 91, 99),
                              (218, 232, 235))},
    "glasswarden": {"label": "Glasswarden", "color": (168, 121, 91),
                     "feature_color": (38, 29, 62), "accent": (45, 128, 164),
                     "feature": "crystal",
                     "body_pattern": "none",
                     "wardrobe": ((54, 48, 84), (42, 44, 62), (83, 57, 39),
                                   (187, 145, 63))},
    "orun": {"label": "Orun", "color": (184, 139, 105),
             "accent": (219, 166, 72), "feature": "none",
             "wardrobe": ((146, 76, 39), (85, 64, 48), (82, 54, 35),
                           (49, 142, 145))},
    "greyhaven": {"label": "Greyhaven", "color": (153, 111, 89),
                   "accent": (154, 174, 171), "feature": "none",
                   "wardrobe": ((225, 220, 202), (41, 59, 75), (65, 49, 39),
                                 (171, 137, 70))},
    "ssarathi": {"label": "Ssarathi", "color": (91, 153, 126),
                  "feature_color": (32, 91, 68), "accent": (157, 122, 50),
                  "feature": "scaled",
                  "wardrobe": ((43, 112, 86), (34, 76, 62), (71, 63, 42),
                                (189, 153, 67))},
    "stoneborn": {"label": "Stoneborn", "color": (118, 105, 91),
                   "feature_color": (61, 59, 56), "accent": (50, 122, 133),
                   "feature": "stone",
                   "wardrobe": ((91, 86, 80), (65, 67, 68), (62, 55, 48),
                                 (84, 189, 199))},
    "mycelari": {"label": "Mycelari", "color": (116, 137, 91),
                  "feature_color": (82, 56, 35), "accent": (154, 92, 48),
                  "feature": "fungal",
                  "wardrobe": ((88, 112, 70), (62, 75, 53), (71, 54, 39),
                                (207, 143, 89))},
}

# --- race anatomy ---------------------------------------------------------
#
# Every playable race shares the one 65-joint Quaternius rig so the universal
# animation library keeps working, but sharing a rig does not have to mean
# sharing a body.  The previous pass scaled the source mesh with three hard
# width bands keyed off absolute height (hips below 48%, shoulders to 78%,
# head above).  That produced a visible pinch at the waist and the neck, it
# stretched arms lengthwise instead of thickening them -- the bands multiply
# X, and an A-posed arm is almost entirely X -- and it left all eight races
# the same human silhouette with a small prop glued on.
#
# This pass retargets the rest pose instead.  Segment lengths and rest
# rotations move the joints, and the mesh follows through linear blend
# skinning with T = B . G . A^-1, where A is the source bind pose, B the
# retargeted bind pose, and G a girth scale expressed perpendicular to the
# bone.  Deformation is therefore smooth by construction (it is blended by
# the same skin weights the renderer uses), anatomically meaningful (a bone
# gets longer or thicker rather than a slab of world space getting wider),
# and it costs no extra vertices.
#
# Two invariants keep the shared animation library usable:
#
#   * hip-to-ground distance is preserved.  The clips write pelvis
#     translation directly, so a longer leg cannot raise the hips -- it would
#     push the feet through the floor.  After retargeting, the leg chain is
#     rescaled by a single solved factor that restores the original ground
#     contact height.  Races still differ in how the leg is *divided*, which
#     is what makes a digitigrade stance possible at all.
#   * overall stature rides on the model registry's import scale rather than
#     on the rig, so a taller race is uniformly taller instead of having its
#     hips detached from its feet.
#
# The rest of the runtime contract is untouched: 65 joints, the same joint
# names and order, one skin, and rest transforms that stay rigid so the
# clips' rotation tracks still mean what they meant before.

CHAIN_CHILD = {"root": "pelvis", "pelvis": "spine_01",
               "hand_l": "middle_01_l", "hand_r": "middle_01_r"}
GROUND_JOINTS = ("ball_leaf_l", "ball_leaf_r")
LEG_GROUPS = ("thigh", "calf", "foot", "ball")


def joint_group(name: str) -> str:
    """Coarse anatomical group for a rig joint, used to key the race specs."""
    if name == "root":
        return "root"
    if name == "pelvis":
        return "pelvis"
    if name == "Head":
        return "head"
    for prefix in ("spine", "neck", "clavicle", "upperarm", "lowerarm",
                   "hand", "thigh", "calf", "foot", "ball"):
        if name.startswith(prefix):
            return prefix
    return "finger"


# stature   uniform import scale for the whole actor (registry, not the rig)
# segment   multiplies the bone that *leaves* this group, i.e. the local
#           offsets of its children -- "thigh": 1.1 lengthens the femur
# girth     thickness perpendicular to the bone
# swell     uniform scale about the joint, for the skull and hands
# stance    rotation of the joint's offset from its parent, in world bind
#           axes (degrees), authored for the right side and mirrored to the
#           left -- this is anatomy the animation clips cannot overwrite
ANATOMY = {
    # Reference proportions.  The Luminous are the baseline every other race
    # is described against, so their body is left exactly as authored.
    "luminous": {},
    # Whitehorn highlanders: tall, long-limbed and lean, with the heavy neck
    # and loaded calves of people who walk mountains carrying horns.
    "votary": {
        "stature": 1.045,
        "segment": {"calf": 1.05, "thigh": 1.03, "neck": 1.10, "spine": 1.02},
        "girth": {"upperarm": .94, "lowerarm": .93, "spine": .97,
                  "neck": 1.16, "calf": 1.12, "thigh": 1.03},
    },
    # Glasswarden field engineers and scholars: shorter, lighter through the
    # shoulders and arms, with the head carried slightly forward.
    "glasswarden": {
        "stature": .975,
        "segment": {"clavicle": .95, "thigh": .99},
        "girth": {"upperarm": .90, "lowerarm": .91, "spine": .95,
                  "thigh": .95, "calf": .93},
        "stance": {"neck_01": (7., 0., 0.), "Head": (-4., 0., 0.)},
    },
    # Orun riders: deep chest, heavy thighs, and the bowed, externally
    # rotated legs of a culture that grows up in the saddle.
    "orun": {
        "stature": 1.01,
        "segment": {"spine": .97, "thigh": 1.02, "clavicle": 1.04},
        "girth": {"spine": 1.09, "thigh": 1.14, "calf": 1.04,
                  "upperarm": 1.06, "lowerarm": 1.02},
        # Knees carried outward and ankles tucked back under: a rider's legs.
        "stance": {"calf_r": (0., 0., -7.), "foot_r": (0., 0., 10.)},
    },
    # Greyhaven coast: stocky and heavy-boned, broad through the shoulders
    # and forearms, shorter in the leg than the arm.
    "greyhaven": {
        "stature": .99,
        "segment": {"clavicle": 1.10, "thigh": .96, "calf": .96,
                    "lowerarm": 1.04, "neck": .94},
        "girth": {"spine": 1.12, "upperarm": 1.10, "lowerarm": 1.14,
                  "hand": 1.08, "thigh": 1.08, "calf": 1.08, "neck": 1.10},
        "stance": {"upperarm_r": (0., 0., -5.)},
    },
    # Ssarathi are reptilian, not humans in scale paint.  The leg is
    # digitigrade: the femur swings forward, the shin back, and the body
    # stands on a long metatarsal with the heel clear of the ground.  Total
    # hip height is unchanged, so the shared walk cycle still plants.  The
    # neck is longer and carried forward, counterweighted by the tail.
    "ssarathi": {
        "stature": 1.02,
        "segment": {"thigh": .86, "calf": 1.12, "foot": 1.55, "ball": 1.30,
                    "neck": 1.32, "spine": .97, "lowerarm": 1.10,
                    "hand": 1.12, "finger": 1.15},
        "girth": {"spine": .93, "upperarm": .88, "lowerarm": .86,
                  "thigh": 1.02, "calf": .88, "foot": .82, "neck": .90},
        "swell": {"hand": .96},
        # Solved so the ankle sits 0.23 m clear of the ground with the ball
        # and toe planted: femur forward, shin near vertical, a long
        # metatarsal dropping steeply, and flat toes.
        "stance": {"calf_r": (-29., 0., 0.), "foot_r": (6., 0., 0.),
                   "ball_r": (45., 0., 0.), "ball_leaf_r": (5., 0., 0.),
                   "neck_01": (18., 0., 0.), "Head": (-14., 0., 0.)},
    },
    # Stoneborn carry mineral mass.  Everything is thicker, and the neck is
    # short and sunk between raised shoulders; the stance is wide because the
    # thighs cannot pass each other.
    "stoneborn": {
        "stature": 1.06,
        "segment": {"neck": .72, "clavicle": 1.14, "spine": 1.02,
                    "thigh": .95, "calf": .93, "upperarm": 1.02},
        "girth": {"spine": 1.24, "neck": 1.45, "clavicle": 1.30,
                  "upperarm": 1.30, "lowerarm": 1.26, "hand": 1.18,
                  "thigh": 1.26, "calf": 1.24, "foot": 1.14},
        "swell": {"head": 1.06},
        "stance": {"calf_r": (0., 0., -8.), "foot_r": (0., 0., 5.),
                   "upperarm_r": (0., 0., -12.), "neck_01": (5., 0., 0.),
                   "Head": (-4., 0., 0.)},
    },
    # Mycelari grow rather than build muscle: a long thin stipe of a body,
    # narrow shoulders, light limbs, and a small skull under a heavy cap.
    "mycelari": {
        "stature": .995,
        "segment": {"thigh": 1.08, "calf": 1.10, "spine": .95,
                    "clavicle": .90, "neck": 1.14, "lowerarm": 1.05},
        "girth": {"spine": .86, "upperarm": .76, "lowerarm": .74,
                  "hand": .88, "thigh": .82, "calf": .78, "neck": .84,
                  "clavicle": .86},
        "swell": {"head": .93},
        "stance": {"neck_01": (5., 0., 0.), "Head": (-5., 0., 0.)},
    },
}

PLAYER_ACTOR_TYPES = {
    0: "luminous_female", 1: "luminous_male",
    2: "votary_female", 3: "votary_male", 4: "glasswarden_female", 5: "glasswarden_male",
    37: "orun_female", 38: "orun_male", 39: "greyhaven_female", 40: "greyhaven_male",
    41: "ssarathi_female", 42: "ssarathi_male", 79: "stoneborn_female", 80: "stoneborn_male",
    81: "mycelari_female", 82: "mycelari_male",
}

CREATURES = (
    # Tuple IDs retain the authored sequence; add the four existing upstream
    # creature slots when registering against eloria-server.  Palettes for the
    # creatures that appear in the concept art are sampled from it by
    # eloria-assets/tools/extract_concept_palettes.py; the rest, which were
    # invented for this roster, keep their authored colours.
    (200, "emberfox", "Emberfox", "fox", (205, 123, 10), (143, 84, 25), .82),
    (201, "mossback_boar", "Mossback Boar", "boar", (111, 63, 29), (224, 154, 91), 1.18),
    (202, "ridgehorn", "Ridgehorn", "ram", (132, 112, 77), (214, 174, 91), 1.05),
    (203, "miretoad", "Miretoad", "toad", (137, 82, 18), (224, 185, 109), 1.15),
    (204, "ash_crawler", "Ash Crawler", "lizard", (67, 62, 66), (172, 63, 54), 1.30),
    (205, "frost_maw", "Frost Maw", "wolf", (105, 153, 205), (38, 89, 196), 1.18),
    (206, "bog_lurker", "Bog Lurker", "toad", (48, 83, 65), (111, 151, 83), 1.42),
    (207, "sunscale_drake", "Sunscale Drake", "drake", (184, 117, 42), (57, 145, 141), 1.35),
    (208, "red_fox", "Red Fox", "fox", (185, 75, 19), (224, 165, 116), .74),
    (209, "snow_hare", "Snow Hare", "hare", (148, 152, 165), (55, 79, 151), .62),
    (210, "mountain_goat", "Mountain Goat", "ram", (134, 150, 181), (73, 74, 109), .92),
    (211, "black_bear", "Black Bear", "bear", (43, 39, 38), (100, 88, 68), 1.28),
    (212, "elk", "Elk", "elk", (150, 70, 26), (224, 164, 110), 1.08),
    (213, "wild_boar", "Wild Boar", "boar", (88, 73, 59), (151, 116, 72), 1.04),
    (214, "dire_wolf", "Dire Wolf", "wolf", (70, 80, 89), (132, 155, 166), 1.13),
    (215, "frost_tiger", "Frost Tiger", "cat", (94, 148, 205), (32, 74, 158), 1.14),
    (216, "giant_crocodile", "Giant Crocodile", "crocodile", (97, 88, 47), (224, 202, 159), 1.55),
    (217, "fire_salamander", "Fire Salamander", "lizard", (184, 69, 33), (245, 153, 48), 1.02),
    (218, "thunder_ram", "Thunder Ram", "ram", (102, 99, 94), (91, 160, 188), 1.24),
    (219, "giant_rat", "Giant Rat", "rat", (105, 85, 70), (179, 138, 92), .84),
    (220, "raccoon", "Raccoon", "fox", (93, 94, 90), (45, 48, 54), .72),
    (221, "river_otter", "River Otter", "otter", (94, 70, 47), (51, 111, 120), .75),
    (222, "porcupine", "Porcupine", "porcupine", (107, 82, 55), (48, 44, 38), .82),
    (223, "moose", "Moose", "elk", (91, 70, 48), (171, 133, 77), 1.28),
    (224, "lynx", "Lynx", "cat", (157, 126, 88), (71, 65, 61), .82),
    (225, "desert_tortoise", "Desert Tortoise", "tortoise", (172, 112, 48), (224, 182, 110), 1.06),
    (226, "saber_tooth_cat", "Saber-Tooth Cat", "saber_cat", (176, 137, 82), (235, 220, 173), 1.20),
    (227, "armored_rhino", "Armored Rhino", "rhino", (104, 105, 99), (62, 118, 128), 1.48),
    (228, "giant_komodo", "Giant Komodo", "lizard", (96, 82, 50), (224, 193, 112), 1.42),
    (229, "ice_bear", "Ice Bear", "bear", (122, 155, 188), (56, 97, 171), 1.48),
    (230, "lava_hound", "Lava Hound", "wolf", (154, 55, 30), (246, 119, 38), 1.17),
    (231, "two_tailed_fox", "Two-Tailed Fox", "two_tail_fox", (183, 100, 44), (63, 151, 164), .90),
)
CREATURE_ACTOR_TYPE_OFFSET = 4

# Scenery livestock authored by eloria-assets/tools/sunmane/creatures.py.  They
# are not built here, but this script owns models.json and the asset catalog, so
# it has to re-register them or a plain rebuild silently unregisters the herds.
# The wider concept-art roster occupies one contiguous block after every range
# already in models.json (which ends at 427).  Server-side actor-type allocation
# belongs to eloria-server; these ids are reserved here for it to adopt.
ROSTER_ACTOR_TYPE_BASE = 428
HOVERING_FAMILIES = {"amorphous"}


def roster_actor_type(index: int) -> int:
    return ROSTER_ACTOR_TYPE_BASE + index


AMBIENT_CREATURES = (
    ("sunmane_steppe_horse", "Sunmane Steppe Horse", "equine", 1.25, False),
    ("sunmane_dun_mare", "Sunmane Dun Mare", "equine", 1.2, False),
    ("sunmane_grey_pony", "Sunmane Grey Pony", "equine", 1.1, True),
)
AMBIENT_NOTE = ("Scenery livestock instanced by the client's ambient population "
                "system. They carry no server actor type: actor-type allocation "
                "belongs to eloria-server, and these never arrive over the wire.")
AMBIENT_SOURCE_NOTE = ("Authored to equine proportions on the shared creature rig "
                       "by eloria-assets/tools/sunmane/creatures.py.")

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

    def texture(self, name: str, png: bytes) -> int:
        view = self.bytes_view(png)
        self.doc.setdefault("images", []).append(
            {"name": name, "bufferView": view, "mimeType": "image/png"})
        image = len(self.doc["images"]) - 1
        self.doc.setdefault("samplers", []).append(
            {"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497})
        sampler = len(self.doc["samplers"]) - 1
        self.doc.setdefault("textures", []).append({"source": image, "sampler": sampler})
        return len(self.doc["textures"]) - 1

    def material(self, name: str, color: tuple[int, int, int], *, metallic: float = 0.,
                 roughness: float = .78, emissive: tuple[int, int, int] | None = None,
                 texture_png: bytes | None = None, normal_png: bytes | None = None,
                 metallic_roughness_png: bytes | None = None,
                 double_sided: bool = False, alpha: float = 1.0,
                 alpha_mode: str | None = None) -> int:
        factor = [c / 255. for c in color] + [float(alpha)]
        pbr = {"baseColorFactor": factor, "metallicFactor": metallic,
               "roughnessFactor": roughness}
        if texture_png is not None:
            pbr["baseColorTexture"] = {"index": self.texture(name + " Base Color", texture_png)}
        if metallic_roughness_png is not None:
            pbr["metallicRoughnessTexture"] = {
                "index": self.texture(name + " Roughness", metallic_roughness_png)}
        material = {"name": name, "pbrMetallicRoughness": pbr, "doubleSided": double_sided}
        if alpha_mode:
            material["alphaMode"] = alpha_mode
        if normal_png is not None:
            material["normalTexture"] = {"index": self.texture(name + " Normal", normal_png)}
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


@lru_cache(maxsize=64)
def resized_texture(path: Path, size: int = 512) -> bytes:
    image = Image.open(path).convert("RGBA")
    if max(image.size) > size:
        image.thumbnail((size, size), Image.Resampling.LANCZOS)
    encoded = io.BytesIO()
    image.save(encoded, format="PNG", optimize=True)
    return encoded.getvalue()


@lru_cache(maxsize=64)
def neutral_texture(path: Path, *, floor: float = .34, size: int = 512) -> bytes:
    """Retain authored texture detail while making it safe for runtime tinting."""
    image = Image.open(path).convert("RGBA")
    if max(image.size) > size:
        image.thumbnail((size, size), Image.Resampling.LANCZOS)
    source = np.asarray(image).astype(np.float32)
    luminance = (source[..., :3] * np.array([.2126, .7152, .0722])).sum(axis=2) / 255.
    luminance = floor + (1. - floor) * luminance
    rgb = np.repeat((luminance * 255.)[..., None], 3, axis=2)
    out = np.dstack((np.clip(rgb, 0, 255).astype(np.uint8), source[..., 3].astype(np.uint8)))
    encoded = io.BytesIO()
    Image.fromarray(out, "RGBA").save(encoded, format="PNG", optimize=True)
    return encoded.getvalue()


@lru_cache(maxsize=16)
def surface_detail_texture(kind: str, size: int = 512) -> bytes:
    """Neutral cloth/leather detail that remains compatible with runtime tinting."""
    yy, xx = np.mgrid[0:size, 0:size]
    if kind == "cloth":
        value = (.86 + np.sin(xx * math.pi) * .035
                 + np.sin(yy * math.pi) * .028
                 + np.sin((xx + yy) * math.pi / 31.) * .020)
    elif kind == "leather":
        grain = (np.sin(xx * .173 + np.sin(yy * .071) * 2.1)
                 + np.sin(yy * .219 + np.sin(xx * .049) * 1.7)) * .035
        pores = (((xx * 17 + yy * 29) % 113) < 3) * -.08
        value = .82 + grain + pores
    else:
        value = (.90 + np.sin((xx + yy) * math.pi / 6.) * .035
                 + np.sin((xx - yy) * math.pi / 6.) * .025)
    channel = np.clip(value * 255., 0, 255).astype(np.uint8)
    alpha = np.full((size, size), 255, dtype=np.uint8)
    encoded = io.BytesIO()
    Image.fromarray(np.dstack((channel, channel, channel, alpha)), "RGBA").save(
        encoded, format="PNG", optimize=True)
    return encoded.getvalue()


def source_texture(document: dict, directory: Path, material_index: int,
                   texture_key: str) -> bytes | None:
    material = document["materials"][material_index]
    if texture_key == "normalTexture":
        texture_spec = material.get("normalTexture")
    else:
        texture_spec = material.get("pbrMetallicRoughness", {}).get(texture_key)
    if texture_spec is None:
        return None
    texture = document["textures"][texture_spec["index"]]
    image = document["images"][texture["source"]]
    path = directory / image["uri"]
    if not path.is_file():
        path = directory.parent / image["uri"]
    return resized_texture(path)


def quaternion_matrix(rotation: list[float]) -> np.ndarray:
    x, y, z, w = rotation
    length = math.sqrt(x*x + y*y + z*z + w*w)
    if length < 1e-8:
        return np.eye(4, dtype=np.float64)
    x, y, z, w = x/length, y/length, z/length, w/length
    return np.array([
        [1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w), 0],
        [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w), 0],
        [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y), 0],
        [0, 0, 0, 1],
    ], dtype=np.float64)


def node_matrix(node: dict) -> np.ndarray:
    if "matrix" in node:
        return np.asarray(node["matrix"], dtype=np.float64).reshape(4, 4).T
    translation = np.eye(4, dtype=np.float64)
    translation[:3, 3] = np.asarray(node.get("translation", [0, 0, 0]), dtype=np.float64)
    rotation = quaternion_matrix(node.get("rotation", [0, 0, 0, 1]))
    scale = np.eye(4, dtype=np.float64)
    scale[np.arange(3), np.arange(3)] = np.asarray(node.get("scale", [1, 1, 1]), dtype=np.float64)
    return translation @ rotation @ scale


def global_node_matrix(document: dict, node_index: int) -> np.ndarray:
    parents = {}
    for parent, node in enumerate(document["nodes"]):
        for child in node.get("children", []):
            parents[child] = parent
    chain = []
    current = node_index
    while current is not None:
        chain.append(current)
        current = parents.get(current)
    result = np.eye(4, dtype=np.float64)
    for index in reversed(chain):
        result = result @ node_matrix(document["nodes"][index])
    return result


def joint_parents(document: dict, skin: dict) -> dict[int, int | None]:
    """Parent slot for every joint, indexed by position in skin["joints"]."""
    slot_of = {node: slot for slot, node in enumerate(skin["joints"])}
    parents: dict[int, int | None] = {slot: None for slot in range(len(skin["joints"]))}
    for node_index, node in enumerate(document["nodes"]):
        if node_index not in slot_of:
            continue
        for child in node.get("children", []):
            if child in slot_of:
                parents[slot_of[child]] = slot_of[node_index]
    return parents


def hierarchy_order(parents: dict[int, int | None]) -> list[int]:
    """Joint slots ordered so a parent is always visited before its children."""
    children: dict[int | None, list[int]] = {}
    for slot, parent in parents.items():
        children.setdefault(parent, []).append(slot)
    order: list[int] = []
    queue = list(children.get(None, []))
    while queue:
        slot = queue.pop(0)
        order.append(slot)
        queue.extend(children.get(slot, []))
    return order


def axis_rotation(degrees: tuple[float, float, float]) -> np.ndarray:
    """Extrinsic X-then-Y-then-Z rotation in world bind axes."""
    result = np.eye(3, dtype=np.float64)
    for axis, value in enumerate(degrees):
        if not value:
            continue
        angle = math.radians(value)
        cos, sin = math.cos(angle), math.sin(angle)
        matrix = np.eye(3, dtype=np.float64)
        i, j = [(1, 2), (2, 0), (0, 1)][axis]
        matrix[i, i] = cos; matrix[i, j] = -sin
        matrix[j, i] = sin; matrix[j, j] = cos
        result = matrix @ result
    return result


def stance_rotation(spec: dict, name: str) -> np.ndarray | None:
    """Rotation applied to a joint's offset, mirrored from the right side."""
    stance = spec.get("stance", {})
    if name in stance:
        return axis_rotation(stance[name])
    if name.endswith("_l"):
        mirrored = stance.get(name[:-2] + "_r")
        if mirrored is not None:
            # Reflecting through the YZ plane flips rotation about Y and Z.
            return axis_rotation((mirrored[0], -mirrored[1], -mirrored[2]))
    return None


def retarget_bind(source_bind: np.ndarray, parents: dict[int, int | None],
                  names: list[str], spec: dict, leg_scale: float) -> np.ndarray:
    """Rebuild the global bind pose from race segment lengths and stance.

    Stance is expressed by rotating a joint's *offset from its parent*, never
    by rotating the joint's own frame.  That distinction is the whole reason a
    digitigrade Ssarathi is possible at all on a shared rig: glTF rotation
    tracks are absolute, so the animation library overwrites every rest
    rotation the moment a clip plays, and any anatomy stored there would snap
    back to the human A-pose.  Local translations are never animated below the
    pelvis, so anatomy stored in the offsets survives every clip -- the limb
    keeps its own segment directions inside whatever frame the clip puts the
    parent in.  Joint frames are therefore left exactly as the source authored
    them, which also means the clips' rotations still mean what they meant.
    """
    segment = spec.get("segment", {})
    result = np.zeros_like(source_bind)
    for slot in hierarchy_order(parents):
        parent = parents[slot]
        if parent is None:
            result[slot] = source_bind[slot].copy()
            continue
        group = joint_group(names[parent])
        scale = segment.get(group, 1.)
        if group in LEG_GROUPS:
            scale *= leg_scale
        offset = (source_bind[slot][:3, 3] - source_bind[parent][:3, 3]) * scale
        rotation = stance_rotation(spec, names[slot])
        if rotation is not None:
            offset = rotation @ offset
        result[slot] = np.eye(4, dtype=np.float64)
        result[slot][:3, :3] = source_bind[slot][:3, :3]
        result[slot][:3, 3] = result[parent][:3, 3] + offset
    return result


def solve_leg_scale(source_bind: np.ndarray, parents: dict[int, int | None],
                    names: list[str], spec: dict) -> float:
    """Leg-chain scale that restores the source hip-to-ground distance.

    Ground contact height is affine in the chain scale -- the offsets are
    scaled, the rotations are not -- so two probes solve it exactly.
    """
    ground = [names.index(joint) for joint in GROUND_JOINTS]
    target = source_bind[ground, 1, 3].min()
    probes = []
    for candidate in (1., 1.1):
        bind = retarget_bind(source_bind, parents, names, spec, candidate)
        probes.append((candidate, float(bind[ground, 1, 3].min())))
    (k0, y0), (k1, y1) = probes
    if abs(y1 - y0) < 1e-9:
        return 1.
    return k0 + (target - y0) * (k1 - k0) / (y1 - y0)


def bone_axis(slot: int, source_bind: np.ndarray, parents: dict[int, int | None],
              names: list[str], children: dict[int, list[int]]) -> np.ndarray:
    """Unit bone direction at a joint, in that joint's own bind frame."""
    options = children.get(slot, [])
    preferred = CHAIN_CHILD.get(names[slot])
    target = None
    for child in options:
        if preferred is None or names[child] == preferred:
            target = source_bind[child][:3, 3]
            break
    if target is None and options:
        target = source_bind[options[0]][:3, 3]
    if target is None:
        parent = parents[slot]
        if parent is None:
            return np.array([0., 1., 0.])
        direction = source_bind[slot][:3, 3] - source_bind[parent][:3, 3]
    else:
        direction = target - source_bind[slot][:3, 3]
    length = np.linalg.norm(direction)
    if length < 1e-7:
        return np.array([0., 1., 0.])
    return source_bind[slot][:3, :3].T @ (direction / length)


def shape_matrices(source_bind: np.ndarray, target_bind: np.ndarray,
                   parents: dict[int, int | None], names: list[str],
                   spec: dict) -> np.ndarray:
    """Per-joint skinning transform T = B . G . A^-1 for the race body."""
    girth = spec.get("girth", {})
    swell = spec.get("swell", {})
    children: dict[int, list[int]] = {}
    for slot, parent in parents.items():
        if parent is not None:
            children.setdefault(parent, []).append(slot)
    result = np.zeros_like(source_bind)
    identity = np.eye(3, dtype=np.float64)
    for slot in range(len(source_bind)):
        group = joint_group(names[slot])
        thickness = girth.get(group, 1.)
        uniform = swell.get(group, 1.)
        axis = bone_axis(slot, source_bind, parents, names, children)
        # Scale only across the bone, so a thicker arm stays the same length
        # whatever direction the bone happens to point in world space.
        local = uniform * (identity + (thickness - 1.) *
                           (identity - np.outer(axis, axis)))
        shape = np.eye(4, dtype=np.float64)
        shape[:3, :3] = local
        result[slot] = target_bind[slot] @ shape @ np.linalg.inv(source_bind[slot])
    return result


def apply_shape(positions: np.ndarray, normals: np.ndarray, joints: np.ndarray,
                weights: np.ndarray, transforms: np.ndarray):
    """Linear blend skinning of the source mesh into the retargeted rest pose."""
    weight = weights.astype(np.float64)
    total = weight.sum(axis=1, keepdims=True)
    weight = np.divide(weight, total, out=np.zeros_like(weight), where=total > 1e-8)
    blended = np.einsum("nk,nkij->nij", weight, transforms[joints.astype(np.int64)])
    unweighted = total[:, 0] <= 1e-8
    if unweighted.any():
        blended[unweighted] = np.eye(4, dtype=np.float64)
    linear = blended[:, :3, :3]
    moved = np.einsum("nij,nj->ni", linear, positions.astype(np.float64)) + blended[:, :3, 3]
    # Normals need the inverse transpose because girth scaling is not uniform.
    cofactor = np.linalg.inv(linear).transpose(0, 2, 1)
    turned = np.einsum("nij,nj->ni", cofactor, normals.astype(np.float64))
    turned /= np.maximum(np.linalg.norm(turned, axis=1, keepdims=True), 1e-9)
    return moved.astype(np.float32), turned.astype(np.float32)


def matrix_quaternion(matrix: np.ndarray) -> list[float]:
    """glTF (x, y, z, w) quaternion from a rotation matrix."""
    trace = matrix[0, 0] + matrix[1, 1] + matrix[2, 2]
    if trace > 0.:
        scale = math.sqrt(trace + 1.) * 2.
        w = .25 * scale
        x = (matrix[2, 1] - matrix[1, 2]) / scale
        y = (matrix[0, 2] - matrix[2, 0]) / scale
        z = (matrix[1, 0] - matrix[0, 1]) / scale
    else:
        axis = int(np.argmax((matrix[0, 0], matrix[1, 1], matrix[2, 2])))
        i, j, k = axis, (axis + 1) % 3, (axis + 2) % 3
        scale = math.sqrt(1. + matrix[i, i] - matrix[j, j] - matrix[k, k]) * 2.
        values = [0., 0., 0.]
        values[i] = .25 * scale
        values[j] = (matrix[j, i] + matrix[i, j]) / scale
        values[k] = (matrix[k, i] + matrix[i, k]) / scale
        x, y, z = values
        w = (matrix[k, j] - matrix[j, k]) / scale
    length = math.sqrt(x * x + y * y + z * z + w * w) or 1.
    return [float(x / length), float(y / length), float(z / length), float(w / length)]


def write_rest_pose(nodes: list[dict], skin_joints: list[int], target_bind: np.ndarray,
                    parents: dict[int, int | None]) -> np.ndarray:
    """Store the retargeted rest pose on the joint nodes; return inverse binds.

    The rest transforms stay rigid, so the animation library's rotation tracks
    keep their meaning and only the proportions they act on have changed.
    """
    for slot, node_index in enumerate(skin_joints):
        parent = parents[slot]
        if parent is None:
            continue
        local = np.linalg.inv(target_bind[parent]) @ target_bind[slot]
        node = nodes[node_index]
        node.pop("matrix", None)
        node.pop("scale", None)
        node["translation"] = [float(value) for value in local[:3, 3]]
        node["rotation"] = matrix_quaternion(local[:3, :3])
    inverse = np.linalg.inv(target_bind)
    return inverse.transpose(0, 2, 1).reshape(-1, 16).astype("float32")


def skinned_subset(positions: np.ndarray, normals: np.ndarray, uvs: np.ndarray,
                   joints: np.ndarray, weights: np.ndarray, faces: np.ndarray,
                   face_mask: np.ndarray, offset: float):
    selected = faces[face_mask]
    if not len(selected):
        empty = np.empty((0, 3), dtype=np.float32)
        return (empty, empty.copy(), np.empty((0, 2), dtype=np.float32),
                np.empty(0, dtype=np.uint32), np.empty((0, 4), dtype=np.uint16),
                np.empty((0, 4), dtype=np.float32))
    unique, remapped = np.unique(selected.reshape(-1), return_inverse=True)
    garment_positions = positions[unique] + normals[unique] * offset
    return (garment_positions.astype(np.float32), normals[unique].astype(np.float32),
            uvs[unique].astype(np.float32), remapped.astype(np.uint32),
            joints[unique].astype(np.uint16), weights[unique].astype(np.float32))


def influence(weights: np.ndarray, joints: np.ndarray, selected_joints: set[int]) -> np.ndarray:
    return np.where(np.isin(joints, list(selected_joints)), weights, 0.).sum(axis=1)


def player_accessory(feature: str, joint_by_name: dict[str, int],
                     bind: dict[str, np.ndarray], color: tuple[int, int, int],
                     accent: tuple[int, int, int]):
    """Integrated race anatomy, authored against the reference bind pose.

    These are not props hung off a human.  Each form is placed from the rig's
    own joint positions and skinned to the joints it grows from, then pushed
    through the same retarget as the body, so it lands on the race's own
    skeleton rather than on the reference one it was measured against.
    """
    mesh = ShapeMesh()
    head = joint_by_name["Head"]
    pelvis = joint_by_name["pelvis"]
    spine = joint_by_name["spine_03"]
    lower_spine = joint_by_name["spine_01"]
    neck = joint_by_name["neck_01"]
    clavicles = {-1.: joint_by_name["clavicle_l"],
                  1.: joint_by_name["clavicle_r"]}
    forearms = {-1.: joint_by_name["lowerarm_l"],
                 1.: joint_by_name["lowerarm_r"]}
    thighs = {-1.: joint_by_name["thigh_l"], 1.: joint_by_name["thigh_r"]}
    if feature == "horns":
        # Curved, ringed horns grow from broad roots inside the temples. This
        # preserves the original stylized model language without detached fins.
        for side in (-1., 1.):
            mesh.tapered_curve([
                (side * .070, 1.700, -.010), (side * .118, 1.727, -.026),
                (side * .155, 1.752, -.058), (side * .184, 1.782, -.104),
                (side * .200, 1.818, -.155), (side * .196, 1.845, -.192),
                (side * .186, 1.866, -.216), (side * .156, 1.879, -.230),
                (side * .124, 1.882, -.234),
            ], [.060, .057, .052, .045, .034, .026, .018, .010, .004],
                head, 0, 14)
            for y, x, z, radius in ((1.729, .120, -.028, .060),
                                     (1.756, .157, -.062, .053),
                                     (1.786, .186, -.108, .045),
                                     (1.820, .200, -.158, .034),
                                     (1.848, .195, -.196, .025)):
                mesh.sphere((side * x, y, z), (radius, .026, radius),
                            head, 1, 3, 10)
    elif feature == "crystal":
        # Glasswardens are human scholars and field engineers in the concept
        # sheets. A compact brass-and-crystal lens rig conveys that identity
        # without a fantasy crown or detached shoulder shards.
        mesh.tapered_curve([(-.150, 1.700, .070), (-.095, 1.714, .105),
                            (0., 1.720, .116), (.095, 1.714, .105),
                            (.150, 1.700, .070)],
                           [.010, .010, .009, .010, .010], head, 0, 12)
        for side in (-1., 1.):
            x = side * .052
            mesh.cylinder((x, 1.704, .112), (x, 1.704, .146), .043,
                          head, 0, 16)
            mesh.sphere((x, 1.704, .150), (.072, .066, .018),
                        head, 1, 6, 16)
            mesh.cylinder((side * .094, 1.704, .131),
                          (side * .146, 1.696, .083), .007, head, 0, 10)
            # Temple strap back to the band, so the rig is worn rather than
            # hovering in front of the face.
            mesh.tapered_curve([(side * .150, 1.700, .070),
                                (side * .162, 1.696, .010),
                                (side * .148, 1.690, -.048)],
                               [.009, .008, .007], head, 0, 8)
        mesh.cylinder((-.010, 1.704, .136), (.010, 1.704, .136),
                      .007, head, 0, 10)
    elif feature == "scaled":
        # Ssarathi anatomy: a joined muzzle and jaw, a dorsal ridge that runs
        # from the brow down the spine, a counterweighting tail, and claws.
        # Gold is reserved for small nostril, tooth and scale accents.
        mesh.sphere((0., 1.625, .145), (.176, .104, .232), head, 0, 7, 14)
        mesh.sphere((0., 1.592, .124), (.150, .060, .196), head, 0, 6, 12)
        mesh.sphere((0., 1.648, .062), (.204, .150, .150), head, 0, 6, 14)
        mesh.tapered_curve([(0., 1.618, .238), (0., 1.648, .186),
                            (0., 1.682, .124), (0., 1.712, .066)],
                           [.016, .020, .019, .012], head, 0, 8)
        for side in (-1., 1.):
            mesh.tapered_curve([(side * .018, 1.702, .105),
                                (side * .066, 1.716, .098),
                                (side * .108, 1.708, .070),
                                (side * .142, 1.688, .036)],
                               [.018, .022, .016, .007], head, 0, 8)
            mesh.cone((side * .036, 1.634, .240),
                      (side * .036, 1.634, .252), .007, head, 1, 8)
            # Brow scales and cheek scutes.
            for y, z, radius in ((1.690, .128, .026), (1.664, .166, .021)):
                mesh.sphere((side * .086, y, z), (radius, radius * .5, radius),
                            head, 1, 3, 8)
        # Dorsal crest: skull, nape and upper back, one continuous line.
        crest = ((head, 1.672, -.032, .030, -.082, .034),
                 (head, 1.700, -.070, .026, -.090, .038),
                 (head, 1.712, -.116, .014, -.092, .036),
                 (head, 1.702, -.160, -.004, -.086, .031),
                 (neck, 1.586, -.092, -.012, -.078, .028),
                 (neck, 1.522, -.104, -.014, -.070, .024),
                 (spine, 1.412, -.118, -.014, -.062, .022),
                 (spine, 1.332, -.130, -.014, -.054, .019))
        for joint, y, z, rise, back, size in crest:
            mesh.cone((0., y, z), (0., y + rise, z + back), size, joint, 0, 10)
        # Tail: a real tapered chord off the sacrum rather than a flat blade,
        # shared between the pelvis and the lower spine so it tracks the hips
        # through the shared locomotion clips instead of swinging as one board.
        points, radii = [], []
        for step in range(13):
            t = step / 12.
            points.append((0.,
                           .952 - .58 * t - .08 * math.sin(t * math.pi)
                           + .10 * max(0., t - .78),
                           -.100 - .86 * t))
            radii.append(.112 * (1. - t) ** 1.30 + .007)
        mesh.blend = lambda position: [
            (pelvis, 1.),
            (lower_spine, max(0., .42 * (1. + position[2] / .34)))]
        mesh.tapered_curve(points, radii, pelvis, 0, 14)
        # Tail scutes read the taper at a distance and break up the tube.
        for step in range(1, 10):
            t = step / 11.
            y = (.952 - .58 * t - .08 * math.sin(t * math.pi)
                 + .10 * max(0., t - .78))
            z = -.100 - .86 * t
            size = .088 * (1. - t) ** 1.2 + .008
            mesh.sphere((0., y + size * .8, z), (size * .7, size, size * 1.5),
                        pelvis, 1, 3, 8)
        mesh.blend = None
        # Claws on every finger and both toes, placed from the rig itself.
        for side in ("l", "r"):
            for digit in ("index", "middle", "pinky", "ring", "thumb"):
                tip = bind.get(f"{digit}_04_leaf_{side}")
                knuckle = bind.get(f"{digit}_03_{side}")
                if tip is None or knuckle is None:
                    continue
                direction = tip - knuckle
                length = float(np.linalg.norm(direction))
                if length < 1e-5:
                    continue
                direction = direction / length
                mesh.cone(tuple(tip - direction * length * .30),
                          tuple(tip + direction * length * 1.15),
                          length * .34, joint_by_name[f"{digit}_04_leaf_{side}"], 1, 8)
            toe = bind.get(f"ball_leaf_{side}")
            ball = bind.get(f"ball_{side}")
            if toe is None or ball is None:
                continue
            direction = toe - ball
            length = float(np.linalg.norm(direction))
            if length < 1e-5:
                continue
            direction = direction / length
            for offset in (-.030, .0, .030):
                root = toe + np.array([offset, 0., 0.]) - direction * length * .2
                mesh.cone(tuple(root), tuple(root + direction * length * .95),
                          .019, joint_by_name[f"ball_leaf_{side}"], 1, 8)
    elif feature == "stone":
        # Stoneborn plating is load-bearing anatomy: a sternum slab, stepped
        # pauldrons, forearm bracers and thigh plates, all seated on the joints
        # they armour, with crystal seams running between them.
        mesh.sphere((0., 1.315, .062), (.330, .270, .080), spine, 0, 5, 12)
        mesh.sphere((0., 1.180, .058), (.280, .200, .070), lower_spine, 0, 4, 12)
        for side in (-1., 1.):
            shoulder = bind.get("clavicle_r" if side > 0 else "clavicle_l")
            arm = bind.get("upperarm_r" if side > 0 else "upperarm_l")
            if shoulder is None or arm is None:
                continue
            cap = arm + (arm - shoulder) * .10
            mesh.sphere((float(cap[0]), float(cap[1]) + .045, float(cap[2])),
                        (.230, .175, .205), clavicles[side], 0, 5, 12)
            # Two hewn bands stepping down the deltoid, following the arm so
            # they read as plating rather than boxes hung off the shoulder.
            elbow = bind.get("lowerarm_r" if side > 0 else "lowerarm_l")
            if elbow is not None:
                along = elbow - arm
                for start, end, radius in ((.02, .17, .118), (.20, .34, .102)):
                    mesh.tapered_curve([tuple(arm + along * start),
                                        tuple(arm + along * (start + end) * .5),
                                        tuple(arm + along * end)],
                                       [radius, radius * 1.04, radius * .90],
                                       clavicles[side], 0, 14)
            forearm = bind.get("lowerarm_r" if side > 0 else "lowerarm_l")
            hand = bind.get("hand_r" if side > 0 else "hand_l")
            if forearm is not None and hand is not None:
                mesh.cylinder(tuple(forearm + (hand - forearm) * .18),
                              tuple(forearm + (hand - forearm) * .74),
                              .085, forearms[side], 0, 14)
                mesh.tapered_curve([tuple(forearm + (hand - forearm) * .20),
                                    tuple(forearm + (hand - forearm) * .72)],
                                   [.012, .010], forearms[side], 1, 8)
            thigh = bind.get("thigh_r" if side > 0 else "thigh_l")
            knee = bind.get("calf_r" if side > 0 else "calf_l")
            if thigh is not None and knee is not None:
                mid = thigh + (knee - thigh) * .40
                mesh.sphere((float(mid[0]), float(mid[1]), float(mid[2]) + .045),
                            (.190, .300, .130), thighs[side], 0, 5, 12)
            # Brow and jaw plates keep eyes, mouth and hairline readable.
            mesh.sphere((side * .104, 1.652, .054), (.072, .100, .050),
                        head, 0, 4, 10)
            mesh.sphere((side * .088, 1.594, .088), (.058, .062, .046),
                        head, 0, 4, 10)
        mesh.sphere((0., 1.706, .094), (.190, .050, .046), head, 0, 4, 12)
        # Crystal seams: thin accent lines along the sternum and the nape.
        mesh.tapered_curve([(-.038, 1.400, .104), (.014, 1.348, .110),
                            (-.022, 1.292, .096), (.026, 1.238, .082)],
                           [.008, .007, .006, .004], spine, 1, 8)
        mesh.tapered_curve([(0., 1.560, -.072), (0., 1.512, -.086)],
                           [.010, .007], neck, 1, 8)
    elif feature == "fungal":
        # Mycelari carry a true parasol: a domed cap with a gilled underside,
        # an annulus collar and a stipe, plus bracket shelves on the shoulders.
        mesh.tapered_curve([(0., 1.706, -.010), (0., 1.760, -.014),
                            (0., 1.822, -.016)], [.064, .056, .050],
                           head, 0, 12)
        mesh.revolve([(1.968, .038), (1.952, .126), (1.928, .202),
                      (1.898, .262), (1.868, .298), (1.844, .314),
                      (1.832, .308), (1.840, .248), (1.852, .172),
                      (1.864, .096), (1.872, .048)], head, 0, 22)
        mesh.sphere((0., 1.962, 0.), (.088, .040, .088), head, 0, 3, 16)
        # Gills: radial blades in the shadow of the cap.
        for index in range(18):
            angle = 2. * math.pi * index / 18.
            cos, sin = math.cos(angle), math.sin(angle)
            corners = []
            for radius, height in ((.098, 1.866), (.292, 1.836)):
                for offset, drop in ((-.004, .0), (.004, .0)):
                    corners.append((cos * radius - sin * offset, height,
                                     sin * radius + cos * offset + drop))
            inner, outer = corners[:2], corners[2:]
            mesh.prism([inner[0], inner[1], outer[1], outer[0],
                        (inner[0][0], inner[0][1] - .026, inner[0][2]),
                        (inner[1][0], inner[1][1] - .026, inner[1][2]),
                        (outer[1][0], outer[1][1] - .020, outer[1][2]),
                        (outer[0][0], outer[0][1] - .020, outer[0][2])],
                       head, 1)
        # Annulus collar where the cap meets the stipe.
        mesh.revolve([(1.848, .072), (1.840, .114), (1.830, .106),
                      (1.824, .074)], head, 1, 18)
        # Shoulder brackets: layered shelf fungi that intersect the clavicle.
        for side in (-1., 1.):
            shoulder = bind.get("clavicle_r" if side > 0 else "clavicle_l")
            arm = bind.get("upperarm_r" if side > 0 else "upperarm_l")
            if shoulder is None or arm is None:
                continue
            for step, (along, lift, width, depth, thick) in enumerate(
                    ((.35, .050, .150, .118, .036),
                     (.62, .014, .126, .098, .030),
                     (.86, -.020, .092, .074, .024))):
                centre = shoulder + (arm - shoulder) * along + np.array([0., lift, 0.])
                mesh.sphere((float(centre[0]), float(centre[1]), float(centre[2]) - .020),
                            (width, thick, depth), clavicles[side], 0, 4, 12)
                mesh.sphere((float(centre[0]), float(centre[1]) - thick * .34,
                             float(centre[2]) - .020),
                            (width * .84, thick * .40, depth * .84),
                            clavicles[side], 1, 3, 10)
        # Mycelial threads down the sternum.
        mesh.tapered_curve([(0., 1.430, .100), (-.030, 1.372, .104),
                            (.026, 1.312, .096), (-.014, 1.256, .084)],
                           [.009, .008, .007, .005], spine, 1, 8)
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
    joint_by_name = {document["nodes"][node].get("name", ""): index
                     for index, node in enumerate(skin["joints"])}
    joint_names = [document["nodes"][node].get("name", "") for node in skin["joints"]]
    anatomy = ANATOMY.get(race, {})
    source_bind = np.stack([global_node_matrix(document, node) for node in skin["joints"]])
    parents = joint_parents(document, skin)
    leg_scale = solve_leg_scale(source_bind, parents, joint_names, anatomy)
    target_bind = retarget_bind(source_bind, parents, joint_names, anatomy, leg_scale)
    transforms = shape_matrices(source_bind, target_bind, parents, joint_names, anatomy)
    inverse = write_rest_pose(glb.doc["nodes"], list(skin["joints"]), target_bind, parents)
    inverse_accessor = glb.accessor(inverse, "MAT4")
    glb.doc["skins"] = [{"name": "Armature", "joints": list(skin["joints"]),
                         "inverseBindMatrices": inverse_accessor, "skeleton": skin["joints"][0]}]
    base_uri = document["images"][document["textures"][
        document["materials"][2]["pbrMetallicRoughness"]["baseColorTexture"]["index"]]["source"]]["uri"]
    if config.get("preserve_body"):
        body_texture = resized_texture(source.parent / base_uri)
    else:
        body_texture = recolored_texture(
            source.parent / base_uri, config["color"], config["accent"],
            config.get("body_pattern", config["feature"]))
    hair_base = source_texture(document, source.parent, 0, "baseColorTexture")
    eye_base = source_texture(document, source.parent, 1, "baseColorTexture")
    materials = {
        "eyebrows": glb.material(
            config["label"] + " Eyebrows", (255, 255, 255), roughness=.82,
            texture_png=neutral_texture(source.parent / document["images"][document["textures"][
                document["materials"][0]["pbrMetallicRoughness"]["baseColorTexture"]["index"]]["source"]]["uri"])
                if hair_base else None,
            normal_png=source_texture(document, source.parent, 0, "normalTexture"),
            double_sided=True),
        "eyes": glb.material(
            config["label"] + " Eyes", (255, 255, 255), roughness=.30,
            texture_png=neutral_texture(source.parent / document["images"][document["textures"][
                document["materials"][1]["pbrMetallicRoughness"]["baseColorTexture"]["index"]]["source"]]["uri"], floor=.62)
                if eye_base else None,
            normal_png=source_texture(document, source.parent, 1, "normalTexture"),
            emissive=tuple(c // 16 for c in config["accent"]), double_sided=True),
        "body": glb.material(
            config["label"] + " Body", (255, 255, 255), roughness=.78,
            texture_png=body_texture,
            normal_png=source_texture(document, source.parent, 2, "normalTexture"),
            metallic_roughness_png=source_texture(
                document, source.parent, 2, "metallicRoughnessTexture"),
            double_sided=True),
        "feature": glb.material(config["label"] + " Integrated Feature",
                                config.get("feature_color", config["color"]),
                                metallic=.04, roughness=.72),
        "accent": glb.material(config["label"] + " Integrated Accent",
                               config["accent"], metallic=.12, roughness=.46,
                               emissive=tuple(c // 28 for c in config["accent"])),
    }
    shirt, pants, boots, trim = config["wardrobe"]
    materials.update({
        "shirt": glb.material(config["label"] + " Shirt", shirt, roughness=.88,
                              texture_png=surface_detail_texture("cloth")),
        "shirt_trim": glb.material(config["label"] + " Shirt Trim", trim,
                                   metallic=.22, roughness=.52,
                                   texture_png=surface_detail_texture("trim")),
        "pants": glb.material(config["label"] + " Pants", pants, roughness=.91,
                              texture_png=surface_detail_texture("cloth")),
        "pants_trim": glb.material(config["label"] + " Pants Seam",
                                    tuple(round(c * .68) for c in pants),
                                   metallic=.12, roughness=.60,
                                   texture_png=surface_detail_texture("trim")),
        "boots": glb.material(config["label"] + " Boots", boots, roughness=.82,
                              texture_png=surface_detail_texture("leather")),
        "boots_trim": glb.material(config["label"] + " Boots Seam",
                                    tuple(round(c * .68) for c in boots),
                                   metallic=.18, roughness=.48,
                                   texture_png=surface_detail_texture("trim")),
        "headwear": glb.material(config["label"] + " Headwear", shirt, roughness=.88,
                                 texture_png=surface_detail_texture("cloth")),
        "headwear_trim": glb.material(config["label"] + " Headwear Trim", trim,
                                      metallic=.20, roughness=.50,
                                      texture_png=surface_detail_texture("trim")),
    })
    vertices = triangles = 0
    body_arrays = None
    for mesh_index, node_index in enumerate((65, 66, 67)):
        source_primitive = document["meshes"][mesh_index]["primitives"][0]
        attrs = source_primitive["attributes"]
        source_positions = read_accessor(document, binary, attrs["POSITION"])
        source_normals = read_accessor(document, binary, attrs["NORMAL"])
        uvs = read_accessor(document, binary, attrs["TEXCOORD_0"]).astype("float32")
        joints = read_accessor(document, binary, attrs["JOINTS_0"]).astype("uint16")
        weights = read_accessor(document, binary, attrs["WEIGHTS_0"]).astype("float32")
        positions, normals = apply_shape(source_positions, source_normals,
                                         joints, weights, transforms)
        indices = read_accessor(document, binary, source_primitive["indices"]).astype("uint32")
        material = (materials["eyebrows"], materials["eyes"], materials["body"])[mesh_index]
        primitive = glb.primitive(positions, normals, uvs, indices, material,
                                  joints=joints, weights=weights)
        canonical_name = ("Eyebrows", "Eyes", "Body")[mesh_index]
        glb.doc["meshes"].append({"name": canonical_name,
                                  "primitives": [primitive]})
        glb.doc["nodes"][node_index]["name"] = canonical_name
        glb.doc["nodes"][node_index]["mesh"] = len(glb.doc["meshes"]) - 1
        glb.doc["nodes"][node_index]["skin"] = 0
        vertices += len(positions)
        triangles += len(indices) // 3
        if mesh_index == 2:
            body_arrays = (positions, normals, uvs, joints, weights,
                           indices.reshape(-1, 3), source_positions)

    # Default clothing is copied from the original body surface, offset by only
    # millimetres and retaining the exact skin weights. It therefore follows all
    # 65 joints instead of moving as one rigid chest/pelvis attachment.
    positions, normals, uvs, joints, weights, faces, source_body = body_arrays
    # Garment cuts are selected on the *source* body.  The thresholds below are
    # absolute heights on the reference skeleton, so reading them off a
    # retargeted body would move every hem as soon as a race changed
    # proportions -- a digitigrade Ssarathi would get boots at mid-shin and a
    # Stoneborn would get a shirt at the collarbone.  Faces are shared between
    # the two, so the mask stays valid for the deformed geometry.
    centers = source_body[faces].mean(axis=1)
    y = centers[:, 1]
    x = np.abs(centers[:, 0])
    z = centers[:, 2]
    by_name = lambda *names: {joint_by_name[name] for name in names}
    shirt_score = influence(weights, joints, by_name(
        "pelvis", "spine_01", "spine_02", "spine_03", "clavicle_l", "clavicle_r",
        "upperarm_l", "upperarm_r"))
    pants_score = influence(weights, joints, by_name(
        "pelvis", "thigh_l", "thigh_r", "calf_l", "calf_r"))
    boots_score = influence(weights, joints, by_name(
        "calf_l", "calf_r", "foot_l", "foot_r", "ball_l", "ball_r",
        "ball_leaf_l", "ball_leaf_r"))
    head_score = influence(weights, joints, by_name("Head"))
    shirt_mask = ((shirt_score[faces].mean(axis=1) > .30) & (y > .900) & (y < 1.550))
    pants_mask = ((pants_score[faces].mean(axis=1) > .30) & (y > .245) & (y < 1.120))
    boots_mask = ((boots_score[faces].mean(axis=1) > .24) & (y < .320))
    shirt_trim = shirt_mask & (((x > .285) & (y > 1.345)) |
                               ((y > 1.435) & (x < .145) & (z > .045)))
    pants_trim = pants_mask & (y > 1.015) & (y < 1.110)
    boots_trim = boots_mask & (y > .270) & (y < .325)
    head_band = ((head_score[faces].mean(axis=1) > .45) &
                 (y > 1.655) & (y < 1.710) & (z < .075))
    head_cap = ((head_score[faces].mean(axis=1) > .45) &
                (y > 1.690) & (z < .050))

    def add_skinned(name: str, mask: np.ndarray, offset: float, material: int) -> None:
        nonlocal vertices, triangles
        arrays = skinned_subset(positions, normals, uvs, joints, weights, faces, mask, offset)
        if not len(arrays[0]):
            return
        primitive = glb.primitive(*arrays[:4], material, joints=arrays[4], weights=arrays[5])
        glb.mesh_node(name, [primitive], skin=0, parent=68)
        vertices += len(arrays[0])
        triangles += len(arrays[3]) // 3

    add_skinned("Wardrobe_Shirt", shirt_mask, .008, materials["shirt"])
    add_skinned("Wardrobe_Shirt_Trim", shirt_trim, .012, materials["shirt_trim"])
    add_skinned("Wardrobe_Pants", pants_mask, .009, materials["pants"])
    add_skinned("Wardrobe_Pants_Seam", pants_trim, .013, materials["pants_trim"])
    add_skinned("Wardrobe_Boots", boots_mask, .013, materials["boots"])
    add_skinned("Wardrobe_Boots_Seam", boots_trim, .017, materials["boots_trim"])
    add_skinned("Wardrobe_Head_Band", head_band, .012, materials["headwear_trim"])
    add_skinned("Wardrobe_Head_Cap", head_cap, .014, materials["headwear"])

    bind_positions = {name: source_bind[slot][:3, 3]
                      for slot, name in enumerate(joint_names)}
    accessory = player_accessory(config["feature"], joint_by_name, bind_positions,
                                 config["color"], config["accent"])
    if len(accessory[0]):
        primitives = []
        # ShapeMesh emits one consolidated primitive and material selectors as its seventh array.
        for material_index, arrays in enumerate(accessory[6]):
            if len(arrays[0]) == 0:
                continue
            feature_material = (materials["feature"], materials["accent"])[material_index]
            # Race features are authored against the reference skeleton and
            # then pushed through the same retarget as the body, so horns sit
            # on the retargeted skull and a tail leaves the retargeted pelvis
            # instead of floating where the reference joint used to be.
            shaped, shaped_normals = apply_shape(arrays[0], arrays[1], arrays[4],
                                                 arrays[5], transforms)
            primitives.append(glb.primitive(shaped, shaped_normals, arrays[2],
                                            arrays[3], feature_material,
                                            joints=arrays[4], weights=arrays[5]))
            vertices += len(arrays[0])
            triangles += len(arrays[3]) // 3
        glb.mesh_node("Integrated_%s_Feature" % config["label"].replace(" ", "_"),
                      primitives, skin=0, parent=68)
    glb.write(output)
    return {"vertices": vertices, "triangles": triangles,
            "joints": len(skin["joints"]), "feature": config["feature"],
            "wardrobe": "skinned", "anatomy": "retargeted",
            "stature": round(anatomy.get("stature", 1.), 4),
            "legChainScale": round(float(leg_scale), 4),
            "hipHeight": round(float(target_bind[joint_by_name["pelvis"]][1, 3]), 5),
            "groundHeight": round(float(min(
                target_bind[joint_by_name[name]][1, 3] for name in GROUND_JOINTS)), 5)}


class ShapeMesh:
    """Small, consistently wound primitive authoring helper."""
    def __init__(self):
        self.groups = [([], [], [], [], [], []), ([], [], [], [], [], [])]
        # Optional position -> [(joint, weight), ...] callback.  A rigid single
        # joint is right for a horn or a claw, but a tail or a shoulder shelf
        # needs to be shared between joints or it swings as one board.
        self.blend = None

    def _skin(self, position, joint: int):
        if self.blend is None:
            return [joint, 0, 0, 0], [1., 0., 0., 0.]
        pairs = sorted(self.blend(position), key=lambda pair: -pair[1])[:4]
        total = sum(weight for _, weight in pairs) or 1.
        joints = [int(bone) for bone, _ in pairs] + [0] * (4 - len(pairs))
        weights = [weight / total for _, weight in pairs] + [0.] * (4 - len(pairs))
        return joints, weights

    def _append(self, positions, normals, uvs, indices, joint: int, material: int):
        p, n, t, f, j, w = self.groups[material]
        base = len(p); p.extend(positions); n.extend(normals); t.extend(uvs)
        f.extend(base + int(i) for i in indices)
        for position in positions:
            joints, weights = self._skin(position, joint)
            j.append(joints); w.append(weights)

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
        self.prism(corners, joint, material)

    def prism(self, corners, joint=0, material=0):
        """Six-sided solid through eight arbitrary corners.

        Hewn Stoneborn plating and Mycelari gills are flat forms that do not
        line up with the world axes, and an axis-aligned box cannot express
        either without visibly floating off the surface it belongs to.
        """
        corners=[np.asarray(corner,dtype=float) for corner in corners]
        quads=((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7))
        p=[];n=[];u=[];f=[]
        for quad in quads:
            points=[corners[i] for i in quad]
            normal=np.cross(points[1]-points[0],points[2]-points[0])
            length=np.linalg.norm(normal)
            if length<1e-9: continue
            normal/=length
            base=len(p);p.extend(tuple(point) for point in points)
            n.extend([tuple(normal)]*4);u.extend(((0,0),(1,0),(1,1),(0,1)))
            f.extend((base,base+1,base+2,base,base+2,base+3))
        self._append(p,n,u,f,joint,material)

    def revolve(self, profile, joint=0, material=0, sides=20):
        """Surface of revolution about the Y axis through (height, radius) pairs."""
        points=[(0.,height,0.) for height,_ in profile]
        radii=[radius for _,radius in profile]
        self.tapered_curve(points,radii,joint,material,sides)

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

    def tapered_curve(self, points, radii, joint=0, material=0, sides=16):
        """Author a continuous tapered tube through bind-pose control points."""
        centers = np.asarray(points, dtype=float)
        if len(centers) < 2 or len(centers) != len(radii):
            return
        p=[];n=[];u=[];f=[]
        previous_right = None
        for row, center in enumerate(centers):
            if row == 0:
                tangent = centers[1] - center
            elif row == len(centers) - 1:
                tangent = center - centers[row - 1]
            else:
                tangent = centers[row + 1] - centers[row - 1]
            tangent /= max(np.linalg.norm(tangent), 1e-6)
            if previous_right is None:
                ref = np.array((1., 0., 0.)) if abs(tangent[0]) < .82 else np.array((0., 0., 1.))
                right = np.cross(tangent, ref)
            else:
                right = previous_right - tangent * np.dot(previous_right, tangent)
            if np.linalg.norm(right) < 1e-5:
                right = np.cross(tangent, np.array((0., 1., 0.)))
            right /= max(np.linalg.norm(right), 1e-6)
            forward = np.cross(right, tangent)
            forward /= max(np.linalg.norm(forward), 1e-6)
            previous_right = right
            for side in range(sides):
                angle = 2 * math.pi * side / sides
                normal = right * math.cos(angle) + forward * math.sin(angle)
                p.append(tuple(center + normal * radii[row]))
                n.append(tuple(normal));u.append((side / sides, row / (len(centers) - 1)))
        for row in range(len(centers) - 1):
            for side in range(sides):
                nxt = (side + 1) % sides
                a = row * sides + side; b = row * sides + nxt
                c = (row + 1) * sides + side; d = (row + 1) * sides + nxt
                f.extend((a, c, b, b, c, d))
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


# The legacy blockout bone table and sphere/box geometry were replaced by the
# body-plan driven anatomy builder in creature_anatomy.py.  Bone *names* are
# still part of the runtime contract: godot-client/data/actors/models.json
# binds attachment points to "head", "body" and "neck".
CREATURE_BONES = anatomy.BONE_TOPOLOGY


def global_bone_positions(bones):
    return anatomy.global_positions(bones)


def creature_geometry(archetype: str, scale: float, bones=None) -> "anatomy.AnatomyMesh":
    return anatomy.creature_geometry(archetype, scale, bones)


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



def apply_growth(mesh, slug: str, scale: float) -> None:
    """Scatter the moss, crystal, barnacles or bramble the art shows.

    The art never scatters growth evenly.  A moss bear carries a mantle over
    its back and shoulders with the brown hide showing on flank and belly; a
    moss troll wears the same mantle plus a beard.  Scattering uniformly in
    every direction — which is what an even radial pass does — turns both into
    a featureless bush and throws away the silhouette the growth is there to
    decorate.  So the heavy pass rides the upper surface, and a much lighter
    pass drapes the flanks.
    """
    entries = roster.GROWTH.get(slug)
    if not entries or not getattr(mesh, "torso", None):
        return
    spine, radii, bones = mesh.torso
    # An upright body is narrower than a quadruped's barrel, so the same count
    # reads as denser; it needs a size gain to clear a robe, not a count gain.
    upright = getattr(mesh, "upright", False)
    density = 1.60 if upright else 1.40
    gain = 1.32 if upright else 1.22
    limbs = getattr(mesh, "growth_extra", None) or ()
    # A standing figure's growth stops at the collar; running it to the end of
    # the torso spine buries the face, which is the one part a player reads.
    crown = 0.86 if upright else 0.98
    for kind, count, size in entries:
        # Mineral growth erupts in every direction; soft growth settles on the
        # upper surfaces.  One bias for both gave golems a tidy one-sided fan.
        bias = .30 if kind in anatomy.SPIKY_GROWTH else .60
        # Mantle: heaviest over the back and shoulders, thinning as it wraps.
        anatomy.encrust(mesh, kind, max(int(count * density), 3), spine, radii,
                        bones, scale, seed=f"{slug}:{kind}", size=size * gain,
                        span=(0.10, crown), up_bias=bias)
        # Drape: a sparse fringe further round the barrel, so the mantle has an
        # edge rather than stopping dead at the waterline.
        anatomy.encrust(mesh, kind, max(int(count * density * .40), 1), spine,
                        radii, bones, scale, seed=f"{slug}:{kind}:flank",
                        size=size * gain * .70, span=(0.14, crown * .96),
                        up_bias=min(bias, .16))
        # Limbs: arms and shoulders on the upright families, so growth does not
        # stop at the shoulder seam.
        for i, (pts, widths, limb_bones) in enumerate(limbs):
            anatomy.encrust(mesh, kind, max(int(count * density * .38), 2), pts,
                            widths, limb_bones, scale,
                            seed=f"{slug}:{kind}:limb{i}", size=size * gain * .78,
                            span=(0.05, 0.85), up_bias=.45)


def add_baked_animation(glb: GLB, name: str,
                        channels: dict[tuple[int, str], tuple[str, list, list]]) -> None:
    """Write a baked clip that may drive several paths on the same node."""
    animation = {"name": name, "samplers": [], "channels": []}
    for (node, _), (path, times, values) in sorted(channels.items()):
        input_acc = glb.accessor(np.asarray(times, dtype="float32"), "SCALAR", bounds=True)
        width = "VEC4" if path == "rotation" else "VEC3"
        output_acc = glb.accessor(np.asarray(values, dtype="float32"), width)
        animation["samplers"].append({"input": input_acc, "output": output_acc,
                                      "interpolation": "LINEAR"})
        animation["channels"].append({"sampler": len(animation["samplers"]) - 1,
                                      "target": {"node": node, "path": path}})
    glb.doc.setdefault("animations", []).append(animation)


def build_roster_creature(path: Path, actor_type: int, slug: str, label: str,
                          family: str, plan: str, base: tuple[int, int, int],
                          accent: tuple[int, int, int], scale: float,
                          surface: str | None = None) -> dict:
    """Author one creature from any skeleton family, not just the quadrupeds."""
    glb = GLB()
    glb.doc["nodes"] = []
    bones, mesh, clips = families.build_parts(family, plan, scale, slug)
    apply_growth(mesh, slug, scale)
    globals_ = anatomy.global_positions(bones)
    children: dict[int, list[int]] = {index: [] for index in range(len(bones))}
    for index, (_, parent, _) in enumerate(bones):
        if parent >= 0:
            children[parent].append(index)
    for index, (name, parent, translation) in enumerate(bones):
        node = {"name": name, "translation": [float(v) for v in translation]}
        if children[index]:
            node["children"] = children[index]
        glb.doc["nodes"].append(node)
    glb.doc["scenes"][0]["nodes"] = [0]

    inverse = []
    for position in globals_:
        matrix = np.eye(4, dtype="float32")
        matrix[:3, 3] = -position
        inverse.append(matrix.T.reshape(-1))
    glb.doc["skins"] = [{"name": f"Nymara {family.title()} Rig",
                         "joints": list(range(len(bones))), "skeleton": 0,
                         "inverseBindMatrices": glb.accessor(
                             np.asarray(inverse, dtype="float32"), "MAT4")}]

    # Full-colour albedo plus a matching normal map, both derived from one
    # height field so the relief lines up with the pattern.  The albedo carries
    # the palette, so the base colour factor stays white and is not applied
    # twice; the underside shares the grain and tints with a factor.
    hints = families.material_hints(family, plan, slug)
    surface_kind = hints.get("surface") or surface or plan
    albedo_png, _ = surfaces.surface_maps(
        surface_kind, base, accent, seed=slug, size=256,
        marking=surfaces.MARKINGS.get(slug))
    _, normal_png = surfaces.surface_maps(
        surface_kind, base, accent, seed=slug, size=192)
    if hints.get("glow"):
        # Shards, motes, orbs and props on an elemental belong to its own
        # palette; bone-white keratin turned every crystal swarm grey.
        horn_albedo, horn_normal = surfaces.surface_maps(
            surface_kind, accent, base, seed=f"{slug}:feature", size=160)
    else:
        horn_albedo, horn_normal = surfaces.keratin_maps(accent, seed=slug, size=160)
    dark = tuple(max(14, int(c * .26)) for c in base)
    alpha = float(hints.get("alpha", 1.0))
    alpha_mode = hints.get("alpha_mode")
    glow = float(hints.get("glow", 0.0))
    two_sided = bool(hints.get("double_sided", False))
    body_glow = tuple(int(c * glow) for c in base) if glow else None
    accent_glow = tuple(int(c * min(1.0, glow * 1.35)) for c in accent) if glow else None
    mats = [glb.material(f"{label} Hide", (255, 255, 255), roughness=.86,
                         texture_png=albedo_png, normal_png=normal_png,
                         emissive=body_glow, alpha=alpha, alpha_mode=alpha_mode,
                         double_sided=two_sided)]
    hide_texture = len(glb.doc["textures"]) - 2
    hide_normal = len(glb.doc["textures"]) - 1
    underside = tuple(min(255, int(.46 * a + .54 * b) + 26) for a, b in zip(accent, base))
    mats.append(glb.material(f"{label} Underside", underside, roughness=.82,
                             emissive=accent_glow, alpha=alpha,
                             alpha_mode=alpha_mode, double_sided=two_sided))
    glb.doc["materials"][mats[1]]["pbrMetallicRoughness"]["baseColorTexture"] = {
        "index": hide_texture}
    glb.doc["materials"][mats[1]]["normalTexture"] = {"index": hide_normal}
    mats.append(glb.material(f"{label} Claw", dark, roughness=.44, metallic=.04))
    # Motes, shards, orbs and props stay opaque so they read through the body.
    mats.append(glb.material(f"{label} Keratin", (255, 255, 255), roughness=.56,
                             metallic=.03, texture_png=horn_albedo,
                             normal_png=horn_normal, emissive=accent_glow))
    # Growth carries its own colour and surface: moss is green, rime is pale
    # ice, crystal keeps the creature's own mineral tint.
    growth_kinds = [(kind, count) for kind, count, _ in roster.GROWTH.get(slug, [])]
    growth_rgb = anatomy.growth_colour(growth_kinds, accent, base)
    growth_surface = {"moss": "moss", "vine": "moss", "leaf": "moss",
                      "fungus": "hide", "thorn": "bark", "barnacle": "barnacle",
                      "coral": "barnacle", "rime": "ice", "crystal": "crystal",
                      "ember": "energy", "plate": "stone", "spine": "bark"}.get(
        growth_kinds[0][0] if growth_kinds else "moss", "moss")
    growth_albedo, growth_normal = surfaces.surface_maps(
        growth_surface, growth_rgb, accent, seed=f"{slug}:growth", size=160)
    mats.append(glb.material(f"{label} Growth", (255, 255, 255), roughness=.80,
                             texture_png=growth_albedo, normal_png=growth_normal,
                             emissive=accent_glow))

    groups = mesh.arrays()
    # Settle the bind pose: raise the rig and its geometry together so a rest
    # pose never starts below the floor.  Shifting the root translation moves
    # every global, and shifting the vertices by the same amount keeps the skin
    # binding identical.
    filled = [a for a in groups if len(a[0])]
    if filled:
        lowest = float(min(a[0][:, 1].min() for a in filled))
        if lowest < -0.002:
            lift = -lowest
            for arrays in groups:
                if len(arrays[0]):
                    arrays[0][:, 1] += lift
            name, parent, translation = bones[0]
            bones[0] = (name, parent, (translation[0], translation[1] + lift,
                                       translation[2]))
            globals_ = anatomy.global_positions(bones)
            inverse = []
            for position in globals_:
                matrix = np.eye(4, dtype="float32")
                matrix[:3, 3] = -position
                inverse.append(matrix.T.reshape(-1))
            glb.doc["skins"][0]["inverseBindMatrices"] = glb.accessor(
                np.asarray(inverse, dtype="float32"), "MAT4")
            glb.doc["nodes"][0]["translation"] = [float(v) for v in bones[0][2]]

    primitives = []
    vertices = triangles = 0
    for index, arrays in enumerate(groups):
        if not len(arrays[0]):
            continue
        primitives.append(glb.primitive(*arrays[:4], mats[index],
                                        joints=arrays[4], weights=arrays[5]))
        vertices += len(arrays[0])
        triangles += len(arrays[3]) // 3
    glb.mesh_node(label, primitives, skin=0, parent=0)

    clips = anatomy.ground_clamp(clips, bones, groups)
    clips = anatomy.settle_final_pose(clips, bones, groups, "Death_A")
    for clip in anatomy.REQUIRED_CLIPS:
        add_baked_animation(glb, clip, clips[clip])
    glb.write(path)
    return {"actor_type": actor_type, "id": slug, "name": label, "family": family,
            "archetype": plan, "vertices": vertices, "triangles": triangles,
            "joints": len(bones), "animations": len(anatomy.REQUIRED_CLIPS)}


def build_creature(path: Path, actor_type: int, slug: str, label: str, archetype: str,
                   base: tuple[int, int, int], accent: tuple[int, int, int],
                   scale: float) -> dict:
    """Author one production creature GLB: rig, skin, materials and clips."""
    glb = GLB()
    glb.doc["nodes"] = []
    bones = anatomy.skeleton_for(archetype, scale)
    globals_ = anatomy.global_positions(bones)
    children: dict[int, list[int]] = {index: [] for index in range(len(bones))}
    for index, (_, parent, _) in enumerate(bones):
        if parent >= 0:
            children[parent].append(index)
    for index, (name, parent, translation) in enumerate(bones):
        node = {"name": name, "translation": [float(v) for v in translation]}
        if children[index]:
            node["children"] = children[index]
        glb.doc["nodes"].append(node)
    glb.doc["scenes"][0]["nodes"] = [0]

    inverse = []
    for position in globals_:
        matrix = np.eye(4, dtype="float32")
        matrix[:3, 3] = -position
        inverse.append(matrix.T.reshape(-1))
    inverse_acc = glb.accessor(np.asarray(inverse, dtype="float32"), "MAT4")
    glb.doc["skins"] = [{"name": "Nymara Creature Rig",
                         "joints": list(range(len(bones))),
                         "skeleton": 0, "inverseBindMatrices": inverse_acc}]

    # -- materials -------------------------------------------------------
    # Full-colour albedo plus a matching normal map, both derived from one
    # height field so the relief lines up with the pattern.  The albedo carries
    # the palette, so the base colour factor stays white and is not applied
    # twice; the underside shares the grain and tints with a factor.
    hints = families.material_hints("quadruped", archetype, slug)
    albedo_png, _ = surfaces.surface_maps(
        archetype, base, accent, seed=slug, size=256,
        marking=surfaces.MARKINGS.get(slug))
    _, normal_png = surfaces.surface_maps(
        archetype, base, accent, seed=slug, size=192)
    if hints.get("glow"):
        # Shards, motes, orbs and props on an elemental belong to its own
        # palette; bone-white keratin turned every crystal swarm grey.
        horn_albedo, horn_normal = surfaces.surface_maps(
            surface_kind, accent, base, seed=f"{slug}:feature", size=160)
    else:
        horn_albedo, horn_normal = surfaces.keratin_maps(accent, seed=slug, size=160)
    dark = tuple(max(14, int(c * .26)) for c in base)
    alpha = float(hints.get("alpha", 1.0))
    alpha_mode = hints.get("alpha_mode")
    glow = float(hints.get("glow", 0.0))
    two_sided = bool(hints.get("double_sided", False))
    body_glow = tuple(int(c * glow) for c in base) if glow else None
    accent_glow = tuple(int(c * min(1.0, glow * 1.35)) for c in accent) if glow else None
    mats = [glb.material(f"{label} Hide", (255, 255, 255), roughness=.86,
                         texture_png=albedo_png, normal_png=normal_png,
                         emissive=body_glow, alpha=alpha, alpha_mode=alpha_mode,
                         double_sided=two_sided)]
    hide_texture = len(glb.doc["textures"]) - 2
    hide_normal = len(glb.doc["textures"]) - 1
    underside = tuple(min(255, int(.46 * a + .54 * b) + 26) for a, b in zip(accent, base))
    mats.append(glb.material(f"{label} Underside", underside, roughness=.82,
                             emissive=accent_glow, alpha=alpha,
                             alpha_mode=alpha_mode, double_sided=two_sided))
    glb.doc["materials"][mats[1]]["pbrMetallicRoughness"]["baseColorTexture"] = {
        "index": hide_texture}
    glb.doc["materials"][mats[1]]["normalTexture"] = {"index": hide_normal}
    mats.append(glb.material(f"{label} Claw", dark, roughness=.44, metallic=.04))
    # Motes, shards, orbs and props stay opaque so they read through the body.
    mats.append(glb.material(f"{label} Keratin", (255, 255, 255), roughness=.56,
                             metallic=.03, texture_png=horn_albedo,
                             normal_png=horn_normal, emissive=accent_glow))
    # Growth carries its own colour and surface: moss is green, rime is pale
    # ice, crystal keeps the creature's own mineral tint.
    growth_kinds = [(kind, count) for kind, count, _ in roster.GROWTH.get(slug, [])]
    growth_rgb = anatomy.growth_colour(growth_kinds, accent, base)
    growth_surface = {"moss": "moss", "vine": "moss", "leaf": "moss",
                      "fungus": "hide", "thorn": "bark", "barnacle": "barnacle",
                      "coral": "barnacle", "rime": "ice", "crystal": "crystal",
                      "ember": "energy", "plate": "stone", "spine": "bark"}.get(
        growth_kinds[0][0] if growth_kinds else "moss", "moss")
    growth_albedo, growth_normal = surfaces.surface_maps(
        growth_surface, growth_rgb, accent, seed=f"{slug}:growth", size=160)
    mats.append(glb.material(f"{label} Growth", (255, 255, 255), roughness=.80,
                             texture_png=growth_albedo, normal_png=growth_normal,
                             emissive=accent_glow))

    geometry = anatomy.creature_geometry(archetype, scale, bones)
    apply_growth(geometry, slug, scale)
    groups = geometry.arrays()
    primitives = []
    vertices = triangles = 0
    for index, arrays in enumerate(groups):
        if not len(arrays[0]):
            continue
        primitives.append(glb.primitive(*arrays[:4], mats[index],
                                        joints=arrays[4], weights=arrays[5]))
        vertices += len(arrays[0])
        triangles += len(arrays[3]) // 3
    glb.mesh_node(label, primitives, skin=0, parent=0)

    clips = anatomy.ground_clamp(anatomy.animation_set(archetype, scale, bones),
                                 bones, groups)
    clips = anatomy.settle_final_pose(clips, bones, groups, "Death_A")
    for clip in anatomy.REQUIRED_CLIPS:
        add_baked_animation(glb, clip, clips[clip])

    glb.write(path)
    return {"actor_type": actor_type, "id": slug, "name": label, "archetype": archetype,
            "vertices": vertices, "triangles": triangles, "joints": len(bones),
            "animations": len(anatomy.REQUIRED_CLIPS)}


def build_equipment(path: Path, slug: str, label: str, kind: str,
                    base: tuple[int,int,int], accent: tuple[int,int,int],
                    rig: "equipment_authoring.Rig") -> dict:
    """Author one equipment GLB through the body-conforming pipeline."""
    return equipment_authoring.build_equipment_piece(
        path, rig, slug, label, kind, base, accent)


HAIR_SOURCES = {
    "buzzed": {"female": "Hair_BuzzedFemale", "male": "Hair_Buzzed"},
    "parted": {"female": "Hair_SimpleParted", "male": "Hair_SimpleParted"},
    "long": {"female": "Hair_Long", "male": "Hair_Long"},
    "buns": {"female": "Hair_Buns", "male": "Hair_Buns"},
}


def build_hair(source_dir: Path, output: Path, style: str, gender: str) -> dict:
    source_name = HAIR_SOURCES[style][gender]
    source = source_dir / "hairstyles" / f"{source_name}.gltf"
    document = json.loads(source.read_text(encoding="utf-8"))
    binary = (source.parent / document["buffers"][0]["uri"]).read_bytes()
    mesh_node_index = next(i for i, node in enumerate(document["nodes"]) if "mesh" in node)
    mesh_index = document["nodes"][mesh_node_index]["mesh"]
    primitive_source = document["meshes"][mesh_index]["primitives"][0]
    attrs = primitive_source["attributes"]
    positions = read_accessor(document, binary, attrs["POSITION"]).astype(np.float64)
    normals = read_accessor(document, binary, attrs["NORMAL"]).astype(np.float64)
    uvs = read_accessor(document, binary, attrs["TEXCOORD_0"]).astype(np.float32)
    indices = read_accessor(document, binary, primitive_source["indices"]).astype(np.uint32)

    body_path = source_dir / f"Superhero_{gender.title()}_FullBody.gltf"
    body_document = json.loads(body_path.read_text(encoding="utf-8"))
    head_node = next(i for i, node in enumerate(body_document["nodes"])
                     if node.get("name") == "Head")
    to_head_local = np.linalg.inv(global_node_matrix(body_document, head_node))
    transform = to_head_local @ global_node_matrix(document, mesh_node_index)
    homogeneous = np.column_stack((positions, np.ones(len(positions))))
    positions = (transform @ homogeneous.T).T[:, :3].astype(np.float32)
    normal_matrix = np.linalg.inv(transform[:3, :3]).T
    normals = (normal_matrix @ normals.T).T
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-6)

    material_source = primitive_source.get("material", 0)
    base_spec = document["materials"][material_source]["pbrMetallicRoughness"]["baseColorTexture"]
    image_uri = document["images"][document["textures"][base_spec["index"]]["source"]]["uri"]
    image_path = source.parent / image_uri
    if not image_path.is_file():
        image_path = source_dir / image_uri
    glb = GLB(generator="Eloria native Quaternius hairstyle packer")
    material = glb.material(
        f"Native Hair {style.title()}", (255, 255, 255), roughness=.82,
        texture_png=neutral_texture(image_path, floor=.42),
        normal_png=source_texture(document, source.parent, material_source, "normalTexture"),
        double_sided=True)
    primitive = glb.primitive(positions, normals.astype(np.float32), uvs, indices, material)
    glb.mesh_node("NativeHair_%s_%s" % (style.title(), gender.title()), [primitive])
    glb.write(output)
    return {"style": style, "gender": gender, "source": source_name,
            "vertices": len(positions), "triangles": len(indices) // 3,
            "bounds": {"min": positions.min(axis=0).round(5).tolist(),
                       "max": positions.max(axis=0).round(5).tolist()}}


def glb_geometry_stats(path: Path) -> dict:
    """Triangle, joint and clip counts read back out of a finished GLB."""
    raw = path.read_bytes()
    json_length = struct.unpack_from("<II", raw, 12)[0]
    doc = json.loads(raw[20:20 + json_length])
    triangles = 0
    for mesh in doc.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            if "indices" in primitive:
                triangles += doc["accessors"][primitive["indices"]]["count"] // 3
    joints = len(doc["skins"][0]["joints"]) if doc.get("skins") else 0
    return {"triangles": triangles, "joints": joints,
            "animations": len(doc.get("animations", []))}


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


def humanoid_model(scene: str, culture: str, gender: str) -> dict:
    return {
        "scene": scene,
        "animationLibrary": "res://assets/actors/native/shared/Universal_Animation_Library.glb",
        "animationMap": "res://data/animations/luminous.json",
        "culture": culture,
        "gender": gender,
        "hairStyles": [
            f"res://assets/actors/native/hair/buzzed_{gender}.glb",
            f"res://assets/actors/native/hair/parted_{gender}.glb",
            f"res://assets/actors/native/hair/long_{gender}.glb",
            f"res://assets/actors/native/hair/buns_{gender}.glb",
        ],
        "boneAliases": {"head": "Head"},
        # Native source characters face +Z, matching the creation-preview
        # camera.  Keeping this at zero presents the face and culture features
        # by default; the legacy 180-degree correction showed their backs.
        # Stature is carried here rather than in the rig: the animation clips
        # write pelvis translation directly, so a taller skeleton would leave
        # the hips at the reference height with the feet hanging below it.
        "import": {"scale": round(ANATOMY.get(culture, {}).get("stature", 1.), 4),
                   "rotationDegreesX": 0,
                   "rotationDegreesY": 0, "rotationDegreesZ": 0},
        "attachments": {
            "right_hand": "hand_r", "left_hand": "hand_l", "head": "Head",
            "back": "spine_03", "body": "spine_02", "pelvis": "pelvis",
            "feet": ["foot_l", "foot_r"], "neck": "neck_01",
        },
    }


def culture_loadout(culture: str, role: str = "") -> dict[str, int]:
    # The culture body models already carry a fully skinned shirt, pants, boots,
    # trim, and optional headwear. Keep NPC defaults to held/shoulder props so
    # rigid pelvis/body/head attachments cannot cover that production wardrobe.
    base = {
        "luminous": {},
        "votary": {0: 109},
        "glasswarden": {0: 102, 1: 101, 2: 101},
        "orun": {0: 106, 1: 103, 2: 103},
        "greyhaven": {0: 104, 1: 102, 2: 102},
        "ssarathi": {0: 107, 1: 104, 2: 104},
    }[culture].copy()
    if culture == "luminous" and role == "guard":
        return {0: 112, 1: 105, 2: 105}
    if culture == "luminous" and role == "ferryman":
        return {0: 105, 2: 102}
    if role in {"merchant", "official", "scholar", "lake_priest", "elder", "councilor"}:
        base.pop(1, None)
    if role in {"merchant", "scholar", "researcher", "astronomer"}:
        base[0] = {"luminous": 108, "glasswarden": 102,
                   "greyhaven": 113}.get(culture, base.get(0, 108))
    return base


def build_model_registry() -> dict:
    models = {}
    actor_types = {}
    creation = []
    for actor_type, model_id in PLAYER_ACTOR_TYPES.items():
        race, gender = model_id.rsplit("_", 1)
        models[model_id] = humanoid_model(
            f"res://assets/actors/native/races/{model_id}.glb", race, gender)
        actor_types[str(actor_type)] = model_id
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

    for index, entry in enumerate(roster.ROSTER):
        slug = entry[0]
        models[slug] = {
            "scene": f"res://assets/actors/native/creatures/{slug}.glb",
            "animationLibrary": f"res://assets/actors/native/creatures/{slug}.glb",
            "animationMap": "res://data/animations/creature.json",
            "import": {"scale": 1, "rotationDegreesX": 0,
                       "rotationDegreesY": 0, "rotationDegreesZ": 0},
            "attachments": {"head": "head", "body": "body", "neck": "neck"},
        }
        actor_types[str(roster_actor_type(index))] = slug

    for slug, _label, _archetype, scale, _tacked in AMBIENT_CREATURES:
        models[slug] = {
            "scene": f"res://assets/actors/native/creatures/{slug}.glb",
            "animationLibrary": f"res://assets/actors/native/creatures/{slug}.glb",
            "animationMap": "res://data/animations/creature.json",
            "import": {"scale": scale, "rotationDegreesX": 0,
                       "rotationDegreesY": 0, "rotationDegreesZ": 0},
            "attachments": {"head": "head", "body": "body", "neck": "neck"},
            "serverActorType": None,
        }

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
    # Invasion-only server IDs intentionally reuse the production native
    # creature library. Keep these in the generator so rebuilding character
    # assets cannot silently regress them to magenta fallbacks.
    invasion_models = {
        400: "river_otter", 401: "elk", 402: "desert_tortoise",
        403: "sunscale_drake", 404: "snow_hare", 405: "thunder_ram",
        406: "ice_bear", 407: "frost_tiger", 408: "ash_crawler",
        409: "dire_wolf", 410: "armored_rhino", 411: "giant_komodo",
        412: "emberfox", 413: "ridgehorn", 414: "saber_tooth_cat",
        415: "fire_salamander", 416: "moose", 417: "mossback_boar",
        418: "frost_maw", 419: "porcupine", 420: "two_tailed_fox",
        421: "miretoad", 422: "giant_komodo", 423: "sunscale_drake",
        424: "bog_lurker", 425: "miretoad", 426: "giant_crocodile",
        427: "giant_crocodile",
    }

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
    actor_types.update({str(key): value for key, value in invasion_models.items()})
    return {"schemaVersion": 2, "models": models, "actorTypes": actor_types,
            "creationOptions": creation, "npcLooks": npc_looks}


def build_equipment_registry(rig: "equipment_authoring.Rig",
                             idle_bases: dict | None) -> dict:
    """Equipment registry v3: character-space sockets and skinned garments."""
    return equipment_authoring.build_equipment_registry(rig, EQUIPMENT, idle_bases)


def carry_forward_ambient(manifest_path: Path, models_path: Path,
                          manifest: dict, models: dict) -> None:
    """Preserve ambient scenery entries contributed by regional generators.

    The Sunmane horses are authored by eloria-assets/tools/sunmane/creatures.py
    and merged into these two registries.  Rebuilding the actor library used to
    drop them silently, which left every herd on the steppe as a magenta
    fallback until someone noticed.  Carry them across instead of rewriting
    them away.
    """
    if manifest_path.is_file():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        ambient = previous.get("ambientCreatures")
        if ambient:
            manifest["ambientCreatures"] = ambient
    if models_path.is_file():
        previous = json.loads(models_path.read_text(encoding="utf-8"))
        for slug, entry in previous.get("models", {}).items():
            if slug not in models["models"] and entry.get("serverActorType", 0) is None:
                models["models"][slug] = entry


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
    parser.add_argument("--animation-library",type=Path,
                        default=repo_root/"godot-client/assets/actors/native/shared/Universal_Animation_Library.glb",
                        help="clip source used to solve weapon grips in the idle pose")
    parser.add_argument("--only",choices=("all","equipment","creatures"),default="all",
                        help="rebuild a single section instead of the whole library")
    args=parser.parse_args()
    if args.only in ("equipment","creatures") and args.manifest.is_file():
        manifest=json.loads(args.manifest.read_text(encoding="utf-8"))
        if args.only=="equipment":
            manifest["equipment"]={}
            manifest["genericEquipment"]={}
        else:
            manifest["creatures"]={}
    else:
        manifest={"schemaVersion":2,"source":"nymara-concept-art-named.zip",
                  "pipeline":"build_native_nymara_glbs.py","races":{},"hair":{},
                  "creatures":{},"equipment":{},"genericEquipment":{}}
    if args.only=="all":
        for gender in ("female", "male"):
            for style in HAIR_SOURCES:
                hair_id = f"{style}_{gender}"
                path = args.output / "hair" / f"{hair_id}.glb"
                manifest["hair"][hair_id] = build_hair(args.source, path, style, gender) | {
                    "path": str(path.relative_to(repo_root))}
                print("hair", hair_id, manifest["hair"][hair_id])
        for race in RACES:
            for gender in ("female","male"):
                model=f"{race}_{gender}";path=args.output/"races"/f"{model}.glb"
                manifest["races"][model]=build_player(args.source,path,race,gender)|{"path":str(path.relative_to(repo_root))}
                print("race",model,manifest["races"][model])
    if args.only in ("all","creatures"):
        for actor_type,slug,label,archetype,base,accent,scale in CREATURES:
            actor_type += CREATURE_ACTOR_TYPE_OFFSET
            path=args.output/"creatures"/f"{slug}.glb"
            manifest["creatures"][slug]=build_creature(path,actor_type,slug,label,archetype,base,accent,scale)|{"path":str(path.relative_to(repo_root))}
            print("creature",slug,manifest["creatures"][slug])
    if args.only in ("all","creatures"):
        for index, entry in enumerate(roster.ROSTER):
            slug, label, family, plan, base, accent, scale, sheet, row, column = entry
            path = args.output / "creatures" / f"{slug}.glb"
            record = build_roster_creature(path, roster_actor_type(index), slug, label,
                                           family, plan, base, accent, scale)
            record |= {"path": str(path.relative_to(repo_root)),
                       "locale": roster.SHEET_LOCALES[sheet],
                       "concept": {"sheet": sheet, "cell": [row, column]}}
            if family in HOVERING_FAMILIES:
                record["hovers"] = True
            manifest["creatures"][slug] = record
            print("creature", slug, record["triangles"], "tris")
    if args.only=="creatures":
        previous=manifest.get("validation",{}).get("results",{})
        rebuilt={str(path.relative_to(repo_root)):validate_glb(path)
                 for path in (args.output/"creatures").rglob("*.glb")}
        merged={**previous,**{k:v for k,v in rebuilt.items() if k in previous}}
        manifest["validation"]={"files":len(merged),"results":merged}
        write_json(args.manifest, manifest)
        print(f"rebuilt {len(manifest['creatures'])} creature GLBs")
        return
    # Equipment is authored against the rig as it exists on disk, so a full run
    # has to build the races first or the geometry is fitted to a stale rest
    # pose. Loading the rig here also keeps a clean tree bootstrappable.
    rig_source=args.output/"races/luminous_male.glb"
    rig=equipment_authoring.load_rig(rig_source)
    # Modified 2026-08-28 for Eloria Client: one garment is worn by every race,
    # so it has to clear every race.  Measuring against the reference body alone
    # left the wider silhouettes - the female hip above all - poking through the
    # shell.  The Ssarathi are left out on purpose: their digitigrade leg is not
    # a wider version of this one, it is somewhere else entirely, and the
    # runtime retarget is what carries a garment onto it.
    cast=[rig]
    for extra in sorted((args.output/"races").glob("*.glb")):
        if extra==rig_source or extra.stem.startswith("ssarathi"):
            continue
        try:
            cast.append(equipment_authoring.load_rig(extra))
        except Exception as error:  # a race still being authored must not stop a build
            print("skip garment cast member",extra.name,error)
    rig=equipment_authoring.RigSet(rig,cast[1:])
    print(f"garment cast: {len(cast)} race silhouettes")
    idle_bases=None
    if args.animation_library.is_file():
        idle_bases=equipment_authoring._idle_hand_bases(
            str(rig_source), str(args.animation_library))
    for slug,label,part,visual,kind,base,accent in EQUIPMENT:
        path=args.output/"equipment"/f"{slug}.glb"
        manifest["equipment"][slug]=build_equipment(path,slug,label,kind,base,accent,rig)|{
            "part":part,"visual":visual,"path":str(path.relative_to(repo_root))}
        print("equipment",slug,manifest["equipment"][slug])
    # The generic tier claims the legacy visual ids directly. One authored mesh
    # serves a whole material ladder; the ids differ by a runtime tint.
    manifest["genericEquipment"]={}
    for piece in equipment_authoring.GENERIC_EQUIPMENT:
        path=args.output/"equipment"/f"{piece.slug}.glb"
        info=equipment_authoring.build_equipment_piece(
            path,rig,piece.slug,piece.label,piece.kind,piece.base,piece.accent,
            finish=piece.finish)
        manifest["genericEquipment"][piece.slug]=info|{
            "part":piece.part,
            "visuals":[visual for visual,_n,_b,_a in piece.variants],
            "path":str(path.relative_to(repo_root))}
        print("generic",piece.slug,manifest["genericEquipment"][piece.slug])
    manifest["ambientCreatures"] = {}
    for slug, label, archetype, _scale, tacked in AMBIENT_CREATURES:
        path = args.output / "creatures" / f"{slug}.glb"
        record = {"id": slug, "name": label, "archetype": archetype,
                  "path": str(path.relative_to(repo_root)),
                  "generator": "eloria-assets/tools/sunmane/creatures.py",
                  "tacked": tacked, "region": "sunmane_steppe",
                  "note": AMBIENT_SOURCE_NOTE}
        if path.exists():
            record |= glb_geometry_stats(path)
        manifest["ambientCreatures"][slug] = record
    manifest["ambientCreaturesNote"] = AMBIENT_NOTE
    validation={str(path.relative_to(repo_root)):validate_glb(path) for path in args.output.rglob("*.glb")}
    if args.only=="equipment":
        # Only revalidate what this run rebuilt.  Ambient scenery GLBs are
        # authored by a different generator and are not part of this manifest's
        # validated set, so a partial rebuild must not adopt them.
        previous=manifest.get("validation",{}).get("results",{})
        validation={key:value for key,value in validation.items()
                    if key in previous or "/equipment/" in key}
        validation={**previous,**validation}
    manifest["validation"]={"files":len(validation),"results":validation}
    models = build_model_registry()
    carry_forward_ambient(args.manifest, args.models, manifest, models)
    write_json(args.manifest, manifest)
    if args.only=="all":
        write_json(args.models, models)
    write_json(args.equipment_registry, build_equipment_registry(rig, idle_bases))
    print(f"validated {len(validation)} native GLBs")


if __name__=="__main__":main()

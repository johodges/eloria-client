#!/usr/bin/env python3
"""The Nymara creature roster, keyed to the supplied concept-art sheets.

Each entry records the creature slug, display name, skeleton family, body
plan, palette, scale and the concept-art cell it was authored from, so any
model can be traced back to the artwork that defines it.

Palettes are *sampled from the artwork* by
``eloria-assets/tools/extract_concept_palettes.py`` rather than guessed by
hand, which is why they are exact triples rather than round numbers.

``sheet`` is the concept image stem; ``cell`` is (row, column) in that
sheet's 4x3 grid.  Several sheets are alternate renders of the same roster
(``47a41963``/``4dc46727`` and ``93197c59``/``1e840e1e``), and the three
Amberwood sheets share many subjects, so ``ALIAS_CELLS`` maps every duplicate
cell onto the model that already covers it.
"""
from __future__ import annotations

# slug, display name, family, plan, base rgb, accent rgb, scale, sheet, row, col
ROSTER = (
    # ---- Amethyst Barrens: crystal-grown fauna -------------------------
    ("amethyst_scorpion", "Amethyst Scorpion", "arachnid", "scorpion",
     (93, 82, 205), (52, 48, 152), 1.05, "47a41963", 0, 0),
    ("geode_scarab", "Geode Scarab", "insect", "beetle",
     (58, 71, 205), (40, 69, 143), .80, "47a41963", 0, 1),
    ("prism_drake", "Prism Drake", "quadruped", "sprawler",
     (69, 83, 151), (171, 181, 224), 1.22, "47a41963", 0, 2),
    ("shardling_swarm", "Shardling Swarm", "amorphous", "shards",
     (65, 81, 205), (43, 56, 154), .92, "47a41963", 0, 3),
    ("barrens_wisp", "Barrens Wisp", "amorphous", "wisp",
     (37, 61, 159), (135, 169, 224), .78, "47a41963", 1, 0),
    ("amethyst_golem", "Amethyst Golem", "biped", "golem",
     (78, 73, 114), (178, 175, 224), 1.55, "47a41963", 1, 1),
    ("crystalwing", "Crystalwing", "quadruped", "drake",
     (61, 66, 159), (170, 179, 224), 1.18, "47a41963", 1, 2),
    ("geode_tortoise", "Geode Tortoise", "quadruped", "chelonian",
     (106, 93, 194), (175, 180, 224), 1.10, "47a41963", 1, 3),
    ("facet_hound", "Facet Hound", "quadruped", "canid",
     (72, 75, 135), (155, 174, 224), 1.14, "47a41963", 2, 0),
    ("prism_moth", "Prism Moth", "insect", "moth",
     (61, 80, 205), (48, 58, 146), .88, "47a41963", 2, 1),
    ("lattice_spider", "Lattice Spider", "arachnid", "spider",
     (66, 67, 171), (181, 179, 224), 1.00, "47a41963", 2, 2),
    ("orrery_sentinel", "Orrery Sentinel", "biped", "construct",
     (91, 94, 139), (73, 107, 224), 1.42, "47a41963", 2, 3),

    # ---- Elemental lords: regional boss tier ---------------------------
    ("verdant_crown_king", "Verdant Crown King", "biped", "monarch",
     (51, 86, 86), (156, 222, 209), 1.72, "f1bb1663", 0, 0),
    ("tidegold_wyrm", "Tidegold Wyrm", "serpent", "wyrm",
     (67, 98, 104), (73, 191, 224), 1.85, "f1bb1663", 0, 1),
    ("rimebound_archmage", "Rimebound Archmage", "biped", "mage",
     (78, 105, 132), (148, 199, 224), 1.62, "f1bb1663", 0, 2),
    ("glacier_brute", "Glacier Brute", "biped", "brute",
     (80, 121, 155), (175, 200, 213), 1.80, "f1bb1663", 0, 3),
    ("orrery_colossus", "Orrery Colossus", "biped", "construct",
     (103, 79, 74), (198, 194, 196), 1.78, "f1bb1663", 1, 0),
    ("amethyst_sibyl", "Amethyst Sibyl", "biped", "mage",
     (83, 77, 136), (130, 131, 224), 1.58, "f1bb1663", 1, 1),
    ("crimson_duelist", "Crimson Duelist", "biped", "duelist",
     (105, 59, 69), (209, 198, 182), 1.60, "f1bb1663", 1, 2),
    ("emberwood_matron", "Emberwood Matron", "biped", "treant",
     (99, 73, 26), (224, 215, 145), 1.75, "f1bb1663", 1, 3),
    ("barrow_sovereign", "Barrow Sovereign", "biped", "knight",
     (57, 60, 61), (173, 213, 202), 1.70, "f1bb1663", 2, 0),
    ("gilded_devourer", "Gilded Devourer", "amorphous", "tentacles",
     (100, 79, 79), (224, 190, 135), 1.66, "f1bb1663", 2, 1),
    ("tidecaller_sorceress", "Tidecaller Sorceress", "biped", "mage",
     (79, 106, 101), (135, 220, 224), 1.58, "f1bb1663", 2, 2),
    ("mirefather_leviathan", "Mirefather Leviathan", "amorphous", "tentacles",
     (81, 96, 63), (208, 221, 158), 1.92, "f1bb1663", 2, 3),

    # ---- Sunmane Steppe ------------------------------------------------
    ("goldmane_aurochs", "Goldmane Aurochs", "quadruped", "bovine",
     (167, 103, 37), (224, 206, 158), 1.42, "93197c59", 0, 1),
    ("dunburrow_mole", "Dunburrow Mole", "quadruped", "mustelid",
     (133, 84, 46), (224, 167, 113), .78, "93197c59", 0, 3),
    ("plumed_crane", "Plumed Crane", "avian", "wader",
     (178, 126, 70), (224, 115, 15), 1.16, "93197c59", 1, 0),
    ("sunmane_minotaur", "Sunmane Minotaur", "biped", "brute",
     (151, 87, 21), (224, 191, 133), 1.68, "93197c59", 1, 1),
    ("stormmane_lion", "Stormmane Lion", "quadruped", "felid",
     (205, 126, 28), (122, 81, 49), 1.30, "93197c59", 1, 2),
    ("grasswing_mantis", "Grasswing Mantis", "insect", "mantis",
     (184, 147, 31), (224, 194, 38), 1.05, "93197c59", 2, 0),
    ("dust_hyena", "Dust Hyena", "quadruped", "canid",
     (162, 95, 39), (224, 147, 63), 1.08, "93197c59", 2, 1),
    ("steppe_jackrabbit", "Steppe Jackrabbit", "quadruped", "lagomorph",
     (204, 133, 58), (224, 201, 160), .70, "93197c59", 2, 2),
    ("sunmane_gryphon", "Sunmane Gryphon", "quadruped", "gryphon",
     (144, 116, 84), (224, 200, 157), 1.34, "93197c59", 2, 3),

    # ---- Crownwater ----------------------------------------------------
    ("crownwater_turtle", "Crownwater Turtle", "quadruped", "chelonian",
     (121, 115, 78), (224, 204, 154), 1.16, "bc78bfcc", 0, 0),
    ("tidefin_naga", "Tidefin Naga", "biped", "warrior",
     (117, 143, 129), (224, 159, 74), 1.44, "bc78bfcc", 0, 1),
    ("lanternwyrm", "Lanternwyrm", "serpent", "sea_serpent",
     (55, 124, 141), (224, 167, 32), 1.55, "bc78bfcc", 0, 2),
    ("crownwater_wyvern", "Crownwater Wyvern", "quadruped", "drake",
     (59, 147, 157), (224, 173, 106), 1.40, "bc78bfcc", 0, 3),
    ("cascade_golem", "Cascade Golem", "biped", "golem",
     (91, 108, 71), (204, 207, 177), 1.62, "bc78bfcc", 1, 0),
    ("tidecoil_serpent", "Tidecoil Serpent", "serpent", "sea_serpent",
     (53, 136, 205), (51, 69, 132), 1.48, "bc78bfcc", 1, 1),
    ("palecrest_crab", "Palecrest Crab", "arachnid", "crab",
     (144, 145, 111), (208, 205, 175), 1.02, "bc78bfcc", 1, 2),
    ("riverbank_ibis", "Riverbank Ibis", "avian", "wader",
     (119, 121, 106), (219, 203, 166), 1.10, "bc78bfcc", 1, 3),
    ("algae_alligator", "Algae Alligator", "quadruped", "sprawler",
     (74, 109, 70), (224, 193, 50), 1.50, "bc78bfcc", 2, 0),
    ("springfly_sprite", "Springfly Sprite", "amorphous", "sprite",
     (62, 147, 205), (49, 106, 145), .74, "bc78bfcc", 2, 1),
    ("gilded_water_lion", "Gilded Water Lion", "quadruped", "felid",
     (89, 132, 116), (12, 156, 224), 1.36, "bc78bfcc", 2, 2),
    ("medusa_tidepriest", "Medusa Tidepriest", "amorphous", "tentacles",
     (61, 104, 97), (17, 171, 224), 1.40, "bc78bfcc", 2, 3),

    # ---- Westhaven -----------------------------------------------------
    ("courier_otter", "Courier Otter", "quadruped", "mustelid",
     (110, 85, 71), (220, 199, 169), .82, "4cf4bb0e", 0, 0),
    ("message_swallow", "Message Swallow", "avian", "songbird",
     (95, 85, 88), (224, 199, 166), .52, "4cf4bb0e", 0, 1),
    ("harborshell_crab", "Harborshell Crab", "arachnid", "crab",
     (106, 94, 64), (224, 206, 151), 1.00, "4cf4bb0e", 0, 2),
    ("brassband_pike", "Brassband Pike", "fish", "pike",
     (115, 121, 82), (224, 200, 141), 1.18, "4cf4bb0e", 0, 3),
    ("reedhat_fisher", "Reedhat Fisher", "biped", "warrior",
     (102, 76, 58), (224, 192, 154), 1.42, "4cf4bb0e", 1, 0),
    ("ratcatcher_tough", "Ratcatcher Tough", "biped", "warrior",
     (93, 71, 56), (209, 203, 175), 1.40, "4cf4bb0e", 1, 1),
    ("verdigris_beetle", "Verdigris Beetle", "insect", "beetle",
     (113, 93, 47), (205, 221, 163), .86, "4cf4bb0e", 1, 2),
    ("lanternwake_sprite", "Lanternwake Sprite", "amorphous", "sprite",
     (70, 186, 166), (117, 96, 39), .92, "4cf4bb0e", 1, 3),
    ("millstone_golem", "Millstone Golem", "biped", "golem",
     (122, 107, 73), (224, 201, 156), 1.66, "4cf4bb0e", 2, 0),
    ("drowned_dockhand", "Drowned Dockhand", "biped", "revenant",
     (82, 89, 82), (60, 211, 224), 1.44, "4cf4bb0e", 2, 1),
    ("sluice_elemental", "Sluice Elemental", "amorphous", "vortex",
     (42, 165, 194), (84, 205, 224), 1.24, "4cf4bb0e", 2, 2),
    ("waterwheel_golem", "Waterwheel Golem", "biped", "construct",
     (107, 112, 80), (61, 201, 224), 1.70, "4cf4bb0e", 2, 3),

    # ---- Drowned Crown coast -------------------------------------------
    ("harbor_gull", "Harbor Gull", "avian", "seabird",
     (155, 148, 162), (196, 196, 196), .70, "5b11c39c", 0, 0),
    ("rockshell_crab", "Rockshell Crab", "arachnid", "crab",
     (138, 73, 39), (224, 182, 136), .94, "5b11c39c", 0, 1),
    ("harbor_seal", "Harbor Seal", "quadruped", "pinniped",
     (119, 122, 124), (199, 197, 192), 1.16, "5b11c39c", 0, 2),
    ("kelpback_turtle", "Kelpback Turtle", "quadruped", "chelonian",
     (103, 102, 86), (224, 202, 156), 1.24, "5b11c39c", 0, 3),
    ("bluewater_marlin", "Bluewater Marlin", "fish", "billfish",
     (90, 105, 118), (224, 179, 61), 1.44, "5b11c39c", 1, 0),
    ("saltmarsh_crocodile", "Saltmarsh Crocodile", "quadruped", "sprawler",
     (107, 95, 72), (214, 201, 173), 1.52, "5b11c39c", 1, 1),
    ("bilge_rat", "Bilge Rat", "quadruped", "mustelid",
     (113, 83, 70), (224, 172, 151), .80, "5b11c39c", 1, 2),
    ("spinefin_eel", "Spinefin Eel", "serpent", "eel",
     (74, 88, 103), (224, 136, 70), 1.30, "5b11c39c", 1, 3),
    ("barnacle_troll", "Barnacle Troll", "biped", "brute",
     (86, 89, 72), (200, 202, 186), 1.72, "5b11c39c", 2, 0),
    ("drowned_captain", "Drowned Captain", "biped", "revenant",
     (76, 73, 69), (209, 199, 180), 1.50, "5b11c39c", 2, 1),
    ("glowmantle_ray", "Glowmantle Ray", "fish", "ray",
     (68, 121, 142), (9, 194, 224), 1.36, "5b11c39c", 2, 2),
    ("deepplate_coelacanth", "Deepplate Coelacanth", "fish", "armored",
     (59, 99, 125), (12, 178, 224), 1.30, "5b11c39c", 2, 3),

    # ---- Grey Moors ----------------------------------------------------
    ("moor_pony", "Moor Pony", "quadruped", "equine",
     (91, 74, 58), (215, 195, 178), 1.10, "2dd667c5", 0, 0),
    ("moorhorn_ram", "Moorhorn Ram", "quadruped", "cervid",
     (67, 59, 48), (224, 198, 145), 1.16, "2dd667c5", 0, 1),
    ("moor_heron", "Moor Heron", "avian", "wader",
     (92, 83, 79), (203, 197, 189), 1.12, "2dd667c5", 0, 2),
    ("cairnback_tortoise", "Cairnback Tortoise", "quadruped", "chelonian",
     (94, 80, 44), (221, 203, 164), 1.14, "2dd667c5", 0, 3),
    ("moorfell_wolf", "Moorfell Wolf", "quadruped", "canid",
     (71, 59, 44), (224, 183, 128), 1.20, "2dd667c5", 1, 0),
    ("reedmask_stalker", "Reedmask Stalker", "biped", "warrior",
     (89, 72, 40), (224, 179, 121), 1.46, "2dd667c5", 1, 1),
    ("moorlight_wisp", "Moorlight Wisp", "amorphous", "wisp",
     (113, 174, 178), (91, 134, 148), .84, "2dd667c5", 1, 2),
    ("barrow_knight", "Barrow Knight", "biped", "knight",
     (76, 98, 75), (129, 224, 205), 1.52, "2dd667c5", 1, 3),
    ("cairn_golem", "Cairn Golem", "biped", "golem",
     (84, 83, 51), (193, 205, 190), 1.60, "2dd667c5", 2, 0),
    ("lantern_wraith", "Lantern Wraith", "biped", "revenant",
     (64, 88, 75), (120, 224, 215), 1.48, "2dd667c5", 2, 1),
    ("spectral_moor_stag", "Spectral Moor Stag", "quadruped", "cervid",
     (83, 154, 150), (118, 224, 215), 1.30, "2dd667c5", 2, 2),
    ("barrow_king", "Barrow King", "biped", "monarch",
     (76, 93, 86), (152, 224, 208), 1.66, "2dd667c5", 2, 3),

    # ---- Mirrorhold ----------------------------------------------------
    ("tidelance_construct", "Tidelance Construct", "amorphous", "vortex",
     (97, 124, 79), (79, 217, 224), 1.16, "53a67c51", 0, 0),
    ("reefplate_golem", "Reefplate Golem", "quadruped", "ursine",
     (131, 129, 104), (224, 197, 166), 1.48, "53a67c51", 0, 1),
    ("mirrorhold_wheelwarden", "Mirrorhold Wheelwarden", "biped", "construct",
     (98, 101, 68), (147, 218, 223), 1.68, "53a67c51", 0, 2),
    ("verdigris_warden", "Verdigris Warden", "biped", "construct",
     (74, 115, 94), (190, 217, 181), 1.56, "53a67c51", 0, 3),
    ("palewater_wyrm", "Palewater Wyrm", "serpent", "sea_serpent",
     (72, 187, 205), (36, 96, 120), 1.52, "53a67c51", 1, 0),
    ("mirrorwing_swarm", "Mirrorwing Swarm", "amorphous", "shards",
     (89, 175, 201), (78, 124, 144), 1.02, "53a67c51", 1, 1),
    ("shattered_sentinel", "Shattered Sentinel", "biped", "golem",
     (95, 106, 81), (78, 192, 224), 1.50, "53a67c51", 1, 2),
    ("mirrorhold_oracle", "Mirrorhold Oracle", "biped", "mage",
     (58, 139, 165), (55, 185, 224), 1.52, "53a67c51", 1, 3),
    ("tideguard_vanguard", "Tideguard Vanguard", "biped", "knight",
     (69, 108, 101), (46, 185, 224), 1.54, "53a67c51", 2, 0),
    ("mirrorhold_siren", "Mirrorhold Siren", "serpent", "naga",
     (102, 130, 127), (213, 204, 172), 1.44, "53a67c51", 2, 1),
    ("shardbound_archivist", "Shardbound Archivist", "amorphous", "shards",
     (77, 157, 171), (85, 211, 224), 1.30, "53a67c51", 2, 2),
    ("mirrorhold_loremaster", "Mirrorhold Loremaster", "biped", "mage",
     (79, 130, 125), (59, 192, 224), 1.64, "53a67c51", 2, 3),

    # ---- Manymouth Delta -----------------------------------------------
    ("mudflat_crab", "Mudflat Crab", "arachnid", "crab",
     (103, 74, 39), (215, 204, 169), .96, "4bbc1f8e", 0, 0),
    ("delta_heron", "Delta Heron", "avian", "wader",
     (105, 85, 55), (216, 200, 173), 1.12, "4bbc1f8e", 0, 1),
    ("voltfin_eel", "Voltfin Eel", "serpent", "eel",
     (59, 80, 72), (121, 220, 224), 1.26, "4bbc1f8e", 1, 1),
    ("reed_stalker", "Reed Stalker", "quadruped", "sprawler",
     (89, 73, 38), (224, 197, 139), 1.10, "4bbc1f8e", 1, 2),
    ("mangrove_turtle", "Mangrove Turtle", "quadruped", "chelonian",
     (93, 86, 39), (224, 197, 151), 1.30, "4bbc1f8e", 1, 3),
    ("bog_warden", "Bog Warden", "biped", "construct",
     (78, 86, 56), (210, 210, 167), 1.62, "4bbc1f8e", 2, 0),
    ("frogspear_warrior", "Frogspear Warrior", "biped", "warrior",
     (85, 72, 49), (224, 202, 149), 1.34, "4bbc1f8e", 2, 1),
    ("reed_drake", "Reed Drake", "quadruped", "sprawler",
     (89, 76, 40), (224, 195, 148), 1.24, "4bbc1f8e", 2, 2),
    ("manymouth_hydra", "Manymouth Hydra", "serpent", "hydra",
     (83, 88, 54), (224, 169, 83), 1.72, "4bbc1f8e", 2, 3),

    # ---- Verdant Stair -------------------------------------------------
    ("emerald_basilisk", "Emerald Basilisk", "quadruped", "sprawler",
     (85, 113, 52), (224, 120, 13), .96, "66616a1d", 0, 0),
    ("leaf_mantis", "Leaf Mantis", "insect", "mantis",
     (127, 125, 21), (161, 224, 78), 1.02, "66616a1d", 0, 1),
    ("dartback_treefrog", "Dartback Tree Frog", "quadruped", "anuran",
     (81, 148, 51), (224, 73, 8), .62, "66616a1d", 0, 2),
    ("plumefire_hummingbird", "Plumefire Hummingbird", "avian", "songbird",
     (205, 101, 76), (224, 137, 63), .48, "66616a1d", 0, 3),
    ("vinecoil_snake", "Vinecoil Snake", "serpent", "snake",
     (82, 94, 37), (224, 126, 10), 1.16, "66616a1d", 1, 0),
    ("canopy_lynx", "Canopy Lynx", "quadruped", "felid",
     (119, 93, 50), (224, 173, 88), 1.08, "66616a1d", 1, 1),
    ("mossback_anteater", "Mossback Anteater", "quadruped", "ursine",
     (112, 88, 38), (224, 174, 91), 1.26, "66616a1d", 1, 2),
    ("bloomtail_axolotl", "Bloomtail Axolotl", "fish", "axolotl",
     (21, 103, 179), (8, 185, 224), .92, "66616a1d", 1, 3),
    ("canopy_gorilla", "Canopy Gorilla", "biped", "primate",
     (94, 64, 38), (224, 156, 78), 1.52, "66616a1d", 2, 0),
    ("vine_treant", "Vine Treant", "biped", "treant",
     (93, 86, 29), (224, 190, 68), 1.66, "66616a1d", 2, 1),
    ("verdant_naiad", "Verdant Naiad", "amorphous", "vortex",
     (50, 197, 194), (190, 224, 74), 1.28, "66616a1d", 2, 2),
    ("verdant_stair_dragon", "Verdant Stair Dragon", "quadruped", "drake",
     (66, 139, 83), (221, 224, 67), 1.62, "66616a1d", 2, 3),

    # ---- Whitehorn Range -----------------------------------------------
    ("rime_harpy", "Rime Harpy", "avian", "harpy",
     (87, 144, 205), (24, 110, 224), 1.28, "15c7630b", 1, 0),
    ("glacier_golem", "Glacier Golem", "biped", "golem",
     (81, 133, 177), (42, 76, 134), 1.62, "15c7630b", 1, 1),
    ("whitehorn_yak", "Whitehorn Yak", "quadruped", "bovine",
     (148, 152, 165), (68, 76, 108), 1.40, "15c7630b", 1, 3),
    ("rimeshell_crab", "Rimeshell Crab", "arachnid", "crab",
     (8, 107, 205), (8, 63, 185), 1.06, "15c7630b", 2, 0),
    ("hoarfrost_serpent", "Hoarfrost Serpent", "serpent", "snake",
     (45, 133, 205), (12, 102, 224), 1.34, "15c7630b", 2, 1),
    ("glacier_eagle", "Glacier Eagle", "avian", "raptor",
     (59, 148, 205), (38, 72, 142), 1.14, "15c7630b", 2, 2),
    ("frostplate_knight", "Frostplate Knight", "biped", "knight",
     (74, 118, 160), (55, 160, 224), 1.58, "15c7630b", 2, 3),

    # ---- Amberwood -----------------------------------------------------
    ("emberwing_moth", "Emberwing Moth", "insect", "moth",
     (205, 89, 18), (224, 151, 34), .92, "a5ba7c19", 0, 3),
    ("amberwood_owl", "Amberwood Owl", "avian", "owl",
     (120, 71, 31), (224, 167, 101), .96, "a5ba7c19", 1, 0),
    ("bramble_wolf", "Bramble Wolf", "quadruped", "canid",
     (108, 68, 44), (224, 153, 98), 1.18, "a5ba7c19", 1, 1),
    ("moss_troll", "Moss Troll", "biped", "brute",
     (120, 83, 24), (224, 173, 100), 1.64, "a5ba7c19", 1, 2),
    ("amberwood_treant", "Amberwood Treant", "biped", "treant",
     (120, 74, 23), (224, 168, 93), 1.72, "a5ba7c19", 1, 3),
    ("ivy_hound", "Ivy Hound", "quadruped", "canid",
     (109, 87, 60), (216, 195, 178), 1.10, "a5ba7c19", 2, 0),
    ("thorn_revenant", "Thorn Revenant", "biped", "revenant",
     (72, 67, 69), (156, 210, 222), 1.46, "a5ba7c19", 2, 1),
    ("spectral_highwayman", "Spectral Highwayman", "biped", "revenant",
     (78, 92, 104), (136, 195, 224), 1.50, "a5ba7c19", 2, 2),
    ("lantern_stag", "Lantern Stag", "quadruped", "cervid",
     (98, 57, 38), (224, 132, 41), 1.40, "a5ba7c19", 2, 3),
    ("moss_badger", "Moss Badger", "quadruped", "mustelid",
     (115, 90, 47), (223, 194, 171), .92, "c09f0eed", 1, 0),
    ("bramble_stag", "Bramble Stag", "quadruped", "cervid",
     (117, 66, 33), (224, 174, 119), 1.32, "c09f0eed", 1, 1),
    ("leafling_sprite", "Leafling Sprite", "biped", "treant",
     (122, 80, 13), (224, 175, 52), .72, "c09f0eed", 1, 2),
    ("ember_wisp", "Ember Wisp", "amorphous", "wisp",
     (205, 103, 13), (224, 208, 119), .86, "c09f0eed", 2, 0),
    ("ivy_stone_golem", "Ivy Stone Golem", "biped", "golem",
     (90, 90, 51), (224, 191, 131), 1.64, "c09f0eed", 2, 2),
    ("amberwood_dryad", "Amberwood Dryad", "biped", "mage",
     (103, 62, 46), (224, 170, 122), 1.56, "c09f0eed", 2, 3),
    ("moss_bear", "Moss Bear", "quadruped", "ursine",
     (109, 86, 41), (224, 176, 59), 1.36, "4250fde7", 0, 3),
    ("amberwood_scarecrow", "Amberwood Scarecrow", "biped", "revenant",
     (142, 80, 30), (213, 198, 177), 1.42, "4250fde7", 1, 3),
    ("amberwood_ghost_knight", "Amberwood Ghost Knight", "biped", "knight",
     (98, 104, 79), (188, 207, 193), 1.52, "4250fde7", 2, 1),
)

# Concept cells already represented by an existing or listed model.
ALIAS_CELLS = {
    # Alternate renders of the Amethyst Barrens sheet.
    **{("4dc46727", r, c): slug for (slug, _n, _f, _p, _b, _a, _s, sheet, r, c)
       in ROSTER if sheet == "47a41963"},
    # Alternate renders of the Sunmane Steppe sheet.
    **{("1e840e1e", r, c): slug for (slug, _n, _f, _p, _b, _a, _s, sheet, r, c)
       in ROSTER if sheet == "93197c59"},
    # Cells covered by creatures built in the previous pass.
    ("93197c59", 0, 0): "sunmane_steppe_horse",
    ("93197c59", 0, 2): "emberfox",
    ("93197c59", 1, 3): "desert_tortoise",
    ("1e840e1e", 0, 0): "sunmane_steppe_horse",
    ("1e840e1e", 0, 2): "emberfox",
    ("1e840e1e", 1, 3): "desert_tortoise",
    ("15c7630b", 0, 0): "mountain_goat",
    ("15c7630b", 0, 1): "snow_hare",
    ("15c7630b", 0, 2): "frost_maw",
    ("15c7630b", 0, 3): "ice_bear",
    ("15c7630b", 1, 2): "frost_tiger",
    ("4bbc1f8e", 0, 2): "miretoad",
    ("4bbc1f8e", 0, 3): "giant_komodo",
    ("4bbc1f8e", 1, 0): "giant_crocodile",
    ("a5ba7c19", 0, 0): "elk",
    ("a5ba7c19", 0, 1): "mossback_boar",
    ("a5ba7c19", 0, 2): "red_fox",
    # Amberwood sheets repeat one another's subjects.
    ("c09f0eed", 0, 0): "elk",
    ("c09f0eed", 0, 1): "mossback_boar",
    ("c09f0eed", 0, 2): "red_fox",
    ("c09f0eed", 0, 3): "amberwood_owl",
    ("c09f0eed", 1, 3): "bramble_wolf",
    ("c09f0eed", 2, 1): "amberwood_ghost_knight",
    ("4250fde7", 0, 0): "elk",
    ("4250fde7", 0, 1): "mossback_boar",
    ("4250fde7", 0, 2): "red_fox",
    ("4250fde7", 1, 0): "amberwood_owl",
    ("4250fde7", 1, 1): "bramble_wolf",
    ("4250fde7", 1, 2): "moss_troll",
    ("4250fde7", 2, 0): "amberwood_treant",
    ("4250fde7", 2, 2): "ivy_hound",
    ("4250fde7", 2, 3): "emberwing_moth",
    # Westhaven otter and coastal fauna already have a first-pass model.
    ("4cf4bb0e", 0, 0): "courier_otter",
}

SHEET_LOCALES = {
    "47a41963": "amethyst_barrens", "4dc46727": "amethyst_barrens",
    "f1bb1663": "elemental_lords",
    "93197c59": "sunmane_steppe", "1e840e1e": "sunmane_steppe",
    "bc78bfcc": "crownwater", "4cf4bb0e": "westhaven",
    "5b11c39c": "drowned_crown", "2dd667c5": "grey_moors",
    "53a67c51": "mirrorhold", "4bbc1f8e": "manymouth_delta",
    "66616a1d": "verdant_stair", "15c7630b": "whitehorn_range",
    "a5ba7c19": "amberwood", "c09f0eed": "amberwood", "4250fde7": "amberwood",
}


# How much each creature's albedo has to be lifted for it to sit at the same
# value, relative to the rest of the library, that it sits at in the artwork.
# The sampled hues are accurate -- the median hue error against the concept
# figures is about two degrees -- but the values were compressed: rendered and
# measured, a whitehorn yak and a coastal gull, which the art paints nearly
# white, came out within a few points of a black iron death knight.  Range is
# what tells one silhouette from another in a lineup, so it is restored here.
# Measured by ``concept_value_gains.py --table``; gains only ever lift, since
# the creatures the art paints dark were already right.
VALUE_GAIN = {
    "amethyst_scorpion": 1.21,          # art  83.4, model  52.5
    "geode_scarab": 1.47,               # art  94.2, model  56.1
    "shardling_swarm": 1.24,            # art  89.5, model  55.8
    "geode_tortoise": 1.27,             # art  86.5, model  53.4
    "prism_moth": 1.55,                 # art  90.0, model  50.5
    "tidegold_wyrm": 1.04,              # art  74.9, model  50.2
    "rimebound_archmage": 1.38,         # art  89.0, model  52.9
    "glacier_brute": 1.15,              # art  97.8, model  62.1
    "amethyst_sibyl": 1.06,             # art  68.1, model  44.4
    "tidecaller_sorceress": 1.21,       # art  81.7, model  51.0
    "goldmane_aurochs": 1.55,           # art  97.1, model  53.9
    "plumed_crane": 1.55,               # art 105.1, model  53.8
    "sunmane_minotaur": 1.05,           # art  79.4, model  53.0
    "stormmane_lion": 1.55,             # art 101.0, model  52.5
    "grasswing_mantis": 1.55,           # art 111.8, model  59.3
    "dust_hyena": 1.45,                 # art  87.2, model  50.0
    "steppe_jackrabbit": 1.55,          # art 115.5, model  64.1
    "sunmane_gryphon": 1.55,            # art  98.1, model  54.5
    "crownwater_turtle": 1.44,          # art  92.7, model  53.6
    "tidefin_naga": 1.55,               # art 109.9, model  56.6
    "lanternwyrm": 1.31,                # art  85.2, model  50.9
    "crownwater_wyvern": 1.55,          # art 105.6, model  55.6
    "cascade_golem": 1.06,              # art  84.3, model  57.5
    "tidecoil_serpent": 1.55,           # art 104.5, model  51.9
    "palecrest_crab": 1.55,             # art 118.9, model  66.4
    "riverbank_ibis": 1.55,             # art 105.9, model  54.6
    "algae_alligator": 1.23,            # art  82.5, model  50.5
    "springfly_sprite": 1.55,           # art 128.9, model  72.7
    "gilded_water_lion": 1.55,          # art  99.0, model  52.7
    "courier_otter": 1.12,              # art  77.1, model  49.8
    "message_swallow": 1.21,            # art  79.9, model  50.2
    "brassband_pike": 1.55,             # art  92.2, model  50.5
    "verdigris_beetle": 1.06,           # art  84.0, model  55.5
    "drowned_dockhand": 1.08,           # art  70.4, model  45.4
    "sluice_elemental": 1.22,           # art 112.1, model  70.3
    "waterwheel_golem": 1.24,           # art  93.3, model  61.0
    "harbor_gull": 1.55,                # art 128.5, model  64.3
    "harbor_seal": 1.55,                # art  98.1, model  55.4
    "kelpback_turtle": 1.29,            # art  84.6, model  51.2
    "bluewater_marlin": 1.44,           # art  87.1, model  49.9
    "saltmarsh_crocodile": 1.12,        # art  78.3, model  50.3
    "glowmantle_ray": 1.40,             # art  92.2, model  54.1
    "deepplate_coelacanth": 1.12,       # art  74.2, model  47.8
    "moor_heron": 1.14,                 # art  77.9, model  49.7
    "moorlight_wisp": 1.55,             # art 144.0, model  78.7
    "spectral_moor_stag": 1.49,         # art 101.8, model  58.5
    "tidelance_construct": 1.23,        # art  96.4, model  59.8
    "reefplate_golem": 1.55,            # art 106.0, model  60.3
    "verdigris_warden": 1.06,           # art  84.4, model  57.8
    "palewater_wyrm": 1.55,             # art 121.1, model  53.0
    "mirrorwing_swarm": 1.55,           # art 144.3, model  62.7
    "shattered_sentinel": 1.07,         # art  85.8, model  57.7
    "mirrorhold_oracle": 1.50,          # art  96.6, model  55.6
    "tideguard_vanguard": 1.15,         # art  82.1, model  52.4
    "mirrorhold_siren": 1.55,           # art  99.5, model  52.5
    "mirrorhold_loremaster": 1.50,      # art  97.0, model  57.1
    "delta_heron": 1.02,                # art  74.5, model  50.0
    "emerald_basilisk": 1.34,           # art  84.7, model  50.0
    "leaf_mantis": 1.45,                # art  96.1, model  55.0
    "dartback_treefrog": 1.55,          # art  96.7, model  52.9
    "plumefire_hummingbird": 1.55,      # art 102.0, model  55.6
    "vinecoil_snake": 1.02,             # art  74.7, model  50.2
    "canopy_lynx": 1.27,                # art  80.5, model  49.3
    "mossback_anteater": 1.09,          # art  74.5, model  48.9
    "bloomtail_axolotl": 1.32,          # art  82.6, model  49.3
    "verdant_stair_dragon": 1.55,       # art  99.1, model  53.5
    "rime_harpy": 1.55,                 # art 123.9, model  58.8
    "glacier_golem": 1.29,              # art 107.4, model  67.3
    "whitehorn_yak": 1.55,              # art 128.1, model  61.8
    "rimeshell_crab": 1.39,             # art  93.5, model  57.0
    "hoarfrost_serpent": 1.55,          # art 133.2, model  52.1
    "glacier_eagle": 1.55,              # art 114.0, model  59.2
    "frostplate_knight": 1.23,          # art  93.7, model  58.0
    "emberwing_moth": 1.38,             # art  88.9, model  53.0
    "ivy_hound": 1.07,                  # art  74.8, model  49.4
    "spectral_highwayman": 1.13,        # art  72.0, model  46.8
    "moss_bear": 1.13,                  # art  74.9, model  48.9
    "amberwood_ghost_knight": 1.20,     # art  88.7, model  56.0
}


# The colour of the brightest lit feature on each concept figure: the ember in
# a treant's chest, the light inside a geode carapace, the centre of a wisp.
# Measured by ``concept_growth_tints.py --core``.  Used for the MAT_CORE
# material, which is why a treant's heart is amber and a barrens wisp's is
# blue rather than both being a generic white glow.
CORE_TINT = {
    "amethyst_scorpion": (125, 210, 248),
    "geode_scarab": (127, 242, 252),
    "prism_drake": (130, 186, 247),
    "shardling_swarm": (127, 207, 250),
    "barrens_wisp": (85, 110, 215),
    "amethyst_golem": (138, 150, 237),
    "crystalwing": (130, 162, 244),
    "geode_tortoise": (128, 221, 233),
    "facet_hound": (122, 159, 239),
    "prism_moth": (126, 207, 251),
    "lattice_spider": (140, 177, 248),
    "orrery_sentinel": (129, 200, 229),
    "verdant_crown_king": (99, 155, 144),
    "tidegold_wyrm": (98, 170, 183),
    "rimebound_archmage": (115, 186, 218),
    "glacier_brute": (131, 204, 229),
    "orrery_colossus": (164, 147, 126),
    "amethyst_sibyl": (117, 117, 197),
    "crimson_duelist": (140, 99, 73),
    "emberwood_matron": (155, 121, 55),
    "barrow_sovereign": (62, 126, 118),
    "gilded_devourer": (176, 144, 92),
    "tidecaller_sorceress": (91, 165, 174),
    "mirefather_leviathan": (119, 153, 105),
    "goldmane_aurochs": (245, 208, 139),
    "dunburrow_mole": (195, 140, 89),
    "plumed_crane": (243, 185, 101),
    "sunmane_minotaur": (220, 168, 88),
    "stormmane_lion": (243, 181, 75),
    "grasswing_mantis": (232, 213, 79),
    "dust_hyena": (233, 162, 83),
    "steppe_jackrabbit": (235, 195, 119),
    "sunmane_gryphon": (236, 188, 108),
    "crownwater_turtle": (227, 185, 106),
    "tidefin_naga": (232, 195, 116),
    "lanternwyrm": (210, 193, 90),
    "crownwater_wyvern": (201, 198, 149),
    "cascade_golem": (199, 187, 116),
    "tidecoil_serpent": (174, 208, 177),
    "palecrest_crab": (241, 222, 138),
    "riverbank_ibis": (249, 221, 131),
    "algae_alligator": (190, 172, 82),
    "springfly_sprite": (193, 216, 179),
    "gilded_water_lion": (181, 204, 166),
    "medusa_tidepriest": (171, 180, 121),
    "courier_otter": (205, 161, 104),
    "message_swallow": (199, 155, 94),
    "harborshell_crab": (189, 145, 81),
    "brassband_pike": (139, 171, 142),
    "reedhat_fisher": (192, 141, 84),
    "ratcatcher_tough": (126, 119, 83),
    "verdigris_beetle": (122, 178, 162),
    "lanternwake_sprite": (101, 201, 198),
    "millstone_golem": (169, 176, 132),
    "drowned_dockhand": (72, 164, 168),
    "sluice_elemental": (89, 209, 227),
    "waterwheel_golem": (130, 214, 211),
    "rockshell_crab": (200, 144, 81),
    "kelpback_turtle": (187, 154, 97),
    "bluewater_marlin": (181, 169, 99),
    "saltmarsh_crocodile": (170, 148, 87),
    "bilge_rat": (170, 123, 92),
    "spinefin_eel": (123, 153, 138),
    "barnacle_troll": (159, 141, 75),
    "drowned_captain": (144, 122, 81),
    "glowmantle_ray": (46, 208, 229),
    "deepplate_coelacanth": (62, 154, 182),
    "moor_pony": (162, 137, 84),
    "moorhorn_ram": (119, 103, 58),
    "moor_heron": (206, 169, 114),
    "cairnback_tortoise": (146, 127, 65),
    "moorfell_wolf": (124, 101, 57),
    "reedmask_stalker": (147, 119, 77),
    "moorlight_wisp": (118, 237, 226),
    "barrow_knight": (99, 183, 170),
    "cairn_golem": (138, 144, 93),
    "lantern_wraith": (89, 175, 168),
    "spectral_moor_stag": (114, 207, 199),
    "barrow_king": (97, 171, 163),
    "tidelance_construct": (107, 216, 214),
    "mirrorhold_wheelwarden": (147, 172, 151),
    "verdigris_warden": (102, 176, 179),
    "palewater_wyrm": (118, 206, 209),
    "mirrorwing_swarm": (134, 224, 225),
    "shattered_sentinel": (98, 193, 204),
    "mirrorhold_oracle": (90, 188, 207),
    "tideguard_vanguard": (89, 180, 190),
    "mirrorhold_siren": (138, 180, 159),
    "shardbound_archivist": (99, 220, 231),
    "mirrorhold_loremaster": (108, 204, 210),
    "mudflat_crab": (191, 146, 84),
    "delta_heron": (201, 162, 98),
    "voltfin_eel": (86, 157, 149),
    "reed_stalker": (170, 138, 73),
    "mangrove_turtle": (161, 141, 68),
    "bog_warden": (143, 152, 112),
    "frogspear_warrior": (168, 131, 79),
    "reed_drake": (159, 135, 79),
    "manymouth_hydra": (155, 152, 101),
    "emerald_basilisk": (142, 172, 76),
    "leaf_mantis": (151, 193, 72),
    "dartback_treefrog": (138, 194, 59),
    "plumefire_hummingbird": (240, 176, 80),
    "vinecoil_snake": (174, 158, 53),
    "canopy_lynx": (202, 154, 73),
    "mossback_anteater": (167, 147, 76),
    "bloomtail_axolotl": (44, 203, 226),
    "canopy_gorilla": (167, 125, 69),
    "vine_treant": (158, 146, 56),
    "verdant_naiad": (115, 220, 231),
    "verdant_stair_dragon": (152, 197, 89),
    "glacier_golem": (127, 239, 252),
    "rimeshell_crab": (103, 224, 245),
    "hoarfrost_serpent": (142, 236, 252),
    "glacier_eagle": (172, 240, 213),
    "frostplate_knight": (138, 203, 209),
    "emberwing_moth": (240, 164, 44),
    "amberwood_owl": (170, 125, 71),
    "bramble_wolf": (161, 114, 79),
    "moss_troll": (173, 135, 65),
    "amberwood_treant": (169, 124, 63),
    "ivy_hound": (160, 141, 86),
    "thorn_revenant": (90, 118, 124),
    "spectral_highwayman": (107, 148, 164),
    "lantern_stag": (161, 104, 55),
    "moss_badger": (180, 154, 64),
    "bramble_stag": (161, 118, 71),
    "leafling_sprite": (162, 123, 44),
    "ember_wisp": (248, 204, 84),
    "ivy_stone_golem": (155, 134, 69),
    "amberwood_dryad": (170, 118, 78),
    "moss_bear": (223, 179, 62),
    "amberwood_scarecrow": (232, 165, 67),
    "amberwood_ghost_knight": (225, 192, 95),
    "elk": (186, 119, 83),
    "emberfox": (241, 176, 128),
    "frost_maw": (141, 238, 252),
    "frost_tiger": (128, 228, 251),
    "giant_crocodile": (170, 150, 80),
    "giant_komodo": (178, 154, 79),
    "giant_tortoise": (232, 183, 108),
    "horse": (237, 172, 88),
    "miretoad": (213, 174, 91),
    "mossback_boar": (163, 120, 78),
    "red_fox": (238, 186, 98),
}


# What colour that growth actually is in the artwork, measured by
# ``eloria-assets/tools/concept_growth_tints.py`` from the cut concept figures.
# Deriving it from the kind alone made every leaf green, which is right for the
# Verdant Stair and wrong for the Amberwood -- an autumn wood whose foliage
# measures amber -- and badly wrong for the thornwood dryad, whose canopy is
# crimson.  Only vegetation is listed: mineral crusts already take the
# creature's own palette.
GROWTH_TINT = {
    "algae_alligator": (153, 129, 50),              # 45% of the ink
    "amberwood_dryad": (127, 73, 50),               # 72% of the ink
    "amberwood_owl": (127, 79, 44),                 # 68% of the ink
    "amberwood_scarecrow": (143, 59, 12),           # 69% of the ink
    "amberwood_treant": (127, 92, 41),              # 50% of the ink
    # barrow_king: dominant hue (78, 147, 141) is not foliage
    # barrow_knight: dominant hue (81, 149, 137) is not foliage
    # bog_lurker: no figure
    "bog_warden": (129, 109, 71),                   # 54% of the ink
    "bramble_stag": (122, 71, 44),                  # 77% of the ink
    "bramble_wolf": (123, 82, 58),                  # 92% of the ink
    "cairn_golem": (113, 100, 50),                  # 75% of the ink
    "canopy_gorilla": (135, 82, 55),                # 60% of the ink
    "drowned_captain": (113, 77, 56),               # 39% of the ink
    "elk": (143, 71, 46),                           # 100% of the ink
    "emerald_basilisk": (112, 134, 40),             # 27% of the ink
    "frogspear_warrior": (132, 104, 60),            # 52% of the ink
    "giant_crocodile": (127, 103, 54),              # 59% of the ink
    "giant_komodo": (135, 114, 57),                 # 88% of the ink
    "ivy_hound": (112, 96, 52),                     # 73% of the ink
    "ivy_stone_golem": (123, 105, 61),              # 49% of the ink
    "kelpback_turtle": (132, 111, 64),              # 62% of the ink
    "leafling_sprite": (120, 92, 22),               # 58% of the ink
    "mangrove_turtle": (129, 107, 59),              # 45% of the ink
    "manymouth_hydra": (136, 113, 58),              # 36% of the ink
    "millstone_golem": (133, 110, 68),              # 73% of the ink
    "mirefather_leviathan": (126, 110, 52),         # 38% of the ink
    "miretoad": (150, 115, 46),                     # 56% of the ink
    "moorfell_wolf": (115, 95, 54),                 # 78% of the ink
    "moorhorn_ram": (117, 100, 57),                 # 78% of the ink
    "moss_badger": (128, 109, 45),                  # 64% of the ink
    "moss_bear": (159, 122, 35),                    # 77% of the ink
    "moss_troll": (127, 97, 36),                    # 68% of the ink
    "mossback_anteater": (134, 109, 44),            # 46% of the ink
    "mossback_boar": (126, 80, 59),                 # 74% of the ink
    "red_fox": (186, 121, 38),                      # 89% of the ink
    "reed_drake": (126, 103, 58),                   # 64% of the ink
    "reed_stalker": (134, 104, 49),                 # 89% of the ink
    "saltmarsh_crocodile": (125, 107, 61),          # 81% of the ink
    "sunmane_gryphon": (170, 122, 62),              # 76% of the ink
    # thorn_revenant: dominant hue (63, 107, 122) is not foliage
    # verdant_stair_dragon: dominant hue (29, 122, 95) is not foliage
    "vine_treant": (133, 104, 42),                  # 42% of the ink
    "waterwheel_golem": (143, 117, 67),             # 45% of the ink
}


# What the concept art shows growing on each creature.  This is most of what
# breaks up a silhouette: a clean swept tube reads as a balloon animal however
# good its proportions are.  (kind, count, size) per entry.
GROWTH = {
    # Amethyst Barrens: crystal erupting through everything
    "amethyst_scorpion": [("crystal", 12, 1.15)],
    "geode_scarab": [("crystal", 9, 1.0)],
    "prism_drake": [("crystal", 13, 1.05)],
    "amethyst_golem": [("crystal", 16, 1.2)],
    "crystalwing": [("crystal", 10, 1.0)],
    "geode_tortoise": [("crystal", 14, 1.15)],
    "facet_hound": [("crystal", 11, .95)],
    "prism_moth": [("crystal", 7, .8)],
    "lattice_spider": [("crystal", 10, .9)],
    "orrery_sentinel": [("plate", 7, 1.0)],
    # Sunmane Steppe
    "goldmane_aurochs": [("plate", 5, .9)],
    "sunmane_gryphon": [("leaf", 8, .7)],
    # Crownwater and the coast: algae, coral, barnacles
    "crownwater_turtle": [("moss", 12, 1.0), ("coral", 5, .8)],
    "algae_alligator": [("moss", 16, 1.05), ("vine", 6, .9)],
    "cascade_golem": [("moss", 14, 1.1), ("coral", 6, .9)],
    "kelpback_turtle": [("moss", 14, 1.1), ("vine", 7, 1.0)],
    "saltmarsh_crocodile": [("moss", 11, .95)],
    "barnacle_troll": [("barnacle", 18, 1.05), ("moss", 8, .9)],
    "rockshell_crab": [("barnacle", 9, .85)],
    "harborshell_crab": [("barnacle", 8, .85), ("moss", 6, .8)],
    "reefplate_golem": [("coral", 12, 1.1), ("barnacle", 8, .9)],
    "mudflat_crab": [("barnacle", 7, .8)],
    "drowned_dockhand": [("moss", 10, .9), ("barnacle", 6, .8)],
    "drowned_captain": [("moss", 7, .8)],
    "millstone_golem": [("moss", 9, .9)],
    "waterwheel_golem": [("moss", 10, .95)],
    "mirrorhold_wheelwarden": [("coral", 8, .9)],
    "verdigris_warden": [("coral", 7, .85)],
    "tidefin_naga": [("coral", 6, .8)],
    # Grey Moors: heather, lichen, cairn stone
    "moorfell_wolf": [("moss", 9, .85)],
    "cairnback_tortoise": [("moss", 12, 1.0), ("plate", 5, .9)],
    "cairn_golem": [("moss", 13, 1.05)],
    "moorhorn_ram": [("moss", 7, .8)],
    "spectral_moor_stag": [("ember", 6, .8)],
    "lantern_wraith": [("ember", 5, .8)],
    "barrow_knight": [("moss", 7, .8)],
    "barrow_king": [("moss", 6, .8)],
    # Manymouth Delta and Verdant Stair: reeds, mangrove, canopy
    "mangrove_turtle": [("vine", 10, 1.1), ("moss", 10, 1.0)],
    "reed_stalker": [("vine", 9, 1.0)],
    "reed_drake": [("vine", 8, .95), ("moss", 7, .9)],
    "bog_warden": [("moss", 11, 1.0)],
    "manymouth_hydra": [("vine", 9, 1.0), ("moss", 9, 1.0)],
    "frogspear_warrior": [("moss", 6, .8)],
    "mossback_anteater": [("moss", 13, 1.05), ("leaf", 7, .8)],
    "vine_treant": [("vine", 10, .85), ("leaf", 4, .7)],
    "verdant_stair_dragon": [("leaf", 12, .9), ("vine", 7, .9)],
    "emerald_basilisk": [("leaf", 6, .7)],
    "canopy_gorilla": [("leaf", 7, .8)],
    # Whitehorn Range: rime and ice
    "rimeshell_crab": [("rime", 10, 1.0)],
    "hoarfrost_serpent": [("rime", 11, .95)],
    "glacier_golem": [("rime", 16, 1.2)],
    "glacier_brute": [("rime", 14, 1.15)],
    "frostplate_knight": [("rime", 9, .95)],
    "whitehorn_yak": [("rime", 7, .85)],
    "rime_harpy": [("rime", 7, .85)],
    # Amberwood: bramble, moss, fungus, leaves
    "moss_bear": [("moss", 15, 1.1), ("fungus", 5, .9), ("leaf", 7, .8)],
    "moss_badger": [("moss", 11, 1.0), ("fungus", 4, .85)],
    "moss_troll": [("moss", 15, 1.1), ("fungus", 6, .95)],
    "bramble_wolf": [("thorn", 14, 1.0), ("leaf", 6, .8)],
    "bramble_stag": [("thorn", 12, 1.0), ("leaf", 7, .85)],
    "ivy_hound": [("vine", 11, 1.0), ("leaf", 8, .85)],
    "ivy_stone_golem": [("vine", 13, 1.05), ("leaf", 9, .9)],
    "amberwood_treant": [("vine", 7, .8), ("leaf", 4, .7), ("fungus", 4, .85)],
    "leafling_sprite": [("leaf", 4, .7)],
    "amberwood_dryad": [("leaf", 6, .8), ("thorn", 6, .8)],
    "thorn_revenant": [("thorn", 13, 1.0)],
    "amberwood_scarecrow": [("thorn", 8, .9)],
    "lantern_stag": [("ember", 7, .85), ("leaf", 6, .8)],
    "amberwood_owl": [("leaf", 7, .8)],
    "emberwing_moth": [("ember", 5, .7)],
    # Elemental lords
    "emberwood_matron": [("leaf", 5, .8), ("ember", 5, .8)],
    "mirefather_leviathan": [("moss", 16, 1.15), ("vine", 8, 1.0)],
    "amethyst_sibyl": [("crystal", 9, .95)],
    "shattered_sentinel": [("crystal", 10, 1.0)],
    "shardbound_archivist": [("crystal", 8, .95)],
    "verdant_crown_king": [("leaf", 8, .85), ("coral", 5, .8)],
    "tidecaller_sorceress": [("coral", 7, .85)],
    "mirrorhold_oracle": [("coral", 6, .8)],
    "mirrorhold_loremaster": [("coral", 6, .8)],
    "orrery_colossus": [("plate", 8, 1.0)],
    # Legacy roster creatures that the art shows encrusted
    "mossback_boar": [("moss", 13, 1.05), ("fungus", 4, .85)],
    "miretoad": [("fungus", 6, .95), ("moss", 8, .9)],
    "bog_lurker": [("moss", 10, .95)],
    "giant_crocodile": [("moss", 9, .9)],
    "giant_komodo": [("moss", 6, .8)],
    "ice_bear": [("rime", 10, 1.0)],
    "frost_maw": [("rime", 9, .95)],
    "frost_tiger": [("rime", 7, .85)],
    "mountain_goat": [("rime", 6, .8)],
    "snow_hare": [("rime", 4, .7)],
    "armored_rhino": [("plate", 6, 1.0)],
    "porcupine": [("spine", 10, 1.0)],
    "ash_crawler": [("crystal", 7, .85)],
    "sunscale_drake": [("plate", 6, .9)],
    "elk": [("leaf", 6, .8)],
    "red_fox": [],
}

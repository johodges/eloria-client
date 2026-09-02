#!/usr/bin/env python3
"""Take the generated weapon and shield set into the client and the server.

Added 2026-09-02 for Eloria Client.

The sibling of ``import_generated_equipment`` for the things you hold rather
than wear.  Same four records, joined by the item's name --

  the mesh          godot-client/assets/actors/native/equipment/<slug>.glb
  the client entry  godot-client/data/actors/equipment.json, models["part:id"]
  the server item   dev-server/config/eloria/items.txt, an [item] block
  the server visual dev-server/eloria/items.py, EQUIPMENT_VISUAL_OVERRIDES

-- and the same rule that a set added to one side and not the other is either
a weapon that draws nothing or geometry nobody can hold.

Two things differ from the armour.  A prop is never skinned: parts 0 and 1
hang off ``hand_r`` and ``hand_l``, so these are plain static meshes and the
socket's own rotation lays them into the grip.  And a prop is not sized from
the body -- a sword is as long as a sword whoever swings it -- so each class
carries its own length, taken off the authored props in
``conform_equipment.PROP_KIND``.

``flip`` is per item and is the one thing that cannot be derived.  Nothing in
a mesh says which end is the tip: a guard is the widest part of a sword and
sits low, an axe head is the widest part of an axe and sits high.  It is set
by looking at a render, the way lowpoly_rigged/models.json sets a donor's
facing.

  python import_generated_weapons.py             build and write
  python import_generated_weapons.py --dry-run
  python import_generated_weapons.py --only sword

Idempotent, like its sibling: the server blocks are marker-fenced and rewritten
whole, the client entries merged into the registry by key.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

import conform_equipment as ce
import equipment_authoring as ea
import import_generated_equipment as armour

HERE = Path(__file__).resolve().parent
CLIENT = HERE.parent.parent / "godot-client"
PROJECT = HERE.parent.parent.parent
GENERATED = PROJECT / "generate_models" / "meshy-weapons-glb"


def _server_beside(client: Path) -> Path:
    """The server checkout that belongs with this client checkout.

    Both halves of a wearable have to be written together, and this tool is
    meant to be run from a worktree -- so defaulting to ``dev-server`` writes
    a worktree's definitions into the main repository, which is exactly the
    mistake this exists to stop.  A worktree at ``wt-<name>`` pairs with
    ``wt-<name>-server`` beside it; anything else falls back to the main
    checkout.  ``--server`` overrides either way.
    """
    paired = client.parent.parent / (client.parent.name + "-server")
    return paired if paired.is_dir() else PROJECT / "dev-server"


SERVER = _server_beside(CLIENT)

EQUIPMENT = CLIENT / "assets/actors/native/equipment"
REGISTRY = CLIENT / "data/actors/equipment.json"

OPEN_ITEMS = "# --- generated weapon set (tools/import_generated_weapons.py) ---"
CLOSE_ITEMS = "# --- end generated weapon set ---"
OPEN_PY = "    # --- generated weapon set (eloria-assets/tools/import_generated_weapons.py) ---"
CLOSE_PY = "    # --- end generated weapon set ---"

#: After the armour set, which ends at 1529.
FIRST_ITEM_ID = 1530

#: After the armour set's icons, which end at 373.
FIRST_IMAGE_ID = 374

#: Where each part's visuals start.  Every legacy weapon and shield model was
#: taken out of the registry when the generated armour became the only
#: equipment, but the ids are left alone above what the legacy set reached
#: (weapon 113, shield 105) so restoring those models could not collide.
FIRST_VISUAL = {0: 114, 1: 106}

#: emu, damage low/high, accuracy, defense for the weapon classes; emu, armour
#: low/high, defense, accuracy for the shields.  The scale is Eternal Lands'
#: (damage in the single digits to the twenties, modifiers a few points either
#: way), and the classes divide it the way EL's families do: one-handed
#: weapons pay for their free shield hand with modest damage, two-handed
#: weapons hit hardest in their own specialty and pay for it somewhere else --
#: a greatsword swings past your own guard (defense), a maul is slow to line
#: up (accuracy), a polearm keeps its point between you and the enemy
#: (defense bonus) but is clumsy up close (accuracy).
WEAPON_STATS = {
    "dagger": (3, (2, 6), 3, 0),
    "sword": (8, (4, 11), 2, 1),
    "axe": (9, (5, 13), 0, 0),
    "mace": (8, (4, 12), 1, 0),
    "wand": (2, (2, 5), 2, 0),
    "thrown": (2, (3, 8), 2, 0),
    "fist": (4, (3, 8), 2, 1),
    "whip": (6, (4, 10), 1, 0),
    # Two-handed: the specialty is strong and the trade-off is explicit.
    "greatsword": (16, (10, 22), -1, -2),
    "greataxe": (15, (12, 24), -2, -3),
    "maul": (17, (11, 25), -3, -3),
    "spear": (11, (7, 16), 1, 1),
    "polearm": (14, (9, 20), -1, 2),
    "staff": (7, (4, 10), 0, 3),
    "bow": (6, (6, 16), 2, -2),
    "crossbow": (10, (9, 20), 1, -2),
}

#: Extra swing weight behind a true two-handed blow: crits land harder.  Reach
#: classes (spear, polearm, staff) and aimed classes (bow, crossbow) already
#: take their benefit as defense or accuracy instead.
TWO_HANDED_CRIT = {"greatsword": 3, "greataxe": 4, "maul": 5}

SHIELD_STATS = {
    "shield": (10, (2, 7), 2, 0),
    "greatshield": (16, (4, 11), 3, -1),
}

#: Which classes loose ammunition rather than swing.  The item declares the
#: class it fires so eloria's own catalogue arms the ranging tables without an
#: entry in the shared Eternal Lands ones (eloria/ranging.py).
AMMUNITION_OF = {"bow": "arrow", "crossbow": "bolt"}


def missile_speed(kind: str, tier: int) -> int:
    """EL firing-speed values: reload is (40 - speed)/10 seconds.

    The trade follows the Eternal Lands bow ladder: the harder a launcher
    hits (tier), the slower it cycles, and a crossbow always cycles slower
    than a bow of its rank.
    """
    if kind == "bow":
        return 30 - 2 * tier
    if kind == "crossbow":
        return 24 - tier
    return 0

#: Design tiers.  2 is honest regional work and the default; 1 is militia and
#: frontier kit; 3 is knightly or otherwise refined; 4 is arcane or exotic
#: mechanism; 5 is the named relics.  Rarer is better: the tier widens the
#: damage range, and from tier 4 the piece picks up a point of accuracy.
DEFAULT_TIER = 2
TIERS = {
    "001_militia_arming_sword": 1,
    "003_frontier_cutlass": 1,
    "011_woodsmans_hatchet": 1,
    "021_militia_short_spear": 1,
    "022_throwing_javelin": 1,
    "041_militia_pike": 1,
    "046_iron_sledgehammer": 1,
    "049_studded_frontier_club": 1,
    "050_fighting_quarterstaff": 1,
    "061_wooden_round_shield": 1,
    "040_frontier_voulge": 1,
    "075_frontier_barricade_shield": 1,
    "002_knightly_cavalry_sword": 3,
    "010_swept_hilt_rapier": 3,
    "013_knightly_battle_axe": 3,
    "018_chain_morningstar": 3,
    "024_knightly_boar_spear": 3,
    "025_hooked_dueling_spear": 3,
    "031_knightly_greatsword": 3,
    "032_highland_claymore": 3,
    "033_flamberge_zweihander": 3,
    "034_executioners_sword": 3,
    "036_classic_halberd": 3,
    "038_knightly_poleaxe": 3,
    "047_lucerne_hammer": 3,
    "048_knightly_great_maul": 3,
    "053_siege_great_crossbow": 3,
    "059_knightly_relic_banner_spear": 4,
    "062_steel_rimmed_heater_shield": 3,
    "063_norman_kite_shield": 3,
    "065_rectangular_tower_shield": 3,
    "066_crossbowmans_pavise": 3,
    "068_legionary_scutum": 3,
    "070_long_dueling_shield": 3,
    "071_knightly_lion_shield": 3,
    "020_arcane_crystal_cudgel": 4,
    "029_arcane_focus_wand": 4,
    "030_crescent_spellblade_sickle": 4,
    "035_arcane_flame_greatblade": 4,
    "054_clockwork_repeating_arbalest": 4,
    "055_alchemical_hand_cannon": 4,
    "056_arcane_double_staff": 4,
    "057_amberwood_branch_bowblade": 4,
    "058_sunmane_twin_crescent_glaive": 4,
    "060_storm_tuning_fork_spear": 4,
    "069_mechanical_lantern_shield": 4,
    "074_arcane_crystal_shield": 4,
    "076_polished_mirror_shield": 4,
    "077_dragon_scale_shield": 4,
    "078_ice_crystal_shield": 4,
    "079_molten_forge_shield": 4,
    "080_thorned_root_shield": 4,
    "081_segmented_whip_sword": 4,
    "084_lantern_flail": 4,
    "086_double_ended_twinblade": 4,
    "087_circular_ringblade": 4,
    "090_folding_crescent_bow": 4,
    "091_rune_battle_gauntlet": 4,
    "092_alchemist_cannon": 4,
    "093_crystal_prism_staff": 4,
    "094_clockwork_saw_lance": 4,
    "088_polarity_war_hammer": 5,
    "089_gravity_anchor_weapon": 5,
    "095_living_vine_bow": 5,
    "096_phoenix_feather_spear": 5,
    "097_void_glass_greatblade": 5,
    "098_radiant_sun_disc_chakram": 5,
    "099_echo_bell_hammer": 5,
    "100_stormglass_shield_spear": 5,
}

#: Elemental and warding character read off the design itself, stated per stem
#: so a piece's flavour is a decision rather than a substring accident.
THEME_STATS = {
    "020_arcane_crystal_cudgel": (("magic_damage", 2),),
    "029_arcane_focus_wand": (("magic_damage", 2), ("max_ether", 4)),
    "030_crescent_spellblade_sickle": (("magic_damage", 2),),
    "035_arcane_flame_greatblade": (("heat_damage", 3),),
    "056_arcane_double_staff": (("magic_damage", 2), ("max_ether", 6)),
    "060_storm_tuning_fork_spear": (("magic_damage", 2),),
    "074_arcane_crystal_shield": (("magic_protection", 3),),
    "076_polished_mirror_shield": (("magic_protection", 2),),
    "077_dragon_scale_shield": (("heat_protection", 3),),
    "078_ice_crystal_shield": (("cold_protection", 3),),
    "079_molten_forge_shield": (("heat_protection", 3),),
    "080_thorned_root_shield": (("critical_to_damage", 1),),
    "088_polarity_war_hammer": (("magic_damage", 3),),
    "089_gravity_anchor_weapon": (("critical_to_damage", 2),),
    "093_crystal_prism_staff": (("magic_damage", 3), ("max_ether", 8)),
    "095_living_vine_bow": (("perception_bonus", 2),),
    "096_phoenix_feather_spear": (("heat_damage", 3),),
    "097_void_glass_greatblade": (("magic_damage", 4),),
    "098_radiant_sun_disc_chakram": (("heat_damage", 2),),
    "099_echo_bell_hammer": (("magic_damage", 2), ("critical_to_hit", 2)),
    "100_stormglass_shield_spear": (("magic_damage", 2), ("magic_protection", 2)),
}

#: Which classes are held in one hand.  ``both_hands`` is a weapon slot on the
#: server (WEAPON_WEAR_EQUIP_TYPES) even though the legacy catalogue also hangs
#: gloves off it, so a two-hander is honest to declare there.
ONE_HANDED = {"dagger", "sword", "axe", "mace", "wand", "thrown", "fist",
              "whip"}

#: stem -> (label, kind).  The stems are the concept art's own file names, so
#: this table is the one place a piece's class is decided.  Order here is the
#: order ids are handed out in, and it follows the art's numbering.
DESIGNS = [
    ("001_militia_arming_sword", "Militia Arming Sword", "sword"),
    ("002_knightly_cavalry_sword", "Knightly Cavalry Sword", "sword"),
    ("003_frontier_cutlass", "Frontier Cutlass", "sword"),
    ("004_amberwood_leafblade", "Amberwood Leafblade", "sword"),
    ("005_sunmane_steppe_saber", "Sunmane Steppe Saber", "sword"),
    ("006_rondel_dagger", "Rondel Dagger", "dagger"),
    ("007_ring_guard_parrying_dagger", "Ring Guard Parrying Dagger", "dagger"),
    ("008_gladius", "Gladius", "sword"),
    ("009_heavy_falchion", "Heavy Falchion", "sword"),
    ("010_swept_hilt_rapier", "Swept Hilt Rapier", "sword"),
    ("011_woodsmans_hatchet", "Woodsman's Hatchet", "axe"),
    ("012_bearded_raider_axe", "Bearded Raider Axe", "axe"),
    ("013_knightly_battle_axe", "Knightly Battle Axe", "axe"),
    ("014_sunmane_crescent_axe", "Sunmane Crescent Axe", "axe"),
    ("015_amberwood_tomahawk", "Amberwood Tomahawk", "axe"),
    ("016_flanged_mace", "Flanged Mace", "mace"),
    ("017_war_hammer", "War Hammer", "mace"),
    ("018_chain_morningstar", "Chain Morningstar", "mace"),
    ("019_blacksmith_maul", "Blacksmith Maul", "maul"),
    ("020_arcane_crystal_cudgel", "Arcane Crystal Cudgel", "mace"),
    ("021_militia_short_spear", "Militia Short Spear", "spear"),
    ("022_throwing_javelin", "Throwing Javelin", "spear"),
    ("023_mariners_trident", "Mariner's Trident", "spear"),
    ("024_knightly_boar_spear", "Knightly Boar Spear", "spear"),
    ("025_hooked_dueling_spear", "Hooked Dueling Spear", "spear"),
    ("026_frontier_hand_crossbow", "Frontier Hand Crossbow", "crossbow"),
    ("027_throwing_knife_fan", "Throwing Knife Fan", "thrown"),
    ("028_engraved_war_chakram", "Engraved War Chakram", "thrown"),
    ("029_arcane_focus_wand", "Arcane Focus Wand", "wand"),
    ("030_crescent_spellblade_sickle", "Crescent Spellblade Sickle", "sword"),
    ("031_knightly_greatsword", "Knightly Greatsword", "greatsword"),
    ("032_highland_claymore", "Highland Claymore", "greatsword"),
    ("033_flamberge_zweihander", "Flamberge Zweihander", "greatsword"),
    ("034_executioners_sword", "Executioner's Sword", "greatsword"),
    ("035_arcane_flame_greatblade", "Arcane Flame Greatblade", "greatsword"),
    ("036_classic_halberd", "Classic Halberd", "polearm"),
    ("037_single_edged_glaive", "Single Edged Glaive", "polearm"),
    ("038_knightly_poleaxe", "Knightly Poleaxe", "polearm"),
    ("039_steppe_bardiche", "Steppe Bardiche", "polearm"),
    ("040_frontier_voulge", "Frontier Voulge", "polearm"),
    ("041_militia_pike", "Militia Pike", "polearm"),
    ("042_forged_war_scythe", "Forged War Scythe", "polearm"),
    ("043_three_pronged_ranseur", "Three Pronged Ranseur", "polearm"),
    ("044_winged_partisan", "Winged Partisan", "polearm"),
    ("045_heavy_boar_spear", "Heavy Boar Spear", "spear"),
    ("046_iron_sledgehammer", "Iron Sledgehammer", "maul"),
    ("047_lucerne_hammer", "Lucerne Hammer", "polearm"),
    ("048_knightly_great_maul", "Knightly Great Maul", "maul"),
    ("049_studded_frontier_club", "Studded Frontier Club", "mace"),
    ("050_fighting_quarterstaff", "Fighting Quarterstaff", "staff"),
    # Not "Amberwood Longbow": the authored prop of that name is already in the
    # catalogue, and the item's name is the only thing joining a definition to
    # its geometry, so two of them resolve to one another's models.
    ("051_amberwood_longbow", "Amberwood Yew Longbow", "bow"),
    ("052_sunmane_recurve_bow", "Sunmane Recurve Bow", "bow"),
    ("053_siege_great_crossbow", "Siege Great Crossbow", "crossbow"),
    ("054_clockwork_repeating_arbalest", "Clockwork Repeating Arbalest",
     "crossbow"),
    ("055_alchemical_hand_cannon", "Alchemical Hand Cannon", "crossbow"),
    ("056_arcane_double_staff", "Arcane Double Staff", "staff"),
    ("057_amberwood_branch_bowblade", "Amberwood Branch Bowblade", "bow"),
    ("058_sunmane_twin_crescent_glaive", "Sunmane Twin Crescent Glaive",
     "polearm"),
    ("059_knightly_relic_banner_spear", "Knightly Relic Banner Spear",
     "polearm"),
    ("060_storm_tuning_fork_spear", "Storm Tuning Fork Spear", "spear"),

    ("061_wooden_round_shield", "Wooden Round Shield", "shield"),
    ("062_steel_rimmed_heater_shield", "Steel Rimmed Heater Shield", "shield"),
    ("063_norman_kite_shield", "Norman Kite Shield", "greatshield"),
    ("064_parrying_buckler", "Parrying Buckler", "shield"),
    ("065_rectangular_tower_shield", "Rectangular Tower Shield",
     "greatshield"),
    ("066_crossbowmans_pavise", "Crossbowman's Pavise", "greatshield"),
    ("067_reinforced_highland_targe", "Reinforced Highland Targe", "shield"),
    ("068_legionary_scutum", "Legionary Scutum", "greatshield"),
    ("069_mechanical_lantern_shield", "Mechanical Lantern Shield", "shield"),
    ("070_long_dueling_shield", "Long Dueling Shield", "greatshield"),
    ("071_knightly_lion_shield", "Knightly Lion Shield", "shield"),
    ("072_sunmane_hide_bronze_shield", "Sunmane Hide Bronze Shield", "shield"),
    ("073_amberwood_living_bark_shield", "Amberwood Living Bark Shield",
     "shield"),
    ("074_arcane_crystal_shield", "Arcane Crystal Shield", "shield"),
    ("075_frontier_barricade_shield", "Frontier Barricade Shield",
     "greatshield"),
    ("076_polished_mirror_shield", "Polished Mirror Shield", "shield"),
    ("077_dragon_scale_shield", "Dragon Scale Shield", "shield"),
    ("078_ice_crystal_shield", "Ice Crystal Shield", "shield"),
    ("079_molten_forge_shield", "Molten Forge Shield", "shield"),
    ("080_thorned_root_shield", "Thorned Root Shield", "shield"),

    ("081_segmented_whip_sword", "Segmented Whip Sword", "whip"),
    ("082_chain_sickle", "Chain Sickle", "whip"),
    ("083_bladed_war_fans", "Bladed War Fans", "fist"),
    ("084_lantern_flail", "Lantern Flail", "mace"),
    ("085_serpent_coil_whip", "Serpent Coil Whip", "whip"),
    ("086_double_ended_twinblade", "Double Ended Twinblade", "staff"),
    ("087_circular_ringblade", "Circular Ringblade", "thrown"),
    ("088_polarity_war_hammer", "Polarity War Hammer", "maul"),
    ("089_gravity_anchor_weapon", "Gravity Anchor", "maul"),
    ("090_folding_crescent_bow", "Folding Crescent Bow", "bow"),
    ("091_rune_battle_gauntlet", "Rune Battle Gauntlet", "fist"),
    ("092_alchemist_cannon", "Alchemist Cannon", "crossbow"),
    ("093_crystal_prism_staff", "Crystal Prism Staff", "staff"),
    ("094_clockwork_saw_lance", "Clockwork Saw Lance", "polearm"),
    ("095_living_vine_bow", "Living Vine Bow", "bow"),
    ("096_phoenix_feather_spear", "Phoenix Feather Spear", "spear"),
    ("097_void_glass_greatblade", "Void Glass Greatblade", "greatsword"),
    ("098_radiant_sun_disc_chakram", "Radiant Sun Disc Chakram", "thrown"),
    ("099_echo_bell_hammer", "Echo Bell Hammer", "maul"),
    ("100_stormglass_shield_spear", "Stormglass Shield Spear", "spear"),
]

#: Pieces that arrive the opposite way round to the rest of their class, which
#: turns the class default off for them as readily as on.  The art is drawn per
#: piece and not to a rule, so a class default is only ever a majority: the
#: greatswords come out blade down like every other blade, except this one.
#: Each line is settled by looking at a render.
FLIP_EXCEPTIONS = {
    "097_void_glass_greatblade",
}

#: How a prop is laid into the hand, as a socket this set overrides the shared
#: part socket with.  The runtime already allows that -- it is how a two-handed
#: haft rides differently from a one-handed hilt on the same bone -- so the
#: authored props keep the part socket they were built against.
#:
#: The sockets are solved against the *idle* pose rather than the rest pose.
#: The shared part socket points a blade forward and down at rest, but the
#: attachment rides the bone, so the idle's hand rotation lands on top of it and
#: swings the sword across the body.  ``upright_grip_basis`` exists for exactly
#: this: it stands a haft up in the idle, and leaning it a right angle turns
#: that "up" into the direction the actor faces.
FORWARD_LEAN = 90.0

#: The clip to solve the grip against.  It can only be right for one: the hand
#: turns differently in every animation, and a weapon that points forward while
#: standing is 48 degrees off mid-stride.  This is the one the client idles in
#: (data/animations/luminous.json maps "idle" to it); Idle_A, which
#: equipment_authoring defaults to, is the *alternate* idle and leaves a blade
#: 43 degrees across the body in the pose a player actually stands in.
IDLE_CLIP = "Idle_Subtle"

#: A quarter turn about the weapon's own length.  It does not change where the
#: weapon points, only which way its flat faces: without it a blade is carried
#: flat, face to the floor, and reads as a plank rather than a sword.
BLADE_ROLL = 90.0

#: The shield is worn half again larger than it is authored, pushed clear of the
#: hip, and turned out from the body so its face is seen rather than its edge.
SHIELD_SCALE = 1.5
SHIELD_SPLAY = 25.0
SHIELD_PUSH = 0.10


def _euler_degrees(basis: np.ndarray) -> list[float]:
    """A basis as the XYZ degrees Godot's ``Basis.from_euler`` will rebuild.

    ``from_euler`` composes YXZ, so the angles come out in that order and are
    reordered here.  Checked against both shipped sockets, which round-trip to
    themselves exactly.
    """
    y, x, z = Rotation.from_matrix(basis).as_euler("YXZ", degrees=True)
    return [round(float(x), 5), round(float(y), 5), round(float(z), 5)]


def prop_sockets(rig, race: Path, library: Path, base: dict) -> dict:
    """Per-part sockets that hold a weapon forward and a shield out."""
    idle = ea._idle_hand_bases(str(race), str(library), IDLE_CLIP)
    sockets = {}

    blade = ea.upright_grip_basis(rig, "r", idle["r"], forward_lean=FORWARD_LEAN)
    # Rolled about the weapon's own length, which leaves where it points alone
    # and only turns which way its flat faces.  `upright_grip_basis` hands back
    # a blade lying flat -- face down, edges to the sides -- and a sword read
    # that way is a plank.  A quarter turn stands the blade up, edges above and
    # below, which is how one is carried.
    roll = math.radians(BLADE_ROLL)
    blade = blade @ np.array([[math.cos(roll), 0., math.sin(roll)],
                              [0., 1., 0.],
                              [-math.sin(roll), 0., math.cos(roll)]])
    sockets[0] = {"bone": "hand_r",
                  "offset": list(base[0]["offset"]),
                  "rotationDegrees": _euler_degrees(blade)}

    # The shield's face is turned out from the body, which for the left hand is
    # the actor's own left, and its top stays up.
    splay = math.radians(SHIELD_SPLAY)
    face = np.array([math.sin(splay), 0., math.cos(splay)])
    up = np.array([0., 1., 0.])
    up = up - face * float(up @ face)
    up /= np.linalg.norm(up)
    desired = np.column_stack((np.cross(up, face), up, face))
    held = rig.basis("hand_l") @ np.linalg.inv(idle["l"]) @ desired
    offset = list(base[1]["offset"])
    offset[2] += SHIELD_PUSH
    sockets[1] = {"bone": "hand_l", "offset": offset,
                  "rotationDegrees": _euler_degrees(held)}
    return sockets


class Piece:
    __slots__ = ("source", "slug", "name", "kind", "part", "visual", "item_id",
                 "image_id", "flip")

    def __init__(self, source, slug, name, kind, part, visual, item_id,
                 image_id, flip):
        self.source, self.slug, self.name, self.kind = source, slug, name, kind
        self.part, self.visual = part, visual
        self.item_id, self.image_id, self.flip = item_id, image_id, flip


def roster() -> list[Piece]:
    """Every generated prop, in a fixed order so ids never move."""
    pieces: list[Piece] = []
    nxt = dict(FIRST_VISUAL)
    for index, (stem, label, kind) in enumerate(DESIGNS):
        source = GENERATED / (stem + ".glb")
        # Only sources that have been through the texture pass, which leaves
        # the raw export beside them as `.glb.orig`.  Same guard the armour
        # importer uses: a raw drop-in would otherwise define an item whose
        # icon and compressed texture do not exist yet.
        if not source.exists() or not source.with_name(
                source.name + ".orig").exists():
            continue
        part = ce.PROP_KIND[kind]["part"]
        pieces.append(Piece(
            source, stem[4:], label, kind, part, nxt[part],
            FIRST_ITEM_ID + index, FIRST_IMAGE_ID + index,
            stem in FLIP_EXCEPTIONS))
        nxt[part] += 1
    return pieces


def design_tier(stem: str) -> int:
    return TIERS.get(stem, DEFAULT_TIER)


def item_block(piece: Piece) -> str:
    stem = piece.source.stem
    tier = design_tier(stem)
    shield = piece.kind in SHIELD_STATS
    themed = list(THEME_STATS.get(stem, ()))
    if shield:
        emu, (low, high), defense, accuracy = SHIELD_STATS[piece.kind]
        low += max(0, tier - 2)
        high += 2 * (tier - 1)
        if tier >= 4:
            defense += 1
        rows = ["armor: %d/%d" % (low, high), "damage: 0/0",
                "accuracy: %d" % accuracy, "defense: %d" % defense]
        category, slot = "Armor", "left_hand"
    else:
        emu, (low, high), accuracy, defense = WEAPON_STATS[piece.kind]
        low += max(0, tier - 2)
        high += 2 * (tier - 1)
        if tier >= 4:
            accuracy += 1
        rows = ["armor: 0/0", "damage: %d/%d" % (low, high),
                "accuracy: %d" % accuracy, "defense: %d" % defense]
        crit = TWO_HANDED_CRIT.get(piece.kind, 0)
        if crit:
            themed.insert(0, ("critical_to_damage", crit))
        category = "Weapons"
        slot = "right_hand" if piece.kind in ONE_HANDED else "both_hands"
    rows.extend("%s: %d" % (key, value) for key, value in themed if value)
    if piece.kind in AMMUNITION_OF:
        rows.append("ranged_ammunition: %s" % AMMUNITION_OF[piece.kind])
        rows.append("missile_speed: %d" % missile_speed(piece.kind, tier))
    return "\n".join([
        "", "[item]",
        "name: %s" % piece.name,
        "item_id: %d" % piece.item_id,
        "image_id: %d" % piece.image_id,
        "emu: %d" % emu,
        "flags: 2",
        "category: %s" % category,
        "description: Generated from the %s concept art." % piece.name.lower(),
        "equip_type: %s" % slot,
        *rows,
        "[/item]"])


def main() -> int:
    ap = argparse.ArgumentParser(
        description="build the generated weapon set and define it on both sides")
    ap.add_argument("--race", default="luminous_male")
    ap.add_argument("--only", default=None,
                    help="only pieces whose slug or kind contains this")
    ap.add_argument("--server", type=Path, default=SERVER)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-build", action="store_true")
    args = ap.parse_args()

    # `--only` narrows what is *built*, never what is defined.  The server
    # blocks are one marker-fenced region rewritten whole, so writing them from
    # a filtered roster deletes every piece the filter excluded -- a one-piece
    # rebuild would take the other ninety-nine out of the catalogue with it.
    everything = roster()
    pieces = everything
    if args.only:
        pieces = [p for p in everything
                  if args.only in p.slug or args.only == p.kind]
    if not pieces:
        print("nothing to do (are the meshes generated and texture-shrunk?)")
        return 2

    import collections
    print("%d prop(s): %s" % (len(pieces), ", ".join(
        "%s x%d" % (k, n) for k, n in
        sorted(collections.Counter(p.kind for p in pieces).items()))))
    if args.dry_run:
        for p in pieces:
            print("  %-32s %-11s part %d visual %-4d item %d image %d"
                  % (p.slug, p.kind, p.part, p.visual, p.item_id, p.image_id))
        print("\nnothing written (--dry-run)")
        return 0

    # An item's name is the only thing joining its definition to its geometry,
    # so two items sharing one is not a cosmetic clash: the catalogue refuses to
    # load, and if it did not, the pair would resolve to each other's models.
    # Checked against the catalogue as it stands minus this set's own fence,
    # so re-running is not mistaken for a collision with itself.
    items_path = args.server / "config/eloria/items.txt"
    catalogue = items_path.read_text(encoding="utf-8")
    if OPEN_ITEMS in catalogue:
        head, _, rest = catalogue.partition(OPEN_ITEMS)
        catalogue = head + rest.partition(CLOSE_ITEMS)[2]
    taken = {line.partition(":")[2].strip().casefold()
             for line in catalogue.splitlines() if line.startswith("name:")}
    clash = sorted(p.name for p in everything if p.name.casefold() in taken)
    if clash:
        print("these names are already in the catalogue: %s"
              % ", ".join(clash), file=sys.stderr)
        return 2

    rig = ea.load_rig(ce.RACES / ("%s.glb" % args.race), ce.BODY_MESH)
    built = failed = 0
    if not args.skip_build:
        EQUIPMENT.mkdir(parents=True, exist_ok=True)
        for p in pieces:
            try:
                info = ce.build(p.source, EQUIPMENT / ("%s.glb" % p.slug), rig,
                                p.kind, p.name, flip=p.flip)
            except Exception as exc:                      # noqa: BLE001
                print("  FAILED %-30s %s" % (p.slug, exc))
                failed += 1
                continue
            built += 1
            print("  %-32s %-11s %5d verts  %.2f MB"
                  % (p.slug, p.kind, info["vertices"], info["bytes"] / 1e6))

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    sockets = prop_sockets(
        rig, ce.RACES / ("%s.glb" % args.race),
        CLIENT / "assets/actors/native/shared/Universal_Animation_Library.glb",
        {int(k): v for k, v in registry["sockets"].items()})
    for p in everything:
        entry = {"scene": "res://assets/actors/native/equipment/%s.glb" % p.slug,
                 "name": p.name, "attach": "socket",
                 "socket": sockets[p.part]}
        if p.part == 1:
            entry["scale"] = SHIELD_SCALE
        registry["models"]["%d:%d" % (p.part, p.visual)] = entry
    REGISTRY.write_text(json.dumps(registry, indent=2) + "\n",
                        encoding="utf-8")

    items = args.server / "config/eloria/items.txt"
    body = "\n".join(item_block(p) for p in everything).lstrip("\n")
    items.write_text(
        armour.fence(items.read_text(encoding="utf-8"), OPEN_ITEMS,
                     CLOSE_ITEMS, body), encoding="utf-8")

    items_py = args.server / "eloria/items.py"
    source = items_py.read_text(encoding="utf-8")
    rows = "\n".join('    "%s": (%d, %d),' % (p.name.casefold(), p.part,
                                              p.visual) for p in everything)
    if OPEN_PY in source:
        source = armour.fence(source, OPEN_PY, CLOSE_PY, rows)
    else:
        anchor = armour.CLOSE_PY + "\n"
        if anchor not in source:
            print("could not find the armour set's override block to sit after")
            return 2
        source = source.replace(
            anchor, anchor + "%s\n%s\n%s\n" % (OPEN_PY, rows, CLOSE_PY), 1)
    items_py.write_text(source, encoding="utf-8")

    print("\n%d built, %d failed" % (built, failed))
    for label, path in (("meshes", EQUIPMENT), ("registry", REGISTRY),
                        ("items", items), ("visuals", items_py)):
        print("  %-9s %s" % (label, path))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

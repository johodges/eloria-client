from __future__ import annotations

"""Thicken generated race-body limbs toward Luminous's own proportions.

Meshy infers a limb's thickness from the 2D concept art's silhouette, so a
race whose reference art wears looser sleeves or trousers than Luminous's
gives it less to go on: measured bone-relative (median distance from a
limb's own skinned vertices to its bone's rest-pose axis, restricted to
each vertex's SINGLE dominant joint so a stray far-off vertex weighted
mostly to some other bone can't skew it), all 14 common-skeleton races
come out with visibly thinner upper arms (26-44% thinner than Luminous)
and calves (12-35% thinner) than Luminous herself/himself; thighs are
closer. Boot mesh width/depth stays roughly constant across bodies, so a
thin calf tucking into an unchanged boot cuff reads as a mismatch too,
without the boot mesh itself needing anything done to it.

This scales each limb segment's skin RADIALLY around its own bone's
rest-pose axis -- moving vertices further from (or closer to) the bone,
never sliding them along it -- so the fix changes girth only, not limb
length or joint position. The scale for a given body's segment is that
body's own current radius divided into a TARGET radius: a fraction
(TARGET_FRACTION) of Luminous's OWN measured radius for that same
segment, gender-matched (male bodies target luminous_male, female bodies
target luminous_female) since the two are not the same thickness to
begin with. A vertex with mixed skinning weight near a joint (e.g. the
elbow) blends the displacement from every bone influencing it, weighted
the same way the skin itself blends, so there is no seam at the segment
boundary -- see `displace`.

TARGET_FRACTION is deliberately a module constant rather than buried in
a formula: it is a judgement call (how close to Luminous is "similar
enough"), not a measured fact, and the whole point of pulling it out is
to make it one line to change and re-run if 0.80 turns out too much or
too little once seen in the client.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from split_race_surfaces import (  # noqa: E402
    BODY_SEGMENTS, CLASSES, RACES, accessor_array, overwrite_accessor,
    resmooth_shared_surfaces, read_glb, write_glb,
)

TARGET_FRACTION = 0.80

# A first version guarded against contamination by ratio-to-Luminous alone
# (anything over 1.5x treated as suspect and left untouched) on the theory
# that a real thin limb never measures ABOVE Luminous, only Ssarathi's
# tail-on-the-thigh-bone contamination does. Checked directly, that is
# false: Orun Female's own legs measure 1.6-1.8x Luminous Female's, for
# real, and the ratio guard was silently protecting them from the
# correction they needed instead of catching contamination. What actually
# marks a vertex as contamination (tail, not leg) is the same test
# classify() already uses to keep tail geometry out of "body" -- distance
# from every recognised limb/torso/head bone segment, not just the one
# whose dominant weight happens to claim it. A real leg surface sits near
# its own bone regardless of how thick it is; only genuinely orphaned
# geometry sits far from all of them.
ORPHAN_DISTANCE = 0.30

# A final backstop, not the primary guard (see above): still catches an
# outright measurement failure (e.g. a handful of stray vertices) without
# relying on it to distinguish a thick leg from contamination.
MAX_SANE_RATIO = 3.0

# Both directions, not a 1.0 floor: the original ask was to thicken limbs
# too thin to grow toward Luminous, but Orun Female's legs (measured
# directly at 1.6-1.8x Luminous Female's own) and the left/right asymmetry
# it produces need to come back DOWN toward the same target, not just stay
# put because they were never going to shrink. 0.5-1.8 bounds either
# direction against a measurement fluke demanding an implausible change.
SCALE_CLAMP = (0.5, 1.8)

# (near bone, far bone) per segment -- far bone only fixes the axis
# direction/length; vertices are selected by dominant weight on the NEAR
# bone alone.
SEGMENT_FAR_BONE = {
    "upperarm": "lowerarm",
    "lowerarm": "hand",
    "thigh": "calf",
    "calf": "foot",
}
SIDES = ("l", "r")


def bone_rest_position(document, binary, skin_index: int, joint_name: str) -> np.ndarray:
    skin = document["skins"][skin_index]
    names = [document["nodes"][j].get("name", "") for j in skin["joints"]]
    ibms = accessor_array(document, binary, skin["inverseBindMatrices"])
    row = names.index(joint_name)
    ibm = np.asarray(ibms[row], dtype=np.float64).reshape(4, 4).T
    return np.linalg.inv(ibm)[:3, 3]


def shared_attributes(document, binary):
    """The one POSITION/JOINTS_0/WEIGHTS_0 accessor every class primitive
    shares (see split_race_surfaces's own module docstring), plus the skin
    index they're all bound to."""
    nodes = [n for n in document["nodes"]
             if n.get("name") in CLASSES and "mesh" in n]
    prims = [document["meshes"][n["mesh"]]["primitives"][0] for n in nodes]
    pos_acc = prims[0]["attributes"]["POSITION"]
    joints_acc = prims[0]["attributes"]["JOINTS_0"]
    weights_acc = prims[0]["attributes"]["WEIGHTS_0"]
    assert all(p["attributes"]["POSITION"] == pos_acc for p in prims)
    assert all(p["attributes"]["JOINTS_0"] == joints_acc for p in prims)
    assert all(p["attributes"]["WEIGHTS_0"] == weights_acc for p in prims)
    skin_index = nodes[0]["skin"]
    assert all(n["skin"] == skin_index for n in nodes)
    return pos_acc, joints_acc, weights_acc, skin_index


def orphan_mask(document, binary, skin_index: int, positions) -> np.ndarray:
    """True for a vertex further than ORPHAN_DISTANCE from every recognised
    limb/torso/head bone segment -- see split_race_surfaces.classify()'s
    own tail exclusion, which this mirrors exactly (same BODY_SEGMENTS,
    same cutoff) because it is the same problem: geometry with no bone
    chain of its own (Ssarathi's tail) falls back to whichever nearby
    bone the auto-rigger happened to weight it to, and a real leg or arm
    surface never sits this far from the bone it actually belongs to."""
    min_dist = None
    for near, far in BODY_SEGMENTS:
        a = bone_rest_position(document, binary, skin_index, near)
        b = bone_rest_position(document, binary, skin_index, far)
        axis = b - a
        axis_len = np.linalg.norm(axis)
        unit = axis / axis_len
        v = positions - a
        t = np.clip(v @ unit, -0.05, axis_len + 0.05)
        dist = np.linalg.norm(positions - (a + np.outer(t, unit)), axis=1)
        min_dist = dist if min_dist is None else np.minimum(min_dist, dist)
    return min_dist > ORPHAN_DISTANCE


def segment_radius(positions, dominant, joint_index, a, b, margin=0.15):
    """Median perpendicular distance from `a`-to-`b`'s own axis, among
    vertices whose SINGLE largest skin weight is `joint_index`, restricted
    to roughly the segment itself (a wide margin either side of the two
    joints, not the whole rest of the body some misweighted vertex might
    otherwise drag in)."""
    axis = b - a
    axis_len = float(np.linalg.norm(axis))
    unit = axis / axis_len
    sel = dominant == joint_index
    if not sel.any():
        return float("nan"), axis_len
    v = positions[sel] - a
    t = v @ unit
    onseg = (t >= -margin * axis_len) & (t <= axis_len * (1 + margin))
    if not onseg.any():
        return float("nan"), axis_len
    perp = v[onseg] - np.outer(t[onseg], unit)
    return float(np.median(np.linalg.norm(perp, axis=1))), axis_len


def measure_body(document, binary) -> dict:
    """{(part, side): radius} for every (part, side) in SEGMENT_FAR_BONE x SIDES."""
    pos_acc, joints_acc, weights_acc, skin_index = shared_attributes(document, binary)
    positions = accessor_array(document, binary, pos_acc)
    joints = accessor_array(document, binary, joints_acc).astype(np.int64)
    weights = accessor_array(document, binary, weights_acc)
    dominant = joints[np.arange(len(joints)), np.argmax(weights, axis=1)]
    # Orphaned geometry (a tail with no bone chain of its own) still has
    # SOME dominant joint -- whichever nearby bone the auto-rigger
    # defaulted it to -- so it has to be pulled out before that argmax
    # result is trusted, not after.
    dominant = np.where(orphan_mask(document, binary, skin_index, positions),
                        -1, dominant)
    skin = document["skins"][skin_index]
    names = [document["nodes"][j].get("name", "") for j in skin["joints"]]

    out = {}
    for part, far in SEGMENT_FAR_BONE.items():
        for side in SIDES:
            a = bone_rest_position(document, binary, skin_index, "%s_%s" % (part, side))
            b = bone_rest_position(document, binary, skin_index, "%s_%s" % (far, side))
            joint_index = names.index("%s_%s" % (part, side))
            radius, _ = segment_radius(positions, dominant, joint_index, a, b)
            out[(part, side)] = radius
    return out


def luminous_reference(gender: str) -> dict:
    """{part: radius}, Luminous's OWN measured radius (not yet scaled by
    TARGET_FRACTION -- that happens once, in compute_scales), averaged
    across both sides of the matching Luminous body. Both sides are
    measured independently rather than assumed symmetric (Luminous Male's
    own thigh_l/thigh_r differ by ~20%, ordinary generation noise, not a
    shape to replicate), so the average is the fairer "this body's own
    scale" than either side alone."""
    path = RACES / ("luminous_%s.glb" % gender)
    document, binary = read_glb(path)
    per_side = measure_body(document, binary)
    return {part: float(np.mean([per_side[(part, side)] for side in SIDES]))
            for part in SEGMENT_FAR_BONE}


def compute_scales(own: dict, luminous_ref: dict) -> dict:
    """{(part, side): scale}, guarded against contamination and extremes."""
    scales = {}
    for (part, side), radius in own.items():
        ref = luminous_ref[part]
        target = TARGET_FRACTION * ref
        if not np.isfinite(radius) or radius <= 1e-6:
            print("    %s_%s: no reliable measurement, leaving alone" % (part, side))
            scales[(part, side)] = 1.0
            continue
        if radius > MAX_SANE_RATIO * ref:
            print("    %s_%s: radius %.4f is %.1fx Luminous's own (%.4f) -- "
                  "treating as contaminated, leaving alone"
                  % (part, side, radius, radius / ref, ref))
            scales[(part, side)] = 1.0
            continue
        scale = target / radius
        clamped = float(np.clip(scale, *SCALE_CLAMP))
        if clamped != scale:
            print("    %s_%s: scale %.3f clamped to %.3f" % (part, side, scale, clamped))
        scales[(part, side)] = clamped
    return scales


def displace(document, binary, scales: dict) -> np.ndarray:
    """New positions after radially scaling each segment by its own factor,
    blending by skin weight so mixed-weight vertices near a joint (e.g. the
    elbow) interpolate smoothly between the two segments' scales instead of
    seaming at the boundary -- the same blend the skin itself already uses,
    just applied to a displacement instead of a bone transform."""
    pos_acc, joints_acc, weights_acc, skin_index = shared_attributes(document, binary)
    positions = accessor_array(document, binary, pos_acc)
    joints = accessor_array(document, binary, joints_acc).astype(np.int64)
    weights = accessor_array(document, binary, weights_acc)
    skin = document["skins"][skin_index]
    names = [document["nodes"][j].get("name", "") for j in skin["joints"]]
    # A vertex this far from every recognised bone segment still carries
    # real skin WEIGHT on whichever nearby bone it defaulted to (Ssarathi's
    # tail on thigh_l/r) -- excluded from the measurement in measure_body,
    # it needs excluding here too, or scaling that thigh would drag the
    # tail along with it even though the tail was never part of what was
    # measured as too thin or too thick.
    not_orphan = ~orphan_mask(document, binary, skin_index, positions)

    total_displacement = np.zeros_like(positions)
    for (part, side), scale in scales.items():
        if scale == 1.0:
            continue
        joint_index = names.index("%s_%s" % (part, side))
        a = bone_rest_position(document, binary, skin_index, "%s_%s" % (part, side))
        b = bone_rest_position(document, binary, skin_index,
                               "%s_%s" % (SEGMENT_FAR_BONE[part], side))
        axis = b - a
        unit = axis / np.linalg.norm(axis)
        v = positions - a
        t = v @ unit
        perp = v - np.outer(t, unit)
        # Per-vertex weight this bone contributes, summed across whichever
        # of the 4 joint slots happen to reference it (glTF does not
        # guarantee a fixed slot order).
        w = np.where(joints == joint_index, weights, 0.0).sum(axis=1)
        w = np.where(not_orphan, w, 0.0)
        total_displacement += (perp * (scale - 1.0)) * w[:, None]
    return positions + total_displacement


def process(path: Path, luminous_ref_by_gender: dict, gender: str) -> str:
    document, binary = read_glb(path)
    own = measure_body(document, binary)
    print("  measured:", {("%s_%s" % k): round(v, 4) for k, v in own.items()})
    scales = compute_scales(own, luminous_ref_by_gender[gender])
    if all(s == 1.0 for s in scales.values()):
        return "no segment needed correction"
    new_positions = displace(document, binary, scales)
    pos_acc, _, _, _ = shared_attributes(document, binary)
    overwrite_accessor(document, binary, pos_acc, new_positions)
    resmooth_shared_surfaces(document, binary)
    write_glb(path, document, binary)
    parts = ", ".join("%s_%s=%.3f" % (k[0], k[1], v)
                      for k, v in scales.items() if v != 1.0)
    return "scaled %s" % parts


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="thicken race-body limbs toward Luminous")
    ap.add_argument("races", nargs="*",
                    help="race glb stems (without .glb) to process; default: "
                         "every *_redraw body")
    args = ap.parse_args()

    reference = {"male": luminous_reference("male"), "female": luminous_reference("female")}
    print("Luminous's own radii (targets are %.0f%% of these):" % (TARGET_FRACTION * 100))
    for gender, r in reference.items():
        print("  %s: %s" % (gender, {k: round(v, 4) for k, v in r.items()}))

    races = args.races or sorted(p.stem for p in RACES.glob("*_redraw.glb"))
    for race in races:
        gender = "female" if "female" in race else "male"
        print("%s (%s):" % (race, gender))
        print(" ", process(RACES / (race + ".glb"), reference, gender))
    return 0


if __name__ == "__main__":
    sys.exit(main())

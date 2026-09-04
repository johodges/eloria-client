from __future__ import annotations

"""Rebuild a race body on Luminous's own geometry/rig BELOW THE NECK,
keeping the source race's own head+eyes mesh and texture UNTOUCHED,
grafted onto Luminous's neck.

Root motive (see the session's own diagnosis): every non-Luminous body's
limbs come from an INDEPENDENT Meshy 2D->3D reconstruction, so their
thickness, and occasionally their pose and even their skin weighting,
vary in ways no amount of post-hoc correction fully closes out. Building
every race's torso/arms/legs directly on Luminous's own already-correct
body sidesteps that at the source: the skeleton was already proven
identical, and now the SKIN (mesh + weights) below the neck is
Luminous's own too, not a fresh reconstruction per race.

The head is handled completely differently, and this was NOT the first
design tried here. The first version baked the source race's own head
texture onto LUMINOUS's head shape too, via the same kind of
bone-relative correspondence used for limbs. That worked passably for
the two male bodies checked (Orun, Greyhaven) -- both amount to a
fairly flat skin tone plus a simple painted-on blindfold, which a
per-face nearest-neighbour bake can place well enough. It broke badly
on the female bodies: their faces carry far more identity (real
eyes/brows/lips, and in Orun Female's case painted facial markings)
than a coarse per-face correspondence can place coherently -- the
result was scrambled, not just low-detail. Per the user's own call
after seeing that failure, the head is no longer rebuilt at all: each
race keeps its OWN head+eyes mesh and texture completely unchanged,
grafted onto Luminous's neck. The known cost of this is a possible
visible seam where the two meshes meet, if the source's own neck rim
does not line up with Luminous's -- accepted as a smaller, more
tractable problem than full head correspondence.

The wardrobe materials (shirt/pants/boots) need no work of either kind:
checked directly, they render from a SEPARATE image via flat runtime
tinting (AppearanceVariants), not from Material_1 at all, and Luminous's
own wardrobe geometry is kept as-is since the source body it used to
belong to is being discarded below the neck anyway.

Below-the-neck correspondence is by BONE-RELATIVE position, not raw 3D
coordinates: (dominant bone, fraction along the bone's own axis, angle
around that axis) -- normalized so it does not care that the two bodies
are different sizes or slightly different proportions, only that a
point on Luminous's forearm at 40% along it and forward-facing
corresponds to whatever is at 40% along and forward-facing on the
source body's own forearm. The output is PER-FACE (one flat colour per
Luminous face, sampled from its corresponding source face's own
texture), not a full per-pixel projection: this mesh is low-poly
enough, and already flat-shaded per facet, that a per-pixel bake would
not read as more detailed in practice.

Only the true skin classes (body, eyes, skin_accent -- see
split_race_surfaces.CLASSES for the full set, which also includes hair
and the wardrobe surfaces) ever enter this correspondence. Checked
directly: a "body" face and a "wardrobe_shirt" face can share the same
dominant joint right at the collar, and correspondence only compares
dominant-bone position -- it does not know or care which class a face
belongs to. Including wardrobe let a handful of collar/cuff-adjacent
skin faces match a wardrobe face on the source side, then sample ITS uv
against Material_1 (the wrong image for that uv entirely, since
wardrobe's own uv layout was built for its own separate texture),
producing small dark garbage patches at every skin/cloth seam.
"""

import copy
import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from split_race_surfaces import (  # noqa: E402
    RACES, accessor_array, append_accessor, append_view,
    bone_rest_position, read_glb, write_glb,
)
from thicken_limbs import SEGMENT_FAR_BONE, luminous_reference  # noqa: E402

# Only these classes carry real per-race skin detail on Material_1 --
# see the module docstring for why the rest (hair, wardrobe_*) must
# stay out of this correspondence entirely.
SKIN_CLASSES = ("body", "eyes", "skin_accent")

# (near, far) axis per bone used for below-neck correspondence. "Head"
# deliberately has no entry: the source's own head is grafted wholesale
# (see graft_source_head), never retextured, so a Head-dominant face
# simply falls back to being unmatched here -- harmless, since those
# faces get removed from Luminous's own mesh entirely regardless of
# what colour they would have baked to.
LIMB_AXES = {
    "upperarm_l": "lowerarm_l", "upperarm_r": "lowerarm_r",
    "lowerarm_l": "hand_l", "lowerarm_r": "hand_r",
    "hand_l": "middle_02_l", "hand_r": "middle_02_r",
    "thigh_l": "calf_l", "thigh_r": "calf_r",
    "calf_l": "foot_l", "calf_r": "foot_r",
    "foot_l": "ball_l", "foot_r": "ball_r",
    "spine_01": "spine_02", "spine_02": "spine_03", "spine_03": "neck_01",
    "neck_01": "Head", "pelvis": "spine_01",
}
# Each finger is its own 4-bone chain (e.g. middle_01/02/03_l then a
# "leaf" tip bone) -- checked directly, "hand_l"'s own weight only
# dominates the palm and first knuckle or so; individual finger bones
# take over dominance further out, and with no axis entry of their own
# those faces fell back to Luminous's own pale skin, producing a
# visible two-tone patch right at the fingertips (most visible on the
# female bodies, whose thinner fingers give the fallback patch
# proportionally more of the finger's surface).
for _finger in ("index", "middle", "ring", "pinky", "thumb"):
    for _side in ("l", "r"):
        LIMB_AXES["%s_01_%s" % (_finger, _side)] = "%s_02_%s" % (_finger, _side)
        LIMB_AXES["%s_02_%s" % (_finger, _side)] = "%s_03_%s" % (_finger, _side)
        LIMB_AXES["%s_03_%s" % (_finger, _side)] = "%s_04_leaf_%s" % (_finger, _side)
HEAD_BONE = "Head"

# A source face whose sampled colour's brightest channel falls below
# this FRACTION of that race's own median skin brightness is treated as
# "never actually captured" rather than a real dark colour -- checked
# directly: candidates near the collar came back as near-uniform
# (23, 20, 18)-style triples, unlike any real skin tone measured nearby.
# Almost certainly a surface the source body's own generation never saw
# (hidden under the collar in its resting pose) and filled with a
# placeholder instead of real data.
#
# This was a FIXED brightness threshold at first (35) -- it promptly
# broke on Stoneborn, whose real stone-grey skin has a median max
# channel of only 73 (Orun and Greyhaven are both above 180), so a
# meaningful slice of her genuinely dark skin was being discarded as
# "no data" and falling back to Luminous's own pale tone instead.
# Scaling by each race's own median (measured across every skin-class
# face, not just a handful) keeps the same relative sensitivity
# regardless of how dark or light that race's skin actually is; the
# clip keeps it sane at either extreme (a race with almost no dark
# faces at all, or one darker still than Stoneborn).
NO_DATA_FRACTION_OF_MEDIAN = 0.22
NO_DATA_MIN_THRESHOLD = 12
NO_DATA_MAX_THRESHOLD = 60


def read_material_1_texture(document, binary):
    for i, mat in enumerate(document["materials"]):
        if mat.get("name") == "Material_1":
            tex_index = mat["pbrMetallicRoughness"]["baseColorTexture"]["index"]
            image_index = document["textures"][tex_index]["source"]
            image = document["images"][image_index]
            view = document["bufferViews"][image["bufferView"]]
            start = 8 + view.get("byteOffset", 0)
            return Image.open(io.BytesIO(bytes(
                binary[start:start + view["byteLength"]]))).convert("RGB"), image_index, i
    raise RuntimeError("no Material_1 found")


def find_node(document, name):
    for i, n in enumerate(document["nodes"]):
        if n.get("name") == name:
            return i, n
    raise KeyError(name)


def joint_names(document, skin_index):
    skin = document["skins"][skin_index]
    return [document["nodes"][j].get("name", "") for j in skin["joints"]]


def body_faces_data(document, binary):
    """positions, uvs, indices(faces Nx3), skin_index for the shared
    skin mesh (see split_race_surfaces's own module docstring:
    attributes are shared across every class primitive in this split)."""
    nodes = [n for n in document["nodes"] if n.get("name") in SKIN_CLASSES and "mesh" in n]
    prim = document["meshes"][nodes[0]["mesh"]]["primitives"][0]
    positions = accessor_array(document, binary, prim["attributes"]["POSITION"])
    uvs = accessor_array(document, binary, prim["attributes"]["TEXCOORD_0"])
    skin_index = nodes[0]["skin"]
    all_faces = []
    for n in nodes:
        p = document["meshes"][n["mesh"]]["primitives"][0]
        idx = accessor_array(document, binary, p["indices"]).reshape(-1, 3).astype(np.int64)
        all_faces.append(idx)
    faces = np.concatenate(all_faces, axis=0)
    return positions, uvs, faces, skin_index


def bone_descriptor(document, binary, skin_index, centroids, dominant, names):
    """{joint_row: (t_fraction, angle)} descriptor array for every face,
    keyed by which joint row is dominant. `angle` is measured around the
    bone's own axis from a fixed reference direction (+Z projected
    perpendicular to the axis), so it means the same thing on any body
    regardless of size. Faces with no LIMB_AXES entry for their dominant
    bone (Head chief among them) are left as NaN -- see the module
    docstring for why Head is deliberately absent."""
    descriptors = np.full((len(centroids), 2), np.nan)
    for row in np.unique(dominant):
        name = names[row]
        far = LIMB_AXES.get(name)
        if far is None:
            continue
        a = bone_rest_position(document, binary, skin_index, name)
        b = bone_rest_position(document, binary, skin_index, far)
        axis = b - a
        axis_len = np.linalg.norm(axis)
        if axis_len < 1e-6:
            continue
        unit = axis / axis_len
        # reference direction for angle=0: global +Z, or +Y if the axis
        # is itself nearly vertical (spine/neck), projected perpendicular
        ref = np.array([0.0, 0.0, 1.0])
        if abs(unit @ ref) > 0.9:
            ref = np.array([1.0, 0.0, 0.0])
        ref = ref - (ref @ unit) * unit
        ref = ref / np.linalg.norm(ref)
        binorm = np.cross(unit, ref)

        sel = dominant == row
        v = centroids[sel] - a
        t = (v @ unit) / axis_len
        perp = v - np.outer(v @ unit, unit)
        x = perp @ ref
        y = perp @ binorm
        angle = np.arctan2(y, x)
        descriptors[sel, 0] = t
        descriptors[sel, 1] = angle
    return descriptors


def sample_face_colors(uv_centroids, texture_arr, tex_w, tex_h):
    """RGB at each face's own UV centroid, for every face at once."""
    px = np.clip(uv_centroids[:, 0] % 1.0, 0, 1) * (tex_w - 1)
    py = np.clip(uv_centroids[:, 1] % 1.0, 0, 1) * (tex_h - 1)
    return texture_arr[py.astype(np.int64), px.astype(np.int64)]


def build_correspondence(luminous_desc, luminous_dominant, source_desc, source_dominant,
                          source_no_data):
    """For each Luminous face, the index of its best-matching source
    face: same dominant joint, closest (t, angle) -- angle compared on
    the circle (wrap-around aware). `source_no_data` (see
    NO_DATA_FRACTION_OF_MEDIAN) excludes source faces with no real baked
    colour from candidacy -- the neck is the main place this matters here: skin
    just under the collar is hidden in the source body's own resting
    pose, so a handful of neck_01-dominant faces there have placeholder
    near-black texture instead of real data."""
    correspondence = np.full(len(luminous_dominant), -1, dtype=np.int64)
    for row in np.unique(luminous_dominant):
        lum_sel = np.flatnonzero((luminous_dominant == row) & ~np.isnan(luminous_desc[:, 0]))
        src_sel = np.flatnonzero((source_dominant == row) & ~np.isnan(source_desc[:, 0])
                                  & ~source_no_data)
        if len(lum_sel) == 0 or len(src_sel) == 0:
            continue
        lum_t = luminous_desc[lum_sel, 0][:, None]
        lum_a = luminous_desc[lum_sel, 1][:, None]
        src_t = source_desc[src_sel, 0][None, :]
        src_a = source_desc[src_sel, 1][None, :]
        dt = lum_t - src_t
        da = np.arctan2(np.sin(lum_a - src_a), np.cos(lum_a - src_a))
        # t matters more than angle for a thin limb; weighted combined distance
        dist = dt * dt * 4.0 + da * da
        best = np.argmin(dist, axis=1)
        correspondence[lum_sel] = src_sel[best]
    return correspondence


def fill_unmatched_from_nearest(correspondence, centroids):
    """For a face with no match at all, borrow its nearest already-
    matched neighbour's result (by plain 3D distance on Luminous's own
    mesh) instead of falling back to Luminous's own pale default.

    A row can end up with zero source candidates for reasons that have
    nothing to do with a bad correspondence: checked directly on
    Stoneborn Female, her own "thumb_01" has NO vertices at all for
    which it is the dominant weight (her automatic skinning gave that
    whole segment to a neighbouring bone instead) -- a real per-body
    weight-painting difference, not a bug this tool can fix by adding
    another named axis, since there is nothing on that axis to match
    against. Every gap seen so far (this one, and a smaller one at
    finger-tip "leaf" bones with no further bone to define an axis
    against) is small and localized, so borrowing color from whatever
    real match already exists right next to it reads as a seamless
    continuation rather than the sharp two-tone patch a fall back to
    Luminous's own skin produces. Faces that will be discarded anyway
    (Head-dominant, stripped in strip_luminous_head) get filled too;
    harmless, since their colour is never used."""
    unmatched = np.flatnonzero(correspondence < 0)
    matched = np.flatnonzero(correspondence >= 0)
    if len(unmatched) == 0 or len(matched) == 0:
        return correspondence
    out = correspondence.copy()
    matched_points = centroids[matched]
    chunk = 2000
    for start in range(0, len(unmatched), chunk):
        block = unmatched[start:start + chunk]
        dist = np.linalg.norm(centroids[block][:, None, :] - matched_points[None, :, :], axis=2)
        nearest = matched[np.argmin(dist, axis=1)]
        out[block] = correspondence[nearest]
    return out


def remap_joint_rows(source_names, target_names, joints_int):
    """JOINTS_0 values are ROW indices into a skin's own joints list, so
    grafting onto a DIFFERENT skin (Luminous's) needs each row
    translated by joint NAME, not assumed identical -- checked directly
    for Orun Male, the row order already happens to match Luminous's
    exactly, but nothing guarantees that for every race, and this is
    cheap insurance against a silently mis-skinned graft if one differs."""
    lookup = np.array([target_names.index(n) for n in source_names], dtype=np.int64)
    return lookup[joints_int]


def compact_submesh(positions, normals, uvs, joints, weights, faces_groups):
    """Slice shared per-vertex arrays down to just the vertices used by
    `faces_groups` (a list of Nx3 face arrays sharing the same vertex
    buffer), remapping every group's faces into the resulting compact
    0..K-1 range. Needed because the source's full body/eyes vertex
    buffer covers the WHOLE body, not just the head being grafted."""
    all_faces = np.concatenate(faces_groups, axis=0)
    used = np.unique(all_faces)
    remap = np.full(positions.shape[0], -1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    remapped_groups = [remap[g] for g in faces_groups]
    return (positions[used], normals[used], uvs[used], joints[used], weights[used],
            remapped_groups)


def embed_source_material(document, binary, src_doc, src_bin, src_material_index):
    """Copy a source material into `document` as a new material, along
    with a fresh, byte-identical copy of whatever image(s) its texture
    slots reference -- the source's own head keeps its own REAL texture
    untouched, not a bake, so this must preserve it exactly rather than
    re-encoding through PIL. Material_1 in practice references the same
    single image from two different texture slots (baseColorTexture AND
    emissiveTexture, the latter giving the skin its shadeless-bright
    look); image bytes are deduped by source image index so that does
    not create two copies."""
    image_cache, texture_cache = {}, {}

    def remap(tex_info):
        if tex_info is None:
            return
        old_tex_idx = tex_info["index"]
        if old_tex_idx not in texture_cache:
            src_texture = src_doc["textures"][old_tex_idx]
            image_idx_src = src_texture["source"]
            if image_idx_src not in image_cache:
                image = src_doc["images"][image_idx_src]
                view = src_doc["bufferViews"][image["bufferView"]]
                start = 8 + view.get("byteOffset", 0)
                raw_bytes = bytes(src_bin[start:start + view["byteLength"]])
                new_view = append_view(document, binary, raw_bytes)
                new_image_idx = len(document["images"])
                document["images"].append(
                    {"bufferView": new_view, "mimeType": image.get("mimeType", "image/png")})
                image_cache[image_idx_src] = new_image_idx
            new_texture = dict(src_texture)
            new_texture["source"] = image_cache[image_idx_src]
            texture_cache[old_tex_idx] = len(document["textures"])
            document["textures"].append(new_texture)
        tex_info["index"] = texture_cache[old_tex_idx]

    new_material = copy.deepcopy(src_doc["materials"][src_material_index])
    pbr = new_material.get("pbrMetallicRoughness", {})
    remap(pbr.get("baseColorTexture"))
    remap(pbr.get("metallicRoughnessTexture"))
    remap(new_material.get("normalTexture"))
    remap(new_material.get("occlusionTexture"))
    remap(new_material.get("emissiveTexture"))
    new_material_index = len(document["materials"])
    document["materials"].append(new_material)
    return new_material_index


def strip_luminous_head(document, binary, lum_names):
    """Remove Luminous's own Head-dominant faces from her "body" mesh
    (everything else -- torso, arms, legs, hands, feet -- stays) and
    make her "eyes" node render nothing. Both are about to be replaced
    by the source race's own, so keeping them around would just double
    up geometry inside the same UV/vertex space the graft occupies.

    The eyes node is emptied in place (mesh/skin keys dropped) rather
    than unlinked from Armature's children list -- checked directly,
    Godot's glTF importer errors ("Unable to find node N") on a node
    that is present in the document but no longer reachable from any
    scene root, so an orphaned-but-still-listed node is not safe;
    leaving it in the hierarchy as an inert empty transform is."""
    body_idx, body_node = find_node(document, "body")
    body_prim = document["meshes"][body_node["mesh"]]["primitives"][0]
    positions = accessor_array(document, binary, body_prim["attributes"]["POSITION"])
    joints = accessor_array(document, binary, body_prim["attributes"]["JOINTS_0"]).astype(np.int64)
    weights = accessor_array(document, binary, body_prim["attributes"]["WEIGHTS_0"])
    dominant = joints[np.arange(len(joints)), np.argmax(weights, axis=1)]
    head_row = lum_names.index(HEAD_BONE)

    faces = accessor_array(document, binary, body_prim["indices"]).reshape(-1, 3).astype(np.int64)
    keep = dominant[faces[:, 0]] != head_row
    new_faces = faces[keep].astype(np.uint32).reshape(-1)
    body_prim["indices"] = append_accessor(document, binary, new_faces, 5125, "SCALAR")

    _, eyes_node = find_node(document, "eyes")
    eyes_node.pop("mesh", None)
    eyes_node.pop("skin", None)


def graft_source_head(document, binary, lum_names, src_doc, src_bin):
    """Attach the source race's own head+eyes mesh (unchanged geometry
    AND texture) as a new node on `document`, skinned onto Luminous's
    own already-shared skeleton by joint NAME. See the module docstring
    for why the head is grafted wholesale rather than retextured."""
    _, src_body_node = find_node(src_doc, "body")
    _, src_eyes_node = find_node(src_doc, "eyes")
    body_prim = src_doc["meshes"][src_body_node["mesh"]]["primitives"][0]
    eyes_prim = src_doc["meshes"][src_eyes_node["mesh"]]["primitives"][0]

    positions = accessor_array(src_doc, src_bin, body_prim["attributes"]["POSITION"])
    normals = accessor_array(src_doc, src_bin, body_prim["attributes"]["NORMAL"])
    uvs = accessor_array(src_doc, src_bin, body_prim["attributes"]["TEXCOORD_0"])
    joints = accessor_array(src_doc, src_bin, body_prim["attributes"]["JOINTS_0"]).astype(np.int64)
    weights = accessor_array(src_doc, src_bin, body_prim["attributes"]["WEIGHTS_0"])

    src_skin_index = src_body_node["skin"]
    src_names = joint_names(src_doc, src_skin_index)
    head_row = src_names.index(HEAD_BONE)
    dominant = joints[np.arange(len(joints)), np.argmax(weights, axis=1)]

    body_faces = accessor_array(src_doc, src_bin, body_prim["indices"]).reshape(-1, 3).astype(np.int64)
    eyes_faces = accessor_array(src_doc, src_bin, eyes_prim["indices"]).reshape(-1, 3).astype(np.int64)
    head_faces = body_faces[dominant[body_faces[:, 0]] == head_row]

    pos_c, norm_c, uv_c, joints_c, weights_c, (head_faces_c, eyes_faces_c) = compact_submesh(
        positions, normals, uvs, joints, weights, [head_faces, eyes_faces])
    joints_remapped = remap_joint_rows(src_names, lum_names, joints_c)

    attrs = {
        "POSITION": append_accessor(document, binary, pos_c.astype(np.float32), 5126, "VEC3"),
        "NORMAL": append_accessor(document, binary, norm_c.astype(np.float32), 5126, "VEC3"),
        "TEXCOORD_0": append_accessor(document, binary, uv_c.astype(np.float32), 5126, "VEC2"),
        "JOINTS_0": append_accessor(document, binary, joints_remapped.astype(np.uint8), 5121, "VEC4"),
        "WEIGHTS_0": append_accessor(document, binary, weights_c.astype(np.float32), 5126, "VEC4"),
    }
    head_idx_acc = append_accessor(
        document, binary, head_faces_c.astype(np.uint32).reshape(-1), 5125, "SCALAR")
    eyes_idx_acc = append_accessor(
        document, binary, eyes_faces_c.astype(np.uint32).reshape(-1), 5125, "SCALAR")

    material_index = embed_source_material(document, binary, src_doc, src_bin, body_prim["material"])

    mesh_index = len(document["meshes"])
    document["meshes"].append({"primitives": [
        {"attributes": attrs, "indices": head_idx_acc, "material": material_index},
        {"attributes": attrs, "indices": eyes_idx_acc, "material": material_index},
    ]})

    _, lum_body_node = find_node(document, "body")
    node_index = len(document["nodes"])
    document["nodes"].append({"name": "head_source", "mesh": mesh_index, "skin": lum_body_node["skin"]})
    _, armature_node = find_node(document, "Armature")
    armature_node["children"].append(node_index)


# Ssarathi-only: how far a vertex dominant-weighted to a leg bone can sit
# from that bone's own rest axis before it counts as tail rather than
# leg flesh -- see tail_vertex_mask. Deliberately the SAME conservative
# 1.5x fix_ssarathi_tail_weights.py verified (not an import of
# thicken_limbs.MAX_SANE_RATIO -- that constant has since been loosened
# to 3.0 for a different job, and would silently move this one too).
#
# Lowering this to catch more of the tail was tried and reverted: at
# 1.0x the farthest "flagged" vertices turned out to be real foot
# vertices (Y close to 0, dominant on calf_l) rather than more tail --
# a foot is not a simple cylinder around the calf's own axis, so its
# real, correct geometry already sits well outside a tight radius
# around that axis, indistinguishable from genuine tail contamination
# by this measure alone. At 0.5x the flagged fraction of thigh_l alone
# reached 774/837 (92%), i.e. this stopped measuring "is this tail" at
# all. Extraction with this conservative threshold only recovers the
# tail's unambiguous outer portion, not its root -- a known, currently
# unresolved gap; see the module docstring.
TAIL_DISTANCE_RATIO = 1.5


def tail_vertex_mask(document, binary, positions, dominant, skin_index, luminous_ref):
    """True for every vertex dominant-weighted to a leg bone (thigh/calf)
    but sitting further from that bone's own rest axis than a real leg
    segment plausibly reaches. Ssarathi's tail has no bone of its own in
    the canonical rig, so the auto-weighting step gave its vertices to
    the nearest existing bone instead; this is the same technique
    fix_ssarathi_tail_weights.py already verified identifies it (see
    that file for the fuller derivation), reimplemented locally rather
    than imported so this tool does not depend on a script meant to be
    run standalone, and does not inherit its drifted MAX_SANE_RATIO."""
    names = joint_names(document, skin_index)
    mask = np.zeros(len(positions), dtype=bool)
    for part in ("thigh", "calf"):
        for side in ("l", "r"):
            near = "%s_%s" % (part, side)
            if near not in names:
                continue
            far = "%s_%s" % (SEGMENT_FAR_BONE[part], side)
            a = bone_rest_position(document, binary, skin_index, near)
            b = bone_rest_position(document, binary, skin_index, far)
            unit = (b - a) / np.linalg.norm(b - a)
            row = names.index(near)
            sel = dominant == row
            if not sel.any():
                continue
            v = positions[sel] - a
            perp = np.linalg.norm(v - np.outer(v @ unit, unit), axis=1)
            contaminated = perp > TAIL_DISTANCE_RATIO * luminous_ref[part]
            idx = np.flatnonzero(sel)
            mask[idx[contaminated]] = True
    return mask


def graft_source_tail(document, binary, lum_names, src_doc, src_bin, gender):
    """Ssarathi-only: her tail rides on a leg bone's weight (see
    tail_vertex_mask) since the canonical rig has no tail bone at all.
    A no-op for every other race -- checked directly, none of their legs
    trip this threshold (thicken_limbs.py already had to fix the ones
    that used to). Grafted fully RIGID to Luminous's own "pelvis",
    matching what the LIVE, already-shipped Ssarathi bodies do (their
    own models.json note: "the tail is static, as it is in game").
    fix_ssarathi_tail_weights.py feathers this same reweighting instead
    of doing it rigidly, but that solves a DIFFERENT problem: keeping
    the tail mesh-CONTINUOUS with the real leg flesh it used to sit
    next to, so a hard weight cut there does not tear during animation.
    Here the tail is a separate floating node, not stitched to
    Luminous's own leg mesh at all, so there is no shared-mesh seam to
    feather across.

    KNOWN GAP, not yet solved: TAIL_DISTANCE_RATIO's conservative 1.5x
    only recovers the tail's unambiguous outer portion, not its root --
    checked directly, the resulting graft renders as a small stub near
    the pelvis, not a complete tail. Loosening the threshold does not
    fix this: at 1.0x the newly-caught "tail" vertices turned out to be
    real foot geometry (a foot is not a cylinder around the calf's own
    axis, so its correct shape already sits outside a tight radius of
    it); at 0.5x, 92% of thigh_l's own vertices got flagged, i.e. the
    measure had stopped meaning "tail" at all. Also discovered while
    investigating: some of the tail's own vertices are dominant-
    weighted to "pelvis" already (its root, being closest to the
    pelvis, is not on a leg bone at all), which this function does not
    look for -- a real avenue for a more complete fix, not yet
    implemented. This needs either a smarter per-vertex signal (e.g.
    distance from the body's own reference silhouette at that height,
    rather than from one bone's own axis) or the mesh-connectivity
    growth approach fix_ssarathi_tail_weights.py's own docstring
    describes trying and only getting to work on the female body."""
    _, src_body_node = find_node(src_doc, "body")
    body_prim = src_doc["meshes"][src_body_node["mesh"]]["primitives"][0]
    positions = accessor_array(src_doc, src_bin, body_prim["attributes"]["POSITION"])
    normals = accessor_array(src_doc, src_bin, body_prim["attributes"]["NORMAL"])
    uvs = accessor_array(src_doc, src_bin, body_prim["attributes"]["TEXCOORD_0"])
    joints = accessor_array(src_doc, src_bin, body_prim["attributes"]["JOINTS_0"]).astype(np.int64)
    weights = accessor_array(src_doc, src_bin, body_prim["attributes"]["WEIGHTS_0"])
    src_skin_index = src_body_node["skin"]
    dominant = joints[np.arange(len(joints)), np.argmax(weights, axis=1)]

    mask = tail_vertex_mask(src_doc, src_bin, positions, dominant, src_skin_index,
                             luminous_reference(gender))
    if not mask.any():
        return False

    body_faces = accessor_array(src_doc, src_bin, body_prim["indices"]).reshape(-1, 3).astype(np.int64)
    tail_faces = body_faces[mask[body_faces].all(axis=1)]
    if len(tail_faces) == 0:
        return False

    pos_c, norm_c, uv_c, _, _, (tail_faces_c,) = compact_submesh(
        positions, normals, uvs, joints, weights, [tail_faces])
    vertex_count = len(pos_c)

    lum_pelvis_row = lum_names.index("pelvis")
    rigid_joints = np.zeros((vertex_count, 4), dtype=np.uint8)
    rigid_joints[:, 0] = lum_pelvis_row
    rigid_weights = np.zeros((vertex_count, 4), dtype=np.float32)
    rigid_weights[:, 0] = 1.0

    attrs = {
        "POSITION": append_accessor(document, binary, pos_c.astype(np.float32), 5126, "VEC3"),
        "NORMAL": append_accessor(document, binary, norm_c.astype(np.float32), 5126, "VEC3"),
        "TEXCOORD_0": append_accessor(document, binary, uv_c.astype(np.float32), 5126, "VEC2"),
        "JOINTS_0": append_accessor(document, binary, rigid_joints, 5121, "VEC4"),
        "WEIGHTS_0": append_accessor(document, binary, rigid_weights, 5126, "VEC4"),
    }
    tail_idx_acc = append_accessor(
        document, binary, tail_faces_c.astype(np.uint32).reshape(-1), 5125, "SCALAR")

    material_index = embed_source_material(document, binary, src_doc, src_bin, body_prim["material"])

    mesh_index = len(document["meshes"])
    document["meshes"].append({"primitives": [
        {"attributes": attrs, "indices": tail_idx_acc, "material": material_index},
    ]})

    _, lum_body_node = find_node(document, "body")
    node_index = len(document["nodes"])
    document["nodes"].append({"name": "tail_source", "mesh": mesh_index, "skin": lum_body_node["skin"]})
    _, armature_node = find_node(document, "Armature")
    armature_node["children"].append(node_index)
    return True


def process(luminous_path: Path, source_path: Path, out_path: Path, gender: str) -> str:
    lum_doc, lum_bin = read_glb(luminous_path)
    src_doc, src_bin = read_glb(source_path)

    lum_pos, lum_uv, lum_faces, lum_skin = body_faces_data(lum_doc, lum_bin)
    src_pos, src_uv, src_faces, src_skin = body_faces_data(src_doc, src_bin)

    lum_names = joint_names(lum_doc, lum_skin)
    src_names = joint_names(src_doc, src_skin)

    lum_prim0 = lum_doc["meshes"][
        [n for n in lum_doc["nodes"] if n.get("name") in SKIN_CLASSES and "mesh" in n][0]["mesh"]
    ]["primitives"][0]
    lum_joints = accessor_array(lum_doc, lum_bin, lum_prim0["attributes"]["JOINTS_0"]).astype(np.int64)
    lum_weights = accessor_array(lum_doc, lum_bin, lum_prim0["attributes"]["WEIGHTS_0"])
    lum_vertex_dominant = lum_joints[np.arange(len(lum_joints)), np.argmax(lum_weights, axis=1)]
    lum_face_dominant = lum_vertex_dominant[lum_faces[:, 0]]  # one vertex is enough per-face

    src_prim0 = src_doc["meshes"][
        [n for n in src_doc["nodes"] if n.get("name") in SKIN_CLASSES and "mesh" in n][0]["mesh"]
    ]["primitives"][0]
    src_joints = accessor_array(src_doc, src_bin, src_prim0["attributes"]["JOINTS_0"]).astype(np.int64)
    src_weights = accessor_array(src_doc, src_bin, src_prim0["attributes"]["WEIGHTS_0"])
    src_vertex_dominant = src_joints[np.arange(len(src_joints)), np.argmax(src_weights, axis=1)]
    src_face_dominant = src_vertex_dominant[src_faces[:, 0]]

    lum_centroids = lum_pos[lum_faces].mean(axis=1)
    src_centroids = src_pos[src_faces].mean(axis=1)

    lum_desc = bone_descriptor(lum_doc, lum_bin, lum_skin, lum_centroids, lum_face_dominant, lum_names)
    src_desc = bone_descriptor(src_doc, src_bin, src_skin, src_centroids, src_face_dominant, src_names)

    src_texture, _, _ = read_material_1_texture(src_doc, src_bin)
    src_tex_arr = np.asarray(src_texture)
    sw, sh = src_texture.size
    src_uv_centroids = src_uv[src_faces].mean(axis=1)
    src_colors = sample_face_colors(src_uv_centroids, src_tex_arr, sw, sh)
    src_brightness = src_colors.max(axis=1)
    no_data_threshold = np.clip(np.median(src_brightness) * NO_DATA_FRACTION_OF_MEDIAN,
                                 NO_DATA_MIN_THRESHOLD, NO_DATA_MAX_THRESHOLD)
    src_no_data = src_brightness < no_data_threshold

    correspondence = build_correspondence(lum_desc, lum_face_dominant, src_desc, src_face_dominant,
                                           src_no_data)
    correspondence = fill_unmatched_from_nearest(correspondence, lum_centroids)

    lum_texture, lum_image_index, lum_material_index = read_material_1_texture(lum_doc, lum_bin)
    out_image = Image.new("RGB", lum_texture.size)
    draw = ImageDraw.Draw(out_image)
    lw, lh = lum_texture.size

    matched, unmatched = 0, 0
    for i, face in enumerate(lum_faces):
        src_face_idx = correspondence[i]
        if src_face_idx < 0:
            unmatched += 1
            color = tuple(int(c) for c in np.asarray(lum_texture)[
                int(lum_uv[face, 1].mean() * (lh - 1)), int(lum_uv[face, 0].mean() * (lw - 1))])
        else:
            matched += 1
            u, v = src_uv_centroids[src_face_idx]
            px = int(np.clip(u % 1.0, 0, 1) * (sw - 1))
            py = int(np.clip(v % 1.0, 0, 1) * (sh - 1))
            color = tuple(int(c) for c in src_tex_arr[py, px])
        tri = [(float(np.clip(lum_uv[v_, 0] % 1.0, 0, 1)) * lw,
               float(np.clip(lum_uv[v_, 1] % 1.0, 0, 1)) * lh) for v_ in face]
        draw.polygon(tri, fill=color)

    out_bytes = io.BytesIO()
    out_image.save(out_bytes, format="PNG")
    payload = out_bytes.getvalue()

    document, binary = read_glb(luminous_path)
    view_index = append_view(document, binary, payload)
    document["images"][lum_image_index]["bufferView"] = view_index
    document["images"][lum_image_index].pop("uri", None)

    strip_luminous_head(document, binary, lum_names)
    graft_source_head(document, binary, lum_names, src_doc, src_bin)
    grafted_tail = graft_source_tail(document, binary, lum_names, src_doc, src_bin, gender)

    write_glb(out_path, document, binary)
    return ("below-neck: matched %d/%d faces, %d used Luminous's own texture as fallback; "
            "head+eyes grafted from the source unchanged%s" % (
                matched, len(lum_faces), unmatched,
                "; tail grafted (rigid to pelvis)" if grafted_tail else ""))


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(
        description="rebuild a race body's torso/limbs on Luminous's own geometry, "
                    "keeping the source's own head+eyes mesh unchanged")
    ap.add_argument("source_race", help="race glb stem to take the skin/head from")
    ap.add_argument("--gender", required=True, choices=["male", "female"])
    ap.add_argument("--out", required=True, help="output glb stem")
    args = ap.parse_args()

    luminous_path = RACES / ("luminous_%s.glb" % args.gender)
    source_path = RACES / (args.source_race + ".glb")
    out_path = RACES / (args.out + ".glb")
    print(process(luminous_path, source_path, out_path, args.gender))
    return 0


if __name__ == "__main__":
    sys.exit(main())

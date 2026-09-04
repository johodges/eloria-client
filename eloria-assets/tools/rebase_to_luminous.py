from __future__ import annotations

"""Prototype: rebuild a race body from Luminous's own geometry/rig, with
the race's own skin texture baked onto Luminous's UV layout.

Root motive (see the session's own diagnosis): every non-Luminous body's
limbs come from an INDEPENDENT Meshy 2D->3D reconstruction, so their
thickness, and occasionally their pose and even their skin weighting,
vary in ways no amount of post-hoc correction fully closes out. Building
every race directly on Luminous's own already-correct body sidesteps
that at the source: the skeleton was already proven identical, and now
the SKIN (mesh + weights) is Luminous's own too, not a fresh
reconstruction per race.

The wardrobe materials (shirt/pants/boots) turned out not to need any
of this: checked directly, they carry a flat baseColorFactor set at
RUNTIME by AppearanceVariants, not a baked texture -- only "Material_1"
(the body/eyes surface) has actual image data. So this only has to
transplant the SKIN texture (face, hands, feet, any visible skin), not
the whole body.

Correspondence between Luminous's mesh and the source race's own mesh is
by BONE-RELATIVE position, not raw 3D coordinates -- but a single
parametrization does not fit every body part equally well, so this uses
two different ones depending on what is dominant:

- Limbs/torso/neck (anything with a natural long axis): (dominant bone,
  fraction along the bone's own axis, angle around that axis) --
  normalized so it does not care that the two bodies are different
  sizes or slightly different proportions, only that a point on
  Luminous's forearm at 40% along it and forward-facing corresponds to
  whatever is at 40% along and forward-facing on the source body's own
  forearm.

- The head is NOT just a thick cylinder, so the same axis+angle
  treatment does not work for it -- checked directly, Luminous's and
  Orun's own head-bone-relative bounding boxes do not overlay (Orun's
  head sits measurably further forward relative to the Head bone than
  Luminous's does: Z range [-0.171, 0.061] vs [-0.099, 0.148]), so
  naive bone-relative position matching misaligns facial features
  (confirmed by a first attempt: the face came back mostly as
  Luminous's own fallback colour with stray artifacts). Instead, each
  body's own head is normalized into its own measured bounding box
  (centered at 0, +-1 half-extent per axis) before matching nearest
  neighbour in that normalized space -- removing exactly the per-body
  size/proportion difference that broke the axis+angle approach.

The output is PER-FACE (one flat colour per Luminous face, sampled from
its corresponding source face's own texture), not a full per-pixel
projection: this mesh is low-poly enough, and already flat-shaded per
facet, that a per-pixel bake would not read as more detailed in
practice, and per-face is far simpler to get right.
"""

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

# Only these classes (see split_race_surfaces.CLASSES for the full set)
# carry real per-race skin detail on Material_1 -- "hair"/"wardrobe_*"
# render from a SEPARATE image via flat runtime tinting, and critically
# their own UV coordinates were laid out for THAT image, not this one.
# Checked directly: a "body" face on one bone can share a dominant joint
# with a "wardrobe_shirt" face on the other body (e.g. both dominated by
# neck_01 right at the collar), and correspondence only compares
# dominant-bone position -- it does not know or care which class a face
# belongs to. Including wardrobe let a handful of collar/cuff-adjacent
# skin faces match a wardrobe face on the source side, then sample ITS
# uv against Material_1 (the wrong image for that uv entirely),
# producing small dark garbage patches right at every skin/cloth seam.
SKIN_CLASSES = ("body", "eyes", "skin_accent")

# (near, far) axis per bone used for limb/torso correspondence; the head
# is handled separately below (see head_bbox_descriptor) since it has no
# single useful long axis.
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
HEAD_BONE = "Head"


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


def body_faces_data(document, binary):
    """positions, uvs, indices(faces Nx3), skin_index for the shared
    body/eyes/... mesh (see split_race_surfaces's own module docstring:
    attributes are shared across every class primitive in this split)."""
    nodes = [n for n in document["nodes"] if n.get("name") in SKIN_CLASSES and "mesh" in n]
    prim = document["meshes"][nodes[0]["mesh"]]["primitives"][0]
    positions = accessor_array(document, binary, prim["attributes"]["POSITION"])
    uvs = accessor_array(document, binary, prim["attributes"]["TEXCOORD_0"])
    skin_index = nodes[0]["skin"]
    all_faces, all_uv_faces = [], []
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
    regardless of size. Head-dominant faces are left as NaN here -- see
    head_bbox_descriptor, which handles them separately."""
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


def face_normals(positions, faces):
    """Unit outward-facing normal per face, in the mesh's own untransformed
    space (deliberately NOT bbox-normalized like the position descriptor --
    a normal is a direction, and anisotropically rescaling XYZ to fit a
    box would distort it)."""
    v0 = positions[faces[:, 0]]
    v1 = positions[faces[:, 1]]
    v2 = positions[faces[:, 2]]
    n = np.cross(v1 - v0, v2 - v0)
    length = np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    return n / length


def head_bbox_descriptor(document, binary, skin_index, centroids, normals, dominant, head_row):
    """Per-axis bounding-box-normalized (x, y, z) position plus unit
    normal (nx, ny, nz) descriptor for Head-dominant faces only -- NaN
    elsewhere. Each body's own head is normalized into its own measured
    extent (center at 0, half-extent at 1 on each axis, relative to the
    Head bone's rest position) before matching, which removes exactly the
    per-body size/proportion difference that breaks a single axis+angle
    parametrization for a shape as irregular as a head/face. The normal
    is carried alongside so matching can prefer a similarly-facing
    source face -- position alone let a handful of jaw/chin-underside
    faces (pointing down) match front-facing target faces that merely
    happened to sit nearby in normalized space, producing small dark
    mismatched patches at the jaw/neck boundary."""
    descriptors = np.full((len(centroids), 6), np.nan)
    sel = dominant == head_row
    if not sel.any():
        return descriptors
    head_pos = bone_rest_position(document, binary, skin_index, HEAD_BONE)
    rel = centroids[sel] - head_pos
    lo = rel.min(axis=0)
    hi = rel.max(axis=0)
    center = (lo + hi) / 2.0
    half = np.maximum((hi - lo) / 2.0, 1e-6)
    descriptors[sel, :3] = (rel - center) / half
    descriptors[sel, 3:] = normals[sel]
    return descriptors


def build_correspondence(luminous_desc, luminous_dominant, source_desc, source_dominant,
                          source_no_data):
    """For each Luminous face, the index of its best-matching source
    face: same dominant joint, closest (t, angle) -- angle compared on
    the circle (wrap-around aware). `source_no_data` (see
    NO_DATA_MAX_CHANNEL) excludes source faces with no real baked colour
    from candidacy -- the neck is the main place this matters here: skin
    just under the collar is hidden in the source body's own resting
    pose, so a handful of neck_01-dominant faces there have the same
    kind of placeholder-black texture as the jaw-bottom head faces this
    was first built for."""
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


# How strongly a mismatched facing direction penalizes an otherwise
# close position match, in the head correspondence search -- see
# build_head_correspondence. 0 = ignore facing entirely (the original
# position-only approach); tuned by eye against the jaw/neck speckling
# it was added to fix, not derived from anything more principled.
HEAD_NORMAL_WEIGHT = 1.5

# A source face whose sampled colour is at or below this on every
# channel is treated as "never actually captured" rather than a real
# dark colour -- checked directly (see the diagnostic that motivated
# this: matched candidates near the jaw/neck came back as near-uniform
# (23, 20, 18)-style triples, unlike any real skin/hair tone measured
# nearby, which were bright with a clear hue). Almost certainly a
# surface the source body's own generation never saw (hidden under the
# chin/collar in whatever pose it was captured from) and filled with a
# placeholder instead of real data. A genuinely very dark-skinned race
# could in principle trip this; revisit if one shows a similar hole.
NO_DATA_MAX_CHANNEL = 35


def sample_face_colors(uv_centroids, texture_arr, tex_w, tex_h):
    """RGB at each face's own UV centroid, for every face at once."""
    px = np.clip(uv_centroids[:, 0] % 1.0, 0, 1) * (tex_w - 1)
    py = np.clip(uv_centroids[:, 1] % 1.0, 0, 1) * (tex_h - 1)
    return texture_arr[py.astype(np.int64), px.astype(np.int64)]


def build_head_correspondence(luminous_desc, luminous_dominant, head_row_lum,
                               source_desc, source_dominant, head_row_src,
                               source_no_data):
    """Nearest-neighbour match in per-body bounding-box-normalized
    (x, y, z) space, for Head-dominant faces only -- see
    head_bbox_descriptor. No wrap-around on the position term (unlike the
    limb angle term, a normalized axis position has no periodicity to
    account for). A facing-direction term is added on top: without it, a
    handful of jaw/chin-underside faces on the source matched
    similarly-positioned but front-facing target faces. `source_no_data`
    (see NO_DATA_MAX_CHANNEL) excludes source faces with no real baked
    colour from candidacy entirely -- both of those turned out to matter
    for the dark mismatched patches this was built to fix: the normal
    term alone did not move them, because the picked source face WAS
    well-aligned in both position and facing, it just had no usable
    texture at all."""
    correspondence = np.full(len(luminous_dominant), -1, dtype=np.int64)
    lum_sel = np.flatnonzero((luminous_dominant == head_row_lum) & ~np.isnan(luminous_desc[:, 0]))
    src_sel = np.flatnonzero((source_dominant == head_row_src) & ~np.isnan(source_desc[:, 0])
                              & ~source_no_data)
    if len(lum_sel) == 0 or len(src_sel) == 0:
        return correspondence
    diff = luminous_desc[lum_sel][:, None, :3] - source_desc[src_sel][None, :, :3]
    dist = np.sum(diff * diff, axis=2)
    lum_n = luminous_desc[lum_sel][:, None, 3:]
    src_n = source_desc[src_sel][None, :, 3:]
    dist += HEAD_NORMAL_WEIGHT * (1.0 - np.sum(lum_n * src_n, axis=2))
    best = np.argmin(dist, axis=1)
    correspondence[lum_sel] = src_sel[best]
    return correspondence


def process(luminous_path: Path, source_path: Path, out_path: Path) -> str:
    lum_doc, lum_bin = read_glb(luminous_path)
    src_doc, src_bin = read_glb(source_path)

    lum_pos, lum_uv, lum_faces, lum_skin = body_faces_data(lum_doc, lum_bin)
    src_pos, src_uv, src_faces, src_skin = body_faces_data(src_doc, src_bin)

    lum_skin_obj = lum_doc["skins"][lum_skin]
    lum_names = [lum_doc["nodes"][j].get("name", "") for j in lum_skin_obj["joints"]]
    src_skin_obj = src_doc["skins"][src_skin]
    src_names = [src_doc["nodes"][j].get("name", "") for j in src_skin_obj["joints"]]

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
    src_no_data = src_colors.max(axis=1) < NO_DATA_MAX_CHANNEL

    correspondence = build_correspondence(lum_desc, lum_face_dominant, src_desc, src_face_dominant,
                                           src_no_data)

    if HEAD_BONE in lum_names and HEAD_BONE in src_names:
        lum_head_row = lum_names.index(HEAD_BONE)
        src_head_row = src_names.index(HEAD_BONE)
        lum_normals = face_normals(lum_pos, lum_faces)
        src_normals = face_normals(src_pos, src_faces)
        lum_head_desc = head_bbox_descriptor(
            lum_doc, lum_bin, lum_skin, lum_centroids, lum_normals, lum_face_dominant, lum_head_row)
        src_head_desc = head_bbox_descriptor(
            src_doc, src_bin, src_skin, src_centroids, src_normals, src_face_dominant, src_head_row)
        head_correspondence = build_head_correspondence(
            lum_head_desc, lum_face_dominant, lum_head_row,
            src_head_desc, src_face_dominant, src_head_row, src_no_data)
        head_sel = lum_face_dominant == lum_head_row
        correspondence[head_sel] = head_correspondence[head_sel]

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
    write_glb(out_path, document, binary)
    return "matched %d/%d faces, %d used Luminous's own texture as fallback" % (
        matched, len(lum_faces), unmatched)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="rebuild a race body on Luminous's own geometry")
    ap.add_argument("source_race", help="race glb stem to take the skin texture from")
    ap.add_argument("--gender", required=True, choices=["male", "female"])
    ap.add_argument("--out", required=True, help="output glb stem")
    args = ap.parse_args()

    luminous_path = RACES / ("luminous_%s.glb" % args.gender)
    source_path = RACES / (args.source_race + ".glb")
    out_path = RACES / (args.out + ".glb")
    print(process(luminous_path, source_path, out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())

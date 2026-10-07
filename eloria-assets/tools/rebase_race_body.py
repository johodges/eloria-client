"""Rebase a race body onto the packed Human body; keep its v2 head rigidly.

    python eloria-assets/tools/rebase_race_body.py build   --root <wt> --slug greyhaven_male --out <dir>/greyhaven_male
    python eloria-assets/tools/rebase_race_body.py verify  --root <wt> --slug greyhaven_male --candidate <dir>/greyhaven_male/greyhaven_male.glb --out <dir>/greyhaven_male
    python eloria-assets/tools/rebase_race_body.py install --root <wt> --candidates <dir> --slugs greyhaven_male greyhaven_female
    (Godot: --headless --path <wt>/godot-client --import, repeated until .godot/imported stops growing)
    python eloria-assets/tools/rebase_race_body.py post-import --root <wt> --candidates <dir> --slugs greyhaven_male greyhaven_female

post-import fails when the import re-wrote an installed JSON file (restore it
from <dir>/install/), when a tracked file outside the rebase file list
changed, or when an untracked file appeared that was not there before
install (Godot-extracted textures must match a .gitignore pattern).

Below the neck plane (travel .075 along neck_01->Head) every triangle is a
byte copy of luminous_<sex>.glb, its UNSIGNED_BYTE joints included. Above it
the v2 race head (body[1], eyes, eyebrows, scalp), the head band and cap, the
node list and the inverse-bind bytes are copied from the installed v2 race
GLB, so fitted hair and socketed headwear keep their binds. A smooth bridge
joins the two rims. Images: a re-packed 1024 head atlas baked from the 2048
Meshy source, the Human skin atlas recoloured on skin texels only, the Human
wardrobe atlas unchanged, and a 1024x512 neck cylinder. Images stay unnamed
so Godot extracts them as <slug>_<index>.jpg, which git already ignores.
shared_player_bodies.py is used read-only; its legacy outputs are unchanged.

Per race (P3): the head plane is the v2 GLB's upperCutM (.11; .13 for the
detailed Glasswarden and Ssarathi necks). A Ssarathi race_tail is carried
with its own material: its root ring is sunk into the Human trousers and the
free tail is feathered off thigh_l onto the pelvis (gate V18). When
the inner-wall rule leaves more than 2% of the head hidden, a second pass
drops every robustly hidden face (drop_buried). The v2 graft's in-plane caps
over inner rim loops get their own head-atlas charts (broken_uv). The head
atlas falls back to 2048 when its islands cannot reach the Human face
density at 1024. Mycelari male: one linear gain darkens the head source.

Skin tone: the Human skin's area-weighted median takes the face reference
calibrate_skin_palettes will measure (face_reference), so a unified skin
palette dyes hands and face alike; the neck then bends to the head rim per
azimuth (neck_tone), so a head lighter at the back than at the throat keeps
that down the neck instead of showing a band under the skull. The bridge
profile cannot dip inside both rims (ungroove, gate V19); bridge grain comes
from outer head skin only (band_visibility) and carries no race feature
(feature_weight: colour outliers and sampled-radius steps such as ear lobes),
and V17 also checks how much grain it carries. Install retires the cuff
propagation manifest once no derived race is left in it. V14 also checks
that the mask covers the painted brow strokes and (Stoneborn) iris colour.

toolSHA256 (gate V16) hashes this file with CRLF folded to LF, i.e. the git
blob, so it holds on a Windows autocrlf checkout and on an LF checkout alike.
Any edit of this file still needs a rebuild before V16 passes again.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import datetime
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess

import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation, binary_fill_holes, convolve, gaussian_filter
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

import equipment_authoring as ea
import shared_player_bodies as spb
import verify_shared_player_bodies as vspb
g = spb.g

KEYS = ('POSITION', 'NORMAL', 'TEXCOORD_0', 'JOINTS_0', 'WEIGHTS_0')
LOWER_CUT = .075
RIM_BAND = .002
NECK_H0 = -.160
LUMA = np.array([.2126, .7152, .0722])
DIRECTIONS = 60
JPEG_QUALITY = 92
CHROMA_MAD = 10
LUM_LOG_MAD = 10
# Bridge columns dipping more than GROOVE_START inside both rims blend (fully
# at GROOVE_START + GROOVE_RANGE) to a monotone radius profile (ungroove);
# gate V19 allows no dip over GROOVE_LIMIT.
GROOVE_START, GROOVE_RANGE, GROOVE_LIMIT = .0005, .001, .001
# The excluded (non-skin) texels grow this far inside the skin before the fill.
EXCLUDE_GROW = 2
# Neck tone (neck_tone): the dyed Human neck takes the head rim's colour per
# azimuth at the cut, fading out by TONE_LOW travel and beyond
# TONE_RADIUS[0] + TONE_RADIUS[1] from the neck axis. Each ring is TONE_RING
# tall and smoothed over TONE_SIGMA of the 1024 columns around the neck.
TONE_LOW, TONE_RING, TONE_SIGMA = 0., .010, 48.
TONE_RADIUS = (.10, .04)
TONE_CLIP = (.25, 4.)
NECK_SIZE = (1024, 512)
BRIDGE_MATERIAL = 'Shared neck bridge'
# Bridge texels take real skin grain: the high-pass of the Human neck just
# below the cut and of the head just above the rim, mirrored into the bridge.
DETAIL_BAND = .030
DETAIL_SIGMA = 4.
# Race features inside a detail band (Glasswarden crystal studs, Ssarathi jaw
# plates, ear lobes) are not skin grain: mirrored into the bridge they print a
# ghost copy on the neck. A texel whose colour stands FEATURE_MADS robust
# deviations off the band's large-scale skin (lowpass FEATURE_SIGMA) is a
# feature; the region, grown FEATURE_GROW texels and hole-filled, gives no grain.
FEATURE_SIGMA, FEATURE_SMOOTH, FEATURE_MADS, FEATURE_GROW, FEATURE_FEATHER = 12., 1.5, 10., 6, 2.
# Shading contours carry no colour outlier (a Votary ear lobe's outline on the
# neck skin): where the sampled surface steps in radius by FEATURE_STEP_M
# between texels (an ear lobe or a plate edge over the neck) is a feature too.
FEATURE_STEP_M, FEATURE_STEP_SKIP = .0015, 4
STREAK_SIGMA = 6.
STREAK_LIMIT = 1.5
# V17 also wants the bridge rows next to the head to carry at least GRAIN_MIN
# of the outer head skin's grain (grain_amount).
GRAIN_MIN = .25
# Files the rebase programme edits besides the install targets (design §8).
PROGRAMME_FILES = frozenset({
    'eloria-assets/tools/rebase_race_body.py', 'eloria-assets/tools/calibrate_skin_palettes.py',
    'eloria-assets/tools/equipment_authoring.py', 'eloria-assets/tools/face_regions.json',
    'godot-client/tests/test_orun_neck_apron_mask.py',
    'godot-client/tests/test_torso_body_cover_lods.gd',
    'godot-client/tests/test_race_rebase.py', 'godot-client/tests/test_native_glb_assets.py',
    'godot-client/tests/test_equipment_fit.py', 'godot-client/tests/test_luminous_cuff_fit_authoring.py',
    '.github/workflows/godot-client.yml'})
STARTER_HELMETS = ('3:134', '3:159', '3:115', '3:122')
# Front ray-cast landmarks of test_face_texture_mapping.py: iris centres for
# every race, brow centres for the races that test has brows for.
IRISES = {
    'glasswarden_female': [(-.037, 1.643), (.037, 1.643)], 'glasswarden_male': [(-.035, 1.653), (.036, 1.653)],
    'greyhaven_female': [(-.035, 1.613), (.035, 1.613)], 'greyhaven_male': [(-.032, 1.624), (.032, 1.624)],
    'mycelari_female': [(-.038, 1.628), (.038, 1.628)], 'mycelari_male': [(-.036, 1.637), (.038, 1.637)],
    'orun_female': [(-.038, 1.631), (.038, 1.631)], 'orun_male': [(-.036, 1.635), (.036, 1.635)],
    'ssarathi_female': [(-.048, 1.680), (.048, 1.680)], 'ssarathi_male': [(-.054, 1.662), (.054, 1.662)],
    'stoneborn_female': [(-.034, 1.624), (.034, 1.624)], 'stoneborn_male': [(-.031, 1.627), (.031, 1.627)],
    'votary_female': [(-.031, 1.607), (.031, 1.607)], 'votary_male': [(-.025, 1.607), (.025, 1.607)]}
BROWS = {'glasswarden_female': (.047, 1.667), 'glasswarden_male': (.040, 1.667),
         'greyhaven_female': (.041, 1.639), 'greyhaven_male': (.042, 1.642),
         'mycelari_female': (.050, 1.655), 'mycelari_male': (.040, 1.650),
         'orun_female': (.047, 1.650), 'orun_male': (.043, 1.650),
         'votary_female': (.035, 1.622), 'votary_male': (.029, 1.613)}
# V14 painted-feature cover (painted_feature_cover): brow strokes under
# BROW_STROKE_MIN canvas px are too faint to judge (votary_male); IRIS_COLOUR
# races paint an iris colour the mask's eye channel must cover.
BROW_STROKE_MIN = 100
IRIS_COLOUR = {'stoneborn_': {'redOverGreen': 15, 'redOverBlue': 30}}
IRIS_COVER = .8
# Races whose head has no eyebrows mesh (test_native_glb_assets budget test).
NO_EYEBROWS = ('mycelari_',)
# Face filter of the Human density reference: Head weight > .5, centroid
# 3 cm in front of the Head joint, normal facing the viewer.
FACE_FRONT, FACE_NZ = .03, .5
# Head inner shell (gate V7). When the inner-wall rule leaves more than this
# hidden, every robustly hidden face goes too (drop_buried).
HIDDEN_LIMIT = .02
DENSE_DIRECTIONS = 120
# v2 grafts capped inner rim loops (spb.cap_inner_loops) with in-plane fans
# whose centre takes the ring's mean UV: those triangles span the source
# atlas. A face is UV-broken when all its corners lie on the upper cut plane
# (such a cap), or when an edge is BROKEN_UV_RATIO times the head's median
# px/cm and longer than BROKEN_UV_PX source pixels (no head has one outside
# the caps today). It gets its own chart, coloured from its corners' colours
# on intact faces.
BROKEN_UV_RATIO, BROKEN_UV_PX = 10., 32.
# Mycelari male: one linear-RGB gain on the 2048 head source brings the
# median race_head body-face luminance (sRGB 0-255, sampled at UV centroids)
# to the female's, measured the same way on mycelari_female_tpose.glb.
HEAD_ALBEDO_TARGETS = {'mycelari_male': {'medianLuminance': 185.0, 'reference': 'mycelari_female'}}
# Ssarathi tail (race_tail): the v2 root ring sat inside the old Luminous
# trousers; on the Human it sits up to 5 cm outside the seat. The root is
# sunk TAIL_DEPTH inside the Human surface with a displacement that fades out
# over TAIL_SINK_FALLOFF; UVs and the rest of the tail keep their bytes.
TAIL_DEPTH, TAIL_SINK_FALLOFF = .008, .12
# The free tail swung with thigh_l (male: 1,568 vertices, up to 1.0; female:
# 2,683 vertices, up to .5, the whole length). Root vertices inside the
# trousers take the seat's weights; over this geodesic distance from the
# emergence the weights blend to the source weights with both thigh shares
# moved to pelvis.
TAIL_FEATHER = {'ssarathi_male': .10, 'ssarathi_female': .10}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_digest(path):
    """SHA-256 of a text source with CRLF folded to LF (the git blob bytes)."""
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def input_digests(inputs):
    return {k: (source_digest if k == 'tool' else digest)(v) for k, v in inputs.items()}


def rig_frame(d):
    skin = d['skins'][0]
    names = [d['nodes'][j]['name'] for j in skin['joints']]
    world = np.array(ea.global_matrices(d))[skin['joints']]
    origin = world[names.index('neck_01')][:3, 3]
    axis = world[names.index('Head')][:3, 3]-origin
    return names, world, origin, axis/np.linalg.norm(axis)


def side_of(axis):
    return np.cross(axis, [1., 0., 0.])


def block_roles(d, b, roles):
    """Union the primitives with these source roles; one race_head per mesh."""
    a, f, off = {k: [] for k in KEYS}, {}, 0
    for mesh in d['meshes']:
        for p in mesh['primitives']:
            if p.get('extras', {}).get('sourceRole') not in roles:
                continue
            key = (mesh['name'], 'head')
            if key in f:
                raise ValueError(f'two {roles} primitives in {mesh["name"]}')
            for k in KEYS:
                a[k].append(ea.accessor_array(d, b, p['attributes'][k]).copy())
            f[key] = ea.accessor_array(d, b, p['indices']).astype(int).reshape(-1, 3)+off
            off += len(a['POSITION'][-1])
    return {'a': {k: np.concatenate(v) for k, v in a.items()}, 'f': f}


def weld(p, tol=1e-6):
    pairs = cKDTree(p).query_pairs(tol, output_type='ndarray')
    return connected_components(coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])),
                                           shape=(len(p), len(p))).tocsr(), directed=False)[1]


def plane_rim(group, origin, axis, height, tol=2e-6):
    """Open edges of the welded surface whose two ends lie on the cut plane."""
    p = group['a']['POSITION'].astype(float)
    ids = weld(p)
    f = np.concatenate(list(group['f'].values()))
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    w = np.sort(ids[e], axis=1)
    _, inverse, count = np.unique(w[:, 0].astype(np.int64)*(ids.max()+1)+w[:, 1],
                                  return_inverse=True, return_counts=True)
    on = np.abs((p-origin)@axis-height) < tol
    return e[(count[inverse.ravel()] == 1) & on[e].all(1)]


def face_components(p, faces):
    """Connected components of position-welded faces (labels per face)."""
    used, inverse = np.unique(faces, return_inverse=True)
    ids = weld(p[used].astype(float))
    ff = ids[inverse.reshape(-1, 3)]
    e = np.concatenate([ff[:, [0, 1]], ff[:, [1, 2]]])
    n = ids.max()+1
    return connected_components(coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n)).tocsr(),
                                directed=False)[1][ff[:, 0]]


def oriented_normals(p, n, faces):
    """Face normals turned to agree with the authored vertex normals."""
    q = np.cross(p[faces[:, 1]]-p[faces[:, 0]], p[faces[:, 2]]-p[faces[:, 0]])
    q /= np.maximum(np.linalg.norm(q, axis=1, keepdims=True), 1e-15)
    s = np.sign((q*n[faces].mean(1)).sum(1)); s[s == 0] = 1
    return q*s[:, None], s


def fibonacci(n=DIRECTIONS):
    i = np.arange(n)+.5
    phi, theta = np.arccos(1-2*i/n), np.pi*(1+5**.5)*i
    return np.stack([np.cos(theta)*np.sin(phi), np.sin(theta)*np.sin(phi), np.cos(phi)], 1)


def intersector(p, faces):
    # trimesh is imported lazily: CI imports these helpers without it.
    import trimesh
    from trimesh.ray.ray_triangle import RayMeshIntersector
    return RayMeshIntersector(trimesh.Trimesh(np.asarray(p, float), faces, process=False))


# Rays per intersector call. 8000 made a whole-body pass peak at 16.5 GB; 1000
# peaks at 5 GB in the same time (results do not depend on the chunk).
RAY_CHUNK = 1000


def any_hit(rmi, origins, directions):
    """intersects_any in chunks: trimesh pairs every ray with its candidate
    triangles at once, which runs a whole-body pass out of memory."""
    hit = np.zeros(len(origins), bool)
    for s in range(0, len(origins), RAY_CHUNK):
        hit[s:s+RAY_CHUNK] = rmi.intersects_any(origins[s:s+RAY_CHUNK], directions[s:s+RAY_CHUNK])
    return hit


def first_hits(rmi, origins, directions):
    """intersects_location(multiple_hits=False) in chunks."""
    locations, rays, triangles = [np.zeros((0, 3))], [np.zeros(0, int)], [np.zeros(0, int)]
    for s in range(0, len(origins), RAY_CHUNK):
        loc, ray, tri = rmi.intersects_location(origins[s:s+RAY_CHUNK], directions[s:s+RAY_CHUNK], multiple_hits=False)
        locations.append(np.asarray(loc, float).reshape(-1, 3)); rays.append(np.asarray(ray, int)+s)
        triangles.append(np.asarray(tri, int))
    return np.concatenate(locations), np.concatenate(rays), np.concatenate(triangles)


def visibility(p, n, faces, candidates):
    """Outside-in visibility and the inner wall (drop_inner_shell.py rule)."""
    p = np.asarray(p, float)
    rmi = intersector(p, faces)
    centre = p[faces].mean(1)
    seen = np.zeros(len(faces), bool)
    for d in fibonacci():
        todo = candidates[~seen[candidates]]
        if not len(todo):
            break
        hit = any_hit(rmi, centre[todo]+2e-4*d, np.repeat(d[None], len(todo), 0))
        seen[todo[~hit]] = True
    hidden = candidates[~seen[candidates]]
    inner = np.zeros(len(faces), bool)
    if len(hidden):
        normal, _ = oriented_normals(p, n, faces)
        origin = centre[hidden]-2e-4*normal[hidden]
        loc, ray, tri = first_hits(rmi, origin, -normal[hidden])
        near = (np.linalg.norm(loc-origin[ray], axis=1) < .015) & seen[tri]
        inner[hidden[ray[near]]] = True
    return seen, inner


def srgb_to_linear(c):
    c = np.asarray(c, float)
    return np.where(c <= .04045, c/12.92, ((c+.055)/1.055)**2.4)


def linear_to_srgb(c):
    c = np.clip(np.asarray(c, float), 0, 1)
    return np.where(c <= .0031308, c*12.92, 1.055*c**(1/2.4)-.055)


def raster(uv, faces, size, wrap=False, tol=-1e-5):
    """Texel centres inside each UV triangle: face, row, column, barycentric."""
    w, h = size
    px = np.asarray(uv, float)*[w, h]
    out = [[], [], [], []]
    for fi, f in enumerate(faces):
        t0 = px[f]
        shifts = [s for s in (-w, 0, w) if t0[:, 0].max()+s >= 0 and t0[:, 0].min()+s <= w] if wrap else [0]
        for s in shifts:
            t = t0+[s, 0]
            lo = np.maximum(np.floor(t.min(0)-.5).astype(int), 0)
            hi = np.minimum(np.ceil(t.max(0)-.5).astype(int), [w-1, h-1])
            if (lo > hi).any():
                continue
            e1, e2 = t[1]-t[0], t[2]-t[0]
            det = e1[0]*e2[1]-e1[1]*e2[0]
            if abs(det) < 1e-12:
                continue
            yy, xx = np.mgrid[lo[1]:hi[1]+1, lo[0]:hi[0]+1]
            dx, dy = xx+.5-t[0, 0], yy+.5-t[0, 1]
            u = (dx*e2[1]-dy*e2[0])/det
            v = (e1[0]*dy-e1[1]*dx)/det
            inside = (u >= tol) & (v >= tol) & (1-u-v >= tol)
            if inside.any():
                out[0].append(np.full(int(inside.sum()), fi)); out[1].append(yy[inside])
                out[2].append(xx[inside]); out[3].append(np.stack([1-u-v, u, v], -1)[inside])
    if not out[0]:
        return np.zeros(0, int), np.zeros(0, int), np.zeros(0, int), np.zeros((0, 3))
    return tuple(np.concatenate(v) for v in out)


def coverage(uv, faces, size, wrap=False, tol=-1e-5):
    face, y, x, _ = raster(uv, faces, size, wrap, tol)
    count = np.zeros(size[::-1], int)
    np.add.at(count, (y, x), 1)
    return count, face, y, x


def dilate(rgb, valid, steps, region=None):
    """Push valid colours outward one texel per step (3x3 mean, repeat wrap)."""
    rgb, valid = rgb.copy(), valid.copy()
    kernel = np.ones((3, 3))
    for _ in range(steps):
        weight = convolve(valid.astype(float), kernel, mode='wrap')
        new = (weight > 0) & ~valid
        if region is not None:
            new &= region
        if not new.any():
            break
        for c in range(rgb.shape[-1]):
            total = convolve(np.where(valid, rgb[..., c], 0.), kernel, mode='wrap')
            rgb[..., c][new] = total[new]/weight[new]
        valid |= new
    return rgb, valid


def encode_jpeg(pixels):
    buffer = io.BytesIO()
    Image.fromarray(np.clip(np.rint(pixels*255), 0, 255).astype('u1')).save(
        buffer, 'JPEG', quality=JPEG_QUALITY, optimize=True)
    return buffer.getvalue()


def decode(payload):
    return np.asarray(Image.open(io.BytesIO(payload)).convert('RGB')).astype(float)/255


def cylinder_uv(p, faces, origin, axis, h1, h0=NECK_H0):
    """Per-corner (theta, travel) UVs, unwrapped within each triangle (SPB:680-688)."""
    rel = p[faces].astype(float)-origin
    theta = np.arctan2(rel@side_of(axis), rel[:, :, 0])
    theta = theta[:, :1]+np.angle(np.exp(1j*(theta-theta[:, :1])))
    return np.stack([theta/(2*np.pi)+.5, ((rel@axis)-h0)/(h1-h0)], axis=-1)


def signed_uv_area(uv):
    e1, e2 = uv[:, 1]-uv[:, 0], uv[:, 2]-uv[:, 0]
    return .5*(e1[:, 0]*e2[:, 1]-e1[:, 1]*e2[:, 0])


def area3(p, faces):
    return .5*np.linalg.norm(np.cross(p[faces[:, 1]]-p[faces[:, 0]], p[faces[:, 2]]-p[faces[:, 0]]), axis=1)


def texel_density(p, uv, faces, size):
    """px/cm per triangle: sqrt(uv area * W * H / area cm2)."""
    a = area3(p.astype(float), faces)*1e4
    ok = a > 1e-6
    uva = np.abs(signed_uv_area(uv[faces].astype(float)))
    return np.sqrt(uva[ok]*size[0]*size[1]/a[ok]), ok


def face_filter(p, n, faces, head, head_weight):
    centre = p[faces].astype(float).mean(1)
    normal = np.cross(p[faces[:, 1]]-p[faces[:, 0]], p[faces[:, 2]]-p[faces[:, 0]]).astype(float)
    normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-12)
    return (head_weight[faces].mean(1) > .5) & (centre[:, 2] > head[2]+FACE_FRONT) & (normal[:, 2] > FACE_NZ)


def joint_weight(a, joint):
    return np.where(a['JOINTS_0'].astype(int) == joint, a['WEIGHTS_0'], 0.).sum(1)


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def locate_head_texture(root, slug, provenance, explicit=None):
    """The 2048 Meshy original (or the archived full-resolution install)."""
    if explicit:
        return Path(explicit), 'explicit'
    for base in (root, *root.parents):
        meshy = base/'generate_models/eloria-races-meshy'/provenance['original']
        if meshy.exists():
            if digest(meshy) != provenance['originalSHA256']:
                raise ValueError(f'{meshy} differs from highResolutionHead.originalSHA256')
            return meshy, 'meshy-original'
    for base in (root, *root.parents):
        archive = base/'archive/fullres-textures-2026-09-16/godot-client/assets/actors/native/races'/f'{slug}.glb'
        if archive.exists():
            return archive, 'archive-fullres-install'
    raise FileNotFoundError('No 2048 head texture source; pass --head-texture')


def head_texture_pixels(path, kind):
    d, b = ea.read_glb(path)
    if kind == 'archive-fullres-install':
        mesh = next(m for m in d['meshes'] if m['name'] == 'body')
        prim = next(p for p in mesh['primitives'] if p.get('extras', {}).get('sourceRole') == 'race_head')
        index = d['textures'][d['materials'][prim['material']]['pbrMetallicRoughness']['baseColorTexture']['index']]['source']
    else:
        index = 0
    payload = spb.image_bytes(d, b, index)
    return decode(payload), hashlib.sha256(payload).hexdigest()


def clean_head(upper, origin, axis, upper_cut):
    """Drop loose fragments and the inner wall; never touch the rim band."""
    p, n = upper['a']['POSITION'], upper['a']['NORMAL']
    keys = list(upper['f'])
    faces = np.concatenate([upper['f'][k] for k in keys])
    tag = np.concatenate([[k[0]]*len(upper['f'][k]) for k in keys])
    travel = (p.astype(float)-origin)@axis
    rim = (np.abs(travel-upper_cut) < RIM_BAND)[faces].any(1)
    # Fragments over the welded union: eye-socket skin joined only through
    # the eyes mesh is one component with it, never a fragment.
    label = face_components(p, faces)
    size = np.bincount(label)
    protected = np.zeros(len(size), bool)
    protected[np.unique(label[rim | np.isin(tag, ('eyes', 'eyebrows'))])] = True
    fragment = (size[label] < 20) & ~protected[label]
    # Inner wall: scalp skin must survive coversHair helmets hiding the scalp,
    # so it never occludes other skin; scalp candidates see every occluder.
    scalp = tag == 'scalp'
    inner = np.zeros(len(faces), bool); seen = np.ones(len(faces), bool)
    for candidates, occluders in ((~scalp, ~scalp), (scalp, np.ones(len(faces), bool))):
        ids = np.flatnonzero(occluders)
        local = np.flatnonzero(candidates[ids])
        s, i = visibility(p, n, faces[ids], local)
        seen[ids[local]] = s[local]; inner[ids[local]] = i[local]
    # An inner-wall face goes only if it also stays hidden from four points
    # along the dense and lattice directions: a crease behind an ear can show
    # one exactly from behind, and deleting it would open a pinhole.
    visible_kept = np.zeros(len(faces), bool)
    for candidates, occluders in ((~scalp, ~scalp), (scalp, np.ones(len(faces), bool))):
        ids = np.flatnonzero(occluders)
        local = np.flatnonzero((inner & ~rim & ~fragment & candidates)[ids])
        if len(local):
            visible_kept[ids[local[~dense_hidden(p.astype(float), faces[ids], local)]]] = True
    inner &= ~visible_kept
    drop = (fragment | inner) & ~rim
    remove_faces(upper, keys, drop)
    kept = ~drop
    report = {'fragmentsRemoved': int(len(np.unique(label[fragment & ~rim]))), 'fragmentTriangles': int((fragment & ~rim).sum()),
              'innerShellRemoved': int((inner & ~rim & ~fragment).sum()),
              'hiddenHeadFraction': float((~seen & kept).sum()/max(kept.sum(), 1)),
              'visibilityDirections': DIRECTIONS}
    if visible_kept.any():
        report['innerShellDenseVisibleKept'] = int(visible_kept.sum())
    if report['hiddenHeadFraction'] > HIDDEN_LIMIT:
        report['buried'] = drop_buried(upper, origin, axis, upper_cut)
        report['hiddenHeadFraction'] = report['buried']['hiddenHeadFractionAfter']
    if report['hiddenHeadFraction'] > 0:
        # The gate counts a face as hidden only when no ray escapes the dense
        # test either: the 60-direction centroid test alone also lists faces
        # that show through a crease or a lip slit (they stay; see above).
        faces = np.concatenate(list(upper['f'].values()))
        tag = np.concatenate([[k[0]]*len(f) for k, f in upper['f'].items()])
        hidden60, robust = robust_hidden(upper['a']['POSITION'].astype(float), upper['a']['NORMAL'].astype(float), faces, tag)
        report.update(hiddenHeadFraction60=float(hidden60.mean()), hiddenHeadFraction=float(robust.mean()), hiddenRule=HIDDEN_RULE)
    return report


HIDDEN_RULE = ('hidden: no ray escapes from the centroid along 60 directions, nor from 4 points (centroid and '
               f'3 interior) along 26 lattice + {DENSE_DIRECTIONS} Fibonacci directions')


def robust_hidden(p, n, faces, tag):
    """60-direction centroid hiding (head_hidden), and the faces of it that
    also stay hidden under dense_hidden with the same occluders."""
    hidden = head_hidden(p, n, faces, tag)
    robust = hidden.copy()
    scalp = tag == 'scalp'
    for wanted, occluders in ((~scalp, ~scalp), (scalp, np.ones(len(faces), bool))):
        ids = np.flatnonzero(occluders)
        local = np.flatnonzero((hidden & wanted)[ids])
        if len(local):
            robust[ids[local]] = dense_hidden(p, faces[ids], local)
    return hidden, robust


def remove_faces(group, keys, drop):
    offset = 0
    for k in keys:
        count = len(group['f'][k])
        group['f'][k] = group['f'][k][~drop[offset:offset+count]]
        offset += count


def head_hidden(p, n, faces, tag, extra=None):
    """Pilot visibility per face: skin never occluded by the scalp, which
    coversHair helmets hide; scalp candidates see every occluder. `extra`
    (points, faces) adds occluders that are never candidates."""
    scalp = tag == 'scalp'
    seen = np.ones(len(faces), bool)
    for candidates, occluders in ((~scalp, ~scalp), (scalp, np.ones(len(faces), bool))):
        ids = np.flatnonzero(occluders)
        local = np.flatnonzero(candidates[ids])
        pp, ff = p, faces[ids]
        if extra is not None:
            pp = np.concatenate([p, extra[0]]); ff = np.concatenate([ff, extra[1]+len(p)])
        s, _ = visibility(pp, np.concatenate([n, np.zeros((len(pp)-len(p), 3))]), ff, local)
        seen[ids[local]] = s[local]
    return ~seen


def lattice():
    """The 26 axis, edge and corner directions: the canonical camera views
    (front, side, back, top and their diagonals) a Fibonacci set misses."""
    grid = np.array([(x, y, z) for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1) if (x, y, z) != (0, 0, 0)], float)
    return grid/np.linalg.norm(grid, axis=1, keepdims=True)


def dense_hidden(p, faces, candidates, directions=DENSE_DIRECTIONS):
    """Re-test hidden faces from four points each (centroid and three interior
    points) along a denser direction set plus the 26 lattice directions; True
    where no ray escapes."""
    rmi = intersector(p, faces)
    corners = np.asarray(p, float)[faces[candidates]]
    points = [corners.mean(1)] + [(corners*w[None, :, None]).sum(1) for w in
                                  np.array([[.7, .15, .15], [.15, .7, .15], [.15, .15, .7]])]
    hidden = np.ones(len(candidates), bool)
    for d in np.concatenate([lattice(), fibonacci(directions)]):
        for origin in points:
            todo = np.flatnonzero(hidden)
            if not len(todo):
                return hidden
            hit = any_hit(rmi, origin[todo]+2e-4*d, np.repeat(d[None], len(todo), 0))
            hidden[todo[~hit]] = False
    return hidden


def drop_buried(upper, origin, axis, upper_cut):
    """Second pass when the inner-wall rule leaves hiddenHeadFraction above
    HIDDEN_LIMIT (Meshy shells with nested walls, a duplicate scalp piece or a
    closed mouth box). The neck opening is plugged by a cone from the outer
    rim to a point 3 cm down the neck axis (in the body the bridge and the
    Human neck close it), so faces seen only up the neck count as hidden.
    A face is dropped when it is hidden from all 60 directions and stays
    hidden from four points each along a denser set.
    As in the first pass, rim-band faces are never touched, so the rim stays
    the one ring the bridge welds to (inner rim loops keep their caps). Loose
    pieces this leaves are dropped by the fragment rule."""
    p, n = upper['a']['POSITION'].astype(float), upper['a']['NORMAL'].astype(float)
    keys = list(upper['f'])
    faces = np.concatenate([upper['f'][k] for k in keys])
    tag = np.concatenate([[k[0]]*len(upper['f'][k]) for k in keys])
    boundary = plane_rim(upper, origin, axis, upper_cut)
    rings = spb.loops({'a': upper['a'], 'boundary': boundary}, origin, axis)
    ring = p[rings[0]]
    rim = (np.abs((p-origin)@axis-upper_cut) < RIM_BAND)[faces].any(1)
    centre = ring.mean(0)-.03*axis
    count = len(ring)
    plug = (np.concatenate([ring, centre[None]]),
            np.stack([np.arange(count), (np.arange(count)+1) % count, np.full(count, count)], 1))
    hidden = head_hidden(p, n, faces, tag, plug)
    candidates = np.flatnonzero(hidden & ~rim)
    pp = np.concatenate([p, plug[0]])
    scalp = tag == 'scalp'
    confirmed = np.zeros(len(faces), bool)
    for wanted, occluders in ((~scalp, ~scalp), (scalp, np.ones(len(faces), bool))):
        ids = np.flatnonzero(occluders)
        local = np.flatnonzero(np.isin(ids, candidates[wanted[candidates]]))
        if not len(local):
            continue
        ff = np.concatenate([faces[ids], plug[1]+len(p)])
        confirmed[ids[local]] = dense_hidden(pp, ff, local)
    drop = confirmed.copy()
    # Pieces cut loose by the drop (eyes and eyebrows excepted).
    label = face_components(p, faces[~drop])
    size = np.bincount(label)
    loose = np.zeros(len(faces), bool)
    protected = np.zeros(len(size), bool)
    protected[np.unique(label[rim[~drop] | np.isin(tag[~drop], ('eyes', 'eyebrows'))])] = True
    loose[np.flatnonzero(~drop)[(size[label] < 20) & ~protected[label]]] = True
    drop |= loose
    remove_faces(upper, keys, drop)
    kept = ~drop
    after = head_hidden(p, n, faces[kept], tag[kept])
    by_tag = Counter(tag[confirmed].tolist())
    return {'rule': 'hidden from 60 directions with the neck plugged, and from 4 points x '
                    f'({DENSE_DIRECTIONS} Fibonacci + 26 lattice) directions; rim-band faces kept', 'hiddenBefore': int(hidden.sum()),
            'denseVisibleKept': int((hidden & ~rim).sum()-confirmed.sum()), 'rimBandHiddenKept': int((hidden & rim).sum()),
            'removed': int(confirmed.sum()), 'removedByMesh': dict(sorted(by_tag.items())),
            'looseRemoved': int(loose.sum()), 'denseDirections': DENSE_DIRECTIONS,
            'hiddenHeadTrianglesAfter': int(after.sum()), 'hiddenHeadFractionAfter': float(after.sum()/max(kept.sum(), 1))}


def broken_uv(upper, size, origin, axis, upper_cut):
    """Per-primitive masks of UV-broken faces: in-plane caps and stretched faces."""
    p, uv = upper['a']['POSITION'].astype(float), upper['a']['TEXCOORD_0'].astype(float)
    faces = np.concatenate(list(upper['f'].values()))
    median = float(np.median(texel_density(p, uv, faces, (size, size))[0]))
    on_plane = np.abs((p-origin)@axis-upper_cut) < 2e-6
    masks, counts = {}, Counter()
    for key, f in upper['f'].items():
        e3 = np.linalg.norm(p[f[:, [1, 2, 0]]]-p[f], axis=2)*100
        eu = np.linalg.norm(uv[f[:, [1, 2, 0]]]-uv[f], axis=2)*size
        cap = on_plane[f].all(1)
        stretched = ((eu > BROKEN_UV_RATIO*median*e3) & (eu > BROKEN_UV_PX)).any(1)
        masks[key] = cap | stretched
        counts['inPlaneCaps'] += int(cap.sum()); counts['stretched'] += int((stretched & ~cap).sum())
    return masks, median, dict(counts)



def broken_corner_colours(upper, masks, pixels):
    """Colour of each broken face's corners where they sit on intact faces."""
    p, uv = upper['a']['POSITION'].astype(float), upper['a']['TEXCOORD_0'].astype(float)
    good = np.unique(np.concatenate([f[~masks[k]] for k, f in upper['f'].items()]))
    tree = cKDTree(p[good])
    colour = spb.sample_image(np.rint(pixels*255), uv[good])
    fallback = np.median(colour, axis=0)
    out = {}
    for key, mask in masks.items():
        if not mask.any():
            continue
        rows = upper['f'][key][mask].ravel()
        values = [colour[h].mean(0) if h else fallback for h in tree.query_ball_point(p[rows], 1e-6)]
        out[key] = np.array(values).reshape(-1, 3, 3)
    return out


def chart_broken(upper, masks, size, density):
    """UV-broken faces get their own corners and a planar chart at the head's
    median density (in source UV units); positions, normals and weights are
    copied byte for byte."""
    a = upper['a']
    for key, mask in masks.items():
        if not mask.any():
            continue
        f = upper['f'][key].copy()
        rows = f[mask].ravel()
        start = len(a['POSITION'])
        for k in KEYS:
            a[k] = np.concatenate([a[k], a[k][rows]])
        new = np.arange(start, start+len(rows)).reshape(-1, 3)
        f[mask] = new
        upper['f'][key] = f
        q = a['POSITION'][new].astype(float)
        e1 = q[:, 1]-q[:, 0]
        normal = np.cross(e1, q[:, 2]-q[:, 0])
        u = e1/np.maximum(np.linalg.norm(e1, axis=1, keepdims=True), 1e-12)
        v = np.cross(normal/np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-12), u)
        rel = q-q[:, :1]
        coords = np.stack([(rel*u[:, None]).sum(2), (rel*v[:, None]).sum(2)], -1)*100*density/size
        a['TEXCOORD_0'][new.ravel()] = coords.reshape(-1, 2).astype(a['TEXCOORD_0'].dtype)


# ---------------------------------------------------------------------------
# Ssarathi tail (race_tail)
# ---------------------------------------------------------------------------

def winding(points, tris, chunk=128):
    """Generalised winding number of each point against a triangle soup."""
    points, tris = np.asarray(points, float), np.asarray(tris, float)
    out = np.zeros(len(points))
    for s in range(0, len(points), chunk):
        q = points[s:s+chunk]
        a, b, c = (tris[None, :, i]-q[:, None] for i in range(3))
        la, lb, lc = (np.linalg.norm(v, axis=2) for v in (a, b, c))
        num = np.einsum('ijk,ijk->ij', a, np.cross(b, c))
        den = (la*lb*lc+np.einsum('ijk,ijk->ij', a, b)*lc+np.einsum('ijk,ijk->ij', b, c)*la
               + np.einsum('ijk,ijk->ij', c, a)*lb)
        out[s:s+chunk] = np.arctan2(num, den).sum(1)/(2*np.pi)
    return out


def open_loops(p, faces):
    """Rows of each open boundary loop of the position-welded surface."""
    ids = weld(p)
    e = np.sort(ids[np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])], 1)
    edges, count = np.unique(e, axis=0, return_counts=True)
    edges = edges[count == 1]
    if not len(edges):
        return []
    n = ids.max()+1
    label = connected_components(coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])), shape=(n, n)).tocsr(),
                                 directed=False)[1]
    return sorted((np.flatnonzero(np.isin(ids, np.unique(edges[label[edges[:, 0]] == c])))
                   for c in np.unique(label[edges[:, 0]])), key=len, reverse=True)


def surface_depth(points, tris):
    """Signed depth below a triangle soup (positive inside) and the closest
    surface point."""
    import trimesh
    mesh = trimesh.Trimesh(tris.reshape(-1, 3), np.arange(tris.size//3).reshape(-1, 3), process=False)
    closest, distance, _ = trimesh.proximity.closest_point(mesh, points)
    inside = winding(points, tris) > .5
    return np.where(inside, distance, -distance), closest


def vertex_normals(p, faces, ids):
    """Area-weighted face normals summed per welded position."""
    q = np.cross(p[faces[:, 1]]-p[faces[:, 0]], p[faces[:, 2]]-p[faces[:, 0]])
    total = np.zeros((ids.max()+1, 3))
    for c in range(3):
        np.add.at(total, ids[faces[:, c]], q)
    return total[ids]/np.maximum(np.linalg.norm(total[ids], axis=1, keepdims=True), 1e-12)


def tail_group(hd, hb):
    if not any(p.get('extras', {}).get('sourceRole') == 'race_tail' for m in hd['meshes'] for p in m['primitives']):
        return None
    group = block_roles(hd, hb, {'race_tail'})
    group['f'] = {('body', 'tail'): group['f'][('body', 'head')]}
    group['role'] = 'race_tail'
    return group


def human_surface(lower):
    """Triangles of the Human below-neck surfaces (skin and wardrobe)."""
    p = lower['a']['POSITION'].astype(float)
    return np.concatenate([p[f] for (name, _), f in lower['f'].items() if name in ea.BODY_SURFACES])


def fit_tail(tail, lower, names, feather=None):
    """Carry the v2 tail onto the Human: drop loose pieces, sink the root
    ring TAIL_DEPTH inside the Human surface (fading over TAIL_SINK_FALLOFF),
    and optionally feather the free tail's thigh weights to the pelvis."""
    a = tail['a']
    key = ('body', 'tail')
    faces = tail['f'][key]
    p0 = a['POSITION'].astype(float)
    report = {'trianglesBefore': int(len(faces)), 'verticesBefore': int(len(np.unique(faces)))}
    label = face_components(p0, faces)
    size = np.bincount(label)
    loose = size[label] < 20
    faces = faces[~loose]
    report.update(fragmentsRemoved=int((size < 20).sum()), fragmentTriangles=int(loose.sum()))
    surface = human_surface(lower)
    loops = open_loops(p0, faces)
    root = loops[0]
    depth, closest = surface_depth(p0[root], surface)
    outward = np.where((depth > 0)[:, None], closest-p0[root], p0[root]-closest)
    outward /= np.maximum(np.linalg.norm(outward, axis=1, keepdims=True), 1e-12)
    move = np.where((depth < TAIL_DEPTH)[:, None], closest-outward*TAIL_DEPTH-p0[root], 0.)
    used = np.unique(faces)
    distance, nearest = cKDTree(p0[root]).query(p0[used], k=min(8, len(root)))
    weight = 1/np.maximum(distance, 1e-9)**4
    field = (weight[..., None]*move[nearest]).sum(1)/weight.sum(1, keepdims=True)
    s = np.clip(distance[:, 0]/TAIL_SINK_FALLOFF, 0, 1)
    shift = np.zeros_like(p0)
    shift[used] = field*(1-s*s*(3-2*s))[:, None]
    shift[root] = move
    p1 = p0+shift
    moved = np.linalg.norm(shift, axis=1) > 1e-9
    ids = weld(p0)
    before, after = vertex_normals(p0, faces, ids), vertex_normals(p1, faces, ids)
    normal = a['NORMAL'].astype(float)
    normal[moved] += after[moved]-before[moved]
    normal[moved] /= np.maximum(np.linalg.norm(normal[moved], axis=1, keepdims=True), 1e-12)
    a['POSITION'] = p1.astype(a['POSITION'].dtype)
    a['NORMAL'] = normal.astype(a['NORMAL'].dtype)
    depth_after, _ = surface_depth(p1[root], surface)
    report['root'] = {'loopVertices': int(len(root)), 'otherOpenLoops': [int(len(x)) for x in loops[1:]],
                      'depthBeforeM': [float(depth.min()), float(np.median(depth)), float(depth.max())],
                      'depthAfterM': [float(depth_after.min()), float(np.median(depth_after)), float(depth_after.max())],
                      'targetDepthM': TAIL_DEPTH, 'sinkFalloffM': TAIL_SINK_FALLOFF,
                      'maxShiftM': float(np.linalg.norm(shift, axis=1).max()), 'movedVertices': int(moved.sum())}
    if feather:
        report['feather'] = feather_tail(a, faces, lower, surface, names, feather)
    tail['f'][key] = faces
    report.update(triangles=int(len(faces)), vertices=int(len(np.unique(faces))))
    return report


def feather_tail(a, faces, lower, surface, names, feather):
    """Root inside the trousers follows the seat; the free tail follows the
    pelvis (both thigh shares moved to it), blended over `feather` metres of
    tail surface from the emergence."""
    from scipy.sparse.csgraph import dijkstra
    p = a['POSITION'].astype(float)
    used = np.unique(faces)
    inside = np.zeros(len(p), bool)
    near = used[p[used, 0] < .45]
    inside[near] = winding(p[near], surface) > .5
    ids = weld(p)
    n = ids.max()+1
    e = np.unique(np.sort(ids[np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])], 1), axis=0)
    rep = np.zeros(n, int); rep[ids] = np.arange(len(p))
    length = np.linalg.norm(p[rep[e[:, 0]]]-p[rep[e[:, 1]]], axis=1)
    graph = coo_matrix((length, (e[:, 0], e[:, 1])), shape=(n, n)).tocsr()
    sources = np.unique(ids[inside])
    along = (dijkstra(graph, directed=False, indices=sources, min_only=True)[ids] if len(sources)
             else np.full(len(p), np.inf))
    dense = spb.dense_weights(a)
    pelvis, thighs = names.index('pelvis'), [names.index('thigh_l'), names.index('thigh_r')]
    free = dense.copy()
    free[:, pelvis] += free[:, thighs].sum(1); free[:, thighs] = 0
    human = lower['a']
    keep = np.unique(np.concatenate([f for (name, _), f in lower['f'].items() if name in ('wardrobe_pants', 'wardrobe_shirt')]))
    distance, nearest = cKDTree(human['POSITION'][keep].astype(float)).query(p, k=4)
    w = 1/np.maximum(distance, 1e-6)**2; w /= w.sum(1, keepdims=True)
    seat_dense = spb.dense_weights({'POSITION': human['POSITION'][keep], 'JOINTS_0': human['JOINTS_0'][keep],
                                    'WEIGHTS_0': human['WEIGHTS_0'][keep]})
    seat = np.einsum('nk,nkj->nj', w, seat_dense[nearest])
    s = np.clip(np.where(np.isfinite(along), along, feather)/feather, 0, 1); s = (s*s*(3-2*s))[:, None]
    blended = (1-s)*seat+s*free
    old_thigh = dense[:, thighs[0]]
    joints, weights = spb.sparse_weights(blended)
    a['JOINTS_0'][used] = joints[used].astype(a['JOINTS_0'].dtype)
    a['WEIGHTS_0'][used] = weights[used].astype(a['WEIGHTS_0'].dtype)
    new_thigh = joint_weight(a, thighs[0])
    return {'featherM': feather, 'insideVertices': int(inside[used].sum()),
            'thighLBefore': {'vertices': int((old_thigh[used] > 0).sum()), 'dominant': int((dense[used].argmax(1) == thighs[0]).sum()),
                             'max': float(old_thigh[used].max())},
            'thighLAfter': {'vertices': int((new_thigh[used] > 1e-6).sum()), 'dominant': int((spb.dense_weights(a)[used].argmax(1) == thighs[0]).sum()),
                            'max': float(new_thigh[used].max()),
                            'maxBeyondFeather': float(new_thigh[used][along[used] >= feather].max(initial=0))},
            'seatThighLAtEmergence': float(seat[used][inside[used], thighs[0]].mean()) if inside[used].any() else None,
            'rule': 'inside the Human surface: the seat (4 nearest pants/shirt vertices); beyond the feather distance '
                    'along the tail surface: source weights with thigh_l/thigh_r moved to pelvis; smoothstep between'}


def head_albedo_gain(hd, hb, pixels, target):
    """One linear-RGB gain taking the race_head body-face median luminance
    (sRGB 0-255 at UV centroids) to the target."""
    group = block_roles(hd, hb, {'race_head'})
    colour = spb.sample_image(np.rint(pixels*255), group['a']['TEXCOORD_0'].astype(float)[group['f'][('body', 'head')]].mean(1))
    linear = srgb_to_linear(colour)

    def median(gain):
        return float(np.median(linear_to_srgb(linear*gain)@LUMA*255))
    lo, hi = 0., 4.
    for _ in range(60):
        mid = (lo+hi)/2
        lo, hi = (mid, hi) if median(mid) < target else (lo, mid)
    gain = (lo+hi)/2
    return gain, median(1.), median(gain)


def weld_ring(group, rows):
    """Coincident rim copies get one normal and one joint distribution."""
    a = group['a']
    rows = np.asarray(rows)
    labels = weld(a['POSITION'][rows].astype(float))
    dense = spb.dense_weights({'POSITION': a['POSITION'][rows], 'JOINTS_0': a['JOINTS_0'][rows],
                               'WEIGHTS_0': a['WEIGHTS_0'][rows]})
    changed = Counter()
    for c in np.unique(labels):
        local = np.flatnonzero(labels == c)
        if len(local) < 2:
            continue
        ids = rows[local]
        normal = a['NORMAL'][ids].astype(float).mean(0)
        normal = (normal/max(np.linalg.norm(normal), 1e-12)).astype(a['NORMAL'].dtype)
        if (a['NORMAL'][ids] != normal).any():
            a['NORMAL'][ids] = normal; changed['normals'] += len(ids)
        w = dense[local]
        if np.abs(w-w[:1]).max() > 0:
            jj, ww = spb.sparse_weights(w.mean(0)[None])
            a['JOINTS_0'][ids] = jj[0].astype(a['JOINTS_0'].dtype); a['WEIGHTS_0'][ids] = ww[0]
            changed['weights'] += len(ids)
    return {'rows': int(len(rows)), 'positions': int(len(np.unique(labels))),
            'normalsChanged': changed['normals'], 'weightsChanged': changed['weights']}


def rim_radius(points, origin, axis, theta):
    """Radius of a rim ring at the given azimuths (periodic interpolation)."""
    rel = np.asarray(points, float)-origin
    radial = rel-(rel@axis)[:, None]*axis
    angle = np.arctan2(radial@side_of(axis), radial[:, 0])
    order = np.argsort(angle)
    return np.interp(theta, angle[order], np.linalg.norm(radial, axis=1)[order], period=2*np.pi)


def bridge_dips(interior, lower_rim, upper_rim, origin, axis):
    """How far each interior bridge point lies inside both rims at its azimuth
    (a groove: the boundary-tangent profile swinging in and back out)."""
    rel = np.asarray(interior, float)-origin
    radial = rel-(rel@axis)[:, None]*axis
    theta = np.arctan2(radial@side_of(axis), radial[:, 0])
    rims = np.minimum(rim_radius(lower_rim, origin, axis, theta), rim_radius(upper_rim, origin, axis, theta))
    return np.maximum(rims-np.linalg.norm(radial, axis=1), 0.), theta


def ungroove(bridge, origin, axis):
    """Columns of the spb.neck_bridge profile that dip inside both rims (the
    Human nape wider than the head rim, both rim tangents sloping out) take a
    monotone cubic radius (Fritsch-Carlson limited end slopes) instead; other
    columns keep their bytes. Heights and azimuths stay; interior normals are
    re-summed from the faces as spb does."""
    a = bridge['a']
    p = a['POSITION'].astype(float)
    n0, n1 = len(bridge['lowerIds']), len(bridge['upperIds'])
    inner = p[n0:len(p)-n1]
    rings = len(inner)//64
    if rings*64 != len(inner):
        raise ValueError('unexpected bridge layout')
    steps = np.arange(1, 8)/8 if rings == 7 else np.array([.125, .25, .5, .75])
    rel = inner-origin
    height = rel@axis
    radial = rel-height[:, None]*axis
    r = np.linalg.norm(radial, axis=1)
    unit = radial/r[:, None]
    theta = np.arange(64)*2*np.pi/64
    r0, r1 = rim_radius(p[:n0], origin, axis, theta), rim_radius(p[len(p)-n1:], origin, axis, theta)
    R = r.reshape(rings, 64)
    dip = np.maximum(np.minimum(r0, r1)-R.min(0), 0.)
    report = {'maxDipBeforeM': float(dip.max()), 'rule': f'columns dipping over {GROOVE_START*1000:g} mm inside both rims '
              f'blend (fully at {(GROOVE_START+GROOVE_RANGE)*1000:g} mm) to a monotone cubic radius profile'}
    alpha = np.clip((dip-GROOVE_START)/GROOVE_RANGE, 0, 1); alpha = alpha*alpha*(3-2*alpha)
    if not alpha.any():
        return {**report, 'columns': 0, 'maxDipAfterM': report['maxDipBeforeM']}
    alpha = np.maximum(alpha, np.clip(gaussian_filter(alpha, 1.5, mode='wrap'), 0, 1))
    alpha[alpha < .01] = 0
    delta = r1-r0
    d0, d1 = (R[0]-r0)/steps[0], (r1-R[-1])/(1-steps[-1])
    d0 = np.where(d0*delta > 0, d0, 0.); d1 = np.where(d1*delta > 0, d1, 0.)
    scale = np.hypot(d0, d1)/np.maximum(np.abs(delta), 1e-9)
    limit = np.where(scale > 3, 3/np.maximum(scale, 1e-9), 1.)
    d0, d1 = d0*limit, d1*limit
    s = steps[:, None]
    mono = ((2*s**3-3*s*s+1)*r0+(s**3-2*s*s+s)*d0+(-2*s**3+3*s*s)*r1+(s**3-s*s)*d1)
    R_new = R+alpha*(mono-R)
    p[n0:len(p)-n1] = origin+height[:, None]*axis+unit*R_new.reshape(-1, 1)
    faces = bridge['f'][('body', 4)]
    normal = np.cross(p[faces[:, 1]]-p[faces[:, 0]], p[faces[:, 2]]-p[faces[:, 0]])
    summed = np.zeros_like(p)
    for column in range(3):
        np.add.at(summed, faces[:, column], normal)
    summed /= np.maximum(np.linalg.norm(summed, axis=1, keepdims=True), 1e-9)
    a['POSITION'] = p
    a['NORMAL'] = np.asarray(a['NORMAL'], float).copy()
    a['NORMAL'][n0:len(p)-n1] = summed[n0:len(p)-n1]
    after = np.maximum(np.minimum(r0, r1)-R_new.min(0), 0.)
    return {**report, 'columns': int((alpha > 0).sum()), 'maxDipAfterM': float(after.max())}


def bridge_metrics(bridge_p, bridge_f, neighbours, origin, axis, lower, upper):
    """Shape of a neck bridge against the faces it joins (decision 14)."""
    bp = bridge_p.astype(float)
    parts = [(bp, bridge_f, None)] + [(q.astype(float), f, n) for q, f, n in neighbours]
    p = np.concatenate([q for q, _, _ in parts])
    ids = weld(p)
    offsets = np.cumsum([0]+[len(q) for q, _, _ in parts])
    bn = np.cross(bp[bridge_f[:, 1]]-bp[bridge_f[:, 0]], bp[bridge_f[:, 2]]-bp[bridge_f[:, 0]])
    bn /= np.maximum(np.linalg.norm(bn, axis=1, keepdims=True), 1e-15)
    centre = bp[bridge_f].mean(1)-origin
    radial = centre-(centre@axis)[:, None]*axis
    bn *= np.where((bn*radial).sum(1) < 0, -1, 1)[:, None]
    e = ids[bridge_f[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2)]
    # Two bridge faces walking a shared edge the same way disagree in winding.
    inconsistent = sum(1 for c in Counter(map(tuple, e.tolist())).values() if c > 1)
    undirected = Counter(tuple(sorted(x)) for x in e.tolist())
    owner = {tuple(sorted(x)): i//3 for i, x in enumerate(e.tolist()) if undirected[tuple(sorted(x))] == 1}
    report = {'faces': int(len(bridge_f)), 'orientationInconsistentEdges': int(inconsistent),
              'openEdges': len(owner), 'nearHorizontalFaces': int((np.abs(bn@axis) > .9).sum()),
              'minNormalDotRadial': float((bn*(radial/np.maximum(np.linalg.norm(radial, axis=1, keepdims=True), 1e-12))).sum(1).min())}
    middle = (lower+upper)/2
    height = (bp[bridge_f].mean(1)-origin)@axis
    for label in ('lower', 'upper'):
        angles = []
        for (q, f, n), base in zip(parts[1:], offsets[1:-1]):
            fn, _ = oriented_normals(q, n, f)
            ee = ids[f[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2)+base]
            for k, (i, j) in enumerate(ee.tolist()):
                key = (min(i, j), max(i, j))
                if key not in owner or (height[owner[key]] < middle) != (label == 'lower'):
                    continue
                angles.append(np.degrees(np.arccos(np.clip(bn[owner[key]]@fn[k//3], -1, 1))))
        angles = np.asarray(angles)
        report[label+'RimCrease'] = ({'edges': int(len(angles)), 'medianDeg': float(np.median(angles)),
                                     'p90Deg': float(np.percentile(angles, 90)), 'maxDeg': float(angles.max())}
                                    if len(angles) else {'edges': 0})
    # Radial jump at the front (theta -90 deg): upper rim radius minus lower.
    side = side_of(axis)
    rel = bp-origin
    travel = rel@axis
    radial = rel-travel[:, None]*axis
    angle = np.degrees(np.arctan2(radial@side, radial[:, 0]))
    near = np.abs(((angle+90+180) % 360)-180) < 6
    radius = np.linalg.norm(radial, axis=1)
    lo = near & (np.abs(travel-lower) < 2e-3)
    hi = near & (np.abs(travel-upper) < 2e-3)
    if lo.any() and hi.any():
        report['frontRadialJumpM'] = float(radius[hi].mean()-radius[lo].mean())
    return report


def neck_floor(p, faces, origin, axis, top=LOWER_CUT, step=.001, bins=720):
    """Lowest travel above which every section of the skin is a closed ring."""
    side = side_of(axis)
    q = p.astype(float)-origin
    travel, theta = q@axis, np.arctan2(q@side, q[:, 0])
    level = top
    while level > -.05:
        h = level-step
        lo, hi = travel[faces].min(1), travel[faces].max(1)
        crossing = faces[(lo < h) & (hi > h)]
        covered = np.zeros(bins, bool)
        for f in crossing:
            t = travel[f]
            pts = []
            for i, j in ((0, 1), (1, 2), (2, 0)):
                if (t[i]-h)*(t[j]-h) < 0:
                    s = (h-t[i])/(t[j]-t[i]); pts.append(theta[f[i]]+s*np.angle(np.exp(1j*(theta[f[j]]-theta[f[i]]))))
            if len(pts) != 2:
                continue
            a, b = pts[0], pts[0]+np.angle(np.exp(1j*(pts[1]-pts[0])))
            lo_b, hi_b = sorted((a, b))
            k = np.arange(int(np.floor((lo_b+np.pi)/(2*np.pi)*bins)), int(np.ceil((hi_b+np.pi)/(2*np.pi)*bins))+1)
            covered[k % bins] = True
        if not covered.all():
            return level
        level = h
    return level


def split_shared_neck(lower, bridge, origin, axis, h1):
    """Human neck faces whose cylinder map is injective (decision 8)."""
    key = next(k for k in lower['f'] if k[0] == 'body')
    ff, p = lower['f'][key], lower['a']['POSITION']
    travel = (p.astype(float)-origin)@axis
    candidate = (travel[ff].max(1) > .005) & (np.abs(p[ff][..., 0]).max(1) < .12)
    floor = neck_floor(p, ff, origin, axis)
    selected = candidate & (travel[ff].min(1) >= floor)
    uv = cylinder_uv(p, ff, origin, axis, h1)
    _, sign = oriented_normals(p.astype(float), lower['a']['NORMAL'], ff)
    wind = np.sign(signed_uv_area(uv))*sign
    majority = np.sign(np.median(wind[selected]))
    folded = selected & (wind != majority)
    selected &= ~folded
    bridge_uv = cylinder_uv(bridge['a']['POSITION'], bridge['f'][('body', 4)], origin, axis, h1)
    overlap_dropped = 0
    for _ in range(32):
        ids = np.flatnonzero(selected)
        both = np.concatenate([uv[ids], bridge_uv]).reshape(-1, 2)
        faces = np.arange(len(both)).reshape(-1, 3)
        count, face, y, x = coverage(both, faces, NECK_SIZE, wrap=True, tol=1e-6)
        bad = np.unique(face[count[y, x] > 1])
        bad = bad[bad < len(ids)]
        if not len(bad):
            break
        selected[ids[bad]] = False; overlap_dropped += len(bad)
    else:
        raise ValueError('shared_neck overlaps did not resolve')
    neck = {'a': {k: v[ff[selected].ravel()] for k, v in lower['a'].items()},
            'f': {('body', 4): np.arange(int(selected.sum())*3).reshape(-1, 3)}, 'role': 'shared_neck',
            'oldUV': lower['a']['TEXCOORD_0'][ff[selected].ravel()].astype(float)}
    neck['a']['TEXCOORD_0'] = uv[selected].reshape(-1, 2).astype('<f4')
    lower['f'][key] = ff[~selected]
    return neck, {'candidates': int(candidate.sum()), 'closedRingFloorM': float(floor),
                  'belowFloor': int((candidate & (travel[ff].min(1) < floor)).sum()),
                  'folded': int(folded.sum()), 'overlapDropped': int(overlap_dropped), 'faces': int(selected.sum())}


def weighted_median(values, weights):
    """Per-column weighted median (calibrate_skin_palettes.weighted_median)."""
    out = []
    for column in np.asarray(values, float).T:
        order = np.argsort(column)
        out.append(float(column[order[np.searchsorted(np.cumsum(weights[order]), weights.sum()/2)]]))
    return np.array(out)


def ring_colour(upper, head_pixels, origin_h, axis_h, upper_cut):
    """Median race-head colour just above the rim (the pilot's recolour target,
    now reported only: the neck tone pass matches the rim per azimuth)."""
    hp, huv = upper['a']['POSITION'].astype(float), upper['a']['TEXCOORD_0'].astype(float)
    hf = intact(upper, ('body', 'head'))
    c = hp[hf].mean(1)-origin_h
    t = c@axis_h
    r = np.linalg.norm(c-t[:, None]*axis_h, axis=1)
    colour = spb.sample_image(np.rint(head_pixels*255), huv[hf].mean(1))
    for band in (.020, .040):
        chosen = (t >= upper_cut) & (t <= upper_cut+band) & (r < .14) & (colour.max(1) > .10)
        if chosen.sum() >= 12:
            return np.median(colour[chosen], axis=0), int(chosen.sum())
    raise ValueError('Too few race neck samples for the skin colour')


def face_reference(upper, head_pixels, region, projection):
    """The race_head reference calibrate_skin_palettes will measure: the
    area-weighted median of the head's body faces at their UV centroids,
    without the eye/brow mask regions (face_regions.json, projected as
    build_face_masks.bake projects them) and without black gutters."""
    from build_face_masks import projection_masks
    from scipy.ndimage import map_coordinates
    hp, huv = upper['a']['POSITION'].astype(float), upper['a']['TEXCOORD_0'].astype(float)
    hf = intact(upper, ('body', 'head'))
    centre, area = hp[hf].mean(1), area3(hp, hf)
    colour = spb.sample_image(np.rint(head_pixels*255), huv[hf].mean(1))
    masks = projection_masks(region)
    py = (projection['yMax']-centre[:, 1])*projection['pixelsPerMetre']
    px = (centre[:, 0]-projection['xMin'])*projection['pixelsPerMetre']
    masked = np.stack([map_coordinates(masks[..., c], [py, px], order=1, mode='constant') for c in range(3)], -1).max(1)
    masked = np.where((centre[:, 2] > .02) & (centre[:, 1] > 1.57), masked, 0.)
    use = (area > 1e-12) & (colour.max(1) > .10) & (masked < .094)
    return weighted_median(colour[use], area[use])


def skin_faces(lower, neck=None):
    """Human skin faces (positions, faces, Human-atlas UVs): the body faces
    below the cut, plus the shared_neck faces with their old UVs once split."""
    body = next(f for k, f in lower['f'].items() if k[0] == 'body')
    parts = [(lower['a']['POSITION'], body, lower['a']['TEXCOORD_0'])]
    if neck is not None:
        parts.append((neck['a']['POSITION'], neck['f'][('body', 4)], neck['oldUV']))
    return parts


def skin_reference(lower, pixels):
    """Area-weighted median of the Human skin atlas at its body-face UV
    centroids (calibrate_skin_palettes' shared_body measure)."""
    (p, f, uv), = skin_faces(lower)
    p = p.astype(float)
    area = np.linalg.norm(np.cross(p[f[:, 1]]-p[f[:, 0]], p[f[:, 2]]-p[f[:, 0]]), axis=1)
    colour = spb.sample_image(np.rint(pixels*255), uv[f].astype(float).mean(1))
    use = (area > 1e-12) & (colour.max(1) > .10)
    return weighted_median(colour[use], area[use])


def tone_weight(points, origin, axis):
    """Neck tone correction weight: 1 at the lower cut on the neck, fading to
    0 at TONE_LOW travel and away from the neck axis (shoulders, T-pose arms)."""
    rel = np.asarray(points, float)-origin
    travel = rel@axis
    radius = np.linalg.norm(rel-travel[:, None]*axis, axis=1)
    s = np.clip((travel-TONE_LOW)/(LOWER_CUT-TONE_LOW), 0, 1)
    r = np.clip((radius-TONE_RADIUS[0])/TONE_RADIUS[1], 0, 1)
    return s*s*(3-2*s)*(1-r*r*(3-2*r))


def tone_gain(points, origin, axis, gain):
    """Per-point linear gain: the per-column ring gain raised to tone_weight."""
    rel = np.asarray(points, float)-origin
    theta = np.arctan2(rel@side_of(axis), rel[:, 0])
    column = (theta/(2*np.pi)+.5)*len(gain)-.5
    lo = np.floor(column).astype(int)
    f = (column-lo)[:, None]
    log_gain = np.log(gain)
    g = (1-f)*log_gain[lo % len(gain)]+f*log_gain[(lo+1) % len(gain)]
    return np.exp(g*tone_weight(points, origin, axis)[:, None])


def recolour_skin(lower, template_pixels, target, origin_t, axis_t, detail_mix, tone=None):
    """B7a: dye the Human skin texels (runtime formula) so that the skin's
    area-weighted median takes the race face colour; with `tone` (per-column
    linear gains, neck_tone) the neck also bends to the head rim per azimuth."""
    size = template_pixels.shape[1::-1]
    a = lower['a']
    body = next(f for k, f in lower['f'].items() if k[0] == 'body')
    wardrobe = np.concatenate([f for k, f in lower['f'].items() if k[0].startswith('wardrobe_')])
    skin_count, skin_face, sy, sx = coverage(a['TEXCOORD_0'], body, size)
    cloth_count, _, _, _ = coverage(a['TEXCOORD_0'], wardrobe, size)
    skin = (skin_count > 0) & (cloth_count == 0)
    reference = skin_reference(lower, template_pixels)
    ref_l, tgt_l = srgb_to_linear(reference), srgb_to_linear(target)
    original = srgb_to_linear(template_pixels[skin])
    lum = (original@LUMA)/(ref_l@LUMA)
    # Skin distribution (decision 5): chromaticity about its median in MAD
    # units, and log luminance about its median in MAD units, both two-sided.
    # Texels outside either (the pale cloth-paint teeth along the collar,
    # grey paint strokes on the hands, the near-black boot-top skin the boots
    # hide) are refilled from neighbouring dyed skin. Nails and highlights
    # inside the distribution keep the runtime dye formula. The excluded set
    # grows EXCLUDE_GROW texels inside the skin: the anti-aliased rim of a
    # paint stroke falls inside the distribution but still reads as a line.
    chroma = original/np.maximum(original.sum(1, keepdims=True), 1e-6)
    med = np.median(chroma, axis=0)
    mad = 1.4826*np.median(np.abs(chroma-med), axis=0)
    distance = np.sqrt((((chroma-med)/np.maximum(mad, 1e-4))[:, :2]**2).sum(1))
    log_lum = np.log(np.maximum(lum, 1e-4))
    lmed = np.median(log_lum); lmad = 1.4826*np.median(np.abs(log_lum-lmed))
    chroma_out = distance > CHROMA_MAD
    lum_out = np.abs(log_lum-lmed) > LUM_LOG_MAD*lmad
    yy, xx = np.nonzero(skin)
    core = np.zeros(skin.shape, bool); core[yy[chroma_out | lum_out], xx[chroma_out | lum_out]] = True
    excluded = binary_dilation(core, iterations=EXCLUDE_GROW) & skin if EXCLUDE_GROW else core
    outside = excluded[yy, xx]
    dyed = tgt_l*((1-detail_mix)*lum[:, None]+detail_mix*original/ref_l)
    face, fy, fx, bary = raster(a['TEXCOORD_0'], body, size)
    first = np.full(skin.shape, -1); first[fy[::-1], fx[::-1]] = np.arange(len(face))[::-1]
    hit = first[yy, xx]
    position = np.einsum('ni,nic->nc', bary[hit], a['POSITION'][body[face[hit]]].astype(float))
    tone_report = None
    if tone is not None:
        dyed = dyed*tone_gain(position, origin_t, axis_t, tone)
        w = tone_weight(position, origin_t, axis_t)
        tone_report = {'texels': int((w > 0).sum()), 'fullTexels': int((w > .999).sum())}
    result = np.zeros_like(template_pixels)
    valid = np.zeros(skin.shape, bool)
    keep = ~outside
    result[yy[keep], xx[keep]] = linear_to_srgb(dyed[keep])
    valid[yy[keep], xx[keep]] = True
    result, valid = dilate(result, valid, 512, region=excluded)
    unfilled = ~valid[yy[outside], xx[outside]]
    result, valid = dilate(result, valid, 16)
    result[~valid] = target
    # Where are the excluded texels (for the report)?
    centre = position[outside]
    region = np.where(np.abs(centre[:, 0]) > .45, 'hands',
                      np.where(((centre-origin_t)@axis_t) > -.05, 'neck', np.where(centre[:, 1] < .6, 'legs', 'other')))
    report = {'space': 'linear', 'detailMix': detail_mix,
              'referenceRGB': reference.tolist(), 'targetRGB': np.asarray(target).tolist(),
              'reference': 'area-weighted median of the Human skin at body-face UV centroids',
              'texels': int(skin.sum()), 'excludedTexels': int(outside.sum()),
              'excludedChroma': int(chroma_out.sum()), 'excludedLuminance': int(lum_out.sum()),
              'excludedCore': int((chroma_out | lum_out).sum()), 'excludedGrown': int(outside.sum()-(chroma_out | lum_out).sum()),
              'excludedDarker': int((outside & (log_lum < lmed)).sum()),
              'excludedLighter': int((outside & (log_lum >= lmed)).sum()),
              'excludedByRegion': dict(sorted(Counter(region.tolist()).items())), 'excludedUnfilled': int(unfilled.sum()),
              'excludedUnfilledByRegion': dict(sorted(Counter(region[unfilled].tolist()).items())),
              'unfilledNote': 'excluded texels with no dyed-skin texel reachable through excluded texels: '
                              'filled by a 16-px dilation across the chart gutter, else the target colour',
              'chromaMedian': med.tolist(), 'chromaMAD': mad.tolist(), 'lumRatioMedian': float(np.exp(lmed)),
              'lumLogMAD': float(lmad),
              'exclusionRule': {'chromaDistanceMAD': CHROMA_MAD, 'logLuminanceMAD': LUM_LOG_MAD, 'sides': 'both',
                                'grownTexels': EXCLUDE_GROW, 'fill': 'dilation from neighbouring dyed skin texels'}}
    if tone_report:
        report['neckTone'] = tone_report
    return result, report


def neck_tone(lower, skin_pixels, upper, head_pixels, visible, origin_t, axis_t, upper_cut, h1):
    """Per-azimuth linear gain taking the dyed Human neck just below the cut to
    the race head just above the rim (both low-passed around the neck). A head
    whose back is lighter than its throat then keeps that difference down the
    neck instead of a darker band under a lighter skull."""
    w = NECK_SIZE[0]
    pitch = (h1-NECK_H0)/NECK_SIZE[1]
    g_cut = int(np.floor((LOWER_CUT-NECK_H0)/pitch-.5))
    g_ring = int(np.ceil((LOWER_CUT-TONE_RING-NECK_H0)/pitch-.5))
    g_top = int(np.ceil((upper_cut-NECK_H0)/pitch-.5))
    g_head = int(np.floor((upper_cut+TONE_RING-NECK_H0)/pitch-.5))
    parts = []
    for p, f, uv in skin_faces(lower):
        t = (p.astype(float)-origin_t)@axis_t
        parts.append((p, f[(t[f].max(1) > LOWER_CUT-TONE_RING-pitch) & (np.abs(p[f][..., 0]).max(1) < .12)], uv))
    human, _ = detail_canvas(parts, skin_pixels, origin_t, axis_t, (g_ring, g_cut), pitch, w)
    head, _ = detail_canvas(head_band_parts(upper, visible, origin_t, axis_t, upper_cut, TONE_RING+pitch),
                            head_pixels, origin_t, axis_t, (g_top, g_head), pitch, w)

    def ring(image):
        mean = srgb_to_linear(image).mean(0)
        return np.stack([gaussian_filter(mean[:, c], TONE_SIGMA, mode='wrap') for c in range(3)], -1)
    lower_ring, upper_ring = ring(human), ring(head)
    gain = np.clip(upper_ring/np.maximum(lower_ring, 1e-6), TONE_CLIP[0], TONE_CLIP[1])
    lum = (upper_ring@LUMA)/np.maximum(lower_ring@LUMA, 1e-6)
    return gain, {'rule': f'per-column linear gain (rim band of the head over the dyed Human neck, each {TONE_RING*100:g} cm '
                          f'tall, circular gaussian {TONE_SIGMA:g} of {w} columns) applied as gain^weight; weight 1 at '
                          f'the cut, smoothstep to 0 at travel {TONE_LOW:g} m and beyond {sum(TONE_RADIUS):g} m from the '
                          'neck axis',
                  'luminanceGain': {'min': float(lum.min()), 'median': float(np.median(lum)), 'max': float(lum.max()),
                                    'front': float(lum[w//4]), 'back': float(lum[3*w//4])},
                  'clip': list(TONE_CLIP)}


def intact(upper, key):
    """A head primitive's faces without the UV-broken ones (broken_uv)."""
    faces = upper['f'][key]
    return faces[~upper['broken'][key]] if 'broken' in upper else faces


def neck_plug(upper, origin, axis, upper_cut):
    """A cone from the rim to a point 3 cm down the neck axis: in the body the
    bridge and the Human neck close the head's neck opening."""
    p = upper['a']['POSITION'].astype(float)
    boundary = plane_rim(upper, origin, axis, upper_cut)
    ring = p[spb.loops({'a': upper['a'], 'boundary': boundary}, origin, axis)[0]]
    count = len(ring)
    return (np.concatenate([ring, (ring.mean(0)-.03*axis)[None]]),
            np.stack([np.arange(count), (np.arange(count)+1) % count, np.full(count, count)], 1))


def band_visibility(upper, origin, axis, upper_cut, band=.05):
    """Which intact head-body faces reaching [rim, rim + band] are outer skin:
    a ray from the centroid escapes along one of 60 directions, every head
    face and a neck plug occluding. The detail and tone bands sample only
    these, never a leftover inner wall a few millimetres inside the skin."""
    p = upper['a']['POSITION'].astype(float)
    faces = np.concatenate(list(upper['f'].values()))
    head = intact(upper, ('body', 'head'))
    travel = (p-origin)@axis
    near = (travel[head].min(1) < upper_cut+band) & (travel[head].max(1) > upper_cut-1e-6)
    plug = neck_plug(upper, origin, axis, upper_cut)
    pp = np.concatenate([p, plug[0]])
    ff = np.concatenate([head[near], faces, plug[1]+len(p)])
    seen, _ = visibility(pp, np.zeros_like(pp), ff, np.arange(int(near.sum())))
    visible = np.zeros(len(head), bool)
    visible[np.flatnonzero(near)] = seen[:int(near.sum())]
    return visible, {'bandFaces': int(near.sum()), 'hiddenBandFaces': int(near.sum()-visible.sum()),
                     'rule': 'centroid ray escapes along one of 60 directions; occluders: every head face and a cone '
                             'plugging the neck opening'}


def head_band_parts(upper, visible, origin, axis, upper_cut, band):
    """detail_canvas parts for the visible head skin in [rim, rim + band]."""
    p, head = upper['a']['POSITION'], intact(upper, ('body', 'head'))
    t = (p.astype(float)-origin)@axis
    sel = visible & (t[head].min(1) < upper_cut+band) & (t[head].max(1) > upper_cut)
    return [(p, head[sel], upper['a']['TEXCOORD_0'])]


def fold_rows(m, a, b):
    """Mirror integer rows into [a, b] (triangle wave), so tiles meet without a step."""
    n = b-a+1
    k = np.mod(m-a, 2*n)
    return a+np.where(k < n, k, 2*n-1-k)


def detail_canvas(parts, pixels, origin, axis, rows, pitch, width, with_radius=False):
    """Skin colour in neck-atlas cylinder space for global rows [first, last].

    parts: (positions, faces, per-vertex source UVs). Where two faces map to
    one texel the smaller radius wins (the neck, not an overhanging jaw).
    With `with_radius`, also the sampled surface's radius per texel (nan: none)."""
    first, last = rows
    height = last-first+1
    lo = NECK_H0+first*pitch
    image = np.zeros((height, width, 3)); best = np.full((height, width), np.inf)
    for p, faces, uv in parts:
        if not len(faces):
            continue
        p = p.astype(float)
        cyl = cylinder_uv(p, faces, origin, axis, lo+height*pitch, h0=lo).reshape(-1, 2)
        face, y, x, bary = raster(cyl, np.arange(len(faces)*3).reshape(-1, 3), (width, height), wrap=True)
        rel = p[faces]-origin
        radius = np.linalg.norm(rel-(rel@axis)[..., None]*axis, axis=-1)
        r = (bary*radius[face]).sum(1)
        colour = spb.sample_image(np.rint(pixels*255), np.einsum('ni,nic->nc', bary, uv[faces[face]].astype(float)))
        key = y*width+x
        order = np.lexsort((r, key))
        keep = order[np.r_[True, key[order][1:] != key[order][:-1]]]
        keep = keep[r[keep] < best[y[keep], x[keep]]]
        image[y[keep], x[keep]] = colour[keep]; best[y[keep], x[keep]] = r[keep]
    valid = np.isfinite(best)
    covered = float(valid.mean())
    image, valid = dilate(image, valid, 64)
    image[~valid] = image[valid].mean(0)
    if with_radius:
        return image, covered, np.where(np.isfinite(best), best, np.nan)
    return image, covered


def lowpass(image, sigma):
    return np.stack([gaussian_filter(image[..., c], sigma, mode=('nearest', 'wrap')) for c in range(image.shape[-1])], -1)


def radius_steps(radius):
    """Texels where the sampled surface steps in radius (FEATURE_STEP_M):
    across a column, or as a kink down a column (a second difference, so a
    steep but smooth jaw line is not a step). The first FEATURE_STEP_SKIP
    rows next to the cut are never steps: the rim keeps its grain."""
    r = np.where(np.isfinite(radius), radius, np.nanmedian(radius))
    across = np.abs(np.diff(r, axis=1, append=r[:, :1]))
    across = np.maximum(across, np.roll(across, 1, axis=1))
    padded = np.concatenate([2*r[:1]-r[1:2], r, 2*r[-1:]-r[-2:-1]], 0)
    down = np.abs(padded[2:]-2*padded[1:-1]+padded[:-2])
    step = np.maximum(across, down) > FEATURE_STEP_M
    step[:FEATURE_STEP_SKIP] = False
    return step


def feature_weight(image, radius=None):
    """1 on race features in a detail canvas (FEATURE_* above), 0 on skin grain,
    with a short feathered falloff; also the masked fractions (all, by colour,
    by radius step)."""
    dev = np.linalg.norm(image-lowpass(image, FEATURE_SIGMA), axis=-1)
    dev = gaussian_filter(dev, FEATURE_SMOOTH, mode=('nearest', 'wrap'))
    median = np.median(dev)
    colour = dev > median+FEATURE_MADS*1.4826*np.median(np.abs(dev-median))
    steps = radius_steps(radius) if radius is not None else np.zeros_like(colour)
    grow = lambda m: binary_fill_holes(binary_dilation(m, iterations=FEATURE_GROW)) if m.any() else m
    mask = grow(colour | steps)
    weight = np.maximum(mask, gaussian_filter(mask.astype(float), FEATURE_FEATHER, mode=('nearest', 'wrap')))
    return weight, {'all': float(mask.mean()), 'colour': float(grow(colour).mean()), 'radiusStep': float(grow(steps).mean())}


def streak_ratio(image, sigma=STREAK_SIGMA):
    """Across-over-along high-pass gradient energy (about 1 for isotropic grain).

    A column-constant fill gives vertical streaks: large d/dx, no d/dy."""
    lum = image@LUMA
    hp = lum-gaussian_filter(lum, sigma, mode=('nearest', 'wrap'))
    return float((np.diff(hp, axis=1)**2).mean()/max((np.diff(hp, axis=0)**2).mean(), 1e-12))


def neck_texture(neck, bridge, lower, upper, skin_pixels, head_pixels, origin_t, axis_t, upper_cut, h1, floor, visible):
    """B7c: one cylinder for shared_neck (exact I1 transfer) and the bridge.

    Bridge texel = a smooth blend of the low-passed skin either side plus the
    high-pass grain of the Human neck below the cut and of the head above the
    rim, each mirrored into the bridge. At either rim the sum is the
    neighbouring skin texel itself, so neither border steps. The head band
    samples only outer skin (band_visibility)."""
    w, h = NECK_SIZE
    pitch = (h1-NECK_H0)/h
    image = np.zeros((h, w, 3)); valid = np.zeros((h, w), bool)
    # shared_neck: barycentric to the old Human UV, sampled from the encoded I1.
    faces = neck['f'][('body', 4)]
    face, y, x, bary = raster(neck['a']['TEXCOORD_0'], faces, NECK_SIZE, wrap=True)
    old = np.einsum('ni,nic->nc', bary, neck['oldUV'][faces[face]])
    image[y, x] = spb.sample_image(np.rint(skin_pixels*255), old); valid[y, x] = True
    # Detail sources: Human neck skin in [max(floor, cut - band), cut] (the
    # closed-ring band) and race-head skin in [rim, rim + band].
    band_lo = max(floor, LOWER_CUT-DETAIL_BAND)
    g_low, g_cut = int(np.ceil((band_lo-NECK_H0)/pitch-.5)), int(np.floor((LOWER_CUT-NECK_H0)/pitch-.5))
    g_top = int(np.ceil((upper_cut-NECK_H0)/pitch-.5))
    g_high = int(np.floor((upper_cut+DETAIL_BAND-NECK_H0)/pitch-.5))
    body_key = next(k for k in lower['f'] if k[0] == 'body')
    human_parts = []
    for p, f, uv in ((lower['a']['POSITION'], lower['f'][body_key], lower['a']['TEXCOORD_0']),
                     (neck['a']['POSITION'], faces, neck['oldUV'])):
        t = (p.astype(float)-origin_t)@axis_t
        sel = (t[f].max(1) > band_lo-pitch) & (t[f].min(1) < LOWER_CUT) & (np.abs(p[f][..., 0]).max(1) < .12)
        human_parts.append((p, f[sel], uv))
    head_parts = head_band_parts(upper, visible, origin_t, axis_t, upper_cut, DETAIL_BAND+pitch)
    human, human_cover, human_radius = detail_canvas(human_parts, skin_pixels, origin_t, axis_t, (g_low, g_cut), pitch, w, True)
    head, head_cover, head_radius = detail_canvas(head_parts, head_pixels, origin_t, axis_t, (g_top, g_high), pitch, w, True)
    human_low, head_low = lowpass(human, DETAIL_SIGMA), lowpass(head, DETAIL_SIGMA)
    # Features in either band carry no grain (no ghost copy in the bridge).
    # Human band rows run upward to the cut, head band rows upward from the rim:
    # flip the human band so its first rows (never steps) are the cut's.
    (human_feature, human_masked) = feature_weight(human[::-1], human_radius[::-1])
    human_feature = human_feature[::-1]
    (head_feature, head_masked) = feature_weight(head, head_radius)
    human_grain = (human-human_low)*(1-human_feature)[..., None]
    head_grain = (head-head_low)*(1-head_feature)[..., None]
    bf = bridge['f'][('body', 4)]
    face, y, x, bary = raster(bridge['a']['TEXCOORD_0'], bf, NECK_SIZE, wrap=True)
    travel = NECK_H0+(y+.5)*pitch
    s = np.clip((travel-LOWER_CUT)/(upper_cut-LOWER_CUT), 0, 1); s = (s*s*(3-2*s))[:, None]
    below = fold_rows(2*g_cut+1-y, g_low, g_cut)-g_low
    above = fold_rows(2*g_top-1-y, g_top, g_high)-g_top
    base = (1-s)*human_low[g_cut-g_low, x]+s*head_low[0, x]
    grain = (1-s)*human_grain[below, x]+s*head_grain[above, x]
    image[y, x] = np.clip(base+grain, 0, 1); valid[y, x] = True
    covered = int(valid.sum())
    image, valid = dilate(image, valid, 4)
    # Every other texel is skin: interpolate each column periodically, so row
    # 0 continues row 511 under repeat-wrap and mip sampling (decision 9).
    rows = np.arange(h)
    for col in range(w):
        have = np.flatnonzero(valid[:, col])
        if not len(have):
            raise ValueError('Neck texture column without coverage')
        for c in range(3):
            image[~valid[:, col], col, c] = np.interp(rows[~valid[:, col]], have, image[have, col, c], period=h)
    bridge_texture = {'method': 'low-passed blend of the skin either side plus mirrored high-pass grain of the '
                                'Human neck below the cut and the head above the rim',
                      'detailBandM': DETAIL_BAND, 'humanBandM': [band_lo, LOWER_CUT], 'lowpassSigmaTexels': DETAIL_SIGMA,
                      'rows': {'humanBand': [g_low, g_cut], 'bridge': [g_cut+1, g_top-1], 'headBand': [g_top, g_high]},
                      'humanBandCoverage': human_cover, 'headBandCoverage': head_cover,
                      'featureMask': {'rule': f'colour deviation from a sigma {FEATURE_SIGMA:g} lowpass (smoothed '
                                              f'{FEATURE_SMOOTH:g}) over median + {FEATURE_MADS:g} robust MAD, or a '
                                              f'sampled-surface radius step over {FEATURE_STEP_M*1000:g} mm between '
                                              f'texels (not in the {FEATURE_STEP_SKIP} rows next to the cut), grown '
                                              f'{FEATURE_GROW} texels, holes filled, feathered {FEATURE_FEATHER:g}; '
                                              'no grain there',
                                      'humanBandMasked': human_masked, 'headBandMasked': head_masked}}
    return image, {'size': [w, h], 'h0': NECK_H0, 'h1': h1, 'coveredTexels': covered,
                   'topRimV': float((upper_cut-NECK_H0)/(h1-NECK_H0)), 'bridgeTexture': bridge_texture}, (human, head)


def neck_streaks(neck_pixels, detail, rows):
    """Bridge grain against the skin bands either side, in the same cylinder
    texels. The bridge mixes both grains, so its reference is the more
    anisotropic neighbour; the old one-colour-per-column fill scored 4.4."""
    human, head = detail
    lo, hi = rows['bridge']
    ratios = {'bridge': streak_ratio(neck_pixels[lo+2:hi-1]), 'humanNeck': streak_ratio(human),
              'headBand': streak_ratio(head)}
    ratios['bridgeOverHumanNeck'] = ratios['bridge']/ratios['humanNeck']
    ratios['bridgeOverNeighbours'] = ratios['bridge']/max(ratios['humanNeck'], ratios['headBand'])
    ratios.update({'limit': STREAK_LIMIT, 'sigmaTexels': STREAK_SIGMA,
                   'pass': ratios['bridgeOverNeighbours'] < STREAK_LIMIT})
    return ratios


def skyline(sizes, side, gutter):
    """Bottom-left skyline packing without rotation; gutter on every side."""
    usable = side-gutter
    sky = [[0, 0, usable]]
    corners = [None]*len(sizes)
    for i in sorted(range(len(sizes)), key=lambda i: (-sizes[i][1], -sizes[i][0])):
        w, h = sizes[i][0]+gutter, sizes[i][1]+gutter
        best = None
        for s in range(len(sky)):
            x = sky[s][0]
            if x+w > usable:
                break
            y, remaining, t = 0, w, s
            while remaining > 0:
                y = max(y, sky[t][1]); remaining -= sky[t][2]; t += 1
            if y+h <= usable and (best is None or (y+h, x) < (best[0]+h, best[1])):
                best = (y, x)
        if best is None:
            return None
        y, x = best
        corners[i] = (x+gutter, y+gutter)
        updated = []
        for sx, sy, sw in sky:
            if sx+sw <= x or sx >= x+w:
                updated.append([sx, sy, sw]); continue
            if sx < x:
                updated.append([sx, sy, x-sx])
            if sx+sw > x+w:
                updated.append([x+w, sy, sx+sw-x-w])
        updated.append([x, y+h, w]); updated.sort()
        sky = []
        for seg in updated:
            if sky and sky[-1][1] == seg[1] and sky[-1][0]+sky[-1][2] == seg[0]:
                sky[-1][2] += seg[2]
            else:
                sky.append(seg)
    return corners


def pack_head(upper, head_pixels, atlas, density_max, human_face, head_joint, head_index):
    """B7d: islands scaled uniformly to one density and shelf-free packed."""
    src = head_pixels.shape[1]
    p, uv = upper['a']['POSITION'], upper['a']['TEXCOORD_0'].astype(float)
    hw = joint_weight(upper['a'], head_index)
    faces = np.concatenate(list(upper['f'].values()))
    Ds = float(np.median(texel_density(p, uv, faces, (src, src))[0]))
    face = face_filter(p, upper['a']['NORMAL'], faces, head_joint, hw)
    Fs = float(np.median(texel_density(p, uv, faces[face], (src, src))[0]))
    centre = p[faces].astype(float).mean(1)
    normal = np.cross(p[faces[:, 1]]-p[faces[:, 0]], p[faces[:, 2]]-p[faces[:, 0]]).astype(float)
    normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-12)
    design_face = (normal[:, 2] > .5) & (centre[:, 1] > 1.57)
    Fs_design = float(np.median(texel_density(p, uv, faces[design_face], (src, src))[0]))
    floor = max(12., human_face*Ds/Fs)
    # Islands: index-connected components inside each primitive.
    islands = []
    for key, f in upper['f'].items():
        used = np.unique(f)
        remap = np.full(len(p), -1); remap[used] = np.arange(len(used))
        local = remap[f]
        e = np.concatenate([local[:, [0, 1]], local[:, [1, 2]]])
        label = connected_components(coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(len(used), len(used))).tocsr(), directed=False)[1]
        for c in np.unique(label):
            islands.append(used[label == c])
    D = density_max
    while D >= floor-1e-9:
        k = D/Ds  # atlas px per source px at density D
        lo = [uv[v].min(0)*src for v in islands]
        sizes = [tuple(int(s) for s in np.ceil((uv[v].max(0)-uv[v].min(0))*src*k)+1) for v in islands]
        corners = skyline(sizes, atlas, 4)
        if corners is not None:
            break
        D *= .95
    else:
        raise ValueError(f'Head islands do not fit a {atlas} atlas at {floor:.2f} px/cm; use --head-atlas 2048')
    new = uv.copy()
    for v, start, corner in zip(islands, lo, corners):
        new[v] = ((uv[v]*src-start)*k+corner)/atlas
    return new, {'size': [atlas, atlas], 'pxPerCm': None, 'facePxPerCm': None, 'targetPxPerCm': float(D),
                 'sourcePxPerCm': Ds, 'sourceFacePxPerCm': Fs, 'sourceFacePxPerCmDesignFilter': Fs_design,
                 'floorPxPerCm': float(floor), 'islands': len(islands), 'gutterPx': 4, 'sourceSize': src}



def bake_head(upper, old_uv, head_pixels, atlas, corner_colours=None):
    faces = np.concatenate(list(upper['f'].values()))
    face, y, x, bary = raster(upper['a']['TEXCOORD_0'], faces, (atlas, atlas))
    old = np.einsum('ni,nic->nc', bary, old_uv[faces[face]])
    image = np.zeros((atlas, atlas, 3)); valid = np.zeros((atlas, atlas), bool)
    image[y, x] = spb.sample_image(np.rint(head_pixels*255), old); valid[y, x] = True
    if corner_colours:
        # UV-broken faces: their corners' colours on the intact faces.
        flat = np.full(len(faces), -1)
        colours, offset, start = [], 0, 0
        for key, f in upper['f'].items():
            if key in corner_colours:
                mask = upper['broken'][key]
                flat[offset+np.flatnonzero(mask)] = start+np.arange(int(mask.sum()))
                colours.append(corner_colours[key]); start += int(mask.sum())
            offset += len(f)
        colours = np.concatenate(colours)
        sel = flat[face] >= 0
        image[y[sel], x[sel]] = np.einsum('ni,nic->nc', bary[sel], colours[flat[face[sel]]])
    median = np.median(image[valid], axis=0)
    image, valid = dilate(image, valid, 4)
    image[~valid] = median
    return image


def append_array(d, binary, values, kind, component=5126):
    dtype = {5126: '<f4', 5125: '<u4', 5123: '<u2', 5121: '<u1'}[component]
    values = np.ascontiguousarray(values, dtype=dtype)
    view = spb.append_view(d, binary, values.tobytes())
    spec = {'bufferView': view, 'componentType': component, 'count': len(values), 'type': kind}
    if kind == 'VEC3':
        spec.update(min=values.min(0).tolist(), max=values.max(0).tolist())
    d['accessors'].append(spec)
    return len(d['accessors'])-1


def write_group_v3(d, binary, group, meshes):
    """spb.write_group with each primitive's joint width kept (u8 or u16)."""
    for (name, material), faces in group['f'].items():
        if not len(faces):
            continue
        used, inverse = np.unique(faces, return_inverse=True)
        rows = np.concatenate([np.ascontiguousarray(group['a'][k][used]).view('u1').reshape(len(used), -1)
                               for k in KEYS], axis=1)
        _, keep, remap = np.unique(rows, axis=0, return_index=True, return_inverse=True)
        used, inverse = used[keep], remap.ravel()[inverse.ravel()]
        attrs = {}
        for k in KEYS:
            values = group['a'][k][used]
            component = (5121 if values.dtype == np.uint8 else 5123) if k == 'JOINTS_0' else 5126
            attrs[k] = append_array(d, binary, values, 'VEC'+str(values.shape[1]), component)
        indices = append_array(d, binary, inverse, 'SCALAR', 5125)
        meshes.setdefault(name, []).append({'attributes': attrs, 'indices': indices, 'material': material,
                                           'extras': {'sourceRole': group['role']}})


def copy_accessor(d, binary, source, blob, index):
    """Copy one accessor's bytes verbatim into a fresh view."""
    spec = copy.deepcopy(source['accessors'][index])
    view = source['bufferViews'][spec['bufferView']]
    width = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}[spec['type']]
    size = {5121: 1, 5123: 2, 5125: 4, 5126: 4}[spec['componentType']]
    if view.get('byteStride', width*size) != width*size:
        raise ValueError('strided accessor')
    start = view.get('byteOffset', 0)+spec.get('byteOffset', 0)
    spec['bufferView'] = spb.append_view(d, binary, bytes(blob[start:start+spec['count']*width*size]))
    spec.pop('byteOffset', None)
    d['accessors'].append(spec)
    return len(d['accessors'])-1


def as_f4(group):
    for k in ('POSITION', 'NORMAL', 'TEXCOORD_0', 'WEIGHTS_0'):
        group['a'][k] = np.asarray(group['a'][k], dtype='<f4')
    return group


def build(root, slug, out, head=None, head_texture=None, template=None, head_atlas=None,
          density_max=20., neck_profile='smooth', detail_mix=.2, skin_target='face'):
    root, out = Path(root).resolve(), Path(out).resolve()
    if 'godot-client' in out.parts:
        raise ValueError('Use a scratch --out outside godot-client')
    target = out/f'{slug}.glb'
    if target.exists():
        raise FileExistsError(target)
    sex = slug.rsplit('_', 1)[1]
    races = root/'godot-client/assets/actors/native/races'
    template = Path(template or races/f'luminous_{sex}.glb')
    head = Path(head or races/f'{slug}.glb')
    td, tb = ea.read_glb(template); hd, hb = ea.read_glb(head)
    if 'eloriaHumanPack' not in td['asset'].get('extras', {}):
        raise ValueError(f'{template} is not a packed Human body')
    shape = hd['asset'].get('extras', {}).get('sharedBodyShape', {})
    if shape.get('version') != 2:
        raise ValueError(f'{head} is not a v2 race body; pass --head (the pre-install backup)')
    provenance = hd['asset']['extras']['highResolutionHead']
    texture_path, texture_kind = locate_head_texture(root, slug, provenance, head_texture)
    inputs = {'template': template, 'head': head, 'headTexture': texture_path, 'tool': Path(__file__)}
    hashes = input_digests(inputs)
    head_pixels, texture_sha = head_texture_pixels(texture_path, texture_kind)
    # B0: rigs equal within 1e-5 by name; the shipped head image is its half.
    names_t, world_t, origin_t, axis_t = rig_frame(td)
    names_h, world_h, origin_h, axis_h = rig_frame(hd)
    if names_t != names_h or len(names_t) != 77:
        raise ValueError('joint names/order differ')
    rig_delta = float(np.abs(world_t-world_h).max())
    if rig_delta > 1e-5:
        raise ValueError(f'rest rigs differ by {rig_delta}')
    head_mesh = next(m for m in hd['meshes'] if m['name'] == 'body')
    head_prim = next(p for p in head_mesh['primitives'] if p.get('extras', {}).get('sourceRole') == 'race_head')
    shipped = spb.material_image(hd, hb, head_prim['material'])[1].astype(float)
    half = np.asarray(Image.fromarray(np.rint(head_pixels*255).astype('u1')).resize(shipped.shape[1::-1], Image.LANCZOS)).astype(float)
    half_delta = float(np.abs(half-shipped).mean())
    if half_delta > 3:
        raise ValueError(f'2048 head texture does not match the shipped head ({half_delta:.2f} levels)')
    if texture_kind != 'meshy-original' and head_pixels.shape[0] < 2048:
        print('WARNING: head texture source is', head_pixels.shape, flush=True)
    albedo = None
    if slug in HEAD_ALBEDO_TARGETS:
        wanted = HEAD_ALBEDO_TARGETS[slug]
        gain, before_lum, after_lum = head_albedo_gain(hd, hb, head_pixels, wanted['medianLuminance'])
        head_pixels = linear_to_srgb(srgb_to_linear(head_pixels)*gain)
        albedo = {'space': 'linear', 'gain': gain, 'medianLuminanceBefore': before_lum, 'medianLuminanceAfter': after_lum,
                  **wanted, 'measure': 'median sRGB luminance (0-255) of the 2048 source at race_head body-face UV centroids'}
    upper_cut = float(shape['upperCutM'])
    # B2: Human below the plane; whole-below triangles stay byte copies.
    common = spb.block(td, tb)
    template_rows = len(common['a']['POSITION'])
    travel = (common['a']['POSITION'].astype(float)-origin_t)@axis_t
    lower = spb.clip(common, travel-LOWER_CUT, keep_positive=False)
    if any(k[0] in ('eyes', 'eyebrows', 'scalp') for k in lower['f']):
        raise ValueError('Human face parts reach below the cut')
    lower_rings = spb.loops(lower, origin_t, axis_t)
    if len(lower_rings) != 1:
        raise ValueError(f'lower cut has {len(lower_rings)} rings')
    below = sum(int((travel[f] < LOWER_CUT-1e-6).all(1).sum()) for f in common['f'].values())
    # B3/B4: the v2 head, rim on its own plane, then cleanup.
    upper = block_roles(hd, hb, {'race_head'})
    upper['boundary'] = plane_rim(upper, origin_h, axis_h, upper_cut)
    upper_rings = spb.loops(upper, origin_h, axis_h)
    if len(upper_rings) != 1:
        raise ValueError(f'head rim has {len(upper_rings)} rings')
    head_counts = {k[0]: len(f) for k, f in upper['f'].items()}
    cleanup = clean_head(upper, origin_h, axis_h, upper_cut)
    upper['boundary'] = plane_rim(upper, origin_h, axis_h, upper_cut)
    if len(spb.loops(upper, origin_h, axis_h)) != 1:
        raise ValueError('head rim is not one ring after cleanup')
    upper['broken'], source_density, broken_counts = broken_uv(upper, head_pixels.shape[1], origin_h, axis_h, upper_cut)
    broken_report = {'faces': {k[0]: int(m.sum()) for k, m in upper['broken'].items() if m.any()}, **broken_counts,
                     'rule': f'all corners on the upper cut plane (v2 inner-loop caps), or an edge over {BROKEN_UV_RATIO:g}x '
                             f'the median px/cm and over {BROKEN_UV_PX:g} source px',
                     'chart': 'own planar chart at the median density; texels interpolate the colours of their corners on intact faces'}
    # B5: weld both rims.
    lower_rows = np.unique(lower['boundary']); lower_rows = lower_rows[lower_rows >= template_rows]
    used = np.unique(np.concatenate(list(upper['f'].values())))
    upper_rows = used[np.abs((upper['a']['POSITION'][used].astype(float)-origin_h)@axis_h-upper_cut) < 2e-6]
    weld_report = {'lower': weld_ring(lower, lower_rows), 'upper': weld_ring(upper, upper_rows)}
    # Ssarathi: the v2 tail, root sunk into the Human trousers.
    tail = tail_group(hd, hb)
    tail_report = fit_tail(tail, lower, names_t, TAIL_FEATHER.get(slug)) if tail else None
    # B6: the bridge (never an automatic linear fallback).
    bridge, lr, ur = spb.neck_bridge(lower, upper, origin_t, axis_t, 4, lower, smooth_profile=neck_profile == 'smooth')
    groove = ungroove(bridge, origin_t, axis_t)
    as_f4(bridge); bridge['role'] = 'neck_join'
    h1 = NECK_H0+(upper_cut-NECK_H0)/(1-2.5/NECK_SIZE[1])
    # B7a: recolour the Human skin atlas: its median takes the face reference
    # (a unified palette then dyes body and face alike); the neck bends to the
    # head rim per azimuth (neck_tone).
    visible, visible_report = band_visibility(upper, origin_h, axis_h, upper_cut)
    template_mat = next(k for k in lower['f'] if k[0] == 'body')[1]
    wardrobe_mat = next(k for k in lower['f'] if k[0].startswith('wardrobe_'))[1]
    template_index, template_pixels = spb.material_image(td, tb, template_mat)
    template_pixels = template_pixels.astype(float)/255
    regions = json.loads(Path(__file__).with_name('face_regions.json').read_text())
    ring, ring_samples = ring_colour(upper, head_pixels, origin_h, axis_h, upper_cut)
    face_ref = face_reference(upper, head_pixels, regions['models'][slug], regions['projection'])
    skin_colour = face_ref if skin_target == 'face' else ring
    first_pass, _ = recolour_skin(lower, template_pixels, skin_colour, origin_t, axis_t, detail_mix)
    gain, tone_report = neck_tone(lower, first_pass, upper, head_pixels, visible, origin_t, axis_t, upper_cut, h1)
    skin, recolour = recolour_skin(lower, template_pixels, skin_colour, origin_t, axis_t, detail_mix, tone=gain)
    recolour.update(targetSource=skin_target, faceReferenceRGB=face_ref.tolist(), neckRingRGB=ring.tolist(),
                    neckRingSamples=ring_samples, neckTone={**tone_report, **recolour.get('neckTone', {})},
                    bandVisibility=visible_report)
    skin_payload = encode_jpeg(skin)
    skin_pixels = decode(skin_payload)
    # B7b/B7c: shared_neck split, cylinder UVs and the neck texture.
    neck, neck_report = split_shared_neck(lower, bridge, origin_t, axis_t, h1)
    bf = bridge['f'][('body', 4)]
    bridge_uv = cylinder_uv(bridge['a']['POSITION'], bf, origin_t, axis_t, h1)
    bridge['a'] = {k: v[bf.ravel()] for k, v in bridge['a'].items()}
    bridge['a']['TEXCOORD_0'] = bridge_uv.reshape(-1, 2).astype('<f4')
    bridge['f'] = {('body', 4): np.arange(len(bf)*3).reshape(-1, 3)}
    neck_pixels, neck_atlas, detail = neck_texture(neck, bridge, lower, upper, skin_pixels, head_pixels,
                                                   origin_t, axis_t, upper_cut, h1, neck_report['closedRingFloorM'], visible)
    neck_payload = encode_jpeg(neck_pixels)
    neck_atlas['streaks'] = neck_streaks(decode(neck_payload), detail, neck_atlas['bridgeTexture']['rows'])
    # B7d: head atlas.
    human_face = human_face_density(td, tb)
    corner_colours = broken_corner_colours(upper, upper['broken'], head_pixels)
    chart_broken(upper, upper['broken'], head_pixels.shape[1], source_density)
    old_uv = upper['a']['TEXCOORD_0'].astype(float).copy()
    head_joint = world_h[names_h.index('Head')][:3, 3]
    sizes = (head_atlas,) if head_atlas else (1024, 2048)
    for head_atlas in sizes:
        try:
            packed, head_atlas_report = pack_head(upper, head_pixels, head_atlas, density_max, human_face,
                                                  head_joint, names_h.index('Head'))
            break
        except ValueError:
            if head_atlas == sizes[-1]:
                raise
    head_atlas_report['triedSizes'] = list(sizes[:sizes.index(head_atlas)+1])
    upper['a']['TEXCOORD_0'] = packed.astype('<f4')
    head_payload = encode_jpeg(bake_head(upper, old_uv, head_pixels, head_atlas, corner_colours))
    faces = np.concatenate(list(upper['f'].values()))
    density, _ = texel_density(upper['a']['POSITION'], upper['a']['TEXCOORD_0'], faces, (head_atlas, head_atlas))
    face = face_filter(upper['a']['POSITION'], upper['a']['NORMAL'], faces, head_joint, joint_weight(upper['a'], names_h.index('Head')))
    head_atlas_report['pxPerCm'] = float(np.median(density))
    head_atlas_report['facePxPerCm'] = float(np.median(texel_density(upper['a']['POSITION'], upper['a']['TEXCOORD_0'], faces[face], (head_atlas, head_atlas))[0]))
    head_atlas_report['humanFacePxPerCm'] = human_face
    head_atlas_report['sourceKind'] = texture_kind
    # B8: assemble a fresh document in the v2 layout.
    spec = {'version': 3, 'template': template.stem, 'templateSHA256': hashes['template'],
            'headSource': head.name, 'headSourceSHA256': hashes['head'], 'headTextureSHA256': texture_sha,
            'skeleton': 'headSource', 'lowerCutM': LOWER_CUT, 'upperCutM': upper_cut, 'bodyCutMode': 'neck-plane',
            'neckBase': {'startM': -.060, 'radiusM': .150},
            'neckProfile': 'boundary-tangent' if neck_profile == 'smooth' else 'linear',
            'skinRecolour': {**{k: recolour[k] for k in ('space', 'detailMix', 'referenceRGB', 'targetRGB', 'targetSource',
                                                         'texels', 'excludedTexels', 'exclusionRule')},
                             'neckTone': {'lowM': TONE_LOW, 'ringM': TONE_RING, 'sigmaColumns': TONE_SIGMA,
                                          'luminanceGain': recolour['neckTone']['luminanceGain']}},
            'headAtlas': {k: head_atlas_report[k] for k in ('size', 'pxPerCm', 'facePxPerCm', 'sourcePxPerCm', 'sourceFacePxPerCm', 'islands', 'gutterPx', 'sourceSize')},
            'neckAtlas': {'size': list(NECK_SIZE), 'bridgeTexture': 'rim blend + mirrored skin grain'},
            'cleanup': cleanup, 'toolSHA256': hashes['tool']}
    if albedo:
        spec['headAlbedo'] = albedo
    if groove['columns']:
        spec['neckProfileRepair'] = {k: groove[k] for k in ('columns', 'maxDipBeforeM', 'maxDipAfterM')}
    if broken_report['faces']:
        spec['brokenUV'] = broken_report
    if tail:
        spec['tail'] = {k: tail_report[k] for k in ('trianglesBefore', 'fragmentTriangles', 'triangles')}
        spec['tail']['rootSinkM'] = {'depth': TAIL_DEPTH, 'falloff': TAIL_SINK_FALLOFF, 'maxShift': tail_report['root']['maxShiftM']}
        if 'feather' in tail_report:
            spec['tail']['featherM'] = tail_report['feather']['featherM']
    d, binary = assemble(hd, hb, td, tb, lower, upper, bridge, neck, spec,
                         head_payload, skin_payload, spb.image_bytes(td, tb, spb.material_image(td, tb, wardrobe_mat)[0]),
                         neck_payload, template_mat, wardrobe_mat, tail)
    d, binary = g.compact(d, bytes(binary))
    if input_digests(inputs) != hashes:
        raise ValueError('An input changed during generation')
    out.mkdir(parents=True, exist_ok=True)
    g.write(target, d, binary)
    metrics_v3 = bridge_metrics(bridge['a']['POSITION'], bridge['f'][('body', 4)],
                                [(upper['a']['POSITION'], np.concatenate(list(upper['f'].values())), upper['a']['NORMAL']),
                                 (lower['a']['POSITION'], next(f for k, f in lower['f'].items() if k[0] == 'body'), lower['a']['NORMAL']),
                                 (neck['a']['POSITION'], neck['f'][('body', 4)], neck['a']['NORMAL'])],
                                origin_t, axis_t, LOWER_CUT, upper_cut)
    report = {'slug': slug, 'inputs': {k: str(v) for k, v in inputs.items()}, 'inputSHA256': hashes,
              'headTextureImageSHA256': texture_sha, 'headTextureKind': texture_kind,
              'outputSHA256': digest(target), 'rigMaxDelta': rig_delta, 'halfResolutionDeltaLevels': half_delta,
              'lowerRings': [len(r) for r in lower_rings], 'upperRings': [len(r) for r in upper_rings],
              'bridgeRings': [len(lr[0]), len(ur[0])], 'templateBelowCutTriangles': below,
              'headTrianglesBefore': head_counts, 'rimWeld': weld_report, 'sharedNeck': neck_report,
              'skinRecolour': recolour, 'headAtlas': head_atlas_report, 'neckAtlas': neck_atlas,
              'bridge': {'v3': metrics_v3, 'v2': v2_bridge_metrics(hd, hb, origin_h, axis_h, upper_cut), 'groove': groove},
              'trianglesByRole': triangles_by_role(d, binary), 'sharedBodyShape': spec,
              'status': 'candidate: requires visual/animation review'}
    if tail:
        report['tail'] = tail_report
    if broken_report['faces']:
        report['brokenUV'] = broken_report
    target.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


def human_face_density(d, b):
    """Human face px/cm with the same filter the race head is measured with."""
    names, world, _, _ = rig_frame(d)
    head = world[names.index('Head')][:3, 3]
    values = []
    for name, role, a, f in vspb.primitives(d, b):
        if name not in ('body', 'eyes', 'eyebrows', 'scalp'):
            continue
        mesh = next(m for m in d['meshes'] if m['name'] == name)
        size = spb.material_image(d, b, mesh['primitives'][0]['material'])[1].shape[1::-1]
        sel = face_filter(a['POSITION'], a['NORMAL'], f, head, joint_weight(a, names.index('Head')))
        values.append(texel_density(a['POSITION'], a['TEXCOORD_0'], f[sel], size)[0])
    return float(np.median(np.concatenate(values)))


def v2_bridge_metrics(d, b, origin, axis, upper_cut):
    parts = list(vspb.primitives(d, b))
    bridge = next((a, f) for _, role, a, f in parts if role == 'neck_join')
    neighbours = [(a['POSITION'], f, a['NORMAL']) for name, role, a, f in parts
                  if role in ('race_head', 'shared_neck', 'shared_body') and name in ea.BODY_SURFACES]
    return bridge_metrics(bridge[0]['POSITION'], bridge[1], neighbours, origin, axis, LOWER_CUT, upper_cut)


def triangles_by_role(d, binary):
    counts = Counter()
    for _, role, _, f in vspb.primitives(d, binary):
        counts[role or 'head_accessory'] += len(f)
    return dict(counts)


def assemble(hd, hb, td, tb, lower, upper, bridge, neck, spec, head_payload, skin_payload, wardrobe_payload,
             neck_payload, template_mat, wardrobe_mat, tail=None):
    """Fresh document: v2 nodes, skin and mesh order; new materials/images."""
    d = {'asset': copy.deepcopy(hd['asset']), 'scene': hd.get('scene', 0), 'scenes': copy.deepcopy(hd['scenes']),
         'nodes': copy.deepcopy(hd['nodes']), 'buffers': [{'byteLength': 0}], 'bufferViews': [], 'accessors': []}
    d['asset']['generator'] = 'Eloria rebase_race_body.py'
    d['asset']['extras']['sharedBodyShape'] = spec
    # The Ssarathi waistband repair belonged to the old Luminous trousers.
    d['asset']['extras'].pop('waistSeamRepair', None)
    binary = bytearray()
    skin = copy.deepcopy(hd['skins'][0])
    skin['inverseBindMatrices'] = copy_accessor(d, binary, hd, hb, hd['skins'][0]['inverseBindMatrices'])
    d['skins'] = [skin]
    human = td['materials']
    headwear = copy.deepcopy(next(m for m in hd['materials'] if m.get('name') == 'Headwear'))
    d['materials'] = [
        headwear,
        {'name': 'Race head', 'doubleSided': True, 'emissiveFactor': [0, 0, 0],
         'pbrMetallicRoughness': {'baseColorTexture': {'index': 0}, 'metallicFactor': 0, 'roughnessFactor': .8}},
        {'name': 'Race body skin', 'doubleSided': human[template_mat].get('doubleSided', True), 'emissiveFactor': [0, 0, 0],
         'pbrMetallicRoughness': {'baseColorTexture': {'index': 1}, 'metallicFactor': 0, 'roughnessFactor': .85}},
        copy.deepcopy(human[wardrobe_mat]),
        {'name': BRIDGE_MATERIAL, 'doubleSided': True, 'emissiveFactor': [0, 0, 0],
         'pbrMetallicRoughness': {'baseColorTexture': {'index': 3}, 'metallicFactor': 0, 'roughnessFactor': .8}}]
    d['materials'][3]['pbrMetallicRoughness']['baseColorTexture'] = {'index': 2}
    d['materials'][3]['pbrMetallicRoughness']['metallicFactor'] = 0
    # Runtime face_appearance.gdshader always repeats; these are cosmetic.
    d['samplers'] = [{'magFilter': 9729, 'minFilter': 9987, 'wrapS': 33071, 'wrapT': 33071},
                     {'magFilter': 9729, 'minFilter': 9987},
                     {'wrapS': 10497, 'wrapT': 33071, 'magFilter': 9729, 'minFilter': 9987}]
    d['images'] = [{'mimeType': 'image/jpeg', 'bufferView': spb.append_view(d, binary, payload)}
                   for payload in (head_payload, skin_payload, wardrobe_payload, neck_payload)]
    d['textures'] = [{'source': 0, 'sampler': 0}, {'source': 1, 'sampler': 1}, {'source': 2}, {'source': 3, 'sampler': 2}]
    if tail:
        # The tail keeps its v2 material (named Material_1) and image bytes.
        source = next(p for m in hd['meshes'] for p in m['primitives'] if p.get('extras', {}).get('sourceRole') == 'race_tail')
        material = copy.deepcopy(hd['materials'][source['material']])
        texture = hd['textures'][material['pbrMetallicRoughness']['baseColorTexture']['index']]
        material['pbrMetallicRoughness']['baseColorTexture'] = {'index': len(d['textures'])}
        d['images'].append({'mimeType': hd['images'][texture['source']]['mimeType'],
                            'bufferView': spb.append_view(d, binary, spb.image_bytes(hd, hb, texture['source']))})
        entry = {'source': len(d['images'])-1}
        if 'sampler' in texture:
            d['samplers'].append(copy.deepcopy(hd['samplers'][texture['sampler']])); entry['sampler'] = len(d['samplers'])-1
        d['textures'].append(entry)
        d['materials'].append(material)
        if material.get('extensions'):
            d['extensionsUsed'] = sorted(material['extensions'])
        tail = {'a': tail['a'], 'role': 'race_tail', 'f': {('body', len(d['materials'])-1): tail['f'][('body', 'tail')]}}
    meshes = {}
    body = {'a': lower['a'], 'role': 'shared_body',
            'f': {(name, 2 if name == 'body' else 3): f for (name, _), f in lower['f'].items()}}
    head = {'a': upper['a'], 'role': 'race_head', 'f': {(name, 1): f for (name, _), f in upper['f'].items()}}
    body_only = {'a': body['a'], 'role': 'shared_body', 'f': {k: f for k, f in body['f'].items() if k[0] == 'body'}}
    write_group_v3(d, binary, body_only, meshes)
    write_group_v3(d, binary, {'a': head['a'], 'role': 'race_head', 'f': {k: f for k, f in head['f'].items() if k[0] == 'body'}}, meshes)
    write_group_v3(d, binary, bridge, meshes)
    write_group_v3(d, binary, neck, meshes)
    if tail:
        write_group_v3(d, binary, tail, meshes)
    write_group_v3(d, binary, {'a': body['a'], 'role': 'shared_body', 'f': {k: f for k, f in body['f'].items() if k[0] != 'body'}}, meshes)
    write_group_v3(d, binary, {'a': head['a'], 'role': 'race_head', 'f': {k: f for k, f in head['f'].items() if k[0] != 'body'}}, meshes)
    for name in ('wardrobe_head_band', 'wardrobe_head_cap'):
        node = next(n for n in hd['nodes'] if n.get('name') == name)
        prims = []
        for p in hd['meshes'][node['mesh']]['primitives']:
            q = copy.deepcopy(p)
            q['attributes'] = {k: copy_accessor(d, binary, hd, hb, v) for k, v in p['attributes'].items()}
            q['indices'] = copy_accessor(d, binary, hd, hb, p['indices'])
            q['material'] = 0
            prims.append(q)
        meshes[name] = prims
    d['meshes'] = []
    for m in hd['meshes']:
        if m['name'] not in meshes:
            raise ValueError(f'no primitives for {m["name"]}')
        d['meshes'].append({'name': m['name'], 'primitives': meshes.pop(m['name'])})
    if meshes:
        raise ValueError(f'unplaced meshes {list(meshes)}')
    return d, binary



# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------

def find_head(root, slug, sha, candidates=None, explicit=None):
    """The v2 head source named by the candidate's headSourceSHA256."""
    options = [explicit] if explicit else []
    options += [root/'godot-client/assets/actors/native/races'/f'{slug}.glb']
    if candidates:
        options += [Path(candidates)/'pre-install'/f'{slug}.glb', Path(candidates).parent/'pre-install'/f'{slug}.glb']
    for path in options:
        if path and Path(path).exists() and digest(path) == sha:
            return Path(path)
    raise FileNotFoundError(f'no head source with sha256 {sha}; pass --head')


def ring_copies(parts, roles, origin, axis, height):
    """Max normal / dense-weight spread among coincident copies on one plane."""
    pp, nn, ww = [], [], []
    for _, role, a, f in parts:
        if role not in roles:
            continue
        used = np.unique(f)
        rows = used[np.abs((a['POSITION'][used].astype(float)-origin)@axis-height) < 2e-6]
        if not len(rows):
            continue
        pp.append(a['POSITION'][rows].astype(float)); nn.append(a['NORMAL'][rows].astype(float))
        ww.append(spb.dense_weights({'POSITION': a['POSITION'][rows], 'JOINTS_0': a['JOINTS_0'][rows],
                                     'WEIGHTS_0': a['WEIGHTS_0'][rows]}))
    p, n, w = np.concatenate(pp), np.concatenate(nn), np.concatenate(ww)
    labels = weld(p)
    first = np.zeros(labels.max()+1, int); first[labels[::-1]] = np.arange(len(labels))[::-1]
    sizes = np.bincount(labels)
    return {'copies': int(len(p)), 'positions': int(len(sizes)), 'shared': int((sizes > 1).sum()),
            'maxNormalSpread': float(np.linalg.norm(n-n[first[labels]], axis=1).max()),
            'maxWeightL1Spread': float(np.abs(w-w[first[labels]]).sum(1).max())}


def small_components(parts, origin, axis):
    """Sizes of sub-20-triangle components wholly below the lower cut."""
    p, faces, off = [], [], 0
    for name, role, a, f in parts:
        if name not in ea.BODY_SURFACES or role in ('race_tail', 'neck_join'):
            continue
        travel = (a['POSITION'].astype(float)-origin)@axis
        p.append(a['POSITION'].astype(float)); faces.append(f[(travel[f] < LOWER_CUT-1e-6).all(1)]+off)
        off += len(a['POSITION'])
    size = np.bincount(face_components(np.concatenate(p), np.concatenate(faces)))
    return sorted(int(x) for x in size[size < 20])


def front_projection(path, mask):
    """Orthographic front view of a GLB's race-head surfaces in the
    face_regions.json canvas (900 x 600, 3000 px/m): head-atlas colour, mask
    colour and depth per pixel (front-most surface; -inf where none)."""
    regions = json.loads(Path(__file__).with_name('face_regions.json').read_text())
    proj = regions['projection']
    d, b = ea.read_glb(Path(path))
    width, height = 900, 600
    colour, masked = np.zeros((height, width, 3)), np.zeros((height, width, 3))
    depth = np.full((height, width), -np.inf)
    mask = np.asarray(mask, float)/255
    for name, role, a, f in vspb.primitives(d, b):
        if role != 'race_head':
            continue
        prim = next(q for q in next(m for m in d['meshes'] if m['name'] == name)['primitives']
                    if q.get('extras', {}).get('sourceRole') == 'race_head')
        image = decode(spb.image_bytes(d, b, d['textures'][d['materials'][prim['material']]['pbrMetallicRoughness']
                                                          ['baseColorTexture']['index']]['source']))
        p, uv = a['POSITION'].astype(float), a['TEXCOORD_0'].astype(float)
        f = f[(p[f][..., 2].max(1) > 0) & (p[f][..., 1].max(1) > 1.5)]
        xy = np.stack([(p[:, 0]-proj['xMin'])*proj['pixelsPerMetre']/width,
                       (proj['yMax']-p[:, 1])*proj['pixelsPerMetre']/height], 1)
        face, y, x, bary = raster(xy, f, (width, height))
        z = np.einsum('ni,ni->n', bary, p[f[face]][..., 2])
        t = np.einsum('ni,nic->nc', bary, uv[f[face]])
        order = np.argsort(z)
        y, x, z, t = y[order], x[order], z[order], t[order]
        front = z > depth[y, x]
        colour[y[front], x[front]] = spb.sample_image(np.rint(image*255), t[front]); depth[y[front], x[front]] = z[front]
        texel = np.floor((t[front] % 1)*np.array(mask.shape[1::-1])).astype(int)
        masked[y[front], x[front]] = mask[texel[:, 1], texel[:, 0]]
    return colour, masked, depth


def painted_feature_cover(path, slug, mask):
    """V14: the mask covers what is painted. Brows (bodies with face_regions
    brow polygons): on each side the largest stroke 25 levels darker than its
    sigma-12 surround, in a +-2 x +-.8 cm window round the BROWS landmark and
    outside the eye region (mask R, grown 14 px), must carry B > .5 on half its
    texels; a stroke under BROW_STROKE_MIN px is too faint to judge. Irises
    (IRIS_COLOUR races): the painted iris colour in a +-1.6 x +-1.2 cm window
    round each iris landmark must carry R >= .8 on IRIS_COVER of its texels."""
    from scipy.ndimage import label
    regions = json.loads(Path(__file__).with_name('face_regions.json').read_text())
    region, proj = regions['models'][slug], regions['projection']
    colour, masked, depth = front_projection(path, mask)
    valid = np.isfinite(depth)
    lum = colour@LUMA*255
    X = lambda x: int(round((x-proj['xMin'])*proj['pixelsPerMetre']))
    Y = lambda y: int(round((proj['yMax']-y)*proj['pixelsPerMetre']))
    checks, report = {}, {}
    if 'brows' in region and slug in BROWS:
        blur = gaussian_filter(np.where(valid, lum, 0), 12)/np.maximum(gaussian_filter(valid.astype(float), 12), 1e-6)
        eye = binary_dilation(masked[..., 0] > .05, iterations=14)
        stroke = (lum < blur-25) & valid & ~eye
        bx, by = BROWS[slug]
        for sign in (-1, 1):
            window = np.zeros_like(stroke)
            window[Y(by+.008):Y(by-.008), X(sign*bx-.02):X(sign*bx+.02)] = True
            labels, count = label(stroke & window)
            size = np.bincount(labels.ravel())[1:] if count else np.zeros(0, int)
            if not count or size.max() < BROW_STROKE_MIN:
                report[f'browStroke{sign:+d}'] = {'texels': int(size.max(initial=0)), 'faint': True}
                continue
            big = labels == np.argmax(size)+1
            cover = float((masked[big][:, 2] > .5).mean())
            report[f'browStroke{sign:+d}'] = {'texels': int(big.sum()), 'coverB05': cover}
            checks[f'browStroke{sign:+d}'] = cover >= .5
    rule = next((v for k, v in IRIS_COLOUR.items() if slug.startswith(k)), None)
    if rule:
        rgb = colour*255
        painted = ((rgb[..., 0] > rgb[..., 1]+rule['redOverGreen']) & (rgb[..., 0] > rgb[..., 2]+rule['redOverBlue'])
                   & valid)
        for i, (x, y) in enumerate(IRISES[slug]):
            window = np.zeros_like(painted)
            window[Y(y)-36:Y(y)+36, X(x)-48:X(x)+48] = True
            sel = painted & window
            cover = float((masked[sel][:, 0] >= .8).mean()) if sel.any() else 0.
            report[f'irisColour{i}'] = {'texels': int(sel.sum()), 'coverR08': cover}
            checks[f'irisColour{i}'] = cover >= IRIS_COVER
    return checks, report


def eye_mask_landmarks(path, slug, mask=None, painted=False):
    """Decision 11: a face mask at the iris and brow landmarks of
    test_face_texture_mapping.py. Without `mask` the candidate's mask is baked
    as install bakes it. Returns {check: passed} and the sampled values."""
    import trimesh
    info = {}
    if mask is None:
        from build_face_masks import bake
        regions = json.loads((Path(__file__).with_name('face_regions.json')).read_text())
        region = copy.deepcopy(regions['models'][slug]); region.pop('browStrokes', None)
        mask, info = bake(Path(path), region, regions['projection'])
    d, b = g.read(path)
    vertices, uvs, faces, off = [], [], [], 0
    for m in d['meshes']:
        for p in m['primitives']:
            if p.get('extras', {}).get('sourceRole') != 'race_head':
                continue
            v = g.accessor(d, b, p['attributes']['POSITION'])
            vertices.append(v); uvs.append(g.accessor(d, b, p['attributes']['TEXCOORD_0']))
            faces.append(g.accessor(d, b, p['indices']).astype(int).reshape(-1, 3)+off); off += len(v)
    mesh = trimesh.Trimesh(np.concatenate(vertices), np.concatenate(faces), process=False)
    uv = np.concatenate(uvs)

    def at(x, y):
        pts, _, tri = mesh.ray.intersects_location([[x, y, 1]], [[0, 0, -1]], multiple_hits=False)
        if not len(pts):
            return None
        bary = trimesh.triangles.points_to_barycentric(mesh.triangles[tri], pts)[0]
        xy = np.floor(((bary@uv[mesh.faces[tri[0]]]) % 1)*np.array(mask.shape[:2][::-1])).astype(int)
        return mask[xy[1], xy[0]]/255.
    report = {'maskSize': list(mask.shape[:2]), 'pixelsPerChannel': info.get('pixelsPerChannel'), 'irises': []}
    if painted:
        cover, cover_report = painted_feature_cover(path, slug, mask)
        report['painted'] = cover_report
    checks = {}
    for i, (x, y) in enumerate(IRISES[slug]):
        values = [v for v in (at(x+dx, y+dy) for dx in (-.001, 0, .001) for dy in (-.001, 0, .001)) if v is not None]
        r, gr = (float(max(v[0] for v in values)), float(max(v[1] for v in values))) if values else (0., 0.)
        report['irises'].append({'at': [x, y], 'R': r, 'G': gr}); checks[f'iris{i}'] = r >= .8 and gr > .15
    if slug in BROWS:
        brow = BROWS[slug]
        for sign in (-1, 1):
            values = np.array([v[2] for v in (at(sign*brow[0]+dx, brow[1]+dy) for dx in np.linspace(-.012, .012, 15)
                                              for dy in np.linspace(-.004, .004, 9)) if v is not None])
            report[f'brow{sign:+d}'] = {'maxB': float(values.max(initial=0)), 'over05': int((values > .05).sum())}
            checks[f'brow{sign:+d}'] = bool(values.max(initial=0) > .1 and (values > .05).sum() > 1)
        centre = at(0, brow[1])
        report['browGapB'] = float(centre[2]) if centre is not None else None
        checks['browGap'] = centre is not None and centre[2] < .02
    clean = [at(x, y) for x, y in [(0, 1.68), (0, 1.63), (-.06, 1.595), (.06, 1.595)]]
    report['skinRG'] = [float(v[:2].max()) if v is not None else None for v in clean]
    for i, v in enumerate(clean):
        checks[f'skin{i}'] = v is not None and v[:2].max() < .02
    if painted:
        checks.update(cover)
    return {k: bool(v) for k, v in checks.items()}, report


def shipped_mask(head, slug):
    """The face mask that ships with a v2 head: beside a pre-install backup,
    else the tree's (verify before install)."""
    head = Path(head)
    for path in (head.parent/f'{slug}.png', head.parents[1]/'face_masks'/f'{slug}.png'):
        if path.exists():
            return np.asarray(Image.open(path).convert('RGB'))
    return None


def headwear_crossings(root, slug, candidate, head):
    """Decision 13 report: body edges crossing each socketed race headwear piece."""
    import trimesh
    from trimesh.ray.ray_triangle import RayMeshIntersector
    client = root/'godot-client'
    equipment = json.loads((client/'data/actors/equipment.json').read_text(encoding='utf-8'))

    def edges(path):
        d, b = ea.read_glb(path)
        a, bb = [], []
        for _, role, attrs, f in vspb.primitives(d, b):
            if role not in ('shared_body', 'shared_neck', 'neck_join'):
                continue
            p = attrs['POSITION'].astype(float)
            e = np.unique(np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), 1), axis=0)
            keep = (np.maximum(p[e[:, 0], 1], p[e[:, 1], 1]) > 1.25) & (np.linalg.norm(p[e[:, 1]]-p[e[:, 0]], axis=1) > 1e-7)
            a.append(p[e[keep, 0]]); bb.append(p[e[keep, 1]])
        names, world, _, _ = rig_frame(d)
        return np.concatenate(a), np.concatenate(bb), world[names.index('Head')][:3, 3]

    def scene(path):
        d, b = ea.read_glb(path)
        world = ea.global_matrices(d)
        tris = []
        for i, node in enumerate(d['nodes']):
            if 'mesh' not in node:
                continue
            m = np.array(world[i])
            for p in d['meshes'][node['mesh']]['primitives']:
                v = ea.accessor_array(d, b, p['attributes']['POSITION']).astype(float)@m[:3, :3].T+m[:3, 3]
                tris.append(v[ea.accessor_array(d, b, p['indices']).astype(int).reshape(-1, 3)])
        return np.concatenate(tris)

    def crossings(rmi, a, b):
        d = b-a; length = np.linalg.norm(d, axis=1); d /= length[:, None]
        loc, ray, _ = first_hits(rmi, a, d)
        return int((np.linalg.norm(loc-a[ray], axis=1) < length[ray]-1e-7).sum())
    a2, b2, _ = edges(head)
    a3, b3, head_joint = edges(candidate)
    rows = []
    for key in sorted((k for k in equipment['models'] if k.startswith('3:')), key=lambda k: int(k[2:])):
        variant = equipment['models'][key].get('variants', {}).get(f'canonical_{slug}')
        if not variant:
            continue
        tris = scene(client/variant['scene'].removeprefix('res://'))+head_joint+np.array(variant['socket']['offset'])
        row = {'piece': key, 'name': equipment['models'][key].get('name'), 'v2': 0, 'v3': 0}
        if tris[..., 1].min() <= 1.50:
            rmi = RayMeshIntersector(trimesh.Trimesh(tris.reshape(-1, 3), np.arange(tris.size//3).reshape(-1, 3), process=False))
            row.update(v2=crossings(rmi, a2, b2), v3=crossings(rmi, a3, b3))
        rows.append(row)
    worse = sorted((r for r in rows if r['v3'] > r['v2']), key=lambda r: r['v2']-r['v3'])
    return {'pieces': len(rows), 'regressions': len(worse),
            'totals': {'v2': sum(r['v2'] for r in rows), 'v3': sum(r['v3'] for r in rows)},
            'cleanOnV2NowCrossing': [r['piece'] for r in worse if r['v2'] == 0], 'regressed': worse,
            'starterHelmets': [r for r in rows if r['piece'] in STARTER_HELMETS],
            'method': 'body edges (shared_body/shared_neck/neck_join, y > 1.25) crossing the piece placed at Head + socket '
                      'offset, rest pose; the Walk back view (--clip Walk --time 0.3 --angle back) shows shirt-through-hood '
                      'clipping this rest-pose count misses (P5 refit)'}


def hidden_body(d, b, origin, axis):
    """V7 report: outside-in hidden triangles over every body surface, all of
    them occluders (the human-map method, 60 directions), per surface."""
    parts = [(name, a, f) for name, _, a, f in vspb.primitives(d, b) if name in ea.BODY_SURFACES]
    p, n, faces, tags, below, off = [], [], [], [], [], 0
    for name, a, f in parts:
        p.append(a['POSITION'].astype(float)); n.append(a['NORMAL'].astype(float)); faces.append(f+off)
        tags += [name]*len(f); off += len(a['POSITION'])
        below.append(((a['POSITION'].astype(float)-origin)@axis < LOWER_CUT-1e-6)[f].all(1))
    p, n, faces, tags, below = np.concatenate(p), np.concatenate(n), np.concatenate(faces), np.array(tags), np.concatenate(below)
    seen, _ = visibility(p, n, faces, np.arange(len(faces)))
    hidden = ~seen
    return {'triangles': int(len(faces)), 'hidden': int(hidden.sum()), 'belowCutHidden': int((hidden & below).sum()),
            'bySurface': {s: int((hidden & (tags == s)).sum()) for s in ea.BODY_SURFACES if (tags == s).any()},
            'belowCutBySurface': {s: int((hidden & below & (tags == s)).sum()) for s in ea.BODY_SURFACES if (tags == s).any()},
            'directions': DIRECTIONS}


def tail_checks(parts, tail, v2_tail, spec, names, slug):
    """V18: the carried tail. UVs are the v2 bytes; every root-ring vertex
    lies at least half TAIL_DEPTH inside the Human surface; the tail faces
    outside it are one piece (nothing pokes through the seat elsewhere); with
    a feather, no free-tail vertex carries thigh weight."""
    if len(tail) != 1 or len(v2_tail) != 1:
        return False, {'tailPrimitives': len(tail), 'v2TailPrimitives': len(v2_tail)}
    (a, f), (a2, f2) = tail[0], v2_tail[0]
    values = {'triangles': int(len(f)), 'v2Triangles': int(len(f2)), 'fragmentTriangles': spec['tail']['fragmentTriangles']}
    uv_ok = not (vspb.signatures(a, f, ('TEXCOORD_0',))-vspb.signatures(a2, f2, ('TEXCOORD_0',)))
    surface = np.concatenate([q['POSITION'].astype(float)[ff] for name, role, q, ff in parts
                              if role in ('shared_body', 'shared_neck') and name in ea.BODY_SURFACES])
    p = a['POSITION'].astype(float)
    loops = open_loops(p, f)
    depth, _ = surface_depth(p[loops[0]], surface)
    used = np.unique(f)
    inside = np.zeros(len(p), bool)
    near = used[p[used, 0] < .45]
    inside[near] = winding(p[near], surface) > .5
    outside = f[~inside[f].all(1)]
    pieces = np.bincount(face_components(p, outside)) if len(outside) else np.zeros(0, int)
    values.update(uvBytesFromV2=uv_ok, rootLoopVertices=int(len(loops[0])),
                  rootDepthM={'min': float(depth.min()), 'median': float(np.median(depth))},
                  otherOpenLoops=[int(len(x)) for x in loops[1:]], insideVertices=int(inside[used].sum()),
                  outsidePieces=sorted(pieces.tolist(), reverse=True))
    fragments = np.bincount(face_components(p, f))
    values['smallestComponent'] = int(fragments.min())
    ok = (uv_ok and len(f) == len(f2)-spec['tail']['fragmentTriangles'] and depth.min() >= TAIL_DEPTH/2
          and len(pieces) == 1 and fragments.min() >= 20)
    thighs = [names.index('thigh_l'), names.index('thigh_r')]
    share = {k: np.where(np.isin(q['JOINTS_0'].astype(int), [j]), q['WEIGHTS_0'], 0.).sum(1)
             for k, q, j in (('now', a, thighs[0]), ('v2', a2, thighs[0]))}
    values['thighL'] = {'v2Vertices': int((share['v2'][np.unique(f2)] > 0).sum()), 'vertices': int((share['now'][used] > 1e-6).sum()),
                        'v2Max': float(share['v2'][np.unique(f2)].max()), 'max': float(share['now'][used].max())}
    feather = TAIL_FEATHER.get(slug)
    if feather:
        from scipy.sparse.csgraph import dijkstra
        ids = weld(p)
        n = ids.max()+1
        e = np.unique(np.sort(ids[np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])], 1), axis=0)
        rep = np.zeros(n, int); rep[ids] = np.arange(len(p))
        graph = coo_matrix((np.linalg.norm(p[rep[e[:, 0]]]-p[rep[e[:, 1]]], axis=1), (e[:, 0], e[:, 1])), shape=(n, n)).tocsr()
        along = dijkstra(graph, directed=False, indices=np.unique(ids[inside]), min_only=True)[ids]
        free = used[along[used] >= feather]
        thigh = np.where(np.isin(a['JOINTS_0'].astype(int), thighs), a['WEIGHTS_0'], 0.).sum(1)
        values['freeTail'] = {'vertices': int(len(free)), 'maxThighWeight': float(thigh[free].max(initial=0)), 'featherM': feather}
        ok &= len(free) > 0 and thigh[free].max(initial=0) == 0
    return bool(ok), values


def grain_amount(d, b, parts, upper, origin_h, axis_h, upper_cut, neck_image, rows):
    """V17: high-pass (sigma 3) luminance spread of the bridge rows nearest the
    head (the upper half of the bridge, I3) over that of the outer head skin in
    [rim, rim + DETAIL_BAND] (I0, band_visibility faces). A bridge sampled from
    an inner wall carries almost no grain under a stippled head (.13)."""
    body = next(m for m in d['meshes'] if m['name'] == 'body')
    prim = next(q for q in body['primitives'] if q.get('extras', {}).get('sourceRole') == 'race_head')
    head_image = decode(spb.image_bytes(d, b, d['textures'][d['materials'][prim['material']]['pbrMetallicRoughness']
                                                             ['baseColorTexture']['index']]['source']))

    def high_pass(image):
        lum = image@LUMA*255
        return lum-gaussian_filter(lum, 3, mode='nearest')
    visible, _ = band_visibility(upper, origin_h, axis_h, upper_cut)
    head = intact(upper, ('body', 'head'))
    travel = (upper['a']['POSITION'].astype(float)-origin_h)@axis_h
    band = head[visible & (travel[head].min(1) < upper_cut+DETAIL_BAND) & (travel[head].max(1) > upper_cut)]
    size = head_image.shape[1::-1]
    _, y, x, _ = raster(upper['a']['TEXCOORD_0'], band, size)
    head_spread = float(high_pass(head_image)[y, x].std())
    lo, hi = rows
    bridge_spread = float(high_pass(neck_image)[(lo+hi)//2:hi].std())
    return {'headBandSpread': head_spread, 'bridgeUpperSpread': bridge_spread,
            'ratio': bridge_spread/max(head_spread, 1e-6), 'limit': GRAIN_MIN}


def profile_dips(parts, origin_t, axis_t, origin_h, axis_h, upper_cut):
    """V19: how far the bridge's interior vertices lie inside both rims."""
    for _, role, a, f in parts:
        if role == 'neck_join':
            p = a['POSITION'].astype(float)[np.unique(f)]
    lower = np.abs((p-origin_t)@axis_t-LOWER_CUT) < 3e-6
    upper = np.abs((p-origin_h)@axis_h-upper_cut) < 3e-6
    dip, theta = bridge_dips(p[~lower & ~upper], p[lower], p[upper], origin_t, axis_t)
    return {'maxDipM': float(dip.max()), 'atDegrees': float(np.degrees(theta[dip.argmax()])),
            'over1mm': int((dip > .001).sum()), 'limit': GROOVE_LIMIT}


def verify(root, slug, candidate, out, head=None, candidates=None, reports=True):
    root, candidate = Path(root).resolve(), Path(candidate).resolve()
    sex = slug.rsplit('_', 1)[1]
    races = root/'godot-client/assets/actors/native/races'
    template = races/f'luminous_{sex}.glb'
    d, b = ea.read_glb(candidate)
    spec = d['asset']['extras']['sharedBodyShape']
    head = find_head(root, slug, spec['headSourceSHA256'], candidates or candidate.parent.parent, head)
    td, tb = ea.read_glb(template); hd, hb = ea.read_glb(head)
    result = {'candidate': str(candidate), 'candidateSHA256': digest(candidate), 'template': str(template),
              'head': str(head), 'gates': {}, 'reports': {}}
    gates = result['gates']

    def gate(name, ok, **values):
        gates[name] = {'pass': bool(ok), **values}
    names, world, origin, axis = rig_frame(d)
    names_t, world_t, origin_t, axis_t = rig_frame(td)
    names_h, world_h, origin_h, axis_h = rig_frame(hd)
    upper_cut = spec['upperCutM']
    ibm = (ea.accessor_array(d, b, d['skins'][0]['inverseBindMatrices']).tobytes()
           == ea.accessor_array(hd, hb, hd['skins'][0]['inverseBindMatrices']).tobytes())
    delta = float(np.abs(world-world_t).max())
    gate('V1_skeleton', names == names_t and len(names) == 77 and ibm and delta <= 1e-5,
         ibmBytesEqualHead=ibm, maxWorldDeltaFromTemplate=delta)
    parts = list(vspb.primitives(d, b))
    template_parts = list(vspb.primitives(td, tb))
    head_parts = list(vspb.primitives(hd, hb))
    tail = [(a, f) for _, role, a, f in parts if role == 'race_tail']
    v2_tail = [(a, f) for _, role, a, f in head_parts if role == 'race_tail']

    def below(prims, fields, exclude=()):
        found, count = Counter(), 0
        for name, role, a, f in prims:
            if name not in ea.BODY_SURFACES or role in ('race_tail', 'neck_join')+tuple(exclude):
                continue
            travel = (a['POSITION'].astype(float)-origin_t)@axis_t
            sel = (travel[f] < LOWER_CUT-1e-6).all(1)
            found.update(vspb.signatures(a, f[sel], fields)); count += int(sel.sum())
        return found, count
    geo, n_geo = below(parts, vspb.GEOMETRY_FIELDS)
    geo_t, n_t = below(template_parts, vspb.GEOMETRY_FIELDS)
    uv, n_uv = below(parts, vspb.FIELDS, exclude=('shared_neck',))
    uv_t, _ = below(template_parts, vspb.FIELDS)
    _, n_neck = below([q for q in parts if q[1] == 'shared_neck'], vspb.GEOMETRY_FIELDS)
    human_joints = sorted({d['accessors'][p['attributes']['JOINTS_0']]['componentType']
                           for m in d['meshes'] for p in m['primitives']
                           if p.get('extras', {}).get('sourceRole') in ('shared_body', 'shared_neck')})
    gate('V2_below_cut_equality', geo == geo_t and not (uv-uv_t) and n_uv+n_neck == n_t and human_joints == [5121],
         triangles=n_geo, templateTriangles=n_t, uvUnchangedTriangles=n_uv, sharedNeckBelowCut=n_neck,
         humanJointComponentTypes=human_joints)
    # V3: head bytes are a sub-multiset of the v2 head; rim rows exempt from NORMAL.
    head_now, head_v2, normal_now, normal_v2 = Counter(), Counter(), Counter(), Counter()
    fields = ('POSITION', 'JOINTS_0', 'WEIGHTS_0')
    for prims, sig, nsig in ((parts, head_now, normal_now), (head_parts, head_v2, normal_v2)):
        for name, role, a, f in prims:
            if role != 'race_head':
                continue
            sig.update(vspb.signatures(a, f, fields))
            rim = (np.abs((a['POSITION'].astype(float)-origin_h)@axis_h-upper_cut) < RIM_BAND)[f].any(1)
            nsig.update(vspb.signatures(a, f[~rim], fields+('NORMAL',)))
    cleanup = spec['cleanup']
    removed = (cleanup['fragmentTriangles']+cleanup['innerShellRemoved']
               + sum(cleanup.get('buried', {}).get(k, 0) for k in ('removed', 'looseRemoved')))
    accessories = []
    for name in ('wardrobe_head_band', 'wardrobe_head_cap'):
        mine = next(m for m in d['meshes'] if m['name'] == name)['primitives']
        theirs = next(m for m in hd['meshes'] if m['name'] == name)['primitives']
        accessories.append(len(mine) == len(theirs) and all(
            ea.accessor_array(d, b, p['attributes'][k]).tobytes() == ea.accessor_array(hd, hb, q['attributes'][k]).tobytes()
            for p, q in zip(mine, theirs) for k in q['attributes']) and all(
            ea.accessor_array(d, b, p['indices']).tobytes() == ea.accessor_array(hd, hb, q['indices']).tobytes()
            for p, q in zip(mine, theirs)))
    gate('V3_head_preservation', not (head_now-head_v2) and sum((head_v2-head_now).values()) == removed
         and not (normal_now-normal_v2) and all(accessories),
         headTriangles=sum(head_now.values()), v2HeadTriangles=sum(head_v2.values()), removed=removed,
         bandCapByteEqual=accessories)
    edges, attrs = vspb.neck_join_checks(parts)
    gate('V4_neck_join', edges['geometricEdges'] > 50 and edges['unmatchedEdges'] == 0 and attrs['unmatchedCopies'] == 0
         and attrs['boundaryCopies'] > 30 and attrs['maxPositionDeltaM'] < 1e-6 and attrs['maxNormalDelta'] < 2e-6
         and attrs['maxWeightL1Delta'] < 2e-6, **edges, **attrs)
    rings = {'lower': ring_copies(parts, ('shared_body', 'shared_neck', 'neck_join'), origin_t, axis_t, LOWER_CUT),
             'upper': ring_copies(parts, ('race_head', 'neck_join'), origin_h, axis_h, upper_cut)}
    gate('V5_rim_weld', all(r['maxNormalSpread'] <= 2e-6 and r['maxWeightL1Spread'] <= 2e-6 for r in rings.values()), **rings)
    # V6: fragments over the welded head union plus the bridge.
    hp, hf, off = [], [], 0
    for _, role, a, f in parts:
        if role in ('race_head', 'neck_join'):
            hp.append(a['POSITION'].astype(float)); hf.append(f+off); off += len(a['POSITION'])
    size = np.bincount(face_components(np.concatenate(hp), np.concatenate(hf)))
    small, small_t = small_components(parts, origin_t, axis_t), small_components(template_parts, origin_t, axis_t)
    gate('V6_fragments', not (size < 20).any() and small == small_t, headBridgeComponents=size.tolist(),
         belowCutSmallComponents=small, templateBelowCutSmallComponents=small_t)
    # V7: the head inner shell, recomputed on the candidate.
    # A face counts as hidden when it fails the 60-direction centroid test
    # and the dense 4-point lattice + Fibonacci test (HIDDEN_RULE): the first
    # alone also lists faces that show through a crease or a lip slit.
    upper = block_roles(d, b, {'race_head'})
    keys = list(upper['f']); faces = np.concatenate([upper['f'][k] for k in keys])
    tag = np.concatenate([[k[0]]*len(upper['f'][k]) for k in keys])
    hidden60, robust = robust_hidden(upper['a']['POSITION'].astype(float), upper['a']['NORMAL'].astype(float), faces, tag)
    hidden, fraction = int(robust.sum()), float(robust.mean())
    whole, whole_t = hidden_body(d, b, origin_t, axis_t), hidden_body(td, tb, origin_t, axis_t)
    gate('V7_inner_shell', fraction <= .02 and cleanup['hiddenHeadFraction'] <= .02, hiddenHeadTriangles=hidden,
         hiddenHeadFraction=fraction, recordedFraction=cleanup['hiddenHeadFraction'],
         hiddenHeadTriangles60=int(hidden60.sum()), hiddenHeadFraction60=float(hidden60.mean()), rule=HIDDEN_RULE,
         wholeBody={'candidate': whole, 'template': whole_t,
                    'belowCutHiddenEqual': whole['belowCutHidden'] == whole_t['belowCutHidden'],
                    'note': 'report only: below the cut the body is the template byte for byte (P0-owned)'})
    rig, rig_t = ea.load_rig(candidate), ea.load_rig(template)
    feet, feet_t = ea.foot_anchor(rig), ea.foot_anchor(rig_t)
    gate('V8_feet', {k: v[0] for k, v in feet.items()} == {k: v[0] for k, v in feet_t.items()},
         maxAbsX=max(abs(v[0]) for v in feet.values()), templateMaxAbsX=max(abs(v[0]) for v in feet_t.values()),
         footAnchor=feet, templateFootAnchor=feet_t)
    head_index = names.index('Head')
    head_joint = world[head_index][:3, 3]
    body = next(m for m in d['meshes'] if m['name'] == 'body')
    face_prim = next(p for p in body['primitives'] if p.get('extras', {}).get('sourceRole') == 'race_head')
    size = np.array(spb.material_image(d, b, face_prim['material'])[1].shape[1::-1])
    dens, face_dens = [], []
    for _, role, a, f in parts:
        if role != 'race_head':
            continue
        dens.append(texel_density(a['POSITION'], a['TEXCOORD_0'], f, size)[0])
        sel = face_filter(a['POSITION'], a['NORMAL'], f, head_joint, joint_weight(a, head_index))
        face_dens.append(texel_density(a['POSITION'], a['TEXCOORD_0'], f[sel], size)[0])
    human = human_face_density(td, tb)
    median, face_median = float(np.median(np.concatenate(dens))), float(np.median(np.concatenate(face_dens)))
    gate('V9_face_density', face_median >= human and median >= 12, raceHeadPxPerCm=median, facePxPerCm=face_median,
         humanFacePxPerCm=human, informationFacePxPerCm=spec['headAtlas']['sourceFacePxPerCm'],
         informationPxPerCm=spec['headAtlas']['sourcePxPerCm'])
    tris = sum(len(f) for _, _, _, f in parts)
    verts = sum(d['accessors'][p['attributes']['POSITION']]['count'] for m in d['meshes'] for p in m['primitives'])
    head_tris = sum(len(f) for _, role, _, f in parts if role == 'race_head')
    gate('V10_budget', verts < 40_000 and tris > 18_000 and 7000 < head_tris < 22000,
         vertices=verts, triangles=tris, raceHead=head_tris)
    nodes = Counter(n.get('name') for n in d['nodes'] if 'mesh' in n)
    wardrobe_nodes = ('wardrobe_shirt', 'wardrobe_pants', 'wardrobe_boots')
    required = ('body', 'eyes', 'scalp', *wardrobe_nodes, 'wardrobe_head_band', 'wardrobe_head_cap')
    if not slug.startswith(NO_EYEBROWS):
        required += ('eyebrows',)

    def eyes_image(dd, bb):
        eyes = next(m for m in dd['meshes'] if m['name'] == 'eyes')['primitives'][0]
        texture = dd['materials'][eyes['material']]['pbrMetallicRoughness']['baseColorTexture']['index']
        return spb.image_bytes(dd, bb, dd['textures'][texture]['source'])
    others = [eyes_image(*ea.read_glb(o)) for o in sorted(races.glob('*.glb')) if o.stem != slug]
    body_mat = d['materials'][body['primitives'][0]['material']]
    wardrobe = [next(m for m in d['meshes'] if m['name'] == w)['primitives'][0]['material'] for w in wardrobe_nodes]
    first_cape = min(i for i, n in enumerate(names) if n.startswith('cape_'))
    highest = max(int(ea.accessor_array(d, b, p['attributes']['JOINTS_0']).max()) for m in d['meshes'] for p in m['primitives'])
    bridges = sum(1 for m in d['meshes'] for p in m['primitives'] if d['materials'][p['material']].get('name') == BRIDGE_MATERIAL)
    roles = [p.get('extras', {}).get('sourceRole') for p in body['primitives']]
    structure = {'nodesOnce': all(nodes[r] == 1 for r in required), 'noHair': 'hair' not in nodes,
                 'eyesImageUnique': eyes_image(d, b) not in others and len(others) == 15,
                 'bodyPrim0Textured': 'baseColorTexture' in body_mat['pbrMetallicRoughness']
                 and body_mat.get('emissiveFactor', [0, 0, 0]) == [0, 0, 0],
                 'wardrobeMaterials': all(w != body['primitives'][0]['material']
                                          and d['materials'][w]['pbrMetallicRoughness']['roughnessFactor'] > .5
                                          and 'baseColorTexture' in d['materials'][w]['pbrMetallicRoughness'] for w in wardrobe),
                 'jointsBelowCape': highest < first_cape, 'bridgePrimitives': bridges, 'bodyRoles': roles,
                 'imagesUnnamed': all('name' not in im for im in d['images'])}
    gate('V11_structure', structure['nodesOnce'] and structure['noHair'] and structure['eyesImageUnique']
         and structure['bodyPrim0Textured'] and structure['wardrobeMaterials'] and structure['jointsBelowCape']
         and bridges == 2 and roles == ['shared_body', 'race_head', 'neck_join', 'shared_neck']+(['race_tail'] if tail else [])
         and structure['imagesUnnamed'],
         **structure)
    soles = {}
    for side in ('l', 'r'):
        feet_ids = [names.index('foot_'+side), names.index('ball_'+side)]
        ys = []
        for name, _, a, f in parts:
            if name in ('body', 'wardrobe_boots'):
                share = np.where(np.isin(a['JOINTS_0'].astype(int), feet_ids), a['WEIGHTS_0'], 0.).sum(1)
                ys.extend(a['POSITION'][share > .5, 1].tolist())
        soles[side] = float(min(ys))
    gate('V12_ground', all(abs(v) < .025 for v in soles.values()), weightedSoleMinY=soles)
    # Decision 8: no neck-atlas texel is covered by more than one face.
    corners = np.concatenate([a['TEXCOORD_0'][f].astype(float) for _, role, a, f in parts
                              if role in ('shared_neck', 'neck_join')]).reshape(-1, 2)
    tri = np.arange(len(corners)).reshape(-1, 3)
    strict = coverage(corners, tri, NECK_SIZE, wrap=True, tol=1e-6)[0]
    inclusive = coverage(corners, tri, NECK_SIZE, wrap=True)[0]
    top = max(float(a['TEXCOORD_0'][np.unique(f), 1].max()) for _, role, a, f in parts if role == 'neck_join')
    gate('V13_neck_atlas_injective', (strict > 1).sum() == 0 and top <= 1-2/NECK_SIZE[1],
         overlappingTexels=int((strict > 1).sum()), overlappingTexelsEdgeInclusive=int((inclusive > 1).sum()),
         maxBridgeV=top)
    # Bridge grain (I3 bridge rows): a one-colour-per-column fill scores > 4.
    bridge_prim = next(p for p in body['primitives'] if p.get('extras', {}).get('sourceRole') == 'neck_join')
    neck_image = decode(spb.image_bytes(d, b, d['textures'][d['materials'][bridge_prim['material']]['pbrMetallicRoughness']
                                                             ['baseColorTexture']['index']]['source']))
    v = np.concatenate([a['TEXCOORD_0'][np.unique(f), 1].astype(float) for _, role, a, f in parts if role == 'neck_join'])
    lo, hi = int(np.ceil(v.min()*NECK_SIZE[1]))+2, int(np.floor(v.max()*NECK_SIZE[1]))-2
    grain = streak_ratio(neck_image[lo:hi])
    amount = grain_amount(d, b, parts, upper, origin_h, axis_h, upper_cut, neck_image, (lo, hi))
    gate('V17_bridge_grain', grain < STREAK_LIMIT and amount['ratio'] >= GRAIN_MIN, bridgeStreakRatio=grain, rows=[lo, hi],
         limit=STREAK_LIMIT, grainAmount=amount)
    dips = profile_dips(parts, origin_t, axis_t, origin_h, axis_h, upper_cut)
    gate('V19_bridge_profile', dips['maxDipM'] <= GROOVE_LIMIT, **dips)
    if tail or v2_tail:
        ok, values = tail_checks(parts, tail, v2_tail, spec, names, slug)
        gate('V18_tail', ok, **values)
    # V14: every landmark check the shipped v2 mask passes still passes, and
    # both irises pass (glasswarden_male and the Mycelari carry no brow mask
    # since install drops browStrokes, as the v2 installer did).
    checks, landmarks = eye_mask_landmarks(candidate, slug, painted=True)
    before = shipped_mask(head, slug)
    v2_checks = eye_mask_landmarks(head, slug, before)[0] if before is not None else {}
    gate('V14_eye_mask_landmarks', all(v for k, v in checks.items() if k.startswith(('iris', 'browStroke')))
         and all(checks[k] or not v for k, v in v2_checks.items()),
         checks=checks, v2Checks=v2_checks, **landmarks)
    margins = [float(min((a['TEXCOORD_0'][np.unique(f)].astype(float)*size).min(),
                         (size-a['TEXCOORD_0'][np.unique(f)].astype(float)*size).min()))
               for _, role, a, f in parts if role == 'race_head']
    gate('V15_head_atlas_border', min(margins) >= 4-1e-3, minBorderPx=min(margins))
    gate('V16_lineage', spec['version'] == 3 and spec['templateSHA256'] == digest(template)
         and spec['headSourceSHA256'] == digest(head) and spec['toolSHA256'] == source_digest(__file__),
         templateSHA256=spec['templateSHA256'], headSourceSHA256=spec['headSourceSHA256'],
         toolSHA256=spec['toolSHA256'], builtByThisTool=spec['toolSHA256'] == source_digest(__file__),
         toolHash='sha256 of the tool with CRLF folded to LF (the git blob)')
    if reports:
        built = candidate.with_suffix('.json')
        if built.exists():
            report = json.loads(built.read_text(encoding='utf-8'))
            result['reports'].update({k: report[k] for k in ('bridge', 'skinRecolour', 'headAtlas', 'neckAtlas',
                                                             'sharedNeck', 'rimWeld') if k in report})
        result['reports']['headwear'] = headwear_crossings(root, slug, candidate, head)
    result['pass'] = all(v['pass'] for v in gates.values())
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    (out/f'{slug}.verify.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return result


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------

def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True, text=True).stdout


def remove_json_block(path, key):
    """Delete one '"key": {...},' member as a text edit that keeps CRLF."""
    raw = path.read_bytes()
    eol = b'\r\n' if b'\r\n' in raw else b'\n'
    lines = raw.split(eol)
    start = next(i for i, line in enumerate(lines) if line.strip().startswith(json.dumps(key).encode()+b':'))
    indent = len(lines[start])-len(lines[start].lstrip())
    end = next(i for i in range(start+1, len(lines))
               if lines[i].strip().startswith(b'}') and len(lines[i])-len(lines[i].lstrip()) == indent)
    kept = lines[:start]+lines[end+1:]
    if not lines[end].strip().endswith(b','):
        # The last member: the one before it (if any) loses its comma.
        before = start-1
        if not lines[before].rstrip().endswith(b','):
            if not lines[before].rstrip().endswith(b'{'):
                raise ValueError(f'cannot remove {key}')
        else:
            kept[before] = lines[before].rstrip()[:-1]
    path.write_bytes(eol.join(kept))
    json.loads(path.read_text(encoding='utf-8'))
    return [start+1, end+1]


CUFF_RETIRED_REASON = ("Every derived female race was rebased onto the regenerated Human body "
                       "(eloria-assets/tools/rebase_race_body.py, sharedBodyShape v3) and now carries the Human pants and "
                       "boots below the neck, so no installed body carries this propagation's outputs. The authoring "
                       "record stays as history.")


def retire_propagation(path, day):
    """Once install has removed every derived race from the cuff propagation
    manifest, mark it retired (status, retiredAt, retiredReason) and write the
    empty assets object as {}: a text edit that keeps the file's line endings
    and layout (it is not json.dumps round-trip-stable)."""
    raw = path.read_bytes()
    eol = b'\r\n' if b'\r\n' in raw else b'\n'
    document = json.loads(raw)
    if document['assets'] or document.get('status') == 'retired':
        return None
    text = raw.decode('utf-8')
    newline = eol.decode()
    empty = re.compile(r'"assets": \{\s*\}')
    if len(empty.findall(text)) != 1:
        raise ValueError('cannot find the empty assets object')
    text = empty.sub('"assets": {}', text)
    status = f'  "status": {json.dumps(document["status"])},{newline}'
    if text.count(status) != 1:
        raise ValueError('cannot find the manifest status')
    text = text.replace(status, f'  "status": "retired",{newline}  "retiredAt": {json.dumps(day)},{newline}'
                                f'  "retiredReason": {json.dumps(CUFF_RETIRED_REASON)},{newline}')
    path.write_bytes(text.encode('utf-8'))
    retired = json.loads(path.read_text(encoding='utf-8'))
    if retired['assets'] or retired['status'] != 'retired':
        raise ValueError('cuff manifest not retired')
    return {'status': 'retired', 'retiredAt': day, 'previousStatus': document['status']}


def untracked(root):
    """Every untracked, not-ignored path (files, not collapsed directories)."""
    return sorted(line[3:] for line in git(root, 'status', '--porcelain', '--untracked-files=all').splitlines()
                  if line.startswith('?? '))


def install_targets(root, slugs):
    client = root/'godot-client'; native = client/'assets/actors/native'
    files = {'models': client/'data/actors/models.json', 'catalog': client/'data/actors/native_asset_catalog.json',
             'equipment': client/'data/actors/equipment.json', 'masks': native/'face_masks/manifest.json',
             'cuff': root/'eloria-assets/qa/luminous-female-cuff-derived-propagation.json'}
    return files, list(files.values())+[native/'races'/f'{s}.glb' for s in slugs]+[native/'face_masks'/f'{s}.png' for s in slugs]


def worktree_checks(root, targets, untracked_before):
    """Tracked changes stay within the install targets and the programme files
    (design §8); no untracked file appears that was not there before install."""
    allowed = {t.relative_to(root).as_posix() for t in targets} | PROGRAMME_FILES
    changed = set(git(root, 'diff', '--name-only').split())
    now = untracked(root)
    new = sorted(set(now)-set(untracked_before)-PROGRAMME_FILES)
    preexisting = sorted(p for p in set(now) & set(untracked_before) if p not in PROGRAMME_FILES)
    return {'changedOutsideRebaseFiles': sorted(changed-allowed), 'newUntracked': new,
            'preexistingUntracked': preexisting,
            'preexistingNote': 'untracked before install and not written by it; stage pilot files by explicit path '
                               'so these stay out of the commit'}


def install(root, candidates, slugs):
    import calibrate_skin_palettes
    from build_face_masks import bake
    root, candidates = Path(root).resolve(), Path(candidates).resolve()
    native = root/'godot-client/assets/actors/native'
    files, targets = install_targets(root, slugs)
    dirty = git(root, 'status', '--porcelain', '--', *[t.relative_to(root).as_posix() for t in targets])
    if dirty.strip():
        raise ValueError('install targets are not clean:\n'+dirty)
    untracked_before = untracked(root)
    checks = {}
    for slug in slugs:
        checked = json.loads((candidates/slug/f'{slug}.verify.json').read_text(encoding='utf-8'))
        if not checked['pass'] or checked['candidateSHA256'] != digest(candidates/slug/f'{slug}.glb'):
            raise ValueError(f'{slug}: candidate has no passing verify report')
        checks[slug] = checked
    backup = candidates/'pre-install'; backup.mkdir(parents=True, exist_ok=True)
    for t in targets:
        name = 'face_masks_manifest.json' if t == files['masks'] else t.name
        if not (backup/name).exists():
            shutil.copy2(t, backup/name)
    json_files = {k: v for k, v in files.items() if k != 'cuff'}
    before = {k: json.loads(p.read_text(encoding='utf-8')) for k, p in json_files.items()}
    data = copy.deepcopy(before)
    regions = json.loads(Path(__file__).with_name('face_regions.json').read_text())
    report = {}
    for slug in slugs:
        sex = slug.rsplit('_', 1)[1]
        path = native/'races'/f'{slug}.glb'
        shutil.copyfile(candidates/slug/f'{slug}.glb', path)
        d, b = g.read(path)
        surface = next(i for i, p in enumerate(next(m for m in d['meshes'] if m['name'] == 'body')['primitives'])
                       if p.get('extras', {}).get('sourceRole') == 'race_head')
        if data['models']['models'][slug]['faceAppearance'] != {'sourceSurface': surface,
                                                                'mask': f'res://assets/actors/native/face_masks/{slug}.png'}:
            raise ValueError(f'{slug}: unexpected faceAppearance')
        region = copy.deepcopy(regions['models'][slug]); region.pop('browStrokes', None)
        mask, mask_report = bake(path, region, regions['projection'])
        mask_path = native/'face_masks'/f'{slug}.png'
        Image.fromarray(mask).save(mask_path, optimize=True)
        mask_report['maskSHA256'] = digest(mask_path)
        data['masks'][slug] = mask_report
        rig = ea.load_rig(path)
        for key, measure in (('bodyGirth', ea.body_girth), ('footAnchor', ea.foot_anchor), ('soleDrop', ea.sole_drop)):
            data['equipment'][key][slug] = measure(rig)
        data['equipment']['fitGroups'][slug] = [f'canonical_{slug}', f'canonical_human_{sex}']
        legacy = data['equipment']['fitProfiles']['legacy']
        for key in ('bodyGirth', 'footAnchor'):
            legacy[key][slug] = copy.deepcopy(legacy[key][f'luminous_{sex}'])
        catalog = data['catalog']['races'][slug]
        if 'sourceIntegration' in catalog or catalog['sourceSHA256'] != d['asset']['extras']['sourceSHA256']:
            raise ValueError(f'{slug}: catalog provenance differs from the GLB')
        catalog.update(sha256=digest(path), sharedBodyShape=d['asset']['extras']['sharedBodyShape'],
                       pipeline='eloria-assets/tools/rebase_race_body.py',
                       neckAdaptorTriangles=sum(d['accessors'][p['indices']]['count']//3 for m in d['meshes']
                                                for p in m['primitives'] if p.get('extras', {}).get('sourceRole') == 'neck_join'),
                       triangles=sum(d['accessors'][p['indices']]['count']//3 for m in d['meshes'] for p in m['primitives']),
                       vertices=sum(d['accessors'][p['attributes']['POSITION']]['count'] for m in d['meshes'] for p in m['primitives']))
        tail = sum(d['accessors'][p['indices']]['count']//3 for m in d['meshes'] for p in m['primitives']
                   if p.get('extras', {}).get('sourceRole') == 'race_tail')
        if tail or 'retainedTailTriangles' in catalog:
            catalog['retainedTailTriangles'] = tail
        # The Ssarathi waistband repair belonged to the old Luminous trousers.
        catalog.pop('waistSeamRepair', None)
        data['catalog']['validation']['results'][path.relative_to(root).as_posix()] = {
            'nodes': len(d['nodes']), 'meshes': len(d['meshes']), 'skins': len(d.get('skins', [])),
            'animations': len(d.get('animations', []))}
        report[slug] = {'modelSHA256': digest(path), 'mask': mask_report, 'verifiedCandidateSHA256': checks[slug]['candidateSHA256'],
                        'bodyGirth': data['equipment']['bodyGirth'][slug], 'footAnchor': data['equipment']['footAnchor'][slug],
                        'soleDrop': data['equipment']['soleDrop'][slug]}
    for key in ('catalog', 'equipment', 'masks'):
        files[key].write_text(json.dumps(data[key], indent=2)+'\n')
    # Palettes last: they read the installed GLB and mask. The calibration
    # tool itself unifies a rebased body's references (decision 12), so a
    # later full calibration run reproduces them.
    calibrate_skin_palettes.run(root, slugs=set(slugs))
    models = json.loads(files['models'].read_text(encoding='utf-8'))
    for slug, config in models['models'].items():
        if slug not in slugs and config != before['models']['models'][slug]:
            raise ValueError(f'calibration changed {slug}')
    # orun-male-rear-neck-v1 masks faces of the v2 shared_neck by ordinal and
    # fingerprint; on a rebased body it no longer matches (torso_body_cover.gd
    # then warns and falls back to the generic rule), so the selector goes.
    retired = [slug for slug in slugs if models['models'][slug].pop('torsoBodyCover', None) is not None]
    if retired:
        files['models'].write_text(json.dumps(models, indent=2)+'\n')
        report['retiredTorsoBodyCover'] = retired
    seams = {}
    for slug in slugs:
        palette = models['models'][slug]['skinPalette']
        refs = palette['references']
        roles = palette.get('bodySeams', {}).get('roles', ['shared_body', 'race_head', 'neck_join', 'shared_neck'])
        if (len(refs['body']) != len(roles) or roles[:4] != ['shared_body', 'race_head', 'neck_join', 'shared_neck']
                or any(refs[p] != [refs['body'][1]] for p in ('eyes', 'eyebrows', 'scalp') if p in refs)):
            raise ValueError(f'{slug}: unexpected palette layout')
        lum = [float(srgb_to_linear(np.array(r))@LUMA) for r in refs['body']]
        after = {'shared_body/shared_neck': lum[0]/lum[3], 'shared_neck/neck_join': lum[3]/lum[2],
                 'neck_join/race_head': lum[2]/lum[1]}
        if 'bodySeams' not in palette or any(abs(r-1) > .02 for r in after.values()):
            raise ValueError(f'{slug}: dye seams remain {after}')
        seams[slug] = {**palette['bodySeams'], 'ratiosAfter': after}
    assets = json.loads(files['cuff'].read_text(encoding='utf-8'))['assets']
    for slug in slugs:
        if slug in assets:
            report.setdefault('cuffManifestLinesRemoved', {})[slug] = remove_json_block(files['cuff'], slug)
    # No derived race left: the propagation record is retired, not deleted.
    retired_cuff = retire_propagation(files['cuff'], datetime.date.today().isoformat())
    if retired_cuff:
        report['cuffManifestRetired'] = retired_cuff
    keep = candidates/'install'; keep.mkdir(parents=True, exist_ok=True)
    for path in files.values():
        shutil.copy2(path, keep/path.name)
    text = files['models'].read_text(encoding='utf-8')
    report['untrackedBeforeInstall'] = untracked_before
    report['postInstall'] = {'modelsRoundTrip': json.dumps(json.loads(text), indent=2)+'\n' == text,
                             **worktree_checks(root, targets, untracked_before)}
    report['dyeSeams'] = seams
    (candidates/'installation.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    post = report['postInstall']
    if not post['modelsRoundTrip'] or post['changedOutsideRebaseFiles'] or post['newUntracked']:
        raise ValueError(post)
    return report


def post_import(root, candidates, slugs):
    """After `godot --import`: installed files intact, no new untracked files."""
    root, candidates = Path(root).resolve(), Path(candidates).resolve()
    installation = json.loads((candidates/'installation.json').read_text(encoding='utf-8'))
    files, targets = install_targets(root, slugs)
    rewritten = [p.relative_to(root).as_posix() for p in files.values()
                 if p.read_bytes() != (candidates/'install'/p.name).read_bytes()]
    glbs = {slug: digest(root/'godot-client/assets/actors/native/races'/f'{slug}.glb') == installation[slug]['modelSHA256']
            for slug in slugs}
    text = files['models'].read_text(encoding='utf-8')
    ignored = [line[3:] for line in git(root, 'status', '--porcelain', '--ignored', '--untracked-files=all', '--',
                                        'godot-client/assets/actors/native/races').splitlines()
               if line.startswith('!! ') and any(Path(line[3:]).name.startswith(s+'_') for s in slugs)]
    report = {'rewrittenByImport': rewritten, 'installedGLBsIntact': glbs,
              'modelsRoundTrip': json.dumps(json.loads(text), indent=2)+'\n' == text,
              **worktree_checks(root, targets, installation['untrackedBeforeInstall']),
              'ignoredExtractedTextures': ignored}
    report['pass'] = (not rewritten and all(glbs.values()) and report['modelsRoundTrip']
                      and not report['changedOutsideRebaseFiles'] and not report['newUntracked'])
    (candidates/'post-import.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='command', required=True)
    b = sub.add_parser('build')
    b.add_argument('--root', type=Path, required=True)
    b.add_argument('--slug', required=True)
    b.add_argument('--out', type=Path, required=True)
    b.add_argument('--head', type=Path)
    b.add_argument('--head-texture', type=Path)
    b.add_argument('--template', type=Path)
    b.add_argument('--head-atlas', type=int, help='1024 or 2048; default: 1024, else 2048 when the islands do not fit')
    b.add_argument('--head-density-max', type=float, default=20.)
    b.add_argument('--neck-profile', choices=('smooth', 'linear'), default='smooth')
    b.add_argument('--detail-mix', type=float, default=.2)
    b.add_argument('--skin-target', choices=('face', 'ring'), default='face',
                   help='skin recolour target: the face reference (default) or the pilot neck-ring median')
    v = sub.add_parser('verify')
    v.add_argument('--root', type=Path, required=True)
    v.add_argument('--slug', required=True)
    v.add_argument('--candidate', type=Path, required=True)
    v.add_argument('--out', type=Path, required=True)
    v.add_argument('--head', type=Path)
    v.add_argument('--no-reports', action='store_true')
    for name in ('install', 'post-import'):
        i = sub.add_parser(name)
        i.add_argument('--root', type=Path, required=True)
        i.add_argument('--candidates', type=Path, required=True)
        i.add_argument('--slugs', nargs='+', required=True)
    args = ap.parse_args()
    if args.command == 'build':
        report = build(args.root, args.slug, args.out, args.head, args.head_texture, args.template,
                       args.head_atlas, args.head_density_max, args.neck_profile, args.detail_mix, args.skin_target)
        print(json.dumps({k: report[k] for k in ('outputSHA256', 'trianglesByRole', 'sharedNeck', 'headAtlas')}, indent=2))
    elif args.command == 'verify':
        result = verify(args.root, args.slug, args.candidate, args.out, args.head, reports=not args.no_reports)
        print(json.dumps({k: v['pass'] for k, v in result['gates'].items()}, indent=2))
        raise SystemExit(0 if result['pass'] else 1)
    elif args.command == 'install':
        print(json.dumps(install(args.root, args.candidates, args.slugs), indent=2))
    else:
        report = post_import(args.root, args.candidates, args.slugs)
        print(json.dumps(report, indent=2))
        raise SystemExit(0 if report['pass'] else 1)


if __name__ == '__main__':
    main()

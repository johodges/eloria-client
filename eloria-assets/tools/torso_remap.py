"""Retarget original torso artwork before fitting it to the wearer.

The design has an upright trunk and hanging arms. Infer a source arm frame
from each cuff, map those frames to the rig, and move welded plate islands
whole. The frontal trunk scale seats the design's waist at the pelvis rather
than squeezing its skirt, waist, chest and collar into one short torso span.
Only the joined cloth seams blend between frames. A skinned backing replaces
the default race clothing through TorsoBodyCover in the client.

conform_equipment supplies file/topology/ray helpers only; none of its legacy
seat, repose, sleeve-unsquash or trunk-correction passes run on this path.
"""
from __future__ import annotations

import argparse
import json
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

import equipment_authoring as ea
import conform_equipment as io

# Art-directed collar height, requested for the three reviewed designs.
# Keys name the original input, so isolated QA builds and shipped builds agree.
COLLAR_LIFT = {
    'Eight_legendary_hero_armor_designs__r01_c01.glb': .045,
    'Eight_leather_ranger_torso_designs__r02_c01.glb': .045,
    'Amberwood_Woodland_Armor_Concept_Sheet__r01_c04.glb': .045,
}


def rotation_between(a, b):
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    cross = np.cross(a, b)
    cosine = float(a @ b)
    if np.linalg.norm(cross) < 1e-8:
        return np.eye(3)
    skew = np.array([[0, -cross[2], cross[1]],
                     [cross[2], 0, -cross[0]],
                     [-cross[1], cross[0], 0]])
    return np.eye(3) + skew + skew @ skew / (1 + cosine)


def source_skeleton(points):
    height = np.ptp(points[:, 1])
    top = float(points[:, 1].max())
    middle_x = float((points[:, 0].min() + points[:, 0].max()) / 2)
    result = {}
    for side, sign in [('l', 1.), ('r', -1.)]:
        shoulder = np.array([middle_x + sign * .23 * height,
                             top - .17 * height, -.04 * height])
        distal = points[((points[:, 0] - middle_x) * sign > .28 * height)
                        & (points[:, 1] < top - .35 * height)]
        if len(distal) > 12:
            low = np.percentile(distal[:, 1], 15)
            wrist = np.median(distal[distal[:, 1] <= low], axis=0)
            # The front lip of an oblique cuff reaches lower than its rear.
            # Measure depth over the whole sleeve, not that biased lip.
            wrist[2] = np.percentile(distal[:, 2], [2, 98]).mean()
        else:
            wrist = shoulder + np.array([sign * .14, -.70, .06]) * height
        result[side] = (shoulder, wrist)
    return result


def remap(points, triangles, rig, collar_lift=0.):
    canon, edges, count = io._weld(points, triangles)
    labels = io._components(edges, count)[canon]
    source = source_skeleton(points)
    source_height = np.ptp(points[:, 1])
    source_top = float(points[:, 1].max())
    shoulder_y = source_top - .17 * source_height
    # In these concept sheets the shoulder and waist landmarks are 53% of
    # the drawing height apart. Seat those at the arm root and pelvis;
    # decorations below the belt remain below it instead of shortening the chest.
    waist = rig.origin('pelvis')[1] + .010 * rig.fit_scale
    scale = (rig.origin('upperarm_l')[1] - waist) / (.53 * source_height)
    centre = np.array([0., shoulder_y, -.02 * source_height])
    target = np.array([0., rig.origin('upperarm_l')[1], -.035 * rig.fit_scale])
    trunk = (points - centre) * np.array([scale, scale, .8 * scale]) + target
    out = trunk.copy()
    arm_share = np.zeros((len(points), 2))
    cap_side = np.full(len(points), -1, dtype=int)
    reports = {}
    for col, (side, sign) in enumerate([('l', 1.), ('r', -1.)]):
        root, wrist = source[side]
        target_root = rig.origin('upperarm_' + side)
        target_wrist = rig.origin('hand_' + side)
        source_axis = wrist - root
        target_axis = target_wrist - target_root
        limb_scale = np.linalg.norm(target_axis) / np.linalg.norm(source_axis)
        turn = rotation_between(source_axis, target_axis)
        arm = (points - root) @ turn.T * limb_scale + target_root
        cap = (points - root) * limb_scale + target_root
        caps = tubes = 0
        for label in np.unique(labels):
            own = labels == label
            block = points[own]
            centroid = np.unique(np.round(block, 5), axis=0).mean(axis=0)
            spanning = block[:, 0].min() < -.075 * source_height and block[:, 0].max() > .075 * source_height
            if spanning:
                if np.max(np.abs(block[:, 0])) < .30 * source_height:
                    continue
                # A sewn sleeve can share the coat's mesh.  Blend only that
                # seam, on welded positions, never across independent plates.
                travel = np.clip((block - root) @ source_axis / (source_axis @ source_axis), 0., 1.)
                axis_point = root + travel[:, None] * source_axis
                distance = np.linalg.norm(block - axis_point, axis=1) / source_height
                blend = np.clip((.18 - distance) / .035, 0., 1.)
                blend *= np.clip((block[:, 0] * sign / source_height - .11) / .04, 0., 1.)
                blend *= np.clip((block[:, 1] - wrist[1]) / (.10 * source_height), 0., 1.)
                upper = np.clip((block[:, 1] - shoulder_y + .22 * source_height)
                                / (.10 * source_height), 0., 1.)
                chest_edge = np.clip((block[:, 0] * sign / source_height - .19) / .06, 0., 1.)
                blend *= 1 - upper * (1 - chest_edge)
                blend *= np.clip((source_top - block[:, 1]) / (.20 * source_height), 0., 1.)
                blend = blend * blend * (3 - 2 * blend)
                out[own] += (arm[own] - trunk[own]) * blend[:, None]
                arm_share[own, col] = blend
                continue
            if centroid[0] * sign < 0:
                continue
            if centroid[0] * sign < .17 * source_height:
                continue
            crest = (centroid[1] > shoulder_y - .11 * source_height
                     and block[:, 1].max() > shoulder_y + .02 * source_height)
            if crest:
                out[own] = cap[own]
                cap_side[own] = col
                caps += 1
            elif centroid[0] * sign > .25 * source_height:
                out[own] = arm[own]
                arm_share[own, col] = 1.
                tubes += 1
        reports[side] = {'sourceShoulder': root.tolist(), 'sourceWrist': wrist.tolist(),
                         'scale': float(limb_scale), 'caps': caps, 'tubes': tubes}
        own = cap_side == col
        if own.any():
            out[own, 0] += sign * .025 * rig.fit_scale
            block = out[own]
            skin = rig._region(list(ea.TORSO_BONES) + ['upperarm_' + side])
            near = skin[(skin[:, 0] * sign > .10 * rig.fit_scale)
                        & (skin[:, 0] * sign < .26 * rig.fit_scale)
                        & (skin[:, 1] > 1.38 * rig.fit_scale)]
            if len(near) > 8:
                have_lo, have_hi = np.percentile(block[:, 2], [2, 98])
                want_lo, want_hi = np.percentile(near[:, 2], [2, 98]) + np.array([-.015, .015])
                depth_scale = max(1., (want_hi - want_lo) / max(have_hi - have_lo, .04))
                out[own, 2] = ((block[:, 2] - (have_hi + have_lo)/2) * depth_scale
                               + (want_hi + want_lo)/2)
                out[own, 1] += max(0., target_root[1] + .025 * rig.fit_scale - float(np.median(block[:, 1])))
    trunk_share = (1 - arm_share.sum(axis=1)) * (cap_side < 0)
    before_cage = out.copy()
    _clear_trunk(out, triangles, rig, trunk_share, labels)
    cage_motion = np.linalg.norm(out - before_cage, axis=1)
    collar_vertices = 0
    if collar_lift:
        shoulder = rig.origin('upperarm_l')[1]
        top = target[1] + (source_top - shoulder_y) * scale
        for label in np.unique(labels):
            own = labels == label
            if not (trunk_share[own] > .99).all():
                continue
            block = out[own].copy()
            if np.ptp(block[:, 1]) < .16 * rig.fit_scale:
                center = block.mean(axis=0)
                rise = np.clip((center[1] - shoulder) / (top - shoulder), 0., 1.)
                rise *= np.clip((.19 * rig.fit_scale - abs(center[0])) / (.06 * rig.fit_scale), 0., 1.)
            else:
                rise = np.clip((block[:, 1] - shoulder) / (top - shoulder), 0., 1.)
                rise *= np.clip((.19 * rig.fit_scale - np.abs(block[:, 0])) / (.06 * rig.fit_scale), 0., 1.)
            out[own, 1] += rise * collar_lift * rig.fit_scale
            collar_vertices += int(np.count_nonzero(out[own, 1] - block[:, 1] > 1e-6))
    # Bind using the same anatomical assignment used for the rest-pose map.
    torso_bones = list(ea.TORSO_BONES) + ['pelvis']
    joints, weights = rig.weights_for(out, torso_bones)
    pool = np.zeros((len(points), len(rig.joint_names)))
    for slot in range(4):
        pool[np.arange(len(points)), joints[:, slot]] += weights[:, slot] * (1 - arm_share.sum(axis=1))
    for col, side in enumerate(['l', 'r']):
        root, wrist = rig.origin('upperarm_' + side), rig.origin('hand_' + side)
        axis = wrist - root
        t = (out - root) @ axis / (axis @ axis)
        lower = np.clip((t - .43) / .16, 0., 1.)
        lower = lower * lower * (3 - 2 * lower)
        pool[:, rig.joint_names.index('upperarm_' + side)] += arm_share[:, col] * (1 - lower)
        pool[:, rig.joint_names.index('lowerarm_' + side)] += arm_share[:, col] * lower
        own = cap_side == col
        pool[own] = 0
        pool[own, rig.joint_names.index('clavicle_' + side)] = 1
    joints = np.argsort(-pool, axis=1)[:, :4].astype(np.uint16)
    weights = np.take_along_axis(pool, joints, axis=1)
    weights /= weights.sum(axis=1, keepdims=True)
    # Meshy sometimes welds the hanging sleeve to the coat down the flank.
    # Those bridges cannot unfold into an armpit: they become enormous UV
    # streaks in the T-pose. Open that fused seam; the fitted backing closes it.
    mixed = np.ptp(arm_share[triangles], axis=1).max(axis=1) > .20
    edge_scale = np.ones(len(triangles))
    for a, b in ((0, 1), (1, 2), (2, 0)):
        before = np.linalg.norm(points[triangles[:, a]] - points[triangles[:, b]], axis=1)
        after = np.linalg.norm(out[triangles[:, a]] - out[triangles[:, b]], axis=1)
        edge_scale = np.maximum(edge_scale, after / np.maximum(before * scale, 1e-9))
    keep = ~(mixed & (edge_scale > 1.45))
    return out, joints, weights, keep, {'trunkScale': scale, 'limbs': reports,
        'openedSeamTriangles': int((~keep).sum()), 'passes': [
            {'name': 'source_pose_retarget', 'vertices': len(points),
             'frontalAspectScale': 1.0, 'shoulderY': float(target[1]), 'waistY': float(waist)},
            {'name': 'body_contact_cage', 'movedVertices': int((cage_motion > 1e-6).sum()),
             'maximumMove': float(cage_motion.max()), 'meanMove': float(cage_motion.mean())},
            {'name': 'raised_collar', 'lift': collar_lift * rig.fit_scale,
             'movedVertices': collar_vertices},
            {'name': 'open_fused_sleeve_seams', 'triangles': int((~keep).sum())}]}


def _clear_trunk(points, faces, rig, influence, labels):
    """Fit front/back contacts with band affines and at most 15% lateral ease.

    Frontmost surfaces, not ray parity, define contact on overlapping solids.
    A short ornament receives only its centroid's translation, preserving its
    volume and UVs. Both walls of a long shell receive the same band affine.
    """
    heights = np.linspace(.90, 1.58, 35) * rig.fit_scale
    scales, shifts = np.ones(len(heights)), np.zeros(len(heights))
    widths = np.ones(len(heights))
    movable = influence > .99
    verts = points[faces[movable[faces].all(axis=1)]]
    body_verts = rig.positions[rig.faces]
    torso_body = rig._region(ea.TORSO_BONES)
    for i, y in enumerate(heights):
        skin = torso_body[np.abs(torso_body[:, 1] - y) < .03]
        if len(skin) >= 6 and y < 1.49 * rig.fit_scale:
            z = float((skin[:, 2].min() + skin[:, 2].max()) / 2)
            sides = [io.cast(np.array([0., y, z]), np.array([s, 0., 0.]), verts)[0] for s in [-1., 1.]]
            if np.isfinite(sides).all() and min(sides) > .07 * rig.fit_scale:
                want = float(np.percentile(np.abs(skin[:, 0]), 98)) + .014
                widths[i] = np.clip(want / min(sides), 1., 1.15)
        contacts = [[], []]
        armour_depths = [[], []]
        for x in np.linspace(-.17, .17, 13) * rig.fit_scale:
            for col, sign in enumerate([1., -1.]):
                origin = np.array([x, y, sign * .8])
                direction = np.array([0., 0., -sign])
                a, _ = io.cast(origin, direction, verts)
                b, _ = io.cast(origin, direction, body_verts)
                if not np.isfinite(a + b): continue
                az, bz = sign * (.8 - a), sign * (.8 - b)
                if az * sign < -.045: continue  # open neckline / opposite wall
                contacts[col].append(max(0., (bz - az) * sign + .018))
                armour_depths[col].append(az)
        if not all(len(c) >= 3 for c in contacts): continue
        f, b = (float(np.percentile(c, 90)) for c in contacts)
        # A collar opening can leave only a few almost coplanar contacts.
        # Their median depth is not the depth of the trunk: scaling about it
        # used to throw a backplate 200 mm behind the wearer. Use the outer
        # contact envelope and bound the ease of the whole band.
        front = float(np.percentile(armour_depths[0], 90))
        back = float(np.percentile(armour_depths[1], 10))
        if front - back < .12 * rig.fit_scale:
            continue
        scales[i] = np.clip(1 + (f + b) / (front - back), 1., 1.35)
        shifts[i] = np.clip(front + f - front * scales[i], -.025 * rig.fit_scale, .025 * rig.fit_scale)
    for values in (scales, shifts, widths):
        for _ in range(2):
            values[:] = np.convolve(np.pad(values, 1, mode='edge'), [.25, .5, .25], mode='valid')
    for label in np.unique(labels[movable]):
        own = labels == label
        block = points[own].copy()
        if np.ptp(block[:, 1]) < .16:
            if not movable[own].all():
                continue
            c = block.mean(axis=0)
            points[own, 2] += c[2] * (np.interp(c[1], heights, scales)-1) + np.interp(c[1], heights, shifts)
            points[own, 0] += c[0] * (np.interp(c[1], heights, widths)-1)
        else:
            points[own, 2] += influence[own]**2 * (block[:, 2] * (np.interp(block[:, 1], heights, scales)-1)
                                                 + np.interp(block[:, 1], heights, shifts))
            points[own, 0] += influence[own]**2 * block[:, 0] * (np.interp(block[:, 1], heights, widths)-1)


def lining(rig, armour, triangles):
    """A closed fitted backing carrying the body's original blend weights."""
    points, faces = rig.positions, rig.faces
    centre = points[faces].mean(axis=1)
    keep = (centre[:, 1] > .95 * rig.fit_scale) & (centre[:, 1] < 1.535 * rig.fit_scale)
    keep &= np.abs(centre[:, 0]) < .665 * rig.fit_scale
    faces = faces[keep]
    used, inverse = np.unique(faces, return_inverse=True)
    points = points[used].copy()
    faces = inverse.reshape(-1, 3)
    # Merge body UV seams before calculating the backing's outward normals.
    _, first, weld = np.unique(np.round(points, 6), axis=0, return_index=True, return_inverse=True)
    points = points[first]
    used = used[first]
    faces = weld[faces]
    _, unique_faces = np.unique(np.sort(faces, axis=1), axis=0, return_index=True)
    faces = faces[unique_faces]
    # The race's default clothing is a loose shirt, not the anatomy under a
    # cuirass.  Build the backing on a fitted cage instead of copying its
    # flared sleeve hems into every armour design.
    dominant = rig.joints[used, np.argmax(rig.weights[used], axis=1)]
    trunk = np.ones(len(points), dtype=bool)
    for side in ['l', 'r']:
        limb_bones = [rig.joint_names.index(b) for b in ['upperarm_'+side, 'lowerarm_'+side, 'hand_'+side]]
        own = np.isin(dominant, limb_bones)
        root, wrist = rig.origin('upperarm_'+side), rig.origin('hand_'+side)
        axis = wrist-root
        t = np.clip((points[own]-root) @ axis / (axis@axis), 0., 1.)
        centre_line = root + t[:, None]*axis
        radial = points[own]-centre_line
        radius = np.linalg.norm(radial, axis=1)
        want = np.interp(t, [0., .15, .5, 1.], [.055, .048, .040, .034]) * rig.fit_scale
        sleeve_faces = armour[triangles]
        sleeve_faces = sleeve_faces[(sleeve_faces[:, :, 0].mean(axis=1) * (1 if side == 'l' else -1)) > .18 * rig.fit_scale]
        for row, (origin, ray, length) in enumerate(zip(centre_line, radial, radius)):
            if length < 1e-8:
                continue
            hit, _ = io.cast(origin, ray / length, sleeve_faces)
            if np.isfinite(hit) and .012 * rig.fit_scale < hit < .16 * rig.fit_scale:
                want[row] = min(want[row], max(.015 * rig.fit_scale, hit * .75 - .004 * rig.fit_scale))
        points[own] = centre_line + radial * np.minimum(1., want/np.maximum(radius, 1e-8))[:, None]
        trunk &= ~own
    y = points[trunk, 1]/rig.fit_scale
    width = np.interp(y, [.95, 1.05, 1.30, 1.45, 1.52], [.16, .15, .18, .18, .075])*rig.fit_scale
    depth = np.interp(y, [.95, 1.05, 1.30, 1.45, 1.52], [.12, .125, .145, .145, .075])*rig.fit_scale
    radial = points[trunk][:, [0, 2]] - np.array([0., -.045*rig.fit_scale])
    ratio = np.linalg.norm(radial/np.column_stack((width, depth)), axis=1)
    points[np.ix_(trunk, [0, 2])] = radial/np.maximum(1., ratio)[:, None] + np.array([0., -.045*rig.fit_scale])
    # Above the chest the source's collar is considerably narrower than the
    # default shirt. Keep the backing inside that artwork, just as on sleeves;
    # otherwise it hides the collar as soon as excessive depth ease is removed.
    collar = np.flatnonzero(trunk & (points[:, 1] > 1.40 * rig.fit_scale))
    art_faces = armour[triangles]
    for vertex in collar:
        origin = np.array([0., points[vertex, 1], -.045 * rig.fit_scale])
        ray = points[vertex] - origin
        radius = np.linalg.norm(ray)
        if radius < 1e-8:
            continue
        hit, _ = io.cast(origin, ray / radius, art_faces)
        want = .065 * rig.fit_scale
        if np.isfinite(hit):
            want = min(radius, max(.015 * rig.fit_scale, hit * .70))
        blend = np.clip((points[vertex, 1] / rig.fit_scale - 1.40) / .07, 0., 1.)
        points[vertex] = origin + ray * (1 - blend + blend * min(1., want / radius))
    # The copied face selection has a saw-toothed neckline. Construct a level
    # neck rim before giving this new backing any thickness.
    rim_edges = np.vstack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    _, rim_inverse, rim_counts = np.unique(np.sort(rim_edges, axis=1), axis=0,
                                           return_inverse=True, return_counts=True)
    rim = np.unique(rim_edges[rim_counts[rim_inverse] == 1])
    neck = rim[(np.abs(points[rim, 0]) < .13 * rig.fit_scale)
               & (points[rim, 1] > 1.49 * rig.fit_scale)]
    points[neck, 1] = 1.535 * rig.fit_scale
    normals = np.zeros_like(points)
    face_normals = np.cross(points[faces[:, 1]] - points[faces[:, 0]], points[faces[:, 2]] - points[faces[:, 0]])
    for col in range(3): np.add.at(normals, faces[:, col], face_normals)
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-10)
    outer, inner = points + normals * .004, points + normals * .001
    n = len(points)
    edges = np.vstack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    _, inv, counts = np.unique(np.sort(edges, axis=1), axis=0, return_inverse=True, return_counts=True)
    boundary = edges[counts[inv] == 1]
    walls = []
    for a, b in boundary:
        walls.extend([(b, a, a+n), (b, a+n, b+n)])
    triangles = np.vstack((faces, faces[:, ::-1]+n, np.array(walls, dtype=int).reshape(-1, 3)))
    return (np.vstack((outer, inner)), np.vstack((normals, -normals)),
            np.vstack((outer[:, [0, 1]], inner[:, [0, 1]])), triangles.reshape(-1),
            np.vstack((rig.joints[used], rig.joints[used])),
            np.vstack((rig.weights[used], rig.weights[used])))


def backing_colour(surface, texture):
    """Pick an unobtrusive cloth colour from the design's own sleeve atlas."""
    if texture is None:
        return [.045, .025, .018, 1.]
    im = np.asarray(Image.open(BytesIO(texture)).convert('RGB'))
    points = surface.positions
    height = np.ptp(points[:, 1])
    own = (np.abs(points[:, 0]) > .28 * height) & (points[:, 1] < points[:, 1].max() - .35 * height)
    uv = surface.uvs[own]
    if not len(uv):
        uv = surface.uvs
    xy = np.clip(uv, 0., 1.) * np.array([im.shape[1]-1, im.shape[0]-1])
    colours = im[xy[:, 1].astype(int), xy[:, 0].astype(int)].astype(float)
    brightness = colours.mean(axis=1)
    lo, hi = np.percentile(brightness, [20, 55])
    cloth = colours[(brightness >= lo) & (brightness <= hi)]
    return ea.srgb_to_linear(np.median(cloth, axis=0)) + [1.]


def build(source, out, rig, kind='cuirass', label='Remapped armour'):
    original = source.with_name(source.name + '.orig')
    if original.exists():
        source = original
    surface, texture = io.read_source(source)
    cloth_colour = backing_colour(surface, texture)
    raw = surface.positions.copy()
    lift = COLLAR_LIFT.get(source.name.removesuffix('.orig'), 0.)
    points, joints, weights, keep, report = remap(raw, surface.indices.reshape(-1, 3), rig, lift)
    surface.indices = surface.indices.reshape(-1, 3)[keep].reshape(-1)
    surface.positions = points
    canon, _, _ = io._weld(points, surface.indices.reshape(-1, 3))
    faces = surface.indices.reshape(-1, 3)
    _, unique = np.unique(np.sort(canon[faces], axis=1), axis=0, return_index=True)
    report['duplicateFacesRemoved'] = int(len(faces) - len(unique))
    surface.indices = faces[np.sort(unique)].reshape(-1)
    io._make_winding_coherent(surface)
    io._unwind_inverted_shells(surface)
    # Face-based normals follow the new geometry.  UV seams remain split.
    triangles = surface.indices.reshape(-1, 3)
    normals = np.zeros_like(points)
    face_normals = np.cross(points[triangles[:, 1]] - points[triangles[:, 0]],
                            points[triangles[:, 2]] - points[triangles[:, 0]])
    for col in range(3):
        np.add.at(normals, triangles[:, col], face_normals)
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-10)
    glb = ea.EquipmentGLB(generator='Eloria source-pose torso retarget')
    source_doc, _ = ea.read_glb(source)
    source_material = source_doc.get('materials', [{}])[0]
    material = io.textured_material(glb, label + ' Base', texture,
                                    double_sided=source_material.get('doubleSided', False))
    # read_source returns the original encoded image. Originals are JPEGs;
    # labelling those bytes PNG makes Godot export corrupt .png sidecars.
    if texture is not None and texture.startswith(b'\xff\xd8'):
        glb.doc['images'][0]['mimeType'] = 'image/jpeg'
    glb.doc['materials'][material]['pbrMetallicRoughness']['roughnessFactor'] = source_material.get(
        'pbrMetallicRoughness', {}).get('roughnessFactor', .8)
    glb.skeleton(rig)
    primitive = glb.primitive(points, normals, surface.uvs, surface.indices, material,
                              joints=joints, weights=weights)
    p, n, uv, idx, j, w = lining(rig, points, triangles)
    liner_mat = len(glb.doc['materials'])
    glb.doc['materials'].append({'name': label + ' Backing', 'pbrMetallicRoughness': {
        'baseColorFactor': cloth_colour, 'metallicFactor': 0., 'roughnessFactor': 1.}})
    liner = glb.primitive(p, n, uv, idx, liner_mat, joints=j, weights=w, weight_floats=True)
    glb.mesh(label, [primitive], skin=0)
    glb.mesh('GeneratedArmorBacking', [liner], skin=0)
    report['passes'].append({'name': 'fitted_backing', 'vertices': len(p),
                             'triangles': len(idx)//3, 'bodyCover': [.95, 1.535, .665]})
    glb.write(out)
    return dict(report, source=source.name, out=out.name, kind=kind,
                vertices=len(points), triangles=len(triangles), bytes=out.stat().st_size)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('source', type=Path)
    ap.add_argument('-o', required=True, type=Path)
    args = ap.parse_args()
    rig = ea.load_rig(io.RACES / 'luminous_male.glb', body_mesh_names=io.BODY_MESH)
    result = build(args.source, args.o, rig)
    args.o.with_suffix('.report.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))

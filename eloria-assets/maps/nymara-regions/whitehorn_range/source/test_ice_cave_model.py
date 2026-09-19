"""Pinned model, transform, material and retained approach contracts."""
from pathlib import Path
import hashlib
import json
import struct
import sys

import numpy as np

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE.parent / "_toolkit"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from amberwood import gltf as GLTF
import cave_model as CAVE
import kit


def _front_hit(mesh, x, y):
    """First surface hit by an axis-aligned ray from model +Z."""
    triangles = mesh.positions[mesh.indices.reshape(-1, 3)]
    px, py = triangles[:, :, 0], triangles[:, :, 1]
    denominator = ((py[:, 1]-py[:, 2])*(px[:, 0]-px[:, 2])
                   + (px[:, 2]-px[:, 1])*(py[:, 0]-py[:, 2]))
    usable = np.abs(denominator) > 1e-12
    a = np.zeros(len(triangles))
    b = np.zeros(len(triangles))
    a[usable] = ((py[usable, 1]-py[usable, 2])*(x-px[usable, 2])
                 + (px[usable, 2]-px[usable, 1])*(y-py[usable, 2])) / denominator[usable]
    b[usable] = ((py[usable, 2]-py[usable, 0])*(x-px[usable, 2])
                 + (px[usable, 0]-px[usable, 2])*(y-py[usable, 2])) / denominator[usable]
    c = 1.0-a-b
    inside = usable & (a >= -1e-7) & (b >= -1e-7) & (c >= -1e-7)
    if not inside.any():
        return -np.inf
    z = a*triangles[:, 0, 2] + b*triangles[:, 1, 2] + c*triangles[:, 2, 2]
    return float(z[inside].max())


def _actor_blocker(mesh, centre_x, scale, x_samples=11, y_samples=25):
    """Nearest +Z surface across the tested 1.0 m by 2.1 m actor prism."""
    half_width = 0.5 / scale
    height = 2.1 / scale
    return max(
        _front_hit(mesh, x, y)
        for x in np.linspace(centre_x-half_width, centre_x+half_width, x_samples)
        for y in np.linspace(CAVE.PASSAGE_FLOOR_Y+1e-4,
                             CAVE.PASSAGE_FLOOR_Y+height-1e-4, y_samples)
    )


def test_pinned_glb_preserves_source_vertices_uv_seams_and_fit():
    assert hashlib.sha256(CAVE.ASSET.read_bytes()).hexdigest() == CAVE.ASSET_SHA256
    mesh = CAVE.source_mesh()
    assert mesh.vertex_count == 5770
    assert mesh.triangle_count == 3859
    assert mesh.copy().weld(1e-4).vertex_count == 5770
    low, high = mesh.bounds()
    assert np.allclose(low, [-8.0, -0.190478, -8.0], atol=2e-5)
    assert np.allclose(high, [8.0, 8.153282, 8.0], atol=2e-5)
    watch_scale = CAVE.scale_for_span(5.0)
    assert np.isclose(watch_scale, 10.666666666666666)
    smaller = CAVE.source_mesh(scale=watch_scale)
    small_low, small_high = smaller.bounds()
    assert np.isclose(small_high[0]-small_low[0], watch_scale)
    assert np.isclose(small_high[2]-small_low[2], watch_scale)


def test_original_actor_prism_is_clear_to_retained_portal_plane():
    raw = CAVE._raw_mesh()
    cases = (
        ("primary", CAVE.SCALE, np.array([-0.37638475, 0.09364375, -3.20237515])),
        # The only smaller production caller is Landmark_WatchCave. Its root is
        # (-122,47.64,-141), yaw pi; its portal is (-122,47.64,-136), hence
        # local (0,0,-5) before placement rotation.
        ("watch", CAVE.scale_for_span(5.0), np.array([0.0, 0.0, -5.0])),
    )
    for name, scale, portal_kit in cases:
        centre_x = -portal_kit[0] / scale
        portal_z = -portal_kit[2] / scale
        blocker = _actor_blocker(raw, centre_x, scale)
        assert blocker < portal_z, name
        # The recessed wall stays more than seven metres behind either portal.
        assert -scale*blocker-portal_kit[2] > 7.0, name

    watch_scale = CAVE.scale_for_span(5.0)
    watch_portal_z = 5.0 / watch_scale
    candidates = np.linspace(-0.15, 0.15, 31)
    valid = [x for x in candidates
             if _actor_blocker(raw, x, watch_scale, 7, 15) <= watch_portal_z]
    assert min(valid) <= 0.0 <= max(valid)
    assert (max(valid)-min(valid))*watch_scale > 2.0


def test_exact_jpegs_register_as_one_double_sided_pbr_material(tmp_path):
    builder = GLTF.GltfBuilder()
    CAVE.register_material(builder)
    assert [image["mimeType"] for image in builder._images] == ["image/jpeg"] * 3
    assert [image["name"] for image in builder._images] == list(CAVE.IMAGE_NAMES)
    assert [hashlib.sha256(CAVE._image_bytes(*CAVE._document(), index)).hexdigest()
            for index in range(3)] == list(CAVE.EXPECTED_IMAGE_SHA256)
    material = builder._materials[0]
    assert material["name"] == CAVE.MATERIAL
    assert material["doubleSided"] is True
    assert set(material) >= {"pbrMetallicRoughness", "normalTexture"}
    assert "occlusionTexture" not in material

    mesh = CAVE.source_mesh()
    builder.add_mesh("approved_cave", mesh)
    builder.add_node(GLTF.Node("ApprovedCave", mesh="approved_cave"))
    output = tmp_path / "adapter.glb"
    builder.write_glb(str(output))
    raw = output.read_bytes()
    offset = 12
    document = binary = None
    while offset < len(raw):
        length, kind = struct.unpack_from("<I4s", raw, offset)
        offset += 8
        payload = raw[offset:offset+length]
        offset += length
        if kind == b"JSON":
            document = json.loads(payload.rstrip(b" \t\r\n\0"))
        elif kind == b"BIN\0":
            binary = payload
    assert document is not None and binary is not None
    assert [image["mimeType"] for image in document["images"]] == ["image/jpeg"] * 3
    readback_hashes = []
    for image in document["images"]:
        view = document["bufferViews"][image["bufferView"]]
        start = int(view.get("byteOffset", 0))
        payload = binary[start:start+int(view["byteLength"])]
        readback_hashes.append(hashlib.sha256(payload).hexdigest())
    assert readback_hashes == list(CAVE.EXPECTED_IMAGE_SHA256)


def test_cave_kit_retains_floor_stairs_and_lanterns_only():
    group = kit.ice_cave_mouth(seed=71, approach_drop=1.7)
    assert len(group.walk_parts) == 2
    assert [part.material for part in group.parts].count(CAVE.MATERIAL) == 1
    assert [part.material for part in group.parts].count(kit.IRON) == 2
    assert [part.material for part in group.parts].count(kit.AMBER) == 2
    assert len(group.parts) == 5
    walk_low, walk_high = group.walk_bounds()
    assert np.isclose(walk_high[1], CAVE.WALK_FLOOR_TOP_Y)
    assert walk_low[2] <= -7.0 and walk_high[2] >= 4.4

    watch = kit.ice_cave_mouth(seed=407, span=5.0, height=4.0)
    watch_shell = next(part for part in watch.parts if part.material == CAVE.MATERIAL)
    low, high = watch_shell.bounds()
    assert np.isclose(high[0]-low[0], CAVE.scale_for_span(5.0))
    assert np.isclose(high[2]-low[2], CAVE.scale_for_span(5.0))
    watch_walk_low, watch_walk_high = watch.walk_bounds()
    assert np.isclose(watch_walk_high[1], CAVE.WALK_FLOOR_TOP_Y)
    assert np.allclose([watch_walk_low[0], watch_walk_high[0]], [-2.0, 2.0])
    assert watch_walk_low[2] <= -7.0 and watch_walk_high[2] >= 4.4

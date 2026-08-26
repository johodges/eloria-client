import json
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eloria-assets" / "tools"))
import generate_authored_players as authored


REQUIRED_CLIPS = {
    "idle", "idle2", "walk", "run", "combat_idle", "attack", "cast",
    "pain", "die", "sit_down", "sit", "stand_up", "harvest", "pick", "drop",
}


def read_glb(path):
    data = path.read_bytes()
    assert data[:4] == b"glTF"
    version, total = struct.unpack_from("<II", data, 4)
    assert version == 2 and total == len(data)
    json_size, json_kind = struct.unpack_from("<II", data, 12)
    assert json_kind == 0x4E4F534A
    document = json.loads(data[20:20 + json_size])
    binary_offset = 20 + json_size
    binary_size, binary_kind = struct.unpack_from("<II", data, binary_offset)
    assert binary_kind == 0x004E4942
    assert binary_offset + 8 + binary_size == len(data)
    assert binary_size >= document["buffers"][0]["byteLength"]
    return document


def test_luminous_runtime_glbs_have_skin_and_complete_action_set(tmp_path):
    clips = authored.read_universal_animations(authored.SOURCE / "luminous_universal.eanim")
    assert set(clips) == REQUIRED_CLIPS
    for sex in ("female", "male"):
        name = f"luminous_{sex}"
        positions, normals, uvs, faces, weights = authored.read_emesh(authored.SOURCE / f"{name}.emesh")
        output = tmp_path / f"{name}_quaternius_v2.glb"
        runtime = authored.luminous_runtime_mesh(positions, normals, uvs, faces, weights)
        authored.write_luminous_glb(output, name, *runtime, authored.fitted_bones(name), clips)
        document = read_glb(output)
        assert len(document["skins"]) == 1
        assert len(document["skins"][0]["joints"]) == 37
        assert {animation["name"] for animation in document["animations"]} == REQUIRED_CLIPS
        attributes = document["meshes"][0]["primitives"][0]["attributes"]
        assert {"POSITION", "NORMAL", "TEXCOORD_0", "JOINTS_0", "WEIGHTS_0"} <= set(attributes)


def test_checked_in_runtime_glbs_are_self_contained():
    for sex in ("female", "male"):
        path = authored.SOURCE / "runtime" / f"luminous_{sex}_quaternius_v2.glb"
        document = read_glb(path)
        assert document["buffers"] == [{"byteLength": document["buffers"][0]["byteLength"]}]
        assert not document.get("images") and not document.get("textures")
        assert {animation["name"] for animation in document["animations"]} == REQUIRED_CLIPS


def test_runtime_action_mapping_covers_every_protocol_frame():
    source = (ROOT / "actor_glb_runtime.cpp").read_text(encoding="utf-8")
    for clip in REQUIRED_CLIPS:
        assert f'"{clip}"' in source
    assert "for(int f=19;f<=61;f++)" in source


def test_quaternius_joint_mapping_matches_runtime_skeleton():
    source = (ROOT / "eloria-assets" / "tools" / "import_quaternius_luminous.py").read_text(
        encoding="utf-8"
    )
    expected = {
        '"thumb_01_l": 31', '"index_01_l": 32',
        '"thumb_01_r": 33', '"index_01_r": 34',
        '"ball_l": 35', '"ball_r": 36',
    }
    assert all(mapping in source for mapping in expected)
    runtime = (ROOT / "actor_glb_runtime.cpp").read_text(encoding="utf-8")
    assert "if(joint==32)joint=31" in runtime
    assert "joint==35&&m.v[x].p[2]>.30f" in runtime

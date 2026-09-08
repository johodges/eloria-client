"""A rebuilt package replaces an already-published map digest."""
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "eloria-assets/tools/sync_package_content.py"
SPEC = importlib.util.spec_from_file_location("package_digest_sync", SOURCE)
sync = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sync
SPEC.loader.exec_module(sync)


@pytest.mark.parametrize("entry", [
    {"id": "demo", "arrival": [2, 3], "packageSha256": "0" * 64},
    {"id": "demo", "packageSha256": "0" * 64, "arrival": [2, 3]},
    {"id": "demo", "packageSha256": "0" * 64},
])
def test_rebuilt_package_replaces_existing_digest_and_then_settles(tmp_path, monkeypatch, entry):
    manifest = tmp_path / "world.json"
    manifest.write_bytes(b'{"asset":{"glb":"world.glb"}}\r\n')
    (tmp_path / "world.glb").write_bytes(b"rebuilt geometry")
    monkeypatch.setattr(sync, "registry_packages", lambda: {"demo": manifest})
    original = {"maps": [copy.deepcopy(entry)], "unrelated": {"post": [4, 5]}}
    text, published, missing, count = sync.publish_digests(original)
    assert text is not None
    updated = json.loads(text)
    assert updated["maps"][0]["packageSha256"] == sync.digest_for(manifest)
    assert updated["unrelated"] == {"post": [4, 5]}
    assert not missing and count == 1
    again, _, _, _ = sync.publish_digests(updated)
    assert again is None

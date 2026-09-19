"""Binary authored assets participate in retained-library certificates."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import build_library as B


def test_source_asset_bytes_invalidate_inputs_but_neighbouring_cache_does_not(
        tmp_path, monkeypatch):
    client = tmp_path / "client"
    maps = client / "eloria-assets/maps"
    regions = maps / "nymara-regions"
    continent = regions / "_continent"
    toolkit = regions / "_toolkit"
    source = regions / "sample/source"
    assets = source / "assets/cave-v001"
    cache = source / "cache"
    for folder in (continent, toolkit, assets, cache):
        folder.mkdir(parents=True, exist_ok=True)
    fake_builder = continent / "build_library.py"
    fake_builder.write_text("# fixture\n", encoding="utf-8")
    (continent / "legacy-geography.json").write_text("{}\n", encoding="utf-8")
    (continent / "legacy-contracts.json").write_text("{}\n", encoding="utf-8")
    (source / "build_sample.py").write_text("VALUE = 1\n", encoding="utf-8")
    (source / "design.json").write_text("{}\n", encoding="utf-8")
    model = assets / "model.glb"
    model.write_bytes(b"approved model v1")
    irrelevant = cache / "preview.bin"
    irrelevant.write_bytes(b"cache v1")

    monkeypatch.setattr(B, "CLIENT", client)
    monkeypatch.setattr(B, "MAPS", maps)
    monkeypatch.setattr(B, "REGIONS", regions)
    monkeypatch.setattr(B, "TOOLKIT", toolkit)
    monkeypatch.setattr(B, "HERE", continent)
    monkeypatch.setattr(B, "__file__", str(fake_builder))

    first = B.inputs("sample")
    model_key = model.relative_to(client).as_posix()
    assert model_key in first
    assert irrelevant.relative_to(client).as_posix() not in first
    assert (source / "build_sample.py").relative_to(client).as_posix() in first
    assert (source / "design.json").relative_to(client).as_posix() in first

    model.write_bytes(b"approved model v2")
    second = B.inputs("sample")
    assert second[model_key] != first[model_key]

    irrelevant.write_bytes(b"cache v2")
    assert B.inputs("sample") == second

"""The client streams the continent-v2 isles beside each other (serve plan CV11).

    python3 -m pytest godot-client/tests/test_continent_v2_links.py -q

The isles' land links live in godot-client/data/maps/exterior_connections-continent-v2.json, written by
_continent_v2/publish_links.py from _continent_v2/crossings.json, and the stream reads them after the legacy graph.
The legacy graph, exterior_connections.json, stays the legacy publisher's: its walk proof and continent audit hold it
equal to the server's own copy, which never holds the isles' links (they are in the server's overlay).
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "eloria-assets" / "maps" / "continent-v2" / "_continent_v2" / "publish_links.py"
SPEC = importlib.util.spec_from_file_location("publish_links", SOURCE)
links = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = links
SPEC.loader.exec_module(links)
ISLES = ("sw_isle", "tollholms", "gull_skerries")


def test_the_committed_links_are_crossings_jsons():
    assert links.check(ROOT) == []


def test_the_legacy_graph_names_no_isle():
    graph = json.loads((ROOT / links.LEGACY_LINKS).read_text(encoding="utf-8"))
    for link in graph["connections"] + graph.get("visualConnections", []):
        assert not {end["map"] for end in link["ends"]} & set(ISLES), link["id"]


def test_every_isle_link_joins_two_served_isles_in_their_registry_frames():
    graph = json.loads((ROOT / links.CLIENT_LINKS).read_text(encoding="utf-8"))
    legacy = json.loads((ROOT / links.LEGACY_LINKS).read_text(encoding="utf-8"))
    rows = json.loads((ROOT / links.REGISTRY).read_text(encoding="utf-8"))["maps"]
    assert {key: graph[key] for key in ("preloadDistance", "retainDistance", "maximumNeighbours")} == \
        {key: legacy[key] for key in ("preloadDistance", "retainDistance", "maximumNeighbours")}
    assert [link["id"] for link in graph["connections"]] == ["sw_isle--tollholms", "border--sw_isle--gull_skerries"]
    for link in graph["connections"]:
        assert link["seamless"] is True
        assert {end["map"] for end in link["ends"]} <= set(ISLES)
        for end in link["ends"]:
            row = rows[end["map"]]
            assert row["status"] == links.SERVED_STATUS
            assert end["frame"]["globalTranslation"] == row["continentGeography"]["translation"]
            assert end["frame"]["geometryMode"] == "continent-chunks-v1"
            assert end["crossingRuns"] and end["preloadEdges"]


def fixture_checkout(tmp_path: Path) -> Path:
    """A checkout holding copies of the real inputs: the catalog, the registry, both graphs, crossings.json and the
    three territory manifests (each package's served-grid hash is what the tool compares)."""
    root = tmp_path / "checkout"
    paths = [links.CATALOG, links.REGISTRY, links.LEGACY_LINKS, links.CLIENT_LINKS, links.CROSSINGS,
             "eloria-assets/tools/publish_continent_geography.py"]
    rows = json.loads((ROOT / links.REGISTRY).read_text(encoding="utf-8"))["maps"]
    for entry in json.loads((ROOT / links.CATALOG).read_text(encoding="utf-8"))["entries"]:
        paths.append(rows[entry["id"]]["manifest"][len("res://../"):])
    for relative in paths:
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, root / relative)
    return root


def test_a_missing_or_edited_file_is_caught_and_written_again(tmp_path):
    root = fixture_checkout(tmp_path)
    committed = (root / links.CLIENT_LINKS).read_bytes()
    (root / links.CLIENT_LINKS).unlink()
    assert links.check(root) == [f"{links.CLIENT_LINKS} is missing; run _continent_v2/publish_links.py"]
    assert links.main(["--checkout", str(root)]) == 0
    assert (root / links.CLIENT_LINKS).read_bytes() == committed
    (root / links.CLIENT_LINKS).write_bytes(committed.replace(b'"seamless": true', b'"seamless": false', 1))
    assert "is not crossings.json's links" in links.check(root)[0]
    assert links.main(["--checkout", str(root)]) == 0 and links.check(root) == []
    # the legacy graph is never touched
    assert (root / links.LEGACY_LINKS).read_bytes() == (ROOT / links.LEGACY_LINKS).read_bytes()


def edit_json(path: Path, change) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


@pytest.mark.parametrize("case, expected", [
    ("distances", "the stream has one value for every link"),
    ("stale crossings", "run crossings_v2.py again"),
    ("preview row", "has no continent-v2-served registry row"),
    ("moved frame", "is not its registry row's"),
    ("legacy link", "the stream would hold two links for one seam"),
])
def test_refusals_write_nothing(tmp_path, case, expected):
    root = fixture_checkout(tmp_path)
    if case == "distances":
        edit_json(root / links.LEGACY_LINKS, lambda d: d.update(preloadDistance=240))
    elif case == "stale crossings":
        edit_json(root / links.CROSSINGS,
                  lambda d: d["inputs"]["maps"]["tollholms"].update(servedGridSha256="0" * 64))
    elif case == "preview row":
        edit_json(root / links.REGISTRY, lambda d: d["maps"]["gull_skerries"].update(
            status="continent-v2-client-preview"))
    elif case == "moved frame":
        edit_json(root / links.REGISTRY, lambda d: d["maps"]["tollholms"]["continentGeography"].update(
            translation=[2800.0, 0.0, 7368.0]))
    elif case == "legacy link":
        def add(d):
            d["connections"].append({"id": "sw_isle--westhaven", "seamless": True, "ends": [
                {"map": "sw_isle"}, {"map": "westhaven"}]})
        edit_json(root / links.LEGACY_LINKS, add)
    before = (root / links.CLIENT_LINKS).read_bytes()
    problems = links.check(root)
    assert len(problems) == 1 and expected in problems[0], problems
    assert links.main(["--checkout", str(root)]) == 1
    assert (root / links.CLIENT_LINKS).read_bytes() == before

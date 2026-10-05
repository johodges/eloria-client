"""The continent-v2 isles' tab maps are generated from their packages, and are current (serve plan CV14).

    python3 -m pytest godot-client/tests/test_continent_v2_cartography.py -q

A chunk-streamed isle holds only the chunks round the player, so its Tab map and minimap need the isle's own picture
(minimap.webp, drawn from the package's chunks by _continent_v2/render_minimap.py) and a cartography row framing it
(godot-client/data/maps/cartography-continent-v2.json, written by _continent_v2/publish_cartography.py; main.gd
appends its rows after cartography.json's). This fails when a package was republished without its picture being
drawn again, a picture or a frame moved, cartography.json's pixel lattice changed, or the file was edited by hand.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "eloria-assets" / "maps" / "continent-v2" / "_continent_v2"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, V2 / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


tool = load("publish_cartography")
render = load("render_minimap")


def read(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_the_tab_maps_and_their_pictures_are_current():
    assert tool.check(ROOT) == []
    served = [key for key, _ in tool.served(read(tool.REGISTRY))]
    assert render.check(ROOT, served) == []


def test_every_served_isle_has_a_row_of_its_own_frame_in_the_legacy_lattice():
    registry = read(tool.REGISTRY)["maps"]
    data = read(tool.OUTPUT)
    continent = read(tool.CARTOGRAPHY)["continent"]
    assert data["lattice"] == {"originMetres": continent["originMetres"],
                               "metresPerPixel": continent["metresPerPixel"]}
    served = [key for key, _ in tool.served({"maps": registry})]
    assert served == ["sw_isle", "tollholms", "gull_skerries"]
    assert [row["serverMap"] for row in data["regions"]] == served
    legacy = {row["serverMap"] for row in read(tool.CARTOGRAPHY)["regions"]}
    for row in data["regions"]:
        key = row["serverMap"]
        assert key not in legacy
        assert row["frame"] == "continent-v2" and "continentRect" not in row
        assert row["name"] == registry[key]["label"]
        assert row["globalTranslation"] == registry[key]["continentGeography"]["translation"]
        manifest = json.loads(tool.legacy_tool(ROOT).resource_to_path(registry[key]["manifest"]).read_text(
            encoding="utf-8"))
        bounds = manifest["asset"]["mapBounds"]
        # the picture is the live Tab map's frame, so the crop is the whole picture
        assert row["tabMap"]["worldMin"] == [bounds["min"][0], bounds["min"][2]]
        assert row["tabMap"]["worldMax"] == [bounds["max"][0], bounds["max"][2]]
        assert row["tabMap"]["region"] == [0, 0, *manifest["minimap"]["imageSize"]]
        scale, origin = continent["metresPerPixel"], continent["originMetres"]
        polygon = manifest["continentGeography"]["ownershipPolygon"]
        assert row["continentPolygon"] == [[(x - origin[0]) / scale, (z - origin[1]) / scale] for x, z in polygon]


def test_the_label_point_is_the_area_centroid():
    assert tool.polygon_centroid([[0, 0], [4, 0], [4, 2], [0, 2]]) == [2.0, 1.0]
    centroid = tool.polygon_centroid([[0, 0], [4, 0], [4, 1], [1, 1], [1, 4], [0, 4]])
    assert [round(v, 4) for v in centroid] == [1.3571, 1.3571]   # (4 x (2, .5) + 3 x (.5, 2.5)) / 7

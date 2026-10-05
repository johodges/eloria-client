"""_continent_v2/frames.py: the one frame source of the isles' served tiles.

The frame is copied into the bootstrap stub, the authoring spec, the client registry row and the published manifest;
frames.load refuses unless all four agree, and its tile rule is the composer's authoring.server_tile. These tests pin
the D2b frames, show the lattice is whole continent metres, compare the rule with the tiles the region bake recorded,
apply it to the committed content tables, and show each disagreement is refused.

The bake's tiles: the published packages keep the bake's serverTile of every spawn point and landmark, and those are
checked here every run. A fresh bake of every marker is checked too when ELORIA_V2_BAKES names one or more bake
directories (or continent-authoring.json files), separated by the platform's path separator.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import random
import shutil
import sys

import pytest

V2 = Path(__file__).resolve().parents[2]
CHECKOUT = V2.parents[2]
sys.path.insert(0, str(V2 / "_continent_v2"))
sys.path.insert(0, str(CHECKOUT / "godot-client" / "tools"))
import frames as F  # noqa: E402
import continent_v2_territories as T  # noqa: E402

MAPS = ("sw_isle", "tollholms", "gull_skerries")


@pytest.fixture(scope="module")
def all_frames():
    return F.load_all()


def test_the_catalog_has_the_three_isles(all_frames):
    assert set(all_frames) == set(MAPS)


def test_the_d2b_frames(all_frames):
    expected = {"sw_isle": ((1023, 993), 2046, (1418.0, 0.0, 7270.0)),
                "tollholms": ((367, 949), 1902, (2800.0, 0.0, 7398.0)),
                "gull_skerries": ((571, 779), 1560, (896.0, 0.0, 7876.0))}
    for region, (origin, side, translation) in expected.items():
        frame = all_frames[region]
        assert frame.origin == origin and frame.cells == (side, side) and frame.translation == translation, region
        assert frame.collision_origin == (-float(origin[0]), float(origin[1]))
    # the server's MAP_TILES_WIDE_BY_NAME (cells / 6): 341, 317, 260
    assert [all_frames[r].cells[0] // 6 for r in MAPS] == [341, 317, 260]


def test_the_tile_rule_and_the_appendix_points(all_frames):
    sw = all_frames["sw_isle"]
    points = {"arrival": ((-443.0, 121.0), (580, 872)), "beam": ((-439.0, 118.0), (584, 875)),
              "respawn": ((-447.0, 124.0), (576, 869)), "ferry": ((592.5, 688.5), (1615, 304)),
              "desk": ((-448.5, 106.5), (574, 886)), "Nesh": ((-430.5, 109.5), (592, 883))}
    for name, ((x, z), tile) in points.items():
        assert sw.tile(x, z) == tile, name
    # a tile is [tx - ox, tx - ox + 1) by (oy - ty - 1, oy - ty]: both edges land as the rule says
    assert sw.tile(-1023.0, 993.0) == (0, 0)
    assert sw.tile(-1022.0001, 992.0001) == (0, 0)
    assert sw.tile(-1022.0, 992.0) == (1, 1)


def test_an_integer_lattice_shared_by_the_neighbours(all_frames):
    for frame in all_frames.values():
        lx, lz = frame.lattice
        assert lx == int(lx) and lz == int(lz), frame.region
    sw, th, gs = (all_frames[r] for r in MAPS)
    # the R32 seam at continent x 2437 and the south plateau seam at z 8259: the same continent metre is a tile of
    # both neighbours, whose centres coincide exactly
    for a, b, point in ((sw, th, (2437.5, 7000.5)), (sw, th, (2436.5, 8100.5)), (sw, gs, (1200.5, 8258.5)),
                        (sw, gs, (1200.5, 8259.5))):
        ta, tb = a.tile_of_continent(*point), b.tile_of_continent(*point)
        assert a.continent(*ta) == b.continent(*tb) == point


def test_conversions_round_trip(all_frames):
    rng = random.Random(7)
    for frame in all_frames.values():
        for _ in range(500):
            tx, ty = rng.randrange(frame.cells[0]), rng.randrange(frame.cells[1])
            assert frame.tile(*frame.local(tx, ty)) == (tx, ty)
            assert frame.tile_of_continent(*frame.continent(tx, ty)) == (tx, ty)
            x, z = rng.uniform(-500, 500), rng.uniform(-500, 500)
            assert frame.to_local(*frame.to_continent(x, z)) == pytest.approx((x, z))


def test_a_point_outside_the_window_is_refused(all_frames):
    sw = all_frames["sw_isle"]
    with pytest.raises(F.FrameError, match="outside"):
        sw.tile(-1024.0, 0.0)
    with pytest.raises(F.FrameError, match="outside"):
        sw.tile(0.0, -1053.5)


def _records_with_tiles(doc):
    for section in ("spawnPoints", "landmarks", "interactives", "npcMarkers", "harvestables", "portals"):
        for record in doc.get(section, []):
            if "serverTile" in record:
                yield section, record


def test_equals_the_tiles_the_bake_recorded_in_the_published_packages(all_frames):
    checked = 0
    for region in MAPS:
        manifest = json.loads((V2 / region / "client" / "world.json").read_text(encoding="utf-8"))
        for section, record in _records_with_tiles(manifest):
            x, _, z = record["position"]
            assert list(all_frames[region].tile(x, z)) == record["serverTile"], (region, section, record["id"])
            checked += 1
    assert checked >= 18   # 3 arrivals and the 15 landmarks published today


def _bakes():
    raw = os.environ.get("ELORIA_V2_BAKES", "")
    out = []
    for item in filter(None, raw.split(os.pathsep)):
        path = Path(item)
        out.append(path / "continent-authoring.json" if path.is_dir() else path)
    return out


@pytest.mark.skipif(not _bakes(), reason="ELORIA_V2_BAKES names no bake of a v2 territory")
def test_equals_the_bake_server_tile_for_every_marker(all_frames):
    for path in _bakes():
        doc = json.loads(path.read_text(encoding="utf-8"))
        frame = all_frames[doc["regionId"]]
        server = doc["server"]
        assert (tuple(server["origin"]), tuple(server["cells"])) == (frame.origin, frame.cells), path
        assert tuple(server["collisionOriginMetres"]) == frame.collision_origin, path
        assert tuple(doc["continentTranslation"]) == frame.translation, path
        count = 0
        for section, records in doc["gameplay"].items():
            for record in records:
                if "serverTile" not in record:
                    continue
                x, _, z = record["position"]
                assert list(frame.tile(x, z)) == record["serverTile"], (path, section, record["id"])
                count += 1
        assert count > 0, path


def scene_marker_positions(region):
    scene = T.load_scene((CHECKOUT / "godot-client" / "world_authoring" / "regions" / region /
                          f"{region}.tscn").resolve())
    for path, section in scene.nodes.items():
        if path.startswith("Gameplay/") and scene.script_of(section).endswith("gameplay_marker.gd"):
            m = scene.world(path)
            yield json.loads(section.properties["record_id"]), float(m[0, 3]), float(m[2, 3])


def test_every_scene_marker_lies_in_its_window(all_frames):
    for region in MAPS:
        records = list(scene_marker_positions(region))
        assert records, region
        for record, x, z in records:
            all_frames[region].tile(x, z)   # raises outside the window


def test_every_spawn_row_lies_in_its_window_one_row_a_tile(all_frames):
    pins = {"sw-spawn-0001": (374, 956), "sw-spawn-0883": (1718, 189), "gs-spawn-0001": (828, 380),
            "th-spawn-0144": (333, 244)}
    for region in MAPS:
        table = json.loads((V2 / region / "content" / "spawns.json").read_text(encoding="utf-8"))
        tiles = {}
        for row in table["spawns"]:
            tile = all_frames[region].tile(*row["local"])
            assert tile not in tiles, (region, row["id"], tiles.get(tile))
            tiles[tile] = row["id"]
            if row["id"] in pins:
                assert tile == pins[row["id"]], row["id"]


# --- refusals: a scratch checkout holding copies of the frame's files ---------------------------------------------

@pytest.fixture()
def scratch(tmp_path):
    files = [F.CATALOG, F.REGISTRY]
    for entry in F.catalog_entries():
        files += [F._rel(F._res(entry["manifestPath"], CHECKOUT), CHECKOUT),
                  F._rel(F._res(entry["authoringSpecPath"], CHECKOUT), CHECKOUT),
                  f"eloria-assets/maps/continent-v2/{entry['id']}/client/world.json"]
    for rel in files:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CHECKOUT / rel, tmp_path / rel)
    assert F.load("sw_isle", tmp_path).origin == (1023, 993)
    return tmp_path


def edit(path: Path, change):
    doc = json.loads(path.read_text(encoding="utf-8"))
    change(doc)
    path.write_text(json.dumps(doc), encoding="utf-8")


def test_refuses_a_mismatched_registry_row(scratch):
    # the drift the legacy continent suffered: the registry left on the frame before a move (D2b moved sw_isle 30 m)
    edit(scratch / F.REGISTRY, lambda d: d["maps"]["sw_isle"]["coordinateTransform"].update(serverOrigin=[1023, 1023]))
    with pytest.raises(F.FrameError, match="registry row: origin"):
        F.load("sw_isle", scratch)
    assert F.load("tollholms", scratch).origin == (367, 949)


def test_refuses_a_registry_row_with_another_translation_or_scale(scratch):
    edit(scratch / F.REGISTRY, lambda d: d["maps"]["tollholms"]["continentGeography"].update(
        translation=[2800.0, 0.0, 7399.0]))
    with pytest.raises(F.FrameError, match="registry row: translation"):
        F.load("tollholms", scratch)
    edit(scratch / F.REGISTRY, lambda d: d["maps"]["gull_skerries"]["coordinateTransform"].update(metresPerTile=2.0))
    with pytest.raises(F.FrameError, match="metresPerTile"):
        F.load("gull_skerries", scratch)


def test_refuses_a_missing_registry_row(scratch):
    edit(scratch / F.REGISTRY, lambda d: d["maps"].pop("gull_skerries"))
    with pytest.raises(F.FrameError, match="no row"):
        F.load("gull_skerries", scratch)


def test_refuses_a_mismatched_manifest_or_spec(scratch):
    manifest = scratch / "eloria-assets/maps/continent-v2/sw_isle/client/world.json"
    edit(manifest, lambda d: d["coordinateTransform"].update(serverCells=[2048, 2048]))
    with pytest.raises(F.FrameError, match="published manifest: cells"):
        F.load("sw_isle", scratch)
    spec = scratch / "godot-client/world_authoring/regions/tollholms/region-authoring-spec.json"
    edit(spec, lambda d: d["server"].update(collisionOriginMetres=[-367.0, 950.0]))
    with pytest.raises(F.FrameError, match="region-authoring-spec: collisionOriginMetres"):
        F.load("tollholms", scratch)

"""The continent-v2 island group's three maps: ownership, shared seam vertices, mirrored seam patches, crops.

sw_isle, tollholms and gull_skerries (owner decisions D2a-D2c) share one conditioned base: sw_isle's terrain grid
covers the whole group and the other two are byte crops of it, so the vertices two neighbours share are bit-identical.
These tests run godot-client/tools/continent_v2_territories.py on the committed territories, and show that each
check catches the fault it is there for.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "godot-client" / "tools"))
import continent_v2_territories as T  # noqa: E402


@pytest.fixture(scope="module")
def territories():
    return T.load_territories()


@pytest.fixture(scope="module")
def lattice(territories):
    return T.Lattice.of(territories)


def by_id(territories, identity):
    return next(t for t in territories if t.id == identity)


def replaced(territories, identity, **changes):
    return [dataclasses.replace(t, **changes) if t.id == identity else t for t in territories]


def vertex_index(territory, x, z):
    column, row = (x - territory.first_vertex[0]) / T.CELL, (z - territory.first_vertex[1]) / T.CELL
    assert column == int(column) and row == int(row)
    return int(row), int(column)


def test_the_catalog_lists_the_island_group(territories):
    # sorted by label, as the composer's catalog loader (authoring_catalog.load_catalog) requires
    assert [t.id for t in territories] == ["sw_isle", "gull_skerries", "tollholms"]
    assert [t.label for t in territories] == ["Landfall", "The Gull Skerries", "The Tollholms"]


def test_scene_frames_agree_with_manifests_and_specs(territories):
    problems, report = T.check_frames(territories)
    assert problems == []
    assert report["sw_isle"]["server"]["origin"] == [1023, 993]
    assert report["tollholms"]["server"]["origin"] == [367, 949]
    assert report["gull_skerries"]["server"]["origin"] == [571, 779]


def test_the_new_territories_are_byte_crops_of_the_sw_isle_base(territories):
    problems, report = T.check_crops(territories)
    assert problems == []
    assert set(report) == {"tollholms", "gull_skerries"}
    assert all(entry == {"parent": "sw_isle", "heights": True, "colors": True, "frame": True}
               for entry in report.values())


def test_ownership_polygons_do_not_overlap_and_own_every_island(territories, lattice):
    problems, report = T.check_ownership(territories, lattice)
    assert problems == []
    assert report["overlappingCells"] == {"sw_isle|tollholms": 0, "sw_isle|gull_skerries": 0,
                                          "gull_skerries|tollholms": 0}
    assert report["unownedIslandLandM2"] == 0 and report["islandLandM2"] > 2_000_000
    # the only land left to a future map is the mainland component that runs off the group grid
    assert report["mainlandComponents"] == 1


def test_shared_border_vertices_are_byte_equal(territories, lattice):
    problems, report = T.check_seams(territories, lattice)
    assert problems == []
    east, south = report["sw_isle|tollholms"], report["sw_isle|gull_skerries"]
    # the adjacent-map design's bands: three vertex columns at x 2435-2439, and the L round sw_isle's south-west
    assert (east["sharedVertices"], east["x"], east["z"]) == (2718, [2435.0, 2439.0], [6451.0, 8261.0])
    assert south["sharedVertices"] == 3339
    assert report["gull_skerries|tollholms"] == {"sharedVertices": 0}
    for entry in (east, south):
        assert entry["baseDifferences"] == 0
        assert all(value == 0 for key, value in entry.items() if key.startswith("sculptedShared_"))
        assert entry["waterNearShared"] == []
    assert east["mirroredPatches"] == ["seam-mole-knob", "seam-mole-pier"]
    # no sculpt hides under a mole's Set on either side
    assert (east["sculptUnderMoles_sw_isle"], east["sculptUnderMoles_tollholms"]) == (0, 0)


def test_a_changed_shared_vertex_is_caught(territories, lattice):
    tollholms = by_id(territories, "tollholms")
    heights = tollholms.heights.copy()
    row, column = vertex_index(tollholms, 2437.0, 7001.0)
    heights[row, column] = np.nextafter(heights[row, column], np.float32(np.inf))
    problems, _ = T.check_seams(replaced(territories, "tollholms", heights=heights), lattice)
    assert any("1 shared vertices differ in the base, e.g. (2437, 7001)" in p for p in problems)


def test_a_sculpted_shared_vertex_is_caught(territories, lattice, monkeypatch):
    original = T.sculpt_deltas

    def sculpted(territory):
        deltas, problems = original(territory)
        if territory.id == "gull_skerries":
            deltas = deltas.copy()
            deltas[vertex_index(territory, 1201.0, 8261.0)] = 0.25
        return deltas, problems

    monkeypatch.setattr(T, "sculpt_deltas", sculpted)
    problems, _ = T.check_seams(territories, lattice)
    assert any("gull_skerries sculpts 1 shared vertices" in p for p in problems)


def test_a_sculpt_delta_under_a_mole_is_caught(territories, lattice, monkeypatch):
    original = T.sculpt_deltas

    def sculpted(territory):
        deltas, problems = original(territory)
        if territory.id == "sw_isle":
            deltas = deltas.copy()
            deltas[vertex_index(territory, 2425.0, 7329.0)] = -1.5   # under seam-mole-pier, 12 m off the seam
        return deltas, problems

    monkeypatch.setattr(T, "sculpt_deltas", sculpted)
    problems, report = T.check_seams(territories, lattice)
    assert any("sw_isle sculpts 1 vertices under seam patch seam-mole-pier, e.g. (2425, 7329)" in p for p in problems)
    assert report["sw_isle|tollholms"]["sculptUnderMoles_sw_isle"] == 1


def test_water_near_a_shared_vertex_is_caught(territories, lattice, monkeypatch):
    original = T.water_features

    def with_river(territory):
        features = original(territory)
        if territory.id == "tollholms":
            features = features + [{"kind": "river", "path": "Rivers/test-river",
                                    "xz": np.array([[2445.0, 6700.0], [2441.0, 6720.0]]), "reach": 3.0}]
        return features

    monkeypatch.setattr(T, "water_features", with_river)
    problems, report = T.check_seams(territories, lattice)
    assert any("tollholms's river Rivers/test-river comes within" in p for p in problems)
    assert report["sw_isle|tollholms"]["waterNearShared"] == ["Rivers/test-river"]


def test_an_unmirrored_or_moved_mole_is_caught(territories, lattice):
    tollholms = by_id(territories, "tollholms")
    scene = tollholms.scene
    missing = dataclasses.replace(scene, nodes={key: value for key, value in scene.nodes.items()
                                                if key != "Terrain/Patches/seam-mole-pier"})
    problems, _ = T.check_seams(replaced(territories, "tollholms", scene=missing), lattice)
    assert any("seam-mole-pier touches shared vertices but only sw_isle declares it" in p for p in problems)
    knob = scene.nodes["Terrain/Patches/seam-mole-knob"]
    moved_knob = dataclasses.replace(knob, properties=dict(
        knob.properties, transform="Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, -369, 3, 534)"))
    moved = dataclasses.replace(scene, nodes=dict(scene.nodes, **{"Terrain/Patches/seam-mole-knob": moved_knob}))
    problems, _ = T.check_seams(replaced(territories, "tollholms", scene=moved), lattice)
    assert any("seam-mole-knob is declared differently" in p for p in problems)


def test_overlapping_or_missing_ownership_is_caught(territories, lattice):
    gull = by_id(territories, "gull_skerries")
    wider = [[x + 10.0 if x == 399.0 else x, z] for x, z in gull.polygon]
    problems, _ = T.check_ownership(replaced(territories, "gull_skerries", polygon=wider), lattice)
    assert any("sw_isle and gull_skerries overlap" in p for p in problems)
    without_gull = [t for t in territories if t.id != "gull_skerries"]
    problems, report = T.check_ownership(without_gull, lattice)
    assert report["unownedIslandLandM2"] > 50_000
    assert any("island land vertices are unowned" in p for p in problems)


def test_classify_counts_edges_as_owned_and_interiors_strictly():
    square = [[1.0, 1.0], [5.0, 1.0], [5.0, 5.0], [1.0, 5.0]]
    assert T.classify(np.array([3.0, 1.0, 5.0, 0.0]), np.array([3.0, 3.0, 5.0, 3.0]), square).tolist() == [1, 2, 2, 0]


# --- the published packages and the served frames (serve plan CV9) ---------------------------------------------------

def test_each_catalog_entry_names_its_published_package(territories):
    problems, report = T.check_published(territories)
    assert problems == []
    for region in ("sw_isle", "tollholms", "gull_skerries"):
        assert report[region]["publishedManifestPath"] == \
            f"res://../eloria-assets/maps/continent-v2/{region}/client/world.json"
        assert report[region]["published"]


def served_fixture(root, *, served_grid=True, status="continent-v2-client-preview", origin=(1023, 993),
                   publish=True, row=None):
    """A checkout holding one v2 catalog entry, its registry row and (when `publish`) its client package."""
    resource = "res://../eloria-assets/maps/continent-v2/isle/client/world.json"
    catalog = root / "godot-client" / "world_authoring" / "continent-v2" / "territories.json"
    registry = root / "godot-client" / "data" / "maps" / "registry.json"
    package = root / "eloria-assets" / "maps" / "continent-v2" / "isle" / "client" / "world.json"
    for path in (catalog, registry, package):
        path.parent.mkdir(parents=True, exist_ok=True)
    transform = {"serverOrigin": list(origin), "serverCells": [2046, 2046], "metresPerTile": 1.0,
                 "invertServerY": True}
    catalog.write_text(T.json.dumps({"schema": "eloria-map-authoring-territories-v1", "entries": [
        {"id": "isle", "label": "Isle", "manifestPath": "res://../eloria-assets/maps/continent-v2/isle/world.json",
         "publishedManifestPath": resource}]}), encoding="utf-8")
    registry.write_text(T.json.dumps({"maps": {"isle": {
        "manifest": resource, "status": status, "coordinateTransform": transform,
        "continentGeography": {"translation": [1418.0, 0.0, 7270.0]}, **(row or {})}}}), encoding="utf-8")
    if publish:
        collision = {"cellMetres": 0.5}
        if served_grid:
            collision["servedGrid"] = {"binary": "served-grid.escg.gz", "format": "ESCG-v2"}
        package.write_text(T.json.dumps({"coordinateTransform": transform, "collision": collision,
                                         "continentGeography": {"translation": [1418, 0, 7270]}}), encoding="utf-8")
    return catalog


def test_a_served_territorys_frame_is_frozen(tmp_path):
    same = {"isle": {"origin": [1023, 993], "cells": [2046, 2046], "translation": [1418.0, 0.0, 7270.0]}}
    # a client preview (no served grid, not served in the registry) may still move: D2b moved sw_isle by 30 tiles
    preview = served_fixture(tmp_path / "preview", served_grid=False)
    assert T.served_frames(preview) == {}
    assert T.served_frame_problems({"isle": dict(same["isle"], origin=[1023, 963])}, preview) == []
    # once the package ships a served grid, the frame it was exported in is frozen
    served = served_fixture(tmp_path / "served")
    assert T.served_frames(served)["isle"]["origin"] == [1023, 993]
    assert T.served_frame_problems(same, served) == []
    moved = T.served_frame_problems({"isle": dict(same["isle"], origin=[1023, 963])}, served)
    assert len(moved) == 1 and "server origin would move from [1023, 993] to [1023, 963]" in moved[0]
    assert "position migration" in moved[0]
    resized = T.served_frame_problems({"isle": dict(same["isle"], cells=[2040, 2040])}, served)
    shifted = T.served_frame_problems({"isle": dict(same["isle"], translation=[1418.0, 0.0, 7240.0])}, served)
    assert any("server cells" in p for p in resized) and any("continent translation" in p for p in shifted)
    assert any("has no frame here" in p for p in T.served_frame_problems({}, served))
    # the registry's served status counts too, even before the package is republished
    registered = served_fixture(tmp_path / "registered", served_grid=False, status=T.SERVED_STATUS, publish=False)
    assert "registry row is continent-v2-served" in T.served_frames(registered)["isle"]["why"]
    assert T.served_frame_problems({"isle": dict(same["isle"], origin=[1023, 963])}, registered)


def test_a_served_row_names_the_map_as_the_catalog_does(tmp_path):
    promoted = {"label": "Isle", "landscapeTransitions": True}
    good = served_fixture(tmp_path / "good", status=T.SERVED_STATUS, row=promoted)
    assert T.served_row_problems(good) == []
    # a client preview is not held to it: it may still wait for its server map, unlabelled
    preview = served_fixture(tmp_path / "preview", row={"requiresServerMap": "not published on the server yet"})
    assert T.served_row_problems(preview) == []
    renamed = served_fixture(tmp_path / "renamed", status=T.SERVED_STATUS, row=dict(promoted, label="Sw Isle"))
    assert ["isle: the served registry row's label 'Sw Isle' is not the catalog's 'Isle'"] ==         T.served_row_problems(renamed)
    unlabelled = served_fixture(tmp_path / "unlabelled", status=T.SERVED_STATUS, row={"landscapeTransitions": True})
    assert any("label None" in p for p in T.served_row_problems(unlabelled))
    walled = served_fixture(tmp_path / "walled", status=T.SERVED_STATUS, row=dict(promoted, landscapeTransitions=False))
    assert any("landscapeTransitions is False" in p for p in T.served_row_problems(walled))
    waiting = served_fixture(tmp_path / "waiting", status=T.SERVED_STATUS,
                             row=dict(promoted, requiresServerMap="2046x2046 server tiles"))
    assert any("still says it requires a server map" in p for p in T.served_row_problems(waiting))


def test_served_packages_from_another_export_run_are_caught(tmp_path):
    catalog = served_fixture(tmp_path / "run")
    package = tmp_path / "run" / "eloria-assets" / "maps" / "continent-v2" / "isle" / "client" / "world.json"
    manifest = T.json.loads(package.read_text(encoding="utf-8"))
    own = {"snapshotSha256": "a" * 64, "servedGridSha256": "b" * 64}
    manifest["collision"].update(sourceSnapshotSha256=own["snapshotSha256"], groupExport={"maps": {"isle": own}})
    manifest["collision"]["servedGrid"]["sha256"] = own["servedGridSha256"]
    package.write_text(T.json.dumps(manifest), encoding="utf-8")
    assert T.served_group_problems(catalog) == []
    manifest["collision"]["groupExport"]["maps"]["isle"]["servedGridSha256"] = "c" * 64
    package.write_text(T.json.dumps(manifest), encoding="utf-8")
    assert ["another export run" in p for p in T.served_group_problems(catalog)] == [True]
    # a preview without a served grid is not held to it
    assert T.served_group_problems(served_fixture(tmp_path / "preview", served_grid=False)) == []


def test_the_committed_frames_are_not_moved(territories):
    stubs = {t.id: {"origin": t.manifest["server"]["origin"], "cells": t.manifest["server"]["cells"],
                    "translation": list(t.translation)} for t in territories}
    assert T.served_frame_problems(stubs) == []

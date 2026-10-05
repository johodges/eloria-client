extends SceneTree
## Serve plan CV9: the editor finds a continent-v2 territory's published package
## through its catalog entry's publishedManifestPath, and the play-test walker
## walks the served grid that package ships. The entry's manifestPath stays the
## bootstrap's stub (frame, ownership, environment), which never carries one.
##
## Fixtures: an isolated catalog, bound with the project setting
## map_authoring/territory_catalog_path for this run only, whose v2 entry names a
## stub and a package shipping the server's golden served grid. manifest_path_for
## gives the stub, published_manifest_path_for the package, and load_grid on a
## scene root of that region (no manifest argument) walks the package's grid:
## format 2, climb 20. A legacy entry (no publishedManifestPath) publishes its
## manifest; an unpublished v2 entry has no package; a territory the bound
## catalog does not list comes from the shared catalog.
##
## Repository: the v2 catalog names each isle's client package, the one its
## registry row names. Once sw_isle's committed package ships a served grid
## (serve plan CV10), the walker loads it through the v2 catalog: 2046 x 2046
## tiles, format 2, climb 20, in the scene's frame (1023, 993). Until then that
## case prints WAITING. ELORIA_V2_PUBLISHED_PACKAGES=<folder holding
## sw_isle/client/world.json> runs it on a package outside the checkout (the CV5
## and CV6 trial packages) through an isolated copy of the v2 catalog.
##
## Godot_v4.7.2-stable_win64_console.exe --headless --path . \
##     --script res://tests/test_map_authoring_v2_published.gd

const Walker := preload("res://addons/map_authoring_usability/playtest_walker.gd")
const TimeOfDay := preload("res://addons/map_authoring_usability/time_of_day_preview.gd")
const Catalog := preload("res://addons/map_authoring_workspace/territory_catalog.gd")
const REGION := preload("res://src/dev/map_authoring_region/region_control.gd")
const SETTING := "map_authoring/territory_catalog_path"
const GOLDEN_PATH := "res://tests/fixtures/served_grid_golden.escg.gz"
const GOLDEN_SHA256 := "7e4522023885486b2a47298826b3fad1d30ba6d660dcc80249c8690d30e66c12"
const FIXTURE := "res://test-artifacts/v2-published"
const V2_CATALOG := "res://world_authoring/continent-v2/territories.json"
const REGISTRY := "res://data/maps/registry.json"
const SW_ISLE_PACKAGE := "res://../eloria-assets/maps/continent-v2/sw_isle/client/world.json"
const SW_ISLE_STUB := "res://../eloria-assets/maps/continent-v2/sw_isle/world.json"
const PACKAGES_ENV := "ELORIA_V2_PUBLISHED_PACKAGES"

var failures := 0
var _had_setting := false
var _saved_setting: Variant = null


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	_had_setting = ProjectSettings.has_setting(SETTING)
	_saved_setting = ProjectSettings.get_setting(SETTING) if _had_setting else null
	_test_fixture_catalog()
	_test_repository_catalog()
	_restore_setting()
	_finish()


func _test_fixture_catalog() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(FIXTURE + "/isle/client"))
	var stub := FIXTURE + "/isle/world.json"
	var package := FIXTURE + "/isle/client/world.json"
	var legacy := FIXTURE + "/legacy/world.json"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(FIXTURE + "/legacy"))
	_write_json(stub, {"asset": {"id": "v2_fixture"}, "server": {"origin": [5, 7], "cells": [24, 16]}})
	_write_json(package, {"asset": {"id": "v2_fixture"}, "coordinateTransform": {"serverOrigin": [5, 7],
		"serverCells": [24, 16], "metresPerTile": 1.0, "invertServerY": true},
		"collision": {"binary": "collision.bin", "servedGrid": {"binary": "served-grid.escg.gz",
			"format": "ESCG-v2", "unitMetres": 0.05, "climbMetres": 1.0, "originMetres": -100.0,
			"sha256": GOLDEN_SHA256}}})
	_write_bytes(FIXTURE + "/isle/client/served-grid.escg.gz", FileAccess.get_file_as_bytes(GOLDEN_PATH))
	_write_json(legacy, {"asset": {"id": "legacy_fixture"}})
	var catalog := FIXTURE + "/territories.json"
	_write_json(catalog, {"schema": Catalog.SCHEMA, "entries": [
		{"id": "v2_fixture", "label": "V2 Fixture", "manifestPath": stub, "publishedManifestPath": package},
		{"id": "v2_unpublished", "label": "V2 Unpublished", "manifestPath": stub,
			"publishedManifestPath": FIXTURE + "/absent/client/world.json"},
		{"id": "legacy_fixture", "label": "Legacy Fixture", "manifestPath": legacy}]})
	ProjectSettings.set_setting(SETTING, catalog)
	_expect(Catalog.configured_path() == catalog,
		"the project setting binds the isolated catalog for this run")
	_expect(TimeOfDay.manifest_path_for("v2_fixture") == stub and
		TimeOfDay.published_manifest_path_for("v2_fixture") == package,
		"a v2 entry's manifest is its stub, its published package the publishedManifestPath")
	_expect(TimeOfDay.published_manifest_path_for("legacy_fixture") == legacy and
		TimeOfDay.manifest_path_for("legacy_fixture") == legacy,
		"a legacy entry, with no publishedManifestPath, publishes its manifest")
	_expect(TimeOfDay.published_manifest_path_for("v2_unpublished") == "" and
		TimeOfDay.manifest_path_for("v2_unpublished") == stub,
		"an unpublished v2 entry has no package, and its stub never stands in for one")
	var shared := TimeOfDay.manifest_path_for("sunmane_steppe")
	_expect(not shared.is_empty() and TimeOfDay.published_manifest_path_for("sunmane_steppe") == shared,
		"a territory the bound catalog does not list comes from the shared catalog (%s)" % shared)
	var root: Node3D = REGION.new()
	root.name = "V2PublishedFixture"
	root.set("region_id", "v2_fixture")
	root.set("server_origin", Vector2i(5, 7))
	get_root().add_child(root)
	var grid := Walker.load_grid(root)
	_expect(not grid.has("error") and String(grid.get("source", "")) == "published" and
		int(grid.get("format", 0)) == 2 and int(grid.get("climb", 0)) == 20 and
		int(grid.get("width", 0)) == 24 and int(grid.get("rows", 0)) == 16 and
		String(grid.get("served_grid", "")).begins_with(FIXTURE + "/isle/client/"),
		"with no manifest argument the walker walks the package's served grid: format 2, climb 20 (%s)" %
			String(grid.get("error", grid.get("served_grid", ""))))
	root.queue_free()


func _test_repository_catalog() -> void:
	var catalog: Variant = JSON.parse_string(FileAccess.get_file_as_string(V2_CATALOG))
	var registry: Variant = JSON.parse_string(FileAccess.get_file_as_string(REGISTRY))
	if not _expect(catalog is Dictionary and registry is Dictionary, "the v2 catalog and the registry parse"):
		return
	var named := 0
	var entries: Array = (catalog as Dictionary).get("entries", [])
	for entry: Dictionary in entries:
		var row: Dictionary = ((registry as Dictionary).get("maps", {}) as Dictionary).get(String(entry.id), {})
		var published := String(entry.get("publishedManifestPath", ""))
		if not published.is_empty() and published == String(row.get("manifest", "")) and \
				published.ends_with("/%s/client/world.json" % String(entry.id)) and FileAccess.file_exists(published):
			named += 1
	_expect(entries.size() == 3 and named == 3,
		"every v2 catalog entry names its client package, the registry row's manifest (%d of %d)" % [named,
			entries.size()])
	ProjectSettings.set_setting(SETTING, V2_CATALOG)
	_expect(TimeOfDay.published_manifest_path_for("sw_isle") == SW_ISLE_PACKAGE and
		TimeOfDay.manifest_path_for("sw_isle") == SW_ISLE_STUB,
		"bound to the v2 catalog, sw_isle's package is client/world.json and its manifest the stub")
	var stub: Variant = JSON.parse_string(FileAccess.get_file_as_string(SW_ISLE_STUB))
	var origin := Vector2i(1023, 993)
	if stub is Dictionary:
		var frame: Array = ((stub as Dictionary).get("server", {}) as Dictionary).get("origin", [])
		if frame.size() == 2:
			origin = Vector2i(int(frame[0]), int(frame[1]))
	var outside := OS.get_environment(PACKAGES_ENV).strip_edges()
	if not outside.is_empty():
		var copy := FIXTURE + "/v2-catalog-outside.json"
		var bound: Dictionary = (catalog as Dictionary).duplicate(true)
		for entry: Dictionary in bound.entries:
			entry["publishedManifestPath"] = outside.path_join(String(entry.id)).path_join("client/world.json")
		_write_json(copy, bound)
		ProjectSettings.set_setting(SETTING, copy)
		print("sw_isle package from %s: %s" % [PACKAGES_ENV, TimeOfDay.published_manifest_path_for("sw_isle")])
	var package := TimeOfDay.published_manifest_path_for("sw_isle")
	var manifest: Variant = JSON.parse_string(FileAccess.get_file_as_string(package)) if not package.is_empty() \
		else null
	var declared := manifest is Dictionary and (((manifest as Dictionary).get("collision", {}) as Dictionary)
		.get("servedGrid") is Dictionary)
	if not declared:
		print("WAITING: sw_isle's package %s ships no served grid yet (serve plan CV10 publishes it)" % package)
		return
	var root: Node3D = REGION.new()
	root.name = "SwIslePublished"
	root.set("region_id", "sw_isle")
	root.set("server_origin", origin)
	get_root().add_child(root)
	var began := Time.get_ticks_msec()
	var grid := Walker.load_grid(root)
	_expect(not grid.has("error") and String(grid.get("source", "")) == "published" and
		int(grid.get("format", 0)) == 2 and int(grid.get("climb", 0)) == 20 and
		int(grid.get("width", 0)) == 2046 and int(grid.get("rows", 0)) == 2046 and
		grid.get("origin") == Vector2i(1023, 993) and
		String(grid.get("served_grid", "")).get_base_dir() == package.get_base_dir(),
		"on the v2 catalog the walker loads sw_isle's served grid: 2046 x 2046, format 2, climb 20, origin %s, in %d ms (%s)" %
			[str(origin), Time.get_ticks_msec() - began, String(grid.get("error", grid.get("served_grid", "")))])
	root.queue_free()


func _restore_setting() -> void:
	ProjectSettings.set_setting(SETTING, _saved_setting if _had_setting else null)


func _write_json(path: String, value: Variant) -> void:
	var file := FileAccess.open(path, FileAccess.WRITE)
	file.store_string(JSON.stringify(value))
	file.close()


func _write_bytes(path: String, bytes: PackedByteArray) -> void:
	var file := FileAccess.open(path, FileAccess.WRITE)
	file.store_buffer(bytes)
	file.close()


func _expect(condition: bool, message: String) -> bool:
	if condition:
		print("PASS: ", message)
		return true
	failures += 1
	push_error("FAIL: " + message)
	return false


func _finish() -> void:
	print("map authoring v2 published: ", "PASS" if failures == 0 else "FAIL (%d)" % failures)
	quit(failures)

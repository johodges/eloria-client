extends SceneTree

const PILOT := preload("res://src/dev/map_authoring_pilot/map_authoring_pilot.tscn")

var _failures := 0


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var pilot: Node = PILOT.instantiate()
	root.add_child(pilot)
	await process_frame
	await process_frame

	var before: Dictionary = pilot.authored_snapshot()
	var refresh_started := Time.get_ticks_usec()
	pilot.refresh_all()
	await process_frame
	var refresh_ms := float(Time.get_ticks_usec() - refresh_started) / 1000.0
	print("map authoring pilot refresh_ms=%.2f" % refresh_ms)
	_expect(pilot.authored_snapshot() == before,
		"refresh leaves every saved authored control unchanged")
	_expect(pilot.get_node("GeneratedPreview/Terrain") != null,
		"refresh creates a disposable terrain preview")
	_expect(pilot.get_node("GeneratedPreview/Terrain").owner == null,
		"generated preview is not scene-owned")
	var fixture_root := "res://src/dev/map_authoring_pilot/example_export"
	var fresh_root := "res://src/dev/map_authoring_pilot/.smoke-export"
	pilot.export_directory = fresh_root
	pilot.export_contract()
	_expect(FileAccess.file_exists(fresh_root + "/collision.bin"),
		"the example EWCG export is written")
	_expect(FileAccess.file_exists(fresh_root + "/world.json"),
		"the example manifest is written")
	_expect(FileAccess.get_file_as_bytes(fresh_root + "/collision.bin") ==
		FileAccess.get_file_as_bytes(fixture_root + "/collision.bin"),
		"the checked EWCG fixture matches a pristine scene export")
	_expect(JSON.parse_string(FileAccess.get_file_as_string(fresh_root + "/world.json")) ==
		JSON.parse_string(FileAccess.get_file_as_string(fixture_root + "/world.json")),
		"the checked manifest matches a pristine scene export")
	DirAccess.remove_absolute(ProjectSettings.globalize_path(fresh_root + "/collision.bin"))
	DirAccess.remove_absolute(ProjectSettings.globalize_path(fresh_root + "/world.json"))
	DirAccess.remove_absolute(ProjectSettings.globalize_path(fresh_root))
	pilot.start_walk()
	var walker: MeshInstance3D = pilot.get_node("LocalWalker") as MeshInstance3D
	var spawn_position := walker.position
	walker.position = Vector3(22.0, 9.0, 22.0)
	pilot.start_walk()
	_expect(walker.position == spawn_position,
		"starting again first returns the local walker to the spawn")

	var building: Node3D = pilot.get_node("AuthoredControls/Building")
	building.position += Vector3(0.0, 0.0, 1.0)
	var moved := building.transform
	pilot.refresh_selected()
	await process_frame
	_expect(building.transform == moved,
		"an authored transform survives regeneration exactly")

	var road: Path3D = pilot.get_node("AuthoredControls/Road")
	var edited_point := road.curve.get_point_position(1) + Vector3(0.0, 0.0, 0.5)
	road.curve.set_point_position(1, edited_point)
	pilot.refresh_all()
	await process_frame
	_expect(road.curve.get_point_position(1) == edited_point,
		"an authored curve edit survives regeneration exactly")
	var packed := PackedScene.new()
	_expect(packed.pack(pilot) == OK, "the edited authoring scene can be packed")
	var reload_path := "res://src/dev/map_authoring_pilot/example_export/reload-smoke.tscn"
	var save_error := ResourceSaver.save(packed, reload_path)
	_expect(save_error == OK, "the edited scene can be saved")
	if save_error != OK:
		quit(_failures)
		return
	var reopened_resource: PackedScene = ResourceLoader.load(reload_path, "PackedScene",
		ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
	var reopened: Node = reopened_resource.instantiate()
	_expect((reopened.get_node("AuthoredControls/Building") as Node3D).transform == moved,
		"the authored building transform survives save and reopen")
	_expect((reopened.get_node("AuthoredControls/Road") as Path3D).curve.get_point_position(1) == edited_point,
		"the authored road curve survives save and reopen")
	reopened.free()
	DirAccess.remove_absolute(ProjectSettings.globalize_path(reload_path))

	var grid: PackedByteArray = pilot.server_grid()
	_expect(grid.size() == 48 * 48, "the preview uses the 48 x 48 conservative server grid")
	var route: Array[Vector2i] = pilot.validation_route()
	_expect(route.size() > 20, "the entrance is reached across the local bridge")
	var every_step_legal := true
	if route.size() > 1:
		for index in route.size() - 1:
			var a: Vector2i = route[index]
			var b: Vector2i = route[index + 1]
			var ah := int(grid[a.y * 48 + a.x])
			var bh := int(grid[b.y * 48 + b.x])
			every_step_legal = every_step_legal and ah > 0 and bh > 0 and absi(ah - bh) <= 2
	_expect(every_step_legal, "every preview route step is legal in the exported server grid")

	print("map authoring pilot: ", "PASS" if _failures == 0 else "FAIL (%d)" % _failures)
	pilot.queue_free()
	quit(_failures)


func _expect(condition: bool, message: String) -> bool:
	if condition:
		print("PASS: ", message)
		return true
	_failures += 1
	push_error("FAIL: " + message)
	return false

extends SceneTree

const SESSION_TIMEOUT_SECONDS := 45.0
const SCREEN_SIZE := Vector2i(1280, 720)

var _failures := 0
var _artifact_directory := ""
var _app_state: Node
var _network: Node

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	_artifact_directory = OS.get_environment("ELORIA_ARTIFACT_DIR")
	if _artifact_directory.is_empty():
		_artifact_directory = ProjectSettings.globalize_path("res://test-artifacts")
	var directory_error: Error = DirAccess.make_dir_recursive_absolute(_artifact_directory)
	_expect(directory_error == OK, "artifact directory is writable")
	root.size = SCREEN_SIZE
	var scene_resource: Resource = load("res://src/app/main.tscn")
	_expect(scene_resource is PackedScene, "main scene loads")
	if not scene_resource is PackedScene:
		_finish()
		return
	var main: Control = (scene_resource as PackedScene).instantiate() as Control
	root.add_child(main)
	await process_frame
	_app_state = root.get_node("AppState")
	_network = root.get_node("Network")

	var host: String = OS.get_environment("ELORIA_INTEGRATION_HOST")
	if host.is_empty():
		host = "18.235.240.60"
	var port_text: String = OS.get_environment("ELORIA_INTEGRATION_PORT")
	var port: int = int(port_text) if port_text.is_valid_int() else 2000
	var suffix: String = _random_hex(5)
	var username: String = "Render" + suffix
	var password: String = _random_hex(24)

	var host_edit: LineEdit = main.get_node("LoginPanel/Content/Host") as LineEdit
	var port_edit: SpinBox = main.get_node("LoginPanel/Content/Port") as SpinBox
	host_edit.text = host
	port_edit.value = port
	main.call("_on_connect_pressed")
	var connected: Callable = func() -> bool:
		return str(_app_state.get("connection_state")) == "connected"
	if not await _wait_for(connected, SESSION_TIMEOUT_SECONDS):
		_fail("development server connection timed out")
		_finish()
		return

	main.call("_on_new_character_pressed")
	var name_edit: LineEdit = main.get_node(
		"CreationPanel/Columns/Form/CreateName") as LineEdit
	var password_edit: LineEdit = main.get_node(
		"CreationPanel/Columns/Form/CreatePassword") as LineEdit
	var confirm_edit: LineEdit = main.get_node(
		"CreationPanel/Columns/Form/CreateConfirm") as LineEdit
	name_edit.text = username
	password_edit.text = password
	confirm_edit.text = password
	main.call("_on_create_pressed")
	var authenticated: Callable = func() -> bool:
		return bool(_app_state.get("authenticated"))
	if not await _wait_for(authenticated, SESSION_TIMEOUT_SECONDS):
		_fail("character creation/login timed out")
		_finish()
		return

	var world_loader: WorldLoader = main.get_node(
		"GameView/ViewportContainer/Viewport/WorldRoot/WorldLoader") as WorldLoader
	var presentation_ready: Callable = func() -> bool:
		var local_id: int = int(_app_state.get("local_actor_id"))
		return (not str(_app_state.get("current_map")).is_empty() and local_id >= 0
			and (main.get("actor_nodes") as Dictionary).has(local_id)
			and world_loader.world_root != null)
	if not await _wait_for(presentation_ready, SESSION_TIMEOUT_SECONDS):
		_fail("authoritative map/local actor presentation timed out")
		_finish()
		return
	for unused_frame: int in range(8):
		await physics_frame
		await process_frame

	var actor_nodes: Dictionary = main.get("actor_nodes") as Dictionary
	var local_actor_id: int = int(_app_state.get("local_actor_id"))
	var actors: Dictionary = _app_state.get("actors") as Dictionary
	var actor: ReplicatedActor3D = actor_nodes.get(local_actor_id) as ReplicatedActor3D
	var local_dto: Dictionary = actors.get(local_actor_id, {}) as Dictionary
	var native_model: Node3D = actor.get_node_or_null("NativeModel") as Node3D
	var fallback: Node = actor.get_node_or_null("MissingModelFallback")
	var visible_native_meshes: int = _visible_native_mesh_count(native_model)
	_expect(native_model != null and fallback == null and visible_native_meshes >= 3,
		"local player uses the visible native luminous GLB")

	var gameplay_world: World3D = main.get("gameplay_world") as World3D
	_expect(gameplay_world != null, "gameplay World3D is non-null")
	var surface_hit: Dictionary = _surface_hit(gameplay_world, actor.server_target)
	var surface_position_value: Variant = surface_hit.get("position")
	_expect(surface_position_value is Vector3, "navigation surface exists below server spawn")
	if surface_position_value is Vector3:
		var surface_position: Vector3 = surface_position_value as Vector3
		_expect(absf(actor.global_position.y - (surface_position.y + 0.02)) < 0.04,
			"actor foot is aligned to the sampled navigation surface")

	var camera: Camera3D = main.get_node(
		"GameView/ViewportContainer/Viewport/WorldRoot/CameraRig/Camera") as Camera3D
	var actor_focus: Vector3 = actor.global_position + Vector3.UP
	var actor_screen: Vector2 = camera.unproject_position(actor_focus)
	var actor_feet_screen: Vector2 = camera.unproject_position(actor.global_position)
	var actor_head_screen: Vector2 = camera.unproject_position(
		actor.global_position + Vector3.UP * 1.78)
	var actor_pixel_height: float = absf(actor_head_screen.y - actor_feet_screen.y)
	_expect(not camera.is_position_behind(actor_focus)
		and Rect2(Vector2.ZERO, Vector2(SCREEN_SIZE)).has_point(actor_screen),
		"local actor is inside the gameplay camera frame")
	_expect(actor_pixel_height >= 24.0,
		"native actor remains readable at the default camera framing")
	var marker: MeshInstance3D = main.get_node(
		"GameView/ViewportContainer/Viewport/WorldRoot/PlayerMapMarker") as MeshInstance3D
	var marker_mesh: CylinderMesh = marker.mesh as CylinderMesh
	_expect(marker.visible and Vector2(marker.global_position.x, marker.global_position.z).distance_to(
		Vector2(actor.global_position.x, actor.global_position.z)) < 0.01,
		"white local-player marker follows the actor")
	_expect(marker_mesh != null and marker_mesh.top_radius >= 5.0,
		"white local-player marker is legible at the full-map scale")
	var map_camera: Camera3D = main.get_node("GameView/MapViewport/MapCamera") as Camera3D
	var full_map_camera: Camera3D = main.get_node(
		"GameView/FullMapViewport/FullMapCamera") as Camera3D
	var camera_rig: IsometricCameraController = main.get_node(
		"GameView/ViewportContainer/Viewport/WorldRoot/CameraRig") as IsometricCameraController
	_expect((map_camera.cull_mask & 4) != 0 and (full_map_camera.cull_mask & 4) != 0,
		"minimap and full-map cameras both render the player marker")

	var evidence: Dictionary = {
		"server_map": str(_app_state.get("current_map")),
		"local_actor_id": local_actor_id,
		"spawn_dto": _json_safe(local_dto),
		"server_tile": [int(local_dto.get("x", -1)), int(local_dto.get("y", -1))],
		"converted_godot_position": str(actor.server_target),
		"navigation_surface_hit": _json_safe(surface_hit),
		"final_actor_position": str(actor.global_position),
		"render": _json_safe(actor.render_diagnostics()),
		"native_visible_meshes": visible_native_meshes,
		"camera_focus_screen": str(actor_screen),
		"actor_projected_height_pixels": actor_pixel_height,
		"camera": _json_safe(camera_rig.camera_diagnostics()),
		"credentials": "REDACTED",
	}
	_write_json("session.json", evidence)
	await _capture("world-default.png")

	var full_map: Control = main.get_node("GameView/FullMap") as Control
	main.call("_on_map_button_pressed")
	await process_frame
	await _capture("world-full-map.png")
	full_map.hide()

	var initial_tile := Vector2i(int(local_dto.get("x", 0)), int(local_dto.get("y", 0)))
	var click_sent: bool = await _send_real_world_click(main, camera, initial_tile)
	_expect(click_sent, "viewport click produced an authoritative actor tile update")
	if click_sent:
		for unused_frame: int in range(8):
			await physics_frame
			await process_frame
		actors = _app_state.get("actors") as Dictionary
		var resulting_dto: Dictionary = actors.get(local_actor_id, {}) as Dictionary
		var resulting_actor: ReplicatedActor3D = (
			main.get("actor_nodes") as Dictionary).get(
			local_actor_id) as ReplicatedActor3D
		var movement_evidence: Dictionary = {
			"initial_tile": [initial_tile.x, initial_tile.y],
			"resulting_tile": [int(resulting_dto.get("x", -1)),
				int(resulting_dto.get("y", -1))],
			"resulting_actor_position": str(resulting_actor.global_position),
			"actor_yaw_radians": resulting_actor.rotation.y,
			"camera": _json_safe(camera_rig.camera_diagnostics()),
			"credentials": "REDACTED",
		}
		_write_json("movement.json", movement_evidence)
		await _capture("world-after-move.png")

	_network.call("disconnect_from_server")
	print("rendered server session: ", "PASS" if _failures == 0 else "FAIL")
	print("credentials: REDACTED")
	_finish()

func _send_real_world_click(main: Control, camera: Camera3D,
		initial_tile: Vector2i) -> bool:
	var adapter: CoordinateAdapter = main.get("adapter") as CoordinateAdapter
	var offsets: Array[Vector2i] = [Vector2i(4, 0), Vector2i(-4, 0),
		Vector2i(0, 4), Vector2i(0, -4)]
	for offset: Vector2i in offsets:
		var target_tile: Vector2i = initial_tile + offset
		var target_world: Vector3 = adapter.tile_center(target_tile.x, target_tile.y)
		var gameplay_world: World3D = main.get("gameplay_world") as World3D
		var hit: Dictionary = _surface_hit(gameplay_world, target_world)
		var hit_value: Variant = hit.get("position")
		if not hit_value is Vector3:
			continue
		target_world = hit_value as Vector3
		if camera.is_position_behind(target_world):
			continue
		var viewport_position: Vector2 = camera.unproject_position(target_world)
		if not Rect2(Vector2(8.0, 8.0), Vector2(SCREEN_SIZE) - Vector2(16.0, 16.0)).has_point(
				viewport_position):
			continue
		var click: InputEventMouseButton = InputEventMouseButton.new()
		click.button_index = MOUSE_BUTTON_LEFT
		click.pressed = true
		click.position = viewport_position
		main.call("_on_world_gui_input", click)
		var actor_tile_changed: Callable = func() -> bool:
			var local_id: int = int(_app_state.get("local_actor_id"))
			var actors: Dictionary = _app_state.get("actors") as Dictionary
			var dto: Dictionary = actors.get(local_id, {}) as Dictionary
			return Vector2i(int(dto.get("x", initial_tile.x)),
				int(dto.get("y", initial_tile.y))) != initial_tile
		var changed: bool = await _wait_for(actor_tile_changed, 8.0)
		if changed:
			return true
		# Restore focus before trying another reachable direction.
		main.call("_update_local_actor_follow")
	return false

func _surface_hit(world: World3D, target: Vector3) -> Dictionary:
	if world == null:
		return {}
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(
		Vector3(target.x, 400.0, target.z), Vector3(target.x, -100.0, target.z),
		WorldLoader.NAVIGATION_SURFACE_LAYER)
	return world.direct_space_state.intersect_ray(query)

func _visible_native_mesh_count(native_model: Node3D) -> int:
	if native_model == null:
		return 0
	var count := 0
	for node_value: Node in native_model.find_children("*", "MeshInstance3D", true, false):
		var mesh_node: MeshInstance3D = node_value as MeshInstance3D
		if mesh_node.mesh != null and mesh_node.is_visible_in_tree() and mesh_node.layers != 0:
			count += 1
	return count

func _wait_for(predicate: Callable, timeout_seconds: float) -> bool:
	var deadline_msec: int = Time.get_ticks_msec() + roundi(timeout_seconds * 1000.0)
	while Time.get_ticks_msec() < deadline_msec:
		if bool(predicate.call()):
			return true
		await process_frame
	return bool(predicate.call())

func _capture(file_name: String) -> void:
	await process_frame
	await process_frame
	RenderingServer.force_draw(false)
	var image: Image = root.get_texture().get_image()
	_expect(not image.is_empty() and image.get_size() == SCREEN_SIZE,
		"rendered screenshot has the reference dimensions")
	var sampled_colors: Dictionary = {}
	for y: int in range(0, image.get_height(), 24):
		for x: int in range(0, image.get_width(), 24):
			sampled_colors[image.get_pixel(x, y).to_html()] = true
	_expect(sampled_colors.size() >= 24, "rendered screenshot is not a blank/dummy frame")
	var result: Error = image.save_png(_artifact_directory.path_join(file_name))
	_expect(result == OK, "saved " + file_name)

func _write_json(file_name: String, value: Dictionary) -> void:
	var file: FileAccess = FileAccess.open(
		_artifact_directory.path_join(file_name), FileAccess.WRITE)
	if file == null:
		_fail("could not open " + file_name)
		return
	file.store_string(JSON.stringify(value, "  "))
	file.close()

func _json_safe(value: Variant) -> Variant:
	if value is Dictionary:
		var converted: Dictionary = {}
		for key_value: Variant in value:
			converted[str(key_value)] = _json_safe((value as Dictionary)[key_value])
		return converted
	if value is Array:
		var converted_array: Array = []
		for item: Variant in value as Array:
			converted_array.append(_json_safe(item))
		return converted_array
	if value is Vector2 or value is Vector2i or value is Vector3 or value is Vector3i:
		return str(value)
	if value is Transform3D or value is Basis or value is AABB:
		return str(value)
	return value

func _random_hex(byte_count: int) -> String:
	var crypto: Crypto = Crypto.new()
	return crypto.generate_random_bytes(byte_count).hex_encode()

func _expect(condition: bool, message: String) -> void:
	if condition:
		print("PASS: ", message)
	else:
		_fail(message)

func _fail(message: String) -> void:
	_failures += 1
	push_error("FAIL: " + message)

func _finish() -> void:
	quit(_failures)

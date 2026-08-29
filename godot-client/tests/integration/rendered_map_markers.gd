extends SceneTree
## Rendered evidence for server-placed map markers.
##
## The "before" frame is the full map with the marker packet already reduced
## into state but the map named as somewhere else - which is exactly what the
## shipped client did with every marker, because nothing decoded command 90 at
## all. The "after" frame is the same map once the marker belongs to it.
##
## Markers draw on the map-camera layer only, so the gameplay view is captured
## as well to show that a navigation aid does not become scenery.

const SCREEN_SIZE := Vector2i(1280, 720)

var _artifacts := ""
var _failures := 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	_artifacts = OS.get_environment("ELORIA_ARTIFACT_DIR")
	if _artifacts.is_empty():
		_artifacts = ProjectSettings.globalize_path("res://test-artifacts/phase2")
	_expect(DirAccess.make_dir_recursive_absolute(_artifacts) == OK,
		"artifact directory is writable")
	root.size = SCREEN_SIZE

	var main: Control = (load("res://src/app/main.tscn") as PackedScene).instantiate() as Control
	root.add_child(main)
	await process_frame
	(main.get_node("GameView") as Control).show()
	(main.get_node("LoginPanel") as Control).hide()
	var app_state: Node = root.get_node("/root/AppState")
	app_state.set("authenticated", true)

	# A plain lit ground so the top-down cameras have something to render.
	var stage: Node3D = main.get_node(
		"GameView/ViewportContainer/Viewport/WorldRoot") as Node3D
	var ground_mesh := PlaneMesh.new()
	ground_mesh.size = Vector2(120.0, 120.0)
	var ground_material := StandardMaterial3D.new()
	ground_material.albedo_color = Color(0.29, 0.35, 0.24)
	ground_mesh.material = ground_material
	var ground := MeshInstance3D.new()
	ground.mesh = ground_mesh
	stage.add_child(ground)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-52.0, 38.0, 0.0)
	stage.add_child(sun)
	for _settle: int in range(4):
		await process_frame

	app_state.call("_on_packet", 7, _nul("./maps/four_gates.elm"))
	for _settle: int in range(4):
		await process_frame

	# A marker the server placed on another map: held, and drawn nowhere.
	# Tile (6, 4): a marker beside the player, where a top-down map can show it.
	var elsewhere := PackedByteArray([0xea, 0x01, 0x06, 0x00, 0x04, 0x00])
	elsewhere.append_array(_nul("./maps/somewhere_else.elm"))
	elsewhere.append_array(_nul("Reed bank"))
	app_state.call("_on_packet", 90, elsewhere)
	main.call("_on_map_button_pressed")
	for _settle: int in range(8):
		await process_frame
	var markers: Dictionary = main.get("map_marker_nodes") as Dictionary
	_expect(markers.is_empty(),
		"a marker for another map is drawn nowhere")
	await _capture("map-marker-before.png",
		"the full map with the marker packet reduced but belonging elsewhere -"
			+ " which is what every marker looked like before command 90 decoded")

	var here := PackedByteArray([0xea, 0x01, 0x06, 0x00, 0x04, 0x00])
	here.append_array(_nul("./maps/four_gates.elm"))
	here.append_array(_nul("Reed bank"))
	app_state.call("_on_packet", 90, here)
	for _settle: int in range(8):
		await process_frame
	markers = main.get("map_marker_nodes") as Dictionary
	_expect(markers.size() == 1, "the marker is drawn on the map it belongs to")
	await _capture("map-marker-full-map.png",
		"the same map with the server's waypoint marker and its label")

	main.call("_on_map_button_pressed")
	for _settle: int in range(6):
		await process_frame
	await _capture("map-marker-gameplay-view.png",
		"the gameplay view: a navigation aid stays on the map cameras rather"
			+ " than becoming a pin over the world")

	app_state.call("_on_packet", 91, PackedByteArray([0xea, 0x01]))
	for _settle: int in range(4):
		await process_frame
	_expect((main.get("map_marker_nodes") as Dictionary).is_empty(),
		"the server takes the marker away again")

	app_state.set("authenticated", false)
	main.queue_free()
	await process_frame
	print("rendered map markers: ",
		"PASS" if _failures == 0 else "FAIL (%d)" % _failures)
	quit(_failures)

func _nul(value: String) -> PackedByteArray:
	var bytes: PackedByteArray = value.to_utf8_buffer()
	bytes.append(0)
	return bytes

func _capture(name: String, description: String) -> void:
	await process_frame
	var image: Image = root.get_texture().get_image()
	_expect(image != null and image.get_size() == SCREEN_SIZE,
		"%s is a full %dx%d frame" % [name, SCREEN_SIZE.x, SCREEN_SIZE.y])
	if image == null:
		return
	_expect(_has_colour_variation(image),
		"%s contains rendered colour variation rather than a dummy frame" % name)
	_expect(image.save_png(_artifacts.path_join(name)) == OK,
		"%s is written" % name)
	print("capture ", name, ": ", description)

func _has_colour_variation(image: Image) -> bool:
	var lowest := 2.0
	var highest := -1.0
	for y: int in range(0, image.get_height(), 8):
		for x: int in range(0, image.get_width(), 8):
			var luminance: float = image.get_pixel(x, y).get_luminance()
			lowest = minf(lowest, luminance)
			highest = maxf(highest, luminance)
	return highest - lowest > 0.02

func _expect(value: bool, label: String) -> bool:
	if not value:
		_failures += 1
		push_error("FAIL: " + label)
	return value

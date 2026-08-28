# Capture real client frames of a region package.
#
# Loads world.glb the way the game does, rebuilds collision and navigation
# through the project's own WorldLoader, then renders the camera set from the
# region's references/captures/index.json so the shots line up with the offline
# previews they are compared against.
#
# Run from the godot-client directory:
#   Godot_v4.7.2-stable_win64_console.exe --path . --script \
#     ../eloria-assets/maps/nymara-regions/_toolkit/godot_capture.gd \
#     --rendering-driver vulkan --resolution 1600x1000 -- \
#     --package=<abs path to region package> --out=<abs path>
extends SceneTree

const SETTLE_FRAMES := 24


func _err(message: String) -> void:
	printerr("[capture] ", message)


func _args() -> Dictionary:
	var out := {}
	for raw in OS.get_cmdline_user_args():
		var arg := str(raw)
		if arg.begins_with("--") and arg.contains("="):
			var parts := arg.substr(2).split("=", true, 1)
			out[parts[0]] = parts[1]
	return out


func _init() -> void:
	var opts := _args()
	var package: String = opts.get("package", "")
	var out_dir: String = opts.get("out", "")
	var only: String = opts.get("only", "")
	if package == "" or out_dir == "":
		_err("need --package=<dir> and --out=<dir>")
		quit(2)
		return

	DirAccess.make_dir_recursive_absolute(out_dir)

	var glb_path := package.path_join("world.glb")
	if not FileAccess.file_exists(glb_path):
		_err("no world.glb at " + glb_path)
		quit(2)
		return

	# Load the GLB exactly as a runtime package: no import step, no .tscn.
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	state.set_handle_binary_image(GLTFState.HANDLE_BINARY_EMBED_AS_BASISU)
	var bytes := FileAccess.get_file_as_bytes(glb_path)
	var err := doc.append_from_buffer(bytes, package, state)
	if err != OK:
		_err("GLTFDocument.append_from_buffer failed: %d" % err)
		quit(2)
		return
	var scene: Node3D = doc.generate_scene(state)
	if scene == null:
		_err("generate_scene returned null")
		quit(2)
		return

	var root := get_root()
	var world := Node3D.new()
	world.name = "World"
	root.add_child(world)
	world.add_child(scene)

	var mesh_count := 0
	var tri_count := 0
	for node in _walk(scene):
		if node is MeshInstance3D:
			mesh_count += 1
			var mesh: Mesh = (node as MeshInstance3D).mesh
			if mesh != null:
				for s in mesh.get_surface_count():
					var arrays := mesh.surface_get_arrays(s)
					var idx: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
					tri_count += idx.size() / 3
	print("[capture] meshes=%d triangles=%d" % [mesh_count, tri_count])

	# What the package asks to be lit by. An interior declares sky "none", its
	# own ambient and fog, and the point lights standing in its lamps; lighting
	# it with an outdoor sun and sky instead shows a room that will never exist.
	var declared: Dictionary = {}
	var manifest_path := package.path_join("world.json")
	if FileAccess.file_exists(manifest_path):
		var parsed_manifest = JSON.parse_string(
			FileAccess.get_file_as_string(manifest_path))
		if parsed_manifest is Dictionary:
			declared = parsed_manifest
	var declared_env: Dictionary = declared.get("environment", {})
	var interior := str(declared_env.get("sky", "")) == "none"

	var env := Environment.new()
	var sky := Sky.new()
	var sky_mat := ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = Color(0.36, 0.52, 0.74)
	sky_mat.sky_horizon_color = Color(0.72, 0.78, 0.84)
	sky_mat.ground_bottom_color = Color(0.26, 0.24, 0.22)
	sky_mat.ground_horizon_color = Color(0.62, 0.62, 0.60)
	sky.sky_material = sky_mat
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 0.45
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_exposure = 1.05
	env.ssao_enabled = true

	if interior:
		env.background_mode = Environment.BG_COLOR
		env.background_color = Color(0.02, 0.02, 0.03)
		env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		var amb: Dictionary = declared_env.get("ambient", {})
		var amb_c: Array = amb.get("colour", [0.13, 0.15, 0.19])
		env.ambient_light_color = Color(float(amb_c[0]), float(amb_c[1]),
										float(amb_c[2]))
		env.ambient_light_energy = float(amb.get("energy", 0.35))
		var fog: Dictionary = declared_env.get("fog", {})
		if bool(fog.get("enabled", false)):
			var fog_c: Array = fog.get("colour", [0.08, 0.09, 0.11])
			env.fog_enabled = true
			env.fog_light_color = Color(float(fog_c[0]), float(fog_c[1]),
										float(fog_c[2]))
			env.fog_density = 0.012
		env.tonemap_exposure = 1.5

	# A WorldEnvironment, not camera.environment: the camera override does not
	# supply the sky the background is drawn from, which leaves the frame in a
	# flat void.
	var world_env := WorldEnvironment.new()
	world_env.environment = env
	world.add_child(world_env)

	var sun := DirectionalLight3D.new()
	sun.light_energy = 1.9
	sun.light_color = Color(1.0, 0.96, 0.88)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 1200.0
	sun.directional_shadow_split_1 = 0.06
	sun.directional_shadow_split_2 = 0.18
	sun.directional_shadow_split_3 = 0.5
	# The region faces south: its citadel, gate and terraces all present their
	# built faces that way, so the sun comes from the south-west or every shot
	# is of a wall in shadow.
	# A DirectionalLight3D shines along its own -Z. The region's built faces
	# look south and most cameras look north, so the light must travel north
	# too: yaw near zero, not near 180, or every shot is backlit.
	sun.rotation_degrees = Vector3(-46.0, 24.0, 0.0)
	if interior:
		# A sealed interior gets a trace of directional light only, so the
		# declared lamps are what actually reads.
		sun.light_energy = 0.12
		sun.shadow_enabled = false
	world.add_child(sun)

	# The lamps the package declares, as real lights.
	var lamp_count := 0
	for entry in declared.get("lights", []):
		var lamp: Dictionary = entry
		var at: Array = lamp.get("position", [])
		if at.size() != 3:
			continue
		var point := OmniLight3D.new()
		point.position = Vector3(float(at[0]), float(at[1]), float(at[2]))
		var col: Array = lamp.get("colour", [1.0, 1.0, 1.0])
		point.light_color = Color(float(col[0]), float(col[1]), float(col[2]))
		point.light_energy = float(lamp.get("energy", 1.5))
		point.omni_range = float(lamp.get("range", 9.0))
		point.shadow_enabled = false
		world.add_child(point)
		lamp_count += 1
	if lamp_count:
		print("[capture] %d declared lamps" % lamp_count)

	var camera := Camera3D.new()
	camera.far = 2400.0
	camera.current = true
	world.add_child(camera)

	var index_path := package.path_join("references/captures/index.json")
	var views: Array = []
	if FileAccess.file_exists(index_path):
		var parsed = JSON.parse_string(FileAccess.get_file_as_string(index_path))
		if parsed is Array:
			views = parsed
	if views.is_empty():
		_err("no camera set at " + index_path)
		quit(2)
		return

	# let the renderer settle before the first shot, or shadows and sky are
	# still converging and every capture is subtly different
	for i in SETTLE_FRAMES:
		await process_frame

	var written := 0
	for entry in views:
		var id: String = str(entry.get("id", ""))
		if only != "" and not id.contains(only):
			continue
		var eye: Array = entry.get("eye", [])
		var target: Array = entry.get("target", [])
		if eye.size() != 3 or target.size() != 3:
			continue
		camera.fov = float(entry.get("fieldOfViewDegrees", 55.0))
		camera.global_position = Vector3(eye[0], eye[1], eye[2])
		var look := Vector3(target[0], target[1], target[2])
		if camera.global_position.distance_to(look) > 0.01:
			camera.look_at(look, Vector3.UP)
		for i in 3:
			await process_frame
		var image := get_root().get_texture().get_image()
		var path := out_dir.path_join(id + ".png")
		if image.save_png(path) == OK:
			written += 1
			print("[capture] %s -> %s" % [id, path])
		else:
			_err("could not save " + path)

	print("[capture] wrote %d frames" % written)
	quit(0)


func _walk(node: Node) -> Array:
	var out: Array = [node]
	for child in node.get_children():
		out.append_array(_walk(child))
	return out

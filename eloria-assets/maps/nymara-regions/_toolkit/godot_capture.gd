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

	# A package that declares `environment.sky == "none"` is sealed - an interior,
	# rooms inside rock. Lighting it with the region rig floods it with sky and
	# puts a sun through its ceiling, which is not a moody frame but a wrong one:
	# the reviewer sees daylight in a vault that has none. Such a package is lit
	# from its own manifest instead.
	var manifest_env: Dictionary = {}
	var manifest_file := FileAccess.open(package.path_join("world.json"), FileAccess.READ)
	if manifest_file != null:
		var parsed: Variant = JSON.parse_string(manifest_file.get_as_text())
		manifest_file.close()
		if typeof(parsed) == TYPE_DICTIONARY:
			manifest_env = parsed.get("environment", {})
	var sealed := str(manifest_env.get("sky", "")) == "none"

	# environment: a plain daylight sky so the shot shows the map, not a mood
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

	# A WorldEnvironment, not camera.environment: the camera override does not
	# supply the sky the background is drawn from, which leaves the frame in a
	# flat void.
	if sealed:
		var amb: Dictionary = manifest_env.get("ambient", {})
		var amb_colour: Variant = amb.get("colour", [0.14, 0.13, 0.18])
		env.background_mode = Environment.BG_COLOR
		env.background_color = Color(0.02, 0.02, 0.03)
		env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		env.ambient_light_color = Color(amb_colour[0], amb_colour[1], amb_colour[2])
		# lifted well above the manifest value: the manifest number is for a
		# renderer with the interior's own lamps, and this harness has none
		env.ambient_light_energy = float(amb.get("energy", 0.4)) * 4.0
		var fog: Dictionary = manifest_env.get("fog", {})
		if bool(fog.get("enabled", false)):
			var fc: Variant = fog.get("colour", [0.06, 0.06, 0.08])
			env.fog_enabled = true
			env.fog_light_color = Color(fc[0], fc[1], fc[2])
			env.fog_density = 0.010

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
	if sealed:
		# straight down and weak: a sealed package has no sun, and this only
		# keeps surfaces from reading as flat unlit colour
		sun.light_energy = 0.30
		sun.light_color = Color(0.82, 0.80, 0.92)
		sun.shadow_enabled = false
		sun.rotation_degrees = Vector3(-88.0, 0.0, 0.0)
	world.add_child(sun)

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

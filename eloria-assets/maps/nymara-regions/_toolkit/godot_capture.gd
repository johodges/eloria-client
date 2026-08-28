extends SceneTree
## Render real Godot frames of a region package through the client's own loader.
##
## Everything in `references/captures/` up to now has come from the offline
## rasteriser in `_toolkit/native/`, which is a preview, not the client. This
## script loads `world.json` with `WorldLoader.load_world` - the same call
## `main.gd` makes - and saves viewport frames, so a capture can honestly be
## labelled as a client render.
##
## Usage:
##   godot --path <godot-client> --script <this> -- <manifest> <outdir> <shots.json>
##
## `shots.json` is a list of {id, eye:[x,y,z], target:[x,y,z], fov, width, height}.
## Heights are absolute metres: the caller resolves ground-relative heights,
## because it has the terrain and this does not.

const SETTLE_FRAMES := 24

var func_to_colour: Callable


func _initialize() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.size() < 3:
		push_error("usage: -- <manifest> <outdir> <shots.json>")
		quit(2)
		return
	var manifest_path: String = args[0]
	var out_dir: String = args[1]
	var shots_path: String = args[2]

	var shots_text: String = FileAccess.get_file_as_string(shots_path)
	if shots_text.is_empty():
		push_error("cannot read shots file: " + shots_path)
		quit(2)
		return
	var shots: Variant = JSON.parse_string(shots_text)
	if typeof(shots) != TYPE_ARRAY:
		push_error("shots file is not a JSON array")
		quit(2)
		return

	DirAccess.make_dir_recursive_absolute(out_dir)

	var window: Window = get_root()
	window.transparent_bg = false

	# This script runs from outside res://, so the project's global class names
	# (WorldLoader among them) are not in scope. The loader script is loaded by
	# path instead, which is still the client's own loader, not a copy of it.
	var loader_script: GDScript = load("res://src/world/world_loader.gd")
	if loader_script == null:
		push_error("cannot load res://src/world/world_loader.gd")
		quit(2)
		return
	var loader = loader_script.new()
	loader.name = "WorldLoader"
	window.add_child(loader)

	var failed: Array = []
	loader.load_failed.connect(func(errors) -> void:
		failed.append_array(errors))

	var completed := [false]
	loader.load_completed.connect(func(_m) -> void: completed[0] = true)

	print("capture stage=load manifest=", manifest_path)
	loader.load_world(manifest_path)

	# `load_world` is synchronous today, but waiting a few frames costs nothing
	# and keeps this working if it ever becomes deferred.
	for i in range(8):
		await process_frame
	if not completed[0]:
		push_error("capture stage=load_failed errors=%s" % [failed])
		quit(3)
		return
	print("capture stage=loaded")

	# The environment comes from the manifest, not from this script. Inventing
	# a light here produced a frame whose whole shadowed side was black and made
	# a cylindrical drum read as a flat slab - a lighting artefact that looks
	# exactly like a modelling defect. What the map asks for is what is captured.
	var manifest_text: String = FileAccess.get_file_as_string(manifest_path)
	var manifest_data: Variant = JSON.parse_string(manifest_text)
	var env_block: Dictionary = {}
	if typeof(manifest_data) == TYPE_DICTIONARY:
		env_block = manifest_data.get("environment", {})

	func_to_colour = func(a, fallback: Color) -> Color:
		if typeof(a) == TYPE_ARRAY and a.size() >= 3:
			return Color(a[0], a[1], a[2])
		return fallback

	var sky_block: Dictionary = env_block.get("sky", {})
	var sun_block: Dictionary = env_block.get("sun", {})
	var ambient_block: Dictionary = env_block.get("ambient", {})
	var fog_block: Dictionary = env_block.get("fog", {})

	var environment := Environment.new()
	environment.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var material := ProceduralSkyMaterial.new()
	material.sky_top_color = func_to_colour.call(sky_block.get("zenith"), Color(0.10, 0.09, 0.16))
	material.sky_horizon_color = func_to_colour.call(sky_block.get("horizon"), Color(0.34, 0.30, 0.38))
	material.ground_horizon_color = material.sky_horizon_color
	material.ground_bottom_color = func_to_colour.call(
		ambient_block.get("groundColor"), Color(0.10, 0.08, 0.06))
	sky.sky_material = material
	environment.sky = sky

	# Ambient is taken as an explicit colour rather than from the sky: a storm
	# sky this dark contributes almost nothing, and every surface facing away
	# from the sun then renders black.
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = func_to_colour.call(
		ambient_block.get("skyColor"), Color(0.20, 0.17, 0.30))
	environment.ambient_light_energy = float(ambient_block.get("energy", 0.34)) * 3.0
	environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	environment.tonemap_exposure = 1.05
	environment.adjustment_enabled = true
	environment.adjustment_saturation = float(env_block.get("saturation", 1.2))
	if bool(fog_block.get("enabled", true)):
		environment.fog_enabled = true
		environment.fog_light_color = func_to_colour.call(
			fog_block.get("color"), Color(0.30, 0.27, 0.36))
		environment.fog_density = float(fog_block.get("density", 0.0011))

	var holder := WorldEnvironment.new()
	holder.environment = environment
	window.add_child(holder)

	var sun := DirectionalLight3D.new()
	sun.light_color = func_to_colour.call(sun_block.get("color"), Color(0.94, 0.88, 1.04))
	sun.light_energy = float(sun_block.get("energy", 1.0)) * 1.6
	sun.shadow_enabled = true
	var dir_array: Variant = sun_block.get("direction", [-0.38, 0.42, 0.82])
	var sun_dir := Vector3(dir_array[0], dir_array[1], dir_array[2]).normalized()
	# the manifest stores the direction TO the sun; a DirectionalLight3D points
	# along its own -Z, so it is placed looking back down that vector
	sun.look_at_from_position(sun_dir * 100.0, Vector3.ZERO, Vector3.UP)
	window.add_child(sun)

	var camera := Camera3D.new()
	camera.far = 2400.0
	camera.near = 0.08
	camera.current = true
	window.add_child(camera)

	var index: Array = []
	for shot in shots:
		var id: String = str(shot.get("id", "shot"))
		var width: int = int(shot.get("width", 1280))
		var height: int = int(shot.get("height", 720))
		window.size = Vector2i(width, height)

		var eye: Array = shot.get("eye", [0, 10, 0])
		var target: Array = shot.get("target", [0, 0, 0])
		var eye_v := Vector3(eye[0], eye[1], eye[2])
		var target_v := Vector3(target[0], target[1], target[2])
		camera.fov = float(shot.get("fov", 55.0))
		camera.global_position = eye_v
		if eye_v.distance_to(target_v) > 0.01:
			camera.look_at(target_v, Vector3.UP)

		# Let the renderer settle: shadow atlas, sky, and any streamed-in state.
		for i in range(SETTLE_FRAMES):
			await process_frame

		var image: Image = window.get_texture().get_image()
		var path: String = out_dir.path_join(id + ".png")
		var err: Error = image.save_png(path)
		if err != OK:
			push_error("capture stage=save id=%s error=%s" % [id, error_string(err)])
			continue
		index.append({"id": id, "file": id + ".png",
			"eye": [eye_v.x, eye_v.y, eye_v.z],
			"target": [target_v.x, target_v.y, target_v.z],
			"fov": camera.fov, "pixels": [width, height]})
		print("capture id=", id, " -> ", path)

	var index_file := FileAccess.open(out_dir.path_join("index.json"), FileAccess.WRITE)
	if index_file != null:
		index_file.store_string(JSON.stringify(index, "  "))
		index_file.close()

	print("capture stage=done count=", index.size())
	quit(0)

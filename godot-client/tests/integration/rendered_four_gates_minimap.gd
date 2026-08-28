extends SceneTree

## Renders the packaged Four Gates minimap straight from the shipped world.glb
## with an orthographic top-down camera, so the cartography can never drift from
## the geometry it describes.

const SIZE := Vector2i(1024, 1024)

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var out: String = OS.get_environment("ELORIA_MINIMAP_OUT")
	if out.is_empty():
		out = ProjectSettings.globalize_path(
			"res://../eloria-assets/maps/four-gates/minimap.png")
	root.size = SIZE
	var scene: Node3D = (load("res://src/dev/world_validation.tscn") as PackedScene
		).instantiate() as Node3D
	root.add_child(scene)
	var loader: WorldLoader = scene.get_node("WorldLoader") as WorldLoader
	var deadline: int = Time.get_ticks_msec() + 240000
	while loader.world_root == null and Time.get_ticks_msec() < deadline:
		await process_frame
	if loader.world_root == null:
		push_error("minimap: world did not load")
		quit(1)
		return
	WorldEnvironmentBinder.apply(loader.manifest,
		scene.get_node("Environment") as WorldEnvironment,
		scene.get_node("Sun") as DirectionalLight3D)
	# flat, shadowless key light so the cartography reads as a map, not a render
	var sun: DirectionalLight3D = scene.get_node("Sun") as DirectionalLight3D
	sun.rotation_degrees = Vector3(-90.0, 0.0, 0.0)
	sun.light_energy = 1.05
	sun.shadow_enabled = false
	var environment: Environment = (scene.get_node("Environment") as WorldEnvironment).environment
	environment.fog_enabled = false
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color(0.05, 0.11, 0.17)
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color(0.85, 0.88, 0.92)
	environment.ambient_light_energy = 0.75
	(scene.get_node("UI") as CanvasLayer).visible = false

	var bounds: Dictionary = loader.manifest.data["asset"]["bounds"]
	var minimum: Array = bounds["min"]
	var maximum: Array = bounds["max"]
	var extent: float = maxf(float(maximum[0]) - float(minimum[0]),
		float(maximum[2]) - float(minimum[2]))
	var camera: Camera3D = scene.get_node("Camera") as Camera3D
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = extent
	camera.near = 1.0
	camera.far = 3000.0
	camera.global_position = Vector3(
		(float(minimum[0]) + float(maximum[0])) * 0.5, 900.0,
		(float(minimum[2]) + float(maximum[2])) * 0.5)
	camera.rotation_degrees = Vector3(-90.0, 0.0, 0.0)
	for _frame: int in range(8):
		await process_frame
	RenderingServer.force_draw(false)
	var image: Image = root.get_texture().get_image()
	var error: int = image.save_png(out)
	print("minimap saved=", out, " ok=", error == OK, " extent_m=", extent)
	quit(0 if error == OK else 1)

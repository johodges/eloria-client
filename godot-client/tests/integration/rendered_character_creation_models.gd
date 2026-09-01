extends SceneTree

const SCREEN_SIZE := Vector2i(1280, 720)
const PREVIEW_SIZE := Vector2i(420, 612)

var _artifact_directory := ""
var _failures := 0
var _results: Array[Dictionary] = []
var _structure_only := false

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	_structure_only = OS.get_environment("ELORIA_STRUCTURE_ONLY") == "1"
	_artifact_directory = OS.get_environment("ELORIA_ARTIFACT_DIR")
	if _artifact_directory.is_empty():
		_artifact_directory = ProjectSettings.globalize_path(
			"res://test-artifacts/character-models")
	_expect(DirAccess.make_dir_recursive_absolute(_artifact_directory) == OK,
		"character-model artifact directory is writable")
	root.size = SCREEN_SIZE
	var scene_resource: Resource = load("res://src/app/main.tscn")
	_expect(scene_resource is PackedScene, "character creation scene loads")
	if scene_resource is not PackedScene:
		_finish()
		return
	var main: Control = (scene_resource as PackedScene).instantiate() as Control
	root.add_child(main)
	for unused_frame: int in range(4):
		await process_frame
	(main.get_node("LoginPanel") as Control).hide()
	(main.get_node("GameView") as Control).hide()
	(main.get_node("CreationPanel") as Control).show()
	# Capture a close three-quarter view so face, hair, clothing fit, and
	# culture features are large enough for the CI artifact to review.
	main.set("preview_yaw", PI + 0.28)
	main.set("preview_pitch", 0.08)
	main.set("preview_distance", 2.4)
	main.call("_update_preview_camera")

	var selector: OptionButton = main.get_node(
		"CreationPanel/Columns/Form/CreateGender") as OptionButton
	var preview: SubViewport = main.get_node(
		"CreationPanel/Columns/CharacterPreview/Viewport") as SubViewport
	var spin_names: Array[String] = ["CreateSkin", "CreateHair", "CreateEyes",
		"CreateHead"]
	# The wardrobe picker is deprecated: creation must not offer a starter
	# shirt, pants or boots over a body that wears its clothing in its texture.
	for gone: String in ["CreateShirt", "CreatePants", "CreateBoots"]:
		_expect(main.get_node_or_null(
			"CreationPanel/Columns/Form/AppearanceGrid/" + gone) == null,
			"creation no longer offers " + gone)
	for spin_name: String in spin_names:
		(main.get_node("CreationPanel/Columns/Form/AppearanceGrid/" + spin_name) as SpinBox).value = 0

	for index: int in range(selector.item_count):
		selector.select(index)
		main.call("_refresh_creation_preview")
		for unused_frame: int in range(10):
			await process_frame
		var label: String = selector.get_item_text(index)
		var slug: String = label.to_lower().replace(" ", "-")
		await _capture_preview(preview, "default-%02d-%s.png" % [index, slug])
		_validate_actor(main.get("preview_actor") as ReplicatedActor3D, label)

	# Exercise all four runtime appearance families through the same creation
	# controls: skin, eyes, native hair, headwear, and wardrobe palettes.
	selector.select(0)
	for style: int in range(4):
		for spin_name: String in spin_names:
			(main.get_node("CreationPanel/Columns/Form/AppearanceGrid/" + spin_name) as SpinBox).value = style
		main.call("_refresh_creation_preview")
		for unused_frame: int in range(10):
			await process_frame
		await _capture_preview(preview, "appearance-variant-%d.png" % style)
		_validate_actor(main.get("preview_actor") as ReplicatedActor3D,
			"appearance variant %d" % style)

	if not _structure_only:
		RenderingServer.force_draw(false)
		var full_texture: ViewportTexture = root.get_texture()
		if full_texture == null:
			_expect(false, "full character creation UI texture is available")
			_finish()
			return
		var full_image: Image = full_texture.get_image()
		_expect(not full_image.is_empty() and full_image.get_size() == SCREEN_SIZE,
			"full character creation UI renders at reference dimensions")
		_expect(full_image.save_png(_artifact_directory.path_join(
			"character-creation-ui.png")) == OK, "saved character creation UI")
	var report := FileAccess.open(_artifact_directory.path_join("validation.json"),
		FileAccess.WRITE)
	_expect(report != null, "character-model validation report is writable")
	if report != null:
		report.store_string(JSON.stringify({"models": _results,
			"failures": _failures}, "  ") + "\n")
	_finish()

func _capture_preview(viewport: SubViewport, file_name: String) -> void:
	for unused_frame: int in range(3):
		await process_frame
	if _structure_only:
		return
	RenderingServer.force_draw(false)
	var texture: ViewportTexture = viewport.get_texture()
	if texture == null:
		_expect(false, "rendered preview texture is available")
		return
	var image: Image = texture.get_image()
	if image == null:
		_expect(false, "rendered preview image is available")
		return
	_expect(not image.is_empty() and image.get_size() == PREVIEW_SIZE,
		"rendered preview has reference dimensions")
	var sampled_colors: Dictionary = {}
	for y: int in range(0, image.get_height(), 16):
		for x: int in range(0, image.get_width(), 16):
			sampled_colors[image.get_pixel(x, y).to_html()] = true
	_expect(sampled_colors.size() >= 32, "rendered preview contains model detail")
	_expect(image.save_png(_artifact_directory.path_join(file_name)) == OK,
		"saved " + file_name)

func _validate_actor(actor: ReplicatedActor3D, label: String) -> void:
	_expect(actor != null, label + " preview actor exists")
	if actor == null:
		return
	var equipment: Dictionary = actor.equipment_diagnostics()
	# Modified 2026-08-28 for Eloria Client: shirt, pants, and boots now use the
	# same skinned equipment path as the world actor. The creation preview should
	# contain those garments, but no socketed prop or fallback placeholder.
	# Modified 2026-09-01 for Eloria Client: an empty wardrobe slot renders
	# bare now -- the race bodies carry their clothing in their own texture --
	# so a preview with nothing equipped has no garments at all.  What must
	# still hold is that nothing was socketed that should have been skinned,
	# and nothing fell back to a placeholder.
	_expect(int(equipment.get("socket", -1)) == 0 and
		int(equipment.get("fallback", -1)) == 0,
		label + " creation preview has no props or fallback placeholders")
	var mesh_names: Array[String] = []
	var maximum_extent := 0.0
	var body_meshes := 0
	# The nameplate, ring and map dot are drawn by the actor, not by the
	# model, and the map dot alone is 15 units across -- measuring them here
	# failed the placeholder check on every body, shipped ones included.
	var furniture: Array[String] = ["SelectionRing", "HealthBarBackground",
		"HealthBarFill", "MapDot", "MapDotOutline"]
	for node_value: Node in actor.find_children("*", "MeshInstance3D", true, false):
		var mesh_node: MeshInstance3D = node_value as MeshInstance3D
		mesh_names.append(mesh_node.name)
		if furniture.has(mesh_node.name):
			continue
		var hair: bool = mesh_node.name.begins_with("NativeHair_")
		var garment: bool = mesh_node.name.begins_with("EquipmentSkin_")
		if not hair and not garment:
			body_meshes += 1
		var size: Vector3 = mesh_node.get_aabb().size
		maximum_extent = maxf(maximum_extent, maxf(size.x, maxf(size.y, size.z)))
	# Modified 2026-09-01 for Eloria Client: a race used to be a nude Body
	# under separate Wardrobe_Shirt/Pants/Boots meshes.  The bodies are now
	# one skinned mesh wearing its clothing in its own texture, so the check
	# is that a body rendered at all, not that it rendered in four pieces.
	_expect(body_meshes >= 1, label + " renders a skinned body")
	_expect(mesh_names.any(func(name: String) -> bool:
		return name.begins_with("NativeHair_")), label + " uses native hairstyle mesh")
	_expect(maximum_extent < 2.1,
		label + " contains no oversized placeholder geometry")
	_results.append({"label": label, "meshes": mesh_names,
		"maximum_extent": maximum_extent, "equipment": equipment})

func _expect(condition: bool, message: String) -> void:
	if condition:
		print("PASS: ", message)
		return
	_failures += 1
	push_error("FAIL: " + message)

func _finish() -> void:
	print("rendered character creation models: ",
		"PASS" if _failures == 0 else "FAIL")
	quit(_failures)

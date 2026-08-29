extends SceneTree
## Rendered evidence for the inventory interaction pass.
##
## Four things are shown rather than asserted structurally: that the backpack
## and wear slots are drawn with nothing selected, that a plain click writes
## only the line along the bottom, that Inspect opens the card over it, and
## that the bag window takes its own size.
##
## Run under a real display:
##   godot --rendering-method gl_compatibility --path . \
##     --script tests/integration/rendered_inventory_tools.gd

const SCREEN_SIZE := Vector2i(1280, 720)

var _artifact_directory := ""
var _failures := 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	_artifact_directory = OS.get_environment("ELORIA_ARTIFACT_DIR")
	if _artifact_directory.is_empty():
		_artifact_directory = ProjectSettings.globalize_path(
			"res://test-artifacts/inventory-tools")
	_expect(DirAccess.make_dir_recursive_absolute(_artifact_directory) == OK,
		"artifact directory is writable")
	root.size = SCREEN_SIZE
	var main: Control = (load("res://src/app/main.tscn") as PackedScene
		).instantiate() as Control
	root.add_child(main)
	await process_frame
	(main.get_node("LoginBackground") as TextureRect).hide()
	(main.get_node("LoginPanel") as Control).hide()
	(main.get_node("GameView") as Control).show()

	var app_state: Node = root.get_node("AppState")
	app_state.set("authenticated", true)
	app_state.set("local_actor_id", 99)
	app_state.set("stats", {
		"health": 72, "max_health": 100, "ether": 33, "max_ether": 50,
		"action_points": 18, "max_action_points": 30, "food": 42,
		"carried": 205, "capacity": 320})
	app_state.set("inventory", {
		0: {"image_id": 3, "quantity": 9, "slot": 0, "inventory_usable": true},
		1: {"image_id": 31, "quantity": 1234567, "slot": 1, "inventory_usable": true},
		2: {"image_id": 35, "quantity": 1, "slot": 2, "inventory_usable": true},
		5: {"image_id": 42, "quantity": 4, "slot": 5, "inventory_usable": true},
		36: {"image_id": 8, "quantity": 1, "slot": 36, "inventory_usable": false}})
	main.call("_on_inventory_button_pressed")
	main.set("selected_inventory_slot", -1)
	main.call("_sync_inventory")
	await _capture("inventory-slots-idle.png")

	# A plain click: the short line is written, and nothing opens over it.
	main.call("_set_inventory_tool", "grab")
	main.call("_describe_slot", 1, false)
	app_state.set("item_detail", {"open": true, "name": "Hearth Bread",
		"category": "Food", "quantity": 1234567,
		"description": "Baked before dawn at the Four Gates ovens.",
		"equipped": false})
	app_state.emit_signal("state_changed", &"item_detail")
	await _capture("inventory-move-short-line.png")

	# Inspect: the same reply, shown in full.
	main.set("selected_inventory_slot", 1)
	main.call("_on_inventory_inspect_pressed")
	app_state.set("item_detail", {"open": true, "name": "Hearth Bread",
		"category": "Food", "quantity": 1234567,
		"description": "Baked before dawn at the Four Gates ovens.",
		"stats": "Restores 40 food. Weight 2.", "equipped": false})
	app_state.emit_signal("state_changed", &"item_detail")
	await _capture("inventory-inspect-card.png")
	app_state.call("close_item_detail")

	# The bag window at its own size, beside an inventory that keeps its own.
	app_state.set("ground_bag", {"open": true, "bag_id": 4, "items": {
		0: {"image_id": 3, "quantity": 12, "slot": 0},
		1: {"image_id": 35, "quantity": 1, "slot": 1}}})
	(main.get_node("GameView/GroundBagPanel") as Control).show()
	main.call("_sync_ground_bag")
	main.call("_apply_ground_bag_scale", 1.0)
	await _capture("bag-window-default.png")
	main.call("_apply_ground_bag_scale", 1.6)
	await _capture("bag-window-resized.png")
	_expect(is_equal_approx(
		(main.get_node("GameView/GroundBagPanel") as Control).scale.x, 1.6),
		"the bag window took the larger size")

	print("rendered inventory tools: ",
		"PASS" if _failures == 0 else "FAIL (%d)" % _failures)
	main.queue_free()
	await process_frame
	quit(_failures)

func _capture(file_name: String) -> void:
	for unused_frame: int in range(4):
		await process_frame
	RenderingServer.force_draw(false)
	var image_value: Variant = root.get_texture().get_image()
	if not image_value is Image:
		_expect(false, "%s: a rendered frame is available" % file_name)
		return
	var image: Image = image_value as Image
	_expect(not image.is_empty() and image.get_size() == SCREEN_SIZE,
		"%s: the frame has reference dimensions" % file_name)
	var sampled: Dictionary = {}
	for y: int in range(0, image.get_height(), 16):
		for x: int in range(0, image.get_width(), 16):
			sampled[image.get_pixel(x, y).to_html()] = true
	_expect(sampled.size() >= 48,
		"%s: the frame carries visual detail (%d colours)"
			% [file_name, sampled.size()])
	_expect(image.save_png(_artifact_directory.path_join(file_name)) == OK,
		"%s: written" % file_name)

func _expect(value: bool, label: String) -> bool:
	if not value:
		_failures += 1
		push_error("FAIL: " + label)
	return value

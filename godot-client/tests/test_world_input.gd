extends SceneTree

var failures: int = 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var scene_resource: Resource = load("res://src/app/main.tscn")
	_expect(scene_resource is PackedScene, "main scene loads")
	if not scene_resource is PackedScene:
		quit(failures)
		return
	var main: Control = (scene_resource as PackedScene).instantiate() as Control
	root.add_child(main)
	await process_frame
	var game_view: Control = main.get_node("GameView") as Control
	var login_panel: Control = main.get_node("LoginPanel") as Control
	var new_character: Button = main.get_node("LoginPanel/Content/NewCharacter") as Button
	var status: Label = main.get_node("LoginPanel/Content/Status") as Label
	var container: SubViewportContainer = main.get_node("GameView/ViewportContainer") as SubViewportContainer
	var world_viewport: SubViewport = main.get_node("GameView/ViewportContainer/Viewport") as SubViewport
	var minimap_viewport: SubViewport = main.get_node("GameView/MapViewport") as SubViewport
	var full_map_viewport: SubViewport = main.get_node("GameView/FullMapViewport") as SubViewport
	var map_camera: Camera3D = main.get_node("GameView/MapViewport/MapCamera") as Camera3D
	var full_map_camera: Camera3D = main.get_node(
		"GameView/FullMapViewport/FullMapCamera") as Camera3D
	var minimap_image: TextureRect = main.get_node("GameView/MinimapFrame/Minimap") as TextureRect
	var full_map_image: TextureRect = main.get_node("GameView/FullMap/MapImage") as TextureRect
	var camera_rig: IsometricCameraController = main.get_node(
		"GameView/ViewportContainer/Viewport/WorldRoot/CameraRig") as IsometricCameraController
	var compass_overlay: TextureRect = main.get_node(
		"GameView/MinimapFrame/CompassOverlay") as TextureRect
	var player_marker: MeshInstance3D = main.get_node(
		"GameView/ViewportContainer/Viewport/WorldRoot/PlayerMapMarker") as MeshInstance3D
	game_view.show()
	_expect(container.mouse_filter == Control.MOUSE_FILTER_STOP,
		"world viewport receives gameplay mouse input")
	_expect(container.gui_input.is_connected(Callable(main, "_on_world_gui_input")),
		"world viewport input handler is connected")
	_expect(not compass_overlay.visible and compass_overlay.texture == null,
		"minimap render is not covered by decorative artwork")
	var resolved_world: World3D = world_viewport.find_world_3d()
	_expect(resolved_world != null, "gameplay World3D resolves from the world viewport")
	_expect(minimap_viewport.world_3d != null and minimap_viewport.world_3d == resolved_world,
		"minimap shares the gameplay World3D")
	_expect(full_map_viewport.world_3d != null and full_map_viewport.world_3d == resolved_world,
		"Tab map shares the gameplay World3D")
	_expect(minimap_image.texture == minimap_viewport.get_texture(),
		"minimap displays its live viewport texture")
	_expect(full_map_image.texture == full_map_viewport.get_texture(),
		"Tab map displays its live viewport texture")
	_expect((map_camera.cull_mask & 4) != 0 and (full_map_camera.cull_mask & 4) != 0,
		"both map cameras render the local-player marker layer")
	var marker_material: StandardMaterial3D = player_marker.material_override as StandardMaterial3D
	if marker_material == null and player_marker.mesh != null:
		marker_material = player_marker.mesh.material as StandardMaterial3D
	_expect(marker_material != null and marker_material.albedo_color == Color.WHITE,
		"local-player map marker is white")
	_expect(marker_material != null and marker_material.no_depth_test,
		"local-player map marker remains visible above map geometry")
	var pick_result: int = int(main.call("_pick_actor", Vector2(640.0, 360.0)))
	_expect(pick_result >= -1, "world click actor ray executes against a non-null World3D")
	_expect(WorldLoader.NAVIGATION_SURFACE_LAYER != WorldLoader.WORLD_COLLISION_LAYER,
		"actor grounding is isolated from structural collision")
	var full_map_panel: Control = main.get_node("GameView/FullMap") as Control
	_expect(not full_map_panel.visible, "Tab map starts closed")
	main.call("_on_map_button_pressed")
	_expect(full_map_panel.visible, "Tab map control opens the populated map viewport")
	main.call("_on_map_button_pressed")
	_expect(camera_rig.distance >= 30.0 and camera_rig.pitch_degrees <= -50.0,
		"default camera presents the map from above")
	var actor_height_fixture: ReplicatedActor3D = ReplicatedActor3D.new()
	root.add_child(actor_height_fixture)
	actor_height_fixture.server_target = Vector3(2.0, 31.15, 3.0)
	actor_height_fixture.global_position = actor_height_fixture.server_target
	actor_height_fixture.set_surface_height(42.08)
	_expect(is_equal_approx(actor_height_fixture.server_target.y, 42.08),
		"actor target follows sampled terrain height")
	_expect(is_equal_approx(actor_height_fixture.global_position.y, 42.08),
		"actor presentation snaps out of terrain")
	actor_height_fixture.actor_id = 77
	actor_height_fixture.apply_server_state({
		"x": 3, "y": 3, "rotation": 0, "command": 22}, CoordinateAdapter.new(), false)
	_expect(is_equal_approx(float(actor_height_fixture.get("_target_yaw")), -PI / 2.0),
		"actor faces the authoritative movement direction")
	_expect(float(actor_height_fixture.get("_presentation_speed")) >= 6.0,
		"walk presentation closes authoritative steps promptly")
	actor_height_fixture.free()
	var lower_hud: Control = main.get_node("GameView/Quickbar") as Control
	var right_stats: Control = main.get_node("GameView/ResourceHud") as Control
	var right_quickbar: Control = main.get_node("GameView/ItemSpellQuickbar") as Control
	var stats_panel: Control = main.get_node("GameView/StatsPanel") as Control
	var inventory_panel: Control = main.get_node("GameView/InventoryPanel") as Control
	var inventory_button: Button = main.get_node(
		"GameView/Quickbar/Buttons/InventoryButton") as Button
	_expect(lower_hud.anchor_bottom == 1.0 and lower_hud.anchor_right == 1.0,
		"lower HUD border spans the bottom edge")
	_expect(right_stats.anchor_left == 1.0 and right_quickbar.anchor_left == 1.0,
		"stats and item/spell quickbar occupy the right HUD rail")
	_expect(not stats_panel.visible, "statistics window starts closed")
	main.call("_on_stats_button_pressed")
	_expect(stats_panel.visible, "statistics button opens the real stats window")
	main.call("_on_stats_button_pressed")
	_expect(not inventory_panel.visible and not inventory_button.disabled,
		"real inventory window starts closed with its HUD action enabled")
	main.call("_on_inventory_button_pressed")
	_expect(inventory_panel.visible and not stats_panel.visible,
		"inventory action opens the window and centrally closes statistics")
	var app_state_inventory: Node = root.get_node("AppState")
	app_state_inventory.set("inventory", {0: {
		"image_id": 3, "quantity": 9, "slot": 0, "flags": 12,
		"inventory_usable": true, "stackable": true}})
	main.call("_sync_inventory")
	var first_inventory_slot: Button = main.get_node(
		"GameView/InventoryPanel/Content/Scroll/InventoryGrid").get_child(0) as Button
	var first_quick_slot: Button = main.get_node(
		"GameView/ItemSpellQuickbar/QuickContent/Slots/Slot1") as Button
	_expect(first_inventory_slot.text.contains("×9") and first_inventory_slot.icon != null
		and not first_inventory_slot.disabled,
		"inventory snapshot populates its server slot")
	_expect(first_quick_slot.text.contains("×9") and first_quick_slot.icon != null
		and not first_quick_slot.disabled,
		"usable inventory slot populates the matching live quick slot")
	for quick_index: int in range(1, 9):
		_expect(InputMap.has_action("quick_item_%d" % quick_index),
			"item quick slot %d has a centralized input action" % quick_index)
	app_state_inventory.set("inventory", {})
	main.call("_on_inventory_close_pressed")
	var viewport_rect: Rect2 = root.get_visible_rect()
	_expect(viewport_rect.encloses(login_panel.get_global_rect()),
		"login panel fits the reference viewport")
	_expect(viewport_rect.encloses(new_character.get_global_rect()),
		"create-character action is visible")
	_expect(viewport_rect.encloses(status.get_global_rect()), "login status is visible")
	var host: LineEdit = main.get_node("LoginPanel/Content/Host") as LineEdit
	_expect(host.text == "18.235.240.60", "development server is the default endpoint")
	var creation_panel: Control = main.get_node("CreationPanel") as Control
	var create_button: Button = main.get_node(
		"CreationPanel/Columns/Form/Actions/Create") as Button
	var back_button: Button = main.get_node(
		"CreationPanel/Columns/Form/Actions/Back") as Button
	login_panel.hide()
	creation_panel.show()
	await process_frame
	_expect(viewport_rect.encloses(creation_panel.get_global_rect()),
		"character-creation panel fits the reference viewport")
	_expect(viewport_rect.encloses(create_button.get_global_rect()),
		"create-character submit action is visible")
	_expect(viewport_rect.encloses(back_button.get_global_rect()),
		"character-creation back action is visible")
	creation_panel.hide()
	game_view.show()

	var right_down: InputEventMouseButton = InputEventMouseButton.new()
	right_down.button_index = MOUSE_BUTTON_RIGHT
	right_down.pressed = true
	main.call("_on_world_gui_input", right_down)
	var motion: InputEventMouseMotion = InputEventMouseMotion.new()
	motion.relative = Vector2(40.0, 12.0)
	var initial_yaw: float = camera_rig.yaw_degrees
	main.call("_on_world_gui_input", motion)
	_expect(not is_equal_approx(camera_rig.yaw_degrees, initial_yaw),
		"right drag rotates camera")
	var right_up: InputEventMouseButton = InputEventMouseButton.new()
	right_up.button_index = MOUSE_BUTTON_RIGHT
	right_up.pressed = false
	main.call("_on_world_gui_input", right_up)

	var wheel: InputEventMouseButton = InputEventMouseButton.new()
	wheel.button_index = MOUSE_BUTTON_WHEEL_UP
	wheel.pressed = true
	var initial_distance: float = camera_rig.distance
	main.call("_on_world_gui_input", wheel)
	_expect(camera_rig.distance < initial_distance, "mouse wheel zooms camera")

	var middle_down: InputEventMouseButton = InputEventMouseButton.new()
	middle_down.button_index = MOUSE_BUTTON_MIDDLE
	middle_down.pressed = true
	main.call("_on_world_gui_input", middle_down)
	var pan_motion: InputEventMouseMotion = InputEventMouseMotion.new()
	pan_motion.relative = Vector2(25.0, -10.0)
	main.call("_on_world_gui_input", pan_motion)
	_expect(camera_rig.pan_offset.length() > 0.0, "middle drag pans camera")
	var follow_actor: Node3D = Node3D.new()
	world_viewport.get_node("WorldRoot").add_child(follow_actor)
	follow_actor.global_position = Vector3(18.0, 47.0, -9.0)
	var app_state: Node = root.get_node("AppState")
	var previous_local_actor_id: int = int(app_state.get("local_actor_id"))
	app_state.set("local_actor_id", 9001)
	var fixture_actors: Dictionary = {9001: follow_actor}
	main.set("actor_nodes", fixture_actors)
	var saved_pan: Vector3 = camera_rig.pan_offset
	main.call("_update_local_actor_follow")
	_expect(camera_rig.focus.is_equal_approx(follow_actor.global_position),
		"camera continuously follows the rendered local actor")
	_expect(camera_rig.pan_offset.is_equal_approx(saved_pan),
		"camera follow preserves the user pan offset")
	app_state.set("local_actor_id", previous_local_actor_id)
	follow_actor.queue_free()

	print("world input tests: ", "PASS" if failures == 0 else "FAIL (%d)" % failures)
	main.queue_free()
	await process_frame
	quit(failures)

func _expect(value: bool, label: String) -> void:
	if value:
		return
	failures += 1
	push_error("FAIL: " + label)

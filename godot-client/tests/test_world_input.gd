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
	var container: TextureRect = main.get_node("GameView/ViewportContainer") as TextureRect
	var world_viewport: SubViewport = main.get_node("GameView/ViewportContainer/Viewport") as SubViewport
	var minimap_viewport: SubViewport = main.get_node("GameView/MapViewport") as SubViewport
	var full_map_viewport: SubViewport = main.get_node("GameView/FullMapViewport") as SubViewport
	var map_camera: Camera3D = main.get_node("GameView/MapViewport/MapCamera") as Camera3D
	var full_map_camera: Camera3D = main.get_node(
		"GameView/FullMapViewport/FullMapCamera") as Camera3D
	var minimap_image: TextureRect = main.get_node("GameView/MinimapFrame/Minimap") as TextureRect
	var full_map_image: TextureRect = main.get_node(
		"GameView/FullMap/MapLayout/MapImage") as TextureRect
	var camera_rig: IsometricCameraController = main.get_node(
		"GameView/ViewportContainer/Viewport/WorldRoot/CameraRig") as IsometricCameraController
	var compass_overlay: TextureRect = main.get_node(
		"GameView/MinimapFrame/CompassOverlay") as TextureRect
	var player_marker: MeshInstance3D = main.get_node(
		"GameView/ViewportContainer/Viewport/WorldRoot/PlayerMapMarker") as MeshInstance3D
	game_view.show()
	var original_window_size: Vector2i = root.size
	root.size = Vector2i(1100, 720)
	await process_frame
	main.call("_on_window_size_changed")
	_expect(world_viewport.size.x != roundi(float(world_viewport.size.y) * 16.0 / 9.0),
		"resizing changes the gameplay viewport aspect without stretching 16:9")
	_expect(world_viewport.size == Vector2i(1100, 720),
		"the world renders at the window pixel size, not the 1280x720 design canvas")
	root.size = original_window_size
	await process_frame
	_expect(container.mouse_filter == Control.MOUSE_FILTER_STOP,
		"world viewport receives gameplay mouse input")
	_expect(container.gui_input.is_connected(Callable(main, "_on_world_gui_input")),
		"world viewport input handler is connected")
	_expect(minimap_image.gui_input.is_connected(Callable(main, "_on_minimap_gui_input")),
		"minimap click-to-walk input handler is connected")
	_expect(full_map_image.gui_input.is_connected(Callable(main, "_on_full_map_gui_input")),
		"Tab map click-to-walk input handler is connected")
	_expect(not compass_overlay.visible and compass_overlay.texture == null,
		"minimap render is not covered by decorative artwork")
	var minimap_frame: Control = main.get_node("GameView/MinimapFrame") as Control
	_expect(not minimap_frame.visible and minimap_frame.anchor_left == 0.0
		and InputMap.has_action("toggle_minimap"),
		"Alt+M controls a floating minimap outside the right HUD rail")
	_expect(minimap_frame.gui_input.is_connected(Callable(main, "_on_minimap_frame_gui_input"))
		and main.get_node("GameView/MinimapFrame/North") is Label
		and main.get_node("GameView/MinimapFrame/East") is Label
		and main.get_node("GameView/MinimapFrame/South") is Label
		and main.get_node("GameView/MinimapFrame/West") is Label,
		"minimap compass border exposes cardinal labels and drag/context input")
	var minimap_menu: PopupMenu = main.get("_minimap_menu") as PopupMenu
	var minimap_border_style: StyleBoxFlat = minimap_frame.get_theme_stylebox(
		"panel") as StyleBoxFlat
	_expect(minimap_menu != null and minimap_menu.item_count == 3,
		"minimap right-click menu exposes north, player, and viewport orientation")
	_expect(minimap_border_style != null
		and minimap_border_style.get_border_width(SIDE_LEFT) == 6
		and is_equal_approx(minimap_image.offset_left,
			float(main.get("MINIMAP_DRAG_BORDER"))),
		"minimap keeps its thick compass ring over a margin the render fills")
	# Scroll wheel over the minimap frames more or less ground. The camera is
	# orthographic, so its size is that width in metres.
	var minimap_camera: Camera3D = map_camera
	var zoom_out := InputEventMouseButton.new()
	zoom_out.button_index = MOUSE_BUTTON_WHEEL_DOWN
	zoom_out.pressed = true
	var zoom_in := InputEventMouseButton.new()
	zoom_in.button_index = MOUSE_BUTTON_WHEEL_UP
	zoom_in.pressed = true
	var zoom_start: float = minimap_camera.size
	main.call("_on_minimap_gui_input", zoom_out)
	_expect(minimap_camera.size > zoom_start,
		"scrolling down over the minimap shows more ground")
	main.call("_on_minimap_gui_input", zoom_in)
	_expect(is_equal_approx(minimap_camera.size, zoom_start),
		"scrolling back up returns the minimap to the width it had")
	for _step: int in range(40):
		main.call("_on_minimap_gui_input", zoom_in)
	_expect(is_equal_approx(minimap_camera.size,
		float(main.get("MINIMAP_ZOOM_MIN"))),
		"minimap zoom stops at its closest bound instead of inverting")
	for _step: int in range(80):
		main.call("_on_minimap_gui_input", zoom_out)
	_expect(is_equal_approx(minimap_camera.size,
		float(main.get("MINIMAP_ZOOM_MAX"))),
		"minimap zoom stops at its widest bound")
	main.set("_minimap_zoom", float(main.get("MINIMAP_ZOOM_DEFAULT")))
	main.call("_apply_minimap_zoom")
	main.call("_on_minimap_orientation_selected", 1)
	_expect(str(main.get("_minimap_orientation")) == "player_up",
		"minimap can rotate with the player")
	main.call("_on_minimap_orientation_selected", 2)
	_expect(str(main.get("_minimap_orientation")) == "viewport_up",
		"minimap can rotate with the viewport")
	main.call("_on_minimap_orientation_selected", 0)
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
	var minimap_center: Vector2 = main.call("_control_to_viewport_position",
		minimap_image.size * 0.5, minimap_image.size, minimap_viewport.size) as Vector2
	var full_map_center: Vector2 = main.call("_control_to_viewport_position",
		full_map_image.size * 0.5, full_map_image.size, full_map_viewport.size) as Vector2
	_expect(minimap_center.is_equal_approx(Vector2(minimap_viewport.size) * 0.5),
		"minimap controls convert local clicks into minimap viewport pixels")
	_expect(full_map_center.is_equal_approx(Vector2(full_map_viewport.size) * 0.5),
		"Tab map controls convert local clicks into full-map viewport pixels")
	_expect(main.call("_map_target_tile", map_camera, minimap_center) is Vector2i,
		"minimap camera ray resolves a server walking target")
	_expect(main.call("_map_target_tile", full_map_camera, full_map_center) is Vector2i,
		"Tab map camera ray resolves a server walking target")
	_expect((map_camera.cull_mask & 4) != 0 and (full_map_camera.cull_mask & 4) != 0,
		"both map cameras render the local-player marker layer")
	var marker_material: StandardMaterial3D = player_marker.material_override as StandardMaterial3D
	if marker_material == null and player_marker.mesh != null:
		marker_material = player_marker.mesh.material as StandardMaterial3D
	_expect(marker_material != null and marker_material.albedo_color == Color.WHITE,
		"local-player map marker is white")
	_expect(marker_material != null and marker_material.no_depth_test,
		"local-player map marker remains visible above map geometry")
	var marker_mesh: CylinderMesh = player_marker.mesh as CylinderMesh
	_expect(marker_mesh != null and marker_mesh.top_radius >= 5.0,
		"local-player white dot remains legible on the full-map scale")
	var pick_result: int = int(main.call("_pick_actor", Vector2(640.0, 360.0)))
	_expect(pick_result >= -1, "world click actor ray executes against a non-null World3D")
	_expect(WorldLoader.NAVIGATION_SURFACE_LAYER != WorldLoader.WORLD_COLLISION_LAYER,
		"actor grounding is isolated from structural collision")
	var full_map_panel: Control = main.get_node("GameView/FullMap") as Control
	_expect(not full_map_panel.visible, "Tab map starts closed")
	main.call("_on_map_button_pressed")
	_expect(full_map_panel.visible, "Tab map control opens the populated map viewport")
	var displayed_map_center: Variant = main.call("_texture_to_viewport_position",
		full_map_image.size * 0.5, full_map_image, full_map_viewport.size)
	_expect(displayed_map_center is Vector2 and (displayed_map_center as Vector2).is_equal_approx(
		Vector2(full_map_viewport.size) * 0.5),
		"full-map hover mapping accounts for keep-aspect centering")
	if full_map_image.size.x > full_map_image.size.y:
		_expect(main.call("_texture_to_viewport_position",
			Vector2(1.0, full_map_image.size.y * 0.5), full_map_image,
			full_map_viewport.size) == null,
			"full-map letterbox margins do not report false coordinates")
	_expect(InputMap.has_action("toggle_map")
		and main.get_node("GameView/FullMap/MapLayout/Sidebar/SidebarContent/ContinentButton") is TextureButton
		and main.get_node("GameView/FullMap/MapLayout/Sidebar/SidebarContent/MapLegend") is RichTextLabel
		and main.get_node("GameView/FullMap/MapLayout/Sidebar/SidebarContent/MapCoordinates") is Label,
		"Tab map exposes continent navigation, a legend, and hover coordinates")
	var map_motion: InputEventMouseMotion = InputEventMouseMotion.new()
	map_motion.position = full_map_image.size * 0.5
	main.call("_on_full_map_gui_input", map_motion)
	_expect((main.get_node(
		"GameView/FullMap/MapLayout/Sidebar/SidebarContent/MapCoordinates") as Label).text.contains(","),
		"map hover reports the same server tile used by click-to-walk")
	main.call("_on_map_button_pressed")
	var gameplay_camera: Camera3D = camera_rig.get_node("Camera") as Camera3D
	_expect(camera_rig.distance >= 24.0 and camera_rig.distance <= 28.0
		and camera_rig.pitch_degrees <= -58.0 and gameplay_camera.fov <= 52.0,
		"default camera keeps the actor readable from a steep isometric angle")
	var actor_height_fixture: ReplicatedActor3D = ReplicatedActor3D.new()
	root.add_child(actor_height_fixture)
	var imported_visual := Node3D.new()
	imported_visual.name = "NativeModel"
	actor_height_fixture.add_child(imported_visual)
	actor_height_fixture.call("_apply_import_adapter", {})
	_expect(is_equal_approx(absf(imported_visual.rotation.y), PI),
		"native visual forward is corrected from glTF +Z to Godot -Z")
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
	_expect(is_equal_approx(actor_height_fixture.server_target.y, 42.08),
		"movement packets preserve the rendered terrain sample")
	_expect(is_equal_approx(float(actor_height_fixture.get("_target_yaw")), -PI / 2.0),
		"actor faces the authoritative movement direction")
	_expect(float(actor_height_fixture.get("_presentation_speed")) >= 6.0,
		"walk presentation closes authoritative steps promptly")
	# A predicted turn holds the facing only until the server answers it.
	actor_height_fixture.predict_turn(PI / 4.0)
	var held_facing: float = actor_height_fixture.desired_facing_yaw()
	actor_height_fixture.apply_server_state({
		"x": 4, "y": 3, "rotation": 0, "command": 22}, CoordinateAdapter.new(), false)
	_expect(is_equal_approx(actor_height_fixture.desired_facing_yaw(), held_facing),
		"a predicted turn holds the facing until the server answers it")
	# CMD_TURN_E. The authoritative turn confirms the prediction and replaces
	# it, so a rejected or differently-resolved turn cannot stick locally.
	actor_height_fixture.apply_server_state({
		"x": 4, "y": 3, "rotation": 16384, "command": 40},
		CoordinateAdapter.new(), false)
	_expect(is_equal_approx(actor_height_fixture.desired_facing_yaw(), -PI / 2.0)
		and not bool(actor_height_fixture.get("_predicted_turn_pending")),
		"an authoritative turn command clears the local turn prediction")
	actor_height_fixture.apply_server_state({
		"x": 4, "y": 3, "rotation": 0, "command": 22}, CoordinateAdapter.new(), false)
	_expect(is_equal_approx(actor_height_fixture.desired_facing_yaw(), -PI / 2.0),
		"movement after a confirmed turn follows authoritative facing again")
	actor_height_fixture.predict_turn(PI / 4.0)
	actor_height_fixture.clear_turn_prediction()
	actor_height_fixture.apply_server_state({
		"x": 5, "y": 3, "rotation": 0, "command": 22}, CoordinateAdapter.new(), false)
	_expect(is_equal_approx(actor_height_fixture.desired_facing_yaw(), -PI / 2.0),
		"an abandoned turn prediction hands the facing back to the server")
	# Nothing but an unanswered turn holds a player off its own step. A route
	# whose steps leave the heading it was ordered from - a keyboard diagonal,
	# or a path that bends round an obstacle - turns the actor onto each step it
	# takes instead of leaving it pointed at the tile it was sent to. CMD_MOVE_NE.
	actor_height_fixture.apply_server_state({
		"x": 6, "y": 4, "rotation": 0, "command": 21}, CoordinateAdapter.new(), false)
	_expect(is_equal_approx(actor_height_fixture.desired_facing_yaw(),
			CoordinateAdapter.new().direction_to_godot(Vector2i(1, 1))),
		"a step off the ordered heading turns the actor onto the step")
	actor_height_fixture.free()
	_check_travel_facing()
	_check_map_dot()
	var north_yaw: float = CoordinateAdapter.new().direction_to_godot(Vector2i(0, -1))
	_expect(main.call("_facing_relative_tile_direction", north_yaw, 1, 0) == Vector2i(0, -1)
		and main.call("_facing_relative_tile_direction", north_yaw, -1, 0) == Vector2i(0, 1)
		and main.call("_facing_relative_tile_direction", north_yaw, 0, -1) == Vector2i(-1, 0)
		and main.call("_facing_relative_tile_direction", north_yaw, 0, 1) == Vector2i(1, 0)
		and main.call("_facing_relative_tile_direction", north_yaw, 1, -1) == Vector2i(-1, -1),
		"WASD is facing-relative, with 45-degree diagonals off the held heading")
	var lower_hud: Control = main.get_node("GameView/Quickbar") as Control
	var chat_panel: Control = main.get_node("GameView/ChatPanel") as Control
	var right_stats: Control = main.get_node("GameView/ResourceHud") as Control
	var right_quickbar: Control = main.get_node("GameView/ItemQuickbar") as Control
	var spell_quickbar: Control = main.get_node("GameView/SpellQuickbar") as Control
	var stats_panel: Control = main.get_node("GameView/StatsPanel") as Control
	var inventory_panel: Control = main.get_node("GameView/InventoryPanel") as Control
	var stats_tabs: TabContainer = main.get_node(
		"GameView/StatsPanel/Content/StatsTabs") as TabContainer
	var inventory_button: Button = main.get_node(
		"GameView/Quickbar/QuickRows/Buttons/InventoryButton") as Button
	var walk_button: Button = main.get_node(
		"GameView/Quickbar/QuickRows/Buttons/WalkButton") as Button
	var attack_button: Button = main.get_node(
		"GameView/Quickbar/QuickRows/Buttons/AttackButton") as Button
	var trade_button: Button = main.get_node(
		"GameView/Quickbar/QuickRows/Buttons/TradeButton") as Button
	var trade_panel: Control = main.get_node("GameView/TradePanel") as Control
	var app_state_inventory: Node = root.get_node("AppState")
	var chat_output: RichTextLabel = main.get_node("GameView/ChatPanel/ChatOutput") as RichTextLabel
	var chat_input: LineEdit = main.get_node("GameView/ChatInput") as LineEdit
	app_state_inventory.call("_on_packet", 0,
		PackedByteArray([1, 128, 91, 80, 77, 32, 102, 114, 111, 109, 32, 65, 108,
			105, 99, 101, 58, 32, 104, 105, 93, 0]))
	main.call("_sync_chat")
	_expect(chat_output.get_parsed_text().contains("[PM] [PM from Alice: hi]"),
		"private chat receives its personal-channel label")
	_expect(not chat_output.bbcode_enabled and chat_input.placeholder_text.contains("/name"),
		"chat remains markup-safe and exposes legacy addressing syntax")
	app_state_inventory.call("_on_packet", 71,
		PackedByteArray([1, 1, 0, 0, 0, 4, 0, 0, 0, 12, 0, 0, 0]))
	main.call("_sync_channel_tabs")
	var numeric_channel: Button = main.get_node("GameView/ChatTabs/Channel2") as Button
	_expect(numeric_channel.visible and numeric_channel.text == "4",
		"server active channels appear as numeric chat tabs")
	main.call("_hide_chat_input")
	_expect(not chat_input.visible, "Esc behavior can dismiss the active chat entry")
	main.call("_show_chat_input")
	_expect(chat_input.visible and chat_input.has_focus(), "T behavior restores chat entry focus")
	main.call("_reveal_chat_messages")
	main.set("_last_chat_activity_msec", Time.get_ticks_msec() - 10000)
	main.call("_update_chat_fade")
	_expect(not chat_panel.visible, "upper chat messages fade away after their display window")
	main.call("_on_chat_tab_pressed", "all")
	_expect(chat_panel.visible and is_equal_approx(chat_panel.modulate.a, 1.0),
		"chat tab selection restores faded messages")
	_expect(lower_hud.anchor_bottom == 1.0 and lower_hud.anchor_right == 1.0,
		"lower HUD border spans the bottom edge")
	main.call("_sync_hud_button_states", true)
	_expect(walk_button.button_pressed and not inventory_button.button_pressed
		and (walk_button.icon as AtlasTexture).atlas !=
			(inventory_button.icon as AtlasTexture).atlas,
		"active and inactive HUD actions use distinct highlighted icon atlases")
	_expect(inventory_button.flat and inventory_button.focus_mode == Control.FOCUS_NONE,
		"bottom HUD icons have no individual box and cannot steal Tab focus")
	# Each icon is painted with its own frame out to the edge of its cell, so
	# without padding the frames touched and the end ones read as cut off.
	var icon_padding: float = float(main.get("HUD_ICON_PADDING"))
	var icon_box: StyleBox = inventory_button.get_theme_stylebox("normal")
	_expect(icon_padding > 0.0
		and is_equal_approx(icon_box.content_margin_left, icon_padding)
		and is_equal_approx(icon_box.content_margin_top, icon_padding)
		and is_equal_approx(inventory_button.custom_minimum_size.x,
			44.0 + icon_padding * 2.0)
		and inventory_button.vertical_icon_alignment == VERTICAL_ALIGNMENT_CENTER,
		"bottom HUD icons are padded off their neighbours and centred in their box")
	var chat_tabs: Control = main.get_node("GameView/ChatTabs") as Control
	_expect(chat_tabs.position.x <= 12.0 and chat_tabs.position.y <= 8.0
		and chat_panel.anchor_bottom < 0.3
		and chat_input.offset_bottom <= lower_hud.offset_top,
		"legacy chat tabs sit at upper left while entry remains above the lower rail")
	# One rail, two columns: spells down its left half and items down its
	# right, with the rail itself owning the only border so its left edge is a
	# single line rather than one per box.
	var right_rail: Panel = main.get_node("GameView/RightRail") as Panel
	var rail_children: Array[Control] = [right_stats, right_quickbar,
		spell_quickbar,
		main.get_node("GameView/EloriaLogoFrame") as Control,
		main.get_node("GameView/ClockFrame") as Control,
		main.get_node("GameView/CompassFrame") as Control]
	var strays := 0
	for railed: Control in rail_children:
		if railed.anchor_left != 1.0 or railed.anchor_right != 1.0:
			strays += 1
		elif railed.offset_left < right_rail.offset_left 				or railed.offset_right > right_rail.offset_right:
			strays += 1
		elif railed.get_theme_stylebox("panel") is not StyleBoxEmpty:
			strays += 1
	_expect(strays == 0 and right_rail.anchor_left == 1.0
		and right_rail.anchor_bottom == 1.0 and right_rail.offset_top == 0.0
		and right_rail.get_theme_stylebox("panel") is StyleBoxFlat,
		"the right rail is one bordered bar from the top of the client down"
			+ " and everything in it is drawn without a box of its own")
	# Offsets are only a request: a container whose contents need more room
	# grows past them, which is how the spell column ended up outside the rail
	# and the stats panel ended up under the clock. Assert the resolved rects.
	var rail_rect := Rect2(right_rail.global_position, right_rail.size)
	var stacked: Array[Control] = [
		main.get_node("GameView/EloriaLogoFrame") as Control, spell_quickbar,
		right_stats, main.get_node("GameView/ClockFrame") as Control,
		main.get_node("GameView/CompassFrame") as Control]
	var spilled := 0
	var collided := 0
	var previous_bottom: float = rail_rect.position.y
	for boxed: Control in stacked + [right_quickbar] as Array[Control]:
		var box := Rect2(boxed.global_position, boxed.size)
		if not rail_rect.encloses(box):
			spilled += 1
	for boxed: Control in stacked:
		if boxed.global_position.y < previous_bottom:
			collided += 1
		previous_bottom = boxed.global_position.y + boxed.size.y
	_expect(spilled == 0 and collided == 0,
		"the rail's contents all fit inside it and none sits on top of another")
	var spell_middle: float = (spell_quickbar.offset_left
		+ spell_quickbar.offset_right) * 0.5
	_expect(right_quickbar.offset_left >= spell_middle
		and right_quickbar.offset_right <= spell_quickbar.offset_right
		and spell_quickbar.offset_left <= spell_middle,
		"spells run down the left of the rail and items down its right")
	var item_slots: GridContainer = main.get_node("%ItemSlots") as GridContainer
	var spell_slots: GridContainer = main.get_node("%SpellSlots") as GridContainer
	_expect(item_slots.columns == 1 and spell_slots.columns == 1
		and item_slots.visible and spell_slots.visible,
		"both quick slot columns stay visible without a mode toggle")
	var clock_face: TextureRect = main.get_node("GameView/ClockFrame/ClockFace") as TextureRect
	var compass_face: TextureRect = main.get_node("GameView/CompassFrame/CompassFace") as TextureRect
	_expect(clock_face.texture != null and compass_face.texture != null,
		"legacy clock and compass use the existing Eloria HUD atlas")
	_expect(clock_face.gui_input.is_connected(Callable(main, "_on_clock_gui_input"))
		and compass_face.gui_input.is_connected(Callable(main, "_on_compass_gui_input"))
		and (main.get_node("GameView/EloriaLogoFrame/HudLogo") as TextureRect).texture != null,
		"clock, compass, and top-right Eloria logo are interactive/present")
	_expect(InputMap.has_action("toggle_console")
		and InputMap.has_action("toggle_inventory")
		and InputMap.has_action("recenter_viewport")
		and InputMap.has_action("move_north") and InputMap.has_action("move_south")
		and InputMap.has_action("move_west") and InputMap.has_action("move_east")
		and InputMap.has_action("turn_left") and InputMap.has_action("turn_right")
		and main.get_node("GameView/ConsolePanel/Content/ConsoleOutput") is RichTextLabel
		and chat_input.anchor_left > 0.5,
		"console, Ctrl+I inventory, WASD/QE/Space, and bottom-right chat controls are available")
	_expect(main.call("_movement_axes_for_actions", true, false, false, false)
		== Vector2i(1, 0)
		and main.call("_movement_axes_for_actions", false, true, false, false)
		== Vector2i(-1, 0)
		and main.call("_movement_axes_for_actions", false, false, true, false)
		== Vector2i(0, 1)
		and main.call("_movement_axes_for_actions", false, false, false, true)
		== Vector2i(0, -1),
		"W/S move forward/backward and A/D use the requested swapped strafe directions")
	# The chat entry above kept keyboard focus. Release it: bound printable keys
	# are deliberately inert while a text field is focused.
	main.call("_hide_chat_input")
	await process_frame
	# Every keyboard binding is resolved through the InputMap. Raw keycode
	# comparisons used to shadow toggle_inventory, turn_left and turn_right, so
	# rebinding them appeared to work and changed nothing. Rebinding an action
	# and pressing both the old and the new key is what proves that is gone.
	for rebindable: String in ["turn_left", "turn_right", "toggle_inventory",
			"toggle_map", "toggle_minimap", "toggle_console",
			"recenter_viewport", "connect", "disconnect"]:
		_expect(InputMap.has_action(rebindable)
			and InputMap.action_get_events(rebindable).size() > 0,
			"%s is a declared action with at least one real event" % rebindable)
	# Every binding also has to name a key this engine has. `toggle_map` held
	# ASCII 9 - Godot 3's tab - which matches nothing in 4.x, so Tab fell
	# through to the built-in ui_focus_next and walked the focus ring around
	# the HUD buttons instead of opening the map.
	for bound: String in ["turn_left", "turn_right", "toggle_inventory",
			"toggle_map", "toggle_minimap", "toggle_console",
			"recenter_viewport", "connect", "disconnect", "cancel"]:
		for bound_event: InputEvent in InputMap.action_get_events(bound):
			var bound_key: InputEventKey = bound_event as InputEventKey
			if bound_key == null:
				continue
			var code: int = bound_key.physical_keycode
			_expect(code != 0 and OS.find_keycode_from_string(
				OS.get_keycode_string(code)) == code,
				"%s is bound to a keycode this engine recognises" % bound)
	# Pressed from a focused HUD button, because that is where the focus ring
	# lived once the map stopped opening.
	var map_hud_button: Button = main.get_node(
		"GameView/Quickbar/QuickRows/Buttons/MapButton") as Button
	var map_hud_focus: int = map_hud_button.focus_mode
	map_hud_button.focus_mode = Control.FOCUS_ALL
	map_hud_button.grab_focus()
	await process_frame
	var map_was_open: bool = full_map_panel.visible
	var tab_press: InputEventKey = (InputMap.action_get_events(
		"toggle_map")[0].duplicate() as InputEventKey)
	tab_press.pressed = true
	root.push_input(tab_press)
	await process_frame
	_expect(full_map_panel.visible != map_was_open
		and root.gui_get_focus_owner() == map_hud_button,
		"Tab opens the map instead of moving focus, even from a focused button")
	root.push_input(tab_press)
	await process_frame
	map_hud_button.focus_mode = map_hud_focus as Control.FocusMode
	map_hud_button.release_focus()
	for rebindable: String in ["turn_left", "turn_right", "toggle_map",
			"toggle_minimap", "toggle_console"]:
		var defaults: Array[InputEvent] = InputMap.action_get_events(rebindable)
		var original_key: InputEventKey = defaults[0].duplicate() as InputEventKey
		original_key.pressed = true
		var moved := InputEventKey.new()
		moved.physical_keycode = KEY_F9
		moved.pressed = true
		InputMap.action_erase_events(rebindable)
		InputMap.action_add_event(rebindable, moved)
		_expect(not bool(main.call("_handle_bound_action", original_key)),
			"rebinding %s releases its previous key" % rebindable)
		_expect(bool(main.call("_handle_bound_action", moved)),
			"rebinding %s moves the behaviour onto the new key" % rebindable)
		InputMap.action_erase_events(rebindable)
		for restored: InputEvent in defaults:
			InputMap.action_add_event(rebindable, restored)
		_expect(bool(main.call("_handle_bound_action", original_key)),
			"restoring the %s binding restores its default key" % rebindable)
	# Both connection actions reach a handler. connect() is driven from the
	# already-connected branch so the assertion opens no socket.
	app_state_inventory.set("connection_state", "connected")
	var connect_key: InputEventKey = InputMap.action_get_events(
		"connect")[0].duplicate() as InputEventKey
	connect_key.pressed = true
	_expect(bool(main.call("_handle_bound_action", connect_key)),
		"the connect binding reaches a handler")
	var disconnect_key: InputEventKey = InputMap.action_get_events(
		"disconnect")[0].duplicate() as InputEventKey
	disconnect_key.pressed = true
	_expect(bool(main.call("_handle_bound_action", disconnect_key)),
		"the disconnect binding reaches a handler")
	app_state_inventory.set("connection_state", "disconnected")
	# A focused text field keeps its own characters and clipboard shortcuts.
	chat_input.show()
	chat_input.grab_focus()
	await process_frame
	var console_key: InputEventKey = InputMap.action_get_events(
		"toggle_console")[0].duplicate() as InputEventKey
	console_key.pressed = true
	_expect(not bool(main.call("_handle_bound_action", console_key)),
		"a bound printable key typed into chat does not also toggle a window")
	chat_input.release_focus()
	chat_input.hide()
	await process_frame
	_expect(stats_tabs.get_tab_count() == 4
		and stats_tabs.get_tab_title(0) == "Statistics"
		and stats_tabs.get_tab_title(1) == "Knowledge"
		and stats_tabs.get_tab_title(2) == "Counters"
		and stats_tabs.get_tab_title(3) == "Session Experience",
		"statistics frame provides the four Eternal Lands-style tabs")
	_expect(main.get_node("GameView/StatsPanel/Content/Header/StatsClose") is Button
		and main.get_node("GameView/StatsPanel/Content/StatsTabs/Counters/CounterColumns/CounterCategories") is ItemList
		and main.get_node("GameView/StatsPanel/Content/StatsTabs/Session Experience/SessionContent/SessionXpText") is RichTextLabel,
		"statistics has close, counters, session XP, and perks-ready content")
	for meter_path: String in [
		"GameView/Quickbar/QuickRows/BottomMeters/ManaMeter/EtherBottom",
		"GameView/Quickbar/QuickRows/BottomMeters/FoodMeter/FoodBottom",
		"GameView/Quickbar/QuickRows/BottomMeters/HealthMeter/HealthBottom",
		"GameView/Quickbar/QuickRows/BottomMeters/LoadMeter/LoadBottom",
		"GameView/Quickbar/QuickRows/BottomMeters/ActionMeter/ActionBottom",
		"GameView/Quickbar/QuickRows/BottomMeters/ExperienceMeter/ExperienceBottom"]:
		_expect(main.get_node_or_null(meter_path) is ProgressBar,
			"bottom HUD exposes %s" % meter_path.get_file())
	var actor_menu: Control = main.get_node("GameView/ActorHudMenu") as Control
	main.call("_open_actor_hud_menu", Vector2(640.0, 360.0))
	var banner_menu_entries: Array[String] = ["ShowNames",
		"ShowHealthBar", "ShowHealthNumbers", "ShowEtherBar", "ShowEtherNumbers",
		"ShowFoodBar", "ShowFoodNumbers", "ShowActionBar", "ShowActionNumbers",
		"InstanceMode", "SpeechBubbles", "BannerBackground", "SitLock",
		"RangingLock", "DisableMenu"]
	var banner_menu_complete: bool = actor_menu.visible
	for entry_name: String in banner_menu_entries:
		if not (main.get_node_or_null(
				"GameView/ActorHudMenu/Options/" + entry_name) is CheckBox):
			banner_menu_complete = false
	_expect(banner_menu_complete,
		"banner context menu carries the Eternal Lands option set")
	app_state_inventory.set("stats", {"health": 72, "max_health": 100,
		"ether": 33, "max_ether": 50, "action_points": 18,
		"max_action_points": 30, "food": 42, "carried": 205, "capacity": 320,
		"attack": 24, "overall": 22, "harvesting": 8,
		"harvesting_base": 8, "harvesting_exp": 1480,
		"harvesting_exp_next": 2066})
	main.call("_sync_stats")
	var overhead_health_bar: ProgressBar = main.get_node(
		"GameView/ActorResourceOverlay/Rows/HealthRow/Bar") as ProgressBar
	var overhead_health_label: Label = main.get_node(
		"GameView/ActorResourceOverlay/Rows/HealthRow/Number") as Label
	var overhead_fill: StyleBoxFlat = overhead_health_bar.get_theme_stylebox("fill") as StyleBoxFlat
	var overhead_background: StyleBoxFlat = overhead_health_bar.get_theme_stylebox(
		"background") as StyleBoxFlat
	# 72/100 health sits in the green half of the EL ramp; the bar keeps only a
	# black frame so the world shows through whatever health is missing.
	_expect(overhead_fill != null and overhead_fill.bg_color.g > overhead_fill.bg_color.r
		and overhead_health_label.get_theme_color("font_color").g
			> overhead_health_label.get_theme_color("font_color").r
		and overhead_background != null and overhead_background.bg_color.a == 0.0,
		"overhead health bar follows the Eternal Lands drain colour")
	var drained: Color = main.call("_banner_colour", "health", 0.15)
	_expect(drained.r > drained.g,
		"the health ramp turns red as it empties")
	_expect(is_equal_approx((main.get_node(
		"GameView/Quickbar/QuickRows/BottomMeters/HealthMeter/HealthBottom") as ProgressBar).value, 72.0)
		and is_equal_approx((main.get_node(
		"GameView/Quickbar/QuickRows/BottomMeters/ManaMeter/EtherBottom") as ProgressBar).value, 33.0)
		and is_equal_approx((main.get_node(
		"GameView/Quickbar/QuickRows/BottomMeters/ActionMeter/ActionBottom") as ProgressBar).value, 18.0),
		"health, ethereality, and action-point meters synchronize live values")
	var floating_feedback: Array[Dictionary] = []
	app_state_inventory.floating_feedback_requested.connect(
		func(feedback: Dictionary) -> void: floating_feedback.append(feedback))
	app_state_inventory.call("_on_packet", 49, PackedByteArray([
		51, 0xd4, 0x05, 0, 0, 27, 9, 0, 0, 0]))
	_expect(floating_feedback.size() == 2
		and floating_feedback[0].kind == "experience"
		and int(floating_feedback[0].amount) == 12
		and floating_feedback[1].kind == "level",
		"partial experience and level updates request EL-style floating feedback")
	var ether_row: Control = main.get_node(
		"GameView/ActorResourceOverlay/Rows/EtherRow") as Control
	var ether_bar_box: CheckBox = main.get_node(
		"GameView/ActorHudMenu/Options/ShowEtherBar") as CheckBox
	var ether_numbers_box: CheckBox = main.get_node(
		"GameView/ActorHudMenu/Options/ShowEtherNumbers") as CheckBox
	var banner_overlay: Control = main.get_node("GameView/ActorResourceOverlay") as Control
	var full_banner_height: float = banner_overlay.size.y
	ether_bar_box.set_pressed_no_signal(false)
	main.call("_apply_banner_options")
	_expect(ether_row.visible
		and not (ether_row.get_node("Bar") as Control).visible
		and (ether_row.get_node("Number") as Control).visible,
		"the ether bar switch leaves the ether numbers behind")
	ether_numbers_box.set_pressed_no_signal(false)
	main.call("_apply_banner_options")
	_expect(not ether_row.visible and banner_overlay.size.y < full_banner_height,
		"a row that is fully switched off shrinks the banner")
	ether_bar_box.set_pressed_no_signal(true)
	ether_numbers_box.set_pressed_no_signal(true)
	main.call("_apply_banner_options")
	_expect(is_equal_approx(banner_overlay.size.y, full_banner_height),
		"restoring the row grows the banner back")
	var banner_background_box: CheckBox = main.get_node(
		"GameView/ActorHudMenu/Options/BannerBackground") as CheckBox
	banner_background_box.set_pressed_no_signal(true)
	main.call("_apply_banner_options")
	var banner_panel: StyleBoxFlat = banner_overlay.get_theme_stylebox("panel") as StyleBoxFlat
	banner_background_box.set_pressed_no_signal(false)
	main.call("_apply_banner_options")
	_expect(banner_panel != null and banner_panel.bg_color.a > 0.0
		and banner_overlay.get_theme_stylebox("panel") is StyleBoxEmpty,
		"the banner background switch swaps the panel behind the banner")
	var disable_menu_box: CheckBox = main.get_node(
		"GameView/ActorHudMenu/Options/DisableMenu") as CheckBox
	disable_menu_box.set_pressed_no_signal(true)
	main.call("_apply_banner_options")
	main.call("_open_actor_hud_menu", Vector2(640.0, 360.0))
	var stayed_closed: bool = not actor_menu.visible
	main.call("_on_banner_menu_enabled_toggled", true)
	main.call("_open_actor_hud_menu", Vector2(640.0, 360.0))
	_expect(stayed_closed and not disable_menu_box.button_pressed and actor_menu.visible,
		"Disable This Menu is honoured and reversible from HUD settings")
	actor_menu.hide()
	var sit_lock_box: CheckBox = main.get_node(
		"GameView/ActorHudMenu/Options/SitLock") as CheckBox
	var ranging_lock_box: CheckBox = main.get_node(
		"GameView/ActorHudMenu/Options/RangingLock") as CheckBox
	var previous_actors: Dictionary = app_state_inventory.get("actors") as Dictionary
	var previous_local_id: int = int(app_state_inventory.get("local_actor_id"))
	app_state_inventory.set("local_actor_id", 91)
	app_state_inventory.set("actors", {91: {"actor_id": 91, "x": 10, "y": 20,
		"sitting": true, "appearance": {"weapon": 0}}})
	sit_lock_box.set_pressed_no_signal(true)
	var sit_locked: bool = bool(main.call("_movement_locked", false))
	var ctrl_overrides: bool = not bool(main.call("_movement_locked", true))
	sit_lock_box.set_pressed_no_signal(false)
	_expect(sit_locked and ctrl_overrides,
		"Sit Lock holds a seated character in place until Ctrl is held")
	ranging_lock_box.set_pressed_no_signal(true)
	var unarmed_free: bool = not bool(main.call("_movement_locked", false))
	# client_serv.h BOW_RECURVE, inside the ranged span Ranging Lock covers.
	app_state_inventory.set("actors", {91: {"actor_id": 91, "x": 10, "y": 20,
		"sitting": false, "appearance": {"weapon": 66}}})
	var bow_locked: bool = bool(main.call("_movement_locked", false))
	ranging_lock_box.set_pressed_no_signal(false)
	_expect(unarmed_free and bow_locked,
		"Ranging Lock only holds a character carrying a ranged weapon")
	app_state_inventory.set("actors", previous_actors)
	app_state_inventory.set("local_actor_id", previous_local_id)
	_expect(not stats_panel.visible, "statistics window starts closed")
	main.call("_on_stats_button_pressed")
	_expect(stats_panel.visible and not stats_panel.get_global_rect().intersects(
		right_stats.get_global_rect()),
		"statistics window opens without covering the fixed resource rail")
	_expect(stats_panel.z_index > (main.get_node("GameView/ActorResourceOverlay") as Control).z_index,
		"popup windows render above the player resource overlay")
	main.call("_on_stats_button_pressed")
	_expect(not inventory_panel.visible and not inventory_button.disabled,
		"real inventory window starts closed with its HUD action enabled")
	var inventory_hotkey := InputEventKey.new()
	inventory_hotkey.pressed = true
	inventory_hotkey.ctrl_pressed = true
	inventory_hotkey.physical_keycode = KEY_I
	main.call("_input", inventory_hotkey)
	_expect(inventory_panel.visible, "Ctrl+I opens inventory")
	main.call("_input", inventory_hotkey)
	_expect(not inventory_panel.visible, "Ctrl+I closes inventory")
	_expect(main.get_node("GameView/InventoryPanel/Content/Header/InventoryClose") is Button
		and main.get_node("GameView/InventoryPanel/Content/InventoryBody/SideActions/InventoryStoreAll") is Button
		and main.get_node("GameView/InventoryPanel/Content/InventoryBody/SideActions/InventoryGetAll") is Button
		and main.get_node("GameView/InventoryPanel/Content/InventoryBody/SideActions/InventoryDropAll") is Button
		and main.get_node("GameView/InventoryPanel/Content/InventoryBody/SideActions/InventoryMixAll") is Button
		and main.get_node("GameView/InventoryPanel/Content/InventoryBody/SideActions/InventoryItemLists") is Button
		and main.get_node("GameView/InventoryPanel/Content/InventoryFooter/InventoryResizeGrip") is Button,
		"inventory exposes close, all EL-style side actions, and a resize grip")
	main.call("_apply_inventory_scale", 0.75)
	_expect(is_equal_approx(inventory_panel.scale.x, 0.75)
		and is_equal_approx(inventory_panel.scale.y, 0.75),
		"inventory resizing uniformly scales boxes, icons, and text without changing aspect")
	main.call("_apply_inventory_scale", 1.0)
	# Command 226 enriches the inventory; it never replaces it. The two
	# fixtures below deliberately disagree about the quantity in slot 0, and
	# the tooltip has to keep the authoritative one.
	app_state_inventory.call("_on_packet", 19, PackedByteArray([
		1, 20, 0, 12, 0, 0, 0, 0, 4]))
	app_state_inventory.call("_on_packet", 226, _hex_bytes(
		"fa00000014000000500000000100001400990000000100000000"
		+ "53756e6c65616600466c6f7765727300"))
	var enriched_tooltip: String = str(main.call("_inventory_tooltip",
		app_state_inventory.get("inventory").get(0, {}), 0))
	_expect(enriched_tooltip.contains("Sunleaf")
		and enriched_tooltip.contains("Flowers")
		and enriched_tooltip.contains("1 EMU"),
		"the inventory tooltip names the item the server described: "
			+ enriched_tooltip)
	_expect(enriched_tooltip.contains("quantity 12")
		and not enriched_tooltip.contains("quantity 153"),
		"the enriched tooltip keeps the authoritative quantity, not the"
			+ " enrichment packet's: " + enriched_tooltip)
	app_state_inventory.call("_on_packet", 226, _hex_bytes(
		"fa000000140000005000000000 00".replace(" ", "")))
	_expect(str(main.call("_inventory_tooltip", app_state_inventory.get("inventory").get(0, {}), 0))
		.contains("Item image #20"),
		"without an enrichment entry the tooltip falls back to the image id")

	_expect((main.call("_parse_item_list", "1158:20\n189:1") as Array).size() == 2,
		"custom storage item lists parse image IDs and quantities")
	var inventory_body: HBoxContainer = main.get_node(
		"GameView/InventoryPanel/Content/InventoryBody") as HBoxContainer
	var equipment_column: VBoxContainer = main.get_node(
		"GameView/InventoryPanel/Content/InventoryBody/EquipmentColumn") as VBoxContainer
	main.call("_on_equipment_side_selected", 1)
	_expect(equipment_column.get_index() == inventory_body.get_child_count() - 1,
		"settings can place equipment on the right side")
	main.call("_on_equipment_side_selected", 0)
	_expect(equipment_column.get_index() == 0,
		"settings can independently restore equipment to the left side")
	main.call("_on_bulk_option_selected", 0, "drop")
	_expect(bool(main.call("_inventory_slot_is_protected", 0, "drop"))
		and not bool(main.call("_inventory_slot_is_protected", 6, "drop")),
		"drop-all row and column protections are independently selectable")
	main.call("_on_bulk_option_selected", 0, "drop")
	_expect(attack_button.disabled, "attack action starts disabled without a selected target")
	_expect(trade_button.disabled and not trade_panel.visible,
		"trade starts closed and disabled without a selected player")
	var attackable_actor: Dictionary = {
		"actor_id": 77, "name": "Rat", "kind": 3, "health": 12,
		"max_health": 12, "alive": true}
	_expect(str(main.call("_model_for_actor", {
		"enhanced": true, "kind": 2, "actor_type": 1})).is_empty(),
		"enhanced NPC wire packets never select a luminous player model")
	_expect(str(main.call("_model_for_actor", {
		"enhanced": true, "kind": 1, "actor_type": 1})) == "luminous_male",
		"enhanced player wire packets retain the native luminous model")
	var invasion_models: Dictionary = {
		400: "river_otter", 401: "elk", 402: "desert_tortoise",
		403: "sunscale_drake", 404: "snow_hare", 405: "thunder_ram",
		406: "ice_bear", 407: "frost_tiger", 408: "ash_crawler",
		409: "dire_wolf", 410: "armored_rhino", 411: "giant_komodo",
		412: "emberfox", 413: "ridgehorn", 414: "saber_tooth_cat",
		415: "fire_salamander", 416: "moose", 417: "mossback_boar",
		418: "frost_maw", 419: "porcupine", 420: "two_tailed_fox",
		421: "miretoad", 422: "giant_komodo", 423: "sunscale_drake",
		424: "bog_lurker", 425: "miretoad", 426: "giant_crocodile",
		427: "giant_crocodile",
	}
	for actor_type_value: Variant in invasion_models:
		var invasion_actor_type: int = int(actor_type_value)
		var expected_model: String = str(invasion_models[actor_type_value])
		_expect(str(main.call("_model_for_actor", {
			"enhanced": true, "kind": 3,
			"actor_type": invasion_actor_type})) == expected_model,
			"invasion actor type %d resolves to native model %s" % [
				invasion_actor_type, expected_model])
	var lakeglass_model_id: String = str(main.call("_model_for_actor", {
		"enhanced": true, "kind": 3, "actor_type": 403}))
	var lakeglass_model_config: Dictionary = (main.get("models") as Dictionary).get(
		lakeglass_model_id, {}) as Dictionary
	var lakeglass_actor: ReplicatedActor3D = ReplicatedActor3D.new()
	main.add_child(lakeglass_actor)
	var lakeglass_errors: Array[String] = lakeglass_actor.configure({
		"actor_id": 4030, "x": 0, "y": 0, "rotation": 0,
		"actor_type": 403, "kind": 3, "name": "Lakeglass Drake",
	}, CoordinateAdapter.new({"walkingHeight": 0.0}), lakeglass_model_config,
		main.call("_animation_for_model", lakeglass_model_config) as Dictionary,
		main.get("equipment_config") as Dictionary)
	_expect(lakeglass_errors.is_empty()
		and lakeglass_actor.get_node_or_null("NativeModel") != null
		and lakeglass_actor.get_node_or_null("MissingModelFallback") == null,
		"Lakeglass Drake actor type 403 loads its animated native GLB without fallback")
	lakeglass_actor.queue_free()
	app_state_inventory.set("actors", {77: attackable_actor})
	app_state_inventory.set("selected_actor_id", 77)
	main.call("_sync_selection")
	_expect(not attack_button.disabled and attack_button.tooltip_text.contains("server"),
		"living creature selection enables the server-authoritative attack action")
	app_state_inventory.call("_on_packet", 47, PackedByteArray([77, 0, 5, 0]))
	var damaged_value: Variant = (app_state_inventory.get("actors") as Dictionary).get(77, {})
	var damaged_actor: Dictionary = damaged_value as Dictionary
	_expect(int(damaged_actor.get("health", -1)) == 7,
		"authoritative combat damage updates replicated actor health")
	app_state_inventory.call("_on_packet", 48, PackedByteArray([77, 0, 3, 0]))
	var healed_value: Variant = (app_state_inventory.get("actors") as Dictionary).get(77, {})
	var healed_actor: Dictionary = healed_value as Dictionary
	_expect(int(healed_actor.get("health", -1)) == 10,
		"authoritative combat heal updates replicated actor health")
	attackable_actor["alive"] = false
	attackable_actor["health"] = 0
	app_state_inventory.set("actors", {77: attackable_actor})
	main.call("_sync_selection")
	_expect(attack_button.disabled, "dead target disables the attack action")
	var tradeable_actor: Dictionary = {
		"actor_id": 88, "name": "Alice", "kind": 1, "health": 20,
		"max_health": 20, "alive": true}
	app_state_inventory.set("actors", {88: tradeable_actor})
	app_state_inventory.set("selected_actor_id", 88)
	main.call("_sync_selection")
	_expect(not trade_button.disabled and trade_button.tooltip_text.contains("four tiles"),
		"living player selection enables the real trade request")
	app_state_inventory.call("_on_packet", 41,
		PackedByteArray([1, 65, 108, 105, 99, 101, 0]))
	app_state_inventory.call("_on_packet", 40,
		PackedByteArray([1, 3, 0, 9, 0, 0, 0, 7, 12]))
	app_state_inventory.call("_on_packet", 35,
		PackedByteArray([3, 0, 4, 0, 0, 0, 1, 2, 0]))
	app_state_inventory.call("_on_packet", 35,
		PackedByteArray([3, 0, 2, 0, 0, 0, 1, 2, 0]))
	app_state_inventory.call("_on_packet", 35,
		PackedByteArray([3, 0, 1, 0, 0, 0, 1, 2, 1]))
	app_state_inventory.call("_on_packet", 36, PackedByteArray([0, 1]))
	app_state_inventory.call("_on_packet", 36, PackedByteArray([1, 1]))
	main.call("_sync_trade")
	var trade_state: Dictionary = app_state_inventory.get("trade") as Dictionary
	var own_offers: Dictionary = trade_state.get("own_offers", {}) as Dictionary
	var accumulated_offer: Dictionary = own_offers.get(2, {}) as Dictionary
	_expect(trade_panel.visible and str(trade_state.get("partner", "")) == "Alice",
		"server partner and trade inventory open the real trade window")
	_expect(root.get_visible_rect().encloses(trade_panel.get_global_rect()),
		"trade window fits the reference viewport")
	var trade_source: ItemList = main.get_node(
		"GameView/TradePanel/Content/Columns/Source/TradeSource") as ItemList
	var trade_own_list: ItemList = main.get_node(
		"GameView/TradePanel/Content/Columns/Own/TradeOwnOffers") as ItemList
	var trade_other_list: ItemList = main.get_node(
		"GameView/TradePanel/Content/Columns/Other/TradeOtherOffers") as ItemList
	var trade_accept_button: Button = main.get_node(
		"GameView/TradePanel/Content/Actions/TradeAccept") as Button
	var trade_storage_destination: CheckBox = main.get_node(
		"GameView/TradePanel/Content/QuantityRow/TradeStorageDestination") as CheckBox
	_expect(trade_source.item_count == 1 and trade_own_list.item_count == 1
		and trade_other_list.item_count == 1,
		"trade source and own-offer columns render authoritative items")
	_expect(not trade_accept_button.disabled and trade_accept_button.text.contains("Confirm"),
		"mutual first acceptance enables the explicit confirmation phase")
	trade_other_list.select(0)
	main.call("_on_trade_other_selected", 0)
	main.call("_on_trade_storage_destination_toggled", true)
	var trade_destinations: PackedByteArray = main.get("trade_destinations") as PackedByteArray
	_expect(not trade_storage_destination.disabled and int(trade_destinations[2]) == 2,
		"storage-adjacent trade records a per-offer storage destination")
	_expect(int(accumulated_offer.get("quantity", 0)) == 6,
		"incremental trade offers accumulate in their authoritative slot")
	_expect(int(trade_state.get("own_accepts", 0)) == 1
		and int(trade_state.get("other_accepts", 0)) == 1,
		"two-sided trade acceptance state is tracked independently")
	app_state_inventory.call("_on_packet", 39, PackedByteArray([5, 0, 0, 0, 2, 0]))
	trade_state = app_state_inventory.get("trade") as Dictionary
	own_offers = trade_state.get("own_offers", {}) as Dictionary
	accumulated_offer = own_offers.get(2, {}) as Dictionary
	_expect(int(accumulated_offer.get("quantity", 0)) == 1,
		"partial offer removal preserves the remaining quantity")
	# The acceptance phase is read off the wire, not counted. A duplicate accept
	# must not advance the state machine, and a reordered pair must leave the
	# client agreeing with the last phase the server actually reported.
	app_state_inventory.call("_on_packet", 36, PackedByteArray([0, 1]))
	app_state_inventory.call("_on_packet", 36, PackedByteArray([0, 1]))
	_expect(int((app_state_inventory.get("trade") as Dictionary).get("own_accepts", -1)) == 1,
		"a duplicated accept packet does not advance the acceptance phase")
	app_state_inventory.call("_on_packet", 36, PackedByteArray([0, 2]))
	app_state_inventory.call("_on_packet", 36, PackedByteArray([0, 1]))
	_expect(int((app_state_inventory.get("trade") as Dictionary).get("own_accepts", -1)) == 1,
		"an out-of-order accept leaves the client on the phase the server last reported")
	app_state_inventory.call("_on_packet", 36, PackedByteArray([0, 2]))
	_expect(int((app_state_inventory.get("trade") as Dictionary).get("own_accepts", -1)) == 2,
		"the second acceptance phase is taken from the packet")
	app_state_inventory.call("_on_packet", 37, PackedByteArray([0]))
	_expect(int((app_state_inventory.get("trade") as Dictionary).get("own_accepts", -1)) == 0,
		"trade rejection resets the correct acceptance side")
	app_state_inventory.call("_on_packet", 38, PackedByteArray())
	main.call("_sync_trade")
	_expect(not trade_panel.visible
		and not bool((app_state_inventory.get("trade") as Dictionary).get("open", true)),
		"trade exit clears offers and closes the window")
	app_state_inventory.call("_on_packet", 67,
		PackedByteArray([1, 4, 70, 108, 111, 119, 101, 114, 115, 0]))
	app_state_inventory.call("_on_packet", 68,
		PackedByteArray([0, 4, 3, 0, 5, 0, 0, 0, 2, 0]))
	app_state_inventory.call("_on_packet", 69,
		PackedByteArray([132, 83, 116, 111, 114, 101, 100, 32, 115, 97, 102, 101, 108, 121, 0]))
	main.call("_sync_storage")
	var storage_panel: Control = main.get_node("GameView/StoragePanel") as Control
	var storage_categories: ItemList = main.get_node(
		"GameView/StoragePanel/Content/Columns/Categories/StorageCategories") as ItemList
	var storage_items: ItemList = main.get_node(
		"GameView/StoragePanel/Content/Columns/Stored/StorageItems") as ItemList
	var storage_status: Label = main.get_node(
		"GameView/StoragePanel/Content/StorageStatus") as Label
	_expect(storage_panel.visible and root.get_visible_rect().encloses(
		storage_panel.get_global_rect()), "server storage opens within the reference viewport")
	_expect(storage_categories.item_count == 1 and storage_items.item_count == 1
		and storage_status.text == "Stored safely",
		"storage categories, items, and inspection text render from server state")
	app_state_inventory.call("_on_packet", 68,
		PackedByteArray([255, 4, 3, 0, 7, 0, 0, 0, 2, 0]))
	var storage_state: Dictionary = app_state_inventory.get("storage") as Dictionary
	var stored_items: Dictionary = storage_state.get("items", {}) as Dictionary
	_expect(int((stored_items.get(2, {}) as Dictionary).get("quantity", 0)) == 7,
		"incremental storage updates replace the authoritative position")
	app_state_inventory.call("close_storage")
	main.call("_sync_storage")
	_expect(not storage_panel.visible, "storage close clears its local session window")
	var knowledge_panel: Control = main.get_node("GameView/StatsPanel") as Control
	var knowledge_button: Button = main.get_node(
		"GameView/Quickbar/QuickRows/Buttons/KnowledgeButton") as Button
	_expect(not knowledge_panel.visible and not knowledge_button.disabled,
		"knowledge window starts closed with its real HUD action enabled")
	app_state_inventory.call("_on_packet", 55, PackedByteArray([0x09]))
	main.call("_on_knowledge_button_pressed")
	var knowledge_list: ItemList = main.get_node(
		"GameView/StatsPanel/Content/StatsTabs/Knowledge/KnowledgeContent/Columns/KnowledgeList") as ItemList
	# The catalog is compiled from the profile this server runs, which has one
	# book. It used to be compiled from the unmodified Eternal Lands data the
	# fork was built on, and listed 385 the server has never heard of.
	_expect(knowledge_panel.visible and knowledge_list.item_count == 1
		and (main.get_node("GameView/StatsPanel/Content/StatsTabs") as TabContainer).current_tab == 1
		and root.get_visible_rect().encloses(knowledge_panel.get_global_rect()),
		"knowledge tab opens the served catalog within the statistics frame: %d"
			% knowledge_list.item_count)
	app_state_inventory.call("select_knowledge", 0)
	app_state_inventory.call("_on_packet", 57,
		PackedByteArray([77, 101, 116, 97, 108, 108, 117, 114, 103, 121, 0]))
	main.call("_sync_knowledge")
	var knowledge_detail: RichTextLabel = main.get_node(
		"GameView/StatsPanel/Content/StatsTabs/Knowledge/KnowledgeContent/Columns/KnowledgeDetail") as RichTextLabel
	_expect(knowledge_detail.text.contains("Metallurgy")
		and knowledge_detail.text.contains("Status: Read"),
		"selected knowledge renders server text and owned status")
	app_state_inventory.call("_on_packet", 56, PackedByteArray([2, 0]))
	var known_knowledge: Array = app_state_inventory.get("known_knowledge") as Array
	_expect(known_knowledge.has(2), "incremental knowledge acquisition updates ownership")
	main.call("_on_knowledge_close_pressed")
	var manufacturing_panel: Control = main.get_node("GameView/ManufacturingPanel") as Control
	var manufacturing_button: Button = main.get_node(
		"GameView/Quickbar/QuickRows/Buttons/ManufacturingButton") as Button
	_expect(not manufacturing_panel.visible and not manufacturing_button.disabled,
		"manufacturing window starts closed with its real HUD action enabled")
	# Recipe 0 on this profile is a Torch: a Wood Plank (39) and a Cloth Roll
	# (40), held with a Hatchet (7), which is checked but never consumed.
	app_state_inventory.set("inventory", {
		4: {"image_id": 39, "quantity": 1, "slot": 4, "flags": 6},
		5: {"image_id": 40, "quantity": 1, "slot": 5, "flags": 6},
		6: {"image_id": 7, "quantity": 1, "slot": 6, "flags": 6}})
	app_state_inventory.set("stats", {"food": 45, "ether": 0})
	main.call("_on_manufacturing_button_pressed")
	var manufacturing_list: ItemList = main.get_node(
		"GameView/ManufacturingPanel/Content/Columns/ManufacturingList") as ItemList
	var manufacturing_detail: RichTextLabel = main.get_node(
		"GameView/ManufacturingPanel/Content/Columns/ManufacturingDetail") as RichTextLabel
	var manufacturing_mix_one: Button = main.get_node(
		"GameView/ManufacturingPanel/Content/Actions/ManufacturingMixOne") as Button
	_expect(manufacturing_panel.visible and manufacturing_list.item_count == 32
		and root.get_visible_rect().encloses(manufacturing_panel.get_global_rect()),
		"the served recipe catalog opens within the reference viewport: %d"
			% manufacturing_list.item_count)
	main.call("_on_manufacturing_selected", 0)
	_expect(not manufacturing_mix_one.disabled
		and manufacturing_detail.text.contains("Torch")
		and manufacturing_detail.text.contains("Wood Plank ×1"),
		"available recipe resolves ingredients and enables the real server"
			+ " action: " + manufacturing_detail.text)
	app_state_inventory.set("inventory", {})
	main.call("_sync_manufacturing")
	_expect(manufacturing_mix_one.disabled
		and manufacturing_detail.text.contains("Missing Wood Plank ×1"),
		"inventory reconciliation disables a recipe with explicit missing"
			+ " ingredients: " + manufacturing_detail.text)
	main.call("_on_manufacturing_close_pressed")
	app_state_inventory.call("_on_packet", 28,
		PackedByteArray([1, 10, 0, 20, 0, 7]))
	app_state_inventory.set("local_actor_id", 77)
	app_state_inventory.set("actors", {77: {"actor_id": 77, "x": 10, "y": 20}})
	_expect(int(main.call("_ground_bag_below_player")) == 7,
		"Get All resolves only the ground bag on the player's exact tile")
	app_state_inventory.set("actors", {77: {"actor_id": 77, "x": 10, "y": 21}})
	_expect(int(main.call("_ground_bag_below_player")) == -1,
		"Get All does not take items from a nearby but non-overlapping bag")
	app_state_inventory.set("actors", {77: {"actor_id": 77, "x": 10, "y": 20}})
	main.call("_sync_ground_bags")
	var ground_bag_nodes: Dictionary = main.get("ground_bag_nodes") as Dictionary
	_expect(ground_bag_nodes.has(7) and ground_bag_nodes.get(7) is GroundBag3D,
		"server bag snapshot creates a pickable world marker")
	var bag_node: GroundBag3D = ground_bag_nodes.get(7) as GroundBag3D
	_expect(bag_node.collision_layer == GroundBag3D.PICK_LAYER
		and bag_node.server_tile == Vector2i(10, 20),
		"ground bag marker preserves its authoritative tile and pick layer")
	app_state_inventory.call("begin_ground_bag_inspection", 7)
	app_state_inventory.call("_on_packet", 23,
		PackedByteArray([1, 3, 0, 5, 0, 0, 0, 2]))
	main.call("_sync_ground_bag")
	var ground_bag_panel: Control = main.get_node("GameView/GroundBagPanel") as Control
	var ground_bag_slots: Array = main.get("ground_bag_slot_buttons") as Array
	var filled_bag_slots: int = 0
	for raw_slot_button: Variant in ground_bag_slots:
		if int((raw_slot_button as Button).get_meta("bag_position", -1)) >= 0:
			filled_bag_slots += 1
	var bag_inventory_panel: Control = main.get_node("GameView/InventoryPanel") as Control
	_expect(ground_bag_panel.visible and filled_bag_slots == 1
		and bag_inventory_panel.visible
		and not ground_bag_panel.get_global_rect().intersects(
			bag_inventory_panel.get_global_rect())
		and root.get_visible_rect().encloses(ground_bag_panel.get_global_rect())
		and root.get_visible_rect().encloses(bag_inventory_panel.get_global_rect()),
		"the bag opens beside the inventory, both inside the reference viewport")
	# Asking what is on the ground. The bag slot carries an image id and a
	# quantity, so a right click is the only way to learn what it is.
	_expect(int((ground_bag_slots[0] as Button).get_meta("bag_position", -1)) == 2
		and not (ground_bag_slots[0] as Button).disabled
		and int((ground_bag_slots[1] as Button).get_meta("bag_position", -1)) == -1
		and (ground_bag_slots[1] as Button).disabled,
		"filled bag slots carry their authoritative position and empty ones stay inert")
	_expect(int(main.call("_ground_bag_slot_position", 0)) == 2
		and int(main.call("_ground_bag_slot_position", 1)) == -1
		and int(main.call("_ground_bag_slot_position", 99)) == -1,
		"the ground Look target resolves only for a filled slot")
	app_state_inventory.call("_on_packet", 24,
		PackedByteArray([4, 0, 9, 0, 0, 0, 5]))
	var ground_bag_state: Dictionary = app_state_inventory.get("ground_bag") as Dictionary
	var ground_items_state: Dictionary = ground_bag_state.get("items", {}) as Dictionary
	_expect(ground_items_state.size() == 2
		and int((ground_items_state.get(5, {}) as Dictionary).get("quantity", 0)) == 9,
		"incremental ground item updates the open bag")
	app_state_inventory.call("_on_packet", 25, PackedByteArray([2]))
	ground_bag_state = app_state_inventory.get("ground_bag") as Dictionary
	ground_items_state = ground_bag_state.get("items", {}) as Dictionary
	_expect(not ground_items_state.has(2),
		"ground item removal clears the authoritative slot")
	app_state_inventory.call("_on_packet", 29, PackedByteArray([7]))
	main.call("_sync_ground_bags")
	main.call("_sync_ground_bag")
	_expect(not (app_state_inventory.get("ground_bags") as Dictionary).has(7)
		and not bool((app_state_inventory.get("ground_bag") as Dictionary).get("open", true)),
		"destroyed bag removes its world marker and closes its matching window")
	app_state_inventory.set("actors", {})
	app_state_inventory.set("selected_actor_id", -1)
	inventory_panel.hide()
	main.call("_on_inventory_button_pressed")
	_expect(inventory_panel.visible and not stats_panel.visible,
		"inventory action opens the window and centrally closes statistics")
	app_state_inventory.set("inventory", {0: {
		"image_id": 3, "quantity": 9, "slot": 0, "flags": 12,
		"inventory_usable": true, "stackable": true}, 36: {
		"image_id": 8, "quantity": 1, "slot": 36, "flags": 0,
		"inventory_usable": false, "stackable": false}})
	main.call("_sync_inventory")
	var first_inventory_slot: Button = main.get_node(
		"GameView/InventoryPanel/Content/InventoryBody/BackpackColumn/Scroll/InventoryGrid").get_child(0) as Button
	var first_quick_slot: Button = main.get_node(
		"GameView/ItemQuickbar/ItemSlots/Slot1") as Button
	var first_equipment_slot: Button = main.get_node(
		"GameView/InventoryPanel/Content/InventoryBody/EquipmentColumn/EquipmentGrid").get_child(0) as Button
	var first_quantity: Label = first_inventory_slot.get_node("Quantity") as Label
	_expect(first_inventory_slot.text.is_empty() and first_quantity.text == "9"
		and first_quantity.anchor_top == 1.0 and first_quantity.anchor_bottom == 1.0
		and first_quantity.horizontal_alignment == HORIZONTAL_ALIGNMENT_RIGHT
		and first_inventory_slot.icon != null and not first_inventory_slot.disabled
		and first_inventory_slot.custom_minimum_size.x >= 40.0,
		"large inventory icon uses an overlaid bottom-right quantity")
	# The count runs the width of the slot and steps down in size, so seven
	# digits are read whole rather than cut off part way through the number.
	_expect(first_quantity.anchor_left == 0.0 and first_quantity.anchor_right == 1.0,
		"the count has the whole width of the slot to be read in")
	_expect(first_quick_slot.text.is_empty() and first_quick_slot.icon != null
		and first_quick_slot.tooltip_text.contains("Quantity: 9")
		and not first_quick_slot.disabled,
		"usable inventory slot populates the icon-only vertical quick slot")
	_expect(first_equipment_slot.text.is_empty() and first_equipment_slot.icon != null
		and not first_equipment_slot.disabled
		and first_equipment_slot.custom_minimum_size.x >= 40.0,
		"large equipment icon renders without a slot or quantity number")
	main.set("selected_inventory_slot", 0)
	main.call("_sync_inventory")
	var empty_inventory_slot: Button = main.get_node(
		"GameView/InventoryPanel/Content/InventoryBody/BackpackColumn/Scroll/InventoryGrid").get_child(1) as Button
	var empty_equipment_slot: Button = main.get_node(
		"GameView/InventoryPanel/Content/InventoryBody/EquipmentColumn/EquipmentGrid").get_child(1) as Button
	_expect(not empty_inventory_slot.disabled
		and empty_inventory_slot.tooltip_text.contains("Move selected"),
		"selected backpack item can move to a chosen empty inventory slot")
	_expect(not empty_equipment_slot.disabled
		and empty_equipment_slot.tooltip_text.contains("Equip selected"),
		"selected backpack item can move to a chosen generic wear slot")
	main.set("selected_inventory_slot", 36)
	main.call("_sync_inventory")
	_expect(not empty_inventory_slot.disabled,
		"selected equipment can move to a chosen empty inventory slot")
	# Carrying an item on the cursor, the way the legacy client moves things.
	# The placing click is an authoritative move, so these assertions read the
	# client-side state machine rather than the wire.
	main.set("selected_inventory_slot", -1)
	main.set("_interaction_mode", "walk")
	app_state_inventory.set("inventory", {0: {
		"image_id": 3, "quantity": 9, "slot": 0, "flags": 12,
		"inventory_usable": true, "stackable": true}, 36: {
		"image_id": 8, "quantity": 1, "slot": 36, "flags": 0,
		"inventory_usable": false, "stackable": false}})
	main.call("_sync_inventory")
	var carried: TextureRect = main.get_node("GameView/CarriedItem") as TextureRect
	var carried_quantity: Label = carried.get_node("Quantity") as Label
	main.call("_on_inventory_slot_pressed", 0)
	_expect(int(main.get("_carried_slot")) == 0 and carried.visible
		and carried.texture != null and carried_quantity.text == "9",
		"walk mode lifts a clicked backpack item onto the cursor")
	main.call("_sync_inventory")
	_expect(not empty_inventory_slot.disabled and not empty_equipment_slot.disabled,
		"a carried item makes every empty inventory and wear slot a target")
	main.call("_on_inventory_slot_pressed", 0)
	_expect(int(main.get("_carried_slot")) == -1 and not carried.visible,
		"clicking the slot it came from puts a carried item back")
	main.call("_on_inventory_slot_pressed", 0)
	main.call("_on_equipment_slot_pressed", 37)
	_expect(int(main.get("_carried_slot")) == -1 and not carried.visible,
		"placing a carried backpack item on a wear slot equips and clears the cursor")
	main.call("_on_equipment_slot_pressed", 36)
	_expect(int(main.get("_carried_slot")) == 36 and carried.visible
		and carried_quantity.text.is_empty(),
		"equipped items lift too, and a single item shows no quantity")
	main.call("_on_inventory_slot_pressed", 1)
	_expect(int(main.get("_carried_slot")) == -1 and not carried.visible,
		"placing a carried equipped item in the backpack unequips it")
	main.call("_on_inventory_slot_pressed", 0)
	_expect(int(main.get("_carried_slot")) == 0, "item back on the cursor to be dropped")
	main.call("_drop_carry")
	_expect(int(main.get("_carried_slot")) == -1 and not carried.visible,
		"dropping a carried item to the world clears the cursor")
	main.call("_on_inventory_slot_pressed", 0)
	main.call("_cancel_carry")
	_expect(int(main.get("_carried_slot")) == -1 and not carried.visible,
		"cancelling returns a carried item without moving it")
	# A stack the server empties underneath the cursor must not stay attached.
	main.call("_on_inventory_slot_pressed", 0)
	app_state_inventory.set("inventory", {36: {
		"image_id": 8, "quantity": 1, "slot": 36, "flags": 0}})
	main.call("_update_carried_item")
	_expect(int(main.get("_carried_slot")) == -1 and not carried.visible,
		"a carried slot the server empties drops off the cursor")
	app_state_inventory.set("inventory", {0: {
		"image_id": 3, "quantity": 9, "slot": 0, "flags": 12,
		"inventory_usable": true, "stackable": true}, 36: {
		"image_id": 8, "quantity": 1, "slot": 36, "flags": 0}})
	main.set("_interaction_mode", "attack")
	main.set("selected_inventory_slot", -1)
	main.call("_on_inventory_slot_pressed", 0)
	_expect(int(main.get("_carried_slot")) == -1 and not carried.visible
		and int(main.get("selected_inventory_slot")) == 0,
		"outside walk mode a click still only selects the item")
	main.set("_interaction_mode", "walk")
	main.call("_cancel_carry")

	# The slots are the shape of the window: they are drawn whether or not
	# anything is selected or carried, because a disabled button has no frame.
	main.set("selected_inventory_slot", -1)
	main.call("_sync_inventory")
	_expect(not empty_inventory_slot.disabled and not empty_equipment_slot.disabled
		and empty_inventory_slot.tooltip_text.contains("Empty inventory slot")
		and empty_equipment_slot.tooltip_text.contains("Empty generic"),
		"empty inventory and wear slots stay drawn with nothing selected")

	# Right click steps through the tools, and the buttons choose the same ones.
	var inventory_description: RichTextLabel = main.get_node(
		"GameView/InventoryPanel/Content/InventoryBody/BackpackColumn/InventoryDescription"
		) as RichTextLabel
	var use_button: Button = main.get("inventory_use_button") as Button
	var inspect_button: Button = main.get("inventory_inspect_button") as Button
	main.call("_set_inventory_tool", "grab")
	main.call("_cycle_inventory_tool", 0)
	_expect(str(main.get("_inventory_tool")) == "use" and use_button.button_pressed,
		"right clicking an item takes the next tool and the button says so")
	main.call("_cycle_inventory_tool", 0)
	_expect(str(main.get("_inventory_tool")) == "inspect"
		and inspect_button.button_pressed and not use_button.button_pressed,
		"right clicking again takes the one after it")
	main.call("_cycle_inventory_tool", 0)
	_expect(str(main.get("_inventory_tool")) == "grab",
		"and a third right click comes back round to move")
	main.call("_on_inventory_unequip_pressed")
	_expect(str(main.get("_inventory_tool")) == "unequip"
		and (main.get("inventory_unequip_button") as Button).button_pressed,
		"the action buttons choose a tool the same way the right click does")

	# The description line is written whichever tool asked for the item; only
	# Inspect is allowed to open the card over the top of it.
	var extension_windows: Control = main.get("extension_windows") as Control
	var detail_panel: PanelContainer = extension_windows.get(
		"detail_panel") as PanelContainer
	var bread_detail := {"open": true, "name": "Hearth Bread", "category": "Food",
		"quantity": 4, "description": "Baked before dawn.", "equipped": false}
	# The client ignores state changes before login, as it should; these
	# assertions are about a session in progress. The flag is put back below,
	# because a later case checks the diagnostics path without one.
	var was_authenticated: bool = bool(app_state_inventory.get("authenticated"))
	app_state_inventory.set("authenticated", true)
	main.call("_set_inventory_tool", "grab")
	main.call("_describe_slot", 0, false)
	app_state_inventory.set("item_detail", bread_detail)
	app_state_inventory.emit_signal("state_changed", &"item_detail")
	await process_frame
	_expect(not detail_panel.visible
		and inventory_description.text.contains("Hearth Bread")
		and inventory_description.text.contains("Food")
		and inventory_description.text.contains("Move"),
		"a move click writes the short line and opens nothing: "
			+ inventory_description.text)
	main.set("selected_inventory_slot", 0)
	main.call("_on_inventory_inspect_pressed")
	app_state_inventory.set("item_detail", bread_detail)
	app_state_inventory.emit_signal("state_changed", &"item_detail")
	await process_frame
	_expect(detail_panel.visible
		and inventory_description.text.contains("Hearth Bread"),
		"Inspect opens the card and still writes the short line")
	app_state_inventory.call("close_item_detail")
	await process_frame
	main.call("_set_inventory_tool", "grab")
	main.set("selected_inventory_slot", -1)
	app_state_inventory.set("authenticated", was_authenticated)

	# The bag window resizes by the same drag as the inventory, and separately.
	var bag_panel: Control = main.get_node("GameView/GroundBagPanel") as Control
	var bag_grip: Button = main.get_node(
		"GameView/GroundBagPanel/Content/GroundBagFooter/GroundBagResizeGrip"
		) as Button
	_expect(bag_grip != null and bag_grip.tooltip_text.contains("resize"),
		"the bag carries its own resize grip")
	var inventory_scale_before: float = inventory_panel.scale.x
	main.call("_apply_ground_bag_scale", 1.4)
	_expect(is_equal_approx(bag_panel.scale.x, 1.4)
		and is_equal_approx(bag_panel.scale.y, 1.4)
		and is_equal_approx(inventory_panel.scale.x, inventory_scale_before),
		"dragging the bag grip scales the bag and leaves the inventory alone: "
			+ "%f, %f" % [bag_panel.scale.x, inventory_panel.scale.x])
	main.call("_apply_ground_bag_scale", 0.05)
	_expect(is_equal_approx(bag_panel.scale.x, 0.65),
		"and the bag cannot be shrunk past legibility: %f" % bag_panel.scale.x)
	main.call("_apply_ground_bag_scale", 1.0)
	_expect(root.get_visible_rect().encloses(bag_panel.get_global_rect())
		and root.get_visible_rect().encloses(inventory_panel.get_global_rect()),
		"both windows stay on a 1280x720 screen: %s, %s"
			% [bag_panel.get_global_rect(), inventory_panel.get_global_rect()])

	# The six quantity boxes along the bottom, as the legacy client has them.
	var quantity_bar: HBoxContainer = main.get_node(
		"GameView/InventoryPanel/Content/InventoryQuantityBar") as HBoxContainer
	var quantity_boxes: Array = main.get("inventory_quantity_buttons") as Array
	_expect(quantity_bar.get_child_count() == 6 and quantity_boxes.size() == 6
		and (quantity_boxes[0] as Button).text == "1"
		and (quantity_boxes[1] as Button).text == "5"
		and (quantity_boxes[5] as Button).text == "100",
		"the inventory carries six quantity boxes with the legacy defaults")
	_expect((quantity_boxes[0] as Button).button_pressed
		and int(main.call("_selected_quantity")) == 1,
		"the first quantity box starts selected")
	main.call("_on_quantity_box_pressed", 2)
	_expect(int(main.call("_selected_quantity")) == 10
		and (quantity_boxes[2] as Button).button_pressed
		and not (quantity_boxes[0] as Button).button_pressed,
		"clicking a quantity box selects it for every later drop and pick-up")
	var quantity_edit: LineEdit = main.get_node(
		"GameView/InventoryPanel/Content/InventoryQuantityEdit") as LineEdit
	main.call("_begin_quantity_edit", 3)
	_expect(quantity_edit.visible and quantity_edit.text == "20",
		"right clicking a quantity box opens it for editing")
	quantity_edit.text = "42"
	main.call("_commit_quantity_edit")
	_expect(int(main.call("_selected_quantity")) == 42
		and (quantity_boxes[3] as Button).text == "42"
		and not quantity_edit.visible,
		"an edited quantity is kept and becomes the selected one")
	main.call("_begin_quantity_edit", 3)
	quantity_edit.text = ""
	main.call("_commit_quantity_edit")
	_expect(int(main.call("_selected_quantity")) == 20
		and (quantity_boxes[3] as Button).text == "20",
		"clearing a quantity box restores its default rather than leaving zero")
	# Seven digits: a stack runs into the millions on a long-lived character,
	# in the box that moves it and in the count drawn over the slot.
	var big_stack: Dictionary = (app_state_inventory.get("inventory") as Dictionary).duplicate(true)
	big_stack[0] = {"image_id": 3, "quantity": 1234567, "slot": 0,
		"inventory_usable": true, "stackable": true}
	app_state_inventory.set("inventory", big_stack)
	main.call("_sync_inventory")
	_expect(first_quantity.text == "1234567"
		and first_quantity.get_theme_font_size("font_size")
			* first_quantity.text.length() <= first_quantity.size.x * 1.6,
		"a seven-digit stack count is drawn whole over its slot: %s at %d px in %f"
			% [first_quantity.text,
				first_quantity.get_theme_font_size("font_size"),
				first_quantity.size.x])
	_expect(quantity_edit.max_length == 7,
		"the quantity box takes seven digits: %d" % quantity_edit.max_length)
	main.call("_begin_quantity_edit", 4)
	quantity_edit.text = "1234567"
	main.call("_commit_quantity_edit")
	_expect(int(main.call("_selected_quantity")) == 1234567
		and (quantity_boxes[4] as Button).text == "1234567",
		"a seven-digit quantity is kept whole: %s" % (quantity_boxes[4] as Button).text)
	main.call("_begin_quantity_edit", 4)
	quantity_edit.text = "88888888"
	main.call("_commit_quantity_edit")
	_expect(int(main.call("_selected_quantity")) == 8888888,
		"an eighth digit does not fit in the box rather than being taken and"
			+ " silently altered: %d" % int(main.call("_selected_quantity")))
	# Put the box back, since these suites share one settings file.
	main.call("_begin_quantity_edit", 4)
	quantity_edit.text = ""
	main.call("_commit_quantity_edit")
	# Pick-ups and drops clamp to what is actually there.
	main.call("_on_quantity_box_pressed", 5)
	app_state_inventory.set("inventory", {0: {
		"image_id": 3, "quantity": 9, "slot": 0, "flags": 12,
		"inventory_usable": true, "stackable": true}})
	main.set("selected_inventory_slot", 0)
	main.call("_sync_ground_bag_actions")
	var bag_drop_button: Button = main.get_node(
		"GameView/GroundBagPanel/Content/Actions/GroundBagDrop") as Button
	_expect(bag_drop_button.tooltip_text.contains("Drop 9 of the 9"),
		"a quantity larger than the stack drops only what is there: "
		+ bag_drop_button.tooltip_text)
	main.call("_on_quantity_box_pressed", 1)
	main.call("_sync_ground_bag_actions")
	_expect(bag_drop_button.tooltip_text.contains("Drop 5 of the 9"),
		"a quantity smaller than the stack drops exactly that many: "
		+ bag_drop_button.tooltip_text)
	main.call("_on_quantity_box_pressed", 0)
	app_state_inventory.set("inventory_cooldowns", {0: {
		"maximum_msec": 30000, "end_msec": Time.get_ticks_msec() + 12000}})
	main.call("_sync_quick_slots")
	_expect(first_quick_slot.disabled and first_quick_slot.tooltip_text.contains("12 seconds"),
		"server cooldown disables the usable quick slot with remaining time")
	app_state_inventory.set("inventory_cooldowns", {})
	for quick_index: int in range(1, 9):
		_expect(InputMap.has_action("quick_item_%d" % quick_index),
			"item quick slot %d has a centralized input action" % quick_index)
	var ready_sigils: Array[int] = [3, 23]
	app_state_inventory.set("owned_sigils", ready_sigils)
	app_state_inventory.set("pending_spell_target", "")
	app_state_inventory.set("stats", {"magic": 0, "ether": 5})
	app_state_inventory.set("inventory", {0: {
		"image_id": 59, "quantity": 1, "slot": 0, "flags": 6}})
	main.call("_sync_spells")
	var first_spell_slot: Button = main.get_node(
		"GameView/SpellQuickbar/SpellContent/SpellSlots/Spell1") as Button
	_expect(not first_spell_slot.disabled,
		"owned castable spell is enabled; tooltip=" + first_spell_slot.tooltip_text)
	_expect(first_spell_slot.icon != null, "owned castable spell has its legacy icon")
	_expect(first_spell_slot.tooltip_text.contains("Heal"),
		"owned castable spell tooltip identifies Heal: " + first_spell_slot.tooltip_text)
	var no_sigils: Array[int] = []
	app_state_inventory.set("owned_sigils", no_sigils)
	main.call("_sync_spells")
	_expect(first_spell_slot.disabled and first_spell_slot.tooltip_text.contains("Missing sigils"),
		"unowned spell is visibly disabled with the exact availability reason")
	for spell_index: int in range(1, 7):
		_expect(InputMap.has_action("quick_spell_%d" % spell_index),
			"spell quick slot %d has a centralized input action" % spell_index)
	_expect(InputMap.has_action("attack_selected"),
		"combat attack has a centralized input action")
	app_state_inventory.set("inventory", {})
	app_state_inventory.set("stats", {})
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
	# The preview renders one character, not the map furniture bolted to it.
	# Its camera had no cull mask, so it drew every layer, and the dot an actor
	# carries for the two map cameras - three and a half metres across, three
	# metres up - hung over the model as a pale blue band.
	var preview_camera: Camera3D = main.get_node(
		"CreationPanel/Columns/CharacterPreview/Viewport/PreviewRoot/PreviewCamera"
		) as Camera3D
	var preview_ground: MeshInstance3D = main.get_node(
		"CreationPanel/Columns/CharacterPreview/Viewport/PreviewRoot/PreviewGround"
		) as MeshInstance3D
	var world_camera: Camera3D = camera_rig.get_node("Camera") as Camera3D
	_expect(preview_camera.cull_mask == world_camera.cull_mask
		and (preview_camera.cull_mask & ReplicatedActor3D.MAP_MARKER_LAYER) == 0,
		"the creation preview renders what the gameplay camera renders,"
			+ " and not the map layer")
	_expect(preview_ground.mesh != null
		and (preview_ground.layers & preview_camera.cull_mask) != 0
		and preview_ground.position.y < 0.0,
		"the creation preview stands its character on a piece of ground")
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
	main.set("_minimap_orientation", "viewport_up")
	camera_rig.yaw_degrees = 37.0
	main.call("_update_local_actor_follow")
	_expect(is_equal_approx(map_camera.rotation.y, deg_to_rad(37.0)),
		"viewport-up minimap tracks camera yaw independently of actor facing")
	chat_input.release_focus()
	var recenter_key: InputEventKey = InputEventKey.new()
	recenter_key.pressed = true
	recenter_key.physical_keycode = KEY_SPACE
	main.call("_input", recenter_key)
	_expect(camera_rig.pan_offset.is_zero_approx(),
		"Space recenters the viewport on the local player when chat is inactive")
	main.set("_minimap_orientation", "north_up")
	app_state.set("local_actor_id", previous_local_actor_id)
	follow_actor.queue_free()

	# The minimap frame holds absolutely positioned children: the map inset by the
	# compass border, and four cardinal labels that main.gd places on a ring.
	# A Container parent re-sorts those children over that layout the moment the
	# frame is shown, so the frame must not be one.
	_expect(not (minimap_frame is Container),
		"the minimap frame does not re-sort its absolutely positioned children")
	minimap_frame.show()
	for _frame: int in range(3):
		await process_frame
	var minimap_border: float = roundf(
		float(main.get("MINIMAP_DRAG_BORDER")) * float(main.get("_minimap_scale")))
	_expect(minimap_image.position.is_equal_approx(Vector2.ONE * minimap_border)
		and minimap_image.size.is_equal_approx(
			minimap_frame.size - Vector2.ONE * minimap_border * 2.0),
		"showing the minimap keeps the map inset inside the compass border")
	var north_label: Control = main.get_node("GameView/MinimapFrame/North") as Control
	var east_label: Control = main.get_node("GameView/MinimapFrame/East") as Control
	_expect(north_label.size.x < minimap_frame.size.x * 0.5
		and not north_label.position.is_equal_approx(east_label.position),
		"showing the minimap keeps the cardinal labels on the compass ring")
	var shown_centre: Vector2 = main.call("_control_to_viewport_position",
		minimap_image.size * 0.5, minimap_image.size, minimap_viewport.size) as Vector2
	_expect(shown_centre.is_equal_approx(Vector2(minimap_viewport.size) * 0.5),
		"a visible minimap still converts clicks into minimap viewport pixels")
	minimap_frame.hide()
	await process_frame

	_expect(container.texture == world_viewport.get_texture(),
		"the gameplay view draws the world render target")
	root.size = Vector2i(2560, 1440)
	await process_frame
	main.call("_on_window_size_changed")
	_expect(world_viewport.size == Vector2i(2560, 1440),
		"enlarging the window raises the world render resolution instead of upscaling")
	main.call("_on_ui_scale_changed", 0.5)
	await process_frame
	_expect(is_equal_approx(root.content_scale_factor, 0.5)
		and container.size.is_equal_approx(Vector2(2560, 1440)),
		"UI scale trades HUD size for canvas space")
	_expect(world_viewport.size == Vector2i(2560, 1440),
		"UI scale leaves the world render resolution at the window pixel size")
	main.call("_on_ui_scale_changed", 1.0)
	await process_frame
	root.size = original_window_size
	await process_frame

	# Perks and lifetime counters are authoritative server state. The client
	# keeps no perk name table and no counter of its own.
	var counter_categories: ItemList = main.get_node(
		"GameView/StatsPanel/Content/StatsTabs/Counters/CounterColumns/CounterCategories") as ItemList
	var counter_text: RichTextLabel = main.get_node(
		"GameView/StatsPanel/Content/StatsTabs/Counters/CounterColumns/CounterText") as RichTextLabel
	_expect(counter_categories.item_count == 0,
		"the counter window ships with no locally invented categories")
	var stats_text: RichTextLabel = main.get_node(
		"GameView/StatsPanel/Content/StatsTabs/Statistics/StatsText") as RichTextLabel
	# Drive the real signal path rather than calling the sync helpers directly,
	# so a missing state_changed case would fail here.
	var previously_authenticated: bool = bool(app_state_inventory.get("authenticated"))
	app_state_inventory.set("authenticated", true)
	app_state_inventory.set("stats", {"health": 10, "max_health": 10})
	var perks_payload: PackedByteArray = PackedByteArray([1, 0, 1, 0xfb, 0xff])
	perks_payload.append_array(_nul_bytes("Power Hungry"))
	perks_payload.append_array(_nul_bytes("Lose 3 food per minute."))
	app_state_inventory.call("_on_packet", 234, perks_payload)
	var reduced_perks: Array = app_state_inventory.get("perks") as Array
	_expect(reduced_perks.size() == 1
		and str((reduced_perks[0] as Dictionary).get("name", "")) == "Power Hungry"
		and bool((reduced_perks[0] as Dictionary).get("from_gear", false)),
		"a perk the client has never heard of is still reduced and flagged")
	_expect(stats_text.text.contains("Power Hungry")
		and stats_text.text.contains("from equipment"),
		"the statistics window presents the server's perks, not a scraped list")
	app_state_inventory.call("_on_packet", 234, PackedByteArray([0, 0]))
	_expect((app_state_inventory.get("perks") as Array).is_empty()
		and not stats_text.text.contains("Power Hungry"),
		"an empty perk packet clears the presented perks")

	var counters_snapshot: PackedByteArray = PackedByteArray([1, 2, 4, 0, 0, 0])
	counters_snapshot.append_array(_nul_bytes("Kills"))
	counters_snapshot.append_array(PackedByteArray([7, 0, 0, 0]))
	counters_snapshot.append_array(_nul_bytes("Harvests"))
	app_state_inventory.call("_on_packet", 235, counters_snapshot)
	_expect(counter_categories.item_count == 2
		and counter_categories.get_item_text(0) == "Kills"
		and counter_categories.get_item_text(1) == "Harvests",
		"the counter category list is built from the server snapshot in its order")
	main.call("_on_counter_category_selected", 1)
	_expect(counter_text.text.contains("Harvests") and counter_text.text.contains("7"),
		"selecting a category presents the server total")
	var counter_delta: PackedByteArray = PackedByteArray([0, 1, 9, 0, 0, 0])
	counter_delta.append_array(_nul_bytes("Harvests"))
	app_state_inventory.call("_on_packet", 235, counter_delta)
	_expect(int((app_state_inventory.get("activity_counters") as Dictionary).get(
		"Harvests", -1)) == 9 and counter_categories.item_count == 2,
		"a delta updates one total without disturbing the category list")
	main.call("_reset_session_tracking")
	main.call("_on_counter_category_selected", 1)
	_expect(counter_text.text.contains("9"),
		"resetting the session keeps the authoritative lifetime total")
	var counter_after_reset: PackedByteArray = PackedByteArray([0, 1, 11, 0, 0, 0])
	counter_after_reset.append_array(_nul_bytes("Harvests"))
	app_state_inventory.call("_on_packet", 235, counter_after_reset)
	_expect(counter_text.text.contains("11"),
		"the session column is a difference against the server total, not a second count")
	app_state_inventory.set("authenticated", previously_authenticated)

	# Protocol diagnostics. Every undecoded packet and decode error used to be
	# reduced into AppState and emitted with no listener at all, which is how
	# most of the gaps in this client went unnoticed.
	var console_panel: Control = main.get_node("GameView/ConsolePanel") as Control
	var console_output: RichTextLabel = main.get_node(
		"GameView/ConsolePanel/Content/ConsoleOutput") as RichTextLabel
	var diagnostics_button: Button = main.get_node(
		"GameView/ConsolePanel/Content/Header/ConsoleDiagnostics") as Button
	var diagnostics_output: RichTextLabel = main.get_node(
		"GameView/ConsolePanel/Content/DiagnosticsOutput") as RichTextLabel
	_expect(diagnostics_button.toggle_mode and not diagnostics_output.visible
		and console_output.visible,
		"the console opens on its message history with diagnostics one click away")
	main.call("_toggle_console")
	diagnostics_button.button_pressed = true
	await process_frame
	_expect(diagnostics_output.visible and not console_output.visible,
		"the diagnostics view replaces the message history in the console panel")
	_expect(diagnostics_output.text.contains("none"),
		"a clean session reports no undecoded opcodes and no decode errors")
	# 199 is not a server opcode this client knows; 36 with a one-byte payload
	# is the pre-0.6 trade accept, which must now fail to decode.
	app_state_inventory.call("_on_packet", 199, PackedByteArray([1, 2, 3]))
	app_state_inventory.call("_on_packet", 199, PackedByteArray([4]))
	app_state_inventory.call("_on_packet", 36, PackedByteArray([0]))
	await process_frame
	_expect(diagnostics_output.text.contains("199")
		and diagnostics_output.text.contains("x2"),
		"an undecoded opcode is listed once with the number of times it arrived")
	_expect(diagnostics_output.text.contains("trade_accept_length"),
		"a decode error names the packet and the failure")
	_expect(int(app_state_inventory.get("unknown_packet_count")) == 2
		and (app_state_inventory.get("unknown_packets") as Dictionary).size() == 1,
		"the same unknown opcode is counted, not re-listed")
	# The panel has to work before login: a handshake decode failure is exactly
	# what it exists to show, and the state-changed handler gates everything else on
	# an authenticated session.
	_expect(not bool(app_state_inventory.get("authenticated")),
		"the diagnostics assertions above ran on an unauthenticated session")
	root.size = Vector2i(1280, 720)
	await process_frame
	main.call("_on_window_size_changed")
	await process_frame
	var console_rect: Rect2 = console_panel.get_global_rect()
	_expect(console_rect.position.x >= 0.0 and console_rect.position.y >= 0.0
		and console_rect.end.x <= 1280.0 and console_rect.end.y <= 720.0,
		"the console panel with diagnostics still fits within 1280x720")
	_expect(not console_rect.intersects(right_stats.get_global_rect()),
		"the console panel with diagnostics does not cover the fixed resource rail")
	var console_escape: InputEventKey = InputMap.action_get_events(
		"cancel")[0].duplicate() as InputEventKey
	console_escape.pressed = true
	main.call("_input", console_escape)
	_expect(not console_panel.visible,
		"the console panel with diagnostics open still answers the cancel cascade")
	diagnostics_button.button_pressed = false
	await process_frame

	# Decoded fields with a consumer: research progress and cooldown art.
	app_state_inventory.set("stats", {"health": 10, "max_health": 10,
		"researching": 1024, "research_completed": 0, "research_total": 0})
	main.call("_sync_stats")
	_expect(stats_text.text.contains("Researching")
		and stats_text.text.contains("nothing"),
		"a character reading nothing says so instead of hiding the field")
	app_state_inventory.set("stats", {"health": 10, "max_health": 10,
		"researching": 0, "research_completed": 30, "research_total": 120})
	main.call("_sync_stats")
	_expect(stats_text.text.contains("30/120") and stats_text.text.contains("25%"),
		"reading progress is presented from the authoritative research statistics")

	var cooldown_slot: Button = (main.get("quick_slot_buttons") as Array)[0] as Button
	var cooldowns: Dictionary = app_state_inventory.get("inventory_cooldowns") as Dictionary
	cooldowns.clear()
	main.call("_update_cooldown_overlays")
	var cooldown_overlay: Control = cooldown_slot.get_node_or_null("Cooldown") as Control
	_expect(cooldown_overlay != null and not cooldown_overlay.visible,
		"a slot with no cooldown draws no cooldown art")
	cooldowns[0] = {"maximum_msec": 10000,
		"end_msec": Time.get_ticks_msec() + 10000}
	main.call("_update_cooldown_overlays")
	_expect(cooldown_overlay.visible
		and is_equal_approx(snappedf(cooldown_overlay.anchor_top, 0.05), 0.0),
		"a cooldown at its full duration covers the whole slot")
	cooldowns[0] = {"maximum_msec": 10000,
		"end_msec": Time.get_ticks_msec() + 2500}
	main.call("_update_cooldown_overlays")
	_expect(is_equal_approx(snappedf(cooldown_overlay.anchor_top, 0.05), 0.75),
		"a quarter-remaining cooldown draws a quarter of the slot")
	_expect((cooldown_overlay.get_node("Seconds") as Label).text == "3",
		"the cooldown art also states the seconds remaining")
	cooldowns[0] = {"maximum_msec": 10000, "end_msec": Time.get_ticks_msec() - 1}
	main.call("_update_cooldown_overlays")
	_expect(not cooldown_overlay.visible, "an expired cooldown clears its art")
	cooldowns.clear()

	# Server popups. The server had no way to ask the player anything: the
	# packet fell through to "unknown" and the reply had no encoder.
	var popup_panel: PanelContainer = main.get_node(
		"GameView/PopupPanel") as PanelContainer
	var popup_options: VBoxContainer = main.get_node(
		"GameView/PopupPanel/PopupContent/PopupOptions") as VBoxContainer
	var popup_confirm: Button = main.get_node(
		"GameView/PopupPanel/PopupContent/PopupActions/PopupConfirm") as Button
	var full_map: Control = main.get_node("GameView/FullMap") as Control
	_expect(not popup_panel.visible, "the popup window starts closed")
	var radio_popup: PackedByteArray = PackedByteArray([0, 0, 0])
	radio_popup.append_array(_sized_bytes("Summon Behavior"))
	radio_popup.append_array(PackedByteArray([0x68, 0x01]))
	radio_popup.append_array(_sized_bytes("Choose how your summons pick targets."))
	radio_popup.append_array(PackedByteArray([9, 1]))
	radio_popup.append_array(_sized_bytes("Weakest first"))
	radio_popup.append(0)
	radio_popup.append_array(PackedByteArray([9, 1]))
	radio_popup.append_array(_sized_bytes("Strongest first"))
	radio_popup.append(1)
	app_state_inventory.set("authenticated", true)
	console_panel.show()
	full_map.show()
	app_state_inventory.call("_on_packet", 83, radio_popup)
	await process_frame
	_expect(popup_panel.visible and not console_panel.visible and not full_map.visible,
		"a popup is modal: it opens and closes the panels underneath it")
	_expect(popup_confirm.visible,
		"a popup with radio options gets a send button, as the legacy contract requires")
	var checkboxes: Array[CheckBox] = []
	for child: Node in popup_options.get_children():
		if child is CheckBox:
			checkboxes.append(child as CheckBox)
	_expect(checkboxes.size() == 2
		and checkboxes[0].text == "Weakest first"
		and checkboxes[1].text == "Strongest first",
		"both radio options are presented with their server labels")
	checkboxes[0].button_pressed = true
	checkboxes[1].button_pressed = true
	await process_frame
	_expect(not checkboxes[0].button_pressed and checkboxes[1].button_pressed,
		"one selection per group: the wire carries exactly one answer per group")
	_expect(int((main.get("_popup_radio_groups") as Dictionary).get(1, -1)) == 1,
		"the selected radio value is the server's value, not the button index")
	var popup_rect: Rect2 = popup_panel.get_global_rect()
	_expect(popup_rect.position.x >= 0.0 and popup_rect.position.y >= 0.0
		and popup_rect.end.x <= 1280.0 and popup_rect.end.y <= 720.0,
		"the popup fits within 1280x720")
	_expect(not popup_rect.intersects(right_stats.get_global_rect()),
		"the popup does not cover the fixed resource rail")
	# The cancel cascade: a modal popup answers Escape before anything under it.
	var popup_escape: InputEventKey = InputMap.action_get_events(
		"cancel")[0].duplicate() as InputEventKey
	popup_escape.pressed = true
	main.call("_unhandled_input", popup_escape)
	await process_frame
	_expect(not popup_panel.visible
		and not bool((app_state_inventory.get("popup") as Dictionary).get("open", true)),
		"cancel dismisses the popup")

	# A popup built only from text options answers on the click itself.
	var action_popup: PackedByteArray = PackedByteArray([5, 0, 0])
	action_popup.append_array(_sized_bytes("Confirm"))
	action_popup.append_array(PackedByteArray([0x2c, 0x01]))
	action_popup.append_array(_sized_bytes("Really?"))
	action_popup.append_array(PackedByteArray([8, 3]))
	action_popup.append_array(_sized_bytes("Yes"))
	action_popup.append(1)
	app_state_inventory.call("_on_packet", 83, action_popup)
	await process_frame
	_expect(popup_panel.visible and not popup_confirm.visible,
		"a popup of text options only needs no send button")
	# The same popup arriving twice must not reopen or duplicate its options.
	var option_count: int = popup_options.get_child_count()
	app_state_inventory.call("_on_packet", 83, action_popup)
	await process_frame
	_expect(popup_options.get_child_count() == option_count,
		"a repeated popup for an id already on screen is ignored")
	for child: Node in popup_options.get_children():
		if child is Button:
			(child as Button).pressed.emit()
			break
	await process_frame
	# There is no connection in this suite, so the reply could not be sent. The
	# popup must stay open rather than pretending the server was answered; the
	# close-on-success path is proved against a real server in
	# tests/integration/popup_local.py.
	_expect(popup_panel.visible
		and bool((app_state_inventory.get("popup") as Dictionary).get("open", false)),
		"an answer that could not be sent leaves the popup open")
	app_state_inventory.call("close_popup")
	await process_frame
	_expect(not popup_panel.visible, "closing the popup state closes the window")
	app_state_inventory.set("authenticated", false)
	console_panel.hide()
	full_map.hide()

	# Harvesting and world-object interaction. The world click handler tried
	# actors, then ground bags, then the navigation surface, and stopped: no
	# rendered prop was ever clickable, so the whole harvestable layer and
	# every interactive were unreachable.
	var harvest_banner: Label = main.get_node("GameView/HarvestBanner") as Label
	_expect(not harvest_banner.visible, "the harvesting indicator starts hidden")
	var objects_payload: PackedByteArray = PackedByteArray([1, 2, 0])
	objects_payload.append_array(PackedByteArray([
		0xf0, 0x01, EloriaProtocol.MAP_OBJECT_HARVEST, 0x02, 0x03, 0xe1, 0x01]))
	objects_payload.append_array(_nul_bytes("Mirror Reed"))
	objects_payload.append_array(_nul_bytes("Harvesting level 0"))
	objects_payload.append_array(PackedByteArray([
		0x0e, 0x00, EloriaProtocol.MAP_OBJECT_INTERACTIVE, 0x00, 0x03, 0x90, 0x05]))
	objects_payload.append_array(_nul_bytes("Storage"))
	objects_payload.append_array(_nul_bytes("A wayfarer's cache."))
	app_state_inventory.set("authenticated", true)
	app_state_inventory.call("_on_packet", 236, objects_payload)
	await process_frame
	var object_nodes: Dictionary = main.get("map_object_nodes") as Dictionary
	_expect(object_nodes.size() == 2,
		"every server world object becomes a pick target in the scene")
	var harvest_node: MapObject3D = object_nodes.get(496) as MapObject3D
	var interactive_node: MapObject3D = object_nodes.get(14) as MapObject3D
	_expect(harvest_node != null and harvest_node.is_harvestable()
		and interactive_node != null and not interactive_node.is_harvestable(),
		"harvest nodes and interactives are told apart by the server's kind")
	_expect(harvest_node != null
		and harvest_node.collision_layer == MapObject3D.PICK_LAYER
		and harvest_node.collision_layer != GroundBag3D.PICK_LAYER,
		"world objects pick on their own layer, not the ground-bag layer")
	_expect(harvest_node != null
		and harvest_node.get_node_or_null("MapMarker") != null,
		"a world object is visible on both map cameras")
	# The prop, not a ring: the reed bed and the wayfarer's cache stand on the
	# tile, and the ring is left for the node being harvested.
	_expect(harvest_node != null and harvest_node.get_node_or_null("Model") != null
		and harvest_node.model_id == "mirror_reed"
		and interactive_node != null and interactive_node.get_node_or_null("Model") != null
		and interactive_node.model_id == "storage",
		"a world object stands as the resource or the service it is")
	var harvest_ring: MeshInstance3D = (harvest_node.get_node_or_null("Ring")
		as MeshInstance3D) if harvest_node != null else null
	_expect(harvest_ring != null and not harvest_ring.visible,
		"the placeholder ring is not drawn under a node that has a model")
	var interactive_marker: MeshInstance3D = (
		interactive_node.get_node_or_null("MapMarker") as MeshInstance3D
	) if interactive_node != null else null
	var interactive_material: StandardMaterial3D = (
		interactive_marker.mesh.surface_get_material(0) as StandardMaterial3D
	) if interactive_marker != null else null
	_expect(interactive_material != null
		and interactive_material.albedo_color.is_equal_approx(
			MapObject3D.INTERACTIVE_COLOUR),
		"an interactive is orange on the map, as the legend says")
	var map_legend: RichTextLabel = main.get_node(
		"GameView/FullMap/MapLayout/Sidebar/SidebarContent/MapLegend") as RichTextLabel
	_expect(map_legend != null and map_legend.text.contains("Harvest node")
		and map_legend.text.contains("Interactive")
		and map_legend.text.contains("NPC"),
		"the legend names every colour the map draws")
	# Each of the three is the colour the legend's own swatch is written in, so
	# a reader comparing the sidebar to the map is comparing like with like.
	_expect(map_legend != null
		and map_legend.text.contains("[color=#%s]●[/color] NPC" % (
			ReplicatedActor3D.MAP_DOT_COLOUR.to_html(false)))
		and map_legend.text.contains("[color=#%s]●[/color] Harvest node" % (
			MapObject3D.HARVEST_COLOUR.to_html(false)))
		and map_legend.text.contains("[color=#%s]●[/color] Interactive" % (
			MapObject3D.INTERACTIVE_COLOUR.to_html(false))),
		"every legend swatch is the colour the map actually draws")
	_expect(harvest_node != null and harvest_node.server_tile == Vector2i(770, 481),
		"the pick target sits on the tile the server named")

	# The harvest indicator follows the authoritative state, not a chat phrase.
	var started: PackedByteArray = PackedByteArray([1, 0xf0, 0x01])
	started.append_array(_nul_bytes("Mirror Reed"))
	app_state_inventory.call("_on_packet", 237, started)
	await process_frame
	_expect(harvest_banner.visible and harvest_banner.text.contains("Mirror Reed"),
		"the harvesting indicator names the resource the server reported")
	_expect(harvest_ring != null and harvest_ring.visible
		and (harvest_ring.material_override as StandardMaterial3D
			).albedo_color.is_equal_approx(
				Color(MapObject3D.ACTIVE_COLOUR, 0.75)),
		"the ring marks the node the player is harvesting")
	_expect(harvest_banner.get_global_rect().end.y <= 720.0
		and harvest_banner.get_global_rect().position.y >= 0.0,
		"the harvesting indicator fits within 1280x720")
	_expect(not harvest_banner.get_global_rect().intersects(
		right_stats.get_global_rect()),
		"the harvesting indicator does not cover the fixed resource rail")
	app_state_inventory.call("_on_packet", 237, PackedByteArray([0, 0, 0, 0]))
	await process_frame
	_expect(harvest_ring != null and not harvest_ring.visible,
		"the ring goes away again when the harvest stops")
	_expect(not harvest_banner.visible,
		"a server stop - moving, a full backpack, combat - clears the indicator")

	# Effects the server announced. They are events, not state: each draws
	# itself where the actor stands and frees itself when it finishes.
	app_state_inventory.call("_on_packet", 51, _hex_bytes(
		"5b000203e1010000000001000001020304050b001e14071400120001416c696365"
		+ "000040ff0600"))
	await process_frame
	main.call("_sync_world")
	await process_frame
	app_state_inventory.call("_on_packet", 79, PackedByteArray([17, 0x5b, 0]))
	await process_frame
	var effects: Array = main.get("world_effects") as Array
	_expect(effects.size() == 1
		and (effects[0] as WorldEffect3D).effect_id == 17,
		"the effect the server announced is drawn")
	_expect((effects[0] as WorldEffect3D).get_node_or_null("EffectBeam") == null,
		"an effect with no second actor draws no beam")
	var effect_burst: GPUParticles3D = (effects[0] as WorldEffect3D
		).get_node_or_null("EffectBurst") as GPUParticles3D
	_expect(effect_burst != null and effect_burst.amount > 0
		and effect_burst.one_shot and effect_burst.process_material != null
		and effect_burst.draw_pass_1 != null,
		"the effect is a particle burst, not a bare ring")
	# A harmful effect falls and a beneficial one rises: the one distinction
	# the server's own grouping supports.
	app_state_inventory.call("_on_packet", 79, PackedByteArray([1, 0x5b, 0]))
	await process_frame
	var blessing: Array = main.get("world_effects") as Array
	var blessing_burst: GPUParticles3D = (blessing[blessing.size() - 1]
		as WorldEffect3D).get_node_or_null("EffectBurst") as GPUParticles3D
	var harm_material: ParticleProcessMaterial = (effect_burst.process_material
		as ParticleProcessMaterial)
	var blessing_material: ParticleProcessMaterial = (
		blessing_burst.process_material as ParticleProcessMaterial)
	_expect(harm_material.gravity.y > 0.0 and blessing_material.gravity.y < 0.0,
		"the two classes move differently rather than sharing one burst")
	_expect(not harm_material.color.is_equal_approx(blessing_material.color),
		"and they are told apart by colour")
	# An actor the client has never been told about has no position.
	var known_effects: int = (main.get("world_effects") as Array).size()
	app_state_inventory.call("_on_packet", 79, PackedByteArray([2, 0xff, 0x7f]))
	await process_frame
	_expect((main.get("world_effects") as Array).size() == known_effects,
		"an effect at an unknown actor is not guessed at a position")
	app_state_inventory.call("_on_packet", 6, PackedByteArray([0x5b, 0]))
	await process_frame

	# Ranged combat: the aim the server states, and the arrow it looses.
	app_state_inventory.call("_on_packet", 51, _hex_bytes(
		"5b00020004000000000001000001020304050b001e14071400120001416c696365"
		+ "000040ff0600"))
	app_state_inventory.call("_on_packet", 51, _hex_bytes(
		"4d00060004000000000001000001020304050b001e1407140012000142657373"
		+ "000040ff0600"))
	await process_frame
	main.call("_sync_world")
	await process_frame
	var missiles_before: int = (main.get("world_effects") as Array).size()
	app_state_inventory.call("_on_packet", 84, PackedByteArray([0x5b, 0, 0x4d, 0]))
	await process_frame
	var shooter: Dictionary = (app_state_inventory.get("actors")
		as Dictionary).get(91, {}) as Dictionary
	_expect(int(shooter.get("aiming_at", -1)) == 77,
		"an aim is kept on the actor it describes")
	_expect((main.get("world_effects") as Array).size() == missiles_before,
		"aiming draws no arrow: nothing has been loosed yet")
	app_state_inventory.call("_on_packet", 86, PackedByteArray([0x5b, 0, 0x4d, 0]))
	await process_frame
	var after_shot: Array = main.get("world_effects") as Array
	_expect(after_shot.size() == missiles_before + 1
		and after_shot[after_shot.size() - 1] is MissileFlight3D,
		"loosing draws an arrow between the two actors")
	var arrow: MissileFlight3D = after_shot[after_shot.size() - 1] as MissileFlight3D
	_expect(arrow.origin.distance_to(arrow.destination) > 1.0
		and arrow.get_node_or_null("Shaft") != null,
		"the arrow flies from one actor to the other")
	shooter = (app_state_inventory.get("actors") as Dictionary).get(91, {}) as Dictionary
	_expect(int(shooter.get("aiming_at", -1)) == -1,
		"loosing ends the aim the server stated before it")
	# Objects the server puts into a map that is already being played in.
	# Everything the client knew about a map used to arrive with the map.
	var placed_before: int = (main.get("placed_object_nodes") as Dictionary).size()
	var totem := PackedByteArray([7, 0, 0x00, 0x03, 0xe6, 0x01, 0, 0])
	totem.append_array(_nul_bytes("boss_totem"))
	app_state_inventory.call("_on_packet", 75, totem)
	await process_frame
	var placed_nodes: Dictionary = main.get("placed_object_nodes") as Dictionary
	_expect(placed_nodes.size() == placed_before + 1 and placed_nodes.has(7)
		and placed_nodes[7] is PlacedObject3D,
		"an object raised mid-game is drawn: %d" % placed_nodes.size())
	_expect(str((placed_nodes[7] as PlacedObject3D).model) == "boss_totem"
		and PlacedObject3D.shape_name_for("boss_totem") == "totem",
		"and a name that says what it is gets the shape it names")
	_expect(PlacedObject3D.shape_name_for("3dobjects/misc/unknowable.e3d")
			== "marker",
		"a name this client has no shape for is still something visible")
	app_state_inventory.call("_on_packet", 76, PackedByteArray([7, 0]))
	await process_frame
	_expect(not (main.get("placed_object_nodes") as Dictionary).has(7),
		"and an object the server takes away goes")

	# A list is the whole truth about a map, so it replaces rather than adds.
	var listed := PackedByteArray([2, 0, 1, 0, 0x00, 0x03, 0xe6, 0x01, 0, 0])
	listed.append_array(_nul_bytes("totem"))
	listed.append_array(PackedByteArray([2, 0, 0x04, 0x03, 0xe6, 0x01, 0, 0]))
	listed.append_array(_nul_bytes("banner"))
	app_state_inventory.call("_on_packet", 74, listed)
	await process_frame
	_expect((app_state_inventory.get("world_objects") as Dictionary).size() == 2,
		"a list states everything already standing on the map")
	var single := PackedByteArray([9, 0, 0x00, 0x03, 0xe6, 0x01, 0, 0])
	single.append_array(_nul_bytes("stone"))
	app_state_inventory.call("_on_packet", 74, PackedByteArray([1, 0])
		+ single)
	await process_frame
	_expect((app_state_inventory.get("world_objects") as Dictionary).size() == 1
		and (app_state_inventory.get("world_objects") as Dictionary).has(9),
		"and a later list replaces it rather than adding to it")
	app_state_inventory.call("_on_packet", 74, PackedByteArray([0, 0]))
	await process_frame
	_expect((main.get("placed_object_nodes") as Dictionary).is_empty(),
		"an empty list clears the map")
	_expect(EloriaProtocol.decode_server(74, PackedByteArray([9, 0])).type
			== "invalid",
		"a list that promises more objects than it carries is rejected")

	# Where the ways off this map are, and both ends of a teleport.
	var ways := PackedByteArray([2, 0, 0x00, 0x03, 0xe6, 0x01,
		0x04, 0x03, 0xe6, 0x01])
	app_state_inventory.call("_on_packet", 10, ways)
	await process_frame
	_expect((app_state_inventory.get("teleporters") as Array).size() == 2,
		"the map says where its portals are")
	app_state_inventory.call("_on_packet", 10, PackedByteArray([0, 0]))
	await process_frame
	_expect((app_state_inventory.get("teleporters") as Array).is_empty(),
		"and a map with none says that too")
	_expect(EloriaProtocol.decode_server(10, PackedByteArray([1, 0, 2, 0])).type
			== "invalid",
		"a teleporter list of the wrong length is rejected")
	var before_teleport: int = (main.get("world_effects") as Array).size()
	app_state_inventory.call("_on_packet", 12,
		PackedByteArray([0x00, 0x03, 0xe6, 0x01]))
	await process_frame
	_expect((main.get("world_effects") as Array).size() == before_teleport + 1,
		"an arrival is drawn where it happened")
	app_state_inventory.call("_on_packet", 13,
		PackedByteArray([0x00, 0x03, 0xe6, 0x01]))
	await process_frame
	_expect((main.get("world_effects") as Array).size() == before_teleport + 2,
		"and so is a departure")

	# Which quest a piece of NPC dialogue belongs to. Before this the client
	# could not tell a quest line from small talk, so neither could a player.
	var dialogue_panel: Control = main.get("dialogue_panel") as Control
	var dialogue_name: Label = main.get("dialogue_name") as Label
	app_state_inventory.call("_on_packet", 30, _nul_bytes("Just passing through."))
	await process_frame
	_expect(dialogue_panel.visible
		and not bool((app_state_inventory.get("npc_dialogue") as Dictionary).get(
			"quest", true))
		and not dialogue_name.text.contains("Quest"),
		"unflagged dialogue is small talk: " + dialogue_name.text)
	app_state_inventory.call("_on_packet", 92, PackedByteArray([]))
	app_state_inventory.call("_on_packet", 93, PackedByteArray([2, 0]))
	app_state_inventory.call("_on_packet", 30, _nul_bytes("Find the reed bank."))
	await process_frame
	var flagged: Dictionary = app_state_inventory.get("npc_dialogue") as Dictionary
	_expect(bool(flagged.get("quest", false)) and int(flagged.get("quest_id", 0)) == 2
		and dialogue_name.text.contains("Quest 2"),
		"flagged dialogue names the quest it belongs to: " + dialogue_name.text)
	app_state_inventory.call("_on_packet", 30, _nul_bytes("Anyway, good day."))
	await process_frame
	_expect(not bool((app_state_inventory.get("npc_dialogue") as Dictionary).get(
			"quest", true)),
		"the flag describes one line, so the next line is small talk again")
	app_state_inventory.call("_on_packet", 94, PackedByteArray([2, 0]))
	await process_frame
	_expect((app_state_inventory.get("finished_quests") as Array).has(2)
		and int(app_state_inventory.get("current_quest_id")) == 0,
		"a finished quest is recorded and stops being the current one")
	app_state_inventory.call("_on_packet", 94, PackedByteArray([2, 0]))
	await process_frame
	_expect((app_state_inventory.get("finished_quests") as Array).size() == 1,
		"and finishing it twice records it once")

	# An arrow going to a place rather than into somebody: a practice shot, or
	# a miss. Where it lands is the server's decision arriving on the wire, so
	# two clients watching one shot draw the same arrow.
	var before_ground: int = (main.get("world_effects") as Array).size()
	app_state_inventory.call("_on_packet", 85,
		PackedByteArray([0x5b, 0, 0x3c, 0, 0x3c, 0]))
	await process_frame
	shooter = (app_state_inventory.get("actors") as Dictionary).get(91, {}) as Dictionary
	_expect(int(shooter.get("aiming_at", 0)) == -1
		and (shooter.get("aiming_at_tile", Vector2i.ZERO) as Vector2i)
			== Vector2i(60, 60),
		"aiming at a place is kept on the shooter and names the tile: %s"
			% str(shooter.get("aiming_at_tile")))
	_expect((main.get("world_effects") as Array).size() == before_ground,
		"and draws no arrow, because nothing has been loosed")
	app_state_inventory.call("_on_packet", 87,
		PackedByteArray([0x5b, 0, 0x3c, 0, 0x3c, 0]))
	await process_frame
	var ground_effects: Array = main.get("world_effects") as Array
	_expect(ground_effects.size() == before_ground + 1
		and ground_effects[ground_effects.size() - 1] is MissileFlight3D,
		"loosing at a place draws an arrow to it")
	shooter = (app_state_inventory.get("actors") as Dictionary).get(91, {}) as Dictionary
	_expect((shooter.get("aiming_at_tile", Vector2i.ZERO) as Vector2i)
			== Vector2i(-1, -1),
		"and the aim at that place ends with it")
	# A shot from an actor the client has never been told about draws nothing.
	app_state_inventory.call("_on_packet", 87,
		PackedByteArray([0xff, 0x7f, 0x3c, 0, 0x3c, 0]))
	await process_frame
	_expect((main.get("world_effects") as Array).size() == before_ground + 1,
		"a ground shot from an unknown actor draws nothing")

	# An arrow at an actor the client has never been told about is not guessed.
	var before_unknown: int = (main.get("world_effects") as Array).size()
	app_state_inventory.call("_on_packet", 86, PackedByteArray([0x5b, 0, 0xff, 0x7f]))
	await process_frame
	_expect((main.get("world_effects") as Array).size() == before_unknown,
		"a shot at an unknown actor draws nothing")
	app_state_inventory.call("_on_packet", 6, PackedByteArray([0x5b, 0]))
	app_state_inventory.call("_on_packet", 6, PackedByteArray([0x4d, 0]))
	await process_frame

	# Guild tags. The tag arrives inside the actor's display name, so a client
	# that takes the whole string as a name shows the tag as part of it.
	app_state_inventory.call("_on_packet", 51, _hex_bytes(
		"5b000203e1010000000001000001020304050b001e14071400120001416c6963652083"
		+ "454c4f000040ff0600"))
	await process_frame
	main.call("_sync_world")
	await process_frame
	var tagged_actor: Dictionary = (app_state_inventory.get("actors")
		as Dictionary).get(91, {}) as Dictionary
	_expect(str(tagged_actor.get("name", "")) == "Alice"
		and str(tagged_actor.get("guild_tag", "")) == "ELO",
		"the reducer keeps the name and the tag apart")
	var tagged_node: Node3D = (main.get("actor_nodes")
		as Dictionary).get(91) as Node3D
	var plate: Label3D = (tagged_node.get_node_or_null("Nameplate")
		as Label3D) if tagged_node != null else null
	_expect(plate != null and plate.text.contains("Alice")
		and plate.text.contains("[ELO]"),
		"the nameplate draws the tag as a tag: "
			+ (plate.text if plate != null else "no nameplate"))
	# The server coloured Alice's tag but not her name, so the plate is left
	# white rather than taking the palette's index 0.
	_expect(plate != null and plate.modulate.is_equal_approx(Color.WHITE),
		"a name the server did not colour stays white")
	app_state_inventory.call("_on_packet", 6, PackedByteArray([91, 0]))
	await process_frame

	# Name colours. The server puts them in front of the name as `127 + index`
	# and they are the only thing that says, without a click, that a player is
	# a demigod (c_green3) or that a creature belongs to an invasion (c_red3).
	app_state_inventory.call("_on_packet", 51, _hex_bytes(
		"5c000203e1010000000001000001020304050b001e14071400"
		+ "12000190426f62000040ff0600"))
	app_state_inventory.call("_on_packet", 1, _hex_bytes(
		"5d000203e10100000000cc0720002000018d456d626572666f7800"))
	await process_frame
	main.call("_sync_world")
	await process_frame
	var demigod_plate: Label3D = _nameplate_of(main, 92)
	_expect(demigod_plate != null and demigod_plate.text == "Bob"
		and demigod_plate.modulate.is_equal_approx(EloriaProtocol.EL_TEXT_COLOURS[17]),
		"a demigod's nameplate is green, and the colour byte is not in the name")
	var invasion_plate: Label3D = _nameplate_of(main, 93)
	_expect(invasion_plate != null and invasion_plate.text == "Emberfox"
		and invasion_plate.modulate.is_equal_approx(EloriaProtocol.EL_TEXT_COLOURS[14]),
		"an invasion creature's nameplate is red")
	# You are given no nameplate of your own, so your own name colour has only
	# the overhead banner to show in.
	var before_colour_local: int = int(app_state_inventory.get("local_actor_id"))
	app_state_inventory.set("local_actor_id", 92)
	main.call("_sync_world")
	await process_frame
	var banner_name: Label = main.get("overhead_player_name") as Label
	_expect(banner_name != null and banner_name.text == "Bob"
		and banner_name.get_theme_color("font_color").is_equal_approx(
			EloriaProtocol.EL_TEXT_COLOURS[17]),
		"your own demigod name is green on the overhead banner")
	app_state_inventory.set("local_actor_id", before_colour_local)
	main.call("_sync_world")
	await process_frame
	app_state_inventory.call("_on_packet", 6, PackedByteArray([92, 0]))
	app_state_inventory.call("_on_packet", 6, PackedByteArray([93, 0]))
	await process_frame

	# Twelve spell quick slots, and the sigils window that says why a spell is
	# out of reach. Ownership is the server's; the names are the catalog's.
	_expect((main.get("spell_slot_buttons") as Array).size() == 12,
		"the quickbar has twelve spell slots, not six")
	for slot: int in range(1, 13):
		_expect(InputMap.has_action("quick_spell_%d" % slot),
			"quick_spell_%d is a rebindable action" % slot)
	var sigils: Control = main.get("sigil_window") as Control
	var sigil_panel: PanelContainer = sigils.get_node("SigilWindow") as PanelContainer
	_expect(not sigil_panel.visible, "the sigils window starts closed")
	# The server states the owned set; two sigils here, from a real packet.
	app_state_inventory.call("_on_packet", 42, PackedByteArray([
		0x0a, 0x00, 0x08, 0x00, 0, 0, 0, 0]))
	main.call("_on_sigil_button_pressed")
	await process_frame
	_expect(sigil_panel.visible, "the button opens it")
	var sigil_list: ItemList = sigils.get_node(
		"SigilWindow/SigilBody/SigilColumns/SigilList") as ItemList
	_expect(sigil_list.item_count == 26,
		"every sigil the catalog names is listed: %d" % sigil_list.item_count)
	var owned_rows: Array[String] = []
	for index: int in range(sigil_list.item_count):
		if not sigil_list.is_item_disabled(index):
			owned_rows.append(sigil_list.get_item_text(index))
	_expect(owned_rows.size() == 3,
		"exactly the sigils the server sent are marked owned: %s" % str(owned_rows))
	var sigil_summary: RichTextLabel = sigils.get_node(
		"SigilWindow/SigilBody/SigilColumns/SigilSummary") as RichTextLabel
	_expect(sigil_summary.text.contains("3 of 26")
		and sigil_summary.text.contains("needs"),
		"the summary counts what is owned and names what each spell still needs")
	var sigil_rect: Rect2 = sigil_panel.get_global_rect()
	_expect(sigil_rect.position.x >= 0.0 and sigil_rect.end.x <= 1280.0
		and sigil_rect.end.y <= 720.0
		and not sigil_rect.intersects(right_stats.get_global_rect()),
		"the sigils window fits 1280x720 clear of the resource rail")
	var sigil_cancel: InputEventKey = InputMap.action_get_events(
		"cancel")[0].duplicate() as InputEventKey
	sigil_cancel.pressed = true
	main.call("_unhandled_input", sigil_cancel)
	await process_frame
	_expect(not sigil_panel.visible, "cancel closes the sigils window")

	# Spell power. Both the preferred power and the ceiling are the server's;
	# the client asks for a power and never works a limit out from a level.
	var power_value: Label = main.get_node(
		"GameView/SpellQuickbar/SpellContent/SpellControls/SpellPowerValue") as Label
	var power_up: Button = main.get_node(
		"GameView/SpellQuickbar/SpellContent/SpellControls/SpellPowerUp") as Button
	var power_down: Button = main.get_node(
		"GameView/SpellQuickbar/SpellContent/SpellControls/SpellPowerDown") as Button
	main.call("_sync_spells")
	await process_frame
	_expect(power_value.text == "P1" and power_up.disabled and power_down.disabled,
		"with no stated limit the stepper offers nothing to choose")
	_expect(int(main.call("_cast_power_for", 3)) == 0,
		"a cast with no stated limit sends the legacy frame, with no power byte")
	# shield: preferred 1 of 4; heal: preferred 3 of 3.
	var power_payload := PackedByteArray([2, 0, 1, 4])
	power_payload.append_array(_nul_bytes("shield"))
	power_payload.append_array(PackedByteArray([3, 3]))
	power_payload.append_array(_nul_bytes("heal"))
	app_state_inventory.call("_on_packet", 231, power_payload)
	await process_frame
	_expect(not power_up.disabled and power_down.disabled,
		"the stepper opens up to the highest limit the server stated")
	main.call("_on_spell_power_up_pressed")
	main.call("_on_spell_power_up_pressed")
	main.call("_on_spell_power_up_pressed")
	main.call("_on_spell_power_up_pressed")
	await process_frame
	_expect(power_value.text == "P4" and power_up.disabled,
		"the stepper stops at the server's ceiling: " + power_value.text)
	_expect(int(main.call("_cast_power_for", 3)) == 4
		and int(main.call("_cast_power_for", 0)) == 3,
		"each cast is clamped to the limit the server stated for its effect")
	var shield_tooltip: String = str(main.call("_spell_tooltip",
		main.get("spell_catalog").call("spell", 3), [] as Array[String], 0))
	_expect(shield_tooltip.contains("Power 4 of 4"),
		"the spell tooltip states the power and the ceiling: " + shield_tooltip)
	main.call("_on_spell_power_down_pressed")
	main.call("_on_spell_power_down_pressed")
	main.call("_on_spell_power_down_pressed")
	await process_frame
	_expect(power_value.text == "P1" and power_down.disabled,
		"the stepper stops at one")

	# Active effects. The server states which buffs are on and for how long;
	# the strip counts down to the moment it stated and shows nothing else.
	var buff_bar: Control = main.get("active_buff_bar") as Control
	var buff_row: HBoxContainer = buff_bar.get_node("ActiveBuffRow") as HBoxContainer
	_expect(buff_row.get_child_count() == 0, "the effect strip starts empty")
	# Buff 0 for 128 seconds, then buff 22 for 90.
	app_state_inventory.call("_on_packet", 44, PackedByteArray([0, 128]))
	app_state_inventory.call("_on_packet", 44, PackedByteArray([22, 90]))
	await process_frame
	_expect((buff_bar.call("shown_buff_ids") as Array) == [0, 22],
		"both effects the server reported are on the strip")
	var first: Control = buff_row.get_child(0) as Control
	_expect((first.get_node("BuffName") as Label).text == "Shield"
		and (first.get_node("BuffRemaining") as Label).text == "128s"
		and (first.get_node("BuffIcon") as TextureRect).texture != null,
		"an effect is named, iconned and counted down from the server's duration")
	var strip_rect: Rect2 = buff_row.get_global_rect()
	_expect(strip_rect.position.x >= 0.0 and strip_rect.position.y >= 0.0
		and strip_rect.end.x <= 1280.0 and strip_rect.end.y <= 720.0
		and not strip_rect.intersects(right_stats.get_global_rect()),
		"the effect strip fits 1280x720 clear of the resource rail: %s" % strip_rect)
	app_state_inventory.call("_on_packet", 46, PackedByteArray([0]))
	await process_frame
	_expect((buff_bar.call("shown_buff_ids") as Array) == [22],
		"the server removing an effect takes it off the strip")
	# A resync list restates the whole set without durations.
	app_state_inventory.call("_on_packet", 45, PackedByteArray([
		1, 3, 255, 255, 255, 255, 255, 255, 255, 255]))
	await process_frame
	_expect((buff_bar.call("shown_buff_ids") as Array) == [1, 3]
		and (buff_row.get_child(0).get_node("BuffRemaining") as Label).text.is_empty(),
		"a resync replaces the set, and states no time to count down")
	# An effect whose stated time has run out leaves without another packet.
	app_state_inventory.call("_on_packet", 46, PackedByteArray([1]))
	app_state_inventory.call("_on_packet", 46, PackedByteArray([3]))
	app_state_inventory.call("_on_packet", 44, PackedByteArray([0, 0]))
	await process_frame
	await process_frame
	_expect((buff_bar.call("shown_buff_ids") as Array).is_empty(),
		"an effect the server said would last no time is not shown as active")

	# Looking at another player. The reply is one packet that names the actor,
	# so the window is the server's answer rather than a request the client
	# remembered making.
	var info_layer: Control = main.get("player_info_panel") as Control
	var info_panel: PanelContainer = info_layer.get_node("PlayerInfo") as PanelContainer
	_expect(not info_panel.visible, "the player-info window starts closed")
	var described := PackedByteArray([0x5b, 0x00, 0x01, 0x00])
	described.append_array(_nul_bytes("Alice"))
	described.append_array(_nul_bytes("Beginner Tutorial"))
	app_state_inventory.call("_on_packet", 228, described)
	await process_frame
	_expect(info_panel.visible
		and (info_layer.get("title") as Label).text == "Alice"
		and (info_layer.get("body") as RichTextLabel).text.contains(
			"Beginner Tutorial"),
		"the window names the player the server described and what they earned")
	var info_rect: Rect2 = info_panel.get_global_rect()
	_expect(info_rect.position.x >= 0.0 and info_rect.position.y >= 0.0
		and info_rect.end.x <= 1280.0 and info_rect.end.y <= 720.0
		and not info_rect.intersects(right_stats.get_global_rect()),
		"the player-info window fits 1280x720 clear of the resource rail: %s"
			% info_rect)
	var cancel_event: InputEventKey = InputMap.action_get_events(
		"cancel")[0].duplicate() as InputEventKey
	cancel_event.pressed = true
	main.call("_unhandled_input", cancel_event)
	await process_frame
	_expect(not info_panel.visible,
		"cancel closes the player-info window like every other panel")
	var empty := PackedByteArray([0x5b, 0x00, 0x00, 0x00])
	empty.append_array(_nul_bytes("Alice"))
	app_state_inventory.call("_on_packet", 228, empty)
	await process_frame
	_expect(info_panel.visible
		and not (info_layer.get("body") as RichTextLabel).text.contains(
			"Beginner Tutorial"),
		"a player with nothing earned is described as such, not left stale")
	app_state_inventory.call("close_player_info")
	await process_frame

	# The console's own commands, routed through the real chat submit path.
	var chat_input_line: LineEdit = main.get_node("GameView/ChatInput") as LineEdit
	var chat_lines_before: int = (app_state_inventory.get("chat_lines") as Array).size()
	main.call("_on_chat_submitted", "#help")
	await process_frame
	_expect((app_state_inventory.get("chat_lines") as Array).size()
			> chat_lines_before
		and chat_input_line.text.is_empty(),
		"a command the client answers writes its reply locally and clears the box")
	main.call("_on_chat_submitted", "#markpos 770 481 Reed bank")
	await process_frame
	var console: ConsoleCommands = main.get("console_commands") as ConsoleCommands
	_expect(console.marks.size() == 1,
		"the mark the player made is kept by the client")
	var overlay_marks: Array = (main.get("map_marker_overlay")
		as Control).get("_player_marks") as Array
	_expect(overlay_marks.size() <= 1,
		"the player's marks reach the map overlay, filtered by map")
	# History and completion.
	chat_input_line.text = "#mar"
	main.call("_complete_console_command")
	_expect(chat_input_line.text == "#mark",
		"tab completes as far as the commands agree: " + chat_input_line.text)
	main.call("_recall_console_history", -1)
	_expect(chat_input_line.text == "#markpos 770 481 Reed bank",
		"up recalls the last line sent: " + chat_input_line.text)
	main.call("_recall_console_history", 1)
	_expect(chat_input_line.text.is_empty(),
		"and down returns to an empty box")
	main.call("_on_chat_submitted", "#unmark Reed bank")
	await process_frame

	# Map markers. The server places every one of them and takes every one of
	# them away; nothing here decides a marker has been reached.
	var here: String = EloriaProtocol.map_id_from_reference(
		str(app_state_inventory.get("current_map")))
	var marker_payload := PackedByteArray([0xea, 0x01, 0x0c, 0x03, 0xe1, 0x01])
	marker_payload.append_array(_nul_bytes("./maps/%s.elm" % here))
	marker_payload.append_array(_nul_bytes("Reed bank"))
	app_state_inventory.call("_on_packet", 90, marker_payload)
	var elsewhere := PackedByteArray([0xeb, 0x01, 0x10, 0x00, 0x20, 0x00])
	elsewhere.append_array(_nul_bytes("./maps/somewhere_else.elm"))
	elsewhere.append_array(_nul_bytes("Another map"))
	app_state_inventory.call("_on_packet", 90, elsewhere)
	await process_frame
	var marker_nodes: Dictionary = main.get("map_marker_nodes") as Dictionary
	_expect((app_state_inventory.get("map_markers") as Dictionary).size() == 2
		and marker_nodes.size() == 1 and marker_nodes.has(490),
		"a marker for another map is held but not drawn here")
	var placed: MapMarker3D = marker_nodes.get(490) as MapMarker3D
	_expect(placed != null and placed.server_tile == Vector2i(780, 481)
		and placed.label == "Reed bank",
		"the marker sits on the tile the server named, with its label")
	var pin: MeshInstance3D = (placed.get_node_or_null("Pin")
		as MeshInstance3D) if placed != null else null
	_expect(pin != null and pin.layers == MapMarker3D.MAP_MARKER_LAYER,
		"a marker draws on the map cameras rather than over the gameplay view")
	var marker_sidebar: RichTextLabel = main.get_node(
		"GameView/FullMap/MapLayout/Sidebar/SidebarContent/MapMarkerList") as RichTextLabel
	_expect(marker_sidebar.visible and marker_sidebar.text.contains("Reed bank")
		and marker_sidebar.text.contains("780") and marker_sidebar.text.contains("481"),
		"the map sidebar names the marker and its tile, which no pin drawn at"
			+ " full-map scale could: " + marker_sidebar.text)
	var overlay: Control = main.get("map_marker_overlay") as Control
	_expect((overlay.get("_markers") as Array).size() == 1,
		"the full-map overlay is given the markers for this map and no others")
	app_state_inventory.call("_on_packet", 91, PackedByteArray([0xea, 0x01]))
	await process_frame
	_expect((app_state_inventory.get("map_markers") as Dictionary).size() == 1
		and (main.get("map_marker_nodes") as Dictionary).is_empty()
		and not marker_sidebar.visible
		and (overlay.get("_markers") as Array).is_empty(),
		"the server takes a marker away and the pin, the list and the overlay"
			+ " entry all go with it")

	# A map change discards the previous map's objects rather than leaving
	# pick targets from somewhere else standing in the new world.
	app_state_inventory.call("_on_packet", 7, _nul_bytes("maps/nymara/mirrorhold.elm"))
	await process_frame
	_expect((app_state_inventory.get("map_objects") as Dictionary).is_empty()
		and not bool((app_state_inventory.get("harvest") as Dictionary).get("active", true)),
		"a map change clears the world objects and the harvesting state")
	# GLTFDocument builds runtime textures with no mip chain, which is what made
	# distant roofs and ground swim as the camera moved.
	var loaded_world: Node3D = (main.get_node(
		"GameView/ViewportContainer/Viewport/WorldRoot/WorldLoader")
		as Node).get("world_root") as Node3D
	var mipped_textures := 0
	var flat_textures := 0
	var anisotropic := 0
	var plain_filter := 0
	if loaded_world != null:
		for node_value: Node in loaded_world.find_children(
				"*", "MeshInstance3D", true, false):
			var world_mesh: Mesh = (node_value as MeshInstance3D).mesh
			if world_mesh == null:
				continue
			for surface: int in range(world_mesh.get_surface_count()):
				var surface_material: BaseMaterial3D = world_mesh.surface_get_material(
					surface) as BaseMaterial3D
				if surface_material == null:
					continue
				if surface_material.texture_filter == 						BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC:
					anisotropic += 1
				else:
					plain_filter += 1
				var albedo: Texture2D = surface_material.albedo_texture
				if albedo == null:
					continue
				var albedo_image: Image = albedo.get_image()
				if albedo_image == null:
					continue
				if albedo_image.has_mipmaps():
					mipped_textures += 1
				else:
					flat_textures += 1
	_expect(anisotropic > 0 and plain_filter == 0,
		"every imported world material samples its textures anisotropically")
	_expect(mipped_textures > 0 and flat_textures == 0,
		"every imported world texture carries a mip chain")
	app_state_inventory.set("authenticated", false)

	# Books. Reading is the other half of the knowledge loop: the catalog, the
	# ownership bitset and the detail pane all worked, but a player could not
	# see that they were reading anything, and the manufacturing resolver
	# reported "unread knowledge" as a blocking reason it had no way to clear.
	var reading_panel: PanelContainer = main.get_node(
		"GameView/ReadingPanel") as PanelContainer
	var reading_title: Label = main.get_node(
		"GameView/ReadingPanel/ReadingContent/ReadingHeader/ReadingTitle") as Label
	var reading_progress: ProgressBar = main.get_node(
		"GameView/ReadingPanel/ReadingContent/ReadingProgress") as ProgressBar
	var reading_detail: RichTextLabel = main.get_node(
		"GameView/ReadingPanel/ReadingContent/ReadingDetail") as RichTextLabel
	app_state_inventory.set("authenticated", true)
	_expect(not reading_panel.visible, "the reading window starts closed")
	# Partial statistics 47/65/66: the book being read, pages done, pages total.
	app_state_inventory.call("_on_packet", 49, PackedByteArray([
		47, 0, 0, 0, 0, 65, 150, 0, 0, 0, 66, 88, 2, 0, 0]))
	await process_frame
	var reading_state: Dictionary = app_state_inventory.get("reading") as Dictionary
	_expect(bool(reading_state.get("active", false))
		and int(reading_state.get("index", -1)) == 0
		and int(reading_state.get("pages_read", 0)) == 150
		and int(reading_state.get("pages_total", 0)) == 600,
		"reading progress is reduced from the authoritative research statistics")
	_expect(reading_panel.visible and reading_title.text.begins_with("Reading ")
		and reading_detail.text.contains("150 of 600")
		and reading_detail.text.contains("25%"),
		"the reading window names the book and its progress: " + reading_title.text)
	_expect(is_equal_approx(reading_progress.value, 150.0)
		and is_equal_approx(reading_progress.max_value, 600.0),
		"the progress bar is driven by the server's page counts")
	var reading_rect: Rect2 = reading_panel.get_global_rect()
	_expect(reading_rect.position.x >= 0.0 and reading_rect.position.y >= 0.0
		and reading_rect.end.x <= 1280.0 and reading_rect.end.y <= 720.0,
		"the reading window fits within 1280x720")
	_expect(not reading_rect.intersects(right_stats.get_global_rect()),
		"the reading window does not cover the fixed resource rail")

	# A recipe gated on that knowledge is blocked until the bit arrives.
	var manufacturing: RefCounted = main.get("manufacturing_catalog") as RefCounted
	var gated_index: int = -1
	for recipe_index: int in range(200):
		var definition: Dictionary = manufacturing.call("recipe", recipe_index) as Dictionary
		if definition.is_empty():
			break
		if int(definition.get("knowledgeIndex", -1)) == 0:
			gated_index = recipe_index
			break
	if gated_index >= 0:
		var known: Array[int] = []
		var blocked: Dictionary = manufacturing.call("availability", gated_index,
			{}, known, {"food": 10, "ether": 10}) as Dictionary
		var unblocked_known: Array[int] = [0]
		var unblocked: Dictionary = manufacturing.call("availability", gated_index,
			{}, unblocked_known, {"food": 10, "ether": 10}) as Dictionary
		var blocked_reasons: Array = blocked.get("reasons", []) as Array
		var unblocked_reasons: Array = unblocked.get("reasons", []) as Array
		var had_knowledge_reason := false
		for reason: Variant in blocked_reasons:
			if str(reason).begins_with("Unread knowledge"):
				had_knowledge_reason = true
		var still_has_knowledge_reason := false
		for reason: Variant in unblocked_reasons:
			if str(reason).begins_with("Unread knowledge"):
				still_has_knowledge_reason = true
		_expect(had_knowledge_reason and not still_has_knowledge_reason,
			"the knowledge that finishing a book grants clears the recipe's block")

	# Finishing: the server reports reading nothing, and the knowledge bit
	# arrives as its own packet rather than being assumed from completion.
	app_state_inventory.call("_on_packet", 56, PackedByteArray([0, 0]))
	app_state_inventory.call("_on_packet", 49, PackedByteArray([
		47, 0, 4, 0, 0, 65, 0, 0, 0, 0, 66, 0, 0, 0, 0]))
	await process_frame
	_expect(not bool((app_state_inventory.get("reading") as Dictionary).get("active", true)),
		"the reading state clears when the server reports reading nothing")
	_expect(reading_panel.visible and reading_title.text.begins_with("Finished ")
		and reading_detail.text.contains("Knowledge gained"),
		"finishing a book reports the knowledge it granted")
	_expect((app_state_inventory.get("known_knowledge") as Array).has(0),
		"the knowledge bit is set from the server packet, not inferred")
	main.call("_on_reading_close_pressed")
	_expect(not reading_panel.visible, "the reading window can be dismissed")
	app_state_inventory.set("authenticated", false)

	# The world-load path is safe while actors are being torn down. Anything
	# that frees an actor node outside the actor map leaves a dangling entry,
	# and calling queue_free() on that crashed the engine rather than raising -
	# which is what made a late _on_world_loaded call in this suite segfault.
	var dangling_actor := ReplicatedActor3D.new()
	dangling_actor.actor_id = 5150
	main.get_node("GameView/ViewportContainer/Viewport/WorldRoot").add_child(
		dangling_actor)
	var actor_nodes: Dictionary = main.get("actor_nodes") as Dictionary
	actor_nodes[5150] = dangling_actor
	dangling_actor.free()
	(app_state_inventory.get("actors") as Dictionary).clear()
	main.call("_sync_world")
	_expect(not actor_nodes.has(5150),
		"a dangling actor entry is dropped rather than freed a second time")
	main.call("_load_server_map")
	_expect(true, "the world-load path survives a dangling actor entry")

	print("world input tests: ", "PASS" if failures == 0 else "FAIL (%d)" % failures)
	main.queue_free()
	await process_frame
	quit(failures)

func _sized_bytes(value: String) -> PackedByteArray:
	var bytes: PackedByteArray = value.to_utf8_buffer()
	var sized: PackedByteArray = PackedByteArray([bytes.size()])
	sized.append_array(bytes)
	return sized

func _nul_bytes(value: String) -> PackedByteArray:
	var bytes: PackedByteArray = value.to_utf8_buffer()
	bytes.append(0)
	return bytes

func _expect(value: bool, label: String) -> void:
	if value:
		return
	failures += 1
	push_error("FAIL: " + label)

func _nameplate_of(main: Node, actor_id: int) -> Label3D:
	var node: Node3D = (main.get("actor_nodes") as Dictionary).get(actor_id) as Node3D
	if node == null:
		return null
	return node.get_node_or_null("Nameplate") as Label3D

func _hex_bytes(value: String) -> PackedByteArray:
	var bytes := PackedByteArray()
	for index: int in range(0, value.length(), 2):
		bytes.append(value.substr(index, 2).hex_to_int())
	return bytes

## The rendered facing has to be the direction the body crosses the ground in,
## not the tile direction that arrived with the packet. The two differ by
## design: the presentation runs a fraction of a tile behind the authoritative
## position, and every step that lands in the same frame as another is folded
## into a single segment before the actor node ever sees it.
func _check_travel_facing() -> void:
	var adapter := CoordinateAdapter.new()
	var actor := ReplicatedActor3D.new()
	root.add_child(actor)
	actor.apply_server_state({"actor_id": 1, "x": 10, "y": 10, "rotation": 0,
		"command": -1}, adapter, true)
	actor._physics_process(1.0 / 60.0)
	_expect(is_equal_approx(actor.call("_rendered_target_yaw"),
		actor.desired_facing_yaw()),
		"a resting actor is drawn facing exactly where the server says it does")

	# CMD_MOVE_E, taken only part way before the next packet arrives.
	actor.apply_server_state({"actor_id": 1, "x": 11, "y": 10, "rotation": 0,
		"command": 22}, adapter, false)
	for frame: int in range(9):
		actor._physics_process(1.0 / 60.0)
	# CMD_MOVE_N from a body that has not finished travelling east yet, so the
	# ground it is about to cross runs north-east and it must face north-east.
	actor.apply_server_state({"actor_id": 1, "x": 11, "y": 11, "rotation": 0,
		"command": 20}, adapter, false)
	var lagging_travel: float = ReplicatedActor3D.travel_yaw(
		actor.get("_segment_start") as Vector3, actor.server_target, 0.0)
	_expect(is_equal_approx(actor.call("_rendered_target_yaw"), lagging_travel)
		and not is_equal_approx(lagging_travel, actor.desired_facing_yaw()),
		"a step taken before the last one finished is faced along the ground crossed")

	# Four steps folded into one world sync, as happens on any frame slower
	# than the server's movement cadence. The straight slide covers all four.
	actor.apply_server_state({"actor_id": 1, "x": 11, "y": 10, "rotation": 0,
		"command": 24}, adapter, true)
	actor._physics_process(1.0 / 60.0)
	actor.apply_server_state({"actor_id": 1, "x": 15, "y": 14, "rotation": 0,
		"command": 20}, adapter, false)
	var folded_travel: float = ReplicatedActor3D.travel_yaw(
		actor.get("_segment_start") as Vector3, actor.server_target, 0.0)
	_expect(is_equal_approx(actor.call("_rendered_target_yaw"), folded_travel)
		and is_equal_approx(folded_travel, adapter.direction_to_godot(Vector2i(1, 1))),
		"a burst folded into one segment is faced along the whole slide")

	# Authority is untouched: the facing the server named is still what the
	# actor settles on once it stops, and a turn shown while its answer is in
	# flight still outranks travel, because that actor is turning, not walking.
	_expect(is_equal_approx(actor.desired_facing_yaw(),
		adapter.direction_to_godot(Vector2i(0, 1))),
		"the authoritative facing survives a segment travelled in another direction")
	actor.predict_turn(PI / 4.0)
	_expect(is_equal_approx(actor.call("_rendered_target_yaw"),
		actor.desired_facing_yaw()),
		"a predicted turn still outranks the direction of travel")
	actor.clear_turn_prediction()
	for frame: int in range(240):
		actor._physics_process(1.0 / 60.0)
	_expect(is_equal_approx(actor.rotation.y, actor.desired_facing_yaw()),
		"the actor comes to rest on the authoritative facing")
	actor.free()

## Everyone the server replicates carries the light blue dot the full map's
## legend calls NPC. The local player draws its own white mark over the top of
## its dot; nobody else has one, so without this an NPC standing in a town is
## on the map only for as long as somebody is looking at the world.
func _check_map_dot() -> void:
	var actor := ReplicatedActor3D.new()
	root.add_child(actor)
	# Gate Warden Ilyon's wire record: an Eloria NPC actor type, kind 20.
	actor.configure({"actor_id": 30014, "x": 704, "y": 816, "rotation": 0,
		"actor_type": 308, "kind": 20, "name": "Gate Warden Ilyon"},
		CoordinateAdapter.new(), {}, {})
	var dot: MeshInstance3D = actor.get_node_or_null("MapDot") as MeshInstance3D
	_expect(dot != null and dot.layers == ReplicatedActor3D.MAP_MARKER_LAYER,
		"a replicated actor carries a dot only the map cameras render")
	var material: StandardMaterial3D = (dot.mesh.surface_get_material(0)
		as StandardMaterial3D) if dot != null else null
	_expect(material != null
		and material.albedo_color.is_equal_approx(ReplicatedActor3D.MAP_DOT_COLOUR),
		"the dot is the light blue the legend names")
	actor.free()

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
		and is_equal_approx(minimap_image.offset_left, 54.0),
		"minimap compass ring and outline are three times their previous thickness")
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
		"keyboard facing override prevents strafe/back packets from rotating the actor")
	# CMD_TURN_E. The authoritative turn confirms the prediction and replaces
	# it, so a rejected or differently-resolved turn cannot stick locally.
	actor_height_fixture.apply_server_state({
		"x": 4, "y": 3, "rotation": 16384, "command": 40},
		CoordinateAdapter.new(), false)
	_expect(is_equal_approx(actor_height_fixture.desired_facing_yaw(), -PI / 2.0)
		and not bool(actor_height_fixture.get("_facing_override_active")),
		"an authoritative turn command clears the local turn prediction")
	actor_height_fixture.apply_server_state({
		"x": 4, "y": 3, "rotation": 0, "command": 22}, CoordinateAdapter.new(), false)
	_expect(is_equal_approx(actor_height_fixture.desired_facing_yaw(), -PI / 2.0),
		"movement after a confirmed turn follows authoritative facing again")
	actor_height_fixture.set_facing_override(false)
	actor_height_fixture.apply_server_state({
		"x": 5, "y": 3, "rotation": 0, "command": 22}, CoordinateAdapter.new(), false)
	_expect(is_equal_approx(actor_height_fixture.desired_facing_yaw(), -PI / 2.0),
		"click-style movement can restore authoritative movement facing")
	actor_height_fixture.free()
	var north_yaw: float = CoordinateAdapter.new().direction_to_godot(Vector2i(0, -1))
	_expect(main.call("_facing_relative_tile_direction", north_yaw, 1, 0) == Vector2i(0, -1)
		and main.call("_facing_relative_tile_direction", north_yaw, -1, 0) == Vector2i(0, 1)
		and main.call("_facing_relative_tile_direction", north_yaw, 0, -1) == Vector2i(-1, 0)
		and main.call("_facing_relative_tile_direction", north_yaw, 0, 1) == Vector2i(1, 0)
		and main.call("_facing_relative_tile_direction", north_yaw, 1, -1) == Vector2i(-1, -1),
		"WASD is facing-relative with non-rotating strafe/back and 45-degree diagonals")
	var lower_hud: Control = main.get_node("GameView/Quickbar") as Control
	var chat_panel: Control = main.get_node("GameView/ChatPanel") as Control
	var right_stats: Control = main.get_node("GameView/ResourceHud") as Control
	var right_quickbar: Control = main.get_node("GameView/ItemSpellQuickbar") as Control
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
	var chat_tabs: Control = main.get_node("GameView/ChatTabs") as Control
	_expect(chat_tabs.position.x <= 12.0 and chat_tabs.position.y <= 8.0
		and chat_panel.anchor_bottom < 0.3
		and chat_input.offset_bottom <= lower_hud.offset_top,
		"legacy chat tabs sit at upper left while entry remains above the lower rail")
	_expect(right_stats.anchor_left == 1.0 and right_quickbar.anchor_left == 1.0,
		"stats and item/spell quickbar occupy the right HUD rail")
	var item_slots: GridContainer = main.get_node("%ItemSlots") as GridContainer
	var spell_slots: GridContainer = main.get_node("%SpellSlots") as GridContainer
	_expect(item_slots.columns == 1 and item_slots.visible and not spell_slots.visible,
		"right rail presents compact single-column item and spell modes")
	main.call("_on_quickbar_mode_pressed", "spells")
	_expect(not item_slots.visible and spell_slots.visible,
		"right rail switches between item and spell quick slots")
	main.call("_on_quickbar_mode_pressed", "items")
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
	_expect(actor_menu.visible and main.get_node("GameView/ActorHudMenu/Options/ShowHealth") is CheckButton
		and main.get_node("GameView/ActorHudMenu/Options/ShowEther") is CheckButton
		and main.get_node("GameView/ActorHudMenu/Options/ShowFood") is CheckButton
		and main.get_node("GameView/ActorHudMenu/Options/ShowAction") is CheckButton,
		"character context menu exposes all overhead bar-and-number options")
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
	_expect(overhead_fill != null and overhead_fill.bg_color.r > overhead_fill.bg_color.g
		and overhead_health_label.get_theme_color("font_color").r
			> overhead_health_label.get_theme_color("font_color").g,
		"overhead health bar and numbers render red")
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
	var show_ether: CheckButton = main.get_node(
		"GameView/ActorHudMenu/Options/ShowEther") as CheckButton
	show_ether.button_pressed = false
	main.call("_on_overhead_option_toggled", false)
	_expect(not (main.get_node("GameView/ActorResourceOverlay/Rows/EtherRow") as Control).visible,
		"character menu independently toggles the overhead ethereality copy")
	show_ether.button_pressed = true
	main.call("_on_overhead_option_toggled", true)
	actor_menu.hide()
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
	_expect(knowledge_panel.visible and knowledge_list.item_count == 385
		and (main.get_node("GameView/StatsPanel/Content/StatsTabs") as TabContainer).current_tab == 1
		and root.get_visible_rect().encloses(knowledge_panel.get_global_rect()),
		"knowledge tab opens the complete server catalog within the statistics frame")
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
	app_state_inventory.set("inventory", {
		4: {"image_id": 42, "quantity": 1, "slot": 4, "flags": 6},
		5: {"image_id": 31, "quantity": 1, "slot": 5, "flags": 6},
		6: {"image_id": 35, "quantity": 1, "slot": 6, "flags": 6}})
	app_state_inventory.set("stats", {"food": 45, "ether": 0})
	main.call("_on_manufacturing_button_pressed")
	var manufacturing_list: ItemList = main.get_node(
		"GameView/ManufacturingPanel/Content/Columns/ManufacturingList") as ItemList
	var manufacturing_detail: RichTextLabel = main.get_node(
		"GameView/ManufacturingPanel/Content/Columns/ManufacturingDetail") as RichTextLabel
	var manufacturing_mix_one: Button = main.get_node(
		"GameView/ManufacturingPanel/Content/Actions/ManufacturingMixOne") as Button
	_expect(manufacturing_panel.visible and manufacturing_list.item_count == 389
		and root.get_visible_rect().encloses(manufacturing_panel.get_global_rect()),
		"complete server recipe catalog opens within the reference viewport")
	main.call("_on_manufacturing_selected", 0)
	_expect(not manufacturing_mix_one.disabled
		and manufacturing_detail.text.contains("Fire Essence")
		and manufacturing_detail.text.contains("Sulfur ×1"),
		"available recipe resolves ingredients and enables the real server action")
	app_state_inventory.set("inventory", {})
	main.call("_sync_manufacturing")
	_expect(manufacturing_mix_one.disabled
		and manufacturing_detail.text.contains("Missing Sulfur ×1"),
		"inventory reconciliation disables a recipe with explicit missing ingredients")
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
	var ground_bag_items: ItemList = main.get_node(
		"GameView/GroundBagPanel/Content/Columns/Ground/GroundBagItems") as ItemList
	_expect(ground_bag_panel.visible and ground_bag_items.item_count == 1
		and root.get_visible_rect().encloses(ground_bag_panel.get_global_rect()),
		"authoritative bag contents open within the reference viewport")
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
		"GameView/ItemSpellQuickbar/QuickContent/ItemSlots/Slot1") as Button
	var first_equipment_slot: Button = main.get_node(
		"GameView/InventoryPanel/Content/InventoryBody/EquipmentColumn/EquipmentGrid").get_child(0) as Button
	var first_quantity: Label = first_inventory_slot.get_node("Quantity") as Label
	_expect(first_inventory_slot.text.is_empty() and first_quantity.text == "9"
		and first_quantity.anchor_left == 1.0 and first_quantity.anchor_top == 1.0
		and first_inventory_slot.icon != null and not first_inventory_slot.disabled
		and first_inventory_slot.custom_minimum_size.x >= 64.0,
		"large inventory icon uses an overlaid bottom-right quantity")
	_expect(first_quick_slot.text.is_empty() and first_quick_slot.icon != null
		and first_quick_slot.tooltip_text.contains("Quantity: 9")
		and not first_quick_slot.disabled,
		"usable inventory slot populates the icon-only vertical quick slot")
	_expect(first_equipment_slot.text.is_empty() and first_equipment_slot.icon != null
		and not first_equipment_slot.disabled
		and first_equipment_slot.custom_minimum_size.x >= 64.0,
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
		"GameView/ItemSpellQuickbar/QuickContent/SpellSlots/Spell1") as Button
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
	var minimap_border: float = roundf(54.0 * float(main.get("_minimap_scale")))
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
	_expect(harvest_node != null and harvest_node.server_tile == Vector2i(770, 481),
		"the pick target sits on the tile the server named")

	# The harvest indicator follows the authoritative state, not a chat phrase.
	var started: PackedByteArray = PackedByteArray([1, 0xf0, 0x01])
	started.append_array(_nul_bytes("Mirror Reed"))
	app_state_inventory.call("_on_packet", 237, started)
	await process_frame
	_expect(harvest_banner.visible and harvest_banner.text.contains("Mirror Reed"),
		"the harvesting indicator names the resource the server reported")
	_expect(harvest_banner.get_global_rect().end.y <= 720.0
		and harvest_banner.get_global_rect().position.y >= 0.0,
		"the harvesting indicator fits within 1280x720")
	_expect(not harvest_banner.get_global_rect().intersects(
		right_stats.get_global_rect()),
		"the harvesting indicator does not cover the fixed resource rail")
	app_state_inventory.call("_on_packet", 237, PackedByteArray([0, 0, 0, 0]))
	await process_frame
	_expect(not harvest_banner.visible,
		"a server stop - moving, a full backpack, combat - clears the indicator")

	# A map change discards the previous map's objects rather than leaving
	# pick targets from somewhere else standing in the new world.
	app_state_inventory.call("_on_packet", 7, _nul_bytes("maps/nymara/mirrorhold.elm"))
	await process_frame
	_expect((app_state_inventory.get("map_objects") as Dictionary).is_empty()
		and not bool((app_state_inventory.get("harvest") as Dictionary).get("active", true)),
		"a map change clears the world objects and the harvesting state")
	app_state_inventory.set("authenticated", false)

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

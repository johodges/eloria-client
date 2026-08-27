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
	var attack_button: Button = main.get_node(
		"GameView/Quickbar/Buttons/AttackButton") as Button
	var trade_button: Button = main.get_node(
		"GameView/Quickbar/Buttons/TradeButton") as Button
	var trade_panel: Control = main.get_node("GameView/TradePanel") as Control
	var app_state_inventory: Node = root.get_node("AppState")
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
	_expect(attack_button.disabled, "attack action starts disabled without a selected target")
	_expect(trade_button.disabled and not trade_panel.visible,
		"trade starts closed and disabled without a selected player")
	var attackable_actor: Dictionary = {
		"actor_id": 77, "name": "Rat", "kind": 3, "health": 12,
		"max_health": 12, "alive": true}
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
		PackedByteArray([0, 65, 108, 105, 99, 101, 0]))
	app_state_inventory.call("_on_packet", 40,
		PackedByteArray([1, 3, 0, 9, 0, 0, 0, 7, 12]))
	app_state_inventory.call("_on_packet", 35,
		PackedByteArray([3, 0, 4, 0, 0, 0, 1, 2, 0]))
	app_state_inventory.call("_on_packet", 35,
		PackedByteArray([3, 0, 2, 0, 0, 0, 1, 2, 0]))
	app_state_inventory.call("_on_packet", 36, PackedByteArray([0]))
	app_state_inventory.call("_on_packet", 36, PackedByteArray([1]))
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
	var trade_accept_button: Button = main.get_node(
		"GameView/TradePanel/Content/Actions/TradeAccept") as Button
	_expect(trade_source.item_count == 1 and trade_own_list.item_count == 1,
		"trade source and own-offer columns render authoritative items")
	_expect(not trade_accept_button.disabled and trade_accept_button.text.contains("Confirm"),
		"mutual first acceptance enables the explicit confirmation phase")
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
		"GameView/InventoryPanel/Content/Scroll/InventoryGrid").get_child(0) as Button
	var first_quick_slot: Button = main.get_node(
		"GameView/ItemSpellQuickbar/QuickContent/Slots/Slot1") as Button
	var first_equipment_slot: Button = main.get_node(
		"GameView/InventoryPanel/Content/EquipmentGrid").get_child(0) as Button
	_expect(first_inventory_slot.text.contains("×9") and first_inventory_slot.icon != null
		and not first_inventory_slot.disabled,
		"inventory snapshot populates its server slot")
	_expect(first_quick_slot.text.contains("×9") and first_quick_slot.icon != null
		and not first_quick_slot.disabled,
		"usable inventory slot populates the matching live quick slot")
	_expect(first_equipment_slot.text.contains("×1") and first_equipment_slot.icon != null
		and not first_equipment_slot.disabled,
		"authoritative wear slot populates the equipment grid")
	main.set("selected_inventory_slot", 0)
	main.call("_sync_inventory")
	var empty_inventory_slot: Button = main.get_node(
		"GameView/InventoryPanel/Content/Scroll/InventoryGrid").get_child(1) as Button
	var empty_equipment_slot: Button = main.get_node(
		"GameView/InventoryPanel/Content/EquipmentGrid").get_child(1) as Button
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
	_expect(first_quick_slot.disabled and first_quick_slot.text.contains("12s"),
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

extends Control

@onready var login_panel: Control = %LoginPanel
@onready var game_view: Control = %GameView
@onready var creation_panel: Control = %CreationPanel
@onready var new_character_button: Button = %NewCharacter
@onready var create_name: LineEdit = %CreateName
@onready var create_password: LineEdit = %CreatePassword
@onready var create_confirm: LineEdit = %CreateConfirm
@onready var create_gender: OptionButton = %CreateGender
@onready var create_status: Label = %CreateStatus
@onready var preview_root: Node3D = %PreviewRoot
@onready var host_edit: LineEdit = %Host
@onready var port_edit: SpinBox = %Port
@onready var user_edit: LineEdit = %Username
@onready var password_edit: LineEdit = %Password
@onready var connect_button: Button = %Connect
@onready var login_button: Button = %Login
@onready var status_label: Label = %Status
@onready var world_root: Node3D = %WorldRoot
@onready var camera_rig: IsometricCameraController = %CameraRig
@onready var world_loader: WorldLoader = %WorldLoader
@onready var fallback_ground: MeshInstance3D = $GameView/ViewportContainer/Viewport/WorldRoot/Ground
@onready var main_viewport: SubViewport = $GameView/ViewportContainer/Viewport
@onready var viewport_container: SubViewportContainer = $GameView/ViewportContainer
@onready var map_viewport: SubViewport = %MapViewport
@onready var map_camera: Camera3D = %MapCamera
@onready var full_map_viewport: SubViewport = %FullMapViewport
@onready var full_map_camera: Camera3D = %FullMapCamera
@onready var minimap: TextureRect = %Minimap
@onready var full_map: Control = %FullMap
@onready var map_image: TextureRect = %MapImage
@onready var health_bar: ProgressBar = %Health
@onready var health_text: Label = %HealthText
@onready var mana_bar: ProgressBar = %Mana
@onready var mana_text: Label = %ManaText
@onready var stats_panel: Control = %StatsPanel
@onready var stats_text: RichTextLabel = %StatsText
@onready var inventory_panel: Control = %InventoryPanel
@onready var inventory_grid: GridContainer = %InventoryGrid
@onready var equipment_grid: GridContainer = %EquipmentGrid
@onready var inventory_description: RichTextLabel = %InventoryDescription
@onready var inventory_use_button: Button = %InventoryUse
@onready var inventory_equip_button: Button = %InventoryEquip
@onready var inventory_unequip_button: Button = %InventoryUnequip
@onready var attack_button: Button = %AttackButton
@onready var quick_slot_container: GridContainer = $GameView/ItemSpellQuickbar/QuickContent/Slots
@onready var spell_slot_container: GridContainer = %SpellSlots
@onready var spell_status: Label = %SpellStatus
@onready var player_map_marker: MeshInstance3D = %PlayerMapMarker
@onready var map_label: Label = %MapLabel
@onready var actor_label: Label = %ActorLabel
@onready var chat_output: RichTextLabel = %ChatOutput
@onready var chat_input: LineEdit = %ChatInput
@onready var selected_target: Label = %SelectedTarget
@onready var dialogue_panel: Control = %DialoguePanel
@onready var dialogue_name: Label = %DialogueName
@onready var dialogue_text: RichTextLabel = %DialogueText
@onready var dialogue_options: VBoxContainer = %DialogueOptions
@onready var login_background: TextureRect = %LoginBackground
@onready var login_logo: TextureRect = %LoginLogo

var actor_nodes: Dictionary = {}
var models: Dictionary = {}
var animation_config: Dictionary = {}
var map_registry: Dictionary = {}
var equipment_config: Dictionary = {}
var item_atlas := ItemAtlas.new()
var spell_catalog := SpellCatalog.new()
var gameplay_world: World3D
var loaded_server_map := ""
var adapter := CoordinateAdapter.new({"walkingHeight": 0.0, "invertServerY": true})
var preview_actor: ReplicatedActor3D
var pending_create_username := ""
var pending_create_password := ""
var inventory_slot_buttons: Array[Button] = []
var equipment_slot_buttons: Array[Button] = []
var quick_slot_buttons: Array[Button] = []
var spell_slot_buttons: Array[Button] = []
var selected_inventory_slot := -1
var cooldown_display_second := -1

func _ready() -> void:
	models = _json("res://data/actors/models.json").get("models", {})
	animation_config = _json("res://data/animations/luminous.json")
	map_registry = _json("res://data/maps/registry.json").get("maps", {})
	equipment_config = _json("res://data/actors/equipment.json")
	item_atlas.configure(_json("res://data/items/atlases.json"))
	spell_catalog.configure(_json("res://data/spells/catalog.json"))
	Network.connection_state_changed.connect(_on_connection_state_changed)
	Network.protocol_error.connect(func(message: String): status_label.text = "Protocol error: " + message)
	AppState.login_succeeded.connect(_on_login_succeeded)
	AppState.login_failed.connect(_on_login_failed)
	AppState.character_created.connect(_on_character_created)
	AppState.character_creation_failed.connect(_on_character_creation_failed)
	AppState.state_changed.connect(_on_state_changed)
	world_loader.load_completed.connect(_on_world_loaded)
	world_loader.load_failed.connect(_on_world_load_failed)
	viewport_container.gui_input.connect(_on_world_gui_input)
	_bind_shared_world()
	minimap.texture = map_viewport.get_texture()
	map_image.texture = full_map_viewport.get_texture()
	full_map.hide()
	stats_panel.hide()
	inventory_panel.hide()
	game_view.hide()
	creation_panel.hide()
	create_gender.add_item("Luminous Female", 0)
	create_gender.add_item("Luminous Male", 1)
	_apply_eloria_art()
	_apply_eloria_theme()
	_build_inventory_slots()
	_build_equipment_slots()
	_bind_quick_slots()
	_bind_spell_slots()

func _bind_shared_world() -> void:
	gameplay_world = world_root.get_world_3d()
	if gameplay_world == null:
		push_error("world_binding stage=resolve error=WorldRoot_has_no_World3D")
		return
	map_viewport.world_3d = gameplay_world
	full_map_viewport.world_3d = gameplay_world
	print_debug("world_binding stage=shared world=", gameplay_world)

func _process(_delta: float) -> void:
	if game_view.visible:
		_update_local_actor_follow()
		var display_second: int = floori(float(Time.get_ticks_msec()) / 1000.0)
		if display_second != cooldown_display_second:
			cooldown_display_second = display_second
			_sync_quick_slots()

func _on_connect_pressed() -> void:
	if AppState.connection_state != "disconnected":
		Network.disconnect_from_server()
		return
	connect_button.disabled = true
	login_button.disabled = true
	status_label.text = "Connecting…"
	var error := Network.connect_to_server(host_edit.text.strip_edges(), int(port_edit.value))
	if error != OK:
		status_label.text = "Connection failed: " + error_string(error)
		connect_button.disabled = false

func _on_new_character_pressed() -> void:
	if AppState.connection_state != "connected":
		status_label.text = "Connect to the server before creating a character."
		return
	login_panel.hide()
	creation_panel.show()
	_refresh_creation_preview()

func _on_creation_back_pressed() -> void:
	_clear_pending_creation()
	creation_panel.hide()
	login_panel.show()

func _on_create_gender_item_selected(_index: int) -> void:
	_refresh_creation_preview()

func _on_create_pressed() -> void:
	var username := create_name.text.strip_edges()
	var password := create_password.text
	if username.length() < 3 or username.length() > 20:
		create_status.text = "Name must contain 3–20 characters."
		return
	if password.length() < 4:
		create_status.text = "Password must contain at least 4 characters."
		return
	if password != create_confirm.text:
		create_status.text = "Passwords do not match."
		return
	pending_create_username = username
	pending_create_password = password
	create_status.text = "Creating character…"
	var appearance := {
		"skin": int(%CreateSkin.value), "hair": int(%CreateHair.value),
		"eyes": int(%CreateEyes.value), "shirt": int(%CreateShirt.value),
		"pants": int(%CreatePants.value), "boots": int(%CreateBoots.value),
		"head": int(%CreateHead.value), "actor_type": create_gender.get_selected_id()}
	var error := Network.create_character(username, password, appearance)
	if error != OK:
		create_status.text = "Creation request failed: " + error_string(error)
		_clear_pending_creation()

func _on_character_created() -> void:
	create_status.text = "Character created. Entering Eloria…"
	user_edit.text = pending_create_username
	var username := pending_create_username
	var password := pending_create_password
	create_password.clear()
	create_confirm.clear()
	_clear_pending_creation()
	var error := Network.login(username, password)
	if error != OK:
		create_status.text = "Created, but login failed to send: " + error_string(error)
		creation_panel.hide()
		login_panel.show()

func _on_character_creation_failed(message: String) -> void:
	create_status.text = "Creation failed: " + message
	_clear_pending_creation()

func _clear_pending_creation() -> void:
	pending_create_username = ""
	pending_create_password = ""

func _refresh_creation_preview() -> void:
	if is_instance_valid(preview_actor):
		preview_actor.queue_free()
	preview_actor = ReplicatedActor3D.new()
	preview_root.add_child(preview_actor)
	var actor_type := create_gender.get_selected_id()
	var dto := {"actor_id": 0, "x": 0, "y": 0, "rotation": 0, "actor_type": actor_type}
	var model_id := "luminous_female" if actor_type == 0 else "luminous_male"
	var errors := preview_actor.configure(dto,
		CoordinateAdapter.new({"walkingHeight": 0.0}), models.get(model_id, {}),
		animation_config, equipment_config)
	if not errors.is_empty():
		create_status.text = "Preview warnings: " + "; ".join(errors)

func _on_login_pressed() -> void:
	if AppState.authenticated:
		return
	if AppState.connection_state != "connected":
		status_label.text = "Connect to the server first."
		return
	if user_edit.text.is_empty() or password_edit.text.is_empty():
		status_label.text = "Enter username and password."
		return
	login_button.disabled = true
	status_label.text = "Authenticating…"
	var error := Network.login(user_edit.text, password_edit.text)
	password_edit.clear()
	if error != OK:
		status_label.text = "Login send failed: " + error_string(error)
		login_button.disabled = false

func _on_login_submitted(_text: String) -> void:
	if AppState.connection_state == "disconnected":
		_on_connect_pressed()
	elif AppState.connection_state == "connected":
		_on_login_pressed()

func _on_map_button_pressed() -> void:
	full_map.visible = not full_map.visible

func _on_walk_button_pressed() -> void:
	var local_actor: Dictionary = AppState.actors.get(AppState.local_actor_id, {})
	if bool(local_actor.get("sitting", false)):
		var error: Error = Network.set_sitting(false)
		if error != OK:
			push_warning("STAND_UP failed: " + error_string(error))

func _on_sit_button_pressed() -> void:
	var local_actor: Dictionary = AppState.actors.get(AppState.local_actor_id, {})
	var error: Error = Network.set_sitting(not bool(local_actor.get("sitting", false)))
	if error != OK:
		push_warning("SIT_DOWN failed: " + error_string(error))

func _on_attack_button_pressed() -> void:
	_attack_selected_actor()

func _on_chat_button_pressed() -> void:
	chat_input.grab_focus()

func _on_stats_button_pressed() -> void:
	stats_panel.visible = not stats_panel.visible
	if stats_panel.visible:
		inventory_panel.hide()
		_sync_stats()

func _on_inventory_button_pressed() -> void:
	inventory_panel.visible = not inventory_panel.visible
	if inventory_panel.visible:
		stats_panel.hide()
		_sync_inventory()

func _on_inventory_close_pressed() -> void:
	inventory_panel.hide()

func _on_inventory_use_pressed() -> void:
	_use_inventory_slot(selected_inventory_slot)

func _on_inventory_equip_pressed() -> void:
	if selected_inventory_slot < 0 or selected_inventory_slot >= 36:
		return
	var destination: int = _first_empty_slot(36, 44)
	if destination >= 0:
		_move_inventory_item(selected_inventory_slot, destination)

func _on_inventory_unequip_pressed() -> void:
	if selected_inventory_slot < 36 or selected_inventory_slot >= 44:
		return
	var destination: int = _first_empty_slot(0, 36)
	if destination >= 0:
		_move_inventory_item(selected_inventory_slot, destination)

func _on_inventory_inspect_pressed() -> void:
	if selected_inventory_slot < 0:
		return
	var error: Error = Network.look_at_inventory_item(selected_inventory_slot)
	if error != OK:
		push_warning("LOOK_AT_INVENTORY_ITEM failed: " + error_string(error))

func _on_disconnect_pressed() -> void:
	Network.disconnect_from_server()

func _on_login_succeeded() -> void:
	login_panel.hide()
	creation_panel.hide()
	game_view.show()
	map_label.text = "Entering world…"
	_load_server_map()
	_sync_world()

func _on_login_failed(message: String) -> void:
	status_label.text = "Login failed: " + message
	login_button.disabled = false

func _on_connection_state_changed(value: String) -> void:
	status_label.text = value.capitalize()
	connect_button.text = "Disconnect" if value == "connected" else "Connect"
	connect_button.disabled = value == "connecting"
	login_button.disabled = value != "connected" or AppState.authenticated
	new_character_button.disabled = value != "connected" or AppState.authenticated
	if value == "disconnected" and game_view.visible:
		_clear_world_presentation()
		game_view.hide()
		login_panel.show()
		status_label.text = "Disconnected"

func _clear_world_presentation() -> void:
	for raw_node: Variant in actor_nodes.values():
		var actor_node: Node = raw_node as Node
		if is_instance_valid(actor_node):
			actor_node.queue_free()
	actor_nodes.clear()
	world_loader.unload_world()
	loaded_server_map = ""
	full_map.hide()
	inventory_panel.hide()
	stats_panel.hide()
	dialogue_panel.hide()
	chat_output.clear()
	selected_target.text = "Target: none"

func _unhandled_input(event: InputEvent) -> void:
	if not game_view.visible:
		return
	for spell_slot: int in range(6):
		if event.is_action_pressed("quick_spell_%d" % (spell_slot + 1)):
			_cast_spell_slot(spell_slot)
			get_viewport().set_input_as_handled()
			return
	if event.is_action_pressed("attack_selected"):
		_attack_selected_actor()
		get_viewport().set_input_as_handled()
		return
	for slot: int in range(8):
		if event.is_action_pressed("quick_item_%d" % (slot + 1)):
			_use_inventory_slot(slot)
			get_viewport().set_input_as_handled()
			return
	if event.is_action_pressed("toggle_map") or (event is InputEventKey and event.pressed and event.keycode == KEY_TAB):
		full_map.visible = not full_map.visible
		get_viewport().set_input_as_handled()
		return
	if event.is_action_pressed("chat_focus"):
		chat_input.grab_focus()
		get_viewport().set_input_as_handled()
		return
	if event.is_action_pressed("cancel"):
		if dialogue_panel.visible:
			AppState.close_dialogue()
		elif inventory_panel.visible:
			inventory_panel.hide()
		elif stats_panel.visible:
			stats_panel.hide()
		elif full_map.visible:
			full_map.hide()
		else:
			chat_input.release_focus()
		get_viewport().set_input_as_handled()
		return
	if event.is_action_pressed("toggle_sit"):
		var local_actor: Dictionary = AppState.actors.get(AppState.local_actor_id, {})
		var wants_to_sit: bool = not bool(local_actor.get("sitting", false))
		var sit_error: Error = Network.set_sitting(wants_to_sit)
		if sit_error != OK:
			push_warning("SIT_DOWN failed: " + error_string(sit_error))
		get_viewport().set_input_as_handled()
		return

func _on_world_gui_input(event: InputEvent) -> void:
	if not game_view.visible or full_map.visible or dialogue_panel.visible:
		return
	if event is InputEventMouseButton:
		var mouse_button: InputEventMouseButton = event as InputEventMouseButton
		if camera_rig.handle_mouse_button(mouse_button):
			viewport_container.accept_event()
			return
		if mouse_button.pressed and mouse_button.button_index == MOUSE_BUTTON_LEFT:
			_handle_world_click(mouse_button, _local_viewport_position(mouse_button.position))
			viewport_container.accept_event()
	elif event is InputEventMouseMotion:
		var mouse_motion: InputEventMouseMotion = event as InputEventMouseMotion
		if camera_rig.handle_mouse_motion(mouse_motion):
			viewport_container.accept_event()

func _handle_world_click(event: InputEventMouseButton, viewport_position: Vector2) -> void:
	var picked_actor_id: int = _pick_actor(viewport_position)
	if picked_actor_id >= 0:
		AppState.select_actor(picked_actor_id)
		var selected_dto: Dictionary = AppState.actors.get(picked_actor_id, {})
		if AppState.pending_spell_target == "actor":
			var spell_touch_error: Error = Network.touch_actor(picked_actor_id)
			if spell_touch_error != OK:
				push_warning("TOUCH_PLAYER spell target failed: " + error_string(spell_touch_error))
			return
		if event.alt_pressed and _is_attackable_actor(picked_actor_id, selected_dto):
			_send_attack(picked_actor_id)
			return
		if int(selected_dto.get("kind", 0)) == 2:
			var touch_error: Error = Network.touch_actor(picked_actor_id)
			if touch_error != OK:
				push_warning("TOUCH_PLAYER failed: " + error_string(touch_error))
		return
	var ray_origin: Vector3 = camera_rig.ray_origin(viewport_position)
	var ray_direction: Vector3 = camera_rig.ray_direction(viewport_position)
	var point: Variant = _navigation_ray_position(ray_origin, ray_direction)
	if not point is Vector3:
		var ground_height: float = adapter.walking_height
		if actor_nodes.has(AppState.local_actor_id):
			var local_actor_node: Node3D = actor_nodes.get(AppState.local_actor_id) as Node3D
			if is_instance_valid(local_actor_node):
				ground_height = local_actor_node.global_position.y
		point = camera_rig.screen_to_ground(viewport_position, ground_height)
	print_debug("world_input local_click=", event.position, " viewport=", viewport_position,
		" ray_origin=", ray_origin, " ray_direction=", ray_direction, " intersection=", point)
	if point is Vector3:
		var tile: Vector2i = adapter.godot_to_server(point as Vector3)
		print_debug("world_input godot=", point, " server_tile=", tile,
			" command=", "RUN_TO" if event.shift_pressed else "MOVE_TO")
		var move_error: Error = Network.move_to(tile, event.shift_pressed)
		if move_error != OK:
			push_warning("MOVE_TO failed: " + error_string(move_error))

func _on_state_changed(path: StringName) -> void:
	if not AppState.authenticated:
		return
	match path:
		&"map":
			_load_server_map()
			_sync_world()
		&"actors", &"local_actor":
			_sync_world()
			_sync_selection()
		&"chat":
			_sync_chat()
		&"stats":
			_sync_stats()
			_sync_spells()
		&"inventory", &"inventory_text":
			_sync_inventory()
			_sync_spells()
		&"inventory_cooldowns":
			_sync_quick_slots()
		&"spells":
			_sync_spells()
		&"selection":
			_sync_selection()
		&"npc_dialogue":
			_sync_dialogue()

func _load_server_map() -> void:
	if AppState.current_map.is_empty() or loaded_server_map == AppState.current_map:
		return
	var normalized_map: String = MapRegistry.normalize_server_map_id(AppState.current_map)
	var entry: Dictionary = MapRegistry.resolve(map_registry, AppState.current_map)
	if entry.is_empty():
		map_label.text = "Map: " + AppState.current_map + " (GLB package unavailable)"
		push_error("map_registry_miss server_id=%s normalized=%s keys=%s" % [
			AppState.current_map, normalized_map, map_registry.keys()])
		return
	loaded_server_map = AppState.current_map
	adapter = CoordinateAdapter.new(entry.get("coordinateTransform", {}))
	for node in actor_nodes.values():
		node.queue_free()
	actor_nodes.clear()
	var manifest_resource: String = str(entry.get("manifest", ""))
	var manifest_path: String = ProjectSettings.globalize_path(manifest_resource)
	print_debug("map_resolved server_id=", AppState.current_map,
		" normalized=", normalized_map, " registry_key=", entry.get("registryKey", ""),
		" manifest_resource=", manifest_resource, " manifest_path=", manifest_path)
	world_loader.load_world(manifest_path)
	map_label.text = "Loading " + AppState.current_map + "…"

func _on_world_loaded(manifest: WorldManifest) -> void:
	_bind_shared_world()
	fallback_ground.hide()
	map_label.text = "Map: " + manifest.data.get("asset", {}).get("name", manifest.asset_id())
	_configure_full_map(manifest)
	_sync_world()
	_snap_all_actors_to_surface.call_deferred()

func _snap_all_actors_to_surface() -> void:
	await get_tree().physics_frame
	for actor_value: Variant in actor_nodes.values():
		var actor: ReplicatedActor3D = actor_value as ReplicatedActor3D
		if is_instance_valid(actor):
			_place_actor_on_surface(actor)

func _on_world_load_failed(errors: Array[String]) -> void:
	fallback_ground.show()
	map_label.text = "Map load failed: " + "; ".join(errors)

func _sync_world() -> void:
	map_label.text = "Map: " + (AppState.current_map if not AppState.current_map.is_empty() else "loading")
	for id in actor_nodes.keys():
		if not AppState.actors.has(id):
			actor_nodes[id].queue_free()
			actor_nodes.erase(id)
	for id in AppState.actors:
		var dto: Dictionary = AppState.actors[id]
		if actor_nodes.has(id):
			actor_nodes[id].apply_server_state(dto, adapter)
			_place_actor_on_surface(actor_nodes[id] as ReplicatedActor3D)
			continue
		var node := ReplicatedActor3D.new()
		node.name = "Actor_%d" % id
		world_root.add_child(node)
		actor_nodes[id] = node
		var model_id := _model_for_actor(dto)
		var errors := node.configure(dto, adapter, models.get(model_id, {}),
			animation_config, equipment_config)
		if not errors.is_empty():
			push_warning("Actor %d: %s" % [id, "; ".join(errors)])
		node.apply_server_state(dto, adapter, true)
		_place_actor_on_surface(node)
	actor_label.text = "Actors: %d" % AppState.actors.size()
	if AppState.local_actor_id >= 0 and actor_nodes.has(AppState.local_actor_id):
		_update_local_actor_follow()
		var local_dto: Dictionary = AppState.actors[AppState.local_actor_id]
		var current_health := int(local_dto.get("health", 0))
		var maximum_health := maxi(1, int(local_dto.get("max_health", 1)))
		if AppState.stats.is_empty():
			health_bar.max_value = maximum_health
			health_bar.value = current_health
			health_text.text = "Health: %d / %d" % [current_health, maximum_health]

func _update_local_actor_follow() -> void:
	if AppState.local_actor_id < 0:
		return
	var target_value: Variant = actor_nodes.get(AppState.local_actor_id)
	if not target_value is Node3D:
		return
	var target: Node3D = target_value as Node3D
	if not is_instance_valid(target):
		return
	var focus_position: Vector3 = target.global_position
	camera_rig.set_focus(focus_position)
	map_camera.global_position = focus_position + Vector3(0, 220, 0)
	map_camera.rotation_degrees = Vector3(-90, 0, 0)
	# Render above the actor and ignore depth so roofs/bridges cannot hide the
	# local-position dot in either top-down map camera.
	player_map_marker.global_position = focus_position + Vector3(0, 5.0, 0)
	player_map_marker.visible = true

func _place_actor_on_surface(actor: ReplicatedActor3D) -> void:
	if not is_instance_valid(actor) or gameplay_world == null:
		return
	var actor_position: Vector3 = actor.server_target
	var ray_start: Vector3 = Vector3(actor_position.x, 400.0, actor_position.z)
	var ray_end: Vector3 = Vector3(actor_position.x, -100.0, actor_position.z)
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(
		ray_start, ray_end, WorldLoader.NAVIGATION_SURFACE_LAYER)
	var hit: Dictionary = gameplay_world.direct_space_state.intersect_ray(query)
	var hit_position_value: Variant = hit.get("position")
	if hit_position_value is Vector3:
		var hit_position: Vector3 = hit_position_value as Vector3
		actor.set_surface_height(hit_position.y + 0.02)
		if actor.actor_id == AppState.local_actor_id:
			print_debug("local_actor_placement map=", AppState.current_map,
				" actor_id=", actor.actor_id, " server_target=", actor_position,
				" navigation_hit=", hit_position, " render=", actor.render_diagnostics(),
				" camera=", camera_rig.camera_diagnostics())
	else:
		actor.set_surface_height(adapter.walking_height + 0.02)
		if actor.actor_id == AppState.local_actor_id:
			push_warning("local_actor_placement navigation_miss map=%s actor_id=%d target=%s fallback_y=%.3f" % [
				AppState.current_map, actor.actor_id, actor_position, adapter.walking_height + 0.02])

func _navigation_ray_position(origin: Vector3, direction: Vector3) -> Variant:
	if gameplay_world == null:
		return null
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(
		origin, origin + direction * 2000.0, WorldLoader.NAVIGATION_SURFACE_LAYER)
	var hit: Dictionary = gameplay_world.direct_space_state.intersect_ray(query)
	var position_value: Variant = hit.get("position")
	return position_value if position_value is Vector3 else null

func _configure_full_map(manifest: WorldManifest) -> void:
	var asset_value: Variant = manifest.data.get("asset", {})
	if not asset_value is Dictionary:
		return
	var asset: Dictionary = asset_value as Dictionary
	var bounds_value: Variant = asset.get("bounds", {})
	if not bounds_value is Dictionary:
		return
	var bounds: Dictionary = bounds_value as Dictionary
	var min_value: Variant = bounds.get("min", [])
	var max_value: Variant = bounds.get("max", [])
	if not min_value is Array or not max_value is Array:
		return
	var minimum: Array = min_value as Array
	var maximum: Array = max_value as Array
	if minimum.size() < 3 or maximum.size() < 3:
		return
	var center: Vector3 = Vector3(
		(float(minimum[0]) + float(maximum[0])) * 0.5,
		maxf(float(maximum[1]) + 100.0, 300.0),
		(float(minimum[2]) + float(maximum[2])) * 0.5)
	var extent: float = maxf(float(maximum[0]) - float(minimum[0]),
		float(maximum[2]) - float(minimum[2]))
	full_map_camera.global_position = center
	full_map_camera.rotation_degrees = Vector3(-90, 0, 0)
	full_map_camera.size = extent * 1.05
	full_map_camera.far = maxf(2500.0, center.y + 500.0)

func _sync_chat() -> void:
	chat_output.clear()
	for line in AppState.chat_lines.slice(maxi(0, AppState.chat_lines.size() - 100)):
		chat_output.append_text(str(line.text) + "\n")
	chat_output.scroll_to_line(maxi(0, chat_output.get_line_count() - 1))

func _sync_stats() -> void:
	var stats: Dictionary = AppState.stats
	if stats.is_empty():
		return
	var health: int = int(stats.get("health", 0))
	var max_health: int = maxi(1, int(stats.get("max_health", 1)))
	var ether: int = int(stats.get("ether", 0))
	var max_ether: int = maxi(1, int(stats.get("max_ether", 1)))
	health_bar.max_value = max_health
	health_bar.value = health
	health_text.text = "Health: %d / %d" % [health, max_health]
	mana_bar.max_value = max_ether
	mana_bar.value = ether
	mana_text.text = "Mana: %d / %d   Food: %d   Carry: %d / %d" % [
		ether, max_ether, int(stats.get("food", 0)),
		int(stats.get("carried", 0)), int(stats.get("capacity", 0))]
	var lines: Array[String] = ["[center][b]CHARACTER STATISTICS[/b][/center]"]
	var displayed_stats: Array[Array] = [
		["Physique", "physique"], ["Coordination", "coordination"],
		["Reasoning", "reasoning"], ["Will", "will"],
		["Instinct", "instinct"], ["Vitality", "vitality"],
		["Attack", "attack"], ["Defense", "defense"], ["Magic", "magic"],
		["Harvesting", "harvesting"], ["Alchemy", "alchemy"],
		["Manufacturing", "manufacturing"], ["Summoning", "summoning"],
		["Crafting", "crafting"], ["Engineering", "engineering"],
		["Tailoring", "tailoring"], ["Ranging", "ranging"], ["Overall", "overall"]]
	for label_and_key: Array in displayed_stats:
		lines.append("%s: %d" % [label_and_key[0], int(stats.get(label_and_key[1], 0))])
	stats_text.text = "\n".join(lines)

func _build_inventory_slots() -> void:
	for slot: int in range(36):
		var button: Button = Button.new()
		button.custom_minimum_size = Vector2(64.0, 52.0)
		button.expand_icon = true
		button.text = str(slot + 1)
		button.tooltip_text = "Empty inventory slot %d" % (slot + 1)
		button.disabled = true
		button.pressed.connect(_on_inventory_slot_pressed.bind(slot))
		inventory_grid.add_child(button)
		inventory_slot_buttons.append(button)

func _build_equipment_slots() -> void:
	for index: int in range(8):
		var button: Button = Button.new()
		button.custom_minimum_size = Vector2(92.0, 48.0)
		button.expand_icon = true
		button.text = "Wear %d" % (index + 1)
		button.tooltip_text = "Generic legacy equipment position %d" % (index + 1)
		button.disabled = true
		button.pressed.connect(_on_equipment_slot_pressed.bind(36 + index))
		equipment_grid.add_child(button)
		equipment_slot_buttons.append(button)

func _bind_quick_slots() -> void:
	var slot: int = 0
	for child: Node in quick_slot_container.get_children():
		if child is Button:
			var button: Button = child as Button
			button.pressed.connect(_on_quick_slot_pressed.bind(slot))
			quick_slot_buttons.append(button)
			slot += 1

func _bind_spell_slots() -> void:
	var slot := 0
	for child: Node in spell_slot_container.get_children():
		if child is Button:
			var button: Button = child as Button
			button.pressed.connect(_cast_spell_slot.bind(slot))
			spell_slot_buttons.append(button)
			slot += 1
	_sync_spells()

func _sync_inventory() -> void:
	for slot: int in range(inventory_slot_buttons.size()):
		var button: Button = inventory_slot_buttons[slot]
		var item_value: Variant = AppState.inventory.get(slot)
		if item_value is Dictionary:
			var item: Dictionary = item_value as Dictionary
			var image_id: int = int(item.get("image_id", 0))
			button.icon = item_atlas.icon_for(image_id)
			button.text = "×%d" % int(item.get("quantity", 0))
			button.tooltip_text = _inventory_tooltip(item)
			button.disabled = false
		else:
			button.icon = null
			button.text = str(slot + 1)
			var can_place: bool = (selected_inventory_slot >= 0
				and selected_inventory_slot < 44
				and AppState.inventory.has(selected_inventory_slot))
			button.tooltip_text = ("Move selected item to slot %d" % (slot + 1)
				if can_place else "Empty inventory slot %d" % (slot + 1))
			button.disabled = not can_place
	_sync_equipment_slots()
	_sync_quick_slots()
	if selected_inventory_slot >= 0:
		var selected_value: Variant = AppState.inventory.get(selected_inventory_slot)
		if selected_value is Dictionary:
			var selected_item: Dictionary = selected_value as Dictionary
			inventory_use_button.disabled = (not bool(selected_item.get("inventory_usable", false))
				or _inventory_cooldown_remaining(selected_inventory_slot) > 0)
		else:
			selected_inventory_slot = -1
			inventory_use_button.disabled = true
	if not AppState.inventory_text.is_empty():
		inventory_description.text = AppState.inventory_text

func _sync_equipment_slots() -> void:
	for index: int in range(equipment_slot_buttons.size()):
		var slot: int = 36 + index
		var button: Button = equipment_slot_buttons[index]
		var item_value: Variant = AppState.inventory.get(slot)
		if item_value is Dictionary:
			var item: Dictionary = item_value as Dictionary
			button.icon = item_atlas.icon_for(int(item.get("image_id", 0)))
			button.text = "Wear %d ×%d" % [index + 1, int(item.get("quantity", 1))]
			button.tooltip_text = _inventory_tooltip(item) + "\nEquipped position %d" % (index + 1)
			button.disabled = false
		else:
			button.icon = null
			button.text = "Wear %d" % (index + 1)
			var can_equip_here: bool = (selected_inventory_slot >= 0
				and selected_inventory_slot < 36
				and AppState.inventory.has(selected_inventory_slot))
			button.tooltip_text = ("Equip selected item in generic wear position %d" % (index + 1)
				if can_equip_here else "Empty generic equipment position %d" % (index + 1))
			button.disabled = not can_equip_here
	inventory_equip_button.disabled = (selected_inventory_slot < 0
		or selected_inventory_slot >= 36 or _first_empty_slot(36, 44) < 0)
	inventory_unequip_button.disabled = (selected_inventory_slot < 36
		or selected_inventory_slot >= 44 or _first_empty_slot(0, 36) < 0)

func _sync_quick_slots() -> void:
	for slot: int in range(quick_slot_buttons.size()):
		var quick_button: Button = quick_slot_buttons[slot]
		var quick_item_value: Variant = AppState.inventory.get(slot)
		if quick_item_value is Dictionary:
			var quick_item: Dictionary = quick_item_value as Dictionary
			var usable: bool = bool(quick_item.get("inventory_usable", false))
			var cooldown_seconds: int = _inventory_cooldown_remaining(slot)
			quick_button.icon = item_atlas.icon_for(int(quick_item.get("image_id", 0)))
			quick_button.expand_icon = true
			quick_button.text = "%d  ×%d%s" % [slot + 1, int(quick_item.get("quantity", 0)),
				"\n%ds" % cooldown_seconds if cooldown_seconds > 0 else ""]
			quick_button.disabled = not usable or cooldown_seconds > 0
			quick_button.tooltip_text = ((_inventory_tooltip(quick_item)
				+ "\nCooldown: %d seconds" % cooldown_seconds) if cooldown_seconds > 0 else
				_inventory_tooltip(quick_item) if usable else
				_inventory_tooltip(quick_item) + "\nThis item cannot be used directly.")
		else:
			quick_button.icon = null
			quick_button.text = str(slot + 1)
			quick_button.disabled = true
			quick_button.tooltip_text = "Empty item quick slot"
	if selected_inventory_slot >= 0:
		var selected_value: Variant = AppState.inventory.get(selected_inventory_slot)
		if selected_value is Dictionary:
			var selected_item: Dictionary = selected_value as Dictionary
			inventory_use_button.disabled = (not bool(selected_item.get("inventory_usable", false))
				or _inventory_cooldown_remaining(selected_inventory_slot) > 0)

func _sync_spells() -> void:
	for slot: int in range(spell_slot_buttons.size()):
		var button: Button = spell_slot_buttons[slot]
		if slot >= spell_catalog.default_quick_slots.size():
			button.icon = null
			button.text = "S%d" % (slot + 1)
			button.tooltip_text = "Empty spell quick slot"
			button.disabled = true
			continue
		var spell_id: int = spell_catalog.default_quick_slots[slot]
		var definition: Dictionary = spell_catalog.spell(spell_id)
		var reasons: Array[String] = spell_catalog.unavailable_reasons(
			spell_id, AppState.owned_sigils, AppState.stats, AppState.inventory)
		if not AppState.pending_spell_target.is_empty():
			reasons.append("Complete the pending spell target first")
		button.icon = spell_catalog.icon_for(spell_id)
		button.expand_icon = true
		button.text = "S%d" % (slot + 1)
		button.disabled = not reasons.is_empty()
		button.tooltip_text = _spell_tooltip(definition, reasons, slot)
	match AppState.pending_spell_target:
		"actor":
			spell_status.text = "Select an actor for the spell"
		"location":
			spell_status.text = "Select a ground location for the spell"
		_:
			spell_status.text = _spell_result_text(AppState.last_spell_result)

func _spell_tooltip(definition: Dictionary, reasons: Array[String], slot: int) -> String:
	var lines: Array[String] = [str(definition.get("name", "Unknown spell")),
		str(definition.get("description", "")), "Mana: %d  Magic: %d" % [
			int(definition.get("mana", 0)), int(definition.get("level", 0))],
		"Shortcut: Shift+%d" % (slot + 1)]
	if reasons.is_empty():
		lines.append("Ready; the server validates the cast")
	else:
		lines.append_array(reasons)
	return "\n".join(lines)

func _spell_result_text(result: Dictionary) -> String:
	if result.is_empty():
		return "Spells synchronize with the server"
	var spell_id: int = int(result.get("spell_id", -1))
	var definition: Dictionary = spell_catalog.spell(spell_id)
	var spell_name: String = str(definition.get("name", "spell"))
	match int(result.get("status", 0)):
		1: return "%s cast successfully" % spell_name
		2: return "%s was rejected" % spell_name
		3: return "Invalid or unknown spell"
		4: return "Select an actor for %s" % spell_name
		5: return "Select a location for %s" % spell_name
		_: return "Spell response received"

func _cast_spell_slot(slot: int) -> void:
	if slot < 0 or slot >= spell_catalog.default_quick_slots.size():
		return
	var spell_id: int = spell_catalog.default_quick_slots[slot]
	var reasons: Array[String] = spell_catalog.unavailable_reasons(
		spell_id, AppState.owned_sigils, AppState.stats, AppState.inventory)
	if not reasons.is_empty() or not AppState.pending_spell_target.is_empty():
		return
	var definition: Dictionary = spell_catalog.spell(spell_id)
	var sigils_value: Variant = definition.get("sigils", [])
	if not sigils_value is Array:
		return
	var sigils: Array[int] = []
	for raw_sigil: Variant in sigils_value:
		sigils.append(int(raw_sigil))
	var error: Error = Network.cast_spell(sigils)
	if error != OK:
		push_warning("CAST_SPELL failed: " + error_string(error))
	else:
		spell_status.text = "Casting %s…" % str(definition.get("name", "spell"))

func _inventory_cooldown_remaining(slot: int) -> int:
	var cooldown_value: Variant = AppState.inventory_cooldowns.get(slot)
	if not cooldown_value is Dictionary:
		return 0
	var cooldown: Dictionary = cooldown_value as Dictionary
	var remaining_msec: int = int(cooldown.get("end_msec", 0)) - Time.get_ticks_msec()
	return maxi(0, ceili(float(remaining_msec) / 1000.0))

func _inventory_tooltip(item: Dictionary) -> String:
	var traits: Array[String] = []
	for flag_and_label: Array in [
		["inventory_usable", "usable"], ["stackable", "stackable"],
		["resource", "resource"], ["reagent", "reagent"]]:
		if bool(item.get(flag_and_label[0], false)):
			traits.append(str(flag_and_label[1]))
	return "Item image #%d — quantity %d%s" % [int(item.get("image_id", 0)),
		int(item.get("quantity", 0)), " — " + ", ".join(traits) if not traits.is_empty() else ""]

func _on_inventory_slot_pressed(slot: int) -> void:
	if not AppState.inventory.has(slot):
		if (selected_inventory_slot >= 0 and selected_inventory_slot < 44
				and AppState.inventory.has(selected_inventory_slot)):
			_move_inventory_item(selected_inventory_slot, slot)
		return
	selected_inventory_slot = slot
	var item: Dictionary = AppState.inventory.get(slot, {}) as Dictionary
	inventory_use_button.disabled = not bool(item.get("inventory_usable", false))
	_sync_equipment_slots()
	inventory_description.text = "Inspecting item image #%d…" % int(item.get("image_id", 0))
	var error: Error = Network.look_at_inventory_item(slot)
	if error != OK:
		push_warning("LOOK_AT_INVENTORY_ITEM failed: " + error_string(error))
	_sync_inventory()

func _on_equipment_slot_pressed(slot: int) -> void:
	if not AppState.inventory.has(slot):
		if (selected_inventory_slot >= 0 and selected_inventory_slot < 36
				and AppState.inventory.has(selected_inventory_slot)):
			_move_inventory_item(selected_inventory_slot, slot)
		return
	selected_inventory_slot = slot
	inventory_use_button.disabled = true
	_sync_equipment_slots()
	var error: Error = Network.look_at_inventory_item(slot)
	if error != OK:
		push_warning("LOOK_AT_INVENTORY_ITEM failed: " + error_string(error))
	_sync_inventory()

func _first_empty_slot(start: int, end: int) -> int:
	for slot: int in range(start, end):
		if not AppState.inventory.has(slot):
			return slot
	return -1

func _move_inventory_item(source: int, destination: int) -> void:
	var error: Error = Network.move_inventory_item(source, destination)
	if error != OK:
		push_warning("MOVE_INVENTORY_ITEM failed: " + error_string(error))

func _on_quick_slot_pressed(slot: int) -> void:
	_use_inventory_slot(slot)

func _use_inventory_slot(slot: int) -> void:
	var item_value: Variant = AppState.inventory.get(slot)
	if not item_value is Dictionary:
		return
	var item: Dictionary = item_value as Dictionary
	if not bool(item.get("inventory_usable", false)) or _inventory_cooldown_remaining(slot) > 0:
		return
	var error: Error = Network.use_inventory_item(slot)
	if error != OK:
		push_warning("USE_INVENTORY_ITEM failed: " + error_string(error))

func _on_chat_submitted(text: String) -> void:
	var message: String = text.strip_edges()
	if message.is_empty():
		chat_input.release_focus()
		return
	var error: Error = Network.send_chat(message)
	if error == OK:
		chat_input.clear()
	else:
		push_warning("RAW_TEXT failed: " + error_string(error))

func _sync_selection() -> void:
	var dto: Dictionary = AppState.actors.get(AppState.selected_actor_id, {})
	if dto.is_empty():
		selected_target.text = "Target: none"
	else:
		selected_target.text = "Target: %s  Health: %d / %d%s" % [
			str(dto.get("name", "Actor %d" % AppState.selected_actor_id)),
			int(dto.get("health", 0)), int(dto.get("max_health", 0)),
			"  [combat]" if bool(dto.get("in_combat", false)) else ""]
	var can_attack: bool = _is_attackable_actor(AppState.selected_actor_id, dto)
	attack_button.disabled = not can_attack
	attack_button.tooltip_text = ("Attack selected target [A] or Alt-click; the server approaches and validates combat"
		if can_attack else "Select a living player or creature to attack")
	for raw_id: Variant in actor_nodes.keys():
		var id: int = int(raw_id)
		var actor: ReplicatedActor3D = actor_nodes.get(id) as ReplicatedActor3D
		if is_instance_valid(actor):
			actor.set_selected(id == AppState.selected_actor_id)

func _is_attackable_actor(actor_id: int, dto: Dictionary) -> bool:
	if actor_id < 0 or actor_id == AppState.local_actor_id or dto.is_empty():
		return false
	var kind: int = int(dto.get("kind", 0))
	return kind in [1, 3, 4, 5] and bool(dto.get("alive", int(dto.get("health", 0)) > 0))

func _attack_selected_actor() -> void:
	var actor_id: int = AppState.selected_actor_id
	var dto: Dictionary = AppState.actors.get(actor_id, {})
	if _is_attackable_actor(actor_id, dto):
		_send_attack(actor_id)

func _send_attack(actor_id: int) -> void:
	print_debug("combat_input command=ATTACK_SOMEONE target_actor_id=", actor_id,
		" redacted_bytes=not_sensitive")
	var error: Error = Network.attack_actor(actor_id)
	if error != OK:
		push_warning("ATTACK_SOMEONE failed: " + error_string(error))

func _sync_dialogue() -> void:
	var dialogue: Dictionary = AppState.npc_dialogue
	dialogue_panel.visible = bool(dialogue.get("open", false))
	if not dialogue_panel.visible:
		return
	dialogue_name.text = str(dialogue.get("name", "NPC"))
	dialogue_text.text = str(dialogue.get("text", ""))
	for child: Node in dialogue_options.get_children():
		child.queue_free()
	var raw_options: Variant = dialogue.get("options", [])
	if raw_options is Array:
		for raw_option: Variant in raw_options:
			if not raw_option is Dictionary:
				continue
			var option: Dictionary = raw_option as Dictionary
			var button: Button = Button.new()
			button.text = str(option.get("label", "Continue"))
			button.pressed.connect(_on_dialogue_option.bind(
				int(option.get("actor_id", -1)), int(option.get("response_id", -1))))
			dialogue_options.add_child(button)

func _on_dialogue_option(actor_id: int, response_id: int) -> void:
	if actor_id < 0 or response_id < 0:
		return
	var error: Error = Network.respond_to_npc(actor_id, response_id)
	if error != OK:
		push_warning("RESPOND_TO_NPC failed: " + error_string(error))

func _viewport_position(global_position: Vector2) -> Vector2:
	var local_position: Vector2 = viewport_container.get_global_transform().affine_inverse() * global_position
	return _local_viewport_position(local_position)

func _local_viewport_position(local_position: Vector2) -> Vector2:
	if viewport_container.size.x <= 0.0 or viewport_container.size.y <= 0.0:
		return local_position
	return local_position * Vector2(main_viewport.size) / viewport_container.size

func _pick_actor(viewport_position: Vector2) -> int:
	if gameplay_world == null:
		push_warning("world_input actor_pick skipped: World3D unavailable")
		return -1
	var origin: Vector3 = camera_rig.ray_origin(viewport_position)
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(
		origin, origin + camera_rig.ray_direction(viewport_position) * 2000.0, 2)
	var hit: Dictionary = gameplay_world.direct_space_state.intersect_ray(query)
	var collider_value: Variant = hit.get("collider")
	if collider_value is ReplicatedActor3D:
		return (collider_value as ReplicatedActor3D).actor_id
	return -1

func _apply_eloria_art() -> void:
	login_background.texture = _external_texture("res://assets/ui/eloria_login_background.jpg")
	login_logo.texture = _external_texture("res://assets/ui/eloria_logo_master.png")
	var button_atlas: Texture2D = _external_texture("res://assets/ui/eloria_gamebuttons.png")
	if button_atlas != null:
		%MapButton.icon = _atlas_region(button_atlas, Rect2(128, 128, 32, 32))
		%SitButton.icon = _atlas_region(button_atlas, Rect2(192, 32, 32, 32))
		%ChatButton.icon = _atlas_region(button_atlas, Rect2(32, 0, 32, 32))
		%DisconnectButton.icon = _atlas_region(button_atlas, Rect2(224, 0, 32, 32))

static func _atlas_region(atlas: Texture2D, region: Rect2) -> AtlasTexture:
	var texture: AtlasTexture = AtlasTexture.new()
	texture.atlas = atlas
	texture.region = region
	return texture

func _apply_eloria_theme() -> void:
	var eloria_theme: Theme = Theme.new()
	var panel: StyleBoxFlat = StyleBoxFlat.new()
	panel.bg_color = Color(0.045, 0.075, 0.09, 0.92)
	panel.border_color = Color(0.72, 0.53, 0.22, 0.95)
	panel.set_border_width_all(2)
	panel.corner_radius_top_left = 7
	panel.corner_radius_top_right = 7
	panel.corner_radius_bottom_left = 7
	panel.corner_radius_bottom_right = 7
	panel.set_content_margin_all(12.0)
	eloria_theme.set_stylebox("panel", "PanelContainer", panel)
	var button: StyleBoxFlat = panel.duplicate() as StyleBoxFlat
	button.bg_color = Color(0.11, 0.18, 0.19, 0.96)
	button.set_border_width_all(1)
	eloria_theme.set_stylebox("normal", "Button", button)
	var button_hover: StyleBoxFlat = button.duplicate() as StyleBoxFlat
	button_hover.bg_color = Color(0.23, 0.31, 0.28, 0.98)
	button_hover.border_color = Color(0.94, 0.72, 0.30, 1.0)
	eloria_theme.set_stylebox("hover", "Button", button_hover)
	eloria_theme.set_stylebox("pressed", "Button", button_hover)
	var field: StyleBoxFlat = button.duplicate() as StyleBoxFlat
	field.bg_color = Color(0.025, 0.045, 0.055, 0.98)
	eloria_theme.set_stylebox("normal", "LineEdit", field)
	eloria_theme.set_color("font_color", "Label", Color(0.91, 0.86, 0.70))
	eloria_theme.set_color("font_color", "Button", Color(0.96, 0.88, 0.66))
	theme = eloria_theme

static func _external_texture(path: String) -> Texture2D:
	if path.begins_with("res://assets/"):
		var imported: Resource = ResourceLoader.load(path)
		if imported is Texture2D:
			return imported as Texture2D
		push_warning("Imported UI texture load failed: " + path)
		return null
	var absolute_path: String = ProjectSettings.globalize_path(path)
	var image: Image = Image.new()
	var error: Error
	if path.get_extension().to_lower() == "dds":
		var bytes: PackedByteArray = FileAccess.get_file_as_bytes(absolute_path)
		error = image.load_dds_from_buffer(bytes)
	else:
		error = image.load(absolute_path)
	if error != OK or image.is_empty():
		push_warning("UI texture load failed: " + path)
		return null
	return ImageTexture.create_from_image(image)

func _model_for_actor(dto: Dictionary) -> String:
	# Enhanced actors are player avatars. NPCs and creatures retain their server
	# kind and use a visible fallback until their actor type has a registry entry.
	if not bool(dto.get("enhanced", false)) and int(dto.get("kind", 0)) not in [1, 4]:
		return ""
	return "luminous_female" if int(dto.get("actor_type", 1)) == 0 else "luminous_male"

static func _json(path: String) -> Dictionary:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {}
	var parsed = JSON.parse_string(file.get_as_text())
	return parsed if parsed is Dictionary else {}

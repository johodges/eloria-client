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
var loaded_server_map := ""
var adapter := CoordinateAdapter.new({"walkingHeight": 0.0, "invertServerY": true})
var preview_actor: ReplicatedActor3D
var pending_create_username := ""
var pending_create_password := ""

func _ready() -> void:
	models = _json("res://data/actors/models.json").get("models", {})
	animation_config = _json("res://data/animations/luminous.json")
	map_registry = _json("res://data/maps/registry.json").get("maps", {})
	Network.connection_state_changed.connect(_on_connection_state_changed)
	Network.protocol_error.connect(func(message: String): status_label.text = "Protocol error: " + message)
	AppState.login_succeeded.connect(_on_login_succeeded)
	AppState.login_failed.connect(_on_login_failed)
	AppState.character_created.connect(_on_character_created)
	AppState.character_creation_failed.connect(_on_character_creation_failed)
	AppState.state_changed.connect(_on_state_changed)
	world_loader.load_completed.connect(_on_world_loaded)
	world_loader.load_failed.connect(_on_world_load_failed)
	map_viewport.world_3d = main_viewport.world_3d
	full_map_viewport.world_3d = main_viewport.world_3d
	minimap.texture = map_viewport.get_texture()
	map_image.texture = full_map_viewport.get_texture()
	full_map.hide()
	game_view.hide()
	creation_panel.hide()
	create_gender.add_item("Luminous Female", 0)
	create_gender.add_item("Luminous Male", 1)
	_apply_eloria_art()
	_apply_eloria_theme()

func _on_connect_pressed() -> void:
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
		CoordinateAdapter.new({"walkingHeight": 0.0}), models.get(model_id, {}), animation_config)
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
	connect_button.disabled = value != "disconnected"
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
	dialogue_panel.hide()
	chat_output.clear()
	selected_target.text = "Target: none"

func _unhandled_input(event: InputEvent) -> void:
	if not game_view.visible:
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
	if event is InputEventMouseButton:
		if camera_rig.handle_mouse_button(event):
			get_viewport().set_input_as_handled()
			return
		if event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
			var viewport_position: Vector2 = _viewport_position(event.global_position)
			var picked_actor_id: int = _pick_actor(viewport_position)
			if picked_actor_id >= 0:
				AppState.select_actor(picked_actor_id)
				var selected_dto: Dictionary = AppState.actors.get(picked_actor_id, {})
				if int(selected_dto.get("kind", 0)) == 2:
					var touch_error: Error = Network.touch_actor(picked_actor_id)
					if touch_error != OK:
						push_warning("TOUCH_PLAYER failed: " + error_string(touch_error))
				get_viewport().set_input_as_handled()
				return
			var local_actor: Dictionary = AppState.actors.get(AppState.local_actor_id, {})
			var ground_height: float = adapter.walking_height
			if not local_actor.is_empty() and actor_nodes.has(AppState.local_actor_id):
				var local_actor_node: Node3D = actor_nodes[AppState.local_actor_id] as Node3D
				ground_height = local_actor_node.global_position.y
			var point: Variant = camera_rig.screen_to_ground(viewport_position, ground_height)
			print_debug("world_input click=", event.global_position,
				" viewport=", viewport_position, " intersection=", point)
			if point is Vector3:
				var tile: Vector2i = adapter.godot_to_server(point as Vector3)
				print_debug("world_input godot=", point, " server_tile=", tile,
					" command=", "RUN_TO" if event.shift_pressed else "MOVE_TO")
				var error: Error = Network.move_to(tile, event.shift_pressed)
				if error == OK:
					camera_rig.pan_offset = Vector3.ZERO
				else:
					push_warning("MOVE_TO failed: " + error_string(error))
			get_viewport().set_input_as_handled()
			return
	if event is InputEventMouseMotion and camera_rig.handle_mouse_motion(event):
		get_viewport().set_input_as_handled()

func _on_state_changed(path: StringName) -> void:
	if not AppState.authenticated:
		return
	match path:
		&"map":
			_load_server_map()
			_sync_world()
		&"actors", &"local_actor":
			_sync_world()
		&"chat":
			_sync_chat()
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
	fallback_ground.hide()
	map_label.text = "Map: " + manifest.data.get("asset", {}).get("name", manifest.asset_id())
	_configure_full_map(manifest)
	_sync_world()

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
			continue
		var node := ReplicatedActor3D.new()
		node.name = "Actor_%d" % id
		world_root.add_child(node)
		actor_nodes[id] = node
		var model_id := _model_for_actor(dto)
		var errors := node.configure(dto, adapter, models.get(model_id, {}), animation_config)
		if not errors.is_empty():
			push_warning("Actor %d: %s" % [id, "; ".join(errors)])
		node.apply_server_state(dto, adapter, true)
	actor_label.text = "Actors: %d" % AppState.actors.size()
	if AppState.local_actor_id >= 0 and actor_nodes.has(AppState.local_actor_id):
		var target: Node3D = actor_nodes[AppState.local_actor_id]
		camera_rig.set_focus(target.global_position)
		map_camera.global_position = target.global_position + Vector3(0, 220, 0)
		map_camera.rotation_degrees = Vector3(-90, 0, 0)
		var local_dto: Dictionary = AppState.actors[AppState.local_actor_id]
		var current_health := int(local_dto.get("health", 0))
		var maximum_health := maxi(1, int(local_dto.get("max_health", 1)))
		health_bar.max_value = maximum_health
		health_bar.value = current_health
		health_text.text = "Health: %d / %d" % [current_health, maximum_health]

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
	selected_target.text = ("Target: none" if dto.is_empty()
		else "Target: %s" % str(dto.get("name", "Actor %d" % AppState.selected_actor_id)))
	for raw_id: Variant in actor_nodes.keys():
		var id: int = int(raw_id)
		var actor: ReplicatedActor3D = actor_nodes.get(id) as ReplicatedActor3D
		if is_instance_valid(actor):
			actor.set_selected(id == AppState.selected_actor_id)

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
	return local_position * Vector2(main_viewport.size) / viewport_container.size

func _pick_actor(viewport_position: Vector2) -> int:
	var origin: Vector3 = camera_rig.ray_origin(viewport_position)
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(
		origin, origin + camera_rig.ray_direction(viewport_position) * 2000.0, 2)
	var hit: Dictionary = main_viewport.world_3d.direct_space_state.intersect_ray(query)
	var collider_value: Variant = hit.get("collider")
	if collider_value is ReplicatedActor3D:
		return (collider_value as ReplicatedActor3D).actor_id
	return -1

func _apply_eloria_art() -> void:
	login_background.texture = _external_texture("res://../eloria-assets/ui/branding/eloria_login_background.dds")
	login_logo.texture = _external_texture("res://../eloria-assets/ui/branding/eloria_logo_master.dds")

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
	var image: Image = Image.load_from_file(ProjectSettings.globalize_path(path))
	if image.is_empty():
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

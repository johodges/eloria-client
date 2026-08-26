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
@onready var map_viewport: SubViewport = %MapViewport
@onready var map_camera: Camera3D = %MapCamera
@onready var minimap: TextureRect = %Minimap
@onready var full_map: Control = %FullMap
@onready var map_image: TextureRect = %MapImage
@onready var health_bar: ProgressBar = %Health
@onready var health_text: Label = %HealthText
@onready var map_label: Label = %MapLabel
@onready var actor_label: Label = %ActorLabel
@onready var chat_output: RichTextLabel = %ChatOutput

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
	minimap.texture = map_viewport.get_texture()
	map_image.texture = map_viewport.get_texture()
	full_map.hide()
	game_view.hide()
	creation_panel.hide()
	create_gender.add_item("Luminous Female", 0)
	create_gender.add_item("Luminous Male", 1)

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
		game_view.hide()
		login_panel.show()
		status_label.text = "Disconnected"

func _unhandled_input(event: InputEvent) -> void:
	if not game_view.visible:
		return
	if event.is_action_pressed("toggle_map") or (event is InputEventKey and event.pressed and event.keycode == KEY_TAB):
		full_map.visible = not full_map.visible
		get_viewport().set_input_as_handled()
		return
	if event is InputEventMouseButton:
		if camera_rig.handle_mouse_button(event):
			get_viewport().set_input_as_handled()
			return
		if event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
			var local_actor: Dictionary = AppState.actors.get(AppState.local_actor_id, {})
			var ground_height: float = adapter.walking_height
			if not local_actor.is_empty() and actor_nodes.has(AppState.local_actor_id):
				var local_actor_node: Node3D = actor_nodes[AppState.local_actor_id] as Node3D
				ground_height = local_actor_node.global_position.y
			var point: Variant = camera_rig.screen_to_ground(event.position, ground_height)
			if point is Vector3:
				var tile: Vector2i = adapter.godot_to_server(point as Vector3)
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

func _load_server_map() -> void:
	if AppState.current_map.is_empty() or loaded_server_map == AppState.current_map:
		return
	var entry: Dictionary = map_registry.get(AppState.current_map, {})
	if entry.has("alias"):
		entry = map_registry.get(str(entry.alias), {})
	if entry.is_empty():
		map_label.text = "Map: " + AppState.current_map + " (GLB package unavailable)"
		return
	loaded_server_map = AppState.current_map
	adapter = CoordinateAdapter.new(entry.get("coordinateTransform", {}))
	for node in actor_nodes.values():
		node.queue_free()
	actor_nodes.clear()
	var manifest_path := ProjectSettings.globalize_path(str(entry.get("manifest", "")))
	world_loader.load_world(manifest_path)
	map_label.text = "Loading " + AppState.current_map + "…"

func _on_world_loaded(manifest: WorldManifest) -> void:
	fallback_ground.hide()
	map_label.text = "Map: " + manifest.data.get("asset", {}).get("name", manifest.asset_id())
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

func _sync_chat() -> void:
	chat_output.clear()
	for line in AppState.chat_lines.slice(maxi(0, AppState.chat_lines.size() - 100)):
		chat_output.append_text(str(line.text) + "\n")
	chat_output.scroll_to_line(maxi(0, chat_output.get_line_count() - 1))

func _model_for_actor(dto: Dictionary) -> String:
	# Server player actor types 0/1 are luminous female/male respectively.
	return "luminous_female" if int(dto.get("actor_type", 1)) == 0 else "luminous_male"

static func _json(path: String) -> Dictionary:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {}
	var parsed = JSON.parse_string(file.get_as_text())
	return parsed if parsed is Dictionary else {}

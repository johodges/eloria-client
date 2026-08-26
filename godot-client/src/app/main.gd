extends Control

@onready var login_panel: Control = %LoginPanel
@onready var game_view: Control = %GameView
@onready var host_edit: LineEdit = %Host
@onready var port_edit: SpinBox = %Port
@onready var user_edit: LineEdit = %Username
@onready var password_edit: LineEdit = %Password
@onready var connect_button: Button = %ConnectButton
@onready var login_button: Button = %LoginButton
@onready var status_label: Label = %Status
@onready var world_root: Node3D = %WorldRoot
@onready var camera: Camera3D = %Camera
@onready var map_label: Label = %MapLabel
@onready var actor_label: Label = %ActorLabel
@onready var chat_output: RichTextLabel = %ChatOutput

var actor_nodes: Dictionary = {}
var models: Dictionary = {}
var animation_config: Dictionary = {}
var adapter := CoordinateAdapter.new({"walkingHeight": 0.0, "invertServerY": true})

func _ready() -> void:
	models = _json("res://data/actors/models.json").get("models", {})
	animation_config = _json("res://data/animations/luminous.json")
	Network.connection_state_changed.connect(_on_connection_state_changed)
	Network.protocol_error.connect(func(message: String): status_label.text = "Protocol error: " + message)
	AppState.login_succeeded.connect(_on_login_succeeded)
	AppState.login_failed.connect(_on_login_failed)
	AppState.state_changed.connect(_on_state_changed)
	game_view.hide()

func _on_connect_pressed() -> void:
	connect_button.disabled = true
	login_button.disabled = true
	status_label.text = "Connecting…"
	var error := Network.connect_to_server(host_edit.text.strip_edges(), int(port_edit.value))
	if error != OK:
		status_label.text = "Connection failed: " + error_string(error)
		connect_button.disabled = false

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
	game_view.show()
	map_label.text = "Entering world…"
	_sync_world()

func _on_login_failed(message: String) -> void:
	status_label.text = "Login failed: " + message
	login_button.disabled = false

func _on_connection_state_changed(value: String) -> void:
	status_label.text = value.capitalize()
	connect_button.disabled = value != "disconnected"
	login_button.disabled = value != "connected" or AppState.authenticated
	if value == "disconnected" and game_view.visible:
		game_view.hide()
		login_panel.show()
		status_label.text = "Disconnected"

func _on_state_changed(path: StringName) -> void:
	if not AppState.authenticated:
		return
	match path:
		&"map", &"actors", &"local_actor":
			_sync_world()
		&"chat":
			_sync_chat()

func _sync_world() -> void:
	map_label.text = "Map: " + (AppState.current_map if not AppState.current_map.is_empty() else "loading")
	for id in actor_nodes.keys():
		if not AppState.actors.has(id):
			actor_nodes[id].queue_free()
			actor_nodes.erase(id)
	for id in AppState.actors:
		var dto: Dictionary = AppState.actors[id]
		if not actor_nodes.has(id):
			var node := ReplicatedActor3D.new()
			node.name = "Actor_%d" % id
			world_root.add_child(node)
			actor_nodes[id] = node
			var model_id := _model_for_actor(dto)
			var errors := node.configure(dto, adapter, models.get(model_id, {}), animation_config)
			if not errors.is_empty():
				push_warning("Actor %d: %s" % [id, "; ".join(errors)])
		else:
			node.apply_server_state(dto, adapter, true)
		else:
			actor_nodes[id].apply_server_state(dto, adapter)
	actor_label.text = "Actors: %d" % AppState.actors.size()
	if AppState.local_actor_id >= 0 and actor_nodes.has(AppState.local_actor_id):
		var target: Node3D = actor_nodes[AppState.local_actor_id]
		camera.global_position = target.global_position + Vector3(0, 9, 12)
		camera.look_at(target.global_position + Vector3.UP, Vector3.UP)

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

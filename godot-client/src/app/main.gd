extends Control

@onready var host_edit: LineEdit = %Host
@onready var port_edit: SpinBox = %Port
@onready var user_edit: LineEdit = %Username
@onready var password_edit: LineEdit = %Password
@onready var status_label: Label = %Status

func _ready() -> void:
	Network.connection_state_changed.connect(_on_connection_state_changed)
	Network.protocol_error.connect(func(message: String): status_label.text = "Protocol error: " + message)

func _on_connect_pressed() -> void:
	status_label.text = "Connecting…"
	var error := Network.connect_to_server(host_edit.text.strip_edges(), int(port_edit.value))
	if error != OK:
		status_label.text = "Connection failed: " + error_string(error)

func _on_login_pressed() -> void:
	if user_edit.text.is_empty() or password_edit.text.is_empty():
		status_label.text = "Enter username and password."
		return
	var error := Network.login(user_edit.text, password_edit.text)
	password_edit.clear()
	if error != OK:
		status_label.text = "Login send failed: " + error_string(error)

func _on_connection_state_changed(value: String) -> void:
	status_label.text = value.capitalize()

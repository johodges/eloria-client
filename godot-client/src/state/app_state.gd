extends Node

signal state_changed(path: StringName)
signal login_succeeded
signal login_failed(message: String)

var connection_state := "disconnected"
var authenticated := false
var local_actor_id := -1
var current_map := ""
var actors: Dictionary = {}
var inventory: Array[Dictionary] = []
var chat_lines: Array[Dictionary] = []
var unknown_packet_count := 0
var recent_protocol_errors: Array[String] = []

func _ready() -> void:
	Network.connection_state_changed.connect(_on_connection_state_changed)
	Network.packet_received.connect(_on_packet)

func _on_connection_state_changed(value: String) -> void:
	connection_state = value
	if value == "disconnected":
		authenticated = false
		local_actor_id = -1
		actors.clear()
	state_changed.emit(&"connection")

func _on_packet(command: int, payload: PackedByteArray) -> void:
	var event := EloriaProtocol.decode_server(command, payload)
	match event.type:
		"login_ok":
			authenticated = true
			login_succeeded.emit()
			state_changed.emit(&"authentication")
		"login_error":
			authenticated = false
			login_failed.emit(event.message)
			state_changed.emit(&"authentication")
		"you_are":
			local_actor_id = event.actor_id
			state_changed.emit(&"local_actor")
		"change_map":
			current_map = event.map_name
			actors.clear()
			state_changed.emit(&"map")
		"actor_spawn":
			actors[event.actor_id] = event
			state_changed.emit(&"actors")
		"remove_actor":
			actors.erase(event.actor_id)
			state_changed.emit(&"actors")
		"clear_actors":
			actors.clear()
			state_changed.emit(&"actors")
		"actor_commands":
			for command_event in event.commands:
				if actors.has(command_event.actor_id):
					actors[command_event.actor_id]["command"] = command_event.command
			state_changed.emit(&"actors")
		"chat":
			chat_lines.append({"channel": event.channel, "text": event.text})
			if chat_lines.size() > 1000:
				chat_lines.pop_front()
			state_changed.emit(&"chat")
		"ping_request":
			Network.send_frame(EloriaProtocol.encode(EloriaProtocol.ClientMessage.PING_RESPONSE))
		"invalid":
			recent_protocol_errors.append(event.error)
			if recent_protocol_errors.size() > 50:
				recent_protocol_errors.pop_front()
			state_changed.emit(&"protocol_errors")
		"unknown":
			unknown_packet_count += 1
			state_changed.emit(&"protocol_unknown")

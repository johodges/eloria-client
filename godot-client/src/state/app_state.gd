extends Node

signal state_changed(path: StringName)

var connection_state := "disconnected"
var local_actor_id := -1
var current_map := ""
var actors: Dictionary = {}
var inventory: Array[Dictionary] = []
var chat_lines: Array[Dictionary] = []

func _ready() -> void:
	Network.connection_state_changed.connect(_on_connection_state_changed)
	Network.packet_received.connect(_on_packet)

func _on_connection_state_changed(value: String) -> void:
	connection_state = value
	state_changed.emit(&"connection")

func _on_packet(command: int, payload: PackedByteArray) -> void:
	match command:
		EloriaProtocol.ServerMessage.LOG_IN_OK:
			state_changed.emit(&"authentication")
		EloriaProtocol.ServerMessage.YOU_ARE:
			if payload.size() >= 2:
				local_actor_id = int(payload[0]) | (int(payload[1]) << 8)
				state_changed.emit(&"local_actor")
		EloriaProtocol.ServerMessage.KILL_ALL_ACTORS:
			actors.clear()
			state_changed.emit(&"actors")
		EloriaProtocol.ServerMessage.RAW_TEXT:
			chat_lines.append({"raw": payload})
			state_changed.emit(&"chat")
